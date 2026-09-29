"""PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0 synthetic tests. No database, no network."""
from __future__ import annotations

import itertools
import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, BetaConfig
from beta.models import NOT_EVALUABLE, NOT_QUALIFIES, QUALIFIES
from beta.rules import _threshold_rule
from scripts.audit.live_archive_replay_preflight import price_oi_semantic_replay as semantic
from scripts.audit.live_archive_replay_preflight.extract_sql import assert_text_read_only
from scripts.audit.price_oi_incremental_information_pilot_v0 import pilot
from scripts.audit.price_oi_incremental_information_pilot_v0 import run_pilot

UTC = timezone.utc
BUCKET = timedelta(minutes=5)
T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
FAMILIES = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP)


@pytest.fixture(scope="module")
def cfg():
    return BetaConfig.load()


def _prepared(bucket, *, price_rank, oi_rank, price_tier="mature", oi_tier="mature",
              price_available=2, oi_available=2, price_median=1.0, oi_median=-1.0):
    rec = semantic.BucketReconstruction(
        bucket_ts=bucket, price_median=price_median, oi_median=oi_median,
        price_available=price_available, oi_available=oi_available,
        price_venues=("binance", "bybit"), oi_venues=("binance", "bybit"),
        calculation_version="0123456789abcdef", venue_failures=())
    return semantic.PreparedBucket(rec, price_rank, oi_rank, price_tier, oi_tier)


def _extreme(family):
    return 0.01 if family == PRICE_OI_CONTRACTION_DOWN else 0.99


def _obs(anchor, group="A", *, cov=(0.0, 0.0, 0.0, 0.0), r4=1.0, r1=0.5, hour=None, weekend=0.0,
         exclusion=None, family=PRICE_OI_CONTRACTION_DOWN):
    covariates = dict(zip(pilot.MATCHED_COVARIATES, cov))
    covariates.update(pilot.time_covariates(anchor))
    covariates["weekend"] = weekend
    if hour is not None:
        covariates["hour_sin"], covariates["hour_cos"] = hour
    return pilot.Observation(family, group, anchor, covariates, {"1h": r1, "4h": r4}, exclusion)


# ---- protocol ----------------------------------------------------------------------
def test_protocol_frozen_and_code_constants_match(tmp_path):
    doc = pilot.check_protocol()
    assert doc["classification"] == "PILOT_ONLY" and doc["confirmatory"] is False
    assert doc["protected_2025_2026_used"] is False and doc["trading_claim"] is False
    assert doc["control_group_b"]["future_event_exclusion"] is False
    altered = json.loads(pilot.PROTOCOL_PATH.read_text())
    altered["matching"]["caliper"] = 1.0
    path = tmp_path / "p.json"
    path.write_text(json.dumps(altered))
    with pytest.raises(pilot.ProtocolMismatch, match="caliper"):
        pilot.check_protocol(path)


# ---- predicates ----------------------------------------------------------------------
RANKS = (0.0, 0.01, 0.05, 0.06, 0.1, 0.11, 0.3, 0.49, 0.5, 0.51, 0.9, 0.94, 0.95, 0.99, 1.0)


@pytest.mark.parametrize("family", FAMILIES)
def test_event_is_exactly_price_side_and_oi_tail(cfg, family):
    oi_max = cfg.rule(family)["oi_change_pct_median_max"]
    for price_rank, oi_rank in itertools.product(RANKS, RANKS):
        item = _prepared(T0, price_rank=price_rank, oi_rank=oi_rank)
        event = pilot.event_status(cfg, family, item)
        assert event == semantic.semantic_rule(cfg, family, item)[0]
        price_ok = pilot.price_side_status(cfg, family, item) == QUALIFIES
        assert (event == QUALIFIES) == (price_ok and oi_rank <= oi_max)


@pytest.mark.parametrize("family", FAMILIES)
def test_price_side_equals_production_threshold_rule_price_check(cfg, family):
    rule = cfg.rule(family)
    check = (("price_move_pct_median", "<=", rule["price_move_pct_median_max"])
             if family == PRICE_OI_CONTRACTION_DOWN
             else ("price_move_pct_median", ">=", rule["price_move_pct_median_min"]))
    for price_rank, oi_rank in itertools.product(RANKS, RANKS):
        item = _prepared(T0, price_rank=price_rank, oi_rank=oi_rank)
        snap = {**semantic._projection(cfg, item), "materialized": True, "stale_barrier": False,
                "evaluation_fresh": True}
        production = _threshold_rule(snap, ("price_structure", "oi"), [check])[0]
        assert pilot.price_side_status(cfg, family, item) == production


