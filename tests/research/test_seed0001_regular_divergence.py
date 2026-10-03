"""SEED-0001 regular divergence detector. Offline, synthetic arrays only.

No market data, no network, no outcome. The detector must read nothing after
an episode's decision time and must carry no post-decision field.
"""
import json
import hashlib
from pathlib import Path

import numpy as np
import pytest

from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO / 'docs/research/SEED0001_REGULAR_DIVERGENCE_PREREG.json'
LEDGER = REPO / 'docs/research/SCIENTIFIC_TEST_LEDGER.json'
H0 = 1_672_531_200_000 - 1000 * L.BAR_MS  # well before 2023-01-01


def _bars(close, *, spread=None, seed=0, start=H0):
    rng = np.random.default_rng(seed)
    close = np.asarray(close, dtype=float)
    n = close.size
    spread = np.full(n, 0.3) if spread is None else np.asarray(spread, dtype=float)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + spread * rng.uniform(0.2, 1.0, n)
    low = np.minimum(open_, close) - spread * rng.uniform(0.2, 1.0, n)
    volume = rng.uniform(80, 120, n)
    taker_buy = volume * rng.uniform(0.4, 0.6, n)
    return {
        'open_time_ms': start + np.arange(n, dtype=np.int64) * L.BAR_MS,
        'open': open_, 'high': high, 'low': low, 'close': close,
        'volume': volume, 'taker_buy': taker_buy, 'complete': np.ones(n, dtype=bool),
    }


def _book(bars, values):
    return {'open_time_ms': bars['open_time_ms'].copy(), 'imbalance': np.asarray(values, dtype=float)}


