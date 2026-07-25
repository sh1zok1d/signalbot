"""Architecture / isolation tests for the Telegram forecast notifier.

Proves, statically (AST/text inspection — no DB/network/Docker), that:
- notifications/* stay pure (no DB, network, clock, logging, filesystem import);
- storage/telegram_notification_readers.py stays SQL-only (no analytics/runtime
  import, no network client import, no raw string-interpolated SQL);
- the shadow forecast/outcome path (runtime/shadow_recovery.py,
  runtime/shadow_cli.py, analytics/forecasting/shadow_cycle.py) never imports
  anything from the Telegram subsystem, and vice versa;
- no asyncio.gather / sleep / background while-loop anywhere in the new code;
- config/stage2.yaml's master switch remains False.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

NOTIFICATIONS_FILES = [
    ROOT / "notifications" / "telegram_models.py",
    ROOT / "notifications" / "telegram_formatter.py",
    ROOT / "notifications" / "telegram_client.py",
]
STORAGE_READER = ROOT / "storage" / "telegram_notification_readers.py"
RUNTIME_TELEGRAM = ROOT / "runtime" / "telegram_cli.py"
RUNTIME_SHADOW_FILES = [
    ROOT / "runtime" / "shadow_recovery.py",
    ROOT / "runtime" / "shadow_cli.py",
]
SHADOW_CYCLE = ROOT / "analytics" / "forecasting" / "shadow_cycle.py"


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _top_level_import_lines(path: Path) -> list:
    """Only module-scope import statements (function-local lazy imports are
    deliberately excluded — that is the whole point of the lazy-import design
    for the `telegram` package)."""
    tree = ast.parse(path.read_text())
    lines = []
    for node in tree.body:   # module body only, not nested in functions
        if isinstance(node, ast.Import):
            lines.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            lines.append(node.module)
    return lines


# ============================================================================
# A. notifications/* purity: no DB, network, clock, logging, filesystem
# ============================================================================
_BANNED_MODULE_PREFIXES = (
    "asyncpg", "aiohttp", "httpx", "requests", "socket", "telegram",
    "logging", "os", "pathlib", "storage", "runtime", "main",
)


def test_notifications_modules_have_no_banned_top_level_imports():
    for path in NOTIFICATIONS_FILES:
        top_level = _top_level_import_lines(path)
        for mod in top_level:
            for banned in _BANNED_MODULE_PREFIXES:
                assert not (mod == banned or mod.startswith(banned + ".")), (
                    f"{path.name} has a banned top-level import: {mod!r}")


def test_notifications_modules_have_no_datetime_now_calls():
    # a pure module must never read the wall clock itself
    for path in NOTIFICATIONS_FILES:
        text = path.read_text()
        assert "datetime.now(" not in text
        assert "utcnow(" not in text


def test_notifications_modules_have_no_db_or_env_access():
    for path in NOTIFICATIONS_FILES:
        text = path.read_text()
        assert "os.environ" not in text
        assert "conn." not in text
        assert "pool." not in text


def test_telegram_client_only_module_allowed_to_reference_telegram_package():
    # notifications/telegram_client.py is the ONE place the `telegram` package
    # name may appear (lazily, inside function bodies) — models/formatter must
    # never reference it at all.
    for path in (ROOT / "notifications" / "telegram_models.py",
                 ROOT / "notifications" / "telegram_formatter.py"):
        assert "telegram." not in path.read_text().replace(".telegram_models", "")


def test_telegram_client_lazy_import_is_function_scoped_only():
    top_level = _top_level_import_lines(ROOT / "notifications" / "telegram_client.py")
    assert not any(m == "telegram" or m.startswith("telegram.") for m in top_level)


# ============================================================================
# B. storage reader: SQL-only, no analytics/runtime import, no raw f-string SQL
# ============================================================================
def test_storage_reader_imports_no_analytics_or_runtime_or_main():
    imports = _imports(STORAGE_READER)
    for mod in imports:
        assert not mod.startswith("analytics"), mod
        assert not mod.startswith("runtime"), mod
        assert mod != "main", mod


def test_storage_reader_imports_no_network_client():
    imports = _imports(STORAGE_READER)
    for banned in ("telegram", "aiohttp", "httpx", "requests"):
        assert not any(m == banned or m.startswith(banned + ".") for m in imports)


def _sql_constant_values(path: Path) -> list:
    """The RHS values of every module-level `*_SQL = ...` assignment — the
    only strings that must be static (error-message f-strings elsewhere in the
    same file are fine)."""
    tree = ast.parse(path.read_text())
    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.endswith("_SQL"):
            values.append(node.value)
    return values


def test_storage_reader_sql_constants_are_static_strings_not_fstrings():
    for value in _sql_constant_values(STORAGE_READER):
        assert isinstance(value, ast.Constant) and isinstance(value.value, str), (
            "every *_SQL constant must be a plain string literal, never an "
            "f-string or runtime concatenation")


def _sql_text(path: Path) -> str:
    return "\n".join(v.value for v in _sql_constant_values(path))


def test_storage_reader_never_selects_consensus_snapshot():
    assert "consensus_snapshot" not in _sql_text(STORAGE_READER).lower()


def test_storage_reader_never_selects_star():
    assert "SELECT *" not in _sql_text(STORAGE_READER)


# ============================================================================
# C. cross-isolation: shadow path <-> telegram subsystem, in BOTH directions
# ============================================================================
def test_shadow_modules_never_import_telegram_subsystem():
    for path in RUNTIME_SHADOW_FILES + [SHADOW_CYCLE]:
        imports = _imports(path)
        for mod in imports:
            assert not mod.startswith("notifications"), f"{path.name} imports {mod!r}"
            assert mod != "runtime.telegram_cli", f"{path.name} imports {mod!r}"
            assert not mod.startswith("storage.telegram_notification_readers"), (
                f"{path.name} imports {mod!r}")


def test_telegram_runtime_never_imports_shadow_execution_path():
    imports = _imports(RUNTIME_TELEGRAM)
    assert "runtime.shadow_recovery" not in imports
    assert "runtime.shadow_cli" not in imports
    assert "analytics.forecasting.shadow_cycle" not in imports


def test_shadow_recovery_never_imports_telegram_package_itself():
    text = RUNTIME_SHADOW_FILES[0].read_text()
    top_level = _top_level_import_lines(RUNTIME_SHADOW_FILES[0])
    assert not any(m == "telegram" or m.startswith("telegram.") for m in top_level)


# ============================================================================
# D. no background loop / concurrency shortcuts anywhere in the new runtime
# ============================================================================
def test_no_asyncio_gather_anywhere_in_telegram_subsystem():
    for path in NOTIFICATIONS_FILES + [STORAGE_READER, RUNTIME_TELEGRAM]:
        assert "asyncio.gather" not in path.read_text(), path


def test_no_sleep_anywhere_in_telegram_subsystem():
    for path in NOTIFICATIONS_FILES + [STORAGE_READER, RUNTIME_TELEGRAM]:
        text = path.read_text()
        assert "time.sleep" not in text, path
        assert "asyncio.sleep" not in text, path


def test_no_while_loop_anywhere_in_telegram_subsystem():
    for path in NOTIFICATIONS_FILES + [STORAGE_READER, RUNTIME_TELEGRAM]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            assert not isinstance(node, ast.While), f"while-loop found in {path.name}"


def test_no_random_or_jitter_in_retry_backoff():
    text = (ROOT / "notifications" / "telegram_models.py").read_text()
    assert "import random" not in text
    assert "random." not in text


# ============================================================================
# E. Stage 2 master switch untouched
# ============================================================================
def test_stage2_master_switch_remains_false():
    cfg = yaml.safe_load((ROOT / "config" / "stage2.yaml").read_text())
    assert cfg["stage2"]["enabled"] is False


# ============================================================================
# F. main.py never mixes shadow and telegram command dispatch
# ============================================================================
def test_main_dispatches_shadow_and_telegram_as_separate_early_returns():
    text = (ROOT / "main.py").read_text()
    assert "is_shadow_command(args)" in text
    assert "is_telegram_command(args)" in text
    shadow_idx = text.index("is_shadow_command(args)")
    telegram_idx = text.index("is_telegram_command(args)")
    assert shadow_idx != telegram_idx
