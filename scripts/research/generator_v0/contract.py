"""GENERATOR_CONTRACT_V02: the single authoritative card rule table.

The generator prompt's hard-rule block is rendered from RULES, and the
application validator dispatches on the same rule IDs. A test fails if a rule
has no check, a check has no rule, or the prompt omits a rule's text.

Rules marked DECODING are also enforced by the strict provider schema
(output_schemas.py). Every rule is re-checked here, because a fake or
non-conforming provider must still be quarantined, never trusted.

A card that violates any rule is quarantined as HARD_FAIL. It never aborts the
campaign (runner.py); batch-level stop conditions are separate.
"""
from __future__ import annotations
import math
import re
from .context import ContractError
from . import textnorm as tn

CONTRACT_ID='GENERATOR_CONTRACT_V02'
PROMPT_VERSION='generator-v0.2'
MAX_TEXT=12000
MAX_DATA_ROWS=20
MAX_VARIANTS_LIMIT=100
PROTECTED_END=(2024,12)
# Canonical LEGAL_RANGE grammar. Years 1900..2024 only, so a protected end month
# is not expressible at all. Strict-schema subset: no lookaround, no \d, no \b.
# Plain groups only: non-capturing groups are not assumed to be supported.
_YEAR=r'(19[0-9][0-9]|20[01][0-9]|202[0-4])'
_MONTH=r'(0[1-9]|1[0-2])'
LEGAL_RANGE_PATTERN=r'^('+_YEAR+'-'+_MONTH+r'\.\.'+_YEAR+'-'+_MONTH+'|pre-'+_YEAR+'|per snapshot)$'
PER_SNAPSHOT='per snapshot'

