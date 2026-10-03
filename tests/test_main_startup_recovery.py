"""Stage-1 startup-recovery readiness row (common.startup_recovery): main.py records
one row per live start, 'running' until the startup backfill/gap-fill is done, and
never leaves it 'running' on a clean exit. run_gap_fill reports per-venue results."""
from __future__ import annotations

import asyncio

import pytest

import main
from backfill import backfill
from common import startup_recovery as sr
from test_main_shadow_cli import _patch_common


class _Stop(Exception):
    pass


def _fakes(monkeypatch, events, *, gap_fill=None, manager_start=None):
    class _DB:
        def __init__(self, dsn): pass
        async def connect(self): events.append("connect")
        async def init_schema(self): events.append("init_schema")
        async def seed_capabilities(self, rows, enabled_exchanges=None): pass
        async def cancel_stale_backfill_runs(self):
            events.append("sweep")
            return "UPDATE 0"

        async def start_backfill_run(self, exchange, symbol, source, window_start, window_end):
            events.append(("start_run", exchange, symbol, source))
            return 41

        async def finish_backfill_run(self, run_id, status, rows_written, note=""):
            events.append(("finish_run", run_id, status, rows_written, note))

        async def close(self): events.append("close")

    class _Redis:
        def __init__(self, url): pass
        async def connect(self): pass
        async def close(self): pass

    class _Mgr:
        def __init__(self, *a): pass

        async def start(self):
            events.append("live")
            if manager_start:
                manager_start()
            raise _Stop()

        async def stop(self): events.append("manager_stop")

    async def _backfill(**k):
        events.append("backfill")

    async def _gap_fill(db, symbol, exchanges):
        events.append("gap_fill")
        if isinstance(gap_fill, BaseException):
            raise gap_fill
        return gap_fill

    monkeypatch.setattr(main, "Database", _DB)
    monkeypatch.setattr(main, "RedisState", _Redis)
    monkeypatch.setattr(main, "IngestionManager", _Mgr)
    monkeypatch.setattr(main, "run_backfill", _backfill)
    monkeypatch.setattr(main, "run_gap_fill", _gap_fill)


def _run_main(argv):
    return asyncio.run(main.run(main.parse_args(argv)))


def _runs(events):
    return [e for e in events if isinstance(e, tuple)]


def test_live_start_records_running_then_ready_before_live_ingestion(monkeypatch):
    _patch_common(monkeypatch)
    events = []
    results = {"binance": {"status": sr.GAP_FILLED, "bars": 23}, "bybit": {"status": sr.GAP_FILLED, "bars": 23},
               "okx": {"status": sr.GAP_FILLED, "bars": 22}}
    _fakes(monkeypatch, events, gap_fill=results)
    with pytest.raises(_Stop):
        _run_main([])
    assert events.index("sweep") < events.index(("start_run", "*", "BTCUSDT", "startup_recovery"))
    start = events.index(("start_run", "*", "BTCUSDT", "startup_recovery"))
    finish = next(i for i, e in enumerate(events) if isinstance(e, tuple) and e[0] == "finish_run")
    assert start < events.index("backfill") < events.index("gap_fill") < finish < events.index("live")
    assert events[finish][:4] == ("finish_run", 41, "complete", 68)
    assert len(_runs(events)) == 2                     # finished exactly once, never re-marked


def test_skip_backfill_still_records_the_gap_fill_readiness(monkeypatch):
    _patch_common(monkeypatch)
    events = []
    _fakes(monkeypatch, events, gap_fill={"binance": {"status": sr.GAP_FAILED, "bars": 0},
                                          "okx": {"status": sr.GAP_CURRENT, "bars": 0}})
    with pytest.raises(_Stop):
        _run_main(["--skip-backfill"])
    assert "backfill" not in events
    finish = [e for e in _runs(events) if e[0] == "finish_run"]
    assert finish[0][2] == "partial" and "binance=failed" in finish[0][4]


def test_a_failed_gap_fill_never_leaves_the_row_running(monkeypatch):
    _patch_common(monkeypatch)
    events = []
    _fakes(monkeypatch, events, gap_fill=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        _run_main([])
    assert [e[2] for e in _runs(events) if e[0] == "finish_run"] == ["failed"]
    assert "live" not in events and "close" in events


def test_backfill_only_records_no_readiness_row(monkeypatch):
    _patch_common(monkeypatch)
    events = []
    _fakes(monkeypatch, events, gap_fill={})
    _run_main(["--backfill-only"])
    assert _runs(events) == []


def test_finish_status():
    assert sr.finish_status({"binance": {"status": "filled", "bars": 3}, "okx": {"status": "current", "bars": 0}}
                            ) == ("complete", 3, "binance=filled:3 okx=current:0")
    assert sr.finish_status({"bybit": {"status": "failed", "bars": 0}})[0] == "partial"
    assert sr.finish_status({}) == ("complete", 0, "")


def test_run_gap_fill_reports_per_venue_results(monkeypatch):
    from datetime import datetime, timedelta, timezone
    last = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=30)

    class _DB:
        async def fetchval(self, sql, exchange, symbol):
            return {"binance": last, "bybit": last, "okx": None}.get(exchange,
                                                                      datetime.now(tz=timezone.utc))

        async def insert_klines(self, rows, source):
            assert source == "backfill"                  # gap-fill bars are never 'live'
            return len(rows)

    async def ok(session, symbol, start_ms, end_ms):
        return [("binance", symbol)] * 29

    async def bad(session, symbol, start_ms, end_ms):
        raise RuntimeError("rest down")

    monkeypatch.setattr(backfill, "KLINES_FETCHERS", {"binance": ok, "bybit": bad, "okx": ok, "kraken": ok})
    res = asyncio.run(backfill.run_gap_fill(_DB(), "BTCUSDT", ["binance", "bybit", "okx", "kraken", "nope"]))
    assert res == {"binance": {"status": sr.GAP_FILLED, "bars": 29}, "bybit": {"status": sr.GAP_FAILED, "bars": 0},
                   "okx": {"status": sr.GAP_NO_HISTORY, "bars": 0}, "kraken": {"status": sr.GAP_CURRENT, "bars": 0},
                   "nope": {"status": sr.GAP_UNSUPPORTED, "bars": 0}}
