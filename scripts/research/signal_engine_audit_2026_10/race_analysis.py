"""Audit analysis of the Level Engine chain on an independent re-implementation.
Inputs: Binance 5m 2020-01..2026-07 (events), OKX/Bybit 5m 2020-04..2024-12 (cross-venue, repo files).
Per event (real structural first touch and its half-rotation pseudo twin):
  T0: label (BREAK/REJECT/NEITHER within 48 bars), time to resolution, RV transition (12 bars pre vs 12 bars post, touch bar excluded),
  T15 (close of bar j+2): END_POSITION_X oriented toward BREAK in X units, Binance 15m move, OKX/Bybit 15m moves, OVMM, OVMM-Binance,
  B0 = driftless first-passage probabilities at T15 (Monte Carlo, fixed seed) for BREAK-first / REJECT-first / NEITHER in the remaining 46 bars.
Economics: (a) T0 bracket: stop at the first barrier hit, hold to the end of the 48-bar window, exit at close j+48 (or at the opposite barrier);
(b) T0 'toward BREAK' from close j; (c) T15 model-directed entry at close j+2, exit at first barrier or close j+48.  Costs applied per round trip.
Models among events unresolved at T15 and resolved later (the #363 support) and among all unresolved (3-class): walk-forward by year."""
import os, sys, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); from levels import *
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
REPO='/home/user/signalbot'
def load_venue(path):
    d=pd.read_csv(path); d['ts']=pd.to_datetime(d.open_ms,unit='ms',utc=True); return d.set_index('ts')['close']
def b0_probs(z0, w, s, tau, n=4000, seed=0):
    """driftless log-price walk from position z0 in [0,w] (0 = REJECT barrier, w = BREAK barrier), per-step std s, tau steps:
    returns P(BREAK first), P(REJECT first), P(neither)."""
    rng=np.random.default_rng(seed); steps=rng.standard_normal((n,tau))*s; path=z0+np.cumsum(steps,axis=1)
    hb=(path>=w).argmax(axis=1); hr=(path<=0).argmax(axis=1); anyb=(path>=w).any(axis=1); anyr=(path<=0).any(axis=1)
    tb=np.where(anyb,hb,10**9); tr=np.where(anyr,hr,10**9)
    pb=float((tb<tr).mean()); pr=float((tr<tb).mean()); return pb,pr,max(0.0,1-pb-pr)
