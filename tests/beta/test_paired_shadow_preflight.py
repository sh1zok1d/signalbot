"""The host adapter refuses a bad input, and the connection string stays out of argv."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from beta.paired_shadow import plan_shadow_record
from beta.paired_shadow_host import judge_sources, overall, require_dsn, write_env_file
from beta.paired_shadow_pg import psql_invocation, redact_connection
from beta.rangecast_shadow import issue_live_record

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc
SECRET = "postgresql://role:s3cret-value@127.0.0.1:5432/shadow"


class _Snap:
    def __init__(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def test_a_missing_model_issues_nothing():
    record = issue_live_record(
        _Snap(), v1_state="missing", v1_model=None, v2_status="NO_SNAPSHOT",
        v2_reason="NO_SNAPSHOT_BUILT_BEFORE_ISSUE", v2_model=None,
    )
    assert record["status"] == "NO_MODEL" and record["price"] is None
    planned = plan_shadow_record(record, issue_slot=_Snap().now)
    assert planned["rows"] == []


def test_a_stale_v1_row_is_not_issued():
    record = issue_live_record(
        _Snap(), v1_state="stale", v1_model={"horizons": {}}, v2_status="OK",
        v2_reason=None, v2_model={"level": "L1"},
    )
    assert record["status"] == "STALE_DATA" and record["reason"] == "V1_STATS_STALE"
    assert plan_shadow_record(record, issue_slot=_Snap().now)["rows"] == []


def test_psql_keeps_the_password_out_of_argv():
    argv, env = psql_invocation(SECRET)
    assert "s3cret-value" not in argv
    assert all("://" not in arg for arg in argv)
    assert env["PGPASSWORD"] == "s3cret-value"
    assert env["PGUSER"] == "role" and env["PGDATABASE"] == "shadow"
    cleaned = redact_connection(f"connection to {SECRET} failed for s3cret-value", SECRET)
    assert "s3cret-value" not in cleaned and SECRET not in cleaned


def test_env_file_is_private_and_the_summary_has_no_secret(tmp_path):
    info = write_env_file(tmp_path / "paired.env", SECRET)
    assert "s3cret-value" not in json.dumps(info)
    path = tmp_path / "paired.env"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert f'PAIRED_SHADOW_DSN="{SECRET}"\n' == path.read_text(encoding="utf-8")


def test_a_url_argument_is_refused_without_echoing_it(capsys):
    with pytest.raises(SystemExit) as caught:
        require_dsn([SECRET])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert "s3cret-value" not in captured.err
    assert "argument" in captured.err


def _preflight_module():
    spec = importlib.util.spec_from_file_location(
        "paired_shadow_preflight", ROOT / "scripts/beta/paired_shadow_preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_scheduler_states_are_not_ready(monkeypatch):
    module = _preflight_module()
    monkeypatch.setattr(module, "_systemctl_show", lambda unit: {"UnitFileState": ""})
    report = module._schedulers()
    assert report["status"] == "NOT_READY"
    assert report["reason"] == "SYSTEMCTL_UNAVAILABLE"


def test_a_disabled_paired_timer_is_not_already_enabled(monkeypatch):
    module = _preflight_module()

    def show(unit):
        if unit.startswith("signalbot-paired-shadow-"):
            return {"UnitFileState": "disabled"}
        return {"UnitFileState": "enabled"}

    monkeypatch.setattr(module, "_systemctl_show", show)
    report = module._schedulers()
    assert report["status"] == "PASS" and report["reason"] is None


def test_source_and_overall_verdicts():
    assert judge_sources({"status": "PASS", "hist_bars": 10, "stats_built_at": "t",
                          "stats_stale": False, "hist_age_h": 1, "live_age_min": 2})["status"] == "PASS"
    assert judge_sources({"status": "PASS", "hist_bars": 0, "stats_built_at": None,
                          "stats_stale": True, "hist_age_h": None, "live_age_min": None})["status"] == "NOT_READY"
    assert overall({"a": {"status": "PASS"}, "b": {"status": "NOT_READY"}}) == "NOT_READY"
    assert overall({"a": {"status": "PASS"}, "b": {"status": "FAIL"}}) == "FAIL"


def test_writer_refuses_a_url_argument(tmp_path):
    record = tmp_path / "record.json"
    record.write_text("{}", encoding="utf-8")
    env = os.environ.copy()
    env["PAIRED_SHADOW_HOUR_APPROVED"] = "1"
    env["PAIRED_SHADOW_DSN"] = "postgresql:///signalbot_shadow_writer"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/run_paired_shadow_hour.py"), "--write", str(record), SECRET],
        capture_output=True, text=True, check=False, env=env,
    )
    assert completed.returncode == 2
    assert "s3cret-value" not in completed.stdout
    assert "s3cret-value" not in completed.stderr
