"""Export scope and owner-authorization provenance (fake connection; no database, no network)."""
import asyncio
import dataclasses
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from tools.beta_user_sim.__main__ import main
from tools.beta_user_sim.bundle import (LIVE_BETA_AUTHORITY_DOC, LIVE_BETA_AUTHORIZATION_REF, LIVE_BETA_FROM,
                                        PROVENANCE_EXPORTED, SCOPE_LIVE_BETA_PROSPECTIVE,
                                        SCOPE_PRE_2025_UNSEALED, SEALED_RESEARCH_FROM, BundleError,
                                        bundle_from_dict, bundle_to_dict, export_metadata, load_bundle,
                                        write_bundle)
from tools.beta_user_sim.export import (EXPORT_QUERIES, EXPORTED_TABLES, ExportRefused, check_query,
                                        export_bundle, export_scope)
from tools.beta_user_sim.replay import ReplayConfig, ReplayEngine
from tools.beta_user_sim.report import build_report, render_markdown

from sim_helpers import CFG, bundle, models, raw_bundle

UTC = timezone.utc
COMMIT = {"commit": "TEST", "worktree_dirty": False}
LIVE_START, LIVE_END = datetime(2026, 9, 28, tzinfo=UTC), datetime(2026, 9, 29, tzinfo=UTC)


class FakeConn:
    """asyncpg stand-in: records every statement and the transaction mode."""

    def __init__(self, tables=None, now=datetime(2026, 10, 2, 12, tzinfo=UTC)):
        self.tables, self.now, self.calls, self.tx = tables or {}, now, [], []

    @asynccontextmanager
    async def _tx(self, **kw):
        self.tx.append(kw)
        yield

    def transaction(self, **kw):
        return self._tx(**kw)

    async def fetchval(self, sql):
        assert sql == "SELECT now()"
        return self.now

    async def fetch(self, sql, *args):
        assert self.tx and self.tx[-1]["readonly"] is True
        self.calls.append((sql, args))
        name = next(k for k, v in EXPORT_QUERIES.items() if v == sql)
        return [dict(r) for r in self.tables.get(name, ())]


def _export(conn, start, end, **kw):
    return asyncio.run(export_bundle(conn, CFG, start=start, end=end, **kw))


def _pre_2025_export():
    raw = raw_bundle()
    tables = {k: raw[k] for k in EXPORT_QUERIES}
    exported_at = datetime.fromisoformat(raw["exported_at"])
    conn = FakeConn(tables, now=exported_at)
    start = datetime(2024, 3, 4, 8, tzinfo=UTC)
    return conn, _export(conn, start, datetime(2024, 3, 4, 17, tzinfo=UTC), history_lookback=timedelta(0))


# ---- scope selection ------------------------------------------------------------------------------

def test_pre_2025_export_needs_no_live_beta_authorization():
    conn, raw = _pre_2025_export()
    b = bundle_from_dict(raw)
    assert b.provenance == PROVENANCE_EXPORTED
    assert b.export["export_scope"] == SCOPE_PRE_2025_UNSEALED
    assert b.export["authorization_ref"] is None and b.export["authority_doc"] is None
    assert b.btc_views and b.episodes and b.klines
    assert all(kw["readonly"] is True for kw in conn.tx)
    kl_args = next(a for s, a in conn.calls if s == EXPORT_QUERIES["klines"])
    assert kl_args[1] <= SEALED_RESEARCH_FROM


@pytest.mark.parametrize("start", [datetime(2024, 12, 31, 12, tzinfo=UTC), datetime(2025, 6, 1, tzinfo=UTC),
                                   datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 9, 24, tzinfo=UTC)])
def test_sealed_modern_windows_are_refused_with_or_without_live_beta_flag(start):
    for flag in (False, True):
        with pytest.raises(ExportRefused):
            export_scope(start, start + timedelta(hours=6), allow_live_beta_window=flag)
        conn = FakeConn()
        with pytest.raises(ExportRefused):
            _export(conn, start, start + timedelta(hours=6), allow_live_beta_window=flag)
        assert conn.calls == [] and conn.tx == []          # refused before any query


def test_live_beta_window_straddling_the_boundary_is_refused():
    with pytest.raises(ExportRefused):
        export_scope(LIVE_BETA_FROM - timedelta(minutes=1), LIVE_END, allow_live_beta_window=True)


