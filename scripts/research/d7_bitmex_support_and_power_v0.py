"""D7_BITMEX_SUPPORT_AND_POWER_V0 — outcome-blind selector support and power.

Answers only:
1. Does frozen D7 have adequate selector/control support on pre-2020 BitMEX?
2. Would an exact confirmation attempt be sufficiently powered at the frozen
   Binance discovery effect?

Does not construct NEXT_HOUR_HIGH_IMPACT_STATE on real BitMEX rows.
Does not pair D7_STATE_t with D7_STATE_t+1.
Does not call the Binance scientific array builder or evaluator.
Power uses synthetic Bernoulli targets and the frozen Binance control rate.
"""
from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.d2_bitmex_pre2020 import BAR_MS, sha256_bytes
from scripts.research.discovery_sprint_02_impl import (
    D7_PCTL,
    D7_PRACTICAL_GATE,
    MIN_D7_STATE_PER_YEAR,
    MIN_D7_STATE_TOTAL,
    N_RANDOM_CONTROLS,
    N_RV_BUCKETS,
    PERCENTILE_METHOD,
    RV_CUTS,
    TRAILING_WINDOW,
    canonical_json,
    d7_selector_digest,
)

UTC = timezone.utc
HOUR_MS = 3_600_000
BARS_PER_HOUR = 12

UNIT = "D7_BITMEX_SUPPORT_AND_POWER_V0"
DATASET_ID = "D7_BITMEX_ACTIVITY_V0"
ACTIVITY_FIELD = "foreignNotional"
ACTIVITY_PORTABILITY_CLASS = "D7_ACTIVITY_SCIENTIFICALLY_COMPARABLE"
CANONICAL_REL = Path("docs/research_data/D7_BITMEX_ACTIVITY_V0/canonical_5m.jsonl.gz")
AUTHORITY_REL = Path("docs/research_data/D7_BITMEX_ACTIVITY_V0/SOURCE_AUTHORITY.json")
D2_CANONICAL_REL = Path("docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz")
RESULT_JSON_REL = Path("docs/research/D7_BITMEX_SUPPORT_AND_POWER_V0.json")
RESULT_MD_REL = Path("docs/research/D7_BITMEX_SUPPORT_AND_POWER_V0.md")

EXPECTED_CANONICAL_GZ_SHA256 = (
    "33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c"
)
EXPECTED_D2_GZ_SHA256 = (
    "8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa"
)
EXPECTED_ROW_COUNT = 382033

# Frozen Binance discovery planning effect. Not a BitMEX estimate.
BINANCE_MU_D7_RULE = 0.18943894389438945
BINANCE_MU_D7_CONTROL = 0.09856569856985697
BINANCE_DELTA_D7 = 0.09087324532453248
PLANNING_P0 = BINANCE_MU_D7_CONTROL

# Frozen before any BitMEX selector count or power result is observed.
POWER_SEED = 20260930171
MC_REPLICATES = 1000
PRIMARY_POWER_BAR = 0.80
PRIMARY_POWER_GATE = "STATISTICAL_MU_RULE_GT_CONTROL_P95"
EFFECT_FRACTIONS = (1.0, 0.75, 0.5)
WILSON_Z_95 = 1.959963984540054

INDEPENDENCE_CLASS_EXPECTED = (
    "D7_TARGET_FRESH_ON_PREVIOUSLY_EXPOSED_MARKET_SURFACE"
)

# Structural judgment, recorded before selector counts are known.
# The exchangeable year x RV_BUCKET Monte Carlo does not preserve dependence
# from overlapping 720-hour thresholds. This unit does not invent a replacement.
DEPENDENCE_MODIFICATION_REQUIRED_BEFORE_PREREG = True
DEPENDENCE_REVIEW_STATUS = "INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW"

FEASIBLE = "FEASIBLE_FOR_D7_BITMEX_PREREGISTRATION"
NEXT_UNIT_IF_FEASIBLE = "D7_BITMEX_CONFIRMATION_PREREG_FREEZE"


class SupportPowerError(RuntimeError):
    pass


class DataIdentityError(SupportPowerError):
    pass


class IndependenceError(SupportPowerError):
    pass


@dataclass(frozen=True)
class FiveMinuteBar:
    open_time_ms: int
    open: Any
    high: Any
    low: Any
    close: Any
    foreign_notional: Any


@dataclass(frozen=True)
class HourBar:
    hour_start_ms: int
    year: int
    open_1h: float
    close_1h: float
    foreign_notional_1h: float
    ret_abs_1h: float


@dataclass
class PredictorFrame:
    """Predictor-side quantities. `state` is D7_STATE_t only.

    `state_defined` is whether the trailing-P90 comparison was executed.
    It is not the next-hour target boolean.
    """

    hour_start_ms: np.ndarray
    year: np.ndarray
    ret_abs_1h: np.ndarray
    foreign_notional_1h: np.ndarray
    qrel_1h: list[float | None]
    impact_proxy: list[float | None]
    state: list[bool | None]
    state_defined: np.ndarray
    rv_bucket: np.ndarray


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def percentile(values: Sequence[float], p: float) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise SupportPowerError("EMPTY_PERCENTILE")
    return float(np.percentile(arr, p, method=PERCENTILE_METHOD))


