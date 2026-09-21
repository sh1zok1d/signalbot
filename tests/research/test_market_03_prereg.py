"""MARKET-03 preregistration tests.

Outcome-blind. Does not execute EmaCross/EmaCrossFunding or inspect
strategy outcomes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
DESIGN_JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.json"

EXPECTED_MD_SHA256 = (
    "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
)
EXPECTED_JSON_SHA256 = (
    "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"
)
EXPECTED_MD_SIZE = 15063
EXPECTED_JSON_SIZE = 15587
EXPECTED_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXPECTED_TREE = "f7717e681c911ea3ccce15492246053cf15883cb"
EXPECTED_SPOT = (
    "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
)
EXPECTED_SPOT_DATA = (
    "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"
)
EXPECTED_FUNDING_JSONL = (
    "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"
)
EXPECTED_DESIGN_JSON = (
    "91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57"
)
EXPECTED_DESIGN_COMMIT = "9454af65398df1d3f5e0cb3af5e48c0986049d2d"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prereg() -> dict:
    return json.loads(JS.read_text(encoding="utf-8"))


def test_prereg_byte_identity():
    assert _sha256(MD) == EXPECTED_MD_SHA256
    assert _sha256(JS) == EXPECTED_JSON_SHA256
    assert MD.stat().st_size == EXPECTED_MD_SIZE
    assert JS.stat().st_size == EXPECTED_JSON_SIZE
    assert EXPECTED_JSON_SHA256 in MD.read_text(encoding="utf-8")


def test_md_json_material_agreement():
    payload = _prereg()
    text = MD.read_text(encoding="utf-8")
    src = payload["pinned_external_source"]
    assert src["commit"] in text
    assert src["tree"] in text
    assert src["repo"] in text
    assert payload["replication_level"] in text
    assert payload["scientific_identity"] in text
    ev = payload["intervals"]["evaluation_interval"]
    assert ev["start_inclusive"] in text
    assert ev["end_exclusive"] in text
    assert ev["end_exclusive"] == "2025-01-01T00:00:00Z"
    warm = payload["intervals"]["warmup_interval"]
    assert warm["start_inclusive"] in text
    assert warm["end_exclusive"] in text
    spot = payload["data_authorities"]["spot"]
    assert spot["snapshot_id"] in text
    assert spot["spot_data_sha256"] in text
    fund = payload["funding_semantics"]
    assert fund["STRICT_HISTORICAL_PUBLICATION_LATENCY"] in text
    assert "UNPROVEN" in text
    assert fund["REPRODUCTION_FUNDINGTIME_ASSUMPTION"] in text
    clf = payload["primary_classification"]
    assert clf["equation"] in text
    assert payload["lifecycle"]["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert "CANONICAL_EXECUTIONS_CONSUMED       = 0" in text
    assert payload["parent_authorities"]["design_json_sha256"] == EXPECTED_DESIGN_JSON
    assert payload["parent_authorities"]["design_commit"] == EXPECTED_DESIGN_COMMIT
    assert _sha256(DESIGN_JS) == EXPECTED_DESIGN_JSON


def test_frozen_external_source_and_spot_snapshot():
    payload = _prereg()
    src = payload["pinned_external_source"]
    assert src["repo"] == "https://github.com/wiktorj137/btc-strategy-lab"
    assert src["commit"] == EXPECTED_COMMIT
    assert src["tree"] == EXPECTED_TREE
    assert src["family"] == "EmaCross vs EmaCrossFunding"
    assert src["replaced"] is False
    spot = payload["data_authorities"]["spot"]
    assert spot["dataset_id"] == "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    assert spot["snapshot_id"] == EXPECTED_SPOT
    assert spot["spot_data_sha256"] == EXPECTED_SPOT_DATA
    assert spot["market_type"] == "SPOT"
    assert spot["substitute_core_perp_forbidden"] is True


def test_evaluation_stops_before_protected_oos():
    payload = _prereg()
    ev = payload["intervals"]["evaluation_interval"]
    assert ev["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert ev["matches_author_full_headline"] is False
    assert payload["intervals"]["no_fill_open_time_on_or_after"] == (
        "2025-01-01T00:00:00Z"
    )
    oos = payload["protected_oos"]
    assert oos["headline_overlaps_protected_oos"] is True
    assert oos["protected_oos_authorized"] is False
    assert oos["protected_oos_touched"] is False
    assert oos["protected_oos_inspected"] is False
    assert oos["resolution"] == (
        "TRUNCATE_TO_AUTHORIZED_INTERVAL_DO_NOT_OPEN_PROTECTED_OOS"
    )


def test_fundingtime_assumption_unproven_and_b2_06_not_authority():
    payload = _prereg()
    fund = payload["funding_semantics"]
    assert fund["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert fund["REPRODUCTION_FUNDINGTIME_ASSUMPTION"] == "ACCEPTABLE"
    assert fund["assumption_does_not_establish_zero_latency_availability"] is True
    assert fund["assumption_does_not_resolve_b2_06"] is True
    auth = payload["data_authorities"]["funding"]
    assert auth["b2_06_is_not_market_03_authority"] is True
    assert auth["b2_06_unauthorized"] is True
    assert auth["acquired_rest_jsonl_sha256"] == EXPECTED_FUNDING_JSONL
    assert auth["named_snapshot_identity_materialized"] is False
    assert auth["pre_arm_required_artifact"] is True
    assert auth["funding_snapshot_ready"] is False
    assert auth["author_funding_feather_not_authority"] is True


def test_signed_mdd_primary_classification():
    payload = _prereg()
    mdd = payload["mdd_definition"]
    assert mdd["units"] == "signed_ratio"
    assert mdd["sign_convention"] == "negative_or_zero"
    assert mdd["example_less_negative_is_smaller_magnitude"] == "-0.338 > -0.494"
    clf = payload["primary_classification"]
    assert clf["sign_convention"] == "signed_negative_ratio"
    assert clf["comparison_uses_signed_values_not_abs"] is True
    assert clf["equation"] == (
        "REPRODUCED_DIRECTION iff finite(MDD_filtered) and "
        "finite(MDD_baseline) and (MDD_filtered > MDD_baseline)"
    )
    assert clf["equality_is_not_reproduced_direction"] is True
    assert clf["successful_label"] == "REPRODUCED_DIRECTION"
    text = MD.read_text(encoding="utf-8")
    assert "elif MDD_filtered > MDD_baseline:" in text
    assert "SIGN CONVENTION  = negative or zero" in text


def test_magnitude_and_secondary_cannot_promote_failed_direction():
    payload = _prereg()
    clf = payload["primary_classification"]
    assert clf["magnitude_cannot_promote_failed_direction"] is True
    assert clf["secondary_metrics_cannot_promote_failed_direction"] is True
    assert clf["binary_magnitude_tolerance_invented"] is False
    mag = payload["magnitude_fidelity"]
    assert mag["role"] == "DESCRIPTIVE_NOT_A_GATE"
    assert mag["no_minimum_magnitude_threshold"] is True
    assert mag["no_post_result_promotion_from_magnitude"] is True
    sec = payload["secondary_metrics"]
    assert sec["cannot_change_primary_classification"] is True
    assert sec["high_return_plus_failed_mdd_direction_remains_failure"] is True
    text = MD.read_text(encoding="utf-8")
    assert '"direction failed but return improved"' in text
    assert "is **not** reproduction" in text


def test_no_pvalue_bootstrap_gate():
    payload = _prereg()
    inf = payload["statistical_inference"]
    assert inf["used"] is False
    assert inf["p_value"] is False
    assert inf["bootstrap"] is False
    assert inf["permutation_test"] is False
    assert inf["confidence_interval_as_promotion_gate"] is False
    assert inf["market_01_02_machinery_imported"] is False
    text = MD.read_text(encoding="utf-8")
    assert "bootstrap" in text.lower()
    assert "**Forbidden** as a promotion gate" in text


def test_prereg_does_not_authorize_execution_consumed_zero():
    payload = _prereg()
    life = payload["lifecycle"]
    assert life["MARKET_03_PREREGISTERED"] is True
    assert life["MARKET_03_ARMED"] is False
    assert life["MARKET_03_IMPLEMENTED"] is False
    assert life["MARKET_03_STRATEGY_EXECUTED"] is False
    assert life["MARKET_03_OUTCOMES_INSPECTED"] is False
    assert life["MARKET_03_PARAMETER_SEARCH"] is False
    assert life["execution_authorized"] is False
    assert life["arm_authorized"] is False
    assert life["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert life["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert life["PROTECTED_OOS_TOUCHED"] is False
    assert life["FUNDING_SNAPSHOT_READY"] is False
    assert life["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["outcome_blindness"] == {
        "emacross_executed": False,
        "emacrossfunding_executed": False,
        "strategy_trades": False,
        "strategy_returns": False,
        "strategy_drawdown": False,
        "sharpe_sortino": False,
        "parameter_sensitivity": False,
        "protected_oos_inspected": False,
    }
    text = MD.read_text(encoding="utf-8")
    assert "does **not** authorize execution or ARM" in text
    fail = payload["fail_closed"]
    assert fail["must_not_become_NOT_REPRODUCED_DIRECTION"] is True
    assert "unauthorized_second_canonical_execution" in fail["EXECUTION_INVALID_if"]
    assert "protected_oos_access" in fail["EXECUTION_INVALID_if"]
