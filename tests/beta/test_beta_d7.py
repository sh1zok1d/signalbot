"""D7 regime context: definition edges, display rules, job, context bump."""
import ast
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta.formatter import format_1h_tab, format_btc, format_event_tab, format_readiness_details
from beta.health import health_alerts
from beta.i18n import t
from beta.regime_d7 import (BAR_MS, HOUR_MS, WARMUP_VALID_HOURS, HourBar, MinuteBar,
                            aggregate_completed_hours, build_d7_states, definition_digest,
                            last_completed_hour, parse_closed_kline, regime_payload)
from beta_fakes import CFG, TEST_DSN, run

REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
NOW = datetime(2026, 6, 15, 15, 30, tzinfo=UTC)          # during hour 15:00–16:00 UTC
H = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)             # last completed clock hour


def test_beta_modules_do_not_import_scripts_research():
    files = list((REPO / "beta").glob("*.py")) + list((REPO / "runtime").glob("beta_*.py"))
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("scripts.research"), (path, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scripts.research"), (path, alias.name)
    source = (REPO / "beta" / "regime_d7.py").read_text(encoding="utf-8")
    assert "PROTECTED_START" not in source
    assert "hit_rate" not in source and "mu_d7" not in source
    for path in (REPO / "tests" / "beta").glob("*.py"):
        if path.name == "test_beta_d7_parity.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("scripts.research"), path
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scripts.research"), path


def test_context_identity_is_v1_and_v0_stays_pinned():
    from beta.config import BetaConfig
    from beta.context import KNOWN_CONTEXT_DIGESTS, context_digest, verify_versions
    from test_beta_config import PINNED_RULES_DIGEST
    cfg = BetaConfig.load()
    versions = verify_versions(cfg)
    assert cfg.section("context")["version"] == "BETA_CONTEXT_1H_V1"
    assert versions["context_version"] == "BETA_CONTEXT_1H_V1"
    assert versions["context_digest"] == KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V1"]
    assert context_digest(cfg) == "59e3df506f7a162f87b69d088fff3d59660dca034efeca48f7f3b4a87ded2576"
    assert KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V0"] == (
        "7f94fde838a33fb094c6683b8834a2f9accbf96f6fb6d3fcc356aab9f49dc701")
    assert cfg.rules_digest == PINNED_RULES_DIGEST
    assert cfg["regime_d7"]["enabled"] is False


def test_59_of_60_bars_is_skipped_and_2026_hours_are_kept():
    start = datetime(2026, 6, 1, tzinfo=UTC)
    bars = []
    for hour, count in ((0, 60), (1, 59), (2, 60)):
        for minute in range(count):
            open_ms = int((start + timedelta(hours=hour, minutes=minute)).timestamp() * 1000)
            bars.append(MinuteBar(open_ms, open_ms + BAR_MS, 100.0, 101.0, 10.0))
    hours = aggregate_completed_hours(bars)
    assert [h.hour_start_ms for h in hours] == [
        int(start.timestamp() * 1000),
        int((start + timedelta(hours=2)).timestamp() * 1000),
    ]
    assert [h.quote_volume_1h for h in hours] == [600.0, 600.0]
    assert all(h.hour_start_ms >= int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000) for h in hours)


def test_warmup_boundary_needs_1440_prior_valid_hours():
    base = datetime(2021, 1, 1, tzinfo=UTC)
    hours = []
    for i in range(WARMUP_VALID_HOURS + 1):
        ms = int((base + timedelta(hours=i)).timestamp() * 1000)
        hours.append(HourBar(ms, ms + HOUR_MS, 100.0, 100.0 * math.exp(0.001), 1.0, 0.001, 0.001))
    states = build_d7_states(hours)
    assert states[1439].d7_state is None
    assert states[1440].d7_state is False          # equal to p90, strict >
    assert all(s.d7_state is None for s in states[:1440])


def _clock_row(**overrides):
    row = {"hour_start": H, "complete": True, "state": True,
           "available_at": H + timedelta(hours=1),
           "computed_at": H + timedelta(hours=1, minutes=5),
           "definition_digest": "ab" * 32}
    row.update(overrides)
    return row


def _decide(**kw):
    return regime_payload(
        enabled=kw.pop("enabled", True),
        now=kw.pop("now", NOW),
        row=kw.pop("row", _clock_row()),
        valid_before=kw.pop("valid_before", WARMUP_VALID_HOURS),
        product_status=kw.pop("product_status", "NO ACTIVE EVENTS"),
    )


