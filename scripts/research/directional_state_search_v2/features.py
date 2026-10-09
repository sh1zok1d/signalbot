"""Past-only states on the dense 5m grid (index i = anchor bar; T = close of bar i). No outcome is used here.

Every state at i uses bars <= i only. R_1H is built separately in sample.py.
"""
from __future__ import annotations

import numpy as np

from scripts.research.rp4h_bitmex_temporal_v1.parent import features as parent_features

from . import constants as K


def _nan(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=np.float64)


def _csum(v: np.ndarray) -> np.ndarray:
    out = np.zeros(v.size + 1, dtype=np.float64)
    np.cumsum(v, out=out[1:])
    return out


def window_sum(v: np.ndarray, w: int) -> np.ndarray:
    """sum of v[i-w+1 .. i] at i (NaN for i < w-1); v must be finite."""
    c = _csum(v)
    out = _nan(v.size)
    out[w - 1:] = c[w:] - c[:-w]
    return out


def log_returns(close: np.ndarray) -> np.ndarray:
    r = _nan(close.size)
    r[1:] = np.log(close[1:] / close[:-1])
    return r


def baseline(bars: dict) -> dict:
    """RP4H, RET_4H, RV_4H, width, R_1H exactly as the RANGE_POSITION_4H units (parent code imported)."""
    return parent_features(bars["high"], bars["low"], bars["close"])


def ret_n(close: np.ndarray, n: int) -> np.ndarray:
    out = _nan(close.size)
    out[n:] = np.log(close[n:] / close[:-n])
    return out


# ---------------------------------------------------------------- F1 SIGNED_PATH_ASYMMETRY
def spa_family(close: np.ndarray, w: int = K.LOOKBACK_24H) -> dict:
    r = np.nan_to_num(log_returns(close))           # r[0] = 0 only affects i < w
    pos = np.where(r > 0, r * r, 0.0)
    neg = np.where(r < 0, r * r, 0.0)
    rs_p, rs_n = window_sum(pos, w), window_sum(neg, w)
    n_up = window_sum((r > 0).astype(np.float64), w)
    n_dn = window_sum((r < 0).astype(np.float64), w)
    tot = rs_p + rs_n
    with np.errstate(invalid="ignore", divide="ignore"):
        spa = np.where(tot > 0, (rs_p - rs_n) / tot, np.nan)
        upf = np.where(n_up + n_dn > 0, (n_up - n_dn) / (n_up + n_dn), np.nan)
    rv = np.sqrt(tot)
    spa[: w] = np.nan
    upf[: w] = np.nan
    rv[: w] = np.nan
    return {"SPA_24H": spa, "UPFRAC_24H": upf, "RV_24H": rv, "RET_24H": ret_n(close, w)}


def windows(a: np.ndarray, idx: np.ndarray, w: int) -> np.ndarray:
    """a[i-w+1 .. i] for each anchor i in idx, shape (len(idx), w). Requires idx >= w-1."""
    return a[idx[:, None] + np.arange(-w + 1, 1)[None, :]]


def chunked(idx: np.ndarray, fn, size: int = 20_000) -> dict:
    parts = [fn(idx[s:s + size]) for s in range(0, idx.size, size)]
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


# ---------------------------------------------------------------- F2 PATH_OCCUPANCY_RESIDUAL
def occupancy(bars: dict, idx: np.ndarray) -> dict:
    """Box = the RP4H box (48 bars i-47..i). p_k = (close_k - L)/(H - L) for the 47 closes k = i-47..i-1 (the current
    close, i.e. RP4H itself, is excluded). OCC_MEAN_4H = mean p_k; OCC_THIRDS_4H = share(p_k >= 2/3) - share(p_k <= 1/3)."""
    def fn(ix):
        hi = windows(bars["high"], ix, K.LOOKBACK_4H).max(axis=1)
        lo = windows(bars["low"], ix, K.LOOKBACK_4H).min(axis=1)
        c = windows(bars["close"], ix, K.LOOKBACK_4H)[:, :-1]
        span = hi - lo
        with np.errstate(invalid="ignore", divide="ignore"):
            p = (c - lo[:, None]) / span[:, None]
        ok = span > 0
        mean = np.where(ok, p.mean(axis=1), np.nan)
        thirds = np.where(ok, (p >= 2.0 / 3.0).mean(axis=1) - (p <= 1.0 / 3.0).mean(axis=1), np.nan)
        return {"OCC_MEAN_4H": mean, "OCC_THIRDS_4H": thirds}
    return chunked(idx, fn)


