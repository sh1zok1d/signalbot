"""GV0R01-C013 market test: pure, deterministic scientific functions.

Frozen by docs/research/GV0R01_C013_MARKET_TEST_PREREG.json. Every scientific
choice is a prereg parameter; this module makes none of its own. It reads no
files and opens no network. The guarded real-data entry is in
scripts/research/gv0r01_c013_market_test.py.

Panel layout: dense [symbol x day] arrays indexed from PANEL_DAY0 (2019-12-01).
A bar for day d opens at d 00:00 UTC and is AVAILABLE_AT d+1 00:00 UTC. At
decision time t (00:00 UTC of day t) the predictor may use bars d <= t-1 only;
the target uses bars t+OFFSET .. t+OFFSET+H-1 only.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

import numpy as np

SCHEMA = 'GV0R01_C013_MARKET_TEST_RESULT_V1'
PANEL_DAY0 = date(2019, 12, 1)
DAY_MS = 86_400_000
PANEL_DAY0_MS = int((PANEL_DAY0 - date(1970, 1, 1)).days) * DAY_MS


class C013IntegrityError(RuntimeError):
    """Malformed identity or impossible state. Fail closed."""


class ProtectedDataRefused(RuntimeError):
    """Any 2025/2026 access attempt."""


# ---------------------------------------------------------------------------
# Panel


@dataclass
class Panel:
    symbols: list[str]
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    QV: np.ndarray
    present: np.ndarray      # a row exists for (symbol, day)
    valid: np.ndarray        # present and well-formed
    malformed: np.ndarray    # present and not well-formed
    first_day: np.ndarray    # first present day index, -1 if none
    last_day: np.ndarray     # last present day index, -1 if none
    n_days: int

    @property
    def n_symbols(self) -> int:
        return len(self.symbols)


def day_index(d: date) -> int:
    return (d - PANEL_DAY0).days


def index_day(i: int) -> date:
    return PANEL_DAY0 + timedelta(days=int(i))


def refuse_protected_day(d: date) -> None:
    if d.year >= 2025:
        raise ProtectedDataRefused(f'PROTECTED_DAY:{d.isoformat()}')


def well_formed(o: float, h: float, l: float, c: float, qv: float) -> bool:
    vals = (o, h, l, c, qv)
    if not all(isinstance(v, float) and math.isfinite(v) for v in vals):
        return False
    if min(o, h, l, c) <= 0 or qv < 0:
        return False
    return l <= o <= h and l <= c <= h


def build_panel(rows: Mapping[str, Mapping[int, Sequence[float]]], *, last_day: date) -> Panel:
    """rows: symbol -> {open_ms: (open, high, low, close, quote_volume)}.

    Open times must be exact UTC day boundaries inside [PANEL_DAY0, last_day].
    A 2025/2026 row is refused, never loaded.
    """

    refuse_protected_day(last_day)
    n_days = day_index(last_day) + 1
    symbols = sorted(rows)
    shape = (len(symbols), n_days)
    arrs = {k: np.full(shape, np.nan) for k in ('O', 'H', 'L', 'C', 'QV')}
    present = np.zeros(shape, dtype=bool)
    valid = np.zeros(shape, dtype=bool)
    for si, sym in enumerate(symbols):
        for open_ms, rec in rows[sym].items():
            if open_ms % DAY_MS:
                raise C013IntegrityError(f'NON_DAY_BOUNDARY_OPEN:{sym}:{open_ms}')
            d = (open_ms - PANEL_DAY0_MS) // DAY_MS
            day = index_day(d)
            refuse_protected_day(day)
            if d < 0 or d >= n_days:
                raise C013IntegrityError(f'DAY_OUTSIDE_PANEL:{sym}:{day.isoformat()}')
            if present[si, d]:
                raise C013IntegrityError(f'DUPLICATE_DAY:{sym}:{day.isoformat()}')
            o, h, l, c, qv = (float(x) for x in rec)
            present[si, d] = True
            if well_formed(o, h, l, c, qv):
                valid[si, d] = True
                for k, v in zip(('O', 'H', 'L', 'C', 'QV'), (o, h, l, c, qv)):
                    arrs[k][si, d] = v
    first = np.full(len(symbols), -1, dtype=np.int64)
    last = np.full(len(symbols), -1, dtype=np.int64)
    for si in range(len(symbols)):
        idx = np.flatnonzero(present[si])
        if idx.size:
            first[si], last[si] = idx[0], idx[-1]
    return Panel(symbols, arrs['O'], arrs['H'], arrs['L'], arrs['C'], arrs['QV'],
                 present, valid, present & ~valid, first, last, n_days)


# ---------------------------------------------------------------------------
# Ranks and correlations


def average_ranks(values: Sequence[float]) -> np.ndarray:
    """1-based average ranks; ties share the mean of their positions."""

    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size == 0 or not np.all(np.isfinite(arr)):
        raise C013IntegrityError('RANK_INPUT')
    order = np.argsort(arr, kind='mergesort')
    ranks = np.empty(arr.size, dtype=np.float64)
    s = arr[order]
    i = 0
    while i < arr.size:
        j = i + 1
        while j < arr.size and s[j] == s[i]:
            j += 1
        ranks[order[i:j]] = 0.5 * ((i + 1) + j)
        i = j
    return ranks


def pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    x = x - x.mean()
    y = y - y.mean()
    den = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
    if not den > 0:
        return None
    return float((x * y).sum() / den)


def ols_residual(y: np.ndarray, regressors: Sequence[np.ndarray]) -> np.ndarray | None:
    """Residual of y on [1, regressors...]; None if the design is rank deficient."""

    X = np.column_stack([np.ones(y.size)] + [np.asarray(r, dtype=np.float64) for r in regressors])
    if np.linalg.matrix_rank(X) < X.shape[1]:
        return None
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


# ---------------------------------------------------------------------------
# Predictor side (bars <= t-1 only)


def bar_clv(o: float, h: float, l: float, c: float) -> float | None:
    """(2C - H - L) / (H - L); None for a zero-range bar."""

    if not h > l:
        return None
    return (2.0 * c - h - l) / (h - l)


@dataclass
class PredictorState:
    t: int
    eligible_n: int
    selected: list[int]            # symbol indices, liquidity order
    clv: dict[int, float]
    trail_ret: dict[int, float]
    trail_range: dict[int, float]
    qv30: dict[int, float]


def _prefix(a: np.ndarray) -> np.ndarray:
    return np.concatenate([np.zeros((a.shape[0], 1)), np.cumsum(a, axis=1, dtype=np.float64)], axis=1)


def _caches(p: Panel) -> dict[str, np.ndarray]:
    cache = getattr(p, '_c013_cache', None)
    if cache is None:
        qv0 = np.where(p.valid, np.nan_to_num(p.QV, nan=0.0), 0.0)
        ranged = p.valid & (np.nan_to_num(p.H, nan=0.0) > np.nan_to_num(p.L, nan=0.0))
        cache = {'VALID': _prefix(p.valid.astype(np.float64)), 'RANGED': _prefix(ranged.astype(np.float64)),
                 'QV': _prefix(qv0)}
        p._c013_cache = cache
    return cache


def trailing_quote_volume(p: Panel, si: int, t: int, window: int) -> float:
    """Sum of quote volume over valid bars with day in [t-window, t-1]; missing = not traded."""

    q = _caches(p)['QV']
    return float(q[si, t] - q[si, max(0, t - window)])


def predictor_state(p: Panel, t: int, prm: Mapping[str, Any], *, K: int, N: int,
                    excluded: frozenset[str]) -> PredictorState:
    """Eligibility, top-N selection and predictor/controls at decision day t.

    Reads only bars with day index < t.
    """

    age = int(prm['LISTING_AGE_DAYS'])
    window = int(prm['LIQUIDITY_WINDOW_DAYS'])
    if t - K < 0 or t > p.n_days:
        raise C013IntegrityError('DECISION_DAY_OUTSIDE_PANEL')
    c = _caches(p)
    lo = max(0, t - window)
    qv_all = c['QV'][:, t] - c['QV'][:, lo]
    ok = ((c['VALID'][:, t] - c['VALID'][:, t - K]) == K) & ((c['RANGED'][:, t] - c['RANGED'][:, t - K]) > 0)
    ok &= (p.first_day >= 0) & (p.first_day <= t - age)
    eligible = [si for si in np.flatnonzero(ok).tolist() if p.symbols[si] not in excluded]
    ranked = sorted(eligible, key=lambda si: (-float(qv_all[si]), p.symbols[si]))
    selected = ranked[:N] if len(ranked) >= N else []
    clv, tr, trg = {}, {}, {}
    for si in selected:
        vals = [bar_clv(p.O[si, d], p.H[si, d], p.L[si, d], p.C[si, d]) for d in range(t - K, t)]
        vals = [v for v in vals if v is not None]
        clv[si] = float(np.mean(vals))
        tr[si] = float(np.sum(np.log(p.C[si, t - K:t] / p.O[si, t - K:t])))
        trg[si] = float(np.sum(np.log(p.H[si, t - K:t] / p.L[si, t - K:t])))
    return PredictorState(t, len(eligible), selected, clv, tr, trg, {si: float(qv_all[si]) for si in selected})


# ---------------------------------------------------------------------------
# Target side (bars t+OFFSET .. t+OFFSET+H-1 only)


@dataclass
class TargetRow:
    wick: float
    ret_win: float
    range_win: float


def target_row(p: Panel, si: int, start: int, H: int, legal_last: int) -> TargetRow | str:
    """Target for one symbol, or a missingness reason string."""

    end = start + H - 1
    if end > legal_last:
        raise ProtectedDataRefused('TARGET_BEYOND_LEGAL_END')
    days = range(start, end + 1)
    for d in days:
        if not p.present[si, d]:
            return 'MISSING_BAR'
        if p.malformed[si, d]:
            return 'MALFORMED_BAR'
        if d == p.last_day[si] and p.last_day[si] < legal_last:
            return 'DELISTING_DAY_BAR'
    o, h, l, c = (a[si, start:end + 1] for a in (p.O, p.H, p.L, p.C))
    wick = float(np.sum(np.log(h / o) - np.log(o / l)))
    return TargetRow(wick, float(np.sum(np.log(c / o))), float(np.sum(np.log(h / l))))


# ---------------------------------------------------------------------------
# Daily statistics


def volume_terciles(qv: Sequence[float], names: Sequence[str]) -> list[np.ndarray]:
    """Positions split into three date-local strata by descending volume (ties by name)."""

    n = len(qv)
    order = sorted(range(n), key=lambda i: (-qv[i], names[i]))
    return [np.asarray(order[(g * n) // 3:((g + 1) * n) // 3], dtype=np.int64) for g in range(3)]


def stratified_permutations(strata: Sequence[np.ndarray], n: int, B: int,
                            rng: np.random.Generator) -> np.ndarray:
    """B x n index matrix; each row permutes positions within each stratum only."""

    out = np.tile(np.arange(n, dtype=np.int64), (B, 1))
    for pos in strata:
        if pos.size > 1:
            out[:, pos] = rng.permuted(np.tile(pos, (B, 1)), axis=1)
    return out


def date_rng(seed: int, variant_index: int, t_ordinal: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, variant_index, t_ordinal])))


@dataclass
class DailyStat:
    rho: float
    rho_ctrl: float | None
    null_rho: np.ndarray | None
    null_ctrl: np.ndarray | None
    n: int


def daily_statistic(ps: PredictorState, targets: Mapping[int, TargetRow], names: Sequence[str],
                    *, B: int, rng: np.random.Generator | None, controls: bool) -> DailyStat | str:
    """Spearman(CLV rank, WICK_RESID rank) over the analysis set, its controlled
    partial version, and B stratified-permutation null values. Returns a reason
    string when the date is not valid."""

    A = [si for si in ps.selected if si in targets]
    wick = np.array([targets[si].wick for si in A])
    resid = ols_residual(wick, [np.array([targets[si].ret_win for si in A]),
                                np.array([targets[si].range_win for si in A])])
    if resid is None:
        return 'REGRESSION_DEGENERATE'
    rx = average_ranks([ps.clv[si] for si in A])
    ry = average_ranks(resid)
    rho = pearson(rx, ry)
    if rho is None:
        return 'ZERO_RANK_VARIANCE'
    rho_ctrl = xp = yp = None
    if controls:
        ctrl = [average_ranks([ps.trail_ret[si] for si in A]),
                average_ranks([ps.trail_range[si] for si in A]),
                average_ranks([ps.qv30[si] for si in A])]
        xp, yp = ols_residual(rx, ctrl), ols_residual(ry, ctrl)
        if xp is None or yp is None:
            return 'CONTROL_REGRESSION_DEGENERATE'
        rho_ctrl = pearson(xp, yp)
        if rho_ctrl is None:
            return 'ZERO_CONTROLLED_VARIANCE'
    null_rho = null_ctrl = None
    if B:
        strata = volume_terciles([ps.qv30[si] for si in A], [names[si] for si in A])
        perms = stratified_permutations(strata, len(A), B, rng)
        null_rho = _corr_rows(rx[perms], ry)
        if controls:
            null_ctrl = _corr_rows(xp[perms], yp)
    return DailyStat(rho, rho_ctrl, null_rho, null_ctrl, len(A))


def _corr_rows(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Pearson correlation of each row of X with y. Permutation leaves row
    variance unchanged, so the denominator is shared."""

    xc = X - X.mean(axis=1, keepdims=True)
    yc = y - y.mean()
    den = math.sqrt(float((xc[0] ** 2).sum()) * float((yc ** 2).sum()))
    return (xc @ yc) / den


