"""Explicit identifiability / rank validation before OLS.

Frozen prereg:

    identifiability.collinear_or_rank_deficient
        = MARKET_06_INCOMPLETE_EXECUTION

The audit requires an explicit ``numpy.linalg.matrix_rank(X.T @ X)`` check
rather than relying on ``numpy.linalg.solve`` raising. This closes rank
deficiency only: no custom tolerance, no condition-number gate, and no
ridge/pinv/lstsq fallback (F-04 stays
HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE).

Synthetic designs only. No retained market data.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pytest

from scripts.research import market_06_cross_venue_dislocation_bootstrap as bootstrap
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
)

REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP_SRC = REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py"

PRODUCTION_MODULES = (
    REPO / "scripts/research/market_06_cross_venue_dislocation_authority.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_parsers.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_bootstrap.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
    REPO / "scripts/research/market_06_cross_venue_dislocation_runner.py",
    REPO / "scripts/research/market_06_canonical_reconstruction.py",
    REPO / "scripts/research/market_06_execution_lifecycle.py",
    REPO / "scripts/research/market_06_git_authority.py",
    REPO / "scripts/research/market_06_result_persistence.py",
    REPO / "scripts/research/market_06_year_stratified_circular_mbb.py",
)


def _full_rank_design(n: int = 60, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(12345)
    design = np.column_stack([np.ones(n)] + [rng.normal(size=n) for _ in range(k - 1)])
    y = rng.normal(size=n)
    return design, y


# --------------------------------------------------------------------------
# 1. Full rank solves.
# --------------------------------------------------------------------------


def test_full_rank_design_passes_explicit_rank_check_and_solves():
    design, y = _full_rank_design()
    xtx = design.T @ design
    assert np.linalg.matrix_rank(xtx) == xtx.shape[0] == design.shape[1]
    beta = bootstrap.ols_solve(design, y)
    assert beta.shape == (design.shape[1],)
    assert np.all(np.isfinite(beta))


def test_full_rank_result_is_unchanged_by_the_repair():
    """The rank check must not alter any accepted solution."""

    design, y = _full_rank_design()
    expected = np.linalg.solve(design.T @ design, design.T @ y)
    assert np.allclose(bootstrap.ols_solve(design, y), expected)


# --------------------------------------------------------------------------
# 2-3. Rank-deficient designs fail closed.
# --------------------------------------------------------------------------


def test_exactly_rank_deficient_design_raises_rank_deficient():
    n = 40
    col = np.arange(float(n))
    design = np.column_stack([np.ones(n), col, col * 2.0])  # 3rd = 2 * 2nd
    y = np.arange(float(n))
    xtx = design.T @ design
    assert np.linalg.matrix_rank(xtx) < xtx.shape[0]
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(design, y)
    assert exc.value.reason == "RANK_DEFICIENT"
    assert exc.value.classification == "MARKET_06_INCOMPLETE_EXECUTION"


def test_duplicated_regressor_column_raises_rank_deficient():
    rng = np.random.default_rng(7)
    n = 50
    x1 = rng.normal(size=n)
    design = np.column_stack([np.ones(n), x1, rng.normal(size=n), x1])  # dup of x1
    y = rng.normal(size=n)
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(design, y)
    assert exc.value.reason == "RANK_DEFICIENT"


def test_constant_duplicate_intercept_raises_rank_deficient():
    n = 30
    design = np.column_stack([np.ones(n), np.ones(n), np.arange(float(n))])
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(design, np.arange(float(n)))
    assert exc.value.reason == "RANK_DEFICIENT"


def test_more_columns_than_rows_raises_rank_deficient():
    rng = np.random.default_rng(3)
    design = rng.normal(size=(4, 6))
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(design, rng.normal(size=4))
    assert exc.value.reason == "RANK_DEFICIENT"


def test_rank_check_runs_before_solve(monkeypatch):
    """Identifiability is decided explicitly, not by catching LinAlgError."""

    n = 40
    col = np.arange(float(n))
    design = np.column_stack([np.ones(n), col, col * 2.0])

    def _must_not_be_called(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("np.linalg.solve was reached on a rank-deficient design")

    monkeypatch.setattr(bootstrap.np.linalg, "solve", _must_not_be_called)
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.ols_solve(design, np.arange(float(n)))
    assert exc.value.reason == "RANK_DEFICIENT"


# --------------------------------------------------------------------------
# 4. A rank-deficient bootstrap replicate aborts the whole execution.
# --------------------------------------------------------------------------


def test_rank_deficient_bootstrap_replicate_aborts_without_redraw(monkeypatch):
    design, y = _full_rank_design(n=60, k=5)
    rng = bootstrap.make_rng()
    calls = {"n": 0}
    real_solve = bootstrap.ols_solve

    def failing_on_third(d, yy):
        calls["n"] += 1
        if calls["n"] == 3:
            raise Market06IncompleteExecution("RANK_DEFICIENT")
        return real_solve(d, yy)

    monkeypatch.setattr(bootstrap, "ols_solve", failing_on_third)
    with pytest.raises(Market06IncompleteExecution) as exc:
        bootstrap.coefficient_moving_block_bootstrap(design, y, rng, replicates=50)
    assert exc.value.reason == "RANK_DEFICIENT"
    # aborted at the third replicate: no redraw, no skip, no replacement
    assert calls["n"] == 3


def test_bootstrap_has_no_redraw_or_replacement_logic():
    source = inspect.getsource(bootstrap.coefficient_moving_block_bootstrap)
    lowered = source.lower()
    for forbidden in ("redraw", "retry", "resample_until", "except", "continue", "skip"):
        assert forbidden not in lowered


# --------------------------------------------------------------------------
# 5-7. No fallback, no custom tolerance, no condition-number gate.
# --------------------------------------------------------------------------


FORBIDDEN_SOLVERS = frozenset({"lstsq", "pinv", "inv", "ridge", "Ridge"})


def _called_names(path: Path) -> set[str]:
    """Names actually CALLED in a module (not words in prose)."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name:
                names.add(name)
    return names


