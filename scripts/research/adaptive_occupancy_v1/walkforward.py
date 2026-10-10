"""Venue-aware nested walk-forward for the occupancy-timescale selector. A block's outcomes never reach its own
models or its own selection.

Per venue (BitMEX; Binance 2020-26): grid blocks of 28 days from Mondays 00:00 UTC. The first outer block is the first
Monday with (26 + 24) weeks of venue history. For every grid block g (start s_g), on venue rows whose 1h label is
realized by s_g (close_ms + 1h <= s_g):
  CLIM        expanding-window mean of Y;
  B1          expanding-window logistic on B1;
  STATIC_OCC4 expanding-window logistic on B1 + OCC_4H;
  (M, c)      trailing-M-week logistic on B1 (c = NO_OCC) or B1 + OCC_L, for every memory M with s_g - M weeks at or
              after the venue's first anchor.
ADAPTIVE for outer block S: the (M, c) with the lowest pooled Brier over the 6 grid blocks before S (rows realized by
S), ties -> log loss -> NO_OCC, then the longer memory, then the shorter lookback. Memories eligible at S are those
whose inner models all had a full window (S - 24 weeks - M weeks >= venue first anchor)."""
from __future__ import annotations

import datetime as dt

import numpy as np

from scripts.research.adaptive_b1_forecast_v1 import model as M

from . import constants as K


def first_monday_at_or_after(ms: int) -> int:
    d = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    base = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    if base.timestamp() * 1000 < ms:
        base += dt.timedelta(days=1)
    base += dt.timedelta(days=(7 - base.weekday()) % 7)
    return int(base.timestamp() * 1000)


def block_ms() -> int:
    return K.BLOCK_DAYS * K.DAY_MS


def schedule(rows: dict) -> dict:
    out = {}
    blk = block_ms()
    for v in sorted(set(rows["venue"].tolist())):
        c = rows["close_ms"][rows["venue"] == v]
        first, last = int(c[0]), int(c[-1])
        s0 = first_monday_at_or_after(first + (min(K.MEMORIES_WEEKS) * 7 + K.INNER_BLOCKS * K.BLOCK_DAYS) * K.DAY_MS)
        starts, s = [], s0 - K.INNER_BLOCKS * blk
        while s <= last:
            starts.append(s)
            s += blk
        starts = np.array(starts, dtype=np.int64)
        out[int(v)] = {"first_ms": first, "last_ms": last, "first_outer_ms": s0, "grid_starts": starts,
                       "outer_starts": starts[starts >= s0]}
    return out


def eligible_memories(S: int, first_ms: int) -> list:
    return [m for m in K.MEMORIES_WEEKS if S - K.INNER_BLOCKS * block_ms() - m * K.WEEK_MS >= first_ms]


def realized_by(close_ms: np.ndarray, t: int) -> np.ndarray:
    return close_ms + K.HOUR_MS <= t


def design(rows: dict, ix: np.ndarray, config: str) -> np.ndarray:
    x = M.design(rows, ix)                                   # B1: RP4H-0.5, RET_4H/RV, RET_1H/RV, RET_15M/RV, log RV
    if config == K.NO_OCC:
        return x
    return np.column_stack([x, rows[config][ix] - 0.5])


def predict_grid(rows: dict, sched: dict, y: np.ndarray, log_models: bool = True) -> dict:
    n = rows["close_ms"].size
    c = rows["close_ms"]
    blk = block_ms()
    preds = {"CLIM": np.full(n, np.nan), "B1": np.full(n, np.nan), "STATIC_OCC4": np.full(n, np.nan)}
    for mem in K.MEMORIES_WEEKS:
        for cfg in K.CONFIGS:
            preds[(mem, cfg)] = np.full(n, np.nan)
    meta = {}
    for v, sv in sched.items():
        inv = rows["venue"] == v
        for s in sv["grid_starts"]:
            s = int(s)
            tgt = np.flatnonzero(inv & (c >= s) & (c < s + blk))
            if tgt.size == 0:
                continue
            past = inv & realized_by(c, s)
            tr = np.flatnonzero(past)
            preds["CLIM"][tgt] = float(y[tr].mean())
            info = {"venue": v, "start_ms": s, "n": int(tgt.size), "expanding_train_n": int(tr.size)}
            for name, cfg in (("B1", K.NO_OCC), ("STATIC_OCC4", K.STATIC_OCC)):
                m = M.fit(design(rows, tr, cfg), y[tr])
                preds[name][tgt] = M.predict(m, design(rows, tgt, cfg))
                info[f"{name}_hash"] = M.coef_hash(m)
            for mem in K.MEMORIES_WEEKS:
                if s - mem * K.WEEK_MS < sv["first_ms"]:
                    continue
                trm = np.flatnonzero(past & (c >= s - mem * K.WEEK_MS))
                info[f"train_n_{mem}"] = int(trm.size)
                for cfg in K.CONFIGS:
                    m = M.fit(design(rows, trm, cfg), y[trm])
                    preds[(mem, cfg)][tgt] = M.predict(m, design(rows, tgt, cfg))
                    if log_models:
                        info[f"{mem}|{cfg}"] = {"hash": M.coef_hash(m),
                                                "beta_occ": None if cfg == K.NO_OCC else float(m["beta"][-1])}
            meta[(v, s)] = info
    return {"preds": preds, "meta": meta}


