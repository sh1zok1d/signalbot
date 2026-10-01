"""Sequential NIST Beacon 2.0 scan after pulse 1965184.

Uses the frozen verifier. Does not parse BitMEX, draw a seed, or score outputValue.
"""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from scripts.research.d7_nist_beacon_verifier_v1 import (
    CONTINUITY_FAILED,
    CONTINUITY_OK,
    INCOMPLETE,
    BeaconVerifierError,
    advance_permitted,
    assess_pulse,
    chain_continuity_status,
    transport_failure_disposition,
)

ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR_PATH = ROOT / "docs/research/D7_CONFIRMATORY_BEACON_PULSE_V1.json"
VERIFIER_PATH = ROOT / "scripts/research/d7_nist_beacon_verifier_v1.py"
VERIFIER_GIT_BLOB = "bed8a2aa33599b7ce4c0915eb410ad7413747b1d"
VERIFIER_BLOB = VERIFIER_GIT_BLOB
VERIFIER_CONTENT_SHA256 = "eff4533d2094e014fa2fb28ad2afb2b2395edaf766569930974d22954b2192e1"
VERIFIER_COMMIT = "d7f7687a6b30f9d5193b77ec8f4c3f94ec54c379"
VERIFIER_TREE = "8b47c2422f54d1e3f8f62aaf85e8eb37274cf3c3"
PREDECESSOR_INDEX = 1965184
CUTOFF = datetime(2026, 10, 1, 7, 9, 59, tzinfo=timezone.utc)
MAX_CANDIDATES_PER_INVOCATION = 1000
BEACON_ROOT = "https://beacon.nist.gov/beacon/2.0"
Fetch = Callable[[str], bytes]


class ScanStop(Exception):
    def __init__(self, status: str, *, kind: str | None = None, pulse: dict | None = None, raw: bytes | None = None) -> None:
        super().__init__(status)
        self.status = status
        self.kind = kind
        self.pulse = pulse
        self.raw = raw


def _stamp(pulse: Mapping[str, object]) -> str:
    value = pulse["timeStamp"]
    if not isinstance(value, str) or len(value) != 24:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:BEACON_TIMESTAMP_FORMAT", pulse=dict(pulse))
    return value


def _instant(stamp: str) -> datetime:
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:BEACON_TIMESTAMP_FORMAT") from exc


def _pulse_from_body(raw: bytes) -> dict:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScanStop(INCOMPLETE, kind="MALFORMED_TRANSPORT") from exc
    pulse = body["pulse"] if isinstance(body, dict) and "pulse" in body else body
    if not isinstance(pulse, dict) or "outputValue" not in pulse:
        raise ScanStop(INCOMPLETE, kind="MALFORMED_TRANSPORT")
    return pulse


def _next_url(stamp: str) -> str:
    millis = int(_instant(stamp).timestamp() * 1000)
    return f"{BEACON_ROOT}/pulse/time/next/{millis}"


def _certificate_url(certificate_id: str) -> str:
    return f"{BEACON_ROOT}/certificate/{certificate_id}"


def urllib_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "signalbot-d7-beacon-scan/1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ScanStop(INCOMPLETE, kind="UNEXPECTED_404") from exc
        if 500 <= exc.code <= 599:
            raise ScanStop(INCOMPLETE, kind="HTTP_5XX") from exc
        raise ScanStop(INCOMPLETE, kind="MALFORMED_TRANSPORT") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ScanStop(INCOMPLETE, kind="HTTP_TIMEOUT") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc)).lower()
        if "timed out" in reason:
            raise ScanStop(INCOMPLETE, kind="HTTP_TIMEOUT") from exc
        if "ssl" in reason or "tls" in reason or "certificate verify" in reason:
            raise ScanStop(INCOMPLETE, kind="TLS") from exc
        raise ScanStop(INCOMPLETE, kind="DNS_OR_NETWORK") from exc
    if not body:
        raise ScanStop(INCOMPLETE, kind="TRUNCATED_RESPONSE")
    return body


def _require_frozen_verifier() -> None:
    """Refuse to scan if the frozen verifier bytes moved."""
    raw = VERIFIER_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != VERIFIER_CONTENT_SHA256:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:VERIFIER_BYTES_CHANGED")
    header = f"blob {len(raw)}\0".encode("ascii") + raw
    if hashlib.sha1(header).hexdigest() != VERIFIER_GIT_BLOB:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:VERIFIER_BYTES_CHANGED")


def _ledger_row(sequence: int, pulse: Mapping[str, object], raw: bytes, assessment: Mapping[str, object]) -> dict[str, object]:
    final = "VALID" if assessment["VALID"] else "INVALID"
    return {
        "sequence": sequence,
        "chainIndex": int(pulse["chainIndex"]),
        "pulseIndex": int(pulse["pulseIndex"]),
        "timestamp": _stamp(pulse),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "certificateId": str(pulse["certificateId"]),
        "modulus_bytes": int(assessment["RSA_MODULUS_BYTES"]),
        "signature_bytes": int(assessment["SIGNATURE_BYTES"]),
        "continuity": "PASS",
        "signature_verification": "PASS" if assessment["pkcs1_sha512_valid"] else "FAIL",
        "output_integrity": "PASS" if assessment["output_matches_serialization"] else "FAIL",
        "classification": str(assessment.get("classification")),
        "final_status": final,
    }


