"""Outcome-blind matched strata for C025-R1.

Bin edges and the collapse level are functions of arm counts and pre-T
covariates only. No post-T field is an input.
"""

from __future__ import annotations

import math

import numpy as np

from .constants import MATCH_MAX_ABS_SMD, MATCH_MIN_ARM, MATCH_MIN_RETENTION

# Finest structure first. Collapse drops hour resolution, then bin count, then
# funding, then hour, then the return bin, then everything but calendar year.
LEVELS = (
    {"id": "L0_YEAR_HOUR_V3_R3_RV3_FUND", "hour": "HOUR", "bins": 3, "funding": True, "use_ret": True, "use_rv": True, "use_vol": True},
    {"id": "L1_YEAR_BLOCK_V3_R3_RV3_FUND", "hour": "BLOCK", "bins": 3, "funding": True, "use_ret": True, "use_rv": True, "use_vol": True},
    {"id": "L2_YEAR_BLOCK_V2_R2_RV2_FUND", "hour": "BLOCK", "bins": 2, "funding": True, "use_ret": True, "use_rv": True, "use_vol": True},
    {"id": "L3_YEAR_BLOCK_V2_R2_RV2", "hour": "BLOCK", "bins": 2, "funding": False, "use_ret": True, "use_rv": True, "use_vol": True},
    {"id": "L4_YEAR_V2_R2_RV2", "hour": "NONE", "bins": 2, "funding": False, "use_ret": True, "use_rv": True, "use_vol": True},
    {"id": "L5_YEAR_V2_R2", "hour": "NONE", "bins": 2, "funding": False, "use_ret": True, "use_rv": False, "use_vol": True},
    {"id": "L6_YEAR", "hour": "NONE", "bins": 1, "funding": False, "use_ret": False, "use_rv": False, "use_vol": False},
)

BALANCE_FIELDS = ("log_quote", "abs_ret", "prior_rv", "pre_impact")


def _edges(values: np.ndarray, bins: int) -> list[float]:
    if bins <= 1:
        return []
    if bins == 2:
        return [float(np.quantile(values, 0.5, method="linear"))]
    if bins == 3:
        lo, hi = np.quantile(values, [1.0 / 3.0, 2.0 / 3.0], method="linear")
        return [float(lo), float(hi)]
    raise RuntimeError("unsupported bin count")


def _assign(values: np.ndarray, edges: list[float]) -> np.ndarray:
    if not edges:
        return np.zeros(values.shape[0], dtype=np.int64)
    return np.searchsorted(np.asarray(edges, dtype=np.float64), values, side="left").astype(np.int64)


def _hour_code(hour: np.ndarray, mode: str) -> np.ndarray:
    if mode == "HOUR":
        return hour.astype(np.int64)
    if mode == "BLOCK":
        return (hour.astype(np.int64) // 3)
    if mode == "NONE":
        return np.zeros(hour.shape[0], dtype=np.int64)
    raise RuntimeError("unknown hour mode")


def _smd(x: np.ndarray, arm: np.ndarray) -> float | None:
    a = x[arm == 1]
    b = x[arm == 0]
    if a.size < 2 or b.size < 2:
        return None
    va = float(np.var(a, ddof=1))
    vb = float(np.var(b, ddof=1))
    sp = math.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / (a.size + b.size - 2))
    if sp == 0.0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / sp)


def _stratum_keys(events: dict, level: dict, edges: dict) -> np.ndarray:
    n = int(events["arm"].shape[0])
    year = events["year"].astype(np.int64)
    hour = _hour_code(events["hour"], level["hour"])
    vol = _assign(events["vol_rank"], edges["vol"] if level["use_vol"] else [])
    ret = _assign(events["abs_ret"], edges["ret"] if level["use_ret"] else [])
    rv = _assign(events["prior_rv"], edges["rv"] if level["use_rv"] else [])
    fund = events["funding"].astype(np.int64) if level["funding"] else np.zeros(n, dtype=np.int64)
    # Pack into a single integer. Ranges are small.
    return (
        year * 1_000_000
        + hour * 10_000
        + vol * 1_000
        + ret * 100
        + rv * 10
        + fund
    )


