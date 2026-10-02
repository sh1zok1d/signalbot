"""Outcome-blind C033 primary-state count and V1 planning seal.

Counts the frozen primary forced-flow state on pinned CORE BTC/ETH klines for
2020-01..2024-12. It does not compute RV_DECAY, any post-T return, or a market
outcome. The planning object is sealed before the GV0R02 V1 compiler runs.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from scripts.research.generator_v0.feasibility_contract_v1 import (
    to_compiler_proposal_v1,
    validate_planning_v1,
)
from scripts.research.gv0r02_feasibility_compiler_v1 import compile_proposal_v1

REPO = Path(__file__).resolve().parents[2]
LEGAL_START = "2020-01"
LEGAL_END = "2024-12"
BUCKET_MS = 15 * 60 * 1000
MINUTE_MS = 60 * 1000
DAY_MS = 24 * 60 * 60 * 1000
BARS_PER_DAY = 24 * 4
SIGMA_DAYS = 30
TAKER_DAYS = 90
SIGMA_BARS = SIGMA_DAYS * BARS_PER_DAY
TAKER_BARS = TAKER_DAYS * BARS_PER_DAY
THIN_MS = 6 * 60 * 60 * 1000
SHOCK_SIGMA = 3.0
TAKER_LO = 0.01
TAKER_HI = 0.99
FRAG_Q = 0.95
ETH_SIGMA_MULT = 3.0
OVERSHOOT_FRACTION = 0.40

COMPONENTS = [
    "One-sided taker burst: 15m taker-buy share of quote volume outside the frozen trailing-90d percentile band",
    "Trade fragmentation: 15m trade count per unit quote volume above the trailing-30d 95th percentile",
    "Cross-asset synchrony: ETH 15m return of the same sign as the BTC shock and beyond 3 trailing-30d ETH sigma",
    "Intrabar overshoot: the 15m extreme in the shock direction exceeds the 15m close by at least 40 percent of the 15m high-low range",
]
COMPONENT_NAMES = [
    "ONE_SIDED_TAKER_BURST",
    "TRADE_FRAGMENTATION",
    "CROSS_ASSET_SYNCHRONY",
    "INTRABAR_OVERSHOOT",
]

BTC_INVENTORY = REPO / "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
ETH_SNAPSHOT = REPO / "docs/research_data/CORE_ETH_BINANCE_V0/SNAPSHOT_4b9c113f.json"
CARD_LEDGER = REPO / "docs/research/ladder-40-card-v03-r02-derived-critics-v2/run_ledger.json"


def legal_months() -> list[str]:
    months = [f"{year}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)]
    if months[0] != LEGAL_START or months[-1] != LEGAL_END or any(m >= "2025-01" for m in months):
        raise RuntimeError("legal month list left 2020-01..2024-12")
    return months


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_sources() -> list[dict]:
    """Zip identity for 2020-01..2024-12 only. Later months are not selected."""
    btc = json.loads(BTC_INVENTORY.read_text())
    eth = json.loads(ETH_SNAPSHOT.read_text())
    btc_by = {row["source_period"]: row for row in btc["objects"] if row.get("archive_class") == "monthly"}
    eth_by = {row["source_period"]: row for row in eth["objects"] if row.get("archive_class") == "monthly"}
    pinned = []
    for month in legal_months():
        for symbol, table, hash_key in (
            ("BTCUSDT", btc_by, "expected_sha256"),
            ("ETHUSDT", eth_by, "zip_sha256"),
        ):
            row = table.get(month)
            if row is None:
                raise RuntimeError(f"pinned {symbol} month {month} is absent")
            if month >= "2025-01":
                raise RuntimeError("protected month selected")
            filename = row["expected_zip_filename"]
            url = row.get("source_url") or (
                "https://data.binance.vision/data/futures/um/monthly/klines/"
                + symbol + "/1m/" + filename
            )
            if "2025" in url or "2026" in url:
                raise RuntimeError("protected url selected")
            pinned.append({
                "SYMBOL": symbol,
                "MONTH": month,
                "URL": url,
                "SHA256": row[hash_key],
                "FILENAME": filename,
            })
    return pinned


def fetch_verified_zip(spec: dict, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / spec["SYMBOL"] / spec["FILENAME"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or _sha256(dest) != spec["SHA256"]:
        urllib.request.urlretrieve(spec["URL"], dest)
    if _sha256(dest) != spec["SHA256"]:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {spec['FILENAME']}")
    return dest


def read_pinned_minutes(path: Path) -> np.ndarray:
    """Read open, high, low, close, quote volume, trade count, taker-buy quote."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise RuntimeError(f"unexpected zip members in {path.name}")
        payload = archive.read(names[0])
    if payload[:1].isalpha():
        payload = payload.split(b"\n", 1)[1]
    raw = np.loadtxt(io.BytesIO(payload), delimiter=",", usecols=(0, 1, 2, 3, 4, 7, 8, 10))
    if raw.ndim != 2 or raw.shape[1] != 8:
        raise RuntimeError(f"unexpected columns in {path.name}")
    return raw


