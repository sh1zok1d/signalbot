import pandas as pd, numpy as np, os, warnings
warnings.filterwarnings('ignore')
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from features import FEATS
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
f = pd.read_pickle(os.path.join(D,'feat5m.pkl'))
print('== MDE table (two-sided 5%, 80% power, iid): pp ==')
for p in [0.5,0.85]:
    for N in [100,300,600,1000,2000,5000,15000,50000]:
        se=np.sqrt(p*(1-p)/N); print(f'p={p} N={N:6d}: SE {se*100:.2f} pp, MDE80 {2.8*se*100:.2f} pp')
print('\n== autocorrelation of non-overlapping returns by year (lag 1..3), and mean |r| ==')
for h,w in [('1h',12),('4h',48),('24h',288)]:
    s = f['r_'+h].iloc[::w].dropna()
    for y in sorted(set(s.index.year)):
        x = s[s.index.year==y].values
        ac = [np.corrcoef(x[:-k],x[k:])[0,1] for k in (1,2,3)]
        se = 1/np.sqrt(len(x))
        print(f'{h} {y}: N={len(x):5d} ac1 {ac[0]:+.3f} ac2 {ac[1]:+.3f} ac3 {ac[2]:+.3f} (se {se:.3f}) mean|r| {np.abs(x).mean()*1e4:.0f}bp sd {x.std()*1e4:.0f}bp')
print('\n== 4h logistic coefficients (train 2020-2024, standardized) ==')
sub = f.iloc[::48].dropna(subset=FEATS+['y_up_4h'])
tr = sub[sub.year<2025]
sc = StandardScaler().fit(tr[FEATS]); m = LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(tr[FEATS]), tr['y_up_4h'])
for c,b in sorted(zip(FEATS,m.coef_[0]), key=lambda t:-abs(t[1])): print(f'  {c:18s} {b:+.4f}')
print('\n== univariate AUC (test 2022-2026H1, sign chosen on 2020-2021) 4h ==')
from sklearn.metrics import roc_auc_score
te = sub[sub.year>=2022]; dv = sub[sub.year<2022]
for c in FEATS:
    s_ = np.sign(roc_auc_score(dv['y_up_4h'], dv[c])-0.5) or 1
    print(f'  {c:18s} AUC {roc_auc_score(te["y_up_4h"], s_*te[c]):.4f} (dev sign {int(s_):+d})')
