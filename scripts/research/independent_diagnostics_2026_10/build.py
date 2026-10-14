import zipfile, io, glob, os, sys
import pandas as pd, numpy as np
D = os.environ.get('DIAG_DATA_DIR', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'artifacts', 'independent_diagnostics_2026_10'))
cols = ['open_time','open','high','low','close','volume','close_time','quote_volume','count','taker_buy_volume','taker_buy_quote_volume','ignore']
frames = []
for f in sorted(glob.glob(os.path.join(D,'klines5m','*.zip'))):
    with zipfile.ZipFile(f) as z:
        name = z.namelist()[0]
        raw = z.read(name)
    first = raw[:40].decode()
    hdr = 0 if first.startswith('open_time') else None
    df = pd.read_csv(io.BytesIO(raw), header=hdr, names=cols if hdr is None else None)
    if hdr == 0: df.columns = cols
    frames.append(df)
k = pd.concat(frames, ignore_index=True)
k = k.astype({c: float for c in ['open','high','low','close','volume','quote_volume','taker_buy_volume','taker_buy_quote_volume']})
k['open_time'] = k['open_time'].astype('int64')
# some 2025+ files use microseconds
k.loc[k['open_time'] > 10**14, 'open_time'] //= 1000
k = k.drop_duplicates('open_time').sort_values('open_time').reset_index(drop=True)
k['ts'] = pd.to_datetime(k['open_time'], unit='ms', utc=True)
full = pd.date_range(k['ts'].iloc[0], k['ts'].iloc[-1], freq='5min', tz='UTC')
print('rows', len(k), 'expected', len(full), 'missing', len(full)-len(k), k['ts'].iloc[0], k['ts'].iloc[-1])
k = k.set_index('ts').reindex(full)
print('nan closes', k['close'].isna().sum())
k['close'] = k['close'].ffill()
for c in ['open','high','low']: k[c] = k[c].fillna(k['close'])
for c in ['volume','quote_volume','taker_buy_volume','taker_buy_quote_volume','count']: k[c] = k[c].fillna(0)
# funding
fr = []
for f in sorted(glob.glob(os.path.join(D,'funding','*.zip'))):
    with zipfile.ZipFile(f) as z:
        raw = z.read(z.namelist()[0])
    first = raw[:40].decode()
    hdr = 0 if first.startswith('calc_time') else None
    df = pd.read_csv(io.BytesIO(raw), header=hdr, names=['calc_time','funding_interval_hours','last_funding_rate'] if hdr is None else None)
    if hdr == 0: df.columns = ['calc_time','funding_interval_hours','last_funding_rate']
    fr.append(df)
fr = pd.concat(fr, ignore_index=True)
fr['calc_time'] = fr['calc_time'].astype('int64')
fr.loc[fr['calc_time'] > 10**14, 'calc_time'] //= 1000
fr['ts'] = pd.to_datetime(fr['calc_time'], unit='ms', utc=True).dt.floor('5min')
fr = fr.drop_duplicates('ts').set_index('ts')['last_funding_rate'].astype(float)
k['funding'] = fr.reindex(k.index).ffill()
print('funding rows', len(fr), 'nan after ffill', k['funding'].isna().sum())
k.to_pickle(os.path.join(D,'btc5m.pkl'))
print(k.tail(2))
