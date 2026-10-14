"""Is AUC ~0.55 a ceiling?  Richer features (OI, positioning, ETH lead-lag, more lags, calendar) and more model classes,
walk-forward 2022-2026H1, 1h and 4h.  Also alternative 4h targets (up-first barrier; direction of large moves)."""
import pandas as pd, numpy as np, glob, zipfile, io, json, sys, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0,'diag'); sys.path.insert(0,'rev')
from features import FEATS
from highvol_test import load_binance
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, ExtraTreesClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
k=pd.read_pickle('data/btc5m.pkl'); f=pd.read_pickle('data/feat5m.pkl'); idx=k.index
lc=np.log(k.close.values); r=np.diff(lc,prepend=np.nan); L=pd.Series(lc,index=idx); R2=pd.Series(r*r,index=idx)
for n,w in [('2h',24),('8h',96),('12h',144),('2d',576),('3d',864),('30d',8640)]: f['r_'+n]=L-L.shift(w)
f['lrv_30d']=np.log(np.sqrt(R2.rolling(8640,min_periods=8640).mean())+1e-9); f['volratio_24h_30d']=f.lrv_24h-f.lrv_30d
rs=pd.Series(r,index=idx); f['skew_24h']=rs.rolling(288).skew(); f['kurt_24h']=rs.rolling(288).kurt()
f['ltrades_rel']=np.log(k['count'].rolling(12).sum()+1)-np.log(k['count'].rolling(12).sum().rolling(2016).mean()+1)
for d in range(7): f[f'dow{d}']=(idx.dayofweek==d).astype(float)
rows=[]
for fz in sorted(glob.glob('data/metrics_early/*.zip')+glob.glob('data/metrics/*.zip')):
    raw=zipfile.ZipFile(fz).read(zipfile.ZipFile(fz).namelist()[0]); rows.append(pd.read_csv(io.BytesIO(raw)))
m=pd.concat(rows,ignore_index=True); m['ts']=pd.to_datetime(m['create_time'],utc=True,format='mixed'); m=m.sort_values('ts').drop_duplicates('ts').set_index('ts'); m.index=m.index.floor('5min'); m=m[~m.index.duplicated()]
mm=m.reindex(idx).ffill(limit=12)   # snapshot labelled with bar open (floored to the 5m grid), used at bar close; gaps up to 1h carried
oi=mm['sum_open_interest'].astype(float)
for n,w in [('1h',12),('4h',48),('24h',288)]: f['doi_'+n]=np.log(oi/oi.shift(w))
f['oi_z30d']=(oi-oi.rolling(8640,min_periods=4000).mean())/(oi.rolling(8640,min_periods=4000).std()+1e-9)
for col,name in [('count_long_short_ratio','ls_acc'),('count_toptrader_long_short_ratio','ls_top'),('sum_toptrader_long_short_ratio','ls_top_pos'),('sum_taker_long_short_vol_ratio','taker_ls')]:
    s=mm[col].astype(float); f[name+'_z']=(s-s.rolling(8640,min_periods=4000).mean())/(s.rolling(8640,min_periods=4000).std()+1e-9); f[name+'_d24h']=s-s.shift(288)
eth=load_binance('data/eth5m/*.zip'); el=np.log(eth.close).reindex(idx)
for n,w in [('1h',12),('4h',48),('24h',288)]: f['eth_r_'+n]=el-el.shift(w); f['ethbtc_r_'+n]=f['eth_r_'+n]-f['r_'+n]
er=el.diff(); f['eth_lrv_24h']=np.log(np.sqrt((er*er).rolling(288).mean())+1e-9)
EXTRA=['r_2h','r_8h','r_12h','r_2d','r_3d','r_30d','lrv_30d','volratio_24h_30d','skew_24h','kurt_24h','ltrades_rel']+[f'dow{d}' for d in range(7)]+['doi_1h','doi_4h','doi_24h','oi_z30d']+[c for c in f.columns if c.endswith('_z') and c.startswith(('ls_','taker_ls'))]+[c for c in f.columns if c.endswith('_d24h')]+['eth_r_1h','eth_r_4h','eth_r_24h','ethbtc_r_1h','ethbtc_r_4h','ethbtc_r_24h','eth_lrv_24h']
RICH=FEATS+EXTRA
METRIC_COLS=['doi_1h','doi_4h','doi_24h','oi_z30d']+[c for c in EXTRA if c.startswith(('ls_','taker_ls'))]
f[RICH]=f[RICH].replace([np.inf,-np.inf],np.nan)
for c in METRIC_COLS: f[c]=f[c].fillna(0.0)   # missing positioning/OI -> neutral value (coverage gaps in the metrics archive)
# alternative 4h targets
sig=pd.Series(r,index=idx).rolling(288,min_periods=288).std(ddof=1).values; X=0.5*1.2816*sig*np.sqrt(48)
hi=k.high.values; lo=k.low.values; c=k.close.values; n=len(k)
def upfirst_all():
    out=np.full(n,np.nan)
    for i in range(288,n-49,48):
        if not np.isfinite(X[i]): continue
        ub=c[i]*(1+X[i]); db=c[i]*(1-X[i])
        for j in range(i+1,i+49):
            hu=hi[j]>=ub; hd=lo[j]<=db
            if hu and hd: break
            if hu: out[i]=1.0; break
            if hd: out[i]=0.0; break
    return out