def _random_walk(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    return 1000 + np.cumsum(rng.normal(0, 1.0, n))


def _truncate(bars, book, t_ms):
    keep = bars['open_time_ms'] + L.BAR_MS <= t_ms
    return ({k: v[keep] for k, v in bars.items()}, {k: v[keep] for k, v in book.items()})


def _window(bars):
    first = int(bars['open_time_ms'][0]) + (L.WARMUP_BARS + 60) * L.BAR_MS
    last = int(bars['open_time_ms'][-1])
    return first, last


# ----------------------------------------------------------------- aggregation

def test_hourly_bars_aggregate_complete_hours_and_flag_incomplete():
    t0 = 1_672_531_200_000
    minutes = np.arange(180, dtype=np.int64)
    minutes = minutes[minutes != 100]  # one missing minute in hour 1
    t = t0 + minutes * L.MINUTE_MS
    price = 100 + minutes.astype(float)
    bars = L.hourly_bars(t, price, price + 0.5, price - 0.5, price + 0.25, np.ones(t.size), np.full(t.size, 0.75))
    assert bars['complete'].tolist() == [True, False, True]
    assert bars['open'][0] == 100 and bars['close'][0] == 159.25
    assert bars['high'][0] == 159.5 and bars['low'][0] == 99.5
    assert bars['volume'][0] == 60 and bars['taker_buy'][0] == 45
    assert np.isnan(bars['close'][1])
    assert L.segments(bars['complete']) == [(0, 1), (2, 3)]


def test_hourly_bars_reject_unordered_or_unaligned_rows():
    t = np.array([0, 60_000, 60_000], dtype=np.int64)
    with pytest.raises(L.DetectorInputError):
        L.hourly_bars(t, *[np.ones(3)] * 6)
    with pytest.raises(L.DetectorInputError):
        L.hourly_bars(np.array([1, 60_001]), *[np.ones(2)] * 6)


# ------------------------------------------------------------------ indicators

def _rsi_reference(close, n):
    d = np.diff(close)
    g, l = np.maximum(d, 0), np.maximum(-d, 0)
    ag, al = g[:n].mean(), l[:n].mean()
    out = [np.nan] * (n + 1)
    out[n] = 100 - 100 / (1 + ag / al)
    for k in range(n, d.size):
        ag = (ag * (n - 1) + g[k]) / n
        al = (al * (n - 1) + l[k]) / n
        out.append(100 - 100 / (1 + ag / al))
    return np.array(out)


def test_rsi_matches_wilder_reference_and_saturates():
    close = _random_walk(300, seed=3)
    for n in L.RSI_PERIODS:
        np.testing.assert_allclose(L.rsi(close, n), _rsi_reference(close, n), equal_nan=True)
    assert L.rsi(np.arange(50.0), 14)[-1] == 100.0


def test_ema_macd_atr_cvd_basics():
    flat = np.full(100, 5.0)
    assert np.allclose(L.ema(flat, 12), 5.0) and np.allclose(L.macd_line(flat), 0.0)
    a = L.atr(flat + 1, flat - 1, flat, 14)
    assert np.isnan(a[12]) and np.allclose(a[13:], 2.0)
    assert L.cvd([10, 10], [7, 2]).tolist() == [4.0, -2.0]


def test_swing_low_needs_three_lower_left_and_three_not_lower_right():
    low = np.array([10, 9, 8, 7, 6, 7, 7, 6, 8, 9, 10, 5, 6, 7], dtype=float)
    flags = L.swing_lows(low)
    assert flags[4]                        # 6 < 9,8,7 and <= 7,7,6
    assert not flags[7]                    # 6 is not below 6,7,7 on the left
    assert not flags[11]                   # right side incomplete
    assert flags.sum() == 1


def test_book_hourly_imbalance_hour_membership_and_minimum():
    grid = np.array([0, L.BAR_MS], dtype=np.int64)
    t = np.r_[np.arange(60) * 30_000, L.BAR_MS + np.arange(59) * 30_000]
    bid = np.r_[np.full(60, 3.0), np.full(59, 1.0)]
    ask = np.r_[np.full(60, 1.0), np.full(59, 1.0)]
    out = L.book_hourly_imbalance(t, bid, ask, grid)
    assert out['snapshots'].tolist() == [60, 59]
    assert out['imbalance'][0] == pytest.approx(0.5) and np.isnan(out['imbalance'][1])


# -------------------------------------------------------------------- detector

def test_designed_divergence_episode_is_found_with_its_comparison_pivot():
    rng = np.random.default_rng(11)
    warm = 1000 + np.cumsum(rng.normal(0, 0.3, 900))
    base = warm[-1]
    path = np.r_[np.linspace(base, base - 14, 6),            # sharp drop: pivot j
                 np.linspace(base - 13, base - 9, 6),        # bounce
                 np.linspace(base - 9.5, base - 15, 14),     # slow grind to a lower low: pivot i
                 np.linspace(base - 14, base - 11, 6)]
    close = np.r_[warm, path]
    bars = _bars(close, spread=np.full(close.size, 0.2), seed=2)
    i = 900 + 6 + 6 + 13
    bars['low'][i] = close[i] - 1.0
    j = 900 + 5
    bars['low'][j] = close[j] - 0.6
    bars['taker_buy'][j + 1:i + 1] = 0.7 * bars['volume'][j + 1:i + 1]   # net buying into the lower low
    imb = np.full(close.size, -0.05)
    imb[i + 2] = 0.40
    out = L.detect(bars, _book(bars, imb), decision_start_ms=0, decision_last_ms=int(bars['open_time_ms'][-1]))
    eps = [e for e in out['EPISODES'] if e['PIVOT_BAR_OPEN_UTC'] == L.iso_utc(int(bars['open_time_ms'][i]))]
    assert len(eps) == 1
    ep = eps[0]
    assert ep['COMPARISON_PIVOT_OPEN_UTC'] == L.iso_utc(int(bars['open_time_ms'][j]))
    assert ep['SUPPORT'] is True and ep['RSI_FAMILY'] is True and ep['CVD_FAMILY'] is True
    assert ep['DIVERGENCE'] is True
    assert ep['ARM'] == 'A'
    assert ep['DECISION_TIME_MS'] == int(bars['open_time_ms'][i + 3]) + L.BAR_MS


def test_arm_follows_support_and_divergence_flags():
    close = _random_walk()
    bars = _bars(close)
    first, last = _window(bars)
    out = L.detect(bars, _book(bars, np.random.default_rng(1).normal(0, 0.1, close.size)),
                   decision_start_ms=first, decision_last_ms=last)
    assert out['EPISODES']
    for ep in out['EPISODES']:
        expected = {(True, True): 'A', (True, False): 'B', (False, True): 'C', (False, False): 'D'}
        assert ep['ARM'] == expected[(ep['SUPPORT'], ep['DIVERGENCE'])]
        assert ep['DIVERGENCE'] == (ep['DIV_COUNT'] >= 2)
        assert ep['RSI_FAMILY'] == (ep['RSI14_DIV'] and ep['RSI21_DIV'])
        assert ep['DECLINE_ATR'] >= L.DECLINE_MIN_ATR and ep['RISK_ATR'] >= L.MIN_RISK_ATR


def test_funnel_accounts_for_every_swing_low():
    close = _random_walk(seed=9)
    bars = _bars(close, seed=9)
    imb = np.random.default_rng(2).normal(0, 0.1, close.size)
    imb[2000:2010] = np.nan
    first, last = _window(bars)
    f = L.detect(bars, _book(bars, imb), decision_start_ms=first, decision_last_ms=last)['FUNNEL']
    pre = ('EXCLUDED_KLINE_WINDOW_INCOMPLETE', 'NOT_PRONOUNCED_DECLINE', 'NO_COMPARISON_PIVOT', 'NOT_LOWER_LOW')
    post = ('EXCLUDED_DEGENERATE_RISK', 'EXCLUDED_BOOK_WINDOW_MISSING', 'EXCLUDED_BOOK_BASELINE_IMMATURE')
    assert f['SWING_LOW_IN_DECISION_WINDOW'] == sum(f[k] for k in pre) + f['POPULATION']
    assert f['POPULATION'] == sum(f[k] for k in post) + f['ELIGIBLE']


def test_every_episode_is_identical_when_data_end_at_its_decision_time():
    close = _random_walk(seed=5)
    bars = _bars(close, seed=5)
    book = _book(bars, np.random.default_rng(4).normal(0, 0.1, close.size))
    first, last = _window(bars)
    full = L.detect(bars, book, decision_start_ms=first, decision_last_ms=last)['EPISODES']
    assert len(full) >= 5
    for ep in full:
        tb, tk = _truncate(bars, book, ep['DECISION_TIME_MS'])
        assert int(tb['open_time_ms'][-1]) + L.BAR_MS == ep['DECISION_TIME_MS']
        again = L.detect(tb, tk, decision_start_ms=ep['DECISION_TIME_MS'], decision_last_ms=ep['DECISION_TIME_MS'])
        assert again['EPISODES'] == [ep]


def test_future_bars_cannot_change_an_episode():
    close = _random_walk(seed=6)
    bars = _bars(close, seed=6)
    book = _book(bars, np.random.default_rng(8).normal(0, 0.1, close.size))
    first, last = _window(bars)
    base = L.detect(bars, book, decision_start_ms=first, decision_last_ms=last)['EPISODES']
    ep = base[len(base) // 2]
    k = int(np.searchsorted(bars['open_time_ms'], ep['DECISION_TIME_MS']))
    shocked = {key: v.copy() for key, v in bars.items()}
    for col in ('open', 'high', 'low', 'close'):
        shocked[col][k:] = shocked[col][k:] * 0.5
    shocked_book = _book(bars, book['imbalance'].copy())
    shocked_book['imbalance'][k:] = 0.99
    again = L.detect(shocked, shocked_book, decision_start_ms=ep['DECISION_TIME_MS'],
                     decision_last_ms=ep['DECISION_TIME_MS'])['EPISODES']
    assert again == [ep]


def test_gap_breaks_the_series_and_excludes_episodes_without_warmup():
    close = _random_walk(seed=12)
    bars = _bars(close, seed=12)
    for col in ('open', 'high', 'low', 'close', 'volume', 'taker_buy'):
        bars[col][2500] = np.nan
    bars['complete'][2500] = False
    book = _book(bars, np.random.default_rng(3).normal(0, 0.1, close.size))
    first, last = _window(bars)
    out = L.detect(bars, book, decision_start_ms=first, decision_last_ms=last)
    gap_t = int(bars['open_time_ms'][2500])
    for ep in out['EPISODES']:
        pivot_ms = ep['DECISION_TIME_MS'] - (L.PIVOT_RIGHT + 1) * L.BAR_MS
        assert not (pivot_ms - L.WARMUP_BARS * L.BAR_MS <= gap_t <= pivot_ms + L.PIVOT_RIGHT * L.BAR_MS)
    assert out['FUNNEL']['EXCLUDED_KLINE_WINDOW_INCOMPLETE'] > 0


def test_protected_surface_guard_and_outcome_blind_fields():
    close = _random_walk(seed=5)
    bars = _bars(close, seed=5)
    book = _book(bars, np.zeros(close.size))
    with pytest.raises(L.DetectorInputError, match='protected'):
        L.detect(bars, book, decision_start_ms=0, decision_last_ms=L.PROTECTED_START_MS - 95 * L.BAR_MS)
    first, last = _window(bars)
    eps = L.detect(bars, _book(bars, np.random.default_rng(4).normal(0, 0.1, close.size)),
                   decision_start_ms=first, decision_last_ms=last)['EPISODES']
    L.assert_outcome_blind(eps)
    bad = [dict(eps[0], FUTURE_RETURN_48H=0.1)]
    with pytest.raises(AssertionError, match='forbidden'):
        L.assert_outcome_blind(bad)


def test_overlap_chains_use_decision_times_only():
    h = L.BAR_MS
    t = np.array([0, 47 * h, 200 * h, 100 * h, 147 * h], dtype=np.int64)
    assert L.overlap_chains(t).tolist() == [0, 0, 2, 1, 1]


def test_epoch_and_week_block_boundaries():
    assert L.half_year_epoch(1_688_169_599_000) == '2023H1'   # 2023-06-30T23:59:59Z
    assert L.half_year_epoch(1_688_169_600_000) == '2023H2'
    assert L.week_block(L.WEEK_ANCHOR_MS) == 0 and L.week_block(L.WEEK_ANCHOR_MS - 1) == -1
    assert L.week_block(L.WEEK_ANCHOR_MS + L.WEEK_MS) == 1


# ------------------------------------------------------- prereg identity binding

def test_prereg_binds_this_detector_and_its_frozen_constants():
    prereg = json.loads(PREREG_JSON.read_text())
    lib = REPO / 'scripts/research/seed0001_regular_divergence_lib.py'
    assert prereg['CODE_IDENTITY']['DETECTOR_LIB_SHA256'] == hashlib.sha256(lib.read_bytes()).hexdigest()
    c = prereg['FROZEN_CONSTANTS']
    for name, value in c.items():
        got = getattr(L, name)
        assert (list(got) if isinstance(got, tuple) else got) == value, name
    assert prereg['DETECTOR_VERSION'] == L.DETECTOR_VERSION and prereg['CARD_ID'] == L.CARD_ID


def test_prereg_primary_family_is_exactly_two_contrasts_with_holm():
    prereg = json.loads(PREREG_JSON.read_text())
    cells = prereg['PRIMARY_TEST_FAMILY']['CELLS']
    assert [c['ID'] for c in cells] == ['P1', 'P2']
    assert [c['CONTRAST'] for c in cells] == ['A_VS_B', 'A_VS_C']
    assert prereg['PRIMARY_TEST_FAMILY']['MULTIPLICITY'] == 'HOLM'
    assert prereg['PRIMARY_TEST_FAMILY']['CONCLUSION_REQUIRES'] == 'BOTH_P1_AND_P2'
    for flag in ('MARKET_OUTCOMES_COMPUTED', 'PROTECTED_2025_VALUES_OPENED', 'PROTECTED_2026_VALUES_OPENED'):
        assert prereg['BOUNDARY'][flag] is False, flag


def test_ledger_registers_the_card_before_any_outcome():
    ledger = json.loads(LEDGER.read_text())
    prereg_sha = hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest()
    entries = {t['TEST_FAMILY_ID']: t for t in ledger['TESTS'] if t['HYPOTHESIS_ID'] == 'SEED0001-RD-V1'}
    assert set(entries) == {'TF-SEED0001-RD-RETRO1', 'TF-SEED0001-RD-PROSP1'}
    for entry in entries.values():
        assert entry['PREREG_SHA256'] == prereg_sha
        assert entry['RERUN_AUTHORIZED'] is False
        assert entry['PRIMARY_TEST_COUNT'] == 2
    # The prospective leg stays registered and unopened.
    assert entries['TF-SEED0001-RD-PROSP1']['STATUS'] == 'REGISTERED_NOT_STARTED'
    assert entries['TF-SEED0001-RD-PROSP1']['RESULT_SHA256'] is None
    # The retrospective leg was opened only under the exploratory owner permit and is closed once.
    retro = entries['TF-SEED0001-RD-RETRO1']
    assert retro['STATUS'] == 'EXECUTED' and retro['CLASSIFICATION'] == 'INCONCLUSIVE_DISCOVERY'
    assert retro['FEASIBILITY_STATUS'] == 'INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR'
    assert retro['EXECUTION_PERMIT_PATH'] == 'docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json'
    result = REPO / retro['RESULT_PATH']
    assert retro['RESULT_SHA256'] == hashlib.sha256(result.read_bytes()).hexdigest()


# ------------------------------------------------------- feasibility statistics

from scripts.research import seed0001_feasibility_lib as F  # noqa: E402


def test_prereg_binds_the_feasibility_rule():
    prereg = json.loads(PREREG_JSON.read_text())
    lib = REPO / 'scripts/research/seed0001_feasibility_lib.py'
    assert prereg['CODE_IDENTITY']['FEASIBILITY_LIB_SHA256'] == hashlib.sha256(lib.read_bytes()).hexdigest()
    rule = prereg['FEASIBILITY_RULE']
    for name in ('POWER_PROFILE_ID', 'COMPARATOR_RATE', 'LATENT_ICC', 'SHOCK_LEVEL', 'ALPHA_FAMILY', 'TARGET_POWER',
                 'POWER_REPS', 'POWER_SEED', 'EFFECT_GRID', 'MIN_MEANINGFUL_EFFECT', 'PLANNING_FRACTIONS',
                 'MIN_ARM_A_EPISODES', 'MIN_ARM_A_DISTINCT_DAYS', 'SMD_LIMIT', 'PROSPECTIVE_STOP_A', 'PROSPECTIVE_MIN_A'):
        got = getattr(F, name)
        assert (list(got) if isinstance(got, tuple) else got) == rule[name], name
    assert rule['MIN_ARM_A_EPISODES'] == 40 and rule['MIN_ARM_A_DISTINCT_DAYS'] == 30
    assert set(rule['MUST_NOT_COMPUTE']) >= {'future return', '+1R/-1R', '+2R/-1R', 'MFE/MAE'}


def test_verdict_rule_order():
    assert F.verdict(39, 35, 0.1, 0.99) == F.VERDICT_BELOW_FLOOR
    assert F.verdict(60, 29, 0.1, 0.99) == F.VERDICT_BELOW_FLOOR
    assert F.verdict(60, 40, 1.2, 0.99) == F.VERDICT_SUPPORT
    assert F.verdict(60, 40, 0.3, 0.79) == F.VERDICT_WEAK
    assert F.verdict(60, 40, 0.3, 0.80) == F.VERDICT_FEASIBLE


def _layout(n=600, seed=0):
    rng = np.random.default_rng(seed)
    arms = rng.choice(list('ABCD'), size=n, p=[0.1, 0.3, 0.1, 0.5])
    return arms, np.sort(rng.integers(0, 90, size=n))


def test_conjunction_power_is_small_under_the_null_and_grows_with_effect():
    arms, clusters = _layout()
    null = F.conjunction_power(arms, clusters, 0.0, 0.25, shock='WEEK_X_ARM', reps=1500)['POWER']
    mid = F.conjunction_power(arms, clusters, 0.15, 0.25, shock='WEEK_X_ARM', reps=1500)['POWER']
    big = F.conjunction_power(arms, clusters, 0.35, 0.25, shock='WEEK_X_ARM', reps=1500)['POWER']
    assert null < 0.03 < mid < big and big > 0.9
    again = F.conjunction_power(arms, clusters, 0.15, 0.25, shock='WEEK_X_ARM', reps=1500)['POWER']
    assert again == mid


def test_power_is_zero_without_an_arm_and_layout_prefix_stops_at_a():
    arms, clusters = _layout()
    no_c = np.where(arms == 'C', 'D', arms)
    assert F.conjunction_power(no_c, clusters, 0.2, 0.1, reps=50)['POWER'] == 0.0
    eps = [{'DECISION_TIME_MS': k, 'ARM': a, 'WEEK_BLOCK': int(c)} for k, (a, c) in enumerate(zip(arms, clusters))]
    pre = F.prospective_layout(eps, 5)
    assert pre[0].count('A') == 5 and pre[0][-1] == 'A'
    assert F.prospective_layout(eps, 10_000) is None


# ------------------------------------------------------------ runner guards

from scripts.research import seed0001_feasibility as R  # noqa: E402


def test_runner_urls_stay_before_the_protected_surface():
    days = R.book_days()
    assert days[0] == '2023-01-01' and days[-1] == '2024-12-31' and len(days) == 731
    assert R.KLINE_MONTHS[0] == '2022-11' and R.KLINE_MONTHS[-1] == '2024-12' and len(R.KLINE_MONTHS) == 26
    for s in R.SYMBOLS:
        for m in R.KLINE_MONTHS:
            R.assert_url_allowed(R.kline_url(s, m))
        for d in days:
            R.assert_url_allowed(R.book_url(s, d))
    for bad in (R.kline_url('BTCUSDT', '2025-01'), R.book_url('ETHUSDT', '2026-10-05'), R.ARCHIVE + '/x.zip'):
        with pytest.raises(R.ProtectedAccessError):
            R.assert_url_allowed(bad)


def test_runner_decision_window_matches_the_prereg():
    prereg = json.loads(PREREG_JSON.read_text())
    window = prereg['SURFACES']['DISCOVERY']
    assert L.iso_utc(R.DECISION_START_MS) == window['DECISION_START_UTC']
    assert L.iso_utc(R.DECISION_LAST_MS) == window['DECISION_LAST_UTC']
    assert R.DECISION_LAST_MS + L.SENSITIVITY_CAP_HOURS * L.BAR_MS == L.PROTECTED_START_MS


def test_runner_pins_kline_months_to_the_accepted_inventories():
    pinned = R.pinned_kline_sha256()
    assert set(pinned) == set(R.SYMBOLS)
    for s in R.SYMBOLS:
        assert list(pinned[s]) == R.KLINE_MONTHS and all(len(v) == 64 for v in pinned[s].values())


# ------------------------------------------------------- feasibility report

REPORT = REPO / 'docs/research/SEED0001_FEASIBILITY_REPORT.json'
_INT = {'DECISION_TIME_MS', 'WEEK_BLOCK', 'COMPARISON_GAP_BARS', 'MAX_INPUT_BAR_CLOSE_MS', 'TOD_HOUR_UTC',
        'DIV_COUNT', 'SUPPORT_TRAILING_PRESENT', 'CHAIN_48H'}
_BOOL = {'RSI14_DIV', 'RSI21_DIV', 'RSI_FAMILY', 'MACD_FAMILY', 'CVD_FAMILY', 'DIVERGENCE', 'SUPPORT'}
_STR = {'DECISION_TIME_UTC', 'DECISION_DATE_UTC', 'EPOCH', 'PIVOT_BAR_OPEN_UTC', 'COMPARISON_PIVOT_OPEN_UTC', 'ARM',
        'SYMBOL', 'EPISODE_ID'}


def _episodes_csv(symbol):
    import csv
    rows = list(csv.DictReader((REPO / f'docs/research/seed0001/EPISODES_{symbol}.csv').open()))
    out = []
    for r in rows:
        out.append({k: (int(v) if k in _INT else v == 'True' if k in _BOOL else v if k in _STR else float(v))
                    for k, v in r.items()})
    return out


def test_report_is_outcome_blind_and_bound_to_the_frozen_prereg():
    report = json.loads(REPORT.read_text())
    assert report['PREREG_SHA256'] == hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest()
    assert report['OUTCOMES_COMPUTED'] is False and report['FORBIDDEN_FIELDS_COMPUTED'] == []
    assert report['PROTECTED_2025_VALUES_OPENED'] is False and report['PROTECTED_2026_VALUES_OPENED'] is False
    assert report['OUTCOME_OPENING_AUTHORIZED'] is False
    v = report['VERDICT_INPUTS']
    assert report['VERDICT'] == F.verdict(v['BTC_A_EPISODES'], v['BTC_A_DISTINCT_DATES'], v['BTC_MAX_ABS_SMD'],
                                          v['BTC_STRESS_POWER_AT_MIN_EFFECT'])
    for sym in R.SYMBOLS:
        audit = report['SYMBOLS'][sym]['PIT_TRUNCATION_AUDIT']
        assert audit['CHECKED'] == audit['IDENTICAL'] >= 1


def test_frozen_episode_sets_reproduce_the_report_digests():
    report = json.loads(REPORT.read_text())
    for sym in R.SYMBOLS:
        eps = _episodes_csv(sym)
        L.assert_outcome_blind(eps)
        rows = L.episode_digest_rows(eps, sym)
        assert hashlib.sha256('\n'.join(rows).encode()).hexdigest() == report['SYMBOLS'][sym]['EPISODE_DIGEST']
        arms = report['SYMBOLS'][sym]['LAYOUT']['BY_ARM']
        assert {a: arms[a]['EPISODES'] for a in L.ARMS} == {a: sum(e['ARM'] == a for e in eps) for a in L.ARMS}
        assert all(e['DECISION_TIME_MS'] <= R.DECISION_LAST_MS for e in eps)
