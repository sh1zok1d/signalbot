"""Short result note. The JSON record is the authority."""

from __future__ import annotations


def _pp(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):.2f} pp"


def _ci(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "withheld"
    return f"[{float(ci[0]):.4f}, {float(ci[1]):.4f}]"


def render(payload: dict) -> str:
    lines = [
        f"# {payload['unit']}",
        "",
        f"Routing: `{payload.get('routing')}`",
        f"Claim ceiling: `{payload.get('claim_ceiling')}`",
        f"Candidate class: `{payload.get('candidate_class')}`",
        f"Outcomes read: `{payload.get('outcomes_read')}`",
        f"Design SHA: `{payload.get('design_sha')}`",
        "",
        payload.get("note") or "",
        "",
        "## Baseline",
        "",
    ]
    base = payload.get("baseline") or {}
    lines.append(
        f"END_POSITION_X: {_pp(base.get('endpos_coef'))} CI {_ci(base.get('endpos_ci95'))} N={base.get('n')}"
    )
    lines.append(
        f"OTHER_VENUE_MEDIAN_MOVE: {_pp(base.get('cv1_coef'))} CI {_ci(base.get('cv1_ci95'))} N={base.get('n')}"
    )
    lines.extend(["", "## Primary spot coefficients", "",
                  "| feature | coef | 95% CI | q | N | class |",
                  "|---|---:|---|---:|---:|---|"])
    for item in payload.get("features") or []:
        cell = item.get("cell") or {}
        summary = item.get("summary") or {}
        lines.append(
            f"| {summary.get('feature')} | {_pp(cell.get('coef'))} | {_ci(cell.get('ci95'))} | "
            f"{summary.get('q')} | {cell.get('n')} | {summary.get('candidate_class')} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "Discovery only. CV1 in the baseline is a control, not a new confirmation. "
        "Spot moving with the structural direction is not a statement that spot led the barrier.",
        "",
    ])
    return "\n".join(lines)
