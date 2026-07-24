"""Static validation of the shadow-forecast systemd deployment artifacts.

Reads and validates repository files only — requires no root, no VPS, no Docker,
no PostgreSQL, no network, and no installed system units. `systemctl` is NEVER
invoked; `systemd-analyze verify` is used only as an OPTIONAL syntax check when
the host utility is present (and its host-path diagnostics are tolerated).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
DOCS = ROOT / "docs"

SERVICE = DEPLOY / "signalbot-shadow.service"
TIMER = DEPLOY / "signalbot-shadow.timer"
INSTALL = DEPLOY / "install_shadow_timer.sh"
CHECK = DEPLOY / "check_shadow_timer.sh"
DOC = DOCS / "SHADOW_TIMER_DEPLOY.md"

EXPECTED_EXECSTART = (
    "/opt/signalbot/.venv/bin/python /opt/signalbot/main.py "
    "--shadow-once --shadow-json --shadow-reference-exchange binance --log-level INFO"
)
EXPECTED_EXECSTARTPRE = [
    "/usr/bin/test -x /opt/signalbot/.venv/bin/python",
    "/usr/bin/test -r /opt/signalbot/.env",
    "/usr/bin/test -f /opt/signalbot/main.py",
]
REQUIRED_HARDENING = {
    "ProtectSystem": "strict",
    "ProtectHome": "true",
    "PrivateTmp": "true",
    "NoNewPrivileges": "true",
    "ProtectKernelTunables": "true",
    "ProtectControlGroups": "true",
    "RestrictSUIDSGID": "true",
    "RestrictAddressFamilies": "AF_INET AF_INET6",
    "UMask": "0077",
}


def _parse_unit(text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse a systemd unit into {section: [(key, value), ...]} preserving
    duplicate keys (e.g. multiple ExecStartPre)."""
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
    """Non-comment directive lines of a unit (comments may legitimately describe
    what the unit avoids)."""
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))


