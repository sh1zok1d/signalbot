"""Markdown for RP4H_TREND_REGIME_MODULATION_V1 (frozen evaluator output)."""
from __future__ import annotations

from pathlib import Path

ROWS = (("rho_t1_b0", "RP4H partial | RET_4H, RV_4H — ranging tercile (T1, low TS)"),
        ("rho_t2_b0", "RP4H partial | RET_4H, RV_4H — middle tercile (T2)"),
        ("rho_t3_b0", "RP4H partial | RET_4H, RV_4H — trending tercile (T3, high TS)"),
        ("delta_b0", "**PRIMARY Δ = T3 − T1 (B0 controls)**"),
        ("rho_t1_b1", "T1 with local path (B1)"), ("rho_t3_b1", "T3 with local path (B1)"),
        ("delta_b1", "Δ with local path (B1)"), ("interaction_b0", "Continuous rank interaction RP4H × TS"))


def _f(v):
    return "—" if v is None else f"{v:+.5f}"


def write_markdown(r: dict, path: Path) -> None:
    L = [f"# {r['unit']}", "", f"**Route:** `{r['route']}`. **Clears the search bar:** {r['clears_search_bar']} "
         f"(z {_f(r['z_delta_b0'])} vs |z| ≥ {r['z_bar']:.3f}).",
         f"**Mode:** `{r['mode']}`. **Claim ceiling:** `{r['claim_ceiling']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.",
         f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`). **Evaluator digest:** `{r['evaluator_digest']}`.",
         f"**Surface:** {r['surface']}. N {r['support']['n']}, ISO weeks {r['support']['iso_weeks']}. TS tercile edges "
         f"{r['ts_tercile_edges'][0]:.4f} / {r['ts_tercile_edges'][1]:.4f}; N by tercile {r['support']['n_by_tercile']}.",
         "", "| Estimand | Point | 95 % interval | valid |", "|---|---|---|---|"]
    for k, lab in ROWS:
        c = r["intervals"][k]
        L.append(f"| {lab} | {_f(r['points'][k])} | [{_f(c['lo'])}, {_f(c['hi'])}] | {c['valid']}/{c['draws']} |")
    L += ["", "## Years (points)", "", "| year | N | T1 | T3 | Δ |", "|---|---|---|---|---|"]
    for y in r["years"]:
        L.append(f"| {y['year']} | {y['n']} | {_f(y['rho_t1_b0'])} | {_f(y['rho_t3_b0'])} | {_f(y['delta_b0'])} |")
    L += ["", "## RP4H quintiles within regime (description only; P(UP) / mean bp / median bp)", ""]
    for lab, rows in r["rp4h_quintiles_within_regime"].items():
        L.append(f"- {lab}: " + "; ".join(f"Q{b['bin']} {b['p_up']:.4f} / {b['mean_bp']:+.2f} / {b['median_bp']:+.2f}" for b in rows))
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
