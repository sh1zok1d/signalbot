"""Pulsy UX V2 render (docs/PULSY_UX_STANDARD_V2.md): facts → salience → phrases → Telegram HTML.

Public API for track B (stable): `render(screen, level, lang, facts) -> (html, buttons)`, where buttons is
`list[list[(label, callback)]]`. Screens and levels: SCREENS. Not wired to any user surface: callers
check `enabled(cfg)` (`ux.v2_enabled`, default false). Deterministic; no LLM; prints only PHRASES keys
and fact values; L1 holds no historical number."""
from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Mapping, Optional

from . import select as sel
from .phrases import EMOJI, EPISODES, text

UX_VERSION = "PULSY_UX_V2_P0"
SCREENS = {"btc": (1, 2, 3), "levels": (1,), "level_card": (1,), "hour": (1,), "level": (1,), "move": (1,),
           "brief": (1,)}
MAX_CHARS = {1: 600, 2: 900, 3: 1500}
NOTIFICATION_MAX_CHARS = 500
CALLBACK_MAX_BYTES = 64
NEAR_MAX = 2                                     # «🎯 Рядом» on L1: at most two levels
NARROW_NBSP, NBSP = " ", " "
# the keys that put a «moving» state line on L1 (the others only add context, the calendar or «Рядом»)
_ACTIVE = ("episode", "range_extreme", "range_high", "volume_high")


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


def usd(v, lang, signed=False):
    from beta.i18n import fmt_usd
    return _nb(fmt_usd(abs(float(v)) if not signed else float(v), lang))


def clock(iso: str) -> str:
    from beta.i18n import fmt_kyiv_hm
    return fmt_kyiv_hm(datetime.fromisoformat(iso.replace("Z", "+00:00")))


def episode_name(event_type: str, lang: str) -> str:
    """The episode's short trader name (phrases epn_*); every EVENT_TYPE has one."""
    return text("epn_" + EPISODES[event_type], lang)


def level_name(member: Mapping[str, Any], lang: str) -> str:
    """The level's name from its data (decision_format.level_name, the old render's own map)."""
    from beta.decision_format import level_name as name
    return name(member, lang)


def _e(s: str) -> str:
    return html.escape(s, quote=False)


def _hdr(s: str) -> str:
    return f"<b>{_e(s)}</b>"


def _join(blocks) -> str:
    """Blocks separated by one blank line; a block's first line is its bold header when marked."""
    out = []
    for b in blocks:
        if not b:
            continue
        out.append("\n".join(x[1:] if x.startswith("\x00") else _e(x) for x in b))
    return "\n\n".join(out)


def H(s: str) -> str:                      # a header line (bold), passed through _join unescaped
    return "\x00" + _hdr(s)


def _sentence(fragments) -> str:
    s = ", ".join(fragments)
    return s[:1].upper() + s[1:] + "."


# ---- shared pieces -------------------------------------------------------------------------------
def _event_name(kind: str, lang: str) -> str:
    return text({"CPI": "ev_cpi", "FOMC": "ev_fomc"}[kind], lang) if kind in ("CPI", "FOMC") else kind


def _side(z: Mapping[str, Any], f: Mapping[str, Any]) -> int:
    lv = f.get("levels") or {}
    if any(z is a for a in lv.get("above") or ()):
        return 1
    if any(z is b for b in lv.get("below") or ()):
        return -1
    p = f.get("price")
    mid = (float(z["low"]) + float(z["high"])) / 2.0 if z.get("low") is not None else float(z["edge"])
    return 1 if p is None or mid >= p else -1


def _level_line(key: str, z: Mapping[str, Any], f, lang: str) -> str:
    if z is (f.get("levels") or {}).get("at"):
        return text("lv_at_line", lang, name=level_name(z["members"][0], lang), edge=price(z["edge"], lang))
    return text(key, lang, arrow="↑" if _side(z, f) > 0 else "↓", name=level_name(z["members"][0], lang),
                edge=price(z["edge"], lang), dist=spct(float(z["distance_pct"]), lang))


def _nearest(f, n: int) -> list:
    """The level at the price first, then the nearest above and the nearest below, at most n."""
    lv = f.get("levels") or {}
    out = [lv["at"]] if lv.get("at") else []
    for side in ("above", "below"):
        zs = [z for z in lv.get(side) or () if z and z.get("distance_pct") is not None]
        if zs:
            out.append(min(zs, key=lambda z: abs(float(z["distance_pct"]))))
    return out[:n]