TEXT_FIELDS=('NAME','MECHANISM_FAMILY','MECHANISM','CAUSAL_OR_STRUCTURAL_STORY','INFORMATION_SOURCE','OBSERVABLE','FUNCTION','PRIMARY_TARGET','HORIZON','BASELINE_OR_NULL','FALSIFIER','NEAREST_TESTED_MECHANISM','MECHANISM_DISTANCE_ARGUMENT','WHY_NOT_A_RESCUE','MAIN_CONFOUNDERS','NO_LOOKAHEAD_RULE','DATA_GAP_CLASS','EXPECTED_IMPLEMENTATION_COST','WHAT_POSITIVE_WOULD_TEACH','WHAT_NULL_WOULD_ELIMINATE','EXPECTED_INFORMATION_GAIN')
DATA_FIELDS=('DATASET','OBSERVABLE','STATUS','LEGAL_RANGE')
SCOPE_FIELDS=('HORIZON','PRIMARY_TARGET')
SCOPE_DATA_FIELDS=('DATASET','OBSERVABLE')
FORBIDDEN_SCORE_KEYS=('EXPECTED_PROBABILITY_OF_SUCCESS','EXPECTED_ALPHA','EXPECTED_PNL','EXPECTED_PROFIT','SUCCESS_PROBABILITY','PROBABILITY_OF_SUCCESS','PROBABILITY_OF_POSITIVE_RESULT','P_SUCCESS')
RULES=(
    {'ID':'SCHEMA_FIELDS','ENFORCEMENT':'DECODING','TEXT':'Each card has exactly the 27 required schema fields and no others.'},
    {'ID':'SLOT_IDENTITY','ENFORCEMENT':'DECODING','TEXT':'Each card copies its slot CANDIDATE_ID, MECHANISM_FAMILY and INFORMATION_SOURCE exactly; there is exactly one card per supplied slot.'},
    {'ID':'TEXT_FIELDS','ENFORCEMENT':'VALIDATOR','TEXT':'Every free-text field is a nonempty string of at most 12000 characters.'},
    {'ID':'NEAREST_TESTED_MECHANISM','ENFORCEMENT':'DECODING','TEXT':'NEAREST_TESTED_MECHANISM is exactly one prior signature ID from BLIND_MECHANISM_MAP_V0 (or a listed sub-signature ID) or NONE.'},
    {'ID':'PROTECTED_FLAG','ENFORCEMENT':'DECODING','TEXT':'PROTECTED_DATA_REQUIREMENT is false.'},
    {'ID':'NO_PROTECTED_YEARS','ENFORCEMENT':'VALIDATOR','TEXT':'Never refer to any year after 2024, in any form: digits (including full-width or other scripts, spaced digits), words (two thousand twenty-five, twenty twenty-six), Roman numerals, or two-digit forms (FY25, Q1 26, year 26, apostrophe 26), not even to exclude it. Any 4-digit number from 2025 to 2099 in text counts as such a year; numeric JSON values 2025 and 2026 are forbidden. The protected boundary is enforced by the system; describe exclusions without naming those years.'},
    {'ID':'NO_OPEN_ENDED_WINDOW','ENFORCEMENT':'VALIDATOR','TEXT':'Every time window has an explicit end no later than 2024-12; write windows as YYYY-MM..YYYY-MM or from YYYY to YYYY. In every field: never put '+', '.join(tn.BEFORE_RELATIONS)+' before any year or year-month; never put '+', '.join(tn.AFTER_RELATIONS)+', -present or a trailing on right after a year; never write a year followed by and/or with '+', '.join(tn.AFTER_CONNECTED)+'; never follow '+', '.join(tn.EXTENSION_WORDS)+' with an open endpoint ('+', '.join(tn.OPEN_ENDPOINTS)+') or with '+', '.join(tn.UNANCHORED_ENDPOINTS)+' unless a point-in-time noun such as bar, close, decision or timestamp follows; never write open-ended, open on the right or no end, never put '+', '.join(tn.UNBOUNDED_WORDS[:-1])+' next to a time word, never put '+', '.join(tn.NOW_WINDOW_WORDS)+' right before a window, sample, period, range or data word, never use 2024 or a later year as the start of a window without an explicit end, never describe a sample that grows as newer data appears, and never put a relation word before the catalog boundary or coverage cutoff.'},
    {'ID':'SCOPE_NO_RECENCY','ENFORCEMENT':'VALIDATOR','TEXT':'In HORIZON, PRIMARY_TARGET and every DATA_REQUIRED DATASET and OBSERVABLE, do not use wall-clock recency words: '+', '.join(tn.RECENCY_WORDS)+'. Point-in-time wording anchored to the decision time elsewhere (for example the latest bar closed at or before T) is allowed.'},
    {'ID':'DATA_ROWS','ENFORCEMENT':'DECODING','TEXT':'DATA_REQUIRED is a list of 1 to 20 objects with exactly DATASET, OBSERVABLE, STATUS and LEGAL_RANGE; STATUS is a DATA_STATUS_TAXONOMY value.'},
    {'ID':'LEGAL_RANGE_GRAMMAR','ENFORCEMENT':'DECODING','TEXT':'LEGAL_RANGE is exactly one of: YYYY-MM..YYYY-MM, pre-YYYY, or per snapshot. Months are 01-12, the start is not after the end, and the end is no later than 2024-12. Put coverage or provenance doubts in STATUS and MISSING_OBSERVABLES, never in LEGAL_RANGE.'},
    {'ID':'CATALOG_RANGE','ENFORCEMENT':'VALIDATOR','TEXT':'For a DATASET that is a DATA_CATALOG_V0 key with a bounded catalog LEGAL_RANGE, the stated range lies inside the catalog range. per snapshot is used only for catalog datasets whose catalog LEGAL_RANGE is per snapshot.'},
    {'ID':'PROTECTED_SOURCE','ENFORCEMENT':'VALIDATOR','TEXT':'Never list the protected catalog entry, any dataset whose catalog STATUS is FORBIDDEN_HARD_FAIL, or any DATASET or OBSERVABLE containing the word protected.'},
    {'ID':'READY_REQUIRES_CATALOG','ENFORCEMENT':'VALIDATOR','TEXT':'A DATA_REQUIRED STATUS of DATA_READY is allowed only for a DATASET that is an exact DATA_CATALOG_V0 key whose catalog STATUS is DATA_READY.'},
    {'ID':'AGGREGATE_STATUS','ENFORCEMENT':'VALIDATOR','TEXT':'DATA_STATUS is one of the DATA_REQUIRED STATUS values, and it is DATA_READY only when every row is DATA_READY.'},
    {'ID':'MISSING_OBSERVABLES','ENFORCEMENT':'VALIDATOR','TEXT':'MISSING_OBSERVABLES is a list of nonempty strings; when any DATA_REQUIRED row is not DATA_READY it names at least one exact missing observable.'},
    {'ID':'DATA_GAP_CLASS','ENFORCEMENT':'VALIDATOR','TEXT':'DATA_GAP_CLASS is NONE only when every DATA_REQUIRED row is DATA_READY; otherwise it names the missing-data class.'},
    {'ID':'SEARCH_SURFACE','ENFORCEMENT':'VALIDATOR','TEXT':'SEARCH_SURFACE has PARAMETERS (each with a nonempty name and a nonempty list of explicit string or number values) and MAX_VARIANTS, an integer from 1 to 100 that is at least the product of the value-list lengths.'},
    {'ID':'NO_SCORE_FIELDS','ENFORCEMENT':'VALIDATOR','TEXT':'No key anywhere, including search parameter names, is a success, probability, alpha, profit or PnL score.'},
    {'ID':'NO_TRADING_CLAIM','ENFORCEMENT':'VALIDATOR','TEXT':'No trade instructions or success claims anywhere: never put the actions '+', '.join(tn.ACTION_WORDS)+' (any form) within three words of '+', '.join(tn.INSTRUCTION_WORDS)+', or right after '+', '.join(tn.INSTRUCTION_LEADS)+'; never put long or short right after '+', '.join(tn.POSITION_VERBS)+'; never put '+', '.join(tn.CLAIM_NOUNS)+' within five words of '+', '.join(tn.CLAIM_MODIFIERS)+'; never put '+', '.join(tn.SUCCESS_WORDS)+' within three words of '+', '.join(tn.CHANCE_WORDS)+'. Order-flow terms such as taker buy volume, sell-side imbalance or short interest are allowed.'},
)
RULE_IDS=tuple(r['ID'] for r in RULES)

