import pandas as pd, numpy as np, zipfile, io, glob, json, sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'diag')
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
def load_binance(pattern):
    cols=['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']; fr=[]
    for z in sorted(glob.glob(pattern)):
        raw=zipfile.ZipFile(z).read(zipfile.ZipFile(z).namelist()[0]); hdr=0 if raw[:9]==b'open_time' else None
        d=pd.read_csv(io.BytesIO(raw),header=hdr,names=None if hdr==0 else cols); d.columns=cols; fr.append(d)
    k=pd.concat(fr); k['open_time']=k['open_time'].astype('int64'); k.loc[k.open_time>1e14,'open_time']//=1000
    k['ts']=pd.to_datetime(k.open_time,unit='ms',utc=True); k=k.drop_duplicates('ts').set_index('ts').sort_index()
    full=pd.date_range(k.index[0],k.index[-1],freq='5min',tz='UTC'); k=k.reindex(full)
    for c in ['open','high','low','close']: k[c]=k[c].astype(float)
    k['close']=k['close'].ffill(); 
    for c in ['open','high','low']: k[c]=k[c].fillna(k['close'])
    k['qv']=k['quote_volume'].astype(float).fillna(0); k['tb']=k['taker_buy_quote_volume'].astype(float).fillna(0); return k[['open','high','low','close','qv','tb']]
def load_bitmex(path):
    d=pd.read_csv(path); d['ts']=pd.to_datetime(d.open_time_ms,unit='ms',utc=True); d=d.set_index('ts').sort_index()
    full=pd.date_range(d.index[0],d.index[-1],freq='5min',tz='UTC'); d=d.reindex(full)
    d['close']=d['close'].ffill(); 
    for c in ['open','high','low']: d[c]=d[c].fillna(d['close'])
    d['qv']=d['quote_usd'].fillna(0); d['tb']=d['taker_buy_quote_usd'].fillna(0); return d[['open','high','low','close','qv','tb']]
def feats(k):
    c=k.close.values; lc=np.log(c); r=np.diff(lc,prepend=lc[0]); f=pd.DataFrame(index=k.index)
    S=lambda x,n: pd.Series(x,index=k.index).rolling(n,min_periods=n).sum().values
    M=lambda x,n: pd.Series(x,index=k.index).rolling(n,min_periods=n).mean().values
    W={'5m':1,'15m':3,'1h':12,'4h':48,'24h':288,'7d':2016}
    for n,w in W.items(): f['r_'+n]=S(r,w)
    for n in ['1h','4h','24h','7d']: f['lrv_'+n]=np.log(np.sqrt(M(r*r,W[n]))+1e-9)
    f['volratio_1h_24h']=f.lrv_1h-f.lrv_24h; f['volratio_4h_7d']=f.lrv_4h-f.lrv_7d
    hi=k.high.values; lo=k.low.values
    for n in ['4h','24h','7d']:
        H=pd.Series(hi,index=k.index).rolling(W[n],min_periods=W[n]).max().values; L=pd.Series(lo,index=k.index).rolling(W[n],min_periods=W[n]).min().values
        f['pos_'+n]=(c-L)/np.maximum(H-L,1e-9); f['lrange_'+n]=np.log((H-L)/c+1e-9)
    for n in ['1h','4h','24h']: f['taker_'+n]=S(k.tb.values,W[n])/np.maximum(S(k.qv.values,W[n]),1e-9)-0.5
    f['lvol_1h_rel']=np.log(S(k.qv.values,12)+1)-np.log(M(S(k.qv.values,12),2016)+1); f['lvol_24h_rel']=np.log(S(k.qv.values,288)+1)-np.log(M(S(k.qv.values,288),2016)+1)
    hr=k.index.hour+k.index.minute/60; f['hod_sin']=np.sin(2*np.pi*hr/24); f['hod_cos']=np.cos(2*np.pi*hr/24); f['weekend']=(k.index.dayofweek>=5).astype(float)
    f['y_r']=pd.Series(lc,index=k.index).shift(-48).values-lc
    f['y_r_open']=np.log(pd.Series(c,index=k.index).shift(-48).values/pd.Series(k.open.values,index=k.index).shift(-1).values)
    f['week']=(k.index-k.index[0]).days//7; f['end']=k.index+pd.Timedelta(minutes=240); return f
FE=['r_5m','r_15m','r_1h','r_4h','r_24h','r_7d','lrv_1h','lrv_4h','lrv_24h','lrv_7d','volratio_1h_24h','volratio_4h_7d','pos_4h','pos_24h','pos_7d','lrange_4h','lrange_24h','lrange_7d','taker_1h','taker_4h','taker_24h','lvol_1h_rel','lvol_24h_rel','hod_sin','hod_cos','weekend']
rng=np.random.default_rng(0)
def boot(stat,wk,B=400):
    uw=np.unique(wk); idx={w:np.where(wk==w)[0] for w in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); o.append(stat(ii))
    return np.percentile(o,[2.5,97.5])
