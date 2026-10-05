"""«Что было после похожих»: history of the 1h / 4h state labels (PRODUCT_DECISION_V2 §2.3).

The live labels ("похоже на выход шортов", "сжатие", the factual pairs …) come from
`beta.interpretation.interpret` over the multi-venue context projection. Here the same function
labels Binance history (a declared single-venue proxy: venue agreement is not checked, and the
liquidation-confirmed "вынос" labels fall back to their base label because no liquidation
history exists):

- rolling 1h (12 bars) and 4h (48 bars) windows: price move, range, quote volume, taker delta
  (2 × taker-buy quote − quote) and the open-interest change between the window's as-of
  boundaries (Vision metrics);
- each value ranked (mid-rank) against the same rolling value at every 5m step of the previous
  30 days, exactly like the live projection;
- one anchor per hour.

For every label and outcome horizon: N, independent days, how often the close was higher, the
median close-to-close move and its 10–90% spread, the median move up and down. Beside it, the
same numbers for all hours in the same volatility tercile ("обычно"), weighted to the label's
tercile mix. A verdict per cell: «отличается» only when a day-clustered bootstrap, Holm-corrected
across the family, rejects equality and the difference passes a materiality floor; otherwise
«как обычно»; «мало данных» below the sufficiency floor.

Pure numpy; no I/O.
"""
from __future__ import annotations

import bisect
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from .hist_series import BAR_MS, BARS_PER_DAY, Bars, forward_extremes, past_range_pct, rolling_sum
from .interpretation import interpret
from .levels import holm

ANALOGUES_VERSION = "BETA_ANALOGUES_V2"
# V2 (C1, docs/BETA_C1_DAY_TYPE_BASELINE_V1.md): history labels rank range, move and volume against
# same-UTC-day-type samples, exactly like the live BETA_CONTEXT_1H_V3 projection.
DAY_TYPE_METRICS = ("price_move_pct_median", "range_width_pct_median", "volume_notional_usd_sum")
DAY_TYPE_MIN_DATES = 8
_DAY_MS = 86_400_000
WINDOWS = {"1h": 12, "4h": 48}
OUTCOMES = {"1h": ("1h", "4h"), "4h": ("4h", "24h")}
OUTCOME_BARS = {"1h": 12, "4h": 48, "24h": 288}
RANK_WINDOW = 30 * BARS_PER_DAY
RANK_MIN_FRACTION = 0.8
ANCHOR_STRIDE = 12
BOOTSTRAP_B = 1000
MIN_N = 30
MIN_DAYS = 15
MATERIAL_UP = 0.03
MATERIAL_RANGE_LOG = math.log(1.15)
ALPHA = 0.05
SEED = 20261003
METRICS = ("price_move_pct_median", "range_width_pct_median", "volume_notional_usd_sum",
           "taker_delta_notional_usd_sum", "oi_change_pct_median")
# a live flush label is looked up under its base label (no liquidation history)
LIVE_TO_HISTORY_KEY = {"short_flush": "short_exit", "long_flush": "long_exit"}


class _ProxyCfg:
    """The two things `interpret` reads from BetaConfig, for a single-venue proxy."""

    def __init__(self, context: Mapping[str, Any]):
        self._context = dict(context)
        self.min_venues = 1

    def section(self, name: str):
        if name != "context":
            raise KeyError(name)
        return self._context


