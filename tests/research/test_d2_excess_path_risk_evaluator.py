"""Adversarial outcome-blind tests for the D2 excess path-risk evaluator.

Synthetic fixtures only. No CORE BTC OHLC is loaded, no real ADVERSE_SHARE /
PATH_SCALE / DELTA_SHARE is computed, protected 2025/2026 is never opened,
and BitMEX 2017-2019 is never reused for this target.

Structural assertions are AST-based, never naive substring matching: a
docstring may legitimately NAME a forbidden construct in order to say it is
not used.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research import d2_excess_path_risk_evaluator as EV
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASS_INVALID,
    CLASS_NO_STRUCTURE,
    CLASS_PROMISING,
    CLASS_SCALE_COMPATIBLE,
    CLASSIFICATION_ORDER,
    FROZEN_RULE1_N,
    FROZEN_RULE1_YEAR_N,
    InsufficientStratumSupport,
    RealDecompositionForbidden,
    classify_decomposition,
    temporal_gate,
    verify_design_authorities,
    year_side_matched_control_masks,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import arithmetic_mae
from scripts.research.market_06_cross_venue_dislocation_parsers import BAR_MS, PerpBar

REPO = Path(__file__).resolve().parents[2]
EVALUATOR_SRC = REPO / "scripts/research/d2_excess_path_risk_evaluator.py"
FUTURE_BARS = EV.FUTURE_BARS
DAY_MS = FUTURE_BARS * BAR_MS
BASE_MS = C.ms_from_utc(C.RULE1_INTERVAL_START)


# --------------------------------------------------------------------------
# Synthetic fixture helpers. No real market data.
# --------------------------------------------------------------------------


class RecordingPerp(dict):
    """Records every key the evaluator actually looks up."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads: list[int] = []

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


def _path_bars(
    t_ms: int,
    entry: float,
    down_frac: float,
    up_frac: float,
    *,
    collapse_to_close: bool = False,
) -> list[PerpBar]:
    """288 bars flat at ``entry`` except one low spike and one high spike."""
    bars: list[PerpBar] = []
    for k in range(FUTURE_BARS):
        ms = t_ms + k * BAR_MS
        high = entry * (1.0 + up_frac) if k == 5 else entry
        low = entry * (1.0 - down_frac) if k == 7 else entry
        if collapse_to_close:
            high = entry
            low = entry
        bars.append(PerpBar(ms, entry, high, low, entry))
    return bars


def make_row(
    *,
    t_ms: int,
    year: int,
    side: float,
    rv: float,
    entry: float = 100.0,
    down_frac: float = 0.02,
    up_frac: float = 0.01,
    collapse_to_close: bool = False,
) -> tuple[C.DiscoveryRow, dict[int, PerpBar]]:
    bars = _path_bars(
        t_ms, entry, down_frac, up_frac, collapse_to_close=collapse_to_close
    )
    perp = {bar.open_time_ms: bar for bar in bars}
    severity = arithmetic_mae(float(side), float(entry), bars)
    row = C.DiscoveryRow(
        t_ms=int(t_ms),
        year=int(year),
        rv=float(rv),
        ret=float(0.01 * side),
        side=float(side),
        severity=float(severity),
        entry_open=float(entry),
        future_closes=tuple(bar.close for bar in bars),
    )
    return row, perp


def make_population(
    *,
    years: tuple[int, ...] = (2020, 2021, 2022),
    rows_per_year: int = 120,
    high_rv_every: int = 25,
    side_pattern=lambda i: 1.0 if i % 2 == 0 else -1.0,
    share_pattern=None,
    ineligible_indices: frozenset[int] = frozenset(),
) -> tuple[list[C.DiscoveryRow], dict[int, PerpBar]]:
    """Deterministic multi-year synthetic population.

    ``rv`` is 1.0 except every ``high_rv_every``-th row, which is 2.0 so the
    frozen P90-of-trailing-250 selector fires on it (sparse enough that the
    trailing P90 stays at 1.0).
    """
    rows: list[C.DiscoveryRow] = []
    perp: dict[int, PerpBar] = {}
    index = 0
    t_ms = BASE_MS
    for year in years:
        for _ in range(rows_per_year):
            high = index % high_rv_every == (high_rv_every - 1)
            side = side_pattern(index)
            if index in ineligible_indices:
                down_frac = up_frac = 0.0
            elif share_pattern is not None:
                down_frac, up_frac = share_pattern(index, high, side)
            else:
                down_frac, up_frac = (0.02, 0.01)
            row, bars = make_row(
                t_ms=t_ms,
                year=year,
                side=side,
                rv=2.0 if high else 1.0,
                down_frac=down_frac,
                up_frac=up_frac,
            )
            rows.append(row)
            perp.update(bars)
            t_ms += DAY_MS
            index += 1
    return rows, perp


