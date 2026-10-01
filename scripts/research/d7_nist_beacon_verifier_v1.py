"""NIST Beacon 2.0 pulse verifier for the D7 confirmatory scan.

A pulse is valid only under the certificate named by its own certificateId.
Signature length is the named RSA modulus size. This module does not fetch
pulses, open the BitMEX target, or draw a confirmatory seed.
"""

from __future__ import annotations

import hashlib
import math
from typing import Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

INCOMPLETE = "BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE"
CONTINUITY_OK = "CONTINUOUS"
CONTINUITY_FAILED = "BEACON_CHAIN_CONTINUITY_FAILED"
SERIALIZATION = "NIST_BEACON_2_0_SIGNED_PREIMAGE_UINT32_PREFIX_RAW_SIGNATURE_OCTETS"

INCOMPLETE_TRANSPORT_KINDS = (
    "HTTP_TIMEOUT",
    "DNS_OR_NETWORK",
    "TLS",
    "TRUNCATED_RESPONSE",
    "MALFORMED_TRANSPORT",
    "HTTP_5XX",
    "UNEXPECTED_404",
    "CERTIFICATE_FETCH_FAILED",
    "VERIFICATION_INCOMPLETE",
)

COMPACT_RECORD_FIELDS = (
    "chainIndex",
    "pulseIndex",
    "timestamp",
    "raw_pulse_sha256",
    "certificateId",
    "rsa_modulus_bytes",
    "signature_bytes",
    "chain_continuity_status",
    "cryptographic_verification_status",
    "classification",
)


class BeaconVerifierError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "big")


def _u64(value: int) -> bytes:
    return int(value).to_bytes(8, "big")


def _ser_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _u32(len(encoded)) + encoded


def _ser_hash(value: str) -> bytes:
    raw = bytes.fromhex(value)
    if len(raw) != 64:
        raise BeaconVerifierError("BEACON_HASH_LENGTH")
    return _u32(len(raw)) + raw


def _list_value(pulse: Mapping[str, object], kind: str) -> str:
    items = pulse["listValues"]
    if not isinstance(items, list):
        raise BeaconVerifierError("BEACON_LIST_VALUE")
    for item in items:
        if isinstance(item, dict) and item.get("type") == kind:
            return str(item["value"])
    raise BeaconVerifierError("BEACON_LIST_VALUE")


def _timestamp_text(pulse: Mapping[str, object]) -> str:
    value = pulse["timeStamp"]
    if not isinstance(value, str) or len(value) != 24:
        raise BeaconVerifierError("BEACON_TIMESTAMP_FORMAT")
    return value


def signature_octets(pulse: Mapping[str, object]) -> bytes:
    """Raw signature field. No fixed 512-byte slot."""
    try:
        raw = bytes.fromhex(str(pulse["signatureValue"]))
    except ValueError as exc:
        raise BeaconVerifierError("BEACON_SIGNATURE_ENCODING") from exc
    if not raw:
        raise BeaconVerifierError("BEACON_SIGNATURE_ENCODING")
    return raw


def signed_preimage(pulse: Mapping[str, object]) -> bytes:
    """Fields F1–F19. String and hash lengths are uint32 prefixes of the actual bytes."""
    external = pulse["external"]
    if not isinstance(external, dict):
        raise BeaconVerifierError("BEACON_EXTERNAL")
    parts = [
        _ser_string(str(pulse["uri"])),
        _ser_string(str(pulse["version"])),
        _u32(int(pulse["cipherSuite"])),
        _u32(int(pulse["period"])),
        _ser_hash(str(pulse["certificateId"])),
        _u64(int(pulse["chainIndex"])),
        _u64(int(pulse["pulseIndex"])),
        _ser_string(_timestamp_text(pulse)),
        _ser_hash(str(pulse["localRandomValue"])),
        _ser_hash(str(external["sourceId"])),
        _u32(int(external["statusCode"])),
        _ser_hash(str(external["value"])),
        _ser_hash(_list_value(pulse, "previous")),
        _ser_hash(_list_value(pulse, "hour")),
        _ser_hash(_list_value(pulse, "day")),
        _ser_hash(_list_value(pulse, "month")),
        _ser_hash(_list_value(pulse, "year")),
        _ser_hash(str(pulse["precommitmentValue"])),
        _u32(int(pulse["statusCode"])),
    ]
    return b"".join(parts)


def output_preimage(pulse: Mapping[str, object]) -> bytes:
    """Signed preimage concatenated with the signature octets actually present.

    A 256-byte signature contributes 256 octets. A 512-byte signature contributes
    512 octets. The signature is not written into a hardcoded 512-byte field.
    """
    return signed_preimage(pulse) + signature_octets(pulse)


def output_matches(pulse: Mapping[str, object]) -> bool:
    digest = hashlib.sha512(output_preimage(pulse)).hexdigest()
    return digest.lower() == str(pulse["outputValue"]).lower()


def _named_rsa_key(pulse: Mapping[str, object], certificate_pem: bytes) -> rsa.RSAPublicKey:
    if int(pulse["cipherSuite"]) != 0:
        raise BeaconVerifierError("BEACON_CIPHER_SUITE")
    certificate = x509.load_pem_x509_certificate(certificate_pem)
    der = certificate.public_bytes(serialization.Encoding.DER)
    cert_hash = hashlib.sha512(der).hexdigest()
    if cert_hash.lower() != str(pulse["certificateId"]).lower():
        raise BeaconVerifierError("BEACON_CERTIFICATE_HASH")
    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise BeaconVerifierError("BEACON_NOT_RSA")
    return public_key


