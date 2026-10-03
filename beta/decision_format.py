"""Rendering of decision support (PRODUCT_DECISION_V2). Language-neutral blocks in, HTML out.

Every string comes from the catalog (`beta.i18n` / `beta.i18n_decision`) and every rendered
text passes `assert_descriptive` (no direct trade calls, no hype).
"""
from __future__ import annotations

import html
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from .i18n import (assert_descriptive, fmt_clock, fmt_kyiv_hm, fmt_plain_pct, fmt_price, fmt_signed_pct,
                   fmt_usd, kyiv, na, t)
from .i18n_decision import EVENT_NAMES, LEVEL_NAMES, WEEKDAYS, cases_word

_LANG_IX = {"ru": 0, "en": 1}
ANALOG_MIN_N = 30


def _ix(lang: str) -> int:
    return _LANG_IX.get(lang, 0)


def _e(s: Any) -> str:
    return html.escape(str(s), quote=False)


def fmt_prob(p: Optional[float], lang: str) -> str:
    if p is None:
        return na(lang)
    if p < 0.01:
        return "&lt;1%"                                    # Telegram HTML: never a raw "<"
    if p > 0.99:
        return "&gt;99%"
    return f"{round(p * 100):d}%"


def fmt_share(p: Optional[float], lang: str) -> str:
    """A realized share (history, accuracy): exact percent, never clamped like a forecast."""
    return na(lang) if p is None else f"{round(p * 100):d}%"


def _x(v: Optional[float], lang: str) -> str:
    if v is None:
        return na(lang)
    s = f"{float(v):.1f}"
    return s.replace(".", ",") if lang == "ru" else s


def _pct(v: float, lang: str, nd: int = 2) -> str:
    return fmt_plain_pct(abs(float(v)), lang, nd=nd)


def _hz(h: str, lang: str) -> str:
    return t(lang, "hz_" + h)


def _n(n: int, lang: str, since_year: Optional[int] = None) -> str:
    base = t(lang, "n_cases", n=int(n), word=cases_word(int(n), lang))
    return base + (" " + t(lang, "since_year", year=since_year) if since_year else "")


def level_name(member: Mapping[str, Any], lang: str) -> str:
    kind = member["kind"]
    if kind == "ROUND" and member.get("major"):
        kind = "ROUND_MAJOR"
    pair = LEVEL_NAMES.get(kind)
    if pair is None:
        return kind
    name = pair[_ix(lang)]
    if "{usd}" in name:
        name = name.format(usd=fmt_usd(float(member.get("notional_usd") or 0.0), lang))
    return name


def zone_names(zone: Mapping[str, Any], lang: str, limit: int = 2) -> str:
    seen, out = set(), []
    for m in zone.get("members") or ():
        name = level_name(m, lang)
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= limit:
            break
    return ", ".join(out)


def zone_price(zone: Mapping[str, Any], lang: str) -> str:
    lo, hi = float(zone["low"]), float(zone["high"])
    if hi - lo <= max(1.0, lo * 0.0005):
        return fmt_price(zone["edge"], lang)
    return f"{fmt_price(lo, lang)}–{fmt_price(hi, lang)}"


def _since_year(block: Mapping[str, Any]) -> Optional[int]:
    ms = ((block.get("stats") or {}).get("data_from_ms"))
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).year if ms else None


# ---- blocks shared by the briefing, /catchup and /btc ---------------------------------------
def unavailable_line(block: Optional[Mapping[str, Any]], lang: str) -> Optional[str]:
    if block is None:
        return None
    if block.get("available"):
        return None
    reason = {"DATA_STALE": "dc_reason_stale", "ERROR": "dc_reason_error"}.get(block.get("reason"),
                                                                               "dc_reason_no_stats")
    return t(lang, "dc_unavailable", reason=t(lang, reason))


