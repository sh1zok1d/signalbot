"""V0.3 market briefing read model (beta/briefing.py). Offline, synthetic data only."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from beta import briefing as br
from beta.config import BetaConfig
from beta.state_tape import BUCKET, metric_key
from tests.beta.test_beta_config import PINNED_RULES_DIGEST

UTC = timezone.utc
CFG = BetaConfig.load()
EX = CFG.exchanges
END = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)          # last closed bucket (open time)


def synthetic(days=91, seed=7, last_hour=None, drop=(), no_oi=False, end=END):
    """A noisy tape for ``days`` days ending at ``end``. ``last_hour`` overrides the
    per-bucket increments of the last 12 buckets: dict(price, oi, delta_share, liq_long, liq_short)."""
    rnd = random.Random(seed)
    start = end - timedelta(days=days)
    n = int((end - start) / BUCKET) + 1
    price, oi = 100.0, 1_000_000.0
    metrics, venue_raw, oi_rows = {}, {}, {ex: [] for ex in EX}
    for i in range(n):
        b = start + i * BUCKET
        in_last = last_hour is not None and b > end - 12 * BUCKET
        dp = (last_hour or {}).get("price", 0.0) if in_last else rnd.gauss(0, 0.0005)
        doi = (last_hour or {}).get("oi", 0.0) if in_last else rnd.gauss(0, 0.0004)
        share = (last_hour or {}).get("delta_share", 0.0) if in_last else rnd.gauss(0, 0.04)
        ll = (last_hour or {}).get("liq_long", None) if in_last else None
        ls = (last_hour or {}).get("liq_short", None) if in_last else None
        if not no_oi:
            for ex in EX:
                oi_rows[ex].append({"ts": b, "oi_raw": oi, "oi_unit": "contracts", "contract_value": 1.0})
        o = price
        price = price * (1 + dp)
        oi = oi * (1 + doi)
        vol = 3_000_000.0 * rnd.uniform(0.8, 1.2)
        row = {"c:volume_notional_usd_sum": vol, "c:taker_delta_notional_usd_sum": vol * share,
               "c:funding_rate_median": 0.0001}
        vr = {}
        for ex in EX:
            row[metric_key(ex, "kline_open")] = o
            row[metric_key(ex, "kline_close")] = price
            row[metric_key(ex, "kline_high")] = max(o, price) * 1.0002
            row[metric_key(ex, "kline_low")] = min(o, price) * 0.9998
            row[metric_key(ex, "long_liquidation_notional")] = ll if ll is not None else rnd.uniform(0, 5_000)
            row[metric_key(ex, "short_liquidation_notional")] = ls if ls is not None else rnd.uniform(0, 5_000)
            vr[ex] = {"taker_delta_notional_usd": vol * share / len(EX)}
        if b not in drop:
            metrics[b] = row
            venue_raw[b] = vr
    if not no_oi:   # boundary after the last bucket
        for ex in EX:
            oi_rows[ex].append({"ts": end + BUCKET, "oi_raw": oi, "oi_unit": "contracts", "contract_value": 1.0})
    return br.BriefingInputs(metrics, venue_raw, oi_rows)


# ---- identity -------------------------------------------------------------------------
def test_versions_are_pinned_and_a_parameter_change_needs_a_new_label():
    v = br.verify_versions(CFG)
    assert v["labels_version"] == "BETA_MARKET_STATE_LABELS_V1" and v["episodes_version"] == "BETA_BRIEFING_EPISODES_V1"
    raw = dict(CFG.raw)
    changed = BetaConfig.from_mapping({**raw, "briefing": {**raw["briefing"], "price_moved_pct": 0.65}})
    with pytest.raises(br.BriefingVersionError):
        br.verify_versions(changed)
    changed = BetaConfig.from_mapping({**raw, "briefing": {**raw["briefing"], "close_delay_buckets": 4}})
    with pytest.raises(br.BriefingVersionError):
        br.verify_versions(changed)
    assert CFG.rules_digest == PINNED_RULES_DIGEST            # not detection
    assert changed.rules_digest == PINNED_RULES_DIGEST


def test_vocabulary_is_the_frozen_contract_text():
    assert br.LABEL_TEXT_RU == {
        br.LONG_FLUSH: "вынос лонгов", br.SHORT_FLUSH: "вынос шортов",
        br.ABSORBED_BUYING: "похоже на поглощение агрессивных покупок",
        br.ABSORBED_SELLING: "похоже на поглощение агрессивных продаж",
        br.SHORT_COVERING: "похоже на закрытие шортов", br.LONG_CLOSING: "похоже на закрытие лонгов",
        br.LONG_BUILDUP: "похоже на рост с набором новых лонгов",
        br.SHORT_BUILDUP: "похоже на снижение с набором новых шортов",
        br.COMPRESSION: "сжатие", br.POSITION_BUILDUP_FLAT: "похоже на набор позиций без движения цены",
        br.DELEVERAGING: "похоже на разгрузку рынка", br.NORMAL: "обычное состояние",
        br.INSUFFICIENT_HISTORY: "мало истории", br.DATA_INCOMPLETE: "данные неполные"}
    heuristic = (br.ABSORBED_BUYING, br.ABSORBED_SELLING, br.SHORT_COVERING, br.LONG_CLOSING,
                 br.LONG_BUILDUP, br.SHORT_BUILDUP, br.POSITION_BUILDUP_FLAT, br.DELEVERAGING)
    assert all(br.LABEL_TEXT_RU[k].startswith("похоже на ") for k in heuristic)
    forbidden = ("будет", "ожида", "прогноз", "сигнал", "bull", "bear", "уклон", "вероятн")
    assert not any(f in t for t in br.LABEL_TEXT_RU.values() for f in forbidden)


def test_percentile_is_mid_rank():
    assert br.percentile_rank(2.0, [1.0, 2.0, 3.0, 4.0]) == pytest.approx(0.375)
    assert br.percentile_rank(9.0, [1.0, 2.0]) == 1.0
    assert br.percentile_rank(None, [1.0]) is None and br.percentile_rank(1.0, []) is None


# ---- windows ----------------------------------------------------------------------------
def test_windows_are_rolling_and_never_read_after_the_end_bucket():
    inp = synthetic(days=3)
    w = br.window(CFG, inp, "24h", END)
    assert w["window_start"] == (END - 287 * BUCKET).isoformat().replace("+00:00", "Z")
    assert w["window_end"] == (END + BUCKET).isoformat().replace("+00:00", "Z")
    assert w["buckets_expected"] == 288 and w["price_complete"]
    w1 = br.window(CFG, inp, "1h", END)
    later = dict(inp.metrics_by_bucket)
    later[END + BUCKET] = {k: 1e9 for k in inp.metrics_by_bucket[END]}       # data after the end
    later_rows = {ex: list(r) + [{"ts": END + 2 * BUCKET, "oi_raw": 1.0, "oi_unit": "contracts",
                                  "contract_value": 1.0}] for ex, r in inp.oi_rows_by_venue.items()}
    w2 = br.window(CFG, br.BriefingInputs(later, inp.venue_raw_by_bucket, later_rows), "1h", END)
    assert w1 == w2


def test_completeness_rules():
    gap = END - 5 * BUCKET
    inp = synthetic(days=2, drop=(gap,))
    w1 = br.window(CFG, inp, "1h", END)
    assert not w1["price_complete"] and w1["volume_notional_usd"] is None
    assert br.state_label(CFG, w1, {}) == br.DATA_INCOMPLETE
    w24 = br.window(CFG, inp, "24h", END)
    assert w24["price_complete"]                                   # 287 of 288, ends present
    assert w24["volume_notional_usd"] is None and w24["buy_share"] is None   # a partial sum is not a value
    first_missing = synthetic(days=2, drop=(END - 287 * BUCKET,))
    assert not br.window(CFG, first_missing, "24h", END)["price_complete"]


def test_baseline_uses_the_same_slot_on_prior_days_and_needs_maturity():
    inp = synthetic(days=31)
    s = br.baseline_samples(CFG, inp, "1h", END)
    assert len(s["price_abs"]) == 30
    young = synthetic(days=10)
    view = br.horizon_view(CFG, young, "1h", END)
    assert view["percentiles"]["price_abs"] is None and view["label"] == br.INSUFFICIENT_HISTORY
    assert br.horizon_view(CFG, young, "24h", END)["label"] == br.INSUFFICIENT_HISTORY


# ---- labels -----------------------------------------------------------------------------
def _w(move=0.0, oi=0.0, buy=0.5, rng=1.0):
    return {"price_complete": True, "price_move_pct": move, "oi_change_pct": oi, "buy_share": buy,
            "range_width_pct": rng}


def _p(price=0.5, oi=0.5, taker=0.5, rng=0.5, liq_long=0.5, liq_short=0.5):
    p = {"price_abs": price, "oi_abs": oi, "taker_abs": taker, "range": rng, "volume": 0.5}
    for ex in EX:
        p[f"liq_long:{ex}"], p[f"liq_short:{ex}"] = liq_long, liq_short
    return p


@pytest.mark.parametrize("w,p,label", [
    (_w(move=-2, oi=-3), _p(price=0.9, oi=0.9, liq_long=0.99), br.LONG_FLUSH),
    (_w(move=2, oi=-3), _p(price=0.9, oi=0.9, liq_short=0.99), br.SHORT_FLUSH),
    (_w(move=0.01, buy=0.7), _p(price=0.2, taker=0.97), br.ABSORBED_BUYING),
    (_w(move=-0.01, buy=0.3), _p(price=0.2, taker=0.97), br.ABSORBED_SELLING),
    (_w(move=2, oi=-3), _p(price=0.9, oi=0.9), br.SHORT_COVERING),
    (_w(move=-2, oi=-3), _p(price=0.9, oi=0.9), br.LONG_CLOSING),
    (_w(move=2, oi=3), _p(price=0.9, oi=0.9), br.LONG_BUILDUP),
    (_w(move=-2, oi=3), _p(price=0.9, oi=0.9), br.SHORT_BUILDUP),
    (_w(move=0.01, oi=1), _p(price=0.3, oi=0.9, rng=0.1), br.COMPRESSION),
    (_w(move=0.01, oi=1), _p(price=0.3, oi=0.9, rng=0.5), br.POSITION_BUILDUP_FLAT),
    (_w(move=0.01, oi=-1), _p(price=0.3, oi=0.9, rng=0.5), br.DELEVERAGING),
    (_w(move=0.5, oi=0.1), _p(price=0.5, oi=0.3), br.NORMAL),
    (_w(move=2, oi=None), _p(price=0.9, oi=None), br.DATA_INCOMPLETE),
])
def test_every_label_is_reachable_in_the_frozen_order(w, p, label):
    assert br.state_label(CFG, w, p) == label


def test_liquidation_flush_needs_two_venues_in_the_tail():
    p = _p(price=0.9, oi=0.9)
    p[f"liq_long:{EX[0]}"] = 0.99                                   # one venue only
    assert br.state_label(CFG, _w(move=-2, oi=-3), p) == br.LONG_CLOSING


def test_end_to_end_market_state_on_a_planted_last_hour():
    inp = synthetic(last_hour={"price": 0.002, "oi": 0.003, "delta_share": 0.25})
    ms = br.market_state(CFG, inp, END)
    assert set(ms["rows"]) == {"5m", "1h", "4h", "24h"}
    row = ms["rows"]["1h"]
    assert row["label"] == br.LONG_BUILDUP and row["label_text_ru"] == "похоже на рост с набором новых лонгов"
    assert row["baseline_days"]["price_abs"] == 30
    assert ms["rows"]["24h"]["baseline_days"]["price_abs"] == 90
    sig = br.significance(CFG, row)
    assert sig["significant"] is True
    assert {"price_abs", "oi_abs", "taker_abs"} <= set(sig["dimensions_in_tail"])
    assert sig["venues_agreeing"] == list(EX)


def test_without_oi_the_positioning_labels_do_not_guess():
    inp = synthetic(days=40, last_hour={"price": 0.002, "oi": 0.003, "delta_share": 0.0}, no_oi=True)
    assert br.horizon_view(CFG, inp, "1h", END)["label"] == br.DATA_INCOMPLETE


# ---- significance -------------------------------------------------------------------------
def _view(dims, moves, deltas, move=1.0, delta=1.0, complete=True):
    pct = {"price_abs": dims.get("price_abs"), "oi_abs": dims.get("oi_abs"), "volume": dims.get("volume"),
           "taker_abs": dims.get("taker_abs"), "range": 0.5}
    for ex in EX:
        pct[f"liq_total:{ex}"] = dims.get("liq_total")
    w = {"price_complete": complete, "price_move_pct": move, "taker_delta_notional_usd": delta,
         "venue_price_move_pct": dict(zip(EX, moves)), "venue_taker_delta_usd": dict(zip(EX, deltas))}
    return {"window": w, "percentiles": pct, "label": br.NORMAL}


def test_significance_is_decomposed_and_needs_venue_agreement():
    two = {"price_abs": 0.97, "volume": 0.96, "oi_abs": 0.5, "taker_abs": 0.5}
    s = br.significance(CFG, _view(two, [1, 1, 1], [5, 5, 5]))
    assert s["significant"] is True and s["dimensions_in_tail"] == ["price_abs", "volume"]
    assert br.significance(CFG, _view({"price_abs": 0.97}, [1, 1, 1], [5, 5, 5]))["significant"] is False
    disagree = br.significance(CFG, _view(two, [1, -1, None], [5, 5, 5]))
    assert disagree["significant"] is False and disagree["venues_agreeing"] == [EX[0]]
    assert disagree["venues_evaluable"] == [EX[0], EX[1]]
    assert br.significance(CFG, _view(two, [1, 1, 1], [5, 5, 5], complete=False))["significant"] is None


# ---- briefing episodes ----------------------------------------------------------------------
def _pts(spec, start=END):
    return [(start + i * BUCKET, sig, lab) for i, (sig, lab) in enumerate(spec)]


def test_episode_opens_closes_after_the_delay_and_records_label_changes():
    A, B = br.LONG_BUILDUP, br.SHORT_COVERING
    eps = br.scan_episodes(CFG, _pts([(False, A), (True, A), (True, A), (True, B), (False, B),
                                      (None, B), (False, B), (False, B)]))
    assert len(eps) == 1
    e = eps[0]
    assert e["start"] == END + BUCKET and e["label_at_open"] == A
    assert e["label_changes"] == [(END + 3 * BUCKET, B)]
    assert e["status"] == br.CLOSED and e["end"] == END + 4 * BUCKET    # close of the last significant bucket
    assert e["significant_buckets"] == 3


def test_episode_merge_is_causal_and_label_bound():
    A, B = br.LONG_BUILDUP, br.SHORT_COVERING
    quiet = [(False, A)] * 3
    same_soon = br.scan_episodes(CFG, _pts([(True, A)] + quiet + [(True, A)]))
    assert len(same_soon) == 1 and same_soon[0]["resumptions"] == [END + 4 * BUCKET]
    other_soon = br.scan_episodes(CFG, _pts([(True, A)] + quiet + [(True, B)]))
    assert [e["label_at_open"] for e in other_soon] == [A, B]
    same_late = br.scan_episodes(CFG, _pts([(True, A)] + [(False, A)] * 9 + [(True, A)]))
    assert len(same_late) == 2                                    # 30 min merge gap exceeded


def test_episode_scan_rejects_unordered_points():
    with pytest.raises(ValueError):
        br.scan_episodes(CFG, [(END, True, br.NORMAL), (END, True, br.NORMAL)])
