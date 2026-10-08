"""Opening-range design guards. Synthetic bars only. No resolution label."""

from __future__ import annotations

import ast
import datetime as dt
import math
from pathlib import Path

import numpy as np

from beta.hist_series import BAR_MS, BARS_PER_DAY, empty_bars
from scripts.research.opening_range_object_v1 import census, constants as K

PKG = Path(__file__).resolve().parents[2] / "scripts" / "research" / "opening_range_object_v1"
DESIGN = Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_DESIGN.md"
UTC = dt.timezone.utc


def _source(name: str) -> str:
    return (PKG / name).read_text()


def _imports(name: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(_source(name))):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _monday_panel(n_days: int = 15) -> tuple:
    t0 = int(dt.datetime(2020, 1, 6, tzinfo=UTC).timestamp() * 1000)
    bars = empty_bars(t0, n_days * BARS_PER_DAY)
    return bars, t0


def _paint_monday(bars, day_index: int, *, or_high: float, or_low: float, p0: float) -> None:
    base = day_index * BARS_PER_DAY
    for i in range(K.FORMATION_BARS):
        bars.open[base + i] = p0
        bars.high[base + i] = p0
        bars.low[base + i] = p0
        bars.close[base + i] = p0
    bars.high[base + 3] = or_high
    bars.low[base + 7] = or_low
    bars.close[base + 11] = p0
    # First active bar tags the printed high. The next bar is wide enough to tag a transplanted band.
    j = base + K.FORMATION_BARS
    bars.open[j] = p0
    bars.high[j] = or_high
    bars.low[j] = p0
    bars.close[j] = p0
    k = j + 1
    bars.open[k] = p0
    bars.high[k] = 1000.0
    bars.low[k] = p0
    bars.close[k] = p0
    for i in range(k + 1, base + BARS_PER_DAY):
        bars.open[i] = p0
        bars.high[i] = p0
        bars.low[i] = p0
        bars.close[i] = p0


def test_freeze_constants():
    assert K.MODE == "DISCOVERY"
    assert K.FORMATION_BARS == 12
    assert K.ANCHORS == {"UTC_00": 0, "UTC_12": 144}
    assert K.PRIMARY_CELL == "UTC_00" and K.VETO_CELL == "UTC_12"
    assert K.EXTENSION_FRACTION == 0.5
    assert K.PRACTICAL_SCALE == 0.03
    assert K.FOUNDATION_BENCHMARK == 0.08
    assert K.min_paired_for_benchmark() == 614
    assert K.BOOT_SEED == 20261027
    assert K.EXACT_CLAIM_PREVIOUSLY_READ is False
    assert K.NEIGHBORING_PATH_PREVIOUSLY_READ is True
    assert K.information_status(613, 260) == "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"
    assert K.information_status(614, 99) == "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"
    assert K.information_status(614, 100) == "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"
    half = K.planning_half_width(614)
    assert 0.03 < half < K.FOUNDATION_BENCHMARK
    assert K.planning_half_width(1827) > K.PRACTICAL_SCALE


def test_design_note_states_the_freeze():
    text = DESIGN.read_text()
    for phrase in (
        "DISCOVERY",
        "FORMATION_BARS = 12",
        "NEW_MECHANISM",
        "DISCOVERY_ON_EXPOSED_SURFACE",
        "EXACT_CLAIM_PREVIOUSLY_READ = false",
        "NEIGHBORING_PATH_PREVIOUSLY_READ = true",
        "UTC_12",
        "0.03",
        "614",
        "20261027",
        "outcome_read",
        "DH3-V1",
    ):
        assert phrase in text


def test_census_module_has_no_outcome_estimator():
    text = _source("census.py")
    assert "EXTENSION_FRACTION" not in text
    assert text.lower().count("midpoint") == 1
    modules = _imports("census.py")
    assert all("outcome" not in name and "rv" not in name.split(".")[-1] for name in modules)
    assert not (PKG / "outcomes.py").exists()
    assert not (PKG / "evaluate.py").exists()


