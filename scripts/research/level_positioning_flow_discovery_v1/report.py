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
        f"N={cell.get('n')}, clusters={cell.get('clusters')}"
    )


def render(result: dict) -> str:
    lines = [
        f"# {result['unit']}",
        "",
        f"MODE = {result['mode']}",
        "",
        "One official discovery run. This note does not change the product.",
        "",
        "## Provenance",
        "",
        f"Design SHA `{result['design_sha']}`. Source main `{result['source_main']}`.",
        "",
        "Dependencies, not rewritten:",
        "",
    ]
    for name, sha in result["dependencies"].items():
        lines.append(f"- {name}: `{sha}`")
    lines.extend([
        "",
        "## Data",
        "",
        f"CORE `{result['core']['dataset_id']}` zip-list SHA256 `{result['core']['zip_list_sha256']}`.",
        f"OI git snapshot `{result['oi']['git_snapshot_id']}` oi.jsonl SHA256 `{result['oi']['oi_jsonl_sha256']}` "
        f"rows {result['oi']['n_rows']}. Runtime wrapper snapshot `{result['oi'].get('runtime_snapshot_id')}`. "
        f"Funding opened: {result['oi']['funding_jsonl_opened']}.",
        f"Event window {result['event_window']['start']} inclusive to {result['event_window']['end_exclusive']} exclusive.",
        "",
        "## Cohort",
        "",
        f"Retained features: {', '.join(result['kept_features']) or 'none'}.",
        f"Dropped before outcomes: {result['dropped_features']}.",
        f"Search exposure: `{result['search_exposure']}`.",
        f"Seed {result['seed']}, bootstrap draws {result['draws']}, FDR q={result['fdr_q']}, "
        f"practical scale {result['practical_scale']}.",
        "",
        "## Decomposition",
        "",
        "Crude BREAK / REJECT / NEITHER frequencies on geometry-legitimate first touches, "
        "including events whose positioning window is incomplete. Ambiguous labels are excluded from the rates.",
        "",
    ])
    dec = result["decomposition_geometry"]
    lines.append(
        f"BREAK {dec['n_break']} ({_num(dec['p_break'])}), "
        f"REJECT {dec['n_reject']} ({_num(dec['p_reject'])}), "
        f"NEITHER {dec['n_neither']} ({_num(dec['p_neither'])}), "
        f"RESOLVE {_num(dec['p_resolve'])}, ambiguous {dec['n_ambiguous']}."
    )
    lines.extend(["", "## RESOLVE_4H", ""])
    for cell in result["primary"]:
        if cell["outcome"] == "RESOLVE_4H":
            lines.append(f"- {_cell_line(cell)}")
    lines.extend(["", "## BREAK_GIVEN_RESOLVED", ""])
    for cell in result["primary"]:
        if cell["outcome"] == "BREAK_GIVEN_RESOLVED":
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
    lines.extend([
        "",
        "## Shape",
        "",
    ])
    for item in result["shape"]:
        bands = ", ".join(
            f"{name} n={band['n']} rate={_num(band['rate'])}" for name, band in item["bands"].items()
        )
        lines.append(f"- {item['feature']} → {item['outcome']}: {item['label']}; {bands}")
    lines.extend(["", "## Stability", ""])
    for spec in ("epoch", "family", "side"):
        lines.append(f"### {spec}")
        lines.append("")
        for cell in result["stability"]:
            if cell["spec"] != spec:
                continue
            lines.append(
                f"- {cell['feature']} → {cell['outcome']} [{cell['slice']}]: "
                f"{_pp(cell.get('coef'))}, N={cell.get('n')}"
            )
        lines.append("")
    lines.extend(["## Leave-one-year-out", ""])
    for cell in result["loyo"]:
        lines.append(
            f"- {cell['feature']} → {cell['outcome']} [{cell['slice']}]: "
            f"{_pp(cell.get('coef'))}, N={cell.get('n')}"
        )
    lines.extend(["", "## Leave-one-family-out", ""])
    for cell in result["lofo"]:
        lines.append(
            f"- {cell['feature']} → {cell['outcome']} [{cell['slice']}]: "
            f"{_pp(cell.get('coef'))}, N={cell.get('n')}, dropped share {_num(cell.get('dropped_share'))}"
        )
    lines.extend([
        "",
        "## Routing",
        "",
        f"Routing `{result['routing']}`.",
        f"SUCCESSOR_CANDIDATE = `{result['successor_candidate']}`.",
        f"PRODUCT_INTEGRATION_CANDIDATE = {result['product_integration_candidate']}.",
        "Claim ceiling L2. A selected cell is a historical association in this cohort, not a current probability.",
        "OI up is more outstanding open interest. Oriented flow is aggressive executed volume toward the level.",
        "No long/short identity, no trade call, no product change.",
        "",
        "Exploratory successor ideas, not estimated:",
        "",
    ])
    ideas = result.get("exploratory_successor_ideas") or ["none"]
    for idea in ideas:
        lines.append(f"- {idea}")
    lines.append("")
    return "\n".join(lines)
