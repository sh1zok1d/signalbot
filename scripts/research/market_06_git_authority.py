"""Hardened immutable Git object authority for MARKET-06.

Every MARKET-06 lifecycle/scientific authority decision must be derived
from immutable Git objects, never from mutable working-tree state.

Hardening (red-team F-08):

* ``GIT_*`` repository-redirection variables are stripped from the child
  environment (``GIT_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``,
  ``GIT_OBJECT_DIRECTORY``, ``GIT_ALTERNATE_OBJECT_DIRECTORIES``,
  ``GIT_COMMON_DIR``, ...);
* replace refs are disabled (``--no-replace-objects`` +
  ``core.useReplaceRefs=false``) so a replace ref cannot substitute object
  content;
* system/global config is neutralized;
* the ``git`` executable is resolved to an absolute path;
* object existence is proven with ``git cat-file -e <oid>^{<type>}``.
  ``git rev-parse <40hex>`` echoes unknown SHAs back verbatim and is never
  accepted as proof of existence.

This module performs no scientific computation and reads no OHLC values.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

_GIT_ENV_PREFIX = "GIT_"
_GIT_ENV_KEEP = {"GIT_CONFIG_NOSYSTEM"}
HEX40 = 40


class Market06GitAuthorityError(RuntimeError):
    """Immutable Git object authority could not be established."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_GIT_ENV_PREFIX) or key in _GIT_ENV_KEEP
    }
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["PATH"] = os.environ.get("PATH", "")
    for passthrough in ("HOME", "LANG", "LC_ALL"):
        if passthrough in os.environ:
            env[passthrough] = os.environ[passthrough]
    return env


def resolved_git_executable() -> str:
    found = shutil.which("git")
    if not found:
        raise Market06GitAuthorityError("MARKET_06_GIT_UNAVAILABLE")
    return str(Path(found).resolve())


def git(*argv: str) -> subprocess.CompletedProcess:
    """Run git with replace-refs and GIT_* redirection neutralized."""

    try:
        exe = resolved_git_executable()
        return subprocess.run(
            [exe, "--no-replace-objects", "-c", "core.useReplaceRefs=false", *argv],
            cwd=str(repo_root()),
            capture_output=True,
            check=False,
            env=_git_env(),
        )
    except OSError as exc:  # pragma: no cover - environment failure
        raise Market06GitAuthorityError("MARKET_06_GIT_UNAVAILABLE") from exc


def _require_hex40(oid: str, *, label: str) -> str:
    if not isinstance(oid, str) or len(oid) != HEX40:
        raise Market06GitAuthorityError(f"MARKET_06_OID_NOT_HEX40:{label}")
    lowered = oid.lower()
    if any(ch not in "0123456789abcdef" for ch in lowered):
        raise Market06GitAuthorityError(f"MARKET_06_OID_NOT_HEX40:{label}")
    if lowered == "0" * HEX40:
        raise Market06GitAuthorityError(f"MARKET_06_OID_NULL:{label}")
    return lowered


def require_object(oid: str, *, kind: str, label: str = "object") -> str:
    """Prove an object of exactly ``kind`` exists. Never trust rev-parse echo."""

    resolved = _require_hex40(oid, label=label)
    proc = git("cat-file", "-e", f"{resolved}^{{{kind}}}")
    if proc.returncode != 0:
        raise Market06GitAuthorityError(
            f"MARKET_06_GIT_OBJECT_MISSING:{kind}:{label}:{resolved}"
        )
    return resolved


def require_commit(oid: str, *, label: str = "commit") -> str:
    return require_object(oid, kind="commit", label=label)


def commit_tree(commit: str) -> str:
    resolved = require_commit(commit)
    proc = git("rev-parse", "--verify", "--quiet", f"{resolved}^{{tree}}")
    if proc.returncode != 0:
        raise Market06GitAuthorityError(f"MARKET_06_GIT_TREE_UNRESOLVABLE:{resolved}")
    tree = proc.stdout.decode("ascii").strip()
    return require_object(tree, kind="tree", label="tree")


def require_commit_tree(commit: str, tree: str, *, label: str = "commit") -> tuple[str, str]:
    resolved_commit = require_commit(commit, label=label)
    expected_tree = _require_hex40(tree, label=f"{label}.tree")
    actual_tree = commit_tree(resolved_commit)
    if actual_tree != expected_tree:
        raise Market06GitAuthorityError(
            f"MARKET_06_GIT_TREE_MISMATCH:{label}:{actual_tree}"
        )
    return resolved_commit, actual_tree


def blob_exists(commit: str, relpath: str) -> bool:
    resolved = require_commit(commit)
    proc = git("cat-file", "-e", f"{resolved}:{relpath}")
    return proc.returncode == 0


def cat_blob(commit: str, relpath: str) -> bytes:
    """Read exact immutable bytes of ``relpath`` at ``commit``."""

    resolved = require_commit(commit)
    proc = git("cat-file", "-p", f"{resolved}:{relpath}")
    if proc.returncode != 0:
        raise Market06GitAuthorityError(
            f"MARKET_06_GIT_BLOB_MISSING:{relpath}@{resolved[:12]}"
        )
    return proc.stdout


def blob_sha256(commit: str, relpath: str) -> str:
    return hashlib.sha256(cat_blob(commit, relpath)).hexdigest()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    a = require_commit(ancestor, label="ancestor")
    d = require_commit(descendant, label="descendant")
    proc = git("merge-base", "--is-ancestor", a, d)
    return proc.returncode == 0


def require_ancestor(ancestor: str, descendant: str, *, label: str) -> None:
    if not is_ancestor(ancestor, descendant):
        raise Market06GitAuthorityError(f"MARKET_06_NOT_DESCENDANT:{label}")


def tree_blob_ids(commit: str) -> dict[str, str]:
    """Map relpath -> blob oid for every file recorded in ``commit``."""

    resolved = require_commit(commit)
    proc = git("ls-tree", "-r", "-z", resolved)
    if proc.returncode != 0:
        raise Market06GitAuthorityError(f"MARKET_06_GIT_TREE_UNREADABLE:{resolved}")
    out: dict[str, str] = {}
    for entry in proc.stdout.decode("utf-8", "replace").split("\0"):
        if not entry:
            continue
        meta, _, rel = entry.partition("\t")
        parts = meta.split()
        if len(parts) >= 3:
            out[rel] = parts[2]
    return out


def working_tree_is_clean() -> bool:
    """Advisory only. Never an authorization input."""

    proc = git("status", "--porcelain")
    if proc.returncode != 0:
        return False
    return proc.stdout.decode("utf-8", "replace").strip() == ""
