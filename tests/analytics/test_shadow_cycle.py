from __future__ import annotations

import ast
import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.feature_engine.bucket_coordinator import Stage2BucketResult
from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.forecasting.core import compute_forecast_decision
from analytics.forecasting.models import NEUTRAL
from analytics.forecasting.outcomes import DEFAULT_OUTCOME_VERSION, EVALUATION_PRICE_SOURCE, OUTCOME_COMPLETE, OUTCOME_INCOMPLETE, ForecastOutcomeEvaluation, OutcomePriceBar, build_forecast_outcome_window
from analytics.forecasting.persistence import build_forecast_prediction
from storage.stage2_readers import ExchangeFeatureRawBundle
from analytics.forecasting.shadow_cycle import (
    DueOutcomeJob, PREDICTION_DUPLICATE, PREDICTION_INSERTED,
    PREDICTION_SKIPPED_NO_CONSENSUS, PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE,
    ShadowCycleError, ShadowCycleResult, process_shadow_cycle,
)
from common.stage2_config import Stage2Config

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
CFG = Stage2Config({})
_UNSET = object()
SYM, MT = "BTCUSDT", "perp"
EXS = ("binance", "bybit", "okx")
COV = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _cv(**over):
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


def _efv(exchange="binance", **over):
    base = dict(
        exchange=exchange, symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version="0123456789abcdef",
        price_move_pct=0.4, range_width_pct=1.0, close_price=105.0,
        volume_raw=1.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=800.0, taker_sell_notional_usd=200.0,
        taker_delta_notional_usd=600.0, cvd_delta_notional_usd=600.0,
        oi_change_pct=0.5, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=100.0, short_liquidation_notional=900.0,
        liquidation_event_count=5, liquidation_feed_quality="full", is_snapshot_feed=False,
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash="a" * 64, config_version="2.1.0", code_version="code-v1")
    base.update(over)
    return ExchangeFeatureVector(**base)


def _bucket(*, consensus=_UNSET, features=None, failures=()):
    if consensus is _UNSET:
        consensus = _cv()
    return Stage2BucketResult(
        exchange_features=features if features is not None else [_efv("binance"), _efv("bybit"), _efv("okx")],
        consensus_feature=consensus, failures=failures,
        expected_exchanges_by_family={"price_structure": ("binance", "bybit", "okx")},
        exclusion_reasons_by_family={"price_structure": {}},
    )


def _prediction(**cv_over):
    cv = _cv(**cv_over)
    return build_forecast_prediction(compute_forecast_decision(cv), cv, reference_price=105.0, reference_price_source="binance_close_5m")


def _eval(status=OUTCOME_INCOMPLETE, horizon="15m", bars_present=0):
    prediction = _prediction()
    w = build_forecast_outcome_window(
        prediction, horizon=horizon, evaluation_exchange="binance"
    )
    if status == OUTCOME_COMPLETE:
        rows = [
            OutcomePriceBar(
                "binance", "BTCUSDT", w.evaluation_start_ts + timedelta(minutes=i),
                100.0, 101.0, 99.0, 100.0,
            )
            for i in range(w.bars_expected)
        ]
        from analytics.forecasting.outcomes import evaluate_forecast_outcome
        return evaluate_forecast_outcome(prediction, w, price_bars=rows)
    missing = tuple(
        w.evaluation_start_ts + timedelta(minutes=i)
        for i in range(bars_present, w.bars_expected)
    )
    return ForecastOutcomeEvaluation(
        horizon=horizon, outcome_version=DEFAULT_OUTCOME_VERSION,
        evaluation_exchange="binance", evaluation_price_source=EVALUATION_PRICE_SOURCE,
        evaluation_start_ts=w.evaluation_start_ts, evaluation_end_ts=w.evaluation_end_ts,
        status=status, bars_expected=w.bars_expected, bars_present=bars_present,
        missing_bar_ts=missing, outcome=None,
    )


def _m(**kw):
    return MappingProxyType(dict(kw))


def _kline(ex, minute, *, close=None):
    close = 101.0 + minute if close is None else close
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              open=100.0 + minute, high=110.0 + minute, low=95.0 + minute,
              close=close, volume=10.0 + minute,
              taker_buy_volume=1.0 + minute, taker_sell_volume=0.5 + minute)


def _oi(ex, minute, value):
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              oi_raw=value, oi_unit="base")


def _fund(ex):
    return _m(exchange=ex, symbol=SYM, ts=B - timedelta(minutes=1), funding_rate=0.0001)


