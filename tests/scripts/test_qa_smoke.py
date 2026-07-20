"""Unit test for the QA smoke test's fail-closed Redis-target guard.

Only the pure `_redis_target_ok` helper is exercised — no Docker, no DB, no Redis
connection. The smoke script lives at scripts/qa-smoke.py (a hyphenated,
non-importable filename), so it is loaded by path via importlib.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SMOKE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "qa-smoke.py"


def _load_smoke():
    spec = importlib.util.spec_from_file_location("qa_smoke_under_test", _SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qa_smoke = _load_smoke()


@pytest.mark.parametrize("url", [
    "redis://127.0.0.1:6380/0",
    "redis://127.0.0.1:6380/1",
    "redis://:secret@127.0.0.1:6380/0",   # credentials present but host/port ok
])
def test_redis_target_ok_accepts_test_instance(url):
    assert qa_smoke._redis_target_ok(url) is True


@pytest.mark.parametrize("url", [
    "redis://127.0.0.1:6379/0",   # production port
    "redis://10.0.0.5:6380/0",    # non-loopback host
    "redis://redis.example.com:6380/0",
    "redis://127.0.0.1/0",        # no port -> None
])
def test_redis_target_ok_rejects_non_test_instance(url):
    assert qa_smoke._redis_target_ok(url) is False
