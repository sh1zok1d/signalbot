"""Structural first touches via the PRODUCT constructor beta.levels.structural_first_touches (parity-tested against the #352
research constructor), on Binance USD-M BTCUSDT 5m 2020-01..2026-07.  Outcomes, T15 features, cross-venue moves, B0 and
economics as in race_analysis.py.  Pseudo twins are added by pseudo.py once the frozen half-rotation definition is applied."""
import os, sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/signalbot'); sys.path.insert(0, os.path.dirname(__file__))
from beta import hist_series as hs, levels as LV
from race_analysis import load_venue, b0_probs, REPO
from levels import load_btc, HOLD
def bars_from_df(k):
    t=((k.index-pd.Timestamp(0,tz='UTC'))//pd.Timedelta('1ms')).values.astype('int64'); b=hs.empty_bars(int(t[0]),len(k))
    for dst,src in (('open','open'),('high','high'),('low','low'),('close','close'),('volume','volume'),('quote','quote_volume'),('taker_buy_quote','taker_buy_quote_volume')): getattr(b,dst)[:]=k[src].to_numpy(dtype=np.float64)
    return b
def scan(k, j, side, brk, rej, hold=HOLD):
    hi=k.high.values; lo=k.low.values
    for t in range(j+1, j+hold+1):
        hb = hi[t]>=brk if side>0 else lo[t]<=brk
        hr = lo[t]<=rej if side>0 else hi[t]>=rej
        if hb and hr: return 'AMBIGUOUS', t-j
        if hb: return 'BREAK_FIRST', t-j
        if hr: return 'REJECT_FIRST', t-j
    return 'NEITHER', None
def enrich(k, events, okx, byb, kind):
    lc=np.log(k.close.values); r5=np.diff(lc,prepend=np.nan); hiv=k.high.values; lov=k.low.values; out=[]
    for e in events:
        j=e['j']; side=e['side']; brk=e['break_barrier']; rej=e['reject_barrier']; X=e['x']; sig=e['sigma']
        if j<300 or j+HOLD+1>=len(k): continue
        label,t=scan(k,j,side,brk,rej)
        lb=np.log(brk); lr=np.log(rej); w=abs(lb-lr); c0=lc[j]; c15=lc[j+2]
        z15=(c15-lr)/(lb-lr)*w   # 0 at REJECT, w at BREAK
        res15 = t is not None and t<=2
        rv_pre=np.sqrt(np.mean(r5[j-12:j]**2)); rv_post=np.sqrt(np.mean(r5[j+1:j+13]**2))
        rec=dict(kind=kind,family=e['family'],lvl_kind=e['kind'],side=side,level=e['anchor_price'],j=j,ts=k.index[j],year=k.index[j].year,label=label,t_res=t,X=X,sig=sig,w=w,z15=z15,
                 resolved_by_15=bool(res15),end_x=(z15-w/2)/X,bin_mv=side*(c15-c0)/X,rv_trans=np.log(rv_post/rv_pre) if rv_pre>0 and rv_post>0 else np.nan,
                 ret_T0_toward_break=side*(lc[j+HOLD]-c0),ret_T15_toward_break=side*(lc[j+HOLD]-c15),event_id=e.get('event_id'))
        for name,ser in [('okx',okx),('byb',byb)]:
            t0=k.index[j]; t15=k.index[j+2]
            rec[name+'_mv']=side*(np.log(ser[t15])-np.log(ser[t0]))/X if (t0 in ser.index and t15 in ser.index and ser[t0]>0 and ser[t15]>0) else np.nan
        if label in ('BREAK_FIRST','REJECT_FIRST'):
            tt=j+t; isb=label=='BREAK_FIRST'; bar_lp=lb if isb else lr; d=side if isb else -side; opp=lr if isb else lb
            hi_=np.log(hiv[tt+1:j+HOLD+1]); lo_=np.log(lov[tt+1:j+HOLD+1])
            crossed=((lo_<=opp) if side>0 else (hi_>=opp)) if isb else ((hi_>=opp) if side>0 else (lo_<=opp))
            exit_lp=opp if crossed.any() else lc[j+HOLD]
            rec['bracket_ret']=d*(exit_lp-bar_lp); rec['bracket_is_break']=isb
            # entry slippage proxy: the barrier is a stop; realistic fill = first close at/after the hit bar
            rec['bracket_ret_closefill']=d*(exit_lp-lc[tt])
        else: rec['bracket_ret']=0.0; rec['bracket_is_break']=None; rec['bracket_ret_closefill']=0.0
        out.append(rec)
    E=pd.DataFrame(out); E['ovmm']=E[['okx_mv','byb_mv']].median(axis=1); E['ovmm_diff']=E['ovmm']-E['bin_mv']
    pb=[];pr=[];pn=[]
    for r in E.itertuples():
        if r.resolved_by_15 or not (0<r.z15<r.w): pb.append(np.nan);pr.append(np.nan);pn.append(np.nan); continue
        a,b_,c=b0_probs(r.z15,r.w,r.sig,HOLD-2,n=3000,seed=int(r.j)%100000); pb.append(a);pr.append(b_);pn.append(c)
    E['b0_break']=pb;E['b0_reject']=pr;E['b0_neither']=pn; return E
if __name__=='__main__':
    k=load_btc(); b=bars_from_df(k)
    ev=[e for e in LV.structural_first_touches(b) if e['eligible']]
    print('eligible structural first touches',len(ev), pd.Series([e['family'] for e in ev]).value_counts().to_dict())
    okx=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/okx_btc_usdt_swap_5m.csv.gz')); byb=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/bybit_btcusdt_linear_5m.csv.gz'))
    E=enrich(k,ev,okx,byb,'real'); E.to_pickle(os.path.join(os.path.dirname(__file__),'results','events_real.pkl'))
    print(E.groupby('year').size().to_dict()); print(E.label.value_counts(normalize=True).round(3).to_dict()); print('resolved by T15', E.resolved_by_15.mean().round(3), 'median t', E.t_res.median())
    print('BREAK share among resolved', (E[E.label.isin(['BREAK_FIRST','REJECT_FIRST'])].label=='BREAK_FIRST').mean().round(3))