def test_display_requires_every_condition():
    assert _decide()["shown"] is True
    assert _decide(row=_clock_row(state=False))["shown"] is False
    assert _decide(row=_clock_row(state=None))["shown"] is False
    assert _decide(row=_clock_row(complete=False))["shown"] is False
    assert _decide(valid_before=WARMUP_VALID_HOURS - 1)["shown"] is False
    assert _decide(row=_clock_row(computed_at=H + timedelta(hours=1, minutes=10)))["shown"] is False
    assert _decide(row=_clock_row(computed_at=H + timedelta(hours=1, minutes=10) - timedelta(seconds=1)))["shown"] is True
    assert _decide(product_status="DATA STALE")["shown"] is False
    assert _decide(product_status="DATA DEGRADED")["shown"] is False
    assert _decide(enabled=False)["shown"] is False
    later = datetime(2026, 6, 15, 16, 0, tzinfo=UTC)
    assert last_completed_hour(later) == H + timedelta(hours=1)
    assert _decide(now=later)["shown"] is False
    assert _decide(now=later)["hour_start"].startswith("2026-06-15T15:00:00")


def _calm(regime):
    return {
        "headline": "NO ACTIVE EVENTS", "product_status": "NO ACTIVE EVENTS", "readiness": None,
        "projection_available": True, "active_episode": None, "last_event": None, "other_active": [],
        "data_through": "2026-06-15T15:05:00+00:00", "requested_at": "2026-06-15T15:30:00+00:00",
        "now": {"reference_price": 112450.0},
        "horizons": {
            "1h": {"complete": True, "price_move_pct": -0.8, "volume_notional_usd": 1.9e9,
                   "volume_ratio": 2.1, "range_width_pct": 1.12, "range_ratio": 2.3,
                   "oi_change_pct": -0.6, "window_start": "2026-06-15T14:10:00+00:00",
                   "window_end": "2026-06-15T15:10:00+00:00",
                   "oi_by_venue": {}, "taker_delta_notional_usd_sum": -8.4e7,
                   "funding_rate": 0.00006, "liquidations": {"venues": {}}},
            "24h": {"price_complete": True, "price_move_pct": -1.9, "volume_complete": True,
                    "volume_ratio": 1.3, "oi_change_pct": 2.1},
        },
        "regime": regime,
    }


def test_exact_strings_on_a_calm_screen_and_in_the_glossary():
    shown = _decide()
    assert shown["shown"] is True
    ru = format_btc(CFG, _calm(shown), "ru")
    en = format_btc(CFG, _calm(shown), "en")
    assert "High impact в прошлый час" in ru
    assert "High impact last hour" in en
    assert "No unusual state now" in en
    tab_ru = format_1h_tab(CFG, _calm(shown), "ru")
    tab_en = format_1h_tab(CFG, _calm(shown), "en")
    assert "High impact 17:00–18:00 (Киев): цена прошла много относительно объёма торгов." in tab_ru
    assert "Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно в 1 из 10)." in tab_ru
    assert "Направление цены это не показывает." in tab_ru
    assert "High impact 17:00–18:00 Kyiv: price moved a lot relative to traded volume." in tab_en
    assert "Historically, the following hour was also like this about 1 in 5 times (usually 1 in 10)." in tab_en
    assert "This says nothing about price direction." in tab_en
    assert t("ru", "d7_main") == "High impact в прошлый час"
    assert t("en", "d7_main") == "High impact last hour"
    assert "High impact — за прошлый календарный час цена прошла много относительно объёма торгов." in t("ru", "terms")
    assert "обычно 1 из 10" in t("ru", "terms")
    assert "High impact — in the last clock hour the price moved a lot relative to traded volume." in t("en", "terms")
    assert "It says nothing about price direction." in t("en", "terms")
    hidden = format_btc(CFG, _calm(_decide(product_status="DATA STALE")), "en")
    assert "High impact last hour" not in hidden
    off = _calm(None)
    off.pop("regime")
    assert "High impact last hour" not in format_btc(CFG, off, "en")
    assert "High impact 17:00" not in format_1h_tab(CFG, off, "en")
    stale = _calm(shown)
    stale["product_status"] = "DATA STALE"
    stale["headline"] = "DATA STALE"
    assert "High impact last hour" not in format_btc(CFG, stale, "en")


