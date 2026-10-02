"""Deterministic claim manifest and factual auditor. No model is involved here.

Claims are reconstructed from the text actually shown, parsed with the frozen
template patterns of the beta string catalog, and checked against structured
fields persisted as-of T (the /btc view payload, or the set-once trigger fields
of a push). A line that matches no known pattern, or a pattern that matches
ambiguously, becomes NOT_EVALUABLE; nothing missing is inferred.

Evaluation classes:
  AT_T_FACT         a statement about the market at render time, checked here;
  FORWARD_OUTCOME   the forward-direction slot (current templates make no forward
                    claim, so it is NO_DIRECTIONAL_CLAIM) and later observations;
  WORDING_JUDGMENT  an interpretive label: its inputs are checked here, its
                    strength is judged by Role B.

Claims are audit metadata only. They are never sent to Role A or to any user.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from beta.config import BetaConfig
from beta.context import level_label
from beta.formatter import (ForbiddenWordingError, _day_line, _hour_line, assert_descriptive, event_label,
                            plain_name)
from beta.i18n import MINUS, fmt_kyiv_date_hm, fmt_kyiv_hm, t

from .surface import html_to_text
from .timeline import KIND_BTC_VIEW, KIND_PUSH

CLAIM_MANIFEST_VERSION = "CLAIM_MANIFEST_V0"
AT_T_FACT, FORWARD_OUTCOME, WORDING_JUDGMENT = "AT_T_FACT", "FORWARD_OUTCOME", "WORDING_JUDGMENT"
CONSISTENT, CONTRADICTED, NOT_EVALUABLE = "CONSISTENT", "CONTRADICTED", "NOT_EVALUABLE"
NO_DIRECTIONAL_CLAIM = "NO_DIRECTIONAL_CLAIM"
STATUSES = (CONSISTENT, CONTRADICTED, NOT_EVALUABLE, NO_DIRECTIONAL_CLAIM)


@dataclass
class Claim:
    claim_id: str
    claim_type: str
    evaluation_class: str
    source_fields: Sequence[str]
    rendered_text_fragment: Optional[str]
    evaluation_rule: str
    directional_claim: bool = False
    horizon: Optional[str] = None
    status: str = NOT_EVALUABLE
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Manifest:
    item_id: str
    kind: str
    manifest_version: str = CLAIM_MANIFEST_VERSION
    claims: list = field(default_factory=list)

    def add(self, **kw) -> Claim:
        c = Claim(claim_id=f"{self.item_id}#c{len(self.claims) + 1}", **kw)
        self.claims.append(c)
        return c

    def as_dict(self) -> dict:
        return {"item_id": self.item_id, "kind": self.kind, "manifest_version": self.manifest_version,
                "claims": [c.as_dict() for c in self.claims]}


# ---- parsing helpers ------------------------------------------------------------------
_NUM = r"[+−-]?\d+(?:[.,]\d+)?"


def _num(s: str) -> float:
    return float(s.replace(MINUS, "-").replace(",", ".").replace("+", ""))


def _signed_text_negative(s: str) -> bool:
    return s.startswith(MINUS) or s.startswith("-")


def _pct_ok(fragment: str, value: Optional[float], nd: int) -> tuple:
    if value is None:
        return CONTRADICTED, "a number is shown but the source field is empty"
    shown = _num(fragment.rstrip("%"))
    tol = 0.5 * 10 ** (-nd) + 1e-9
    if abs(shown - value) > tol:
        return CONTRADICTED, f"shown {shown} vs source {value:.6g}"
    if value < 0 and not _signed_text_negative(fragment) or value > 0 and _signed_text_negative(fragment):
        return CONTRADICTED, "sign differs from the source"
    return CONSISTENT, f"source {value:.6g}"


def _ratio_ok(fragment: str, ratio: Optional[float], lang: str) -> tuple:
    if fragment == t(lang, "na"):
        return (CONSISTENT, "n/a with no ratio") if ratio is None else (CONTRADICTED, "n/a but a ratio exists")
    if ratio is None:
        return CONTRADICTED, "a ratio is shown but the source ratio is empty"
    if fragment == "10×+":
        return (CONSISTENT, f"source {ratio:.4g}") if ratio >= 10 else (CONTRADICTED, f"10×+ vs {ratio:.4g}")
    shown = _num(fragment.rstrip("×"))
    return (CONSISTENT, f"source {ratio:.4g}") if abs(shown - ratio) <= 0.05 + 1e-9 else \
        (CONTRADICTED, f"shown {shown} vs source {ratio:.4g}")


def _price_ok(fragment: str, value: Optional[float]) -> tuple:
    if value is None:
        return CONTRADICTED, "a price is shown but the source price is empty"
    shown = int(re.sub(r"[^\d]", "", fragment))
    return (CONSISTENT, f"source {value:.2f}") if shown == int(round(value)) else \
        (CONTRADICTED, f"shown {shown} vs source {value:.2f}")


def _arrow_ok(arrow: str, value: Optional[float]) -> tuple:
    if value is None:
        return CONTRADICTED, "an arrow is shown but the source value is empty"
    want = "↑" if value > 0 else "↓" if value < 0 else "·"
    return (CONSISTENT, f"source {value:.6g}") if arrow == want else (CONTRADICTED, f"{arrow} vs source {value:.6g}")


def _get(d: Any, *path: str) -> Any:
    for p in path:
        if not isinstance(d, Mapping):
            return None
        d = d.get(p)
    return d


def _dt(s: Optional[str]) -> Optional[datetime]:
    return None if not s else datetime.fromisoformat(s)


def _strip_disclaimer(text: str, lang: str) -> str:
    disc = html_to_text(t(lang, "disclaimer"))
    return text.replace(disc, "").strip()


def _forward_slot(m: Manifest, text: str, lang: str) -> None:
    try:
        assert_descriptive(text, lang)
        status, detail = NO_DIRECTIONAL_CLAIM, "template catalog has no forward claim; descriptive guard passes"
    except ForbiddenWordingError as exc:
        status, detail = NOT_EVALUABLE, f"forbidden wording present ({exc}); absence of a forward claim unproven"
    m.add(claim_type="FORWARD_DIRECTION_ASSERTION", evaluation_class=FORWARD_OUTCOME, source_fields=[],
          rendered_text_fragment=None, evaluation_rule="NO_FORWARD_CLAIM_TEMPLATE_V0",
          directional_claim=False, status=status, detail=detail)


# ---- /btc view ----------------------------------------------------------------------------
def _state_labels(lang: str) -> dict:
    return {t(lang, k): k for k in ("title_calm", "title_unusual", "title_calmed", "title_ended",
                                    "title_history", "title_incomplete")}


def _screen_state_rule(key: str, p: Mapping[str, Any]) -> tuple:
    status = p.get("product_status")
    head = p.get("headline")
    active, last = p.get("active_episode"), p.get("last_event")
    if status in ("DATA STALE", "DATA DEGRADED"):
        ok = key == "title_incomplete"
    elif key == "title_incomplete":
        ok = head == "DETECTOR NOT READY"
    elif key == "title_unusual":
        ok = active is not None or status in ("WATCH", "EVENT ACTIVE")
    elif key in ("title_calmed", "title_ended"):
        ok = last is not None and active is None
    elif key == "title_history":
        ok = head == "HISTORY BUILDING"
    else:
        ok = status == "NO ACTIVE EVENTS" and active is None and last is None and head == "NO ACTIVE EVENTS"
    return (CONSISTENT if ok else CONTRADICTED), f"product_status={status} headline={head}"


def _horizon_parts(m: Manifest, lang: str, line: str, h: str, p: Mapping[str, Any]) -> None:
    prefix = t(lang, "h1_prefix" if h == "1h" else "h24_prefix", body="")
    body = line[len(prefix):]
    block = _get(p, "horizons", h)
    legacy = p.get("horizons") is None
    for part in body.split(" · "):
        src = f"horizons.{h}"
        if re.fullmatch(_NUM + "%", part):
            value = (_get(p, "context_1h", "price_move_pct_median") if legacy and h == "1h"
                     else _get(block, "price_move_pct"))
            st, d = _pct_ok(part, value, 1)
            m.add(claim_type=f"HORIZON_{h.upper()}_PRICE_CHANGE", evaluation_class=AT_T_FACT,
                  source_fields=[("context_1h.price_move_pct_median" if legacy else f"{src}.price_move_pct")],
                  rendered_text_fragment=part, evaluation_rule="SIGNED_PCT_ROUNDED_1DP", horizon=h,
                  status=st, detail=d)
            continue
        vm = re.fullmatch(re.escape(t(lang, "h1_vol", ratio="")) + r"(.+)", part)
        rm = re.fullmatch(re.escape(t(lang, "h1_range", ratio="")) + r"(.+)", part)
        om = re.fullmatch(re.escape(t(lang, "h_oi", pct="")) + r"(" + _NUM + "%)", part)
        if part == t(lang, "h_vol_partial"):
            ok = bool(_get(block, "volume_partial"))
            m.add(claim_type=f"HORIZON_{h.upper()}_VOLUME_PARTIAL", evaluation_class=AT_T_FACT,
                  source_fields=[f"{src}.volume_partial"], rendered_text_fragment=part,
                  evaluation_rule="FLAG_EQUALS", horizon=h, status=CONSISTENT if ok else CONTRADICTED)
        elif vm and not legacy:
            st, d = _ratio_ok(vm.group(1), _get(block, "volume_ratio"), lang)
            m.add(claim_type=f"HORIZON_{h.upper()}_VOLUME_RATIO", evaluation_class=AT_T_FACT,
                  source_fields=[f"{src}.volume_ratio"], rendered_text_fragment=part,
                  evaluation_rule="RATIO_ROUNDED_1DP", horizon=h, status=st, detail=d)
        elif rm and not legacy:
            st, d = _ratio_ok(rm.group(1), _get(block, "range_ratio"), lang)
            m.add(claim_type=f"HORIZON_{h.upper()}_RANGE_RATIO", evaluation_class=AT_T_FACT,
                  source_fields=[f"{src}.range_ratio"], rendered_text_fragment=part,
                  evaluation_rule="RATIO_ROUNDED_1DP", horizon=h, status=st, detail=d)
        elif om and not legacy:
            st, d = _pct_ok(om.group(1), _get(block, "oi_change_pct"), 1)
            m.add(claim_type=f"HORIZON_{h.upper()}_OI_CHANGE", evaluation_class=AT_T_FACT,
                  source_fields=[f"{src}.oi_change_pct"], rendered_text_fragment=part,
                  evaluation_rule="SIGNED_PCT_ROUNDED_1DP", horizon=h, status=st, detail=d)
        else:
            m.add(claim_type="UNRECOGNIZED_FRAGMENT", evaluation_class=AT_T_FACT, source_fields=[],
                  rendered_text_fragment=part, evaluation_rule="LEGACY_PATTERN_UNKNOWN", horizon=h,
                  status=NOT_EVALUABLE, detail="no V0 rule for this fragment (legacy or unparsed)")


def _reading_parts(cfg: BetaConfig, m: Manifest, lang: str, reading: str, anchor: Mapping[str, Any]) -> None:
    arrows = {"part_price": ("price_move_pct", "PRICE_ARROW"), "part_oi": ("oi_change_pct", "OI_ARROW"),
              "part_taker": ("taker_delta_notional_usd", "TAKER_ARROW")}
    levels = {t(lang, "level_" + k): k for k in ("normal", "elevated", "high", "extreme")}
    for part in reading.split(" · "):
        done = False
        for key, (fld, ctype) in arrows.items():
            mm = re.fullmatch(re.escape(t(lang, key, arrow="")) + r"([↑↓·])", part)
            if mm:
                st, d = _arrow_ok(mm.group(1), _get(anchor, fld, "value"))
                m.add(claim_type=f"EVENT_BUCKET_{ctype}", evaluation_class=AT_T_FACT,
                      source_fields=[f"anchor.view.{fld}.value"], rendered_text_fragment=part,
                      evaluation_rule="ARROW_EQUALS_SIGN", status=st, detail=d)
                done = True
        vm = re.fullmatch(re.escape(t(lang, "part_vol", level="")) + r"(.+)", part)
        if vm and vm.group(1) in levels:
            src = anchor.get("volume_notional_usd") or {}
            want = level_label(cfg, src.get("rank"), src.get("tier"))
            st = CONSISTENT if want == levels[vm.group(1)] else CONTRADICTED
            m.add(claim_type="EVENT_BUCKET_VOLUME_LEVEL", evaluation_class=WORDING_JUDGMENT,
                  source_fields=["anchor.view.volume_notional_usd.rank", "anchor.view.volume_notional_usd.tier"],
                  rendered_text_fragment=part, evaluation_rule="LEVEL_LABEL_FROM_PERCENTILE_V0", status=st,
                  detail=f"label from rank={src.get('rank')} tier={src.get('tier')} is {want}")
            done = True
        lm = re.search(r"(\d+)/(\d+)", part)
        if not done and lm:
            side = None
            for s in ("long", "short"):
                if t(lang, "liq_count", Side=t(lang, "liq_" + s + "_name"), side=t(lang, "side_" + s),
                     votes=lm.group(1), eligible=lm.group(2)) == part:
                    side = s
            liq = _get(anchor, "liquidations", side or "") or {}
            if side is None:
                m.add(claim_type="UNRECOGNIZED_FRAGMENT", evaluation_class=AT_T_FACT, source_fields=[],
                      rendered_text_fragment=part, evaluation_rule="LEGACY_PATTERN_UNKNOWN", status=NOT_EVALUABLE,
                      detail="liquidation fragment did not match the catalog")
            else:
                ok = (int(lm.group(1)), int(lm.group(2))) == (len(liq.get("voting") or []),
                                                              len(liq.get("eligible") or []))
                m.add(claim_type="EVENT_BUCKET_LIQUIDATION_VENUE_COUNT", evaluation_class=AT_T_FACT,
                      source_fields=[f"anchor.view.liquidations.{side}.voting",
                                     f"anchor.view.liquidations.{side}.eligible"],
                      rendered_text_fragment=part, evaluation_rule="VOTES_OVER_ELIGIBLE_COUNT",
                      status=CONSISTENT if ok else CONTRADICTED)
            done = True
        if not done:
            m.add(claim_type="UNRECOGNIZED_FRAGMENT", evaluation_class=AT_T_FACT, source_fields=[],
                  rendered_text_fragment=part, evaluation_rule="LEGACY_PATTERN_UNKNOWN", status=NOT_EVALUABLE,
                  detail="no V0 rule for this fragment")


_WHY_KEYS = {"oi_fell_drop": (False, False), "oi_fell_rise": (True, False),
             "oi_rose_rise": (True, True), "oi_rose_drop": (False, True)}


def _view_claims(cfg: BetaConfig, item, payload: Mapping[str, Any]) -> Manifest:
    lang = item.lang
    m = Manifest(item.item_id, item.kind)
    text = html_to_text(item.html)
    _forward_slot(m, text, lang)
    body = _strip_disclaimer(text, lang)
    lines = [ln for ln in body.split("\n") if ln.strip()]
    focus = payload.get("active_episode") or payload.get("last_event")
    anchor = _get(focus, "anchor", "view") or {}
    labels = _state_labels(lang)
    for i, line in enumerate(lines):
        if i == 0:
            tm = re.fullmatch(r"BTC (?:(?P<price>[\d, ]+) )?· (?P<state>.+)", line)
            if not tm:
                m.add(claim_type="UNRECOGNIZED_FRAGMENT", evaluation_class=AT_T_FACT, source_fields=[],
                      rendered_text_fragment=line, evaluation_rule="LEGACY_PATTERN_UNKNOWN", status=NOT_EVALUABLE)
                continue
            if tm.group("price"):
                st, d = _price_ok(tm.group("price"), _get(payload, "now", "reference_price"))
                m.add(claim_type="PRICE_LEVEL", evaluation_class=AT_T_FACT, source_fields=["now.reference_price"],
                      rendered_text_fragment=tm.group("price"), evaluation_rule="WHOLE_USD_ROUNDED",
                      status=st, detail=d)
            key = labels.get(tm.group("state"))
            if key is None:
                m.add(claim_type="SCREEN_STATE", evaluation_class=AT_T_FACT, source_fields=["product_status"],
                      rendered_text_fragment=tm.group("state"), evaluation_rule="LEGACY_PATTERN_UNKNOWN",
                      status=NOT_EVALUABLE)
            else:
                st, d = _screen_state_rule(key, payload)
                m.add(claim_type="SCREEN_STATE", evaluation_class=WORDING_JUDGMENT,
                      source_fields=["product_status", "headline", "active_episode", "last_event"],
                      rendered_text_fragment=tm.group("state"), evaluation_rule="SCREEN_STATE_TABLE_V0",
                      status=st, detail=d)
            continue
        if line.startswith(t(lang, "h1_prefix", body="")) and line != t(lang, "h1_incomplete"):
            _horizon_parts(m, lang, line, "1h", payload)
            continue
        if line.startswith(t(lang, "h24_prefix", body="")) and line != t(lang, "h24_incomplete"):
            _horizon_parts(m, lang, line, "24h", payload)
            continue
        if line in (t(lang, "h1_incomplete"), t(lang, "h24_incomplete")):
            h = "1h" if line == t(lang, "h1_incomplete") else "24h"
            try:
                want = (_hour_line if h == "1h" else _day_line)(payload, lang)
                st = CONSISTENT if want == line else CONTRADICTED
            except Exception:  # noqa: BLE001 - payload shape the current template cannot read
                st = NOT_EVALUABLE
            m.add(claim_type=f"HORIZON_{h.upper()}_INCOMPLETE", evaluation_class=AT_T_FACT,
                  source_fields=[f"horizons.{h}"], rendered_text_fragment=line,
                  evaluation_rule="FROZEN_TEMPLATE_REPRODUCES_INCOMPLETE_LINE", status=st)
            continue
        rm = re.fullmatch(r"(?:5м|5m) (\d\d:\d\d)–(\d\d:\d\d): (.+)", line)
        if rm:
            want = fmt_kyiv_hm(_dt(anchor["bucket_ts"])) if anchor.get("bucket_ts") else None
            m.add(claim_type="EVENT_BUCKET_WINDOW", evaluation_class=AT_T_FACT,
                  source_fields=["anchor.bucket_ts"], rendered_text_fragment=f"{rm.group(1)}–{rm.group(2)}",
                  evaluation_rule="KYIV_WINDOW_START_EQUALS_ANCHOR",
                  status=CONSISTENT if want == rm.group(1) else CONTRADICTED if want else NOT_EVALUABLE)
            _reading_parts(cfg, m, lang, rm.group(3), anchor)
            continue
        why = next((k for k in _WHY_KEYS if t(lang, k) == line), None)
        if why:
            up_want, oi_up_want = _WHY_KEYS[why]
            price, oi = _get(anchor, "price_move_pct", "value"), _get(anchor, "oi_change_pct", "value")
            ok = price is not None and oi is not None and (price > 0) == up_want and (oi > 0) == oi_up_want
            m.add(claim_type="PRICE_OI_RELATION", evaluation_class=WORDING_JUDGMENT,
                  source_fields=["anchor.view.price_move_pct.value", "anchor.view.oi_change_pct.value"],
                  rendered_text_fragment=line, evaluation_rule="SIGNS_MATCH_SENTENCE_V0",
                  status=CONSISTENT if ok else CONTRADICTED, detail=f"price={price} oi={oi}")
            continue
        dm = re.fullmatch(r"(?:(?P<status>.+) · )?(?:данные|data) (?P<hm>\d\d:\d\d) .+", line)
        if dm:
            through = _dt(payload.get("data_through"))
            req = _dt(payload.get("requested_at"))
            if through is None:
                st, d = CONTRADICTED, "a data time is shown but data_through is empty"
            elif fmt_kyiv_hm(through) != dm.group("hm"):
                st, d = CONTRADICTED, f"shown {dm.group('hm')} vs {fmt_kyiv_hm(through)}"
            elif req is not None and through > req:
                st, d = CONTRADICTED, "data time is later than the request time"
            else:
                age = None if req is None else int((req - through).total_seconds() // 60)
                st, d = CONSISTENT, f"data age at request {age} min"
            m.add(claim_type="TIMESTAMP_DATA_THROUGH", evaluation_class=AT_T_FACT,
                  source_fields=["data_through", "requested_at"], rendered_text_fragment=dm.group("hm"),
                  evaluation_rule="KYIV_HM_EQUALS_AND_NOT_AFTER_REQUEST", status=st, detail=d)
            if dm.group("status") == t(lang, "still_active"):
                m.add(claim_type="EVENT_STILL_ACTIVE", evaluation_class=AT_T_FACT, source_fields=["active_episode"],
                      rendered_text_fragment=dm.group("status"), evaluation_rule="ACTIVE_EPISODE_PRESENT",
                      status=CONSISTENT if payload.get("active_episode") else CONTRADICTED)
            elif dm.group("status") and dm.group("status").startswith(t(lang, "notable_none", span="")[:12]):
                ok = payload.get("active_episode") is None and payload.get("last_event") is None
                m.add(claim_type="NO_NOTABLE_EVENT_IN_RETENTION", evaluation_class=AT_T_FACT,
                      source_fields=["active_episode", "last_event"], rendered_text_fragment=dm.group("status"),
                      evaluation_rule="NO_ACTIVE_OR_RETAINED_EPISODE",
                      status=CONSISTENT if ok else CONTRADICTED)
            elif dm.group("status"):
                m.add(claim_type="EVENT_END_STATUS", evaluation_class=AT_T_FACT, source_fields=["last_event"],
                      rendered_text_fragment=dm.group("status"), evaluation_rule="NO_V0_RULE",
                      status=NOT_EVALUABLE, detail="end-status wording has no V0 rule")
            continue
        if line == t(lang, "no_unusual"):
            ok = payload.get("active_episode") is None
            m.add(claim_type="NO_UNUSUAL_STATE", evaluation_class=WORDING_JUDGMENT, source_fields=["active_episode"],
                  rendered_text_fragment=line, evaluation_rule="NO_ACTIVE_EPISODE",
                  status=CONSISTENT if ok else CONTRADICTED)
            continue
        if focus and plain_name(focus["event_type"], lang) in line:
            m.add(claim_type="EVENT_NAME_AND_TIMING", evaluation_class=WORDING_JUDGMENT,
                  source_fields=["active_episode.event_type", "last_event.event_type", "last_event.terminal_at"],
                  rendered_text_fragment=line, evaluation_rule="EVENT_TYPE_LABEL_MATCHES",
                  status=CONSISTENT, detail="label matches the persisted event type; timing wording has no V0 rule")
            continue
        m.add(claim_type="UNRECOGNIZED_FRAGMENT", evaluation_class=AT_T_FACT, source_fields=[],
              rendered_text_fragment=line, evaluation_rule="LEGACY_PATTERN_UNKNOWN", status=NOT_EVALUABLE,
              detail="no V0 rule for this line")
    return m


# ---- push ------------------------------------------------------------------------------------
def _push_claims(item, episode: Mapping[str, Any]) -> Manifest:
    lang = item.lang
    m = Manifest(item.item_id, item.kind)
    text = html_to_text(item.html)
    _forward_slot(m, text, lang)
    lines = [ln for ln in _strip_disclaimer(text, lang).split("\n") if ln.strip()]
    title = t(lang, "push_title", name=event_label(episode["event_type"], lang))
    m.add(claim_type="PUSH_EVENT_LABEL", evaluation_class=WORDING_JUDGMENT, source_fields=["episode.event_type"],
          rendered_text_fragment=lines[0] if lines else None, evaluation_rule="EVENT_TYPE_LABEL_MATCHES",
          status=CONSISTENT if lines and lines[0] == title else NOT_EVALUABLE)
    when = fmt_kyiv_date_hm(episode["triggered_at"], lang)
    dline = t(lang, "push_decision", when=when)
    if dline in lines:
        ok = episode["triggered_at"] <= item.at
        m.add(claim_type="PUSH_DECISION_TIME", evaluation_class=AT_T_FACT, source_fields=["episode.triggered_at"],
              rendered_text_fragment=when, evaluation_rule="KYIV_TIME_EQUALS_AND_NOT_AFTER_ARRIVAL",
              status=CONSISTENT if ok else CONTRADICTED,
              detail=f"arrived {int((item.at - episode['triggered_at']).total_seconds())}s after the decision")
    else:
        m.add(claim_type="PUSH_DECISION_TIME", evaluation_class=AT_T_FACT, source_fields=["episode.triggered_at"],
              rendered_text_fragment=None, evaluation_rule="KYIV_TIME_EQUALS_AND_NOT_AFTER_ARRIVAL",
              status=NOT_EVALUABLE, detail="decision line not found")
    pm = next((re.search(r"(?P<p>[\d, ]+) \((?P<v>[^)]*)\)$", ln) for ln in lines
               if ln.startswith(t(lang, "push_close", price="", venues="")[:10])), None)
    if pm:
        st, d = _price_ok(pm.group("p"), episode.get("reference_price"))
        m.add(claim_type="PUSH_REFERENCE_PRICE", evaluation_class=AT_T_FACT, source_fields=["episode.reference_price"],
              rendered_text_fragment=pm.group("p").strip(), evaluation_rule="WHOLE_USD_ROUNDED", status=st, detail=d)
        shown = [v.strip() for v in pm.group("v").split(",") if v.strip()]
        ok = len(shown) == len(episode.get("reference_exchanges") or ())
        m.add(claim_type="PUSH_REFERENCE_VENUES", evaluation_class=AT_T_FACT,
              source_fields=["episode.reference_exchanges"], rendered_text_fragment=pm.group("v"),
              evaluation_rule="VENUE_COUNT_EQUALS", status=CONSISTENT if ok else CONTRADICTED)
    m.add(claim_type="PUSH_RULE_DESCRIPTION", evaluation_class=AT_T_FACT, source_fields=["tape.rule_evaluations"],
          rendered_text_fragment=lines[2] if len(lines) > 2 else None, evaluation_rule="RULE_FIRED_ON_TAPE",
          status=NOT_EVALUABLE, detail="the tape row behind the trigger is not part of the replay bundle")
    return m


def _surface_claims(item_id: str, kind: str, text: str, lang: str) -> Manifest:
    m = Manifest(item_id, kind)
    _forward_slot(m, text, lang)
    m.add(claim_type="SURFACE_CONTENT", evaluation_class=AT_T_FACT, source_fields=[],
          rendered_text_fragment=None, evaluation_rule="NO_V0_CLAIM_RULES_FOR_SURFACE",
          status=NOT_EVALUABLE, detail=f"{kind}: no V0 claim rules")
    return m


def build_manifest(cfg: BetaConfig, item, *, payload: Optional[Mapping[str, Any]] = None,
                   episode: Optional[Mapping[str, Any]] = None) -> Manifest:
    if item.kind == KIND_BTC_VIEW:
        return _view_claims(cfg, item, payload or {})
    if item.kind == KIND_PUSH:
        return _push_claims(item, episode or {})
    return _surface_claims(item.item_id, item.kind, html_to_text(item.html), item.lang)


def surface_manifest(item_id: str, kind: str, html_text: str, lang: str) -> Manifest:
    return _surface_claims(item_id, kind, html_to_text(html_text), lang)


def summarize_claims(manifests: Sequence[Manifest]) -> dict:
    total = {s: 0 for s in STATUSES}
    by_type: dict = {}
    by_class: dict = {}
    for man in manifests:
        for c in man.claims:
            total[c.status] += 1
            by_type.setdefault(c.claim_type, {s: 0 for s in STATUSES})[c.status] += 1
            by_class.setdefault(c.evaluation_class, {s: 0 for s in STATUSES})[c.status] += 1
    return {"total_claims": sum(total.values()), **total,
            "by_claim_type": dict(sorted(by_type.items())), "by_evaluation_class": dict(sorted(by_class.items()))}
