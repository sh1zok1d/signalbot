"""A3 monitoring (PRE_BETA_BACKLOG_V1, with the external review of A3), pure: a Binance-only outage on
the decision's own clock, the research feeds / stress hours / history sync judged by their cadence from
the first run, the definition check failing only on FAILED, a swallowed notifier step reaching the
owner, the failure spike from every kind with blocked participants apart, the notifier dead-man run
from the bot process with a two-row read, and the external ping: only when asked, also when the beta
is disabled, and bounded including name resolution. Synthetic inputs only."""
import asyncio
import dataclasses
import time
from datetime import datetime, timedelta, timezone

from beta.config import BetaConfig, BetaSwitches
from beta.health import health_alerts, notifier_deadman_due
from beta_fakes import ON

CFG = BetaConfig.load()
UTC = timezone.utc
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
QUIET = dataclasses.replace(ON, detection=False, outcome_tracking=False, telegram=False)


def _keys(**kw):
    args = dict(now=NOW, heartbeat={"healthy": True, "ages_s": {"binance": 20, "bybit": 20, "okx": 20}},
                detector_watermark=None, latest_live=None, runtime={}, switches=QUIET)
    args.update(kw)
    return {a["key"]: a["detail"] for a in health_alerts(CFG, **args)}


def test_a_binance_only_outage_alerts_on_the_decisions_clock():
    assert "BINANCE_STALE" not in _keys()
    # A3 review 9: the heartbeat ages from the bar's close, the screens from its open; 545 s after
    # the close is 605 s after the open: the screens already say «данные отстают»
    stale = _keys(heartbeat={"healthy": True, "ages_s": {"binance": 545, "bybit": 20, "okx": 20}})
    assert stale["BINANCE_STALE"] == {"age_s": 605}
    assert "BINANCE_STALE" not in _keys(heartbeat={"healthy": True, "ages_s": {"binance": 535}})
    assert _keys(heartbeat={"healthy": True, "ages_s": {"binance": None, "bybit": 20, "okx": 20}})["BINANCE_STALE"] \
        == {"age_s": None}
    down = _keys(heartbeat={"healthy": False, "healthy_venues": [], "ages_s": {"binance": 900}})
    assert "INGESTION_STALE" in down and "BINANCE_STALE" not in down          # one alert for one cause


def _row(ok_ago_s=None, run_ago_s=None, first_ago_s=None, error=None):
    run = NOW - timedelta(seconds=run_ago_s if run_ago_s is not None else (ok_ago_s or 0))
    return {"last_run_at": run, "last_error_type": error,
            "last_success_at": None if ok_ago_s is None else NOW - timedelta(seconds=ok_ago_s),
            "first_run_at": None if first_ago_s is None else NOW - timedelta(seconds=first_ago_s)}


def test_jobs_alert_by_their_own_cadence_also_before_their_first_success():
    jobs = {"FEEDS_FAILING", "STRESS_HOURS_FAILING", "HISTORY_SYNC_FAILING"}
    assert not jobs & set(_keys())                                             # never ran
    ok = _keys(runtime={"research_feeds": _row(300), "research_stress_hours": _row(3600),
                        "history_sync": _row(20 * 3600)})
    assert not jobs & set(ok)
    bad = _keys(runtime={"research_feeds": _row(31 * 60, 60, error="ClientError"),
                         "research_stress_hours": _row(4 * 3600), "history_sync": _row(51 * 3600)})
    assert bad["FEEDS_FAILING"] == {"error": "ClientError"}
    assert "STRESS_HOURS_FAILING" in bad and "HISTORY_SYNC_FAILING" in bad
    # A3 review 5: no success yet: the grace runs from the first run, not from nothing
    young = _keys(runtime={"research_feeds": _row(None, 0, first_ago_s=5 * 60, error="SCHEMA_NOT_READY")})
    assert "FEEDS_FAILING" not in young
    old = _keys(runtime={"research_feeds": _row(None, 0, first_ago_s=31 * 60, error="SCHEMA_NOT_READY")})
    assert old["FEEDS_FAILING"] == {"error": "SCHEMA_NOT_READY"}


