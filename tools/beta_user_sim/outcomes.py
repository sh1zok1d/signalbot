"""Delayed outcome unlock. Only the existing beta outcome definitions are used.

Two observation sources, both with the frozen `beta.outcomes` fields
(`max_up_pct`, `max_down_pct`, `close_return_pct`, `realized_range_pct`, ...):

* push items — the persisted `beta_episode_outcomes` rows of the episode, only for
  the configured `outcome_version`, only the latest revision whose `computed_at`
  is at or before the clock (exactly what the production tracker had written);
* /btc view items — `beta.outcomes.compute_outcome` (the same pure function the
  tracker runs) over the bundle's 1m klines, anchored at the view's
  `data_through` and its `now.reference_price`, on the configured venues. A
  horizon unlocks at anchor + h + LAST_BAR_GRACE (the tracker's own due rule) and
  never after the bundle export time.

Outcomes are observations. Nothing here grades a message; a move is never a
Signalbot failure unless the claim manifest holds a matching forward claim.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

from beta.config import HORIZON_MINUTES, BetaConfig
from beta.outcomes import LAST_BAR_GRACE, OUTCOME_FIELDS, compute_outcome

from .bundle import ReplayBundle
from .timeline import KIND_BTC_VIEW, KIND_PUSH

OUTCOME_LEDGER_VERSION = "SIM_OUTCOME_LEDGER_V0"
SOURCE_PERSISTED = "PERSISTED_EPISODE_OUTCOME"
SOURCE_RECOMPUTED = "RECOMPUTED_VIEW_FORWARD_PATH"
NOT_AVAILABLE = "NOT_AVAILABLE"


class NotMatured(RuntimeError):
    """An outcome was requested before it was causally available."""


@dataclass(frozen=True)
class Observation:
    item_id: str
    horizon: str
    source: str
    available_at: Optional[datetime]
    status: str
    outcome_version: str
    anchor_ts: Optional[datetime]
    reference_price: Optional[float]
    fields: dict
    note: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("available_at", "anchor_ts"):
            d[k] = None if d[k] is None else d[k].isoformat()
        return d


def _dt(s) -> Optional[datetime]:
    if s is None or isinstance(s, datetime):
        return s
    return datetime.fromisoformat(s)


class OutcomeLedger:
    def __init__(self, bundle: ReplayBundle, cfg: BetaConfig):
        self.bundle, self.cfg = bundle, cfg
        self.horizons: tuple = tuple(cfg.horizons)
        self.anomalies: list = []

    # ---- maturity -------------------------------------------------------------------------
    def audit_at(self, item) -> datetime:
        """The earliest instant every configured horizon of this item can be mature."""
        longest = max(HORIZON_MINUTES[h] for h in self.horizons)
        return item.at + timedelta(minutes=longest) + LAST_BAR_GRACE

    def matured_by_export(self, item) -> bool:
        return self.bundle.exported_at is None or self.audit_at(item) <= self.bundle.exported_at

    def require_matured(self, item, clock: datetime) -> None:
        if clock < self.audit_at(item):
            raise NotMatured(f"{item.item_id}: outcomes mature at {self.audit_at(item).isoformat()}, "
                             f"clock is {clock.isoformat()}")
        if not self.matured_by_export(item):
            raise NotMatured(f"{item.item_id}: horizon ends after the bundle export time")

    # ---- observations as-of a clock ---------------------------------------------------------
    def available(self, item, clock: datetime, *, payload: Optional[dict] = None) -> list:
        if item.kind == KIND_PUSH:
            return self._episode(item, clock)
        if item.kind == KIND_BTC_VIEW:
            return self._view(item, clock, payload or {})
        return []

    def _episode(self, item, clock: datetime) -> list:
        pk = item.source["episode_pk"]
        ep = self.bundle.episode(pk) or {}
        out = []
        for h in self.horizons:
            rows = [o for o in self.bundle.outcomes
                    if o["episode_pk"] == pk and o["horizon"] == h
                    and o.get("outcome_version") == self.cfg.outcome_version]
            due = None if ep.get("triggered_at") is None else (
                ep["triggered_at"] + timedelta(minutes=HORIZON_MINUTES[h]) + LAST_BAR_GRACE)
            early = [o for o in rows if due is not None and o["computed_at"] < due]
            if early:
                self.anomalies.append({"item_id": item.item_id, "horizon": h,
                                       "anomaly": "OUTCOME_COMPUTED_BEFORE_MATURITY"})
            known = [o for o in rows if o["computed_at"] <= clock and o not in early]
            if not known:
                out.append(Observation(item.item_id, h, SOURCE_PERSISTED, None, NOT_AVAILABLE,
                                       self.cfg.outcome_version, ep.get("triggered_at"),
                                       ep.get("reference_price"), {f: None for f in OUTCOME_FIELDS},
                                       "no outcome row written by this time"))
                continue
            o = max(known, key=lambda r: r["revision"])
            out.append(Observation(item.item_id, h, SOURCE_PERSISTED, o["computed_at"], o["status"],
                                   self.cfg.outcome_version, o.get("anchor_ts") or ep.get("triggered_at"),
                                   o.get("reference_price", ep.get("reference_price")),
                                   {f: o.get(f) for f in OUTCOME_FIELDS},
                                   f"revision {o['revision']}"))
        return out

    def _view(self, item, clock: datetime, payload: dict) -> list:
        anchor = _dt(payload.get("data_through"))
        ref = (payload.get("now") or {}).get("reference_price")
        venues = list(self.cfg.exchanges)
        out = []
        for h in self.horizons:
            if anchor is None or ref is None:
                out.append(Observation(item.item_id, h, SOURCE_RECOMPUTED, None, NOT_AVAILABLE,
                                       self.cfg.outcome_version, anchor, ref, {f: None for f in OUTCOME_FIELDS},
                                       "view has no data time or reference price"))
                continue
            due = anchor + timedelta(minutes=HORIZON_MINUTES[h]) + LAST_BAR_GRACE
            if clock < due or (self.bundle.exported_at is not None and due > self.bundle.exported_at):
                out.append(Observation(item.item_id, h, SOURCE_RECOMPUTED, None, NOT_AVAILABLE,
                                       self.cfg.outcome_version, anchor, ref, {f: None for f in OUTCOME_FIELDS},
                                       "horizon not mature"))
                continue
            _start, end = anchor, anchor + timedelta(minutes=HORIZON_MINUTES[h])
            bars = [k for k in self.bundle.klines if anchor <= k["ts"] < end]
            o = compute_outcome(anchor=anchor, horizon=h, reference_price=ref, exchanges=venues, klines=bars)
            out.append(Observation(item.item_id, h, SOURCE_RECOMPUTED, due, o["status"], self.cfg.outcome_version,
                                   anchor, ref, {f: o.get(f) for f in OUTCOME_FIELDS},
                                   "configured venues; the view's reference composite membership is not persisted"))
        return out


def observations_as_dicts(obs: Sequence[Observation]) -> list:
    return [o.as_dict() for o in obs]
