"""Official markdown rendered from the one zone-traded payload. No second fit."""

from __future__ import annotations

from . import constants as K


def _pp(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):+.2f} pp"


def _rate(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):.2f}%"


def _ci(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "NA"
    return f"[{100.0 * float(ci[0]):+.2f}, {100.0 * float(ci[1]):+.2f}] pp"


def _num(value) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.6g}"


def _slices(rows: list[dict]) -> list[str]:
    if not rows:
        return ["- none"]
    lines = []
    for row in rows:
        lines.append(f"- {row.get('name')}: {_pp(row.get('coef'))} N={row.get('n')}")
    return lines


def _feature(item: dict) -> list[str]:
    summary = item.get("summary") or {}
    cell = item.get("cell") or {}
    matched = item.get("matched") or {}
    lines = [
        f"### {summary.get('feature')}",
        "",
        f"effect {_pp(cell.get('coef'))} per +1 SD, CI {_ci(cell.get('ci95'))}",
        f"p={_num(cell.get('p'))} q={_num(summary.get('q'))} N={cell.get('n')} "
        f"clusters={cell.get('clusters')} bootstrap={cell.get('bootstrap_valid')}/{K.BOOT_DRAWS}",
        f"class `{summary.get('candidate_class')}` specificity `{summary.get('specificity_status')}` "
        f"statistical={summary.get('statistical')} conjunction={summary.get('conjunction_pass')} "
        f"failed={summary.get('failed')}",
        "",
        "Tertiles of late BREAK rate",
    ]
    for shape in item.get("shape") or []:
        lines.append(f"- {shape.get('bin')}: {_rate(shape.get('late_break_rate'))} N={shape.get('n')}")
    lines.extend(["", "Years", *_slices(item.get("epochs") or [])])
    lines.extend(["LOYO", *_slices(item.get("loyo") or [])])
    lines.extend(["Family", *_slices(item.get("families") or [])])
    lines.extend(["Side", *_slices(item.get("sides") or [])])
    lines.extend([
        "",
        f"matched status `{matched.get('status')}` N={matched.get('n_pairs')}",
        f"matched real {_pp(matched.get('beta_real'))} CI {_ci(matched.get('beta_real_ci95'))}",
        f"matched pseudo {_pp(matched.get('beta_pseudo'))} CI {_ci(matched.get('beta_pseudo_ci95'))}",
        f"delta {_pp(matched.get('delta'))} CI {_ci(matched.get('delta_ci95'))}",
        "",
    ])
    return lines


def render(payload: dict) -> str:
    baseline = payload.get("baseline") or {}
    lines = [
        f"# {K.UNIT}",
        "",
        f"Routing: `{payload.get('routing')}`",
        f"Claim ceiling: `{payload.get('claim_ceiling')}` / `{payload.get('exposure_status')}`",
        f"Design SHA: `{payload.get('design_sha')}`",
        f"Outcomes read: {payload.get('outcomes_read')}",
        f"Overall class: `{payload.get('overall_candidate_class')}`",
        f"Product integration: {payload.get('product_integration_candidate')}",
        f"Successor: `{payload.get('successor_candidate')}`",
        "",
        "The question is whether unsigned executed notional inside the frozen structural zone",
        "during the first 15 minutes adds information about later BREAK versus REJECT after",
        "END_POSITION_X, OTHER_VENUE_MEDIAN_MOVE, and TOUCH_OFFSET_SECONDS.",
        "",
        f"Unresolved feature-complete N={payload.get('n_unresolved_complete')}",
        f"Resolved primary N={payload.get('n_resolved')}",
        f"Late counts: {payload.get('late_counts_unresolved_complete')}",
        f"RAW_TOUCH_MATCH_RATE={payload.get('raw_touch_match_rate')}",
        "",
        "Baseline, no ZA feature",
        f"- END_POSITION_X {_pp(baseline.get('endpos_coef'))} CI {_ci(baseline.get('endpos_ci95'))}",
        f"- OTHER_VENUE_MEDIAN_MOVE {_pp(baseline.get('cv1_coef'))} CI {_ci(baseline.get('cv1_ci95'))}",
        f"- TOUCH_OFFSET_SECONDS {_pp(baseline.get('offset_coef'))} CI {_ci(baseline.get('offset_ci95'))}",
        f"- N={baseline.get('n')} clusters={baseline.get('clusters')}",
        "",
    ]
    if payload.get("note"):
        lines.extend([payload["note"], ""])
    for item in payload.get("features") or []:
        lines.extend(_feature(item))
    lines.extend([
        "No product surface was changed. No successor was started.",
        "A historical association is not a current probability and not a trading instruction.",
        "",
    ])
    return "\n".join(lines)
