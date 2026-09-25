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
    "/btc — current state (NO ACTIVE EVENTS / WATCH / EVENT ACTIVE / DATA DEGRADED / DATA STALE)\n"
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
