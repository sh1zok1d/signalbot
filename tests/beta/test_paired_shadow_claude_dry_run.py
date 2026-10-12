"""End-to-end dry-run of Claude's paired_forecast through the shadow store.

Skipped unless beta.rangecast_shadow is importable. The test database is local.
Nothing here writes beta_claims or enables the production hour.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("beta.rangecast_shadow")
pytest.importorskip("beta.rangecast_v2")

from beta import hist_series as hs  # noqa: E402
from beta import rangecast as rc  # noqa: E402
from beta import rangecast_shadow as sh  # noqa: E402
from beta import rangecast_v2 as v2  # noqa: E402
from beta.paired_shadow import (  # noqa: E402
    V1_PROCEDURE_ID, V2_ARTIFACT_MATH_DIGEST, V2_ARTIFACT_SHA256, V2_PARAMS_DIGEST,
    V2_PROCEDURE_DIGEST, V2_PROCEDURE_ID, V2_SPEC_DIGEST, V2_SPEC_ID, execute_hour,
)
from beta.paired_shadow_pg import PgShadowLedger  # noqa: E402
from beta_fakes import TEST_DSN  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc


def _psql(sql: str) -> None:
    completed = subprocess.run(
        ["psql", TEST_DSN, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)


@pytest.fixture(scope="module")
def bars():
    sys.path.insert(0, str(ROOT / "tests" / "beta"))
    from v2_fakes import synthetic_rows
    rows, _ = synthetic_rows(datetime(2026, 5, 1, tzinfo=UTC), 140, seed=9)
    return hs.bars_from_rows(rows)


@pytest.fixture(scope="module")
def snapshot(bars):
    fitted = rc.fit_range_model(bars, events={}, holdout_days=30)
    artifact = sh.load_frozen_model()
    return bars, fitted, artifact


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
@pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed")
def test_claude_forecast_is_stored_once_and_scored(snapshot):
    full, fitted, artifact = snapshot
    index = full.last_complete_index() - 60
    prefix = full.slice(0, index + 1)
    close = prefix.t0 + prefix.n * hs.BAR_MS
    now = datetime.fromtimestamp(close / 1000, tz=UTC) + timedelta(minutes=2)
    snap = sh.Snapshot(
        bars=prefix, price=float(prefix.close[-1]), price_ts=now - timedelta(minutes=1, seconds=30),
        now=now, calendar={"events": []},
    )
    assert v2.shadow_spec_digest() == V2_SPEC_DIGEST
    assert v2.shadow_procedure_digest() == V2_PROCEDURE_DIGEST
    assert v2.spec_digest() == V2_ARTIFACT_MATH_DIGEST
    assert v2.spec_digest() != V2_SPEC_DIGEST
    assert artifact["params_digest"] == V2_PARAMS_DIGEST
    assert artifact["artifact_id"] == "RANGECAST_V2_W_L1_MODEL_V1"
    raw = (ROOT / "docs/research/RANGECAST_V2_W_L1_MODEL_V1.json").read_bytes()
    import hashlib
    assert hashlib.sha256(raw).hexdigest() == V2_ARTIFACT_SHA256
    record = sh.paired_forecast(snap, v1_model=fitted, v2_model=artifact)
    assert record["status"] == "OK"
    assert record["horizons"]["4h"]["paired"] is True
    issue_slot = datetime.fromisoformat(record["as_of"]).astimezone(UTC).replace(
        minute=0, second=0, microsecond=0)
    _psql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    _psql_file(ROOT / "storage/beta_v0_schema.sql")
    approved = os.environ.copy()
    approved["PAIRED_SHADOW_SCHEMA_APPROVED"] = "1"
    applied = subprocess.run(
        [sys.executable, str(ROOT / "scripts/beta/apply_paired_shadow_schema.py"), TEST_DSN],
        capture_output=True, text=True, check=False, env=approved,
    )
    assert applied.returncode == 0, applied.stderr
    assert _count("beta_claims") == 0
    ledger = PgShadowLedger(TEST_DSN)
    first = execute_hour(
        record, ledger, issue_slot=issue_slot, allow_write=True, score=True, bars=full,
        now=datetime.fromisoformat(record["as_of"]).astimezone(UTC) + timedelta(hours=5),
    )
    assert first["written"] is True
    assert first["inserted"] > 0
    assert first["horizons"]["4h"]["status"] == "OK"
    stored = ledger.joined_rows()
    four = [row for row in stored if row["horizon"] == "4h" and row["family"] == "touch"]
    assert {row["procedure_id"] for row in four} == {V1_PROCEDURE_ID, V2_PROCEDURE_ID}
    assert {row["spec_id"] for row in four if row["procedure_id"] == V2_PROCEDURE_ID} == {V2_SPEC_ID}
    assert {row["spec_digest"] for row in four if row["procedure_id"] == V2_PROCEDURE_ID} == {V2_SPEC_DIGEST}
    assert {row["snapshot_id"] for row in four if row["procedure_id"] == V2_PROCEDURE_ID} == {V2_PARAMS_DIGEST}
    assert all(0.0 < row["probability"] < 1.0 for row in four)
    paired = {}
    for row in four:
        paired.setdefault((row["side"], row["distance_pct"]), {})[row["procedure_id"]] = row["probability"]
    assert paired
    assert any(item[V1_PROCEDURE_ID] != item[V2_PROCEDURE_ID] for item in paired.values())
    scored = [item for item in first["scoring"] if item["horizon"] == "4h" and item["family"] == "touch"]
    assert scored
    assert {item["status"] for item in scored} <= {"COMPLETE", "LOW_COVERAGE", "NO_DATA"}
    assert first["settlement"]["launched"] is True
    assert first["settlement"]["stored"] > 0
    clock = datetime.fromisoformat(record["as_of"]).astimezone(UTC) + timedelta(hours=5)
    assert all(row["outcome"] is None for row in stored if row["horizon"] == "24h")
    day = [book for book in first["books"] if book["horizon"] == "24h"]
    assert day and all(book["state"] != "INCOMPLETE_DATA" for book in day)
    assert all(book["n_pending"] > 0 and book["n_unfinished"] == 0 for book in day)
    assert clock > datetime.fromisoformat(record["as_of"]).astimezone(UTC)
    second = execute_hour(record, ledger, issue_slot=issue_slot, allow_write=True)
    assert second["inserted"] == 0
    assert second["kept"] == first["inserted"]
    assert _count("beta_claims") == 0
    stale_snap = sh.Snapshot(
        bars=snap.bars, price=snap.price, price_ts=snap.now - timedelta(minutes=12),
        now=snap.now, calendar=snap.calendar,
    )
    stale = sh.paired_forecast(stale_snap, v1_model=fitted, v2_model=artifact)
    assert stale["status"] == "STALE_DATA"
    gap = execute_hour(stale, ledger, issue_slot=issue_slot + timedelta(hours=1), allow_write=True)
    assert gap["inserted"] == 0
    assert gap["horizons"]["4h"]["status"] == "STALE_DATA"
    assert _count("beta_shadow_issues") == first["inserted"]
    view = _query("SELECT pg_get_viewdef('beta_shadow_export_v1'::regclass)")
    assert "level_up" not in view and "level_down" not in view
    exported = _query("SELECT coalesce(json_agg(row_to_json(beta_shadow_export_v1)), '[]'::json)::text FROM beta_shadow_export_v1")
    assert "level_up" not in exported
    books = {book["procedure_id"] for book in first["books"]}
    assert books == {V1_PROCEDURE_ID, V2_PROCEDURE_ID}
    assert "TOUCH_CHANCE_PROCEDURE_V1" not in books


def _psql_file(path: Path) -> None:
    completed = subprocess.run(
        ["psql", TEST_DSN, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-1", "-f", str(path)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)


def _count(table: str) -> int:
    return int(_query(f"SELECT count(*) FROM {table}"))


def _query(sql: str) -> str:
    completed = subprocess.run(
        ["psql", TEST_DSN, "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()
