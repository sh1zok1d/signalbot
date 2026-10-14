"""E8: executable portfolio simulation of the cross-sectional short-term reversal (revision of E6).
At each 4h anchor (bar close), rank the assets present by their past 4h (or 1h) log return; long the bottom third, short the
top third; leg weights equal (or inverse-vol), each leg gross 0.5 (dollar-neutral, gross notional 1).  Positions are held to
the next anchor; the next weights are compared with the drifted old weights, and the TURNOVER (sum |dw|) is charged at c bp
per unit notional traded (c = 0,1,2,4,8), plus an optional slippage s bp.  Funding is charged at every 8h settlement
(00/08/16 UTC) that falls inside the holding window, from the Binance funding archives (long pays positive funding).
A vol-targeted variant scales gross notional so that the trailing 30-day realised strategy vol equals a 1 % per-4h target
(leverage capped at 3).  Fixed rules, no fitting: every year is out of sample.  Years on the command line."""
import os, sys, glob, zipfile, io, pickle, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); from panel import DATA_DIR
D=pickle.load(open(os.path.join(DATA_DIR,os.environ.get('XM_PANEL','xm_panel12.pkl')),'rb')); P=D['P']; F=D['F']; assets=D['assets']
years=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [2022,2023,2024]; tag=sys.argv[2] if len(sys.argv)>2 else 'dev12'
def load_funding(sym):
    d={'BTC':'funding'}.get(sym, f'funding_{sym}USDT'); fr=[]
    for z in sorted(glob.glob(os.path.join(DATA_DIR,d,'*.zip'))):
        zf=zipfile.ZipFile(z); raw=zf.read(zf.namelist()[0]); hdr=0 if raw[:9]==b'calc_time' else None
        df=pd.read_csv(io.BytesIO(raw),header=hdr,names=None if hdr==0 else ['calc_time','funding_interval_hours','last_funding_rate']); df.columns=['calc_time','funding_interval_hours','last_funding_rate']; fr.append(df)
    if not fr: return None
    f=pd.concat(fr); f['calc_time']=f['calc_time'].astype('int64'); f.loc[f.calc_time>1e14,'calc_time']//=1000
    f['ts']=pd.to_datetime(f.calc_time,unit='ms',utc=True).dt.round('h'); return f.drop_duplicates('ts').set_index('ts')['last_funding_rate'].astype(float).sort_index()
FUND={a:load_funding(a) for a in assets}; missing=[a for a,v in FUND.items() if v is None]
w=48; rows=[]
for a in assets:
    f=F[a][['r_1h','r_4h','lrv_24h','y_r_4h']].copy(); f['asset']=a; f['present']=P[a]['present']; rows.append(f.iloc[::w])
CS=pd.concat(rows); CS=CS[CS.present==1].dropna(); CS['ts']=CS.index; CS=CS[CS.index.year.isin(years)]
anchors=sorted(CS.ts.unique()); A=np.array(assets); ia={a:i for i,a in enumerate(assets)}
rng=np.random.default_rng(0)
def boot(x,wk,B=400):
    uw=np.unique(wk); idx={u:np.where(wk==u)[0] for u in uw}; o=[]
    for _ in range(B):
        ii=np.concatenate([idx[u] for u in rng.choice(uw,len(uw),replace=True)]); o.append(x[ii].mean())
    return np.percentile(o,[2.5,97.5])
def fund_cost(ts, wvec):
    """funding paid on weights held during (ts, ts+4h]: settlements at hours 0/8/16 strictly after ts and <= ts+4h"""
    cost=0.0; t_end=ts+pd.Timedelta(hours=4)
    for st in pd.date_range(ts+pd.Timedelta(hours=1), t_end, freq='h'):
        if st.hour in (0,8,16):
            for i,a in enumerate(assets):
                if wvec[i]!=0 and FUND[a] is not None and st in FUND[a].index: cost+=wvec[i]*float(FUND[a].loc[st])   # long pays positive rate
    return cost