def median(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise SupportPowerError("EMPTY_MEDIAN")
    return float(np.median(arr))


def wilson_score_interval(k: int, n: int, z: float = WILSON_Z_95) -> tuple[float, float]:
    if int(n) <= 0:
        raise SupportPowerError("WILSON_EMPTY_N")
    k = int(k)
    n = int(n)
    if k < 0 or k > n:
        raise SupportPowerError(f"WILSON_BAD_K:{k}:{n}")
    p = k / float(n)
    z2 = float(z) * float(z)
    denom = 1.0 + z2 / float(n)
    center = (p + z2 / (2.0 * float(n))) / denom
    half = float(z) * math.sqrt((p * (1.0 - p) + z2 / (4.0 * float(n))) / float(n)) / denom
    return float(max(0.0, center - half)), float(min(1.0, center + half))


def ms_to_iso(ms: int) -> str:
    dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def load_5m_bars(path: Path) -> list[FiveMinuteBar]:
    bars: list[FiveMinuteBar] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            open_ms = row.get("open_time_ms")
            if open_ms is None:
                raise DataIdentityError("NULL_OPEN_TIME")
            year = datetime.fromtimestamp(int(open_ms) / 1000.0, tz=UTC).year
            if year >= 2025:
                raise DataIdentityError(f"PROTECTED_OPEN_TIME:{open_ms}")
            bars.append(
                FiveMinuteBar(
                    open_time_ms=int(open_ms),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    foreign_notional=row.get(ACTIVITY_FIELD),
                )
            )
    return bars


def verify_bar_identity(bars: Sequence[FiveMinuteBar]) -> dict[str, Any]:
    if len(bars) != EXPECTED_ROW_COUNT:
        raise DataIdentityError(f"ROW_COUNT:{len(bars)}!={EXPECTED_ROW_COUNT}")
    nulls = {"open": 0, "high": 0, "low": 0, "close": 0, "foreignNotional": 0}
    duplicate = 0
    non_monotonic = 0
    prev: int | None = None
    missing: list[int] = []
    for bar in bars:
        if bar.open is None:
            nulls["open"] += 1
        if bar.high is None:
            nulls["high"] += 1
        if bar.low is None:
            nulls["low"] += 1
        if bar.close is None:
            nulls["close"] += 1
        if bar.foreign_notional is None:
            nulls["foreignNotional"] += 1
        if prev is not None:
            if bar.open_time_ms == prev:
                duplicate += 1
            elif bar.open_time_ms < prev:
                non_monotonic += 1
            else:
                cursor = prev + BAR_MS
                while cursor < bar.open_time_ms:
                    missing.append(cursor)
                    cursor += BAR_MS
        prev = bar.open_time_ms
    if duplicate or non_monotonic:
        raise DataIdentityError(f"ORDER:{duplicate}:{non_monotonic}")
    if any(nulls.values()):
        raise DataIdentityError(f"NULL_REQUIRED:{nulls}")
    gaps = _missing_runs(missing)
    return {
        "row_count": len(bars),
        "duplicate_timestamp_count": duplicate,
        "non_monotonic_steps": non_monotonic,
        "null_counts": nulls,
        "missing_buckets": len(missing),
        "missing_runs": gaps,
        "first_open_time": ms_to_iso(bars[0].open_time_ms),
        "last_open_time": ms_to_iso(bars[-1].open_time_ms),
        "monotonic": True,
        "no_fill": True,
        "no_interpolation": True,
        "no_forward_fill": True,
    }


def _missing_runs(missing: Sequence[int]) -> list[dict[str, Any]]:
    if not missing:
        return []
    runs: list[dict[str, Any]] = []
    start = missing[0]
    prev = missing[0]
    count = 1
    for ts in list(missing[1:]) + [None]:
        if ts is not None and ts == prev + BAR_MS:
            prev = ts
            count += 1
            continue
        runs.append(
            {
                "first_missing_bucket_open": ms_to_iso(start),
                "last_missing_bucket_open": ms_to_iso(prev),
                "half_open_interval_open_time": (
                    f"[{ms_to_iso(start)}, {ms_to_iso(prev + BAR_MS)})"
                ),
                "missing_buckets": count,
            }
        )
        if ts is None:
            break
        start = ts
        prev = ts
        count = 1
    return runs


def verify_data_identity(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    canonical = root / CANONICAL_REL
    authority_path = root / AUTHORITY_REL
    d2_path = root / D2_CANONICAL_REL
    for path in (canonical, authority_path, d2_path):
        if not path.is_file():
            raise DataIdentityError(f"MISSING:{path}")
        text = str(path)
        if "2025-" in text or "2026-" in text:
            raise DataIdentityError(f"PROTECTED_PATH:{path}")
    gz_hash = sha256_bytes(canonical.read_bytes())
    d2_hash = sha256_bytes(d2_path.read_bytes())
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    if gz_hash != EXPECTED_CANONICAL_GZ_SHA256:
        raise DataIdentityError("CANONICAL_HASH_MISMATCH")
    if authority.get("canonical_jsonl_gz_sha256") != EXPECTED_CANONICAL_GZ_SHA256:
        raise DataIdentityError("AUTHORITY_HASH_MISMATCH")
    if authority.get("dataset_id") != DATASET_ID:
        raise DataIdentityError("DATASET_ID_MISMATCH")
    selected = (authority.get("pit_audit") or {}).get("SELECTED_D7_ACTIVITY_FIELD")
    if selected != ACTIVITY_FIELD:
        raise DataIdentityError(f"ACTIVITY_FIELD:{selected}")
    portability = (authority.get("pit_audit") or {}).get("ACTIVITY_PORTABILITY_CLASS")
    if portability != ACTIVITY_PORTABILITY_CLASS:
        raise DataIdentityError(f"PORTABILITY:{portability}")
    if d2_hash != EXPECTED_D2_GZ_SHA256:
        raise DataIdentityError("D2_HASH_CHANGED")
    if authority.get("d2_canonical_sha256_unchanged_bytes") != EXPECTED_D2_GZ_SHA256:
        raise DataIdentityError("D2_AUTHORITY_HASH_MISMATCH")
    outcomes = authority.get("scientific_outcomes") or {}
    if outcomes.get("BINANCE_2025_OPENED") is not False:
        raise DataIdentityError("AUTHORITY_2025_OPENED")
    if outcomes.get("BINANCE_2026_OPENED") is not False:
        raise DataIdentityError("AUTHORITY_2026_OPENED")
    if outcomes.get("D7_PRIMARY_TARGET_OPENED") is not False:
        raise DataIdentityError("AUTHORITY_TARGET_OPENED")
    bars = load_5m_bars(canonical)
    quality = verify_bar_identity(bars)
    authority_gap = (authority.get("quality") or {}).get("gap_spans") or []
    if quality["missing_buckets"] != 288 or len(quality["missing_runs"]) != 1:
        raise DataIdentityError(f"MISSING_IDENTITY:{quality['missing_runs']}")
    run = quality["missing_runs"][0]
    if len(authority_gap) != 1:
        raise DataIdentityError("AUTHORITY_GAP_COUNT")
    # Authority stores the bracketing observed opens. The missing run is the
    # open interval strictly between them.
    bracket = authority_gap[0]
    if bracket.get("missing_bars") != 288:
        raise DataIdentityError("AUTHORITY_GAP_BARS")
    if run["half_open_interval_open_time"] != "[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)":
        raise DataIdentityError(f"GAP_INTERVAL:{run['half_open_interval_open_time']}")
    return {
        "DATA_IDENTITY_STATUS": "PASS",
        "DATASET_ID": DATASET_ID,
        "CANONICAL_GZ_SHA256": gz_hash,
        "D2_CANONICAL_GZ_SHA256": d2_hash,
        "D2_CANONICAL_MODIFIED": False,
        "ACTIVITY_FIELD": ACTIVITY_FIELD,
        "ACTIVITY_PORTABILITY_CLASS": ACTIVITY_PORTABILITY_CLASS,
        "BINANCE_2025_OPENED": False,
        "BINANCE_2026_OPENED": False,
        "files_read": [
            str(CANONICAL_REL),
            str(AUTHORITY_REL),
            str(D2_CANONICAL_REL),
        ],
        "quality": quality,
        "bars": bars,
    }


def aggregate_completed_hours(bars: Sequence[FiveMinuteBar]) -> list[HourBar]:
    by_open: dict[int, FiveMinuteBar] = {}
    for bar in bars:
        if bar.open_time_ms in by_open:
            raise DataIdentityError("DUPLICATE_OPEN_TIME")
        by_open[bar.open_time_ms] = bar
    if not by_open:
        return []
    first = min(by_open)
    last = max(by_open)
    hour = first - (first % HOUR_MS)
    end_limit = (last - (last % HOUR_MS)) + HOUR_MS
    hours: list[HourBar] = []
    while hour < end_limit:
        members: list[FiveMinuteBar] = []
        complete = True
        for k in range(BARS_PER_HOUR):
            found = by_open.get(hour + k * BAR_MS)
            if found is None:
                complete = False
                break
            members.append(found)
        if complete:
            built = _hour_from_members(hour, members)
            if built is not None:
                hours.append(built)
        hour += HOUR_MS
    return hours


def _hour_from_members(hour_start: int, members: Sequence[FiveMinuteBar]) -> HourBar | None:
    first = members[0]
    last = members[-1]
    open_px = _finite_float(first.open)
    close_px = _finite_float(last.close)
    if open_px is None or close_px is None or open_px <= 0.0 or close_px <= 0.0:
        return None
    event_return = math.log(close_px / open_px)
    if not math.isfinite(event_return):
        return None
    activity = 0.0
    for bar in members:
        value = _finite_float(bar.foreign_notional)
        if value is None:
            return None
        activity += value
    year = datetime.fromtimestamp(hour_start / 1000.0, tz=UTC).year
    if year >= 2025:
        raise DataIdentityError(f"PROTECTED_HOUR:{hour_start}")
    return HourBar(
        hour_start_ms=int(hour_start),
        year=int(year),
        open_1h=open_px,
        close_1h=close_px,
        foreign_notional_1h=float(activity),
        ret_abs_1h=abs(event_return),
    )


def rv_bucket_from_trailing(rv: float, trailing: Sequence[float]) -> int:
    if len(trailing) < TRAILING_WINDOW:
        raise SupportPowerError("RV_BUCKET_SHORT_WINDOW")
    p25 = percentile(trailing, RV_CUTS[0])
    p50 = percentile(trailing, RV_CUTS[1])
    p75 = percentile(trailing, RV_CUTS[2])
    if rv <= p25:
        return 0
    if rv <= p50:
        return 1
    if rv <= p75:
        return 2
    return 3


def build_predictor_frame(hours: Sequence[HourBar]) -> PredictorFrame:
    """Construct D7_STATE_t. Does not read or store a t+1 boolean."""

    qrels: list[float | None] = []
    impacts: list[float | None] = []
    states: list[bool | None] = []
    defined: list[bool] = []
    buckets: list[int] = []
    valid_volumes: list[float] = []
    valid_impacts: list[float] = []
    valid_rvs: list[float] = []
    for hour in hours:
        qrel = None
        impact = None
        state = None
        state_defined = False
        bucket = -1
        vol_ok = math.isfinite(hour.foreign_notional_1h)
        rv_ok = math.isfinite(hour.ret_abs_1h)
        if vol_ok and len(valid_volumes) >= TRAILING_WINDOW:
            med = median(valid_volumes[-TRAILING_WINDOW:])
            if math.isfinite(med) and med > 0.0 and hour.foreign_notional_1h > 0.0:
                qrel = hour.foreign_notional_1h / med
                if math.isfinite(qrel) and qrel > 0.0 and rv_ok:
                    impact = hour.ret_abs_1h / qrel
                    if not math.isfinite(impact):
                        impact = None
                        qrel = None
                else:
                    qrel = None
        if impact is not None and len(valid_impacts) >= TRAILING_WINDOW:
            p90 = percentile(valid_impacts[-TRAILING_WINDOW:], D7_PCTL)
            state = bool(impact > p90)
            state_defined = True
        if rv_ok and len(valid_rvs) >= TRAILING_WINDOW:
            bucket = rv_bucket_from_trailing(
                hour.ret_abs_1h, valid_rvs[-TRAILING_WINDOW:]
            )
        qrels.append(qrel)
        impacts.append(impact)
        states.append(state)
        defined.append(state_defined)
        buckets.append(bucket)
        if vol_ok:
            valid_volumes.append(hour.foreign_notional_1h)
        if impact is not None:
            valid_impacts.append(impact)
        if rv_ok:
            valid_rvs.append(hour.ret_abs_1h)
    return PredictorFrame(
        hour_start_ms=np.asarray([h.hour_start_ms for h in hours], dtype=np.int64),
        year=np.asarray([h.year for h in hours], dtype=np.int64),
        ret_abs_1h=np.asarray([h.ret_abs_1h for h in hours], dtype=np.float64),
        foreign_notional_1h=np.asarray(
            [h.foreign_notional_1h for h in hours], dtype=np.float64
        ),
        qrel_1h=qrels,
        impact_proxy=impacts,
        state=states,
        state_defined=np.asarray(defined, dtype=bool),
        rv_bucket=np.asarray(buckets, dtype=np.int64),
    )


def structural_target_eligible(
    hour_start_ms: np.ndarray,
    state_defined: np.ndarray,
) -> np.ndarray:
    """Next completed hour exists and its D7 state is defined.

    Reads `state_defined` at t+1, which is whether the trailing comparison
    was executed. Does not read the true/false D7 state at t+1.
    """

    n = int(hour_start_ms.size)
    if int(state_defined.size) != n:
        raise SupportPowerError("ELIGIBILITY_SHAPE")
    eligible = np.zeros(n, dtype=bool)
    index = {int(hour_start_ms[i]): i for i in range(n)}
    for i in range(n):
        nxt = index.get(int(hour_start_ms[i]) + HOUR_MS)
        if nxt is None:
            continue
        if bool(state_defined[nxt]):
            eligible[i] = True
    return eligible


def support_from_frame(frame: PredictorFrame) -> dict[str, Any]:
    eligible = structural_target_eligible(frame.hour_start_ms, frame.state_defined)
    years = sorted({int(y) for y in frame.year.tolist()})
    state_by_year = {str(year): 0 for year in years}
    state_by_stratum = {f"{year}:{bucket}": 0 for year in years for bucket in range(N_RV_BUCKETS)}
    eligible_by_stratum = {f"{year}:{bucket}": 0 for year in years for bucket in range(N_RV_BUCKETS)}
    candidate_by_stratum = {f"{year}:{bucket}": 0 for year in years for bucket in range(N_RV_BUCKETS)}
    selector_rows: list[tuple[int, int, int]] = []
    valid_impact = 0
    state_n = 0
    for i in range(int(frame.hour_start_ms.size)):
        if frame.impact_proxy[i] is not None:
            valid_impact += 1
        is_state = frame.state[i] is True
        bucket = int(frame.rv_bucket[i])
        year = int(frame.year[i])
        if is_state:
            state_n += 1
            state_by_year[str(year)] = state_by_year.get(str(year), 0) + 1
            if bucket >= 0:
                skey = f"{year}:{bucket}"
                state_by_stratum[skey] = state_by_stratum.get(skey, 0) + 1
        if bool(eligible[i]) and bucket >= 0:
            ekey = f"{year}:{bucket}"
            eligible_by_stratum[ekey] = eligible_by_stratum.get(ekey, 0) + 1
            if is_state:
                candidate_by_stratum[ekey] = candidate_by_stratum.get(ekey, 0) + 1
                selector_rows.append((int(frame.hour_start_ms[i]), year, bucket))
    strata = _stratum_table(eligible_by_stratum, candidate_by_stratum)
    failures = list(strata["failures"])
    if state_n < MIN_D7_STATE_TOTAL:
        failures.append(f"MIN_D7_STATE_TOTAL:{state_n}<{MIN_D7_STATE_TOTAL}")
    for year, n_year in state_by_year.items():
        if int(n_year) < MIN_D7_STATE_PER_YEAR:
            failures.append(
                f"MIN_D7_STATE_PER_YEAR:{year}:{n_year}<{MIN_D7_STATE_PER_YEAR}"
            )
    control_ok = not failures
    return {
        "CONSTRUCTED_HOURS": int(frame.hour_start_ms.size),
        "VALID_IMPACT_ROWS": int(valid_impact),
        "TARGET_STRUCTURALLY_ELIGIBLE_ROWS": int(np.count_nonzero(eligible)),
        "STATE_N": int(state_n),
        "STATE_N_BY_YEAR": {k: int(v) for k, v in sorted(state_by_year.items())},
        "STATE_N_BY_YEAR_RV_BUCKET": {
            k: int(v) for k, v in sorted(state_by_stratum.items())
        },
        "ELIGIBLE_N_BY_YEAR_RV_BUCKET": {
            k: int(v) for k, v in sorted(eligible_by_stratum.items())
        },
        "CANDIDATE_N_BY_YEAR_RV_BUCKET": {
            k: int(v) for k, v in sorted(candidate_by_stratum.items())
        },
        "SELECTOR_N": len(selector_rows),
        "SELECTOR_DIGEST": d7_selector_digest(selector_rows),
        "CONTROL_SUPPORT": "CONTROL_SUPPORT_OK" if control_ok else "CONTROL_SUPPORT_INSUFFICIENT",
        "CONTROL_SUPPORT_FAILURES": failures,
        "CONTROL_POOL_BY_STRATUM": strata["rows"],
        "STRATA_FOR_POWER": strata["power_rows"],
        "N_RANDOM_CONTROLS": N_RANDOM_CONTROLS,
        "MIN_D7_STATE_TOTAL": MIN_D7_STATE_TOTAL,
        "MIN_D7_STATE_PER_YEAR": MIN_D7_STATE_PER_YEAR,
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
        "ADJACENCY_INSPECTED": False,
    }


def _stratum_table(
    eligible_by_stratum: Mapping[str, int],
    candidate_by_stratum: Mapping[str, int],
) -> dict[str, Any]:
    keys = sorted(set(eligible_by_stratum) | set(candidate_by_stratum))
    rows: dict[str, Any] = {}
    power_rows: list[dict[str, int]] = []
    failures: list[str] = []
    for key in keys:
        eligible_n = int(eligible_by_stratum.get(key, 0))
        candidate_n = int(candidate_by_stratum.get(key, 0))
        non_candidate_n = eligible_n - candidate_n
        sampling_possible = candidate_n <= eligible_n
        census_ok = candidate_n == 0 or eligible_n >= 2 * candidate_n
        if not sampling_possible:
            failures.append(
                f"RATE_MATCHED_IMPOSSIBLE:{key}:K={candidate_n}:POOL={eligible_n}"
            )
        elif not census_ok:
            failures.append(
                f"STRATUM_POOL:{key}:K={candidate_n}:POOL={eligible_n}<{2 * candidate_n}"
            )
        rate = None if eligible_n == 0 else candidate_n / float(eligible_n)
        rows[key] = {
            "eligible_n": eligible_n,
            "candidate_n": candidate_n,
            "non_candidate_n": non_candidate_n,
            "candidate_rate": rate,
            "rate_matched_sampling_possible": sampling_possible,
            "census_pool_at_least_2k": census_ok,
            "n_control_draws": N_RANDOM_CONTROLS,
        }
        year_s, bucket_s = key.split(":")
        power_rows.append(
            {
                "year": int(year_s),
                "rv_bucket": int(bucket_s),
                "eligible_n": eligible_n,
                "candidate_n": candidate_n,
            }
        )
    return {"rows": rows, "power_rows": power_rows, "failures": failures}


def synthetic_power(
    strata: Sequence[Mapping[str, int]],
    *,
    p0: float = PLANNING_P0,
    delta: float = BINANCE_DELTA_D7,
    fraction: float = 1.0,
    seed: int = POWER_SEED,
    n_outer: int = MC_REPLICATES,
    n_inner: int = N_RANDOM_CONTROLS,
) -> dict[str, Any]:
    """Power of the frozen statistical gate under synthetic targets.

    Stratum sizes are the only BitMEX inputs. Targets are Bernoulli draws.
    p0 stays the frozen Binance control probability.
    """

    if not (0.0 < float(p0) < 1.0):
        raise SupportPowerError("P0_RANGE")
    p1 = float(p0) + float(fraction) * float(delta)
    if not (0.0 < p1 < 1.0):
        raise SupportPowerError(f"P1_RANGE:{p1}")
    prepared = []
    total_k = 0
    for row in sorted(strata, key=lambda item: (int(item["year"]), int(item["rv_bucket"]))):
        eligible_n = int(row["eligible_n"])
        candidate_n = int(row["candidate_n"])
        if candidate_n < 0 or eligible_n < candidate_n:
            raise SupportPowerError(f"STRATUM_SHAPE:{row}")
        if candidate_n == 0:
            continue
        prepared.append((candidate_n, eligible_n - candidate_n))
        total_k += candidate_n
    if total_k <= 0:
        raise SupportPowerError("NO_CANDIDATES_FOR_POWER")
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    rule_success = np.zeros(int(n_outer), dtype=np.int64)
    control_success = np.zeros((int(n_outer), int(n_inner)), dtype=np.int64)
    for candidate_n, non_candidate_n in prepared:
        rule_part, control_part = _stratum_synthetic_counts(
            rng,
            candidate_n=candidate_n,
            non_candidate_n=non_candidate_n,
            p1=p1,
            p0=float(p0),
            n_outer=int(n_outer),
            n_inner=int(n_inner),
        )
        rule_success += rule_part
        control_success += control_part
    mu_rule = rule_success / float(total_k)
    control_means = control_success / float(total_k)
    p95 = np.percentile(control_means, 95.0, method=PERCENTILE_METHOD, axis=1)
    statistical = mu_rule > p95
    mu_control = control_means.mean(axis=1)
    practical = (mu_rule - mu_control) >= float(D7_PRACTICAL_GATE)
    stat_k = int(np.count_nonzero(statistical))
    prac_k = int(np.count_nonzero(practical))
    stat_lo, stat_hi = wilson_score_interval(stat_k, int(n_outer))
    prac_lo, prac_hi = wilson_score_interval(prac_k, int(n_outer))
    return {
        "POWER": stat_k / float(n_outer),
        "POWER_95CI": [stat_lo, stat_hi],
        "POWER_N_SUCCESS": stat_k,
        "PRACTICAL_PASS_RATE_INFORMATIONAL": prac_k / float(n_outer),
        "PRACTICAL_PASS_RATE_95CI": [prac_lo, prac_hi],
        "MC_REPLICATES": int(n_outer),
        "N_RANDOM_CONTROLS": int(n_inner),
        "SEED": int(seed),
        "P0": float(p0),
        "DELTA": float(fraction) * float(delta),
        "P1": p1,
        "EFFECT_FRACTION": float(fraction),
        "TOTAL_CANDIDATE_N": int(total_k),
        "PRIMARY_POWER_GATE": PRIMARY_POWER_GATE,
        "TARGETS": "SYNTHETIC_BERNOULLI",
        "BITMEX_TPLUS1_USED": False,
    }


def _stratum_synthetic_counts(
    rng: np.random.Generator,
    *,
    candidate_n: int,
    non_candidate_n: int,
    p1: float,
    p0: float,
    n_outer: int,
    n_inner: int,
) -> tuple[np.ndarray, np.ndarray]:
    rule_success = rng.binomial(candidate_n, p1, size=n_outer).astype(np.int64)
    if non_candidate_n <= 0:
        return rule_success, np.repeat(rule_success[:, None], n_inner, axis=1)
    non_success = rng.binomial(non_candidate_n, p0, size=n_outer).astype(np.int64)
    k_c = rng.hypergeometric(
        candidate_n, non_candidate_n, candidate_n, size=(n_outer, n_inner)
    ).astype(np.int64)
    succ_c = rng.hypergeometric(
        rule_success[:, None],
        (candidate_n - rule_success)[:, None],
        k_c,
    ).astype(np.int64)
    k_u = candidate_n - k_c
    succ_u = rng.hypergeometric(
        non_success[:, None],
        (non_candidate_n - non_success)[:, None],
        k_u,
    ).astype(np.int64)
    return rule_success, succ_c + succ_u


def power_seed_for_fraction(fraction: float) -> int:
    order = {1.0: 0, 0.75: 1, 0.5: 2}
    if float(fraction) not in order:
        raise SupportPowerError(f"EFFECT_FRACTION:{fraction}")
    # Distinct deterministic streams. The published POWER_SEED is the parent.
    entropy = np.random.SeedSequence(POWER_SEED).spawn(3)[order[float(fraction)]]
    return int(entropy.generate_state(1)[0])


def run_power(strata: Sequence[Mapping[str, int]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "MC_REPLICATES": MC_REPLICATES,
        "POWER_SEED": POWER_SEED,
        "N_RANDOM_CONTROLS": N_RANDOM_CONTROLS,
        "P0": PLANNING_P0,
        "P0_SOURCE": "FROZEN_BINANCE_MU_D7_CONTROL",
        "P0_ESTIMATED_FROM_BITMEX_TPLUS1": False,
        "PLANNING_DELTA": BINANCE_DELTA_D7,
        "PLANNING_MU_RULE": BINANCE_MU_D7_RULE,
        "PLANNING_SOURCE": "DISCOVERY_SPRINT_02_D7_RESULT.json",
        "PRIMARY_POWER_GATE": PRIMARY_POWER_GATE,
        "PRIMARY_POWER_BAR": PRIMARY_POWER_BAR,
        "PRACTICAL_THRESHOLD": D7_PRACTICAL_GATE,
        "PRACTICAL_THRESHOLD_ROLE": "INFORMATIONAL_NOT_SUBSTITUTED_FOR_PRIMARY_BAR",
        "TEMPORAL_GATE": "NOT_SCORED",
        "TEMPORAL_NOTE": (
            "Frozen D7 temporal gate counts positive yearly deltas on Binance "
            "years 2020-2024. Those years are not this surface. No BitMEX "
            "temporal rule is invented in this unit."
        ),
    }
    labels = {1.0: "FULL", 0.75: "75PCT", 0.5: "50PCT"}
    for fraction in EFFECT_FRACTIONS:
        label = labels[fraction]
        seed = power_seed_for_fraction(fraction)
        result = synthetic_power(
            strata,
            fraction=fraction,
            seed=seed,
        )
        key = "POWER_FULL_EFFECT" if fraction == 1.0 else f"POWER_{label}_EFFECT"
        out[key] = result["POWER"]
        out[f"{key}_95CI"] = result["POWER_95CI"]
        out[f"{key}_N_SUCCESS"] = result["POWER_N_SUCCESS"]
        out[f"{key}_SEED"] = seed
        out[f"PRACTICAL_PASS_RATE_{label}_INFORMATIONAL"] = result[
            "PRACTICAL_PASS_RATE_INFORMATIONAL"
        ]
        out[f"PRACTICAL_PASS_RATE_{label}_95CI"] = result["PRACTICAL_PASS_RATE_95CI"]
    out["POWER_FULL_EFFECT_MEETS_BAR"] = bool(out["POWER_FULL_EFFECT"] >= PRIMARY_POWER_BAR)
    return out


def audit_independence(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    prereg = (root / "docs/research/D2_BITMEX_REPLICATION_PREREG.md").read_text(
        encoding="utf-8"
    )
    if "RV_ABSTENTION" not in prereg or "arithmetic_mae" not in prereg:
        raise IndependenceError("D2_TARGET_NOT_PRICE_PATH")
    if "NEXT_HOUR_HIGH_IMPACT_STATE" in prereg:
        raise IndependenceError("D2_PREREG_CONTAINS_D7_TARGET")
    smoking = []
    roots = [
        root / "docs" / "research",
        root / "docs" / "research_data",
        root / "scripts" / "research",
    ]
    allow_names = {
        "d7_bitmex_support_and_power_v0.py",
        "D7_BITMEX_SUPPORT_AND_POWER_V0.md",
        "D7_BITMEX_SUPPORT_AND_POWER_V0.json",
        "test_d7_bitmex_support_and_power_v0.py",
    }
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.name in allow_names:
                continue
            if path.suffix.lower() not in {".py", ".md", ".json"}:
                continue
            if path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            mentions_surface = "bitmex" in lowered or "xbtusd" in lowered
            if not mentions_surface:
                continue
            if '"NEXT_HOUR_HIGH_IMPACT_STATE_COMPUTED": true' in text:
                smoking.append(str(path.relative_to(root)))
            if "D7_PRIMARY_TARGET_OPENED = true" in text:
                smoking.append(str(path.relative_to(root)))
            if "evaluate_d7_scientific" in text and "foreignNotional" in text:
                smoking.append(str(path.relative_to(root)))
            if "construct_d7_scientific_arrays" in text and (
                "bitmex" in lowered or "foreignNotional" in text
            ):
                smoking.append(str(path.relative_to(root)))
    if smoking:
        raise IndependenceError("PRIOR_D7_TARGET_ARTIFACT:" + ",".join(sorted(set(smoking))))
    return {
        "INDEPENDENCE_CLASS": INDEPENDENCE_CLASS_EXPECTED,
        "D2_TARGET": "RV_ABSTENTION / arithmetic_mae price path",
        "D7_TARGET_PREVIOUSLY_COMPUTED_ON_BITMEX": False,
        "PRIOR_TPLUS1_ASSOCIATION_ARTIFACT": False,
        "MARKET_BYTES_PREVIOUSLY_EXPOSED_FOR_D2": True,
        "ACTIVITY_AUTHORITY": DATASET_ID,
        "SURFACE_CALLED_UNTOUCHED": False,
    }


def feasibility_decision(
    *,
    identity_ok: bool,
    independence_ok: bool,
    control_ok: bool,
    power_full: float | None,
    dependence_modification_required: bool = DEPENDENCE_MODIFICATION_REQUIRED_BEFORE_PREREG,
) -> str:
    """First failing gate. Order frozen before BitMEX counts are observed."""

    if not identity_ok:
        return "DATA_IDENTITY_INVALID"
    if not independence_ok:
        return "INDEPENDENCE_NOT_ESTABLISHED"
    if not control_ok:
        return "CONTROL_SUPPORT_INSUFFICIENT"
    if dependence_modification_required:
        return DEPENDENCE_REVIEW_STATUS
    if power_full is None or float(power_full) < PRIMARY_POWER_BAR:
        return "INFORMATIONALLY_WEAK"
    return FEASIBLE


def _public_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    support = dict(raw["support"])
    support.pop("STRATA_FOR_POWER", None)
    decision = raw["FEASIBILITY_DECISION"]
    payload = {
        "UNIT": UNIT,
        "DATA_IDENTITY_STATUS": raw["identity"]["DATA_IDENTITY_STATUS"],
        "DATASET_ID": DATASET_ID,
        "CANONICAL_GZ_SHA256": raw["identity"]["CANONICAL_GZ_SHA256"],
        "D2_CANONICAL_GZ_SHA256": raw["identity"]["D2_CANONICAL_GZ_SHA256"],
        "D2_CANONICAL_MODIFIED": False,
        "ACTIVITY_FIELD": ACTIVITY_FIELD,
        "ACTIVITY_PORTABILITY_CLASS": ACTIVITY_PORTABILITY_CLASS,
        "QUALITY": {
            key: raw["identity"]["quality"][key]
            for key in (
                "row_count",
                "duplicate_timestamp_count",
                "non_monotonic_steps",
                "null_counts",
                "missing_buckets",
                "missing_runs",
                "first_open_time",
                "last_open_time",
                "monotonic",
                "no_fill",
                "no_interpolation",
                "no_forward_fill",
            )
        },
        "CONSTRUCTED_HOURS": support["CONSTRUCTED_HOURS"],
        "VALID_IMPACT_ROWS": support["VALID_IMPACT_ROWS"],
        "TARGET_STRUCTURALLY_ELIGIBLE_ROWS": support["TARGET_STRUCTURALLY_ELIGIBLE_ROWS"],
        "STATE_N": support["STATE_N"],
        "STATE_N_BY_YEAR": support["STATE_N_BY_YEAR"],
        "STATE_N_BY_YEAR_RV_BUCKET": support["STATE_N_BY_YEAR_RV_BUCKET"],
        "ELIGIBLE_N_BY_YEAR_RV_BUCKET": support["ELIGIBLE_N_BY_YEAR_RV_BUCKET"],
        "CANDIDATE_N_BY_YEAR_RV_BUCKET": support["CANDIDATE_N_BY_YEAR_RV_BUCKET"],
        "SELECTOR_N": support["SELECTOR_N"],
        "SELECTOR_DIGEST": support["SELECTOR_DIGEST"],
        "CONTROL_SUPPORT": support["CONTROL_SUPPORT"],
        "CONTROL_SUPPORT_FAILURES": support["CONTROL_SUPPORT_FAILURES"],
        "CONTROL_POOL_BY_STRATUM": support["CONTROL_POOL_BY_STRATUM"],
        "INDEPENDENCE": raw["independence"],
        "INDEPENDENCE_CLASS": raw["independence"]["INDEPENDENCE_CLASS"],
        "POWER": raw["power"],
        "DEPENDENCE_REVIEW_STATUS": DEPENDENCE_REVIEW_STATUS,
        "DEPENDENCE_NOTE": _dependence_note(),
        "FEASIBILITY_DECISION": decision,
        "PRIMARY_BLOCKERS": raw["PRIMARY_BLOCKERS"],
        "NEXT_UNIT": NEXT_UNIT_IF_FEASIBLE if decision == FEASIBLE else "NONE",
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
        "D7_BITMEX_EFFECT_COMPUTED": False,
        "D7_BITMEX_REPLICATION_CLASS_ASSIGNED": False,
        "BINANCE_2025_OPENED": False,
        "BINANCE_2026_OPENED": False,
        "CONFIRMATION_PREREG_CREATED": False,
        "EXECUTION_PERMIT_CREATED": False,
        "CONFIRMATION_EXECUTED": False,
    }
    _assert_public_payload_closed(payload)
    return payload


def _dependence_note() -> str:
    return (
        "Structural dependence is present before any outcome is observed. "
        "Each D7 threshold is a 720-hour trailing percentile, so adjacent "
        "hours share 719 threshold inputs. QREL, IMPACT_PROXY, and RV_BUCKET "
        "use those overlapping histories. The panel is a repeated hourly "
        "sequence. calendar_year x RV_BUCKET stratification changes the "
        "sampling frame and does not preserve serial dependence. The frozen "
        "rate-matched Monte Carlo draws exchangeably inside each stratum. "
        "That null is not a dependence-preserving null for an hourly "
        "next-state association. This unit does not measure real D7 adjacency "
        "and does not invent a block estimator. A confirmation preregistration "
        "needs an explicit dependence-preserving inference choice first. "
        "The power figures in this unit are the power of that exchangeable "
        "gate under independent synthetic targets. They are not a "
        "dependence-robust power."
    )


def _assert_public_payload_closed(payload: Mapping[str, Any]) -> None:
    blob = json.dumps(payload)
    forbidden = (
        "hour_start_ms",
        "selector_rows",
        "transition",
        "persistence",
        "run_length",
        "consecutive",
        "next_d7",
        "MU_BITMEX",
        "REPLICATED",
    )
    for token in forbidden:
        if token in blob:
            raise SupportPowerError(f"PUBLIC_PAYLOAD_LEAK:{token}")
    if payload["D7_BITMEX_PRIMARY_TARGET_OPENED"] is not False:
        raise SupportPowerError("TARGET_FLAG")
    if payload["D7_BITMEX_EFFECT_COMPUTED"] is not False:
        raise SupportPowerError("EFFECT_FLAG")
    if payload["D7_BITMEX_REPLICATION_CLASS_ASSIGNED"] is not False:
        raise SupportPowerError("REPLICATION_FLAG")


def run_support_and_power(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    try:
        identity = verify_data_identity(root)
    except DataIdentityError as exc:
        raise DataIdentityError(str(exc)) from exc
    bars = identity.pop("bars")
    independence = audit_independence(root)
    hours = aggregate_completed_hours(bars)
    frame = build_predictor_frame(hours)
    support = support_from_frame(frame)
    # Drop the in-memory state sequence before power and serialization.
    del frame
    power = run_power(support["STRATA_FOR_POWER"])
    decision = feasibility_decision(
        identity_ok=True,
        independence_ok=True,
        control_ok=support["CONTROL_SUPPORT"] == "CONTROL_SUPPORT_OK",
        power_full=float(power["POWER_FULL_EFFECT"]),
    )
    blockers: list[str] = []
    if support["CONTROL_SUPPORT"] != "CONTROL_SUPPORT_OK":
        blockers.extend(support["CONTROL_SUPPORT_FAILURES"])
    if decision == DEPENDENCE_REVIEW_STATUS:
        blockers.append(
            "Exchangeable year x RV_BUCKET rate-matched Monte Carlo does not "
            "preserve overlapping 720-hour dependence. No replacement "
            "estimator is defined in this unit."
        )
    if decision == "INFORMATIONALLY_WEAK":
        blockers.append(
            f"POWER_FULL_EFFECT {power['POWER_FULL_EFFECT']} < {PRIMARY_POWER_BAR}"
        )
    payload = _public_payload(
        {
            "identity": identity,
            "independence": independence,
            "support": support,
            "power": power,
            "FEASIBILITY_DECISION": decision,
            "PRIMARY_BLOCKERS": blockers,
        }
    )
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    power = payload["POWER"]
    quality = payload["QUALITY"]
    run = quality["missing_runs"][0]
    lines = [
        "# D7 BitMEX support and power V0",
        "",
        f"**Unit:** `{UNIT}`",
        "",
        "Outcome-blind selector support and synthetic power on the pinned",
        f"`{DATASET_ID}` authority. The BitMEX primary target",
        "`NEXT_HOUR_HIGH_IMPACT_STATE` is unopened. No t+1 pairing, no",
        "persistence statistic, no BitMEX effect, no replication class.",
        "No confirmation preregistration and no execution permit.",
        "",
        "## Data identity",
        "",
        "```",
        f"DATA_IDENTITY_STATUS = {payload['DATA_IDENTITY_STATUS']}",
        f"DATASET_ID = {payload['DATASET_ID']}",
        f"CANONICAL_GZ_SHA256 = {payload['CANONICAL_GZ_SHA256']}",
        f"D2_CANONICAL_GZ_SHA256 = {payload['D2_CANONICAL_GZ_SHA256']}",
        f"D2_CANONICAL_MODIFIED = false",
        f"ACTIVITY_FIELD = {payload['ACTIVITY_FIELD']}",
        f"ACTIVITY_PORTABILITY_CLASS = {payload['ACTIVITY_PORTABILITY_CLASS']}",
        f"ROW_COUNT = {quality['row_count']}",
        f"FIRST_OPEN = {quality['first_open_time']}",
        f"LAST_OPEN = {quality['last_open_time']}",
        f"DUPLICATE_TIMESTAMPS = {quality['duplicate_timestamp_count']}",
        f"NON_MONOTONIC = {quality['non_monotonic_steps']}",
        f"NULL_OPEN = {quality['null_counts']['open']}",
        f"NULL_HIGH = {quality['null_counts']['high']}",
        f"NULL_LOW = {quality['null_counts']['low']}",
        f"NULL_CLOSE = {quality['null_counts']['close']}",
        f"NULL_FOREIGN_NOTIONAL = {quality['null_counts']['foreignNotional']}",
        f"MISSING_BUCKETS = {quality['missing_buckets']}",
        f"FIRST_MISSING_BUCKET = {run['first_missing_bucket_open']}",
        f"LAST_MISSING_BUCKET = {run['last_missing_bucket_open']}",
        f"MISSING_HALF_OPEN = {run['half_open_interval_open_time']}",
        "```",
        "",
        "No fill, interpolation, or forward-fill. Incomplete UTC hours are",
        "absent from the constructed-hour set.",
        "",
        "## Selector",
        "",
        "Completed UTC hours use the frozen D7 return: absolute log return",
        "from the first 5m open to the last 5m close, and only when all 12",
        "buckets exist. Quote activity is the sum of `foreignNotional`.",
        "`QREL_1H`, `IMPACT_PROXY`, trailing P90, and `RV_BUCKET` use the",
        "previous 720 valid values. The current hour is excluded. The state",
        "cut is strict `>`. Structural eligibility requires the next",
        "constructed hour to exist and to have a defined D7 state. It does",
        "not read whether that next state is true or false.",
        "",
        "```",
        f"CONSTRUCTED_HOURS = {payload['CONSTRUCTED_HOURS']}",
        f"VALID_IMPACT_ROWS = {payload['VALID_IMPACT_ROWS']}",
        f"TARGET_STRUCTURALLY_ELIGIBLE_ROWS = {payload['TARGET_STRUCTURALLY_ELIGIBLE_ROWS']}",
        f"STATE_N = {payload['STATE_N']}",
        f"SELECTOR_N = {payload['SELECTOR_N']}",
        f"SELECTOR_DIGEST = {payload['SELECTOR_DIGEST']}",
        f"STATE_N_BY_YEAR = {payload['STATE_N_BY_YEAR']}",
        "```",
        "",
        "Year by RV-bucket state counts and eligible counts are in the JSON",
        "twin. Selector timestamps are not listed.",
        "",
        "## Control support",
        "",
        "```",
        f"CONTROL_SUPPORT = {payload['CONTROL_SUPPORT']}",
        "```",
        "",
        "A stratum can host 10,000 rate-matched draws when candidate N is",
        "at most eligible N. The frozen discovery census also requires",
        "eligible N >= 2 times candidate N, and the discovery floors",
        f"`MIN_D7_STATE_TOTAL = {MIN_D7_STATE_TOTAL}` and",
        f"`MIN_D7_STATE_PER_YEAR = {MIN_D7_STATE_PER_YEAR}` on each observed",
        "BitMEX calendar year. Binance years 2020–2024 are not copied onto",
        "this surface. Each stratum row reports `eligible_n`, `candidate_n`,",
        "`non_candidate_n`, `candidate_rate`, and the two support flags.",
        "Candidate rates are higher in the top RV bucket because the frozen",
        "impact state uses absolute return and the bucket is the same",
        "absolute return. That is a selector property, not a next-hour result.",
        "",
        "## Independence",
        "",
        "```",
        f"INDEPENDENCE_CLASS = {payload['INDEPENDENCE_CLASS']}",
        "```",
        "",
        "The pre-2020 XBTUSD price path was already used for D2",
        "`RV_ABSTENTION` / `arithmetic_mae`. That surface is not untouched.",
        "No prior artifact computed the D7 target or a t+1 persistence",
        "statistic on BitMEX. Activity bytes are the new",
        f"`{DATASET_ID}` authority. The D2 canonical gzip is unchanged.",
        "",
        "## Power",
        "",
        "Planning effect is the frozen Binance discovery result only:",
        f"`MU_D7_RULE = {BINANCE_MU_D7_RULE}`,",
        f"`MU_D7_CONTROL = {BINANCE_MU_D7_CONTROL}`,",
        f"`DELTA_D7 = {BINANCE_DELTA_D7}`.",
        "Synthetic targets use that control probability as `p0` for",
        "non-candidates and `p0 + fraction * delta` for candidates.",
        "No BitMEX t+1 rate enters. The primary power event is the frozen",
        "statistical gate, candidate mean above the 95th percentile of",
        f"{N_RANDOM_CONTROLS} rate-matched control means. The practical",
        f"threshold `{D7_PRACTICAL_GATE}` is reported beside it and is not",
        "the primary bar. The Binance temporal-year gate is not scored.",
        "",
        "```",
        f"POWER_FULL_EFFECT = {power['POWER_FULL_EFFECT']}",
        f"POWER_FULL_EFFECT_95CI = {power['POWER_FULL_EFFECT_95CI']}",
        f"POWER_75PCT_EFFECT = {power['POWER_75PCT_EFFECT']}",
        f"POWER_75PCT_EFFECT_95CI = {power['POWER_75PCT_EFFECT_95CI']}",
        f"POWER_50PCT_EFFECT = {power['POWER_50PCT_EFFECT']}",
        f"POWER_50PCT_EFFECT_95CI = {power['POWER_50PCT_EFFECT_95CI']}",
        f"MC_REPLICATES = {power['MC_REPLICATES']}",
        f"POWER_SEED = {power['POWER_SEED']}",
        f"PRIMARY_BAR = {PRIMARY_POWER_BAR}",
        f"POWER_FULL_EFFECT_MEETS_BAR = {str(power['POWER_FULL_EFFECT_MEETS_BAR']).lower()}",
        f"PRACTICAL_PASS_RATE_FULL_INFORMATIONAL = {power['PRACTICAL_PASS_RATE_FULL_INFORMATIONAL']}",
        f"PRACTICAL_PASS_RATE_75PCT_INFORMATIONAL = {power['PRACTICAL_PASS_RATE_75PCT_INFORMATIONAL']}",
        f"PRACTICAL_PASS_RATE_50PCT_INFORMATIONAL = {power['PRACTICAL_PASS_RATE_50PCT_INFORMATIONAL']}",
        "```",
        "",
        "The practical pass rates use the frozen `0.05` threshold on the",
        "synthetic delta. They are not the primary bar. At half the Binance",
        "delta the expected contrast sits below `0.05`, so that informational",
        "rate is low even when the statistical gate passes.",
        "",
        "## Dependence",
        "",
        "```",
        f"DEPENDENCE_REVIEW_STATUS = {payload['DEPENDENCE_REVIEW_STATUS']}",
        "```",
        "",
        payload["DEPENDENCE_NOTE"],
        "",
        "## Decision",
        "",
        "```",
        f"FEASIBILITY_DECISION = {payload['FEASIBILITY_DECISION']}",
        f"PRIMARY_BLOCKERS = {payload['PRIMARY_BLOCKERS']}",
        f"NEXT_UNIT = {payload['NEXT_UNIT']}",
        "D7_BITMEX_PRIMARY_TARGET_OPENED = false",
        "D7_BITMEX_EFFECT_COMPUTED = false",
        "D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false",
        "BINANCE_2025_OPENED = false",
        "BINANCE_2026_OPENED = false",
        "```",
        "",
        "This unit does not classify scientific truth.",
        "",
    ]
    return "\n".join(lines)


def write_artifacts(payload: Mapping[str, Any], repo: Path | None = None) -> None:
    root = repo or repo_root()
    json_path = root / RESULT_JSON_REL
    md_path = root / RESULT_MD_REL
    json_path.write_text(canonical_json(payload), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def main() -> None:
    payload = run_support_and_power()
    write_artifacts(payload)
    print(canonical_json({
        "FEASIBILITY_DECISION": payload["FEASIBILITY_DECISION"],
        "CONTROL_SUPPORT": payload["CONTROL_SUPPORT"],
        "STATE_N": payload["STATE_N"],
        "SELECTOR_DIGEST": payload["SELECTOR_DIGEST"],
        "POWER_FULL_EFFECT": payload["POWER"]["POWER_FULL_EFFECT"],
        "NEXT_UNIT": payload["NEXT_UNIT"],
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
    }))


if __name__ == "__main__":
    main()
