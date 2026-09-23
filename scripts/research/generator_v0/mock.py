"""Synthetic infrastructure fixtures, not proposed research or scientific evidence."""
from .context import canonical,digest
from .schema import signature
from .roles import NOVELTY_DIMENSIONS,RED_DIMENSIONS,FEAS_DIMENSIONS

# Canonical V02 LEGAL_RANGE inside each catalog dataset's own bounds.
FIXTURE_RANGES={'MARKET_06_OKX_BINANCE_FEASIBILITY_V0':'2022-01..2024-12','D2_BITMEX_PRE2020_XBTUSD':'pre-2020'}
SOURCE_CLASSES=('KLINES','CROSS_VENUE','PRE2020_SURFACE','OFFICIAL_CALENDAR','CROSS_SECTIONAL_PANEL','OPTIONS','ONCHAIN','ORDER_BOOK')
DATASETS=('CORE_BTC_BINANCE_V0','MARKET_06_OKX_BINANCE_FEASIBILITY_V0','D2_BITMEX_PRE2020_XBTUSD','D11_FOMC_OFFICIAL_V0','SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0','SYNTHETIC_OPTIONS_ARCHIVE','SYNTHETIC_ONCHAIN_ARCHIVE','SYNTHETIC_ORDERBOOK_ARCHIVE')
MECHANISMS=(
 'BTC-ETH relative structure','Volatility-scale state','Leverage crowding','Future-informed synthetic state','Depth observability check',
 'Synthetic settlement synchronization','Synthetic validator congestion','Synthetic queue replenishment',
 'Synthetic seasonal phase coupling','Synthetic venue outage transmission','Synthetic prehistory session segmentation','Synthetic announcement-time dispersion',
 'Synthetic listing-cohort turnover','Synthetic variance-term curvature','Synthetic fee-pressure clustering','Synthetic cancellation asymmetry',
 'Synthetic volume-clock entropy','Synthetic auction discontinuity','Synthetic historical fragmentation','Synthetic calendar overlap',
 'Synthetic breadth concentration','Synthetic expiry concentration','Synthetic transfer-network topology','Synthetic depth recovery',
 'Synthetic trade-size discreteness','Synthetic venue-clock drift','Synthetic timestamp quantization','Synthetic scheduled-pause effects',
 'Synthetic cohort membership instability','Synthetic strike-density geometry','Synthetic address age mixture','Synthetic hidden-depth observability',
 'Synthetic count-volume decoupling','Synthetic exchange-status latency','Synthetic session-boundary topology','Synthetic calendar revision visibility',
 'Synthetic listing-name aliasing','Synthetic options quote synchronization','Synthetic finality-delay dispersion','Synthetic queue-position survival')

def slot_plan(size=40):
    return [{'CANDIDATE_ID':f'C{i+1:03}','MECHANISM_FAMILY':chr(65+i%10) if i<size-10 else 'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':SOURCE_CLASSES[i%8]} for i in range(size)]

