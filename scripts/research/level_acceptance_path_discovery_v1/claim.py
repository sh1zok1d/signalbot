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


def _estimable(item: dict, min_n: int, arm_min: int) -> bool:
    if int(item.get("n") or 0) < min_n:
        return False
    if int(item.get("n_treated") or 0) < arm_min or int(item.get("n_reference") or 0) < arm_min:
        return False
    return item.get("coef") is not None


def conjunction(cell: dict, epochs: list[dict], loyo: list[dict], families: list[dict],
                sides: list[dict]) -> dict:
    """Real-cohort rule. Specificity is applied only after this passes.

    Family stability is the pair of estimable DAY and WEEK slopes. A missing
    coefficient is not a contradiction. Leave-one-family-out is not a gate.
    """
    failed = []
    coef = cell.get("coef")
    sign = _sign(coef)
    if int(cell.get("n_treated") or 0) < K.RESOLVED_ARM_MIN_N:
        failed.append("arm_n")
    if int(cell.get("n_reference") or 0) < K.RESOLVED_ARM_MIN_N:
        failed.append("arm_n")
    if not cell.get("overlap_pass"):
        failed.append("overlap")
    q = cell.get("q")
    if q is None or float(q) > K.FDR_Q:
        failed.append("fdr")
    if coef is None or abs(float(coef)) < K.PRACTICAL_SCALE:
        failed.append("scale")
    if not excludes_zero(cell.get("ci95")):
        failed.append("interval")
    if sign == 0:
        failed.append("sign")
    # A year with enough rows but no coefficient is eligible and unmatched.
    eligible_years = [
        item for item in epochs
        if int(item.get("n") or 0) >= K.YEAR_MIN_N
        and int(item.get("n_treated") or 0) >= K.YEAR_ARM_MIN
        and int(item.get("n_reference") or 0) >= K.YEAR_ARM_MIN
    ]
    matched = [item for item in eligible_years if item.get("coef") is not None and _sign(item.get("coef")) == sign]
    if len(eligible_years) < K.YEAR_SIGN_MIN or len(matched) < K.YEAR_SIGN_MIN:
        failed.append("epochs")
    for item in loyo:
        if int(item.get("n") or 0) < K.LOYO_MIN_N:
            continue
        if item.get("coef") is None or _sign(item.get("coef")) != sign:
            failed.append("loyo")
            break
    day = next((item for item in families if item.get("slice") == "DAY"), None)
    week = next((item for item in families if item.get("slice") == "WEEK"), None)
    if (
        day is not None and week is not None
        and _estimable(day, K.FAMILY_MIN_N, K.FAMILY_ARM_MIN)
        and _estimable(week, K.FAMILY_MIN_N, K.FAMILY_ARM_MIN)
        and _sign(day.get("coef")) * _sign(week.get("coef")) < 0
    ):
        failed.append("family")
    adequate = [item for item in sides if _estimable(item, K.SIDE_MIN_N, K.SIDE_ARM_MIN)]
    side_signs = {_sign(item.get("coef")) for item in adequate}
    if 1 in side_signs and -1 in side_signs:
        failed.append("side")
    seen = []
    for name in failed:
        if name not in seen:
            seen.append(name)
    return {"pass": not seen, "failed": seen}


def specificity_label(primary: dict, stacked: dict) -> str:
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
        return "LEVEL_ACCEPTANCE_PATH_CANDIDATE"
    if similar:
        return "GENERIC_PRICE_PATH_MEMORY_CANDIDATE"
    return "SPECIFICITY_UNRESOLVED"


def statistical_hit(cell: dict) -> bool:
    coef = cell.get("coef")
    q = cell.get("q")
    return (
        int(cell.get("n_treated") or 0) >= K.RESOLVED_ARM_MIN_N
        and int(cell.get("n_reference") or 0) >= K.RESOLVED_ARM_MIN_N
        and bool(cell.get("overlap_pass"))
        and q is not None
        and float(q) <= K.FDR_Q
        and coef is not None
        and abs(float(coef)) >= K.PRACTICAL_SCALE
        and excludes_zero(cell.get("ci95"))
    )


def route(decisions: list[dict], *, n_estimated: int) -> str:
    labels = [item["label"] for item in decisions]
    if "LEVEL_ACCEPTANCE_PATH_CANDIDATE" in labels:
        return "LEVEL_PATH_MEMORY_STRUCTURE_PRESENT"
    if "GENERIC_PRICE_PATH_MEMORY_CANDIDATE" in labels:
        return "GENERIC_PRICE_PATH_MEMORY_ONLY"
    if any(item.get("statistical_hit") and not item.get("conjunction_pass") for item in decisions):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if "SPECIFICITY_UNRESOLVED" in labels:
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if int(n_estimated) == 0:
        return "INFORMATION_LIMITED"
    return "NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT"
