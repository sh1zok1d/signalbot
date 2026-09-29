"""Outcome-blind tests for the GV0R01-C012 design. No market data."""

from __future__ import annotations

import json

import pytest

from scripts.research import gv0r01_c012_design as D

REQUIRED = {
    "CLAIM", "NULL", "ALTERNATIVE", "PRIMARY_ENDPOINT", "PRIMARY_VARIANT",
    "INFERENCE", "FALSIFIERS", "OVERLAP_POLICY", "MISSING_DATA_POLICY",
    "OUTLIER_POLICY", "PRE_CUTOFF_GAP_POLICY", "MULTIPLE_TESTING_POLICY",
    "OUTCOME_BLIND_GATE", "POWER", "EVENTS", "MARKET_DATA_OPENED",
}


@pytest.fixture(scope="module")
def doc():
    return D.design_document()


def test_written_contract_matches_rebuild():
    assert D.validate_written() == []


def test_schema_and_single_primary(doc):
    assert REQUIRED <= set(doc)
    assert doc["PRIMARY_VARIANT"] == {"EVENT_SET": "FOMC_AND_CPI", "PRE_WINDOW_H": 24}
    assert sum(v["ROLE"] == "PRIMARY" for v in doc["CARD_VARIANTS"]) == 1
    assert doc["PRIMARY_ENDPOINT"].startswith("DELTA_24")


def test_event_universe_and_digest(doc):
    assert doc["DATASETS"]["CPI"]["DIGEST"] == D.DATASET_DIGEST
    manifest = json.loads((D.CPI_DIR / "MANIFEST.json").read_text())
    assert manifest["CANONICAL_DATASET_DIGEST"] == D.DATASET_DIGEST
    assert doc["UNIVERSE_SUMMARY"]["CPI_N"] == 60
    assert doc["UNIVERSE_SUMMARY"]["FOMC_N"] == 39
    assert doc["UNIVERSE_SUMMARY"]["EVENT_N"] == 99
    cpi_ids = {e["EVENT_ID"] for e in doc["EVENTS"] if e["FAMILY"] == "CPI"}
    canonical = {e["EVENT_ID"] for e in json.loads((D.CPI_DIR / "EVENTS.json").read_text())["EVENTS"]}
    inventory = {r["REFERENCE_PERIOD"] for r in json.loads((D.CPI_DIR / "OUT_OF_RANGE_INVENTORY.json").read_text())["REFERENCE_PERIODS"]}
    assert cpi_ids == canonical
    assert not any(e["EVENT_ID"].endswith(p.replace("-", "_")) for e in doc["EVENTS"] for p in inventory if p >= "2025-01")
    assert all(e["RELEASE_UTC"] < "2025-01-01" for e in doc["EVENTS"])


def test_windows_timezone_and_dst(doc):
    for e in doc["EVENTS"]:
        release = D.parse_utc(e["RELEASE_UTC"])
        start, end = D.window_bounds(release, 24)
        assert e["WINDOW_END_UTC"] == D.iso_utc(end)
        assert e["WINDOW_START_UTC"] == D.iso_utc(start)
        assert end == release - D.dt.timedelta(minutes=1)
        if e["FAMILY"] == "CPI":
            assert e["UTC_HOUR"] in (12, 13)
            assert e["LOCAL_ZONE_ABBREV"] in ("EST", "EDT")
        else:
            assert e["UTC_HOUR"] in (18, 19)


def test_overlap_and_long_gap_kept(doc):
    ids = {e["EVENT_ID"] for e in doc["EVENTS"]}
    assert doc["UNIVERSE_SUMMARY"]["OVERLAP_PAIRS"] == [
        ["BLS_CPI_REF_2020_05", "FOMC_20200610"],
        ["BLS_CPI_REF_2024_05", "FOMC_20240612"],
    ]
    for pair in doc["UNIVERSE_SUMMARY"]["OVERLAP_PAIRS"]:
        assert set(pair) <= ids
    long_gap = [e for e in doc["EVENTS"] if e["LONG_GAP"]]
    assert len(long_gap) == 11
    assert all(e["FAMILY"] == "CPI" and e["PRE_CUTOFF_GAP_HOURS"] > 720 for e in long_gap)


def test_power_reproducible_and_gate(doc):
    again = D.power_report(D.build_universe())
    assert again == doc["POWER"]
    mde = D.mde_standardized(94 / 2)
    assert doc["POWER"]["SCENARIOS"][-1]["MDE_STANDARDIZED"] == pytest.approx(mde)
    assert doc["OUTCOME_BLIND_GATE"]["STATE"] == "EXECUTION_JUSTIFIED"
    assert doc["EXECUTION_AUTHORIZED"] is False
    weak = dict(doc)
    # A bar below the conservative MDE must not justify execution.
    saved = D.ECONOMIC_BAR_STANDARDIZED
    try:
        D.ECONOMIC_BAR_STANDARDIZED = 0.10
        universe = D.build_universe()
        gate = D.outcome_blind_gate(universe, D.calendar_control_slots(universe["EVENTS"]), D.power_report(universe))
        assert gate["STATE"] == "EXECUTION_INFORMATIONALLY_WEAK"
    finally:
        D.ECONOMIC_BAR_STANDARDIZED = saved


def test_gate_does_not_read_returns(doc):
    assert doc["MARKET_DATA_OPENED"] is False
    assert doc["MARKET_OUTCOMES_COMPUTED"] is False
    assert doc["PROTECTED_2025_VALUES_OPENED"] is False
    D.assert_no_market_access()
    src = open(D.__file__).read()
    assert "read_parquet" not in src
    assert "load_hourly_closes" not in src


def test_known_mde_value():
    # (z_0.975 + z_0.80) / sqrt(47) is the planning MDE.
    assert D.mde_standardized(47) == pytest.approx(0.408653, rel=1e-4)
    assert D.power_at_effect(0.50, 47) > 0.80
    assert D.power_at_effect(0.25, 47) < 0.80
