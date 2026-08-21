"""
V2-H2e: Stage-2 correction-publication coherence barrier.

**Amended per tech-lead review (round 2) -- the single-scope DIRTY/CLEAN
status this module originally exposed is REPLACED by a two-table,
revision-based, calculation_version-aware model:**

  - `stage2_raw_revision` (symbol, market_type) -> ONE monotonic BIGINT
    `raw_revision`, bumped by EVERY invalidating raw write (a genuine
    correction, OR a first-ever insert that lands inside an already-
    published derived bucket -- see `storage/db.py`'s raw writers). This
    counter has NO `calculation_version` -- raw market data has no
    calculation_version; it is a Stage-2-computation-identity concept.
  - `stage2_publication_state` (symbol, market_type, calculation_version)
    -> `published_raw_revision`: the raw revision THIS calculation_version's
    derived data was last coherently, atomically, completely published
    against. A scope+calc_version is CLEAN iff
    `published_raw_revision == (the current stage2_raw_revision.raw_revision
    for that symbol/market_type)` -- never a separately-stored boolean that
    could drift out of sync with the two real facts it's supposed to
    summarize.

Why this replaces the original single-status design (finding 3, prior
review round): the original `(symbol, market_type)`-only status meant
marking ONE calculation_version's correction CLEAN silently authorized
every OTHER calculation_version sharing that scope as CLEAN too --
including a SUPERSEDED version that was never actually republished. The
revision-comparison model fixes this structurally: a superseded version's
`published_raw_revision` (whatever it was last published against, possibly
never) stays behind the current `raw_revision` forever (nobody republishes
it), so it correctly reads as STALE/DIRTY regardless of what happens to the
active version.

Why this ALSO fixes the overlapping-correction/stale-publisher race
(finding 1): `publish_stage2_correction`'s CAS
(`mark_publication_clean_cas`) requires the caller to supply the EXACT
`raw_revision` its derived computation was performed against
(`expected_raw_revision`) and re-reads the authoritative current
`raw_revision` (`SELECT ... FOR UPDATE`, serializing concurrent
publishers/correctors for this scope) INSIDE the same transaction as the
family writes -- if a later correction bumped the revision in the
meantime, the CAS fails, the whole transaction (including every family
write already issued) rolls back, and the scope is provably still stale.
There is no wall-clock timestamp or UUID anywhere in this ordering -- the
revision is a plain DB-owned, serially-incrementing integer.

Every function here takes an already-acquired `conn` as its first
argument -- none of them acquire a pool connection or open/close a
transaction themselves. Callers compose these calls inside their OWN
transaction: `storage/db.py`'s `insert_klines`/`insert_open_interest`/
`insert_funding` (raw-revision bump, same transaction/COMMIT as the raw
write) and `Database.publish_stage2_correction` (CAS + family writes, one
transaction, CLEAN-equivalent state written last).

NEVER auto-bootstraps a scope+calc_version's `stage2_publication_state`
row (finding 6, prior review round): only a REAL, successful
`publish_stage2_correction` ever creates or updates one. Absence of a
`stage2_publication_state` row is therefore ALWAYS treated identically to
STALE/DIRTY by `open_v2_coherent_read_session` -- for a genuinely fresh,
never-corrected namespace exactly as much as for a legacy pre-H2e database
that already has raw+derived history nobody has ever explicitly
published/reconciled through this barrier. This eliminates the entire
"is this scope fresh or legacy" classification problem: there is no
silent-CLEAN code path to get wrong, because there is no automatic CLEAN
path at all -- CLEAN is earned exclusively by an explicit, atomic,
CAS-verified publish."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

__all__ = [
    "PublicationState", "PublicationStateError", "V2PublicationDirtyError",
    "V2StalePublicationError", "Stage2PublicationResult",
    "read_raw_revision", "bump_raw_revision", "read_publication_state",
    "mark_publication_clean_cas", "validate_publication_scope_args",
]


class PublicationStateError(ValueError):
    """Raised for a malformed (symbol, market_type[, calculation_version])
    publication-scope argument -- never for a genuine STALE/DIRTY state,
    which is a normal, expected outcome represented by `PublicationState`,
    not an exception."""


class V2PublicationDirtyError(RuntimeError):
    """Raised by `Database.open_v2_coherent_read_session` when the
    requested `(symbol, market_type, calculation_version)` scope is not
    CLEAN (STALE, NEVER_PUBLISHED, or the raw-revision row itself does not
    exist yet) at the moment the session's REPEATABLE READ snapshot is
    taken -- the fail-closed outcome §3.4 requires. Deliberately a
    DIFFERENT condition from H2a's `NOT_READY` (activation readiness,
    `analytics/forecasting_v2/activation_readiness.py`): `NOT_READY` means
    "this calculation_version has not yet materialized enough history to
    decide from"; `DIRTY_PUBLICATION` means "this instrument's published
    history is mid-correction (or never coherently published at all), of
    ANY calculation_version's age" -- a caller integrating both (a future
    orchestrator) MUST check them as two independent, non-collapsed
    fail-closed conditions."""

    def __init__(self, *, symbol: str, market_type: str, calculation_version: str,
                 status: str) -> None:
        self.symbol = symbol
        self.market_type = market_type
        self.calculation_version = calculation_version
        self.status = status
        super().__init__(
            f"V2 publication state for symbol={symbol!r} market_type={market_type!r} "
            f"calculation_version={calculation_version!r} is {status} -- refusing to open a "
            "coherent V2 read session (DIRTY_PUBLICATION, fail-closed per "
            "docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.4)"
        )


class V2StalePublicationError(RuntimeError):
    """Raised by `mark_publication_clean_cas` (and therefore by
    `Database.publish_stage2_correction`) when the caller's
    `expected_raw_revision` no longer matches the authoritative current
    `stage2_raw_revision.raw_revision` -- a LATER correction committed
    after this publisher started computing. The whole publish transaction
    MUST be rolled back by the caller's `conn.transaction()` context (this
    exception propagates out of it uncaught), so none of the family writes
    already issued in the same transaction survive, and the scope remains
    exactly as stale as it was before this call."""

    def __init__(self, *, symbol: str, market_type: str,
                 expected_raw_revision: int, actual_raw_revision: int) -> None:
        self.symbol = symbol
        self.market_type = market_type
        self.expected_raw_revision = expected_raw_revision
        self.actual_raw_revision = actual_raw_revision
        super().__init__(
            f"stale publication attempt for symbol={symbol!r} market_type={market_type!r}: "
            f"expected_raw_revision={expected_raw_revision!r} but the authoritative current "
            f"raw_revision is {actual_raw_revision!r} -- a later raw correction committed "
            "after this publication's computation started; this publish is rejected in full"
        )


def validate_publication_scope_args(*, symbol: str, market_type: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise PublicationStateError(f"symbol must be a non-empty str, got {symbol!r}")
    if not isinstance(market_type, str) or not market_type.strip():
        raise PublicationStateError(f"market_type must be a non-empty str, got {market_type!r}")


def validate_calculation_version_arg(calculation_version: str) -> None:
    if not isinstance(calculation_version, str) or not calculation_version.strip():
        raise PublicationStateError(
            f"calculation_version must be a non-empty str, got {calculation_version!r}")


@dataclass(frozen=True)
class PublicationState:
    """Detached, immutable snapshot combining `stage2_raw_revision` (the
    authoritative current revision for `(symbol, market_type)`) with
    `stage2_publication_state` (the revision `calculation_version` was last
    published against, if ever)."""
    symbol: str
    market_type: str
    calculation_version: str
    raw_revision: int
    published_raw_revision: Optional[int]
    publication_generation: int
    published_at: Optional[datetime]
    updated_at: datetime

    @property
    def is_clean(self) -> bool:
        return (self.published_raw_revision is not None
                and self.published_raw_revision == self.raw_revision)

    @property
    def status(self) -> str:
        if self.published_raw_revision is None:
            return "NEVER_PUBLISHED"
        return "CLEAN" if self.published_raw_revision == self.raw_revision else "STALE"


@dataclass(frozen=True)
class Stage2PublicationResult:
    """Return value of `Database.publish_stage2_correction` — a summary of
    exactly what one atomic CAS'd publish transaction wrote."""
    symbol: str
    market_type: str
    calculation_version: str
    published_raw_revision: int
    publication_generation: int
    exchange_feature_vectors_written: int
    consensus_feature_vectors_written: int
    percentile_snapshots_written: int
    data_health_snapshots_written: int
    percentile_snapshots_absent_reason: Optional[str]
    data_health_snapshots_absent_reason: Optional[str]


