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
                   fmt_usd, kyiv, local, na, t)
from .i18n_decision import EVENT_NAMES, LEVEL_NAMES, WEEKDAYS, cases_word

_LANG_IX = {"ru": 0, "en": 1}
# One threshold for every historical or tracked count on a user surface (PRE_BETA_SCOPE_DECISION_V1
# block B): below it a share becomes «мало данных (N)». It equals the statistics' own minimum
# (`analogues.MIN_N`, `levels.MIN_EVENTS`); a test keeps them equal.
MIN_N_SHOWN = 30
# The bootstrap behind every L2 interval needs this many distinct days (analogues) or periods (level
# history); with fewer, a large N gets no interval and the line says so, never «мало данных» beside it.
# They equal `analogues.MIN_DAYS` and `levels.MIN_PERIODS`; a test keeps them equal.
MIN_DAYS_SHOWN = 15
MIN_PERIODS_SHOWN = 15


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


def _x(v: Optional[float], lang: str, nd: int = 1) -> str:
    if v is None:
        return na(lang)
    s = f"{float(v):.{nd}f}"
    return s.replace(".", ",") if lang == "ru" else s


def fmt_pp(v: float, lang: str) -> str:
    """A difference of two shares (fractions) in percentage points: one decimal, signed by the unrounded
    value, so an interval edge just below zero stays «−0,0» rather than an unsigned «0,0»."""
    return fmt_signed_pct(float(v) * 100.0, lang, nd=1)[:-1]


def _interval(ci: Any) -> Optional[tuple]:
    """A stored [lo, hi] as two floats, or None."""
    if not ci or len(ci) != 2 or ci[0] is None or ci[1] is None:
        return None
    return float(ci[0]), float(ci[1])


def pp_ci(ci: Optional[Sequence[float]], lang: str) -> str:
    """'; 95% интервал −0,8…+3,1' for a stored [lo, hi] of a difference of shares, or ''."""
    iv = _interval(ci)
    return "" if iv is None else t(lang, "dc_pp_ci", lo=fmt_pp(iv[0], lang), hi=fmt_pp(iv[1], lang))


def share_pair(a: float, b: float, lang: str) -> tuple:
    """Two shares printed side by side: whole percents while their difference is the rounded difference of
    the shares, else one decimal for both (never «52% против 52%» beside +1,0 п.п., «52% против 53%» beside
    −0,0 п.п. or «52% против 54%» beside −1,0 п.п.)."""
    if round(a * 100) - round(b * 100) == round((a - b) * 100):
        return fmt_share(a, lang), fmt_share(b, lang)
    return tuple(fmt_plain_pct(x * 100.0, lang, nd=1) for x in (a, b))


def analog_shown(cell: Mapping[str, Any]) -> bool:
    """Whether «после похожих» prints its numbers: enough cases, a baseline and the difference's 95%
    interval. Without the interval (fewer days than the bootstrap needs, or statistics built before the
    interval existed) the line says «мало данных»; the claim journal states the same."""
    return int(cell.get("n") or 0) >= MIN_N_SHOWN and bool(cell.get("baseline")) \
        and _interval((cell.get("ci95") or {}).get("direction")) is not None


def level_hist_shown(hist: Optional[Mapping[str, Any]], h: str = "1h") -> bool:
    """Whether a level's first-touch history prints its numbers at horizon `h`: enough touches, both
    hold rates and the difference's 95% interval; otherwise «мало данных», as on /levels and /check."""
    if not hist:
        return False
    real, ctrl = hist.get("real") or {}, hist.get("control") or {}
    return int(real.get("n") or 0) >= MIN_N_SHOWN and (real.get(h) or {}).get("hold_rate") is not None \
        and (ctrl.get(h) or {}).get("hold_rate") is not None \
        and _interval((hist.get("ci95") or {}).get(h)) is not None


def analog_range(cell: Mapping[str, Any], lang: str) -> tuple:
    """(ratio, interval text) of the move against «обычно». With the bootstrapped interval stored, the
    ratio is exp of the mean log range of the cohort minus its baseline's and the interval is exp of its
    95% interval. Without it (an older statistics row, which may carry the mean log range already) the
    median ratio with no interval, so the estimand never changes silently."""
    base = cell.get("baseline") or {}
    ci = _interval((cell.get("ci95") or {}).get("range"))
    if ci is not None and cell.get("mean_log_range") is not None and base.get("mean_log_range") is not None:
        ratio = math.exp(float(cell["mean_log_range"]) - float(base["mean_log_range"]))
        return ratio, t(lang, "dc_ratio_ci", lo=_x(math.exp(ci[0]), lang, 2), hi=_x(math.exp(ci[1]), lang, 2))
    return cell.get("range_ratio"), ""


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
    reason = {"DATA_STALE": "dc_reason_stale", "STATS_STALE": "dc_reason_stats_stale",
              "ERROR": "dc_reason_error"}.get(block.get("reason"), "dc_reason_no_stats")
    return t(lang, "dc_unavailable", reason=t(lang, reason))


