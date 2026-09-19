"""MARKET-05 exact implementation checks on synthetic fixtures.

Independent expectations. Does not execute the scientific study on
CORE BTC/ETH development rows.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research.market05_cross_asset_authority import Market05AuthorityError
from scripts.research.market05_cross_asset_lib import (
    BAR_MS,
    BASELINE_COLUMN_NAMES,
    BASELINE_MODEL,
    BLOCK_LENGTH,
    BOOTSTRAP_KIND,
    BOOTSTRAP_REPLICATES,
    CANDIDATE_COLUMN_NAMES,
    CANDIDATE_MODEL,
    CLASS_INCOMPLETE,
    CLASS_NO_EVIDENCE,
    CLASS_PROMOTED,
    DECISION_TIME,
    ETH_CONFIRMATION_COL,
    ETH_CONFIRMATION_FORMULA,
    FIRST_USABLE_MS,
    FOLDS,
    HORIZON_MS,
    LAST_USABLE_MS,
    LOOKBACK_MS,
    MATERIALITY_THRESHOLD,
    N_FEATURE_BARS,
    N_OUTCOME_BARS,
    PRIMARY_OUTCOME,
    PROTECTED_OOS_START_MS,
    RANDOM_SEED,
    RESEARCH_ID,
    Bar,
    EligibleRow,
    Market05DecisionBoundError,
    Market05IntegrityError,
    Market05ProtectedOOSError,
    SplitMix64,
    apply_standardization,
    assert_development_decision_time,
    assert_no_protected_open_times,
    assert_outcome_window_inside_development,
    build_eligible_row,
    classify,
    coefficient_bootstrap,
    design_candidate,
    direction_aligned_mae,
    evaluate_prepared_rows,
    feature_open_times,
    fit_ols,
    fit_standardizer,
    in_half_open,
    instantiate_scientific_result,
    mean_absolute_error,
    outcome_open_times,
    prefix_open_time,
    relative_mae_improvement,
    result_schema,
    heldout_fold_name,
    training_mean_sd,
)

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]
PREREG_MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.md"
PREREG_JSON = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.json"
PREREG_MD_SHA256 = "31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e"
PREREG_JSON_SHA256 = "f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25"


def _ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp() * 1000)


def _bar(open_ms: int, close: float, high: float | None = None, low: float | None = None) -> Bar:
    return Bar(open_ms, float(high if high is not None else close), float(low if low is not None else close), float(close))


def _window(t_ms: int, *, prefix_close: float, last_feature_close: float, step: float = 0.01):
    prefix = _bar(prefix_open_time(t_ms), prefix_close)
    feat_opens = feature_open_times(t_ms)
    n = len(feat_opens)
    feat = []
    for i, ot in enumerate(feat_opens):
        frac = (i + 1) / n
        close = prefix_close + (last_feature_close - prefix_close) * frac
        feat.append(_bar(ot, close))
    return prefix, feat


def _complete_pair(
    t_ms: int,
    *,
    btc_prefix_close: float = 100.0,
    btc_last_close: float = 110.0,
    eth_prefix_close: float = 10.0,
    eth_last_close: float = 11.0,
    outcome_high: float = 111.0,
    outcome_low: float = 99.0,
    first_outcome_close: float = 110.0,
    last_outcome_close: float = 110.0,
    first_outcome_high: float | None = None,
    first_outcome_low: float | None = None,
    last_outcome_high: float | None = None,
    last_outcome_low: float | None = None,
):
    btc_prefix, btc_feat = _window(
        t_ms, prefix_close=btc_prefix_close, last_feature_close=btc_last_close
    )
    eth_prefix, eth_feat = _window(
        t_ms, prefix_close=eth_prefix_close, last_feature_close=eth_last_close
    )
    out = []
    opens = outcome_open_times(t_ms)
    for i, ot in enumerate(opens):
        close = first_outcome_close if i == 0 else (
            last_outcome_close if i == len(opens) - 1 else btc_last_close
        )
        high = outcome_high
        low = outcome_low
        if i == 0:
            if first_outcome_high is not None:
                high = first_outcome_high
            if first_outcome_low is not None:
                low = first_outcome_low
        if i == len(opens) - 1:
            if last_outcome_high is not None:
                high = last_outcome_high
            if last_outcome_low is not None:
                low = last_outcome_low
        out.append(_bar(ot, close, high=high, low=low))
    btc_bars = btc_feat + out
    return btc_prefix, btc_bars, eth_prefix, eth_feat


def test_prereg_constants_are_bound_literally():
    assert RESEARCH_ID == "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
    assert DECISION_TIME == "00:00:00 UTC"
    assert LOOKBACK_MS == 24 * 60 * 60 * 1000
    assert HORIZON_MS == 24 * 60 * 60 * 1000
    assert N_FEATURE_BARS == 1440
    assert N_OUTCOME_BARS == 1440
    assert MATERIALITY_THRESHOLD == 0.02
    assert BLOCK_LENGTH == 14
    assert BOOTSTRAP_REPLICATES == 5000
    assert RANDOM_SEED == 2026091905
    assert BOOTSTRAP_KIND == "CIRCULAR_MOVING_BLOCK"
    assert ETH_CONFIRMATION_FORMULA == "BTC_SIDE * Z_ETH"
    assert PRIMARY_OUTCOME == "BTC_DIRECTION_ALIGNED_MAE_24H"
    assert BASELINE_MODEL == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H"
    assert CANDIDATE_MODEL == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION"
    assert hashlib.sha256(PREREG_MD.read_bytes()).hexdigest() == PREREG_MD_SHA256
    assert hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest() == PREREG_JSON_SHA256
    prereg = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
    assert prereg["bootstrap"]["random_seed"] == RANDOM_SEED
    assert prereg["materiality_threshold"] == MATERIALITY_THRESHOLD
    assert prereg["bootstrap"]["block_length"] == BLOCK_LENGTH


def test_feature_window_excludes_bar_beginning_at_t_and_includes_bar_ending_at_t():
    t = _ms(2021, 6, 1)
    feat = feature_open_times(t)
    out = outcome_open_times(t)
    assert len(feat) == 1440
    assert feat[0] == t - LOOKBACK_MS
    assert feat[-1] == t - BAR_MS
    assert t not in feat
    assert feat[-1] + BAR_MS == t
    assert out[0] == t
    assert out[-1] == t + HORIZON_MS - BAR_MS
    assert prefix_open_time(t) == t - LOOKBACK_MS - BAR_MS
    assert prefix_open_time(t) + BAR_MS == t - LOOKBACK_MS


def test_bar_at_t_is_outcome_not_feature_for_price_and_mae():
    t = _ms(2021, 6, 1)
    btc_prefix, btc_bars, eth_prefix, eth_feat = _complete_pair(
        t,
        btc_prefix_close=100.0,
        btc_last_close=110.0,
        first_outcome_close=999.0,
        first_outcome_low=50.0,
        first_outcome_high=999.0,
        outcome_low=109.0,
        outcome_high=111.0,
    )
    row = build_eligible_row(t, btc_bars, btc_prefix, eth_feat, eth_prefix)
    assert row is not None
    independent_r = math.log(110.0 / 100.0)
    assert row.btc_side == 1.0
    leaked_r = math.log(999.0 / 100.0)
    assert not math.isclose(independent_r, leaked_r)
    expected_y = math.log(110.0 / 50.0)
    close_only_y = max(0.0, math.log(110.0 / 999.0))
    assert row.y == pytest.approx(expected_y)
    assert row.y != pytest.approx(close_only_y)


def test_eth_confirmation_formula_independent():
    t = _ms(2021, 6, 1)
    btc_prefix, btc_bars, eth_prefix, eth_feat = _complete_pair(
        t, btc_prefix_close=100.0, btc_last_close=110.0,
        eth_prefix_close=10.0, eth_last_close=12.0,
        outcome_low=99.0, outcome_high=111.0,
    )
    row = build_eligible_row(t, btc_bars, btc_prefix, eth_feat, eth_prefix)
    assert row is not None
    r_eth = math.log(12.0 / 10.0)
    eth_closes = [eth_prefix.close] + [b.close for b in eth_feat]
    rets = [math.log(eth_closes[i] / eth_closes[i - 1]) for i in range(1, len(eth_closes))]
    rv_eth = math.sqrt(sum(r * r for r in rets))
    z_eth = r_eth / rv_eth
    assert row.btc_side == 1.0
    assert row.eth_confirmation == pytest.approx(1.0 * z_eth)
    btc_prefix_dn, btc_bars_dn, eth_prefix_dn, eth_feat_dn = _complete_pair(
        t, btc_prefix_close=110.0, btc_last_close=100.0,
        eth_prefix_close=10.0, eth_last_close=12.0,
        outcome_low=99.0, outcome_high=120.0,
    )
    down = build_eligible_row(t, btc_bars_dn, btc_prefix_dn, eth_feat_dn, eth_prefix_dn)
    assert down is not None
    assert down.btc_side == -1.0
    assert down.eth_confirmation == pytest.approx((-1.0) * z_eth)
    assert down.eth_confirmation != pytest.approx(z_eth)


def test_direction_aligned_mae_golden_both_sides():
    p_t = 100.0
    lows = [99.0] * 1439 + [90.0]
    highs = [101.0] * 1440
    y_up = direction_aligned_mae(1.0, p_t, lows, highs)
    assert y_up == pytest.approx(math.log(100.0 / 90.0))
    y_dn = direction_aligned_mae(-1.0, p_t, [99.0] * 1440, [101.0] * 1439 + [110.0])
    assert y_dn == pytest.approx(math.log(110.0 / 100.0))
    y_zero = direction_aligned_mae(1.0, p_t, [100.0] * 1440, [120.0] * 1440)
    assert y_zero == 0.0
    y_first = direction_aligned_mae(1.0, p_t, [80.0] + [99.0] * 1439, [101.0] * 1440)
    assert y_first == pytest.approx(math.log(100.0 / 80.0))
    y_last = direction_aligned_mae(-1.0, p_t, [99.0] * 1440, [101.0] * 1439 + [125.0])
    assert y_last == pytest.approx(math.log(125.0 / 100.0))
    favorable_only = direction_aligned_mae(
        1.0, p_t, [100.5] * 1440, [200.0] * 1440
    )
    assert favorable_only == 0.0
    close_trap = direction_aligned_mae(1.0, p_t, [70.0] + [99.0] * 1439, [80.0] + [101.0] * 1439)
    close_only = max(0.0, math.log(100.0 / 80.0))
    assert close_trap == pytest.approx(math.log(100.0 / 70.0))
    assert close_trap != pytest.approx(close_only)


def test_mae_through_evaluator_matches_independent_y():
    t = _ms(2021, 6, 1)
    btc_prefix, btc_bars, eth_prefix, eth_feat = _complete_pair(
        t, btc_prefix_close=100.0, btc_last_close=110.0,
        outcome_low=99.0, last_outcome_low=88.0, outcome_high=111.0,
    )
    row = build_eligible_row(t, btc_bars, btc_prefix, eth_feat, eth_prefix)
    assert row is not None
    assert row.y == pytest.approx(math.log(110.0 / 88.0))
    btc_prefix2, btc_bars2, eth_prefix2, eth_feat2 = _complete_pair(
        t, btc_prefix_close=110.0, btc_last_close=100.0,
        outcome_high=101.0, last_outcome_high=130.0, outcome_low=90.0,
    )
    down = build_eligible_row(t, btc_bars2, btc_prefix2, eth_feat2, eth_prefix2)
    assert down is not None
    assert down.y == pytest.approx(math.log(130.0 / 100.0))


def test_same_support_adversarial_missingness():
    t = _ms(2021, 6, 1)
    btc_prefix, btc_bars, eth_prefix, eth_feat = _complete_pair(t)
    assert build_eligible_row(t, btc_bars, btc_prefix, eth_feat, eth_prefix) is not None

    eth_missing = eth_feat[:-1]
    assert build_eligible_row(t, btc_bars, btc_prefix, eth_missing, eth_prefix) is None

    feat_opens = set(feature_open_times(t))
    btc_missing_feat = [b for b in btc_bars if not (b.open_time_ms in feat_opens and b.open_time_ms == feature_open_times(t)[10])]
    assert build_eligible_row(t, btc_missing_feat, btc_prefix, eth_feat, eth_prefix) is None

    out_opens = outcome_open_times(t)
    btc_missing_out = [b for b in btc_bars if b.open_time_ms != out_opens[20]]
    assert build_eligible_row(t, btc_missing_out, btc_prefix, eth_feat, eth_prefix) is None

    bad_prefix = _bar(prefix_open_time(t) - BAR_MS, 100.0)
    assert build_eligible_row(t, btc_bars, bad_prefix, eth_feat, eth_prefix) is None
    assert build_eligible_row(t, btc_bars, btc_prefix, eth_feat, bad_prefix) is None

    dup = list(btc_bars) + [btc_bars[3]]
    assert build_eligible_row(t, dup, btc_prefix, eth_feat, eth_prefix) is None
    eth_dup = list(eth_feat) + [eth_feat[3]]
    assert build_eligible_row(t, btc_bars, btc_prefix, eth_dup, eth_prefix) is None


def test_zero_return_and_zero_rv_excluded():
    t = _ms(2021, 6, 1)
    btc_prefix, btc_bars, eth_prefix, eth_feat = _complete_pair(
        t, btc_prefix_close=100.0, btc_last_close=100.0
    )
    assert build_eligible_row(t, btc_bars, btc_prefix, eth_feat, eth_prefix) is None


def test_decision_bounds_and_protected_oos():
    assert_development_decision_time(FIRST_USABLE_MS)
    assert_development_decision_time(LAST_USABLE_MS)
    with pytest.raises(Market05DecisionBoundError):
        assert_development_decision_time(FIRST_USABLE_MS - 86_400_000)
    with pytest.raises(Market05DecisionBoundError):
        assert_development_decision_time(LAST_USABLE_MS + 86_400_000)
    with pytest.raises(Market05DecisionBoundError):
        assert_development_decision_time(FIRST_USABLE_MS + 3_600_000)
    with pytest.raises(Market05DecisionBoundError):
        assert_outcome_window_inside_development(PROTECTED_OOS_START_MS)
    with pytest.raises(Market05ProtectedOOSError):
        assert_no_protected_open_times([PROTECTED_OOS_START_MS])
    with pytest.raises(Market05ProtectedOOSError):
        build_eligible_row(
            _ms(2021, 6, 1),
            [_bar(PROTECTED_OOS_START_MS, 1.0)],
            _bar(prefix_open_time(_ms(2021, 6, 1)), 1.0),
            [_bar(_ms(2021, 5, 31), 1.0)],
            _bar(prefix_open_time(_ms(2021, 6, 1)), 1.0),
        )


def test_fold_boundaries_land_in_exactly_one_test_partition():
    cases = {
        _ms(2020, 1, 3): None,
        _ms(2021, 12, 31): None,
        _ms(2022, 1, 1): "FOLD_1",
        _ms(2022, 12, 31): "FOLD_1",
        _ms(2023, 1, 1): "FOLD_2",
        _ms(2023, 12, 31): "FOLD_2",
        _ms(2024, 1, 1): "FOLD_3",
        _ms(2024, 12, 31): "FOLD_3",
    }
    for t_ms, expected in cases.items():
        names = [name for name, spec in FOLDS.items() if in_half_open(t_ms, spec["test"])]
        if expected is None:
            assert names == []
            assert heldout_fold_name(t_ms) is None
        else:
            assert names == [expected]
            assert heldout_fold_name(t_ms) == expected
    assert in_half_open(_ms(2022, 1, 1), FOLDS["FOLD_1"]["train"]) is False
    assert in_half_open(_ms(2021, 12, 31), FOLDS["FOLD_1"]["train"]) is True


def test_train_only_standardization_rejects_full_period_leakage():
    train = [1.0, 2.0, 3.0]
    test = [1000.0]
    mean, sd = training_mean_sd(train)
    assert mean == pytest.approx(2.0)
    assert sd == pytest.approx(math.sqrt(2.0 / 3.0))
    got = float(apply_standardization(test, mean, sd)[0])
    expected = (1000.0 - 2.0) / math.sqrt(2.0 / 3.0)
    assert got == pytest.approx(expected)
    full = train + test
    leaked_mean, leaked_sd = training_mean_sd(full)
    leaked = float(apply_standardization(test, leaked_mean, leaked_sd)[0])
    assert leaked == pytest.approx((1000.0 - 251.5) / math.sqrt(sum((x - 251.5) ** 2 for x in full) / 4.0))
    assert abs(got - leaked) > 100.0


def test_ols_fail_closed_rank_collinearity_zero_sd_nonfinite():
    rows = [
        EligibleRow(_ms(2020, 1, 3), 1.0, 1.0, 0.02, 0.5, 0.1),
        EligibleRow(_ms(2020, 1, 4), 1.0, 1.0, 0.02, 0.5, 0.1),
        EligibleRow(_ms(2020, 1, 5), 1.0, 1.0, 0.02, 0.5, 0.1),
        EligibleRow(_ms(2020, 1, 6), 1.0, 1.0, 0.02, 0.5, 0.1),
        EligibleRow(_ms(2020, 1, 7), 1.0, 1.0, 0.02, 0.5, 0.1),
    ]
    with pytest.raises(Market05IntegrityError, match="zero training sd"):
        fit_standardizer(rows, include_eth=True)

    varied = [
        EligibleRow(_ms(2020, 1, 3 + i), 1.0, 1.0 + i, 0.02 + 0.001 * i, 3.0 + 3 * i, 0.1 * i)
        for i in range(6)
    ]
    stats = fit_standardizer(varied, include_eth=True)
    x = design_candidate(varied, stats)
    y = np.array([r.y for r in varied], dtype=np.float64)
    x[:, 4] = 2.0 * x[:, 2] + 3.0 * x[:, 3]
    with pytest.raises(Market05IntegrityError, match="collinear|rank"):
        fit_ols(x, y, expected_cols=5)

    x_rank = np.ones((4, 4))
    with pytest.raises(Market05IntegrityError, match="rank deficiency"):
        fit_ols(x_rank, np.array([1.0, 2.0, 3.0, 4.0]), expected_cols=4)

    x_bad = np.array([[1.0, 1.0, np.nan, 0.1]], dtype=np.float64)
    with pytest.raises(Market05IntegrityError, match="non-finite"):
        fit_ols(x_bad, np.array([1.0]), expected_cols=4)


def test_candidate_column_order_and_counts():
    assert BASELINE_COLUMN_NAMES == ("INTERCEPT", "BTC_SIDE", "ABS_Z_BTC", "RV_BTC_24H")
    assert CANDIDATE_COLUMN_NAMES == (
        "INTERCEPT",
        "BTC_SIDE",
        "ABS_Z_BTC",
        "RV_BTC_24H",
        "ETH_CONFIRMATION",
    )
    assert ETH_CONFIRMATION_COL == 4
    assert len(CANDIDATE_COLUMN_NAMES) == 5
    assert len(BASELINE_COLUMN_NAMES) == 4


def test_relative_mae_formula_and_zero_denominator():
    assert relative_mae_improvement(2.0, 1.5) == pytest.approx(0.25)
    assert relative_mae_improvement(1.0, 0.98) == pytest.approx(0.02)
    with pytest.raises(Market05IntegrityError):
        relative_mae_improvement(0.0, 0.1)
    y = np.array([1.0, 2.0, 3.0])
    pred = np.array([1.5, 1.5, 2.0])
    assert mean_absolute_error(y, pred) == pytest.approx((0.5 + 0.5 + 1.0) / 3.0)


def test_classification_truth_table_boundaries():
    years_ok = {2022: 0.03, 2023: 0.01, 2024: -0.01}

    def run(**overrides):
        payload = dict(
            beta_eth_confirmation=-0.1,
            beta_ci_upper=-0.01,
            relative_mae_improvement_value=0.03,
            relative_mae_ci_lower=0.01,
            year_relative_mae=years_ok,
            integrity_ok=True,
        )
        payload.update(overrides)
        return classify(**payload)

    cls, gates = run()
    assert cls == CLASS_PROMOTED
    assert all(gates.values())

    cls, gates = run(beta_eth_confirmation=0.0)
    assert cls == CLASS_NO_EVIDENCE
    assert gates["GATE_1_DIRECTION"] is False

    cls, gates = run(beta_ci_upper=0.0)
    assert cls == CLASS_NO_EVIDENCE
    assert gates["GATE_2_DIRECTION_UNCERTAINTY"] is False

    cls, gates = run(relative_mae_improvement_value=0.0, relative_mae_ci_lower=-0.01)
    assert cls == CLASS_NO_EVIDENCE
    assert gates["GATE_3_PREDICTIVE_SIGN"] is False
    assert gates["GATE_5_MATERIALITY"] is False

    cls, gates = run(relative_mae_improvement_value=0.02)
    assert gates["GATE_5_MATERIALITY"] is True
    assert gates["GATE_3_PREDICTIVE_SIGN"] is True

    cls, gates = run(relative_mae_improvement_value=0.019999)
    assert gates["GATE_5_MATERIALITY"] is False
    assert cls == CLASS_NO_EVIDENCE

    cls, gates = run(relative_mae_ci_lower=0.0)
    assert gates["GATE_4_PREDICTIVE_UNCERTAINTY"] is False
    assert cls == CLASS_NO_EVIDENCE

    cls, gates = run(year_relative_mae={2022: 0.03, 2023: 0.01, 2024: -0.02})
    assert gates["GATE_6_TEMPORAL_STABILITY"] is False
    assert cls == CLASS_NO_EVIDENCE

    cls, gates = run(year_relative_mae={2022: 0.03, 2023: -0.01, 2024: -0.01})
    assert gates["GATE_6_TEMPORAL_STABILITY"] is False

    cls, gates = run(year_relative_mae={2022: 0.03, 2023: 0.01, 2024: -0.01})
    assert gates["GATE_6_TEMPORAL_STABILITY"] is True

    cls, gates = run(year_relative_mae={2022: 0.03, 2023: 0.01, 2024: 0.02})
    assert gates["GATE_6_TEMPORAL_STABILITY"] is True

    cls, gates = run(integrity_ok=False)
    assert cls == CLASS_INCOMPLETE
    assert CLASS_PROMOTED != CLASS_NO_EVIDENCE


def test_no_near_pass_states_and_result_schema_not_instantiated():
    schema = result_schema()
    for key in (
        "research_id",
        "prereg_md_sha256",
        "classification",
        "protected_oos_touched",
        "scientific_consumed",
        "gates",
        "bootstrap_cis",
    ):
        assert key in schema
        assert schema[key] is None
    with pytest.raises(
        (Market05IntegrityError, Market05AuthorityError),
        match="RESULT_INSTANTIATION_FORBIDDEN|RESULT_ARTIFACT_MUST_NOT_EXIST",
    ):
        instantiate_scientific_result({"classification": CLASS_PROMOTED})
    for forbidden in ("NEAR_PASS", "PROMISING", "MIXED", "PARTIAL_PASS"):
        assert forbidden not in {CLASS_PROMOTED, CLASS_NO_EVIDENCE, CLASS_INCOMPLETE}


def _synthetic_dev_rows() -> list[EligibleRow]:
    rows = []
    dates = [
        (2020, 1, 3), (2020, 2, 1), (2020, 4, 1), (2020, 6, 1), (2020, 8, 1), (2020, 10, 1), (2020, 12, 1),
        (2021, 1, 1), (2021, 3, 1), (2021, 5, 1), (2021, 7, 1), (2021, 9, 1), (2021, 11, 1),
        (2022, 1, 1), (2022, 3, 1), (2022, 6, 1), (2022, 9, 1), (2022, 12, 1),
        (2023, 1, 1), (2023, 3, 1), (2023, 6, 1), (2023, 9, 1), (2023, 12, 1),
        (2024, 1, 1), (2024, 3, 1), (2024, 6, 1), (2024, 9, 1), (2024, 12, 1), (2024, 12, 31),
    ]
    for i, (y, m, d) in enumerate(dates):
        eth = -0.4 + 0.05 * i
        rows.append(
            EligibleRow(
                t_ms=_ms(y, m, d),
                btc_side=1.0 if i % 2 == 0 else -1.0,
                abs_z_btc=0.4 + 0.21 * ((i * 3) % 7),
                rv_btc_24h=0.008 + 0.0017 * ((i * 5) % 11),
                eth_confirmation=eth,
                y=0.04 + 0.006 * i - 0.05 * eth + 0.004 * ((i * 3) % 7),
            )
        )
    return rows


def test_synthetic_end_to_end_evaluator_does_not_use_real_data():
    rows = _synthetic_dev_rows()
    rng = SplitMix64(RANDOM_SEED)
    result = evaluate_prepared_rows(
        rows,
        predictive_replicates=8,
        coefficient_replicates=8,
        block_length=2,
        rng=rng,
    )
    assert result["research_id"] == RESEARCH_ID
    assert result["candidate_column_names"][ETH_CONFIRMATION_COL] == "ETH_CONFIRMATION"
    assert result["predictive_bootstrap_refit"] is False
    assert result["coefficient_bootstrap_refit"] is True
    assert result["classification"] in {CLASS_PROMOTED, CLASS_NO_EVIDENCE, CLASS_INCOMPLETE}
    assert set(result["YEAR_RELATIVE_MAE_IMPROVEMENT"]) == {2022, 2023, 2024}


def test_coefficient_bootstrap_invalid_replicate_is_incomplete_not_dropped():
    rows = [
        EligibleRow(_ms(2022, 1, 1 + i), 1.0, 1.0, 0.02, 0.1 * i, 0.05)
        for i in range(6)
    ]
    with pytest.raises(Market05IntegrityError, match="invalid_coefficient_bootstrap_replicate"):
        coefficient_bootstrap(
            rows, block_length=2, replicates=3, rng=SplitMix64(RANDOM_SEED), refit=True
        )
    with pytest.raises(Market05IntegrityError, match="must refit"):
        coefficient_bootstrap(
            rows, block_length=2, replicates=1, rng=SplitMix64(RANDOM_SEED), refit=False
        )


def test_lookback_and_midnight_mutations_would_fail():
    assert LOOKBACK_MS != 12 * 60 * 60 * 1000
    assert N_FEATURE_BARS != 720
    t = _ms(2021, 6, 1, 12, 0)
    with pytest.raises(Market05DecisionBoundError):
        assert_development_decision_time(t)
    assert DECISION_TIME != "12:00:00 UTC"
