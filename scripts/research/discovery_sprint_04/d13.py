"""D13 weekly cross-sectional rank-IC evaluator.

Pure functions. Real-panel scientific execution is refused by evaluate.py
during this unit. Residual weekly serial dependence is a declared limitation
and is not "improved" here.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04.d13_terminal_mark import (
    DEFERRED_TERMINAL_MARK_UNRESOLVED,
    NO_POST_T_CLOSE,
    assert_terminal_marks_resolved,
    no_post_t_close_selected_n,
    terminal_mark,
)


def average_ranks(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise C.Sprint04IntegrityError("D13_EMPTY_RANKS")
    if not np.all(np.isfinite(arr)):
        raise C.Sprint04IntegrityError("D13_RANK_NONFINITE")
    sorter = np.argsort(arr, kind="mergesort")
    sorted_vals = arr[sorter]
    ranks = np.empty(arr.size, dtype=np.float64)
    i = 0
    n = arr.size
    while i < n:
        j = i + 1
        while j < n and sorted_vals[j] == sorted_vals[i]:
            j += 1
        avg = 0.5 * ((i + 1) + j)
        ranks[sorter[i:j]] = avg
        i = j
    return ranks


def spearman_rank_ic(formation: Sequence[float], holding: Sequence[float]) -> float:
    x = np.asarray(list(formation), dtype=np.float64)
    y = np.asarray(list(holding), dtype=np.float64)
    if x.size != y.size or x.size < 2:
        raise C.Sprint04IntegrityError("D13_IC_SHAPE")
    rx = average_ranks(x)
    ry = average_ranks(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = float(np.sqrt((rx * rx).sum() * (ry * ry).sum()))
    if denom == 0.0:
        raise C.Sprint04IntegrityError("D13_IC_ZERO_VARIANCE")
    return C.finite(float((rx * ry).sum() / denom), name="SPEARMAN_IC")


def log_return(end_px: float, start_px: float) -> float:
    if not (math.isfinite(end_px) and math.isfinite(start_px)) or start_px <= 0 or end_px <= 0:
        raise C.Sprint04IntegrityError("D13_RETURN_NONPOSITIVE")
    return C.finite(math.log(end_px / start_px), name="LOG_RETURN")


def formation_return(close_at_t: float, close_at_t_minus_7d: float) -> float:
    return log_return(close_at_t, close_at_t_minus_7d)


def holding_return_from_mark(entry_close: float, terminal_close: float) -> float:
    return log_return(terminal_close, entry_close)


def holding_return_for_symbol(
    symbol: str,
    t_ms: int,
    daily_closes: Mapping[int, float],
    *,
    terminal_mark_authority: Mapping[str, float] | None = None,
) -> float:
    mark = terminal_mark(symbol, t_ms, daily_closes)
    if mark.status == NO_POST_T_CLOSE:
        authority = terminal_mark_authority or {}
        if symbol not in authority:
            raise C.DeferredD13(
                f"{DEFERRED_TERMINAL_MARK_UNRESOLVED}:{symbol}:{t_ms}"
            )
        return holding_return_from_mark(mark.entry_close, float(authority[symbol]))
    if mark.terminal_close is None:
        raise C.Sprint04IntegrityError(f"D13_MARK_WITHOUT_TERMINAL:{symbol}")
    return holding_return_from_mark(mark.entry_close, mark.terminal_close)


def quintile_labels(formation: Sequence[float], *, n_q: int = C.D13_QUINTILES) -> np.ndarray:
    arr = np.asarray(list(formation), dtype=np.float64)
    n = arr.size
    if n < n_q:
        raise C.Sprint04IntegrityError("D13_QUINTILE_SHORT")
    order = np.argsort(arr, kind="mergesort")
    labels = np.empty(n, dtype=np.int64)
    for rank_i, idx in enumerate(order):
        labels[idx] = (rank_i * n_q) // n
    return labels


def top_minus_bottom_spread(
    formation: Sequence[float],
    holding: Sequence[float],
    *,
    n_q: int = C.D13_QUINTILES,
) -> float:
    labels = quintile_labels(formation, n_q=n_q)
    h = np.asarray(list(holding), dtype=np.float64)
    bottom = h[labels == 0]
    top = h[labels == n_q - 1]
    if bottom.size == 0 or top.size == 0:
        raise C.Sprint04IntegrityError("D13_EMPTY_QUINTILE")
    return C.finite(float(top.mean() - bottom.mean()), name="Q5_MINUS_Q1")


def sign_of_pooled_ic(pooled_ic: float) -> int:
    if not math.isfinite(pooled_ic):
        raise C.Sprint04IntegrityError("D13_POOLED_IC_NONFINITE")
    if pooled_ic > 0:
        return 1
    if pooled_ic < 0:
        return -1
    return 0


def signed_practical_spread(raw_q5_minus_q1: float, pooled_ic: float) -> float:
    """Sign the SAME pooled IC. Do not choose max(momentum, reversal)."""

    return C.finite(
        float(sign_of_pooled_ic(pooled_ic) * raw_q5_minus_q1),
        name="SIGNED_SPREAD",
    )


def two_sided_sign_flip_pvalue(
    weekly_ic: Sequence[float],
    *,
    n: int = C.D13_N_RANDOMIZATIONS,
    seed: int = C.D13_RANDOM_SEED,
) -> float:
    arr = np.asarray(list(weekly_ic), dtype=np.float64)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        raise C.Sprint04IntegrityError("D13_MC_NONFINITE")
    observed = float(arr.mean())
    rng = np.random.Generator(np.random.PCG64(seed))
    count = 0
    for _ in range(n):
        flips = rng.choice(np.array([-1.0, 1.0]), size=arr.size)
        null_mean = float((arr * flips).mean())
        if abs(null_mean) >= abs(observed):
            count += 1
    return float((1.0 + count) / (1.0 + n))


def practical_gate(signed_spread: float, *, floor: float = C.D13_FRICTION_FLOOR) -> bool:
    return math.isfinite(signed_spread) and signed_spread >= floor


def temporal_gate(yearly_mean_ic: Mapping[str, float], pooled_ic: float) -> bool:
    sign = sign_of_pooled_ic(pooled_ic)
    if sign == 0:
        return False
    matching = [
        year
        for year, value in yearly_mean_ic.items()
        if math.isfinite(value) and sign_of_pooled_ic(value) == sign
    ]
    return len(matching) >= C.D13_TEMPORAL_YEARS_REQUIRED


def listing_age_ok(first_open_ms: int, t_ms: int) -> bool:
    return first_open_ms <= t_ms - C.D13_LISTING_AGE_DAYS * C.DAY_MS


def completeness_ok(close_present: Mapping[int, bool], t_ms: int) -> bool:
    return bool(
        close_present.get(t_ms - C.DAY_MS, False)
        and close_present.get(t_ms - C.D13_FORMATION_DAYS * C.DAY_MS - C.DAY_MS, False)
    )


def trailing_quote_volume(
    quote_by_open: Mapping[int, float],
    t_ms: int,
    *,
    window_days: int = C.D13_LIQUIDITY_WINDOW_DAYS,
) -> float:
    total = 0.0
    start = t_ms - window_days * C.DAY_MS
    for open_ms, volume in quote_by_open.items():
        if start <= open_ms < t_ms:
            if not math.isfinite(volume) or volume < 0:
                raise C.Sprint04IntegrityError("D13_QUOTE_VOLUME_INVALID")
            total += float(volume)
    return total


def select_top_n(
    eligible: Sequence[str],
    liquidity: Mapping[str, float],
    *,
    n: int,
) -> list[str]:
    ranked = sorted(eligible, key=lambda sym: (-float(liquidity[sym]), sym))
    return ranked[:n]


def n_from_eligible_counts(counts: Sequence[int]) -> int:
    if not counts:
        raise C.Sprint04IntegrityError("D13_NO_DECISION_MONDAYS")
    return min(C.D13_N_CAP, min(int(c) for c in counts))


def decision_mondays() -> list[date]:
    return C.mondays_inclusive(C.D13_FIRST_MONDAY_FLOOR, C.D13_LAST_DECISION_MONDAY)


def refuse_protected_year_timestamp(ms: int) -> None:
    if ms >= C.PROTECTED_START_MS:
        raise C.ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{ms}")


def evaluate_d13_scientific(
    weekly_ic: Sequence[float],
    weekly_years: Sequence[int],
    weekly_raw_spreads: Sequence[float],
    *,
    support: Mapping[str, Any],
    n: int,
    no_post_t_close_selected_n: int,
    pinned_taker_fee: float | None,
) -> dict[str, Any]:
    """Pure evaluator on supplied weekly arrays. Must not be called on real panel here."""

    identity_ok = bool(support.get("IDENTITY_OK"))
    support_pass = bool(support.get("SUPPORT_PASS"))
    summary: dict[str, Any] = {
        "IDENTITY_OK": identity_ok,
        "SUPPORT_PASS": support_pass,
        "STATISTICAL_GATE": False,
        "PRACTICAL_GATE": False,
        "TEMPORAL_GATE": False,
        "RANDOM_SEED": C.D13_RANDOM_SEED,
        "N_RANDOMIZATIONS": C.D13_N_RANDOMIZATIONS,
        "N": n,
        "NO_POST_T_CLOSE_SELECTED_N": int(no_post_t_close_selected_n),
        "PINNED_TAKER_FEE": pinned_taker_fee,
        "FRICTION_FLOOR": None if pinned_taker_fee is None else C.D13_FEE_LEGS * pinned_taker_fee,
        "TEMPORAL_DEPENDENCE_LIMITATION": C.D13_TEMPORAL_DEPENDENCE_LIMITATION,
        "DIRECTION_RULE": "Report observed pooled IC sign; do not choose momentum vs reversal after seeing the result.",
    }
    if not identity_ok:
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    if no_post_t_close_selected_n > 0 and not support.get("TERMINAL_MARK_AUTHORITY_FROZEN"):
        summary["STATUS"] = DEFERRED_TERMINAL_MARK_UNRESOLVED
        summary["SUPPORT_PASS"] = False
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    if pinned_taker_fee is None:
        summary["STATUS"] = "DEFERRED_PRACTICAL_FLOOR_NOT_PINNED"
        summary["SUPPORT_PASS"] = False
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    if n < C.D13_N_MIN or len(weekly_ic) < C.D13_MIN_WEEKS:
        summary["SUPPORT_PASS"] = False
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    if not support_pass:
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    ics = [C.finite(x, name="WEEKLY_IC") for x in weekly_ic]
    pooled = float(np.mean(ics))
    raw_spreads = [C.finite(x, name="RAW_SPREAD") for x in weekly_raw_spreads]
    mean_raw = float(np.mean(raw_spreads))
    signed = signed_practical_spread(mean_raw, pooled)
    p_value = two_sided_sign_flip_pvalue(ics)
    yearly: dict[str, float] = {}
    by_year: dict[int, list[float]] = {}
    for year, value in zip(weekly_years, ics):
        by_year.setdefault(int(year), []).append(value)
    for year, values in sorted(by_year.items()):
        yearly[str(year)] = float(np.mean(values))
    summary.update(
        {
            "POOLED_MEAN_IC": pooled,
            "POOLED_IC_SIGN": sign_of_pooled_ic(pooled),
            "STRUCTURE_LABEL": (
                "MOMENTUM"
                if pooled > 0
                else "REVERSAL"
                if pooled < 0
                else "ZERO"
            ),
            "MEAN_RAW_Q5_MINUS_Q1": mean_raw,
            "SIGNED_SPREAD": signed,
            "MC_P": p_value,
            "STATISTICAL_GATE": p_value < C.D13_MC_ALPHA,
            "PRACTICAL_GATE": practical_gate(signed, floor=C.D13_FEE_LEGS * pinned_taker_fee),
            "TEMPORAL_GATE": temporal_gate(yearly, pooled),
            "YEARLY_MEAN_IC": yearly,
            "WEEK_N": len(ics),
        }
    )
    summary["CLASSIFICATION"] = C.classify_from_summary(summary)
    return summary


def classify_d13_from_summary(summary: Mapping[str, Any]) -> str:
    return C.classify_from_summary(summary)


def assert_no_survival_conditioning(selected_at_t: Sequence[str], survived_to_t7: Sequence[str]) -> None:
    """Selected set must not be a function of T+7 survival."""

    if set(selected_at_t) == set(survived_to_t7) and len(selected_at_t) != len(survived_to_t7):
        raise C.Sprint04IntegrityError("D13_SURVIVAL_CONDITIONING")


def assert_no_relisting_leakage(
    holding_week_opens: Sequence[int],
    used_open_ms: int | None,
    t_ms: int,
) -> None:
    if used_open_ms is None:
        return
    legal = {t_ms + k * C.DAY_MS for k in range(C.D13_HOLDING_DAYS)}
    if used_open_ms not in legal:
        raise C.Sprint04IntegrityError("D13_RELISTING_LEAKAGE")
    if used_open_ms not in set(holding_week_opens) and used_open_ms > t_ms + (C.D13_HOLDING_DAYS - 1) * C.DAY_MS:
        raise C.Sprint04IntegrityError("D13_RELISTING_LEAKAGE")


__all__ = [
    "assert_no_relisting_leakage",
    "assert_no_survival_conditioning",
    "assert_terminal_marks_resolved",
    "average_ranks",
    "completeness_ok",
    "decision_mondays",
    "evaluate_d13_scientific",
    "formation_return",
    "holding_return_for_symbol",
    "listing_age_ok",
    "n_from_eligible_counts",
    "no_post_t_close_selected_n",
    "quintile_labels",
    "refuse_protected_year_timestamp",
    "select_top_n",
    "sign_of_pooled_ic",
    "signed_practical_spread",
    "spearman_rank_ic",
    "temporal_gate",
    "top_minus_bottom_spread",
    "trailing_quote_volume",
    "two_sided_sign_flip_pvalue",
]
