"""Rendering of research evidence (beta/research_evidence.py) for every surface.

A line is the live state plus what the closed research found after such states, worded by the
finding's status: «Проверено» only for CONFIRMED, «Гипотеза … не подтверждено» for DISCOVERY,
«ниже нашего порога практической величины» for WEAK, «проверка эффекта не нашла» for NOT_CONFIRMED.
Every text passes `assert_descriptive`.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from .hist_series import from_ms
from .i18n import assert_descriptive, fmt_clock, fmt_kyiv_hm, fmt_plain_pct, fmt_price, fmt_signed_pct, fmt_usd, t


def _e(s: Any) -> str:
    return html.escape(str(s), quote=False)


def _num(v: float, lang: str, nd: int = 1) -> str:
    s = f"{float(v):.{nd}f}"
    return s.replace(".", ",") if lang == "ru" else s


def _level_name(kind: str, lang: str) -> str:
    from .i18n_decision import LEVEL_NAMES
    pair = LEVEL_NAMES.get(kind)
    if pair is None:
        return kind
    return pair[0 if lang == "ru" else 1].replace(" {usd}", "")


def _params(m: Mapping[str, Any], lang: str) -> dict:
    v = (m.get("live_state") or {}).get("values") or {}
    at = datetime.fromisoformat(m["matched_at"])
    p: dict = {"when": fmt_kyiv_hm(at)}
    for k, x in v.items():
        if x is None:
            continue
        if k in ("doi4_pct", "doi1_pct", "ret_pct", "impulse_pct"):
            p[k.replace("_pct", "")] = fmt_signed_pct(x, lang)
        elif k in ("range4_pct", "range_pct", "rv_pct", "p90_pct", "jump_pct"):
            p[k.replace("_pct", "")] = fmt_plain_pct(x, lang)
        elif k in ("ratio_pct", "recovery_pct", "depth_pct"):
            p[k.replace("_pct", "")] = f"{round(float(x)):d}%"
        elif k == "z":
            p["z"] = ("+" if x > 0 else "−") + _num(abs(x), lang)
        elif k == "dvol":
            p["dvol"] = _num(x, lang)
        elif k in ("bid_usd", "ask_usd"):
            p[k.replace("_usd", "")] = fmt_usd(x, lang)
        elif k == "kind":
            p["name"] = _level_name(x, lang)
        elif k == "kinds":
            p["names"] = ", ".join(_level_name(y, lang) for y in x)
        elif k == "price":
            p["price"] = fmt_price(x, lang)
        elif k == "window_min":
            p["window"] = int(x)
        elif k == "lookback_min":
            p["window"] = int(x)
        elif k == "lookback_h":
            p["hours"] = int(x)
        else:
            p[k] = x
    return p


def state_text(m: Mapping[str, Any], lang: str) -> str:
    ls = m.get("live_state") or {}
    key, arm = ls.get("key"), ls.get("arm")
    p = _params(m, lang)
    if m.get("relevance") == "CONTEXT" and key == "M02_OI_CONFIRMED_IMPULSE":
        return t(lang, "rev_st_M02_OI_CONFIRMED_IMPULSE_LABEL")
    for k in (f"rev_st_{key}_{arm}" if arm else None, f"rev_st_{key}"):
        if not k:
            continue
        try:
            return t(lang, k, **p)
        except KeyError:
            continue
    return key or m["finding_id"]


def line(m: Mapping[str, Any], lang: str) -> str:
    """The surface line for one match."""
    effect = ((m.get("historical_effect") or {}).get(lang) or (m.get("historical_effect") or {}).get("ru", "")).rstrip(".")
    if m.get("relevance") == "CONDITIONAL":
        out = t(lang, "rev_line_conditional", state=state_text(m, lang),
                verdict=t(lang, "rev_verdict_" + m["status"].lower()), effect=effect, id=_e(m["finding_id"]))
    else:
        out = t(lang, "rev_line_" + m["status"].lower(), state=state_text(m, lang), effect=effect,
                id=_e(m["finding_id"]))
    return assert_descriptive(out, lang)


def surface_lines(evidence: Optional[Mapping[str, Any]], surface: str, lang: str, *, limit: int = 2,
                  now: Optional[datetime] = None, since: Optional[datetime] = None,
                  topics: Optional[Sequence[str]] = None) -> list:
    """At most `limit` lines for a main surface (hierarchy, one per topic, vetoes removed)."""
    from .research_evidence import select
    try:
        return [line(m, lang) for m in select(evidence, surface, limit=limit, now=now, since=since, topics=topics)]
    except Exception:  # noqa: BLE001 - research context never breaks a message
        return []


def _reason_text(reason: str, lang: str) -> str:
    base = str(reason).split(":", 1)[0]
    try:
        return t(lang, "rev_reason_" + base)
    except KeyError:
        return base


def _zone_lines(evidence: Mapping[str, Any], levels: Optional[Mapping[str, Any]], lang: str) -> list:
    """What the research found about touches of the shown levels, if price gets there: per level its price
    and names, then the strongest conditional finding (the line /levels prints with the main surfaces on)."""
    from .decision_format import zone_names, zone_price
    zones, lv, out = evidence.get("zones") or {}, levels or {}, []
    for side, arrow in (("above", "↑"), ("below", "↓")):
        for k, conds in enumerate(zones.get(side) or ()):
            shown = lv.get(side) or []
            if not conds or k >= len(shown):
                continue
            out.append(t(lang, "rev_tab_zone", arrow=arrow, price=zone_price(shown[k], lang),
                         name=_e(zone_names(shown[k], lang, limit=2))))
            out.append(line(conds[0], lang))
    return out


def _alert_lines(evidence: Mapping[str, Any], lang: str) -> list:
    """The matches recorded with the last day's level and sharp-move alerts (the lines the alert prints
    with the main surfaces on), newest first."""
    from .decision_format import level_name
    from .i18n import fmt_price, fmt_signed_pct
    out = []
    for a in evidence.get("alerts") or ():
        lines = surface_lines({"matches": a.get("matches") or []}, "level_alert" if a["kind"] == "level" else "move_alert",
                              lang, limit=2)
        if not lines:
            continue
        clock = fmt_clock(datetime.fromisoformat(a["at"]), lang)
        if a["kind"] == "level":
            out.append(t(lang, "rev_tab_alert_level", clock=clock, price=fmt_price(a["level"], lang),
                         name=_e(level_name({"kind": a.get("level_kind")}, lang))))
        else:
            out.append(t(lang, "rev_tab_alert_move", clock=clock, move=fmt_signed_pct(a.get("move_pct") or 0.0, lang)))
        out.extend(lines)
    return out


def details_text(evidence: Optional[Mapping[str, Any]], lang: str, *, now: datetime, max_unavailable: int = 12,
                 levels: Optional[Mapping[str, Any]] = None) -> str:
    """The research Details tab: every running match with its comparator, N, replication and
    limits; vetoed ones marked; what the research found about touches of the shown levels; the
    matches of the last day's alerts; the live-relevant findings that cannot be checked now."""
    from .research_evidence import current, rank_key
    lines = [t(lang, "rev_tab_head", clock=fmt_clock(now, lang))]
    ms = sorted(current((evidence or {}).get("matches") or (), now=now), key=rank_key)
    if not ms:
        lines.append(t(lang, "rev_tab_none"))
    for m in ms:
        effect = (m.get("historical_effect") or {}).get(lang, "").rstrip(".")
        lines.append(t(lang, "rev_tab_item", id=_e(m["finding_id"]), status=t(lang, "rev_status_" + m["status"].lower()),
                       state=state_text(m, lang), effect=effect))
        n = m.get("sample_size")
        lines.append(t(lang, "rev_tab_meta", comparator=(m.get("comparator") or {}).get(lang, ""),
                       n="—" if n is None else f"{int(n):,}".replace(",", " "),
                       replication=(m.get("replication_status") or {}).get(lang, ""),
                       limitations=(m.get("limitations") or {}).get(lang, "")))
        if m.get("vetoed_by"):
            lines.append(t(lang, "rev_tab_vetoed", by=_e(m["vetoed_by"])))
    for head, extra in (("rev_tab_zones_head", _zone_lines(evidence or {}, levels, lang)),
                        ("rev_tab_alerts_head", _alert_lines(evidence or {}, lang))):
        if extra:
            lines += ["", t(lang, head)] + extra
    un = list((evidence or {}).get("unavailable") or ())
    if un:
        lines.append("")
        lines.append(t(lang, "rev_tab_unavailable_head"))
        for u in un[:max_unavailable]:
            lines.append(t(lang, "rev_tab_unavailable", id=_e(u["finding_id"]), reason=_reason_text(u["reason"], lang)))
    lines.append("")
    lines.append(t(lang, "rev_tab_footer"))
    return assert_descriptive("\n".join(lines), lang)