def test_no_solver_fallback_anywhere_in_production():
    """Checked structurally: a docstring may NAME a banned solver to say it
    is not used; what matters is that none is ever called."""

    for path in PRODUCTION_MODULES:
        called = _called_names(path)
        offending = called & FORBIDDEN_SOLVERS
        assert not offending, f"{sorted(offending)} called in {path.name}"


def test_matrix_rank_is_called_without_custom_tolerance():
    tree = ast.parse(BOOTSTRAP_SRC.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "matrix_rank"
    ]
    assert len(calls) == 1, "expected exactly one matrix_rank call"
    call = calls[0]
    assert len(call.args) == 1, "matrix_rank must take only the matrix"
    assert not call.keywords, "no tol/hermitian keyword may be supplied"
    # structural, not textual: the docstring legitimately explains that
    # NumPy's default tolerance is used and no custom tol is supplied.
    assert not any(
        isinstance(node, ast.keyword) and node.arg in ("tol", "hermitian")
        for node in ast.walk(call)
    )


def test_no_condition_number_gate_anywhere_in_production():
    """Structural: no module may CALL a condition-number routine."""

    for path in PRODUCTION_MODULES:
        called = _called_names(path)
        assert "cond" not in called, f"cond() called in {path.name}"
        assert "condition_number" not in called, f"condition_number() in {path.name}"
    # and no rcond keyword is ever passed
    for path in PRODUCTION_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "rcond":
                raise AssertionError(f"rcond keyword supplied in {path.name}")


def test_frozen_solver_equation_unchanged():
    text = BOOTSTRAP_SRC.read_text(encoding="utf-8")
    assert "xtx = design.T @ design" in text
    assert "xty = design.T @ y" in text
    assert "np.linalg.solve(xtx, xty)" in text
    # the LinAlgError layer is retained as a second defence
    assert "except np.linalg.LinAlgError" in text


def test_rank_predicate_is_exact_equality_to_column_count():
    text = BOOTSTRAP_SRC.read_text(encoding="utf-8")
    assert "rank = np.linalg.matrix_rank(xtx)" in text
    assert "if rank != xtx.shape[0]:" in text


def test_scientific_constants_untouched():
    from scripts.research import market_06_cross_venue_dislocation_evaluator as ev
    from scripts.research import market_06_year_stratified_circular_mbb as mbb

    assert ev.REFERENCE_COUNT == 8640
    assert ev.MAD_CONSISTENCY_CONSTANT == 1.4826
    assert ev.RV_RETURN_COUNT == 288
    assert ev.FUTURE_BARS == 288
    assert ev.MATERIALITY_THRESHOLD == 0.02
    assert ev.G6_ADVERSE_YEAR_THRESHOLD == -0.02
    assert ev.TRAIN_SD_DDOF == 0
    assert mbb.BLOCK_LENGTH_DAYS == 14
    assert mbb.BOOTSTRAP_REPLICATES == 5000
    assert mbb.RANDOM_SEED == 2026092106
    assert bootstrap.PERCENTILE_Q == [2.5, 97.5]
    assert bootstrap.PERCENTILE_METHOD == "linear"