def _shell_code(text: str) -> str:
    """Non-comment lines of a shell script (drops the shebang and `#` comments, so
    'this script never runs X' prose is not mistaken for running X)."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def _values(section: list[tuple[str, str]], key: str) -> list[str]:
    return [v for k, v in section if k == key]


def _one(section: list[tuple[str, str]], key: str) -> str:
    vals = _values(section, key)
    assert len(vals) == 1, f"expected exactly one {key}, got {vals}"
    return vals[0]


# ============================================================================
# A. service unit
# ============================================================================
def test_service_files_exist():
    for p in (SERVICE, TIMER, INSTALL, CHECK, DOC):
        assert p.is_file(), f"missing {p}"


def test_service_sections_and_no_install():
    unit = _parse_unit(SERVICE.read_text())
    assert set(unit) == {"Unit", "Service"}          # NO [Install]
    assert "Install" not in unit


def test_service_unit_ordering():
    unit = _parse_unit(SERVICE.read_text())["Unit"]
    after = _one(unit, "After")
    assert "network-online.target" in after and "docker.service" in after
    assert _one(unit, "Wants") == "network-online.target"
    # must NOT couple to the Stage 1 service (check directives, not comments)
    code = _unit_code(SERVICE.read_text())
    for coupling in ("Requires=", "Requisite=", "PartOf=", "BindsTo="):
        assert coupling not in code
    assert "signalbot.service" not in code            # no Stage 1 unit coupling


def test_service_core_contract():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    assert _one(svc, "Type") == "oneshot"
    assert _one(svc, "User") == "signalbot"
    assert _one(svc, "Group") == "signalbot"
    assert _one(svc, "WorkingDirectory") == "/opt/signalbot"
    assert _one(svc, "EnvironmentFile") == "/opt/signalbot/.env"
    assert _one(svc, "Environment") == "PYTHONDONTWRITEBYTECODE=1"


def test_service_execstartpre_exact_three():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    assert _values(svc, "ExecStartPre") == EXPECTED_EXECSTARTPRE


def test_service_execstart_exact():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    assert _one(svc, "ExecStart") == EXPECTED_EXECSTART


def test_service_execstart_flags():
    text = SERVICE.read_text()
    assert text.count("--shadow-once") == 1
    assert text.count("--shadow-json") == 1
    assert "--shadow-reference-exchange binance" in text
    # automatic bucket: no explicit timestamp
    assert "--shadow-bucket-ts" not in text
    # no outcome/recovery/redis flags
    execstart = _one(_parse_unit(text)["Service"], "ExecStart")
    for banned in ("--shadow-bucket-ts", "outcome", "recovery", "catch",
                   "watermark", "lock", "redis", "due"):
        assert banned.lower() not in execstart.lower()


def test_service_no_redis_anywhere():
    assert "redis" not in _unit_code(SERVICE.read_text()).lower()


def test_service_timeout_bounded():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    timeout = _one(svc, "TimeoutStartSec")
    assert timeout.isdigit()
    assert 0 < int(timeout) < 300


def test_service_no_restart_or_remain():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    keys = [k for k, _ in svc]
    assert not any(k.startswith("Restart") for k in keys)   # no Restart / RestartSec
    assert "RemainAfterExit" not in keys
    assert "ExecStartPost" not in keys
    assert "ExecReload" not in keys


def test_service_journal_output_and_identifier():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    assert _one(svc, "StandardOutput") == "journal"
    assert _one(svc, "StandardError") == "journal"
    assert _one(svc, "SyslogIdentifier") == "signalbot-shadow"


def test_service_hardening_directives():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    for key, expected in REQUIRED_HARDENING.items():
        assert _one(svc, key) == expected


def test_service_no_readwritepaths():
    assert "ReadWritePaths" not in _unit_code(SERVICE.read_text())


def test_service_exec_lines_have_no_shell_or_docker():
    svc = _parse_unit(SERVICE.read_text())["Service"]
    exec_values = _values(svc, "ExecStart") + _values(svc, "ExecStartPre")
    for v in exec_values:
        low = v.lower()
        for banned in ("/bin/sh", "/bin/bash", " bash ", "sh -c", "sudo", "docker"):
            assert banned not in low, f"{banned!r} in {v!r}"


# ============================================================================
# B. timer unit
# ============================================================================
def test_timer_sections_and_target():
    unit = _parse_unit(TIMER.read_text())
    assert set(unit) == {"Unit", "Timer", "Install"}
    assert _one(unit["Install"], "WantedBy") == "timers.target"


def test_timer_oncalendar_exact():
    timer = _parse_unit(TIMER.read_text())["Timer"]
    oncal = _one(timer, "OnCalendar")
    assert oncal == "*-*-* *:00/5:05 UTC"
    assert oncal.endswith("UTC")               # UTC
    assert ":00/5:" in oncal                   # five-minute step
    assert oncal.endswith(":05 UTC")           # second :05


def test_timer_alignment_directives():
    timer = _parse_unit(TIMER.read_text())["Timer"]
    assert _one(timer, "AccuracySec") == "1s"
    assert _one(timer, "RandomizedDelaySec") == "0"
    assert _one(timer, "Persistent") == "true"
    assert _one(timer, "Unit") == "signalbot-shadow.service"


def test_timer_no_relative_or_randomized_scheduling():
    keys = [k for k, _ in _parse_unit(TIMER.read_text())["Timer"]]
    for banned in ("OnBootSec", "OnStartupSec", "OnUnitActiveSec",
                   "OnUnitInactiveSec", "WakeSystem"):
        assert banned not in keys


# ============================================================================
# C. shell syntax
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


# ============================================================================
# D. installer safety (static)
# ============================================================================
def test_installer_requires_root():
    text = INSTALL.read_text()
    assert "EUID" in text and "-ne 0" in text


def test_installer_fixed_paths():
    text = INSTALL.read_text()
    assert "APP_DIR=/opt/signalbot" in text
    assert "UNIT_DIR=/etc/systemd/system" in text
    assert "SERVICE_NAME=signalbot-shadow.service" in text
    assert "TIMER_NAME=signalbot-shadow.timer" in text


def test_installer_validation_and_verify_before_install_and_enable():
    text = INSTALL.read_text()
    i_verify = text.index("systemd-analyze verify")
    i_install = text.index("install -o root")
    i_reload = text.index("systemctl daemon-reload")
    i_enable = text.index("systemctl enable --now")
    # source validation + verify happen before install; install/reload before enable
    assert i_verify < i_install < i_reload < i_enable
    # the source-file existence checks precede verify
    assert text.index('[[ -f "${SRC_SERVICE}" ]]') < i_verify


def test_installer_default_is_install_only():
    text = INSTALL.read_text()
    # exactly one enable, no service/timer start verb at all
    assert text.count("systemctl enable --now") == 1
    assert "systemctl start" not in text
    # enable is gated behind --enable-now
    assert "--enable-now" in text
    assert 'if [[ "${ENABLE_NOW}" -eq 1 ]]' in text
    # default branch prints the later activation command
    assert "install-only default" in text


def test_installer_enables_timer_not_service():
    text = INSTALL.read_text()
    assert 'systemctl enable --now "${TIMER_NAME}"' in text
    assert "enable --now signalbot-shadow.service" not in text
    assert 'enable --now "${SERVICE_NAME}"' not in text


def test_installer_no_dangerous_operations():
    code = _shell_code(INSTALL.read_text())         # code only, not the header comment
    for banned in ("shadow-once", "docker", "usermod", "useradd", "groupmod",
                   "groupadd", "chmod", "chown", "systemctl restart",
                   "systemctl stop", "psql", "migrate"):
        assert banned not in code, banned
    # never touches the Stage 1 unit
    assert "signalbot.service" not in code


def test_installer_installs_mode_0644():
    text = INSTALL.read_text()
    assert text.count("install -o root -g root -m 0644") == 2


# ============================================================================
# E. check-script safety (static, read-only)
# ============================================================================
def test_check_script_has_no_mutating_systemctl_verbs():
    code = _shell_code(CHECK.read_text())
    # is-enabled / is-active must NOT be read as enable/disable verbs.
    for verb in ("start", "stop", "restart", "enable", "disable",
                 "daemon-reload", "reset-failed", "kill", "edit", "mask", "unmask"):
        assert not re.search(rf"systemctl\s+{verb}\b", code), verb


def test_check_script_is_read_only_and_no_secrets():
    code = _shell_code(CHECK.read_text())            # code only, not the header comment
    for banned in ("docker", "shadow-once", "psql", "SELECT", "INSERT",
                   ".env", "printenv", "rm ", "cat "):
        assert banned not in code, banned


def test_check_script_only_inspection_commands():
    code = _shell_code(CHECK.read_text())
    # every systemctl call is an inspection verb
    for m in re.findall(r"systemctl\s+(\S+)", code):
        assert m in {"is-enabled", "is-active", "list-timers", "status", "show"}, m


# ============================================================================
# F. documentation
# ============================================================================
def test_doc_covers_required_sections():
    text = DOC.read_text()
    low = text.lower()
    # authoring boundary (no server needed)
    assert "no production deployment was performed during pr authoring" in low
    assert "no vps access" in low or "no server access" in low
    # manual status + dry-run before activation
    assert "--shadow-status" in text and "--shadow-dry-run" in text
    # install-only and explicit enable commands
    assert "install_shadow_timer.sh" in text
    assert "install_shadow_timer.sh --enable-now" in text
    # first-run warning
    assert "WARNING" in text and "REAL Stage 2 write" in text
    # journal + DB verification
    assert "journalctl -u signalbot-shadow.service" in text
    assert "forecast_predictions" in text
    # rollback
    assert "systemctl disable --now signalbot-shadow.timer" in text
    # limitations / deferrals
    assert "current limitations" in low
    assert "due_outcome_jobs" in text and "empty" in low
    assert "recovery" in low and ("catch-up" in low or "later" in low)


def test_doc_rollback_preserves_state():
    low = DOC.read_text().lower()
    assert "signalbot.service" in DOC.read_text()      # Stage 1 stays running
    assert "not** deleted" in low or "not deleted" in low
    assert ".env" in DOC.read_text()


# ============================================================================
# G. optional systemd-analyze syntax validation
# ============================================================================
def test_optional_systemd_analyze_verify():
    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze unavailable on this host; unit structure "
                    "tests remain authoritative")
    result = subprocess.run(
        [analyze, "verify", str(SERVICE), str(TIMER)],
        capture_output=True, text=True)
    # Tolerate ONLY host-path diagnostics: on the authoring machine /opt/signalbot
    # does not exist, so the ExecStart binary / EnvironmentFile cannot be resolved.
    # Any OTHER diagnostic indicates a genuine unit-syntax problem.
    offending = [
        ln for ln in result.stderr.splitlines()
        if ln.strip() and "/opt/signalbot" not in ln
    ]
    assert not offending, "systemd-analyze reported non-environmental issues:\n" + \
        "\n".join(offending)
