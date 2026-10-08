"""beta.level_race (HIST line): frozen table, lookup and display rules.

Parity with the research twin lives in tests/research/test_level_race_parity_beta.py
(tests/beta must not import the research package).
"""

from __future__ import annotations

import numpy as np
import pytest

from beta import level_race as L


def test_table_digest_and_lookup():
    t = L.load_hist_table()
    assert t["table_sha256"] == L.HIST_TABLE_SHA256
    g = L.geometry(99850.0, 100150.0, 0.002, 1)
    line = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.002)
    c = t["cells"]["T0|DAY|H"]
    assert line["template"] == "LR_HIST_V1" and line["n"] == c["n"]
    assert line["h"] == {"up": c["h"]["BEYOND"], "dn": c["h"]["BACK"], "neither": c["h"]["NEITHER"]}
    g2 = L.geometry(99850.0, 100150.0, 0.002, -1)        # approach from above: beyond is the lower price
    line2 = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g2, sigma=0.002)
    assert line2["h"]["dn"] == c["h"]["BEYOND"]
    low = L.hist_line(t, landmark="T0", kind="PMH", price=100000.0, geo=g, sigma=0.002)
    assert low["template"] == "LR_HIST_LOW_N_V1" and "h" not in low


def test_t15_eligibility_and_window_end():
    g = {"p_up": 101.0, "p_dn": 99.0}
    high = np.array([100.2] * 10)
    low = np.array([99.8] * 10)
    assert L.t15_eligible(high, low, 3, g)
    high[5] = 101.0
    assert not L.t15_eligible(high, low, 3, g)
    assert L.window_end_ms(0) == 49 * 300_000


def test_percents_sum_to_100():
    assert sum(L.percents({"up": 0.333, "dn": 0.333, "neither": 0.334}).values()) == 100
    assert L.percents({"up": 0.4, "dn": 0.467, "neither": 0.133}) == {"up": 40, "dn": 47, "neither": 13}


def test_t0_out_of_corridor_is_not_displayed_but_flagged():
    t = L.load_hist_table()
    g = L.event_geometry(99850.0, 100150.0, 0.002, 1)
    above = g["p_up"] * 1.001
    line = L.hist_line(t, landmark="T0", kind="PDH", price=above, geo=g, sigma=0.002)
    assert line["out_of_corridor"] is True and line["display"] is False
    assert line["class"] == "L2_LEVEL_RACE_HIST_T0_4H"
    inside = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.002)
    assert inside["out_of_corridor"] is False and inside["display"] is True


def test_hist_line_carries_difference_and_interval():
    t = L.load_hist_table()
    g = L.event_geometry(99850.0, 100150.0, 0.002, 1)
    line = L.hist_line(t, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.002)
    c = t["cells"]["T0|DAY|H"]
    assert line["d_pp"]["up"] == line["printed_h"]["up"] - line["printed_b"]["up"]
    assert line["ci95_pp"]["up"] == [round(c["diff_ci95_pp"]["BEYOND"][0]), round(c["diff_ci95_pp"]["BEYOND"][1])]


def test_t15_visibility_rule():
    g = {"p_up": 101.0, "p_dn": 99.0}
    assert L.t15_visible([100.5], [99.5], 100.0, g, now_ms=1, end_ms=10)
    assert not L.t15_visible([101.0], [99.5], 100.0, g, now_ms=1, end_ms=10)      # resolved
    assert not L.t15_visible([100.5], [99.5], 101.2, g, now_ms=1, end_ms=10)      # price beyond P_UP
    assert not L.t15_visible([100.5], [99.5], 100.0, g, now_ms=10, end_ms=10)     # window over
    assert not L.t15_visible([100.5], [99.5], 100.0, g, now_ms=1, end_ms=10, was_hidden=True)


def test_shown_difference_equals_shown_percentages_when_rounding_diverges():
    cell = {"n": 100, "weeks": 90, "h": {"BEYOND": 0.354, "BACK": 0.300, "NEITHER": 0.346},
            "b": {"BEYOND": 0.365, "BACK": 0.290, "NEITHER": 0.345},
            "diff_pp": {"BEYOND": -1.1, "BACK": 1.0, "NEITHER": 0.1},
            "diff_ci95_pp": {"BEYOND": [-6.4, 4.4], "BACK": [-3.6, 5.5], "NEITHER": [-4.0, 4.2]},
            "k_pp": {"BEYOND": 6, "BACK": 5, "NEITHER": 5}}
    table = {"version": "T", "table_sha256": "x", "cells": {"T0|DAY|H": cell},
             "ladder": {"T0|DAY|H": {"level": "CELL", "source": "T0|DAY|H"}}}
    g = L.event_geometry(99850.0, 100150.0, 0.002, 1)
    line = L.hist_line(table, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.002)
    # printed 35 vs 37 (b rounds up by largest remainder) -> shown difference -2, not round(-1.1) = -1
    assert line["printed_h"]["up"] - line["printed_b"]["up"] == line["d_pp"]["up"]
    assert line["d_pp"]["up"] != round(cell["diff_pp"]["BEYOND"])
    assert line["ci95_pp"]["up"] == [-6, 4]
    assert sum(line["printed_h"].values()) == sum(line["printed_b"].values()) == 100


def test_table_file_digest_covers_provenance(tmp_path):
    import json
    raw = L.HIST_TABLE_PATH.read_bytes()
    t = json.loads(raw)
    t["provenance"]["design_sha"] = "deadbeef"
    t["provenance"]["years"] = [2020, 2021, 2022, 2023, 2024, 2025]
    bad = tmp_path / "t.json"
    bad.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")
    with pytest.raises(RuntimeError):
        L.load_hist_table(bad)
    same = tmp_path / "same.json"
    same.write_bytes(raw)
    assert L.load_hist_table(same)["table_sha256"] == L.HIST_TABLE_SHA256
    flipped = tmp_path / "flip.json"
    flipped.write_bytes(raw.replace(b"2020", b"2021", 1))
    with pytest.raises(RuntimeError):
        L.load_hist_table(flipped)


def test_cell_key_format():
    assert L.cell_key("T0", "PDH") == "T0|DAY|H"
    assert L.cell_key("T15", "PWL", 0.5) == "T15|WEEK|L|F2"


def test_model_file_digest_and_raw_forecasts(tmp_path):
    m = L.load_model()
    assert m["champion"] == "M1" and m["version"] == "LEVEL_RACE_MODEL_V1"
    g = L.event_geometry(99850.0, 100150.0, 0.0015, 1)
    out = L.raw_forecasts(m, landmark="T0", kind="PDH", price=100000.0, geo=g, sigma=0.0015)
    for k in ("b0", "m1", "g1", "c1"):
        assert abs(sum(out["break_order"][k]) - 1) < 1e-9
        assert out["display"][k]["up"] == out["break_order"][k][0]      # approach from below: beyond = up
    t15 = L.raw_forecasts(m, landmark="T15", kind="PDH", price=100000.0, geo=g, sigma=0.0015)
    assert "c1" not in t15["break_order"]                                # no cross-venue move -> no C1
    bad = tmp_path / "m.json"
    bad.write_bytes(L.MODEL_PATH.read_bytes().replace(b"M1", b"M2", 1))
    with pytest.raises(RuntimeError):
        L.load_model(bad)