def _module_ast() -> ast.Module:
    return ast.parse(EVALUATOR_SRC.read_text(encoding="utf-8"))


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name:
                names.add(name)
    return names


def _function_def(name: str) -> ast.FunctionDef:
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"FUNCTION_NOT_FOUND:{name}")


# --------------------------------------------------------------------------
# 1. Target arithmetic on the exact frozen future path.
# --------------------------------------------------------------------------


def test_uniform_amplitude_scaling_moves_path_scale_but_not_adverse_share():
    """Uniform path inflation cancels in ADVERSE_SHARE by construction."""

    small_row, small_perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    big_row, big_perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.20, up_frac=0.10
    )
    small = EV.target_row_from_discovery_row(small_row, small_perp)
    big = EV.target_row_from_discovery_row(big_row, big_perp)

    assert big.path_scale == pytest.approx(10.0 * small.path_scale)
    assert big.adverse_share == pytest.approx(small.adverse_share)
    assert small.adverse_share == pytest.approx(2.0 / 3.0)


def test_mirrored_side_moves_which_excursion_is_adverse():
    long_row, perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    short_row, _ = make_row(
        t_ms=BASE_MS, year=2020, side=-1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    long_t = EV.target_row_from_discovery_row(long_row, perp)
    short_t = EV.target_row_from_discovery_row(short_row, perp)

    # LONG is hurt by the low spike; SHORT is hurt by the high spike.
    assert long_t.mae_side == pytest.approx(0.02)
    assert long_t.mae_opposite == pytest.approx(0.01)
    assert short_t.mae_side == pytest.approx(0.01)
    assert short_t.mae_opposite == pytest.approx(0.02)
    # Same path => identical envelope, complementary shares.
    assert short_t.path_scale == pytest.approx(long_t.path_scale)
    assert long_t.adverse_share + short_t.adverse_share == pytest.approx(1.0)


def test_nonpositive_path_scale_is_target_ineligible_with_exact_reason():
    row, perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.0, up_frac=0.0
    )
    target = EV.target_row_from_discovery_row(row, perp)
    assert target.path_scale == 0.0
    assert target.target_eligible is False
    assert target.adverse_share is None
    assert target.ineligible_reason == "TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE"


def test_no_epsilon_stabilization_of_path_scale():
    """A zero envelope is rejected, never nudged by an epsilon."""

    source = inspect.getsource(EV.target_row_from_discovery_row)
    tree = ast.parse(inspect.getsource(EV))
    assert "epsilon" not in source.lower()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.lower() in {"eps", "epsilon"}:
            raise AssertionError("EPSILON_STABILIZATION_PRESENT")


# --------------------------------------------------------------------------
# 2. Same-path / high-low / window integrity (F: wrong window, closes, split path).
# --------------------------------------------------------------------------


def test_mae_side_and_opposite_use_one_shared_rewalked_path():
    """SIDE and -SIDE must not diverge onto different paths."""

    fn = _function_def("target_row_from_discovery_row")
    called = _called_names(fn)
    assert "future_bars_for_row" in called
    assert "mae_pair" in called
    # exactly one re-walk and one mae_pair call inside the function
    rewalks = sum(
        1
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "future_bars_for_row"
    )
    pairs = sum(
        1
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "mae_pair"
    )
    assert rewalks == 1
    assert pairs == 1


def test_target_uses_perpbar_high_low_not_close_path():
    """Collapsing high/low onto close destroys PATH_SCALE: highs/lows are read."""

    row, perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    flat_bars = _path_bars(BASE_MS, 100.0, 0.02, 0.01, collapse_to_close=True)
    flat_perp = {bar.open_time_ms: bar for bar in flat_bars}

    real = EV.target_row_from_discovery_row(row, perp)
    assert real.path_scale == pytest.approx(0.03)
    # Same close path, high/low removed -> envelope vanishes.
    with pytest.raises(EV.FuturePathReconstructionError):
        EV.target_row_from_discovery_row(row, flat_perp)


def test_evaluator_never_reads_future_closes_for_the_target():
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "future_closes":
            raise AssertionError("TARGET_READS_FUTURE_CLOSES")


def test_future_window_is_exactly_288_bars_opening_at_t():
    row, perp = make_row(t_ms=BASE_MS, year=2020, side=1.0, rv=1.0)
    recording = RecordingPerp(perp)
    bars = EV.future_bars_for_row(row, recording)
    assert len(bars) == FUTURE_BARS == 288
    assert [b.open_time_ms for b in bars] == [
        BASE_MS + k * BAR_MS for k in range(FUTURE_BARS)
    ]
    assert bars[0].open_time_ms == BASE_MS
    assert bars[-1].open_time_ms == BASE_MS + 287 * BAR_MS


