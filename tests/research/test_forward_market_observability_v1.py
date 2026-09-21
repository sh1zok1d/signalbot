"""FORWARD_MARKET_OBSERVABILITY_V1 acquisition tests.

Synthetic/unit only unless the optional live smoke can connect. No future
return / MAE / beta / prediction / classification.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import monotonic_ns

import pytest

from scripts.research.forward_market_observability_v1.clock import (
    ClockWatch,
    ReceiptStamp,
    capture_receipt,
    format_utc_ns,
)
from scripts.research.forward_market_observability_v1.collector import (
    CollectorError,
    SourceRuntime,
)
from scripts.research.forward_market_observability_v1.envelope import (
    decode_raw_payload,
    sha256_bytes,
)
from scripts.research.forward_market_observability_v1.parse import parse_native_fields
from scripts.research.forward_market_observability_v1.schemas import (
    CHUNK_SCHEMA,
    FORBIDDEN_SCIENTIFIC_FIELDS,
    MANIFEST_SCHEMA,
    RAW_ENVELOPE_SCHEMA,
    SOURCE_TYPE_BACKFILL,
    CollectorSchemaError,
    assert_no_scientific_fields,
)
from scripts.research.forward_market_observability_v1.session import create_session
from scripts.research.forward_market_observability_v1.sources import default_config
from scripts.research.forward_market_observability_v1.storage import (
    ChunkStore,
    StorageError,
    quarantine_leftover_partials,
    verify_chunk_sha256,
)
from scripts.research.forward_market_observability_v1.transport import (
    fetch_rest_body,
    rest_response_body_bytes,
    websocket_application_payload_bytes,
)

REPO = Path(__file__).resolve().parents[2]
MARK_JSON = (
    b'{"e":"markPriceUpdate","E":1562305380000,"s":"BTCUSDT",'
    b'"p":"11185.87786614","i":"11784.62659091","P":"11784.25641265",'
    b'"r":"0.00030000","T":1562306400000}'
)
OI_JSON = b'{"openInterest":"23520.636","symbol":"BTCUSDT","time":1589428639544}'
PREMIUM_JSON = (
    b'{"symbol":"BTCUSDT","markPrice":"11793.63102583","indexPrice":"11781.80495983",'
    b'"lastFundingRate":"0.00038246","nextFundingTime":1597392000000,'
    b'"interestRate":"0.00010000","time":1597370495002}'
)


def _stamp_seq(values: list[ReceiptStamp]):
    it = iter(values)

    def _next() -> ReceiptStamp:
        return next(it)

    return _next


def _make_stamp(utc_ns: int, mono: int) -> ReceiptStamp:
    return ReceiptStamp(
        local_received_at_utc=format_utc_ns(utc_ns),
        local_received_monotonic_ns=mono,
        utc_epoch_ns=utc_ns,
    )


def _runtime(tmp_path: Path, *, max_messages: int = 100, stamp_fn=None, parser=None) -> SourceRuntime:
    config = default_config(root_dir=str(tmp_path))
    created = create_session(repo=REPO, root=tmp_path, config=config)
    source = config["sources"][0]
    return SourceRuntime(
        session_id=created["session"]["session_id"],
        session_dir=created["session_dir"],
        source=source,
        max_messages=max_messages,
        max_bytes=1_000_000,
        stamp_fn=stamp_fn or capture_receipt,
        parser=parser or parse_native_fields,
    )


def _ws_receipt(raw: bytes = MARK_JSON):
    return websocket_application_payload_bytes(
        raw.decode("utf-8"),
        endpoint="wss://example/ws",
        stream="btcusdt@markPrice@1s",
    )


def test_receipt_timestamp_assigned_before_parser_invocation(tmp_path):
    order: list[str] = []

    def stamp() -> ReceiptStamp:
        order.append("stamp")
        return capture_receipt()

    def parser(raw: bytes):
        order.append("parse")
        assert order[0] == "stamp"
        return parse_native_fields(raw)

    runtime = _runtime(tmp_path, stamp_fn=stamp, parser=parser)
    runtime.ingest(_ws_receipt())
    assert order[0] == "stamp"
    assert order.index("stamp") < order.index("parse")


def test_monotonic_receipt_order(tmp_path):
    runtime = _runtime(tmp_path)
    first = runtime.ingest(_ws_receipt())["envelope"]
    second = runtime.ingest(_ws_receipt())["envelope"]
    assert second["local_received_monotonic_ns"] >= first["local_received_monotonic_ns"]


def test_raw_bytes_and_sha256_preserved_exactly(tmp_path):
    runtime = _runtime(tmp_path)
    raw = MARK_JSON + b"\xff\x00raw-tail"
    receipt = websocket_application_payload_bytes(
        raw, endpoint="wss://example/ws", stream="btcusdt@markPrice@1s"
    )
    envelope = runtime.ingest(receipt)["envelope"]
    restored = decode_raw_payload(envelope["raw_payload"])
    assert restored == raw
    assert envelope["raw_payload_sha256"] == sha256_bytes(raw)
    assert envelope["raw_payload_length"] == len(raw)
    assert envelope["legal_available_at"] == envelope["local_received_at_utc"]
    assert envelope["schema_version"] == RAW_ENVELOPE_SCHEMA


def test_rest_body_exact_byte_preservation(tmp_path):
    runtime = _runtime(tmp_path)
    receipt = rest_response_body_bytes(
        PREMIUM_JSON,
        endpoint="https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
        stream="GET /fapi/v1/premiumIndex",
        http_status=200,
        content_encoding=None,
    )
    envelope = runtime.ingest(receipt)["envelope"]
    assert decode_raw_payload(envelope["raw_payload"]) == PREMIUM_JSON
    assert envelope["transport"]["transport"] == "rest"
    assert envelope["transport"]["http_status"] == 200


def test_websocket_application_payload_exact_bytes():
    text = MARK_JSON.decode("utf-8")
    receipt = websocket_application_payload_bytes(
        text, endpoint="wss://x", stream="btcusdt@markPrice@1s"
    )
    assert receipt.raw_payload == MARK_JSON
    assert receipt.transport["transport"] == "websocket"
    binary = websocket_application_payload_bytes(
        MARK_JSON, endpoint="wss://x", stream="btcusdt@markPrice@1s"
    )
    assert binary.raw_payload == MARK_JSON
    assert binary.transport["websocket_message_type"] == "binary"


def test_parsed_derivative_references_raw_identity(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.ingest(_ws_receipt())
    parsed = result["parsed"]
    envelope = result["envelope"]
    assert parsed["raw_payload_sha256"] == envelope["raw_payload_sha256"]
    assert parsed["session_id"] == envelope["session_id"]
    assert parsed["root_evidence"] == "raw_envelope"
    assert parsed["native_fields"]["funding_rate"] == "0.00030000"
    assert parsed["native_fields"]["mark_price"] == "11185.87786614"
    assert parsed["legal_available_at"] == envelope["local_received_at_utc"]


def test_append_only_and_completed_chunk_cannot_be_overwritten(tmp_path):
    config = default_config(root_dir=str(tmp_path))
    created = create_session(repo=REPO, root=tmp_path, config=config)
    store = ChunkStore(
        session_dir=created["session_dir"],
        session_id=created["session"]["session_id"],
        source_id="TEST",
        max_messages=2,
        max_bytes=1_000_000,
    )
    runtime = SourceRuntime(
        session_id=created["session"]["session_id"],
        session_dir=created["session_dir"],
        source={"source_id": "TEST", "instrument": "BTCUSDT"},
        max_messages=2,
        max_bytes=1_000_000,
    )
    runtime.store = store
    runtime.ingest(_ws_receipt())
    meta = runtime.ingest(_ws_receipt())["chunk"]
    assert meta["status"] == "COMPLETE"
    chunk_path = created["session_dir"] / meta["path"]
    assert verify_chunk_sha256(chunk_path, meta["sha256"])
    store._next_index = int(meta["chunk_index"])
    with pytest.raises(StorageError, match="CHUNK_ALREADY_EXISTS"):
        store._ensure_open()


def test_chunk_sha_and_manifest_ordering(tmp_path):
    runtime = _runtime(tmp_path, max_messages=1)
    runtime.ingest(_ws_receipt())
    runtime.ingest(_ws_receipt())
    manifest_path = runtime.session_dir / "manifests" / f"{runtime.source_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == MANIFEST_SCHEMA
    indexes = [item["chunk_index"] for item in manifest["chunks"]]
    assert indexes == sorted(indexes)
    for item in manifest["chunks"]:
        path = runtime.session_dir / item["path"]
        assert verify_chunk_sha256(path, item["sha256"])


def test_crash_leaves_incomplete_chunk(tmp_path):
    runtime = _runtime(tmp_path, max_messages=50)
    runtime.ingest(_ws_receipt())
    incomplete = runtime.store.close_incomplete(reason="SIMULATED_CRASH")
    assert incomplete is not None
    assert incomplete["status"] == "INCOMPLETE"
    partials = list((runtime.session_dir / "raw").glob("*/*.jsonl.partial"))
    assert partials
    notes = quarantine_leftover_partials(runtime.session_dir)
    assert notes
    assert notes[0]["status"] == "QUARANTINED"
    completed = list((runtime.session_dir / "raw").glob("*/*.jsonl"))
    assert completed == []
    created = create_session(
        repo=REPO,
        root=tmp_path,
        config=default_config(root_dir=str(tmp_path)),
    )
    assert created["session"]["session_id"] != runtime.session_id


def test_reconnect_creates_new_connection_and_records_gap(tmp_path):
    runtime = _runtime(tmp_path)
    first_conn = runtime.connection_id
    first = runtime.ingest(_ws_receipt())["envelope"]
    last_before = first["local_received_at_utc"]
    new_conn = runtime.reconnect(
        disconnect_utc="2026-09-19T00:00:00.000000000Z",
        reconnect_utc="2026-09-19T00:00:05.000000000Z",
    )
    assert new_conn != first_conn
    second = runtime.ingest(_ws_receipt())["envelope"]
    events = [
        json.loads(line)
        for line in runtime.events_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    types = [item["event_type"] for item in events]
    assert "DISCONNECT" in types
    assert "RECONNECT" in types
    assert "GAP" in types
    gap = next(item for item in events if item["event_type"] == "GAP")
    assert gap["labeled_as_original_point_in_time_receipt"] is False
    assert gap["filled_with_exchange_event_time"] is False
    assert gap["last_durable_receipt_before_disconnect"] == last_before
    assert gap["first_durable_receipt_after_reconnect"] == second["local_received_at_utc"]
    assert second["connection_id"] != first["connection_id"]


def test_backfill_cannot_masquerade_as_original_live_receipt(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.ingest_backfill(
        rest_response_body_bytes(
            OI_JSON,
            endpoint="https://example/openInterest",
            stream="GET /openInterest",
            http_status=200,
        )
    )
    envelope = result["envelope"]
    assert envelope["source_type"] == SOURCE_TYPE_BACKFILL
    assert envelope["original_live_receipt"] is False
    assert envelope["legal_available_at"] == envelope["local_received_at_utc"]
    with pytest.raises(CollectorError):
        runtime.ingest(_ws_receipt(), source_type="HISTORICAL_LIVE")


def test_utc_backward_jump_records_clock_anomaly(tmp_path):
    mono0 = monotonic_ns()
    stamps = [
        _make_stamp(1_000_000_000_000, mono0),
        _make_stamp(900_000_000_000, mono0 + 1_000),
    ]
    runtime = _runtime(tmp_path, stamp_fn=_stamp_seq(stamps))
    runtime.clock_watch = ClockWatch()
    runtime.ingest(_ws_receipt())
    runtime.ingest(_ws_receipt())
    events = [
        json.loads(line)
        for line in runtime.events_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    anomaly = next(item for item in events if item["event_type"] == "CLOCK_ANOMALY")
    assert anomaly["clock_anomaly_kind"] == "UTC_BACKWARD"
    assert anomaly["rewrote_receipt_timestamps"] is False
    assert anomaly["replaced_utc_with_exchange_time"] is False
    runtime.finalize()
    chunk = next((runtime.session_dir / "raw" / runtime.source_id).glob("chunk-*.jsonl"))
    envelopes = [json.loads(line) for line in chunk.read_text(encoding="utf-8").splitlines()]
    assert envelopes[0]["local_received_at_utc"] == format_utc_ns(1_000_000_000_000)
    assert envelopes[1]["local_received_at_utc"] == format_utc_ns(900_000_000_000)


def test_parser_failure_still_preserves_raw_evidence(tmp_path):
    def boom(_raw: bytes):
        raise ValueError("not json")

    runtime = _runtime(tmp_path, parser=boom)
    raw = b"this is not json {{{"
    receipt = websocket_application_payload_bytes(
        raw, endpoint="wss://x", stream="btcusdt@markPrice@1s"
    )
    result = runtime.ingest(receipt)
    envelope = result["envelope"]
    assert decode_raw_payload(envelope["raw_payload"]) == raw
    assert envelope["parse_error"]
    assert result["parsed"] is None
    assert envelope["source_observation_valid"] is False


# =============================================================================
# Response validity: HTTP error bodies / malformed payloads are never
# treated as market observations, even when their bytes happen to parse.
# =============================================================================


def _oi_runtime(tmp_path: Path) -> SourceRuntime:
    config = default_config(root_dir=str(tmp_path))
    created = create_session(repo=REPO, root=tmp_path, config=config)
    source = next(item for item in config["sources"] if "OPEN_INTEREST" in item["source_id"])
    return SourceRuntime(
        session_id=created["session"]["session_id"],
        session_dir=created["session_dir"],
        source=source,
        max_messages=100,
        max_bytes=1_000_000,
    )


def _premium_runtime(tmp_path: Path) -> SourceRuntime:
    config = default_config(root_dir=str(tmp_path))
    created = create_session(repo=REPO, root=tmp_path, config=config)
    source = next(item for item in config["sources"] if "PREMIUM_INDEX" in item["source_id"])
    return SourceRuntime(
        session_id=created["session"]["session_id"],
        session_dir=created["session_dir"],
        source=source,
        max_messages=100,
        max_bytes=1_000_000,
    )


def test_http_451_preserved_operationally_but_invalid(tmp_path):
    runtime = _oi_runtime(tmp_path)
    # A real restricted-location body: valid JSON, but not the OI schema.
    body = b'{"code":0,"msg":"Service unavailable from a restricted location"}'
    receipt = rest_response_body_bytes(
        body,
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=451,
    )
    result = runtime.ingest(receipt)
    envelope = result["envelope"]
    # Operational transport evidence is preserved exactly.
    assert decode_raw_payload(envelope["raw_payload"]) == body
    assert envelope["transport"]["http_status"] == 451
    # But it is never a valid market observation.
    assert envelope["source_observation_valid"] is False


def test_http_500_is_invalid(tmp_path):
    runtime = _oi_runtime(tmp_path)
    body = b'{"code":-1000,"msg":"An unknown error occurred"}'
    receipt = rest_response_body_bytes(
        body,
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=500,
    )
    result = runtime.ingest(receipt)
    assert result["envelope"]["transport"]["http_status"] == 500
    assert result["envelope"]["source_observation_valid"] is False


def test_http_200_with_malformed_schema_is_invalid(tmp_path):
    runtime = _oi_runtime(tmp_path)
    # HTTP 200 but not the openInterest schema (no "openInterest" key).
    body = b'{"symbol":"BTCUSDT","time":1589428639544}'
    receipt = rest_response_body_bytes(
        body,
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=200,
    )
    result = runtime.ingest(receipt)
    assert result["envelope"]["transport"]["http_status"] == 200
    assert result["envelope"]["source_observation_valid"] is False


def test_http_200_with_unparseable_json_is_invalid(tmp_path):
    runtime = _oi_runtime(tmp_path)
    body = b"not json at all {{{"
    receipt = rest_response_body_bytes(
        body,
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=200,
    )
    result = runtime.ingest(receipt)
    assert result["envelope"]["parse_error"] is not None
    assert result["envelope"]["source_observation_valid"] is False


def test_valid_premium_native_response_is_accepted(tmp_path):
    runtime = _premium_runtime(tmp_path)
    receipt = rest_response_body_bytes(
        PREMIUM_JSON,
        endpoint="https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
        stream="GET /fapi/v1/premiumIndex",
        http_status=200,
    )
    result = runtime.ingest(receipt)
    envelope = result["envelope"]
    assert envelope["transport"]["http_status"] == 200
    assert envelope["source_observation_valid"] is True
    assert result["parsed"]["native_fields"]["mark_price"] == "11793.63102583"


def test_valid_oi_native_response_is_accepted(tmp_path):
    runtime = _oi_runtime(tmp_path)
    receipt = rest_response_body_bytes(
        OI_JSON,
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=200,
    )
    result = runtime.ingest(receipt)
    envelope = result["envelope"]
    assert envelope["transport"]["http_status"] == 200
    assert envelope["source_observation_valid"] is True
    assert result["parsed"]["native_fields"]["open_interest"] == "23520.636"


def test_valid_mark_price_ws_payload_is_accepted(tmp_path):
    runtime = _runtime(tmp_path)
    result = runtime.ingest(_ws_receipt(MARK_JSON))
    envelope = result["envelope"]
    assert envelope["transport"]["transport"] == "websocket"
    assert envelope["source_observation_valid"] is True
    assert result["parsed"]["native_fields"]["funding_rate"] == "0.00030000"


def test_ws_connection_notice_is_not_a_valid_native_payload(tmp_path):
    runtime = _runtime(tmp_path)
    # A generic WS control/notice frame: valid JSON, not the markPrice schema.
    receipt = _ws_receipt(b'{"id":1,"result":null}')
    result = runtime.ingest(receipt)
    assert result["envelope"]["source_observation_valid"] is False


def test_invalid_observations_counted_in_health_not_scientific(tmp_path):
    runtime = _oi_runtime(tmp_path)
    receipt = rest_response_body_bytes(
        b'{"code":0,"msg":"restricted"}',
        endpoint="https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        stream="GET /fapi/v1/openInterest",
        http_status=451,
    )
    runtime.ingest(receipt)
    runtime.finalize()
    health = json.loads(
        (runtime.session_dir / "health" / f"{runtime.source_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert health["invalid_observation_count"] == 1
    assert_no_scientific_fields(health, where="health")


def test_no_scientific_fields_in_collector_schema():
    config = default_config()
    assert_no_scientific_fields(config, where="config")
    for field in FORBIDDEN_SCIENTIFIC_FIELDS:
        with pytest.raises(CollectorSchemaError):
            assert_no_scientific_fields({field: 1}, where="probe")
    for name in (
        "docs/research/MARKET_06.md",
        "docs/research/MARKET_06.json",
        "docs/research/M04_FWD.md",
        "docs/research/MARKET_04_FWD_PREREG.md",
    ):
        assert not (REPO / name).exists()


def test_session_metadata_binds_git_and_rejects_secrets(tmp_path):
    config = default_config(root_dir=str(tmp_path))
    created = create_session(repo=REPO, root=tmp_path, config=config)
    session = created["session"]
    assert session["collector_git_head"]
    assert session["collector_git_tree"]
    assert session["collector_config_sha256"]
    assert session["instrument"] == "BTCUSDT"
    assert session["hostname"]
    assert session["python_version"]
    assert session["market_06_created"] is False
    with pytest.raises(Exception):
        create_session(
            repo=REPO,
            root=tmp_path,
            config={**config, "api_token": "secret-value"},
        )


def test_independent_source_ids_are_not_merged():
    config = default_config()
    ids = [item["source_id"] for item in config["sources"]]
    assert len(ids) == len(set(ids))
    oi = next(item for item in config["sources"] if "OPEN_INTEREST" in item["source_id"])
    mark = next(item for item in config["sources"] if "MARK_PRICE" in item["source_id"])
    assert oi["separately_timestamped"] is True
    assert oi["must_not_merge_clock_with"] == mark["source_id"]


def test_duplicates_kept_in_raw_marked_in_parsed(tmp_path):
    runtime = _runtime(tmp_path)
    first = runtime.ingest(_ws_receipt())
    second = runtime.ingest(_ws_receipt())
    assert first["duplicate_candidate"] is False
    assert second["duplicate_candidate"] is True
    runtime.finalize()
    chunk = next((runtime.session_dir / "raw" / runtime.source_id).glob("chunk-*.jsonl"))
    lines = [line for line in chunk.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 2


def test_fetch_rest_body_uses_exact_bytes_before_json(monkeypatch):
    class _Resp:
        status = 200
        headers = {"Content-Encoding": "identity"}

        def read(self):
            return PREMIUM_JSON

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    receipt = fetch_rest_body(
        "https://example/premiumIndex",
        stream="GET /premiumIndex",
        opener=lambda *a, **k: _Resp(),
    )
    assert receipt.raw_payload == PREMIUM_JSON
    parsed = json.loads(receipt.raw_payload.decode("utf-8"))
    assert parsed["symbol"] == "BTCUSDT"


def test_cli_collect_refuses_authoritative_start():
    from scripts.research.forward_market_observability_v1.cli import main

    assert main(["collect"]) == 2


def test_implementation_freeze_binds_collector_sha_set():
    """The ORIGINAL freeze is historical evidence of the pre-repair bytes.

    It intentionally no longer matches the live tree: the lifecycle repair
    changed several files and added two new authority modules. It is
    explicitly marked superseded; live-tree consistency is asserted
    against the NEW refreeze instead, in
    test_forward_market_observability_v1_collection_arm.py.
    """
    from scripts.research.forward_market_observability_v1.identity import FREEZE_JSON

    freeze = json.loads((REPO / FREEZE_JSON).read_text(encoding="utf-8"))
    assert freeze["raw_envelope_schema"] == RAW_ENVELOPE_SCHEMA
    assert freeze["chunk_schema"] == CHUNK_SCHEMA
    assert freeze["manifest_schema"] == MANIFEST_SCHEMA
    assert freeze["authoritative_collection_started"] is False
    assert freeze["authoritative_collection_start_utc"] is None
    assert freeze["market_06_created"] is False
    assert freeze["m04_fwd_created"] is False
    assert freeze["computes_scientific_outcomes"] is False
    assert freeze["smoke_data_scientifically_excluded"] is True
    assert freeze["legal_available_at_rule"] == "local_received_at_utc"
    assert freeze["is_current_authority"] is False
    assert freeze["superseded_by"] == (
        "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_REFREEZE.json"
    )