def zone_note(zones: Optional[Mapping[str, Any]], horizons: Sequence[str], lang: str) -> Optional[str]:
    """Why a horizon shows no number: the scheduled release(s) whose event zone holds now
    (BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §9). None outside every zone."""
    zones = zones or {}
    hs = [h for h in horizons if zones.get(h)]
    if not hs:
        return None
    seen, events = set(), []
    for h in hs:
        for e in zones[h]:
            if (e["kind"], e["at"]) not in seen:
                seen.add((e["kind"], e["at"]))
                events.append(e)
    events.sort(key=lambda e: e["at"])
    parts = [t(lang, "ez_event", name=_e(EVENT_NAMES.get(e["kind"], (e["kind"], e["kind"]))[_ix(lang)]),
               when=_when(datetime.fromisoformat(e["at"]), lang, with_day=True)) for e in events]
    return t(lang, "ez_note", hs=", ".join(_hz(h, lang) for h in hs), events="; ".join(parts))


def corridor_lines(block: Mapping[str, Any], lang: str, horizons: Sequence[str] = ("4h", "24h")) -> list:
    c = block.get("corridor") or {}
    hz = c.get("horizons") or {}
    parts = []
    for h in horizons:
        x = hz.get(h)
        if not x:
            continue
        parts.append(t(lang, "dc_corridor_part", h=_hz(h, lang), low=fmt_price(x["lower"], lang),
                       high=fmt_price(x["upper"], lang), half=_pct(x["half_width_pct"], lang, 1)))
    note = zone_note(block.get("event_zone"), horizons, lang)
    if note:                      # an event context: no coverage claim in the header
        return [t(lang, "dc_corridor_head_event")] + ([" · ".join(parts)] if parts else []) + [note]
    if not parts:
        return []
    return [t(lang, "dc_corridor_head"), " · ".join(parts)]


def _level_line(zone: Mapping[str, Any], lang: str, arrow: str, *, with_p: bool = True) -> str:
    if not with_p:
        return t(lang, "dc_level_line_nop", arrow=arrow, price=zone_price(zone, lang),
                 name=_e(zone_names(zone, lang)), dist=fmt_signed_pct(zone["distance_pct"], lang))
    p = (zone.get("touch") or {}).get("24h")
    return t(lang, "dc_level_line", arrow=arrow, price=zone_price(zone, lang), name=_e(zone_names(zone, lang)),
             dist=fmt_signed_pct(zone["distance_pct"], lang), p=fmt_prob(p, lang))


def _brief_pick(zones: Sequence[Mapping[str, Any]], n: int) -> list:
    """The nearest zone and the most important of the others (zones arrive nearest first)."""
    from .levels import LEVEL_ORDER
    if len(zones) <= n:
        return list(zones)

    def rank(z):
        return min((LEVEL_ORDER.index(k) if k in LEVEL_ORDER else 99) for k in z.get("kinds") or ["?"])
    rest = sorted(zones[1:], key=rank)[: n - 1]
    return sorted([zones[0], *rest], key=lambda z: abs(z["distance_pct"]))


def levels_lines(block: Mapping[str, Any], lang: str, each_side: int = 2) -> list:
    lv = block.get("levels") or {}
    above = _brief_pick(lv.get("above") or [], each_side)
    below = _brief_pick(lv.get("below") or [], each_side)
    at = lv.get("at")
    if not (above or below or at):
        return []
    with_p = not (block.get("event_zone") or {}).get("24h")     # 24h touch chances are withheld in its zone
    lines = [t(lang, "dc_levels_head" if with_p else "dc_levels_head_plain")]
    lines.extend(_level_line(z, lang, "↑", with_p=with_p) for z in reversed(above))
    if at:
        lines.append(t(lang, "dc_level_at", price=zone_price(at, lang), name=_e(zone_names(at, lang))))
    elif block.get("price") is not None:
        lines.append(t(lang, "dc_level_now", price=fmt_price(block["price"], lang)))
    lines.extend(_level_line(z, lang, "↓", with_p=with_p) for z in below)
    return lines


def _when(at: datetime, lang: str, *, with_day: bool) -> str:
    local = kyiv(at)
    hm = local.strftime("%H:%M")
    if not with_day:
        return hm
    return f"{WEEKDAYS[lang if lang in WEEKDAYS else 'ru'][local.weekday()]} {local.strftime('%d.%m')} {hm}"


