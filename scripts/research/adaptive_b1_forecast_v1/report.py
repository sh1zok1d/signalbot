"""Markdown for ADAPTIVE_B1_FORECAST_V1 (frozen evaluator output)."""
from __future__ import annotations

from pathlib import Path


def _e(v, nd=7):
    return "—" if v is None else f"{v:+.{nd}f}"


def write_markdown(r: dict, path: Path) -> None:
    s = r["support"]
    L = [f"# {r['unit']}", "",
         f"**Routes:** P1 static B1 vs climatology `{r['routes']['P1_static_vs_climatology']}`; "
         f"P2 adaptive vs static `{r['routes']['P2_adaptive_vs_static']}`.",
         f"**Evidence class:** `{r['evidence_class']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No PnL or fees.",
         f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`). Fold manifest `{r['fold_manifest_sha256']}`. "
         f"Evaluator digest `{r['evaluator_digest']}`.",
         f"**Rows** {s['rows']} ({s['rows_by_era']}); outer rows {s['outer_rows']} in {s['n_outer_blocks']} blocks. "
         f"Outer P(UP) {r['outer_p_up']:.4f}.", "",
         "## Mean outer losses", "", "| model | Brier | log loss | AUROC | cal. intercept | cal. slope | ECE |", "|---|---|---|---|---|---|---|"]
    for k, v in r["mean_brier"].items():
        sec = r["secondary"][k]
        L.append(f"| {k} | {v:.7f} | {r['mean_logloss'][k]:.7f} | {sec['auroc']:.4f} | {sec['calibration']['intercept']:+.4f} | "
                 f"{sec['calibration']['slope']:+.3f} | {sec['reliability']['ece']:.4f} |")
    L += ["", "## Loss differences (a − b; negative = a better; ISO-week block 95 %)", "",
          "| pair | ΔBrier | 95 % | Δlog loss | 95 % |", "|---|---|---|---|---|"]
    for pair, d in r["brier_differences"].items():
        l = r["logloss_differences"][pair]
        L.append(f"| {pair} | {_e(d['point'])} | [{_e(d['lo'])}, {_e(d['hi'])}] | {_e(l['point'])} | [{_e(l['lo'])}, {_e(l['hi'])}] |")
    L += ["", "## Per era (diagnostic)", "", "| era | N | P(UP) | STATIC−CLIM ΔBrier | ADAPTIVE−STATIC ΔBrier |", "|---|---|---|---|---|"]
    for lab, e in r["per_era"].items():
        a, b = e["brier"]["STATIC-CLIM"], e["brier"]["ADAPTIVE-STATIC"]
        L.append(f"| {lab} | {e['n']} | {e['p_up']:.4f} | {_e(a['point'])} [{_e(a['lo'])}, {_e(a['hi'])}] | "
                 f"{_e(b['point'])} [{_e(b['lo'])}, {_e(b['hi'])}] |")
    sm = r["selector"]["summary"]
    L += ["", "## Selector behaviour", "", f"Share of outer blocks by selected memory: {sm['share']}; switches {sm['switches']}; "
          f"mean run length {sm['mean_run_length']:.2f} blocks.", "", "By year: " + "; ".join(f"{y} {v}" for y, v in sm["by_year"].items())]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
