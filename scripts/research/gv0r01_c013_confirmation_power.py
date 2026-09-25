"""GV0R01-C013 confirmation power planning (outcome-aware on EXPOSED discovery data only).

Reads only the immutable discovery result (docs/research/GV0R01_C013_MARKET_TEST_RESULT.json):
its 2020-2024 primary and adjacency weekly series and its permutation-null summary. Opens
no market data and nothing from 2025/2026. Deterministic (fixed seed).

    python -m scripts.research.gv0r01_c013_confirmation_power

Authoritative method: YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK. A fresh
surface of W weeks is built from whole exposed 52-week years sampled with replacement plus
one contiguous partial block, re-centred to the assumed true effect. This keeps within-year
serial dependence and the observed year-to-year heterogeneity (including the 2023-2024
sign reversal). Moving-block and IID bootstraps are sensitivity/diagnostic only.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RESULT_REL = 'docs/research/GV0R01_C013_MARKET_TEST_RESULT.json'
RESULT_SHA256 = '036016c403f83e4c63b2e006379551a0f595e8803cb55a0ef8f27a19ce3a1062'
SEED = int(hashlib.sha256(b'GV0R01-C013|CONFIRMATION_POWER|V1').hexdigest()[:16], 16)
N_REP = 20000
ALPHA = 0.05
HAC_CRIT = 1.96
MIN_POWER = 0.80
# Calendar grid fixed from calendar arithmetic only (complete ISO weeks):
#   51  = 2025 (Mon 2025-01-06 .. Sun 2025-12-28)
#   86  = 2025 + 2026 prefix of complete weeks available now (.. Sun 2026-08-30)
#   103 = 2025 + full 2026 (.. Sun 2026-12-27)
#   plus 3..7 year lengths for size planning.
GRID = (51, 86, 103, 156, 208, 260, 312, 364)
# Size planning only (authoritative method, discovery effect): 8, 9, 10, 12 and 15 years.
SIZE_GRID = (416, 468, 520, 624, 780)
OUTPUT_REL = 'docs/research/GV0R01_C013_CONFIRMATION_POWER.json'
HALF_BLOCK = 26


def load():
    raw = (REPO / RESULT_REL).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RESULT_SHA256:
        raise RuntimeError('discovery result digest mismatch')
    r = json.loads(raw)
    x = np.array([v for _, v in r['PRIMARY']['WEEKLY_SERIES']])
    a = np.array([v for _, v in r['ADJACENCY_DIAGNOSTIC']['WEEKLY_SERIES']])
    years = np.array([int(m[:4]) for m, _ in r['PRIMARY']['WEEKLY_SERIES']])
    null = r['PRIMARY']['NULL']
    per_week_null_sd = (null['NULL_Q975'] - null['NULL_Q025']) / (2 * 1.959964) * math.sqrt(len(x))
    hac_se = abs(r['PRIMARY']['POOLED'] / r['EVALUATION']['HAC_T'])
    return {'x': x, 'a': a, 'years': years, 'null_mean': null['NULL_MEAN'], 'null_sd_week': per_week_null_sd,
            'pooled': r['PRIMARY']['POOLED'], 'adj_pooled': r['ADJACENCY_DIAGNOSTIC']['POOLED'], 'hac_se': hac_se}


def hac_lag(W):
    return int(math.floor(4 * (W / 100) ** (2 / 9)))


def nw_t(s, lag):
    T = s.size
    c = s - s.mean()
    lrv = float((c * c).sum() / T)
    for l in range(1, lag + 1):
        lrv += 2 * (1 - l / (lag + 1)) * float((c[l:] * c[:-l]).sum() / T)
    return float(s.mean() / math.sqrt(lrv / T)) if lrv > 0 else 0.0


def temporal_ok(s):
    """Confirmation temporal rule: at least ceil(0.6 * B) of the B consecutive 26-week
    blocks (last block absorbs a remainder; a surface shorter than 52 weeks uses 2 halves)
    have a strictly negative mean."""
    B = max(2, s.size // HALF_BLOCK)
    edges = [round(i * s.size / B) for i in range(B + 1)]
    neg = sum(1 for i in range(B) if s[edges[i]:edges[i + 1]].mean() < 0)
    return neg >= math.ceil(0.6 * B)


def surface_indices(rng, W, method, n_weeks, years):
    if method == 'YEAR_BLOCK':
        starts = [int(np.flatnonzero(years == y)[0]) for y in sorted(set(years))]
        idx = []
        for _ in range(W // 52):
            s = starts[rng.integers(len(starts))]
            idx.extend(range(s, s + 52))
        r = W % 52
        if r:
            s = starts[rng.integers(len(starts))] + int(rng.integers(0, 52 - r + 1))
            idx.extend(range(s, s + r))
        return np.array(idx)
    if method.startswith('MBB'):
        L = int(method[3:])
        idx = []
        while len(idx) < W:
            s = int(rng.integers(n_weeks))
            idx.extend((s + j) % n_weeks for j in range(L))
        return np.array(idx[:W])
    return rng.integers(0, n_weeks, size=W)  # IID diagnostic


def simulate(d, mu, W, method, rng):
    x, a = d['x'], d['a']
    xc, ac = x - x.mean(), a - a.mean()
    mu_adj = d['adj_pooled'] * (mu / d['pooled'])
    sd0 = d['null_sd_week'] / math.sqrt(W)
    lag = hac_lag(W)
    out = {'STATISTICAL': 0, 'DIRECTION': 0, 'STATISTICAL_AND_DIRECTION': 0, 'DEPENDENCE': 0, 'TEMPORAL': 0,
           'ADJACENCY': 0, 'FULL_PASS_EXCLUDING_CONTROL': 0}
    for _ in range(N_REP):
        idx = surface_indices(rng, W, method, x.size, d['years'])
        s = xc[idx] + mu
        adj = float((ac[idx] + mu_adj).mean())
        pooled = float(s.mean())
        z = (pooled - d['null_mean']) / sd0
        p = min(1.0, 2 * min(0.5 * math.erfc(-z / math.sqrt(2)), 0.5 * math.erfc(z / math.sqrt(2))))
        stat, direction = p <= ALPHA, pooled < 0
        t = nw_t(s, lag)
        dep = t <= -HAC_CRIT
        temp = temporal_ok(s)
        adjok = adj < 0
        out['STATISTICAL'] += stat
        out['DIRECTION'] += direction
        out['STATISTICAL_AND_DIRECTION'] += stat and direction
        out['DEPENDENCE'] += dep
        out['TEMPORAL'] += temp
        out['ADJACENCY'] += adjok
        out['FULL_PASS_EXCLUDING_CONTROL'] += stat and direction and dep and temp and adjok
    return {k: round(v / N_REP, 4) for k, v in out.items()}


def run():
    d = load()
    effects = {
        'DISCOVERY_EFFECT': d['pooled'],
        'ATTENUATED_50PCT': 0.5 * d['pooled'],
        # Smallest effect the discovery evidence itself supports: one-sided 95% HAC bound.
        'DISCOVERY_CONSISTENT_MINIMUM': -(abs(d['pooled']) - 1.644854 * d['hac_se']),
    }
    rng = np.random.Generator(np.random.PCG64(SEED))
    table = {}
    for method in ('YEAR_BLOCK', 'MBB13', 'MBB26', 'IID'):
        for name, mu in effects.items():
            for W in GRID:
                table.setdefault(method, {}).setdefault(name, {})[str(W)] = simulate(d, mu, W, method, rng)
    size = {str(W): simulate(d, d['pooled'], W, 'YEAR_BLOCK', rng) for W in SIZE_GRID}
    need = [W for W in GRID + SIZE_GRID if (table['YEAR_BLOCK']['DISCOVERY_EFFECT'].get(str(W)) or size[str(W)])['STATISTICAL_AND_DIRECTION'] >= MIN_POWER]
    return {'UNIT': 'GV0R01_C013_CONFIRMATION_POWER', 'INPUT': RESULT_REL, 'INPUT_SHA256': RESULT_SHA256,
            'AUTHORITATIVE_METHOD': 'YEAR_BLOCK', 'SENSITIVITY_METHODS': ['MBB13', 'MBB26'], 'DIAGNOSTIC_ONLY': ['IID'],
            'CONTROL_GATE_SIMULATED': False,
            'CONTROL_GATE_NOTE': 'The discovery result stores no controlled weekly series, so FULL_PASS_EXCLUDING_CONTROL is an upper bound on the full confirmation pass probability.',
            'NULL_MODEL': 'Normal approximation to the frozen within-date permutation null: mean = discovery NULL_MEAN, sd = discovery per-week null sd / sqrt(W).',
            'MIN_POWER': MIN_POWER, 'SIZE_GRID_WEEKS': list(SIZE_GRID), 'SIZE_PLANNING_YEAR_BLOCK_DISCOVERY_EFFECT': size,
            'MIN_WEEKS_STAT_AND_DIRECTION_AT_DISCOVERY_EFFECT': min(need) if need else None,
            'PROTECTED_DATA_OPENED': False, 'MARKET_DATA_READ': False,
            'SEED': SEED, 'N_REP': N_REP, 'GRID_WEEKS': list(GRID), 'EFFECTS': effects,
            'NULL_MEAN': d['null_mean'], 'NULL_SD_PER_WEEK': d['null_sd_week'], 'DISCOVERY_HAC_SE': d['hac_se'],
            'HAC_LAG_BY_W': {str(W): hac_lag(W) for W in GRID}, 'RESULTS': table}


if __name__ == '__main__':
    out = run()
    (REPO / OUTPUT_REL).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('MIN_WEEKS_STAT_AND_DIRECTION_AT_DISCOVERY_EFFECT', 'SEED', 'N_REP')}, indent=2))
