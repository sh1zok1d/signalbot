"""Deterministic, local-only tests for deploy/sync_backup_offsite.sh.

No real cloud account, no real `rclone` binary, and no network are required:
a small fake `rclone` executable (a bash script backed by a plain directory
tree) is placed first on PATH so the script under test talks to a
deterministic local stand-in. This exercises the script's own selection,
validation, idempotency, and retention logic exactly as written — it does
not (and cannot) prove any real provider's `rclone` backend behaves the
same way.
"""
from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
SCRIPT = DEPLOY / "sync_backup_offsite.sh"

FAKE_RCLONE = r"""#!/usr/bin/env bash
set -euo pipefail
STORE="${FAKE_RCLONE_STORE:?FAKE_RCLONE_STORE not set}"
cmd="$1"; shift
_map() { # remote:path -> $STORE/path
  local arg="$1"
  echo "${STORE}/${arg#*:}"
}
case "$cmd" in
  copyto)
    src="$1"; dst="$(_map "$2")"
    if [ "${FAKE_RCLONE_FAIL_UPLOAD:-0}" = "1" ]; then
      echo "fake rclone: simulated upload failure" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    ;;
  lsf)
    dir="$(_map "$1")"
    if [ -d "$dir" ]; then
      ls -1 "$dir"
    fi
    ;;
  deletefile)
    f="$(_map "$1")"
    if [ "${FAKE_RCLONE_FAIL_DELETE:-0}" = "1" ]; then
      echo "fake rclone: simulated delete failure" >&2
      exit 1
    fi
    [ -f "$f" ] || { echo "fake rclone: no such file: $f" >&2; exit 1; }
    rm -f "$f"
    ;;
  *)
    echo "fake rclone: unsupported command: $cmd" >&2
    exit 2
    ;;
esac
"""


def _make_dump(path: Path, content: bytes = b"-- fake sql dump --") -> Path:
    with gzip.open(path, "wb") as f:
        f.write(content)
    return path


