# explicit-loop verification of feature/target alignment in the original feat5m.pkl
import pandas as pd, numpy as np
k = pd.read_pickle('data/btc5m.pkl'); f = pd.read_pickle('data/feat5m.pkl')
c = k['close'].values; hi=k['high'].values; lo=k['low'].values; lc=np.log(c); r=np.diff(lc,prepend=lc[0])
rng=np.random.default_rng(3); idx=rng.integers(3000,len(k)-3000,size=2000)
bad={}
for i in idx:
    # backward features: r_4h = sum of r over bars i-47..i (= lc[i]-lc[i-48])
    assert abs(f['r_4h'].iloc[i]-(lc[i]-lc[i-48]))<1e-12
    assert abs(f['rv_4h'].iloc[i]-np.sqrt(np.mean(r[i-47:i+1]**2)))<1e-12
    assert abs(f['pos_24h'].iloc[i]-(c[i]-lo[i-287:i+1].min())/max(hi[i-287:i+1].max()-lo[i-287:i+1].min(),1e-9))<1e-9
    # forward targets over bars i+1..i+48
    assert abs(f['y_r_4h'].iloc[i]-(lc[i+48]-lc[i]))<1e-12
    assert abs(f['y_lrv_4h'].iloc[i]-np.log(np.sqrt(np.mean(r[i+1:i+49]**2))+1e-9))<1e-9
    assert abs(f['y_lrange_4h'].iloc[i]-np.log((hi[i+1:i+49].max()-lo[i+1:i+49].min())/c[i]+1e-9))<1e-9
    assert abs(f['y_r_1h'].iloc[i]-(lc[i+12]-lc[i]))<1e-12
    assert abs(f['y_r_24h'].iloc[i]-(lc[i+288]-lc[i]))<1e-12
print('alignment OK on 2000 random anchors')
# funding availability: funding at bar t equals the last calc_time <= open_time(t)?
print('ties y_r_4h==0:', int((f['y_r_4h']==0).sum()), ' y_r_1h==0:', int((f['y_r_1h']==0).sum()))
# taker share sanity
print('taker_4h mean/std', f['taker_4h'].mean(), f['taker_4h'].std())
# how many training anchors (stride 48) have horizon end inside the next year, per year
for h,w in [('1h',12),('4h',48),('24h',288)]:
    sub=f.iloc[::48]; ends=sub.index+pd.Timedelta(minutes=5*w)
    cross=(ends.year!=sub.index.year).sum(); print(h,'stride48 anchors whose horizon crosses a year boundary:',int(cross))
