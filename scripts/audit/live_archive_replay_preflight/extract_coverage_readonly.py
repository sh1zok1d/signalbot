"""Owner-executable read-only coverage export.

Usage, on the database host, from a checkout of this repository, with
SIGNALBOT_DSN already set in the environment:

    python -m scripts.audit.live_archive_replay_preflight.extract_coverage_readonly \\
        --out-dir /tmp/live_archive_replay_preflight_coverage

The process forces a UTC read-only session, runs the packaged SELECT
statements, and writes compact coverage files. It does not print or persist
the DSN. It does not export prices, OHLC, volume, taker values, open-interest
magnitudes, or liquidation notionals.

Copy the output directory to the cursor account only after it finishes:

    mkdir -p /home/cursor/exports && cp -a /tmp/live_archive_replay_preflight_coverage /home/cursor/exports/live_archive_replay_preflight_coverage
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import EXPORTER_VERSION
from .eligibility import (
    MATURITY_DAYS,
    declared_liquidation_available,
    derive_coverage_row,
    full_replay_intervals,
    production_outage_overlap,
)
from .extract_sql import (
    EXCHANGES,
    FORBIDDEN_EXPORT_COLUMNS,
    MARKET_TYPE,
    SCHEMA_REQUIREMENTS,
    STATEMENT_TABLES,
    SYMBOL,
    assert_text_read_only,
    render_statements,
    schema_availability_sql,
)

UTC = timezone.utc
REQUESTED_START = datetime(2026, 7, 17, tzinfo=UTC)
OWNER_OUT_DIR = "/tmp/live_archive_replay_preflight_coverage"
OWNER_COPY_DIR = "/home/cursor/exports/live_archive_replay_preflight_coverage"
NO_MAGNITUDES_STATEMENT = (
    "No prices, OHLC values, volume values, taker values, open-interest magnitudes, "
    "or liquidation notionals were exported."
)
_DSN_USERINFO = re.compile(r"://[^@/\s]+@")
_ARCHIVE_COLUMNS = (
    "table_name", "exchange", "source", "row_count", "min_ts", "max_ts", "note",
)
_COVERAGE_COLUMNS = (
    "bucket_start",
    "exchange",
    "grid_role",
    "live_bar_row_count",
    "distinct_expected_live_minutes",
    "offslot_live_bar_count",
    "first_live_minute_ts",
    "last_live_minute_ts",
    "first_expected_bar_present",
    "first_expected_open_is_zero",
    "all_five_exact_live_minutes",
    "bar_coverage_eligible",
    "taker_split_complete_expected_minutes",
    "price_feature_non_null",
    "live_oi_row_count",
    "usable_oi_distinct_timestamps",
    "oi_duplicate_timestamp_count",
    "oi_distinct_unit_count",
    "oi_units",
    "first_usable_oi_is_zero_or_null",
    "first_usable_oi_ts",
    "last_usable_oi_ts",
    "oi_mixed_units",
    "oi_evaluable",
    "oi_feature_non_null",
    "pit_table_present",
    "pit_row_count",
    "pit_quantity_unit",
    "pit_multiplier_present",
    "pit_history_present",
    "pit_overlap_fail_closed",
    "pit_status",
    "missing_pit_history",
    "notional_eligible",
    "volume_notional_non_null",
    "taker_notional_non_null",
    "liquidation_table_present",
    "liquidation_event_count",
    "liquidation_has_long",
    "liquidation_has_short",
    "liquidation_rows_present",
    "outage_overlap",
    "outage_status",
    "heartbeat_healthy",
    "liquidation_capability_row_present",
    "liquidation_live_supported",
    "liquidation_enabled",
    "liquidation_coverage_type",
    "liquidation_declared_available",
    "liquidation_vote_prereq_without_percentile",
    "liquidation_feature_non_null",
    "in_requested_interval",
    "note",
)
_CONNECTIVITY_COLUMNS = (
    "record_type", "exchange", "event_id", "event_type", "event_ts", "idle_seconds",
    "interval_start", "interval_end", "open_ended", "note",
)
_OI_UNIT_COLUMNS = ("exchange", "source", "oi_unit", "row_count", "min_ts", "max_ts", "note")
_INSTRUMENT_COLUMNS = (
    "exchange", "symbol", "market_type", "quantity_unit", "multiplier_present",
    "metadata_source", "effective_from", "effective_until", "open_ended", "note",
)
_CAPABILITY_COLUMNS = (
    "exchange", "symbol", "market_type", "metric", "live_supported", "enabled",
    "coverage_type", "declared_available", "note",
)
_SCHEMA_COLUMNS = ("kind", "table_name", "column_name", "present", "eligibility_role")
_COVERAGE_REQUIRED_COLUMNS = (
    ("klines_1m", "open"),
    ("klines_1m", "source"),
    ("klines_1m", "ts"),
    ("klines_1m", "taker_buy_volume"),
    ("klines_1m", "taker_sell_volume"),
    ("open_interest", "oi_raw"),
    ("open_interest", "oi_unit"),
    ("open_interest", "source"),
    ("open_interest", "ts"),
)
_PIT_COLUMNS = (
    ("exchange_instrument_history", "quantity_unit"),
    ("exchange_instrument_history", "contract_multiplier"),
    ("exchange_instrument_history", "effective_from"),
    ("exchange_instrument_history", "effective_until"),
    ("exchange_instrument_history", "market_type"),
)
_LIQ_COLUMNS = (("liquidations", "side"), ("liquidations", "ts"))
_STATEMENT_COLUMNS = {
    "archive_klines": (("klines_1m", "source"), ("klines_1m", "ts")),
    "archive_open_interest": (("open_interest", "source"), ("open_interest", "ts")),
    "archive_liquidations": _LIQ_COLUMNS,
    "archive_connectivity": (("connectivity_events", "event_type"), ("connectivity_events", "ts")),
    "archive_instrument_history": (("exchange_instrument_history", "effective_from"),),
    "oi_unit_changes": (("open_interest", "oi_unit"), ("open_interest", "source"), ("open_interest", "ts")),
    "instrument_history_intervals": _PIT_COLUMNS,
    "connectivity_events": (
        ("connectivity_events", "id"),
        ("connectivity_events", "event_type"),
        ("connectivity_events", "ts"),
        ("connectivity_events", "detail"),
    ),
    "liquidation_capability": (
        ("symbol_exchange_capabilities", "live_supported"),
        ("symbol_exchange_capabilities", "enabled"),
        ("symbol_exchange_capabilities", "coverage_type"),
        ("symbol_exchange_capabilities", "metric"),
    ),
}


def redact(text: str) -> str:
    return _DSN_USERINFO.sub("://REDACTED@", text)


def latest_complete_interval_end(now: datetime) -> datetime:
    """Exclusive end: 00:00 UTC of the day that is still in progress."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = now.astimezone(UTC)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def interval_bounds(now: datetime) -> tuple[datetime, datetime, datetime]:
    requested_start = REQUESTED_START
    interval_end = latest_complete_interval_end(now)
    lookback_start = requested_start - timedelta(days=MATURITY_DAYS)
    if interval_end <= lookback_start:
        raise SystemExit("execution clock is before the maturity lookback; refusing to guess a window")
    return lookback_start, requested_start, interval_end


