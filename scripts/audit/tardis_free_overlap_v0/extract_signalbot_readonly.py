"""Owner-executable read-only export of the two overlap days.

Usage, on a host that can read the Signalbot database:

    export SIGNALBOT_DSN='postgresql://...'   # environment only; never commit it
    python -m scripts.audit.tardis_free_overlap_v0.extract_signalbot_readonly \
        --out-dir ./signalbot_gold_20260801_20260901

The process sets the session to read-only, runs the SELECT statements in
extract_signalbot_readonly.sql, writes CSV files, and prints SHA-256 hashes.
It does not print the DSN. It does not export Telegram, user, or chat data.

Requires psycopg (version 3) or psycopg2. Connection failures are reported
with the URI userinfo removed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from pathlib import Path

from .extract_sql import STATEMENTS, assert_sql_is_read_only

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)
_DSN_USERINFO = re.compile(r"://[^@/\s]+@")


def redact(text: str) -> str:
    return _DSN_USERINFO.sub("://REDACTED@", text)


def assert_text_read_only(text: str) -> None:
    if _FORBIDDEN.search(text):
        raise SystemExit("refusing to run SQL that is not a plain SELECT")


def _connect(dsn: str):
    try:
        import psycopg
    except ImportError:
        psycopg = None
    if psycopg is not None:
        conn = psycopg.connect(dsn, autocommit=True)
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        conn.execute("SET default_transaction_read_only = on")
        return conn, "psycopg"
    try:
        import psycopg2
    except ImportError as exc:
        raise SystemExit(
            "install psycopg or psycopg2 on the database host; no write fallback is provided"
        ) from exc
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    cur.execute("SET default_transaction_read_only = on")
    cur.close()
    return conn, "psycopg2"


def _run_select(conn, driver: str, sql: str):
    if driver == "psycopg":
        with conn.transaction():
            row = conn.execute("SHOW transaction_read_only").fetchone()
            if row is None or str(row[0]).lower() != "on":
                raise SystemExit("transaction is not read-only; aborting")
            cur = conn.execute(sql)
            header = [col.name for col in cur.description]
            rows = cur.fetchall()
        return header, rows
    # psycopg2
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute("BEGIN TRANSACTION READ ONLY")
        cur.execute("SHOW transaction_read_only")
        flag = cur.fetchone()
        if flag is None or str(flag[0]).lower() != "on":
            raise SystemExit("transaction is not read-only; aborting")
        cur.execute(sql)
        header = [col.name for col in cur.description]
        rows = cur.fetchall()
        conn.rollback()
        return header, rows
    finally:
        conn.rollback()
        conn.autocommit = True


def _write_csv(path: Path, header: list[str], rows) -> str:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if value is None else value for value in row])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{digest}  {path.name}  rows={len(rows)}")
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Signalbot overlap export")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    dsn = os.environ.get("SIGNALBOT_DSN", "").strip()
    if not dsn:
        print("SIGNALBOT_DSN is not set. Refusing to guess a database.", file=sys.stderr)
        print("WAITING_FOR_SIGNALBOT_EXPORT")
        return 2
    sql_path = Path(__file__).with_name("extract_signalbot_readonly.sql")
    text = sql_path.read_text()
    assert_text_read_only(text)
    statements = assert_sql_is_read_only(text)
    if statements != list(STATEMENTS):
        raise SystemExit("SQL file does not match the packaged statement list")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = (
        "klines_1m.csv",
        "klines_1m_source_counts.csv",
        "open_interest.csv",
        "open_interest_source_counts.csv",
        "exchange_instrument_history.csv",
        "exchange_instruments_current_not_used_as_pit.csv",
    )
    try:
        conn, driver = _connect(dsn)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - connection errors must not leak the DSN
        print(f"database connection failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    try:
        for name, sql in zip(names, statements):
            try:
                header, rows = _run_select(conn, driver, sql)
            except Exception as exc:  # noqa: BLE001
                message = redact(str(exc))
                if "exchange_instrument" in name and (
                    "does not exist" in message or "UndefinedTable" in message
                ):
                    _write_csv(out / name, ["note"], [("table_absent",)])
                    print(f"instrument table absent, wrote empty note for {name}")
                    continue
                print(f"query failed for {name}: {message}", file=sys.stderr)
                return 1
            _write_csv(out / name, header, rows)
    finally:
        conn.close()
    print("EXPORT_COMPLETE")
    print("Gold files contain source=live market rows only. They are not a comparison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
