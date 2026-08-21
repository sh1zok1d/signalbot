"""Tests for the bounded automatic shadow recovery + outcome maturation.

Pure planning / hydration / dueness are tested directly. Orchestration is tested
with a fake Database: watermark/status tests monkeypatch the cycle primitive to a
spy; the integration tests use the REAL process_shadow_cycle /
process_forecast_outcome_horizon over fabricated raw bundles + kline windows. No
real DB / Docker / network.
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from common.config import Config
from common.stage2_config import Stage2Config
from storage.stage2_readers import ExchangeFeatureRawBundle
from storage.stage2_serialization import to_jsonable

import runtime.shadow_recovery as sr
from runtime.shadow_recovery import (
    LOCK_ACQUIRED, LOCK_HELD_SKIPPED, LockedOnceReport, PredictionPlan,
    ShadowRecoveryError, derive_evaluation_exchange, due_horizons,
    execute_shadow_once_locked, execute_shadow_recovery,
    hydrate_consensus_snapshot, hydrate_forecast_prediction, plan_prediction_buckets,
    render_locked_once_report, render_locked_once_report_json,
    shadow_recovery_lock_key, validate_operational_cap,
)
from runtime.shadow_cli import execute_shadow_dry_run, execute_shadow_status
from analytics.forecasting.core import compute_forecast_decision
from analytics.forecasting.persistence import build_forecast_prediction
from analytics.forecasting.shadow_cycle import (
    PREDICTION_DUPLICATE, PREDICTION_INSERTED, PREDICTION_SKIPPED_NO_CONSENSUS,
    PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
SYM, MT = "BTCUSDT", "perp"
EXS = ("binance", "bybit", "okx")
COV = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
STEP = timedelta(minutes=5)


def _run(coro):
    return asyncio.run(coro)


def _cfgs():
    return Config.load(), Stage2Config.load()


# ---- consensus factory (LONG) ----------------------------------------------
def _cv(**over):
    from analytics.feature_engine.consensus_models import ConsensusFeatureVector
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version="0123456789abcdef",
        coverage_by_metric=MappingProxyType({}), provenance_by_metric=MappingProxyType({}),
        data_confidence_by_metric=MappingProxyType({}), exchanges_expected_max=3,
        min_coverage_ratio=1.0, data_confidence_overall=80.0,
        price_direction_agreement=1.0, flow_direction_agreement=1.0, oi_direction_agreement=1.0,
        price_move_pct_median=0.4, range_width_pct_median=1.0, oi_change_pct_median=0.5,
        funding_rate_median=0.0001, funding_rate_mad=0.0, volume_notional_usd_sum=1000.0,
        taker_buy_notional_usd_sum=800.0, taker_sell_notional_usd_sum=200.0,
        taker_delta_notional_usd_sum=600.0, cvd_delta_notional_usd_sum=600.0,
        observed_long_liquidation_notional_sum=100.0, observed_short_liquidation_notional_sum=900.0,
        observed_liquidation_event_count_sum=5, liquidation_feed_quality_by_exchange=MappingProxyType({}),
        price_move_pct_mad=0.0, oi_change_pct_mad=0.0, outlier_exchanges=MappingProxyType({}),
        consensus_confidence=80.0, is_partial_consensus=False, config_hash="a" * 64,
        config_version="2.1.0", code_version="code-v1")
    base.update(over)
    return ConsensusFeatureVector(**base)


def _prediction(bucket_ts=B, source="binance_close_5m"):
    cv = _cv(bucket_ts=bucket_ts)
    return build_forecast_prediction(compute_forecast_decision(cv), cv,
                                     reference_price=105.0, reference_price_source=source)


def _prediction_row(pred):
    snap = json.loads(json.dumps(to_jsonable(pred.consensus_snapshot)))
    return MappingProxyType({
        "symbol": pred.symbol, "market_type": pred.market_type, "timeframe": pred.timeframe,
        "bucket_ts": pred.bucket_ts, "feature_schema_version": pred.feature_schema_version,
        "calculation_version": pred.calculation_version, "rule_version": pred.rule_version,
        "direction": pred.direction, "confidence": pred.confidence,
        "horizon_set": list(pred.horizon_set), "reasons": list(pred.reasons),
        "component_scores": dict(pred.component_scores), "final_score": pred.final_score,
        "reference_price": pred.reference_price, "reference_price_source": pred.reference_price_source,
        "exchanges_expected_max": pred.exchanges_expected_max, "min_coverage_ratio": pred.min_coverage_ratio,
        "data_confidence_overall": pred.data_confidence_overall, "consensus_confidence": pred.consensus_confidence,
        "is_partial_consensus": pred.is_partial_consensus, "consensus_snapshot": snap,
        "config_hash": pred.config_hash, "config_version": pred.config_version, "code_version": pred.code_version})


# ---- raw bundle fixtures ----------------------------------------------------
def _m(**kw):
    return MappingProxyType(dict(kw))


def _bundle(ex, bucket_ts):
    def k(minute):
        o = 100.0 + minute
        return _m(exchange=ex, symbol=SYM, ts=bucket_ts + timedelta(minutes=minute), open=o,
                  high=110.0 + minute, low=95.0 + minute, close=101.0 + minute,
                  volume=10.0 + minute, taker_buy_volume=1.0 + minute, taker_sell_volume=0.5 + minute)
    return ExchangeFeatureRawBundle(
        klines=tuple(k(i) for i in range(5)),
        open_interest=(_m(exchange=ex, symbol=SYM, ts=bucket_ts, oi_raw=100.0, oi_unit="base"),
                       _m(exchange=ex, symbol=SYM, ts=bucket_ts + timedelta(minutes=4), oi_raw=110.0, oi_unit="base")),
        latest_funding=_m(exchange=ex, symbol=SYM, ts=bucket_ts - timedelta(minutes=1), funding_rate=0.0001),
        liquidations=(_m(id=1, exchange=ex, symbol=SYM, ts=bucket_ts + timedelta(minutes=1), side="long",
                         notional=100.0, is_snapshot_feed=(COV[ex] == "snapshot")),),
        instrument=_m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
                      quantity_unit="base", contract_multiplier=None, tick_size=0.1, price_precision=None,
                      quantity_precision=None, metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None),
        liquidation_capability=_m(exchange=ex, symbol=SYM, market_type=MT, metric="liquidations",
                                  live_supported=True, historical_supported=False, coverage_type=COV[ex],
                                  expected_freshness_s=None, enabled=True))


def _inst_row(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
              quantity_unit="base", contract_multiplier=None, tick_size=0.1, price_precision=None,
              quantity_precision=None, metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)


async def _fetch_json(url, params):   # fresh instruments -> never called
    raise AssertionError("no metadata network expected")


# ---- fake Database ----------------------------------------------------------
class RecoveryDB:
    def __init__(self, *, lock_free=True, watermark=None, newest_pred=None,
                 candidates=(), missing=(), outcome_klines=None):
        self.lock_free = lock_free
        self.watermark = watermark
        self.newest_pred = newest_pred
        self.candidates = tuple(candidates)
        self.missing = tuple(missing)
        self.outcome_klines = tuple(outcome_klines) if outcome_klines is not None else ()
        self.calls: list = []
        self.advanced: list = []
        self.instruments = {ex: _inst_row(ex) for ex in EXS}
        self.outcome_upserts: list = []
        self.predictions: list = []

    @contextlib.asynccontextmanager
    async def shadow_recovery_lock(self, key):
        self.calls.append(("lock", key))
        try:
            yield self.lock_free
        finally:
            self.calls.append(("unlock", key))

    async def init_stage2_schema(self):
        self.calls.append("init_stage2_schema")

    async def bootstrap_instrument_metadata_revision(self, *, initial_revision):
        self.calls.append(("bootstrap_revision", initial_revision))
        return "SEEDED"

    async def bootstrap_stage2_raw_revision(self, *, symbol, market_type):
        self.calls.append(("bootstrap_raw_revision", symbol, market_type))
        return "SEEDED"

    async def seed_symbols(self, rows):
        self.calls.append("seed_symbols"); return len(rows)

    async def seed_symbol_exchange_capabilities(self, rows):
        self.calls.append("seed_caps"); return len(rows)

    async def get_exchange_instrument(self, exchange, symbol, market_type="perp"):
        return self.instruments.get(exchange)

    async def upsert_exchange_instrument(self, **kw):
        self.calls.append(("upsert_instr", kw["exchange"])); return "OK"

    async def fetch_shadow_watermark(self, **kw):
        self.calls.append("wm_read"); return self.watermark

    async def advance_shadow_watermark(self, *, bucket_ts, **kw):
        self.calls.append(("wm_advance", bucket_ts)); self.advanced.append(bucket_ts)

    async def fetch_newest_prediction_bucket(self, **kw):
        self.calls.append("newest_pred"); return self.newest_pred

    async def fetch_recovery_prediction_candidates(self, **kw):
        self.calls.append("candidates"); return self.candidates

    async def fetch_missing_outcome_identities(self, *, candidates, **kw):
        self.calls.append(("antijoin", len(candidates))); return self.missing

    async def fetch_shadow_liquidation_availability(self, *, exchanges, **kw):
        return MappingProxyType({ex: True for ex in exchanges})

    async def fetch_exchange_feature_raw_bundle(self, *, exchange, bucket_start, **kw):
        self.calls.append(("raw", exchange)); return _bundle(exchange, bucket_start)

    async def upsert_exchange_feature_vectors(self, rows):
        return len(rows)

    async def upsert_consensus_feature_vectors(self, rows):
        return len(rows)

    async def insert_forecast_prediction(self, row):
        self.calls.append("insert_pred"); self.predictions.append(row); return True

    async def upsert_forecast_outcomes(self, rows):
        self.calls.append("outcome_upsert"); self.outcome_upserts.append(tuple(rows)); return len(rows)

    async def fetch_forecast_outcome_klines(self, **kw):
        return self.outcome_klines


def _recover(db, *, now, max_catchup=12, max_outcomes=100):
    c1, c2 = _cfgs()
    return _run(execute_shadow_recovery(
        db, c1, c2, now=now, reference_exchange="binance", explicit_code_version="cli",
        metadata_fetch_json=_fetch_json, max_catchup_buckets=max_catchup,
        max_outcome_jobs=max_outcomes))


# ============================================================================
# 1. pure planning
# ============================================================================
def test_plan_fresh_processes_latest_only():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    plan = plan_prediction_buckets(watermark=None, newest_prediction_bucket=None,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288)
    assert plan.buckets == (lc,)


def test_plan_bootstrap_from_newest_prediction():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    plan = plan_prediction_buckets(watermark=None, newest_prediction_bucket=lc - 2 * STEP,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288)
    assert plan.buckets == (lc - STEP, lc)


def test_plan_catchup_oldest_first_no_duplicates():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    plan = plan_prediction_buckets(watermark=lc - 3 * STEP, newest_prediction_bucket=None,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288)
    assert plan.buckets == (lc - 2 * STEP, lc - STEP, lc)
    assert list(plan.buckets) == sorted(plan.buckets)
    assert len(set(plan.buckets)) == len(plan.buckets)


def test_plan_cap_keeps_oldest():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    plan = plan_prediction_buckets(watermark=lc - 20 * STEP, newest_prediction_bucket=None,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288)
    assert len(plan.buckets) == 12 and plan.truncated_by_cap
    assert plan.buckets[0] == lc - 19 * STEP           # oldest kept


def test_plan_lookback_truncation():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    plan = plan_prediction_buckets(watermark=lc - 500 * STEP, newest_prediction_bucket=None,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288)
    assert plan.truncated_by_lookback
    assert plan.buckets[0] == lc - 288 * STEP          # floored to lookback


def test_plan_already_caught_up():
    lc = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    assert plan_prediction_buckets(watermark=lc, newest_prediction_bucket=None,
                                   latest_closed=lc, max_buckets=12, lookback_buckets=288).buckets == ()


@pytest.mark.parametrize("bad", [
    datetime(2026, 7, 24, 12, 2, tzinfo=UTC),          # not 5m aligned
    datetime(2026, 7, 24, 12, 0),                       # naive
])
def test_plan_rejects_misaligned_latest(bad):
    with pytest.raises(ShadowRecoveryError):
        plan_prediction_buckets(watermark=None, newest_prediction_bucket=None,
                                latest_closed=bad, max_buckets=12, lookback_buckets=288)


@pytest.mark.parametrize("cap", [0, -1, True, 3.0, 10**9])
def test_operational_cap_validation(cap):
    with pytest.raises(ShadowRecoveryError):
        validate_operational_cap(cap, "x", 288)


# ============================================================================
# 2. lock key + lock-held
# ============================================================================
def test_lock_key_deterministic_and_int64():
    a = shadow_recovery_lock_key("shadow_forecast_v1", "BTCUSDT", "perp", "5m")
    b = shadow_recovery_lock_key("shadow_forecast_v1", "BTCUSDT", "perp", "5m")
    c = shadow_recovery_lock_key("shadow_forecast_v1", "ETHUSDT", "perp", "5m")
    assert a == b and a != c
    assert -(2 ** 63) <= a < 2 ** 63


def test_lock_held_does_zero_work():
    db = RecoveryDB(lock_free=False)
    rep = _recover(db, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    assert rep.lock_status == LOCK_HELD_SKIPPED and rep.writes_enabled is False
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    for forbidden in ("init_stage2_schema", "bootstrap_revision", "seed_symbols", "seed_caps",
                      "wm_advance", "insert_pred", "outcome_upsert"):
        assert forbidden not in verbs
    assert db.advanced == []


# ============================================================================
# 3. watermark (spy cycle so status is controllable)
# ============================================================================
def _spy_cycle(monkeypatch, status_by_bucket=None, raise_on=None, default=PREDICTION_INSERTED):
    seen = []

    async def spy(reader, writer, cfg, *, bucket_ts, **kw):
        seen.append(bucket_ts)
        if raise_on is not None and bucket_ts == raise_on:
            raise RuntimeError("cycle boom")
        status = (status_by_bucket or {}).get(bucket_ts, default)
        return SimpleNamespace(prediction_status=status)

    monkeypatch.setattr(sr, "process_shadow_cycle", spy)
    return seen


def test_watermark_initial_insert_on_fresh(monkeypatch):
    _spy_cycle(monkeypatch)
    db = RecoveryDB(watermark=None, newest_pred=None)
    rep = _recover(db, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    assert rep.prediction_buckets_attempted == 1 and len(db.advanced) == 1
    assert rep.watermark_after == db.advanced[0]


def test_watermark_monotonic_oldest_first(monkeypatch):
    now = datetime(2026, 3, 1, 0, 30, tzinfo=UTC)      # latest closed 00:25
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    _spy_cycle(monkeypatch)
    db = RecoveryDB(watermark=lc - 3 * STEP)
    _recover(db, now=now)
    assert db.advanced == sorted(db.advanced) == [lc - 2 * STEP, lc - STEP, lc]


@pytest.mark.parametrize("status", [
    PREDICTION_INSERTED, PREDICTION_DUPLICATE,
    PREDICTION_SKIPPED_NO_CONSENSUS, PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE])
def test_watermark_advances_for_all_four_statuses(monkeypatch, status):
    _spy_cycle(monkeypatch, default=status)
    db = RecoveryDB(watermark=None, newest_pred=None)
    rep = _recover(db, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    assert len(db.advanced) == 1                        # every completed attempt advances
    assert rep.per_bucket_status[0][1] == status


def test_watermark_not_advanced_on_exception(monkeypatch):
    now = datetime(2026, 3, 1, 0, 30, tzinfo=UTC)
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    boom_bucket = lc - STEP                              # second bucket raises
    _spy_cycle(monkeypatch, raise_on=boom_bucket)
    db = RecoveryDB(watermark=lc - 2 * STEP)            # plan: [lc-STEP, lc]
    with pytest.raises(RuntimeError, match="cycle boom"):
        _recover(db, now=now)
    assert db.advanced == []                            # never advanced past the failing bucket


def test_retry_after_advance_failure_leaves_watermark(monkeypatch):
    # writes succeeded but the watermark advance fails -> exception propagates,
    # watermark unchanged, so the next run reprocesses (idempotent insert makes it safe).
    _spy_cycle(monkeypatch)
    db = RecoveryDB(watermark=None, newest_pred=None)

    async def boom_advance(**kw):
        raise RuntimeError("advance boom")

    db.advance_shadow_watermark = boom_advance
    with pytest.raises(RuntimeError, match="advance boom"):
        _recover(db, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    assert db.advanced == []


# ============================================================================
# 4. hydration + discovery
# ============================================================================
def test_hydrate_valid_prediction_and_nested_consensus():
    pred = _prediction()
    rebuilt = hydrate_forecast_prediction(_prediction_row(pred))
    assert rebuilt.direction == pred.direction and rebuilt.bucket_ts == pred.bucket_ts
    assert rebuilt.consensus_snapshot.symbol == "BTCUSDT"


def test_hydrate_malformed_snapshot_fails_closed():
    pred = _prediction()
    row = dict(_prediction_row(pred))
    snap = dict(row["consensus_snapshot"]); del snap["coverage_by_metric"]
    row["consensus_snapshot"] = snap
    with pytest.raises(ShadowRecoveryError):
        hydrate_forecast_prediction(MappingProxyType(row))


def test_hydrate_identity_mismatch_fails_closed():
    pred = _prediction()
    row = dict(_prediction_row(pred))
    row["calculation_version"] = "ffffffffffffffff"    # != snapshot
    with pytest.raises(ShadowRecoveryError):
        hydrate_forecast_prediction(MappingProxyType(row))


@pytest.mark.parametrize("source", ["kraken_close_5m", "binance_close_1m", "garbage", ""])
def test_derive_evaluation_exchange_malformed(source):
    with pytest.raises(ShadowRecoveryError):
        derive_evaluation_exchange(source)


# ============================================================================
# 5. outcome dueness boundaries
# ============================================================================
@pytest.mark.parametrize("horizon,minutes", [("15m", 15), ("1h", 60), ("4h", 240)])
def test_horizon_due_exactly_at_boundary(horizon, minutes):
    pred = hydrate_forecast_prediction(_prediction_row(_prediction()))
    end = pred.bucket_ts + timedelta(minutes=5 + minutes)
    assert horizon in due_horizons(pred, end, 0)                    # due at end
    assert horizon not in due_horizons(pred, end - timedelta(minutes=1), 0)  # not before end


def test_due_horizons_mixed_and_ordered():
    pred = hydrate_forecast_prediction(_prediction_row(_prediction()))
    now = pred.bucket_ts + timedelta(minutes=5 + 60 + 1)           # 15m + 1h due, 4h not
    assert due_horizons(pred, now, 0) == ("15m", "1h")


# ============================================================================
# 6. runtime orchestration (real cycle + real outcome pipeline)
# ============================================================================
def test_automatic_single_bucket_real_cycle():
    now = datetime(2026, 3, 1, 0, 10, tzinfo=UTC)      # latest closed 00:00 (grace 5)
    db = RecoveryDB(watermark=None, newest_pred=None)
    rep = _recover(db, now=now)
    assert rep.lock_status == LOCK_ACQUIRED
    assert rep.prediction_buckets_attempted == 1
    assert rep._count(PREDICTION_INSERTED) == 1
    assert len(db.advanced) == 1
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert verbs.count("init_stage2_schema") == 1       # bootstrap once
    assert verbs.count("bootstrap_revision") == 1
    assert verbs.count("seed_symbols") == 1 and verbs.count("seed_caps") == 1
    # (Tech-lead review 4992495660, finding 10) revision bootstrap must
    # complete strictly BEFORE any instrument upsert or raw-bundle read, for
    # the AUTOMATIC recovery path too (not just the explicit one-bucket path).
    bootstrap_idx = verbs.index("bootstrap_revision")
    assert bootstrap_idx > verbs.index("init_stage2_schema")
    # (CodeRabbit finding 5C) assert the ACTUAL forwarded value, not merely
    # that SOME call named "bootstrap_revision" happened.
    _, expected_cfg = _cfgs()
    bootstrap_calls = [c for c in db.calls if isinstance(c, tuple) and c[0] == "bootstrap_revision"]
    assert bootstrap_calls == [("bootstrap_revision", expected_cfg.instrument_metadata_revision)]
    upsert_indices = [i for i, v in enumerate(verbs) if v == "upsert_instr"]
    raw_indices = [i for i, v in enumerate(verbs) if v == "raw"]
    assert all(bootstrap_idx < i for i in upsert_indices)
    assert all(bootstrap_idx < i for i in raw_indices)
    # (CodeRabbit review, tech-lead review round 3, finding 3) assert the
    # ACTUAL (symbol, market_type) scope forwarded to
    # bootstrap_stage2_raw_revision -- the V2-H2e raw-revision COUNTER seed
    # only, never a stage2_publication_state CLEAN bootstrap (that no
    # longer exists for the automatic recovery path either).
    raw_revision_calls = [c for c in db.calls if isinstance(c, tuple) and c[0] == "bootstrap_raw_revision"]
    assert raw_revision_calls == [("bootstrap_raw_revision", SYM, MT)]


def test_several_missed_buckets_recovered_oldest_first():
    now = datetime(2026, 3, 1, 0, 30, tzinfo=UTC)
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    db = RecoveryDB(watermark=lc - 3 * STEP)
    rep = _recover(db, now=now)
    assert rep.prediction_buckets_attempted == 3
    assert db.advanced == [lc - 2 * STEP, lc - STEP, lc]


def _outcome_setup(*, klines):
    pred = _prediction()
    now = pred.bucket_ts + timedelta(minutes=5 + 15 + 10)   # 15m due
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    missing = [MappingProxyType({
        "bucket_ts": pred.bucket_ts, "calculation_version": pred.calculation_version,
        "rule_version": pred.rule_version, "horizon": "15m",
        "evaluation_exchange": "binance", "outcome_version": sr.DEFAULT_OUTCOME_VERSION})]
    db = RecoveryDB(watermark=lc, candidates=[_prediction_row(pred)],
                    missing=missing, outcome_klines=klines)
    return db, now


def test_outcome_complete_persisted():
    pred = _prediction()
    start = pred.bucket_ts + timedelta(minutes=5)
    klines = tuple(MappingProxyType(dict(
        exchange="binance", symbol="BTCUSDT", ts=start + timedelta(minutes=i),
        open=100.0, high=101.0, low=99.0, close=100.0)) for i in range(15))
    db, now = _outcome_setup(klines=klines)
    rep = _recover(db, now=now)
    assert rep.outcome_jobs_attempted == 1 and rep.outcome_evaluations_complete == 1
    assert len(db.outcome_upserts) == 1                 # COMPLETE persisted


def test_outcome_incomplete_not_persisted():
    db, now = _outcome_setup(klines=())                 # empty window -> INCOMPLETE
    rep = _recover(db, now=now)
    assert rep.outcome_jobs_attempted == 1 and rep.outcome_evaluations_incomplete == 1
    assert db.outcome_upserts == []                     # INCOMPLETE never persisted


def test_outcome_existing_excluded_by_antijoin():
    # anti-join returns NO missing -> zero jobs even though a horizon is due
    pred = _prediction()
    now = pred.bucket_ts + timedelta(minutes=5 + 240 + 10)
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    db = RecoveryDB(watermark=lc, candidates=[_prediction_row(pred)], missing=())
    rep = _recover(db, now=now)
    assert rep.outcome_jobs_discovered == 0 and rep.outcome_jobs_attempted == 0


def test_exception_in_cycle_fails_closed(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("real boom")

    monkeypatch.setattr(sr, "process_shadow_cycle", boom)
    db = RecoveryDB(watermark=None, newest_pred=None)
    with pytest.raises(RuntimeError, match="real boom"):
        _recover(db, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    assert db.advanced == []


def test_max_outcome_jobs_cap(monkeypatch):
    # three due+missing candidates but cap=1 -> only 1 attempted, others left
    preds = [_prediction(bucket_ts=B + i * STEP) for i in range(3)]
    now = B + timedelta(minutes=5 + 240 + 10)
    lc = sr.select_latest_closed_5m_bucket(now, soft_grace_s=5)
    missing = [MappingProxyType({
        "bucket_ts": p.bucket_ts, "calculation_version": p.calculation_version,
        "rule_version": p.rule_version, "horizon": "15m",
        "evaluation_exchange": "binance", "outcome_version": sr.DEFAULT_OUTCOME_VERSION})
        for p in preds]
    # klines make each 15m COMPLETE
    def klines_for(p):
        s = p.bucket_ts + timedelta(minutes=5)
        return [dict(exchange="binance", symbol="BTCUSDT", ts=s + timedelta(minutes=i),
                     open=100.0, high=101.0, low=99.0, close=100.0) for i in range(15)]

    db = RecoveryDB(watermark=lc, candidates=[_prediction_row(p) for p in preds], missing=missing)
    # only the first prediction's 15m is due (others have later buckets not yet matured)
    db.outcome_klines = tuple(MappingProxyType(r) for r in klines_for(preds[0]))
    rep = _recover(db, now=now, max_outcomes=1)
    assert rep.outcome_jobs_attempted == 1              # capped


def test_report_json_has_no_secrets_or_snapshot():
    now = datetime(2026, 3, 1, 0, 10, tzinfo=UTC)
    db = RecoveryDB(watermark=None, newest_pred=None)
    rep = _recover(db, now=now)
    js = sr.render_shadow_recovery_report_json(rep)
    low = js.lower()
    for banned in ("postgres", "dsn", "redis", "consensus_snapshot", "password", "coverage_by_metric"):
        assert banned not in low
    assert json.loads(js)["stage2_global_enabled"] is False      # stays false


# ============================================================================
# 7. architecture
# ============================================================================
_SRC = Path("runtime/shadow_recovery.py")


def test_recovery_module_has_no_while_gather_sleep():
    tree = ast.parse(_SRC.read_text())
    for node in ast.walk(tree):
        assert not isinstance(node, ast.While)
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"gather", "create_task", "ensure_future", "sleep"}


def test_recovery_module_has_no_raw_sql():
    src = _SRC.read_text()
    for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "FROM"):
        assert not __import__("re").search(rf"\b{kw}\b", src), kw


# ============================================================================
# 8. explicit --shadow-bucket-ts run shares the SAME advisory lock as automatic
#    recovery (locking hardening amendment)
# ============================================================================
class StatusCapableDB(RecoveryDB):
    """RecoveryDB + fetch_shadow_status, for exercising execute_shadow_status /
    execute_shadow_dry_run (neither of which should ever touch the recovery lock)."""

    async def fetch_shadow_status(self, **kw):
        self.calls.append("status")
        return MappingProxyType({
            "state": "EMPTY",
            "instrument_metadata_revision": 1,
            "prerequisites": tuple(MappingProxyType({
                "exchange": ex, "instrument_present": True, "instrument_is_stale": False,
                "liquidation_capability_present": True, "liquidation_live_supported": True,
                "liquidation_enabled": True, "liquidation_coverage_type": COV[ex]})
                for ex in EXS),
            "latest_prediction": None, "outcomes": ()})


def _locked_once(db, *, bucket_ts="2026-03-01T00:00:00Z", now=None):
    c1, c2 = _cfgs()
    now = now or datetime(2026, 3, 1, 0, 10, tzinfo=UTC)
    return _run(execute_shadow_once_locked(
        db, c1, c2, now=now, explicit_bucket_ts=bucket_ts,
        reference_exchange="binance", explicit_code_version="cli",
        metadata_fetch_json=_fetch_json))


def test_explicit_and_automatic_derive_same_lock_key():
    db_auto = RecoveryDB(watermark=None, newest_pred=None)
    _recover(db_auto, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC))
    auto_key = next(v for (tag, v) in db_auto.calls if tag == "lock")

    db_explicit = RecoveryDB(watermark=None)
    _locked_once(db_explicit)
    explicit_key = next(v for (tag, v) in db_explicit.calls if tag == "lock")

    assert auto_key == explicit_key                 # one lock namespace, same identity
    assert auto_key == shadow_recovery_lock_key("shadow_forecast_v1", "BTCUSDT", "perp", "5m")


def test_explicit_run_acquires_and_releases_lock():
    db = RecoveryDB(watermark=None)
    rep = _locked_once(db)
    assert rep.lock_status == LOCK_ACQUIRED
    tags = [c[0] for c in db.calls if isinstance(c, tuple)]
    assert tags.count("lock") == 1 and tags.count("unlock") == 1
    assert tags.index("lock") < tags.index("unlock")


def test_explicit_run_releases_lock_after_exception(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("explicit boom")

    monkeypatch.setattr(sr, "execute_shadow_once", boom)
    db = RecoveryDB(watermark=None)
    with pytest.raises(RuntimeError, match="explicit boom"):
        _locked_once(db)
    tags = [c[0] for c in db.calls if isinstance(c, tuple)]
    assert "lock" in tags and "unlock" in tags       # released even after the exception


def test_explicit_run_with_held_lock_zero_work():
    db = RecoveryDB(lock_free=False, watermark=None)
    rep = _locked_once(db)
    assert rep.lock_status == LOCK_HELD_SKIPPED and rep.execution is None
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    for forbidden in ("init_stage2_schema", "bootstrap_revision", "seed_symbols", "seed_caps",
                      "upsert_instr", "insert_pred", "outcome_upsert", "wm_read", "wm_advance",
                      "candidates", "antijoin", "raw"):
        assert forbidden not in verbs
    assert verbs == ["lock", "unlock"]               # nothing else ran at all


def test_explicit_run_with_acquired_lock_processes_one_bucket():
    db = RecoveryDB(watermark=None)                 # fresh consensus -> real insert
    rep = _locked_once(db)
    assert rep.lock_status == LOCK_ACQUIRED
    assert rep.execution.result.prediction_status == PREDICTION_INSERTED
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert verbs.count("insert_pred") == 1
    assert verbs.count("raw") == 3                   # one bucket, one read per exchange


def test_explicit_run_never_reads_or_advances_watermark():
    db = RecoveryDB(watermark=B - timedelta(minutes=15))  # would imply catch-up if it were read
    _locked_once(db, bucket_ts="2026-03-01T00:00:00Z")
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert "wm_read" not in verbs and "wm_advance" not in verbs
    assert db.advanced == []


def test_explicit_run_no_catchup_no_outcome_discovery():
    db = RecoveryDB(watermark=None)
    _locked_once(db)
    verbs = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert "candidates" not in verbs and "antijoin" not in verbs
    assert verbs.count("raw") == 3                   # exactly the one selected bucket


def test_status_and_dry_run_do_not_acquire_recovery_lock():
    c1, c2 = _cfgs()
    db_status = StatusCapableDB(watermark=None)
    _run(execute_shadow_status(db_status, c1, c2))
    assert not any(isinstance(c, tuple) and c[0] == "lock" for c in db_status.calls)

    db_dry = StatusCapableDB(watermark=None)
    report = _run(execute_shadow_dry_run(
        db_dry, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        explicit_bucket_ts=None, reference_exchange="binance",
        explicit_code_version="cli", metadata_fetch_json=_fetch_json))
    assert report.writes_enabled is False
    assert not any(isinstance(c, tuple) and c[0] == "lock" for c in db_dry.calls)


def test_locked_once_report_json_and_human_have_lock_status():
    db = RecoveryDB(watermark=None)
    rep = _locked_once(db)
    js = json.loads(render_locked_once_report_json(rep))
    assert js["lock_status"] == LOCK_ACQUIRED
    assert "lock_status" in js and "lock:" in render_locked_once_report(rep)

    held = RecoveryDB(lock_free=False, watermark=None)
    rep2 = _locked_once(held)
    js2 = json.loads(render_locked_once_report_json(rep2))
    assert js2["lock_status"] == LOCK_HELD_SKIPPED and js2["writes_enabled"] is False


def test_locked_once_report_invariants():
    with pytest.raises(ShadowRecoveryError):
        LockedOnceReport(lock_status="BOGUS", execution=None, bucket_ts=B,
                         reference_exchange="binance", code_version="c",
                         stage2_global_enabled=False)
    with pytest.raises(ShadowRecoveryError):
        LockedOnceReport(lock_status=LOCK_ACQUIRED, execution=None, bucket_ts=B,
                         reference_exchange="binance", code_version="c",
                         stage2_global_enabled=False)
    with pytest.raises(ShadowRecoveryError):
        LockedOnceReport(lock_status=LOCK_HELD_SKIPPED, execution=object(), bucket_ts=B,
                         reference_exchange="binance", code_version="c",
                         stage2_global_enabled=False)
