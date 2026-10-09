"""Markdown for OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1 (frozen evaluator output)."""
from __future__ import annotations

from pathlib import Path

LABELS = {"raw": "Raw Spearman(OCC, R_1H)", "b0": "Secondary: partial | B0",
          "b0_ret1h": "Secondary: partial | B0 + RET_1H", "primary_b1": "**PRIMARY: partial | B1 = B0 + RET_1H + RET_15M**"}


def _f(v):
    return "—" if v is None else f"{v:+.6f}"


def write_markdown(r: dict, path: Path) -> None:
    L = [f"# {r['unit']}", "", f"**Route:** `{r['route']}`. **Status after the route:** `{r['status_after_route']}`.",
         f"**Evidence class:** `{r['evidence_class']}`. **Claim ceiling:** `{r['claim_ceiling']}`. "
         "`PRODUCT_INTEGRATION_CANDIDATE = NO`.",
         f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`), frozen before this read. "
         f"**Evaluator digest:** `{r['evaluator_digest']}`.",
         f"**Objects:** `{r['manifest']}` list SHA256 `{r['object_list_sha256']}`. E1 window: {r['e1_window']}; "
         f"E1-development slice: {r['e1_development_slice']}. Not read: " + ", ".join(r["not_read"]) + ".",
         "", "## Sample",
         f"Rows {r['census']['rows']}, holes {r['census']['holes']} (E1 window {r['census']['holes_in_e1_window']}, "
         f"E1-development slice {r['census']['holes_in_e1_development_slice']}, rest of the refused 25th "
         f"{r['census']['holes_e1_refused_day_tail']}, other {r['census']['holes_other']}). Analysis N {r['support']['n']}, "
         f"ISO weeks {r['support']['iso_weeks']}.", "",
         f"## Estimates (95 % ISO-week block interval; B {r['bootstrap']['draws']}, seed {r['bootstrap']['seed']})", "",
         "| Estimand | Point | 95 % interval | valid draws |", "|---|---|---|---|"]
    for name in ("raw", "b0", "b0_ret1h", "primary_b1"):
        c = r["intervals"][name]
        L.append(f"| {LABELS[name]} | {_f(r['points'][name])} | [{_f(c['lo'])}, {_f(c['hi'])}] | {c['valid']}/{c['draws']} |")
    L += ["", "## Years and halves (points; diagnostics only)", "", "| piece | N | raw | B0 | B0 + RET_1H | PRIMARY B1 |",
          "|---|---|---|---|---|---|"]
    for p in r["years"] + r["halves"]["pieces"]:
        L.append(f"| {p['piece']} | {p['n']} | {_f(p['raw'])} | {_f(p['b0'])} | {_f(p['b0_ret1h'])} | {_f(p['primary_b1'])} |")
    L += ["", f"All anchors: P(UP) {r['p_up_all']:.4f}, mean {r['mean_bp_all']:+.2f} bp, median {r['median_bp_all']:+.2f} bp.", "",
          "## Quintiles (description only; P(UP) / mean bp / median bp)", ""]
    for lab, key in (("OCC", "quintiles_occ"), ("OCC residual on B1 ranks", "quintiles_occ_residual_on_b1")):
        q = r[key]
        if not q or q["degenerate"]:
            L.append(f"- {lab}: degenerate")
            continue
        L.append(f"- {lab}: " + "; ".join(f"Q{b['bin']} {b['p_up']:.4f} / {b['mean_bp']:+.2f} / {b['median_bp']:+.2f}"
                                           for b in q["bins"]))
    c = r["comparison_quoted"]
    L += ["", "## Cross-era comparison (quoted, not pooled, not recomputed)", "",
          "| surface | OCC \\| B0 | OCC \\| B1 |", "|---|---|---|",
          f"| Binance 2020–24 (discovery) | {c['discovery']['b0']:+.4f} [{c['discovery']['b0_ci'][0]:+.4f}, "
          f"{c['discovery']['b0_ci'][1]:+.4f}] | never computed |",
          f"| BitMEX 2016–19 | {c['bitmex']['b0']:+.4f} [{c['bitmex']['b0_ci'][0]:+.4f}, {c['bitmex']['b0_ci'][1]:+.4f}] | "
          f"{c['bitmex']['b1']:+.4f} [{c['bitmex']['b1_ci'][0]:+.4f}, {c['bitmex']['b1_ci'][1]:+.4f}] |",
          f"| Binance 2025–26 (this unit) | {_f(r['points']['b0'])} [{_f(r['intervals']['b0']['lo'])}, "
          f"{_f(r['intervals']['b0']['hi'])}] | {_f(r['points']['primary_b1'])} [{_f(r['intervals']['primary_b1']['lo'])}, "
          f"{_f(r['intervals']['primary_b1']['hi'])}] |"]
    if r["heterogeneity"]:
        h = r["heterogeneity"]["b1"]
        L += ["", f"Heterogeneity (descriptive): modern − BitMEX PRIMARY {h['modern_minus_bitmex_b1']:+.4f}, approximate SE "
              f"{h['approx_se']:.4f} (from the two percentile intervals), z {h['approx_z']:+.2f}."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
