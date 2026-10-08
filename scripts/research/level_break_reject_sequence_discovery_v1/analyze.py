"""One read of post-first opposite-barrier sequences. Imported only by the evaluator."""

from __future__ import annotations

import json
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import constants as K
from .claim import (
    decide_primary,
    family_stability,
    loyo_stability,
    route,
    side_stability,
    year_stability,
)
from .inference import bh_adjust, bootstrap_contrast, contrast
from .sequence import reversal_flag, sequence_class


def load_frozen(path=None) -> dict:
    from . import preflight
    target = path or preflight.OUT
    return json.loads(target.read_text())


def should_scan(first: Optional[str], gates: dict) -> bool:
    """Opposite-barrier scan is allowed only for a direction whose denominator gate passed."""
    if first == "BREAK":
        return bool(gates.get("P1"))
    if first == "REJECT":
        return bool(gates.get("P2"))
    return first in ("NEITHER", "AMBIGUOUS")


def _parent(high, low, touch: dict):
    return classify(
        high, low, int(touch["j"]), int(touch["side"]),
        float(touch["zone_low"]), float(touch["zone_high"]),
        float(touch["x_primary"]), K.HORIZON_BARS,
    )


def _label(high, low, touch: dict, gates: dict) -> dict:
    first = _parent(high, low, touch)
    if first is None:
        return {"status": "UNUSABLE", "class": None, "first": None, "delay_min": None}
    if not should_scan(first, gates):
        return {"status": "GATE_CLOSED", "class": None, "first": first, "delay_min": None}
    return sequence_class(
        high, low, int(touch["j"]), int(touch["side"]),
        float(touch["zone_low"]), float(touch["zone_high"]), float(touch["x_primary"]),
    )


def _flag(row: dict, primary: str) -> float:
    value = reversal_flag(row.get("class"), primary)
    return np.nan if value is None else float(value)


def _point(real_flags: np.ndarray, pseudo_flags: np.ndarray, mask: np.ndarray) -> dict:
    rr = real_flags[mask]
    pp = pseudo_flags[mask]
    got = contrast(rr[np.isfinite(rr)], pp[np.isfinite(pp)])
    if got is None:
        return {"n_real": 0, "n_pseudo": 0, "delta": None, "p_real": None, "p_pseudo": None}
    return got


def _table(names: list[str]) -> dict:
    n = len(names)
    out = {}
    for key in K.CLASSES:
        count = sum(1 for name in names if name == key)
        out[key] = {"n": count, "share": (count / n) if n else None}
    return out


def _quartiles(delays: list[float]) -> dict:
    if not delays:
        return {"n": 0, "p25": None, "median": None, "p75": None}
    arr = np.asarray(delays, dtype=float)
    p25, med, p75 = np.quantile(arr, [0.25, 0.5, 0.75])
    return {"n": int(arr.size), "p25": float(p25), "median": float(med), "p75": float(p75)}


def _rate(names: list[str], keys: tuple[str, ...]) -> Optional[float]:
    if not names:
        return None
    return sum(1 for name in names if name in keys) / len(names)