def aggregate_15m(minutes: np.ndarray) -> dict[str, np.ndarray]:
    """UTC epoch-aligned 15m bars. Incomplete buckets are dropped, not filled."""
    order = np.argsort(minutes[:, 0], kind="mergesort")
    minutes = minutes[order]
    open_ms = minutes[:, 0].astype(np.int64)
    if np.any(np.diff(open_ms) <= 0):
        raise RuntimeError("minute open times are not strictly increasing")
    bucket = open_ms // BUCKET_MS
    cuts = np.flatnonzero(np.diff(bucket)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [len(bucket)]))
    counts = ends - starts
    complete = counts == 15
    # A complete bucket also spans exactly 15 distinct minutes inside [B, E).
    first = open_ms[starts]
    last = open_ms[ends - 1]
    aligned = (first % BUCKET_MS == 0) & ((last - first) == 14 * MINUTE_MS)
    keep = np.flatnonzero(complete & aligned)
    out_open = np.empty(len(keep), dtype=np.int64)
    o = np.empty(len(keep))
    h = np.empty(len(keep))
    l = np.empty(len(keep))
    c = np.empty(len(keep))
    q = np.empty(len(keep))
    n = np.empty(len(keep))
    tbq = np.empty(len(keep))
    for i, src in enumerate(keep):
        sl = slice(int(starts[src]), int(ends[src]))
        out_open[i] = int(first[src])
        o[i] = minutes[sl.start, 1]
        h[i] = float(np.max(minutes[sl, 2]))
        l[i] = float(np.min(minutes[sl, 3]))
        c[i] = minutes[sl.stop - 1, 4]
        q[i] = float(np.sum(minutes[sl, 5]))
        n[i] = float(np.sum(minutes[sl, 6]))
        tbq[i] = float(np.sum(minutes[sl, 7]))
    return {
        "open_ms": out_open,
        "end_ms": out_open + BUCKET_MS,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "quote": q,
        "trades": n,
        "taker_buy_quote": tbq,
    }


