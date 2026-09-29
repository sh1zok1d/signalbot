"""Pinned C020 holiday calendars: provenance only, no market semantics."""

import json
from pathlib import Path

from scripts.research.c020_holiday_calendar_pin_v0 import (
    CANONICAL_YEARS,
    CN_ID,
    NYSE_ID,
    OPM_ID,
    dataset_digest,
    sha256_hex,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "research_data"


def _load(dataset_id: str, name: str):
    return json.loads((DATA / dataset_id / name).read_text())


def test_first_party_authority_and_distinct_roles():
    nyse = _load(NYSE_ID, "SOURCE_AUTHORITY.json")
    opm = _load(OPM_ID, "SOURCE_AUTHORITY.json")
    cn = _load(CN_ID, "SOURCE_AUTHORITY.json")
    assert nyse["FIRST_PARTY"] and nyse["ROLE"] == "PRIMARY_EVENT_DEFINITION"
    assert opm["ROLE"] == "OTHER_FALSIFIER_SPECIFICITY"
    assert "NYSE" in opm["ROLE_NOTE"]
    assert cn["ROLE"] == "CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION"
    assert nyse["THIRD_PARTY_USED_AS_CANONICAL"] is False


def test_canonical_years_and_no_protected_years():
    for dataset_id in (NYSE_ID, OPM_ID, CN_ID):
        events = _load(dataset_id, "EVENTS.json")
        years = set()
        for row in events:
            if row.get("EVENT_DATE"):
                years.add(int(row["EVENT_DATE"][:4]))
            years.add(int(row["YEAR"]))
        assert years <= set(CANONICAL_YEARS)
        blob = json.dumps(events)
        assert "2025-" not in blob and "2026-" not in blob


def test_digests_and_raw_bytes_rebuild_offline():
    validate()
    for dataset_id in (NYSE_ID, OPM_ID, CN_ID):
        folder = DATA / dataset_id
        manifest = _load(dataset_id, "MANIFEST.json")
        again = dataset_digest(
            _load(dataset_id, "EVENTS.json"),
            _load(dataset_id, "OUT_OF_RANGE_INVENTORY.json"),
            _load(dataset_id, "SOURCE_AUTHORITY.json"),
            _load(dataset_id, "SNAPSHOT_LEDGER.json"),
        )
        assert again == manifest["CANONICAL_DATASET_DIGEST"]
        for rel, digest in manifest["RAW_FILE_DIGESTS_SHA256"].items():
            assert sha256_hex((folder / rel).read_bytes()) == digest


def test_point_in_time_fields_and_nyse_closure_split():
    events = _load(NYSE_ID, "EVENTS.json")
    full = [r for r in events if r["EVENT_TYPE"] == "FULL_DAY_CLOSURE"]
    early = [r for r in events if r["EVENT_TYPE"] == "EARLY_CLOSE"]
    assert full and early
    assert {r["EVENT_DATE"] for r in full}.isdisjoint({r["EVENT_DATE"] for r in early})
    assert all(r["POINT_IN_TIME_STATUS"] == "VERIFIED_PREANNOUNCED" for r in full)
    assert all(r["PRIMARY_FOR_LEAD_ARM"] for r in full)
    assert all(not r["PRIMARY_FOR_LEAD_ARM"] for r in early)
    july3 = next(r for r in full if r["EVENT_DATE"] == "2020-07-03")
    assert july3["NOMINAL_DATE"] == "2020-07-04"
    assert any(r["EVENT_DATE"] == "2020-12-24" and r["EVENT_TYPE"] == "EARLY_CLOSE" for r in early)
    ids = [r["EVENT_ID"] for r in events]
    assert len(ids) == len(set(ids))


def test_opm_nominal_observed_and_china_workdays():
    opm = _load(OPM_ID, "EVENTS.json")
    july = next(r for r in opm if r["EVENT_DATE"] == "2020-07-03")
    assert july["NOMINAL_DATE"] == "2020-07-04"
    assert july["OBSERVED_DIFFERS_FROM_NOMINAL"] is True
    assert july["DOES_NOT_PROVE_NYSE_CLOSURE"] is True
    cn = _load(CN_ID, "EVENTS.json")
    work = {r["EVENT_DATE"] for r in cn if r["EVENT_TYPE"] == "COMPENSATING_WORKING"}
    off = {r["EVENT_DATE"] for r in cn if r["EVENT_TYPE"] == "NON_WORKING"}
    assert "2020-01-19" in work
    assert "2020-01-24" in off
    assert work.isdisjoint(off)
    ids = [r["EVENT_ID"] for r in cn]
    assert len(ids) == len(set(ids))


def test_no_market_or_inference_imports():
    text = (ROOT / "scripts/research/c020_holiday_calendar_pin_v0.py").read_text()
    for banned in ("CORE_BTC", "quote_volume", "power_simulation", "gv0r01_c020_design", "pandas_market"):
        assert banned not in text
    for dataset_id in (NYSE_ID, OPM_ID, CN_ID):
        assert _load(dataset_id, "MANIFEST.json")["MARKET_DATA_PRESENT"] is False
