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
    "L3_LEVEL_RACE_C1_T15_4H": {"landmark": "T15", "rule": "LEVEL_RACE_4H_V1", "display": (), "templates": (),
                                "from": "model freeze"},  # the C1 challenger's shadow record (LEVEL_RACE_LIVE_JOURNAL_V1)
    "L3_GENERIC_RACE_4H": {"landmark": None, "rule": "GENERIC_RACE_4H_V1", "display": (), "templates": (),
                           "from": "model freeze"},      # journal only, never shown
}
# template id -> i18n key
TEMPLATE_KEYS = {"LR_HIST_V1": "lr_hist_v1", "LR_PUSH_HIST_V1": "lr_push_hist_v1", "LR_HIST_LOW_N_V1": "lr_hist_low_n_v1",
                 "LR_L3H_V1": "lr_l3h_v1", "LR_L3L_V1": "lr_l3l_v1", "LR_FB_V1": "lr_fb_v1", "LR_OFF_V1": "lr_off_v1",
                 "LR_PUSH_L3H_V1": "lr_push_l3h_v1", "LR_PUSH_L3L_V1": "lr_push_l3l_v1", "LR_PUSH_FB_V1": "lr_push_fb_v1",
                 "LR_PUSH_OFF_V1": "lr_push_off_v1"}
HIST_CLASS = {"T0": "L2_LEVEL_RACE_HIST_T0_4H", "T15": "L2_LEVEL_RACE_HIST_T15_4H"}
L3_CLASS = {"T0": "L3_LEVEL_RACE_T0_4H", "T15": "L3_LEVEL_RACE_T15_4H"}
C1_CLASS = "L3_LEVEL_RACE_C1_T15_4H"
LANDMARK_BARS = {"T0": 0, "T15": 2}     # landmark = close of bar j + this
OUTCOMES = ("UP", "DN", "NEITHER")
MODEL_VERSION: Optional[str] = None    # the freeze commit of F1's predictor; None until it exists
PROVIDER = None                        # the frozen model side for the L3 journal (claims.record_level_race_l3); set with MODEL_VERSION


def setting(cfg, name: str) -> bool:
    """`level_race.<name>`; an absent section or key is off."""
    raw = getattr(cfg, "raw", None) or {}
    return bool((raw.get("level_race") or {}).get(name, False))


def push_trigger(cfg) -> str:
    """The one switch between the two level-touch triggers (architect, P2 = A): `structural` makes the
    push the #352 event; anything else keeps the legacy exact-price touch."""
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
    """The race geometry of the event itself (beta.levels is its one source: σ, X, P_UP, P_DN)."""
    if not ev.get("eligible") or ev.get("p_up") is None or ev.get("p_dn") is None:
        return None
    return {"x": float(ev["x"]), "p_up": float(ev["p_up"]), "p_dn": float(ev["p_dn"]), "beyond_is_up": int(ev["side"]) > 0}


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


def _after(b: Bars, closed_1m, v: Mapping[str, Any]) -> tuple:
    """Highs and lows of every closed bar after the landmark: the 5m tape and every closed 1m bar after
    the landmark (a barrier reached inside the current 5m bar, or inside a 5m bar the tape lacks for a
    missing minute, already hides the line)."""
    j = _bar(b, v["touch_open_ms"])
    a = j + LANDMARK_BARS[v["landmark"]] + 1
    highs, lows = list(b.high[a:]), list(b.low[a:])
    for r in closed_1m or ():
        if to_ms(r["ts"]) >= v["landmark_ms"]:
            highs.append(float(r["high"]))
            lows.append(float(r["low"]))
    return [h for h in highs if math.isfinite(h)], [x for x in lows if math.isfinite(x)]


