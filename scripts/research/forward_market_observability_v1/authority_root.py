"""FORWARD_MARKET_OBSERVABILITY_V1 independent authority root of trust.

Closes the self-attestation gap: ``collection_authority.py`` cannot
authenticate its own bytes, so a mutation of that module could otherwise
weaken every downstream check.

Mirrors the MARKET-05 authority-root design:

* pins the git **blob id** of every collector/authority file, including
  ``collection_authority.py``, computed from content alone
  (``sha1("blob <len>\\0" + bytes)``) -- no commit required to compute it;
* does NOT pin its own blob id (impossible: a file cannot contain a
  literal constant equal to its own hash); its integrity is established
  from the other direction -- the frozen COLLECTOR SOURCE commit/tree
  recorded in the refreeze artifact must contain this file with exactly
  the bytes executing now;
* fails closed without a locally verifiable git object store. There is no
  exported-tree/no-git authorization mode.

This module loads no market data and decides no collection authorization
itself; it only establishes whether the executing bytes are the frozen
ones.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_GIT_ENV_BLOCKLIST_PREFIX = "GIT_"
_GIT_ENV_KEEP = {"GIT_CONFIG_NOSYSTEM"}


class ForwardObservabilityAuthorityRootError(RuntimeError):
    """The executing authority bytes are not the frozen authority bytes."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _authority_git_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_GIT_ENV_BLOCKLIST_PREFIX)
    }
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["PATH"] = os.environ.get("PATH", "")
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    if "LANG" in os.environ:
        env["LANG"] = os.environ["LANG"]
    return env


def resolved_git_executable() -> str:
    found = shutil.which("git")
    if not found:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED:git_unavailable"
        )
    return str(Path(found).resolve())


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _git(*argv: str) -> subprocess.CompletedProcess:
    """Run git without replace-refs or GIT_* repository redirection."""
    try:
        exe = resolved_git_executable()
        return subprocess.run(
            [exe, "--no-replace-objects", "-c", "core.useReplaceRefs=false", *argv],
            cwd=str(_repo_root()),
            capture_output=True,
            check=False,
            env=_authority_git_env(),
        )
    except OSError as exc:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED:git_unavailable"
        ) from exc


def git_ls_files(rel: str) -> subprocess.CompletedProcess:
    return _git("ls-files", "--error-unmatch", "--", rel)


def git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}".encode("utf-8") + b"\x00"
    return hashlib.sha1(header + data).hexdigest()


AUTHORITY_ROOT_REL = (
    "scripts/research/forward_market_observability_v1/authority_root.py"
)
COLLECTION_AUTHORITY_REL = (
    "scripts/research/forward_market_observability_v1/collection_authority.py"
)
REFREEZE_JSON_REL = (
    "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_REFREEZE.json"
)
COLLECTOR_SOURCE_HEAD_KEY = "collector_source_head"
COLLECTOR_SOURCE_TREE_KEY = "collector_source_tree"

# git blob ids of every collector file that can materially change
# authorization or collection behaviour, including collection_authority.py
# itself. Filled by the refreeze.
FROZEN_BLOB_IDS: dict[str, str] = {
    "scripts/research/forward_market_observability_v1/__init__.py": "3710f289b59f4d6464f8928af813f36aa91500da",
    "scripts/research/forward_market_observability_v1/__main__.py": "73f9cc09505d04e51e0d22e52b953cd8eaae765f",
    "scripts/research/forward_market_observability_v1/cli.py": "bf0ca8fd8e04704365b4c264248b4d9c50c0db09",
    "scripts/research/forward_market_observability_v1/clock.py": "f457ca60ec982e9664179dde41aa50a039ecd554",
    "scripts/research/forward_market_observability_v1/collector.py": "914935f396b143e7fa9771cfbbcfd1379d7f085f",
    "scripts/research/forward_market_observability_v1/envelope.py": "a9dd3108d4aaa28226e0b75b5aab71b119853c86",
    "scripts/research/forward_market_observability_v1/health.py": "f05d4f551365defcede3bb6e3b36e2445a36f96b",
    "scripts/research/forward_market_observability_v1/identity.py": "8300b56a4112a02804aa4191b1743d373724a176",
    "scripts/research/forward_market_observability_v1/parse.py": "2f12093289f73fe48ff2139dab83552d907a6c96",
    "scripts/research/forward_market_observability_v1/schemas.py": "6a68ce4ceadaca16b9befdc59197bdd23fdfbf8b",
    "scripts/research/forward_market_observability_v1/session.py": "05dbf0d9ba252a87a3d253fe379d199c9ce82fd9",
    "scripts/research/forward_market_observability_v1/sources.py": "89a211cf005ba602d7eda80797caa3affbe2bc7b",
    "scripts/research/forward_market_observability_v1/storage.py": "36ae72cc7164f6c35fa87cc486fa397c6071b083",
    "scripts/research/forward_market_observability_v1/transport.py": "d0623605726794166247ebb9bbb4ccb9afcd32d6",
    "scripts/research/forward_market_observability_v1/collection_authority.py": "bf9adec2cf576cb1f6e64d70927f4d8c3ec372fd",
}


