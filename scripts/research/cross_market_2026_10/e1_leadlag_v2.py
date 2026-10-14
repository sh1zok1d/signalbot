"""E1/E4 v2 (beta-leak fixed in E4): lead-lag at fine scale, and E4: catch-up of idiosyncratic returns.  Descriptive, by year."""
import os, sys, pickle, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); from panel import DATA_DIR
D=pickle.load(open(os.path.join(DATA_DIR,'xm_panel.pkl'),'rb')); P=D['P']; assets=D['assets']
R5={s:np.log(P[s].close).diff() for s in assets}
years=[2021,2022,2023,2024,2025,2026]
out={'xcorr_5m':{}, 'granger':{}, 'catchup':{}}
# E1a: cross-correlation corr(r_alt[t], r_btc[t-k]) for k=-6..6 (k>0: BTC leads), 5m returns, by year
for s in [a for a in assets if a!='BTC']:
    out['xcorr_5m'][s]={}
    for y in years:
        a=R5[s][R5[s].index.year==y]; b=R5['BTC'][R5['BTC'].index.year==y]
        m=(a!=0)&(b!=0)&a.notna()&b.notna(); a=a[m]; b=b[m]
        if len(a)<5000: continue
        row={k:float(np.corrcoef(a.values[6:-6], b.shift(k).values[6:-6])[0,1]) for k in range(-6,7)}
        out['xcorr_5m'][s][y]=row
    print(s, 'xcorr lag0/+1/+2/-1 by year:', {y:(round(v[0],3),round(v[1],3),round(v[2],3),round(v[-1],3)) for y,v in out['xcorr_5m'][s].items()})
# E1b: Granger-style: alt return over next w bars on own lagged returns and BTC lagged returns (5m, 15m, 1h blocks), OLS by year, t-stats with HAC-free (non-overlapping anchors)
def blocks(r, w): return r.rolling(w).sum()
for s in [a for a in assets if a!='BTC']:
    out['granger'][s]={}
    for w,label in [(1,'5m'),(3,'15m'),(12,'1h')]:
        ra=R5[s]; rb=R5['BTC']; y=blocks(ra,w).shift(-w)   # next w bars
        X=pd.DataFrame({'own_l1':blocks(ra,w),'own_l2':blocks(ra,w).shift(w),'own_l3':blocks(ra,w).shift(2*w),'btc_l1':blocks(rb,w),'btc_l2':blocks(rb,w).shift(w),'btc_l3':blocks(rb,w).shift(2*w)})
        X['y']=y; X=X.iloc[::w].dropna(); X=X[(X.y!=0)]
        res={}
        for yr in years:
            d=X[X.index.year==yr]
            if len(d)<2000: continue
            Xm=np.column_stack([np.ones(len(d)),d[['own_l1','own_l2','own_l3','btc_l1','btc_l2','btc_l3']].values]); yv=d.y.values
            b,_,_,_=np.linalg.lstsq(Xm,yv,rcond=None); resid=yv-Xm@b; s2=resid@resid/(len(d)-7); cov=s2*np.linalg.inv(Xm.T@Xm); se=np.sqrt(np.diag(cov))
            # R2 increment from BTC lags
            Xo=Xm[:,:4]; bo=np.linalg.lstsq(Xo,yv,rcond=None)[0]; r2o=1-np.sum((yv-Xo@bo)**2)/np.sum((yv-yv.mean())**2); r2f=1-np.sum(resid**2)/np.sum((yv-yv.mean())**2)
            res[yr]={'btc_l1':round(float(b[4]),4),'t':round(float(b[4]/se[4]),2),'own_l1':round(float(b[1]),4),'t_own':round(float(b[1]/se[1]),2),'dR2_btc':round(float(r2f-r2o),5),'n':int(len(d))}
        out['granger'][s][label]=res; print(s,label,{yr:(v['btc_l1'],v['t'],v['dR2_btc']) for yr,v in res.items()})
