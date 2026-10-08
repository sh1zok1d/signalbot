"""English result note."""

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


def _line(item: dict) -> str:
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
            f"Surface class: `{payload.get('surface_evidence_class')}`.",
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
        f"Mode: `{payload['mode']}`.",
        f"Surface class: `{payload['surface_evidence_class']}`. Not pristine.",
        f"Routing: `{payload['routing']}`.",
        f"Evidence label: `{payload['evidence_label']}`.",
        f"Claim ceiling: {payload['claim_ceiling']}.",
        f"Independence from the resolution clock: `{payload['independence_from_resolution_clock']}`.",
        "",
        "The frozen structural first-touch volatility-transition relation discovered on Binance 2020–2024 was evaluated on time-disjoint BitMEX 2017–2019 under the unchanged 60m pre/post definition. The BitMEX surface had previously been used for a neighboring 4h barrier-path outcome, so this is an exposed-surface historical replication rather than a pristine confirmation.",
        "",
        "## Cohort",
        "",
        f"- Real legitimate first touches: {payload['real_legitimate']}",
        f"- Pseudo legitimate first touches: {payload['pseudo_legitimate']}",
        f"- Matched pairs: {payload['matched_pairs']}",
        f"- Path-complete pairs: {payload['path_complete_pairs']}",
        f"- Usable pairs: {payload['usable_pairs']}",
        f"- ISO weeks: {payload['weeks']}",
        f"- Non-positive RV drops: {payload['zero_rv']}",
        "",
        "## Realized volatility",
        "",
        f"- Real PRE60 mean/median: {_num(real['rv_pre_mean'])} / {_num(real['rv_pre_median'])}",
        f"- Real POST60 mean/median: {_num(real['rv_post_mean'])} / {_num(real['rv_post_median'])}",
        f"- Pseudo PRE60 mean/median: {_num(pseudo['rv_pre_mean'])} / {_num(pseudo['rv_pre_median'])}",
        f"- Pseudo POST60 mean/median: {_num(pseudo['rv_post_mean'])} / {_num(pseudo['rv_post_median'])}",
        f"- Real transition mean/median: {_num(real['mean'])} / {_num(real['median'])}",
        f"- Pseudo transition mean/median: {_num(pseudo['mean'])} / {_num(pseudo['median'])}",
        "",
        "## Primary",
        "",
        f"- DELTA_TRANSITION: {_num(primary['delta_log'])} ({_pct(primary['multiplicative_pct'])})",
        f"- 95% CI: {_ci(primary['ci95'])}",
        f"- CI multiplicative: {primary['ci95_multiplicative_pct']}",
        f"- SE: {_num(primary['se'])}",
        f"- Wald p: {_num(primary['p'])}",
        f"- Bootstrap: {primary['bootstrap_valid']}/{primary['bootstrap_draws']} seed {primary['bootstrap_seed']}",
        f"- Practical bar log(1.10) cleared: {primary['practical_pass']}",
        f"- CI excludes 0: {primary['ci_excludes_zero']}",
        f"- CI contains log(1.10): {primary['ci_contains_practical_bar']}",
        f"- CI contains discovery point 0.106803: {primary['ci_contains_discovery_point']}",
        "",
        "## Pre-RV balance",
        "",
        f"- Paired mean log(real pre / pseudo pre): {_num(balance['paired_log_diff_mean'])} ({_pct(balance['paired_log_diff_multiplicative_pct'])})",
        f"- Paired median of that log: {_num(balance['paired_log_diff_median'])}",
        "Not used as an adjustment.",
        "",
        "## Expansion fraction, descriptive",
        "",
        f"- Real P(transition > 0): {_num(real['expansion_fraction'])}",
        f"- Pseudo P(transition > 0): {_num(pseudo['expansion_fraction'])}",
        f"- Difference: {_num(payload['expansion_fraction_difference'])}",
        "",
        "## Epochs",
        "",
    ]
    lines.extend(_line(item) for item in payload["epochs"])
    lines.extend(["", "## Family", ""])
    lines.extend(_line(item) for item in payload["families"])
    lines.extend(["", "## Side", ""])
    lines.extend(_line(item) for item in payload["sides"])
    lines.extend(["", "## Leave-one-epoch-out", ""])
    if payload["loeo_ran"]:
        lines.extend(_line(item) for item in payload["loeo"])
    else:
        lines.append("Not run. The full sample did not clear a positive practical bar with an interval above 0.")
    lines.extend([
        "",
        "## Discovery comparison, not pooled",
        "",
        f"- Binance discovery point: {_num(payload['discovery_comparison_not_pooled']['discovery_delta_log'])} "
        f"({_pct(payload['discovery_comparison_not_pooled']['discovery_multiplicative_pct'])})",
        "- The two samples were not pooled.",
        "",
        "No product change. No prospective collection. No cross-venue unit. Clock independence remains unresolved.",
        "",
    ])
    return "\n".join(lines)