def _liq(ex, id_, minute, side="long"):
    return _m(id=id_, exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              side=side, notional=100.0, is_snapshot_feed=(COV[ex] == "snapshot"))


def _inst(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
              quantity_unit="base", contract_multiplier=None, tick_size=0.1,
              price_precision=None, quantity_precision=None,
              metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)


def _cap(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, metric="liquidations",
              live_supported=True, historical_supported=False, coverage_type=COV[ex],
              expected_freshness_s=None, enabled=True)


def _bundle(ex, *, n_klines=5, final_close=None):
    return ExchangeFeatureRawBundle(
        klines=tuple(_kline(ex, i, close=final_close if i == 4 else None)
                     for i in range(n_klines)),
        open_interest=(_oi(ex, 0, 100.0), _oi(ex, 4, 110.0)),
        latest_funding=_fund(ex),
        liquidations=(_liq(ex, 1, 1), _liq(ex, 2, 2, "short")),
        instrument=_inst(ex),
        liquidation_capability=_cap(ex),
    )


class FakeRW:
    def __init__(self, *, inserted=True, rows=(), bundles=None, fail_raw=(), block_first_read=None):
        self.calls = []
        self.inserted = inserted
        self.rows = list(rows)
        self.bundles = bundles or {}
        self.fail_raw = set(fail_raw)
        self.block_first_read = block_first_read
        self.inserted_rows = []
        self.exchange_upserts = []
        self.consensus_upserts = []
        self.outcome_upserts = []

    async def insert_forecast_prediction(self, row):
        self.calls.append(("insert", row))
        self.inserted_rows.append(row)
        if isinstance(self.inserted, BaseException):
            raise self.inserted
        return self.inserted

    async def fetch_forecast_outcome_klines(self, **kw):
        self.calls.append(("outcome_read", kw))
        return self.rows

    async def upsert_forecast_outcomes(self, rows):
        self.calls.append(("outcome_write", tuple(rows)))
        self.outcome_upserts.append(tuple(rows))
        return len(rows)

    async def fetch_exchange_feature_raw_bundle(self, **kw):
        exchange = kw["exchange"]
        self.calls.append(("raw", exchange))
        if self.block_first_read is not None and len([c for c in self.calls if c[0] == "raw"]) == 1:
            self.block_first_read["started"].set()
            await self.block_first_read["release"].wait()
        if exchange in self.fail_raw:
            raise ValueError(f"raw boom {exchange}")
        return self.bundles[exchange]

    async def upsert_exchange_feature_vectors(self, rows):
        self.calls.append(("efv", rows[0].exchange))
        self.exchange_upserts.append(tuple(rows))
        return len(rows)

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append(("consensus",))
        self.consensus_upserts.append(tuple(rows))
        return len(rows)


def run(coro):
    return asyncio.run(coro)


async def _cycle(rw, **kw):
    params = dict(exchanges=("binance", "bybit", "okx"), symbol="BTCUSDT", market_type="perp",
                  timeframe="5m", bucket_ts=B, code_version="code-v1",
                  liquidation_feed_available_by_exchange={"binance": True, "bybit": True, "okx": True},
                  reference_exchange="binance")
    params.update(kw)
    return await process_shadow_cycle(rw, rw, CFG, **params)


@pytest.mark.parametrize("bad", [object(), "binance", {"binance"}, iter(["binance"])])
def test_preflight_bad_exchanges_before_io(bad):
    rw = FakeRW()
    with pytest.raises(ShadowCycleError):
        run(_cycle(rw, exchanges=bad))
    assert rw.calls == []


@pytest.mark.parametrize("kw", [
    dict(stage2_config=object()), dict(forecast_rules=object()), dict(exchanges=()),
    dict(exchanges=("binance", "kraken")), dict(exchanges=("binance", "binance")),
    dict(reference_exchange="kraken"), dict(reference_exchange="okx", exchanges=("binance", "bybit")),
    dict(due_outcome_jobs=object()), dict(due_outcome_jobs=[object()]),
])
def test_preflight_malformed_inputs_before_io(monkeypatch, kw):
    async def fake(*a, **k):
        raise AssertionError("stage2 should not run")
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake)
    rw = FakeRW()
    params = dict(exchanges=("binance",), symbol="BTCUSDT", market_type="perp", timeframe="5m",
                  bucket_ts=B, code_version="code-v1", liquidation_feed_available_by_exchange={"binance": True},
                  reference_exchange="binance")
    stage2_config = kw.pop("stage2_config", CFG)
    params.update(kw)
    with pytest.raises(ShadowCycleError):
        run(process_shadow_cycle(rw, rw, stage2_config, **params))
    assert rw.calls == []


