"""E3 v2 (beta-leak fixed): relative return and idiosyncratic reversal.  (i) Pair object: idio_h = r_X,h - beta*r_BTC,h; predict sign of next idio
with own + BTC + relative features (walk-forward, logit), vs baselines: sign(-idio_past) (pure reversal rule), zero.
(ii) Cross-section at 4h anchors over all assets: predicted h-return rank vs realized; rank IC and top-minus-bottom portfolio,
vs reversal / momentum / beta-ranked baselines.  Test years on the command line."""
import os, sys, pickle, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore'); sys.path.insert(0, os.path.dirname(__file__))
from panel import DATA_DIR, OWN
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
D=pickle.load(open(os.path.join(DATA_DIR,os.environ.get('XM_PANEL','xm_panel.pkl')),'rb')); P=D['P']; F=D['F']; assets=D['assets']
test_years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]; tag=sys.argv[2] if len(sys.argv)>2 else 'dev'
rng=np.random.default_rng(0)
def boot(stat,wk,B=300):
    uw=np.unique(wk); idx={w:np.where(wk==w)[0] for w in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[w] for w in rng.choice(uw,len(uw),replace=True)]); o.append(stat(ii))
    return np.percentile(o,[2.5,97.5])
lb=np.log(P['BTC'].close); res={'pairs':{},'xsec':{}}
# ---------- (i) pairs: idiosyncratic reversal
for X in [a for a in assets if a!='BTC']:
    la=np.log(P[X].close)
    h1=pd.DataFrame({'a':la.diff(12).iloc[::12],'b':lb.diff(12).iloc[::12]}).dropna(); beta=(h1.a.rolling(720).cov(h1.b)/h1.b.rolling(720).var()).reindex(la.index).ffill()
    for h,w in [('1h',12),('4h',48)]:
        ra=la.diff(w); rb=lb.diff(w); idio=ra-beta*rb
        # v2 FIX: the target uses the decision-time beta(t), not beta(t+w): y = r_X(t->t+w) - beta(t) * r_BTC(t->t+w)
        idio_fwd=ra.shift(-w)-beta*rb.shift(-w)
        df=pd.DataFrame({'idio_1h':la.diff(12)-beta*lb.diff(12),'idio_4h':la.diff(48)-beta*lb.diff(48),'idio_24h':la.diff(288)-beta*lb.diff(288),'beta':beta,'btc_r_1h':lb.diff(12),'btc_r_4h':lb.diff(48),'btc_r_24h':lb.diff(288)})
        df=df.join(F[X][OWN].add_prefix('own_')).join(F['BTC'][['lrv_1h','lrv_4h','lrv_24h','pos_24h','taker_1h','taker_4h']].add_prefix('btc_'))
        df['y']=idio_fwd; df['y_leaky']=idio.shift(-w); df['y_abs']=ra.shift(-w); df['y_btc']=rb.shift(-w); df['present']=P[X]['present']
        df=df.iloc[::w]; df=df[(df.present==1)].drop(columns='present').dropna(); df=df[df.y!=0]
        df['year']=df.index.year; df['week']=(df.index-df.index[0]).days//7; df['end']=df.index+pd.Timedelta(minutes=5*w)
        cols=[c for c in df.columns if c not in ('y','y_leaky','y_abs','y_btc','year','week','end')]
        leak={'corr_y_leaky_vs_fixed':round(float(np.corrcoef(df.y,df.y_leaky)[0,1]),5),'sign_agree':round(float((np.sign(df.y)==np.sign(df.y_leaky)).mean()),5)}
        PP=[];YY=[];WW=[];RR=[];RB=[];BB=[];IP=[]
        for ty in test_years:
            t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=df[(df.year<ty)&(df.end<t0)]; te=df[df.year==ty]
            if len(tr)<1500 or len(te)<300: continue
            lo=tr[cols].quantile(0.001); hi=tr[cols].quantile(0.999); sc=StandardScaler().fit(tr[cols].clip(lo,hi,axis=1))
            m=LogisticRegression(C=0.1,max_iter=3000).fit(sc.transform(tr[cols].clip(lo,hi,axis=1)),(tr.y>0).astype(int))
            PP.append(m.predict_proba(sc.transform(te[cols].clip(lo,hi,axis=1)))[:,1]); YY.append((te.y>0).astype(int).values); WW.append(te.week.values); RR.append(te.y_abs.values); RB.append(te.y_btc.values); BB.append(te.beta.values); IP.append(te['idio_'+h].values)
        if not YY: continue
        p=np.concatenate(PP); Y=np.concatenate(YY); Wk=np.concatenate(WW); ra_=np.concatenate(RR); rb_=np.concatenate(RB); b_=np.concatenate(BB); ip=np.concatenate(IP)
        auc=roc_auc_score(Y,p); ci=boot(lambda ii: roc_auc_score(Y[ii],p[ii]),Wk)
        auc_rule=roc_auc_score(Y,-ip); cir=boot(lambda ii: roc_auc_score(Y[ii],-ip[ii]),Wk)
        # pair economics: position s=sign(p-.5) in X, hedge -s*beta in BTC; costs 2 legs
        s=np.sign(p-0.5); pair=s*(ra_-b_*rb_); legs=1+np.abs(b_)
        srule=-np.sign(ip); pair_rule=srule*(ra_-b_*rb_)
        row={'leak':leak,'n':int(len(Y)),'auc_model':round(float(auc),4),'ci':[round(float(x),4) for x in ci],'auc_rule_reverse_idio':round(float(auc_rule),4),'ci_rule':[round(float(x),4) for x in cir],
             'pair_gross_bp':round(float(pair.mean()*1e4),2),'pair_ci':[round(float(x),2) for x in boot(lambda ii: pair[ii].mean()*1e4,Wk)],'pair_net_4bp_per_leg':round(float((pair-4e-4*legs).mean()*1e4),2),
             'pair_rule_gross_bp':round(float(pair_rule.mean()*1e4),2),'pair_sd_bp':round(float(pair.std()*1e4),1),'beta_mean':round(float(b_.mean()),3),
             'by_year_gross_bp':{int(y):round(float(pair[np.concatenate([np.full(len(v),ty) for v,ty in zip(YY,test_years)])==y].mean()*1e4),2) for y in test_years}}
        res['pairs'][f'{X}_{h}']=row; print('PAIR',X,h,row,flush=True)
