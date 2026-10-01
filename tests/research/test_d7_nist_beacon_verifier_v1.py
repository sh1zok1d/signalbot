"""Offline NIST Beacon 2.0 verifier regressions.

No network. No BitMEX parse. No confirmatory seed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.d7_nist_beacon_verifier_v1 import (
    COMPACT_RECORD_FIELDS,
    INCOMPLETE,
    INCOMPLETE_TRANSPORT_KINDS,
    advance_permitted,
    assess_pulse,
    chain_continuity_status,
    chain_index_blocks_eligibility,
    compact_candidate_record,
    output_preimage,
    signed_preimage,
    transport_failure_disposition,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/research/fixtures/d7_beacon_verifier_v1"
PULSE_1965184 = ROOT / "docs/research/D7_CONFIRMATORY_BEACON_PULSE_V1.json"
CERT_1965184 = ROOT / "docs/research/D7_CONFIRMATORY_BEACON_CERTIFICATE_V1.crt"
VERIFIER = ROOT / "scripts/research/d7_nist_beacon_verifier_v1.py"
DRIVER = ROOT / "scripts/research/d7_confirmatory_target_opening_v1.py"


def _pulse(path: Path) -> dict:
    body = json.loads(path.read_text(encoding="utf-8"))
    return body["pulse"] if isinstance(body, dict) and "pulse" in body else body


def test_verifier_has_no_hardcoded_512_byte_signature_slot() -> None:
    for path in (VERIFIER, DRIVER):
        text = path.read_text(encoding="utf-8")
        assert "len(signature) != 512" not in text
        assert "len(signature) == 512" not in text
        assert "SIGNATURE_LENGTH" not in text


def test_historical_4096_pulse_verifies() -> None:
    pulse = _pulse(FIXTURE / "historical_2026_09_02_pulse.json")
    certificate = (FIXTURE / "historical_2026_09_02_certificate.crt").read_bytes()
    assert int(pulse["pulseIndex"]) == 1923756
    assert int(pulse["pulseIndex"]) < 1965184
    assert pulse["timeStamp"] == "2026-09-02T12:00:00.000Z"
    assessment = assess_pulse(pulse, certificate)
    assert assessment["RSA_MODULUS_BITS"] == 4096
    assert assessment["RSA_MODULUS_BYTES"] == 512
    assert assessment["SIGNATURE_BYTES"] == 512
    assert assessment["SIGNATURE_INTEGER_LT_MODULUS"] is True
    assert assessment["signature_length_matches_modulus"] is True
    assert assessment["output_matches_serialization"] is True
    assert assessment["pkcs1_sha512_valid"] is True
    assert assessment["VALID"] is True
    assert assessment["classification"] == "VALID"
    assert len(output_preimage(pulse)) - len(signed_preimage(pulse)) == 512


def test_pulse_1965184_is_objectively_invalid() -> None:
    pulse = _pulse(PULSE_1965184)
    certificate = CERT_1965184.read_bytes()
    assessment = assess_pulse(pulse, certificate)
    assert assessment["RSA_MODULUS_BITS"] == 2048
    assert assessment["RSA_MODULUS_BYTES"] == 256
    assert assessment["SIGNATURE_BYTES"] == 512
    assert assessment["SIGNATURE_INTEGER_LT_MODULUS"] is False
    assert assessment["signature_length_matches_modulus"] is False
    assert assessment["certificate_sha512_matches_certificateId"] is True
    assert assessment["output_matches_serialization"] is True
    assert assessment["pkcs1_sha512_valid"] is False
    assert assessment["VALID"] is False
    assert assessment["classification"] == "PULSE_1965184_OBJECTIVELY_INVALID"


def test_named_certificate_is_authoritative() -> None:
    pulse = _pulse(PULSE_1965184)
    other = (FIXTURE / "test_only_rsa2048_certificate.crt").read_bytes()
    with pytest.raises(Exception) as caught:
        assess_pulse(pulse, other)
    assert "BEACON_CERTIFICATE_HASH" in str(caught.value)


def test_test_only_rsa2048_pulse_verifies() -> None:
    pulse = _pulse(FIXTURE / "test_only_rsa2048_pulse.json")
    certificate = (FIXTURE / "test_only_rsa2048_certificate.crt").read_bytes()
    assert pulse["version"] == "TEST_ONLY"
    assert pulse["timeStamp"] == "2000-01-01T00:00:00.000Z"
    assert str(pulse["uri"]).startswith("test-only://")
    assessment = assess_pulse(pulse, certificate)
    assert assessment["RSA_MODULUS_BITS"] == 2048
    assert assessment["RSA_MODULUS_BYTES"] == 256
    assert assessment["SIGNATURE_BYTES"] == 256
    assert assessment["SIGNATURE_INTEGER_LT_MODULUS"] is True
    assert assessment["output_matches_serialization"] is True
    assert assessment["pkcs1_sha512_valid"] is True
    assert assessment["VALID"] is True
    assert len(output_preimage(pulse)) - len(signed_preimage(pulse)) == 256


@pytest.mark.parametrize("kind", INCOMPLETE_TRANSPORT_KINDS)
def test_incomplete_transport_does_not_advance(kind: str) -> None:
    disposition = transport_failure_disposition(kind)
    assert disposition["status"] == INCOMPLETE
    assert disposition["may_advance"] is False
    assert disposition["classification"] is None


def test_chain_continuity_and_chain_neutral_eligibility() -> None:
    output = "ab" * 64
    previous = {"outputValue": output, "chainIndex": 2}
    linked = {"listValues": [{"type": "previous", "value": output.upper()}], "chainIndex": 9}
    broken = {"listValues": [{"type": "previous", "value": "cd" * 64}], "chainIndex": 2}
    assert chain_continuity_status(previous, linked) == "CONTINUOUS"
    assert chain_continuity_status(previous, broken) == "BEACON_CHAIN_CONTINUITY_FAILED"
    assert chain_index_blocks_eligibility(2) is False
    assert chain_index_blocks_eligibility(9) is False
    invalid = {
        "VALID": False,
        "classification": "PULSE_1_OBJECTIVELY_INVALID",
        "failure_code": "BEACON_SIGNATURE_REPRESENTATION_INVALID",
    }
    assert advance_permitted(invalid, "CONTINUOUS") is True
    assert advance_permitted(invalid, "BEACON_CHAIN_CONTINUITY_FAILED") is False
    assert advance_permitted({"VALID": True, "classification": "VALID", "failure_code": None}, "CONTINUOUS") is False


def test_compact_record_schema() -> None:
    pulse = _pulse(FIXTURE / "test_only_rsa2048_pulse.json")
    raw = (FIXTURE / "test_only_rsa2048_pulse.json").read_bytes()
    certificate = (FIXTURE / "test_only_rsa2048_certificate.crt").read_bytes()
    assessment = assess_pulse(pulse, certificate)
    previous = {"outputValue": pulse["listValues"][0]["value"]}
    continuity = chain_continuity_status(previous, pulse)
    record = compact_candidate_record(
        pulse=pulse,
        raw_pulse=raw,
        assessment=assessment,
        continuity=continuity,
    )
    assert tuple(record) == COMPACT_RECORD_FIELDS
    assert record["chainIndex"] == 0
    assert record["pulseIndex"] == 0
    assert record["timestamp"] == "2000-01-01T00:00:00.000Z"
    assert record["rsa_modulus_bytes"] == 256
    assert record["signature_bytes"] == 256
    assert record["classification"] == "VALID"
    assert record["chain_continuity_status"] == "CONTINUOUS"