@pytest.mark.parametrize("over", [dict(prediction=object()), dict(horizon="30m"), dict(evaluation_exchange="bybit"), dict(outcome_version=" ")])
def test_due_outcome_job_validation(over):
    params = dict(prediction=_prediction(), horizon="15m", evaluation_exchange="binance")
    params.update(over)
    with pytest.raises((ShadowCycleError, ValueError)):
        DueOutcomeJob(**params)


def test_duplicate_due_jobs_rejected_before_io(monkeypatch):
    job = DueOutcomeJob(_prediction(), "15m", "binance")
    rw = FakeRW()
    with pytest.raises(ShadowCycleError):
        run(_cycle(rw, due_outcome_jobs=[job, job]))
    assert rw.calls == []


@pytest.mark.parametrize("direction,cv_over", [
    ("LONG", {}),
    ("SHORT", dict(price_move_pct_median=-0.4, taker_buy_notional_usd_sum=200.0, taker_sell_notional_usd_sum=800.0, taker_delta_notional_usd_sum=-600.0, cvd_delta_notional_usd_sum=-600.0, observed_long_liquidation_notional_sum=900.0, observed_short_liquidation_notional_sum=100.0, funding_rate_median=-0.0001)),
    (NEUTRAL, dict(min_coverage_ratio=1.0 / 3.0)),
])
def test_happy_path_inserted_all_directions(monkeypatch, direction, cv_over):
    bucket = _bucket(consensus=_cv(**cv_over))
    async def fake_stage2(*a, **k): return bucket
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(inserted=True)
    result = run(_cycle(rw))
    assert result.prediction_status == PREDICTION_INSERTED
    assert result.bucket_result is bucket
    assert result.decision.direction == direction
    assert result.prediction.direction == direction
    assert result.prediction.reference_price == 105.0
    assert result.prediction.reference_price_source == "binance_close_5m"
    assert result.prediction.consensus_snapshot is bucket.consensus_feature
    assert rw.inserted_rows == [result.prediction]
    assert result.outcome_evaluations == ()


def test_duplicate_prediction_is_idempotent(monkeypatch):
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", lambda *a, **k: _bucket())
    async def fake_stage2(*a, **k): return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(inserted=False)
    result = run(_cycle(rw))
    assert result.prediction_status == PREDICTION_DUPLICATE
    assert result.prediction is not None and result.decision is not None
    assert len(rw.inserted_rows) == 1


def test_no_consensus_still_processes_due_outcome(monkeypatch):
    old = _prediction()
    window = build_forecast_outcome_window(old, horizon="15m", evaluation_exchange="binance")
    rows = [dict(exchange="binance", symbol="BTCUSDT", ts=window.evaluation_start_ts + timedelta(minutes=i),
                 open=100.0, high=101.0, low=99.0, close=100.0) for i in range(15)]
    async def fake_stage2(*a, **k): return _bucket(consensus=None, features=[])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(rows=rows)
    result = run(_cycle(rw, due_outcome_jobs=[DueOutcomeJob(old, "15m", "binance")]))
    assert result.prediction_status == PREDICTION_SKIPPED_NO_CONSENSUS
    assert result.decision is None and result.prediction is None and result.prediction_inserted is None
    assert len(result.outcome_evaluations) == 1
    assert result.outcome_evaluations[0].status == OUTCOME_COMPLETE
    assert rw.inserted_rows == [] and len(rw.outcome_upserts) == 1


@pytest.mark.parametrize("feature", [
    _efv("bybit"), _efv("binance", is_usable=False), _efv("binance", has_gap=True),
    _efv("binance", bars_present=4), _efv("binance", close_price=None),
])
def test_reference_unavailable_no_fallback(monkeypatch, feature):
    async def fake_stage2(*a, **k): return _bucket(features=[feature, _efv("bybit"), _efv("okx")])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW()
    result = run(_cycle(rw))
    assert result.prediction_status == PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE
    assert result.decision is not None and result.prediction is None
    assert rw.inserted_rows == []


@pytest.mark.parametrize("close", [True, float("nan"), float("inf"), -float("inf"), 0.0, -1.0])
def test_malformed_reference_close_raises(monkeypatch, close):
    async def fake_stage2(*a, **k): return _bucket(features=[_efv("binance", close_price=close), _efv("bybit")])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