def window_values(b: Bars, n: int) -> dict:
    """Rolling-window metrics ending at the close of every bar i (bars i−n+1 .. i)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        start_open = np.roll(b.open, n - 1)
        start_open[: n - 1] = np.nan
        move = (b.close - start_open) / start_open * 100.0
        rng = past_range_pct(b, n, min_frac=1.0) * b.close / start_open
        vol = rolling_sum(b.quote, n)
        delta = rolling_sum(2.0 * b.taker_buy_quote - b.quote, n)
        oi_prev = np.roll(b.oi, n)
        oi_prev[:n] = np.nan
        oi = (b.oi - oi_prev) / oi_prev * 100.0
    return {"price_move_pct_median": move, "range_width_pct_median": rng, "volume_notional_usd_sum": vol,
            "taker_delta_notional_usd_sum": delta, "oi_change_pct_median": oi}


def trailing_ranks(values: np.ndarray, anchors: np.ndarray, *, window: int = RANK_WINDOW,
                   min_fraction: float = RANK_MIN_FRACTION) -> np.ndarray:
    """Mid-rank of values[a] among the finite values[a−window .. a−1], for every anchor a
    (the anchor value itself is never a sample). NaN when fewer than min_fraction × window."""
    out = np.full(anchors.size, np.nan)
    if anchors.size == 0:
        return out
    is_anchor = np.zeros(values.size, dtype=bool)
    is_anchor[anchors] = True
    pos = {int(a): k for k, a in enumerate(anchors)}
    window_vals: list = []
    need = int(window * min_fraction)
    for i in range(values.size):
        if is_anchor[i] and len(window_vals) >= need and math.isfinite(values[i]):
            v = values[i]
            lo = bisect.bisect_left(window_vals, v)
            hi = bisect.bisect_right(window_vals, v)
            out[pos[i]] = (lo + 0.5 * (hi - lo)) / len(window_vals)
        v = values[i]
        if math.isfinite(v):
            bisect.insort(window_vals, v)
        j = i - window
        if j >= 0:
            old = values[j]
            if math.isfinite(old):
                del window_vals[bisect.bisect_left(window_vals, old)]
    return out


def window_start_day(b: Bars, n: int) -> tuple:
    """(UTC epoch day of each bar's window start, weekend flag) for windows of n bars ending at each bar."""
    day = (b.times - (n - 1) * BAR_MS) // _DAY_MS
    return day, ((day + 3) % 7) >= 5                      # 1970-01-01 was a Thursday (weekday 3)


def trailing_ranks_day_type(values: np.ndarray, anchors: np.ndarray, day: np.ndarray, weekend: np.ndarray,
                            *, window: int = RANK_WINDOW, min_fraction: float = RANK_MIN_FRACTION,
                            min_dates: int = DAY_TYPE_MIN_DATES) -> np.ndarray:
    """C1: mid-rank of values[a] among the finite values[a−window .. a−1] of the SAME day type.
    NaN unless the unfiltered window holds min_fraction × window finite values (the C0 rule) and
    at least min_dates distinct same-type dates have a finite value. No fallback."""
    out = np.full(anchors.size, np.nan)
    if anchors.size == 0:
        return out
    is_anchor = np.zeros(values.size, dtype=bool)
    is_anchor[anchors] = True
    pos = {int(a): k for k, a in enumerate(anchors)}
    lists = {False: [], True: []}
    dates = {False: {}, True: {}}
    total = 0
    need = int(window * min_fraction)
    for i in range(values.size):
        t = bool(weekend[i])
        if is_anchor[i] and total >= need and math.isfinite(values[i]) and len(dates[t]) >= min_dates:
            lst, v = lists[t], values[i]
            lo = bisect.bisect_left(lst, v)
            hi = bisect.bisect_right(lst, v)
            out[pos[i]] = (lo + 0.5 * (hi - lo)) / len(lst)
        v = values[i]
        if math.isfinite(v):
            bisect.insort(lists[t], v)
            dates[t][int(day[i])] = dates[t].get(int(day[i]), 0) + 1
            total += 1
        j = i - window
        if j >= 0:
            old = values[j]
            if math.isfinite(old):
                tj = bool(weekend[j])
                del lists[tj][bisect.bisect_left(lists[tj], old)]
                dj = int(day[j])
                dates[tj][dj] -= 1
                if not dates[tj][dj]:
                    del dates[tj][dj]
                total -= 1
    return out


def label_history(b: Bars, *, context: Mapping[str, Any], stride: int = ANCHOR_STRIDE) -> dict:
    """Anchors (hourly) with their 1h and 4h label keys, volatility tercile and outcomes."""
    close_ms = b.times + BAR_MS
    anchors = np.flatnonzero(((close_ms % (stride * BAR_MS)) == 0) & np.isfinite(b.close))
    cfg = _ProxyCfg(context)
    labels: dict = {}
    for w, n in WINDOWS.items():
        vals = window_values(b, n)
        day, weekend = window_start_day(b, n)
        ranks = {m: (trailing_ranks_day_type(vals[m], anchors, day, weekend) if m in DAY_TYPE_METRICS
                     else trailing_ranks(vals[m], anchors)) for m in METRICS}
        keys = []
        for k, a in enumerate(anchors):
            pm = vals["price_move_pct_median"][a]
            ctx = {"window_start": None, "window_end": None,
                   "price_move_pct_by_venue": {"binance": float(pm)} if math.isfinite(pm) else {},
                   "percentiles": {}}
            for m in METRICS:
                v = vals[m][a]
                r = ranks[m][k]
                ctx[m] = float(v) if math.isfinite(v) else None
                ctx["percentiles"][m] = {"rank": float(r) if math.isfinite(r) else None,
                                         "tier": "mature" if math.isfinite(r) else None}
            keys.append(interpret(cfg, ctx, horizon=w)["key"])
        labels[w] = np.asarray(keys, dtype=object)
    vol24 = past_range_pct(b, BARS_PER_DAY)
    vrank = trailing_ranks(vol24, anchors)
    tercile = np.where(np.isfinite(vrank), np.minimum(np.floor(np.nan_to_num(vrank) * 3), 2), -1)
    outcomes = {}
    for h, n in OUTCOME_BARS.items():
        fhi, flo, fcl = forward_extremes(b, n)
        c = b.close[anchors]
        with np.errstate(invalid="ignore", divide="ignore"):
            outcomes[h] = {"ret": (fcl[anchors] - c) / c * 100.0,
                           "up": np.maximum((fhi[anchors] - c) / c * 100.0, 0.0),
                           "down": np.maximum((c - flo[anchors]) / c * 100.0, 0.0)}
    return {"anchors": anchors, "close_ms": close_ms[anchors], "labels": labels,
            "tercile": tercile.astype(np.int64), "outcomes": outcomes}


def _wquantile(x: np.ndarray, w: np.ndarray, q: float) -> float:
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return float(np.interp(q * c[-1], c, x))


def _baseline(hist: Mapping[str, Any], h: str, mix: np.ndarray, valid: np.ndarray) -> Optional[dict]:
    """'Обычно': all anchors with outcomes, weighted to the cohort's tercile mix."""
    o = hist["outcomes"][h]
    t = hist["tercile"]
    ok = valid & np.isfinite(o["ret"]) & (t >= 0)
    if not ok.any():
        return None
    counts = np.bincount(t[ok], minlength=3).astype(np.float64)
    w_t = np.divide(mix, counts, out=np.zeros(3), where=counts > 0)
    w = w_t[t[ok]]
    if w.sum() <= 0:
        return None
    ret, up, dn = o["ret"][ok], o["up"][ok], o["down"][ok]
    rng = up + dn
    return {"p_up": float(np.sum(w * (ret > 0)) / w.sum()),
            "median_ret": _wquantile(ret, w, 0.5), "q10": _wquantile(ret, w, 0.1),
            "q90": _wquantile(ret, w, 0.9), "median_up": _wquantile(up, w, 0.5),
            "median_down": _wquantile(dn, w, 0.5), "median_range": _wquantile(rng, w, 0.5),
            "mean_log_range": float(np.sum(w * np.log(np.maximum(rng, 0.01))) / w.sum())}


def _boot(days: np.ndarray, x: np.ndarray, base_value: float, rng, b_reps: int) -> Optional[float]:
    """Two-sided p-value of mean(x) − base_value = 0 with day-clustered resampling."""
    uniq, inv = np.unique(days, return_inverse=True)
    if uniq.size < MIN_DAYS:
        return None
    s = np.bincount(inv, weights=x).astype(np.float64)
    c = np.bincount(inv).astype(np.float64)
    W = rng.multinomial(uniq.size, np.full(uniq.size, 1.0 / uniq.size), size=b_reps).astype(np.float64)
    d = (W @ s) / (W @ c) - base_value
    d = d[np.isfinite(d)]
    if d.size < b_reps * 0.9:
        return None
    return float(min(1.0, 2 * min(np.mean(d <= 0), np.mean(d >= 0))))


def analogue_stats(b: Bars, *, context: Mapping[str, Any], seed: int = SEED,
                   bootstrap: int = BOOTSTRAP_B, hist: Optional[Mapping[str, Any]] = None) -> dict:
    hist = hist or label_history(b, context=context)
    rng = np.random.default_rng(seed)
    days_all = hist["close_ms"] // 86_400_000
    out: dict = {"version": ANALOGUES_VERSION, "source": "binance_usdm_btcusdt_5m",
                 "proxy": {"venue_agreement": "not checked (single venue)",
                           "liquidation_labels": "no history; looked up under the base label"},
                 "windows": {}, "method": {"baseline": "all hours, same 24h-volatility tercile mix",
                                           "bootstrap": bootstrap, "cluster": "UTC day",
                                           "correction": "Holm", "alpha": ALPHA,
                                           "materiality": {"p_up": MATERIAL_UP, "range_ratio": 1.15},
                                           "min_n": MIN_N, "min_days": MIN_DAYS}}
    if hist["anchors"].size:
        out["data_from_ms"] = int(hist["close_ms"][0])
        out["data_to_ms"] = int(hist["close_ms"][-1])
    pvals: dict = {}
    cells: dict = {}
    for w, outs in OUTCOMES.items():
        labels = hist["labels"][w]
        valid = np.array([k not in ("missing", "insufficient") for k in labels])
        out["windows"][w] = {}
        for key in sorted(set(labels[valid])):
            sel = valid & (labels == key)
            rec = {"n_anchors": int(sel.sum()), "outcomes": {}}
            for h in outs:
                o = hist["outcomes"][h]
                ok = sel & np.isfinite(o["ret"]) & (hist["tercile"] >= 0)
                n = int(ok.sum())
                days = days_all[ok]
                cell: dict = {"n": n, "days": int(np.unique(days).size)}
                if n:
                    ret, up, dn = o["ret"][ok], o["up"][ok], o["down"][ok]
                    rngv = up + dn
                    mix = np.bincount(hist["tercile"][ok], minlength=3).astype(np.float64) / n
                    base = _baseline(hist, h, mix, valid)
                    cell.update({"p_up": float(np.mean(ret > 0)), "median_ret": float(np.median(ret)),
                                 "q10": float(np.quantile(ret, 0.1)), "q90": float(np.quantile(ret, 0.9)),
                                 "median_up": float(np.median(up)), "median_down": float(np.median(dn)),
                                 "median_range": float(np.median(rngv)), "baseline": base})
                    if base is not None:
                        cell["range_ratio"] = float(np.median(rngv) / base["median_range"]) \
                            if base["median_range"] > 0 else None
                    if n >= MIN_N and cell["days"] >= MIN_DAYS and base is not None:
                        pvals[(w, key, h, "direction")] = _boot(days, (ret > 0).astype(np.float64),
                                                                base["p_up"], rng, bootstrap)
                        pvals[(w, key, h, "range")] = _boot(days, np.log(np.maximum(rngv, 0.01)),
                                                            base["mean_log_range"], rng, bootstrap)
                        cell["mean_log_range"] = float(np.mean(np.log(np.maximum(rngv, 0.01))))
                rec["outcomes"][h] = cell
                cells[(w, key, h)] = cell
            out["windows"][w][key] = rec
    adj = holm(pvals)
    out["family_size"] = len([p for p in pvals.values() if p is not None])
    for (w, key, h), cell in cells.items():
        verdicts = {}
        for test in ("direction", "range"):
            p = adj.get((w, key, h, test))
            if p is None or cell.get("baseline") is None:
                verdicts[test] = "insufficient"
                continue
            if test == "direction":
                material = abs(cell["p_up"] - cell["baseline"]["p_up"]) >= MATERIAL_UP
            else:
                material = abs(cell["mean_log_range"] - cell["baseline"]["mean_log_range"]) >= MATERIAL_RANGE_LOG
            verdicts[test] = "differs" if p < ALPHA and material else "as_usual"
            cell.setdefault("p_holm", {})[test] = round(p, 5)
        cell["verdicts"] = verdicts
    return out


def lookup(stats: Optional[Mapping[str, Any]], window: str, live_key: Optional[str]) -> Optional[dict]:
    """The card for a live label key, or None (no stats, no such label in history, or stats
    built under another label definition: a live C1 label is never matched to C0 history)."""
    if not stats or not live_key or stats.get("version") != ANALOGUES_VERSION:
        return None
    key = LIVE_TO_HISTORY_KEY.get(live_key, live_key)
    rec = ((stats.get("windows") or {}).get(window) or {}).get(key)
    if rec is None:
        return None
    return {"window": window, "key": key, "live_key": live_key,
            "proxy_label": key != live_key, **rec}
