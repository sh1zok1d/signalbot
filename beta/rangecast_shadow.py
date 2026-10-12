"""Rangecast V2 paired shadow: the number source of the paired shadow store.

NOT WIRED. No product module imports this; nothing here writes a database, a claim or a user text, and V1
(`beta/rangecast.py`) and the sharp-move detector are untouched. Storage, the hour path, outcomes and
measurement belong to the paired shadow store (`beta/paired_shadow.py`: `plan_shadow_record`, `execute_hour`;
docs/BETA_PAIRED_SHADOW_CONTRACT_V1.md); this module only provides numbers and identities. The forecast side
of that contract: docs/RANGECAST_V2_SHADOW_CONTRACT_V2.md.

- `paired_forecast`: one hourly record. It checks the snapshot (fresh price and 5m bars, 30 days of history,
  the live data-quality gate, CPI / FOMC event zones), binds V1 (`paired_shadow.bind_rangecast_v1`, behind the
  V1 identity check) and W_L1 (`rangecast_v2.bind_shadow_model`) on the same bar, and returns both models' numbers
  on the journal grid (and any target prices) with their identities. A horizon one model cannot answer is
  not `OK` for the pair, so the store keeps only paired anchors. `plan_paired_issues` returns the rows the
  store's hour path would store for that record, without writing.
- Nightly snapshots: `fit_nightly_snapshot` fits W_L1 on the grid of the V1 nightly build; `SnapshotStore`
  keeps every snapshot of coefficients, write-once and verified on read, and `select` returns the snapshot
  in force at an issue.
- `load_frozen_model`: the committed W_L1 artifact, kept for reproducibility (parity and golden tests).

A probability is never invented: every failure is a status.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from . import rangecast as rc
from . import rangecast_v2 as v2
from .hist_series import BAR_MS, Bars, to_ms
from .state_tape import sha256_json

logger = logging.getLogger("beta.rangecast_shadow")

SHADOW_SCHEMA = "RANGECAST_SHADOW_RECORD_V2"
ADAPTER_VERSION = "RANGECAST_SHADOW_ADAPTER_V2"
SNAPSHOT_SCHEMA = "RANGECAST_V2_SNAPSHOT_V1"
HORIZONS = ("1h", "4h", "24h")
TOUCH_GRID_PCT = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)     # = beta.claims.TOUCH_GRID_PCT (test-pinned)
NEITHER_GRID_PCT = (0.5, 1.0, 2.0, 3.0)              # = beta.claims.NEITHER_GRID_PCT (test-pinned)
MIN_DISTANCE_PCT, MAX_DISTANCE_PCT = 0.05, 30.0      # = beta.check (test-pinned)
STALE_AFTER = timedelta(minutes=v2.STALE_AFTER_MIN)  # = beta.decision.STALE_AFTER (test-pinned)
EVENT_ZONE_POST_MS = v2.EVENT_ZONE_POST_MIN * 60_000  # = beta.decision.EVENT_ZONE_POST_MS (test-pinned)
SNAPSHOT_MAX_AGE = timedelta(hours=v2.SNAPSHOT_MAX_AGE_H)
PROB_DECIMALS = 6

V1_PROCEDURE_ID, V1_SPEC_ID = "RANGECAST_V1", "RANGECAST_V1"   # = beta.paired_shadow (test-pinned)

MODEL_PATH = Path(__file__).resolve().parents[1] / "docs/research/RANGECAST_V2_W_L1_MODEL_V1.json"
MODEL_ARTIFACT_ID = "RANGECAST_V2_W_L1_MODEL_V1"
MODEL_FILE_SHA256 = "2c7e3eca0d90f12d11e7a10558ffaed8d719ff63d630f2c7b252fd6030f70533"
MODEL_PARAMS_DIGEST = "095f409f024c3a968d0ec4dc14ca99a3cea67d27c58c3329c241fce02569e261"

OK = "OK"
NO_MODEL = "NO_MODEL"
MODEL_INVALID = "MODEL_INVALID"
NO_SNAPSHOT = "NO_SNAPSHOT"
STALE_SNAPSHOT = "STALE_SNAPSHOT"
STALE_DATA = "STALE_DATA"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INCOMPLETE_WINDOW = "INCOMPLETE_WINDOW"
EVENT_ZONE = "EVENT_ZONE"
NOT_COMPUTABLE = "NOT_COMPUTABLE"
INVALID_TARGET = "INVALID_TARGET"


class ShadowModelError(RuntimeError):
    pass


# ---- the frozen artifact (reproducibility) ------------------------------------------------------------
def load_frozen_model(path: Path = MODEL_PATH) -> dict:
    """The committed W_L1 artifact, verified: file bytes, parameter digest, and the math spec digest the
    current code computes (a code change to any model constant refuses the old artifact)."""
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


# ---- V1 identity (read from beta.rangecast; V1 is not changed) ---------------------------------------------
def v1_shadow_procedure() -> dict:
    """Every constant of the production V1 procedure that moves a touch or «ни один» chance. Its digest is
    the `procedure_digest` of `paired_shadow.V1_SPEC_IDENTITY`."""
    return {
        "math": {"version": rc.RANGE_MODEL_VERSION, "horizons": dict(rc.HORIZONS), "features": list(rc.FEATURES),
                 "past_windows": list(rc.PAST_WINDOWS), "event_kinds": list(rc.EVENT_KINDS), "floor_pct": rc.FLOOR_PCT,
                 "p_grid": list(rc.P_GRID), "joint_levels": list(rc.JOINT_LEVELS), "anchor_stride": rc.ANCHOR_STRIDE,
                 "min_train_anchors": rc.MIN_TRAIN_ANCHORS},
        "fit": {"schedule": "NIGHTLY", "function": "rangecast.fit_range_model", "grid": "history_stats.run_history_build"},
        "serve": {"state": "rangecast.scale_at on the last complete 5m bar", "stale_after_min": v2.STALE_AFTER_MIN,
                  "event_zone": {"kinds": list(rc.EVENT_KINDS), "post_min": v2.EVENT_ZONE_POST_MIN}},
    }


def v1_spec_identity() -> dict:
    return {"procedure_id": V1_PROCEDURE_ID, "spec_id": V1_SPEC_ID,
            "surface": "beta.rangecast.touch_probability+neither_probability", "symbol": v2.SHADOW_SYMBOL,
            "procedure_digest": sha256_json(v1_shadow_procedure())}


def v1_spec_digest() -> str:
    """`paired_shadow.V1_SPEC_DIGEST`, after checking that the V1 code still computes it."""
    from .paired_shadow import V1_SPEC_DIGEST, V1_SPEC_IDENTITY
    mine = v1_spec_identity()
    if mine != dict(V1_SPEC_IDENTITY) or sha256_json(mine) != V1_SPEC_DIGEST:
        raise ShadowModelError("V1 SPEC_IDENTITY_MISMATCH: the V1 procedure changed; register a new spec_id")
    return V1_SPEC_DIGEST


def v1_snapshot_id(model: Mapping[str, Any]) -> str:
    """sha256 of V1's fitted horizons. The nightly V1 build changes it on later issues only."""
    return sha256_json(model["horizons"])


