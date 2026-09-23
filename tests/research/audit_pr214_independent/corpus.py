"""Independent synthetic cards for PR #214 verification.

Labels are assigned from the published V02 rule *text* (principle + listed
phrases), not by running the validator and copying its answer. Wording is
original to this verifier file; it is not taken from the implementer gate
corpus or from first-shadow v5/v6/v7 strings.
"""
from __future__ import annotations
import copy

SLOT={'CANDIDATE_ID':'C401','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':'KLINES'}

# Rule-text principle: no open-ended / post-2024 window, and never name 2025/2026.
# Listed phrases are the implementer's explicit list; paraphrases test whether
# the principle is enforced or only the list.
LISTED_OPEN_ENDED=(
    'through today','through present','until present','up to now','up to the present',
    'open-ended','open ended','post-2024','after 2024','since 2024','beyond 2024',
    'later than 2024','2024+','2024 onward','2024 onwards','2024 and later',
    '2024-present','year after 2024',
)
LISTED_RECENCY=('current','latest','live','real-time','realtime','today','now','ongoing','up-to-date')
LISTED_TRADING=('expected alpha','probability of success','guaranteed profit','validated trading edge','buy signal','sell signal')

def seed():
    return {
        'CANDIDATE_ID':'C401',
        'NAME':'Audit probe: lattice occupancy after a scheduled venue pause',
        'MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL',
        'MECHANISM':'Occupancy of resting size in a discrete price lattice once a scheduled halt lifts',
        'CAUSAL_OR_STRUCTURAL_STORY':'A halt freezes the lattice; the first post-halt replenishment is a structural restart, not a continuation of the pre-halt book.',
        'INFORMATION_SOURCE':'KLINES',
        'OBSERVABLE':'Completed 1-minute bar high, low and close after the halt timestamp',
        'FUNCTION':'Compare occupancy reconstruction error against a halt-stratified permutation null',
        'PRIMARY_TARGET':'Absolute 6-hour log move starting at the first fully observed bar after the halt',
        'HORIZON':'6h',
        'BASELINE_OR_NULL':'Halt-stratified permutation of occupancy increments, weekday mix held fixed',
        'FALSIFIER':'Reconstruction error sits inside the null band on both halves of the declared window',
        'NEAREST_TESTED_MECHANISM':'NONE',
        'MECHANISM_DISTANCE_ARGUMENT':'Uses halt-bounded lattice restart rather than a rolling volatility state.',
        'WHY_NOT_A_RESCUE':'No listed signature is a halt-bounded lattice occupancy restart.',
        'SEARCH_SURFACE':{'PARAMETERS':{'halt_min_bars':[3,5],'horizon_hours':[6]},'MAX_VARIANTS':2},
        'MAIN_CONFOUNDERS':'Calendar clustering of halts and common-factor bursts at the reopen',
        'NO_LOOKAHEAD_RULE':'Every predictor bar must have a public close at or before decision T.',
        'DATA_REQUIRED':[{'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'1-minute OHLC of completed bars','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}],
        'DATA_STATUS':'DATA_READY',
        'MISSING_OBSERVABLES':[],
        'DATA_GAP_CLASS':'NONE',
        'EXPECTED_IMPLEMENTATION_COST':'One bounded pass over catalogued bars inside the declared window',
        'WHAT_POSITIVE_WOULD_TEACH':'Halt-bounded lattice restart is a distinct structural pathway.',
        'WHAT_NULL_WOULD_ELIMINATE':'Occupancy restart as a standalone explanation of the post-halt move.',
        'EXPECTED_INFORMATION_GAIN':'Separates halt restart from ordinary volatility clustering.',
        'PROTECTED_DATA_REQUIREMENT':False,
    }

def _item(cid,category,spec_intent,card,slot=None,note=''):
    card=copy.deepcopy(card)
    slot=copy.deepcopy(slot or SLOT)
    return {'ID':cid,'CATEGORY':category,'SPEC_INTENT':spec_intent,'CARD':card,'SLOT':slot,'NOTE':note}

def _put(card,*path,value):
    c=copy.deepcopy(card);cur=c
    for k in path[:-1]:
        if isinstance(cur,list):cur=cur[k]
        else:cur=cur[k]
    if isinstance(cur,list):cur[path[-1]]=value
    else:cur[path[-1]]=value
    return c