def _identity(pulse: Mapping[str, object]) -> str:
    return f"{int(pulse['chainIndex'])}/{int(pulse['pulseIndex'])}"


def scan(
    predecessor: Mapping[str, object],
    fetch: Fetch,
    *,
    max_candidates: int = MAX_CANDIDATES_PER_INVOCATION,
    assess: Callable[[Mapping[str, object], bytes], Mapping[str, object]] = assess_pulse,
    require_frozen_predecessor: bool = True,
) -> dict[str, object]:
    """Walk chronological successors. Stop at the first VALID pulse."""
    if max_candidates < 1:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:BATCH_LIMIT")
    if require_frozen_predecessor and int(predecessor["pulseIndex"]) != PREDECESSOR_INDEX:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:PREDECESSOR")
    rows: list[dict[str, object]] = []
    certificates: dict[str, bytes] = {}
    raw_by_identity: dict[str, bytes] = {}
    previous = predecessor
    selected_raw: bytes | None = None
    selected_cert: bytes | None = None
    stop_status = "D7_CONFIRMATORY_BEACON_SCAN_CONTINUATION_REQUIRED"
    incomplete_kind = None
    boundary_raw: bytes | None = None
    for _ in range(max_candidates):
        try:
            raw = fetch(_next_url(_stamp(previous)))
            pulse = _pulse_from_body(raw)
        except ScanStop as exc:
            if exc.status != INCOMPLETE:
                raise
            transport_failure_disposition(str(exc.kind))
            stop_status = INCOMPLETE
            incomplete_kind = exc.kind
            break
        try:
            stamp = _stamp(pulse)
            instant = _instant(stamp)
            previous_instant = _instant(_stamp(previous))
            if instant <= previous_instant or instant < CUTOFF or int(pulse["pulseIndex"]) == int(previous["pulseIndex"]):
                boundary_raw = raw
                stop_status = "BEACON_VERIFICATION_AMBIGUOUS:NON_INCREASING_TIMESTAMP"
                break
            continuity = chain_continuity_status(previous, pulse)
        except ScanStop as exc:
            boundary_raw = raw
            stop_status = exc.status
            break
        except BeaconVerifierError as exc:
            boundary_raw = raw
            stop_status = f"BEACON_VERIFICATION_AMBIGUOUS:{exc.code}"
            break
        except (KeyError, TypeError, ValueError):
            boundary_raw = raw
            stop_status = "BEACON_VERIFICATION_AMBIGUOUS:PULSE_FIELDS"
            break
        if continuity != CONTINUITY_OK:
            boundary_raw = raw
            stop_status = CONTINUITY_FAILED
            rows.append(
                {
                    "sequence": len(rows) + 1,
                    "chainIndex": int(pulse["chainIndex"]),
                    "pulseIndex": int(pulse["pulseIndex"]),
                    "timestamp": stamp,
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "certificateId": str(pulse.get("certificateId", "")),
                    "modulus_bytes": None,
                    "signature_bytes": None,
                    "continuity": "FAIL",
                    "signature_verification": None,
                    "output_integrity": None,
                    "final_status": CONTINUITY_FAILED,
                }
            )
            break
        certificate_id = str(pulse["certificateId"])
        if certificate_id not in certificates:
            try:
                certificates[certificate_id] = fetch(_certificate_url(certificate_id))
            except ScanStop as exc:
                if exc.status != INCOMPLETE:
                    raise
                kind = "CERTIFICATE_FETCH_FAILED" if exc.kind == "UNEXPECTED_404" else exc.kind
                transport_failure_disposition(str(kind))
                stop_status = INCOMPLETE
                incomplete_kind = kind
                boundary_raw = raw
                break
        try:
            assessment = assess(pulse, certificates[certificate_id])
        except BeaconVerifierError as exc:
            boundary_raw = raw
            stop_status = f"BEACON_VERIFICATION_AMBIGUOUS:{exc.code}"
            break
        except (KeyError, TypeError, ValueError):
            boundary_raw = raw
            stop_status = "BEACON_VERIFICATION_AMBIGUOUS:ASSESSMENT_FIELDS"
            break
        row = _ledger_row(len(rows) + 1, pulse, raw, assessment)
        rows.append(row)
        raw_by_identity[_identity(pulse)] = raw
        if assessment["VALID"]:
            if advance_permitted(assessment, continuity):
                boundary_raw = raw
                stop_status = "BEACON_VERIFICATION_AMBIGUOUS:VALID_ADVANCE_CONFLICT"
                break
            selected_raw = raw
            selected_cert = certificates[certificate_id]
            stop_status = "SELECTED"
            previous = pulse
            break
        if not advance_permitted(assessment, continuity):
            boundary_raw = raw
            stop_status = "BEACON_VERIFICATION_AMBIGUOUS:INVALID_NOT_SKIPPABLE"
            break
        previous = pulse
    else:
        stop_status = "D7_CONFIRMATORY_BEACON_SCAN_CONTINUATION_REQUIRED"
    classified = [row for row in rows if row["final_status"] in {"VALID", "INVALID"}]
    last = classified[-1] if classified else None
    if last is None:
        last_identity = _identity(predecessor)
        next_required = f"chronological successor of {last_identity}"
    elif stop_status == "SELECTED":
        last_identity = f"{last['chainIndex']}/{last['pulseIndex']}"
        next_required = None
    else:
        last_identity = f"{last['chainIndex']}/{last['pulseIndex']}"
        next_required = f"chronological successor of {last_identity}"
    valid_count = sum(1 for row in rows if row["final_status"] == "VALID")
    invalid_count = sum(1 for row in rows if row["final_status"] == "INVALID")
    cursor_raw = None if last is None else raw_by_identity.get(f"{last['chainIndex']}/{last['pulseIndex']}")
    return {
        "CONFIRMATORY_RNG_GENERATED": False,
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
        "D7_PRIMARY_EFFECT_COMPUTED": False,
        "LAST_COMPLETELY_CLASSIFIED_CANDIDATE": last_identity if stop_status != "SELECTED" else last_identity,
        "MAX_CANDIDATES_PER_INVOCATION": max_candidates,
        "NEXT_REQUIRED_CANDIDATE": next_required,
        "SELECTED_CONFIRMATORY_BEACON": _identity(previous) if stop_status == "SELECTED" else "NONE",
        "VERIFIER_BLOB_SHA256": VERIFIER_GIT_BLOB,
        "VERIFIER_CONTENT_SHA256": VERIFIER_CONTENT_SHA256,
        "VERIFIER_COMMIT": VERIFIER_COMMIT,
        "VERIFIER_TREE": VERIFIER_TREE,
        "boundary_raw": boundary_raw,
        "continuity_edges": len(rows),
        "cursor_raw": cursor_raw,
        "examined": len(rows),
        "first_candidate": None if not rows else f"{rows[0]['chainIndex']}/{rows[0]['pulseIndex']}",
        "incomplete_count": 1 if stop_status == INCOMPLETE else 0,
        "incomplete_kind": incomplete_kind,
        "invalid_count": invalid_count,
        "last_candidate": None if not rows else f"{rows[-1]['chainIndex']}/{rows[-1]['pulseIndex']}",
        "rows": rows,
        "selected_certificate": selected_cert,
        "selected_raw": selected_raw,
        "status": stop_status,
        "valid_count": valid_count,
        "continuity_all_pass": bool(rows) and all(row["continuity"] == "PASS" for row in rows),
    }