@pytest.mark.parametrize("family", FAMILIES)
def test_control_changes_only_the_oi_component(cfg, family):
    x = _extreme(family)
    assert pilot.control_status(cfg, family, _prepared(T0, price_rank=x, oi_rank=0.5)) == QUALIFIES
    assert pilot.control_status(cfg, family, _prepared(T0, price_rank=x, oi_rank=0.8)) == QUALIFIES
    # Between the contraction tail and the median: neither group.
    mid = _prepared(T0, price_rank=x, oi_rank=0.3)
    assert pilot.control_status(cfg, family, mid) == NOT_QUALIFIES
    assert pilot.event_status(cfg, family, mid) == NOT_QUALIFIES
    # Contracting OI: event, never control.
    tail = _prepared(T0, price_rank=x, oi_rank=0.05)
    assert pilot.event_status(cfg, family, tail) == QUALIFIES
    assert pilot.control_status(cfg, family, tail) == NOT_QUALIFIES
    # Price side not met: never control, whatever OI does.
    calm = _prepared(T0, price_rank=0.5, oi_rank=0.9)
    assert pilot.control_status(cfg, family, calm) == NOT_QUALIFIES
    # OI must be valid: immature / missing / unusable OI is not evaluable.
    for bad in (dict(oi_tier="developing"), dict(oi_median=None), dict(oi_available=1),
                dict(price_tier="developing"), dict(oi_rank=None)):
        kwargs = dict(price_rank=x, oi_rank=0.9) | bad
        assert pilot.control_status(cfg, family, _prepared(T0, **kwargs)) == NOT_EVALUABLE
    # Disjoint over the grid.
    for price_rank, oi_rank in itertools.product(RANKS, RANKS):
        item = _prepared(T0, price_rank=price_rank, oi_rank=oi_rank)
        assert not (pilot.event_status(cfg, family, item) == QUALIFIES
                    and pilot.control_status(cfg, family, item) == QUALIFIES)


# ---- lifecycle -------------------------------------------------------------------------
def _series(ranks, start=T0):
    return [_prepared(start + i * BUCKET, price_rank=p, oi_rank=o) for i, (p, o) in enumerate(ranks)]


def test_event_lifecycle_reproduces_replay_series(cfg):
    ranks = [(0.01, 0.01), (0.01, 0.01), (0.01, 0.01), (0.5, 0.5), (0.01, 0.02), (0.01, 0.02),
             (0.99, 0.05), (0.99, 0.05), (0.99, 0.9), (0.01, 0.01)]
    series = _series(ranks)
    gap_after = [_prepared(datetime(2026, 9, 25, 12, 40, tzinfo=UTC), price_rank=0.01, oi_rank=0.01),
                 _prepared(datetime(2026, 9, 25, 13, 5, tzinfo=UTC), price_rank=0.01, oi_rank=0.01)]
    for prepared in (series, series + gap_after):
        replayed = semantic.replay_series(cfg, prepared)
        for family in FAMILIES:
            want = sorted(e.episode.triggered_at for e in replayed["episodes"]
                          if e.episode.event_type == family and e.episode.triggered_at)
            assert pilot.triggered_anchors(cfg, family, prepared, pilot.event_status) == want
    assert pilot.triggered_anchors(cfg, PRICE_OI_CONTRACTION_DOWN, series, pilot.event_status) == [
        T0 + 2 * BUCKET, T0 + 6 * BUCKET]


def test_control_needs_same_persistence_and_gap_resets(cfg):
    fam = PRICE_OI_CONTRACTION_DOWN
    one = _series([(0.01, 0.9), (0.5, 0.9), (0.01, 0.9)])
    assert pilot.triggered_anchors(cfg, fam, one, pilot.control_status) == []
    two = _series([(0.01, 0.9), (0.01, 0.6), (0.01, 0.9)])
    assert pilot.triggered_anchors(cfg, fam, two, pilot.control_status) == [T0 + 2 * BUCKET]
    # A mixed run (one contracting, one non-contracting bucket) is neither group.
    mixed = _series([(0.01, 0.05), (0.01, 0.9)])
    assert pilot.triggered_anchors(cfg, fam, mixed, pilot.control_status) == []
    assert pilot.triggered_anchors(cfg, fam, mixed, pilot.event_status) == []
    broken = [_prepared(T0, price_rank=0.01, oi_rank=0.9),
              _prepared(T0 + 2 * BUCKET, price_rank=0.01, oi_rank=0.9)]
    assert pilot.triggered_anchors(cfg, fam, broken, pilot.control_status) == []


