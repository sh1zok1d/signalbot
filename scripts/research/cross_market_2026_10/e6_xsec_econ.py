"""E6: economics of the cross-sectional short-term reversal (rank assets by past 1h/4h return, long the bottom k, short the top k)
and of the single-asset reversal applied per asset, at 4h anchors.  Equal-risk sizing (each leg scaled to a target 4h vol using
the asset's trailing 24h RV), costs per leg 0/1/2/4/8 bp round trip, concentration, drawdown, by year.  No model fitting: these
are fixed rules, so every year is out of sample; test years on the command line."""
import os, sys, pickle, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); from panel import DATA_DIR
D=pickle.load(open(os.path.join(DATA_DIR,os.environ.get('XM_PANEL','xm_panel12.pkl')),'rb')); P=D['P']; F=D['F']; assets=D['assets']
years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]; tag=sys.argv[2] if len(sys.argv)>2 else 'dev12'
w=48; rows=[]
for a in assets:
    f=F[a][['r_1h','r_4h','r_24h','lrv_24h','y_r_4h']].copy(); f['asset']=a; f['present']=P[a]['present']; f['ts']=f.index; rows.append(f.iloc[::w])
CS=pd.concat(rows); CS=CS[CS.present==1].dropna(); CS['year']=CS.index.year; CS=CS[CS.year.isin(years)]
CS['sig4h']=np.exp(CS.lrv_24h)*np.sqrt(48)   # ex-ante 4h vol
CS['mean_y']=CS.groupby('ts').y_r_4h.transform('mean'); CS['y_rel']=CS.y_r_4h-CS.mean_y
rng=np.random.default_rng(0)
def boot(x,wk,B=400):
    uw=np.unique(wk); idx={u:np.where(wk==u)[0] for u in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(x[ii].mean())
    return np.percentile(o,[2.5,97.5])
out={}
TARGET=0.01  # 1 % 4h vol target per leg (BTC-like)
for rule in ['rev_1h','rev_4h']:
    col={'rev_1h':'r_1h','rev_4h':'r_4h'}[rule]
    for kfrac in [1/3,1/4]:
        pnl=[]; pnl_eq=[]; turn=[]; wks=[]; ts_list=[]
        for ts,g in CS.groupby('ts'):
            n=len(g)
            if n<6: continue
            k=max(1,int(round(n*kfrac))); gs=g.sort_values(col)   # ascending past return: bottom = losers
            lo=gs.iloc[:k]; hi=gs.iloc[-k:]
            # equal-weight legs
            pnl.append(lo.y_r_4h.mean()-hi.y_r_4h.mean())
            # equal-risk: weight each asset by TARGET/sig4h, legs normalised to gross 1 each
            wl=(TARGET/lo.sig4h); wl=wl/wl.sum(); wh=(TARGET/hi.sig4h); wh=wh/wh.sum()
            pnl_eq.append(float((wl*lo.y_r_4h).sum()-(wh*hi.y_r_4h).sum()))
            wks.append(int((ts-CS.index.min()).days//7)); ts_list.append(ts)
        pnl=np.array(pnl); pnl_eq=np.array(pnl_eq); wk=np.array(wks); tsa=pd.DatetimeIndex(ts_list)
        # turnover: fraction of names changing between consecutive anchors ~ assume full rebalance each 4h (upper bound on cost): 2 legs each of gross 1 -> cost = 2 * c per anchor
        res={'n_anchors':int(len(pnl)),'gross_bp':round(float(pnl.mean()*1e4),2),'ci':[round(float(x*1e4),2) for x in boot(pnl,wk)],'sd_bp':round(float(pnl.std()*1e4),1),'hit':round(float((pnl>0).mean()),3),
             'eqrisk_gross_bp':round(float(pnl_eq.mean()*1e4),2),'eqrisk_ci':[round(float(x*1e4),2) for x in boot(pnl_eq,wk)],'eqrisk_sd_bp':round(float(pnl_eq.std()*1e4),1),
             'net_bp_at_cost_per_leg':{c:round(float(pnl.mean()*1e4-2*c),2) for c in [0,1,2,4,8]},
             'sharpe_ann_gross':round(float(pnl.mean()/pnl.std()*np.sqrt(6*365)),2),'sharpe_ann_net2bp':round(float((pnl.mean()-2*2e-4)/pnl.std()*np.sqrt(6*365)),2),
             'top5pct_share':round(float(pnl[pnl>=np.quantile(pnl,0.95)].sum()/pnl.sum()),3) if pnl.sum()>0 else None,
             'max_dd_bp':round(float((pnl.cumsum()-np.maximum.accumulate(pnl.cumsum())).min()*1e4),0),
             'by_year_bp':{int(y):round(float(pnl[tsa.year==y].mean()*1e4),2) for y in years},
             'by_hour_block':{f'{h0:02d}-{h0+4:02d}':round(float(pnl[(tsa.hour>=h0)&(tsa.hour<h0+4)].mean()*1e4),2) for h0 in range(0,24,4)}}
        out[f'{rule}_k{kfrac:.2f}']=res; print(rule,f'k={kfrac:.2f}',res,flush=True)
# single-asset reversal per asset (sign = -sign(r_4h)), net of 4 bp, for comparison at the same anchors (one leg)
sa={}
for a in assets:
    g=CS[CS.asset==a]; s=-np.sign(g.r_4h); x=(s*g.y_r_4h).values; sa[a]={'n':int(len(g)),'gross_bp':round(float(x.mean()*1e4),2),'net4':round(float(x.mean()*1e4-4),2),'hit':round(float((x>0).mean()),3)}
out['single_asset_rev_4h']=sa; print('single-asset reversal',sa)
json.dump(out,open(os.path.join(os.path.dirname(__file__),'results',f'e6_xsec_econ_{tag}.json'),'w'),indent=1)
