"""E9: audit checks for the revision.  (a) explicit-loop verification that cross-asset features at an anchor use only bars
<= t and targets only bars t+1..t+w; (b) year-by-year rank IC of the fixed cross-sectional rules 2021-2026 (no fitting);
(c) share of forward-filled (missing) bars inside 4h target windows per asset; (d) the beta leak size: corr(beta_t, beta_{t+48})."""
import os, sys, pickle, json, numpy as np, pandas as pd
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(__file__)); from panel import DATA_DIR, own_features
D=pickle.load(open(os.path.join(DATA_DIR,'xm_panel12.pkl'),'rb')); P=D['P']; F=D['F']; assets=D['assets']
out={}
# (a) explicit checks on 500 random anchors for SOL own features and BTC cross features
rng=np.random.default_rng(7); k=P['SOL']; b=P['BTC']; f=F['SOL']; fb=F['BTC']; lc=np.log(k.close.values); lb=np.log(b.close.values)
idx=rng.integers(3000,len(k)-300,size=500); bad=0
for i in idx:
    if not np.isfinite(f.r_4h.iloc[i]): continue
    assert abs(f.r_4h.iloc[i]-(lc[i]-lc[i-48]))<1e-12; assert abs(fb.r_1h.iloc[i]-(lb[i]-lb[i-12]))<1e-12
    assert abs(f.y_r_4h.iloc[i]-(lc[i+48]-lc[i]))<1e-12; assert abs(fb.r_24h.iloc[i]-(lb[i]-lb[i-288]))<1e-12
out['a_alignment']='OK on 500 anchors (own r_4h, BTC r_1h/r_24h backward; y_r_4h forward t+1..t+48)'
# (c) missing bars inside forward windows
miss={}
for a in assets:
    pres=P[a]['present'].values; fw=pd.Series(pres,index=P[a].index)[::-1].rolling(48,min_periods=48).mean()[::-1].shift(-1)
    sub=fw.iloc[::48]; sub=sub[(sub.index.year>=2022)]; miss[a]=round(float((sub<1).mean()),4)
out['c_share_of_4h_windows_with_any_missing_bar_2022plus']=miss
# (d) beta autocorrelation at 48 bars
bl={}
for a in [x for x in assets if x!='BTC']:
    la=np.log(P[a].close); lbs=np.log(P['BTC'].close); h1=pd.DataFrame({'a':la.diff(12).iloc[::12],'b':lbs.diff(12).iloc[::12]}).dropna()
    beta=(h1.a.rolling(720).cov(h1.b)/h1.b.rolling(720).var()).dropna(); bl[a]=round(float(np.corrcoef(beta.values[:-4],beta.values[4:])[0,1]),5)
out['d_corr_beta_t_vs_beta_t_plus_4h']=bl
# (b) rank IC by year for fixed rules
rows=[]
for a in assets:
    g=F[a][['r_1h','r_4h','r_24h','r_7d','y_r_4h']].copy(); g['asset']=a; g['present']=P[a]['present']; rows.append(g.iloc[::48])
CS=pd.concat(rows); CS=CS[CS.present==1].dropna(); CS['ts']=CS.index; CS['y_rel']=CS.y_r_4h-CS.groupby('ts').y_r_4h.transform('mean')
ic={}
for rule,col,sgn in [('rev_4h','r_4h',-1),('rev_1h','r_1h',-1),('rev_24h','r_24h',-1),('mom_7d','r_7d',1)]:
    byy={}
    for y in range(2020,2027):
        d=CS[CS.index.year==y]; vals=[]
        for ts,g in d.groupby('ts'):
            if len(g)>=6: vals.append(spearmanr(sgn*g[col],g.y_rel).correlation)
        if len(vals)>100: vals=np.array(vals); byy[y]={'IC':round(float(np.nanmean(vals)),4),'t':round(float(np.nanmean(vals)/np.nanstd(vals)*np.sqrt(len(vals))),1),'n':int(len(vals))}
    ic[rule]=byy
out['b_rank_IC_by_year']=ic
print(json.dumps(out,indent=1)); json.dump(out,open(os.path.join(os.path.dirname(__file__),'results','e9_audit_checks.json'),'w'),indent=1)
