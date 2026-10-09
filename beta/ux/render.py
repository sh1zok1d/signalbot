"""Pulsy UX V2 render (docs/PULSY_UX_STANDARD_V2.md): facts → salience → phrases → Telegram HTML.

Public API for track B (stable): `render(screen, level, lang, facts) -> (html, buttons)`, where buttons is
`list[list[(label, callback)]]`. Screens and levels: SCREENS. Not wired to any user surface: callers
check `enabled(cfg)` (`ux.v2_enabled`, default false). Deterministic; no LLM; prints only PHRASES keys
and fact values; L1 holds no historical number."""
from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Mapping

from . import select as sel
from .phrases import EMOJI, text

UX_VERSION = "PULSY_UX_V2_P0"
SCREENS = {"btc": (1, 2, 3), "levels": (1,), "level_card": (1,), "hour": (1,), "level": (1,), "move": (1,),
           "brief": (1,)}
MAX_CHARS = {1: 600, 2: 900, 3: 1500}
NOTIFICATION_MAX_CHARS = 500
CALLBACK_MAX_BYTES = 64
NARROW_NBSP, NBSP = " ", " "


def enabled(cfg) -> bool:
    return bool((cfg.raw.get("ux") or {}).get("v2_enabled"))


def callback(screen: str, level: int) -> str:
    data = f"ux:{screen}:{level}"
    assert len(data.encode("utf-8")) <= CALLBACK_MAX_BYTES
    return data


# ---- numbers: the i18n formatters, with no-break spaces (thousands: narrow NBSP; number–unit: NBSP) ----
def _nb(s: str) -> str:
    s = re.sub(r"(?<=\d) (?=\d)", NARROW_NBSP, s)
    return s.replace(" ", NBSP)


def price(v, lang):
    from beta.i18n import fmt_price
    return _nb(fmt_price(float(v), lang))


def spct(v, lang):
    from beta.i18n import fmt_signed_pct
    return _nb(fmt_signed_pct(float(v), lang))


def ppct(v, lang):
    from beta.i18n import fmt_plain_pct
    return _nb(fmt_plain_pct(float(v), lang))


def usd(v, lang):
    from beta.i18n import fmt_usd
    return _nb(fmt_usd(float(v), lang))


def clock(iso: str) -> str:
    from beta.i18n import fmt_kyiv_hm
    return fmt_kyiv_hm(datetime.fromisoformat(iso.replace("Z", "+00:00")))


def level_name(member: Mapping[str, Any], lang: str) -> str:
    """The level's name from its data (decision_format.level_name, the old render's own map)."""
    from beta.decision_format import level_name as name
    return name(member, lang)


def _e(s: str) -> str:
    return html.escape(s, quote=False)


def _join(blocks) -> str:
    return "\n\n".join("\n".join(_e(x) if not x.startswith("<b>") else x for x in b) for b in blocks if b)


def _hdr(s: str) -> str:
    return f"<b>{_e(s)}</b>"


# ---- /btc ------------------------------------------------------------------------------------------
def _cfg_rule_values() -> dict:
    from beta.config import BetaConfig
    cfg = BetaConfig.load()
    c = cfg.section("context")
    days = int(str(cfg["percentile_window"]).rstrip("d"))
    return {"high": round((1 - c["label_high"]) * 100), "extreme": round((1 - c["label_extreme"]) * 100), "days": days}


def _event_name(kind: str, lang: str) -> str:
    return {"CPI": "CPI", "FOMC": "FOMC"}.get(kind, kind) if lang == "en" else \
        {"CPI": "CPI (инфляция США)", "FOMC": "решение ФРС"}.get(kind, kind)


def _l1_line(key: str, f, lang: str) -> str:
    if key == "episode":
        from beta.formatter import plain_name
        return text("l1_episode", lang, name=plain_name(f["episode"]["event_type"], lang))
    if key == "level_at":
        z = f["levels"]["at"]
        return text("l1_level_at", lang, name=level_name(z["members"][0], lang), edge=price(z["edge"], lang))
    if key == "event_today":
        e = sel.next_event(f)
        return text("l1_event_today", lang, clock=clock(e["at"]), event=_event_name(e["kind"], lang))
    return text({"range_extreme": "l1_range_extreme", "range_high": "l1_range_high", "volume_high": "l1_volume_high",
                 "corridor_edge": "l1_corridor_edge", "stale": "l1_stale", "nothing": "l1_nothing"}[key], lang)


