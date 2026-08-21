"""Structural assertions on the additive `exchange_instrument_history` DDL
in `storage/stage2_schema.sql` (no Docker / PostgreSQL). Parsing mirrors
`tests/storage/test_v2_version_switch_schema.py`.

Real PostgreSQL behavior (as-of resolution, non-overlap, transactional
close-then-open, restart) is proven separately in
`tests/storage/test_v2_instrument_history_readers.py` -- this file only
checks the DDL text itself: presence, shape, and that it does not touch
anything outside its own table (V2-H2c,
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a)."""
from __future__ import annotations

import re
from pathlib import Path

SQL = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")

TABLE = "exchange_instrument_history"


def _table_body(table: str) -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", SQL, re.S)
    assert m, f"{table} table not found"
    return m.group(1)


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


_BODY = _table_body(TABLE)
_SECTION = SQL[SQL.index("V2-H2c: as-of/historical instrument metadata"):]
_SECTION_CODE = _strip_sql_comments(_SECTION)


def _columns(body: str) -> list[str]:
    cols = []
    col_re = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s+(TEXT|TIMESTAMPTZ|DOUBLE PRECISION|INTEGER)\b")
    for line in body.splitlines():
        m = col_re.match(line)
        if m:
            cols.append(m.group(1))
    return cols


def _pk(body: str) -> list[str]:
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


# ---- table presence & scope -------------------------------------------------
def test_exactly_one_exchange_instrument_history_table():
    assert len(re.findall(
        r"CREATE TABLE IF NOT EXISTS exchange_instrument_history\b", SQL)) == 1


def test_section_touches_no_other_table():
    code = _SECTION_CODE
    for t in ("exchange_instruments", "v2_episode_events", "v2_version_switch_state",
              "klines_1m", "consensus_feature_vectors", "symbol_exchange_capabilities"):
        assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\b" + t + r"\b", code), t
    assert "ALTER TABLE" not in code   # CREATE-only, no upgrade path needed.
    assert "DROP" not in code.upper()


def test_no_foreign_keys_in_this_table():
    assert "REFERENCES" not in _BODY
    assert "FOREIGN KEY" not in _BODY


def test_never_reads_or_writes_exchange_instruments():
    """The whole point of H2c is that this history table is SEPARATE from
    the current/LKG `exchange_instruments` snapshot -- the two must never
    be conflated at the schema level either."""
    assert "exchange_instruments" not in _BODY
    # Strip every "exchange_instrument_history"/"...ux_eih..." occurrence
    # first so the substring "exchange_instruments" can't false-positive
    # against "exchange_instrument_history" itself.
    code_without_history_refs = _SECTION_CODE.replace("exchange_instrument_history", "")
    assert "exchange_instruments" not in code_without_history_refs


# ---- columns / PK -----------------------------------------------------------
_EXPECTED_COLUMNS = [
    "exchange", "symbol", "market_type", "exchange_instrument_id", "quantity_unit",
    "contract_multiplier", "tick_size", "price_precision", "quantity_precision",
    "metadata_source", "observed_at", "effective_from", "effective_until", "note",
    "accepted_metadata_revision", "recorded_at",
]


def test_columns_match_expected_shape():
    """Column set mirrors `exchange_instruments`' own data-field shape
    exactly, plus the identity/temporal/provenance fields H2c adds
    (`observed_at`/`effective_from`/`effective_until`/
    `accepted_metadata_revision`/`recorded_at`) — deliberately NO
    `is_stale` (a current/LKG-only concept; a historical interval is
    either the version in effect or it is not)."""
    assert _columns(_BODY) == _EXPECTED_COLUMNS
    assert "is_stale" not in _BODY


def test_observed_at_is_nullable_not_not_null():
    """(Tech-lead review 4990482334, finding 1/2) `observed_at` is
    PROVENANCE ONLY and must be nullable -- a manual/declared-fallback
    value with no honest fetch timestamp is legal, provided
    `effective_from` is still supplied explicitly."""
    assert re.search(r"observed_at\s+TIMESTAMPTZ,", _BODY)
    assert not re.search(r"observed_at\s+TIMESTAMPTZ NOT NULL", _BODY)


def test_effective_from_is_not_null():
    assert re.search(r"effective_from\s+TIMESTAMPTZ NOT NULL,", _BODY)


def test_observed_at_not_after_effective_from_check_present():
    assert re.search(
        r"observed_at IS NULL OR observed_at <= effective_from", _BODY)


