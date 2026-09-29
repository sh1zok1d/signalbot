"""Offline tests for BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0 (schedule metadata only).

No network, no market data, no CPI values, no protected 2025/2026 outcomes.
"""

from __future__ import annotations

import copy
import json

import pytest

from scripts.research import bls_cpi_schedule_archive_v0 as M

DS = M.DATASET_DIR
TRANSITIONS = M.load_us_transitions()


def _load(name):
    return json.loads((DS / name).read_text())


@pytest.fixture(scope="module")
def built():
    return M.build(DS / "raw")


def test_committed_dataset_validates():
    assert M.validate(DS) == []


def test_files_reproduce_byte_exact_and_digest_stable(built):
    for name, obj in built.items():
        assert (DS / name).read_bytes() == M.dump_json(obj)
    again = M.build(DS / "raw")
    assert M.dataset_digest(built) == M.dataset_digest(again)
    assert _load("MANIFEST.json")["CANONICAL_DATASET_DIGEST"] == M.dataset_digest(built)


def test_manifest_counts():
    m = _load("MANIFEST.json")
    assert m["EVENT_COUNT"] == 60
    assert m["YEAR_COUNTS"] == {str(y): 12 for y in range(2020, 2025)}
    assert (m["SAFE_W6"], m["SAFE_W12"], m["SAFE_W24"]) == (60, 60, 60)
    assert m["UNRESOLVED_COUNT"] == 0 and m["RESCHEDULED_COUNT"] == 0
    assert m["MARKET_DATA_PRESENT"] is False and m["CPI_VALUES_PRESENT"] is False
    for name in M.DATASET_FILES:
        assert m["FILE_DIGESTS_SHA256"][name] == M.sha256_hex((DS / name).read_bytes())


def test_event_schema_and_uniqueness():
    events = _load("EVENTS.json")["EVENTS"]
    assert all(set(e) == set(M.EVENT_FIELDS) for e in events)
    assert len({e["EVENT_ID"] for e in events}) == len(events)
    assert len({e["REFERENCE_PERIOD"] for e in events}) == len(events)
    assert all(e["SERIES"] == M.SERIES for e in events)
    assert {e["PROVENANCE_STATUS"] for e in events} <= set(M.PROVENANCE_STATUSES)
    utcs = [e["SCHEDULED_RELEASE_UTC"] for e in events]
    assert utcs == sorted(utcs) and len(set(utcs)) == len(utcs)
    assert events[0]["REFERENCE_PERIOD"] == "2019-12"
    assert events[-1]["REFERENCE_PERIOD"] == "2024-11"


def test_known_first_and_last_events():
    ev = {e["EVENT_ID"]: e for e in _load("EVENTS.json")["EVENTS"]}
    jan20 = ev["BLS_CPI_REF_2019_12"]
    assert (jan20["SCHEDULED_RELEASE_DATE"], jan20["SCHEDULED_RELEASE_UTC"]) == ("2020-01-14", "2020-01-14T13:30:00Z")
    dec24 = ev["BLS_CPI_REF_2024_11"]
    assert (dec24["SCHEDULED_RELEASE_DATE"], dec24["SCHEDULED_RELEASE_UTC"]) == ("2024-12-11", "2024-12-11T13:30:00Z")
    assert "BLS_CPI_REF_2024_12" not in ev


@pytest.mark.parametrize("day,expected", [
    ("2020-03-06", ("2020-03-06T13:30:00Z", "-05:00", "EST")),
    ("2020-03-09", ("2020-03-09T12:30:00Z", "-04:00", "EDT")),
    ("2020-10-30", ("2020-10-30T12:30:00Z", "-04:00", "EDT")),
    ("2020-11-02", ("2020-11-02T13:30:00Z", "-05:00", "EST")),
    ("2024-03-12", ("2024-03-12T12:30:00Z", "-04:00", "EDT")),
    ("2024-11-13", ("2024-11-13T13:30:00Z", "-05:00", "EST")),
])
def test_dst_conversion(day, expected):
    assert M.local_to_utc(day, "08:30", TRANSITIONS) == expected
    assert M.zoneinfo_utc(day, "08:30") == expected[0]


