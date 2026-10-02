"""BETA_CONTEXT_1H_V2 (1h + 4h windows, taker-delta and OI-change ranks) and the
pure 1h/4h interpretation (PRODUCT_FIRST_DECISION_V1 §3 rows 4-6, §3.1)."""
import asyncio
import copy
import math
from datetime import timedelta
from types import SimpleNamespace

import pytest

from test_beta_context import CFG, DOWN, EXS, T0, _hist, cx, snap, tape

from beta import interpretation as it
from beta.config import LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, PRICE_OI_CONTRACTION_DOWN
from beta.i18n import assert_descriptive
from beta.oi_asof import OiAsofIndex, window_oi_change
from beta.state_tape import BUCKET, metric_key

IDENT = {"feature_schema_version": 1, "calculation_version": "a" * 16,
         "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
TIERS = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}
T = T0 + timedelta(days=31)
N30 = int(timedelta(days=30, hours=4) / BUCKET)      # 30d of samples + one 4h window


def _taker_hist(n, start, taker=1e5):
    return [(b, dict(m, **{"c:taker_delta_notional_usd_sum": taker})) for b, m in _hist(n, start)]


def _ctx(horizon, *, hist, cur, oi_index=None):
    return cx.context_1h(CFG, bucket_ts=T, current_metrics=cur, history=hist, identity=IDENT,
                         code_version="t", tiers=TIERS, oi_index=oi_index, horizon=horizon)


def _oi_rows(start, end, *, exchanges=EXS, step=timedelta(minutes=1), value=lambda ts: 1000.0):
    rows, ts = [], start
    while ts <= end:
        for ex in exchanges:
            rows.append({"exchange": ex, "ts": ts, "oi_raw": value(ts), "oi_unit": "base",
                         "contract_value": None})
        ts += step
    return rows


# ---- 4h window: the same machinery, 48 buckets ------------------------------------------------
def test_4h_window_is_the_rolling_machinery_over_48_buckets():
    assert cx.horizon_buckets(CFG) == {"1h": 12, "4h": 48}
    rows = dict(_taker_hist(48, T0))
    rows[T0] = dict(rows[T0], **{metric_key(ex, "kline_open"): 100.0 for ex in EXS})
    rows[T0 + 47 * BUCKET] = dict(rows[T0 + 47 * BUCKET], **{metric_key(ex, "kline_close"): 101.0 for ex in EXS})
    v = cx.rolling_window_values(CFG, rows, T0 + 47 * BUCKET, 48)
    assert v["window_start"] == cx.iso(T0) and v["window_end"] == cx.iso(T0 + 48 * BUCKET)
    assert math.isclose(v["price_move_pct_median"], 1.0) and math.isclose(v["volume_notional_usd_sum"], 48e6)
    assert math.isclose(v["taker_delta_notional_usd_sum"], 48 * 1e5)
    assert v["price_move_pct_by_venue"] == {ex: pytest.approx(1.0) for ex in EXS}
    # the 1h reading of the same tape is the last 12 buckets only
    assert cx.rolling_1h_values(CFG, rows, T0 + 47 * BUCKET)["window_start"] == cx.iso(T0 + 36 * BUCKET)
    del rows[T0 + 5 * BUCKET]
    assert cx.rolling_window_values(CFG, rows, T0 + 47 * BUCKET, 48) is None
    assert cx.rolling_1h_values(CFG, rows, T0 + 47 * BUCKET) is not None     # 1h does not need it


def test_taker_sum_needs_every_bucket_value():
    rows = dict(_taker_hist(12, T0))
    rows[T0 + 3 * BUCKET] = dict(rows[T0 + 3 * BUCKET], **{"c:taker_delta_notional_usd_sum": None})
    v = cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET)
    assert v["taker_delta_notional_usd_sum"] is None and v["price_move_pct_median"] is not None


def test_4h_ranks_against_30d_of_4h_windows_and_taker_rank():
    hist = _taker_hist(N30, T - N30 * BUCKET)
    cur = dict(hist[-1][1], **{"c:taker_delta_notional_usd_sum": 9e9})
    for h in ("1h", "4h"):
        out = _ctx(h, hist=hist, cur=cur)
        p = out["percentiles"]["taker_delta_notional_usd_sum"]
        assert (out["horizon"], p["tier"], p["rank"], p["sample_size"]) == (h, "mature", 1.0, 8640)
        assert out["percentiles"]["range_width_pct_median"]["tier"] == "mature"


