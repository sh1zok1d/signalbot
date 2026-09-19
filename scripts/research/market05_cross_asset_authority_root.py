"""MARKET-05 independent authority root of trust.

Closes the self-attestation gap: ``market05_cross_asset_arm_authority.py``
cannot authenticate its own bytes, so a mutation of the ARM authority could
otherwise weaken every downstream check without changing RUN_IDENTITY.

The root of trust is **git object identity**, not a constant that a module
asserts about itself:

* This module pins the git **blob id** of every authority/scientific file,
  including ``market05_cross_asset_arm_authority.py``. A blob id is
  ``sha1("blob <len>\\0" + bytes)`` -- content-addressed, computable before
  any commit exists, and independent of commit history.
* This module does **not** pin its own blob id. Its integrity is
  established from the other direction: the frozen scientific
  implementation commit/tree recorded in
  ``MARKET_05_IMPLEMENTATION_REFREEZE.json`` must contain this file with
  exactly the bytes being executed.

That is a cross-binding, not a circle:

    code (here)  pins  -> blob ids of the other authority files
    docs (refreeze)     -> pins the commit/tree that contains THIS file

Neither artifact alone can authorize. Mutating this module is caught by
the git tree comparison; mutating the ARM authority is caught by the
pinned blob id here; rewriting the docs to name a different tree fails
because that tree must still carry the pinned blob ids.

This module loads no scientific data, evaluates nothing, and decides no
scientific question.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


AUTHORITY_ROOT_REL = "scripts/research/market05_cross_asset_authority_root.py"
ARM_AUTHORITY_REL = "scripts/research/market05_cross_asset_arm_authority.py"
REFREEZE_JSON_REL = "docs/research/MARKET_05_IMPLEMENTATION_REFREEZE.json"

# The frozen SCIENTIFIC implementation commit. This is the commit that
# carries the scientific + authority source. Later documentation-only
# authority commits (which record provenance) are NOT this value and must
# never be presented as the scientific implementation commit.
#
# Resolved from the re-freeze artifact at runtime and cross-checked against
# the blob ids below, so this module never has to hardcode a commit SHA it
# could not know while being written.
SCIENTIFIC_IMPLEMENTATION_HEAD_KEY = "scientific_implementation_head"
SCIENTIFIC_IMPLEMENTATION_TREE_KEY = "scientific_implementation_tree"

# git blob ids (sha1 of the git blob object) of every file that can
# materially change authorization or scientific results.
FROZEN_BLOB_IDS: dict[str, str] = {
    "scripts/research/market05_cross_asset_lib.py": (
        "331a5e884bf4ccd99514af7961cb0c102cfa330f"
    ),
    "scripts/research/market05_cross_asset_authority.py": (
        "aa39e8f5685f93b20bf2c487cd8b3ac1db42722c"
    ),
    "scripts/research/market05_cross_asset_arm_authority.py": (
        "93adc219238b3151276329a8ed192999baf1bd20"
    ),
    "scripts/research/market05_cross_asset.py": (
        "cd3f82b9fff37f431bac815cd6f7e7fd566dc6fd"
    ),
    "scripts/research/market05_cross_asset_data.py": (
        "37b2c462ac4b089577ca706960cb404892e4c594"
    ),
    "scripts/research/market05_cross_asset_canonical_execution.py": (
        "3b940a9747a843af74a0c4d5ff3769e1b587b54d"
    ),
    "scripts/research/core_eth_binance_v0_acceptor_lib.py": (
        "ff5631dcf51d40f1597c8a21903ed168f8fd610f"
    ),
}


class Market05AuthorityRootError(RuntimeError):
    """The executing authority bytes are not the frozen authority bytes."""


def git_blob_id(data: bytes) -> str:
    """Compute a git blob id from content alone (no repository needed)."""
    header = f"blob {len(data)}".encode("utf-8") + b"\x00"
    return hashlib.sha1(header + data).hexdigest()


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _git(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argv],
        cwd=str(_repo_root()),
        capture_output=True,
        check=False,
    )


def verify_frozen_blob_ids() -> dict[str, str]:
    """Every pinned file's on-disk bytes must hash to the pinned blob id.

    This alone refuses a post-freeze mutation of the ARM authority module,
    with no repository or commit required.
    """
    seen: dict[str, str] = {}
    for rel, expected in sorted(FROZEN_BLOB_IDS.items()):
        path = _path(rel)
        if path.is_symlink():
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_SYMLINK_REFUSED:{rel}"
            )
        if not path.is_file():
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_FILE_MISSING:{rel}"
            )
        actual = git_blob_id(path.read_bytes())
        if actual != expected:
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_BLOB_MISMATCH:{rel}"
            )
        seen[rel] = actual
    return seen


def load_frozen_provenance() -> dict[str, str]:
    """Read the frozen scientific commit/tree from the re-freeze artifact."""
    path = _path(REFREEZE_JSON_REL)
    if path.is_symlink():
        raise Market05AuthorityRootError(
            "MARKET_05_AUTHORITY_ROOT_SYMLINK_REFUSED:refreeze"
        )
    if not path.is_file():
        raise Market05AuthorityRootError("MARKET_05_AUTHORITY_ROOT_REFREEZE_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Market05AuthorityRootError(
            "MARKET_05_AUTHORITY_ROOT_REFREEZE_MALFORMED"
        ) from exc
    head = payload.get(SCIENTIFIC_IMPLEMENTATION_HEAD_KEY)
    tree = payload.get(SCIENTIFIC_IMPLEMENTATION_TREE_KEY)
    for label, value in (("head", head), ("tree", tree)):
        if not isinstance(value, str) or len(value) != 40:
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_PROVENANCE_INVALID:{label}"
            )
        if "UNSET" in value:
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_PROVENANCE_PLACEHOLDER:{label}"
            )
    return {"head": head, "tree": tree}


def verify_frozen_commit_tree(provenance: dict[str, str]) -> dict[str, Any]:
    """Cross-check the frozen commit/tree against the pinned blob ids.

    Verifies, when the git object store is available:

    * the recorded commit resolves and its tree equals the recorded tree;
    * this module's own bytes at that commit equal the bytes executing now
      (this module cannot pin its own blob id, so it is anchored here);
    * every pinned blob id is the blob actually recorded at that commit,
      so the docs cannot name an unrelated tree.
    """
    head = provenance["head"]
    tree = provenance["tree"]

    resolved = _git("rev-parse", "--verify", "--quiet", f"{head}^{{tree}}")
    if resolved.returncode != 0:
        # Object store unavailable (e.g. an exported tree). Blob-id
        # verification above still stands on its own.
        return {"git_verified": False, "head": head, "tree": tree}
    if resolved.stdout.decode().strip() != tree:
        raise Market05AuthorityRootError("MARKET_05_AUTHORITY_ROOT_TREE_MISMATCH")

    # This module, anchored by the frozen commit rather than by itself.
    own = _git("cat-file", "-p", f"{head}:{AUTHORITY_ROOT_REL}")
    if own.returncode != 0:
        raise Market05AuthorityRootError(
            "MARKET_05_AUTHORITY_ROOT_NOT_IN_FROZEN_COMMIT"
        )
    if own.stdout != _path(AUTHORITY_ROOT_REL).read_bytes():
        raise Market05AuthorityRootError("MARKET_05_AUTHORITY_ROOT_SELF_MUTATED")

    # Every pinned blob id must be the one recorded at the frozen commit.
    listing = _git("ls-tree", "-r", "-z", head)
    if listing.returncode != 0:
        raise Market05AuthorityRootError("MARKET_05_AUTHORITY_ROOT_TREE_UNREADABLE")
    recorded: dict[str, str] = {}
    for entry in listing.stdout.decode("utf-8", "replace").split("\0"):
        if not entry:
            continue
        meta, _, rel = entry.partition("\t")
        parts = meta.split()
        if len(parts) >= 3:
            recorded[rel] = parts[2]
    for rel, expected in FROZEN_BLOB_IDS.items():
        if recorded.get(rel) != expected:
            raise Market05AuthorityRootError(
                f"MARKET_05_AUTHORITY_ROOT_COMMIT_BLOB_MISMATCH:{rel}"
            )
    return {"git_verified": True, "head": head, "tree": tree}


def verify_authority_root(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Establish the root of trust. Must run BEFORE the ARM authority."""
    if args or kwargs:
        raise Market05AuthorityRootError(
            "caller arguments cannot redefine the MARKET-05 authority root"
        )
    blobs = verify_frozen_blob_ids()
    provenance = load_frozen_provenance()
    commit = verify_frozen_commit_tree(provenance)
    return {
        "blob_ids": blobs,
        "scientific_implementation_head": commit["head"],
        "scientific_implementation_tree": commit["tree"],
        "git_verified": commit["git_verified"],
    }


def _provenance_or_none(key: str) -> str | None:
    try:
        return load_frozen_provenance()[key]
    except Market05AuthorityRootError:
        return None


def __getattr__(name: str) -> Any:
    """Expose frozen provenance as module attributes, read from the artifact."""
    if name == "SCIENTIFIC_IMPLEMENTATION_HEAD":
        return _provenance_or_none("head")
    if name == "SCIENTIFIC_IMPLEMENTATION_TREE":
        return _provenance_or_none("tree")
    raise AttributeError(name)
