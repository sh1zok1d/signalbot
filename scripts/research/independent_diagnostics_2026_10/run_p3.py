# Independent time-disjoint check of DH3-P3 on 2025-01..2026-07 (NOTE: this read exposes the 2025/2026 Binance BTC positioning surface for the P3 claim)
import pandas as pd, numpy as np, os, glob, zipfile, io, warnings, sys
warnings.filterwarnings('ignore')
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
rows=[]
for fz in sorted(glob.glob(os.path.join(D,'metrics','*.zip'))):
    try:
        with zipfile.ZipFile(fz) as z: raw=z.read(z.namelist()[0])
    except Exception as e: print('bad',fz); continue
    df=pd.read_csv(io.BytesIO(raw)); rows.append(df)
m=pd.concat(rows,ignore_index=True)
m['ts']=pd.to_datetime(m['create_time'],utc=True, format='mixed')
m=m.sort_values('ts').drop_duplicates('ts').set_index('ts')
print(m.columns.tolist(), len(m), m.index.min(), m.index.max())
k=pd.read_pickle(os.path.join(D,'btc5m.pkl'))
mm=m.reindex(k.index, method='ffill', tolerance=pd.Timedelta('10min'))
k['ls_acc']=mm['count_long_short_ratio'].astype(float); k['ls_top_acc']=mm['count_toptrader_long_short_ratio'].astype(float)
k['ls_top_pos']=mm['sum_toptrader_long_short_ratio'].astype(float); k['taker_ls']=mm['sum_taker_long_short_vol_ratio'].astype(float); k['oi']=mm['sum_open_interest'].astype(float)
lc=np.log(k['close'].values); c=k['close'].values; hi=k['high'].values; lo=k['low'].values
r=np.diff(lc,prepend=lc[0]); sig=pd.Series(r,index=k.index).rolling(288,min_periods=288).std().values
# DH3-P3 style outcome: within the next 4h (48 bars), price goes UP first by X before DOWN by X, X = 0.5*1.2816*sigma*sqrt(48) (same barrier geometry as the Level Engine); outcome among resolved.
X = 0.5*1.2816*sig*np.sqrt(48)
n=len(k); up_first=np.full(n,np.nan)
H=hi; L=lo
for i in range(288, n-49):
    if not np.isfinite(X[i]): continue
    ub=c[i]*np.exp(X[i]); db=c[i]*np.exp(-X[i])
    for j in range(i+1,i+49):
        hu = H[j]>=ub; hd = L[j]<=db
        if hu and hd: up_first[i]=0.5; break
        if hu: up_first[i]=1.0; break
        if hd: up_first[i]=0.0; break
k['up_first']=up_first
k['y_up4h']=(pd.Series(lc,index=k.index).shift(-48).values-lc>0).astype(float)
# hourly anchors, exclude unresolved (nan) and ties
a=k.iloc[::12].copy()
a['year']=a.index.year
def cell(df, col, label):
    d=df.dropna(subset=[col,'up_first']); d=d[d['up_first']!=0.5]
    if len(d)<100: print(label,'n<100'); return
    q=d[col].quantile(0.8)  # top 20% within the evaluated period (DH3 used top quintile of the state)
    top=d[d[col]>=q]; rest=d[d[col]<q]
    p1=top['up_first'].mean(); p0=rest['up_first'].mean(); se=np.sqrt(p1*(1-p1)/len(top)+p0*(1-p0)/len(rest))
    # week-cluster bootstrap
    wk=((d.index-d.index[0]).days//7).values; dd=d.assign(wk=wk, istop=(d[col]>=q))
    rng=np.random.default_rng(0); uw=np.unique(wk); b=[]
    for _ in range(500):
        s=rng.choice(uw,len(uw),replace=True); x=pd.concat([dd[dd.wk==w] for w in s])
        b.append(x[x.istop]['up_first'].mean()-x[~x.istop]['up_first'].mean())
    lo_,hi_=np.percentile(b,[2.5,97.5])
    print(f'{label:40s} top20% up-first {p1*100:.1f}% (n={len(top)}) vs rest {p0*100:.1f}% (n={len(rest)}): diff {100*(p1-p0):+.2f} pp [95% {100*lo_:+.2f},{100*hi_:+.2f}]')
for yrs,label in [([2022,2023,2024],'2022-2024 (overlaps DH3 discovery)'),([2025,2026],'2025-01..2026-07 (time-disjoint)')]:
    d=a[a.year.isin(yrs)]
    print('==',label,'==')
    for col in ['ls_acc','ls_top_acc','ls_top_pos','taker_ls']:
        cell(d,col,f'{col} top-quintile')
    # also the plain 4h sign outcome for crowd-long
    d2=d.dropna(subset=['ls_acc','y_up4h']); q=d2['ls_acc'].quantile(0.8)
    print(f'  plain 4h up share: crowd-long {d2[d2.ls_acc>=q]["y_up4h"].mean()*100:.1f}% vs rest {d2[d2.ls_acc<q]["y_up4h"].mean()*100:.1f}%')
