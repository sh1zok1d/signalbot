"""Structural assertions on the additive v2_version_switch_state DDL in
storage/stage2_schema.sql (no Docker / PostgreSQL). Parsing mirrors
tests/storage/test_v2_episode_event_schema.py.

Real PostgreSQL behavior (atomicity/concurrency/restart) is proven
separately in tests/storage/test_v2_version_switch_readers.py -- this file
only checks the DDL text itself: presence, shape, and that it does not
touch anything outside its own table."""
from __future__ import annotations

import re
from pathlib import Path

SQL = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")

TABLE = "v2_version_switch_state"


def _table_body(table: str) -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", SQL, re.S)
    assert m, f"{table} table not found"
    return m.group(1)


def _strip_sql_comments(text: str) -> str:
    return re.sub(r"--[^\n]*", "", text)


_BODY = _table_body(TABLE)
_SECTION = SQL[SQL.index("V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch durable state"):]
_SECTION_CODE = _strip_sql_comments(_SECTION)


def _columns(body: str) -> list[str]:
    cols = []
    col_re = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s+(TEXT|TIMESTAMPTZ)\b")
    for line in body.splitlines():
        m = col_re.match(line)
        if m:
            cols.append(m.group(1))
    return cols


def _pk(body: str) -> list[str]:
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


# ---- table presence & scope --------------------------------------------------
def test_exactly_one_v2_version_switch_state_table():
    assert len(re.findall(
        r"CREATE TABLE IF NOT EXISTS v2_version_switch_state\b", SQL)) == 1


def test_section_touches_no_other_table():
    code = _SECTION_CODE
    for t in ("v2_episode_events", "klines_1m", "consensus_feature_vectors",
              "percentile_snapshots", "exchange_feature_vectors",
              "forecast_predictions", "forecast_outcomes"):
        assert not re.search(r"(CREATE|ALTER)\s+TABLE[^\n]*\b" + t + r"\b", code), t
    assert "ALTER TABLE" not in code  # CREATE-only, no upgrade path needed.


def test_no_foreign_keys_in_this_table():
    assert "REFERENCES" not in _BODY
    assert "FOREIGN KEY" not in _BODY


# ---- columns / PK -------------------------------------------------------------
_EXPECTED_COLUMNS = [
    "run_kind", "run_id",
    "active_rules_version", "active_calculation_version", "active_decision_code_version",
    "pending_rules_version", "pending_calculation_version", "pending_decision_code_version",
    "phase", "drain_complete_at", "requested_at", "updated_at",
]


def test_columns_match_v2versionswitchstate_shape():
    """Column set mirrors `V2VersionSwitchState`'s own field set exactly
    (run_kind/run_id/active-triple/pending-triple/phase/drain_complete_at/
    requested_at), plus the one DB-owned `updated_at` metadata column that
    has no Python-side field (mirrors v2_episode_events' own `created_at`
    convention)."""
    assert _columns(_BODY) == _EXPECTED_COLUMNS


def test_primary_key_is_scope_execution_stream_only():
    """PK is exactly (run_kind, run_id) -- the execution_stream scope
    (§12.10), never symbol/market_type (neither of which is a column on
    this table at all -- see version_switch.py's module docstring)."""
    assert _pk(_BODY) == ["run_kind", "run_id"]
    assert "symbol" not in _BODY
    assert "market_type" not in _BODY


# ---- CHECK constraints ---------------------------------------------------------
def test_run_kind_check_matches_v2_episode_events_convention():
    assert re.search(r"run_kind IN \('LIVE','REPLAY'\)", _BODY)


def test_phase_check_covers_exactly_the_three_python_phases():
    m = re.search(r"phase IN \(([^)]*)\)", _BODY)
    assert m
    values = {v.strip().strip("'") for v in m.group(1).split(",")}
    assert values == {"NO_PENDING_SWITCH", "DRAINING", "AWAITING_ACTIVATION_READINESS"}


