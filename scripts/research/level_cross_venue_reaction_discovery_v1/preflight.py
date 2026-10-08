"""Outcome-blind census. This module must not import the late label."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble, early_census, slice_counts, unresolved_rows
from .inference import drop_redundant, freeze_scales, rough_mde, scale_hex, tertile_cuts
from .series import DATA, load_reaction_series

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1_PREFLIGHT.json"


def _dist(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"n": 0}
    qs = np.quantile(finite, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n": int(finite.size),
        "mean": float(finite.mean()),
        "sd": float(finite.std(ddof=0)),
        "p05": float(qs[0]),
        "p25": float(qs[1]),
        "p50": float(qs[2]),
        "p75": float(qs[3]),
        "p95": float(qs[4]),
    }


def _identity_artifact() -> bool:
    """Fail closed unless the frozen UTC+3 Bybit clock matches the trade tape.

    The bound is the observability rule, not a fitted price tolerance. Audited
    residuals were a few USDT. A residual above 10 USDT, or agreement below
    95 percent, means the kline is not the linear trade price.
    """
    manifest = json.loads((DATA / "MANIFEST.json").read_text())
    if manifest["venues"]["bybit"].get("clock_offset_hours") != K.BYBIT_LABEL_OFFSET_HOURS:
        return True
    if manifest["venues"]["okx"].get("clock_offset_hours") != 0:
        return True
    audits = manifest.get("trade_close_audits") or []
    if len(audits) < 2:
        return True
    for audit in audits:
        if audit.get("shift_hours") != K.BYBIT_LABEL_OFFSET_HOURS:
            return True
        if int(audit.get("bars_compared") or 0) < 200:
            return True
        if float(audit.get("close_match_rate") or 0.0) < 0.95:
            return True
        if float(audit.get("max_abs_close_diff") or 99.0) > 10.0:
            return True
    return False


def run() -> dict:
    bars = load_discovery_bars()
    venues = load_reaction_series()
    built = assemble(bars, venues)
    rows = built["real_rows"]
    unresolved = unresolved_rows(rows)
    feature_complete = [row for row in unresolved if row["feature_complete"]]
    missing = Counter()
    for row in rows:
        if row["early_status"] != "UNRESOLVED":
            continue
        for name in ("RET_BINANCE", "RET_BYBIT", "RET_OKX"):
            if row.get(name) is None:
                missing[name] += 1
    redundancy = drop_redundant(feature_complete)
    scales = freeze_scales(feature_complete)
    cuts = {name: tertile_cuts(feature_complete, name) for name in redundancy["retained"]}
    cut_hex = {
        name: {key: None if value is None else float(value).hex() for key, value in item.items()}
        for name, item in cuts.items()
    }
    pseudo_complete = [
        pair["pseudo"] for pair in built["pairs"]
        if pair["real"]["early_status"] == "UNRESOLVED" and pair["pseudo"]["early_status"] == "UNRESOLVED"
        and pair["pseudo"]["nuisance_ok"] and pair["real"]["nuisance_ok"]
    ]
    gate_n = len(feature_complete) >= K.PRE_OUTCOME_MIN_UNRESOLVED and bool(redundancy["retained"])
    payload = {
        "unit": K.UNIT,
        "outcomes_read": False,
        "tier": K.TIER,
        "venues": list(K.OTHER_VENUES),
        "reference_venue": K.REFERENCE_VENUE,
        "alignment_tolerance_ms": K.ALIGNMENT_TOLERANCE_MS,
        "event_window": [K.EVENT_START, K.EVENT_END],
        "structural_episodes": built["structural_episodes"],
        "real_status": built["real_status"],
        "pseudo_status": built["pseudo_status"],
        "first_touch_legitimate": built["real_status"]["LEGITIMATE"],
        "early": early_census(rows),
        "unresolved_nuisance_complete": len(unresolved),
        "feature_complete_unresolved": len(feature_complete),
        "resolved_after_d": None,
        "missing_among_unresolved": dict(missing),
        "slice_counts_unresolved_complete": slice_counts(feature_complete),
        "return_distributions": {
            name: _dist(np.asarray([row[name] for row in feature_complete], dtype=float))
            for name in ("RET_BINANCE", "RET_BYBIT", "RET_OKX", *K.FEATURES)
        },
        "redundancy": redundancy,
        "scales": {name: scales[name] for name in ("END_POSITION_X", "disp", *K.FEATURES)},
        "scale_hex": {name: scale_hex(scales[name]) for name in ("END_POSITION_X", "disp", *K.FEATURES)},
        "tertile_cuts": cuts,
        "tertile_cuts_hex": cut_hex,
        "pseudo_unresolved_feature_complete_pairs": len(pseudo_complete),
        "rough_mde_80": rough_mde(len(feature_complete)),
        "planning_resolve_fraction": K.PLANNING_RESOLVE_FRACTION,
        "venue_artifact": _identity_artifact(),
        "pre_outcome_gate_pass": gate_n and not _identity_artifact(),
        "history_ok": gate_n,
        "novelty_ok": True,
    }
    return payload


def main() -> None:
    payload = run()
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "legitimate": payload["first_touch_legitimate"],
        "early": payload["early"],
        "feature_complete_unresolved": payload["feature_complete_unresolved"],
        "retained": payload["redundancy"]["retained"],
        "dropped": payload["redundancy"]["dropped"],
        "mde": payload["rough_mde_80"],
        "gate": payload["pre_outcome_gate_pass"],
        "artifact": payload["venue_artifact"],
    }, indent=2))


if __name__ == "__main__":
    main()
