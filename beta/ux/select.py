"""Pulsy UX V2 salience (docs/PULSY_UX_STANDARD_V2.md §4): which current observations reach L1, in a
frozen order. Each rule reads facts only, through existing labels and thresholds (context.level_label,
the decision block's level zone, the calendar, the 24h corridor). No rule firing is the «ничего
заметного» path. L1 shows at most L1_MAX lines; L2 explains exactly the lines L1 shows."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from beta.models import S_DEGRADED, S_STALE

SALIENCE_VERSION = "PULSY_SALIENCE_V1"
L1_MAX = 3
CORRIDOR_EDGE_SHARE = 0.10             # within 10% of the 24h half-width from a corridor bound
EVENT_AHEAD = timedelta(hours=24)
STALE_STATUSES = (S_DEGRADED, S_STALE)


def _cfg():
    from beta.config import BetaConfig
    return BetaConfig.load()


def _label(facts: Mapping[str, Any], metric: str) -> Optional[str]:
    from beta.context import level_label
    r = (facts.get("ranks_1h") or {}).get(metric) or {}
    return level_label(_cfg(), r.get("rank"), r.get("tier"))


def low_band(facts: Mapping[str, Any], metric: str) -> bool:
    """The 1h metric is in the existing low tail (context.tail_label «bottom»: rank <= tail_display_max,
    tier mature). Display only: not a salience rule, so PULSY_SALIENCE_V1 is unchanged."""
    from beta.context import tail_label
    r = (facts.get("ranks_1h") or {}).get(metric) or {}
    return (tail_label(_cfg(), r.get("rank"), r.get("tier")) or "").startswith("bottom")


def stale_only(f) -> bool:
    """Late data (shows nothing current), as opposed to degraded data (names the partial input)."""
    return f.get("status") == S_STALE or f.get("decision_reason") == "DATA_STALE"


def _stale(f) -> bool:
    return f.get("status") in STALE_STATUSES or f.get("decision_reason") == "DATA_STALE"


def _episode(f) -> bool:
    ep = f.get("episode") or {}
    return bool(ep.get("triggered"))


def _level_at(f) -> bool:
    return bool((f.get("levels") or {}).get("at"))


def _range_extreme(f) -> bool:
    return _label(f, "range_width_pct_median") == "extreme"


def _range_high(f) -> bool:
    return _label(f, "range_width_pct_median") == "high"


def _volume_high(f) -> bool:
    return _label(f, "volume_notional_usd_sum") in ("high", "extreme")


def next_event(f) -> Optional[dict]:
    now = f.get("data_through")
    if not now:
        return None
    t0 = datetime.fromisoformat(now)
    for e in f.get("events") or ():
        at = datetime.fromisoformat(e["at"])
        if t0 <= at <= t0 + EVENT_AHEAD:
            return e
    return None


def _event_today(f) -> bool:
    return next_event(f) is not None


def _corridor_edge(f) -> bool:
    c, p = f.get("corridor_24h") or {}, f.get("price")
    if p is None or not c or c.get("lower") is None or c.get("upper") is None:
        return False
    band = (float(c["upper"]) - float(c["lower"])) / 2.0
    return min(abs(p - float(c["lower"])), abs(float(c["upper"]) - p)) <= CORRIDOR_EDGE_SHARE * band


# (key, predicate) in priority order. Frozen: a change is a new SALIENCE_VERSION.
SALIENCE = (
    ("stale", _stale),
    ("episode", _episode),
    ("level_at", _level_at),
    ("range_extreme", _range_extreme),
    ("range_high", _range_high),
    ("volume_high", _volume_high),
    ("event_today", _event_today),
    ("corridor_edge", _corridor_edge),
)


def salient(facts: Mapping[str, Any]) -> list:
    """The keys that reach L1, in priority order; ["nothing"] when none fires."""
    out = [k for k, pred in SALIENCE if pred(facts)]
    return out[:L1_MAX] or ["nothing"]
