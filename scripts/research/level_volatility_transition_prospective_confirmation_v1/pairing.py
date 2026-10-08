"""Final pseudo map. Built only when the cohort closes.

The half-rotation is the #352 procedure. This module stores geometry and
path presence. It does not store a transition.
"""

from __future__ import annotations

import hashlib
import json

from scripts.research.level_touch_degradation_v1.control import control_episodes
from scripts.research.level_touch_degradation_v1.events import touch_week
from scripts.research.level_volatility_transition_discovery_v1.windows import path_flags

from .events import active_end_ms, active_start_ms, complete_by, first_touches
from . import constants as K

_BANNED = ("rv_post", "rv_pre", "vol_transition", "transition", "pair_delta", "delta_transition")


def _public_episode(episode: dict, *, t0: int) -> dict:
    return {
        "episode_id": episode["episode_id"],
        "kind": episode["kind"],
        "family": episode["family"],
        "struct_side": int(episode["struct_side"]),
        "anchor_price": float(episode["anchor_price"]),
        "i0": int(episode["i0"]),
        "i1": int(episode["i1"]),
        "active_start_ms": active_start_ms(t0, episode),
        "active_end_ms": active_end_ms(t0, episode),
        "population": episode.get("population", "real"),
        "partner_id": episode.get("partner_id"),
        "shadow_id": episode.get("shadow_id"),
    }


def _touch_row(touch: dict) -> dict:
    row = {
        "episode_id": touch["episode_id"],
        "family": touch["family"],
        "struct_side": int(touch["struct_side"]),
        "kind": touch["kind"],
        "touch_number": int(touch["touch_number"]),
        "open_ms": int(touch["open_ms"]),
        "j": int(touch["j"]),
        "iso_week": int(touch_week(int(touch["open_ms"]))),
    }
    if int(row["touch_number"]) != 1:
        raise RuntimeError("pair map received a touch after the first")
    return row


def _keys(value) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key).lower())
            found.extend(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_keys(item))
    return found


def assert_outcome_free(payload: dict) -> None:
    found = set(_keys(payload))
    for token in _BANNED:
        if token in found:
            raise RuntimeError(f"pair map contains forbidden field {token}")


def digest_of(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "pair_map_digest"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_pair_map(bars, episodes: list[dict], instances: list[dict], *,
                   start_ms: int, checkpoint_end_ms: int, checkpoint_weeks: int) -> dict:
    """Closed-cohort geometry. Path completeness is bar presence, not RV."""
    t0 = int(bars.t0)
    closed = [
        ep for ep in episodes
        if complete_by(ep, t0=t0, checkpoint_end_ms=checkpoint_end_ms)
        and active_start_ms(t0, ep) >= int(start_ms)
    ]
    controls = control_episodes(closed, instances, K.ZONE_HALF)
    real_touches = {_touch_row(t)["episode_id"]: _touch_row(t)
                    for t in first_touches(bars, closed, end_ms=checkpoint_end_ms)}
    pseudo_touches = {_touch_row(t)["episode_id"]: _touch_row(t)
                      for t in first_touches(bars, controls, end_ms=checkpoint_end_ms)}
    pairs = []
    for ctrl in controls:
        real = real_touches.get(ctrl["shadow_id"])
        pseudo = pseudo_touches.get(ctrl["episode_id"])
        if real is None or pseudo is None:
            continue
        real_path = path_flags(bars.close, int(real["j"]))["complete"]
        pseudo_path = path_flags(bars.close, int(pseudo["j"]))["complete"]
        if not (real_path and pseudo_path):
            continue
        pairs.append({
            "real_episode_id": real["episode_id"],
            "pseudo_episode_id": pseudo["episode_id"],
            "family": real["family"],
            "struct_side": int(real["struct_side"]),
            "side_name": "resistance" if int(real["struct_side"]) == 1 else "support",
            "real_open_ms": int(real["open_ms"]),
            "pseudo_open_ms": int(pseudo["open_ms"]),
            "real_j": int(real["j"]),
            "pseudo_j": int(pseudo["j"]),
            "real_path_complete": True,
            "pseudo_path_complete": True,
            "iso_week": int(real["iso_week"]),
        })
    pairs.sort(key=lambda row: (row["real_open_ms"], row["real_episode_id"]))
    payload = {
        "unit": K.UNIT,
        "checkpoint_weeks": int(checkpoint_weeks),
        "checkpoint_end_ms": int(checkpoint_end_ms),
        "start_ms": int(start_ms),
        "n_real_episodes": len(closed),
        "n_pseudo_episodes": len(controls),
        "n_real_first_touches": len(real_touches),
        "matched_path_complete": len(pairs),
        "episodes": [_public_episode(ep, t0=t0) for ep in closed],
        "pseudo_episodes": [_public_episode(ep, t0=t0) for ep in controls],
        "real_first_touches": sorted(real_touches.values(), key=lambda row: row["open_ms"]),
        "pairs": pairs,
        "contains_transition": False,
    }
    assert_outcome_free(payload)
    payload["pair_map_digest"] = digest_of(payload)
    return payload


def main() -> None:
    raise SystemExit(
        "REFUSING_PREMATURE_COHORT_CLOSE: the frozen week and pair floors are not met"
    )


if __name__ == "__main__":
    main()
