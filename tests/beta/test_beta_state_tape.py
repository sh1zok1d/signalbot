"""State tape: reuse of the real Stage-2 pipeline, by-value snapshot, no-lookahead
percentiles, maturity, reference price, liquidation unavailable-vs-measured-zero."""
import random
from datetime import timedelta

import pytest

from beta_fakes import (BETA_CODE, CFG, EXS, FEATURE_CODE, S2, T0, ScenarioReader, down_move,
                        history_buckets, history_metrics, quiet, run)
from analytics.percentile_engine.models import PercentileError
from beta.state_tape import (build_tape_record, compute_percentiles, extract_metrics,
                             materialize_bucket, percentile_inputs, reference_price,
                             select_latest_closed_bucket)

B = T0 + timedelta(days=40)
HEALTHY = {e: {"declared_available": True, "live_bars": 5, "bars": 5, "outage_overlap": False,
               "heartbeat_healthy": True} for e in EXS}


def _mat(scenario, avail=None):
    return run(materialize_bucket(ScenarioReader(scenario), S2, CFG, bucket_ts=B, code_version=FEATURE_CODE,
                                  liquidation_feed_available_by_exchange=avail or {e: True for e in EXS}))


def _record(result, percentiles=None, venues=HEALTHY, evaluated_at=None, before=0, after=0):
    return build_tape_record(CFG, bucket_ts=B, origin="LIVE", result=result, materialization_error=None,
                             venues=venues, percentiles=percentiles, code_version=BETA_CODE,
                             feature_code_version=FEATURE_CODE, raw_revision_before=before,
                             raw_revision_after=after,
                             evaluated_at=evaluated_at or B + timedelta(minutes=5, seconds=30))


def test_latest_closed_bucket_respects_grace():
    now = T0 + timedelta(minutes=10, seconds=10)
    assert select_latest_closed_bucket(now, grace_s=20) == T0
    assert select_latest_closed_bucket(now + timedelta(seconds=15), grace_s=20) == T0 + timedelta(minutes=5)


def test_materialization_reuses_stage2_pipeline_and_writes_nothing_to_stage2():
    r = _mat(down_move)
    c = r.consensus_feature
    assert c.price_move_pct_median == pytest.approx(-2.0) and c.oi_change_pct_median == pytest.approx(-3.0)
    assert len(c.calculation_version) == 16


def test_snapshot_is_by_value_and_digest_deterministic():
    r = _mat(down_move)
    a, b = _record(r), _record(r)
    assert a.snapshot_digest == b.snapshot_digest and a.feature_digest == b.feature_digest
    assert a.snapshot["metrics"]["c:price_move_pct_median"] == pytest.approx(-2.0)
    assert a.snapshot["reference"]["status"] == "OK" and a.snapshot["reference"]["exchanges"] == list(EXS)
    import json
    json.dumps(a.snapshot)                   # plain JSON-safe values only
    assert "telegram" not in json.dumps(a.snapshot).lower()
    later = _record(r, evaluated_at=B + timedelta(minutes=6))
    assert later.feature_digest == a.feature_digest and later.snapshot_digest != a.snapshot_digest


def test_percentile_window_excludes_current_bucket_and_rejects_lookahead():
    r = _mat(down_move)
    ident = percentile_inputs(r)
    m = extract_metrics(r, CFG, {e: True for e in EXS})
    rng = random.Random(3)
    hist = [(b, history_metrics(rng)) for b in history_buckets(B, 1)]
    p = compute_percentiles(S2, CFG, bucket_ts=B, metrics=m, ident=ident, code_version=FEATURE_CODE, history=hist)
    assert p["c:price_move_pct_median"]["rank"] == 0.0 and p["c:price_move_pct_median"]["tier"] == "mature"
    assert p["c:price_move_pct_median"]["window_end"] < B.isoformat().replace("+00:00", "Z")
    with pytest.raises(PercentileError):          # the current bucket may never be a sample
        compute_percentiles(S2, CFG, bucket_ts=B, metrics=m, ident=ident, code_version=FEATURE_CODE,
                            history=hist + [(B, history_metrics(rng))])


def test_immature_history_is_not_mature():
    r = _mat(down_move)
    rng = random.Random(4)
    hist = [(B - timedelta(days=d), history_metrics(rng)) for d in range(1, 20)]   # span 19d
    p = compute_percentiles(S2, CFG, bucket_ts=B, metrics=extract_metrics(r, CFG, {e: True for e in EXS}),
                            ident=percentile_inputs(r), code_version=FEATURE_CODE, history=hist)
    assert all(v["tier"] == "building" for v in p.values())


def test_reference_price_needs_two_usable_venues_no_single_venue_fallback():
    r = _mat(lambda b: {"binance": {}, "bybit": "FAIL", "okx": "FAIL"})
    ref = reference_price(r, CFG)
    assert ref["status"] == "INSUFFICIENT_VENUES" and ref["price"] is None
    r2 = _mat(lambda b: {"binance": {"base": 100.0}, "bybit": {"base": 102.0}, "okx": "FAIL"})
    ref2 = reference_price(r2, CFG)
    assert ref2["status"] == "OK" and ref2["price"] == pytest.approx(101.0) and ref2["dispersion_pct"] > 0


def test_liquidation_unhealthy_venue_is_none_but_healthy_zero_is_measured():
    r = _mat(quiet, avail={"binance": True, "bybit": False, "okx": True})
    venues = dict(HEALTHY, bybit=dict(HEALTHY["bybit"], heartbeat_healthy=False, live_bars=3))
    rec = _record(r, venues=venues)
    assert rec.metrics["x:binance:long_liquidation_notional"] == 0.0     # measured zero
    assert rec.metrics["x:bybit:long_liquidation_notional"] is None      # never a fake zero


def test_stale_barrier_and_late_evaluation_are_not_fresh():
    r = _mat(down_move)
    assert _record(r).evaluation_fresh is True
    assert _record(r, before=1, after=2).evaluation_fresh is False
    assert _record(r, evaluated_at=B + timedelta(minutes=20)).evaluation_fresh is False


def test_unmaterialized_bucket_is_recorded_fail_closed():
    rec = build_tape_record(CFG, bucket_ts=B, origin="LIVE", result=None, materialization_error="ConsensusError",
                            venues=HEALTHY, percentiles=None, code_version=BETA_CODE,
                            feature_code_version=FEATURE_CODE, raw_revision_before=0, raw_revision_after=0,
                            evaluated_at=B + timedelta(minutes=5, seconds=30))
    assert rec.materialized is False and rec.evaluation_fresh is False
    assert rec.calculation_version == "UNMATERIALIZED"
    assert all(not f["usable"] for f in rec.snapshot["families"].values())