def test_control_eligibility_uses_no_future_buckets(cfg):
    fam = PRICE_OI_CONTRACTION_UP
    ranks = [(0.99, 0.9), (0.99, 0.7), (0.3, 0.2), (0.99, 0.6), (0.99, 0.55), (0.99, 0.05), (0.99, 0.02)]
    series = _series(ranks)
    full = pilot.triggered_anchors(cfg, fam, series, pilot.control_status)
    for cut in range(1, len(series) + 1):
        prefix = pilot.triggered_anchors(cfg, fam, series[:cut], pilot.control_status)
        assert prefix == [a for a in full if a <= series[cut - 1].reconstruction.bucket_ts + BUCKET]
    # An event right after a control does not remove it (no forward exclusion).
    assert full == [T0 + 2 * BUCKET, T0 + 5 * BUCKET]


# ---- covariates / outcomes -------------------------------------------------------------
def _flat_klines(start, minutes, *, price=100.0, spread=0.1, venues=("binance", "bybit")):
    rows = []
    for i in range(minutes):
        ts = start + timedelta(minutes=i)
        for v in venues:
            rows.append({"exchange": v, "ts": ts, "high": price + spread, "low": price - spread,
                         "close": price})
    return rows


def _ref(price=100.0):
    return {"status": "OK", "price": price, "exchanges": ["binance", "bybit"], "dispersion_pct": 0.0}


def test_covariates_ignore_bars_at_or_after_anchor_and_endpoint_uses_forward_bars():
    anchor = T0 + timedelta(days=2)
    base = _flat_klines(anchor - timedelta(hours=25), 25 * 60 + 5 * 60)
    a = pilot.observe(PRICE_OI_CONTRACTION_DOWN, "A", anchor, price_move=-0.8, reference=_ref(),
                      klines=pilot.KlineIndex(base))
    assert a.eligible
    assert a.covariates["log_prior_range_1h"] == pytest.approx(math.log(0.2))
    assert a.covariates["log_abs_trigger_price_move"] == pytest.approx(math.log(0.8))
    assert a.ranges["4h"] == pytest.approx(0.2)
    shocked = [dict(r, high=r["high"] + 5) if r["ts"] >= anchor + timedelta(hours=2) else r for r in base]
    b = pilot.observe(PRICE_OI_CONTRACTION_DOWN, "A", anchor, price_move=-0.8, reference=_ref(),
                      klines=pilot.KlineIndex(shocked))
    assert {k: b.covariates[k] for k in pilot.MATCHED_COVARIATES} == \
        {k: a.covariates[k] for k in pilot.MATCHED_COVARIATES}
    assert b.ranges["4h"] > a.ranges["4h"] and b.ranges["1h"] == a.ranges["1h"]
    # A missing forward minute fails closed; a missing pre-anchor minute drops the covariate.
    hole = [r for r in base if r["ts"] != anchor + timedelta(minutes=90)]
    assert pilot.observe(PRICE_OI_CONTRACTION_DOWN, "A", anchor, price_move=-0.8, reference=_ref(),
                         klines=pilot.KlineIndex(hole)).exclusion == pilot.OUTCOME_NOT_COMPLETE
    hole = [r for r in base if r["ts"] != anchor - timedelta(minutes=100)]
    assert pilot.observe(PRICE_OI_CONTRACTION_DOWN, "A", anchor, price_move=-0.8, reference=_ref(),
                         klines=pilot.KlineIndex(hole)).exclusion == pilot.COVARIATE_UNAVAILABLE
    assert pilot.observe(PRICE_OI_CONTRACTION_DOWN, "A", anchor, price_move=-0.8,
                         reference={"status": "INSUFFICIENT_VENUES", "price": None, "exchanges": []},
                         klines=pilot.KlineIndex(base)).exclusion == pilot.REFERENCE_UNAVAILABLE


