"""Opening-range design guards. Synthetic bars only. No resolution label."""

from __future__ import annotations

import ast
import datetime as dt
import json
import math
from pathlib import Path

import pytest

import numpy as np

from beta.hist_series import BAR_MS, BARS_PER_DAY, empty_bars
from scripts.research.opening_range_object_v1 import census, constants as K, evaluate, multiplicity, outcomes, routing, specificity, touch_time

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
    assert K.ANCHORS == {"UTC_00": 0, "UTC_08": 96, "UTC_12": 144, "UTC_16": 192}
    assert K.PRIMARY_CELL == "UTC_00" and K.VETO_CELL == "UTC_12"
    assert K.OBJECT_NAME == "FROZEN_HOUR_RANGE"
    assert K.AMENDMENT == "A1"
    assert K.timing_handling(False, 10, 10) == "PUBLISH_AUDIT_NO_CORRECTION"
    assert K.timing_handling(True, 614, 100) == "PUBLISH_AUDIT_PLUS_NEARBY_SENSITIVITY"
    assert K.timing_handling(True, 100, 100) == "PUBLISH_AUDIT_NEARBY_SENSITIVITY_INFORMATION_LIMITED"
    assert K.timing_imbalance_material(0.25, 0) is True
    assert K.timing_imbalance_material(0.0, 119) is False
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
    assert "EXTENSION_FRACTION" in _source("outcomes.py")
    assert "load_discovery" not in _source("outcomes.py")
    evaluate_src = _source("evaluate.py")
    assert "REFUSING_RERUN" in evaluate_src
    assert "PUBLISH_AUDIT_NO_CORRECTION" in evaluate_src
    assert "REFUSING_OUTCOME_BEFORE_OWNER_GO" in _source("specificity.py")


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


def test_official_census_did_not_read_the_outcome():
    path = Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_FEASIBILITY.json"
    payload = json.loads(path.read_text())
    census.assert_support_only(payload)
    assert payload["design_commit"] == "3be350eb0f71011928b1c99cc92f37059d631252"
    assert payload["information_primary"] == "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"
    assert payload["information_veto"] == "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"
    assert payload["cells"]["UTC_00"]["paired_outcome_eligible"] == 1719
    assert payload["cells"]["UTC_12"]["paired_outcome_eligible"] == 1704
    assert payload["cells"]["UTC_00"]["paired_iso_weeks"] == 262


def test_amendment_audit_did_not_read_the_outcome():
    path = Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A1_CENSUS.json"
    payload = json.loads(path.read_text())
    census.assert_support_only(payload)
    assert payload["outcome_read"] is False
    assert payload["y_known"] is False
    assert payload["original_design_commit"] == "3be350eb0f71011928b1c99cc92f37059d631252"
    assert payload["amendment_commit"] == "fb57fc8df8960e336b6dd779a339ec390b74e76b"
    assert payload["timing_handling"] == "PUBLISH_AUDIT_NO_CORRECTION"
    assert payload["primary_timing_imbalance_material"] is False
    paired = {name: payload["cells"][name]["support"]["paired_outcome_eligible"] for name in K.CLOCK_CELLS}
    assert paired == {"UTC_00": 1719, "UTC_08": 1716, "UTC_12": 1704, "UTC_16": 1698}


def test_half_width_matches_the_conservative_bound():
    n = 614
    expected = K.Z_95 * math.sqrt(K.PLANNING_VARIANCE / n)
    assert K.planning_half_width(n) == expected
    assert np.isfinite(K.planning_half_width(n))


def _est(point, lo, hi):
    return {
        "point": point,
        "marginal_lo": lo,
        "marginal_hi": hi,
        "sim_lo": lo,
        "sim_hi": hi,
    }


def _failed_map():
    return {
        name: {"point": 0.0, "marginal_lo": -0.1, "marginal_hi": 0.1, "holm_p": 1.0}
        for name in K.NONFOUNDATION_ORDER
    }


def _clock(point=0.0, lo=-0.01, hi=0.01):
    return {cell: _est(point, lo, hi) for cell in K.CLOCK_CELLS}


def _info(ok=True):
    status = "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME" if ok else "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"
    return {cell: status for cell in K.CLOCK_CELLS}


