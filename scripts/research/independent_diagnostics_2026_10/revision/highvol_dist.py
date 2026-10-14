"""Distribution of the top-volatility-tercile 4h trades on the BTC selection surface (2022-2026H1): quantiles, skew,
equity path drawdown, dependence on the year, hour, weekend, and a slippage sensitivity."""
import sys; sys.path.insert(0,'rev'); sys.path.insert(0,'diag')
import pandas as pd, numpy as np, json
from highvol_test import load_binance, feats, FE, yr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
btc=feats(load_binance('data/klines5m/*.zip')); sub=btc.iloc[::48].dropna(subset=FE+['y_r']); sub=sub[sub.y_r!=0]; T=[]
for ty in [2022,2023,2024,2025,2026]:
    t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=sub[(yr(sub)<ty)&(sub.end<t0)]; te=sub[yr(sub)==ty].copy()
    lo=tr[FE].quantile(0.001); hi=tr[FE].quantile(0.999); sc=StandardScaler().fit(tr[FE].clip(lo,hi,axis=1)); m=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(tr[FE].clip(lo,hi,axis=1)),(tr.y_r>0).astype(int))
    te['p']=m.predict_proba(sc.transform(te[FE].clip(lo,hi,axis=1)))[:,1]; e=np.quantile(tr.lrv_24h,[1/3,2/3]); te['volt']=np.digitize(te.lrv_24h,e); T.append(te)
te=pd.concat(T); d=te[te.volt==2].copy(); d['g']=np.sign(d.p-0.5)*d.y_r*1e4
q=d.g.quantile([0.01,0.05,0.25,0.5,0.75,0.95,0.99]).round(1).to_dict()
eq=d.g.cumsum(); dd=(eq-eq.cummax()).min()
out={'n':int(len(d)),'mean_bp':float(d.g.mean()),'median_bp':float(d.g.median()),'sd_bp':float(d.g.std()),'skew':float(d.g.skew()),'quantiles_bp':q,
     'share_trades_positive':float((d.g>0).mean()),'sum_bp':float(d.g.sum()),'max_drawdown_bp_cum':float(dd),'worst_trade_bp':float(d.g.min()),'best_trade_bp':float(d.g.max()),
     'mean_excluding_top_bottom_1pct':float(d.g[(d.g>d.g.quantile(0.01))&(d.g<d.g.quantile(0.99))].mean()),
     'by_year':{int(y):{'n':int((d.index.year==y).sum()),'mean':float(d.g[d.index.year==y].mean()),'hit':float((d.g[d.index.year==y]>0).mean())} for y in sorted(set(d.index.year))},
     'weekend_share':float(d.weekend.mean()),'mean_weekend':float(d.g[d.weekend==1].mean()),'mean_weekday':float(d.g[d.weekend==0].mean()),
     'by_utc_hour_block':{f'{h0:02d}-{h0+4:02d}':float(d.g[(d.index.hour>=h0)&(d.index.hour<h0+4)].mean()) for h0 in range(0,24,4)},
     'long_share':float((d.p>0.5).mean()),'mean_long':float(d.g[d.p>0.5].mean()),'mean_short':float(d.g[d.p<0.5].mean()),
     'net_at_slippage_bp':{s:float(d.g.mean()-s) for s in [2,4,6,10,15]},
     'avg_abs_4h_return_bp_in_state':float((d.y_r.abs()*1e4).mean()),'avg_abs_4h_return_bp_all':float((te.y_r.abs()*1e4).mean()),
     'monthly_means_bp':{str(k_)[:7]:round(float(v),1) for k_,v in d.g.groupby(d.index.to_period('M')).mean().items()}}
print(json.dumps(out,indent=1)); json.dump(out,open('rev/highvol_dist_results.json','w'),indent=1)