def price_clock(price_ts: Optional[str]) -> Optional[datetime]:
    """When a price was observed: the close of its Binance 1m bar. `price_ts` is the bar's open (the
    stored convention of decision support: the claim journal and the health check add the minute too)."""
    return datetime.fromisoformat(price_ts) + timedelta(minutes=1) if price_ts else None


def data_clock(block: Mapping[str, Any]) -> Optional[datetime]:
    """When the price of the block was observed (the close of its newest closed Binance 1m bar), never
    the request time (A1)."""
    return price_clock(block.get("price_ts"))


def stats_line(block: Mapping[str, Any], lang: str) -> Optional[str]:
    """«Статистика от …»: when the history statistics behind the numbers were built (A1)."""
    built = (block.get("stats") or {}).get("built_at")
    if not built:
        return None
    return t(lang, "dc_stats_built", when=_when(datetime.fromisoformat(built), lang, with_day=True))


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


def _when(at: datetime, lang: str, *, with_day: bool) -> str:
    loc = local(at)                                       # the recipient's clock (C5)
    hm = loc.strftime("%H:%M")
    if not with_day:
        return hm
    return f"{WEEKDAYS[lang if lang in WEEKDAYS else 'ru'][loc.weekday()]} {loc.strftime('%d.%m')} {hm}"


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


MAIN_RESEARCH_LINES = 2          # owner task 2026-10-04: at most 2 research conclusions on a main surface
RISK_TOPICS = ("RANGE_1H", "RANGE_4H", "RANGE_24H", "CALENDAR_VOL")


def _block_now(block: Mapping[str, Any]) -> Optional[datetime]:
    at = block.get("as_of")
    return datetime.fromisoformat(at) if at else None


def main_research(block: Mapping[str, Any]) -> bool:
    """Whether the block's research evidence may reach a main surface (the «🔬 Исследования» tab reads it
    either way). A block built before the split switch carries no flag and shows none."""
    return bool((block.get("evidence") or {}).get("main_surfaces"))


def evidence_lines(block: Mapping[str, Any], surface: str, lang: str, *, limit: int = MAIN_RESEARCH_LINES,
                   since: Optional[datetime] = None, topics: Optional[Sequence[str]] = None,
                   running: bool = True) -> list:
    """Research conclusions for a surface from the block's research evidence: the live state and
    what the closed research found after it, by the evidence hierarchy (beta/research_evidence.py).
    None unless the block was built with research on the main surfaces (decision §6.1)."""
    from .research_render import surface_lines
    if not main_research(block):
        return []
    now = _block_now(block)
    return surface_lines(block.get("evidence"), surface, lang, limit=limit, since=since, topics=topics,
                         now=now if running else None)


def research_line(contexts: Sequence[str], lang: str) -> Optional[str]:
    """One «Проверено: …» line from the research registry, or None (the registry is optional)."""
    try:
        from .research_link import context_line
        return context_line(contexts, lang)
    except Exception:  # noqa: BLE001 - never let the registry break a message
        return None


def analog_line(card: Optional[Mapping[str, Any]], lang: str, *, since_year: Optional[int] = None) -> Optional[str]:
    """One line of «что было после похожих» for a window's own horizon (1h → 1h, 4h → 4h)."""
    if not card:
        return None
    h = card["window"]
    cell = (card.get("outcomes") or {}).get(h) or {}
    n = int(cell.get("n") or 0)
    if not analog_shown(cell):
        return _short_line(("dc_analog_short", "dc_analog_fewdays", "dc_analog_noci"), n, cell.get("days"),
                           MIN_DAYS_SHOWN, lang)
    base = cell["baseline"]
    ratio, rci = analog_range(cell, lang)
    p_up, base_up = share_pair(cell["p_up"], base["p_up"], lang)
    return t(lang, "dc_analog_line", n=_n(n, lang, since_year), h=_hz(h, lang), p_up=p_up, base_up=base_up,
             diff=fmt_pp(cell["p_up"] - base["p_up"], lang),
             ci=pp_ci((cell.get("ci95") or {}).get("direction"), lang), ratio=_x(ratio, lang, 2 if rci else 1),
             rci=rci)


def brief_levels_line(block: Mapping[str, Any], lang: str) -> list:
    """«Уровни: ↑ 62 950 максимум вчера (+0,75%) · ↓ 61 900 минимум Азии (−0,93%)»: the nearest level each
    side, no chance (the briefing's «🎯 Проверить» buttons open /check with it)."""
    lv = block.get("levels") or {}
    out = []
    if lv.get("at"):
        out.append(t(lang, "dc_level_at", price=zone_price(lv["at"], lang), name=_e(zone_names(lv["at"], lang))))
    parts = [t(lang, "dc_btc_level", arrow=arrow, price=zone_price(z, lang), name=_e(zone_names(z, lang, limit=1)),
               dist=fmt_signed_pct(z["distance_pct"], lang))
             for z, arrow in (((lv.get("above") or [None])[0], "↑"), ((lv.get("below") or [None])[0], "↓")) if z]
    if parts:
        out.append(t(lang, "dc_brief_levels", parts=" · ".join(parts)))
    return out


