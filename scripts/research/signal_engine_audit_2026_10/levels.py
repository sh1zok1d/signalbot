"""Independent re-implementation of the Level Engine event object (structural first touch) for the audit.
Levels: previous UTC day high/low (PDH/PDL), previous ISO week high/low (PWH/PWL), previous calendar month high/low (PMH/PML),
built from Binance USD-M BTCUSDT 5m bars.  A level instance lives for the following day / week / month.  Touch = first bar whose
[low, high] intersects the zone [L(1-hw), L(1+hw)] while the previous close is on the inside (below a high, above a low).
Decision T = close of touch bar j; sigma = sample std of the 288 5m log returns before j; X = 0.5*1.2816*sigma*sqrt(48);
BREAK barrier = outer zone edge beyond the level (×(1+X) for highs, ×(1-X) for lows), REJECT barrier = inner zone edge the other way;
outcome over bars j+1..j+48 on high/low: BREAK_FIRST / REJECT_FIRST / NEITHER / AMBIGUOUS (both in one bar).
Pseudo level (half-rotation, following the frozen constructor as far as reported): see pseudo_price().  Everything is parameterised
so it can be aligned with the frozen definitions reported by the code audit."""
import os, numpy as np, pandas as pd
DATA_DIR=os.environ.get('XM_DATA_DIR','/tmp/claude-0/-home-user-signalbot/4d2253b8-11f7-5571-8d07-29099e51fb7c/scratchpad/data')
HW=0.0015; BARRIER_FRAC=0.5; CORR_Z=1.2816; HOLD=48; SIG_W=288
def load_btc():
    return pd.read_pickle(os.path.join(DATA_DIR,'btc5m.pkl'))
def level_instances(k):
    """returns DataFrame of level instances: family, side (H/L), price, start, end (exclusive), formed_from period"""
    idx=k.index; out=[]
    day=k.resample('1D').agg({'high':'max','low':'min'})
    for i in range(1,len(day)):
        s=day.index[i]; e=s+pd.Timedelta(days=1); out.append(('DAY','H',day.high.iloc[i-1],s,e)); out.append(('DAY','L',day.low.iloc[i-1],s,e))
    wk=k.resample('W-MON',label='left',closed='left').agg({'high':'max','low':'min'})   # ISO weeks starting Monday
    for i in range(1,len(wk)):
        s=wk.index[i]; e=s+pd.Timedelta(days=7); out.append(('WEEK','H',wk.high.iloc[i-1],s,e)); out.append(('WEEK','L',wk.low.iloc[i-1],s,e))
    mo=k.resample('MS').agg({'high':'max','low':'min'})
    for i in range(1,len(mo)):
        s=mo.index[i]; e=(s+pd.offsets.MonthBegin(1)); out.append(('MONTH','H',mo.high.iloc[i-1],s,e)); out.append(('MONTH','L',mo.low.iloc[i-1],s,e))
    L=pd.DataFrame(out,columns=['family','side','price','start','end']); L=L[np.isfinite(L.price)]; return L
def first_touches(k, L, hw=HW):
    """first touch of each level instance; returns one row per instance that was touched (touch_number=1)"""
    hi=k.high.values; lo=k.low.values; cl=k.close.values; idx=k.index; pos={t:i for i,t in enumerate(idx)}
    rows=[]
    for r in L.itertuples():
        a=pos.get(r.start); b=pos.get(min(r.end,idx[-1]+pd.Timedelta(minutes=5)),len(idx))
        if a is None: continue
        zl=r.price*(1-hw); zu=r.price*(1+hw)
        for j in range(a,b):
            if hi[j]>=zl and lo[j]<=zu:
                inside = cl[j-1]<zl if r.side=='H' else cl[j-1]>zu   # approach from the inside
                if not inside: break   # the period opened at/beyond the level: no legitimate first touch
                rows.append((r.family,r.side,r.price,r.start,j)); break
    return pd.DataFrame(rows,columns=['family','side','price','start','j'])
def pseudo_price(k, ev, mode='half_rotation'):
    """pseudo level: the real level price rotated by half of the previous day's range in the inside direction
    (i.e. a price with no structural meaning at a comparable distance); the pseudo touch is the first bar of the same period
    whose range intersects the pseudo zone from the inside."""
    day=k.resample('1D').agg({'high':'max','low':'min'}); rng=(day.high-day.low)
    pr=[]
    for r in ev.itertuples():
        d=rng.shift(1).reindex([r.start.floor('D')]).iloc[0]
        pr.append(r.price - 0.5*d if r.side=='H' else r.price + 0.5*d)
    return np.array(pr)
def outcomes(k, j, side, price, hw=HW, frac=BARRIER_FRAC, hold=HOLD):
    hi=k.high.values; lo=k.low.values; cl=k.close.values; lc=np.log(cl); n=len(k)
    if j<SIG_W+1 or j+hold>=n: return None
    r=np.diff(lc[j-SIG_W:j+1]); sig=r.std(ddof=1); X=frac*CORR_Z*sig*np.sqrt(hold)
    zl=price*(1-hw); zu=price*(1+hw)
    if side=='H': brk=zu*(1+X); rej=zl*(1-X)
    else: brk=zl*(1-X); rej=zu*(1+X)
    hit_b=None; hit_r=None
    for t in range(j+1,j+hold+1):
        hb = hi[t]>=brk if side=='H' else lo[t]<=brk
        hr = lo[t]<=rej if side=='H' else hi[t]>=rej
        if hb and hr: return dict(label='AMBIGUOUS',t=t-j,X=X,sig=sig,brk=brk,rej=rej)
        if hb: return dict(label='BREAK_FIRST',t=t-j,X=X,sig=sig,brk=brk,rej=rej)
        if hr: return dict(label='REJECT_FIRST',t=t-j,X=X,sig=sig,brk=brk,rej=rej)
    return dict(label='NEITHER',t=None,X=X,sig=sig,brk=brk,rej=rej)