def run(bars, built: dict, frozen: dict) -> dict:
    gates = dict(frozen.get("gates") or {})
    high, low = bars.high, bars.low
    rows = []
    unusable = 0
    for pair in built["pairs"]:
        real_parent = _parent(high, low, pair["real"])
        pseudo_parent = _parent(high, low, pair["pseudo"])
        if real_parent is None or pseudo_parent is None:
            unusable += 1
            continue
        real_row = _label(high, low, pair["real"], gates)
        pseudo_row = _label(high, low, pair["pseudo"], gates)
        rows.append({**pair, "real_row": real_row, "pseudo_row": pseudo_row})
    table_complete = bool(gates.get("P1") and gates.get("P2"))
    real_names = [row["real_row"]["class"] for row in rows]
    pseudo_names = [row["pseudo_row"]["class"] for row in rows]
    if table_complete:
        for names in (real_names, pseudo_names):
            if any(name not in K.CLASSES for name in names):
                raise RuntimeError("sequence class is missing from the frozen six")
            if sum(1 for name in names if name in K.CLASSES) != len(names):
                raise RuntimeError("sequence classes are not a partition")
    real_flags = {
        "P1": np.asarray([_flag(row["real_row"], "P1") for row in rows], dtype=float),
        "P2": np.asarray([_flag(row["real_row"], "P2") for row in rows], dtype=float),
    }
    pseudo_flags = {
        "P1": np.asarray([_flag(row["pseudo_row"], "P1") for row in rows], dtype=float),
        "P2": np.asarray([_flag(row["pseudo_row"], "P2") for row in rows], dtype=float),
    }
    weeks = np.asarray([row["week"] for row in rows], dtype=int)
    years = np.asarray([row["year"] for row in rows], dtype=int)
    families = np.asarray([row["family"] for row in rows], dtype=object)
    sides = np.asarray([row["side_name"] for row in rows], dtype=object)
    fitted = []
    for name in K.PRIMARIES:
        if not gates.get(name):
            continue
        fitted.append(bootstrap_contrast(weeks, real_flags[name], pseudo_flags[name]))
        fitted[-1]["name"] = name
    qs = bh_adjust([item.get("p") for item in fitted]) if fitted else []
    for item, q in zip(fitted, qs):
        item["q"] = q
    artifact = unusable > 0
    primaries = {}
    features = []
    for item in fitted:
        name = item["name"]
        epochs = [{"name": str(year), **_point(real_flags[name], pseudo_flags[name], years == year)}
                  for year in K.YEARS]
        loyo = [{"name": f"omit_{year}", **_point(real_flags[name], pseudo_flags[name], years != year)}
                for year in K.YEARS]
        family_rows = [{"name": fam, **_point(real_flags[name], pseudo_flags[name], families == fam)}
                       for fam in K.FAMILIES]
        side_rows = [{"name": side, **_point(real_flags[name], pseudo_flags[name], sides == side)}
                     for side in ("resistance", "support")]
        years_rule = year_stability(item["delta"], epochs)
        leave_rule = loyo_stability(item["delta"], loyo)
        family_rule = family_stability(family_rows)
        side_rule = side_stability(side_rows)
        decision = decide_primary(
            name, item["delta"], item["delta_ci95"], item["q"],
            int(item["n_real"]), int(item["n_pseudo"]),
            years_ok=years_rule["pass"], loyo_ok=leave_rule["pass"],
            family_ok=family_rule["pass"], side_ok=side_rule["pass"],
            artifact=artifact,
        )
        packed = {
            **item,
            **decision,
            "years": epochs,
            "loyo": loyo,
            "families": family_rows,
            "sides": side_rows,
            "year_rule": years_rule,
            "loyo_rule": leave_rule,
            "family_rule": family_rule,
            "side_rule": side_rule,
        }
        primaries[name] = packed
        features.append({"name": name, "estimated": True, **decision})
    if artifact:
        for item in features:
            item["candidate"] = False
        for packed in primaries.values():
            packed["candidate"] = False
            packed["class"] = "NONE"
    routing = route(
        features, novelty_ok=bool(frozen.get("novelty_ok")),
        any_gate=any(gates.get(name) for name in K.PRIMARIES),
    )
    if artifact:
        routing = "INFORMATION_LIMITED"
    two_sided_keys = ("BREAK_THEN_REJECT", "REJECT_THEN_BREAK", "FIRST_AMBIGUOUS")
    one_sided_keys = ("BREAK_NO_LATER_REJECT", "REJECT_NO_LATER_BREAK")
    if table_complete:
        real_two = _rate(real_names, two_sided_keys)
        pseudo_two = _rate(pseudo_names, two_sided_keys)
        real_one = _rate(real_names, one_sided_keys)
        pseudo_one = _rate(pseudo_names, one_sided_keys)
        two_sided = {
            "status": "DESCRIPTIVE",
            "real": real_two,
            "pseudo": pseudo_two,
            "delta": None if real_two is None or pseudo_two is None else real_two - pseudo_two,
            "n": len(real_names),
        }
        one_sided = {
            "status": "DESCRIPTIVE",
            "real": real_one,
            "pseudo": pseudo_one,
            "delta": None if real_one is None or pseudo_one is None else real_one - pseudo_one,
            "n": len(real_names),
        }
        delays = {
            "real_BREAK_THEN_REJECT": _quartiles([
                row["real_row"]["delay_min"] for row in rows
                if row["real_row"]["class"] == "BREAK_THEN_REJECT" and row["real_row"]["delay_min"] is not None
            ]),
            "pseudo_BREAK_THEN_REJECT": _quartiles([
                row["pseudo_row"]["delay_min"] for row in rows
                if row["pseudo_row"]["class"] == "BREAK_THEN_REJECT" and row["pseudo_row"]["delay_min"] is not None
            ]),
            "real_REJECT_THEN_BREAK": _quartiles([
                row["real_row"]["delay_min"] for row in rows
                if row["real_row"]["class"] == "REJECT_THEN_BREAK" and row["real_row"]["delay_min"] is not None
            ]),
            "pseudo_REJECT_THEN_BREAK": _quartiles([
                row["pseudo_row"]["delay_min"] for row in rows
                if row["pseudo_row"]["class"] == "REJECT_THEN_BREAK" and row["pseudo_row"]["delay_min"] is not None
            ]),
        }
        real_table = _table(real_names)
        pseudo_table = _table(pseudo_names)
    else:
        two_sided = {"status": "NOT_READ"}
        one_sided = {"status": "NOT_READ"}
        delays = {"status": "NOT_READ"}
        real_table = None
        pseudo_table = None
    classes = [primaries[name]["class"] for name in primaries if primaries[name]["candidate"]]
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "outcomes_sequence_read": True,
        "first_event_type_already_exposed": True,
        "novelty_ok": bool(frozen.get("novelty_ok")),
        "source_main": K.SOURCE_MAIN_HEAD,
        "dependencies": {"touch": K.DEP_TOUCH, "path": K.DEP_PATH, "clock": K.DEP_CLOCK},
        "practical_pp": K.PRACTICAL_PP,
        "fdr_q": K.FDR_Q,
        "bootstrap_draws": K.BOOT_DRAWS,
        "bootstrap_seed": K.BOOT_SEED,
        "n_matched": built["matched_pairs"],
        "n_unusable": unusable,
        "n_labeled": len(rows),
        "data_artifact": artifact,
        "table_complete": table_complete,
        "first_event": frozen.get("first_event"),
        "gates": gates,
        "real_table": real_table,
        "pseudo_table": pseudo_table,
        "primaries": primaries,
        "two_sided": two_sided,
        "one_sided": one_sided,
        "reversal_delay": delays,
        "p1_class": primaries.get("P1", {}).get("class", "NONE"),
        "p2_class": primaries.get("P2", {}).get("class", "NONE"),
        "overall_candidate": bool(classes),
        "candidate_classes": classes,
        "routing": routing,
        "note": (
            "Discovery only. A historical difference in post-first barrier sequence "
            "is not a current false-break probability and not an acceptance probability."
        ),
    }