@pytest.mark.parametrize("horizon", ["15m", "1h", "4h"])
def test_explicit_complete_outcome_jobs(monkeypatch, horizon):
    old = _prediction()
    window = build_forecast_outcome_window(old, horizon=horizon, evaluation_exchange="binance")
    rows = [dict(exchange="binance", symbol="BTCUSDT", ts=window.evaluation_start_ts + timedelta(minutes=i),
                 open=100.0, high=101.0, low=99.0, close=100.0) for i in range(window.bars_expected)]
    async def fake_stage2(*a, **k): return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(rows=rows)
    result = run(_cycle(rw, due_outcome_jobs=[DueOutcomeJob(old, horizon, "binance")]))
    assert result.outcome_evaluations[0].status == OUTCOME_COMPLETE
    assert rw.outcome_upserts[0][0] is result.outcome_evaluations[0].outcome


def test_incomplete_outcome_not_persisted(monkeypatch):
    old = _prediction()
    async def fake_stage2(*a, **k): return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(rows=[])
    result = run(_cycle(rw, due_outcome_jobs=[DueOutcomeJob(old, "15m", "binance")]))
    assert result.outcome_evaluations[0].status == OUTCOME_INCOMPLETE
    assert rw.outcome_upserts == []


@pytest.mark.parametrize("exc_attr", ["stage2", "forecast", "prediction", "outcome_read", "outcome_write"])
def test_exceptions_propagate(monkeypatch, exc_attr):
    boom = RuntimeError("boom")
    async def fake_stage2(*a, **k):
        if exc_attr == "stage2": raise boom
        return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    if exc_attr == "forecast":
        monkeypatch.setattr("analytics.forecasting.shadow_cycle.compute_forecast_decision", lambda *a, **k: (_ for _ in ()).throw(boom))
        rw = FakeRW()
    elif exc_attr == "prediction":
        rw = FakeRW(inserted=boom)
    elif exc_attr == "outcome_read":
        rw = FakeRW()
        async def bad_read(**kw): raise boom
        rw.fetch_forecast_outcome_klines = bad_read
    elif exc_attr == "outcome_write":
        old = _prediction(); window = build_forecast_outcome_window(old, horizon="15m", evaluation_exchange="binance")
        rows = [dict(exchange="binance", symbol="BTCUSDT", ts=window.evaluation_start_ts + timedelta(minutes=i), open=100.0, high=101.0, low=99.0, close=100.0) for i in range(15)]
        rw = FakeRW(rows=rows)
        async def bad_write(rows): raise boom
        rw.upsert_forecast_outcomes = bad_write
    else:
        rw = FakeRW()
    jobs = [DueOutcomeJob(_prediction(), "15m", "binance")] if exc_attr in ("outcome_read", "outcome_write") else []
    with pytest.raises(RuntimeError) as ei:
        run(_cycle(rw, due_outcome_jobs=jobs))
    assert ei.value is boom
    if exc_attr in ("outcome_read", "outcome_write"):
        assert len(rw.inserted_rows) == 1