def test_readiness_warmup_line_and_old_anchor_oi():
    rd = {"bucket_ts": "2026-06-15T14:55:00+00:00", "maturity_days": 30.0, "groups": [],
          "events": {}, "readiness_version": "BETA_READINESS",
          "impact_context": {"warmup_complete": False, "valid_hours_before": 10}}
    text = format_readiness_details(CFG, rd, "ru")
    assert "Контекст импакта: бот собирает историю" in text
    assert "Impact context: history building" in format_readiness_details(CFG, {**rd,
        "impact_context": {"warmup_complete": False}}, "en")
    done = format_readiness_details(CFG, {**rd, "impact_context": {"warmup_complete": True}}, "en")
    assert "Impact context: history building" not in done
    bare = format_readiness_details(CFG, {k: v for k, v in rd.items() if k != "impact_context"}, "en")
    assert "Impact context" not in bare
    view = {"active_episode": {
        "event_type": "PRICE_OI_CONTRACTION_DOWN", "opened_at": "2026-06-15T12:00:00+00:00",
        "episode_id": "EV-OLD", "anchor": {"view": {
            "bucket_ts": "2026-06-15T12:00:00+00:00",
            "price_move_pct": {"value": 1.0}, "range_width_pct": {"value": 0.4},
            "volume_notional_usd": {"value": 1000.0}, "oi_change_pct": {"value": -0.4},
            "taker_delta_notional_usd": {"value": None},
            "liquidations": {"long": {"per_venue": {}}, "short": {"per_venue": {}}},
        }}}, "last_event": None, "other_active": []}
    assert "n/a" in format_event_tab(CFG, view, "en")
    assert "н/д" in format_event_tab(CFG, view, "ru")


def test_closed_bar_filter_and_definition_digest_stable():
    now = datetime(2026, 6, 15, 15, 0, 30, tzinfo=UTC)
    now_ms = int(now.timestamp() * 1000)
    open_ms = int(datetime(2026, 6, 15, 15, 0, tzinfo=UTC).timestamp() * 1000)
    row = [open_ms, "100", "101", "99", "100.5", "1", open_ms + 59_999, "10", 1, "0", "0", "0"]
    assert parse_closed_kline(row, now_ms=now_ms, fetched_at=now) is None
    closed = [open_ms - BAR_MS, "100", "101", "99", "100.5", "1", open_ms - 1, "10", 1, "0", "0", "0"]
    parsed = parse_closed_kline(closed, now_ms=now_ms, fetched_at=now)
    assert parsed is not None and parsed["quote_asset_volume"] == 10.0
    assert definition_digest() == definition_digest()
    assert len(definition_digest()) == 64


def test_d7_units_and_smoke_identity_are_wired():
    assert "*:01:00 UTC" in (REPO / "deploy" / "signalbot-beta-d7.timer").read_text(encoding="utf-8")
    assert "--beta-d7-once" in (REPO / "deploy" / "signalbot-beta-d7.service").read_text(encoding="utf-8")
    install = (REPO / "deploy" / "install_beta_units.sh").read_text(encoding="utf-8")
    check = (REPO / "deploy" / "check_beta_units.sh").read_text(encoding="utf-8")
    assert "signalbot-beta-d7.timer" in install and "signalbot-beta-d7.timer" in check
    smoke = (REPO / "deploy" / "signalbot-beta-smoke.sql").read_text(encoding="utf-8")
    assert "BETA_CONTEXT_1H_V1" in smoke
    assert "59e3df506f7a162f87b69d088fff3d59660dca034efeca48f7f3b4a87ded2576" in smoke
    assert "context_gaps" in smoke and "d7_missing" in smoke


def test_d7_health_alert_uses_available_at_age():
    from beta.config import BetaSwitches
    fresh_runtime = {"outcomes": {"last_success_at": NOW}, "bot": {"last_success_at": NOW},
                     "notifier": {"last_success_at": NOW}}
    kw = dict(now=NOW, heartbeat={"healthy": True}, detector_watermark=NOW - timedelta(minutes=5),
              latest_live={"snapshot": {"materialized": True}}, runtime=fresh_runtime,
              delivery_problems=0, switches=BetaSwitches(True, True, False, True))
    on = CFG.with_overrides(regime_d7={"enabled": True})
    assert "D7_HOUR_STATE_STALE" in {a["key"] for a in health_alerts(on, d7_newest_available_at=None, **kw)}
    old = NOW - timedelta(minutes=70, seconds=1)
    assert "D7_HOUR_STATE_STALE" in {a["key"] for a in health_alerts(on, d7_newest_available_at=old, **kw)}
    boundary = NOW - timedelta(minutes=70)
    assert "D7_HOUR_STATE_STALE" not in {a["key"] for a in health_alerts(on, d7_newest_available_at=boundary, **kw)}
    assert "D7_HOUR_STATE_STALE" not in {a["key"] for a in health_alerts(CFG, d7_newest_available_at=old, **kw)}


