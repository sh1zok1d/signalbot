"""Operational CLI.

Lifecycle:

    smoke      always infrastructure-only, scientifically excluded
    readiness  infrastructure-only native-payload proof, scientifically
               excluded; never grants authorization by itself
    collect    authenticate frozen source -> authenticate collection ARM
               -> verify environment -> verify source readiness ->
               start a NEW authoritative session

Before a valid collection ARM exists, "collect" refuses. After one exists,
the exact same source bytes allow collection -- no source edit is
permitted between ARM creation and collection start.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from scripts.research.forward_market_observability_v1.collector import SourceRuntime
from scripts.research.forward_market_observability_v1.session import (
    INFRASTRUCTURE_READINESS_CHECK_ONLY,
    INFRASTRUCTURE_SMOKE_TEST_ONLY,
    create_session,
)
from scripts.research.forward_market_observability_v1.sources import default_config
from scripts.research.forward_market_observability_v1.transport import (
    fetch_rest_body,
    websocket_application_payload_bytes,
)

REPO = Path(__file__).resolve().parents[3]

AUTHORITATIVE_LABEL = "FORWARD_MARKET_OBSERVABILITY_V1_AUTHORITATIVE_COLLECTION"


def _refuse_authoritative(reason: str) -> int:
    print(
        f"AUTHORITATIVE_COLLECTION_NOT_STARTED:{reason}",
        file=sys.stderr,
    )
    return 2


def _connect_ws(endpoint: str):
    try:
        import websockets.sync.client as ws_client
    except Exception as exc:  # pragma: no cover — exercised when websockets missing
        print(f"WEBSOCKET_LIBRARY_UNAVAILABLE:{exc}", file=sys.stderr)
        return None
    try:
        return ws_client.connect(endpoint, open_timeout=10, close_timeout=5)
    except Exception as exc:
        print(f"WEBSOCKET_CONNECT_FAILED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return None


def _poll_sources(
    *,
    config: dict[str, Any],
    sources: dict[str, SourceRuntime],
    duration_seconds: float,
    stop_on_all_valid: bool,
) -> dict[str, bool]:
    """Shared REST+WS polling loop. Tracks per-source observation validity.

    Used by both ``readiness`` (infrastructure-only, stops early once every
    required source has produced one valid native observation) and
    ``collect`` (authoritative, runs for the full configured duration
    regardless of early validity).
    """
    rest_sources = [item for item in config["sources"] if item["transport"] == "rest"]
    ws_source = next(item for item in config["sources"] if item["transport"] == "websocket")
    valid_seen: dict[str, bool] = {item["source_id"]: False for item in config["sources"]}
    deadline = time.time() + float(duration_seconds)
    ws = _connect_ws(ws_source["endpoint"])
    last_rest_poll: dict[str, float] = {}
    try:
        while time.time() < deadline:
            if ws is not None:
                try:
                    message = ws.recv(timeout=1.0)
                    receipt = websocket_application_payload_bytes(
                        message,
                        endpoint=ws_source["endpoint"],
                        stream=ws_source["stream"],
                    )
                    result = sources[ws_source["source_id"]].ingest(receipt)
                    if result["envelope"]["source_observation_valid"]:
                        valid_seen[ws_source["source_id"]] = True
                except Exception as exc:
                    print(f"WS_RECV:{type(exc).__name__}:{exc}", file=sys.stderr)
            now = time.time()
            for item in rest_sources:
                interval = float(item.get("poll_interval_seconds", 5))
                if now - last_rest_poll.get(item["source_id"], -1e9) < interval:
                    continue
                last_rest_poll[item["source_id"]] = now
                try:
                    receipt = fetch_rest_body(item["endpoint"], stream=item["stream"], timeout=5)
                    result = sources[item["source_id"]].ingest(receipt)
                    if result["envelope"]["source_observation_valid"]:
                        valid_seen[item["source_id"]] = True
                except Exception as exc:
                    print(f"REST:{item['source_id']}:{type(exc).__name__}:{exc}", file=sys.stderr)
            if stop_on_all_valid and all(valid_seen.values()):
                break
            time.sleep(0.2)
    finally:
        if ws is not None:
            ws.close()
    return valid_seen


def cmd_smoke(args: argparse.Namespace) -> int:
    config = default_config(root_dir=args.root)
    created = create_session(
        repo=REPO,
        root=Path(args.root),
        config=config,
        infrastructure_label=INFRASTRUCTURE_SMOKE_TEST_ONLY,
    )
    session = created["session"]
    session_dir: Path = created["session_dir"]
    sources = {
        item["source_id"]: SourceRuntime(
            session_id=session["session_id"],
            session_dir=session_dir,
            source=item,
            max_messages=int(args.chunk_messages),
            max_bytes=65536,
        )
        for item in config["sources"]
    }
    valid_seen = _poll_sources(
        config=config, sources=sources, duration_seconds=args.duration_seconds,
        stop_on_all_valid=False,
    )
    received = sum(runtime.message_count for runtime in sources.values())
    for runtime in sources.values():
        runtime.finalize(reason="SMOKE_STOP")
    summary = {
        "infrastructure_label": INFRASTRUCTURE_SMOKE_TEST_ONLY,
        "scientific_evidence": False,
        "smoke_data_scientifically_excluded": True,
        "session_id": session["session_id"],
        "session_dir": str(session_dir),
        "messages_ingested": received,
        "any_valid_observation_seen": valid_seen,
        "authoritative_collection": False,
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    (session_dir / "SMOKE.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if received > 0 else 1


def cmd_readiness(args: argparse.Namespace) -> int:
    """Infrastructure-only. Proves (or refutes) real native payloads.

    Never grants authorization by itself and is never authoritative
    evidence, regardless of outcome.
    """
    config = default_config(root_dir=args.root)
    created = create_session(
        repo=REPO,
        root=Path(args.root),
        config=config,
        infrastructure_label=INFRASTRUCTURE_READINESS_CHECK_ONLY,
    )
    session = created["session"]
    session_dir: Path = created["session_dir"]
    sources = {
        item["source_id"]: SourceRuntime(
            session_id=session["session_id"],
            session_dir=session_dir,
            source=item,
            max_messages=int(args.chunk_messages),
            max_bytes=65536,
        )
        for item in config["sources"]
    }
    valid_seen = _poll_sources(
        config=config, sources=sources, duration_seconds=args.duration_seconds,
        stop_on_all_valid=True,
    )
    for runtime in sources.values():
        runtime.finalize(reason="READINESS_STOP")

    from scripts.research.forward_market_observability_v1.sources import (
        SOURCE_MARK_PRICE_WS,
        SOURCE_OPEN_INTEREST_REST,
        SOURCE_PREMIUM_INDEX_REST,
    )

    report = {
        "infrastructure_label": INFRASTRUCTURE_READINESS_CHECK_ONLY,
        "scientific_evidence": False,
        "readiness_data_scientifically_excluded": True,
        "session_id": session["session_id"],
        "session_dir": str(session_dir),
        "MARK_PRICE_WS_NATIVE_READY": bool(valid_seen.get(SOURCE_MARK_PRICE_WS, False)),
        "PREMIUM_INDEX_NATIVE_READY": bool(valid_seen.get(SOURCE_PREMIUM_INDEX_REST, False)),
        "OPEN_INTEREST_NATIVE_READY": bool(valid_seen.get(SOURCE_OPEN_INTEREST_REST, False)),
        "all_frozen_sources_ready": all(valid_seen.values()),
        "authoritative_collection": False,
    }
    print(json.dumps(report, sort_keys=True, indent=2))
    (session_dir / "READINESS.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if report["all_frozen_sources_ready"] else 1


def cmd_collect(args: argparse.Namespace) -> int:
    from scripts.research.forward_market_observability_v1.collection_authority import (
        CollectionAuthorityError,
        CollectionNotAuthorized,
        authenticate_collection_arm,
    )

    try:
        bound = authenticate_collection_arm()
    except (CollectionNotAuthorized, CollectionAuthorityError) as exc:
        return _refuse_authoritative(str(exc))
    except Exception as exc:  # noqa: BLE001 — any other failure also refuses
        return _refuse_authoritative(f"{type(exc).__name__}:{exc}")

    try:
        import websockets  # noqa: F401
    except Exception as exc:
        return _refuse_authoritative(f"ENVIRONMENT_WEBSOCKETS_UNAVAILABLE:{exc}")

    config = default_config(root_dir=args.root)
    probe_created = create_session(
        repo=REPO,
        root=Path(args.root),
        config=config,
        infrastructure_label=INFRASTRUCTURE_READINESS_CHECK_ONLY,
    )
    probe_dir: Path = probe_created["session_dir"]
    probe_sources = {
        item["source_id"]: SourceRuntime(
            session_id=probe_created["session"]["session_id"],
            session_dir=probe_dir,
            source=item,
            max_messages=int(args.chunk_messages),
            max_bytes=65536,
        )
        for item in config["sources"]
    }
    ready = _poll_sources(
        config=config,
        sources=probe_sources,
        duration_seconds=args.readiness_duration_seconds,
        stop_on_all_valid=True,
    )
    for runtime in probe_sources.values():
        runtime.finalize(reason="PRE_COLLECT_READINESS_STOP")
    if not all(ready.values()):
        return _refuse_authoritative(
            "FORWARD_OBSERVABILITY_SOURCE_NOT_READY:" + json.dumps(ready, sort_keys=True)
        )

    created = create_session(
        repo=REPO,
        root=Path(args.root),
        config=config,
        infrastructure_label=AUTHORITATIVE_LABEL,
        authoritative_collection=True,
        collection_authority={
            "collection_run_identity": bound["collection_run_identity"],
            "arm_sha256": bound["sha256"],
        },
    )
    session = created["session"]
    session_dir: Path = created["session_dir"]
    sources = {
        item["source_id"]: SourceRuntime(
            session_id=session["session_id"],
            session_dir=session_dir,
            source=item,
            max_messages=int(args.chunk_messages),
            max_bytes=int(args.chunk_bytes),
        )
        for item in config["sources"]
    }
    valid_seen = _poll_sources(
        config=config,
        sources=sources,
        duration_seconds=args.duration_seconds,
        stop_on_all_valid=False,
    )
    for runtime in sources.values():
        runtime.finalize(reason="COLLECT_STOP")

    summary = {
        "infrastructure_label": AUTHORITATIVE_LABEL,
        "scientific_evidence": False,
        "authoritative_collection": True,
        "collector_source_head": bound["payload"]["collector_source_head"],
        "collector_source_tree": bound["payload"]["collector_source_tree"],
        "collection_run_identity": bound["collection_run_identity"],
        "collection_arm_sha256": bound["sha256"],
        "session_id": session["session_id"],
        "session_dir": str(session_dir),
        "process_start_utc": session["process_start_utc"],
        "process_start_monotonic_ns": session["process_start_monotonic_ns"],
        "any_valid_observation_seen": valid_seen,
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    (session_dir / "COLLECTION_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forward_market_observability_v1",
        description="Acquisition infrastructure. Not a scientific experiment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="INFRASTRUCTURE_SMOKE_TEST_ONLY live/synthetic proof")
    smoke.add_argument("--duration-seconds", type=float, default=8.0)
    smoke.add_argument("--root", default="artifacts/forward_market_observability_v1")
    smoke.add_argument("--chunk-messages", type=int, default=20)
    smoke.set_defaults(func=cmd_smoke)

    readiness = sub.add_parser(
        "readiness", help="INFRASTRUCTURE_READINESS_CHECK_ONLY native-payload proof"
    )
    readiness.add_argument("--duration-seconds", type=float, default=20.0)
    readiness.add_argument("--root", default="artifacts/forward_market_observability_v1")
    readiness.add_argument("--chunk-messages", type=int, default=20)
    readiness.set_defaults(func=cmd_readiness)

    collect = sub.add_parser(
        "collect", help="Authoritative collection (requires a valid collection ARM)"
    )
    collect.add_argument("--duration-seconds", type=float, default=86400.0)
    collect.add_argument("--readiness-duration-seconds", type=float, default=20.0)
    collect.add_argument("--root", default="artifacts/forward_market_observability_v1")
    collect.add_argument("--chunk-messages", type=int, default=100)
    collect.add_argument("--chunk-bytes", type=int, default=1_048_576)
    collect.set_defaults(func=cmd_collect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
