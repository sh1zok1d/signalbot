"""Synthetic tests for the frozen D2 BitMEX replication evaluator.

Does not execute the scientific replication on sealed BitMEX OHLC.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pytest

from scripts.research.d2_bitmex_pre2020 import BAR_MS, FUTURE_BARS, RV_RETURN_COUNT
from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_INVALID,
    CLASS_NOT_SUPPORTED,
    CLASS_SUPPORTED,
    EXECUTION_AUTHORIZED,
    EXECUTION_PERMIT_REL,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
    N_REPLICATES,
    REPLICATION_RANDOM_SEED,
    ExecutionNotAuthorized,
    SampleIdentityError,
    assert_frozen_sample_identity,
    bars_from_canonical_jsonl,
    classify_replication,
    compute_delta,
    compute_mc_p,
    compute_mu_rule,
    construct_rows_for_decisions,
    evaluate_constructed_rows,
    execute_replication,
    load_sealed_bitmex_bars,
    practical_gate,
    rv_abstention_mask,
    statistical_gate,
    year_matched_control_masks,
    year_matched_control_replicate_means,
)
from scripts.research.d2_bitmex_replication_prereg import (
    FROZEN_EXPECTED_ELIGIBLE_N,
    FROZEN_FIRST_RULE_ELIGIBLE_T,
    FROZEN_LAST_RULE_ELIGIBLE_T,
    verify_frozen_eligibility,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    arithmetic_mae,
    btc_ret_24h,
    btc_side_from_ret,
    feature_cutoff_ms,
    get_perp_bar_ending_at,
    get_perp_bar_opening_at,
    rv_btc_24h,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar

REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
D2_RESULT = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
FEASIBILITY_JSON = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json"


def _row(
    t: datetime,
    *,
    rv: float,
    ret: float,
    severity: float,
) -> C.DiscoveryRow:
    return C.DiscoveryRow(
        t_ms=C.ms_from_utc(t),
        year=t.year,
        rv=float(rv),
        ret=float(ret),
        side=1.0 if ret > 0 else -1.0,
        severity=float(severity),
        entry_open=100.0,
        future_closes=tuple(100.0 for _ in range(FUTURE_BARS)),
    )


def _warmup_and_eligible(
    *,
    eligible_n: int = 30,
    years: tuple[int, ...] | None = None,
    rvs: Sequence[float] | None = None,
    sevs: Sequence[float] | None = None,
) -> list[C.DiscoveryRow]:
    rows: list[C.DiscoveryRow] = []
    start = datetime(2016, 5, 15, 0, 5, tzinfo=UTC)
    for i in range(C.RV_TRAILING_WINDOW):
        rows.append(_row(start + timedelta(days=i), rv=0.01 + 0.0001 * i, ret=0.01, severity=0.02))
    if years is None:
        years = tuple(2017 if i < eligible_n // 3 else 2018 if i < 2 * eligible_n // 3 else 2019 for i in range(eligible_n))
    for i in range(eligible_n):
        t = datetime(int(years[i]), 3, 1, 0, 5, tzinfo=UTC) + timedelta(days=i)
        rv = 0.05 if rvs is None else float(rvs[i])
        sev = 0.03 if sevs is None else float(sevs[i])
        rows.append(_row(t, rv=rv, ret=0.01, severity=sev))
    return rows


def _fill_grid(perp: dict[int, PerpBar], first_open: int, last_open: int, *, base: float = 100.0) -> None:
    open_ms = int(first_open)
    price = float(base)
    while open_ms <= last_open:
        price *= 1.0001
        perp[open_ms] = PerpBar(
            open_time_ms=open_ms,
            open=price,
            high=price * 1.001,
            low=price * 0.999,
            close=price * 1.00005,
        )
        open_ms += BAR_MS


def test_scientific_callables_are_frozen_reuse() -> None:
    import scripts.research.d2_bitmex_replication_evaluator as E

    assert E.SCIENTIFIC_RV is rv_btc_24h
    assert E.SCIENTIFIC_RET is btc_ret_24h
    assert E.SCIENTIFIC_SIDE is btc_side_from_ret
    assert E.SCIENTIFIC_MAE is arithmetic_mae
    assert E.SCIENTIFIC_RV_MASK is C.rv_abstention_mask
    assert E.SCIENTIFIC_CONSTRUCT_ROW is C.construct_discovery_row


def test_rv_btc_ret_side_mae_formulas() -> None:
    closes = [100.0 * (1.01 ** k) for k in range(RV_RETURN_COUNT + 1)]
    assert rv_btc_24h(closes) == pytest.approx(
        math.sqrt(sum(math.log(closes[i] / closes[i - 1]) ** 2 for i in range(1, len(closes))))
    )
    ret = btc_ret_24h(110.0, 100.0)
    assert ret == pytest.approx(math.log(1.1))
    assert btc_side_from_ret(ret) == 1.0
    assert btc_side_from_ret(-0.01) == -1.0
    with pytest.raises(Exception):
        btc_ret_24h(100.0, 100.0)
    t0 = 1_000_000_000_000
    future = [
        PerpBar(open_time_ms=t0 + k * BAR_MS, open=100.0, high=101.0, low=90.0, close=100.0)
        for k in range(FUTURE_BARS)
    ]
    assert arithmetic_mae(1.0, 100.0, future) == pytest.approx((100.0 - 90.0) / 100.0)
    future_short = [
        PerpBar(open_time_ms=t0 + k * BAR_MS, open=100.0, high=120.0, low=99.0, close=100.0)
        for k in range(FUTURE_BARS)
    ]
    assert arithmetic_mae(-1.0, 100.0, future_short) == pytest.approx((120.0 - 100.0) / 100.0)


def test_p90_trailing_250_excludes_t_and_strict_gt() -> None:
    start = datetime(2016, 5, 15, 0, 5, tzinfo=UTC)
    base: list[C.DiscoveryRow] = [
        _row(start + timedelta(days=i), rv=float(i), ret=0.01, severity=0.02)
        for i in range(C.RV_TRAILING_WINDOW)
    ]
    trailing = [row.rv for row in base]
    threshold = float(np.percentile(trailing, 90.0))
    eq_rows = base + [_row(start + timedelta(days=250), rv=threshold, ret=0.01, severity=0.1)]
    gt_rows = base + [_row(start + timedelta(days=250), rv=threshold + 1.0, ret=0.01, severity=0.2)]
    eq_mask = rv_abstention_mask(eq_rows)
    gt_mask = rv_abstention_mask(gt_rows)
    assert int(eq_mask[: C.RV_TRAILING_WINDOW].sum()) == 0
    assert not bool(eq_mask[C.RV_TRAILING_WINDOW])
    assert bool(gt_mask[C.RV_TRAILING_WINDOW])
    # Including t in the percentile would raise the threshold for a large t.
    included = float(np.percentile(trailing + [threshold + 1.0], 90.0))
    excluded = float(np.percentile(trailing, 90.0))
    assert included >= excluded
    assert (threshold + 1.0) > excluded


def test_missing_feature_or_future_path_invalid() -> None:
    t = datetime(2017, 6, 1, 0, 5, tzinfo=UTC)
    t_ms = C.ms_from_utc(t)
    e_ms = feature_cutoff_ms(t_ms)
    first_open = (e_ms - RV_RETURN_COUNT * BAR_MS) - BAR_MS
    last_open = t_ms + (FUTURE_BARS - 1) * BAR_MS
    perp: dict[int, PerpBar] = {}
    _fill_grid(perp, first_open, last_open)
    rows = construct_rows_for_decisions([t], perp)
    assert len(rows) == 1
    # Feature hole: drop a lookback open.
    missing_feature = dict(perp)
    feature_open = get_perp_bar_ending_at(perp, e_ms).open_time_ms  # type: ignore[union-attr]
    del missing_feature[feature_open]
    assert construct_rows_for_decisions([t], missing_feature) == []
    # Future hole.
    missing_future = dict(perp)
    future_open = t_ms + 10 * BAR_MS
    del missing_future[future_open]
    assert construct_rows_for_decisions([t], missing_future) == []
    # Entry bar at T is used for entry, not as a feature close at E.
    assert get_perp_bar_opening_at(perp, t_ms) is not None
    assert get_perp_bar_ending_at(perp, e_ms) is not None
    assert get_perp_bar_opening_at(perp, t_ms).open_time_ms != get_perp_bar_ending_at(perp, e_ms).open_time_ms  # type: ignore[union-attr]


def test_zero_btc_ret_row_ineligible() -> None:
    t = datetime(2017, 6, 2, 0, 5, tzinfo=UTC)
    t_ms = C.ms_from_utc(t)
    e_ms = feature_cutoff_ms(t_ms)
    first_open = (e_ms - RV_RETURN_COUNT * BAR_MS) - BAR_MS
    last_open = t_ms + (FUTURE_BARS - 1) * BAR_MS
    perp: dict[int, PerpBar] = {}
    _fill_grid(perp, first_open, last_open)
    e_bar = get_perp_bar_ending_at(perp, e_ms)
    e_24h = get_perp_bar_ending_at(perp, e_ms - FUTURE_BARS * BAR_MS)
    assert e_bar is not None and e_24h is not None
    # Force identical closes at E and E-24h → exact-zero return.
    perp[e_24h.open_time_ms] = PerpBar(
        open_time_ms=e_24h.open_time_ms,
        open=e_bar.close,
        high=e_bar.close,
        low=e_bar.close,
        close=e_bar.close,
    )
    assert construct_rows_for_decisions([t], perp) == []


def test_year_matched_k_y_and_no_pooled_k() -> None:
    years = np.asarray([2017] * 8 + [2018] * 8 + [2019] * 8)
    mask = np.zeros(24, dtype=bool)
    mask[[0, 1, 8, 16, 17, 18]] = True  # 2,1,3
    reps = year_matched_control_masks(
        years, mask, seed=REPLICATION_RANDOM_SEED, n_replicates=40
    )
    for rep in reps:
        assert int(rep[years == 2017].sum()) == 2
        assert int(rep[years == 2018].sum()) == 1
        assert int(rep[years == 2019].sum()) == 3
        assert int(rep.sum()) == 6
    helper = C.rate_matched_random_abstention(
        years, mask, seed=REPLICATION_RANDOM_SEED, n_replicates=40
    )
    for a, b in zip(reps, helper):
        assert np.array_equal(a, b)


def test_deterministic_pcg64_seed_and_control_p95() -> None:
    years = [2017, 2017, 2018, 2018, 2019, 2019]
    sev = [0.1, 0.4, 0.2, 0.5, 0.3, 0.6]
    mask = np.asarray([True, False, True, False, True, False])
    a = year_matched_control_replicate_means(
        years, sev, mask, seed=REPLICATION_RANDOM_SEED, n_replicates=25
    )
    b = year_matched_control_replicate_means(
        years, sev, mask, seed=REPLICATION_RANDOM_SEED, n_replicates=25
    )
    assert np.allclose(a, b)
    p95 = float(np.percentile(a, 95))
    mu_rule = compute_mu_rule(sev, mask)
    assert statistical_gate(mu_rule, p95) is (mu_rule > p95)
    rng = np.random.Generator(np.random.PCG64(REPLICATION_RANDOM_SEED))
    rng2 = np.random.default_rng(REPLICATION_RANDOM_SEED)
    assert rng.integers(0, 10_000) == rng2.integers(0, 10_000)


def test_mc_p_and_gates_and_classification() -> None:
    ctrl = np.asarray([0.10, 0.11, 0.12, 0.20])
    mu = 0.20
    assert compute_mc_p(ctrl, mu) == pytest.approx((1.0 + 1.0) / 5.0)
    assert statistical_gate(0.21, 0.20) is True
    assert statistical_gate(0.20, 0.20) is False
    assert practical_gate(0.03, 0.10) is True
    assert practical_gate(0.01, 0.10) is False
    assert classify_replication(integrity_invalid=True, statistical=True, practical=True) == CLASS_INVALID
    assert classify_replication(integrity_invalid=False, statistical=True, practical=True) == CLASS_SUPPORTED
    assert classify_replication(integrity_invalid=False, statistical=True, practical=False) == CLASS_NOT_SUPPORTED
    assert classify_replication(integrity_invalid=False, statistical=False, practical=True) == CLASS_NOT_SUPPORTED
    # F12: yearly signs cannot rescue.
    assert (
        classify_replication(
            integrity_invalid=False,
            statistical=False,
            practical=False,
            yearly_positive=[True, True, True],
        )
        == CLASS_NOT_SUPPORTED
    )


def test_evaluate_constructed_rows_warmup_and_identity() -> None:
    rows = _warmup_and_eligible(eligible_n=9, years=(2017,) * 3 + (2018,) * 3 + (2019,) * 3)
    # High RV on last three so the rule fires.
    for i in range(3):
        idx = C.RV_TRAILING_WINDOW + 6 + i
        t = C.utc_from_ms(rows[idx].t_ms)
        rows[idx] = _row(t, rv=10.0, ret=0.01, severity=0.50)
    evaluated = evaluate_constructed_rows(
        rows, seed=REPLICATION_RANDOM_SEED, n_replicates=30, enforce_sample_identity=False
    )
    assert evaluated["WARMUP_N"] == 250
    assert evaluated["ELIGIBLE_N"] == 9
    assert evaluated["ABSTAIN_COUNT"] >= 1
    assert evaluated["YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY"] is True
    assert evaluated["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert set(evaluated["YEARLY_DIAGNOSTICS"]) == {"2017", "2018", "2019"}
    with pytest.raises(SampleIdentityError):
        assert_frozen_sample_identity(rows[C.RV_TRAILING_WINDOW :])
    invalid = evaluate_constructed_rows(
        rows, seed=REPLICATION_RANDOM_SEED, n_replicates=10, enforce_sample_identity=True
    )
    assert invalid["CLASSIFICATION"] == CLASS_INVALID
    assert invalid["integrity_invalid"] is True


def test_bitmex_timestamp_keyed_by_open_not_bucket_end() -> None:
    end = datetime(2017, 1, 1, 0, 10, tzinfo=UTC)
    open_ms = int(end.timestamp() * 1000) - BAR_MS
    line = json.dumps(
        {
            "source_timestamp": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "open_time_ms": open_ms,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "trades": 0,
        }
    ).encode("utf-8")
    bars = bars_from_canonical_jsonl(line + b"\n")
    assert open_ms in bars
    assert int(end.timestamp() * 1000) not in bars
    assert bars[open_ms].open_time_ms == open_ms


def test_real_execution_refused_and_no_permit() -> None:
    assert EXECUTION_AUTHORIZED is False
    assert not (REPO / EXECUTION_PERMIT_REL).is_file()
    with pytest.raises(ExecutionNotAuthorized, match="NO_EXECUTION_PERMIT"):
        execute_replication(repo=REPO)
    with pytest.raises(ExecutionNotAuthorized, match="NO_EXECUTION_PERMIT"):
        load_sealed_bitmex_bars(REPO, execution_authority={"run_identity": "nope"})


def test_frozen_timestamp_census_unchanged() -> None:
    verified = verify_frozen_eligibility(REPO)
    assert verified["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"] == FROZEN_EXPECTED_ELIGIBLE_N
    assert verified["legal"]["FIRST_RULE_ELIGIBLE_T"] == "2017-01-24T00:05:00.000Z"
    assert verified["legal"]["LAST_RULE_ELIGIBLE_T"] == "2019-12-30T00:05:00.000Z"
    assert FROZEN_FIRST_RULE_ELIGIBLE_T.year == 2017
    assert FROZEN_LAST_RULE_ELIGIBLE_T.year == 2019
    assert FROZEN_CANONICAL_JSONL_SHA256 == "b145013cbcda34294104a0234c89fa9e27965bded66e3bc18b23753dde03fd0f"
    assert FROZEN_CANONICAL_GZ_SHA256 == "8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa"
    assert N_REPLICATES == 10_000
    assert REPLICATION_RANDOM_SEED == 20260921125


def test_discovery_and_feasibility_bytes_unchanged() -> None:
    import subprocess

    for rel in (D2_RESULT, FEASIBILITY_JSON):
        committed = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)
        assert (REPO / rel).read_bytes() == committed
    prereg = "docs/research/D2_BITMEX_REPLICATION_PREREG.json"
    assert (REPO / prereg).read_bytes() == subprocess.check_output(["git", "show", f"HEAD:{prereg}"], cwd=REPO)


def test_review_artifact_preserves_stub_lineage() -> None:
    path = REPO / "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.json"
    if not path.is_file():
        pytest.skip("review JSON not written yet")
    review = json.loads(path.read_text(encoding="utf-8"))
    stub = review["ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256"][
        "scripts/research/d2_bitmex_replication_evaluator.py"
    ]
    final = review["FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"][
        "scripts/research/d2_bitmex_replication_evaluator.py"
    ]
    assert stub == "e132f5ee24029b18aa971c4dda6a2e453282038a9527d8362d6656ecd40b75de"
    assert final != stub
    assert review["IMPLEMENTATION_REVIEW"] == "PASS"
    assert review["EXECUTION_READY"] is True
    assert review["EXECUTION_AUTHORIZED"] is False
    assert review["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert review["CLASSIFICATION_ASSIGNED"] is None
    binding = json.loads((REPO / "docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json").read_text())
    assert binding["ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256"]["scripts/research/d2_bitmex_replication_evaluator.py"] == stub
    assert binding["EXECUTION_AUTHORIZED"] is False
    assert binding["EXECUTION_READY"] is True



def test_no_binance_protected_open() -> None:
    from scripts.research.d2_confirmation_feasibility_and_design import (
        ProtectedPriceRefused,
        refuse_protected_price_path,
    )
    from scripts.research.d2_bitmex_pre2020 import ProtectedBinanceRefused

    bad = REPO / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused, ProtectedBinanceRefused)):
        refuse_protected_price_path(bad)
