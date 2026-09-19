"""Operational CLI. Refuses authoritative collection until a later unit."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from scripts.research.forward_market_observability_v1.collector import SourceRuntime
from scripts.research.forward_market_observability_v1.session import create_session
from scripts.research.forward_market_observability_v1.sources import default_config
from scripts.research.forward_market_observability_v1.transport import (
    fetch_rest_body,
    websocket_application_payload_bytes,
)

REPO = Path(__file__).resolve().parents[3]


def _refuse_authoritative() -> int:
    print(
        "AUTHORITATIVE_COLLECTION_NOT_STARTED: "
        "this unit freezes implementation only. Next unit is "
        "FORWARD_MARKET_OBSERVABILITY_V1_AUTHORITATIVE_COLLECTION_START.",
        file=sys.stderr,
    )
    return 2


def cmd_smoke(args: argparse.Namespace) -> int:
    config = default_config(root_dir=args.root)
    created = create_session(
        repo=REPO,
        root=Path(args.root),
        config=config,
        infrastructure_label="INFRASTRUCTURE_SMOKE_TEST_ONLY",
    )
    session = created["session"]
    session_dir: Path = created["session_dir"]
    sources = {item["source_id"]: SourceRuntime(
        session_id=session["session_id"],
        session_dir=session_dir,
        source=item,
        max_messages=int(args.chunk_messages),
        max_bytes=65536,
    ) for item in config["sources"]}
    deadline = time.time() + float(args.duration_seconds)
    rest_sources = [
        item for item in config["sources"] if item["transport"] == "rest"
    ]
    ws_source = next(item for item in config["sources"] if item["transport"] == "websocket")
    received = 0
    try:
        import websockets.sync.client as ws_client
    except Exception as exc:  # pragma: no cover — exercised when websockets missing
        print(f"SMOKE_WEBSOCKET_UNAVAILABLE:{exc}", file=sys.stderr)
        ws_client = None
    ws = None
    if ws_client is not None:
        try:
            ws = ws_client.connect(ws_source["endpoint"], open_timeout=10, close_timeout=5)
        except Exception as exc:
            print(f"SMOKE_WEBSOCKET_CONNECT_FAILED:{exc}", file=sys.stderr)
            ws = None
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
                    sources[ws_source["source_id"]].ingest(receipt)
                    received += 1
                except Exception as exc:
                    print(f"SMOKE_WS_RECV:{type(exc).__name__}:{exc}", file=sys.stderr)
            for item in rest_sources:
                try:
                    receipt = fetch_rest_body(item["endpoint"], stream=item["stream"], timeout=5)
                    sources[item["source_id"]].ingest(receipt)
                    received += 1
                except Exception as exc:
                    print(f"SMOKE_REST:{item['source_id']}:{type(exc).__name__}:{exc}", file=sys.stderr)
            time.sleep(0.2)
    finally:
        if ws is not None:
            ws.close()
        for runtime in sources.values():
            runtime.finalize(reason="SMOKE_STOP")
    summary = {
        "infrastructure_label": "INFRASTRUCTURE_SMOKE_TEST_ONLY",
        "scientific_evidence": False,
        "smoke_data_scientifically_excluded": True,
        "session_id": session["session_id"],
        "session_dir": str(session_dir),
        "messages_ingested": received,
        "authoritative_collection": False,
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    (session_dir / "SMOKE.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if received > 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forward_market_observability_v1",
        description="Acquisition infrastructure. Not a scientific experiment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="INFRASTRUCTURE_SMOKE_TEST_ONLY live/synthetic proof")
    smoke.add_argument("--duration-seconds", type=float, default=8.0)
    smoke.add_argument(
        "--root",
        default="artifacts/forward_market_observability_v1",
    )
    smoke.add_argument("--chunk-messages", type=int, default=20)
    smoke.set_defaults(func=cmd_smoke)
    collect = sub.add_parser("collect", help="Authoritative collection (refused in this unit)")
    collect.set_defaults(func=lambda _args: _refuse_authoritative())
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