def test_prospective_beta_window_requires_the_explicit_live_beta_scope():
    with pytest.raises(ExportRefused):
        export_scope(LIVE_START, LIVE_END)
    assert export_scope(LIVE_START, LIVE_END, allow_live_beta_window=True) == SCOPE_LIVE_BETA_PROSPECTIVE
    assert export_scope(LIVE_BETA_FROM, LIVE_END, allow_live_beta_window=True) == SCOPE_LIVE_BETA_PROSPECTIVE


def test_pre_2025_window_cannot_be_exported_under_the_live_beta_scope():
    with pytest.raises(ExportRefused):
        export_scope(datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 2, tzinfo=UTC), allow_live_beta_window=True)


def test_live_beta_export_never_reads_before_the_boundary():
    conn = FakeConn()
    raw = _export(conn, LIVE_START, LIVE_END, allow_live_beta_window=True)   # default 14-day lookback
    for sql, args in conn.calls:
        assert args[0] >= LIVE_BETA_FROM, sql
    assert datetime.fromisoformat(raw["episodes_since"]) == LIVE_BETA_FROM


# ---- durable provenance in the bundle --------------------------------------------------------------

def _live_raw():
    return _export(FakeConn(), LIVE_START, LIVE_END, allow_live_beta_window=True)


def test_live_beta_bundle_carries_and_keeps_the_owner_authorization(tmp_path):
    raw = _live_raw()
    meta = raw["export"]
    assert meta["export_scope"] == SCOPE_LIVE_BETA_PROSPECTIVE
    assert meta["authorization_ref"] == LIVE_BETA_AUTHORIZATION_REF == "SYNTHETIC_BETA_USER_V0_OWNER_AUTH_2026_10_02"
    assert meta["authority_doc"] == LIVE_BETA_AUTHORITY_DOC
    assert datetime.fromisoformat(meta["requested_start"]) == LIVE_START
    assert datetime.fromisoformat(meta["requested_end"]) == LIVE_END
    assert meta["exported_at"] == raw["exported_at"]
    path = tmp_path / "a.json"
    write_bundle(raw, path)
    copied = tmp_path / "copy.json"
    copied.write_bytes(path.read_bytes())
    b = load_bundle(copied)
    assert b.export == meta
    assert bundle_to_dict(b)["export"] == meta
    assert bundle_from_dict(bundle_to_dict(b)).export == meta


def _mutated(mutate):
    raw = json.loads(json.dumps(_live_raw()))
    mutate(raw)
    return raw


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("export"),
    lambda r: r.update(export=None),
    lambda r: r["export"].pop("authorization_ref"),
    lambda r: r["export"].update(authorization_ref=None),
    lambda r: r["export"].update(authorization_ref="SOMETHING_ELSE"),
    lambda r: r["export"].update(authority_doc=None),
    lambda r: r["export"].update(live_beta_from="2025-01-01T00:00:00+00:00"),
    lambda r: r["export"].update(requested_start="2026-03-01T00:00:00+00:00"),
    lambda r: r["export"].update(requested_start=None),
    lambda r: r["export"].update(exported_at="2026-10-03T00:00:00+00:00"),
    lambda r: r["export"].update(export_scope="PROTECTED_ANY"),
    lambda r: r["export"].update(export_scope=SCOPE_PRE_2025_UNSEALED),
    lambda r: r["export"].update(export_meta_version="OTHER"),
    lambda r: r["export"].update(extra="x"),
    lambda r: r.update(episodes_since="2026-09-11T00:00:00+00:00"),
    lambda r: r.update(klines=[{"exchange": "binance", "ts": "2026-06-01T00:00:00+00:00", "open": 1,
                                "high": 1, "low": 1, "close": 1}]),
])
def test_validator_rejects_live_beta_bundle_without_intact_authorization(mutate):
    with pytest.raises(BundleError):
        bundle_from_dict(_mutated(mutate))


