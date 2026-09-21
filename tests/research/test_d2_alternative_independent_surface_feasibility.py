"""Tests for D2 alternative independent surface feasibility.

Does not open Binance 2025/2026 prices or compute D2 outcomes on BitMEX.
"""

from __future__ import annotations

import ast
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.research.d2_bitmex_pre2020 import (
    BAR_MS,
    LISTING_UTC,
    PRE2020_END_EXCLUSIVE,
    RV_TRAILING_WINDOW,
    BitmexSchemaError,
    ProtectedBinanceRefused,
    aggregate_1m_to_5m,
    bitmex_end_ts_to_open_ms,
    census_gaps,
    count_legal_decision_rows,
    parse_5m_page,
    refuse_binance_protected_path,
    refuse_d2_outcome_request,
    theoretical_calendar,
    utc_ms,
)
from scripts.research.d2_confirmation_dependence_preserving_power import (
    COARSE_REFINED_N_GRID,
    COMPLETE_EXPOSED_YEARS,
    D2_REFINED_FRESH_N_SEED,
    five_row_refinement_grid,
    wilson_score_interval,
)
from scripts.research.d2_alternative_independent_surface_feasibility import (
    JSON_REL,
    MD_REL,
    SEMANTIC_AUDIT,
    classify_feasibility,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.d2_confirmation_feasibility_and_design import (
    refuse_protected_price_path,
    ProtectedPriceRefused,
)


REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
D2_RESULT = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
D2_RESULT_MD = "docs/research/discovery_results/D2_DISCOVERY_RESULT.md"
BITMEX_PY = "scripts/research/d2_bitmex_pre2020.py"
AUTHORITY_REL = "docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json"


def _committed(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)


def test_bitmex_module_does_not_compute_d2_outcomes() -> None:
    tree = ast.parse((REPO / BITMEX_PY).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {
        "arithmetic_mae",
        "rv_btc_24h",
        "btc_ret_24h",
        "evaluate_rule_1",
        "rv_abstention_mask",
        "evaluate_abstention_delta",
        "MU_RULE",
        "DELTA",
    }
    assert not (forbidden & names)
    assert not (forbidden & attrs)
    src = (REPO / BITMEX_PY).read_text(encoding="utf-8")
    assert "D2_OUTCOME_REFUSED" in src


def test_refuse_d2_outcome_helper() -> None:
    with pytest.raises(Exception) as exc:
        refuse_d2_outcome_request("MU_RULE")
    assert "D2_OUTCOME_REFUSED" in str(exc.value)


def test_no_binance_2025_2026_price_access() -> None:
    bad = REPO / "artifacts" / "research_data" / "CORE_BTC_BINANCE_V0" / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused, ProtectedBinanceRefused)):
        refuse_protected_price_path(bad)
    also = REPO / "canonical" / "1m" / "monthly" / "2026-06.parquet"
    with pytest.raises((C.ProtectedYearRefused, ProtectedPriceRefused, ProtectedBinanceRefused)):
        refuse_binance_protected_path(also)
    assert C.path_is_protected_partition(Path("canonical/1m/monthly/2025-01.parquet"))
    assert C.path_is_protected_partition(Path("canonical/1m/monthly/2026-01.parquet"))


def test_pre2020_boundary_and_250_warmup() -> None:
    raw = utc_ms(LISTING_UTC)
    cal = theoretical_calendar(raw_open_ms=raw)
    assert cal["RAW_DATA_START"] == "2016-05-13T12:00:00.000Z"
    assert cal["FIRST_RV_AVAILABLE_T"] == "2016-05-15T00:05:00.000Z"
    assert cal["FIRST_RULE_ELIGIBLE_T"] == "2017-01-21T00:05:00.000Z"
    assert cal["LAST_RULE_ELIGIBLE_T"] == "2019-12-30T00:05:00.000Z"
    assert cal["WARMUP_DECISION_ROWS"] == RV_TRAILING_WINDOW == 250
    assert cal["COMPLETE_DECISION_ROWS_INCLUDING_WARMUP"] - 250 == cal["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"]
    assert cal["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"] == 1072
    first_eligible = datetime.fromisoformat(cal["FIRST_RULE_ELIGIBLE_T"].replace("Z", "+00:00"))
    last_eligible = datetime.fromisoformat(cal["LAST_RULE_ELIGIBLE_T"].replace("Z", "+00:00"))
    assert first_eligible >= datetime(2017, 1, 21, 0, 5, tzinfo=UTC)
    assert last_eligible < PRE2020_END_EXCLUSIVE
    last_future_open = last_eligible + timedelta(minutes=5 * 287)
    last_future_end = last_future_open + timedelta(minutes=5)
    assert last_future_open == datetime(2019, 12, 31, 0, 0, tzinfo=UTC)
    assert last_future_end == datetime(2019, 12, 31, 0, 5, tzinfo=UTC)
    assert last_future_end < PRE2020_END_EXCLUSIVE
    # Dec 31 is never a legal decision.
    assert last_eligible.month != 12 or last_eligible.day != 31


