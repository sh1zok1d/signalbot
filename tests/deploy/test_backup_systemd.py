"""Static validation of the INFRA-D1 backup + restore-verify systemd
deployment artifacts (deploy/signalbot-backup*, deploy/*_backup_timer.sh).

Reads and validates repository files only — requires no root, no VPS, no
Docker, no PostgreSQL, no network, and no installed system units.
`systemctl` is NEVER invoked; `systemd-analyze verify` is used only as an
OPTIONAL syntax check when the host utility is present (and its host-path
diagnostics are tolerated), following the same pattern as
tests/deploy/test_shadow_systemd.py.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
DOCS = ROOT / "docs"

BACKUP_SERVICE = DEPLOY / "signalbot-backup.service"
BACKUP_TIMER = DEPLOY / "signalbot-backup.timer"
VERIFY_SERVICE = DEPLOY / "signalbot-backup-verify.service"
VERIFY_TIMER = DEPLOY / "signalbot-backup-verify.timer"
INSTALL = DEPLOY / "install_backup_timer.sh"
CHECK = DEPLOY / "check_backup_timer.sh"
DOC = DOCS / "DATA_DURABILITY_RUNBOOK.md"

ALL_UNITS = [BACKUP_SERVICE, BACKUP_TIMER, VERIFY_SERVICE, VERIFY_TIMER]


def _parse_unit(text: str) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections.setdefault(current, [])
            continue
        if "=" in line and current is not None:
            key, _, val = line.partition("=")
            sections[current].append((key.strip(), val.strip()))
    return sections


def _unit_code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))


def _shell_code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def _values(section: list[tuple[str, str]], key: str) -> list[str]:
    return [v for k, v in section if k == key]


def _one(section: list[tuple[str, str]], key: str) -> str:
    vals = _values(section, key)
    assert len(vals) == 1, f"expected exactly one {key}, got {vals}"
    return vals[0]


# ============================================================================
# A. files exist
# ============================================================================
def test_backup_files_exist():
    for p in ALL_UNITS + [INSTALL, CHECK, DOC, DEPLOY / "sync_backup_offsite.sh"]:
        assert p.is_file(), f"missing {p}"


# ============================================================================
# B. signalbot-backup.service
# ============================================================================
def test_backup_service_sections_and_no_install():
    unit = _parse_unit(BACKUP_SERVICE.read_text())
    assert set(unit) == {"Unit", "Service"}
    assert "Install" not in unit


def test_backup_service_runs_as_root_with_docker_access_documented():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    # Root, NOT the unprivileged signalbot user (that user has no docker access).
    assert _one(svc, "User") == "root"
    assert "Group" not in [k for k, _ in svc]  # no explicit Group override needed for root
    text = BACKUP_SERVICE.read_text()
    assert "docker exec" in text.lower() or "docker" in text.lower()  # documented rationale


def test_backup_service_two_execstart_local_then_offsite():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    starts = _values(svc, "ExecStart")
    assert starts == [
        "/opt/signalbot/deploy/backup.sh",
        "/opt/signalbot/deploy/sync_backup_offsite.sh",
    ], "local dump must run before off-site sync so a failed local dump blocks the sync"


def test_backup_service_execstartpre_checks_both_scripts():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    pre = _values(svc, "ExecStartPre")
    assert "/usr/bin/test -x /opt/signalbot/deploy/backup.sh" in pre
    assert "/usr/bin/test -x /opt/signalbot/deploy/sync_backup_offsite.sh" in pre


def test_backup_service_environment_files():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    env_files = _values(svc, "EnvironmentFile")
    assert "/opt/signalbot/.env" in env_files
    assert "/etc/signalbot/backup.env" in env_files
    # the admin-only remote/retention config must NOT live inside the repo checkout
    for f in env_files:
        assert not f.startswith("/opt/signalbot/deploy/")


def test_backup_service_no_secret_literal_in_unit_source():
    # code only, not the header prose explaining that no secret lives here
    code = _unit_code(BACKUP_SERVICE.read_text()).lower()
    for banned in ("oauth", "token=", "api_key", "apikey", "client_secret"):
        assert banned not in code


def test_backup_service_readwritepaths_scoped_to_backups_dir():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    assert _one(svc, "ReadWritePaths") == "/opt/signalbot/backups"


def test_backup_service_no_restart_or_remain():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    keys = [k for k, _ in svc]
    assert not any(k.startswith("Restart") for k in keys)
    assert "RemainAfterExit" not in keys


def test_backup_service_journal_identifier():
    svc = _parse_unit(BACKUP_SERVICE.read_text())["Service"]
    assert _one(svc, "SyslogIdentifier") == "signalbot-backup"


# ============================================================================
# C. signalbot-backup-verify.service
# ============================================================================
def test_verify_service_sections_and_no_install():
    unit = _parse_unit(VERIFY_SERVICE.read_text())
    assert set(unit) == {"Unit", "Service"}
    assert "Install" not in unit


def test_verify_service_runs_as_root():
    svc = _parse_unit(VERIFY_SERVICE.read_text())["Service"]
    assert _one(svc, "User") == "root"


def test_verify_service_reuses_restore_self_test_only():
    svc = _parse_unit(VERIFY_SERVICE.read_text())["Service"]
    starts = _values(svc, "ExecStart")
    assert starts == ["/opt/signalbot/deploy/restore.sh --self-test"]
    # no second/competing restore implementation, no --force-live in a real
    # directive (code only -- the header prose explicitly documents its
    # absence, which would otherwise trip a naive substring check)
    code = _unit_code(VERIFY_SERVICE.read_text())
    assert "--force-live" not in code


def test_verify_service_never_force_live():
    code = _unit_code(VERIFY_SERVICE.read_text())
    assert "force-live" not in code.lower()


def test_verify_service_journal_identifier():
    svc = _parse_unit(VERIFY_SERVICE.read_text())["Service"]
    assert _one(svc, "SyslogIdentifier") == "signalbot-backup-verify"


# ============================================================================
# D. timers
# ============================================================================
def test_backup_timer_daily_utc_persistent():
    timer = _parse_unit(BACKUP_TIMER.read_text())["Timer"]
    oncal = _one(timer, "OnCalendar")
    assert oncal.endswith("UTC")
    assert oncal.startswith("*-*-*")           # every day
    assert _one(timer, "Persistent") == "true"
    assert _one(timer, "Unit") == "signalbot-backup.service"
    assert _one(_parse_unit(BACKUP_TIMER.read_text())["Install"], "WantedBy") == "timers.target"


def test_verify_timer_monthly_utc_persistent():
    timer = _parse_unit(VERIFY_TIMER.read_text())["Timer"]
    oncal = _one(timer, "OnCalendar")
    assert oncal.endswith("UTC")
    assert "-01 " in oncal or oncal.split()[0].endswith("-01")   # 1st of the month
    assert _one(timer, "Persistent") == "true"
    assert _one(timer, "Unit") == "signalbot-backup-verify.service"


def test_timers_no_relative_or_randomized_scheduling():
    for timer_file in (BACKUP_TIMER, VERIFY_TIMER):
        keys = [k for k, _ in _parse_unit(timer_file.read_text())["Timer"]]
        for banned in ("OnBootSec", "OnStartupSec", "OnUnitActiveSec",
                       "OnUnitInactiveSec", "WakeSystem"):
            assert banned not in keys, f"{banned} in {timer_file.name}"


# ============================================================================
# E. shell syntax + safety (installer/checker)
# ============================================================================
@pytest.mark.parametrize("script", [INSTALL, CHECK])
def test_shell_scripts_parse(script):
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", [INSTALL, CHECK])
def test_shell_scripts_strict_mode(script):
    text = script.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


def test_installer_requires_root():
    text = INSTALL.read_text()
    assert "EUID" in text and "-ne 0" in text


def test_installer_default_is_install_only():
    text = INSTALL.read_text()
    assert "systemctl start" not in text
    assert "--enable-now" in text
    assert 'if [[ "${ENABLE_NOW}" -eq 1 ]]' in text
    assert "install-only default" in text


def test_installer_never_runs_backup_or_restore_or_docker():
    code = _shell_code(INSTALL.read_text())
    for banned in ("docker", "backup.sh\n", "restore.sh --self-test", "psql",
                   "usermod", "useradd", "groupmod", "groupadd"):
        assert banned not in code


def test_installer_checks_backup_env_before_install():
    text = INSTALL.read_text()
    assert "/etc/signalbot/backup.env" in text
    i_check = text.index('[[ -r "${BACKUP_ENV_FILE}" ]]')
    i_install = text.index("install -o root -g root -m 0644")
    assert i_check < i_install


def test_installer_installs_all_four_units_mode_0644():
    text = INSTALL.read_text()
    assert text.count("install -o root -g root -m 0644") == 1  # one loop, not four literal lines
    assert "signalbot-backup.service" in text
    assert "signalbot-backup.timer" in text
    assert "signalbot-backup-verify.service" in text
    assert "signalbot-backup-verify.timer" in text


def test_check_script_has_no_mutating_systemctl_verbs():
    import re
    code = _shell_code(CHECK.read_text())
    for verb in ("start", "stop", "restart", "enable", "disable",
                 "daemon-reload", "reset-failed", "kill", "edit", "mask", "unmask"):
        assert not re.search(rf"systemctl\s+{verb}\b", code), verb


def test_check_script_is_read_only_and_no_secrets():
    code = _shell_code(CHECK.read_text())
    for banned in ("docker", "backup.sh", "restore.sh", "psql", "SELECT", "INSERT",
                   ".env", "backup.env", "printenv", "rm ", "cat "):
        assert banned not in code, banned


def test_check_script_covers_all_four_units():
    text = CHECK.read_text()
    for u in ("signalbot-backup.service", "signalbot-backup.timer",
              "signalbot-backup-verify.service", "signalbot-backup-verify.timer"):
        assert u in text


# ============================================================================
# F. repository executable modes
# ============================================================================
def _git_mode(path: Path) -> str:
    rel = str(path.relative_to(ROOT))
    out = subprocess.run(["git", "ls-files", "-s", "--", rel],
                          cwd=ROOT, capture_output=True, text=True).stdout
    assert out.strip(), f"{rel} is not tracked by git"
    return out.split()[0]


def test_shell_scripts_are_git_executable():
    assert _git_mode(INSTALL) == "100755"
    assert _git_mode(CHECK) == "100755"
    assert _git_mode(DEPLOY / "sync_backup_offsite.sh") == "100755"


def test_unit_files_are_not_executable():
    for u in ALL_UNITS:
        assert _git_mode(u) == "100644"


# ============================================================================
# G. optional systemd-analyze syntax validation
# ============================================================================
_MISSING_HOST_PATHS = (
    "/opt/signalbot/deploy/backup.sh",
    "/opt/signalbot/deploy/sync_backup_offsite.sh",
    "/opt/signalbot/deploy/restore.sh",
)


def accept_systemd_analyze(returncode: int, stderr: str) -> bool:
    diagnostics = [ln for ln in stderr.splitlines() if ln.strip()]
    if not diagnostics:
        return returncode == 0
    if returncode == 0:
        return False
    return all(any(p in ln for p in _MISSING_HOST_PATHS) for ln in diagnostics)


def test_optional_systemd_analyze_verify():
    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze unavailable on this host; unit structure tests remain authoritative")
    result = subprocess.run(
        [analyze, "verify", *[str(u) for u in ALL_UNITS]],
        capture_output=True, text=True)
    assert accept_systemd_analyze(result.returncode, result.stderr), (
        f"systemd-analyze verify rc={result.returncode} stderr:\n{result.stderr}")