out={}
for rule in ['rev_4h','rev_1h']:
    col={'rev_1h':'r_1h','rev_4h':'r_4h'}[rule]
    for wt in ['equal','invvol']:
        w_old=np.zeros(len(assets)); rets=[]; turns=[]; funds=[]; wks=[]; tss=[]; gross_exp=[]
        G=dict(tuple(CS.groupby('ts')))
        for ts in anchors:
            g=G[ts]; n=len(g)
            if n<6: w_new=np.zeros(len(assets))
            else:
                k=max(1,int(round(n/3))); gs=g.sort_values(col); lo=gs.iloc[:k]; hi=gs.iloc[-k:]; w_new=np.zeros(len(assets))
                if wt=='equal': wl=np.full(k,0.5/k); wh=np.full(k,0.5/k)
                else:
                    sl=1/np.exp(lo.lrv_24h.values); wl=0.5*sl/sl.sum(); sh=1/np.exp(hi.lrv_24h.values); wh=0.5*sh/sh.sum()
                for a_,x in zip(lo.asset,wl): w_new[ia[a_]]=x
                for a_,x in zip(hi.asset,wh): w_new[ia[a_]]=-x
            turn=np.abs(w_new-w_old).sum(); r=np.zeros(len(assets))
            for a_,y in zip(g.asset,g.y_r_4h): r[ia[a_]]=y
            ret=float((w_new*r).sum()); fc=fund_cost(ts,w_new)
            rets.append(ret); turns.append(turn); funds.append(fc); wks.append(int((ts-anchors[0]).days//7)); tss.append(ts); gross_exp.append(np.abs(w_new).sum())
            w_old=w_new*(1+r)   # drift
        rets=np.array(rets); turns=np.array(turns); funds=np.array(funds); wk=np.array(wks); tsa=pd.DatetimeIndex(tss)
        res={'n_anchors':int(len(rets)),'gross_bp':round(float(rets.mean()*1e4),2),'gross_ci':[round(float(x*1e4),2) for x in boot(rets,wk)],'sd_bp':round(float(rets.std()*1e4),1),
             'turnover_per_anchor':round(float(turns.mean()),3),'funding_bp_per_anchor':round(float(funds.mean()*1e4),3),'gross_exposure':round(float(np.mean(gross_exp)),3)}
        for c in [0,1,2,4,8]:
            net=rets-turns*c*1e-4-funds; res[f'net_bp_c{c}']=round(float(net.mean()*1e4),2); res[f'net_ci_c{c}']=[round(float(x*1e4),2) for x in boot(net,wk)]
            res[f'sharpe_ann_c{c}']=round(float(net.mean()/net.std()*np.sqrt(6*365)),2); eq=net.cumsum(); res[f'maxdd_pct_c{c}']=round(float((eq-np.maximum.accumulate(eq)).min()*100),2)
            res[f'by_year_net_bp_c{c}']={int(y):round(float(net[tsa.year==y].mean()*1e4),2) for y in years}
        # vol-targeted: scale by target/trailing realised vol of gross returns (180 anchors ~ 30 days), cap 3x; costs scale with leverage
        sd=pd.Series(rets).rolling(180,min_periods=60).std().shift(1).values; lev=np.clip(0.01/np.where(np.isfinite(sd)&(sd>0),sd,np.nan),0,3); lev=np.where(np.isfinite(lev),lev,1.0)
        for c in [2,4]:
            netv=lev*(rets-turns*c*1e-4-funds); eq=netv.cumsum()
            res[f'voltarget_net_bp_c{c}']=round(float(netv.mean()*1e4),2); res[f'voltarget_sharpe_c{c}']=round(float(netv.mean()/netv.std()*np.sqrt(6*365)),2); res[f'voltarget_maxdd_pct_c{c}']=round(float((eq-np.maximum.accumulate(eq)).min()*100),2); res['mean_leverage']=round(float(lev.mean()),2)
        out[f'{rule}_{wt}']=res; print(rule,wt,json.dumps(res),flush=True)
out['funding_missing_assets']=missing
json.dump(out,open(os.path.join(os.path.dirname(__file__),'results',f'e8_portfolio_{tag}.json'),'w'),indent=1)
