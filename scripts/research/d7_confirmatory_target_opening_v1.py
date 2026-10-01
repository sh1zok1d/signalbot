"""One authorized D7 confirmatory opening.

Identity is checked before the canonical source is parsed. The NIST pulse is
the first verified Beacon 2.0 pulse at or after the frozen cutoff. The
bootstrap is the audited ``run_primary`` path; studentized replicates are
retained in that same pass so the preregistered lower bound can be sealed
with the primary result.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from scripts.research.d7_bitmex_support_and_power_v0 import (
    CANONICAL_REL,
    EXPECTED_CANONICAL_GZ_SHA256,
    HOUR_MS,
    aggregate_completed_hours,
    build_predictor_frame,
    load_5m_bars,
    structural_target_eligible,
    support_from_frame,
)
from scripts.research.d7_eligible_index_gap_break_v1 import GAP_START_MS
from scripts.research.discovery_sprint_02_impl import d7_selector_digest
from scripts.research.self_referential_contrast_v1 import contrast as contrast_module
from scripts.research.self_referential_contrast_v1.confirmatory_contract import (
    NUMPY_RECORD_SHA256,
    NUMPY_VERSION_REQUIRED,
    PROFILE_VERSION,
    R_CONFIRMATORY,
    SELECTOR_DIGEST,
    bootstrap_critical_floor,
    confirmatory_seed_digest,
    confirmatory_seed_message,
    directional_confirmation_pass,
    dwb_one_sided_lower_bound,
    integrity_pass,
    magnitude_classification,
    seed_sequence_from_confirmatory_digest,
    statistical_implementation_digest,
)
from scripts.research.self_referential_contrast_v1.constants import (
    CONFIRMATORY_PURPOSE,
    PROFILE_ID,
    R_CONFIRMATORY as R_CONST,
    STATUS_PRIMARY_COMPLETED,
)
from scripts.research.self_referential_contrast_v1.contrast import (
    ContrastInput,
    bartlett_variance,
    classify_bootstrap_variance,
    counts_as_exceedance,
    finite_r_tail,
    indexed_epsilon_sampler,
    primitive_moments,
    run_primary,
)
from scripts.research.self_referential_contrast_v1.multipliers import (
    epsilon_width,
    moving_average_multipliers,
)

ROOT = Path(__file__).resolve().parents[2]
ART = Path("/opt/cursor/artifacts/official_d7_confirmatory_v1")
FREEZE_COMMIT = "5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b"
FREEZE_MANIFEST_SHA256 = "2aaa228c40a486f3b7fa208ec62f3c19bb63318a65e8d7d19b8c1e211c751e07"
ADAPTER_DIGEST = "260dd8f6a30ff48a1cecdb306b4d5bb7c90930d5123095d08b9400234c51b579"
DECISION_RULE_DIGEST = "39c5a727ee6ac5c6877924670a6acc1520584b312ae6ddf49a206a2656e34751"
IMPLEMENTATION_DIGEST = "3347d43575ac7532b9ae34a831a1783d95a4b9b3def923b35d4b099562d87d20"
SOURCE_SHA = "33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c"
FREEZE_SERVER_TIME = datetime(2026, 10, 1, 6, 9, 59, tzinfo=timezone.utc)
ELIGIBLE_INSTANT = datetime(2026, 10, 1, 7, 9, 59, tzinfo=timezone.utc)
BEACON_ID = "NIST-Beacon-2.0"
DECLARED = (
    "2016:0",
    "2016:1",
    "2016:2",
    "2016:3",
    "2017:0",
    "2017:1",
    "2017:2",
    "2017:3",
    "2018:0",
    "2018:1",
    "2018:2",
    "2018:3",
    "2019:0",
    "2019:1",
    "2019:2",
    "2019:3",
)
YEAR_MASS = {"2016": 4079, "2017": 8757, "2018": 8759, "2019": 8759}
TEMPORAL_YEARS = ("2017", "2018", "2019")


class OpeningStop(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _u64(value: int) -> bytes:
    return int(value).to_bytes(8, "big")


def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "big")


def _ser_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _u32(len(encoded)) + encoded


def _ser_hash(value: str) -> bytes:
    raw = bytes.fromhex(value)
    if len(raw) != 64:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_HASH_LENGTH")
    return _u32(64) + raw


def _list_value(pulse: dict, kind: str) -> str:
    for item in pulse["listValues"]:
        if item["type"] == kind:
            return str(item["value"])
    raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_LIST_VALUE")


def _timestamp_text(pulse: dict) -> str:
    value = pulse["timeStamp"]
    if not isinstance(value, str) or len(value) != 24:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_TIMESTAMP_FORMAT")
    return value


def _timestamp_instant(text: str) -> datetime:
    parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return parsed


def _signature_preimage(pulse: dict) -> bytes:
    external = pulse["external"]
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


def _output_preimage(pulse: dict) -> bytes:
    signature = bytes.fromhex(str(pulse["signatureValue"]))
    if len(signature) != 512:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_SIGNATURE_LENGTH")
    return _signature_preimage(pulse) + signature


def _verify_pulse(pulse: dict, certificate_pem: bytes) -> dict[str, object]:
    if int(pulse["cipherSuite"]) != 0:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_CIPHER_SUITE")
    preimage = _signature_preimage(pulse)
    output = hashlib.sha512(_output_preimage(pulse)).hexdigest()
    if output.lower() != str(pulse["outputValue"]).lower():
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_OUTPUT_MISMATCH")
    certificate = x509.load_pem_x509_certificate(certificate_pem)
    der = certificate.public_bytes(encoding=serialization_encoding())
    cert_hash = hashlib.sha512(der).hexdigest()
    if cert_hash.lower() != str(pulse["certificateId"]).lower():
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_CERTIFICATE_HASH")
    try:
        certificate.public_key().verify(
            bytes.fromhex(str(pulse["signatureValue"])),
            preimage,
            padding.PKCS1v15(),
            hashes.SHA512(),
        )
    except InvalidSignature as exc:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_SIGNATURE_INVALID") from exc
    return {
        "signature_valid": True,
        "output_matches_serialization": True,
        "certificate_sha512_matches_certificateId": True,
        "serialization": "NIST_BEACON_2_0_UINT32_LENGTH_PREFIX",
    }


def serialization_encoding():
    from cryptography.hazmat.primitives.serialization import Encoding

    return Encoding.DER


def _http_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "signalbot-d7-confirmatory/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _pulse_from_bytes(payload: bytes) -> dict:
    body = json.loads(payload)
    pulse = body["pulse"] if isinstance(body, dict) and "pulse" in body else body
    if "outputValue" not in pulse:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_RECORD")
    return pulse


def _wait_for_cutoff() -> None:
    while datetime.now(timezone.utc) < ELIGIBLE_INSTANT:
        remaining = (ELIGIBLE_INSTANT - datetime.now(timezone.utc)).total_seconds()
        time.sleep(min(20.0, max(1.0, remaining)))


def _previous_uri(pulse: dict) -> str:
    for item in pulse["listValues"]:
        if item["type"] == "previous" and item.get("uri"):
            return str(item["uri"])
    raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_PREVIOUS_URI")


def _earliest_eligible(raw: bytes) -> tuple[dict, bytes]:
    pulse = _pulse_from_bytes(raw)
    instant = _timestamp_instant(_timestamp_text(pulse))
    if instant < ELIGIBLE_INSTANT or instant < FREEZE_SERVER_TIME:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_BEFORE_CUTOFF")
    for _ in range(8):
        previous_raw = _http_bytes(_previous_uri(pulse))
        previous = _pulse_from_bytes(previous_raw)
        previous_instant = _timestamp_instant(_timestamp_text(previous))
        if previous_instant >= instant:
            raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_PREVIOUS_ORDER")
        if previous_instant < ELIGIBLE_INSTANT:
            return pulse, raw
        pulse = previous
        raw = previous_raw
        instant = previous_instant
    raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:EARLIER_ELIGIBLE_PULSE")


def _assert_saved_pulse_is_first(pulse: dict) -> None:
    previous = _pulse_from_bytes(_http_bytes(_previous_uri(pulse)))
    previous_instant = _timestamp_instant(_timestamp_text(previous))
    if previous_instant >= ELIGIBLE_INSTANT:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:EARLIER_ELIGIBLE_PULSE")


def _select_beacon() -> tuple[dict, bytes, bytes, dict]:
    saved = ART / "beacon_pulse.json"
    cert_path = ART / "beacon_certificate.pem"
    ART.mkdir(parents=True, exist_ok=True)
    if saved.exists():
        raw = saved.read_bytes()
        pulse = _pulse_from_bytes(raw)
        instant = _timestamp_instant(_timestamp_text(pulse))
        if instant < ELIGIBLE_INSTANT or instant < FREEZE_SERVER_TIME:
            raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_BEFORE_CUTOFF")
        _assert_saved_pulse_is_first(pulse)
        if not cert_path.exists():
            certificate = _http_bytes(
                f"https://beacon.nist.gov/beacon/2.0/certificate/{pulse['certificateId']}"
            )
            cert_path.write_bytes(certificate)
        certificate = cert_path.read_bytes()
        verification = _verify_pulse(pulse, certificate)
        return pulse, raw, certificate, verification
    _wait_for_cutoff()
    cutoff_ms = int(ELIGIBLE_INSTANT.timestamp() * 1000)
    raw = _http_bytes(f"https://beacon.nist.gov/beacon/2.0/pulse/time/{cutoff_ms}")
    pulse = _pulse_from_bytes(raw)
    instant = _timestamp_instant(_timestamp_text(pulse))
    if instant < ELIGIBLE_INSTANT:
        stamp_ms = int(instant.timestamp() * 1000)
        raw = _http_bytes(f"https://beacon.nist.gov/beacon/2.0/pulse/time/next/{stamp_ms}")
        pulse = _pulse_from_bytes(raw)
        instant = _timestamp_instant(_timestamp_text(pulse))
    if instant < ELIGIBLE_INSTANT or instant < FREEZE_SERVER_TIME:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_BEFORE_CUTOFF")
    pulse, raw = _earliest_eligible(raw)
    saved.write_bytes(raw)
    certificate = _http_bytes(
        f"https://beacon.nist.gov/beacon/2.0/certificate/{pulse['certificateId']}"
    )
    cert_path.write_bytes(certificate)
    verification = _verify_pulse(pulse, certificate)
    return pulse, raw, certificate, verification


def _identity() -> None:
    if R_CONST != 9999 or R_CONFIRMATORY != 9999:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    if np.__version__ != NUMPY_VERSION_REQUIRED:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    record = Path(
        "/home/ubuntu/.local/lib/python3.11/site-packages/numpy-2.1.3.dist-info/RECORD"
    ).read_bytes()
    if hashlib.sha256(record).hexdigest() != NUMPY_RECORD_SHA256:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    manifest_path = ROOT / "docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json"
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != FREEZE_MANIFEST_SHA256:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    manifest = json.loads(manifest_bytes)
    if statistical_implementation_digest(manifest) != IMPLEMENTATION_DIGEST:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    for item in manifest["files"]:
        payload = (ROOT / item["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    adapter = (ROOT / "docs/research/D7_CONFIRMATORY_ADAPTER_V1.json").read_bytes()
    decision = (ROOT / "docs/research/D7_DIRECTIONAL_CONFIRMATION_DECISION_RULE_V1.json").read_bytes()
    if hashlib.sha256(adapter).hexdigest() != ADAPTER_DIGEST:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    if hashlib.sha256(decision).hexdigest() != DECISION_RULE_DIGEST:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")
    source = ROOT / CANONICAL_REL
    if _sha256_file(source) != SOURCE_SHA or SOURCE_SHA != EXPECTED_CANONICAL_GZ_SHA256:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:IDENTITY_MISMATCH")


def _seed(pulse: dict) -> bytes:
    message = confirmatory_seed_message(
        {
            "adapter_digest": ADAPTER_DIGEST,
            "beacon_id": BEACON_ID,
            "beacon_output_value": str(pulse["outputValue"]),
            "beacon_pulse_time": _timestamp_text(pulse),
            "decision_rule_digest": DECISION_RULE_DIGEST,
            "freeze_manifest_sha256": FREEZE_MANIFEST_SHA256,
            "numpy_record_sha256": NUMPY_RECORD_SHA256,
            "numpy_version": NUMPY_VERSION_REQUIRED,
            "profile_id": PROFILE_ID,
            "profile_version": PROFILE_VERSION,
            "purpose": CONFIRMATORY_PURPOSE,
            "r_confirmatory": R_CONFIRMATORY,
            "statistical_implementation_digest": IMPLEMENTATION_DIGEST,
            "target_source_digest": SOURCE_SHA,
        }
    )
    digest = confirmatory_seed_digest(message)
    sequence = seed_sequence_from_confirmatory_digest(digest)
    if len(list(sequence.entropy)) != 8:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:SEED_ENTROPY")
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "seed_message.json").write_bytes(message.encode("utf-8"))
    (ART / "seed_digest.hex").write_text(digest.hex(), encoding="utf-8")
    return digest


def _retaining_tail(
    centered: np.ndarray,
    segments: list[tuple[int, int]],
    bandwidth: int,
    t_obs: float,
    replicates: int,
    epsilon_sampler,
    draw_batch_size: int,
) -> dict:
    values: list[float] = []
    t_count = centered.shape[0]
    exceedance = 0
    scale = math.sqrt(t_count)
    for batch_start in range(0, replicates, draw_batch_size):
        batch_end = min(replicates, batch_start + draw_batch_size)
        draw_ids = range(batch_start, batch_end)
        batch = len(draw_ids)
        eta = np.empty((batch, t_count), dtype=np.float64)
        for segment_index, (start, stop) in enumerate(segments):
            width = epsilon_width(stop - start, bandwidth)
            shocks = np.empty((batch, width), dtype=np.float64)
            for row, draw_index in enumerate(draw_ids):
                shocks[row] = np.asarray(
                    epsilon_sampler(draw_index, segment_index, width), dtype=np.float64
                )
            eta[:, start:stop] = moving_average_multipliers(shocks, bandwidth)
        starred = eta * centered[None, :]
        numerators = starred.sum(axis=1) / scale
        variances, gamma0 = bartlett_variance(starred, segments, bandwidth)
        for row, draw_index in enumerate(draw_ids):
            status = classify_bootstrap_variance(
                float(variances[row]), float(gamma0[row]), bandwidth, t_count
            )
            if status != "POSITIVE":
                return {"inference_status": status, "failed_draw_index": int(draw_index)}
            studentized = float(numerators[row]) / math.sqrt(float(variances[row]))
            values.append(studentized)
            if counts_as_exceedance(studentized, t_obs):
                exceedance += 1
    tail = finite_r_tail(exceedance, replicates)
    tail["inference_status"] = STATUS_PRIMARY_COMPLETED
    tail["studentized"] = values
    return tail


def _open_target(seed: bytes) -> dict[str, object]:
    source = ROOT / CANONICAL_REL
    before = _sha256_file(source)
    hours = aggregate_completed_hours(load_5m_bars(source))
    frame = build_predictor_frame(hours)
    support = support_from_frame(frame)
    if support["SELECTOR_DIGEST"] != SELECTOR_DIGEST or d7_selector_digest([]) == SELECTOR_DIGEST:
        if support["SELECTOR_DIGEST"] != SELECTOR_DIGEST:
            raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:SELECTOR_DIGEST_MISMATCH")
    eligible = structural_target_eligible(frame.hour_start_ms, frame.state_defined)
    lookup = {int(frame.hour_start_ms[i]): i for i in range(int(frame.hour_start_ms.size))}
    xs: list[float] = []
    ys: list[float] = []
    cells: list[str] = []
    blocks: list[str] = []
    years: list[int] = []
    before_gap = 0
    for index in range(int(frame.hour_start_ms.size)):
        if not bool(eligible[index]) or int(frame.rv_bucket[index]) < 0:
            continue
        stamp = int(frame.hour_start_ms[index])
        nxt = lookup.get(stamp + HOUR_MS)
        if nxt is None:
            raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:MISSING_LEAD_HOUR")
        if stamp < GAP_START_MS:
            before_gap += 1
        xs.append(1.0 if frame.state[index] is True else 0.0)
        ys.append(1.0 if frame.state[nxt] is True else 0.0)
        year = int(frame.year[index])
        cells.append(f"{year}:{int(frame.rv_bucket[index])}")
        blocks.append(str(year))
        years.append(year)
    t_count = len(xs)
    if t_count != 30354 or before_gap != 3503:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:GEOMETRY_MISMATCH")
    year_counts = {year: 0 for year in YEAR_MASS}
    for year in years:
        year_counts[str(year)] = year_counts.get(str(year), 0) + 1
    if year_counts != YEAR_MASS:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:GEOMETRY_MISMATCH")
    segment = np.asarray([0] * 3503 + [1] * (t_count - 3503), dtype=np.int64)
    data = ContrastInput(
        x=np.asarray(xs, dtype=np.float64),
        y=np.asarray(ys, dtype=np.float64),
        cell=np.asarray(cells, dtype=object),
        block=np.asarray(blocks, dtype=object),
        segment_id=segment,
        declared_cells=DECLARED,
        h_mechanical=721,
    )
    retained: dict[str, object] = {}

    def _capture(*args, **kwargs):
        tail = _retaining_tail(*args, **kwargs)
        retained["tail"] = tail
        public = {key: value for key, value in tail.items() if key != "studentized"}
        return public

    contrast_module._bootstrap_tail = _capture
    sampler = indexed_epsilon_sampler(seed)
    result = run_primary(
        data,
        replicates=9999,
        epsilon_sampler=sampler,
        draw_batch_size=64,
        compute_sensitivity=False,
    )
    after = _sha256_file(source)
    tail = retained.get("tail")
    if not isinstance(tail, dict) or result["inference_status"] != STATUS_PRIMARY_COMPLETED:
        status = result["inference_status"]
        raise OpeningStop(f"D7_CONFIRMATORY_EXECUTION_FAILED:{status}")
    studentized = [float(item) for item in tail["studentized"]]
    if int(result["exceedance_count"]) != int(tail["exceedance_count"]):
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:EXCEEDANCE_MISMATCH")
    if len(studentized) != 9999:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:REPLICATE_COUNT")
    year_theta = {}
    x_arr = data.x
    y_arr = data.y
    cell_arr = data.cell
    for year in ("2016", "2017", "2018", "2019"):
        mask = np.asarray([label.startswith(year + ":") for label in cells])
        declared = tuple(name for name in DECLARED if name.startswith(year + ":"))
        moments = primitive_moments(
            ContrastInput(
                x=x_arr[mask],
                y=y_arr[mask],
                cell=cell_arr[mask],
                block=np.asarray([year] * int(mask.sum()), dtype=object),
                segment_id=np.zeros(int(mask.sum()), dtype=np.int64),
                declared_cells=declared,
                h_mechanical=721,
            )
        )
        year_theta[year] = None if moments["status"] != "DEFINED" else float(moments["theta_hat"])
    theta = float(result["theta_hat"])
    variance = float(result["observed_variance"])
    lower = dwb_one_sided_lower_bound(
        theta_hat=theta,
        observed_variance=variance,
        t_count=30354,
        studentized=studentized,
    )
    critical = bootstrap_critical_floor(studentized)
    magnitude = magnitude_classification(lower)
    temporal_hits = 0
    for year in TEMPORAL_YEARS:
        value = year_theta[year]
        if value is not None and value > 0.0:
            temporal_hits += 1
    temporal_pass = temporal_hits >= 2
    exceedance = int(result["exceedance_count"])
    statistical_reject = bool(
        result["inference_status"] == STATUS_PRIMARY_COMPLETED
        and variance > 0.0
        and int(result["R"]) == 9999
        and exceedance <= 499
    )
    pins = {
        "adapter_digest": ADAPTER_DIGEST,
        "canonical_source_sha256": SOURCE_SHA,
        "confirmatory_seed_digest": seed.hex(),
        "statistical_implementation_digest": IMPLEMENTATION_DIGEST,
    }
    observed = {
        "T": 30354,
        "adapter_digest": ADAPTER_DIGEST,
        "canonical_source_sha256": before,
        "confirmatory_seed_digest": seed.hex(),
        "eligible_index_gap_break": before_gap,
        "forbidden_input_accessed": False,
        "inference_status": result["inference_status"],
        "numpy_record_sha256": NUMPY_RECORD_SHA256,
        "numpy_version": NUMPY_VERSION_REQUIRED,
        "statistical_implementation_digest": IMPLEMENTATION_DIGEST,
        "structural_segments": [3503, t_count - 3503],
        "target_mutated": before != after,
        "year_eligible_masses": year_counts,
    }
    integrity = integrity_pass(observed, pins)
    passed = directional_confirmation_pass(
        inference_status=str(result["inference_status"]),
        statistical_reject=statistical_reject,
        temporal_pass=temporal_pass,
        integrity=integrity,
    )
    label = "CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS" if passed else "DIRECTIONAL_NON_REJECTION"
    if result["inference_status"] != STATUS_PRIMARY_COMPLETED:
        label = str(result["inference_status"])
    se = math.sqrt(variance) / math.sqrt(30354)
    return {
        "B_T": int(result["B_T"]),
        "D7_BITMEX_PRIMARY_TARGET_OPENED": True,
        "D7_DIRECTIONAL_CONFIRMATION_PASS": passed,
        "D7_PRIMARY_EFFECT_COMPUTED": True,
        "INTEGRITY_PASS": integrity,
        "L": lower,
        "L_hex": float(lower).hex(),
        "MAGNITUDE_AT_0_05_SUPPORTED": bool(magnitude["MAGNITUDE_AT_0_05_SUPPORTED"]),
        "MAGNITUDE_CLASS": magnitude["MAGNITUDE_CLASS"],
        "R": 9999,
        "SE_theta_hat": se,
        "SE_theta_hat_hex": float(se).hex(),
        "STATISTICAL_REJECT": statistical_reject,
        "T": 30354,
        "T_obs": float(result["T_obs"]),
        "T_obs_hex": float(result["T_obs"]).hex(),
        "TEMPORAL_PASS": temporal_pass,
        "V_obs": variance,
        "V_obs_hex": float(variance).hex(),
        "bootstrap_critical_floor": critical,
        "eligible_index_gap_break": 3503,
        "evidence_label": label,
        "exceedance_count": exceedance,
        "inference_status": result["inference_status"],
        "p_denominator": int(result["p_denominator"]),
        "p_numerator": int(result["p_numerator"]),
        "p_value": float(result["p_value"]),
        "primary_method": result["primary_method"],
        "structural_segments": [3503, 26851],
        "target_mutated": before != after,
        "theta_hat": theta,
        "theta_hat_hex": float(theta).hex(),
        "year_eligible_masses": year_counts,
        "year_theta_hat": year_theta,
        "year_theta_hat_hex": {
            year: None if value is None else float(value).hex() for year, value in year_theta.items()
        },
    }


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    _identity()
    pulse, raw, _certificate, verification = _select_beacon()
    instant = _timestamp_instant(_timestamp_text(pulse))
    if instant < ELIGIBLE_INSTANT:
        raise OpeningStop("D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_BEFORE_CUTOFF")
    seed = _seed(pulse)
    beacon_record = {
        "BEACON_FETCHED": True,
        "CONFIRMATORY_RNG_GENERATED": True,
        "D7_BITMEX_PRIMARY_TARGET_OPENED": False,
        "beacon_id": BEACON_ID,
        "certificate_id": pulse["certificateId"],
        "chain_index": pulse["chainIndex"],
        "output_value": pulse["outputValue"],
        "pulse_index": pulse["pulseIndex"],
        "pulse_uri": pulse["uri"],
        "raw_record_sha256": hashlib.sha256(raw).hexdigest(),
        "timeStamp": _timestamp_text(pulse),
        "verification": verification,
    }
    (ART / "beacon_selected.json").write_text(
        json.dumps(beacon_record, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    primary = _open_target(seed)
    primary.update(
        {
            "ADAPTER_DIGEST": ADAPTER_DIGEST,
            "BEACON_FETCHED": True,
            "CONFIRMATORY_FREEZE_COMMIT": FREEZE_COMMIT,
            "CONFIRMATORY_RNG_GENERATED": True,
            "DECISION_RULE_DIGEST": DECISION_RULE_DIGEST,
            "FREEZE_MANIFEST_SHA256": FREEZE_MANIFEST_SHA256,
            "FREEZE_SERVER_TIME": "2026-10-01T06:09:59Z",
            "NUMPY_RECORD_SHA256": NUMPY_RECORD_SHA256,
            "NUMPY_VERSION": NUMPY_VERSION_REQUIRED,
            "PRIMARY_RESULT_SEALED": True,
            "STATISTICAL_IMPLEMENTATION_DIGEST": IMPLEMENTATION_DIGEST,
            "TARGET_SOURCE_SHA256": SOURCE_SHA,
            "beacon": beacon_record,
            "profile_id": PROFILE_ID,
            "profile_version": PROFILE_VERSION,
            "purpose": CONFIRMATORY_PURPOSE,
            "seed_digest": seed.hex(),
        }
    )
    text = json.dumps(primary, sort_keys=True, separators=(",", ":"), allow_nan=False)
    out = ROOT / "docs/research/D7_CONFIRMATORY_PRIMARY_RESULT_V1.json"
    out.write_bytes(text.encode("utf-8"))
    sealed_hash = hashlib.sha256(out.read_bytes()).hexdigest()
    (ART / "primary_result_sha256.txt").write_text(sealed_hash + "\n", encoding="utf-8")
    print("PRIMARY_WRITTEN", sealed_hash)
    print("theta_hat", primary["theta_hat_hex"])
    print("exceedance", primary["exceedance_count"])
    print("STATISTICAL_REJECT", primary["STATISTICAL_REJECT"])
    print("TEMPORAL_PASS", primary["TEMPORAL_PASS"])
    print("INTEGRITY_PASS", primary["INTEGRITY_PASS"])
    print("PASS", primary["D7_DIRECTIONAL_CONFIRMATION_PASS"])
    print("LABEL", primary["evidence_label"])
    print("MAGNITUDE", primary["MAGNITUDE_CLASS"])


if __name__ == "__main__":
    try:
        main()
    except OpeningStop as exc:
        ART.mkdir(parents=True, exist_ok=True)
        (ART / "execution_stop.txt").write_text(exc.code + "\n", encoding="utf-8")
        print(exc.code)
        raise SystemExit(2)