def _evaluate(events: dict, keys: np.ndarray) -> dict:
    arm = events["arm"]
    one_n = int(np.sum(arm == 1))
    two_n = int(np.sum(arm == 0))
    usable = np.zeros(arm.shape[0], dtype=bool)
    strata = 0
    orbit = 1
    for key in np.unique(keys):
        member = keys == key
        n1 = int(np.sum(member & (arm == 1)))
        n0 = int(np.sum(member & (arm == 0)))
        if n1 >= 1 and n0 >= 1:
            usable[member] = True
            strata += 1
            orbit *= math.comb(n1 + n0, n1)
    match_one = int(np.sum(usable & (arm == 1)))
    match_two = int(np.sum(usable & (arm == 0)))
    retain_one = (match_one / one_n) if one_n else 0.0
    retain_two = (match_two / two_n) if two_n else 0.0
    balance = {}
    fields = {
        "log_quote": np.log(events["quote"]),
        "abs_ret": events["abs_ret"],
        "prior_rv": events["prior_rv"],
        "pre_impact": events["pre_impact"],
    }
    max_smd = 0.0
    smd_ok = True
    for name, values in fields.items():
        stat = _smd(values[usable], arm[usable]) if np.any(usable) else None
        balance[name] = stat
        if stat is None:
            smd_ok = False
        else:
            max_smd = max(max_smd, abs(stat))
    admissible = (
        match_one >= MATCH_MIN_ARM
        and match_two >= MATCH_MIN_ARM
        and retain_one >= MATCH_MIN_RETENTION
        and retain_two >= MATCH_MIN_RETENTION
        and smd_ok
        and max_smd <= MATCH_MAX_ABS_SMD
        and orbit >= 20
    )
    return {
        "usable": usable,
        "MATCHABLE_ONE_SIDED_N": match_one,
        "MATCHABLE_TWO_SIDED_N": match_two,
        "MATCHED_STRATA_N": strata,
        "RETENTION_ONE": retain_one,
        "RETENTION_TWO": retain_two,
        "MAX_ABS_SMD": None if not smd_ok else max_smd,
        "SMD": balance,
        "PRIMARY_LABEL_ORBIT_SIZE": orbit,
        "ADMISSIBLE": admissible,
    }