def main(argv: list[str] | None = None, *, connect=None, now=None, git_sha=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only live-archive coverage export")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    dsn = os.environ.get("SIGNALBOT_DSN", "").strip()
    if not dsn:
        print("SIGNALBOT_DSN is not set. Refusing to guess a database.", file=sys.stderr)
        return 2
    when = now or datetime.now(UTC)
    try:
        lookback_start, requested_start, interval_end = interval_bounds(when)
    except SystemExit:
        raise
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    opener = connect or _connect
    try:
        conn, driver = opener(dsn)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - connection errors must not leak the DSN
        print(f"database connection failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    try:
        try:
            files = _export(
                conn, driver, out,
                lookback_start=lookback_start,
                requested_start=requested_start,
                interval_end=interval_end,
                git_sha=_resolve_git_sha(git_sha),
            )
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"export failed: {redact(str(exc))}", file=sys.stderr)
            return 1
    finally:
        conn.close()
    for name, digest, nrows in files:
        print(f"{digest}  {name}  rows={nrows}")
    print("EXPORT_COMPLETE")
    print(NO_MAGNITUDES_STATEMENT)
    return 0


def _export(conn, driver, out: Path, *, lookback_start, requested_start, interval_end, git_sha) -> list:
    schema_header, schema_raw = _run_select(conn, driver, schema_availability_sql())
    schema_rows = _as_dicts(schema_header, schema_raw)
    present_tables, present_columns = _presence(schema_rows)
    pit_ok = _table_and_columns(present_tables, present_columns, "exchange_instrument_history", _PIT_COLUMNS)
    liq_ok = _table_and_columns(present_tables, present_columns, "liquidations", _LIQ_COLUMNS)
    statements = render_statements(
        lookback_start=lookback_start,
        interval_end=interval_end,
        requested_start=requested_start,
        pit_table_present=pit_ok,
        liquidation_table_present=liq_ok,
    )
    results = {}
    for name, sql in statements:
        missing = [table for table in STATEMENT_TABLES[name] if table not in present_tables]
        missing_columns = [
            f"{table}.{column}"
            for table, column in _STATEMENT_COLUMNS.get(name, ())
            if (table, column) not in present_columns
        ]
        if name == "coverage_grid":
            missing_columns.extend(
                f"{table}.{column}"
                for table, column in _COVERAGE_REQUIRED_COLUMNS
                if (table, column) not in present_columns
            )
        if missing or missing_columns:
            results[name] = {"status": "absent", "missing": missing + missing_columns, "rows": []}
            continue
        try:
            header, raw_rows = _run_select(conn, driver, sql)
        except Exception as exc:  # noqa: BLE001
            if _is_missing_relation(exc):
                results[name] = {"status": "absent", "missing": list(STATEMENT_TABLES[name]), "rows": []}
                continue
            print(f"query failed for {name}: {redact(str(exc))}", file=sys.stderr)
            raise SystemExit(1) from None
        results[name] = {"status": "ok", "rows": _as_dicts(header, raw_rows)}

    payloads = _payloads(
        schema_rows=schema_rows,
        results=results,
        connectivity_present=(
            "connectivity_events" in present_tables
            and results["connectivity_events"]["status"] == "ok"
        ),
    )
    written = []
    for filename, columns, rows in payloads:
        _reject_magnitude_columns(columns)
        path = out / filename
        digest = _write_csv(path, columns, rows)
        written.append((filename, digest, len(rows)))
    manifest_rows = _write_manifest(
        out,
        written=written,
        lookback_start=lookback_start,
        requested_start=requested_start,
        interval_end=interval_end,
        git_sha=git_sha,
        archive_rows=payloads_by_name(payloads, "archive_summary.csv"),
        coverage_status=results["coverage_grid"]["status"],
        coverage_missing=results["coverage_grid"].get("missing", []),
    )
    written.append(manifest_rows)
    return written


def _payloads(*, schema_rows, results, connectivity_present) -> list:
    schema = []
    roles = {(kind, table, column): role for kind, table, column, role in SCHEMA_REQUIREMENTS}
    for row in schema_rows:
        column = row.get("column_name")
        schema.append({
            "kind": row.get("kind"),
            "table_name": row.get("table_name"),
            "column_name": column,
            "present": row.get("present"),
            "eligibility_role": roles.get((row.get("kind"), row.get("table_name"), column or None), ""),
        })

    archive = []
    for name in (
        "archive_klines", "archive_open_interest", "archive_liquidations",
        "archive_connectivity", "archive_instrument_history",
    ):
        archive.extend(_archive_rows(name, results[name]))

    oi_units = _simple_or_note(results["oi_unit_changes"], _OI_UNIT_COLUMNS, "open_interest")
    instruments = _instrument_rows(results["instrument_history_intervals"])
    if connectivity_present:
        events = [_health_event(row) for row in results["connectivity_events"]["rows"]]
        connectivity = _connectivity_rows(events)
    else:
        events = []
        missing = ",".join(results["connectivity_events"].get("missing") or ["connectivity_events"])
        connectivity = [_note_row(_CONNECTIVITY_COLUMNS, f"table_absent:{missing}")]
    capabilities = _capability_rows(results["liquidation_capability"])
    coverage_rows, lookback_rows = _coverage_rows(
        results["coverage_grid"], events, results["liquidation_capability"], connectivity_present,
    )
    return [
        ("schema_availability.csv", _SCHEMA_COLUMNS, schema),
        ("archive_summary.csv", _ARCHIVE_COLUMNS, archive),
        ("oi_unit_changes.csv", _OI_UNIT_COLUMNS, oi_units),
        ("instrument_history_coverage.csv", _INSTRUMENT_COLUMNS, instruments),
        ("connectivity_coverage.csv", _CONNECTIVITY_COLUMNS, connectivity),
        ("liquidation_capability.csv", _CAPABILITY_COLUMNS, capabilities),
        ("coverage_5m.csv", _COVERAGE_COLUMNS, coverage_rows),
        ("maturity_lookback_5m.csv", _COVERAGE_COLUMNS, lookback_rows),
    ]


def _coverage_rows(result, events, capability_result, connectivity_present):
    if result["status"] != "ok":
        missing = ",".join(result.get("missing") or ["coverage_inputs"])
        note = [_note_row(_COVERAGE_COLUMNS, f"required_input_absent:{missing}")]
        return note, list(note)
    by_exchange = defaultdict(list)
    for event in events:
        by_exchange[event["exchange"]].append(event)
    caps = _index_capabilities(capability_result)
    requested, lookback = [], []
    for atomic in result["rows"]:
        exchange = atomic["exchange"]
        bucket = _parse_ts(atomic["bucket_start"])
        if connectivity_present:
            overlap = production_outage_overlap(by_exchange.get(exchange, ()), bucket)
            outage_status = "EVALUATED"
        else:
            overlap = None
            outage_status = "TABLE_ABSENT"
        derived = derive_coverage_row(
            atomic,
            outage_overlap=overlap,
            outage_status=outage_status,
            capability=caps.get(exchange),
        )
        target = requested if derived["grid_role"] == "requested_interval" else lookback
        target.append({key: derived.get(key) for key in _COVERAGE_COLUMNS})
    return requested, lookback


def _index_capabilities(result) -> dict:
    if result["status"] != "ok":
        return {}
    found = {}
    duplicated = set()
    for row in result["rows"]:
        exchange = row["exchange"]
        if exchange in found:
            duplicated.add(exchange)
        found[exchange] = {
            "live_supported": _optional_bool(row.get("live_supported")),
            "enabled": _optional_bool(row.get("enabled")),
            "coverage_type": row.get("coverage_type"),
        }
    for exchange in duplicated:
        found[exchange] = {"live_supported": None, "enabled": None, "coverage_type": None}
    return found


def _capability_rows(result) -> list:
    if result["status"] != "ok":
        missing = ",".join(result.get("missing") or ["symbol_exchange_capabilities"])
        return [_note_row(_CAPABILITY_COLUMNS, f"table_absent:{missing}")]
    counts: dict[str, int] = defaultdict(int)
    last: dict[str, Mapping] = {}
    for source in result["rows"]:
        counts[source["exchange"]] += 1
        last[source["exchange"]] = source
    rows = []
    for exchange in EXCHANGES:
        source = last.get(exchange)
        if source is None:
            rows.append(_note_row(_CAPABILITY_COLUMNS, "capability_row_absent", exchange=exchange))
            continue
        if counts[exchange] > 1:
            rows.append({
                "exchange": exchange,
                "symbol": source.get("symbol") or SYMBOL,
                "market_type": source.get("market_type") or MARKET_TYPE,
                "metric": "liquidations",
                "live_supported": None,
                "enabled": None,
                "coverage_type": None,
                "declared_available": None,
                "note": "duplicate_capability_rows",
            })
            continue
        cap = {
            "live_supported": _optional_bool(source.get("live_supported")),
            "enabled": _optional_bool(source.get("enabled")),
            "coverage_type": source.get("coverage_type"),
        }
        rows.append({
            "exchange": exchange,
            "symbol": source.get("symbol") or SYMBOL,
            "market_type": source.get("market_type") or MARKET_TYPE,
            "metric": source.get("metric") or "liquidations",
            "live_supported": cap["live_supported"],
            "enabled": cap["enabled"],
            "coverage_type": cap["coverage_type"],
            "declared_available": declared_liquidation_available(cap),
            "note": "current_row_not_pit",
        })
    return rows


def _instrument_rows(result) -> list:
    if result["status"] != "ok":
        missing = ",".join(result.get("missing") or ["exchange_instrument_history"])
        return [_note_row(_INSTRUMENT_COLUMNS, f"table_absent:{missing}")]
    rows = []
    seen = set()
    for source in result["rows"]:
        seen.add(source["exchange"])
        rows.append({
            "exchange": source.get("exchange"),
            "symbol": source.get("symbol"),
            "market_type": source.get("market_type"),
            "quantity_unit": source.get("quantity_unit"),
            "multiplier_present": source.get("multiplier_present"),
            "metadata_source": source.get("metadata_source"),
            "effective_from": source.get("effective_from"),
            "effective_until": source.get("effective_until"),
            "open_ended": source.get("open_ended"),
            "note": "",
        })
    for exchange in EXCHANGES:
        if exchange not in seen:
            rows.append(_note_row(_INSTRUMENT_COLUMNS, "no_history_rows", exchange=exchange))
    return rows


def _connectivity_rows(events) -> list:
    rows = []
    for event in events:
        rows.append({
            "record_type": "event",
            "exchange": event["exchange"],
            "event_id": event["id"],
            "event_type": event["event_type"],
            "event_ts": event["ts"],
            "idle_seconds": event["detail"]["idle_seconds"],
            "interval_start": None,
            "interval_end": None,
            "open_ended": None,
            "note": "",
        })
    grouped = defaultdict(list)
    for event in events:
        grouped[event["exchange"]].append(event)
    for exchange in EXCHANGES:
        for start, end in full_replay_intervals(grouped.get(exchange, ())):
            rows.append({
                "record_type": "interval",
                "exchange": exchange,
                "event_id": None,
                "event_type": None,
                "event_ts": None,
                "idle_seconds": None,
                "interval_start": start,
                "interval_end": end,
                "open_ended": end is None,
                "note": "full_replay_of_exported_events",
            })
    if not rows:
        return [_note_row(_CONNECTIVITY_COLUMNS, "no_disconnect_or_restore_events")]
    return rows


def _archive_rows(name: str, result) -> list:
    table = STATEMENT_TABLES[name][0]
    if result["status"] != "ok":
        missing = ",".join(result.get("missing") or [table])
        return [{
            "table_name": table,
            "exchange": "",
            "source": "",
            "row_count": "",
            "min_ts": "",
            "max_ts": "",
            "note": f"table_absent:{missing}",
        }]
    rows = []
    seen = set()
    for source in result["rows"]:
        seen.add(source.get("exchange"))
        rows.append({column: source.get(column) for column in _ARCHIVE_COLUMNS})
    for exchange in EXCHANGES:
        if exchange not in seen:
            rows.append({
                "table_name": table,
                "exchange": exchange,
                "source": "",
                "row_count": 0,
                "min_ts": "",
                "max_ts": "",
                "note": "no_rows",
            })
    return rows


def _simple_or_note(result, columns, table: str) -> list:
    if result["status"] != "ok":
        missing = ",".join(result.get("missing") or [table])
        return [_note_row(columns, f"table_absent:{missing}")]
    if not result["rows"]:
        return [_note_row(columns, "no_rows")]
    return [{column: source.get(column) for column in columns} | {"note": source.get("note") or ""} for source in result["rows"]]


def _note_row(columns, note: str, *, exchange: str = "") -> dict:
    row = {column: "" for column in columns}
    if "note" in row:
        row["note"] = note
    if "exchange" in row:
        row["exchange"] = exchange
    if "record_type" in row:
        row["record_type"] = "note"
    return row


def _health_event(row: Mapping) -> dict:
    raw = row.get("idle_seconds_text")
    if raw is None or str(raw).strip() == "":
        idle = 0.0
    else:
        try:
            idle = float(raw)
        except (TypeError, ValueError) as exc:
            raise SystemExit("connectivity idle_seconds is not numeric; refusing to mark the feed healthy") from exc
    return {
        "id": int(row["id"]),
        "exchange": row["exchange"],
        "event_type": row["event_type"],
        "ts": _parse_ts(row["ts"]),
        "detail": {"idle_seconds": idle},
    }


def _write_manifest(out, *, written, lookback_start, requested_start, interval_end, git_sha,
                    archive_rows, coverage_status, coverage_missing) -> tuple:
    files = []
    for name, digest, nrows in written:
        files.append({"name": name, "sha256": digest, "rows": nrows})
    bounds = []
    for row in archive_rows:
        bounds.append({
            "table_name": row.get("table_name") or "",
            "exchange": row.get("exchange") or "",
            "source": row.get("source") or "",
            "row_count": "" if row.get("row_count") is None else row.get("row_count"),
            "min_ts": _iso(row.get("min_ts")) if isinstance(row.get("min_ts"), datetime) else (row.get("min_ts") or ""),
            "max_ts": _iso(row.get("max_ts")) if isinstance(row.get("max_ts"), datetime) else (row.get("max_ts") or ""),
            "note": row.get("note") or "",
        })
    payload = {
        "exporter": "scripts.audit.live_archive_replay_preflight.extract_coverage_readonly",
        "exporter_version": EXPORTER_VERSION,
        "git_sha": git_sha,
        "symbol": SYMBOL,
        "market_type": MARKET_TYPE,
        "exchanges": list(EXCHANGES),
        "requested_interval_start": _iso(requested_start),
        "requested_interval_end_exclusive": _iso(interval_end),
        "latest_complete_utc_day": (interval_end - timedelta(days=1)).date().isoformat(),
        "maturity_lookback_start": _iso(lookback_start),
        "maturity_window_days": MATURITY_DAYS,
        "mature_when_span_days_gte": MATURITY_DAYS,
        "minimum_metric_coverage": 0.95,
        "allowed_missing_bars_5m": 0,
        "expected_live_minutes": 5,
        "oi_min_distinct_timestamps": 2,
        "min_venue_coverage": 2,
        "heartbeat_live_bar_count": 5,
        "connectivity_lookaround_hours": 6,
        "percentiles_computed": False,
        "events_computed": False,
        "liquidation_declared_available_is_current_capability_row_not_pit": True,
        "zero_liquidation_rows_are_not_feed_health": True,
        "exchange_instruments_not_used_as_pit": True,
        "coverage_grid_status": coverage_status,
        "coverage_grid_missing": list(coverage_missing),
        "observed_archive_bounds": bounds,
        "files": files,
        "no_market_magnitudes_exported": True,
        "statement": NO_MAGNITUDES_STATEMENT,
        "manifest_sha256_excludes_self": True,
    }
    path = out / "export_manifest.json"
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if _DSN_USERINFO.search(encoded):
        raise SystemExit("refusing to write a DSN into the manifest")
    path.write_text(encoded)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ("export_manifest.json", digest, 1)


def payloads_by_name(payloads, filename: str):
    for name, _columns, rows in payloads:
        if name == filename:
            return rows
    return []


def _connect(dsn: str, *, psycopg_module=None, psycopg2_module=None):
    psycopg = psycopg_module
    if psycopg is None:
        try:
            import psycopg
        except ImportError:
            psycopg = None
    if psycopg is not None:
        conn = psycopg.connect(dsn, autocommit=True)
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        conn.execute("SET default_transaction_read_only = on")
        return conn, "psycopg"
    psycopg2 = psycopg2_module
    if psycopg2 is None:
        try:
            import psycopg2
        except ImportError as exc:
            raise SystemExit(
                "install psycopg or psycopg2 on the database host; no write fallback is provided"
            ) from exc
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET TIME ZONE 'UTC'")
    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    cur.execute("SET default_transaction_read_only = on")
    cur.close()
    return conn, "psycopg2"


def _run_select(conn, driver: str, sql: str):
    assert_text_read_only(sql)
    if driver == "psycopg":
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            row = conn.execute("SHOW transaction_read_only").fetchone()
            if row is None or str(row[0]).lower() != "on":
                raise SystemExit("transaction is not read-only; aborting")
            cur = conn.execute(sql)
            header = [col.name for col in cur.description]
            rows = cur.fetchall()
        return header, rows
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute("BEGIN TRANSACTION READ ONLY")
        cur.execute("SHOW transaction_read_only")
        flag = cur.fetchone()
        if flag is None or str(flag[0]).lower() != "on":
            raise SystemExit("transaction is not read-only; aborting")
        cur.execute(sql)
        header = [col.name for col in cur.description]
        rows = cur.fetchall()
        conn.rollback()
        return header, rows
    finally:
        conn.rollback()
        conn.autocommit = True


def _write_csv(path: Path, columns: Sequence[str], rows: list) -> str:
    _reject_magnitude_columns(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _cell(row.get(column)) for column in columns})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_magnitude_columns(columns) -> None:
    bad = [column for column in columns if column.lower() in FORBIDDEN_EXPORT_COLUMNS]
    if bad:
        raise SystemExit(f"refusing to write magnitude columns: {','.join(bad)}")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise SystemExit("refusing to export a non-finite number")
        return format(value, "g")
    text = str(value)
    if _DSN_USERINFO.search(text):
        raise SystemExit("refusing to write a DSN")
    return text


