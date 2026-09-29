"""Pairwise diagnostics. No 30-day percentiles, no episodes, no outcomes.

Principle readings are the constants in constants.py. This module does not
fit a tolerance to a result, and it does not rescale a series after seeing
the ratio.
"""
from __future__ import annotations

import math
from typing import Sequence

from .constants import (
    EVALUABILITY_DISAGREEMENT_FRACTION_MAX,
    MATERIAL_FEATURE_MIN_PAIRS,
    OI_SIGN_AGREEMENT_MIN_OUTSIDE_LOWEST_DECILE,
    OI_STRATUM_MIN_PAIRS,
    QUORUM_DISAGREEMENT_FRACTION_MAX,
    RANK_CORRELATION_MIN,
    SCALE_RATIO_ACCEPT_MAX,
    SCALE_RATIO_ACCEPT_MIN,
    SCALE_SUSPECT_RATIOS,
    SCALE_SUSPECT_RELATIVE_TOLERANCE,
    TAKER_INVERSION_SIGN_AGREEMENT_MAX,
    VENDOR_GAP_TAG,
)

COMPARED_FAMILIES = (
    "price_structure",
    "volume",
    "taker_flow",
    "oi",
)


def _finite_pair(gold, tardis) -> bool:
    return _finite(gold) and _finite(tardis)


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _percentile_sorted(sorted_values: Sequence[float], pct: float) -> float | None:
    """Empirical nearest-rank percentile. pct in (0, 100].

    index = ceil(pct/100 * n) - 1. Declared here so reports do not switch
    methods after the fact.
    """
    n = len(sorted_values)
    if n == 0:
        return None
    rank = math.ceil(pct / 100.0 * n)
    index = min(n - 1, max(0, rank - 1))
    return sorted_values[index]


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    num = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(math.fsum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(math.fsum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2:
        return None
    return pearson(_ranks(xs), _ranks(ys))


def numeric_diagnostics(pairs: Sequence[tuple[float | None, float | None]]) -> dict:
    """pairs are (signalbot, tardis). None means not evaluable, not zero."""
    both_null = 0
    gold_only = 0
    tardis_only = 0
    both = []
    for gold, tardis in pairs:
        g_ok = _finite(gold)
        t_ok = _finite(tardis)
        if g_ok and t_ok:
            both.append((float(gold), float(tardis)))
        elif not g_ok and not t_ok:
            both_null += 1
        elif g_ok:
            gold_only += 1
        else:
            tardis_only += 1
    abs_diff = sorted(abs(t - g) for g, t in both)
    signs_agree = sum(1 for g, t in both if _sign(g) == _sign(t))
    sign_differ = [(g, t) for g, t in both if _sign(g) != _sign(t)]
    ratios = [t / g for g, t in both if g != 0]
    ratios_sorted = sorted(ratios)
    return {
        "pair_count": len(pairs),
        "comparable_count": len(both),
        "both_null": both_null,
        "gold_only_evaluable": gold_only,
        "tardis_only_evaluable": tardis_only,
        "null_agreement_count": both_null + len(both),
        "null_agreement_fraction": (
            (both_null + len(both)) / len(pairs) if pairs else None
        ),
        "median_absolute_difference": _percentile_sorted(abs_diff, 50),
        "p90_absolute_difference": _percentile_sorted(abs_diff, 90),
        "p95_absolute_difference": _percentile_sorted(abs_diff, 95),
        "p99_absolute_difference": _percentile_sorted(abs_diff, 99),
        "maximum_absolute_difference": abs_diff[-1] if abs_diff else None,
        "sign_agreement_count": signs_agree,
        "sign_agreement_fraction": (signs_agree / len(both) if both else None),
        "sign_disagreement_count": len(sign_differ),
        "spearman": spearman([g for g, _ in both], [t for _, t in both]),
        "pearson": pearson([g for g, _ in both], [t for _, t in both]),
        "median_scale_ratio_tardis_over_gold": _percentile_sorted(ratios_sorted, 50),
        "evaluable_disagreement_count": gold_only + tardis_only,
    }


def magnitude_strata(pairs: Sequence[tuple[float | None, float | None]]) -> dict:
    """OI sign agreement in bins of the Signalbot absolute-change distribution.

    Edges are the empirical 10th, 50th, and 90th percentiles of |gold| on
    comparable pairs. The lowest decile is reported separately and is not
    hidden. No epsilon is applied.
    """
    both = [(float(g), float(t)) for g, t in pairs if _finite_pair(g, t)]
    magnitudes = sorted(abs(g) for g, _ in both)
    p10 = _percentile_sorted(magnitudes, 10)
    p50 = _percentile_sorted(magnitudes, 50)
    p90 = _percentile_sorted(magnitudes, 90)
    bins = {
        "lowest_10pct": [],
        "10_to_50pct": [],
        "50_to_90pct": [],
        "top_10pct": [],
    }
    if p10 is None:
        return {"edges": None, "strata": {k: _stratum([]) for k in bins}}
    for gold, tardis in both:
        mag = abs(gold)
        if mag <= p10:
            bins["lowest_10pct"].append((gold, tardis))
        elif mag <= p50:
            bins["10_to_50pct"].append((gold, tardis))
        elif mag <= p90:
            bins["50_to_90pct"].append((gold, tardis))
        else:
            bins["top_10pct"].append((gold, tardis))
    return {
        "edges": {"p10_abs_gold": p10, "p50_abs_gold": p50, "p90_abs_gold": p90},
        "strata": {name: _stratum(rows) for name, rows in bins.items()},
        "label": "SAMPLE-DAY magnitude strata of the Signalbot reference. Not a 30-day percentile.",
    }


def _stratum(rows: Sequence[tuple[float, float]]) -> dict:
    if not rows:
        return {"count": 0, "sign_agreement_fraction": None, "sign_disagreement_count": 0}
    agree = sum(1 for g, t in rows if _sign(g) == _sign(t))
    return {
        "count": len(rows),
        "sign_agreement_fraction": agree / len(rows),
        "sign_disagreement_count": len(rows) - agree,
    }


def tail_overlap(pairs: Sequence[tuple[float | None, float | None]], fraction: float) -> dict:
    """Overlap of extreme sets inside the sample. Not a production percentile."""
    both = [(float(g), float(t)) for g, t in pairs if _finite_pair(g, t)]
    n = len(both)
    k = max(1, math.floor(fraction * n)) if n else 0
    if k == 0:
        return {"n": 0, "k": 0, "top_overlap": None, "bottom_overlap": None}

    def index_set(values: list[float], *, largest: bool) -> set[int]:
        order = sorted(range(n), key=lambda i: values[i], reverse=largest)
        return set(order[:k])

    gold = [g for g, _ in both]
    tardis = [t for _, t in both]
    top_g = index_set(gold, largest=True)
    top_t = index_set(tardis, largest=True)
    bot_g = index_set(gold, largest=False)
    bot_t = index_set(tardis, largest=False)
    return {
        "n": n,
        "k": k,
        "fraction": fraction,
        "top_overlap": len(top_g & top_t) / k,
        "bottom_overlap": len(bot_g & bot_t) / k,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
    }


def scale_failure(median_ratio: float | None) -> str | None:
    if median_ratio is None or not math.isfinite(median_ratio) or median_ratio <= 0:
        return None
    for suspect in SCALE_SUSPECT_RATIOS:
        if abs(median_ratio - suspect) / suspect <= SCALE_SUSPECT_RELATIVE_TOLERANCE:
            return "METADATA_SCALE_SUSPECT"
    if not (SCALE_RATIO_ACCEPT_MIN <= median_ratio <= SCALE_RATIO_ACCEPT_MAX):
        return "SYSTEMATIC_SCALE_ERROR"
    return None


def gap_tagged(tags: Sequence[str] | None) -> bool:
    return bool(tags) and (VENDOR_GAP_TAG in tags or "SIGNALBOT_DATA_GAP" in tags)


def evaluate_principles(feature_stats: dict, *, oi_strata: dict | None,
                        evaluable_disagreement_fraction: float | None,
                        quorum_disagreement_fraction: float | None,
                        unit_mismatch_count: int,
                        post_hoc_transform_applied: bool) -> list[dict]:
    """Return principle findings. Empty means none of the rejection rules fired.

    `feature_stats` maps a feature name to the dict from numeric_diagnostics.
    """
    findings = []
    if unit_mismatch_count:
        findings.append({
            "code": "PERSISTENT_UNIT_MISMATCH",
            "class": "reject",
            "detail": f"{unit_mismatch_count} comparable buckets disagree on unit",
        })
    taker = feature_stats.get("taker_delta_notional_usd") or {}
    if (taker.get("comparable_count") or 0) >= MATERIAL_FEATURE_MIN_PAIRS:
        # Inversion is judged on the whole comparable set's sign agreement
        # only when it is at or below the pre-declared inversion ceiling.
        # A mild clock disagreement stays above that ceiling.
        fraction = taker.get("sign_agreement_fraction")
        if fraction is not None and fraction <= TAKER_INVERSION_SIGN_AGREEMENT_MAX:
            findings.append({
                "code": "PERSISTENT_TAKER_INVERSION",
                "class": "reject",
                "detail": f"taker sign agreement {fraction}",
            })
    for name in ("volume_notional_usd", "taker_delta_notional_usd"):
        stats = feature_stats.get(name) or {}
        failure = scale_failure(stats.get("median_scale_ratio_tardis_over_gold"))
        if failure:
            findings.append({
                "code": failure,
                "class": "reject",
                "detail": f"{name} median ratio {stats.get('median_scale_ratio_tardis_over_gold')}",
            })
    if (evaluable_disagreement_fraction is not None
            and evaluable_disagreement_fraction > EVALUABILITY_DISAGREEMENT_FRACTION_MAX):
        findings.append({
            "code": "FREQUENT_EVALUABILITY_DISAGREEMENT",
            "class": "reject",
            "detail": str(evaluable_disagreement_fraction),
        })
    if (quorum_disagreement_fraction is not None
            and quorum_disagreement_fraction > QUORUM_DISAGREEMENT_FRACTION_MAX):
        findings.append({
            "code": "CONSENSUS_QUORUM_DISAGREEMENT",
            "class": "reject",
            "detail": str(quorum_disagreement_fraction),
        })
    for name, stats in feature_stats.items():
        n = stats.get("comparable_count") or 0
        rho = stats.get("spearman")
        if n >= MATERIAL_FEATURE_MIN_PAIRS and rho is not None and rho < RANK_CORRELATION_MIN:
            findings.append({
                "code": "MATERIAL_REORDER",
                "class": "reject",
                "detail": f"{name} spearman {rho}",
            })
    if oi_strata and oi_strata.get("strata"):
        for stratum_name, stratum in oi_strata["strata"].items():
            if stratum_name == "lowest_10pct":
                continue
            count = stratum.get("count") or 0
            fraction = stratum.get("sign_agreement_fraction")
            if (count >= OI_STRATUM_MIN_PAIRS and fraction is not None
                    and fraction < OI_SIGN_AGREEMENT_MIN_OUTSIDE_LOWEST_DECILE):
                findings.append({
                    "code": "OI_SIGN_DISAGREEMENT_OUTSIDE_TINY",
                    "class": "reject",
                    "detail": f"{stratum_name} sign agreement {fraction} n={count}",
                })
    if post_hoc_transform_applied:
        findings.append({
            "code": "POST_HOC_TRANSFORM_REQUIRED",
            "class": "reject",
            "detail": "a corrective scale or sign flip was applied",
        })
    return findings


def overall_decision(*, comparison_performed: bool, findings: Sequence[dict],
                     repair_findings: Sequence[dict] = ()) -> str:
    if not comparison_performed:
        return "INCOMPLETE_NO_SIGNALBOT_EXPORT"
    if any(item.get("class") == "reject" for item in findings):
        return "REJECT_TARDIS_FOR_CURRENT_REPLAY"
    if repair_findings:
        return "REPAIR_AND_REPEAT_FREE_VALIDATION"
    return "PROCEED_TO_30D_OVERLAP_VALIDATION"