def load_predecessor() -> dict:
    pulse = _pulse_from_body(PREDECESSOR_PATH.read_bytes())
    if int(pulse["pulseIndex"]) != PREDECESSOR_INDEX:
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:PREDECESSOR")
    if _stamp(pulse) != "2026-10-01T07:10:00.000Z":
        raise ScanStop("BEACON_VERIFICATION_AMBIGUOUS:PREDECESSOR")
    return pulse


def main() -> dict[str, object]:
    _require_frozen_verifier()
    try:
        result = scan(load_predecessor(), urllib_fetch)
    except ScanStop as exc:
        result = {
            "CONFIRMATORY_RNG_GENERATED": False,
            "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
            "D7_PRIMARY_EFFECT_COMPUTED": False,
            "SELECTED_CONFIRMATORY_BEACON": "NONE",
            "VERIFIER_COMMIT": VERIFIER_COMMIT,
            "VERIFIER_TREE": VERIFIER_TREE,
            "boundary_raw": exc.raw,
            "examined": 0,
            "incomplete_kind": exc.kind,
            "rows": [],
            "status": exc.status,
            "valid_count": 0,
            "invalid_count": 0,
            "incomplete_count": 1 if exc.status == INCOMPLETE else 0,
        }
    out_dir = ROOT / "docs/research"
    ledger = out_dir / "D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl"
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in result["rows"]]
    ledger.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if result.get("selected_raw"):
        (out_dir / "D7_CONFIRMATORY_SELECTED_BEACON_PULSE_V1.json").write_bytes(result["selected_raw"])
        (out_dir / "D7_CONFIRMATORY_SELECTED_BEACON_CERTIFICATE_V1.crt").write_bytes(result["selected_certificate"])
    if result.get("boundary_raw"):
        (out_dir / "D7_CONFIRMATORY_BEACON_SCAN_V1_BOUNDARY.json").write_bytes(result["boundary_raw"])
    if result.get("cursor_raw") and result.get("status") != "SELECTED":
        (out_dir / "D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json").write_bytes(result["cursor_raw"])
    public = {
        key: value
        for key, value in result.items()
        if key not in {"rows", "selected_raw", "selected_certificate", "boundary_raw", "cursor_raw"}
    }
    public["ledger_path"] = "docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl"
    text = json.dumps(public, sort_keys=True, separators=(",", ":"), allow_nan=False)
    (out_dir / "D7_CONFIRMATORY_BEACON_SCAN_V1.json").write_text(text, encoding="utf-8")
    print(text)
    return result


if __name__ == "__main__":
    main()
