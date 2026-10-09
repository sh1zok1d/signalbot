"""The gallery's SYNTHETIC market states (Pulsy UX V2, P0; the architect's list): 18 named states, each with levels.

They are facts in track A's schema (`beta.ux.facts`), built here. None of it is market data. Each state carries the
screens it can show: btc 1/2/3, levels, level_card, and the notifications that state produces
(hour, level, move, brief). Dates are in 2024 on purpose: no protected 2025/2026 period is represented.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from beta.config import (LIQUIDATION_STRESS_LONG, POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN,
                         TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)
from beta.models import S_DEGRADED, S_STALE
from beta.ux import FACTS_VERSION

T0 = datetime(2024, 3, 4, 6, 0, tzinfo=timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat()


def _zone(kind: str, edge: float, price: float) -> dict:
    return {"members": [{"kind": kind}], "kinds": [kind], "edge": edge, "low": edge * 0.9993, "high": edge * 1.0007,
            "distance_pct": round((edge - price) / price * 100, 2), "touch": {}}


def _rank(r: Optional[float]) -> dict:
    return {"rank": r, "tier": "mature" if r is not None else None}


def view(price: Optional[float], t: datetime, *, rng: float = 0.5, vol: float = 0.5, episode: Optional[str] = None,
         at: Optional[str] = None, above=("PDH", "PWH"), below=("PDL", "PWL"), corridor: tuple = (-1.8, 1.8),
         events=(), status: str = "NO ACTIVE EVENT", reason: Optional[str] = None, move1h: float = 0.1,
         oi1h: float = 0.2, kind: str = "btc", window: Optional[dict] = None, reasons=()) -> dict:
    """View facts (`from_view` shape) for a synthetic state."""
    ok = price is not None and reason is None
    p = price or 0.0
    steps = (0.6, 1.4, 2.3)
    return {
        "version": FACTS_VERSION, "source": "view", "kind": kind, "status": status, "data_through": _iso(t),
        "status_reasons": list(reasons),
        "decision_available": ok, "decision_reason": reason, "price": price if ok else None,
        "h1": {"complete": True, "window_start": _iso(t - timedelta(hours=1)), "window_end": _iso(t),
               "price_move_pct": move1h, "range_width_pct": 0.4 + rng, "range_ratio": 1.0 + rng,
               "volume_notional_usd": 4.0e8 * (1 + 3 * vol), "volume_ratio": 1.0 + 2 * vol, "oi_change_pct": oi1h,
               "taker_delta_notional_usd_sum": None, "funding_rate": 0.0001,
               "baseline_days": {"range_width_pct_median": 30, "volume_notional_usd_sum": 30},
               "baseline_median": {"range_width_pct_median": 0.55, "volume_notional_usd_sum": 6.0e8}},
        "h24": {"price_complete": True, "window_start": _iso(t - timedelta(hours=24)), "window_end": _iso(t),
                "price_move_pct": move1h * 3, "range_width_pct": 2.4, "high": p * 1.012, "low": p * 0.988,
                "range_ratio": 1.1, "volume_notional_usd": 9.0e9, "volume_ratio": 1.0, "oi_change_pct": oi1h * 2,
                "baseline_days": 30, "baseline_median": {}},
        "episode": None if episode is None else {"event_type": episode, "state": "TRIGGERED", "triggered": True},
        "ranks_1h": {"range_width_pct_median": _rank(rng), "volume_notional_usd_sum": _rank(vol)},
        "levels": {"above": [_zone(k, p * (1 + s / 100), p) for k, s in zip(above, steps)] if ok else [],
                   "below": [_zone(k, p * (1 - s / 100), p) for k, s in zip(below, steps)] if ok else [],
                   "at": _zone(at, p * 1.0004, p) if ok and at else None},
        "corridor_24h": {"lower": p * (1 + corridor[0] / 100), "upper": p * (1 + corridor[1] / 100),
                         "half_width_pct": (corridor[1] - corridor[0]) / 2} if ok else None,
        "corridor_coverage": 0.8 if ok else None,
        "events": [{"kind": k, "at": _iso(t + timedelta(hours=h))} for k, h in events],
        "window": window, "window_hours": 8 if window else None, "interpretation": {},
    }


def hour(t: datetime, *, price: float, move: float, oi: float, rng: bool = True, vol: bool = True) -> dict:
    """The unusual-hour push of a state: it closes at the state's price."""
    return {"version": FACTS_VERSION, "source": "hour", "triggered_at": _iso(t),
            "window_start": _iso(t - timedelta(hours=1)), "window_end": _iso(t), "price_move_pct": move,
            "open": round(price / (1 + move / 100), 1), "close": price, "oi_change_pct": oi,
            "taker_delta_notional_usd": None, "passed": {"price": abs(move) > 1, "range": rng, "volume": vol},
            "interpretation": None}


