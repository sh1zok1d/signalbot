"""Markdown for ADAPTIVE_OCCUPANCY_TIMESCALE_V1 (frozen evaluator output)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path


def _e(v, nd=7):
    return "—" if v is None else f"{v:+.{nd}f}"


def _d(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def _ci(d):
    return f"{_e(d['point'])} [{_e(d['lo'])}, {_e(d['hi'])}]"


def write_markdown(r: dict, path: Path) -> None:
    s = r["support"]
    L = [f"# {r['unit']} — result", "",
         f"**Route:** `{r['route']}`. **Adaptation vs static OCC_4H (qualifier):** `{r['adaptation_vs_static']}`.",
         f"**Evidence class:** `{r['evidence_class']}`. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No PnL, fees or entries.",
         f"**Design SHA256** `{r['design_sha256']}` (commit `{r['design_commit']}`); evaluator digest "
         f"`{r['evaluator_digest']}`; feature digest `{r['feature_sha256']}`.",
         f"**Rows** {s['rows']} ({s['rows_by_era']}); outer rows {s['outer_rows']} "
         f"(coverage {s['coverage_outer_share']:.3f}); outer blocks {s['outer_blocks']}. Outer P(UP) {r['outer_p_up']:.4f}.",
         "", "## Mean outer losses", "",
         "| model | Brier | log loss | AUROC | cal. intercept | cal. slope | ECE | p sd | share p∉[0.45, 0.55] |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in r["mean_brier"].items():
        sec = r["secondary"][k]
        L.append(f"| {k} | {v:.7f} | {r['mean_logloss'][k]:.7f} | {sec['auroc']:.4f} | "
                 f"{sec['calibration']['intercept']:+.4f} | {sec['calibration']['slope']:+.3f} | "
                 f"{sec['reliability']['ece']:.4f} | {sec['probability']['sd']:.4f} | "
                 f"{sec['probability']['share_outside_0.45_0.55']:.3f} |")
    L += ["", "## Loss differences (a − b; negative = a better; ISO-week block bootstrap 95 %)", "",
          "| pair | ΔBrier [95 %] | Δlog loss [95 %] | valid draws |", "|---|---|---|---|"]
    for pair, d in r["brier_differences"].items():
        L.append(f"| {pair} | {_ci(d)} | {_ci(r['logloss_differences'][pair])} | {d['valid']} |")
    L += ["", "## Diagnostic eras (no route)", "",
          "| era | N | weeks | P(UP) | ADAPTIVE−B1 | ADAPTIVE−STATIC_OCC4 | STATIC_OCC4−B1 | ADAPTIVE−MM_NO_OCC |",
          "|---|---|---|---|---|---|---|---|"]
    for lab, e in r["per_era"].items():
        if not e.get("n"):
            L.append(f"| {lab} | 0 | — | — | — | — | — | — |")
            continue
        b = e["brier"]
        L.append(f"| {lab} | {e['n']} | {e['weeks']} | {e['p_up']:.4f} | {_ci(b['ADAPTIVE-B1'])} | "
                 f"{_ci(b['ADAPTIVE-STATIC_OCC4'])} | {_ci(b['STATIC_OCC4-B1'])} | {_ci(b['ADAPTIVE-MM_NO_OCC'])} |")
    L += ["", "## Selector behaviour", ""]
    for name in ("config_persistence", "memory_persistence"):
        for venue, v in r["selector"][name].items():
            L.append(f"- {name} {venue}: share {v['share']}; switches {v['switches']} in {v['n_blocks']} blocks; "
                     f"mean run length {v['mean_run_length']:.2f}.")
    L += ["", "## Selector log (one row per outer block)", "",
          "| venue | outer block | memory | config | inner Brier | inner log loss | outer Brier | outer log loss | B1 outer Brier |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in r["selector"]["blocks"]:
        L.append(f"| {b['venue']} | {_d(b['outer_start_ms'])} → {_d(b['outer_end_ms'])} | {b['selected_memory_weeks']} | "
                 f"{b['selected_config']} | {b['inner_brier']:.6f} | {b['inner_logloss']:.6f} | {b['outer_brier']:.6f} | "
                 f"{b['outer_logloss']:.6f} | {b['outer_brier_b1']:.6f} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
