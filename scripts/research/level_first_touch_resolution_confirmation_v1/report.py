"""Prose for the confirmation result. The sentences are fixed; the numbers come from the estimate."""

from __future__ import annotations


def _pp(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):+.1f} pp"


def _pct(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _ci(row: dict) -> str:
    if row.get("ci_low") is None or row.get("ci_high") is None:
        return "n/a"
    return f"{_pp(row['ci_low'])} .. {_pp(row['ci_high'])}"


def _line(row: dict) -> str:
    return (
        f"{row.get('name', '')} N={row.get('n')} Δ={_pp(row.get('estimate'))} "
        f"(95% {_ci(row)}); real {_pct(row.get('p_real'))}, pseudo {_pct(row.get('p_pseudo'))}"
    ).strip()


def _evidence(result: dict) -> str:
    label = result["evidence_label"]
    primary = result["primary"]
    if label == "REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE":
        return (
            "The first touch of a pre-known structural level resolved into BREAK or REJECT within "
            "4 hours more often than the matched first touch of the deterministic half-rotation "
            f"pseudo-price. Δ_resolution = {_pp(primary['estimate'])} (95% {_ci(primary)}), "
            f"N = {result['n_analysis']} pairs. Real resolution rate {_pct(primary['p_real'])}, "
            f"pseudo resolution rate {_pct(primary['p_pseudo'])}. This is a historical resolution "
            "contrast. It is not a direction and not a current probability."
        )
    if label == "NO_MATERIAL_POSITIVE_RESOLUTION_DIFFERENCE":
        return (
            f"Δ_resolution = {_pp(primary['estimate'])} (95% {_ci(primary)}), "
            f"N = {result['n_analysis']}. The 95% interval lies below +3 percentage points. "
            "That is evidence against a materially positive resolution difference of the "
            "predeclared size. Real resolution rate "
            f"{_pct(primary['p_real'])}, pseudo resolution rate {_pct(primary['p_pseudo'])}."
        )
    if label == "POSITIVE_RESOLUTION_DIFFERENCE_UNSTABLE":
        return (
            f"Δ_resolution = {_pp(primary['estimate'])} (95% {_ci(primary)}), "
            f"N = {result['n_analysis']}. The point estimate is positive, the interval excludes 0, "
            "and the estimate is at least +3 percentage points. The predeclared epoch sign rule "
            "or the leave-one-epoch-out sign rule does not hold."
        )
    if primary.get("ci_low") is None:
        return (
            f"Δ_resolution = {_pp(primary['estimate'])}, N = {result['n_analysis']}. "
            "A 95% interval was not obtained. The predeclared reading is information-limited."
        )
    return (
        f"Δ_resolution = {_pp(primary['estimate'])} (95% {_ci(primary)}), "
        f"N = {result['n_analysis']}. The interval admits a positive difference of at least "
        "+3 percentage points and also admits 0 or a negative difference. The sample does not "
        "separate those possibilities. Real resolution rate "
        f"{_pct(primary['p_real'])}, pseudo resolution rate {_pct(primary['p_pseudo'])}."
    )


def render(result: dict) -> str:
    d = result["discordant"]
    adj = result["adjusted"]
    lines = [
        "# LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1 — result",
        "",
        f"MODE = {result['mode']}.",
        f"Design note commit `{result['design_sha']}`.",
        "Tracks: STRUCTURE, PRODUCT_EVIDENCE. One official run. The primary contrast was frozen before this file existed.",
        "",
        "## evidence",
        "",
        _evidence(result),
        "",
        f"Evidence label: `{result['evidence_label']}`.",
        f"Supporting clauses: `{result['supporting_clauses']}`.",
        "",
        "## primary",
        "",
        f"Δ_resolution = {_pp(result['primary']['estimate'])}.",
        f"95% week-block interval: {_ci(result['primary'])}.",
        f"Real resolution rate: {_pct(result['primary']['p_real'])}.",
        f"Pseudo resolution rate: {_pct(result['primary']['p_pseudo'])}.",
        f"Analysis pairs: {result['n_analysis']}. Availability-matched pairs before the ambiguous drop: {result['n_matched_available']}.",
        f"Weeks in the analysis sample: {result['weeks']}.",
        f"Ambiguous real labels among availability-matched touches: {result['n_ambiguous_real']}.",
        f"Ambiguous pseudo labels among availability-matched touches: {result['n_ambiguous_pseudo']}.",
        f"Pairs excluded because either label was ambiguous: {result['n_excluded_ambiguous']}.",
        f"Pairs excluded because a label was unclassified: {result['n_excluded_unclassified']}.",
        "",
        "## discordant pairs",
        "",
        f"Both resolved: {d['both_resolved']}. Both neither: {d['both_neither']}.",
        f"Real resolved and pseudo neither: {d['real_only']}. Pseudo resolved and real neither: {d['pseudo_only']}.",
        "",
        "## adjusted sensitivity",
        "",
        f"Long-form coefficient on the real-touch indicator: {_pp(adj['estimate'])} (95% {_ci(adj)}).",
        f"Status: {adj['status']}. Columns: {', '.join(adj['columns']) or 'none'}.",
        "This coefficient does not replace the paired mean.",
        "",
        "## decomposition",
        "",
    ]
    for name in ("BREAK", "REJECT", "NEITHER"):
        row = result["decomposition"][name]
        lines.append(
            f"{name}: Δ={_pp(row['estimate'])} (95% {_ci(row)}); "
            f"real {_pct(row['p_real'])}, pseudo {_pct(row['p_pseudo'])}."
        )
    lines += ["", "## epochs", ""]
    for row in result["epochs"]:
        lines.append(_line(row))
    lines += ["", "## families", ""]
    for row in result["families"]:
        lines.append(_line(row))
    lines += ["", "## approach side of the real touch", ""]
    for row in result["sides"]:
        lines.append(_line(row))
    lines += ["", "## leave-one-epoch-out", ""]
    for row in result["leave_one_epoch_out"]:
        lines.append(_line(row))
    lines += [
        "",
        "## claim",
        "",
        f"Claim level: {result['claim_level']}. Status: {result['claim_status']}.",
        "Ceiling L2. A historical frequency is not a current probability. L3 needs prospective calibration of this claim class. L4 is not available.",
        f"Replicated historical mechanism: {result['replicated_historical_mechanism']}.",
        "",
        "## product",
        "",
        f"PRODUCT_INTEGRATION_CANDIDATE = {result['product_integration_candidate']}.",
        "No /btc, /levels, /check, /risk, scoring, findings-registry, Telegram or deploy change. Integration needs a separate owner go.",
        "",
        "## bootstrap",
        "",
        f"Draws {result['bootstrap']['draws']}, seed {result['bootstrap']['seed']}, cluster = product week of the real first touch.",
        "Each cell uses an independent stream at seed + cell index, in the order primary, BREAK, REJECT, NEITHER, three epochs, three families, two sides, three leave-one-epoch-out cuts, adjusted coefficient.",
        f"Search cells predeclared: {result['search_cells']}. No FDR screen. One primary contrast.",
        "",
        "## dataset",
        "",
        f"Surface {result['dataset']['dataset_id']}, days {result['dataset']['days']}, canonical SHA256 {result['dataset']['canonical_sha256']}.",
        f"Event window {result['event_window'][0]} inclusive to {result['event_window'][1]} exclusive.",
        f"Exposure: {result['exposure_status']}.",
        "",
        "## limitations",
        "",
        "One venue and one symbol. The surface had been used for outcome-blind DH1 feasibility counts. Same-bar barrier ties are excluded. The pseudo price is one deterministic half-rotation, not every non-structural price. The cohort is the first touch only. The endpoint is resolution into either barrier, not the direction of the move. The week block does not model every form of dependence. The discovery gap on Binance is not a required magnitude.",
        "",
        "FOLLOW_UP_IDEA: none.",
        "",
    ]
    return "\n".join(lines)