def _l2_line(key: str, f, lang: str) -> str:
    rv = _cfg_rule_values()
    if key == "level_at":
        return text("l2_level_at", lang, name=level_name(f["levels"]["at"]["members"][0], lang))
    if key == "range_high":
        return text("l2_range", lang, top=rv["high"], days=rv["days"])
    if key == "range_extreme":
        return text("l2_range_extreme", lang, top=rv["extreme"], days=rv["days"])
    if key == "volume_high":
        return text("l2_volume", lang, top=rv["high"], days=rv["days"])
    if key == "corridor_edge":
        return text("l2_corridor_edge", lang, cov=round(float(f.get("corridor_coverage") or 0) * 100))
    return text({"stale": "l2_stale", "episode": "l2_episode", "event_today": "l2_event", "nothing": "l2_nothing"}[key],
                lang)


def _btc_header(f, lang: str) -> list:
    head = text("hdr_btc", lang, price=price(f["price"], lang)) if f.get("price") is not None else text("hdr_btc_na", lang)
    out = [_hdr(head)]
    if f.get("data_through"):
        out.append(text("asof", lang, clock=clock(f["data_through"])))
    return out


def _btc_l3(f, lang: str) -> list:
    h1, h24, out = f.get("h1") or {}, f.get("h24") or {}, []
    if h1.get("price_move_pct") is not None:
        out.append(text("l3_price_1h", lang, pct=spct(h1["price_move_pct"], lang)))
    base, days = h1.get("baseline_median") or {}, h1.get("baseline_days") or {}
    if h1.get("range_width_pct") is not None and base.get("range_width_pct_median") is not None:
        out.append(text("l3_range_1h", lang, val=ppct(h1["range_width_pct"], lang),
                        base=ppct(base["range_width_pct_median"], lang), n=int(days.get("range_width_pct_median") or 0)))
    if h1.get("volume_notional_usd") is not None and base.get("volume_notional_usd_sum") is not None:
        out.append(text("l3_volume_1h", lang, val=usd(h1["volume_notional_usd"], lang),
                        base=usd(base["volume_notional_usd_sum"], lang), n=int(days.get("volume_notional_usd_sum") or 0)))
    oi = h1.get("oi_change_pct")
    if oi:
        out.append(text("l3_oi_down" if oi < 0 else "l3_oi_up", lang, pct=spct(oi, lang)))
    if h24.get("price_complete") and h24.get("high") is not None and h24.get("low") is not None:
        out.append(text("l3_hilo_24h", lang, high=price(h24["high"], lang), low=price(h24["low"], lang)))
    c = f.get("corridor_24h") or {}
    if c.get("lower") is not None and c.get("upper") is not None:
        out.append(text("l3_corridor", lang, lower=price(c["lower"], lang), upper=price(c["upper"], lang)))
    return out


def _btc(level: int, lang: str, f) -> tuple:
    keys = sel.salient(f)
    if level == 1:
        body = [_l1_line(k, f, lang) for k in keys]
        buttons = [[(text("btn_why", lang), callback("btc", 2)), (text("btn_data", lang), callback("btc", 3))],
                   [(text("btn_levels", lang), callback("levels", 1))]]
        return _join([_btc_header(f, lang), body]), buttons
    if level == 2:
        body = [_l2_line(k, f, lang) for k in keys]
        return (_join([[_hdr(text("hdr_why", lang))], body]),
                [[(text("btn_data", lang), callback("btc", 3)), (text("btn_back", lang), callback("btc", 1))]])
    return (_join([[_hdr(text("hdr_data", lang))], _btc_l3(f, lang)]),
            [[(text("btn_back", lang), callback("btc", 1))]])


# ---- levels ----------------------------------------------------------------------------------------
def card_line(z: Mapping[str, Any], lang: str) -> str:
    return text("lv_card", lang, name=level_name(z["members"][0], lang), edge=price(z["edge"], lang),
                dist=spct(float(z["distance_pct"]), lang))


