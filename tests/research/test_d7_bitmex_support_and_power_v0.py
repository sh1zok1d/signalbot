"""Outcome-blind guards for D7 BitMEX support and power. No network."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research import discovery_sprint_02_d7_one_shot as one_shot
from scripts.research import discovery_sprint_02_impl as sprint
from scripts.research.d7_bitmex_support_and_power_v0 import (
    BAR_MS,
    HOUR_MS,
    TRAILING_WINDOW,
    FiveMinuteBar,
    HourBar,
    aggregate_completed_hours,
    build_predictor_frame,
    d7_selector_digest,
    feasibility_decision,
    percentile,
    power_seed_for_fraction,
    render_markdown,
    structural_target_eligible,
    support_from_frame,
    synthetic_power,
    wilson_score_interval,
)
from scripts.research.discovery_sprint_02_impl import PERCENTILE_METHOD

MODULE_PATH = Path("scripts/research/d7_bitmex_support_and_power_v0.py")
HOUR_12 = 12


def _bar(open_ms: int, *, open_px: float = 100.0, close_px: float = 101.0, foreign: float = 10.0) -> FiveMinuteBar:
    return FiveMinuteBar(
        open_time_ms=open_ms,
        open=open_px,
        high=max(open_px, close_px),
        low=min(open_px, close_px),
        close=close_px,
        foreign_notional=foreign,
    )


def _hour_bars(start_ms: int, n_hours: int, *, foreign: float = 10.0, close_px: float = 101.0) -> list[FiveMinuteBar]:
    bars: list[FiveMinuteBar] = []
    for h in range(n_hours):
        hour = start_ms + h * HOUR_MS
        for k in range(HOUR_12):
            bars.append(_bar(hour + k * BAR_MS, close_px=close_px, foreign=foreign))
    return bars


def _hour(
    start_ms: int,
    *,
    year: int = 2017,
    open_px: float = 100.0,
    close_px: float = 100.0,
    foreign: float = 10.0,
) -> HourBar:
    import math

    return HourBar(
        hour_start_ms=start_ms,
        year=year,
        open_1h=open_px,
        close_1h=close_px,
        foreign_notional_1h=foreign,
        ret_abs_1h=abs(math.log(close_px / open_px)),
    )


def test_module_source_does_not_name_forbidden_evaluators():
    src = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    forbidden = {
        "construct_d7_scientific_arrays",
        "evaluate_d7_scientific",
        "call_reviewed_d7_evaluator",
    }
    assert forbidden.isdisjoint(called)


def test_runtime_path_does_not_call_scientific_evaluators(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("real scientific evaluator called")

    monkeypatch.setattr(one_shot, "construct_d7_scientific_arrays", boom)
    monkeypatch.setattr(one_shot, "call_reviewed_d7_evaluator", boom)
    monkeypatch.setattr(sprint, "evaluate_d7_scientific", boom)
    hours = [
        _hour(i * HOUR_MS, close_px=100.0 * (1.01 if i % 17 == 0 else 1.0), foreign=5.0 + (i % 5))
        for i in range(TRAILING_WINDOW + 8)
    ]
    frame = build_predictor_frame(hours)
    support = support_from_frame(frame)
    synthetic_power(
        [{"year": 2017, "rv_bucket": 0, "eligible_n": 20, "candidate_n": 4}],
        fraction=1.0,
        seed=11,
        n_outer=3,
        n_inner=5,
    )
    assert support["D7_BITMEX_PRIMARY_TARGET_OPENED"] is False
    assert "next_d7" not in json.dumps(support)


def test_hourly_construction_sums_foreign_notional_not_a_stand_in():
    start = 1_514_764_800_000  # 2018-01-01T00:00:00Z
    bars = []
    for k in range(HOUR_12):
        bars.append(
            _bar(
                start + k * BAR_MS,
                open_px=100.0 if k == 0 else 100.0,
                close_px=110.0 if k == HOUR_12 - 1 else 100.0,
                foreign=float(k + 1),
            )
        )
    # A thirteenth bar in the next hour must not be folded backward.
    bars.append(_bar(start + HOUR_MS, foreign=1000.0))
    hours = aggregate_completed_hours(bars)
    assert len(hours) == 1
    assert hours[0].foreign_notional_1h == float(sum(range(1, 13)))
    assert hours[0].open_1h == 100.0
    assert hours[0].close_1h == 110.0
    assert hours[0].ret_abs_1h == pytest.approx(abs(__import__("math").log(1.1)))


def test_gap_is_not_filled_and_blocks_next_hour_eligibility():
    start = 1_480_550_400_000  # 2016-12-01T00:00:00Z
    bars = _hour_bars(start, 1, foreign=10.0, close_px=101.0)
    # Skip the entire next hour, then build the hour after that.
    later = start + 2 * HOUR_MS
    bars.extend(_hour_bars(later, 1, foreign=10.0, close_px=101.0))
    hours = aggregate_completed_hours(bars)
    assert [h.hour_start_ms for h in hours] == [start, later]
    frame = build_predictor_frame(hours)
    eligible = structural_target_eligible(frame.hour_start_ms, frame.state_defined)
    assert bool(eligible[0]) is False


def test_trailing_window_excludes_current_hour_and_uses_strict_p90():
    prior = [0.0] * 648 + [10.0] * 72
    assert percentile(prior, 90.0) == pytest.approx(1.0)
    # Inclusion of a 1.2 current value, dropping the oldest 0, moves P90 above 1.2.
    included = prior[1:] + [1.2]
    assert percentile(included, 90.0) > 1.2
    base = 1_483_228_800_000  # 2017-01-01T00:00:00Z
    hours: list[HourBar] = []
    for i in range(TRAILING_WINDOW):
        # Constant activity so QREL stays 1 once the median window is full.
        # Impact then equals RET_ABS.
        close_px = 100.0 * __import__("math").exp(prior[i] if i < len(prior) else 0.0)
        hours.append(_hour(base + i * HOUR_MS, open_px=100.0, close_px=close_px, foreign=10.0))
    # The first 720 hours only fill the volume window. Impacts begin at index 720.
    # Build a long constant-activity prefix, then the impact design.
    prefix_n = TRAILING_WINDOW
    hours = [
        _hour(base + i * HOUR_MS, open_px=100.0, close_px=100.0, foreign=10.0)
        for i in range(prefix_n)
    ]
    for value in prior:
        close_px = 100.0 * __import__("math").exp(value)
        hours.append(
            _hour(base + len(hours) * HOUR_MS, open_px=100.0, close_px=close_px, foreign=10.0)
        )
    current = 100.0 * __import__("math").exp(1.2)
    hours.append(_hour(base + len(hours) * HOUR_MS, open_px=100.0, close_px=current, foreign=10.0))
    equal = 100.0 * __import__("math").exp(1.0)
    hours.append(_hour(base + len(hours) * HOUR_MS, open_px=100.0, close_px=equal, foreign=10.0))
    frame = build_predictor_frame(hours)
    # Current 1.2 is strictly above P90 of the prior design (1.0) only if excluded.
    assert frame.impact_proxy[-2] == pytest.approx(1.2)
    assert frame.state[-2] is True
    assert bool(frame.state_defined[-2]) is True
    prior_impacts = [v for v in frame.impact_proxy[:-1] if v is not None][-TRAILING_WINDOW:]
    assert len(prior_impacts) == TRAILING_WINDOW
    expected_cut = float(np.percentile(np.asarray(prior_impacts), 90.0, method=PERCENTILE_METHOD))
    assert frame.impact_proxy[-1] < expected_cut
    assert frame.state[-1] is False


def test_rv_bucket_boundaries_use_previous_window_only():
    from scripts.research.d7_bitmex_support_and_power_v0 import rv_bucket_from_trailing

    prior = [float(i) for i in range(TRAILING_WINDOW)]
    p25 = percentile(prior, 25.0)
    p50 = percentile(prior, 50.0)
    p75 = percentile(prior, 75.0)
    assert rv_bucket_from_trailing(p25, prior) == 0
    assert rv_bucket_from_trailing(p25 + 1e-9, prior) == 1
    assert rv_bucket_from_trailing(p50, prior) == 1
    assert rv_bucket_from_trailing(p75, prior) == 2
    assert rv_bucket_from_trailing(p75 + 1.0, prior) == 3
    base = 1_483_228_800_000
    hours = []
    for value in prior:
        close_px = 100.0 * __import__("math").exp(value / 1000.0)
        hours.append(_hour(base + len(hours) * HOUR_MS, open_px=100.0, close_px=close_px))
    probe = hours + [_hour(base + len(hours) * HOUR_MS, open_px=100.0, close_px=100.0 * __import__("math").exp(0.5))]
    frame = build_predictor_frame(probe)
    direct = rv_bucket_from_trailing(float(frame.ret_abs_1h[-1]), list(frame.ret_abs_1h[:-1]))
    assert int(frame.rv_bucket[-1]) == direct


def test_selector_digest_is_stable_and_stratum_counts_ignore_next_boolean():
    base = 1_483_228_800_000
    hours = []
    for i in range(TRAILING_WINDOW + 30):
        shock = 0.2 if i % 11 == 0 else 0.0
        close_px = 100.0 * __import__("math").exp(shock)
        year = 2017 if i < TRAILING_WINDOW + 15 else 2018
        hours.append(
            _hour(
                base + i * HOUR_MS,
                year=year,
                open_px=100.0,
                close_px=close_px,
                foreign=10.0 if i % 5 else 30.0,
            )
        )
    frame = build_predictor_frame(hours)
    first = support_from_frame(frame)
    second = support_from_frame(frame)
    assert first["SELECTOR_DIGEST"] == second["SELECTOR_DIGEST"]
    assert first["SELECTOR_DIGEST"] == d7_selector_digest([]) or len(first["SELECTOR_DIGEST"]) == 64
    flipped = list(frame.state)
    if len(flipped) > 2 and flipped[-1] is not None:
        flipped[-1] = not flipped[-1]
    frame.state = flipped
    changed = support_from_frame(frame)
    # Flipping only the last boolean cannot change the previous row's candidate
    # status. Eligible totals stay put because eligibility ignores the boolean.
    assert changed["TARGET_STRUCTURALLY_ELIGIBLE_ROWS"] == first["TARGET_STRUCTURALLY_ELIGIBLE_ROWS"]
    assert changed["ELIGIBLE_N_BY_YEAR_RV_BUCKET"] == first["ELIGIBLE_N_BY_YEAR_RV_BUCKET"]
    digest_rows = [(10, 2017, 1), (20, 2017, 2)]
    assert d7_selector_digest(digest_rows) == sprint.d7_selector_digest(digest_rows)


def test_structural_eligibility_does_not_read_state_boolean():
    starts = np.asarray([0, HOUR_MS, 3 * HOUR_MS], dtype=np.int64)
    defined = np.asarray([True, True, False])
    eligible = structural_target_eligible(starts, defined)
    assert eligible.tolist() == [True, False, False]
    # A hole at 2h removes eligibility of hour 1 even though hour 0's next exists.


def test_synthetic_power_is_reproducible_and_rejects_real_target_inputs():
    strata = [
        {"year": 2017, "rv_bucket": 0, "eligible_n": 40, "candidate_n": 8},
        {"year": 2017, "rv_bucket": 1, "eligible_n": 30, "candidate_n": 5},
    ]
    kwargs = {"fraction": 1.0, "seed": power_seed_for_fraction(1.0), "n_outer": 20, "n_inner": 30}
    a = synthetic_power(strata, **kwargs)
    b = synthetic_power(strata, **kwargs)
    assert a == b
    assert a["BITMEX_TPLUS1_USED"] is False
    assert a["TARGETS"] == "SYNTHETIC_BERNOULLI"
    assert a["P0"] == pytest.approx(0.09856569856985697)
    with pytest.raises(TypeError):
        synthetic_power(strata, target=[0, 1, 0], **kwargs)  # type: ignore[call-arg]


def test_wilson_and_decision_order_are_frozen():
    lo, hi = wilson_score_interval(80, 100)
    assert 0.7 < lo < 0.8 < hi < 0.9
    assert (
        feasibility_decision(
            identity_ok=False,
            independence_ok=True,
            control_ok=True,
            power_full=0.99,
            dependence_modification_required=False,
        )
        == "DATA_IDENTITY_INVALID"
    )
    assert (
        feasibility_decision(
            identity_ok=True,
            independence_ok=True,
            control_ok=True,
            power_full=0.99,
            dependence_modification_required=True,
        )
        == "INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW"
    )
    assert (
        feasibility_decision(
            identity_ok=True,
            independence_ok=True,
            control_ok=True,
            power_full=0.79,
            dependence_modification_required=False,
        )
        == "INFORMATIONALLY_WEAK"
    )
    assert (
        feasibility_decision(
            identity_ok=True,
            independence_ok=True,
            control_ok=False,
            power_full=0.99,
            dependence_modification_required=True,
        )
        == "CONTROL_SUPPORT_INSUFFICIENT"
    )


def test_render_has_closed_flags_and_no_selector_timestamps():
    payload = {
        "DATA_IDENTITY_STATUS": "PASS",
        "DATASET_ID": "D7_BITMEX_ACTIVITY_V0",
        "CANONICAL_GZ_SHA256": "abc",
        "D2_CANONICAL_GZ_SHA256": "def",
        "ACTIVITY_FIELD": "foreignNotional",
        "ACTIVITY_PORTABILITY_CLASS": "D7_ACTIVITY_SCIENTIFICALLY_COMPARABLE",
        "QUALITY": {
            "row_count": 1,
            "duplicate_timestamp_count": 0,
            "non_monotonic_steps": 0,
            "null_counts": {"open": 0, "high": 0, "low": 0, "close": 0, "foreignNotional": 0},
            "missing_buckets": 288,
            "missing_runs": [
                {
                    "first_missing_bucket_open": "2016-12-06T23:55:00.000Z",
                    "last_missing_bucket_open": "2016-12-07T23:50:00.000Z",
                    "half_open_interval_open_time": "[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)",
                }
            ],
            "first_open_time": "2016-05-13T11:55:00.000Z",
            "last_open_time": "2019-12-31T23:55:00.000Z",
        },
        "CONSTRUCTED_HOURS": 3,
        "VALID_IMPACT_ROWS": 2,
        "TARGET_STRUCTURALLY_ELIGIBLE_ROWS": 1,
        "STATE_N": 1,
        "STATE_N_BY_YEAR": {"2017": 1},
        "SELECTOR_N": 1,
        "SELECTOR_DIGEST": "digest",
        "CONTROL_SUPPORT": "CONTROL_SUPPORT_OK",
        "INDEPENDENCE_CLASS": "D7_TARGET_FRESH_ON_PREVIOUSLY_EXPOSED_MARKET_SURFACE",
        "POWER": {
            "POWER_FULL_EFFECT": 0.9,
            "POWER_FULL_EFFECT_95CI": [0.8, 0.95],
            "POWER_75PCT_EFFECT": 0.7,
            "POWER_75PCT_EFFECT_95CI": [0.6, 0.8],
            "POWER_50PCT_EFFECT": 0.4,
            "POWER_50PCT_EFFECT_95CI": [0.3, 0.5],
            "MC_REPLICATES": 1000,
            "POWER_SEED": 20260930171,
            "POWER_FULL_EFFECT_MEETS_BAR": True,
            "PRACTICAL_PASS_RATE_FULL_INFORMATIONAL": 1.0,
            "PRACTICAL_PASS_RATE_75PCT_INFORMATIONAL": 0.8,
            "PRACTICAL_PASS_RATE_50PCT_INFORMATIONAL": 0.0,
        },
        "DEPENDENCE_REVIEW_STATUS": "INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW",
        "DEPENDENCE_NOTE": "rolling windows overlap",
        "FEASIBILITY_DECISION": "INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW",
        "PRIMARY_BLOCKERS": ["dependence"],
        "NEXT_UNIT": "NONE",
    }
    text = render_markdown(payload)
    assert "D7_BITMEX_PRIMARY_TARGET_OPENED = false" in text
    assert "D7_BITMEX_EFFECT_COMPUTED = false" in text
    assert "D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false" in text
    assert "BINANCE_2025_OPENED = false" in text
    assert "BINANCE_2026_OPENED = false" in text
    assert "hour_start_ms" not in text


def test_committed_artifact_stays_outcome_closed():
    path = Path("docs/research/D7_BITMEX_SUPPORT_AND_POWER_V0.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["D7_BITMEX_PRIMARY_TARGET_OPENED"] is False
    assert payload["D7_BITMEX_EFFECT_COMPUTED"] is False
    assert payload["D7_BITMEX_REPLICATION_CLASS_ASSIGNED"] is False
    assert payload["BINANCE_2025_OPENED"] is False
    assert payload["BINANCE_2026_OPENED"] is False
    assert payload["CONFIRMATION_EXECUTED"] is False
    blob = json.dumps(payload)
    assert "hour_start_ms" not in blob
    assert "evaluate_d7_scientific" not in blob
    assert "construct_d7_scientific_arrays" not in blob
