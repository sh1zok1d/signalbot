"""Tests for D2 confirmation feasibility/design.

Does not open 2025/2026 price bytes or mutate the D2 discovery result.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.d2_confirmation_feasibility_and_design import (
    AUTHORITATIVE_POWER_METHOD,
    BINDING_REL,
    D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED,
    D2_CONFIRMATION_POWER_SEED,
    D2_CONFIRMATION_RANDOM_CONTROL_SEED,
    D2_CONFIRMATION_SIZE_PLANNING_SEED,
    FIRST_T,
    FIXED_N_POWER_GRID,
    FRESH_SURFACE_SIZES,
    JSON_REL,
    LAST_FUTURE_BAR_OPEN,
    LAST_T,
    MD_REL,
    N_2025_DECISION_SLOTS,
    N_REPLICATES_CONFIRMATION,
    ORIGINAL_ONE_YEAR_POWER_AT_20PCT,
    SUPERSEDED_IID_TWO_YEAR_POWER,
    ProtectedPriceRefused,
    confirmation_decision_slot_count,
    extract_2025_metadata,
    refuse_protected_price_path,
    _calibrate_relative_effect,
)
from scripts.research.d2_confirmation_dependence_preserving_power import (
    calibrate_year_matched_relative_effect,
    circular_shift_mask,
    construct_fixed_n_surface,
    expected_year_matched_control_mean,
    frozen_2026_prefix_from_total_n,
    year_matched_control_selected_counts,
)


REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
D2_RESULT = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
D2_RESULT_MD = "docs/research/discovery_results/D2_DISCOVERY_RESULT.md"


def _committed(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)


def test_decision_interval_and_slot_count() -> None:
    assert FIRST_T == datetime(2025, 1, 1, 0, 5, tzinfo=UTC)
    assert LAST_T == datetime(2025, 12, 30, 0, 5, tzinfo=UTC)
    assert confirmation_decision_slot_count() == N_2025_DECISION_SLOTS == 364
    assert LAST_FUTURE_BAR_OPEN.year == 2025
    assert LAST_FUTURE_BAR_OPEN.month == 12
    assert LAST_FUTURE_BAR_OPEN.day == 31


def test_frozen_seeds_and_replicates() -> None:
    assert D2_CONFIRMATION_RANDOM_CONTROL_SEED == 20260921120
    assert D2_CONFIRMATION_POWER_SEED == 20260921121
    assert D2_CONFIRMATION_SIZE_PLANNING_SEED == 20260921122
    assert D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED == 20260921123
    assert D2_CONFIRMATION_RANDOM_CONTROL_SEED != C.D2_RANDOM_CONTROL_SEED
    assert D2_CONFIRMATION_SIZE_PLANNING_SEED != D2_CONFIRMATION_POWER_SEED
    assert D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED != D2_CONFIRMATION_SIZE_PLANNING_SEED
    assert N_REPLICATES_CONFIRMATION == 10_000
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_statistical_gate"] == 0.011
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_both_gates"] == 0.006
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_practical_gate"] == 0.499
    assert FRESH_SURFACE_SIZES == ((1, 364), (2, 728), (3, 1092), (4, 1456))
    assert FIXED_N_POWER_GRID == (364, 550, 575, 600, 625, 650, 675, 700, 728, 1092, 1456)
    assert AUTHORITATIVE_POWER_METHOD == "YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK"
    assert SUPERSEDED_IID_TWO_YEAR_POWER == 0.903


def test_2025_metadata_binding_has_twelve_months_and_no_prices() -> None:
    meta = extract_2025_metadata(repo=REPO)
    assert meta["n_months"] == 12
    assert meta["issues"] == []
    assert meta["CONFIRMATION_2025_MONTHS_METADATA_BOUND"] is True
    assert meta["CONFIRMATION_2025_SOURCE_HASHES_BOUND"] is True
    assert meta["CONFIRMATION_2025_CANONICAL_HASHES_BOUND"] is True
    assert meta["2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL"] is False
    periods = [row["period"] for row in meta["months"]]
    assert periods == [f"2025-{m:02d}" for m in range(1, 13)]
    binding = json.loads((REPO / BINDING_REL).read_text(encoding="utf-8"))
    assert binding["contains_price_values"] is False
    assert binding["objects_materialized"] is False
    assert len(binding["objects"]) == 12
    assert all("2026" not in obj["period"] for obj in binding["objects"])
    assert all(obj["source_SHA256"] and obj["canonical_parquet_SHA256"] for obj in binding["objects"])
    packed = json.dumps(binding["objects"])
    assert "close" not in packed
    assert "severity" not in packed


def test_refuse_protected_price_paths(tmp_path: Path) -> None:
    bad = tmp_path / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"nope")
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused)):
        refuse_protected_price_path(bad)
    also = tmp_path / "canonical" / "1m" / "monthly" / "2026-02.parquet"
    also.write_bytes(b"nope")
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused)):
        refuse_protected_price_path(also)


def test_report_does_not_open_protected_prices() -> None:
    report = json.loads((REPO / JSON_REL).read_text(encoding="utf-8"))
    assert report["PROTECTED_2025_PRICE_VALUES_INSPECTED"] is False
    assert report["PROTECTED_2026_PRICE_VALUES_INSPECTED"] is False
    assert report["PROTECTED_2025_OPENED"] is False
    assert report["PROTECTED_2026_OPENED"] is False
    assert report["PROTECTED_PRICE_PATHS_OPENED"] == []
    assert report["EXPOSED_FILES_OPENED_YEARS"] == ["2020", "2021", "2022", "2023", "2024"]
    assert report["MARKET_07_CREATED"] is False
    assert report["ARM_CREATED"] is False
    assert report["2025_OPEN_AUTHORIZED"] is False
    assert report["CONFIRMATION_FEASIBILITY"] == "UNDERPOWERED_SINGLE_YEAR_2025"
    assert report["POWER_AT_20PCT_MIN_EFFECT"] == 0.006
    assert report["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(0.011)
    assert report["ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT"] == pytest.approx(0.006)
    assert report["PRIMARY_PROSPECTIVE_POWER_CRITERION"] == "STATISTICAL_POWER_AT_20PCT_EFFECT"
    assert report["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"] < 0.80
    assert report["CANDIDATE"] == "D2 / RULE_1 / RV_ABSTENTION"
    assert "DISLOCATION_ABSTENTION" in report["NOT_CONFIRMED_VARIANTS"]
    assert report["RULE_CHANGED"] is False
    assert report["TARGET_CHANGED"] is False
    assert report["GATES_CHANGED"] is False
    assert report["AUTHORIZED_TO_OPEN"] is False
    assert report["2025_OPEN_AUTHORIZED"] is False
    assert "P90" in report["CONFIRMATION_RULE"]
    assert "trailing 250" in report["CONFIRMATION_RULE"]
    assert "24h direction-aligned" in report["CONFIRMATION_TARGET"]
    assert "RATE_MATCHED_RANDOM_ABSTENTION" in report["CONFIRMATION_COMPARATOR"]
    assert "0.20 * UNCONDITIONAL_MEAN" in report["CONFIRMATION_PRACTICAL_GATE"]
    assert "P95" in report["CONFIRMATION_STATISTICAL_GATE"]
    interp = report["POWER_INTERPRETATION_CORRECTION"]
    assert interp["JOINT_PASS_PROBABILITY_IS_DIAGNOSTIC_ONLY"] is True
    assert interp["PRACTICAL_GATE_UNCHANGED"] is True
    orig = interp["ORIGINAL_ONE_YEAR_CALCULATION_PRESERVED"]
    assert orig["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(0.011)
    assert orig["ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT"] == pytest.approx(0.006)
    assert orig["ONE_YEAR_PRACTICAL_GATE_POWER_AT_20PCT"] == pytest.approx(0.499)
    md = (REPO / MD_REL).read_text(encoding="utf-8")
    assert "UNDERPOWERED_SINGLE_YEAR_2025" in md
    assert "## POWER_INTERPRETATION_CORRECTION" in md
    assert "MARKET-07" in md
    assert "AUTHORIZED_TO_OPEN = false" in md
    if "DEPENDENCE_PRESERVING_SIZE_PLANNING" in report:
        assert report["SUPERSEDED_IID_TWO_YEAR_POWER"] == pytest.approx(0.903)
        iid = report["SUPERSEDED_IID_SIZE_PLANNING"]
        assert iid["SIZE_PLANNING_SEED"] == D2_CONFIRMATION_SIZE_PLANNING_SEED
        assert iid["TWO_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(0.903)
        assert report["AUTHORITATIVE_POWER_METHOD"] == AUTHORITATIVE_POWER_METHOD
        dep = report["DEPENDENCE_PRESERVING_SIZE_PLANNING"]
        assert dep["DEPENDENCE_PRESERVING_SEED"] == D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED
        assert dep["pooled_k_subset_used"] is False
        assert dep["iid_row_resampling_used"] is False
        assert dep["FIXED_N_POWER_GRID"] == list(FIXED_N_POWER_GRID)
        assert report["PR_READY_TO_MERGE"] is False
        assert "## SUPERSEDED_IID_SIZE_PLANNING" in md
        assert "YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK" in md
    else:
        assert report["TWO_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(0.903)


def test_2025_metadata_binding_unchanged_by_sizing_amendment() -> None:
    rel = BINDING_REL
    current = (REPO / rel).read_bytes()
    original = subprocess.check_output(
        ["git", "show", "72746234119031b00632a92086076021c2a72ba4:" + rel],
        cwd=REPO,
    )
    assert current == original


def test_d2_discovery_result_unchanged() -> None:
    for rel in (D2_RESULT, D2_RESULT_MD):
        current = (REPO / rel).read_bytes()
        committed = _committed(rel)
        assert hashlib.sha256(current).digest() == hashlib.sha256(committed).digest()
        assert current == committed


def test_calibration_hits_predeclared_relative_effect() -> None:
    rng = np.random.default_rng(0)
    y = rng.random(364) + 0.01
    selected = np.zeros(364, dtype=bool)
    selected[rng.choice(364, size=39, replace=False)] = True
    y_alt = _calibrate_relative_effect(y, selected, 0.20)
    rel = (float(y_alt[selected].mean()) - float(y_alt.mean())) / float(y_alt.mean())
    assert rel == pytest.approx(0.20, abs=1e-12)


def test_no_2025_parquet_materialized_locally() -> None:
    monthly = REPO / "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly"
    if monthly.is_dir():
        names = {p.name for p in monthly.glob("*.parquet")}
        assert not any(name.startswith("2025-") or name.startswith("2026-") for name in names)


def test_year_matched_controls_are_not_pooled() -> None:
    n = 20
    block_slices = [(0, 10), (10, 20)]
    block_k = [2, 5]
    rng = np.random.default_rng(1)
    selected = year_matched_control_selected_counts(block_slices, block_k, 200, rng, n)
    assert selected.shape == (200, 20)
    for rep in selected:
        assert int(rep[0:10].sum()) == 2
        assert int(rep[10:20].sum()) == 5
        assert int(rep.sum()) == 7
    # A pooled K=7 subset would sometimes put !=2 into the first block.
    pooled_first = selected[:, 0:10].sum(axis=1)
    assert np.all(pooled_first == 2)


def test_circular_shift_breaks_alignment_and_preserves_k() -> None:
    rng = np.random.default_rng(2)
    mask = np.zeros(40, dtype=bool)
    mask[0:5] = True
    mask[20:23] = True
    k0 = int(mask.sum())
    shifted, offset = circular_shift_mask(mask, rng)
    assert offset != 0
    assert int(shifted.sum()) == k0
    assert not np.array_equal(shifted, mask)
    assert np.array_equal(shifted, np.roll(mask, offset))


def test_partial_year_surface_is_contiguous_and_block_matched() -> None:
    rng = np.random.default_rng(3)
    year_blocks = {
        2021: {
            "severity": np.linspace(0.01, 0.05, 364),
            "mask": np.array([i % 10 == 0 for i in range(364)]),
        },
        2022: {
            "severity": np.linspace(0.02, 0.06, 364),
            "mask": np.array([i % 8 == 0 for i in range(364)]),
        },
        2023: {
            "severity": np.linspace(0.015, 0.04, 364),
            "mask": np.array([i % 12 == 0 for i in range(364)]),
        },
        2024: {
            "severity": np.linspace(0.01, 0.07, 365),
            "mask": np.array([i % 9 == 0 for i in range(365)]),
        },
    }
    y, selected, slices, meta = construct_fixed_n_surface(year_blocks, 650, rng)
    assert y.size == 650
    assert selected.size == 650
    assert slices[0][0] == 0
    assert slices[-1][1] == 650
    lengths = [m["length"] for m in meta]
    assert sum(lengths) == 650
    assert any(m["whole_year"] for m in meta)
    assert any(not m["whole_year"] for m in meta)
    for m in meta:
        assert m["contiguous"] is True
        assert m["association_broken"] is True
        assert m["shift_offset"] != 0
        src = year_blocks[m["source_year"]]["severity"]
        if not m["whole_year"]:
            assert m["end"] - m["start"] == m["length"]
            assert 0 <= m["start"] < m["end"] <= src.size
    block_k = [int(selected[lo:hi].sum()) for lo, hi in slices]
    drawn = year_matched_control_selected_counts(slices, block_k, 50, rng, 650)
    for i, ((lo, hi), k) in enumerate(zip(slices, block_k)):
        assert np.all(drawn[:, lo:hi].sum(axis=1) == k)


def test_year_matched_20pct_injection_hits_expected_control_definition() -> None:
    rng = np.random.default_rng(4)
    y = rng.random(80) + 0.02
    selected = np.zeros(80, dtype=bool)
    selected[0:10] = True
    selected[50:57] = True
    slices = [(0, 40), (40, 80)]
    y_alt = calibrate_year_matched_relative_effect(y, selected, slices, relative=0.20)
    block_k = [int(selected[lo:hi].sum()) for lo, hi in slices]
    mu_rule = float(y_alt[selected].mean())
    e_ctrl = expected_year_matched_control_mean(y_alt, slices, block_k)
    uncond = float(y_alt.mean())
    rel = (mu_rule - e_ctrl) / uncond
    assert rel == pytest.approx(0.20, abs=1e-12)


def test_fixed_n_cutoff_is_deterministic_calendar_only() -> None:
    prefix = frozen_2026_prefix_from_total_n(650)
    assert prefix["FROZEN_2026_PREFIX_DECISION_COUNT"] == 286
    assert prefix["FROZEN_FINAL_DECISION_TIMESTAMP"] == "2026-10-13T00:05:00Z"
    full = frozen_2026_prefix_from_total_n(728)
    assert full["FROZEN_2026_PREFIX_DECISION_COUNT"] == 364
    assert full["FROZEN_FINAL_DECISION_TIMESTAMP"] == "2026-12-30T00:05:00Z"
    none = frozen_2026_prefix_from_total_n(364)
    assert none["FROZEN_2026_PREFIX_DECISION_COUNT"] == 0
    assert none["FROZEN_FINAL_DECISION_TIMESTAMP"] is None