def rsa_representation(public_key: rsa.RSAPublicKey, signature: bytes) -> dict[str, object]:
    modulus_bits = int(public_key.key_size)
    modulus_bytes = int(math.ceil(modulus_bits / 8))
    signature_int = int.from_bytes(signature, "big")
    modulus = int(public_key.public_numbers().n)
    length_ok = len(signature) == modulus_bytes
    below_modulus = 0 <= signature_int < modulus
    return {
        "RSA_MODULUS_BITS": modulus_bits,
        "RSA_MODULUS_BYTES": modulus_bytes,
        "SIGNATURE_BYTES": len(signature),
        "SIGNATURE_INTEGER_LT_MODULUS": below_modulus,
        "signature_length_matches_modulus": length_ok,
        "representation_valid": bool(length_ok and below_modulus),
    }


def _pkcs1_sha512_valid(public_key: rsa.RSAPublicKey, signature: bytes, preimage: bytes) -> bool:
    try:
        public_key.verify(signature, preimage, padding.PKCS1v15(), hashes.SHA512())
    except InvalidSignature:
        return False
    return True


def assess_pulse(pulse: Mapping[str, object], certificate_pem: bytes) -> dict[str, object]:
    """Full validity assessment under the certificate named by this pulse."""
    signature = signature_octets(pulse)
    preimage = signed_preimage(pulse)
    output_ok = output_matches(pulse)
    public_key = _named_rsa_key(pulse, certificate_pem)
    facts = rsa_representation(public_key, signature)
    pkcs1_ok = False
    if facts["representation_valid"]:
        pkcs1_ok = _pkcs1_sha512_valid(public_key, signature, preimage)
    pulse_index = int(pulse["pulseIndex"])
    if not facts["representation_valid"]:
        classification = f"PULSE_{pulse_index}_OBJECTIVELY_INVALID"
        failure = "BEACON_SIGNATURE_REPRESENTATION_INVALID"
        valid = False
    elif not output_ok:
        classification = "OUTPUT_MISMATCH"
        failure = "BEACON_OUTPUT_MISMATCH"
        valid = False
    elif not pkcs1_ok:
        classification = "PKCS1_INVALID"
        failure = "BEACON_SIGNATURE_INVALID"
        valid = False
    else:
        classification = "VALID"
        failure = None
        valid = True
    return {
        "VALID": valid,
        "classification": classification,
        "failure_code": failure,
        "output_matches_serialization": output_ok,
        "certificate_sha512_matches_certificateId": True,
        "pkcs1_sha512_valid": pkcs1_ok,
        "signature_valid": bool(valid),
        "serialization": SERIALIZATION,
        "named_certificate_only": True,
        **facts,
    }


def transport_failure_disposition(kind: str) -> dict[str, object]:
    """A transport or incomplete-verification failure stops the scan."""
    if kind not in INCOMPLETE_TRANSPORT_KINDS:
        raise BeaconVerifierError("BEACON_UNKNOWN_TRANSPORT_FAILURE")
    return {
        "status": INCOMPLETE,
        "kind": kind,
        "may_advance": False,
        "classification": None,
    }


def chain_continuity_status(
    previous_pulse: Mapping[str, object],
    candidate: Mapping[str, object],
) -> str:
    """Beacon 2.0 previous-link. Chain index is not an eligibility gate."""
    linked = _list_value(candidate, "previous")
    if linked.lower() != str(previous_pulse["outputValue"]).lower():
        return CONTINUITY_FAILED
    return CONTINUITY_OK


def chain_index_blocks_eligibility(chain_index: int) -> bool:
    """A NIST Beacon 2.0 chain transition is not, by itself, disqualifying."""
    del chain_index
    return False


def advance_permitted(assessment: Mapping[str, object], continuity: str) -> bool:
    """Skip only a fully fetched pulse that classified INVALID with continuity intact."""
    if continuity != CONTINUITY_OK:
        return False
    classification = str(assessment.get("classification"))
    if classification == "VALID":
        return False
    if assessment.get("failure_code") is None:
        return False
    return True


def compact_candidate_record(
    *,
    pulse: Mapping[str, object],
    raw_pulse: bytes,
    assessment: Mapping[str, object],
    continuity: str,
) -> dict[str, object]:
    record = {
        "chainIndex": int(pulse["chainIndex"]),
        "pulseIndex": int(pulse["pulseIndex"]),
        "timestamp": _timestamp_text(pulse),
        "raw_pulse_sha256": hashlib.sha256(raw_pulse).hexdigest(),
        "certificateId": str(pulse["certificateId"]),
        "rsa_modulus_bytes": int(assessment["RSA_MODULUS_BYTES"]),
        "signature_bytes": int(assessment["SIGNATURE_BYTES"]),
        "chain_continuity_status": continuity,
        "cryptographic_verification_status": (
            "VALID" if assessment["VALID"] else str(assessment["failure_code"])
        ),
        "classification": assessment["classification"],
    }
    missing = [name for name in COMPACT_RECORD_FIELDS if name not in record]
    if missing:
        raise BeaconVerifierError("BEACON_COMPACT_RECORD")
    return record
