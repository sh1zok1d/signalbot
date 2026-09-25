"""Calendar-only preflight for C012. Must not open a price file."""

from scripts.research import gv0r01_c012_execute as EX


def test_preflight_assigns_every_event_without_prices():
    report = EX.preflight()
    assert report["MARKET_DATA_OPENED"] is False
    assert report["PREFLIGHT_STATUS"] == "PASS"
    top = report["TOPOLOGY"]
    assert top["EVENTS_WITH_CONTROL"] == 99
    assert top["UNMATCHED_EVENTS"] == 0
    assert top["UNIQUE_CONTROL_WINDOWS"] == 99
    assert top["CONTROL_REUSE_COUNT"] == 0
    assert top["MAX_CONTROL_REUSE"] == 1
    assert top["EVENT_EVENT_WINDOW_OVERLAPS"] == 2
    assert top["EXCHANGEABILITY"] == "PASS_WITHIN_STRATUM"
    assert top["MIN_WITHIN_STRATUM_ENDPOINT_GAP_SECONDS"] >= 7 * 24 * 3600
    again = EX.preflight()
    assert [p["CONTROL_WINDOW_END_UTC"] for p in again["PAIRS"]] == [
        p["CONTROL_WINDOW_END_UTC"] for p in report["PAIRS"]
    ]


def test_executor_source_refuses_protected_months():
    src = open(EX.__file__).read()
    assert "2025-01" in src
    assert "PROTECTED_START_MS" in src
    assert "read_parquet" not in src
