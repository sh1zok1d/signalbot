import sys; sys.path.insert(0,'rev'); sys.path.insert(0,'diag')
import pandas as pd, numpy as np, json
from highvol_test import load_binance, feats, run, yr
R={}
fw=[(lambda s,ty=ty:(yr(s)<ty)&(s.end<pd.Timestamp(f'{ty}-01-01',tz='UTC')), lambda s,ty=ty: yr(s)==ty, str(ty)) for ty in [2022,2023,2024,2025,2026]]
for sym in ['SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT']:
    try: R[sym]=run(sym+' 2022-26',feats(load_binance(f'data/{sym}_5m/*.zip')),fw)
    except Exception as e: print(sym,'ERR',e)
spot=feats(load_binance('data/spot_btc_5m/*.zip'))
sp=[(lambda s:(s.index<pd.Timestamp('2018-07-01',tz='UTC'))&(s.end<pd.Timestamp('2018-07-01',tz='UTC')), lambda s:(s.index>=pd.Timestamp('2018-07-01',tz='UTC'))&(s.index<pd.Timestamp('2019-01-01',tz='UTC')),'2018H2'),
    (lambda s:(s.index<pd.Timestamp('2019-01-01',tz='UTC'))&(s.end<pd.Timestamp('2019-01-01',tz='UTC')), lambda s: yr(s)==2019,'2019')]
R['BINANCE_SPOT_BTC_2018H2_2019']=run('Binance spot BTC 2018H2+2019',spot,sp)
json.dump(R,open('rev/highvol_more_results.json','w'),indent=1)
