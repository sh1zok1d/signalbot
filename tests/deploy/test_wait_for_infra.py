"""deploy/wait_for_infra.py: default checks PostgreSQL then Redis; --postgres-only skips Redis."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[2] / "deploy/wait_for_infra.py"


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location("wait_for_infra_under_test", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []

    async def pg(dsn, timeout):
        calls.append(("pg", timeout))

    async def rd(url, timeout):
        calls.append(("redis", timeout))
    monkeypatch.setattr(mod, "_wait_pg", pg)
    monkeypatch.setattr(mod, "_wait_redis", rd)
    monkeypatch.setattr(mod, "load_secrets", lambda cfg: SimpleNamespace(postgres_dsn="x", redis_url="y"))
    monkeypatch.setattr(mod.Config, "load", staticmethod(lambda *a, **k: None))
    return mod, calls


@pytest.mark.parametrize("argv,expected", [
    ([], [("pg", 90.0), ("redis", 90.0)]),
    (["--postgres-only", "--timeout", "60"], [("pg", 60.0)]),
])
def test_readiness_modes(monkeypatch, argv, expected):
    mod, calls = _load(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["wait_for_infra.py", *argv])
    asyncio.run(mod.main())
    assert calls == expected