def test_the_definition_check_alerts_on_failed_only_and_a_failed_build_at_once():
    k = _keys(runtime={"history_build": _row(20 * 3600, 600, error="RangeModelError")})
    assert k["HISTORY_BUILD_FAILED"] == {"error": "RangeModelError"}
    assert "HISTORY_BUILD_FAILED" not in _keys(runtime={"history_build": _row(600)})
    # A3 review 1: PENDING (not enough overlap yet) is the feeds' success=False too, but no failure
    pending = {**_row(None, 60), "detail": {"oi_base": {"status": "PENDING"}, "ls_account_ratio": {"status": "OK"}}}
    assert "FEEDS_DEFINITION_CHECK_FAILED" not in _keys(runtime={"research_feeds_definition": pending})
    failed = {**_row(None, 60), "detail": {"oi_base": {"status": "FAILED"}, "ls_account_ratio": {"status": "OK"}}}
    assert _keys(runtime={"research_feeds_definition": failed})["FEEDS_DEFINITION_CHECK_FAILED"] == \
        {"fields": ["oi_base"]}


def test_a_swallowed_notifier_step_reaches_the_owner_under_its_own_key():
    """A3 review 3: market alerts or the weekly report failing while the outbox carried on; review of
    #345: one key per step, so one step's repeat window never hides the other's failure."""
    k = _keys(runtime={"notify_market": _row(600, 0, error="KeyError"), "notify_weekly": _row(0)})
    assert k["NOTIFIER_STEP_FAILED_MARKET"] == {"step": "market", "error": "KeyError"}
    both = _keys(runtime={"notify_market": _row(600, 0, error="KeyError"),
                          "notify_weekly": _row(600, 0, error="ValueError")})
    assert both["NOTIFIER_STEP_FAILED_WEEKLY"] == {"step": "weekly", "error": "ValueError"}
    assert "NOTIFIER_STEP_FAILED_MARKET" in both
    assert not {"NOTIFIER_STEP_FAILED_MARKET", "NOTIFIER_STEP_FAILED_WEEKLY"} & \
        set(_keys(runtime={"notify_market": _row(0), "notify_weekly": _row(0)}))


def test_the_failure_spike_counts_every_kind_and_keeps_blocked_participants_apart():
    """A3 review 2 and A5 review 2: blocked participants never make a spike; expired and flood-control
    rows do."""
    problems = {"by_kind": {"brief": 2, "alert": 1}, "by_reason": {"expired": 2, "throttled": 1}, "blocked": 5}
    assert _keys(delivery_problems=problems)["DELIVERY_FAILURE_SPIKE"] == \
        {"count": 3, "by_kind": {"brief": 2, "alert": 1}, "by_reason": {"expired": 2, "throttled": 1}, "blocked": 5}
    assert "DELIVERY_FAILURE_SPIKE" not in _keys(delivery_problems={"by_kind": {}, "blocked": 20})


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
        self.runtime, self.reads = runtime, []

    async def fetch_health(self, components=None):
        self.reads.append(None if components is None else sorted(components))
        return {k: v for k, v in self.runtime.items() if components is None or k in components}

    async def record_health(self, component, *, now, success, detail=None, error_type=None):
        prev = (self.runtime.get(component) or {}).get("last_success_at")
        self.runtime[component] = {"last_success_at": now if success else prev, "last_run_at": now,
                                   "last_error_type": error_type}


class _Sender:
    def __init__(self, exc=None):
        self.sent, self.exc = [], exc

    async def send(self, *, chat_id, html, buttons=None):
        self.sent.append((chat_id, html))
        if self.exc is not None:
            raise self.exc
        return 1


def test_a_refused_or_ambiguous_dead_man_alert_is_not_repeated_within_the_window():
    """Review of #345: as the outbox, an ambiguous send may have arrived and a refused one would be refused
    again; neither is retried on every poll."""
    from beta.delivery import DeliveryAmbiguous, DeliveryRejected
    from runtime.beta_bot import _notifier_deadman
    on = dataclasses.replace(ON, telegram=True)
    started = NOW - timedelta(hours=1)
    for exc in (DeliveryRejected("Forbidden: bot was blocked by the user"), DeliveryAmbiguous("TimedOut")):
        conn, s = _Conn({"notifier": {"last_success_at": NOW - timedelta(minutes=30)}}), _Sender(exc)
        asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW))
        asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW + timedelta(minutes=5)))
        assert len(s.sent) == 1, exc


