"""Candidate rule for the two sequence contrasts. Frozen before the sequence read."""

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


def material(delta) -> bool:
    return delta is not None and abs(float(delta)) >= K.PRACTICAL_PP


def _estimable(item: dict) -> bool:
    return (
        int(item.get("n_real") or 0) >= K.SLICE_MIN_N
        and int(item.get("n_pseudo") or 0) >= K.SLICE_MIN_N
        and item.get("delta") is not None
    )


def year_stability(full_delta, epochs: list[dict]) -> dict:
    full = _sign(full_delta)
    eligible = [item for item in epochs if _estimable(item)]
    matched = [item for item in eligible if _sign(item.get("delta")) == full and full != 0]
    opposite = [item for item in eligible if _sign(item.get("delta")) == -full and full != 0]
    n_eligible = len(eligible)
    if full == 0 or n_eligible < 3:
        ok = False
    elif n_eligible >= 5:
        ok = len(matched) >= 4
    elif n_eligible == 4:
        material_opposite = [item for item in opposite if abs(float(item["delta"])) >= K.PRACTICAL_PP]
        ok = len(matched) >= 3 and not material_opposite
    else:
        ok = len(matched) == n_eligible
    return {"pass": ok, "n_eligible": n_eligible, "n_matched": len(matched)}


def loyo_stability(full_delta, rows: list[dict]) -> dict:
    full = _sign(full_delta)
    checked = [item for item in rows if _estimable(item)]
    if full == 0 or len(checked) < 3:
        return {"pass": False, "n_checked": len(checked)}
    ok = all(_sign(item.get("delta")) == full for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def _material_opposite(left: dict, right: dict) -> bool:
    if not _estimable(left) or not _estimable(right):
        return False
    if _sign(left["delta"]) * _sign(right["delta"]) >= 0:
        return False
    return abs(float(left["delta"])) >= K.PRACTICAL_PP and abs(float(right["delta"])) >= K.PRACTICAL_PP


def family_stability(rows: list[dict]) -> dict:
    by_name = {item["name"]: item for item in rows}
    day, week = by_name.get("DAY"), by_name.get("WEEK")
    if day is None or week is None:
        return {"pass": True, "material_opposite": False}
    opposite = _material_opposite(day, week)
    return {"pass": not opposite, "material_opposite": opposite}


def side_stability(rows: list[dict]) -> dict:
    by_name = {item["name"]: item for item in rows}
    resistance, support = by_name.get("resistance"), by_name.get("support")
    if resistance is None or support is None:
        return {"pass": True, "material_opposite": False}
    opposite = _material_opposite(resistance, support)
    return {"pass": not opposite, "material_opposite": opposite}


def class_name(primary: str, delta) -> str:
    if delta is None or _sign(delta) == 0:
        return "NONE"
    if primary == "P1":
        return "BREAK_FIRST_REVERSAL_CANDIDATE" if _sign(delta) > 0 else "BREAK_FIRST_ONE_SIDED_CANDIDATE"
    return "REJECT_FIRST_REVERSAL_CANDIDATE" if _sign(delta) > 0 else "REJECT_FIRST_ONE_SIDED_CANDIDATE"


def decide_primary(primary: str, delta, ci, q, n_real: int, n_pseudo: int, *,
                   years_ok: bool, loyo_ok: bool, family_ok: bool, side_ok: bool,
                   artifact: bool) -> dict:
    """One primary. q failure is not an unstable structure."""
    info = information_limited(n_real, n_pseudo, ci)
    effect = material(delta)
    signed = excludes_zero(ci)
    if effect and signed:
        info = False
    statistical = bool(
        (not info) and effect and signed and q is not None and float(q) <= K.FDR_Q
    )
    stable = bool(years_ok and loyo_ok and family_ok and side_ok and not artifact)
    candidate = bool(statistical and stable)
    return {
        "information_limited": info,
        "statistical": statistical,
        "stable": stable,
        "candidate": candidate,
        "class": class_name(primary, delta) if candidate else "NONE",
    }


def information_limited(n_real: int, n_pseudo: int, ci) -> bool:
    if n_real < K.DENOM_GATE or n_pseudo < K.DENOM_GATE:
        return True
    if not ci or ci[0] is None or ci[1] is None:
        return True
    return (float(ci[1]) - float(ci[0])) > K.INFORMATION_CI_WIDTH


def route(features: list[dict], *, novelty_ok: bool, any_gate: bool) -> str:
    if not novelty_ok:
        return "BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE"
    if not any_gate:
        return "INFORMATION_LIMITED"
    if any(item.get("candidate") for item in features):
        return "LEVEL_SEQUENTIAL_OUTCOME_STRUCTURE_PRESENT"
    if any(item.get("statistical") and not item.get("stable") for item in features):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    read = [item for item in features if item.get("estimated")]
    if read and all(item.get("information_limited") for item in read):
        return "INFORMATION_LIMITED"
    return "NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE"