# reverse: BTC next return on alt lags (ETH, SOL) controlling own
for s in ['ETH','SOL']:
    for w,label in [(1,'5m'),(3,'15m'),(12,'1h')]:
        ra=R5[s]; rb=R5['BTC']; y=blocks(rb,w).shift(-w)
        X=pd.DataFrame({'own_l1':blocks(rb,w),'own_l2':blocks(rb,w).shift(w),'alt_l1':blocks(ra,w),'alt_l2':blocks(ra,w).shift(w)}); X['y']=y; X=X.iloc[::w].dropna(); X=X[X.y!=0]
        res={}
        for yr in years:
            d=X[X.index.year==yr]
            if len(d)<2000: continue
            Xm=np.column_stack([np.ones(len(d)),d[['own_l1','own_l2','alt_l1','alt_l2']].values]); yv=d.y.values; b=np.linalg.lstsq(Xm,yv,rcond=None)[0]; resid=yv-Xm@b; s2=resid@resid/(len(d)-5); se=np.sqrt(np.diag(s2*np.linalg.inv(Xm.T@Xm)))
            res[yr]={'alt_l1':round(float(b[3]),4),'t':round(float(b[3]/se[3]),2)}
        out['granger'][f'BTC<-{s}']=out['granger'].get(f'BTC<-{s}',{}); out['granger'][f'BTC<-{s}'][label]=res; print('BTC<-',s,label,res)
# E4: catch-up. beta from trailing 30d of 1h returns; idio_h = r_alt_h - beta*r_btc_h; regress next idio (1h,4h) on past idio (1h,4h), and on past BTC move, by year, non-overlapping anchors
for s in [a for a in assets if a!='BTC']:
    out['catchup'][s]={}
    la=np.log(P[s].close); lb=np.log(P['BTC'].close)
    r1a=la.diff(12); r1b=lb.diff(12)
    # rolling beta over 30d of hourly (non-overlapping) returns
    h=pd.DataFrame({'a':r1a.iloc[::12],'b':r1b.iloc[::12]}).dropna()
    cov=h.a.rolling(720).cov(h.b); var=h.b.rolling(720).var(); beta=(cov/var).reindex(la.index).ffill()
    for w,label in [(12,'1h'),(48,'4h')]:
        ra=la.diff(w); rb=lb.diff(w); idio=ra-beta*rb; y=ra.shift(-w)-beta*rb.shift(-w)   # v2 FIX: decision-time beta in the target
        X=pd.DataFrame({'idio_past':idio,'btc_past':rb,'y':y,'beta':beta}).iloc[::w].dropna()
        res={}
        for yr in years:
            d=X[X.index.year==yr]
            if len(d)<500: continue
            Xm=np.column_stack([np.ones(len(d)),d.idio_past.values,d.btc_past.values]); yv=d.y.values; b=np.linalg.lstsq(Xm,yv,rcond=None)[0]; resid=yv-Xm@b; s2=resid@resid/(len(d)-3); se=np.sqrt(np.diag(s2*np.linalg.inv(Xm.T@Xm)))
            # conditional: after large BTC moves (|btc_past| top quintile), mean next idio by sign of past idio
            big=d.btc_past.abs()>=d.btc_past.abs().quantile(0.8); lag=d.idio_past<0
            res[yr]={'b_idio':round(float(b[1]),4),'t_idio':round(float(b[1]/se[1]),2),'b_btc':round(float(b[2]),4),'t_btc':round(float(b[2]/se[2]),2),'beta_mean':round(float(d.beta.mean()),3),
                     'bigBTC_laggard_next_idio_bp':round(float(yv[big&lag].mean()*1e4),2),'bigBTC_leader_next_idio_bp':round(float(yv[big&~lag].mean()*1e4),2),'n':int(len(d))}
        out['catchup'][s][label]=res; print('catchup',s,label,{yr:(v['b_idio'],v['t_idio'],v['b_btc'],v['t_btc']) for yr,v in res.items()})
json.dump(out,open(os.path.join(os.path.dirname(__file__),'results','e1v2_leadlag_e4_catchup.json'),'w'),indent=1)
