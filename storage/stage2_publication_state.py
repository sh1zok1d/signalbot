"""
V2-H2e: Stage-2 correction-publication coherence barrier.

Pure, connection-scoped helpers over `stage2_publication_state`
(`storage/stage2_schema.sql`) -- the durable DIRTY/CLEAN state machine
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.4 requires so that ONE V2
decision boundary never combines a post-correction raw fact with a
pre-correction derived fact under the same `calculation_version`.

Every function here takes an already-acquired `conn` (asyncpg connection or
connection-like object) as its first argument -- none of them acquire a pool
connection themselves, and none of them open or close a transaction. That is
deliberate: callers are REQUIRED to compose these calls inside their OWN
transaction so that (a) marking DIRTY commits atomically with the raw write
that caused it, and (b) marking CLEAN commits atomically with every
publication-member write it accompanies. See `storage/db.py`'s
`insert_klines`/`insert_open_interest`/`insert_funding` (DIRTY side) and
`Database.publish_stage2_correction` (CLEAN side) for the two call sites
that actually compose these functions inside a transaction.

No clock is read here except via Postgres's own `now()` (server-side,
deterministic per-transaction); no `uuid`/`random`; no business logic about
WHICH derived families are publication members -- that discipline lives in
`Database.publish_stage2_correction`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

__all__ = [
    "PublicationState", "PublicationStateError", "V2PublicationDirtyError",
    "Stage2PublicationResult",
    "read_publication_state", "bootstrap_publication_state",
    "mark_publication_dirty", "mark_publication_clean",
    "validate_publication_scope_args",
]


class PublicationStateError(ValueError):
    """Raised for a malformed (symbol, market_type) publication-scope
    argument -- never for a genuine DIRTY state, which is a normal,
    expected outcome represented by `PublicationState`, not an
    exception."""


class V2PublicationDirtyError(RuntimeError):
    """Raised by `Database.open_v2_coherent_read_session` when the
    requested `(symbol, market_type)` scope is DIRTY (or has never been
    bootstrapped) at the moment the session's REPEATABLE READ snapshot is
    taken -- the fail-closed outcome §3.4 requires. Deliberately a
    DIFFERENT condition from H2a's `NOT_READY` (activation readiness,
    `analytics/forecasting_v2/activation_readiness.py`): `NOT_READY` means
    "this calculation_version has not yet materialized enough history to
    decide from"; `DIRTY_PUBLICATION` means "this instrument's published
    history is mid-correction, of ANY calculation_version's age" -- a
    caller integrating both (a future orchestrator) MUST check them as
    two independent, non-collapsed fail-closed conditions."""

    def __init__(self, *, symbol: str, market_type: str, status: str) -> None:
        self.symbol = symbol
        self.market_type = market_type
        self.status = status
        super().__init__(
            f"V2 publication state for symbol={symbol!r} market_type={market_type!r} is "
            f"{status} -- refusing to open a coherent V2 read session (DIRTY_PUBLICATION, "
            "fail-closed per docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.4)"
        )


def validate_publication_scope_args(*, symbol: str, market_type: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise PublicationStateError(f"symbol must be a non-empty str, got {symbol!r}")
    if not isinstance(market_type, str) or not market_type.strip():
        raise PublicationStateError(f"market_type must be a non-empty str, got {market_type!r}")


@dataclass(frozen=True)
class PublicationState:
    """Detached, immutable snapshot of one `stage2_publication_state` row."""
    symbol: str
    market_type: str
    status: str                       # 'CLEAN' | 'DIRTY'
    publication_generation: int
    dirty_reason: Optional[str]
    dirty_since: Optional[datetime]
    clean_since: Optional[datetime]
    updated_at: datetime

    @property
    def is_clean(self) -> bool:
        return self.status == "CLEAN"


@dataclass(frozen=True)
class Stage2PublicationResult:
    """Return value of `Database.publish_stage2_correction` — a summary of
    exactly what one atomic CLEAN-transition transaction wrote."""
    symbol: str
    market_type: str
    publication_generation: int
    exchange_feature_vectors_written: int
    consensus_feature_vectors_written: int
    percentile_snapshots_written: int
    data_health_snapshots_written: int
    percentile_snapshots_absent_reason: Optional[str]
    data_health_snapshots_absent_reason: Optional[str]


def _row_to_state(row) -> PublicationState:
    return PublicationState(
        symbol=row["symbol"], market_type=row["market_type"], status=row["status"],
        publication_generation=row["publication_generation"],
        dirty_reason=row["dirty_reason"], dirty_since=row["dirty_since"],
        clean_since=row["clean_since"], updated_at=row["updated_at"],
    )


async def read_publication_state(
    conn, *, symbol: str, market_type: str,
) -> Optional[PublicationState]:
    """The ONE `stage2_publication_state` row for `(symbol, market_type)`,
    or `None` if it has never been bootstrapped -- callers MUST treat
    `None` identically to DIRTY (fail closed), never as an implicit CLEAN
    default. Read-only; issues exactly one `SELECT`."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    row = await conn.fetchrow(
        "SELECT symbol, market_type, status, publication_generation, "
        "dirty_reason, dirty_since, clean_since, updated_at "
        "FROM stage2_publication_state WHERE symbol=$1 AND market_type=$2",
        symbol, market_type,
    )
    return _row_to_state(row) if row is not None else None


