"""Outcome-blind design and synthetic power for GV0R01-C020.

No BTC price or quote-volume values are read. Session bounds come from the
card and the statutory DST calendar, not from a volume profile.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
NYSE_DIR = REPO / "docs/research_data/NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"
OPM_DIR = REPO / "docs/research_data/US_OPM_FEDERAL_HOLIDAY_LIST_V0"
CN_DIR = REPO / "docs/research_data/CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0"
DST_PATH = REPO / "docs/research/DISCOVERY_SPRINT_04.json"
OUT_JSON = REPO / "docs/research/GV0R01_C020_OUTCOME_BLIND_DESIGN.json"
OUT_MD = REPO / "docs/research/GV0R01_C020_OUTCOME_BLIND_DESIGN.md"

EXPECTED_DIGESTS = {
    "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0": "45201d104e52b0ff3544920c5b6cd614c73ced7cdda3784512b06a6ea61b297c",
    "US_OPM_FEDERAL_HOLIDAY_LIST_V0": "e2402e00ecc68bbac23c74f83126b007cf825b2dc78eff22af7ebc175a522f68",
    "CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0": "4223719d57f314105093a582aede44e9526f3cff2bdcf59aacac4c1db240d3d1",
}

# Frozen before power. The card states no numeric magnitude. The endpoint is a
# log share ratio, so the bar is a 10 percent relative reduction of the US-session
# share versus matched controls: log(0.90).
EXECUTION_MDE_THRESHOLD = math.log(0.90)
EXECUTION_MDE_UNITS = "LOG_US_SESSION_SHARE_DISPLACEMENT"
TARGET_POWER = 0.80
ALPHA = 0.05
CONTROL_WINDOW_WEEKS = 2
NULL_DRAWS = 1000
POWER_REPS = 200
POWER_SEED = 20020
NULL_SEED = 20021
BASE_LOG_VOLUME_SD = 0.25
STRESS_LOG_VOLUME_SD = 0.50
LEGAL_FIRST = dt.date(2020, 1, 1)
LEGAL_LAST = dt.date(2024, 12, 31)
UNRESOLVED_OPM_DATE = "2021-06-18"
# Uniform-clock base share: NYSE regular session is 6.5 hours of the 24h UTC day.
# This is clock arithmetic, not a BTC volume profile.
BASE_SESSION_HOURS = 6.5
BASE_DAY_HOURS = 24.0

CLAIM = (
    "Official regional holidays remove the corresponding participant block, "
    "which displaces the BTCUSDT perpetual intraday volume profile away from "
    "that region's session. The lead contrast is the mean log US-session share "
    "displacement on NYSE weekday closures versus matched same-weekday non-holiday days."
)


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text())


def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def parse_date(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def dst_transitions() -> dict[int, tuple[dt.date, dt.date]]:
    sprint = load_json(DST_PATH)
    raw = sprint["CARDS"]["D12"]["DATASET_OR_SOURCE_AUTHORITY"]["US_TRANSITION_DAYS"]
    out = {}
    for year, pair in raw.items():
        spring, fall = parse_date(pair[0]), parse_date(pair[1])
        out[int(year)] = (spring, fall)
    return out


def utc_offset_hours(day: dt.date, transitions: dict[int, tuple[dt.date, dt.date]]) -> int:
    """Hours to add to UTC to get America/New_York civil time. -4 EDT, -5 EST.

    Spring-forward Sunday is EDT at 09:30. Fall-back Sunday is EST at 09:30.
    """
    spring, fall = transitions[day.year]
    if spring <= day < fall:
        return -4
    return -5


def us_session_utc(day: dt.date, transitions: dict[int, tuple[dt.date, dt.date]]) -> tuple[str, str]:
    """Half-open NYSE regular session [09:30, 16:00) local, as UTC timestamps."""
    offset = utc_offset_hours(day, transitions)
    start_local_min = 9 * 60 + 30
    end_local_min = 16 * 60
    start_utc_min = start_local_min - offset * 60
    end_utc_min = end_local_min - offset * 60
    def fmt(minutes: int) -> str:
        return f"{day.isoformat()}T{minutes // 60:02d}:{minutes % 60:02d}:00Z"
    return fmt(start_utc_min), fmt(end_utc_min)


def holiday_inputs():
    digests = {}
    for folder, key in (
        (NYSE_DIR, "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"),
        (OPM_DIR, "US_OPM_FEDERAL_HOLIDAY_LIST_V0"),
        (CN_DIR, "CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0"),
    ):
        manifest = load_json(folder / "MANIFEST.json")
        digest = manifest["CANONICAL_DATASET_DIGEST"]
        if digest != EXPECTED_DIGESTS[key]:
            raise SystemExit(f"digest mismatch {key}")
        digests[key] = digest
    nyse = load_json(NYSE_DIR / "EVENTS.json")
    opm = load_json(OPM_DIR / "EVENTS.json")
    cn = load_json(CN_DIR / "EVENTS.json")
    return digests, nyse, opm, cn


def build_calendar():
    digests, nyse, opm, cn = holiday_inputs()
    transitions = dst_transitions()
    full = [
        row for row in nyse
        if row["EVENT_TYPE"] == "FULL_DAY_CLOSURE"
        and row["POINT_IN_TIME_STATUS"] == "VERIFIED_PREANNOUNCED"
        and row["PRIMARY_FOR_LEAD_ARM"] is True
        and 2020 <= row["YEAR"] <= 2024
    ]
    full.sort(key=lambda row: row["EVENT_DATE"])
    if len(full) != 47:
        raise SystemExit(f"expected 47 primary closures, got {len(full)}")
    unresolved_nyse = [
        row for row in nyse
        if 2020 <= row["YEAR"] <= 2024 and row["POINT_IN_TIME_STATUS"] != "VERIFIED_PREANNOUNCED"
    ]
    early = {row["EVENT_DATE"] for row in nyse if row["EVENT_TYPE"] == "EARLY_CLOSE" and 2020 <= row["YEAR"] <= 2024}
    closure_dates = {row["EVENT_DATE"] for row in full}
    if any(row["EVENT_TYPE"] == "FULL_DAY_CLOSURE" and row["EVENT_DATE"] for row in unresolved_nyse):
        raise SystemExit("unresolved row entered the closure type")
    cn_nonworking = {row["EVENT_DATE"] for row in cn if row["EVENT_TYPE"] == "NON_WORKING"}
    cn_work = {row["EVENT_DATE"] for row in cn if row["EVENT_TYPE"] == "COMPENSATING_WORKING"}
    if cn_nonworking & cn_work:
        raise SystemExit("China non-working overlaps compensating work")
    opm_block = set()
    opm_open_candidates = []
    for row in opm:
        if row["GEOGRAPHIC_SCOPE"] != "NATIONWIDE":
            continue
        if row["OBSERVED_DATE"] == UNRESOLVED_OPM_DATE or row["POINT_IN_TIME_STATUS"] != "VERIFIED_PREANNOUNCED":
            continue
        opm_block.add(row["OBSERVED_DATE"])
        if row["OBSERVED_DATE"] not in closure_dates and row["OBSERVED_DATE"] not in early:
            observed = parse_date(row["OBSERVED_DATE"])
            if observed.weekday() < 5 and LEGAL_FIRST <= observed <= LEGAL_LAST:
                opm_open_candidates.append(row)
    # OPM dates stay out of this set. Their role is the specificity falsifier, not a control exclusion.
    contaminated = closure_dates | early | cn_nonworking | cn_work
    holiday_weeks = set()
    for iso in closure_dates:
        day = parse_date(iso)
        monday = day - dt.timedelta(days=day.weekday())
        for offset in range(7):
            holiday_weeks.add(monday + dt.timedelta(days=offset))

    def eligible_control(day: dt.date) -> bool:
        iso = day.isoformat()
        if not (LEGAL_FIRST <= day <= LEGAL_LAST):
            return False
        return iso not in contaminated

    pairs = []
    for row in full:
        event_day = parse_date(row["EVENT_DATE"])
        controls = []
        for step in (-2, -1, 1, 2):
            cand = event_day + dt.timedelta(days=7 * step)
            if eligible_control(cand):
                controls.append(cand.isoformat())
        start_utc, end_utc = us_session_utc(event_day, transitions)
        pairs.append({
            "EVENT_ID": row["EVENT_ID"],
            "EVENT_DATE": row["EVENT_DATE"],
            "OFFICIAL_LABEL": row["OFFICIAL_LABEL"],
            "YEAR": row["YEAR"],
            "WEEKDAY": event_day.strftime("%A"),
            "US_SESSION_UTC_START": start_utc,
            "US_SESSION_UTC_END": end_utc,
            "CONTROL_DATES": controls,
            "COVERED": len(controls) > 0,
        })
    covered = [pair for pair in pairs if pair["COVERED"]]
    control_uses: dict[str, int] = {}
    for pair in covered:
        for control in pair["CONTROL_DATES"]:
            control_uses[control] = control_uses.get(control, 0) + 1
    reused = sorted(day for day, count in control_uses.items() if count > 1)

    # Event-event edge if control sets intersect or UTC days are within 14 days.
    edges = []
    for i, left in enumerate(covered):
        left_controls = set(left["CONTROL_DATES"])
        left_day = parse_date(left["EVENT_DATE"])
        for right in covered[i + 1:]:
            right_day = parse_date(right["EVENT_DATE"])
            share = left_controls & set(right["CONTROL_DATES"])
            close = abs((left_day - right_day).days) <= 14
            if share or close:
                edges.append({
                    "LEFT": left["EVENT_ID"],
                    "RIGHT": right["EVENT_ID"],
                    "SHARED_CONTROLS": sorted(share),
                    "WITHIN_14_DAYS": close,
                })
    parent = {pair["EVENT_ID"]: pair["EVENT_ID"] for pair in covered}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for edge in edges:
        a, b = find(edge["LEFT"]), find(edge["RIGHT"])
        if a != b:
            parent[b] = a
    components: dict[str, list[str]] = {}
    for pair in covered:
        components.setdefault(find(pair["EVENT_ID"]), []).append(pair["EVENT_ID"])
    component_sizes = sorted((len(members) for members in components.values()), reverse=True)

    # Exact pseudo-holiday support within YEAR x WEEKDAY, outside holiday weeks.
    strata: dict[tuple[int, int], dict] = {}
    for pair in covered:
        day = parse_date(pair["EVENT_DATE"])
        key = (day.year, day.weekday())
        strata.setdefault(key, {"EVENTS": [], "POOL": []})
        strata[key]["EVENTS"].append(pair["EVENT_DATE"])
    for day in daterange(LEGAL_FIRST, LEGAL_LAST):
        if day in holiday_weeks or not eligible_control(day):
            continue
        key = (day.year, day.weekday())
        if key not in strata:
            continue
        if not any(eligible_control(day + dt.timedelta(days=7 * step)) for step in (-2, -1, 1, 2)):
            continue
        strata[key]["POOL"].append(day.isoformat())
    support = 1
    stratum_rows = []
    for key in sorted(strata):
        year, weekday = key
        k = len(strata[key]["EVENTS"])
        pool = len(strata[key]["POOL"])
        ways = math.comb(pool, k) if pool >= k else 0
        support *= ways
        stratum_rows.append({
            "YEAR": year,
            "WEEKDAY": weekday,
            "EVENT_COUNT": k,
            "PSEUDO_POOL": pool,
            "COMBINATIONS": ways,
        })
    if support <= 1:
        raise SystemExit("pseudo-holiday support collapsed")
    # The observed closures sit inside holiday weeks, so they are not members of the pseudo set.
    min_p = 1.0 / support
    alpha_attainable = min_p <= ALPHA

    f3_events = []
    for row in sorted(opm_open_candidates, key=lambda item: item["OBSERVED_DATE"]):
        day = parse_date(row["OBSERVED_DATE"])
        controls = []
        for step in (-2, -1, 1, 2):
            cand = day + dt.timedelta(days=7 * step)
            if eligible_control(cand) and cand.isoformat() not in closure_dates and cand.isoformat() not in opm_block:
                controls.append(cand.isoformat())
        if controls:
            f3_events.append({
                "OBSERVED_DATE": row["OBSERVED_DATE"],
                "OFFICIAL_LABEL": row["OFFICIAL_LABEL"],
                "NOMINAL_DATE": row["NOMINAL_DATE"],
                "CONTROL_DATES": controls,
            })

    return {
        "DIGESTS": digests,
        "PAIRS": pairs,
        "COVERED": covered,
        "EARLY_CLOSE_DATES": sorted(early),
        "UNRESOLVED_NYSE": [
            {"EVENT_ID": row["EVENT_ID"], "EVENT_TYPE": row["EVENT_TYPE"], "EVENT_DATE": row["EVENT_DATE"]}
            for row in unresolved_nyse
        ],
        "CONTROL_USE_COUNTS": control_uses,
        "REUSED_CONTROLS": reused,
        "EDGES": edges,
        "COMPONENT_SIZES": component_sizes,
        "STRATA": stratum_rows,
        "SUPPORT": support,
        "MIN_P": min_p,
        "ALPHA_ATTAINABLE": alpha_attainable,
        "F3_EVENTS": f3_events,
        "CN_NON_WORKING_COUNT": len(cn_nonworking),
        "CN_COMPENSATING_COUNT": len(cn_work),
        "TRANSITIONS": {str(year): [a.isoformat(), b.isoformat()] for year, (a, b) in transitions.items()},
    }


def share_from_volumes(log_us: np.ndarray, log_rest: np.ndarray) -> np.ndarray:
    us = np.exp(log_us)
    rest = np.exp(log_rest)
    return us / (us + rest)


def volume_factor_for_log_share(delta: float) -> float:
    s0 = BASE_SESSION_HOURS / BASE_DAY_HOURS
    s1 = s0 * math.exp(delta)
    if not 0 < s1 < 1:
        raise SystemExit("target share left (0,1)")
    return (s1 / (1.0 - s1)) / (s0 / (1.0 - s0))


def statistic(shares: dict[str, float], pairs: list[dict]) -> float:
    terms = []
    for pair in pairs:
        controls = [shares[day] for day in pair["CONTROL_DATES"]]
        mean_control = float(np.mean(controls))
        if mean_control <= 0 or shares[pair["EVENT_DATE"]] <= 0:
            continue
        terms.append(math.log(shares[pair["EVENT_DATE"]] / mean_control))
    if not terms:
        raise SystemExit("empty statistic")
    return float(np.mean(terms))


def null_p_value(shares: dict[str, float], pairs: list[dict], pools: dict[tuple, list[str]], rng: np.random.Generator) -> float:
    observed = statistic(shares, pairs)
    as_extreme = 0
    for _ in range(NULL_DRAWS):
        pseudo_pairs = []
        used = set()
        for pair in pairs:
            day = parse_date(pair["EVENT_DATE"])
            pool = pools[(day.year, day.weekday())]
            choice = None
            for _try in range(20):
                cand = pool[int(rng.integers(0, len(pool)))]
                if cand not in used:
                    choice = cand
                    break
            if choice is None:
                continue
            used.add(choice)
            event_day = parse_date(choice)
            controls = []
            for step in (-2, -1, 1, 2):
                ctrl = event_day + dt.timedelta(days=7 * step)
                iso = ctrl.isoformat()
                if iso in shares and iso != choice:
                    controls.append(iso)
            if controls:
                pseudo_pairs.append({"EVENT_DATE": choice, "CONTROL_DATES": controls})
        if not pseudo_pairs:
            continue
        draw = statistic(shares, pseudo_pairs)
        if abs(draw) >= abs(observed):
            as_extreme += 1
    return (1.0 + as_extreme) / (1.0 + NULL_DRAWS)


def build_pools(calendar: dict) -> dict[tuple, list[str]]:
    pools = {}
    for row in calendar["STRATA"]:
        # Reconstructed inside power from the same eligibility rule via STRATA pools
        pools[(row["YEAR"], row["WEEKDAY"])] = []
    # The stratum rows do not list dates. Rebuild from calendar pairs' year/weekday
    # by calling the dates stored on covered pairs' pools through a second pass.
    return pools


def simulate_power(calendar: dict) -> dict:
    """Synthetic shares only. The economic bar is already frozen above."""
    covered = calendar["COVERED"]
    transitions = dst_transitions()
    # Rebuild pseudo pools with dates. Holiday weeks and contamination match build_calendar.
    holiday_weeks = set()
    closure_dates = {parse_date(pair["EVENT_DATE"]) for pair in covered}
    for day in closure_dates:
        monday = day - dt.timedelta(days=day.weekday())
        for offset in range(7):
            holiday_weeks.add(monday + dt.timedelta(days=offset))
    needed = set()
    pools: dict[tuple[int, int], list[str]] = {}
    for pair in covered:
        day = parse_date(pair["EVENT_DATE"])
        pools.setdefault((day.year, day.weekday()), [])
        needed.add(pair["EVENT_DATE"])
        needed.update(pair["CONTROL_DATES"])
    # Eligible pseudo dates: same rule as build_calendar, recovered from stratum counts
    # by scanning the legal range against stored closure/control exclusions is repeated
    # here from the calendar object's contaminated logic. We store pool dates below.
    digests, nyse, _opm, cn = holiday_inputs()
    del digests, _opm
    early = {parse_date(row["EVENT_DATE"]) for row in nyse if row["EVENT_TYPE"] == "EARLY_CLOSE"}
    closures = {parse_date(row["EVENT_DATE"]) for row in nyse if row["EVENT_TYPE"] == "FULL_DAY_CLOSURE" and row["PRIMARY_FOR_LEAD_ARM"]}
    cn_bad = {parse_date(row["EVENT_DATE"]) for row in cn if row["EVENT_TYPE"] in {"NON_WORKING", "COMPENSATING_WORKING"}}
    blocked = closures | early | cn_bad
    for day in daterange(LEGAL_FIRST, LEGAL_LAST):
        if day in holiday_weeks or day in blocked:
            continue
        key = (day.year, day.weekday())
        if key not in pools:
            continue
        if not any(
            LEGAL_FIRST <= (day + dt.timedelta(days=7 * step)) <= LEGAL_LAST
            and (day + dt.timedelta(days=7 * step)) not in blocked
            for step in (-2, -1, 1, 2)
        ):
            continue
        pools[key].append(day.isoformat())
        needed.add(day.isoformat())
        for step in (-2, -1, 1, 2):
            ctrl = day + dt.timedelta(days=7 * step)
            if LEGAL_FIRST <= ctrl <= LEGAL_LAST and ctrl not in blocked:
                needed.add(ctrl.isoformat())
    dates = sorted(needed)
    index = {iso: i for i, iso in enumerate(dates)}
    s0 = BASE_SESSION_HOURS / BASE_DAY_HOURS
    log_us_base = math.log(BASE_SESSION_HOURS)
    log_rest_base = math.log(BASE_DAY_HOURS - BASE_SESSION_HOURS)

    control_idx = {}
    for iso in dates:
        day = parse_date(iso)
        ctrls = []
        for step in (-2, -1, 1, 2):
            cand = (day + dt.timedelta(days=7 * step)).isoformat()
            cand_day = parse_date(cand)
            if cand in index and cand != iso and cand_day not in blocked and LEGAL_FIRST <= cand_day <= LEGAL_LAST:
                ctrls.append(index[cand])
        control_idx[iso] = np.asarray(ctrls, dtype=int)
    event_pos = np.asarray([index[pair["EVENT_DATE"]] for pair in covered], dtype=int)
    event_controls = [np.asarray([index[day] for day in pair["CONTROL_DATES"]], dtype=int) for pair in covered]
    pool_pos = {}
    pool_controls = {}
    for key, members in pools.items():
        pool_pos[key] = np.asarray([index[iso] for iso in members], dtype=int)
        pool_controls[key] = [control_idx[iso] for iso in members]
    pair_keys = [(parse_date(pair["EVENT_DATE"]).year, parse_date(pair["EVENT_DATE"]).weekday()) for pair in covered]

    observed_ctrl = np.full((len(covered), 4), -1, dtype=int)
    for i, ctrl in enumerate(event_controls):
        observed_ctrl[i, :len(ctrl)] = ctrl
    null_event_pos = []
    null_ctrl = []
    for key in pair_keys:
        positions = pool_pos[key]
        padded = np.full((len(positions), 4), -1, dtype=int)
        for i, ctrl in enumerate(pool_controls[key]):
            if len(ctrl):
                padded[i, :len(ctrl)] = ctrl
        null_event_pos.append(positions)
        null_ctrl.append(padded)

    def terms_from(log_shares: np.ndarray, events: np.ndarray, padded: np.ndarray) -> float:
        gathered = np.where(padded >= 0, log_shares[np.clip(padded, 0, None)], np.nan)
        mean_share = np.nanmean(np.exp(gathered), axis=1)
        return float(np.mean(log_shares[events] - np.log(mean_share)))

    groups: dict[tuple[int, int], list[int]] = {}
    for event_index, key in enumerate(pair_keys):
        groups.setdefault(key, []).append(event_index)
    padded_by_key = {}
    pos_by_key = {}
    seen = set()
    for key, positions, padded in zip(pair_keys, null_event_pos, null_ctrl):
        if key in seen:
            continue
        seen.add(key)
        pos_by_key[key] = positions
        padded_by_key[key] = padded

    def fast_p(log_shares: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
        observed = terms_from(log_shares, event_pos, observed_ctrl)
        events = np.empty((NULL_DRAWS, len(covered)), dtype=int)
        padded = np.empty((NULL_DRAWS, len(covered), 4), dtype=int)
        for key, member_idx in groups.items():
            positions = pos_by_key[key]
            choice = np.argsort(rng.random((NULL_DRAWS, len(positions))), axis=1)[:, : len(member_idx)]
            events[:, member_idx] = positions[choice]
            padded[:, member_idx, :] = padded_by_key[key][choice]
        valid = padded >= 0
        safe = np.where(valid, np.exp(log_shares[np.clip(padded, 0, None)]), 0.0)
        counts = np.sum(valid, axis=2)
        mean_share = np.divide(safe.sum(axis=2), counts, out=np.full(counts.shape, np.nan), where=counts > 0)
        draw_stats = np.nanmean(log_shares[events] - np.log(mean_share), axis=1)
        as_extreme = int(np.sum(np.abs(draw_stats) >= abs(observed)))
        return observed, (1.0 + as_extreme) / (1.0 + NULL_DRAWS)

    def run_scenario(sigma: float, deltas: list[float], seed: int) -> list[dict]:
        rng = np.random.default_rng(seed)
        rows = []
        n = len(dates)
        for delta in deltas:
            phi = volume_factor_for_log_share(delta) if delta != 0 else 1.0
            rejects = 0
            realized = []
            shift = math.log(phi) if delta != 0 else 0.0
            for _rep in range(POWER_REPS):
                log_us = log_us_base + rng.normal(0.0, sigma, n)
                log_rest = log_rest_base + rng.normal(0.0, sigma, n)
                if shift:
                    log_us[event_pos] += shift
                log_shares = np.log(share_from_volumes(log_us, log_rest))
                stat, p_value = fast_p(log_shares, rng)
                realized.append(stat)
                if p_value <= ALPHA:
                    rejects += 1
            rate = rejects / POWER_REPS
            rows.append({
                "NOISE_FREE_LOG_SHARE_DISPLACEMENT": delta,
                "US_VOLUME_FACTOR": phi,
                "POWER": rate,
                "MEAN_REALIZED_STATISTIC": float(np.mean(realized)),
                "MC_POWER_SE": math.sqrt(rate * (1.0 - rate) / POWER_REPS),
            })
        return rows

    # Grid frozen before looking at the resulting powers. Includes the bar.
    grid = [0.0, -0.05, EXECUTION_MDE_THRESHOLD, -0.15, -0.2231435513142097, -0.30]
    # -0.223... is log(0.80), a wider point on the curve, not the bar.
    base = run_scenario(BASE_LOG_VOLUME_SD, grid, POWER_SEED)
    stress = run_scenario(STRESS_LOG_VOLUME_SD, grid, POWER_SEED + 1)

    def mde_at_target(rows: list[dict]) -> float | None:
        ordered = sorted((row for row in rows if row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] < 0), key=lambda row: row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"], reverse=True)
        prev = None
        for row in ordered:
            if row["POWER"] >= TARGET_POWER:
                if prev is None or prev["POWER"] == row["POWER"]:
                    return row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"]
                span = prev["POWER"] - row["POWER"]
                weight = (TARGET_POWER - row["POWER"]) / span
                return row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] + weight * (
                    prev["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] - row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"]
                )
            prev = row
        return None

    return {
        "BASE_SHARE_IF_VOLUME_UNIFORM_OVER_THE_DAY": s0,
        "BASE": base,
        "STRESS": stress,
        "MDE_BASE": mde_at_target(base),
        "MDE_STRESS": mde_at_target(stress),
        "NULL_REJECTION_BASE": next(row["POWER"] for row in base if row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] == 0.0),
        "NULL_REJECTION_STRESS": next(row["POWER"] for row in stress if row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] == 0.0),
    }


def power_at(rows: list[dict], delta: float) -> dict:
    for row in rows:
        if abs(row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] - delta) < 1e-12:
            return row
    raise SystemExit("missing grid point")


def main() -> dict:
    calendar = build_calendar()
    if not calendar["ALPHA_ATTAINABLE"]:
        gate = "INFERENCE_SUPPORT_INSUFFICIENT"
        power = None
    else:
        power = simulate_power(calendar)
        stress_at_bar = power_at(power["STRESS"], EXECUTION_MDE_THRESHOLD)
        base_at_bar = power_at(power["BASE"], EXECUTION_MDE_THRESHOLD)
        if stress_at_bar["POWER"] >= TARGET_POWER and base_at_bar["POWER"] >= TARGET_POWER:
            gate = "EXECUTION_JUSTIFIED"
        else:
            gate = "EXECUTION_INFORMATIONALLY_WEAK"
    covered = calendar["COVERED"]
    design = {
        "UNIT": "GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER_CONTINUATION",
        "C020_CANONICAL_CLAIM": CLAIM,
        "HOLIDAY_DATASET_DIGESTS": calendar["DIGESTS"],
        "PRIMARY_EVENT_FAMILY": "NYSE_FULL_WEEKDAY_CLOSURE",
        "PLANNED_EVENT_COUNT": len(calendar["PAIRS"]),
        "COVERED_EVENT_COUNT": len(covered),
        "UNRESOLVED_PRIMARY_EVENT_COUNT": 0,
        "PRIMARY_EVENT_IDS": [pair["EVENT_ID"] for pair in covered],
        "PRIMARY_EVENT_DATES": [pair["EVENT_DATE"] for pair in covered],
        "PRIMARY_PAIRS": covered,
        "UNRESOLVED_NYSE_EXCLUDED": calendar["UNRESOLVED_NYSE"],
        "EARLY_CLOSE_DATES_EXCLUDED": calendar["EARLY_CLOSE_DATES"],
        "TRADING_DAY_TIMEZONE": "America/New_York for the session clock; denominator day is UTC",
        "US_SESSION_START_RULE": "09:30 America/New_York inclusive on the closure's calendar date",
        "US_SESSION_END_RULE": "16:00 America/New_York exclusive on the closure's calendar date",
        "DST_RULE": "Energy Policy Act of 2005 as pinned in DISCOVERY_SPRINT_04 CARDS.D12 US_TRANSITION_DAYS. EDT begins on the spring-transition Sunday; EST resumes on the fall-transition Sunday. Both changes are at 02:00 local and do not split the 09:30-16:00 session.",
        "DST_TRANSITIONS": calendar["TRANSITIONS"],
        "OTHER_SESSION_RULES": {
            "ASIA_NON_DECISIVE": "01:00 inclusive to 08:00 exclusive UTC, fixed, China arm only",
            "EU_SESSION": "NOT_REQUIRED_FOR_PRIMARY",
            "ET_0900_1700": "NON_DECISIVE_SEARCH_VARIANT",
        },
        "VOLUME_FIELD": "quote_volume",
        "SHARE_NUMERATOR": "sum of BTCUSDT perpetual 1m quote_volume with open time in [US session start UTC, US session end UTC)",
        "SHARE_DENOMINATOR": "sum of BTCUSDT perpetual 1m quote_volume with open time in [UTC date 00:00, next UTC date 00:00) of the closure date",
        "SHARE_TRANSFORMATION": "log(session_share_event / mean session_share over eligible matched controls)",
        "PRIMARY_ENDPOINT": "mean over covered NYSE full weekday closures of that log ratio",
        "PRIMARY_EFFECT_UNITS": EXECUTION_MDE_UNITS,
        "DAY_BOUNDARY": "UTC calendar date equal to the NYSE closure date. Under the frozen session the 09:30-16:00 New York interval lies wholly inside that UTC date.",
        "ZERO_TOTAL_VOLUME_POLICY": "drop the day; share undefined",
        "MISSING_BAR_POLICY": "a UTC day is usable only if all 1440 minute buckets and the session buckets are present",
        "MISSING_DAY_POLICY": "drop a missing control; drop an event with no remaining control or a missing event day",
        "DUPLICATE_TIMESTAMP_POLICY": "drop the day as malformed",
        "OUTLIER_POLICY": "no winsorization and no outcome-based deletion",
        "COUNTERFACTUAL_DESIGN": "mean of all eligible same-weekday days at ±2 weeks; not a 1:1 draw",
        "CONTROL_WINDOW_WEEKS_PRIMARY": CONTROL_WINDOW_WEEKS,
        "CONTROL_WINDOW_WEEKS_NON_DECISIVE": 4,
        "CONTROL_COUNT_ASSIGNMENTS": sum(len(pair["CONTROL_DATES"]) for pair in covered),
        "UNIQUE_CONTROL_DAYS": len(calendar["CONTROL_USE_COUNTS"]),
        "CONTROL_REUSE_POLICY": "a control day may serve more than one event if both windows contain it; no redraw after market access",
        "CONTROL_REUSE_COUNT": len(calendar["REUSED_CONTROLS"]),
        "REUSED_CONTROL_DATES": calendar["REUSED_CONTROLS"],
        "CONTROL_CONTAMINATION_RULE": "exclude NYSE full closures, NYSE early closes, China non-working dates, and China compensating working dates. Verified OPM dates are not a primary exclusion; they are the F3 sample.",
        "CONTROL_SELECTION_SEED": None,
        "F3_OPM_JUNETEENTH_2021": "excluded from F3 only; not treated as preannounced; does not remove any primary NYSE closure",
        "F3_EVENT_COUNT": len(calendar["F3_EVENTS"]),
        "F3_EVENTS": calendar["F3_EVENTS"],
        "FALSIFIERS": [
            {
                "NAME": "F1_PSEUDO_HOLIDAY_NULL",
                "PURPOSE": "primary test",
                "RULE": "two-sided central 95 percent of the year-by-weekday pseudo-holiday null",
                "VETO_OR_DESCRIPTIVE": "PRIMARY",
                "POWER_CALIBRATED": True,
            },
            {
                "NAME": "F2_YEARLY_SIGN_CONSISTENCY",
                "PURPOSE": "the claim fails if fewer than 3 of 5 yearly signs match the pooled sign",
                "RULE": "veto when the number of years whose mean displacement sign equals the pooled sign is below 3",
                "VETO_OR_DESCRIPTIVE": "VETO",
                "POWER_CALIBRATED": False,
            },
            {
                "NAME": "F3_NYSE_OPEN_FEDERAL_HOLIDAYS",
                "PURPOSE": "specificity: equity-clock anchoring should not produce the same displacement when the NYSE is open",
                "RULE": "veto if the same two-sided pseudo-holiday test on verified nationwide OPM dates with the NYSE open rejects in the same direction as the primary. 2021-06-18 is omitted.",
                "VETO_OR_DESCRIPTIVE": "VETO",
                "POWER_CALIBRATED": False,
            },
        ],
        "CHINA_EXTENSION": "NON_DECISIVE",
        "EARLY_CLOSE_ARM": "NON_DECISIVE",
        "DEPENDENCE_STRUCTURE_TYPE": "event graph linked by shared controls or closure dates within 14 days",
        "DEPENDENCE_GRAPH_NODES": len(covered),
        "DEPENDENCE_GRAPH_EDGES": len(calendar["EDGES"]),
        "DEPENDENCE_GRAPH_COMPONENTS": len(calendar["COMPONENT_SIZES"]),
        "MAX_COMPONENT_SIZE": calendar["COMPONENT_SIZES"][0] if calendar["COMPONENT_SIZES"] else 0,
        "DEPENDENCE_EDGES": calendar["EDGES"],
        "INFERENCE_METHOD": "exact two-sided pseudo-holiday randomization within YEAR x WEEKDAY, outside holiday weeks, recomputing ±2-week controls for each pseudo date",
        "TEST_STATISTIC": "mean log(US_SESSION_SHARE_event / mean US_SESSION_SHARE_controls)",
        "NULL_HYPOTHESIS": "NYSE closure dates are exchangeable with other same-weekday dates in the same year outside holiday weeks and contamination exclusions",
        "ALTERNATIVE_HYPOTHESIS": "the mean log US-session share displacement is not zero. The mechanism predicts a negative sign.",
        "ALPHA": ALPHA,
        "SIDEDNESS": "TWO_SIDED",
        "GLOBAL_INFERENCE_VALIDITY_STATUS": "PASS",
        "RESIDUAL_INFERENCE_ASSUMPTIONS": "Given year and weekday, and after removing the frozen contamination dates, calendar days are exchangeable for the session-share contrast. The local control mean removes a common two-week level. It does not remove a holiday-specific confounder that is not shared by other same-weekday days.",
        "PRIMARY_SUPPORT_SIZE": str(calendar["SUPPORT"]),
        "PRIMARY_LABEL_ORBIT_SIZE": str(calendar["SUPPORT"]),
        "MIN_ATTAINABLE_EXACT_P": calendar["MIN_P"],
        "ALPHA_ATTAINABLE": calendar["ALPHA_ATTAINABLE"],
        "STRATA": calendar["STRATA"],
        "MONTE_CARLO_ESTIMATION_FLOOR": 1.0 / (1.0 + NULL_DRAWS),
        "NULL_DRAWS": NULL_DRAWS,
        "TARGET_POWER": TARGET_POWER,
        "EXECUTION_MDE_THRESHOLD": EXECUTION_MDE_THRESHOLD,
        "EXECUTION_MDE_UNITS": EXECUTION_MDE_UNITS,
        "GATE_AUTHORITY": "stress-scenario power at a noise-free 10 percent relative US-share reduction, frozen before the power run",
        "GATE_RATIONALE": "The card gives no numeric magnitude. The endpoint is a log share ratio, so the bar is log(0.90): the US-session share is 10 percent lower on the closure than on the matched-control mean. This is not a standardized SD and not the C004 or C012 bar.",
        "POWER_SIMULATION_PERFORMED": power is not None,
        "POWER": power,
        "OUTCOME_BLIND_GATE_RESULT": gate,
        "SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING": 0,
        "BTC_PRICE_VALUES_OPENED": False,
        "BTC_VOLUME_VALUES_OPENED": False,
        "MARKET_DATA_OPENED_FOR_C020": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "C020_PRIMARY_TEST_EXECUTED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "C012_C004_OUTCOMES_USED": False,
        "NON_DECISIVE_VARIANTS": ["CONTROL_WINDOW_WEEKS=4", "US_SESSION_DEF=ET_0900_1700", "HOLIDAY_SET=CN_STATUTORY_HOLIDAY_WEEKS"],
    }
    if power is not None:
        design["NULL_REJECTION_RATE"] = power["NULL_REJECTION_BASE"]
        design["POWER_CURVE"] = {"BASE": power["BASE"], "STRESS": power["STRESS"]}
        design["MDE_AT_TARGET_POWER"] = {"BASE": power["MDE_BASE"], "STRESS": power["MDE_STRESS"]}
        design["MONTE_CARLO_UNCERTAINTY"] = "binomial SE at POWER_REPS=200 reported on each grid point"
        design["POWER_SIMULATION_ASSUMPTIONS"] = (
            "Two positive lognormal volumes, US and rest-of-day, with medians 6.5 and 17.5 hours "
            "so the noise-free share equals the uniform-clock share 6.5/24. Event days multiply US "
            "volume by the factor that moves that noise-free share by the grid delta. No BTC volume is used. "
            "Base log-volume SD is 0.25; stress SD is 0.50."
        )
    design["NEXT_UNIT"] = (
        "GV0R01_C020_ONE_SHOT_EXECUTION_PREP"
        if gate == "EXECUTION_JUSTIFIED"
        else "NO_C020_EXECUTION_AUTHORIZED"
    )
    OUT_JSON.write_bytes(canonical_json(design))
    OUT_MD.write_text(render_md(design))
    return design


def render_md(design: dict) -> str:
    power = design.get("POWER") or {}
    return "\n".join([
        "# GV0R01-C020 outcome-blind design",
        "",
        design["C020_CANONICAL_CLAIM"],
        "",
        f"Gate: `{design['OUTCOME_BLIND_GATE_RESULT']}`.",
        f"Covered NYSE full weekday closures: {design['COVERED_EVENT_COUNT']}.",
        f"US session: {design['US_SESSION_START_RULE']} to {design['US_SESSION_END_RULE']}.",
        f"Endpoint: {design['PRIMARY_ENDPOINT']}.",
        f"Alpha attainable: {design['ALPHA_ATTAINABLE']}. Minimum exact p: {design['MIN_ATTAINABLE_EXACT_P']}.",
        f"Execution bar, frozen before power: {design['EXECUTION_MDE_THRESHOLD']} {design['EXECUTION_MDE_UNITS']}.",
        f"Power performed: {design['POWER_SIMULATION_PERFORMED']}.",
        f"MDE at 80 percent: {design.get('MDE_AT_TARGET_POWER')}.",
        f"Null rejection, base: {power.get('NULL_REJECTION_BASE')}.",
        "No BTC price or volume value was opened.",
        "",
    ])


if __name__ == "__main__":
    result = main()
    print(result["OUTCOME_BLIND_GATE_RESULT"], result["COVERED_EVENT_COUNT"], result["MIN_ATTAINABLE_EXACT_P"])
