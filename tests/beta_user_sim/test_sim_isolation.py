"""Dependency isolation, no real side effects, and private-beta metric isolation (§2, §17, §18, §20.4/5/10/11)."""
import ast
import asyncio
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sim_helpers import CFG, run
from tools.beta_user_sim import llm
from tools.beta_user_sim.sandbox import SIM_SWITCHES, SIM_TELEGRAM_USER_ID, SandboxStore, sandbox_handler

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "tools" / "beta_user_sim"
PRODUCTION_DIRS = ("beta", "runtime", "storage", "scripts", "common", "analytics", "notifications", "audit",
                   "symbols", "deploy", "config")


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(("." * n.level) + n.module)
        elif isinstance(n, ast.ImportFrom):
            mods.add("." * n.level)
        elif isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
    return mods


def _production_py_files():
    files = [REPO / "main.py"]
    for d in PRODUCTION_DIRS:
        files += sorted((REPO / d).rglob("*.py"))
    return [f for f in files if f.exists()]


def test_no_production_module_imports_the_harness():
    files = _production_py_files()
    assert len(files) > 50
    for f in files:
        for m in _imports(f):
            assert m != "tools" and not m.startswith("tools."), f"{f.relative_to(REPO)} imports {m}"
        text = f.read_text(encoding="utf-8")
        assert "beta_user_sim" not in text, f"{f.relative_to(REPO)} names the harness"


def test_harness_imports_no_storage_network_telegram_or_research_code():
    banned = ("storage", "telegram", "openai", "httpx", "requests", "aiohttp", "scripts", "research",
              "notifications", "runtime.beta_cli", "runtime.beta_notifier", "beta.delivery", "beta.admin")
    for f in sorted(HARNESS.glob("*.py")):
        for m in _imports(f):
            if f.name == "__main__.py" and m == "asyncpg":
                continue                      # read-only exporter connection, only for `export`
            assert not any(m == b or m.startswith(b + ".") for b in banned), f"{f.name} imports {m}"


def test_only_the_cli_export_path_can_open_a_database_connection():
    for f in sorted(HARNESS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        if "asyncpg" in src:
            assert f.name in ("__main__.py", "export.py"), f.name
    export_src = (HARNESS / "export.py").read_text(encoding="utf-8")
    assert "readonly=True" in export_src and "default_transaction_read_only" in export_src


def test_sandbox_participant_cannot_exist_in_production_tables():
    schema = (REPO / "storage" / "beta_v0_schema.sql").read_text(encoding="utf-8")
    assert "telegram_user_id  BIGINT PRIMARY KEY CHECK (telegram_user_id > 0)" in schema
    assert "telegram_user_id     BIGINT NOT NULL UNIQUE CHECK (telegram_user_id > 0)" in schema
    assert SIM_TELEGRAM_USER_ID < 0


def test_sandbox_handler_has_no_owner_no_telemetry_salt_and_hard_push_switch_only():
    from tools.beta_user_sim.bundle import bundle_from_dict
    from sim_helpers import raw_bundle
    b = bundle_from_dict(raw_bundle())
    h = sandbox_handler(SandboxStore(b, CFG, start=datetime(2024, 3, 4, tzinfo=timezone.utc)), CFG)
    assert h.owner is None and h._salt() is None
    assert SIM_SWITCHES.push_hard is True


def test_full_replay_has_no_real_side_effects(monkeypatch):
    """Any socket, PostgreSQL, Telegram or production-store access fails the run."""
    def boom(*a, **k):
        raise AssertionError("real side effect attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    import asyncpg
    monkeypatch.setattr(asyncpg, "connect", boom)
    monkeypatch.setattr(asyncpg, "create_pool", boom)
    from runtime import beta_bot
    for name in ("send", "edit", "answer", "get_updates", "get_me"):
        monkeypatch.setattr(beta_bot.BetaTelegramSender, name, boom)
    from storage import beta_v0_store
    monkeypatch.setattr(beta_v0_store.BetaStore, "connect", boom)
    monkeypatch.setattr(beta_v0_store.BetaStore, "advisory_lock", boom)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    e, r = run()
    assert r["role_b"]["audits"] and r["transcript"]


def test_synthetic_activity_stays_in_the_sandbox_and_out_of_usage_reports():
    from beta.usage import build_usage_report
    real_facts = {"users": [{"user_pk": 1, "telegram_user_id": 501, "status": "ACTIVE", "lang": "ru",
                             "joined_at": datetime(2024, 3, 1, tzinfo=timezone.utc), "invite_code": None}],
                  "activity": [{"user_pk": 1, "action": "cmd_btc",
                                "at": datetime(2024, 3, 4, 9, tzinfo=timezone.utc)}],
                  "invites": [], "deletions": [], "rejected_hashes": [], "rejected_counts": [], "waitlist_size": 0}
    now = datetime(2024, 3, 5, tzinfo=timezone.utc)
    before = build_usage_report(real_facts, now=now, owner_user_id=None)
    e, r = run()
    assert r["sandbox"]["activity_rows"] > 0                  # the sandbox did record synthetic activity
    assert build_usage_report(real_facts, now=now, owner_user_id=None) == before
    assert all(a["user_pk"] == 1 for a in real_facts["activity"])
    assert set(e.store.users) == {SIM_TELEGRAM_USER_ID}       # the only participant the sandbox ever saw


def test_real_model_cannot_be_constructed_without_explicit_network_authorization(monkeypatch):
    monkeypatch.delenv("SIGNALBOT_SIM_ALLOW_NETWORK", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    with pytest.raises(llm.NetworkNotAuthorized):
        llm.build_models("openai", model_id="gpt-x")
    with pytest.raises(llm.NetworkNotAuthorized):
        llm.build_models("openai", model_id="gpt-x", allow_network=True)
    monkeypatch.setenv("SIGNALBOT_SIM_ALLOW_NETWORK", "1")
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(llm.NetworkNotAuthorized):
        llm.build_models("openai", model_id="gpt-x", allow_network=True)
    with pytest.raises(llm.NetworkNotAuthorized):
        llm.build_models("openai", model_id="gpt-x")


def test_fake_models_report_no_network():
    for m in llm.build_models("fake").values():
        assert m.settings()["network"] is False


# ---- PostgreSQL: the negative synthetic id is structurally rejected -------------------------------
from beta_fakes_path import TEST_DSN, fresh_pool  # noqa: E402


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
def test_production_schema_rejects_the_synthetic_participant_everywhere():
    import asyncpg
    from storage.beta_v0_store import BetaStore

    async def go():
        pool = await fresh_pool()
        try:
            store = BetaStore(pool)
            async with store.connect() as c:
                with pytest.raises(asyncpg.CheckViolationError):
                    await c.conn.execute("INSERT INTO beta_allowlist (telegram_user_id) VALUES ($1)",
                                         SIM_TELEGRAM_USER_ID)
                with pytest.raises(asyncpg.CheckViolationError):
                    await c.join_user(telegram_user_id=SIM_TELEGRAM_USER_ID, chat_id=SIM_TELEGRAM_USER_ID,
                                      now=datetime(2024, 3, 4, tzinfo=timezone.utc))
                facts = await c.usage_facts()
                assert facts["users"] == [] and facts["activity"] == []
                assert await c.active_user_chats() == []
        finally:
            await pool.close()
    asyncio.run(go())
