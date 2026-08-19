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
# Record every single invocation (any subcommand), unconditionally, before
# any other logic -- this lets tests prove a malformed local dump causes
# ZERO rclone invocations of any kind, not merely "no upload landed".
if [ -n "${FAKE_RCLONE_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${FAKE_RCLONE_CALL_LOG}"
fi
cmd="$1"; shift
_map() { # remote:path -> $STORE/path
  local arg="$1"
  echo "${STORE}/${arg#*:}"
}
case "$cmd" in
  mkdir)
    if [ "${FAKE_RCLONE_FAIL_MKDIR:-0}" = "1" ]; then
      echo "fake rclone: simulated mkdir failure" >&2
      exit 1
    fi
    dir="$(_map "$1")"
    mkdir -p "$dir"
    ;;
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
    if [ "${FAKE_RCLONE_FAIL_LSF:-0}" = "1" ]; then
      echo "fake rclone: simulated listing failure (auth/network/backend)" >&2
      exit 1
    fi
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


def _call_log_path(fake_rclone) -> Path:
    _, store = fake_rclone
    return store.parent / "rclone_calls.log"


def _call_log_lines(fake_rclone) -> list[str]:
    p = _call_log_path(fake_rclone)
    if not p.is_file():
        return []
    return [ln for ln in p.read_text().splitlines() if ln]


def _run(fake_rclone, backup_dir, args=(), extra_env=None, remote="fake:signalbot-backups"):
    bindir, store = fake_rclone
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["FAKE_RCLONE_STORE"] = str(store)
    env["FAKE_RCLONE_CALL_LOG"] = str(_call_log_path(fake_rclone))
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


@pytest.mark.parametrize("remote", ["gdrive:/", "gdrive://", "gdrive:///"])
def test_refuses_root_equivalent_slash_only_remote(fake_rclone, backup_dir, remote):
    # each of these normalizes (by stripping a single trailing slash) to the
    # exact bare-root form ("gdrive:") the code already claims to forbid --
    # the validation must catch them BEFORE any such normalization, not after.
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, remote=remote)
    assert result.returncode != 0, f"{remote!r} must be rejected as root-equivalent"
    assert "root" in result.stderr.lower()
    assert _remote_files(fake_rclone, "daily") == []


def test_accepts_slash_prefixed_nested_remote_path(fake_rclone, backup_dir):
    # a real path is allowed even when it happens to start with '/' or
    # contains internal '/' -- only an ALL-slashes (or empty) path is root-
    # equivalent and rejected.
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, remote="gdrive:/signalbot-backups")
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily", prefix="signalbot-backups") == [
        "btcbot_20260801T030000Z.sql.gz"]


def test_accepts_nested_nonroot_remote_path(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, remote="gdrive:a/b")
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily", prefix="a/b") == [
        "btcbot_20260801T030000Z.sql.gz"]