def test_validator_rejects_pre_2025_bundle_with_modern_rows_or_a_borrowed_authorization():
    _, raw = _pre_2025_export()
    bundle_from_dict(raw)
    bad = json.loads(json.dumps(raw))
    bad["klines"].append({"exchange": "binance", "ts": "2025-02-01T00:00:00+00:00", "open": 1, "high": 1,
                          "low": 1, "close": 1})
    with pytest.raises(BundleError):
        bundle_from_dict(bad)
    bad = json.loads(json.dumps(raw))
    bad["export"]["authorization_ref"] = LIVE_BETA_AUTHORIZATION_REF
    with pytest.raises(BundleError):
        bundle_from_dict(bad)
    bad = json.loads(json.dumps(raw))
    bad["export"]["requested_end"] = "2024-12-31T12:00:00+00:00"
    with pytest.raises(BundleError):
        bundle_from_dict(bad)


def test_synthetic_bundle_cannot_carry_export_metadata():
    raw = raw_bundle()
    assert "export" not in raw and bundle_from_dict(raw).export is None
    raw["export"] = export_metadata(SCOPE_LIVE_BETA_PROSPECTIVE, start=LIVE_START, end=LIVE_END,
                                    exported_at=datetime(2026, 10, 2, tzinfo=UTC))
    with pytest.raises(BundleError):
        bundle_from_dict(raw)


# ---- run manifest and report propagation -----------------------------------------------------------

def _report(b):
    result = ReplayEngine(b, CFG, models(), ReplayConfig()).run()
    return result, build_report(result, run_at=datetime(2026, 10, 2, tzinfo=UTC), commit=COMMIT)


def test_replay_and_report_reproduce_the_live_beta_authorization():
    meta = bundle_from_dict(_live_raw()).export
    b = dataclasses.replace(bundle(), provenance=PROVENANCE_EXPORTED, export=meta)
    result, report = _report(b)
    assert result["bundle"]["export"] == meta
    assert report["manifest"]["bundle"]["export"] == meta
    md = render_markdown(report)
    for text in (SCOPE_LIVE_BETA_PROSPECTIVE, LIVE_BETA_AUTHORIZATION_REF, LIVE_BETA_AUTHORITY_DOC,
                 meta["requested_start"], meta["requested_end"]):
        assert text in md


def test_cli_replay_of_an_exported_bundle_records_scope_in_run_and_report(tmp_path):
    _, raw = _pre_2025_export()
    path = tmp_path / "exported.json"
    write_bundle(raw, path)
    out = tmp_path / "run"
    assert main(["replay", "--bundle", str(path), "--out", str(out), "--model", "fake"]) == 0
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert run["bundle"]["export"] == raw["export"] == rep["manifest"]["bundle"]["export"]
    md = (out / "report.md").read_text(encoding="utf-8")
    assert SCOPE_PRE_2025_UNSEALED in md and raw["export"]["requested_start"] in md


def test_synthetic_report_says_there_is_no_export_scope():
    _, report = _report(bundle())
    assert report["manifest"]["bundle"]["export"] is None
    assert "export scope: none (fully synthetic bundle)" in render_markdown(report)


# ---- query guards ----------------------------------------------------------------------------------

def test_exporter_queries_touch_only_live_beta_tables_and_klines():
    for sql in EXPORT_QUERIES.values():
        check_query(sql)
        tables = set(re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", sql, flags=re.IGNORECASE))
        assert tables and tables <= set(EXPORTED_TABLES)
        assert not re.search(r"research|archive|protected|sealed|holdout|parquet", sql, re.IGNORECASE)
    for bad in ("SELECT * FROM research_klines", "SELECT ts FROM klines_1m JOIN market_archive USING (ts)",
                "SELECT * FROM public.klines_1m_2025", "SELECT * FROM beta_episodes e JOIN beta_users u ON true"):
        with pytest.raises(ExportRefused):
            check_query(bad)


def test_cli_export_refuses_sealed_window_before_reading_the_dsn(monkeypatch, capsys):
    monkeypatch.setenv("SIM_TEST_DSN", "postgresql://never-used")
    import asyncpg

    def boom(*a, **k):
        raise AssertionError("connection attempted")
    monkeypatch.setattr(asyncpg, "connect", boom)
    rc = main(["export", "--dsn-env", "SIM_TEST_DSN", "--start", "2025-06-01T00:00:00+00:00",
               "--end", "2025-06-02T00:00:00+00:00", "--out", "/nonexistent/x.json", "--beta-live-window"])
    assert rc == 2 and "sealed" in capsys.readouterr().err
