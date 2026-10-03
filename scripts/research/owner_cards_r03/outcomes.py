"""Post-T targets for R03. Imported only by the one-shot evaluator.

Target of a window (t0, L): log range ln(max high / min low) over bars with open time in
[t0, t0 + L). A window with any missing bar is UNAVAILABLE (timestamps only).
Standardization: per calendar year and per window definition, over all days' windows of that
definition (label-blind). Nuisance features computed as-of t0: prior 24h realized variance
from bar log returns, and the lagged target (same definition, previous calendar day).
"""

from __future__ import annotations

import numpy as np

from . import constants as K


class Bars:
    def __init__(self, panel: dict[str, np.ndarray], step_ms: int):
        self.t = panel["open_ms"]
        self.high = panel["high"]
        self.low = panel["low"]
        self.close = panel["close"]
        self.step = step_ms
        self.logret = np.zeros_like(self.close)
        self.logret[1:] = np.log(self.close[1:] / self.close[:-1])
        # a return is valid only if the previous bar is the adjacent bucket
        self.ret_ok = np.zeros(self.t.size, dtype=bool)
        self.ret_ok[1:] = np.diff(self.t) == step_ms
        self.cum_r2 = np.concatenate([[0.0], np.cumsum(np.where(self.ret_ok, self.logret ** 2, 0.0))])
        self.cum_ok = np.concatenate([[0], np.cumsum(self.ret_ok.astype(np.int64))])

    def window_log_range(self, t0: int, minutes: int) -> float:
        t1 = t0 + minutes * K.MINUTE_MS
        i0 = int(np.searchsorted(self.t, t0, side="left"))
        i1 = int(np.searchsorted(self.t, t1, side="left"))
        expected = (t1 - t0) // self.step
        if i1 - i0 != expected or i0 >= self.t.size:
            return float("nan")
        lo = float(np.min(self.low[i0:i1]))
        hi = float(np.max(self.high[i0:i1]))
        if lo <= 0 or hi < lo:
            return float("nan")
        return float(np.log(hi / lo))

    def prior_rv(self, t0: int, minutes: int = K.PRIOR_RV_MINUTES) -> float:
        """log of the realized variance of bar returns over [t0 - minutes, t0); NaN below 80% coverage."""
        ta = t0 - minutes * K.MINUTE_MS
        i0 = int(np.searchsorted(self.t, ta, side="left"))
        i1 = int(np.searchsorted(self.t, t0, side="left"))
        expected = minutes * K.MINUTE_MS // self.step
        n_ok = int(self.cum_ok[i1] - self.cum_ok[i0])
        if n_ok < 0.8 * expected:
            return float("nan")
        rv = float(self.cum_r2[i1] - self.cum_r2[i0]) * expected / n_ok
        return float(np.log(rv)) if rv > 0 else float("nan")


def year_of(t0: int) -> int:
    import datetime as dt
    return dt.datetime.fromtimestamp(t0 / 1000, tz=dt.timezone.utc).year


def attach_targets(units: list[dict], bars: Bars) -> dict:
    """Compute raw log ranges for every window of every unit, plus the label-blind
    standardization table per (year, definition) from the union of all windows seen."""
    rows = []  # (unit_idx, role, t0, minutes, defkey, year, raw, prior_rv, lagged_raw)
    for ui, u in enumerate(units):
        for role, wins in (("S", u["STATE"]), ("C", u["COMPARATOR"])):
            for (t0, minutes, defkey) in wins:
                raw = bars.window_log_range(t0, minutes)
                lag = bars.window_log_range(t0 - K.DAY_MS, minutes)
                rows.append((ui, role, t0, minutes, defkey, year_of(t0), raw, bars.prior_rv(t0), lag))
    return {"rows": rows}


def standardize(rows: list[tuple]) -> dict:
    """z = (raw - mean) / sd within (year, defkey) over all available windows; label-blind."""
    groups: dict[tuple, list[float]] = {}
    for r in rows:
        if np.isfinite(r[6]):
            groups.setdefault((r[5], r[4]), []).append(r[6])
    stats = {k: (float(np.mean(v)), float(np.std(v, ddof=1))) for k, v in groups.items() if len(v) >= 10}
    return stats


def nuisance_adjust(rows: list[tuple], stats: dict) -> dict[int, float]:
    """Residual of z on [1, z(prior RV), z(lagged target)] fitted per (year, defkey) over all
    windows with every feature available. Label-blind. Returns index -> adjusted z."""
    by_group: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        key = (r[5], r[4])
        if key in stats and np.isfinite(r[6]) and np.isfinite(r[7]) and np.isfinite(r[8]):
            by_group.setdefault(key, []).append(i)
    out: dict[int, float] = {}
    for key, idx in by_group.items():
        mu, sd = stats[key]
        if sd <= 0 or len(idx) < 30:
            continue
        z = np.array([(rows[i][6] - mu) / sd for i in idx])
        rv = np.array([rows[i][7] for i in idx])
        lag = np.array([(rows[i][8] - mu) / sd for i in idx])
        X = np.column_stack([np.ones(z.size), (rv - rv.mean()) / (rv.std() if rv.std() > 0 else 1.0), lag])
        beta, *_ = np.linalg.lstsq(X, z, rcond=None)
        resid = z - X @ beta
        for i, v in zip(idx, resid):
            out[i] = float(v)
    return out


def unit_differences(units: list[dict], rows: list[tuple], stats: dict, adjusted: dict[int, float]) -> dict:
    """Per unit: d = mean z(state) - mean z(comparator), and the nuisance-adjusted d_adj."""
    acc: dict[int, dict] = {ui: {"S": [], "C": [], "Sa": [], "Ca": []} for ui in range(len(units))}
    for i, r in enumerate(rows):
        key = (r[5], r[4])
        if key not in stats or not np.isfinite(r[6]):
            continue
        mu, sd = stats[key]
        if sd <= 0:
            continue
        acc[r[0]][r[1]].append((r[6] - mu) / sd)
        if i in adjusted:
            acc[r[0]][r[1] + "a"].append(adjusted[i])
    d, d_adj, years, ids, dropped = [], [], [], [], 0
    for ui, u in enumerate(units):
        a = acc[ui]
        if not a["S"] or not a["C"]:
            dropped += 1
            continue
        d.append(float(np.mean(a["S"]) - np.mean(a["C"])))
        d_adj.append(float(np.mean(a["Sa"]) - np.mean(a["Ca"])) if a["Sa"] and a["Ca"] else float("nan"))
        years.append(int(u["YEAR"]))
        ids.append(u["UNIT_ID"])
    return {"d": np.array(d), "d_adj": np.array(d_adj), "years": np.array(years), "unit_ids": ids,
            "DROPPED_UNITS_MISSING_BARS": dropped}