# ============================================================================
# C2. strict backup timestamp validation (INFRA-D1 follow-up: closes the
#     "malformed timestamps upload first" Qodo finding on merged PR #45).
#     A `?`-wildcard shape check validated field WIDTH only, so a malformed
#     but gzip-valid filename like "btcbot_abcdefghTijklmnZ.sql.gz" used to
#     pass, reach `rclone copyto` for daily/, and only fail LATER while
#     computing the weekly/monthly period key -- after the malformed object
#     was already uploaded. The exact digit shape AND real UTC calendar/
#     time validity are now both enforced before any rclone invocation.
# ============================================================================
def test_nonnumeric_timestamp_rejected_with_zero_rclone_calls(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_abcdefghTijklmnZ.sql.gz")
    before = dump.read_bytes()
    result = _run(fake_rclone, backup_dir)
    assert result.returncode != 0
    assert "filename shape" in result.stderr.lower() or "timestamp" in result.stderr.lower()
    assert _call_log_lines(fake_rclone) == [], "malformed timestamp must cause ZERO rclone invocations"
    assert _remote_files(fake_rclone, "daily") == []
    assert _remote_files(fake_rclone, "weekly") == []
    assert _remote_files(fake_rclone, "monthly") == []
    assert dump.is_file()
    assert dump.read_bytes() == before


@pytest.mark.parametrize("fname,label", [
    ("btcbot_20260230T030000Z.sql.gz", "impossible calendar date (Feb 30)"),
    ("btcbot_20261301T030000Z.sql.gz", "invalid month (13)"),
    ("btcbot_20260819T250000Z.sql.gz", "invalid hour (25)"),
    ("btcbot_20260819T236100Z.sql.gz", "invalid minute (61)"),
    ("btcbot_20260819T235960Z.sql.gz", "invalid second (60)"),
])
def test_impossible_or_invalid_datetime_rejected_with_zero_rclone_calls(fake_rclone, backup_dir, fname, label):
    dump = _make_dump(backup_dir / fname)
    before = dump.read_bytes()
    result = _run(fake_rclone, backup_dir)
    assert result.returncode != 0, f"{label} ({fname}) must be rejected"
    assert _call_log_lines(fake_rclone) == [], f"{label}: must cause ZERO rclone invocations"
    assert _remote_files(fake_rclone, "daily") == []
    assert _remote_files(fake_rclone, "weekly") == []
    assert _remote_files(fake_rclone, "monthly") == []
    assert dump.is_file()
    assert dump.read_bytes() == before


def test_valid_leap_day_accepted(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20280229T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20280229T030000Z.sql.gz"]
    assert _remote_files(fake_rclone, "weekly") == ["btcbot_20280229T030000Z.sql.gz"]
    assert _remote_files(fake_rclone, "monthly") == ["btcbot_20280229T030000Z.sql.gz"]


def test_valid_normal_timestamp_still_accepted(fake_rclone, backup_dir):
    # confirms the strict validation is not a regression for real producer
    # output (deploy/backup.sh's `date -u +%Y%m%dT%H%M%SZ`).
    _make_dump(backup_dir / "btcbot_20260819T031500Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    assert _remote_files(fake_rclone, "daily") == ["btcbot_20260819T031500Z.sql.gz"]
    # at least one rclone call did happen for a genuinely valid dump --
    # contrasts with the zero-invocation assertions above
    assert len(_call_log_lines(fake_rclone)) > 0


def test_trailing_garbage_after_extension_rejected(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_20260819T030000Z.sql.gz.extra")
    before = dump.read_bytes()
    result = _run(fake_rclone, backup_dir, args=[str(dump)])
    assert result.returncode != 0
    assert _call_log_lines(fake_rclone) == []
    assert dump.read_bytes() == before


def test_missing_z_suffix_rejected(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_20260819T030000.sql.gz")
    result = _run(fake_rclone, backup_dir, args=[str(dump)])
    assert result.returncode != 0
    assert _call_log_lines(fake_rclone) == []


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
# D2. remote LISTING failures must never be reinterpreted as "tier is empty"
#     (tech-lead amendment round 1, item 2: a swallowed `rclone lsf` error
#     previously let an auth/network/backend failure masquerade as an empty
#     remote, and the job could go on to report success.)
# ============================================================================
def test_lsf_failure_returns_nonzero(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_LSF": "1"})
    assert result.returncode != 0


def test_local_backup_survives_lsf_failure(fake_rclone, backup_dir):
    dump = _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    before = dump.read_bytes()
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_LSF": "1"})
    assert result.returncode != 0
    assert dump.is_file()
    assert dump.read_bytes() == before


def test_job_never_reports_done_after_lsf_failure(fake_rclone, backup_dir):
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_LSF": "1"})
    assert result.returncode != 0
    assert "[offsite] done." not in result.stdout


def test_lsf_failure_during_retention_is_not_treated_as_empty_tier(fake_rclone, backup_dir):
    # A pre-existing object sits in daily/. If the listing failure were ever
    # swallowed into an empty list (the old bug), retention pruning would
    # proceed believing there was nothing to prune/compare against. Instead
    # the whole run must abort before pruning ever runs, leaving the
    # pre-existing object completely untouched.
    _, store = fake_rclone
    daily_dir = store / "signalbot-backups" / "daily"
    daily_dir.mkdir(parents=True)
    _make_dump(daily_dir / "btcbot_20260701T030000Z.sql.gz")
    _make_dump(backup_dir / "btcbot_20260801T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={
        "FAKE_RCLONE_FAIL_LSF": "1",
        "SIGNALBOT_BACKUP_DAILY_RETENTION": "1",
    })
    assert result.returncode != 0
    # the pre-existing object was never pruned by a run that never validly
    # observed the tier's true contents
    assert "btcbot_20260701T030000Z.sql.gz" in _remote_files(fake_rclone, "daily")


def test_weekly_dedup_does_not_silently_continue_on_untrusted_listing(fake_rclone, backup_dir):
    # A weekly representative already exists. If the listing failure were
    # ever swallowed into "no representative found", the script would
    # proceed to upload a second, duplicate weekly representative for the
    # same UTC week. Instead the run must abort at the listing call itself,
    # uploading nothing further.
    _, store = fake_rclone
    weekly_dir = store / "signalbot-backups" / "weekly"
    weekly_dir.mkdir(parents=True)
    _make_dump(weekly_dir / "btcbot_20260803T030000Z.sql.gz")
    _make_dump(backup_dir / "btcbot_20260804T030000Z.sql.gz")  # same ISO week
    result = _run(fake_rclone, backup_dir, extra_env={"FAKE_RCLONE_FAIL_LSF": "1"})
    assert result.returncode != 0
    # still exactly the original single representative -- no duplicate landed
    assert _remote_files(fake_rclone, "weekly") == ["btcbot_20260803T030000Z.sql.gz"]


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


# ============================================================================
# G. malformed/foreign REMOTE objects have no semantic standing (PR #46
#    tech-lead amendment: closes the "invalid remotes suppress tier uploads"
#    Qodo finding). `_iso_week_of` used to examine only the DATE portion of a
#    remote candidate (never HHMMSS), and `_month_of` performed no date/time
#    validation at all, so a digit-shaped-but-impossible remote object could
#    still compute a normal-looking period key and silently masquerade as an
#    already-present representative -- suppressing a genuinely valid weekly
#    or monthly upload. Retention's shape-only grep had the same disease: a
#    digit-shaped-but-impossible timestamp could consume one of the `keep`
#    slots and displace a genuinely valid backup from being retained. The
#    fix routes ALL three call sites (local dump gate, weekly/monthly
#    dedup, retention accounting) through the one `_valid_backup_filename`
#    helper. A malformed/foreign remote object must never suppress a valid
#    upload, never count toward retention, and -- just as importantly -- is
#    never automatically deleted; it simply has no semantic standing.
# ============================================================================
def test_invalid_time_remote_object_does_not_suppress_weekly_upload(fake_rclone, backup_dir):
    _, store = fake_rclone
    weekly_dir = store / "signalbot-backups" / "weekly"
    weekly_dir.mkdir(parents=True)
    # digit-shaped but an impossible TIME (99:99:99). `_iso_week_of` only
    # ever looked at the DATE portion, so under the old shape-only remote
    # filter this would compute a normal-looking ISO week matching the
    # incoming valid dump below and masquerade as an already-present
    # representative -- suppressing the valid upload.
    malformed = _make_dump(weekly_dir / "btcbot_20260803T999999Z.sql.gz")
    before = malformed.read_bytes()
    _make_dump(backup_dir / "btcbot_20260804T030000Z.sql.gz")  # same ISO week as 2026-08-03
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    weekly_files = _remote_files(fake_rclone, "weekly")
    assert "btcbot_20260804T030000Z.sql.gz" in weekly_files, \
        "a genuinely valid weekly upload must not be suppressed by a malformed remote object"
    # the malformed object is left completely untouched -- excluded from
    # semantics, never deleted
    assert "btcbot_20260803T999999Z.sql.gz" in weekly_files
    assert malformed.read_bytes() == before


def test_invalid_time_remote_object_does_not_suppress_monthly_upload(fake_rclone, backup_dir):
    _, store = fake_rclone
    monthly_dir = store / "signalbot-backups" / "monthly"
    monthly_dir.mkdir(parents=True)
    malformed = _make_dump(monthly_dir / "btcbot_20260803T999999Z.sql.gz")
    before = malformed.read_bytes()
    _make_dump(backup_dir / "btcbot_20260825T030000Z.sql.gz")  # same month, different week
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    monthly_files = _remote_files(fake_rclone, "monthly")
    assert "btcbot_20260825T030000Z.sql.gz" in monthly_files, \
        "a genuinely valid monthly upload must not be suppressed by a malformed remote object"
    assert "btcbot_20260803T999999Z.sql.gz" in monthly_files
    assert malformed.read_bytes() == before


def test_impossible_date_remote_object_does_not_suppress_monthly_upload(fake_rclone, backup_dir):
    _, store = fake_rclone
    monthly_dir = store / "signalbot-backups" / "monthly"
    monthly_dir.mkdir(parents=True)
    # digit-shaped but an impossible DATE (Feb 30). `_month_of` performed no
    # date/time validation at all, so under the old code this would slice
    # out "2026-02" and masquerade as an already-present February
    # representative.
    malformed = _make_dump(monthly_dir / "btcbot_20260230T030000Z.sql.gz")
    before = malformed.read_bytes()
    _make_dump(backup_dir / "btcbot_20260228T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    monthly_files = _remote_files(fake_rclone, "monthly")
    assert "btcbot_20260228T030000Z.sql.gz" in monthly_files, \
        "a genuinely valid monthly upload must not be suppressed by an impossible-date remote object"
    assert "btcbot_20260230T030000Z.sql.gz" in monthly_files
    assert malformed.read_bytes() == before


def test_malformed_remote_names_are_skipped_without_crashing(fake_rclone, backup_dir):
    _, store = fake_rclone
    for tier in ("daily", "weekly", "monthly"):
        d = store / "signalbot-backups" / tier
        d.mkdir(parents=True)
        (d / "not-a-backup.txt").write_text("unrelated file")
        _make_dump(d / "btcbot_garbageTgarbageZ.sql.gz")
    _make_dump(backup_dir / "btcbot_20260819T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir)
    assert result.returncode == 0, result.stderr
    for tier in ("daily", "weekly", "monthly"):
        files = _remote_files(fake_rclone, tier)
        assert "btcbot_20260819T030000Z.sql.gz" in files
        # the foreign/malformed objects are left completely untouched
        assert "not-a-backup.txt" in files
        assert "btcbot_garbageTgarbageZ.sql.gz" in files


def test_retention_poisoning_malformed_object_does_not_consume_slot(fake_rclone, backup_dir):
    _, store = fake_rclone
    daily_dir = store / "signalbot-backups" / "daily"
    daily_dir.mkdir(parents=True)
    for day in ("01", "02", "03", "04", "05"):
        _make_dump(daily_dir / f"btcbot_202608{day}T030000Z.sql.gz")
    # digit-shaped, lexicographically "future" (a far year), but calendar-
    # IMPOSSIBLE (month 13). A shape-only retention filter would sort this
    # first (newest) and let it consume one of the `keep` slots, displacing
    # a genuinely valid backup from being retained.
    malformed = _make_dump(daily_dir / "btcbot_29991301T030000Z.sql.gz")
    before = malformed.read_bytes()
    _make_dump(backup_dir / "btcbot_20260806T030000Z.sql.gz")
    result = _run(fake_rclone, backup_dir, extra_env={
        "SIGNALBOT_BACKUP_DAILY_RETENTION": "3",
        "SIGNALBOT_BACKUP_WEEKLY_RETENTION": "12",
        "SIGNALBOT_BACKUP_MONTHLY_RETENTION": "12",
    })
    assert result.returncode == 0, result.stderr
    daily_files = _remote_files(fake_rclone, "daily")
    # newest 3 VALID backups (04, 05, 06) survive -- the malformed object,
    # despite sorting first, must never have consumed a retention slot
    assert "btcbot_20260804T030000Z.sql.gz" in daily_files
    assert "btcbot_20260805T030000Z.sql.gz" in daily_files
    assert "btcbot_20260806T030000Z.sql.gz" in daily_files
    # excess VALID objects beyond the newest 3 are pruned
    assert "btcbot_20260801T030000Z.sql.gz" not in daily_files
    assert "btcbot_20260802T030000Z.sql.gz" not in daily_files
    assert "btcbot_20260803T030000Z.sql.gz" not in daily_files
    # the malformed object itself is excluded from accounting, but left
    # completely untouched -- never a `deletefile` target
    assert "btcbot_29991301T030000Z.sql.gz" in daily_files
    assert malformed.read_bytes() == before
