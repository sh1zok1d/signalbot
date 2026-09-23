"""Strict implementation types for the frozen 27 fields; semantic review is separate."""
import json
import math
import re
from .context import ContractError, canonical, digest

DATA_FIELDS={'DATASET','OBSERVABLE','STATUS','LEGAL_RANGE'}
TEXT_FIELDS={'NAME','MECHANISM_FAMILY','MECHANISM','CAUSAL_OR_STRUCTURAL_STORY','INFORMATION_SOURCE','OBSERVABLE','FUNCTION','PRIMARY_TARGET','HORIZON','BASELINE_OR_NULL','FALSIFIER','NEAREST_TESTED_MECHANISM','MECHANISM_DISTANCE_ARGUMENT','WHY_NOT_A_RESCUE','MAIN_CONFOUNDERS','NO_LOOKAHEAD_RULE','DATA_GAP_CLASS','EXPECTED_IMPLEMENTATION_COST','WHAT_POSITIVE_WOULD_TEACH','WHAT_NULL_WOULD_ELIMINATE','EXPECTED_INFORMATION_GAIN'}

def parse_json(raw):
    def pairs(items):
        d={}
        for key,value in items:
            if key in d:raise ContractError('duplicate JSON key')
            d[key]=value
        return d
    try:
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ContractError('nonfinite JSON')))
    except (ValueError,TypeError) as e:
        raise ContractError('malformed JSON') from e

def text(value):
    return isinstance(value,str) and bool(value.strip()) and len(value)<=12000

def validate_card(card, contexts):
    # SEARCH_SURFACE has dynamic parameter names; forbidden scoring fields must
    # be refused recursively, not only at the 27-field root.
    forbidden={'EXPECTED_PROBABILITY_OF_SUCCESS','EXPECTED_ALPHA','EXPECTED_PNL',
               'EXPECTED_PROFIT','SUCCESS_PROBABILITY','PROBABILITY_OF_SUCCESS',
               'PROBABILITY_OF_POSITIVE_RESULT','P_SUCCESS'}
    def check_keys(value):
        if isinstance(value,dict):
            for key,item in value.items():
                normalized=re.sub(r'[^A-Z0-9]+','_',str(key).upper()).strip('_')
                if normalized in forbidden:raise ContractError('forbidden nested success or alpha field')
                check_keys(item)
        elif isinstance(value,list):
            for item in value:check_keys(item)
    check_keys(card)
    d=contexts.design
    if not isinstance(card,dict) or set(card)!=set(d['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']):
        raise ContractError('candidate fields differ from frozen schema')
    if not isinstance(card['CANDIDATE_ID'],str) or not re.fullmatch(r'C[0-9]{3}',card['CANDIDATE_ID']):
        raise ContractError('candidate id must be C001..C999')
    if any(not text(card[f]) for f in TEXT_FIELDS):raise ContractError('empty or malformed candidate field')
    if card['MECHANISM_FAMILY'] not in set(contexts.families)|{'NEW_FAMILY_PROPOSAL'}:
        raise ContractError('unknown family; use NEW_FAMILY_PROPOSAL')
    if card['PROTECTED_DATA_REQUIREMENT'] is not False or re.search(r'\b202[56]\b',canonical(card)):
        raise ContractError('protected data requirement')
    if card['DATA_STATUS'] not in d['DATA_STATUS_TAXONOMY']:raise ContractError('unknown data status')
    req=card['DATA_REQUIRED']
    if not isinstance(req,list) or not 1<=len(req)<=20:raise ContractError('data requirements list')
    for row in req:
        if not isinstance(row,dict) or set(row)!=DATA_FIELDS or any(not text(v) for v in row.values()):
            raise ContractError('data requirement shape')
        if row['STATUS'] not in d['DATA_STATUS_TAXONOMY']:raise ContractError('requirement status')
        known=contexts.catalog.get(row['DATASET'])
        if row['STATUS']=='DATA_READY' and (known is None or known['STATUS']!='DATA_READY'):
            raise ContractError('unverified source claimed ready')
        if known and known['STATUS']=='FORBIDDEN_HARD_FAIL':raise ContractError('protected source')
    statuses={r['STATUS'] for r in req}
    if card['DATA_STATUS']=='DATA_READY' and statuses!={'DATA_READY'}:raise ContractError('aggregate status mismatch')
    if card['DATA_STATUS'] not in statuses:raise ContractError('aggregate status absent from requirements')
    missing=card['MISSING_OBSERVABLES']
    if not isinstance(missing,list) or any(not text(x) for x in missing):raise ContractError('missing-observable list')
    if statuses!={'DATA_READY'} and not missing:raise ContractError('exact missing observable required')
    if statuses!={'DATA_READY'} and card['DATA_GAP_CLASS']=='NONE':raise ContractError('missing data gap class')
    surf=card['SEARCH_SURFACE']
    if not isinstance(surf,dict) or set(surf)!={'PARAMETERS','MAX_VARIANTS'}:raise ContractError('search surface shape')
    if type(surf['MAX_VARIANTS']) is not int or not 1<=surf['MAX_VARIANTS']<=100:
        raise ContractError('unbounded search surface')
    if not isinstance(surf['PARAMETERS'],dict) or not surf['PARAMETERS']:raise ContractError('unstated search surface')
    n=1
    for k,values in surf['PARAMETERS'].items():
        if not text(k) or not isinstance(values,list) or not values:raise ContractError('parameter grid')
        if any(type(v) not in (str,int,float) or (type(v)==float and not math.isfinite(v)) for v in values):
            raise ContractError('parameter value')
        n*=len(values)
    if n>surf['MAX_VARIANTS']:raise ContractError('understated search surface')
    claim=' '.join(str(card[k]) for k in TEXT_FIELDS)
    if re.search(r'expected[_ -]alpha|probability[_ -]of[_ -]success|guaranteed profit|validated trading edge|buy signal|sell signal',claim,re.I):
        raise ContractError('trading or success claim')
    return card

def signature(card):
    return digest({k:card[k] for k in ('MECHANISM','INFORMATION_SOURCE','OBSERVABLE','FUNCTION','PRIMARY_TARGET','HORIZON')})

def output_schema(contexts):
    props={k:{'type':'string'} for k in contexts.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']}
    props['PROTECTED_DATA_REQUIREMENT']={'type':'boolean','enum':[False]}
    props['DATA_STATUS']={'type':'string','enum':list(contexts.design['DATA_STATUS_TAXONOMY'])}
    props['MISSING_OBSERVABLES']={'type':'array','items':{'type':'string'}}
    props['DATA_REQUIRED']={'type':'array','items':{'type':'object','properties':{k:{'type':'string'} for k in sorted(DATA_FIELDS)},'required':sorted(DATA_FIELDS),'additionalProperties':False}}
    # Dynamic parameter names are represented as JSON object by json_object output mode;
    # application validation is authoritative (strict provider schemas are optional).
    props['SEARCH_SURFACE']={'type':'object'}
    return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
