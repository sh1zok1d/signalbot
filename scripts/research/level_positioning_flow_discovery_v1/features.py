"""PIT positioning and aggressive-flow features. No outcome is read.

OI change is outstanding-open-interest expansion or contraction.
Oriented taker imbalance is aggressive executed flow toward the level.
Neither is a long, a short, a liquidation, or an order-book state.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _aligned(ms: int) -> bool:
    return int(ms) % K.BAR_MS == 0


def oi_prints(available_at: np.ndarray, values: np.ndarray, decision_ms: int) -> Optional[np.ndarray]:
    """Thirteen exact prints from T-60m through T. Missing, non-positive, or future prints fail closed."""
    t = int(decision_ms)
    if not _aligned(t) or t >= K.SURFACE_END_MS:
        return None
    want = t - K.PRIMARY_MS + np.arange(K.OI_PRINTS, dtype=np.int64) * K.BAR_MS
    if int(want[-1]) != t or int(want[0]) != t - K.PRIMARY_MS:
        return None
    if np.any(want > t):
        return None
    idx = np.searchsorted(available_at, want, side="left")
    if np.any(idx >= available_at.shape[0]):
        return None
    got = available_at[idx]
    if np.any(got != want):
        return None
    out = values[idx].astype(float)
    if not np.all(np.isfinite(out)) or np.any(out <= 0.0):
        return None
    # The next print, if present, is the touch bar's OI and is not in `out`.
    return out


def oi_features_from_prints(prints: np.ndarray) -> dict:
    """F1 and F2. `prints` is the frozen 13-point window, index 0 at T-60m and index 12 at T."""
    if prints.shape != (K.OI_PRINTS,):
        raise ValueError("OI window must be 13 prints")
    first = float(prints[0])
    at_15 = float(prints[9])  # T-15m
    last = float(prints[12])
    change = math.log(last / first)
    recent = math.log(last / at_15) / 15.0
    prior = math.log(at_15 / first) / 45.0
    return {
        "OI_CHANGE_60M": change,
        "OI_RECENT_ACCELERATION": recent - prior,
    }


def _bar_ok(quote: float, taker: float) -> bool:
    if not math.isfinite(quote) or not math.isfinite(taker):
        return False
    if quote < 0.0 or taker < 0.0 or taker > quote:
        return False
    return True


def _slice_ok(quote: np.ndarray, taker: np.ndarray) -> bool:
    if quote.size == 0 or quote.shape != taker.shape:
        return False
    finite = np.isfinite(quote) & np.isfinite(taker)
    if not bool(finite.all()):
        return False
    if np.any(quote < 0.0) or np.any(taker < 0.0) or np.any(taker > quote):
        return False
    return True


def _imbalance(quote: np.ndarray, taker: np.ndarray, side: int) -> Optional[float]:
    if not _slice_ok(quote, taker):
        return None
    total = float(quote.sum())
    if not math.isfinite(total) or total <= 0.0:
        return None
    buy = float(taker.sum())
    sell = total - buy
    raw = (buy - sell) / total
    return float(side) * raw


def flow_features(open_: np.ndarray, close: np.ndarray, quote: np.ndarray, taker: np.ndarray,
                  t0: int, decision_ms: int, side: int) -> dict:
    """F3, F4, oriented displacement, and relative quote volume. Touch bar is index of T, excluded."""
    empty = {
        "ORIENTED_TAKER_IMBALANCE_60M": None,
        "TAKER_RECENT_SHIFT": None,
        "disp": None,
        "rel_volume": None,
        "taker_complete_60m": False,
        "taker_complete_15m": False,
    }
    t = int(decision_ms)
    if side not in (1, -1) or not _aligned(t) or (t - int(t0)) % K.BAR_MS != 0:
        return empty
    j = (t - int(t0)) // K.BAR_MS
    i0 = j - K.TAKER_BARS
    i15 = j - K.RECENT_BARS
    i24 = j - K.REL_VOL_BARS
    if i0 < 0 or j > quote.shape[0]:
        return empty
    q60 = quote[i0:j]
    tb60 = taker[i0:j]
    if q60.shape[0] != K.TAKER_BARS or not _slice_ok(q60, tb60):
        return empty
    # Bar opens must be exactly [T-60m, T).
    if int(t0) + i0 * K.BAR_MS != t - K.PRIMARY_MS:
        return empty
    if int(t0) + (j - 1) * K.BAR_MS + K.BAR_MS != t:
        return empty
    imb60 = _imbalance(q60, tb60, side)
    q15, tb15 = quote[i15:j], taker[i15:j]
    q45, tb45 = quote[i0:i15], taker[i0:i15]
    imb15 = _imbalance(q15, tb15, side)
    imb45 = _imbalance(q45, tb45, side)
    o0 = float(open_[i0])
    c1 = float(close[j - 1])
    disp = None
    if math.isfinite(o0) and math.isfinite(c1) and o0 > 0.0 and c1 > 0.0:
        disp = float(side) * math.log(c1 / o0)
    rel = None
    if i24 >= 0:
        hist = quote[i24:j]
        ok = np.isfinite(hist) & (hist >= 0.0)
        if ok.size == K.REL_VOL_BARS and float(ok.mean()) >= K.REL_VOL_MIN_PRESENT:
            base = float(hist[ok].mean())
            if base > 0.0:
                rel = float(q60.sum()) / (base * K.TAKER_BARS)
    return {
        "ORIENTED_TAKER_IMBALANCE_60M": imb60,
        "TAKER_RECENT_SHIFT": None if imb15 is None or imb45 is None else float(imb15 - imb45),
        "disp": disp,
        "rel_volume": rel,
        "taker_complete_60m": imb60 is not None and disp is not None,
        "taker_complete_15m": imb15 is not None and imb45 is not None,
    }


def time_block(decision_ms: int) -> int:
    hour = (int(decision_ms) // K.HOUR_MS) % 24
    return int(hour // 6)


def epoch_of(decision_ms: int, year: int) -> str:
    if int(year) == 2020:
        return "2020Q4"
    return str(int(year))


def vol_tercile(sigma: Optional[float]) -> Optional[int]:
    if sigma is None or not math.isfinite(float(sigma)):
        return None
    if float(sigma) <= K.PARENT_SIGMA_LO:
        return 0
    if float(sigma) <= K.PARENT_SIGMA_HI:
        return 1
    return 2