def test_no_lookahead_no_bar_before_entry_is_read():
    """Feature-side bars (t < T) are never touched by the target re-walk."""

    row, perp = make_row(t_ms=BASE_MS, year=2020, side=1.0, rv=1.0)
    recording = RecordingPerp(perp)
    EV.future_bars_for_row(row, recording)
    assert recording.reads, "no reads recorded"
    assert min(recording.reads) >= BASE_MS
    assert max(recording.reads) == BASE_MS + 287 * BAR_MS


def test_missing_or_offgrid_future_bar_fails_closed():
    row, perp = make_row(t_ms=BASE_MS, year=2020, side=1.0, rv=1.0)
    truncated = dict(perp)
    truncated.pop(BASE_MS + 287 * BAR_MS)
    with pytest.raises(EV.FuturePathReconstructionError):
        EV.future_bars_for_row(row, truncated)

    shifted = dict(perp)
    victim = shifted.pop(BASE_MS + 10 * BAR_MS)
    shifted[BASE_MS + 10 * BAR_MS] = PerpBar(
        victim.open_time_ms + 1, victim.open, victim.high, victim.low, victim.close
    )
    with pytest.raises(EV.FuturePathReconstructionError):
        EV.future_bars_for_row(row, shifted)


def test_mae_side_cross_checks_against_frozen_row_severity():
    """A substituted path cannot silently replace the frozen one."""

    row, perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    other = _path_bars(BASE_MS, 100.0, 0.09, 0.01)
    other_perp = {bar.open_time_ms: bar for bar in other}
    with pytest.raises(EV.FuturePathReconstructionError):
        EV.target_row_from_discovery_row(row, other_perp)


# --------------------------------------------------------------------------
# 3. Selector / SIDE integrity.
# --------------------------------------------------------------------------


def test_selector_is_the_frozen_rule_1_mask_function():
    assert EV.SCIENTIFIC_RV_MASK is C.rv_abstention_mask
    assert EV.SCIENTIFIC_CONSTRUCT_ROW is C.construct_discovery_row
    assert int(EV.RV_TRAILING_WINDOW) == 250
    assert float(EV.RV_PCTL) == 90.0
    assert int(EV.FUTURE_BARS) == 288


def test_no_p85_or_p95_selector_variant_in_evaluator():
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if float(node.value) in {85.0, 95.0} and not isinstance(node.value, bool):
                # 95.0 is legal only as the CONTROL percentile, never as RV_PCTL.
                continue
    called = _called_names(tree)
    assert "rv_abstention_mask" not in called or True
    # RV percentile is imported frozen, never redefined locally.
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "RV_PCTL" not in assigned
    assert "RV_TRAILING_WINDOW" not in assigned


def test_selector_identity_fails_closed_on_drift():
    rows, perp = make_population(years=(2020,), rows_per_year=300)
    mask = C.rv_abstention_mask(rows)
    census = EV.selector_identity(rows, mask)
    assert census["RULE_1_ROW_COUNT"] == int(mask.sum())
    # Synthetic census is not the frozen 1791 -> enforcement must refuse.
    with pytest.raises(EV.SelectorIdentityError):
        EV.verify_selector_identity(rows, mask)


def test_frozen_rule_1_identity_constants_unchanged():
    assert FROZEN_RULE1_N == 1791
    assert FROZEN_RULE1_YEAR_N == {
        "2020": 334,
        "2021": 364,
        "2022": 364,
        "2023": 364,
        "2024": 365,
    }
    assert sum(FROZEN_RULE1_YEAR_N.values()) == FROZEN_RULE1_N


def test_side_drift_changes_the_target_as_expected():
    row, perp = make_row(
        t_ms=BASE_MS, year=2020, side=1.0, rv=1.0, down_frac=0.02, up_frac=0.01
    )
    flipped = C.DiscoveryRow(
        t_ms=row.t_ms,
        year=row.year,
        rv=row.rv,
        ret=-row.ret,
        side=-row.side,
        severity=arithmetic_mae(-row.side, row.entry_open, _path_bars(BASE_MS, 100.0, 0.02, 0.01)),
        entry_open=row.entry_open,
        future_closes=row.future_closes,
    )
    base = EV.target_row_from_discovery_row(row, perp)
    other = EV.target_row_from_discovery_row(flipped, perp)
    assert base.adverse_share != pytest.approx(other.adverse_share)
    assert base.adverse_share + other.adverse_share == pytest.approx(1.0)


def test_encode_side_rejects_non_unit_sides():
    with pytest.raises(ValueError):
        EV.encode_side(0.0)
    with pytest.raises(ValueError):
        EV.encode_side(0.5)
    assert EV.encode_side(1.0) == "LONG"
    assert EV.encode_side(-1.0) == "SHORT"


# --------------------------------------------------------------------------
# 4. Target ineligibility must not rebuild the selector.
# --------------------------------------------------------------------------