def fixture(slot,contexts):
    i=int(slot['CANDIDATE_ID'][1:])-1;j=i%8
    status='DATA_READY' if j<5 else ('FEASIBILITY_REQUIRED','DATA_BLOCKED_PROVENANCE','DATA_BLOCKED_MISSING_OBSERVABLE')[j-5]
    if i==21:status='DATA_BLOCKED_COST'
    if i==29:status='DATA_BLOCKED_POINT_IN_TIME_SEMANTICS'
    card={k:'Synthetic test fixture; no scientific evidence.' for k in contexts.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']}
    card.update(slot)
    card.update(NAME='Infrastructure fixture: '+(MECHANISMS[i%len(MECHANISMS)]+(' variant fixture '+str(i+1) if i>=len(MECHANISMS) else '')),MECHANISM=(MECHANISMS[i%len(MECHANISMS)]+(' variant fixture '+str(i+1) if i>=len(MECHANISMS) else '')),
        CAUSAL_OR_STRUCTURAL_STORY='Synthetic structural pathway specified for exercising the review pipeline.',
        OBSERVABLE='Synthetic observable '+str(i+1),FUNCTION='Synthetic comparison function '+str(i+1),PRIMARY_TARGET='Synthetic future response '+str(i+1),HORIZON='6h',
        BASELINE_OR_NULL='Stratum-preserving synthetic permutation null',FALSIFIER='No separation from the declared synthetic null distribution',
        NEAREST_TESTED_MECHANISM='NONE',MECHANISM_DISTANCE_ARGUMENT='Different synthetic observable and function.',WHY_NOT_A_RESCUE='A distinct synthetic structural pathway.',
        SEARCH_SURFACE={'PARAMETERS':{'horizon_hours':[6],'variant':['fixed']},'MAX_VARIANTS':1},
        MAIN_CONFOUNDERS='Calendar composition, missingness, common factors.',NO_LOOKAHEAD_RULE='Every predictor must have an observable public timestamp at or before decision T.',
        DATA_REQUIRED=[{'DATASET':DATASETS[j],'OBSERVABLE':'Synthetic observable '+str(i+1),'STATUS':status,'LEGAL_RANGE':FIXTURE_RANGES.get(DATASETS[j],'2020-01..2024-12')}],
        DATA_STATUS=status,MISSING_OBSERVABLES=[] if status=='DATA_READY' else ['Synthetic observable '+str(i+1)+' with timestamp and archive provenance'],
        DATA_GAP_CLASS='NONE' if status=='DATA_READY' else SOURCE_CLASSES[j],EXPECTED_IMPLEMENTATION_COST='Bounded synthetic fixture computation',
        WHAT_POSITIVE_WOULD_TEACH='Distinguish the specified synthetic structural pathway.',WHAT_NULL_WOULD_ELIMINATE='Eliminate this synthetic mechanism formulation.',EXPECTED_INFORMATION_GAIN='Separate structurally different explanations.',PROTECTED_DATA_REQUIREMENT=False)
    if i==0:card.update(NEAREST_TESTED_MECHANISM='D4',FUNCTION='Rolling 90d correlation range')
    if i==1:card.update(NEAREST_TESTED_MECHANISM='D2',FUNCTION='RV threshold neighbor')
    if i==2:card.update(NEAREST_TESTED_MECHANISM='B2-06',FUNCTION='Unresolved original crowding card')
    if i==3:card['NO_LOOKAHEAD_RULE']='Use a future observation as the predictor at T.'
    if i==4:card['OBSERVABLE']='L2 depth from daily kline catalog'
    return card

class MockResponder:
    def __init__(self,contexts):self.c=contexts
    def __call__(self,request):
        role=request['role'];ctx=request['context']
        if role=='GENERATOR':return canonical({'CANDIDATES':[fixture(s,self.c) for s in request['parameters']['slots']]})
        if role=='SELECTOR':
            j=ctx['SELECTION_JUDGMENTS']
            order=sorted(j,key=lambda k:tuple(-j[k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))
            return canonical({'ORDERED_CANDIDATE_IDS':order})
        card=ctx['CANDIDATE'];score=1+int(digest(card)[:4],16)%3
        if role=='NOVELTY_CRITIC':
            relations=[]
            for k,row in self.c.rows.items():
                if row['STATE']=='PARTIAL_OR_MIXED':continue
                rel='ORTHOGONAL_MECHANISM'
                if k=='D4.ROLLING_CORRELATION_90D' and card['FUNCTION']=='Rolling 90d correlation range':rel='EXACT_DUPLICATE'
                if k=='D2' and card['FUNCTION']=='RV threshold neighbor':rel='PARAMETER_NEIGHBOR'
                if k=='B2-06' and card['FUNCTION']=='Unresolved original crowding card':rel='EXACT_DUPLICATE'
                relations.append({'SIGNATURE_ID':k,'RELATION':rel})
            others=[{'CANDIDATE_ID':x['CANDIDATE_ID'],'RELATION':'EXACT_DUPLICATE' if signature(x)==signature(card) else 'ORTHOGONAL_MECHANISM'} for x in ctx['CURRENT_BATCH_SIGNATURES'] if x['CANDIDATE_ID']!=card['CANDIDATE_ID']]
            return canonical({'PRIOR_RELATIONS':relations,'BATCH_RELATIONS':others,'JUDGMENTS':{k:score for k in NOVELTY_DIMENSIONS}})
        if role=='FEASIBILITY_CRITIC':
            ready=card['DATA_STATUS']=='DATA_READY'
            return canonical({'DATA_STATUS':card['DATA_STATUS'],'CHECKS':{'OBSERVABLE_SUPPORTED':ready and 'L2 depth' not in card['OBSERVABLE'],'LEGAL_RANGE':True,'POINT_IN_TIME':ready,'PROVENANCE':ready,'BLOCKER_RESOLVED':True},'JUDGMENTS':{k:score for k in FEAS_DIMENSIONS},'FEASIBILITY':3 if ready else 1,'CHEAPNESS':score})
        if role=='RED_TEAM':return canonical({'CHECKS':{'NO_LOOKAHEAD':'future observation as the predictor' not in card['NO_LOOKAHEAD_RULE'],'CAUSALITY':True,'FALSIFIABLE':True,'BOUNDED_SEARCH':True,'CONFOUNDING_ADDRESSED':True,'NO_TRADING_CLAIM':True},'JUDGMENTS':{k:score for k in RED_DIMENSIONS}})
        raise ValueError(role)