def _contrasts(point, lo, hi):
    return {cell: _est(point, lo, hi) for cell in ("UTC_08", "UTC_12", "UTC_16")}


def test_amendment_keeps_opening_as_a_label():
    text = (Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A1.md").read_text()
    for phrase in (
        "3be350eb0f71011928b1c99cc92f37059d631252",
        "outcome_read",
        "FROZEN_HOUR_RANGE",
        "UTC_08",
        "UTC_16",
        "00:00 / 08:00 / 16:00",
        "UTC_DAY_BOUNDARY_RANGE_CANDIDATE",
        "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE",
        "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE",
        "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE",
        "OUTSIDE_OCCUPANCY",
        "OUTWARD_EXCURSION",
        "PUBLISH_AUDIT_NO_CORRECTION",
        "REFUSING_OUTCOME_BEFORE_OWNER_GO",
    ):
        assert phrase in text
    assert "does not close an observable outside this map" in text


def test_routes_use_the_direct_contrast():
    adequate = _info(True)
    failed_map = _failed_map()
    separated = _contrasts(0.06, 0.02, 0.10)
    similar = _contrasts(0.005, -0.01, 0.02)
    foundation = _clock(0.06, 0.02, 0.10)
    day_boundary = routing.decide(adequate, foundation, separated, failed_map)
    assert day_boundary["route"] == "UTC_DAY_BOUNDARY_RANGE_CANDIDATE"
    assert day_boundary["opening_wording_allowed"] is False
    assert day_boundary["hour_adopted"] is None

    generic_f = _clock(0.05, 0.02, 0.08)
    generic = routing.decide(adequate, generic_f, similar, failed_map)
    assert generic["route"] == "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE"

    funding_f = _clock(0.05, 0.02, 0.08)
    funding_f["UTC_12"] = _est(0.0, -0.02, 0.02)
    funding_c = similar | {"UTC_12": _est(0.05, 0.02, 0.08)}
    funding = routing.decide(adequate, funding_f, funding_c, failed_map)
    assert funding["route"] == "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE"

    # Other cells fail, and the contrasts also fail: not day-boundary.
    weak = routing.decide(adequate, _clock(0.06, 0.02, 0.10) | {
        "UTC_08": _est(0.0, -0.02, 0.02),
        "UTC_12": _est(0.0, -0.02, 0.02),
        "UTC_16": _est(0.0, -0.02, 0.02),
    }, similar, failed_map)
    assert weak["route"] == "INCONCLUSIVE"

    null = routing.decide(adequate, _clock(0.0, -0.02, 0.02), similar, failed_map)
    assert null["route"] == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"
    assert null["nonfoundation_candidates"] == []

    mixed = _clock(0.0, -0.02, 0.02)
    mixed["UTC_08"] = _est(0.06, 0.02, 0.10)
    assert routing.decide(adequate, mixed, similar, failed_map)["route"] == "INCONCLUSIVE"

    map_rows = _failed_map()
    map_rows["OUTWARD_EXCURSION"] = {
        "point": 0.4,
        "marginal_lo": 0.1,
        "marginal_hi": 0.7,
        "holm_p": 0.01,
    }
    found = routing.decide(adequate, _clock(0.0, -0.02, 0.02), similar, map_rows)
    assert found["route"] == "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00"
    assert found["nonfoundation_candidates"] == [
        {"row": "OUTWARD_EXCURSION", "role": "INDEPENDENT_OBSERVABLE"},
    ]

    # A marginal interval that excludes 0 is not a candidate when Holm does not clear.
    marginal_only = _failed_map()
    marginal_only["DIRECTION_EXTENSION_FIRST"] = {
        "point": 0.05,
        "marginal_lo": 0.02,
        "marginal_hi": 0.08,
        "holm_p": 0.20,
    }
    assert routing.decide(adequate, _clock(0.0, -0.02, 0.02), similar, marginal_only)["route"] == (
        "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"
    )

    both = _failed_map()
    both["DIRECTION_EXTENSION_FIRST"] = {"point": 0.04, "marginal_lo": 0.02, "marginal_hi": 0.06, "holm_p": 0.01}
    both["OUTWARD_EXCURSION"] = {"point": 0.90, "marginal_lo": 0.4, "marginal_hi": 1.2, "holm_p": 0.01}
    listed = routing.decide(adequate, _clock(0.0, -0.02, 0.02), similar, both)
    assert [item["row"] for item in listed["nonfoundation_candidates"]] == [
        "DIRECTION_EXTENSION_FIRST",
        "OUTWARD_EXCURSION",
    ]
    assert listed["nonfoundation_candidates"][0]["role"] == "BARRIER_FAMILY_DECOMPOSITION"

    limited = _info(False)
    assert routing.decide(limited, foundation, separated, failed_map)["route"] == "INFORMATION_LIMITED"
    partial = _info(True)
    partial["UTC_08"] = "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"
    assert routing.decide(partial, foundation, separated, failed_map)["route"] == "CLOCK_SPECIFICITY_INFORMATION_LIMITED"

    negative = _clock(-0.06, -0.10, -0.02)
    neg_c = _contrasts(-0.06, -0.10, -0.02)
    assert routing.decide(adequate, negative, neg_c, failed_map)["route"] == "UTC_DAY_BOUNDARY_RANGE_CANDIDATE"

    # Simultaneous interval includes 0. The marginal interval does not. Route follows simultaneous.
    crowded = _clock(0.0, -0.02, 0.02)
    crowded["UTC_00"] = {
        "point": 0.06,
        "marginal_lo": 0.02,
        "marginal_hi": 0.10,
        "sim_lo": -0.01,
        "sim_hi": 0.13,
    }
    assert routing.decide(adequate, crowded, similar, failed_map)["route"] == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"


def test_max_t_is_wider_than_three_marginal_intervals():
    # UTC_08 marginal percentile stays positive. Six joint draws of UTC_12 are far
    # enough that the family critical value covers the UTC_08 point.
    point = {"UTC_08": 0.04, "UTC_12": 0.0, "UTC_16": 0.0}
    draws = []
    for i in range(100):
        draws.append({
            "UTC_08": 0.05 if i < 50 else 0.03,
            "UTC_12": 1.0 if i < 6 else 0.0,
            "UTC_16": 0.0,
        })
    marginal_lo, marginal_hi = multiplicity.marginal_percentile([draw["UTC_08"] for draw in draws])
    simultaneous = multiplicity.simultaneous_max_t(point, draws)
    assert marginal_lo > 0.0
    assert marginal_hi > marginal_lo
    assert simultaneous["UTC_08"]["sim_lo"] < 0.0 < simultaneous["UTC_08"]["sim_hi"]
    assert simultaneous["UTC_08"]["critical"] > 1.96
    foundation = {
        cell: {"point": 0.0, "sim_lo": -0.02, "sim_hi": 0.02}
        for cell in K.CLOCK_CELLS
    }
    contrasts = {
        cell: {
            "point": point[cell],
            "marginal_lo": marginal_lo if cell == "UTC_08" else -0.05,
            "marginal_hi": marginal_hi if cell == "UTC_08" else 0.05,
            "sim_lo": simultaneous[cell]["sim_lo"],
            "sim_hi": simultaneous[cell]["sim_hi"],
        }
        for cell in ("UTC_08", "UTC_12", "UTC_16")
    }
    route = routing.decide(_info(True), foundation, contrasts, _failed_map())
    assert route["route"] == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"


def test_holm_keeps_a_marginal_p_inside_the_map_family():
    adjusted = multiplicity.holm_adjusted({
        "DIRECTION_EXTENSION_FIRST": 0.02,
        "OUTSIDE_OCCUPANCY": 0.04,
        "OUTWARD_EXCURSION": 0.50,
    })
    assert adjusted["DIRECTION_EXTENSION_FIRST"] == pytest.approx(0.06)
    assert adjusted["OUTSIDE_OCCUPANCY"] > 0.05
    assert adjusted["OUTWARD_EXCURSION"] > adjusted["OUTSIDE_OCCUPANCY"]
    assert multiplicity.bootstrap_p_value(0.0, [0.1, -0.2, 0.3]) == 1.0
    # Replicates centered on the estimate put 0 far into the tail only when the
    # estimate itself is large relative to that spread. A zero estimate does not.


def test_amendment_a2_is_interpretation_only():
    text = (Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A2.md").read_text()
    for phrase in (
        "3be350eb0f71011928b1c99cc92f37059d631252",
        "fb57fc8df8960e336b6dd779a339ec390b74e76b",
        "outcome_read = false",
        "y_known = false",
        "FOUNDATION_CELL_EFFECTS",
        "CLOCK_SPECIFICITY",
        "NONFOUNDATION_MAP",
        "STUDENTIZED_MAX_T",
        "HOLM",
        "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00",
        "BARRIER_FAMILY_DECOMPOSITION",
        "REFUSING_OUTCOME_BEFORE_OWNER_GO",
    ):
        assert phrase in text
    assert "load_discovery" not in _source("multiplicity.py")
    assert "EXTENSION_FRACTION" not in _source("multiplicity.py")


def test_joint_draw_uses_one_week_multiplicity():
    sums = {
        "UTC_00": {"w0": (2.0, 2), "w1": (0.0, 2)},
        "UTC_08": {"w0": (0.0, 2), "w1": (2.0, 2)},
        "UTC_12": {"w0": (1.0, 2), "w1": (1.0, 2)},
        "UTC_16": {"w0": (4.0, 2), "w1": (0.0, 2)},
    }
    got = specificity.one_draw(sums, {"w0": 2, "w1": 0})
    assert got["means"]["UTC_00"] == 1.0
    assert got["means"]["UTC_08"] == 0.0
    assert got["contrasts"]["UTC_08"] == 1.0
    assert got["contrasts"]["UTC_16"] == 1.0 - 2.0
    assert specificity.one_draw(sums, {"w0": 0, "w1": 0}) is None


def test_evaluator_manifest_is_pre_outcome():
    path = Path(__file__).resolve().parents[2] / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_EVALUATOR_MANIFEST.json"
    manifest = json.loads(path.read_text())
    assert manifest["outcome_read"] is False
    assert manifest["y_known"] is False
    assert manifest["code_digest"] == evaluate.code_digest()["code_digest"]


def test_evaluator_refuses_a_second_official_write(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(evaluate, "RESULT_JSON", target)
    monkeypatch.setattr(evaluate, "RESULT_MD", tmp_path / "result.md")
    with pytest.raises(SystemExit) as exc:
        evaluate.write_result({"route": "INCONCLUSIVE"})
    assert str(exc.value) == "REFUSING_RERUN"
    with pytest.raises(SystemExit) as exc2:
        specificity.main()
    assert str(exc2.value) == "REFUSING_OUTCOME_BEFORE_OWNER_GO"


def test_score_window_follows_the_frozen_barriers():
    high = np.full(48, 100.0)
    low = np.full(48, 100.0)
    quiet = outcomes.score_window(high, low, 110.0, 90.0, "high")
    assert quiet["resolution"] == 1.0
    assert quiet["extension_first"] == 0.0
    assert quiet["outward_excursion"] == 0.0
    extended = high.copy()
    extended[3] = 130.0
    hit = outcomes.score_window(extended, low, 110.0, 90.0, "high")
    assert hit["resolution"] == 1.0
    assert hit["extension_first"] == 0.0
    clear_low = np.full(48, 105.0)
    first = clear_low.copy()
    first[0] = 130.0
    lead = outcomes.score_window(first, clear_low, 110.0, 90.0, "high")
    assert lead["extension_first"] == 1.0
    assert lead["outward_excursion"] == pytest.approx(1.0)
    both_high = high.copy()
    both_low = low.copy()
    both_high[0] = 130.0
    both_low[0] = 90.0
    tied = outcomes.score_window(both_high, both_low, 110.0, 90.0, "high")
    assert tied["resolution"] == 1.0
    assert tied["extension_first"] == 0.0
    assert tied["both_barriers_on_first_hit"] is True
    down_high = np.full(48, 99.0)
    down_low = np.full(48, 95.0)
    down_low[0] = 70.0
    lower = outcomes.score_window(down_high, down_low, 110.0, 90.0, "low")
    assert lower["extension_first"] == 1.0
    assert lower["outward_excursion"] == pytest.approx(1.0)
    outside_high = np.full(48, 130.0)
    outside_low = np.full(48, 120.0)
    occupied = outcomes.score_window(outside_high, outside_low, 110.0, 90.0, "high")
    assert occupied["outside_share"] == 1.0


def test_painted_monday_scores_match_the_window_after_the_touch():
    bars, _ = _monday_panel()
    shapes = {0: (110.0, 90.0), 7: (120.0, 80.0), 14: (115.0, 85.0)}
    for day, (hi, lo) in shapes.items():
        _paint_monday(bars, day, or_high=hi, or_low=lo, p0=100.0)
    collected = evaluate.collect_pairs(bars.high, bars.low, bars.close, int(bars.t0))
    assert len(collected["UTC_00"]["pairs"]) == 3
    assert collected["UTC_08"]["pairs"] == []
    scored = evaluate.score_pairs(bars.high, bars.low, collected["UTC_00"]["pairs"])
    resolution = evaluate._arm_summary(scored, "resolution")
    direction = evaluate._arm_summary(scored, "extension_first")
    outside = evaluate._arm_summary(scored, "outside_share")
    excursion = evaluate._arm_summary(scored, "outward_excursion")
    assert resolution["paired_effect"] == 0.0
    # The wide bar's low sits on the midpoint, so the first hit is both barriers.
    assert direction["paired_effect"] == 0.0
    assert sum(row["both_barriers_real"] for row in scored) == 3
    assert outside["paired_effect"] == 0.0
    assert excursion["paired_effect"] == pytest.approx(22.0 / 3.0)


def test_zero_map_on_an_adequate_sample_is_not_a_candidate():
    rows = []
    for i in range(614):
        rows.append({
            "year": 2020 + (i % 5),
            "iso_year": 2020 + (i // 120),
            "iso_week": (i % 120) + 1,
            "real_side": "high" if i % 2 == 0 else "low",
            "resolution_real": 0.0,
            "resolution_pseudo": 0.0,
            "extension_first_real": 0.0,
            "extension_first_pseudo": 0.0,
            "outside_share_real": 0.0,
            "outside_share_pseudo": 0.0,
            "outward_excursion_real": 0.0,
            "outward_excursion_pseudo": 0.0,
            "both_barriers_real": False,
            "both_barriers_pseudo": False,
        })
    counts = {
        "paired_iso_weeks": 120,
        "information_status": K.information_status(614, 120),
    }
    inferred = evaluate.analyze_scored(
        {name: rows for name in K.CLOCK_CELLS},
        counts_by_cell={name: counts for name in K.CLOCK_CELLS},
    )
    assert inferred["route"] == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"
    assert inferred["opening_wording_allowed"] is False
    assert inferred["hour_adopted"] is None
    assert inferred["nonfoundation_candidates"] == []
    assert inferred["claim"] == "L0_NO_CANDIDATE_ON_THIS_MAP"
    assert inferred["foundation"]["UTC_00"]["passes_family_rule"] is False
    assert inferred["stability"]["UTC_00"]["calendar_year"]["2020"]["eligible"] is True
    assert inferred["stability"]["UTC_00"]["calendar_year"]["2020"]["paired_effect"] == 0.0
    assert inferred["stability"]["UTC_00"]["real_side"]["high"]["eligible"] is True


def test_touch_time_audit_ignores_the_post_touch_path():
    bars, _ = _monday_panel()
    shapes = {0: (110.0, 90.0), 7: (120.0, 80.0), 14: (115.0, 85.0)}
    for day, (hi, lo) in shapes.items():
        _paint_monday(bars, day, or_high=hi, or_low=lo, p0=100.0)
    other = empty_bars(bars.t0, bars.n)
    for name in ("open", "high", "low", "close"):
        getattr(other, name)[:] = getattr(bars, name)
    spike = K.FORMATION_BARS + 2
    other.high[spike:spike + 40] = 10_000.0
    other.low[spike:spike + 40] = 0.5
    left = touch_time.audit(bars, amendment_commit="synthetic")
    right = touch_time.audit(other, amendment_commit="synthetic")
    assert left == right
    assert left["outcome_read"] is False
    assert left["y_known"] is False
    primary = left["cells"]["UTC_00"]["touch_time"]
    assert primary["paired_n"] == 3
    assert primary["far_240m_n"] == 0
    assert primary["timing_imbalance_material"] is False
    assert left["timing_handling"] == "PUBLISH_AUDIT_NO_CORRECTION"
    census.assert_support_only(left)