def test_oi_change_rank_from_stage1_asof_and_missing_oi_degrades_only_oi():
    hist = _taker_hist(N30, T - N30 * BUCKET)
    end = T + BUCKET
    # OI flat for 30 days, then falling 2% over the last hour
    def value(ts):
        return 1000.0 if ts <= end - timedelta(hours=1) else 980.0
    idx = OiAsofIndex(_oi_rows(T - N30 * BUCKET - timedelta(minutes=5), end, value=value))
    with_oi = _ctx("1h", hist=hist, cur=hist[-1][1], oi_index=idx)
    assert with_oi["oi_change_pct_median"] == pytest.approx(-2.0)
    assert with_oi["oi_status"] == "OK"
    p = with_oi["percentiles"]["oi_change_pct_median"]
    assert p["tier"] == "mature" and p["rank"] < 0.01
    without = _ctx("1h", hist=hist, cur=hist[-1][1], oi_index=None)
    assert without["oi_change_pct_median"] is None and without["oi_status"] == cx.OI_UNAVAILABLE
    assert without["percentiles"]["oi_change_pct_median"]["rank"] is None
    for m in cx.CONTEXT_METRICS[:4]:                       # nothing else changes
        assert without["percentiles"][m] == with_oi["percentiles"][m]
        assert without[m] == with_oi[m]


def test_oi_from_fewer_than_two_venues_is_not_a_value_and_never_reads_after_the_window():
    end = T0 + timedelta(hours=1)
    idx = OiAsofIndex(_oi_rows(T0 - timedelta(minutes=5), end, exchanges=("binance",)))
    assert window_oi_change(idx, EXS, T0, end, min_venues=2)["oi_change_pct_median"] is None
    late = OiAsofIndex([{"exchange": ex, "ts": end + timedelta(seconds=30), "oi_raw": 5.0, "oi_unit": "base",
                         "contract_value": None} for ex in EXS])
    assert late.at("binance", end) is None


def test_short_history_is_immature_not_missing():
    hist = _taker_hist(int(timedelta(days=5) / BUCKET), T - int(timedelta(days=5) / BUCKET) * BUCKET)
    out = _ctx("4h", hist=hist, cur=hist[-1][1])
    assert out is not None and out["price_move_pct_median"] is not None
    assert all(p["tier"] != "mature" for p in out["percentiles"].values())
    assert it.interpret(CFG, out, horizon="4h")["kind"] == it.INSUFFICIENT_HISTORY


def test_1h_values_and_ranks_unchanged_by_the_4h_extension():
    """The three V1 metrics come out of the shared machinery exactly as before."""
    hist = _hist(int(timedelta(days=30, minutes=55) / BUCKET), T - int(timedelta(days=30, minutes=55) / BUCKET) * BUCKET)
    cur = dict(hist[-1][1], **{metric_key(ex, "kline_high"): 110.0 for ex in EXS})
    out = _ctx("1h", hist=hist, cur=cur)
    p = out["percentiles"]["range_width_pct_median"]
    assert (p["tier"], p["rank"], p["sample_size"]) == ("mature", 1.0, 8640)
    assert out["percentiles"]["volume_notional_usd_sum"]["rank"] == 0.5
    assert out["taker_delta_notional_usd_sum"] is None          # this history has no taker values
    assert out["percentiles"]["taker_delta_notional_usd_sum"]["rank"] is None


def test_rules_digest_is_untouched():
    from test_beta_config import PINNED_RULES_DIGEST
    assert CFG.rules_digest == PINNED_RULES_DIGEST


# ---- interpretation (pure) ----------------------------------------------------------------------
def C(price=0.5, oi=0.5, taker=0.5, rng=0.5, *, tier="mature", venues=None, missing=(), start=T0,
      oi_tier=None):
    """A context reading with the given ranks. `venues` = per-venue price moves."""
    med = (price - 0.5) * 2
    vals = {"price_move_pct_median": med, "oi_change_pct_median": (oi - 0.5) * 4,
            "taker_delta_notional_usd_sum": (taker - 0.5) * 1e7, "range_width_pct_median": rng,
            "volume_notional_usd_sum": 1e9}
    pct = {m: {"rank": {"price_move_pct_median": price, "oi_change_pct_median": oi,
                        "taker_delta_notional_usd_sum": taker, "range_width_pct_median": rng,
                        "volume_notional_usd_sum": 0.5}[m], "tier": tier} for m in vals}
    if oi_tier is not None:
        pct["oi_change_pct_median"]["tier"] = oi_tier
    for m in missing:
        vals[m] = None
        pct[m] = {"rank": None, "tier": None}
    by = venues if venues is not None else {ex: med for ex in EXS}
    return {**vals, "percentiles": pct, "price_move_pct_by_venue": by,
            "window_start": cx.iso(start), "window_end": cx.iso(start + timedelta(hours=1))}