# ---------- (ii) cross-section at 4h anchors
h,w='4h',48
rows=[]
for a in assets:
    f=F[a][OWN+['y_r_4h']].copy(); f['asset']=a; f['present']=P[a]['present']; f['r_btc_4h']=F['BTC']['r_4h']; f['r_btc_24h']=F['BTC']['r_24h']
    la=np.log(P[a].close); h1=pd.DataFrame({'a':la.diff(12).iloc[::12],'b':lb.diff(12).iloc[::12]}).dropna(); f['beta']=(h1.a.rolling(720).cov(h1.b)/h1.b.rolling(720).var()).reindex(la.index).ffill()
    rows.append(f.iloc[::w])
CS=pd.concat(rows); CS=CS[(CS.present==1)].dropna(); CS['year']=CS.index.year; CS['week']=(CS.index-CS.index.min()).days//7; CS['end']=CS.index+pd.Timedelta(hours=4)
CS['ts']=CS.index
# cross-sectionally demeaned target (relative to equal-weight mean of assets present at that anchor)
CS['y_rel']=CS.y_r_4h-CS.groupby('ts').y_r_4h.transform('mean')
feat=OWN+['r_btc_4h','r_btc_24h','beta']
ICs={'model':[], 'rev_1h':[], 'rev_4h':[], 'rev_24h':[], 'mom_7d':[], 'beta_x_btcdir':[]}; PNL={k:[] for k in ICs}; WKS=[]
for ty in test_years:
    t0=pd.Timestamp(f'{ty}-01-01',tz='UTC'); tr=CS[(CS.year<ty)&(CS.end<t0)]; te=CS[CS.year==ty]
    if len(tr)<3000: continue
    lo=tr[feat].quantile(0.001); hi=tr[feat].quantile(0.999); sc=StandardScaler().fit(tr[feat].clip(lo,hi,axis=1))
    m=Ridge(alpha=10.0).fit(sc.transform(tr[feat].clip(lo,hi,axis=1)),tr.y_rel.values); te=te.copy(); te['pred']=m.predict(sc.transform(te[feat].clip(lo,hi,axis=1)))
    # BTC own-direction forecast for the beta baseline: sign of a BTC-only logit on OWN feats
    trb=F['BTC'][OWN+['y_r_4h']].iloc[::w].dropna(); trb=trb[(trb.index.year<ty)&(trb.index+pd.Timedelta(hours=4)<t0)]
    scb=StandardScaler().fit(trb[OWN]); mb=LogisticRegression(C=0.1,max_iter=3000).fit(scb.transform(trb[OWN]),(trb.y_r_4h>0).astype(int))
    pb=pd.Series(mb.predict_proba(scb.transform(F['BTC'][OWN].reindex(te.ts.unique()).fillna(0)))[:,1],index=te.ts.unique()); te['btcdir']=te.ts.map(pb)-0.5
    scores={'model':te.pred,'rev_1h':-te.r_1h,'rev_4h':-te.r_4h,'rev_24h':-te.r_24h,'mom_7d':te.r_7d,'beta_x_btcdir':te.beta*te.btcdir}
    for k,sv in scores.items():
        te['s']=sv.values
        for ts,g in te.groupby('ts'):
            if len(g)<4: continue
            ic=spearmanr(g.s,g.y_rel).correlation; ICs[k].append(ic)
            k_=max(1,len(g)//3); gs=g.sort_values('s'); PNL[k].append(gs.y_rel.iloc[-k_:].mean()-gs.y_rel.iloc[:k_].mean())
            if k=='model': WKS.append(int((ts-CS.index.min()).days//7))
out={}
for k in ICs:
    ic=np.array(ICs[k]); pnl=np.array(PNL[k]); wk=np.array(WKS)[:len(ic)]
    out[k]={'n_anchors':int(len(ic)),'mean_IC':round(float(np.nanmean(ic)),4),'IC_ci':[round(float(x),4) for x in boot(lambda ii: np.nanmean(ic[ii]),wk)],'IC_t':round(float(np.nanmean(ic)/np.nanstd(ic)*np.sqrt(len(ic))),2),
            'ls_gross_bp':round(float(pnl.mean()*1e4),2),'ls_ci':[round(float(x),2) for x in boot(lambda ii: pnl[ii].mean()*1e4,wk)],'ls_sd_bp':round(float(pnl.std()*1e4),1)}
    print('XSEC',k,out[k],flush=True)
res['xsec']=out; res['assets']=assets; res['years']=test_years
json.dump(res,open(os.path.join(os.path.dirname(__file__),'results',f'e3v2_relative_{tag}.json'),'w'),indent=1)