# ---------------------------------------------------------------------------
# Aggregation


def iso_weeks(first_monday: date, n_weeks: int) -> list[date]:
    if first_monday.weekday() != 0:
        raise C013IntegrityError('FIRST_WEEK_NOT_MONDAY')
    return [first_monday + timedelta(days=7 * k) for k in range(n_weeks)]


def weekly_means(daily: Mapping[date, float], mondays: Sequence[date], min_days: int) -> dict[date, float]:
    out: dict[date, float] = {}
    for m in mondays:
        vals = [daily[m + timedelta(days=j)] for j in range(7) if (m + timedelta(days=j)) in daily]
        if len(vals) >= min_days:
            out[m] = float(np.mean(vals))
    return out


def weekly_means_matrix(null_daily: Mapping[date, np.ndarray], mondays: Sequence[date],
                        valid_weeks: Sequence[date]) -> np.ndarray:
    """Null weekly means for the same valid weeks and the same valid days. Shape W x B."""

    rows = []
    for m in valid_weeks:
        days = [m + timedelta(days=j) for j in range(7) if (m + timedelta(days=j)) in null_daily]
        rows.append(np.mean(np.stack([null_daily[d] for d in days]), axis=0))
    return np.stack(rows)


def sign(x: float) -> int:
    if not math.isfinite(x):
        raise C013IntegrityError('SIGN_NONFINITE')
    return 1 if x > 0 else -1 if x < 0 else 0