def test_accepted_metadata_revision_positive_check_present():
    assert re.search(
        r"accepted_metadata_revision IS NULL OR accepted_metadata_revision > 0",
        _BODY)


def test_primary_key_is_identity_plus_effective_from():
    assert _pk(_BODY) == ["exchange", "symbol", "market_type", "effective_from"]


# ---- CHECK constraints -------------------------------------------------------
def test_quantity_unit_and_metadata_source_checks_mirror_exchange_instruments():
    assert re.search(r"quantity_unit IS NULL OR quantity_unit IN \('base','contracts'\)", _BODY)
    assert re.search(
        r"metadata_source IN \('exchange_api','declared_fallback','manual'\)", _BODY)


def test_tick_size_and_contract_multiplier_positivity_checks_present():
    """(CodeRabbit finding 3) A naive `CHECK (... > 0)` on a float8 column
    does NOT reject NaN/+Infinity (Postgres's float8 ordering treats both
    as "greater than any value"); the schema's own CHECK is tightened to
    also require `< 'Infinity'::float8`, which NaN/+Infinity both fail."""
    assert re.search(
        r"tick_size IS NULL OR \(tick_size > 0 AND tick_size < 'Infinity'::float8\)", _BODY)
    assert re.search(
        r"contract_multiplier IS NULL OR\s*\n\s*\(contract_multiplier > 0 AND "
        r"contract_multiplier < 'Infinity'::float8\)", _BODY)


def test_precision_fields_nonnegative_checks_present():
    assert re.search(r"price_precision IS NULL OR price_precision >= 0", _BODY)
    assert re.search(r"quantity_precision IS NULL OR quantity_precision >= 0", _BODY)


def test_interval_well_formed_check_present():
    assert re.search(r"effective_until IS NULL OR effective_until > effective_from", _BODY)


def test_one_open_interval_per_identity_partial_unique_index_present():
    """The cheap, DB-level defense against two concurrently-open intervals
    for the same identity -- see the table's own comment for why this,
    plus transactional close-then-open, is chosen over a btree_gist
    exclusion constraint."""
    assert "ux_eih_one_open_interval_per_identity" in _SECTION_CODE
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS ux_eih_one_open_interval_per_identity\s*\n"
        r"\s*ON exchange_instrument_history \(exchange, symbol, market_type\)\s*\n"
        r"\s*WHERE effective_until IS NULL",
        _SECTION_CODE)


def test_no_exclusion_constraint_or_extension_added():
    """Explicit non-goal (item 8): no btree_gist/EXCLUDE USING -- narrowest
    durable model, not a generic bitemporal framework."""
    assert "EXCLUDE" not in _SECTION_CODE.upper()
    assert "btree_gist" not in _SECTION_CODE
    assert "CREATE EXTENSION" not in _SECTION_CODE.upper()


def test_recorded_at_is_db_owned_metadata_only():
    assert re.search(r"recorded_at\s+TIMESTAMPTZ NOT NULL DEFAULT now\(\)", _BODY)


def test_observed_at_and_effective_from_are_not_db_defaulted():
    """Both are always caller-supplied -- `observed_at` from a real fetch's
    own timestamp (or explicitly NULL for a manual/declared value),
    `effective_from` from the caller's own explicit V2 decision-time
    acceptance boundary -- never `DEFAULT now()`, which would silently
    fabricate a wall-clock timestamp instead of the real one, and never
    silently derived from each other."""
    assert not re.search(r"observed_at\s+TIMESTAMPTZ.*DEFAULT", _BODY)
    assert not re.search(r"effective_from\s+TIMESTAMPTZ.*DEFAULT", _BODY)


# ============================================================================
# Tech-lead review 4991738511: stage2_instrument_metadata_state -- the ONE
# GLOBAL, Stage-2-wide row every feature computation must agree with before
# constructing a feature vector (analytics/feature_engine/input_adapter.py::
# assemble_exchange_feature_request). Structural DDL assertions only; the
# real end-to-end fork/fail-closed proof lives in
# tests/analytics/test_stage2_metadata_revision_fork.py and the real-Postgres
# atomic-bump/lock proof lives in tests/storage/test_v2_instrument_history_readers.py.
# ============================================================================
_REVISION_TABLE = "stage2_instrument_metadata_state"
_REVISION_BODY = _table_body(_REVISION_TABLE)


def test_exactly_one_stage2_instrument_metadata_state_table():
    assert len(re.findall(
        r"CREATE TABLE IF NOT EXISTS stage2_instrument_metadata_state\b", SQL)) == 1


