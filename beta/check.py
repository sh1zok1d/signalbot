"""`/check` — the full version (PRE_BETA_SCOPE_DECISION_V1 §5; backlog D1–D7).

For one or two user prices:
- the chance to reach each within 1h / 4h / 24h, worded by the frozen rule of
  docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md (`claims.touch_wording`): «шанс ≈ X %» beside its
  held-out or live accuracy, or «исторически в X % случаев»;
- for two levels, the chance that neither is touched (the joint excursion table, never a product of
  two chances); «кто первый» is not shown (post-beta);
- «обычно»: the typical move of each horizon; the scheduled events of the next 24h; the next
  objective level beyond;
- what followed touches of similar levels: the level's own type history beside a random level when
  the price is an objective level, otherwise the reaction of a level at that distance on history.

No direction is ever stated. Pure (the bot passes the decision block and the statistics).
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from .i18n import assert_descriptive, fmt_clock, fmt_price, fmt_signed_pct, t

MAX_LEVELS = 2
MAX_DISTANCE_PCT = 30.0
MIN_DISTANCE_PCT = 0.05
HORIZONS = ("1h", "4h", "24h")
_NUM = r"\d+(?:[.,]\d+)?"


def _tokens(text: str) -> list:
    s = (text or "").strip().lower().replace("\u00a0", " ").replace("$", "").replace("к", "k")
    s = re.sub(r"[,;]\s+|;", " ", s).strip(",")              # «64000, 61000» / «64000; 61000»: two levels
    s = re.sub(r"(\d),(\d{4,})", r"\1 \2", s)                  # «64000,61000»: a comma before 4+ digits splits
    s = re.sub(r"(\d)\s+%", r"\1%", s)                       # «-3 %»
    s = re.sub(r"([+-])\s+(\d)", r"\1\2", s)                  # «- 3%»
    out: list = []
    grouped = False                                            # the last token can take another digit group
    for tok in s.split():                                      # «64 000» → «64000», never «64000 100»
        m = re.fullmatch(r"\d{3}([.,]\d{1,2})?", tok)             # «62 480,5»: the last group may carry decimals
        if m and out and grouped:
            out[-1] += tok
            grouped = m.group(1) is None
            continue
        out.append(tok)
        grouped = bool(re.fullmatch(r"[+-]?\d{1,3}", tok))
    return out


def _value(tok: str, price: float) -> Optional[float]:
    """A price from one token: «64000», «64k», «64,5k», «65,000», «-3%», «+1.5%»."""
    m = re.fullmatch(r"([+-]?)(" + _NUM + r")%", tok)
    if m:
        d = float(m.group(2).replace(",", "."))
        return price * (1 + (-d if m.group(1) == "-" else d) / 100.0)
    m = re.fullmatch(r"(" + _NUM + r")k", tok)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000.0
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", tok):     # «65,000» / «65,000.5»
        return float(tok.replace(",", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", tok) and float(tok) < price / 10:   # «65.000»
        return float(tok.replace(".", ""))
    if re.fullmatch(_NUM, tok):
        return float(tok.replace(",", "."))
    return None


def parse_check_args(args: Optional[str], price: Optional[float]) -> tuple:
    """(levels, error key). Levels are prices; at most two; each 0.05 %–30 % from the price."""
    if not price:
        return [], "al_no_price"
    toks = _tokens(args or "")
    if not toks or len(toks) > MAX_LEVELS:
        return [], "ck_usage"
    levels = []
    for tok in toks:
        v = _value(tok, float(price))
        if v is None or not math.isfinite(v) or v <= 0:
            return [], "ck_usage"
        d = abs(v / price - 1) * 100.0
        if d > MAX_DISTANCE_PCT:
            return [], "al_too_far"
        if d < MIN_DISTANCE_PCT:
            return [], "al_too_close"
        levels.append(round(v, 2))
    if len(levels) == 2 and abs(levels[0] / levels[1] - 1) * 100.0 < MIN_DISTANCE_PCT:
        return [], "ck_usage"
    return levels, None


# ---- the numbers ----------------------------------------------------------------------------------
def _chances(model: Mapping[str, Any], hz: Mapping[str, Any], dist_pct: float) -> dict:
    from .rangecast import touch_probability
    return {h: touch_probability(model, h, hz[h]["scale_pct"], abs(dist_pct)) for h in HORIZONS if h in hz}


def _neither(model: Mapping[str, Any], hz: Mapping[str, Any], d1: float, d2: float, p1: dict, p2: dict) -> dict:
    """{h: (chance, kind)}: opposite sides from the joint table (kind 'neither'); the same side is not
    touching the nearer one (kind 'touch', on the nearer chance)."""
    from .rangecast import neither_probability
    out = {}
    for h in HORIZONS:
        if h not in hz or h not in p1 or h not in p2:
            continue
        if (d1 > 0) != (d2 > 0):
            up, dn = (d1, d2) if d1 > 0 else (d2, d1)
            pu, pd_ = (p1[h], p2[h]) if d1 > 0 else (p2[h], p1[h])
            if "q_joint" not in ((model.get("horizons") or {}).get(h) or {}):
                continue
            out[h] = (neither_probability(model, h, hz[h]["scale_pct"], up, abs(dn), p_up=pu, p_down=pd_), "neither",
                      None)
        else:
            near = p1[h] if abs(d1) <= abs(d2) else p2[h]
            out[h] = (1.0 - near, "touch", near)
    return out


def _wording(block: Mapping[str, Any], h: str, p: float, kind: str = "touch") -> dict:
    from .claims import touch_wording
    return touch_wording((block.get("corridor") or {}).get("holdout"), block.get("touch_live"), h, p, kind=kind)


# ---- the text ---------------------------------------------------------------------------------------
def _p(p: Optional[float], lang: str) -> str:
    from .decision_format import fmt_prob
    return fmt_prob(p, lang)


def _cal(w: Mapping[str, Any], lang: str, *, complement: bool = False) -> tuple:
    from .decision_format import fmt_share
    pp, rr = (1 - w["predicted"], 1 - w["realized"]) if complement else (w["predicted"], w["realized"])
    return fmt_share(pp, lang), fmt_share(rr, lang)


def _history_days(model: Mapping[str, Any], h: str) -> int:
    """The days of history the model's chance of horizon h is fitted on (the N of «исторически»)."""
    return int((((model.get("horizons") or {}).get(h)) or {}).get("n_days") or 0)