def test_days_flag_is_only_valid_on_backfill():
    import main
    with pytest.raises(SystemExit):
        main.parse_args(["--beta-d7-once", "--days", "90"])
    args = main.parse_args(["--beta-d7-backfill", "--days", "90", "--beta-json"])
    assert args.beta_d7_backfill and args.days == 90


# ---- PostgreSQL -----------------------------------------------------------------
pytestmark_pg = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


def _kline(open_dt, qv="10"):
    open_ms = int(open_dt.timestamp() * 1000)
    return [open_ms, "100", "101", "99", "100", "1", open_ms + 59_999, qv, 1, "0", "0", "0"]


def _exchange(start, hours, *, drop=()):
    rows = []
    for h in range(hours):
        for m in range(60):
            if (h, m) in drop:
                continue
            rows.append(_kline(start + timedelta(hours=h, minutes=m)))
    return rows


def _fetcher(rows):
    calls = []

    async def fetch(start_ms, limit):
        calls.append((start_ms, limit))
        return [r for r in rows if r[0] >= start_ms][:limit]

    return fetch, calls


@pytestmark_pg
def test_d7_job_is_idempotent_catches_up_and_skips_open_bars():
    async def body():
        from storage.beta_v0_store import BetaStore
        from beta.regime_d7 import run_d7_job
        from beta_fakes import fresh_pool
        start = datetime(2026, 3, 1, tzinfo=UTC)
        rows = _exchange(start, 8, drop={(1, 30)})
        # A bar that is still open at the first clock must not be stored.
        rows.append(_kline(start + timedelta(hours=3)))
        fetch, calls = _fetcher(rows)
        pool = await fresh_pool()
        store = BetaStore(pool)
        now1 = start + timedelta(hours=3, seconds=30)
        first = await run_d7_job(store, now=now1, mode="once", fetcher=fetch, pace_s=0)
        assert first["status"] == "OK" and first["hours_inserted"] == 1
        async with store.connect() as conn:
            hours = await conn.conn.fetch("SELECT hour_start, quote_volume_1h, state, computed_at "
                                           "FROM beta_d7_hour_states ORDER BY hour_start")
            assert [r["hour_start"] for r in hours] == [start + timedelta(hours=2)]
            assert hours[0]["quote_volume_1h"] == 600.0 and hours[0]["state"] is None
            open_bar = await conn.conn.fetchval(
                "SELECT count(*) FROM beta_d7_klines_1m WHERE open_time=$1", start + timedelta(hours=3))
            assert open_bar == 0
            stored_at = hours[0]["computed_at"]
        again = await run_d7_job(store, now=now1, mode="once", fetcher=fetch, pace_s=0)
        assert again["hours_inserted"] == 0
        now2 = start + timedelta(hours=6, seconds=30)
        caught = await run_d7_job(store, now=now2, mode="once", fetcher=fetch, pace_s=0)
        assert caught["hours_inserted"] == 3
        async with store.connect() as conn:
            hours = await conn.conn.fetch(
                "SELECT hour_start, computed_at FROM beta_d7_hour_states ORDER BY hour_start")
            got = [r["hour_start"] for r in hours]
            assert start + timedelta(hours=1) not in got
            assert got == [start + timedelta(hours=h) for h in (2, 3, 4, 5)]
            assert hours[0]["computed_at"] == stored_at
        assert calls[0][1] == 1500
        await pool.close()
    run(body())