# ---- /btc L1 -------------------------------------------------------------------------------------
_REASON_INPUT = {"FAMILY_UNUSABLE:price_structure": "in_price", "FAMILY_UNUSABLE:oi": "in_oi",
                 "FAMILY_UNUSABLE:volume": "in_volume", "INGESTION_HEARTBEAT_UNHEALTHY": "in_feed",
                 "MATERIALIZATION_FAILED": "in_calc", "STALE_COHERENCE_BARRIER": "in_calc",
                 "EVALUATION_NOT_FRESH": "in_calc"}
_PARTIAL_FAMILY = {"in_price": "range_width_pct_median", "in_volume": "volume_notional_usd_sum"}


def _partial(f) -> list:
    """The degraded inputs as phrase keys, in a fixed order, from view.status_reasons."""
    keys = {_REASON_INPUT[r] for r in f.get("status_reasons") or () if r in _REASON_INPUT}
    return [k for k in ("in_price", "in_oi", "in_volume", "in_feed", "in_calc") if k in keys] or ["in_any"]


def _inputs(f, lang: str) -> str:
    return ", ".join(text(k, lang) for k in _partial(f))


def _degraded(f) -> bool:
    return "stale" in sel.salient(f) and not sel.stale_only(f)


def _weekend(f) -> bool:
    if not f.get("data_through"):
        return False
    from beta.i18n import local
    return local(datetime.fromisoformat(f["data_through"].replace("Z", "+00:00"))).weekday() >= 5


def _band(f, metric: str) -> Optional[str]:
    """'low' | 'usual' | None (unknown, or a family the degraded status names as partial)."""
    if _degraded(f) and metric in {_PARTIAL_FAMILY.get(k) for k in _partial(f)} | (
            {"range_width_pct_median", "volume_notional_usd_sum"} if "in_any" in _partial(f) else set()):
        return None
    if sel.low_band(f, metric):
        return "low"
    lab = sel._label(f, metric)
    return "usual" if lab in ("normal", "elevated") else None


def _calm_lines(f, lang: str) -> list:
    """The calm family: one sentence with the hour's move and the range / volume bands it can name."""
    pct = (f.get("h1") or {}).get("price_move_pct")
    if pct is None:
        return [text("st_calm_noprice", lang)]
    rng, vol = _band(f, "range_width_pct_median"), _band(f, "volume_notional_usd_sum")
    head = "st_calm_head_weekend" if _weekend(f) else ("st_calm_head_low" if "low" in (rng, vol) else "st_calm_head")
    frag = [text("st_calm_move", lang, pct=spct(pct, lang))]
    if rng == "usual" and vol == "usual":
        frag.append(text("calm_both_usual", lang))
    else:
        frag += [text(k, lang) for k, on in (("calm_range_low", rng == "low"), ("calm_range_usual", rng == "usual"),
                                             ("calm_volume_low", vol == "low"), ("calm_volume_usual", vol == "usual"))
                 if on]
    return [text(head, lang) + " " + _sentence(frag)]


def _l1_header(f, lang: str) -> str:
    if sel.stale_only(f):
        return text("hdr_btc_bare", lang)
    when = clock(f["data_through"]) if f.get("data_through") else "—"
    if f.get("price") is not None:
        return text("hdr_btc", lang, price=price(f["price"], lang), clock=when)
    return text("hdr_btc_na", lang, clock=when)


def _state_lines(keys, f, lang: str) -> list:
    """The state line (with its number) and one context sentence, from facts only."""
    h1 = f.get("h1") or {}
    pct = h1.get("price_move_pct")
    if "stale" in keys and sel.stale_only(f):
        if f.get("data_through"):
            return [text("st_stale", lang, clock=clock(f["data_through"]))]
        return [text("st_stale_never", lang)]
    pre = [text("st_degraded", lang, inputs=_inputs(f, lang))] if "stale" in keys else []
    keys = [k for k in keys if k != "stale"] or ["nothing"]
    active = [k for k in keys if k in _ACTIVE]
    if active:
        emoji = "⚡" if ("episode" in keys or "range_extreme" in keys) or pct is None else ("📈" if pct >= 0 else "📉")
        lines = [text("st_move", lang, emoji=emoji, pct=spct(pct, lang)) if pct is not None else text("nt_hour_any", lang)]
        frag = []
        if "episode" in keys:
            frag.append(text("cx_episode", lang, name=episode_name(f["episode"]["event_type"], lang)))
        for k in ("range_extreme", "range_high", "volume_high", "corridor_edge"):
            if k in keys:
                frag.append(text("cx_" + k, lang))
        if frag:
            lines.append(_sentence(frag))
        return pre + lines
    if "level_at" in keys:
        z = f["levels"]["at"]
        lines = [text("st_level", lang, name=level_name(z["members"][0], lang), edge=price(z["edge"], lang))]
    elif keys == ["nothing"]:
        return pre + _calm_lines(f, lang)
    else:
        lines = [text("st_quiet", lang, pct=spct(pct, lang))] if pct is not None else [text("st_calm_noprice", lang)]
    if "corridor_edge" in keys:
        lines.append(_sentence([text("cx_corridor_edge", lang)]))
    return pre + lines