BASE_PROMPT='''Return JSON with exactly CANDIDATES: one card for each supplied slot, keyed as the output schema requires. Propose bounded mechanistic questions, falsifiers and null models. Data-blocked ideas are wanted. No self-grading or success estimates. Use public-time semantics. Slot assignments are neutral batch-diversity instructions, not historical research evidence. No tools, market execution or acquisition.'''

def generator_prompt():
    lines=[BASE_PROMPT,'Hard rules. A card that breaks any rule is quarantined and does not reach review; the rest of the batch continues.']
    lines+=[str(i+1)+'. ['+r['ID']+'] '+r['TEXT'] for i,r in enumerate(RULES)]
    return '\n'.join(lines)

_LEGAL=re.compile(LEGAL_RANGE_PATTERN)

def text(value):
    return isinstance(value,str) and bool(value.strip()) and len(value)<=MAX_TEXT

def parse_legal_range(value):
    """Canonical V02 LEGAL_RANGE -> {'KIND','START','END'} or None."""
    if not isinstance(value,str) or not _LEGAL.fullmatch(value):return None
    if value==PER_SNAPSHOT:return {'KIND':'PER_SNAPSHOT'}
    if value.startswith('pre-'):
        y=int(value[4:]);return {'KIND':'BOUNDED','START':None,'END':(y-1,12)}
    a,b=value.split('..')
    start=(int(a[:4]),int(a[5:]));end=(int(b[:4]),int(b[5:]))
    if start>end:return None
    return {'KIND':'BOUNDED','START':start,'END':end}

