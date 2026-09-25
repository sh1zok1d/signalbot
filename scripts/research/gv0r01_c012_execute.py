"""One-shot executor for the frozen GV0R01-C012 contract.

``preflight`` reads calendars and the contract only. It does not open a
price file. ``execute`` is the single outcome-opening entry point.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research import gv0r01_c012_design as DESIGN
from scripts.research.discovery_sprint_03 import common as C

REPO = Path(__file__).resolve().parents[2]
CONTRACT = DESIGN.DESIGN_JSON
OUT_DIR = REPO / "docs/research"
PREFLIGHT_JSON = OUT_DIR / "GV0R01_C012_PREFLIGHT.json"
PRIMARY_JSON = OUT_DIR / "GV0R01_C012_PRIMARY_RESULT.json"
RESULT_JSON = OUT_DIR / "GV0R01_C012_EXECUTION_RESULT.json"
BTC_ROOT = REPO / C.CORE_BTC_ROOT_REL

DESIGN_HEAD = "0af0ce5aaff9a98b9584c4f9a7a3af2294fe6c9b"
DESIGN_TREE = "e86f5545276b7a608d95981f6f63557ff3fc6339"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(e: dict) -> str:
    return f"{e['YEAR']}:{e['WEEKDAY']}:{e['UTC_HOUR']}"


def _windows_overlap(a0: str, a1: str, b0: str, b1: str) -> bool:
    return a0 < b1 and b0 < a1


def control_candidates(events: list[dict]) -> dict[str, list[int]]:
    """Eligible control window-end timestamps. Same rule as the frozen census.

    A candidate date is the same year and weekday, is not a release date, and
    the 24h window lies inside 2020-01-01..2025-01-01. The endpoint minute
    matches the event window end in that cell. No prices are read.
    """
    release_days = {e["RELEASE_UTC"][:10] for e in events}
    by_cell: dict[str, list[dict]] = {}
    for e in events:
        by_cell.setdefault(_cell(e), []).append(e)
    out: dict[str, list[int]] = {}
    for cell, group in by_cell.items():
        ends = {e["WINDOW_END_UTC"][11:19] for e in group}
        if len(ends) != 1:
            raise RuntimeError(f"CELL_CLOCK_NOT_UNIQUE:{cell}")
        hh, mm, ss = (int(x) for x in ends.pop().split(":"))
        year, weekday, _hour = (int(x) for x in cell.split(":"))
        ids = []
        day = dt.date(year, 1, 1)
        while day.year == year:
            if day.weekday() == weekday and day.isoformat() not in release_days:
                end = dt.datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=dt.timezone.utc)
                start = end - dt.timedelta(hours=24)
                if start >= dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc) and end < dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc):
                    ids.append(int(end.timestamp()))
            day += dt.timedelta(days=1)
        out[cell] = sorted(set(ids))
    return out


def assign_controls(events: list[dict]) -> dict:
    by_cell: dict[str, list[int]] = {}
    for e in events:
        by_cell.setdefault(_cell(e), []).append(int(DESIGN.parse_utc(e["WINDOW_END_UTC"]).timestamp()))
    candidates = control_candidates(events)
    matched, balanced = C.sample_matched_ids_per_cell(by_cell, candidates, seed=DESIGN.MATCH_SEED)
    pairs = []
    for cell in sorted(by_cell):
        ev = sorted((e for e in events if _cell(e) == cell), key=lambda e: e["EVENT_ID"])
        chosen = matched.get(cell) or []
        if len(ev) != len(chosen):
            raise RuntimeError(f"UNMATCHED_CELL:{cell}")
        for e, cid in zip(ev, chosen):
            end = dt.datetime.fromtimestamp(cid, tz=dt.timezone.utc)
            start = end - dt.timedelta(hours=24)
            pairs.append({
                "EVENT_ID": e["EVENT_ID"],
                "CELL": cell,
                "EVENT_WINDOW_START_UTC": e["WINDOW_START_UTC"],
                "EVENT_WINDOW_END_UTC": e["WINDOW_END_UTC"],
                "CONTROL_WINDOW_END_UTC": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "CONTROL_WINDOW_START_UTC": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "LONG_GAP": e["LONG_GAP"],
                "FAMILY": e["FAMILY"],
                "YEAR": e["YEAR"],
            })
    return {"BALANCED": balanced, "PAIRS": pairs}


def _overlap_count(rows: list[tuple[str, str]]) -> int:
    n = 0
    rows = sorted(rows)
    for i, (a0, a1) in enumerate(rows):
        for b0, b1 in rows[i + 1:]:
            if b0 >= a1:
                break
            if _windows_overlap(a0, a1, b0, b1):
                n += 1
    return n


def topology(pairs: list[dict], event_pairs: list[list[str]]) -> dict:
    controls = [p["CONTROL_WINDOW_END_UTC"] for p in pairs]
    reuse = len(controls) - len(set(controls))
    ev = [(p["EVENT_WINDOW_START_UTC"], p["EVENT_WINDOW_END_UTC"]) for p in pairs]
    ct = [(p["CONTROL_WINDOW_START_UTC"], p["CONTROL_WINDOW_END_UTC"]) for p in pairs]
    cross = 0
    for a0, a1 in ev:
        for b0, b1 in ct:
            if _windows_overlap(a0, a1, b0, b1):
                cross += 1
    within = {}
    for cell in sorted({p["CELL"] for p in pairs}):
        ends = sorted(int(DESIGN.parse_utc(p["CONTROL_WINDOW_END_UTC"]).timestamp()) for p in pairs if p["CELL"] == cell)
        ends += sorted(int(DESIGN.parse_utc(p["EVENT_WINDOW_END_UTC"]).timestamp()) for p in pairs if p["CELL"] == cell)
        ends = sorted(set(ends))
        gaps = [b - a for a, b in zip(ends, ends[1:])]
        within[cell] = min(gaps) if gaps else None
    min_gap = min(v for v in within.values() if v is not None)
    return {
        "EVENTS_WITH_CONTROL": len(pairs),
        "UNMATCHED_EVENTS": 0,
        "UNIQUE_CONTROL_WINDOWS": len(set(controls)),
        "CONTROL_REUSE_COUNT": reuse,
        "MAX_CONTROL_REUSE": max(__import__("collections").Counter(controls).values()),
        "EVENT_EVENT_WINDOW_OVERLAPS": len(event_pairs),
        "CONTROL_CONTROL_WINDOW_OVERLAPS": _overlap_count(ct),
        "EVENT_CONTROL_WINDOW_OVERLAPS": cross,
        "MIN_WITHIN_STRATUM_ENDPOINT_GAP_SECONDS": min_gap,
        "EXCHANGEABILITY": (
            "PASS_WITHIN_STRATUM"
            if reuse == 0 and min_gap >= 6 * 24 * 3600
            else "FAIL"
        ),
        "CROSS_STRATUM_OVERLAPS_NOTE": (
            "Event-event overlaps are the two frozen pairs. Control-control and event-control "
            "overlaps are across strata. The frozen test permutes labels only inside a stratum, "
            "where endpoints are at least 7 days apart, so those overlaps do not break the "
            "exchangeability the permutation uses. They are not dropped."
        ),
    }


def preflight() -> dict:
    if DESIGN.validate_written():
        raise RuntimeError("CONTRACT_DRIFT")
    doc = json.loads(CONTRACT.read_text())
    if doc["UNIVERSE_SUMMARY"]["EVENT_N"] != 99:
        raise RuntimeError("EVENT_N")
    if any(e["RELEASE_UTC"] >= "2025-01-01" for e in doc["EVENTS"]):
        raise RuntimeError("PROTECTED_EVENT")
    power = DESIGN.power_report(DESIGN.build_universe())
    if abs(power["SCENARIOS"][-1]["MDE_STANDARDIZED"] - 0.40865320412771755) > 1e-12:
        raise RuntimeError("MDE_DRIFT")
    assigned = assign_controls(doc["EVENTS"])
    if not assigned["BALANCED"] or len(assigned["PAIRS"]) != 99:
        raise RuntimeError("ASSIGNMENT")
    top = topology(assigned["PAIRS"], doc["UNIVERSE_SUMMARY"]["OVERLAP_PAIRS"])
    status = "PASS" if top["EXCHANGEABILITY"] == "PASS_WITHIN_STRATUM" else "DESIGN_INVALID"
    report = {
        "UNIT": "GV0R01_C012_ONE_SHOT_EXECUTION_PREFLIGHT",
        "PREFLIGHT_STATUS": status,
        "MARKET_DATA_OPENED": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "DESIGN_HEAD": DESIGN_HEAD,
        "DESIGN_TREE": DESIGN_TREE,
        "CONTRACT_SHA256": _sha(CONTRACT),
        "POWER_SHA256": _sha(DESIGN.POWER_JSON),
        "CPI_DATASET_DIGEST": DESIGN.DATASET_DIGEST,
        "FOMC_PIN_SHA256": _sha(DESIGN.FOMC_PIN),
        "EVENT_N": 99,
        "CONTROL_ASSIGNMENT_DETERMINISTIC": True,
        "MATCH_SEED": DESIGN.MATCH_SEED,
        "TOPOLOGY": top,
        "POWER_REPRODUCED": True,
        "POWER_STANDARDIZATION_DEFINITION": (
            "MDE_STANDARDIZED = (z_0.975 + z_0.80) / sqrt(n_eff) is the detectable size of a mean "
            "of n_eff observations, in units of the SD of those observations. "
            "0.82/1.63/2.45 percent = that MDE times an assumed SD of an individual 24h log return. "
            "It is not the SD of a paired difference. Variance inflation is already inside n_eff=47."
        ),
        "SIGN_STABILITY_POWER_SCOPE": (
            "F2 is required for PROMISING_PROTOTYPE and was not power-calibrated. "
            "TARGET_POWER=0.80 applies only to the primary two-sided mean test."
        ),
        "PAIRS": assigned["PAIRS"],
    }
    if status != "PASS":
        raise RuntimeError(f"PRE_OUTCOME_STATUS=DESIGN_INVALID:{top}")
    return report


def write_preflight() -> dict:
    report = preflight()
    PREFLIGHT_JSON.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def _bar_open_ms(close_ts: dt.datetime) -> int:
    """Open time of the 1m bar that closes at close_ts."""
    return int((close_ts - dt.timedelta(minutes=1)).timestamp() * 1000)


def _window_opens(start_iso: str, end_iso: str) -> list[int]:
    end = DESIGN.parse_utc(end_iso)
    start = DESIGN.parse_utc(start_iso)
    first_close = start + dt.timedelta(minutes=1)
    opens = []
    t = first_close
    while t <= end:
        opens.append(_bar_open_ms(t))
        t += dt.timedelta(minutes=1)
    return opens


def load_btc_closes() -> tuple[dict[int, float], dict]:
    """Legal 2020-2024 1m closes only. Refuses any open_time at or after 2025-01-01."""
    checksums = C.btc_legal_parquet_checksums(REPO)
    log = C.OpenedFileLog()
    by_open: dict[int, float] = {}
    rows = 0
    for period in C.LEGAL_MONTHS:
        if not period.startswith(("2020", "2021", "2022", "2023", "2024")):
            raise RuntimeError(f"ILLEGAL_PERIOD:{period}")
        path = C.legal_monthly_parquet_path(BTC_ROOT, period)
        raw = path.read_bytes()
        if C.sha256_bytes(raw) != checksums[period]:
            raise C.SnapshotIdentityError(f"BTC_CHECKSUM:{period}")
        log.record(path, repo_root=REPO)
        for open_ms, close_px in C._read_1m_closes(path):
            if open_ms >= C.PROTECTED_START_MS:
                raise C.ProtectedYearRefused(f"PROTECTED:{open_ms}")
            if open_ms in by_open and by_open[open_ms] != close_px:
                raise RuntimeError(f"DUP:{open_ms}")
            by_open[open_ms] = close_px
            rows += 1
    identity = {
        "DATASET_ID": C.CORE_BTC_DATASET_ID,
        "SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "ROOT": C.CORE_BTC_ROOT_REL,
        "RESOLUTION": "1m",
        "COVERAGE": "2020-01..2024-12",
        "ROW_COUNT": rows,
        "MONTH_SHA256": {p: checksums[p] for p in C.LEGAL_MONTHS},
        "CONTENT_DIGEST": hashlib.sha256("".join(checksums[p] for p in C.LEGAL_MONTHS).encode()).hexdigest(),
        "TIMESTAMP_CONVENTION": "open_time_ms is the bar open. The bar closes 60s later. A window uses bars whose close time is inside (WINDOW_START, WINDOW_END].",
        "FILES_OPENED": log.files,
    }
    return by_open, identity


def window_return(closes: dict[int, float], start_iso: str, end_iso: str) -> float | None:
    opens = _window_opens(start_iso, end_iso)
    if len(opens) != 24 * 60:
        raise RuntimeError("WINDOW_BAR_COUNT")
    if any(o not in closes or not math.isfinite(closes[o]) or closes[o] <= 0 for o in opens):
        return None
    if any(o >= C.PROTECTED_START_MS for o in opens):
        raise C.ProtectedYearRefused("WINDOW_CROSSES_PROTECTED")
    return math.log(closes[opens[-1]] / closes[opens[0]])


def _mean_diff(ev: np.ndarray, ct: np.ndarray) -> float:
    return float(np.mean(ev) - np.mean(ct))


def _permute(event_by_cell, control_by_cell, observed: float) -> tuple[float, float]:
    p = C.stratified_label_permutation_p(
        event_by_cell, control_by_cell, observed=observed, statistic=_mean_diff,
        seed=DESIGN.PERMUTATION_SEED, n=DESIGN.PERMUTATIONS, alternative="two-sided-abs",
    )
    rng = np.random.default_rng(DESIGN.PERMUTATION_SEED)
    stats = []
    strata = []
    for cell in sorted(set(event_by_cell) | set(control_by_cell)):
        ev = np.asarray(event_by_cell[cell], dtype=np.float64)
        ct = np.asarray(control_by_cell[cell], dtype=np.float64)
        strata.append((ev, ct))
    for _ in range(DESIGN.PERMUTATIONS):
        fake_e, fake_c = [], []
        for ev, ct in strata:
            pooled = np.concatenate([ev, ct])
            rng.shuffle(pooled)
            fake_e.append(pooled[: ev.size])
            fake_c.append(pooled[ev.size:])
        stats.append(_mean_diff(np.concatenate(fake_e), np.concatenate(fake_c)))
    sd = float(np.std(stats, ddof=1))
    return p, sd


def _classify(support: bool, f1: bool, f2: bool, f3: bool) -> str:
    if not support:
        return "INCONCLUSIVE_DISCOVERY"
    if (not f1) and (not f2) and (not f3):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def execute(preflight_head: str, preflight_tree: str) -> dict:
    report = json.loads(PREFLIGHT_JSON.read_text())
    if report["PREFLIGHT_STATUS"] != "PASS" or report["MARKET_DATA_OPENED"] is not False:
        raise RuntimeError("PREFLIGHT_NOT_CLEAN")
    closes, identity = load_btc_closes()
    pairs = report["PAIRS"]
    used = []
    missing = []
    for p in pairs:
        er = window_return(closes, p["EVENT_WINDOW_START_UTC"], p["EVENT_WINDOW_END_UTC"])
        cr = window_return(closes, p["CONTROL_WINDOW_START_UTC"], p["CONTROL_WINDOW_END_UTC"])
        row = dict(p)
        row["EVENT_RET"] = er
        row["CONTROL_RET"] = cr
        if er is None or cr is None:
            missing.append(row)
        else:
            used.append(row)
    dropped_rate = len(missing) / len(pairs)
    by_year: dict[int, int] = {}
    for r in used:
        by_year[r["YEAR"]] = by_year.get(r["YEAR"], 0) + 1
    support = dropped_rate <= DESIGN.MAX_MISSING_EVENT_RATE and all(by_year.get(y, 0) >= DESIGN.MIN_EVENTS_PER_YEAR for y in range(2020, 2025))
    ev_cells: dict[str, list[float]] = {}
    ct_cells: dict[str, list[float]] = {}
    for r in used:
        ev_cells.setdefault(r["CELL"], []).append(r["EVENT_RET"])
        ct_cells.setdefault(r["CELL"], []).append(r["CONTROL_RET"])
    ev = np.array([r["EVENT_RET"] for r in used])
    ct = np.array([r["CONTROL_RET"] for r in used])
    delta = float(np.mean(ev) - np.mean(ct)) if len(used) else float("nan")
    p_value, null_sd = _permute(ev_cells, ct_cells, delta) if support else (float("nan"), float("nan"))
    z = 1.959963984540054
    ci = [delta - z * null_sd, delta + z * null_sd] if support else [None, None]
    yearly = {}
    for y in range(2020, 2025):
        ye = [r["EVENT_RET"] for r in used if r["YEAR"] == y]
        yc = [r["CONTROL_RET"] for r in used if r["YEAR"] == y]
        yearly[str(y)] = float(np.mean(ye) - np.mean(yc)) if ye else None
    signs = [v for v in yearly.values() if v is not None and v != 0]
    agree = sum(1 for v in signs if (v > 0) == (delta > 0))
    f1 = not (p_value <= DESIGN.ALPHA)
    f2 = agree < DESIGN.MIN_YEARS_SHARING_SIGN
    f3, placebo = _falsifier3(closes, used, delta)
    classification = _classify(support, f1, f2, f3)
    primary = {
        "EXECUTION_IDENTITY": "GV0R01_C012_ONE_SHOT",
        "DESIGN_HEAD": DESIGN_HEAD,
        "DESIGN_TREE": DESIGN_TREE,
        "PREFLIGHT_HEAD": preflight_head,
        "PREFLIGHT_TREE": preflight_tree,
        "CONTRACT_SHA256": report["CONTRACT_SHA256"],
        "CPI_DATASET_DIGEST": DESIGN.DATASET_DIGEST,
        "FOMC_PIN_SHA256": report["FOMC_PIN_SHA256"],
        "MARKET_DATA_IDENTITY": identity,
        "MARKET_DATA_OPENED": True,
        "MARKET_OUTCOMES_COMPUTED": True,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "EVENTS_PLANNED": 99,
        "EVENTS_USED": len(used),
        "CONTROLS_USED": len(used),
        "MISSING_EVENT_COUNT": len(missing),
        "MISSING_EVENT_IDS": [r["EVENT_ID"] for r in missing],
        "PRIMARY_ENDPOINT": "DELTA_24",
        "DELTA_24": delta,
        "PRIMARY_P_VALUE": p_value,
        "PRIMARY_INTERVAL": ci,
        "PRIMARY_DIRECTION": "POSITIVE" if delta > 0 else "NEGATIVE" if delta < 0 else "ZERO",
        "YEARLY_DELTA": yearly,
        "PERMUTATION_SEED": DESIGN.PERMUTATION_SEED,
        "PERMUTATIONS": DESIGN.PERMUTATIONS,
        "SUPPORT_PASS": support,
        "FALSIFIER_FIRED": {"F1_PERMUTATION": f1, "F2_TEMPORAL": f2, "F3_PRIOR_WINDOW": f3},
        "F2_YEARS_SHARING_SIGN": agree,
        "PLACEBO_DELTA": placebo.get("DELTA"),
        "PLACEBO_P_VALUE": placebo.get("P"),
        "F3_EVENTS_WITHOUT_CALIPER_CONTROL": placebo.get("WITHOUT_CALIPER"),
        "CLASSIFICATION": classification,
        "USED_EVENT_IDS": [r["EVENT_ID"] for r in used],
    }
    PRIMARY_JSON.write_text(json.dumps(primary, indent=1, sort_keys=True) + "\n")
    return primary


def _falsifier3(closes, used, delta: float) -> tuple[bool, dict]:
    ev_cells: dict[str, list[float]] = {}
    ct_cells: dict[str, list[float]] = {}
    ok = 0
    for r in used:
        es = DESIGN.parse_utc(r["EVENT_WINDOW_START_UTC"]) - dt.timedelta(hours=24)
        ee = DESIGN.parse_utc(r["EVENT_WINDOW_START_UTC"])
        cs = DESIGN.parse_utc(r["CONTROL_WINDOW_START_UTC"]) - dt.timedelta(hours=24)
        ce = DESIGN.parse_utc(r["CONTROL_WINDOW_START_UTC"])
        er = window_return(closes, es.strftime("%Y-%m-%dT%H:%M:%SZ"), ee.strftime("%Y-%m-%dT%H:%M:%SZ"))
        cr = window_return(closes, cs.strftime("%Y-%m-%dT%H:%M:%SZ"), ce.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if er is None or cr is None:
            continue
        ok += 1
        ev_cells.setdefault(r["CELL"], []).append(er)
        ct_cells.setdefault(r["CELL"], []).append(cr)
    if ok < 2:
        return True, {"DELTA": None, "P": None, "WITHOUT_CALIPER": None}
    ev = np.concatenate([np.asarray(v) for v in ev_cells.values()])
    ct = np.concatenate([np.asarray(v) for v in ct_cells.values()])
    pdelta = float(np.mean(ev) - np.mean(ct))
    p_value, _sd = _permute(ev_cells, ct_cells, pdelta)
    same_dir = (pdelta > 0) == (delta > 0) and p_value <= DESIGN.ALPHA
    without = _caliper_failures(closes, used)
    fired = bool(same_dir or without > len(used) / 2)
    return fired, {"DELTA": pdelta, "P": p_value, "WITHOUT_CALIPER": without}


def _caliper_failures(closes, used) -> int:
    """Events with no unused-calendar control inside the 0.25 prior-return caliper.

    The candidate list is the frozen calendar list, not a new match.
    """
    doc = json.loads(CONTRACT.read_text())
    candidates = control_candidates(doc["EVENTS"])
    fails = 0
    for r in used:
        es = DESIGN.parse_utc(r["EVENT_WINDOW_START_UTC"]) - dt.timedelta(hours=24)
        ee = DESIGN.parse_utc(r["EVENT_WINDOW_START_UTC"])
        er = window_return(closes, es.strftime("%Y-%m-%dT%H:%M:%SZ"), ee.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if er is None:
            fails += 1
            continue
        hit = False
        for cid in candidates[r["CELL"]]:
            end = dt.datetime.fromtimestamp(cid, tz=dt.timezone.utc)
            start = end - dt.timedelta(hours=24)
            prior_end = start
            prior_start = start - dt.timedelta(hours=24)
            cr = window_return(closes, prior_start.strftime("%Y-%m-%dT%H:%M:%SZ"), prior_end.strftime("%Y-%m-%dT%H:%M:%SZ"))
            if cr is not None and abs(cr - er) <= DESIGN.PLACEBO_CALIPER_LOG:
                hit = True
                break
        if not hit:
            fails += 1
    return fails