def _window_line(f, lang: str) -> Optional[str]:
    w = f.get("window") or {}
    if not (w.get("window_start") and w.get("window_end") and w.get("price_move_pct") is not None
            and w.get("low") is not None and w.get("high") is not None and f.get("window_hours")):
        return None
    return text("win_line", lang, hours=int(f["window_hours"]), start=clock(w["window_start"]),
                end=clock(w["window_end"]), pct=spct(w["price_move_pct"], lang), low=price(w["low"], lang),
                high=price(w["high"], lang))


def _btc_l1(f, lang: str) -> str:
    keys = sel.salient(f)
    blocks = [[H(_l1_header(f, lang))], _state_lines(keys, f, lang)]
    if sel.stale_only(f):
        return _join(blocks)
    win = _window_line(f, lang)
    if win:
        blocks.append([win])
    near = _nearest(f, NEAR_MAX)
    if near:
        blocks.append([H(text("near_hdr", lang))] + [_level_line("near_line", z, f, lang) for z in near])
    ev = sel.next_event(f)
    if ev:
        blocks.append([text("ev_today", lang, clock=clock(ev["at"]), event=_event_name(ev["kind"], lang))])
    return _join(blocks)


# ---- /btc L2 -------------------------------------------------------------------------------------
def _now_lines(keys, f, lang: str) -> list:
    out = []
    for k in keys:
        if k == "stale":
            out.append(text("now_stale", lang) if sel.stale_only(f) else
                       text("now_degraded", lang, inputs=_inputs(f, lang)))
        elif k == "episode":
            out.append(text("ep_" + EPISODES[f["episode"]["event_type"]], lang))
        elif k == "level_at":
            z = f["levels"]["at"]
            out.append(text("now_level_at", lang, name=level_name(z["members"][0], lang), edge=price(z["edge"], lang)))
        elif k in ("range_extreme", "range_high", "volume_high", "corridor_edge"):
            out.append(text("now_" + k, lang))
        elif k == "event_today":
            e = sel.next_event(f)
            out.append(text("now_event", lang, clock=clock(e["at"]), event=_event_name(e["kind"], lang)))
        elif k == "nothing":
            out += _calm_now(f, lang)
    if keys and keys[0] == "stale" and not sel.stale_only(f) and len(keys) == 1:
        out += _calm_now(f, lang)
    return out


def _calm_now(f, lang: str) -> list:
    rng, vol = _band(f, "range_width_pct_median"), _band(f, "volume_notional_usd_sum")
    if rng == "usual" and vol == "usual":
        return [text("now_calm", lang)]
    out = [text(k, lang) for k, on in (("now_range_low", rng == "low"), ("now_volume_low", vol == "low")) if on]
    return out or ([] if _degraded(f) else [text("now_calm_young", lang)])


def _hist_verdict(z, f, lang: str) -> Optional[str]:
    hist = z.get("history") or {}
    verdict = (hist.get("verdicts") or {}).get("1h")
    if not verdict:
        return None
    name = level_name(z["members"][0], lang)
    side = text("side_above" if _side(z, f) > 0 else "side_below", lang)
    if verdict == "insufficient":
        return text("hist_few", lang, name=name)
    if verdict == "as_usual":
        return text("hist_same", lang, name=name, side=side)
    real = ((hist.get("real") or {}).get("1h") or {}).get("hold_rate")
    ctrl = ((hist.get("control") or {}).get("1h") or {}).get("hold_rate")
    if real is None or ctrl is None or real == ctrl:
        return None
    return text("hist_more" if real > ctrl else "hist_less", lang, name=name, side=side)


def _btc_l2(f, lang: str) -> str:
    keys = sel.salient(f)
    blocks = [[H(text("hdr_why", lang))], [H(text("b_now", lang))] + _now_lines(keys, f, lang)]
    hist = [x for x in (_hist_verdict(z, f, lang) for z in _nearest(f, NEAR_MAX)) if x]
    if hist and not sel.stale_only(f):
        blocks.append([H(text("b_hist", lang))] + hist)
    if any(k in keys for k in ("episode", "range_extreme", "range_high", "volume_high", "level_at")):
        blocks.append([H(text("b_not", lang)), text("not_forecast", lang)])
    return _join(blocks)


