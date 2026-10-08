"""Official markdown rendered from the one sequence payload. No second fit."""

from __future__ import annotations

from . import constants as K


def _pp(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):.2f} pp"


def _rate(value) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * float(value):.2f}%"


def _ci(ci) -> str:
    if not ci or ci[0] is None or ci[1] is None:
        return "NA"
    return f"[{100.0 * float(ci[0]):.2f}, {100.0 * float(ci[1]):.2f}] pp"


def _mins(value) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.2f} min"


def _table(table: dict) -> list[str]:
    if not table:
        return ["not read"]
    lines = []
    for name in K.CLASSES:
        cell = table[name]
        lines.append(f"- {name}: N={cell['n']} share={_rate(cell['share'])}")
    return lines


def _slices(rows: list[dict]) -> list[str]:
    lines = []
    for row in rows:
        lines.append(
            f"- {row['name']}: delta {_pp(row.get('delta'))} "
            f"real N={row.get('n_real')} pseudo N={row.get('n_pseudo')}"
        )
    return lines


def _primary(name: str, item: dict) -> list[str]:
    if not item:
        return [f"### {name}", "", "not estimated", ""]
    return [
        f"### {name}",
        "",
        f"real {_rate(item.get('p_real'))} (N={item.get('n_real')})",
        f"pseudo {_rate(item.get('p_pseudo'))} (N={item.get('n_pseudo')})",
        f"delta {_pp(item.get('delta'))} CI {_ci(item.get('delta_ci95'))}",
        f"p={item.get('p')} q={item.get('q')} weeks={item.get('weeks')} "
        f"bootstrap={item.get('bootstrap_valid')}/{K.BOOT_DRAWS}",
        f"class `{item.get('class')}` candidate={item.get('candidate')} "
        f"statistical={item.get('statistical')} stable={item.get('stable')} "
        f"information_limited={item.get('information_limited')}",
        f"years pass={item.get('year_rule')} loyo pass={item.get('loyo_rule')}",
        f"family pass={item.get('family_rule')} side pass={item.get('side_rule')}",
        "",
        "Years",
        *_slices(item.get("years") or []),
        "LOYO",
        *_slices(item.get("loyo") or []),
        "Families",
        *_slices(item.get("families") or []),
        "Sides",
        *_slices(item.get("sides") or []),
        "",
    ]


def _delay(block: dict) -> list[str]:
    if not isinstance(block, dict) or block.get("status") == "NOT_READ":
        return ["not read"]
    lines = []
    for key, cell in block.items():
        if not isinstance(cell, dict):
            continue
        lines.append(
            f"- {key}: N={cell.get('n')} p25={_mins(cell.get('p25'))} "
            f"median={_mins(cell.get('median'))} p75={_mins(cell.get('p75'))}"
        )
    return lines


def render(payload: dict) -> str:
    primaries = payload.get("primaries") or {}
    lines = [
        f"# {payload.get('unit')}",
        "",
        f"Routing: `{payload.get('routing')}`",
        f"Claim ceiling: `{payload.get('claim_ceiling')}` / `{payload.get('exposure_status')}`",
        f"P1 class: `{payload.get('p1_class')}`",
        f"P2 class: `{payload.get('p2_class')}`",
        f"Overall candidate: `{payload.get('overall_candidate')}` {payload.get('candidate_classes')}",
        f"Sequence outcomes read: `{payload.get('outcomes_sequence_read')}`",
        f"Design SHA: `{payload.get('design_sha')}`",
        f"Product integration: `{payload.get('product_integration_candidate')}`",
        f"Successor: `{payload.get('successor_candidate')}`",
        "",
        payload.get("note") or "",
        "",
        "## Sample",
        "",
        f"Matched pairs {payload.get('n_matched')}. Labeled {payload.get('n_labeled')}. "
        f"Unusable {payload.get('n_unusable')}. Artifact `{payload.get('data_artifact')}`.",
        "",
        "## Real sequence",
        "",
        *_table(payload.get("real_table")),
        "",
        "## Pseudo sequence",
        "",
        *_table(payload.get("pseudo_table")),
        "",
        "## Primaries",
        "",
        *_primary("P1", primaries.get("P1") or {}),
        *_primary("P2", primaries.get("P2") or {}),
        "## Descriptive",
        "",
        f"Two-sided traversal: {payload.get('two_sided')}",
        f"One-sided resolution: {payload.get('one_sided')}",
        "Reversal delay",
        *_delay(payload.get("reversal_delay") or {}),
        "",
    ]
    return "\n".join(lines) + "\n"