def brief_lines(view: Mapping[str, Any], lang: str) -> list:
    """The decision block of the briefing and /catchup (after «Сейчас»), in about four lines (backlog C2):
    the 4h / 24h corridor and its record, the nearest levels, the next 24h events, then research
    (main surfaces only, decision §6.1)."""
    block = view.get("decision")
    if not block:
        return []
    gone = unavailable_line(block, lang)
    if gone:
        return ["", gone]
    if view.get("product_status") == "DATA STALE":
        # A2: under a stale tape no corridor, level or state-matched research, whatever the block
        # holds; the calendar and the event warning carry no market number and stay
        out = ["", t(lang, "dc_unavailable", reason=t(lang, "dc_reason_data_late"))]
        note = zone_note(block.get("event_zone"), ("4h", "24h"), lang)
        return out + ([note] if note else []) + _btc_events(block, lang)
    surface = "brief" if view.get("kind") == "brief" else "catchup"
    window = ((view.get("market") or {}).get("window") or {})
    since = datetime.fromisoformat(window["window_start"]) if window.get("window_start") else None
    out = (_btc_corridor(block, lang, ("4h", "24h")) + brief_levels_line(block, lang) + _btc_events(block, lang)
           + evidence_lines(block, surface, lang, since=since, running=False))
    return ([""] + out) if out else []


def touch_wording(block: Mapping[str, Any], h: str, p: Optional[float], kind: str = "touch") -> dict:
    """The frozen wording rule of a touch chance on every surface (BETA_CHECK_CALIBRATION_DESIGN_V1 §3):
    mode B with its held-out or live «говорили → было», or the «исторически» fallback."""
    from .claims import touch_wording as rule
    return rule((block.get("corridor") or {}).get("holdout"), block.get("touch_live"), h, p, kind=kind)


def cal_part(label: str, w: Mapping[str, Any], lang: str) -> str:
    """«↑ 40% → 39% (на истории, N=120)»: one B-mode chance's own check."""
    return t(lang, "ck_cal_part", label=label, P=fmt_share(w["predicted"], lang), R=fmt_share(w["realized"], lang),
             n=int(w["n_eff"]), src=t(lang, "ck_src_live" if w["source"] == "live" else "ck_src_hold"))


def _btc_corridor(block: Mapping[str, Any], lang: str, horizons: Sequence[str] = ("1h", "4h", "24h")) -> list:
    """«Коридор: 1ч … · 4ч … · 24ч …» and its record: the share inside by horizon, live over 30 days
    once its independent windows reach MIN_N_SHOWN (the /accuracy rule), else on the held-out year."""
    c = block.get("corridor") or {}
    hz = c.get("horizons") or {}
    zones = block.get("event_zone") or {}
    shown = [h for h in horizons if hz.get(h)]
    out = []
    if shown:
        out.append(t(lang, "dc_btc_corridor", parts=" · ".join(
            t(lang, "dc_btc_corridor_part", h=_hz(h, lang), low=fmt_price(hz[h]["lower"], lang),
              high=fmt_price(hz[h]["upper"], lang)) for h in shown)))
    note = zone_note(zones, list(horizons), lang)
    if note:
        out.append(note)
    live, hold, days = [], [], 0
    for h in shown:
        rec = (c.get("live") or {}).get(h) or {}
        n = int(rec.get("INSIDE", 0)) + int(rec.get("OUTSIDE", 0))
        n_eff = int(rec.get("N_EFF", 0))
        ho = (c.get("holdout") or {}).get(h) or {}
        if n and n_eff >= MIN_N_SHOWN:
            live.append(t(lang, "dc_btc_track_live", h=_hz(h, lang), p=fmt_share(rec.get("INSIDE", 0) / n, lang), n=n_eff))
        elif ho.get("coverage_realized") is not None:
            hold.append(t(lang, "dc_btc_track_part", h=_hz(h, lang), p=fmt_share(ho["coverage_realized"], lang)))
            days = max(days, int(ho.get("n_days") or 0))
    parts = live + ([t(lang, "dc_btc_track_hold", parts=" · ".join(hold), days=days)] if hold else [])
    if parts:
        # every horizon shown here is outside its own release span (a horizon inside it is dropped at the
        # source, BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR §9), so its designed share is the comparator of its record
        out.append(t(lang, "dc_btc_track", share=fmt_share(c.get("coverage"), lang), parts=" · ".join(parts)))
    return out


_H_ORDER = {"1h": 1, "4h": 4, "24h": 24}