def test_result_detaches_and_is_frozen():
    evs = [_eval()]
    result = ShadowCycleResult(_bucket(), PREDICTION_INSERTED, compute_forecast_decision(_cv()), _prediction(), True, evs)
    evs.clear()
    assert len(result.outcome_evaluations) == 1 and isinstance(result.outcome_evaluations, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.prediction_status = "x"


def test_result_rejects_copied_consensus_snapshot_identity():
    consensus = _cv()
    copied = dataclasses.replace(consensus)
    decision = compute_forecast_decision(consensus)
    prediction = build_forecast_prediction(
        decision, copied, reference_price=105.0,
        reference_price_source="binance_close_5m",
    )
    with pytest.raises(ShadowCycleError):
        ShadowCycleResult(
            _bucket(consensus=consensus), PREDICTION_INSERTED, decision,
            prediction, True, [],
        )


@pytest.mark.parametrize("kwargs", [
    dict(bucket_result=object()), dict(prediction_status="BAD"), dict(outcome_evaluations=iter([])),
    dict(outcome_evaluations=[object()]), dict(prediction_status=PREDICTION_INSERTED, prediction_inserted=False),
    dict(prediction_status=PREDICTION_SKIPPED_NO_CONSENSUS, decision=compute_forecast_decision(_cv())),
])
def test_result_rejects_invariants(kwargs):
    base = dict(bucket_result=_bucket(), prediction_status=PREDICTION_INSERTED,
                decision=compute_forecast_decision(_cv()), prediction=_prediction(), prediction_inserted=True,
                outcome_evaluations=[])
    base.update(kwargs)
    if base["prediction_status"] == PREDICTION_SKIPPED_NO_CONSENSUS:
        base["bucket_result"] = _bucket(consensus=None, features=[])
    with pytest.raises(ShadowCycleError):
        ShadowCycleResult(**base)


@pytest.mark.parametrize("expected,present,ok_status", [
    (5, 5, PREDICTION_INSERTED),
    (5, 4, PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE),
])
def test_reference_bar_count_valid_cases(monkeypatch, expected, present, ok_status):
    async def fake_stage2(*a, **k):
        return _bucket(features=[_efv("binance", bars_expected=expected, bars_present=present)])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    result = run(_cycle(FakeRW()))
    assert result.prediction_status == ok_status


@pytest.mark.parametrize("expected,present", [
    (4, 4), (3, 3), (0, 0), (True, 5), (5, True), (5.0, 5),
    (5, 5.0), ("5", 5), (5, "5"), (5, -1), (5, 6),
])
def test_reference_bar_count_malformed_rejected(monkeypatch, expected, present):
    async def fake_stage2(*a, **k):
        return _bucket(features=[_efv("binance", bars_expected=expected, bars_present=present)])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


def test_huge_int_reference_close_rejected(monkeypatch):
    async def fake_stage2(*a, **k):
        return _bucket(features=[_efv("binance", close_price=10 ** 400)])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


@pytest.mark.parametrize("returned", [None, 0, 1, "true", object()])
def test_prediction_writer_must_return_actual_bool(monkeypatch, returned):
    async def fake_stage2(*a, **k): return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW(inserted=returned)))


def test_process_stage2_bucket_must_return_stage2_bucket_result(monkeypatch):
    async def fake_stage2(*a, **k): return object()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


def test_malformed_exchange_feature_item_rejected_before_attribute_access(monkeypatch):
    async def fake_stage2(*a, **k): return _bucket(features=[object()])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


def test_multiple_reference_vectors_rejected(monkeypatch):
    async def fake_stage2(*a, **k): return _bucket(features=[_efv("binance"), _efv("binance")])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    with pytest.raises(ShadowCycleError):
        run(_cycle(FakeRW()))


def test_real_coordinator_integration_three_exchanges():
    cfg = Stage2Config.load()
    rw = FakeRW(bundles={ex: _bundle(ex, final_close=777.0 if ex == "binance" else None) for ex in EXS})
    result = run(process_shadow_cycle(
        rw, rw, cfg, exchanges=list(EXS), symbol=SYM, market_type=MT, timeframe="5m",
        bucket_ts=B, code_version="code-v1",
        liquidation_feed_available_by_exchange={ex: True for ex in EXS},
        reference_exchange="binance",
    ))
    assert [c[0] for c in rw.calls] == ["raw", "efv", "raw", "efv", "raw", "efv", "consensus", "insert"]
    assert len(rw.exchange_upserts) == 3
    assert len(rw.consensus_upserts) == 1
    assert len(rw.inserted_rows) == 1
    assert result.bucket_result.consensus_feature is rw.consensus_upserts[0][0]
    assert result.prediction.reference_price == 777.0
    assert result.prediction.reference_price_source == "binance_close_5m"


def test_partial_consensus_non_reference_failure_still_inserts():
    cfg = Stage2Config.load()
    rw = FakeRW(bundles={ex: _bundle(ex) for ex in EXS}, fail_raw={"okx"})
    result = run(process_shadow_cycle(
        rw, rw, cfg, exchanges=list(EXS), symbol=SYM, market_type=MT, timeframe="5m",
        bucket_ts=B, code_version="code-v1",
        liquidation_feed_available_by_exchange={ex: True for ex in EXS},
        reference_exchange="binance",
    ))
    assert len(result.bucket_result.failures) == 1
    assert result.bucket_result.failures[0].exchange == "okx"
    assert tuple(result.bucket_result.expected_exchanges_by_family["price_structure"]) == EXS
    assert result.bucket_result.consensus_feature.is_partial_consensus is True
    assert result.prediction_status == PREDICTION_INSERTED
    assert len(rw.inserted_rows) == 1


