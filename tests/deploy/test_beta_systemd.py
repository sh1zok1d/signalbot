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