def test_frozen_dst_table_matches_statute_and_refuses_unknown_year():
    for y, v in TRANSITIONS.items():
        assert M.statutory_us_transitions(y) == v
    with pytest.raises(KeyError):
        M.local_to_utc("2025-01-15", "08:30", TRANSITIONS)
    with pytest.raises(ValueError):
        M.local_to_utc("2020-03-08", "02:30", TRANSITIONS)


def test_every_event_dst_matches_zoneinfo():
    for e in _load("EVENTS.json")["EVENTS"]:
        assert M.zoneinfo_utc(e["SCHEDULED_RELEASE_DATE"], e["SCHEDULED_RELEASE_LOCAL"]) == e["SCHEDULED_RELEASE_UTC"]


def test_evidence_precedes_cutoffs_and_implications():
    for e in _load("EVENTS.json")["EVENTS"]:
        t = M.parse_iso_utc(e["SCHEDULED_RELEASE_UTC"])
        assert not e["SAFE_FOR_W24"] or e["SAFE_FOR_W12"]
        assert not e["SAFE_FOR_W12"] or e["SAFE_FOR_W6"]
        for w in M.WINDOWS_H:
            we = e["WINDOW_EVIDENCE"][f"W{w}"]
            if e[f"SAFE_FOR_W{w}"]:
                assert M.parse_iso_utc(we["LATEST_PRE_CUTOFF_CAPTURE_UTC"]) < t - M.dt.timedelta(hours=w)
                assert we["EVIDENCE_LEAD_HOURS"] > 0


def _obs(ts, day, hhmm="08:30"):
    return (ts, f"WB_{ts}", day, hhmm)


def test_classify_preannounced_and_no_evidence():
    c = M.classify_event("2021-01", [_obs("2020-10-16T22:36:33Z", "2021-02-10")], TRANSITIONS)
    assert c["STATUS"] == "VERIFIED_PREANNOUNCED" and c["SAFE"] == (True, True, True)
    late = M.classify_event("2021-01", [_obs("2021-02-10T09:00:00Z", "2021-02-10")], TRANSITIONS)
    assert late["STATUS"] == "UNRESOLVED_POINT_IN_TIME"


def test_capture_between_cutoffs_gives_only_short_windows():
    # T = 2021-02-10T13:30Z; capture at T-18h is before W12/W6 cutoffs only.
    c = M.classify_event("2021-01", [_obs("2021-02-09T19:30:00Z", "2021-02-10")], TRANSITIONS)
    assert c["SAFE"] == (True, True, False)
    assert c["STATUS"] == "VERIFIED_PREANNOUNCED"


def test_reschedule_uses_latest_prewindow_schedule():
    obs = [_obs("2020-10-01T00:00:00Z", "2021-02-09"), _obs("2021-01-20T00:00:00Z", "2021-02-10")]
    c = M.classify_event("2021-01", obs, TRANSITIONS)
    assert c["FINAL"] == ("2021-02-10", "08:30")
    assert c["STATUS"] == "VERIFIED_RESCHEDULED" and c["SAFE"] == (True, True, True)


def test_reschedule_announced_inside_window_is_not_safe_for_long_window():
    # Update visible only at T-10h: W12/W24 saw the stale schedule.
    obs = [_obs("2020-10-01T00:00:00Z", "2021-02-11"), _obs("2021-02-10T03:30:00Z", "2021-02-10")]
    c = M.classify_event("2021-01", obs, TRANSITIONS)
    assert c["FINAL"] == ("2021-02-10", "08:30")
    assert c["SAFE"] == (True, False, False)