# ---- /btc L3 -------------------------------------------------------------------------------------
def _btc_l3(f, lang: str) -> str:
    if sel.stale_only(f):                    # late data: nothing current, not even the last hour's numbers
        return _join([[H(text("hdr_data", lang))], _state_lines(["stale"], f, lang)])
    part = set(_partial(f)) if _degraded(f) else set()
    h1, h24 = f.get("h1") or {}, f.get("h24") or {}
    base, days = h1.get("baseline_median") or {}, h1.get("baseline_days") or {}
    g_price = []
    if "in_price" in part:
        h1 = {k: v for k, v in h1.items() if k not in ("price_move_pct", "range_width_pct")}
        h24 = {}
    if "in_volume" in part:
        h1 = {k: v for k, v in h1.items() if k != "volume_notional_usd"}
    if "in_oi" in part:
        h1 = {k: v for k, v in h1.items() if k != "oi_change_pct"}
    if h1.get("price_move_pct") is not None:
        g_price.append(text("l3_price_1h", lang, pct=spct(h1["price_move_pct"], lang)))
    if h1.get("range_width_pct") is not None and base.get("range_width_pct_median") is not None:
        g_price.append(text("l3_range_1h", lang, val=ppct(h1["range_width_pct"], lang),
                            base=ppct(base["range_width_pct_median"], lang),
                            n=int(days.get("range_width_pct_median") or 0)))
    if h24.get("price_complete") and h24.get("high") is not None and h24.get("low") is not None:
        g_price.append(text("l3_hilo_24h", lang, high=price(h24["high"], lang), low=price(h24["low"], lang)))
    c = f.get("corridor_24h") or {}
    if c.get("lower") is not None and c.get("upper") is not None and "in_price" not in part:
        g_price.append(text("l3_corridor", lang, lower=price(c["lower"], lang), upper=price(c["upper"], lang)))
    g_flow = []
    if h1.get("volume_notional_usd") is not None and base.get("volume_notional_usd_sum") is not None:
        g_flow.append(text("l3_volume_1h", lang, val=usd(h1["volume_notional_usd"], lang),
                           base=usd(base["volume_notional_usd_sum"], lang),
                           n=int(days.get("volume_notional_usd_sum") or 0)))
    oi = h1.get("oi_change_pct")
    if oi:
        g_flow.append(text("l3_oi_down" if oi < 0 else "l3_oi_up", lang, pct=spct(oi, lang)))
    delta = h1.get("taker_delta_notional_usd_sum")
    if delta:
        g_flow.append(text("l3_buys" if delta > 0 else "l3_sells", lang, usd=usd(delta, lang)))
    lv = f.get("levels") or {}
    g_levels = [_level_line("l3_level", z, f, lang)
                for z in [z for z in (lv.get("above") or ()) if z] + [z for z in (lv.get("below") or ()) if z]]
    g_hist = []
    from beta.decision_format import _hist_lines
    for z in _nearest(f, NEAR_MAX):
        for line in _hist_lines(z.get("history"), lang, _side(z, f), "levels")[:1]:
            name = level_name(z["members"][0], lang)
            g_hist.append(text("l3_hist", lang, name=name[:1].upper() + name[1:], line=line.lstrip("↳ ").strip()))
    blocks = [[H(text("hdr_data", lang))]]
    if part:
        blocks.append([text("st_degraded", lang, inputs=_inputs(f, lang))])
    if g_price:
        blocks.append([H(text("g_price", lang))] + g_price)
    if g_flow:
        blocks.append([H(text("g_flow", lang))] + g_flow)
    if g_levels:
        blocks.append([H(text("g_levels", lang))] + g_levels)
    if g_hist:
        blocks.append([H(text("g_hist", lang))] + g_hist)
    return _join(blocks)


def _btc(level: int, lang: str, f) -> tuple:
    if level == 1:
        return _btc_l1(f, lang), [[(text("btn_why", lang), callback("btc", 2)), (text("btn_data", lang), callback("btc", 3))],
                                  [(text("btn_levels", lang), callback("levels", 1))]]
    if level == 2:
        return _btc_l2(f, lang), [[(text("btn_data", lang), callback("btc", 3)), (text("btn_back", lang), callback("btc", 1))]]
    return _btc_l3(f, lang), [[(text("btn_back", lang), callback("btc", 1))]]


