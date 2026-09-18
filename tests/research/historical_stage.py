"""Locate historical lifecycle commits without assuming they are HEAD.

Used by freeze/ARM tests that were written when HEAD *was* the freeze or
ARM commit. Current descendants must still verify those git objects.
Does not load CORE/OI, mint RESULT, or consume reservations.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def git(*args: str, repo: Path = REPO) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def git_bytes(*args: str, repo: Path = REPO) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def unique_child_on_ancestry(parent: str, descendant: str = "HEAD", *, repo: Path = REPO) -> str:
    """Unique immediate child of ``parent`` on the ancestry path to ``descendant``."""
    path = git(
        "rev-list", "--ancestry-path", "--reverse", f"{parent}..{descendant}", repo=repo
    ).splitlines()
    if not path:
        raise AssertionError(f"{descendant} is not a descendant of {parent}")
    child = path[0]
    if git("rev-parse", f"{child}^", repo=repo) != parent:
        raise AssertionError(f"{child} is not the immediate child of {parent}")
    return child


def blob_bytes(commit: str, path: str, *, repo: Path = REPO) -> bytes:
    return git_bytes("cat-file", "blob", f"{commit}:{path}", repo=repo)


def blob_sha256(commit: str, path: str, *, repo: Path = REPO) -> str:
    return hashlib.sha256(blob_bytes(commit, path, repo=repo)).hexdigest()


def blob_json(commit: str, path: str, *, repo: Path = REPO) -> dict:
    return json.loads(blob_bytes(commit, path, repo=repo).decode("utf-8"))
