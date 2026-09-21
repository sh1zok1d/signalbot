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
    BINDING_REL,
    D2_CONFIRMATION_POWER_SEED,
    D2_CONFIRMATION_RANDOM_CONTROL_SEED,
    D2_CONFIRMATION_SIZE_PLANNING_SEED,
    FIRST_T,
    FRESH_SURFACE_SIZES,
    JSON_REL,
    LAST_FUTURE_BAR_OPEN,
    LAST_T,
    MD_REL,
    N_2025_DECISION_SLOTS,
    N_REPLICATES_CONFIRMATION,
    ORIGINAL_ONE_YEAR_POWER_AT_20PCT,
    ProtectedPriceRefused,
    confirmation_decision_slot_count,
    extract_2025_metadata,
    refuse_protected_price_path,
    _calibrate_relative_effect,
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
    assert D2_CONFIRMATION_RANDOM_CONTROL_SEED != C.D2_RANDOM_CONTROL_SEED
    assert D2_CONFIRMATION_SIZE_PLANNING_SEED != D2_CONFIRMATION_POWER_SEED
    assert N_REPLICATES_CONFIRMATION == 10_000
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_statistical_gate"] == 0.011
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_both_gates"] == 0.006
    assert ORIGINAL_ONE_YEAR_POWER_AT_20PCT["power_practical_gate"] == 0.499
    assert FRESH_SURFACE_SIZES == ((1, 364), (2, 728), (3, 1092), (4, 1456))


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
    size = report["SIZE_PLANNING"]
    assert size["SIZE_PLANNING_SEED"] == D2_CONFIRMATION_SIZE_PLANNING_SEED
    ns = [row["N"] for row in size["surfaces"]]
    assert ns == [364, 728, 1092, 1456]
    ks = [row["expected_K"] for row in size["surfaces"]]
    assert ks == [39, 77, 116, 154]
    assert report["TWO_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(0.903)
    assert report["THREE_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(1.0)
    assert report["FOUR_YEAR_STATISTICAL_POWER_AT_20PCT"] == pytest.approx(1.0)
    assert report["MIN_REQUIRED_FRESH_DECISION_ROWS"] == 728
    assert report["MIN_REQUIRED_FRESH_YEARS"] == 2
    assert report["POTENTIAL_FUTURE_SURFACE"] == "2025_PLUS_FULL_2026"
    assert report["NEXT_UNIT"] == "D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_2026_WITHOUT_OPENING"
    md = (REPO / MD_REL).read_text(encoding="utf-8")
    assert "UNDERPOWERED_SINGLE_YEAR_2025" in md
    assert "## POWER_INTERPRETATION_CORRECTION" in md
    assert "MARKET-07" in md
    assert "AUTHORIZED_TO_OPEN = false" in md


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
