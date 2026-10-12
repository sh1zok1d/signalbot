"""Read-only calibration journal export: schema, SQL, JSONL, adapter, monitor V2.

The executable chain needs PostgreSQL ($BETA_TEST_DSN) and psql. The column and
wiring checks run without a database.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta import claims as cj
from beta.calibration_monitor import (
    STATE_FAULT, STATE_INSUFFICIENT, evaluate, observations_from_claim_rows,
)
from beta_fakes import TEST_DSN
from scripts.beta.replay_calibration_monitor_v2 import (
    FORBIDDEN_KEYS, READ_ONLY_EXPORT_SQL, load_jsonl,
)

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "scripts/beta/export_calibration_journal_v2.sql"
SHELL_PATH = ROOT / "scripts/beta/export_calibration_journal_v2.sh"
SCHEMA_PATH = ROOT / "storage/beta_v0_schema.sql"
UTC = timezone.utc
AS_OF = datetime(2024, 1, 1, 0, 1, tzinfo=UTC)
STATS = "a" * 64
LEAKS = (
    "secret-subject-marker",
    "65432.1",
    "66000.5",
    "64000.25",
    "65555.5",
    "66111.5",
    "64111.25",
    "65666.5",
    "l2-must-not-export",
    "88888.25",
    "67000.5",
    "63000.25",
    "unresolved-price-77111",
    "chat-id-9001",
    "2024-01-01T00:05:00Z",
)


def _executable_sql(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return " ".join(" ".join(lines).lower().split())


def _table_columns(schema: str, table: str) -> set:
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", schema, re.S)
    assert match, table
    columns = set()
    for line in match.group(1).splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped:
            continue
        first = stripped.split()[0]
        if first in {"CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN"}:
            continue
        columns.add(first)
    return columns


def _qualified(sql: str, alias: str) -> set:
    return set(re.findall(rf"\b{alias}\.([a-z_]+)", _executable_sql(sql)))


def test_export_sql_matches_the_claim_schema_and_keeps_the_scoring_fields():
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    sql = SQL_PATH.read_text(encoding="utf-8")
    assert sql.strip() == READ_ONLY_EXPORT_SQL
    folded = _executable_sql(sql)
    assert folded.startswith("select ")
    for verb in ("insert ", "update ", "delete ", "truncate ", "alter ", "drop ", "grant "):
        assert verb not in folded
    for banned in ("subject", "subject_key", "'high'", "'low'", "'close'", "price", "realized -"):
        assert banned not in folded
    assert _qualified(sql, "c") <= _table_columns(schema, "beta_claims")
    assert _qualified(sql, "o") <= _table_columns(schema, "beta_claim_outcomes")
    assert _qualified(sql, "x") <= _table_columns(schema, "beta_claim_outcomes")
    for required in ("coverage", "eval_rule_digest", "eval_rule_id", "outcome_revision"):
        assert required in folded
    assert "order by x.revision desc" in folded
    assert "limit 1" in folded
    claims = _table_columns(schema, "beta_claims")
    outcomes = _table_columns(schema, "beta_claim_outcomes")
    assert {"claim_class", "as_of", "horizon_end", "numbers", "stats_digest", "stats_pk",
            "eval_rule_digest", "eval_rule_id", "rule_version", "claim_pk"} <= claims
    assert {"claim_pk", "revision", "status", "realized"} <= outcomes


def test_export_shell_is_read_only_and_does_not_name_the_password():
    shell = SHELL_PATH.read_text(encoding="utf-8")
    assert shell.count("default_transaction_read_only=on") >= 2
    assert "docker exec -i -e PGOPTIONS=" in shell
    assert "POSTGRES_PASSWORD" not in shell
    assert "GRANT" not in shell
    assert "census" not in shell.lower()
    for line in shell.splitlines():
        if "echo" in line or "printf" in line:
            assert "CALIBRATION_EXPORT_DSN" not in line
            assert "PASSWORD" not in line
    match = re.search(r"FORBIDDEN = \{([^}]+)\}", shell)
    assert match
    assert set(re.findall(r'"([^"]+)"', match.group(1))) == set(FORBIDDEN_KEYS)


def test_monitor_is_not_called_from_health_notifier_or_wording():
    beta = ROOT / "beta"
    for path in sorted(beta.glob("*.py")):
        if path.name in ("calibration_monitor.py", "paired_shadow.py"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "calibration_monitor" not in text
        assert "touch_cal_monitor_v2" not in text


def _psql(*args, stdin=None, env=None, check=True):
    proc = subprocess.run(
        ["psql", TEST_DSN, "-X", "-v", "ON_ERROR_STOP=1", *args],
        input=stdin, capture_output=True, text=True, env=env, check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc


def _dollar(text: str) -> str:
    tag = "cal"
    while f"${tag}$" in text:
        tag += "x"
    return f"${tag}${text}${tag}$"


def _lit(value):
    if value is None:
        return "NULL"
    if isinstance(value, datetime):
        stamp = value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")
        return f"timestamptz {_dollar(stamp)}"
    if isinstance(value, (dict, list)):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return _dollar(payload) + "::jsonb"
    return _dollar(str(value))


_CLAIM_COLUMNS = (
    "claim_class", "level", "issued_at", "issue_slot", "as_of", "context_pk", "stats_pk",
    "stats_digest", "subject", "subject_key", "numbers", "rule_version", "template_id",
    "template_digest", "eval_rule_id", "eval_rule", "eval_rule_digest", "horizon_end",
    "eligible_reason", "claim_digest",
)


def _insert_claim(row: dict) -> int:
    columns = ", ".join(_CLAIM_COLUMNS)
    values = ", ".join(_lit(row.get(column)) for column in _CLAIM_COLUMNS)
    out = _psql("-qAt", "-c", f"INSERT INTO beta_claims ({columns}) VALUES ({values}) RETURNING claim_pk")
    return int(out.stdout.splitlines()[0].strip())


def _insert_outcome(claim_pk: int, digest: str, *, revision: int, status: str, realized: dict,
                    supersedes: int | None, note: str | None, outcome_digest: str) -> int:
    note_sql = "NULL" if note is None else _dollar(note)
    sup_sql = "NULL" if supersedes is None else str(supersedes)
    when = AS_OF + timedelta(hours=5, minutes=revision)
    sql = f"""
        INSERT INTO beta_claim_outcomes (
            claim_pk, eval_rule_digest, revision, supersedes_outcome_pk, status, realized,
            computed_at, outcome_digest, correction_note)
        VALUES (
            {claim_pk}, {_dollar(digest)}, {revision}, {sup_sql}, {_dollar(status)},
            {_lit(realized)}, timestamptz {_dollar(when.strftime('%Y-%m-%d %H:%M:%S+00'))},
            {_dollar(outcome_digest)}, {note_sql})
        RETURNING outcome_pk
    """
    return int(_psql("-qAt", "-c", sql).stdout.splitlines()[0].strip())


def _seed() -> dict:
    _psql("-c", "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    _psql("-1", "-f", str(SCHEMA_PATH))
    touch = cj.claim_row(
        "L3_DISTANCE_TOUCH_4H", issued_at=AS_OF, issue_slot=AS_OF.replace(minute=0), as_of=AS_OF,
        subject={"side": 1, "level": 65432.1, "price": 65432.1, "chat_id": "chat-id-9001",
                 "note": "secret-subject-marker"},
        subject_key="secret-subject-marker", numbers={"probability": 0.40},
        rule_version="touch-rule-v1", eligible_reason="GRID", horizon_ms=14_400_000,
        stats_digest=STATS,
    )
    touch_pk = _insert_claim(touch)
    first = _insert_outcome(
        touch_pk, touch["eval_rule_digest"], revision=1, status="COMPLETE",
        realized={"touched": True, "coverage": 0.2, "high": 66000.5, "low": 64000.25,
                  "close": 65555.5, "first_touch": "2024-01-01T00:05:00Z"},
        supersedes=None, note=None, outcome_digest="b" * 64,
    )
    _insert_outcome(
        touch_pk, touch["eval_rule_digest"], revision=2, status="COMPLETE",
        realized={"touched": False, "coverage": 0.97, "high": 66111.5, "low": 64111.25,
                  "close": 65666.5},
        supersedes=first, note="scored on the full window", outcome_digest="c" * 64,
    )
    neither = cj.claim_row(
        "L3_NEITHER_4H", issued_at=AS_OF, issue_slot=AS_OF.replace(minute=0), as_of=AS_OF,
        subject={"level_up": 67000.5, "level_down": 63000.25, "price": 65432.1},
        subject_key="neither-pair", numbers={"probability": 0.55},
        rule_version="neither-rule-v1", eligible_reason="GRID", horizon_ms=14_400_000,
        stats_digest=STATS,
    )
    neither_pk = _insert_claim(neither)
    _insert_outcome(
        neither_pk, neither["eval_rule_digest"], revision=1, status="COMPLETE",
        realized={"neither": True, "coverage": 1.0, "high": 67000.5, "low": 63000.25},
        supersedes=None, note=None, outcome_digest="d" * 64,
    )
    hidden = cj.claim_row(
        "L2_DH3_P1_RANGE_4H", issued_at=AS_OF, issue_slot=AS_OF.replace(minute=0), as_of=AS_OF,
        subject={"price": 88888.25, "note": "l2-must-not-export"},
        subject_key="l2-must-not-export", numbers={"probability": 0.10},
        rule_version="l2-rule", eligible_reason="GRID", horizon_ms=14_400_000,
    )
    _insert_claim(hidden)
    pending = cj.claim_row(
        "L3_DISTANCE_TOUCH_1H", issued_at=AS_OF, issue_slot=AS_OF.replace(minute=0), as_of=AS_OF,
        subject={"side": 1, "level": 77111.0, "price": 77111.0, "note": "unresolved-price-77111"},
        subject_key="unresolved-price-77111", numbers={"probability": 0.25},
        rule_version="touch-rule-v1", eligible_reason="GRID", horizon_ms=3_600_000,
        stats_digest=STATS,
    )
    _insert_claim(pending)
    return {"touch": touch, "neither": neither}


def _assert_export(text: str, seeded: dict) -> None:
    for leak in LEAKS:
        assert leak not in text
    rows = load_jsonl(text)
    assert [row["claim_class"] for row in rows] == [
        "L3_DISTANCE_TOUCH_1H", "L3_DISTANCE_TOUCH_4H", "L3_NEITHER_4H",
    ]
    pending, touch, neither = rows
    assert "status" not in pending
    assert "outcome_revision" not in pending
    assert pending["realized"] == {}
    assert touch["outcome_revision"] == 2
    assert touch["status"] == "COMPLETE"
    assert touch["realized"] == {"touched": False, "coverage": 0.97}
    assert set(touch["realized"]) <= {"touched", "neither", "coverage"}
    assert touch["eval_rule_digest"] == seeded["touch"]["eval_rule_digest"]
    assert touch["eval_rule_id"] == "TOUCH_V1"
    assert touch["probability"] == pytest.approx(0.40)
    assert touch["as_of"] == "2024-01-01T00:01:00Z"
    assert touch["horizon_end"] == "2024-01-01T04:01:00Z"
    assert touch["stats_digest"] == STATS
    assert neither["realized"]["neither"] is True
    assert neither["realized"]["coverage"] == pytest.approx(1.0)
    assert neither["eval_rule_id"] == "NEITHER_V1"
    assert neither["eval_rule_digest"] == seeded["neither"]["eval_rule_digest"]
    observations = observations_from_claim_rows(rows)
    by_key = {(item["family"], item["horizon"]): item for item in observations}
    assert by_key[("touch", "4h")]["coverage"] == pytest.approx(0.97)
    assert by_key[("touch", "4h")]["outcome"] is False
    assert by_key[("touch", "1h")]["status"] == "MISSING"
    report = evaluate(observations)
    books = {(book["family"], book["horizon"]): book for book in report["books"]}
    assert books[("touch", "4h")]["state"] == STATE_INSUFFICIENT
    assert books[("touch", "4h")]["state"] != STATE_FAULT
    assert books[("neither", "4h")]["state"] == STATE_INSUFFICIENT
    assert books[("touch", "1h")]["n_unfinished"] == 1
    assert books[("touch", "1h")]["state"] != STATE_FAULT
    assert report["shadow_component"] == "touch_cal_monitor_v2"


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
@pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed")
def test_sql_jsonl_adapter_monitor_chain(tmp_path):
    seeded = _seed()
    exported = _psql(
        "-q", "-t", "-A", "-f", str(SQL_PATH),
        env={**os.environ, "PGOPTIONS": "-c default_transaction_read_only=on"},
    )
    _assert_export(exported.stdout, seeded)
    before = _psql("-At", "-c", "SELECT count(*) FROM beta_claims").stdout.strip()
    denied = _psql(
        "-c", "INSERT INTO beta_claims (claim_class) VALUES ('L3_NOPE');",
        env={**os.environ, "PGOPTIONS": "-c default_transaction_read_only=on"},
        check=False,
    )
    assert denied.returncode != 0
    assert "read-only" in (denied.stderr + denied.stdout).lower()
    assert _psql("-At", "-c", "SELECT count(*) FROM beta_claims").stdout.strip() == before

    out = tmp_path / "from-dsn.jsonl"
    dsn_run = subprocess.run(
        ["bash", str(SHELL_PATH), str(out)],
        env={**os.environ, "CALIBRATION_EXPORT_DSN": TEST_DSN},
        capture_output=True, text=True, check=False,
    )
    assert dsn_run.returncode == 0, dsn_run.stderr
    assert "rows=3 " in dsn_run.stdout
    assert f"path={out}" in dsn_run.stdout
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    body = out.read_text(encoding="utf-8")
    assert hashlib.sha256(body.encode()).hexdigest() in dsn_run.stdout
    _assert_export(body, seeded)

    secret = "super-secret-do-not-print"
    env_file = tmp_path / "signalbot.env"
    env_file.write_text(
        f"POSTGRES_PASSWORD={secret}\nPOSTGRES_USER=btcbot\n"
        "POSTGRES_DB=signalbot_calibration_export\nBTCBOT_PG_CONTAINER=fake_timescaledb\n",
        encoding="utf-8",
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker-args.txt"
    fake = bin_dir / "docker"
    fake.write_text(
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" >>\"$FAKE_DOCKER_LOG\"\n"
        "pgoptions=\"\"\n"
        "args=(\"$@\")\n"
        "i=0\n"
        "while [ \"$i\" -lt \"${#args[@]}\" ]; do\n"
        "  if [ \"${args[$i]}\" = \"-e\" ]; then\n"
        "    i=$((i + 1))\n"
        "    case \"${args[$i]}\" in\n"
        "      PGOPTIONS=*) pgoptions=\"${args[$i]#PGOPTIONS=}\" ;;\n"
        "    esac\n"
        "  fi\n"
        "  i=$((i + 1))\n"
        "done\n"
        "if [ -n \"$pgoptions\" ]; then export PGOPTIONS=\"$pgoptions\"; fi\n"
        "exec psql \"$FAKE_DOCKER_DSN\" -X -q -t -A -v ON_ERROR_STOP=1 -f -\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    docker_out = tmp_path / "from-docker.jsonl"
    docker_env = os.environ.copy()
    docker_env.pop("CALIBRATION_EXPORT_DSN", None)
    docker_env.update({
        "SIGNALBOT_ENV": str(env_file),
        "PATH": f"{bin_dir}{os.pathsep}{docker_env.get('PATH', '')}",
        "FAKE_DOCKER_DSN": TEST_DSN,
        "FAKE_DOCKER_LOG": str(log),
    })
    docker_run = subprocess.run(
        ["bash", str(SHELL_PATH), str(docker_out)],
        env=docker_env, capture_output=True, text=True, check=False,
    )
    assert docker_run.returncode == 0, docker_run.stderr
    combined = docker_run.stdout + docker_run.stderr + log.read_text(encoding="utf-8")
    assert secret not in combined
    assert "POSTGRES_PASSWORD" not in combined
    assert "container=fake_timescaledb db=signalbot_calibration_export user=btcbot" in docker_run.stdout
    assert "default_transaction_read_only=on" in log.read_text(encoding="utf-8")
    assert docker_out.read_bytes() == out.read_bytes()
    _assert_export(docker_out.read_text(encoding="utf-8"), seeded)
