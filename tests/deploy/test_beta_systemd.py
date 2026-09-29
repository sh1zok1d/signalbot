"""Private beta V0.2 systemd artifacts: prepared (hardened, bounded) but never activated."""
import configparser
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
ONESHOTS = {"detector": "--beta-once", "outcomes": "--beta-outcomes-once", "notify": "--beta-notify-once"}
HARDENING = {"ProtectSystem": "strict", "ProtectHome": "true", "PrivateTmp": "true", "NoNewPrivileges": "true",
             "UMask": "0077"}


def _unit(name):
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read_string((DEPLOY / name).read_text())
    return cp


@pytest.mark.parametrize("name,flag", ONESHOTS.items())
def test_oneshot_services(name, flag):
    u = _unit(f"signalbot-beta-{name}.service")
    s = u["Service"]
    assert s["Type"] == "oneshot" and s["User"] == "signalbot"
    assert s["ExecStart"].endswith(f"main.py {flag} --beta-json --log-level INFO")
    assert "--shadow" not in s["ExecStart"] and "--telegram" not in s["ExecStart"]
    assert int(s["TimeoutStartSec"]) <= 300 and "Restart" not in s
    for k, v in HARDENING.items():
        assert s[k] == v
    assert "Install" not in u


@pytest.mark.parametrize("name", ONESHOTS)
def test_timers(name):
    t = _unit(f"signalbot-beta-{name}.timer")["Timer"]
    assert t["Unit"] == f"signalbot-beta-{name}.service"
    assert t["OnCalendar"].endswith("UTC") and t["Persistent"] == "true"


def test_bot_service():
    s = _unit("signalbot-beta-bot.service")["Service"]
    assert s["Type"] == "simple" and s["ExecStart"].endswith("-m runtime.beta_bot")
    assert s["Restart"] == "on-failure"
    for k, v in HARDENING.items():
        assert s[k] == v


def test_install_script_never_activates_and_check_script_is_read_only():
    install = (DEPLOY / "install_beta_units.sh").read_text()
    code = "\n".join(l for l in install.splitlines() if not l.strip().startswith(("#", "echo")))
    for verb in ("systemctl enable", "systemctl start", "systemctl restart", "--now"):
        assert verb not in code
    check = (DEPLOY / "check_beta_units.sh").read_text()
    code = "\n".join(l for l in check.splitlines() if not l.strip().startswith("#"))
    for verb in (" enable ", " start ", " stop ", " restart ", "daemon-reload", "--beta-once", "psql"):
        assert verb not in code
    for f in DEPLOY.glob("signalbot-beta-*"):
        assert "BETA_TELEGRAM_BOT_TOKEN=" not in f.read_text()


@pytest.mark.parametrize("name", ["detector", "outcomes"])
def test_detector_and_outcomes_wait_for_postgres_first(name):
    lines = [l.strip() for l in (DEPLOY / f"signalbot-beta-{name}.service").read_text().splitlines()]
    pre = [l for l in lines if l.startswith("ExecStartPre=")]
    gate = "ExecStartPre=/opt/signalbot/.venv/bin/python /opt/signalbot/deploy/wait_for_infra.py --postgres-only"
    assert any(l.startswith(gate) for l in pre)
    assert lines.index(next(l for l in pre if l.startswith(gate))) < lines.index(
        next(l for l in lines if l.startswith("ExecStart=")))
    timeout = int(next(l for l in pre if l.startswith(gate)).split("--timeout")[1].split()[0])
    assert timeout < int(_unit(f"signalbot-beta-{name}.service")["Service"]["TimeoutStartSec"])


def test_beta_units_reuse_the_single_readiness_script():
    for f in DEPLOY.glob("*.service"):
        for l in f.read_text().splitlines():
            if "wait_for" in l and not l.strip().startswith("#"):
                assert "/opt/signalbot/deploy/wait_for_infra.py" in l, (f.name, l)
    assert sorted(p.name for p in DEPLOY.glob("wait_for*")) == ["wait_for_infra.py"]
