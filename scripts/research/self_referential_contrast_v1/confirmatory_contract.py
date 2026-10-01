"""Outcome-blind D7 confirmatory identity.

This module does not open a target, read lag-1 pairs, fetch a beacon, or
draw a confirmatory stream. The multiplier law stays the audited
NumPy PCG64 path in ``seeds.generator_from_digest``.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping, Sequence

from scripts.research.self_referential_contrast_v1.constants import (
    CONFIRMATORY_PURPOSE,
    PROFILE_ID,
    R_CONFIRMATORY,
)
from scripts.research.self_referential_contrast_v1.seeds import seed_sequence_from_digest

PROFILE_VERSION = "D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1"
CONFIRMATORY_BIT_GENERATOR = "NUMPY_PCG64"
NUMPY_VERSION_REQUIRED = "2.1.3"
NUMPY_RECORD_SHA256 = "ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1"
CANONICAL_SOURCE_SHA256 = "33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c"
SELECTOR_DIGEST = "88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6"
PRACTICAL_EFFECT = "1/20"
TAIL_COUNT_AT_R_9999 = 499
TEMPORAL_YEARS = ("2017", "2018", "2019")

TEST_ONLY_SEED_FIELDS = {
    "adapter_digest": "TEST_ONLY_ADAPTER",
    "beacon_id": "TEST_ONLY_NOT_A_NIST_PULSE",
    "beacon_output_value": "TEST_ONLY_OUTPUT",
    "beacon_pulse_time": "TEST_ONLY",
    "decision_rule_digest": "TEST_ONLY_DECISION",
    "freeze_manifest_sha256": "TEST_ONLY_NOT_THE_CONFIRMATION_MANIFEST",
    "numpy_record_sha256": NUMPY_RECORD_SHA256,
    "numpy_version": NUMPY_VERSION_REQUIRED,
    "profile_id": PROFILE_ID,
    "profile_version": PROFILE_VERSION,
    "purpose": CONFIRMATORY_PURPOSE,
    "r_confirmatory": R_CONFIRMATORY,
    "statistical_implementation_digest": "TEST_ONLY_IMPLEMENTATION",
    "target_source_digest": "TEST_ONLY_SOURCE",
}
KAT_DRAW_INDEX = 0
KAT_SEGMENT_INDEX = 0
KAT_WIDTH = 8

CELL_MARGINS = (
    ("2016:0", 1064, 82),
    ("2016:1", 1080, 140),
    ("2016:2", 942, 119),
    ("2016:3", 993, 82),
    ("2017:0", 2106, 24),
    ("2017:1", 2104, 147),
    ("2017:2", 2120, 341),
    ("2017:3", 2427, 697),
    ("2018:0", 2377, 2),
    ("2018:1", 2218, 41),
    ("2018:2", 2113, 235),
    ("2018:3", 2051, 596),
    ("2019:0", 2268, 7),
    ("2019:1", 2234, 124),
    ("2019:2", 2084, 319),
    ("2019:3", 2173, 482),
)


def canonical_json(payload: Mapping[str, object]) -> str:
    """UTF-8 JSON, sorted keys, no insignificant whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def adapter_document() -> dict[str, object]:
    """Published predictor-side geometry only. No joint lead statistic."""
    cells = []
    for name, eligible_n, candidate_n in CELL_MARGINS:
        cells.append(
            {
                "candidate_n": candidate_n,
                "cell": name,
                "eligible_n": eligible_n,
                "pi_s": f"{candidate_n}/{eligible_n}",
            }
        )
    return {
        "B_T": 721,
        "H_mechanical": 721,
        "K": 3438,
        "L_T": 721,
        "T": 30354,
        "canonical_source_sha256": CANONICAL_SOURCE_SHA256,
        "cells": cells,
        "deterministic_blocks": ["2016", "2017", "2018", "2019"],
        "eligible_index_gap_break": 3503,
        "estimand": "theta=g(m)",
        "gap_end_exclusive": "2016-12-07T23:55:00.000Z",
        "gap_start_inclusive": "2016-12-06T23:55:00.000Z",
        "label_geometry": "CONTIGUOUS_PUBLISHED_YEAR_RV_MARGINS",
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "rv_buckets": [0, 1, 2, 3],
        "selector_digest": SELECTOR_DIGEST,
        "selector_n": 3438,
        "structural_segments": [3503, 26851],
        "year_eligible_masses": {"2016": 4079, "2017": 8757, "2018": 8759, "2019": 8759},
    }


