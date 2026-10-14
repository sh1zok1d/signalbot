"""E7: state dependence of cross-market information (development years only, exploratory).
For each alt and horizon (1h, 4h): OLS of next alt return on own past return, BTC past return, and interactions of the BTC
past return with (a) a large-|BTC move| dummy (top decile within the training years), (b) a high-correlation dummy (trailing 24h
corr with BTC above its median), (c) a high-dispersion dummy; plus conditional mean next returns of the alt and of its
idiosyncratic part after large BTC up / down moves.  Non-overlapping anchors; t-stats from OLS (iid), by year."""
import os, sys, pickle, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); from panel import DATA_DIR
D=pickle.load(open(os.path.join(DATA_DIR,'xm_panel12.pkl'),'rb')); P=D['P']; F=D['F']; assets=D['assets']
years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]; tag=sys.argv[2] if len(sys.argv)>2 else 'dev12'
alts=[a for a in assets if a!='BTC']; lb=np.log(P['BTC'].close); rb5=F['BTC']['r5']
r5=pd.DataFrame({a:F[a]['r5'] for a in alts}); disp=r5.sub(r5.mean(axis=1),axis=0).abs().mean(axis=1).rolling(288).mean()
out={}
for a in alts:
    la=np.log(P[a].close); ra5=F[a]['r5']; corr=ra5.rolling(288).corr(rb5)
    h1=pd.DataFrame({'a':la.diff(12).iloc[::12],'b':lb.diff(12).iloc[::12]}).dropna(); beta=(h1.a.rolling(720).cov(h1.b)/h1.b.rolling(720).var()).reindex(la.index).ffill()
    out[a]={}
    for h,w in [('1h',12),('4h',48)]:
        df=pd.DataFrame({'own':la.diff(w),'btc':lb.diff(w),'y':la.diff(w).shift(-w),'corr':corr,'disp':disp,'beta':beta,'present':P[a]['present']}).iloc[::w]
        df=df[df.present==1].dropna(); df['year']=df.index.year; df=df[df.year.isin(years)]
        df['big']=(df.btc.abs()>=df.btc.abs().quantile(0.9)).astype(float); df['hicorr']=(df['corr']>=df['corr'].median()).astype(float); df['hidisp']=(df.disp>=df.disp.median()).astype(float)
        df['y_idio']=df.y-df.beta*lb.diff(w).shift(-w).reindex(df.index)
        X=np.column_stack([np.ones(len(df)),df.own,df.btc,df.btc*df.big,df.btc*df.hicorr,df.btc*df.hidisp]); yv=df.y.values
        b=np.linalg.lstsq(X,yv,rcond=None)[0]; res_=yv-X@b; s2=res_@res_/(len(df)-X.shape[1]); se=np.sqrt(np.diag(s2*np.linalg.inv(X.T@X)))
        names=['const','own','btc','btc_x_big','btc_x_hicorr','btc_x_hidisp']; coef={n:(round(float(b[i]),4),round(float(b[i]/se[i]),2)) for i,n in enumerate(names)}
        up=df.btc>=df.btc.quantile(0.95); dn=df.btc<=df.btc.quantile(0.05)
        cond={'after_bigBTC_up_next_alt_bp':round(float(df.y[up].mean()*1e4),1),'after_bigBTC_up_next_idio_bp':round(float(df.y_idio[up].mean()*1e4),1),'n_up':int(up.sum()),
              'after_bigBTC_dn_next_alt_bp':round(float(df.y[dn].mean()*1e4),1),'after_bigBTC_dn_next_idio_bp':round(float(df.y_idio[dn].mean()*1e4),1),'n_dn':int(dn.sum()),
              'uncond_next_alt_bp':round(float(df.y.mean()*1e4),1)}
        out[a][h]={'coef':coef,'cond':cond,'n':int(len(df))}
        print(a,h,coef,cond,flush=True)
json.dump(out,open(os.path.join(os.path.dirname(__file__),'results',f'e7_states_{tag}.json'),'w'),indent=1)