def event_lines(events: Sequence[Mapping[str, Any]], lang: str, *, with_day: bool = False) -> list:
    out = []
    for e in events:
        at = datetime.fromisoformat(e["at"]) if isinstance(e["at"], str) else e["at"]
        name = EVENT_NAMES.get(e["kind"], (e["kind"], e["kind"]))[_ix(lang)]
        out.append(t(lang, "dc_event_line", when=_when(at, lang, with_day=with_day), name=_e(name)))
    return out


def _event_contexts(kinds: Iterable[str]) -> list:
    """Research contexts for listed events. CPI/FOMC get none: around a release the bot shows no size or
    multiplier at all (design record §9), so a registry line such as D11's never rides on those surfaces."""
    from .rangecast import EVENT_KINDS
    return [f"event:{k}" for k in kinds if k not in EVENT_KINDS]


def event_note(events: Sequence[Mapping[str, Any]], lang: str) -> Optional[str]:
    """The neutral warning for listed CPI/FOMC releases: no size, no share, no direction (event-zone kinds only)."""
    from .rangecast import EVENT_KINDS
    kinds = [k for k in EVENT_KINDS if any(e["kind"] == k for e in events)]
    if not kinds:
        return None
    names = ", ".join(_e(EVENT_NAMES.get(k, (k, k))[_ix(lang)]) for k in kinds)
    return t(lang, "ev_release_note", names=names)


def research_line(contexts: Sequence[str], lang: str) -> Optional[str]:
    """One «Проверено: …» line from the research registry, or None (the registry is optional)."""
    try:
        from .research_link import context_line
        return context_line(contexts, lang)
    except Exception:  # noqa: BLE001 - never let the registry break a message
        return None


def today_lines(block: Mapping[str, Any], lang: str) -> list:
    evs = block.get("events")
    if evs is None:
        return []
    out = [t(lang, "dc_today_head")] + (event_lines(evs, lang) or [t(lang, "dc_no_events")])
    note = event_note(evs, lang)
    if note:
        out.append(note)
    contexts = _event_contexts(e["kind"] for e in evs) + (["weekend"] if block.get("weekend") else [])
    line = research_line(contexts, lang)
    if line:
        out.append(line)
    return out


def analog_line(card: Optional[Mapping[str, Any]], lang: str, *, since_year: Optional[int] = None) -> Optional[str]:
    """One line of «что было после похожих» for a window's own horizon (1h → 1h, 4h → 4h)."""
    if not card:
        return None
    h = card["window"]
    cell = (card.get("outcomes") or {}).get(h) or {}
    n = int(cell.get("n") or 0)
    if n < ANALOG_MIN_N or not cell.get("baseline"):
        return t(lang, "dc_analog_short", n=_n(n, lang))
    v = cell.get("verdicts") or {}
    base = cell["baseline"]
    if v.get("direction") == "differs":
        dir_v = t(lang, "dc_dir_higher" if cell["p_up"] > base["p_up"] else "dc_dir_lower")
    elif v.get("direction") == "as_usual":
        dir_v = t(lang, "dc_dir_as_usual")
    else:
        dir_v = t(lang, "dc_insufficient")
    ratio = cell.get("range_ratio")
    if v.get("range") == "differs" and ratio is not None:
        rng_v = t(lang, "dc_range_bigger" if ratio > 1 else "dc_range_smaller")
    elif v.get("range") == "as_usual":
        rng_v = t(lang, "dc_range_as_usual")
    else:
        rng_v = t(lang, "dc_insufficient")
    return t(lang, "dc_analog_line", n=_n(n, lang, since_year), h=_hz(h, lang), p_up=fmt_share(cell["p_up"], lang),
             base_up=fmt_share(base["p_up"], lang), dir_verdict=dir_v, ratio=_x(ratio, lang), range_verdict=rng_v)