def test_time_covariates_use_trigger_bucket():
    sat = datetime(2026, 9, 5, 0, 0, tzinfo=UTC)          # Saturday 00:00 anchor -> Friday 23:55 bucket
    assert pilot.time_covariates(sat)["weekend"] == 0.0
    assert pilot.time_covariates(sat + BUCKET)["weekend"] == 1.0


# ---- matching ---------------------------------------------------------------------------
def test_matching_is_deterministic_with_replacement_caliper_and_ties():
    e1, e2 = _obs(T0, cov=(0, 0, 0, 0)), _obs(T0 + timedelta(days=1), cov=(0, 0, 0, 0))
    far = _obs(T0 + timedelta(days=3), "B", cov=(5, 5, 5, 5))
    tie_late = _obs(T0 + timedelta(days=5), "B", cov=(0.1, 0, 0, 0))
    tie_early = _obs(T0 - timedelta(days=5), "B", cov=(-0.1, 0, 0, 0))
    near = [_obs(T0 + timedelta(days=10 + i), "B", cov=(0.2 * (i + 1), 0, 0, 0)) for i in range(3)]
    scale = {k: 1.0 for k in pilot.MATCHED_COVARIATES}
    controls = [far, tie_late, *near, tie_early]
    m = pilot.match([e1, e2], controls, scale)
    picked = [c.anchor for _d, c in m[e1.anchor]]
    assert picked == [tie_early.anchor, tie_late.anchor, near[0].anchor]     # k=3, earlier wins ties
    assert [c.anchor for _d, c in m[e2.anchor]] == picked                  # with replacement
    assert far.anchor not in picked                                          # outside caliper
    assert pilot.match([e1, e2], list(reversed(controls)), scale) == m      # order independent
    assert pilot.match([_obs(T0, cov=(9, 9, 9, 9))], controls, scale) == {}
    # Placebo never matches a pseudo-event to itself.
    pm = pilot.match(near, near, scale, exclude_self=True)
    assert all(c.anchor != a for a, pairs in pm.items() for _d, c in pairs)


# ---- gates / endpoint / verdicts ---------------------------------------------------------
def _world(n_events=12, n_controls=24, event_r4=2.0, control_r4=1.0, shift=0.0, event_cov_shift=0.0):
    events = [_obs(T0 + timedelta(hours=13 * i), cov=((i % 4) * 0.1 + event_cov_shift, (i % 3) * 0.1, 0.1, 0.2),
                   r4=event_r4, r1=event_r4 / 2) for i in range(n_events)]
    controls = [_obs(T0 + timedelta(hours=13 * i + 3), "B", cov=((i % 4) * 0.1 + shift, (i % 3) * 0.1, 0.1, 0.2),
                     r4=control_r4 * (1 + 0.01 * (i % 2)), r1=control_r4 / 2) for i in range(n_controls)]
    return events, controls


def test_survives_only_when_material_and_declustered():
    events, controls = _world(event_r4=2.0, control_r4=1.0)
    r = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)
    assert r["verdict"] == pilot.SURVIVES
    assert r["endpoint"]["4h"]["median_range_ratio"] == pytest.approx(2.0 / 1.005, rel=0.01)
    assert r["placebo"]["pass"] and r["support"]["matched_events"] == 12
    events, controls = _world(event_r4=1.1, control_r4=1.0)
    assert pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)["verdict"] == pilot.NULL_LIKE


def test_log_ratio_endpoint():
    e = _obs(T0, r4=3.0)
    cs = [_obs(T0, "B", r4=1.0), _obs(T0, "B", r4=4.0)]
    assert pilot.log_ratio(e, cs, "4h") == pytest.approx(math.log(3.0) - (math.log(1) + math.log(4)) / 2)


def test_balance_gate_fails_closed_and_hides_endpoint():
    events, controls = _world()
    events = [pilot.Observation(e.family, e.group, e.anchor, {**e.covariates, "weekend": 1.0}, e.ranges)
              for e in events]
    r = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)
    assert r["verdict"] == pilot.BALANCE_FAILED and r["verdict_reason"] == "SMD_GATE_FAILED"
    assert "endpoint" not in r and "placebo" not in r
    assert r["balance"]["weekend"]["pass"] is False and r["balance"]["weekend"]["smd"] == math.inf


