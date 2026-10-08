"""Candidate rule and routing. One primary contrast, no multiplicity adjustment."""

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


def support_gate(n_pairs: int, n_weeks: int, year_counts: dict) -> dict:
    eligible_years = []
    for year in K.YEARS:
        n = int(year_counts.get(str(year), year_counts.get(year, 0)) or 0)
        if n >= K.YEAR_MIN_N:
            eligible_years.append(int(year))
    ok = (
        int(n_pairs) >= K.PATH_PAIR_MIN
        and int(n_weeks) >= K.WEEK_MIN
        and len(eligible_years) >= K.YEAR_MIN_ELIGIBLE
    )
    return {
        "pass": ok,
        "n_pairs": int(n_pairs),
        "n_weeks": int(n_weeks),
        "years_eligible": len(eligible_years),
        "eligible_years": eligible_years,
    }


def _estimable(item: dict, min_n: int) -> bool:
    return int(item.get("n") or 0) >= min_n and item.get("delta") is not None


def year_stability(full_delta, epochs: list[dict]) -> dict:
    full = _sign(full_delta)
    eligible = [item for item in epochs if _estimable(item, K.YEAR_MIN_N)]
    matched = [item for item in eligible if _sign(item.get("delta")) == full and full != 0]
    opposite = [item for item in eligible if _sign(item.get("delta")) == -full and full != 0]
    n_eligible = len(eligible)
    if full == 0 or n_eligible < 3:
        ok = False
    elif n_eligible >= 5:
        ok = len(matched) >= K.YEAR_SIGN_MIN_OF_FIVE
    elif n_eligible == 4:
        material = [item for item in opposite if abs(float(item["delta"])) >= K.PRACTICAL_LOG]
        ok = len(matched) >= 3 and not material
    else:
        ok = len(matched) == n_eligible and n_eligible == 3
    return {"pass": ok, "n_eligible": n_eligible, "n_matched": len(matched), "n_opposite": len(opposite)}


def loyo_stability(full_delta, loyo: list[dict]) -> dict:
    full = _sign(full_delta)
    checked = [item for item in loyo if _estimable(item, K.YEAR_MIN_N)]
    if full == 0 or not checked:
        return {"pass": False, "n_checked": len(checked)}
    ok = all(_sign(item.get("delta")) == full for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def _material_opposite(left: dict, right: dict) -> bool:
    if _sign(left.get("delta")) * _sign(right.get("delta")) >= 0:
        return False
    return abs(float(left["delta"])) >= K.PRACTICAL_LOG and abs(float(right["delta"])) >= K.PRACTICAL_LOG


def family_stability(families: list[dict]) -> dict:
    by_name = {item.get("name"): item for item in families}
    day, week = by_name.get("DAY"), by_name.get("WEEK")
    day_ok = day is not None and _estimable(day, K.FAMILY_MIN_N)
    week_ok = week is not None and _estimable(week, K.FAMILY_MIN_N)
    if not day_ok or not week_ok:
        return {"pass": True, "contradiction": False, "day_estimable": day_ok, "week_estimable": week_ok}
    contradiction = _material_opposite(day, week)
    return {
        "pass": not contradiction, "contradiction": contradiction,
        "day_estimable": True, "week_estimable": True,
    }


def side_stability(sides: list[dict]) -> dict:
    by_name = {item.get("name"): item for item in sides}
    resistance, support = by_name.get("resistance"), by_name.get("support")
    r_ok = resistance is not None and _estimable(resistance, K.SIDE_MIN_N)
    s_ok = support is not None and _estimable(support, K.SIDE_MIN_N)
    if not r_ok or not s_ok:
        return {"pass": True, "contradiction": False}
    contradiction = _material_opposite(resistance, support)
    return {"pass": not contradiction, "contradiction": contradiction}


def statistical_pass(delta, ci) -> bool:
    if delta is None or abs(float(delta)) < K.PRACTICAL_LOG:
        return False
    return excludes_zero(ci)


def decide(*, blocked_key_level: bool, blocked_vol_cell: bool, pre_gate: bool, usable_gate: bool,
           delta, ci, ci_withheld: bool, epochs: list[dict], families: list[dict], sides: list[dict],
           loyo: list[dict], loyo_ran: bool, artifact: bool) -> dict:
    if blocked_key_level:
        routing = "BLOCKED_REOPENING_KEY_LEVEL_RANGE"
        klass = "NONE"
        failed = ["novelty_key_level_range"]
    elif blocked_vol_cell:
        routing = "BLOCKED_REOPENING_VOLATILITY_TRANSITION_CELL"
        klass = "NONE"
        failed = ["novelty_volatility_transition_cell"]
    elif not pre_gate or not usable_gate or ci_withheld:
        routing = "VOLATILITY_TRANSITION_INFORMATION_INSUFFICIENT"
        klass = "NONE"
        failed = ["information"]
    else:
        stat = statistical_pass(delta, ci)
        years = year_stability(delta, epochs)
        family = family_stability(families)
        side = side_stability(sides)
        leave = loyo_stability(delta, loyo) if loyo_ran else {"pass": False, "n_checked": 0}
        failed = []
        if not stat:
            failed.append("statistical")
        if artifact:
            failed.append("artifact")
        if stat:
            if not years["pass"]:
                failed.append("years")
            if not leave["pass"]:
                failed.append("loyo")
            if not family["pass"]:
                failed.append("family")
            if not side["pass"]:
                failed.append("side")
        if not failed:
            routing = "LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT"
            klass = "LEVEL_VOLATILITY_TRANSITION_CANDIDATE"
        elif stat:
            routing = "STRUCTURE_PRESENT_BUT_UNSTABLE"
            klass = "NONE"
        else:
            routing = "NO_INCREMENTAL_LEVEL_VOLATILITY_TRANSITION"
            klass = "NONE"
        return {
            "routing": routing,
            "candidate_class": klass,
            "failed": failed,
            "statistical": stat,
            "years": years,
            "family": family,
            "side": side,
            "loyo": leave,
        }
    return {
        "routing": routing,
        "candidate_class": klass,
        "failed": failed,
        "statistical": False,
        "years": year_stability(delta, epochs),
        "family": family_stability(families),
        "side": side_stability(sides),
        "loyo": {"pass": False, "n_checked": 0},
    }
