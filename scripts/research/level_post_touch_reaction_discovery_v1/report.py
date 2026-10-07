"""Result note. Numbers come from the one official run."""

from __future__ import annotations


def _pp(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):+.2f} pp"


def _ci(ci) -> str:
    if not ci:
        return "n/a"
    return f"{_pp(ci[0])} .. {_pp(ci[1])}"


def _num(value, digits=4) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _cell_line(cell: dict) -> str:
    return (
        f"{cell['feature']} → {cell['outcome']}: {_pp(cell.get('coef'))} "
        f"(95% {_ci(cell.get('ci95'))}), p={_num(cell.get('p'))}, q={_num(cell.get('q'))}, "
        f"N={cell.get('n')}, clusters={cell.get('clusters')}, "
        f"bootstrap_valid={cell.get('bootstrap_valid')}"
    )


def render(result: dict) -> str:
    lines = [
        f"# {result['unit']}",
        "",
        f"MODE = {result['mode']}",
        "",
        "One official discovery run. Decision time is 15 minutes after the first touch. "
        "Events that already reached a barrier before that time are a census, not a prediction. "
        "This note does not change the product.",
        "",
        "## Provenance",
        "",
        f"Design SHA `{result['design_sha']}`. Source main `{result['source_main']}`.",
        f"Exposure `{result['exposure_status']}`.",
        "",
        "Dependencies, not rewritten:",
        "",
    ]
    for name, sha in result["dependencies"].items():
        lines.append(f"- {name}: `{sha}`")
    oi = result["oi"]
    lines.extend([
        "",
        "## Data",
        "",
        f"CORE `{result['core']['dataset_id']}` zip-list SHA256 `{result['core']['zip_list_sha256']}`.",
        f"OI `{oi['dataset_id']}` snapshot `{oi['git_snapshot_id']}` "
        f"jsonl SHA256 `{oi['oi_jsonl_sha256']}`. Funding opened: {oi['funding_jsonl_opened']}.",
        f"Event window {result['event_window']['start']} inclusive to "
        f"{result['event_window']['end_exclusive']} exclusive.",
        "T is the open of the touch bar. D = T+15m. Reaction bars are j, j+1, j+2. "
        "Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.",
        "",
        "## Cohort",
        "",
        f"Retained features: {', '.join(result['kept_features']) or 'none'}.",
        f"Dropped before outcomes: {result['dropped_features']}.",
        f"Search exposure: `{result['search_exposure']}`.",
        f"Seed {result['seed']}, bootstrap draws {result['draws']}, FDR q={result['fdr_q']}, "
        f"practical scale {result['practical_scale']}.",
        "",
        "## Early census",
        "",
        "Counts of geometry-legitimate first touches. No real-versus-pseudo test is reported.",
        "",
    ])
    early = result["early_census_geometry"]
    lines.append(
        f"N {early['n']}. Early BREAK {early['n_early_break']} ({_num(early['p_early_break'])}), "
        f"early REJECT {early['n_early_reject']} ({_num(early['p_early_reject'])}), "
        f"early ambiguous {early['n_early_ambiguous']} ({_num(early['p_early_ambiguous'])}), "
        f"unresolved {early['n_unresolved']} ({_num(early['p_unresolved'])}), "
        f"unavailable {early['n_unavailable']}."
    )
    late = result["late_decomposition"]
    lines.extend([
        "",
        "## Late decomposition",
        "",
        "BREAK / REJECT / NEITHER after D, on events unresolved at D. Ambiguous labels are excluded from the rates.",
        "",
        f"BREAK {late['n_break']} ({_num(late['p_break'])}), "
        f"REJECT {late['n_reject']} ({_num(late['p_reject'])}), "
        f"NEITHER {late['n_neither']} ({_num(late['p_neither'])}), "
        f"RESOLVE {_num(late['p_resolve'])}, ambiguous {late['n_ambiguous']}.",
        "",
        "## LATE_RESOLVE_BY_4H",
        "",
    ])
    for cell in result["primary"]:
        if cell["outcome"] == "LATE_RESOLVE_BY_4H":
            lines.append(f"- {_cell_line(cell)}")
    lines.extend(["", "## LATE_BREAK_GIVEN_RESOLVED", ""])
    for cell in result["primary"]:
        if cell["outcome"] == "LATE_BREAK_GIVEN_RESOLVED":
            lines.append(f"- {_cell_line(cell)}")
    lines.extend(["", "## Specificity (beta_real - beta_pseudo)", ""])
    for cell in result["specificity"]:
        lines.append(
            f"- {cell['feature']} → {cell['outcome']}: delta {_pp(cell.get('delta'))} "
            f"(95% {_ci(cell.get('ci95'))}), beta_real {_pp(cell.get('beta_real'))}, "
            f"beta_pseudo {_pp(cell.get('beta_pseudo'))}, N={cell.get('n')}, clusters={cell.get('clusters')}"
        )
    lines.extend(["", "## Pseudo cohort", ""])
    for cell in result["pseudo"]:
        lines.append(
            f"- {cell['feature']} → {cell['outcome']}: {_pp(cell.get('coef'))} "
            f"(95% {_ci(cell.get('ci95'))}), N={cell.get('n')}, clusters={cell.get('clusters')}"
        )
    lines.extend(["", "## Decisions", ""])
    for item in result["decisions"]:
        lines.append(
            f"- {item['feature']} → {item['outcome']}: label {item['label']}, "
            f"conjunction {item['conjunction_pass']}, failed {item['failed']}"
        )
    lines.extend(["", "## Shape", ""])
    for item in result["shape"]:
        bands = item["bands"]
        bits = ", ".join(
            f"{name} n={bands[name]['n']} rate={_num(bands[name]['rate'])}"
            for name in ("low", "mid", "high")
        )
        lines.append(f"- {item['feature']} → {item['outcome']}: {item['label']}; {bits}")
    lines.extend(["", "## Stability", ""])
    for spec in ("epoch", "family", "side"):
        lines.append(f"### {spec}")
        lines.append("")
        for item in result["stability"]:
            if item["spec"] != spec:
                continue
            lines.append(
                f"- {item['feature']} → {item['outcome']} [{item['slice']}]: "
                f"{_pp(item.get('coef'))}, N={item.get('n')}"
            )
        lines.append("")
    lines.extend(["## Leave-one-year-out", ""])
    for item in result["loyo"]:
        lines.append(
            f"- {item['feature']} → {item['outcome']} [{item['slice']}]: "
            f"{_pp(item.get('coef'))}, N={item.get('n')}"
        )
    lines.extend(["", "## Leave-one-family-out", ""])
    for item in result["lofo"]:
        lines.append(
            f"- {item['feature']} → {item['outcome']} [{item['slice']}]: "
            f"{_pp(item.get('coef'))}, N={item.get('n')}, dropped share {_num(item.get('dropped_share'))}"
        )
    lines.extend([
        "",
        "## Routing",
        "",
        f"Routing `{result['routing']}`.",
        f"LEVEL_POST_TOUCH_REACTION_CANDIDATE count: {len(result['level_post_touch_reaction_candidate'])}.",
        f"GENERIC_POST_TOUCH_STATE_CANDIDATE count: {len(result['generic_post_touch_state_candidate'])}.",
        f"SUCCESSOR_CANDIDATE = `{result['successor_candidate']}`.",
        "PRODUCT_INTEGRATION_CANDIDATE = False.",
        "Claim ceiling L2. A historical association is not a current probability.",
        "End position is the close at D in units of the barrier distance. It is not acceptance, "
        "a failed break, or a confirmed breakout.",
        "No trade call and no product change.",
        "",
        "Exploratory successor ideas, not estimated:",
        "",
    ])
    for idea in result["exploratory_successor_ideas"]:
        lines.append(f"- {idea}")
    if not result["exploratory_successor_ideas"]:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
