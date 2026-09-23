"""Fresh synthetic card corpus for GENERATOR_CONTRACT_V02.

Built from templates written for this gate. It deliberately does not reuse any
first-shadow v5/v6/v7 production string (a test enforces that). Every item is
labelled before validation with:
  SAFETY   SAFE | UNSAFE          (semantic: could require protected/post-2024
                                   data, claim a result, or misstate data status)
  CONTRACT COMPLIANT | VIOLATING  (does it follow the stated V02 rules)
  EXPECT   VALID | HARD_FAIL      (what intake must do)
Semantically wrong but contract-compliant cards (e.g. a lookahead predictor) are
labelled SAFETY=SEMANTIC_ERROR, EXPECT=VALID: intake cannot judge them; the red
team critic must.
"""
from __future__ import annotations
import copy
import random

SLOT={'CANDIDATE_ID':'C101','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':'KLINES'}

def base_ready():
    return {
        'CANDIDATE_ID':'C101','NAME':'Gate card: intraday range position persistence','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL',
        'MECHANISM':'Close location inside the session range as an inventory-pressure proxy',
        'CAUSAL_OR_STRUCTURAL_STORY':'Market makers unwinding inventory leave a footprint in where bars close within their range.',
        'INFORMATION_SOURCE':'KLINES','OBSERVABLE':'Close location value computed from completed 1m bars',
        'FUNCTION':'Rank-correlate close location with subsequent 4h absolute return','PRIMARY_TARGET':'Absolute 4h log return after decision T',
        'HORIZON':'4h','BASELINE_OR_NULL':'Block-shuffled close location preserving weekday composition',
        'FALSIFIER':'Rank correlation inside the null 95 percent band in both halves of the window',
        'NEAREST_TESTED_MECHANISM':'NONE','MECHANISM_DISTANCE_ARGUMENT':'Uses bar-internal geometry rather than levels or volatility state.',
        'WHY_NOT_A_RESCUE':'No prior signature used close location.','SEARCH_SURFACE':{'PARAMETERS':{'window_bars':[30,60],'horizon_hours':[4]},'MAX_VARIANTS':2},
        'MAIN_CONFOUNDERS':'Volatility clustering and session effects','NO_LOOKAHEAD_RULE':'Every input bar closes at or before decision T.',
        'DATA_REQUIRED':[{'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'1m OHLC bars','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}],
        'DATA_STATUS':'DATA_READY','MISSING_OBSERVABLES':[],'DATA_GAP_CLASS':'NONE',
        'EXPECTED_IMPLEMENTATION_COST':'Small; one pass over catalogued bars','WHAT_POSITIVE_WOULD_TEACH':'Bar geometry carries inventory information.',
        'WHAT_NULL_WOULD_ELIMINATE':'Close location as a standalone pressure proxy.','EXPECTED_INFORMATION_GAIN':'Separates geometry from volatility level.',
        'PROTECTED_DATA_REQUIREMENT':False,
    }

def base_blocked():
    c=base_ready()
    c.update(NAME='Gate card: validator queue depth and block timing',MECHANISM='Mempool congestion propagating into exchange deposit timing',
             INFORMATION_SOURCE='ONCHAIN',OBSERVABLE='Pending transaction count per block interval',
             DATA_REQUIRED=[{'DATASET':'GATE_MEMPOOL_ARCHIVE','OBSERVABLE':'pending transaction counts with first-seen timestamps','STATUS':'DATA_BLOCKED_MISSING_OBSERVABLE','LEGAL_RANGE':'2021-03..2024-06'}],
             DATA_STATUS='DATA_BLOCKED_MISSING_OBSERVABLE',MISSING_OBSERVABLES=['first-seen mempool timestamps'],DATA_GAP_CLASS='MEMPOOL_HISTORY')
    c['SLOT']={'CANDIDATE_ID':'C101','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':'ONCHAIN'}
    return c

def _item(cid,category,safety,contract,expect,card,slot=None,note=''):
    card=copy.deepcopy(card)
    slot=copy.deepcopy(slot or card.pop('SLOT',None) or SLOT)
    card.pop('SLOT',None)
    return {'ID':cid,'CATEGORY':category,'SAFETY':safety,'CONTRACT':contract,'EXPECT':expect,'CARD':card,'SLOT':slot,'NOTE':note}