def test_post_cutoff_contradiction_unresolves():
    obs = [_obs("2020-10-01T00:00:00Z", "2021-02-10"), _obs("2021-03-01T00:00:00Z", "2021-02-12")]
    c = M.classify_event("2021-01", obs, TRANSITIONS)
    assert c["STATUS"] == "UNRESOLVED_POINT_IN_TIME" and c["SAFE"] == (False, False, False)


def test_validator_detects_tampering():
    events = _load("EVENTS.json")["EVENTS"]
    bad = copy.deepcopy(events)
    bad[0]["SCHEDULED_RELEASE_UTC"] = "2020-01-14T12:30:00Z"
    assert any("DST" in err for err in M.validate_events(bad, TRANSITIONS))
    bad = copy.deepcopy(events)
    bad[1]["SAFE_FOR_W12"] = False
    assert any("W24 without W12" in err for err in M.validate_events(bad, TRANSITIONS))
    bad = copy.deepcopy(events)
    bad[2]["REFERENCE_PERIOD"] = bad[3]["REFERENCE_PERIOD"]
    assert any("duplicate REFERENCE_PERIOD" in err for err in M.validate_events(bad, TRANSITIONS))


def test_no_cpi_values_or_market_data(built):
    assert M.validate_boundary(built) == []
    tampered = copy.deepcopy(built)
    tampered["EVENTS.json"]["EVENTS"][0]["CPI_VALUE"] = 1.0
    assert M.validate_boundary(tampered)
    tampered = copy.deepcopy(built)
    tampered["EVENTS.json"]["EVENTS"][0]["BTC_CLOSE"] = 1.0
    assert M.validate_boundary(tampered)
    text = (DS / "EVENTS.json").read_text()
    for token in ("BTCUSDT", "kline", "ohlc", "Index level"):
        assert token not in text


def test_protected_years_only_in_noncanonical_inventory():
    for e in _load("EVENTS.json")["EVENTS"]:
        assert e["SCHEDULED_RELEASE_DATE"] <= M.LEGAL_LAST_DATE
    inv = _load("OUT_OF_RANGE_INVENTORY.json")
    assert inv["CANONICAL"] is False
    scopes = {r["SCOPE"] for r in inv["REFERENCE_PERIODS"]}
    assert scopes <= {"PRE_2020_METADATA_ONLY", "PROTECTED_2025_2026_METADATA_ONLY"}
    for r in inv["REFERENCE_PERIODS"]:
        assert set(r) == {"REFERENCE_PERIOD", "SCHEDULES_OBSERVED", "FIRST_SEEN_UTC", "LAST_SEEN_UTC",
                          "SNAPSHOT_COUNT", "SCOPE"}


def test_ledger_hashes_only_obtained_bytes():
    snaps = _load("SNAPSHOT_LEDGER.json")["SNAPSHOTS"]
    assert len({s["SNAPSHOT_ID"] for s in snaps}) == len(snaps)
    for s in snaps:
        if s["OBTAINED"]:
            data = (DS / s["RAW_PATH"]).read_bytes()
            assert M.sha256_hex(data) == s["SHA256"]
            if s["SNAPSHOT_ID"].startswith("WB_"):
                assert s["CDX_DIGEST_MATCH"] is (M.cdx_sha1_base32(data) == s["CDX_DIGEST_SHA1_BASE32"])
            if s["SUPPORTED_EVENT_IDS"]:
                assert s["CDX_DIGEST_MATCH"] is True
        else:
            assert s["SHA256"] is None and s["RAW_PATH"] is None


def test_parser_on_retained_capture():
    snaps = {s["SNAPSHOT_ID"]: s for s in _load("SNAPSHOT_LEDGER.json")["SNAPSHOTS"]}
    rows = M.parse_schedule_rows((DS / snaps["WB_20191216023559"]["RAW_PATH"]).read_bytes())
    assert ("2019-12", "2020-01-14", "08:30") in rows
    assert len(rows) == 14
