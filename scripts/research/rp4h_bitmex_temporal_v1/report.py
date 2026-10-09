"""Markdown record of the one Unit A read. Numbers come from the result dict only."""

from __future__ import annotations

from pathlib import Path


def _ci(b: dict) -> str:
    return "n/a" if b["lo"] is None else f"[{b['lo']:.6f}, {b['hi']:.6f}] ({b['valid']}/{b['draws']})"


def _f(v) -> str:
    return "n/a" if v is None else f"{v:.6f}"


def write_markdown(r: dict, path: Path) -> None:
    b = r["bootstrap"]
    lines = [
        f"# {r['unit']}",
        "",
        f"**Route:** `{r['route']}`" + (f" (flags: {', '.join(r['route_flags'])})" if r["route_flags"] else "") + ".",
        f"**Evidence class:** `{r['evidence_class']}`. **Claim ceiling:** `{r['claim_ceiling']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.",
        f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`), frozen before this read. "
        f"**Parent:** `{r['parent_unit']}` (`{r['parent_design_sha256']}`).",
        f"**Series:** `{r['series']}` SHA256 `{r['series_sha256']}`. **Evaluator digest:** `{r['evaluator_digest']}`.",
        "Nothing else was read: no Binance 2025-26, no spot, no Bybit or Binance 2020-24 outcome, no fees.",
        "",
        "## Sample",
        f"Grid slots {r['grid']['slots']}, bars {r['grid']['occupied']}, holes {r['grid']['holes']} (the documented gap); "
        f"zero-trade bars kept {r['preflight_census']['zero_trade_bars']}. Phase anchors {r['phase_anchors']}, "
        f"analysis N {r['analysis_n']}, ISO weeks {r['iso_weeks']}, T {r['first_t']} .. {r['last_t']}.",
        "",
        "## Estimates",
        "| Estimand | Point | 95 % week-block interval |",
        "|---|---|---|",
        f"| Raw Spearman(RP4H, R_1H) | {_f(r['raw_spearman'])} | {_ci(b['raw'])} |",
        f"| **Primary** partial given RET_4H, RV_4H | {_f(r['primary_partial'])} | {_ci(b['primary'])} |",
        f"| Secondary 1 (parent): partial given RET_4H | {_f(r['secondary_ret4_partial'])} | {_ci(b['secondary_ret4'])} |",
        f"| Secondary 2 (local path): given RET_4H, RV_4H, RET_1H, RET_15M | {_f(r['secondary_local_partial'])} | {_ci(b['secondary_local'])} |",
        "",
        f"Width diagnostic: Spearman(RP4H, width) {_f(r['width_spearman_with_rp'])}; partial also given width {_f(r['width_partial'])}. "
        f"Attenuation by RET_4H {_f(r['attenuation_by_ret'])}, share {_f(r['share_removed_by_ret'])}.",
        "",
        "## Quintiles (description, no gate)",
        "| bin | N | P(UP) | mean R | median R |",
        "|---|---|---|---|---|",
    ]
    q = r["quintiles"]
    for row in (q.get("bins") or []):
        lines.append(f"| {row['bin']} | {row['n']} | {_f(row['p_up'])} | {row['mean_return']} | {row['median_return']} |")
    lines += ["", "## Years and halves", "| piece | N | raw | primary |", "|---|---|---|---|"]
    for row in r["yearly"] + r["halves"]["pieces"]:
        lines.append(f"| {row['piece']} | {row['n']} | {_f(row['raw'])} | {_f(row['primary'])} |")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