def _cal_line(block: Mapping[str, Any], cals: Mapping[tuple, str], fallback: set, lang: str) -> list:
    """The checks of the «≈» chances, once per horizon and bin, by hours (never «24ч» before «4ч»), and one
    note under «исторически» chances: the N of the history and that their accuracy did not pass (/check)."""
    out = []
    if cals:
        out.append(t(lang, "dc_btc_cal", parts=" · ".join(cals[k] for k in sorted(cals, key=lambda k: (_H_ORDER[k[0]], k[1])))))
    if fallback:
        days = [((block.get("corridor") or {}).get("history_days") or {}).get(h) for h in fallback]
        out.append(t(lang, "ck_fallback_note", n=min(days)) if all(days) else t(lang, "dc_fallback_note"))
    return out


def _btc_levels(block: Mapping[str, Any], lang: str) -> list:
    """The nearest level above and below with the chance to reach it within 24h (4h inside the 24h
    event zone), worded by the frozen rule: «≈ X%» with its check, or «исторически в X% случаев»."""
    lv = block.get("levels") or {}
    lines, cals, fallback = [], {}, set()
    for z, arrow in (((lv.get("above") or [None])[0], "↑"), ((lv.get("below") or [None])[0], "↓")):
        if not z:
            continue
        args = dict(arrow=arrow, price=zone_price(z, lang), name=_e(zone_names(z, lang, limit=1)),
                    dist=fmt_signed_pct(z["distance_pct"], lang))
        touch = z.get("touch") or {}
        h = next((x for x in ("24h", "4h") if touch.get(x) is not None), None)
        w = touch_wording(block, h, touch[h]) if h else {"mode": "none"}
        if w["mode"] == "B":
            lines.append(t(lang, "dc_btc_level_b", h=_hz(h, lang), p=fmt_prob(touch[h], lang), **args))
            # one check per bin: two levels in the same bin share it, it is not a per-level accuracy
            cals.setdefault((h, tuple(w["bin"])), cal_part(_hz(h, lang), w, lang))
        elif w["mode"] == "fallback":
            lines.append(t(lang, "dc_btc_level_fb", h=_hz(h, lang), p=fmt_prob(touch[h], lang), **args))
            fallback.add(h)
        else:
            lines.append(t(lang, "dc_btc_level", **args))
    return lines + _cal_line(block, cals, fallback, lang)


def _btc_events(block: Mapping[str, Any], lang: str) -> list:
    evs = block.get("events")
    if evs is None:
        return []
    if not evs:
        return [t(lang, "dc_no_events")]
    now = _block_now(block)
    parts = []
    for e in evs:
        at = datetime.fromisoformat(e["at"])
        same_day = now is not None and local(at).date() == local(now).date()
        parts.append(f"{_when(at, lang, with_day=not same_day)} "
                     f"{_e(EVENT_NAMES.get(e['kind'], (e['kind'], e['kind']))[_ix(lang)])}")
    return [t(lang, "dc_btc_events", list=", ".join(parts))]


def btc_lines(view: Mapping[str, Any], lang: str) -> list:
    """/btc decision support (backlog C1): corridors with their record, the two nearest levels with
    their chance, the next 24h events, then research (main surfaces only, decision §6.1)."""
    block = view.get("decision")
    if not block:
        return []
    if not block.get("available"):
        return [unavailable_line(block, lang)]          # A2: the screen says why, as /levels and /risk do
    out = _btc_corridor(block, lang) + _btc_levels(block, lang) + _btc_events(block, lang)
    out.extend(evidence_lines(block, "btc", lang))
    return out


def typical_move(view: Mapping[str, Any], h: str) -> Optional[float]:
    """The «обычно» of the price change over the window just ended: the model's typical move of horizon h as
    it stood at the window's start (never the current scale, which already contains that change). None in
    its event zone, or for a block built before this value existed."""
    block = view.get("decision") or {}
    if not block.get("available"):
        return None
    c = block.get("corridor") or {}
    if h not in (c.get("horizons") or {}):
        return None
    return (c.get("window_typical") or {}).get(h)


# ---- /levels -----------------------------------------------------------------------------
_HIST_KEYS = {"levels": ("lv_hist", ("lv_hist_short", "lv_hist_fewperiods", "lv_hist_noci"), "lv_hist_move"),
              "alert": ("pa_level_hist", ("pa_level_hist_short", "pa_level_hist_fewperiods", "pa_level_hist_noci"),
                        "pa_level_move")}


def _short_line(keys: Sequence[str], n: int, units: Optional[int], min_units: int, lang: str) -> str:
    """Why an L2 line has no numbers: too few cases; enough cases on too few distinct days or periods for
    the interval («мало разных дней (412 случаев за 9 дн.)»); or an interval not computed yet (statistics
    built before it existed)."""
    short, few, noci = keys
    if n < MIN_N_SHOWN:
        return t(lang, short, n=_n(n, lang))
    if units is not None and int(units) < min_units:
        return t(lang, few, n=_n(n, lang), d=int(units))
    return t(lang, noci, n=_n(n, lang))


