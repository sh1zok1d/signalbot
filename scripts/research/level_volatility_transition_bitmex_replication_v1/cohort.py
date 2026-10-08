"""#357 first-touch pairs plus the #368 path flags. No barrier label and no RV."""

from __future__ import annotations

from scripts.research.level_first_touch_resolution_confirmation_v1.cohort import (
    first_touch_status,
    iter_episode_links,
    population,
)
from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_volatility_transition_discovery_v1.windows import path_flags

from . import constants as K


def assemble(bars) -> dict:
    built = population(bars)
    keys = (
        "NO_TOUCH", "OUTSIDE_WINDOW", "INCOMPLETE_4H", "UNKNOWN_SIDE", "UNUSABLE_X", "LEGITIMATE",
    )
    real_counts = {name: 0 for name in keys}
    pseudo_counts = {name: 0 for name in keys}
    pseudo_counts["NO_CONTROL"] = 0
    pairs = []
    close = bars.close
    t0 = int(bars.t0)
    for episode, real, ctrl, pseudo in iter_episode_links(built):
        _refuse_label(real)
        _refuse_label(pseudo)
        real_status = first_touch_status(
            real, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS,
        )
        real_counts[real_status] += 1
        if ctrl is None:
            pseudo_counts["NO_CONTROL"] += 1
            pseudo_status = "NO_CONTROL"
        else:
            pseudo_status = first_touch_status(
                pseudo, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS,
            )
            pseudo_counts[pseudo_status] += 1
        if real_status == "LEGITIMATE" and pseudo_status == "LEGITIMATE":
            pairs.append(_pair(episode, real, pseudo, close, t0))
    path_pairs = [pair for pair in pairs if pair["path_complete"]]
    return {
        "structural_episodes": len(built["episodes"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_legitimate": real_counts["LEGITIMATE"],
        "pseudo_legitimate": pseudo_counts["LEGITIMATE"],
        "matched_pairs": len(pairs),
        "path_complete_pairs": len(path_pairs),
        "slices_path": _slices(path_pairs),
        "pairs": pairs,
    }


def _refuse_label(touch) -> None:
    if touch is None:
        return
    if touch.get("outcome") not in (None,):
        raise RuntimeError("a touch already carries a resolution label")


def _arm(touch: dict, close, t0: int) -> dict:
    j = int(touch["j"])
    if t0 + j * PARENT.BAR_MS != int(touch["open_ms"]):
        raise RuntimeError("touch bar j does not match its open time")
    if int(touch["touch_number"]) != 1:
        raise RuntimeError("a legitimate pair contained a touch other than 1")
    return {"j": j, "open_ms": int(touch["open_ms"]), "flags": path_flags(close, j)}


def _pair(episode: dict, real: dict, pseudo: dict, close, t0: int) -> dict:
    from scripts.research.level_first_touch_resolution_confirmation_v1.constants import epoch_of_ms

    side = int(real["side"])
    real_arm = _arm(real, close, t0)
    pseudo_arm = _arm(pseudo, close, t0)
    epoch = epoch_of_ms(int(real["open_ms"]))
    if epoch not in K.EPOCHS:
        raise RuntimeError(f"legitimate touch epoch {epoch} is outside 2017H2/2018/2019")
    return {
        "episode_id": episode["episode_id"],
        "family": episode["family"],
        "epoch": epoch,
        "week": int(real["week"]),
        "side_name": "resistance" if side > 0 else "support",
        "real": real_arm,
        "pseudo": pseudo_arm,
        "path_complete": bool(real_arm["flags"]["complete"] and pseudo_arm["flags"]["complete"]),
    }


def _slices(pairs: list[dict]) -> dict:
    epoch = {name: 0 for name in K.EPOCHS}
    family = {name: 0 for name in K.FAMILIES}
    side = {"resistance": 0, "support": 0}
    for pair in pairs:
        epoch[pair["epoch"]] += 1
        family[pair["family"]] = family.get(pair["family"], 0) + 1
        side[pair["side_name"]] += 1
    return {
        "epoch": epoch,
        "family": family,
        "side": side,
        "weeks": len({int(pair["week"]) for pair in pairs}),
    }
