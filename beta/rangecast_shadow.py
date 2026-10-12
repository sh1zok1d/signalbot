"""Paired shadow forecasts: the production range model V1 and the frozen W_L1 candidate on one snapshot.

NOT WIRED. No product module imports this; nothing here writes a database, a claim or a text, and V1
(`beta/rangecast.py`) and the sharp-move detector are untouched. Contract with the claim journal and the
calibration monitor: docs/RANGECAST_V2_SHADOW_CONTRACT_V1.md.

One call takes the market snapshot the decision block is built from (closed 5m bars, the last closed 1m
price, now, the calendar) and returns, per horizon, a V1 record and a V2 record on the same anchor, the
same price and the same levels:

- single-level chances on the claim journal's distance grid, both sides, and on any target prices given;
- «ни один» on the journal's level pairs;
- every identifier the journal needs (procedure, model, spec and parameter digests, as-of, horizon end,
  the claim-style subject keys), so the two records pair one to one.

A forecast is never invented. Stale data, too little history, an incomplete window, a CPI / FOMC event
zone, a missing or altered model, or an invalid target each return a status and no number.

V1 numbers are computed exactly as `beta.claims.touch_claims` computes them (`rangecast.touch_probability`
and `neither_probability` on the corridor scale of the last complete 5m bar). V2 numbers are the research
path the RANGECAST_V2 evaluation scored (`rangecast_v2.state_at` → `touch_prob` / `neither_prob`).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from . import rangecast as rc
from . import rangecast_v2 as v2
from .hist_series import BAR_MS, Bars, to_ms

logger = logging.getLogger("beta.rangecast_shadow")

SHADOW_SCHEMA = "RANGECAST_SHADOW_RECORD_V1"
ADAPTER_VERSION = "RANGECAST_SHADOW_ADAPTER_V1"
PROCEDURE_V1 = "TOUCH_CHANCE_PROCEDURE_V1"          # the id calibration monitor V2 gives the production chances
PROCEDURE_V2 = "TOUCH_CHANCE_PROCEDURE_RCV2_W_L1"
HORIZONS = ("1h", "4h", "24h")
TOUCH_GRID_PCT = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)     # = beta.claims.TOUCH_GRID_PCT (test-pinned)
NEITHER_GRID_PCT = (0.5, 1.0, 2.0, 3.0)              # = beta.claims.NEITHER_GRID_PCT (test-pinned)
MIN_DISTANCE_PCT, MAX_DISTANCE_PCT = 0.05, 30.0      # = beta.check (test-pinned)
STALE_AFTER = timedelta(minutes=10)                  # = beta.decision.STALE_AFTER (test-pinned)
EVENT_ZONE_POST_MS = 60 * 60_000                     # = beta.decision.EVENT_ZONE_POST_MS (test-pinned)
PROB_DECIMALS = 6

# proposed journal classes of the V2 side, never shown (docs/RANGECAST_V2_SHADOW_CONTRACT_V1.md §3): the V1
# class name plus _RCV2, evaluated by the V1 class's rule
SHADOW_CLASSES = {**{("touch", h): f"L3_DISTANCE_TOUCH_{h.upper()}_RCV2" for h in HORIZONS},
                  **{("neither", h): f"L3_NEITHER_{h.upper()}_RCV2" for h in HORIZONS}}

MODEL_PATH = Path(__file__).resolve().parents[1] / "docs/research/RANGECAST_V2_W_L1_MODEL_V1.json"
MODEL_ARTIFACT_ID = "RANGECAST_V2_W_L1_MODEL_V1"
MODEL_FILE_SHA256 = "2c7e3eca0d90f12d11e7a10558ffaed8d719ff63d630f2c7b252fd6030f70533"
MODEL_PARAMS_DIGEST = "095f409f024c3a968d0ec4dc14ca99a3cea67d27c58c3329c241fce02569e261"

OK = "OK"
NO_MODEL = "NO_MODEL"
MODEL_INVALID = "MODEL_INVALID"
STALE_DATA = "STALE_DATA"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INCOMPLETE_WINDOW = "INCOMPLETE_WINDOW"
EVENT_ZONE = "EVENT_ZONE"
NOT_COMPUTABLE = "NOT_COMPUTABLE"
INVALID_TARGET = "INVALID_TARGET"


class ShadowModelError(RuntimeError):
    pass


# ---- the frozen candidate ------------------------------------------------------------------------
def load_frozen_model(path: Path = MODEL_PATH) -> dict:
    """The committed W_L1 artifact, verified: file bytes, parameter digest, and the spec digest the
    current code computes (a code change to any procedure constant refuses the old artifact)."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_FILE_SHA256:
        raise ShadowModelError("artifact file digest mismatch")
    model = json.loads(raw.decode("utf-8"))
    validate_v2_model(model)
    if model.get("params_digest") != MODEL_PARAMS_DIGEST:
        raise ShadowModelError("artifact parameter digest is not the pinned one")
    return model


