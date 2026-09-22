"""Restore gitignored D13 raw zips from the frozen object ledger.

Refuses 2025/2026. Does not parse closes or compute returns.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d13_acquire as ACQ
from scripts.research.discovery_sprint_04 import d13_panel as P


def restore(*, repo: Path | None = None) -> dict[str, int]:
    base = repo or C.repo_root()
    docs = base / C.D13_DOCS_REL
    raw_root = base / C.D13_RAW_REL
    ledger = json.loads((docs / "object_ledger.json").read_text(encoding="utf-8"))
    downloaded = 0
    skipped = 0
    for obj in ledger["objects"]:
        key = obj["key"]
        ACQ.refuse_protected_key(key)
        dest = raw_root / key
        if dest.is_file() and C.sha256_file(dest) == obj["expected_sha256"]:
            skipped += 1
            continue
        meta = ACQ.download_object(key, dest)
        if meta["sha256"] != obj["expected_sha256"]:
            raise C.SnapshotIdentityError(f"RESTORE_SHA_MISMATCH:{key}")
        downloaded += 1
    verified = P.verify_local_bytes_against_ledger(repo=base)
    return {
        "downloaded": downloaded,
        "already_present": skipped,
        "verified": int(verified["VERIFIED_N"]),
    }


def main() -> None:
    result = restore()
    print(result)


if __name__ == "__main__":
    main()
