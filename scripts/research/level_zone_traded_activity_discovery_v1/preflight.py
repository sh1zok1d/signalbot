"""Outcome-blind census. This module must not import a late label."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from scripts.research.level_cross_venue_reaction_discovery_v1.cohort import (
    assemble, early_census, slice_counts,
)
from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .features import baseline_ready, finite_feature, zone_features
from .inference import drop_redundant, freeze_scales, rough_mde, scale_hex, spearman, tertile_cuts

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1_PREFLIGHT.json"
AGGREGATES = ROOT / "docs" / "research_data" / K.TRADE_DATASET_ID / "event_aggregates.json"
INVENTORY = ROOT / "docs" / "research_data" / K.TRADE_DATASET_ID / "SOURCE_INVENTORY.json"


def _dist(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"n": 0}
    qs = np.quantile(finite, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n": int(finite.size), "mean": float(finite.mean()), "sd": float(finite.std(ddof=0)),
        "p05": float(qs[0]), "p25": float(qs[1]), "p50": float(qs[2]),
        "p75": float(qs[3]), "p95": float(qs[4]),
        "min": float(finite.min()), "max": float(finite.max()),
    }


def load_aggregates() -> tuple[dict, dict]:
    payload = json.loads(AGGREGATES.read_text())
    inventory = json.loads(INVENTORY.read_text())
    records = {row["key"]: row for row in payload["records"]}
    return records, inventory


def attach(row: dict, records: dict, population: str) -> dict:
    key = f"{population}:{row['episode_id']}"
    out = dict(row)
    out.update(zone_features(records.get(key), int(row["open_ms"])))
    out["baseline_ok"] = baseline_ready(out)
    out["population"] = population
    return out


def _overlap_pairs(rows: list[dict]) -> int:
    spans = sorted((int(row["open_ms"]), int(row["open_ms"]) + K.REACTION_MS) for row in rows)
    count = 0
    for i, (left, right) in enumerate(spans):
        for other, other_right in spans[i + 1:]:
            if other >= right:
                break
            if other < right and left < other_right:
                count += 1
    return count


def _rates(rows: list[dict]) -> dict:
    n = len(rows)
    def share(pred) -> Optional[float]:
        return None if n == 0 else sum(1 for row in rows if pred(row)) / n

    out = {"n": n, "touch_match_rate": share(lambda row: int(row.get("touch_in_zone") or 0) >= 1)}
    out["coverage_rate"] = share(lambda row: bool(row.get("trade_covered")))
    out["baseline_ready_rate"] = share(lambda row: bool(row.get("baseline_ok")))
    out["pre60_positive_rate"] = share(
        lambda row: row.get("PRE60_TOTAL_NOTIONAL") is not None and float(row["PRE60_TOTAL_NOTIONAL"]) > 0.0
    )
    for name in K.FEATURES:
        finite = [row for row in rows if finite_feature(row, name)]
        zeros = [row for row in finite if float(row[name]) == 0.0]
        out[name] = {
            "missing_rate": None if n == 0 else 1.0 - (len(finite) / n),
            "zero_rate_among_finite": None if not finite else len(zeros) / len(finite),
            "n_finite": len(finite),
        }
    return out


def _inventory_ok(inventory: dict) -> dict:
    objects = inventory.get("OBJECTS") or []
    months = [obj["MONTH"] for obj in objects]
    bad_year = [month for month in months if month < K.LOOKBACK_MONTH or month > K.LAST_MONTH]
    verified = [obj for obj in objects if obj.get("CHECKSUM_VERIFICATION") == "VERIFIED" and obj.get("SHA256")]
    identity = (
        inventory.get("ARCHIVE_ID") == K.ARCHIVE_ID
        and inventory.get("AGGRESSOR_SIDE_USED") is False
        and inventory.get("RAW_RETAINED") is False
        and "BTCUSDT" in str(inventory.get("INSTRUMENT"))
        and "USD-M" in str(inventory.get("INSTRUMENT"))
    )
    return {
        "source_identity_ok": identity,
        "n_objects": len(objects),
        "n_verified": len(verified),
        "checksums_verified": len(objects) > 0 and len(verified) == len(objects),
        "protected_months": bad_year,
        "no_protected_year": not bad_year,
        "months": months,
        "aggregates_sha256": inventory.get("AGGREGATES_SHA256"),
        "object_list_sha256": inventory.get("OBJECT_LIST_SHA256"),
        "n_multi_event_trades": inventory.get("N_MULTI_EVENT_TRADES"),
        "double_counts_across_events": inventory.get("DOUBLE_COUNTS_ACROSS_EVENTS"),
    }


def run() -> dict:
    records, inventory = load_aggregates()
    bars = load_discovery_bars()
    venues = load_reaction_series()
    built = assemble(bars, venues)
    real = [attach(row, records, "real") for row in built["real_rows"]]
    pseudo = [attach(pair["pseudo"], records, "pseudo") for pair in built["pairs"]]
    touch = _rates(real)
    pseudo_touch = _rates(pseudo)
    unresolved = [row for row in real if row.get("early_status") == "UNRESOLVED" and row.get("nuisance_ok")]
    ready = [row for row in unresolved if row.get("baseline_ok")]
    complete_all = [row for row in ready if all(finite_feature(row, name) for name in K.FEATURES)]
    redundancy = drop_redundant(complete_all, K.FEATURES)
    retained = list(redundancy["retained"])
    support = [row for row in ready if all(finite_feature(row, name) for name in retained)] if retained else []
    per_feature = {
        name: sum(1 for row in ready if finite_feature(row, name)) for name in retained
    }
    scales = freeze_scales(support, tuple(retained))
    cuts = {name: tertile_cuts(support, name) for name in retained}
    cut_hex = {
        name: {key: None if value is None else float(value).hex() for key, value in item.items()}
        for name, item in cuts.items()
    }
    context_rho = {}
    for name in retained:
        for control in ("END_POSITION_X", K.CV1_NAME, K.OFFSET_NAME, "disp"):
            context_rho[f"{name}__{control}"] = spearman(support, name, control)
    audit = _inventory_ok(inventory)
    match_rate = touch["touch_match_rate"] or 0.0
    pseudo_rate = pseudo_touch["touch_match_rate"] or 0.0
    touch_ok = match_rate >= K.TOUCH_MATCH_MIN
    pseudo_ok = pseudo_rate >= K.TOUCH_MATCH_MIN
    expected = len(support) * K.PLANNING_RESOLVE_FRACTION
    gate = (
        audit["source_identity_ok"]
        and audit["checksums_verified"]
        and touch_ok
        and audit["no_protected_year"]
        and len(support) >= K.PRE_OUTCOME_MIN_UNRESOLVED
        and expected >= K.INFORMATION_MIN_RESOLVED
        and bool(retained)
    )
    payload = {
        "unit": K.UNIT,
        "outcomes_read": False,
        "novelty_ok": K.NOVELTY_OK,
        "event_window": ["2020-04-01T00:05:00Z", "2025-01-01T00:00:00Z"],
        "lookback_month": K.LOOKBACK_MONTH,
        "structural_episodes": built["structural_episodes"],
        "real_status": built["real_status"],
        "pseudo_status": built["pseudo_status"],
        "first_touch_legitimate": built["real_status"]["LEGITIMATE"],
        "early": early_census(real),
        "unresolved_nuisance": len(unresolved),
        "unresolved_baseline_ready": len(ready),
        "feature_complete_unresolved": len(support),
        "per_feature_complete": per_feature,
        "resolved_after_d": None,
        "raw_touch_match_rate": match_rate,
        "pseudo_touch_match_rate": pseudo_rate,
        "touch_identity_pass": touch_ok,
        "pseudo_identity_ok": pseudo_ok,
        "real_trade_audit": touch,
        "pseudo_trade_audit": pseudo_touch,
        "unresolved_trade_audit": _rates(unresolved),
        "overlapping_reaction_windows": _overlap_pairs(real),
        "inventory": audit,
        "redundancy": redundancy,
        "retained": retained,
        "context_rho": context_rho,
        "slice_counts_unresolved_complete": slice_counts(support),
        "distributions": {
            name: _dist(np.asarray([row.get(name, math.nan) for row in support], dtype=float))
            for name in ("END_POSITION_X", K.CV1_NAME, K.OFFSET_NAME, *retained)
        },
        "scales": scales,
        "scale_hex": {name: scale_hex(scales[name]) for name in scales if name != "n"},
        "tertile_cuts_hex": cut_hex,
        "rough_mde_80": rough_mde(len(support)),
        "planning_resolve_fraction": K.PLANNING_RESOLVE_FRACTION,
        "expected_primary_n": expected,
        "identity_artifact": not touch_ok or not audit["checksums_verified"] or not audit["no_protected_year"],
        "pre_outcome_gate_pass": gate,
        "aggressor_side_used": False,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload
