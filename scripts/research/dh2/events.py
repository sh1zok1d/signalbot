"""DH2 events, states and nuisance on several coins, point-in-time at the decision boundary.

The per-bar rules are DH1's, imported unchanged (`scripts/research/dh1/events.py`): first-touch
levels, dedupe, staleness, flow terms, volatility scale, hour block and ISO week. DH2 adds the
coin dimension, its own surfaces and epochs, drops round-number levels and computes terciles
within each coin. No outcome is computed here.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta.hist_series import Bars
from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import events as E1

from . import constants as K


def epoch_of(ms: int, epochs: list) -> Optional[str]:
    for name, a, z in epochs:
        if K._ms(a) <= ms < K._ms(z):
            return name
    return None


def level_events(b: Bars, spot: Optional[dict], symbol: str, start_ms: int, end_ms: int, epochs: list) -> list:
    sigma = E1.rolling_sigma(b.close)
    touches = [t for t in E1.raw_level_touches(b) if t[1] in K.LEVEL_TYPES]
    out = []
    for j, typ, lvl, side in E1.dedupe_touches(touches):
        T = E1.decision_ms(b, j)
        if T < start_ms or T + K1.HOLD_BARS * K1.BAR_MS > end_ms or j + K1.HOLD_BARS >= b.n:
            continue
        c, c_lag = b.close[j], (b.close[j - K1.LAG_BARS] if j >= K1.LAG_BARS else np.nan)
        flow = E1.flow_terms(b, spot, j - K1.APPROACH_BARS + 1, j, side) if spot is not None else {}
        out.append({
            "SYMBOL": symbol, "J": int(j), "T_MS": int(T), "TYPE": typ, "TYPE_GROUP": K.TYPE_GROUP[typ], "LEVEL": lvl,
            "SIDE": int(side), "EPOCH": epoch_of(T, epochs), "WEEK": E1.week_of(T), "HOUR_BLOCK": E1.hour_block(T),
            "RV": float(sigma[j]) if math.isfinite(sigma[j]) else None,
            "LAG": float(side * math.log(c / c_lag)) if (math.isfinite(c) and math.isfinite(c_lag)) else None,
            "PERP_IMB": flow.get("PERP_IMB"),
            "SPOT_CONFIRMED_APPROACH": (None if flow.get("SPOT_NET") is None else bool(flow["SPOT_NET"] > 0)),
            "STALE_LEVEL": E1.stale(b, j, lvl)})
    return out


def move_events(b: Bars, spot: dict, symbol: str, start_ms: int, end_ms: int, epochs: list) -> list:
    """DH1's sharp-move rule (2x the pre-move 1h scale over 15 minutes, one per hour)."""
    sigma = E1.rolling_sigma(b.close)
    c = b.close
    out = []
    i = K1.MOVE_BARS + K1.SCALE_BARS + 1
    last_event = -10 ** 9
    while i < b.n:
        if i - last_event <= K1.MOVE_REFRACTORY_BARS:
            i += 1
            continue
        c0, c1, sg = c[i - K1.MOVE_BARS], c[i], sigma[i - K1.MOVE_BARS]
        if not (math.isfinite(c0) and math.isfinite(c1) and math.isfinite(sg)) or sg <= 0 \
                or not np.isfinite(c[i - K1.MOVE_BARS:i + 1]).all():
            i += 1
            continue
        move = math.log(c1 / c0)
        ratio = abs(move) / (sg * math.sqrt(12))
        if ratio < K1.MOVE_RATIO_MIN or move == 0:
            i += 1
            continue
        last_event = i
        T = E1.decision_ms(b, i)
        if T < start_ms or T + K1.HOLD_BARS * K1.BAR_MS > end_ms or i + K1.HOLD_BARS >= b.n:
            i += 1
            continue
        d = 1 if move > 0 else -1
        a, z = i - K1.MOVE_BARS + 1, i
        flow = E1.flow_terms(b, spot, a, z, d)
        c_lag = c[i - K1.MOVE_BARS - K1.LAG_BARS] if i - K1.MOVE_BARS - K1.LAG_BARS >= 0 else np.nan
        share_move = share_base = None
        sq_base = E1.window_sum(spot["quote"], a - K1.SCALE_BARS, a - 1)
        pq_base = E1.window_sum(b.quote, a - K1.SCALE_BARS, a - 1)
        if flow["SPOT_QUOTE"] is not None and flow["PERP_QUOTE"] is not None and sq_base is not None and pq_base is not None:
            if flow["SPOT_QUOTE"] + flow["PERP_QUOTE"] > 0 and sq_base + pq_base > 0:
                share_move = flow["SPOT_QUOTE"] / (flow["SPOT_QUOTE"] + flow["PERP_QUOTE"])
                share_base = sq_base / (sq_base + pq_base)
        x = K1.BARRIER_FRACTION * K1.CORRIDOR_Z * sg * math.sqrt(K1.HOLD_BARS)
        out.append({"SYMBOL": symbol, "J": int(i), "T_MS": int(T), "DIR": d, "RATIO": float(ratio), "X": float(x),
                    "EPOCH": epoch_of(T, epochs), "WEEK": E1.week_of(T), "HOUR_BLOCK": E1.hour_block(T), "RV": float(sg),
                    "LAG": float(d * math.log(c0 / c_lag)) if math.isfinite(c_lag) else None,
                    "PERP_IMB": flow["PERP_IMB"],
                    "SPOT_SHARE_HIGH_MOVE": (None if share_move is None else bool(share_move > share_base))})
        i += 1
    return out