def parse_catalog_range(value):
    """Frozen catalog LEGAL_RANGE forms (catalog data, not model output)."""
    if value==PER_SNAPSHOT:return {'KIND':'PER_SNAPSHOT'}
    if not isinstance(value,str):return None
    m=re.fullmatch(r'([0-9]{4})-([0-9]{2})\.\.([0-9]{4})-([0-9]{2})',value)
    if m:y1,m1,y2,m2=map(int,m.groups());return {'KIND':'BOUNDED','START':(y1,m1),'END':(y2,m2)}
    m=re.fullmatch(r'([0-9]{4})\.\.([0-9]{4})',value)
    if m:y1,y2=map(int,m.groups());return {'KIND':'BOUNDED','START':(y1,1),'END':(y2,12)}
    m=re.fullmatch(r'pre-([0-9]{4})',value)
    if m:return {'KIND':'BOUNDED','START':None,'END':(int(m.group(1))-1,12)}
    return None

def _strings(value,path='',numbers=True):
    """Yield (path,string) for every string key and value, and (unless numbers is
    False) numbers as strings. Numeric JSON values are judged by _numbers for years."""
    if isinstance(value,dict):
        for k,v in value.items():
            yield path+'.<key>',str(k)
            yield from _strings(v,path+'.'+str(k),numbers)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from _strings(v,path+'['+str(i)+']',numbers)
    elif isinstance(value,str):yield path,value
    elif numbers and isinstance(value,(int,float)) and not isinstance(value,bool):yield path,repr(value)

def _number_is_protected(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):return False
    return isinstance(value,(int,float)) and math.isfinite(value) and value in (2025,2026)

def _numbers(value):
    if isinstance(value,dict):
        for v in value.values():yield from _numbers(v)
    elif isinstance(value,list):
        for v in value:yield from _numbers(v)
    else:yield value

def _normalized_dataset(name):
    return re.sub(r'[^a-z0-9]','',tn.normalize_text(name))