async def read_raw_revision(conn, *, symbol: str, market_type: str) -> Optional[int]:
    """The current authoritative `raw_revision` for `(symbol, market_type)`,
    or `None` if `stage2_raw_revision` has never been bootstrapped for this
    scope. Read-only, no lock -- for planning/reporting. A publisher's CAS
    check (`mark_publication_clean_cas`) re-reads this under `FOR UPDATE`
    inside its own transaction; this function is NOT that check."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    return await conn.fetchval(
        "SELECT raw_revision FROM stage2_raw_revision WHERE symbol=$1 AND market_type=$2",
        symbol, market_type,
    )


async def bootstrap_raw_revision(conn, *, symbol: str, market_type: str) -> str:
    """Idempotently seed `(symbol, market_type)` at `raw_revision=0` if it
    has never been bootstrapped. Returns `"SEEDED"` or
    `"ALREADY_INITIALIZED"`. Deliberately does NOT touch
    `stage2_publication_state` -- seeding the counter that raw writers
    increment makes no claim about whether any calculation_version's
    derived data is coherent; see this module's docstring."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    row = await conn.fetchrow(
        """
        INSERT INTO stage2_raw_revision (symbol, market_type, raw_revision, updated_at)
        VALUES ($1, $2, 0, now())
        ON CONFLICT (symbol, market_type) DO NOTHING
        RETURNING symbol
        """,
        symbol, market_type,
    )
    return "SEEDED" if row is not None else "ALREADY_INITIALIZED"