def validate_v2_model(model: Mapping[str, Any]) -> None:
    if model.get("level") != v2.SELECTED_LEVEL or model.get("half_life_days") != v2.SELECTED_HALF_LIFE_DAYS:
        raise ShadowModelError("not the W_L1 configuration")
    if model.get("spec_digest") != v2.spec_digest():
        raise ShadowModelError("spec digest differs from the code's procedure constants")
    if model.get("params_digest") is not None and model["params_digest"] != v2.params_digest(model):
        raise ShadowModelError("parameter digest does not match the stored parameters")
    if set(model.get("horizons") or {}) != set(HORIZONS):
        raise ShadowModelError("horizons missing")


def v2_identity(model: Mapping[str, Any]) -> dict:
    return {"procedure_id": PROCEDURE_V2, "model_version": model.get("version"), "spec_id": model.get("spec_id"),
            "spec_digest": model.get("spec_digest"), "params_digest": model.get("params_digest") or v2.params_digest(model),
            "artifact_id": model.get("artifact_id")}


def shadow_rule_version(model: Mapping[str, Any]) -> str:
    """The `rule_version` of a V2 journal row: spec, fitted numbers and adapter (contract §3.3)."""
    ident = v2_identity(model)
    return f"{ident['spec_id']}+{ident['params_digest'][:16]}+{ADAPTER_VERSION}"


def v1_identity(model: Mapping[str, Any], *, stats_pk: Optional[int] = None,
                stats_digest: Optional[str] = None) -> dict:
    return {"procedure_id": PROCEDURE_V1, "model_version": model.get("version"), "stats_pk": stats_pk,
            "stats_digest": stats_digest}


# ---- snapshot ----------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Snapshot:
    """What `decision.load_live_bars` and the block already hold: closed 5m bars, the last closed 1m close
    and its open time, the wall clock and the calendar file."""
    bars: Bars
    price: Optional[float]
    price_ts: Optional[datetime]
    now: datetime
    calendar: Mapping[str, Any]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def event_zone_horizons(now_ms: int, calendar: Mapping[str, Any]) -> dict:
    """{horizon: [releases]} where a CPI / FOMC release r has r − H <= now < r + 60 min: the rule of
    `beta.decision.event_zones`, so a horizon is withheld exactly where the product withholds it."""
    rel = sorted((e for e in calendar.get("events") or () if e["kind"] in rc.EVENT_KINDS), key=lambda e: e["at"])
    out: dict = {}
    for h in HORIZONS:
        hms = rc.HORIZON_MS[h]
        hits = [{"kind": e["kind"], "at": _iso(e["at"])} for e in rel
                if to_ms(e["at"]) - hms <= int(now_ms) < to_ms(e["at"]) + EVENT_ZONE_POST_MS]
        if hits:
            out[h] = hits
    return out