def run(name,f,folds):
    sub=f.iloc[::48].dropna(subset=FE+['y_r','y_r_open']); sub=sub[sub.y_r!=0]; T=[]
    for trmask,temask,lab in folds:
        tr=sub[trmask(sub)]; te=sub[temask(sub)].copy()
        lo=tr[FE].quantile(0.001); hi=tr[FE].quantile(0.999); Xtr=tr[FE].clip(lo,hi,axis=1); Xte=te[FE].clip(lo,hi,axis=1)
        sc=StandardScaler().fit(Xtr); m=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(Xtr),(tr.y_r>0).astype(int))
        te['p']=m.predict_proba(sc.transform(Xte))[:,1]; e=np.quantile(tr.lrv_24h,[1/3,2/3]); te['volt']=np.digitize(te.lrv_24h,e); te['fold']=lab; T.append(te)
    te=pd.concat(T); out={}
    for v in [0,1,2]:
        d=te[te.volt==v]; side=np.sign(d.p-0.5); g=(side*d.y_r).values; go=(side*d.y_r_open).values; wk=d.week.values
        ci=boot(lambda ii: g[ii].mean()*1e4,wk); big=np.abs(g)>=np.quantile(np.abs(g),0.95)
        o={'n':int(len(d)),'gross_bp':float(g.mean()*1e4),'ci':[float(ci[0]),float(ci[1])],'gross_open_bp':float(go.mean()*1e4),'hit':float((g>0).mean()),'net4':float(g.mean()*1e4-4),
           'auc':float(roc_auc_score((d.y_r>0).astype(int),d.p)) if d.y_r.gt(0).nunique()>1 else None,'top5pct_share_of_profit':float(g[big].sum()/g.sum()) if g.sum()!=0 else None,
           'median_bp':float(np.median(g)*1e4),'by_fold':{str(k_):float(v_) for k_,v_ in (d.assign(g=g).groupby('fold').g.mean()*1e4).items()}}
        out[f'tercile{v}']=o
        print(f'{name:28s} vol-tercile {v}: n={o["n"]:5d} gross {o["gross_bp"]:+6.2f} [{ci[0]:+.2f},{ci[1]:+.2f}] open-entry {o["gross_open_bp"]:+6.2f} hit {o["hit"]:.3f} AUC {o["auc"]} top5%share {o["top5pct_share_of_profit"]} median {o["median_bp"]:+.1f} folds {o["by_fold"]}')
    return out
yr=lambda f: f.index.year
if __name__=='__main__':
    R={}
    S='data/'
    btc=feats(load_binance(S+'klines5m/*.zip')); eth=feats(load_binance(S+'eth5m/*.zip')); bmx=feats(load_bitmex('/home/user/signalbot/docs/research_data/DH1_BITMEX_XBTUSD_TRADES_5M_V0/xbtusd_5m.csv.gz'))
    yr=lambda f: f.index.year
    fw=[(lambda s,ty=ty:(yr(s)<ty)&(s.end<pd.Timestamp(f'{ty}-01-01',tz='UTC')), lambda s,ty=ty: yr(s)==ty, str(ty)) for ty in [2022,2023,2024,2025,2026]]
    R['BTC_2022_2026_26feat']=run('BTC 2022-26 (selection surface)',btc,fw)
    R['ETH_2022_2026']=run('ETH 2022-26',eth,fw)
    bm=[(lambda s:(s.index<pd.Timestamp('2018-07-01',tz='UTC'))&(s.end<pd.Timestamp('2018-07-01',tz='UTC')), lambda s:(s.index>=pd.Timestamp('2018-07-01',tz='UTC'))&(s.index<pd.Timestamp('2019-01-01',tz='UTC')),'2018H2'),
        (lambda s:(s.index<pd.Timestamp('2019-01-01',tz='UTC'))&(s.end<pd.Timestamp('2019-01-01',tz='UTC')), lambda s: yr(s)==2019,'2019')]
    R['BITMEX_2018H2_2019']=run('BitMEX 2018H2+2019',bmx,bm)
    rv=[(lambda s: s.index>=pd.Timestamp('2022-01-01',tz='UTC'), lambda s:(yr(s)<=2021)&(s.end<pd.Timestamp('2022-01-01',tz='UTC')),'2020-21rev')]
    R['BTC_2020_2021_reverse']=run('BTC 2020-21 (reverse-time)',btc,rv)
    json.dump(R,open('rev/highvol_results.json','w'),indent=1)
