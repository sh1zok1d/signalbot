"""Corrected walk-forward (v2): train-only clipping bounds, purge of training anchors whose horizon ends
at/after the test year start, ties excluded from the direction target, per-year + pooled week-block CIs.
Compares with the original run on the same feature matrix."""
import pandas as pd, numpy as np, json, warnings, sys
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss
sys.path.insert(0,'diag'); from features import FEATS
f = pd.read_pickle('data/feat5m.pkl')
W = {'1h':12,'4h':48,'24h':288}
STRIDE = {'1h':12,'4h':48,'24h':288}   # v2: 24h on daily anchors too (no overlap)
rng = np.random.default_rng(0)
def boot(stat, weeks, B=400):
    uw=np.unique(weeks); idx={w:np.where(weeks==w)[0] for w in uw}; out=[]
    for _ in range(B):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); out.append(stat(ii))
    return np.percentile(out,[2.5,97.5])
res={}
for h in ['1h','4h','24h']:
    s=STRIDE[h]; w=W[h]
    sub=f.iloc[::s].dropna(subset=FEATS+['y_r_'+h,'y_lrv_'+h,'y_lrange_'+h]).copy()
    sub['end']=sub.index+pd.Timedelta(minutes=5*w)
    sub=sub[sub['y_r_'+h]!=0]; sub['y']=(sub['y_r_'+h]>0).astype(float)
    res[h]={}; PP={'logit':[],'gbm':[]}; YY=[]; WW=[]; RR=[]
    for ty in [2022,2023,2024,2025,2026]:
        t0=pd.Timestamp(f'{ty}-01-01',tz='UTC')
        tr=sub[(sub.year<ty)&(sub['end']<t0)]; te=sub[sub.year==ty]
        lo_=tr[FEATS].quantile(0.001); hi_=tr[FEATS].quantile(0.999)
        Xtr=tr[FEATS].clip(lo_,hi_,axis=1); Xte=te[FEATS].clip(lo_,hi_,axis=1)
        sc=StandardScaler().fit(Xtr); ytr=tr['y'].values; yte=te['y'].values
        lr=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(Xtr),ytr)
        gb=HistGradientBoostingClassifier(max_iter=300,learning_rate=0.03,max_depth=3,min_samples_leaf=300,l2_regularization=1.0,random_state=0).fit(Xtr,ytr)
        out={'n_train':len(tr),'n_test':len(te),'base':float(yte.mean())}
        pb=ytr.mean(); ll0=log_loss(yte,np.full(len(yte),pb))
        for name,p in [('logit',lr.predict_proba(sc.transform(Xte))[:,1]),('gbm',gb.predict_proba(Xte)[:,1])]:
            auc=roc_auc_score(yte,p); ci=boot(lambda ii: roc_auc_score(yte[ii],p[ii]),te['week'].values)
            r=te['y_r_'+h].values; g=np.sign(p-0.5)*r
            out[name]={'auc':float(auc),'ci':[float(ci[0]),float(ci[1])],'ll_skill':float(1-log_loss(yte,p)/ll0),'gross_bp_all':float(g.mean()*1e4),
                       'gross_bp_conf05':float(g[np.abs(p-0.5)>0.05].mean()*1e4) if (np.abs(p-0.5)>0.05).sum()>20 else None,'n_conf05':int((np.abs(p-0.5)>0.05).sum())}
            PP[name].append(p)
        YY.append(yte); WW.append(te['week'].values); RR.append(te['y_r_'+h].values)
        for tgt,persist in [('y_lrv_'+h,'lrv_'+h),('y_lrange_'+h,'lrange_'+h if 'lrange_'+h in f.columns else 'lrv_'+h)]:
            yv=tr[tgt].values; yvt=te[tgt].values
            pr=Ridge(alpha=1.0).fit(sc.transform(Xtr),yv).predict(sc.transform(Xte))
            pg=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.03,max_depth=3,min_samples_leaf=300,random_state=0).fit(Xtr,yv).predict(Xte)
            a,b=np.polyfit(tr[persist].values,yv,1); pp=a*te[persist].values+b
            r2=lambda pred,ref: float(1-np.sum((yvt-pred)**2)/np.sum((yvt-ref)**2))
            out[tgt]={'r2_ridge':r2(pr,yv.mean()),'r2_gbm':r2(pg,yv.mean()),'r2_persist':r2(pp,yv.mean()),'r2_ridge_vs_persist':r2(pr,pp)}
        res[h][ty]=out
        print(h,ty,'logit AUC %.4f [%.4f,%.4f] gbm %.4f | lrv R2 ridge %.3f persist %.3f | n_tr %d n_te %d'%(out['logit']['auc'],*out['logit']['ci'],out['gbm']['auc'],out['y_lrv_'+h]['r2_ridge'],out['y_lrv_'+h]['r2_persist'],len(tr),len(te)))
    Y=np.concatenate(YY); Wk=np.concatenate(WW); R=np.concatenate(RR)
    for name in ['logit','gbm']:
        P=np.concatenate(PP[name]); auc=roc_auc_score(Y,P); ci=boot(lambda ii: roc_auc_score(Y[ii],P[ii]),Wk)
        g=np.sign(P-0.5)*R; gci=boot(lambda ii: g[ii].mean()*1e4,Wk)
        res[h]['pooled_'+name]={'auc':float(auc),'ci':[float(ci[0]),float(ci[1])],'gross_bp':float(g.mean()*1e4),'gross_ci':[float(gci[0]),float(gci[1])],'n':int(len(Y))}
        print(h,'POOLED',name,'AUC %.4f [%.4f,%.4f] gross %.2f bp [%.2f,%.2f] n=%d'%(auc,*ci,g.mean()*1e4,*gci,len(Y)))
json.dump(res,open('rev/wf_v2_results.json','w'),indent=1)