def _single_line(h: str, p: float, w: Mapping[str, Any], lang: str, *, model: Mapping[str, Any],
                 hz: Mapping[str, Any]) -> str:
    from .decision_format import _hz, _pct
    if w["mode"] == "B":
        P, R = _cal(w, lang)
        key = "ck_h_b_live" if w["source"] == "live" else "ck_h_b_hold"
        return t(lang, key, h=_hz(h, lang), p=_p(p, lang), P=P, R=R, n=int(w["n_eff"]))
    return t(lang, "ck_h_fallback", h=_hz(h, lang), p=_p(p, lang), n=_history_days(model, h),
             typ=_pct(hz[h]["typical_move_pct"], lang))


def _context_lines(block: Mapping[str, Any], levels: Sequence[float], dist_stats, lang: str) -> list:
    """«обычно», today's events, the next objective level beyond, and what followed similar touches."""
    from .decision_format import _e, _hist_lines, _pct, zone_names, zone_price
    from .levels import ZONE_TOL_PCT, distance_reaction
    hz = (block.get("corridor") or {}).get("horizons") or {}
    price = float(block["price"])
    out = []
    if all(h in hz for h in HORIZONS):
        out.append(t(lang, "rk_typical", h1=_pct(hz["1h"]["typical_move_pct"], lang),
                     h4=_pct(hz["4h"]["typical_move_pct"], lang), h24=_pct(hz["24h"]["typical_move_pct"], lang)))
    evs = block.get("events") or []
    if evs:
        from .decision_format import _when
        from .i18n_decision import EVENT_NAMES
        from .decision_format import _ix
        names = [f"{_when(datetime.fromisoformat(e['at']), lang, with_day=False)} "
                 f"{EVENT_NAMES.get(e['kind'], (e['kind'],) * 2)[_ix(lang)]}" for e in evs]
        out.append(t(lang, "ck_events", list=_e(", ".join(names))))
    lv = block.get("levels") or {}
    for level in levels:
        side = 1 if level > price else -1
        zones = (lv.get("above") if side > 0 else lv.get("below")) or []
        same = next((z for z in zones + ([lv["at"]] if lv.get("at") else [])
                     if abs(float(z["edge"]) / level - 1) * 100.0 <= ZONE_TOL_PCT), None)
        beyond = next((z for z in zones if side * (float(z["edge"]) - level) > level * 0.001), None)
        head = fmt_price(level, lang)
        if same is not None:
            hist = _hist_lines(same.get("history"), lang, side)
            out.append(t(lang, "ck_is_level", level=head, names=_e(zone_names(same, lang, limit=2))))
            out.extend(hist)
        else:
            cell = distance_reaction(dist_stats, (level / price - 1) * 100.0)
            out.extend(_distance_lines(cell, head, lang))
        if beyond is not None:
            out.append(t(lang, "ck_beyond", level=head, price=zone_price(beyond, lang),
                         name=_e(zone_names(beyond, lang, limit=1)),
                         dist=fmt_signed_pct(beyond["distance_pct"], lang)))
    return out


def _distance_lines(cell: Optional[Mapping[str, Any]], head: str, lang: str) -> list:
    from .decision_format import MIN_N_SHOWN, _n, _pct, fmt_share
    if not cell:
        return []
    n = int(cell.get("n") or 0)
    if n < MIN_N_SHOWN or not cell.get("1h"):
        return [t(lang, "ck_dist_short", level=head, n=_n(n, lang))]
    one = cell["1h"]
    d = float(cell["distance_pct"])
    return [t(lang, "ck_dist", level=head, n=_n(n, lang), d=_pct(d, lang, 2 if d < 1 else 0),
              hold=fmt_share(one["hold_rate"], lang), further=_pct(one["further_median"], lang),
              back=_pct(one["back_median"], lang))]