def snapshot_status(snap: Snapshot) -> tuple:
    """(status, reason, anchor bar index or None) for the snapshot as a whole."""
    if snap.price is None or snap.price_ts is None or not math.isfinite(float(snap.price)) or snap.price <= 0:
        return STALE_DATA, "NO_PRICE", None
    if snap.now - snap.price_ts > STALE_AFTER:
        return STALE_DATA, "PRICE_OLDER_THAN_10_MIN", None
    i = snap.bars.last_complete_index()
    if i is None:
        return INSUFFICIENT_HISTORY, "NO_BARS", None
    anchor_close = snap.bars.t0 + (i + 1) * BAR_MS
    if to_ms(snap.now) - anchor_close > STALE_AFTER.total_seconds() * 1000:
        return STALE_DATA, "LAST_5M_BAR_OLDER_THAN_10_MIN", None
    if anchor_close > to_ms(snap.now):
        return NOT_COMPUTABLE, "BAR_CLOSES_AFTER_NOW", None
    if i < v2.LOOKBACK_BARS + 1:
        return INSUFFICIENT_HISTORY, "LESS_THAN_30_DAYS_OF_BARS", None
    fails = v2.data_quality_failures(snap.bars, i)
    if fails:
        return INCOMPLETE_WINDOW, ";".join(fails), None
    return OK, None, i


# ---- targets -------------------------------------------------------------------------------------
def _round(p: float) -> float:
    return round(float(p), PROB_DECIMALS)


def touch_targets(price: float, *, grid_pct: Sequence[float] = TOUCH_GRID_PCT,
                  target_prices: Sequence[float] = ()) -> list:
    """The journal grid on both sides (subject keys as `beta.claims.touch_claims`), then any target prices."""
    out = []
    for d in grid_pct:
        for side in (+1, -1):
            out.append({"source": "GRID", "side": side, "distance_pct": float(d),
                        "level": round(price * (1 + side * d / 100.0), 2), "subject_key": f"{side:+d}:{d}"})
    for tp in target_prices:
        try:
            tp = float(tp)
        except (TypeError, ValueError):
            out.append({"source": "TARGET", "target_price": tp, "status": INVALID_TARGET, "reason": "NOT_A_NUMBER"})
            continue
        if not math.isfinite(tp) or tp <= 0:
            out.append({"source": "TARGET", "target_price": tp, "status": INVALID_TARGET, "reason": "NOT_POSITIVE"})
            continue
        d = abs(tp / price - 1) * 100.0
        side = +1 if tp > price else -1
        if not MIN_DISTANCE_PCT <= d <= MAX_DISTANCE_PCT:
            out.append({"source": "TARGET", "target_price": tp, "status": INVALID_TARGET,
                        "reason": "TOO_CLOSE" if d < MIN_DISTANCE_PCT else "TOO_FAR"})
            continue
        out.append({"source": "TARGET", "side": side, "distance_pct": round(d, 6), "level": round(tp, 2),
                    "target_price": tp, "subject_key": f"T{side:+d}:{round(tp, 2):.2f}"})
    return out


def neither_pairs(price: float, grid_pct: Sequence[float] = NEITHER_GRID_PCT) -> list:
    return [{"up_pct": float(du), "down_pct": float(dd), "level_up": round(price * (1 + du / 100.0), 2),
             "level_down": round(price * (1 - dd / 100.0), 2), "subject_key": f"{du}:{dd}"}
            for du in grid_pct for dd in grid_pct]


# ---- per-model scorers -------------------------------------------------------------------------------
class _V1Scorer:
    def __init__(self, model: Mapping[str, Any], b: Bars, i: int, h: str, events):
        self.model, self.h = model, h
        self.S = rc.scale_at(model, b, i, h, events=events)

    @property
    def ok(self) -> bool:
        return self.S is not None and math.isfinite(self.S) and self.S > 0

    def state(self) -> dict:
        return {"scale_pct": self.S}

    def touch(self, side: int, d: float) -> float:
        return rc.touch_probability(self.model, self.h, self.S, d)

    def neither(self, du: float, dd: float) -> tuple:
        pu, pd_ = self.touch(+1, du), self.touch(-1, dd)
        if "q_joint" not in ((self.model.get("horizons") or {}).get(self.h) or {}):
            return None, pu, pd_
        return rc.neither_probability(self.model, self.h, self.S, du, dd, p_up=pu, p_down=pd_), pu, pd_


