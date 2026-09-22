"""Canonical Discovery Sprint 04 D12/D13 one-shot scientific execution.

Ordinary import does not load market data and cannot emit results.
Real execution requires --authorize-canonical-sprint04-execution.
EXECUTION_AUTHORIZED in common.py stays false.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pyarrow.parquet as pq

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d12 as D12
from scripts.research.discovery_sprint_04 import d13 as D13
from scripts.research.discovery_sprint_04 import d13_acquire as ACQ
from scripts.research.discovery_sprint_04 import d13_panel as P
from scripts.research.discovery_sprint_04 import restore_d13_panel as RESTORE
from scripts.research.discovery_sprint_04.d13_terminal_mark import (
    NO_POST_T_CLOSE,
    terminal_mark,
)

UNIT = "DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION"
EXECUTION_ROOT = "d2a62da6e5c907def603a258505b9cc1f92ae3a5"
EXPECTED_TREE = "3c5c5262db5c1313c8d5c712c0d1658f32da0edb"
AUTHORIZE_FLAG = "--authorize-canonical-sprint04-execution"
PERMIT_REL = "docs/research/DISCOVERY_SPRINT_04_EXECUTION_PERMIT.json"
FREEZE_REL = "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.json"
SPRINT_REL = "docs/research/DISCOVERY_SPRINT_04.json"
UNIVERSE_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/UNIVERSE_IDENTITY.json"
)
EXCLUSION_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/EXCLUSION_LISTS.json"
)
PREFIXES_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/symbol_prefixes.json"
)
RUNNER_REL = "scripts/research/discovery_sprint_04/execute_scientific.py"

RESULT_REL = {
    "D12": (
        "docs/research/discovery_results/D12_DISCOVERY_RESULT.json",
        "docs/research/discovery_results/D12_DISCOVERY_RESULT.md",
    ),
    "D13": (
        "docs/research/discovery_results/D13_DISCOVERY_RESULT.json",
        "docs/research/discovery_results/D13_DISCOVERY_RESULT.md",
    ),
    "BATCH": (
        "docs/research/DISCOVERY_SPRINT_04_RESULT.json",
        "docs/research/DISCOVERY_SPRINT_04_RESULT.md",
    ),
}


class ExecutionAbortedPreResult(RuntimeError):
    """Scientific classification must not be persisted."""


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def payload_sha256(payload: Mapping[str, Any]) -> str:
    hashed = {k: v for k, v in payload.items() if k != "RESULT_PAYLOAD_SHA256"}
    return C.sha256_bytes(canonical_json(hashed).encode("utf-8"))


def git_sha(repo: Path, rev: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", rev],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def load_json(repo: Path, rel: str) -> dict[str, Any]:
    path = repo / rel
    if not path.is_file():
        raise ExecutionAbortedPreResult(f"MISSING:{rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_execution_root(repo: Path) -> None:
    root = git_sha(repo, EXECUTION_ROOT)
    if root != EXECUTION_ROOT:
        raise ExecutionAbortedPreResult(f"EXECUTION_ROOT_UNRESOLVED:{root}")
    tree = git_sha(repo, f"{EXECUTION_ROOT}^{{tree}}")
    if tree != EXPECTED_TREE:
        raise ExecutionAbortedPreResult(f"EXECUTION_TREE_MISMATCH:{tree}")


def verify_implementation_hashes(repo: Path, freeze: Mapping[str, Any]) -> dict[str, str]:
    observed = C.implementation_hashes(repo)
    expected = freeze["IMPLEMENTATION_HASHES"]
    for rel, digest in expected.items():
        if observed.get(rel) != digest:
            raise ExecutionAbortedPreResult(
                f"IMPLEMENTATION_HASH_MISMATCH:{rel}:expected={digest}:observed={observed.get(rel)}"
            )
    freeze_path = repo / FREEZE_REL
    freeze_sha = C.sha256_file(freeze_path)
    permit = load_json(repo, PERMIT_REL)
    if freeze_sha != permit["IMPLEMENTATION_FREEZE_SHA256"]:
        raise ExecutionAbortedPreResult("FREEZE_SHA256_MISMATCH")
    if observed != permit["IMPLEMENTATION_HASHES"]:
        raise ExecutionAbortedPreResult("PERMIT_IMPLEMENTATION_HASH_MISMATCH")
    runner_sha = C.sha256_file(repo / RUNNER_REL)
    if runner_sha != permit["ONE_SHOT_RUNNER_SHA256"]:
        raise ExecutionAbortedPreResult("RUNNER_SHA256_MISMATCH")
    return observed


def verify_permit_bindings(repo: Path, freeze: Mapping[str, Any], permit: Mapping[str, Any]) -> None:
    checks = {
        "EXECUTION_ROOT": EXECUTION_ROOT,
        "EXPECTED_TREE": EXPECTED_TREE,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "D12_RANDOM_SEED": C.D12_RANDOM_SEED,
        "D13_RANDOM_SEED": C.D13_RANDOM_SEED,
        "D13_N": freeze["D13_N"],
        "D13_SNAPSHOT_ID": freeze["D13_SNAPSHOT_ID"],
        "D13_FILE_LEDGER_DIGEST": freeze["D13_FILE_LEDGER_DIGEST"],
        "D13_UNIVERSE_IDENTITY_DIGEST": freeze["D13_UNIVERSE_IDENTITY_DIGEST"],
        "D13_EXCLUSION_LIST_DIGEST": freeze["D13_EXCLUSION_LIST_DIGEST"],
        "D13_PINNED_TAKER_FEE": freeze["D13_PINNED_TAKER_FEE"],
        "D13_FRICTION_FLOOR": freeze["D13_FRICTION_FLOOR"],
        "D12_DATASET_ID": C.CORE_BTC_DATASET_ID,
        "D12_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
    }
    for key, want in checks.items():
        got = permit.get(key)
        if got != want:
            raise ExecutionAbortedPreResult(f"PERMIT_MISMATCH:{key}:expected={want}:observed={got}")
    if permit.get("EXECUTION_AUTHORIZED_IN_COMMON_PY") is not False:
        raise ExecutionAbortedPreResult("PERMIT_MUST_KEEP_COMMON_EXECUTION_AUTHORIZED_FALSE")


def verify_d13_frozen_identity(repo: Path, freeze: Mapping[str, Any]) -> dict[str, Any]:
    prefixes = load_json(repo, PREFIXES_REL)
    ledger = P.load_object_ledger(repo=repo)
    universe = load_json(repo, UNIVERSE_REL)
    exclusions = load_json(repo, EXCLUSION_REL)
    pin = json.loads((repo / C.D13_FEE_AUTHORITY_REL).read_text(encoding="utf-8"))
    P.verify_index_ledger_keyset(repo=repo)
    ledger_digest = P.file_ledger_digest(ledger)
    snap = P.snapshot_id(
        enumeration_digest=prefixes["listing_digest"],
        ledger_digest=ledger_digest,
    )
    if prefixes["listing_digest"] != freeze["D13_SYMBOL_ENUMERATION_AUTHORITY"]:
        raise ExecutionAbortedPreResult("D13_ENUMERATION_MISMATCH")
    if ledger_digest != freeze["D13_FILE_LEDGER_DIGEST"]:
        raise ExecutionAbortedPreResult("D13_LEDGER_DIGEST_MISMATCH")
    if snap != freeze["D13_SNAPSHOT_ID"]:
        raise ExecutionAbortedPreResult("D13_SNAPSHOT_MISMATCH")
    if universe["UNIVERSE_IDENTITY_DIGEST"] != freeze["D13_UNIVERSE_IDENTITY_DIGEST"]:
        raise ExecutionAbortedPreResult("D13_UNIVERSE_DIGEST_MISMATCH")
    if exclusions["EXCLUSION_LIST_DIGEST"] != freeze["D13_EXCLUSION_LIST_DIGEST"]:
        raise ExecutionAbortedPreResult("D13_EXCLUSION_DIGEST_MISMATCH")
    if int(universe["N"]) != 82 or int(freeze["D13_N"]) != 82:
        raise ExecutionAbortedPreResult("D13_N_MISMATCH")
    if universe["FIRST_DECISION_MONDAY"] != "2020-02-03":
        raise ExecutionAbortedPreResult("D13_FIRST_MONDAY_MISMATCH")
    if universe["LAST_DECISION_MONDAY"] != "2024-12-23":
        raise ExecutionAbortedPreResult("D13_LAST_MONDAY_MISMATCH")
    if int(universe["NO_POST_T_CLOSE_SELECTED_N"]) != 0:
        raise ExecutionAbortedPreResult("D13_NO_POST_FREEZE_MISMATCH")
    if float(pin["PINNED_TAKER_FEE"]) != 0.001:
        raise ExecutionAbortedPreResult("D13_FEE_MISMATCH")
    if float(pin["FRICTION_FLOOR"]) != 0.004:
        raise ExecutionAbortedPreResult("D13_FRICTION_MISMATCH")
    if C.D12_RANDOM_SEED != 20260922196 or C.D13_RANDOM_SEED != 20260922197:
        raise ExecutionAbortedPreResult("SEED_MISMATCH")
    selected = universe["SELECTED_BY_MONDAY"]
    for monday, names in selected.items():
        if len(names) != 82:
            raise ExecutionAbortedPreResult(f"D13_WEEK_N_MISMATCH:{monday}:{len(names)}")
    return {
        "SNAPSHOT_ID": snap,
        "FILE_LEDGER_DIGEST": ledger_digest,
        "UNIVERSE_IDENTITY_DIGEST": universe["UNIVERSE_IDENTITY_DIGEST"],
        "EXCLUSION_LIST_DIGEST": exclusions["EXCLUSION_LIST_DIGEST"],
        "N": 82,
        "WEEK_N": len(selected),
        "SELECTED_BY_MONDAY": selected,
        "ELIGIBLE_COUNT_BY_MONDAY": universe.get("ELIGIBLE_COUNT_BY_MONDAY"),
        "PINNED_TAKER_FEE": 0.001,
        "FRICTION_FLOOR": 0.004,
        "RUNTIME_FILE_AUTHORITY": "SNAPSHOT_BOUND_OBJECT_LEDGER",
    }


def verify_d13_raw_bytes(repo: Path) -> dict[str, Any]:
    try:
        return P.verify_local_bytes_against_ledger(repo=repo)
    except C.MissingLocalData:
        RESTORE.restore(repo=repo)
        return P.verify_local_bytes_against_ledger(repo=repo)


def identity_gate(repo: Path, *, verify_raw_bytes: bool = True) -> dict[str, Any]:
    if C.EXECUTION_AUTHORIZED:
        raise ExecutionAbortedPreResult("GLOBAL_EXECUTION_AUTHORIZED_MUST_REMAIN_FALSE")
    verify_execution_root(repo)
    freeze = load_json(repo, FREEZE_REL)
    permit = load_json(repo, PERMIT_REL)
    verify_permit_bindings(repo, freeze, permit)
    hashes = verify_implementation_hashes(repo, freeze)
    d12_id = D12.verify_core_identity(repo=repo)
    d13_id = verify_d13_frozen_identity(repo, freeze)
    bytes_id = {"IDENTITY_OK": True, "SKIPPED": True}
    if verify_raw_bytes:
        bytes_id = verify_d13_raw_bytes(repo)
    if not d12_id.get("IDENTITY_OK") or not bytes_id.get("IDENTITY_OK"):
        raise ExecutionAbortedPreResult("IDENTITY_OK_FALSE")
    return {
        "IMPLEMENTATION_HASHES": hashes,
        "PERMIT": {k: permit[k] for k in permit if k != "IMPLEMENTATION_HASHES"},
        "D12_DATA_IDENTITY": {
            "DATASET_ID": d12_id["DATASET_ID"],
            "SNAPSHOT_ID": d12_id["SNAPSHOT_ID"],
            "MONTH_N": d12_id["MONTH_N"],
            "QUOTE_VOLUME_FIELD": d12_id["QUOTE_VOLUME_FIELD"],
            "DATA_IDENTITY_MODE": d12_id["DATA_IDENTITY_MODE"],
        },
        "D13_DATA_IDENTITY": {
            k: v for k, v in d13_id.items() if k != "SELECTED_BY_MONDAY"
        },
        "D13_SELECTED_BY_MONDAY": d13_id["SELECTED_BY_MONDAY"],
        "IDENTITY_OK": True,
    }


def load_hourly_by_complete_day(*, repo: Path) -> tuple[dict[date, bool], dict[date, np.ndarray]]:
    checksums = D12.btc_legal_parquet_checksums(repo)
    root = repo / C.CORE_BTC_ROOT_REL
    present: dict[int, float] = {}
    for period in C.LEGAL_MONTHS_CORE:
        path = root / "canonical" / "1m" / "monthly" / f"{period}.parquet"
        C.assert_openable(path)
        raw = path.read_bytes()
        if C.sha256_bytes(raw) != checksums[period]:
            raise C.SnapshotIdentityError(f"CORE_BTC_CHECKSUM_MISMATCH:{period}")
        table = pq.read_table(path, columns=["open_time_ms", "quote_volume"])
        opens = table.column("open_time_ms").to_pylist()
        quotes = table.column("quote_volume").to_pylist()
        for open_ms, quote in zip(opens, quotes):
            ts = int(open_ms)
            if ts >= C.PROTECTED_START_MS:
                raise C.ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{period}:{ts}")
            if ts < C.LEGAL_START_MS:
                continue
            vol = C.parse_decimal_string(quote, field="quote_volume")
            if ts in present and present[ts] != vol:
                raise C.Sprint04IntegrityError(f"D12_DUPLICATE_CONFLICT:{ts}")
            present[ts] = vol
    flags: dict[date, bool] = {}
    hourly: dict[date, np.ndarray] = {}
    day = date(2020, 1, 1)
    while day <= C.LEGAL_END_INCLUSIVE:
        start = C.date_to_ms(day)
        hours = np.zeros(C.HOURS_PER_DAY, dtype=np.float64)
        complete = True
        volume = 0.0
        for k in range(C.MINUTE_BARS_PER_DAY):
            ts = start + k * C.BAR_1M_MS
            if ts not in present:
                complete = False
                break
            vol = present[ts]
            hours[k // C.BARS_PER_HOUR] += vol
            volume += vol
        ok = bool(complete and math.isfinite(volume) and volume > 0.0)
        flags[day] = ok
        if ok:
            hourly[day] = hours
        day += timedelta(days=1)
    return flags, hourly


def _window_profiles(
    sunday: date,
    flags: Mapping[date, bool],
    hourly: Mapping[date, np.ndarray],
) -> tuple[np.ndarray, np.ndarray] | None:
    before, after = D12.assert_weekday_matched_windows(sunday)
    b_days = [d for d in before if flags.get(d, False)]
    a_days = [d for d in after if flags.get(d, False)]
    if not (D12.window_eligible(len(b_days)) and D12.window_eligible(len(a_days))):
        return None
    p_before = D12.mean_profile([hourly[d] for d in b_days])
    p_after = D12.mean_profile([hourly[d] for d in a_days])
    return p_before, p_after


def _a_or_none(p_after: np.ndarray, p_before: np.ndarray, delta: int) -> float | None:
    try:
        return D12.clock_anchoring_index(p_after, p_before, delta)
    except C.Sprint04IntegrityError as exc:
        if "D12_D0_ZERO_INELIGIBLE" in str(exc):
            return None
        raise


def assemble_d12(repo: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    flags, hourly = load_hourly_by_complete_day(repo=repo)
    census = D12.census_complete_days(flags)
    if int(census["US_TRANSITIONS_FEASIBLE"]) != 10:
        raise ExecutionAbortedPreResult(f"D12_US_FEASIBLE:{census['US_TRANSITIONS_FEASIBLE']}")
    if int(census["PSEUDO_SUNDAY_N"]) != 239:
        raise ExecutionAbortedPreResult(f"D12_PSEUDO_N:{census['PSEUDO_SUNDAY_N']}")
    us = C.us_transition_dates()
    eu = C.eu_transition_dates()
    us_rows: list[dict[str, Any]] = []
    us_a: list[float] = []
    us_delta: list[int] = []
    us_years: list[int] = []
    for sunday in us:
        profiles = _window_profiles(sunday, flags, hourly)
        delta = C.predicted_delta(sunday, kind="US")
        a_val = None if profiles is None else _a_or_none(profiles[1], profiles[0], delta)
        row = {
            "sunday": sunday.isoformat(),
            "year": sunday.year,
            "delta": delta,
            "eligible": a_val is not None,
            "A": a_val,
        }
        us_rows.append(row)
        if a_val is not None:
            us_a.append(float(a_val))
            us_delta.append(int(delta))
            us_years.append(int(sunday.year))
    eu_rows: list[dict[str, Any]] = []
    eu_a: list[float] = []
    for sunday in eu:
        profiles = _window_profiles(sunday, flags, hourly)
        delta = C.predicted_delta(sunday, kind="EU")
        a_val = None if profiles is None else _a_or_none(profiles[1], profiles[0], delta)
        eu_rows.append(
            {
                "sunday": sunday.isoformat(),
                "year": sunday.year,
                "delta": delta,
                "eligible": a_val is not None,
                "A": a_val,
            }
        )
        if a_val is not None:
            eu_a.append(float(a_val))
    plus_pool: list[float] = []
    minus_pool: list[float] = []
    for sunday in D12.pseudo_sundays(us, eu):
        profiles = _window_profiles(sunday, flags, hourly)
        if profiles is None:
            continue
        a_plus = _a_or_none(profiles[1], profiles[0], 1)
        a_minus = _a_or_none(profiles[1], profiles[0], -1)
        if a_plus is not None:
            plus_pool.append(float(a_plus))
        if a_minus is not None:
            minus_pool.append(float(a_minus))
    support_pass = (
        len(us_a) >= C.D12_MIN_US_ELIGIBLE
        and int(census["PSEUDO_SUNDAY_N"]) >= C.D12_MIN_PSEUDO_SUNDAYS
        and bool(census["SUPPORT_PASS"])
    )
    summary = D12.evaluate_d12_scientific(
        us_a,
        us_delta,
        us_years,
        plus_pool,
        minus_pool,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": support_pass},
    )
    return {
        "CENSUS": {
            "US_TRANSITIONS_TOTAL": census["US_TRANSITIONS_TOTAL"],
            "US_TRANSITIONS_FEASIBLE": census["US_TRANSITIONS_FEASIBLE"],
            "EU_TRANSITIONS_TOTAL": census["EU_TRANSITIONS_TOTAL"],
            "EU_TRANSITIONS_FEASIBLE": census["EU_TRANSITIONS_FEASIBLE"],
            "PSEUDO_SUNDAY_N": census["PSEUDO_SUNDAY_N"],
            "COMPLETE_DAY_N": census["COMPLETE_DAY_N"],
            "SUPPORT_PASS": census["SUPPORT_PASS"],
        },
        "EVALUATION": summary,
        "A_BY_US_TRANSITION": us_rows,
        "A_BY_EU_TRANSITION": eu_rows,
        "US_A": us_a,
        "EU_A": eu_a,
        "PLUS_POOL_N": len(plus_pool),
        "MINUS_POOL_N": len(minus_pool),
        "DATA_IDENTITY": identity["D12_DATA_IDENTITY"],
    }


def load_close_panel_from_ledger(*, repo: Path, symbols: set[str]) -> dict[str, dict[int, float]]:
    raw_root = repo / C.D13_RAW_REL
    panel: dict[str, dict[int, float]] = {}
    for key in P.scientific_file_keys(repo=repo):
        match = ACQ.OBJECT_RE.match(key)
        if not match:
            raise C.Sprint04IntegrityError(f"D13_BAD_OBJECT_KEY:{key}")
        symbol = match.group(1)
        if symbol not in symbols:
            continue
        path = raw_root / key
        C.assert_openable(path)
        if not path.is_file():
            raise C.MissingLocalData(f"D13_MISSING_ZIP:{key}")
        with zipfile.ZipFile(path) as zf:
            text = zf.read(zf.namelist()[0]).decode("utf-8")
        closes = P.parse_scientific_closes(text)
        bucket = panel.setdefault(symbol, {})
        for ts, px in closes.items():
            if ts in bucket and bucket[ts] != px:
                raise C.Sprint04IntegrityError(f"D13_DUPLICATE_CLOSE:{symbol}:{ts}")
            bucket[ts] = px
    return panel


def assemble_d13(repo: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    selected_by_monday: dict[str, list[str]] = identity["D13_SELECTED_BY_MONDAY"]
    symbols = {name for names in selected_by_monday.values() for name in names}
    panel = load_close_panel_from_ledger(repo=repo, symbols=symbols)
    mondays = D13.decision_mondays()
    weekly_ic: list[float] = []
    weekly_years: list[int] = []
    weekly_raw_spreads: list[float] = []
    no_post = 0
    for monday in mondays:
        t_ms = C.date_to_ms(monday)
        D13.refuse_protected_year_timestamp(t_ms)
        selected = selected_by_monday[monday.isoformat()]
        if len(selected) != 82:
            raise ExecutionAbortedPreResult(f"D13_SELECTED_N:{monday}:{len(selected)}")
        formation: list[float] = []
        holding: list[float] = []
        for symbol in selected:
            closes = panel.get(symbol) or {}
            entry_open = t_ms - C.DAY_MS
            form_open = t_ms - C.D13_FORMATION_DAYS * C.DAY_MS - C.DAY_MS
            if entry_open not in closes or form_open not in closes:
                raise ExecutionAbortedPreResult(f"D13_MISSING_FORMATION_CLOSE:{symbol}:{monday}")
            mark = terminal_mark(symbol, t_ms, closes)
            if mark.status == NO_POST_T_CLOSE:
                no_post += 1
                continue
            formation.append(D13.formation_return(closes[entry_open], closes[form_open]))
            holding.append(D13.holding_return_for_symbol(symbol, t_ms, closes))
        if no_post > 0:
            raise ExecutionAbortedPreResult(f"D13_NO_POST_RUNTIME:{no_post}:{monday}")
        weekly_ic.append(D13.spearman_rank_ic(formation, holding))
        weekly_raw_spreads.append(D13.top_minus_bottom_spread(formation, holding))
        weekly_years.append(monday.year)
    if len(weekly_ic) != len(mondays):
        raise ExecutionAbortedPreResult(f"D13_WEEK_IC_N:{len(weekly_ic)}:{len(mondays)}")
    support = {
        "IDENTITY_OK": True,
        "SUPPORT_PASS": True,
        "TERMINAL_MARK_AUTHORITY_FROZEN": False,
    }
    summary = D13.evaluate_d13_scientific(
        weekly_ic,
        weekly_years,
        weekly_raw_spreads,
        support=support,
        n=82,
        no_post_t_close_selected_n=0,
        pinned_taker_fee=0.001,
    )
    ics = np.asarray(weekly_ic, dtype=np.float64)
    return {
        "EVALUATION": summary,
        "WEEKLY_IC": weekly_ic,
        "WEEKLY_YEARS": weekly_years,
        "WEEKLY_RAW_SPREADS": weekly_raw_spreads,
        "WEEKLY_IC_SUMMARY": {
            "N": int(ics.size),
            "MEAN": float(ics.mean()),
            "MIN": float(ics.min()),
            "MAX": float(ics.max()),
            "STD": float(ics.std(ddof=0)),
        },
        "ELIGIBLE_COUNT_BY_MONDAY": identity["D13_DATA_IDENTITY"].get("ELIGIBLE_COUNT_BY_MONDAY"),
        "DATA_IDENTITY": identity["D13_DATA_IDENTITY"],
        "NO_POST_T_CLOSE_SELECTED_N": 0,
        "UNION_SELECTED_N": len(symbols),
    }


def _common_result_fields(*, hashes: Mapping[str, str], permit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "UNIT": UNIT,
        "KIND": "CANONICAL_SCIENTIFIC_EXECUTION",
        "EXECUTION_ROOT": EXECUTION_ROOT,
        "EXPECTED_TREE": EXPECTED_TREE,
        "IMPLEMENTATION_HASHES": dict(hashes),
        "PERMIT_REL": PERMIT_REL,
        "IMPLEMENTATION_FREEZE_SHA256": permit["IMPLEMENTATION_FREEZE_SHA256"],
        "ONE_SHOT_RUNNER_SHA256": permit["ONE_SHOT_RUNNER_SHA256"],
        "PERMIT_SHA256": permit["PERMIT_SHA256"],
        "EVIDENCE_LABEL": "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA",
        "NOT_PROVEN_ALPHA": True,
        "NOT_VALIDATED_TRADING_EDGE": True,
        "NOT_PRODUCTION_SIGNAL": True,
        "NOT_CONFIRMED_MECHANISM": True,
        "NOT_CAUSAL_PROOF": True,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "D7_RERUN_PERFORMED": False,
        "D8_EXECUTED": False,
        "D7_CONFIRMATION_EXECUTED": False,
        "D11_CONFIRMATION_EXECUTED": False,
        "MARKET_07_CREATED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
        "POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED": True,
        "AUTOMATIC_SPRINT05": False,
    }


def build_d12_result(assembled: Mapping[str, Any], hashes: Mapping[str, str], permit: Mapping[str, Any]) -> dict[str, Any]:
    ev = assembled["EVALUATION"]
    eu_a = assembled["EU_A"]
    payload = {
        **_common_result_fields(hashes=hashes, permit=permit),
        "DISCOVERY_ID": "D12",
        "NAME": "PARTICIPATION_CLOCK_ANCHORING_DST_NATURAL_EXPERIMENT",
        "D12_EXECUTED": True,
        "CLASSIFICATION": ev["CLASSIFICATION"],
        "IDENTITY_OK": ev["IDENTITY_OK"],
        "SUPPORT_PASS": ev["SUPPORT_PASS"],
        "DATA_IDENTITY": assembled["DATA_IDENTITY"],
        "RANDOM_SEED": C.D12_RANDOM_SEED,
        "N_RANDOMIZATIONS": C.D12_N_RANDOMIZATIONS,
        "US_TRANSITION_N": len(assembled["US_A"]),
        "US_TRANSITIONS_TOTAL": assembled["CENSUS"]["US_TRANSITIONS_TOTAL"],
        "PSEUDO_SUNDAY_N": assembled["CENSUS"]["PSEUDO_SUNDAY_N"],
        "A_BY_US_TRANSITION": assembled["A_BY_US_TRANSITION"],
        "MEAN_A": ev.get("MEAN_A"),
        "MC_P": ev.get("MC_P"),
        "STATISTICAL_GATE": ev["STATISTICAL_GATE"],
        "PRACTICAL_GATE": ev["PRACTICAL_GATE"],
        "TEMPORAL_GATE": ev["TEMPORAL_GATE"],
        "YEARLY_MEAN_A": ev.get("YEARLY_MEAN_A"),
        "EU_DIAGNOSTIC": {
            "A_BY_TRANSITION": assembled["A_BY_EU_TRANSITION"],
            "MEAN_A": float(np.mean(eu_a)) if eu_a else None,
            "N": len(eu_a),
        },
        "EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION": False,
        "ALLOWED_CLAIM": (
            "whether BTC Binance 2020-2024 intraday quote-volume timing exhibits "
            "the frozen US-clock anchoring pattern"
        ),
        "FORBIDDEN_CLAIMS": [
            "specific participant identity",
            "ETF/institution causality",
            "equity-session causality",
            "directional prediction",
            "trading alpha",
            "volatility claim",
            "D11 rescue/reinterpretation",
        ],
        "LIMITATIONS": [
            "Adaptive discovery on historically exposed 2020-2024 CORE BTC.",
            "EU transitions are secondary diagnostic only and cannot change classification.",
            "Not a participant-identity, equity-session, directional, or trading claim.",
        ],
    }
    payload["RESULT_PAYLOAD_SHA256"] = payload_sha256(payload)
    return payload


def build_d13_result(assembled: Mapping[str, Any], hashes: Mapping[str, str], permit: Mapping[str, Any]) -> dict[str, Any]:
    ev = assembled["EVALUATION"]
    payload = {
        **_common_result_fields(hashes=hashes, permit=permit),
        "DISCOVERY_ID": "D13",
        "NAME": "CROSS_SECTIONAL_WEEKLY_RELATIVE_RETURN_STRUCTURE",
        "D13_EXECUTED": True,
        "CLASSIFICATION": ev["CLASSIFICATION"],
        "IDENTITY_OK": ev["IDENTITY_OK"],
        "SUPPORT_PASS": ev["SUPPORT_PASS"],
        "DATA_IDENTITY": assembled["DATA_IDENTITY"],
        "RUNTIME_FILE_AUTHORITY": "SNAPSHOT_BOUND_OBJECT_LEDGER",
        "RANDOM_SEED": C.D13_RANDOM_SEED,
        "N_RANDOMIZATIONS": C.D13_N_RANDOMIZATIONS,
        "N": 82,
        "WEEK_N": ev.get("WEEK_N"),
        "MEAN_WEEKLY_IC": ev.get("POOLED_MEAN_IC"),
        "POOLED_IC_SIGN": ev.get("POOLED_IC_SIGN"),
        "STRUCTURE_LABEL": ev.get("STRUCTURE_LABEL"),
        "MC_P": ev.get("MC_P"),
        "STATISTICAL_GATE": ev["STATISTICAL_GATE"],
        "SIGNED_TOP_BOTTOM_SPREAD": ev.get("SIGNED_SPREAD"),
        "MEAN_RAW_Q5_MINUS_Q1": ev.get("MEAN_RAW_Q5_MINUS_Q1"),
        "FRICTION_FLOOR": ev.get("FRICTION_FLOOR"),
        "PINNED_TAKER_FEE": ev.get("PINNED_TAKER_FEE"),
        "PRACTICAL_GATE": ev["PRACTICAL_GATE"],
        "YEARLY_MEAN_IC": ev.get("YEARLY_MEAN_IC"),
        "TEMPORAL_GATE": ev["TEMPORAL_GATE"],
        "NO_POST_T_CLOSE_SELECTED_N": assembled["NO_POST_T_CLOSE_SELECTED_N"],
        "WEEKLY_IC_SUMMARY": assembled["WEEKLY_IC_SUMMARY"],
        "ELIGIBLE_COUNT_BY_MONDAY": assembled.get("ELIGIBLE_COUNT_BY_MONDAY"),
        "TEMPORAL_DEPENDENCE_LIMITATION": C.D13_TEMPORAL_DEPENDENCE_LIMITATION,
        "ALLOWED_CLAIM": (
            "whether the frozen liquid Binance spot USDT panel exhibits 1-week "
            "cross-sectional relative-return structure, and its observed sign"
        ),
        "FORBIDDEN_CLAIMS": [
            "tradable strategy",
            "profitability",
            "net alpha",
            "factor/risk-premium interpretation",
            "BTC direction",
            "other horizons",
            "other venues",
        ],
        "LIMITATIONS": [
            C.D13_TEMPORAL_DEPENDENCE_LIMITATION,
            "Adaptive discovery on historically exposed 2020-2024 Binance spot USDT panel.",
            "Not a tradable strategy, net-of-cost profitability, or factor interpretation.",
        ],
    }
    payload["RESULT_PAYLOAD_SHA256"] = payload_sha256(payload)
    return payload


def render_card_md(result: Mapping[str, Any]) -> str:
    disc = result["DISCOVERY_ID"]
    lines = [
        f"# Discovery Sprint 04 {disc} RESULT",
        "",
        f"**Classification:** `{result['CLASSIFICATION']}`",
        f"**Execution root:** `{result['EXECUTION_ROOT']}`",
        f"**RESULT_PAYLOAD_SHA256:** `{result['RESULT_PAYLOAD_SHA256']}`",
        "",
        "Adaptive discovery on historically exposed data. Not proven alpha, "
        "not a trading edge, not a confirmed mechanism, not causal proof.",
        "",
        "```",
        f"CLASSIFICATION = {result['CLASSIFICATION']}",
        f"IDENTITY_OK = {result['IDENTITY_OK']}",
        f"SUPPORT_PASS = {result['SUPPORT_PASS']}",
        f"STATISTICAL_GATE = {result['STATISTICAL_GATE']}",
        f"PRACTICAL_GATE = {result['PRACTICAL_GATE']}",
        f"TEMPORAL_GATE = {result['TEMPORAL_GATE']}",
        f"PROTECTED_2025_OPENED = {result['PROTECTED_2025_OPENED']}",
        f"PROTECTED_2026_OPENED = {result['PROTECTED_2026_OPENED']}",
        "```",
        "",
    ]
    if disc == "D12":
        lines.extend(
            [
                f"US_TRANSITION_N = {result['US_TRANSITION_N']}",
                f"PSEUDO_SUNDAY_N = {result['PSEUDO_SUNDAY_N']}",
                f"MEAN_A = {result['MEAN_A']}",
                f"MC_P = {result['MC_P']}",
                f"YEARLY_MEAN_A = {result['YEARLY_MEAN_A']}",
                f"EU_DIAGNOSTIC_MEAN_A = {result['EU_DIAGNOSTIC']['MEAN_A']}",
                "EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION = false",
                "",
                "Allowed claim: US-clock anchoring of BTC Binance 2020-2024 quote-volume timing.",
                "Forbidden: participant identity, ETF/equity causality, direction, trading alpha, "
                "volatility, D11 rescue.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"N = {result['N']}",
                f"WEEK_N = {result['WEEK_N']}",
                f"MEAN_WEEKLY_IC = {result['MEAN_WEEKLY_IC']}",
                f"POOLED_IC_SIGN = {result['POOLED_IC_SIGN']}",
                f"MC_P = {result['MC_P']}",
                f"SIGNED_TOP_BOTTOM_SPREAD = {result['SIGNED_TOP_BOTTOM_SPREAD']}",
                f"FRICTION_FLOOR = {result['FRICTION_FLOOR']}",
                f"YEARLY_MEAN_IC = {result['YEARLY_MEAN_IC']}",
                f"NO_POST_T_CLOSE_SELECTED_N = {result['NO_POST_T_CLOSE_SELECTED_N']}",
                "",
                result["TEMPORAL_DEPENDENCE_LIMITATION"],
                "",
                "Allowed claim: 1-week cross-sectional relative-return structure and its observed sign.",
                "Forbidden: tradable strategy, profitability, net alpha, factor interpretation, "
                "BTC direction, other horizons/venues.",
                "",
            ]
        )
    return "\n".join(lines)


def write_result(repo: Path, rel_json: str, rel_md: str, payload: Mapping[str, Any]) -> None:
    json_path = repo / rel_json
    md_path = repo / rel_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in payload.items() if k != "_MARKDOWN"}
    json_path.write_text(canonical_json(body), encoding="utf-8")
    if "DISCOVERY_ID" in body:
        md_path.write_text(render_card_md(body), encoding="utf-8")
    else:
        md_path.write_text(str(payload.get("_MARKDOWN") or ""), encoding="utf-8")


def execute(*, repo: Path, authorize: bool, write: bool) -> dict[str, Any]:
    if not authorize:
        raise C.RealScientificOutcomeForbidden("SPRINT04_EXECUTION_NOT_AUTHORIZED")
    identity = identity_gate(repo, verify_raw_bytes=True)
    d12_a = assemble_d12(repo, identity)
    d13_a = assemble_d13(repo, identity)
    permit = load_json(repo, PERMIT_REL)
    hashes = identity["IMPLEMENTATION_HASHES"]
    d12_r = build_d12_result(d12_a, hashes, permit)
    d13_r = build_d13_result(d13_a, hashes, permit)
    promising = sum(
        1 for row in (d12_r, d13_r) if row["CLASSIFICATION"] == "PROMISING_PROTOTYPE"
    )
    executed = 10
    batch = {
        **_common_result_fields(hashes=hashes, permit=permit),
        "D12_EXECUTED": True,
        "D13_EXECUTED": True,
        "D12_CLASSIFICATION": d12_r["CLASSIFICATION"],
        "D13_CLASSIFICATION": d13_r["CLASSIFICATION"],
        "D12_RESULT_PAYLOAD_SHA256": d12_r["RESULT_PAYLOAD_SHA256"],
        "D13_RESULT_PAYLOAD_SHA256": d13_r["RESULT_PAYLOAD_SHA256"],
        "INTERNAL_DISCOVERY_CARDS_EXECUTED": executed,
        "INTERNAL_PROMISING_PROTOTYPES": 3 + promising,
        "NEXT_UNIT": "POST_SPRINT04_AUTOMATION_MATURITY_DECISION",
    }
    batch["RESULT_PAYLOAD_SHA256"] = payload_sha256(batch)
    batch["_MARKDOWN"] = "\n".join(
        [
            "# Discovery Sprint 04 canonical RESULT",
            "",
            f"EXECUTION_ROOT = `{EXECUTION_ROOT}`",
            f"D12_CLASSIFICATION = `{d12_r['CLASSIFICATION']}`",
            f"D13_CLASSIFICATION = `{d13_r['CLASSIFICATION']}`",
            f"INTERNAL_DISCOVERY_CARDS_EXECUTED = {executed}",
            f"INTERNAL_PROMISING_PROTOTYPES = {3 + promising}",
            f"SPRINT04_RESULT_PAYLOAD_SHA256 = `{batch['RESULT_PAYLOAD_SHA256']}`",
            "",
            "Adaptive discovery only. Not proven alpha. No automatic Sprint 05.",
            "NEXT_UNIT = POST_SPRINT04_AUTOMATION_MATURITY_DECISION",
            "",
        ]
    )
    if write:
        write_result(repo, *RESULT_REL["D12"], d12_r)
        write_result(repo, *RESULT_REL["D13"], d13_r)
        md = batch.pop("_MARKDOWN")
        write_result(repo, *RESULT_REL["BATCH"], {**batch, "_MARKDOWN": md})
        batch["_MARKDOWN"] = md
    return {"D12": d12_r, "D13": d13_r, "BATCH": batch}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument(AUTHORIZE_FLAG, dest="authorize", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--identity-only", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo or C.repo_root()
    try:
        if args.identity_only:
            identity = identity_gate(repo, verify_raw_bytes=True)
            print(
                json.dumps(
                    {
                        "IMPLEMENTATION_IDENTITY_VERIFIED": True,
                        "D12_SNAPSHOT_ID": identity["D12_DATA_IDENTITY"]["SNAPSHOT_ID"],
                        "D13_SNAPSHOT_ID": identity["D13_DATA_IDENTITY"]["SNAPSHOT_ID"],
                        "D13_N": identity["D13_DATA_IDENTITY"]["N"],
                    },
                    indent=2,
                )
            )
            return 0
        out = execute(repo=repo, authorize=args.authorize, write=args.write)
        summary = {
            "D12_CLASSIFICATION": out["D12"]["CLASSIFICATION"],
            "D13_CLASSIFICATION": out["D13"]["CLASSIFICATION"],
            "D12_RESULT_PAYLOAD_SHA256": out["D12"]["RESULT_PAYLOAD_SHA256"],
            "D13_RESULT_PAYLOAD_SHA256": out["D13"]["RESULT_PAYLOAD_SHA256"],
            "BATCH_RESULT_PAYLOAD_SHA256": out["BATCH"]["RESULT_PAYLOAD_SHA256"],
        }
        print(canonical_json(summary))
        return 0
    except ExecutionAbortedPreResult as exc:
        print("EXECUTION_ABORTED_PRE_RESULT")
        print(f"REASON = {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
