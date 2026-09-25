"""Beta V0.2 forward outcome tracker — factual, symmetric, never directional.

For every TRIGGERED episode (pushed or suppressed) and each configured horizon,
from the trigger decision boundary (bucket close) and the recorded composite
reference price. Composite 1m path = per-minute median of the reference
venues' high / low / close; every minute must have every reference venue
(complete bars) — otherwise nothing is written until the window completes, or an
explicit INCOMPLETE_DATA row after `incomplete_after_h`. No MFE/MAE naming, no
WIN/LOSS, no hidden trade direction, no win rate. Corrections APPEND a new
revision that supersedes the previous one (history is never overwritten).
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

from .config import BetaConfig, BetaSwitches, HORIZON_MINUTES
from .models import (OUTCOME_COMPLETE, OUTCOME_INCOMPLETE_DATA, OUTCOME_REFERENCE_UNAVAILABLE)
from .state_tape import sha256_json

LAST_BAR_GRACE = timedelta(minutes=2)
OUTCOME_FIELDS = ("max_up_pct", "max_down_pct", "close_return_pct", "realized_range_pct",
                  "time_to_max_up_s", "time_to_max_down_s")


def horizon_window(anchor: datetime, horizon: str) -> tuple:
    return anchor, anchor + timedelta(minutes=HORIZON_MINUTES[horizon])


def compute_outcome(*, anchor: datetime, horizon: str, reference_price: Optional[float],
                    exchanges: Sequence[str], klines: Sequence[Mapping[str, Any]]) -> dict:
    """Pure. Returns a dict with status + factual fields (None where n/a)."""
    start, end = horizon_window(anchor, horizon)
    expected = HORIZON_MINUTES[horizon]
    base = {"anchor_ts": start, "window_end": end, "bars_expected": expected,
            "reference_price": reference_price, "source_exchanges": sorted(exchanges),
            **{f: None for f in OUTCOME_FIELDS}}
    if reference_price is None or not exchanges:
        return {**base, "status": OUTCOME_REFERENCE_UNAVAILABLE, "bars_complete": 0}
    wanted = set(exchanges)
    by_minute: dict = {}
    for k in klines:
        if k["exchange"] in wanted and start <= k["ts"] < end:
            by_minute.setdefault(k["ts"], {})[k["exchange"]] = k
    minutes = [start + timedelta(minutes=i) for i in range(expected)]
    complete = [m for m in minutes if set(by_minute.get(m, {})) == wanted]
    if len(complete) != expected:
        return {**base, "status": OUTCOME_INCOMPLETE_DATA, "bars_complete": len(complete)}
    ref = float(reference_price)
    path = []
    for m in minutes:
        bars = by_minute[m].values()
        path.append((m, statistics.median(float(b["high"]) for b in bars),
                     statistics.median(float(b["low"]) for b in bars),
                     statistics.median(float(b["close"]) for b in bars)))
    hi = max(p[1] for p in path)
    lo = min(p[2] for p in path)
    t_hi = next(p[0] for p in path if p[1] == hi)
    t_lo = next(p[0] for p in path if p[2] == lo)
    return {**base, "status": OUTCOME_COMPLETE, "bars_complete": expected,
            "max_up_pct": (hi / ref - 1.0) * 100.0,
            "max_down_pct": (1.0 - lo / ref) * 100.0,
            "close_return_pct": (path[-1][3] / ref - 1.0) * 100.0,
            "realized_range_pct": (hi - lo) / ref * 100.0,
            "time_to_max_up_s": int((t_hi + timedelta(minutes=1) - start).total_seconds()),
            "time_to_max_down_s": int((t_lo + timedelta(minutes=1) - start).total_seconds())}


def outcome_digest(o: Mapping[str, Any]) -> str:
    return sha256_json({k: o.get(k) for k in ("status", "bars_complete", "bars_expected",
                                              "reference_price", *OUTCOME_FIELDS)}
                       | {"source_exchanges": list(o.get("source_exchanges") or ())})


async def run_outcomes_once(store, cfg: BetaConfig, switches: BetaSwitches, *, clock,
                            raw_revision) -> dict:
    if not switches.outcome_tracking:
        return {"status": "DISABLED", "switches": switches.as_dict()}
    from storage.beta_v0_store import OUTCOMES_LOCK_KEY
    oc = cfg.section("outcomes")
    now = clock()
    written, not_due, pending_incomplete, superseded = [], 0, 0, []
    async with store.advisory_lock(OUTCOMES_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "LOCKED"}
        async with store.connect() as conn:
            cands = await conn.fetch_outcome_candidates(
                symbol=cfg.symbol, outcome_version=cfg.outcome_version, horizons=cfg.horizons,
                limit=oc["max_jobs_per_run"])
            rev = await raw_revision()
            for c in cands:
                anchor = c["triggered_at"]
                _s, end = horizon_window(anchor, c["horizon"])
                if now < end + LAST_BAR_GRACE:
                    not_due += 1            # never computed early
                    continue
                exchanges = list(c["reference_exchanges"] or ())
                klines = await conn.fetch_klines(exchanges=exchanges or list(cfg.exchanges),
                                                 symbol=cfg.symbol, start=anchor, end=end)
                o = compute_outcome(anchor=anchor, horizon=c["horizon"],
                                    reference_price=c["reference_price"], exchanges=exchanges,
                                    klines=klines)
                if o["status"] == OUTCOME_INCOMPLETE_DATA and \
                        now < end + timedelta(hours=oc["incomplete_after_h"]):
                    pending_incomplete += 1     # remains discoverable for completion
                    continue
                row = {**o, "episode_pk": c["episode_pk"], "horizon": c["horizon"],
                       "outcome_version": cfg.outcome_version, "revision": 1,
                       "supersedes_outcome_id": None, "source_raw_revision": rev,
                       "outcome_digest": outcome_digest(o), "computed_at": now}
                await conn.insert_outcome(row)
                written.append((c["public_id"], c["horizon"], o["status"]))
            # Correction re-check: recompute recent COMPLETE outcomes; append a
            # superseding revision if the underlying bars changed.
            for r in await conn.fetch_recheck_candidates(
                    outcome_version=cfg.outcome_version,
                    since=now - timedelta(hours=oc["recheck_window_h"]),
                    limit=oc["max_jobs_per_run"]):
                anchor = r["triggered_at"]
                _s, end = horizon_window(anchor, r["horizon"])
                exchanges = list(r["reference_exchanges"] or ())
                klines = await conn.fetch_klines(exchanges=exchanges, symbol=cfg.symbol,
                                                 start=anchor, end=end)
                o = compute_outcome(anchor=anchor, horizon=r["horizon"],
                                    reference_price=r["reference_price"], exchanges=exchanges,
                                    klines=klines)
                d = outcome_digest(o)
                if d == r["outcome_digest"] or o["status"] != OUTCOME_COMPLETE:
                    continue
                await conn.insert_outcome({
                    **o, "episode_pk": r["episode_pk"], "horizon": r["horizon"],
                    "outcome_version": cfg.outcome_version, "revision": r["revision"] + 1,
                    "supersedes_outcome_id": r["outcome_id"], "source_raw_revision": rev,
                    "outcome_digest": d, "computed_at": now,
                    "correction_note": f"source bars changed; supersedes revision {r['revision']}"})
                superseded.append((r["public_id"], r["horizon"], r["revision"] + 1))
            await conn.record_health("outcomes", now=clock(), success=True,
                                     detail={"written": len(written), "superseded": len(superseded)})
    return {"status": "OK", "written": written, "not_due": not_due,
            "pending_incomplete": pending_incomplete, "superseded": superseded}