class _V2Scorer:
    def __init__(self, model: Mapping[str, Any], b: Bars, i: int, h: str, events):
        self.model, self.h = model, h
        self.st = v2.state_at(model, b, i, h, events=events)

    @property
    def ok(self) -> bool:
        return self.st is not None and all(math.isfinite(v) for v in self.st.values())

    def state(self) -> dict:
        return {"scale_pct": self.st["S"]} if "S" in self.st else dict(self.st)

    def touch(self, side: int, d: float) -> float:
        return v2.touch_probability_v2(self.model, self.h, self.st, side, d)

    def neither(self, du: float, dd: float) -> tuple:
        mh = self.model["horizons"][self.h]
        s = {k: np.array([v]) for k, v in self.st.items()}
        p = float(v2.neither_prob(mh, s, np.array([du]), np.array([dd]))[0])
        return p, self.touch(+1, du), self.touch(-1, dd)


def _model_record(scorer, identity: Mapping[str, Any], *, h: str, as_of: datetime, targets: Sequence[Mapping],
                  pairs: Sequence[Mapping]) -> dict:
    from .claims import printed_prob
    rec = {**identity, "horizon": h, "as_of": _iso(as_of), "horizon_end": _iso(as_of + timedelta(milliseconds=rc.HORIZON_MS[h])),
           "status": OK, "reason": None, "state": None, "touch": [], "neither": []}
    if not scorer.ok:
        rec.update(status=NOT_COMPUTABLE, reason="MODEL_STATE_NOT_FINITE")
        return rec
    rec["state"] = {k: float(v) for k, v in scorer.state().items()}
    for t in targets:
        if t.get("status") == INVALID_TARGET:
            rec["touch"].append(dict(t))
            continue
        p = scorer.touch(int(t["side"]), float(t["distance_pct"]))
        rec["touch"].append({**t, "status": OK, "probability": _round(p), "printed": printed_prob(p)})
    for q in pairs:
        p, pu, pd_ = scorer.neither(float(q["up_pct"]), float(q["down_pct"]))
        if p is None:
            rec["neither"].append({**q, "status": NOT_COMPUTABLE, "reason": "NO_JOINT_TABLE"})
            continue
        rec["neither"].append({**q, "status": OK, "probability": _round(p), "printed": printed_prob(p),
                               "p_up": _round(pu), "p_down": _round(pd_)})
    return rec


def _blank(identity: Mapping[str, Any], h: str, as_of: Optional[datetime], status: str, reason: Optional[str]) -> dict:
    return {**identity, "horizon": h, "as_of": None if as_of is None else _iso(as_of),
            "horizon_end": None if as_of is None else _iso(as_of + timedelta(milliseconds=rc.HORIZON_MS[h])),
            "status": status, "reason": reason, "state": None, "touch": [], "neither": []}


