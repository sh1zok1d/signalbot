"""Common 5m panel of Binance USD-M perpetuals from monthly Binance Vision archives.
DATA_DIR (env XM_DATA_DIR) holds <SYM>_5m/ (or klines5m/ for BTC, eth5m/ for ETH) monthly zips."""
import os, glob, zipfile, io
import numpy as np, pandas as pd
DATA_DIR = os.environ.get('XM_DATA_DIR', '/tmp/claude-0/-home-user-signalbot/4d2253b8-11f7-5571-8d07-29099e51fb7c/scratchpad/data')
DIRS = {'BTC':'klines5m','ETH':'eth5m'}
COLS = ['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']
ASSETS_ALL = ['BTC','ETH','SOL','BNB','XRP','DOGE','ADA','LINK','LTC','AVAX','DOT','BCH']
def load_asset(sym):
    d = DIRS.get(sym, f'{sym}USDT_5m'); fr=[]
    for z in sorted(glob.glob(os.path.join(DATA_DIR, d, '*.zip'))):
        zf=zipfile.ZipFile(z); raw=zf.read(zf.namelist()[0]); hdr=0 if raw[:9]==b'open_time' else None
        df=pd.read_csv(io.BytesIO(raw),header=hdr,names=None if hdr==0 else COLS); df.columns=COLS; fr.append(df)
    k=pd.concat(fr); k['open_time']=k['open_time'].astype('int64'); k.loc[k.open_time>1e14,'open_time']//=1000
    k['ts']=pd.to_datetime(k.open_time,unit='ms',utc=True); k=k.drop_duplicates('ts').set_index('ts').sort_index()
    for c in ['open','high','low','close','quote_volume','taker_buy_quote_volume','count']: k[c]=k[c].astype(float)
    return k[['open','high','low','close','quote_volume','taker_buy_quote_volume','count']]
def build(assets, start='2020-01-01', end='2026-08-01'):
    idx=pd.date_range(pd.Timestamp(start,tz='UTC'), pd.Timestamp(end,tz='UTC')-pd.Timedelta('5min'), freq='5min')
    P={}
    for s in assets:
        k=load_asset(s).reindex(idx); present=k['close'].notna()
        k['close']=k['close'].ffill()
        for c in ['open','high','low']: k[c]=k[c].fillna(k['close'])
        for c in ['quote_volume','taker_buy_quote_volume','count']: k[c]=k[c].fillna(0.0)
        k['present']=present.astype(float); P[s]=k
        print(s, 'first', present.idxmax(), 'present share', round(present.mean(),4))
    return P
W={'5m':1,'15m':3,'1h':12,'4h':48,'24h':288,'7d':2016}
def own_features(k):
    """26 single-asset features used by the earlier investigations (no funding), at bar close t."""
    c=k.close.values; lc=np.log(c); r=np.diff(lc,prepend=lc[0]); f=pd.DataFrame(index=k.index)
    S=lambda x,n: pd.Series(x,index=k.index).rolling(n,min_periods=n).sum().values
    M=lambda x,n: pd.Series(x,index=k.index).rolling(n,min_periods=n).mean().values
    for n,w in W.items(): f['r_'+n]=S(r,w)
    for n in ['1h','4h','24h','7d']: f['lrv_'+n]=np.log(np.sqrt(M(r*r,W[n]))+1e-9)
    f['volratio_1h_24h']=f.lrv_1h-f.lrv_24h; f['volratio_4h_7d']=f.lrv_4h-f.lrv_7d
    hi=k.high.values; lo=k.low.values
    for n in ['4h','24h','7d']:
        H=pd.Series(hi,index=k.index).rolling(W[n],min_periods=W[n]).max().values; L=pd.Series(lo,index=k.index).rolling(W[n],min_periods=W[n]).min().values
        f['pos_'+n]=(c-L)/np.maximum(H-L,1e-9); f['lrange_'+n]=np.log((H-L)/c+1e-9)
    qv=k.quote_volume.values; tb=k.taker_buy_quote_volume.values
    for n in ['1h','4h','24h']: f['taker_'+n]=S(tb,W[n])/np.maximum(S(qv,W[n]),1e-9)-0.5
    f['lvol_1h_rel']=np.log(S(qv,12)+1)-np.log(M(S(qv,12),2016)+1); f['lvol_24h_rel']=np.log(S(qv,288)+1)-np.log(M(S(qv,288),2016)+1)
    hr=k.index.hour+k.index.minute/60; f['hod_sin']=np.sin(2*np.pi*hr/24); f['hod_cos']=np.cos(2*np.pi*hr/24); f['weekend']=(k.index.dayofweek>=5).astype(float)
    for n,w in [('1h',12),('4h',48),('24h',288)]: f['y_r_'+n]=pd.Series(lc,index=k.index).shift(-w).values-lc
    f['r5']=r
    return f
OWN=['r_5m','r_15m','r_1h','r_4h','r_24h','r_7d','lrv_1h','lrv_4h','lrv_24h','lrv_7d','volratio_1h_24h','volratio_4h_7d','pos_4h','pos_24h','pos_7d','lrange_4h','lrange_24h','lrange_7d','taker_1h','taker_4h','taker_24h','lvol_1h_rel','lvol_24h_rel','hod_sin','hod_cos','weekend']
XFEATS=['r_5m','r_15m','r_1h','r_4h','r_24h','r_7d','lrv_1h','lrv_4h','lrv_24h','pos_24h','taker_1h','taker_4h']   # features of ANOTHER asset used as cross inputs
if __name__=='__main__':
    import sys, pickle
    assets=sys.argv[1].split(',') if len(sys.argv)>1 else ['BTC','ETH','SOL','BNB','XRP','DOGE']
    P=build(assets); F={s:own_features(P[s]) for s in assets}
    out=os.path.join(DATA_DIR,'xm_panel.pkl'); pickle.dump({'P':P,'F':F,'assets':assets},open(out,'wb')); print('saved',out)
