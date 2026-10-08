"""Synthetic guards for the equal-width support census. No spot zip is opened."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.frozen_hour_equal_width_v1 import census, constants as K, data, evaluate
from scripts.research.frozen_hour_equal_width_v1.solver import solve_equal_width

ROOT = Path(__file__).resolve().parents[2]


def test_solver_matches_the_symmetric_closed_form_and_keeps_asymmetry():
    p0 = 100.0
    u = math.log(1.02)
    w = 5.0
    got = solve_equal_width(p0, w, u, u)
    assert got["status"] == "ok"
    assert got["rel_width_error"] <= 1e-9
    assert got["k"] == pytest.approx(math.asinh(w / (2.0 * p0)) / u, rel=1e-8)
    u2, d2 = math.log(1.03), math.log(1.01)
    wide = solve_equal_width(p0, 8.0, u2, d2)
    assert wide["status"] == "ok"
    ku = math.log(wide["pseudo_high"] / p0)
    kd = math.log(p0 / wide["pseudo_low"])
    assert (ku - kd) / (ku + kd) == pytest.approx((u2 - d2) / (u2 + d2), abs=1e-12)
    assert solve_equal_width(100.0, 50.0, 1e-20, 1e-20)["status"] == "scale_unbounded"


def test_month_selector_stays_inside_the_frozen_window():
    months = data.allowed_months()
    assert months[0] == "2017-09" and months[-1] == "2019-12" and len(months) == 28
    inventory = json.loads((ROOT / "docs/research_data/DH1_BINANCE_SPOT_BTCUSDT_5M_V0/SOURCE_INVENTORY.json").read_text())
    chosen = data.select_objects(inventory)
    assert [obj["MONTH"] for obj in chosen] == months
    for month in ("2017-08", "2020-01", "2024-12", "2025-01", "2026-01"):
        with pytest.raises(RuntimeError):
            data.refuse_month(month)
    with pytest.raises(RuntimeError):
        data.place_on_grid([K.SURFACE_END_MS], [1.0], [1.0], [1.0])
    start = K.EVENT_START_MS
    high, low, close, present, excluded = data.place_on_grid(
        [start, start + K.BAR_MS + 194789, start + 2 * K.BAR_MS],
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0],
    )
    assert excluded == 1 and present == 2
    assert high[0] == 1.0 and high[2] == 3.0 and np.isnan(high[1])
    with pytest.raises(RuntimeError):
        data.place_on_grid([K.EVENT_START_MS - K.BAR_MS], [1.0], [1.0], [1.0])


def test_joint_gate_stops_when_either_cell_is_short():
    assert K.joint_information(K.ADEQUATE, K.ADEQUATE) == K.ADEQUATE
    assert K.joint_information(K.ADEQUATE, K.LIMITED) == K.LIMITED
    assert K.joint_information(K.LIMITED, K.ADEQUATE) == K.LIMITED
    assert K.information_status(614, 100) == K.ADEQUATE
    assert K.information_status(613, 100) == K.LIMITED
    assert K.information_status(614, 99) == K.LIMITED


def _day_slice(day: int) -> slice:
    start = day * K.BARS_PER_DAY
    return slice(start, start + 81)


def _paint(high, low, close, day: int, hi: float, lo: float, p0: float, touch_at: int, touch_high: float, touch_low: float):
    sl = _day_slice(day)
    high[sl] = p0
    low[sl] = p0
    close[sl] = p0
    form = day * K.BARS_PER_DAY
    high[form:form + 12] = hi
    low[form:form + 12] = lo
    close[form:form + 12] = p0
    j = form + K.FORMATION_BARS + touch_at
    high[j] = touch_high
    low[j] = touch_low


def test_census_counts_support_and_does_not_score_a_barrier():
    n = 14 * K.BARS_PER_DAY
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    close = np.full(n, np.nan)
    # Two identical Mondays: the scale matches the printed bounds and collides.
    _paint(high, low, close, 0, 110.0, 90.0, 100.0, 0, 100.0, 100.0)
    _paint(high, low, close, 7, 110.0, 90.0, 100.0, 0, 100.0, 100.0)
    high[0:12] = 110.0
    low[0:12] = 90.0
    high[7 * K.BARS_PER_DAY:7 * K.BARS_PER_DAY + 12] = 110.0
    low[7 * K.BARS_PER_DAY:7 * K.BARS_PER_DAY + 12] = 90.0
    # Two different Tuesdays. The touch is after the first active bar, and a later
    # bar trades far through any 0.5W mark. That bar is availability only.
    _paint(high, low, close, 1, 110.0, 90.0, 100.0, 10, 1.0e6, 100.0)
    _paint(high, low, close, 8, 104.0, 97.0, 100.0, 10, 1.0e6, 100.0)
    high[1 * K.BARS_PER_DAY + 40] = 1.0e6
    t0 = K._ms("2018-01-01")
    payload = census.summarize(
        high, low, close, t0,
        provenance={"present_bars": 0, "missing_bars": 0, "grid_bars": n, "months": ["synthetic"]},
        design_sha256_hex="synthetic",
    )
    cell = payload["cells"]["UTC_00"]
    assert cell["usable_real_geometry"] == 4
    assert cell["collisions"] == 2
    assert cell["partner_not_found"] == 2
    assert cell["valid_equal_width_pseudo_geometry"] == 2
    assert cell["solver_success"] == 4
    assert cell["scale_unbounded"] == 0
    assert cell["scale_tolerance_failed"] == 0
    assert cell["paired_outcome_eligible"] == 2
    assert cell["paired_neither_immediate"] == 2
    assert cell["immediate_real"] == 0
    assert cell["one_sided_outcome_eligible_real"] == 2
    assert cell["information_status"] == K.LIMITED
    assert payload["information_gate"] == K.LIMITED
    assert payload["outcome_read"] is False
    assert payload["barrier_path_read"] is False
    dumped = json.dumps(payload)
    for token in ("resolution", "extension", "reentry", "excursion", "occupancy", "pair_delta"):
        assert token not in dumped
    census.assert_support_only(payload)


def test_ambiguous_and_incomplete_windows_are_not_eligible():
    n = 14 * K.BARS_PER_DAY
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    close = np.full(n, np.nan)
    _paint(high, low, close, 0, 110.0, 90.0, 100.0, 0, 200.0, 50.0)
    _paint(high, low, close, 7, 104.0, 97.0, 100.0, 0, 200.0, 50.0)
    close[K.FORMATION_BARS + 1] = np.nan
    payload = census.summarize(
        high, low, close, K._ms("2018-01-01"),
        provenance={"present_bars": 0, "missing_bars": 0, "grid_bars": n, "months": ["synthetic"]},
        design_sha256_hex="synthetic",
    )
    cell = payload["cells"]["UTC_00"]
    assert cell["ambiguous_real"] == 2
    assert cell["immediate_real"] == 2
    assert cell["one_sided_outcome_eligible_real"] == 0
    assert cell["paired_outcome_eligible"] == 0


def test_outcome_path_checks_support_before_scoring_and_census_refuses_a_second_write(tmp_path, monkeypatch):
    evaluate_source = (ROOT / "scripts/research/frozen_hour_equal_width_v1/evaluate.py").read_text()
    census_source = (ROOT / "scripts/research/frozen_hour_equal_width_v1/census.py").read_text()
    data_source = (ROOT / "scripts/research/frozen_hour_equal_width_v1/data.py").read_text()
    main_source = evaluate_source.split("def main", 1)[1]
    assert main_source.index("REFUSAL_RERUN") < main_source.index("load_panel")
    assert main_source.index("require_live_matches") < main_source.index("score_pairs")
    assert "score_window" not in census_source
    assert "load_spot_5m" not in data_source
    assert "spot_months" not in data_source
    target = tmp_path / "feasibility.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(census, "FEASIBILITY_JSON", target)
    monkeypatch.setattr(census, "FEASIBILITY_MD", tmp_path / "feasibility.md")

    def _boom():
        raise AssertionError("rerun opened the market")

    monkeypatch.setattr(data, "load_panel", _boom)
    with pytest.raises(SystemExit) as exc2:
        census.main()
    assert str(exc2.value) == "REFUSING_RERUN"


def test_official_support_census_matches_the_code_and_refuses_a_rerun():
    path = ROOT / "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_FEASIBILITY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["outcome_read"] is False
    assert payload["barrier_path_read"] is False
    assert payload["labels_computed"] is False
    assert payload["code_digest"] == "803dd81cb9fe981ff1f1e5825702641105f5ca8a6b60a42497ab2c7aefa93bcb"
    assert payload["head"] == "3b02de8380064aa2ce3fe384e86899e08d2b3778"
    assert payload["design_commit"] == K.DESIGN_COMMIT
    assert payload["information_gate"] == K.ADEQUATE
    assert payload["cells"]["UTC_00"]["paired_outcome_eligible"] == 817
    assert payload["cells"]["UTC_00"]["paired_iso_weeks"] == 123
    assert payload["cells"]["UTC_12"]["paired_outcome_eligible"] == 833
    assert payload["cells"]["UTC_12"]["paired_iso_weeks"] == 123
    assert payload["cells"]["UTC_00"]["scale_unbounded"] == 0
    assert payload["cells"]["UTC_12"]["collisions"] == 0
    assert payload["panel_provenance"]["months"][0] == "2017-09"
    assert payload["panel_provenance"]["months"][-1] == "2019-12"
    assert "2020-01" not in payload["panel_provenance"]["months"]
    assert payload["panel_provenance"]["off_grid_rows_not_placed"] == 241
    census.assert_support_only(payload)
    with pytest.raises(SystemExit) as exc:
        census.main()
    assert str(exc.value) == "REFUSING_RERUN"
