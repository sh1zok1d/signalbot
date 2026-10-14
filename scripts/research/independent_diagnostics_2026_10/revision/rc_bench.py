"""Rangecast V1 / W_L1 (the production code, fitted offline) vs HAR+clock with the same empirical-shape machinery,
and vs GARCH-scaled and reflection probabilities.  Touch log-loss at 0.5/1/2 % within 4h, hourly anchors, test years 2022-2026H1,
expanding fit on years < Y.  Event calendar: the repo's config/beta_calendar.yaml."""
import sys; sys.path.insert(0,'/home/user/signalbot')
import numpy as np, pandas as pd, json
from datetime import datetime, timezone
from beta import hist_series as hs, rangecast as rc, rangecast_v2 as v2
from beta.calendar_events import load_calendar, event_times_ms
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
k=pd.read_pickle('data/btc5m.pkl')
t=((k.index-pd.Timestamp(0,tz='UTC'))//pd.Timedelta('1ms')).values.astype('int64'); t0=int(t[0]); assert t0==1577836800000; n=len(k); b=hs.empty_bars(t0,n)
for dst,src in (('open','open'),('high','high'),('low','low'),('close','close'),('volume','volume'),('quote','quote_volume'),('taker_buy_quote','taker_buy_quote_volume')): getattr(b,dst)[:]=k[src].to_numpy(dtype=np.float64)
events=event_times_ms(load_calendar())
ms=lambda y: int(datetime(y,1,1,tzinfo=timezone.utc).timestamp()*1000)
H='4h'; h=rc.HORIZONS[H]; logs=rc.past_log_ranges(b); weekend=rc.weekend_share(b,h); close_ms=b.times+hs.BAR_MS
tg=rc.targets(b,h)   # up/down excursions in % of close over next h bars
F=v2.bar_features(b)
# HAR+clock features for the comparison scale (my implementation): log RV 4h/24h/7d/30d of 5m log returns + hour sin/cos + weekend
lc=np.log(b.close); r=np.diff(lc,prepend=np.nan); r2=pd.Series(r*r)
har=pd.DataFrame({'l4':np.log(np.sqrt(r2.rolling(48,min_periods=48).mean())+1e-9),'l24':np.log(np.sqrt(r2.rolling(288,min_periods=288).mean())+1e-9),'l7':np.log(np.sqrt(r2.rolling(2016,min_periods=2016).mean())+1e-9),'l30':np.log(np.sqrt(r2.rolling(8640,min_periods=8640).mean())+1e-9)})
hr=(close_ms//3600000)%24; har['hs']=np.sin(2*np.pi*hr/24); har['hc']=np.cos(2*np.pi*hr/24); har['we']=weekend
res={}
for ty in [2022,2023,2024,2025,2026]:
    tr_end=ms(ty); te_end=ms(ty+1)
    bt=b.slice(0,b.index_at_open(tr_end)); m1=rc.fit_range_model(bt,events=events,holdout_days=0); mh=m1['horizons'][H]
    m2=v2.fit_range_model_v2(bt,events=events); mh2=m2['horizons'][H]
    ok=(close_ms%(12*hs.BAR_MS)==0)&np.isfinite(b.close)&(close_ms>=tr_end)&(close_ms<te_end)&np.isfinite(tg['up'])&np.isfinite(tg['down'])
    for w_ in rc.PAST_WINDOWS: ok&=np.isfinite(logs[w_])
    for nme in mh2['features']: ok&=np.isfinite(F[nme])
    ok&=np.isfinite(har.values).all(axis=1)
    idx=np.flatnonzero(ok)
    X=rc.design(b,idx,H,logs=logs,season=mh['season'],events=events,weekend=weekend); S1=np.exp(X@np.asarray(mh['beta']))
    st=v2.state(mh2,{kk:F[kk][idx] for kk in mh2['features']},v2.calendar_columns(b,idx,H,events,weekend=weekend)); S2=st['S']
    # HAR+clock scale with the SAME target definition as V1 (log of up+down excursion %), ridge, train anchors = hourly closes with close+h <= tr_end
    okt=(close_ms%(12*hs.BAR_MS)==0)&np.isfinite(b.close)&(close_ms+h*hs.BAR_MS<=tr_end)&np.isfinite(tg['up'])&np.isfinite(tg['down'])&np.isfinite(har.values).all(axis=1)
    it=np.flatnonzero(okt); yv=np.log(np.maximum(tg['up'][it]+tg['down'][it],0.02))
    sc=StandardScaler().fit(har.values[it]); rg=Ridge(alpha=1.0).fit(sc.transform(har.values[it]),yv); S3=np.exp(rg.predict(sc.transform(har.values[idx])))
    # empirical one-sided shape for the HAR scale from training residuals (pooled up & down z)
    S3tr=np.exp(rg.predict(sc.transform(har.values[it]))); z=np.sort(np.concatenate([tg['up'][it]/S3tr,tg['down'][it]/S3tr]))
    up=tg['up'][idx]; dn=tg['down'][idx]; out={'n':int(len(idx))}
    for d in [0.5,1.0,2.0]:
        y=np.concatenate([(up>=d),(dn>=d)]).astype(float)
        p1=np.clip(np.concatenate([1-np.interp(d/S1,mh['q_one'],rc.P_GRID)]*2),1e-3,1-1e-3)
        p2=np.clip(np.concatenate([v2.touch_prob(mh2,st,'up',np.full(idx.size,d)),v2.touch_prob(mh2,st,'down',np.full(idx.size,d))]),1e-3,1-1e-3)
        p3=np.clip(np.concatenate([1-np.searchsorted(z,d/S3)/len(z)]*2),1e-3,1-1e-3)
        base=np.clip(np.concatenate([(tg['up'][it]>=d),(tg['down'][it]>=d)]).mean(),1e-3,1-1e-3)
        ll=lambda p: float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))); br=lambda p: float(np.mean((p-y)**2))
        out[f'd={d}%']={'rate':float(y.mean()),'ll_base':ll(np.full(len(y),base)),'ll_V1':ll(p1),'ll_WL1':ll(p2),'ll_HARclock_emp':ll(p3),'brier_V1':br(p1),'brier_WL1':br(p2),'brier_HARclock_emp':br(p3),'mean_p_V1':float(p1.mean()),'mean_p_WL1':float(p2.mean()),'mean_p_HAR':float(p3.mean())}
    # scale-level R2 of log(up+down) 
    yt=np.log(np.maximum(up+dn,0.02)); mu=yv.mean(); r2f=lambda s: float(1-np.sum((yt-np.log(s))**2)/np.sum((yt-mu)**2))
    out['r2_logrange']={'V1':r2f(S1),'WL1':r2f(S2),'HARclock':r2f(S3)}
    res[ty]=out; print(ty,json.dumps(out))
json.dump(res,open('rev/rc_bench_results.json','w'),indent=1)
