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
    "/btc — current state (NO ACTIVE EVENTS / WATCH / EVENT ACTIVE / HISTORY BUILDING / "
    "DETECTOR NOT READY / DATA DEGRADED / DATA STALE) with detector readiness, "
    "the open or most recent detector episode, its trigger or strongest bucket, the latest 5m bucket "
    "and the rolling 1h\n"
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
_EVENT_SIGN = {PRICE_OI_CONTRACTION_DOWN: -1, PRICE_OI_CONTRACTION_UP: +1, POSITION_BUILDUP_COMPRESSION: +1,
               TAKER_FLOW_EXTREME_BUY: +1, TAKER_FLOW_EXTREME_SELL: -1}
_DIRECTION_FIELD = {PRICE_OI_CONTRACTION_DOWN: ("price_structure", "price"),
                    PRICE_OI_CONTRACTION_UP: ("price_structure", "price"),
                    POSITION_BUILDUP_COMPRESSION: ("oi", "oi"),
                    TAKER_FLOW_EXTREME_BUY: ("taker_flow", "taker"), TAKER_FLOW_EXTREME_SELL: ("taker_flow", "taker"),
                    LIQUIDATION_STRESS_LONG: ("price_structure", None),
                    LIQUIDATION_STRESS_SHORT: ("price_structure", None)}
