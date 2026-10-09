"""Pulsy UX V2 facts (docs/PULSY_UX_STANDARD_V2.md §2): a read-only copy of the numbers a screen may
print, taken from the persisted view or notification payload. Nothing is computed here: every value is
a field the old render already prints, at the same path, so a V2 screen can never state a number the
product does not hold. `facts_equivalent` re-reads the payload and lists any fact that drifted."""
from __future__ import annotations

from typing import Any, Mapping, Optional

FACTS_VERSION = "PULSY_FACTS_V1"
LEVELS_PER_SIDE = 3

_H1_KEYS = ("complete", "window_start", "window_end", "price_move_pct", "range_width_pct", "range_ratio",
            "volume_notional_usd", "volume_ratio", "oi_change_pct", "taker_delta_notional_usd_sum", "funding_rate",
            "baseline_days", "baseline_median")
_H24_KEYS = ("price_complete", "window_start", "window_end", "price_move_pct", "range_width_pct", "high", "low",
             "range_ratio", "volume_notional_usd", "volume_ratio", "oi_change_pct", "baseline_days", "baseline_median")


def _pick(src: Optional[Mapping[str, Any]], keys) -> Optional[dict]:
    if not src:
        return None
    return {k: src.get(k) for k in keys}


def _zone(z: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """One level zone as the decision block stores it; the name comes from its members (data), never text."""
    if not z:
        return None
    return {"members": [dict(m) for m in z.get("members") or ()], "kinds": list(z.get("kinds") or ()),
            "edge": z.get("edge"), "low": z.get("low"), "high": z.get("high"),
            "distance_pct": z.get("distance_pct"), "touch": dict(z.get("touch") or {}),
            "history": z.get("history")}


def _episode(ep: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if not ep:
        return None
    return {"event_type": ep.get("event_type"), "state": ep.get("state"),
            "triggered": ep.get("triggered_at") is not None or ep.get("state") == "TRIGGERED"}


def from_view(view: Mapping[str, Any]) -> dict:
    """/btc, /levels and the brief: the persisted view (market_view.build_view)."""
    dec = view.get("decision") or {}
    hz = view.get("horizons") or {}
    levels = dec.get("levels") or {}
    corridor = ((dec.get("corridor") or {}).get("horizons") or {}).get("24h") if dec.get("available") else None
    market = view.get("market") or {}
    return {
        "version": FACTS_VERSION,
        "source": "view",
        "kind": view.get("kind", "btc"),
        "status": view.get("product_status"),
        "status_reasons": list(view.get("status_reasons") or ()),
        "data_through": view.get("data_through"),
        "decision_available": bool(dec.get("available")),
        "decision_reason": dec.get("reason"),
        "price": dec.get("price") if dec.get("available") else None,
        "h1": _pick(hz.get("1h"), _H1_KEYS),
        "h24": _pick(hz.get("24h"), _H24_KEYS),
        "episode": _episode(view.get("active_episode")),
        "ranks_1h": {m: {"rank": (p or {}).get("rank"), "tier": (p or {}).get("tier")}
                     for m, p in ((view.get("context_1h") or {}).get("percentiles") or {}).items()},
        "levels": {
            "above": [_zone(z) for z in (levels.get("above") or ())[:LEVELS_PER_SIDE]],
            "below": [_zone(z) for z in (levels.get("below") or ())[:LEVELS_PER_SIDE]],
            "at": _zone(levels.get("at")),
        },
        "corridor_24h": _pick(corridor, ("lower", "upper", "half_width_pct")),
        "corridor_coverage": (dec.get("corridor") or {}).get("coverage") if dec.get("available") else None,
        "events": [{"kind": e.get("kind"), "at": e.get("at")} for e in (dec.get("events") or ())[:3]],
        "window": _pick(market.get("window"), ("window_start", "window_end", "price_move_pct", "high", "low",
                                               "open", "close", "volume_notional_usd", "oi_change_pct")),
        "window_hours": market.get("window_hours"),
        "interpretation": {h: (r or {}).get("key") for h, r in (market.get("interpretation") or {}).items()},
    }


def from_alert(kind: str, payload: Mapping[str, Any]) -> dict:
    """A market alert as `market_alerts` stored it (level touch, sharp move)."""
    if kind not in ("level", "move"):
        raise ValueError(f"no P0 facts for alert kind {kind!r}")
    base = {"version": FACTS_VERSION, "source": f"alert:{kind}", "at": payload.get("at"), "price": payload.get("price")}
    if kind == "level":
        return {**base, "level_kind": payload.get("level_kind"), "level": payload.get("level"),
                "side": payload.get("side"), "period": payload.get("period"),
                "member": {"kind": payload.get("level_kind"), "price": payload.get("level")}}
    return {**base, "start": payload.get("start"), "open": payload.get("open"), "close": payload.get("close"),
            "move_pct": payload.get("move_pct"), "every_days": payload.get("every_days"),
            "near": [_zone(z) for z in (payload.get("near") or ())[:1]]}


def from_hour_gate(triggered_at: Optional[str], gate: Mapping[str, Any]) -> dict:
    """The unusual-hour push: the push decision's stored hour gate (detector._hour_gate)."""
    values = gate.get("values") or {}
    passed = gate.get("passed") or {}
    return {"version": FACTS_VERSION, "source": "hour", "triggered_at": triggered_at,
            "window_start": gate.get("window_start"), "window_end": gate.get("window_end"),
            "price_move_pct": values.get("price_move_pct"), "open": values.get("open"), "close": values.get("close"),
            "oi_change_pct": values.get("oi_change_pct"),
            "taker_delta_notional_usd": values.get("taker_delta_notional_usd"),
            "passed": {k: passed.get(k) for k in ("price", "range", "volume")},
            "interpretation": (gate.get("interpretation") or {}).get("key")}


def facts_equivalent(facts: Mapping[str, Any], view: Mapping[str, Any]) -> list:
    """The paths whose fact no longer equals the payload (empty = equivalent). Facts are copies only."""
    fresh = from_view(view)
    return sorted(k for k in fresh if fresh[k] != facts.get(k))