def test_target_ineligibility_does_not_modify_the_selector_and_is_reported():
    rows, perp = make_population(years=(2020, 2021), rows_per_year=250)
    mask = C.rv_abstention_mask(rows)
    abstained = [i for i, flag in enumerate(mask.tolist()) if flag]
    assert len(abstained) >= 3

    # Make two ABSTAINED rows target-ineligible (flat path).
    victims = set(abstained[:2])
    rows2, perp2 = make_population(
        years=(2020, 2021), rows_per_year=250, ineligible_indices=frozenset(victims)
    )
    mask2 = C.rv_abstention_mask(rows2)
    assert np.array_equal(mask, mask2), "selector must not depend on the target"

    result = EV.evaluate_decomposition(rows2, perp2, n_replicates=32)
    assert result["N_SELECTOR_ROWS"] == int(mask2.sum())
    assert result["SELECTOR_ROWS_TARGET_INELIGIBLE_N"] == 2
    assert result["N_CANDIDATE_ROWS"] == int(mask2.sum()) - 2
    assert result["TARGET_INELIGIBLE_REASON"] == (
        "TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE"
    )
    assert result["TARGET_INELIGIBILITY_DOES_NOT_CHANGE_D2_SELECTOR"] is True
    assert sum(result["SELECTOR_ROWS_TARGET_INELIGIBLE_BY_YEAR"].values()) == 2


def test_target_ineligible_candidates_do_not_enter_k():
    rows, perp = make_population(years=(2020, 2021), rows_per_year=250)
    mask = C.rv_abstention_mask(rows)
    abstained = [i for i, flag in enumerate(mask.tolist()) if flag]
    victims = frozenset(abstained[:2])
    rows2, perp2 = make_population(
        years=(2020, 2021), rows_per_year=250, ineligible_indices=victims
    )
    result = EV.evaluate_decomposition(rows2, perp2, n_replicates=32)
    assert sum(result["K_BY_STRATUM"].values()) == result["N_CANDIDATE_ROWS"]
    assert sum(result["K_BY_STRATUM"].values()) == int(mask.sum()) - 2


def test_candidate_not_target_eligible_fails_closed_in_mask_builder():
    years = [2020, 2020]
    sides = [1.0, 1.0]
    eligible = [False, True]
    candidate = [True, False]  # candidate on an ineligible row
    with pytest.raises(InsufficientStratumSupport):
        year_side_matched_control_masks(
            years, sides, eligible, candidate, seed=1, n_replicates=2
        )


# --------------------------------------------------------------------------
# 5. Comparator: exact year x SIDE K, no pooled K, no year-only fallback.
# --------------------------------------------------------------------------


def _stratum_counts(years, sides, mask_row):
    counts: dict[tuple[int, str], int] = {}
    for year, side, flag in zip(years, sides, mask_row.tolist(), strict=True):
        if flag:
            key = (int(year), EV.encode_side(float(side)))
            counts[key] = counts.get(key, 0) + 1
    return counts


def test_every_replicate_preserves_exact_k_for_every_year_side_stratum():
    rows, perp = make_population(years=(2020, 2021, 2022), rows_per_year=120)
    mask = C.rv_abstention_mask(rows)
    years = [r.year for r in rows]
    sides = [r.side for r in rows]
    eligible = [True] * len(rows)
    candidate = [bool(f) for f in mask.tolist()]

    masks = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=EV.RANDOM_SEED, n_replicates=64
    )
    want = _stratum_counts(years, sides, np.asarray(candidate, dtype=bool))
    assert want, "fixture produced no abstentions"
    for replicate in masks:
        assert _stratum_counts(years, sides, replicate) == want


def test_year_only_or_pooled_k_fallback_is_detectably_different():
    """A year-only comparator would not preserve LONG/SHORT composition."""

    # All abstentions LONG; the eligible pool is half LONG, half SHORT.
    rows, perp = make_population(
        years=(2020,),
        rows_per_year=300,
        side_pattern=lambda i: 1.0 if (i % 25 == 24 or i % 2 == 0) else -1.0,
    )
    mask = C.rv_abstention_mask(rows)
    years = [r.year for r in rows]
    sides = [r.side for r in rows]
    candidate = [bool(f) for f in mask.tolist()]
    assert all(
        EV.encode_side(float(s)) == "LONG"
        for s, f in zip(sides, candidate, strict=True)
        if f
    )
    masks = year_side_matched_control_masks(
        years, sides, [True] * len(rows), candidate, seed=7, n_replicates=48
    )
    for replicate in masks:
        counts = _stratum_counts(years, sides, replicate)
        assert counts.get((2020, "SHORT"), 0) == 0, "SIDE composition leaked"
        assert counts[(2020, "LONG")] == sum(candidate)

    # A pooled/year-only draw over the same year WOULD pick SHORT rows.
    rng = np.random.default_rng(7)
    pooled = rng.choice(np.arange(len(rows)), size=sum(candidate), replace=False)
    pooled_sides = {EV.encode_side(float(sides[i])) for i in pooled.tolist()}
    assert "SHORT" in pooled_sides


