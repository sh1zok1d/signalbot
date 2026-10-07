"""One official run of LEVEL_TOUCH_DEGRADATION_V1.

Reads the design note's committed preflight for tercile edges. Writes the result once.
Refuses to overwrite an existing result file.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from . import claim, constants as K, inference, outcomes
from .build import build_population
from .data import load_discovery_bars

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_PREFLIGHT.json"
DESIGN = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_RESULT.md"


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


def _edges(which: str) -> tuple[float, float]:
    payload = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    key = "real" if which == "primary" else "sensitivity_zone_real"
    lo, hi = payload[key]["sigma_tercile_edges"]
    if lo is None or hi is None:
        raise RuntimeError(f"frozen tercile edges missing for {which}")
    return float(lo), float(hi)


def _score(bars, touches, horizon: int, fraction: float) -> list[dict]:
    return outcomes.attach(bars.high, bars.low, touches, horizon=horizon, barrier_fraction=fraction)


def _pack_contrast(got: dict) -> dict:
    return {
        "delta_touch2": _r(got.get("d2")),
        "delta_touch3": _r(got.get("d3")),
        "ci95_touch2": _ci(got.get("ci2")),
        "ci95_touch3": _ci(got.get("ci3")),
        "p_touch1_on_touch2_strata": _r(got.get("p1_for_2")),
        "p_touch2_standardized": _r(got.get("p2")),
        "p_touch1_on_touch3_strata": _r(got.get("p1_for_3")),
        "p_touch3_standardized": _r(got.get("p3")),
        "retained_touch1_share_touch2": _r(got.get("share2")),
        "retained_touch1_share_touch3": _r(got.get("share3")),
        "bootstrap_valid": got.get("valid"),
        "week_clusters": got.get("weeks"),
    }


def _slice_contrasts(rows, edges, *, standardized: bool) -> dict:
    got = inference.contrasts(rows, edges, standardized=standardized)
    return _pack_contrast(got)


def _by(rows, edges, field: str, values) -> dict:
    out = {}
    for value in values:
        sub = [r for r in rows if r[field] == value]
        out[str(value)] = {
            **_slice_contrasts(sub, edges, standardized=False),
            "n": {b: sum(1 for r in sub if r["bucket"] == b) for b in K.TOUCH_BUCKETS},
        }
    return out


def _spec(bars, touches, edges, *, horizon: int, fraction: float, standardized_edges=None) -> dict:
    scored = _score(bars, touches, horizon, fraction)
    rows = inference.analysis_rows(scored)
    use_edges = edges if standardized_edges is None else standardized_edges
    return {
        "counts": inference.bucket_counts(scored),
        "standardized": _slice_contrasts(rows, use_edges, standardized=True),
        "crude": _slice_contrasts(rows, use_edges, standardized=False),
        "n_analysis": len(rows),
        "rows_meta": _meta(rows),
        "_rows": rows,
    }


def _meta(rows: list[dict]) -> dict:
    if not rows:
        return {"weeks": 0, "max_year_share": None, "max_family_share_touch3": None,
                "year_n": {}, "family_n_touch3": {}}
    years = Counter(int(r["year"]) for r in rows)
    fam3 = Counter(r["family"] for r in rows if r["bucket"] == "3+")
    n3 = sum(fam3.values())
    year_n = {}
    for year in K.YEARS:
        sub = [r for r in rows if int(r["year"]) == year]
        year_n[year] = (
            sum(1 for r in sub if r["bucket"] == "1"),
            sum(1 for r in sub if r["bucket"] == "3+"),
        )
    return {
        "weeks": len({int(r["week"]) for r in rows}),
        "max_year_share": max(years.values()) / len(rows),
        "max_family_share_touch3": (max(fam3.values()) / n3) if n3 else None,
        "year_n": year_n,
        "family_n_touch3": dict(fam3),
    }


def _rates(counts: dict) -> dict:
    out = {}
    for bucket, rec in counts.items():
        n = rec["analysis"]
        out[bucket] = {
            "n_break": rec["BREAK"],
            "n_reject": rec["REJECT"],
            "n_neither": rec["NEITHER"],
            "n_ambiguous": rec["AMBIGUOUS"],
            "n_analysis": n,
            "p_break": _r(rec["BREAK"] / n) if n else None,
            "p_reject": _r(rec["REJECT"] / n) if n else None,
            "p_neither": _r(rec["NEITHER"] / n) if n else None,
        }
    return out


def _pct(x):
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def _pp(x):
    if x is None:
        return "n/a"
    return f"{100 * x:+.1f} pp"


def _interval(ci):
    if not ci:
        return "not computable"
    return f"{100 * ci[0]:+.1f}..{100 * ci[1]:+.1f} pp"


def _sentence(rates, std) -> str:
    p = rates
    d2, d3 = std["delta_touch2"], std["delta_touch3"]
    ci2, ci3 = std["ci95_touch2"], std["ci95_touch3"]
    n1 = p["1"]["n_analysis"]
    n2 = p["2"]["n_analysis"]
    n3 = p["3+"]["n_analysis"]
    thin = []
    if not claim.l2_line_allowed(n1, n2, ci2):
        thin.append(f"touch 2 мало данных (N={n2})")
    if not claim.l2_line_allowed(n1, n3, ci3):
        thin.append(f"touch 3+ мало данных (N={n3})")
    thin_txt = (" " + "; ".join(thin) + ".") if thin else ""
    return (
        f"Among structural BTC levels that reached the touch, the 2020–2024 historical "
        f"BREAK_FIRST frequency was {_pct(p['1']['p_break'])} on touch 1 (N={n1}), "
        f"{_pct(p['2']['p_break'])} on touch 2 (N={n2}) and {_pct(p['3+']['p_break'])} on touch 3+ "
        f"(N={n3}); the touch-1-standardized differences were {_pp(d2)} "
        f"(95% {_interval(ci2)}) and {_pp(d3)} (95% {_interval(ci3)}).{thin_txt}"
    )


def _wording(rates, std) -> dict:
    """Exact L2 sentences. Absent when the predeclared information rule fails."""
    out = {}
    n1 = rates["1"]["n_analysis"]
    for key, bucket, n in (("touch2", "2", rates["2"]["n_analysis"]),
                           ("touch3", "3+", rates["3+"]["n_analysis"])):
        delta = std["delta_touch2" if key == "touch2" else "delta_touch3"]
        ci = std["ci95_touch2" if key == "touch2" else "ci95_touch3"]
        if delta is None or not claim.l2_line_allowed(n1, n, ci):
            out[key] = None
            continue
        lo, hi = ci
        out[key] = (
            f"В истории независимых касаний заранее известных структурных уровней BTC "
            f"(PDH/PDL, PWH/PWL, PMH/PML; Binance USD-M, 2020–2024) среди уровней, дошедших "
            f"до этого теста, BREAK_FIRST за 4ч был в {rates[bucket]['p_break']:.1%} "
            f"против {rates['1']['p_break']:.1%} при первом касании "
            f"({100 * delta:+.1f} п.п. после выравнивания по типу уровня, стороне подхода и "
            f"терцилю волатильности; N₁={n1}, N={n}; 95% интервал {100 * lo:+.1f}..{100 * hi:+.1f} п.п.). "
            f"Это частота в той когорте, не текущая вероятность пробоя."
        )
    return out


def _md(result: dict) -> str:
    p = result["primary"]
    std = p["standardized"]
    rates = p["rates"]
    lines = [
        "# LEVEL_TOUCH_DEGRADATION_V1 — result",
        "",
        f"Design note commit `{result['method_before_outcome']}`.",
        f"Tracks: {', '.join(result['tracks'])}. Claim ceiling recorded below. One run.",
        "",
        "## estimate",
        "",
        result["evidence_summary"],
        "",
        "| bucket | N | BREAK_FIRST | REJECT_FIRST | NEITHER | ambiguous (excluded) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket in K.TOUCH_BUCKETS:
        r = rates[bucket]
        lines.append(
            f"| {bucket} | {r['n_analysis']} | {_pct(r['p_break'])} | {_pct(r['p_reject'])} | "
            f"{_pct(r['p_neither'])} | {r['n_ambiguous']} |"
        )
    lines += [
        "",
        f"Standardized Δ(touch 2 − touch 1) = {_pp(std['delta_touch2'])}, 95% {_interval(std['ci95_touch2'])}, "
        f"retained touch-1 weight {std['retained_touch1_share_touch2']}.",
        f"Standardized Δ(touch 3+ − touch 1) = {_pp(std['delta_touch3'])}, 95% {_interval(std['ci95_touch3'])}, "
        f"retained touch-1 weight {std['retained_touch1_share_touch3']}.",
        f"Crude companions: Δ2 {_pp(p['crude']['delta_touch2'])} ({_interval(p['crude']['ci95_touch2'])}), "
        f"Δ3 {_pp(p['crude']['delta_touch3'])} ({_interval(p['crude']['ci95_touch3'])}).",
        "",
        "## uncertainty",
        "",
        "95% percentile interval from 2000 resamples of the product week of the touch, seed 20261007. "
        "Not a p-value and not a Holm-adjusted interval. Two primary contrasts were predeclared; "
        "the intervals are unadjusted and the claim sentence cites only those two.",
        "",
        "## information",
        "",
        f"Analysis N = {p['n_analysis']} (ambiguous same-bar events excluded). "
        f"Week clusters = {p['meta']['weeks']}. "
        f"Feature-eligible preflight N = {result['preflight_feature_eligible']}. "
        f"Planning MDE at rate 0.5 and DEFF 1.25 was about 6 pp; the week-cluster upper bound "
        f"(DEFF = events/weeks) was about 21 pp. Those are amounts of information, not gates.",
        "",
        "## stability",
        "",
        "| year | N1 | N2 | N3+ | crude Δ2 | crude Δ3 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for year, rec in p["by_year"].items():
        lines.append(
            f"| {year} | {rec['n']['1']} | {rec['n']['2']} | {rec['n']['3+']} | "
            f"{_pp(rec['delta_touch2'])} | {_pp(rec['delta_touch3'])} |"
        )
    lines += [
        "",
        f"Busiest year share of analysis events: {p['meta']['max_year_share']:.1%}. "
        f"Busiest family share of touch 3+: {p['meta']['max_family_share_touch3']:.1%}.",
        "",
        "Family crude Δ3: "
        + ", ".join(f"{name} {_pp(rec['delta_touch3'])} (N3={rec['n']['3+']})"
                    for name, rec in p["by_family"].items())
        + ".",
        "",
        "Approach-side crude Δ3: "
        + ", ".join(f"{name} {_pp(rec['delta_touch3'])}" for name, rec in p["by_side"].items())
        + ".",
        "",
        "## falsification",
        "",
        f"Pseudo-level standardized Δ2 {_pp(result['control']['standardized']['delta_touch2'])} "
        f"({_interval(result['control']['standardized']['ci95_touch2'])}), "
        f"Δ3 {_pp(result['control']['standardized']['delta_touch3'])} "
        f"({_interval(result['control']['standardized']['ci95_touch3'])}).",
        "",
        "Control crude Δ3 by year: "
        + ", ".join(f"{year} {_pp(rec['delta_touch3'])}"
                    for year, rec in result["control"]["by_year"].items())
        + ".",
        "",
        "## limitations",
        "",
        result["limitations"],
        "",
        "## search exposure",
        "",
        f"{K.N_CONTRASTS_TOTAL} predeclared contrasts. Primary multiplicity family size "
        f"{K.N_PRIMARY_CONTRASTS}. No contrast was added after the rates were read. "
        "Sensitivity and slices are descriptive and cannot replace contrasts 1 and 2.",
        "",
        "## sensitivity",
        "",
    ]
    for name, spec in result["sensitivity"].items():
        s = spec["standardized"]
        lines.append(
            f"- {name}: Δ2 {_pp(s['delta_touch2'])} ({_interval(s['ci95_touch2'])}), "
            f"Δ3 {_pp(s['delta_touch3'])} ({_interval(s['ci95_touch3'])}), "
            f"analysis N={spec['n_analysis']}."
        )
    lines += [
        "",
        "## method before outcome",
        "",
        f"`{result['method_before_outcome']}` — `docs/research/LEVEL_TOUCH_DEGRADATION_V1_DESIGN.md`.",
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
    ]
    for key, text in result["claim_decision"]["wording"].items():
        lines.append(f"- {key}: {text if text else 'no L2 line (information rule).'}")
    lines += [
        "",
        "Not integrated. No `/levels` change, no findings-registry edit, no deploy.",
        "",
        "## successors not run",
        "",
        "- LEVEL_REJECTION_MEMORY_V1",
        "- LEVEL_APPROACH_STATE_V1",
        "- LEVEL_CONFLUENCE_V1",
        "",
    ]
    return "\n".join(lines)


def run() -> dict:
    if RESULT_JSON.exists():
        raise SystemExit(f"result already exists: {RESULT_JSON}")
    bars = load_discovery_bars()
    primary_edges = _edges("primary")
    narrow_edges = _edges("zone")
    built = build_population(bars, K.ZONE_HALF_PRIMARY)
    narrow = build_population(bars, K.ZONE_HALF_SENSITIVITY)
    real = built["touches"]
    ctrl = built["control_touches"]
    primary = _spec(bars, real, primary_edges, horizon=K.HOLD_BARS_PRIMARY,
                    fraction=K.BARRIER_FRACTION_PRIMARY)
    rows = primary.pop("_rows")
    control = _spec(bars, ctrl, primary_edges, horizon=K.HOLD_BARS_PRIMARY,
                    fraction=K.BARRIER_FRACTION_PRIMARY)
    control.pop("_rows")
    zone = _spec(bars, narrow["touches"], narrow_edges, horizon=K.HOLD_BARS_PRIMARY,
                 fraction=K.BARRIER_FRACTION_PRIMARY)
    zone.pop("_rows")
    barrier = _spec(bars, real, primary_edges, horizon=K.HOLD_BARS_PRIMARY,
                    fraction=K.BARRIER_FRACTION_SENSITIVITY)
    barrier.pop("_rows")
    horizon = _spec(bars, real, primary_edges, horizon=K.HOLD_BARS_SENSITIVITY,
                    fraction=K.BARRIER_FRACTION_PRIMARY)
    horizon.pop("_rows")
    by_year = _by(rows, primary_edges, "year", K.YEARS)
    by_family = _by(rows, primary_edges, "family", K.FAMILIES)
    side_rows = {
        "resistance": _by([r for r in rows if r["side"] == 1], primary_edges, "side", [1]).get("1", {}),
        "support": _by([r for r in rows if r["side"] == -1], primary_edges, "side", [-1]).get("-1", {}),
    }
    # _by on an already filtered list still filters by side value. resistance side is +1.
    control_rows = inference.analysis_rows(_score(bars, ctrl, K.HOLD_BARS_PRIMARY, K.BARRIER_FRACTION_PRIMARY))
    control_year = _by(control_rows, primary_edges, "year", K.YEARS)
    meta = primary["rows_meta"]
    year_d3 = {int(y): rec["delta_touch3"] for y, rec in by_year.items()}
    year_n = {int(y): tuple(meta["year_n"][y]) for y in K.YEARS}
    flag = claim.integration_candidate(
        d2=primary["standardized"]["delta_touch2"],
        d3=primary["standardized"]["delta_touch3"],
        ci3=primary["standardized"]["ci95_touch3"],
        control_d3=control["standardized"]["delta_touch3"],
        control_ci3=control["standardized"]["ci95_touch3"],
        year_d3=year_d3,
        year_n=year_n,
        max_year_share=meta["max_year_share"],
        max_family_share_touch3=meta["max_family_share_touch3"],
        weeks=meta["weeks"],
    )
    rates = _rates(primary["counts"])
    pre = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    result = {
        "unit": K.UNIT,
        "tracks": list(K.TRACKS),
        "surface": K.SURFACE_ID,
        "method_before_outcome": _design_sha(),
        "primary_edges": list(primary_edges),
        "zone_sensitivity_edges": list(narrow_edges),
        "preflight_feature_eligible": pre["real"]["feature_eligible_n"],
        "primary": {
            "rates": rates,
            "counts": primary["counts"],
            "standardized": primary["standardized"],
            "crude": primary["crude"],
            "by_year": by_year,
            "by_family": by_family,
            "by_side": side_rows,
            "n_analysis": primary["n_analysis"],
            "meta": {
                "weeks": meta["weeks"],
                "max_year_share": _r(meta["max_year_share"]),
                "max_family_share_touch3": _r(meta["max_family_share_touch3"]),
            },
        },
        "control": {"standardized": control["standardized"], "rates": _rates(control["counts"]),
                    "by_year": control_year, "n_analysis": control["n_analysis"]},
        "sensitivity": {
            "zone_half_0.0003": {"standardized": zone["standardized"], "n_analysis": zone["n_analysis"],
                                 "rates": _rates(zone["counts"])},
            "barrier_fraction_1": {"standardized": barrier["standardized"], "n_analysis": barrier["n_analysis"],
                                   "rates": _rates(barrier["counts"])},
            "horizon_12": {"standardized": horizon["standardized"], "n_analysis": horizon["n_analysis"],
                           "rates": _rates(horizon["counts"])},
        },
        "integration": flag,
        "product_integration_candidate": "YES" if flag["candidate"] else "NO",
        "near_zero_reading": claim.both_near_zero(
            primary["standardized"]["delta_touch2"], primary["standardized"]["ci95_touch2"],
            primary["standardized"]["delta_touch3"], primary["standardized"]["ci95_touch3"]),
        "limitations": (
            "Touch 2 and touch 3+ exist only for levels that were retested, so the contrast is "
            "conditional on survival to that touch and is not a causal effect of the touch. "
            "Touches of the same level, and levels in the same week, are dependent; the interval "
            "resamples weeks and does not model a richer dependence. The same price path can "
            "host several structural levels; confluence merges those that share a zone, and the "
            "rest still share the week shock. A 5m bar that hits both barriers is dropped rather "
            "than ordered. The sample is one venue and one symbol, 2020–2024, on a surface already "
            "exposed for level research. The association can differ by family and by year. "
            "A historical frequency in this cohort is not a current probability."
        ),
    }
    result["evidence_summary"] = _sentence(rates, primary["standardized"])
    result["claim_decision"] = {
        "level": "L2" if any(claim.l2_line_allowed(
            rates["1"]["n_analysis"], rates[b]["n_analysis"],
            primary["standardized"]["ci95_touch2" if b == "2" else "ci95_touch3"])
            for b in ("2", "3+")) else "L2-withheld",
        "wording": _wording(rates, primary["standardized"]),
        "l3": "not permitted",
        "l4": "not permitted",
    }
    # Drop non-json bits already removed. Round meta shares inside primary for the md.
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    RESULT_JSON.write_text(text, encoding="utf-8")
    RESULT_MD.write_text(_md(result), encoding="utf-8")
    return result


def main() -> None:
    result = run()
    print(json.dumps({
        "delta2": result["primary"]["standardized"]["delta_touch2"],
        "delta3": result["primary"]["standardized"]["delta_touch3"],
        "candidate": result["product_integration_candidate"],
        "claim": result["claim_decision"]["level"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
