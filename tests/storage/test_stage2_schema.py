"""Structural tests over storage/stage2_schema.sql (text-level; no DB needed)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SQL = (Path(__file__).resolve().parents[2] / "storage" / "stage2_schema.sql").read_text()

EXPECTED_TABLES = [
    "symbols", "symbol_status_history", "exchange_instruments",
    "symbol_exchange_capabilities", "exchange_feature_vectors",
    "consensus_feature_vectors", "percentile_snapshots",
    "data_health_snapshots", "stage2_watermarks", "stage2_recompute_queue",
]


def _table_block(name: str) -> str:
    """Return the CREATE TABLE (...) body for `name`."""
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\);", SQL, re.DOTALL)
    assert m, f"table {name} not found"
    return m.group(1)


def _primary_key(name: str) -> str:
    body = _table_block(name)
    m = re.search(r"PRIMARY KEY \(([^)]*)\)", body)
    assert m, f"no PRIMARY KEY in {name}"
    return m.group(1)


# -- table set ---------------------------------------------------------------
def test_exactly_ten_create_table_statements():
    creates = re.findall(r"^CREATE TABLE IF NOT EXISTS (\w+)", SQL, re.MULTILINE)
    assert len(creates) == 10
    assert creates == EXPECTED_TABLES


# -- forbidden operations ----------------------------------------------------
def test_no_alter_drop_truncate_delete():
    assert not re.search(r"\bALTER\s+TABLE\b", SQL, re.IGNORECASE)
    assert not re.search(r"\bDROP\s+TABLE\b", SQL, re.IGNORECASE)
    assert not re.search(r"\bTRUNCATE\b", SQL, re.IGNORECASE)
    assert not re.search(r"\bDELETE\s+FROM\b", SQL, re.IGNORECASE)


def test_no_foreign_keys_or_references():
    assert not re.search(r"\bREFERENCES\b", SQL, re.IGNORECASE)
    assert not re.search(r"\bFOREIGN\s+KEY\b", SQL, re.IGNORECASE)


def test_only_additive_objects():
    # Only CREATE EXTENSION / TABLE / INDEX and create_hypertable SELECTs.
    statements = [s.strip() for s in re.sub(r"--[^\n]*", "", SQL).split(";") if s.strip()]
    for st in statements:
        head = st.split(None, 1)[0].upper()
        assert head in {"CREATE", "SELECT"}, f"unexpected statement head: {st[:40]!r}"
        if head == "SELECT":
            assert "create_hypertable" in st


# -- hypertables -------------------------------------------------------------
def test_required_hypertables_present():
    hypertables = set(re.findall(r"create_hypertable\('(\w+)'", SQL))
    assert hypertables == {
        "exchange_feature_vectors", "consensus_feature_vectors",
        "percentile_snapshots", "data_health_snapshots",
    }


# -- calculation_version in logical keys -------------------------------------
@pytest.mark.parametrize("table", [
    "exchange_feature_vectors", "consensus_feature_vectors",
    "percentile_snapshots", "data_health_snapshots", "stage2_watermarks",
])
def test_calculation_version_in_primary_key(table):
    assert "calculation_version" in _primary_key(table)


def test_data_health_pk_includes_calculation_version():
    assert "calculation_version" in _primary_key("data_health_snapshots")


def test_recompute_queue_calculation_version_in_dedup_index():
    m = re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job(.*?);", SQL, re.DOTALL)
    assert m and "calculation_version" in m.group(1)


# -- percentile constraints --------------------------------------------------
def test_percentile_constraints_present():
    body = _table_block("percentile_snapshots")
    assert "ck_ps_scope" in body
    assert "ck_ps_scope_exchange" in body
    assert "ck_ps_no_lookahead" in body
    assert "sample_window_end IS NULL OR sample_window_end < bucket_ts" in body


# -- unit contract -----------------------------------------------------------
def test_volume_raw_and_unit_present_no_volume_base():
    efv = _table_block("exchange_feature_vectors")
    assert "volume_raw" in efv
    assert "volume_raw_unit" in efv
    assert "volume_base" not in SQL


def test_no_raw_oi_sum_in_consensus():
    cfv = _table_block("consensus_feature_vectors")
    # notional sums are allowed; a raw OI sum is not.
    assert not re.search(r"oi\w*_sum", cfv)


def test_funding_median_and_mad_present():
    cfv = _table_block("consensus_feature_vectors")
    assert "funding_rate_median" in cfv
    assert "funding_rate_mad" in cfv


# -- recompute queue: ranged model, not bucket_ts-only -----------------------
def test_recompute_queue_ranged_model():
    body = _table_block("stage2_recompute_queue")
    assert "range_start_ts" in body
    assert "range_end_ts" in body
    assert "job_type" in body
    # the queue itself must NOT carry a bare bucket_ts column (old model)
    assert not re.search(r"^\s*bucket_ts\b", body, re.MULTILINE)


def test_pending_dedup_index_nulls_not_distinct_and_partial():
    m = re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job(.*?);", SQL, re.DOTALL)
    assert m
    idx = m.group(1)
    assert "NULLS NOT DISTINCT" in idx
    assert "WHERE processed_at IS NULL" in idx


def test_no_table_level_unique_in_recompute_queue():
    body = _table_block("stage2_recompute_queue")
    assert not re.search(r"\bUNIQUE\b", body, re.IGNORECASE)


# -- reserved-keyword: percentile_window, never a bare `window` column --------
def test_no_bare_window_column_reserved_keyword():
    # `window` is a PostgreSQL reserved keyword; it must never be a bare column.
    assert not re.search(r"(^|[^a-z0-9_])window[ \t]+(TEXT|VARCHAR|CHAR)",
                         SQL, re.IGNORECASE)
    assert "percentile_window" in SQL


def test_percentile_snapshots_uses_percentile_window():
    body = _table_block("percentile_snapshots")
    assert re.search(r"^\s*percentile_window\s+TEXT\s+NOT NULL", body, re.MULTILINE)
    pk = _primary_key("percentile_snapshots")
    assert "percentile_window" in pk
    assert re.search(r"\bwindow\b", pk) is None          # no bare window token


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


def test_recompute_queue_uses_percentile_window():
    body = _table_block("stage2_recompute_queue")
    assert re.search(r"^\s*percentile_window\s+TEXT", body, re.MULTILINE)
    # no bare `window` COLUMN (ignore explanatory comments)
    assert re.search(r"(^|[^a-z0-9_])window[ \t]+TEXT",
                     _strip_sql_comments(body), re.IGNORECASE) is None


def test_dedup_index_uses_percentile_window_and_keeps_contract():
    m = re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job(.*?);", SQL, re.DOTALL)
    assert m
    idx = m.group(1)
    assert "percentile_window" in idx
    assert re.search(r"\bwindow\b", idx) is None         # old bare name gone
    # ranged-queue dedup contract preserved
    assert "calculation_version" in idx
    assert "reason" in idx
    assert "NULLS NOT DISTINCT" in idx
    assert "WHERE processed_at IS NULL" in idx