def format_check(block: Mapping[str, Any], stats: Optional[Mapping[str, Any]], levels: Sequence[float], lang: str, *,
                 now: datetime) -> str:
    from .decision_format import _hz, data_clock, unavailable_line, zone_note
    gone = unavailable_line(block, lang)
    model = (stats or {}).get("range_model")
    if gone or model is None:
        return assert_descriptive(gone or t(lang, "dc_unavailable", reason=t(lang, "dc_reason_no_stats")), lang)
    hz = (block.get("corridor") or {}).get("horizons") or {}
    price = float(block["price"])
    clock = fmt_clock(data_clock(block) or now, lang)          # the price's own time (A1)
    dists = [(lv / price - 1) * 100.0 for lv in levels]
    probs = [_chances(model, hz, d) for d in dists]
    lines = []
    if len(levels) == 1:
        lines.append(t(lang, "ck_title_one", level=fmt_price(levels[0], lang), dist=fmt_signed_pct(dists[0], lang),
                       price=fmt_price(price, lang), clock=clock))
        for h in HORIZONS:
            if h in probs[0]:
                lines.append(_single_line(h, probs[0][h], _wording(block, h, probs[0][h]), lang, model=model, hz=hz))
    else:
        order = sorted(range(2), key=lambda k: -dists[k])          # the higher level first
        a, b = order
        lines.append(t(lang, "ck_title_two", a=fmt_price(levels[a], lang), da=fmt_signed_pct(dists[a], lang),
                       b=fmt_price(levels[b], lang), db=fmt_signed_pct(dists[b], lang),
                       price=fmt_price(price, lang), clock=clock))
        neither = _neither(model, hz, dists[a], dists[b], probs[a], probs[b])
        fallback = []
        for h in HORIZONS:
            if h not in probs[a]:
                continue
            vals = [(probs[a][h], "touch", None, t(lang, "ck_arrow_up" if dists[a] > 0 else "ck_arrow_down")),
                    (probs[b][h], "touch", None, t(lang, "ck_arrow_up" if dists[b] > 0 else "ck_arrow_down"))]
            if h in neither:
                pn, kind, near = neither[h]
                vals.append((pn, kind, near, t(lang, "ck_neither")))
            parts, cals = [], []
            for p, kind, near, label in vals:
                w = _wording(block, h, near if near is not None else p, kind)
                if w["mode"] == "B":
                    parts.append(t(lang, "ck_part_b", label=label, p=_p(p, lang)))
                    P, R = _cal(w, lang, complement=near is not None)
                    # each part says where its own check comes from and its own N
                    cals.append(t(lang, "ck_cal_part", label=label, P=P, R=R, n=int(w["n_eff"]),
                                  src=t(lang, "ck_src_live" if w["source"] == "live" else "ck_src_hold")))
                else:
                    fallback.append(h)
                    parts.append(t(lang, "ck_part_fallback", label=label, p=_p(p, lang)))
            lines.append(t(lang, "ck_pair_line", h=_hz(h, lang), parts=" · ".join(parts)))
            if cals:
                lines.append(t(lang, "ck_pair_cal", parts=" · ".join(cals)))
        if fallback:
            lines.append(t(lang, "ck_fallback_note", n=min(_history_days(model, h) for h in fallback)))
    note = zone_note(block.get("event_zone"), [h for h in HORIZONS if h not in hz], lang)
    if note:
        lines.append(note)
    lines.extend(_context_lines(block, levels, (stats or {}).get("distance_reactions"), lang))
    from .decision_format import race_lines
    lines.extend(race_lines(block, lang, "check", check_levels=levels))
    lines.append(t(lang, "ck_footer_one" if len(levels) == 1 else "ck_footer_two"))
    return assert_descriptive("\n".join(lines), lang)


def check_buttons(levels: Sequence[float], lang: str) -> list:
    """«Следить за уровнем»: one tap makes a personal /alert at the level."""
    return [[(t(lang, "btn_watch", price=fmt_price(lv, lang)), f"w:{lv:.2f}") for lv in levels]]


def check_button(level: float, lang: str) -> tuple:
    """One tap from a push or the briefing runs /check with the level filled in."""
    return (t(lang, "btn_check", price=fmt_price(level, lang)), f"k:{float(level):.2f}")


def parse_level_callback(data: str) -> Optional[float]:
    """`w:<price>` / `k:<price>` → the price (None for anything malformed)."""
    if len(data) > 64 or data[:2] not in ("w:", "k:"):
        return None
    try:
        v = float(data[2:])
    except ValueError:
        return None
    return v if math.isfinite(v) and v > 0 else None