def key(ctx, **kw):
    return it.interpret(CFG, ctx, horizon="1h", **kw)["key"]


@pytest.mark.parametrize("price,oi,taker,label", [
    (0.9, 0.1, 0.9, "short_exit"),
    (0.9, 0.9, 0.9, "long_build"),
    (0.1, 0.9, 0.1, "short_build"),
    (0.1, 0.1, 0.1, "long_exit"),
])
def test_each_inferred_label_needs_price_oi_and_taker(price, oi, taker, label):
    r = it.interpret(CFG, C(price, oi, taker), horizon="1h")
    assert (r["kind"], r["label"], r["key"]) == (it.INTERPRETED, label, label)
    assert it.interpretation_text(r, "ru").startswith("похоже на ")


@pytest.mark.parametrize("price,oi,taker,fallback", [
    (0.9, 0.1, 0.1, "up_oi_down"), (0.9, 0.1, 0.5, "up_oi_down"),
    (0.9, 0.9, 0.1, "up_oi_up"),
    (0.1, 0.9, 0.9, "down_oi_up"),
    (0.1, 0.1, 0.9, "down_oi_down"), (0.1, 0.1, 0.5, "down_oi_down"),
])
def test_conflicting_or_unconfirmed_taker_falls_back_to_facts(price, oi, taker, fallback):
    r = it.interpret(CFG, C(price, oi, taker), horizon="1h")
    assert (r["kind"], r["label"], r["key"]) == (it.FACTUAL, None, fallback)
    assert "похоже" not in it.interpretation_text(r, "ru")


def test_missing_taker_is_factual_pair_only():
    r = it.interpret(CFG, C(0.9, 0.1, missing=("taker_delta_notional_usd_sum",)), horizon="1h")
    assert (r["kind"], r["key"]) == (it.FACTUAL, "up_oi_down")


@pytest.mark.parametrize("oi_case", ["missing", "immature"])
def test_missing_or_immature_oi_keeps_the_price_fact(oi_case):
    ctx = C(0.1, 0.1, 0.1, missing=("oi_change_pct_median",)) if oi_case == "missing" \
        else C(0.1, 0.1, 0.1, oi_tier="building")
    r = it.interpret(CFG, ctx, horizon="4h")
    assert (r["kind"], r["key"]) == (it.FACTUAL, "down_oi_na")
    assert it.interpretation_text(r, "ru") == "снижение, OI н/д"


def test_directional_price_with_flat_oi_is_the_price_fact():
    assert key(C(0.9, 0.5, 0.9)) == "up"
    assert key(C(0.1, 0.5, 0.1)) == "down"


def test_price_agreement_below_two_venues_gives_no_label():
    ctx = C(0.9, 0.1, 0.9, venues={"binance": 0.5, "bybit": -0.2, "okx": -0.1})
    r = it.interpret(CFG, ctx, horizon="1h")
    assert (r["kind"], r["label"], r["key"]) == (it.VENUES_DIVERGE, None, "venues_diverge")
    assert it.interpretation_text(r, "ru") == "биржи расходятся"
    # two of three agreeing is enough; two venues both agreeing is enough
    assert key(C(0.9, 0.1, 0.9, venues={"binance": 0.5, "bybit": 0.2, "okx": -0.1})) == "short_exit"
    assert key(C(0.9, 0.1, 0.9, venues={"binance": 0.5, "bybit": 0.2})) == "short_exit"
    assert key(C(0.9, 0.1, 0.9, venues={"binance": 0.5})) == "venues_diverge"


def test_immature_or_missing_price_never_labels():
    assert it.interpret(CFG, C(0.9, 0.1, 0.9, tier="building"), horizon="1h")["kind"] == it.INSUFFICIENT_HISTORY
    assert it.interpret(CFG, C(missing=("price_move_pct_median",)), horizon="1h")["kind"] == it.DATA_MISSING
    assert it.interpret(CFG, None, horizon="1h")["kind"] == it.DATA_MISSING


