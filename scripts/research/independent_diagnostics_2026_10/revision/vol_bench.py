"""Volatility benchmark: is Pulsy-type range forecasting better than standard baselines, and do the
forecasts give coherent touch probabilities?  4h horizon, non-overlapping 4h anchors, test years 2022-2026H1."""
import pandas as pd, numpy as np, json, sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'diag'); from features import FEATS
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from scipy.stats import norm
from arch import arch_model
k=pd.read_pickle('data/btc5m.pkl'); f=pd.read_pickle('data/feat5m.pkl')
lc=np.log(k.close.values); r=np.diff(lc,prepend=lc[0]); r2=pd.Series(r*r,index=k.index)
# extra vol features
f['lrv_30d']=np.log(np.sqrt(r2.rolling(8640,min_periods=8640).mean()).values+1e-9)
for hl,name in [(288,'ewma1d'),(48,'ewma4h'),(2016,'ewma7d')]:
    f['l'+name]=np.log(np.sqrt(r2.ewm(halflife=hl,min_periods=hl).mean()).values+1e-9)
# DVOL (Deribit, hourly close), last value at or before the anchor bar's open; available 2021-03-25..2024-12-31
dv=pd.read_csv('/home/user/signalbot/docs/research_data/DH3_DERIBIT_DVOL_1H_V0/dvol_1h.csv.gz'); dv=dv[dv.currency=='BTC']
dv['ts']=pd.to_datetime(dv.timestamp_ms,unit='ms',utc=True)+pd.Timedelta(hours=1)  # hourly bar labelled by open -> known at its close
dvs=dv.set_index('ts').sort_index()['close']; f['ldvol']=np.log(dvs.reindex(f.index,method='ffill',tolerance=pd.Timedelta('2h')).values/100/np.sqrt(365*24*12)+1e-12)  # per-5m-bar scale
# hourly returns for GARCH
H=pd.Series(lc,index=k.index).resample('1h').last().dropna(); rh=(H.diff()*100).dropna()
# forward excursion targets (next 48 bars): max up, max down in log terms
hi=k.high.values; lo=k.low.values; c=k.close.values
Hm=pd.Series(hi,index=k.index)[::-1].rolling(48,min_periods=48).max()[::-1].shift(-1).values; Lm=pd.Series(lo,index=k.index)[::-1].rolling(48,min_periods=48).min()[::-1].shift(-1).values
f['up_exc']=np.log(Hm/c); f['dn_exc']=-np.log(Lm/c)
sub=f.iloc[::48].copy(); sub=sub.dropna(subset=FEATS+['y_lrv_4h','y_lrange_4h','up_exc','dn_exc','lrv_30d','lewma1d'])
sub['end']=sub.index+pd.Timedelta(hours=4)
TGT='y_lrv_4h'
MODELS={'persist_4h':['lrv_4h'],'HAR(4h,24h,7d,30d)':['lrv_4h','lrv_24h','lrv_7d','lrv_30d'],'HAR+clock':['lrv_4h','lrv_24h','lrv_7d','lrv_30d','hod_sin','hod_cos','weekend'],
        'EWMA(1d)':['lewma1d'],'EWMA(4h,1d,7d)+clock':['lewma4h','lewma1d','lewma7d','hod_sin','hod_cos','weekend'],
        'ranges(1h,4h,24h,7d)+clock (V1-like)':['lrange_4h','lrange_24h','lrange_7d','lrv_1h','hod_sin','hod_cos','weekend'],
        'ridge29 (first report)':FEATS,'DVOL only':['ldvol'],'HAR+clock+DVOL':['lrv_4h','lrv_24h','lrv_7d','lrv_30d','hod_sin','hod_cos','weekend','ldvol'],'ridge29+DVOL':FEATS+['ldvol']}