def display_block(b: Optional[Bars], now: datetime, table: Optional[Mapping[str, Any]], *,
                  price: Optional[float] = None, closed_1m=()) -> dict:
    """What /levels and /check show for every event whose window is open and whose race is not decided:
    the T0 statement until T15 (the push's full line, one tap away; none when the touch close lies
    outside the barrier pair), then the T15 statement. Visibility is `beta.level_race.t15_visible`
    (architect, 2026-10-08): hidden once a barrier is reached on a closed bar after the landmark or the
    price is beyond P_UP / P_DN, and never back — the bars that hid it stay in the tape, so the same
    inputs give the same answer on every later request. State OFF when the table did not load."""
    from .level_race import t15_visible
    if table is None:
        return {"state": "OFF", "races": []}
    now_ms = to_ms(now)
    races = []
    for ev in events(b):
        if not (landmark_ms(ev, "T0") <= now_ms < int(ev["window_end_ms"])):
            continue
        v = landmark_view(b, ev, "T15", table) if now_ms >= landmark_ms(ev, "T15") else None
        if v is None and now_ms >= landmark_ms(ev, "T15"):
            continue                                    # no T15 statement: the race moved on j+1 / j+2
        if v is None:
            v = landmark_view(b, ev, "T0", table)
            if v is None or not v["display"]:
                continue
        highs, lows = _after(b, closed_1m, v)
        geo = {"p_up": v["p_up"], "p_dn": v["p_dn"]}
        if price is None or not t15_visible(highs, lows, price, geo, now_ms=now_ms, end_ms=v["end_ms"]):
            continue
        races.append(_public(v))
    return {"state": "HIST", "races": races}