def _log_return(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    ret = np.full(len(open_), np.nan)
    ok = (open_ > 0) & (close > 0)
    ret[ok] = np.log(close[ok] / open_[ok])
    return ret


def _share(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.full(len(num), np.nan)
    ok = den > 0
    out[ok] = num[ok] / den[ok]
    return out


def _rolling_sample_std(values: np.ndarray, window: int) -> np.ndarray:
    """Sample std of values[i-window:i]. Index i does not enter its own window."""
    out = np.full(len(values), np.nan)
    if window < 2 or len(values) <= window:
        return out
    finite = np.isfinite(values)
    x = np.where(finite, values, 0.0)
    c1 = np.cumsum(x)
    c2 = np.cumsum(x * x)
    c_ok = np.cumsum(finite.astype(np.int64))
    idx = np.arange(window, len(values))
    total = c1[idx - 1] - np.concatenate(([0.0], c1[:-1]))[idx - window]
    total2 = c2[idx - 1] - np.concatenate(([0.0], c2[:-1]))[idx - window]
    n_ok = c_ok[idx - 1] - np.concatenate(([0], c_ok[:-1]))[idx - window]
    var = (total2 - (total * total) / window) / (window - 1)
    good = (n_ok == window) & (var > 0)
    out[idx[good]] = np.sqrt(var[good])
    return out


def label_primary_state(
    btc: dict[str, np.ndarray],
    eth: dict[str, np.ndarray],
    *,
    taker_bars: int = TAKER_BARS,
    sigma_bars: int = SIGMA_BARS,
    taker_span_ms: int = TAKER_DAYS * DAY_MS,
    sigma_span_ms: int = SIGMA_DAYS * DAY_MS,
) -> dict:
    """Label each BTC 15m bar using only bars at or before that bar.

    Thresholds use the strictly earlier window. The bar's own OHLC and flow
    are known at its end. No later bar is read.
    """
    n = len(btc["open_ms"])
    ret = _log_return(btc["open"], btc["close"])
    taker = _share(btc["taker_buy_quote"], btc["quote"])
    frag = _share(btc["trades"], btc["quote"])
    eth_index = {int(t): i for i, t in enumerate(eth["open_ms"])}
    eth_ret = _log_return(eth["open"], eth["close"])
    sigma = _rolling_sample_std(ret, sigma_bars)
    eth_sigma = _rolling_sample_std(eth_ret, sigma_bars)
    shock = np.zeros(n, dtype=bool)
    all4 = np.zeros(n, dtype=bool)
    for i in range(taker_bars, n):
        if int(btc["end_ms"][i] - btc["end_ms"][i - taker_bars]) != taker_span_ms:
            continue
        if int(btc["open_ms"][i] - btc["open_ms"][i - taker_bars]) != taker_bars * BUCKET_MS:
            continue
        r = ret[i]
        s = sigma[i]
        if not np.isfinite(r) or not np.isfinite(s) or s <= 0 or abs(r) <= SHOCK_SIGMA * s:
            continue
        shock[i] = True
        direction = 1 if r > 0 else -1
        lo, hi = np.nanquantile(taker[i - taker_bars:i], [TAKER_LO, TAKER_HI])
        taker_flag = np.isfinite(taker[i]) and np.isfinite(lo) and (taker[i] < lo or taker[i] > hi)
        frag_cut = float(np.nanquantile(frag[i - sigma_bars:i], FRAG_Q))
        frag_flag = np.isfinite(frag[i]) and np.isfinite(frag_cut) and frag[i] > frag_cut
        j = eth_index.get(int(btc["open_ms"][i]))
        sync = False
        if j is not None and j >= sigma_bars:
            if int(eth["end_ms"][j] - eth["end_ms"][j - sigma_bars]) == sigma_span_ms:
                er = eth_ret[j]
                es = eth_sigma[j]
                sync = (
                    np.isfinite(er)
                    and np.isfinite(es)
                    and es > 0
                    and abs(er) > ETH_SIGMA_MULT * es
                    and ((er > 0 and direction > 0) or (er < 0 and direction < 0))
                )
        span = btc["high"][i] - btc["low"][i]
        wick = (btc["high"][i] - btc["close"][i]) if direction > 0 else (btc["close"][i] - btc["low"][i])
        over = span > 0 and wick >= OVERSHOOT_FRACTION * span
        all4[i] = bool(taker_flag and frag_flag and sync and over)
    return {"shock": shock, "all4": all4, "end_ms": btc["end_ms"]}


def thin_first_in_6h(end_ms: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Keep the first masked bar in each 6h cluster. Later bars inside 6h of the kept bar drop."""
    kept = np.zeros(len(mask), dtype=bool)
    last = None
    for i in np.flatnonzero(mask):
        t = int(end_ms[i])
        if last is None or t - last >= THIN_MS:
            kept[i] = True
            last = t
    return kept


def summarize_counts(labels: dict) -> dict:
    end = labels["end_ms"]
    shock = labels["shock"]
    kept = thin_first_in_6h(end, shock)
    all4_kept = labels["all4"] & kept
    year = end.astype("datetime64[ms]").astype("datetime64[Y]").astype(int) + 1970
    day = end.astype("datetime64[ms]").astype("datetime64[D]")

    def by_year(mask: np.ndarray) -> dict[str, int]:
        counts = {}
        for y in range(2020, 2025):
            n = int(np.sum(mask & (year == y)))
            if n:
                counts[str(y)] = n
        return counts

    return {
        "TOTAL_ELIGIBLE_SHOCKS": int(np.sum(shock)),
        "TOTAL_ALL4_EVENTS": int(np.sum(all4_kept)),
        "ALL4_BEFORE_THINNING": int(np.sum(labels["all4"] & shock)),
        "COUNT_BY_YEAR": by_year(kept),
        "ALL4_COUNT_BY_YEAR": by_year(all4_kept),
        "DISTINCT_DAYS": int(len(set(day[kept].tolist()))),
        "DEPENDENCE_CLUSTER_COUNT": int(np.sum(kept)),
        "KEPT_ELIGIBLE_SHOCKS": int(np.sum(kept)),
        "COUNTING_NOTE": (
            "TOTAL_ELIGIBLE_SHOCKS counts shock bars with a complete trailing window before the 6h rule. "
            "KEPT_ELIGIBLE_SHOCKS and DEPENDENCE_CLUSTER_COUNT are the first bar in each 6h cluster. "
            "TOTAL_ALL4_EVENTS counts the all-four joint state on those kept bars. "
            "COUNT_BY_YEAR and DISTINCT_DAYS describe the kept eligible shocks, which are the nominal sample."
        ),
    }


def load_symbol_minutes(symbol: str, cache: Path) -> np.ndarray:
    rows = []
    for spec in pinned_sources():
        if spec["SYMBOL"] != symbol:
            continue
        path = fetch_verified_zip(spec, cache)
        rows.append(read_pinned_minutes(path))
    if not rows:
        raise RuntimeError(f"no pinned months for {symbol}")
    return np.concatenate(rows, axis=0)


def run_count(cache: Path) -> dict:
    btc = aggregate_15m(load_symbol_minutes("BTCUSDT", cache))
    eth = aggregate_15m(load_symbol_minutes("ETHUSDT", cache))
    labels = label_primary_state(btc, eth)
    summary = summarize_counts(labels)
    summary.update({
        "DETECTOR": "C033_PRIMARY_STATE_COUNT_V1",
        "PRIMARY_CELL": {
            "SHOCK_SIGMA": SHOCK_SIGMA,
            "TAKER_BAND": "p1_p99",
            "POST_WINDOW_H": 6,
        },
        "SHOCK_SIGMA_WINDOW": "TRAILING_30D_OF_15M_LOG_OPEN_TO_CLOSE_STRICTLY_BEFORE_T",
        "SHOCK_SIGMA_WINDOW_BASIS": (
            "The card names trailing sigma for the BTC shock and names trailing-30d only for the ETH sigma "
            "and the fragmentation percentile. The BTC shock sigma uses that same 30d window. It is not a searched parameter."
        ),
        "RETURN_DEFINITION": "15m log(close/open), known at the bar end",
        "THRESHOLD_WINDOW": "strictly earlier bars; the event bar is not inside its own percentile or sigma",
        "THINNING": "first eligible shock whose end is at least 6h after the previous kept shock",
        "NOT_COMPUTED": [
            "RV_DECAY",
            "future realized variance",
            "price or return after T",
            "MFE",
            "MAE",
            "future direction",
            "target values",
        ],
        "LEGAL_RANGE": "2020-01..2024-12",
        "DATASETS": ["CORE_BTC_BINANCE_V0", "CORE_ETH_BINANCE_V0"],
        "ZIP_OBJECTS": len(pinned_sources()),
        "PROTECTED_2025_2026_OPENED": False,
        "MARKET_OUTCOMES_OPENED": False,
        "BTC_15M_BARS": int(len(btc["open_ms"])),
        "ETH_15M_BARS": int(len(eth["open_ms"])),
    })
    return summary


def build_planning(counts: dict) -> dict:
    kept = counts["KEPT_ELIGIBLE_SHOCKS"]
    by_year = counts["COUNT_BY_YEAR"]
    if kept < 1 or sum(by_year.values()) != kept:
        raise RuntimeError("nominal count does not match the yearly kept-shock counts")
    nuisance = [
        "PRIOR_REALIZED_VOLATILITY",
        "LAGGED_TARGET",
        "TIME_OF_DAY",
        *COMPONENT_NAMES,
        *COMPONENTS,
        "LOG_SHOCK_SIZE",
        "HOUR_OF_WEEK",
        "YEAR",
    ]
    return {
        "CONTRACT_VERSION": "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1",
        "PROPOSAL_ID": "GV0V03L40-C033-V1",
        "MEMORY_CAMPAIGN_ID": "GV0V03L40",
        "SOURCE_RUN_ID": "ladder-40-card-v03-r02-derived-critics-v2",
        "CANDIDATE_ID": "C033",
        "MECHANISM": (
            "Liquidation engines send price-insensitive market orders that are finite in quantity. "
            "Once the inventory of margin-deficient positions is exhausted, the forcing stops. "
            "A shock produced by forced flow should therefore lose volatility faster than an equal-size shock "
            "driven by discretionary information. The forced-flow state is identified only when several "
            "independent footprints occur together."
        ),
        "FALSIFIABLE_CLAIM": (
            "The joint coefficient lies inside the permutation null. Alternatively, it has the opposite sign, "
            "meaning slower decay, in at least 3 of 5 years."
        ),
        "EVENT_OR_STATE_DEFINITION": (
            "Primary cell only: BTC 15m absolute log(close/open) beyond 3 trailing-30d sigma, "
            "taker-buy quote share outside the trailing-90d p1-p99 band, trade count per quote volume "
            "above the trailing-30d 95th percentile, ETH 15m return of the same sign beyond 3 trailing-30d ETH sigma, "
            "and intrabar overshoot of at least 40 percent of the 15m range. "
            "The nominal sample keeps the first eligible shock in each 6h cluster."
        ),
        "PRIMARY_OBSERVABLE": "FORCED_FLOW_ALL4_JOINT",
        "ENDPOINT_MOMENT": "SECOND_MOMENT",
        "COUNTERFACTUAL_CLASS": (
            "Permute the ALL4 joint label within YEAR x SHOCK_SIZE_STRATUM while preserving individual "
            "component main effects, their marginal counts, and the frozen nuisance structure."
        ),
        "NAMED_INFERENCE_CLASS": "PERMUTATION_GROUP_INVARIANCE",
        "HISTORICAL_WINDOW": "2020-01..2024-12",
        "POINT_IN_TIME_REQUIREMENTS": [
            {"DATASET_ID": "CORE_BTC_BINANCE_V0", "PIT_STATUS": "VERIFIED"},
            {"DATASET_ID": "CORE_ETH_BINANCE_V0", "PIT_STATUS": "VERIFIED"},
        ],
        "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION": {
            "COUNTING_UNIT": "KEPT_ELIGIBLE_15M_SHOCK_AFTER_6H_THINNING",
            "WINDOW": "2020-01..2024-12",
            "INCLUSION_RULE": (
                "BTC 15m bar with a complete trailing 90d history whose absolute log(close/open) exceeds "
                "3 trailing-30d sigma, then the first such bar in each 6h cluster."
            ),
            "EXCLUSION_RULE": (
                "Bars without a complete trailing window, bars inside 6h after a kept shock, "
                "and every month from 2025-01 onward."
            ),
            "OUTCOME_FILTER": "NONE",
            "DECLARED_NOMINAL_COUNT": kept,
            "DECLARED_COUNT_BY_YEAR": by_year,
        },
        "DEPENDENCE_CLUSTERING_UNIT": "6H_EVENT_CLUSTER",
        "ERA_ROLES": {
            "BINANCE_2020_2024": "DISCOVERY",
            "BITMEX_2016_2019": "HISTORICAL_REPLICATION_CANDIDATE",
            "Y2025_2026": "PROTECTED_HOLDOUT",
        },
        "EXPECTED_EFFECT": {
            "DIRECTION": "NEGATIVE",
            "MIN_MEANINGFUL_EFFECT": 0.20,
            "UNITS": "STANDARDIZED_RV_DECAY_SD",
            "RATIONALE": (
                "An incremental effect smaller than 0.20 outcome SD is not large enough to justify carrying "
                "a four-component forced-flow state into the Signalbot decision/context layer. "
                "This is a planning magnitude. It is not an observed effect."
            ),
        },
        "REQUIRED_STRESS_SCREENS": ["STRESS_SD_MULTIPLIER", "HOMOGENEOUS_EFFECT", "ZERO_EFFECT_IN_ONE_ERA"],
        "FEATURE_REQUIREMENTS": ["CORE_BTC_BINANCE_V0", "CORE_ETH_BINANCE_V0"],
        "DATA_SOURCE_REFS": {
            "FEATURE_REGISTRY_VERSION": "GV0R02_FEATURE_REGISTRY_V0",
            "FEATURE_IDS": ["CORE_BTC_BINANCE_V0", "CORE_ETH_BINANCE_V0"],
        },
        "BLOCKING_ASSUMPTIONS": [
            "The permutation keeps each component's marginal count inside YEAR x SHOCK_SIZE_STRATUM.",
            "Overlapping trailing feature windows remain in the dependence description.",
            "Volatility clustering remains in the dependence description.",
            "Multiple shocks inside one market episode remain in the dependence description.",
            "Common ETH and BTC shocks remain in the dependence description.",
            "A time gap between events is not treated as independence.",
        ],
        "ERA_INVARIANCE_PRIOR": "NOT_EXPECTED",
        "ERA_INVARIANCE_RATIONALE": (
            "No BitMEX replication is claimed. The prospective Binance surface stays separate from discovery."
        ),
        "QUALITATIVE_DEPENDENCE_SOURCES": [
            "overlapping trailing feature windows",
            "volatility clustering",
            "multiple shocks inside the same market episode",
            "common ETH/BTC market shocks",
        ],
        "CLAIM_TYPE": "INCREMENTAL",
        "TARGET_CLASS": "UNCONDITIONAL",
        "VARIABLE_ROLES": {
            "REGIME_VARIABLES": [],
            "MECHANISM_VARIABLES": ["FORCED_FLOW_ALL4_JOINT"],
            "NUISANCE_BASELINE_VARIABLES": nuisance,
        },
        "INTRADAY": True,
        "PRIMARY_CELLS": [
            {
                "REGIME": "ALL_ELIGIBLE_BTC_15M_SHOCKS",
                "ESTIMAND": (
                    "standardized incremental coefficient of FORCED_FLOW_ALL4_JOINT on RV_DECAY "
                    "beyond component main effects and nuisance baseline"
                ),
                "HORIZON": "post window from T+1h through T+7h (POST_WINDOW_H = 6h)",
            }
        ],
        "PRACTICAL_BAR_BASIS": "PRODUCT_RELEVANCE",
        "DISCOVERY_SURFACE": {"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-01-01"},
        "REPLICATION_SURFACE": {
            "KIND": "PROSPECTIVE",
            "ID": "BINANCE_PROSPECTIVE_C033_V1",
            "START": "2027-01-01",
            "STARTS_AFTER_FREEZE": True,
            "STOPPING_RULE": {
                "MIN_N": 1000,
                "MAX_EPISODES": 1500,
                "END_DATE": "2028-12-31",
                "COUNTS_ONLY_MONITORING": True,
                "PRODUCT_EXPOSURE_HANDLING": (
                    "hidden from product users until the stopping rule fires and the replication "
                    "result is separately authorized"
                ),
            },
        },
        "EPOCHS": "CALENDAR_YEAR",
        "COMPLEXITY_CLASS": "COMPOSITE",
        "COMPONENTS": list(COMPONENTS),
        "PRIMARY_FREEZE": {"SHOCK_SIGMA": 3, "TAKER_BAND": "p1_p99", "POST_WINDOW_H": 6, "PRIMARY_CELLS": 1},
        "SECONDARY_DIAGNOSTIC_VARIANTS": {
            "SHOCK_SIGMA": 4,
            "TAKER_BAND": "p2_p98",
            "POST_WINDOW_H": 12,
            "ROLE": "SECONDARY_DIAGNOSTIC_ONLY",
            "ENTERS_PRIMARY_MULTIPLICITY": False,
        },
        "OUTCOME_BLIND_COUNTS": {
            "TOTAL_ELIGIBLE_SHOCKS": counts["TOTAL_ELIGIBLE_SHOCKS"],
            "TOTAL_ALL4_EVENTS": counts["TOTAL_ALL4_EVENTS"],
            "COUNT_BY_YEAR": by_year,
            "DISTINCT_DAYS": counts["DISTINCT_DAYS"],
            "DEPENDENCE_CLUSTER_COUNT": counts["DEPENDENCE_CLUSTER_COUNT"],
        },
    }


def seal_and_compile(planning: dict) -> tuple[dict, dict]:
    validate_planning_v1(planning)
    proposal = to_compiler_proposal_v1(planning)
    result = compile_proposal_v1(proposal)
    if planning != json.loads(json.dumps(planning)):
        raise RuntimeError("planning object changed")
    return proposal, result


def next_action(status: str) -> str:
    if status == "FEASIBLE_FOR_PREREGISTRATION":
        return "PREREGISTRATION_DESIGN"
    return "STOP"


def card_components_unchanged() -> bool:
    ledger = json.loads(CARD_LEDGER.read_text())
    card = next(row for row in ledger["PARSED_CARD"] if row["CANDIDATE_ID"] == "C033")
    return card["COMPONENTS"] == COMPONENTS and card["COMPLEXITY_CLASS"] == "COMPOSITE"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if not card_components_unchanged():
        raise SystemExit("C033 card components differ from the frozen text")
    cache = Path("/tmp/gv0v03l40_c033_legal_zips")
    counts = run_count(cache)
    planning = build_planning(counts)
    validate_planning_v1(planning)
    planning_path = REPO / "docs/research/GV0V03L40_C033_V1_PLANNING.json"
    write_json(planning_path, planning)
    sealed = json.loads(planning_path.read_text())
    proposal, result = seal_and_compile(sealed)
    if json.loads(planning_path.read_text()) != sealed:
        raise SystemExit("planning file changed during compile")
    result = {
        **result,
        "NOMINAL_N": sealed["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["DECLARED_NOMINAL_COUNT"],
        "ATTAINABLE_ALPHA": result["V0_PASSES"]["ALPHA_ATTAINABLE"],
        "C033_NEXT": next_action(result["FEASIBILITY_STATUS"]),
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_2026_OPENED": False,
        "SCIENTIFIC_DESIGN_CHANGED_AFTER_COMPILE": False,
    }
    write_json(REPO / "docs/research/GV0V03L40_C033_V1_FEASIBILITY.json", result)
    write_json(REPO / "docs/research/GV0V03L40_C033_V1_EVENT_COUNTS.json", counts)
    print(json.dumps({
        "FEASIBILITY_STATUS": result["FEASIBILITY_STATUS"],
        "C033_NEXT": result["C033_NEXT"],
        "TOTAL_ELIGIBLE_SHOCKS": counts["TOTAL_ELIGIBLE_SHOCKS"],
        "TOTAL_ALL4_EVENTS": counts["TOTAL_ALL4_EVENTS"],
        "COUNT_BY_YEAR": counts["COUNT_BY_YEAR"],
        "DISTINCT_DAYS": counts["DISTINCT_DAYS"],
        "DEPENDENCE_CLUSTER_COUNT": counts["DEPENDENCE_CLUSTER_COUNT"],
        "BLOCKERS": result["BLOCKERS"],
        "DISCOVERY_SCREEN": result["DISCOVERY_SCREEN"],
        "REPLICATION_SCREEN": result["REPLICATION_SCREEN"],
        "HETEROGENEITY_ASSESSABILITY": result["HETEROGENEITY_ASSESSABILITY"],
        "NOMINAL_N": result["V0_PASSES"].get("NOMINAL_N") if isinstance(result.get("V0_PASSES"), dict) else None,
    }, indent=2))
    del proposal


if __name__ == "__main__":
    main()