def test_compression_normal_and_their_degradation():
    r = it.interpret(CFG, C(0.5, 0.5, 0.5, rng=0.1), horizon="4h")
    assert (r["kind"], r["label"], it.interpretation_text(r, "ru")) == (it.COMPRESSION, "compression", "сжатие")
    assert key(C(0.5, 0.5, 0.5, rng=0.1, missing=("oi_change_pct_median",))) == "compression_oi_na"
    assert key(C(0.5, 0.1, 0.5, rng=0.1)) == "normal"                 # OI in its bottom tail
    r = it.interpret(CFG, C(0.5, 0.5, 0.5, rng=0.5), horizon="1h")
    assert (r["kind"], it.interpretation_text(r, "ru")) == (it.NORMAL, "обычное состояние")
    assert key(C(0.5, 0.5, 0.5, rng=0.1, missing=("range_width_pct_median",))) == "missing"


def _liq_ep(et, opened, last, *, triggered=True):
    return {"episode_id": f"EV-{et[-4:]}", "event_type": et, "opened_bucket": cx.iso(opened),
            "last_bucket": cx.iso(last), "triggered_at": cx.iso(opened + BUCKET) if triggered else None}


def test_flush_only_with_an_overlapping_liquidation_stress_episode_of_the_matching_side():
    short_exit, long_exit = C(0.9, 0.1, 0.9), C(0.1, 0.1, 0.1)
    inside = _liq_ep(LIQUIDATION_STRESS_SHORT, T0 + 2 * BUCKET, T0 + 3 * BUCKET)
    r = it.interpret(CFG, short_exit, horizon="1h", liquidation_episodes=[inside])
    assert (r["label"], r["liquidation_episode"]) == ("short_flush", inside["episode_id"])
    assert it.interpretation_text(r, "ru") == "похоже на вынос шортов"
    # last qualifying bucket [T0-5m, T0) ends exactly at the window start: no overlap
    before = _liq_ep(LIQUIDATION_STRESS_SHORT, T0 - 3 * BUCKET, T0 - BUCKET)
    assert key(short_exit, liquidation_episodes=[before]) == "short_exit"
    edge = _liq_ep(LIQUIDATION_STRESS_SHORT, T0 - 3 * BUCKET, T0)                  # touches the window
    assert key(short_exit, liquidation_episodes=[edge]) == "short_flush"
    wrong_side = _liq_ep(LIQUIDATION_STRESS_LONG, T0 + 2 * BUCKET, T0 + 3 * BUCKET)
    assert key(short_exit, liquidation_episodes=[wrong_side]) == "short_exit"
    assert key(short_exit, liquidation_episodes=[dict(inside, triggered_at=None)]) == "short_exit"
    long_ep = _liq_ep(LIQUIDATION_STRESS_LONG, T0 + 2 * BUCKET, T0 + 2 * BUCKET)
    assert key(long_exit, liquidation_episodes=[long_ep]) == "long_flush"
    # an episode never upgrades a factual fallback or another row
    assert key(C(0.9, 0.1, 0.1), liquidation_episodes=[inside]) == "up_oi_down"
    assert key(C(0.9, 0.9, 0.9), liquidation_episodes=[inside]) == "long_build"


def test_liquidation_episodes_come_from_the_projection_memory():
    state = {"open": {LIQUIDATION_STRESS_SHORT: {"event_type": LIQUIDATION_STRESS_SHORT}},
             "last_ended": {LIQUIDATION_STRESS_LONG: {"event_type": LIQUIDATION_STRESS_LONG},
                            PRICE_OI_CONTRACTION_DOWN: {"event_type": PRICE_OI_CONTRACTION_DOWN}}}
    assert sorted(e["event_type"] for e in it.liquidation_episodes(state)) == sorted(
        [LIQUIDATION_STRESS_SHORT, LIQUIDATION_STRESS_LONG])


def test_24h_has_no_interpretation_label():
    with pytest.raises(ValueError):
        it.interpret(CFG, C(0.9, 0.1, 0.9), horizon="24h")


def test_every_phrase_passes_both_forbidden_lists_and_inferred_ones_hedge():
    for k, cat in it.LABEL_KEYS.items():
        for lang in ("ru", "en"):
            assert_descriptive(it.interpretation_text({"key": k}, lang), lang)
    inferred = ("short_exit", "long_build", "short_build", "long_exit", "short_flush", "long_flush")
    assert all(it.interpretation_text({"key": k}, "ru").startswith("похоже на ") for k in inferred)
    assert all(it.interpretation_text({"key": k}, "en").startswith("looks like ") for k in inferred)


