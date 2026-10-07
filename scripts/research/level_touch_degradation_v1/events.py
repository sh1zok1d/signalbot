"""Point-in-time structural levels, confluence zones and distinct touches.

No break/reject label is computed here. Outcome classification lives in `outcomes.py`
and is imported only by the evaluator.

A level price is the previous completed UTC period's high or low (product period rules).
It is active only on the following period, so the source period's own bars never count
as touches of that level.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

import numpy as np

from beta import levels as LV
from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.dh1.events import rolling_sigma

from . import constants as K


def sigma_before_touch(close: np.ndarray) -> np.ndarray:
    """sigma_before[j] is the 24h log-return std known at the close of bar j-1.

    DH1's `rolling_sigma[e]` includes the return that ends at bar e. The touch bar's own
    return is not part of the volatility state ("before touch").
    """
    sig = rolling_sigma(close, window=K.SCALE_BARS, min_frac=K.MIN_PRESENT)
    out = np.full(close.shape[0], np.nan)
    out[1:] = sig[:-1]
    return out


def _expected_bars(family: str) -> Optional[int]:
    if family == "DAY":
        return BARS_PER_DAY
    if family == "WEEK":
        return 7 * BARS_PER_DAY
    return None


def level_instances(b: Bars) -> tuple[list[dict], dict]:
    """Structural level instances whose price was fixed before the active period opened.

    Returns (instances, drop_counts). An instance is not emitted when the source period
    and the active period are not consecutive full periods under the product rule.
    """
    keys = LV.period_keys(b)
    spec = (("DAY", "day", "D"), ("WEEK", "week", "W"), ("MONTH", "month", "M"))
    out: list[dict] = []
    drops = {"gap": 0, "incomplete_source": 0, "incomplete_active": 0}
    for family, name, pref in spec:
        periods = LV._period_table(b, keys[name])
        exp = _expected_bars(family)
        for p in range(1, len(periods)):
            prev, cur = periods[p - 1], periods[p]
            if prev["key"] != cur["key"] - 1:
                drops["gap"] += 2
                continue
            if not LV._full_period(prev, exp):
                drops["incomplete_source"] += 2
                continue
            if not LV._full_period(cur, exp):
                drops["incomplete_active"] += 2
                continue
            for kind, price in ((f"P{pref}H", prev["high"]), (f"P{pref}L", prev["low"])):
                if not math.isfinite(price) or price <= 0 or not math.isfinite(cur["open"]):
                    continue
                out.append({
                    "kind": kind,
                    "family": family,
                    "struct_side": K.STRUCT_SIDE[kind],
                    "price": float(price),
                    "i0": int(cur["first"]),
                    "i1": int(cur["last"]),
                    "period_open": float(cur["open"]),
                    "source_key": int(prev["key"]),
                    "period_key": int(cur["key"]),
                })
    return out, drops


def _rel_gap(higher: float, lower: float) -> float:
    return (higher - lower) / lower if lower > 0 else math.inf


def _near(price: float, anchor: float, tol: float) -> bool:
    lo, hi = (price, anchor) if price < anchor else (anchor, price)
    return _rel_gap(hi, lo) <= tol


def build_episodes(instances: Iterable[dict], zone_half: float) -> tuple[list[dict], dict]:
    """One episode per confluence zone. Geometry is fixed at birth from levels known then.

    A level that appears later and falls inside an already active zone is absorbed: it does
    not open a second touch counter. Absorption does not move the zone.
    """
    born: dict[int, list] = {}
    for inst in instances:
        born.setdefault(int(inst["i0"]), []).append(inst)
    episodes: list[dict] = []
    absorbed_later = 0
    absorbed_at_birth = 0
    for i0 in sorted(born):
        active = [ep for ep in episodes if ep["i0"] < i0 <= ep["i1"]]
        free: list[dict] = []
        for inst in born[i0]:
            hosts = []
            for ep in active:
                inside = ep["zone_low"] <= inst["price"] <= ep["zone_high"]
                if inside or _near(inst["price"], ep["anchor_price"], zone_half):
                    hosts.append(ep)
            if not hosts:
                free.append(inst)
                continue
            host = min(hosts, key=lambda ep: (ep["priority"], abs(ep["anchor_price"] - inst["price"])))
            host["absorbed_later"].append(inst["kind"])
            absorbed_later += 1
        free.sort(key=lambda r: (r["price"], K.PRIORITY[r["kind"]], r["kind"]))
        clusters: list[list] = []
        for inst in free:
            if clusters and _rel_gap(inst["price"], clusters[-1][-1]["price"]) <= zone_half:
                clusters[-1].append(inst)
            else:
                clusters.append([inst])
        for cluster in clusters:
            anchor = min(cluster, key=lambda r: (K.PRIORITY[r["kind"]], r["price"], r["kind"]))
            prices = [r["price"] for r in cluster]
            zlo = min(prices) * (1.0 - zone_half)
            zhi = max(prices) * (1.0 + zone_half)
            if not (zlo > 0 and zhi > zlo):
                continue
            episodes.append({
                "episode_id": f"{anchor['kind']}:{anchor['source_key']}:{anchor['i0']}",
                "kind": anchor["kind"],
                "family": anchor["family"],
                "struct_side": anchor["struct_side"],
                "priority": K.PRIORITY[anchor["kind"]],
                "anchor_price": anchor["price"],
                "zone_low": float(zlo),
                "zone_high": float(zhi),
                "i0": anchor["i0"],
                "i1": anchor["i1"],
                "period_open": anchor["period_open"],
                "source_key": anchor["source_key"],
                "period_key": anchor["period_key"],
                "member_kinds": [r["kind"] for r in cluster],
                "n_members": len(cluster),
                "absorbed_later": [],
                "population": "real",
                "zone_half": float(zone_half),
            })
            absorbed_at_birth += len(cluster) - 1
    info = {"episodes": len(episodes), "absorbed_at_birth": absorbed_at_birth,
            "absorbed_later": absorbed_later}
    return episodes, info


def _finite_bar(high, low, j: int) -> bool:
    return bool(np.isfinite(high[j]) and np.isfinite(low[j]))


def intersects(high, low, j: int, zlo: float, zhi: float) -> bool:
    if not _finite_bar(high, low, j):
        return False
    return bool(high[j] >= zlo and low[j] <= zhi)


def is_clearance(high, low, j: int, zlo: float, zhi: float, dist: float) -> bool:
    """The whole bar is outside the zone and at least `dist` (fraction) beyond the near edge."""
    if not _finite_bar(high, low, j) or intersects(high, low, j, zlo, zhi):
        return False
    if low[j] > zhi:
        return bool(low[j] >= zhi * (1.0 + dist))
    if high[j] < zlo:
        return bool(high[j] <= zlo * (1.0 - dist))
    return False


def approach_side(open_, close, high, low, j: int, i0: int, zlo: float, zhi: float) -> int:
    """+1 approach from below (break is up); -1 approach from above (break is down); 0 unknown."""
    k = j - 1
    while k >= i0:
        if _finite_bar(high, low, k) and not intersects(high, low, k, zlo, zhi):
            c = close[k]
            if np.isfinite(c) and c < zlo:
                return 1
            if np.isfinite(c) and c > zhi:
                return -1
        k -= 1
    if j > 0 and np.isfinite(close[j - 1]):
        c = float(close[j - 1])
        if c < zlo:
            return 1
        if c > zhi:
            return -1
        return 1 if c <= 0.5 * (zlo + zhi) else -1
    ref = open_[j] if np.isfinite(open_[j]) else np.nan
    if not np.isfinite(ref):
        return 0
    return 1 if float(ref) <= 0.5 * (zlo + zhi) else -1


def window_complete(high, low, j: int, horizon: int, n: int, t0: int, end_ms: int) -> bool:
    """The horizon is inside the series and inside the legal surface, with enough finite bars.

    This does not look at which barrier was hit.
    """
    if horizon < 1 or j + horizon >= n:
        return False
    if t0 + (j + horizon + 1) * K.BAR_MS > end_ms:
        return False
    hh = high[j + 1:j + 1 + horizon]
    ll = low[j + 1:j + 1 + horizon]
    ok = np.isfinite(hh) & np.isfinite(ll)
    return bool(ok.size == horizon and ok.mean() >= K.MIN_PRESENT)


def touch_open_ms(t0: int, j: int) -> int:
    return int(t0 + j * K.BAR_MS)


def touch_year(open_ms: int) -> int:
    return int(np.datetime64(int(open_ms), "ms").astype("datetime64[Y]").astype(int) + 1970)


def touch_week(open_ms: int) -> int:
    """Product week id: Monday 00:00 UTC, the same `(day + 3) // 7` as `beta.levels.period_keys`."""
    day = int(open_ms) // K.DAY_MS
    return int((day + 3) // 7)


def scan_episode(high, low, close, open_, sigma_before, t0: int, episode: dict, *,
                 end_ms: int) -> list[dict]:
    """Distinct touches of one zone. Numbering is geometric and does not depend on the outcome.

    Touch 1 is the first intersection at or after the episode opens (the level is already
    known). A later touch starts only after a clearance bar at least primary-X beyond the zone.
    If the volatility scale at a touch is unusable, that touch is ineligible and the chain stops:
    the refractory distance would otherwise be invented.
    """
    i0, i1 = int(episode["i0"]), int(episode["i1"])
    zlo, zhi = float(episode["zone_low"]), float(episode["zone_high"])
    n = int(high.shape[0])
    i1 = min(i1, n - 1)
    if i0 < 0 or i0 > i1:
        return []
    out: list[dict] = []
    number = 0
    state = "OUT"
    clear_dist = None
    for j in range(i0, i1 + 1):
        if state == "STOP":
            break
        hit = intersects(high, low, j, zlo, zhi)
        if state == "OUT":
            if not hit:
                continue
            number += 1
            sigma = float(sigma_before[j]) if j < sigma_before.shape[0] else math.nan
            x = K.x_from_sigma(sigma) if math.isfinite(sigma) else math.nan
            usable = bool(math.isfinite(x) and K.X_MIN < x < K.X_MAX)
            side = approach_side(open_, close, high, low, j, i0, zlo, zhi)
            oms = touch_open_ms(t0, j)
            w48 = window_complete(high, low, j, K.HOLD_BARS_PRIMARY, n, t0, end_ms)
            w12 = window_complete(high, low, j, K.HOLD_BARS_SENSITIVITY, n, t0, end_ms)
            in_window = oms >= K.EVENT_START_MS
            feature_ok = bool(usable and side in (1, -1) and w48 and in_window)
            out.append({
                "episode_id": episode["episode_id"],
                "population": episode.get("population", "real"),
                "kind": episode["kind"],
                "family": episode["family"],
                "struct_side": int(episode["struct_side"]),
                "anchor_price": float(episode["anchor_price"]),
                "zone_low": zlo,
                "zone_high": zhi,
                "zone_half": float(episode["zone_half"]),
                "n_members": int(episode["n_members"]),
                "member_kinds": list(episode["member_kinds"]),
                "i0": i0,
                "j": int(j),
                "touch_number": int(number),
                "bucket": K.bucket_of(number),
                "open_ms": oms,
                "year": touch_year(oms),
                "week": touch_week(oms),
                "side": int(side),
                "sigma": sigma if math.isfinite(sigma) else None,
                "x_primary": x if math.isfinite(x) else None,
                "window_ok_48": w48,
                "window_ok_12": w12,
                "feature_eligible": feature_ok,
                "chain_stop": not usable,
                "outcome": None,
            })
            if not usable:
                state = "STOP"
            else:
                state = "WAIT"
                clear_dist = K.REFRACTORY_MULT * x
            continue
        if is_clearance(high, low, j, zlo, zhi, float(clear_dist)):
            state = "OUT"
            clear_dist = None
    return out


def scan_all(b: Bars, episodes: Iterable[dict], sigma_before: np.ndarray, *,
             end_ms: int = K.SURFACE_END_MS) -> list[dict]:
    high, low, close, open_ = b.high, b.low, b.close, b.open
    out: list[dict] = []
    for ep in episodes:
        out.extend(scan_episode(high, low, close, open_, sigma_before, int(b.t0), ep, end_ms=end_ms))
    return out
