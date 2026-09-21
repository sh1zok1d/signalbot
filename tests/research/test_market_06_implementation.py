"""Outcome-blind MARKET-06 implementation tests. Synthetic fixtures only.

Does not parse retained 2022-2024 MARKET-06 OHLC for science, compute real
dislocation/MAE/betas, create ARM/RESULT, or open 2025/2026.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research import market_06_cross_venue_dislocation_authority as authority
from scripts.research import market_06_cross_venue_dislocation_bootstrap as bootstrap
from scripts.research import market_06_cross_venue_dislocation_evaluator as ev
from scripts.research import market_06_cross_venue_dislocation_parsers as parsers
from scripts.research import market_06_cross_venue_dislocation_runner as runner
from scripts.research.market_06_cross_venue_dislocation_authority import (
    CLASS_INCOMPLETE,
    CLASS_NO_EVIDENCE,
    CLASS_PROMOTED,
    Market06ExecutionNotAuthorized,
    Market06IncompleteExecution,
    Market06RowIneligible,
)
from scripts.research.market_06_cross_venue_dislocation_evaluator import EligibleRow
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar
from scripts.research.market_06_year_stratified_circular_mbb import (
    BLOCK_LENGTH_DAYS,
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
)


REPO = Path(__file__).resolve().parents[2]
PRODUCTION_MODULES = (
    REPO / "scripts/research/market_06_cross_venue_dislocation_authority.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_parsers.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_runner.py",
    REPO / "scripts/research/market_06_canonical_reconstruction.py",
    REPO / "scripts/research/market_06_execution_lifecycle.py",
    REPO / "scripts/research/market_06_git_authority.py",
)


def _row(
    *,
    t_ms: int,
    split: str,
    year: int,
    btc_side: float = 1.0,
    abs_btc_ret_24h: float,
    rv_btc_24h: float,
    abs_dislocation_z: float,
    y: float,
) -> EligibleRow:
    return EligibleRow(
        t_ms=t_ms,
        split=split,
        year=year,
        btc_side=btc_side,
        abs_btc_ret_24h=abs_btc_ret_24h,
        rv_btc_24h=rv_btc_24h,
        abs_dislocation_z=abs_dislocation_z,
        y=y,
    )


def _synthetic_rows(*, n_train: int = 40, n_2023: int = 24, n_2024: int = 24) -> list[EligibleRow]:
    rows: list[EligibleRow] = []
    day = 86_400_000
    fixture = np.random.default_rng(7)

    def _pack(n: int, t0: int, split: str, year: int) -> None:
        for i in range(n):
            z = 0.05 + 0.8 * fixture.random()
            ret = 0.002 + 0.03 * fixture.random()
            rv = 0.01 + 0.04 * fixture.random()
            side = 1.0 if fixture.random() < 0.5 else -1.0
            y = 0.04 + 0.5 * z + 0.05 * ret + 0.02 * rv + 0.01 * fixture.random()
            rows.append(
                _row(
                    t_ms=t0 + i * day,
                    split=split,
                    year=year,
                    btc_side=side,
                    abs_btc_ret_24h=float(ret),
                    rv_btc_24h=float(rv),
                    abs_dislocation_z=float(z),
                    y=float(y),
                )
            )

    _pack(
        n_train,
        int(datetime(2022, 2, 1, 0, 5, tzinfo=timezone.utc).timestamp() * 1000),
        "TRAIN",
        2022,
    )
    _pack(
        n_2023,
        int(datetime(2023, 1, 1, 0, 5, tzinfo=timezone.utc).timestamp() * 1000),
        "HOLDOUT_2023",
        2023,
    )
    _pack(
        n_2024,
        int(datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc).timestamp() * 1000),
        "HOLDOUT_2024",
        2024,
    )
    return rows


def test_prereg_authority_from_git_objects_not_caller_dicts():
    """Prereg identity is still Git-bound; caller dicts still cannot override.

    verify_prereg_authority() now raises Market06AuthorityError because a
    canonical RESULT exists -- that is the correct terminal behaviour, so
    the Git-object bindings are checked directly instead.
    """

    with pytest.raises(authority.Market06AuthorityError) as exc:
        authority.verify_prereg_authority()
    assert "MARKET_06_RESULT_EXISTS" in str(exc.value)

    heads = authority.verify_live_prereg_freeze_objects()
    assert heads["prereg_freeze_head"] == authority.PREREG_FREEZE_HEAD
    assert heads["prereg_freeze_tree"] == authority.PREREG_FREEZE_TREE
    assert heads["prereg_content_head"] == authority.PREREG_CONTENT_HEAD
    payload = authority.load_frozen_prereg_json()
    assert payload["amendment_of"]["amendment_id"] == authority.LIVE_AMENDMENT_ID
    assert payload["data"]["snapshot_id"] == authority.SNAPSHOT_ID
    assert (
        payload["data"]["durable_evidence_root_sha256"]
        == authority.DURABLE_EVIDENCE_ROOT_SHA256
    )
    with pytest.raises(Market06ExecutionNotAuthorized):
        authority.verify_prereg_authority(expected_sha256="deadbeef")


def test_data_authority_bound_from_git_without_scientific_parse():
    report = authority.verify_git_bound_data_authority(hash_raw_objects=False)
    assert report["binance_object_count"] == 36
    assert report["okx_page_count"] == 1053
    assert report["snapshot_id"] == authority.SNAPSHOT_ID
    assert report["scientific_parse"] is False
    hashes = authority.retained_payload_sha256s()
    assert len(hashes) == 36 + 1053


def test_canonical_result_exists_and_blocks_further_execution():
    """Terminal state: the canonical RESULT exists and is a hard blocker."""

    with pytest.raises(authority.Market06AuthorityError) as exc:
        authority.assert_no_canonical_result()
    assert "MARKET_06_RESULT_EXISTS" in str(exc.value)

    research = REPO / "docs" / "research"
    assert (research / "MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.json").exists()
    assert (research / "MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.md").exists()
    # the superseded legacy artifact names were never used
    for name in ("MARKET_06_ARM.md", "MARKET_06_ARM.json",
                 "MARKET_06_RESULT.md", "MARKET_06_RESULT.json"):
        assert not (research / name).exists()


def test_d_formula_and_8640_reference_excludes_d_e():
    perp_close_e = 101.0
    spot_close_e = 100.0
    d_e = ev.dislocation_d(perp_close_e, spot_close_e)
    assert d_e == pytest.approx(math.log(101.0 / 100.0))
    ref = [0.01 + 0.0001 * i for i in range(ev.REFERENCE_COUNT)]
    assert ev.REFERENCE_COUNT == 8640
    center, mad, scale, z = ev.robust_dislocation_z(d_e, ref)
    assert d_e not in ref
    assert scale == pytest.approx(1.4826 * mad)
    assert z == pytest.approx((d_e - center) / (1.4826 * mad))
    with pytest.raises(Market06IncompleteExecution):
        ev.robust_dislocation_z(d_e, ref[:-1])
    raw_mad_denominator = (d_e - center) / mad
    assert z != pytest.approx(raw_mad_denominator)


def test_raw_mad_denominator_is_not_the_z_scale():
    assert ev.MAD_CONSISTENCY_CONSTANT == 1.4826
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "1.4826" in src
    assert "MAD_CONSISTENCY_CONSTANT * mad" in src


def test_daily_0005_grid_and_t_minus_5m_cutoff():
    t = datetime(2022, 2, 1, 0, 5, tzinfo=timezone.utc)
    assert ev.is_forbidden_decision(t) is None
    t_ms = int(t.timestamp() * 1000)
    assert ev.feature_cutoff_ms(t_ms) == t_ms - parsers.BAR_MS
    noon = datetime(2022, 2, 1, 12, 0, tzinfo=timezone.utc)
    assert ev.is_forbidden_decision(noon) == "NOT_DAILY_0005"
    days = ev.decision_times_for_split("TRAIN")
    assert days[0] == ev.TRAIN_START
    assert days[-1] == ev.TRAIN_END
    assert all(moment.hour == 0 and moment.minute == 5 for moment in days)
    assert all(not (moment.month == 12 and moment.day == 31) for moment in days)


def test_2025_and_2026_rejected():
    assert ev.is_forbidden_decision(datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc))
    assert ev.is_forbidden_decision(datetime(2026, 6, 1, 0, 5, tzinfo=timezone.utc))
    dec31 = datetime(2022, 12, 31, 0, 5, tzinfo=timezone.utc)
    assert ev.is_forbidden_decision(dec31) == "DECEMBER_31_FORBIDDEN"


def test_btc_ret_abs_control_and_288_rv_returns():
    ret = ev.btc_ret_24h(110.0, 100.0)
    assert ret == pytest.approx(math.log(1.1))
    assert ev.btc_side_from_ret(ret) == 1.0
    assert ev.btc_side_from_ret(-0.2) == -1.0
    with pytest.raises(Market06RowIneligible):
        ev.btc_ret_24h(100.0, 100.0)
    closes = [100.0 * math.exp(0.001 * i) for i in range(289)]
    rv = ev.rv_btc_24h(closes)
    rs = [math.log(closes[i] / closes[i - 1]) for i in range(1, 289)]
    assert len(rs) == 288
    assert rv == pytest.approx(math.sqrt(sum(r * r for r in rs)))
    assert list(ev.BASELINE_COLUMNS) == [
        "INTERCEPT",
        "BTC_SIDE",
        "ABS_BTC_RET_24H_STD",
        "RV_BTC_24H_STD",
    ]
    assert "ABS_Z_BTC" not in ev.BASELINE_COLUMNS
    assert ev.CANDIDATE_COLUMNS[-1] == "ABS_DISLOCATION_Z_STD"


def test_arithmetic_long_and_short_mae_288_future_bars():
    entry = 100.0
    future = [
        PerpBar(open_time_ms=i * parsers.BAR_MS, open=100.0, high=101.0, low=90.0 + i * 0.01, close=100.0)
        for i in range(288)
    ]
    long_y = ev.arithmetic_mae(1.0, entry, future)
    assert long_y == pytest.approx((100.0 - min(bar.low for bar in future)) / 100.0)
    short_future = [
        PerpBar(open_time_ms=i * parsers.BAR_MS, open=100.0, high=110.0 - i * 0.01, low=99.0, close=100.0)
        for i in range(288)
    ]
    short_y = ev.arithmetic_mae(-1.0, entry, short_future)
    assert short_y == pytest.approx((max(bar.high for bar in short_future) - 100.0) / 100.0)
    with pytest.raises(Market06IncompleteExecution):
        ev.arithmetic_mae(1.0, entry, future[:10])


def test_same_support_no_fill_missing_reference_makes_row_ineligible():
    """Bar-end semantics: the oldest reference OPENS at E - 8641*5m."""

    t = datetime(2022, 2, 1, 0, 5, tzinfo=timezone.utc)
    t_ms = int(t.timestamp() * 1000)
    e_ms = ev.feature_cutoff_ms(t_ms)
    perp: dict[int, PerpBar] = {}
    spot: dict[int, float] = {}
    oldest_reference_open = ev.bar_open_for_close_at(e_ms - ev.REFERENCE_COUNT * parsers.BAR_MS)
    end = t_ms + ev.FUTURE_BARS * parsers.BAR_MS
    ts = oldest_reference_open
    idx = 0
    while ts < end:
        price = 100.0 + 0.01 * idx
        perp[ts] = PerpBar(ts, price, price + 1.0, price - 1.0, price + 0.2)
        spot[ts] = price
        ts += parsers.BAR_MS
        idx += 1
    assert ev.construct_row_or_none(t_ms, "TRAIN", perp, spot) is not None
    # dropping any single required bar makes the row ineligible for BOTH models
    missing = ev.bar_open_for_close_at(e_ms - 10 * parsers.BAR_MS)
    del perp[missing]
    assert ev.construct_row_or_none(t_ms, "TRAIN", perp, spot) is None


def test_reference_window_does_not_include_d_e():
    """D_E is excluded from REF, addressed by BOUNDARY not by stored key.

    The fixture keys bars by open_time and reasons about bar_end, so it
    cannot pass merely because storage and lookup share a key.
    """

    t = datetime(2022, 2, 1, 0, 5, tzinfo=timezone.utc)
    t_ms = int(t.timestamp() * 1000)
    e_ms = ev.feature_cutoff_ms(t_ms)
    d_e_open = ev.bar_open_for_close_at(e_ms)
    perp: dict[int, PerpBar] = {}
    spot: dict[int, float] = {}
    ts = ev.bar_open_for_close_at(e_ms - ev.REFERENCE_COUNT * parsers.BAR_MS)
    end = t_ms + ev.FUTURE_BARS * parsers.BAR_MS
    while ts < end:
        if ts == d_e_open:
            perp_close = 200.0
            spot_close = 100.0
        else:
            k = (e_ms - ev.bar_end_for_open_at(ts)) // parsers.BAR_MS
            perp_close = 100.0
            spot_close = 100.0 * math.exp(0.001 + 0.00001 * (k % 17))
        perp[ts] = PerpBar(ts, perp_close, perp_close + 1, perp_close - 1, perp_close)
        spot[ts] = spot_close
        ts += parsers.BAR_MS
    row = ev.construct_row_or_none(t_ms, "TRAIN", perp, spot)
    assert row is not None
    d_e = math.log(200.0 / 100.0)
    ref = []
    for k in range(1, ev.REFERENCE_COUNT + 1):
        spot_close = 100.0 * math.exp(0.001 + 0.00001 * (k % 17))
        ref.append(math.log(100.0 / spot_close))
    _c, _m, _s, z = ev.robust_dislocation_z(d_e, ref)
    assert row.abs_dislocation_z == pytest.approx(abs(z))


def test_train_only_standardization_no_holdout_refit():
    rows = _synthetic_rows()
    train = [row for row in rows if row.split == "TRAIN"]
    hold = [row for row in rows if row.split != "TRAIN"]
    mean, sd = ev.fit_train_standardization(train)
    hold_mean, hold_sd = ev.fit_train_standardization(hold)
    assert not np.allclose(mean, hold_mean)
    x_hold = ev.standardize_row(hold[0], mean, sd)
    x_wrong = ev.standardize_row(hold[0], hold_mean, hold_sd)
    assert x_hold[0] == 1.0
    assert x_hold[1] == hold[0].btc_side
    assert not np.allclose(x_hold[2:], x_wrong[2:])
    assert ev.TRAIN_SD_CONVENTION == "numpy.std(x, ddof=0)"
    assert ev.TRAIN_SD_DDOF == 0


def test_exact_ols_column_order_and_candidate_adds_only_abs_dislocation_z():
    assert ev.CANDIDATE_COLUMNS == ev.BASELINE_COLUMNS + ("ABS_DISLOCATION_Z_STD",)
    rows = _synthetic_rows()
    mean, sd = ev.fit_train_standardization([r for r in rows if r.split == "TRAIN"])
    base, cand, y = ev.design_matrices([r for r in rows if r.split == "TRAIN"], mean, sd)
    assert base.shape[1] == 4
    assert cand.shape[1] == 5
    assert np.allclose(base, cand[:, :4])
    beta = bootstrap.ols_solve(cand, y)
    assert beta.shape == (5,)
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "lstsq" not in src
    assert "sklearn" not in src
    assert "ridge" not in src


def test_singular_matrix_fails_closed():
    x = np.ones((10, 2), dtype=np.float64)
    x[:, 1] = 1.0
    y = np.arange(10, dtype=np.float64)
    with pytest.raises(Market06IncompleteExecution, match="RANK_DEFICIENT"):
        bootstrap.ols_solve(x, y)


def test_no_prediction_clipping_in_evaluator():
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "clip" not in src.lower() or "prediction_clipped" in src
    assert "np.clip" not in src


def test_evaluate_year_and_pooled_mae_and_gates():
    result = ev.evaluate_from_eligible_rows(_synthetic_rows())
    assert "YEAR_2023_RELATIVE_MAE_IMPROVEMENT" in result
    assert "YEAR_2024_RELATIVE_MAE_IMPROVEMENT" in result
    assert result["RELATIVE_MAE_IMPROVEMENT"] == pytest.approx(
        1.0 - result["POOLED_MAE_CANDIDATE"] / result["POOLED_MAE_BASELINE"]
    )
    assert result["BOOTSTRAP_REPLICATES"] == 5000
    assert result["RANDOM_SEED"] == 2026092106
    assert result["BLOCK_LENGTH_DAYS"] == 14
    assert result["PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP"] is False
    assert result["PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR"] is True
    assert result["CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED"] is False
    assert result["holdout_refit"] is False
    assert result["prediction_clipped"] is False
    assert result["classification"] in {CLASS_PROMOTED, CLASS_NO_EVIDENCE}


def test_coefficient_mbb_14d_and_gate2_uses_lower_bound():
    rows = _synthetic_rows()
    result = ev.evaluate_from_eligible_rows(rows)
    assert result["gates"]["G2"] == (
        result["BETA_ABS_DISLOCATION_Z_CI95_LOW"] > 0
    )
    assert result["BETA_ABS_DISLOCATION_Z_CI95_LOW"] <= result["BETA_ABS_DISLOCATION_Z_CI95_HIGH"]
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "beta_ci_low" in src
    assert "CI95_HIGH > 0" not in src


def test_year_stratified_predictive_no_cross_year_and_n_preserved():
    loss_2023 = [(1.0, 0.8)] * 16
    loss_2024 = [(1.1, 0.9)] * 18
    rng = bootstrap.make_rng(RANDOM_SEED)
    stats = bootstrap.year_stratified_predictive_bootstrap(loss_2023, loss_2024, rng, replicates=20)
    assert stats.shape == (20,)
    from scripts.research.market_06_year_stratified_circular_mbb import (
        year_stratified_predictive_resample,
    )

    rng2 = bootstrap.make_rng(RANDOM_SEED)
    labeled_23 = [(2023, i) for i in range(16)]
    labeled_24 = [(2024, i) for i in range(18)]
    b23, b24, blocks23, blocks24 = year_stratified_predictive_resample(
        labeled_23, labeled_24, rng=rng2
    )
    assert len(b23) == 16 and len(b24) == 18
    assert all(item[0] == 2023 for item in b23)
    assert all(item[0] == 2024 for item in b24)
    for block in blocks23:
        assert all(0 <= i < 16 for i in block)
    for block in blocks24:
        assert all(0 <= i < 18 for i in block)


def test_rng_order_coefficient_then_predictive_2023_then_2024():
    assert bootstrap.RNG_ORDER[0] == "init_pcg64_once"
    assert bootstrap.RNG_ORDER[1] == "coefficient_bootstrap_5000"
    assert bootstrap.RNG_ORDER[2] == "predictive_bootstrap_5000"
    assert bootstrap.RNG_ORDER[3] == "within_predictive_replicate_sample_2023_then_2024"
    rows = _synthetic_rows()
    a = ev.evaluate_from_eligible_rows(rows)
    b = ev.evaluate_from_eligible_rows(rows)
    assert a["BETA_ABS_DISLOCATION_Z_CI95_LOW"] == b["BETA_ABS_DISLOCATION_Z_CI95_LOW"]
    assert a["RELATIVE_MAE_IMPROVEMENT_CI95_LOW"] == b["RELATIVE_MAE_IMPROVEMENT_CI95_LOW"]
    assert a["RANDOM_SEED"] == RANDOM_SEED
    assert BOOTSTRAP_REPLICATES == 5000
    assert BLOCK_LENGTH_DAYS == 14


def test_six_gates_and_2pct_threshold_and_classification_truth_table():
    assert ev.MATERIALITY_THRESHOLD == 0.02
    gates = ev.apply_six_gates(
        beta_abs_dislocation_z=0.1,
        beta_ci_low=0.01,
        pooled_improvement=0.03,
        pooled_improvement_ci_low=0.005,
        year_2023_improvement=0.01,
        year_2024_improvement=0.01,
    )
    assert gates["G5"] is True
    assert gates["G6"] is True
    assert ev.classify(gates) == CLASS_PROMOTED
    fail = ev.apply_six_gates(
        beta_abs_dislocation_z=-0.1,
        beta_ci_low=-0.2,
        pooled_improvement=-0.01,
        pooled_improvement_ci_low=-0.02,
        year_2023_improvement=-0.03,
        year_2024_improvement=0.01,
    )
    assert fail["G1"] is False
    assert fail["G6"] is False
    assert fail["G6_NO_YEAR_LE_MINUS_0_02"] is False
    assert ev.classify(fail) == CLASS_NO_EVIDENCE
    names = ("G1", "G2", "G3", "G4", "G5", "G6")
    for mask in range(64):
        bits = [(mask >> i) & 1 == 1 for i in range(6)]
        synthetic = {name: bits[i] for i, name in enumerate(names)}
        expected = CLASS_PROMOTED if all(bits) else CLASS_NO_EVIDENCE
        assert ev.classify(synthetic) == expected
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "G6_ADVERSE_YEAR_THRESHOLD" in src
    assert "<= G6_ADVERSE_YEAR_THRESHOLD" in src
    for forbidden in ("NEAR_PASS", "MIXED", "PROMISING", "PARTIAL_PASS"):
        assert forbidden not in ev.classify(gates)


def test_empty_holdout_is_incomplete():
    rows = [row for row in _synthetic_rows() if row.split == "TRAIN"]
    report = ev.safe_evaluate_from_eligible_rows(rows)
    assert report["classification"] == CLASS_INCOMPLETE


def test_binance_and_okx_parsers_on_synthetic_bytes():
    rows = [
        [1641081600000, 100, 101, 99, 100.5],
        [1641081900000, 100.5, 102, 100, 101],
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        text = "open_time,open,high,low,close\n" + "\n".join(
            ",".join(str(x) for x in row) for row in rows
        )
        archive.writestr("BTCUSDT-5m-2022-01.csv", text)
    bars = parsers.parse_binance_zip_bytes(buf.getvalue(), zip_name="BTCUSDT-5m-2022-01.zip")
    assert len(bars) == 2
    assert bars[0].close == 100.5
    body = json.dumps(
        {
            "code": "0",
            "data": [
                [1641081600000, "100", "101", "99", "100.4", "1", "1", "1", "1"],
                [1641081900000, "100.4", "102", "100", "101.1", "1", "1", "1", "1"],
            ],
        }
    ).encode("utf-8")
    spots = parsers.parse_okx_history_body(body, source="synthetic")
    assert spots[0].close == pytest.approx(100.4)
    with pytest.raises(Market06IncompleteExecution):
        parsers.parse_okx_history_body(
            json.dumps(
                {
                    "code": "0",
                    "data": [[1641081600000, "100", "101", "99", "100.4", "1", "1", "1", "0"]],
                }
            ).encode("utf-8"),
            source="unconfirmed",
        )


def test_parsers_refuse_real_retained_hashes(monkeypatch):
    """Retained bytes stay unparseable without an authenticated permit."""

    payload = b"synthetic-but-listed"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(parsers, "retained_payload_sha256s", lambda: frozenset({digest}))
    with pytest.raises(Market06ExecutionNotAuthorized):
        parsers.parse_binance_zip_bytes(payload, zip_name="BTCUSDT-5m-2022-01.zip")
    with pytest.raises(Market06ExecutionNotAuthorized):
        parsers.parse_okx_history_body(payload, source="listed")
    # a forged "permit" is not a permit
    with pytest.raises(Market06ExecutionNotAuthorized):
        parsers.parse_okx_history_body(payload, source="listed", permit={"ok": True})


def test_retained_bytes_parse_under_synthetic_authenticated_permit(monkeypatch):
    """With a genuine permit the exact canonical parser is allowed to run."""

    from scripts.research import market_06_execution_lifecycle as lifecycle

    body = json.dumps(
        {"code": "0", "data": [["1640995200000", "1", "2", "0.5", "1", "1", "1", "1", "1"]]}
    ).encode()
    digest = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(parsers, "retained_payload_sha256s", lambda: frozenset({digest}))
    permit = lifecycle.ExecutionPermit(
        run_identity="synthetic",
        arm_commit="a" * 40,
        implementation_freeze_head="b" * 40,
        implementation_freeze_tree="c" * 40,
        dataset_id=lifecycle.DATASET_ID,
        snapshot_id=lifecycle.SNAPSHOT_ID,
        durable_evidence_root_sha256=lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        authorization_kind=lifecycle.AUTHORIZATION_KIND,
        _token=lifecycle._PERMIT_TOKEN,
    )
    closes = parsers.parse_okx_history_body(body, source="listed", permit=permit)
    assert len(closes) == 1


def test_canonical_execution_refused_kwargs_env_and_cli(monkeypatch):
    """Still refused -- now because the shot is consumed, not unarmed."""

    with pytest.raises(Market06ExecutionNotAuthorized):
        ev.evaluate_canonical_market_06()
    with pytest.raises(Market06ExecutionNotAuthorized):
        ev.evaluate_canonical_market_06(authorize=True, force=True)
    with pytest.raises(Market06ExecutionNotAuthorized):
        parsers.reconstruct_canonical_dataset(execute=True)
    with pytest.raises(Market06ExecutionNotAuthorized):
        parsers.reconstruct_canonical_dataset()
    monkeypatch.setenv("MARKET_06_EXECUTE", "1")
    with pytest.raises(Market06ExecutionNotAuthorized):
        authority.refuse_canonical_execution()
    # The runner now exits on the authority error raised by the existing
    # canonical RESULT rather than on "not authorized".
    code = runner.main(["--execute", "--force"])
    assert code == 3


def test_production_modules_have_no_concatenated_then_sample_or_network():
    for path in PRODUCTION_MODULES:
        text = path.read_text(encoding="utf-8")
        assert "import concatenated_then_sample" not in text
        assert "concatenated_then_sample(" not in text
        assert "urllib" not in text
        assert "requests" not in text
        assert "binance.vision" not in text
        assert "okx.com" not in text
        assert "evaluate_v3_world" not in text
    evaluator = (
        REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py"
    ).read_text(encoding="utf-8")
    assert "concatenated_then_sample" not in evaluator


def test_bootstrap_constants_and_no_predictive_refit_in_module():
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "year_stratified_predictive_resample" in src
    assert "import concatenated_then_sample" not in src
    assert "concatenated_then_sample(" not in src
    assert "BOOTSTRAP_REPLICATES" in src
    assert "ols_solve" in src
    assert "refit predictive" not in src.lower() or "Does not refit predictive" in src


def test_f04_no_condition_number_threshold_was_introduced():
    """F-04 accepted as HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE.

    The frozen solver stays numpy.linalg.solve(X'X, X'y) with no
    conditioning cutoff, ridge, pinv, lstsq, or regularization, because no
    such threshold was preregistered.
    """

    for path in PRODUCTION_MODULES:
        text = path.read_text(encoding="utf-8")
        for forbidden in (
            "np.linalg.cond",
            "numpy.linalg.cond",
            "linalg.pinv",
            "linalg.lstsq",
            "rcond",
            "Ridge",
            "regulariz",
        ):
            assert forbidden not in text, f"{forbidden} appeared in {path.name}"
    source = (
        REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "np.linalg.solve(xtx, xty)" in source
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(
            np.column_stack([np.ones(6), np.ones(6), np.arange(6.0), np.arange(6.0)]),
            np.arange(6.0),
        )
    assert exc.value.reason == "RANK_DEFICIENT"


def test_temporal_api_is_the_only_bar_end_mapping():
    """No feature call site may derive open-time/bar-end mapping itself."""

    evaluator = (
        REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py"
    ).read_text(encoding="utf-8")
    assert "def bar_open_for_close_at" in evaluator
    assert "def get_perp_bar_ending_at" in evaluator
    assert "def get_spot_close_ending_at" in evaluator
    assert "def get_perp_bar_opening_at" in evaluator
    # the removed ad-hoc helpers must not come back
    assert "def _lookup_perp" not in evaluator
    assert "def _d_at(" not in evaluator
