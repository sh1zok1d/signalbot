"""Text result. Wording stays descriptive: no venue is said to lead or confirm causally."""

from __future__ import annotations


def _num(value, digits: int = 4) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.{digits}f}"


def _ci(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "NA"
    return f"[{_num(ci[0])}, {_num(ci[1])}]"


def _pp(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):.2f} pp"


def render(result: dict) -> str:
    lines = [
        f"# {result['unit']}",
        "",
        f"Routing: `{result['routing']}`",
        f"Claim ceiling: `{result['claim_ceiling']}`",
        f"Candidate class: `{result.get('candidate_class')}`",
        f"Outcomes read: `{result['outcomes_read']}`",
        f"Design SHA: `{result['design_sha']}`",
        "",
        "Other perpetual venues' 15-minute price moves are a state around the Binance structural event.",
        "The lines below do not say that a venue led, confirmed, or caused the later barrier.",
        "",
        "## Baseline",
        "",
        f"END_POSITION_X coefficient on the primary support: {_pp(result['baseline'].get('coef'))} "
        f"CI {_ci(result['baseline'].get('ci95'))} N={result['baseline'].get('n')}",
        "",
        "## Primary cross-venue coefficients",
        "",
        "| feature | coef | 95% CI | q | N | class |",
        "|---|---:|---|---:|---:|---|",
    ]
    for item in result.get("features") or []:
        cell = item["cell"]
        lines.append(
            f"| {cell.get('feature')} | {_pp(cell.get('coef'))} | {_ci(cell.get('ci95'))} | "
            f"{_num(cell.get('q'))} | {cell.get('n')} | {item['summary'].get('candidate_class')} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.append(result.get("note") or "Discovery only. No current probability and no trade instruction.")
    lines.append("")
    return "\n".join(lines)