def brief_lines(view: Mapping[str, Any], lang: str) -> list:
    """Corridor, levels and today's events for the briefing and /catchup (after «Сейчас»)."""
    block = view.get("decision")
    if not block:
        return []
    gone = unavailable_line(block, lang)
    if gone:
        return ["", gone]
    out = []
    for part in (corridor_lines(block, lang), levels_lines(block, lang), today_lines(block, lang)):
        if part:
            out.append("")
            out.extend(part)
    return out


def btc_lines(view: Mapping[str, Any], lang: str) -> list:
    block = view.get("decision") or {}
    if not block.get("available"):
        return []
    out = []
    x = ((block.get("corridor") or {}).get("horizons") or {}).get("4h")
    note = zone_note(block.get("event_zone"), ["4h"], lang)
    if note:
        out.append(note)
    elif x:
        out.append(t(lang, "dc_btc_corridor", low=fmt_price(x["lower"], lang), high=fmt_price(x["upper"], lang),
                     half=_pct(x["half_width_pct"], lang, 1)))
    lv = block.get("levels") or {}
    parts = []
    for z, arrow in (((lv.get("above") or [None])[0], "↑"), ((lv.get("below") or [None])[0], "↓")):
        if z:
            parts.append(t(lang, "dc_btc_level_part", arrow=arrow, price=zone_price(z, lang),
                           name=_e(zone_names(z, lang, limit=1)), dist=fmt_signed_pct(z["distance_pct"], lang)))
    if parts:
        out.append(t(lang, "dc_btc_levels", parts=" · ".join(parts)))
    return out


# ---- /levels -----------------------------------------------------------------------------
def _hist_lines(hist: Optional[Mapping[str, Any]], lang: str, side: int) -> list:
    if not hist or not hist.get("real"):
        return []
    real, ctrl = hist["real"], hist.get("control") or {}
    r1, c1 = real.get("1h"), ctrl.get("1h")
    if not r1 or not c1 or not real.get("n"):
        return []
    verdict = (hist.get("verdicts") or {}).get("1h", "insufficient")
    if verdict == "differs":
        vk = "lv_verdict_differs_more" if r1["hold_rate"] > c1["hold_rate"] else "lv_verdict_differs_less"
    else:
        vk = "lv_verdict_" + verdict
    return [t(lang, "lv_hist", n=_n(real["n"], lang), side=t(lang, "lv_side_above" if side > 0 else "lv_side_below"),
              hold=fmt_share(r1["hold_rate"], lang), ctrl=fmt_share(c1["hold_rate"], lang), verdict=t(lang, vk)),
            t(lang, "lv_hist_move", further=_pct(r1["further_median"], lang), back=_pct(r1["back_median"], lang))]


def _zone_block(z: Mapping[str, Any], lang: str, side: int) -> list:
    lines = [t(lang, "lv_zone", price=zone_price(z, lang), names=_e(zone_names(z, lang, limit=3)),
               dist=fmt_signed_pct(z["distance_pct"], lang))]
    touch = z.get("touch") or {}
    if "4h" in touch and "24h" in touch:
        lines.append(t(lang, "lv_touch", p4=fmt_prob(touch["4h"], lang), p24=fmt_prob(touch["24h"], lang)))
    elif "4h" in touch:
        lines.append(t(lang, "lv_touch_4h", p4=fmt_prob(touch["4h"], lang)))
    elif "24h" in touch:
        lines.append(t(lang, "lv_touch_24h", p24=fmt_prob(touch["24h"], lang)))
    lines.extend(_hist_lines(z.get("history"), lang, side))
    return lines


