"""Known-answer and decision-rule tests for the D7 confirmatory contract.

No beacon, no BitMEX target, and no power or admission rerun.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.self_referential_contrast_v1.confirmatory_contract import (
    CANONICAL_SOURCE_SHA256,
    KAT_DRAW_INDEX,
    KAT_SEGMENT_INDEX,
    KAT_WIDTH,
    NUMPY_RECORD_SHA256,
    NUMPY_VERSION_REQUIRED,
    TEST_ONLY_SEED_FIELDS,
    adapter_document,
    bootstrap_critical_floor,
    canonical_json,
    confirmatory_seed_digest,
    confirmatory_seed_message,
    decision_rule_document,
    digest_to_seedsequence_words,
    directional_confirmation_pass,
    dwb_one_sided_lower_bound,
    integrity_pass,
    magnitude_classification,
    seed_sequence_from_confirmatory_digest,
)
from scripts.research.self_referential_contrast_v1.contrast import indexed_epsilon_sampler
from scripts.research.self_referential_contrast_v1.seeds import generator_from_digest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / "docs/research/D7_CONFIRMATORY_ADAPTER_V1.json"
DECISION_PATH = ROOT / "docs/research/D7_DIRECTIONAL_CONFIRMATION_DECISION_RULE_V1.json"
PIN_PATH = ROOT / "docs/research/D7_CONFIRMATORY_NUMPY_PIN_V1.json"
MANIFEST_PATH = ROOT / "docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json"
POWER_MANIFEST = ROOT / "docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_POWER_GATE_V1_MANIFEST.json"
FORBIDDEN = (
    "m_xy",
    "m_XY",
    "transition",
    "autocorrelation",
    "raw_pages",
    "canonical_5m",
    "DELTA_D7",
    "run_length",
    "persistence",
)


def test_official_power_manifest_includes_temporal_gate() -> None:
    payload = POWER_MANIFEST.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == (
        "9c35900d7cf33ccdda42dc7a1e94eac4c47482bcd64087e5e7e8f509b3b2f50c"
    )
    body = json.loads(payload)
    assert body["D7_POWER_GATE_STARTED"] is False
    rule = body["detection_rule"]
    assert "year-level theta_hat > 0" in rule
    assert "not a second gate" in rule


def test_adapter_file_is_canonical_and_target_blind() -> None:
    text = ADAPTER_PATH.read_text(encoding="utf-8")
    assert text == canonical_json(adapter_document())
    body = json.loads(text)
    assert body["T"] == 30354
    assert sum(body["year_eligible_masses"].values()) == 30354
    assert body["K"] == sum(cell["candidate_n"] for cell in body["cells"]) == 3438
    assert body["eligible_index_gap_break"] == 3503
    assert body["structural_segments"] == [3503, 26851]
    lowered = text.lower()
    for token in FORBIDDEN:
        assert token.lower() not in lowered


def test_decision_rule_removes_magnitude_from_pass() -> None:
    text = DECISION_PATH.read_text(encoding="utf-8")
    assert text == canonical_json(decision_rule_document())
    body = json.loads(text)
    assert body["CLAIM_CHANGE"] == "magnitude >= 0.05 is no longer a D7 confirmation PASS condition"
    assert body["D7_DIRECTIONAL_CONFIRMATION_PASS"] == (
        "PRIMARY_COMPLETED AND STATISTICAL_REJECT AND TEMPORAL_PASS AND INTEGRITY_PASS"
    )
    assert "0.05" not in body["D7_DIRECTIONAL_CONFIRMATION_PASS"]
    assert body["does_not_establish"] == "theta >= 0.05"
    assert body["TEMPORAL_POWER_ALREADY_EXECUTED"] is True


def test_known_answer_normal_path_uses_full_digest() -> None:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    message = confirmatory_seed_message(TEST_ONLY_SEED_FIELDS)
    digest = confirmatory_seed_digest(message)
    assert digest.hex() == pin["known_answer"]["seed_message_sha256"]
    words = digest_to_seedsequence_words(digest)
    sequence = seed_sequence_from_confirmatory_digest(digest)
    assert list(sequence.entropy) == words
    assert len(words) == 8
    generator = generator_from_digest(digest, spawn_key=(KAT_DRAW_INDEX, KAT_SEGMENT_INDEX))
    assert type(generator.bit_generator).__name__ == "PCG64"
    draws = indexed_epsilon_sampler(digest)(KAT_DRAW_INDEX, KAT_SEGMENT_INDEX, KAT_WIDTH)
    assert [float(value).hex() for value in draws] == pin["known_answer"]["standard_normal_hex"]


def test_nist_identity_rejects_test_only_output() -> None:
    fields = dict(TEST_ONLY_SEED_FIELDS)
    fields["beacon_id"] = "NIST-Beacon-2.0"
    with pytest.raises(ValueError, match="NIST"):
        confirmatory_seed_message(fields)


def test_lower_bound_matches_zero_null_rejection() -> None:
    boundary = [0.0] * 9500 + [1.0] * 499
    assert bootstrap_critical_floor(boundary) == 0.0
    lower = dwb_one_sided_lower_bound(
        theta_hat=0.02, observed_variance=1.0, t_count=100, studentized=boundary
    )
    assert lower == pytest.approx(0.02)
    tied = dwb_one_sided_lower_bound(
        theta_hat=0.0, observed_variance=1.0, t_count=100, studentized=boundary
    )
    assert tied == pytest.approx(0.0)
    flat = [2.0] * 9999
    assert bootstrap_critical_floor(flat) == 2.0
    at_floor = dwb_one_sided_lower_bound(
        theta_hat=2.0, observed_variance=1.0, t_count=1, studentized=flat
    )
    assert at_floor == pytest.approx(0.0)
    above = dwb_one_sided_lower_bound(
        theta_hat=2.25, observed_variance=1.0, t_count=1, studentized=flat
    )
    assert above == pytest.approx(0.25)


def test_magnitude_class_does_not_change_directional_pass() -> None:
    supported = magnitude_classification(0.05)
    assert supported["MAGNITUDE_AT_0_05_SUPPORTED"] is True
    assert supported["changes_directional_pass"] is False
    direction_only = magnitude_classification(0.049)
    assert direction_only["MAGNITUDE_CLASS"] == "DIRECTION_ONLY"
    assert direction_only["changes_directional_pass"] is False
    assert directional_confirmation_pass(
        inference_status="PRIMARY_COMPLETED",
        statistical_reject=True,
        temporal_pass=True,
        integrity=True,
    )
    assert not directional_confirmation_pass(
        inference_status="PRIMARY_COMPLETED",
        statistical_reject=False,
        temporal_pass=True,
        integrity=True,
    )


def test_integrity_pass_is_mechanical() -> None:
    pins = {
        "adapter_digest": "a" * 64,
        "canonical_source_sha256": CANONICAL_SOURCE_SHA256,
        "confirmatory_seed_digest": "b" * 64,
        "statistical_implementation_digest": "c" * 64,
    }
    observed = {
        "T": 30354,
        "adapter_digest": pins["adapter_digest"],
        "canonical_source_sha256": CANONICAL_SOURCE_SHA256,
        "confirmatory_seed_digest": pins["confirmatory_seed_digest"],
        "eligible_index_gap_break": 3503,
        "forbidden_input_accessed": False,
        "inference_status": "PRIMARY_COMPLETED",
        "numpy_record_sha256": NUMPY_RECORD_SHA256,
        "numpy_version": NUMPY_VERSION_REQUIRED,
        "statistical_implementation_digest": pins["statistical_implementation_digest"],
        "structural_segments": [3503, 26851],
        "target_mutated": False,
        "year_eligible_masses": {"2016": 4079, "2017": 8757, "2018": 8759, "2019": 8759},
    }
    assert integrity_pass(observed, pins)
    mutated = dict(observed)
    mutated["target_mutated"] = True
    assert not integrity_pass(mutated, pins)


def test_freeze_manifest_hashes_covered_files_only() -> None:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    body = json.loads(text)
    assert body["document"] == "D7_CONFIRMATORY_FREEZE_MANIFEST_V1"
    paths = [item["path"] for item in body["files"]]
    assert "docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json" not in paths
    assert "CONFIRMATORY_FREEZE_COMMIT" not in text
    for item in body["files"]:
        payload = (ROOT / item["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
