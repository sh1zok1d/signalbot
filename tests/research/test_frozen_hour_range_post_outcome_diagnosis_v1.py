"""Guards for the post-outcome diagnosis. No market read."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from scripts.research.opening_range_object_v1 import constants as K
from scripts.research.opening_range_object_v1 import evaluate, outcomes
from scripts.research.frozen_hour_range_post_outcome_diagnosis_v1 import (
    OFFICIAL_ROUTE,
    RESULT_JSON,
    barrier_detail,
    equal_width_line,
    recover_active_start,
    spearman,
    width_bin,
)

ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_diagnosis_leaves_the_evaluator_digest_and_result_route():
    before = _sha(RESULT_JSON)
    manifest = evaluate.code_digest()["code_digest"]
    assert manifest == json_digest_pin()
    official = __import__("json").loads(RESULT_JSON.read_text(encoding="utf-8"))
    assert official["route"] == OFFICIAL_ROUTE
    assert _sha(RESULT_JSON) == before
    source = (ROOT / "scripts" / "research" / "frozen_hour_range_post_outcome_diagnosis_v1.py").read_text()
    assert "POST_OUTCOME_DIAGNOSIS" in source
    assert "RESULT_JSON.write" not in source
    assert "RESULT_MD.write" not in source


def json_digest_pin() -> str:
    text = (ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_EVALUATOR_MANIFEST.json").read_text()
    return __import__("json").loads(text)["code_digest"]


def test_active_start_is_unique_for_every_frozen_hour():
    for offset in K.ANCHORS.values():
        active = 3 * K.BARS_PER_DAY + offset + K.FORMATION_BARS
        assert recover_active_start(active, offset) == active
        assert recover_active_start(active + K.ACTIVE_LIFE_BARS - 1, offset) == active
        with pytest.raises(RuntimeError):
            recover_active_start(active + K.ACTIVE_LIFE_BARS, offset)


def test_barrier_detail_matches_the_frozen_score():
    high = np.full(48, 105.0)
    low = np.full(48, 101.0)
    quiet = barrier_detail(high, low, 110.0, 90.0, "high")
    assert quiet["resolution"] == 0.0
    assert quiet["first_barrier_bar"] is None
    high = high.copy()
    high[5] = 120.0
    extended = barrier_detail(high, low, 110.0, 90.0, "high")
    frozen = outcomes.score_window(high, low, 110.0, 90.0, "high")
    assert extended["extension_first"] == frozen["extension_first"] == 1.0
    assert extended["first_barrier_bar"] == 5
    low = low.copy()
    low[2] = 100.0
    reentry = barrier_detail(high, low, 110.0, 90.0, "high")
    assert reentry["resolution"] == 1.0
    assert reentry["extension_first"] == 0.0
    assert reentry["first_barrier_bar"] == 2


def test_spearman_and_width_bins_and_equal_width_line():
    same = spearman([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
    opposite = spearman([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0])
    tied = spearman([1.0, 1.0, 2.0], [1.0, 1.0, 2.0])
    assert same["rho"] == pytest.approx(1.0)
    assert opposite["rho"] == pytest.approx(-1.0)
    assert tied["rho"] == pytest.approx(1.0)
    assert width_bin(0.79) == "PSEUDO_WIDER"
    assert width_bin(0.8) == "SIMILAR"
    assert width_bin(1.25) == "SIMILAR"
    assert width_bin(1.26) == "REAL_WIDER"
    flat = [
        {"resolution_real": 0.7, "resolution_pseudo": 0.5, "width_ratio": 1.0},
        {"resolution_real": 0.6, "resolution_pseudo": 0.4, "width_ratio": 1.0},
        {"resolution_real": 0.8, "resolution_pseudo": 0.9, "width_ratio": 2.0},
    ]
    line = equal_width_line(flat)
    assert line["role"] == "EXPLORATORY_POST_OUTCOME"
    assert line["not_a_confirmation"] is True
    y = np.array([0.2, 0.2, -0.1])
    x = np.log(np.array([1.0, 1.0, 2.0]))
    design = np.column_stack([np.ones(3), x])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    assert line["intercept_at_equal_width"] == pytest.approx(float(coef[0]))
