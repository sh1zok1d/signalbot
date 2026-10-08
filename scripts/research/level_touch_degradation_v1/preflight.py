"""Outcome-blind counts for LEVEL_TOUCH_DEGRADATION_V1.

Reads prices and touch geometry only. Refuses to run if any touch already carries an outcome.
Does not import `outcomes.py`.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from . import constants as K
from .build import build_population
from .data import load_discovery_bars
from .inference import planning_mde, tercile_edges

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_PREFLIGHT.json"

FORBIDDEN_KEYS = ("outcome_rate", "break_rate", "reject_rate", "delta", "effect_pp", "ci", "p_value")


def _tallies(touches: list[dict]) -> dict:
    if any(t.get("outcome") is not None for t in touches):
        raise RuntimeError("preflight saw an outcome label")
    geo = Counter(t["bucket"] for t in touches)
    elig = [t for t in touches if t["feature_eligible"]]
    by_bucket = Counter(t["bucket"] for t in elig)
    by_year = Counter(int(t["year"]) for t in elig)
    by_family = Counter(t["family"] for t in elig)
    by_side = Counter(int(t["side"]) for t in elig)
    by_bucket_year = Counter((t["bucket"], int(t["year"])) for t in elig)
    by_bucket_family = Counter((t["bucket"], t["family"]) for t in elig)
    weeks = len({int(t["week"]) for t in elig})
    n = len(elig)
    n1 = by_bucket["1"]
    n2 = by_bucket["2"]
    n3 = by_bucket["3+"]
    sigmas = np.asarray([t["sigma"] for t in elig if t.get("sigma") is not None], dtype=float)
    lo, hi = tercile_edges(sigmas)
    deff = (n / weeks) if weeks else None
    max_year_share = (max(by_year.values()) / n) if n else None
    max_family_share = (max(by_family.values()) / n) if n else None
    n3_fam = {fam: by_bucket_family[("3+", fam)] for fam in K.FAMILIES}
    n3_tot = sum(n3_fam.values())
    max_family_share_3 = (max(n3_fam.values()) / n3_tot) if n3_tot else None
    return {
        "geometric": {b: int(geo[b]) for b in K.TOUCH_BUCKETS},
        "geometric_n": int(len(touches)),
        "feature_eligible_n": int(n),
        "by_bucket": {b: int(by_bucket[b]) for b in K.TOUCH_BUCKETS},
        "by_year": {str(y): int(by_year[y]) for y in K.YEARS},
        "by_family": {fam: int(by_family[fam]) for fam in K.FAMILIES},
        "by_side": {"resistance": int(by_side[1]), "support": int(by_side[-1])},
        "by_bucket_year": {f"{b}|{y}": int(by_bucket_year[(b, y)]) for b in K.TOUCH_BUCKETS for y in K.YEARS},
        "by_bucket_family": {f"{b}|{fam}": int(by_bucket_family[(b, fam)]) for b in K.TOUCH_BUCKETS
                             for fam in K.FAMILIES},
        "sigma_tercile_edges": [lo, hi],
        "week_clusters": int(weeks),
        "deff_upper": deff,
        "max_year_share": max_year_share,
        "max_family_share": max_family_share,
        "max_family_share_touch3": max_family_share_3,
        "planning_mde_deff_upper": {
            "touch2_vs_1": planning_mde(n1, n2, deff) if deff else None,
            "touch3_vs_1": planning_mde(n1, n3, deff) if deff else None,
        },
        "planning_mde_deff_1_25": {
            "touch2_vs_1": planning_mde(n1, n2, K.PLANNING_DEFF_DH1),
            "touch3_vs_1": planning_mde(n1, n3, K.PLANNING_DEFF_DH1),
        },
        "chain_stops": int(sum(1 for t in touches if t["chain_stop"])),
        "window_incomplete_48": int(sum(1 for t in touches if not t["window_ok_48"])),
        "before_event_window": int(sum(1 for t in touches if t["open_ms"] < K.EVENT_START_MS)),
        "side_unknown": int(sum(1 for t in touches if t["side"] not in (1, -1))),
    }


def _episode_counts(episodes: list[dict]) -> dict:
    c = Counter(ep["family"] for ep in episodes)
    members = Counter(ep["n_members"] for ep in episodes)
    return {"n": len(episodes), "by_family": {fam: int(c[fam]) for fam in K.FAMILIES},
            "n_members_hist": {str(k): int(v) for k, v in sorted(members.items())},
            "with_later_absorption": int(sum(1 for ep in episodes if ep["absorbed_later"]))}


def summarize(bars, built: dict, built_narrow: dict) -> dict:
    present = float(np.isfinite(bars.close).mean())
    payload = {
        "unit": K.UNIT,
        "phase": "OUTCOME_BLIND_PREFLIGHT",
        "tracks": list(K.TRACKS),
        "surface": K.SURFACE_ID,
        "data_start": K.DATA_START,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "bars": int(bars.n),
        "close_present_frac": present,
        "instance_drops": built["drops"],
        "instances_emitted": int(len(built["instances"])),
        "instances_by_kind": {k: int(sum(1 for i in built["instances"] if i["kind"] == k)) for k in K.LEVEL_KINDS},
        "primary_zone_half": K.ZONE_HALF_PRIMARY,
        "episodes": _episode_counts(built["episodes"]),
        "episode_build": built["episode_info"],
        "real": _tallies(built["touches"]),
        "control_episodes": len(built["controls"]),
        "control": _tallies(built["control_touches"]),
        "sensitivity_zone_half": K.ZONE_HALF_SENSITIVITY,
        "sensitivity_zone_real": _tallies(built_narrow["touches"]),
        "method_computable": bool(
            built["touches"] and _tallies(built["touches"])["by_bucket"]["1"] > 0
            and _tallies(built["touches"])["by_bucket"]["2"] > 0
            and _tallies(built["touches"])["by_bucket"]["3+"] > 0
        ),
        "notes": [
            "Counts are feature-eligible touches (known level, usable pre-touch sigma, complete 4h window, event window). They are not break rates.",
            "Planning MDE uses a rate of 0.5 and is an amount of information, not a gate.",
            "Ambiguous same-bar outcomes are not known here and will be excluded only at execution.",
        ],
    }
    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_KEYS:
                    raise RuntimeError(f"preflight payload contains forbidden key {key}")
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)
    _walk(payload)
    return payload


def _jsonable(node):
    if isinstance(node, dict):
        return {k: _jsonable(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_jsonable(v) for v in node]
    if isinstance(node, float) and not np.isfinite(node):
        return None
    return node


def main() -> None:
    bars = load_discovery_bars()
    primary = build_population(bars, K.ZONE_HALF_PRIMARY)
    narrow = build_population(bars, K.ZONE_HALF_SENSITIVITY)
    payload = _jsonable(summarize(bars, primary, narrow))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT),
        "feature_eligible": payload["real"]["feature_eligible_n"],
        "by_bucket": payload["real"]["by_bucket"],
        "weeks": payload["real"]["week_clusters"],
        "control_eligible": payload["control"]["feature_eligible_n"],
        "method_computable": payload["method_computable"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