def push_view(b: Optional[Bars], ev: Mapping[str, Any], table: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """The T0 line of the level-touch push, or None (no table, an ineligible event, or the touch close
    outside the barrier pair: the record is still journaled, flagged)."""
    if table is None or b is None or not ev.get("eligible"):
        return None
    v = landmark_view(b, ev, "T0", table)
    return None if v is None or not v["display"] else _public(v)


def _public(v: Mapping[str, Any]) -> dict:
    keep = ("class", "event_id", "landmark", "kind", "member_kinds", "cell", "ladder_level", "template", "n",
            "h", "b", "printed_h", "printed_b", "d_pp", "ci95_pp", "p_up", "p_dn", "end_ms", "landmark_ms",
            "touch_open_ms", "zone_low", "zone_high")
    return {k: v[k] for k in keep if k in v}


def subject_key(v: Mapping[str, Any]) -> str:
    return f"{v['event_id']}:{v['landmark']}"


# ---- model inputs at the landmarks (design §2.3, §8) ------------------------------------------
# The predictor's row for one event at one landmark, in the research row's keys
# (scripts/research/level_race_forecast_v1/events.landmark_rows) so the frozen model reads live and
# development rows the same way. Geometry, σ and B0 come only from the landmark view (beta.levels →
# beta.level_race); nothing is recomputed here. Pure; the model itself arrives with the freeze.
C1_TERM = "OVMM"                       # = research constants.C1_TERM
C1_VENUES = ("bybit", "okx")           # live klines_1m exchanges (canonical symbol), #363 Bybit / OKX perps
C1_EXCHANGE = "binance"
MINUTE_MS = 60_000


def model_row(v: Mapping[str, Any]) -> dict:
    """Inputs of the M1 family at the view's landmark: the terms (T15, family, structural side, σ) and
    the event's own B0 in beyond/back/neither orientation (the heads' offsets)."""
    from .level_race import TAU
    b0 = v["event_b0"]
    beyond, back = (b0["up"], b0["dn"]) if v["beyond_is_up"] else (b0["dn"], b0["up"])
    return {"event_id": v["event_id"], "landmark": v["landmark"], "family": v["family"],
            "struct_side": int(v["struct_side"]), "side": int(v["side"]), "position": float(v["position"]),
            "p_up": float(v["p_up"]), "p_dn": float(v["p_dn"]), "beyond_is_up": bool(v["beyond_is_up"]),
            "sigma": float(v["sigma"]), "tau": TAU[v["landmark"]], "b0_beyond": float(beyond),
            "b0_back": float(back), "b0_neither": float(b0["neither"])}


def c1_instants(touch_open_ms: int) -> tuple[int, int]:
    """The two close instants of `OTHER_VENUE_MEDIAN_MOVE` (#363): the close of the last bar before the
    touch bar (= touch open) and the close of bar j+2 (= the T15 landmark)."""
    return int(touch_open_ms), int(touch_open_ms) + (1 + LANDMARK_BARS["T15"]) * BAR_MS


def closes_at(rows_1m: Sequence[Mapping[str, Any]]) -> dict:
    """{close instant ms: close} from klines_1m rows (`ts` = minute open): the 1m close at a 5m boundary
    is the 5m close there. Non-finite or non-positive closes are left out (missing, never filled)."""
    out = {}
    for r in rows_1m or ():
        c = r.get("close")
        if c is None:
            continue
        c = float(c)
        if math.isfinite(c) and c > 0:
            out[to_ms(r["ts"]) + MINUTE_MS] = c
    return out


def _oriented(base: Optional[float], dec: Optional[float], side: int) -> Optional[float]:
    if base is None or dec is None or side not in (1, -1):
        return None
    base, dec = float(base), float(dec)
    if not (math.isfinite(base) and math.isfinite(dec) and base > 0 and dec > 0):
        return None
    r = math.log(dec / base)
    return float(side) * r if math.isfinite(r) else None


def c1_block(b: Bars, v: Mapping[str, Any], venue_closes: Mapping[str, Mapping[int, float]], *,
             read_ms: Optional[int] = None) -> dict:
    """`OTHER_VENUE_MEDIAN_MOVE` for the C1 challenger, exactly as #363, with everything it was computed
    from: the median (= mean of two) of the Bybit and OKX 15m log moves from close(j-1) to close(j+2),
    oriented by the approach side; all three venues required (the Binance closes from the 5m tape), no
    fill. 0 at T0 (not defined before the decision bar; design §8). `closes` are the six prices as read
    and `missing` every venue without both closes (binance, bybit, okx order); the journal stores this
    block as read and never recomputes it (a later gap-fill may rewrite klines_1m)."""
    base_ms, dec_ms = c1_instants(v["touch_open_ms"])
    out = {"value": None, "missing": [], "instants_ms": [base_ms, dec_ms], "closes": {}, "read_ms": read_ms}
    if v["landmark"] == "T0":
        return {**out, "value": 0.0, "instants_ms": None}
    side = int(v["side"])
    j = _bar(b, v["touch_open_ms"])
    ok = j is not None and j >= 1 and j + LANDMARK_BARS["T15"] < b.n
    bc = [float(b.close[j - 1]), float(b.close[j + LANDMARK_BARS["T15"]])] if ok else [None, None]
    out["closes"]["binance"] = [x if x is not None and math.isfinite(x) else None for x in bc]
    moves = {"binance": _oriented(bc[0], bc[1], side)}
    for ven in C1_VENUES:
        closes = venue_closes.get(ven) or {}
        out["closes"][ven] = [closes.get(base_ms), closes.get(dec_ms)]
        moves[ven] = _oriented(closes.get(base_ms), closes.get(dec_ms), side)
    out["missing"] = [ven for ven in (C1_EXCHANGE,) + C1_VENUES if moves[ven] is None]
    if not out["missing"]:
        out["value"] = 0.5 * (moves[C1_VENUES[0]] + moves[C1_VENUES[1]])
    return out


def c1_input(b: Bars, v: Mapping[str, Any], venue_closes: Mapping[str, Mapping[int, float]]) -> dict:
    """The C1 term and the first missing venue (None when complete); see `c1_block`."""
    blk = c1_block(b, v, venue_closes)
    return {C1_TERM: blk["value"], "c1_missing": blk["missing"][0] if blk["missing"] else None}


# C1 ingestion wait (frozen before any data; docs/research/LEVEL_RACE_LIVE_JOURNAL_V1.md §3). The two
# closes sit at fixed instants at or before the T15 landmark, so waiting reads nothing later than the
# landmark: it only lets the Bybit / OKX minute ending at the landmark reach klines_1m (Stage-1 writes
# a minute when the next minute's first trade arrives). The C1 shadow record is written at the first
# run with every C1 close present, or at the first run at or after C1_WAIT_MS with C1 missing. The
# champion's record never waits.
C1_WAIT_MS = 3 * MINUTE_MS


def c1_due(blk: Mapping[str, Any], *, landmark_ms: int, now_ms: int) -> bool:
    """Whether the C1 shadow record may be written now under the wait rule."""
    return not blk.get("missing") or int(now_ms) >= int(landmark_ms) + C1_WAIT_MS


def c1_minutes(views: Sequence[Mapping[str, Any]]) -> list:
    """The klines_1m minute opens (ms) the T15 views need from each other venue (two per event)."""
    out = set()
    for v in views:
        if v["landmark"] == "T15":
            for at in c1_instants(v["touch_open_ms"]):
                out.add(at - MINUTE_MS)
    return sorted(out)


async def load_venue_closes(conn, symbol: str, views: Sequence[Mapping[str, Any]]) -> dict:
    """{venue: {close instant ms: close}} for the C1 instants of `views`, read-only from the Stage-1
    klines_1m of Bybit and OKX (the same canonical symbol as Binance). One query per venue and
    minute; nothing in the E1 protected window is read."""
    from .history_data import protected_overlap
    out: dict = {ven: {} for ven in C1_VENUES}
    for m in c1_minutes(views):
        if protected_overlap(m, m + MINUTE_MS) is not None:
            continue
        for ven in C1_VENUES:
            rows = await conn.fetch_live_klines_1m(exchange=ven, symbol=symbol, start=from_ms(m),
                                                   end=from_ms(m + MINUTE_MS))
            out[ven].update(closes_at(rows))
    return out


def calibrator_version_at(t_ms: int, versions: Sequence[Any], prior: Any = None) -> Optional[str]:
    """The version id of the calibrator that applies to a forecast issued at `t_ms`: F3's
    `level_race_calibration.calibrator_at` (public function), None before any calibrator exists."""
    from .level_race_calibration import calibrator_at
    cal = calibrator_at(int(t_ms), versions, prior)
    return None if cal is None else cal.version


def model_inputs(b: Bars, v: Mapping[str, Any], venue_closes: Mapping[str, Mapping[int, float]]) -> dict:
    """The model row plus C1's extra input: what the predictor and the L3 journal read at a landmark."""
    return {**model_row(v), **c1_input(b, v, venue_closes)}


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


# ---- coverage: expected against written (pure) -------------------------------------------------
def coverage(b: Optional[Bars], rows: Sequence[Mapping[str, Any]], *, since_ms: int, until_ms: int,
             table: Mapping[str, Any], max_listed: int = 20) -> dict:
    """Per landmark: the statements the journal should hold for (since, until] — every eligible event of
    the tape whose landmark closed in it (T15 only with a T15 statement) — against the HIST records
    written. A notifier outage (records are written only within WRITE_WINDOW_MS) shows as `missing`
    instead of silently thinning the live metrics. Records the tape cannot reproduce are `unexpected`."""
    settled = int(until_ms) - WRITE_WINDOW_MS            # later landmarks may still be written: not counted
    written = {(r["subject"]["landmark"], r["subject_key"]) for r in rows
               if r.get("claim_class") in HIST_CLASS.values() and since_ms < to_ms(r["issue_slot"]) <= settled}
    expected = set()
    if b is not None:
        for ev in events(b):
            for lm in ("T0", "T15"):
                at = landmark_ms(ev, lm)
                if since_ms < at <= settled and at <= b.end_ms and landmark_view(b, ev, lm, table) is not None:
                    expected.add((lm, f"{ev['event_id']}:{lm}"))
    out = {"since_ms": int(since_ms), "settled_until_ms": settled, "tape_from_ms": None if b is None else int(b.t0)}
    for lm in ("T0", "T15"):
        exp = {k for l_, k in expected if l_ == lm}
        got = {k for l_, k in written if l_ == lm}
        miss, extra = sorted(exp - got), sorted(got - exp)
        out[lm] = {"expected": len(exp), "written": len(got & exp), "missing": len(miss),
                   "missing_keys": miss[:max_listed], "unexpected": len(extra), "unexpected_keys": extra[:max_listed]}
    return out


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
        key = (r["subject"].get("mode", "HIST"), r["subject"].get("cell") or r.get("claim_class"))
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
        for key in ("raw", "published"):                     # L3 records (LEVEL_RACE_LIVE_JOURNAL_V1)
            got = [r for r in scored if r["numbers"].get(key)]
            if got:
                rec[f"log_loss_{key}"] = round(float(np.mean([_ll(r["numbers"][key], r["realized"]["outcome"]) for r in got])), 5)
                rec[f"n_{key}"] = len(got)
        c1 = [r["numbers"]["c1"] for r in rs if r["numbers"].get("c1") and r["subject"].get("landmark") == "T15"]
        if c1:                                            # every T15 record, scored or not: the missing count
            rec["c1"] = {"records": len(c1), "complete": sum(1 for c in c1 if not c.get("missing")),
                         "missing_by_venue": {ven: sum(1 for c in c1 if ven in (c.get("missing") or ()))
                                              for ven in (C1_EXCHANGE,) + C1_VENUES}}
        if scored:
            rec["log_loss_b0"] = round(float(np.mean([_ll(r["numbers"]["event_b0"], r["realized"]["outcome"]) for r in scored])), 5)
            rec["brier_b0"] = round(float(np.mean([_brier(r["numbers"]["event_b0"], r["realized"]["outcome"]) for r in scored])), 5)
        res["cells"][f"{md}:{cell}"] = rec
    return res


def utc(ms: int) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