@pytestmark_pg
def test_d7_backfill_pages_resumes_and_paces():
    async def body():
        from storage.beta_v0_store import BetaStore
        from beta.regime_d7 import run_d7_job
        from beta_fakes import fresh_pool
        start = datetime(2026, 4, 1, tzinfo=UTC)
        rows = _exchange(start, 48)
        fetch, calls = _fetcher(rows)
        pauses = []

        async def pause(seconds):
            pauses.append(seconds)

        pool = await fresh_pool()
        store = BetaStore(pool)
        now = start + timedelta(days=2, seconds=30)
        report = await run_d7_job(store, now=now, mode="backfill", days=2, fetcher=fetch,
                                  pace_s=0.2, pause=pause)
        assert report["requests"] >= 2 and report["hours_inserted"] == 48
        assert pauses and pauses[0] == 0.2
        calls.clear()
        second = await run_d7_job(store, now=now, mode="backfill", days=2, fetcher=fetch, pace_s=0)
        assert second["hours_inserted"] == 0
        # Resume from the last stored bar rather than the beginning of the window.
        assert calls[0][0] == int((start + timedelta(hours=47, minutes=59)).timestamp() * 1000)
        await pool.close()
    run(body())


@pytestmark_pg
def test_v0_context_snapshot_is_ignored_and_a_v1_chain_starts():
    import json
    import random
    from beta.context import KNOWN_CONTEXT_DIGESTS, verify_versions
    from beta.detector import run_detector_once
    from beta.state_tape import BUCKET, materialize_bucket
    from beta_fakes import (FEATURE_CODE, ON, S2, T0, Clock, ScenarioReader, deps, fresh_pool,
                            history_buckets, history_metrics, quiet, seed_history, seed_live_klines)
    from storage.beta_v0_store import BetaStore
    b0 = T0 + timedelta(days=40)
    mat = run(materialize_bucket(
        ScenarioReader(quiet), S2, CFG, bucket_ts=b0, code_version=FEATURE_CODE,
        liquidation_feed_available_by_exchange={"binance": True, "bybit": True, "okx": True}))
    calc = mat.consensus_feature.calculation_version

    async def body():
        pool = await fresh_pool()
        rng = random.Random(7)
        await seed_history(pool, calculation_version=calc, buckets=history_buckets(b0, 8),
                           metrics_fn=lambda b: history_metrics(rng))
        await seed_live_klines(pool, [b0 + i * BUCKET for i in range(300)])
        versions = verify_versions(CFG)
        marker = "EV-V0-CHAIN"
        state = {"context_version": "BETA_CONTEXT_1H_V0", "last_ended": {
            "PRICE_OI_CONTRACTION_DOWN": {"episode_id": marker, "terminal_at": "2026-03-01T00:00:00Z"}}}
        async with BetaStore(pool).connect() as conn:
            await conn.conn.execute(
                """INSERT INTO beta_context_snapshots (symbol, bucket_ts, episodization_version,
                       episodization_digest, context_version, context_digest, rules_digest,
                       prev_state_digest, state, state_digest)
                   VALUES ('BTCUSDT',$1,$2,$3,'BETA_CONTEXT_1H_V0',$4,$5,$6,$7::jsonb,$8)""",
                b0 - BUCKET, versions["episodization_version"], versions["episodization_digest"],
                KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V0"], CFG.rules_digest, "cd" * 32,
                json.dumps(state), "ab" * 32)
        clock = Clock(b0 + BUCKET + timedelta(seconds=30))
        await run_detector_once(deps(pool, ScenarioReader(quiet), clock), CFG, ON)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT context_version, context_digest, prev_state_digest, state::text AS state
                   FROM beta_context_snapshots ORDER BY bucket_ts""")
        assert [r["context_version"] for r in rows] == ["BETA_CONTEXT_1H_V0", "BETA_CONTEXT_1H_V1"]
        assert rows[0]["state"].find(marker) >= 0
        assert rows[1]["prev_state_digest"] is None
        assert rows[1]["context_digest"] == KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V1"]
        assert marker not in rows[1]["state"]
        assert '"regime"' not in rows[1]["state"]
        await pool.close()
    run(body())


@pytestmark_pg
def test_health_alerts_d7_only_when_the_flag_is_on():
    async def body():
        from beta.admin import collect_health
        from beta.config import BetaSwitches
        from beta_fakes import fresh_pool
        from storage.beta_v0_store import BetaStore
        pool = await fresh_pool()
        now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        switches = BetaSwitches(True, True, False, True)
        async with BetaStore(pool).connect() as conn:
            off = await collect_health(conn, CFG, switches, now)
            on = await collect_health(conn, CFG.with_overrides(regime_d7={"enabled": True}), switches, now)
        assert "D7_HOUR_STATE_STALE" not in {a["key"] for a in off["alerts"]}
        assert "D7_HOUR_STATE_STALE" in {a["key"] for a in on["alerts"]}
        await pool.close()
    run(body())