def build():
    """>=200 independently labelled cards. SPEC_INTENT is ADMIT or QUARANTINE."""
    items=[];n=[0]
    def add(category,intent,card,slot=None,note=''):
        n[0]+=1
        items.append(_item('IV'+str(n[0]).zfill(3),category,intent,card,slot,note))
    ready=seed()
    blocked=_put(ready,'DATA_REQUIRED',0,value={'DATASET':'AUDIT_LATTICE_ARCHIVE','OBSERVABLE':'halt occupancy counts','STATUS':'DATA_BLOCKED_MISSING_OBSERVABLE','LEGAL_RANGE':'2021-03..2024-06'})
    blocked=_put(blocked,'DATA_STATUS',value='DATA_BLOCKED_MISSING_OBSERVABLE')
    blocked=_put(blocked,'MISSING_OBSERVABLES',value=['halt occupancy counts with first-seen timestamps'])
    blocked=_put(blocked,'DATA_GAP_CLASS',value='HALT_OCCUPANCY')
    blocked=_put(blocked,'INFORMATION_SOURCE',value='ORDER_BOOK')

    # --- 1. Canonical ADMIT (principle: legal grammar, no protected years, listed phrases absent)
    for rng in ('2020-01..2024-12','2021-06..2023-02','2024-12..2024-12','2020-01..2020-01','2022-01..2022-12'):
        add('CANONICAL','ADMIT',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value=rng),note='inside CORE_BTC catalog')
    for rng in ('pre-2020','pre-2018','2016-01..2019-12'):
        add('CANONICAL','ADMIT',_put(ready,'DATA_REQUIRED',0,value={'DATASET':'D2_BITMEX_PRE2020_XBTUSD','OBSERVABLE':'5m XBTUSD','STATUS':'DATA_READY','LEGAL_RANGE':rng}),note='inside BitMEX pre-2020 catalog')
    for ds,rng in (('CORE_ETH_BINANCE_V0','2020-01..2024-12'),('MARKET_06_OKX_BINANCE_FEASIBILITY_V0','2022-01..2024-12'),
                   ('D2_BITMEX_PRE2020_XBTUSD','pre-2020'),('D11_FOMC_OFFICIAL_V0','2020-01..2024-12'),
                   ('SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0','2019-12..2024-12'),('STATUTORY_DST_CALENDARS','2020-03..2024-11')):
        add('CANONICAL','ADMIT',_put(ready,'DATA_REQUIRED',0,value={'DATASET':ds,'OBSERVABLE':'catalogued field','STATUS':'DATA_READY','LEGAL_RANGE':rng}))
    add('CANONICAL','ADMIT',_put(ready,'DATA_REQUIRED',0,value={'DATASET':'MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0','OBSERVABLE':'hourly close','STATUS':'DATA_READY','LEGAL_RANGE':'per snapshot'}))
    for status in ('FEASIBILITY_REQUIRED','DATA_BLOCKED_PROVENANCE','DATA_BLOCKED_COST','DATA_BLOCKED_POINT_IN_TIME_SEMANTICS','DATA_BLOCKED_MISSING_OBSERVABLE'):
        c=_put(blocked,'DATA_REQUIRED',0,'STATUS',value=status);c=_put(c,'DATA_STATUS',value=status)
        add('CANONICAL','ADMIT',c,slot={'CANDIDATE_ID':'C401','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':'ORDER_BOOK'})
    for near in ('NONE','H01','D2','B2-06'):
        add('CANONICAL','ADMIT',_put(ready,'NEAREST_TESTED_MECHANISM',value=near))
    add('CANONICAL','ADMIT',_put(ready,'NO_LOOKAHEAD_RULE',value='Use only the latest bar that has already closed at or before T.'))
    add('CANONICAL','ADMIT',_put(ready,'CAUSAL_OR_STRUCTURAL_STORY',value='Point-in-time: the latest completed observation available as of T, never a later print.'))

    # --- 2. Listed-phrase QUARANTINE (rule text names these strings)
    for phrase in LISTED_OPEN_ENDED:
        add('LISTED_OPEN_ENDED','QUARANTINE',_put(ready,'MECHANISM',value='Occupancy window '+phrase+' is the object of study.'),note=phrase)
    for word in LISTED_RECENCY:
        add('LISTED_RECENCY','QUARANTINE',_put(ready,'HORIZON',value=word+' 6h'),note=word)
        add('LISTED_RECENCY','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'OBSERVABLE',value=word+' occupancy print'),note=word+' in DATA_REQUIRED.OBSERVABLE')
    for phrase in LISTED_TRADING:
        add('LISTED_TRADING','QUARANTINE',_put(ready,'WHAT_POSITIVE_WOULD_TEACH',value='This would be a '+phrase+'.'),note=phrase)
    add('LISTED_SCORE','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'EXPECTED_ALPHA':[1,2],'horizon_hours':[6]},'MAX_VARIANTS':2}))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'NO_LOOKAHEAD_RULE',value='Do not use 2025 bars.'))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'FALSIFIER',value='No separation in 2026.'))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'NAME',value='Audit probe for FY25 occupancy'))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'NAME',value='Audit probe for CY26 occupancy'))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'MECHANISM',value='twenty twenty-five occupancy restart'))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'year_mark':[2025],'horizon_hours':[6]},'MAX_VARIANTS':2}))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'year_mark':[2026.0],'horizon_hours':[6]},'MAX_VARIANTS':2}))
    add('LISTED_YEAR','QUARANTINE',_put(ready,'WHY_NOT_A_RESCUE',value="Do not extend into '25."))
    add('PROTECTED_FLAG','QUARANTINE',_put(ready,'PROTECTED_DATA_REQUIREMENT',value=True))
    add('PROTECTED_SOURCE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'DATASET',value='PROTECTED_2025_2026'))
    add('READY_UNCATALOGUED','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'DATASET',value='NOT_A_CATALOG_KEY'))
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2020-01 to 2024-12'))
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2025-01..2025-12'))
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2020-01..2025-01'))
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2024-12..2020-01'))  # start after end; grammar principle
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='pre-2025'))
    add('LEGAL_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='per-snapshot'))
    add('CATALOG_RANGE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,value={'DATASET':'MARKET_06_OKX_BINANCE_FEASIBILITY_V0','OBSERVABLE':'aligned close','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}))
    add('PER_SNAPSHOT_MISUSE','QUARANTINE',_put(ready,'DATA_REQUIRED',0,value={'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'1m OHLC','STATUS':'DATA_READY','LEGAL_RANGE':'per snapshot'}))
    add('AGGREGATE','QUARANTINE',_put(_put(blocked,'DATA_STATUS',value='DATA_READY'),'DATA_REQUIRED',0,'STATUS',value='DATA_BLOCKED_MISSING_OBSERVABLE'))
    add('MISSING_OBS','QUARANTINE',_put(blocked,'MISSING_OBSERVABLES',value=[]))
    add('GAP_CLASS','QUARANTINE',_put(blocked,'DATA_GAP_CLASS',value='NONE'))
    add('SEARCH','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'horizon_hours':[6,12],'halt_min_bars':[3,5]},'MAX_VARIANTS':2}))
    add('TEXT','QUARANTINE',_put(ready,'FALSIFIER',value='   '))
    add('SCHEMA','QUARANTINE',{k:v for k,v in ready.items() if k!='FALSIFIER'})
    extra=copy.deepcopy(ready);extra['EXTRA_FIELD']='nope'
    add('SCHEMA','QUARANTINE',extra)
    add('SLOT','QUARANTINE',_put(ready,'CANDIDATE_ID',value='C999'))
    add('NEAREST','QUARANTINE',_put(ready,'NEAREST_TESTED_MECHANISM',value='NOT_A_SIGNATURE'))

    # --- 3. Principle paraphrases: SPEC says post-2024 / open window, listed phrases absent
    paraphrases=(
        ('post 2024','MECHANISM','Occupancy measured post 2024 is the object of study.'),
        ('thru today','MECHANISM','Occupancy measured thru today is the object of study.'),
        ('until now','MECHANISM','Occupancy measured until now is the object of study.'),
        ('til now','MECHANISM','Occupancy measured til now is the object of study.'),
        ('til present','MECHANISM','Occupancy measured til present is the object of study.'),
        ('present-day','MECHANISM','A present-day occupancy window is the object of study.'),
        ('after December 2024','MECHANISM','Occupancy after December 2024 is the object of study.'),
        ('calendar year following 2024','MECHANISM','Use the calendar year following 2024 as the sample end.'),
        ('the year after twenty twenty-four','MECHANISM','Sample end is the year after twenty twenty-four.'),
        ('from 2024-12 forward','MECHANISM','Window runs from 2024-12 forward without a stated stop.'),
        ('continuing past year-end 2024','MECHANISM','The window keeps continuing past year-end 2024.'),
        ('including next calendar year','HORIZON','6h including next calendar year'),
        ('open ended window hyphenless already listed as open ended','CAUSAL_OR_STRUCTURAL_STORY','Study an unbounded window with no stop date stated.'),
        ('no terminal month','CAUSAL_OR_STRUCTURAL_STORY','Legal coverage has no terminal month.'),
        ('through this morning','MECHANISM','Occupancy through this morning is the object of study.'),
        ('up until this moment','MECHANISM','Occupancy up until this moment is the object of study.'),
        ('fullwidth 2025','NAME','Audit probe year ２０２５ occupancy'),
        ('fullwidth 2026','FALSIFIER','No separation in ２０２６.'),
        ('homoglyph 2025','NAME','Audit probe year 2025'.replace('5','５')),
        ('cyrillic year words','MECHANISM','twenty‑twenty‑five occupancy restart'),  # non-breaking hyphen
        ('FY 2025 spelled','NAME','Audit probe for fiscal year two thousand twenty five'),
        ('end of next year after 2024','MECHANISM','Window ends at the end of next year after 2024.'),
        ('post-December-2024','MECHANISM','Occupancy post-December-2024 is in scope.'),
        ('2024/2025 boundary as words','MECHANISM','Coverage crosses the twenty-four / twenty-five boundary.'),
        ('trailing plus on 2024 with space','MECHANISM','Window is 2024 + onward without a stop.'),
        ('since December 2024','MECHANISM','Occupancy since December 2024 is in scope.'),
        ('from 2024-12 until further notice','MECHANISM','From 2024-12 until further notice.'),
        ('inclusive of all subsequent years','MECHANISM','Inclusive of all subsequent years after 2024.'),
        ('CY 25 with space','NAME','Audit probe for CY 25 occupancy'),  # listed regex wants cy + 2[56]
        ('apostrophe 25 spaced','NAME','Audit probe for year  25 occupancy'),
    )
    for note,field,text in paraphrases:
        add('PARAPHRASE', 'QUARANTINE', _put(ready,field,value=text), note=note)

    # Recency paraphrases in scope fields (principle: do not use recency; list is specific tokens)
    recency_para=(
        ('present','HORIZON','present 6h'),
        ('newest','PRIMARY_TARGET','newest halt response'),
        ('most recent','HORIZON','most recent 6h'),
        ('as-of-now','PRIMARY_TARGET','as-of-now halt response'),
        ('fresh','HORIZON','fresh 6h'),
        ('up to date hyphenless','PRIMARY_TARGET','up to date halt response'),
        ('right now','HORIZON','right now 6h'),
        ('currently','PRIMARY_TARGET','currently available halt response'),
    )
    for note,field,text in recency_para:
        add('RECENCY_PARAPHRASE','QUARANTINE',_put(ready,field,value=text),note=note)

    # Trading/success paraphrases
    for note,text in (
        ('alpha expected reversed','This would be an alpha expected improvement.'),
        ('edge that has been validated','This would be an edge that has been validated.'),
        ('signal to buy','This would be a signal to buy.'),
        ('profit that is guaranteed','This would be a profit that is guaranteed.'),
        ('success chance','This would raise the success chance of the trade.'),
        ('PnL forecast','This would be a PnL forecast.'),
    ):
        add('TRADING_PARAPHRASE','QUARANTINE',_put(ready,'WHAT_POSITIVE_WOULD_TEACH',value=text),note=note)

    # --- 4. Structural mutations (principle: 27 fields, types, counts)
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',value=[]))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',0,value={'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'x','STATUS':'DATA_READY'}))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'STATUS',value='NOT_A_STATUS'))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_STATUS',value='NOT_A_STATUS'))
    add('STRUCT','QUARANTINE',_put(ready,'MISSING_OBSERVABLES',value=['']))
    add('STRUCT','QUARANTINE',_put(ready,'MISSING_OBSERVABLES',value=[1]))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{},'MAX_VARIANTS':1}))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'h':[6]},'MAX_VARIANTS':0}))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'h':[6]},'MAX_VARIANTS':101}))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'h':['']},'MAX_VARIANTS':1}))
    add('STRUCT','QUARANTINE',_put(ready,'CANDIDATE_ID',value='401'))
    add('STRUCT','QUARANTINE',_put(ready,'CANDIDATE_ID',value='c401'))
    add('STRUCT','QUARANTINE',_put(ready,'MECHANISM_FAMILY',value='NOT_A_FAMILY'))
    add('STRUCT','QUARANTINE',_put(ready,'PROTECTED_DATA_REQUIREMENT',value=0))
    add('STRUCT','QUARANTINE',_put(ready,'PROTECTED_DATA_REQUIREMENT',value='false'))
    long_text='x'*12001
    add('STRUCT','QUARANTINE',_put(ready,'MECHANISM',value=long_text))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',value=[{'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'x','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}]*21))
    add('STRUCT','QUARANTINE',_put(ready,'LEGAL_RANGE_PLACE',value='nope') if False else _put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2020-13..2024-12'))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2019-00..2024-12'))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='1899-01..2024-12'))
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value='2024-12..2024-13'))
    # duplicate-looking search key that is a score alias
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'expected_pnl':[1],'h':[6]},'MAX_VARIANTS':2}))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value={'PARAMETERS':{'SUCCESS_PROBABILITY':['a']},'MAX_VARIANTS':1}))
    # wrong types
    add('STRUCT','QUARANTINE',_put(ready,'DATA_REQUIRED',value='not-a-list'))
    add('STRUCT','QUARANTINE',_put(ready,'SEARCH_SURFACE',value=['nope']))
    add('STRUCT','QUARANTINE',_put(ready,'MISSING_OBSERVABLES',value='x'))
    bad=copy.deepcopy(ready);bad['DATA_REQUIRED'][0]['LEGAL_RANGE']=None
    add('STRUCT','QUARANTINE',bad)
    bad=copy.deepcopy(ready);bad['NAME']=None
    add('STRUCT','QUARANTINE',bad)
    add('STRUCT','QUARANTINE',[])
    add('STRUCT','QUARANTINE','not-an-object')
    add('STRUCT','QUARANTINE',123)
    add('STRUCT','QUARANTINE',{'CANDIDATE_ID':'C401'})

    # More legal-range near-misses that the principle rejects
    for rng in ('2020/01..2024/12','2020.01..2024.12','2020-1..2024-12','2020-01...2024-12',
                'pre 2020','Pre-2020','PRE-2020','per Snapshot','Per snapshot',
                '2020-01..2024-12 ',' 2020-01..2024-12','2020-01–2024-12',
                '2015-01..2024-12 UTC','2020-01..2024-12 inclusive','to present',
                '2017-01..now','unbounded','open','2020-01..','..2024-12'):
        add('RANGE_NEARMISS','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value=rng),note=rng)

    # Extra independent near-misses so the corpus is not size-padded with clones of the implementer set.
    for i,text in enumerate((
        'Window continues after the 2024 boundary without naming later years.',
        'Sample includes every subsequent December after 2024-12.',
        'Coverage is left open on the right of 2024-12.',
        'Use whatever bars exist after the last catalogued December.',
        'No stop date is declared past the 2024 winter month.',
        'Extend the window whenever newer public bars appear.',
        'Keep appending months as they become public after 2024-12.',
        'The right edge of the window is defined as unbounded future time.',
        'Include the next two winters after 2024 without writing those year numbers.',
        'Treat 2024-12 as a start, not an end.',
    )):
        add('PARAPHRASE','QUARANTINE',_put(ready,'MECHANISM',value=text),note='open-right-'+str(i))
    for rng in ('2020-01..2024-12.','2020-01..2024-12\n','2020-01..2024-12\t','2020-01 .. 2024-12'):
        add('RANGE_NEARMISS','QUARANTINE',_put(ready,'DATA_REQUIRED',0,'LEGAL_RANGE',value=rng),note=repr(rng))
    assert len(items)>=200
    return items
