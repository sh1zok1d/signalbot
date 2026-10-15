"""Economics and incrementality on the real structural first touches (product constructor).  Pseudo twins are handled in analyze_pairs.py."""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
E=pd.read_pickle(os.path.join(os.path.dirname(__file__),'results','events_real.pkl')); out={}
rng=np.random.default_rng(0)
def boot(x,wk,B=400):
    uw=np.unique(wk); idx={u:np.where(wk==u)[0] for u in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(x[ii].mean())
    return [round(float(v),2) for v in np.percentile(o,[2.5,97.5])]
E['wk']=((E.ts-E.ts.min()).dt.days//7).values
print('== outcome split by year ==')
print(E.groupby('year').label.value_counts(normalize=True).unstack().round(3))
print('== by family ==');print(E.groupby('family').label.value_counts(normalize=True).unstack().round(3))
out['split_by_year']=E.groupby('year').label.value_counts(normalize=True).unstack().round(3).to_dict()
# ---- T0 economics (entry at close of touch bar j)
res={}
for nm,col in [('T0 always toward BREAK (hold 48 bars)','ret_T0_toward_break')]:
    x=E[col].values*1e4; res[nm]={'n':int(len(x)),'gross_bp':round(float(x.mean()),2),'ci':boot(x,E.wk.values),'hit':round(float((x>0).mean()),3),'sd':round(float(x.std()),1),'by_year':{int(y):round(float(x[E.year.values==y].mean()),2) for y in sorted(E.year.unique())}}
# bracket: stop at first barrier (fill at barrier), exit at opposite barrier or close j+48; unresolved -> no trade
m=E.label.isin(['BREAK_FIRST','REJECT_FIRST']).values
for nm,col in [('T0 bracket, fill at barrier','bracket_ret'),('T0 bracket, fill at close of hit bar','bracket_ret_closefill')]:
    x=E.loc[m,col].values*1e4; res[nm]={'n_trades':int(m.sum()),'gross_bp':round(float(x.mean()),2),'ci':boot(x,E.wk.values[m]),'hit':round(float((x>0).mean()),3),'sd':round(float(x.std()),1),
        'break_leg_bp':round(float(E.loc[m&E.bracket_is_break.fillna(False).values.astype(bool),col].mean()*1e4),2),'reject_leg_bp':round(float(E.loc[m&~E.bracket_is_break.fillna(False).values.astype(bool),col].mean()*1e4),2),
        'by_year':{int(y):round(float(x[E.year.values[m]==y].mean()),2) for y in sorted(E.year.unique())}}
out['T0_economics']=res; print(json.dumps(res,indent=1))
# ---- T15: among events unresolved at T15 with B0 available; outcome BREAK vs REJECT among later-resolved (#363 support) and 3-class
U=E[(~E.resolved_by_15)&E.b0_break.notna()].copy(); U['y_res']=U.label.isin(['BREAK_FIRST','REJECT_FIRST']).astype(int); U['y_b']=(U.label=='BREAK_FIRST').astype(int)
print('unresolved at T15 with B0:',len(U),'resolved later share',U.y_res.mean().round(3),'break share among resolved',U[U.y_res==1].y_b.mean().round(3))
# B0 calibration: predicted vs realized among all unresolved (3 class)
cal={'b0_mean_break':round(float(U.b0_break.mean()),3),'real_break':round(float(U.y_b.mean()),3),'b0_mean_reject':round(float(U.b0_reject.mean()),3),'real_reject':round(float((U.label=='REJECT_FIRST').mean()),3),'b0_mean_neither':round(float(U.b0_neither.mean()),3),'real_neither':round(float((U.label=='NEITHER').mean()),3)}
out['B0_calibration_T15']=cal; print('B0 calibration',cal)
# ---- walk-forward logit: BREAK vs REJECT among later-resolved; years 2021-2024 (cross-venue available), train on earlier
R=U[U.y_res==1].copy(); R['lb0']=np.log(R.b0_break/(R.b0_reject+1e-9)); R=R.dropna(subset=['ovmm','ovmm_diff'])
sets={'B0':['lb0'],'B0+end_x':['lb0','end_x'],'B0+end_x+bin_mv':['lb0','end_x','bin_mv'],'B0+end_x+OVMM':['lb0','end_x','ovmm'],'B0+end_x+OVMM_diff':['lb0','end_x','ovmm_diff'],'end_x only':['end_x'],'OVMM only':['ovmm'],'OVMM_diff only':['ovmm_diff']}
wf={}
for name,cols in sets.items():
    P=[];Y=[];W=[]
    for ty in [2021,2022,2023,2024]:
        tr=R[(R.year<ty)]; te=R[R.year==ty]
        if len(tr)<100 or len(te)<50: continue
        mu=tr[cols].mean(); sd=tr[cols].std()+1e-9; m=LogisticRegression(C=1.0,max_iter=2000).fit(((tr[cols]-mu)/sd).values,tr.y_b.values)
        P.append(m.predict_proba(((te[cols]-mu)/sd).values)[:,1]); Y.append(te.y_b.values); W.append(te.wk.values)
    P=np.concatenate(P);Y=np.concatenate(Y);W=np.concatenate(W)
    auc=roc_auc_score(Y,P); ci=boot(np.zeros(1),np.zeros(1,dtype=int)) if False else None
    # bootstrap AUC by week
    uw=np.unique(W); idx={u:np.where(W==u)[0] for u in uw}; o=[]
    for _ in range(300):
        ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(roc_auc_score(Y[ii],P[ii]))
    wf[name]={'n':int(len(Y)),'auc':round(float(auc),4),'auc_ci':[round(float(v),4) for v in np.percentile(o,[2.5,97.5])],'logloss':round(float(log_loss(Y,np.clip(P,1e-3,1-1e-3))),4),'base_rate':round(float(Y.mean()),3)}
    # raw B0 as probability (no fit) for reference
    if name=='B0': wf['B0 raw (no fit)']={'auc':round(float(roc_auc_score(Y,np.concatenate([R[R.year==ty].lb0.values for ty in [2021,2022,2023,2024] if len(R[R.year==ty])>=50]))),4),'logloss':round(float(log_loss(Y,np.clip(np.concatenate([(R[R.year==ty].b0_break/(R[R.year==ty].b0_break+R[R.year==ty].b0_reject)).values for ty in [2021,2022,2023,2024] if len(R[R.year==ty])>=50]),1e-3,1-1e-3))),4)}
    print(name,wf[name])
out['T15_walkforward_break_vs_reject']=wf
print('corr(ovmm, bin_mv)=%.3f corr(ovmm_diff, bin_mv)=%.3f corr(end_x,bin_mv)=%.3f'%(R.ovmm.corr(R.bin_mv),R.ovmm_diff.corr(R.bin_mv),R.end_x.corr(R.bin_mv)))
# ---- T15 economics: direction by model P(BREAK|resolved) with B0+end_x+OVMM; enter at close j+2, exit at first barrier or close j+48; among ALL unresolved (NEITHER -> exit at close)
hi=None
def t15_pnl(Uall, p, theta):
    # trade toward BREAK if p>0.5+theta, toward REJECT if p<0.5-theta
    side=np.where(p>0.5+theta,1,np.where(p<0.5-theta,-1,0)); r=np.zeros(len(Uall))
    lab=Uall.label.values; X=Uall.X.values; z=Uall.z15.values; w=Uall.w.values; rT=Uall.ret_T15_toward_break.values
    for i in range(len(Uall)):
        if side[i]==0: continue
        if lab[i]=='BREAK_FIRST': move=(w[i]-z[i])           # from T15 to the BREAK barrier
        elif lab[i]=='REJECT_FIRST': move=-(z[i])            # down to the REJECT barrier
        else: move=rT[i]                                     # neither: hold to the end
        r[i]=side[i]*move
    return r, side
econ={}
cols=['lb0','end_x','ovmm']; Ua=U.dropna(subset=['ovmm']).copy(); Ua['lb0']=np.log(Ua.b0_break/(Ua.b0_reject+1e-9))
P=[];IDX=[]
for ty in [2021,2022,2023,2024]:
    tr=Ua[(Ua.year<ty)&(Ua.y_res==1)]; te=Ua[Ua.year==ty]
    if len(tr)<100 or len(te)<50: continue
    mu=tr[cols].mean(); sd=tr[cols].std()+1e-9; m=LogisticRegression(C=1.0,max_iter=2000).fit(((tr[cols]-mu)/sd).values,tr.y_b.values)
    P.append(m.predict_proba(((te[cols]-mu)/sd).values)[:,1]); IDX.append(te.index.values)
P=np.concatenate(P); Ut=Ua.loc[np.concatenate(IDX)]
for theta in [0.0,0.1,0.2]:
    r,side=t15_pnl(Ut,P,theta); m=side!=0; x=r[m]*1e4
    econ[f'theta={theta}']={'n_trades':int(m.sum()),'gross_bp':round(float(x.mean()),2),'ci':boot(x,Ut.wk.values[m]),'hit':round(float((x>0).mean()),3),'sd':round(float(x.std()),1),'net_c4':round(float(x.mean()-4),2),'net_c10':round(float(x.mean()-10),2),'by_year':{int(y):round(float(x[Ut.year.values[m]==y].mean()),2) for y in [2021,2022,2023,2024]}}
    print('T15 econ',theta,econ[f'theta={theta}'])
# baseline: direction by B0 alone and by end_x sign
for nm,p in [('B0 only',(Ut.b0_break/(Ut.b0_break+Ut.b0_reject)).values),('end_x sign',(Ut.end_x.values>0).astype(float)*0.4+0.3)]:
    r,side=t15_pnl(Ut,p,0.0); m=side!=0; x=r[m]*1e4; econ['baseline '+nm]={'n':int(m.sum()),'gross_bp':round(float(x.mean()),2),'ci':boot(x,Ut.wk.values[m]),'hit':round(float((x>0).mean()),3)}
    print('T15 baseline',nm,econ['baseline '+nm])
out['T15_economics']=econ
json.dump(out,open(os.path.join(os.path.dirname(__file__),'results','analyze_real.json'),'w'),indent=1,default=str)