def _iso(value: datetime) -> str:
    if not isinstance(value, datetime):
        return "" if value is None else str(value)
    if value.tzinfo is None:
        raise SystemExit("refusing to export a naive timestamp")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise SystemExit("database timestamp is naive; refusing to guess a zone")
        return value.astimezone(UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise SystemExit("database timestamp is naive; refusing to guess a zone")
    return parsed.astimezone(UTC)


def _as_dicts(header, rows) -> list:
    return [dict(zip(header, row)) for row in rows]


def _presence(schema_rows):
    tables = set()
    columns = set()
    for row in schema_rows:
        present = _optional_bool(row.get("present")) is True
        if row.get("kind") == "table" and present:
            tables.add(row.get("table_name"))
        if row.get("kind") == "column" and present:
            columns.add((row.get("table_name"), row.get("column_name")))
    return tables, columns


def _table_and_columns(tables, columns, table: str, required) -> bool:
    return table in tables and all(item in columns for item in required)


def _optional_bool(value):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def _is_missing_relation(exc: Exception) -> bool:
    message = redact(str(exc)).lower()
    return type(exc).__name__ == "UndefinedTable" or "does not exist" in message


def _resolve_git_sha(supplied):
    if supplied is not None:
        return supplied or None
    try:
        root = Path(__file__).resolve().parents[3]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = out.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", text):
        return None
    return text


if __name__ == "__main__":
    raise SystemExit(main())