def _hist_lines(hist: Optional[Mapping[str, Any]], lang: str, side: int, style: str = "levels") -> list:
    """A level's first-touch history: the 1h hold rate beside the random level's with the difference and
    its interval, then the medians; «мало данных» without enough touches or without the interval."""
    if not hist or not hist.get("real"):
        return []
    real, ctrl = hist["real"], hist.get("control") or {}
    r1, c1 = real.get("1h"), ctrl.get("1h")
    if not r1 or not c1 or not real.get("n"):
        return []
    line, short, move_key = _HIST_KEYS[style]
    if not level_hist_shown(hist, "1h"):
        return [_short_line(short, int(real["n"]), real.get("periods"), MIN_PERIODS_SHOWN, lang)]
    hold, ctrl_share = share_pair(r1["hold_rate"], c1["hold_rate"], lang)
    lines = [t(lang, line, n=_n(real["n"], lang), side=t(lang, "lv_side_above" if side > 0 else "lv_side_below"),
               hold=hold, ctrl=ctrl_share, diff=fmt_pp(r1["hold_rate"] - c1["hold_rate"], lang),
               ci=pp_ci((hist.get("ci95") or {}).get("1h"), lang))]
    move = _move_args(r1, c1, lang)
    if move:
        lines.append(t(lang, move_key, **move))
    return lines


def _move_args(r1: Mapping[str, Any], c1: Mapping[str, Any], lang: str) -> Optional[dict]:
    """The touch cohort's 1h median move beside the random level's: the random level is the
    «обычно» of a level reaction, never the cohort's own median. None without the control's
    medians (no move line rather than a number without its comparison)."""
    keys = ("further_median", "back_median")
    if any(r1.get(k) is None or c1.get(k) is None for k in keys):
        return None
    return {"further": _pct(r1["further_median"], lang), "back": _pct(r1["back_median"], lang),
            "c_further": _pct(c1["further_median"], lang), "c_back": _pct(c1["back_median"], lang)}


def _zone_research(cond: Sequence[Mapping[str, Any]], lang: str) -> list:
    """The strongest conditional finding for a zone (one line): what such a touch was followed by."""
    from .research_render import line
    try:
        return [line(cond[0], lang)] if cond else []
    except Exception:  # noqa: BLE001 - research context never breaks /levels
        return []


def _zone_block(block: Mapping[str, Any], z: Mapping[str, Any], lang: str, side: int,
                cond: Sequence[Mapping[str, Any]] = (), cals: Optional[dict] = None,
                fallback: Optional[set] = None) -> list:
    """One level of the /levels ladder (backlog C3): the /btc level line with its 4h and 24h chances by the
    frozen wording rule, then «↳» lines for what followed its first touch. The B checks go to `cals`."""
    parts = []
    touch = z.get("touch") or {}
    for h in ("4h", "24h"):
        if touch.get(h) is None:
            continue
        w = touch_wording(block, h, touch[h])
        if w["mode"] == "B":
            parts.append(t(lang, "lv_chance_b", h=_hz(h, lang), p=fmt_prob(touch[h], lang)))
            if cals is not None:
                cals.setdefault((h, tuple(w["bin"])), cal_part(_hz(h, lang), w, lang))
        else:
            parts.append(t(lang, "lv_chance_fb", h=_hz(h, lang), p=fmt_prob(touch[h], lang)))
            if fallback is not None:
                fallback.add(h)
    lines = [t(lang, "lv_level", arrow="↑" if side > 0 else "↓", price=zone_price(z, lang),
               names=_e(zone_names(z, lang, limit=3)), dist=fmt_signed_pct(z["distance_pct"], lang),
               chances="".join(" · " + x for x in parts))]
    lines.extend(_hist_lines(z.get("history"), lang, side))
    lines.extend(_zone_research(cond, lang))
    return lines


def format_levels(block: Mapping[str, Any], lang: str, *, now: datetime) -> str:
    """/levels as one ladder in the /btc style (backlog C3): above from far to near, the price, below;
    each level with its chances and first-touch history; then the checks of the chances, the corridor
    and its record, the statistics time and the UTC note."""
    gone = unavailable_line(block, lang)
    if gone:
        return assert_descriptive(gone, lang)
    lv = block.get("levels") or {}
    lines = [t(lang, "lv_title", price=fmt_price(block["price"], lang), clock=fmt_clock(data_clock(block) or now, lang)),
             ""]
    zc = ((block.get("evidence") or {}).get("zones") or {}) if main_research(block) else {}

    def cond(side: str, k: int) -> list:
        lst = zc.get(side) or []
        return list(lst[k]) if k < len(lst) else []
    cals: dict = {}
    fallback: set = set()
    above = lv.get("above") or []
    for k in reversed(range(len(above))):
        lines.extend(_zone_block(block, above[k], lang, +1, cond("above", k), cals, fallback))
    if not above:
        lines.append(t(lang, "lv_none", arrow="↑"))
    if lv.get("at"):
        lines.append(t(lang, "dc_level_at", price=zone_price(lv["at"], lang), name=_e(zone_names(lv["at"], lang))))
    else:
        lines.append(t(lang, "dc_level_now", price=fmt_price(block["price"], lang)))
    below = lv.get("below") or []
    for k, z in enumerate(below):
        lines.extend(_zone_block(block, z, lang, -1, cond("below", k), cals, fallback))
    if not below:
        lines.append(t(lang, "lv_none", arrow="↓"))
    tail = _cal_line(block, cals, fallback, lang)
    tail.extend(_btc_corridor(block, lang, ("4h", "24h")))
    if tail:
        lines += [""] + tail
    lines.append(t(lang, "lv_footer"))
    sl = stats_line(block, lang)
    if sl:
        lines.append(sl)
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
    clock = data_clock(block)
    lines = [t(lang, "rk_title", price=fmt_price(price, lang)) + (f" · {fmt_clock(clock, lang)}" if clock else "")]

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
    lines.extend(evidence_lines(block, "risk", lang, topics=RISK_TOPICS))
    sl = stats_line(block, lang)
    if sl:
        lines.append(sl)
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
ACCURACY_WINDOWS_DAYS = (7, 30, 90)
_H_MS = {"1h": 3_600_000, "4h": 14_400_000, "24h": 86_400_000}


