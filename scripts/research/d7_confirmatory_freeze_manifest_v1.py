"""Write the D7 confirmatory freeze manifest.

The manifest hashes the covered files. It does not hash its own output
and it does not record a git commit.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.research.self_referential_contrast_v1.confirmatory_contract import (
    PROFILE_VERSION,
    canonical_json,
)
from scripts.research.self_referential_contrast_v1.constants import PROFILE_ID

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json")
COVERED = (
    "docs/research/D7_CONFIRMATORY_ADAPTER_V1.json",
    "docs/research/D7_CONFIRMATORY_NUMPY_PIN_V1.json",
    "docs/research/D7_DIRECTIONAL_CONFIRMATION_DECISION_RULE_V1.json",
    "docs/research/D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1.json",
    "docs/research/D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1.md",
    "scripts/research/d7_confirmatory_freeze_manifest_v1.py",
    "scripts/research/self_referential_contrast_v1/__init__.py",
    "scripts/research/self_referential_contrast_v1/bartlett.py",
    "scripts/research/self_referential_contrast_v1/benchmark.py",
    "scripts/research/self_referential_contrast_v1/confirmatory_contract.py",
    "scripts/research/self_referential_contrast_v1/constants.py",
    "scripts/research/self_referential_contrast_v1/contrast.py",
    "scripts/research/self_referential_contrast_v1/dgp.py",
    "scripts/research/self_referential_contrast_v1/env_limits.py",
    "scripts/research/self_referential_contrast_v1/multipliers.py",
    "scripts/research/self_referential_contrast_v1/runner.py",
    "scripts/research/self_referential_contrast_v1/seeds.py",
    "scripts/research/self_referential_contrast_v1/validation_protocol.py",
)


def manifest_document() -> dict[str, object]:
    files = []
    for relative in COVERED:
        payload = (ROOT / relative).read_bytes()
        files.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    if any(item["path"] == OUTPUT.as_posix() for item in files):
        raise RuntimeError("freeze manifest must not hash itself")
    return {
        "document": "D7_CONFIRMATORY_FREEZE_MANIFEST_V1",
        "files": files,
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
    }


def main() -> None:
    text = canonical_json(manifest_document())
    (ROOT / OUTPUT).write_bytes(text.encode("utf-8"))


if __name__ == "__main__":
    main()
