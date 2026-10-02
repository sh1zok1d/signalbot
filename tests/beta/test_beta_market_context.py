"""Shared 1h/4h market context (BETA_CONTEXT_1H_V2) and its pure interpretation.

PRODUCT_FIRST_DECISION_V1 §3 rows 4-6, §3.1, §3.1b. Offline: no DB, no forward data,
no detector change, no delivery."""
import ast
import copy
import dataclasses
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta import context as cx
from beta import interpretation as it
from beta.config import BetaConfig
from beta.state_tape import BUCKET, metric_key

CFG = BetaConfig.load()
EXS = CFG.exchanges
T = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
IDENT = {"feature_schema_version": 1, "calculation_version": "a" * 16,
         "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
# Short maturity spans keep the offline fixtures small; the live tiers come from Stage-2 config.
TIERS = {"none_below_days": 1, "low_below_days": 2, "building_below_days": 3}
CUTS = it.cuts_from_config(CFG)
REPO = Path(__file__).resolve().parents[2]


def bucket_metrics(price_open=100.0, price_close=100.0, hi=None, lo=None, vol=1e6, taker=0.0, venues=EXS):
    hi = max(price_open, price_close) + 0.5 if hi is None else hi
    lo = min(price_open, price_close) - 0.5 if lo is None else lo
    m = {"c:volume_notional_usd_sum": vol, "c:taker_delta_notional_usd_sum": taker}
    for ex in venues:
        m.update({metric_key(ex, "kline_open"): price_open, metric_key(ex, "kline_high"): hi,
                  metric_key(ex, "kline_low"): lo, metric_key(ex, "kline_close"): price_close})
    return m


def calm_history(days: float, end: datetime):
    """Flat price, varying taker delta, buckets strictly before `end`."""
    n = int(timedelta(days=days) / BUCKET)
    return [(end - (n - i) * BUCKET, bucket_metrics(taker=((i % 7) - 3) * 1e5)) for i in range(n)]


def oi_rows(days: float, end: datetime, *, venues=EXS, jump_at=None, jump=0.0):
    """One Stage-1 row per venue at every 5m boundary; small oscillation, optional jump."""
    n = int(timedelta(days=days) / BUCKET) + 2
    out = {ex: [] for ex in venues}
    for i in range(n):
        ts = end - (n - 1 - i) * BUCKET
        v = 1e9 * (1 + 0.0001 * ((i % 5) - 2))
        if jump_at is not None and ts >= jump_at:
            v *= 1 + jump
        for ex in venues:
            out[ex].append({"ts": ts, "oi_raw": v, "oi_unit": "contracts", "contract_value": 1.0})
    return out


def run(history, current, oi, *, bucket_ts=T):
    return cx.market_context(CFG, bucket_ts=bucket_ts, current_metrics=current, history=history,
                             oi_rows_by_venue=oi, identity=IDENT, code_version="t", tiers=TIERS)


def with_window(history, end_bucket, n, fn):
    """Replace the last n-1 history buckets before `end_bucket` via fn(index, metrics)."""
    rows = dict(history)
    for k in range(1, n):
        b = end_bucket - k * BUCKET
        rows[b] = fn(n - 1 - k, rows[b])
    return sorted(rows.items())


# ---- rolling windows -------------------------------------------------------------------------------
def test_4h_window_is_48_raw_buckets_with_full_sums():
    rows = {T - i * BUCKET: bucket_metrics(vol=2e6, taker=-1e5) for i in range(48)}
    rows[T - 47 * BUCKET] = bucket_metrics(price_open=100.0, price_close=100.0, vol=2e6, taker=-1e5)
    rows[T] = bucket_metrics(price_open=101.0, price_close=102.0, hi=103.0, vol=2e6, taker=-1e5)
    v = cx.rolling_window_values(CFG, rows, T, 48)
    assert math.isclose(v["price_move_pct_median"], 2.0)
    assert math.isclose(v["range_width_pct_median"], (103.0 - 99.5) / 100.0 * 100)
    assert math.isclose(v["volume_notional_usd_sum"], 96e6)
    assert math.isclose(v["taker_delta_notional_usd_sum"], -4.8e6)        # USD notional, summed as stored
    assert v["window_start"] == cx.iso(T - 47 * BUCKET) and v["window_end"] == cx.iso(T + BUCKET)
    assert set(v["venue_price_move_pct"]) == set(EXS)
    del rows[T - 20 * BUCKET]
    assert cx.rolling_window_values(CFG, rows, T, 48) is None                 # 47 of 48 buckets


def test_partial_taker_sum_is_not_a_value():
    rows = {T - i * BUCKET: bucket_metrics(taker=1e5) for i in range(48)}
    rows[T - 3 * BUCKET] = {k: v for k, v in rows[T - 3 * BUCKET].items() if k != "c:taker_delta_notional_usd_sum"}
    v = cx.rolling_window_values(CFG, rows, T, 48)
    assert v["taker_delta_notional_usd_sum"] is None and v["volume_notional_usd_sum"] is not None
    assert v["price_move_pct_median"] is not None


def test_rolling_1h_values_keeps_the_v1_shape():
    rows = {T - i * BUCKET: bucket_metrics() for i in range(12)}
    v = cx.rolling_1h_values(CFG, rows, T)
    assert set(v) == {"window_start", "window_end", "range_width_pct_median", "price_move_pct_median",
                      "volume_notional_usd_sum", "venues"}
    g = cx.rolling_window_values(CFG, rows, T, 12)
    assert all(v[k] == g[k] for k in v)


# ---- versions --------------------------------------------------------------------------------------
def test_live_config_stays_on_v1_and_v2_is_pinned():
    assert cx.verify_versions(CFG)["context_version"] == "BETA_CONTEXT_1H_V1"
    assert cx.verify_market_context_version(CFG) == cx.KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V2"]
    v2 = CFG.with_overrides(context={**CFG.section("context"), "version": "BETA_CONTEXT_1H_V2"})
    assert cx.verify_versions(v2)["context_digest"] == cx.KNOWN_CONTEXT_DIGESTS["BETA_CONTEXT_1H_V2"]
    assert cx.context_payload(v2)["horizons"] == {"1h": 12, "4h": 48}


def test_v2_parameter_change_without_new_label_fails():
    changed = CFG.with_overrides(context={**CFG.section("context"), "tail_display_max": 0.25})
    with pytest.raises(cx.ContextVersionError):
        cx.verify_market_context_version(changed)
    with pytest.raises(cx.ContextVersionError):
        cx.market_context(changed, bucket_ts=T, current_metrics=bucket_metrics(), history=calm_history(1, T),
                          oi_rows_by_venue={}, identity=IDENT, code_version="t", tiers=TIERS)


# ---- ranks, maturity, missing data -------------------------------------------------------------------
def test_4h_unavailable_until_48_buckets_but_1h_available():
    hist = calm_history(46 * 5 / 1440, T)                          # 46 buckets before T
    out = run(hist, bucket_metrics(), oi_rows(1, T + BUCKET))
    assert out["4h"] is None and out["1h"] is not None
    out = run(calm_history(47 * 5 / 1440, T), bucket_metrics(), oi_rows(1, T + BUCKET))
    assert out["4h"] is not None and out["4h"]["buckets"] == 48


def test_short_history_is_not_mature_and_interprets_as_insufficient_history():
    hist = calm_history(1.5, T)
    cur = bucket_metrics(price_open=100.0, price_close=103.0)
    out = run(hist, cur, oi_rows(1.5, T + BUCKET))
    p = out["1h"]["percentiles"]["price_move_pct_median"]
    assert p["tier"] in ("low", "building") and p["rank"] is not None
    assert it.interpret(out["1h"], horizon="1h", cuts=CUTS).state == it.INSUFFICIENT_HISTORY


def test_strong_rise_ranks_at_the_top_and_strong_drop_at_the_bottom():
    hist = calm_history(4, T)
    rise = with_window(hist, T, 12, lambda i, m: bucket_metrics(price_open=100.0, price_close=100.0))
    up = run(rise, bucket_metrics(price_open=101.0, price_close=103.0), oi_rows(4, T + BUCKET))
    down = run(rise, bucket_metrics(price_open=99.0, price_close=97.0), oi_rows(4, T + BUCKET))
    pu, pd = (x["1h"]["percentiles"]["price_move_pct_median"] for x in (up, down))
    assert pu["tier"] == pd["tier"] == "mature"
    assert pu["rank"] == 1.0 and pd["rank"] == 0.0
    assert up["1h"]["price_move_pct_median"] > 0 > down["1h"]["price_move_pct_median"]


def test_taker_delta_ranks_keep_usd_notional_units():
    hist = calm_history(4, T)
    hist = with_window(hist, T, 12, lambda i, m: bucket_metrics(taker=-5e7))
    out = run(hist, bucket_metrics(taker=-5e7), oi_rows(4, T + BUCKET))
    h = out["1h"]
    assert math.isclose(h["taker_delta_notional_usd_sum"], -6e8)
    assert h["percentiles"]["taker_delta_notional_usd_sum"]["rank"] < 0.01
    assert out["4h"]["percentiles"]["taker_delta_notional_usd_sum"]["tier"] == "mature"


def test_oi_ranks_use_stage1_asof_change_between_window_boundaries():
    hist = calm_history(4, T)
    oi = oi_rows(4, T + BUCKET, jump_at=T + BUCKET, jump=0.05)    # +5% at the decision boundary
    out = run(hist, bucket_metrics(), oi)
    h = out["1h"]
    assert h["oi_change_pct_median"] > 4.5
    assert set(h["venue_oi_change_pct"]) == set(EXS)
    p = h["percentiles"]["oi_change_pct_median"]
    assert p["rank"] == 1.0 and p["tier"] == "mature"


def test_oi_from_one_venue_is_not_an_aggregate():
    out = run(calm_history(4, T), bucket_metrics(), oi_rows(4, T + BUCKET, venues=EXS[:1]))
    assert out["1h"]["oi_change_pct_median"] is None
    assert out["1h"]["percentiles"]["oi_change_pct_median"]["rank"] is None


def test_oi_rows_after_the_decision_boundary_are_never_read():
    hist = calm_history(4, T)
    base = oi_rows(4, T + BUCKET)
    future = copy.deepcopy(base)
    for ex in EXS:
        future[ex].append({"ts": T + BUCKET + timedelta(seconds=30), "oi_raw": 9e9,
                           "oi_unit": "contracts", "contract_value": 1.0})
    assert run(hist, bucket_metrics(), base) == run(hist, bucket_metrics(), future)


def test_history_after_bucket_ts_is_ignored():
    hist = calm_history(4, T)
    later = hist + [(T + BUCKET, bucket_metrics(price_close=150.0, taker=-9e9))]
    assert run(hist, bucket_metrics(), oi_rows(4, T + BUCKET)) == run(later, bucket_metrics(),
                                                                       oi_rows(4, T + BUCKET))


def test_market_context_does_not_mutate_inputs():
    hist = calm_history(4, T)
    oi = oi_rows(4, T + BUCKET)
    cur = bucket_metrics()
    h0, o0, c0 = copy.deepcopy(hist), copy.deepcopy(oi), copy.deepcopy(cur)
    run(hist, cur, oi)
    assert (hist, oi, cur) == (h0, o0, c0)


# ---- interpretation ---------------------------------------------------------------------------------
def horizon(price=0.5, oi=0.5, taker=0.5, rng=0.5, *, tier="mature", venue_moves=None,
            oi_value=1.0, taker_value=1.0, price_value=None):
    pv = price_value if price_value is not None else (price - 0.5) * 4
    moves = venue_moves if venue_moves is not None else {ex: pv for ex in EXS}
    return {"price_move_pct_median": pv, "range_width_pct_median": 1.0,
            "oi_change_pct_median": oi_value, "taker_delta_notional_usd_sum": taker_value,
            "venue_price_move_pct": moves,
            "percentiles": {"price_move_pct_median": {"rank": price, "tier": tier},
                            "range_width_pct_median": {"rank": rng, "tier": tier},
                            "oi_change_pct_median": {"rank": oi if oi_value is not None else None,
                                                     "tier": tier if oi_value is not None else "none"},
                            "taker_delta_notional_usd_sum": {"rank": taker if taker_value is not None else None,
                                                             "tier": tier if taker_value is not None else "none"}}}


def state(h, **kw):
    return it.interpret(h, horizon="1h", cuts=CUTS, **kw).state


@pytest.mark.parametrize("price,oi,taker,expected", [
    (0.90, 0.10, 0.90, it.SHORT_EXIT),
    (0.90, 0.90, 0.90, it.LONG_BUILDUP),
    (0.10, 0.90, 0.10, it.SHORT_BUILDUP),
    (0.10, 0.10, 0.10, it.LONG_EXIT),
    # taker does not confirm -> the factual pair of §3.1
    (0.90, 0.10, 0.10, it.RISE_OI_DOWN),
    (0.90, 0.90, 0.50, it.RISE_OI_UP),
    (0.10, 0.90, 0.90, it.DROP_OI_UP),
    (0.10, 0.10, 0.50, it.DROP_OI_DOWN),
    # boundaries are inclusive: up >= 0.80, down <= 0.20
    (0.80, 0.20, 0.80, it.SHORT_EXIT),
    (0.20, 0.80, 0.20, it.SHORT_BUILDUP),
])
def test_interpretation_table(price, oi, taker, expected):
    s = state(horizon(price, oi, taker))
    assert s == expected
    assert (s in it.INFERRED_STATES) == it.interpret(horizon(price, oi, taker), horizon="1h",
                                                     cuts=CUTS).inferred


def test_strong_rise_and_strong_drop_map_by_direction():
    rise = it.interpret(horizon(0.99, 0.95, 0.97), horizon="4h", cuts=CUTS)
    drop = it.interpret(horizon(0.01, 0.95, 0.03), horizon="4h", cuts=CUTS)
    assert (rise.price, rise.state, rise.horizon) == (it.UP, it.LONG_BUILDUP, "4h")
    assert (drop.price, drop.state) == (it.DOWN, it.SHORT_BUILDUP)


def test_wipeout_needs_the_matching_row_and_an_existing_liquidation_episode():
    assert state(horizon(0.1, 0.1, 0.1), liquidation_stress_long=True) == it.LONG_WIPEOUT
    assert state(horizon(0.9, 0.1, 0.9), liquidation_stress_short=True) == it.SHORT_WIPEOUT
    assert state(horizon(0.1, 0.1, 0.1)) == it.LONG_EXIT                      # no episode -> exit row
    assert state(horizon(0.1, 0.1, 0.1), liquidation_stress_short=True) == it.LONG_EXIT
    assert state(horizon(0.9, 0.9, 0.9), liquidation_stress_short=True) == it.LONG_BUILDUP
    w = it.interpret(horizon(0.1, 0.1, 0.1), horizon="1h", cuts=CUTS, liquidation_stress_long=True)
    assert w.inferred and w.liquidation_confirmed


def test_compression_is_range_rank_at_most_020_and_oi_rank_above_020():
    assert state(horizon(0.5, 0.5, 0.5, rng=0.20)) == it.COMPRESSION
    assert state(horizon(0.5, 0.21, 0.5, rng=0.05)) == it.COMPRESSION
    assert state(horizon(0.5, 0.20, 0.5, rng=0.05)) == it.NORMAL               # OI in the down band
    assert state(horizon(0.5, 0.5, 0.5, rng=0.21)) == it.NORMAL
    assert state(horizon(0.5, 0.5, 0.5, rng=0.05, oi_value=None)) == it.COMPRESSION_OI_NA
    assert not it.interpret(horizon(0.5, 0.5, 0.5, rng=0.1), horizon="1h", cuts=CUTS).inferred


def test_missing_oi_or_taker_gives_facts_only_for_a_directional_move():
    f = it.interpret(horizon(0.95, taker_value=None), horizon="1h", cuts=CUTS)
    assert (f.state, f.price, f.taker, f.missing) == (it.FACTS_ONLY, it.UP, None, ("taker",))
    g = it.interpret(horizon(0.05, oi_value=None), horizon="1h", cuts=CUTS)
    assert (g.state, g.oi, g.missing) == (it.FACTS_ONLY, None, ("oi",))
    assert state(horizon(0.5, oi_value=None, taker_value=None)) == it.NORMAL


def test_venue_disagreement_and_incomplete_data():
    split = {EXS[0]: 0.3, EXS[1]: -0.2, EXS[2]: 0.0}
    assert state(horizon(0.9, 0.9, 0.9, venue_moves=split, price_value=0.0)) == it.VENUES_DIVERGE
    assert state(horizon(0.9, 0.9, 0.9, venue_moves={EXS[0]: 1.0, EXS[1]: -1.0}, price_value=0.5)) \
        == it.VENUES_DIVERGE
    assert state(None) == it.DATA_INCOMPLETE
    assert state({**horizon(), "price_move_pct_median": None}) == it.DATA_INCOMPLETE


def test_immature_rank_means_insufficient_history():
    assert state(horizon(0.95, 0.95, 0.95, tier="building")) == it.INSUFFICIENT_HISTORY
    h = horizon(0.95, 0.95, 0.95)
    h["percentiles"]["taker_delta_notional_usd_sum"]["tier"] = "low"
    assert state(h) == it.INSUFFICIENT_HISTORY


def test_every_returned_state_is_in_the_frozen_vocabulary():
    seen = set()
    for p in (0.05, 0.5, 0.95):
        for o in (0.05, 0.5, 0.95, None):
            for t in (0.05, 0.5, 0.95, None):
                for r in (0.1, 0.5):
                    for ll, ls in ((False, False), (True, False), (False, True)):
                        h = horizon(p, o or 0.5, t or 0.5, rng=r, oi_value=None if o is None else 1.0,
                                    taker_value=None if t is None else 1.0)
                        seen.add(state(h, liquidation_stress_long=ll, liquidation_stress_short=ls))
    assert seen <= it.STATES
    assert {it.SHORT_EXIT, it.LONG_BUILDUP, it.SHORT_BUILDUP, it.LONG_EXIT, it.LONG_WIPEOUT,
            it.SHORT_WIPEOUT, it.COMPRESSION, it.NORMAL, it.FACTS_ONLY} <= seen


def test_interpretation_has_no_side_effects_and_is_deterministic():
    h = horizon(0.1, 0.1, 0.1)
    before = copy.deepcopy(h)
    a = it.interpret(h, horizon="1h", cuts=CUTS, liquidation_stress_long=True)
    b = it.interpret(h, horizon="1h", cuts=CUTS, liquidation_stress_long=True)
    assert h == before and a == b
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.state = it.NORMAL                                                    # type: ignore[misc]


def test_interpretation_module_is_pure_and_carries_no_copy():
    src = (REPO / "beta" / "interpretation.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    docstring = tree.body[0].value if isinstance(tree.body[0], ast.Expr) else None
    imported, literals = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node is not docstring:
            literals.append(node.value)
    assert imported <= {"__future__", "dataclasses", "typing"}
    # Russian copy belongs to the renderer: no Cyrillic string value in the module's code.
    assert not any("Ѐ" <= ch <= "ӿ" for s in literals for ch in s)


# ---- end to end -----------------------------------------------------------------------------------------
def test_end_to_end_strong_drop_with_new_shorts_on_both_horizons():
    hist = calm_history(4, T)

    def drop(i, m):          # the last 47 buckets fall and sellers lead; OI rises below
        return bucket_metrics(price_open=100.0 - 0.05 * i, price_close=100.0 - 0.05 * (i + 1), taker=-2e6)

    hist = with_window(hist, T, 48, drop)
    oi = oi_rows(4, T + BUCKET, jump_at=T - 40 * BUCKET, jump=0.03)
    out = run(hist, bucket_metrics(price_open=97.65, price_close=97.6, taker=-2e6), oi)
    for hz in ("1h", "4h"):
        r = it.interpret(out[hz], horizon=hz, cuts=CUTS)
        assert r.price == it.DOWN and r.taker == it.DOWN, (hz, r)
    assert it.interpret(out["4h"], horizon="4h", cuts=CUTS).state == it.SHORT_BUILDUP
