"""The paired-shadow readiness check uses PAIRED_SHADOW_DSN and never the core .env."""
from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "deploy/wait_for_paired_shadow.py"
SECRET = "postgresql://role:s3cret-value@127.0.0.1:1/shadow"
PEER = "postgresql:///signalbot_calibration_export"


def _load():
    spec = importlib.util.spec_from_file_location("wait_for_paired_shadow_under_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_script_does_not_load_the_core_config():
    text = PATH.read_text(encoding="utf-8")
    for forbidden in ("load_secrets", "common.config", "load_dotenv", "POSTGRES_PASSWORD", "POSTGRES_DSN"):
        assert forbidden not in text


def test_a_ready_database_is_the_paired_shadow_dsn(monkeypatch):
    module = _load()
    seen = []

    class _Conn:
        async def execute(self, sql):
            seen.append(sql)

        async def close(self):
            seen.append("close")

    async def connect(dsn, timeout):
        seen.append((dsn, timeout))
        return _Conn()

    monkeypatch.setattr(module.asyncpg, "connect", connect)
    monkeypatch.setenv("PAIRED_SHADOW_DSN", SECRET)
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://core:other-secret@127.0.0.1/core")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    asyncio.run(module.wait_for_paired_shadow(module.require_dsn([]), 60))
    assert seen[0] == (SECRET, 5)
    assert "SELECT 1" in seen


def test_a_failed_connection_is_retried_and_does_not_print_the_secret(monkeypatch, capsys):
    module = _load()
    attempts = {"n": 0}

    async def connect(dsn, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError(f"password authentication failed for {dsn}")
        class _Conn:
            async def execute(self, sql):
                return sql

            async def close(self):
                return None
        return _Conn()

    async def sleep(_seconds):
        return None

    monkeypatch.setattr(module.asyncpg, "connect", connect)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    asyncio.run(module.wait_for_paired_shadow(SECRET, 30))
    assert attempts["n"] == 3
    captured = capsys.readouterr()
    assert "s3cret-value" not in captured.out
    assert "s3cret-value" not in captured.err
    assert "postgresql://" not in captured.out + captured.err


def test_a_deadline_prints_the_exception_class_only(monkeypatch, capsys):
    module = _load()

    async def connect(dsn, timeout):
        raise RuntimeError(f"could not connect to {dsn} with s3cret-value")

    monkeypatch.setattr(module.asyncpg, "connect", connect)
    with pytest.raises(SystemExit) as caught:
        asyncio.run(module.wait_for_paired_shadow(SECRET, 0))
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "s3cret-value" not in captured.err
    assert "postgresql://" not in captured.err
    assert SECRET not in captured.out + captured.err


def test_a_url_argument_is_refused_without_printing_it(monkeypatch, capsys):
    module = _load()
    monkeypatch.setenv("PAIRED_SHADOW_DSN", SECRET)
    with pytest.raises(SystemExit) as caught:
        module.main([SECRET, "--timeout", "1"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert "s3cret-value" not in blob
    assert "postgresql://" not in blob
    assert "refusing: a database URL was passed as an argument" in captured.err


def test_a_missing_dsn_exits_before_connecting(monkeypatch, capsys):
    module = _load()
    monkeypatch.delenv("PAIRED_SHADOW_DSN", raising=False)
    with pytest.raises(SystemExit) as caught:
        module.main([])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert "PAIRED_SHADOW_DSN is not set" in captured.err
    assert "s3cret-value" not in captured.err


def _peer_available() -> bool:
    probe = subprocess.run(
        ["psql", PEER, "-X", "-q", "-c", "SELECT 1"],
        capture_output=True, text=True, check=False,
    )
    return probe.returncode == 0


@pytest.mark.skipif(not _peer_available(), reason="local peer PostgreSQL is not available")
def test_a_real_select_succeeds_without_the_core_password():
    env = {key: value for key, value in os.environ.items() if not key.startswith("POSTGRES")}
    env["PAIRED_SHADOW_DSN"] = PEER
    env["SIGNALBOT_DOTENV"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(PATH), "--timeout", "10"],
        capture_output=True, text=True, check=False, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "SELECT 1 ok" in completed.stdout
    assert "postgresql://" not in completed.stdout + completed.stderr
    assert PEER not in completed.stdout + completed.stderr


def test_a_refused_connection_does_not_echo_the_url():
    env = {key: value for key, value in os.environ.items() if not key.startswith("POSTGRES")}
    env["PAIRED_SHADOW_DSN"] = SECRET
    env["SIGNALBOT_DOTENV"] = "0"
    completed = subprocess.run(
        [sys.executable, str(PATH), "--timeout", "0"],
        capture_output=True, text=True, check=False, env=env,
    )
    assert completed.returncode == 1
    assert "s3cret-value" not in completed.stdout
    assert "s3cret-value" not in completed.stderr
    assert "postgresql://" not in completed.stdout + completed.stderr
