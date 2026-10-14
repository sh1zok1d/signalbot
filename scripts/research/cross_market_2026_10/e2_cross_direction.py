"""E2: does information from other assets improve the direction forecast of asset X at 1h / 4h?
Models: logit (C=0.1) and small GBM; feature sets: own | own+BTC | own+market(EW alt index) | own+all.
Walk-forward test years given on the command line (development: 2022 2023 2024)."""
import os, sys, pickle, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore'); sys.path.insert(0, os.path.dirname(__file__))
from panel import DATA_DIR, OWN, XFEATS
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss
D=pickle.load(open(os.path.join(DATA_DIR,'xm_panel.pkl'),'rb')); P=D['P']; F=D['F']; assets=D['assets']
test_years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]
tag=sys.argv[2] if len(sys.argv)>2 else 'dev'
# equal-weight alt index (all assets except BTC) returns and RV, from 5m log returns where present
alts=[a for a in assets if a!='BTC']
r5=pd.DataFrame({a:F[a]['r5'] for a in alts}); mkt=r5.mean(axis=1)
MK=pd.DataFrame(index=mkt.index)
for n,w in [('5m',1),('15m',3),('1h',12),('4h',48),('24h',288)]: MK['mkt_r_'+n]=mkt.rolling(w).sum()
for n,w in [('1h',12),('4h',48),('24h',288)]: MK['mkt_lrv_'+n]=np.log(np.sqrt((mkt*mkt).rolling(w).mean())+1e-9)
# dispersion and realized correlation (trailing 24h of 5m returns)
MK['disp_24h']=r5.rolling(288).std().mean(axis=1)/ (r5.rolling(288).std().mean(axis=1).rolling(2016).mean()+1e-12)
rb=F['BTC']['r5']; MK['corr_btc_24h']=pd.concat([r5[a].rolling(288).corr(rb) for a in alts],axis=1).mean(axis=1)
rng=np.random.default_rng(0)
def boot(stat,wk,B=300):
    uw=np.unique(wk); idx={w:np.where(wk==w)[0] for w in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); o.append(stat(ii))
    return np.percentile(o,[2.5,97.5])
res={}
for X in assets:
    for h,w in [('1h',12),('4h',48)]:
        df=F[X][OWN+['y_r_'+h]].copy(); df.columns=['own_'+c for c in OWN]+['y']
        bt=F['BTC'][XFEATS].add_prefix('btc_'); df=df.join(bt).join(MK)
        for a in assets:
            if a in (X,'BTC'): continue
            df=df.join(F[a][['r_1h','r_4h','r_24h','lrv_24h']].add_prefix(a.lower()+'_'))
        df['present']=P[X]['present']; df=df.iloc[::w]; df=df[(df.present==1)&(df.y!=0)].drop(columns='present').dropna()
        df['year']=df.index.year; df['week']=(df.index-df.index[0]).days//7; df['end']=df.index+pd.Timedelta(minutes=5*w)
        own=[c for c in df.columns if c.startswith('own_')]; btc=[c for c in df.columns if c.startswith('btc_')]; mk=[c for c in MK.columns]; others=[c for c in df.columns if any(c.startswith(a.lower()+'_') for a in assets if a not in (X,'BTC'))]
        sets={'own':own,'own+btc':own+btc,'own+mkt':own+mk,'own+all':own+btc+mk+others}
        if X=='BTC': sets={'own':own,'own+mkt':own+mk,'own+all':own+mk+others}
        PP={}; YY=[]; WW=[]; RR=[]
        for ty in test_years:
            t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=df[(df.year<ty)&(df.end<t0)]; te=df[df.year==ty]
            if len(tr)<1500 or len(te)<300: continue
            y=(tr.y>0).astype(int).values; yt=(te.y>0).astype(int).values; YY.append(yt); WW.append(te.week.values); RR.append(te.y.values)
            for name,cols in sets.items():
                lo=tr[cols].quantile(0.001); hi=tr[cols].quantile(0.999); Xtr=tr[cols].clip(lo,hi,axis=1); Xte=te[cols].clip(lo,hi,axis=1)
                sc=StandardScaler().fit(Xtr); m=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(Xtr),y); PP.setdefault(name+':logit',[]).append(m.predict_proba(sc.transform(Xte))[:,1])
                g=HistGradientBoostingClassifier(max_iter=300,learning_rate=0.03,max_depth=3,min_samples_leaf=200,l2_regularization=1.0,random_state=0).fit(Xtr,y); PP.setdefault(name+':gbm',[]).append(g.predict_proba(Xte)[:,1])
        if not YY: continue
        Y=np.concatenate(YY); Wk=np.concatenate(WW); R=np.concatenate(RR); row={'n':int(len(Y)),'years':test_years}
        base={k:np.concatenate(v) for k,v in PP.items()}
        for k,p in base.items():
            auc=roc_auc_score(Y,p); ci=boot(lambda ii: roc_auc_score(Y[ii],p[ii]),Wk); g=np.sign(p-0.5)*R
            row[k]={'auc':round(float(auc),4),'ci':[round(float(ci[0]),4),round(float(ci[1]),4)],'gross_bp':round(float(g.mean()*1e4),2)}
        for mdl in ['logit','gbm']:
            p0=base['own:'+mdl]
            for name in sets:
                if name=='own': continue
                p1=base[name+':'+mdl]; d=roc_auc_score(Y,p1)-roc_auc_score(Y,p0); ci=boot(lambda ii: roc_auc_score(Y[ii],p1[ii])-roc_auc_score(Y[ii],p0[ii]),Wk)
                row[f'dAUC {name} vs own ({mdl})']={'d':round(float(d),4),'ci':[round(float(ci[0]),4),round(float(ci[1]),4)]}
        res[f'{X}_{h}']=row
        print(X,h,'n',len(Y),{k:v['auc'] for k,v in row.items() if isinstance(v,dict) and 'auc' in v},{k:(v['d'],v['ci']) for k,v in row.items() if k.startswith('dAUC')},flush=True)
json.dump(res,open(os.path.join(os.path.dirname(__file__),'results',f'e2_cross_direction_{tag}.json'),'w'),indent=1)
