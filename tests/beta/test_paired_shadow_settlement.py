"""Writer settlement and a 12-week journal. Test PostgreSQL only (BETA_TEST_DSN). No production DSN."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta.hist_series import BAR_MS
from beta.paired_shadow import V1_SPEC_DIGEST, V2_SPEC_DIGEST
from beta.paired_shadow_pg import PgShadowLedger
from beta_fakes import TEST_DSN

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc


def _sibling(name: str):
    """A database beside BETA_TEST_DSN's: the same server and role, so CI's PostgreSQL service runs these too."""
    if not TEST_DSN:
        return None
    from urllib.parse import urlsplit
    parts = urlsplit(TEST_DSN)
    return f"{parts.scheme}://{parts.netloc}/{name}" + (f"?{parts.query}" if parts.query else "")


WRITER_DSN = _sibling("signalbot_shadow_writer")
VOLUME_DSN = _sibling("signalbot_shadow_volume")
NEEDS_TEST_DB = pytest.mark.skipif(not TEST_DSN or shutil.which("psql") is None,
                                   reason="BETA_TEST_DSN not set (local PostgreSQL) or psql missing")
HOURS = 12 * 7 * 24
TOUCH = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)
NEITHER = (0.5, 1.0, 2.0, 3.0)
PRICE = 100.0
RULE_DIGEST = "ab" * 32


def _psql(dsn: str, sql: str, check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["psql", dsn, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-t", "-A"],
        input=sql, capture_output=True, text=True, check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed


def _ensure_db(name: str, dsn: str) -> None:
    probe = subprocess.run(
        ["psql", dsn, "-X", "-q", "-c", "SELECT 1"],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode != 0:
        created = _psql(TEST_DSN, f"CREATE DATABASE {name}", check=False)
        if created.returncode != 0 and "already exists" not in (created.stderr or ""):
            raise AssertionError(created.stderr or created.stdout)
    _psql(dsn, "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")


def _apply(dsn: str) -> None:
    approved = os.environ.copy()
    approved["PAIRED_SHADOW_SCHEMA_APPROVED"] = "1"
    approved["PAIRED_SHADOW_DSN"] = dsn
    applied = subprocess.run(
        ["python3", str(ROOT / "scripts/beta/apply_paired_shadow_schema.py")],
        capture_output=True, text=True, check=False, env=approved,
    )
    assert applied.returncode == 0, applied.stderr
    assert dsn not in applied.stdout
    assert dsn not in applied.stderr


def _record(as_of: datetime, *, price: float = 65432.1, touch_p: float = 0.20,
            touch_p_v2: float = 0.80) -> dict:
    touch = [{"side": 1, "distance_pct": 1.25, "status": "OK", "probability": touch_p},
             {"side": -1, "distance_pct": 1.25, "status": "OK", "probability": touch_p}]
    neither = [{"up_pct": 0.5, "down_pct": 1.0, "status": "OK", "probability": 0.70}]
    touch_v2 = [{**item, "probability": touch_p_v2} for item in touch]
    neither_v2 = [{**item, "probability": 0.30} for item in neither]

    def block():
        return {
            "status": "OK",
            "v1": {"procedure_id": "TOUCH_CHANCE_PROCEDURE_V1", "stats_digest": "a" * 64, "status": "OK",
                   "touch": touch, "neither": neither},
            "v2": {"procedure_id": "TOUCH_CHANCE_PROCEDURE_RCV2_W_L1", "spec_id": "RANGECAST_V2_W_L1",
                   "spec_digest": V2_SPEC_DIGEST, "params_digest": "b" * 64, "status": "OK",
                   "touch": touch_v2, "neither": neither_v2},
        }

    return {
        "schema": "RANGECAST_SHADOW_RECORD_V1",
        "status": "OK",
        "as_of": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "price": price,
        "horizons": {"1h": block(), "24h": block()},
    }


def _bars(as_of: datetime, *, price: float = 65432.1, high_ratio: float = 1.005,
          low_ratio: float = 0.995) -> list:
    start = int(as_of.timestamp() * 1000)
    rows = []
    for index in range(48):
        rows.append({
            "open_time_ms": start + index * BAR_MS,
            "open": price, "high": price * high_ratio, "low": price * low_ratio, "close": price,
            "volume": 1, "quote_volume": 1, "taker_buy_quote": 1,
        })
    return rows


def _run_writer(record_path: Path, *extra: str) -> dict:
    approved = os.environ.copy()
    approved["PAIRED_SHADOW_HOUR_APPROVED"] = "1"
    approved["PAIRED_SHADOW_DSN"] = WRITER_DSN
    command = ["python3", str(ROOT / "scripts/beta/run_paired_shadow_hour.py"), "--write",
               str(record_path), *extra]
    assert WRITER_DSN not in command
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, env=approved,
    )
    assert completed.returncode == 0, completed.stderr
    assert WRITER_DSN not in completed.stdout
    assert WRITER_DSN not in completed.stderr
    assert "postgresql" not in completed.stdout
    return json.loads(completed.stdout)


@NEEDS_TEST_DB
def test_writer_launches_settlement_for_elapsed_anchors(tmp_path):
    _ensure_db("signalbot_shadow_writer", WRITER_DSN)
    _apply(WRITER_DSN)
    as_of = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    record_path = tmp_path / "record.json"
    bars_path = tmp_path / "bars.json"
    record_path.write_text(json.dumps(_record(as_of)), encoding="utf-8")
    bars_path.write_text(json.dumps({"bars": _bars(as_of)}), encoding="utf-8")
    without_bars = _run_writer(record_path)
    assert without_bars["written"] is True
    assert without_bars["inserted"] > 0
    assert without_bars["settlement"]["launched"] is True
    assert without_bars["settlement"]["status"] == "NO_BARS"
    assert without_bars["settlement"]["stored"] == 0
    assert _psql(WRITER_DSN, "SELECT count(*) FROM beta_shadow_outcomes").stdout.strip() == "0"
    with_bars = _run_writer(record_path, "--bars", str(bars_path), "--settle-limit", "50")
    assert with_bars["inserted"] == 0
    assert with_bars["kept"] == without_bars["inserted"]
    assert with_bars["settlement"]["launched"] is True
    assert with_bars["settlement"]["status"] == "OK"
    assert with_bars["settlement"]["stored"] > 0
    outcomes = _psql(WRITER_DSN, """
        SELECT a.horizon || ':' || count(*)::text
        FROM beta_shadow_outcomes o
        JOIN beta_shadow_anchors a USING (anchor_pk)
        GROUP BY a.horizon ORDER BY a.horizon
    """).stdout.strip().splitlines()
    assert outcomes == [f"1h:{with_bars['settlement']['stored']}"]
    again = _run_writer(record_path, "--bars", str(bars_path), "--settle-limit", "50")
    assert again["settlement"]["stored"] == 0
    assert again["settlement"]["selected"] == 0
    missing_claims = _psql(WRITER_DSN, "SELECT to_regclass('public.beta_claims')").stdout.strip()
    assert missing_claims in ("", "None", "null")


@NEEDS_TEST_DB
def test_a_later_live_minute_keeps_the_first_pair_and_settles_it(tmp_path):
    """Seven minutes later the price and bars differ. The first barrier is what gets scored."""
    _ensure_db("signalbot_shadow_writer", WRITER_DSN)
    _apply(WRITER_DSN)
    slot = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    first_as_of = slot
    second_as_of = slot + timedelta(minutes=7)
    first_price = 65432.1
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    bars_path = tmp_path / "bars.json"
    first_path.write_text(json.dumps(_record(first_as_of, price=first_price)), encoding="utf-8")
    second_path.write_text(json.dumps(_record(
        second_as_of, price=first_price * 1.08, touch_p=0.11, touch_p_v2=0.15,
    )), encoding="utf-8")
    # 2% above the first price crosses its 1.25% barrier and not the barrier of the later price.
    bars_path.write_text(json.dumps({"bars": _bars(first_as_of, price=first_price, high_ratio=1.02)}),
                         encoding="utf-8")
    opened = _run_writer(first_path)
    assert opened["inserted"] > 0
    assert opened["settlement"]["status"] == "NO_BARS"
    replay = _run_writer(second_path, "--bars", str(bars_path), "--settle-limit", "50")
    assert replay["inserted"] == 0
    assert replay["kept"] == opened["inserted"]
    assert replay["settlement"]["launched"] is True
    assert replay["settlement"]["status"] == "OK"
    assert replay["settlement"]["stored"] > 0
    row = _psql(WRITER_DSN, """
        SELECT to_char(a.as_of AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
               a.level_up::text,
               i.probability::text,
               o.outcome::text
        FROM beta_shadow_anchors a
        JOIN beta_shadow_issues i ON i.anchor_pk = a.anchor_pk AND i.procedure_id = 'RANGECAST_V1'
        JOIN LATERAL (
            SELECT outcome FROM beta_shadow_outcomes
            WHERE anchor_pk = a.anchor_pk
            ORDER BY revision DESC LIMIT 1
        ) o ON true
        WHERE a.family = 'touch' AND a.side = 1 AND a.horizon = '1h'
    """).stdout.strip()
    as_of_text, level_text, probability_text, outcome_text = row.split("|")
    assert as_of_text == first_as_of.strftime("%Y-%m-%d %H:%M:%S")
    assert float(level_text) == pytest.approx(first_price * 1.0125)
    assert float(probability_text) == pytest.approx(0.20)
    assert outcome_text == "1"


def _geometries() -> str:
    rows = []
    ordinal = 0
    for distance in TOUCH:
        for side in (1, -1):
            level_up = "NULL" if side < 0 else format(PRICE * (1 + distance / 100), ".8f")
            level_down = "NULL" if side > 0 else format(PRICE * (1 - distance / 100), ".8f")
            rows.append(
                f"('touch', {side}::smallint, {distance}::float8, NULL::float8, NULL::float8, "
                f"{level_up}::float8, {level_down}::float8, 'TOUCH_V1', {ordinal})"
            )
            ordinal += 1
    for up in NEITHER:
        for down in NEITHER:
            rows.append(
                f"('neither', NULL::smallint, NULL::float8, {up}::float8, {down}::float8, "
                f"{PRICE * (1 + up / 100):.8f}::float8, {PRICE * (1 - down / 100):.8f}::float8, "
                f"'NEITHER_V1', {ordinal})"
            )
            ordinal += 1
    return ",\n".join(rows)


@NEEDS_TEST_DB
def test_twelve_week_journal_settles_in_bounded_batches():
    _ensure_db("signalbot_shadow_volume", VOLUME_DSN)
    _apply(VOLUME_DSN)
    started = time.perf_counter()
    _psql(VOLUME_DSN, f"""
        INSERT INTO beta_shadow_anchors (
            anchor_key, symbol, family, horizon, issue_slot, as_of, horizon_end, side,
            distance_pct, distance_up_pct, distance_down_pct, level_up, level_down,
            eval_rule_id, eval_rule_digest)
        SELECT 'V|' || h.horizon || '|' || i || '|' || g.ordinal,
               'BTCUSDT', g.family, h.horizon, slot.ts, slot.ts, slot.ts + h.span,
               g.side, g.distance_pct, g.distance_up_pct, g.distance_down_pct,
               g.level_up, g.level_down, g.rule, '{RULE_DIGEST}'
        FROM generate_series(0, {HOURS - 1}) AS i
        CROSS JOIN LATERAL (
            SELECT timestamptz '2024-01-01 00:00:00+00' + i * interval '1 hour' AS ts
        ) AS slot
        CROSS JOIN (VALUES
            ('1h', interval '1 hour'),
            ('4h', interval '4 hours'),
            ('24h', interval '24 hours')
        ) AS h(horizon, span)
        CROSS JOIN (VALUES
            {_geometries()}
        ) AS g(family, side, distance_pct, distance_up_pct, distance_down_pct,
               level_up, level_down, rule, ordinal);
        INSERT INTO beta_shadow_issues (
            anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
        SELECT a.anchor_pk, p.procedure_id, p.spec_id, p.spec_digest, 'snap-volume', 0.40, a.as_of
        FROM beta_shadow_anchors a
        CROSS JOIN (VALUES
            ('RANGECAST_V1', 'RANGECAST_V1', '{V1_SPEC_DIGEST}'),
            ('RANGECAST_V2', 'W_L1', '{V2_SPEC_DIGEST}')
        ) AS p(procedure_id, spec_id, spec_digest);
    """)
    loaded = time.perf_counter() - started
    anchors = int(_psql(VOLUME_DSN, "SELECT count(*) FROM beta_shadow_anchors").stdout.strip())
    issues = int(_psql(VOLUME_DSN, "SELECT count(*) FROM beta_shadow_issues").stdout.strip())
    per_hour = (len(TOUCH) * 2 + len(NEITHER) * len(NEITHER)) * 3
    assert anchors == HOURS * per_hour
    assert issues == anchors * 2
    now = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=HOURS)
    open_horizons = int(_psql(VOLUME_DSN, f"""
        SELECT count(*) FROM beta_shadow_anchors
        WHERE horizon_end > timestamptz '2024-01-01 00:00:00+00' + interval '{HOURS} hours'
    """).stdout.strip())
    assert open_horizons > 0
    ledger = PgShadowLedger(VOLUME_DSN)

    def _refuse_full_journal():
        raise AssertionError("settlement loaded the full journal")

    ledger.joined_rows = _refuse_full_journal
    query_started = time.perf_counter()
    page = ledger.due_unscored(now, limit=500)
    query_s = time.perf_counter() - query_started
    assert len(page) == 500
    assert all(row["horizon_end"] <= now for row in page)
    assert query_s < 5
    from beta.hist_series import Bars
    import numpy as np
    bars = Bars(
        t0=0, open=np.ones(4), high=np.ones(4), low=np.ones(4), close=np.ones(4),
        volume=np.ones(4), quote=np.ones(4), taker_buy_quote=np.ones(4), oi=np.ones(4),
    )
    from beta.paired_shadow import settle_due
    first = settle_due(ledger, bars, now=now, limit=200, allow_write=True, max_batches=1)
    assert first["selected"] == 200
    assert first["stored"] == 200
    second = settle_due(ledger, bars, now=now, limit=200, allow_write=True, max_batches=1)
    assert second["stored"] == 200
    assert {item["anchor_key"] for item in first["reports"]}.isdisjoint(
        {item["anchor_key"] for item in second["reports"]}
    )
    totals = _psql(VOLUME_DSN, """
        SELECT count(*)::text || ' ' || count(DISTINCT anchor_pk)::text || ' ' || max(revision)::text
        FROM beta_shadow_outcomes
    """).stdout.strip().split()
    assert totals == ["400", "400", "1"]
    settled_open = int(_psql(VOLUME_DSN, f"""
        SELECT count(*) FROM beta_shadow_outcomes o
        JOIN beta_shadow_anchors a USING (anchor_pk)
        WHERE a.horizon_end > timestamptz '2024-01-01 00:00:00+00' + interval '{HOURS} hours'
    """).stdout.strip())
    assert settled_open == 0
    third = settle_due(ledger, bars, now=now, limit=200, allow_write=True, max_batches=1)
    assert third["stored"] == 200
    replay = settle_due(ledger, bars, now=now, limit=200, allow_write=True, max_batches=1)
    assert replay["stored"] == 200
    still = _psql(VOLUME_DSN, """
        SELECT count(*)::text || ' ' || max(revision)::text FROM beta_shadow_outcomes
    """).stdout.strip()
    assert still == "800 1"
    log = Path("/opt/cursor/artifacts/paired_shadow_volume.log")
    log.write_text(
        f"anchors={anchors} issues={issues} load_s={loaded:.2f} due_query_s={query_s:.3f} "
        f"open_horizons={open_horizons} outcomes=800\n",
        encoding="utf-8",
    )
