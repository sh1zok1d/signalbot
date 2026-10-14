"""Analysis of the Forecast V1 shadow export (CSV files produced by v1_extraction_procedure.md on the VPS).
Usage: python v1_analyze_export.py /path/v1_predictions.csv /path/v1_outcomes.csv [--exclude-e1]
Computes, per horizon: hit rate of LONG/SHORT, mean directional return (bp), AUC of final_score and of the 5m
price move (price_move_pct_median) for the sign of market_return, incremental AUC of final_score after
removing the price component, hit rate by confidence quartile and by day, adjacent flip rate, and the
counterfactual 'late by one cycle' (not available from persisted outcomes; needs 1m klines)."""
import sys, pandas as pd, numpy as np
from sklearn.metrics import roc_auc_score
pred=pd.read_csv(sys.argv[1], parse_dates=['bucket_ts']); outc=pd.read_csv(sys.argv[2], parse_dates=['bucket_ts'])
if '--exclude-e1' in sys.argv:
    lo=pd.Timestamp('2026-08-16T00:00:00Z'); hi=pd.Timestamp('2026-08-25T17:20:00Z')
    pred=pred[(pred.bucket_ts<lo)|(pred.bucket_ts>=hi)]; outc=outc[(outc.bucket_ts<lo)|(outc.bucket_ts>=hi)]
pred=pred.sort_values(['bucket_ts','created_at']).drop_duplicates('bucket_ts',keep='first')   # one row per bucket (earliest calc version)
key=['symbol','market_type','timeframe','bucket_ts','calculation_version','rule_version']
print('predictions', len(pred), pred.bucket_ts.min(), pred.bucket_ts.max(), 'direction counts', pred.direction.value_counts().to_dict())
d=pred.direction.map({'LONG':1,'SHORT':-1,'NEUTRAL':0}).values
print('signal share', (d!=0).mean(), 'adjacent flip among consecutive signals', (d[1:]*d[:-1]<0).mean())
for h in ['15m','1h','4h']:
    o=outc[outc.horizon==h].merge(pred[key+['direction','final_score','confidence','component_scores_price','price_move_pct_median'] if 'component_scores_price' in pred.columns else key+['direction','final_score','confidence']],on=key,how='inner',suffixes=('','_p'))
    o=o[o.market_return_pct!=0]; y=(o.market_return_pct>0).astype(int)
    row={'n':len(o),'auc_final_score':roc_auc_score(y,o.final_score)}
    if 'price_move_pct_median' in o: row['auc_5m_move_only']=roc_auc_score(y,o.price_move_pct_median); row['auc_final_minus_price']=roc_auc_score(y,o.final_score-0.30*o.component_scores_price)
    s=o[o.direction.isin(['LONG','SHORT'])]; g=s.directional_return_pct
    row.update({'signals':len(s),'hit':(g>0).mean(),'mean_bp':g.mean()*100,'median_bp':g.median()*100,'mfe_bp':s.mfe_pct.mean()*100,'mae_bp':s.mae_pct.mean()*100})
    q=pd.qcut(s.confidence,4,labels=False,duplicates='drop'); row['hit_by_conf_q']={int(i):float((g[q==i]>0).mean()) for i in sorted(q.unique())}
    row['hit_by_day']={str(k_.date()):round(float(v),3) for k_,v in g.groupby(s.bucket_ts.dt.floor('D')).apply(lambda x:(x>0).mean()).items()}
    print(h, row)