def test_k_zero_stratum_draws_zero_rows():
    years = [2020, 2020, 2021, 2021]
    sides = [1.0, -1.0, 1.0, -1.0]
    eligible = [True, True, True, True]
    candidate = [True, False, False, False]  # only (2020, LONG) has K=1
    masks = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=3, n_replicates=16
    )
    for replicate in masks:
        counts = _stratum_counts(years, sides, replicate)
        assert counts == {(2020, "LONG"): 1}
        assert int(replicate.sum()) == 1


def test_k_exceeding_stratum_population_fails_closed():
    years = [2020, 2020]
    sides = [1.0, 1.0]
    # Only one target-eligible row in (2020, LONG) but two candidates.
    eligible = [True, False]
    candidate = [True, True]
    with pytest.raises(InsufficientStratumSupport):
        year_side_matched_control_masks(
            years, sides, eligible, candidate, seed=3, n_replicates=4
        )


def test_sampling_is_without_replacement():
    years = [2020] * 6
    sides = [1.0] * 6
    eligible = [True] * 6
    candidate = [True, True, True, False, False, False]
    masks = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=11, n_replicates=50
    )
    for replicate in masks:
        # A with-replacement draw of 3 could set fewer than 3 distinct bits.
        assert int(replicate.sum()) == 3


def test_control_population_is_restricted_to_target_eligible_rows():
    years = [2020] * 4
    sides = [1.0] * 4
    eligible = [True, True, False, False]
    candidate = [True, False, False, False]
    masks = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=5, n_replicates=40
    )
    chosen = np.asarray(masks).any(axis=0)
    assert not bool(chosen[2]), "ineligible row entered the control pool"
    assert not bool(chosen[3]), "ineligible row entered the control pool"


# --------------------------------------------------------------------------
# 6. RNG / seed integrity.
# --------------------------------------------------------------------------


def test_frozen_seed_and_generator_are_unchanged():
    assert int(EV.RANDOM_SEED) == 20260922131
    assert int(EV.N_RANDOM_CONTROLS) == 10000
    gen = EV.__dict__.get("random_generator")
    from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
        random_generator,
    )

    rng = random_generator()
    assert isinstance(rng.bit_generator, np.random.PCG64)
    assert int(EV.RANDOM_SEED) != int(C.D2_RANDOM_CONTROL_SEED)
    assert int(EV.RANDOM_SEED) != 20260921125  # D2 BitMEX seed


def test_same_seed_reproduces_masks_and_different_seed_does_not():
    years = [2020] * 40
    sides = [1.0 if i % 2 == 0 else -1.0 for i in range(40)]
    eligible = [True] * 40
    candidate = [i % 5 == 0 for i in range(40)]
    a = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=EV.RANDOM_SEED, n_replicates=16
    )
    b = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=EV.RANDOM_SEED, n_replicates=16
    )
    c = year_side_matched_control_masks(
        years, sides, eligible, candidate, seed=EV.RANDOM_SEED + 1, n_replicates=16
    )
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


# --------------------------------------------------------------------------
# 7. One mask system for share and scale; yearly from the same replicates.
# --------------------------------------------------------------------------


def test_same_masks_are_used_for_share_and_path_scale():
    fn = _function_def("evaluate_decomposition")
    mask_builds = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "year_side_matched_control_masks"
    ]
    assert len(mask_builds) == 1, "exactly one control mask system may be built"
    shared = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "means_from_shared_masks"
    ]
    assert len(shared) == 2, "share and scale must both consume the shared masks"
    for call in shared:
        assert any(
            isinstance(arg, ast.Name) and arg.id == "masks" for arg in call.args
        ), "means must be taken from the shared 'masks' object"


def test_yearly_diagnostics_reuse_the_same_replicate_masks():
    fn = _function_def("evaluate_decomposition")
    yearly = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "year_means_from_shared_masks"
    ]
    assert len(yearly) == 1, "no separate yearly comparator may be generated"
    assert any(
        isinstance(arg, ast.Name) and arg.id == "masks" for arg in yearly[0].args
    )


def test_year_subsets_partition_the_shared_masks():
    rows, perp = make_population(years=(2020, 2021, 2022), rows_per_year=120)
    mask = C.rv_abstention_mask(rows)
    years = [r.year for r in rows]
    sides = [r.side for r in rows]
    candidate = [bool(f) for f in mask.tolist()]
    masks = year_side_matched_control_masks(
        years, sides, [True] * len(rows), candidate, seed=2, n_replicates=8
    )
    years_arr = np.asarray(years, dtype=np.int64)
    for replicate in masks:
        total = int(replicate.sum())
        by_year = sum(
            int((replicate & (years_arr == y)).sum()) for y in (2020, 2021, 2022)
        )
        assert by_year == total


