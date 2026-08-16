"""Tests for analytics/forecasting_v2/alignment.py (Stage 3 — Multi-timeframe
Alignment PR 1). Pure timestamp-selection tests only — no DB, network,
clock, or filesystem. Exercises the two frozen layers
(docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §1): `decision_boundary`
(wall-clock -> logical decision boundary T) and `selected_bucket`
(T -> per-timeframe closed bucket start), their exact V1 5m equivalence,
the frozen worked-alignment vectors, no-lookahead invariants, and fail-closed
input validation.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from analytics.forecasting_v2 import alignment as alignment_module
from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, decision_boundary, selected_bucket,
)
from runtime.shadow_cli import select_latest_closed_5m_bucket

UTC = timezone.utc


def dt(y, mo, d, h, mi, s=0, us=0):
    return datetime(y, mo, d, h, mi, s, us, tzinfo=UTC)


# ============================================================================
# TIMEFRAME_MINUTES
# ============================================================================
def test_timeframe_minutes_exact_mapping():
    assert dict(TIMEFRAME_MINUTES) == {"5m": 5, "15m": 15, "1h": 60, "4h": 240}


def test_timeframe_minutes_is_immutable():
    assert isinstance(TIMEFRAME_MINUTES, MappingProxyType)
    with pytest.raises(TypeError):
        TIMEFRAME_MINUTES["8h"] = 480  # type: ignore[index]


@pytest.mark.parametrize("bad_tf", [
    "1m", "60m", "240m", "05m", "15M", "1H", "4H", "5M", "d", "", None, 5, "1d",
])
def test_unsupported_timeframe_rejected(bad_tf):
    with pytest.raises(V2AlignmentError, match="timeframe"):
        selected_bucket(bad_tf, dt(2026, 8, 15, 12, 10))


@pytest.mark.parametrize("unhashable_tf", [[], {}, set()])
def test_unhashable_timeframe_rejected_with_alignment_error_not_typeerror(unhashable_tf):
    # Regression: `timeframe not in TIMEFRAME_MINUTES` alone would raise a
    # bare TypeError for an unhashable value (list/dict/set) before this
    # function's own fail-closed V2AlignmentError ever got a chance to
    # fire — the exact-type check must come first.
    with pytest.raises(V2AlignmentError, match="timeframe"):
        selected_bucket(unhashable_tf, dt(2026, 8, 15, 12, 10))


# ============================================================================
# §1.4 worked alignment vectors — exact contract table
# ============================================================================
@pytest.mark.parametrize("T,expected", [
    (dt(2026, 8, 15, 12, 10), {
        "5m": dt(2026, 8, 15, 12, 5), "15m": dt(2026, 8, 15, 11, 45),
        "1h": dt(2026, 8, 15, 11, 0), "4h": dt(2026, 8, 15, 8, 0)}),
    (dt(2026, 8, 15, 12, 15), {
        "5m": dt(2026, 8, 15, 12, 10), "15m": dt(2026, 8, 15, 12, 0),
        "1h": dt(2026, 8, 15, 11, 0), "4h": dt(2026, 8, 15, 8, 0)}),
    (dt(2026, 8, 15, 13, 0), {
        "5m": dt(2026, 8, 15, 12, 55), "15m": dt(2026, 8, 15, 12, 45),
        "1h": dt(2026, 8, 15, 12, 0), "4h": dt(2026, 8, 15, 8, 0)}),
    (dt(2026, 8, 15, 16, 0), {
        "5m": dt(2026, 8, 15, 15, 55), "15m": dt(2026, 8, 15, 15, 45),
        "1h": dt(2026, 8, 15, 15, 0), "4h": dt(2026, 8, 15, 12, 0)}),
])
def test_worked_alignment_vectors(T, expected):
    for tf, bucket_ts in expected.items():
        assert selected_bucket(tf, T) == bucket_ts


# ============================================================================
# §1.4 grace-boundary vector — Layer 1 + Layer 2 together, microsecond exact
# ============================================================================
def test_grace_boundary_just_before_threshold():
    now = dt(2026, 8, 15, 12, 10, 4, 999999)
    T = decision_boundary(now, soft_grace_s=5)
    assert T == dt(2026, 8, 15, 12, 5, 0)
    assert selected_bucket("5m", T) == dt(2026, 8, 15, 12, 0)


def test_grace_boundary_exactly_at_threshold():
    now = dt(2026, 8, 15, 12, 10, 5, 0)
    T = decision_boundary(now, soft_grace_s=5)
    assert T == dt(2026, 8, 15, 12, 10, 0)
    assert selected_bucket("5m", T) == dt(2026, 8, 15, 12, 5)


def test_decision_boundary_returns_close_instant_not_bucket_start():
    # Load-bearing distinction (§1.2/§1.3): decision_boundary's T is the
    # 5m bucket's CLOSE instant, never its start — selected_bucket("5m", T)
    # subtracts the 5m to get the start.
    now = dt(2026, 8, 15, 12, 10, 0)
    T = decision_boundary(now, soft_grace_s=0)
    assert T == dt(2026, 8, 15, 12, 10, 0)          # close instant
    assert selected_bucket("5m", T) == dt(2026, 8, 15, 12, 5, 0)  # bucket start
    assert T != selected_bucket("5m", T)


# ============================================================================
# midnight / day-rollover
# ============================================================================
def test_midnight_rollover_all_timeframes():
    T = dt(2026, 8, 16, 0, 0)
    assert selected_bucket("4h", T) == dt(2026, 8, 15, 20, 0)
    assert selected_bucket("1h", T) == dt(2026, 8, 15, 23, 0)
    assert selected_bucket("15m", T) == dt(2026, 8, 15, 23, 45)
    assert selected_bucket("5m", T) == dt(2026, 8, 15, 23, 55)


def test_decision_boundary_grace_crossing_midnight():
    now = dt(2026, 8, 16, 0, 0, 2, 0)  # 2s past midnight
    T = decision_boundary(now, soft_grace_s=5)
    # effective = 2026-08-15 23:59:57 -> floors to 2026-08-15 23:55:00
    assert T == dt(2026, 8, 15, 23, 55, 0)
    assert selected_bucket("5m", T) == dt(2026, 8, 15, 23, 50, 0)


# ============================================================================
# V1 equivalence — same algorithm, reused not re-derived
# ============================================================================
@pytest.mark.parametrize("now,grace", [
    (dt(2026, 8, 15, 12, 10, 0), 0),
    (dt(2026, 8, 15, 12, 10, 5), 5),
    (dt(2026, 8, 15, 12, 10, 4, 999999), 5),
    (dt(2026, 8, 15, 12, 10, 5, 0), 5),
    (dt(2026, 8, 15, 13, 0, 0), 5),
    (dt(2026, 8, 15, 12, 3, 0), 200),          # larger grace
    (dt(2026, 8, 16, 0, 0, 2, 0), 5),           # midnight rollover
    (dt(2026, 8, 15, 23, 59, 59, 999999), 5),   # just before day rollover
])
def test_v1_equivalence(now, grace):
    v2_result = selected_bucket("5m", decision_boundary(now, soft_grace_s=grace))
    v1_result = select_latest_closed_5m_bucket(now, soft_grace_s=grace)
    assert v2_result == v1_result


def test_v1_helper_not_imported_by_production_module():
    # analytics -> runtime would be the wrong dependency direction; the
    # frozen algorithm is re-implemented locally in alignment.py, and the
    # V1 helper is only ever imported from tests (this file).
    import ast
    tree = ast.parse(inspect.getsource(alignment_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("runtime"), alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("runtime"), node.module


# ============================================================================
# no-lookahead / "latest closed bucket" invariants
# ============================================================================
@pytest.mark.parametrize("tf", ["5m", "15m", "1h", "4h"])
def test_bucket_never_extends_past_T_and_no_later_bucket_qualifies(tf):
    T = dt(2026, 8, 15, 12, 10)
    m = TIMEFRAME_MINUTES[tf]
    bucket_start = selected_bucket(tf, T)
    bucket_end = bucket_start + timedelta(minutes=m)
    assert bucket_start < bucket_end <= T
    # the very next bucket on this timeframe's grid must NOT yet be closed
    # at T (no-lookahead: selected_bucket returns the LATEST closed bucket).
    next_bucket_end = bucket_end + timedelta(minutes=m)
    assert next_bucket_end > T


def test_partially_formed_higher_timeframe_bucket_not_selected_at_1210():
    T = dt(2026, 8, 15, 12, 10)
    assert selected_bucket("15m", T) == dt(2026, 8, 15, 11, 45)   # not [12:00,12:15)
    assert selected_bucket("1h", T) == dt(2026, 8, 15, 11, 0)     # not [12:00,13:00)
    assert selected_bucket("4h", T) == dt(2026, 8, 15, 8, 0)      # not [12:00,16:00)


def test_15m_rolls_forward_at_1215_but_1h_and_4h_do_not():
    t1 = dt(2026, 8, 15, 12, 10)
    t2 = dt(2026, 8, 15, 12, 15)
    assert selected_bucket("15m", t1) != selected_bucket("15m", t2)
    assert selected_bucket("1h", t1) == selected_bucket("1h", t2)
    assert selected_bucket("4h", t1) == selected_bucket("4h", t2)


# ============================================================================
# decision_boundary input validation
# ============================================================================
def test_decision_boundary_valid():
    T = decision_boundary(dt(2026, 8, 15, 12, 10, 5), soft_grace_s=5)
    assert T == dt(2026, 8, 15, 12, 10, 0)


@pytest.mark.parametrize("bad_now", [
    datetime(2026, 8, 15, 12, 10),                              # naive
    datetime(2026, 8, 15, 12, 10, tzinfo=timezone(timedelta(hours=2))),  # non-UTC
    "2026-08-15T12:10:00Z",
    None,
    12345,
    True,
])
def test_decision_boundary_rejects_bad_now(bad_now):
    with pytest.raises(V2AlignmentError, match="now"):
        decision_boundary(bad_now, soft_grace_s=5)


@pytest.mark.parametrize("bad_grace", [-1, -5, 1.5, "5", None, True, False])
def test_decision_boundary_rejects_bad_soft_grace_s(bad_grace):
    with pytest.raises(V2AlignmentError, match="soft_grace_s"):
        decision_boundary(dt(2026, 8, 15, 12, 10), soft_grace_s=bad_grace)


def test_decision_boundary_accepts_zero_grace():
    T = decision_boundary(dt(2026, 8, 15, 12, 10, 0), soft_grace_s=0)
    assert T == dt(2026, 8, 15, 12, 10, 0)


def test_decision_boundary_no_upper_bound_on_grace():
    # A deliberately large grace legitimately selects an older boundary —
    # no arbitrary maximum is imposed.
    T = decision_boundary(dt(2026, 8, 15, 12, 10, 0), soft_grace_s=3600)
    assert T == dt(2026, 8, 15, 11, 10, 0)


# ============================================================================
# selected_bucket T input validation (fail-closed, never silently floored)
# ============================================================================
@pytest.mark.parametrize("bad_T", [
    datetime(2026, 8, 15, 12, 10),                                       # naive
    datetime(2026, 8, 15, 12, 10, tzinfo=timezone(timedelta(hours=-5))),  # non-UTC
    dt(2026, 8, 15, 12, 10, 1),        # second != 0
    dt(2026, 8, 15, 12, 10, 0, 1),     # microsecond != 0
    dt(2026, 8, 15, 12, 11),           # minute not on 5m grid
    dt(2026, 8, 15, 12, 12),           # minute not on 5m grid
    "2026-08-15T12:10:00Z",
    None,
    12345,
])
def test_selected_bucket_rejects_malformed_T(bad_T):
    with pytest.raises(V2AlignmentError):
        selected_bucket("5m", bad_T)


def test_malformed_T_is_rejected_not_silently_floored():
    # A non-5m-aligned T must fail outright, not be quietly rounded down to
    # the nearest legal decision boundary before use.
    with pytest.raises(V2AlignmentError, match="5m grid"):
        selected_bucket("5m", dt(2026, 8, 15, 12, 11, 0))


@pytest.mark.parametrize("tf", ["5m", "15m", "1h", "4h"])
def test_selected_bucket_accepts_every_5m_aligned_T_for_every_timeframe(tf):
    for minute in (0, 5, 10, 15, 20, 55):
        T = dt(2026, 8, 15, 12, minute)
        assert isinstance(selected_bucket(tf, T), datetime)


# ============================================================================
# purity / source-level checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with the module docstring and every statement-level docstring
    (class/function) stripped, so a prose mention inside documentation
    (e.g. this module's own "no datetime.now()" design-rationale sentence)
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


def test_module_reads_no_clock():
    body_src = _executable_body_source(alignment_module)
    for forbidden in ("datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic("):
        assert forbidden not in body_src


def test_module_has_no_db_network_config_env_random_uuid_asyncio_access():
    body_src = _executable_body_source(alignment_module)
    forbidden = (
        "asyncpg", "import yaml", "os.environ", "os.getenv", "open(",
        "import random", "import uuid", "import asyncio", "import subprocess",
        "sleep(", "Stage2Config", "V2Config", "requests.", "httpx.",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found in alignment.py body: {token!r}"


def test_module_has_no_top_level_mutable_state_besides_frozen_mapping():
    import ast
    tree = ast.parse(inspect.getsource(alignment_module))
    module_level_assign_targets = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_level_assign_targets.append(target.id)
    # TIMEFRAME_MINUTES is an immutable MappingProxyType; _UTC/_EPOCH are
    # frozen constants; __all__ is the standard export list. No other
    # module-level mutable container is defined.
    assert set(module_level_assign_targets) == {"TIMEFRAME_MINUTES", "_UTC", "_EPOCH", "__all__"}


def test_functions_are_plain_sync_deterministic_callables():
    assert not inspect.iscoroutinefunction(decision_boundary)
    assert not inspect.iscoroutinefunction(selected_bucket)


def test_decision_boundary_deterministic_same_inputs_same_output():
    now = dt(2026, 8, 15, 12, 10, 5)
    assert decision_boundary(now, soft_grace_s=5) == decision_boundary(now, soft_grace_s=5)


def test_selected_bucket_deterministic_same_inputs_same_output():
    T = dt(2026, 8, 15, 12, 10)
    assert selected_bucket("4h", T) == selected_bucket("4h", T)
