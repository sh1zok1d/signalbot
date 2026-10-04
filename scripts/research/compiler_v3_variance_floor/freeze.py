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
EXECUTION_BINDING_V1 = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_EXECUTION_BINDING_V1.json"  # immutable, as committed in e5dd620
EXECUTION_BINDING = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_EXECUTION_BINDING_V2.json"  # current, immutable
RUN_AUTHORIZATION = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_RUN_AUTHORIZATION_V1.json"  # does not exist yet
AMENDMENT = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_FREEZE_AMENDMENT_V1.json"
EFFECTIVE_MANIFEST = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_EFFECTIVE_MANIFEST_V1.json"
ORIGINAL_FREEZE_COMMIT = "62f1a74"
MANIFEST = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json"
SPEC = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md"
GENERATOR_FILES = (
    "scripts/research/compiler_v3_variance_floor/freeze.py",
    "scripts/research/compiler_v3_variance_floor/cp.py",
    "scripts/research/compiler_v3_variance_floor/compiler.py",
    "scripts/research/compiler_v3_variance_floor/generator.py",
    "scripts/research/compiler_v3_variance_floor/engine.py",
    "scripts/research/compiler_v3_variance_floor/amendment.py",
    "scripts/research/compiler_v3_variance_floor/binding.py",
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
    """The current binding (V2) must exist and match; V1 must be byte-identical to its recorded digest."""
    if not EXECUTION_BINDING.exists():
        raise FreezeMismatch("execution binding record is absent")
    binding = json.loads(EXECUTION_BINDING.read_text())
    v1 = binding.get("SUPERSEDES") or {}
    if sha256_path(v1.get("PATH", "")) != v1.get("SHA256"):
        raise FreezeMismatch("execution binding V1 differs from the digest recorded in V2")
    bad = {rel: (want, sha256_path(rel)) for rel, want in binding["GENERATOR_DIGESTS"].items() if sha256_path(rel) != want}
    if bad:
        raise FreezeMismatch(f"generator digest mismatch against the execution binding: {bad}")
    if set(binding["GENERATOR_DIGESTS"]) != set(GENERATOR_FILES):
        raise FreezeMismatch("execution binding does not list exactly the generator files")
    return binding


def verify_run_authorization(binding: dict) -> dict:
    """A separate immutable artifact authorizes the one official run; it does not exist yet."""
    if not RUN_AUTHORIZATION.exists():
        raise FreezeMismatch("run authorization artifact is absent: the official run is not authorized")
    auth = json.loads(RUN_AUTHORIZATION.read_text())
    want = hashlib.sha256(EXECUTION_BINDING.read_bytes()).hexdigest()
    if auth.get("BINDING_SHA256") != want or auth.get("OFFICIAL_RUN_AUTHORIZED") is not True:
        raise FreezeMismatch("run authorization does not bind the current execution binding")
    return auth


def load_manifest() -> dict:
    verify_freeze()
    return json.loads(MANIFEST.read_text())


def verify_amendment() -> dict:
    """The pre-run freeze amendment must reference the original freeze digests exactly and
    the effective manifest must match the digest it records."""
    record = verify_freeze()
    if not AMENDMENT.exists():
        raise FreezeMismatch("freeze amendment is absent")
    amendment = json.loads(AMENDMENT.read_text())
    if amendment["ORIGINAL_FREEZE"]["COMMIT"] != ORIGINAL_FREEZE_COMMIT or amendment["ORIGINAL_FREEZE"]["ARTIFACTS"] != record["ARTIFACTS"]:
        raise FreezeMismatch("amendment does not bind the original freeze")
    eff_rel = str(EFFECTIVE_MANIFEST.relative_to(REPO))
    if sha256_path(eff_rel) != amendment["EFFECTIVE_MANIFEST_SHA256"]:
        raise FreezeMismatch("effective manifest digest differs from the amendment")
    return amendment


def load_effective_manifest() -> dict:
    verify_amendment()
    return json.loads(EFFECTIVE_MANIFEST.read_text())