# ---- the paired call ---------------------------------------------------------------------------------
def paired_forecast(snap: Snapshot, *, v1_model: Optional[Mapping[str, Any]], v2_model: Optional[Mapping[str, Any]],
                    v1_ids: Optional[Mapping[str, Any]] = None, horizons: Sequence[str] = HORIZONS,
                    touch_grid_pct: Sequence[float] = TOUCH_GRID_PCT, neither_grid_pct: Sequence[float] = NEITHER_GRID_PCT,
                    target_prices: Sequence[float] = ()) -> dict:
    """V1 and V2 records per horizon on one anchor. Never raises: a failure is a status."""
    v1_ids = dict(v1_ids or {})
    id1 = v1_identity(v1_model or {}, stats_pk=v1_ids.get("stats_pk"), stats_digest=v1_ids.get("stats_digest"))
    try:
        id2 = v2_identity(v2_model) if v2_model is not None else {"procedure_id": PROCEDURE_V2}
        v2_problem = None
        if v2_model is not None:
            try:
                validate_v2_model(v2_model)
            except ShadowModelError as exc:
                v2_problem = str(exc)
        status, reason, i = snapshot_status(snap)
        as_of = (snap.price_ts + timedelta(minutes=1)) if snap.price_ts is not None else None
        out = {"schema": SHADOW_SCHEMA, "adapter_version": ADAPTER_VERSION, "status": status, "reason": reason,
               "now": _iso(snap.now), "as_of": None if as_of is None else _iso(as_of),
               "price": None if snap.price is None else float(snap.price),
               "anchor_close_ms": None if i is None else int(snap.bars.t0 + (i + 1) * BAR_MS), "horizons": {}}
        zones = event_zone_horizons(to_ms(snap.now), snap.calendar) if status == OK else {}
        events = None
        if status == OK:
            from .calendar_events import event_times_ms
            events = event_times_ms(snap.calendar)
            targets = touch_targets(float(snap.price), grid_pct=touch_grid_pct, target_prices=target_prices)
            pairs = neither_pairs(float(snap.price), neither_grid_pct)
        for h in horizons:
            if status != OK:
                hs = {"status": status, "reason": reason, "v1": _blank(id1, h, as_of, status, reason),
                      "v2": _blank(id2, h, as_of, status, reason)}
            elif h in zones:
                why = "RELEASE " + ",".join(f"{z['kind']}@{z['at']}" for z in zones[h])
                hs = {"status": EVENT_ZONE, "reason": why, "v1": _blank(id1, h, as_of, EVENT_ZONE, why),
                      "v2": _blank(id2, h, as_of, EVENT_ZONE, why)}
            else:
                r1 = (_blank(id1, h, as_of, NO_MODEL, "NO_V1_MODEL") if v1_model is None else
                      _model_record(_V1Scorer(v1_model, snap.bars, i, h, events), id1, h=h, as_of=as_of,
                                    targets=targets, pairs=pairs))
                if v2_model is None:
                    r2 = _blank(id2, h, as_of, NO_MODEL, "NO_V2_MODEL")
                elif v2_problem is not None:
                    r2 = _blank(id2, h, as_of, MODEL_INVALID, v2_problem)
                else:
                    r2 = _model_record(_V2Scorer(v2_model, snap.bars, i, h, events), id2, h=h, as_of=as_of,
                                       targets=targets, pairs=pairs)
                both = r1["status"] == OK and r2["status"] == OK
                hs = {"status": OK if both else NOT_COMPUTABLE, "reason": None if both else "ONE_SIDE_UNAVAILABLE",
                      "v1": r1, "v2": r2}
            hs["paired"] = hs["status"] == OK
            hs["pair_key"] = pair_key(out["as_of"], out["anchor_close_ms"], out["price"], h)
            out["horizons"][h] = hs
        return out
    except Exception as exc:  # noqa: BLE001 - the shadow never breaks its caller
        logger.warning("rangecast shadow failed: %s", type(exc).__name__)
        return {"schema": SHADOW_SCHEMA, "adapter_version": ADAPTER_VERSION, "status": NOT_COMPUTABLE,
                "reason": type(exc).__name__, "now": _iso(snap.now), "as_of": None, "price": None,
                "anchor_close_ms": None, "horizons": {}}


def pair_key(as_of: Optional[str], anchor_close_ms: Optional[int], price: Optional[float], h: str) -> str:
    """One key per (as-of, anchor, price, horizon): the V1 and V2 claims of one pair share it."""
    body = json.dumps([SHADOW_SCHEMA, as_of, anchor_close_ms, price, h], separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()