def decision_rule_document() -> dict[str, object]:
    return {
        "CLAIM_CHANGE": "magnitude >= 0.05 is no longer a D7 confirmation PASS condition",
        "D7_DIRECTIONAL_CONFIRMATION_PASS": (
            "PRIMARY_COMPLETED AND STATISTICAL_REJECT AND TEMPORAL_PASS AND INTEGRITY_PASS"
        ),
        "MAGNITUDE_AT_0_05_SUPPORTED": "one_sided_dwb_lower_bound >= 1/20",
        "MAGNITUDE_CLASS_OTHERWISE": "DIRECTION_ONLY",
        "POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL": True,
        "PRACTICAL_MAGNITUDE_ROLE": "PRACTICAL_MAGNITUDE_DIAGNOSTIC",
        "STATISTICAL_REJECT": (
            "inference_status = PRIMARY_COMPLETED AND V_obs > 0 AND R = 9999 "
            "AND p = (1 + exceedance_count) / 10000 AND exceedance_count <= 499"
        ),
        "TEMPORAL_PASS": (
            "year_theta defined and > 0 in at least 2 of {2017, 2018, 2019}; 2016 diagnostic"
        ),
        "TEMPORAL_POWER_ALREADY_EXECUTED": True,
        "label": "D7_DIRECTIONAL_CONFIRMATION_PASS",
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "does_not_establish": "theta >= 0.05",
    }


def digest_to_seedsequence_words(digest: bytes) -> list[int]:
    """All 256 bits, as eight little-endian uint32 words.

    This is the conversion already used by ``seed_sequence_from_digest``.
    """
    if len(digest) != 32:
        raise ValueError("seed digest must be 32 bytes")
    words = [int.from_bytes(digest[i : i + 4], "little") for i in range(0, 32, 4)]
    if len(words) != 8:
        raise ValueError("SeedSequence entropy must be eight words")
    rebuilt = b"".join(word.to_bytes(4, "little") for word in words)
    if rebuilt != digest:
        raise ValueError("SeedSequence word conversion dropped bits")
    return words


def seed_sequence_from_confirmatory_digest(digest: bytes):
    """NumPy SeedSequence over the full SHA-256 digest. No truncation."""
    sequence = seed_sequence_from_digest(digest)
    words = digest_to_seedsequence_words(digest)
    if list(sequence.entropy) != words:
        raise ValueError("SeedSequence entropy is not the full digest")
    return sequence


def confirmatory_seed_message(fields: Mapping[str, object]) -> str:
    required = {
        "adapter_digest",
        "beacon_id",
        "beacon_output_value",
        "beacon_pulse_time",
        "decision_rule_digest",
        "freeze_manifest_sha256",
        "numpy_record_sha256",
        "numpy_version",
        "profile_id",
        "profile_version",
        "purpose",
        "r_confirmatory",
        "statistical_implementation_digest",
        "target_source_digest",
    }
    if set(fields) != required:
        missing = sorted(required - set(fields))
        extra = sorted(set(fields) - required)
        raise ValueError(f"seed message fields missing={missing} extra={extra}")
    if fields["purpose"] != CONFIRMATORY_PURPOSE:
        raise ValueError("purpose must be CONFIRMATORY_DWB_MULTIPLIERS")
    if int(fields["r_confirmatory"]) != R_CONFIRMATORY:
        raise ValueError("R_CONFIRMATORY must be 9999")
    if fields["numpy_version"] != NUMPY_VERSION_REQUIRED:
        raise ValueError("NumPy version is not the pinned confirmation build")
    if str(fields["beacon_id"]).startswith("NIST") and str(fields["beacon_output_value"]).startswith("TEST_ONLY"):
        raise ValueError("a NIST beacon id cannot carry a test output")
    return canonical_json(dict(fields))


def confirmatory_seed_digest(message: str) -> bytes:
    return hashlib.sha256(message.encode("utf-8")).digest()


