"""One official run of LEVEL_REJECTION_MEMORY_V1.

Reads frozen predictor scales from the preflight file. Writes the result once.
Refuses to overwrite an existing result file. Does not edit LEVEL_TOUCH_DEGRADATION_V1.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import ZONE_HALF_PRIMARY
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import claim, constants as K
from .hits import annotate
from .inference import band_rates, lpm_effect, rate_diff, slice_pairs
from .pairs import analysis_pairs

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "docs" / "research" / "LEVEL_REJECTION_MEMORY_V1_PREFLIGHT.json"
DESIGN = ROOT / "docs" / "research" / "LEVEL_REJECTION_MEMORY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_REJECTION_MEMORY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_REJECTION_MEMORY_V1_RESULT.md"


def _r(x, n=6):
    if x is None:
        return None
    return round(float(x), n)


def _ci(ci):
    if not ci:
        return None
    return [_r(ci[0]), _r(ci[1])]


def _design_sha() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(DESIGN.relative_to(ROOT))],
        cwd=ROOT, text=True).strip()


def _load_scales() -> dict:
    blob = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    scales = blob["real"]["scales"]
    for key in ("speed_mean", "speed_sd", "linear_mean", "linear_sd", "gap_mean", "gap_sd",
                "overshoot_mean", "overshoot_sd", "speed_q33", "speed_q66"):
        if key not in scales:
            raise RuntimeError(f"preflight scales missing {key}")
    return scales


def _cell(pairs, scales, **kwargs) -> dict:
    out = lpm_effect(pairs, scales, **kwargs)
    return {**out, "coef": _r(out["coef"]), "ci95": _ci(out["ci95"])}


def _bucket_cell(pairs, scales, endpoint: str) -> dict:
    out = rate_diff(pairs, scales, endpoint=endpoint)
    return {**out, "coef": _r(out["coef"]), "ci95": _ci(out["ci95"])}


def _pp(x) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * x:+.1f} pp"


def _interval(ci) -> str:
    if not ci:
        return "not computable"
    return f"{100.0 * ci[0]:+.1f}..{100.0 * ci[1]:+.1f} pp"


def _wording(primary: dict) -> str:
    coef = primary.get("coef")
    ci = primary.get("ci95")
    n = primary.get("n") or 0
    if not claim.l2_allowed(n, ci):
        return (f"Мало данных для строки L2 (N={n}). Оценка коэффициента "
                f"{_pp(coef)} ({_interval(ci)}) остаётся в записи и не формулируется как утверждение.")
    return (
        "В истории структурных уровней BTC, которые ранее дали REJECT_FIRST и позже были протестированы "
        "снова (PDH/PDL, PWH/PWL, PMH/PML; Binance USD-M, 2020–2024), более быстрый предыдущий rejection "
        f"на 1 SD по −log(числа 5m баров до reject-барьера) был связан с отличием частоты BREAK_FIRST "
        f"на следующем независимом касании на {_pp(coef)} после выравнивания по номеру следующего касания, "
        "типу уровня, стороне подхода, терцилю волатильности, году и логарифму ожидания после rejection "
        f"(N={n}; 95% интервал {_interval(ci)}). Это частота в когорте уровней с наблюдавшимся rejection "
        "и последующим тестом, не текущая вероятность пробоя и не причинное усиление уровня."
    )


def _sentence(primary: dict) -> str:
    return (
        "Among structural BTC levels whose previous independent touch was REJECT_FIRST and that were "
        f"tested again, one SD faster prior rejection (frozen −log bars to the reject barrier) lined up "
        f"with a {_pp(primary.get('coef'))} difference in the next touch's 4h BREAK_FIRST frequency "
        f"after adjustment for touch ordinal, family, side, volatility tercile, year and log wait "
        f"(N={primary.get('n')}, 95% {_interval(primary.get('ci95'))})."
    )


def _limitations() -> str:
    return (
        "The cohort is conditional on two events: the previous independent touch was REJECT_FIRST, "
        "and the same zone was later touched again. The estimate is about levels with an observed "
        "rejection that were retested. It is not a causal effect of a strong rejection on every level. "
        "Touch number already predicts BREAK_FIRST in LEVEL_TOUCH_DEGRADATION_V1, so the primary "
        "coefficient is the one that still adjusts for the next touch's bucket. Several pairs can "
        "share a level; day and week pairs are clustered on the product week of the next touch, and "
        "month pairs on the episode. That does not model every shared path. A 5m bar that hits both "
        "barriers is dropped rather than ordered. The sample is one venue and one symbol, 2020–2024, "
        "on a surface already exposed for level research. A historical frequency in this cohort is "
        "not a current probability."
    )


def run() -> dict:
    if RESULT_JSON.exists():
        raise SystemExit(f"refusing to overwrite {RESULT_JSON.name}")
    scales = _load_scales()
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    real = annotate(bars.high, bars.low, built["touches"])
    control_touches = annotate(bars.high, bars.low, built["control_touches"])
    pairs, drops = analysis_pairs(real)
    control, control_drops = analysis_pairs(control_touches)

    primary = _cell(pairs, scales, spec="full", which="speed", endpoint="BREAK")
    cells = {
        "1_primary_break": primary,
        "2_reject": _cell(pairs, scales, spec="full", which="speed", endpoint="REJECT"),
        "3_neither": _cell(pairs, scales, spec="full", which="speed", endpoint="NEITHER"),
        "4_break_without_touch_ordinal": _cell(pairs, scales, spec="no_touch", which="speed", endpoint="BREAK"),
        "5_break_without_gap": _cell(pairs, scales, spec="no_gap", which="speed", endpoint="BREAK"),
        "6_bucket_break_fast_minus_slow": _bucket_cell(pairs, scales, "BREAK"),
        "7_bucket_reject_fast_minus_slow": _bucket_cell(pairs, scales, "REJECT"),
        "8_bucket_neither_fast_minus_slow": _bucket_cell(pairs, scales, "NEITHER"),
        "9_linear_speed_break": _cell(pairs, scales, spec="full", which="linear", endpoint="BREAK"),
        "10_overshoot_break": _cell(pairs, scales, spec="full", which="overshoot", endpoint="BREAK"),
    }
    years = []
    for year in K.YEARS:
        cell = _cell(slice_pairs(pairs, year=year), scales, spec="year", which="speed", endpoint="BREAK")
        cells[f"year_{year}"] = cell
        years.append(cell)
    for fam in K.FAMILIES:
        cells[f"family_{fam}"] = _cell(slice_pairs(pairs, family=fam), scales, spec="family",
                                       which="speed", endpoint="BREAK")
    cells["side_resistance"] = _cell(slice_pairs(pairs, side=1), scales, spec="side",
                                     which="speed", endpoint="BREAK")
    cells["side_support"] = _cell(slice_pairs(pairs, side=-1), scales, spec="side",
                                  which="speed", endpoint="BREAK")
    cells["bucket_2"] = _cell(slice_pairs(pairs, bucket="2"), scales, spec="bucket",
                              which="speed", endpoint="BREAK")
    cells["bucket_3plus"] = _cell(slice_pairs(pairs, bucket="3+"), scales, spec="bucket",
                                  which="speed", endpoint="BREAK")
    control_primary = _cell(control, scales, spec="full", which="speed", endpoint="BREAK")
    cells["23_control_primary"] = control_primary
    control_years = []
    for year in K.YEARS:
        cell = _cell(slice_pairs(control, year=year), scales, spec="year", which="speed", endpoint="BREAK")
        cells[f"control_year_{year}"] = cell
        control_years.append(cell)

    n = len(pairs)
    by_year = Counter(p["year"] for p in pairs)
    by_family = Counter(p["family"] for p in pairs)
    by_side = Counter(p["side"] for p in pairs)
    by_bucket = Counter(p["next_bucket"] for p in pairs)
    clusters = len({p["cluster"] for p in pairs})
    max_year_share = max(by_year.values()) / n if n else 1.0
    max_family_share = max(by_family.values()) / n if n else 1.0
    flag = claim.integration_candidate(
        primary, years, control_primary,
        max_year_share=max_year_share, max_family_share=max_family_share, clusters=clusters)
    bands = band_rates(pairs, scales)
    result = {
        "unit": K.UNIT,
        "dependency": {"unit": K.DEPENDENCY_UNIT, "pr": K.DEPENDENCY_PR, "sha": K.DEPENDENCY_SHA},
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "method_before_outcome": _design_sha(),
        "surface": "CORE_BTC_BINANCE_V0",
        "n_analysis_pairs": n,
        "drops": drops,
        "control_drops": control_drops,
        "control_n": len(control),
        "clusters": clusters,
        "by_year": {str(y): int(by_year[y]) for y in K.YEARS},
        "by_family": {fam: int(by_family[fam]) for fam in K.FAMILIES},
        "by_side": {"resistance": int(by_side[1]), "support": int(by_side[-1])},
        "by_next_bucket": {"2": int(by_bucket["2"]), "3+": int(by_bucket["3+"])},
        "max_year_share": _r(max_year_share),
        "max_family_share": _r(max_family_share),
        "bands": bands,
        "cells": cells,
        "n_contrasts": K.N_CONTRASTS,
        "integration": flag,
        "product_integration_candidate": "YES" if flag["candidate"] else "NO",
        "near_zero_reading": claim.both_near_zero(primary.get("coef"), primary.get("ci95")),
        "limitations": _limitations(),
        "evidence_summary": _sentence(primary),
        "claim_decision": {
            "level": "L2" if claim.l2_allowed(primary.get("n") or 0, primary.get("ci95")) else "L2-withheld",
            "wording": _wording(primary),
            "l3": "not permitted",
            "l4": "not permitted",
        },
    }
    if len(cells) != K.N_CONTRASTS:
        raise RuntimeError(f"cell count {len(cells)} != {K.N_CONTRASTS}")
    RESULT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD.write_text(_md(result), encoding="utf-8")
    return result


def _md(result: dict) -> str:
    p = result["cells"]["1_primary_break"]
    lines = [
        "# LEVEL_REJECTION_MEMORY_V1 — result",
        "",
        f"Dependency: `{result['dependency']['unit']}` / PR #{result['dependency']['pr']} / "
        f"`{result['dependency']['sha']}`.",
        f"Design note commit `{result['method_before_outcome']}`.",
        "Tracks: STRUCTURE, PRODUCT_EVIDENCE. One run. Not a rescore of the dependency unit.",
        "",
        "## estimate",
        "",
        result["evidence_summary"],
        "",
        f"Primary coefficient (cell 1): {_pp(p.get('coef'))}, 95% {_interval(p.get('ci95'))}, "
        f"N={p.get('n')}, clusters={p.get('clusters')}.",
        "",
        "## decomposition",
        "",
        _line("REJECT_FIRST", result["cells"]["2_reject"]),
        _line("NEITHER", result["cells"]["3_neither"]),
        "",
        "Speed tertiles (slow / mid / fast), crude next-touch shares:",
        "",
    ]
    for name in ("slow", "mid", "fast"):
        b = result["bands"][name]
        n = b["n"]
        def share(k, _n=n, _b=b):
            if not _n:
                return "n/a"
            return f"{100.0 * _b[k] / _n:.1f}%"
        lines.append(
            f"- {name}: N={n}, BREAK {share('BREAK')}, REJECT {share('REJECT')}, NEITHER {share('NEITHER')}")
    lines += [
        "",
        f"Fast minus slow: BREAK {_pp(result['cells']['6_bucket_break_fast_minus_slow'].get('coef'))} "
        f"({_interval(result['cells']['6_bucket_break_fast_minus_slow'].get('ci95'))}).",
        "",
        "## uncertainty",
        "",
        "95% percentile interval from 2000 resamples of the predeclared cluster "
        "(product week of the next touch for day and week levels; episode id for month levels), "
        f"seed {K.BOOT_SEED}. Not a p-value. The claim sentence cites cell 1 only.",
        "",
        "## touch ordinal and time since rejection",
        "",
        _line("without touch-ordinal control", result["cells"]["4_break_without_touch_ordinal"]),
        _line("without log-gap control", result["cells"]["5_break_without_gap"]),
        _line("inside next-touch bucket 2", result["cells"]["bucket_2"]),
        _line("inside next-touch bucket 3+", result["cells"]["bucket_3plus"]),
        "",
        "## stability",
        "",
        "| slice | N | coef | 95% |",
        "|---|---:|---:|---|",
    ]
    for year in K.YEARS:
        c = result["cells"][f"year_{year}"]
        lines.append(f"| {year} | {c['n']} | {_pp(c.get('coef'))} | {_interval(c.get('ci95'))} |")
    for fam in K.FAMILIES:
        c = result["cells"][f"family_{fam}"]
        lines.append(f"| {fam} | {c['n']} | {_pp(c.get('coef'))} | {_interval(c.get('ci95'))} |")
    for name in ("side_resistance", "side_support"):
        c = result["cells"][name]
        lines.append(f"| {name} | {c['n']} | {_pp(c.get('coef'))} | {_interval(c.get('ci95'))} |")
    lines += [
        "",
        f"Busiest year share {100.0 * result['max_year_share']:.1f}%. "
        f"Busiest family share {100.0 * result['max_family_share']:.1f}%.",
        "",
        "## sensitivity",
        "",
        _line("linear −bars, per 1 SD faster", result["cells"]["9_linear_speed_break"]),
        _line("overshoot, per 1 SD deeper", result["cells"]["10_overshoot_break"]),
        "",
        "## falsification",
        "",
        _line("pseudo-level primary", result["cells"]["23_control_primary"]),
    ]
    for year in K.YEARS:
        c = result["cells"][f"control_year_{year}"]
        lines.append(f"- control {year}: N={c['n']}, {_pp(c.get('coef'))} ({_interval(c.get('ci95'))}).")
    lines += [
        "",
        "## information",
        "",
        f"Analysis pairs N={result['n_analysis_pairs']}. Clusters={result['clusters']}. "
        f"Next-touch buckets {result['by_next_bucket']}. "
        f"Ambiguous next touches excluded: {result['drops']['ambiguous']}.",
        "",
        "## limitations",
        "",
        result["limitations"],
        "",
        "## search exposure",
        "",
        f"{result['n_contrasts']} predeclared contrasts. Primary multiplicity family size 1. "
        "No contrast was added after the rates were read.",
        "",
        "## method before outcome",
        "",
        f"`{result['method_before_outcome']}` — `docs/research/LEVEL_REJECTION_MEMORY_V1_DESIGN.md`.",
        "",
        "## evidence summary",
        "",
        result["evidence_summary"],
        "",
        "## claim decision",
        "",
        f"Ladder: `{result['claim_decision']['level']}`. "
        f"PRODUCT_INTEGRATION_CANDIDATE = {result['product_integration_candidate']}.",
        "",
        result["claim_decision"]["wording"],
        "",
        "Not integrated. No `/levels` change, no findings-registry edit, no deploy.",
        "",
        "## successors not run",
        "",
        "- LEVEL_APPROACH_STATE_V1",
        "- LEVEL_CONFLUENCE_V1",
        "",
    ]
    return "\n".join(lines)


def _line(label: str, cell: dict) -> str:
    return (f"- {label}: {_pp(cell.get('coef'))} ({_interval(cell.get('ci95'))}), "
            f"N={cell.get('n')}, clusters={cell.get('clusters')}.")


def main() -> None:
    result = run()
    cell = result["cells"]["1_primary_break"]
    print(json.dumps({
        "coef": cell.get("coef"),
        "candidate": result["product_integration_candidate"],
        "claim": result["claim_decision"]["level"],
        "n": result["n_analysis_pairs"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
