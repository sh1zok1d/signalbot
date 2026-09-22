"""Outcome-blind D13 panel load and universe identity.

Feasibility path stores candle presence and quote_volume only. Close *prices*
are not parsed to floats on the feasibility path, so formation/holding returns
and IC cannot be computed from this loader.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d13 as D13
from scripts.research.discovery_sprint_04 import d13_acquire as ACQ
from scripts.research.discovery_sprint_04 import d13_exclusions as EX

CANONICALIZATION_VERSION = C.D13_CANONICALIZATION_VERSION
DOCS_REL = C.D13_DOCS_REL
RAW_REL = C.D13_RAW_REL


@dataclass(frozen=True)
class PresenceDay:
    open_ms: int
    quote_volume: float
    close_present: bool


def _object_month(key: str) -> str:
    match = ACQ.OBJECT_RE.match(key)
    if not match:
        raise C.Sprint04IntegrityError(f"D13_BAD_OBJECT_KEY:{key}")
    return match.group(2)


def refuse_protected_object(key: str) -> None:
    ACQ.refuse_protected_key(key)


def normalize_open_ms(raw: int) -> int:
    """Binance 1d open_time is millisecond UTC. Rare archive rows are microseconds."""

    ts = int(raw)
    if ts >= 10**15:
        ts //= 1000
    D13.refuse_protected_year_timestamp(ts)
    return ts


def parse_kline_presence(csv_text: str) -> list[PresenceDay]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if rows and rows[0] and rows[0][0].lower().replace("\ufeff", "").startswith("open"):
        rows = rows[1:]
    out: list[PresenceDay] = []
    for rec in rows:
        if len(rec) < 8:
            continue
        open_ms = normalize_open_ms(int(rec[0]))
        close_present = rec[4] not in ("", None)
        quote = float(rec[7]) if rec[7] not in ("", None) else 0.0
        out.append(PresenceDay(open_ms, quote, close_present))
    return out


INDEX_LEDGER_KEYSET_MISMATCH = "INDEX_LEDGER_KEYSET_MISMATCH"


def read_zip_presence(path: Path) -> list[PresenceDay]:
    C.assert_openable(path)
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        text = zf.read(name).decode("utf-8")
    return parse_kline_presence(text)


def load_object_ledger(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    ledger_path = base / DOCS_REL / "object_ledger.json"
    if not ledger_path.is_file():
        raise C.MissingLocalData("D13_OBJECT_LEDGER_MISSING")
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def load_object_key_index(*, repo: Path | None = None) -> dict[str, Any]:
    """Provenance/acquisition metadata only. Not scientific file-set authority."""

    base = repo or C.repo_root()
    index_path = base / DOCS_REL / "object_key_index.json"
    if not index_path.is_file():
        raise C.MissingLocalData("D13_OBJECT_KEY_INDEX_MISSING")
    return json.loads(index_path.read_text(encoding="utf-8"))


def assert_ledger_key_integrity(ledger: Mapping[str, Any]) -> list[str]:
    """Fail-closed unique legal-month ledger keys. Do not compare counts only."""

    objects = ledger.get("objects")
    if not isinstance(objects, list):
        raise C.Sprint04IntegrityError("D13_LEDGER_OBJECTS_MISSING")
    keys: list[str] = []
    seen: set[str] = set()
    for obj in objects:
        key = obj["key"]
        refuse_protected_object(key)
        match = ACQ.OBJECT_RE.match(key)
        if not match:
            raise C.Sprint04IntegrityError(f"D13_BAD_OBJECT_KEY:{key}")
        month = match.group(2)
        if not ACQ.month_allowed(month):
            raise C.Sprint04IntegrityError(f"D13_ILLEGAL_MONTH:{key}:{month}")
        if key in seen:
            raise C.Sprint04IntegrityError(f"D13_DUPLICATE_LEDGER_KEY:{key}")
        seen.add(key)
        keys.append(key)
    unique_n = len(seen)
    if unique_n != len(keys):
        raise C.Sprint04IntegrityError("D13_LEDGER_DUPLICATE_KEYS")
    if len(objects) != unique_n:
        raise C.Sprint04IntegrityError("D13_LEDGER_COUNT_MISMATCH")
    if int(ledger.get("n_files", -1)) != unique_n:
        raise C.Sprint04IntegrityError("D13_LEDGER_COUNT_MISMATCH")
    return keys


def legal_zip_keys_from_ledger(ledger: Mapping[str, Any]) -> list[str]:
    """Snapshot-bound scientific file-key set. Sole runtime zip authority."""

    return assert_ledger_key_integrity(ledger)


def index_legal_zip_set(index: Mapping[str, Any]) -> set[str]:
    zips = index.get("legal_zips")
    if not isinstance(zips, list):
        raise C.Sprint04IntegrityError("D13_INDEX_LEGAL_ZIPS_MISSING")
    return set(zips)


def assert_index_ledger_keyset_equal(
    index: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> None:
    """Exact-set equality. Counts-only comparison is not sufficient."""

    ledger_keys = set(legal_zip_keys_from_ledger(ledger))
    index_keys = index_legal_zip_set(index)
    if index_keys != ledger_keys:
        raise C.Sprint04IntegrityError(INDEX_LEDGER_KEYSET_MISMATCH)


def verify_index_ledger_keyset(*, repo: Path | None = None) -> dict[str, Any]:
    """Feasibility/integrity: index provenance set must equal bound ledger set."""

    index = load_object_key_index(repo=repo)
    ledger = load_object_ledger(repo=repo)
    assert_index_ledger_keyset_equal(index, ledger)
    keys = legal_zip_keys_from_ledger(ledger)
    return {
        "IDENTITY_OK": True,
        "LEDGER_UNIQUE_N": len(keys),
        "INDEX_UNIQUE_N": len(index_legal_zip_set(index)),
        "RUNTIME_FILE_AUTHORITY": "SNAPSHOT_BOUND_OBJECT_LEDGER",
    }


def scientific_file_keys(*, repo: Path | None = None) -> list[str]:
    """Legal zip keys for any scientific panel loader. Ledger-bound only."""

    return legal_zip_keys_from_ledger(load_object_ledger(repo=repo))


def load_presence_panel(
    *,
    repo: Path | None = None,
    symbols: Iterable[str] | None = None,
) -> dict[str, dict[int, PresenceDay]]:
    """Load presence from ledger-bound zip keys. Does not read the unbound index."""

    base = repo or C.repo_root()
    raw_root = base / RAW_REL
    wanted = None if symbols is None else set(symbols)
    panel: dict[str, dict[int, PresenceDay]] = {}
    for key in scientific_file_keys(repo=base):
        refuse_protected_object(key)
        match = ACQ.OBJECT_RE.match(key)
        if not match:
            raise C.Sprint04IntegrityError(f"D13_BAD_OBJECT_KEY:{key}")
        symbol = match.group(1)
        if wanted is not None and symbol not in wanted:
            continue
        path = raw_root / key
        if not path.is_file():
            raise C.MissingLocalData(f"D13_MISSING_ZIP:{key}")
        days = read_zip_presence(path)
        bucket = panel.setdefault(symbol, {})
        for day in days:
            if day.open_ms in bucket and bucket[day.open_ms] != day:
                raise C.Sprint04IntegrityError(f"D13_DUPLICATE_DAY:{symbol}:{day.open_ms}")
            bucket[day.open_ms] = day
    return panel


def verify_local_bytes_against_ledger(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    raw_root = base / RAW_REL
    ledger = load_object_ledger(repo=base)
    keys = legal_zip_keys_from_ledger(ledger)
    verified = 0
    for obj in ledger["objects"]:
        key = obj["key"]
        refuse_protected_object(key)
        path = raw_root / key
        if not path.is_file():
            raise C.MissingLocalData(f"D13_MISSING_ZIP:{key}")
        digest = C.sha256_file(path)
        if digest != obj["local_sha256"] or digest != obj["expected_sha256"]:
            raise C.SnapshotIdentityError(f"D13_LEDGER_MISMATCH:{key}")
        if obj["checksum_verification"] != "VERIFIED":
            raise C.SnapshotIdentityError(f"D13_CHECKSUM_NOT_VERIFIED:{key}")
        verified += 1
    if verified != len(keys) or verified != ledger["n_files"]:
        raise C.SnapshotIdentityError("D13_LEDGER_COUNT_MISMATCH")
    return {"VERIFIED_N": verified, "IDENTITY_OK": True}


def file_ledger_digest(ledger: Mapping[str, Any]) -> str:
    rows = [
        {
            "key": obj["key"],
            "sha256": obj["local_sha256"],
            "bytes": obj["byte_size"],
            "expected_sha256": obj["expected_sha256"],
        }
        for obj in ledger["objects"]
    ]
    rows.sort(key=lambda r: r["key"])
    return C.sha256_bytes(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def snapshot_id(*, enumeration_digest: str, ledger_digest: str) -> str:
    payload = {
        "dataset_id": C.D13_DATASET_ID,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "enumeration_digest": enumeration_digest,
        "file_ledger_digest": ledger_digest,
        "months": list(C.D13_MONTHS),
    }
    return C.sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def universe_week_identity(selected: Sequence[str]) -> str:
    payload = json.dumps(list(selected), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _close_present_map(days: Mapping[int, PresenceDay]) -> dict[int, bool]:
    return {open_ms: day.close_present for open_ms, day in days.items()}


def _quote_map(days: Mapping[int, PresenceDay]) -> dict[int, float]:
    return {open_ms: day.quote_volume for open_ms, day in days.items()}


def first_open_ms(days: Mapping[int, PresenceDay]) -> int | None:
    if not days:
        return None
    return min(days)


def eligible_at_t(
    symbol: str,
    t_ms: int,
    days: Mapping[int, PresenceDay],
    excluded: Mapping[str, str],
) -> bool:
    if symbol in excluded:
        return False
    first = first_open_ms(days)
    if first is None or not D13.listing_age_ok(first, t_ms):
        return False
    return D13.completeness_ok(_close_present_map(days), t_ms)


def no_post_t_from_presence(days: Mapping[int, PresenceDay], t_ms: int) -> bool:
    for k in range(C.D13_HOLDING_DAYS):
        open_ms = t_ms + k * C.DAY_MS
        day = days.get(open_ms)
        if day is not None and day.close_present:
            return False
    return True


def feasibility_universe_census(
    panel: Mapping[str, Mapping[int, PresenceDay]],
    enumerated: Sequence[str],
) -> dict[str, Any]:
    """Eligibility, N, selected identity, NO_POST_T_CLOSE counts. No returns."""

    exclusions = EX.freeze_exclusion_lists(enumerated)
    excluded = exclusions["EXCLUDED_SYMBOLS"]
    mondays = D13.decision_mondays()
    eligible_by_monday: dict[str, list[str]] = {}
    eligible_counts: list[int] = []
    for monday in mondays:
        t_ms = C.date_to_ms(monday)
        D13.refuse_protected_year_timestamp(t_ms)
        eligible = [
            symbol
            for symbol, days in panel.items()
            if eligible_at_t(symbol, t_ms, days, excluded)
        ]
        eligible.sort()
        eligible_by_monday[monday.isoformat()] = eligible
        eligible_counts.append(len(eligible))
    n = D13.n_from_eligible_counts(eligible_counts)
    selected_by_monday: dict[str, list[str]] = {}
    week_digests: list[str] = []
    no_post = 0
    if n >= C.D13_N_MIN:
        for monday in mondays:
            t_ms = C.date_to_ms(monday)
            eligible = eligible_by_monday[monday.isoformat()]
            liquidity = {
                symbol: D13.trailing_quote_volume(_quote_map(panel[symbol]), t_ms)
                for symbol in eligible
            }
            selected = D13.select_top_n(eligible, liquidity, n=n)
            selected_by_monday[monday.isoformat()] = selected
            week_digests.append(universe_week_identity(selected))
            for symbol in selected:
                if no_post_t_from_presence(panel[symbol], t_ms):
                    no_post += 1
    universe_identity = C.sha256_bytes(
        json.dumps(
            {
                "n": n,
                "weeks": week_digests,
                "exclusion_digest": exclusions["EXCLUSION_LIST_DIGEST"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    support = (
        n >= C.D13_N_MIN
        and len(mondays) >= C.D13_MIN_WEEKS
        and no_post == 0
    )
    return {
        "N": n,
        "N_MIN_ELIGIBLE_COUNT": min(eligible_counts) if eligible_counts else 0,
        "ELIGIBLE_COUNT_BY_MONDAY": {
            day: len(syms) for day, syms in eligible_by_monday.items()
        },
        "WEEK_N": len(mondays),
        "FIRST_DECISION_MONDAY": C.D13_FIRST_MONDAY_FLOOR.isoformat(),
        "LAST_DECISION_MONDAY": C.D13_LAST_DECISION_MONDAY.isoformat(),
        "NO_POST_T_CLOSE_SELECTED_N": no_post,
        "SELECTED_BY_MONDAY": selected_by_monday,
        "UNIVERSE_IDENTITY_DIGEST": universe_identity,
        "EXCLUSIONS": exclusions,
        "SUPPORT_PASS": support,
        "RETURNS_COMPUTED": False,
        "IC_COMPUTED": False,
        "HOLDING_RETURNS_PERSISTED": False,
        "LIQUIDITY_RANK_USED_PRIOR_28D_QUOTE_VOLUME_ONLY": True,
    }


def compact_eligible_counts(census: Mapping[str, Any]) -> dict[str, int]:
    return {k: int(v) for k, v in census["ELIGIBLE_COUNT_BY_MONDAY"].items()}


def parse_scientific_closes(csv_text: str) -> dict[int, float]:
    """Pure close parser for synthetic tests. Real-panel entry stays guarded."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if rows and rows[0] and rows[0][0].lower().replace("\ufeff", "").startswith("open"):
        rows = rows[1:]
    out: dict[int, float] = {}
    for rec in rows:
        if len(rec) < 5:
            continue
        open_ms = normalize_open_ms(int(rec[0]))
        close_px = float(rec[4])
        out[open_ms] = close_px
    return out


def load_price_panel_real(*_args: Any, **_kwargs: Any) -> dict[str, dict[int, float]]:
    """Real close-price loader. Forbidden in this unit.

    A later authorized implementation MUST iterate scientific_file_keys()
    (snapshot-bound object ledger), never object_key_index.legal_zips.
    """

    C.refuse_real_scientific_execution()
    raise C.RealScientificOutcomeForbidden("D13_PRICE_PANEL_GUARD")
