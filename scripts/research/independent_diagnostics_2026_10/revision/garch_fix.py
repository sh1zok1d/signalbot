"""GARCH(1,1) on hourly log returns (params from years < Y, forecasts for every hour with fixed params), 4h-ahead variance;
compared on the same anchors/targets as vol_bench: R2 of log RV_4h and touch log-loss (reflection and empirical shape)."""
import pandas as pd, numpy as np, json
from arch import arch_model
from scipy.stats import norm
k=pd.read_pickle('data/btc5m.pkl'); f=pd.read_pickle('data/feat5m.pkl')
lc=np.log(k.close); H=lc.resample('1h').last().dropna(); rh=(H.diff()*100).dropna()
hi=k.high.values; lo=k.low.values; c=k.close.values
Hm=pd.Series(hi,index=k.index)[::-1].rolling(48,min_periods=48).max()[::-1].shift(-1).values; Lm=pd.Series(lo,index=k.index)[::-1].rolling(48,min_periods=48).min()[::-1].shift(-1).values
f['up_exc']=np.log(Hm/c); f['dn_exc']=-np.log(Lm/c)
sub=f.iloc[::48].dropna(subset=['y_lrv_4h','up_exc','dn_exc','lrv_4h']); sub['end']=sub.index+pd.Timedelta(hours=4)
res={}
for ty in [2022,2023,2024,2025,2026]:
    t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); t1=pd.Timestamp(f'{ty+1}-01-01',tz='UTC')
    fit=arch_model(rh[rh.index<t0],vol='GARCH',p=1,q=1,mean='Zero').fit(disp='off')
    full=arch_model(rh[rh.index<t1],vol='GARCH',p=1,q=1,mean='Zero').fix(fit.params.values)
    v4=full.forecast(horizon=4,start=0,reindex=True).variance.sum(axis=1)   # %^2 over next 4 hours, from info to hour label
    g=np.log(np.sqrt(v4/48)/100+1e-12); g.index=g.index+pd.Timedelta(hours=1)
    tr=sub[(sub.year<ty)&(sub.end<t0)]; te=sub[sub.year==ty]; gtr=g.reindex(tr.index).values; gte=g.reindex(te.index).values
    m=np.isfinite(gtr); a,b=np.polyfit(gtr[m],tr.y_lrv_4h.values[m],1); ptr=a*gtr+b; pte=a*gte+b
    yt=te.y_lrv_4h.values; ok=np.isfinite(pte); r2=float(1-np.sum((yt[ok]-pte[ok])**2)/np.sum((yt[ok]-tr.y_lrv_4h.mean())**2))
    # also raw GARCH (no affine) R2
    r2raw=float(1-np.sum((yt[ok]-gte[ok])**2)/np.sum((yt[ok]-tr.y_lrv_4h.mean())**2))
    S_tr=np.exp(ptr[m])*np.sqrt(48); z=np.sort(np.concatenate([tr.up_exc.values[m]/S_tr,tr.dn_exc.values[m]/S_tr])); S_te=np.exp(pte[ok])*np.sqrt(48)
    row={'r2_affine':r2,'r2_raw':r2raw,'n':int(ok.sum()),'params':fit.params.round(4).to_dict()}
    for d in [0.005,0.01,0.02]:
        yy=np.concatenate([(te.up_exc.values[ok]>=d),(te.dn_exc.values[ok]>=d)]).astype(float); zz=np.concatenate([d/S_te]*2)
        pr=np.clip(2*(1-norm.cdf(zz)),1e-3,1-1e-3); pe=np.clip(1-np.searchsorted(z,zz)/len(z),1e-3,1-1e-3); ll=lambda p: float(-np.mean(yy*np.log(p)+(1-yy)*np.log(1-p)))
        row[f'd={d*100:.1f}%']={'ll_refl':ll(pr),'ll_emp':ll(pe)}
    res[ty]=row; print(ty,row)
json.dump(res,open('rev/garch_results.json','w'),indent=1)
