import pandas as pd, numpy as np, os, json, warnings
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss
from features import FEATS
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
f = pd.read_pickle(os.path.join(D,'feat5m.pkl'))
for c in FEATS: f[c] = f[c].clip(f[c].quantile(0.001), f[c].quantile(0.999))
STRIDE = {'1h':12,'4h':48,'24h':48}   # anchors; 24h uses 4h stride (overlapping targets; CIs by week block)
rng = np.random.default_rng(0)
def block_boot(stat, weeks, B=400):
    uw = np.unique(weeks); idx = {w:np.where(weeks==w)[0] for w in uw}
    out=[]
    for _ in range(B):
        samp = rng.choice(uw, len(uw), replace=True)
        ii = np.concatenate([idx[w] for w in samp]); out.append(stat(ii))
    return np.percentile(out,[2.5,97.5])
res = {}
TEST_YEARS = [2022,2023,2024,2025,2026]
for h in ['1h','4h','24h']:
    s = STRIDE[h]
    sub = f.iloc[::s].dropna(subset=FEATS+['y_up_'+h,'y_r_'+h,'y_lrv_'+h,'y_lrange_'+h]).copy()
    print(f'\n===== horizon {h}: anchors {len(sub)} =====')
    res[h] = {}
    for ty in TEST_YEARS:
        tr = sub[sub.year < ty]; te = sub[sub.year == ty]
        if len(te) < 200: continue
        sc = StandardScaler().fit(tr[FEATS]); Xtr = sc.transform(tr[FEATS]); Xte = sc.transform(te[FEATS])
        ytr = tr['y_up_'+h].values; yte = te['y_up_'+h].values
        out = {'n_train':len(tr),'n_test':len(te),'base_rate':float(yte.mean())}
        # direction models
        lr = LogisticRegression(C=0.1, max_iter=2000).fit(Xtr,ytr)
        gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.03, max_depth=3, min_samples_leaf=300, l2_regularization=1.0, random_state=0).fit(tr[FEATS],ytr)
        pb = float(ytr.mean())
        ll0 = log_loss(yte, np.full(len(yte), pb))
        for name,p in [('logit',lr.predict_proba(Xte)[:,1]),('gbm',gb.predict_proba(te[FEATS])[:,1])]:
            auc = roc_auc_score(yte,p); ll = log_loss(yte,p)
            wk = te['week'].values
            ci = block_boot(lambda ii: roc_auc_score(yte[ii],p[ii]) if len(np.unique(yte[ii]))>1 else 0.5, wk)
            acc = float(((p>0.5)==(yte>0.5)).mean())
            # economic value (4h & 1h): trade sign when |p-.5|>theta, cost round trip
            econ = {}
            r = te['y_r_'+h].values
            for theta in [0.0,0.03,0.05,0.08]:
                m = np.abs(p-0.5)>theta
                if m.sum()<20: econ[theta]={'n':int(m.sum())}; continue
                side = np.sign(p[m]-0.5); gross = side*r[m]
                per = {'n':int(m.sum()),'hit':float((gross>0).mean()),'gross_bp':float(gross.mean()*1e4)}
                for cost in [0.0,4.0,10.0]:
                    net = gross - cost/1e4
                    per[f'net_bp_c{int(cost)}'] = float(net.mean()*1e4)
                    per[f'sharpe_c{int(cost)}'] = float(net.mean()/ (net.std()+1e-12) * np.sqrt( (365*24)/{'1h':1,'4h':4,'24h':24}[h] * m.mean()))
                econ[theta]=per
            out[name] = {'auc':float(auc),'auc_ci':[float(ci[0]),float(ci[1])],'logloss':float(ll),'logloss_base':float(ll0),'ll_skill':float(1-ll/ll0),'acc':acc,'econ':econ}
            print(f'{ty} {name:5s} AUC {auc:.3f} [{ci[0]:.3f},{ci[1]:.3f}] LLskill {1-ll/ll0:+.4f} acc {acc:.3f} base {pb:.3f} | econ θ=.05: {econ[0.05]}')
        # volatility models: targets log fwd RV and log fwd range; baselines: persistence (same-window past) and train mean
        for tgt, persist in [('y_lrv_'+h, 'lrv_'+h), ('y_lrange_'+h, 'lrange_'+h if 'lrange_'+h in f.columns else 'lrv_'+h)]:
            yv = tr[tgt].values; yvt = te[tgt].values
            rr = Ridge(alpha=1.0).fit(Xtr, yv); pr = rr.predict(Xte)
            gr = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.03, max_depth=3, min_samples_leaf=300, random_state=0).fit(tr[FEATS], yv); pg = gr.predict(te[FEATS])
            def r2(pred, ref): return float(1 - np.sum((yvt-pred)**2)/np.sum((yvt-ref)**2))
            persist_pred = te[persist].values
            # persistence with train-fitted bias/scale
            a,b = np.polyfit(tr[persist].values, yv, 1); pp = a*persist_pred+b
            o = {'r2_ridge_vs_mean':r2(pr, yv.mean()), 'r2_gbm_vs_mean':r2(pg, yv.mean()), 'r2_persist_vs_mean':r2(pp, yv.mean()), 'r2_ridge_vs_persist':r2(pr, pp), 'r2_gbm_vs_persist': r2(pg, pp)}
            out[tgt]=o
            print(f'{ty} VOL {tgt:12s} R2 ridge {o["r2_ridge_vs_mean"]:.3f} gbm {o["r2_gbm_vs_mean"]:.3f} persist {o["r2_persist_vs_mean"]:.3f} | ridge vs persist {o["r2_ridge_vs_persist"]:+.3f}')
        res[h][ty]=out
json.dump(res, open(os.path.join(os.path.dirname(__file__),'direction_results.json'),'w'), indent=1, default=float)