res={}
for ty in [2022,2023,2024,2025,2026]:
    t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=sub[(sub.year<ty)&(sub.end<t0)]; te=sub[sub.year==ty]
    y=tr[TGT].values; yt=te[TGT].values; out={}
    def r2(pred): return float(1-np.sum((yt-pred)**2)/np.sum((yt-y.mean())**2))
    preds={}
    for name,cols in MODELS.items():
        trr=tr.dropna(subset=cols); tee=te.dropna(subset=cols)
        if len(trr)<500 or len(tee)<200: continue
        sc=StandardScaler().fit(trr[cols]); m=Ridge(alpha=1.0).fit(sc.transform(trr[cols]),trr[TGT].values); p=m.predict(sc.transform(tee[cols]))
        if len(tee)==len(te): preds[name]=p; out[name]=r2(p)
        else: out[name+' (DVOL-covered rows)']=float(1-np.sum((tee[TGT].values-p)**2)/np.sum((tee[TGT].values-trr[TGT].mean())**2)); out[name+' n']=int(len(tee))
    gb=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.03,max_depth=3,min_samples_leaf=300,random_state=0).fit(tr[FEATS],y); p=gb.predict(te[FEATS]); preds['gbm29']=p; out['gbm29']=r2(p)
    # GARCH(1,1) on hourly returns, params from train, forecasts on full series with fixed params
    rtr=rh[rh.index<t0]; am=arch_model(rtr,vol='GARCH',p=1,q=1,dist='normal',mean='Zero'); fit=am.fit(disp='off')
    full=arch_model(rh[rh.index<pd.Timestamp(f'{ty+1}-01-01',tz='UTC')],vol='GARCH',p=1,q=1,dist='normal',mean='Zero').fix(fit.params.values)
    fc=full.forecast(horizon=4,reindex=True).variance  # variance per hourly step, indexed by the last observed hour
    v4=fc.sum(axis=1)  # 4h variance in %^2 -> per-5m-bar RV: sqrt(v4/48)/100
    g=np.log(np.sqrt(v4/48)/100+1e-9); g.index=g.index+pd.Timedelta(hours=1)  # forecast made at close of hour -> anchor at next hour open
    ga=g.reindex(te.index); gtr=g.reindex(tr.index)
    m_=np.isfinite(gtr.values); a,b=np.polyfit(gtr.values[m_],y[m_],1); p=a*ga.values+b; p=np.where(np.isfinite(p),p,y.mean()); preds['GARCH(1,1) hourly']=p; out['GARCH(1,1) hourly']=r2(p)
    # touch probabilities for d in {0.5%,1%,2%} either side within 4h, from each scale forecast:
    # (a) Brownian reflection p=2(1-Phi(d/(S*sqrt(48)))) with S=exp(pred); (b) empirical shape: z=exc/(S*sqrt(48)) distribution from train
    touch={}
    for name in ['persist_4h','HAR+clock','ridge29 (first report)','gbm29','GARCH(1,1) hourly']:
        if name not in preds: continue
        # train-scale for the empirical shape: in-sample predictions on train
        cols=MODELS.get(name,None)
        if cols is not None:
            sc=StandardScaler().fit(tr[cols]); m=Ridge(alpha=1.0).fit(sc.transform(tr[cols]),y); ptr=m.predict(sc.transform(tr[cols]))
        elif name=='gbm29': ptr=gb.predict(tr[FEATS])
        else: ptr=np.where(np.isfinite(gtr.values),a*gtr.values+b,y.mean())
        S_tr=np.exp(ptr)*np.sqrt(48); z_tr=np.concatenate([tr.up_exc.values/S_tr,tr.dn_exc.values/S_tr])  # pooled one-sided excursion shape
        S_te=np.exp(preds[name])*np.sqrt(48); row={}
        for d in [0.005,0.01,0.02]:
            yu=(te.up_exc.values>=d).astype(float); yd=(te.dn_exc.values>=d).astype(float); yy=np.concatenate([yu,yd]); zz=np.concatenate([d/S_te,d/S_te])
            p_refl=np.clip(2*(1-norm.cdf(zz)),1e-3,1-1e-3); p_emp=np.clip(1-np.searchsorted(np.sort(z_tr),zz)/len(z_tr),1e-3,1-1e-3)
            ll=lambda p: float(-np.mean(yy*np.log(p)+(1-yy)*np.log(1-p))); base=np.clip(yy.mean()*0+np.mean(np.concatenate([(tr.up_exc.values>=d),(tr.dn_exc.values>=d)])),1e-3,1-1e-3)
            row[f'd={d*100:.1f}%']={'rate':float(yy.mean()),'ll_base':ll(np.full(len(yy),base)),'ll_refl':ll(p_refl),'ll_emp':ll(p_emp),'cal_refl_mean_p':float(p_refl.mean()),'cal_emp_mean_p':float(p_emp.mean())}
        touch[name]=row
    out['touch']=touch; res[ty]=out
    print(ty,{k_:round(v,3) for k_,v in out.items() if isinstance(v,float)})
    for name,row in touch.items(): print('   touch',name,{d:(round(v['ll_base'],4),round(v['ll_refl'],4),round(v['ll_emp'],4)) for d,v in row.items()})
json.dump(res,open('rev/vol_bench_results.json','w'),indent=1)
