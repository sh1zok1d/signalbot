"""Independent re-implementation on 1h bars built directly from the monthly zips (separate code path):
resample 5m -> 1h with pandas, features on 1h bars, explicit-shift targets, logistic regression via sklearn
and a from-scratch numpy logistic regression (Newton) as a cross-check."""
import pandas as pd, numpy as np, zipfile, io, glob, json, warnings
warnings.filterwarnings('ignore')
from sklearn.metrics import roc_auc_score
cols=['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']
fr=[]
for z in sorted(glob.glob('data/klines5m/*.zip')):
    raw=zipfile.ZipFile(z).read(zipfile.ZipFile(z).namelist()[0]); hdr=0 if raw[:9]==b'open_time' else None
    d=pd.read_csv(io.BytesIO(raw),header=hdr,names=None if hdr==0 else cols); d.columns=cols; fr.append(d)
k=pd.concat(fr); k['open_time']=k['open_time'].astype('int64'); k.loc[k.open_time>1e14,'open_time']//=1000
k['ts']=pd.to_datetime(k.open_time,unit='ms',utc=True); k=k.drop_duplicates('ts').set_index('ts').sort_index()
for c in ['open','high','low','close','quote_volume','taker_buy_quote_volume']: k[c]=k[c].astype(float)
H=k.resample('1h').agg({'open':'first','high':'max','low':'min','close':'last','quote_volume':'sum','taker_buy_quote_volume':'sum'}).dropna()
lc=np.log(H.close); r1=lc.diff()
X=pd.DataFrame(index=H.index)
for n in [1,4,24,168]: X[f'ret{n}']=lc-lc.shift(n)
for n in [4,24,168]: X[f'lrv{n}']=np.log(r1.pow(2).rolling(n).mean().pow(0.5)+1e-9)
for n in [4,24,168]:
    hh=H.high.rolling(n).max(); ll=H.low.rolling(n).min(); X[f'pos{n}']=(H.close-ll)/(hh-ll).clip(lower=1e-9); X[f'lrng{n}']=np.log((hh-ll)/H.close+1e-9)
for n in [1,4,24]: X[f'tk{n}']=H.taker_buy_quote_volume.rolling(n).sum()/H.quote_volume.rolling(n).sum().clip(lower=1)-0.5
X['hs']=np.sin(2*np.pi*H.index.hour/24); X['hc']=np.cos(2*np.pi*H.index.hour/24); X['we']=(H.index.dayofweek>=5).astype(float)
X['year']=H.index.year; X['week']=(H.index-H.index[0]).days//7
rng=np.random.default_rng(0)
def boot(Y,P,wk,B=300):
    uw=np.unique(wk); idx={w:np.where(wk==w)[0] for w in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); o.append(roc_auc_score(Y[ii],P[ii]))
    return np.percentile(o,[2.5,97.5])
def newton_logit(Xm,y,l2=1.0,it=50):
    Xb=np.hstack([np.ones((len(Xm),1)),Xm]); b=np.zeros(Xb.shape[1])
    for _ in range(it):
        p=1/(1+np.exp(-Xb@b)); g=Xb.T@(p-y)+l2*np.r_[0,b[1:]]; Hm=(Xb*(p*(1-p))[:,None]).T@Xb+l2*np.diag(np.r_[0,np.ones(len(b)-1)])
        b-=np.linalg.solve(Hm,g)
    return b
out={}
feats=[c for c in X.columns if c not in ('year','week')]
for h in [1,4,24]:
    y_r=lc.shift(-h)-lc; D=X.copy(); D['yr']=y_r; D=D.iloc[::h].dropna(); D=D[D.yr!=0]; D['y']=(D.yr>0).astype(float)
    D['end']=D.index+pd.Timedelta(hours=h); PP=[];YY=[];WW=[]
    for ty in [2022,2023,2024,2025,2026]:
        t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=D[(D.year<ty)&(D.end<t0)]; te=D[D.year==ty]
        lo=tr[feats].quantile(0.001); hi=tr[feats].quantile(0.999)
        mu=tr[feats].clip(lo,hi,axis=1).mean(); sd=tr[feats].clip(lo,hi,axis=1).std()+1e-12
        Xtr=((tr[feats].clip(lo,hi,axis=1)-mu)/sd).values; Xte=((te[feats].clip(lo,hi,axis=1)-mu)/sd).values
        b=newton_logit(Xtr,tr.y.values,l2=10.0); p=1/(1+np.exp(-(np.hstack([np.ones((len(Xte),1)),Xte])@b)))
        auc=roc_auc_score(te.y.values,p); ci=boot(te.y.values,p,te.week.values)
        g=(np.sign(p-0.5)*te.yr.values).mean()*1e4
        print(f'{h}h {ty}: AUC {auc:.4f} [{ci[0]:.4f},{ci[1]:.4f}] gross {g:+.2f}bp n={len(te)}')
        out[f'{h}h_{ty}']={'auc':float(auc),'ci':[float(ci[0]),float(ci[1])],'gross_bp':float(g),'n':int(len(te))}
        PP.append(p);YY.append(te.y.values);WW.append(te.week.values)
    P=np.concatenate(PP);Y=np.concatenate(YY);Wk=np.concatenate(WW); auc=roc_auc_score(Y,P); ci=boot(Y,P,Wk)
    print(f'{h}h POOLED: AUC {auc:.4f} [{ci[0]:.4f},{ci[1]:.4f}] n={len(Y)}'); out[f'{h}h_pooled']={'auc':float(auc),'ci':[float(ci[0]),float(ci[1])],'n':int(len(Y))}
json.dump(out,open('rev/indep_1h_results.json','w'),indent=1)
