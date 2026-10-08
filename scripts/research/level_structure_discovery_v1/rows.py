"""Structural rows for real touches and for the rotated-price control.

Does not read or write an outcome. Control rows keep the real episode's constituent
ledger and anchor formation, and they use the control touch's own time, side and X.
The rotated price is the location being tested. It is not a new source extreme.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta.hist_series import Bars

from scripts.research.level_touch_degradation_v1.constants import ZONE_HALF_PRIMARY

from . import constants as K
from .features import touch_features
from .formation import formation_of, period_catalog
from .membership import replay


def vol_tercile(sigma: Optional[float]) -> Optional[int]:
    if sigma is None or not math.isfinite(float(sigma)):
        return None
    if float(sigma) <= K.PARENT_SIGMA_LO:
        return 0
    if float(sigma) <= K.PARENT_SIGMA_HI:
        return 1
    return 2


def _birth_cache(bars: Bars, ledgers: dict[str, dict]) -> dict[str, dict]:
    catalog = period_catalog(bars)
    out = {}
    for episode_id, ledger in ledgers.items():
        out[episode_id] = formation_of(
            catalog, bars,
            family=ledger["anchor_family"],
            source_key=int(ledger["source_key"]),
            side=int(ledger["anchor_side"]),
        )
    return out


def prepare(bars: Bars, built: dict) -> dict:
    """Ledgers and birth features for the real episodes. Outcome-blind."""
    ledgers = replay(built["instances"], ZONE_HALF_PRIMARY)
    return {"ledgers": ledgers, "birth": _birth_cache(bars, ledgers)}


def _base(touch: dict, *, match_id: str, real: bool) -> Optional[dict]:
    if not touch.get("feature_eligible"):
        return None
    tercile = vol_tercile(touch.get("sigma"))
    if tercile is None or touch.get("x_primary") is None:
        return None
    bucket = touch["bucket"]
    return {
        "episode_id": touch["episode_id"],
        "match_id": match_id,
        "cluster": match_id,
        "real": 1.0 if real else 0.0,
        "population": "real" if real else "control",
        "family": touch["family"],
        "bucket": bucket,
        "touch2": 1.0 if bucket == "2" else 0.0,
        "touch3": 1.0 if bucket == "3+" else 0.0,
        "support": 1.0 if int(touch["side"]) < 0 else 0.0,
        "vol_tercile": tercile,
        "year": int(touch["year"]),
        "j": int(touch["j"]),
        "side": int(touch["side"]),
        "sigma": float(touch["sigma"]) if touch.get("sigma") is not None else None,
        "x_primary": float(touch["x_primary"]),
        "i0": int(touch["i0"]),
        "zone_low": float(touch["zone_low"]),
        "zone_high": float(touch["zone_high"]),
    }


def real_rows(touches: list[dict], prepared: dict) -> list[dict]:
    out = []
    for touch in touches:
        if touch.get("population", "real") != "real":
            continue
        ledger = prepared["ledgers"].get(touch["episode_id"])
        birth = prepared["birth"].get(touch["episode_id"])
        if ledger is None or birth is None:
            continue
        row = _base(touch, match_id=touch["episode_id"], real=True)
        if row is None:
            continue
        feat = touch_features(ledger, birth, j=int(touch["j"]), x=touch.get("x_primary"))
        if feat is None:
            continue
        row.update(feat)
        out.append(row)
    return out


def control_rows(control_touches: list[dict], controls: list[dict], prepared: dict,
                 real_episode_ids: set[str]) -> list[dict]:
    """Pseudo touches whose shadow episode is in the real feature-eligible set."""
    shadow = {ep["episode_id"]: ep.get("shadow_id") for ep in controls}
    out = []
    for touch in control_touches:
        match = shadow.get(touch["episode_id"])
        if match is None or match not in real_episode_ids:
            continue
        ledger = prepared["ledgers"].get(match)
        birth = prepared["birth"].get(match)
        if ledger is None or birth is None:
            continue
        row = _base(touch, match_id=match, real=False)
        if row is None:
            continue
        feat = touch_features(ledger, birth, j=int(touch["j"]), x=touch.get("x_primary"))
        if feat is None:
            continue
        row.update(feat)
        out.append(row)
    return out


def finite(value) -> bool:
    return value is not None and math.isfinite(float(value))


def complete(rows: list[dict], names: list[str]) -> list[dict]:
    return [row for row in rows if all(finite(row.get(name)) for name in names)]


def restrict_matched(real: list[dict], pseudo: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep episodes that have at least one row on each side.

    The set is a function of the predictor rows. It does not use an outcome.
    """
    ids = {row["cluster"] for row in real} & {row["cluster"] for row in pseudo}
    return (
        [row for row in real if row["cluster"] in ids],
        [row for row in pseudo if row["cluster"] in ids],
    )


def counts(rows: list[dict]) -> dict:
    def tally(key, transform=lambda v: v):
        out: dict[str, int] = {}
        for row in rows:
            label = str(transform(row[key]))
            out[label] = out.get(label, 0) + 1
        return out

    return {
        "n": len(rows),
        "clusters": len({row["cluster"] for row in rows}),
        "by_year": tally("year"),
        "by_family": tally("family"),
        "by_side": tally("support", lambda v: "support" if v else "resistance"),
        "by_bucket": tally("bucket"),
    }
