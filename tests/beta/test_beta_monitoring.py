"""A3 monitoring (PRE_BETA_BACKLOG_V1), pure: a Binance-only outage, the research feeds / stress hours /
history sync and build failures, the failure spike by kind, the notifier dead-man run from the bot process
and the optional external ping. Synthetic inputs only."""
import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from beta.config import BetaConfig
from beta.health import health_alerts, notifier_deadman_due
from beta_fakes import ON

CFG = BetaConfig.load()
UTC = timezone.utc
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
QUIET = dataclasses.replace(ON, detection=False, outcome_tracking=False, telegram=False)


def _keys(**kw):
    args = dict(now=NOW, heartbeat={"healthy": True, "ages_s": {"binance": 20, "bybit": 20, "okx": 20}},
                detector_watermark=None, latest_live=None, runtime={}, delivery_problems=0, switches=QUIET)
    args.update(kw)
    return {a["key"]: a["detail"] for a in health_alerts(CFG, **args)}


def test_a_binance_only_outage_alerts_while_the_heartbeat_is_healthy():
    assert "BINANCE_STALE" not in _keys()
    stale = _keys(heartbeat={"healthy": True, "ages_s": {"binance": 900, "bybit": 20, "okx": 20}})
    assert stale["BINANCE_STALE"] == {"age_s": 900}
    assert _keys(heartbeat={"healthy": True, "ages_s": {"binance": None, "bybit": 20, "okx": 20}})["BINANCE_STALE"] \
        == {"age_s": None}
    down = _keys(heartbeat={"healthy": False, "healthy_venues": [], "ages_s": {"binance": 900}})
    assert "INGESTION_STALE" in down and "BINANCE_STALE" not in down          # one alert for one cause


def _row(ok_ago_s, run_ago_s=None, error=None):
    run = NOW - timedelta(seconds=run_ago_s if run_ago_s is not None else ok_ago_s)
    return {"last_run_at": run, "last_success_at": NOW - timedelta(seconds=ok_ago_s), "last_error_type": error}


def test_jobs_alert_by_their_own_cadence_once_they_have_run():
    assert not {"FEEDS_FAILING", "STRESS_HOURS_FAILING", "HISTORY_SYNC_FAILING"} & set(_keys())   # never ran
    ok = _keys(runtime={"research_feeds": _row(300), "research_stress_hours": _row(3600),
                        "history_sync": _row(20 * 3600)})
    assert not {"FEEDS_FAILING", "STRESS_HOURS_FAILING", "HISTORY_SYNC_FAILING"} & set(ok)
    bad = _keys(runtime={"research_feeds": _row(31 * 60, 60, "ClientError"), "research_stress_hours": _row(4 * 3600),
                         "history_sync": _row(51 * 3600)})
    assert bad["FEEDS_FAILING"] == {"error": "ClientError"}
    assert "STRESS_HOURS_FAILING" in bad and "HISTORY_SYNC_FAILING" in bad


def test_a_failed_build_and_a_failed_definition_check_alert_at_once():
    k = _keys(runtime={"history_build": _row(20 * 3600, 600, "RangeModelError"),
                       "research_feeds_definition": _row(3600, 60)})
    assert k["HISTORY_BUILD_FAILED"] == {"error": "RangeModelError"} and "FEEDS_DEFINITION_CHECK_FAILED" in k
    fine = _keys(runtime={"history_build": _row(600), "research_feeds_definition": _row(60)})
    assert "HISTORY_BUILD_FAILED" not in fine and "FEEDS_DEFINITION_CHECK_FAILED" not in fine


def test_the_failure_spike_names_its_kinds():
    k = _keys(delivery_problems=4, delivery_problems_by_kind={"brief": 3, "alert": 1})
    assert k["DELIVERY_FAILURE_SPIKE"] == {"count": 4, "by_kind": {"brief": 3, "alert": 1}}


def test_the_dead_man_is_due_only_after_the_stall_and_not_twice_within_the_repeat():
    started = NOW - timedelta(hours=2)
    rt = {"notifier": {"last_success_at": NOW - timedelta(minutes=5)}}
    assert not notifier_deadman_due(rt, now=NOW, stall_s=600, repeat_s=1800, watcher_started_at=started)
    rt = {"notifier": {"last_success_at": NOW - timedelta(minutes=11)}}
    assert notifier_deadman_due(rt, now=NOW, stall_s=600, repeat_s=1800, watcher_started_at=started)
    rt["owner_alert:NOTIFIER_DEADMAN"] = {"last_success_at": NOW - timedelta(minutes=10)}
    assert not notifier_deadman_due(rt, now=NOW, stall_s=600, repeat_s=1800, watcher_started_at=started)
    # never ran: counted from the watcher's own start, so a fresh deploy does not alert at once
    assert not notifier_deadman_due({}, now=NOW, stall_s=600, repeat_s=1800, watcher_started_at=NOW - timedelta(minutes=2))
    assert notifier_deadman_due({}, now=NOW, stall_s=600, repeat_s=1800, watcher_started_at=started)


class _Conn:
    def __init__(self, runtime):
        self.runtime = runtime

    async def fetch_health(self):
        return self.runtime

    async def record_health(self, component, *, now, success, detail=None, error_type=None):
        self.runtime[component] = {"last_success_at": now if success else None}


class _Sender:
    def __init__(self):
        self.sent = []

    async def send(self, *, chat_id, html, buttons=None):
        self.sent.append((chat_id, html))
        return 1


def test_the_bot_process_alerts_the_owner_once_per_repeat():
    from runtime.beta_bot import _notifier_deadman
    conn, s = _Conn({"notifier": {"last_success_at": NOW - timedelta(minutes=30)}}), _Sender()
    on = dataclasses.replace(ON, telegram=True)
    started = NOW - timedelta(hours=1)
    assert asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW))
    assert s.sent and s.sent[0][0] == 777 and "NOTIFIER_DEADMAN" in s.sent[0][1]
    assert not asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW + timedelta(minutes=5)))
    assert len(s.sent) == 1
    assert not asyncio.run(_notifier_deadman(_Conn({}), _Sender(), CFG, on, None, started_at=started, now=NOW))


def test_the_external_ping_is_optional_https_only_and_never_raises(monkeypatch):
    from beta import delivery
    monkeypatch.delenv(delivery.DEADMAN_PING_ENV, raising=False)
    assert asyncio.run(delivery.deadman_ping()) == "OFF"
    assert asyncio.run(delivery.deadman_ping("http://example.invalid/x")) == "REFUSED_NOT_HTTPS"

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: _Resp())
    assert asyncio.run(delivery.deadman_ping("https://hc.example/abc")) == "OK"

    def _boom(url, timeout):
        raise OSError("unreachable")
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert asyncio.run(delivery.deadman_ping("https://hc.example/abc")) == "FAILED"


def test_the_outage_texts_exist_in_both_languages():
    from beta.i18n import t
    for lang in ("ru", "en"):
        assert t(lang, "outage_start") and t(lang, "outage_end")
    assert "сбой" in t("ru", "outage_start").lower() and "устранён" in t("ru", "outage_end")