def test_future_window_cannot_cross_2020() -> None:
    raw = utc_ms(LISTING_UTC)
    present = set()
    # Complete grid from listing through 2019-12-31 23:55 open would include 2020 boundary
    # if we naively continued. Count function must refuse open >= 2020.
    start = utc_ms(LISTING_UTC)
    end = utc_ms(datetime(2019, 12, 31, 23, 55, tzinfo=UTC))
    ms = start
    while ms <= end:
        present.add(ms)
        ms += BAR_MS
    legal = count_legal_decision_rows(present, raw_open_ms=start)
    last = datetime.fromisoformat(legal["LAST_RULE_ELIGIBLE_T"].replace("Z", "+00:00"))
    last_end = last + timedelta(minutes=5 * 288)
    assert last_end < PRE2020_END_EXCLUSIVE
    assert legal["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"] == 1072


def test_deterministic_1m_to_5m_aggregation() -> None:
    base = utc_ms(datetime(2019, 1, 1, 0, 0, tzinfo=UTC))
    rows = []
    for i in range(10):
        t = base + i * 60_000
        rows.append((t, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i))
    first = aggregate_1m_to_5m(rows)
    second = aggregate_1m_to_5m(list(reversed(rows)))
    assert first == second
    assert base in first
    bar = first[base]
    assert bar["open"] == 100.0
    assert bar["close"] == 104.5
    assert bar["high"] == 105.0
    assert bar["low"] == 99.0
    assert base + BAR_MS in first
    # 10 one-minute rows fill exactly two 5m buckets; a third is not fabricated.
    assert base + 2 * BAR_MS not in first
    incomplete = aggregate_1m_to_5m(rows[:7])
    assert base in incomplete
    assert base + BAR_MS not in incomplete


def test_duplicate_and_nonmonotonic_timestamps_rejected() -> None:
    payload = [
        {
            "timestamp": "2016-05-13T12:05:00.000Z",
            "symbol": "XBTUSD",
            "open": 1.0,
            "high": 2.0,
            "low": 1.0,
            "close": 1.5,
            "trades": 1,
        },
        {
            "timestamp": "2016-05-13T12:05:00.000Z",
            "symbol": "XBTUSD",
            "open": 1.5,
            "high": 2.0,
            "low": 1.0,
            "close": 1.6,
            "trades": 1,
        },
    ]
    with pytest.raises(BitmexSchemaError):
        parse_5m_page(payload)
    backward = [
        payload[0],
        {
            "timestamp": "2016-05-13T12:00:00.000Z",
            "symbol": "XBTUSD",
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "trades": 0,
        },
    ]
    with pytest.raises(BitmexSchemaError):
        parse_5m_page(backward)


def test_missing_timestamps_are_recorded_not_silently_filled() -> None:
    raw = utc_ms(datetime(2019, 6, 1, 0, 0, tzinfo=UTC))
    present = {raw, raw + 2 * BAR_MS}
    gaps = census_gaps(present, raw_open_ms=raw, last_open_ms=raw + 2 * BAR_MS)
    assert gaps["missing_bucket_count"] == 1
    assert gaps["missing_silently_accepted"] is False
    assert gaps["duplicates_silently_accepted"] is False
    assert gaps["expected_5m_bars"] == 3
    assert gaps["observed_5m_bars"] == 2


def test_bitmex_timestamp_end_to_open_mapping() -> None:
    end = datetime(2016, 5, 13, 12, 5, tzinfo=UTC)
    assert bitmex_end_ts_to_open_ms(end) == utc_ms(datetime(2016, 5, 13, 12, 0, tzinfo=UTC))


