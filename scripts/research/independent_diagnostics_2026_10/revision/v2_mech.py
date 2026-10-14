"""V2 setup families as mechanisms at scale (approximations of the frozen Stage-5 detectors, not the frozen code):
CB: compression (mean 15m range over 16 bars in the bottom quartile of the trailing 30d distribution) + fresh 5m close
beyond the compression run's high/low -> continuation over 15m/1h/2h/4h.  FB: fresh 5m close beyond the trailing 48h
high/low -> continuation.  TP: 4h-bar move in the top quartile of trailing 30d (trend) and 1h bias agreeing, price
pulled back 0.5-3x the 15m range proxy from the leg extreme -> continuation.  Outcomes vs matched random anchors
(same hour, same RV tercile, same year) and vs the unconditional sign.  Binance BTCUSDT 5m 2020-01..2026-07."""
import pandas as pd, numpy as np, json
k=pd.read_pickle('data/btc5m.pkl'); c=k.close.values; hi=k.high.values; lo=k.low.values; lc=np.log(c); idx=k.index; n=len(k)
r=np.diff(lc,prepend=np.nan)
rng15=pd.Series((hi-lo)/c,index=idx).rolling(3).max()  # crude 15m range proxy per 5m bar (max of 3 bars' ranges)
b15=pd.Series(hi,index=idx).rolling(3).max(); l15=pd.Series(lo,index=idx).rolling(3).min(); range15=((b15-l15)/c)
comp=range15.rolling(48).mean()   # mean 15m range over 16x15m = 48 bars
comp_pct=comp.rolling(8640,min_periods=4000).rank(pct=True)
run_hi=pd.Series(hi,index=idx).rolling(48).max().shift(1); run_lo=pd.Series(lo,index=idx).rolling(48).min().shift(1)
hi48h=pd.Series(hi,index=idx).rolling(576).max().shift(1); lo48h=pd.Series(lo,index=idx).rolling(576).min().shift(1)
mv4h=pd.Series(lc,index=idx).diff(48); mv4h_pct=mv4h.abs().rolling(8640,min_periods=4000).rank(pct=True)
mv1h=pd.Series(lc,index=idx).diff(12)
rv24=pd.Series(r,index=idx).rolling(288).std()
ev={}
cb=(comp_pct<=0.25)&((c>run_hi)|(c<run_lo)); ev['CB']=(cb.values, np.where(c>run_hi,1,-1))
fb=(c>hi48h)|(c<lo48h); ev['FB']=(fb.values, np.where(c>hi48h,1,-1))
# TP: trend over 4h strong (top quartile), 1h move same sign, and current close pulled back from the 4h extreme by 0.5-3x the 15m range
ext_hi=pd.Series(hi,index=idx).rolling(48).max(); ext_lo=pd.Series(lo,index=idx).rolling(48).min()
pb_up=(ext_hi.values-c)/c; pb_dn=(c-ext_lo.values)/c; rp=range15.rolling(14).mean().values
tp_up=(mv4h_pct>=0.75)&(mv4h>0)&(mv1h>0)&(pb_up>=0.5*rp)&(pb_up<=3*rp); tp_dn=(mv4h_pct>=0.75)&(mv4h<0)&(mv1h<0)&(pb_dn>=0.5*rp)&(pb_dn<=3*rp)
ev['TP']=((tp_up|tp_dn).values, np.where(tp_up,1,-1))
H={'15m':3,'1h':12,'2h':24,'4h':48}
fwd={h:(pd.Series(lc,index=idx).shift(-w).values-lc) for h,w in H.items()}
year=idx.year.values; hour=idx.hour.values; rvt=pd.qcut(rv24,3,labels=False).values
rng=np.random.default_rng(0); out={}
for name,(mask,side) in ev.items():
    # one event per episode: first qualification, then a 48-bar refractory period
    js=np.where(mask&np.isfinite(rv24.values)&(np.arange(n)<n-300))[0]; keep=[]; last=-10**9
    for j in js:
        if j-last>=48: keep.append(j); last=j
    keep=np.array(keep); s=side[keep]; res={'n_events':int(len(keep)),'per_year':{int(y):int((year[keep]==y).sum()) for y in np.unique(year[keep])}}
    for h in H:
        cont=s*fwd[h][keep]; ok=np.isfinite(cont); cont=cont[ok]; kk=keep[ok]
        # matched random: same year, hour, rv tercile
        mr=[]; 
        pool={}
        for j in kk:
            key=(year[j],hour[j],rvt[j]); 
            if key not in pool:
                cand=np.where((year==key[0])&(hour==key[1])&(rvt==key[2]))[0]; pool[key]=cand[cand<n-300]
            cand=pool[key]; m=rng.choice(cand,1)[0]; mr.append(s[ok][len(mr)]*fwd[h][m] if False else np.sign(rng.choice([-1,1]))*fwd[h][m])
        mr=np.array(mr)
        # block bootstrap by week for the mean
        wk=(kk//2016); uw=np.unique(wk); id_={u:np.where(wk==u)[0] for u in uw}; bs=[]
        for _ in range(500):
            ii=np.concatenate([id_[u] for u in rng.choice(uw,len(uw),replace=True)]); bs.append(cont[ii].mean())
        lo_,hi_=np.percentile(bs,[2.5,97.5])
        res[h]={'cont_mean_bp':float(cont.mean()*1e4),'ci':[float(lo_*1e4),float(hi_*1e4)],'pos_share':float((cont>0).mean()),'matched_random_bp':float(mr.mean()*1e4),'median_bp':float(np.median(cont)*1e4),
                'by_year_bp':{int(y):float(cont[year[kk]==y].mean()*1e4) for y in np.unique(year[kk])}}
    out[name]=res; print(name,json.dumps(res,indent=None)[:1500])
json.dump(out,open('rev/v2_mech_results.json','w'),indent=1)
