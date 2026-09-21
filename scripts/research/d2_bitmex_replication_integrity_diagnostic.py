"""Outcome-blind D2 BitMEX sample-identity diagnostic.

Identifies timestamp-complete decisions that fail frozen scientific
row construction. Does not compute arithmetic_mae, RV_ABSTENTION K,
MU_RULE, controls, or any D2 effect metric.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping

from scripts.research.d2_bitmex_pre2020 import refuse_binance_protected_path, utc_ms
from scripts.research.d2_bitmex_replication_evaluator import (
    bars_from_canonical_jsonl,
    load_sealed_canonical_bytes,
    timestamp_complete_decisions,
    verify_eligibility,
)
from scripts.research.d2_bitmex_replication_prereg import CANONICAL_REL
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
    Market06RowIneligible,
)
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    BAR_MS,
    FUTURE_BARS,
    RV_RETURN_COUNT,
    btc_ret_24h,
    btc_side_from_ret,
    feature_cutoff_ms,
    get_perp_bar_ending_at,
    get_perp_bar_opening_at,
    is_forbidden_decision,
    rv_btc_24h,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar

UTC = timezone.utc

REASON_ELIGIBLE = None


def _exception_reason(exc: BaseException) -> str:
    text = str(exc)
    if ":" in text:
        code = text.split(":", 1)[-1]
    else:
        code = text
    code = code.strip()
    known = {
        "BTC_RET_24H_EQ_0",
        "RV_LE_0_OR_NONFINITE",
        "NONPOSITIVE_BTC_RET_CLOSE",
        "NONPOSITIVE_RV_CLOSE",
        "NONPOSITIVE_ENTRY",
        "NONFINITE_BTC_RET_24H",
        "NONFINITE_RV_RETURN",
        "NONFINITE_Y",
        "INVALID_BTC_SIDE",
        "RV_CLOSE_COUNT",
        "FUTURE_BAR_COUNT",
    }
    if code in known:
        return code
    if "BTC_RET_24H_EQ_0" in text:
        return "BTC_RET_24H_EQ_0"
    if "RV_LE_0_OR_NONFINITE" in text:
        return "RV_LE_0_OR_NONFINITE"
    if "NONPOSITIVE_BTC_RET_CLOSE" in text:
        return "NONPOSITIVE_BTC_RET_CLOSE"
    if "NONPOSITIVE_RV_CLOSE" in text:
        return "NONPOSITIVE_RV_CLOSE"
    if "NONPOSITIVE_ENTRY" in text:
        return "NONPOSITIVE_ENTRY"
    return f"OTHER_EXACT_REASON:{code}"


def diagnose_scientific_eligibility(
    t_ms: int,
    perp: Mapping[int, PerpBar],
) -> str | None:
    """Return a frozen-kernel ineligibility reason, or None if the row survives.

    Stops before arithmetic_mae / adverse severity.
    """
    moment = C.utc_from_ms(t_ms)
    if moment.year >= 2025:
        return "PROTECTED_2025_PLUS"
    forbidden = is_forbidden_decision(moment)
    if forbidden is not None:
        return str(forbidden)
    e_ms = feature_cutoff_ms(t_ms)
    e_bar = get_perp_bar_ending_at(perp, e_ms)
    e_24h = get_perp_bar_ending_at(perp, e_ms - FUTURE_BARS * BAR_MS)
    if e_bar is None or e_24h is None:
        return "MISSING_FEATURE_BAR"
    try:
        ret = btc_ret_24h(e_bar.close, e_24h.close)
        btc_side_from_ret(ret)
    except (Market06RowIneligible, Market06IncompleteExecution) as exc:
        return _exception_reason(exc)
    rv_closes = []
    for k in range(RV_RETURN_COUNT, -1, -1):
        bar = get_perp_bar_ending_at(perp, e_ms - k * BAR_MS)
        if bar is None:
            return "MISSING_FEATURE_BAR"
        rv_closes.append(bar.close)
    try:
        rv_btc_24h(rv_closes)
    except (Market06RowIneligible, Market06IncompleteExecution) as exc:
        return _exception_reason(exc)
    entry_bar = get_perp_bar_opening_at(perp, t_ms)
    if entry_bar is None:
        return "MISSING_ENTRY_BAR"
    if not math.isfinite(entry_bar.open) or float(entry_bar.open) <= 0.0:
        return "NONPOSITIVE_ENTRY"
    for k in range(FUTURE_BARS):
        bar = get_perp_bar_opening_at(perp, t_ms + k * BAR_MS)
        if bar is None:
            return "MISSING_FUTURE_BAR"
        if bar.open_time_ms >= C.PROTECTED_START_MS:
            return "PROTECTED_FUTURE_BAR"
        for field in (bar.open, bar.high, bar.low, bar.close):
            if not math.isfinite(field):
                return "NONFINITE_FUTURE_OHLC"
    return REASON_ELIGIBLE


def reconstruct_timestamp_complete(repo, perp: Mapping[int, PerpBar]) -> list[datetime]:
    census = verify_eligibility(repo=repo)
    raw_open = utc_ms(
        datetime.fromisoformat(str(census["legal"]["RAW_DATA_START"]).replace("Z", "+00:00"))
    )
    return timestamp_complete_decisions(set(perp), raw_open_ms=raw_open)


def dropped_timestamp_complete_decisions(repo) -> dict[str, Any]:
    refuse_binance_protected_path(repo / CANONICAL_REL)
    jsonl = load_sealed_canonical_bytes(repo)
    perp = bars_from_canonical_jsonl(jsonl)
    complete = reconstruct_timestamp_complete(repo, perp)
    dropped: list[dict[str, Any]] = []
    constructed: list[datetime] = []
    for moment in complete:
        reason = diagnose_scientific_eligibility(C.ms_from_utc(moment), perp)
        if reason is None:
            constructed.append(moment)
        else:
            dropped.append(
                {
                    "DROP_TIMESTAMP": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "DROP_YEAR": int(moment.year),
                    "EXACT_INELIGIBILITY_REASON": reason,
                }
            )
    warmup_n = C.RV_TRAILING_WINDOW
    eligible = constructed[warmup_n:]
    years = {str(y): int(sum(1 for t in eligible if t.year == y)) for y in (2017, 2018, 2019)}
    return {
        "TIMESTAMP_COMPLETE_N": int(len(complete)),
        "SCIENTIFIC_CONSTRUCTED_N": int(len(constructed)),
        "SCIENTIFIC_WARMUP_N": int(warmup_n),
        "SCIENTIFIC_ELIGIBLE_N": int(len(eligible)),
        "SCIENTIFIC_FIRST_T": eligible[0].strftime("%Y-%m-%dT%H:%M:%SZ") if eligible else None,
        "SCIENTIFIC_LAST_T": eligible[-1].strftime("%Y-%m-%dT%H:%M:%SZ") if eligible else None,
        "SCIENTIFIC_YEAR_ELIGIBLE_N": years,
        "DROPPED": dropped,
        "ARITHMETIC_MAE_COMPUTED": False,
        "SEVERITY_COMPUTED": False,
        "RV_ABSTENTION_K_COMPUTED": False,
        "PRIMARY_OUTCOME_COMPUTED": False,
    }
