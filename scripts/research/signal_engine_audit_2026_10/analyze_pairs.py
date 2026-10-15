"""Real vs pseudo (half-rotation) structural first touches: resolution (#357), outcome shares, time to resolution (#365),
volatility transition (#368), specificity of END_POSITION_X / OVMM slopes (#361/#363), tradeable expressions on both arms, and
conditioning diagnostics.  Paired statistics, week-block bootstrap (real touch week).  Periods: 2020-24 (discovery surface of the
Level Engine) and 2025-01..2026-07 (exposed by the race held-out read and the product history sync; NOT independent)."""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.dirname(__file__))
from levels import load_btc
P=pd.read_pickle('results/pairs.pkl'); k=load_btc(); out={}
rng=np.random.default_rng(1)
P['wk']=((P.ts_r-P.ts_r.min()).dt.days//7).values; P['period']=np.where(P.year_r<=2024,'2020-24','2025-26')
RES=['BREAK_FIRST','REJECT_FIRST']
def bootm(x,wk,B=500):
    uw=np.unique(wk); idx={u:np.where(wk==u)[0] for u in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(np.nanmean(x[ii]))
    return [float(v) for v in np.percentile(o,[2.5,97.5])]
def paired(col_r,col_p,m=None,scale=1.0,nd=4):
    m=np.ones(len(P),bool) if m is None else m; d=(P.loc[m,col_r].values.astype(float)-P.loc[m,col_p].values.astype(float))*scale
    return {'n':int(m.sum()),'real':round(float(np.nanmean(P.loc[m,col_r].values.astype(float))*scale),nd),'pseudo':round(float(np.nanmean(P.loc[m,col_p].values.astype(float))*scale),nd),'delta':round(float(np.nanmean(d)),nd),'ci':[round(v,nd) for v in bootm(d,P.wk.values[m])]}
for a in 'rp':
    P['res_'+a]=P['label_'+a].isin(RES).astype(float); P['brk_'+a]=(P['label_'+a]=='BREAK_FIRST').astype(float); P['nei_'+a]=(P['label_'+a]=='NEITHER').astype(float)
    P['anyres_'+a]=P['label_'+a].isin(RES+['AMBIGUOUS']).astype(float); P['tcl_'+a]=np.where(P['anyres_'+a]==1,P['t_res_'+a].fillna(48),48)*5.0
    for c in (3,6,12,24,48): P[f'by{c}_'+a]=((P['anyres_'+a]==1)&(P['t_res_'+a]<=c)).astype(float)
    P['abs4h_'+a]=P['ret_T0_toward_break_'+a].abs()/P['X_'+a]
    # range of bars j+1..j+48 in X units
    hi=k.high.values; lo=k.low.values; cl=k.close.values; r5=np.diff(np.log(cl),prepend=np.nan)
    P['rng48_'+a]=[np.log(hi[j+1:j+49].max()/lo[j+1:j+49].min())/x for j,x in zip(P['j_'+a].values,P['X_'+a].values)]
    P['rvpre_'+a]=[np.sqrt(np.mean(r5[j-12:j]**2)) for j in P['j_'+a].values]
    P['rvpost_'+a]=[np.sqrt(np.mean(r5[j+1:j+13]**2)) for j in P['j_'+a].values]
    # bars since period open and approach run from period open (in X units, oriented toward the level)
    ts=P['ts_'+a]; fam=P['family_'+a]
    ps=np.where(fam=='DAY',ts.dt.floor('D'),np.where(fam=='WEEK',(ts-pd.to_timedelta(ts.dt.weekday,unit='D')).dt.floor('D'),ts.dt.to_period('M').dt.start_time.dt.tz_localize('UTC')))
    ps=pd.to_datetime(pd.Series(ps,index=P.index),utc=True); P['bars_since_open_'+a]=((ts-ps)/pd.Timedelta('5min')).astype(int)
    op=k.open.values; po=op[P['j_'+a].values-P['bars_since_open_'+a].values]; P['approach_run_'+a]=np.log(cl[P['j_'+a].values]/po)/P['X_'+a].values*P['side_'+a].values  # + = price moved from the period open toward the level (in X units)
    P['hour_'+a]=ts.dt.hour
# approach run: for side +1 (approach from below, level above), the move from period open to touch is log(c_j/open) > 0 if price came up to it; sign convention so that + = moved toward the level
print('pairs',len(P),P.period.value_counts().to_dict())
# ---- A/B resolution and shares
sec={}
for per in ['all','2020-24','2025-26']:
    m=np.ones(len(P),bool) if per=='all' else (P.period==per).values
    sec[per]={'resolved(BREAK|REJECT)':paired('res_r','res_p',m,100,2),'BREAK':paired('brk_r','brk_p',m,100,2),'NEITHER':paired('nei_r','nei_p',m,100,2),
              'any_res_incl_ambig':paired('anyres_r','anyres_p',m,100,2)}
sec['by_family']={f:paired('res_r','res_p',(P.family_r==f).values,100,2) for f in ['DAY','WEEK','MONTH']}
sec['by_year']={int(y):paired('res_r','res_p',(P.year_r==y).values,100,2) for y in sorted(P.year_r.unique())}
sec['by_struct_side']={s:paired('res_r','res_p',(P.lvl_kind_r.str.endswith(s)).values,100,2) for s in ['H','L']}
out['A_resolution_pp']=sec; print(json.dumps(sec,indent=0)[:3000])
# ---- C time to resolution (#365)
tt={}
for per in ['all','2020-24','2025-26']:
    m=np.ones(len(P),bool) if per=='all' else (P.period==per).values
    tt[per]={'restricted_mean_unresolved_min':paired('tcl_r','tcl_p',m,1,2),**{f'resolved_by_{c*5}min':paired(f'by{c}_r',f'by{c}_p',m,100,2) for c in (3,6,12,24,48)}}
out['C_time_to_resolution']=tt; print(json.dumps(tt['all'],indent=0))
# ---- D/E volatility transition (#368) and expansion
ve={}
for per in ['all','2020-24','2025-26']:
    m=np.ones(len(P),bool) if per=='all' else (P.period==per).values
    ve[per]={'rv_transition_log':paired('rv_trans_r','rv_trans_p',m,1,4),'rv_pre_x1e4':paired('rvpre_r','rvpre_p',m,1e4,3),'rv_post_x1e4':paired('rvpost_r','rvpost_p',m,1e4,3),
             'abs_4h_move_in_X':paired('abs4h_r','abs4h_p',m,1,3),'range48_in_X':paired('rng48_r','rng48_p',m,1,3),'sigma_x1e4':paired('sig_r','sig_p',m,1e4,3)}
out['D_volatility']=ve; print(json.dumps(ve['all'],indent=0))
# ---- H conditioning: touch timing, approach run, hour
cond={}
for a in 'rp':
    cond['bars_since_period_open_'+a]={'median':float(P['bars_since_open_'+a].median()),'mean':round(float(P['bars_since_open_'+a].mean()),1),'share_first_bar':round(float((P['bars_since_open_'+a]==0).mean()),3),'share_within_1h':round(float((P['bars_since_open_'+a]<=12).mean()),3)}
    cond['approach_run_in_X_'+a]={'mean':round(float(P['approach_run_'+a].mean()),3),'median':round(float(P['approach_run_'+a].median()),3)}
# resolution by bars-since-open bins, each arm separately (not paired)
bins=[-1,0,12,48,144,100000]; lab=['open bar','1-12','13-48','49-144','>144']
for a in 'rp':
    g=P.groupby(pd.cut(P['bars_since_open_'+a],bins,labels=lab))['res_'+a].agg(['mean','size']); cond['res_by_bars_since_open_'+a]={str(i):[round(float(r['mean']),3),int(r['size'])] for i,r in g.iterrows()}
# resolution by approach-run bins
abins=[-100,-0.5,0.5,2,100]; alab=['<-0.5X (opened beyond/through)','-0.5..0.5X','0.5..2X','>2X']
for a in 'rp':
    g=P.groupby(pd.cut(P['approach_run_'+a],abins,labels=alab))['res_'+a].agg(['mean','size']); cond['res_by_approach_run_'+a]={str(i):[round(float(r['mean']),3),int(r['size'])] for i,r in g.iterrows()}
# touch on the first bar of the period (price opens inside the zone) vs later
for a in 'rp':
    m=P['bars_since_open_'+a]==0; cond['res_open_bar_vs_later_'+a]={'open_bar':[round(float(P.loc[m,'res_'+a].mean()),3),int(m.sum())],'later':[round(float(P.loc[~m,'res_'+a].mean()),3),int((~m).sum())]}
# matched-timing comparison: restrict to pairs where both touched after the first hour
m=(P.bars_since_open_r>12)&(P.bars_since_open_p>12); cond['paired_res_both_after_1h']=paired('res_r','res_p',m.values,100,2)
m=(P.bars_since_open_r==0)&(P.bars_since_open_p==0); cond['paired_res_both_open_bar']=paired('res_r','res_p',m.values,100,2)
# pair selection: the matched cohort keeps a touch only if the twin level was ALSO touched in the same period (a path condition unknown at T0)
R=pd.read_pickle('results/events_real.pkl'); Z=pd.read_pickle('results/events_pseudo.pkl')
for nm,E,key in [('real',R,R.event_id.isin(P.event_id_r)),('pseudo',Z,Z.shadow_id.isin(P.event_id_r))]:
    cond['pair_selection_'+nm]={'n_all':int(len(E)),'n_in_pairs':int(key.sum()),'res_all':round(float(E.label.isin(RES).mean()),3),'res_in_pairs':round(float(E[key].label.isin(RES).mean()),3),'res_not_in_pairs':round(float(E[~key].label.isin(RES).mean()),3),
        'T0_toward_break_bp_all':round(float(E.ret_T0_toward_break.mean()*1e4),1),'T0_toward_break_bp_in_pairs':round(float(E[key].ret_T0_toward_break.mean()*1e4),1),'T0_toward_break_bp_not_in_pairs':round(float(E[~key].ret_T0_toward_break.mean()*1e4),1)}
# unpaired contrast on all eligible touches (week-block bootstrap on each arm, difference of means)
def unp(col,scale,nd):
    xr=R[col].values*scale; xp=Z[col].values*scale; wr=((R.ts-R.ts.min()).dt.days//7).values; wp=((Z.ts-Z.ts.min()).dt.days//7).values
    o=[]
    for _ in range(500):
        ur=np.unique(wr); ir=np.concatenate([np.where(wr==u)[0] for u in rng.choice(ur,len(ur),replace=True)]); up=np.unique(wp); ip=np.concatenate([np.where(wp==u)[0] for u in rng.choice(up,len(up),replace=True)]); o.append(np.nanmean(xr[ir])-np.nanmean(xp[ip]))
    return {'n_real':int(len(xr)),'n_pseudo':int(len(xp)),'real':round(float(np.nanmean(xr)),nd),'pseudo':round(float(np.nanmean(xp)),nd),'delta':round(float(np.nanmean(xr)-np.nanmean(xp)),nd),'ci':[round(float(v),nd) for v in np.percentile(o,[2.5,97.5])]}
for E in (R,Z): E['res']=E.label.isin(RES).astype(float); E['nei']=(E.label=='NEITHER').astype(float); E['brk']=(E.label=='BREAK_FIRST').astype(float)
cond['unpaired_all_eligible']={'resolved_pp':unp('res',100,2),'NEITHER_pp':unp('nei',100,2),'BREAK_pp':unp('brk',100,2),'rv_transition_log':unp('rv_trans',1,4),'T0_toward_break_bp':unp('ret_T0_toward_break',1e4,2),'bracket_ret_bp':unp('bracket_ret',1e4,2)}
# touch order inside pairs
m=(P.j_r<P.j_p).values; cond['touch_order']={'real_first_share':round(float(m.mean()),3),'same_bar_share':round(float((P.j_r==P.j_p).mean()),3),'res_real_when_real_first':round(float(P[m].res_r.mean()),3),'res_real_when_pseudo_first':round(float(P[~m].res_r.mean()),3),'res_pseudo_when_pseudo_first':round(float(P[~m].res_p.mean()),3),'res_pseudo_when_real_first':round(float(P[m].res_p.mean()),3)}
out['H_conditioning']=cond; print(json.dumps(cond,indent=0))
# ---- F specificity: slopes of END_POSITION_X and OVMM on BREAK among unresolved-at-T15 & later resolved, each arm
def arm(a):
    U=P[(~P['resolved_by_15_'+a].astype(bool))&(P['label_'+a].isin(RES))]; return U
spec={}
sdx=P.loc[~P.resolved_by_15_r.astype(bool),'end_x_r'].std(); sdo=P.loc[~P.resolved_by_15_r.astype(bool),'ovmm_r'].std()
for feat,sd in [('end_x',sdx),('ovmm',sdo),('bin_mv',None)]:
    res={}
    for a,nm in [('r','real'),('p','pseudo')]:
        U=arm(a).dropna(subset=[feat+'_'+a]); x=U[feat+'_'+a].values/(sd if sd else U[feat+'_'+a].std()); y=U['brk_'+a].values
        X=np.column_stack([x,(U['family_'+a]!='DAY').astype(float),(U['side_'+a]<0).astype(float)]); b=LinearRegression().fit(X,y).coef_[0]
        # bootstrap slope by week
        uw=np.unique(U.wk.values); idx={u:np.where(U.wk.values==u)[0] for u in uw}; o=[]
        for _ in range(300):
            ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(LinearRegression().fit(X[ii],y[ii]).coef_[0])
        res[nm]={'n':int(len(U)),'slope_pp_per_sd':round(float(b*100),2),'ci':[round(float(v*100),2) for v in np.percentile(o,[2.5,97.5])],'auc':round(float(roc_auc_score(y,x)),3)}
    spec[feat]=res
# paired slope delta (stacked rows with real dummy interaction), pairs where both arms unresolved at T15 and later resolved
m=(~P.resolved_by_15_r.astype(bool))&(~P.resolved_by_15_p.astype(bool))&P.label_r.isin(RES)&P.label_p.isin(RES)
S=P[m]
for feat,sd in [('end_x',sdx),('ovmm',sdo)]:
    S2=S.dropna(subset=[feat+'_r',feat+'_p']); xr=S2[feat+'_r'].values/sd; xp=S2[feat+'_p'].values/sd
    def fit(ii):
        x=np.concatenate([xr[ii],xp[ii]]); real=np.concatenate([np.ones(len(ii)),np.zeros(len(ii))]); y=np.concatenate([S2.brk_r.values[ii],S2.brk_p.values[ii]])
        X=np.column_stack([x,real,x*real]); c=LinearRegression().fit(X,y).coef_; return c[0],c[0]+c[2],c[2]
    ii=np.arange(len(S2)); bp,br,d=fit(ii); uw=np.unique(S2.wk.values); idx={u:np.where(S2.wk.values==u)[0] for u in uw}; o=[]
    for _ in range(300):
        jj=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(fit(jj)[2])
    spec[feat+'_stacked']={'n_pairs':int(len(S2)),'beta_pseudo_pp':round(float(bp*100),2),'beta_real_pp':round(float(br*100),2),'delta_pp':round(float(d*100),2),'delta_ci':[round(float(v*100),2) for v in np.percentile(o,[2.5,97.5])]}
out['F_specificity']=spec; print(json.dumps(spec,indent=0))
# ---- G economics on both arms
econ={}
for a,nm in [('r','real'),('p','pseudo')]:
    m=P['label_'+a].isin(RES).values; e={}
    for col in ['bracket_ret','bracket_ret_closefill']:
        x=P.loc[m,col+'_'+a].values*1e4; e[col]={'n':int(m.sum()),'gross_bp':round(float(x.mean()),2),'ci':[round(v,2) for v in bootm(x,P.wk.values[m])],'hit':round(float((x>0).mean()),3)}
    x=P['ret_T0_toward_break_'+a].values*1e4; e['T0_toward_break_hold4h']={'gross_bp':round(float(x.mean()),2),'ci':[round(v,2) for v in bootm(x,P.wk.values)]}
    # fade: toward REJECT from T0 to first barrier or close (symmetric to bracket but one-directional): enter at T0 against the approach
    econ[nm]=e
# T15 model-directed: fit on real rows (years<ty), apply to both arms' unresolved rows of year ty
def t15_ret(U,a,p,theta):
    s=np.where(p>0.5+theta,1,np.where(p<0.5-theta,-1,0)); lab=U['label_'+a].values; z=U['z15_'+a].values; w=U['w_'+a].values; rT=U['ret_T15_toward_break_'+a].values
    mv=np.where(lab=='BREAK_FIRST',w-z,np.where(lab=='REJECT_FIRST',-z,rT)); return s*mv,s
for a,nm in [('r','real'),('p','pseudo')]:
    U=P[(~P['resolved_by_15_'+a].astype(bool))&P['b0_break_'+a].notna()].copy(); U['lb0']=np.log(U['b0_break_'+a]/(U['b0_reject_'+a]+1e-9)); U['ex']=U['end_x_'+a]; U['yb']=U['brk_'+a]; U['res']=U['res_'+a]
    Rr=P[(~P.resolved_by_15_r.astype(bool))&P.b0_break_r.notna()&P.label_r.isin(RES)].copy(); Rr['lb0']=np.log(Rr.b0_break_r/(Rr.b0_reject_r+1e-9)); Rr['ex']=Rr.end_x_r
    PP=[];IDX=[]
    for ty in [2021,2022,2023,2024,2025,2026]:
        tr=Rr[Rr.year_r<ty]; te=U[U['year_'+a]==ty]
        if len(tr)<100 or len(te)<30: continue
        cols=['lb0','ex']; mu=tr[cols].mean(); sd=tr[cols].std()+1e-9; mdl=LogisticRegression(C=1.0,max_iter=2000).fit(((tr[cols]-mu)/sd).values,tr.brk_r.values)
        PP.append(mdl.predict_proba(((te[cols]-mu)/sd).values)[:,1]); IDX.append(te.index.values)
    PP=np.concatenate(PP); Ut=U.loc[np.concatenate(IDX)]
    e=econ[nm]; e['T15_model_auc_break_vs_reject']=round(float(roc_auc_score(Ut.loc[Ut.res==1,'yb'],PP[Ut.res.values==1])),3)
    for theta in [0.0,0.15]:
        r,s=t15_ret(Ut,a,PP,theta); mm=s!=0; x=r[mm]*1e4
        e[f'T15_directed_theta{theta}']={'n':int(mm.sum()),'gross_bp':round(float(x.mean()),2),'ci':[round(v,2) for v in bootm(x,Ut.wk.values[mm])],'hit':round(float((x>0).mean()),3),'by_period':{p:round(float(x[Ut.period.values[mm]==p].mean()),2) for p in ['2020-24','2025-26']}}
out['G_economics']=econ; print(json.dumps(econ,indent=0))
json.dump(out,open('results/analyze_pairs.json','w'),indent=1,default=str); P.to_pickle('results/pairs_enriched.pkl')
