"""Candidate rule and routing. No coefficient is estimated here."""

from __future__ import annotations

from . import constants as K


def _sign(value) -> int:
    if value is None:
        return 0
    value = float(value)
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def excludes_zero(ci) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return float(ci[0]) > 0.0 or float(ci[1]) < 0.0


def _slice_ok(item: dict, sign: int, min_n: int) -> bool:
    if int(item.get("n") or 0) < min_n:
        return True
    coef = item.get("coef")
    if coef is None:
        return False
    return _sign(coef) == sign


def conjunction(cell: dict, epochs: list[dict], loeo: list[dict], lofo: list[dict],
                sides: list[dict]) -> dict:
    """Real-cohort rule. Specificity is applied only after this passes."""
    failed = []
    coef = cell.get("coef")
    sign = _sign(coef)
    if int(cell.get("n") or 0) < K.MIN_CELL_N:
        failed.append("n")
    q = cell.get("q")
    if q is None or float(q) > K.FDR_Q:
        failed.append("fdr")
    if coef is None or abs(float(coef)) < K.PRACTICAL_SCALE:
        failed.append("scale")
    if not excludes_zero(cell.get("ci95")):
        failed.append("interval")
    if sign == 0:
        failed.append("sign")
    slots = [item for item in epochs if int(item.get("n") or 0) >= K.EPOCH_MIN_N]
    if len(slots) < K.EPOCH_SIGN_MIN or any(
        item.get("coef") is None or _sign(item.get("coef")) != sign for item in slots
    ):
        failed.append("epochs")
    if any(not _slice_ok(item, sign, K.EPOCH_MIN_N) for item in loeo):
        failed.append("loeo")
    for item in lofo:
        if int(item.get("n") or 0) < K.FAMILY_COMPLEMENT_MIN_N:
            continue
        if item.get("coef") is None or _sign(item.get("coef")) != sign:
            failed.append("family")
            break
    adequate = [
        item for item in sides
        if int(item.get("n") or 0) >= K.SIDE_MIN_N and item.get("coef") is not None
    ]
    side_signs = {_sign(item.get("coef")) for item in adequate}
    if 1 in side_signs and -1 in side_signs:
        failed.append("side")
    seen = []
    for name in failed:
        if name not in seen:
            seen.append(name)
    return {"pass": not seen, "failed": seen}


def specificity_label(primary: dict, stacked: dict) -> str:
    """Apply only when the real conjunction passed."""
    delta = stacked.get("delta")
    beta_real = stacked.get("beta_real")
    beta_pseudo = stacked.get("beta_pseudo")
    sign = _sign(primary.get("coef"))
    material = (
        delta is not None
        and abs(float(delta)) >= K.SPECIFICITY_SCALE
        and excludes_zero(stacked.get("ci95"))
        and beta_real is not None
        and beta_pseudo is not None
        and abs(float(beta_real)) > abs(float(beta_pseudo))
        and _sign(beta_real) == sign
        and _sign(delta) == sign
    )
    similar = (
        not material
        and beta_pseudo is not None
        and primary.get("coef") is not None
        and _sign(beta_pseudo) == sign
        and abs(float(beta_pseudo)) >= K.SIMILARITY_RATIO * abs(float(primary["coef"]))
    )
    if material:
        return "LEVEL_LIQUIDITY_INTERACTION_CANDIDATE"
    if similar:
        return "GENERIC_LIQUIDITY_STATE_CANDIDATE"
    return "SPECIFICITY_UNRESOLVED"


def statistical_hit(cell: dict) -> bool:
    coef = cell.get("coef")
    q = cell.get("q")
    return (
        int(cell.get("n") or 0) >= K.MIN_CELL_N
        and q is not None
        and float(q) <= K.FDR_Q
        and coef is not None
        and abs(float(coef)) >= K.PRACTICAL_SCALE
        and excludes_zero(cell.get("ci95"))
    )


def route(decisions: list[dict], *, n_resolve: int, clusters: int) -> str:
    labels = [item["label"] for item in decisions]
    if "LEVEL_LIQUIDITY_INTERACTION_CANDIDATE" in labels:
        return "LEVEL_LIQUIDITY_STRUCTURE_PRESENT"
    if "GENERIC_LIQUIDITY_STATE_CANDIDATE" in labels:
        return "GENERIC_LIQUIDITY_STATE_ONLY"
    if any(item.get("statistical_hit") and not item.get("conjunction_pass") for item in decisions):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if "SPECIFICITY_UNRESOLVED" in labels:
        # Real conjunction passed, but the pseudo contrast is neither specific nor similar.
        # That is not a named candidate. The allowed route for an association that cannot
        # be assigned a candidate class is STRUCTURE_PRESENT_BUT_UNSTABLE.
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if n_resolve < K.INFO_MIN_N or clusters < K.INFO_MIN_CLUSTERS:
        return "INFORMATION_LIMITED"
    return "NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE"
