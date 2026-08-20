"""Tests for analytics/forecasting_v2/ports.py's V2EpisodeEventWriter,
V2AlignedInputReader, and V2SetupHistoryReader.

Proves each Protocol stays a narrow, structural-typing dependency boundary:
a minimal fake satisfies it without importing storage/db.py, the concrete
storage.db.Database satisfies it WITHOUT being made to inherit from the
Protocol, and an object missing a method does not satisfy it. Also proves
V2SetupHistoryReader (Stage 5) and V2AlignedInputReader (Stage 3) are
deliberately SEPARATE Protocols with no inheritance relationship between
them — a fake satisfying only one does not automatically satisfy the
other. No runtime behavior is exercised here — this module only asserts
type shape.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

from analytics.forecasting_v2.ports import (
    V2AlignedInputReader, V2EpisodeEventWriter, V2SetupHistoryReader,
    V2VersionDrainStatusReader,
)


# ---- a minimal fake writer, built with zero storage/db.py import --------------
class FakeWriter:
    def __init__(self):
        self.calls = []

    async def insert_v2_episode_events(self, rows):
        self.calls.append(list(rows))
        return len(rows)


def test_fake_writer_satisfies_the_protocol_structurally():
    fw = FakeWriter()
    assert isinstance(fw, V2EpisodeEventWriter)


def _imported_module_names(module, *, top_level_only: bool = False) -> set[str]:
    """AST-level import audit: real `import`/`from ... import` statements
    only, never a prose mention of a module name inside a docstring or
    comment (this file's own docstring, and ports.py's, both legitimately
    *talk about* storage.db.Database without importing it). With
    `top_level_only=True`, only module-scope imports count — a local
    `import` inside one test function's body (used elsewhere in this same
    file to test Database's structural conformance) is deliberately not
    counted as "the module imports X"."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    nodes = tree.body if top_level_only else ast.walk(tree)
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_fake_writer_class_needs_no_storage_db_import():
    # FakeWriter itself is defined with zero storage/db.py dependency: this
    # test file's own MODULE-LEVEL imports never reference storage.db (a
    # separate test further below deliberately does a local import inside
    # its own function body, to prove Database ALSO satisfies the Protocol
    # — that is a distinct claim, not a requirement of FakeWriter).
    import sys
    imported = _imported_module_names(sys.modules[FakeWriter.__module__], top_level_only=True)
    assert not any(name == "storage.db" or name.startswith("storage.db.")
                   for name in imported)


def test_fake_writer_returns_honest_count():
    fw = FakeWriter()
    result = asyncio.run(fw.insert_v2_episode_events([1, 2, 3]))
    assert result == 3
    assert fw.calls == [[1, 2, 3]]


# ---- an object missing the method does NOT satisfy the protocol ---------------
class NotAWriter:
    async def some_other_method(self):
        return None


def test_object_missing_method_does_not_satisfy_protocol():
    assert not isinstance(NotAWriter(), V2EpisodeEventWriter)


def test_plain_object_does_not_satisfy_protocol():
    assert not isinstance(object(), V2EpisodeEventWriter)


# ---- storage.db.Database satisfies the Protocol structurally, without ---------
# being made to inherit from it (no coupling introduced in storage/db.py).
def test_database_satisfies_protocol_without_inheritance():
    from storage.db import Database
    assert V2EpisodeEventWriter not in Database.__mro__
    db = Database("postgresql://unused")
    assert isinstance(db, V2EpisodeEventWriter)


def test_database_has_the_matching_method_name():
    from storage.db import Database
    assert hasattr(Database, "insert_v2_episode_events")
    assert inspect.iscoroutinefunction(Database.insert_v2_episode_events)


# ---- Protocol shape itself: one async method, one Sequence[...] param ---------
def test_protocol_defines_exactly_one_method():
    members = [
        name for name, val in vars(V2EpisodeEventWriter).items()
        if not name.startswith("_") and callable(val)
    ]
    assert members == ["insert_v2_episode_events"]


def test_protocol_method_is_async():
    assert inspect.iscoroutinefunction(V2EpisodeEventWriter.insert_v2_episode_events)


def test_protocol_method_signature_is_rows_only():
    sig = inspect.signature(V2EpisodeEventWriter.insert_v2_episode_events)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["rows"]


def test_protocol_is_runtime_checkable():
    # isinstance() succeeding above already proves this, but assert the
    # explicit marker too so a future refactor can't silently drop it.
    assert getattr(V2EpisodeEventWriter, "_is_runtime_protocol", False) is True


