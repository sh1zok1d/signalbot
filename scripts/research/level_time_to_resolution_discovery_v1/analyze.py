"""One read of resolution times. Imported only by the official evaluator."""

from __future__ import annotations

import json

import numpy as np

from . import constants as K
from .claim import (
    candidate_pass,
    excludes_zero,
    family_stability,
    information_limited,
    loyo_stability,
    material,
    route,
    side_stability,
    year_stability,
)
from .clock import km_inputs, resolution_clock
from .inference import bootstrap_delta, paired_rmut
from .survival import summarize


def load_frozen(path=None) -> dict:
    from . import preflight
    target = path or preflight.OUT
    return json.loads(target.read_text())


def _clock_touch(high, low, touch: dict) -> dict:
    return resolution_clock(
        high, low, int(touch["j"]), int(touch["side"]),
        float(touch["zone_low"]), float(touch["zone_high"]), float(touch["x_primary"]),
    )


def _arrays(clocks: list[dict]):
    return km_inputs(clocks)


def _subset_delta(real_t, real_e, pseudo_t, pseudo_e, mask) -> dict:
    if int(mask.sum()) == 0:
        return {"n": 0, "delta": None, "real": None, "pseudo": None}
    got = paired_rmut(real_t[mask], real_e[mask], pseudo_t[mask], pseudo_e[mask])
    if got is None:
        return {"n": 0, "delta": None, "real": None, "pseudo": None}
    return got


def run(bars, built: dict, frozen: dict) -> dict:
    high, low = bars.high, bars.low
    usable = []
    unusable = 0
    for pair in built["pairs"]:
        real_clock = _clock_touch(high, low, pair["real"])
        pseudo_clock = _clock_touch(high, low, pair["pseudo"])
        if real_clock["status"] == "UNUSABLE" or pseudo_clock["status"] == "UNUSABLE":
            unusable += 1
            continue
        usable.append({**pair, "real_clock": real_clock, "pseudo_clock": pseudo_clock})
    real_t, real_e, real_k = _arrays([row["real_clock"] for row in usable])
    pseudo_t, pseudo_e, pseudo_k = _arrays([row["pseudo_clock"] for row in usable])
    weeks = np.asarray([row["week"] for row in usable], dtype=int)
    years = np.asarray([row["year"] for row in usable], dtype=int)
    families = np.asarray([row["family"] for row in usable], dtype=object)
    sides = np.asarray([row["side_name"] for row in usable], dtype=object)
    primary = bootstrap_delta(weeks, real_t, real_e, pseudo_t, pseudo_e)
    real_summary = summarize(real_t, real_e, real_k)
    pseudo_summary = summarize(pseudo_t, pseudo_e, pseudo_k)
    epochs = []
    for year in K.YEARS:
        got = _subset_delta(real_t, real_e, pseudo_t, pseudo_e, years == year)
        epochs.append({"name": str(year), **got})
    loyo = []
    for year in K.YEARS:
        got = _subset_delta(real_t, real_e, pseudo_t, pseudo_e, years != year)
        loyo.append({"name": f"omit_{year}", **got})
    family_rows = []
    for name in K.FAMILIES:
        got = _subset_delta(real_t, real_e, pseudo_t, pseudo_e, families == name)
        family_rows.append({"name": name, **got})
    side_rows = []
    for name in ("resistance", "support"):
        got = _subset_delta(real_t, real_e, pseudo_t, pseudo_e, sides == name)
        side_rows.append({"name": name, **got})
    years_rule = year_stability(primary["delta"], epochs)
    leave_rule = loyo_stability(primary["delta"], loyo)
    family_rule = family_stability(family_rows)
    side_rule = side_stability(side_rows)
    artifact = unusable > 0
    passed = candidate_pass(
        primary["delta"], primary["delta_ci95"],
        years_ok=years_rule["pass"], loyo_ok=leave_rule["pass"],
        family_ok=family_rule["pass"], side_ok=side_rule["pass"],
        artifact=artifact, n=int(primary["n"]),
    )
    effect = material(primary["delta"])
    signed = excludes_zero(primary["delta_ci95"])
    stable = years_rule["pass"] and leave_rule["pass"] and family_rule["pass"] and side_rule["pass"]
    info = information_limited(int(primary["n"]), primary["delta_ci95"])
    # A wide interval that still excludes 0 and clears 15 minutes is not an information failure.
    if effect and signed:
        info = False
    if artifact:
        routing = "INFORMATION_LIMITED"
        passed = False
    else:
        routing = route(
            novelty_ok=True, gate_pass=bool(frozen.get("pre_outcome_gate_pass")),
            candidate=passed, material_effect=effect, ci_excludes_0=signed,
            stable=stable, info_limited=info,
        )
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "outcomes_read": True,
        "novelty_ok": True,
        "source_main": K.SOURCE_MAIN_HEAD,
        "dependencies": {
            "touch": K.DEP_TOUCH,
            "confirm": K.DEP_CONFIRM,
            "reaction": K.DEP_REACTION,
            "cross_venue": K.DEP_CROSS,
            "spot": K.DEP_SPOT,
        },
        "n_matched_geometric": built["matched_pairs"],
        "n_unusable_clock": unusable,
        "n_primary": int(primary["n"]),
        "primary": primary,
        "real": real_summary,
        "pseudo": pseudo_summary,
        "years": epochs,
        "loyo": loyo,
        "families": family_rows,
        "sides": side_rows,
        "year_rule": years_rule,
        "loyo_rule": leave_rule,
        "family_rule": family_rule,
        "side_rule": side_rule,
        "data_artifact": artifact,
        "candidate": passed,
        "candidate_class": "LEVEL_RESOLUTION_CLOCK_CANDIDATE" if passed else "NONE",
        "routing": routing,
        "note": (
            "Discovery only. A historical difference in unresolved time is not a current "
            "expected number of minutes and not a statement that a level expires."
        ),
    }
