"""Structural assertions on the additive v2_episode_events DDL in
storage/stage2_schema.sql (no Docker / PostgreSQL). Parsing mirrors
tests/storage/test_forecast_prediction_schema.py, plus schema/model/spec
parity for the new immutable V2 episode-event table.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from analytics.forecasting_v2.events import V2EpisodeEvent
from storage.v2_serialization import V2_EPISODE_EVENT_SPEC

SQL = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")


def _table_body(table: str) -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", SQL, re.S)
    assert m, f"{table} table not found"
    return m.group(1)


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


_V2EE_BODY = _table_body("v2_episode_events")
_V2EE_SECTION = SQL[
    SQL.index("V2 episode events"):
    SQL.index("V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch durable state")]
_V2EE_SECTION_CODE = _strip_sql_comments(_V2EE_SECTION)


def _columns(body: str) -> list[str]:
    cols = []
    col_re = re.compile(
        r"^\s*([a-z_][a-z0-9_]*)\s+"
        r"(TEXT|INTEGER|BIGINT|DOUBLE|TIMESTAMPTZ|BOOLEAN|JSONB|BIGSERIAL)\b")
    for line in body.splitlines():
        m = col_re.match(line)
        if m:
            cols.append(m.group(1))
    return cols


def _jsonb_columns(body: str) -> set[str]:
    return {c for c in _columns(body)
            if re.search(r"^\s*" + c + r"\s+JSONB\b", body, re.M)}


def _pk(body: str) -> list[str]:
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


# ---- table presence & scope -------------------------------------------------
def test_exactly_one_v2_episode_events_table():
    assert len(re.findall(r"CREATE TABLE IF NOT EXISTS v2_episode_events\b", SQL)) == 1


def test_v2_section_does_not_touch_other_tables():
    code = _V2EE_SECTION_CODE
    assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\bforecast_predictions\b", code)
    assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\bforecast_outcomes\b", code)
    for t in ("klines_1m", "open_interest", "funding_rate", "mark_price",
              "liquidations", "exchange_capabilities"):
        assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\b" + t + r"\b", code), t


def test_v2ee_alter_table_statements_target_only_this_table():
    # V2-H3 adds an additive, idempotent upgrade-path ALTER TABLE
    # (decision_code_version) -- this table is no longer CREATE-only, but
    # every ALTER TABLE in this section must still target v2_episode_events
    # itself, never a different table.
    code = _V2EE_SECTION_CODE
    targets = re.findall(r"ALTER\s+TABLE\s+(\w+)", code)
    assert targets, "expected at least one ALTER TABLE statement (V2-H3 upgrade path)"
    assert set(targets) == {"v2_episode_events"}


def test_v1_tables_still_pinned_model_family_v1_unchanged():
    # This PR must NOT relax PR #30's V1-only CHECK constraints.
    fp_body = _table_body("forecast_predictions")
    fo_body = _table_body("forecast_outcomes")
    assert re.search(r"model_family\s*=\s*'v1'", fp_body)
    assert re.search(r"model_family\s*=\s*'v1'", fo_body)
    assert "ck_fp_model_family" in fp_body
    assert "ck_fo_model_family" in fo_body


def test_v1_primary_keys_and_rule_version_unchanged():
    fp_body = _table_body("forecast_predictions")
    fo_body = _table_body("forecast_outcomes")
    assert _pk(fp_body) == [
        "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
        "rule_version"]
    assert _pk(fo_body) == [
        "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
        "rule_version", "horizon", "evaluation_exchange", "evaluation_price_source",
        "outcome_version"]
    assert re.search(r"rule_version\s+TEXT\s+NOT\s+NULL", fp_body)
    assert re.search(r"rule_version\s+TEXT\s+NOT\s+NULL", fo_body)


# ---- columns ------------------------------------------------------------------
def test_required_columns_present_in_order():
    expected = [
        "run_kind", "run_id", "event_id", "episode_id",
        "model_family", "rules_version",
        "symbol", "market_type", "direction", "setup_family", "structural_anchor",
        "episode_state", "decision_boundary",
        "feature_schema_version", "calculation_version", "config_hash",
        "config_version", "code_version", "decision_code_version",
        "decision_snapshot", "event_payload",
        "created_at",
    ]
    assert _columns(_V2EE_BODY) == expected


def test_created_at_in_schema_but_not_model():
    assert "created_at" in _columns(_V2EE_BODY)
    model_fields = {f.name for f in dataclasses.fields(V2EpisodeEvent)}
    assert "created_at" not in model_fields


def test_created_at_defaults_to_now():
    assert re.search(r"created_at\s+TIMESTAMPTZ\s+NOT NULL\s+DEFAULT now\(\)", _V2EE_BODY)


# ---- primary key: run namespace ------------------------------------------------
def test_primary_key_is_run_namespace():
    assert _pk(_V2EE_BODY) == ["run_kind", "run_id", "event_id"]


def test_episode_id_not_in_primary_key():
    # episode_id groups events into one logical episode's history but is NOT
    # part of the storage identity -- multiple events (one per state
    # transition) share one episode_id under the same run.
    assert "episode_id" not in _pk(_V2EE_BODY)


# ---- CHECK constraints: run provenance -----------------------------------------
def test_run_kind_check():
    assert re.search(r"run_kind\s+IN\s*\(\s*'LIVE'\s*,\s*'REPLAY'\s*\)", _V2EE_BODY)


def test_run_id_event_id_episode_id_nonblank_checks():
    for col in ("run_id", "event_id", "episode_id"):
        assert re.search(r"length\(btrim\(" + col + r"\)\)\s*>\s*0", _V2EE_BODY), col


# ---- CHECK constraints: model/version identity ---------------------------------
def test_model_family_pinned_to_v2():
    assert re.search(r"model_family\s*=\s*'v2'", _V2EE_BODY)


def test_rules_version_namespace_check():
    assert "ck_v2ee_rules_version" in _V2EE_BODY
    assert "v2-rules-v" in _V2EE_BODY


def test_rules_version_check_matches_python_validator():
    # HONESTY NOTE: this is a structural/semantic PROXY, not a real
    # PostgreSQL integration test — no ephemeral Postgres/Timescale harness
    # is available in this environment (see PR #31's/#32's own final
    # reports). It compiles the SQL CHECK's own regex TEXT with Python's
    # `re` and exercises it against the same accept/reject vectors
    # `common.v2_config.RULES_VERSION_RE` / `validate_rules_version` are
    # tested against (tests/common/test_v2_config.py), so a divergence
    # between the two independently-maintained patterns fails loudly here.
    # It does NOT prove PostgreSQL's own POSIX ERE engine (via `~`) accepts
    # exactly this set — POSIX ERE and Python `re` are different engines —
    # only that the two patterns' *source text* implies the same accepted
    # shape under a careful, `fullmatch()`-based reading.
    #
    # Using `.fullmatch()`, never `.match()`: Python's `$` can match
    # immediately before a trailing newline even without MULTILINE, so
    # `match()` would silently accept "v2-rules-v0.1.0\n" as if it fully
    # matched. `fullmatch()` requires the pattern to consume the entire
    # string, so a trailing LF/CR/space is correctly rejected regardless of
    # whether the extracted pattern text still carries its own `^...$`
    # anchors (harmless but redundant under fullmatch).
    m = re.search(r"CHECK \(rules_version ~ '(\^v2-rules-v.*?\$)'\)", _V2EE_BODY)
    assert m, "rules_version CHECK pattern not found"
    sql_pattern = m.group(1)
    py_re = re.compile(sql_pattern)

    accept = [
        "v2-rules-v0.1.0",
        "v2-rules-v12.34.56",
        "v2-rules-v0.0.0",
    ]
    reject = [
        "v2-rules-v01.0.0",       # leading zero, major
        "v2-rules-v0.01.0",       # leading zero, minor
        "v2-rules-v0.1.00",       # leading zero, patch
        "v2-rules-v0.1",          # missing patch component
        "forecast-rules-v0.1.0",  # V1 namespace
        "v2-rules-v0.1.0\n",      # trailing LF
        "v2-rules-v0.1.0\r",      # trailing CR
        "v2-rules-v0.1.0 ",       # trailing space
        " v2-rules-v0.1.0",       # leading space
        "v2-rules-v1٢.0.0",       # Arabic-Indic digit (non-ASCII)
        "v2-rules-v1१.0.0",       # Devanagari digit (non-ASCII)
    ]
    for good in accept:
        assert py_re.fullmatch(good), f"expected ACCEPT: {good!r}"
    for bad in reject:
        assert not py_re.fullmatch(bad), f"expected REJECT: {bad!r}"


# ---- CHECK constraints: episode logical dimensions -----------------------------
def test_symbol_and_market_type_pinned_to_initial_v2_scope():
    assert re.search(r"symbol\s*=\s*'BTCUSDT'", _V2EE_BODY)
    assert re.search(r"market_type\s*=\s*'perp'", _V2EE_BODY)


def test_direction_check_long_short_only():
    assert re.search(r"direction\s+IN\s*\(\s*'LONG'\s*,\s*'SHORT'\s*\)", _V2EE_BODY)
    assert "NEUTRAL" not in re.search(r"CONSTRAINT ck_v2ee_direction.*?\)", _V2EE_BODY, re.S).group(0)


def test_setup_family_check_exactly_three_families():
    assert re.search(
        r"setup_family\s+IN\s*\(\s*'TREND_PULLBACK'\s*,\s*'COMPRESSION_BREAKOUT'\s*,\s*'CONFIRMED_BREAKOUT'\s*\)",
        _V2EE_BODY)


def test_structural_anchor_is_jsonb_object_check():
    assert re.search(r"structural_anchor\s+JSONB\s+NOT\s+NULL", _V2EE_BODY)
    assert re.search(r"jsonb_typeof\(structural_anchor\)\s*=\s*'object'", _V2EE_BODY)


# ---- CHECK constraints: episode_state, REVERSAL_CANDIDATE excluded -------------
def test_episode_state_check_exactly_six_states():
    m = re.search(r"CONSTRAINT ck_v2ee_episode_state\s+CHECK \(episode_state IN\s*\(([^)]*)\)\)", _V2EE_BODY)
    assert m, "episode_state CHECK not found"
    states = {s.strip().strip("'") for s in m.group(1).split(",")}
    assert states == {"EARLY_SIGNAL", "CONFIRMED", "WEAKENING", "INVALIDATED", "EXPIRED", "COMPLETED"}


def test_reversal_candidate_not_a_legal_episode_state():
    # REVERSAL_CANDIDATE is legitimately *mentioned* in an explanatory banner
    # comment (it is not an episode_state — see events.py/product contract
    # §13.3), so assert it is absent from the CHECK constraint's allowed
    # value list specifically, not from the whole table body/comments.
    m = re.search(r"CONSTRAINT ck_v2ee_episode_state\s+CHECK \(episode_state IN\s*\(([^)]*)\)\)", _V2EE_BODY)
    assert m, "episode_state CHECK not found"
    states = {s.strip().strip("'") for s in m.group(1).split(",")}
    assert "REVERSAL_CANDIDATE" not in states


# ---- CHECK constraints: shared Stage 2 provenance ------------------------------
def test_feature_schema_version_check():
    assert re.search(r"feature_schema_version\s*>\s*0", _V2EE_BODY)


def test_calculation_version_and_config_hash_hex_checks():
    assert re.search(r"calculation_version\s*~\s*'\^\[0-9a-f\]\{16\}\$'", _V2EE_BODY)
    assert re.search(r"config_hash\s*~\s*'\^\[0-9a-f\]\{64\}\$'", _V2EE_BODY)


def test_config_version_and_code_version_nonblank_checks():
    assert re.search(r"length\(btrim\(config_version\)\)\s*>\s*0", _V2EE_BODY)
    assert re.search(r"length\(btrim\(code_version\)\)\s*>\s*0", _V2EE_BODY)


# ---- CHECK constraints: V2-H3 decision-code provenance + deterministic-ID shape --
def test_decision_code_version_column_and_check():
    assert re.search(r"decision_code_version\s+TEXT\s+NOT\s+NULL", _V2EE_BODY)
    assert re.search(r"length\(btrim\(decision_code_version\)\)\s*>\s*0", _V2EE_BODY)


def test_event_id_and_episode_id_hash_format_checks_present():
    # V2-H3: ADDITIONAL to (never a replacement for) the plain nonblank
    # checks tested by test_run_id_event_id_episode_id_nonblank_checks.
    assert re.search(r"event_id\s*~\s*'\^\[0-9a-f\]\{64\}\$'", _V2EE_BODY)
    assert re.search(r"episode_id\s*~\s*'\^\[0-9a-f\]\{64\}\$'", _V2EE_BODY)


def test_original_nonblank_checks_not_removed_by_hash_format_addition():
    # The V2-H3 hash-format CHECKs above must never have REPLACED the
    # original ck_v2ee_event_id/ck_v2ee_episode_id nonblank constraints.
    assert "ck_v2ee_event_id" in _V2EE_BODY
    assert "ck_v2ee_episode_id" in _V2EE_BODY
    assert re.search(r"CONSTRAINT ck_v2ee_event_id\s+CHECK", _V2EE_BODY)
    assert re.search(r"CONSTRAINT ck_v2ee_episode_id\s+CHECK", _V2EE_BODY)


# ---- pre-H3 upgrade path: fresh == upgraded (Blocker 2) ------------------------
# storage/db.py::Database._harden_v2_episode_events_id_constraints is the
# Python-level, idempotent upgrade path making an ALREADY-EXISTING
# (pre-H3) v2_episode_events table converge onto the EXACT SAME two
# hash-format CHECK constraints this file's own inline CREATE TABLE gives
# a fresh database for free. Runtime proof (real PostgreSQL, both a
# genuinely pre-H3 table and a fully-upgraded-except-hash-format legacy-
# row fail-closed vector) lives in
# tests/storage/test_v2_episode_event_id_constraint_upgrade.py; these are
# the structural/source-level counterparts: no Docker/PostgreSQL needed.
from storage.db import Database  # noqa: E402


def test_harden_helper_exists_and_targets_exactly_the_two_hash_format_constraints():
    names = {name for name, _column in Database._V2EE_ID_HASH_FORMAT_CONSTRAINTS}
    assert names == {"ck_v2ee_event_id_hash_format", "ck_v2ee_episode_id_hash_format"}


def test_canonical_init_stage2_schema_calls_the_upgrade_helper():
    # "used by the canonical Stage2/V2 schema initialization path" --
    # init_stage2_schema() is that path (storage/db.py's own docstring: the
    # entry point normal runtime/deployment calls, not a private helper
    # called directly by callers).
    import inspect
    init_src = inspect.getsource(Database.init_stage2_schema)
    assert "_harden_v2_episode_events_id_constraints" in init_src


def test_upgrade_helper_uses_the_exact_same_hash_format_pattern_as_fresh_ddl():
    # fresh == upgraded: extract the ACTUAL quoted regex from the fresh
    # CREATE TABLE (event_id AND episode_id) and the ACTUAL quoted regex
    # literal from the Python helper, unescape the helper's doubled
    # f-string braces, and compare the extracted strings directly. A
    # hardcoded expected pattern would let both sides drift together
    # without the test noticing. Not a generic SQL/Python parser -- two
    # narrow `~ '...'` extractions against already-scoped source text.
    import inspect
    harden_src = inspect.getsource(Database._harden_v2_episode_events_id_constraints)
    # Strip the method docstring so a rendered example in comments cannot
    # satisfy the extraction in place of the actual f-string CHECK.
    harden_body = re.sub(r'""".*?"""', "", harden_src, count=1, flags=re.S)
    fresh_event = re.search(r"event_id\s*~\s*'([^']+)'", _V2EE_BODY)
    fresh_episode = re.search(r"episode_id\s*~\s*'([^']+)'", _V2EE_BODY)
    harden_literal = re.search(r"~\s*'([^']+)'", harden_body)
    assert fresh_event is not None, "fresh DDL event_id regex not found"
    assert fresh_episode is not None, "fresh DDL episode_id regex not found"
    assert harden_literal is not None, "harden-helper regex literal not found"
    helper_pattern = harden_literal.group(1).replace("{{", "{").replace("}}", "}")
    assert fresh_event.group(1) == helper_pattern
    assert fresh_episode.group(1) == helper_pattern
    assert fresh_event.group(1) == fresh_episode.group(1)


def test_upgrade_helper_checks_pg_constraint_before_altering_never_uses_do_block():
    # Idempotency mechanism must be the narrow pg_constraint-inspection
    # helper, never a DO $$ block (which _split_sql_statements' plain
    # semicolon-splitting cannot parse safely -- see storage/db.py's own
    # _split_sql_statements docstring).
    import inspect
    harden_src = inspect.getsource(Database._harden_v2_episode_events_id_constraints)
    harden_body = re.sub(r'""".*?"""', "", harden_src, count=1, flags=re.S)
    assert "pg_constraint" in harden_body
    assert "DO $$" not in harden_src
    assert "ADD CONSTRAINT" in harden_body
    assert "pg_advisory_xact_lock" in harden_body
    assert harden_body.index("pg_advisory_xact_lock") < harden_body.index("pg_constraint")
    assert not re.search(r"except\s+[^\n]*DuplicateObjectError", harden_src)


# ---- CHECK constraints: by-value historical truth ------------------------------
def test_decision_snapshot_and_event_payload_jsonb_object_checks():
    assert re.search(r"decision_snapshot\s+JSONB\s+NOT\s+NULL", _V2EE_BODY)
    assert re.search(r"event_payload\s+JSONB\s+NOT\s+NULL", _V2EE_BODY)
    assert re.search(r"jsonb_typeof\(decision_snapshot\)\s*=\s*'object'", _V2EE_BODY)
    assert re.search(r"jsonb_typeof\(event_payload\)\s*=\s*'object'", _V2EE_BODY)


# ---- table type: NOT a hypertable ------------------------------------------------
def test_not_a_hypertable():
    assert "create_hypertable" not in _V2EE_SECTION
    assert "v2_episode_events" not in re.findall(r"create_hypertable\(\s*'(\w+)'", SQL)


# ---- indexes: only the three useful ones, nothing speculative --------------------
def test_only_three_indexes_present():
    # V2-H3 adds ux_v2ee_episode_decision_boundary (a UNIQUE index enforcing
    # the frozen §2.1a physical-uniqueness invariant) alongside the two
    # original plain indexes -- matches BOTH `CREATE INDEX` and
    # `CREATE UNIQUE INDEX` so an unreviewed fourth index cannot slip in
    # unnoticed either.
    indexes = re.findall(
        r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS (\w+)\s*\n\s*ON v2_episode_events",
        _V2EE_SECTION)
    assert set(indexes) == {
        "ix_v2ee_episode_history", "ix_v2ee_symbol_recent",
        "ux_v2ee_episode_decision_boundary",
    }


def test_episode_decision_boundary_unique_index_shape():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS ux_v2ee_episode_decision_boundary\s*\n"
        r"\s*ON v2_episode_events \(run_kind, run_id, episode_id, decision_boundary\)",
        _V2EE_SECTION)


def test_episode_history_index_shape():
    assert re.search(
        r"ix_v2ee_episode_history\s*\n\s*ON v2_episode_events \(run_kind, run_id, episode_id, decision_boundary ASC\)",
        _V2EE_SECTION)


def test_symbol_recent_index_shape():
    assert re.search(
        r"ix_v2ee_symbol_recent\s*\n\s*ON v2_episode_events \(symbol, decision_boundary DESC\)",
        _V2EE_SECTION)


def test_no_partial_active_episode_index():
    # Active-episode/state-machine read semantics belong to a later PR --
    # no partial index referencing episode_state should exist yet.
    assert "WHERE episode_state" not in _V2EE_SECTION


# ---- no FK / trigger / update / destructive migration ---------------------------
def test_no_fk_references():
    code = _V2EE_SECTION_CODE.upper()
    assert "REFERENCES" not in code
    assert "FOREIGN KEY" not in code


def test_no_trigger_or_update_path():
    code = _V2EE_SECTION_CODE.upper()
    assert "TRIGGER" not in code
    assert "UPDATE" not in code   # insert-once event table -- no DO UPDATE anywhere


def test_no_destructive_migration():
    code = _V2EE_SECTION_CODE.upper()
    assert "DROP TABLE" not in code
    assert "DROP COLUMN" not in code
    assert "RENAME" not in code
    assert "TRUNCATE" not in code
    assert "DELETE FROM" not in code


# ---- schema / model / spec parity ------------------------------------------------
def test_schema_columns_minus_created_at_equal_spec_columns():
    sql_cols = [c for c in _columns(_V2EE_BODY) if c != "created_at"]
    assert tuple(sql_cols) == V2_EPISODE_EVENT_SPEC.columns


def test_spec_columns_equal_model_fields():
    model_fields = tuple(f.name for f in dataclasses.fields(V2EpisodeEvent))
    assert V2_EPISODE_EVENT_SPEC.columns == model_fields


def test_pk_matches_spec():
    assert tuple(_pk(_V2EE_BODY)) == V2_EPISODE_EVENT_SPEC.pk


def test_jsonb_sql_columns_match_spec():
    assert _jsonb_columns(_V2EE_BODY) == set(V2_EPISODE_EVENT_SPEC.jsonb_columns)
    assert _jsonb_columns(_V2EE_BODY) == {"structural_anchor", "decision_snapshot", "event_payload"}
