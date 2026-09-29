"""Coverage-exporter tests. Synthetic fixtures only; no database and no network."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.audit.live_archive_replay_preflight.eligibility import (
    EXPECTED_LIVE_MINUTES,
    MATURITY_DAYS,
    derive_coverage_row,
    floor_5m,
    in_half_open_bucket,
    is_expected_minute,
    production_outage_overlap,
)
from scripts.audit.live_archive_replay_preflight.extract_coverage_readonly import (
    NO_MAGNITUDES_STATEMENT,
    REQUESTED_START,
    _COVERAGE_COLUMNS,
    _connect,
    _reject_magnitude_columns,
    _run_select,
    interval_bounds,
    latest_complete_interval_end,
    main,
    redact,
)
from scripts.audit.live_archive_replay_preflight.extract_sql import (
    FORBIDDEN_EXPORT_COLUMNS,
    SQL_COVERAGE_COLUMNS,
    assert_text_read_only,
    output_aliases,
    render_statements,
    schema_availability_sql,
    split_named_statements,
    sql_text,
)

UTC = timezone.utc
BUCKET = datetime(2026, 7, 17, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def test_packaged_sql_is_select_only():
    text = sql_text()
    statements = split_named_statements(text)
    assert statements
    for _name, body in statements:
        assert_text_read_only(body)
        stripped = body.lstrip()
        assert stripped.startswith("WITH") or stripped.startswith("SELECT") or stripped.startswith("--")
    rendered = render_statements(
        lookback_start=datetime(2026, 6, 17, tzinfo=UTC),
        interval_end=datetime(2026, 9, 28, tzinfo=UTC),
        requested_start=REQUESTED_START,
        pit_table_present=True,
        liquidation_table_present=True,
    )
    coverage = dict(rendered)["coverage_grid"]
    assert output_aliases(coverage) == list(SQL_COVERAGE_COLUMNS)
    assert not (set(SQL_COVERAGE_COLUMNS) & FORBIDDEN_EXPORT_COLUMNS)
    assert not (set(_COVERAGE_COLUMNS) & FORBIDDEN_EXPORT_COLUMNS)
    assert "TIMESTAMPTZ '2026-07-17 00:00:00+00'" in coverage
    assert "ts < TIMESTAMPTZ '2026-09-28 00:00:00+00'" in coverage
    assert "source = 'live'" in coverage
    assert "interval '5 minutes'" in coverage
    absent = dict(render_statements(
        lookback_start=datetime(2026, 6, 17, tzinfo=UTC),
        interval_end=datetime(2026, 9, 28, tzinfo=UTC),
        requested_start=REQUESTED_START,
        pit_table_present=False,
        liquidation_table_present=False,
    ))["coverage_grid"]
    assert "FROM liquidations" not in absent
    assert "exchange_instrument_history" not in absent
    assert output_aliases(absent) == list(SQL_COVERAGE_COLUMNS)
    assert_text_read_only(schema_availability_sql())
    assert "exchange_instruments" in schema_availability_sql()


def test_write_sql_is_rejected():
    with pytest.raises(ValueError):
        assert_text_read_only("INSERT INTO klines_1m VALUES (1)")
    with pytest.raises(ValueError):
        assert_text_read_only("SELECT 1; DELETE FROM open_interest")
    with pytest.raises(ValueError):
        split_named_statements("CREATE TEMP TABLE t (id int); SELECT 1")


def test_exact_five_minute_boundaries():
    assert floor_5m(BUCKET) == BUCKET
    assert floor_5m(BUCKET + timedelta(minutes=4, seconds=59)) == BUCKET
    assert floor_5m(BUCKET + timedelta(minutes=5)) == BUCKET + timedelta(minutes=5)
    assert in_half_open_bucket(BUCKET, BUCKET) is True
    assert in_half_open_bucket(BUCKET + timedelta(minutes=4), BUCKET) is True
    assert in_half_open_bucket(BUCKET + timedelta(minutes=5), BUCKET) is False
    assert in_half_open_bucket(BUCKET - timedelta(minutes=1), BUCKET) is False
    assert is_expected_minute(BUCKET + timedelta(minutes=4), BUCKET) is True
    assert is_expected_minute(BUCKET + timedelta(minutes=4, seconds=30), BUCKET) is False
    assert is_expected_minute(BUCKET + timedelta(minutes=5), BUCKET) is False


def _atomic(**overrides):
    row = {
        "bucket_start": BUCKET,
        "exchange": "binance",
        "live_bar_row_count": 0,
        "distinct_expected_live_minutes": 0,
        "offslot_live_bar_count": 0,
        "first_live_minute_ts": None,
        "last_live_minute_ts": None,
        "first_expected_bar_present": False,
        "first_expected_open_is_zero": None,
        "taker_split_complete_expected_minutes": 0,
        "live_oi_row_count": 0,
        "usable_oi_distinct_timestamps": 0,
        "oi_duplicate_timestamp_count": 0,
        "oi_distinct_unit_count": 0,
        "oi_units": None,
        "first_usable_oi_is_zero_or_null": True,
        "first_usable_oi_ts": None,
        "last_usable_oi_ts": None,
        "pit_table_present": True,
        "pit_row_count": 0,
        "pit_quantity_unit": None,
        "pit_multiplier_present": None,
        "liquidation_table_present": True,
        "liquidation_event_count": 0,
        "liquidation_has_long": False,
        "liquidation_has_short": False,
        "in_requested_interval": True,
    }
    row.update(overrides)
    return row


def _derive(**overrides):
    capability = overrides.pop("capability", {
        "live_supported": True, "enabled": True, "coverage_type": "full",
    })
    overlap = overrides.pop("outage_overlap", False)
    return derive_coverage_row(
        _atomic(**overrides),
        outage_overlap=overlap,
        outage_status="EVALUATED",
        capability=capability,
    )


def test_four_of_five_live_minutes_are_ineligible_and_five_are_eligible():
    missing = _derive(
        live_bar_row_count=4,
        distinct_expected_live_minutes=4,
        first_expected_bar_present=True,
        first_expected_open_is_zero=False,
    )
    assert missing["all_five_exact_live_minutes"] is False
    assert missing["bar_coverage_eligible"] is False
    assert missing["price_feature_non_null"] is False
    assert missing["heartbeat_healthy"] is False

    complete = _derive(
        live_bar_row_count=EXPECTED_LIVE_MINUTES,
        distinct_expected_live_minutes=EXPECTED_LIVE_MINUTES,
        first_expected_bar_present=True,
        first_expected_open_is_zero=False,
        taker_split_complete_expected_minutes=5,
        pit_row_count=1,
        pit_quantity_unit="base",
    )
    assert complete["bar_coverage_eligible"] is True
    assert complete["price_feature_non_null"] is True
    assert complete["volume_notional_non_null"] is True
    assert complete["taker_notional_non_null"] is True
    assert complete["heartbeat_healthy"] is True


def test_open_interest_observation_counts_and_mixed_units():
    assert _derive(usable_oi_distinct_timestamps=0)["oi_evaluable"] is False
    assert _derive(
        usable_oi_distinct_timestamps=1,
        oi_distinct_unit_count=1,
        first_usable_oi_is_zero_or_null=False,
        oi_units="base",
    )["oi_evaluable"] is False
    eligible = _derive(
        usable_oi_distinct_timestamps=2,
        oi_distinct_unit_count=1,
        first_usable_oi_is_zero_or_null=False,
        oi_units="base",
    )
    assert eligible["oi_evaluable"] is True
    assert eligible["oi_feature_non_null"] is True
    assert eligible["oi_mixed_units"] is False
    zero_base = _derive(
        usable_oi_distinct_timestamps=2,
        oi_distinct_unit_count=1,
        first_usable_oi_is_zero_or_null=True,
        oi_units="base",
    )
    assert zero_base["oi_evaluable"] is False
    mixed = _derive(
        usable_oi_distinct_timestamps=3,
        oi_distinct_unit_count=2,
        first_usable_oi_is_zero_or_null=False,
        oi_units="base,contracts",
    )
    assert mixed["oi_mixed_units"] is True
    assert mixed["oi_evaluable"] is False
    assert mixed["oi_units"] == "base,contracts"


def test_missing_pit_history_is_surfaced_and_blocks_notional():
    missing = _derive(
        live_bar_row_count=5,
        distinct_expected_live_minutes=5,
        first_expected_bar_present=True,
        first_expected_open_is_zero=False,
        pit_table_present=True,
        pit_row_count=0,
    )
    assert missing["missing_pit_history"] is True
    assert missing["pit_status"] == "NO_ROW"
    assert missing["notional_eligible"] is False
    assert missing["volume_notional_non_null"] is False
    absent = _derive(pit_table_present=False, pit_row_count=None)
    assert absent["pit_status"] == "TABLE_ABSENT"
    assert absent["missing_pit_history"] is True
    overlap = _derive(pit_row_count=2, pit_quantity_unit="base", pit_multiplier_present=True)
    assert overlap["pit_overlap_fail_closed"] is True
    assert overlap["notional_eligible"] is False
    contracts = _derive(pit_row_count=1, pit_quantity_unit="contracts", pit_multiplier_present=False)
    assert contracts["notional_eligible"] is False
    contracts_ok = _derive(pit_row_count=1, pit_quantity_unit="contracts", pit_multiplier_present=True)
    assert contracts_ok["notional_eligible"] is True


def test_zero_liquidation_rows_do_not_decide_feed_health():
    quiet = _derive(live_bar_row_count=5, liquidation_event_count=0)
    busy = _derive(live_bar_row_count=5, liquidation_event_count=10, liquidation_has_long=True)
    assert quiet["liquidation_rows_present"] is False
    assert busy["liquidation_rows_present"] is True
    assert quiet["heartbeat_healthy"] is True
    assert quiet["heartbeat_healthy"] == busy["heartbeat_healthy"]
    assert quiet["liquidation_feature_non_null"] is True
    unhealthy = _derive(live_bar_row_count=4, liquidation_event_count=0)
    assert unhealthy["heartbeat_healthy"] is False
    assert unhealthy["liquidation_feature_non_null"] is False
    outage = _derive(live_bar_row_count=5, liquidation_event_count=0, outage_overlap=True)
    assert outage["heartbeat_healthy"] is False


def test_outage_uses_logged_connectivity_not_an_empty_liquidation_table():
    disconnect = {
        "id": 1,
        "event_type": "disconnect",
        "ts": BUCKET - timedelta(minutes=1),
        "detail": {"idle_seconds": 0},
    }
    assert production_outage_overlap([disconnect], BUCKET) is True
    restored = [
        disconnect,
        {"id": 2, "event_type": "restore", "ts": BUCKET - timedelta(seconds=30), "detail": {}},
    ]
    assert production_outage_overlap(restored, BUCKET) is False
    late = {
        "id": 3,
        "event_type": "disconnect",
        "ts": BUCKET + timedelta(hours=7),
        "detail": {"idle_seconds": 60 * 60 * 8},
    }
    assert production_outage_overlap([late], BUCKET) is False
    near = {
        "id": 4,
        "event_type": "disconnect",
        "ts": BUCKET + timedelta(minutes=6),
        "detail": {"idle_seconds": 120},
    }
    assert production_outage_overlap([near], BUCKET) is True


def test_interval_ends_at_the_latest_complete_utc_day():
    now = datetime(2026, 9, 28, 17, 27, tzinfo=UTC)
    assert latest_complete_interval_end(now) == datetime(2026, 9, 28, tzinfo=UTC)
    lookback, requested, end = interval_bounds(now)
    assert requested == REQUESTED_START
    assert lookback == REQUESTED_START - timedelta(days=MATURITY_DAYS)
    assert end == datetime(2026, 9, 28, tzinfo=UTC)
    midnight = datetime(2026, 9, 28, tzinfo=UTC)
    assert latest_complete_interval_end(midnight) == midnight


def test_read_only_transaction_is_enforced():
    class Conn:
        def __init__(self, flag):
            self.flag = flag
            self.statements = []

        def transaction(self):
            return contextlib.nullcontext()

        def execute(self, sql):
            self.statements.append(sql)
            if sql.startswith("SHOW"):
                return SimpleNamespace(fetchone=lambda: (self.flag,), description=[], fetchall=lambda: [])
            if sql.startswith("SELECT"):
                return SimpleNamespace(
                    description=[SimpleNamespace(name="n")],
                    fetchall=lambda: [(1,)],
                    fetchone=lambda: (1,),
                )
            return SimpleNamespace(description=[], fetchall=lambda: [], fetchone=lambda: None)

    blocked = Conn("off")
    with pytest.raises(SystemExit, match="not read-only"):
        _run_select(blocked, "psycopg", "SELECT 1")
    assert not any(sql.startswith("SELECT 1") for sql in blocked.statements)
    assert any(sql == "SET TRANSACTION READ ONLY" for sql in blocked.statements)

    allowed = Conn("on")
    header, rows = _run_select(allowed, "psycopg", "SELECT 1")
    assert header == ["n"]
    assert rows == [(1,)]


def test_connect_sets_read_only_session_without_printing_dsn(capsys):
    secret = "postgresql://exporter:supersecret@127.0.0.1/signalbot"

    class Conn:
        def __init__(self):
            self.statements = []
            self.autocommit = False

        def execute(self, sql):
            self.statements.append(sql)

        def cursor(self):
            return self

        def close(self):
            pass

    conn = Conn()

    class Module:
        @staticmethod
        def connect(dsn, autocommit=False):
            assert dsn == secret
            assert autocommit is True
            return conn

    _connect(secret, psycopg_module=Module)
    assert "SET TIME ZONE 'UTC'" in conn.statements
    assert "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY" in conn.statements
    assert "SET default_transaction_read_only = on" in conn.statements
    captured = capsys.readouterr()
    assert "supersecret" not in captured.out + captured.err
    assert redact(f"failed {secret}") == "failed postgresql://REDACTED@127.0.0.1/signalbot"


def test_dsn_is_never_printed_when_connect_fails(capsys, tmp_path, monkeypatch):
    secret = "postgresql://exporter:supersecret@127.0.0.1/signalbot"
    monkeypatch.setenv("SIGNALBOT_DSN", secret)

    def explode(_dsn):
        raise RuntimeError(f"could not connect to {secret}")

    code = main(
        ["--out-dir", str(tmp_path / "out")],
        connect=explode,
        now=datetime(2026, 9, 28, 17, 27, tzinfo=UTC),
        git_sha="abc",
    )
    assert code == 1
    captured = capsys.readouterr()
    assert "supersecret" not in captured.out + captured.err
    assert "REDACTED" in captured.err
    monkeypatch.delenv("SIGNALBOT_DSN")
    assert main(["--out-dir", str(tmp_path / "nodsn")]) == 2


def test_magnitude_columns_are_rejected_and_absent_from_export(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit, match="magnitude"):
        _reject_magnitude_columns(["bucket_start", "oi_raw"])
    secret = "postgresql://exporter:supersecret@127.0.0.1/signalbot"
    monkeypatch.setenv("SIGNALBOT_DSN", secret)
    out = tmp_path / "export"
    code = main(
        ["--out-dir", str(out)],
        connect=lambda _dsn: (_ScriptedConn(), "psycopg"),
        now=datetime(2026, 9, 28, 17, 27, tzinfo=UTC),
        git_sha="0123456789abcdef" * 2 + "01234567",
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "supersecret" not in captured.out + captured.err
    coverage = list(csv.DictReader((out / "coverage_5m.csv").read_text().splitlines()))
    lookback = list(csv.DictReader((out / "maturity_lookback_5m.csv").read_text().splitlines()))
    assert [row["exchange"] for row in coverage] == ["binance", "bybit"]
    assert lookback[0]["grid_role"] == "maturity_lookback"
    by_exchange = {row["exchange"]: row for row in coverage}
    assert by_exchange["binance"]["bar_coverage_eligible"] == "false"
    assert by_exchange["binance"]["distinct_expected_live_minutes"] == "4"
    assert by_exchange["bybit"]["bar_coverage_eligible"] == "true"
    assert by_exchange["bybit"]["oi_evaluable"] == "true"
    assert by_exchange["bybit"]["oi_mixed_units"] == "false"
    assert by_exchange["binance"]["missing_pit_history"] == "true"
    assert by_exchange["binance"]["oi_mixed_units"] == "true"
    assert by_exchange["binance"]["oi_evaluable"] == "false"
    assert by_exchange["bybit"]["liquidation_rows_present"] == "false"
    assert by_exchange["bybit"]["heartbeat_healthy"] == "true"
    assert by_exchange["binance"]["heartbeat_healthy"] == "false"
    for path in out.iterdir():
        text = path.read_text()
        assert "supersecret" not in text
        header = text.splitlines()[0]
        if path.name in {"coverage_5m.csv", "maturity_lookback_5m.csv", "archive_summary.csv"}:
            for banned in FORBIDDEN_EXPORT_COLUMNS:
                assert f",{banned}," not in f",{header},"
                assert not header.startswith(banned + ",")
    manifest = json.loads((out / "export_manifest.json").read_text())
    assert manifest["no_market_magnitudes_exported"] is True
    assert manifest["statement"] == NO_MAGNITUDES_STATEMENT
    assert manifest["requested_interval_start"] == "2026-07-17T00:00:00Z"
    assert manifest["requested_interval_end_exclusive"] == "2026-09-28T00:00:00Z"
    assert manifest["latest_complete_utc_day"] == "2026-09-27"
    assert manifest["maturity_lookback_start"] == "2026-06-17T00:00:00Z"
    assert manifest["percentiles_computed"] is False
    assert manifest["events_computed"] is False
    assert manifest["exchange_instruments_not_used_as_pit"] is True
    names = {item["name"] for item in manifest["files"]}
    assert names == {path.name for path in out.iterdir() if path.name != "export_manifest.json"}
    for item in manifest["files"]:
        digest = hashlib.sha256((out / item["name"]).read_bytes()).hexdigest()
        assert digest == item["sha256"]


def test_missing_required_table_is_reported_without_a_guessed_grid(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALBOT_DSN", "postgresql://exporter:supersecret@127.0.0.1/signalbot")
    out = tmp_path / "export"
    code = main(
        ["--out-dir", str(out)],
        connect=lambda _dsn: (_ScriptedConn(klines_present=False), "psycopg"),
        now=datetime(2026, 9, 28, 17, 27, tzinfo=UTC),
        git_sha="0123456789abcdef" * 2 + "01234567",
    )
    assert code == 0
    text = (out / "coverage_5m.csv").read_text()
    assert "required_input_absent" in text
    assert "klines_1m" in text
    assert "oi_raw" not in text
    manifest = json.loads((out / "export_manifest.json").read_text())
    assert manifest["coverage_grid_status"] == "absent"
    assert any(row["note"].startswith("table_absent") for row in csv.DictReader(
        (out / "archive_summary.csv").read_text().splitlines()
    ))


def test_frozen_config_constants_match_the_exporter():
    stage2 = yaml.safe_load((ROOT / "config" / "stage2.yaml").read_text())
    beta = yaml.safe_load((ROOT / "config" / "beta_v0.yaml").read_text())["beta"]
    tiers = stage2["defaults"]["percentiles"]["confidence_tiers"]
    assert tiers["building_below_days"] == MATURITY_DAYS == 30
    assert stage2["defaults"]["data_confidence"]["minimum_metric_coverage"] == 0.95
    assert beta["percentile_window"] == "30d"
    assert beta["symbol"] == "BTCUSDT"
    assert beta["market_type"] == "perp"
    assert beta["active_exchanges"] == ["binance", "bybit", "okx"]
    assert beta["min_venue_coverage"] == 2
    assert beta["timeframe"] == "5m"


class _Result:
    def __init__(self, header, rows):
        self.description = [SimpleNamespace(name=name) for name in header]
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _ScriptedConn:
    def __init__(self, *, klines_present=True):
        self.klines_present = klines_present
        self.statements = []

    def transaction(self):
        return contextlib.nullcontext()

    def close(self):
        return None

    def execute(self, sql):
        self.statements.append(sql)
        if sql.startswith("SET"):
            return _Result([], [])
        if sql.startswith("SHOW"):
            return _Result(["transaction_read_only"], [("on",)])
        if "to_regclass" in sql:
            return self._schema()
        if "in_requested_interval" in sql:
            if not self.klines_present:
                raise AssertionError("coverage grid ran without klines_1m")
            return self._coverage()
        if "'klines_1m' AS table_name" in sql:
            if not self.klines_present:
                raise AssertionError("klines archive ran without the table")
            return _Result(
                ["table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note"],
                [("klines_1m", "binance", "live", 10, BUCKET, BUCKET, None)],
            )
        if "'open_interest' AS table_name" in sql:
            return _Result(
                ["table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note"],
                [("open_interest", "bybit", "live", 4, BUCKET, BUCKET, None)],
            )
        if "'liquidations' AS table_name" in sql:
            return _Result(
                ["table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note"],
                [],
            )
        if "'connectivity_events' AS table_name" in sql:
            return _Result(
                ["table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note"],
                [],
            )
        if "'exchange_instrument_history' AS table_name" in sql:
            return _Result(
                ["table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note"],
                [],
            )
        if "GROUP BY exchange, source, oi_unit" in sql:
            return _Result(
                ["exchange", "source", "oi_unit", "row_count", "min_ts", "max_ts"],
                [("binance", "live", "base", 3, BUCKET, BUCKET), ("binance", "live", "contracts", 1, BUCKET, BUCKET)],
            )
        if "multiplier_present" in sql and "effective_from" in sql and "in_requested_interval" not in sql:
            return _Result(
                ["exchange", "symbol", "market_type", "quantity_unit", "multiplier_present",
                 "metadata_source", "effective_from", "effective_until", "open_ended"],
                [],
            )
        if "idle_seconds_text" in sql:
            return _Result(["id", "exchange", "event_type", "ts", "idle_seconds_text"], [])
        if "metric = 'liquidations'" in sql:
            rows = [("binance", "BTCUSDT", "perp", "liquidations", True, True, "snapshot"),
                    ("bybit", "BTCUSDT", "perp", "liquidations", True, True, "full"),
                    ("okx", "BTCUSDT", "perp", "liquidations", True, True, "full")]
            return _Result(
                ["exchange", "symbol", "market_type", "metric", "live_supported", "enabled", "coverage_type"],
                rows,
            )
        raise AssertionError(sql[:180])

    def _schema(self):
        from scripts.audit.live_archive_replay_preflight.extract_sql import SCHEMA_REQUIREMENTS
        rows = []
        for kind, table, column, _role in SCHEMA_REQUIREMENTS:
            present = self.klines_present or table != "klines_1m"
            rows.append((kind, table, column, present))
        return _Result(["kind", "table_name", "column_name", "present"], rows)

    def _coverage(self):
        def row(bucket, exchange, minutes, oi_units, oi_count, pit_rows, requested):
            return (
                bucket, exchange, minutes, minutes, 0, bucket, bucket, minutes == 5, False, minutes,
                oi_count, oi_count, 0, 1 if "," not in (oi_units or "") and oi_units else (2 if oi_units else 0),
                oi_units, False if oi_count else True, bucket if oi_count else None, bucket if oi_count else None,
                True, pit_rows, "base" if pit_rows == 1 else None, False if pit_rows == 1 else None,
                True, 0, False, False, requested,
            )
        rows = [
            row(datetime(2026, 6, 17, tzinfo=UTC), "binance", 5, "base", 2, 1, False),
            row(BUCKET, "binance", 4, "base,contracts", 3, 0, True),
            row(BUCKET, "bybit", 5, "base", 2, 1, True),
        ]
        return _Result(list(SQL_COVERAGE_COLUMNS), rows)
