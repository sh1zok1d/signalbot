"""E5: second-moment cross-market information.  (a) Does BTC / market volatility improve the forecast of an alt's next-4h
log RV beyond its own HAR+clock?  (b) Is next-24h realized correlation (alt, BTC) predictable beyond persistence?
Walk-forward test years on the command line."""
import os, sys, pickle, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore'); sys.path.insert(0, os.path.dirname(__file__))
from panel import DATA_DIR
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
D=pickle.load(open(os.path.join(DATA_DIR,os.environ.get('XM_PANEL','xm_panel.pkl')),'rb')); P=D['P']; F=D['F']; assets=D['assets']
test_years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]; tag=sys.argv[2] if len(sys.argv)>2 else 'dev'
alts=[a for a in assets if a!='BTC']; r5=pd.DataFrame({a:F[a]['r5'] for a in alts}); mkt=r5.mean(axis=1); rb=F['BTC']['r5']
def lrv(x,w): return np.log(np.sqrt((x*x).rolling(w,min_periods=w).mean())+1e-9)
res={'vol':{},'corr':{}}
for X in alts:
    f=F[X]; r=f['r5']
    df=pd.DataFrame({'own_4h':f.lrv_4h,'own_24h':f.lrv_24h,'own_7d':f.lrv_7d,'own_1h':f.lrv_1h,'hs':f.hod_sin,'hc':f.hod_cos,'we':f.weekend,
                     'btc_1h':F['BTC'].lrv_1h,'btc_4h':F['BTC'].lrv_4h,'btc_24h':F['BTC'].lrv_24h,'btc_7d':F['BTC'].lrv_7d,'mkt_4h':lrv(mkt,48),'mkt_24h':lrv(mkt,288),
                     'y':lrv(r[::-1],48)[::-1].shift(-1)})
    df['present']=P[X]['present']; df=df.iloc[::48]; df=df[df.present==1].drop(columns='present').dropna(); df['year']=df.index.year; df['end']=df.index+pd.Timedelta(hours=4)
    sets={'own HAR+clock':['own_1h','own_4h','own_24h','own_7d','hs','hc','we'],'+BTC RV':['own_1h','own_4h','own_24h','own_7d','hs','hc','we','btc_1h','btc_4h','btc_24h','btc_7d'],'+market RV':['own_1h','own_4h','own_24h','own_7d','hs','hc','we','mkt_4h','mkt_24h'],'+both':['own_1h','own_4h','own_24h','own_7d','hs','hc','we','btc_1h','btc_4h','btc_24h','btc_7d','mkt_4h','mkt_24h']}
    out={}
    for ty in test_years:
        t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=df[(df.year<ty)&(df.end<t0)]; te=df[df.year==ty]
        if len(tr)<1000 or len(te)<300: continue
        row={}
        for k,cols in sets.items():
            sc=StandardScaler().fit(tr[cols]); m=Ridge(alpha=1.0).fit(sc.transform(tr[cols]),tr.y.values); p=m.predict(sc.transform(te[cols])); row[k]=round(float(1-np.sum((te.y.values-p)**2)/np.sum((te.y.values-tr.y.mean())**2)),4)
        out[ty]=row
    res['vol'][X]=out; print('VOL',X,out,flush=True)
    # correlation: next-24h realized corr of 5m returns with BTC vs past 24h / 7d corr
    c24=r.rolling(288).corr(rb); c7=r.rolling(2016).corr(rb); y=c24.shift(-288)
    dc=pd.DataFrame({'c24':c24,'c7':c7,'own_24h':f.lrv_24h,'btc_24h':F['BTC'].lrv_24h,'y':y}).iloc[::288].dropna(); dc['year']=dc.index.year; dc['end']=dc.index+pd.Timedelta(hours=24)
    outc={}
    for ty in test_years:
        t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=dc[(dc.year<ty)&(dc.end<t0)]; te=dc[dc.year==ty]
        if len(tr)<200: continue
        r2=lambda p: round(float(1-np.sum((te.y.values-p)**2)/np.sum((te.y.values-tr.y.mean())**2)),4)
        a,b=np.polyfit(tr.c24,tr.y,1); p1=a*te.c24+b
        sc=StandardScaler().fit(tr[['c24','c7','own_24h','btc_24h']]); m=Ridge(alpha=1.0).fit(sc.transform(tr[['c24','c7','own_24h','btc_24h']]),tr.y); p2=m.predict(sc.transform(te[['c24','c7','own_24h','btc_24h']]))
        outc[ty]={'persist_24h':r2(p1),'ridge(c24,c7,vols)':r2(p2),'mean_corr':round(float(te.y.mean()),3),'sd_corr':round(float(te.y.std()),3)}
    res['corr'][X]=outc; print('CORR',X,outc,flush=True)
json.dump(res,open(os.path.join(os.path.dirname(__file__),'results',f'e5_vol_spillover_{tag}.json'),'w'),indent=1)
