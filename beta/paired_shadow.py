"""Paired shadow store for Rangecast V1 and Rangecast V2.

This module does not write ``beta_claims``, does not change user text, and does not
call health or the notifier. Recording stays off until the owner allows it. The
tables live in ``storage/beta_paired_shadow_schema.sql``, which is not part of
``apply_beta_schema``.

A book in Monitor V2 is one procedure and one specification. A nightly refit changes
``snapshot_id`` only. A new specification is a new stream. The first write of a
probability for an anchor is kept.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from beta.calibration_monitor import (
    JOURNAL_SPEC_ID, PROCEDURE_TOUCH_CHANCE, evaluate as monitor_evaluate,
    observations_from_claim_rows,
)
from beta.claims import (
    HORIZON_MS, NEITHER_GRID_PCT, TOUCH_GRID_PCT, eval_rule, evaluate as score_claim,
)
from beta.state_tape import sha256_json

SHADOW_RECORDING_ENABLED = False
PRIMARY_SYMBOL = "BTCUSDT"
PRIMARY_HORIZON = "4h"
HORIZONS = ("1h", "4h", "24h")
FAMILIES = ("touch", "neither")
V1_PROCEDURE_ID = "RANGECAST_V1"
V1_SPEC_ID = "RANGECAST_V1"
V2_PROCEDURE_ID = "RANGECAST_V2"
V2_SPEC_ID = "W_L1"
# Amendment 1 of BETA_PAIRED_SHADOW_CONTRACT_V1, as specified by
# docs/RANGECAST_V2_SHADOW_CONTRACT_V2.md. procedure_digest is the sha256 of every
# constant of the procedure beyond its coefficients. This store imports no model code.
# The binders refuse to issue when the code no longer computes these objects.
# Coefficients are not identity. A refit changes snapshot_id only.
V2_RECORD_SPEC_ID = "RANGECAST_V2_W_L1"
V2_RECORD_PROCEDURE_ID = "TOUCH_CHANCE_PROCEDURE_RCV2_W_L1"
V1_RECORD_PROCEDURE_ID = "TOUCH_CHANCE_PROCEDURE_V1"
V2_PROCEDURE_DIGEST = "e573ae5d65894bb7b98831014aa3fd3fb3807aa1badaed89eb6b42f5288cb3b6"
V1_PROCEDURE_DIGEST = "4aef58b31d70164e15486cd71b9468349fc517935deb6262d8035bf2881873f7"
V2_SPEC_IDENTITY = {
    "procedure_id": V2_PROCEDURE_ID,
    "spec_id": V2_SPEC_ID,
    "level": "L1",
    "half_life_days": 365,
    "symbol": PRIMARY_SYMBOL,
    "market": "binance_usdm",
    "procedure_digest": V2_PROCEDURE_DIGEST,
}
V1_SPEC_IDENTITY = {
    "procedure_id": V1_PROCEDURE_ID,
    "spec_id": V1_SPEC_ID,
    "surface": "beta.rangecast.touch_probability+neither_probability",
    "symbol": PRIMARY_SYMBOL,
    "procedure_digest": V1_PROCEDURE_DIGEST,
}
V1_SPEC_DIGEST = sha256_json(V1_SPEC_IDENTITY)
V2_SPEC_DIGEST = sha256_json(V2_SPEC_IDENTITY)
# The frozen artifact's own spec_digest is sha256 of rangecast_v2.spec() (the math only).
# It is not the store's spec_digest and it is not a stream id.
V2_ARTIFACT_MATH_DIGEST = "00539f2d2a1660c861d4ee7cbd411a010b2f296f3af3826b8ab527cc98727246"
V2_ARTIFACT_ID = "RANGECAST_V2_W_L1_MODEL_V1"
V2_ARTIFACT_SHA256 = "2c7e3eca0d90f12d11e7a10558ffaed8d719ff63d630f2c7b252fd6030f70533"
V2_PARAMS_DIGEST = "095f409f024c3a968d0ec4dc14ca99a3cea67d27c58c3329c241fce02569e261"
DEFAULT_SETTLE_LIMIT = 500
DEFAULT_SETTLE_BATCHES = 8
_V2_RECORD_PROCEDURES = frozenset({V2_RECORD_PROCEDURE_ID, V2_PROCEDURE_ID})
_V2_RECORD_SPECS = frozenset({V2_RECORD_SPEC_ID, V2_SPEC_ID})
_V1_RECORD_PROCEDURES = frozenset({V1_RECORD_PROCEDURE_ID, V1_PROCEDURE_ID})
HOUR_STATUSES = (
    "OK", "STALE_DATA", "INSUFFICIENT_HISTORY", "INCOMPLETE_WINDOW", "EVENT_ZONE",
    "NO_MODEL", "MODEL_INVALID", "NOT_COMPUTABLE", "INVALID_TARGET", "PENDING",
)
TOUCH_RULE_ID = "TOUCH_V1"
NEITHER_RULE_ID = "NEITHER_V1"
_LOG_LOSS_CLIP = 1e-6
_ID_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class ShadowRecordingDisabled(RuntimeError):
    """The owner has not allowed shadow rows to be stored."""


class ShadowConflict(ValueError):
    """A second write disagreed with the row already stored."""


class BoundShadowModel:
    """Probabilities at one already-chosen issue. No journal write."""

    def __init__(self, *, procedure_id: str, spec_id: str, spec_digest: str, snapshot_id: str,
                 touch, neither):
        self.procedure_id = _require_id(procedure_id, "procedure_id")
        self.spec_id = _require_id(spec_id, "spec_id")
        self.spec_digest = _require_digest(spec_digest)
        self.snapshot_id = _require_snapshot(snapshot_id)
        self._touch = touch
        self._neither = neither

    def touch_probability(self, *, horizon: str, distance_pct: float, side: int) -> float:
        return float(self._touch(horizon, distance_pct, side))

    def neither_probability(self, *, horizon: str, distance_up_pct: float,
                            distance_down_pct: float) -> float:
        return float(self._neither(horizon, distance_up_pct, distance_down_pct))


def bind_rangecast_v1(model: Mapping, scales: Mapping[str, float], *, snapshot_id: str) -> BoundShadowModel:
    """V1 probabilities from ``beta.rangecast``. ``scales`` is the horizon scale at issue.

    The sharp-move detector is not read. ``side`` does not change the V1 touch chance;
    the anchor still records the side, so the two directions stay separate outcomes.
    """
    from beta.rangecast import neither_probability, touch_probability

    def touch(horizon: str, distance_pct: float, side: int) -> float:
        del side
        return touch_probability(model, horizon, float(scales[horizon]), distance_pct)

    def neither(horizon: str, distance_up_pct: float, distance_down_pct: float) -> float:
        scale = float(scales[horizon])
        p_up = touch_probability(model, horizon, scale, distance_up_pct)
        p_down = touch_probability(model, horizon, scale, distance_down_pct)
        return neither_probability(
            model, horizon, scale, distance_up_pct, distance_down_pct, p_up=p_up, p_down=p_down,
        )

    return BoundShadowModel(
        procedure_id=V1_PROCEDURE_ID, spec_id=V1_SPEC_ID, spec_digest=V1_SPEC_DIGEST,
        snapshot_id=snapshot_id, touch=touch, neither=neither,
    )


def anchor_key(*, symbol: str, family: str, horizon: str, issue_slot: datetime, side: Optional[int],
               distance_pct: Optional[float], distance_up_pct: Optional[float],
               distance_down_pct: Optional[float], eval_rule_id: str, eval_rule_digest: str) -> str:
    """Identity of the market question. Procedure, snapshot and prices are not part of it."""
    slot = _utc(issue_slot).strftime("%Y-%m-%dT%H:%M:%SZ")
    side_text = "-" if side is None else f"{int(side):+d}"
    parts = [
        "PAIRED-SHADOW-V1", symbol, family, horizon, slot, side_text,
        _num(distance_pct), _num(distance_up_pct), _num(distance_down_pct),
        eval_rule_id, eval_rule_digest,
    ]
    return "|".join(parts)


def plan_issues(models: Sequence[BoundShadowModel], *, price: float, as_of: datetime,
                issue_slot: datetime, issued_at: Optional[datetime] = None,
                horizons: Sequence[str] = (PRIMARY_HORIZON,),
                distances: Optional[Sequence[float]] = None,
                neither_pairs: Optional[Sequence[tuple]] = None) -> list:
    """One row per model, family, horizon and distance. Every model shares the anchors.

    ``price`` freezes the barrier for later scoring and is not part of the anchor key.
    The barrier is ``price * (1 ± distance/100)`` with no rounding. The user journal
    rounds its level to cents; this shadow pair does not, and both models use this one.
    """
    if not math.isfinite(price) or price <= 0:
        raise ValueError("price must be a positive finite number")
    as_of = _utc(as_of)
    issue_slot = _utc(issue_slot)
    issued_at = as_of if issued_at is None else _utc(issued_at)
    horizons = tuple(horizons)
    for horizon in horizons:
        if horizon not in HORIZONS:
            raise ValueError(f"unknown horizon {horizon}")
    if distances is None:
        distances = TOUCH_GRID_PCT
    if neither_pairs is None:
        neither_pairs = tuple((up, down) for up in NEITHER_GRID_PCT for down in NEITHER_GRID_PCT)
    seen = set()
    for model in models:
        ident = (model.procedure_id, model.spec_id)
        if ident in seen:
            raise ValueError(f"two models share {ident[0]} / {ident[1]}")
        seen.add(ident)
    touch_digest = sha256_json(eval_rule(TOUCH_RULE_ID))
    neither_digest = sha256_json(eval_rule(NEITHER_RULE_ID))
    rows = []
    for horizon in horizons:
        horizon_end = as_of + timedelta(milliseconds=HORIZON_MS[horizon])
        for distance in distances:
            distance = float(distance)
            if not math.isfinite(distance) or distance <= 0:
                raise ValueError("distance_pct must be positive")
            for side in (+1, -1):
                level = price * (1.0 + side * distance / 100.0)
                key = anchor_key(
                    symbol=PRIMARY_SYMBOL, family="touch", horizon=horizon, issue_slot=issue_slot,
                    side=side, distance_pct=distance, distance_up_pct=None, distance_down_pct=None,
                    eval_rule_id=TOUCH_RULE_ID, eval_rule_digest=touch_digest,
                )
                anchor = {
                    "anchor_key": key, "symbol": PRIMARY_SYMBOL, "family": "touch", "horizon": horizon,
                    "issue_slot": issue_slot, "as_of": as_of, "horizon_end": horizon_end,
                    "side": side, "distance_pct": distance, "distance_up_pct": None,
                    "distance_down_pct": None,
                    "level_up": level if side > 0 else None,
                    "level_down": level if side < 0 else None,
                    "eval_rule_id": TOUCH_RULE_ID, "eval_rule_digest": touch_digest,
                }
                for model in models:
                    rows.append(_issue(anchor, model, model.touch_probability(
                        horizon=horizon, distance_pct=distance, side=side,
                    ), issued_at))
        for up, down in neither_pairs:
            up, down = float(up), float(down)
            if up <= 0 or down <= 0:
                raise ValueError("neither distances must be positive")
            key = anchor_key(
                symbol=PRIMARY_SYMBOL, family="neither", horizon=horizon, issue_slot=issue_slot,
                side=None, distance_pct=None, distance_up_pct=up, distance_down_pct=down,
                eval_rule_id=NEITHER_RULE_ID, eval_rule_digest=neither_digest,
            )
            anchor = {
                "anchor_key": key, "symbol": PRIMARY_SYMBOL, "family": "neither", "horizon": horizon,
                "issue_slot": issue_slot, "as_of": as_of, "horizon_end": horizon_end,
                "side": None, "distance_pct": None, "distance_up_pct": up, "distance_down_pct": down,
                "level_up": price * (1.0 + up / 100.0),
                "level_down": price * (1.0 - down / 100.0),
                "eval_rule_id": NEITHER_RULE_ID, "eval_rule_digest": neither_digest,
            }
            for model in models:
                rows.append(_issue(anchor, model, model.neither_probability(
                    horizon=horizon, distance_up_pct=up, distance_down_pct=down,
                ), issued_at))
    return rows


class ShadowLedger:
    """In-memory store with the same keep-first and revision rules as the SQL file."""

    def __init__(self):
        self.anchors: dict = {}
        self.issues: dict = {}
        self.outcomes: dict = {}
        self.spec_digests: dict = {}
        self.hour_status: dict = {}

    def record_issues(self, rows: Sequence[Mapping], *, allow_write: bool = False) -> dict:
        _require_recording(allow_write)
        known = dict(self.spec_digests)
        for row in rows:
            spec_key = (row["procedure_id"], row["spec_id"])
            digest = row["spec_digest"]
            if spec_key in known and known[spec_key] != digest:
                raise ShadowConflict(
                    f"{spec_key[0]} / {spec_key[1]} already has another spec_digest; use a new spec_id"
                )
            known[spec_key] = digest
            key = row["anchor_key"]
            stored = self.anchors.get(key)
            if stored is not None and _anchor_body(stored) != _anchor_body(row):
                raise ShadowConflict(f"anchor {key} was already frozen")
            ident = (key, row["procedure_id"], row["spec_id"])
            previous = self.issues.get(ident)
            if previous is not None and previous["spec_digest"] != digest:
                raise ShadowConflict("spec_id changed its digest; use a new spec_id")
        inserted = kept = 0
        self.spec_digests = known
        for row in rows:
            key = row["anchor_key"]
            if key not in self.anchors:
                self.anchors[key] = {field: row[field] for field in _ANCHOR_FIELDS}
            ident = (key, row["procedure_id"], row["spec_id"])
            if ident not in self.issues:
                self.issues[ident] = {
                    "probability": float(row["probability"]),
                    "snapshot_id": row["snapshot_id"],
                    "spec_digest": row["spec_digest"],
                    "issued_at": row["issued_at"],
                }
                inserted += 1
            else:
                kept += 1
        return {"inserted": inserted, "kept": kept}

    def record_hour_statuses(self, rows: Sequence[Mapping], *, allow_write: bool = False) -> dict:
        _require_recording(allow_write)
        incoming = []
        for row in rows:
            horizon = row["horizon"]
            status = row["status"]
            if horizon not in HORIZONS:
                raise ValueError(f"unknown horizon {horizon}")
            if status not in HOUR_STATUSES:
                raise ValueError(f"unknown hour status {status}")
            slot = _utc(row["issue_slot"])
            payload = {"status": status, "reason": row.get("reason")}
            current = self.hour_status.get((slot, horizon))
            if current is not None and current != payload:
                raise ShadowConflict(f"hour {horizon} already has status {current['status']}")
            incoming.append((slot, horizon, payload))
        inserted = kept = 0
        for slot, horizon, payload in incoming:
            if (slot, horizon) in self.hour_status:
                kept += 1
            else:
                self.hour_status[(slot, horizon)] = payload
                inserted += 1
        return {"inserted": inserted, "kept": kept}

    def record_outcome(self, anchor_key: str, *, status: str, outcome: Optional[int],
                       coverage: Optional[float], eval_rule_digest: str, computed_at: datetime,
                       revision: Optional[int] = None, correction_note: Optional[str] = None,
                       allow_write: bool = False) -> dict:
        _require_recording(allow_write)
        anchor = self.anchors.get(anchor_key)
        if anchor is None:
            raise KeyError(anchor_key)
        if eval_rule_digest != anchor["eval_rule_digest"]:
            raise ShadowConflict("outcome under another evaluation rule")
        if status not in ("COMPLETE", "INCOMPLETE_DATA", "NO_DATA"):
            raise ValueError("unknown outcome status")
        if outcome not in (None, 0, 1):
            raise ValueError("outcome must be 0, 1, or absent")
        revisions = self.outcomes.setdefault(anchor_key, [])
        number = len(revisions) + 1 if revision is None else int(revision)
        if number < 1 or number > len(revisions) + 1:
            raise ValueError("outcome revisions must be the next integer")
        payload = {
            "revision": number, "status": status, "outcome": outcome, "coverage": coverage,
            "eval_rule_digest": eval_rule_digest, "computed_at": _utc(computed_at),
            "correction_note": correction_note,
        }
        if number <= len(revisions):
            current = revisions[number - 1]
            if current != payload:
                raise ShadowConflict(f"revision {number} already stored")
            return {"revision": number, "stored": False}
        if number > 1 and not correction_note:
            raise ValueError("a revised outcome needs a correction note")
        revisions.append(payload)
        return {"revision": number, "stored": True}

    def latest_outcome(self, anchor_key: str) -> Optional[dict]:
        revisions = self.outcomes.get(anchor_key) or []
        return None if not revisions else revisions[-1]

    def due_unscored(self, now: datetime, *, limit: int) -> list:
        """Elapsed anchors with no outcome, oldest first, at most ``limit``.

        An anchor whose horizon is still open is not returned. An anchor that already
        has an outcome is not returned, so a restarted batch continues after the last
        stored outcome.
        """
        if limit < 1:
            raise ValueError("limit must be positive")
        moment = _utc(now)
        due = [
            anchor for anchor in self.anchors.values()
            if anchor["horizon_end"] <= moment and not self.outcomes.get(anchor["anchor_key"])
        ]
        due.sort(key=lambda row: (row["horizon_end"], row["anchor_key"]))
        return due[:int(limit)]

    def joined_rows(self) -> list:
        out = []
        for (anchor_key, procedure_id, spec_id), issue in sorted(self.issues.items()):
            anchor = self.anchors[anchor_key]
            latest = self.latest_outcome(anchor_key)
            out.append({
                **anchor,
                "procedure_id": procedure_id,
                "spec_id": spec_id,
                "spec_digest": issue["spec_digest"],
                "snapshot_id": issue["snapshot_id"],
                "probability": issue["probability"],
                "issued_at": issue["issued_at"],
                "status": None if latest is None else latest["status"],
                "outcome": None if latest is None else latest["outcome"],
                "coverage": None if latest is None else latest["coverage"],
                "outcome_revision": None if latest is None else latest["revision"],
            })
        return out


def score_anchor(anchor: Mapping, bars, *, now: datetime, closed_1m=()) -> dict:
    """One market outcome for the anchor, through ``beta.claims.evaluate``.

    The returned record has no high, low, close or first-touch time. Both procedures
    read this one record.
    """
    subject = {}
    if anchor["family"] == "touch":
        level = anchor["level_up"] if anchor["side"] > 0 else anchor["level_down"]
        subject = {"side": int(anchor["side"]), "level": float(level)}
    else:
        subject = {"level_up": float(anchor["level_up"]), "level_down": float(anchor["level_down"])}
    claim = {
        "eval_rule": {"id": anchor["eval_rule_id"]},
        "as_of": anchor["as_of"],
        "horizon_end": anchor["horizon_end"],
        "subject": subject,
    }
    scored = score_claim(claim, bars, closed_1m, now=now)
    if scored is None:
        return {"status": "PENDING", "outcome": None, "coverage": None}
    status, realized = scored
    if anchor["family"] == "touch":
        bit = realized.get("touched")
    else:
        bit = realized.get("neither")
    outcome = None if bit is None else int(bool(bit))
    coverage = realized.get("coverage")
    return {
        "status": status,
        "outcome": outcome,
        "coverage": None if coverage is None else float(coverage),
    }


def log_loss(probability: float, outcome: float) -> float:
    p = min(max(float(probability), _LOG_LOSS_CLIP), 1.0 - _LOG_LOSS_CLIP)
    y = float(outcome)
    return -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))


def brier(probability: float, outcome: float) -> float:
    return (float(probability) - float(outcome)) ** 2


def paired_report(rows: Sequence[Mapping], *, procedure_v1: str = V1_PROCEDURE_ID,
                  procedure_v2: str = V2_PROCEDURE_ID, spec_v1: str = V1_SPEC_ID,
                  spec_v2: str = V2_SPEC_ID) -> dict:
    """Mean log loss and Brier of one specification pair, and the V2 minus V1 difference.

    A pair is one anchor with both named specifications and a latest outcome the monitor
    would score: status COMPLETE, and coverage absent or at least 0.9. The same outcome
    is used for both probabilities. Another spec_id is a separate comparison.
    """
    by_anchor: dict = {}
    for row in rows:
        ident = (row["procedure_id"], row["spec_id"])
        by_anchor.setdefault(row["anchor_key"], {})[ident] = row
    groups: dict = {}
    unscored = 0
    for present in by_anchor.values():
        left = present.get((procedure_v1, spec_v1))
        right = present.get((procedure_v2, spec_v2))
        if left is None or right is None:
            unscored += 1
            continue
        if not _scored(left) or not _scored(right) or left["outcome"] != right["outcome"]:
            unscored += 1
            continue
        y = float(left["outcome"])
        cell = groups.setdefault((left["horizon"], left["family"]), [])
        cell.append((log_loss(left["probability"], y), log_loss(right["probability"], y),
                     brier(left["probability"], y), brier(right["probability"], y)))
    report = {}
    for (horizon, family), items in sorted(groups.items()):
        n = len(items)
        ll1 = sum(item[0] for item in items) / n
        ll2 = sum(item[1] for item in items) / n
        br1 = sum(item[2] for item in items) / n
        br2 = sum(item[3] for item in items) / n
        report.setdefault(horizon, {})[family] = {
            "n": n,
            "log_loss_v1": ll1,
            "log_loss_v2": ll2,
            "log_loss_v2_minus_v1": ll2 - ll1,
            "brier_v1": br1,
            "brier_v2": br2,
            "brier_v2_minus_v1": br2 - br1,
        }
    return {
        "procedure_v1": procedure_v1,
        "procedure_v2": procedure_v2,
        "spec_v1": spec_v1,
        "spec_v2": spec_v2,
        "primary_horizon": PRIMARY_HORIZON,
        "n_unscored_anchors": unscored,
        "horizons": report,
    }


def monitor_observations(rows: Sequence[Mapping], *, now: Optional[datetime] = None) -> list:
    """Monitor V2 observations. Each procedure and specification stays on its own book.

    The production journal's procedure is not used here. A shadow row names its own.
    An anchor with no outcome whose horizon is still open is PENDING, not a hole.
    """
    clock = None if now is None else _utc(now)
    adapted = []
    for row in rows:
        if row.get("family") == "touch":
            claim_class = f"L3_DISTANCE_TOUCH_{str(row['horizon']).upper()}"
            realized = {"touched": None if row.get("outcome") is None else bool(row["outcome"])}
        else:
            claim_class = f"L3_NEITHER_{str(row['horizon']).upper()}"
            realized = {"neither": None if row.get("outcome") is None else bool(row["outcome"])}
        if row.get("coverage") is not None:
            realized["coverage"] = row["coverage"]
        status = row.get("status")
        if status in (None, "", "MISSING", "PENDING") and row.get("outcome") is None:
            end = row.get("horizon_end")
            if status == "PENDING" or (clock is not None and isinstance(end, datetime) and end > clock):
                status = "PENDING"
            else:
                status = "MISSING"
        elif not status:
            status = "MISSING"
        adapted.append({
            "claim_class": claim_class,
            "procedure_id": row["procedure_id"],
            "spec_id": row["spec_id"],
            "as_of": row["as_of"],
            "horizon_end": row["horizon_end"],
            "probability": row["probability"],
            "snapshot_id": row["snapshot_id"],
            "eval_rule_digest": row["eval_rule_digest"],
            "eval_rule_id": row["eval_rule_id"],
            "status": status,
            "realized": realized,
        })
    observations = observations_from_claim_rows(adapted, now=clock)
    for observation, row in zip(observations, adapted):
        if observation["procedure_id"] != row["procedure_id"]:
            raise ShadowConflict("monitor adapter rewrote the procedure")
        if observation["spec_id"] != row["spec_id"]:
            raise ShadowConflict("monitor adapter rewrote the specification")
        if observation["procedure_id"] == PROCEDURE_TOUCH_CHANCE or observation["spec_id"] == JOURNAL_SPEC_ID:
            raise ShadowConflict("a shadow issue fell into the production journal book")
    return observations


def plan_shadow_record(record: Mapping, *, issue_slot: datetime) -> dict:
    """Turn one ``paired_forecast`` record into store rows. Writes nothing.

    Claude's record labels are mapped onto ``RANGECAST_V1`` / ``RANGECAST_V2`` and
    ``W_L1``. A horizon that is not ``OK`` contributes a diagnostic and no probability.
    The stored barrier is the unrounded distance, not the cent-rounded level in the record.
    """
    issue_slot = _utc(issue_slot)
    status = str(record.get("status") or "NOT_COMPUTABLE")
    reason = record.get("reason")
    blocks = record.get("horizons") or {}
    if status != "OK":
        return {
            "status": status, "reason": reason, "rows": [],
            "horizons": _failed_horizons(blocks, status, reason),
        }
    try:
        price = float(record["price"])
        as_of = _parse_time(record["as_of"])
    except (KeyError, TypeError, ValueError):
        return {
            "status": "NOT_COMPUTABLE", "reason": "RECORD_WITHOUT_PRICE_OR_TIME", "rows": [],
            "horizons": _failed_horizons(blocks, "NOT_COMPUTABLE", "RECORD_WITHOUT_PRICE_OR_TIME"),
        }
    if not math.isfinite(price) or price <= 0:
        return {
            "status": "NOT_COMPUTABLE", "reason": "RECORD_WITHOUT_PRICE_OR_TIME", "rows": [],
            "horizons": _failed_horizons(blocks, "NOT_COMPUTABLE", "RECORD_WITHOUT_PRICE_OR_TIME"),
        }
    rows = []
    horizons = {}
    for horizon, block in blocks.items():
        if horizon not in HORIZONS:
            horizons[horizon] = {"status": "NOT_COMPUTABLE", "reason": "UNKNOWN_HORIZON", "n_issues": 0}
            continue
        block = block or {}
        horizon_status = str(block.get("status") or "NOT_COMPUTABLE")
        if horizon_status != "OK":
            horizons[horizon] = {
                "status": horizon_status, "reason": block.get("reason"), "n_issues": 0,
            }
            continue
        built, skip_reason = _rows_for_horizon(
            block, price=price, as_of=as_of, issue_slot=issue_slot, horizon=horizon,
        )
        if skip_reason:
            horizons[horizon] = {"status": "MODEL_INVALID", "reason": skip_reason, "n_issues": 0}
            continue
        rows.extend(built)
        horizons[horizon] = {"status": "OK" if built else "NOT_COMPUTABLE",
                             "reason": None if built else "NO_PAIRED_PROBABILITY",
                             "n_issues": len(built)}
    overall = "OK" if any(item["status"] == "OK" for item in horizons.values()) else "NOT_COMPUTABLE"
    return {"status": overall, "reason": None if overall == "OK" else "NO_PAIRED_HORIZON",
            "rows": rows, "horizons": horizons}


def execute_hour(record: Mapping, ledger, *, issue_slot: datetime, allow_write: bool = False,
                 bars=None, now: Optional[datetime] = None, score: bool = False,
                 settle_limit: int = DEFAULT_SETTLE_LIMIT,
                 settle_batches: int = DEFAULT_SETTLE_BATCHES, report: bool = True) -> dict:
    """Plan one hour. The default does not write.

    ``allow_write=True`` is the owner's later switch. It is not set by this module.
    A write always launches settlement. ``score`` is accepted for older callers and
    does not turn settlement off. Without bars the settlement reports ``NO_BARS``
    and stores no outcome. ``report=False`` skips the full-journal monitor read.
    """
    if not isinstance(score, bool):
        raise TypeError("score must be bool")
    planned = plan_shadow_record(record, issue_slot=issue_slot)
    summary = {
        "status": planned["status"],
        "reason": planned["reason"],
        "written": False,
        "inserted": 0,
        "kept": 0,
        "horizons": planned["horizons"],
        "scoring": [],
        "settlement": {"launched": False, "status": "NOT_WRITTEN", "selected": 0,
                       "stored": 0, "kept": 0, "pending": 0, "limit": settle_limit},
        "paired": None,
        "books": [],
    }
    if not allow_write and not SHADOW_RECORDING_ENABLED:
        return summary
    issue_slot = _utc(issue_slot)
    statuses = [
        {"issue_slot": issue_slot, "horizon": horizon, "status": item["status"], "reason": item.get("reason")}
        for horizon, item in planned["horizons"].items()
        if horizon in HORIZONS
    ]
    if planned["rows"]:
        stored = ledger.record_issues(planned["rows"], allow_write=True)
    else:
        stored = {"inserted": 0, "kept": 0}
    ledger.record_hour_statuses(statuses, allow_write=True)
    summary["written"] = True
    summary["inserted"] = stored["inserted"]
    summary["kept"] = stored["kept"]
    clock = _utc(now) if now is not None else datetime.now(timezone.utc)
    # `score` remains in the signature for callers written before settlement was
    # part of every write. It does not skip settlement.
    summary["settlement"] = settle_due(
        ledger, bars, now=clock, limit=settle_limit, allow_write=True, max_batches=settle_batches,
    )
    summary["scoring"] = summary["settlement"]["reports"]
    if report:
        joined = ledger.joined_rows()
        summary["paired"] = paired_report(joined)
        books = monitor_evaluate(monitor_observations(joined, now=clock))["books"]
        summary["books"] = [
            {"procedure_id": book["procedure_id"], "spec_id": book["spec_id"], "family": book["family"],
             "horizon": book["horizon"], "state": book["state"],
             "n_pending": book["n_pending"], "n_unfinished": book["n_unfinished"],
             "n_rows": book["n_rows"]}
            for book in books
        ]
    return summary


def _failed_horizons(blocks: Mapping, status: str, reason) -> dict:
    if not blocks:
        return {horizon: {"status": status, "reason": reason, "n_issues": 0} for horizon in HORIZONS}
    return {
        horizon: {"status": str((block or {}).get("status") or status),
                  "reason": (block or {}).get("reason") if block else reason, "n_issues": 0}
        for horizon, block in blocks.items()
    }


def _rows_for_horizon(block: Mapping, *, price: float, as_of: datetime, issue_slot: datetime,
                      horizon: str) -> tuple:
    v1 = block.get("v1") or {}
    v2 = block.get("v2") or {}
    if v1.get("procedure_id") not in _V1_RECORD_PROCEDURES:
        return [], "V1_PROCEDURE"
    if v2.get("procedure_id") not in _V2_RECORD_PROCEDURES or v2.get("spec_id") not in _V2_RECORD_SPECS:
        return [], "V2_IDENTITY"
    if v2.get("spec_digest") != V2_SPEC_DIGEST:
        return [], "V2_SPEC_DIGEST"
    snapshot_v2 = v2.get("params_digest") or v2.get("snapshot_id")
    snapshot_v1 = v2_snapshot_v1(v1)
    if not snapshot_v1 or not snapshot_v2:
        return [], "SNAPSHOT_MISSING"
    touch_digest = sha256_json(eval_rule(TOUCH_RULE_ID))
    neither_digest = sha256_json(eval_rule(NEITHER_RULE_ID))
    horizon_end = as_of + timedelta(milliseconds=HORIZON_MS[horizon])
    issued_at = as_of
    rows = []
    v1_touch = _ok_by_key(v1.get("touch") or (), lambda item: (int(item["side"]), float(item["distance_pct"])))
    v2_touch = _ok_by_key(v2.get("touch") or (), lambda item: (int(item["side"]), float(item["distance_pct"])))
    for key in sorted(set(v1_touch) & set(v2_touch)):
        side, distance = key
        if distance <= 0:
            continue
        level = price * (1.0 + side * distance / 100.0)
        anchor = {
            "anchor_key": anchor_key(
                symbol=PRIMARY_SYMBOL, family="touch", horizon=horizon, issue_slot=issue_slot,
                side=side, distance_pct=distance, distance_up_pct=None, distance_down_pct=None,
                eval_rule_id=TOUCH_RULE_ID, eval_rule_digest=touch_digest,
            ),
            "symbol": PRIMARY_SYMBOL, "family": "touch", "horizon": horizon,
            "issue_slot": issue_slot, "as_of": as_of, "horizon_end": horizon_end,
            "side": side, "distance_pct": distance, "distance_up_pct": None, "distance_down_pct": None,
            "level_up": level if side > 0 else None, "level_down": level if side < 0 else None,
            "eval_rule_id": TOUCH_RULE_ID, "eval_rule_digest": touch_digest,
        }
        rows.append(_issued(anchor, V1_PROCEDURE_ID, V1_SPEC_ID, V1_SPEC_DIGEST, snapshot_v1,
                            v1_touch[key], issued_at))
        rows.append(_issued(anchor, V2_PROCEDURE_ID, V2_SPEC_ID, V2_SPEC_DIGEST, snapshot_v2,
                            v2_touch[key], issued_at))
    v1_neither = _ok_by_key(v1.get("neither") or (), lambda item: (float(item["up_pct"]), float(item["down_pct"])))
    v2_neither = _ok_by_key(v2.get("neither") or (), lambda item: (float(item["up_pct"]), float(item["down_pct"])))
    for up, down in sorted(set(v1_neither) & set(v2_neither)):
        if up <= 0 or down <= 0:
            continue
        anchor = {
            "anchor_key": anchor_key(
                symbol=PRIMARY_SYMBOL, family="neither", horizon=horizon, issue_slot=issue_slot,
                side=None, distance_pct=None, distance_up_pct=up, distance_down_pct=down,
                eval_rule_id=NEITHER_RULE_ID, eval_rule_digest=neither_digest,
            ),
            "symbol": PRIMARY_SYMBOL, "family": "neither", "horizon": horizon,
            "issue_slot": issue_slot, "as_of": as_of, "horizon_end": horizon_end,
            "side": None, "distance_pct": None, "distance_up_pct": up, "distance_down_pct": down,
            "level_up": price * (1.0 + up / 100.0), "level_down": price * (1.0 - down / 100.0),
            "eval_rule_id": NEITHER_RULE_ID, "eval_rule_digest": neither_digest,
        }
        rows.append(_issued(anchor, V1_PROCEDURE_ID, V1_SPEC_ID, V1_SPEC_DIGEST, snapshot_v1,
                            v1_neither[(up, down)], issued_at))
        rows.append(_issued(anchor, V2_PROCEDURE_ID, V2_SPEC_ID, V2_SPEC_DIGEST, snapshot_v2,
                            v2_neither[(up, down)], issued_at))
    return rows, None


def v2_snapshot_v1(record: Mapping) -> Optional[str]:
    if record.get("stats_digest"):
        return str(record["stats_digest"])
    if record.get("snapshot_id"):
        return str(record["snapshot_id"])
    if record.get("stats_pk") is not None:
        return f"pk:{record['stats_pk']}"
    if record.get("model_version"):
        return str(record["model_version"])
    return None


def _ok_by_key(items, key_of) -> dict:
    out = {}
    for item in items:
        if item.get("status") != "OK" or item.get("probability") is None:
            continue
        try:
            out[key_of(item)] = float(item["probability"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _issued(anchor: Mapping, procedure_id: str, spec_id: str, spec_digest: str, snapshot_id: str,
            probability: float, issued_at: datetime) -> dict:
    model = BoundShadowModel(
        procedure_id=procedure_id, spec_id=spec_id, spec_digest=spec_digest, snapshot_id=snapshot_id,
        touch=lambda *_args, **_kwargs: probability,
        neither=lambda *_args, **_kwargs: probability,
    )
    return _issue(anchor, model, probability, issued_at)


def settle_due(ledger, bars, *, now: datetime, limit: int = DEFAULT_SETTLE_LIMIT,
               allow_write: bool = False, max_batches: int = 1) -> dict:
    """Score elapsed anchors that have no outcome yet.

    Each batch asks the ledger for at most ``limit`` such anchors. A horizon that is
    still open is not selected. ``score_anchor`` may still return PENDING when the
    price window is not yet late enough to call the outcome missing; that anchor is
    left without a row so the next run continues it. An outcome already stored is
    not selected, so a restart resumes after the last committed anchor. One settler
    runs at a time: a second writer of revision 1 hits the unique outcome key.
    """
    _require_recording(allow_write)
    if limit < 1:
        raise ValueError("limit must be positive")
    if max_batches < 1:
        raise ValueError("max_batches must be positive")
    moment = _utc(now)
    summary = {
        "launched": True,
        "status": "OK",
        "limit": int(limit),
        "batches": 0,
        "selected": 0,
        "stored": 0,
        "kept": 0,
        "pending": 0,
        "reports": [],
    }
    if bars is None:
        summary["status"] = "NO_BARS"
        return summary
    for _batch in range(int(max_batches)):
        due = ledger.due_unscored(moment, limit=int(limit))
        summary["batches"] += 1
        summary["selected"] += len(due)
        stored_before = summary["stored"]
        pending_before = summary["pending"]
        for anchor in due:
            scored = score_anchor(anchor, bars, now=moment)
            if scored["status"] == "PENDING":
                summary["pending"] += 1
                summary["reports"].append({
                    "anchor_key": anchor["anchor_key"], "horizon": anchor["horizon"],
                    "family": anchor["family"], "status": "PENDING",
                })
                continue
            written = ledger.record_outcome(
                anchor["anchor_key"], status=scored["status"], outcome=scored["outcome"],
                coverage=scored["coverage"], eval_rule_digest=anchor["eval_rule_digest"],
                computed_at=moment, allow_write=True,
            )
            if written["stored"]:
                summary["stored"] += 1
            else:
                summary["kept"] += 1
            label = scored["status"]
            if scored["coverage"] is not None and scored["coverage"] < 0.9 and scored["status"] == "COMPLETE":
                label = "LOW_COVERAGE"
            summary["reports"].append({
                "anchor_key": anchor["anchor_key"], "horizon": anchor["horizon"],
                "family": anchor["family"], "status": label,
                "outcome": scored["outcome"], "coverage": scored["coverage"],
            })
        made_progress = summary["stored"] > stored_before
        still_open = summary["pending"] > pending_before and not made_progress
        if len(due) < int(limit) or still_open:
            break
    return summary


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return _utc(value)
    return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def export_row(row: Mapping) -> dict:
    """Fields that may leave the host. Barriers, subject and credentials are absent."""
    exported = {
        "anchor_key": row["anchor_key"],
        "symbol": row["symbol"],
        "family": row["family"],
        "horizon": row["horizon"],
        "issue_slot": _iso(row["issue_slot"]),
        "as_of": _iso(row["as_of"]),
        "horizon_end": _iso(row["horizon_end"]),
        "side": row["side"],
        "distance_pct": row["distance_pct"],
        "distance_up_pct": row["distance_up_pct"],
        "distance_down_pct": row["distance_down_pct"],
        "eval_rule_id": row["eval_rule_id"],
        "eval_rule_digest": row["eval_rule_digest"],
        "procedure_id": row["procedure_id"],
        "spec_id": row["spec_id"],
        "spec_digest": row["spec_digest"],
        "snapshot_id": row["snapshot_id"],
        "probability": row["probability"],
        "status": row.get("status"),
        "outcome": row.get("outcome"),
        "coverage": row.get("coverage"),
        "outcome_revision": row.get("outcome_revision"),
    }
    return {key: value for key, value in exported.items() if value is not None}


_ANCHOR_FIELDS = (
    "anchor_key", "symbol", "family", "horizon", "issue_slot", "as_of", "horizon_end",
    "side", "distance_pct", "distance_up_pct", "distance_down_pct", "level_up", "level_down",
    "eval_rule_id", "eval_rule_digest",
)


def _issue(anchor: Mapping, model: BoundShadowModel, probability: float, issued_at: datetime) -> dict:
    probability = float(probability)
    if not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
        raise ValueError("probability must be finite and inside [0, 1]")
    return {**anchor, "procedure_id": model.procedure_id, "spec_id": model.spec_id,
            "spec_digest": model.spec_digest, "snapshot_id": model.snapshot_id,
            "probability": probability, "issued_at": issued_at}


def _anchor_body(row: Mapping) -> tuple:
    return tuple(row[field] for field in _ANCHOR_FIELDS)


def _scored(row: Mapping) -> bool:
    if row.get("status") != "COMPLETE" or row.get("outcome") not in (0, 1):
        return False
    coverage = row.get("coverage")
    return coverage is None or (isinstance(coverage, (int, float)) and coverage >= 0.9)


def _require_recording(allow_write: bool) -> None:
    if allow_write or SHADOW_RECORDING_ENABLED:
        return
    raise ShadowRecordingDisabled(
        "paired shadow recording is off; the owner has not allowed these writes"
    )


def _require_id(value: str, label: str) -> str:
    if not value or len(value) > 64 or any(ch not in _ID_OK for ch in value) or not value[0].isalpha():
        raise ValueError(f"{label} must be an uppercase identifier")
    return value


def _require_digest(value: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("spec_digest must be 64 hex characters")
    return value


def _require_snapshot(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("snapshot_id must be a non-empty string")
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{float(value):.8f}"
