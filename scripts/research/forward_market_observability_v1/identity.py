"""Collector implementation identity. Hashes are provenance, not science."""

from __future__ import annotations

import hashlib
from pathlib import Path

COLLECTOR_IMPLEMENTATION_RELPATHS: tuple[str, ...] = (
    "scripts/research/forward_market_observability_v1/__init__.py",
    "scripts/research/forward_market_observability_v1/__main__.py",
    "scripts/research/forward_market_observability_v1/cli.py",
    "scripts/research/forward_market_observability_v1/clock.py",
    "scripts/research/forward_market_observability_v1/collector.py",
    "scripts/research/forward_market_observability_v1/envelope.py",
    "scripts/research/forward_market_observability_v1/health.py",
    "scripts/research/forward_market_observability_v1/identity.py",
    "scripts/research/forward_market_observability_v1/parse.py",
    "scripts/research/forward_market_observability_v1/schemas.py",
    "scripts/research/forward_market_observability_v1/session.py",
    "scripts/research/forward_market_observability_v1/sources.py",
    "scripts/research/forward_market_observability_v1/storage.py",
    "scripts/research/forward_market_observability_v1/transport.py",
    "scripts/research/forward_market_observability_v1/collection_authority.py",
    "scripts/research/forward_market_observability_v1/authority_root.py",
    "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_CONFIG.json",
    "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_SCHEMAS.json",
    "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_CONTRACT.json",
)

FREEZE_JSON = "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collector_implementation_sha_set(repo: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for rel in COLLECTOR_IMPLEMENTATION_RELPATHS:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        mapping[rel] = sha256_file(path)
    return mapping
