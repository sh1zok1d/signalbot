"""The build SHA every beta process reports (beta/build.py): explicit env, then the checkout's HEAD (with
-dirty), then the deploy-written BUILD_SHA file, else "unknown" — never a guess."""
import shutil
import subprocess
from pathlib import Path

import pytest

from beta.build import UNKNOWN, resolve_build_sha

ROOT = Path(__file__).resolve().parents[2]
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _repo(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("1")
    git("add", "a.txt")
    git("commit", "-qm", "c1")
    return git, git("rev-parse", "HEAD")


def test_an_explicit_sha_wins_and_a_malformed_one_is_never_recorded(tmp_path):
    sha = "a" * 40
    assert resolve_build_sha(env={"BETA_BUILD_SHA": sha}, repo_root=tmp_path) == sha
    assert resolve_build_sha(env={"BETA_BUILD_SHA": f" {sha.upper()}-DIRTY "}, repo_root=tmp_path) == sha + "-dirty"
    assert resolve_build_sha(env={"BETA_BUILD_SHA": "v1.2 main"}, repo_root=tmp_path) == UNKNOWN


@needs_git
def test_the_checkouts_head_and_dirty_when_a_tracked_file_differs(tmp_path):
    git, head = _repo(tmp_path)
    assert resolve_build_sha(env={}, repo_root=tmp_path) == head
    (tmp_path / "new.txt").write_text("untracked")                      # untracked files do not count
    assert resolve_build_sha(env={}, repo_root=tmp_path) == head
    (tmp_path / "a.txt").write_text("2")
    assert resolve_build_sha(env={}, repo_root=tmp_path) == head + "-dirty"


def test_without_git_the_deploy_written_file_else_unknown(tmp_path):
    assert resolve_build_sha(env={}, repo_root=tmp_path) == UNKNOWN          # no .git, no file
    (tmp_path / "BUILD_SHA").write_text("b" * 40 + "\n")
    assert resolve_build_sha(env={}, repo_root=tmp_path) == "b" * 40
    (tmp_path / "BUILD_SHA").write_text("garbage\n")
    assert resolve_build_sha(env={}, repo_root=tmp_path) == UNKNOWN


@needs_git
def test_the_units_installer_records_the_build_sha_and_never_leaves_a_stale_one():
    text = (ROOT / "deploy" / "install_beta_units.sh").read_text()
    assert 'rev-parse HEAD' in text and '"${REPO_DIR}/BUILD_SHA"' in text and 'rm -f "${REPO_DIR}/BUILD_SHA"' in text
    assert "BUILD_SHA" in (ROOT / ".gitignore").read_text().split()


@needs_git
def test_this_checkout_reports_its_own_head():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert resolve_build_sha(env={}, repo_root=ROOT).split("-")[0] == head


def test_a_long_lived_process_keeps_the_sha_it_started_with(monkeypatch):
    """The SHA is fixed when the code is loaded: what changes on the disk or in the environment later
    (a pull, a new .env) does not change what a running process reports; it still runs the old code."""
    import importlib
    import beta.build as build
    monkeypatch.setenv("BETA_BUILD_SHA", "d" * 40)
    reloaded = importlib.reload(build)
    try:
        assert reloaded.build_sha() == "d" * 40
        monkeypatch.setenv("BETA_BUILD_SHA", "e" * 40)
        assert reloaded.build_sha() == "d" * 40          # unchanged until the process restarts
    finally:
        monkeypatch.undo()
        importlib.reload(build)