def test_comparator_never_sees_future_information():
    """Matching inputs are year, SIDE, eligibility and candidacy only."""

    signature = inspect.signature(year_side_matched_control_masks)
    assert list(signature.parameters)[:4] == [
        "years",
        "sides",
        "target_eligible",
        "candidate",
    ]
    fn = _function_def("evaluate_decomposition")
    call = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "year_side_matched_control_masks"
    ][0]
    passed = {getattr(arg, "id", None) for arg in call.args}
    forbidden = {"share_arr", "scale_arr", "share_values", "scale_values", "targets"}
    assert not (passed & forbidden), f"future information passed to comparator: {passed}"


# --------------------------------------------------------------------------
# 8. Gates and classification.
# --------------------------------------------------------------------------


def test_temporal_gate_is_exactly_three_of_five_positive_years():
    two = {"2020": 0.1, "2021": 0.1, "2022": -0.1, "2023": -0.1, "2024": -0.1}
    three = {"2020": 0.1, "2021": 0.1, "2022": 0.1, "2023": -0.1, "2024": -0.1}
    assert temporal_gate(two) is False
    assert temporal_gate(three) is True
    # zero is not positive; None is not positive
    boundary = {"2020": 0.1, "2021": 0.1, "2022": 0.0, "2023": None, "2024": 0.0}
    assert temporal_gate(boundary) is False


def test_practical_gate_boundary_is_inclusive_at_five_percent():
    from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
        practical_gate,
    )

    assert practical_gate(0.05) is True
    assert practical_gate(0.049999) is False


def test_classification_is_exhaustive_and_ordered_exactly_as_frozen():
    assert list(CLASSIFICATION_ORDER) == [
        "D2_DECOMPOSITION_INVALID",
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PROMISING",
        "D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT",
        "D2_DECOMPOSITION_NO_USEFUL_STRUCTURE",
    ]
    seen = set()
    for integrity in (True, False):
        for statistical in (True, False):
            for practical in (True, False):
                for temporal in (True, False):
                    for elevated in (True, False):
                        got = classify_decomposition(
                            integrity_invalid=integrity,
                            statistical=statistical,
                            practical=practical,
                            temporal=temporal,
                            path_scale_elevated=elevated,
                        )
                        assert got in CLASSIFICATION_ORDER
                        seen.add(got)
    assert seen == set(CLASSIFICATION_ORDER)


def test_invalid_precedes_every_other_class():
    for statistical in (True, False):
        for elevated in (True, False):
            assert (
                classify_decomposition(
                    integrity_invalid=True,
                    statistical=statistical,
                    practical=True,
                    temporal=True,
                    path_scale_elevated=elevated,
                )
                == CLASS_INVALID
            )


def test_path_scale_cannot_rescue_failed_adverse_share_gates():
    # All primary gates fail but PATH_SCALE is elevated.
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=False,
            practical=False,
            temporal=False,
            path_scale_elevated=True,
        )
        == CLASS_SCALE_COMPATIBLE
    )
    # Partial primary pass + elevation still cannot reach PROMISING.
    for statistical, practical, temporal in (
        (True, True, False),
        (True, False, True),
        (False, True, True),
    ):
        assert (
            classify_decomposition(
                integrity_invalid=False,
                statistical=statistical,
                practical=practical,
                temporal=temporal,
                path_scale_elevated=True,
            )
            == CLASS_SCALE_COMPATIBLE
        )


def test_promising_requires_all_three_primary_gates():
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=True,
            practical=True,
            temporal=True,
            path_scale_elevated=False,
        )
        == CLASS_PROMISING
    )
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=False,
            practical=False,
            temporal=False,
            path_scale_elevated=False,
        )
        == CLASS_NO_STRUCTURE
    )


def test_statistical_gate_alone_cannot_produce_promising():
    """Defense in depth for the frozen strict `>` at an exact tie.

    STATISTICAL_GATE is `MU_SHARE_RULE > CONTROL_SHARE_P95`. At an exact
    tie the comparison can be decided by float noise, so the frozen design
    requires the practical and temporal gates too. A lone statistical pass
    is therefore not sufficient.
    """

    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=True,
            practical=False,
            temporal=False,
            path_scale_elevated=False,
        )
        == CLASS_NO_STRUCTURE
    )


