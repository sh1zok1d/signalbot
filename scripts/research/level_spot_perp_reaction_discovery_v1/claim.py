"""Candidate rule, matched specificity, and routing."""

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


def _estimable(item: dict, min_n: int) -> bool:
    return int(item.get("n") or 0) >= min_n and item.get("coef") is not None


def year_stability(full_coef, epochs: list[dict]) -> dict:
    full = _sign(full_coef)
    eligible = [item for item in epochs if _estimable(item, K.YEAR_MIN_N)]
    matched = [item for item in eligible if _sign(item.get("coef")) == full and full != 0]
    opposite = [item for item in eligible if _sign(item.get("coef")) == -full and full != 0]
    n_eligible = len(eligible)
    if full == 0 or n_eligible < 3:
        ok = False
    elif n_eligible >= 5:
        ok = len(matched) >= K.YEAR_SIGN_MIN_OF_FIVE
    elif n_eligible == 4:
        material = [item for item in opposite if abs(float(item["coef"])) >= K.MATERIAL_OPPOSITE]
        ok = len(matched) >= 3 and not material
    else:
        material = [item for item in opposite if abs(float(item["coef"])) >= K.MATERIAL_OPPOSITE]
        ok = len(matched) == 3 or (len(matched) >= 2 and not material and len(opposite) <= 1)
    return {"pass": ok, "n_eligible": n_eligible, "n_matched": len(matched), "n_opposite": len(opposite)}


def loyo_stability(full_coef, loyo: list[dict]) -> dict:
    full = _sign(full_coef)
    checked = [item for item in loyo if int(item.get("n") or 0) >= K.LOYO_MIN_N]
    if full == 0 or len(checked) < 3:
        return {"pass": False, "n_checked": len(checked)}
    ok = all(item.get("coef") is not None and _sign(item.get("coef")) == full for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def family_stability(families: list[dict]) -> dict:
    by_name = {item.get("name"): item for item in families}
    day, week = by_name.get("DAY"), by_name.get("WEEK")
    day_ok = day is not None and _estimable(day, K.FAMILY_MIN_N)
    week_ok = week is not None and _estimable(week, K.FAMILY_MIN_N)
    if not day_ok or not week_ok:
        return {"pass": True, "contradiction": False, "day_estimable": day_ok, "week_estimable": week_ok}
    contradiction = _sign(day.get("coef")) * _sign(week.get("coef")) < 0
    return {"pass": not contradiction, "contradiction": contradiction,
            "day_estimable": True, "week_estimable": True}


def side_stability(sides: list[dict]) -> dict:
    by_name = {item.get("name"): item for item in sides}
    resistance, support = by_name.get("resistance"), by_name.get("support")
    r_ok = resistance is not None and _estimable(resistance, K.SIDE_MIN_N)
    s_ok = support is not None and _estimable(support, K.SIDE_MIN_N)
    if not r_ok or not s_ok:
        return {"pass": True, "contradiction": False}
    contradiction = _sign(resistance.get("coef")) * _sign(support.get("coef")) < 0
    return {"pass": not contradiction, "contradiction": contradiction}


def statistical_pass(cell: dict) -> bool:
    coef = cell.get("coef")
    if coef is None or abs(float(coef)) < K.PRACTICAL_SCALE:
        return False
    if not excludes_zero(cell.get("ci95")):
        return False
    q = cell.get("q")
    if q is None or float(q) > K.FDR_Q:
        return False
    if not cell.get("includes_end_position") or not cell.get("includes_cv1"):
        return False
    return True


def support_sensitive(full_coef, matched_real) -> bool:
    """Full-sample slope and matched real slope disagree.

    Disagreement is an opposite sign, or a matched slope inside 3 pp while the
    full-sample slope cleared that scale. A missing matched slope is not itself
    this disagreement; the caller records it as not estimated.
    """
    if full_coef is None or matched_real is None:
        return False
    if _sign(full_coef) == 0:
        return False
    if _sign(matched_real) != _sign(full_coef):
        return True
    if abs(float(full_coef)) >= K.PRACTICAL_SCALE and abs(float(matched_real)) < K.PRACTICAL_SCALE:
        return True
    return False


def specificity_pass(matched: dict, full_coef) -> bool:
    if matched.get("status") != "ESTIMATED":
        return False
    if support_sensitive(full_coef, matched.get("beta_real")):
        return False
    delta = matched.get("delta")
    if delta is None or abs(float(delta)) < K.SPECIFICITY_SCALE:
        return False
    return excludes_zero(matched.get("delta_ci95"))


def conjunction(cell: dict, epochs: list[dict], loyo: list[dict], families: list[dict],
                sides: list[dict], *, identity_artifact: bool) -> dict:
    failed = []
    if identity_artifact:
        failed.append("identity_artifact")
    if not statistical_pass(cell):
        failed.append("statistical")
    years = year_stability(cell.get("coef"), epochs)
    if not years["pass"]:
        failed.append("years")
    leave = loyo_stability(cell.get("coef"), loyo)
    if not leave["pass"]:
        failed.append("loyo")
    family = family_stability(families)
    if not family["pass"]:
        failed.append("family")
    side = side_stability(sides)
    if not side["pass"]:
        failed.append("side")
    return {
        "pass": not failed,
        "failed": failed,
        "years": years,
        "loyo": leave,
        "family": family,
        "side": side,
        "statistical": statistical_pass(cell),
    }


def information_limited(n_resolved: int, cells: list[dict]) -> bool:
    if n_resolved < K.INFORMATION_MIN_RESOLVED:
        return True
    precise = False
    for cell in cells:
        ci = cell.get("ci95")
        if ci and ci[0] is not None and ci[1] is not None and (float(ci[1]) - float(ci[0])) <= K.INFORMATION_CI_WIDTH:
            precise = True
    return not precise


def route(features: list[dict], *, n_resolved: int, history_ok: bool, novelty_ok: bool) -> str:
    if not novelty_ok:
        return "BLOCKED_REOPENING_SPOT_CONFIRMATION_CELL"
    if not history_ok:
        return "SPOT_PERP_REACTION_INFORMATION_INSUFFICIENT"
    if any(item.get("candidate_class") == "LEVEL_SPOT_PERP_INTERACTION_CANDIDATE" for item in features):
        return "LEVEL_SPOT_PERP_STRUCTURE_PRESENT"
    if any(item.get("specificity_status") == "SUPPORT_SENSITIVE" for item in features):
        return "SPECIFICITY_NOT_ESTABLISHED_SUPPORT_SENSITIVE"
    if any(item.get("candidate_class") == "GENERIC_SPOT_PERP_REACTION_CANDIDATE" for item in features):
        return "GENERIC_SPOT_PERP_REACTION_STRUCTURE"
    if any(item.get("statistical") and not item.get("conjunction_pass") for item in features):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if information_limited(n_resolved, features):
        return "INFORMATION_LIMITED"
    return "NO_INCREMENTAL_SPOT_PERP_REACTION"