def test_interpretation_reads_only_the_window_it_is_given():
    ctx = C(0.9, 0.1, 0.9)
    before = copy.deepcopy(ctx)
    it.interpret(CFG, ctx, horizon="1h")
    assert ctx == before


# ---- version change does not reset the projection --------------------------------------------
class _Conn:
    def __init__(self, snapshots):
        self.snapshots = snapshots          # context_digest -> snapshot
        self.inserted = []

    async def fetch_latest_context_snapshot(self, *, context_digest, **_kw):
        return self.snapshots.get(context_digest)

    async def fetch_tape_history(self, **_kw):
        return []

    async def fetch_open_interest_range(self, **_kw):
        raise RuntimeError("Stage-1 OI read failed")

    async def insert_context_snapshot(self, state, **kw):
        self.inserted.append((state, kw))


def _v1_state(states):
    s = copy.deepcopy(states[-1])
    s.pop("context_4h", None)
    s.update(context_version="BETA_CONTEXT_1H_V1",
             context_digest=cx.KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V1"])
    return s


def test_new_context_label_keeps_open_episodes_instead_of_restarting_empty():
    from beta.detector import advance_context
    snaps = [snap(DOWN), snap(DOWN), snap(DOWN)]
    rows = tape(snaps)
    states = cx.replay(CFG, {b: r for b, r in rows.items() if b < T0 + 2 * BUCKET},
                       start_bucket=T0, end_bucket=T0 + BUCKET)
    assert PRICE_OI_CONTRACTION_DOWN in states[-1]["open"]
    old = {"bucket_ts": T0 + BUCKET, "state": _v1_state(states), "state_digest": "f" * 64}
    conn = _Conn({cx.KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V1"]: old})
    third = rows[T0 + 2 * BUCKET]
    third["snapshot"]["feature_code_version"] = "t"
    rec = SimpleNamespace(snapshot=third["snapshot"], snapshot_digest=third["snapshot_digest"])
    deps = SimpleNamespace(stage2_config=SimpleNamespace(
        resolve=lambda _s: {"percentiles": {"confidence_tiers": TIERS}}))
    state = asyncio.run(advance_context(deps, CFG, conn, T0 + 2 * BUCKET, rec, 3))
    assert PRICE_OI_CONTRACTION_DOWN in state["open"]                       # not restarted empty
    assert state["context_version"] == "BETA_CONTEXT_1H_V2"
    assert state["context_digest"] == cx.KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V2"]
    assert conn.inserted[-1][1]["prev_state_digest"] == "f" * 64
    # the same as a projection that never changed version
    reference = cx.replay(CFG, rows, start_bucket=T0, end_bucket=T0 + 2 * BUCKET)[-1]
    assert state["open"] == reference["open"]


def test_without_a_predecessor_snapshot_the_projection_starts_empty_as_before():
    from beta.detector import advance_context
    rows = tape([snap(DOWN)])
    row = rows[T0]
    row["snapshot"]["feature_code_version"] = "t"
    rec = SimpleNamespace(snapshot=row["snapshot"], snapshot_digest=row["snapshot_digest"])
    deps = SimpleNamespace(stage2_config=SimpleNamespace(
        resolve=lambda _s: {"percentiles": {"confidence_tiers": TIERS}}))
    state = asyncio.run(advance_context(deps, CFG, _Conn({}), T0, rec, 1))
    assert state["as_of_bucket"] == cx.iso(T0) and PRICE_OI_CONTRACTION_DOWN in state["open"]


def test_adoption_refuses_a_state_that_is_not_a_declared_predecessor():
    states, _ = (cx.replay(CFG, tape([snap(DOWN)]), start_bucket=T0, end_bucket=T0), None)
    s = _v1_state(states)
    adopted = cx.adopt_predecessor_state(CFG, s)
    assert adopted["context_4h"] is None and adopted["context_1h"] is None
    assert adopted["open"] == s["open"]
    with pytest.raises(cx.ContextVersionError):
        cx.adopt_predecessor_state(CFG, dict(s, context_version="BETA_CONTEXT_1H_V0"))
    with pytest.raises(cx.ContextVersionError):
        cx.adopt_predecessor_state(CFG, dict(s, episodization_digest="0" * 64))