async def bump_raw_revision(conn, *, symbol: str, market_type: str, reason: str) -> int:
    """Atomically increment `(symbol, market_type)`'s `raw_revision` by
    exactly 1 -- creating the row at revision 1 if it has never been
    bootstrapped (an unbootstrapped scope that is already being corrected
    is not a reason to lose the correction signal). Returns the NEW
    revision. MUST be called with a `conn` inside the SAME transaction as
    the raw-data write that triggered it (one COMMIT covers both)."""
    if not isinstance(reason, str) or not reason.strip():
        raise PublicationStateError(f"reason must be a non-empty str, got {reason!r}")
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    return await conn.fetchval(
        """
        INSERT INTO stage2_raw_revision (symbol, market_type, raw_revision, last_bump_reason, updated_at)
        VALUES ($1, $2, 1, $3, now())
        ON CONFLICT (symbol, market_type) DO UPDATE SET
            raw_revision = stage2_raw_revision.raw_revision + 1,
            last_bump_reason = EXCLUDED.last_bump_reason,
            updated_at = now()
        RETURNING raw_revision
        """,
        symbol, market_type, reason,
    )


async def read_publication_state(
    conn, *, symbol: str, market_type: str, calculation_version: str,
) -> Optional[PublicationState]:
    """The combined `PublicationState` for `(symbol, market_type,
    calculation_version)`, or `None` if `stage2_raw_revision` itself has
    never been bootstrapped for this `(symbol, market_type)` (a fully
    uninitialized scope). If the raw-revision row exists but NO
    `stage2_publication_state` row exists yet for this exact
    `calculation_version`, a real `PublicationState` is still returned,
    with `published_raw_revision=None` / `status == "NEVER_PUBLISHED"` /
    `is_clean == False` -- callers MUST treat that identically to STALE
    (fail closed), never as an implicit CLEAN default."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    validate_calculation_version_arg(calculation_version)
    row = await conn.fetchrow(
        """
        SELECT r.raw_revision AS raw_revision, r.updated_at AS raw_updated_at,
               p.published_raw_revision, p.publication_generation,
               p.published_at, p.updated_at AS pub_updated_at
        FROM stage2_raw_revision r
        LEFT JOIN stage2_publication_state p
            ON p.symbol = r.symbol AND p.market_type = r.market_type
               AND p.calculation_version = $3
        WHERE r.symbol = $1 AND r.market_type = $2
        """,
        symbol, market_type, calculation_version,
    )
    if row is None:
        return None
    return PublicationState(
        symbol=symbol, market_type=market_type, calculation_version=calculation_version,
        raw_revision=row["raw_revision"],
        published_raw_revision=row["published_raw_revision"],
        publication_generation=row["publication_generation"] or 0,
        published_at=row["published_at"],
        updated_at=row["pub_updated_at"] or row["raw_updated_at"],
    )


async def mark_publication_clean_cas(
    conn, *, symbol: str, market_type: str, calculation_version: str,
    expected_raw_revision: int,
) -> int:
    """The ONLY way `stage2_publication_state` ever becomes CLEAN. Locks
    `stage2_raw_revision`'s row for `(symbol, market_type)` (`SELECT ...
    FOR UPDATE`, serializing against a concurrent raw-revision bump for the
    SAME scope), compares the authoritative current `raw_revision` to
    `expected_raw_revision`, and:

      - if they DIFFER: raises `V2StalePublicationError` -- a later
        correction committed after this publish's computation started.
        The caller's surrounding transaction MUST then roll back (this
        exception is never caught here), so every family row this publish
        attempt already wrote in the SAME transaction is undone too.
      - if they MATCH: upserts `stage2_publication_state` for this exact
        `(symbol, market_type, calculation_version)`, sets
        `published_raw_revision = expected_raw_revision`, and bumps
        `publication_generation` by exactly 1 (DB-owned, monotonic).
        Returns the NEW generation.

    This function does NOT write any derived family itself -- it is only
    ever safe to call as the LAST statement of the SAME transaction that
    already wrote every publication-member row (see
    `Database.publish_stage2_correction`)."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    validate_calculation_version_arg(calculation_version)
    if not isinstance(expected_raw_revision, int) or isinstance(expected_raw_revision, bool):
        raise PublicationStateError(
            f"expected_raw_revision must be an int, got {type(expected_raw_revision).__name__}")

    current = await conn.fetchval(
        "SELECT raw_revision FROM stage2_raw_revision WHERE symbol=$1 AND market_type=$2 "
        "FOR UPDATE",
        symbol, market_type,
    )
    if current is None:
        current = 0   # an unbootstrapped scope is treated as revision 0 for CAS purposes
    if current != expected_raw_revision:
        raise V2StalePublicationError(
            symbol=symbol, market_type=market_type,
            expected_raw_revision=expected_raw_revision, actual_raw_revision=current)

    row = await conn.fetchrow(
        """
        INSERT INTO stage2_publication_state
            (symbol, market_type, calculation_version, published_raw_revision,
             publication_generation, published_at, updated_at)
        VALUES ($1, $2, $3, $4, 1, now(), now())
        ON CONFLICT (symbol, market_type, calculation_version) DO UPDATE SET
            published_raw_revision = EXCLUDED.published_raw_revision,
            publication_generation = stage2_publication_state.publication_generation + 1,
            published_at = now(),
            updated_at = now()
        RETURNING publication_generation
        """,
        symbol, market_type, calculation_version, expected_raw_revision,
    )
    return row["publication_generation"]