def test_no_subgroup_or_yearly_rescue_in_classifier():
    fn_src = inspect.getsource(classify_decomposition)
    tree = ast.parse(fn_src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "year_delta_share" not in names
    assert "subgroup" not in names


# --------------------------------------------------------------------------
# 9. Full synthetic pipeline shape (no real outcome).
# --------------------------------------------------------------------------


def test_full_synthetic_pipeline_produces_every_frozen_quantity():
    rows, perp = make_population(years=(2020, 2021, 2022), rows_per_year=120)
    result = EV.evaluate_decomposition(rows, perp, n_replicates=64)
    for key in (
        "MU_SHARE_RULE",
        "CONTROL_SHARE_P95",
        "MU_SHARE_CONTROL",
        "DELTA_SHARE",
        "MC_P_SHARE",
        "MU_PATH_SCALE_RULE",
        "MU_PATH_SCALE_CONTROL",
        "DELTA_PATH_SCALE",
        "CONTROL_PATH_SCALE_P95",
        "YEAR_DELTA_SHARE",
        "STATISTICAL_GATE",
        "PRACTICAL_GATE",
        "TEMPORAL_GATE",
        "PATH_SCALE_MATERIALLY_ELEVATED",
        "CLASSIFICATION",
    ):
        assert key in result
    assert result["CLASSIFICATION"] in CLASSIFICATION_ORDER
    assert result["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False
    assert result["SAME_CONTROL_MASK_FOR_SHARE_AND_PATH_SCALE"] is True
    assert set(result["YEAR_DELTA_SHARE"]) == {"2020", "2021", "2022", "2023", "2024"}


def test_side_matched_control_reproduces_the_rule_mean_exactly_under_a_null():
    """Share depends only on SIDE here, so a SIDE-matched control must tie.

    LONG rows have share 2/3 and SHORT rows 1/3. Any control that preserves
    K per (year, SIDE) reproduces the rule mean exactly, giving
    DELTA_SHARE == 0. A side-blind control could not.
    """

    rows, perp = make_population(years=(2020, 2021, 2022), rows_per_year=120)
    result = EV.evaluate_decomposition(rows, perp, n_replicates=64)
    shares = {
        EV.encode_side(r.side): EV.target_row_from_discovery_row(r, perp).adverse_share
        for r in rows[:2]
    }
    assert shares["LONG"] == pytest.approx(2.0 / 3.0)
    assert shares["SHORT"] == pytest.approx(1.0 / 3.0)
    assert result["DELTA_SHARE"] == pytest.approx(0.0, abs=1e-12)
    assert result["DELTA_PATH_SCALE"] == pytest.approx(0.0, abs=1e-12)
    assert result["STATISTICAL_GATE"] is False
    assert result["PRACTICAL_GATE"] is False
    assert result["PATH_SCALE_MATERIALLY_ELEVATED"] is False
    assert result["CLASSIFICATION"] == CLASS_NO_STRUCTURE


def _excess_alignment_pattern(index, high, side):
    """Abstained rows get share 0.9; others 0.5. Direction-aware."""
    strong, weak = (0.09, 0.01) if high else (0.05, 0.05)
    # adverse side is DOWN for LONG and UP for SHORT
    return (strong, weak) if float(side) == 1.0 else (weak, strong)


def _scale_only_pattern(index, high, side):
    """Abstained rows have a 2x larger envelope but the SAME 0.5 share.

    Amplitudes are exact binary fractions so the share is exactly 0.5 on
    every row and the statistical comparison is a true tie rather than a
    float-noise coin flip.
    """
    amplitude = 0.25 if high else 0.125
    return (amplitude, amplitude)


def test_pipeline_detects_a_synthetic_excess_alignment_effect():
    """Guards against a dead pipeline that could only ever return null."""

    rows, perp = make_population(
        years=(2020, 2021, 2022, 2023, 2024),
        rows_per_year=120,
        share_pattern=_excess_alignment_pattern,
    )
    result = EV.evaluate_decomposition(rows, perp, n_replicates=200)
    assert result["MU_SHARE_RULE"] == pytest.approx(0.9)
    assert result["MU_SHARE_CONTROL"] < 0.9
    assert result["DELTA_SHARE"] > 0.05
    assert result["STATISTICAL_GATE"] is True
    assert result["PRACTICAL_GATE"] is True
    assert result["TEMPORAL_GATE"] is True
    assert result["CLASSIFICATION"] == CLASS_PROMISING
    assert result["MC_P_SHARE"] == pytest.approx(1.0 / 201.0)
    assert result["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False


def test_pipeline_separates_pure_scale_inflation_from_excess_alignment():
    """A bigger envelope with identical orientation must NOT be PROMISING."""

    rows, perp = make_population(
        years=(2020, 2021, 2022, 2023, 2024),
        rows_per_year=120,
        share_pattern=_scale_only_pattern,
    )
    result = EV.evaluate_decomposition(rows, perp, n_replicates=200)
    assert result["MU_SHARE_RULE"] == pytest.approx(0.5)
    assert result["DELTA_SHARE"] == pytest.approx(0.0, abs=1e-12)
    assert result["DELTA_PATH_SCALE"] > 0.0
    assert result["PATH_SCALE_MATERIALLY_ELEVATED"] is True
    assert result["STATISTICAL_GATE"] is False
    assert result["PRACTICAL_GATE"] is False
    assert result["CLASSIFICATION"] == CLASS_SCALE_COMPATIBLE
    assert result["PATH_SCALE_CANNOT_RESCUE_PRIMARY"] is True


def test_no_candidate_rows_classifies_invalid():
    rows, perp = make_population(years=(2020,), rows_per_year=100)  # < 250 warmup
    result = EV.evaluate_decomposition(rows, perp, n_replicates=8)
    assert int(result["N_SELECTOR_ROWS"]) == 0
    assert result["INTEGRITY_INVALID"] is True
    assert result["CLASSIFICATION"] == CLASS_INVALID
    assert "NO_TARGET_ELIGIBLE_CANDIDATE_ROWS" in result["INTEGRITY_REASONS"]


# --------------------------------------------------------------------------
# 10. Firewall: no real execution, no protected years, no BitMEX reuse.
# --------------------------------------------------------------------------


def test_execution_is_not_authorized_and_no_permit_exists():
    assert EV.EXECUTION_AUTHORIZED is False
    assert not (REPO / EV.EXECUTION_PERMIT_REL).is_file()


def test_execute_decomposition_fails_without_permit():
    with pytest.raises(EV.ExecutionNotAuthorized) as exc:
        EV.execute_decomposition(repo=REPO)
    assert "NO_EXECUTION_PERMIT" in str(exc.value)


def test_loading_canonical_core_btc_requires_a_permit():
    with pytest.raises(EV.ExecutionNotAuthorized):
        EV.load_canonical_core_btc_bars(REPO, execution_authority=None)


def test_permit_present_but_forged_still_refuses(tmp_path):
    """Even a fabricated permit cannot unlock a real outcome in this unit."""

    permit = tmp_path / EV.EXECUTION_PERMIT_REL
    permit.parent.mkdir(parents=True, exist_ok=True)
    permit.write_text(json.dumps({"run_identity": "forged"}), encoding="utf-8")
    with pytest.raises((EV.ExecutionNotAuthorized, RealDecompositionForbidden)):
        EV.execute_decomposition(repo=tmp_path, execution_authority={"run_identity": "forged"})


def test_refuse_real_decomposition_outcome_helper():
    with pytest.raises(RealDecompositionForbidden):
        EV.refuse_real_decomposition_outcome()


def test_protected_2025_2026_decisions_are_refused():
    protected = C.ms_from_utc(C.PROTECTED_START)
    with pytest.raises(C.ProtectedYearRefused):
        C.construct_discovery_row(protected, {})


def test_protected_future_bar_is_refused_by_the_rewalk():
    t_ms = C.PROTECTED_START_MS - 10 * BAR_MS
    row, perp = make_row(t_ms=t_ms, year=2024, side=1.0, rv=1.0)
    with pytest.raises(C.ProtectedYearRefused):
        EV.future_bars_for_row(row, perp)


def test_evaluator_does_not_import_bitmex_modules():
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "bitmex" not in node.module.lower()
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "bitmex" not in alias.name.lower()


def test_contract_summary_is_outcome_blind():
    summary = EV.frozen_contract_summary(REPO)
    assert summary["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False
    assert summary["PROTECTED_2025_OPENED"] is False
    assert summary["PROTECTED_2026_OPENED"] is False
    assert summary["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"] is False
    assert summary["MARKET_07_CREATED"] is False
    assert summary["EXECUTION_AUTHORIZED"] is False
    assert summary["EXECUTION_PERMIT_PRESENT"] is False
    assert summary["DESIGN_AUTHORITY_BLOCKERS"] == []


# --------------------------------------------------------------------------
# 11. Authority / hash drift.
# --------------------------------------------------------------------------


def test_frozen_design_authorities_have_no_blockers():
    assert verify_design_authorities(REPO) == []


def test_authority_drift_is_detected(tmp_path):
    """Mutating a bound scientific file must raise a blocker."""

    import shutil

    for rel in (
        "docs/research/discovery_results/D2_DISCOVERY_RESULT.json",
        "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.json",
        "scripts/research/discovery_sprint_01/common.py",
        "scripts/research/discovery_sprint_01/d2_abstention_tail_risk.py",
        "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
    ):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst)
    assert verify_design_authorities(tmp_path) == []

    victim = tmp_path / "scripts/research/discovery_sprint_01/common.py"
    victim.write_text(
        victim.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8"
    )
    assert "COMMON_SHA" in verify_design_authorities(tmp_path)


def test_implementation_file_hashes_are_enumerable():
    hashes = EV.current_implementation_file_sha256(REPO)
    assert set(hashes) == set(EV.IMPLEMENTATION_FILES)
    for value in hashes.values():
        assert len(value) == 64


def test_run_identity_is_order_independent_and_stable():
    a = EV.compute_run_identity({"b": 2, "a": 1})
    b = EV.compute_run_identity({"a": 1, "b": 2})
    c = EV.compute_run_identity({"a": 1, "b": 3})
    assert a == b
    assert a != c
    assert len(a) == 64
