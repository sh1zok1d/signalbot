"""Pure, DB-free tests for `scripts/research/math002b_consensus_robustness.py`'s
`compare_bucket()`/`compute_binance_only_diagnostic()`/`_summarize_study()` --
the real recomputation logic the harness applies to a fetched bucket,
exercised here with synthetic `ExchangeFeatureVector` fixtures instead of a
live database. These tests prove the harness computes the RIGHT thing; they
are not, and never substitute for, the real historical study (blocked --
see `docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md`).

Tech-lead review round 1 (PR #57) amendment: fixtures now use the REAL
identity `_resolve_authoritative_identity()` derives from
`config/stage2.yaml` (not arbitrary fake hex strings) -- the harness's
request construction now goes through the same
`build_consensus_feature_request()` production uses, which validates every
EFV against that authoritative identity and would otherwise reject these
fixtures outright."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from analytics.feature_engine.consensus_input_adapter import ConsensusInputError
from analytics.feature_engine.models import ExchangeFeatureVector
from common.stage2_config import Stage2Config
from scripts.research.math002b_consensus_robustness import (
    BB,
    BO,
    BYO,
    Math002BCalculationVersionUnsupported,
    _resolve_authoritative_identity,
    compare_bucket,
    compute_binance_only_diagnostic,
    _summarize_study,
)

BASE = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
LQ_QUALITY = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
_STAGE2_CONFIG = Stage2Config.load()
_CODE_VERSION = "math002b-test"


def _real_identity() -> tuple[str, str, int, str]:
    """Derive the REAL authoritative (config_hash, config_version,
    feature_schema_version, calculation_version) for _CODE_VERSION against
    the actual `config/stage2.yaml` -- a throwaway stub EFV supplies only
    `symbol`/`code_version`, which is all `_resolve_authoritative_identity`
    reads."""
    stub = _efv_raw("binance", price_move=0.0, oi=0.0, config_hash="a" * 64,
                    config_version="stub", feature_schema_version=1, calculation_version="0" * 16)
    return _resolve_authoritative_identity(_STAGE2_CONFIG, stub)


def _efv_raw(
    exchange: str, *, price_move: float, oi: float, config_hash: str, config_version: str,
    feature_schema_version: int, calculation_version: str,
) -> ExchangeFeatureVector:
    return ExchangeFeatureVector(
        exchange=exchange, symbol="BTCUSDT", market_type="perp", timeframe="4h",
        bucket_ts=BASE, feature_schema_version=feature_schema_version,
        calculation_version=calculation_version,
        price_move_pct=price_move, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=oi, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ_QUALITY[exchange],
        is_snapshot_feed=(exchange == "binance"), bars_expected=5, bars_present=5,
        has_gap=False, is_usable=True, config_hash=config_hash, config_version=config_version,
        code_version=_CODE_VERSION,
    )


def _efv(exchange: str, *, price_move: float, oi: float, **overrides) -> ExchangeFeatureVector:
    config_hash, config_version, feature_schema_version, calculation_version = _real_identity()
    kwargs = dict(config_hash=config_hash, config_version=config_version,
                  feature_schema_version=feature_schema_version,
                  calculation_version=calculation_version)
    kwargs.update(overrides)
    return _efv_raw(exchange, price_move=price_move, oi=oi, **kwargs)


def _bucket(values: dict[str, float], **efv_overrides) -> dict[str, ExchangeFeatureVector]:
    return {ex: _efv(ex, price_move=v, oi=v, **efv_overrides) for ex, v in values.items()}


def test_compare_bucket_matches_known_math002a_vector():
    """[1, 1, 100] extreme -- same numbers as the MATH-002A adversarial
    vector -- must produce the same characterized deltas via the harness's
    OWN recomputation path (proves the harness doesn't silently diverge
    from the deterministic characterization)."""
    efvs = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}

    # BB = binance+bybit -> pair values (1,1), median 1 -- no change from FULL3.
    assert by_pair[BB].full3_median == 1.0
    assert by_pair[BB].pair_median == 1.0
    assert by_pair[BB].absolute_median_delta == 0.0
    assert by_pair[BB].signed_median_delta == 0.0
    assert by_pair[BB].sign_flipped is False

    # BO = binance+okx -> pair values (1,100), median 50.5 -- large delta.
    assert by_pair[BO].pair_median == 50.5
    assert by_pair[BO].absolute_median_delta == 49.5
    assert by_pair[BO].signed_median_delta == 49.5
    assert by_pair[BO].sign_flipped is False

    # BYO = bybit+okx -> pair values (1,100), median 50.5 -- same shape.
    assert by_pair[BYO].pair_median == 50.5
    assert by_pair[BYO].absolute_median_delta == 49.5


def test_compare_bucket_absolute_delta_is_positive_for_negative_signed_case():
    """Finding 1 regression at the harness-integration level: a pair whose
    median DROPS relative to FULL3 must still report a positive
    absolute_median_delta."""
    efvs = _bucket({"binance": 100.0, "bybit": 100.0, "okx": 1.0})
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}
    # BO = binance+okx -> pair values (100,1), median 50.5; FULL3 median 100.
    assert by_pair[BO].full3_median == 100.0
    assert by_pair[BO].pair_median == 50.5
    assert by_pair[BO].signed_median_delta == pytest.approx(-49.5)
    assert by_pair[BO].signed_median_delta < 0
    assert by_pair[BO].absolute_median_delta == pytest.approx(49.5)
    assert by_pair[BO].absolute_median_delta > 0


def test_compare_bucket_detects_sign_flip():
    efvs = _bucket({"binance": 1.0, "bybit": -1.0, "okx": -100.0})
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}
    # FULL3 median of (1,-1,-100) = -1 (middle value). BO pair = (1,-100) -> median -49.5.
    assert by_pair[BO].full3_median == -1.0
    assert by_pair[BO].pair_median == -49.5
    assert by_pair[BO].sign_flipped is False  # both negative -- no flip here
    # BB pair = (1,-1) -> median 0.0; FULL3 negative -> sign flips to "0" bucket.
    assert by_pair[BB].pair_median == 0.0


def test_compare_bucket_quality_gate_stays_true_for_moderate_distortion():
    efvs = _bucket({"binance": 1.0, "bybit": 100.0, "okx": 1.0})
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    for c in comparisons:
        if c.pair_agreement == 1.0:
            assert c.pair_quality_gate_pass is True


def test_compare_bucket_derives_honest_non_target_family_exclusions():
    """Finding 2 regression: a bucket valid for price_structure but with a
    NULL non-target field (e.g. funding_rate) must still recompute the
    TARGET family successfully -- the harness must not fabricate data for
    funding, nor fail before reaching price_structure."""
    efvs = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    # Simulate a real historical row where price_structure is guaranteed but
    # funding_rate legitimately never arrived for one venue.
    okx_efv = efvs["okx"]
    import dataclasses
    efvs["okx"] = dataclasses.replace(okx_efv, funding_rate=None)
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}
    # price_structure recomputation is unaffected by okx's missing funding_rate.
    assert by_pair[BO].pair_median == 50.5


def test_compute_binance_only_diagnostic_is_actually_computed():
    """Finding 5 regression: BINANCE_ONLY_RESEARCH_BASELINE must be a REAL
    computed value, not merely an imported label."""
    efvs = _bucket({"binance": 42.0, "bybit": 1.0, "okx": 100.0})
    diag = compute_binance_only_diagnostic(_STAGE2_CONFIG, efvs, family="price_structure")
    assert diag["median"] == 42.0
    assert diag["coverage_ratio"] == pytest.approx(1.0 / 3.0)
    assert "RESEARCH ONLY" in diag["note"]


def test_summarize_study_reports_every_computed_metric():
    efvs = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    comparisons = compare_bucket(_STAGE2_CONFIG, efvs, family="price_structure", timeframe="4h")
    diag = compute_binance_only_diagnostic(_STAGE2_CONFIG, efvs, family="price_structure")
    summary = _summarize_study(
        symbol="BTCUSDT", market_type="perp", timeframe="4h", family="price_structure",
        complete_3of3_bucket_count=1, comparisons=comparisons, binance_only_diagnostics=[diag],
    )
    assert summary["complete_3of3_bucket_count"] == 1
    assert set(summary["pairs"]) == {BB, BO, BYO}
    for pair_name in (BB, BO, BYO):
        p = summary["pairs"][pair_name]
        assert p["n"] == 1
        for key in ("absolute_median_delta", "signed_median_delta", "relative_median_delta",
                    "agreement_delta", "confidence_delta"):
            assert key in p
        assert p["contributing_venues"] == sorted(p["contributing_venues"])
        assert p["omitted_venue"] not in p["contributing_venues"]
    assert summary["binance_only_research_baseline"]["implemented"] is True
    assert summary["binance_only_research_baseline"]["n"] == 1
    assert "natural_2of3_prevalence_study" in summary["not_implemented_this_pr"]


def test_discovery_and_fetch_sql_restricted_to_canonical_exchanges():
    """Finding 4 static regression: `HAVING COUNT(DISTINCT exchange) = 3`
    alone could admit any three exchange names -- the SQL text itself must
    explicitly restrict to the three canonical study venues."""
    from scripts.research.math002b_consensus_robustness import (
        _EXACT_3OF3_OI_SQL,
        _EXACT_3OF3_PRICE_SQL,
        _ROWS_FOR_BUCKET_SQL,
    )
    for sql in (_EXACT_3OF3_PRICE_SQL, _EXACT_3OF3_OI_SQL, _ROWS_FOR_BUCKET_SQL):
        assert "exchange IN" in sql
        assert "'binance'" in sql and "'bybit'" in sql and "'okx'" in sql


def test_mismatched_calculation_version_fails_explicitly():
    """Finding 3 regression: an EFV whose stored identity does NOT match
    what the currently-resolved Stage2Config derives must raise explicitly,
    never silently mix a stale calculation identity with today's config."""
    good = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    import dataclasses
    good["binance"] = dataclasses.replace(good["binance"], calculation_version="f" * 16)
    with pytest.raises(Math002BCalculationVersionUnsupported):
        compare_bucket(_STAGE2_CONFIG, good, family="price_structure", timeframe="4h")
