"""The git SHA of the running build (architect, 2026-10-08): ОПГ-2's forecast journal writes it into
every record. One source for every beta process, read once per process:

1. `BETA_BUILD_SHA` in the environment, when set: an explicit SHA (7–40 hex, optional `-dirty`);
2. `git rev-parse HEAD` of the checkout this code runs from, with `-dirty` when a tracked file differs
   from HEAD (the code on disk then is not exactly that commit);
3. the `BUILD_SHA` file at the checkout root, which `deploy/install_beta_units.sh` writes at every
   deploy, for a process that cannot run git (no `.git`, or git refuses the directory's owner);
4. otherwise "unknown": never a guess.

Not `BETA_CODE_VERSION` (runtime/beta_cli.py): that is the last commit touching the beta paths, it
carries a content-hash dirty suffix and it feeds the tape's code identity; this is the build's HEAD.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Mapping, Optional

UNKNOWN = "unknown"
BUILD_SHA_FILE = "BUILD_SHA"
_SHA = re.compile(r"^[0-9a-f]{7,40}(-dirty)?$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _valid(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip().lower()
    return v if _SHA.match(v) else None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5,
                          check=True).stdout.strip()


def resolve_build_sha(*, env: Optional[Mapping[str, str]] = None, repo_root: Optional[Path] = None) -> str:
    """The build SHA by the order above; "unknown" when none is readable. A malformed explicit value is
    not used (it falls through), so a typo never becomes a recorded build."""
    env = os.environ if env is None else env
    root = repo_root if repo_root is not None else _repo_root()
    explicit = _valid(env.get("BETA_BUILD_SHA"))
    if explicit:
        return explicit
    try:
        head = _valid(_git(root, "rev-parse", "HEAD"))
        if head:
            dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=no"))
            return f"{head}-dirty" if dirty else head
    except Exception:  # noqa: BLE001 - no git, not a repo, or refused: the deploy-written file next
        pass
    try:
        from_file = _valid((root / BUILD_SHA_FILE).read_text(encoding="utf-8"))
    except OSError:
        from_file = None
    return from_file or UNKNOWN


# Resolved once, when the module is imported, i.e. when the process loads its code: a long-lived
# process (the bot) must report the code it runs, not a HEAD pulled onto the disk later.
_PROCESS_BUILD_SHA = resolve_build_sha()


def build_sha() -> str:
    """The running process's build SHA (resolved at import; see above)."""
    return _PROCESS_BUILD_SHA