def test_placebo_detects_a_pipeline_that_manufactures_differences(monkeypatch):
    # Identical covariates; the three earliest controls are low-range, so every
    # high-range pseudo-event is matched (tie-break) to them.
    lows = [_obs(T0 + timedelta(days=i), "B", r4=1.0, hour=(0.0, 1.0)) for i in range(3)]
    highs = [_obs(T0 + timedelta(days=10 + i), "B", r4=10.0, hour=(0.0, 1.0)) for i in range(13)]
    pool = lows + highs
    scale = pilot.scales(pool)
    bad = pilot.placebo_statistic(pool, pilot.match(pool, pool, scale, exclude_self=True))
    assert bad["pass"] is False and bad["median_log_ratio_4h"] == pytest.approx(math.log(10))
    same = [_obs(T0 + timedelta(days=i), "B", r4=2.0) for i in range(12)]
    ok = pilot.placebo_statistic(same, pilot.match(same, same, pilot.scales(same), exclude_self=True))
    assert ok["pass"] is True and ok["median_log_ratio_4h"] == 0.0
    # A failed placebo blocks interpretation of the event endpoint.
    events, controls = _world()
    monkeypatch.setattr(pilot, "placebo_statistic", lambda *_a: dict(bad))
    r = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)
    assert r["verdict"] == pilot.BALANCE_FAILED and r["verdict_reason"] == "PLACEBO_FAILED"
    assert "endpoint" not in r


def test_support_gate_and_data_block_fail_closed():
    events, controls = _world(n_controls=9)
    r = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)
    assert r["verdict"] == pilot.INSUFFICIENT and "endpoint" not in r
    events, controls = _world(n_events=9)
    assert pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)["verdict"] == pilot.INSUFFICIENT
    events, controls = _world(shift=50.0)            # nothing inside the caliper
    assert pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls)["verdict"] == pilot.INSUFFICIENT
    blocked = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, events, controls, data_blocked_reason="X")
    assert blocked["verdict"] == pilot.DATA_BLOCKED
    excluded = [pilot.Observation(e.family, e.group, e.anchor, e.covariates, e.ranges, pilot.OUTCOME_NOT_COMPLETE)
                for e in _world()[0]]
    r = pilot.evaluate_family(PRICE_OI_CONTRACTION_DOWN, excluded, _world()[1])
    assert r["verdict"] == pilot.INSUFFICIENT and r["event_exclusions"] == {pilot.OUTCOME_NOT_COMPLETE: 12}


def test_clusters_and_first_per_cluster():
    anchors = [T0, T0 + timedelta(hours=3), T0 + timedelta(hours=6, minutes=55),
               T0 + timedelta(hours=11), T0 + timedelta(days=2)]
    groups = pilot.clusters(anchors)
    assert [len(g) for g in groups] == [3, 1, 1]
    assert [g[0] for g in groups] == [T0, T0 + timedelta(hours=11), T0 + timedelta(days=2)]


def test_final_classification_rule():
    f = pilot.final_classification
    D, U = FAMILIES
    assert f({D: pilot.NULL_LIKE, U: pilot.NULL_LIKE}) == pilot.NULL_LIKE
    assert f({D: pilot.SURVIVES, U: pilot.NULL_LIKE}) == pilot.SURVIVES
    assert f({D: pilot.SURVIVES, U: pilot.DATA_BLOCKED}) == pilot.DATA_BLOCKED
    assert f({D: pilot.NULL_LIKE, U: pilot.INSUFFICIENT}) == pilot.INSUFFICIENT
    assert f({D: pilot.NULL_LIKE, U: pilot.BALANCE_FAILED}) == pilot.BALANCE_FAILED
    assert f({D: pilot.INSUFFICIENT, U: pilot.BALANCE_FAILED}) == pilot.INSUFFICIENT
    for word in pilot.FORBIDDEN_OUTPUTS:
        assert all(word not in v for v in pilot.VERDICTS)
        with pytest.raises(ValueError):
            pilot.assert_allowed_wording(f"x {word}")


