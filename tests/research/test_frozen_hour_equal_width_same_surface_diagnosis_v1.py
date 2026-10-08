"""Synthetic checks for the same-surface equal-width diagnosis. No market panel is opened."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.frozen_hour_equal_width_v1 import solver
from scripts.research.frozen_hour_equal_width_same_surface_diagnosis_v1 import (
    ORIGINAL_RESULT,
    REFUSAL_RERUN,
    SPOT_RESULT,
    _pooled_illustration,
    _rate_block,
    build_cell,
    write_outputs,
)
from scripts.research.opening_range_object_v1 import constants as PARENT

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_SHA = "9d21dafa4272bc0dab16329187edd65a7acf50adad071b80c8d63f2ea3c57fae"
SPOT_SHA = "137f59e00d1a676f68d9353f50fe9f060e29ab01c6c850e4eef3bbb46c7b4ac8"


def _row(year: int, y_real: float, y_orig: float, y_eq: float, ratio: float) -> dict:
    return {
        "year": year,
        "iso_year": year,
        "iso_week": 1,
        "y_real": y_real,
        "y_orig": y_orig,
        "y_eq": y_eq,
        "d_orig": y_real - y_orig,
        "d_eq": y_real - y_eq,
        "d_att": y_eq - y_orig,
        "w_real": 20.0,
        "w_orig": 20.0 * ratio,
        "w_eq": 20.0,
        "width_ratio_orig": ratio,
        "width_ratio_eq": 1.0,
        "rel_mismatch_orig": ratio - 1.0,
        "rel_width_error": 0.0,
    }


def test_attenuation_is_the_control_gap_on_one_cohort():
    rows = [
        _row(2023, 1.0, 0.0, 1.0, 1.4),
        _row(2023, 1.0, 0.0, 1.0, 0.7),
    ]
    block = _rate_block(rows)
    assert block["n"] == 2
    assert block["original_delta"] == 1.0
    assert block["equal_width_delta"] == 0.0
    assert block["attenuation"] == 1.0
    assert block["equal_width_minus_original_pseudo"] == block["attenuation"]
    assert _pooled_illustration(0.01) == "WIDTH_REGIME_COUPLING_STRONGLY_SUPPORTED_AS_EXPLANATION"
    assert _pooled_illustration(0.045) == "MIXED_WIDTH_AND_FORMATION_STRUCTURE_PLAUSIBLE"
    assert _pooled_illustration(0.03) == "OUTSIDE_THE_STATED_NUMERIC_ILLUSTRATIONS"


def test_scale_uses_the_frozen_solver_and_the_published_partner():
    assert solver.solve_equal_width.__module__.endswith("frozen_hour_equal_width_v1.solver")
    n_days = 8
    n = n_days * PARENT.BARS_PER_DAY
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    close = np.full(n, np.nan)
    # 2020-01-06 and 2020-01-13 are the two Mondays. Other days stay missing.
    _paint(high, low, close, 0, 110.0, 90.0, 100.0)
    _paint(high, low, close, 7, 104.0, 96.0, 100.0)
    t0 = 1578268800000  # 2020-01-06T00:00:00Z
    built = build_cell(high, low, close, t0, PARENT.ANCHORS["UTC_00"])
    assert built["published_n"] == 2
    assert len(built["rows"]) == 2
    assert sum(built["drop_from_published_pairs"].values()) == 0
    for row in built["rows"]:
        assert abs(row["width_ratio_eq"] - 1.0) <= 1e-9
        assert row["rel_width_error"] <= 1e-9
    ratios = sorted(row["width_ratio_orig"] for row in built["rows"])
    assert ratios[0] < 1.0 < ratios[1]


def test_official_result_bytes_stay_pinned():
    assert hashlib.sha256(ORIGINAL_RESULT.read_bytes()).hexdigest() == ORIGINAL_SHA
    assert hashlib.sha256(SPOT_RESULT.read_bytes()).hexdigest() == SPOT_SHA
    official = json.loads(ORIGINAL_RESULT.read_text(encoding="utf-8"))
    spot = json.loads(SPOT_RESULT.read_text(encoding="utf-8"))
    assert official["route"] == "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE"
    assert spot["route"] == "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE"


def test_second_write_refuses(tmp_path):
    json_path = tmp_path / "diag.json"
    md_path = tmp_path / "diag.md"
    json_path.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        write_outputs({"unit": "synthetic"}, json_path, md_path)
    assert str(exc.value) == REFUSAL_RERUN


def _paint(high, low, close, day: int, level_high: float, level_low: float, p0: float) -> None:
    form = day * PARENT.BARS_PER_DAY
    high[form:form + 12] = level_high
    low[form:form + 12] = level_low
    close[form:form + 12] = p0
    life = form + 12
    end = life + PARENT.ACTIVE_LIFE_BARS
    high[life:end] = p0 + 1.0
    low[life:end] = p0 + 0.5
    close[life:end] = p0
    # One high-side touch of both the real bound and a partner bound placed on this day.
    high[life] = 1000.0
    low[life] = p0 + 0.5
