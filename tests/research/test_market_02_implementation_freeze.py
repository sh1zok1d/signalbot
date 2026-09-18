"""MARKET-02 implementation-freeze identity checks.

Does not ARM, execute MARKET-02, inspect outcomes, or load CORE/OI.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    FROZEN_PREREG_JSON_SHA256 as M01_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256 as M01_PREREG_MD_SHA256,
    LIB_ARMED_LIFECYCLE_SHA256,
)
from scripts.research.market_02_oi_expansion_price_confirmation_lib import (
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    MARKET_02_ARMED,
    MARKET_02_BOOTSTRAP_SEED,
    MARKET_02_EXECUTED,
    MARKET_02_TEST_CALIBRATED,
    RESEARCH_ID,
    SEED_MATERIAL_SHA256,
)


REPO = Path(__file__).resolve().parents[2]
FREEZE_JSON = (
    REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE.json"
)
FREEZE_MD = (
    REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE.md"
)
PREREG_MD = REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md"
PREREG_JSON = REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json"
LIB = REPO / "scripts/research/market_02_oi_expansion_price_confirmation_lib.py"
TESTS = REPO / "tests/research/test_market_02_implementation.py"
M01_RESULT = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json"
M01_LIB = REPO / "scripts/research/market_01_oi_expansion_weak_continuation_lib.py"
M01_PREREG_MD = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
M01_PREREG_JSON = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"

EXPECTED_FREEZE_JSON_SHA256 = (
    "204da4872393461185f568ce46552cd9c4893b1f04db3264ba671cdf153d06fb"
)
REVIEWED_HEAD = "1d2b0abf73d245f37cd9ca55ece99d1628dc80ee"
REVIEWED_TREE = "9e18ccf690e280bbd4b033f4a44f3b0700a5bedb"
REVIEWED_LIB_SHA256 = (
    "51638796db235a999bd1a12d44a57aace9e21f4b0cfffeea14bdabaf3eac7ea6"
)
M01_RESULT_SHA256 = "5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


def test_freeze_json_byte_identity():
    assert _sha256(FREEZE_JSON) == EXPECTED_FREEZE_JSON_SHA256
    freeze = _freeze()
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["status"] == "IMPLEMENTATION_FROZEN_NOT_ARMED"
    assert freeze["research_id"] == RESEARCH_ID
    assert freeze["not_an_arm"] is True
    assert freeze["not_an_execution"] is True
    assert freeze["not_outcome_inspection"] is True


def test_freeze_binds_reviewed_implementation_and_unchanged_lib():
    freeze = _freeze()
    reviewed = freeze["reviewed_implementation"]
    assert reviewed["head"] == REVIEWED_HEAD
    assert reviewed["tree"] == REVIEWED_TREE
    lib = freeze["accepted_scientific_implementation"][0]
    assert lib["reviewed_sha256"] == REVIEWED_LIB_SHA256
    assert _sha256(LIB) == REVIEWED_LIB_SHA256
    assert LIB.stat().st_size == lib["reviewed_size_bytes"]
    tests = freeze["implementation_tests"][0]
    assert tests["sha256"] == _sha256(TESTS)
    assert tests["includes_canonical_chronological_order_invariant"] is True


def test_prereg_bytes_unchanged_and_md_seed_authority():
    freeze = _freeze()
    md = freeze["prereg_authority"]["files"][0]
    js = freeze["prereg_authority"]["files"][1]
    assert _sha256(PREREG_MD) == FROZEN_PREREG_MD_SHA256
    assert _sha256(PREREG_JSON) == FROZEN_PREREG_JSON_SHA256
    assert md["sha256"] == FROZEN_PREREG_MD_SHA256
    assert js["sha256"] == FROZEN_PREREG_JSON_SHA256
    seed = freeze["seed_authority"]
    assert seed["md_authoritative_seed"] == "1852983754304692007"
    assert seed["json_twin_stored_numeric"] == "1852983754304692000"
    assert seed["silent_prereg_repair"] is False
    assert seed["prereg_files_unmodified_by_this_freeze"] is True
    assert seed["implementation_uses"] == "MD"
    assert seed["json_never_overrides_md"] is True
    assert seed["seed_material_sha256"] == SEED_MATERIAL_SHA256
    twin = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
    assert twin["bootstrap"]["seed"] == 1852983754304692000
    assert MARKET_02_BOOTSTRAP_SEED == 1852983754304692007
    assert str(MARKET_02_BOOTSTRAP_SEED) == seed["md_authoritative_seed"]


def test_freeze_preserves_interpretation_constraints_and_uncalibrated_flag():
    freeze = _freeze()
    state = freeze["explicit_state"]
    assert state["market_02_prereg_frozen"] is True
    assert state["market_02_implementation_complete"] is True
    assert state["market_02_implementation_frozen"] is True
    assert state["market_02_armed"] is False
    assert state["canonical_executions_consumed"] == 0
    assert state["real_market_02_outcome_inspection"] is False
    assert state["bound_market_02_execution"] is False
    assert state["protected_oos_touched"] is False
    assert state["market_02_test_calibrated"] is False
    limits = freeze["limitations_preserved"]
    assert limits["MARKET_02_TEST_CALIBRATED"] is False
    assert limits["canonical_executions_consumed"] == 0
    assert freeze["interpretation_constraints"]["pooled_estimand"][
        "detected_does_not_imply_every_stratum"
    ] is True
    assert freeze["interpretation_constraints"]["bootstrap_limitation"][
        "p_value_is_not_calibrated_real_market_false_positive_probability"
    ] is True
    assert freeze["interpretation_constraints"]["program_level"][
        "not_independent_replication_of_market_01"
    ] is True
    assert freeze["interpretation_constraints"]["temporal_persistence"][
        "passing_robustness_does_not_establish_persistent_edge"
    ] is True
    claim = freeze["interpretation_constraints"]["allowed_detected_claim"]
    assert "pooled within-stratum contrast" in claim
    assert "uncalibrated" in claim
    assert MARKET_02_TEST_CALIBRATED is False
    assert MARKET_02_ARMED is False
    assert MARKET_02_EXECUTED is False
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert "MARKET_02_TEST_CALIBRATED     = NO" in md
    assert "ARMED                         = NO" in md
    assert "pooled within-stratum contrast" in md
    assert freeze["ordering_invariant"]["evaluate_from_confirmatory_rows_redesigned"] is False
    assert freeze["next_lifecycle_state"] == "MARKET_02_ARM_IF_AUTHORIZED"


def test_market_01_frozen_bytes_untouched_by_market_02_freeze():
    assert _sha256(M01_PREREG_MD) == M01_PREREG_MD_SHA256
    assert _sha256(M01_PREREG_JSON) == M01_PREREG_JSON_SHA256
    assert _sha256(M01_LIB) == LIB_ARMED_LIFECYCLE_SHA256
    assert hashlib.sha256(M01_RESULT.read_bytes()).hexdigest() == M01_RESULT_SHA256