def test_the_bot_process_alerts_the_owner_once_per_repeat_reading_two_rows():
    from runtime.beta_bot import _notifier_deadman
    conn, s = _Conn({"notifier": {"last_success_at": NOW - timedelta(minutes=30)}, "other": {}}), _Sender()
    on = dataclasses.replace(ON, telegram=True)
    started = NOW - timedelta(hours=1)
    assert asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW))
    assert s.sent and s.sent[0][0] == 777 and "NOTIFIER_DEADMAN" in s.sent[0][1]
    assert not asyncio.run(_notifier_deadman(conn, s, CFG, on, 777, started_at=started, now=NOW + timedelta(minutes=5)))
    assert len(s.sent) == 1
    # A3 review 15: every poll reads the two rows it needs, never the whole table
    assert conn.reads == [["notifier", "owner_alert:NOTIFIER_DEADMAN"]] * 2
    assert not asyncio.run(_notifier_deadman(_Conn({}), _Sender(), CFG, on, None, started_at=started, now=NOW))


def test_the_external_ping_is_optional_https_only_bounded_and_never_raises(monkeypatch):
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

    # A3 review 10: a hanging name resolution never holds the run past the bound
    def _hang(url, timeout):
        time.sleep(3)
        return _Resp()
    monkeypatch.setattr(urllib.request, "urlopen", _hang)
    t0 = time.monotonic()
    assert asyncio.run(delivery.deadman_ping("https://hc.example/abc", timeout_s=0.3)) == "TIMEOUT"
    assert time.monotonic() - t0 < 1.5


def test_the_ping_is_sent_only_when_asked_and_also_when_the_beta_is_off(monkeypatch):
    """A3 review 6 and 8: tests and manual runs never ping; a disabled beta or the no-Telegram shadow
    soak still pings when the unit asks (the box and the timer are alive)."""
    from beta import delivery
    calls = []

    async def ping():
        calls.append(1)
        return "OK"
    monkeypatch.setattr(delivery, "deadman_ping", ping)
    off = BetaSwitches(enabled=False, detection=False, push_hard=False, outcome_tracking=False)
    shadow = dataclasses.replace(ON, telegram=False)
    for sw in (off, shadow):
        r = asyncio.run(delivery.run_notify_once(None, CFG, sw, sender=None, clock=lambda: NOW))
        assert "deadman_ping" not in r
        r = asyncio.run(delivery.run_notify_once(None, CFG, sw, sender=None, clock=lambda: NOW, ping=True))
        assert r["deadman_ping"] == "OK"
    assert calls == [1, 1]


def test_the_cli_pings_only_with_the_units_flag(monkeypatch):
    import main
    from beta import delivery
    from runtime.beta_cli import run_beta_cli_command
    calls = []

    async def ping():
        calls.append(1)
        return "OK"
    monkeypatch.setattr(delivery, "deadman_ping", ping)
    env = {"BETA_ENABLED": "0"}
    out = asyncio.run(run_beta_cli_command(main.parse_args(["--beta-notify-once", "--beta-json"]), db=object(), env=env,
                                           clock=lambda: NOW))
    assert out["status"] == "DISABLED" and "deadman_ping" not in out and calls == []
    out = asyncio.run(run_beta_cli_command(main.parse_args(["--beta-notify-once", "--beta-deadman-ping",
                                                            "--beta-json"]), db=object(), env=env, clock=lambda: NOW))
    assert out["deadman_ping"] == "OK" and calls == [1]


def test_the_outage_texts_exist_in_both_languages():
    from beta.i18n import t
    for lang in ("ru", "en"):
        assert t(lang, "outage_start") and t(lang, "outage_end")
    assert "сбой" in t("ru", "outage_start").lower() and "устранён" in t("ru", "outage_end")