def _terciles_within_symbol(rows: list, key: str) -> list:
    out = [None] * len(rows)
    for sym in sorted({r["SYMBOL"] for r in rows}):
        idx = [k for k, r in enumerate(rows) if r["SYMBOL"] == sym]
        t = E1.tercile([rows[k].get(key) for k in idx])
        for k, v in zip(idx, t):
            out[k] = v
    return out


def nuisance_names(h: dict) -> tuple:
    return tuple(K.NUISANCE_COMMON) + tuple(K.CARDS[h["CARD"]]["NUISANCE_EXTRA"]) + tuple(h["NUISANCE_EXTRA"])


def cell_rows(events: list, h: dict) -> list:
    """Events of one cell with complete state and nuisance; terciles within each coin (frozen rule)."""
    names = nuisance_names(h)
    need = ["RV", "LAG"] + (["PERP_IMB"] if "PERP_IMB_TERCILE" in names else []) + \
           (["RATIO"] if "MOVE_TERCILE" in names else [])
    rows = [e for e in events if e.get(h["STATE"]) is not None and e["EPOCH"] is not None
            and all(e.get(k) is not None for k in need)]
    terc = {"RV_TERCILE": _terciles_within_symbol(rows, "RV"), "LAG_TERCILE": _terciles_within_symbol(rows, "LAG"),
            "PERP_IMB_TERCILE": _terciles_within_symbol(rows, "PERP_IMB") if "PERP_IMB" in need else [None] * len(rows),
            "MOVE_TERCILE": _terciles_within_symbol(rows, "RATIO") if "RATIO" in need else [None] * len(rows)}
    out = []
    for k, e in enumerate(rows):
        r = dict(e)
        r["S"] = int(bool(e[h["STATE"]]))
        for name, vals in terc.items():
            r[name] = vals[k]
        out.append(r)
    return out


def design_matrix(rows: list, h: dict, levels: Optional[dict] = None) -> tuple:
    names = nuisance_names(h)
    if levels is None:
        levels = {n: sorted({r[n] for r in rows}, key=str) for n in names}
    cols = [np.ones(len(rows)), np.array([r["S"] for r in rows], dtype=float)]
    labels = ["INTERCEPT", "S"]
    for n in names:
        for lv in levels[n][1:]:
            cols.append(np.array([1.0 if r[n] == lv else 0.0 for r in rows]))
            labels.append(f"{n}={lv}")
    return np.column_stack(cols), labels, levels
