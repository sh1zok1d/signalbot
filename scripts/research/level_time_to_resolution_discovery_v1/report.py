"""Short official markdown. The closeout note may expand it from the JSON."""

from __future__ import annotations


def _mins(value) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.2f} min"


def _ci(ci) -> str:
    if not ci:
        return "NA"
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def render(payload: dict) -> str:
    primary = payload.get("primary") or {}
    lines = [
        f"# {payload.get('unit')}",
        "",
        f"Routing: `{payload.get('routing')}`",
        f"Claim ceiling: `{payload.get('claim_ceiling')}`",
        f"Candidate: `{payload.get('candidate_class')}`",
        f"Outcomes read: `{payload.get('outcomes_read')}`",
        f"Design SHA: `{payload.get('design_sha')}`",
        "",
        payload.get("note") or "",
        "",
        "## Primary",
        "",
        f"N={payload.get('n_primary')} weeks={primary.get('weeks')}",
        f"real RMUT {_mins(primary.get('real'))}",
        f"pseudo RMUT {_mins(primary.get('pseudo'))}",
        f"delta {_mins(primary.get('delta'))} CI {_ci(primary.get('delta_ci95'))}",
        "",
    ]
    return "\n".join(lines) + "\n"
