"""`liquidations.mapping_version` on real PostgreSQL (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1, R2):
storage/schema.sql adds it to an existing table without touching old rows (NULL = written under the
old mapping), and every row the collector writes from now on carries the fixed revision. The table
comes from schema.sql's own DDL, minus `create_hypertable` (no TimescaleDB needed), in a throwaway
schema. DSN: $LIQUIDATIONS_TEST_DSN, else $BETA_TEST_DSN; skipped without either."""
import asyncio
import os
import re
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from data_ingestion.base_client import ClientCallbacks, Liquidation
from storage.db import Database

DSN = os.environ.get("LIQUIDATIONS_TEST_DSN") or os.environ.get("BETA_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="no LIQUIDATIONS_TEST_DSN / BETA_TEST_DSN (local PostgreSQL)")
SCHEMA_SQL = (Path(__file__).resolve().parents[2] / "storage" / "schema.sql").read_text()


def _ddl():
    create = re.search(r"CREATE TABLE IF NOT EXISTS liquidations \(.*?\n\);", SCHEMA_SQL, re.S).group(0)
    alters = re.findall(r"^ALTER TABLE liquidations [^;]*;", SCHEMA_SQL, re.M)
    return create, alters


def _scoped(dsn, schema):
    p = urllib.parse.urlsplit(dsn)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True) + [("options", f"-csearch_path={schema}")]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), p.fragment))


def test_old_rows_keep_null_and_new_collector_rows_carry_the_fixed_mapping():
    from data_ingestion.manager import IngestionManager
    create, alters = _ddl()
    assert alters, "storage/schema.sql must add liquidations.mapping_version"

    async def body():
        schema = "liqmap_" + uuid.uuid4().hex[:12]
        admin = await asyncpg.connect(DSN)
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        db = Database(_scoped(DSN, schema))
        await db.connect()
        try:
            at = datetime(2026, 10, 1, tzinfo=timezone.utc)
            async with db.pool.acquire() as c:
                await c.execute(create)
                # a row written under the old mapping, before the column exists
                await c.execute("""INSERT INTO liquidations (exchange, symbol, ts, side, price, qty, notional,
                                       is_snapshot_feed) VALUES ('bybit','BTCUSDT',$1,'short',60000,1,60000,false)""", at)
                for a in alters:                  # schema.sql re-applied by the restarted collector
                    await c.execute(a)
                    await c.execute(a)            # idempotent
            # the collector's own path: client -> manager callback -> Database.insert_liquidations
            mgr = IngestionManager.__new__(IngestionManager)
            mgr.db, mgr.symbol, mgr.bar_builders = db, "BTCUSDT", {}
            cb: ClientCallbacks = mgr._make_callbacks("bybit")
            await cb.on_liquidation(Liquidation(exchange="bybit", symbol="BTCUSDT", ts=at.timestamp() + 60,
                                                side="long", price=59000.0, qty=0.5, notional=29500.0))
            await db.insert_liquidations([("okx", "BTCUSDT", at, "long", 1.0, 1.0, 1.0, False)])  # 8 fields
            async with db.pool.acquire() as c:
                rows = [tuple(r) for r in await c.fetch(
                    "SELECT exchange, side, mapping_version FROM liquidations ORDER BY id")]
            assert rows == [("bybit", "short", None), ("bybit", "long", 2), ("okx", "long", None)]
        finally:
            await db.close()
            await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
            await admin.close()
    asyncio.run(body())
