"""Pseudo-level twins per the frozen #352 half-rotation control (scripts/research/level_touch_degradation_v1/control.py),
re-implemented on the product constructor's episodes.  Real episodes of the same (family, struct_side) are sorted by (i0,
anchor_price, id); episode i takes partner (i + n//2 + step) % n; the pseudo anchor sits at the partner's signed distance from its
period open, applied to this episode's period open; partners colliding (within zone_half) with any real level instance active over
an overlapping index span are skipped.  Pseudo touches use the same touch rule, approach side, sigma, X and barriers as real ones
(scan with the product's _hits / _approach_side / sigma_at / race_x).  Output: results/events_pseudo.pkl with shadow_id = the real
event_id, plus results/pairs.pkl (real + pseudo matched on touch 1 both eligible)."""
import os, sys, math, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/signalbot'); sys.path.insert(0, os.path.dirname(__file__))
from beta import levels as LV
from race_analysis import load_venue, REPO
from levels import load_btc
from product_events import bars_from_df, enrich
ZH=LV.STRUCT_ZONE_HALF
def near(a,c,tol):
    lo,hi=(a,c) if a<c else (c,a); return lo>0 and (hi-lo)/lo<=tol
def collides(price,i0,i1,inst):
    for v in inst:
        if i0<=v['i1'] and v['i0']<=i1 and near(price,v['price'],ZH): return True
    return False
def control_episodes(b, episodes, inst):
    groups={}
    for ep in episodes: groups.setdefault((ep['family'],int(ep['struct_side'])),[]).append(ep)
    out=[]
    for key in sorted(groups):
        g=sorted(groups[key],key=lambda e:(e['i0'],e['anchor_price'],e['event_id'])); n=len(g)
        if n<2: continue
        shift=n//2
        for i,ep in enumerate(g):
            po=float(b.open[ep['i0']]); chosen=None
            for step in range(n-1):
                p=g[(i+shift+step)%n]
                if p['event_id']==ep['event_id']: continue
                ppo=float(b.open[p['i0']])
                if not (po>0 and ppo>0): continue
                d=p['anchor_price']/ppo-1.0; price=po*(1.0+d)
                if not math.isfinite(price) or price<=0: continue
                if collides(price,ep['i0'],ep['i1'],inst): continue
                chosen=(p,d,price); break
            if chosen is None: continue
            p,d,price=chosen
            out.append({**ep,'event_id':'CTRL:'+ep['event_id'],'shadow_id':ep['event_id'],'partner_id':p['event_id'],'kind':'CTRL_'+ep['kind'],
                        'anchor_price':price,'zone_low':price*(1-ZH),'zone_high':price*(1+ZH),'distance':d,'member_kinds':['CTRL_'+ep['kind']],'absorbed_later':[]})
    return out
def touches(b, episodes):
    out=[]
    for ep in episodes:
        i0,i1=ep['i0'],min(ep['i1'],b.n-1)
        j=next((k for k in range(i0,i1+1) if LV._hits(b,k,ep['zone_low'],ep['zone_high'])),None)
        if j is None: continue
        s=LV.sigma_at(b.close,j); x=LV.race_x(s) if math.isfinite(s) else math.nan
        usable=bool(math.isfinite(x) and LV.RACE_X_MIN<x<LV.RACE_X_MAX); side=LV._approach_side(b,j,i0,ep['zone_low'],ep['zone_high'])
        brk,rej=(ep['zone_high']*(1+x),ep['zone_low']*(1-x)) if side>0 else (ep['zone_low']*(1-x),ep['zone_high']*(1+x))
        reason=None if usable and side in (1,-1) else ('SIGMA_UNUSABLE' if not usable else 'SIDE_UNKNOWN')
        if ep['active_open_ms']-b.t0<LV.ABSORPTION_LOOKBACK_MS: reason='WINDOW_TOO_SHORT'
        out.append({**{k:v for k,v in ep.items() if k not in ('i0','i1','priority')},'j':int(j),'side':int(side),'sigma':s,'x':x,
                    'break_barrier':float(brk) if usable and side else None,'reject_barrier':float(rej) if usable and side else None,'eligible':reason is None})
    return out
if __name__=='__main__':
    k=load_btc(); b=bars_from_df(k)
    levels=LV.structural_levels(b); eps=LV.structural_episodes(b,levels)
    inst=[{'price':l['price'],'i0':l['i0'],'i1':l['i1']} for l in levels]
    ctrl=control_episodes(b,eps,inst); print('real episodes',len(eps),'control episodes',len(ctrl))
    # sanity: product touches reproduce product constructor
    pt=[e for e in touches(b,eps) if e['eligible']]; prod=[e for e in LV.structural_first_touches(b) if e['eligible']]
    assert len(pt)==len(prod) and all(a['j']==c['j'] and a['side']==c['side'] and abs((a['x'] or 0)-(c['x'] or 0))<1e-12 for a,c in zip(pt,prod)), 'touch re-implementation differs from product'
    ct=[e for e in touches(b,ctrl) if e['eligible']]; print('eligible pseudo touches',len(ct),'of',len(ctrl))
    okx=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/okx_btc_usdt_swap_5m.csv.gz')); byb=load_venue(os.path.join(REPO,'docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/bybit_btcusdt_linear_5m.csv.gz'))
    P=enrich(k,ct,okx,byb,'pseudo'); P['shadow_id']=[e['shadow_id'] for e in ct if e['j']>=300 and e['j']+49<len(k)]
    P.to_pickle(os.path.join(os.path.dirname(__file__),'results','events_pseudo.pkl'))
    R=pd.read_pickle(os.path.join(os.path.dirname(__file__),'results','events_real.pkl'))
    pairs=R.merge(P,left_on='event_id',right_on='shadow_id',suffixes=('_r','_p')); pairs.to_pickle(os.path.join(os.path.dirname(__file__),'results','pairs.pkl'))
    print('matched pairs',len(pairs), pairs.groupby('year_r').size().to_dict()); print(P.label.value_counts(normalize=True).round(3).to_dict())
    print('pseudo distance stats', pd.Series([e['distance'] for e in ctrl]).describe().round(4).to_dict())
