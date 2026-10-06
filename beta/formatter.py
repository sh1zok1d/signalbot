"""Beta V0.2 user-facing wording — descriptive only, HTML for Telegram.

Every user-facing string comes from ``beta.i18n``. The formatter takes ``lang``
and does not assemble wording on its own. Detection, readiness semantics and
push policy are unchanged; this module only renders.
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from .config import (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, POSITION_BUILDUP_COMPRESSION,
                     PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY,
                     TAKER_FLOW_EXTREME_SELL)
from .i18n import (MINUS, ForbiddenWordingError, assert_descriptive, fmt_clock, fmt_funding,
                   fmt_kyiv_date_hm, fmt_kyiv_hm, fmt_plain_pct, fmt_price, fmt_ratio, fmt_signed_pct,
                   fmt_usd, na, t)

__all__ = ["ForbiddenWordingError", "assert_descriptive", "EVENT_LABELS", "EVENT_DESCRIPTIONS",
           "CLOSED_BETA_TEXT", "PRIVACY_NOTICE", "HELP_TEXT", "DISCLAIMER"]

_EVENT_KEYS = {
    PRICE_OI_CONTRACTION_DOWN: "evt_down",
    PRICE_OI_CONTRACTION_UP: "evt_up",
    POSITION_BUILDUP_COMPRESSION: "evt_build",
    TAKER_FLOW_EXTREME_BUY: "evt_buy",
    TAKER_FLOW_EXTREME_SELL: "evt_sell",
    LIQUIDATION_STRESS_LONG: "evt_liq_long",
    LIQUIDATION_STRESS_SHORT: "evt_liq_short",
}
_DESC_KEYS = {
    PRICE_OI_CONTRACTION_DOWN: "desc_down",
    PRICE_OI_CONTRACTION_UP: "desc_up",
    POSITION_BUILDUP_COMPRESSION: "desc_build",
    TAKER_FLOW_EXTREME_BUY: "desc_buy",
    TAKER_FLOW_EXTREME_SELL: "desc_sell",
    LIQUIDATION_STRESS_LONG: "desc_liq_long",
    LIQUIDATION_STRESS_SHORT: "desc_liq_short",
}
_PLAIN_KEYS = {
    PRICE_OI_CONTRACTION_DOWN: "plain_down",
    PRICE_OI_CONTRACTION_UP: "plain_up",
    POSITION_BUILDUP_COMPRESSION: "plain_build",
    TAKER_FLOW_EXTREME_BUY: "plain_buy",
    TAKER_FLOW_EXTREME_SELL: "plain_sell",
    LIQUIDATION_STRESS_LONG: "plain_liq_long",
    LIQUIDATION_STRESS_SHORT: "plain_liq_short",
}
_STATE_KEYS = {"EARLY": "state_early", "ARMED": "state_armed", "TRIGGERED": "state_triggered",
               "ENDED": "state_ended", "EXPIRED": "state_expired"}
_PRICE_OI = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP)
_TAKER = (TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)
_KNOWN_HEADLINES = {"DATA STALE", "DATA DEGRADED", "DETECTOR NOT READY", "HISTORY BUILDING",
                    "EVENT ACTIVE", "WATCH", "NO ACTIVE EVENTS"}
_DATA_END = {"DETECTION_GAP": "end_gap", "NOT_EVALUABLE": "end_not_evaluable",
             "DETECTOR_VERSION_CHANGED": "end_version"}
_READY_KEYS = {"READY": "ready_word", "HISTORY_BUILDING": "ready_building",
               "DATA_UNAVAILABLE": "ready_unavailable", "DEGRADED": "ready_degraded",
               "DISABLED": "ready_disabled"}
_HISTORY_NAMES = {"c:price_move_pct_median": "hist_price", "c:oi_change_pct_median": "hist_oi",
                  "c:range_width_pct_median": "hist_range", "c:volume_notional_usd_sum": "hist_volume",
                  "c:taker_delta_notional_usd_sum": "hist_taker",
                  "x:*:long_liquidation_notional": "hist_liq_long",
                  "x:*:short_liquidation_notional": "hist_liq_short"}
_FAMILY_WORDS = {"price_structure": "fam_price", "oi": "fam_oi", "volume": "fam_volume",
                 "taker_flow": "fam_taker"}
_REASON_EXACT = {"NOT_MATERIALIZED": "reason_not_mat", "EVALUATION_NOT_FRESH": "reason_late",
                 "STALE_BARRIER": "reason_stale", "RULE_DISABLED": "reason_off",
                 "NOT_EVALUATED": "reason_not_eval"}


def event_label(event_type: str, lang: str = "en") -> str:
    return t(lang, _EVENT_KEYS[event_type])


def event_description(event_type: str, lang: str = "en") -> str:
    return t(lang, _DESC_KEYS[event_type])


def plain_name(event_type: str, lang: str = "en") -> str:
    return t(lang, _PLAIN_KEYS[event_type])


def state_label(state: str, lang: str = "en") -> str:
    return t(lang, _STATE_KEYS[state])


EVENT_LABELS = {et: event_label(et, "en") for et in _EVENT_KEYS}
EVENT_DESCRIPTIONS = {et: event_description(et, "en") for et in _DESC_KEYS}
STATE_LABELS = {s: state_label(s, "en") for s in _STATE_KEYS}
DISCLAIMER = t("en", "disclaimer")
CLOSED_BETA_TEXT = t("en", "closed_beta")
PRIVACY_NOTICE = assert_descriptive(t("en", "privacy"), "en")
HELP_TEXT = assert_descriptive(t("en", "help") + "\n\n" + t("en", "disclaimer"), "en")


def _e(s: Any) -> str:
    return html.escape(str(s), quote=False)


def _ok(text: str, lang: str) -> str:
    return assert_descriptive(text, lang)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _when(dt: Optional[datetime], lang: str) -> str:
    if dt is None:
        return "—"
    return fmt_kyiv_date_hm(dt, lang)


def _dur(minutes: float, lang: str) -> str:
    m = int(max(0, round(minutes)))
    if m < 60:
        return t(lang, "dur_m", n=m)
    if m % 60 == 0:
        return t(lang, "dur_h", n=m // 60)
    return t(lang, "dur_hm", h=m // 60, m=m % 60)


def _level_word(cfg, metric: Optional[Mapping[str, Any]], lang: str, *, omit_normal: bool) -> Optional[str]:
    from .context import level_label
    if not metric:
        return None
    label = level_label(cfg, metric.get("rank"), metric.get("tier"))
    if label is None:
        return None
    if omit_normal and label == "normal":
        return None
    return t(lang, "level_" + label)


def _signed_arrow(metric: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not metric or metric.get("value") is None:
        return None
    v = metric["value"]
    if v == 0:
        return "·"
    return "↑" if v > 0 else "↓"


def _screen_state(view: Mapping[str, Any], lang: str) -> str:
    h = view.get("headline") or ""
    if h not in _KNOWN_HEADLINES:
        return h
    if h in ("DATA STALE", "DATA DEGRADED", "DETECTOR NOT READY"):
        return t(lang, "title_incomplete")
    if h == "HISTORY BUILDING":
        return t(lang, "title_history")
    if view.get("active_episode") is not None or h in ("EVENT ACTIVE", "WATCH"):
        return t(lang, "title_unusual")
    last = view.get("last_event")
    if last is not None:
        return t(lang, "title_calmed" if last.get("terminal_reason") == "CONDITION_FAILED" else "title_ended")
    return t(lang, "title_calm")


def _title(view: Mapping[str, Any], lang: str) -> str:
    state = _screen_state(view, lang)
    price = (view.get("now") or {}).get("reference_price")
    rest = f"{fmt_price(price, lang)} · {state}" if price is not None else f"· {state}"
    return f"<b>{_e(t(lang, 'screen_title', rest=rest))}</b>"


def _reading_line(cfg, event_type: str, view: Mapping[str, Any], lang: str) -> str:
    if event_type in _PRICE_OI:
        parts = []
        price, oi = _signed_arrow(view.get("price_move_pct")), _signed_arrow(view.get("oi_change_pct"))
        vol = _level_word(cfg, view.get("volume_notional_usd"), lang, omit_normal=True)
        if price and price != "·":
            parts.append(t(lang, "part_price", arrow=price))
        if oi and oi != "·":
            parts.append(t(lang, "part_oi", arrow=oi))
        if vol:
            parts.append(t(lang, "part_vol", level=vol))
        return " · ".join(parts) or t(lang, "na_reading")
    if event_type == POSITION_BUILDUP_COMPRESSION:
        parts = []
        oi = _signed_arrow(view.get("oi_change_pct"))
        vol = _level_word(cfg, view.get("volume_notional_usd"), lang, omit_normal=True)
        if oi and oi != "·":
            parts.append(t(lang, "part_oi", arrow=oi))
        if vol:
            parts.append(t(lang, "part_vol", level=vol))
        return " · ".join(parts) or t(lang, "na_reading")
    if event_type in _TAKER:
        parts = []
        taker = _signed_arrow(view.get("taker_delta_notional_usd"))
        price = _signed_arrow(view.get("price_move_pct"))
        if taker and taker != "·":
            parts.append(t(lang, "part_taker", arrow=taker))
        if price and price != "·":
            parts.append(t(lang, "part_price", arrow=price))
        return " · ".join(parts) or t(lang, "na_reading")
    side = "long" if event_type == LIQUIDATION_STRESS_LONG else "short"
    liq = (view.get("liquidations") or {}).get(side) or {}
    if liq.get("rule_status") == "NOT_EVALUABLE":
        return t(lang, "liq_not_evaluable", Side=t(lang, "liq_" + side + "_name"), side=t(lang, "side_" + side))
    return t(lang, "liq_count", Side=t(lang, "liq_" + side + "_name"), side=t(lang, "side_" + side),
             votes=len(liq.get("voting") or []), eligible=len(liq.get("eligible") or []))


def _why_line(cfg, event_type: str, view: Mapping[str, Any], lang: str) -> Optional[str]:
    if event_type == POSITION_BUILDUP_COMPRESSION:
        word = _level_word(cfg, view.get("oi_change_pct"), lang, omit_normal=True)
        if word:
            return t(lang, "oi_level", level=word)
        v = (view.get("oi_change_pct") or {}).get("value")
        if v is None or v == 0:
            return None
        return t(lang, "oi_rose" if v > 0 else "oi_fell")
    if event_type not in _PRICE_OI:
        return None
    price = (view.get("price_move_pct") or {}).get("value")
    oi = (view.get("oi_change_pct") or {}).get("value")
    if price is None or oi is None or price == 0 or oi == 0:
        return None
    up, oi_up = price > 0, oi > 0
    side = "short" if up else "long"
    liq = ((view.get("liquidations") or {}).get(side) or {})
    need = cfg.rule("LIQUIDATION_STRESS")["min_eligible_venues"]
    votes, eligible = liq.get("voting") or [], liq.get("eligible") or []
    if not oi_up and liq.get("rule_status") not in (None, "NOT_EVALUABLE") and len(votes) >= need and eligible:
        return t(lang, "move_liq", move=t(lang, "move_rise" if up else "move_drop"), side=side if lang == "en" else t(lang, "side_" + side))
    key = ("oi_rose_rise" if oi_up else "oi_fell_rise") if up else ("oi_rose_drop" if oi_up else "oi_fell_drop")
    return t(lang, key)


def _hour_bits(lang: str, *, price, range_ratio, volume_ratio) -> str:
    parts = []
    if price is not None:
        parts.append(fmt_signed_pct(price, lang, nd=1))
    parts.append(t(lang, "h1_vol", ratio=na(lang) if volume_ratio is None else fmt_ratio(volume_ratio, lang)))
    parts.append(t(lang, "h1_range", ratio=na(lang) if range_ratio is None else fmt_ratio(range_ratio, lang)))
    return t(lang, "h1_prefix", body=" · ".join(parts))


# Presentation only. The horizon block already stores baseline_days per metric.
# 20 is the frozen maturity count from the horizon contract; this does not recompute it.
_BASELINE_READY_DAYS = 20
_H1_RANGE_DAYS = "range_width_pct_median"
_H1_VOLUME_DAYS = "volume_notional_usd_sum"
_H24_RANGE_DAYS = "range_width_pct"
_H24_VOLUME_DAYS = "volume_notional_usd"


def _baseline_day_count(block: Mapping[str, Any], metric: str) -> Optional[int]:
    days = block.get("baseline_days")
    if not isinstance(days, Mapping):
        return None
    value = days.get(metric)
    if value is None:
        return None
    return int(value)


def _day_type_tod(view: Mapping[str, Any], metric: str) -> bool:
    """True when this 1h baseline metric follows the C1 same-day-type rule (BETA_HORIZON_TOD_V3):
    its day count is same-type days and it is ready at _DAY_TYPE_MIN_DAYS, not 20. Payloads
    stored under an older horizon version keep the old countdown."""
    from .horizons import HORIZON_VERSION, _DAY_TYPE_TOD_METRICS
    return (view.get("horizons") or {}).get("version") == HORIZON_VERSION and metric in _DAY_TYPE_TOD_METRICS


def _ready_days(day_type: bool) -> int:
    from .horizons import _DAY_TYPE_MIN_DAYS
    return _DAY_TYPE_MIN_DAYS if day_type else _BASELINE_READY_DAYS


def _immature_baseline(block: Mapping[str, Any], metric: str, day_type: bool = False) -> bool:
    days = _baseline_day_count(block, metric)
    return days is not None and days < _ready_days(day_type)


def _days_remaining(block: Mapping[str, Any], metric: str, day_type: bool = False) -> Optional[int]:
    """Calendar days until the baseline is ready, at least 1. None once it is mature or unknown.
    C1 (day_type): the missing same-type dates are counted forward on the calendar from the UTC
    date of the window start (a weekend window needs weekend dates, a weekday one weekdays)."""
    days = _baseline_day_count(block, metric)
    need = _ready_days(day_type)
    if days is None or days >= need:
        return None
    if not day_type:
        return max(1, need - days)
    from .day_type import date_type, utc_date
    start = block.get("window_start")
    if not start:
        return None
    d0 = utc_date(_dt(start))
    own, missing, n = date_type(d0), need - days, 0
    while missing > 0:                         # each same-type date becomes a prior day the next day
        if date_type(d0 + timedelta(days=n)) == own:
            missing -= 1
        n += 1
    return max(1, n)


def _main_ratio_token(block: Mapping[str, Any], *, value_key: str, ratio_key: str,
                      days_key: str, lang: str, day_type: bool = False) -> Optional[str]:
    """Main-line ratio. An immature baseline omits the field. A missing value is omitted.
    A mature baseline with no ratio prints n/a."""
    ratio = block.get(ratio_key)
    if ratio is not None:
        return fmt_ratio(ratio, lang)
    if block.get(value_key) is None or _immature_baseline(block, days_key, day_type):
        return None
    return na(lang)


_VENUE_NAMES = {"binance": "Binance", "bybit": "Bybit", "okx": "OKX"}


def venue_name(ex: str) -> str:
    return _VENUE_NAMES.get(ex, ex)


def _hour_line(view: Mapping[str, Any], lang: str) -> str:
    horizons = view.get("horizons")
    if horizons is None:
        c1h = view.get("context_1h")
        if not c1h:
            return t(lang, "h1_incomplete")
        return _hour_bits(lang, price=c1h.get("price_move_pct_median"), range_ratio=None, volume_ratio=None)
    block = horizons.get("1h")
    if not block or not block.get("complete"):
        return t(lang, "h1_incomplete")
    parts = []
    if block.get("price_move_pct") is not None:
        parts.append(fmt_signed_pct(block["price_move_pct"], lang, nd=1))
    vol = _main_ratio_token(block, value_key="volume_notional_usd", ratio_key="volume_ratio",
                            days_key=_H1_VOLUME_DAYS, lang=lang,
                            day_type=_day_type_tod(view, _H1_VOLUME_DAYS))
    if vol is not None:
        parts.append(t(lang, "h1_vol", ratio=vol))
    rng = _main_ratio_token(block, value_key="range_width_pct", ratio_key="range_ratio",
                            days_key=_H1_RANGE_DAYS, lang=lang,
                            day_type=_day_type_tod(view, _H1_RANGE_DAYS))
    if rng is not None:
        parts.append(t(lang, "h1_range", ratio=rng))
    oi = block.get("oi_change_pct")
    if oi is not None:
        parts.append(t(lang, "h_oi", pct=fmt_signed_pct(oi, lang, nd=1)))
    if not parts:
        return t(lang, "h1_incomplete")
    return t(lang, "h1_prefix", body=" · ".join(parts))


def _day_line(view: Mapping[str, Any], lang: str) -> Optional[str]:
    """24h main line. Absent when the view has no horizons block at all."""
    horizons = view.get("horizons")
    if horizons is None:
        return None
    block = horizons.get("24h")
    if not block:
        return t(lang, "h24_incomplete")
    parts = []
    if block.get("price_complete") and block.get("price_move_pct") is not None:
        parts.append(fmt_signed_pct(block["price_move_pct"], lang, nd=1))
    if block.get("volume_complete"):
        ratio = _main_ratio_token(block, value_key="volume_notional_usd", ratio_key="volume_ratio",
                                  days_key=_H24_VOLUME_DAYS, lang=lang)
        if ratio is not None:
            parts.append(t(lang, "h1_vol", ratio=ratio))
    elif block.get("volume_partial"):
        parts.append(t(lang, "h_vol_partial"))
    oi = block.get("oi_change_pct")
    if oi is not None:
        parts.append(t(lang, "h_oi", pct=fmt_signed_pct(oi, lang, nd=1)))
    if not parts:
        return t(lang, "h24_incomplete")
    return t(lang, "h24_prefix", body=" · ".join(parts))


def _retention_phrase(cfg, lang: str) -> str:
    m = int(cfg.section("context")["last_event_retention_min"])
    return _dur(m, lang)


def _run_start(cfg, ep: Mapping[str, Any]) -> Optional[datetime]:
    """First qualifying bucket of the run. The episode opens when the streak
    reaches its entry streak, so the run began entry_streak - 1 buckets earlier."""
    if not ep.get("opened_bucket"):
        return None
    from .detector import lifecycle
    return _dt(ep["opened_bucket"]) - (lifecycle(cfg, ep["event_type"]).entry_streak - 1) * timedelta(minutes=5)


def _run_window(cfg, ep: Mapping[str, Any]) -> Optional[str]:
    """Kyiv window of the whole qualifying run, to the end of the last qualifying
    bucket. None for a record without bucket bounds."""
    start = _run_start(cfg, ep)
    if start is None or not ep.get("last_bucket"):
        return None
    return _window_kyiv(start.isoformat(), ep["last_bucket"])


def _ago_phrase(cfg, view: Mapping[str, Any], ep: Mapping[str, Any], lang: str) -> str:
    """One time reference: when the condition held, when it ended, how long ago."""
    end = _dt(ep["terminal_at"])
    minutes = (_dt(view["requested_at"]) - end).total_seconds() / 60
    m = int(max(0, round(minutes)))
    name = plain_name(ep["event_type"], lang)
    window = _run_window(cfg, ep)
    if window is None:
        return t(lang, "ago_just", name=name) if m == 0 else t(lang, "ago", dur=_dur(m, lang), name=name)
    if m == 0:
        return t(lang, "ended_run_just", window=window, name=name, hm=fmt_kyiv_hm(end))
    return t(lang, "ended_run", window=window, name=name, hm=fmt_kyiv_hm(end), dur=_dur(m, lang))


def _core_gap_line(rd: Optional[Mapping[str, Any]], lang: str) -> Optional[str]:
    if not rd:
        return None
    core = next(g for g in rd["groups"] if g["group"] == "PRICE_OI")
    if core["status"] == "READY":
        return None
    if core["status"] == "HISTORY_BUILDING":
        p = core.get("progress") or {}
        if p.get("span_days") is not None:
            return t(lang, "gap_span", span=f"{p['span_days']:.1f}".replace(".", "," if lang == "ru" else "."),
                     need=f"{rd['maturity_days']:.0f}")
        return t(lang, "gap_maturing")
    if core["status"] == "DATA_UNAVAILABLE":
        return t(lang, "gap_unavailable")
    if core["status"] == "DISABLED":
        return t(lang, "gap_off")
    return None


def _noticed_lines(cfg, view, ep, lang: str, *, active: bool) -> list:
    lines = []
    if not active:
        lines.append(_ago_phrase(cfg, view, ep, lang))
    anchor = (ep.get("anchor") or {}).get("view")
    if anchor is None:
        lines.append(t(lang, "measurements_missing"))
        return lines
    reading = _reading_line(cfg, ep["event_type"], anchor, lang)
    lines.append(t(lang, "bucket_reading", window=_window_kyiv(anchor["bucket_ts"]), reading=reading))
    why = _why_line(cfg, ep["event_type"], anchor, lang)
    if why:
        lines.append(why)
    return lines


def _last_known_lines(ep, last, lang: str) -> list:
    if ep is not None:
        at = _dt(ep["last_bucket"]) + timedelta(minutes=5)
        known = t(lang, "last_known", hm=fmt_kyiv_hm(at), name=plain_name(ep["event_type"], lang))
    elif last is not None:
        known = t(lang, "last_known_ended", hm=fmt_kyiv_hm(_dt(last["terminal_at"])),
                  name=plain_name(last["event_type"], lang))
    else:
        return []
    return [known, t(lang, "state_unavailable")]


def _after_status(view, ep, last, lang: str) -> Optional[str]:
    if ep is not None:
        return t(lang, "still_active")
    if last is None:
        return None
    reason = last.get("terminal_reason")
    if reason in _DATA_END:
        return t(lang, _DATA_END[reason])
    if reason == "MAX_DURATION":
        return t(lang, "ended_cap")
    if reason == "CONDITION_FAILED":
        return None          # the title says "calmed" and the event line says when it ended
    return t(lang, "event_ended_line")


def _clock_of(view) -> Optional[datetime]:
    if not view.get("data_through"):
        return None
    return _dt(view["data_through"])


def format_btc(cfg, view: Mapping[str, Any], lang: str = "en") -> str:
    """Compact /btc. Presentation only."""
    lines = [_title(view, lang)]
    status = view["product_status"]
    market_ok = status not in ("DATA DEGRADED", "DATA STALE")
    if not market_ok:
        lines.append(t(lang, "insufficient"))
    if not view.get("projection_available") and status in ("WATCH", "EVENT ACTIVE"):
        lines.append(t(lang, "projection_missing"))
    ep, last = view.get("active_episode"), view.get("last_event")
    shown = ep or last
    state = _screen_state(view, lang)
    if shown is not None and not market_ok:
        lines.extend(_last_known_lines(ep, last, lang))
    elif shown is not None:
        lines.extend(_noticed_lines(cfg, view, shown, lang, active=ep is not None))
        others = view.get("other_active") or []
        if ep is not None and others:
            lines.append(t(lang, "also_open", names=", ".join(plain_name(et, lang) for et, _st in others)))
    elif market_ok and state == t(lang, "title_calm"):
        lines.append(t(lang, "no_unusual"))
    if market_ok and state in (t(lang, "title_history"), t(lang, "title_incomplete"), t(lang, "title_unusual")):
        gap = _core_gap_line(view.get("readiness"), lang)
        if gap:
            lines.append(gap)
        if state == t(lang, "title_history") and shown is None:
            lines.append(t(lang, "not_evaluated_yet"))
    if market_ok:
        lines.append(_hour_line(view, lang))
        day = _day_line(view, lang)
        if day:
            lines.append(day)
        d7 = _d7_main_line(view, lang)
        if d7:
            lines.append(d7)
        from .decision_format import btc_lines
        lines.extend(btc_lines(view, lang))
    clock = _clock_of(view)
    if market_ok and state == t(lang, "title_calm") and shown is None:
        status_bit = t(lang, "notable_none", span=_retention_phrase(cfg, lang))
    elif shown is not None and market_ok:
        status_bit = _after_status(view, ep, last, lang)
    else:
        status_bit = None
    if clock is None:
        lines.append(t(lang, "no_evaluation_line"))
    elif status_bit:
        lines.append(t(lang, "data_line", status=status_bit, clock=fmt_clock(clock, lang)))
    else:
        lines.append(t(lang, "data_only", clock=fmt_clock(clock, lang)))
    # No disclaimer here: it lives in /start and /terms only (BETA_COPY_CONTRACT_V1 §4, §5 rule 8;
    # owner decision 2026-10-03). The no-trading-advice wording stays in onboarding and /terms.
    return _ok("\n".join(lines), lang)


def format_catchup(cfg, view: Mapping[str, Any], lang: str = "en", *, push_enabled: bool = True,
                   first_brief: bool = False) -> str:
    """/catchup and the morning briefing: one render path over the shared view
    (BETA_COPY_CONTRACT_V1 §1.1). Window price path, the unusual hours of the window
    (the push gate's own qualification, read from the market side), the 1h / 4h state
    and the 24h context line, then the data time. Descriptive only; never what comes
    next. `push_enabled` is the recipient's preference: a user with push off sees the
    same hours and no note about withheld messages (decision §3.1b.4)."""
    market = view.get("market") or {}
    hours = int(market.get("window_hours") or 8)
    window = market.get("window") or {}
    brief = view.get("kind") == "brief"
    span = _window_span(window, hours, lang)
    if brief:
        title = t(lang, "brief_title", span=span)
    elif window.get("window_start") and window.get("window_end"):
        title = t(lang, "catchup_title", hours=hours, span=span)
    else:                                       # no window: never «BTC за 8 ч · 8 ч»
        title = t(lang, "catchup_title_nospan", hours=hours)
    lines = [f"<b>{_e(title)}</b>"]
    degraded = view.get("product_status") in ("DATA STALE", "DATA DEGRADED") or not market.get("complete")
    if degraded:
        lines.append(t(lang, "insufficient"))
    else:
        lines.append(_price_span_line(window, lang))
        lines.extend(_unusual_hours_lines(cfg, market, lang, push_enabled=push_enabled))
    lines.append("")
    lines.append(f"<b>{t(lang, 'now_head')}</b>")
    for h in ("1h", "4h"):
        res = (market.get("interpretation") or {}).get(h)
        body = t(lang, "data_incomplete") if degraded or res is None else _state_body(
            cfg, res, (market.get("values") or {}).get(h) or {}, h, lang)
        lines.append(t(lang, "now_line", h=t(lang, "hz_" + h), body=body))
        if not degraded and res is not None:
            line = _analog_line(view, res, h, lang)
            if line:
                lines.append(line)
    lines.append(_line_24h(view, lang))
    from .decision_format import brief_lines
    lines.extend(brief_lines(view, lang))
    clock = _clock_of(view)
    lines.append("")
    lines.append(t(lang, "data_at", clock=fmt_clock(clock, lang)) if clock else t(lang, "no_evaluation_line"))
    if brief and first_brief:
        lines.append(t(lang, "brief_off_hint"))
    return _ok("\n".join(lines), lang)


def _analog_line(view: Mapping[str, Any], res: Mapping[str, Any], h: str, lang: str) -> Optional[str]:
    """«После похожих» under a 1h / 4h state that says something (PRODUCT_DECISION_V2 §2.3)."""
    from .decision_format import _since_year, analog_line
    from .interpretation import COMPRESSION, FACTUAL, INTERPRETED
    if res.get("kind") not in (INTERPRETED, FACTUAL, COMPRESSION):
        return None
    block = view.get("decision") or {}
    card = (block.get("analogues") or {}).get(h)
    return analog_line(card, lang, since_year=_since_year(block)) if card else None


def _research_line(res: Mapping[str, Any], h: str, lang: str) -> Optional[str]:
    """«Проверено: …» from the research record for a state that says something (research ↔ bot)."""
    from .interpretation import COMPRESSION, FACTUAL, INTERPRETED
    if res.get("kind") not in (INTERPRETED, FACTUAL, COMPRESSION):
        return None
    try:
        from .research_link import context_line, label_contexts
        line = context_line(label_contexts(h, res.get("key")), lang)
    except Exception:  # noqa: BLE001 - the registry is optional context, never a failure
        return None
    return ("↳ " + line) if line else None


def _window_span(window: Mapping[str, Any], hours: int, lang: str) -> str:
    start, end = window.get("window_start"), window.get("window_end")
    if not start or not end:
        return t(lang, "span_hours", hours=hours)
    return t(lang, "window_kyiv", start=fmt_kyiv_hm(_dt(start)), end=fmt_kyiv_hm(_dt(end)))


def _price_span_line(window: Mapping[str, Any], lang: str) -> str:
    if not window.get("price_complete") or window.get("price_move_pct") is None \
            or window.get("open") is None or window.get("close") is None:
        return t(lang, "price_span_incomplete")
    body = t(lang, "price_span", open=fmt_price(window["open"], lang), close=fmt_price(window["close"], lang),
             pct=fmt_signed_pct(window["price_move_pct"], lang))
    if window.get("low") is not None and window.get("high") is not None:
        body += t(lang, "price_span_minmax", low=fmt_price(window["low"], lang), high=fmt_price(window["high"], lang))
    return body


_CATCHUP_MAX_LINES = 15
_CATCHUP_TAIL_LINES = 6          # Сейчас, 1ч, 4ч, 24ч, Данные, and the first-brief hint at most


def _unusual_hours_lines(cfg, market: Mapping[str, Any], lang: str, *, push_enabled: bool) -> list:
    hours = market.get("unusual_hours") or []
    if not hours:
        days = market.get("history_days")
        if market.get("ranks_immature") and days is not None:
            return [t(lang, "unusual_immature", days=int(days))]
        return [t(lang, "no_unusual_hours")]
    out, budget = [], _CATCHUP_MAX_LINES - 2 - _CATCHUP_TAIL_LINES
    for hour in hours[:3]:
        block = _hour_block(cfg, hour, lang, push_enabled=push_enabled)
        if out and len(out) + len(block) > budget:
            break
        out.extend(block)
    return out


def _hour_block(cfg, hour: Mapping[str, Any], lang: str, *, push_enabled: bool) -> list:
    gate = hour.get("gate") or {}
    values = gate.get("values") or {}
    label = _gate_state_text(gate, lang)
    span = t(lang, "window_kyiv", start=fmt_kyiv_hm(_dt(gate["window_start"])),
             end=fmt_kyiv_hm(_dt(gate["window_end"]))) if gate.get("window_start") else ""
    lines = [t(lang, "unusual_head", span=span, label=label), _facts_line(values, lang)]
    liq = _liq_votes_line(gate, lang)
    if liq:
        lines.append(liq)
    unsigned = _unsigned_line(gate, lang)
    if unsigned:
        lines.append(unsigned)
    if push_enabled:
        note = _withheld_note(cfg, hour.get("suppression_reason"), lang)
        if note:
            lines.append(note)
    return lines


def _withheld_note(cfg, reason: Optional[str], lang: str) -> Optional[str]:
    if reason == "QUIET_HOURS":
        s, e = cfg.quiet_hours_kyiv
        return t(lang, "note_quiet", s=s, e=e)
    if reason == "DAILY_CAP":
        return t(lang, "note_cap", n=int(cfg["max_new_pushes_per_utc_day"]))
    if reason in ("GLOBAL_COOLDOWN", "SAME_EVENT_COOLDOWN"):
        return t(lang, "note_cooldown")
    return None


def _facts_line(values: Mapping[str, Any], lang: str) -> str:
    return t(lang, "hour_facts", pct=_pct_or_na(values.get("price_move_pct"), lang, nd=1),
             oi=_pct_or_na(values.get("oi_change_pct"), lang, nd=1), delta=_usd_or_na(values.get("taker_delta_notional_usd"), lang))


def _pct_or_na(v, lang: str, nd: int = 2) -> str:
    return na(lang) if v is None else fmt_signed_pct(float(v), lang, nd=nd)


def _usd_or_na(v, lang: str) -> str:
    return na(lang) if v is None else fmt_usd(float(v), lang, signed=True)


def _taker_against_price(res: Mapping[str, Any]) -> bool:
    """True only when taker flow points AGAINST the price move: price up with taker
    down, or price down with taker up (BETA_COPY_CONTRACT_V1 §2). Aligned, flat,
    missing or immature taker flow is never called "against"."""
    inputs = res.get("inputs") or {}
    price, taker = inputs.get("price"), inputs.get("taker")
    return (price == "up" and taker == "down") or (price == "down" and taker == "up")


def _gate_state_text(gate: Mapping[str, Any], lang: str) -> str:
    from .interpretation import LABEL_KEYS
    res = gate.get("interpretation") or {}
    key = res.get("key") or "missing"
    return t(lang, LABEL_KEYS.get(key, "interp_missing"))


def _liq_votes_line(gate: Mapping[str, Any], lang: str) -> Optional[str]:
    liq = gate.get("liquidation")
    if not liq or not liq.get("voting"):
        return None            # no votes of the confirming episode at this bucket: no evidence line
    n = len(gate.get("values", {}).get("ranks", {})) and 3
    return t(lang, "liq_votes_line", side=t(lang, "side_" + liq["side"]), k=len(liq.get("voting") or ()),
             n=max(n, len(liq.get("eligible") or ()), 1))


def _unsigned_line(gate: Mapping[str, Any], lang: str) -> Optional[str]:
    passed = gate.get("passed") or {}
    if passed.get("range") and passed.get("volume"):
        return t(lang, "unsigned_both")
    if passed.get("range"):
        return t(lang, "unsigned_range")
    if passed.get("volume"):
        return t(lang, "unsigned_volume")
    return None


def _state_body(cfg, res: Mapping[str, Any], values: Mapping[str, Any], h: str, lang: str) -> str:
    """The 1h / 4h state and what must stand beside it (BETA_COPY_CONTRACT_V1 §2)."""
    from .interpretation import (COMPRESSION, FACTUAL, INSUFFICIENT_HISTORY, INTERPRETED, NORMAL,
                                 VENUES_DIVERGE, interpretation_text)
    kind, key = res.get("kind"), res.get("key") or "missing"
    label = interpretation_text(res, lang)
    pct = _pct_or_na(values.get("price_move_pct"), lang, nd=1)
    oi = _pct_or_na(values.get("oi_change_pct"), lang, nd=1)
    delta = _usd_or_na(values.get("taker_delta_notional_usd"), lang)
    if kind == NORMAL:
        return label
    if kind == INTERPRETED:
        return t(lang, "beside_facts", label=label, pct=pct, oi=oi, delta=delta)
    if kind == COMPRESSION:
        rng = values.get("range_width_pct")
        body = t(lang, "beside_compression", label=label,
                 rng=na(lang) if rng is None else fmt_plain_pct(float(rng), lang), hz=t(lang, "hz_windows_" + h))
        return body + (t(lang, "beside_oi", oi=oi) if key != "compression_oi_na" else "")
    if kind == VENUES_DIVERGE:
        by = values.get("price_move_pct_by_venue") or {}
        parts = [f"{venue_name(ex)} {fmt_signed_pct(float(v), lang)}" for ex, v in by.items()]
        return t(lang, "beside_venues", label=label, venues=", ".join(parts) or na(lang))
    if kind == INSUFFICIENT_HISTORY:
        return t(lang, "beside_insufficient", label=label, pct=pct, oi=oi)
    if kind == FACTUAL:
        taker = (res.get("inputs") or {}).get("taker")
        if key.endswith("_oi_na"):
            dirn = t(lang, "dir_up" if key.startswith("up") else "dir_down")
            k = len(values.get("oi_venues") or ())
            return t(lang, "beside_oi_na", dir=dirn, delta=delta, k=k, n=len(cfg.exchanges))
        if taker in ("MISSING", "IMMATURE", None):
            return t(lang, "beside_delta_na", label=label)
        if _taker_against_price(res):
            return t(lang, "beside_delta_against", label=label, delta=delta)
        return t(lang, "beside_facts", label=label, pct=pct, oi=oi, delta=delta)
    return t(lang, "data_incomplete")


def _line_24h(view: Mapping[str, Any], lang: str) -> str:
    block = ((view.get("horizons") or {}).get("24h")) or {}
    price = (view.get("now") or {}).get("reference_price")
    parts = []
    low, high = block.get("low"), block.get("high")
    if block.get("price_complete") and low is not None and high is not None:
        rng = t(lang, "range_24h", low=fmt_price(low, lang), high=fmt_price(high, lang))
        if price is not None and high > low:
            q = (float(price) - float(low)) / (float(high) - float(low))
            pos = ("pos_low" if q < 0.1 else "pos_lowish" if q < 0.4 else "pos_mid" if q <= 0.6
                   else "pos_highish" if q <= 0.9 else "pos_high")
            rng += ", " + t(lang, pos)
        parts.append(rng)
    else:
        parts.append(t(lang, "range_24h_na"))
    der = view.get("derivatives") or {}
    oi = block.get("oi_change_pct")
    oi_typ = der.get("oi_24h") or {}
    parts.append(t(lang, "oi_24h", oi=na(lang) if oi is None else fmt_signed_pct(float(oi), lang, nd=1))
                 + (t(lang, "oi_usual_part", typ=fmt_plain_pct(oi_typ["typical_abs_pct"], lang, nd=1),
                      n=oi_typ["n_days"]) if oi is not None and oi_typ.get("typical_abs_pct") is not None else ""))
    avg = block.get("funding_rate_avg")
    if avg is None:
        parts.append(t(lang, "funding_avg_na"))
    else:
        payer = t(lang, "payer_longs") if avg > 0 else t(lang, "payer_shorts") if avg < 0 else ""
        f_typ = der.get("funding_24h") or {}
        usual = (t(lang, "funding_usual_part", typ=fmt_funding(float(f_typ["typical"]), lang), n=f_typ["n_days"])
                 if f_typ.get("typical") is not None else "")
        note = "; ".join(x for x in (payer, usual) if x)
        parts.append(t(lang, "funding_avg", f=fmt_funding(float(avg), lang)) + (f" ({note})" if note else ""))
    return t(lang, "now_line", h=t(lang, "hz_24h"), body=" · ".join(parts))


def derivative_lines(view: Mapping[str, Any], lang: str, *, part: str) -> list:
    """The «обычно» of OI change ('oi'), of the 24h funding mean ('funding') and the long/short account
    ratio ('long_short') for the 24h tab (backlog G2). Nothing without the stored block."""
    der = view.get("derivatives") or {}
    if part == "oi":
        x = der.get("oi_24h") or {}
        if x.get("typical_abs_pct") is not None:
            return [t(lang, "der_oi_usual", typ=fmt_plain_pct(x["typical_abs_pct"], lang, nd=1), n=x["n_days"])]
        return [t(lang, "der_usual_short", n=x["n_days"])] if x.get("n_days") else []
    if part == "funding":
        x = der.get("funding_24h") or {}
        if x.get("typical") is not None:
            return [t(lang, "der_funding_usual", typ=fmt_funding(float(x["typical"]), lang), n=x["n_days"])]
        return [t(lang, "der_usual_short", n=x["n_days"])] if x.get("n_days") else []
    x = der.get("long_short")
    if not x:
        return []
    ratio = f"{float(x['ratio']):.2f}"
    ratio = ratio.replace(".", ",") if lang == "ru" else ratio
    if x.get("typical") is None:
        return [t(lang, "der_ls_short", ratio=ratio, n=x["n_days"])]
    typ = f"{float(x['typical']):.2f}"
    return [t(lang, "der_ls", ratio=ratio, typ=typ.replace(".", ",") if lang == "ru" else typ, n=x["n_days"])]


def btc_buttons(view: Mapping[str, Any], lang: str = "en", view_pk: Optional[int] = None):
    """Event only with an open or retained episode. 1h outside fail-closed. No Readiness button:
    the per-rule readiness details carry tiers, sample counts, reason codes and the read-model
    version (BETA_COPY_CONTRACT_V1 §5 rule 5); the main screen already names what is building."""
    row = []
    fail = view.get("product_status") in ("DATA STALE", "DATA DEGRADED")
    focus = view.get("active_episode") or view.get("last_event")
    if view_pk is not None and focus and focus.get("episode_id"):
        row.append((t(lang, "btn_event"), f"o:{int(view_pk)}:event"))
    if view_pk is not None and not fail:
        row.append((t(lang, "btn_1h"), f"o:{int(view_pk)}:1h"))
        row.append((t(lang, "btn_24h"), f"o:{int(view_pk)}:24h"))
    if view_pk is not None and _has_research(view):
        row.append((t(lang, "btn_research"), f"o:{int(view_pk)}:research"))
    rows = [row] if row else []
    block = view.get("decision") or {}
    if block.get("available"):
        rows.append([(t(lang, "btn_levels"), "L:levels"), (t(lang, "btn_risk"), "L:risk")])
        if view.get("kind") == "brief":
            # «🎯 Проверить» the nearest level above and below, filled in (PRE_BETA_SCOPE_DECISION_V1 §5)
            from .check import check_button
            lv = block.get("levels") or {}
            near = [z for z in ((lv.get("above") or [None])[0], (lv.get("below") or [None])[0]) if z]
            if near:
                rows.append([check_button(float(z["edge"]), lang) for z in near])
    return rows or None


def _has_research(view: Mapping[str, Any]) -> bool:
    block = view.get("decision") or {}
    return bool(block.get("available") and block.get("evidence") and not block["evidence"].get("error_type"))


def detail_tab_buttons(view: Mapping[str, Any], lang: str, view_pk: int):
    """Tab row under a Details message. Presses edit that message."""
    row = []
    fail = view.get("product_status") in ("DATA STALE", "DATA DEGRADED")
    focus = view.get("active_episode") or view.get("last_event")
    if focus and focus.get("episode_id"):
        row.append((t(lang, "btn_event"), f"e:{int(view_pk)}:event"))
    if not fail:
        row.append((t(lang, "btn_1h"), f"e:{int(view_pk)}:1h"))
        row.append((t(lang, "btn_24h"), f"e:{int(view_pk)}:24h"))
    if _has_research(view):
        row.append((t(lang, "btn_research"), f"e:{int(view_pk)}:research"))
    return [row] if row else None


def format_research_tab(cfg, view: Mapping[str, Any], lang: str = "en", view_id8: str = "--------") -> str:
    """Research tab from the persisted view: every research finding that describes the market at
    the view's time, with comparator, N, replication and limits, and the ones that cannot be
    checked now (no fresh data). Not recomputed."""
    from .research_render import details_text
    block = view.get("decision") or {}
    at = block.get("as_of")
    now = _dt(at) if at else datetime.now(timezone.utc)
    return _ok(details_text(block.get("evidence"), lang, now=now), lang)


def _window_kyiv(first_bucket: str, last_bucket: Optional[str] = None) -> str:
    start = _dt(first_bucket)
    end = _dt(last_bucket or first_bucket) + timedelta(minutes=5)
    return f"{fmt_kyiv_hm(start)}–{fmt_kyiv_hm(end)}"


def _venue_oi(anchor_view: Mapping[str, Any], lang: str, *, nd: int = 2) -> str:
    raw = anchor_view.get("oi_change_pct_by_venue") or {}
    order = [ex for ex in ("binance", "bybit", "okx") if ex in raw] or list(raw)
    bits = []
    for ex in order:
        v = raw.get(ex)
        bits.append(f"{venue_name(ex)} {na(lang) if v is None else fmt_signed_pct(v, lang, nd=nd)}")
    med = (anchor_view.get("oi_change_pct") or {}).get("value")
    venues = " · ".join(bits) if bits else na(lang)
    if med is None:
        return t(lang, "anchor_oi_na", venues=venues)
    return t(lang, "anchor_oi", med=fmt_signed_pct(med, lang, nd=nd), venues=venues)


def _taker_text(value, lang: str) -> str:
    if value is None:
        return t(lang, "taker_na", na=na(lang))
    if value == 0:
        return t(lang, "taker_flat")
    signed = (MINUS if value < 0 else "+") + fmt_usd(abs(value), lang)
    side = t(lang, "taker_sellers" if value < 0 else "taker_buyers")
    return t(lang, "taker_line", signed=signed, side=side)


def _fmt_liq_body(per_venue: Mapping[str, Mapping[str, Any]], lang: str) -> tuple:
    """Returns (text, (any_lower_bound, any_incomplete_zero))."""
    order = [ex for ex in ("binance", "bybit", "okx") if ex in per_venue] or list(per_venue)
    bits = []
    lower = zero = False
    for ex in order:
        cell = per_venue[ex]
        name = venue_name(ex)
        if cell.get("missing") or cell.get("amount") is None:
            bits.append(f"{name} {na(lang)}")
            continue
        amt = fmt_usd(cell["amount"], lang)
        if cell.get("lower_bound") and cell["amount"] > 0:
            lower = True
            bits.append(f"{name} ≥{amt}")
        elif cell.get("lower_bound"):
            # "at least $0" says nothing: an incomplete zero is marked, not bounded.
            zero = True
            bits.append(f"{name} {amt}*")
        else:
            bits.append(f"{name} {amt}")
    return " · ".join(bits) if bits else na(lang), (lower, zero)


def _anchor_liq_map(anchor_view: Mapping[str, Any]) -> dict:
    """One bucket: Binance is always a lower bound; None is missing, never zero."""
    out = {}
    liq = anchor_view.get("liquidations") or {}
    for side in ("long", "short"):
        per = (liq.get(side) or {}).get("per_venue") or {}
        out[side] = {}
        for ex, amount in per.items():
            if amount is None:
                out[side][ex] = {"amount": None, "missing": True, "lower_bound": False}
            else:
                out[side][ex] = {"amount": float(amount), "missing": False, "lower_bound": ex == "binance"}
    return out


def _liq_lines(venues_by_side: Mapping[str, Mapping], lang: str) -> tuple:
    lines = []
    lower = zero = False
    for side, name_key in (("long", "liq_long_name"), ("short", "liq_short_name")):
        body, (hit, hit_zero) = _fmt_liq_body(venues_by_side.get(side) or {}, lang)
        lower, zero = lower or hit, zero or hit_zero
        lines.append(t(lang, "liq_line", side=t(lang, name_key), Side=t(lang, name_key), body=body))
    return lines, (lower, zero)


def _liq_footnotes(marks: tuple, lang: str) -> list:
    lower, zero = marks
    return ([t(lang, "liq_footnote")] if lower else []) + ([t(lang, "liq_zero_footnote")] if zero else [])


def format_event_tab(cfg, view: Mapping[str, Any], lang: str = "en", view_id8: str = "--------") -> str:
    """Anchor bucket only, from the persisted view. No Now block, no ranks, no versions."""
    ep = view.get("active_episode") or view.get("last_event")
    if ep is None:
        return _ok(t(lang, "measurements_missing"), lang)
    lines = [f"<b>{_e(t(lang, 'event_head', name=plain_name(ep['event_type'], lang)))}</b>"]
    if ep.get("terminal_at"):
        lines.append(t(lang, "event_ended_at", clock=fmt_clock(_dt(ep["terminal_at"]), lang)))
    else:
        start = _run_start(cfg, ep)       # same start as the "why" window below
        opened = start if start is not None else _dt(ep.get("opened_at") or ep.get("opened_bucket"))
        lines.append(t(lang, "event_since", clock=fmt_clock(opened, lang)))
    anchor = (ep.get("anchor") or {}).get("view")
    if anchor is None:
        lines.append(t(lang, "measurements_missing"))
    else:
        lines.append(t(lang, "why_window", window=_run_window(cfg, ep) or _window_kyiv(anchor["bucket_ts"])))
        lines.append(t(lang, "bucket_head", window=_window_kyiv(anchor["bucket_ts"])))
        price = (anchor.get("price_move_pct") or {}).get("value")
        rng = (anchor.get("range_width_pct") or {}).get("value")
        vol = (anchor.get("volume_notional_usd") or {}).get("value")
        level = _level_word(cfg, anchor.get("volume_notional_usd"), lang, omit_normal=False)
        level_bit = "" if not level else " (" + level + ")"
        lines.append("  " + t(
            lang, "anchor_metrics",
            price=na(lang) if price is None else fmt_signed_pct(price, lang),
            range=na(lang) if rng is None else fmt_plain_pct(rng, lang),
            vol=na(lang) if vol is None else fmt_usd(vol, lang),
            level=level_bit))
        lines.append("  " + _venue_oi(anchor, lang))
        taker = (anchor.get("taker_delta_notional_usd") or {}).get("value")
        lines.append("  " + _taker_text(taker, lang))
        liq_lines, lower = _liq_lines(_anchor_liq_map(anchor), lang)
        lines.extend("  " + ln for ln in liq_lines)
    others = view.get("other_active") or []
    if view.get("active_episode") is not None and others:
        lines.append(t(lang, "also_open", names=", ".join(plain_name(et, lang) for et, _st in others)))
    if anchor is not None:
        lines.extend(_liq_footnotes(lower, lang))
    lines.append(t(lang, "terms_footer"))
    return _ok("\n".join(lines), lang)


def format_context_details(cfg, episode: Mapping[str, Any], state: Mapping[str, Any], lang: str = "en",
                           view_id8: str = "--------") -> str:
    """Compatibility wrapper: the Event tab is the user-facing Details for an episode."""
    view = {"active_episode": episode if not episode.get("terminal_at") else None,
            "last_event": episode if episode.get("terminal_at") else None,
            "other_active": []}
    if view["active_episode"] is None and view["last_event"] is None:
        view["last_event"] = episode
    return format_event_tab(cfg, view, lang, view_id8)


def _comparison_suffix(block: Mapping[str, Any], *, ratio, days_key: str, lang: str,
                      horizon: str, day_type: bool = False) -> str:
    """Tab parenthetical. A present ratio names its baseline. An immature one counts down."""
    if ratio is not None:
        key = "h1_ratio" if horizon == "1h" else "h24_ratio"
        return t(lang, key, ratio=fmt_ratio(ratio, lang))
    remaining = _days_remaining(block, days_key, day_type)
    if remaining is None:
        return t(lang, "ratio_unavailable")
    if lang == "en" and remaining == 1:
        return t(lang, "h1_ratio_wait_one" if horizon == "1h" else "h24_ratio_wait_one")
    return t(lang, "h1_ratio_wait" if horizon == "1h" else "h24_ratio_wait", n=remaining)


def _horizon_liq(block: Mapping[str, Any]) -> dict:
    venues = (block.get("liquidations") or {}).get("venues") or {}
    by_side = {"long": {}, "short": {}}
    for ex, sides in venues.items():
        for side in ("long", "short"):
            by_side[side][ex] = (sides or {}).get(side) or {"amount": None, "missing": True, "lower_bound": False}
    return by_side


def _horizon_oi_line(block: Mapping[str, Any], lang: str) -> Optional[str]:
    raw = block.get("oi_by_venue") or {}
    if not raw and block.get("oi_change_pct") is None:
        return None
    return _venue_oi({"oi_change_pct_by_venue": raw,
                      "oi_change_pct": {"value": block.get("oi_change_pct")}}, lang, nd=1)


def _change_sentence(item: Mapping[str, Any], lang: str) -> str:
    rule = item.get("rule")
    if rule == "range":
        key = "changes_range_wider" if item.get("direction") == "wider" else "changes_range_narrower"
        return t(lang, key, a=fmt_plain_pct(item["w"], lang, nd=1), b=fmt_plain_pct(item["p"], lang, nd=1))
    if rule == "volume":
        key = "changes_vol_higher" if item.get("direction") == "higher" else "changes_vol_lower"
        return t(lang, key, a=fmt_usd(item["w"], lang), b=fmt_usd(item["p"], lang))
    if rule == "oi_price":
        oi_up, price_up = bool(item.get("oi_up")), bool(item.get("price_up"))
        if oi_up and price_up:
            key = "changes_oi_up_up"
        elif oi_up:
            key = "changes_oi_up_down"
        elif price_up:
            key = "changes_oi_down_up"
        else:
            key = "changes_oi_down_down"
        return t(lang, key)
    if rule == "funding":
        return t(lang, "changes_funding_pos" if item.get("positive") else "changes_funding_neg")
    return ""


def _changes_lines(block: Mapping[str, Any], lang: str) -> list:
    lines = [t(lang, "changes_head")]
    items = [s for s in (_change_sentence(item, lang) for item in (block.get("changes") or [])) if s]
    if not items:
        lines.append(t(lang, "changes_none"))
    else:
        lines.extend("· " + s for s in items)
    return lines


def _d7_main_line(view: Mapping[str, Any], lang: str) -> Optional[str]:
    regime = view.get("regime") or {}
    if not regime.get("shown"):
        return None
    return t(lang, "d7_main")


def _d7_tab_lines(view: Mapping[str, Any], lang: str) -> list:
    """The three D7 lines from the decision stored on the view. Not recomputed."""
    regime = view.get("regime") or {}
    if not regime.get("shown"):
        return []
    start = fmt_kyiv_hm(_dt(regime["hour_start"]))
    end = fmt_kyiv_hm(_dt(regime["hour_end"]))
    return [t(lang, "d7_h1_1", start=start, end=end), t(lang, "d7_h1_2"), t(lang, "d7_h1_3")]


def format_1h_tab(cfg, view: Mapping[str, Any], lang: str = "en", view_id8: str = "--------") -> str:
    """1h tab from the persisted horizons block. D7 lines only when the view says shown."""
    block = (view.get("horizons") or {}).get("1h")
    if block and block.get("window_start") and block.get("window_end"):
        window = f"{fmt_kyiv_hm(_dt(block['window_start']))}–{fmt_kyiv_hm(_dt(block['window_end']))}"
    else:
        window = "—"
    lines = [f"<b>{_e(t(lang, 'h1_head', window=window, zone=t(lang, 'zone')))}</b>"]
    lower = (False, False)
    if not block or not block.get("complete"):
        lines.append(t(lang, "h1_incomplete_body"))
    else:
        price = block.get("price_move_pct")
        rng = block.get("range_width_pct")
        if price is not None or rng is not None:
            lines.append(t(
                lang, "h1_price_range",
                price=na(lang) if price is None else fmt_signed_pct(price, lang),
                range=na(lang) if rng is None else fmt_plain_pct(rng, lang),
                ratio="" if rng is None else _comparison_suffix(
                    block, ratio=block.get("range_ratio"), days_key=_H1_RANGE_DAYS,
                    lang=lang, horizon="1h", day_type=_day_type_tod(view, _H1_RANGE_DAYS))))
        vol = block.get("volume_notional_usd")
        if vol is not None:
            lines.append(t(lang, "h1_volume", vol=fmt_usd(vol, lang),
                           ratio=_comparison_suffix(
                               block, ratio=block.get("volume_ratio"), days_key=_H1_VOLUME_DAYS,
                               lang=lang, horizon="1h", day_type=_day_type_tod(view, _H1_VOLUME_DAYS))))
    if block:
        oi_line = _horizon_oi_line(block, lang)
        if oi_line:
            lines.append(oi_line)
        lines.append(_taker_text(block.get("taker_delta_notional_usd_sum"), lang))
        liq_lines, lower = _liq_lines(_horizon_liq(block), lang)
        lines.extend(liq_lines)
        funding = block.get("funding_rate")
        lines.append(t(lang, "funding_na", na=na(lang)) if funding is None
                     else t(lang, "funding_now", rate=fmt_funding(funding, lang)))
    lines.extend(_d7_tab_lines(view, lang))
    lines.extend(_liq_footnotes(lower, lang))
    lines.append(t(lang, "terms_footer"))
    return _ok("\n".join(lines), lang)


def format_24h_tab(cfg, view: Mapping[str, Any], lang: str = "en", view_id8: str = "--------") -> str:
    """24h tab from the persisted horizons block. No D7 lines."""
    block = (view.get("horizons") or {}).get("24h")
    if block and block.get("window_end"):
        hm = fmt_kyiv_hm(_dt(block["window_end"]))
    else:
        hm = "—"
    lines = [f"<b>{_e(t(lang, 'h24_head', hm=hm, zone=t(lang, 'zone')))}</b>"]
    lower = (False, False)
    if not block:
        lines.append(t(lang, "h24_incomplete"))
    else:
        if block.get("price_complete") and block.get("price_move_pct") is not None:
            lines.append(t(
                lang, "h24_price",
                price=fmt_signed_pct(block["price_move_pct"], lang, nd=1),
                high=na(lang) if block.get("high") is None else fmt_price(block["high"], lang),
                low=na(lang) if block.get("low") is None else fmt_price(block["low"], lang)))
            if block.get("range_width_pct") is not None:
                lines.append(t(
                    lang, "h24_range",
                    range=fmt_plain_pct(block["range_width_pct"], lang, nd=1),
                    ratio=_comparison_suffix(
                        block, ratio=block.get("range_ratio"), days_key=_H24_RANGE_DAYS,
                        lang=lang, horizon="24h")))
        else:
            lines.append(t(lang, "h24_incomplete"))
        vol = block.get("volume_notional_usd")
        if vol is not None and block.get("volume_complete"):
            lines.append(t(lang, "h24_volume", vol=fmt_usd(vol, lang),
                           ratio=_comparison_suffix(
                               block, ratio=block.get("volume_ratio"), days_key=_H24_VOLUME_DAYS,
                               lang=lang, horizon="24h")))
        elif vol is not None and block.get("volume_partial"):
            lines.append(t(lang, "h24_volume_partial", vol=fmt_usd(vol, lang)))
        oi_line = _horizon_oi_line(block, lang)
        if oi_line:
            lines.append(oi_line)
            lines.extend(derivative_lines(view, lang, part="oi"))
        lines.append(_taker_text(block.get("taker_delta_notional_usd_sum"), lang))
        liq_lines, lower = _liq_lines(_horizon_liq(block), lang)
        lines.extend(liq_lines)
        now = block.get("funding_rate")
        avg = block.get("funding_rate_avg")
        lines.append(t(
            lang, "funding_24h",
            now=na(lang) if now is None else fmt_funding(now, lang),
            avg=na(lang) if avg is None else fmt_funding(avg, lang)))
        if avg is not None:
            lines.extend(derivative_lines(view, lang, part="funding"))
        lines.extend(derivative_lines(view, lang, part="long_short"))
        lines.extend(_changes_lines(block, lang))
    lines.extend(_liq_footnotes(lower, lang))
    lines.append(t(lang, "terms_footer"))
    return _ok("\n".join(lines), lang)


def feedback_buttons(public_id: str, lang: str = "en") -> list:
    """Useful / Noise under the product push. No Details button: the episode details
    expose the detector name, internal id and rules version (PRODUCT_FIRST_DECISION_V1
    §3 row 9, BETA_COPY_CONTRACT_V1 §4). The id travels only in callback data. Above them
    the «BTC сейчас» action (owner decision 2026-10-03): push → /btc in one tap."""
    return [push_action_row(lang),
            [(t(lang, "btn_useful"), f"u:{public_id}"),
             (t(lang, "btn_noise"), f"n:{public_id}")]]


PUSH_BTC_ACTION = "b:now"


def push_action_row(lang: str = "en") -> list:
    """The one action under every push: open the current /btc view (activity `btn_btc_now`)."""
    return [(t(lang, "btn_btc_now"), PUSH_BTC_ACTION)]


# ---- legacy status / push / history / readiness (same facts, catalog wording) ----
def _pct_rank(snapshot: Mapping[str, Any], key: str, lang: str) -> str:
    p = (snapshot.get("percentiles") or {}).get(key) or {}
    if p.get("rank") is None:
        return t(lang, "rank_na")
    if p.get("tier") != "mature":
        return t(lang, "rank_immature", tier=_e(p.get("tier")))
    return t(lang, "rank_pct", n=f"{p['rank'] * 100:.0f}")


def format_status(status: Mapping[str, Any], open_episodes: Sequence[Any],
                  snapshot: Optional[Mapping[str, Any]], lang: str = "en") -> str:
    lines = [f"<b>{_e(t(lang, 'status_title', status=status['status']))}</b>"]
    last = status.get("last_good_bucket")
    if last is not None:
        lines.append(t(lang, "status_eval", when=fmt_kyiv_date_hm(last + timedelta(minutes=5), lang)))
    else:
        lines.append(t(lang, "status_eval_none"))
    if status["status"] in ("DATA DEGRADED", "DATA STALE"):
        lines.append(t(lang, "insufficient"))
    for ep in open_episodes:
        lines.append(t(lang, "status_episode", name=_e(event_label(ep.event_type, lang)),
                       state=state_label(ep.state, lang), when=fmt_kyiv_date_hm(ep.opened_at, lang)))
    if snapshot is not None and snapshot.get("materialized") and status["status"] != "DATA STALE":
        lines.append("\n<b>" + t(lang, "status_context") + "</b>")
        lines.append(t(lang, "status_price", v=_pct_rank(snapshot, "c:price_move_pct_median", lang)))
        lines.append(t(lang, "status_oi", v=_pct_rank(snapshot, "c:oi_change_pct_median", lang)))
        lines.append(t(lang, "status_range", v=_pct_rank(snapshot, "c:range_width_pct_median", lang)))
        lines.append(t(lang, "status_volume", v=_pct_rank(snapshot, "c:volume_notional_usd_sum", lang)))
        ref = snapshot.get("reference") or {}
        if ref.get("status") == "OK":
            lines.append(t(lang, "status_ref", price=fmt_price(ref["price"], lang),
                           venues=", ".join(venue_name(ex) for ex in ref["exchanges"])))
        evals = snapshot.get("rule_evaluations") or {}
        gated = sorted(k for k, v in evals.items() if v.get("status") == "NOT_EVALUABLE")
        if gated:
            lines.append(t(lang, "status_gated", names=", ".join(_e(event_label(k, lang)) for k in gated)))
    lines.append("\n" + t(lang, "disclaimer"))
    return _ok("\n".join(lines), lang)


PUSH_MAX_LINES = 8


def format_push(episode: Any, snapshot: Optional[Mapping[str, Any]] = None, lang: str = "en",
                gate: Optional[Mapping[str, Any]] = None, analog: Optional[Mapping[str, Any]] = None,
                since_year: Optional[int] = None, latency: Optional[Mapping[str, Any]] = None) -> str:
    """The unusual-hour push (BETA_COPY_CONTRACT_V1 §1.2): the 1h state around the
    TRIGGERED episode, never the detector name, never an id. At most 8 non-empty
    lines. `gate` is the push decision's stored hour gate; without it only the hour
    and the time are known. `latency` is the measured delay field (`beta.latency.latency_field`,
    backlog A4); its line is drawn by the template work of F1, not here."""
    gate = gate or {}
    values = gate.get("values") or {}
    when = episode.triggered_at
    if gate.get("window_start") and gate.get("window_end"):
        span = t(lang, "window_kyiv", start=fmt_kyiv_hm(_dt(gate["window_start"])), end=fmt_kyiv_hm(_dt(gate["window_end"])))
    else:
        span = t(lang, "window_kyiv", start=fmt_kyiv_hm(when - timedelta(hours=1)), end=fmt_kyiv_hm(when))
    state = _gate_state_text(gate, lang)
    lines = [f"<b>{_e(t(lang, 'push_hour_title'))}</b>", span, "", _e(state[:1].upper() + state[1:])]
    pct = values.get("price_move_pct")
    if pct is None:
        lines.append(t(lang, "price_line_na"))
    else:
        if values.get("open") is not None and values.get("close") is not None:
            price = t(lang, "price_line", pct=fmt_signed_pct(float(pct), lang), open=fmt_price(values["open"], lang),
                      close=fmt_price(values["close"], lang))
        else:
            price = t(lang, "price_line_noprices", pct=fmt_signed_pct(float(pct), lang))
        tail = (gate.get("passed") or {}).get("price")
        if tail in ("up", "down"):
            price += t(lang, "price_tail", dir=t(lang, "price_rise_95" if tail == "up" else "price_drop_95"))
        lines.append(price)
    res = gate.get("interpretation") or {}
    oi, delta = values.get("oi_change_pct"), values.get("taker_delta_notional_usd")
    oi_txt = na(lang) if oi is None else fmt_signed_pct(float(oi), lang, nd=1)
    if delta is None:
        lines.append(t(lang, "oi_only_line", oi=oi_txt))
        lines.append(t(lang, "beside_delta_na_bare"))
    else:
        line = t(lang, "oi_delta_line", oi=oi_txt, delta=fmt_usd(float(delta), lang, signed=True))
        if res.get("kind") == "FACTUAL" and _taker_against_price(res):
            line += t(lang, "delta_against_suffix")
        lines.append(line)
    liq = _liq_votes_line(gate, lang)
    if liq:
        lines.append(liq)
    unsigned = _unsigned_line(gate, lang)
    if unsigned:
        lines.append(unsigned)
    if gate.get("venues_agree") is not None:
        lines.append(t(lang, "venues_line", k=int(gate["venues_agree"]), n=max(int(gate.get("venues") or 0), 3)))
    # the history line and the research line are extras: each is added only while the push
    # stays within its 8 non-empty lines (BETA_COPY_CONTRACT_V1 §5)
    extras = []
    if analog:
        from .decision_format import analog_line
        extras.append(analog_line(analog, lang, since_year=since_year))
    extras.append(_research_line(gate.get("interpretation") or {}, "1h", lang))
    for line in extras:
        if line and sum(1 for x in lines if x.strip()) < PUSH_MAX_LINES:
            lines.append(line)
    return _ok("\n".join(lines), lang)


def format_push_v02(episode: Any, lang: str = "en") -> str:
    """The V0.2 event-push text. Never delivered since the unusual-hour push
    (BETA_COPY_CONTRACT_V1); kept only for offline replay of recorded V0.2 pushes."""
    lines = [f"<b>{_e(t(lang, 'push_title', name=event_label(episode.event_type, lang)))}</b>",
             t(lang, "push_decision", when=fmt_kyiv_date_hm(episode.triggered_at, lang)),
             _e(event_description(episode.event_type, lang))]
    if episode.reference_price is not None:
        lines.append(t(lang, "push_close", price=fmt_price(episode.reference_price, lang),
                       venues=", ".join(venue_name(ex) for ex in episode.reference_exchanges)))
    lines.append("\n" + t(lang, "disclaimer"))
    return _ok("\n".join(lines), lang)


def push_status_label(row: Mapping[str, Any], lang: str = "en") -> str:
    """What happened to the message, in words: never a delivery state or suppression code."""
    decision = row.get("decision")
    if decision is None or decision == "SUPPRESSED":
        return t(lang, "push_none")
    states = set(row.get("delivery_states") or ())
    if "SENT" in states:
        return t(lang, "push_sent")
    if "DELIVERY_UNKNOWN" in states:
        return t(lang, "push_unconfirmed")
    if "EXPIRED_UNDELIVERED" in states:
        return t(lang, "push_expired")
    return t(lang, "push_pending")


_END_KEYS = {"NOT_EVALUABLE": "end_not_evaluable", "MAX_DURATION": "end_max_duration",
             "DETECTOR_VERSION_CHANGED": "end_version_changed", "DETECTION_GAP": "end_detection_gap"}


def _range_summary(outcomes: Iterable[Mapping[str, Any]], lang: str) -> str:
    parts = []
    for o in sorted(outcomes, key=lambda o: ["15m", "30m", "1h", "4h", "24h"].index(o["horizon"])):
        mark = "*" if (o.get("revision") or 1) > 1 else ""
        if o["status"] == "COMPLETE":
            pct = f"{o['realized_range_pct']:.2f}"
            if lang == "ru":
                pct = pct.replace(".", ",")
            parts.append(t(lang, "range_complete", h=o["horizon"], pct=pct, mark=mark))
        else:
            parts.append(t(lang, "range_na", h=o["horizon"]))
    return "; ".join(parts) if parts else t(lang, "follow_pending")


def format_history(rows: Sequence[Mapping[str, Any]],
                   outcomes_by_pk: Mapping[int, Sequence[Mapping[str, Any]]], lang: str = "en") -> str:
    lines = ["<b>" + t(lang, "history_title") + "</b>"]
    if not rows:
        lines.append(t(lang, "history_empty"))
    for r in rows:
        corr = t(lang, "history_corrected") if r.get("correction_flag") else ""
        end = _END_KEYS.get(r.get("terminal_reason") or "")
        term = f", {t(lang, end)}" if end else ""
        lines.append(
            f"• {_e(event_label(r['event_type'], lang))} — "
            f"{state_label(r['state'], lang)}{term}{corr}\n"
            f"  {t(lang, 'history_times', opened=_when(r['opened_at'], lang), triggered=_when(r.get('triggered_at'), lang), push=push_status_label(r, lang))}\n"
            f"  {_range_summary(outcomes_by_pk.get(r['episode_pk'], ()), lang)}")
    lines.append("<i>" + t(lang, "history_note") + "</i>")
    lines.append(t(lang, "disclaimer"))
    return _ok("\n".join(lines), lang)


def format_details(episode: Any, transitions: Sequence[Mapping[str, Any]],
                   outcomes: Sequence[Mapping[str, Any]], lang: str = "en") -> str:
    lines = [f"<b>{episode.public_id} — {_e(event_label(episode.event_type, lang))}</b>",
             _e(event_description(episode.event_type, lang)),
             t(lang, "details_rules", ver=_e(episode.rules_version), digest=episode.rules_digest[:12])]
    for tr in transitions:
        lines.append(t(lang, "details_transition", when=fmt_kyiv_date_hm(tr["decision_ts"], lang),
                       state=state_label(tr["to_state"], lang),
                       reason=tr["reason"].lower().replace("_", " ")))
    if episode.reference_price is not None:
        lines.append(t(lang, "details_close", price=fmt_price(episode.reference_price, lang)))
    for o in sorted(outcomes, key=lambda o: ["15m", "30m", "1h", "4h", "24h"].index(o["horizon"])):
        if o["status"] == "COMPLETE":
            rev = t(lang, "details_revised") if (o.get("revision") or 1) > 1 else ""
            lines.append(t(lang, "details_outcome", h=o["horizon"],
                           rng=f"{o['realized_range_pct']:.2f}".replace(".", "," if lang == "ru" else "."),
                           up=fmt_signed_pct(o["max_up_pct"], lang),
                           down=fmt_signed_pct(-o["max_down_pct"], lang),
                           close=fmt_signed_pct(o["close_return_pct"], lang), rev=rev))
        else:
            lines.append(f"{o['horizon']}: {o['status'].lower().replace('_', ' ')}")
    if episode.correction_flag:
        lines.append(t(lang, "details_corrected", note=_e(episode.correction_note or "")))
    lines.append("\n" + t(lang, "disclaimer"))
    return _ok("\n".join(lines), lang)


def format_owner_alert(alerts: Sequence[Mapping[str, Any]]) -> str:
    lines = ["<b>Signalbot beta — owner health alert</b>"]
    for a in alerts:
        lines.append(f"• {_e(a['key'])} {_e(a.get('detail') or '')}")
    return "\n".join(lines)


def _readiness_reason(cfg, reason: Optional[str], lang: str) -> str:
    r = reason or ""
    if r.startswith("FAMILY_UNUSABLE:"):
        fam = r.split(":", 1)[1]
        return t(lang, "reason_venues", n=cfg.min_venues, fam=t(lang, _FAMILY_WORDS.get(fam, "fam_price")))
    if r == "INSUFFICIENT_ELIGIBLE_VENUES":
        return t(lang, "reason_eligible")
    if r.startswith("VALUE_UNAVAILABLE"):
        return t(lang, "reason_value")
    if r.startswith("PERCENTILE_MISSING"):
        return t(lang, "reason_pct")
    key = _REASON_EXACT.get(r)
    if key:
        return t(lang, key)
    return r.lower().replace("_", " ") or t(lang, "reason_not_eval")


def _group_text(cfg, g: Mapping[str, Any], maturity_days: float, lang: str) -> str:
    st = g["status"]
    if st == "READY":
        return t(lang, "ready_word")
    text = t(lang, _READY_KEYS[st])
    if st == "HISTORY_BUILDING" and g.get("progress"):
        p = g["progress"]
        text += " · " + t(lang, "ready_span", name=t(lang, _HISTORY_NAMES.get(p["metric"], "hist_price")),
                          span=f"{p['span_days']:.1f}", need=f"{maturity_days:.0f}")
    elif st in ("DATA_UNAVAILABLE", "DEGRADED"):
        text += " · " + _readiness_reason(cfg, g.get("reason"), lang)
    if g.get("partly_ready"):
        text = t(lang, "ready_partly", a=g["ready_members"], b=g["enabled_members"], text=text)
    return text


def format_readiness_details(cfg, rd: Mapping[str, Any], lang: str = "en") -> str:
    close = _dt(rd["bucket_ts"]) + timedelta(minutes=5)
    lines = [f"<b>{_e(t(lang, 'ready_title', when=fmt_kyiv_date_hm(close, lang)))}</b>",
             t(lang, "ready_intro", days=f"{rd['maturity_days']:.0f}")]
    for g in rd["groups"]:
        lines.append(f"\n<b>{_e(g['label'])}</b>: {_group_text(cfg, g, rd['maturity_days'], lang)}")
        for et in g["members"]:
            e = rd["events"][et]
            reason = f" ({_e(e['reason'])})" if e.get("reason") else ""
            lines.append(t(lang, "ready_member", name=_e(event_label(et, lang)),
                           status=t(lang, _READY_KEYS[e["status"]]), reason=reason))
            for key, m in (e.get("metrics") or {}).items():
                lines.append("  " + t(lang, "ready_metric", name=_e(t(lang, _HISTORY_NAMES.get(key, "hist_price"))),
                                      tier=m["tier"] or na(lang), n=m["sample_size"] or 0,
                                      span=f"{m['span_days']:.1f}"))
            for ex, v in (e.get("venues") or {}).items():
                reason = f" ({_e(v['reason'])})" if v.get("reason") else ""
                lines.append("  " + t(lang, "ready_venue", ex=venue_name(ex), state=t(lang, _READY_KEYS[v["state"]]),
                                      reason=reason, tier=v["tier"] or na(lang), span=f"{v['span_days']:.1f}"))
    lines.append("\n" + t(lang, "ready_footer", ver=_e(rd["readiness_version"])))
    impact = rd.get("impact_context") or {}
    if impact and not impact.get("warmup_complete"):
        lines.append(t(lang, "d7_warmup"))
    lines.append("\n" + t(lang, "disclaimer"))
    return _ok("\n".join(lines), lang)


def view_id8(payload_digest: str) -> str:
    return (payload_digest or "--------")[:8]