def bootstrap_critical_floor(studentized: Sequence[float], *, replicates: int = R_CONFIRMATORY) -> float:
    """Largest replicate ``t`` with ``#{T* >= t} > 499``.

    At ``R = 9999`` that order statistic is ``sorted_replicates[9499]``
    (zero-based), the 9500th ascending value. The frozen level-0.05 rule
    rejects when ``#{T* >= T_obs} <= 499``. That event is ``T_obs > floor``.
    """
    if replicates != R_CONFIRMATORY:
        raise ValueError("confirmatory critical value is defined at R=9999")
    values = [float(item) for item in studentized]
    if len(values) != replicates:
        raise ValueError("studentized replicate count must equal R")
    if any(not math.isfinite(item) for item in values):
        raise ValueError("studentized replicates must be finite")
    values.sort()
    index = replicates - TAIL_COUNT_AT_R_9999 - 1
    return float(values[index])


def dwb_one_sided_lower_bound(
    *,
    theta_hat: float,
    observed_variance: float,
    t_count: int,
    studentized: Sequence[float],
) -> float:
    """Invert the frozen one-sided DWB test. Not a second procedure.

    ``T(theta0) = sqrt(T) (theta_hat - theta0) / sqrt(V_obs)``.
    ``H0: theta <= theta0`` is rejected when ``T(theta0) > c``, where ``c``
    is ``bootstrap_critical_floor``. The lower bound is the boundary of
    that rejection region:

    ``L = theta_hat - c * sqrt(V_obs) / sqrt(T)``.

    ``L > 0`` is the same event as rejection of ``H0: theta <= 0``.
    ``L >= 1/20`` is the separate magnitude classification.
    """
    if t_count < 1:
        raise ValueError("T must be positive")
    if not math.isfinite(theta_hat) or not math.isfinite(observed_variance):
        raise ValueError("theta and variance must be finite")
    if observed_variance <= 0.0:
        raise ValueError("lower bound requires positive observed variance")
    scale = math.sqrt(observed_variance) / math.sqrt(t_count)
    floor = bootstrap_critical_floor(studentized)
    return float(theta_hat - floor * scale)


def magnitude_classification(lower_bound: float) -> dict[str, object]:
    supported = float(lower_bound) >= 0.05
    return {
        "MAGNITUDE_AT_0_05_SUPPORTED": supported,
        "MAGNITUDE_CLASS": "MAGNITUDE_AT_0_05_SUPPORTED" if supported else "DIRECTION_ONLY",
        "lower_bound": float(lower_bound),
        "changes_directional_pass": False,
    }


def statistical_implementation_digest(manifest: Mapping[str, object]) -> str:
    files = manifest["files"]
    if not isinstance(files, list):
        raise ValueError("manifest files must be a list")
    subset = {
        str(item["path"]): str(item["sha256"])
        for item in files
        if str(item["path"]).startswith("scripts/research/self_referential_contrast_v1/")
    }
    if not subset:
        raise ValueError("manifest has no statistical implementation files")
    return sha256_text(canonical_json(subset))


def integrity_pass(observed: Mapping[str, object], pins: Mapping[str, object]) -> bool:
    """Mechanical identity only. No post-result credibility judgment."""
    year_masses = observed["year_eligible_masses"]
    return bool(
        observed["canonical_source_sha256"] == pins["canonical_source_sha256"] == CANONICAL_SOURCE_SHA256
        and observed["adapter_digest"] == pins["adapter_digest"]
        and int(observed["T"]) == 30354
        and dict(year_masses) == {"2016": 4079, "2017": 8757, "2018": 8759, "2019": 8759}
        and int(observed["eligible_index_gap_break"]) == 3503
        and list(observed["structural_segments"]) == [3503, 26851]
        and observed["statistical_implementation_digest"] == pins["statistical_implementation_digest"]
        and observed["confirmatory_seed_digest"] == pins["confirmatory_seed_digest"]
        and observed["numpy_record_sha256"] == NUMPY_RECORD_SHA256
        and observed["numpy_version"] == NUMPY_VERSION_REQUIRED
        and observed["inference_status"] == "PRIMARY_COMPLETED"
        and observed["target_mutated"] is False
        and observed["forbidden_input_accessed"] is False
    )


def directional_confirmation_pass(
    *,
    inference_status: str,
    statistical_reject: bool,
    temporal_pass: bool,
    integrity: bool,
) -> bool:
    return bool(
        inference_status == "PRIMARY_COMPLETED" and statistical_reject and temporal_pass and integrity
    )
