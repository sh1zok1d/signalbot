"""Digest binding to the frozen COMPILER_V3_VARIANCE_FLOOR_VALIDATION artifacts.

Every simulation entry point calls `verify_freeze()` first and refuses to work
on any mismatch. Nothing here reads market data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FREEZE_RECORD = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_FREEZE_RECORD.json"
EXECUTION_BINDING = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_EXECUTION_BINDING_V1.json"
MANIFEST = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json"
SPEC = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md"
GENERATOR_FILES = (
    "scripts/research/compiler_v3_variance_floor/freeze.py",
    "scripts/research/compiler_v3_variance_floor/cp.py",
    "scripts/research/compiler_v3_variance_floor/compiler.py",
    "scripts/research/compiler_v3_variance_floor/generator.py",
    "scripts/research/compiler_v3_variance_floor/engine.py",
)


class FreezeMismatch(RuntimeError):
    pass


def sha256_path(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_freeze() -> dict:
    """Return the freeze record after checking every artifact digest; raise on mismatch."""
    record = json.loads(FREEZE_RECORD.read_text())
    bad = {rel: (want, sha256_path(rel)) for rel, want in record["ARTIFACTS"].items() if sha256_path(rel) != want}
    if bad:
        raise FreezeMismatch(f"frozen artifact digest mismatch: {bad}")
    return record


def generator_digests() -> dict:
    return {rel: sha256_path(rel) for rel in GENERATOR_FILES}


def verify_execution_binding() -> dict:
    """The binding that must exist, and match, before any official run."""
    if not EXECUTION_BINDING.exists():
        raise FreezeMismatch("execution binding record is absent")
    binding = json.loads(EXECUTION_BINDING.read_text())
    bad = {rel: (want, sha256_path(rel)) for rel, want in binding["GENERATOR_DIGESTS"].items() if sha256_path(rel) != want}
    if bad:
        raise FreezeMismatch(f"generator digest mismatch against the execution binding: {bad}")
    if set(binding["GENERATOR_DIGESTS"]) != set(GENERATOR_FILES):
        raise FreezeMismatch("execution binding does not list exactly the generator files")
    return binding


def load_manifest() -> dict:
    verify_freeze()
    return json.loads(MANIFEST.read_text())
