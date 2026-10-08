"""English result note. The user report is separate."""

from __future__ import annotations


def _num(value, digits=6):
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}g}"


def _pct(value):
    if value is None:
        return "n/a"
    return f"{float(value):+.3f}%"


def _ci(ci):
    if not ci:
        return "withheld"
    return f"[{_num(ci[0])} .. {_num(ci[1])}]"


def _slice_line(item: dict) -> str:
    return (
        f"- {item.get('name')}: N={item.get('n')} delta={_num(item.get('delta'))} "
        f"({_pct(item.get('multiplicative_pct'))})"
    )


def render(payload: dict) -> str:
    if not payload.get("outcomes_read"):
        return "\n".join([
            f"# {payload['unit']}",
            "",
            "Outcomes were not read.",
            "",
            f"Routing: `{payload['routing']}`.",
            "",
            payload.get("note") or "",
            "",
        ])
    primary = payload["primary"]
    real = payload["real"]
    pseudo = payload["pseudo"]
    balance = payload["pre_rv_balance"]
    lines = [
        f"# {payload['unit']}",
        "",
        f"Routing: `{payload['routing']}`.",
        f"Class: `{payload['candidate_class']}`.",
        f"Claim ceiling: {payload['claim_ceiling']} / {payload['exposure_status']}.",
        "LEVEL_ENGINE_DISCOVERY_8_OF_8_COMPLETE = YES.",
        "",
        "## Cohort",
        "",
        f"- Real legitimate first touches: {payload['real_legitimate']}",
        f"- Pseudo legitimate first touches: {payload['pseudo_legitimate']}",
        f"- Matched pairs: {payload['matched_pairs']}",
        f"- Path-complete pairs: {payload['path_complete_pairs']}",
        f"- Usable pairs (both RV finite and positive): {payload['usable_pairs']}",
        f"- ISO weeks: {payload['weeks']}",
        f"- Non-positive RV drops: {payload['zero_rv']}",
        "",
        "## Realized volatility",
        "",
        f"- Real PRE60 mean/median: {_num(real['rv_pre_mean'])} / {_num(real['rv_pre_median'])}",
        f"- Real POST60 mean/median: {_num(real['rv_post_mean'])} / {_num(real['rv_post_median'])}",
        f"- Pseudo PRE60 mean/median: {_num(pseudo['rv_pre_mean'])} / {_num(pseudo['rv_pre_median'])}",
        f"- Pseudo POST60 mean/median: {_num(pseudo['rv_post_mean'])} / {_num(pseudo['rv_post_median'])}",
        (
            f"- Real transition mean/median/p25/p75: {_num(real['mean'])} / {_num(real['median'])} / "
            f"{_num(real['p25'])} / {_num(real['p75'])}"
        ),
        (
            f"- Pseudo transition mean/median/p25/p75: {_num(pseudo['mean'])} / {_num(pseudo['median'])} / "
            f"{_num(pseudo['p25'])} / {_num(pseudo['p75'])}"
        ),
        "",
        "## Primary",
        "",
        f"- DELTA_TRANSITION: {_num(primary['delta_log'])} log units",
        f"- Multiplicative: {_pct(primary['multiplicative_pct'])}",
        f"- CI95: {_ci(primary['ci95'])}",
        f"- p: {_num(primary['p'])}",
        f"- Bootstrap: {primary['bootstrap_valid']}/{primary['bootstrap_draws']} seed {primary['bootstrap_seed']}",
        f"- Practical 10% pass: {primary['practical_pass']}",
        f"- CI excludes 0: {primary['ci_excludes_zero']}",
        "",
        "## Pre-RV balance",
        "",
        (
            f"- Paired log(pre real / pre pseudo) mean: {_num(balance['paired_log_diff_mean'])} "
            f"({_pct(balance['paired_log_diff_multiplicative_pct'])})"
        ),
        f"- At or above the 10% scale: {balance['imbalance_at_practical_scale']}",
        "",
        "## Expansion fraction (descriptive)",
        "",
        f"- Real P(transition > 0): {_num(real['expansion_fraction'])}",
        f"- Pseudo P(transition > 0): {_num(pseudo['expansion_fraction'])}",
        f"- Difference: {_num(payload['expansion_fraction_difference'])}",
        "",
        "## Years",
        "",
    ]
    lines.extend(_slice_line(item) for item in payload["years"])
    lines.extend(["", "## Family", ""])
    lines.extend(_slice_line(item) for item in payload["families"])
    lines.extend(["", "## Side", ""])
    lines.extend(_slice_line(item) for item in payload["sides"])
    lines.extend(["", "## Leave-one-year-out", ""])
    if payload["loyo_ran"]:
        lines.extend(_slice_line(item) for item in payload["loyo"])
    else:
        lines.append("- not run; the full primary did not clear magnitude and the interval together")
    lines.extend([
        "",
        "## Stability",
        "",
        f"`{payload['stability']}`",
        "",
        "No product integration. No confirmation. No successor. The 8-step discovery sequence stops here.",
        "",
    ])
    return "\n".join(lines)
