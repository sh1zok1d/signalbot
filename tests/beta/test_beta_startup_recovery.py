"""Stage-1 startup-recovery barrier and repair selection: pure parts (offline)."""
from datetime import datetime, timedelta, timezone

import pytest

from beta import recovery
from beta.health import health_alerts
from beta_fakes import CFG, ON

T = datetime(2026, 10, 2, 22, 57, 0, tzinfo=timezone.utc)
BOOT = datetime(2026, 10, 2, 22, 56, 49, tzinfo=timezone.utc)
WAIT = recovery.max_wait(CFG)


def _row(status, started=T, finished=None, run_id=7):
    return {"id": run_id, "status": status, "started_at": started, "finished_at": finished}


def test_max_wait_is_the_detector_catch_up_bound():
    assert WAIT == CFG["detector"]["max_catchup_buckets_per_run"] * timedelta(minutes=5) == timedelta(hours=1)


@pytest.mark.parametrize("row,boot,state,proceed", [
    (None, None, recovery.NO_SIGNAL, True),
    (None, BOOT, recovery.NO_SIGNAL, True),
    (_row("complete", finished=T), None, recovery.READY, True),
    (_row("partial", finished=T), BOOT, recovery.READY, True),
    (_row("running"), BOOT, recovery.RECOVERING, False),
    (_row("cancelled", finished=T), BOOT, recovery.NOT_READY, False),
    (_row("failed", finished=T), BOOT, recovery.NOT_READY, False),
    # the newest row predates this boot: this boot's Stage-1 has not started recovering
    (_row("complete", started=BOOT - timedelta(days=1), finished=BOOT - timedelta(days=1)), BOOT,
     recovery.WAITING_FOR_STAGE1_START, False),
    # boot time unknown: the previous boot's complete row cannot be told apart (documented risk)
    (_row("complete", started=BOOT - timedelta(days=1), finished=BOOT - timedelta(days=1)), None,
     recovery.READY, True),
])
def test_startup_gate_states(row, boot, state, proceed):
    g = recovery.startup_gate(row, now=T + timedelta(seconds=5), host_boot_time=boot, max_wait=WAIT)
    assert (g["state"], g["proceed"]) == (state, proceed)
    assert g["recovery_run_id"] == (row["id"] if row else None)


def test_startup_gate_is_bounded_and_reports_what_it_waited_on():
    row = _row("running")
    assert not recovery.startup_gate(row, now=T + WAIT - timedelta(seconds=1), host_boot_time=None,
                                     max_wait=WAIT)["proceed"]
    g = recovery.startup_gate(row, now=T + WAIT, host_boot_time=None, max_wait=WAIT)
    assert (g["state"], g["proceed"], g["blocked_state"]) == (recovery.OVERDUE, True, recovery.RECOVERING)
    assert g["waited_s"] == WAIT.total_seconds() and g["waiting_since"] == T.isoformat()
    old = _row("complete", started=BOOT - timedelta(days=1), finished=BOOT - timedelta(days=1))
    g = recovery.startup_gate(old, now=BOOT + WAIT, host_boot_time=BOOT, max_wait=WAIT)
    assert (g["state"], g["blocked_state"]) == (recovery.OVERDUE, recovery.WAITING_FOR_STAGE1_START)


def test_repair_window_covers_the_catch_up_before_the_recovery_and_ends_at_its_finish():
    started = datetime(2026, 10, 2, 22, 57, 1, tzinfo=timezone.utc)
    start, end = recovery.repair_window({"started_at": started, "finished_at": started + timedelta(seconds=10)},
                                        max_catchup=12)
    assert start == datetime(2026, 10, 2, 21, 55, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 2, 22, 55, tzinfo=timezone.utc)
    for b in ("22:35", "22:40", "22:45", "22:50"):            # the incident's degraded buckets
        h, m = map(int, b.split(":"))
        assert start <= datetime(2026, 10, 2, h, m, tzinfo=timezone.utc) <= end


