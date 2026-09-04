"""Adversarial synthetic tests for the frozen B2-04 implementation.

These tests must not open real CORE parquet, create a production evidence
reservation, claim outcome access, or invoke run_development against real
market data. Synthetic fixtures only.

Test numbering follows the required adversarial matrix in the implementation
brief (1..60); each frozen contract clause is attacked rather than merely
demonstrated.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research import b2_04_moderate_pullback_structure as runner
from scripts.research import b2_04_moderate_pullback_structure_lib as lib
from scripts.research.lib.batch02_contracts import rolling_midrank_percentile
from scripts.research.lib.batch02_source_policy import validate_batch02_source_tree


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
PREREG_MD = REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md"
PREREG_JSON = REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _frame_1m_from_15m(closes15: np.ndarray) -> dict:
    """A 1m frame whose 15m aggregation reproduces `closes15` exactly."""
    closes15 = np.asarray(closes15, dtype=np.float64)
    close_1m = np.repeat(closes15, lib.HTF_MIN)
    n = len(close_1m)
    open_ms = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.BAR_MS
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "close": close_1m,
    }


def _event_closes(
    *,
    l_minutes: int,
    trend_log: float,
    path_logs: tuple[float, float, float, float],
    n_post: int = 12,
) -> tuple[np.ndarray, int]:
    """Build 15m closes containing exactly one designed pullback event.

    Layout (15m indices), with `base` chosen so the designed decision index
    is the FIRST index whose trend leg is defined and nonzero:

      [0, base]        flat at 100 (pre-jump)
      base+1 ...       plateau at 100*exp(trend_log) (the trend leg is one
                       jump, so TREND_RET_L is exactly zero at every earlier
                       decision index and no earlier bar can qualify)
      base+2..base+5   the four pullback path steps, as cumulative log
                       offsets relative to the path origin close(T-60m)
      tail             flat at the final path close

    T_index = base + 5, so close(T-P) = close[base+1] (the plateau/origin)
    and close(T-P-L) = close[base+1-l_step] = 100. Because every index below
    T_index has TREND_RET_L == 0, the designed event is the earliest
    qualifying event in its stream and refractory cannot suppress it.
    """
    l_step = int(l_minutes) // lib.HTF_MIN
    base = l_step + lib.REF_STEPS + 8
    origin_index = base + 1
    t_index = base + lib.P_STEPS + 1
    total = t_index + int(n_post) + 1
    closes = np.full(total, 100.0, dtype=np.float64)
    closes[base + 1:] = 100.0 * math.exp(float(trend_log))
    origin = float(closes[origin_index])
    for k, offset in enumerate(path_logs):
        closes[origin_index + 1 + k] = origin * math.exp(float(offset))
    closes[t_index + 1:] = float(closes[t_index])
    return closes, t_index


def _one_event(monkeypatch, *, l_minutes, trend_log, path_logs, ref_steps=8):
    monkeypatch.setattr(lib, "REF_STEPS", ref_steps)
    closes, t_index = _event_closes(
        l_minutes=l_minutes,
        trend_log=trend_log,
        path_logs=path_logs,
    )
    frame15 = lib.aggregate_1m_to_15m(_frame_1m_from_15m(closes))
    events = lib.construct_events(frame15)
    return frame15, events, t_index


def _stamp_records(events, frame15, H):
    """Deterministic score-record stub used by scoring/OLS/placebo tests."""
    del frame15
    out = []
    for event in events:
        record = dict(event)
        record["H"] = int(H)
        record["score_record_id"] = lib.canonical_score_record_id(
            str(record["base_event_id"]), int(H)
        )
        record["target_available"] = bool(math.isfinite(float(record.get("Y", np.nan))))
        record["scoreable"] = bool(
            record["target_available"] and bool(record.get("force_scoreable", True))
        )
        out.append(record)
    return out


def _synthetic_event(
    t_ms,
    *,
    L=240,
    direction="UP",
    depth=0.30,
    recovery=0.5,
    y=1.0,
    state=None,
    scoreable=True,
):
    d = lib.DIR_UP if direction == "UP" else lib.DIR_DOWN
    return {
        "L": int(L),
        "T": int(t_ms),
        "index": 0,
        "d": int(d),
        "direction": direction,
        "trend_ret": 0.05 * d,
        "abs_trend": 0.05,
        "trend_standing": 0.9,
        "signed_pb_ret": -depth * 0.05,
        "final_depth": float(depth),
        "base_event_id": lib.canonical_base_event_id(
            L=int(L), direction=direction, T_ms=int(t_ms)
        ),
        "warmup_only": False,
        "recovery_available": True,
        "recovery_fraction": float(recovery),
        "max_adverse": float(depth) / max(1.0 - float(recovery), 1e-9),
        "structure_state": state,
        "structure_standing": 0.6 if state == lib.STATE_HIGH else 0.4,
        "Y": float(y),
        "force_scoreable": bool(scoreable),
    }


# ---------------------------------------------------------------------------
# 1-5: event construction
# ---------------------------------------------------------------------------
def test_01_up_event_construction(monkeypatch):
    trend = 0.10
    depth = 0.30
    path = (-0.02 * trend, -0.45 * trend, -0.35 * trend, -depth * trend)
    frame15, events, t_index = _one_event(
        monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
    )
    designed = [e for e in events if int(e["index"]) == t_index and int(e["L"]) == 240]
    assert len(designed) == 1
    event = designed[0]
    assert event["direction"] == "UP"
    assert event["d"] == lib.DIR_UP
    assert event["trend_ret"] == pytest.approx(trend)
    assert event["signed_pb_ret"] == pytest.approx(-depth * trend)
    assert event["final_depth"] == pytest.approx(depth)
    assert lib.MODERATE_LO <= event["final_depth"] < lib.MODERATE_HI


def test_02_down_event_construction(monkeypatch):
    trend = -0.10
    depth = 0.30
    path = (0.02 * -trend, 0.45 * -trend, 0.35 * -trend, depth * -trend)
    frame15, events, t_index = _one_event(
        monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
    )
    designed = [e for e in events if int(e["index"]) == t_index and int(e["L"]) == 240]
    assert len(designed) == 1
    event = designed[0]
    assert event["direction"] == "DOWN"
    assert event["d"] == lib.DIR_DOWN
    assert event["signed_pb_ret"] < 0.0
    assert event["final_depth"] == pytest.approx(depth)


def test_03_exact_moderate_lower_bound_is_accepted(monkeypatch):
    trend = 0.10
    path = (-0.01 * trend, -0.30 * trend, -0.28 * trend, -lib.MODERATE_LO * trend)
    frame15, events, t_index = _one_event(
        monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
    )
    designed = [e for e in events if int(e["index"]) == t_index]
    assert len(designed) == 1
    assert designed[0]["final_depth"] == pytest.approx(lib.MODERATE_LO)


def test_04_exact_moderate_upper_bound_is_rejected(monkeypatch):
    trend = 0.10
    path = (-0.01 * trend, -0.45 * trend, -0.42 * trend, -lib.MODERATE_HI * trend)
    frame15, events, t_index = _one_event(
        monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
    )
    assert [e for e in events if int(e["index"]) == t_index] == []


def test_05_zero_trend_is_rejected(monkeypatch):
    monkeypatch.setattr(lib, "REF_STEPS", 8)
    closes = np.full(120, 100.0, dtype=np.float64)
    closes[60] = 99.0  # a pullback with an exactly-zero trend leg
    frame15 = lib.aggregate_1m_to_15m(_frame_1m_from_15m(closes))
    events = lib.construct_events(frame15)
    trend = lib.trend_returns(frame15["close"], 240)
    assert np.any(trend == 0.0)
    assert all(float(e["trend_ret"]) != 0.0 for e in events)


# ---------------------------------------------------------------------------
# 6-10: recovery descriptor
# ---------------------------------------------------------------------------
def _descriptor(path_logs, d, abs_trend):
    origin = 100.0
    closes = np.array(
        [origin] + [origin * math.exp(float(v)) for v in path_logs],
        dtype=np.float64,
    )
    return lib.recovery_descriptor(closes, len(closes) - 1, d, abs_trend)


def test_06_recovery_up_formula_matches_hand_arithmetic():
    trend = 0.10
    path = (-0.02, -0.05, -0.04, -0.03)
    got = _descriptor(path, lib.DIR_UP, trend)
    adverse = [-1.0 * v / trend for v in path]
    assert got is not None
    assert got["adverse_path"] == pytest.approx(adverse)
    assert got["max_adverse"] == pytest.approx(max(adverse))
    assert got["path_final_depth"] == pytest.approx(adverse[-1])
    assert got["recovery_fraction"] == pytest.approx(
        (max(adverse) - adverse[-1]) / max(adverse)
    )
    assert got["recovery_fraction"] == pytest.approx(1.0 - adverse[-1] / max(adverse))


def test_07_recovery_down_formula_matches_hand_arithmetic():
    trend = 0.10
    path = (0.02, 0.05, 0.04, 0.03)
    got = _descriptor(path, lib.DIR_DOWN, trend)
    adverse = [1.0 * v / trend for v in path]
    assert got is not None
    assert got["adverse_path"] == pytest.approx(adverse)
    assert got["recovery_fraction"] == pytest.approx(
        (max(adverse) - adverse[-1]) / max(adverse)
    )


def test_08_recovery_is_zero_when_final_point_is_deepest():
    trend = 0.10
    path = (-0.01, -0.02, -0.025, -0.03)
    got = _descriptor(path, lib.DIR_UP, trend)
    assert got is not None
    assert got["recovery_fraction"] == pytest.approx(0.0)
    assert got["max_adverse"] == pytest.approx(got["path_final_depth"])


def test_09_positive_recovery_after_deeper_earlier_excursion():
    trend = 0.10
    path = (-0.02, -0.06, -0.05, -0.03)
    got = _descriptor(path, lib.DIR_UP, trend)
    assert got is not None
    assert got["max_adverse"] == pytest.approx(0.6)
    assert got["path_final_depth"] == pytest.approx(0.3)
    assert got["recovery_fraction"] == pytest.approx(0.5)
    assert 0.0 <= got["recovery_fraction"] <= 1.0


def test_10_final_depth_equals_h04_pullback_depth(monkeypatch):
    for trend, sign in ((0.10, 1), (-0.10, -1)):
        depth = 0.32
        path = tuple(
            sign * v for v in (-0.02 * abs(trend), -0.5 * abs(trend), -0.4 * abs(trend), -depth * abs(trend))
        )
        frame15, events, t_index = _one_event(
            monkeypatch, l_minutes=480, trend_log=trend, path_logs=path
        )
        # the same T legitimately produces an independent event per L: there
        # is no cross-L refractory, so select the designed L explicitly.
        designed = [
            e for e in events if int(e["index"]) == t_index and int(e["L"]) == 480
        ]
        assert len(designed) == 1
        attached = lib.attach_recovery(designed, frame15)[0]
        descriptor = lib.recovery_descriptor(
            frame15["close"],
            t_index,
            int(attached["d"]),
            float(attached["abs_trend"]),
        )
        # Independent H04 depth from the frozen construction formula.
        close = frame15["close"]
        d = int(attached["d"])
        h04_depth = -(
            d * math.log(float(close[t_index]) / float(close[t_index - lib.P_STEPS]))
        ) / abs(float(attached["trend_ret"]))
        assert descriptor["path_final_depth"] == pytest.approx(h04_depth, abs=1e-12)
        assert attached["final_depth"] == pytest.approx(h04_depth, abs=1e-12)


# ---------------------------------------------------------------------------
# 11-15: lifecycle isolation
# ---------------------------------------------------------------------------
def test_11_malformed_recovery_preserves_the_base_event(monkeypatch):
    trend = 0.10
    depth = 0.30
    path = (-0.02 * trend, -0.45 * trend, -0.35 * trend, -depth * trend)
    frame15, events, t_index = _one_event(
        monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
    )
    assert events
    monkeypatch.setattr(lib, "recovery_descriptor", lambda *a, **k: None)
    attached = lib.attach_recovery(events, frame15)
    assert len(attached) == len(events)
    assert all(e["recovery_available"] is False for e in attached)
    assert all(math.isnan(float(e["recovery_fraction"])) for e in attached)
    assert [e["base_event_id"] for e in attached] == [
        e["base_event_id"] for e in events
    ]


def test_12_malformed_recovery_cannot_resurrect_a_suppressed_event():
    t0 = lib.DEV_START_MS
    stream = [
        {"L": 240, "T": t0, "tag": "winner"},
        {"L": 240, "T": t0 + 15 * lib.BAR_MS, "tag": "suppressed"},
        {"L": 240, "T": t0 + 60 * lib.BAR_MS, "tag": "next"},
    ]
    kept = lib.apply_refractory(stream)
    assert [e["tag"] for e in kept] == ["winner", "next"]
    # Recovery availability is not an input to apply_refractory at all: the
    # same stream with every recovery flag flipped yields the same winners.
    flipped = [dict(e, recovery_available=False, recovery_fraction=float("nan")) for e in stream]
    assert [e["tag"] for e in lib.apply_refractory(flipped)] == ["winner", "next"]


def test_13_recovery_cannot_affect_event_qualification(monkeypatch):
    trend = 0.10
    depth = 0.30
    shallow_path = (-0.01 * trend, -0.31 * trend, -0.30 * trend, -depth * trend)
    deep_path = (-0.01 * trend, -0.90 * trend, -0.60 * trend, -depth * trend)
    ids = []
    for path in (shallow_path, deep_path):
        frame15, events, t_index = _one_event(
            monkeypatch, l_minutes=240, trend_log=trend, path_logs=path
        )
        designed = [e for e in events if int(e["index"]) == t_index]
        assert len(designed) == 1
        attached = lib.attach_recovery(designed, frame15)[0]
        ids.append((attached["base_event_id"], attached["final_depth"]))
        assert attached["recovery_available"] is True
    # Very different recovery, identical construction identity and depth.
    assert ids[0][0] == ids[1][0]
    assert ids[0][1] == pytest.approx(ids[1][1])


def test_14_horizon_cannot_affect_refractory():
    t0 = lib.DEV_START_MS
    stream = [{"L": 240, "T": t0 + k * 15 * lib.BAR_MS} for k in range(9)]
    kept = [int(e["T"]) for e in lib.apply_refractory(stream)]
    assert kept == [t0, t0 + 60 * lib.BAR_MS, t0 + 120 * lib.BAR_MS]
    # H is not an argument and no post-construction field is read: the
    # executable body (docstring stripped) may only touch "T".
    import ast

    tree = ast.parse(Path(lib.__file__).read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "apply_refractory"
    )
    arg_names = {a.arg for a in function.args.args} | {
        a.arg for a in function.args.kwonlyargs
    }
    assert arg_names == {"stream", "refractory_ms"}
    docstring_node = (
        function.body[0].value
        if isinstance(function.body[0], ast.Expr)
        and isinstance(function.body[0].value, ast.Constant)
        else None
    )
    constants = {
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node is not docstring_node
    }
    assert constants == {"T"}
    # identical stream, every horizon-derived field flipped -> same winners
    for H in lib.H_VALUES:
        decorated = [dict(e, H=H, Y=float(H), target_available=False) for e in stream]
        assert [int(e["T"]) for e in lib.apply_refractory(decorated)] == kept


def test_15_target_availability_cannot_affect_refractory():
    t0 = lib.DEV_START_MS
    stream = [
        {"L": 960, "T": t0, "target_available": False},
        {"L": 960, "T": t0 + 30 * lib.BAR_MS, "target_available": True},
        {"L": 960, "T": t0 + 61 * lib.BAR_MS, "target_available": True},
    ]
    kept = lib.apply_refractory(stream)
    assert [int(e["T"]) for e in kept] == [t0, t0 + 61 * lib.BAR_MS]


# ---------------------------------------------------------------------------
# 16-20: identity and chronology
# ---------------------------------------------------------------------------
def test_16_canonical_base_id_is_exact():
    t = 1_580_600_000_000 - (1_580_600_000_000 % lib.HTF_MS)
    got = lib.canonical_base_event_id(L=480, direction="UP", T_ms=t)
    want = "|".join(
        [
            lib.REQUIRED_SNAPSHOT,
            "1m",
            "15m",
            "15m",
            "480",
            "UP",
            str(t - 60 * lib.BAR_MS),
            str(t),
        ]
    )
    assert got == want
    assert " " not in got and '"' not in got
    assert got.count("|") == 7
    with pytest.raises(lib.B204Error):
        lib.canonical_base_event_id(L=480, direction="up", T_ms=t)


def test_17_canonical_score_id_is_exact():
    t = 1_580_600_000_000 - (1_580_600_000_000 % lib.HTF_MS)
    base = lib.canonical_base_event_id(L=960, direction="DOWN", T_ms=t)
    got = lib.canonical_score_record_id(base, 120)
    assert got == base + "|120"
    assert got.count("|") == 8
    with pytest.raises(lib.B204Error):
        lib.canonical_score_record_id(base, 45)


def test_18_no_t_only_deduplication():
    t = 1_580_600_000_000 - (1_580_600_000_000 % lib.HTF_MS)
    ids = {
        lib.canonical_base_event_id(L=L, direction=direction, T_ms=t)
        for L in lib.L_VALUES
        for direction in ("UP", "DOWN")
    }
    assert len(ids) == 6
    # cross-L refractory must not exist: same T at three L values all survive
    stream_by_l = {
        L: lib.apply_refractory([{"L": L, "T": t}]) for L in lib.L_VALUES
    }
    assert all(len(v) == 1 for v in stream_by_l.values())


def test_19_strict_last_legal_t_for_every_horizon():
    frozen = {
        15: "2024-12-31T23:30:00Z",
        30: "2024-12-31T23:15:00Z",
        60: "2024-12-31T22:45:00Z",
        120: "2024-12-31T21:45:00Z",
        240: "2024-12-31T19:45:00Z",
    }
    for H, iso in frozen.items():
        want = int(
            datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
        )
        got = lib.last_legal_t_ms(H)
        assert got == want
        assert got % lib.HTF_MS == 0
        assert got + H * lib.BAR_MS < lib.DEV_END_MS
        assert (got + lib.HTF_MS) + H * lib.BAR_MS >= lib.DEV_END_MS
        assert lib.scoring_eligible(got, H) is True
        assert lib.scoring_eligible(got + lib.HTF_MS, H) is False


def test_20_t_plus_h_equality_with_2025_is_rejected():
    for H in lib.H_VALUES:
        boundary_t = lib.DEV_END_MS - H * lib.BAR_MS
        assert boundary_t % lib.HTF_MS == 0
        assert lib.scoring_eligible(boundary_t, H) is False
        assert lib.scoring_eligible(boundary_t - lib.HTF_MS, H) is True


# ---------------------------------------------------------------------------
# 21-23: causal references
# ---------------------------------------------------------------------------
def test_21_trend_standing_is_causal_and_matches_an_independent_midrank():
    rng = np.random.default_rng(5)
    values = rng.normal(size=400)
    window = 20
    got = rolling_midrank_percentile(values, window=window)

    def oracle(i):
        if i < window:
            return None
        ref = values[i - window: i]
        x = values[i]
        return (
            float(np.sum(ref < x)) + 0.5 * float(np.sum(ref == x))
        ) / float(window)

    for i in range(len(values)):
        want = oracle(i)
        if want is None:
            assert math.isnan(float(got[i]))
        else:
            assert float(got[i]) == pytest.approx(want)
    # current record never enters its own reference
    constant = np.full(50, 3.0)
    scores = rolling_midrank_percentile(constant, window=window)
    assert float(scores[window]) == pytest.approx(0.5)


def test_21b_fixed_count_and_time_window_agree_on_the_trend_series():
    """The frozen text says "preceding 30 calendar days"; H04 froze that as a
    fixed count of 15m steps. On the contiguous grid the two canonical modes
    are the same reference set, and on a real ABS_TREND series (which always
    carries a leading NaN prefix of length P_STEPS + L/15) their finite masks
    are identical as well, so the choice of mode is mechanical."""
    rng = np.random.default_rng(9)
    n = 600
    window = 96
    times = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.HTF_MS

    values = rng.normal(size=n)
    fixed = rolling_midrank_percentile(values, window=window)
    timed = rolling_midrank_percentile(
        values, timestamps_ms=times, lookback_ms=window * lib.HTF_MS
    )
    both = np.isfinite(fixed) & np.isfinite(timed)
    assert both.sum() > 0
    assert np.allclose(fixed[both], timed[both])
    # Wherever the fixed-count window is full, the two modes are identical.
    assert np.all(np.isfinite(timed[np.isfinite(fixed)]))

    # An ABS_TREND-shaped series: the leading NaN prefix poisons both modes
    # over exactly the same span, so the finite masks coincide exactly.
    trendish = values.copy()
    trendish[: lib.P_STEPS + 16] = np.nan
    fixed_t = rolling_midrank_percentile(trendish, window=window)
    timed_t = rolling_midrank_percentile(
        trendish, timestamps_ms=times, lookback_ms=window * lib.HTF_MS
    )
    assert np.array_equal(np.isfinite(fixed_t), np.isfinite(timed_t))
    mask = np.isfinite(fixed_t)
    assert mask.sum() > 0
    assert np.allclose(fixed_t[mask], timed_t[mask])


def test_22_target_scale_is_causal_and_matches_an_independent_median():
    rng = np.random.default_rng(3)
    n = 300
    abs_ret = np.abs(rng.normal(size=n)) + 0.01
    H = 60
    h_steps = H // lib.HTF_MIN
    ref_steps = 40
    original = lib.REF_STEPS
    try:
        lib.REF_STEPS = ref_steps
        got = lib.past_median_abs_return(abs_ret, H)
    finally:
        lib.REF_STEPS = original
    span = ref_steps - h_steps + 1
    for i in range(n):
        lo = i - ref_steps
        hi = i - h_steps
        if lo < 0 or hi < lo or (hi - lo + 1) != span:
            continue
        want = float(np.median(abs_ret[lo: hi + 1]))
        assert float(got[i]) == pytest.approx(want)


def test_23_scale_reference_requires_ref_t_plus_h_le_t():
    """Independent-oracle attack on the frozen `ref_t + H <= T` boundary.

    A strictly monotonic reference series is required: on an all-equal
    fixture, whether the boundary element is included or excluded cannot be
    observed in the resulting median at all, so that shape of fixture cannot
    prove anything about `<=` vs `<`. Here every window element is distinct,
    so dropping or keeping exactly one boundary element provably changes the
    median, and the test is written to fail if the implementation's `<=`
    ever regresses to `<`.
    """
    n = 200
    H = 60
    h_steps = H // lib.HTF_MIN
    ref_steps = 40
    span = ref_steps - h_steps + 1
    assert span >= 2  # otherwise a single-element median can't expose the bug

    values = np.arange(n, dtype=np.float64)  # strictly monotonic
    target = 100

    original = lib.REF_STEPS
    try:
        lib.REF_STEPS = ref_steps
        got = lib.past_median_abs_return(values, H)
    finally:
        lib.REF_STEPS = original

    # Independent oracle: the frozen reference window is exactly
    # values[target-REF_STEPS : target-h_steps+1] (Python slice, i.e. the
    # last legal reference index target-h_steps IS included -- ref_t+H==T).
    lo = target - ref_steps
    hi_inclusive = target - h_steps  # last legal reference index
    oracle_slice = values[lo: hi_inclusive + 1]
    assert len(oracle_slice) == span
    correct_oracle = float(np.median(oracle_slice))
    assert float(got[target]) == pytest.approx(correct_oracle)

    # Intentionally wrong oracle that excludes the equality-boundary element
    # (as a `<` implementation would): must disagree with both the real
    # implementation and the correct oracle, proving the boundary element is
    # load-bearing on this monotonic fixture.
    wrong_oracle_slice = values[lo:hi_inclusive]  # drops index hi_inclusive
    assert len(wrong_oracle_slice) == span - 1
    wrong_oracle = float(np.median(wrong_oracle_slice))
    assert wrong_oracle != pytest.approx(correct_oracle)
    assert float(got[target]) != pytest.approx(wrong_oracle)

    # ref_t + H > T (one grid step beyond the boundary) must be excluded:
    # corrupting only that element must not move the result at all.
    poisoned = values.copy()
    poisoned[hi_inclusive + 1] = 10_000.0  # first index NOT known by T
    original = lib.REF_STEPS
    try:
        lib.REF_STEPS = ref_steps
        dirty = lib.past_median_abs_return(poisoned, H)
    finally:
        lib.REF_STEPS = original
    assert float(dirty[target]) == pytest.approx(correct_oracle)

    # Corrupting the boundary element itself (ref_t + H == T) MUST move the
    # result, proving it is genuinely a member of the reference set. The
    # window is strictly increasing, so the boundary element is the window's
    # maximum: pushing it further up would not move an odd-length median at
    # all, so it must be pushed BELOW the median to be observable.
    poisoned_boundary = values.copy()
    poisoned_boundary[hi_inclusive] = -10_000.0
    original = lib.REF_STEPS
    try:
        lib.REF_STEPS = ref_steps
        boundary_dirty = lib.past_median_abs_return(poisoned_boundary, H)
    finally:
        lib.REF_STEPS = original
    assert float(boundary_dirty[target]) != pytest.approx(correct_oracle)


# ---------------------------------------------------------------------------
# 24-27: causal training pool
# ---------------------------------------------------------------------------
def _cell_with(monkeypatch, events, *, L=240, H=60, min_train=3, n_placebo=2, n_boot=8):
    monkeypatch.setattr(lib, "build_score_records", _stamp_records)
    monkeypatch.setattr(lib, "MIN_TRAIN_COUNT", min_train)
    monkeypatch.setattr(lib, "N_PLACEBO", n_placebo)
    monkeypatch.setattr(lib, "N_BOOT", n_boot)
    return lib.evaluate_cell(events, {"t_ms": np.zeros(1), "close": np.ones(1)}, L, H)


def test_24_training_history_is_limited_to_365_days(monkeypatch):
    monkeypatch.setattr(lib, "TRAIN_MS", 10 * lib.DAY_MS)
    t0 = lib.DEV_START_MS + 400 * lib.DAY_MS
    events = []
    # stale records far outside the training window
    for k in range(40):
        events.append(
            _synthetic_event(
                t0 - 200 * lib.DAY_MS + k * lib.HOUR_MS if hasattr(lib, "HOUR_MS")
                else t0 - 200 * lib.DAY_MS + k * 60 * lib.BAR_MS,
                depth=0.30 + 0.0001 * k,
                recovery=0.1 * (k % 5),
                y=float(k % 3),
                scoreable=False,
            )
        )
    for k in range(40):
        events.append(
            _synthetic_event(
                t0 + k * 3 * 60 * lib.BAR_MS,
                depth=0.26 + 0.001 * k,
                recovery=0.05 * (k % 7),
                y=float((k % 4) - 1),
            )
        )
    cell = _cell_with(monkeypatch, events, min_train=5)
    assert cell["N"] > 0
    for record in cell["scored"]:
        assert record["training_count"] <= 40


def test_25_training_requires_training_t_plus_h_le_current_t(monkeypatch):
    H = 60
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = [
        _synthetic_event(t0 + k * h_ms, depth=0.26 + 0.002 * k, recovery=0.1 * (k % 6), y=float(k % 3))
        for k in range(12)
    ]
    cell = _cell_with(monkeypatch, events, H=H, min_train=2)
    assert cell["scored"]
    first = cell["scored"][0]
    # earliest scored record admits exactly the records matured by T
    assert first["training_count"] >= 2
    for record in cell["scored"]:
        current_t = int(record["T"])
        matured = [
            e for e in events
            if int(e["T"]) + h_ms <= current_t
            and str(e["direction"]) == str(record["direction"])
            and int(e["T"]) >= current_t - lib.TRAIN_MS
        ]
        assert record["training_count"] == len(matured)


def test_26_training_pool_is_same_l_and_same_direction(monkeypatch):
    H = 60
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = []
    for k in range(20):
        events.append(
            _synthetic_event(
                t0 + k * h_ms, direction="UP",
                depth=0.26 + 0.002 * k, recovery=0.05 * (k % 8), y=float(k % 3),
            )
        )
    for k in range(20):
        events.append(
            _synthetic_event(
                t0 + (k + 30) * h_ms, direction="DOWN",
                depth=0.26 + 0.002 * k, recovery=0.05 * (k % 8), y=float(k % 3),
            )
        )
    cell = _cell_with(monkeypatch, events, H=H, min_train=3)
    for record in cell["scored"]:
        current_t = int(record["T"])
        same_side = [
            e for e in events
            if str(e["direction"]) == str(record["direction"])
            and int(e["T"]) + h_ms <= current_t
            and int(e["T"]) >= current_t - lib.TRAIN_MS
        ]
        assert record["training_count"] == len(same_side)


def test_27_shared_minimum_training_count_is_thirty(monkeypatch):
    assert lib.MIN_TRAIN_COUNT == 30
    H = 60
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = [
        _synthetic_event(t0 + k * h_ms, depth=0.26 + 0.002 * k, recovery=0.05 * k, y=float(k % 3))
        for k in range(40)
    ]
    monkeypatch.setattr(lib, "build_score_records", _stamp_records)
    monkeypatch.setattr(lib, "N_PLACEBO", 2)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    frame = {"t_ms": np.zeros(1), "close": np.ones(1)}
    cell = lib.evaluate_cell(events, frame, 240, H)
    assert all(r["training_count"] >= 30 for r in cell["scored"])
    monkeypatch.setattr(lib, "MIN_TRAIN_COUNT", 1000)
    empty = lib.evaluate_cell(events, frame, 240, H)
    assert empty["N"] == 0
    assert empty["per_cell_conditions"]["primary_positive"] is False


# ---------------------------------------------------------------------------
# 28-35: OLS contract
# ---------------------------------------------------------------------------
def test_28_baseline_design_matrix_is_exact():
    depth = np.array([0.25, 0.30, 0.35], dtype=np.float64)
    design = lib._baseline_design(depth)
    assert design.shape == (3, 2)
    assert np.array_equal(design[:, 0], np.ones(3))
    assert np.array_equal(design[:, 1], depth)


def test_29_candidate_design_matrix_is_exact():
    depth = np.array([0.25, 0.30, 0.35], dtype=np.float64)
    recovery = np.array([0.1, 0.5, 0.9], dtype=np.float64)
    design = lib._candidate_design(depth, recovery)
    assert design.shape == (3, 3)
    assert np.array_equal(design[:, 0], np.ones(3))
    assert np.array_equal(design[:, 1], depth)
    assert np.array_equal(design[:, 2], recovery)


def test_30_recovery_is_the_only_model_increment():
    rng = np.random.default_rng(17)
    depth = rng.uniform(0.25, 0.40, size=60)
    recovery = rng.uniform(0.0, 1.0, size=60)
    y = 0.4 + 1.3 * depth - 0.7 * recovery + rng.normal(scale=1e-9, size=60)
    base = lib.ols_fit(lib._baseline_design(depth), y)
    cand = lib.ols_fit(lib._candidate_design(depth, recovery), y)
    assert base is not None and cand is not None
    assert len(base) == 2 and len(cand) == 3
    assert cand[0] == pytest.approx(0.4, abs=1e-6)
    assert cand[1] == pytest.approx(1.3, abs=1e-6)
    assert cand[2] == pytest.approx(-0.7, abs=1e-6)
    # candidate design differs from baseline in exactly one column
    cand_design = lib._candidate_design(depth, recovery)
    base_design = lib._baseline_design(depth)
    assert np.array_equal(cand_design[:, :2], base_design)


def test_30b_ols_matches_an_independent_least_squares_path():
    """The Cholesky rank test plus LU solve must agree with a wholly
    different solver on well-posed designs (no pseudoinverse required)."""
    rng = np.random.default_rng(4)
    worst = 0.0
    for _ in range(120):
        n = int(rng.integers(30, 200))
        depth = rng.uniform(0.25, 0.40, size=n)
        recovery = rng.uniform(0.0, 1.0, size=n)
        y = rng.normal(size=n)
        design = lib._candidate_design(depth, recovery)
        got = lib.ols_fit(design, y)
        assert got is not None
        reference, *_ = np.linalg.lstsq(design, y, rcond=None)
        worst = max(worst, float(np.max(np.abs(got - reference))))
    assert worst < 1e-8


def test_36b_structure_state_cannot_change_scored_support(monkeypatch):
    """RECOVERY_STATE is gate-only: stripping it must leave support, event
    identities and every AE metric bit-identical."""
    events = _placebo_events(n=30)
    with_state = [
        dict(e, structure_state=(lib.STATE_HIGH if k % 2 else lib.STATE_LOW))
        for k, e in enumerate(events)
    ]
    without_state = [dict(e, structure_state=None) for e in events]
    first = _cell_with(monkeypatch, with_state, H=60, min_train=3)
    second = _cell_with(monkeypatch, without_state, H=60, min_train=3)
    assert first["N"] == second["N"] > 0
    assert first["score_record_ids"] == second["score_record_ids"]
    assert first["mean_ae_improvement"] == second["mean_ae_improvement"]
    assert first["relative_mae_improvement"] == second["relative_mae_improvement"]
    assert first["placebo_q95"] == second["placebo_q95"]
    # only the ordering diagnostic reacts to the state
    assert second["structure_separation_pooled"] is None
    assert second["per_cell_conditions"]["structure_ordering"] is False


def test_31_candidate_and_baseline_share_support(monkeypatch):
    H = 60
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = []
    for k in range(30):
        events.append(
            _synthetic_event(t0 + k * h_ms, direction="UP", depth=0.26 + 0.003 * k,
                             recovery=0.03 * k, y=float(k % 5))
        )
        events.append(
            _synthetic_event(t0 + k * h_ms + h_ms // 2, direction="DOWN",
                             depth=0.26 + 0.003 * k, recovery=0.03 * ((k + 3) % 10),
                             y=float((k + 1) % 5))
        )
    cell = _cell_with(monkeypatch, events, H=H, min_train=3)
    assert cell["N"] > 0
    ids = cell["score_record_ids"]
    assert len(set(ids)) == len(ids)
    for record in cell["scored"]:
        assert math.isfinite(float(record["base_pred"]))
        assert math.isfinite(float(record["candidate_pred"]))
        assert record["score_record_id"] == lib.canonical_score_record_id(
            record["base_event_id"], H
        )
    assert cell["same_support"]["score_record_count"] == len(ids)
    assert cell["same_support"]["score_record_digest_sha256"] == hashlib.sha256(
        "\n".join(ids).encode("utf-8")
    ).hexdigest()


def test_32_singular_baseline_fails_closed():
    depth = np.full(50, 0.30, dtype=np.float64)  # constant -> rank deficient
    y = np.arange(50, dtype=np.float64)
    assert lib.ols_fit(lib._baseline_design(depth), y) is None


def test_33_singular_candidate_fails_closed():
    rng = np.random.default_rng(21)
    depth = rng.uniform(0.25, 0.40, size=50)
    recovery = 2.0 * depth  # perfectly collinear with depth
    y = rng.normal(size=50)
    assert lib.ols_fit(lib._baseline_design(depth), y) is not None
    assert lib.ols_fit(lib._candidate_design(depth, recovery), y) is None


def test_33b_singular_candidate_removes_the_record_from_both_models(monkeypatch):
    H = 60
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    # recovery constant -> candidate rank deficient, baseline well posed
    events = [
        _synthetic_event(t0 + k * h_ms, depth=0.26 + 0.003 * k, recovery=0.5, y=float(k % 5))
        for k in range(20)
    ]
    cell = _cell_with(monkeypatch, events, H=H, min_train=3)
    assert cell["N"] == 0
    assert cell["score_record_ids"] == []


def test_34_no_pseudoinverse_in_source():
    source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "pinv" not in source
    assert "lstsq" not in source
    assert "np.linalg.cholesky" in source


def test_35_nonfinite_inputs_fail_closed():
    depth = np.array([0.25, 0.30, 0.35, 0.28] * 10, dtype=np.float64)
    y = np.arange(40, dtype=np.float64)
    bad_y = y.copy()
    bad_y[3] = np.nan
    assert lib.ols_fit(lib._baseline_design(depth), bad_y) is None
    bad_depth = depth.copy()
    bad_depth[2] = np.inf
    assert lib.ols_fit(lib._baseline_design(bad_depth), y) is None
    assert lib.ols_fit(np.zeros((2, 3)), np.zeros(2)) is None


# ---------------------------------------------------------------------------
# 36-37: recovery state is gate-only
# ---------------------------------------------------------------------------
def test_36_recovery_state_never_enters_the_ols_design():
    source = Path(lib.__file__).read_text(encoding="utf-8")
    candidate_body = source.split("def _candidate_design(", 1)[1].split("\ndef ", 1)[0]
    assert "structure_state" not in candidate_body
    assert "STATE_HIGH" not in candidate_body
    cell_body = source.split("def evaluate_cell(", 1)[1].split("\ndef ", 1)[0]
    assert "_candidate_design(pool_depth, pool_recovery)" in cell_body
    assert "structure_state" not in cell_body


def test_37_recovery_state_midrank_excludes_the_current_event():
    t0 = lib.DEV_START_MS
    events = [
        _synthetic_event(t0 + k * 2 * 60 * lib.BAR_MS, recovery=0.1 * k)
        for k in range(6)
    ]
    stated = lib.attach_structure_state(events)
    assert stated[0]["structure_state"] is None  # no prior reference
    assert math.isnan(float(stated[0]["structure_standing"]))
    # strictly increasing recovery -> every later event ranks at the top
    for record in stated[1:]:
        assert record["structure_standing"] == pytest.approx(1.0)
        assert record["structure_state"] == lib.STATE_HIGH
    # state assignment does not change population size or identity
    assert [e["base_event_id"] for e in stated] == [e["base_event_id"] for e in events]


# ---------------------------------------------------------------------------
# 38-42: placebo
# ---------------------------------------------------------------------------
def _placebo_events(n=24, H=60):
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    return [
        _synthetic_event(
            t0 + k * h_ms,
            depth=0.26 + 0.004 * k,
            recovery=(k * 0.037) % 1.0,
            y=float((k % 7) - 3),
        )
        for k in range(n)
    ]


def _single_event_cell(monkeypatch, *, n_train=30, H=60, n_placebo=1):
    """One scoreable event on top of exactly `n_train` matured training rows."""
    h_ms = H * lib.BAR_MS
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = [
        _synthetic_event(
            t0 + k * h_ms,
            depth=0.26 + 0.0031 * k,
            recovery=(0.0417 * k) % 1.0,
            y=float(((k * 7) % 11) - 5),
            scoreable=False,
        )
        for k in range(n_train)
    ]
    evaluation = _synthetic_event(
        t0 + n_train * h_ms,
        depth=0.331,
        recovery=0.734,
        y=2.25,
        scoreable=True,
    )
    events.append(evaluation)
    monkeypatch.setattr(lib, "build_score_records", _stamp_records)
    monkeypatch.setattr(lib, "MIN_TRAIN_COUNT", n_train)
    monkeypatch.setattr(lib, "N_PLACEBO", n_placebo)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    cell = lib.evaluate_cell(
        events, {"t_ms": np.zeros(1), "close": np.ones(1)}, 240, H
    )
    return cell, events[:n_train], evaluation


def _independent_ols(design, target):
    """Reference solver that shares no code path with lib.ols_fit."""
    beta, *_ = np.linalg.lstsq(
        np.asarray(design, dtype=np.float64),
        np.asarray(target, dtype=np.float64),
        rcond=None,
    )
    return beta


def test_38_39_40_41_42_placebo_matches_an_independent_oracle(monkeypatch):
    """38 depth fixed, 39 Y fixed, 40 recovery-only permutation, 41
    determinism, 42 canonical ordering -- all pinned by a from-scratch
    oracle rather than by observing the implementation."""
    H = 60
    cell, training, evaluation = _single_event_cell(monkeypatch, H=H, n_placebo=1)
    assert cell["N"] == 1
    record = cell["scored"][0]
    assert record["training_count"] == len(training)

    ordered = sorted(
        training,
        key=lambda item: lib.canonical_score_record_id(item["base_event_id"], H),
    )
    depth = np.asarray([e["final_depth"] for e in ordered], dtype=np.float64)
    recovery = np.asarray([e["recovery_fraction"] for e in ordered], dtype=np.float64)
    y = np.asarray([e["Y"] for e in ordered], dtype=np.float64)

    base_beta = _independent_ols(np.column_stack((np.ones(len(depth)), depth)), y)
    base_pred = base_beta[0] + base_beta[1] * evaluation["final_depth"]
    base_ae = abs(evaluation["Y"] - base_pred)
    assert record["base_pred"] == pytest.approx(base_pred)
    assert record["base_ae"] == pytest.approx(base_ae)

    stratum = lib.baseline_stratum_id(L=240, direction=evaluation["direction"])
    assert stratum == "240|UP"
    rng = np.random.default_rng(
        lib.seed_int((lib.SEED_PLACEBO, 0, 240, H, int(evaluation["T"]), stratum))
    )
    permuted = rng.permutation(recovery)
    # 40: exactly the same multiset, in a different order
    assert sorted(permuted.tolist()) == sorted(recovery.tolist())
    # 38 / 39: depth and Y are the untouched, canonically ordered vectors
    placebo_beta = _independent_ols(
        np.column_stack((np.ones(len(depth)), depth, permuted)), y
    )
    placebo_pred = (
        placebo_beta[0]
        + placebo_beta[1] * evaluation["final_depth"]
        + placebo_beta[2] * evaluation["recovery_fraction"]
    )
    expected = base_ae - abs(evaluation["Y"] - placebo_pred)
    assert cell["placebo_q95"] == pytest.approx(expected, rel=1e-9, abs=1e-12)

    # 41: determinism across repeated evaluation
    again, _, _ = _single_event_cell(monkeypatch, H=H, n_placebo=1)
    assert again["placebo_q95"] == cell["placebo_q95"]


def test_40b_permuting_recovery_changes_only_the_candidate_side(monkeypatch):
    """The placebo must not disturb the baseline model at all."""
    cell, _, _ = _single_event_cell(monkeypatch, H=60, n_placebo=4)
    record = cell["scored"][0]
    shuffled_baseline = lib.ols_fit
    assert callable(shuffled_baseline)
    # baseline prediction is a pure function of (depth, Y); a placebo replicate
    # cannot enter it, so BASE_AE is identical to the non-placebo computation.
    again, _, _ = _single_event_cell(monkeypatch, H=60, n_placebo=1)
    assert again["scored"][0]["base_ae"] == pytest.approx(record["base_ae"])
    assert again["scored"][0]["base_pred"] == pytest.approx(record["base_pred"])


def _counting_ols_wrapper(monkeypatch, *, outer_calls, fail_replicate_indices):
    """Wrap lib.ols_fit so the first `outer_calls` invocations (the real
    baseline/candidate outer fits) always succeed, and every subsequent
    invocation (placebo replicate k, in ascending replicate order) fails
    (returns None) iff k is in `fail_replicate_indices`.

    This deterministically forces specific placebo replicates to become
    singular/nonfinite while the true baseline/candidate cell for the same
    scored event remains fully scoreable -- exactly the frozen-procedure
    attack required by the BLOCKER repair.
    """
    real_fit = lib.ols_fit
    counter = {"n": 0}

    def wrapper(design, target):
        idx = counter["n"]
        counter["n"] += 1
        if idx < outer_calls:
            return real_fit(design, target)
        replicate = idx - outer_calls
        if replicate in fail_replicate_indices:
            return None
        return real_fit(design, target)

    monkeypatch.setattr(lib, "ols_fit", wrapper)
    return counter


@pytest.mark.parametrize(
    "finite_count",
    [100, 99, 1, 0],
)
def test_blocker_placebo_requires_all_frozen_replicates_finite(monkeypatch, finite_count):
    """BLOCKER repair: placebo_q95 may be computed ONLY when all N_PLACEBO
    frozen replicates are finite. A partial-subset quantile (even 99/100)
    must make the cell's placebo comparison unavailable and
    placebo_separation False -- never a silent pass on a degraded subset."""
    n_placebo = 100
    fail_count = n_placebo - finite_count
    fail_indices = set(range(fail_count))  # fail the first `fail_count` replicates
    _counting_ols_wrapper(monkeypatch, outer_calls=2, fail_replicate_indices=fail_indices)

    h_ms = 60 * lib.BAR_MS
    n_train = 30
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = [
        _synthetic_event(
            t0 + k * h_ms,
            depth=0.26 + 0.0031 * k,
            recovery=(0.0417 * k) % 1.0,
            y=float(((k * 7) % 11) - 5),
            scoreable=False,
        )
        for k in range(n_train)
    ]
    evaluation = _synthetic_event(
        t0 + n_train * h_ms, depth=0.331, recovery=0.734, y=2.25, scoreable=True
    )
    events.append(evaluation)
    monkeypatch.setattr(lib, "build_score_records", _stamp_records)
    monkeypatch.setattr(lib, "MIN_TRAIN_COUNT", n_train)
    monkeypatch.setattr(lib, "N_PLACEBO", n_placebo)
    monkeypatch.setattr(lib, "N_BOOT", 8)

    cell = lib.evaluate_cell(
        events, {"t_ms": np.zeros(1), "close": np.ones(1)}, 240, 60
    )

    # The true baseline/candidate cell remains fully scoreable regardless of
    # how many placebo replicates were made to fail.
    assert cell["N"] == 1
    assert cell["scored"][0]["base_ae"] is not None
    assert math.isfinite(float(cell["scored"][0]["base_ae"]))

    assert cell["placebo_replicate_count_nominal"] == 100
    assert cell["placebo_replicate_count_finite"] == finite_count

    if finite_count == 100:
        assert cell["placebo_q95"] is not None
        assert math.isfinite(float(cell["placebo_q95"]))
    else:
        assert cell["placebo_q95"] is None
        assert cell["per_cell_conditions"]["placebo_separation"] is False


def test_blocker_placebo_never_resamples_or_falls_back(monkeypatch):
    """No replacement replicate, no seed change, no alternate solver: a
    failed replicate index simply contributes nothing -- the finite count
    strictly reflects how many of the ORIGINAL 100 seeded replicates
    succeeded, never a resampled/padded count back up to 100."""
    _counting_ols_wrapper(monkeypatch, outer_calls=2, fail_replicate_indices={7, 42, 99})
    h_ms = 60 * lib.BAR_MS
    n_train = 30
    t0 = lib.DEV_START_MS + 30 * lib.DAY_MS
    events = [
        _synthetic_event(
            t0 + k * h_ms,
            depth=0.26 + 0.0031 * k,
            recovery=(0.0417 * k) % 1.0,
            y=float(((k * 7) % 11) - 5),
            scoreable=False,
        )
        for k in range(n_train)
    ]
    events.append(
        _synthetic_event(t0 + n_train * h_ms, depth=0.331, recovery=0.734, y=2.25)
    )
    monkeypatch.setattr(lib, "build_score_records", _stamp_records)
    monkeypatch.setattr(lib, "MIN_TRAIN_COUNT", n_train)
    monkeypatch.setattr(lib, "N_PLACEBO", 100)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    cell = lib.evaluate_cell(
        events, {"t_ms": np.zeros(1), "close": np.ones(1)}, 240, 60
    )
    assert cell["placebo_replicate_count_nominal"] == 100
    assert cell["placebo_replicate_count_finite"] == 97
    assert cell["placebo_q95"] is None
    assert cell["per_cell_conditions"]["placebo_separation"] is False
    # source-level guard: no pseudoinverse / resampling escape hatch exists
    source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "pinv" not in source
    placebo_body = source.split("def evaluate_cell(", 1)[1].split("\ndef ", 1)[0]
    assert "replace(" not in placebo_body


def test_blocker_degraded_placebo_cell_cannot_join_a_promoting_neighborhood():
    """A cell whose placebo comparison is unavailable fails
    placebo_separation, which is one of the five per-cell conditions
    required by both horizon_robustness and parameter_robustness -- so it
    can never contribute to a qualifying promotion neighborhood."""

    def passing_cell(L, H):
        return {
            "L": L,
            "H": H,
            "year_stability_pass": True,
            "per_cell_conditions": {
                name: True for name in lib.PER_CELL_GATE_NAMES
            },
        }

    def degraded_cell(L, H):
        conditions = {name: True for name in lib.PER_CELL_GATE_NAMES}
        conditions["placebo_separation"] = False  # placebo_q95 unavailable
        return {
            "L": L,
            "H": H,
            "year_stability_pass": True,
            "per_cell_conditions": conditions,
        }

    cells = []
    for L in lib.L_VALUES:
        for H in lib.H_VALUES:
            cells.append(
                {
                    "L": L,
                    "H": H,
                    "year_stability_pass": False,
                    "per_cell_conditions": {
                        name: False for name in lib.PER_CELL_GATE_NAMES
                    },
                }
            )
    index = {(c["L"], c["H"]): i for i, c in enumerate(cells)}

    # Two L values each have a "complete" adjacent-H pair, but ONE of the
    # four cells is the placebo-degraded cell.
    cells[index[(240, 15)]] = passing_cell(240, 15)
    cells[index[(240, 30)]] = degraded_cell(240, 30)  # placebo blocked here
    cells[index[(480, 15)]] = passing_cell(480, 15)
    cells[index[(480, 30)]] = passing_cell(480, 30)

    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True  # 480 alone still qualifies
    assert gates["parameter_robustness"] is False  # only one L has the full pair
    assert neighborhoods == []
    passed = bool(neighborhoods) and all(
        gates.get(name) is True for name in lib.GATE_NAMES
    )
    assert passed is False


def test_41_placebo_is_deterministic(monkeypatch):
    events = _placebo_events()
    first = _cell_with(monkeypatch, events, H=60, min_train=3, n_placebo=5)
    second = _cell_with(monkeypatch, events, H=60, min_train=3, n_placebo=5)
    assert first["placebo_q95"] == second["placebo_q95"]
    assert first["placebo_replicate_count_finite"] == second["placebo_replicate_count_finite"]


def test_42_placebo_ordering_is_canonical_and_row_order_invariant(monkeypatch):
    events = _placebo_events()
    forward = _cell_with(monkeypatch, events, H=60, min_train=3, n_placebo=4)
    backward = _cell_with(
        monkeypatch, list(reversed(events)), H=60, min_train=3, n_placebo=4
    )
    assert forward["placebo_q95"] == backward["placebo_q95"]
    assert forward["score_record_ids"] == backward["score_record_ids"]


def test_42b_placebo_seed_serialization_is_frozen():
    stratum = lib.baseline_stratum_id(L=480, direction="DOWN")
    assert stratum == "480|DOWN"
    t = 1_580_600_000_000
    seed = lib.seed_int((lib.SEED_PLACEBO, 7, 480, 120, t, stratum))
    raw = "|".join(str(p) for p in (20260906, 7, 480, 120, t, "480|DOWN")).encode("utf-8")
    assert seed == int(hashlib.sha256(raw).hexdigest()[:16], 16)
    boot = lib.seed_int((lib.SEED_BOOT, 3, 240, 15))
    raw_boot = "|".join(str(p) for p in (20260907, 3, 240, 15)).encode("utf-8")
    assert boot == int(hashlib.sha256(raw_boot).hexdigest()[:16], 16)


# ---------------------------------------------------------------------------
# 43-44: bootstrap
# ---------------------------------------------------------------------------
def test_43_bootstrap_is_deterministic_and_matches_a_reference(monkeypatch):
    monkeypatch.setattr(lib, "N_BOOT", 64)
    improvements = np.array([1.0, 1.0, 1.0, -5.0, 2.0, 0.5], dtype=np.float64)
    t0 = lib.DEV_START_MS
    times = np.array(
        [t0, t0 + lib.DAY_MS, t0 + 2 * lib.DAY_MS,
         t0 + 30 * lib.DAY_MS, t0 + 31 * lib.DAY_MS, t0 + 60 * lib.DAY_MS],
        dtype=np.int64,
    )
    got = lib.week_bootstrap_interval(improvements, times, 240, 60)
    assert got == lib.week_bootstrap_interval(improvements, times, 240, 60)

    groups: dict[int, list[float]] = {}
    for value, t in zip(improvements, times):
        groups.setdefault(lib.iso_week_id(int(t)), []).append(float(value))
    keys = sorted(groups)
    draws = []
    for replicate in range(64):
        rng = np.random.default_rng(lib.seed_int((lib.SEED_BOOT, replicate, 240, 60)))
        sampled = rng.integers(0, len(keys), size=len(keys))
        pooled = []
        for pos in sampled:  # concatenate whole weeks in canonical order
            pooled.extend(groups[keys[pos]])
        draws.append(float(np.mean(pooled)))
    finite = np.asarray(draws)
    assert got[0] == pytest.approx(float(np.quantile(finite, 0.025)))
    assert got[1] == pytest.approx(float(np.quantile(finite, 0.975)))
    # row order must not matter
    order = np.array([4, 0, 5, 2, 1, 3])
    assert lib.week_bootstrap_interval(improvements[order], times[order], 240, 60) == got


def test_44_iso_week_year_boundary_is_not_the_gregorian_year():
    cases = [
        "2019-12-30T00:00:00Z",
        "2019-12-31T23:45:00Z",
        "2020-01-01T00:00:00Z",
        "2021-01-01T00:00:00Z",
        "2021-01-03T23:45:00Z",
        "2021-01-04T00:00:00Z",
        "2022-01-02T00:00:00Z",
        "2024-12-30T00:00:00Z",
        "2024-12-31T23:45:00Z",
    ]
    for iso in cases:
        ms = int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
        stamp = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        year, week, _ = stamp.isocalendar()
        assert lib.iso_week_id(ms) == year * 100 + week
    # 2019-12-30 is ISO 2020-W01 while its Gregorian year is 2019
    ms = int(datetime.fromisoformat("2019-12-30T00:00:00+00:00").timestamp() * 1000)
    assert lib.iso_week_id(ms) == 202001
    assert lib.utc_year(ms) == 2019
    rng = np.random.default_rng(2)
    for _ in range(3000):
        ms = int(rng.integers(lib.WARMUP_START_MS, lib.DEV_END_MS))
        stamp = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        year, week, _ = stamp.isocalendar()
        assert lib.iso_week_id(ms) == year * 100 + week


# ---------------------------------------------------------------------------
# 45-51: gates
# ---------------------------------------------------------------------------
def _conditions(**kwargs):
    base = dict(
        mean_improvement=1.0,
        up_mean=1.0,
        down_mean=1.0,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        separation_pooled=0.5,
        separation_up=0.5,
        separation_down=0.5,
    )
    base.update(kwargs)
    return lib.per_cell_conditions(**base)


def test_45_all_five_cell_conditions_exist_and_are_strict():
    passing = _conditions()
    assert set(passing) == set(lib.PER_CELL_GATE_NAMES)
    assert all(passing.values())
    assert _conditions(mean_improvement=0.0)["primary_positive"] is False
    assert _conditions(relative=0.019999)["material_relative_mae"] is False
    assert _conditions(relative=0.02)["material_relative_mae"] is True
    assert _conditions(bootstrap_lower=0.0)["bootstrap_positive"] is False
    assert _conditions(mean_improvement=0.2, placebo_q95=0.2)["placebo_separation"] is False
    assert _conditions(separation_pooled=0.0)["structure_ordering"] is False
    assert _conditions(mean_improvement=float("nan"))["primary_positive"] is False
    assert _conditions(bootstrap_lower=float("nan"))["bootstrap_positive"] is False


def test_46_side_symmetry_blocks_one_sided_results():
    assert _conditions(up_mean=2.0, down_mean=-0.1)["primary_positive"] is False
    assert _conditions(up_mean=-0.1, down_mean=2.0)["primary_positive"] is False
    assert _conditions(up_mean=float("nan"))["primary_positive"] is False
    assert _conditions(separation_up=1.0, separation_down=-0.1)["structure_ordering"] is False
    assert _conditions(separation_down=float("nan"))["structure_ordering"] is False
    # a missing HIGH or LOW side is NaN, never zero
    records = [
        {"direction": "UP", "structure_state": lib.STATE_HIGH, "base_residual": 1.0},
        {"direction": "UP", "structure_state": lib.STATE_HIGH, "base_residual": 2.0},
    ]
    assert math.isnan(lib.structure_separation(records))
    assert math.isnan(lib.structure_separation(records, "DOWN"))


def _cell(L, H, passing, year=True):
    return {
        "L": L,
        "H": H,
        "year_stability_pass": year,
        "per_cell_conditions": {
            name: (name in passing) for name in lib.PER_CELL_GATE_NAMES
        },
    }


def _all_fail_grid():
    return [_cell(L, H, set()) for L in lib.L_VALUES for H in lib.H_VALUES]


def test_47_adjacent_h_pairs_are_exact():
    assert lib.ADJACENT_H_PAIRS == ((15, 30), (30, 60), (60, 120), (120, 240))
    cells = _all_fail_grid()
    index = {(c["L"], c["H"]): i for i, c in enumerate(cells)}
    # 15 and 60 are not adjacent
    for L in (240, 480):
        cells[index[(L, 15)]] = _cell(L, 15, set(lib.PER_CELL_GATE_NAMES))
        cells[index[(L, 60)]] = _cell(L, 60, set(lib.PER_CELL_GATE_NAMES))
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is False
    assert neighborhoods == []


def test_48_same_pair_must_pass_at_a_second_l():
    cells = _all_fail_grid()
    index = {(c["L"], c["H"]): i for i, c in enumerate(cells)}
    cells[index[(240, 15)]] = _cell(240, 15, set(lib.PER_CELL_GATE_NAMES))
    cells[index[(240, 30)]] = _cell(240, 30, set(lib.PER_CELL_GATE_NAMES))
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []

    cells[index[(960, 15)]] = _cell(960, 15, set(lib.PER_CELL_GATE_NAMES))
    cells[index[(960, 30)]] = _cell(960, 30, set(lib.PER_CELL_GATE_NAMES))
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["parameter_robustness"] is True
    assert neighborhoods and neighborhoods[0]["H_pair"] == [15, 30]
    assert neighborhoods[0]["L"] == [240, 960]


def test_48b_mosaic_of_single_gates_cannot_promote():
    """Disjoint per-gate passes across L cannot satisfy the neighborhood."""
    cells = _all_fail_grid()
    index = {(c["L"], c["H"]): i for i, c in enumerate(cells)}
    sets = {
        240: {"primary_positive", "material_relative_mae", "structure_ordering"},
        480: {"primary_positive", "material_relative_mae", "bootstrap_positive",
              "placebo_separation"},
        960: {"bootstrap_positive", "placebo_separation", "structure_ordering"},
    }
    for L, names in sets.items():
        for H in (15, 30):
            cells[index[(L, H)]] = _cell(L, H, names)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert all(gates[name] is True for name in lib.PER_CELL_GATE_NAMES)
    assert gates["horizon_robustness"] is False
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []
    passed = bool(neighborhoods) and all(
        gates.get(name) is True for name in lib.GATE_NAMES
    )
    assert passed is False


def test_49_year_stability_applies_to_every_neighborhood_cell():
    cells = _all_fail_grid()
    index = {(c["L"], c["H"]): i for i, c in enumerate(cells)}
    for L in (240, 480):
        cells[index[(L, 60)]] = _cell(L, 60, set(lib.PER_CELL_GATE_NAMES))
        cells[index[(L, 120)]] = _cell(L, 120, set(lib.PER_CELL_GATE_NAMES))
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["year_stability"] is True
    # a single unstable member of the neighborhood removes that L
    cells[index[(480, 120)]] = _cell(480, 120, set(lib.PER_CELL_GATE_NAMES), year=False)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["parameter_robustness"] is True
    assert gates["year_stability"] is False
    assert neighborhoods == []


def test_49b_year_stability_threshold_is_four_of_five(monkeypatch):
    H = 60
    h_ms = H * lib.BAR_MS
    events = []
    for year_index, year_start in enumerate(
        (
            lib.DEV_START_MS,
            lib.DEV_START_MS + 366 * lib.DAY_MS,
            lib.DEV_START_MS + 731 * lib.DAY_MS,
            lib.DEV_START_MS + 1096 * lib.DAY_MS,
            lib.DEV_START_MS + 1461 * lib.DAY_MS,
        )
    ):
        for k in range(8):
            events.append(
                _synthetic_event(
                    year_start + k * h_ms,
                    depth=0.26 + 0.004 * k,
                    recovery=(k * 0.11) % 1.0,
                    y=float(k % 3),
                )
            )
    cell = _cell_with(monkeypatch, events, H=H, min_train=3)
    assert set(cell["yearly_mean_ae_improvement"]) == {"2020", "2021", "2022", "2023", "2024"}
    assert cell["year_stability_pass"] is (cell["positive_years"] >= 4)


def test_50_exactly_eight_gates_no_ninth():
    assert lib.GATE_NAMES == (
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "structure_ordering",
        "horizon_robustness",
        "parameter_robustness",
        "year_stability",
    )
    assert len(lib.GATE_NAMES) == 8
    assert len(set(lib.GATE_NAMES)) == 8
    assert lib.PER_CELL_GATE_NAMES == lib.GATE_NAMES[:5]
    gates, _ = lib.determine_promotion_gates(_all_fail_grid())
    assert set(gates) == set(lib.GATE_NAMES)
    freeze = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
    assert tuple(freeze["promotion_gate_contract"]["required_gate_names"]) == lib.GATE_NAMES


def test_51_reverse_recovery_ordering_cannot_rescue():
    """A negative HIGH-minus-LOW separation is failure, never exhaustion."""
    assert _conditions(
        separation_pooled=-0.4, separation_up=-0.4, separation_down=-0.4
    )["structure_ordering"] is False
    records = [
        {"direction": "UP", "structure_state": lib.STATE_HIGH, "base_residual": -1.0},
        {"direction": "UP", "structure_state": lib.STATE_LOW, "base_residual": 1.0},
        {"direction": "DOWN", "structure_state": lib.STATE_HIGH, "base_residual": -1.0},
        {"direction": "DOWN", "structure_state": lib.STATE_LOW, "base_residual": 1.0},
    ]
    assert lib.structure_separation(records) < 0.0
    source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "abs(separation" not in source
    assert "exhaustion" not in source.lower().split("prereg")[0]


# ---------------------------------------------------------------------------
# 52-54: payload determinism
# ---------------------------------------------------------------------------
def _synthetic_market_frame(n_days=90, seed=11):
    n = n_days * 24 * 60
    n -= n % lib.HTF_MIN
    rng = np.random.default_rng(seed)
    open_ms = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.BAR_MS
    drift = np.repeat(rng.normal(0, 0.00004, size=(n // 720) + 1), 720)[:n]
    steps = rng.normal(0, 0.0006, size=n) + drift
    close = 100.0 * np.exp(np.cumsum(steps))
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "close": close,
    }


def test_52_all_fifteen_cells_present_in_the_payload():
    result = lib.evaluate_b2_04(_synthetic_market_frame(50))
    assert len(result["cells"]) == 15
    pairs = {(int(c["L"]), int(c["H"])) for c in result["cells"]}
    assert pairs == {(L, H) for L in lib.L_VALUES for H in lib.H_VALUES}
    assert result["search_surface"]["primary_cells"] == 15
    for cell in result["cells"]:
        for key in (
            "L", "H", "N", "UP_N", "DOWN_N",
            "mean_ae_improvement", "relative_mae_improvement",
            "bootstrap_lower_95", "bootstrap_upper_95", "placebo_q95",
            "structure_separation_pooled", "structure_separation_up",
            "structure_separation_down", "positive_years",
            "per_cell_conditions", "same_support",
        ):
            assert key in cell
        assert set(cell["per_cell_conditions"]) == set(lib.PER_CELL_GATE_NAMES)
        assert "scored" not in cell
    assert result["promotion"]["verdict"] in {
        "B2_04_PROMOTED_CANDIDATE",
        "B2_04_CLOSED_NO_PROMOTION",
    }
    assert result["hypothesis_id"] == lib.HYPOTHESIS_ID
    assert result["structural_property"]["count"] == 1
    assert result["windows"]["validation_2025_untouched"] is True
    assert result["windows"]["oos_2026_untouched"] is True


def test_52b_base_population_is_independent_of_the_horizon():
    """STAGE C immutability: attaching H may not add, drop or re-rank the
    constructed base events."""
    frame15 = lib.aggregate_1m_to_15m(_synthetic_market_frame(60))
    base = lib.construct_events(frame15)
    assert base
    ids = [e["base_event_id"] for e in base]
    assert len(set(ids)) == len(ids)
    events = lib.attach_structure_state(lib.attach_recovery(base, frame15))
    for H in lib.H_VALUES:
        records = lib.build_score_records(events, frame15, H)
        assert [r["base_event_id"] for r in records] == ids
        assert [int(r["T"]) for r in records] == [int(e["T"]) for e in base]
    result = lib.evaluate_b2_04(_synthetic_market_frame(60))
    by_l: dict[int, set[int]] = {}
    for cell in result["cells"]:
        by_l.setdefault(int(cell["L"]), set()).add(int(cell["constructed_base_events"]))
    assert all(len(counts) == 1 for counts in by_l.values())
    assert result["constructed_base_events"] == len(ids)


def test_52c_bytes_after_the_event_cannot_change_construction_or_features():
    """Future-leakage attack: multiply every close beyond the last decision
    time by five and require identical construction, recovery and state."""
    frame = _synthetic_market_frame(60)
    frame15 = lib.aggregate_1m_to_15m(frame)
    base = lib.construct_events(frame15)
    assert base
    events = lib.attach_structure_state(lib.attach_recovery(base, frame15))

    last_t = max(int(e["T"]) for e in base)
    poisoned = {key: value.copy() for key, value in frame.items()}
    horizon_guard = last_t + max(lib.H_VALUES) * lib.BAR_MS
    mask = poisoned["open_time_ms"] >= horizon_guard
    assert mask.sum() > 0
    poisoned["close"][mask] *= 5.0

    poisoned15 = lib.aggregate_1m_to_15m(poisoned)
    poisoned_base = lib.construct_events(poisoned15)
    poisoned_events = lib.attach_structure_state(
        lib.attach_recovery(poisoned_base, poisoned15)
    )
    assert [e["base_event_id"] for e in poisoned_base] == [
        e["base_event_id"] for e in base
    ]
    for original, attacked in zip(events, poisoned_events):
        assert original["structure_state"] == attacked["structure_state"]
        assert original["final_depth"] == pytest.approx(attacked["final_depth"])
        if original["recovery_available"]:
            assert attacked["recovery_available"] is True
            assert original["recovery_fraction"] == pytest.approx(
                attacked["recovery_fraction"]
            )
        else:
            assert attacked["recovery_available"] is False


def test_53_54_payload_serializes_deterministically():
    first = lib.evaluate_b2_04(_synthetic_market_frame(50))
    second = lib.evaluate_b2_04(_synthetic_market_frame(50))
    blob_a = json.dumps(first, sort_keys=True, separators=(",", ":"), allow_nan=False)
    blob_b = json.dumps(second, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert blob_a == blob_b
    assert hashlib.sha256(blob_a.encode("utf-8")).hexdigest() == hashlib.sha256(
        blob_b.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# 55-57: runner, retention ceremony, source policy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "acknowledgement",
    [None, False, 0, 1, "true", "True", [], object()],
)
def test_55_only_literal_true_acknowledgement_is_accepted(monkeypatch, acknowledgement):
    calls: list[str] = []

    def _boom(name):
        def _inner(*a, **k):
            calls.append(name)
            raise AssertionError(f"{name} must not run before acknowledgement")
        return _inner

    for name in (
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
        "persist_batch02_retained_result",
        "archive_batch02_result",
    ):
        monkeypatch.setattr(runner, name, _boom(name))

    with pytest.raises(ValueError, match="outcome_access_acknowledged"):
        runner.run_development("a" * 40, outcome_access_acknowledged=acknowledgement)
    assert calls == []


def test_55b_default_acknowledgement_is_false(monkeypatch):
    calls: list[str] = []
    for name in (
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
    ):
        monkeypatch.setattr(
            runner, name, lambda *a, **k: calls.append("called")
        )
    with pytest.raises(ValueError):
        runner.run_development("a" * 40)
    assert calls == []


def test_56_retention_call_order(monkeypatch):
    calls: list[str] = []

    class Freeze:
        code_sha = "a" * 40
        tree_oid = "b" * 40
        repo_root = REPO_ROOT

    class Reservation:
        hypothesis_id = lib.HYPOTHESIS_ID

        def assert_minted(self):
            return None

    class Proof:
        artifact_sha256 = "c" * 64
        result_path = runner.RESULT_PATH

    class Receipt:
        archive_commit_sha = "d" * 40

    class Context:
        run_identity = {
            "hypothesis_id": lib.HYPOTHESIS_ID,
            "window": {
                "start_inclusive_ms": lib.DEV_START_MS,
                "end_exclusive_ms": lib.DEV_END_MS,
                "allowed_years": [2020, 2021, 2022, 2023, 2024],
            },
            "partitions": [{"relative_path": "canonical/1m/monthly/2020-02.parquet"}],
        }
        code_freeze = Freeze()

        def assert_minted(self):
            return None

    class Table:
        def column(self, name):
            frame = _synthetic_market_frame(2)

            class Col:
                def __init__(self, values):
                    self._values = values

                def to_numpy(self, zero_copy_only=False):
                    return self._values

            return Col(frame[name])

    monkeypatch.setattr(
        runner, "verify_batch02_code", lambda **k: calls.append("verify") or Freeze()
    )
    monkeypatch.setattr(
        runner,
        "prepare_batch02_evidence_reservation",
        lambda **k: calls.append("reserve") or Reservation(),
    )
    monkeypatch.setattr(
        runner,
        "prepare_batch02_retained_run",
        lambda **k: calls.append("claim") or Context(),
    )
    monkeypatch.setattr(
        runner, "load_authorized_parquet_table", lambda **k: calls.append("load") or Table()
    )
    monkeypatch.setattr(
        runner,
        "persist_batch02_retained_result",
        lambda *a, **k: calls.append("persist") or Proof(),
    )
    monkeypatch.setattr(
        runner, "archive_batch02_result", lambda **k: calls.append("archive") or Receipt()
    )
    monkeypatch.setattr(
        runner,
        "evaluate_b2_04",
        lambda frame: calls.append("evaluate")
        or {"promotion": {"verdict": "B2_04_CLOSED_NO_PROMOTION"}},
    )
    out = runner.run_development("a" * 40, outcome_access_acknowledged=True)
    assert calls == [
        "verify",
        "reserve",
        "claim",
        "load",
        "evaluate",
        "persist",
        "archive",
    ]
    assert out["overall_status"] == "B2_04_CLOSED_NO_PROMOTION"
    assert out["validation_2025_accessed"] is False
    assert out["oos_2026_accessed"] is False


def test_56b_legacy_retention_api_is_absent():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "prepare_batch02_run(" not in source
    assert "persist_batch02_result(" not in source
    assert "prepare_batch02_evidence_reservation" in source
    assert "prepare_batch02_retained_run" in source
    assert "persist_batch02_retained_result" in source
    assert "archive_batch02_result" in source
    assert "b2_04_moderate_pullback_structure" in str(runner.RESULT_PATH)
    assert runner.RESULT_PATH.as_posix().endswith(
        "artifacts/b2_04_moderate_pullback_structure/"
        "B2_04_MODERATE_PULLBACK_STRUCTURE_DEV_RESULTS.json"
    )


def test_57_no_direct_parquet_or_alternate_loader():
    for path in (Path(runner.__file__), Path(lib.__file__)):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "read_parquet",
            "pq.read_table",
            "pyarrow.parquet",
            "ParquetFile",
            "open(",
            "rankdata",
            "percentileofscore",
            "searchsorted",
            "importlib",
            "subprocess",
            "batch02_evidence_retention",
        ):
            assert forbidden not in source, (path.name, forbidden)
    visited = set(validate_batch02_source_tree(RESEARCH_DIR, repo_root=REPO_ROOT))
    assert RESEARCH_DIR / "b2_04_moderate_pullback_structure.py" in visited
    assert RESEARCH_DIR / "b2_04_moderate_pullback_structure_lib.py" in visited


# ---------------------------------------------------------------------------
# 58-60: freeze and outcome boundary
# ---------------------------------------------------------------------------
def test_58_prereg_documents_are_unchanged_by_this_unit():
    result = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
    assert result["formulation_id"] == lib.HYPOTHESIS_ID
    assert result["implementation_exists"] is False
    assert result["outcome_access_authorized"] is False
    md = PREREG_MD.read_text(encoding="utf-8")
    assert "FROZEN_BEFORE_IMPLEMENTATION" in md
    # implementation constants must equal the frozen twin
    assert tuple(result["event_construction"]["L_minutes"]) == lib.L_VALUES
    assert tuple(result["horizons_minutes"]) == lib.H_VALUES
    assert result["event_construction"]["moderate_domain_lo_inclusive"] == lib.MODERATE_LO
    assert result["event_construction"]["moderate_domain_hi_exclusive"] == lib.MODERATE_HI
    assert result["event_construction"]["refractory_minutes"] * lib.BAR_MS == lib.REFRACTORY_MS
    assert result["event_construction"]["trend_q"] == lib.TREND_Q
    assert result["forecast"]["training_lookback_days"] == lib.TRAIN_DAYS
    assert result["forecast"]["training_min_count"] == lib.MIN_TRAIN_COUNT
    assert result["controls"]["permutation_seed"] == lib.SEED_PLACEBO
    assert result["controls"]["permutation_replicates"] == lib.N_PLACEBO
    assert result["controls"]["bootstrap_seed"] == lib.SEED_BOOT
    assert result["controls"]["bootstrap_replicates"] == lib.N_BOOT
    assert result["per_cell_thresholds"]["relative_mae_improvement_min"] == lib.RELATIVE_MAE_MIN
    assert result["structural_property"]["name"] == lib.STRUCTURAL_PROPERTY_NAME
    assert result["structural_property"]["path_step_count"] == len(lib.PATH_OFFSETS_MIN)
    assert result["structural_property"]["formulas"]["P_minutes"] == lib.P_MIN
    assert result["recovery_representation"]["structure_ordering_only"]["reference_days"] == lib.TRAIN_DAYS
    assert result["recovery_representation"]["structure_ordering_only"]["cutpoint"] == lib.STATE_CUTPOINT
    assert result["target"]["scale_reference_days"] == lib.REF_DAYS
    for H, iso in result["chronology"]["last_legal_T_by_horizon_minutes"].items():
        want = int(
            datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
        )
        assert lib.last_legal_t_ms(int(H)) == want


def test_59_60_outcome_boundary_flags_are_closed(monkeypatch):
    class Freeze:
        code_sha = "e" * 40

    monkeypatch.setattr(runner, "verify_batch02_code", lambda **k: Freeze())
    out = runner.identity("e" * 40)
    assert out["outcome_accessed"] is False
    assert out["validation_2025_accessed"] is False
    assert out["oos_2026_accessed"] is False
    assert out["prereg_merge_sha"] == lib.PREREG_MERGE_SHA
    assert out["hypothesis_id"] == lib.HYPOTHESIS_ID

    evidence = lib.derive_forbidden_window_evidence(
        {
            "window": {
                "start_inclusive_ms": lib.DEV_START_MS,
                "end_exclusive_ms": lib.DEV_END_MS,
                "allowed_years": [2020, 2021, 2022, 2023, 2024],
            },
            "partitions": [
                {"relative_path": "canonical/1m/monthly/2020-02.parquet"},
                {"relative_path": "canonical/1m/monthly/2024-12.parquet"},
            ],
        },
        {
            "open_time_ms": np.asarray([lib.DEV_END_MS - lib.BAR_MS], dtype=np.int64),
            "available_at_ms": np.asarray([lib.DEV_END_MS], dtype=np.int64),
            "close": np.asarray([100.0], dtype=np.float64),
        },
    )
    assert evidence["2025_validation"] is False
    assert evidence["2026_oos"] is False
    assert evidence["authorized_max_partition_year"] == 2024


def test_59b_empty_allowed_years_is_malformed_evidence_not_a_raw_valueerror():
    """max() over an empty allowed_years must never leak as a bare
    ValueError; it must fail closed as a deterministic B204Error."""
    frame = {
        "open_time_ms": np.asarray([lib.DEV_START_MS], dtype=np.int64),
        "available_at_ms": np.asarray([lib.DEV_START_MS + lib.BAR_MS], dtype=np.int64),
        "close": np.asarray([100.0], dtype=np.float64),
    }
    identity = {
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": lib.DEV_END_MS,
            "allowed_years": [],
        },
        "partitions": [{"relative_path": "canonical/1m/monthly/2020-02.parquet"}],
    }
    with pytest.raises(lib.B204Error, match="allowed_years") as excinfo:
        lib.derive_forbidden_window_evidence(identity, frame)
    assert "max() arg is an empty sequence" not in str(excinfo.value)
    # empty partitions is already guarded identically; keep both guards
    # aligned in behavior (deterministic B204Error, not a raw exception).
    identity["window"]["allowed_years"] = [2020]
    identity["partitions"] = []
    with pytest.raises(lib.B204Error, match="partition"):
        lib.derive_forbidden_window_evidence(identity, frame)


def test_60_forbidden_windows_fail_closed():
    frame = {
        "open_time_ms": np.asarray([lib.DEV_END_MS - lib.BAR_MS], dtype=np.int64),
        "available_at_ms": np.asarray([lib.DEV_END_MS], dtype=np.int64),
        "close": np.asarray([100.0], dtype=np.float64),
    }
    identity = {
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": lib.DEV_END_MS,
            "allowed_years": [2020, 2025],
        },
        "partitions": [{"relative_path": "canonical/1m/monthly/2020-02.parquet"}],
    }
    with pytest.raises(lib.B204Error, match="forbidden window"):
        lib.derive_forbidden_window_evidence(identity, frame)
    identity["window"]["allowed_years"] = [2020]
    identity["partitions"] = [{"relative_path": "canonical/1m/monthly/2025-01.parquet"}]
    with pytest.raises(lib.B204Error, match="partitions reach a forbidden window"):
        lib.derive_forbidden_window_evidence(identity, frame)
    identity["partitions"] = [{"relative_path": "canonical/1m/monthly/2020-02.parquet"}]
    identity["window"]["end_exclusive_ms"] = lib.DEV_END_MS + 1
    with pytest.raises(lib.B204Error, match="reserved 2025"):
        lib.derive_forbidden_window_evidence(identity, frame)
    # a 1m frame reaching 2025 is rejected at validation time
    bad_open = lib.WARMUP_START_MS + np.arange(15, dtype=np.int64) * lib.BAR_MS
    bad = {
        "open_time_ms": bad_open + (lib.DEV_END_MS - lib.WARMUP_START_MS),
        "available_at_ms": bad_open + (lib.DEV_END_MS - lib.WARMUP_START_MS) + lib.BAR_MS,
        "close": np.full(15, 100.0, dtype=np.float64),
    }
    with pytest.raises(lib.B204Error, match="2025"):
        lib.validate_1m_frame(bad)


# ---------------------------------------------------------------------------
# frame validation and aggregation
# ---------------------------------------------------------------------------
def test_frame_validation_and_15m_aggregation():
    closes15 = np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float64)
    frame = _frame_1m_from_15m(closes15)
    frame15 = lib.aggregate_1m_to_15m(frame)
    assert np.array_equal(frame15["close"], closes15)
    assert np.array_equal(
        frame15["t_ms"],
        lib.WARMUP_START_MS + (np.arange(4, dtype=np.int64) + 1) * lib.HTF_MS,
    )
    short = dict(frame)
    short["open_time_ms"] = frame["open_time_ms"][:-1]
    short["available_at_ms"] = frame["available_at_ms"][:-1]
    short["close"] = frame["close"][:-1]
    with pytest.raises(lib.B204Error, match="15m buckets"):
        lib.validate_1m_frame(short)
    gap = dict(frame)
    gap["open_time_ms"] = frame["open_time_ms"].copy()
    gap["open_time_ms"][5] += lib.BAR_MS
    with pytest.raises(lib.B204Error, match="contiguous"):
        lib.validate_1m_frame(gap)
    bad_avail = dict(frame)
    bad_avail["available_at_ms"] = frame["available_at_ms"].copy()
    bad_avail["available_at_ms"][0] += 1
    with pytest.raises(lib.B204Error, match="60000"):
        lib.validate_1m_frame(bad_avail)
    bad_close = dict(frame)
    bad_close["close"] = frame["close"].copy()
    bad_close["close"][2] = 0.0
    with pytest.raises(lib.B204Error, match="positive"):
        lib.validate_1m_frame(bad_close)