def two_sided_p(observed: float, null: np.ndarray) -> dict[str, float]:
    """Rank p with +1 correction; the observed value is 'inside the central 95%'
    exactly when P_TWO_SIDED > alpha."""

    B = int(null.size)
    lo = (1 + int((null <= observed).sum())) / (B + 1)
    hi = (1 + int((null >= observed).sum())) / (B + 1)
    return {'P_LOWER': lo, 'P_UPPER': hi, 'P_TWO_SIDED': min(1.0, 2.0 * min(lo, hi)),
            'NULL_Q025': float(np.quantile(null, 0.025, method='linear')),
            'NULL_Q975': float(np.quantile(null, 0.975, method='linear')),
            'NULL_MEAN': float(null.mean())}


def newey_west_t(series: Sequence[float], lag: int) -> float | None:
    x = np.asarray(series, dtype=np.float64)
    T = x.size
    if T <= lag + 1:
        return None
    xc = x - x.mean()
    lrv = float((xc * xc).sum() / T)
    for l in range(1, lag + 1):
        lrv += 2.0 * (1.0 - l / (lag + 1)) * float((xc[l:] * xc[:-l]).sum() / T)
    if not lrv > 0:
        return None
    return float(x.mean() / math.sqrt(lrv / T))


def holm(pvalues: Mapping[str, float]) -> dict[str, float]:
    items = sorted(pvalues.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(items)
    out: dict[str, float] = {}
    running = 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


# ---------------------------------------------------------------------------
# Variant run


def variant_id(K: int, H: int, N: int) -> str:
    return f'K{K}_H{H}_N{N}'


def decision_days(prm: Mapping[str, Any], H: int, offset: int) -> list[int]:
    first = day_index(date.fromisoformat(prm['FIRST_DECISION_DATE']))
    last = day_index(date.fromisoformat(prm['LAST_DECISION_DATE']))
    legal_last = day_index(date.fromisoformat(prm['LEGAL_LAST_BAR_DATE']))
    return [t for t in range(first, last + 1) if t + offset + H - 1 <= legal_last]


def run_variant(p: Panel, prm: Mapping[str, Any], *, K: int, H: int, N: int, offset: int,
                variant_index: int, B: int, controls: bool, excluded: frozenset[str]) -> dict[str, Any]:
    legal_last = day_index(date.fromisoformat(prm['LEGAL_LAST_BAR_DATE']))
    min_n = int(math.ceil(float(prm['MIN_ANALYSIS_FRACTION']) * N))
    daily: dict[date, float] = {}
    daily_ctrl: dict[date, float] = {}
    null_daily: dict[date, np.ndarray] = {}
    null_ctrl_daily: dict[date, np.ndarray] = {}
    invalid: dict[str, int] = {}
    missing: dict[str, int] = {}
    selected_name_days = 0
    universe_digest = hashlib.sha256()
    for t in decision_days(prm, H, offset):
        day = index_day(t)
        ps = predictor_state(p, t, prm, K=K, N=N, excluded=excluded)
        universe_digest.update(json.dumps([day.isoformat(), [p.symbols[s] for s in ps.selected]],
                                          separators=(',', ':')).encode())
        if not ps.selected:
            invalid['UNIVERSE_SHORT'] = invalid.get('UNIVERSE_SHORT', 0) + 1
            continue
        selected_name_days += len(ps.selected)
        targets: dict[int, TargetRow] = {}
        for si in ps.selected:
            row = target_row(p, si, t + offset, H, legal_last)
            if isinstance(row, str):
                missing[row] = missing.get(row, 0) + 1
            else:
                targets[si] = row
        if len(targets) < min_n:
            invalid['ANALYSIS_SHORT'] = invalid.get('ANALYSIS_SHORT', 0) + 1
            continue
        rng = date_rng(int(prm['SEED']), variant_index, day.toordinal()) if B else None
        st = daily_statistic(ps, targets, p.symbols, B=B, rng=rng, controls=controls)
        if isinstance(st, str):
            invalid[st] = invalid.get(st, 0) + 1
            continue
        daily[day] = st.rho
        if controls:
            daily_ctrl[day] = st.rho_ctrl
        if B:
            null_daily[day] = st.null_rho
            if controls:
                null_ctrl_daily[day] = st.null_ctrl
    mondays = iso_weeks(date.fromisoformat(prm['FIRST_WEEK_MONDAY']), int(prm['N_WEEKS']))
    weekly = weekly_means(daily, mondays, int(prm['MIN_VALID_DAYS_PER_WEEK']))
    valid_weeks = sorted(weekly)
    out: dict[str, Any] = {
        'VARIANT': variant_id(K, H, N), 'K': K, 'H': H, 'N': N, 'TARGET_OFFSET_DAYS': offset,
        'DECISION_DAYS': len(decision_days(prm, H, offset)), 'VALID_DAYS': len(daily),
        'INVALID_DAYS_BY_REASON': dict(sorted(invalid.items())),
        'SELECTED_NAME_DAYS': selected_name_days,
        'MISSING_TARGET_BY_REASON': dict(sorted(missing.items())),
        'MISSING_TARGET_RATE': (sum(missing.values()) / selected_name_days) if selected_name_days else None,
        'UNIVERSE_IDENTITY_DIGEST': universe_digest.hexdigest(),
        'VALID_WEEKS': len(valid_weeks),
        'VALID_WEEKS_BY_YEAR': _count_by_year(valid_weeks),
        'WEEKLY_SERIES': [[m.isoformat(), weekly[m]] for m in valid_weeks],
    }
    if not valid_weeks:
        out['POOLED'] = None
        return out
    pooled = float(np.mean([weekly[m] for m in valid_weeks]))
    out['POOLED'] = pooled
    out['YEARLY'] = _yearly(weekly)
    if B:
        null_w = weekly_means_matrix(null_daily, mondays, valid_weeks)
        out['NULL'] = two_sided_p(pooled, null_w.mean(axis=0))
    if controls:
        wc = weekly_means(daily_ctrl, mondays, int(prm['MIN_VALID_DAYS_PER_WEEK']))
        if sorted(wc) != valid_weeks:
            raise C013IntegrityError('CONTROLLED_WEEK_MASK_DIVERGED')
        pc = float(np.mean([wc[m] for m in valid_weeks]))
        out['CONTROLLED'] = {'POOLED': pc}
        if B:
            out['CONTROLLED']['NULL'] = two_sided_p(pc, weekly_means_matrix(null_ctrl_daily, mondays, valid_weeks).mean(axis=0))
    return out


def _count_by_year(weeks: Sequence[date]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in weeks:
        out[str(m.year)] = out.get(str(m.year), 0) + 1
    return dict(sorted(out.items()))


def _yearly(weekly: Mapping[date, float]) -> dict[str, float]:
    by: dict[int, list[float]] = {}
    for m, v in weekly.items():
        by.setdefault(m.year, []).append(v)
    return {str(y): float(np.mean(v)) for y, v in sorted(by.items())}


# ---------------------------------------------------------------------------
# Gates and classification


def evaluate(primary: Mapping[str, Any], adjacency: Mapping[str, Any], secondary: Sequence[Mapping[str, Any]],
             prm: Mapping[str, Any], *, identity_ok: bool, identity_reasons: Sequence[str] = ()) -> dict[str, Any]:
    """Frozen gates and classification. Pure function of the variant summaries."""

    alpha = float(prm['PRIMARY_ALPHA'])
    direction = int(prm['PRIMARY_EFFECT_DIRECTION_SIGN'])
    years = list(prm['STABILITY_YEARS'])
    out: dict[str, Any] = {'IDENTITY_OK': bool(identity_ok), 'IDENTITY_REASONS': list(identity_reasons)}
    support_reasons = []
    if primary.get('VALID_WEEKS', 0) < int(prm['MIN_VALID_WEEKS']):
        support_reasons.append('VALID_WEEKS_BELOW_MIN')
    by_year = primary.get('VALID_WEEKS_BY_YEAR', {})
    if any(by_year.get(y, 0) < int(prm['MIN_VALID_WEEKS_PER_YEAR']) for y in years):
        support_reasons.append('YEAR_WEEKS_BELOW_MIN')
    rate = primary.get('MISSING_TARGET_RATE')
    if rate is None or rate > float(prm['MAX_MISSING_TARGET_RATE']):
        support_reasons.append('MISSING_TARGET_RATE_ABOVE_MAX')
    if primary.get('POOLED') is None or 'NULL' not in primary or 'CONTROLLED' not in primary:
        support_reasons.append('PRIMARY_NOT_COMPUTABLE')
    out['SUPPORT_PASS'] = not support_reasons
    out['SUPPORT_REASONS'] = support_reasons
    gates = {'STATISTICAL_GATE': False, 'DIRECTION_GATE': False, 'TEMPORAL_GATE': False,
             'CONTROL_GATE': False, 'DEPENDENCE_GATE': False, 'ADJACENCY_GATE': False}
    reasons: list[str] = []
    if identity_ok and out['SUPPORT_PASS']:
        pooled = float(primary['POOLED'])
        s = sign(pooled)
        p = float(primary['NULL']['P_TWO_SIDED'])
        gates['STATISTICAL_GATE'] = p <= alpha
        gates['DIRECTION_GATE'] = s == direction
        yearly = primary['YEARLY']
        sharing = [y for y in years if y in yearly and s != 0 and sign(float(yearly[y])) == s]
        out['YEARS_SHARING_POOLED_SIGN'] = sharing
        gates['TEMPORAL_GATE'] = s != 0 and len(sharing) >= int(prm['MIN_YEARS_SHARING_SIGN'])
        ctrl = primary['CONTROLLED']
        gates['CONTROL_GATE'] = (float(ctrl['NULL']['P_TWO_SIDED']) <= alpha and s != 0
                                 and sign(float(ctrl['POOLED'])) == s)
        series = [v for _, v in primary['WEEKLY_SERIES']]
        t = newey_west_t(series, int(prm['HAC_LAG_WEEKS']))
        out['HAC_T'] = t
        gates['DEPENDENCE_GATE'] = (t is not None and abs(t) >= float(prm['HAC_CRITICAL_ABS_T'])
                                    and sign(t) == s and s != 0)
        adj = adjacency.get('POOLED')
        adj_ok = (adj is not None and adjacency.get('VALID_WEEKS', 0) >= int(prm['MIN_VALID_WEEKS']))
        gates['ADJACENCY_GATE'] = bool(adj_ok and s != 0 and sign(float(adj)) == s)
        if not adj_ok:
            reasons.append('ADJACENCY_NOT_COMPUTABLE')
        for k, v in gates.items():
            if not v:
                reasons.append(k + '_FAILED')
        if gates['STATISTICAL_GATE'] and s == -direction:
            reasons.append('OPPOSITE_DIRECTION_OUTSIDE_NULL')
    out['GATES'] = gates
    if not identity_ok:
        cls = 'INVALID_DISCOVERY'
    elif not out['SUPPORT_PASS']:
        cls = 'INCONCLUSIVE_DISCOVERY'
    elif all(gates.values()):
        cls = 'PROMISING_PROTOTYPE'
    else:
        cls = 'NO_USEFUL_STRUCTURE'
    out['CLASSIFICATION'] = cls
    out['REASONS'] = reasons
    grid = {v['VARIANT']: float(v['NULL']['P_TWO_SIDED']) for v in secondary
            if v.get('POOLED') is not None and 'NULL' in v}
    out['SECONDARY_HOLM_P'] = holm(grid) if grid else {}
    out['SECONDARY_CAN_CHANGE_CLASSIFICATION'] = False
    return out


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def run_all(p: Panel, prm: Mapping[str, Any], *, excluded: frozenset[str], identity: Mapping[str, Any],
            identity_ok: bool, identity_reasons: Sequence[str] = ()) -> dict[str, Any]:
    """Primary, adjacency diagnostic and secondary grid, then frozen evaluation."""

    B = int(prm['PERMUTATIONS'])
    pv = prm['PRIMARY_VARIANT']
    primary = run_variant(p, prm, K=pv['K'], H=pv['H'], N=pv['N'], offset=0, variant_index=0,
                          B=B, controls=True, excluded=excluded)
    adjacency = run_variant(p, prm, K=pv['K'], H=1, N=pv['N'], offset=int(prm['ADJACENCY_OFFSET_DAYS']),
                            variant_index=int(prm['ADJACENCY_VARIANT_INDEX']), B=0, controls=False, excluded=excluded)
    secondary = []
    for v in prm['SECONDARY_VARIANTS']:
        secondary.append(run_variant(p, prm, K=v['K'], H=v['H'], N=v['N'], offset=0,
                                     variant_index=int(v['VARIANT_INDEX']), B=B, controls=False,
                                     excluded=excluded))
    evaluation = evaluate(primary, adjacency, secondary, prm, identity_ok=identity_ok,
                          identity_reasons=identity_reasons)
    return {'SCHEMA': SCHEMA, 'HYPOTHESIS_ID': prm['HYPOTHESIS_ID'], 'TEST_FAMILY_ID': prm['TEST_FAMILY_ID'],
            'IDENTITY': dict(identity), 'PRIMARY': primary, 'ADJACENCY_DIAGNOSTIC': adjacency,
            'SECONDARY_GRID': secondary, 'EVALUATION': evaluation,
            'NUMPY_VERSION': np.__version__,
            'PROTECTED_2025_2026_OPENED': False}