def bind_v1(model: Mapping[str, Any], scales: Mapping[str, float], *, snapshot_id: str):
    """`paired_shadow.bind_rangecast_v1` behind the identity checks."""
    from .paired_shadow import bind_rangecast_v1
    if model.get("version") != rc.RANGE_MODEL_VERSION:
        raise ShadowModelError("not the production V1 model")
    v1_spec_digest()
    if snapshot_id != v1_snapshot_id(model):
        raise ShadowModelError("V1 snapshot id mismatch")
    for h, s in scales.items():
        if s is None or not math.isfinite(float(s)) or float(s) <= 0:
            raise ShadowModelError(f"V1 scale not finite: {h}")
    return bind_rangecast_v1(model, {h: float(s) for h, s in scales.items()}, snapshot_id=snapshot_id)


# ---- nightly snapshots of the W_L1 coefficients ----------------------------------------------------------
def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _utc(v) -> datetime:
    dt = datetime.fromisoformat(v) if isinstance(v, str) else v
    if dt.tzinfo is None:
        raise ShadowModelError("timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc)


def fit_nightly_snapshot(b: Bars, *, calendar: Mapping[str, Any], built_at: datetime) -> dict:
    """W_L1 fitted on the nightly grid `b` (`history_stats.load_history_grid`, the grid the V1 build reads,
    ending at the UTC midnight of the build). JSON-ready. Pure."""
    from .calendar_events import event_times_ms
    from .history_stats import json_safe
    built_at = _utc(built_at)
    if b.end_ms > to_ms(built_at):
        raise ShadowModelError("the grid ends after the build time")
    present = b.present()
    if not present.any():
        raise ShadowModelError("empty grid")
    model = json_safe(v2.fit_range_model_v2(b, events=event_times_ms(calendar)))
    first = int(present.argmax())
    return {"schema": SNAPSHOT_SCHEMA, "procedure_id": v2.SHADOW_PROCEDURE_ID, "spec_id": v2.SHADOW_SPEC_ID,
            "spec_digest": v2.shadow_spec_digest(), "snapshot_id": v2.shadow_snapshot_id(model),
            "built_at": _iso(built_at), "data_from": _iso(datetime.fromtimestamp((b.t0 + first * BAR_MS) / 1000, timezone.utc)),
            "data_through": _iso(datetime.fromtimestamp(b.end_ms / 1000, timezone.utc)),
            "calendar_version": calendar.get("version"), "model": model}


def verify_snapshot(record: Mapping[str, Any]) -> dict:
    """The model of a snapshot record, after checking schema, identity, coefficients and time order."""
    if record.get("schema") != SNAPSHOT_SCHEMA:
        raise ShadowModelError("not a W_L1 snapshot record")
    if (record.get("procedure_id"), record.get("spec_id")) != (v2.SHADOW_PROCEDURE_ID, v2.SHADOW_SPEC_ID):
        raise ShadowModelError("snapshot of another procedure")
    try:
        current = v2.shadow_spec_digest()
    except v2.RangeModelV2Error as exc:
        raise ShadowModelError(str(exc)) from None
    if record.get("spec_digest") != current:
        raise ShadowModelError("snapshot of another specification")
    model = record.get("model") or {}
    validate_v2_model(model)
    if record.get("snapshot_id") != v2.shadow_snapshot_id(model):
        raise ShadowModelError("snapshot id does not match the coefficients")
    if _utc(record["data_through"]) > _utc(record["built_at"]):
        raise ShadowModelError("snapshot data after its build time")
    return model


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class SnapshotStore:
    """W_L1 coefficient snapshots, one write-once JSON file `<built_at>_<snapshot_id>.json` each in one
    directory. The first snapshot of a set of coefficients is kept; a later identical fit adds nothing.
    Every read is verified. No database table."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _files(self) -> list:
        return sorted(self.root.glob("*_*.json")) if self.root.is_dir() else []

    def put(self, record: Mapping[str, Any]) -> dict:
        verify_snapshot(record)
        sid = record["snapshot_id"]
        same = [p for p in self._files() if p.stem.endswith("_" + sid)]
        if same:
            return {"stored": False, "path": str(same[0])}
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{_stamp(_utc(record['built_at']))}_{sid}.json"
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")      # a crashed write never blocks the next
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f, sort_keys=True)
        os.replace(tmp, path)
        return {"stored": True, "path": str(path)}

    def get(self, snapshot_id: str) -> dict:
        for p in self._files():
            if p.stem.endswith("_" + snapshot_id):
                rec = json.loads(p.read_text(encoding="utf-8"))
                verify_snapshot(rec)
                return rec
        raise KeyError(snapshot_id)

    def select(self, at: datetime) -> tuple:
        """(status, reason, record) of the snapshot in force at `at`: the newest built at or before it."""
        at = _utc(at)
        due = [p for p in self._files() if p.stem.split("_", 1)[0] <= _stamp(at)]
        if not due:
            return NO_SNAPSHOT, "NO_SNAPSHOT_BUILT_BEFORE_ISSUE", None
        try:
            rec = json.loads(due[-1].read_text(encoding="utf-8"))
            verify_snapshot(rec)
        except (ShadowModelError, ValueError, KeyError) as exc:
            return MODEL_INVALID, f"SNAPSHOT_INVALID:{exc}", None
        if _utc(rec["built_at"]) > at:
            return NO_SNAPSHOT, "NO_SNAPSHOT_BUILT_BEFORE_ISSUE", None
        if at - _utc(rec["data_through"]) > SNAPSHOT_MAX_AGE:
            return STALE_SNAPSHOT, f"DATA_THROUGH_{rec['data_through']}", rec
        return OK, None, rec


# ---- the market snapshot ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Snapshot:
    """What `decision.load_live_bars` and the block already hold: closed 5m bars, the last closed 1m close
    and its open time, the wall clock and the calendar file."""
    bars: Bars
    price: Optional[float]
    price_ts: Optional[datetime]
    now: datetime
    calendar: Mapping[str, Any]


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


# ---- one issue: checks and bindings -------------------------------------------------------------------------
def _v1_side(model, b, i, horizons, events) -> tuple:
    """({h: (status, reason)}, bound or None)."""
    if model is None:
        return {h: (NO_MODEL, "NO_V1_MODEL") for h in horizons}, None
    st, scales = {}, {}
    for h in horizons:
        s = rc.scale_at(model, b, i, h, events=events)
        if s is None or not math.isfinite(s) or s <= 0:
            st[h] = (NOT_COMPUTABLE, "V1_SCALE_NOT_FINITE")
        else:
            st[h], scales[h] = (OK, None), s
    try:
        bound = bind_v1(model, scales, snapshot_id=v1_snapshot_id(model))
    except (ShadowModelError, KeyError, TypeError) as exc:
        return {h: (MODEL_INVALID, str(exc)) for h in horizons}, None
    return st, bound


def _v2_side(model, b, i, horizons, events) -> tuple:
    if model is None:
        return {h: (NO_MODEL, "NO_V2_MODEL") for h in horizons}, None
    try:
        validate_v2_model(model)
    except ShadowModelError as exc:
        return {h: (MODEL_INVALID, str(exc)) for h in horizons}, None
    st, states = {}, {}
    for h in horizons:
        s = v2.state_at(model, b, i, h, events=events)
        if s is None or not all(math.isfinite(x) for x in s.values()):
            st[h] = (NOT_COMPUTABLE, "V2_STATE_NOT_FINITE")
        else:
            st[h], states[h] = (OK, None), s
    try:
        bound = v2.bind_shadow_model(model, states, snapshot_id=v2.shadow_snapshot_id(model))
    except v2.RangeModelV2Error as exc:
        return {h: (MODEL_INVALID, str(exc)) for h in horizons}, None
    return st, bound


def prepare_issue(snap: Snapshot, *, v1_model: Optional[Mapping[str, Any]], v2_model: Optional[Mapping[str, Any]],
                  horizons: Sequence[str] = HORIZONS) -> dict:
    """Checks and bindings of one issue (the first half of `paired_forecast`). `report` is JSON-ready; `v1` /
    `v2` are the bound models (or None); `paired` lists the horizons both answer. Never raises."""
    horizons = tuple(horizons)
    try:
        status, reason, i = snapshot_status(snap)
        as_of = snap.price_ts + timedelta(minutes=1) if snap.price_ts is not None else None
        rep = {"schema": SHADOW_SCHEMA, "adapter_version": ADAPTER_VERSION, "status": status, "reason": reason,
               "now": _iso(snap.now), "as_of": None if as_of is None else _iso(as_of),
               "issue_slot": _iso(snap.now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)),
               "price": None if snap.price is None else float(snap.price),
               "anchor_close_ms": None if i is None else int(snap.bars.t0 + (i + 1) * BAR_MS), "horizons": {}}
        if status != OK:
            rep["horizons"] = {h: {"status": status, "reason": reason, "v1": status, "v2": status} for h in horizons}
            return {"report": rep, "v1": None, "v2": None, "paired": []}
        from .calendar_events import event_times_ms
        events = event_times_ms(snap.calendar)
        zones = event_zone_horizons(to_ms(snap.now), snap.calendar)
        free = tuple(h for h in horizons if h not in zones)
        s1, b1 = _v1_side(v1_model, snap.bars, i, free, events)
        s2, b2 = _v2_side(v2_model, snap.bars, i, free, events)
        paired = []
        for h in horizons:
            if h in zones:
                why = "RELEASE " + ",".join(f"{z['kind']}@{z['at']}" for z in zones[h])
                rep["horizons"][h] = {"status": EVENT_ZONE, "reason": why, "v1": EVENT_ZONE, "v2": EVENT_ZONE}
                continue
            (a, ra), (c, rc_) = s1[h], s2[h]
            both = a == OK and c == OK
            rep["horizons"][h] = {"status": OK if both else NOT_COMPUTABLE,
                                  "reason": None if both else ("V1:" + str(ra) if a != OK else "V2:" + str(rc_)),
                                  "v1": a, "v2": c}
            if both:
                paired.append(h)
        return {"report": rep, "v1": b1, "v2": b2, "paired": paired, "v1_status": s1, "v2_status": s2}
    except Exception as exc:  # noqa: BLE001 - the shadow never breaks its caller
        logger.warning("rangecast shadow failed: %s", type(exc).__name__)
        rep = {"schema": SHADOW_SCHEMA, "adapter_version": ADAPTER_VERSION, "status": NOT_COMPUTABLE,
               "reason": type(exc).__name__, "now": _iso(snap.now), "as_of": None, "issue_slot": None, "price": None,
               "anchor_close_ms": None, "horizons": {}}
        return {"report": rep, "v1": None, "v2": None, "paired": []}


# ---- the hourly record ----------------------------------------------------------------------------------------
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


def _identity(bound, procedure_id: str, spec_id: str, model: Optional[Mapping[str, Any]], extra: Mapping) -> dict:
    return {"procedure_id": procedure_id, "spec_id": spec_id,
            "spec_digest": None if bound is None else bound.spec_digest,
            "snapshot_id": None if bound is None else bound.snapshot_id,
            "model_version": None if model is None else model.get("version"), **extra}


def _model_record(bound, ident: Mapping[str, Any], status: tuple, *, h: str, as_of: Optional[datetime],
                  targets: Sequence[Mapping], pairs: Sequence[Mapping]) -> dict:
    from .claims import printed_prob
    rec = {**ident, "horizon": h, "as_of": None if as_of is None else _iso(as_of),
           "horizon_end": None if as_of is None else _iso(as_of + timedelta(milliseconds=rc.HORIZON_MS[h])),
           "status": status[0], "reason": status[1], "touch": [], "neither": []}
    if status[0] != OK or bound is None:
        return rec
    for t in targets:
        if t.get("status") == INVALID_TARGET:
            rec["touch"].append(dict(t))
            continue
        p = bound.touch_probability(horizon=h, distance_pct=float(t["distance_pct"]), side=int(t["side"]))
        rec["touch"].append({**t, "status": OK, "probability": _round(p), "printed": printed_prob(p)})
    for q in pairs:
        du, dd = float(q["up_pct"]), float(q["down_pct"])
        try:
            p = bound.neither_probability(horizon=h, distance_up_pct=du, distance_down_pct=dd)
        except KeyError:
            rec["neither"].append({**q, "status": NOT_COMPUTABLE, "reason": "NO_JOINT_TABLE"})
            continue
        rec["neither"].append({**q, "status": OK, "probability": _round(p), "printed": printed_prob(p),
                               "p_up": _round(bound.touch_probability(horizon=h, distance_pct=du, side=1)),
                               "p_down": _round(bound.touch_probability(horizon=h, distance_pct=dd, side=-1))})
    return rec


def paired_forecast(snap: Snapshot, *, v1_model: Optional[Mapping[str, Any]], v2_model: Optional[Mapping[str, Any]],
                    v1_ids: Optional[Mapping[str, Any]] = None, horizons: Sequence[str] = HORIZONS,
                    touch_grid_pct: Sequence[float] = TOUCH_GRID_PCT, neither_grid_pct: Sequence[float] = NEITHER_GRID_PCT,
                    target_prices: Sequence[float] = ()) -> dict:
    """V1 and V2 numbers per horizon on one anchor, for the journal grid and any target prices, with their
    identities: the record `paired_shadow.plan_shadow_record` / `execute_hour` store. `v1_ids` may carry the
    production statistics row (`stats_pk`, `stats_digest`) the V1 model came from. Nothing is stored. Never
    raises."""
    prep = prepare_issue(snap, v1_model=v1_model, v2_model=v2_model, horizons=horizons)
    out = {k: v for k, v in prep["report"].items() if k != "horizons"}
    out["horizons"] = {}
    try:
        as_of = None if out["as_of"] is None else _utc(out["as_of"])
        ok = out["status"] == OK
        targets = touch_targets(float(snap.price), grid_pct=touch_grid_pct, target_prices=target_prices) if ok else []
        pairs = neither_pairs(float(snap.price), neither_grid_pct) if ok else []
        ids = dict(v1_ids or {})
        id1 = _identity(prep["v1"], V1_PROCEDURE_ID, V1_SPEC_ID, v1_model,
                        {"stats_pk": ids.get("stats_pk"), "stats_digest": ids.get("stats_digest")})
        id2 = _identity(prep["v2"], v2.SHADOW_PROCEDURE_ID, v2.SHADOW_SPEC_ID, v2_model,
                        {"params_digest": None if prep["v2"] is None else prep["v2"].snapshot_id,
                         "artifact_id": None if v2_model is None else v2_model.get("artifact_id")})
        for h, hs in prep["report"]["horizons"].items():
            s1 = prep.get("v1_status", {}).get(h, (hs["v1"], hs["reason"]))
            s2 = prep.get("v2_status", {}).get(h, (hs["v2"], hs["reason"]))
            out["horizons"][h] = {"status": hs["status"], "reason": hs["reason"], "paired": h in prep["paired"],
                                  "v1": _model_record(prep["v1"], id1, s1, h=h, as_of=as_of, targets=targets, pairs=pairs),
                                  "v2": _model_record(prep["v2"], id2, s2, h=h, as_of=as_of, targets=targets, pairs=pairs)}
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("rangecast shadow forecast failed: %s", type(exc).__name__)
        return {**out, "status": NOT_COMPUTABLE, "reason": type(exc).__name__, "horizons": {}}


def plan_paired_issues(snap: Snapshot, *, v1_model: Optional[Mapping[str, Any]], v2_model: Optional[Mapping[str, Any]],
                       v1_ids: Optional[Mapping[str, Any]] = None) -> dict:
    """{record, planned}: the hourly record and the store rows `paired_shadow.plan_shadow_record` builds from
    it, the rows `execute_hour` would store. Writes nothing; the store's mapper is the only row builder."""
    from .paired_shadow import plan_shadow_record
    record = paired_forecast(snap, v1_model=v1_model, v2_model=v2_model, v1_ids=v1_ids)
    slot = snap.now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return {"record": record, "planned": plan_shadow_record(record, issue_slot=slot)}