def test_rules_version_format_check_mirrors_v2_episode_events_exactly():
    """Same `common/v2_config.py` RULES_VERSION_RE pattern as
    `v2_episode_events.ck_v2ee_rules_version` -- the DB-side and Python-side
    rules must never silently diverge, for BOTH active_ and pending_."""
    pattern = r"v2-rules-v\(0\|\[1-9\]\[0-9\]\*\)\\\.\(0\|\[1-9\]\[0-9\]\*\)\\\.\(0\|\[1-9\]\[0-9\]\*\)"
    assert re.search(r"active_rules_version ~ '\^" + pattern + r"\$'", _BODY)
    assert re.search(r"pending_rules_version ~ '\^" + pattern + r"\$'", _BODY)
    # And the real v2_episode_events table's own CHECK uses the identical
    # pattern (proves this isn't just internally self-consistent, but
    # actually matches the sibling table).
    v2ee_body = _table_body("v2_episode_events")
    assert re.search(r"rules_version ~ '\^" + pattern + r"\$'", v2ee_body)


def test_calculation_version_format_check_mirrors_v2_episode_events_exactly():
    assert re.search(r"active_calculation_version ~ '\^\[0-9a-f\]\{16\}\$'", _BODY)
    assert re.search(r"pending_calculation_version ~ '\^\[0-9a-f\]\{16\}\$'", _BODY)
    v2ee_body = _table_body("v2_episode_events")
    assert re.search(r"calculation_version ~ '\^\[0-9a-f\]\{16\}\$'", v2ee_body)


def test_active_and_pending_all_or_none_checks_present():
    assert "ck_v2vss_active_all_or_none" in _BODY
    assert "ck_v2vss_pending_all_or_none" in _BODY


def test_phase_shape_checks_present():
    assert "ck_v2vss_no_pending_switch_shape" in _BODY
    assert "ck_v2vss_pending_requires_requested_at" in _BODY
    assert "ck_v2vss_draining_no_drain_complete_at" in _BODY
    assert "ck_v2vss_awaiting_requires_drain_complete_at" in _BODY
    assert "ck_v2vss_drain_complete_at_not_before_requested_at" in _BODY


def test_pending_distinct_from_active_check_present():
    assert "ck_v2vss_pending_distinct_from_active" in _BODY


# ---- amendment round 2: REPLAY-never-mid-switch + pending-requires-active ----
def test_replay_no_pending_switch_check_present_and_shaped_correctly():
    """Mirrors V2VersionSwitchState.__post_init__'s `run_kind not in
    _SWITCH_ELIGIBLE_RUN_KINDS and phase != PHASE_NO_PENDING_SWITCH` check --
    a steady REPLAY row (any active tuple, or none yet) must remain legal;
    only a REPLAY row claiming a pending-switch phase is rejected."""
    assert "ck_v2vss_replay_no_pending_switch" in _BODY
    m = re.search(
        r"CONSTRAINT ck_v2vss_replay_no_pending_switch CHECK \(([^)]*)\)", _BODY)
    assert m
    assert "run_kind = 'LIVE'" in m.group(1)
    assert "phase = 'NO_PENDING_SWITCH'" in m.group(1)


def test_pending_switch_requires_active_check_present_and_shaped_correctly():
    """Mirrors V2VersionSwitchState.__post_init__'s `phase !=
    PHASE_NO_PENDING_SWITCH => active is not None` check -- a pending switch
    always means an OLD active tuple exists; this does not duplicate the
    all-or-none triple check, it only requires one column of that
    already-enforced triple to be present."""
    assert "ck_v2vss_pending_switch_requires_active" in _BODY
    m = re.search(
        r"CONSTRAINT ck_v2vss_pending_switch_requires_active CHECK \(([^)]*)\)", _BODY)
    assert m
    assert "phase = 'NO_PENDING_SWITCH'" in m.group(1)
    assert "active_rules_version IS NOT NULL" in m.group(1)


def test_replay_table_is_not_made_live_only_by_new_checks():
    """The new REPLAY constraint must NOT forbid REPLAY rows outright --
    only mid-switch REPLAY rows. REPLAY must remain a legal run_kind value
    everywhere else in this table's CHECK constraints."""
    assert re.search(r"run_kind IN \('LIVE','REPLAY'\)", _BODY)


def test_updated_at_is_db_owned_metadata_only():
    assert re.search(r"updated_at\s+TIMESTAMPTZ NOT NULL DEFAULT now\(\)", _BODY)