def _losses(p, y):
    from scripts.research.adaptive_b1_forecast_v1.metrics import brier, logloss
    return float(np.mean(brier(p, y))), float(np.mean(logloss(p, y)))


def _order_key(cand):
    mem, cfg = cand
    occ_rank = -1 if cfg == K.NO_OCC else K.LOOKBACK_HOURS.index(int(cfg.split("_")[1][:-1]))
    return (0 if cfg == K.NO_OCC else 1, -mem, occ_rank)


def choose(scores: dict) -> tuple:
    """scores[(mem, cfg)] = (brier, logloss). Lowest Brier; ties within TIE_TOL by log loss; then the fixed order."""
    best_b = min(v[0] for v in scores.values())
    cand = [k for k, v in scores.items() if v[0] <= best_b + K.TIE_TOL]
    best_l = min(scores[k][1] for k in cand)
    cand = [k for k in cand if scores[k][1] <= best_l + K.TIE_TOL]
    return sorted(cand, key=_order_key)[0]


def select(rows: dict, sched: dict, grid: dict, y: np.ndarray) -> dict:
    n = rows["close_ms"].size
    c = rows["close_ms"]
    blk = block_ms()
    adaptive, mm = np.full(n, np.nan), np.full(n, np.nan)
    log = []
    for v, sv in sched.items():
        inv = rows["venue"] == v
        for S in sv["outer_starts"]:
            S = int(S)
            inner = np.flatnonzero(inv & (c >= S - K.INNER_BLOCKS * blk) & (c < S) & realized_by(c, S))
            elig = eligible_memories(S, sv["first_ms"])
            scores = {}
            for mem in elig:
                for cfg in K.CONFIGS:
                    p = grid["preds"][(mem, cfg)][inner]
                    if not np.isfinite(p).all():
                        raise SystemExit("INNER_PREDICTION_MISSING")
                    scores[(mem, cfg)] = _losses(p, y[inner])
            mem, cfg = choose(scores)
            tgt = np.flatnonzero(inv & (c >= S) & (c < S + blk))
            adaptive[tgt] = grid["preds"][(mem, cfg)][tgt]
            mm[tgt] = grid["preds"][(mem, K.NO_OCC)][tgt]
            info = grid["meta"].get((v, S), {})
            best_no = min((scores[(m, K.NO_OCC)] for m in elig), key=lambda t: t[0])
            log.append({"venue": K.VENUES[v], "outer_start_ms": S, "outer_end_ms": S + blk, "train_end_ms": S,
                        "inner_interval_ms": [S - K.INNER_BLOCKS * blk, S], "inner_rows": int(inner.size),
                        "eligible_memories": elig, "selected_memory_weeks": mem, "selected_config": cfg,
                        "inner_brier": scores[(mem, cfg)][0], "inner_logloss": scores[(mem, cfg)][1],
                        "inner_best_no_occ_brier": best_no[0], "n_outer": int(tgt.size),
                        "model": info.get(f"{mem}|{cfg}")})
    return {"ADAPTIVE": adaptive, "MM_NO_OCC": mm, "log": log}


def outer_mask(rows: dict, sched: dict) -> np.ndarray:
    m = np.zeros(rows["close_ms"].size, dtype=bool)
    for v, sv in sched.items():
        m |= (rows["venue"] == v) & (rows["close_ms"] >= sv["first_outer_ms"])
    return m