def _set(card,path,value):
    c=copy.deepcopy(card);slot=c.pop('SLOT',None)
    target=c
    for k in path[:-1]:target=target[k]
    target[path[-1]]=value
    if slot:c['SLOT']=slot
    return c

TEXT_TARGETS=('HORIZON','PRIMARY_TARGET','OBSERVABLE','FUNCTION','BASELINE_OR_NULL','FALSIFIER','CAUSAL_OR_STRUCTURAL_STORY','MECHANISM','NO_LOOKAHEAD_RULE','MAIN_CONFOUNDERS','EXPECTED_INFORMATION_GAIN')

def build_corpus(seed=20260923):
    rng=random.Random(seed)
    items=[];n=[0]
    def add(*a,**k):
        n[0]+=1;items.append(_item('G'+str(n[0]).zfill(3),*a,**k))
    ready,blocked=base_ready(),base_blocked()
    # 1. Canonical valid cards across datasets, statuses and ranges.
    for ds,rngs in (('CORE_BTC_BINANCE_V0',['2020-01..2024-12','2021-06..2023-02','2024-12..2024-12']),('CORE_ETH_BINANCE_V0',['2020-01..2020-01','2022-03..2024-12']),
                    ('MARKET_06_OKX_BINANCE_FEASIBILITY_V0',['2022-01..2024-12','2023-05..2024-01']),('D2_BITMEX_PRE2020_XBTUSD',['pre-2020','pre-2018','2016-01..2019-12']),
                    ('D11_FOMC_OFFICIAL_V0',['2020-01..2024-12']),('SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0',['2019-12..2024-12','2020-06..2024-06']),('STATUTORY_DST_CALENDARS',['2020-03..2024-11'])):
        for r in rngs:
            add('SAFE_CANONICAL','SAFE','COMPLIANT','VALID',_set(ready,('DATA_REQUIRED',0),{'DATASET':ds,'OBSERVABLE':'catalogued field','STATUS':'DATA_READY','LEGAL_RANGE':r}))
    for status in ('FEASIBILITY_REQUIRED','DATA_BLOCKED_PROVENANCE','DATA_BLOCKED_COST','DATA_BLOCKED_POINT_IN_TIME_SEMANTICS','DATA_BLOCKED_MISSING_OBSERVABLE'):
        for r in ('2018-01..2024-12','1998-01..2003-12','pre-2021'):
            c=_set(blocked,('DATA_REQUIRED',0,'STATUS'),status);c['DATA_STATUS']=status;c=_set(c,('DATA_REQUIRED',0,'LEGAL_RANGE'),r)
            add('SAFE_CANONICAL','SAFE','COMPLIANT','VALID',c)
    for ds in ('B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0','MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0'):
        c=_set(blocked,('DATA_REQUIRED',0),{'DATASET':ds,'OBSERVABLE':'snapshot field','STATUS':'DATA_BLOCKED_POINT_IN_TIME_SEMANTICS','LEGAL_RANGE':'per snapshot'})
        c['DATA_STATUS']='DATA_BLOCKED_POINT_IN_TIME_SEMANTICS';add('SAFE_CANONICAL','SAFE','COMPLIANT','VALID',c)
    two=copy.deepcopy(blocked);slot=two.pop('SLOT')
    two['DATA_REQUIRED']=[{'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'1m bars','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'},dict(blocked['DATA_REQUIRED'][0])]
    two['SLOT']=slot;add('SAFE_CANONICAL','SAFE','COMPLIANT','VALID',two)
    for nearest in ('D4','D4.LEAD_LAG_1DAY','B2-06','MARKET-03','H01'):
        add('SAFE_CANONICAL','SAFE','COMPLIANT','VALID',_set(ready,('NEAREST_TESTED_MECHANISM',),nearest))
    # 2. Boundary values that are safe.
    for r in ('1900-01..1900-01','2024-12..2024-12','1999-12..2000-01','pre-1901','pre-2024','2024-01..2024-12'):
        c=_set(blocked,('DATA_REQUIRED',0,'LEGAL_RANGE'),r);add('SAFE_BOUNDARY','SAFE','COMPLIANT','VALID',c)
    for grid,mv in (({'a':[1]},1),({'a':list(range(10)),'b':list(range(10))},100),({'a':[0.5,1.5]},2),({'a':['x','y','z']},3)):
        add('SAFE_BOUNDARY','SAFE','COMPLIANT','VALID',_set(ready,('SEARCH_SURFACE',),{'PARAMETERS':grid,'MAX_VARIANTS':mv}))
    for v in (2024,2019,1999,2000,2048,2100,20250,12025):
        add('SAFE_BOUNDARY','SAFE','COMPLIANT','VALID',_set(ready,('SEARCH_SURFACE',),{'PARAMETERS':{'bucket':[v]},'MAX_VARIANTS':1}),note='non-protected number')
    # 3. Legitimate point-in-time "current/latest" wording outside scope fields.
    for field,text in (('NO_LOOKAHEAD_RULE','Use the latest bar closed at or before decision T.'),('NO_LOOKAHEAD_RULE','Features use only the current and prior closed bars.'),
                       ('OBSERVABLE','Close location within the current range of the session'),('CAUSAL_OR_STRUCTURAL_STORY','Dealers hedge against the current market regime.'),
                       ('MAIN_CONFOUNDERS','Current volatility level and weekday mix'),('FUNCTION','Compare the current period volatility to the prior period'),
                       ('MECHANISM','Latest quotes at T versus stale quotes'),('BASELINE_OR_NULL','Null reshuffles the latest completed session labels')):
        add('SAFE_LEGIT_WORDING','SAFE','COMPLIANT','VALID',_set(ready,(field,),text))
    # 4. Semantically wrong but contract-compliant (red team's job, not intake's).
    for field,text in (('NO_LOOKAHEAD_RULE','Use the close of bar T+1 as a predictor at T.'),('FUNCTION','Regress the 4h return on the next bar direction.'),
                       ('FALSIFIER','Any positive rank correlation confirms the mechanism.'),('BASELINE_OR_NULL','No null; compare with intuition.')):
        add('SEMANTIC_ERROR','SEMANTIC_ERROR','COMPLIANT','VALID',_set(ready,(field,),text),note='intake cannot judge meaning; red team must')
    # 5. Protected-year references (unsafe) in every text field and several forms.
    forms=('in 2025','during 2026','2025-2026 holdout','FY25 results','the 2025 halving aftermath',"returns in '26",'twenty twenty-five outcomes','2026-03 onward')
    for field in TEXT_TARGETS:
        for form in rng.sample(forms,3):
            add('UNSAFE_PROTECTED_YEAR','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,(field,),'Evaluate '+form))
    for v in (2025,2026,2025.0):
        add('UNSAFE_PROTECTED_YEAR','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('SEARCH_SURFACE',),{'PARAMETERS':{'end_year':[2024,v]},'MAX_VARIANTS':2}))
    add('UNSAFE_PROTECTED_YEAR','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('SEARCH_SURFACE',),{'PARAMETERS':{'window_2026':[1]},'MAX_VARIANTS':1}),note='year in a key')
    for ds in ('BTC_TRADES_2025','protected_2025_2026','PROTECTED-2025-2026','PROTECTED_2025_2026'):
        add('UNSAFE_PROTECTED_SOURCE','UNSAFE','VIOLATING','HARD_FAIL',_set(blocked,('DATA_REQUIRED',0,'DATASET'),ds))
    # 6. Exclusion statements that name the years: semantically safe, but the V02 rule forbids naming them.
    for text in ('No 2025/2026 data are permitted.','Never use 2025 or 2026 bars.','Only pre-2025 information may be used.','Data from 2025-2026 is excluded.'):
        add('SAFE_BUT_NAMES_PROTECTED_YEAR','SAFE','VIOLATING','HARD_FAIL',_set(ready,('NO_LOOKAHEAD_RULE',),text),note='stated rule: never write the years')
    # 7. Open-ended / post-2024 windows (unsafe) in several fields.
    for phrase in ('through today','through present','until present','up to now','open-ended','post-2024','after 2024','since 2024','2024+','2024 onward','2024 onwards','2024 and later','2024-present','year after 2024','2024-07 onward','beyond 2024'):
        field=rng.choice(('HORIZON','PRIMARY_TARGET','OBSERVABLE','FUNCTION','NO_LOOKAHEAD_RULE','BASELINE_OR_NULL'))
        add('UNSAFE_OPEN_ENDED','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,(field,),'Returns measured '+phrase))
    # 8. Recency words in scope fields (unsafe window ambiguity).
    for field,text in (('HORIZON','current session'),('PRIMARY_TARGET','latest return'),('PRIMARY_TARGET','live funding change'),('HORIZON','real-time')):
        add('UNSAFE_SCOPE_RECENCY','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,(field,),text))
    for text in ('current closes','latest data','today order book'):
        add('UNSAFE_SCOPE_RECENCY','UNSAFE','VIOLATING','HARD_FAIL',_set(blocked,('DATA_REQUIRED',0,'OBSERVABLE'),text))
    # 9. Ranges: protected or post-2024 ends (unsafe), and malformed/non-canonical forms.
    for r in ('2020-01..2025-06','2024-06..2026-01','2025-01..2025-12','pre-2026','pre-2025','2020..2025','2023-01..2027-01'):
        add('UNSAFE_RANGE','UNSAFE','VIOLATING','HARD_FAIL',_set(blocked,('DATA_REQUIRED',0,'LEGAL_RANGE'),r))
    for r in ('2020-01 to 2024-12','Jan 2020 - Dec 2024','2020..2024','2020-01..2024-12 (requested)','2020-01-01..2024-12-31','2024-12..2020-01','2020-13..2024-12','2020-00..2024-12',
              'pre 2020','PER SNAPSHOT','','  2020-01..2024-12','2020-01..2024-12;','latest available','current'):
        safe='SAFE' if r in ('2020-01 to 2024-12','Jan 2020 - Dec 2024','2020..2024','2020-01..2024-12 (requested)','2020-01-01..2024-12-31','pre 2020','  2020-01..2024-12','2020-01..2024-12;') else 'UNSAFE'
        add('NONCANONICAL_RANGE',safe,'VIOLATING','HARD_FAIL',_set(blocked,('DATA_REQUIRED',0,'LEGAL_RANGE'),r))
    # 10. Catalog consistency.
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('DATA_REQUIRED',0),{'DATASET':'MARKET_06_OKX_BINANCE_FEASIBILITY_V0','OBSERVABLE':'aligned closes','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}),note='wider than catalog')
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('DATA_REQUIRED',0,'LEGAL_RANGE'),'per snapshot'),note='per snapshot on bounded catalog dataset')
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(blocked,('DATA_REQUIRED',0,'LEGAL_RANGE'),'per snapshot'),note='per snapshot on unknown dataset')
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('DATA_REQUIRED',0,'DATASET'),'GATE_UNLISTED_READY'),note='off-catalog DATA_READY')
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('DATA_REQUIRED',0),{'DATASET':'B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0','OBSERVABLE':'oi','STATUS':'DATA_READY','LEGAL_RANGE':'per snapshot'}),note='blocked catalog claimed ready')
    add('CATALOG','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('DATA_REQUIRED',0,'LEGAL_RANGE'),'2019-01..2024-12'),note='starts before catalog')
    # 11. Trading/score claims.
    for field,text in (('NAME','Validated trading edge from close location'),('FUNCTION','Emit a buy signal when close location is high'),('WHAT_POSITIVE_WOULD_TEACH','Guaranteed profit regime'),('MECHANISM','Sell-signal cascade')):
        add('UNSAFE_CLAIM','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,(field,),text))
    for key in ('EXPECTED_ALPHA','expected-probability-of-success','P_SUCCESS','Expected PnL'):
        add('UNSAFE_CLAIM','UNSAFE','VIOLATING','HARD_FAIL',_set(ready,('SEARCH_SURFACE',),{'PARAMETERS':{key:[1]},'MAX_VARIANTS':1}))
    # 12. Malformed / hidden-rule violations (safe content, broken contract).
    def mal(label,fn,safety='SAFE'):
        c=copy.deepcopy(ready);fn(c);add('MALFORMED',safety,'VIOLATING','HARD_FAIL',c,note=label)
    mal('missing field',lambda c:c.pop('FALSIFIER'))
    mal('extra field',lambda c:c.update(STREAM='EXECUTABLE_NOW'))
    mal('empty text',lambda c:c.update(BASELINE_OR_NULL=''))
    mal('whitespace text',lambda c:c.update(FALSIFIER='   '))
    mal('overlong text',lambda c:c.update(MECHANISM='x'*12001))
    mal('non-string text',lambda c:c.update(HORIZON=4))
    mal('protected flag true',lambda c:c.update(PROTECTED_DATA_REQUIREMENT=True),'UNSAFE')
    mal('protected flag string',lambda c:c.update(PROTECTED_DATA_REQUIREMENT='false'))
    mal('unknown family',lambda c:c.update(MECHANISM_FAMILY='Z'))
    mal('nearest free text',lambda c:c.update(NEAREST_TESTED_MECHANISM='the D2 card'))
    mal('data rows not list',lambda c:c.update(DATA_REQUIRED={'DATASET':'x'}))
    mal('data rows empty',lambda c:c.update(DATA_REQUIRED=[]))
    mal('data rows 21',lambda c:c.update(DATA_REQUIRED=[dict(c['DATA_REQUIRED'][0]) for _ in range(21)]))
    mal('row extra key',lambda c:c['DATA_REQUIRED'][0].update(NOTE='coverage unverified'))
    mal('row missing key',lambda c:c['DATA_REQUIRED'][0].pop('OBSERVABLE'))
    mal('row status unknown',lambda c:c['DATA_REQUIRED'][0].update(STATUS='MAYBE'))
    mal('aggregate absent',lambda c:c.update(DATA_STATUS='FEASIBILITY_REQUIRED'))
    mal('aggregate not in taxonomy',lambda c:c.update(DATA_STATUS='READY-ISH'))
    mal('max variants 0',lambda c:c['SEARCH_SURFACE'].update(MAX_VARIANTS=0))
    mal('max variants 101',lambda c:c['SEARCH_SURFACE'].update(MAX_VARIANTS=101))
    mal('max variants string',lambda c:c['SEARCH_SURFACE'].update(MAX_VARIANTS='2'))
    mal('product exceeds',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={'a':[1,2,3],'b':[1,2,3]},MAX_VARIANTS=8))
    mal('product 125',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={'a':[1,2,3,4,5],'b':[1,2,3,4,5],'c':[1,2,3,4,5]},MAX_VARIANTS=100))
    mal('empty parameters',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={}))
    mal('empty value list',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={'a':[]}))
    mal('boolean value',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={'a':[True]}))
    mal('nan value',lambda c:c['SEARCH_SURFACE'].update(PARAMETERS={'a':[float('nan')]}))
    mal('missing observables not list',lambda c:c.update(MISSING_OBSERVABLES='none'))
    def blocked_mal(label,fn):
        c=copy.deepcopy(blocked);slot=c.pop('SLOT');fn(c);c['SLOT']=slot;add('MALFORMED','SAFE','VIOLATING','HARD_FAIL',c,note=label)
    blocked_mal('blocked without missing observable',lambda c:c.update(MISSING_OBSERVABLES=[]))
    blocked_mal('blocked with gap NONE',lambda c:c.update(DATA_GAP_CLASS='NONE'))
    blocked_mal('ready aggregate over blocked row',lambda c:c.update(DATA_STATUS='DATA_READY'))
    # 13. Slot identity violations.
    add('SLOT','SAFE','VIOLATING','HARD_FAIL',_set(ready,('CANDIDATE_ID',),'C102'),note='wrong id for slot')
    add('SLOT','SAFE','VIOLATING','HARD_FAIL',_set(ready,('CANDIDATE_ID',),'c101'),note='malformed id')
    add('SLOT','SAFE','VIOLATING','HARD_FAIL',_set(ready,('MECHANISM_FAMILY',),'A'),note='family differs from slot')
    add('SLOT','SAFE','VIOLATING','HARD_FAIL',_set(ready,('INFORMATION_SOURCE',),'OPTIONS'),note='source differs from slot')
    return items

def round_cases():
    """Round-level faults: (label, cards_fn(slot_cards)->cards, expected per-slot states)."""
    return [
        ('exact round',lambda cs:cs,['VALID']*10),
        ('missing card',lambda cs:cs[:-1],['VALID']*9+['HARD_FAIL']),
        ('extra card',lambda cs:cs+[dict(cs[0],CANDIDATE_ID='C999')],['VALID']*10),
        ('duplicate id',lambda cs:[cs[0],dict(cs[0])]+cs[2:],['HARD_FAIL','HARD_FAIL']+['VALID']*8),
        ('reordered',lambda cs:list(reversed(cs)),['VALID']*10),
        ('non-object entry',lambda cs:['oops']+cs[1:],['HARD_FAIL']+['VALID']*9),
        ('empty round',lambda cs:[],['HARD_FAIL']*10),
    ]