def format_levels(block: Mapping[str, Any], lang: str, *, now: datetime) -> str:
    gone = unavailable_line(block, lang)
    if gone:
        return assert_descriptive(gone, lang)
    lv = block.get("levels") or {}
    lines = [t(lang, "lv_title", price=fmt_price(block["price"], lang), clock=fmt_clock(now, lang))]
    if lv.get("at"):
        lines.append(t(lang, "dc_level_at", price=zone_price(lv["at"], lang), name=_e(zone_names(lv["at"], lang))))
    lines.append("")
    lines.append(t(lang, "lv_above"))
    above = lv.get("above") or []
    for z in above:
        lines.extend(_zone_block(z, lang, +1))
    if not above:
        lines.append(t(lang, "lv_none"))
    lines.append("")
    lines.append(t(lang, "lv_below"))
    below = lv.get("below") or []
    for z in below:
        lines.extend(_zone_block(z, lang, -1))
    if not below:
        lines.append(t(lang, "lv_none"))
    x = ((block.get("corridor") or {}).get("horizons") or {}).get("24h")
    note = zone_note(block.get("event_zone"), ["4h", "24h"], lang)
    if x or note:
        lines.append("")
    if x:
        lines.append(t(lang, "lv_corridor", low=fmt_price(x["lower"], lang), high=fmt_price(x["upper"], lang)))
    if note:
        lines.append(note)
    lines.append(t(lang, "lv_footer"))
    return assert_descriptive("\n".join(lines), lang)


# ---- /risk -------------------------------------------------------------------------------
def parse_risk_arg(args: Optional[str], price: Optional[float]) -> tuple:
    """('pct', value) / ('table', None) / ('bad', None). A value >= 100 is a stop price."""
    text = (args or "").strip().replace(",", ".").rstrip("%").strip()
    if not text:
        return "table", None
    try:
        v = float(text)
    except ValueError:
        return "bad", None
    if not math.isfinite(v):
        return "bad", None
    if v >= 100:
        if not price:
            return "bad", None
        pct = abs(price - v) / price * 100.0
        return ("pct", pct) if 0.01 <= pct <= 30 else ("bad", None)
    return ("pct", v) if 0.01 <= v <= 30 else ("bad", None)


def format_risk(block: Mapping[str, Any], model: Optional[Mapping[str, Any]], lang: str, *,
                stop_pct: Optional[float]) -> str:
    from .rangecast import touch_probability
    gone = unavailable_line(block, lang)
    if gone or model is None:
        return assert_descriptive(gone or t(lang, "dc_unavailable", reason=t(lang, "dc_reason_no_stats")), lang)
    hz = (block.get("corridor") or {}).get("horizons") or {}
    price = float(block["price"])
    lines = [t(lang, "rk_title", price=fmt_price(price, lang))]

    zones = block.get("event_zone") or {}

    def prob(h, pct):
        x = hz.get(h)
        return None if not x else touch_probability(model, h, x["scale_pct"], pct)

    def cell(h, pct):
        return "—" if zones.get(h) else fmt_prob(prob(h, pct), lang)     # withheld in its event zone

    if stop_pct is not None:
        lines.append(t(lang, "rk_stop", pct=_pct(stop_pct, lang), usd=fmt_usd(price * stop_pct / 100.0, lang)))
        for h in ("1h", "4h", "24h"):
            lines.append(t(lang, "rk_line_zone", h=_hz(h, lang)) if zones.get(h)
                         else t(lang, "rk_line", h=_hz(h, lang), p=fmt_prob(prob(h, stop_pct), lang)))
    else:
        lines.append(t(lang, "rk_table_head"))
        for pct in (0.25, 0.5, 1.0, 2.0):
            lines.append(t(lang, "rk_table_line", pct=_pct(pct, lang), p1=cell("1h", pct),
                           p4=cell("4h", pct), p24=cell("24h", pct)))
    note = zone_note(zones, ["1h", "4h", "24h"], lang)
    if note:
        lines.append(note)
    if all(hz.get(h) for h in ("1h", "4h", "24h")):
        lines.append(t(lang, "rk_typical", h1=_pct(hz["1h"]["typical_move_pct"], lang),
                       h4=_pct(hz["4h"]["typical_move_pct"], lang), h24=_pct(hz["24h"]["typical_move_pct"], lang)))
    lines.append(t(lang, "rk_note"))
    checked = research_line(["corridor"], lang)
    if checked:
        lines.append(checked)
    if stop_pct is None:
        lines.append(t(lang, "rk_usage"))
    return assert_descriptive("\n".join(lines), lang)


