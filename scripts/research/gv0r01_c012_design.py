"""GV0R01-C012 outcome-blind design and ex-ante power.

Calendar and design only. This module must not open CORE_BTC, compute a
pre-release return, or read a protected 2025/2026 market value.

The primary specification is singular. The other five card variants are a
frozen descriptive grid and cannot change the classification.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CPI_DIR = REPO / "docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"
FOMC_PIN = REPO / "docs/research_data/D11_FOMC_OFFICIAL_V0/PIN.json"
DESIGN_JSON = REPO / "docs/research/GV0R01_C012_OUTCOME_BLIND_DESIGN.json"
POWER_JSON = REPO / "docs/research/GV0R01_C012_POWER.json"

DATASET_DIGEST = "760ed2c5d18b03b7a41c25e6bab157ebde476977fdc3e5f7a3462aa376f4154f"
CPI_DATASET_ID = "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"
FOMC_DATASET_ID = "D11_FOMC_OFFICIAL_V0"
CORE_BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"

PRIMARY_EVENT_SET = "FOMC_AND_CPI"
PRIMARY_WINDOW_H = 24
ALPHA = 0.05
TARGET_POWER = 0.80
PERMUTATIONS = 5000
PERMUTATION_SEED = 12012
MATCH_SEED = 12012
MIN_YEARS_SHARING_SIGN = 3
N_YEARS = 5
LONG_GAP_HOURS = 720.0
# Vol-scaled size of the equity pre-announcement drift (about half a daily
# standard deviation). Not estimated from C012 outcomes.
ECONOMIC_BAR_STANDARDIZED = 0.50
# Conservative dependence: variance inflation of 2 on the week-cluster count.
VARIANCE_INFLATION = 2.0
# Assumed std of a 24h BTC log return. Stated assumptions, not fit to C012.
SIGMA_24H = (0.02, 0.04, 0.06)
PLACEBO_CALIPER_LOG = 0.25
MAX_MISSING_EVENT_RATE = 0.05
MIN_EVENTS_PER_YEAR = 4

CARD_VARIANTS = tuple(
    {"EVENT_SET": es, "PRE_WINDOW_H": w, "ROLE": "PRIMARY" if (es, w) == (PRIMARY_EVENT_SET, PRIMARY_WINDOW_H) else "DESCRIPTIVE_CANNOT_DECIDE"}
    for es in ("FOMC_ONLY", "FOMC_AND_CPI")
    for w in (6, 12, 24)
)

FORBIDDEN_OPEN_MARKERS = (
    "CORE_BTC",
    "load_hourly",
    "parquet",
    "kline",
    "quote_volume",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_utc(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def iso_utc(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def z_quantile(p: float) -> float:
    """Inverse standard-normal CDF (Acklam), deterministic, no scipy."""
    if not 0.0 < p < 1.0:
        raise ValueError(p)
    a = [ -3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00 ]
    b = [ -5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01 ]
    c = [ -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00 ]
    d = [ 7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00 ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def mde_standardized(n_eff: float, alpha: float = ALPHA, power: float = TARGET_POWER) -> float:
    if n_eff <= 0:
        raise ValueError(n_eff)
    return (z_quantile(1 - alpha / 2) + z_quantile(power)) / math.sqrt(n_eff)


def power_at_effect(effect_sigma: float, n_eff: float, alpha: float = ALPHA) -> float:
    """Two-sided normal power for a standardized effect at sample size n_eff."""
    z = z_quantile(1 - alpha / 2)
    ncp = effect_sigma * math.sqrt(n_eff)
    # Approximate the lower tail as negligible for positive effects.
    return _phi(ncp - z) + _phi(-ncp - z)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def window_bounds(release: dt.datetime, hours: int) -> tuple[dt.datetime, dt.datetime]:
    """W-hour window ending one minute before the release. Half-open (start, end]."""
    end = release - dt.timedelta(minutes=1)
    start = end - dt.timedelta(hours=hours)
    return start, end


def load_cpi_events() -> list[dict]:
    manifest = json.loads((CPI_DIR / "MANIFEST.json").read_text())
    if manifest["CANONICAL_DATASET_DIGEST"] != DATASET_DIGEST:
        raise RuntimeError("CPI_DATASET_DIGEST_MISMATCH")
    events = json.loads((CPI_DIR / "EVENTS.json").read_text())["EVENTS"]
    inv = json.loads((CPI_DIR / "OUT_OF_RANGE_INVENTORY.json").read_text())
    if inv.get("CANONICAL") is not False:
        raise RuntimeError("OUT_OF_RANGE_INVENTORY_MUST_STAY_NONCANONICAL")
    return events


def load_fomc_events() -> list[dict]:
    pin = json.loads(FOMC_PIN.read_text())
    if pin.get("STATUS") != "OFFICIAL_SOURCE_PINNED":
        raise RuntimeError("D11_NOT_PINNED")
    if pin.get("PROTECTED_2025_OPENED") or pin.get("PROTECTED_2026_OPENED"):
        raise RuntimeError("D11_PIN_CLAIMS_PROTECTED_OPEN")
    return list(pin["EVENTS"])


def cpi_record(e: dict) -> dict:
    release = parse_utc(e["SCHEDULED_RELEASE_UTC"])
    start, end = window_bounds(release, PRIMARY_WINDOW_H)
    lead = float(e["WINDOW_EVIDENCE"]["W24"]["EVIDENCE_LEAD_HOURS"])
    if e["PROVENANCE_STATUS"] != "VERIFIED_PREANNOUNCED":
        raise RuntimeError(f"CPI_NOT_PREANNOUNCED:{e['EVENT_ID']}")
    if e["SCHEDULED_RELEASE_DATE"] >= "2025-01-01":
        raise RuntimeError(f"CPI_PROTECTED_YEAR:{e['EVENT_ID']}")
    return {
        "EVENT_ID": e["EVENT_ID"],
        "FAMILY": "CPI",
        "RELEASE_UTC": e["SCHEDULED_RELEASE_UTC"],
        "RELEASE_LOCAL": e["SCHEDULED_RELEASE_LOCAL"],
        "LOCAL_ZONE_ABBREV": e["LOCAL_ZONE_ABBREV"],
        "UTC_OFFSET": e["UTC_OFFSET"],
        "YEAR": release.year,
        "WEEKDAY": release.weekday(),
        "UTC_HOUR": release.hour,
        "WINDOW_START_UTC": iso_utc(start),
        "WINDOW_END_UTC": iso_utc(end),
        "PRE_CUTOFF_GAP_HOURS": lead,
        "LONG_GAP": lead > LONG_GAP_HOURS,
        "PROVENANCE_STATUS": e["PROVENANCE_STATUS"],
        "SAFE_FOR_W24": e["SAFE_FOR_W24"],
    }


def fomc_record(e: dict) -> dict:
    release = parse_utc(e["ANNOUNCEMENT_UTC"])
    if release >= dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc):
        raise RuntimeError(f"FOMC_PROTECTED_YEAR:{e['EVENT_ID']}")
    start, end = window_bounds(release, PRIMARY_WINDOW_H)
    return {
        "EVENT_ID": f"FOMC_{e['EVENT_ID']}",
        "FAMILY": "FOMC",
        "RELEASE_UTC": e["ANNOUNCEMENT_UTC"],
        "RELEASE_LOCAL": "14:00",
        "LOCAL_ZONE_ABBREV": e.get("STATED_TIMEZONE"),
        "UTC_OFFSET": "-04:00" if e.get("STATED_TIMEZONE") == "EDT" else "-05:00",
        "YEAR": release.year,
        "WEEKDAY": release.weekday(),
        "UTC_HOUR": release.hour,
        "WINDOW_START_UTC": iso_utc(start),
        "WINDOW_END_UTC": iso_utc(end),
        "PRE_CUTOFF_GAP_HOURS": None,
        "LONG_GAP": False,
        "PROVENANCE_STATUS": "INHERITED_D11_FOMC_OFFICIAL_V0",
        "SOURCE_EVENT_ID": e["EVENT_ID"],
    }


def overlaps(a: dict, b: dict) -> bool:
    return a["WINDOW_START_UTC"] < b["WINDOW_END_UTC"] and b["WINDOW_START_UTC"] < a["WINDOW_END_UTC"]


def build_universe() -> dict:
    cpi = [cpi_record(e) for e in load_cpi_events()]
    fomc = [fomc_record(e) for e in load_fomc_events()]
    events = sorted(cpi + fomc, key=lambda r: (r["RELEASE_UTC"], r["EVENT_ID"]))
    ids = [e["EVENT_ID"] for e in events]
    if len(ids) != len(set(ids)):
        raise RuntimeError("DUPLICATE_EVENT_ID")
    pairs = []
    for i, a in enumerate(events):
        for b in events[i + 1:]:
            if overlaps(a, b):
                pairs.append([a["EVENT_ID"], b["EVENT_ID"]])
    weeks = {parse_utc(e["RELEASE_UTC"]).strftime("%G-W%V") for e in events}
    return {
        "EVENTS": events,
        "CPI_N": len(cpi),
        "FOMC_N": len(fomc),
        "EVENT_N": len(events),
        "OVERLAP_PAIRS": pairs,
        "ISO_WEEK_N": len(weeks),
        "LONG_GAP_CPI_N": sum(1 for e in cpi if e["LONG_GAP"]),
        "CPI_IDS": [e["EVENT_ID"] for e in cpi],
    }


def _cell(e: dict) -> str:
    return f"{e['YEAR']}:{e['WEEKDAY']}:{e['UTC_HOUR']}"


def calendar_control_slots(events: list[dict]) -> dict:
    """Count same-year, same-weekday, same-UTC-hour dates that are not events.

    This is a calendar count. It does not check 1m bar completeness.
    """
    release_days = {e["RELEASE_UTC"][:10] for e in events}
    by_cell: dict[str, list] = {}
    for e in events:
        by_cell.setdefault(_cell(e), []).append(e)
    slots = {}
    for cell, group in sorted(by_cell.items()):
        year, weekday, hour = (int(x) for x in cell.split(":"))
        n = 0
        day = dt.date(year, 1, 1)
        while day.year == year:
            if day.weekday() == weekday and day.isoformat() not in release_days:
                end = dt.datetime(day.year, day.month, day.day, hour, tzinfo=dt.timezone.utc)
                start = end - dt.timedelta(hours=PRIMARY_WINDOW_H)
                if start >= dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc) and end < dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc):
                    n += 1
            day += dt.timedelta(days=1)
        slots[cell] = {"EVENTS": len(group), "CALENDAR_CONTROL_SLOTS": n, "MATCHABLE": n >= len(group)}
    return slots


def power_report(universe: dict) -> dict:
    n_nom = universe["EVENT_N"]
    n_week = universe["ISO_WEEK_N"]
    n_cons = n_week / VARIANCE_INFLATION
    rows = []
    for name, n in (("NOMINAL_EVENTS", n_nom), ("ISO_WEEK_CLUSTERS", n_week), ("VARIANCE_INFLATION_2", n_cons)):
        mde = mde_standardized(n)
        rows.append({
            "SAMPLE": name,
            "N_EFF": n,
            "MDE_STANDARDIZED": mde,
            "MDE_LOG_RETURN_BY_SIGMA": {f"{s:.2f}": mde * s for s in SIGMA_24H},
            "POWER_AT_0.50_SIGMA": power_at_effect(ECONOMIC_BAR_STANDARDIZED, n),
            "POWER_AT_0.25_SIGMA": power_at_effect(0.25, n),
        })
    return {
        "ALPHA": ALPHA,
        "TARGET_POWER": TARGET_POWER,
        "TAIL": "TWO_SIDED",
        "ECONOMIC_BAR_STANDARDIZED": ECONOMIC_BAR_STANDARDIZED,
        "ECONOMIC_BAR_MEANING": "Half of one 24h-return standard deviation, the vol-scaled size of the equity pre-announcement drift. Not fit to C012.",
        "SIGMA_24H_ASSUMPTIONS": list(SIGMA_24H),
        "SIGMA_PROVENANCE": "Stated scenario range for a 24h BTC log-return standard deviation. Not estimated from CORE_BTC and not from any C012 window.",
        "N_PROVENANCE": "Nominal count and ISO-week clusters come from the two calendars only. Variance inflation 2 is a stated dependence stress, not an estimated autocorrelation.",
        "SCENARIOS": rows,
        "PLANNING_SCENARIO": "VARIANCE_INFLATION_2",
    }


def outcome_blind_gate(universe: dict, slots: dict, power: dict) -> dict:
    reasons = []
    if universe["CPI_N"] != 60 or universe["FOMC_N"] != 39:
        reasons.append("EVENT_COUNT")
    if universe["LONG_GAP_CPI_N"] != 11:
        reasons.append("LONG_GAP_COUNT")
    if any(not s["MATCHABLE"] for s in slots.values()):
        reasons.append("CONTROL_SLOTS")
    if not all(e["SAFE_FOR_W24"] for e in universe["EVENTS"] if e["FAMILY"] == "CPI"):
        reasons.append("CPI_NOT_SAFE_W24")
    planning = next(s for s in power["SCENARIOS"] if s["SAMPLE"] == "VARIANCE_INFLATION_2")
    mde = planning["MDE_STANDARDIZED"]
    if reasons:
        state = "DESIGN_INVALID" if "EVENT_COUNT" in reasons or "CPI_NOT_SAFE_W24" in reasons else "BLOCKED_BY_MISSING_INPUT"
    elif mde > ECONOMIC_BAR_STANDARDIZED:
        state = "EXECUTION_INFORMATIONALLY_WEAK"
        reasons.append("CONSERVATIVE_MDE_ABOVE_ECONOMIC_BAR")
    else:
        state = "EXECUTION_JUSTIFIED"
    return {
        "STATE": state,
        "REASONS": reasons,
        "PLANNING_MDE_STANDARDIZED": mde,
        "ECONOMIC_BAR_STANDARDIZED": ECONOMIC_BAR_STANDARDIZED,
        "EXECUTION_AUTHORIZED": False,
        "RULE": (
            "EXECUTION_JUSTIFIED only if the calendar universe, digest and 1:1 control slots "
            "check out AND the two-sided 80% MDE at n = ISO_WEEK_N / 2 is at most 0.50 sigma. "
            "A larger conservative MDE is EXECUTION_INFORMATIONALLY_WEAK. A broken calendar is "
            "DESIGN_INVALID or BLOCKED_BY_MISSING_INPUT. Realized returns cannot change this state."
        ),
    }


def design_document() -> dict:
    universe = build_universe()
    slots = calendar_control_slots(universe["EVENTS"])
    power = power_report(universe)
    gate = outcome_blind_gate(universe, slots, power)
    events_out = []
    for e in universe["EVENTS"]:
        events_out.append({k: e[k] for k in (
            "EVENT_ID", "FAMILY", "RELEASE_UTC", "YEAR", "WEEKDAY", "UTC_HOUR",
            "WINDOW_START_UTC", "WINDOW_END_UTC", "PRE_CUTOFF_GAP_HOURS", "LONG_GAP",
            "PROVENANCE_STATUS", "LOCAL_ZONE_ABBREV",
        )})
    return {
        "UNIT": "GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER",
        "HYPOTHESIS_ID": "GV0R01-C012",
        "TEST_FAMILY_ID": "TF-GV0R01-C012-MT1",
        "STATUS": "PREREGISTRATION_CANDIDATE",
        "EXECUTION_AUTHORIZED": False,
        "MARKET_DATA_OPENED": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "CLAIM": (
            "Anticipation of a scheduled FOMC statement or CPI release produces a signed "
            "drift in the Binance BTCUSDT perpetual log return over the 24 hours ending one "
            "minute before the release, relative to the same year, weekday and UTC hour on "
            "weeks with no such release."
        ),
        "NULL": "After 1:1 matching inside YEAR x WEEKDAY x UTC_HOUR, the mean event-window log return equals the mean control-window log return.",
        "ALTERNATIVE": "The two means differ. Two-sided. The sign is not pre-specified.",
        "PRIMARY_ENDPOINT": "DELTA_24 = mean(PRE_RET_24 on events) - mean(PRE_RET_24 on 1:1 matched controls)",
        "PRIMARY_VARIANT": {"EVENT_SET": PRIMARY_EVENT_SET, "PRE_WINDOW_H": PRIMARY_WINDOW_H},
        "PRIMARY_SELECTION_RULE": (
            "Outcome-free. The event set is the card's named set, FOMC and CPI. "
            "The window is the longest card horizon for which every canonical CPI event is SAFE_FOR_W. "
            "Both facts are calendar facts. The other five card variants are descriptive and cannot decide."
        ),
        "CARD_VARIANTS": list(CARD_VARIANTS),
        "ASSET": {"SYMBOL": "BTCUSDT", "MARKET": "BINANCE_UM_PERPETUAL", "DATASET": CORE_BTC_DATASET_ID, "SNAPSHOT_ID": CORE_BTC_SNAPSHOT_ID, "FIELD": "1m close", "LEGAL_RANGE": "2020-01-01..2024-12-31"},
        "PRE_RET_DEFINITION": "ln(close of the 1m bar that closes at WINDOW_END) - ln(close of the 1m bar that closes at WINDOW_START). WINDOW_END is T-1min. No bar at or after T enters.",
        "AGGREGATION": "Equal weight per event after 1:1 within-stratum matching. Strata are concatenated. Not a trade, not a costed return.",
        "OVERLAP_POLICY": "Overlapping event windows stay in the primary set. They are listed in OVERLAP_PAIRS. The primary permutation does not drop them. A descriptive sensitivity drops the later event of each pair and cannot change the classification.",
        "MISSING_DATA_POLICY": f"An event or its matched control with any missing 1m close inside the window is dropped and counted. If the dropped-event rate exceeds {MAX_MISSING_EVENT_RATE} or any year keeps fewer than {MIN_EVENTS_PER_YEAR} events, SUPPORT_PASS is false and the result is INCONCLUSIVE_DISCOVERY. No imputation.",
        "OUTLIER_POLICY": "No winsorization and no outlier deletion in the primary statistic.",
        "PRE_CUTOFF_GAP_POLICY": "All 11 CPI events with EVIDENCE_LEAD_HOURS > 720 stay in the primary set. Sensitivity S_GAP repeats DELTA_24 on the complement (CPI lead <= 720 plus every FOMC event) and cannot change the classification.",
        "MULTIPLE_TESTING_POLICY": "One primary endpoint, one alpha. The five descriptive variants, S_GAP, the overlap-drop sensitivity and the placebo window are reported and cannot change the classification. Alpha is not split and is not relaxed.",
        "INFERENCE": {
            "METHOD": "STRATIFIED_LABEL_PERMUTATION",
            "STRATA": ["YEAR", "WEEKDAY", "UTC_HOUR"],
            "MATCHING": "1:1 without replacement inside each stratum, using scripts/research/discovery_sprint_03/common.py sample_matched_ids_per_cell",
            "MATCH_SEED": MATCH_SEED,
            "PERMUTATIONS": PERMUTATIONS,
            "PERMUTATION_SEED": PERMUTATION_SEED,
            "ALTERNATIVE": "two-sided-abs",
            "ALPHA": ALPHA,
            "CI": "95 percent normal interval using the permutation-null standard deviation of DELTA_24, centered on the observed DELTA_24. The interval is reported. The decision is the permutation p-value plus the conjunctive falsifiers.",
        },
        "FALSIFIERS": {
            "F1_PERMUTATION": "two-sided stratified permutation p-value > 0.05",
            "F2_TEMPORAL": f"the yearly mean difference shares the pooled sign in fewer than {MIN_YEARS_SHARING_SIGN} of {N_YEARS} years",
            "F3_PRIOR_WINDOW": (
                "On the 24h window immediately before the primary window, using the same matched control timestamps shifted back 24h, "
                f"the placebo contrast is significant at alpha in the same direction, OR more than half of events lack a control whose prior-window log return is within {PLACEBO_CALIPER_LOG} of the event's. "
                "Either condition means the primary difference is not specific to the pre-release window."
            ),
        },
        "CLASSIFICATION": {
            "PRECEDENCE": [
                "identity or digest failure -> INVALID_DISCOVERY",
                "SUPPORT_PASS false -> INCONCLUSIVE_DISCOVERY",
                "F1, F2 and F3 all not fired -> PROMISING_PROTOTYPE",
                "otherwise -> NO_USEFUL_STRUCTURE",
            ],
            "NO_TRADING_CLAIM": True,
            "DESCRIPTIVE_GRID_CANNOT_DECIDE": True,
        },
        "DATASETS": {
            "CPI": {"ID": CPI_DATASET_ID, "DIGEST": DATASET_DIGEST, "PATH": "docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/"},
            "FOMC": {"ID": FOMC_DATASET_ID, "PATH": "docs/research_data/D11_FOMC_OFFICIAL_V0/PIN.json", "NOTE": "Point-in-time status inherited from the pinned D11 official statements. Not re-audited here."},
        },
        "UNIVERSE_SUMMARY": {
            "CPI_N": universe["CPI_N"],
            "FOMC_N": universe["FOMC_N"],
            "EVENT_N": universe["EVENT_N"],
            "ISO_WEEK_N": universe["ISO_WEEK_N"],
            "OVERLAP_PAIRS": universe["OVERLAP_PAIRS"],
            "LONG_GAP_CPI_N": universe["LONG_GAP_CPI_N"],
            "YEAR_COUNTS": _year_counts(universe["EVENTS"]),
        },
        "EVENTS": events_out,
        "CONTROL_SLOT_CENSUS": slots,
        "POWER": power,
        "OUTCOME_BLIND_GATE": gate,
        "DEPENDENCE_MODEL": (
            "CPI releases are at least 647 hours apart and FOMC releases at least 984 hours apart, "
            "so same-family 24h windows do not overlap. Two CPI-FOMC pairs overlap (5.5h apart) and "
            f"are kept. Planning sample size is the {universe['ISO_WEEK_N']} ISO weeks, then divided by "
            f"{VARIANCE_INFLATION:g} as a dependence stress. Five years are a sign-stability gate, not the sample size."
        ),
    }


def _year_counts(events: list[dict]) -> dict:
    out: dict[str, int] = {}
    for e in events:
        y = str(e["YEAR"])
        out[y] = out.get(y, 0) + 1
    return dict(sorted(out.items()))


def assert_no_market_access() -> None:
    src = Path(__file__).read_text()
    # The contract names the dataset. It must not call a loader.
    banned = ("load_" + "hourly_closes", "btc_" + "legal_parquet", "read_" + "parquet", "py" + "arrow")
    for marker in banned:
        if marker in src:
            raise RuntimeError(f"DESIGN_MODULE_TOUCHES_MARKET_LOADER:{marker}")


def write_documents() -> dict:
    assert_no_market_access()
    doc = design_document()
    DESIGN_JSON.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    POWER_JSON.write_text(json.dumps(doc["POWER"] | {"GATE": doc["OUTCOME_BLIND_GATE"], "UNIVERSE": doc["UNIVERSE_SUMMARY"]}, indent=1, sort_keys=True) + "\n")
    return doc


def validate_written() -> list[str]:
    errors = []
    doc = json.loads(DESIGN_JSON.read_text())
    fresh = design_document()
    if doc["UNIVERSE_SUMMARY"] != fresh["UNIVERSE_SUMMARY"]:
        errors.append("UNIVERSE_DRIFT")
    if doc["POWER"] != fresh["POWER"]:
        errors.append("POWER_DRIFT")
    if doc["OUTCOME_BLIND_GATE"] != fresh["OUTCOME_BLIND_GATE"]:
        errors.append("GATE_DRIFT")
    if doc["PRIMARY_VARIANT"]["PRE_WINDOW_H"] != 24 or doc["PRIMARY_VARIANT"]["EVENT_SET"] != "FOMC_AND_CPI":
        errors.append("PRIMARY_NOT_SINGULAR")
    primaries = [v for v in doc["CARD_VARIANTS"] if v["ROLE"] == "PRIMARY"]
    if len(primaries) != 1:
        errors.append("PRIMARY_COUNT")
    if len(doc["EVENTS"]) != 99:
        errors.append("EVENT_N")
    cpi_ids = {e["EVENT_ID"] for e in doc["EVENTS"] if e["FAMILY"] == "CPI"}
    if len(cpi_ids) != 60:
        errors.append("CPI_N")
    if any(e["RELEASE_UTC"] >= "2025-01-01" for e in doc["EVENTS"]):
        errors.append("PROTECTED_EVENT")
    if doc["MARKET_DATA_OPENED"] or doc["MARKET_OUTCOMES_COMPUTED"]:
        errors.append("MARKET_FLAG")
    digest = json.loads((CPI_DIR / "MANIFEST.json").read_text())["CANONICAL_DATASET_DIGEST"]
    if digest != DATASET_DIGEST or doc["DATASETS"]["CPI"]["DIGEST"] != DATASET_DIGEST:
        errors.append("DIGEST")
    return errors


def main() -> int:
    write_documents()
    errors = validate_written()
    print("\n".join(errors) if errors else "VALID")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
