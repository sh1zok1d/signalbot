"""T15 incrementality (#363 question) and B0 calibration on the EXPOSED 2025-01..2026-07 surface: models fitted on real touches
2020-2024 (the Level Engine discovery surface), scored once on 2025-26.  Not an independent confirmation: this surface was read by the
level race held-out one-shot and by the product history sync."""
import os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
E=pd.read_pickle('results/events_real.pkl'); rng=np.random.default_rng(2); out={}
E['wk']=((E.ts-E.ts.min()).dt.days//7).values
U=E[(~E.resolved_by_15)&E.b0_break.notna()].copy(); U['y_b']=(U.label=='BREAK_FIRST').astype(int); U['y_res']=U.label.isin(['BREAK_FIRST','REJECT_FIRST']).astype(int); U['lb0']=np.log(U.b0_break/(U.b0_reject+1e-9))
R=U[U.y_res==1]; tr=R[R.year<=2024]; te=R[R.year>=2025]
print('OVMM available in 2025-26:',int(te.ovmm.notna().sum()),'(pinned cross-venue files end 2024-12; OVMM sets cannot be scored on 2025-26)')
print('train',len(tr),'test 2025-26',len(te),'base rate test',round(float(te.y_b.mean()),3))
sets={'B0':['lb0'],'B0+end_x':['lb0','end_x'],'B0+end_x+bin_mv':['lb0','end_x','bin_mv'],'end_x only':['end_x']}
res={}; preds={}
for nm,cols in sets.items():
    mu=tr[cols].mean(); sd=tr[cols].std()+1e-9; m=LogisticRegression(C=1.0,max_iter=2000).fit(((tr[cols]-mu)/sd).values,tr.y_b.values); p=m.predict_proba(((te[cols]-mu)/sd).values)[:,1]; preds[nm]=p
    res[nm]={'auc':round(float(roc_auc_score(te.y_b,p)),4),'logloss':round(float(log_loss(te.y_b,np.clip(p,1e-3,1-1e-3))),4),'coef_z':dict(zip(cols,[round(float(c),3) for c in m.coef_[0]]))}
# paired AUC difference bootstrap for OVMM increment
uw=np.unique(te.wk.values); idx={u:np.where(te.wk.values==u)[0] for u in uw}; o=[]; y=te.y_b.values
for _ in range(500):
    ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(roc_auc_score(y[ii],preds['B0+end_x'][ii])-roc_auc_score(y[ii],preds['B0'][ii]))
res['delta_auc_end_x_over_B0']={'delta':round(float(res['B0+end_x']['auc']-res['B0']['auc']),4),'ci':[round(float(v),4) for v in np.percentile(o,[2.5,97.5])]}
out['T15_break_vs_reject_2025_26']=res; print(json.dumps(res,indent=0))
# B0 calibration 2025-26 among unresolved at T15 (3-class) and resolution rate
t=U[U.year>=2025]; out['B0_calibration_2025_26']={'n':int(len(t)),'b0_break':round(float(t.b0_break.mean()),3),'real_break':round(float(t.y_b.mean()),3),'b0_neither':round(float(t.b0_neither.mean()),3),'real_neither':round(float((t.label=='NEITHER').mean()),3)}
t0=U[U.year<=2024]; out['B0_calibration_2020_24']={'n':int(len(t0)),'b0_break':round(float(t0.b0_break.mean()),3),'real_break':round(float(t0.y_b.mean()),3),'b0_neither':round(float(t0.b0_neither.mean()),3),'real_neither':round(float((t0.label=='NEITHER').mean()),3)}
print(out['B0_calibration_2020_24'],out['B0_calibration_2025_26'])
json.dump(out,open('results/exposed_2025.json','w'),indent=1)
