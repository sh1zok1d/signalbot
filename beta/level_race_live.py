"""Level race, live side: the one place for names, events at their landmarks, the scored outcome
and what a surface shows (FORECAST_LAYER_DECISION_V1 §5–§6a; design note
docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md §0, §9, §10).

ОПГ-2 module (ORCHESTRATION_V1 §4). The event is the product's structural first touch
(`beta.levels.structural_first_touches`, pinned to the #352 constructor); the HIST numbers and
B0 come from `beta.level_race` (F1). Nothing here changes a corridor, a touch chance, a push
decision or another claim.

Day 0 is `HIST`: the 2020–2024 shares of the event's cell beside their «обычно» (B0), in the
past tense, prices only, the three outcomes together. The switch to the model states is one
setting (`level_race.model_states_enabled`); until a model is frozen it changes nothing here and
the mode is recorded on every journal row.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from .hist_series import BAR_MS, Bars, from_ms, to_ms

LIVE_VERSION = "BETA_LEVEL_RACE_LIVE_V1"
WRITE_WINDOW_MS = 10 * 60_000          # a landmark is journaled only within 10 min of its close
MIN_PRESENT = 0.9                      # #352: share of finite window bars needed to score

# ---- names (the measurement-contract registry; FORECAST_LAYER §8) ------------------------------
SETTINGS = {"journal": "level_race.journal_enabled", "display": "level_race.display_enabled",
            "model_states": "level_race.model_states_enabled", "push_trigger": "level_race.push_trigger"}
PUSH_TRIGGERS = ("legacy", "structural")     # the level-touch push: exact price (legacy) or the #352 zone entry
CLASSES = {
    "L2_LEVEL_RACE_HIST_T0_4H": {"landmark": "T0", "rule": "LEVEL_RACE_4H_V1", "display": ("alert", "levels", "check"),
                                 "templates": ("LR_PUSH_HIST_V1", "LR_HIST_V1", "LR_HIST_LOW_N_V1"), "from": "Day 0"},
    "L2_LEVEL_RACE_HIST_T15_4H": {"landmark": "T15", "rule": "LEVEL_RACE_4H_V1", "display": ("levels", "check"),
                                  "templates": ("LR_HIST_V1", "LR_HIST_LOW_N_V1"), "from": "Day 0"},
    # model states and the shadow streams: journaled from the model freeze (not written yet)
    "L3_LEVEL_RACE_T0_4H": {"landmark": "T0", "rule": "LEVEL_RACE_4H_V1", "display": ("alert",),
                            "templates": ("LR_PUSH_L3H_V1", "LR_PUSH_L3L_V1", "LR_PUSH_FB_V1", "LR_PUSH_OFF_V1"),
                            "from": "model freeze"},
    "L3_LEVEL_RACE_T15_4H": {"landmark": "T15", "rule": "LEVEL_RACE_4H_V1", "display": ("levels", "check"),
                             "templates": ("LR_L3H_V1", "LR_L3L_V1", "LR_FB_V1", "LR_OFF_V1"), "from": "model freeze"},
    "L3_GENERIC_RACE_4H": {"landmark": None, "rule": "GENERIC_RACE_4H_V1", "display": (), "templates": (),
                           "from": "model freeze"},      # journal only, never shown
}
# template id -> i18n key
TEMPLATE_KEYS = {"LR_HIST_V1": "lr_hist_v1", "LR_PUSH_HIST_V1": "lr_push_hist_v1", "LR_HIST_LOW_N_V1": "lr_hist_low_n_v1"}
HIST_CLASS = {"T0": "L2_LEVEL_RACE_HIST_T0_4H", "T15": "L2_LEVEL_RACE_HIST_T15_4H"}
LANDMARK_BARS = {"T0": 0, "T15": 2}     # landmark = close of bar j + this
OUTCOMES = ("UP", "DN", "NEITHER")
MODEL_VERSION: Optional[str] = None    # the freeze commit of F1's predictor; None until it exists


def setting(cfg, name: str) -> bool:
    """`level_race.<name>`; an absent section or key is off."""
    raw = getattr(cfg, "raw", None) or {}
    return bool((raw.get("level_race") or {}).get(name, False))


def push_trigger(cfg) -> str:
    """The one switch between the two level-touch triggers (architect, P2 = A): `structural` makes the
    push the #352 event with its T0 race line; anything else keeps the legacy exact-price touch."""
    raw = getattr(cfg, "raw", None) or {}
    v = (raw.get("level_race") or {}).get("push_trigger", "legacy")
    return v if v in PUSH_TRIGGERS else "legacy"


def mode(cfg) -> str:
    """HIST until a frozen model exists; the switch is recorded, never applied without one."""
    return "MODEL" if setting(cfg, "model_states_enabled") and MODEL_VERSION is not None else "HIST"


# ---- events and landmarks --------------------------------------------------------------------
def _bar(b: Bars, ms: int) -> Optional[int]:
    i = (int(ms) - b.t0) // BAR_MS
    return int(i) if 0 <= i < b.n and b.t0 + i * BAR_MS == int(ms) else None


