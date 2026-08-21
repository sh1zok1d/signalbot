"""Structural tests over `stage2_raw_revision`/`stage2_publication_state` in
storage/stage2_schema.sql (text-level; no DB needed) -- V2-H2e
correction-publication coherence barrier.

Amended per tech-lead review (round 2): the original single
`stage2_publication_state(symbol, market_type)` status table was replaced
by a revision-comparison model across TWO tables -- see
`storage/stage2_publication_state.py`'s module docstring. Mirrors
tests/storage/test_stage2_schema.py's own style for these two additive
tables."""
from __future__ import annotations

import re
from pathlib import Path

SQL = (Path(__file__).resolve().parents[2] / "storage" / "stage2_schema.sql").read_text()


def _table_block(name: str) -> str:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\);", SQL, re.DOTALL)
    assert m, f"table {name} not found"
    return m.group(1)


# ============================================================================
# stage2_raw_revision
# ============================================================================
def test_raw_revision_table_exists_additive_only():
    assert "CREATE TABLE IF NOT EXISTS stage2_raw_revision" in SQL


def test_raw_revision_columns_present():
    body = _table_block("stage2_raw_revision")
    for col in ("symbol", "market_type", "raw_revision", "last_bump_reason", "updated_at"):
        assert re.search(rf"^\s*{col}\b", body, re.MULTILINE), f"missing column {col}"


def test_raw_revision_primary_key_is_symbol_market_type():
    body = _table_block("stage2_raw_revision")
    m = re.search(r"PRIMARY KEY \(([^)]*)\)", body)
    assert m
    pk = tuple(p.strip() for p in m.group(1).split(","))
    assert pk == ("symbol", "market_type")


def test_raw_revision_no_calculation_version_column():
    # Raw market data has no calculation_version of its own -- this counter
    # must never be scoped by it (see schema comment).
    body = _table_block("stage2_raw_revision")
    assert "calculation_version" not in body


def test_raw_revision_nonneg_check_constraint():
    body = _table_block("stage2_raw_revision")
    assert "ck_srr_revision_nonneg" in body
    assert re.search(r"CHECK\s*\(\s*raw_revision\s*>=\s*0\s*\)", body, re.IGNORECASE)


def test_raw_revision_default_zero():
    body = _table_block("stage2_raw_revision")
    assert re.search(r"raw_revision\s+BIGINT\s+NOT NULL\s+DEFAULT\s+0", body, re.IGNORECASE)


def test_raw_revision_no_foreign_key_no_hypertable():
    body = _table_block("stage2_raw_revision")
    assert "REFERENCES" not in body.upper()
    assert "create_hypertable('stage2_raw_revision'" not in SQL


# ============================================================================
# stage2_publication_state
# ============================================================================
def test_publication_state_table_exists_additive_only():
    assert "CREATE TABLE IF NOT EXISTS stage2_publication_state" in SQL


def test_publication_state_columns_present():
    body = _table_block("stage2_publication_state")
    for col in ("symbol", "market_type", "calculation_version", "published_raw_revision",
                "publication_generation", "published_at", "updated_at"):
        assert re.search(rf"^\s*{col}\b", body, re.MULTILINE), f"missing column {col}"


def test_publication_state_primary_key_includes_calculation_version():
    body = _table_block("stage2_publication_state")
    m = re.search(r"PRIMARY KEY \(([^)]*)\)", body)
    assert m
    pk = tuple(p.strip() for p in m.group(1).split(","))
    assert pk == ("symbol", "market_type", "calculation_version")


def test_publication_state_no_status_enum_column():
    # The old CLEAN/DIRTY status text column is gone -- CLEAN-ness is now a
    # comparison against stage2_raw_revision, computed at read time, never a
    # separately-stored (and driftable) boolean/enum.
    body = _table_block("stage2_publication_state")
    assert not re.search(r"^\s*status\s+TEXT", body, re.MULTILINE)
    assert "ck_sps_status" not in body


def test_publication_state_check_constraints():
    body = _table_block("stage2_publication_state")
    assert "ck_sps_revision_nonneg" in body
    assert re.search(r"CHECK\s*\(\s*published_raw_revision\s*>=\s*0\s*\)", body, re.IGNORECASE)
    assert "ck_sps_generation_positive" in body
    assert re.search(r"CHECK\s*\(\s*publication_generation\s*>\s*0\s*\)", body, re.IGNORECASE)


def test_publication_state_no_foreign_key_no_hypertable():
    body = _table_block("stage2_publication_state")
    assert "REFERENCES" not in body.upper()
    assert "create_hypertable('stage2_publication_state'" not in SQL
