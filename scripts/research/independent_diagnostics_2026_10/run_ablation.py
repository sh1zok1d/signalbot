import pandas as pd, numpy as np, os, json, warnings
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss
from features import FEATS
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
f = pd.read_pickle(os.path.join(D,'feat5m.pkl'))
for c in FEATS: f[c] = f[c].clip(f[c].quantile(0.001), f[c].quantile(0.999))
GROUPS = {
 'short_ret (5m,15m,1h)': ['r_5m','r_15m','r_1h'],
 'mid_ret (4h,24h)': ['r_4h','r_24h'],
 'long_ret (7d)': ['r_7d'],
 'vol/range/pos': ['lrv_1h','lrv_4h','lrv_24h','lrv_7d','volratio_1h_24h','volratio_4h_7d','pos_4h','pos_24h','pos_7d','lrange_4h','lrange_24h','lrange_7d'],
 'taker': ['taker_1h','taker_4h','taker_24h'],
 'volume': ['lvol_1h_rel','lvol_24h_rel'],
 'funding': ['funding','funding_24h','funding_z30d'],
 'clock': ['hod_sin','hod_cos','weekend'],
}
rng = np.random.default_rng(1)
def wf(sub, cols, h):
    P=[];Y=[];W=[];R=[]
    for ty in [2022,2023,2024,2025,2026]:
        tr = sub[sub.year<ty]; te = sub[sub.year==ty]
        sc = StandardScaler().fit(tr[cols]); m = LogisticRegression(C=0.1,max_iter=2000).fit(sc.transform(tr[cols]), tr['y_up_'+h])
        P.append(m.predict_proba(sc.transform(te[cols]))[:,1]); Y.append(te['y_up_'+h].values); W.append(te['week'].values); R.append(te['y_r_'+h].values)
    P=np.concatenate(P);Y=np.concatenate(Y);W=np.concatenate(W);R=np.concatenate(R)
    auc = roc_auc_score(Y,P)
    uw=np.unique(W); idx={w:np.where(W==w)[0] for w in uw}; b=[]
    for _ in range(300):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); b.append(roc_auc_score(Y[ii],P[ii]))
    lo,hi=np.percentile(b,[2.5,97.5])
    # long-short mean gross return in bp when trading sign(p-.5)
    g = np.sign(P-0.5)*R
    return auc, lo, hi, g.mean()*1e4, P, Y, W, R
for h,s in [('1h',12),('4h',48)]:
    sub = f.iloc[::s].dropna(subset=FEATS+['y_up_'+h,'y_r_'+h]).copy()
    print(f'\n===== {h}: pooled walk-forward 2022-2026H1, N={len(sub[sub.year>=2022])} =====')
    auc,lo,hi,g,P,Y,W,R = wf(sub, FEATS, h); print(f'ALL features        AUC {auc:.4f} [{lo:.4f},{hi:.4f}] gross {g:+.2f}bp/trade')
    for name,cols in GROUPS.items():
        auc,lo,hi,g,*_ = wf(sub, cols, h); print(f'ONLY {name:24s} AUC {auc:.4f} [{lo:.4f},{hi:.4f}] gross {g:+.2f}bp')
    for name,cols in GROUPS.items():
        rest=[c for c in FEATS if c not in cols]; auc,lo,hi,g,*_ = wf(sub, rest, h); print(f'DROP {name:24s} AUC {auc:.4f} [{lo:.4f},{hi:.4f}] gross {g:+.2f}bp')
    # conditional: AUC of ALL model within states
    auc,lo,hi,g,P,Y,W,R = wf(sub, FEATS, h)
    te = sub[sub.year>=2022].copy(); te['p']=P
    print('-- conditional AUC (ALL model) by state --')
    for col,q in [('lrv_24h',3),('r_4h',3),('funding_z30d',3),('lvol_1h_rel',3)]:
        te['bin']=pd.qcut(te[col],q,labels=False)
        for b_ in range(q):
            m=te['bin']==b_; print(f'  {col} tercile {b_}: AUC {roc_auc_score(te.loc[m,"y_up_"+h],te.loc[m,"p"]):.4f} N={m.sum()} gross {(np.sign(te.loc[m,"p"]-.5)*te.loc[m,"y_r_"+h]).mean()*1e4:+.2f}bp')
    te['absr4']=te['r_4h'].abs(); te['bin']=pd.qcut(te['absr4'],3,labels=False)
    for b_ in range(3):
        m=te['bin']==b_; print(f'  |r_4h| tercile {b_}: AUC {roc_auc_score(te.loc[m,"y_up_"+h],te.loc[m,"p"]):.4f} N={m.sum()}')
    m=te['weekend']==1; print(f'  weekend: AUC {roc_auc_score(te.loc[m,"y_up_"+h],te.loc[m,"p"]):.4f} N={m.sum()}; weekday: AUC {roc_auc_score(te.loc[~m,"y_up_"+h],te.loc[~m,"p"]):.4f}')
    hrs = te.index.hour
    for lo_,hi_ in [(0,8),(8,13),(13,17),(17,24)]:
        m=(hrs>=lo_)&(hrs<hi_); print(f'  UTC {lo_:02d}-{hi_:02d}: AUC {roc_auc_score(te.loc[m,"y_up_"+h],te.loc[m,"p"]):.4f} N={m.sum()}')
    # top-decile confidence
    conf=np.abs(P-0.5); q=np.quantile(conf,0.9); m=conf>=q
    print(f'  top-10% confidence: hit {((np.sign(P[m]-.5)*R[m])>0).mean():.3f} gross {(np.sign(P[m]-.5)*R[m]).mean()*1e4:+.2f}bp N={m.sum()}')