@pytest.fixture()
def fake_rclone(tmp_path: Path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "rclone"
    exe.write_text(FAKE_RCLONE)
    exe.chmod(0o755)
    store = tmp_path / "fakeremote"
    store.mkdir()
    return bindir, store


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


def _run(fake_rclone, backup_dir, args=(), extra_env=None, remote="fake:signalbot-backups"):
    bindir, store = fake_rclone
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["FAKE_RCLONE_STORE"] = str(store)
    env["BACKUP_DIR"] = str(backup_dir)
    if remote is not None:
        env["SIGNALBOT_BACKUP_REMOTE"] = remote
    else:
        env.pop("SIGNALBOT_BACKUP_REMOTE", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def _remote_files(fake_rclone, tier: str, prefix: str = "signalbot-backups") -> list[str]:
    _, store = fake_rclone
    d = store / prefix / tier
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir())


# ============================================================================
# A. static / repo conventions
# ============================================================================
def test_script_exists_and_is_git_executable():
    assert SCRIPT.is_file()
    rel = str(SCRIPT.relative_to(ROOT))
    out = subprocess.run(["git", "ls-files", "-s", "--", rel], cwd=ROOT,
                          capture_output=True, text=True).stdout
    assert out.strip(), f"{rel} is not tracked by git"
    assert out.split()[0] == "100755"


def test_script_parses():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_script_strict_mode():
    text = SCRIPT.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


def test_script_never_deletes_local_dump():
    code = "\n".join(l for l in SCRIPT.read_text().splitlines() if not l.lstrip().startswith("#"))
    assert "rm " not in code
    assert "rm -f \"$dump\"" not in code


# ============================================================================
# B. selection (spec §14 items 1-2)
# ============================================================================
def test_selects_newest_valid_completed_dump(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    _make_dump(backup_dir / "btcbot_20260810T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260810T030000Z.sql.gz"]


def test_ignores_partial_files(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    # a newer .partial must never be picked, even though it is newer by name/mtime
    (backup_dir / "btcbot_20260815T030000Z.sql.gz.partial").write_bytes(b"incomplete")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260801T030000Z.sql.gz"]


def test_explicit_dump_argument_is_honored(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    other = _make_dump(backup_dir / "btcbot_20260805T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, args=[str(other)])
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260805T030000Z.sql.gz"]


# ============================================================================
# C. validation (spec §14 items 3-4)
# ============================================================================
def test_rejects_invalid_gzip(fake_rclone, backup_dir):
    bad = backup_dir / "btcbot_20260801T030000Z.sql.gz"
    bad.write_bytes(b"this is not gzip content")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode != 0
    assert "not a valid gzip" in result.stderr
    assert _remote_files(fake_rclone, "daily") == []


def test_rejects_empty_dump(fake_rclone, backup_dir):
    empty = backup_dir / "btcbot_20260801T030000Z.sql.gz"
    empty.touch()
    result = _run(fake_rclone, backup_dir)
    assert result.returncode != 0
    assert "empty" in result.stderr


def test_refuses_missing_remote_configuration(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, remote=None)
    assert result.returncode != 0
    assert "SIGNALBOT_BACKUP_REMOTE" in result.stderr


def test_refuses_empty_remote_configuration(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, remote="")
    assert result.returncode != 0


def test_refuses_remote_without_path_component(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    # bare remote name with no colon at all
    result = _run(fake_rclone, backup_dir, remote="gdrive")
    assert result.returncode != 0
    # remote name WITH colon but empty path -> would be an ambiguous root op
    result2 = _run(fake_rclone, backup_dir, remote="gdrive:")
    assert result2.returncode != 0
    assert "root" in result2.stderr.lower()


# ============================================================================
# D. upload success/failure (spec §14 items 5-7)
# ============================================================================
def test_successful_fake_upload(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260801T030000Z.sql.gz"]


def test_remote_upload_failure_returns_nonzero(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_UPLOAD": "1"})
    assert result.returncode != 0
    assert _remote_files(fake_rclone, "daily") == []


def test_local_backup_survives_remote_failure(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    before = dump.read_bytes()
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_UPLOAD": "1"})
    assert result.returncode != 0
    assert dump.is_file()
    assert dump.read_bytes() == before


# ============================================================================
# E. retention (spec §14 items 8-9)
# ============================================================================
def test_retention_deletes_only_objects_beyond_tier_count(fake_rclone, backup_dir):
    _, store = fake_rclone
    daily_dir = store / "signalbot-backups" / "daily"
    daily_dir.mkdir(parents=True)
    for day in ("01", "02", "03", "04", "05"):
        _make_dump(daily_dir / f"btcbot_202608{day}T030000Z.sql.gz")
    _make_dump(backup_dir / "btcbot_20260806T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={
        "SIGNALBOT_BACKUP_DAILY_RETENTION": "3",
        "SIGNALBOT_BACKUP_WEEKLY_RETENTION": "12",
        "SIGNALBOT_BACKUP_MONTHLY_RETENTION": "12",
    })
    assert result.returncode == 0, result.stderr
    # newest 3 of {01..06} are 04, 05, 06 -- exactly retention=3 survive
    assert _remote_files(fake_rclone, "daily") == [
        "btcbot_20260804T030000Z.sql.gz",
        "btcbot_20260805T030000Z.sql.gz",
        "btcbot_20260806T030000Z.sql.gz",
    ]


def test_retention_never_escapes_configured_remote_path(fake_rclone, backup_dir):
    _, store = fake_rclone
    daily_dir = store / "signalbot-backups" / "daily"
    daily_dir.mkdir(parents=True)
    # a non-matching, unrelated object that retention pruning must never touch
    unrelated = daily_dir / "not-a-backup.txt"
    unrelated.write_text("do not touch")
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={
        "SIGNALBOT_BACKUP_DAILY_RETENTION": "1",
    })
    assert result.returncode == 0, result.stderr
    assert unrelated.is_file()
    assert unrelated.read_text() == "do not touch"
    # nothing was ever written outside the three known tier subdirectories
    top = store / "signalbot-backups"
    assert set(p.name for p in top.iterdir()) <= {"daily", "weekly", "monthly"}


def test_retention_pruning_failure_is_nonzero_and_does_not_mask_success(fake_rclone, backup_dir):
    _, store = fake_rclone
    daily_dir = store / "signalbot-backups" / "daily"
    daily_dir.mkdir(parents=True)
    _make_dump(daily_dir / "btcbot_20260801T030000Z.sql.gz")
    _make_dump(backup_dir / "btcbot_20260802T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={
        "SIGNALBOT_BACKUP_DAILY_RETENTION": "1",
        "FAKE_RCLONE_FAIL_DELETE": "1",
    })
    assert result.returncode != 0
    # the newly-uploaded backup was NOT deleted merely to mask the pruning failure
    assert "btcbot_20260802T030000Z.sql.gz" in _remote_files(fake_rclone, "daily")


# ============================================================================
# F. idempotency / weekly-monthly de-duplication (spec §14 items 10-12)
# ============================================================================
def test_repeated_sync_is_idempotent(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    r1 = _run(fake_rclone, backup_dir, args=[str(dump)])
    r2 = _run(fake_rclone, backup_dir, args=[str(dump)])
    assert r1.returncode == 0 and r2.returncode == 0
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260801T030000Z.sql.gz"]
    assert _remote_files(fake_rclone, "weekly") == ["btcbot_20260801T030000Z.sql.gz"]
    assert _remote_files(fake_rclone, "monthly") == ["btcbot_20260801T030000Z.sql.gz"]


def test_weekly_representative_not_duplicated_in_same_week(fake_rclone, backup_dir):
    # 2026-08-03 and 2026-08-04 are both within the same ISO/UTC week
    d1 = _make_dump(backup_dir / "btcbot_20260803T030000Z.sql.gz")
    d2 = _make_dump(backup_dir / "btcbot_20260804T030000Z.sql.gz")
    r1 = _run(fake_rclone, backup_dir, args=[str(d1)])
    r2 = _run(fake_rclone, backup_dir, args=[str(d2)])
    assert r1.returncode == 0 and r2.returncode == 0
    # exactly one weekly representative -- the first one written, never overwritten
    assert _remote_files(fake_rclone, "weekly") == ["btcbot_20260803T030000Z.sql.gz"]
    # daily still receives both independently
    assert _remote_files(fake_rclone, "daily") == [
        "btcbot_20260803T030000Z.sql.gz", "btcbot_20260804T030000Z.sql.gz"]


def test_monthly_representative_not_duplicated_in_same_month(fake_rclone, backup_dir):
    d1 = _make_dump(backup_dir / "btcbot_20260803T030000Z.sql.gz")
    d2 = _make_dump(backup_dir / "btcbot_20260825T030000Z.sql.gz")  # different week, same month
    r1 = _run(fake_rclone, backup_dir, args=[str(d1)])
    r2 = _run(fake_rclone, backup_dir, args=[str(d2)])
    assert r1.returncode == 0 and r2.returncode == 0
    assert _remote_files(fake_rclone, "monthly") == ["btcbot_20260803T030000Z.sql.gz"]
    # confirms these two really do fall in different ISO weeks (a stronger check
    # that the monthly test isn't accidentally exercising weekly de-dup instead)
    assert _remote_files(fake_rclone, "weekly") == [
        "btcbot_20260803T030000Z.sql.gz", "btcbot_20260825T030000Z.sql.gz"]


def test_next_month_gets_its_own_representative(fake_rclone, backup_dir):
    d1 = _make_dump(backup_dir / "btcbot_20260803T030000Z.sql.gz")
    d2 = _make_dump(backup_dir / "btcbot_20260903T030000Z.sql.gz")
    r1 = _run(fake_rclone, backup_dir, args=[str(d1)])
    r2 = _run(fake_rclone, backup_dir, args=[str(d2)])
    assert r1.returncode == 0 and r2.returncode == 0
    assert _remote_files(fake_rclone, "monthly") == [
        "btcbot_20260803T030000Z.sql.gz", "btcbot_20260903T030000Z.sql.gz"]
