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


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _cell_line(cell: dict) -> str:
    return (
        f"{cell['contrast']}: {_pp(cell.get('coef'))} "
        f"(95% {_ci(cell.get('ci95'))}), p={_num(cell.get('p'))}, q={_num(cell.get('q'))}, "
        f"N={cell.get('n')}, treated={cell.get('n_treated')}, reference={cell.get('n_reference')}, "
        f"clusters={cell.get('clusters')}, bootstrap_valid={cell.get('bootstrap_valid')}"
    )


def _audit_lines(audit: dict) -> list[str]:
    treated = audit["treated"]
    reference = audit["reference"]
    return [
        f"{audit['contrast']}: treated `{audit['treated_state']}` N={treated['n']} "
        f"mean={_num(treated.get('mean'))} sd={_num(treated.get('sd'))}; "
        f"reference `{audit['reference_state']}` N={reference['n']} "
        f"mean={_num(reference.get('mean'))} sd={_num(reference.get('sd'))}.",
        f"Standardized difference {_num(audit.get('standardized_difference'))}. "
        f"Overlap [{_num(audit.get('overlap_lo'))}, {_num(audit.get('overlap_hi'))}] "
        f"width {_num(audit.get('overlap_width'))}. "
        f"Shares {_num(audit.get('share_treated_in_reference_central'))} and "
        f"{_num(audit.get('share_reference_in_treated_central'))}. "
        f"Overlap pass {audit.get('overlap_pass')}. Arm pass {audit.get('arm_n_pass')}. "
        f"Reasons {audit.get('block_reasons')}.",
    ]


def render(result: dict) -> str:
    lines = [
        f"# {result['unit']}",
        "",
        f"MODE = {result['mode']}",
        "",
        "One official discovery run. The question is whether the 15-minute path adds a late-BREAK "
        "difference after the endpoint location is held fixed. This note does not change the product.",
        "",
        "## Provenance",
        "",
        f"Design SHA `{result['design_sha']}`. Source main `{result['source_main']}`.",
        f"Exposure `{result['exposure_status']}`. Outcomes read: {result['outcomes_read']}.",
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
        "Price OHLC only.",
        f"Event window {result['event_window']['start']} inclusive to "
        f"{result['event_window']['end_exclusive']} exclusive.",
        "T is the open of the touch bar. D = T+15m. Path bits use closes of j, j+1 and j+2. "
        "Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.",
        "",
        f"Seed {result['seed']}, bootstrap draws {result['draws']}, FDR q={result['fdr_q']}, "
        f"practical scale {result['practical_scale']}.",
        f"Eligible contrasts: {', '.join(result['eligible_contrasts']) or 'none'}.",
        f"Search exposure: `{result['search_exposure']}`.",
        "",
        "## Early census",
        "",
    ])
    early = result["early_census"]
    lines.append(
        f"Geometry-legitimate rows in the census base {early['n']}. "
        f"Early BREAK {early['n_early_break']}, early REJECT {early['n_early_reject']}, "
        f"early ambiguous {early['n_early_ambiguous']}, unresolved {early['n_unresolved']}, "
        f"unavailable {early['n_unavailable']}."
    )
    lines.extend(["", "## Path counts on unresolved events", ""])
    lines.append(f"Sequences: `{result['sequence_counts']}`.")
    lines.append(f"States: `{result['state_counts']}`.")
    lines.append(f"Pseudo unresolved sequences: `{result['pseudo_sequence_counts']}`.")
    lines.append(f"Pseudo unresolved states: `{result['pseudo_state_counts']}`.")
    lines.extend(["", "## Endpoint overlap", ""])
    for name, block in result["contrasts"].items():
        lines.extend(_audit_lines(block["audit"]))
        info = result["information"][name]
        lines.append(
            f"Eligible {block['eligible']}. Rough 80% MDE {_pp(info.get('rough_80pct_mde'))}. "
            f"Block reasons {block['block_reasons']}."
        )
    if not result["outcomes_read"]:
        lines.extend([
            "",
            "## Stop",
            "",
            result.get("note", "Outcomes were not read."),
            "",
            f"Routing `{result['routing']}`. Successor candidate `{result['successor_candidate']}`.",
            "",
            "Claim ceiling L2, discovery only. No product change.",
            "",
        ])
        return "\n".join(lines)
    lines.extend(["", "## Primary contrasts", ""])
    for cell in result["primary"]:
        lines.append(_cell_line(cell))
    lines.extend(["", "## Decisions", ""])
    for item in result["decisions"]:
        lines.append(
            f"{item['contrast']}: class `{item['label']}`, conjunction {item['conjunction_pass']}, "
            f"failed {item['failed']}, statistical hit {item['statistical_hit']}, "
            f"delta {_pp(item.get('delta'))} (95% {_ci(item.get('delta_ci95'))}), "
            f"pseudo slope {_pp(item.get('pseudo_coef'))} (95% {_ci(item.get('pseudo_ci95'))})."
        )
    lines.extend(["", "## Year, family, side, leave-one-year-out", ""])
    for spec in ("epoch", "family", "side"):
        lines.append(f"### {spec}")
        lines.append("")
        for cell in result["stability"]:
            if cell["spec"] != spec:
                continue
            lines.append(
                f"{cell['contrast']} {cell['slice']}: {_pp(cell.get('coef'))}, "
                f"N={cell.get('n')}, treated={cell.get('n_treated')}, reference={cell.get('n_reference')}"
            )
        lines.append("")
    lines.append("### leave-one-year-out")
    lines.append("")
    for cell in result["loyo"]:
        lines.append(
            f"{cell['contrast']} {cell['slice']}: {_pp(cell.get('coef'))}, "
            f"N={cell.get('n')}, treated={cell.get('n_treated')}, reference={cell.get('n_reference')}"
        )
    lines.extend(["", "## Descriptive sequences", ""])
    for row in result["sequence_table"]:
        lines.append(
            f"{row['sequence']}: N={row['n']}, BREAK {_pct(row['p_break'])}, "
            f"REJECT {_pct(row['p_reject'])}, NEITHER {_pct(row['p_neither'])}, "
            f"ambiguous {row['n_ambiguous']}"
        )
    lines.extend(["", "## Descriptive states, including resolve rate", ""])
    for row in result["state_table"]:
        lines.append(
            f"{row['state']}: N={row['n']}, BREAK {_pct(row['p_break'])}, "
            f"REJECT {_pct(row['p_reject'])}, NEITHER {_pct(row['p_neither'])}, "
            f"resolve among labeled {_pct(row['p_resolve_among_labeled'])}"
        )
    lines.extend([
        "",
        "## Routing",
        "",
        f"`{result['routing']}`. Successor candidate `{result['successor_candidate']}`.",
        "Claim ceiling L2, discovery only. The coefficient is a historical adjusted difference "
        "in this unresolved first-touch cohort. It is not a current probability.",
        "No product change.",
        "",
    ])
    return "\n".join(lines)
