"""MARKET-03 preregistration-design tests.

Does not run EmaCross/EmaCrossFunding, construct trades, or compute
Signalbot strategy returns/drawdown/Sharpe. This file tests the design
unit bytes; a later unit may write the live preregistration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.md"
JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.json"

EXPECTED_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXPECTED_TREE = "f7717e681c911ea3ccce15492246053cf15883cb"
EXPECTED_SPOT = (
    "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
)
EXPECTED_FUNDING_JSONL = (
    "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"
)
EXPECTED_JSON_SHA256 = (
    "91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_design_verdict_and_stop_flags():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    assert payload["design_verdict"] == "READY_FOR_MARKET_03_PREREG"
    assert payload["design_verdict_letter"] == "A"
    assert payload["status"] == "PREREG_DESIGN_COMPLETE_NOT_PREREGISTERED"
    assert payload["replication_level"] == "LEVEL_2_FAITHFUL_REIMPLEMENTATION"
    assert payload["scientific_identity"] == "EXTERNAL_HISTORICAL_CLAIM_REPRODUCTION"
    assert payload["addresses"] == "A_REPRODUCE_FINAL_PUBLISHED_STRATEGY_CLAIM"
    assert payload["does_not_address"] == "B_VALIDATE_AUTHOR_STRATEGY_SELECTION_PROCESS"
    assert payload["MARKET_03_STRATEGY_EXECUTED"] is False
    assert payload["MARKET_03_OUTCOMES_INSPECTED"] is False
    assert payload["MARKET_03_PARAMETER_SEARCH"] is False
    assert payload["MARKET_03_PREREGISTERED"] is False
    assert payload["MARKET_03_ARMED"] is False
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["final_prereg_written"] is False
    assert payload["implemented"] is False
    assert payload["material_execution_semantic_unresolved"] is False
    assert _sha256(JS) == EXPECTED_JSON_SHA256


def test_pinned_source_and_intervals():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    src = payload["pinned_external_source"]
    assert src["repo"] == "https://github.com/wiktorj137/btc-strategy-lab"
    assert src["commit"] == EXPECTED_COMMIT
    assert src["tree"] == EXPECTED_TREE
    assert src["family"] == "EmaCross vs EmaCrossFunding"
    assert src["replaced"] is False
    ev = payload["intervals"]["evaluation_interval"]
    assert ev["start_inclusive"] == "2019-10-01T00:00:00Z"
    assert ev["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert ev["matches_author_full_headline"] is False
    warm = payload["intervals"]["warmup_interval"]
    assert warm["start_inclusive"] == "2019-08-07T20:00:00Z"
    assert warm["end_exclusive"] == "2019-10-01T00:00:00Z"
    assert warm["contributes_to_performance_metrics"] is False
    conflict = payload["protected_oos_conflict"]
    assert conflict["headline_overlaps_protected_oos"] is True
    assert conflict["protected_oos_opened"] is False
    assert conflict["resolution"] == (
        "TRUNCATE_TO_AUTHORIZED_INTERVAL_DO_NOT_OPEN_PROTECTED_OOS"
    )


def test_semantics_claim_and_classification():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    sem = payload["strategy_semantics"]
    assert sem["market"] == "Binance SPOT BTC/USDT"
    assert sem["timeframe"] == "1h"
    assert sem["ema_period"] == 600
    assert sem["exit_threshold_pct"] == 2.0
    assert sem["stoploss"] == -0.15
    assert sem["trailing_stop"] is True
    assert sem["trailing_stop_positive"] is None
    assert sem["trailing_stop_positive_offset"] == 0.0
    assert sem["trailing_only_offset_is_reached"] is False
    assert sem["shorts"] is False
    assert sem["max_open_trades"] == 1
    assert sem["fee_per_side"] == 0.001
    assert sem["startup_candle_count"] == 1300
    assert sem["process_only_new_candles"] is True
    assert sem["entry_fill"] == "open of the next candle"
    assert sem["same_candle_evaluation_sequence"] == [
        "exit_signal",
        "stoploss",
        "roi",
        "trailing_stoploss",
    ]
    fund = payload["funding_semantics"]
    assert fund["field"] == "fundingRate"
    assert fund["timestamp_field"] == "fundingTime"
    assert fund["threshold"] == 55
    assert fund["missing_percentile_allows_entry"] is True
    assert fund["filter_affects_entries_only"] is True
    assert fund["current_observation_enters_own_percentile"] is True
    assert fund["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert fund["assumption_does_not_establish_zero_latency_availability"] is True
    claim = payload["primary_external_claim"]
    assert claim["author_mdd_baseline_pct"] == -49.4
    assert claim["author_mdd_filtered_pct"] == -33.8
    assert claim["author_abs_reduction_pp"] == 15.6
    assert claim["author_rel_reduction_pct_1dp"] == 31.6
    assert claim["arithmetic_verified"] is True
    assert claim["not_return_improvement"] is True
    clf = payload["primary_classification"]
    assert clf["structure"] == "DIRECTION_PRIMARY_MAGNITUDE_DESCRIPTIVE"
    assert clf["binary_magnitude_tolerance_invented"] is False
    assert "REPRODUCED_DIRECTION" in clf["labels"]
    assert "NOT_REPRODUCED_DIRECTION" in clf["labels"]
    assert payload["magnitude_fidelity"]["role"] == "DESCRIPTIVE_NOT_A_GATE"
    assert payload["secondary_metrics"]["role"] == "DESCRIPTIVE_NOT_SUCCESS_CRITERIA"
    assert payload["secondary_metrics"][
        "high_return_plus_failed_mdd_direction_remains_failure"
    ] is True
    assert payload["statistical_inference"]["p_value"] is False
    assert payload["statistical_inference"]["bootstrap"] is False
    assert payload["statistical_inference"]["market_01_02_machinery_imported"] is False
    assert payload["gap_and_degenerate_row_policy"]["synthesize_missing_hours"] is False
    assert payload["gap_and_degenerate_row_policy"]["degenerate_row"][
        "policy"
    ] == "RETAIN_UNREPAIRED"
    auth = payload["funding_dataset_authority"]
    assert auth["b2_06_is_not_market_03_authority"] is True
    assert auth["required_before_arm"] is True
    assert auth["named_snapshot_identity_materialized"] is False
    assert auth["acquired_rest_jsonl_sha256"] == EXPECTED_FUNDING_JSONL
    assert auth["spot_snapshot_id"] == EXPECTED_SPOT
    assert auth["spot_currently_scientifically_bound"] is False
    assert payload["program_level"]["market_03_is_not_a_rescue_experiment"] is True
    assert payload["mdd_definition"]["not_freqtrade_absolute_drawdown_percent"] is True


def test_markdown_binds_verdict_and_records_design_unit_stop():
    text = MD.read_text(encoding="utf-8")
    assert "READY_FOR_MARKET_03_PREREG" in text
    assert "DESIGN_VERDICT = READY_FOR_MARKET_03_PREREG" in text
    assert EXPECTED_COMMIT in text
    assert "MARKET_03_STRATEGY_EXECUTED     = NO" in text
    assert "MARKET_03_PREREGISTERED         = NO" in text
    assert "PROTECTED_OOS_TOUCHED           = NO" in text
    assert "HEADLINE_OVERLAPS_PROTECTED_OOS = YES" in text
    assert "STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN" in text
    assert "does **not** write the final preregistration" in text
    assert "91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57" in text
    payload = json.loads(JS.read_text(encoding="utf-8"))
    assert payload["final_prereg_written"] is False
    assert payload["MARKET_03_PREREGISTERED"] is False


def test_outcome_blindness_flags_are_all_false():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    flags = payload["outcome_blindness"]
    assert flags == {
        "emacross_executed": False,
        "emacrossfunding_executed": False,
        "strategy_trades": False,
        "strategy_returns": False,
        "strategy_drawdown": False,
        "sharpe_sortino": False,
        "parameter_sensitivity": False,
        "protected_oos_inspected": False,
    }
    # Design may name metrics; it must not record observed Signalbot outcomes.
    assert "OBS_MDD_BASELINE" not in payload
    assert payload.get("observed_mdd_baseline") is None
    assert payload.get("observed_mdd_filtered") is None