def verify_frozen_blob_ids() -> dict[str, str]:
    seen: dict[str, str] = {}
    for rel, expected in sorted(FROZEN_BLOB_IDS.items()):
        path = _path(rel)
        if path.is_symlink():
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_SYMLINK_REFUSED:{rel}"
            )
        if not path.is_file():
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_FILE_MISSING:{rel}"
            )
        actual = git_blob_id(path.read_bytes())
        if actual != expected:
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_BLOB_MISMATCH:{rel}"
            )
        seen[rel] = actual
    return seen


def load_frozen_provenance() -> dict[str, str]:
    path = _path(REFREEZE_JSON_REL)
    if path.is_symlink():
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_SYMLINK_REFUSED:refreeze"
        )
    if not path.is_file():
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_REFREEZE_MISSING"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_REFREEZE_MALFORMED"
        ) from exc
    head = payload.get(COLLECTOR_SOURCE_HEAD_KEY)
    tree = payload.get(COLLECTOR_SOURCE_TREE_KEY)
    for label, value in (("head", head), ("tree", tree)):
        if not isinstance(value, str) or len(value) != 40:
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_PROVENANCE_INVALID:{label}"
            )
        if (
            "UNSET" in value.upper()
            or value == "0" * 40
            or any(ch not in "0123456789abcdef" for ch in value.lower())
        ):
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_PROVENANCE_PLACEHOLDER:{label}"
            )
    return {"head": head, "tree": tree}


def verify_frozen_commit_tree(provenance: dict[str, str]) -> dict[str, Any]:
    """Fails closed: the git object store MUST be locally verifiable."""
    head = provenance["head"]
    tree = provenance["tree"]
    try:
        resolved = _git("rev-parse", "--verify", "--quiet", f"{head}^{{tree}}")
    except OSError as exc:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED:git_unavailable"
        ) from exc
    if resolved.returncode != 0:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED:"
            "frozen_commit_unresolvable"
        )
    if resolved.stdout.decode().strip() != tree:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_TREE_MISMATCH"
        )

    own = _git("cat-file", "-p", f"{head}:{AUTHORITY_ROOT_REL}")
    if own.returncode != 0:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_NOT_IN_FROZEN_COMMIT"
        )
    if own.stdout != _path(AUTHORITY_ROOT_REL).read_bytes():
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_SELF_MUTATED"
        )

    listing = _git("ls-tree", "-r", "-z", head)
    if listing.returncode != 0:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_TREE_UNREADABLE"
        )
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
            raise ForwardObservabilityAuthorityRootError(
                f"FORWARD_OBS_AUTHORITY_ROOT_COMMIT_BLOB_MISMATCH:{rel}"
            )
    return {"git_verified": True, "head": head, "tree": tree}


def verify_authority_root(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        raise ForwardObservabilityAuthorityRootError(
            "caller arguments cannot redefine the FORWARD_MARKET_OBSERVABILITY_V1 authority root"
        )
    blobs = verify_frozen_blob_ids()
    provenance = load_frozen_provenance()
    commit = verify_frozen_commit_tree(provenance)
    if commit.get("git_verified") is not True:
        raise ForwardObservabilityAuthorityRootError(
            "FORWARD_OBS_AUTHORITY_ROOT_GIT_VERIFICATION_REQUIRED"
        )
    return {
        "blob_ids": blobs,
        "collector_source_head": commit["head"],
        "collector_source_tree": commit["tree"],
        "git_verified": commit["git_verified"],
    }
