import pandas as pd, numpy as np, os
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
def load():
    k = pd.read_pickle(os.path.join(D,'btc5m.pkl'))
    c = k['close'].values; lc = np.log(c)
    r = np.diff(lc, prepend=lc[0])
    f = pd.DataFrame(index=k.index)
    f['close'] = c
    def roll_sum(x, n): return pd.Series(x, index=k.index).rolling(n, min_periods=n).sum().values
    def roll_mean(x, n): return pd.Series(x, index=k.index).rolling(n, min_periods=n).mean().values
    def roll_max(x, n): return pd.Series(x, index=k.index).rolling(n, min_periods=n).max().values
    def roll_min(x, n): return pd.Series(x, index=k.index).rolling(n, min_periods=n).min().values
    W = {'5m':1,'15m':3,'1h':12,'4h':48,'24h':288,'7d':2016}
    for n,w in W.items():
        f['r_'+n] = roll_sum(r, w)
    for n in ['1h','4h','24h','7d']:
        w = W[n]; f['rv_'+n] = np.sqrt(roll_mean(r*r, w))
    f['lrv_1h'] = np.log(f['rv_1h']+1e-9); f['lrv_4h']=np.log(f['rv_4h']+1e-9); f['lrv_24h']=np.log(f['rv_24h']+1e-9); f['lrv_7d']=np.log(f['rv_7d']+1e-9)
    f['volratio_1h_24h'] = f['lrv_1h']-f['lrv_24h']; f['volratio_4h_7d'] = f['lrv_4h']-f['lrv_7d']
    hi = k['high'].values; lo = k['low'].values
    for n in ['4h','24h','7d']:
        w = W[n]; H = roll_max(hi,w); L = roll_min(lo,w)
        f['pos_'+n] = (c-L)/np.maximum(H-L,1e-9)
        f['lrange_'+n] = np.log((H-L)/c+1e-9)
    qv = k['quote_volume'].values; tb = k['taker_buy_quote_volume'].values
    for n in ['1h','4h','24h']:
        w = W[n]; f['taker_'+n] = roll_sum(tb,w)/np.maximum(roll_sum(qv,w),1e-9)-0.5
    f['lvol_1h_rel'] = np.log(roll_sum(qv,12)+1)-np.log(roll_mean(roll_sum(qv,12),2016)+1)
    f['lvol_24h_rel'] = np.log(roll_sum(qv,288)+1)-np.log(roll_mean(roll_sum(qv,288),2016)+1)
    f['funding'] = k['funding'].values
    f['funding_24h'] = roll_mean(k['funding'].values, 288)
    fm = pd.Series(k['funding'].values,index=k.index); f['funding_z30d'] = ((fm - fm.rolling(8640,min_periods=2000).mean())/(fm.rolling(8640,min_periods=2000).std()+1e-9)).values
    hr = k.index.hour.values + k.index.minute.values/60
    f['hod_sin'] = np.sin(2*np.pi*hr/24); f['hod_cos']=np.cos(2*np.pi*hr/24)
    f['weekend'] = (k.index.dayofweek.values>=5).astype(float)
    f['dow'] = k.index.dayofweek.values
    # forward targets (computed at close of bar t, over bars t+1..t+h)
    for n in ['1h','4h','24h']:
        w = W[n]
        fwd = pd.Series(lc,index=k.index).shift(-w).values - lc
        f['y_r_'+n] = fwd
        f['y_up_'+n] = (fwd>0).astype(float); f.loc[np.isnan(fwd),'y_up_'+n]=np.nan
        r2 = pd.Series(r*r,index=k.index)
        f['y_lrv_'+n] = np.log(np.sqrt(r2.shift(-w).rolling(w,min_periods=w).sum().values/w)+1e-9) if False else np.log(np.sqrt(r2[::-1].rolling(w,min_periods=w).mean()[::-1].shift(-1).values)+1e-9)
        H = pd.Series(hi,index=k.index)[::-1].rolling(w,min_periods=w).max()[::-1].shift(-1).values
        L = pd.Series(lo,index=k.index)[::-1].rolling(w,min_periods=w).min()[::-1].shift(-1).values
        f['y_lrange_'+n] = np.log((H-L)/c+1e-9)
        f['y_maxabs_'+n] = np.maximum(np.log(H/c), -np.log(L/c))  # max excursion either side
    f['year'] = k.index.year
    f['week'] = (k.index - k.index[0]).days//7
    return f
FEATS = ['r_5m','r_15m','r_1h','r_4h','r_24h','r_7d','lrv_1h','lrv_4h','lrv_24h','lrv_7d','volratio_1h_24h','volratio_4h_7d',
         'pos_4h','pos_24h','pos_7d','lrange_4h','lrange_24h','lrange_7d','taker_1h','taker_4h','taker_24h','lvol_1h_rel','lvol_24h_rel',
         'funding','funding_24h','funding_z30d','hod_sin','hod_cos','weekend']
if __name__ == '__main__':
    f = load(); f.to_pickle(os.path.join(D,'feat5m.pkl')); print(f.shape); print(f[FEATS].describe().T[['mean','std','min','max']])