def test_multiple_due_jobs_preserve_order_and_persistence(monkeypatch):
    p = _prediction()
    complete_window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    complete_rows = [dict(exchange="binance", symbol="BTCUSDT", ts=complete_window.evaluation_start_ts + timedelta(minutes=i),
                          open=100.0, high=101.0, low=99.0, close=100.0) for i in range(15)]
    class SequencedRW(FakeRW):
        def __init__(self):
            super().__init__()
            self.read_count = 0
        async def fetch_forecast_outcome_klines(self, **kw):
            self.calls.append(("outcome_read", kw["window_end"]))
            self.read_count += 1
            return complete_rows if self.read_count == 1 else []
    async def fake_stage2(*a, **k): return _bucket()
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = SequencedRW()
    result = run(_cycle(rw, due_outcome_jobs=[DueOutcomeJob(p, "15m", "binance"), DueOutcomeJob(_prediction(bucket_ts=B + timedelta(minutes=5)), "15m", "binance")]))
    assert [ev.status for ev in result.outcome_evaluations] == [OUTCOME_COMPLETE, OUTCOME_INCOMPLETE]
    assert isinstance(result.outcome_evaluations, tuple)
    assert len(rw.outcome_upserts) == 1
    assert rw.outcome_upserts[0][0] is result.outcome_evaluations[0].outcome


def test_reference_unavailable_still_runs_due_jobs(monkeypatch):
    p = _prediction()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = [dict(exchange="binance", symbol="BTCUSDT", ts=window.evaluation_start_ts + timedelta(minutes=i),
                 open=100.0, high=101.0, low=99.0, close=100.0) for i in range(15)]
    async def fake_stage2(*a, **k): return _bucket(features=[_efv("binance", bars_present=4), _efv("bybit")])
    monkeypatch.setattr("analytics.forecasting.shadow_cycle.process_stage2_bucket", fake_stage2)
    rw = FakeRW(rows=rows)
    result = run(_cycle(rw, due_outcome_jobs=[DueOutcomeJob(p, "15m", "binance")]))
    assert result.prediction_status == PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE
    assert result.prediction is None and rw.inserted_rows == []
    assert result.outcome_evaluations[0].status == OUTCOME_COMPLETE


def test_mutable_inputs_snapshot(monkeypatch):
    p = _prediction()
    started, release = asyncio.Event(), asyncio.Event()
    rw = FakeRW(
        bundles={ex: _bundle(ex) for ex in EXS},
        rows=[],
        block_first_read={"started": started, "release": release},
    )
    exchanges = ["binance", "bybit", "okx"]
    jobs = [DueOutcomeJob(p, "15m", "binance")]
    async def main():
        task = asyncio.create_task(process_shadow_cycle(
            rw, rw, Stage2Config.load(), exchanges=exchanges, symbol=SYM, market_type=MT,
            timeframe="5m", bucket_ts=B, code_version="code-v1",
            liquidation_feed_available_by_exchange={ex: True for ex in EXS},
            reference_exchange="binance", due_outcome_jobs=jobs,
        ))
        await started.wait()
        exchanges[:] = ["binance"]
        jobs.clear()
        jobs.append(DueOutcomeJob(_prediction(bucket_ts=B + timedelta(minutes=5)), "15m", "binance"))
        release.set()
        return await task
    result = run(main())
    assert [call for call in rw.calls if call[0] == "raw"] == [("raw", "binance"), ("raw", "bybit"), ("raw", "okx")]
    assert len(result.outcome_evaluations) == 1
    assert result.outcome_evaluations[0].evaluation_start_ts == B + timedelta(minutes=5)


def test_architecture_no_forbidden_imports_or_runtime_patterns():
    tree = ast.parse(Path("analytics/forecasting/shadow_cycle.py").read_text())
    source = Path("analytics/forecasting/shadow_cycle.py").read_text()
    forbidden = {"storage", "Database", "asyncpg", "aiohttp", "requests", "websocket", "os", "dotenv", "subprocess", "pathlib", "main", "data_ingestion", "backfill", "deployment", "systemd", "Telegram", "time", "asyncio", "random", "numpy", "pandas", "sklearn", "torch", "tensorflow"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            name = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            assert name.split(".")[0] not in forbidden
        assert not isinstance(node, ast.While)
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"now", "utcnow", "sleep", "gather", "create_task", "ensure_future"}
    assert "SELECT " not in source and "CREATE TABLE" not in source and "retry" not in source.lower()
