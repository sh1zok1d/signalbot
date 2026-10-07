"""Render the one-shot result. Numbers come from the result dict."""

from __future__ import annotations


def _pp(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):+.2f} pp"


def _ci(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "n/a"
    return f"{100.0 * float(ci[0]):+.2f} pp .. {100.0 * float(ci[1]):+.2f} pp"


def _line(cell: dict) -> str:
    return (
        f"- {cell['state']} → {cell['outcome']}: {_pp(cell.get('coef'))} "
        f"(95% {_ci(cell.get('ci95'))}), p={cell.get('p')}, q={cell.get('q')}, "
        f"N={cell.get('n')}, n_state={cell.get('n_state')}, clusters={cell.get('clusters')}, "
        f"bootstrap_valid={cell.get('bootstrap_valid')}"
    )


def render(result: dict) -> str:
    lines = [
        f"# {result['unit']}",
        "",
        "MODE = DISCOVERY",
        "",
        "One official discovery run. This note does not change the product.",
        "",
        "## Provenance",
        "",
        f"Design SHA `{result['design_sha']}`. Source main `{result['source_main']}`.",
        "",
        "## Partition",
        "",
        f"Selected K = {result['selected_k']}. Training rows {result['census']['predictor_complete']}.",
        f"Routing `{result['routing']}`. SUCCESSOR_CANDIDATE = `{result['successor_candidate']}`.",
        f"PRODUCT_INTEGRATION_CANDIDATE = {result['product_integration_candidate']}.",
        "",
        "## Centroids",
        "",
    ]
    for name, centroid, text in zip(result["state_names"], result["centroids"], result["descriptions"]):
        coords = ", ".join(f"{float(v):+.4f}" for v in centroid)
        lines.append(f"- {name}: ({coords}). {text}")
    lines.extend(["", "## RESOLVE_4H", ""])
    for cell in result["primary"]:
        if cell["outcome"] == "RESOLVE_4H":
            lines.append(_line(cell))
    lines.extend(["", "## BREAK_GIVEN_RESOLVED", ""])
    for cell in result["primary"]:
        if cell["outcome"] == "BREAK_GIVEN_RESOLVED":
            lines.append(_line(cell))
    lines.extend(["", "## Three-way map", ""])
    for row in result["three_way"]:
        lines.append(
            f"- {row['state']}: N={row['n']}, BREAK={row['p_break']}, REJECT={row['p_reject']}, "
            f"NEITHER={row['p_neither']}, RESOLVE={row['p_resolve']}, "
            f"BREAK|RESOLVED={row['p_break_given_resolved']}"
        )
    lines.extend(["", "## Specificity", ""])
    for cell in result["specificity"]:
        lines.append(
            f"- {cell['state']} → {cell['outcome']}: delta {_pp(cell.get('delta'))} "
            f"(95% {_ci(cell.get('ci95'))}), beta_real {_pp(cell.get('beta_real'))}, "
            f"beta_pseudo {_pp(cell.get('beta_pseudo'))}, N={cell.get('n')}"
        )
    lines.extend(["", "## Decisions", ""])
    for item in result["decisions"]:
        lines.append(
            f"- {item['state']} → {item['outcome']}: {item['label']}, "
            f"conjunction {item['conjunction']['pass']}, failed {item['conjunction']['failed']}"
        )
    lines.extend(["", "## Claim", ""])
    lines.append("Claim ceiling L2. A selected state is a historical association in this cohort, not a current probability.")
    lines.append("Centroid words describe robust-z coordinates. They are not a participant identity and not a cause.")
    lines.append("")
    return "\n".join(lines)
