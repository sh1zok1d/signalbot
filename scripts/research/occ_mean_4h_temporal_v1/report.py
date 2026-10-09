"""Markdown for OCC_MEAN_4H_TEMPORAL_REPLICATION_V1 (frozen evaluator output)."""
from __future__ import annotations

from pathlib import Path

LABELS = {"raw": "Raw Spearman(OCC, R_1H)", "b0": "Secondary A: partial | B0 (parity with discovery)",
          "b0_ret1h": "Secondary B: partial | B0 + RET_1H", "primary_b1": "**PRIMARY: partial | B1 = B0 + RET_1H + RET_15M**"}


def _f(v):
    return "—" if v is None else f"{v:+.6f}"


def write_markdown(r: dict, path: Path) -> None:
    L = [f"# {r['unit']}", "",
         f"**Route:** `{r['route']}`" + (f" (flags: {', '.join(r['route_flags'])})" if r["route_flags"] else "") + ".",
         f"**Evidence class:** `{r['evidence_class']}`. **Claim ceiling:** `{r['claim_ceiling']}`. "
         "`PRODUCT_INTEGRATION_CANDIDATE = NO`.",
         f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`), frozen before this read. "
         f"**Evaluator digest:** `{r['evaluator_digest']}`.",
         f"**Series:** `{r['series']}` SHA256 `{r['series_sha256']}`. Nothing else was read: " + ", ".join(r["not_read"]) + ".",
         "", "## Sample",
         f"Rows {r['census']['rows']}, holes {r['census']['holes']} (the documented gap), zero-trade bars kept "
         f"{r['census']['zero_trade_bars']}. Analysis N {r['support']['n']}, ISO weeks {r['support']['iso_weeks']}, "
         f"T {r['support']['first_t']} .. {r['support']['last_t']}.", "",
         "## Estimates (95 % ISO-week block interval)", "", "| Estimand | Point | 95 % interval | valid draws |", "|---|---|---|---|"]
    for name in ("raw", "b0", "b0_ret1h", "primary_b1"):
        c = r["intervals"][name]
        L.append(f"| {LABELS[name]} | {_f(r['points'][name])} | [{_f(c['lo'])}, {_f(c['hi'])}] | {c['valid']}/{c['draws']} |")
    d = r["discovery"]
    L += ["", f"Discovery (Binance 2020–24, not recomputed): partial | B0 {d['b0_point']:+.4f} "
          f"[{d['b0_ci'][0]:+.4f}, {d['b0_ci'][1]:+.4f}]; local-path-controlled discovery point not computed.", "",
          "## Years and halves (points)", "", "| piece | N | raw | B0 | B0 + RET_1H | PRIMARY B1 |", "|---|---|---|---|---|---|"]
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
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
