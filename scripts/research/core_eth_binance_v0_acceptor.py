#!/usr/bin/env python3
"""Outcome-blind CORE_ETH_BINANCE_V0 companion acceptor CLI.

Acquires frozen Vision ETHUSDT 1m objects, verifies inventory checksums,
audits timestamp/schema coverage, and writes snapshot identity. Does not
compute MARKET-05 scientific outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.research.core_eth_binance_v0_acceptor_lib import (
    DATASET_ID,
    MANIFEST_REL,
    CoreEthBinanceV0AcceptorError,
    accept_core_eth,
    canonical_json_bytes,
    manifest_yaml,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = Path("artifacts/research_data") / DATASET_ID / "raw"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Accept CORE_ETH_BINANCE_V0 outcome-blind companion identity"
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = accept_core_eth(raw_root=args.raw_root, repo_root=_REPO_ROOT)
    except CoreEthBinanceV0AcceptorError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    snap_id = result["snapshot_id"]
    payload = result["identity_payload"]
    print(json.dumps({"dataset_id": DATASET_ID, "snapshot_id": snap_id, "accepted": True}))
    if args.write_docs:
        snap_dir = _REPO_ROOT / "docs/research_data" / DATASET_ID
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"SNAPSHOT_{snap_id[:8]}.json"
        snap_path.write_bytes(canonical_json_bytes(payload))
        manifest_path = _REPO_ROOT / MANIFEST_REL
        manifest_path.write_text(manifest_yaml(snap_id, payload), encoding="utf-8")
        readme = snap_dir / "README.md"
        readme.write_text(
            "# CORE_ETH_BINANCE_V0 accepted companion identity\n\n"
            f"**Status:** `ACCEPTED_FOR_DISCOVERY`\n\n"
            f"**Snapshot:** `{snap_id}`\n\n"
            "Companion identity for `CORE_BTC_BINANCE_V0`. Same venue, "
            "instrument class, frozen range, and bar-end-exclusive "
            "availability. Does not redefine CORE BTC. Not a MARKET-05 "
            "RESULT. Scientific outcomes were not inspected. Protected "
            "2025/2026 OHLC values were not scientifically evaluated.\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