def level_alert(t: datetime, kind: str, level: float, price: float) -> dict:
    return {"version": FACTS_VERSION, "source": "alert:level", "at": _iso(t), "price": price, "level_kind": kind,
            "level": level, "side": "up" if price >= level else "down", "period": "D",
            "member": {"kind": kind, "price": level}}


def move_alert(t: datetime, pct: float, start_price: float) -> dict:
    return {"version": FACTS_VERSION, "source": "alert:move", "at": _iso(t), "price": start_price * (1 + pct / 100),
            "start": _iso(t - timedelta(minutes=15)), "open": start_price, "close": start_price * (1 + pct / 100),
            "move_pct": pct, "every_days": 9, "near": []}


def named_states() -> list:
    """[(sid, name, screens)] for the 18 named states, in the architect's order."""
    def t(h: float) -> datetime:
        return T0 + timedelta(hours=h)

    out = [
        ("calm", view(64210.0, t(0), rng=0.40, vol=0.35)),
        ("compression", view(64480.0, t(3), rng=0.05, vol=0.50, corridor=(-0.9, 0.9), move1h=0.02)),
        ("sharp drop", view(61930.0, t(6), rng=0.995, vol=0.97, move1h=-2.4, oi1h=-1.1),
         {"move": move_alert(t(6), -2.4, 63450.0), "hour": hour(t(6), price=61930.0, move=-2.4, oi=-1.1)}),
        ("sharp rise", view(66120.0, t(9), rng=0.96, vol=0.90, move1h=2.1, oi1h=1.3),
         {"move": move_alert(t(9), 2.1, 64760.0)}),
        ("strong selling", view(63380.0, t(12), rng=0.85, vol=0.96, episode=TAKER_FLOW_EXTREME_SELL, move1h=-0.9),
         {"hour": hour(t(12), price=63380.0, move=-0.9, oi=0.4, rng=False)}),
        ("strong buying", view(65040.0, t(15), rng=0.86, vol=0.97, episode=TAKER_FLOW_EXTREME_BUY, move1h=1.0),
         {"hour": hour(t(15), price=65040.0, move=1.0, oi=0.6, rng=False)}),
        ("OI build-up, flat price", view(64600.0, t(18), rng=0.20, vol=0.60, episode=POSITION_BUILDUP_COMPRESSION,
                                         move1h=0.03, oi1h=3.4)),
        ("OI unwind", view(63900.0, t(21), rng=0.70, vol=0.75, episode=PRICE_OI_CONTRACTION_DOWN, move1h=-0.6,
                           oi1h=-3.8)),
        ("liquidation stress", view(62250.0, t(24), rng=0.997, vol=0.995, episode=LIQUIDATION_STRESS_LONG,
                                    move1h=-1.9, oi1h=-2.6),
         {"hour": hour(t(24), price=62250.0, move=-1.9, oi=-2.6)}),
        ("price at a level above", view(64990.0, t(27), at="PDH", above=("PWH", "PMH"), rng=0.60),
         {"level": level_alert(t(27), "PDH", 65015.0, 64990.0)}),
        ("price at a level below", view(63210.0, t(30), at="PDL", below=("PWL", "PML"), rng=0.62),
         {"level": level_alert(t(30), "PDL", 63185.0, 63210.0)}),
        ("touch of the weekly low", view(61840.0, t(33), at="PWL", below=("PML",), rng=0.96, vol=0.80),
         {"level": level_alert(t(33), "PWL", 61815.0, 61840.0)}),
        ("near a corridor edge", view(65380.0, t(36), rng=0.55, corridor=(-2.1, 0.08))),
        ("CPI / FOMC later today", view(64050.0, t(39), rng=0.30, events=(("CPI", 6.5), ("FOMC", 30)))),
        ("weekend thin trading", view(64330.0, T0 + timedelta(days=5, hours=4), rng=0.02, vol=0.01, move1h=0.01,
                                      corridor=(-0.7, 0.7))),
        ("stale data", view(None, t(45), status=S_STALE, reason="DATA_STALE")),
        ("degraded data", view(64120.0, t(48), status=S_DEGRADED, rng=0.5, reasons=("FAMILY_UNUSABLE:oi",))),
        ("quiet night (brief)", view(64270.0, t(50), rng=0.15, vol=0.08, kind="brief",
                                     window={"window_start": _iso(t(42)), "window_end": _iso(t(50)),
                                             "price_move_pct": 0.3, "high": 64390.0, "low": 63980.0,
                                             "open": 64080.0, "close": 64270.0, "volume_notional_usd": 2.1e9,
                                             "oi_change_pct": 0.4}),
         {"brief": None}),
    ]
    states = []
    for i, item in enumerate(out, start=1):
        name, f = item[0], item[1]
        extra = dict(item[2]) if len(item) > 2 else {}
        screens = {"btc": f, "levels": f, "level_card": f}      # the card takes its zone itself (track A)
        for k, v in extra.items():
            screens[k] = f if v is None else v
        states.append((f"S{i:02d}", name, screens))
    return states
