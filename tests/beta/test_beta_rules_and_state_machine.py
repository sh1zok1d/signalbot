"""BETA_EVENT_RULES_V1 evaluation + episode state machine + push policy (pure)."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig, EVENT_TYPES
from beta.detector import BucketContext, lifecycle, plan_buckets, public_episode_id, push_policy, step_episode
from beta.models import (ARMED, DAILY_CAP, DATA_DEGRADED_REASON, DELIVERY_TOO_OLD, EARLY, ENDED, EXPIRED,
                         NOT_EVALUABLE, NOT_QUALIFIES, PUSH, PUSH_DISABLED, QUALIFIES,
                         SAME_EVENT_COOLDOWN, SUPPRESSED, TRIGGERED)
from beta.rules import evaluate_bucket

CFG = BetaConfig.load().with_overrides(enabled=True)
T = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAMS = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")


def _p(rank, tier="mature", value=1.0):
    return {"value": value, "rank": rank, "tier": tier, "sample_size": 100}


def snap(ranks=None, *, fresh=True, families_ok=FAMS, venues=None, liq=None):
    ranks = dict(ranks or {})
    pct = {f"c:{k}": _p(v) if not isinstance(v, dict) else v for k, v in ranks.items()}
    for k in ("price_move_pct_median", "oi_change_pct_median", "range_width_pct_median",
              "volume_notional_usd_sum", "taker_delta_notional_usd_sum"):
        pct.setdefault(f"c:{k}", _p(0.5))
    for ex in ("binance", "bybit", "okx"):
        for side in ("long", "short"):
            pct[f"x:{ex}:{side}_liquidation_notional"] = (liq or {}).get((ex, side), _p(0.5))
    v = venues or {ex: {"declared_available": True, "heartbeat_healthy": True} for ex in ("binance", "bybit", "okx")}
    return {"materialized": True, "stale_barrier": False, "evaluation_fresh": fresh, "percentiles": pct,
            "families": {f: {"usable": f in families_ok} for f in FAMS}, "venues": v}


DOWN = {"price_move_pct_median": 0.02, "oi_change_pct_median": 0.05}
UP = {"price_move_pct_median": 0.97, "oi_change_pct_median": 0.05}
BUILD = {"range_width_pct_median": 0.2, "oi_change_pct_median": 0.9, "volume_notional_usd_sum": 0.7}


def test_core_rules_qualify_and_mirror():
    ev = evaluate_bucket(CFG, snap(DOWN), None)
    assert ev["PRICE_OI_CONTRACTION_DOWN"]["status"] == QUALIFIES
    assert ev["PRICE_OI_CONTRACTION_UP"]["status"] == NOT_QUALIFIES
    assert evaluate_bucket(CFG, snap(UP), None)["PRICE_OI_CONTRACTION_UP"]["status"] == QUALIFIES
    assert evaluate_bucket(CFG, snap(BUILD), None)["POSITION_BUILDUP_COMPRESSION"]["status"] == QUALIFIES


@pytest.mark.parametrize("edge,expected", [(0.05, QUALIFIES), (0.0500001, NOT_QUALIFIES)])
def test_threshold_boundaries_inclusive(edge, expected):
    ev = evaluate_bucket(CFG, snap({"price_move_pct_median": edge, "oi_change_pct_median": 0.10}), None)
    assert ev["PRICE_OI_CONTRACTION_DOWN"]["status"] == expected


def test_immature_percentile_is_not_evaluable_not_inactive():
    s = snap({"price_move_pct_median": _p(0.01, tier="building"), "oi_change_pct_median": 0.01})
    ev = evaluate_bucket(CFG, s, None)["PRICE_OI_CONTRACTION_DOWN"]
    assert ev["status"] == NOT_EVALUABLE and "NOT_MATURE" in ev["reason"]
    s = snap({"taker_delta_notional_usd_sum": _p(0.99, tier="low")})
    assert evaluate_bucket(CFG, s, None)["TAKER_FLOW_EXTREME_BUY"]["status"] == NOT_EVALUABLE


@pytest.mark.parametrize("missing,event", [("oi", "PRICE_OI_CONTRACTION_DOWN"),
                                           ("price_structure", "PRICE_OI_CONTRACTION_DOWN"),
                                           ("volume", "POSITION_BUILDUP_COMPRESSION"),
                                           ("taker_flow", "TAKER_FLOW_EXTREME_BUY")])
def test_per_family_fail_closed_requires_two_venues(missing, event):
    s = snap({**DOWN, **BUILD, "taker_delta_notional_usd_sum": 0.99},
             families_ok=[f for f in FAMS if f != missing])
    ev = evaluate_bucket(CFG, s, None)[event]
    assert ev["status"] == NOT_EVALUABLE and ev["reason"] == f"FAMILY_UNUSABLE:{missing}"


def test_not_fresh_evaluation_is_not_evaluable():
    ev = evaluate_bucket(CFG, snap(DOWN, fresh=False), None)
    assert all(v["status"] == NOT_EVALUABLE for v in ev.values())


def test_liquidation_stress_votes_and_not_evaluable_paths():
    hi = _p(0.99)
    s = snap(liq={("binance", "long"): hi, ("okx", "long"): hi})
    assert evaluate_bucket(CFG, s, None)["LIQUIDATION_STRESS_LONG"]["status"] == QUALIFIES
    assert evaluate_bucket(CFG, s, None)["LIQUIDATION_STRESS_SHORT"]["status"] == NOT_QUALIFIES
    # one venue extreme cannot trigger a 2-venue event
    s1 = snap(liq={("binance", "long"): hi})
    assert evaluate_bucket(CFG, s1, None)["LIQUIDATION_STRESS_LONG"]["status"] == NOT_QUALIFIES
    # only one eligible venue -> NOT_EVALUABLE
    venues = {"binance": {"declared_available": True, "heartbeat_healthy": True},
              "bybit": {"declared_available": False, "heartbeat_healthy": True},
              "okx": {"declared_available": True, "heartbeat_healthy": False}}
    ev = evaluate_bucket(CFG, snap(venues=venues, liq={("binance", "long"): hi}), None)["LIQUIDATION_STRESS_LONG"]
    assert ev["status"] == NOT_EVALUABLE and ev["detail"]["ineligible"]["okx"] == "HEARTBEAT_UNHEALTHY"
    # immature / unmeasured venues are not eligible
    s2 = snap(liq={("binance", "long"): _p(0.99, tier="building"), ("bybit", "long"): _p(None, value=None)})
    assert evaluate_bucket(CFG, s2, None)["LIQUIDATION_STRESS_LONG"]["status"] == NOT_EVALUABLE


def test_measured_zero_counts_as_eligible():
    zero = {"value": 0.0, "rank": 0.5, "tier": "mature", "sample_size": 100}
    s = snap(liq={(ex, "long"): zero for ex in ("binance", "bybit", "okx")})
    ev = evaluate_bucket(CFG, s, None)["LIQUIDATION_STRESS_LONG"]
    assert ev["status"] == NOT_QUALIFIES and len(ev["detail"]["eligible"]) == 3


def test_streaks_chain_and_reset():
    ev1 = evaluate_bucket(CFG, snap(DOWN), None)
    ev2 = evaluate_bucket(CFG, snap(DOWN), ev1)
    assert ev2["PRICE_OI_CONTRACTION_DOWN"]["streak"] == 2
    ev3 = evaluate_bucket(CFG, snap(), ev2)
    assert ev3["PRICE_OI_CONTRACTION_DOWN"]["streak"] == 0


# ---- state machine -------------------------------------------------------------------
class Sim:
    """Drive step_episode over a sequence of statuses for one event type."""
    def __init__(self, et, cfg=CFG):
        self.et, self.cfg, self.ep, self.streak, self.b, self.log, self.n = et, cfg, None, 0, T, [], 0

    def feed(self, status, calc="0" * 16):
        self.streak = self.streak + 1 if status == QUALIFIES else 0
        ctx = BucketContext(bucket_ts=self.b, decision_ts=self.b + timedelta(minutes=5),
                            snapshot_digest=f"{self.n:064x}", calculation_version=calc,
                            reference={"status": "OK", "price": 100.0, "exchanges": ["binance", "okx"],
                                       "dispersion_pct": 0.1}, code_version="c")
        st = step_episode(self.cfg, self.et, self.ep, {"status": status, "streak": self.streak}, ctx)
        self.log.append([(t[1], t[2], t[3]) for t in st.transitions])
        if st.terminated is not None:
            self.ep = None
        if st.updated is not None:
            self.ep = st.updated
        if st.opened is not None:
            self.ep = st.opened.__class__(**{**st.opened.__dict__, "episode_pk": 1})
        self.b += timedelta(minutes=5)
        self.n += 1
        return st


def test_price_oi_armed_triggered_ended():
    s = Sim("PRICE_OI_CONTRACTION_DOWN")
    assert s.feed(QUALIFIES).opened.state == ARMED
    st = s.feed(QUALIFIES)
    assert st.updated.state == TRIGGERED and st.triggered == "updated" and st.updated.reference_price == 100.0
    s.feed(QUALIFIES)
    st = s.feed(NOT_QUALIFIES)
    assert st.terminated.state == ENDED and st.terminated.terminal_reason == "CONDITION_FAILED"


def test_price_oi_armed_expired():
    s = Sim("PRICE_OI_CONTRACTION_UP")
    s.feed(QUALIFIES)
    st = s.feed(NOT_QUALIFIES)
    assert st.terminated.state == EXPIRED and st.terminated.triggered_at is None


def test_buildup_early_armed_triggered_and_expired():
    s = Sim("POSITION_BUILDUP_COMPRESSION")
    states = []
    for i in range(10):
        st = s.feed(QUALIFIES)
        states.append(s.ep.state if s.ep else None)
    assert states[:2] == [None, None] and states[2] == EARLY and states[5] == ARMED and states[8] == TRIGGERED
    s2 = Sim("POSITION_BUILDUP_COMPRESSION")
    for _ in range(4):
        s2.feed(QUALIFIES)
    st = s2.feed(NOT_QUALIFIES)
    assert st.terminated.state == EXPIRED


def test_buildup_max_duration_and_no_immediate_reopen():
    s = Sim("POSITION_BUILDUP_COMPRESSION")
    for _ in range(3):
        s.feed(QUALIFIES)
    opened = s.ep.opened_at
    reason = None
    for _ in range(40):
        st = s.feed(QUALIFIES)
        if st.terminated is not None:
            reason = st.terminated.terminal_reason
            assert st.terminated.state == ENDED and st.terminated.terminal_at - opened >= timedelta(minutes=180)
            assert st.opened is None
            break
    assert reason == "MAX_DURATION"
    assert s.feed(QUALIFIES).opened is None          # streak must break before a new episode


def test_not_evaluable_terminalizes_open_episode():
    s = Sim("PRICE_OI_CONTRACTION_DOWN")
    s.feed(QUALIFIES)
    s.feed(QUALIFIES)
    st = s.feed(NOT_EVALUABLE)
    assert st.terminated.state == ENDED and st.terminated.terminal_reason == "NOT_EVALUABLE"


def test_liquidation_opens_directly_triggered():
    s = Sim("LIQUIDATION_STRESS_SHORT")
    st = s.feed(QUALIFIES)
    assert st.opened.state == TRIGGERED and st.triggered == "opened" and st.opened.armed_at is None


def test_version_change_terminalizes_and_gap_terminalizes():
    s = Sim("PRICE_OI_CONTRACTION_DOWN")
    s.feed(QUALIFIES)
    s.feed(QUALIFIES)
    s.cfg = CFG.with_overrides(max_state_age_s=421)         # new rules digest
    st = s.feed(QUALIFIES)
    assert st.terminated.terminal_reason == "DETECTOR_VERSION_CHANGED" and st.terminated.state == ENDED
    s2 = Sim("PRICE_OI_CONTRACTION_DOWN")
    s2.feed(QUALIFIES)
    s2.b += timedelta(minutes=5)                            # a skipped bucket
    st = s2.feed(QUALIFIES)
    assert st.terminated.terminal_reason == "DETECTION_GAP"
    s3 = Sim("PRICE_OI_CONTRACTION_DOWN")
    s3.feed(QUALIFIES)
    st = s3.feed(QUALIFIES, calc="1" * 16)                  # Stage-2 calculation_version fork
    assert st.terminated.terminal_reason == "DETECTOR_VERSION_CHANGED"


def test_public_id_is_deterministic_and_well_formed():
    a = public_episode_id("BTCUSDT", "PRICE_OI_CONTRACTION_DOWN", T, "a" * 64)
    assert a == public_episode_id("BTCUSDT", "PRICE_OI_CONTRACTION_DOWN", T, "a" * 64)
    assert a.startswith("EV-") and len(a) == 13 and a != public_episode_id("BTCUSDT", "PRICE_OI_CONTRACTION_UP", T, "a" * 64)


def test_every_event_type_has_a_lifecycle():
    for et in EVENT_TYPES:
        lc = lifecycle(CFG, et)
        assert lc.entry_streak <= lc.triggered_at


# ---- push policy -----------------------------------------------------------------------
PT = T + timedelta(hours=12)        # 14:00 Kyiv: outside the quiet hours


def _pp(**kw):
    base = dict(decision_ts=PT, evaluated_at=PT + timedelta(seconds=30), snapshot=snap(),
                last_same_type_terminal=None, last_same_type_would_push=None, would_push_today=0,
                push_enabled=True, hour={"qualified": True}, last_any_would_push=None)
    base.update(kw)
    return push_policy(CFG, **base)


def test_push_policy_order_and_reasons():
    from beta.models import GLOBAL_COOLDOWN, HOUR_NOT_UNUSUAL, QUIET_HOURS
    assert _pp() == (True, PUSH, None)
    assert _pp(push_enabled=False) == (True, SUPPRESSED, PUSH_DISABLED)
    assert _pp(would_push_today=2) == (False, SUPPRESSED, DAILY_CAP)
    assert _pp(hour=None) == (False, SUPPRESSED, HOUR_NOT_UNUSUAL)
    assert _pp(hour={"qualified": False}) == (False, SUPPRESSED, HOUR_NOT_UNUSUAL)
    assert _pp(last_any_would_push=PT - timedelta(minutes=59)) == (False, SUPPRESSED, GLOBAL_COOLDOWN)
    assert _pp(last_any_would_push=PT - timedelta(minutes=60)) == (True, PUSH, None)
    night = datetime(2026, 3, 1, 21, 30, tzinfo=timezone.utc)   # 23:30 Kyiv (EET)
    assert _pp(decision_ts=night, evaluated_at=night + timedelta(seconds=30)) == (False, SUPPRESSED, QUIET_HOURS)
    # the gate is evaluated before every delivery-side reason, so those imply a qualified hour
    assert _pp(hour=None, would_push_today=2)[2] == HOUR_NOT_UNUSUAL
    assert _pp(last_same_type_terminal=PT - timedelta(minutes=19)) == (False, SUPPRESSED, SAME_EVENT_COOLDOWN)
    assert _pp(last_same_type_terminal=PT - timedelta(minutes=20)) == (True, PUSH, None)
    assert _pp(last_same_type_would_push=PT - timedelta(minutes=5))[2] == SAME_EVENT_COOLDOWN
    assert _pp(evaluated_at=PT + timedelta(seconds=601)) == (False, SUPPRESSED, DELIVERY_TOO_OLD)
    assert _pp(snapshot=snap(fresh=False)) == (False, SUPPRESSED, DATA_DEGRADED_REASON)
    assert _pp(snapshot=snap(families_ok=("price_structure", "oi"))) == (False, SUPPRESSED, DATA_DEGRADED_REASON)


def test_plan_buckets_bounded_catchup():
    assert plan_buckets(None, T, 12) == ([T], 0)
    assert plan_buckets(T, T, 12) == ([], 0)
    b, skipped = plan_buckets(T - timedelta(hours=2), T, 12)
    assert skipped == 12 and len(b) == 12 and b[-1] == T