def test_revision_table_columns_and_pk():
    assert _columns(_REVISION_BODY) == ["required_revision", "updated_at"]
    assert _pk(_REVISION_BODY) == ["singleton"]


def test_revision_table_singleton_and_positivity_checks_present():
    assert re.search(r"CONSTRAINT ck_s2ims_singleton_true CHECK \(\s*singleton\s*\)",
                      _REVISION_BODY)
    assert re.search(r"CONSTRAINT ck_s2ims_revision_positive CHECK \(\s*required_revision > 0\s*\)",
                      _REVISION_BODY)


def test_revision_table_no_default_seed_row_in_ddl():
    """(Finding 11) The initial value is established EXPLICITLY from the
    caller's own resolved Stage 2 configuration via
    `Database.bootstrap_instrument_metadata_revision` -- never a hardcoded
    DDL literal that could silently drift from config."""
    section = SQL[SQL.index("stage2_instrument_metadata_state ("):]
    section = section[:section.index(");") + 2]
    assert "INSERT INTO stage2_instrument_metadata_state" not in section


def test_revision_table_no_foreign_keys():
    assert "REFERENCES" not in _REVISION_BODY
    assert "FOREIGN KEY" not in _REVISION_BODY


# ============================================================================
# CodeRabbit finding 6: `tests/storage/test_v2_instrument_history_readers.py`
# (and `tests/storage/test_stage2_raw_bundle_snapshot.py`, which reuses that
# module's own copies) hand-copies exchange_instruments/
# exchange_instrument_history/stage2_instrument_metadata_state DDL for real-
# Postgres tests, deliberately avoiding `Database.init_stage2_schema()`'s
# TimescaleDB dependency (see that module's own docstring). The smallest
# robust drift guard: parse BOTH the production definitions and the test's
# own hand-copied text the SAME way and assert they describe the identical
# column set, PRIMARY KEY, and CHECK constraints (name + predicate) -- so a
# future production schema change can never silently diverge from what the
# real-Postgres test suite actually exercises.
# ============================================================================
def _generic_table_body(ddl_text: str, table: str) -> str:
    m = re.search(r"CREATE TABLE (?:IF NOT EXISTS )?" + table + r"\s*\((.*?)\n\);",
                  ddl_text, re.S)
    assert m, f"{table} not found in given DDL text"
    return m.group(1)


def _constraints(body: str) -> "list[tuple[str, str]]":
    """Ordered (name, whitespace-normalized predicate) pairs for every
    `CONSTRAINT <name> CHECK (...)` clause. Handles at most one level of
    parenthesis nesting inside the CHECK's own outer parens -- sufficient
    for every constraint this table actually declares."""
    pattern = re.compile(r"CONSTRAINT\s+(\w+)\s+CHECK\s*\(((?:[^()]|\([^()]*\))*)\)", re.S)
    return [(name, " ".join(pred.split())) for name, pred in pattern.findall(body)]


def test_hand_copied_test_ddl_matches_production_for_exchange_instruments():
    from tests.storage.test_v2_instrument_history_readers import _EXCHANGE_INSTRUMENTS_DDL
    prod_body = _table_body("exchange_instruments")
    test_body = _generic_table_body(_EXCHANGE_INSTRUMENTS_DDL, "exchange_instruments")
    assert _columns(test_body) == _columns(prod_body)
    assert _pk(test_body) == _pk(prod_body)
    assert _constraints(test_body) == _constraints(prod_body)


def test_hand_copied_test_ddl_matches_production_for_exchange_instrument_history():
    from tests.storage.test_v2_instrument_history_readers import _EXCHANGE_INSTRUMENT_HISTORY_DDL
    test_body = _generic_table_body(
        _EXCHANGE_INSTRUMENT_HISTORY_DDL, "exchange_instrument_history")
    assert _columns(test_body) == _columns(_BODY)
    assert _pk(test_body) == _pk(_BODY)
    assert _constraints(test_body) == _constraints(_BODY)


def test_hand_copied_test_ddl_matches_production_for_stage2_instrument_metadata_state():
    from tests.storage.test_v2_instrument_history_readers import (
        _STAGE2_INSTRUMENT_METADATA_STATE_DDL,
    )
    test_body = _generic_table_body(
        _STAGE2_INSTRUMENT_METADATA_STATE_DDL, "stage2_instrument_metadata_state")
    assert _columns(test_body) == _columns(_REVISION_BODY)
    assert _pk(test_body) == _pk(_REVISION_BODY)
    assert _constraints(test_body) == _constraints(_REVISION_BODY)