def landmark_ms(ev: Mapping[str, Any], landmark: str) -> int:
    return int(ev["touch_open_ms"]) + (1 + LANDMARK_BARS[landmark]) * BAR_MS


def _geo(ev: Mapping[str, Any]) -> Optional[dict]:
    from .level_race import geometry
    if not ev.get("eligible") or ev.get("sigma") is None:
        return None
    return geometry(float(ev["zone_low"]), float(ev["zone_high"]), float(ev["sigma"]), int(ev["side"]))


def landmark_view(b: Bars, ev: Mapping[str, Any], landmark: str, table: Mapping[str, Any]) -> Optional[dict]:
    """The HIST statement of one event at one landmark from bars closed by then, or None when the
    landmark has none: T15 after a barrier or a both-barrier bar on j+1, j+2 (design §0), or a bar
    missing at the landmark."""
    from .level_race import hist_line, t15_eligible
    geo = _geo(ev)
    j = _bar(b, int(ev["touch_open_ms"]))
    if geo is None or j is None:
        return None
    k = j + LANDMARK_BARS[landmark]
    if k >= b.n or not math.isfinite(b.close[k]):
        return None
    if landmark == "T15" and not t15_eligible(b.high, b.low, j, geo):
        return None
    line = hist_line(table, landmark=landmark, kind=ev["kind"], price=float(b.close[k]), geo=geo,
                     sigma=float(ev["sigma"]))
    return {**line, "landmark": landmark, "event_id": ev["event_id"], "kind": ev["kind"],
            "member_kinds": list(ev.get("member_kinds") or ()), "family": ev["family"],
            "struct_side": int(ev["struct_side"]), "side": int(ev["side"]), "zone_low": float(ev["zone_low"]),
            "zone_high": float(ev["zone_high"]), "anchor_price": float(ev["anchor_price"]),
            "sigma": float(ev["sigma"]), "x": float(geo["x"]), "touch_open_ms": int(ev["touch_open_ms"]),
            "landmark_ms": landmark_ms(ev, landmark), "end_ms": int(ev["window_end_ms"]),
            "position": float(b.close[k])}


def events(b: Optional[Bars]) -> list:
    if b is None or b.n == 0:
        return []
    from .levels import structural_first_touches
    return [e for e in structural_first_touches(b) if e["eligible"]]


def due_landmarks(b: Optional[Bars], now: datetime, table: Mapping[str, Any]) -> list:
    """(landmark view) for every eligible event whose T0 / T15 closed within the last WRITE_WINDOW_MS:
    what the journal writes, shown or not, before the outcome."""
    now_ms = to_ms(now)
    out = []
    for ev in events(b):
        for lm in ("T0", "T15"):
            at = landmark_ms(ev, lm)
            if at <= now_ms <= at + WRITE_WINDOW_MS and at <= b.end_ms:
                v = landmark_view(b, ev, lm, table)
                if v is not None:
                    out.append(v)
    return out


def _resolved_since(b: Bars, v: Mapping[str, Any], price: Optional[float]) -> bool:
    """A barrier was already reached after the landmark (closed bars, then the last price)."""
    j = _bar(b, v["touch_open_ms"])
    for k in range(j + LANDMARK_BARS[v["landmark"]] + 1, b.n):
        if (math.isfinite(b.high[k]) and b.high[k] >= v["p_up"]) or (math.isfinite(b.low[k]) and b.low[k] <= v["p_dn"]):
            return True
    return price is not None and not (v["p_dn"] < float(price) < v["p_up"])


def display_block(b: Optional[Bars], now: datetime, table: Optional[Mapping[str, Any]], *,
                  price: Optional[float] = None) -> dict:
    """What /levels and /check show for every event whose window is still open and whose race is not
    decided yet: the T0 statement until T15 (the push's full line, one tap away; none when the touch
    close lies outside the barrier pair), then the T15 statement. State OFF when the table did not load."""
    if table is None:
        return {"state": "OFF", "races": []}
    now_ms = to_ms(now)
    races = []
    for ev in events(b):
        if not (landmark_ms(ev, "T0") <= now_ms < int(ev["window_end_ms"])):
            continue
        lm = "T15" if now_ms >= landmark_ms(ev, "T15") else "T0"
        v = landmark_view(b, ev, lm, table)
        if v is None or v["outside_corridor"] or _resolved_since(b, v, price):
            continue
        races.append(_public(v))
    return {"state": "HIST", "races": races}


