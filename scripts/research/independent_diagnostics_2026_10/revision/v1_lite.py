"""V1-lite: the Forecast V1 score formula (analytics/forecasting/core.py) replayed on Binance-only 5m data 2020-10..2026-07.
Components: price = clamp(pm/0.50)*1 (pm = 5m open->close move %), flow = clamp(imb/0.10) (imb = (tb-ts)/(tb+ts) of the bucket),
oi = sign-conditional clamp01(|d_oi|/1.0) with d_oi = % change of sum_open_interest over the bucket (5m metrics snapshots),
funding = clamp(-fr/0.0003), liquidations = 0 (not archived), agreement = anchor_sign*1.0 (single venue).
final = 0.30 price + 0.30 flow + 0.15 oi + 0.10 funding + 0.10*0 + 0.05 agreement; gates |anchor|>=0.10, |final|>=0.30.
Questions: does the score carry information about the future beyond the 5m move itself? at 15m/1h/4h? with one-cycle lateness?"""
import pandas as pd, numpy as np, glob, zipfile, io, json
from sklearn.metrics import roc_auc_score
k=pd.read_pickle('data/btc5m.pkl')
rows=[]
for fz in sorted(glob.glob('data/metrics_early/*.zip')+glob.glob('data/metrics/*.zip')):
    raw=zipfile.ZipFile(fz).read(zipfile.ZipFile(fz).namelist()[0]); rows.append(pd.read_csv(io.BytesIO(raw)))
m=pd.concat(rows,ignore_index=True); m['ts']=pd.to_datetime(m['create_time'],utc=True,format='mixed'); m=m.sort_values('ts').drop_duplicates('ts').set_index('ts')
oi=m['sum_open_interest'].astype(float); oi=oi[oi.index==oi.index.floor('5min')].reindex(k.index)
# bucket t = [open_time, open_time+5m): OI change within the bucket ~ snapshot at t+5m vs snapshot at t
d_oi=(oi.shift(-1)/oi-1)*100   # known at bucket close
clamp=lambda x: np.clip(x,-1,1)
pm=(k.close/k.open-1)*100; price=clamp(pm/0.50)
tb=k.taker_buy_quote_volume; ts=k.quote_volume-k.taker_buy_quote_volume; gross=tb+ts; imb=np.where(gross>0,(tb-ts)/np.maximum(gross,1e-9),0.0); flow=clamp(imb/0.10)
anchor=clamp(0.5*price+0.5*flow); asign=np.sign(anchor)
oi_s=np.where((asign!=0)&np.isfinite(d_oi)&(d_oi!=0), np.where(d_oi>0,asign,-asign)*np.clip(np.abs(d_oi)/1.0,0,1),0.0)
fund=clamp(-k.funding/0.0003)
agree=asign*1.0
final=clamp(0.30*price+0.30*flow+0.15*oi_s+0.10*fund+0.05*agree)
gate=(np.abs(anchor)>=0.10)&(np.abs(final)>=0.30)
direction=np.where(gate,np.sign(final),0)
conf=np.abs(final)   # sqrt(cc/100*mcr) unavailable -> 1
lc=np.log(k.close.values); c=k.close.values; o=k.open.values
D=pd.DataFrame({'final':final,'price':price,'flow':flow,'oi':oi_s,'fund':fund,'dir':direction,'conf':conf,'pm':pm},index=k.index)
D=D[D.index>=pd.Timestamp('2020-10-01',tz='UTC')]
out={}
for h,w in [('15m',3),('1h',12),('4h',48)]:
    fwd=pd.Series(lc,index=k.index).shift(-w)-lc              # from bucket close (reference price = close)
    fwd_late=pd.Series(lc,index=k.index).shift(-w-1)-pd.Series(lc,index=k.index).shift(-1)  # one 5m cycle late (enter at close of next bucket)
    d=D.join(fwd.rename('y')).join(fwd_late.rename('yl')).dropna(); d=d[d.y!=0]
    yb=(d.y>0).astype(int); res={'n_buckets':int(len(d)),'signal_share':float((d.dir!=0).mean()),'flip_adjacent':float((np.sign(d.dir.values[1:])*np.sign(d.dir.values[:-1])<0).mean())}
    res['auc_final']=float(roc_auc_score(yb,d.final)); res['auc_price_only(5m move)']=float(roc_auc_score(yb,d.price)); res['auc_flow_only']=float(roc_auc_score(yb,d.flow))
    res['auc_oi_only']=float(roc_auc_score(yb,d.oi)); res['auc_funding_only']=float(roc_auc_score(yb,d.fund))
    # incremental: residual of final after price? use final - 0.30*price
    res['auc_final_minus_price']=float(roc_auc_score(yb,d.final-0.30*d.price))
    s=d[d.dir!=0]; g=s.dir*s.y; gl=s.dir*s.yl
    res['signals']={'n':int(len(s)),'hit':float((g>0).mean()),'gross_bp':float(g.mean()*1e4),'hit_late':float((gl>0).mean()),'gross_bp_late':float(gl.mean()*1e4)}
    # by confidence quartile
    q=pd.qcut(s.conf,4,labels=False); res['hit_by_conf_quartile']={int(i):float((g[q==i]>0).mean()) for i in range(4)}; res['gross_by_conf_quartile']={int(i):float(g[q==i].mean()*1e4) for i in range(4)}
    # by year
    res['hit_by_year']={int(y):float((g[s.index.year==y]>0).mean()) for y in sorted(set(s.index.year))}
    # does the signal beat "sign of the 5m move" as a rule?
    gp=np.sign(d.pm)*d.y; res['rule_sign_of_5m_move']={'hit':float((gp[d.pm!=0]>0).mean()),'gross_bp':float(gp.mean()*1e4)}
    out[h]=res; print(h,json.dumps(res))
json.dump(out,open('rev/v1_lite_results.json','w'),indent=1)