def test_stale_buckets_need_more_raw_bars_than_were_decided():
    b1, b2, b3 = (datetime(2026, 10, 2, 22, m, tzinfo=timezone.utc) for m in (35, 40, 45))
    decided = {b3: {"binance": 5, "bybit": 5, "okx": 5}, b1: {"binance": 0, "bybit": 0, "okx": 0},
               b2: {"binance": 5, "bybit": 4, "okx": 5}}
    raw = {(b1, "binance"): 5, (b1, "bybit"): 5, (b2, "binance"): 5, (b2, "bybit"): 5, (b2, "okx"): 5,
           (b3, "binance"): 5, (b3, "bybit"): 5, (b3, "okx"): 5}
    assert recovery.stale_buckets(decided, raw, ("binance", "bybit", "okx")) == [b1, b2]
    # raw that never arrived is not "stale": nothing to repair
    assert recovery.stale_buckets({b1: {"binance": 0}}, {}, ("binance",)) == []


def test_read_host_boot_time(tmp_path):
    p = tmp_path / "stat"
    p.write_text("cpu  1 2 3\nbtime 1790981809\nprocesses 5\n")
    assert recovery.read_host_boot_time(str(p)) == datetime.fromtimestamp(1790981809, tz=timezone.utc)
    p.write_text("cpu  1 2 3\n")
    assert recovery.read_host_boot_time(str(p)) is None
    assert recovery.read_host_boot_time(str(tmp_path / "missing")) is None


def _alerts(runtime):
    return {a["key"] for a in health_alerts(CFG, now=T, heartbeat={"healthy": True}, detector_watermark=T,
                                            latest_live=None, runtime=runtime, delivery_problems=0,
                                            switches=ON)}


def test_health_alerts_for_a_stuck_recovery_and_an_incomplete_repair():
    stall = CFG["health"]["detector_stall_s"]

    def det(state, waited):
        return {"detector": {"last_success_at": T, "detail": {"startup_recovery": {"state": state,
                                                                                   "waited_s": waited}}}}
    assert "STAGE1_RECOVERY_NOT_READY" not in _alerts(det(recovery.RECOVERING, 20))     # a normal short wait
    assert "STAGE1_RECOVERY_NOT_READY" in _alerts(det(recovery.RECOVERING, stall))
    assert "STAGE1_RECOVERY_NOT_READY" in _alerts(det(recovery.OVERDUE, WAIT.total_seconds()))
    assert "STAGE1_RECOVERY_NOT_READY" not in _alerts(det(recovery.READY, None))
    rep = {recovery.REPAIR_COMPONENT: {"last_success_at": None, "detail": {"complete": False, "failed": 1}}}
    assert "STARTUP_RECOVERY_REPAIR_INCOMPLETE" in _alerts(rep)
    rep[recovery.REPAIR_COMPONENT]["detail"] = {"complete": True}
    assert "STARTUP_RECOVERY_REPAIR_INCOMPLETE" not in _alerts(rep)


def test_a_stage1_crash_loop_cannot_reset_the_bound():
    first = T
    prev = {"last_run_at": T + timedelta(minutes=55),
            "detail": {"startup_recovery": {"state": recovery.RECOVERING, "waiting_since": first.isoformat()}}}
    now = T + WAIT
    since = recovery.continuing_block(prev, now=now, max_wait=WAIT)
    assert since == first
    newest = _row("running", started=now - timedelta(seconds=30), run_id=99)   # restarted again
    assert not recovery.startup_gate(newest, now=now, host_boot_time=None, max_wait=WAIT)["proceed"]
    g = recovery.startup_gate(newest, now=now, host_boot_time=None, max_wait=WAIT, blocked_since=since)
    assert (g["state"], g["proceed"], g["recovery_run_id"]) == (recovery.OVERDUE, True, 99)
    # a block reported long ago (the detector was not running) is not continued
    stale = {**prev, "last_run_at": now - WAIT - timedelta(seconds=1)}
    assert recovery.continuing_block(stale, now=now, max_wait=WAIT) is None
    ready = {**prev, "detail": {"startup_recovery": {"state": recovery.READY}}}
    assert recovery.continuing_block(ready, now=now, max_wait=WAIT) is None
    assert recovery.continuing_block(None, now=now, max_wait=WAIT) is None