# ---- /events -----------------------------------------------------------------------------
def format_events(events: Sequence[Mapping[str, Any]], lang: str, *, funding_utc: Sequence[str] = ()) -> str:
    lines = [t(lang, "ev_title")]
    body = event_lines(events, lang, with_day=True)
    lines.extend(body or [t(lang, "ev_none")])
    if funding_utc:
        today = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        times = []
        for s in funding_utc:
            hh, mm = (int(x) for x in str(s).split(":"))
            times.append(fmt_kyiv_hm(today.replace(hour=hh, minute=mm)))
        lines.append(t(lang, "ev_funding", times=", ".join(sorted(times))))
    note = event_note(events, lang)
    if note:
        lines.append(note)
    return assert_descriptive("\n".join(lines), lang)


# ---- /accuracy ---------------------------------------------------------------------------
def format_accuracy(model: Optional[Mapping[str, Any]], live: Mapping[str, Mapping[str, int]], lang: str) -> str:
    lines = [t(lang, "ac_title")]
    cal = (model or {}).get("calibration") or {}
    if cal:
        parts, period = [], ""
        for h in ("1h", "4h", "24h"):
            c = cal.get(h)
            if not c:
                continue
            parts.append(t(lang, "ac_part", h=_hz(h, lang), p=fmt_share(c.get("coverage_realized"), lang)))
            if c.get("holdout_from_ms") and c.get("holdout_to_ms"):
                a = datetime.fromtimestamp(c["holdout_from_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m")
                z = datetime.fromtimestamp(c["holdout_to_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m")
                period = f"{a} – {z}"
        lines.append(t(lang, "ac_holdout", period=period, parts=", ".join(parts)))
    parts = []
    for h in ("1h", "4h", "24h"):
        rec = live.get(h) or {}
        n = int(rec.get("INSIDE", 0)) + int(rec.get("OUTSIDE", 0))
        if n:
            parts.append(t(lang, "ac_part_live", h=_hz(h, lang), p=fmt_share(rec.get("INSIDE", 0) / n, lang), n=n))
    lines.append(t(lang, "ac_live", parts=", ".join(parts)) if parts else t(lang, "ac_live_none"))
    return assert_descriptive("\n".join(lines), lang)


# ---- pushes --------------------------------------------------------------------------------
def _corridor_line(c: Optional[Mapping[str, Any]], key: str, lang: str) -> Optional[str]:
    if not c:
        return None
    return t(lang, key, low=fmt_price(c["lower"], lang), high=fmt_price(c["upper"], lang),
             half=_pct(c["half_width_pct"], lang, 1))


ALERT_MAX_LINES = 8


def format_alert(kind: str, payload: Mapping[str, Any], lang: str) -> str:
    at = datetime.fromisoformat(payload["at"])
    zones = payload.get("event_zone") or {}
    lines: list = []
    if kind == "level":
        names = [level_name({"kind": k}, lang) for k in [payload["level_kind"]] + list(payload.get("also_kinds") or ())]
        lines.append(t(lang, "pa_level_title", name=_e(" = ".join(names)),
                       level=fmt_price(payload["level"], lang)))
        lines.append(t(lang, "pa_level_now", clock=fmt_clock(at, lang), price=fmt_price(payload["price"], lang),
                       period=t(lang, "pa_period_" + payload.get("period", "day"))))
        hist = payload.get("history")
        side = int(payload.get("side") or 1)
        if hist and hist.get("real") and (hist["real"].get("1h") and (hist.get("control") or {}).get("1h")):
            r1, c1 = hist["real"]["1h"], hist["control"]["1h"]
            verdict = (hist.get("verdicts") or {}).get("1h", "insufficient")
            vk = ("lv_verdict_differs_more" if r1["hold_rate"] > c1["hold_rate"] else "lv_verdict_differs_less") \
                if verdict == "differs" else "lv_verdict_" + verdict
            lines.append(t(lang, "pa_level_hist", n=_n(hist["real"]["n"], lang),
                           side=t(lang, "lv_side_above" if side > 0 else "lv_side_below"),
                           hold=fmt_share(r1["hold_rate"], lang), ctrl=fmt_share(c1["hold_rate"], lang),
                           verdict=t(lang, vk)))
            lines.append(t(lang, "pa_level_move", further=_pct(r1["further_median"], lang),
                           back=_pct(r1["back_median"], lang)))
        nxt = payload.get("next")
        if nxt:
            p24 = (nxt.get("touch") or {}).get("24h")
            if zones.get("24h") or p24 is None:
                lines.append(t(lang, "pa_next_nop", price=zone_price(nxt, lang),
                               name=_e(zone_names(nxt, lang, limit=1)), dist=fmt_signed_pct(nxt["distance_pct"], lang)))
            else:
                lines.append(t(lang, "pa_next", price=zone_price(nxt, lang), name=_e(zone_names(nxt, lang, limit=1)),
                               dist=fmt_signed_pct(nxt["distance_pct"], lang), p=fmt_prob(p24, lang)))
        cl = None if zones.get("4h") else _corridor_line(payload.get("corridor_4h"), "pa_corridor", lang)
        if cl:
            lines.append(cl)
        note = zone_note(zones, ["4h", "24h"], lang)
        if note:
            lines.append(note)
    elif kind == "event":
        # always inside the release's 1h zone (30 minutes ahead): no corridor, no multiplier
        name = EVENT_NAMES.get(payload["event_kind"], (payload["event_kind"],) * 2)[_ix(lang)]
        lines.append(t(lang, "pa_event_title", mins=int(payload["minutes"]), name=_e(name)))
        lines.append(t(lang, "pa_event_when", clock=fmt_clock(datetime.fromisoformat(payload["event_at"]), lang),
                       price=fmt_price(payload["price"], lang)))
        lines.append(t(lang, "ez_event_note"))
    elif kind == "move":
        start = datetime.fromisoformat(payload["start"])
        lines.append(t(lang, "pa_move_title", pct=fmt_signed_pct(payload["move_pct"], lang)))
        lines.append(t(lang, "pa_move_span", span=f"{fmt_kyiv_hm(start)}–{fmt_kyiv_hm(at)} {t(lang, 'zone')}",
                       open=fmt_price(payload["open"], lang), close=fmt_price(payload["close"], lang)))
        if payload.get("every_days"):
            lines.append(t(lang, "pa_move_rare", days=_x(payload["every_days"], lang)))
        cl = None if zones.get("1h") else _corridor_line(payload.get("corridor_1h"), "pa_corridor_1h_plain", lang)
        if cl:
            lines.append(cl)
        note = zone_note(zones, ["1h"], lang)
        if note:
            lines.append(note)
        near = payload.get("near") or []
        if near:
            parts = [t(lang, "dc_btc_level_part", arrow="↑" if z["distance_pct"] > 0 else "↓",
                       price=zone_price(z, lang), name=_e(zone_names(z, lang, limit=1)),
                       dist=fmt_signed_pct(z["distance_pct"], lang)) for z in near]
            lines.append(t(lang, "pa_levels_near", parts=" · ".join(parts)))
    elif kind == "price":
        lines.append(t(lang, "pa_price_title", level=fmt_price(payload["level"], lang)))
        if payload.get("late"):
            lines.append(t(lang, "pa_price_late", when=_when(at, lang, with_day=True),
                           price=fmt_price(payload["price"], lang)))
        else:
            lines.append(t(lang, "pa_price_now", clock=fmt_clock(at, lang), price=fmt_price(payload["price"], lang)))
        cl = None if zones.get("4h") else _corridor_line(payload.get("corridor_4h"), "pa_corridor", lang)
        if cl:
            lines.append(cl)
        note = zone_note(zones, ["4h"], lang)
        if note:
            lines.append(note)
        lines.append(t(lang, "pa_price_footer"))
    else:
        raise ValueError(f"unknown alert kind {kind!r}")
    contexts = {"level": [f"level:{payload.get('level_kind')}", "level"],
                "event": _event_contexts([payload.get("event_kind")]),
                "move": ["move"]}.get(kind, [])
    checked = research_line(contexts, lang)
    if checked and sum(1 for x in lines if x.strip()) < ALERT_MAX_LINES:     # an extra, never a 9th line
        lines.append(checked)
    return assert_descriptive("\n".join(lines), lang)
