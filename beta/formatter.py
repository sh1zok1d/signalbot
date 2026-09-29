"""Beta V0.2 user-facing wording — descriptive only, HTML for Telegram.

A NEW model/formatter: no LONG/SHORT direction, confidence or score fields, and
nothing from the legacy forecast notifier. Every rendered message passes
`assert_descriptive`, which rejects trade-instruction / predictive wording.
Messages always show the event DECISION time (bucket close), not just send time.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from .config import (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, POSITION_BUILDUP_COMPRESSION,
                     PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY,
                     TAKER_FLOW_EXTREME_SELL)

EVENT_LABELS = {
    PRICE_OI_CONTRACTION_DOWN: "price + OI contraction down",
    PRICE_OI_CONTRACTION_UP: "price + OI contraction up",
    POSITION_BUILDUP_COMPRESSION: "position build-up with range compression",
    TAKER_FLOW_EXTREME_BUY: "taker flow extreme (buyer-initiated)",
    TAKER_FLOW_EXTREME_SELL: "taker flow extreme (seller-initiated)",
    LIQUIDATION_STRESS_LONG: "liquidation stress (long-side liquidations)",
    LIQUIDATION_STRESS_SHORT: "liquidation stress (short-side liquidations)",
}
EVENT_DESCRIPTIONS = {
    PRICE_OI_CONTRACTION_DOWN: "5m price move in the bottom 5% of the last 30 days while open "
                               "interest fell in its bottom 10%, on at least 2 venues.",
    PRICE_OI_CONTRACTION_UP: "5m price move in the top 5% of the last 30 days while open "
                             "interest fell in its bottom 10%, on at least 2 venues.",
    POSITION_BUILDUP_COMPRESSION: "Open interest growing (top 20% of 30d) with a narrow 5m range "
                                  "(bottom 40%) and at least median volume, for 45 consecutive minutes.",
    TAKER_FLOW_EXTREME_BUY: "Taker delta in the top 5% of the last 30 days for two consecutive 5m buckets.",
    TAKER_FLOW_EXTREME_SELL: "Taker delta in the bottom 5% of the last 30 days for two consecutive 5m buckets.",
    LIQUIDATION_STRESS_LONG: "Long-side liquidation notional in the top 5% of its own 30d history "
                             "on at least 2 healthy venues in the same 5m bucket.",
    LIQUIDATION_STRESS_SHORT: "Short-side liquidation notional in the top 5% of its own 30d history "
                              "on at least 2 healthy venues in the same 5m bucket.",
}
STATE_LABELS = {"EARLY": "early", "ARMED": "armed", "TRIGGERED": "triggered",
                "ENDED": "ended", "EXPIRED": "expired"}
DISCLAIMER = ("<i>Experimental closed beta. Descriptive market-state observation only — "
              "not investment advice and not a trade instruction.</i>")

# Rejected in any user-facing text (case-insensitive unless noted).
_FORBIDDEN = [
    r"\bbuy\b", r"\bsell\b", r"\b(long|short)\s+now\b", r"\bgo\s+(long|short)\b",
    r"\bentry\b", r"\bentries\b", r"\bstop[- ]?loss\b", r"\btake[- ]?profit\b", r"\btargets?\b",
    r"\bleverage\b", r"\bposition[- ]siz", r"probabilit", r"\blikely\b", r"\bimpulse\b",
    r"\bwin(s|ning)?\b", r"\bloss(es)?\b", r"win[- ]?rate", r"\bmfe\b", r"\bmae\b",
    r"\brecommend", r"\bprofit\b", r"\bsignal\b", r"\bforecast", r"\bpredict",
]
_FORBIDDEN_CASE = [r"\bLONG\b", r"\bSHORT\b", r"\bBUY\b", r"\bSELL\b"]


class ForbiddenWordingError(ValueError):
    pass


def assert_descriptive(text: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", text)
    for pat in _FORBIDDEN:
        if re.search(pat, plain, flags=re.IGNORECASE):
            raise ForbiddenWordingError(f"forbidden wording matched {pat!r}")
    for pat in _FORBIDDEN_CASE:
        if re.search(pat, plain):
            raise ForbiddenWordingError(f"forbidden wording matched {pat!r}")
    return text


def _e(s: Any) -> str:
    return html.escape(str(s), quote=False)


def ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _pct_rank(snapshot: Mapping[str, Any], key: str) -> str:
    p = (snapshot.get("percentiles") or {}).get(key) or {}
    if p.get("rank") is None:
        return "n/a"
    if p.get("tier") != "mature":
        return f"not evaluable ({_e(p.get('tier'))} history)"
    return f"{p['rank'] * 100:.0f}th pct of 30d"


def _fmt_num(v: Optional[float], nd: int = 2, suffix: str = "%") -> str:
    return "n/a" if v is None else f"{v:+.{nd}f}{suffix}"


# ---- static texts --------------------------------------------------------------
CLOSED_BETA_TEXT = "This is a closed private beta. Access is by invitation only."

PRIVACY_NOTICE = assert_descriptive(
    "<b>Signalbot closed beta — privacy notice</b>\n"
    "• We store your Telegram user id and chat id to send you beta messages, plus your "
    "Useful/Noise votes and delivery status.\n"
    "• Market/event records contain no personal data.\n"
    "• /stop pauses all messages. /delete_me deletes your participant data and removes "
    "you from the beta.\n"
    "• After /stop, your data is deleted automatically after 30 days.\n"
    "• Nothing here is investment advice; the bot never places or suggests trades.\n\n"
    "Press <b>Join</b> to accept and join the beta.")

HELP_TEXT = assert_descriptive(
    "<b>Signalbot closed beta — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
    "The bot watches a few frozen, deterministic, unusual market states and tells you when one "
    "is observed. It does not tell you what to trade.\n\n"
    "/btc — compact BTC perpetual state (calm, unusual now, calmed, history building, "
    "or data incomplete). Details holds the measurements.\n"
    "/history — recent detector episodes, pushed or not, with factual follow-up ranges\n"
    "/stop — pause messages · /delete_me — delete your data\n\n" + DISCLAIMER)


def event_label(event_type: str) -> str:
    return EVENT_LABELS[event_type]


# ---- /btc ---------------------------------------------------------------------
def format_status(status: Mapping[str, Any], open_episodes: Sequence[Any],
                  snapshot: Optional[Mapping[str, Any]]) -> str:
    lines = [f"<b>BTCUSDT perp — {_e(status['status'])}</b>"]
    last = status.get("last_good_bucket")
    if last is not None:
        lines.append(f"Last evaluation: 5m bucket closed {ts(last + timedelta(minutes=5))}")
    else:
        lines.append("Last evaluation: none yet")
    if status["status"] in ("DATA DEGRADED", "DATA STALE"):
        lines.append("Current observability is insufficient; the absence of events cannot be "
                     "claimed right now.")
    for ep in open_episodes:
        lines.append(f"• {_e(event_label(ep.event_type))} — {STATE_LABELS[ep.state]} "
                     f"(since {ts(ep.opened_at)})")
    if snapshot is not None and snapshot.get("materialized") and status["status"] != "DATA STALE":
        lines.append("\n<b>Context (5m, cross-venue)</b>")
        lines.append(f"price move: {_pct_rank(snapshot, 'c:price_move_pct_median')}")
        lines.append(f"OI change: {_pct_rank(snapshot, 'c:oi_change_pct_median')}")
        lines.append(f"range width: {_pct_rank(snapshot, 'c:range_width_pct_median')}")
        lines.append(f"volume: {_pct_rank(snapshot, 'c:volume_notional_usd_sum')}")
        ref = snapshot.get("reference") or {}
        if ref.get("status") == "OK":
            lines.append(f"composite close: {ref['price']:,.1f} ({', '.join(ref['exchanges'])})")
        evals = snapshot.get("rule_evaluations") or {}
        gated = sorted(k for k, v in evals.items() if v.get("status") == "NOT_EVALUABLE")
        if gated:
            lines.append("not evaluable now: " + ", ".join(_e(event_label(k)) for k in gated))
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


# ---- push -------------------------------------------------------------------------
def format_push(episode: Any, snapshot: Optional[Mapping[str, Any]] = None) -> str:
    lines = [f"<b>BTCUSDT perp — EVENT: {_e(event_label(episode.event_type))}</b>",
             f"Decision time: {ts(episode.triggered_at)} (5m bucket close)",
             _e(EVENT_DESCRIPTIONS[episode.event_type])]
    if episode.reference_price is not None:
        lines.append(f"Composite close at decision: {episode.reference_price:,.1f} "
                     f"({', '.join(episode.reference_exchanges)})")
    lines.append(f"Episode {episode.public_id} · rules {_e(episode.rules_version)}")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


# ---- /history + details ---------------------------------------------------------------
def _range_summary(outcomes: Iterable[Mapping[str, Any]]) -> str:
    parts = []
    for o in sorted(outcomes, key=lambda o: ["15m", "30m", "1h", "4h", "24h"].index(o["horizon"])):
        mark = "*" if (o.get("revision") or 1) > 1 else ""
        if o["status"] == "COMPLETE":
            parts.append(f"{o['horizon']} range {o['realized_range_pct']:.2f}%{mark}")
        else:
            parts.append(f"{o['horizon']} {o['status'].lower().replace('_', ' ')}")
    return "; ".join(parts) if parts else "follow-up pending"


def push_status_label(row: Mapping[str, Any]) -> str:
    decision = row.get("decision")
    if decision is None:
        return "no push (not triggered)"
    if decision == "SUPPRESSED":
        return f"SUPPRESSED ({row.get('suppression_reason')})"
    states = set(row.get("delivery_states") or ())
    if "SENT" in states:
        return "SENT"
    if "DELIVERY_UNKNOWN" in states:
        return "UNKNOWN"
    if "EXPIRED_UNDELIVERED" in states:
        return "EXPIRED"
    return "PUSH (pending)"


def format_history(rows: Sequence[Mapping[str, Any]],
                   outcomes_by_pk: Mapping[int, Sequence[Mapping[str, Any]]]) -> str:
    lines = ["<b>Detector history (all episodes, pushed or not)</b>"]
    if not rows:
        lines.append("No episodes recorded yet.")
    for r in rows:
        corr = " ⚠ corrected input" if r.get("correction_flag") else ""
        term = f", {r['terminal_reason'].lower().replace('_', ' ')}" if r.get("terminal_reason") else ""
        lines.append(
            f"• {r['public_id']} {_e(event_label(r['event_type']))} — "
            f"{STATE_LABELS[r['state']]}{term}{corr}\n"
            f"  opened {ts(r['opened_at'])}; triggered {ts(r.get('triggered_at'))}; "
            f"push {push_status_label(r)}\n"
            f"  {_range_summary(outcomes_by_pk.get(r['episode_pk'], ()))}")
    lines.append("<i>Ranges are absolute (max − min) moves after the decision time; "
                 "* = revised after a data correction.</i>")
    return assert_descriptive("\n".join(lines))


def format_details(episode: Any, transitions: Sequence[Mapping[str, Any]],
                   outcomes: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"<b>{episode.public_id} — {_e(event_label(episode.event_type))}</b>",
             _e(EVENT_DESCRIPTIONS[episode.event_type]),
             f"Rules {_e(episode.rules_version)} ({episode.rules_digest[:12]})"]
    for t in transitions:
        lines.append(f"• {ts(t['decision_ts'])}: {STATE_LABELS[t['to_state']]} "
                     f"({t['reason'].lower().replace('_', ' ')})")
    if episode.reference_price is not None:
        lines.append(f"Composite close at decision: {episode.reference_price:,.1f}")
    for o in sorted(outcomes, key=lambda o: ["15m", "30m", "1h", "4h", "24h"].index(o["horizon"])):
        if o["status"] == "COMPLETE":
            lines.append(f"{o['horizon']}: range {o['realized_range_pct']:.2f}%, "
                         f"max up {_fmt_num(o['max_up_pct'])}, max down {_fmt_num(-o['max_down_pct'])}, "
                         f"close {_fmt_num(o['close_return_pct'])}"
                         + (" (revised)" if (o.get("revision") or 1) > 1 else ""))
        else:
            lines.append(f"{o['horizon']}: {o['status'].lower().replace('_', ' ')}")
    if episode.correction_flag:
        lines.append(f"⚠ corrected input: {_e(episode.correction_note or '')}")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


def format_owner_alert(alerts: Sequence[Mapping[str, Any]]) -> str:
    lines = ["<b>Signalbot beta — owner health alert</b>"]
    for a in alerts:
        lines.append(f"• {_e(a['key'])} {_e(a.get('detail') or '')}")
    return "\n".join(lines)


# ---- /btc with temporal context (ACTIVE / LAST EVENT · anchor bucket · NOW · 1h) ------------
TERMINAL_WORDS = {"CONDITION_FAILED": "condition no longer met", "NOT_EVALUABLE": "data not evaluable",
                  "DETECTION_GAP": "detection gap", "DETECTOR_VERSION_CHANGED": "rules/data version changed",
                  "MAX_DURATION": "maximum duration reached"}
ANCHOR_WORDS = {"STRONGEST_OBSERVED_BUCKET": "Strongest observed bucket", "TRIGGER_BUCKET": "Trigger bucket",
                "OPENING_BUCKET": "Opening bucket"}
def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _hm(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%H:%M")


def _window(first_bucket: str, last_bucket: Optional[str] = None) -> str:
    """Bucket start of `first_bucket` to bucket END of `last_bucket` (HH:MM–HH:MM)."""
    return f"{_hm(_dt(first_bucket))}–{_hm(_dt(last_bucket or first_bucket) + timedelta(minutes=5))}"


def _dur(minutes: float) -> str:
    m = int(max(0, round(minutes)))
    if m < 60:
        return f"{m}m"
    if m % 60 == 0:
        return f"{m // 60}h"
    return f"{m // 60}h{m % 60:02d}m"


def _usd(v: Optional[float], *, signed: bool = False) -> str:
    if v is None:
        return "n/a"
    sign = ("+" if v > 0 else "−" if v < 0 else "") if signed else ""
    a = abs(v)
    body = f"${a / 1e9:.1f}B" if a >= 1e9 else f"${a / 1e6:.1f}M" if a >= 1e6 else \
        f"${a / 1e3:.0f}K" if a >= 1e3 else f"${a:.0f}"
    return sign + body


def _signed_pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:+.2f}%".replace("-", "−")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


# Main-screen names. Detector lifecycle words stay in Details.
_PLAIN = {PRICE_OI_CONTRACTION_DOWN: "unusual drop", PRICE_OI_CONTRACTION_UP: "unusual rise",
          POSITION_BUILDUP_COMPRESSION: "position build-up",
          TAKER_FLOW_EXTREME_BUY: "buyer-initiated flow", TAKER_FLOW_EXTREME_SELL: "seller-initiated flow",
          LIQUIDATION_STRESS_LONG: "long-side liquidations", LIQUIDATION_STRESS_SHORT: "short-side liquidations"}
_PRICE_OI = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP)
_TAKER = (TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)
_KNOWN_HEADLINES = {"DATA STALE", "DATA DEGRADED", "DETECTOR NOT READY", "HISTORY BUILDING",
                    "EVENT ACTIVE", "WATCH", "NO ACTIVE EVENTS"}
_INSUFFICIENT = ("Current observability is insufficient; the absence of events cannot be "
                 "claimed right now.")
_DATA_END = {"DETECTION_GAP": "A recent event ended on a data gap",
             "NOT_EVALUABLE": "A recent event ended because data was not evaluable",
             "DETECTOR_VERSION_CHANGED": "A recent event ended on a version change"}


def _reached(ep: Mapping[str, Any]) -> str:
    return "triggered" if ep.get("triggered_at") else "armed" if ep.get("armed_at") else "early"


def _screen_title(view: Mapping[str, Any]) -> str:
    """User-facing title. Unknown headlines are passed through so wording checks still see them."""
    h = view.get("headline") or ""
    if h not in _KNOWN_HEADLINES:
        return h
    if h in ("DATA STALE", "DATA DEGRADED", "DETECTOR NOT READY"):
        return "data incomplete"
    if h == "HISTORY BUILDING":
        return "history building"
    if view.get("active_episode") is not None or h in ("EVENT ACTIVE", "WATCH"):
        return "unusual now"
    last = view.get("last_event")
    if last is not None:
        return "calmed" if last.get("terminal_reason") == "CONDITION_FAILED" else "event ended"
    return "calm"


def _intensity(cfg, rank: Optional[float], tier: Optional[str]) -> int:
    """1, 2 or 3 arrows from the frozen context tails. Immature history is direction only."""
    if rank is None or tier != "mature":
        return 1
    c = cfg.section("context")
    if rank >= c["label_extreme"] or rank <= 1.0 - c["label_extreme"]:
        return 3
    if rank >= c["label_high"] or rank <= 1.0 - c["label_high"]:
        return 2
    return 1


def _signed_arrows(cfg, metric: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not metric or metric.get("value") is None:
        return None
    v = metric["value"]
    if v == 0:
        return "·"
    return ("↑" if v > 0 else "↓") * _intensity(cfg, metric.get("rank"), metric.get("tier"))


def _volume_arrows(cfg, metric: Optional[Mapping[str, Any]]) -> Optional[str]:
    from .context import level_label
    if not metric:
        return None
    n = {"elevated": 1, "high": 2, "extreme": 3}.get(
        level_label(cfg, metric.get("rank"), metric.get("tier")) or "")
    return None if not n else "↑" * n


def _reading_line(cfg, event_type: str, view: Mapping[str, Any]) -> str:
    if event_type in _PRICE_OI:
        parts = []
        price, oi = _signed_arrows(cfg, view["price_move_pct"]), _signed_arrows(cfg, view["oi_change_pct"])
        vol = _volume_arrows(cfg, view["volume_notional_usd"])
        if price and price != "·":
            parts.append(f"Price {price}")
        if oi and oi != "·":
            parts.append(f"OI {oi}")
        if vol:
            parts.append(f"Volume {vol}")
        return " · ".join(parts) or "n/a"
    if event_type == POSITION_BUILDUP_COMPRESSION:
        parts = []
        oi, vol = _signed_arrows(cfg, view["oi_change_pct"]), _volume_arrows(cfg, view["volume_notional_usd"])
        if oi and oi != "·":
            parts.append(f"OI {oi}")
        if vol:
            parts.append(f"Volume {vol}")
        return " · ".join(parts) or "n/a"
    if event_type in _TAKER:
        parts = []
        taker, price = _signed_arrows(cfg, view["taker_delta_notional_usd"]), _signed_arrows(cfg, view["price_move_pct"])
        if taker and taker != "·":
            parts.append(f"Taker flow {taker}")
        if price and price != "·":
            parts.append(f"Price {price}")
        return " · ".join(parts) or "n/a"
    side = "long" if event_type == LIQUIDATION_STRESS_LONG else "short"
    liq = view["liquidations"][side]
    if liq["rule_status"] == "NOT_EVALUABLE":
        return f"{_cap(side)}-side liquidations not evaluable"
    return f"{_cap(side)}-side liquidations {len(liq['voting'])}/{len(liq['eligible'])} venues"


def _why_line(cfg, event_type: str, view: Mapping[str, Any]) -> Optional[str]:
    if event_type == POSITION_BUILDUP_COMPRESSION:
        from .context import level_label
        m = view["oi_change_pct"]
        label = level_label(cfg, m.get("rank"), m.get("tier"))
        if label in ("elevated", "high", "extreme"):
            return f"Open interest {label}"
        v = m.get("value")
        if v is None or v == 0:
            return None
        return "Open interest rose" if v > 0 else "Open interest fell"
    if event_type not in _PRICE_OI:
        return None
    price, oi = view["price_move_pct"].get("value"), view["oi_change_pct"].get("value")
    if price is None or oi is None or price == 0 or oi == 0:
        return None
    up, oi_up = price > 0, oi > 0
    if up and not oi_up:
        base = "Positions shrank during the rise"
    elif not up and not oi_up:
        base = "Positions shrank during the drop"
    elif up and oi_up:
        base = "Price and open positions both rose"
    else:
        base = "Open positions grew while price fell"
    side = "short" if up else "long"
    liq = (view.get("liquidations") or {}).get(side) or {}
    need = cfg.rule("LIQUIDATION_STRESS")["min_eligible_venues"]
    votes, eligible = liq.get("voting") or [], liq.get("eligible") or []
    if not oi_up and liq.get("rule_status") not in (None, "NOT_EVALUABLE") and len(votes) >= need and eligible:
        move = "Rise" if up else "Drop"
        return f"{move}, falling OI, elevated {side}-side liquidations"
    return base


def _hour_line(cfg, c1h: Optional[Mapping[str, Any]]) -> str:
    if c1h is None:
        return "1h activity: incomplete"
    from .context import level_label
    pr, bits, immature = c1h.get("percentiles") or {}, [], True
    for key, name in (("volume_notional_usd_sum", "volume"), ("range_width_pct_median", "range")):
        p = pr.get(key) or {}
        label = level_label(cfg, p.get("rank"), p.get("tier"))
        if label:
            immature = False
            bits.append(f"{name}: {label}")
        elif c1h.get(key) is None:
            immature = False
            bits.append(f"{name}: n/a")
        else:
            bits.append(f"{name}: history building")
    return "1h activity: history building" if immature else "1h " + " · ".join(bits)


def _retention_phrase(cfg) -> str:
    m = int(cfg.section("context")["last_event_retention_min"])
    return f"{m // 60}h" if m >= 60 and m % 60 == 0 else _dur(m)


def _ago_phrase(view: Mapping[str, Any], ep: Mapping[str, Any]) -> str:
    minutes = (_dt(view["requested_at"]) - _dt(ep["terminal_at"])).total_seconds() / 60
    m = int(max(0, round(minutes)))
    return "just ended" if m == 0 else f"{_dur(m)} ago"


def _core_gap_line(rd: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not rd:
        return None
    core = next(g for g in rd["groups"] if g["group"] == "PRICE_OI")
    if core["status"] == "READY":
        return None
    if core["status"] == "HISTORY_BUILDING":
        p = core.get("progress") or {}
        if p.get("span_days") is not None:
            return f"Price/OI history {p['span_days']:.1f}d / {rd['maturity_days']:.0f}d"
        return "Price/OI history still maturing"
    if core["status"] == "DATA_UNAVAILABLE":
        return "Price/OI cannot be evaluated right now"
    if core["status"] == "DISABLED":
        return "Price/OI is switched off"
    return None


def _noticed_lines(cfg, view: Mapping[str, Any], ep: Mapping[str, Any], *, active: bool) -> list:
    lines = []
    if not active:
        lines.append(f"{_ago_phrase(view, ep)}: {_PLAIN[ep['event_type']]}")
    anchor = (ep.get("anchor") or {}).get("view")
    if anchor is None:
        lines.append("Measurements are not available")
        return lines
    lines.append(_reading_line(cfg, ep["event_type"], anchor))
    why = _why_line(cfg, ep["event_type"], anchor)
    if why:
        lines.append(why)
    return lines


def _after_lines(view: Mapping[str, Any], ep: Optional[Mapping[str, Any]],
                 last: Optional[Mapping[str, Any]]) -> list:
    if ep is not None:
        lines = ["Still active"]
        others = view.get("other_active") or []
        if others:
            lines.append("Also open: " + ", ".join(_PLAIN[et] for et, _st in others))
        return lines
    if last is None:
        return []
    reason = last.get("terminal_reason")
    if reason in _DATA_END:
        return [_DATA_END[reason]]
    if reason == "MAX_DURATION":
        return ["Ended at the duration cap"]
    if reason == "CONDITION_FAILED":
        return ["Event has ended"]
    return ["Event has ended"]


def format_btc(cfg, view: Mapping[str, Any]) -> str:
    """Compact mobile /btc from the factual view model. Presentation only: no score,
    no direction call, no detector lifecycle words. Evidence stays in Details."""
    title = _screen_title(view)
    lines = [f"<b>BTC · {_e(title)}</b>"]
    status = view["product_status"]
    if status in ("DATA DEGRADED", "DATA STALE"):
        lines.append(_INSUFFICIENT)
    if not view.get("projection_available") and status in ("WATCH", "EVENT ACTIVE"):
        lines.append("Episode details are not available right now.")
    ep, last = view.get("active_episode"), view.get("last_event")
    shown = ep or last
    market_ok = status not in ("DATA DEGRADED", "DATA STALE")
    if shown is not None:
        lines.extend(_noticed_lines(cfg, view, shown, active=ep is not None))
    elif market_ok and title == "calm":
        lines.append("No unusual state now")
    if market_ok and title in ("history building", "data incomplete", "unusual now"):
        gap = _core_gap_line(view.get("readiness"))
        if gap:
            lines.append(gap)
        if title == "history building" and shown is None:
            lines.append("Unusual states are not evaluated yet")
    if market_ok and view.get("projection_available"):
        lines.append(_hour_line(cfg, view.get("context_1h")))
    if market_ok and title == "calm":
        lines.append(f"No notable event in the last {_retention_phrase(cfg)}")
    if shown is not None and (market_ok or status in ("DATA DEGRADED", "DATA STALE")):
        lines.extend(_after_lines(view, ep, last))
    lines.append(f"Data through {_hm(_dt(view['data_through']))} UTC" if view.get("data_through")
                 else "No evaluation yet")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


def btc_buttons(view: Mapping[str, Any]):
    """Details for the open/retained episode, or the latest bucket when there is none.
    Readiness is only a button while some family is not ready. The handlers stay."""
    focus = view.get("active_episode") or view.get("last_event")
    row = []
    if focus and focus.get("episode_id"):
        row.append(("Details", "c:" + focus["episode_id"]))
    elif view.get("now"):
        row.append(("Details", "n:latest"))
    rd = view.get("readiness")
    if rd and any(g.get("status") != "READY" for g in rd.get("groups") or ()):
        row.append(("Readiness", "r:latest"))
    return [row] if row else None


def _metric_line(key: str, name: str, m: Mapping[str, Any]) -> str:
    if key.endswith("usd"):
        val = _usd(m["value"], signed=key == "taker_delta_notional_usd")
    elif key == "range_width_pct":
        val = "n/a" if m["value"] is None else f"{m['value']:.2f}%"
    else:
        val = _signed_pct(m["value"])
    rank = "n/a" if m.get("rank") is None else f"{m['rank'] * 100:.1f} pct of 30d ({m.get('tier')})"
    return f"  {name}: {val} · {rank}"


def _venue_line(label: str, vd: Optional[Mapping[str, Any]]) -> Optional[str]:
    if vd is None:
        return None
    return (f"  {label} by venue: up {','.join(vd['up']) or '—'} · down {','.join(vd['down']) or '—'}"
            f" · flat {','.join(vd['flat']) or '—'}")


def _metric_sections(v: Optional[Mapping[str, Any]]) -> tuple:
    """MARKET / OI / FLOW lines. Strings stay stable so Details evidence is not dropped."""
    if v is None:
        return ["  n/a"], ["  n/a"], ["  n/a"]
    market = [_metric_line("price_move_pct", "price move", v["price_move_pct"]),
              _metric_line("range_width_pct", "range width", v["range_width_pct"]),
              _metric_line("volume_notional_usd", "volume", v["volume_notional_usd"])]
    price_venues = _venue_line("price", v["venue_direction"]["price"])
    if price_venues:
        market.append(price_venues)
    oi = [_metric_line("oi_change_pct", "OI change", v["oi_change_pct"])]
    oi_venues = _venue_line("OI", v["venue_direction"]["oi"])
    if oi_venues:
        oi.append(oi_venues)
    oi.append("  Direction only. Per-venue OI percents are not in this view.")
    flow = [_metric_line("taker_delta_notional_usd", "taker delta", v["taker_delta_notional_usd"])]
    taker_venues = _venue_line("taker delta", v["venue_direction"]["taker"])
    if taker_venues:
        flow.append(taker_venues)
    for side in ("long", "short"):
        liq = v["liquidations"][side]
        per = ", ".join(f"{ex} {_usd(x)}" for ex, x in liq["per_venue"].items() if x is not None) or "none observed"
        flow.append(f"  {side}-side liquidations by venue: {per} · top-5% votes "
                    f"{','.join(liq['voting']) or '—'} of eligible {','.join(liq['eligible']) or '—'}")
    return market, oi, flow


def _append_sections(lines: list, v: Optional[Mapping[str, Any]]) -> None:
    market, oi, flow = _metric_sections(v)
    lines.append("\n<b>MARKET</b>")
    lines += market
    lines.append("\n<b>OI BY VENUE</b>")
    lines += oi
    lines.append("\n<b>FLOW</b>")
    lines += flow


def _append_1h(lines: list, state: Mapping[str, Any]) -> None:
    c1h = state.get("context_1h")
    lines.append("\n<b>Rolling 1h</b> (last 12 closed 5m buckets)")
    if c1h is None:
        lines.append("  n/a")
        return
    for key, name in (("range_width_pct_median", "range"), ("price_move_pct_median", "price move"),
                      ("volume_notional_usd_sum", "volume")):
        v = c1h.get(key)
        p = (c1h.get("percentiles") or {}).get(key) or {}
        val = _usd(v) if key.endswith("sum") else _signed_pct(v)
        rank = "n/a" if p.get("rank") is None else f"{p['rank'] * 100:.1f} pct of rolling-1h 30d ({p.get('tier')})"
        lines.append(f"  {name}: {val} · {rank}")
    lines.append(f"  venues: {', '.join(c1h.get('venues') or []) or '—'}")


def _append_data_footer(lines: list, state: Mapping[str, Any]) -> None:
    now = state.get("now") or {}
    ref = now.get("reference_price")
    if ref is not None:
        lines.append(f"Reference price {ref:,.1f}")
    cov = (now.get("coverage") or {}).get("price_structure") or {}
    if cov.get("available") is not None:
        lines.append(f"Venues {cov['available']}/{cov['expected']}")


def format_context_details(cfg, episode: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    lines = ["<b>EVENT</b>",
             f"<b>{_e(episode['episode_id'])} — {_e(event_label(episode['event_type']))}</b>",
             _e(EVENT_DESCRIPTIONS[episode["event_type"]]),
             f"Detector state {STATE_LABELS[episode['state']]} · reached {_reached(episode)} · qualifying "
             f"{_window(episode['opened_bucket'], episode['last_bucket'])} UTC ({episode['qualifying_buckets']} buckets)"]
    if episode.get("terminal_at"):
        lines.append(f"Ended {ts(_dt(episode['terminal_at']))}: "
                     f"{TERMINAL_WORDS.get(episode['terminal_reason'], 'ended')}")
    a = episode.get("anchor")
    if a is not None:
        lines.append(f"\n<b>{ANCHOR_WORDS[a['kind']]}</b> {_window(a['bucket_ts'])} UTC")
        _append_sections(lines, a["view"])
    lines.append(f"\n<b>Now</b> {_window(state['now']['bucket_ts']) + ' UTC' if state.get('now') else ''}")
    _append_sections(lines, state.get("now"))
    lines.append("\n<b>DATA</b>")
    _append_1h(lines, state)
    _append_data_footer(lines, state)
    lines.append(f"\nEpisodization {_e(episode['episodization_version'])} ({episode['episodization_digest'][:12]}): "
                 f"detector episode boundaries · context {_e(state.get('context_version'))}")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


def format_now_details(cfg, state: Mapping[str, Any]) -> str:
    """Evidence for a calm screen: latest bucket and rolling 1h, no episode."""
    now = state.get("now")
    lines = ["<b>DETAILS</b>", "Latest bucket and rolling 1h. No open or retained event."]
    lines.append(f"\n<b>Now</b> {_window(now['bucket_ts']) + ' UTC' if now else ''}")
    _append_sections(lines, now)
    lines.append("\n<b>DATA</b>")
    _append_1h(lines, state)
    _append_data_footer(lines, state)
    lines.append(f"\nContext {_e(state.get('context_version'))}")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


# ---- detector readiness (read model; beta.readiness) ----------------------------------
READINESS_WORDS = {"READY": "ready", "HISTORY_BUILDING": "history building",
                   "DATA_UNAVAILABLE": "data unavailable", "DEGRADED": "degraded", "DISABLED": "disabled"}
_HISTORY_NAMES = {"c:price_move_pct_median": "price history", "c:oi_change_pct_median": "OI history",
                  "c:range_width_pct_median": "range history", "c:volume_notional_usd_sum": "volume history",
                  "c:taker_delta_notional_usd_sum": "taker-flow history",
                  "x:*:long_liquidation_notional": "long-side liquidation history",
                  "x:*:short_liquidation_notional": "short-side liquidation history"}
_FAMILY_WORDS = {"price_structure": "price", "oi": "OI", "volume": "volume", "taker_flow": "taker flow"}


def _readiness_reason(cfg, reason: Optional[str]) -> str:
    r = reason or ""
    if r.startswith("FAMILY_UNUSABLE:"):
        fam = r.split(":", 1)[1]
        return f"fewer than {cfg.min_venues} usable venues for {_FAMILY_WORDS.get(fam, fam)}"
    if r == "INSUFFICIENT_ELIGIBLE_VENUES":
        return "fewer than the required eligible live feeds"
    if r.startswith("VALUE_UNAVAILABLE"):
        return "current value unavailable"
    if r.startswith("PERCENTILE_MISSING"):
        return "percentile unavailable"
    return {"NOT_MATERIALIZED": "latest bucket not materialized", "EVALUATION_NOT_FRESH": "evaluation late",
            "STALE_BARRIER": "inputs changed during evaluation", "RULE_DISABLED": "switched off",
            "NOT_EVALUATED": "not evaluated"}.get(r, r.lower().replace("_", " ") or "unknown")


def _group_text(cfg, g: Mapping[str, Any], maturity_days: float) -> str:
    st = g["status"]
    if st == "READY":
        return "ready"
    text = READINESS_WORDS[st]
    if st == "HISTORY_BUILDING" and g.get("progress"):
        p = g["progress"]
        text += (f" · {_HISTORY_NAMES.get(p['metric'], 'history')} "
                 f"{p['span_days']:.1f}d / {maturity_days:.0f}d")
    elif st in ("DATA_UNAVAILABLE", "DEGRADED"):
        text += f" · {_readiness_reason(cfg, g.get('reason'))}"
    if g.get("partly_ready"):
        text = f"partly ready ({g['ready_members']}/{g['enabled_members']} rules) · {text}"
    return text


def format_readiness_details(cfg, rd: Mapping[str, Any]) -> str:
    """Per-rule readiness for the latest closed bucket: status, detector reason,
    percentile tier / samples / history span, and liquidation venue eligibility."""
    close = _dt(rd["bucket_ts"]) + timedelta(minutes=5)
    lines = [f"<b>Detector readiness — bucket closed {ts(close)}</b>",
             f"Maturity needs {rd['maturity_days']:.0f} days of valid history per required percentile "
             f"(counted from the earliest valid sample, not from deployment)."]
    for g in rd["groups"]:
        lines.append(f"\n<b>{_e(g['label'])}</b>: {_group_text(cfg, g, rd['maturity_days'])}")
        for et in g["members"]:
            e = rd["events"][et]
            lines.append(f"• {_e(event_label(et))}: {READINESS_WORDS[e['status']]}"
                         + (f" ({_e(e['reason'])})" if e.get("reason") else ""))
            for key, m in (e.get("metrics") or {}).items():
                lines.append(f"  {_e(_HISTORY_NAMES.get(key, key))}: {m['tier'] or 'n/a'} · "
                             f"{m['sample_size'] or 0} samples · {m['span_days']:.1f}d span")
            for ex, v in (e.get("venues") or {}).items():
                lines.append(f"  {ex}: {READINESS_WORDS[v['state']]}"
                             + (f" ({_e(v['reason'])})" if v.get("reason") else "")
                             + f" · {v['tier'] or 'n/a'} · {v['span_days']:.1f}d span")
    lines.append(f"\nRead model {_e(rd['readiness_version'])}. Readiness changes never send notifications.")
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))