# ---- purity / no added behavior ------------------------------------------------
def _executable_body_source(module) -> str:
    """Source with the module docstring and every statement-level docstring
    (class/function) stripped, so a prose mention inside documentation
    (e.g. ports.py's own "no transactions" design-rationale sentence)
    cannot false-positive a forbidden-token scan of the actual code."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_ports_module_adds_no_behavior_beyond_the_type_shape():
    import analytics.forecasting_v2.ports as ports_mod
    body_src = _executable_body_source(ports_mod)
    forbidden = (
        "retry", "transaction", "fetch(", "fetchval(", "execute(",
        "asyncpg", "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "connect(", "await ",
    )
    for token in forbidden:
        assert token not in body_src, f"unexpected behavior token found in ports.py body: {token!r}"


def test_ports_module_does_not_import_storage_db():
    import analytics.forecasting_v2.ports as ports_mod
    imported = _imported_module_names(ports_mod)
    assert not any(name == "storage.db" or name.startswith("storage.db.")
                   for name in imported)


def test_ports_module_does_not_wire_anything_into_runtime():
    import analytics.forecasting_v2.ports as ports_mod
    # the module namespace should expose only the four Protocols and
    # their error-free supporting typing imports — no stray callable side
    # effect object.
    public = [n for n in dir(ports_mod) if not n.startswith("_")]
    assert set(ports_mod.__all__) <= set(public)
    assert ports_mod.__all__ == [
        "V2EpisodeEventWriter", "V2AlignedInputReader", "V2SetupHistoryReader",
        "V2VersionDrainStatusReader",
    ]


# ============================================================================
# V2AlignedInputReader — a minimal fake reader, built with zero storage/db.py
# import
# ============================================================================
class FakeAlignedInputReader:
    def __init__(self):
        self.calls = []

    async def fetch_v2_consensus_feature(self, **kw):
        self.calls.append(("consensus_feature", kw))
        return None

    async def fetch_v2_consensus_percentiles(self, **kw):
        self.calls.append(("consensus_percentiles", kw))
        return ()

    async def fetch_v2_data_health_at_cutoff(self, **kw):
        self.calls.append(("data_health_at_cutoff", kw))
        return {}

    async def fetch_v2_reference_feature(self, **kw):
        self.calls.append(("reference_feature", kw))
        return None

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        return ()


def test_fake_aligned_input_reader_satisfies_the_protocol_structurally():
    assert isinstance(FakeAlignedInputReader(), V2AlignedInputReader)


def test_fake_aligned_input_reader_module_never_imports_storage_db():
    import sys
    imported = _imported_module_names(
        sys.modules[FakeAlignedInputReader.__module__], top_level_only=True)
    assert not any(name == "storage.db" or name.startswith("storage.db.")
                   for name in imported)


class NotAnAlignedInputReader:
    async def fetch_v2_consensus_feature(self, **kw):
        return None
    # missing the other four methods


def test_object_missing_methods_does_not_satisfy_aligned_input_reader_protocol():
    assert not isinstance(NotAnAlignedInputReader(), V2AlignedInputReader)


def test_plain_object_does_not_satisfy_aligned_input_reader_protocol():
    assert not isinstance(object(), V2AlignedInputReader)


def test_database_satisfies_aligned_input_reader_protocol_without_inheritance():
    from storage.db import Database
    assert V2AlignedInputReader not in Database.__mro__
    db = Database("postgresql://unused")
    assert isinstance(db, V2AlignedInputReader)


@pytest.mark.parametrize("method_name", [
    "fetch_v2_consensus_feature", "fetch_v2_consensus_percentiles",
    "fetch_v2_data_health_at_cutoff", "fetch_v2_reference_feature",
    "fetch_v2_reference_klines",
])
def test_database_has_matching_coroutine_methods(method_name):
    from storage.db import Database
    assert hasattr(Database, method_name)
    assert inspect.iscoroutinefunction(getattr(Database, method_name))


def test_aligned_input_reader_protocol_defines_exactly_five_methods():
    members = [
        name for name, val in vars(V2AlignedInputReader).items()
        if not name.startswith("_") and callable(val)
    ]
    assert sorted(members) == sorted([
        "fetch_v2_consensus_feature", "fetch_v2_consensus_percentiles",
        "fetch_v2_data_health_at_cutoff", "fetch_v2_reference_feature",
        "fetch_v2_reference_klines",
    ])


@pytest.mark.parametrize("method_name", [
    "fetch_v2_consensus_feature", "fetch_v2_consensus_percentiles",
    "fetch_v2_data_health_at_cutoff", "fetch_v2_reference_feature",
    "fetch_v2_reference_klines",
])
def test_aligned_input_reader_protocol_methods_are_async(method_name):
    assert inspect.iscoroutinefunction(getattr(V2AlignedInputReader, method_name))


def test_aligned_input_reader_protocol_is_runtime_checkable():
    assert getattr(V2AlignedInputReader, "_is_runtime_protocol", False) is True


def test_aligned_input_reader_protocol_adds_no_behavior_beyond_the_type_shape():
    import analytics.forecasting_v2.ports as ports_mod
    body_src = _executable_body_source(ports_mod)
    forbidden = (
        "retry", "transaction", "fetch(", "fetchval(", "execute(",
        "asyncpg", "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "connect(", "await ",
    )
    for token in forbidden:
        assert token not in body_src, f"unexpected behavior token found in ports.py body: {token!r}"


# ============================================================================
# V2SetupHistoryReader (Stage 5) — a minimal fake reader, built with zero
# storage/db.py import
# ============================================================================
class FakeSetupHistoryReader:
    def __init__(self):
        self.calls = []

    async def fetch_v2_consensus_feature_window(self, **kw):
        self.calls.append(("consensus_feature_window", kw))
        return ()

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(("consensus_percentile_window", kw))
        return ()

    async def fetch_v2_reference_feature_window(self, **kw):
        self.calls.append(("reference_feature_window", kw))
        return ()

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        return ()

    async def fetch_v2_instrument(self, **kw):
        self.calls.append(("instrument", kw))
        return None


def test_fake_setup_history_reader_satisfies_the_protocol_structurally():
    assert isinstance(FakeSetupHistoryReader(), V2SetupHistoryReader)


def test_fake_setup_history_reader_module_never_imports_storage_db():
    import sys
    imported = _imported_module_names(
        sys.modules[FakeSetupHistoryReader.__module__], top_level_only=True)
    assert not any(name == "storage.db" or name.startswith("storage.db.")
                   for name in imported)


class NotASetupHistoryReader:
    async def fetch_v2_consensus_feature_window(self, **kw):
        return ()
    # missing the other four methods


def test_object_missing_methods_does_not_satisfy_setup_history_reader_protocol():
    assert not isinstance(NotASetupHistoryReader(), V2SetupHistoryReader)


def test_plain_object_does_not_satisfy_setup_history_reader_protocol():
    assert not isinstance(object(), V2SetupHistoryReader)


def test_database_satisfies_setup_history_reader_protocol_without_inheritance():
    from storage.db import Database
    assert V2SetupHistoryReader not in Database.__mro__
    db = Database("postgresql://unused")
    assert isinstance(db, V2SetupHistoryReader)


@pytest.mark.parametrize("method_name", [
    "fetch_v2_consensus_feature_window", "fetch_v2_consensus_percentile_window",
    "fetch_v2_reference_feature_window", "fetch_v2_reference_klines", "fetch_v2_instrument",
])
def test_database_has_matching_setup_history_coroutine_methods(method_name):
    from storage.db import Database
    assert hasattr(Database, method_name)
    assert inspect.iscoroutinefunction(getattr(Database, method_name))


def test_setup_history_reader_protocol_defines_exactly_five_methods():
    members = [
        name for name, val in vars(V2SetupHistoryReader).items()
        if not name.startswith("_") and callable(val)
    ]
    assert sorted(members) == sorted([
        "fetch_v2_consensus_feature_window", "fetch_v2_consensus_percentile_window",
        "fetch_v2_reference_feature_window", "fetch_v2_reference_klines", "fetch_v2_instrument",
    ])


@pytest.mark.parametrize("method_name", [
    "fetch_v2_consensus_feature_window", "fetch_v2_consensus_percentile_window",
    "fetch_v2_reference_feature_window", "fetch_v2_reference_klines", "fetch_v2_instrument",
])
def test_setup_history_reader_protocol_methods_are_async(method_name):
    assert inspect.iscoroutinefunction(getattr(V2SetupHistoryReader, method_name))


def test_setup_history_reader_protocol_is_runtime_checkable():
    assert getattr(V2SetupHistoryReader, "_is_runtime_protocol", False) is True


def test_setup_history_reader_protocol_adds_no_behavior_beyond_the_type_shape():
    import analytics.forecasting_v2.ports as ports_mod
    body_src = _executable_body_source(ports_mod)
    forbidden = (
        "retry", "transaction", "fetch(", "fetchval(", "execute(",
        "asyncpg", "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "connect(", "await ",
    )
    for token in forbidden:
        assert token not in body_src, f"unexpected behavior token found in ports.py body: {token!r}"


# ============================================================================
# V2SetupHistoryReader / V2AlignedInputReader — deliberately SEPARATE
# Protocols, no inheritance relationship between them
# ============================================================================
def test_setup_history_reader_and_aligned_input_reader_share_no_inheritance():
    assert V2SetupHistoryReader not in V2AlignedInputReader.__mro__
    assert V2AlignedInputReader not in V2SetupHistoryReader.__mro__


def test_stage3_only_fake_does_not_need_stage5_methods():
    # A fake implementing ONLY the original five Stage 3 methods still
    # satisfies V2AlignedInputReader -- it is not retroactively required
    # to grow Stage 5 methods just because V2SetupHistoryReader now exists.
    assert isinstance(FakeAlignedInputReader(), V2AlignedInputReader)
    assert not isinstance(FakeAlignedInputReader(), V2SetupHistoryReader)


def test_stage5_only_fake_does_not_satisfy_aligned_input_reader():
    # Symmetric: a fake implementing only the Stage 5 methods does not
    # satisfy V2AlignedInputReader (it lacks fetch_v2_consensus_feature,
    # fetch_v2_consensus_percentiles, fetch_v2_data_health_at_cutoff).
    assert isinstance(FakeSetupHistoryReader(), V2SetupHistoryReader)
    assert not isinstance(FakeSetupHistoryReader(), V2AlignedInputReader)


def test_database_satisfies_both_protocols_simultaneously():
    from storage.db import Database
    db = Database("postgresql://unused")
    assert isinstance(db, V2AlignedInputReader)
    assert isinstance(db, V2SetupHistoryReader)


# ============================================================================
# V2VersionDrainStatusReader (V2-H2b) — deliberately has NO concrete
# implementation yet (Stage 6 does not exist); only fakes satisfy it.
# ============================================================================
class FakeDrainStatusReader:
    def __init__(self, fact=None):
        from analytics.forecasting_v2.version_switch import V2DrainFact
        self._fact = fact if fact is not None else V2DrainFact(0, 0)
        self.calls = []

    async def fetch_v2_version_drain_status(self, **kw):
        self.calls.append(kw)
        return self._fact


def test_fake_drain_status_reader_satisfies_the_protocol_structurally():
    assert isinstance(FakeDrainStatusReader(), V2VersionDrainStatusReader)


def test_fake_drain_status_reader_module_never_imports_storage_db():
    import sys
    imported = _imported_module_names(
        sys.modules[FakeDrainStatusReader.__module__], top_level_only=True)
    assert not any(name == "storage.db" or name.startswith("storage.db.")
                   for name in imported)


class NotADrainStatusReader:
    pass


def test_object_missing_method_does_not_satisfy_drain_status_reader_protocol():
    assert not isinstance(NotADrainStatusReader(), V2VersionDrainStatusReader)


def test_plain_object_does_not_satisfy_drain_status_reader_protocol():
    assert not isinstance(object(), V2VersionDrainStatusReader)


def test_drain_status_reader_protocol_defines_exactly_one_method():
    methods = [name for name in vars(V2VersionDrainStatusReader)
               if not name.startswith("_") and callable(getattr(V2VersionDrainStatusReader, name))]
    assert methods == ["fetch_v2_version_drain_status"]


def test_drain_status_reader_protocol_method_is_async():
    method = getattr(V2VersionDrainStatusReader, "fetch_v2_version_drain_status")
    assert inspect.iscoroutinefunction(method)


def test_drain_status_reader_protocol_is_runtime_checkable():
    assert getattr(V2VersionDrainStatusReader, "_is_runtime_protocol", False) is True


def test_database_does_not_satisfy_drain_status_reader_protocol():
    """Deliberate: Stage 6 (which would own a real non-terminal-episode/
    active-cooldown count) does not exist yet -- storage.db.Database has no
    `fetch_v2_version_drain_status` method, and must not, until a real
    Stage-6-backed implementation is written as its own future work."""
    from storage.db import Database
    db = Database("postgresql://unused")
    assert not isinstance(db, V2VersionDrainStatusReader)
    assert not hasattr(db, "fetch_v2_version_drain_status")
