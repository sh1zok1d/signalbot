"""Outcome-blind parser checks for D7_BITMEX_ACTIVITY_V0. No network. No D7 target."""
import json

import pytest

from scripts.research.d7_bitmex_activity_v0 import (
    ACTIVITY_FIELDS,
    ActivitySchemaError,
    audit_rows,
    parse_activity_page,
    refuse_protected_or_d2_write,
)
from pathlib import Path


def _row(**overrides):
    base = {
        "timestamp": "2017-06-01T00:05:00.000Z",
        "symbol": "XBTUSD",
        "open": 2400.0,
        "high": 2401.0,
        "low": 2399.0,
        "close": 2400.5,
        "trades": 3,
        "volume": 100,
        "turnover": 4166666,
        "homeNotional": 0.04166666,
        "foreignNotional": 100,
        "vwap": 2400.2,
        "lastSize": 1,
        "pool": "Primary",
    }
    base.update(overrides)
    return base


def test_parser_keeps_activity_fields_and_bucket_end_clock():
    parsed = parse_activity_page([_row()])
    assert parsed[0]["open_time_ms"] == 1496275200000  # 2017-06-01T00:00:00Z
    for key in ACTIVITY_FIELDS:
        assert parsed[0][key] == _row()[key]


def test_missing_activity_field_stays_null():
    row = _row()
    del row["foreignNotional"]
    del row["vwap"]
    parsed = parse_activity_page([row])
    assert parsed[0]["foreignNotional"] is None
    assert parsed[0]["vwap"] is None
    assert parsed[0]["volume"] == 100


def test_duplicate_and_backward_timestamps_fail():
    with pytest.raises(ActivitySchemaError, match="DUPLICATE_TIMESTAMP"):
        parse_activity_page([_row(), _row()])
    with pytest.raises(ActivitySchemaError, match="NON_MONOTONIC"):
        parse_activity_page([
            _row(timestamp="2017-06-01T00:10:00.000Z"),
            _row(timestamp="2017-06-01T00:05:00.000Z"),
        ])


def test_audit_counts_gaps_and_does_not_fill_or_score_d7():
    a = parse_activity_page([_row()])[0]
    b = parse_activity_page([_row(timestamp="2017-06-01T00:20:00.000Z", volume=0, foreignNotional=0, trades=0)])[0]
    quality = audit_rows([a, b])
    assert quality["missing_buckets"] == 2
    assert quality["zero_volume_buckets"] == 1
    assert quality["volume_ne_foreign_notional"] == 0
    assert quality["no_fill"] is True
    assert quality["d7_target_computed"] is False
    assert "impact" not in json.dumps(quality).lower()


def test_refuses_d2_and_protected_paths():
    with pytest.raises(ActivitySchemaError):
        refuse_protected_or_d2_write(Path("docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz"))
    with pytest.raises(ActivitySchemaError):
        refuse_protected_or_d2_write(Path("data/binance/2025-01.parquet"))