def build_events(k, okx=None, byb=None, pseudo=True):
    L=level_instances(k); ev=first_touches(k,L); ev['kind']='real'
    rows=[ev]
    if pseudo:
        pp=pseudo_price(k,ev); pe=ev.copy(); pe['price']=pp; pe['real_j']=ev.j.values
        # pseudo touch: first bar of the same period intersecting the pseudo zone from the inside
        hi=k.high.values; lo=k.low.values; cl=k.close.values; idx=k.index; pos={t:i for i,t in enumerate(idx)}
        js=[]
        for r in pe.itertuples():
            a=pos.get(r.start); zl=r.price*(1-HW); zu=r.price*(1+HW); jj=None
            if a is not None and np.isfinite(r.price):
                end=min(a+{'DAY':288,'WEEK':2016,'MONTH':8928}[r.family],len(idx))
                for j in range(a,end):
                    if hi[j]>=zl and lo[j]<=zu:
                        inside = cl[j-1]<zl if r.side=='H' else cl[j-1]>zu
                        jj=j if inside else None; break
            js.append(jj)
        pe['j']=js; pe=pe.dropna(subset=['j']); pe['j']=pe.j.astype(int); pe['kind']='pseudo'; rows.append(pe)
    E=pd.concat(rows,ignore_index=True)
    lc=np.log(k.close.values); cl=k.close.values; r5=np.diff(lc,prepend=np.nan); out=[]
    for r in E.itertuples():
        j=int(r.j); o=outcomes(k,j,r.side,r.price)
        if o is None or j+HOLD+1>=len(k): continue
        X=o['X']; sgn=1 if r.side=='H' else -1   # BREAK direction in price: up for highs, down for lows
        lb=np.log(o['brk']); lr=np.log(o['rej']); w=abs(lb-lr)
        def zpos(lp): return (lp-lr)/(lb-lr)*w   # 0 at REJECT barrier, w at BREAK barrier (in log units)
        c0=lc[j]; c15=lc[j+2]
        # unresolved at T15? (no barrier hit in bars j+1, j+2)
        res15 = o['label'] in ('BREAK_FIRST','REJECT_FIRST','AMBIGUOUS') and o['t'] is not None and o['t']<=2
        end_x = (zpos(c15)-w/2)/X          # END_POSITION_X: signed position relative to the mid, in X units, + toward BREAK
        bin_mv = sgn*(c15-c0)/X
        rv_pre=np.sqrt(np.mean(r5[j-12:j]**2)); rv_post=np.sqrt(np.mean(r5[j+1:j+13]**2))
        rec=dict(kind=r.kind,family=r.family,side=r.side,level=r.price,j=j,ts=k.index[j],year=k.index[j].year,label=o['label'],t_res=o['t'],X=X,sig=o['sig'],
                 resolved_by_15=bool(res15),end_x=end_x,bin_mv=bin_mv,rv_trans=np.log(rv_post/rv_pre) if rv_pre>0 and rv_post>0 else np.nan,
                 ret_T0_toward_break=sgn*(lc[j+HOLD]-c0), ret_T15_toward_break=sgn*(lc[j+HOLD]-c15),
                 z15=zpos(c15), w=w)
        # cross-venue 15m moves (oriented toward BREAK, in X units)
        for name,ser in [('okx',okx),('byb',byb)]:
            if ser is None: rec[name+'_mv']=np.nan; continue
            t0=k.index[j]; t15=k.index[j+2]
            if t0 in ser.index and t15 in ser.index and ser[t0]>0 and ser[t15]>0: rec[name+'_mv']=sgn*(np.log(ser[t15])-np.log(ser[t0]))/X
            else: rec[name+'_mv']=np.nan
        # barrier-hit continuation for the bracket strategy: after the first hit (if resolved), log return from the barrier to close j+48
        if o['label'] in ('BREAK_FIRST','REJECT_FIRST'):
            tt=j+o['t']; bar_lp=lb if o['label']=='BREAK_FIRST' else lr; d=sgn if o['label']=='BREAK_FIRST' else -sgn
            # exit at the opposite barrier if hit afterwards, else at close j+48
            opp=lr if o['label']=='BREAK_FIRST' else lb; exit_lp=lc[j+HOLD]
            hi_=np.log(k.high.values[tt+1:j+HOLD+1]); lo_=np.log(k.low.values[tt+1:j+HOLD+1])
            if o['label']=='BREAK_FIRST':
                crossed=(lo_<=opp) if sgn==1 else (hi_>=opp)
            else:
                crossed=(hi_>=opp) if sgn==1 else (lo_<=opp)
            if crossed.any(): exit_lp=opp
            rec['bracket_ret']=d*(exit_lp-bar_lp); rec['bracket_dir_is_break']=(o['label']=='BREAK_FIRST')
        else: rec['bracket_ret']=0.0; rec['bracket_dir_is_break']=None
        out.append(rec)
    E2=pd.DataFrame(out); E2['ovmm']=E2[['okx_mv','byb_mv']].median(axis=1); E2['ovmm_diff']=E2['ovmm']-E2['bin_mv']
    # B0 at T15 for unresolved events
    pb=[];pr=[];pn=[]
    for r in E2.itertuples():
        if r.resolved_by_15 or not np.isfinite(r.z15): pb.append(np.nan);pr.append(np.nan);pn.append(np.nan); continue
        a,b,c=b0_probs(r.z15,r.w,r.sig,HOLD-2,n=3000,seed=int(r.j)%100000); pb.append(a);pr.append(b);pn.append(c)
    E2['b0_break']=pb;E2['b0_reject']=pr;E2['b0_neither']=pn
    return E2
if __name__=='__main__':
    k=load_btc(); okx=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/okx_btc_usdt_swap_5m.csv.gz')); byb=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/bybit_btcusdt_linear_5m.csv.gz'))
    E=build_events(k,okx,byb); E.to_pickle(os.path.join(os.path.dirname(__file__),'results','events.pkl')); print('events',E.kind.value_counts().to_dict())
    print(E.groupby('kind').label.value_counts(normalize=True).round(3))