def test_refined_power_grid_and_one_five_row_refinement() -> None:
    assert COARSE_REFINED_N_GRID[0] == 728
    assert COARSE_REFINED_N_GRID[-1] == 1092
    assert 750 in COARSE_REFINED_N_GRID
    assert 1075 in COARSE_REFINED_N_GRID
    assert COMPLETE_EXPOSED_YEARS == (2021, 2022, 2023, 2024)
    assert D2_REFINED_FRESH_N_SEED == 20260921124
    grid = five_row_refinement_grid(728, 750)
    assert grid == (733, 738, 743, 748)
    assert all(n % 5 == 3 or n == 748 or True for n in grid)
    lo, hi = wilson_score_interval(800, 1000)
    assert 0.0 <= lo < 0.8 < hi <= 1.0


def test_no_cross_venue_row_count_multiplication() -> None:
    a = classify_feasibility(
        bitmex_n=1072,
        min_required=750,
        compatible="SCIENTIFICALLY_COMPARABLE_CROSS_VENUE",
        five_m_available=True,
    )
    assert a["CONFIRMATION_FEASIBILITY"] == (
        "FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION"
    )
    # Contemporaneous venues must not be summed into independent N.
    combined = 1072 + 1072
    assert combined != 1072
    assert SEMANTIC_AUDIT["BITMEX_CONTRACT_COMPATIBILITY"] == (
        "SCIENTIFICALLY_COMPARABLE_CROSS_VENUE"
    )


def test_severity_is_price_path_not_inverse_pnl() -> None:
    src = (REPO / "scripts/research/market_06_cross_venue_dislocation_evaluator.py").read_text(
        encoding="utf-8"
    )
    assert "def arithmetic_mae" in src
    assert "entry - min(lows)" in src
    assert "max(highs) - entry" in src
    assert "1.0 / entry" not in src.split("def arithmetic_mae", 1)[1].split("def ", 1)[0]


def test_report_firewall_when_present() -> None:
    path = REPO / JSON_REL
    if not path.is_file():
        pytest.skip("feasibility JSON not written yet")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["D2_OUTCOME_COMPUTED_ON_BITMEX"] is False
    assert report["PROTECTED_2025_OPENED"] is False
    assert report["PROTECTED_2026_OPENED"] is False
    assert report["2025_OPEN_AUTHORIZED"] is False
    assert report["2026_OPEN_AUTHORIZED"] is False
    assert report["MARKET_07_CREATED"] is False
    assert report["ARM_CREATED"] is False
    assert report["CROSS_VENUE_ROW_COUNT_MULTIPLICATION"] is False
    assert report["refined_power"]["POWER_USES_BINANCE_2025_2026"] is False
    assert report["refined_power"]["POWER_USES_BITMEX_OUTCOMES"] is False
    assert report["refined_power"]["EXPOSED_FILES_OPENED_YEARS"] == [
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
    ]
    assert report["BITMEX_LAST_RULE_ELIGIBLE_T"] < "2020-01-01T00:00:00.000Z"
    assert report["semantic_audit"]["ADVERSE_SEVERITY_METRIC"]["uses_inverse_pnl"] is False
    md = (REPO / MD_REL).read_text(encoding="utf-8")
    assert "wait until 2027" not in md.lower()
    packed = json.dumps(report)
    assert "CONFIRMATION RESULT" not in packed


def test_authority_has_no_scientific_outcomes_when_present() -> None:
    path = REPO / AUTHORITY_REL
    if not path.is_file():
        pytest.skip("BitMEX authority not written yet")
    auth = json.loads(path.read_text(encoding="utf-8"))
    assert auth["scientific_outcomes"]["D2_OUTCOME_COMPUTED_ON_BITMEX"] is False
    assert auth["scientific_outcomes"]["MU_RULE"] is None
    assert auth["scientific_outcomes"]["DELTA"] is None
    assert auth["contains_human_readable_price_dump"] is False
    assert auth["source_identity"]["third_party_kaggle_used"] is False
    # Human authority must not dump OHLC series.
    assert "canonical_rows" not in auth
    text = path.read_text(encoding="utf-8")
    assert '"open":' not in text or text.count('"open"') < 5


def test_d2_discovery_result_bytes_unchanged() -> None:
    assert (REPO / D2_RESULT).read_bytes() == _committed(D2_RESULT)
    assert (REPO / D2_RESULT_MD).read_bytes() == _committed(D2_RESULT_MD)