def test_support_counts_ignore_post_touch_path():
    bars, _ = _monday_panel()
    shapes = {0: (110.0, 90.0), 7: (120.0, 80.0), 14: (115.0, 85.0)}
    for day, (hi, lo) in shapes.items():
        _paint_monday(bars, day, or_high=hi, or_low=lo, p0=100.0)
    other = empty_bars(bars.t0, bars.n)
    for name in ("open", "high", "low", "close"):
        getattr(other, name)[:] = getattr(bars, name)
    # Mutate only bars after both first touches. A resolution score would move; support counts must not.
    base = 0
    spike = base + K.FORMATION_BARS + 2
    other.high[spike:spike + 40] = 10_000.0
    other.low[spike:spike + 40] = 0.5
    left = census.summarize(bars, design_sha256="synthetic")
    right = census.summarize(other, design_sha256="synthetic")
    assert left == right
    assert left["outcome_read"] is False
    cell = left["cells"]["UTC_00"]
    assert cell["usable_geometry"] == 3
    assert cell["first_interaction"] == 3
    assert cell["immediate_interaction"] == 3
    assert cell["high_side_interaction"] == 3
    assert cell["ambiguous_interaction"] == 0
    assert cell["paired_outcome_eligible"] == 3
    assert cell["one_sided_outcome_eligible"] == 3
    noon = left["cells"]["UTC_12"]
    assert noon["formation_incomplete"] == 12
    assert noon["nonpositive_width"] == 3
    assert noon["usable_geometry"] == 0
    assert noon["first_interaction"] == 0
    census.assert_support_only(left)


def test_ambiguous_and_late_and_inside_close_are_support_rules():
    t0 = int(dt.datetime(2020, 1, 6, tzinfo=UTC).timestamp() * 1000)
    bars = empty_bars(t0, BARS_PER_DAY)
    for i in range(BARS_PER_DAY):
        bars.open[i] = 100.0
        bars.high[i] = 101.0
        bars.low[i] = 99.0
        bars.close[i] = 100.0
    bars.high[3] = 110.0
    bars.low[7] = 90.0
    bars.close[11] = 100.0
    # Same active bar meets both bounds.
    j = K.FORMATION_BARS
    bars.high[j] = 110.0
    bars.low[j] = 90.0
    summary = census.summarize(bars, design_sha256="synthetic")
    cell = summary["cells"]["UTC_00"]
    assert cell["ambiguous_interaction"] == 1
    assert cell["one_sided_outcome_eligible"] == 0
    assert cell["paired_outcome_eligible"] == 0

    late = empty_bars(t0, BARS_PER_DAY)
    for i in range(BARS_PER_DAY):
        late.open[i] = 100.0
        late.high[i] = 101.0
        late.low[i] = 99.0
        late.close[i] = 100.0
    late.high[3] = 110.0
    late.low[7] = 90.0
    late.close[11] = 110.0  # decision close sits on the bound
    edge = census.summarize(late, design_sha256="synthetic")
    assert edge["cells"]["UTC_00"]["close_not_strictly_inside"] == 1
    assert edge["cells"]["UTC_00"]["usable_geometry"] == 0

    delayed = empty_bars(t0, BARS_PER_DAY)
    for i in range(BARS_PER_DAY):
        delayed.open[i] = 100.0
        delayed.high[i] = 101.0
        delayed.low[i] = 99.0
        delayed.close[i] = 100.0
    delayed.high[3] = 110.0
    delayed.low[7] = 90.0
    delayed.close[11] = 100.0
    # Touch late enough that 48 bars do not fit before the next midnight.
    delayed.high[250] = 110.0
    delayed.low[250] = 100.0
    got = census.summarize(delayed, design_sha256="synthetic")
    utc = got["cells"]["UTC_00"]
    assert utc["first_interaction"] == 1
    assert utc["immediate_interaction"] == 0
    assert utc["outcome_window_incomplete"] == 1
    assert utc["one_sided_outcome_eligible"] == 0


def test_rotation_is_deterministic_and_skips_a_copy():
    bars, _ = _monday_panel()
    for day in (0, 7):
        _paint_monday(bars, day, or_high=110.0, or_low=90.0, p0=100.0)
    summary = census.summarize(bars, design_sha256="synthetic")
    cell = summary["cells"]["UTC_00"]
    assert cell["usable_geometry"] == 2
    assert cell["partner_not_found"] == 2
    assert cell["paired_outcome_eligible"] == 0
    again = census.summarize(bars, design_sha256="synthetic")
    assert again == summary


def test_half_width_matches_the_conservative_bound():
    n = 614
    expected = K.Z_95 * math.sqrt(K.PLANNING_VARIANCE / n)
    assert K.planning_half_width(n) == expected
    assert np.isfinite(K.planning_half_width(n))
