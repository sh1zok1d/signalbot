"""Structural tests over `stage2_publication_state` in storage/stage2_schema.sql
(text-level; no DB needed) -- V2-H2e correction-publication coherence barrier.

Mirrors tests/storage/test_stage2_schema.py's own style for this ONE
additive table."""
from __future__ import annotations

import re
from pathlib import Path

SQL = (Path(__file__).resolve().parents[2] / "storage" / "stage2_schema.sql").read_text()


def _table_block(name: str) -> str:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\);", SQL, re.DOTALL)
    assert m, f"table {name} not found"
    return m.group(1)


def test_table_exists_additive_only():
    assert "CREATE TABLE IF NOT EXISTS stage2_publication_state" in SQL


def test_columns_present():
    body = _table_block("stage2_publication_state")
    for col in ("symbol", "market_type", "status", "publication_generation",
                "dirty_reason", "dirty_since", "clean_since", "updated_at"):
        assert re.search(rf"^\s*{col}\b", body, re.MULTILINE), f"missing column {col}"


def test_primary_key_is_symbol_market_type():
    body = _table_block("stage2_publication_state")
    m = re.search(r"PRIMARY KEY \(([^)]*)\)", body)
    assert m
    pk = tuple(p.strip() for p in m.group(1).split(","))
    assert pk == ("symbol", "market_type")


def test_status_check_constraint():
    body = _table_block("stage2_publication_state")
    assert "ck_sps_status" in body
    assert re.search(r"CHECK\s*\(\s*status\s+IN\s*\(\s*'CLEAN'\s*,\s*'DIRTY'\s*\)\s*\)",
                     body, re.IGNORECASE)


def test_generation_nonneg_check_constraint():
    body = _table_block("stage2_publication_state")
    assert "ck_sps_generation_nonneg" in body
    assert re.search(r"CHECK\s*\(\s*publication_generation\s*>=\s*0\s*\)", body, re.IGNORECASE)


def test_default_status_clean_generation_zero():
    body = _table_block("stage2_publication_state")
    assert re.search(r"status\s+TEXT\s+NOT NULL\s+DEFAULT\s+'CLEAN'", body, re.IGNORECASE)
    assert re.search(r"publication_generation\s+BIGINT\s+NOT NULL\s+DEFAULT\s+0", body, re.IGNORECASE)


def test_no_foreign_key_no_hypertable():
    body = _table_block("stage2_publication_state")
    assert "REFERENCES" not in body.upper()
    # a state singleton-per-scope table, not a time series -- must NOT be
    # registered as a hypertable
    assert "create_hypertable('stage2_publication_state'" not in SQL
