"""Synthetic/unit tests for the GV0R01-C013 market-test harness.

No real market data is read. Synthetic panels are random walks with no planted
effect; they check mechanics only, never the scientific outcome.
"""

from __future__ import annotations

import copy
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts.research import gv0r01_c013_market_test as R
from scripts.research import gv0r01_c013_market_test_lib as L

REPO = Path(__file__).resolve().parents[2]
DAY_MS = L.DAY_MS


def _ms(d: date) -> int:
    return (d - date(1970, 1, 1)).days * DAY_MS


def synthetic_rows(n_symbols=30, last=date(2020, 3, 10), seed=7, listing=None, delist=None):
    """Random-walk OHLCV rows from 2019-12-01. listing/delist: {symbol: date}."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = {}
    n_days = (last - L.PANEL_DAY0).days + 1
    for i in range(n_symbols):
        sym = f'S{i:03d}USDT'
        px = 10.0 * math.exp(rng.normal())
        bucket = {}
        for d in range(n_days):
            day = L.PANEL_DAY0 + timedelta(days=d)
            o = px
            path = o * np.exp(np.cumsum(rng.normal(0, 0.01, size=24)))
            c = float(path[-1])
            h = float(max(o, path.max()))
            l = float(min(o, path.min()))
            qv = float(abs(rng.normal(1e6 * (i + 1), 1e5)))
            px = c
            if listing and sym in listing and day < listing[sym]:
                continue
            if delist and sym in delist and day > delist[sym]:
                continue
            bucket[_ms(day)] = (o, h, l, c, qv)
        rows[sym] = bucket
    return rows


def small_params(**over):
    prm = copy.deepcopy(R.load_prereg(REPO)['PARAMS'])
    prm.update({'FIRST_DECISION_DATE': '2020-01-06', 'LAST_DECISION_DATE': '2020-03-01',
                'LEGAL_LAST_BAR_DATE': '2020-03-10', 'FIRST_WEEK_MONDAY': '2020-01-06', 'N_WEEKS': 8,
                'MIN_VALID_WEEKS': 7, 'MIN_VALID_WEEKS_PER_YEAR': 7, 'STABILITY_YEARS': ['2020'],
                'MIN_YEARS_SHARING_SIGN': 1, 'PERMUTATIONS': 40,
                'PRIMARY_VARIANT': {'K': 5, 'H': 1, 'N': 12},
                'SECONDARY_VARIANTS': [{'K': 1, 'H': 1, 'N': 12, 'VARIANT_INDEX': 1},
                                       {'K': 5, 'H': 5, 'N': 20, 'VARIANT_INDEX': 2}]})
    prm.update(over)
    return prm


def panel(**kw):
    return L.build_panel(synthetic_rows(**kw), last_day=kw.get('last', date(2020, 3, 10)))


# ---- prereg / frozen identity ----------------------------------------------------------------

def test_prereg_freezes_single_primary_and_card_search_surface():
    pre = R.load_prereg(REPO)
    prm = pre['PARAMS']
    assert prm['PRIMARY_VARIANT'] == {'K': 5, 'H': 1, 'N': 50}
    grid = {(v['K'], v['H'], v['N']) for v in prm['SECONDARY_VARIANTS']} | {(5, 1, 50)}
    assert grid == {(k, h, n) for k in (1, 5) for h in (1, 5) for n in (50, 100)}
    assert len({v['VARIANT_INDEX'] for v in prm['SECONDARY_VARIANTS']}) == 7
    assert prm['PERMUTATIONS'] == 1000 and prm['SEED'] == R.derived_seed()
    assert prm['PRIMARY_EFFECT_DIRECTION_SIGN'] == -1 and prm['PRIMARY_ALPHA'] == 0.05
    assert prm['STABILITY_YEARS'] == ['2020', '2021', '2022', '2023', '2024']
    assert pre['EXECUTION_AUTHORIZED'] is False
    assert pre['PROTECTED_DATA_RULE']['PROTECTED_2025_2026_OPEN_AUTHORIZED'] is False
    assert pre['MULTIPLICITY']['PRIMARY_TEST_COUNT'] == 1 and pre['MULTIPLICITY']['SECONDARY_TEST_COUNT'] == 7


def test_frozen_calendar_is_five_full_years_of_iso_weeks():
    prm = R.load_prereg(REPO)['PARAMS']
    weeks = L.iso_weeks(date.fromisoformat(prm['FIRST_WEEK_MONDAY']), prm['N_WEEKS'])
    assert weeks[-1] == date(2024, 12, 23) and weeks[-1] + timedelta(days=6) == date.fromisoformat(prm['LAST_DECISION_DATE'])
    by_year = {}
    for w in weeks:
        by_year[w.year] = by_year.get(w.year, 0) + 1
    assert by_year == {2020: 52, 2021: 52, 2022: 52, 2023: 52, 2024: 52}
    days = L.decision_days(prm, 1, 0)
    assert L.index_day(days[0]) == date(2020, 1, 6) and L.index_day(days[-1]) == date(2024, 12, 29)
    assert len(days) == 1820
    # H=5 and the adjacency offset never need a bar after 2024-12-31
    assert L.index_day(L.decision_days(prm, 5, 0)[-1]) == date(2024, 12, 27)
    assert L.index_day(L.decision_days(prm, 1, 1)[-1]) == date(2024, 12, 29)


def test_repository_preflight_passes_offline_checks_and_execute_is_refused():
    pf = R.preflight(REPO)
    offline = {k: v for k, v in pf['CHECKS'].items() if k != 'SCIENTIFIC_PATHS_CLEAN'}
    assert all(v['OK'] for v in offline.values()), {k: v for k, v in offline.items() if not v['OK']}
    assert pf['TARGETS_COMPUTED'] is False
    ex = R.preflight(REPO, mode='execute')
    assert not ex['OK'] and 'EXECUTION_PERMIT_BOUND' in ex['FAILURES']
    with pytest.raises(R.PreflightRefused):
        R.execute(REPO)
    assert not (REPO / R.RESULT_REL).exists()


def test_prereg_lists_exactly_the_preflight_checks():
    pre = R.load_prereg(REPO)['PREFLIGHT']
    assert set(R.preflight(REPO)['CHECKS']) == set(pre['CHECKS'])
    assert set(R.preflight(REPO, mode='execute')['CHECKS']) == set(pre['CHECKS']) | set(pre['EXECUTE_ONLY_CHECKS'])


def test_real_panel_loader_refuses_without_execute_preflight():
    with pytest.raises(R.PreflightRefused):
        R.load_real_panel(REPO, permit_checked=False)


# ---- data semantics ----------------------------------------------------------------------------

def test_protected_rows_and_targets_are_refused():
    with pytest.raises(L.ProtectedDataRefused):
        L.build_panel({'AUSDT': {_ms(date(2025, 1, 1)): (1.0, 1.0, 1.0, 1.0, 1.0)}}, last_day=date(2024, 12, 31))
    with pytest.raises(L.ProtectedDataRefused):
        L.build_panel({}, last_day=date(2025, 1, 1))
    p = panel()
    with pytest.raises(L.ProtectedDataRefused):
        L.target_row(p, 0, p.n_days - 1, 2, p.n_days - 1)


def test_malformed_bars_are_unavailable_not_zero():
    rows = {'AUSDT': {_ms(date(2019, 12, 1)): (1.0, 0.9, 0.8, 1.0, 5.0)}}   # high < open
    p = L.build_panel(rows, last_day=date(2019, 12, 5))
    assert p.present[0, 0] and p.malformed[0, 0] and not p.valid[0, 0]
    assert L.target_row(p, 0, 0, 1, p.n_days - 1) == 'MALFORMED_BAR'


def test_clv_and_zero_range():
    assert L.bar_clv(1.0, 2.0, 1.0, 2.0) == 1.0
    assert L.bar_clv(1.0, 2.0, 1.0, 1.0) == -1.0
    assert L.bar_clv(1.5, 2.0, 1.0, 1.5) == 0.0
    assert L.bar_clv(1.0, 1.0, 1.0, 1.0) is None


def test_wick_target_and_algebraic_identity():
    o, h, l, c = 100.0, 110.0, 95.0, 97.0
    rows = {'AUSDT': {_ms(date(2019, 12, 1)): (o, h, l, c, 1.0), _ms(date(2019, 12, 2)): (c, c, c, c, 1.0)}}
    p = L.build_panel(rows, last_day=date(2019, 12, 31))
    assert L.target_row(p, 0, 1, 1, p.n_days - 1) == 'DELISTING_DAY_BAR'   # final archive bar before legal end
    tr = L.target_row(p, 0, 0, 1, p.n_days - 1)
    assert tr.wick == pytest.approx(math.log(h / o) - math.log(o / l))
    assert tr.ret_win == pytest.approx(math.log(c / o)) and tr.range_win == pytest.approx(math.log(h / l))
    # WICK = -range * CLV(log prices) + 2 * RET  (the coupling residualization removes linearly)
    lh, ll, lc = math.log(h), math.log(l), math.log(c)
    clv_log = (2 * lc - lh - ll) / (lh - ll)
    assert tr.wick == pytest.approx(-(lh - ll) * clv_log + 2 * tr.ret_win)


def test_residual_is_orthogonal_to_controls():
    rng = np.random.Generator(np.random.PCG64(1))
    y, a, b = rng.normal(size=40), rng.normal(size=40), rng.normal(size=40)
    r = L.ols_residual(y, [a, b])
    for x in (np.ones(40), a, b):
        assert abs(float(r @ x)) < 1e-9
    assert L.ols_residual(y, [a, a]) is None


def test_average_ranks_ties_and_spearman():
    assert list(L.average_ranks([3.0, 1.0, 3.0, 2.0])) == [3.5, 1.0, 3.5, 2.0]
    x = L.average_ranks([1.0, 2.0, 3.0, 4.0])
    assert L.pearson(x, L.average_ranks([10.0, 20.0, 30.0, 40.0])) == pytest.approx(1.0)
    assert L.pearson(x, L.average_ranks([4.0, 3.0, 2.0, 1.0])) == pytest.approx(-1.0)
    assert L.pearson(x, np.ones(4)) is None


def test_persistence_maps_to_negative_statistic():
    """Direction algebra: if future log-CLV equals past CLV (pure persistence) and
    returns are unrelated, rank(CLV) vs rank(WICK_RESID) is negative."""
    rng = np.random.Generator(np.random.PCG64(3))
    n = 60
    clv = rng.uniform(-0.9, 0.9, n)
    rng_width = rng.uniform(0.02, 0.06, n)
    ret = rng.normal(0, 0.01, n)
    wick = -rng_width * clv + 2 * ret
    resid = L.ols_residual(wick, [ret, rng_width])
    assert L.pearson(L.average_ranks(clv), L.average_ranks(resid)) < -0.5


# ---- point-in-time ---------------------------------------------------------------------------

def test_predictor_and_universe_ignore_bars_at_or_after_t():
    prm = small_params()
    rows = synthetic_rows()
    t_day = date(2020, 2, 3)
    t = L.day_index(t_day)
    base = L.predictor_state(L.build_panel(rows, last_day=date(2020, 3, 10)), t, prm, K=5, N=12, excluded=frozenset())
    mutated = copy.deepcopy(rows)
    for sym in mutated:
        for ms in list(mutated[sym]):
            if ms >= _ms(t_day):
                o, h, l, c, qv = mutated[sym][ms]
                mutated[sym][ms] = (o, h * 3, l / 3, c, qv * 1000)
    other = L.predictor_state(L.build_panel(mutated, last_day=date(2020, 3, 10)), t, prm, K=5, N=12, excluded=frozenset())
    assert base.selected == other.selected and base.clv == other.clv and base.qv30 == other.qv30
    assert base.trail_ret == other.trail_ret and base.trail_range == other.trail_range


def test_target_ignores_bars_before_t():
    rows = synthetic_rows()
    t = L.day_index(date(2020, 2, 3))
    a = L.build_panel(rows, last_day=date(2020, 3, 10))
    mutated = copy.deepcopy(rows)
    for sym in mutated:
        for ms in list(mutated[sym]):
            if ms < _ms(date(2020, 2, 3)):
                o, h, l, c, qv = mutated[sym][ms]
                mutated[sym][ms] = (o, h * 2, l / 2, c, qv)
    b = L.build_panel(mutated, last_day=date(2020, 3, 10))
    for si in range(a.n_symbols):
        assert L.target_row(a, si, t, 1, a.n_days - 1) == L.target_row(b, si, t, 1, b.n_days - 1)


def test_listing_age_exclusions_and_later_delisted_names():
    prm = small_params()
    t = L.day_index(date(2020, 2, 3))
    rows = synthetic_rows(listing={'S029USDT': date(2020, 1, 10)}, delist={'S028USDT': date(2020, 2, 10)})
    p = L.build_panel(rows, last_day=date(2020, 3, 10))
    ps = L.predictor_state(p, t, prm, K=5, N=30, excluded=frozenset({'S027USDT'}))
    sel = {p.symbols[s] for s in L.predictor_state(p, t, prm, K=5, N=27, excluded=frozenset({'S027USDT'})).selected}
    assert 'S029USDT' not in sel               # listed 24 days before t (< 35)
    assert 'S027USDT' not in sel               # pinned exclusion
    assert 'S028USDT' in sel                   # delisted after t: no survivorship filter
    assert ps.eligible_n == 28 and ps.selected == []   # fewer than N eligible -> no universe
    si = p.symbols.index('S028USDT')
    assert L.target_row(p, si, L.day_index(date(2020, 2, 10)), 1, p.n_days - 1) == 'DELISTING_DAY_BAR'


def test_top_n_by_trailing_volume_with_symbol_tiebreak():
    prm = small_params()
    p = panel()
    t = L.day_index(date(2020, 2, 3))
    ps = L.predictor_state(p, t, prm, K=5, N=5, excluded=frozenset())
    qv = [L.trailing_quote_volume(p, si, t, 30) for si in range(p.n_symbols)]
    assert ps.selected == sorted(range(p.n_symbols), key=lambda s: (-qv[s], p.symbols[s]))[:5]


# ---- null, aggregation, multiplicity -----------------------------------------------------------

def test_stratified_permutations_are_deterministic_and_stay_in_strata():
    strata = L.volume_terciles([float(x) for x in range(12)], [f'N{i}' for i in range(12)])
    assert [len(s) for s in strata] == [4, 4, 4]
    a = L.stratified_permutations(strata, 12, 30, L.date_rng(5, 0, 737000))
    b = L.stratified_permutations(strata, 12, 30, L.date_rng(5, 0, 737000))
    c = L.stratified_permutations(strata, 12, 30, L.date_rng(5, 0, 737001))
    assert (a == b).all() and not (a == c).all()
    for s in strata:
        assert set(a[:, s].ravel().tolist()) <= set(s.tolist())


def test_weekly_aggregation_minimum_days_and_monday_year():
    mon = date(2020, 12, 28)
    daily = {mon + timedelta(days=j): float(j) for j in range(5)}
    assert L.weekly_means(daily, [mon], 5) == {mon: 2.0}
    assert L.weekly_means(daily, [mon], 6) == {}
    assert L._yearly({mon: 1.0, date(2021, 1, 4): 3.0}) == {'2020': 1.0, '2021': 3.0}


def test_two_sided_p_holm_and_hac():
    null = np.arange(-50, 50, dtype=float) / 100
    r = L.two_sided_p(0.6, null)
    assert r['P_UPPER'] == pytest.approx(1 / 101) and r['P_TWO_SIDED'] == pytest.approx(2 / 101)
    assert L.two_sided_p(0.0, null)['P_TWO_SIDED'] == 1.0
    assert L.holm({'a': 0.01, 'b': 0.04, 'c': 0.03}) == {'a': 0.03, 'c': 0.06, 'b': 0.06}
    assert L.newey_west_t([1.0, -1.0] * 20, 4) == pytest.approx(0.0)
    assert L.newey_west_t([1.0], 4) is None


# ---- classification ---------------------------------------------------------------------------

def _summary(pooled=-0.02, p=0.001, yearly=None, ctrl=-0.01, ctrl_p=0.01, adj=-0.01, weeks=260, miss=0.0):
    yearly = yearly or {y: pooled for y in ('2020', '2021', '2022', '2023', '2024')}
    series = [['2020-01-06', pooled + 0.001 * ((i % 3) - 1)] for i in range(weeks)]
    prim = {'POOLED': pooled, 'NULL': {'P_TWO_SIDED': p}, 'YEARLY': yearly, 'VALID_WEEKS': weeks,
            'VALID_WEEKS_BY_YEAR': {y: weeks // 5 for y in yearly}, 'MISSING_TARGET_RATE': miss,
            'CONTROLLED': {'POOLED': ctrl, 'NULL': {'P_TWO_SIDED': ctrl_p}}, 'WEEKLY_SERIES': series}
    return prim, {'POOLED': adj, 'VALID_WEEKS': weeks}


def _classify(**kw):
    prim, adj = _summary(**kw)
    return L.evaluate(prim, adj, [], R.load_prereg(REPO)['PARAMS'], identity_ok=True)


def test_classification_rules():
    assert _classify()['CLASSIFICATION'] == 'PROMISING_PROTOTYPE'
    assert _classify(p=0.2)['CLASSIFICATION'] == 'NO_USEFUL_STRUCTURE'
    opp = _classify(pooled=0.02, ctrl=0.01, adj=0.01)
    assert opp['CLASSIFICATION'] == 'NO_USEFUL_STRUCTURE' and 'OPPOSITE_DIRECTION_OUTSIDE_NULL' in opp['REASONS']
    two_years = {'2020': -0.02, '2021': -0.02, '2022': 0.01, '2023': 0.01, '2024': 0.0}
    assert _classify(yearly=two_years)['GATES']['TEMPORAL_GATE'] is False
    assert _classify(ctrl_p=0.3)['GATES']['CONTROL_GATE'] is False
    assert _classify(ctrl=0.01)['GATES']['CONTROL_GATE'] is False
    assert _classify(adj=0.01)['GATES']['ADJACENCY_GATE'] is False
    assert _classify(weeks=200)['CLASSIFICATION'] == 'INCONCLUSIVE_DISCOVERY'
    assert _classify(miss=0.05)['CLASSIFICATION'] == 'INCONCLUSIVE_DISCOVERY'
    prim, adj = _summary()
    bad = L.evaluate(prim, adj, [], R.load_prereg(REPO)['PARAMS'], identity_ok=False, identity_reasons=['X'])
    assert bad['CLASSIFICATION'] == 'INVALID_DISCOVERY'


def test_nominal_p_alone_is_never_sufficient():
    for kw in ({'yearly': {'2020': 0.01, '2021': 0.01, '2022': 0.01, '2023': -0.02, '2024': -0.02}},
               {'ctrl_p': 0.5}, {'adj': 0.02}):
        out = _classify(p=0.001, **kw)
        assert out['GATES']['STATISTICAL_GATE'] is True and out['CLASSIFICATION'] == 'NO_USEFUL_STRUCTURE'


def test_secondary_grid_cannot_change_classification():
    prim, adj = _summary(p=0.2)
    sec = [{'VARIANT': 'K1_H1_N50', 'POOLED': -0.5, 'NULL': {'P_TWO_SIDED': 0.001}}]
    out = L.evaluate(prim, adj, sec, R.load_prereg(REPO)['PARAMS'], identity_ok=True)
    assert out['CLASSIFICATION'] == 'NO_USEFUL_STRUCTURE' and out['SECONDARY_CAN_CHANGE_CLASSIFICATION'] is False
    assert out['SECONDARY_HOLM_P'] == {'K1_H1_N50': 0.001}


# ---- end to end on synthetic data -------------------------------------------------------------

def test_end_to_end_synthetic_is_byte_identical():
    prm = small_params()
    ident = {'SYNTHETIC': True}
    a = L.run_all(panel(), prm, excluded=frozenset(), identity=ident, identity_ok=True)
    b = L.run_all(panel(), prm, excluded=frozenset(), identity=ident, identity_ok=True)
    assert L.canonical_bytes(a) == L.canonical_bytes(b)
    prim = a['PRIMARY']
    assert prim['VALID_WEEKS'] == 8 and prim['VALID_DAYS'] == 56
    assert set(prim) >= {'POOLED', 'NULL', 'CONTROLLED', 'YEARLY', 'WEEKLY_SERIES', 'UNIVERSE_IDENTITY_DIGEST'}
    assert a['EVALUATION']['CLASSIFICATION'] in {'PROMISING_PROTOTYPE', 'NO_USEFUL_STRUCTURE'}
    assert a['PROTECTED_2025_2026_OPENED'] is False
    assert [v['VARIANT'] for v in a['SECONDARY_GRID']] == ['K1_H1_N12', 'K5_H5_N20']
    assert a['SECONDARY_GRID'][1]['INVALID_DAYS_BY_REASON'] == {}
    json.loads(L.canonical_bytes(a))


def test_output_schema_keys_match_prereg():
    prm = small_params()
    out = L.run_all(panel(), prm, excluded=frozenset(), identity={}, identity_ok=True)
    schema = R.load_prereg(REPO)['OUTPUT_SCHEMA']
    assert set(out) == set(schema['TOP_LEVEL_KEYS'])
    assert set(schema['VARIANT_KEYS']) <= set(out['PRIMARY'])
    assert set(schema['EVALUATION_KEYS']) <= set(out['EVALUATION'])


def test_seed_change_changes_null_but_not_observed_statistic():
    p = panel()
    a = L.run_all(p, small_params(), excluded=frozenset(), identity={}, identity_ok=True)
    b = L.run_all(panel(), small_params(SEED=12345), excluded=frozenset(), identity={}, identity_ok=True)
    assert a['PRIMARY']['POOLED'] == b['PRIMARY']['POOLED']
    assert a['PRIMARY']['NULL'] != b['PRIMARY']['NULL']