def corridor_accuracy(rows, *, now: datetime, events_ms=()) -> dict:
    """The live corridor record by horizon (backlog B1): the share inside over 7 / 30 / 90 days with
    its effective N (distinct horizon-length slots), the mean half-width, the misses above and below
    with their median size, and two regimes over 90 days — forecasts issued on a CPI / FOMC day and
    forecasts in the widest third (high volatility). Pure."""
    from statistics import median
    ev_days = {int(t) // 86_400_000 for t in events_ms}
    out: dict = {}
    for h, hms in _H_MS.items():
        hr = [r for r in rows if r["horizon"] == h]
        if not hr:
            continue

        def ms(r):
            return int(r["issued_at"].timestamp() * 1000)

        def share(sel):
            n = len(sel)
            return {"n": n, "n_eff": len({ms(r) // hms for r in sel}),
                    "inside": (sum(1 for r in sel if r["outcome"] == "INSIDE") / n) if n else None}
        rec: dict = {"windows": {}}
        for d in ACCURACY_WINDOWS_DAYS:
            since = now.timestamp() * 1000 - d * 86_400_000
            rec["windows"][d] = share([r for r in hr if ms(r) >= since])
        last30 = [r for r in hr if ms(r) >= now.timestamp() * 1000 - 30 * 86_400_000]
        if last30:
            rec["half_width_pct"] = sum((r["upper"] - r["lower"]) / 2 / r["anchor_price"] * 100 for r in last30) / len(last30)
            up = [(r["realized_high"] / r["upper"] - 1) * 100 for r in last30
                  if r["realized_high"] is not None and r["realized_high"] > r["upper"]]
            dn = [(1 - r["realized_low"] / r["lower"]) * 100 for r in last30
                  if r["realized_low"] is not None and r["realized_low"] < r["lower"]]
            rec["miss_up"] = {"share": len(up) / len(last30), "median_pct": median(up) if up else None}
            rec["miss_down"] = {"share": len(dn) / len(last30), "median_pct": median(dn) if dn else None}
        widths = sorted((r["upper"] - r["lower"]) / r["anchor_price"] for r in hr)
        cut = widths[int(len(widths) * 2 / 3)] if len(widths) >= 3 else None
        rec["event_days"] = share([r for r in hr if ms(r) // 86_400_000 in ev_days])
        rec["high_vol"] = share([r for r in hr if cut is not None and (r["upper"] - r["lower"]) / r["anchor_price"] >= cut])
        out[h] = rec
    return out


def _share_part(x: Mapping[str, Any], key: str, lang: str, **kw) -> str:
    if x["n_eff"] < MIN_N_SHOWN or x["inside"] is None:
        return t(lang, key + "_short", n=x["n_eff"], **kw)
    return t(lang, key, p=fmt_share(x["inside"], lang), n=x["n_eff"], **kw)


def _accuracy_detail_lines(detail: Mapping[str, Any], lang: str) -> list:
    lines = [t(lang, "ac_live_head")]
    for h in ("1h", "4h", "24h"):
        rec = detail.get(h)
        if not rec:
            continue
        wins = " · ".join(_share_part(rec["windows"][d], "ac_win", lang, d=d) for d in ACCURACY_WINDOWS_DAYS)
        width = rec.get("half_width_pct")
        lines.append(t(lang, "ac_h_line", h=_hz(h, lang), windows=wins,
                       width=_pct(width, lang, 2) if width is not None else na(lang)))
        if rec.get("miss_up") is not None:
            mu, md = rec["miss_up"], rec["miss_down"]
            lines.append(t(lang, "ac_miss_line", up=fmt_share(mu["share"], lang), dn=fmt_share(md["share"], lang),
                           up_size=_pct(mu["median_pct"], lang, 2) if mu["median_pct"] is not None else na(lang),
                           dn_size=_pct(md["median_pct"], lang, 2) if md["median_pct"] is not None else na(lang)))
        lines.append(t(lang, "ac_regime_line", ev=_share_part(rec["event_days"], "ac_reg", lang),
                       hv=_share_part(rec["high_vol"], "ac_reg", lang)))
    return lines if len(lines) > 1 else [t(lang, "ac_live_none")]
def format_accuracy(model: Optional[Mapping[str, Any]], live: Mapping[str, Mapping[str, int]], lang: str,
                    detail: Optional[Mapping[str, Any]] = None,
                    touch_live: Optional[Mapping[str, Any]] = None) -> str:
    """Held-out and live corridor coverage against its target. A live share is computed over every
    scored hourly forecast, but its N is the number of non-overlapping horizon windows (`N_EFF`,
    `BetaConn.forecast_accuracy`): hourly 24h forecasts overlap 24 times, so the raw count would
    overstate the evidence. Below `MIN_N_SHOWN` independent windows the share is not shown. With
    `detail` (the windowed corridor accuracy) the `live` summary is not used."""
    from .rangecast import COVERAGE
    target = (model or {}).get("coverage") or COVERAGE
    lines = [t(lang, "ac_title", share=fmt_share(target, lang))]
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
        days = max((int(c.get("n_days") or 0) for c in cal.values()), default=0)
        lines.append(t(lang, "ac_holdout", period=period, days=days, parts=", ".join(parts)))
    if detail is not None:
        lines.extend(_accuracy_detail_lines(detail, lang))
    else:
        parts = []
        for h in ("1h", "4h", "24h"):
            rec = live.get(h) or {}
            n = int(rec.get("INSIDE", 0)) + int(rec.get("OUTSIDE", 0))
            if not n:
                continue
            n_eff = int(rec.get("N_EFF", n))
            if n_eff < MIN_N_SHOWN:
                parts.append(t(lang, "ac_part_live_short", h=_hz(h, lang), n=n_eff))
            else:
                parts.append(t(lang, "ac_part_live", h=_hz(h, lang), p=fmt_share(rec.get("INSIDE", 0) / n, lang),
                               n=n_eff))
        lines.append(t(lang, "ac_live", parts=", ".join(parts)) if parts else t(lang, "ac_live_none"))
    lines.extend(_touch_cal_lines(cal, lang))
    lines.extend(_live_cal_lines(touch_live, lang))
    return assert_descriptive("\n".join(lines), lang)


def _touch_cal_lines(cal: Mapping[str, Any], lang: str) -> list:
    """The held-out reliability of the touch chances and of «ни один» by bin
    (docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md §3, §7): «говорили P → было R (N)», a bin outside the frozen
    rule marked and explained once."""
    out, off = [], False
    for key, head in (("touch_bins", "ac_touch_head"), ("neither_bins", "ac_neither_head")):
        rows = []
        for h in ("1h", "4h", "24h"):
            bins = (((cal.get(h) or {}).get(key)) or {}).get("bins") or []
            parts = []
            for x in bins:
                part = "ac_touch_part" if x.get("passed") else "ac_touch_part_off"
                off = off or not x.get("passed")
                parts.append(t(lang, part, p=fmt_share(x["predicted"], lang), r=fmt_share(x["realized"], lang),
                               n=int(x["n_eff"])))
            if parts:
                rows.append(t(lang, "ac_touch_line", h=_hz(h, lang), parts=" · ".join(parts)))
        if rows:
            out += [t(lang, head), *rows]
    return out + ([t(lang, "ac_touch_note")] if off else [])


def _live_cal_lines(live: Optional[Mapping[str, Any]], lang: str) -> list:
    """The journal's live bins (design note §3): shown at effective N >= MIN_N_SHOWN; a bin that diverged
    stays visible here, marked, while every other surface has fallen back for it."""
    if not live:
        return []
    days = int(live.get("days") or 0)
    out, div = [], False
    for kind, head, dkey in (("horizons", "ac_live_touch_head", "diverged"),
                             ("neither", "ac_live_neither_head", "diverged_neither")):
        rows = []
        for h in ("1h", "4h", "24h"):
            bins = ((live.get(kind) or {}).get(h) or {}).get("bins") or []
            if not bins:
                continue
            bad = [list(x) for x in ((live.get(dkey) or {}).get(h) or ())]
            shown = [x for x in bins if x["n_eff"] >= MIN_N_SHOWN]
            if not shown:
                rows.append(t(lang, "ac_live_bins_short", h=_hz(h, lang), n=max(int(x["n_eff"]) for x in bins)))
                continue
            parts = []
            for x in shown:
                off = list(x["bin"]) in bad
                div = div or off
                parts.append(t(lang, "ac_touch_part_div" if off else "ac_touch_part", p=fmt_share(x["predicted"], lang),
                               r=fmt_share(x["realized"], lang), n=int(x["n_eff"])))
            rows.append(t(lang, "ac_touch_line", h=_hz(h, lang), parts=" · ".join(parts)))
        if rows:
            out += [t(lang, head, days=days), *rows]
    return out + ([t(lang, "ac_live_div_note")] if div else [])


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
        pts = payload.get("price_ts")
        if pts:
            lines.append(t(lang, "pa_level_now_at", clock=fmt_clock(at, lang), price=fmt_price(payload["price"], lang),
                           price_clock=fmt_kyiv_hm(price_clock(pts)),
                           period=t(lang, "pa_period_" + payload.get("period", "day"))))
        else:                                       # a payload stored before A1
            lines.append(t(lang, "pa_level_now", clock=fmt_clock(at, lang), price=fmt_price(payload["price"], lang),
                           period=t(lang, "pa_period_" + payload.get("period", "day"))))
        lines.extend(_hist_lines(payload.get("history"), lang, int(payload.get("side") or 1), "alert"))
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
        pts = payload.get("price_ts")
        lines.append(t(lang, "pa_event_when_at" if pts else "pa_event_when",
                       clock=fmt_clock(datetime.fromisoformat(payload["event_at"]), lang),
                       price=fmt_price(payload["price"], lang),
                       price_clock=fmt_kyiv_hm(price_clock(pts)) if pts else ""))
        lines.append(t(lang, "ez_event_note"))
    elif kind == "move":
        start = datetime.fromisoformat(payload["start"])
        lines.append(t(lang, "pa_move_title", pct=fmt_signed_pct(payload["move_pct"], lang)))
        lines.append(t(lang, "pa_move_span", span=f"{fmt_kyiv_hm(start)}–{fmt_kyiv_hm(at)} {t(lang, 'zone')}",
                       open=fmt_price(payload["open"], lang), close=fmt_price(payload["close"], lang)))
        # «раз в N дней» is a pooled all-hours frequency, not a release-conditioned one: none in a zone
        if payload.get("every_days") and not zones.get("1h"):
            lines.append(t(lang, "pa_move_rare", days=_x(payload["every_days"], lang)))
        cl = None if zones.get("1h") else _corridor_line(payload.get("corridor_1h"), "pa_corridor_1h_plain", lang)
        if cl:
            lines.append(cl)
        note = zone_note(zones, ["1h"], lang)
        if note:
            lines.append(note)
        near = payload.get("near") or []
        if near:
            parts = [t(lang, "dc_btc_level", arrow="↑" if z["distance_pct"] > 0 else "↓",
                       price=zone_price(z, lang), name=_e(zone_names(z, lang, limit=1)),
                       dist=fmt_signed_pct(z["distance_pct"], lang)) for z in near]
            lines.append(t(lang, "pa_levels_near", parts=" · ".join(parts)))
    elif kind == "price":
        lines.append(t(lang, "pa_price_title", level=fmt_price(payload["level"], lang)))
        pts = payload.get("price_ts")
        pclock = fmt_kyiv_hm(price_clock(pts)) if pts else ""
        if payload.get("late"):
            lines.append(t(lang, "pa_price_late_at" if pts else "pa_price_late", when=_when(at, lang, with_day=True),
                           price=fmt_price(payload["price"], lang), price_clock=pclock))
        else:
            lines.append(t(lang, "pa_price_now_at" if pts else "pa_price_now", clock=fmt_clock(at, lang),
                           price=fmt_price(payload["price"], lang), price_clock=pclock))
        cl = None if zones.get("4h") else _corridor_line(payload.get("corridor_4h"), "pa_corridor", lang)
        if cl:
            lines.append(cl)
        note = zone_note(zones, ["4h"], lang)
        if note:
            lines.append(note)
        lines.append(t(lang, "pa_price_footer"))
    elif kind == "approach":                 # «мои уровни»: the price within the hour's typical move (E1)
        lines.append(t(lang, "pa_approach_title", level=fmt_price(payload["level"], lang)))
        pts = payload.get("price_ts")
        lines.append(t(lang, "pa_approach_line", clock=fmt_clock(at, lang), price=fmt_price(payload["price"], lang),
                       price_clock=fmt_kyiv_hm(datetime.fromisoformat(pts)) if pts else fmt_kyiv_hm(at),
                       dist=_pct(payload["distance_pct"], lang), typ=_pct(payload["typical_1h_pct"], lang)))
        lines.append(t(lang, "pa_price_footer"))
    else:
        raise ValueError(f"unknown alert kind {kind!r}")
    # research evidence recorded with the alert (beta/research_evidence.py); no unit tested release moves
    surface = {"level": "level_alert", "move": "move_alert"}.get(kind)
    # printed only with research on the main surfaces (decision §6.1); a payload from before the switch
    # carried evidence only when they were on
    if surface and payload.get("evidence_main", True) and not (kind == "move" and zones.get("1h")):
        from .research_render import surface_lines
        ev = {"matches": payload.get("evidence") or []}
        for x in surface_lines(ev, surface, lang, limit=MAIN_RESEARCH_LINES):
            if sum(1 for y in lines if y.strip()) >= ALERT_MAX_LINES:            # an extra, never a 9th line
                break
            lines.append(x)
    return assert_descriptive("\n".join(lines), lang)