# ---- runner -------------------------------------------------------------------------------
def test_runner_sql_read_only_and_refusals(tmp_path, monkeypatch, capsys):
    kline_sql, oi_sql = run_pilot.pilot_sql()
    for text in (kline_sql, oi_sql):
        assert_text_read_only(text)
        assert "source = 'live'" in text
    monkeypatch.delenv("SIGNALBOT_DSN", raising=False)
    assert run_pilot.main(["--out-dir", str(tmp_path)]) in (2,)
    assert run_pilot.main(["--out-dir", "/var/tmp/x"]) == 2
    monkeypatch.setenv("SIGNALBOT_DSN", "postgresql://user:secret@host/db")

    def explode(_dsn):
        raise RuntimeError("could not connect to postgresql://user:secret@host/db")
    assert run_pilot.main(["--out-dir", "/tmp/pilot_test_refusal"], connect=explode, code_version="t") == 1
    err = capsys.readouterr().err
    assert "secret" not in err


def test_runner_blocks_on_replay_refusal(monkeypatch, tmp_path):
    def refuse(*_a, **_k):
        raise SystemExit("authorized bucket count 1 != frozen Phase A count 12434")
    monkeypatch.setattr(run_pilot.replay, "build_replay", refuse)
    result = run_pilot.run([], [], code_version="t")
    assert result["final_classification"] == pilot.DATA_BLOCKED
    assert all(r["verdict"] == pilot.DATA_BLOCKED for r in result["families"].values())
    out = tmp_path / "o"
    run_pilot.write_outputs(out, result)
    doc = json.loads((out / "pilot_result.json").read_text())
    assert doc["production_tables_written"] is False and doc["protected_2025_2026_opened"] is False
    text = run_pilot.summary_lines(result, out)
    assert "FINAL_CLASSIFICATION=PILOT_DATA_BLOCKED" in pilot.assert_allowed_wording(text)


def test_runner_end_to_end_on_small_synthetic_archive(cfg, monkeypatch, tmp_path):
    start = datetime(2026, 9, 2, 0, 0, tzinfo=UTC)
    kline_rows, oi_rows = [], []
    for minute in range(36 * 60):
        ts = start + timedelta(minutes=minute)
        for venue in ("binance", "bybit", "okx"):
            price = 100.0 + (minute % 7) * 0.01
            kline_rows.append((venue, ts, price, price + 0.05, price - 0.05, price, 1.0))
            if minute % 5 == 0:
                oi_rows.append((venue, ts, 1000.0, "base"))
    trig = start + timedelta(hours=26)
    ranks = {trig: (0.01, 0.02), trig + BUCKET: (0.01, 0.02),
             trig + timedelta(hours=2): (0.01, 0.9), trig + timedelta(hours=2) + BUCKET: (0.01, 0.7)}
    series = [_prepared(b, price_rank=ranks.get(b, (0.5, 0.5))[0], oi_rank=ranks.get(b, (0.5, 0.5))[1],
                        price_median=-0.9)
              for b in (start + timedelta(hours=25) + i * BUCKET for i in range(72))]
    replayed = semantic.replay_series(cfg, series)
    monkeypatch.setattr(run_pilot.replay, "build_replay",
                        lambda *_a, **_k: {"prepared": series, "episodes": replayed["episodes"]})
    monkeypatch.setattr(pilot, "EXPECTED_AUTHORIZED_BUCKETS", len(series))
    monkeypatch.setattr(pilot, "EXPECTED_TRIGGERED", {PRICE_OI_CONTRACTION_DOWN: 1, PRICE_OI_CONTRACTION_UP: 0})
    result = run_pilot.run(kline_rows, oi_rows, code_version="t")
    down = result["families"][PRICE_OI_CONTRACTION_DOWN]
    assert down["event_anchors_triggered"] == 1 and down["control_anchors_triggered"] == 1
    assert down["events_eligible"] == 1 and down["controls_eligible"] == 1
    assert down["verdict"] == pilot.INSUFFICIENT
    assert result["families"][PRICE_OI_CONTRACTION_UP]["verdict"] == pilot.INSUFFICIENT
    assert result["final_classification"] == pilot.INSUFFICIENT
    obs = {o.group: o for o in result["observations"] if o.family == PRICE_OI_CONTRACTION_DOWN}
    assert obs["A"].anchor == trig + 2 * BUCKET and obs["B"].anchor == trig + timedelta(hours=2) + 2 * BUCKET
    assert obs["A"].covariates["log_abs_trigger_price_move"] == pytest.approx(math.log(0.9))
    run_pilot.write_outputs(tmp_path / "o", result)
    assert (tmp_path / "o" / "observations.csv").read_text().count("\n") == 3