def push_view(b: Optional[Bars], ev: Mapping[str, Any], table: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """The T0 line of the level-touch push, or None (no table, an ineligible event, or the touch close
    outside the barrier pair: the record is still journaled, flagged)."""
    if table is None or b is None or not ev.get("eligible"):
        return None
    v = landmark_view(b, ev, "T0", table)
    return None if v is None or v["outside_corridor"] else _public(v)


def _public(v: Mapping[str, Any]) -> dict:
    keep = ("class", "event_id", "landmark", "kind", "member_kinds", "cell", "ladder_level", "template", "n",
            "h", "b", "k_pp", "p_up", "p_dn", "end_ms", "landmark_ms", "touch_open_ms", "zone_low", "zone_high")
    return {k: v[k] for k in keep if k in v}


def subject_key(v: Mapping[str, Any]) -> str:
    return f"{v['event_id']}:{v['landmark']}"


# ---- outcome (rule LEVEL_RACE_4H_V1) ----------------------------------------------------------
def classify(b: Bars, *, touch_open_ms: int, landmark: str, p_up: float, p_dn: float) -> Optional[dict]:
    """The #352 `classify` on the original window from the landmark: bars j+1+L .. j+48 (L = 0 at T0,
    2 at T15), 5m highs and lows, at least 90 % finite. UP / DN / NEITHER, or AMBIGUOUS when one bar
    reaches both first. None while the window is not in the bars yet or is not usable."""
    from .level_race import WINDOW_BARS
    j = _bar(b, touch_open_ms)
    if j is None:
        return None
    a, z = j + 1 + LANDMARK_BARS[landmark], j + WINDOW_BARS
    if z >= b.n:
        return None
    hh, ll = b.high[a:z + 1], b.low[a:z + 1]
    ok = np.isfinite(hh) & np.isfinite(ll)
    cov = float(ok.mean()) if ok.size else 0.0
    if cov < MIN_PRESENT:
        return {"usable": False, "coverage": round(cov, 4)}
    up = np.flatnonzero(ok & (hh >= p_up))
    dn = np.flatnonzero(ok & (ll <= p_dn))
    fu = int(up[0]) if up.size else None
    fd = int(dn[0]) if dn.size else None
    if fu is None and fd is None:
        y, first = "NEITHER", None
    elif fu is not None and fd is not None and fu == fd:
        y, first = "AMBIGUOUS", fu
    elif fd is None or (fu is not None and fu < fd):
        y, first = "UP", fu
    else:
        y, first = "DN", fd
    return {"usable": True, "outcome": y, "coverage": round(cov, 4),
            "first_bar_open": None if first is None else from_ms(b.t0 + (a + first) * BAR_MS).isoformat()}


# ---- report (pure) -----------------------------------------------------------------------------
def _ll(p: Mapping[str, float], y: str) -> float:
    return -math.log(max(float(p[{"UP": "up", "DN": "dn", "NEITHER": "neither"}[y]]), 1e-12))


def _brier(p: Mapping[str, float], y: str) -> float:
    return sum((float(p[k]) - (1.0 if o == y else 0.0)) ** 2 for k, o in (("up", "UP"), ("dn", "DN"),
                                                                           ("neither", "NEITHER")))


def report(rows: Sequence[Mapping[str, Any]]) -> dict:
    """«говорили h → было» per class and per cell (mean shown share vs the observed share per outcome),
    with log loss and Brier of the shown shares and of the event's own B0. AMBIGUOUS is excluded and
    counted; rows of both modes are reported separately (the dated switch, FORECAST_LAYER §6a)."""
    out: dict = {}
    for r in rows:
        key = (r["subject"].get("mode", "HIST"), r["subject"].get("cell"))
        out.setdefault(key, []).append(r)
    res = {"n": len(rows), "cells": {}}
    for (md, cell), rs in sorted(out.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        done = [r for r in rs if r.get("status") == "COMPLETE" and r["realized"].get("usable")]
        scored = [r for r in done if r["realized"]["outcome"] in OUTCOMES]
        rec = {"mode": md, "n": len(rs), "scored": len(scored), "ambiguous": len(done) - len(scored)}
        shown = [r for r in scored if r["numbers"].get("h")]
        if shown:
            rec["shown_h"] = {k: round(float(np.mean([r["numbers"]["h"][k] for r in shown])), 4) for k in ("up", "dn", "neither")}
            rec["observed"] = {k: round(float(np.mean([r["realized"]["outcome"] == o for r in shown])), 4)
                               for k, o in (("up", "UP"), ("dn", "DN"), ("neither", "NEITHER"))}
            rec["log_loss_h"] = round(float(np.mean([_ll(r["numbers"]["h"], r["realized"]["outcome"]) for r in shown])), 5)
            rec["brier_h"] = round(float(np.mean([_brier(r["numbers"]["h"], r["realized"]["outcome"]) for r in shown])), 5)
        if scored:
            rec["log_loss_b0"] = round(float(np.mean([_ll(r["numbers"]["event_b0"], r["realized"]["outcome"]) for r in scored])), 5)
            rec["brier_b0"] = round(float(np.mean([_brier(r["numbers"]["event_b0"], r["realized"]["outcome"]) for r in scored])), 5)
        res["cells"][f"{md}:{cell}"] = rec
    return res


def utc(ms: int) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