async def bootstrap_publication_state(conn, *, symbol: str, market_type: str) -> str:
    """Idempotently seed a fresh `(symbol, market_type)` row CLEAN at
    `publication_generation=0` if none exists yet. Returns `"SEEDED"` or
    `"ALREADY_INITIALIZED"` -- never overwrites an existing row (in
    particular, never resets an existing DIRTY row to CLEAN; that would
    silently discard a real correctness signal). Mirrors
    `Database.bootstrap_instrument_metadata_revision`'s shape."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    row = await conn.fetchrow(
        """
        INSERT INTO stage2_publication_state
            (symbol, market_type, status, publication_generation, clean_since, updated_at)
        VALUES ($1, $2, 'CLEAN', 0, now(), now())
        ON CONFLICT (symbol, market_type) DO NOTHING
        RETURNING symbol
        """,
        symbol, market_type,
    )
    return "SEEDED" if row is not None else "ALREADY_INITIALIZED"


async def mark_publication_dirty(conn, *, symbol: str, market_type: str, reason: str) -> None:
    """Mark `(symbol, market_type)` DIRTY -- creating the row DIRTY at
    generation 0 if it does not exist yet (an unbootstrapped instrument
    that is already being corrected is not a reason to lose the
    correction signal). Idempotent and re-entrant: marking an
    already-DIRTY row DIRTY again preserves the EARLIEST `dirty_since`
    (never resets it to `now()`) and replaces `dirty_reason` with the
    latest trigger, so the row always reflects how long a scope has been
    unavailable, not merely the most recent correction.

    MUST be called with a `conn` that is inside the SAME transaction as
    the raw-data write that triggered the correction -- see this module's
    own docstring."""
    if not isinstance(reason, str) or not reason.strip():
        raise PublicationStateError(f"reason must be a non-empty str, got {reason!r}")
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    await conn.execute(
        """
        INSERT INTO stage2_publication_state
            (symbol, market_type, status, publication_generation,
             dirty_reason, dirty_since, updated_at)
        VALUES ($1, $2, 'DIRTY', 0, $3, now(), now())
        ON CONFLICT (symbol, market_type) DO UPDATE SET
            status = 'DIRTY',
            dirty_reason = EXCLUDED.dirty_reason,
            dirty_since = CASE
                WHEN stage2_publication_state.status = 'DIRTY'
                THEN stage2_publication_state.dirty_since
                ELSE now()
            END,
            updated_at = now()
        """,
        symbol, market_type, reason,
    )


async def mark_publication_clean(conn, *, symbol: str, market_type: str) -> int:
    """Flip `(symbol, market_type)` CLEAN and durably bump
    `publication_generation` by exactly 1 (DB-owned, monotonic --
    never wall-clock-derived, never random). Returns the NEW generation.

    This function does NOT write any derived family itself -- it is only
    ever safe to call as the LAST statement of the SAME transaction that
    already wrote every publication-member row (see
    `Database.publish_stage2_correction`). Calling it standalone, outside
    that transaction, would fake atomicity and is deliberately not
    supported as a public write path from `storage/db.py`."""
    validate_publication_scope_args(symbol=symbol, market_type=market_type)
    row = await conn.fetchrow(
        """
        INSERT INTO stage2_publication_state
            (symbol, market_type, status, publication_generation, clean_since, updated_at)
        VALUES ($1, $2, 'CLEAN', 1, now(), now())
        ON CONFLICT (symbol, market_type) DO UPDATE SET
            status = 'CLEAN',
            publication_generation = stage2_publication_state.publication_generation + 1,
            dirty_reason = NULL,
            clean_since = now(),
            updated_at = now()
        RETURNING publication_generation
        """,
        symbol, market_type,
    )
    return row["publication_generation"]