_PARTS = {PRICE_OI_CONTRACTION_DOWN: ("price", "oi", "volume"), PRICE_OI_CONTRACTION_UP: ("price", "oi", "volume"),
          POSITION_BUILDUP_COMPRESSION: ("oi", "range", "volume"),
          TAKER_FLOW_EXTREME_BUY: ("taker", "price", "volume"), TAKER_FLOW_EXTREME_SELL: ("taker", "price", "volume"),
          LIQUIDATION_STRESS_LONG: ("liq_long", "price"), LIQUIDATION_STRESS_SHORT: ("liq_short", "price")}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _hm(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%H:%M")


def _window(first_bucket: str, last_bucket: Optional[str] = None) -> str:
    """Bucket start of `first_bucket` to bucket END of `last_bucket` (HH:MM–HH:MM)."""
    return f"{_hm(_dt(first_bucket))}–{_hm(_dt(last_bucket or first_bucket) + timedelta(minutes=5))}"


def _dur(minutes: float) -> str:
    m = int(max(0, round(minutes)))
    return f"{m}m" if m < 60 else f"{m // 60}h{m % 60:02d}m"


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


def _tail(cfg, m: Mapping[str, Any]) -> str:
    from .context import tail_label
    t = tail_label(cfg, m.get("rank"), m.get("tier"))
    return f" ({t})" if t else ""


def _part(cfg, view: Mapping[str, Any], which: str) -> str:
    from .context import level_label
    if which == "price":
        m = view["price_move_pct"]
        return f"price {_signed_pct(m['value'])}{_tail(cfg, m)}"
    if which == "oi":
        m = view["oi_change_pct"]
        return f"OI {_signed_pct(m['value'])}{_tail(cfg, m)}"
    if which == "range":
        m = view["range_width_pct"]
        return f"range {'n/a' if m['value'] is None else format(m['value'], '.2f') + '%'}{_tail(cfg, m)}"
    if which == "taker":
        m = view["taker_delta_notional_usd"]
        return f"taker delta {_usd(m['value'], signed=True)}{_tail(cfg, m)}"
    if which == "volume":
        m = view["volume_notional_usd"]
        return f"volume {level_label(cfg, m.get('rank'), m.get('tier')) or 'n/a'}"
    if which in ("liq_long", "liq_short"):
        side = which[4:]
        liq = view["liquidations"][side]
        if liq["rule_status"] == "NOT_EVALUABLE":
            return f"{side}-side liquidations not evaluable"
        venues = ", ".join(liq["voting"]) or "no venue"
        return (f"{side}-side liquidations in their top 5% on {venues} "
                f"({len(liq['voting'])} of {len(liq['eligible'])} eligible venues)")
    raise ValueError(which)


def _parts(cfg, view, event_type: Optional[str]) -> str:
    return " · ".join(_part(cfg, view, p) for p in (_PARTS[event_type] if event_type else ("price", "oi", "volume")))


def _venues(ep: Optional[Mapping[str, Any]], now_view: Optional[Mapping[str, Any]]) -> Optional[str]:
    anchor_view = ((ep or {}).get("anchor") or {}).get("view")
    fam, field = _DIRECTION_FIELD[ep["event_type"]] if ep else ("price_structure", None)
    src = anchor_view or now_view
    if src is None:
        return None
    cov = src["coverage"][fam]
    out = f"Venues {cov['available']}/{cov['expected']}"
    if ep is not None and field is not None and anchor_view is not None:
        vd = anchor_view["venue_direction"][field]
        if vd is None:
            out += " · per-venue direction n/a"
        else:
            agree = vd["up"] if _EVENT_SIGN[ep["event_type"]] > 0 else vd["down"]
            out += f" · same direction on {len(agree)}/{vd['contributing']} at the {ANCHOR_WORDS[ep['anchor']['kind']].lower()}"
    return out


def _reached(ep: Mapping[str, Any]) -> str:
    return "triggered" if ep.get("triggered_at") else "armed" if ep.get("armed_at") else "early"


def format_btc(cfg, view: Mapping[str, Any]) -> str:
    """Compact mobile /btc summary built only from factual detector state:
    ACTIVE EVENT (an open detector episode) or LAST EVENT (ended, within the
    presentation retention window), its factual anchor bucket, NOW, the rolling-1h
    background and data freshness. No score, no direction call, no forecast."""
    from .context import level_label
    lines = [f"<b>BTC perp · {_e(view['headline'])}</b>"]
    if view["product_status"] in ("DATA DEGRADED", "DATA STALE"):
        lines.append("Current observability is insufficient; the absence of events cannot be "
                     "claimed right now.")
    if not view.get("projection_available") and view["product_status"] in ("WATCH", "EVENT ACTIVE"):
        lines.append("Episode details are not available right now.")
    ep, last, now_v, c1h = view.get("active_episode"), view.get("last_event"), view.get("now"), view.get("context_1h")
    shown = ep or last
    if ep is not None:
        lines.append(f"{_e(event_label(ep['event_type']))} · {_reached(ep)} · qualifying "
                     f"{_window(ep['opened_bucket'], ep['last_bucket'])} UTC "
                     f"({ep['qualifying_buckets']} bucket{'s' if ep['qualifying_buckets'] != 1 else ''})")
        if view.get("other_active"):
            lines.append("Also open: " + ", ".join(_e(event_label(et)) for et, _st in view["other_active"]))
    elif last is not None:
        ago = (_dt(view["requested_at"]) - _dt(last["terminal_at"])).total_seconds() / 60
        lines.append(f"Last event: {_e(event_label(last['event_type']))} · reached {_reached(last)}")
        lines.append(f"{_window(last['opened_bucket'], last['last_bucket'])} UTC · ended {_dur(ago)} ago "
                     f"({TERMINAL_WORDS.get(last['terminal_reason'], 'ended')})")
    a = (shown or {}).get("anchor")
    if a is not None:
        lines.append(f"{ANCHOR_WORDS[a['kind']]} {_window(a['bucket_ts'])}: {_parts(cfg, a['view'], shown['event_type'])}")
    lines += _readiness_lines(cfg, view.get("readiness"))
    if now_v is not None:
        lines.append(f"Now {_window(now_v['bucket_ts'])}: {_parts(cfg, now_v, (shown or {}).get('event_type'))}")
    if c1h is not None:
        pr = c1h.get("percentiles") or {}
        rng, vol = pr.get("range_width_pct_median") or {}, pr.get("volume_notional_usd_sum") or {}
        lines.append(f"1h: range {level_label(cfg, rng.get('rank'), rng.get('tier')) or 'n/a (history building)'}"
                     f" · volume {level_label(cfg, vol.get('rank'), vol.get('tier')) or 'n/a (history building)'}"
                     f" · price {_signed_pct(c1h.get('price_move_pct_median'))}")
    elif view["product_status"] != "DATA STALE" and view.get("as_of_bucket"):
        lines.append("1h: n/a (incomplete last hour)")
    tail = [t for t in [_venues(shown, now_v)] if t]
    ref = (now_v or {}).get("reference_price")
    if ref is not None:
        tail.append(f"{ref:,.1f}")
    tail.append(f"data through {_hm(_dt(view['data_through']))} UTC" if view.get("data_through")
                else "no evaluation yet")
    lines.append(" · ".join(tail))
    lines.append("\n" + DISCLAIMER)
    return assert_descriptive("\n".join(lines))


def _full_metrics(cfg, v: Optional[Mapping[str, Any]]) -> list:
    if v is None:
        return ["  n/a"]
    out = []
    for key, name in (("price_move_pct", "price move"), ("oi_change_pct", "OI change"),
                      ("range_width_pct", "range width"), ("volume_notional_usd", "volume"),
                      ("taker_delta_notional_usd", "taker delta")):
        m = v[key]
        if key.endswith("usd"):
            val = _usd(m["value"], signed=key == "taker_delta_notional_usd")
        elif key == "range_width_pct":
            val = "n/a" if m["value"] is None else f"{m['value']:.2f}%"
        else:
            val = _signed_pct(m["value"])
        rank = "n/a" if m.get("rank") is None else f"{m['rank'] * 100:.1f} pct of 30d ({m.get('tier')})"
        out.append(f"  {name}: {val} · {rank}")
    for f, label in (("price", "price"), ("oi", "OI"), ("taker", "taker delta")):
        vd = v["venue_direction"][f]
        if vd is not None:
            out.append(f"  {label} by venue: up {','.join(vd['up']) or '—'} · down {','.join(vd['down']) or '—'}"
                       f" · flat {','.join(vd['flat']) or '—'}")
    for side in ("long", "short"):
        liq = v["liquidations"][side]
        per = ", ".join(f"{ex} {_usd(x)}" for ex, x in liq["per_venue"].items() if x is not None) or "none observed"
        out.append(f"  {side}-side liquidations by venue: {per} · top-5% votes "
                   f"{','.join(liq['voting']) or '—'} of eligible {','.join(liq['eligible']) or '—'}")
    return out


def format_context_details(cfg, episode: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    lines = [f"<b>{_e(episode['episode_id'])} — {_e(event_label(episode['event_type']))}</b>",
             _e(EVENT_DESCRIPTIONS[episode["event_type"]]),
             f"Detector state {STATE_LABELS[episode['state']]} · reached {_reached(episode)} · qualifying "
             f"{_window(episode['opened_bucket'], episode['last_bucket'])} UTC ({episode['qualifying_buckets']} buckets)"]
    if episode.get("terminal_at"):
        lines.append(f"Ended {ts(_dt(episode['terminal_at']))}: "
                     f"{TERMINAL_WORDS.get(episode['terminal_reason'], 'ended')}")
    a = episode.get("anchor")
    if a is not None:
        lines.append(f"\n<b>{ANCHOR_WORDS[a['kind']]}</b> {_window(a['bucket_ts'])} UTC")
        lines += _full_metrics(cfg, a["view"])
    lines.append(f"\n<b>Now</b> {_window(state['now']['bucket_ts']) + ' UTC' if state.get('now') else ''}")
    lines += _full_metrics(cfg, state.get("now"))
    c1h = state.get("context_1h")
    lines.append("\n<b>Rolling 1h</b> (last 12 closed 5m buckets)")
    if c1h is None:
        lines.append("  n/a")
    else:
        for key, name in (("range_width_pct_median", "range"), ("price_move_pct_median", "price move"),
                          ("volume_notional_usd_sum", "volume")):
            v = c1h.get(key)
            p = (c1h.get("percentiles") or {}).get(key) or {}
            val = _usd(v) if key.endswith("sum") else _signed_pct(v)
            rank = "n/a" if p.get("rank") is None else f"{p['rank'] * 100:.1f} pct of rolling-1h 30d ({p.get('tier')})"
            lines.append(f"  {name}: {val} · {rank}")
        lines.append(f"  venues: {', '.join(c1h.get('venues') or []) or '—'}")
    lines.append(f"\nEpisodization {_e(episode['episodization_version'])} ({episode['episodization_digest'][:12]}): "
                 f"detector episode boundaries · context {_e(state.get('context_version'))}")
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


def _readiness_lines(cfg, rd: Optional[Mapping[str, Any]]) -> list:
    if not rd:
        return []
    groups = rd["groups"]
    if all(g["status"] == "READY" for g in groups):
        return ["Detector readiness: all families ready"]
    return ["Detector readiness"] + [f"{g['label']}: {_group_text(cfg, g, rd['maturity_days'])}" for g in groups]


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