def choose_matching(events: dict) -> dict:
    """First admissible collapse level, else the coarsest level marked insufficient."""
    n = int(events["arm"].shape[0])
    if n == 0:
        return {
            "STATUS": "INFERENCE_SUPPORT_INSUFFICIENT",
            "LEVEL": None,
            "EDGES": {},
            "REASON": "no admitted events",
            "MATCHABLE_ONE_SIDED_N": 0,
            "MATCHABLE_TWO_SIDED_N": 0,
            "MATCHED_STRATA_N": 0,
            "PRIMARY_LABEL_ORBIT_SIZE": 1,
            "KEYS": np.zeros(0, dtype=np.int64),
            "USABLE": np.zeros(0, dtype=bool),
            "LEVELS_TRIED": [],
        }
    edges = {
        "vol": _edges(events["vol_rank"], 3),
        "ret": _edges(events["abs_ret"], 3),
        "rv": _edges(events["prior_rv"], 3),
        "vol2": _edges(events["vol_rank"], 2),
        "ret2": _edges(events["abs_ret"], 2),
        "rv2": _edges(events["prior_rv"], 2),
        "pre_decile": [float(x) for x in np.quantile(events["pre_impact"], np.linspace(0.1, 0.9, 9), method="linear")],
    }
    tried = []
    chosen = None
    for level in LEVELS:
        bins = level["bins"]
        use_edges = {
            "vol": edges["vol"] if bins == 3 else (edges["vol2"] if bins == 2 else []),
            "ret": edges["ret"] if bins == 3 else (edges["ret2"] if bins == 2 else []),
            "rv": edges["rv"] if bins == 3 else (edges["rv2"] if bins == 2 else []),
        }
        if bins == 3 and (
            len(use_edges["vol"]) != 2 or use_edges["vol"][0] >= use_edges["vol"][1]
            or use_edges["ret"][0] >= use_edges["ret"][1]
            or use_edges["rv"][0] >= use_edges["rv"][1]
        ):
            tried.append({"id": level["id"], "ADMISSIBLE": False, "REASON": "DEGENERATE_TERTILES"})
            continue
        keys = _stratum_keys(events, level, use_edges)
        stats = _evaluate(events, keys)
        tried.append({
            "id": level["id"],
            "ADMISSIBLE": stats["ADMISSIBLE"],
            "MATCHABLE_ONE_SIDED_N": stats["MATCHABLE_ONE_SIDED_N"],
            "MATCHABLE_TWO_SIDED_N": stats["MATCHABLE_TWO_SIDED_N"],
            "MATCHED_STRATA_N": stats["MATCHED_STRATA_N"],
            "RETENTION_ONE": stats["RETENTION_ONE"],
            "RETENTION_TWO": stats["RETENTION_TWO"],
            "MAX_ABS_SMD": stats["MAX_ABS_SMD"],
            "PRIMARY_LABEL_ORBIT_SIZE": str(stats["PRIMARY_LABEL_ORBIT_SIZE"]),
        })
        if stats["ADMISSIBLE"] and chosen is None:
            chosen = (level, use_edges, keys, stats)
            break
    if chosen is None:
        # Coarsest diagnostic, still not a license to open outcomes.
        level = LEVELS[-1]
        keys = _stratum_keys(events, level, {"vol": [], "ret": [], "rv": []})
        stats = _evaluate(events, keys)
        return {
            "STATUS": "INFERENCE_SUPPORT_INSUFFICIENT",
            "LEVEL": level["id"],
            "LEVEL_SPEC": dict(level),
            "EDGES": _json_edges(edges),
            "APPLIED_EDGES": {"vol": [], "ret": [], "rv": []},
            "REASON": "no collapse level met the predeclared count, retention, balance, and orbit floors",
            "MATCHABLE_ONE_SIDED_N": stats["MATCHABLE_ONE_SIDED_N"],
            "MATCHABLE_TWO_SIDED_N": stats["MATCHABLE_TWO_SIDED_N"],
            "MATCHED_STRATA_N": stats["MATCHED_STRATA_N"],
            "RETENTION_ONE": stats["RETENTION_ONE"],
            "RETENTION_TWO": stats["RETENTION_TWO"],
            "MAX_ABS_SMD": stats["MAX_ABS_SMD"],
            "SMD": stats["SMD"],
            "PRIMARY_LABEL_ORBIT_SIZE": stats["PRIMARY_LABEL_ORBIT_SIZE"],
            "KEYS": keys,
            "USABLE": stats["usable"],
            "LEVELS_TRIED": tried,
        }
    level, use_edges, keys, stats = chosen
    return {
        "STATUS": "MATCHING_FROZEN",
        "LEVEL": level["id"],
        "LEVEL_SPEC": dict(level),
        "EDGES": _json_edges(edges),
        "APPLIED_EDGES": {k: list(v) for k, v in use_edges.items()},
        "REASON": "first predeclared level with support, retention, balance, and orbit",
        "MATCHABLE_ONE_SIDED_N": stats["MATCHABLE_ONE_SIDED_N"],
        "MATCHABLE_TWO_SIDED_N": stats["MATCHABLE_TWO_SIDED_N"],
        "MATCHED_STRATA_N": stats["MATCHED_STRATA_N"],
        "RETENTION_ONE": stats["RETENTION_ONE"],
        "RETENTION_TWO": stats["RETENTION_TWO"],
        "MAX_ABS_SMD": stats["MAX_ABS_SMD"],
        "SMD": stats["SMD"],
        "PRIMARY_LABEL_ORBIT_SIZE": stats["PRIMARY_LABEL_ORBIT_SIZE"],
        "KEYS": keys,
        "USABLE": stats["usable"],
        "LEVELS_TRIED": tried,
    }


def _json_edges(edges: dict) -> dict:
    return {key: list(value) for key, value in edges.items()}


def count_by_year_arm(events: dict, usable: np.ndarray) -> dict:
    out = {}
    for year in (2020, 2021, 2022, 2023, 2024):
        member = usable & (events["year"] == year)
        out[str(year)] = {
            "ONE_SIDED": int(np.sum(member & (events["arm"] == 1))),
            "TWO_SIDED": int(np.sum(member & (events["arm"] == 0))),
        }
    return out


def distinct_event_days(open_ms: np.ndarray, usable: np.ndarray) -> int:
    if open_ms.size == 0 or not np.any(usable):
        return 0
    days = (open_ms[usable] // 86_400_000).astype(np.int64)
    return int(np.unique(days).size)