def _levels(lang: str, f) -> tuple:
    lv = f.get("levels") or {}
    above, below = [z for z in lv.get("above") or () if z], [z for z in lv.get("below") or () if z]
    blocks = [[_hdr(text("hdr_levels", lang))]]
    if above:
        blocks.append([text("lv_above", lang)] + ["📍 " + card_line(z, lang) for z in above])
    if below:
        blocks.append([text("lv_below", lang)] + ["📍 " + card_line(z, lang) for z in below])
    if not above and not below:
        blocks.append([text("lv_none", lang)])
    return _join(blocks), [[(text("btn_back", lang), callback("btc", 1))]]


def _level_card(lang: str, f) -> tuple:
    z = f["zone"]
    return (_join([[_hdr(level_name(z["members"][0], lang) + " " + price(z["edge"], lang))], [card_line(z, lang)]]),
            [[(text("btn_back", lang), callback("levels", 1))]])


# ---- notifications ---------------------------------------------------------------------------------
def _hour(lang: str, f) -> tuple:
    span = f"{clock(f['window_start'])}–{clock(f['window_end'])}"
    body = []
    if (f.get("passed") or {}).get("range"):
        body.append(text("nt_hour_range", lang))
    if (f.get("passed") or {}).get("volume"):
        body.append(text("nt_hour_volume", lang))
    if f.get("price_move_pct") is not None:
        body.append(text("nt_hour_price", lang, pct=spct(f["price_move_pct"], lang)))
    return _join([[_hdr("🕐 " + text("nt_hour", lang, span=span))], body]), [[(text("btn_why", lang), callback("btc", 2))]]


def _level_alert(lang: str, f) -> tuple:
    name = level_name(f["member"], lang)
    return (_join([[_hdr("📍 " + text("nt_level", lang, name=name, level=price(f["level"], lang)))],
                   [text("nt_level_price", lang, price=price(f["price"], lang), clock=clock(f["at"]))]]),
            [[(text("btn_levels", lang), callback("levels", 1))]])


def _move(lang: str, f) -> tuple:
    return (_join([[_hdr("⚡ " + text("nt_move", lang, pct=spct(f["move_pct"], lang)))],
                   [text("nt_move_span", lang, start=clock(f["start"]), end=clock(f["at"]),
                         open=price(f["open"], lang), close=price(f["close"], lang))]]),
            [[(text("btn_levels", lang), callback("levels", 1))]])


def _brief(lang: str, f) -> tuple:
    hours = int(f.get("window_hours") or 8)
    w = f.get("window") or {}
    first = []
    if w.get("price_move_pct") is not None and w.get("low") is not None and w.get("high") is not None:
        first.append(text("nt_brief_move", lang, hours=hours, pct=spct(w["price_move_pct"], lang),
                          low=price(w["low"], lang), high=price(w["high"], lang)))
    body = [_l1_line(k, f, lang) for k in sel.salient(f)]
    return (_join([[_hdr("☀️ " + text("nt_brief", lang, hours=hours))], first, body]),
            [[(text("btn_why", lang), callback("btc", 2)), (text("btn_levels", lang), callback("levels", 1))]])


_SCREENS = {"levels": _levels, "level_card": _level_card, "hour": _hour, "level": _level_alert, "move": _move,
            "brief": _brief}


def render(screen: str, level: int, lang: str, facts: Mapping[str, Any]) -> tuple:
    """(html, buttons) for one screen and level. Raises on an unknown screen or level, never guesses."""
    if screen not in SCREENS or level not in SCREENS[screen]:
        raise ValueError(f"no P0 template for {screen!r} level {level}")
    if lang not in ("ru", "en"):
        raise ValueError(f"unknown lang {lang!r}")
    out = _btc(level, lang, facts) if screen == "btc" else _SCREENS[screen](lang, facts)
    from beta.i18n import assert_descriptive
    assert_descriptive(re.sub(r"<[^>]+>", "", out[0]), lang)
    return out


def max_chars(screen: str, level: int) -> int:
    return NOTIFICATION_MAX_CHARS if screen in ("hour", "level", "move", "brief") else MAX_CHARS[level]


def used_emoji(html_text: str) -> set:
    return {e for e in EMOJI if e in html_text}

