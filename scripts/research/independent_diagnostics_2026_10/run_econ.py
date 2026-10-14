import pandas as pd, numpy as np, os, warnings
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from features import FEATS
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
f = pd.read_pickle(os.path.join(D,'feat5m.pkl'))
for c in FEATS: f[c] = f[c].clip(f[c].quantile(0.001), f[c].quantile(0.999))
h='4h'; sub = f.iloc[::48].dropna(subset=FEATS+['y_up_4h','y_r_4h']).copy()
P=[]; T=[]
for ty in [2022,2023,2024,2025,2026]:
    tr=sub[sub.year<ty]; te=sub[sub.year==ty]
    sc=StandardScaler().fit(tr[FEATS]); m=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(tr[FEATS]),tr['y_up_4h'])
    te=te.copy(); te['p']=m.predict_proba(sc.transform(te[FEATS]))[:,1]
    # vol tercile edges from training years only
    e=np.quantile(tr['lrv_24h'],[1/3,2/3]); te['volt']=np.digitize(te['lrv_24h'],e)
    e2=np.quantile(tr['r_4h'].abs(),[1/3,2/3]); te['mvt']=np.digitize(te['r_4h'].abs(),e2)
    T.append(te)
te=pd.concat(T)
def report(mask, label):
    d=te[mask]; side=np.sign(d['p']-0.5); g=(side*d['y_r_4h']).values
    if len(d)<30: print(f'{label:45s} n<30'); return
    yrs = d.groupby(d.index.year).apply(lambda x: (np.sign(x['p']-.5)*x['y_r_4h']).mean()*1e4)
    print(f'{label:45s} n={len(d):5d} hit {(g>0).mean():.3f} gross {g.mean()*1e4:+5.2f}bp  net(2bp) {g.mean()*1e4-2:+5.2f} net(4bp) {g.mean()*1e4-4:+5.2f} net(10bp) {g.mean()*1e4-10:+6.2f} | by year: '+' '.join(f'{y}:{v:+.1f}' for y,v in yrs.items()))
print('4h direction, logit, walk-forward 2022-2026H1. Costs = round trip (2bp≈maker both legs, 4bp≈maker+taker, 10bp≈taker both legs Binance VIP0)')
report(te['p'].notna(),'all anchors')
for th in [0.03,0.05,0.08,0.10]:
    report((te['p']-0.5).abs()>th, f'|p-0.5|>{th}')
for v in range(3):
    report(te['volt']==v, f'vol tercile {v} (all)')
    report((te['volt']==v)&((te['p']-0.5).abs()>0.05), f'vol tercile {v} & |p-.5|>0.05')
for v in range(3):
    report((te['mvt']==v)&((te['p']-0.5).abs()>0.05), f'|r_4h| tercile {v} & |p-.5|>0.05')
report((te['volt']==2)&(te['mvt']==2)&((te['p']-0.5).abs()>0.05), 'high vol & big move & |p-.5|>0.05')