def _check_schema_fields(card,ctx,slot):
    required=set(ctx.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS'])
    if set(card)!=required:return ['fields differ from the frozen 27-field schema']
    return []

def _check_slot_identity(card,ctx,slot):
    out=[]
    cid=card.get('CANDIDATE_ID')
    if not isinstance(cid,str) or not re.fullmatch(r'C[0-9]{3}',cid):out.append('candidate id must be C001..C999')
    if slot is not None:
        for k,v in slot.items():
            if card.get(k)!=v:out.append('slot '+k+' mismatch')
    if card.get('MECHANISM_FAMILY') not in set(ctx.families)|{'NEW_FAMILY_PROPOSAL'}:out.append('unknown family')
    return out

def _check_text_fields(card,ctx,slot):
    bad=[f for f in TEXT_FIELDS if not text(card.get(f))]
    return ['empty or malformed text field '+f for f in bad]

def nearest_mechanism_ids(ctx):
    return sorted(set(ctx.blind)|set(ctx.rows))+['NONE']

def _check_nearest(card,ctx,slot):
    return [] if card.get('NEAREST_TESTED_MECHANISM') in nearest_mechanism_ids(ctx) else ['NEAREST_TESTED_MECHANISM is not a prior signature ID or NONE']

def _check_protected_flag(card,ctx,slot):
    return [] if card.get('PROTECTED_DATA_REQUIREMENT') is False else ['PROTECTED_DATA_REQUIREMENT is not false']

PROTECTED_TEXT_YEARS=range(2025,2100)

def _check_no_protected_years(card,ctx,slot):
    hits=[p for p,v in _strings(card,numbers=False) if any(y in PROTECTED_TEXT_YEARS for y in tn.years_in(tn.normalize_text(v)))]
    hits+=['<number>' for v in _numbers(card) if _number_is_protected(v)]
    return ['protected year reference at '+hits[0]] if hits else []

def _check_open_ended(card,ctx,slot):
    for p,v in _strings(card):
        found=tn.temporal_violations(tn.normalize_text(v))
        if found:return ['open-ended or post-2024 window at '+p+' ('+found[0]+')']
    return []

def _scope_strings(card):
    for f in SCOPE_FIELDS:
        if isinstance(card.get(f),str):yield f,card[f]
    rows=card.get('DATA_REQUIRED')
    if isinstance(rows,list):
        for i,row in enumerate(rows):
            if isinstance(row,dict):
                for f in SCOPE_DATA_FIELDS:
                    if isinstance(row.get(f),str):yield 'DATA_REQUIRED['+str(i)+'].'+f,row[f]

def _check_scope_recency(card,ctx,slot):
    for p,v in _scope_strings(card):
        found=tn.recency_tokens(tn.normalize_text(v))
        if found:return ['recency word in scope field '+p+' ('+found[0]+')']
    return []

def _rows(card):
    rows=card.get('DATA_REQUIRED')
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_DATA_ROWS:return None
    if any(not isinstance(r,dict) or set(r)!=set(DATA_FIELDS) or any(not text(v) for v in r.values()) for r in rows):return None
    return rows

def _check_data_rows(card,ctx,slot):
    rows=_rows(card)
    if rows is None:return ['DATA_REQUIRED shape']
    tax=set(ctx.design['DATA_STATUS_TAXONOMY'])
    out=['DATA_REQUIRED STATUS not in taxonomy' for r in rows if r['STATUS'] not in tax]
    if card.get('DATA_STATUS') not in tax:out.append('DATA_STATUS not in taxonomy')
    return out

def _check_legal_range_grammar(card,ctx,slot):
    rows=_rows(card) or []
    return ['noncanonical LEGAL_RANGE' for r in rows if parse_legal_range(r['LEGAL_RANGE']) is None]

def _within(inner,outer):
    if inner['KIND']!='BOUNDED' or outer['KIND']!='BOUNDED':return False
    if inner['END']>outer['END']:return False
    if outer['START'] is not None and (inner['START'] is None or inner['START']<outer['START']):return False
    return True

def _check_catalog_range(card,ctx,slot):
    out=[]
    for r in _rows(card) or []:
        stated=parse_legal_range(r['LEGAL_RANGE'])
        if stated is None:continue
        if stated['KIND']=='BOUNDED' and stated['END']>PROTECTED_END:out.append('LEGAL_RANGE ends after 2024-12');continue
        known=ctx.catalog.get(r['DATASET'])
        catalog=parse_catalog_range(known.get('LEGAL_RANGE')) if known else None
        if stated['KIND']=='PER_SNAPSHOT':
            if catalog is None or catalog['KIND']!='PER_SNAPSHOT':out.append('per snapshot only for per-snapshot catalog datasets')
            continue
        if catalog is not None and catalog['KIND']=='BOUNDED' and not _within(stated,catalog):out.append('LEGAL_RANGE outside catalog range')
    return out

def _check_protected_source(card,ctx,slot):
    protected={_normalized_dataset(k) for k,v in ctx.catalog.items() if v.get('STATUS')=='FORBIDDEN_HARD_FAIL'}
    out=[]
    for r in _rows(card) or []:
        if _normalized_dataset(r['DATASET']) in protected:out.append('protected source')
        elif any('protected' in tn.tokens(tn.normalize_text(r[f])) for f in SCOPE_DATA_FIELDS):out.append('protected word in data row')
    return out

def _check_ready_catalog(card,ctx,slot):
    out=[]
    for r in _rows(card) or []:
        known=ctx.catalog.get(r['DATASET'])
        if r['STATUS']=='DATA_READY' and (known is None or known.get('STATUS')!='DATA_READY'):out.append('DATA_READY claimed for uncatalogued or not-ready dataset')
    return out

def _statuses(card):
    return {r['STATUS'] for r in _rows(card) or []}

def _check_aggregate(card,ctx,slot):
    s=_statuses(card)
    if not s:return []
    if card.get('DATA_STATUS') not in s:return ['DATA_STATUS absent from requirements']
    if card.get('DATA_STATUS')=='DATA_READY' and s!={'DATA_READY'}:return ['DATA_READY aggregate with blocked rows']
    return []

def _check_missing(card,ctx,slot):
    m=card.get('MISSING_OBSERVABLES')
    if not isinstance(m,list) or any(not text(x) for x in m):return ['MISSING_OBSERVABLES shape']
    s=_statuses(card)
    if s and s!={'DATA_READY'} and not m:return ['blocked card without a named missing observable']
    return []

def _check_gap_class(card,ctx,slot):
    s=_statuses(card)
    if s and s!={'DATA_READY'} and card.get('DATA_GAP_CLASS')=='NONE':return ['blocked card with DATA_GAP_CLASS NONE']
    return []

def _check_search_surface(card,ctx,slot):
    surf=card.get('SEARCH_SURFACE')
    if not isinstance(surf,dict) or set(surf)!={'PARAMETERS','MAX_VARIANTS'}:return ['SEARCH_SURFACE shape']
    mv=surf['MAX_VARIANTS']
    if type(mv) is not int or not 1<=mv<=MAX_VARIANTS_LIMIT:return ['MAX_VARIANTS outside 1..100']
    params=surf['PARAMETERS']
    if not isinstance(params,dict) or not params:return ['unstated search surface']
    n=1
    for k,values in params.items():
        if not text(k) or not isinstance(values,list) or not values:return ['parameter grid shape']
        if any(type(v) not in (str,int,float) or (type(v) is float and not math.isfinite(v)) or (type(v) is str and not v.strip()) for v in values):return ['parameter value']
        n*=len(values)
    return ['understated search surface'] if n>mv else []

def _keys(value):
    if isinstance(value,dict):
        for k,v in value.items():
            yield k
            yield from _keys(v)
    elif isinstance(value,list):
        for v in value:yield from _keys(v)

def _check_score_fields(card,ctx,slot):
    bad=[k for k in _keys(card) if re.sub(r'[^A-Z0-9]+','_',str(k).upper()).strip('_') in FORBIDDEN_SCORE_KEYS]
    return ['forbidden score field'] if bad else []

def _check_trading(card,ctx,slot):
    for p,v in _strings(card):
        found=tn.trade_violations(tn.normalize_text(v))
        if found:return ['trading or success claim at '+p+' ('+found[0]+')']
    return []

CHECKS={
    'SCHEMA_FIELDS':_check_schema_fields,'SLOT_IDENTITY':_check_slot_identity,'TEXT_FIELDS':_check_text_fields,
    'NEAREST_TESTED_MECHANISM':_check_nearest,'PROTECTED_FLAG':_check_protected_flag,'NO_PROTECTED_YEARS':_check_no_protected_years,
    'NO_OPEN_ENDED_WINDOW':_check_open_ended,'SCOPE_NO_RECENCY':_check_scope_recency,'DATA_ROWS':_check_data_rows,
    'LEGAL_RANGE_GRAMMAR':_check_legal_range_grammar,'CATALOG_RANGE':_check_catalog_range,'PROTECTED_SOURCE':_check_protected_source,
    'READY_REQUIRES_CATALOG':_check_ready_catalog,'AGGREGATE_STATUS':_check_aggregate,'MISSING_OBSERVABLES':_check_missing,
    'DATA_GAP_CLASS':_check_gap_class,'SEARCH_SURFACE':_check_search_surface,'NO_SCORE_FIELDS':_check_score_fields,
    'NO_TRADING_CLAIM':_check_trading,
}
# Content that may reach protected data or claim a result: never admitted.
SAFETY_RULES=frozenset({'PROTECTED_FLAG','NO_PROTECTED_YEARS','NO_OPEN_ENDED_WINDOW','SCOPE_NO_RECENCY','LEGAL_RANGE_GRAMMAR','CATALOG_RANGE','PROTECTED_SOURCE','READY_REQUIRES_CATALOG','NO_SCORE_FIELDS','NO_TRADING_CLAIM'})

def card_violations(card,contexts,slot=None):
    """All V02 rule violations as [{'RULE','DETAIL'}]. Never raises on content."""
    if not isinstance(card,dict):return [{'RULE':'SCHEMA_FIELDS','DETAIL':'card is not an object'}]
    out=[]
    for rule in RULE_IDS:
        try:details=CHECKS[rule](card,contexts,slot)
        except Exception as e:details=['check error '+type(e).__name__]
        out+=[{'RULE':rule,'DETAIL':d} for d in details]
    return out

def validate_card_v02(card,contexts,slot=None):
    violations=card_violations(card,contexts,slot)
    if violations:raise ContractError('; '.join(v['RULE']+': '+v['DETAIL'] for v in violations))
    return card
