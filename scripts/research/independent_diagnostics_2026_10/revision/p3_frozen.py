"""DH3-P3 under the FROZEN definition (reproduced from scripts/research/dh3): z-score of count_long_short_ratio vs
trailing 720 hourly values (>=600, population std); q20/q80 pooled over the discovery surface 2020-10-01..2025-01-01;
hourly anchors = bar closing at HH:00; Y = up-first within 48 bars, 0.5 if unresolved or tie; barriers c(1+-X),
X = 0.5*1.2816*sigma*sqrt(48), sigma = sample std of last 288 5m log returns; estimand = OLS coefficient of S in
Y ~ 1 + S + hour_block + RV tercile + lag4h tercile + trend24h tercile (terciles within the cell); ISO-week clusters
cut at year boundaries; cluster bootstrap B=2000.  Part A: discovery surface (reproducibility of -5.92 pp).
Part B: 2025-01-01..2026-07-31 — an EXPOSED surface (read by run_p3.py); frozen cut points q20/q80 from part A."""
import pandas as pd, numpy as np, glob, zipfile, io, json
k=pd.read_pickle('data/btc5m.pkl')
rows=[]
for fz in sorted(glob.glob('data/metrics_early/*.zip')+glob.glob('data/metrics/*.zip')):
    raw=zipfile.ZipFile(fz).read(zipfile.ZipFile(fz).namelist()[0]); rows.append(pd.read_csv(io.BytesIO(raw)))
m=pd.concat(rows,ignore_index=True); m['ts']=pd.to_datetime(m['create_time'],utc=True,format='mixed'); m=m.sort_values('ts').drop_duplicates('ts').set_index('ts')
# frozen alignment: snapshot labelled t is placed at grid index t only if exactly 5m aligned (else dropped)
ls=m['count_long_short_ratio'].astype(float); ls=ls[ls.index==ls.index.floor('5min')]; ls=ls.reindex(k.index)
c=k.close.values; hi=k.high.values; lo=k.low.values; lc=np.log(c); r=np.diff(lc,prepend=np.nan)
sig=pd.Series(r,index=k.index).rolling(288,min_periods=288).std(ddof=1).values
n=len(k)
# anchors: bar j closing at HH:00 -> bar open HH:55
js=np.where((k.index.minute==55))[0]
# hourly series of ls at anchors (value labelled with bar j's open, used at bar j's close)
ls_h=ls.values[js]
z=np.full(len(js),np.nan)
for q in range(720,len(js)):
    h=ls_h[q-720:q]; h=h[np.isfinite(h)]
    if len(h)>=600 and h.std()>0: z[q]=(ls_h[q]-h.mean())/h.std()
# outcome
def outcome(j):
    if not np.isfinite(sig[j]) or j+48>=n: return np.nan
    X=0.5*1.2816*sig[j]*np.sqrt(48); up=c[j]*(1+X); dn=c[j]*(1-X)
    for t in range(j+1,j+49):
        hu=hi[t]>=up; hd=lo[t]<=dn
        if hu and hd: return 0.5
        if hu: return 1.0
        if hd: return 0.0
    return 0.5
Y=np.array([outcome(j) for j in js])
lag4=np.array([lc[j]-lc[j-48] if j>=48 else np.nan for j in js]); tr24=np.array([lc[j]-lc[j-288] if j>=288 else np.nan for j in js])
D=pd.DataFrame({'j':js,'ts':k.index[js],'z':z,'Y':Y,'sig':sig[js],'lag4':lag4,'tr24':tr24}).set_index('ts')
D['hour_block']=(D.index.hour+1)%24//4   # decision hour = close hour
iso=D.index.isocalendar(); D['cluster']=D.index.year.astype(str)+'-'+iso.week.astype(str)
def estimate(d, q20,q80, B=2000, seed=20261211):
    d=d.dropna(subset=['z','Y','sig','lag4','tr24']).copy()
    d=d[(d.z>=q80)|(d.z<=q20)]; d['S']=(d.z>=q80).astype(float)
    for col in ['sig','lag4','tr24']: d[col+'_t']=pd.qcut(d[col],3,labels=False,duplicates='drop')
    X=pd.get_dummies(d[['hour_block','sig_t','lag4_t','tr24_t']].astype(int).astype(str),drop_first=True).astype(float); X.insert(0,'S',d.S.values); X.insert(0,'const',1.0)
    Xm=X.values; y=d.Y.values
    beta=np.linalg.lstsq(Xm,y,rcond=None)[0]; b=beta[1]
    cl=d.cluster.values; uc=np.unique(cl); idx={u:np.where(cl==u)[0] for u in uc}; rng=np.random.default_rng(seed); bs=[]
    for _ in range(B):
        ii=np.concatenate([idx[u] for u in rng.choice(uc,len(uc),replace=True)]); bs.append(np.linalg.lstsq(Xm[ii],y[ii],rcond=None)[0][1])
    bs=np.array(bs); lo_,hi_=np.percentile(bs,[2.5,97.5]); p=min(1.0,max(2*min((bs<=0).mean(),(bs>=0).mean()),1/B))
    byyear={}
    for yr,g in d.groupby(d.index.year):
        if len(g)<50: continue
        Xg=X.loc[g.index] if False else Xm[np.isin(d.index,g.index)]; byyear[int(yr)]=(float(np.linalg.lstsq(Xg,g.Y.values,rcond=None)[0][1]*100),int(g.S.sum()),int((1-g.S).sum()))
    return {'beta_pp':float(b*100),'ci':[float(lo_*100),float(hi_*100)],'p_boot':float(p),'raw_state':float(d[d.S==1].Y.mean()),'raw_comp':float(d[d.S==0].Y.mean()),'n_state':int(d.S.sum()),'n_comp':int((1-d.S).sum()),'clusters':int(len(uc)),'by_year':byyear}
A=D[(D.index>=pd.Timestamp('2020-10-01',tz='UTC'))&(D.index<pd.Timestamp('2025-01-01',tz='UTC'))]
zz=A.z.dropna(); q20,q80=np.quantile(zz,0.2),np.quantile(zz,0.8)
resA=estimate(A,q20,q80); print('PART A discovery surface 2020-10..2024-12 (frozen cuts q20=%.4f q80=%.4f; record 1.2992 / -1.0324):'%(q80,q20)); print(json.dumps(resA,indent=1))
B_=D[(D.index>=pd.Timestamp('2025-01-01',tz='UTC'))&(D.index<pd.Timestamp('2026-08-01',tz='UTC'))]
resB=estimate(B_,q20,q80); print('PART B EXPOSED surface 2025-01..2026-07 with frozen cuts:'); print(json.dumps(resB,indent=1))
json.dump({'q20':float(q20),'q80':float(q80),'A':resA,'B_exposed':resB},open('rev/p3_frozen_results.json','w'),indent=1)