# ---------------------------------------------------------------- F4 COUNTERMOVE_DECAY
def countermove(bars: dict, idx: np.ndarray) -> dict:
    """Bars i-287..i in six chronological 4h segments of 48 bars. In segment s:
    DD_s = max over bars of [log running-max high (within s, up to the bar) - log low]  (largest down-countermove);
    RU_s = max over bars of [log high - log running-min low (within s, up to the bar)]  (largest up-move).
    CMD_UP_24H = [mean log RU (segments 5,6) - mean log RU (segments 1,2)] - [same for DD].
    Positive = down-countermoves shrank relative to up-moves from the first 8h to the last 8h of the 24h window."""
    def fn(ix):
        h = np.log(windows(bars["high"], ix, K.LOOKBACK_24H)).reshape(-1, 6, 48)
        l = np.log(windows(bars["low"], ix, K.LOOKBACK_24H)).reshape(-1, 6, 48)
        dd = (np.maximum.accumulate(h, axis=2) - l).max(axis=2)
        ru = (h - np.minimum.accumulate(l, axis=2)).max(axis=2)
        ok = (dd[:, [0, 1, 4, 5]] > 0).all(axis=1) & (ru[:, [0, 1, 4, 5]] > 0).all(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ldd, lru = np.log(dd), np.log(ru)
            d_ru = lru[:, 4:6].mean(axis=1) - lru[:, 0:2].mean(axis=1)
            d_dd = ldd[:, 4:6].mean(axis=1) - ldd[:, 0:2].mean(axis=1)
        return {"CMD_UP_24H": np.where(ok, d_ru - d_dd, np.nan)}
    return chunked(idx, fn)


# ---------------------------------------------------------------- F7 EFFORT_TO_RESULT (price response to aggressive flow)
def flow_family(bars: dict) -> dict:
    """f_k = 2*takerBuyQuote_k - quote_k (signed aggressive notional, USDT); r_k = 5m log return.
    lambda(window) = sum r f / sum f^2 (OLS slope through the origin); side-split slopes use bars with f > 0 (buy) or
    f < 0 (sell) only. recent = bars i-47..i (48), prior = bars i-287..i-48 (240).
    IMB_4H = sum f / sum quote over the recent 48 bars (the flow itself; mandatory nuisance).
    LOG_LAMBDA_4H = log lambda_recent (the response level; sensitivity control only).
    FLOW_RESPONSE_CHANGE_4H = sign(sum f recent) * log(lambda_recent / lambda_prior)   (both slopes > 0, else NaN).
    SIDE_ASYM_CHANGE_4H = log(lambda_buy/lambda_sell)_recent - log(lambda_buy/lambda_sell)_prior (all four > 0)."""
    r = np.nan_to_num(log_returns(bars["close"]))
    f = 2.0 * bars["tbq"] - bars["quote"]
    q = bars["quote"]
    buy, sell = f > 0, f < 0
    rf, ff = r * f, f * f

    def recent_prior(v):
        s48 = window_sum(v, K.LOOKBACK_4H)
        s288 = window_sum(v, K.LOOKBACK_24H)
        return s48, s288 - s48

    rf_r, rf_p = recent_prior(rf)
    ff_r, ff_p = recent_prior(ff)
    rfb_r, rfb_p = recent_prior(np.where(buy, rf, 0.0))
    ffb_r, ffb_p = recent_prior(np.where(buy, ff, 0.0))
    rfs_r, rfs_p = recent_prior(np.where(sell, rf, 0.0))
    ffs_r, ffs_p = recent_prior(np.where(sell, ff, 0.0))
    f_r, _ = recent_prior(f)
    q_r, _ = recent_prior(q)
    with np.errstate(invalid="ignore", divide="ignore"):
        lam_r, lam_p = rf_r / ff_r, rf_p / ff_p
        lb_r, lb_p, ls_r, ls_p = rfb_r / ffb_r, rfb_p / ffb_p, rfs_r / ffs_r, rfs_p / ffs_p
        frc = np.where((lam_r > 0) & (lam_p > 0) & (f_r != 0), np.sign(f_r) * np.log(lam_r / lam_p), np.nan)
        ok = (lb_r > 0) & (lb_p > 0) & (ls_r > 0) & (ls_p > 0)
        sac = np.where(ok, np.log(lb_r / ls_r) - np.log(lb_p / ls_p), np.nan)
        imb = np.where(q_r > 0, f_r / q_r, np.nan)
        loglam = np.where(lam_r > 0, np.log(lam_r), np.nan)
    for a in (frc, sac, imb, loglam):
        a[: K.LOOKBACK_24H] = np.nan
    return {"FLOW_RESPONSE_CHANGE_4H": frc, "SIDE_ASYM_CHANGE_4H": sac, "IMB_4H": imb, "LOG_LAMBDA_4H": loglam}


# ---------------------------------------------------------------- F3 REJECTION_DECAY (24h box at T; no structural level)
def _wall_decay(contact: np.ndarray, retreat: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Rows = anchors, columns = bars of the window in time order.
    contact: bar touches the wall zone; retreat: bar close has left the zone by the gate; depth: per-bar distance from
    the wall (box units). An episode starts at a contact bar with no earlier contact, or with a retreat close strictly
    after the previous contact bar. The rejection completed before episode e (e >= 2) is the max depth over the bars
    strictly between the previous contact bar and the start of e. Returns log(last / previous completed rejection)
    when at least two completed rejections exist, else NaN."""
    rows, cols = contact.shape
    last_contact = np.full(rows, -1)
    retreat_since = np.zeros(rows, dtype=bool)
    gap_max = np.full(rows, np.nan)
    n_rej = np.zeros(rows, dtype=np.int64)
    last_rej = np.full(rows, np.nan)
    prev_rej = np.full(rows, np.nan)
    for k in range(cols):
        c = contact[:, k]
        start = c & ((last_contact < 0) | retreat_since)
        completed = start & (last_contact >= 0)
        prev_rej = np.where(completed, last_rej, prev_rej)
        last_rej = np.where(completed, gap_max, last_rej)
        n_rej = n_rej + completed
        # update state after bar k
        gap_max = np.where(c, np.nan, np.fmax(gap_max, depth[:, k]) if k else depth[:, k])
        gap_max = np.where(c, np.nan, gap_max)
        retreat_since = np.where(c, False, retreat_since | retreat[:, k])
        last_contact = np.where(c, k, last_contact)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n_rej >= 2, np.log(last_rej / prev_rej), np.nan)


def rejection(bars: dict, idx: np.ndarray) -> dict:
    """24h box at T over bars i-287..i: H = max high, L = min low, positions in log box units.
    Upper wall: contact = high position >= 0.90; retreat gate = close position < 0.75; depth = 1 - low position.
    Lower wall: contact = low position <= 0.10; retreat gate = close position > 0.25; depth = high position.
    RP_24H = close position of bar i. REJ_DECAY_24H = -UD if RP_24H >= 0.5 else +LD (UD/LD = log ratio of the last two
    completed rejections at the upper/lower wall). Positive = the near upper wall's rejections shrink, or the near
    lower wall's rejections grow."""
    def fn(ix):
        h = np.log(windows(bars["high"], ix, K.LOOKBACK_24H))
        l = np.log(windows(bars["low"], ix, K.LOOKBACK_24H))
        c = np.log(windows(bars["close"], ix, K.LOOKBACK_24H))
        hi, lo = h.max(axis=1), l.min(axis=1)
        w = hi - lo
        ok = w > 0
        w = np.where(ok, w, np.nan)
        ph, pl, pc = (h - lo[:, None]) / w[:, None], (l - lo[:, None]) / w[:, None], (c - lo[:, None]) / w[:, None]
        ud = _wall_decay(ph >= 0.90, pc < 0.75, 1.0 - pl)
        ld = _wall_decay(pl <= 0.10, pc > 0.25, ph)
        rp24 = pc[:, -1]
        state = np.where(rp24 >= 0.5, -ud, ld)
        return {"REJ_DECAY_24H": np.where(ok, state, np.nan), "RP_24H": np.where(ok, rp24, np.nan)}
    return chunked(idx, fn)


# F5 FAILED_PROGRESS (progress per attempt) was abandoned before any outcome: the collision audit placed it inside the
# owner-closed divergence / selling-exhaustion line (catalog §6 price-only momentum divergence; E2's price leg). Not computed.
