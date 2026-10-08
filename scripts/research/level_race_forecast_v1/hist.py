"""HIST table V1 (design §0): race shares by fixed cell on CORE 2020–2024, with B0 «обычно».

`build_table` reads outcomes; it is run once after the design freeze (997ba986).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Iterable, Optional

import numpy as np

from . import constants as K

SCORED = K.OUTCOMES


def band_of(b0_beyond: float) -> str:
    lo, hi = K.BAND_EDGES
    if b0_beyond < lo:
        return "F1"
    if b0_beyond < hi:
        return "F2"
    return "F3"


def cell_key(row: dict, *, pooled_side: bool = False) -> str:
    lm = row["landmark"]
    side = "ANY" if pooled_side else ("H" if int(row["struct_side"]) > 0 else "L")
    if lm == "T0":
        return f"T0|{row['family']}|{side}"
    return f"T15|{row['family']}|{side}|{band_of(float(row['b0_beyond']))}"


def all_cell_keys() -> list[str]:
    keys = [f"T0|{f}|{s}" for f in K.FAMILIES for s in ("H", "L")]
    keys += [f"T15|{f}|{s}|{b}" for f in K.FAMILIES for s in ("H", "L") for b in K.BANDS]
    keys += [f"T15|{f}|ANY|{b}" for f in K.FAMILIES for b in K.BANDS]
    return keys


def _seed_for(key: str) -> list[int]:
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return [K.BOOT_SEED, h]


def cell_stats(key: str, rows: list[dict]) -> dict:
    ambiguous = sum(1 for r in rows if r["outcome"] == "AMBIGUOUS")
    unusable = sum(1 for r in rows if r["outcome"] is None)
    sc = [r for r in rows if r["outcome"] in SCORED]
    n = len(sc)
    out: dict = {"key": key, "n": n, "ambiguous": ambiguous, "unusable": unusable}
    if n == 0:
        out.update({"weeks": 0, "h": None, "b": None, "diff_ci95_pp": None, "k_pp": None})
        return out
    y = np.array([[r["outcome"] == o for o in SCORED] for r in sc], dtype=float)
    b = np.array([[r["b0_beyond"], r["b0_back"], r["b0_neither"]] for r in sc], dtype=float)
    weeks = np.array([r["week"] for r in sc])
    uw, inv = np.unique(weeks, return_inverse=True)
    m = uw.size
    ysum = np.zeros((m, 3))
    bsum = np.zeros((m, 3))
    cnt = np.zeros(m)
    np.add.at(ysum, inv, y)
    np.add.at(bsum, inv, b)
    np.add.at(cnt, inv, 1.0)
    rng = np.random.default_rng(_seed_for(key))
    draws = rng.integers(0, m, size=(K.BOOT_DRAWS, m))
    w = np.zeros((K.BOOT_DRAWS, m))
    for d in range(K.BOOT_DRAWS):
        w[d] = np.bincount(draws[d], minlength=m)
    tot = w @ cnt
    diff = (w @ ysum - w @ bsum) / tot[:, None]
    lo = np.quantile(diff, K.CI_ALPHA / 2, axis=0)
    hi = np.quantile(diff, 1 - K.CI_ALPHA / 2, axis=0)
    h = y.mean(axis=0)
    bm = b.mean(axis=0)
    out.update({
        "weeks": int(m),
        "h": {o: float(v) for o, v in zip(SCORED, h)},
        "b": {o: float(v) for o, v in zip(SCORED, bm)},
        "diff_pp": {o: float(100 * (h[i] - bm[i])) for i, o in enumerate(SCORED)},
        "diff_ci95_pp": {o: [float(100 * lo[i]), float(100 * hi[i])] for i, o in enumerate(SCORED)},
        "k_pp": {o: int(math.ceil(100 * (hi[i] - lo[i]) / 2 - 1e-9)) for i, o in enumerate(SCORED)},
    })
    return out


def resolve(stats: dict) -> dict:
    """Small-N ladder: T0 cell -> LOW_N; T15 cell -> family x band (sides pooled) -> LOW_N."""
    out = {}
    for key in all_cell_keys():
        parts = key.split("|")
        if parts[2] == "ANY":
            continue
        s = stats[key]
        if s["n"] >= K.N_MIN:
            out[key] = {"level": "CELL", "source": key}
            continue
        if parts[0] == "T15":
            pk = f"T15|{parts[1]}|ANY|{parts[3]}"
            if stats[pk]["n"] >= K.N_MIN:
                out[key] = {"level": "POOLED_SIDE", "source": pk}
                continue
        out[key] = {"level": "LOW_N", "source": key}
    return out


def build_table(rows: Iterable[dict], *, provenance: dict) -> dict:
    rows = list(rows)
    groups: dict[str, list] = {k: [] for k in all_cell_keys()}
    for r in rows:
        groups[cell_key(r)].append(r)
        if r["landmark"] == "T15":
            groups[cell_key(r, pooled_side=True)].append(r)
    stats = {k: cell_stats(k, v) for k, v in groups.items()}
    ladder = resolve(stats)
    body = {"version": K.HIST_TABLE_VERSION, "label": K.HIST_LABEL, "rule_id": K.RULE_ID,
            "band_edges": list(K.BAND_EDGES), "n_min": K.N_MIN, "boot": {"draws": K.BOOT_DRAWS, "seed": K.BOOT_SEED},
            "cells": stats, "ladder": ladder}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {**body, "table_sha256": digest, "provenance": provenance}


def lookup(table: dict, row: dict) -> Optional[dict]:
    """The cell statistics a live row shows, or None for LOW_N."""
    key = cell_key(row)
    lad = table["ladder"][key]
    if lad["level"] == "LOW_N":
        return None
    return {"ladder": lad, **table["cells"][lad["source"]]}
