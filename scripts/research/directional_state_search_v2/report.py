"""Result markdown and the post-outcome ledger section (the pre-outcome section is kept byte-for-byte as data)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _f(v, nd=4):
    return "—" if v is None else f"{v:+.{nd}f}"


def _ci(e):
    return f"[{e['lo']:+.4f}, {e['hi']:+.4f}]"


def write_markdown(r: dict, path: Path) -> None:
    L = [f"# {r['program']} — RESULT (one bounded discovery cycle)", "",
         f"**Mode:** `{r['mode']}`. **Exposure class:** `{r['exposure_class']}`. **Claim ceiling:** `{r['claim_ceiling']}` "
         f"(every number here is discovery on an exposed surface). `PRODUCT_INTEGRATION_CANDIDATE = NO`.",
         f"**Design SHA256:** `{r['design_sha256']}` (commit `{r['design_commit']}`), frozen before this read. "
         f"**Pre-outcome ledger SHA256:** `{r['ledger_pre_sha256']}`. **Evaluator digest:** `{r['evaluator_digest']}`.",
         f"**Surface:** {r['surface']}; CORE digest `{r['core_digest']}`; tzdata `{r['tzdata']}`.",
         f"**Parity:** close_pos_4h → R_1H on the discovery anchors reproduced exactly: N {r['parity']['n']}, "
         f"ρ {r['parity']['rho']:.15f}.",
         f"**Bootstrap:** {r['bootstrap']['method']}, {r['bootstrap']['draws']} draws, seed {r['bootstrap']['seed']}, "
         f"{r['global_iso_weeks']} ISO weeks.", "",
         "## Primary objects (target R_1H; incremental = partial Spearman given B0 = RP4H, RET_4H, RV_4H + listed extras)", "",
         "| id | state | N | weeks | raw ρ [95 %] | incremental ρ [95 %] | z | years same sign | extra controls |",
         "|---|---|---|---|---|---|---|---|---|"]
    for cid, ev in r["objects"].items():
        extra = [c for c in ev["controls"] if c not in ("RP4H", "RET_4H", "RV_4H")]
        L.append(f"| {cid} | `{ev['state']}` | {ev['n']} | {ev['iso_weeks']} | {_f(ev['raw']['point'])} {_ci(ev['raw'])} | "
                 f"**{_f(ev['incremental']['point'])}** {_ci(ev['incremental'])} | {_f(ev['incremental']['z'], 2)} | "
                 f"{ev['years_same_sign_as_incremental']}/5 | {', '.join(extra) or '—'} |")
    L += ["", "## Per-year incremental points", "", "| id | " + " | ".join(str(y) for y in range(2020, 2025)) + " |",
          "|---|" + "---|" * 5]
    for cid, ev in r["objects"].items():
        ys = {y["year"]: y["incremental"] for y in ev["years"]}
        L.append(f"| {cid} | " + " | ".join(_f(ys.get(y)) for y in range(2020, 2025)) + " |")
    L += ["", "## Quintiles (description only; P(UP), mean and median R_1H in bp)", ""]
    for cid, ev in r["objects"].items():
        L.append(f"**{cid} `{ev['state']}`** — all: P(UP) {ev['p_up_all']:.4f}, mean {ev['mean_bp_all']:+.2f}, "
                 f"median {ev['median_bp_all']:+.2f}")
        for lab, key in (("state", "quintiles_state"), ("residual of state on controls", "quintiles_residual_state")):
            q = ev[key]
            if q["degenerate"]:
                L.append(f"- by {lab}: degenerate edges")
                continue
            cells = "; ".join(f"Q{b['bin']} {b['p_up']:.3f} / {b['mean_bp']:+.2f} / {b['median_bp']:+.2f}" for b in q["bins"])
            L.append(f"- by {lab}: {cells}")
        L.append("")
    L += ["## Variant, sensitivity, placebo clocks, interactions", ""]
    for vid, v in r["variants"].items():
        L.append(f"- **{vid}** (variant of {v['parent']}, `{v['state']}`): raw {_f(v['raw']['point'])} {_ci(v['raw'])}; "
                 f"incremental {_f(v['incremental']['point'])} {_ci(v['incremental'])}; years same sign "
                 f"{v['years_same_sign_as_incremental']}/5.")
    for sid, v in r["sensitivities"].items():
        L.append(f"- **{sid}** (sensitivity of {v['parent']}; controls {', '.join(v['controls'])}): "
                 f"{_f(v['incremental']['point'])} {_ci(v['incremental'])}.")
    for cid, v in r["placebo"].items():
        L.append(f"- **{cid} placebo clocks** (same statistic at every other anchor, N {v['n']}): incremental "
                 f"{_f(v['placebo_incremental']['point'])} {_ci(v['placebo_incremental'])}; clock − placebo "
                 f"{_f(v['clock_minus_placebo']['point'])} {_ci(v['clock_minus_placebo'])}.")
    L.append(f"- **Session Holm-adjusted p (F6a, F6b):** " + ", ".join(f"{k} {v:.4f}" for k, v in r["session_holm_adjusted_p"].items()))
    if r["interactions"]:
        for cid, v in r["interactions"].items():
            t = ", ".join(f"T{w['tercile']} {_f(w['rp4h_partial_given_ret4h_rv4h'])}" for w in v["rp4h_effect_by_state_tercile"])
            L.append(f"- **{cid} × RP4H** (stage 2): interaction {_f(v['interaction']['point'])} {_ci(v['interaction'])}; "
                     f"RP4H partial by state tercile: {t}.")
    else:
        L.append("- **Stage 2 interactions:** none run (no incremental interval excluded zero).")
    L += ["", "## Blocked before outcome", ""] + [f"- **{k}:** {v}" for k, v in r["blocked_families"].items()]
    L += ["", "## Search exposure and the promotion bar", "",
          f"Cells read in this cycle: {r['cells_read']}. Bar (rules §4): family-wise α 0.10 Bonferroni over m = "
          f"{r['m_for_bar']} (813 CORE × DIRECTION before + this cycle) → |z| ≥ {r['z_bar']:.3f}.", "",
          "| rank | id | |incremental| | interval excludes 0 | years same sign | z | clears bar | eligible |",
          "|---|---|---|---|---|---|---|---|"]
    for k, row in enumerate(r["ranking"]["rows"], 1):
        L.append(f"| {k} | {row['id']} | {row['abs_point']:.4f} | {row['interval_excludes_zero']} | {row['years_same_sign']}/5 | "
                 f"{_f(row['z'], 2)} | {row['clears_search_bar']} | {row['eligible']} |")
    L += ["", f"**TOP 3 by the frozen rule:** {', '.join(r['ranking']['top3']) or 'none'}.", "",
          "Interpretation, the claim decision and the replication proposals are in the program's design note follow-up "
          "and the owner report; this file is the frozen evaluator output."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_ledger(r: dict, path: Path) -> None:
    body = json.loads(path.read_text())
    if "post_outcome" in body:
        raise SystemExit("LEDGER_ALREADY_HAS_POST_OUTCOME")
    body["post_outcome"] = {"cells_read": r["cells_read"], "reads": r["reads"], "m_for_bar": r["m_for_bar"],
                            "z_bar": r["z_bar"], "top3_by_frozen_rule": r["ranking"]["top3"],
                            "result_json": "docs/research/DIRECTIONAL_STATE_SEARCH_V2_RESULT.json"}
    text = json.dumps(body, indent=1, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")