# ---- levels ----------------------------------------------------------------------------------------
def card_zone(f: Mapping[str, Any]):
    """The card's level: `zone` when given, else the view's level at the price, else the nearest level of
    either side (by |distance|); None when there is none."""
    if f.get("zone"):
        return f["zone"]
    lv = f.get("levels") or {}
    if lv.get("at"):
        return lv["at"]
    near = [z for z in list(lv.get("above") or ()) + list(lv.get("below") or ()) if z and z.get("distance_pct") is not None]
    return min(near, key=lambda z: abs(float(z["distance_pct"]))) if near else None


def _levels(lang: str, f) -> tuple:
    lv = f.get("levels") or {}
    zones = [z for z in lv.get("above") or () if z] + [z for z in lv.get("below") or () if z]
    blocks = [[H(text("hdr_levels", lang))]]
    blocks.append([_level_line("l3_level", z, f, lang) for z in zones] or [text("lv_none", lang)])
    return _join(blocks), [[(text("btn_back", lang), callback("btc", 1))]]


def _level_card(lang: str, f) -> tuple:
    back = [[(text("btn_back", lang), callback("levels", 1))]]
    z = card_zone(f)
    if z is None or not z.get("members"):
        return _join([[H(text("hdr_levels", lang))], [text("lv_none", lang)]]), back
    blocks = [[H("🎯 " + level_name(z["members"][0], lang) + " " + price(z["edge"], lang))],
              [_level_line("l3_level", z, f, lang)]]
    v = _hist_verdict(z, f, lang)
    if v:
        blocks.append([v])
    return _join(blocks), back


# ---- notifications: one headline with its number, one sentence, the time window ---------------------
def _hour(lang: str, f) -> tuple:
    pct = f.get("price_move_pct")
    head = (text("nt_hour", lang, emoji="📈" if pct >= 0 else "📉", pct=spct(pct, lang)) if pct is not None
            else text("nt_hour_any", lang))
    frag = [text(k, lang) for k, on in (("cx_range_high", (f.get("passed") or {}).get("range")),
                                         ("cx_volume_high", (f.get("passed") or {}).get("volume"))) if on]
    body = [text("nt_hour_why", lang, what=_sentence(frag)[:-1])] if frag else []
    window = [text("nt_window", lang, start=clock(f["window_start"]), end=clock(f["window_end"]))]
    return _join([[H(head)], body + window]), [[(text("btn_why", lang), callback("btc", 2))]]


def _level_alert(lang: str, f) -> tuple:
    name = level_name(f["member"], lang)
    period = text("period_" + f["period"], lang) if f.get("period") in ("day", "week", "month") else None
    body = [text("nt_level_why", lang, period=period, price=price(f["price"], lang))] if period else []
    return (_join([[H(text("nt_level", lang, name=name, level=price(f["level"], lang)))],
                   body + [text("nt_at", lang, clock=clock(f["at"]))]]),
            [[(text("btn_levels", lang), callback("levels", 1))]])


def _move(lang: str, f) -> tuple:
    return (_join([[H(text("nt_move", lang, pct=spct(f["move_pct"], lang)))],
                   [text("nt_move_why", lang, open=price(f["open"], lang), close=price(f["close"], lang)),
                    text("nt_move_rule", lang),
                    text("nt_window", lang, start=clock(f["start"]), end=clock(f["at"]))]]),
            [[(text("btn_levels", lang), callback("levels", 1))]])


def _brief(lang: str, f) -> tuple:
    hours = int(f.get("window_hours") or 8)
    w = f.get("window") or {}
    pct = w.get("price_move_pct")
    head = text("nt_brief", lang, hours=hours, pct=spct(pct, lang)) if pct is not None else \
        text("nt_brief", lang, hours=hours, pct="—")
    keys = sel.salient(f)
    frag = []
    if "episode" in keys:
        frag.append(text("cx_episode", lang, name=episode_name(f["episode"]["event_type"], lang)))
    frag += [text("cx_" + k, lang) for k in ("range_extreme", "range_high", "volume_high", "corridor_edge") if k in keys]
    body = [_sentence(frag)] if frag else []
    if w.get("low") is not None and w.get("high") is not None:
        body.append(text("nt_brief_range", lang, low=price(w["low"], lang), high=price(w["high"], lang)))
    if w.get("window_start") and w.get("window_end"):
        body.append(text("nt_window", lang, start=clock(w["window_start"]), end=clock(w["window_end"])))
    else:
        body = [text("nt_brief_none", lang)] + body
        if f.get("data_through"):
            body.append(text("nt_at", lang, clock=clock(f["data_through"])))
    return (_join([[H(head)], body]),
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
