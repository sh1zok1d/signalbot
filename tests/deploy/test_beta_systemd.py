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


# ---- research evidence feed units (docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md §A/§C, PREREQ-3) ----------
FEED_UNITS = {"signalbot-beta-feeds.service": "--beta-feeds-once", "signalbot-beta-stress.service": "--beta-stress-once"}
CORE_UNITS = ("signalbot.service", "signalbot-telegram.service", "signalbot-shadow.service",
              "signalbot-beta-bot.service", "signalbot-beta-detector.service", "signalbot-beta-outcomes.service",
              "signalbot-beta-notify.service", "signalbot-beta-d7.service", "signalbot-beta-history.service")


def _directives(name):
    """[(key, value)] of a unit, every repeated key kept (configparser keeps only the last one)."""
    out = []
    for line in (DEPLOY / name).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "[")) and "=" in line:
            k, v = line.split("=", 1)
            out.append((k.strip(), v.strip()))
    return out


@pytest.mark.parametrize("name,flag", FEED_UNITS.items())
def test_feed_units_read_only_the_feed_env_file_and_never_the_core_env(name, flag):
    d = _directives(name)
    get = lambda k: [v for kk, v in d if kk == k]                       # noqa: E731
    assert get("EnvironmentFile") == ["/opt/signalbot/.env.beta-feeds"]  # no "-": a missing file fails the unit
    env = dict(v.split("=", 1) for v in get("Environment"))
    assert env["SIGNALBOT_DOTENV"] == "0"                                # the shared .env is never loaded
    assert env["BETA_FEEDS_EXPECTED_DB_ROLE"] == "signalbot_beta_feeds"
    assert env["REDIS_URL"].startswith("redis://unused.invalid")         # placeholder; beta commands never use Redis
    assert not {"POSTGRES_PASSWORD", "POSTGRES_DSN", "TELEGRAM_BOT_TOKEN", "BETA_TELEGRAM_BOT_TOKEN",
                "BETA_OWNER_TELEGRAM_USER_ID", "BETA_PUSH_ENABLED"} & set(env)
    assert "-/opt/signalbot/.env" in get("InaccessiblePaths")
    assert not any("/opt/signalbot/.env " in v + " " for v in get("ExecStartPre"))
    assert get("ExecStart") == [f"/opt/signalbot/.venv/bin/python /opt/signalbot/main.py {flag} --beta-json "
                                "--log-level INFO"]
    s = _unit(name)["Service"]
    assert s["Type"] == "oneshot" and s["User"] == "signalbot" and "Restart" not in s
    for k, v in HARDENING.items():
        assert s[k] == v
    u = _unit(name)
    assert "Install" not in u                                            # the timer owns activation
    for k in ("Requires", "BindsTo", "PartOf", "Requisite", "OnFailure"):
        assert not get(k), (name, k)
    assert get("Wants") == ["network-online.target"]


def test_no_core_unit_depends_on_the_research_feeds():
    for name in CORE_UNITS:
        text = (DEPLOY / name).read_text()
        assert "signalbot-beta-feeds" not in text and "signalbot-beta-stress" not in text, name
    for t in ("signalbot-beta-feeds.timer", "signalbot-beta-stress.timer"):
        tm = _unit(t)
        assert tm["Install"]["WantedBy"] == "timers.target" and tm["Timer"]["Persistent"] == "true"


def test_feed_role_sql_grants_exactly_what_the_jobs_verify_and_holds_no_secret():
    import re
    from beta.research_feeds import FEED_JOB_COLUMN_READS, FEED_JOB_GRANTS
    sql = (DEPLOY / "beta_feeds_role.sql").read_text()
    code = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    assert "PASSWORD" not in code.upper()                                # set from stdin by the install script
    assert "SUPERUSER" not in code.upper().replace("NOSUPERUSER", "")
    assert "CONNECTION LIMIT 4" in code and "statement_timeout = '60s'" in code
    granted: dict = {}
    for privs, cols, tables in re.findall(r"GRANT ([A-Z, ]+?)(?: \(([^)]*)\))? ON ([a-z0-9_, \n]+?)\s+TO signalbot_beta_feeds",
                                          code):
        for t in (x.strip() for x in tables.split(",")):
            if cols:
                granted[(t, "COLUMNS")] = tuple(c.strip() for c in cols.split(","))
            else:
                granted.setdefault(t, set()).update(p.strip() for p in privs.split(","))
    want: dict = {}
    for job in FEED_JOB_GRANTS.values():
        for t, ps in job.items():
            want.setdefault(t, set()).update(ps)
    assert {k: v for k, v in granted.items() if isinstance(k, str)} == want
    assert granted[("beta_hist_oi_5m", "COLUMNS")] == FEED_JOB_COLUMN_READS["feeds"]["beta_hist_oi_5m"]
    for word in ("DELETE", "TRUNCATE", "CREATE ON", "ALL PRIVILEGES"):
        assert not re.search(rf"GRANT[^;]*{word}", code), word


def test_feed_role_install_script_never_activates_and_never_exposes_the_password():
    script = (DEPLOY / "install_beta_feeds_role.sh").read_text()
    code = "\n".join(l for l in script.splitlines() if not l.strip().startswith("#"))
    for verb in ("systemctl", "--now", "set -x"):
        assert verb not in code
    assert "openssl rand -hex 24" in code
    assert "printf \"ALTER ROLE %s PASSWORD '%s';\\n\"" in code and "| psql_su" in code      # stdin only
    # the password is echoed only into the private env file (the block redirected to the temp file)
    lines = code.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "{")
    end = next(i for i, l in enumerate(lines) if l.strip() == '} > "${tmp}"')
    outside = lines[:start] + lines[end + 1:]
    assert not any("${pw}" in l for l in outside if "printf" not in l and "pw=$(" not in l)
    assert "chmod 0600" in code and "chown root:root" in code
    assert ". \"${ENV_CORE}\"" not in code and "source " not in code                        # core .env never sourced
    example = (DEPLOY / "beta-feeds.env.example").read_text()
    keys = {l.split("=", 1)[0] for l in example.splitlines() if l and not l.startswith("#")}
    assert keys == {"POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
                    "BETA_ENABLED"}


def test_the_shared_env_file_is_not_loaded_when_a_unit_says_so():
    import subprocess
    import sys
    probe = ("import dotenv; calls = []; dotenv.load_dotenv = lambda *a, **k: calls.append(a); "
             "import common.config; print(len(calls))")
    root = Path(__file__).resolve().parents[2]
    for value, expected in (("0", "0"), ("", "1"), ("1", "1")):
        env = {k: v for k, v in __import__("os").environ.items() if k != "SIGNALBOT_DOTENV"}
        if value:
            env["SIGNALBOT_DOTENV"] = value
        out = subprocess.run([sys.executable, "-c", probe], cwd=root, env=env, capture_output=True, text=True,
                             timeout=60)
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == expected, (value, out.stdout)