f['y_upfirst_4h']=upfirst_all(); f['bigmove_4h']=(np.abs(f['y_r_4h'])>sig*np.sqrt(48)).astype(float)
rng=np.random.default_rng(0)
def boot(Y,P,wk,B=300):
    uw=np.unique(wk); id_={w:np.where(wk==w)[0] for w in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([id_[w] for w in rng.choice(uw,len(uw),replace=True)]); o.append(roc_auc_score(Y[ii],P[ii]))
    return np.percentile(o,[2.5,97.5])
def models():
    return {'logit':LogisticRegression(C=0.1,max_iter=3000),'gbm_small':HistGradientBoostingClassifier(max_iter=300,learning_rate=0.03,max_depth=3,min_samples_leaf=300,l2_regularization=1.0,random_state=0),
            'gbm_big':HistGradientBoostingClassifier(max_iter=600,learning_rate=0.03,max_depth=6,min_samples_leaf=100,l2_regularization=1.0,early_stopping=True,validation_fraction=0.15,random_state=0),
            'rf':RandomForestClassifier(n_estimators=300,min_samples_leaf=200,max_features=0.3,n_jobs=2,random_state=0),'et':ExtraTreesClassifier(n_estimators=300,min_samples_leaf=200,max_features=0.3,n_jobs=2,random_state=0),
            'mlp':MLPClassifier(hidden_layer_sizes=(64,32),alpha=1e-2,early_stopping=True,max_iter=300,random_state=0),'knn500':KNeighborsClassifier(n_neighbors=500,n_jobs=2)}
res={}
for h,s,ycol in [('4h',48,'y_up_4h'),('1h',12,'y_up_1h'),('4h_upfirst',48,'y_upfirst_4h'),('4h_bigmove_dir',48,'y_up_4h')]:
    hh=h.split('_')[0]; w={'4h':48,'1h':12}[hh]
    sub=f.iloc[::s].copy(); sub['end']=sub.index+pd.Timedelta(minutes=5*w)
    sub=sub.dropna(subset=RICH+[ycol,'y_r_'+hh]); sub=sub[sub['y_r_'+hh]!=0]
    if h=='4h_bigmove_dir': sub=sub[sub.bigmove_4h==1]
    sub=sub[sub.index>=pd.Timestamp('2020-11-01',tz='UTC')]
    res[h]={}; PP={}; YY=[]; WW=[]
    for ty in [2022,2023,2024,2025,2026]:
        t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=sub[(sub.year<ty)&(sub.end<t0)]; te=sub[sub.year==ty]
        yy=te[ycol].values; YY.append(yy); WW.append(te.week.values); row={'n_tr':len(tr),'n_te':len(te)}
        for fs_name,cols in [('base29',FEATS),('rich',RICH)]:
            lo_=tr[cols].quantile(0.001); hi_=tr[cols].quantile(0.999); Xtr=tr[cols].clip(lo_,hi_,axis=1); Xte=te[cols].clip(lo_,hi_,axis=1)
            sc=StandardScaler().fit(Xtr); Ztr=sc.transform(Xtr); Zte=sc.transform(Xte); ytr=tr[ycol].values
            preds={}
            for mn,mdl in models().items():
                if fs_name=='base29' and mn not in ('logit','gbm_small','gbm_big'): continue
                if h=='1h' and mn in ('knn500','mlp','et'): continue
                mdl.fit(Ztr,ytr); preds[mn]=mdl.predict_proba(Zte)[:,1]
            preds['ensemble']=np.mean([preds[q] for q in preds],axis=0)
            for mn,p in preds.items():
                key=f'{fs_name}:{mn}'; row[key]=float(roc_auc_score(yy,p)); PP.setdefault(key,[]).append(p)
        res[h][ty]=row; print(h,ty,{q:round(v,4) for q,v in row.items() if isinstance(v,float)})
    Y=np.concatenate(YY); Wk=np.concatenate(WW); pooled={}
    for key,ps in PP.items():
        P=np.concatenate(ps); ci=boot(Y,P,Wk); pooled[key]={'auc':float(roc_auc_score(Y,P)),'ci':[float(ci[0]),float(ci[1])]}
    best_hindsight=np.mean([max(v for q,v in res[h][ty].items() if isinstance(v,float)) for ty in res[h]])
    res[h]['pooled']=pooled; res[h]['hindsight_best_per_year_mean_auc']=float(best_hindsight); res[h]['n']=int(len(Y))
    print(h,'POOLED',{q:(round(v['auc'],4),[round(x,4) for x in v['ci']]) for q,v in pooled.items()},'hindsight-best mean',round(best_hindsight,4))
json.dump(res,open('rev/ceiling_results.json','w'),indent=1)
