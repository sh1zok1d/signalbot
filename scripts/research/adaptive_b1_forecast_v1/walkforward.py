"""Chronological walk-forward with nested memory selection. Outcomes of a block never reach its own model or selection.

Grid blocks: 28-day blocks starting on Mondays 00:00 UTC. For every grid block g with start s_g, models are trained on
rows whose target is realized before s_g (close_ms + 1h <= s_g):
  CLIM     : the expanding-window mean of Y;
  STATIC   : the expanding-window ridge logistic on B1;
  FIXED_M  : the trailing M-week ridge logistic (M in 26/52/104).
Outer block k (start S_k): ADAPTIVE uses FIXED_{M*}, with M* = the memory with the lowest pooled Brier over the
INNER_BLOCKS grid blocks immediately before S_k, scored only on rows whose target is realized before S_k.
Ties within TIE_TOL go to the longer memory."""
from __future__ import annotations

import datetime as dt

import numpy as np

from . import constants as K
from . import model as M


def first_monday_at_or_after(ms: int) -> int:
    d = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    base = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    if base.timestamp() * 1000 < ms:
        base += dt.timedelta(days=1)
    base += dt.timedelta(days=(7 - base.weekday()) % 7)
    return int(base.timestamp() * 1000)


def schedule(close_ms: np.ndarray) -> dict:
    """First outer block: the first Monday with max memory + the inner window of history before it."""
    first, last = int(close_ms[0]), int(close_ms[-1])
    need = (max(K.MEMORIES_WEEKS) * 7 + K.INNER_BLOCKS * K.BLOCK_DAYS) * K.DAY_MS
    s0 = first_monday_at_or_after(first + need)
    blk = K.BLOCK_DAYS * K.DAY_MS
    grid0 = s0 - K.INNER_BLOCKS * blk
    starts = []
    s = grid0
    while s <= last:
        starts.append(s)
        s += blk
    starts = np.array(starts, dtype=np.int64)
    return {"grid_starts": starts, "first_outer_ms": s0, "outer_starts": starts[starts >= s0], "block_ms": blk}


def realized_before(close_ms: np.ndarray, t: int) -> np.ndarray:
    return close_ms + K.HOUR_MS <= t


def predict_grid(rows: dict, sched: dict, y: np.ndarray, log_coefs: bool = True) -> dict:
    """Predictions of every model for every grid block; y may be synthetic (power check)."""
    c = rows["close_ms"]
    blk = sched["block_ms"]
    preds = {name: np.full(c.size, np.nan) for name in ("CLIM", "STATIC", *[f"FIXED_{m}" for m in K.MEMORIES_WEEKS])}
    block_of = np.full(c.size, -1, dtype=np.int64)
    meta = []
    for g, s in enumerate(sched["grid_starts"]):
        tgt = np.flatnonzero((c >= s) & (c < s + blk))
        if tgt.size == 0:
            meta.append({"grid": g, "start_ms": int(s), "n": 0})
            continue
        block_of[tgt] = g
        past = realized_before(c, int(s))
        xt = M.design(rows, tgt)
        tr = np.flatnonzero(past)
        preds["CLIM"][tgt] = float(y[tr].mean())
        st = M.fit(M.design(rows, tr), y[tr])
        preds["STATIC"][tgt] = M.predict(st, xt)
        info = {"grid": g, "start_ms": int(s), "n": int(tgt.size), "static_train_n": int(tr.size),
                "static_hash": M.coef_hash(st)}
        for mem in K.MEMORIES_WEEKS:
            trm = np.flatnonzero(past & (c >= s - mem * K.WEEK_MS))
            fm = M.fit(M.design(rows, trm), y[trm])
            preds[f"FIXED_{mem}"][tgt] = M.predict(fm, xt)
            info[f"fixed_{mem}_train_n"] = int(trm.size)
            info[f"fixed_{mem}_hash"] = M.coef_hash(fm)
            if log_coefs:
                info[f"fixed_{mem}_beta"] = [float(b) for b in fm["beta"]]
        meta.append(info)
    return {"preds": preds, "block_of": block_of, "meta": meta}


def select(rows: dict, sched: dict, grid: dict, y: np.ndarray) -> dict:
    """Nested selection for every outer block, then the ADAPTIVE predictions."""
    c = rows["close_ms"]
    blk = sched["block_ms"]
    adaptive = np.full(c.size, np.nan)
    choice = np.full(c.size, -1, dtype=np.int64)
    log = []
    starts = sched["grid_starts"]
    for S in sched["outer_starts"]:
        inner = np.flatnonzero((c >= S - K.INNER_BLOCKS * blk) & (c < S) & realized_before(c, int(S)))
        scores = {}
        for mem in K.MEMORIES_WEEKS:
            p = grid["preds"][f"FIXED_{mem}"][inner]
            ok = np.isfinite(p)
            scores[mem] = float(np.mean((p[ok] - y[inner][ok]) ** 2)) if ok.any() else np.inf
        best = min(scores.values())
        chosen = max(m for m in K.MEMORIES_WEEKS if scores[m] <= best + K.TIE_TOL)
        tgt = np.flatnonzero((c >= S) & (c < S + blk))
        adaptive[tgt] = grid["preds"][f"FIXED_{chosen}"][tgt]
        choice[tgt] = chosen
        g = int(np.searchsorted(starts, S))
        log.append({"outer_start_ms": int(S), "n": int(tgt.size), "inner_rows": int(inner.size),
                    "inner_interval_ms": [int(S - K.INNER_BLOCKS * blk), int(S)],
                    "inner_brier": {str(m): scores[m] for m in K.MEMORIES_WEEKS}, "selected_memory_weeks": int(chosen),
                    "model_hash": grid["meta"][g].get(f"fixed_{chosen}_hash"),
                    "beta": grid["meta"][g].get(f"fixed_{chosen}_beta"), "train_end_ms": int(S)})
    return {"ADAPTIVE": adaptive, "choice": choice, "log": log}


def outer_mask(rows: dict, sched: dict) -> np.ndarray:
    return rows["close_ms"] >= sched["first_outer_ms"]
