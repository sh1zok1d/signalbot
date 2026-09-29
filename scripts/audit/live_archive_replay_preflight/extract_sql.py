"""Load and check the packaged coverage SELECT script."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY"
    r"|INTO|LOCK|CALL|VACUUM|ANALYZE|MERGE|COMMENT|DO)\b",
    re.IGNORECASE,
)
_STATEMENT = re.compile(r"(?m)^-- statement: ([a-z0-9_]+)\s*$")
_BLOCK = {
    "LIQ": re.compile(r"/\* LIQ_BLOCK \*/.*?/\* END_LIQ_BLOCK \*/", re.DOTALL),
    "PIT": re.compile(r"/\* PIT_BLOCK \*/.*?/\* END_PIT_BLOCK \*/", re.DOTALL),
}

EXCHANGES = ("binance", "bybit", "okx")
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

# Column names that would carry market magnitudes. They may appear in schema
# availability as names. They must not be coverage-export result aliases.
FORBIDDEN_EXPORT_COLUMNS = frozenset({
    "open", "high", "low", "close", "volume", "taker_buy_volume", "taker_sell_volume",
    "trades_count", "oi_raw", "oi_contracts", "oi_notional", "oi_notional_usd",
    "contract_value", "oi_base_asset", "notional", "price", "qty", "mark_price",
    "funding_rate", "contract_multiplier", "tick_size", "price_precision",
    "quantity_precision",
})

SQL_COVERAGE_COLUMNS = (
    "bucket_start",
    "exchange",
    "live_bar_row_count",
    "distinct_expected_live_minutes",
    "offslot_live_bar_count",
    "first_live_minute_ts",
    "last_live_minute_ts",
    "first_expected_bar_present",
    "first_expected_open_is_zero",
    "taker_split_complete_expected_minutes",
    "live_oi_row_count",
    "usable_oi_distinct_timestamps",
    "oi_duplicate_timestamp_count",
    "oi_distinct_unit_count",
    "oi_units",
    "first_usable_oi_is_zero_or_null",
    "first_usable_oi_ts",
    "last_usable_oi_ts",
    "pit_table_present",
    "pit_row_count",
    "pit_quantity_unit",
    "pit_multiplier_present",
    "liquidation_table_present",
    "liquidation_event_count",
    "liquidation_has_long",
    "liquidation_has_short",
    "in_requested_interval",
)

# kind, table, column or None, eligibility role
SCHEMA_REQUIREMENTS = (
    ("table", "klines_1m", None, "market"),
    ("column", "klines_1m", "exchange", "market"),
    ("column", "klines_1m", "symbol", "market"),
    ("column", "klines_1m", "ts", "market"),
    ("column", "klines_1m", "open", "market"),
    ("column", "klines_1m", "source", "market"),
    ("column", "klines_1m", "taker_buy_volume", "market"),
    ("column", "klines_1m", "taker_sell_volume", "market"),
    ("table", "open_interest", None, "market"),
    ("column", "open_interest", "exchange", "market"),
    ("column", "open_interest", "symbol", "market"),
    ("column", "open_interest", "ts", "market"),
    ("column", "open_interest", "source", "market"),
    ("column", "open_interest", "oi_raw", "market"),
    ("column", "open_interest", "oi_unit", "market"),
    ("table", "liquidations", None, "market"),
    ("column", "liquidations", "exchange", "market"),
    ("column", "liquidations", "symbol", "market"),
    ("column", "liquidations", "ts", "market"),
    ("column", "liquidations", "side", "market"),
    ("table", "connectivity_events", None, "feed_health"),
    ("column", "connectivity_events", "id", "feed_health"),
    ("column", "connectivity_events", "exchange", "feed_health"),
    ("column", "connectivity_events", "event_type", "feed_health"),
    ("column", "connectivity_events", "ts", "feed_health"),
    ("column", "connectivity_events", "detail", "feed_health"),
    ("table", "exchange_instrument_history", None, "pit"),
    ("column", "exchange_instrument_history", "exchange", "pit"),
    ("column", "exchange_instrument_history", "symbol", "pit"),
    ("column", "exchange_instrument_history", "market_type", "pit"),
    ("column", "exchange_instrument_history", "quantity_unit", "pit"),
    ("column", "exchange_instrument_history", "contract_multiplier", "pit"),
    ("column", "exchange_instrument_history", "effective_from", "pit"),
    ("column", "exchange_instrument_history", "effective_until", "pit"),
    ("table", "exchange_instruments", None, "not_used_as_pit"),
    ("table", "symbol_exchange_capabilities", None, "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "exchange", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "symbol", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "market_type", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "metric", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "live_supported", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "enabled", "liquidation_declared"),
    ("column", "symbol_exchange_capabilities", "coverage_type", "liquidation_declared"),
)

STATEMENT_TABLES = {
    "archive_klines": ("klines_1m",),
    "archive_open_interest": ("open_interest",),
    "archive_liquidations": ("liquidations",),
    "archive_connectivity": ("connectivity_events",),
    "archive_instrument_history": ("exchange_instrument_history",),
    "oi_unit_changes": ("open_interest",),
    "instrument_history_intervals": ("exchange_instrument_history",),
    "connectivity_events": ("connectivity_events",),
    "liquidation_capability": ("symbol_exchange_capabilities",),
    "coverage_grid": ("klines_1m", "open_interest"),
}

_LIQ_DUMMY = """
, liq_agg AS (
    SELECT
        NULL::timestamptz AS bucket_start,
        NULL::text AS exchange,
        NULL::bigint AS liquidation_event_count,
        NULL::boolean AS liquidation_has_long,
        NULL::boolean AS liquidation_has_short
    WHERE FALSE
)
"""

_PIT_DUMMY = """
, pit_agg AS (
    SELECT
        NULL::timestamptz AS bucket_start,
        NULL::text AS exchange,
        NULL::bigint AS pit_row_count,
        NULL::text AS pit_quantity_unit,
        NULL::boolean AS pit_multiplier_present
    WHERE FALSE
)
"""


def assert_text_read_only(text: str) -> None:
    if _FORBIDDEN.search(text):
        raise ValueError("SQL contains a statement this exporter must not run")


def sql_text() -> str:
    return Path(__file__).with_name("extract_coverage_readonly.sql").read_text()


def split_named_statements(text: str) -> list[tuple[str, str]]:
    assert_text_read_only(text)
    parts = _STATEMENT.split(text)
    if len(parts) < 3 or len(parts) % 2 != 1:
        raise ValueError("SQL file has no named statements")
    found = []
    for index in range(1, len(parts), 2):
        name = parts[index]
        body = parts[index + 1].strip()
        if body.endswith(";"):
            body = body[:-1].strip()
        if not body:
            raise ValueError(f"empty statement {name}")
        stripped = _strip_comments(body).lstrip()
        if not re.match(r"(?is)^(SELECT|WITH)\b", stripped):
            raise ValueError(f"refusing non-SELECT statement {name}")
        found.append((name, body))
    names = [name for name, _ in found]
    if names != list(STATEMENT_TABLES):
        raise ValueError(f"unexpected statements: {names}")
    return found


def schema_availability_sql() -> str:
    values = []
    for kind, table, column, _role in SCHEMA_REQUIREMENTS:
        column_sql = "NULL::text" if column is None else "'" + column + "'"
        values.append(f"('{kind}', '{table}', {column_sql})")
    sql = (
        "-- statement: schema_availability\n"
        "SELECT req.kind, req.table_name, req.column_name,\n"
        "    CASE\n"
        "        WHEN req.kind = 'table' THEN to_regclass('public.' || req.table_name) IS NOT NULL\n"
        "        ELSE c.column_name IS NOT NULL\n"
        "    END AS present\n"
        "FROM (VALUES\n    "
        + ",\n    ".join(values)
        + "\n) AS req(kind, table_name, column_name)\n"
        "LEFT JOIN information_schema.columns AS c\n"
        "  ON c.table_schema = 'public'\n"
        " AND c.table_name = req.table_name\n"
        " AND c.column_name = req.column_name\n"
        "ORDER BY req.table_name, req.kind, req.column_name"
    )
    assert_text_read_only(sql)
    return sql


def render_statements(
    *,
    lookback_start: datetime,
    interval_end: datetime,
    requested_start: datetime,
    pit_table_present: bool,
    liquidation_table_present: bool,
) -> list[tuple[str, str]]:
    rendered = []
    for name, body in split_named_statements(sql_text()):
        if name == "coverage_grid":
            body = _render_coverage(
                body,
                lookback_start=lookback_start,
                interval_end=interval_end,
                requested_start=requested_start,
                pit_table_present=pit_table_present,
                liquidation_table_present=liquidation_table_present,
            )
        else:
            body = body.replace("__INTERVAL_END__", _ts_literal(interval_end))
        if "__" in body:
            raise ValueError(f"unreplaced token in {name}")
        assert_text_read_only(body)
        rendered.append((name, body))
    return rendered


def output_aliases(coverage_sql: str) -> list[str]:
    marker = "-- OUTPUT_COLUMNS"
    if marker not in coverage_sql:
        raise ValueError("coverage SQL is missing OUTPUT_COLUMNS")
    tail = coverage_sql.split(marker, 1)[1]
    select_list = tail.split("FROM grid", 1)[0]
    return re.findall(r"\bAS\s+([a-z_]+)\b", select_list)


def _render_coverage(
    body: str,
    *,
    lookback_start: datetime,
    interval_end: datetime,
    requested_start: datetime,
    pit_table_present: bool,
    liquidation_table_present: bool,
) -> str:
    if not liquidation_table_present:
        body = _BLOCK["LIQ"].sub(_LIQ_DUMMY.strip(), body, count=1)
    if not pit_table_present:
        body = _BLOCK["PIT"].sub(_PIT_DUMMY.strip(), body, count=1)
    if "LIQ_BLOCK" in body or "PIT_BLOCK" in body:
        if (liquidation_table_present and "LIQ_BLOCK" not in body) or (
            pit_table_present and "PIT_BLOCK" not in body
        ):
            raise ValueError("coverage block marker disappeared unexpectedly")
    if not liquidation_table_present and "FROM liquidations" in body:
        raise ValueError("liquidation-absent coverage still reads liquidations")
    if not pit_table_present and "exchange_instrument_history" in body:
        raise ValueError("pit-absent coverage still reads instrument history")
    replacements = {
        "__LOOKBACK_START__": _ts_literal(lookback_start),
        "__INTERVAL_END__": _ts_literal(interval_end),
        "__REQUESTED_START__": _ts_literal(requested_start),
        "__PIT_TABLE_PRESENT__": "TRUE" if pit_table_present else "FALSE",
        "__LIQ_TABLE_PRESENT__": "TRUE" if liquidation_table_present else "FALSE",
    }
    for token, value in replacements.items():
        if token not in body:
            raise ValueError(f"missing token {token}")
        body = body.replace(token, value)
    aliases = output_aliases(body)
    if tuple(aliases) != SQL_COVERAGE_COLUMNS:
        raise ValueError(f"coverage output columns drifted: {aliases}")
    if set(aliases) & FORBIDDEN_EXPORT_COLUMNS:
        raise ValueError("coverage SQL exports a market magnitude column")
    return body


def _ts_literal(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp literal requires a timezone")
    text = value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+00", text):
        raise ValueError("refusing to interpolate an unexpected timestamp")
    return f"TIMESTAMPTZ '{text}'"


def _strip_comments(body: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", body, flags=re.DOTALL)
    lines = []
    for line in without_block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def load_statements() -> tuple[tuple[str, str], ...]:
    return tuple(split_named_statements(sql_text()))


STATEMENTS = load_statements()
