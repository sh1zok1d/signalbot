"""Strict implementation types for the frozen 27 fields; semantic review is separate."""
import json
import math
import re
from .context import ContractError, digest

DATA_FIELDS={'DATASET','OBSERVABLE','STATUS','LEGAL_RANGE'}
TEXT_FIELDS={'NAME','MECHANISM_FAMILY','MECHANISM','CAUSAL_OR_STRUCTURAL_STORY','INFORMATION_SOURCE','OBSERVABLE','FUNCTION','PRIMARY_TARGET','HORIZON','BASELINE_OR_NULL','FALSIFIER','NEAREST_TESTED_MECHANISM','MECHANISM_DISTANCE_ARGUMENT','WHY_NOT_A_RESCUE','MAIN_CONFOUNDERS','NO_LOOKAHEAD_RULE','DATA_GAP_CLASS','EXPECTED_IMPLEMENTATION_COST','WHAT_POSITIVE_WOULD_TEACH','WHAT_NULL_WOULD_ELIMINATE','EXPECTED_INFORMATION_GAIN'}
PROTECTED_PERIOD_START=(2025,1)
PROTECTED_CATALOG_DATASET='PROTECTED_2025_2026'
PROTECTED_YEAR_TOKEN=re.compile(r'(?<!\d)202[56](?!\d)')
# Unambiguous exclusion only: "No 2025[/2026] <non-numeric subject> are/is permitted|allowed".
# Body cannot contain digits, another year, or `. ; : ! ?`. No "not"/"forbidden".
PROTECTED_EXCLUSION_STATEMENT=re.compile(
    r'(?i)\bno\s+202[56](?:\s*/\s*202[56])?\b[^\d.;:!?]{0,240}\b(?:are|is)\s+(?:permitted|allowed)\b'
)
# Explicit observation-window / open-ended / post-2024 aliases only.
# Bare "latest" or "current" is not sufficient (point-in-time wording allowed).
OPEN_ENDED_OR_POST2024=re.compile(
    r'(?i)(?:'
    r'\blatest\s+(?:available|data|quotes|prices?|observations?|closes|bars)\b'
    r'|\blatest\s*/\s*current\b'
    r'|\bcurrent\s+(?:bars|quotes|closes|prices?|data|available|window|range|period|observations?|markets?)\b'
    r'|\bthrough\s+(?:today|present)\b'
    r'|\buntil\s+present\b'
    r'|\bup\s+to\s+now\b'
    r'|\bopen-?ended\b'
    r'|\bpost-2024\b'
    r'|\bafter\s+2024\b'
    r'|\bsince\s+2024\b'
    r'|\b2024\+'
    r'|\b2024(?:-\d{2})?\s+onwards?\b'
    r'|\b2024\s+and\s+later\b'
    r'|\b2024-present\b'
    r'|\byear\s+after\s+2024\b'
    r')'
)

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

# Exact v5 annotated form only. Not "extract the first date range from prose".
_ANNOTATED_LEGAL_RANGE=re.compile(
    r'(?is)\Arequired\s+historical\s+window:\s*'
    r'(?P<range>\d{4}-\d{2}\.\.\d{4}-\d{2}|\d{4}\.\.\d{4}|pre-\d{4})\s*;\s*'
    r'(?P<note>coverage\s+unverified\s+and\s+not\s+catalogued|no\s+known\s+public\s+coverage)\s*\Z'
)

def _classify_strict_range(text):
    month=re.fullmatch(r'(\d{4})-(\d{2})\.\.(\d{4})-(\d{2})',text)
    if month:
        y1,m1,y2,m2=map(int,month.groups())
        if not (1<=m1<=12 and 1<=m2<=12):return {'KIND':'AMBIGUOUS'}
        start,end=(y1,m1),(y2,m2)
        if start>end:return {'KIND':'AMBIGUOUS'}
        return {'KIND':'BOUNDED','START':start,'END':end}
    year=re.fullmatch(r'(\d{4})\.\.(\d{4})',text)
    if year:
        y1,y2=map(int,year.groups())
        start,end=(y1,1),(y2,12)
        if start>end:return {'KIND':'AMBIGUOUS'}
        return {'KIND':'BOUNDED','START':start,'END':end}
    pre=re.fullmatch(r'pre-(\d{4})',text)
    if pre:
        y=int(pre.group(1))
        if y<1:return {'KIND':'AMBIGUOUS'}
        return {'KIND':'BOUNDED','START':None,'END':(y-1,12)}
    return {'KIND':'AMBIGUOUS'}

def classify_legal_range(value):
    """Deterministic classifier for frozen catalog LEGAL_RANGE forms. Fail closed."""
    if not isinstance(value,str):return {'KIND':'AMBIGUOUS'}
    text=value.strip()
    if text=='per snapshot':return {'KIND':'PER_SNAPSHOT'}
    classified=_classify_strict_range(text)
    if classified['KIND']!='AMBIGUOUS':return classified
    annotated=_ANNOTATED_LEGAL_RANGE.fullmatch(text)
    if not annotated:return {'KIND':'AMBIGUOUS'}
    return _classify_strict_range(annotated.group('range'))

def legal_range_includes_protected(classified):
    return classified.get('KIND')=='BOUNDED' and classified['END']>=PROTECTED_PERIOD_START

def contains_protected_year(value):
    if isinstance(value,dict):
        return any((isinstance(k,str) and PROTECTED_YEAR_TOKEN.search(k)) or contains_protected_year(v) for k,v in value.items())
    if isinstance(value,list):
        return any(contains_protected_year(v) for v in value)
    if type(value) is int and value in (2025,2026):return True
    if isinstance(value,str) and PROTECTED_YEAR_TOKEN.search(value):return True
    return False

def contains_open_ended_or_post2024(value):
    if isinstance(value,dict):
        return any((isinstance(k,str) and OPEN_ENDED_OR_POST2024.search(k)) or contains_open_ended_or_post2024(v) for k,v in value.items())
    if isinstance(value,list):
        return any(contains_open_ended_or_post2024(v) for v in value)
    return isinstance(value,str) and OPEN_ENDED_OR_POST2024.search(value) is not None

def text_outside_exclusions(text):
    if not isinstance(text,str):return ''
    parts=[];last=0
    for match in PROTECTED_EXCLUSION_STATEMENT.finditer(text):
        parts.append(text[last:match.start()]);last=match.end()
    parts.append(text[last:])
    return ' '.join(parts)

def years_only_in_exclusions(text):
    if not isinstance(text,str):return False
    spans=[m.span() for m in PROTECTED_EXCLUSION_STATEMENT.finditer(text)]
    for token in PROTECTED_YEAR_TOKEN.finditer(text):
        if not any(start<=token.start() and token.end()<=end for start,end in spans):
            return False
    return True

def assert_protected_semantics(card):
    """Fail closed if the candidate requires protected 2025/2026 observations.

    Recognized exclusion statements are allowed only in NO_LOOKAHEAD_RULE.
    """
    if card.get('PROTECTED_DATA_REQUIREMENT') is not False:
        raise ContractError('protected data requirement')
    rule=card.get('NO_LOOKAHEAD_RULE')
    if not years_only_in_exclusions(rule):raise ContractError('protected data requirement')
    if contains_open_ended_or_post2024(text_outside_exclusions(rule)):raise ContractError('protected data requirement')
    rest={k:v for k,v in card.items() if k!='NO_LOOKAHEAD_RULE'}
    if contains_protected_year(rest) or contains_open_ended_or_post2024(rest):
        raise ContractError('protected data requirement')

def assert_required_data_legal(row,known):
    """DATA_REQUIRED legal range is necessary, not sufficient, for protected-data safety."""
    dataset=row['DATASET']
    if dataset==PROTECTED_CATALOG_DATASET or (known and known.get('STATUS')=='FORBIDDEN_HARD_FAIL'):
        raise ContractError('protected source')
    classified=classify_legal_range(row['LEGAL_RANGE'])
    if known is not None:
        catalog=classify_legal_range(known.get('LEGAL_RANGE'))
        if legal_range_includes_protected(catalog):raise ContractError('protected catalog legal range')
        if classified['KIND']=='PER_SNAPSHOT':return
        if classified['KIND']=='BOUNDED' and not legal_range_includes_protected(classified):return
        if classified['KIND']=='BOUNDED':raise ContractError('protected legal range')
        raise ContractError('ambiguous protected range')
    if classified['KIND']=='BOUNDED' and not legal_range_includes_protected(classified):return
    if classified['KIND']=='BOUNDED':raise ContractError('protected legal range')
    raise ContractError('ambiguous protected range')

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
    if card['PROTECTED_DATA_REQUIREMENT'] is not False:
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
        assert_required_data_legal(row,known)
    assert_protected_semantics(card)
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

def strict_object(properties):
    props=dict(properties)
    return {'type':'object','properties':props,'required':sorted(props),'additionalProperties':False}

def search_surface_application_schema():
    # Dynamic parameter names remain a dict for the frozen application card.
    return strict_object({'MAX_VARIANTS':{'type':'integer','minimum':1,'maximum':100},'PARAMETERS':{'type':'object','properties':{},'required':[],'additionalProperties':True}})

def search_surface_provider_schema():
    # OpenAI strict JSON Schema forbids free-form object keys. Encode the frozen
    # PARAMETERS dict as an array of {NAME,VALUES} without changing card semantics.
    value={'anyOf':[{'type':'string'},{'type':'integer'},{'type':'number'}]}
    entry=strict_object({'NAME':{'type':'string'},'VALUES':{'type':'array','minItems':1,'items':value}})
    return strict_object({'MAX_VARIANTS':{'type':'integer','minimum':1,'maximum':100},'PARAMETERS':{'type':'array','minItems':1,'items':entry}})

def output_schema(contexts,*,provider=False):
    required=list(contexts.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS'])
    props={k:{'type':'string'} for k in required}
    props['CANDIDATE_ID']={'type':'string','pattern':r'^C[0-9]{3}$'}
    props['PROTECTED_DATA_REQUIREMENT']={'type':'boolean','enum':[False]}
    props['DATA_STATUS']={'type':'string','enum':sorted(contexts.design['DATA_STATUS_TAXONOMY'])}
    props['MECHANISM_FAMILY']={'type':'string','enum':sorted(set(contexts.families)|{'NEW_FAMILY_PROPOSAL'})}
    props['MISSING_OBSERVABLES']={'type':'array','items':{'type':'string'}}
    props['DATA_REQUIRED']={'type':'array','minItems':1,'maxItems':20,'items':strict_object({k:{'type':'string'} for k in DATA_FIELDS})}
    props['SEARCH_SURFACE']=search_surface_provider_schema() if provider else search_surface_application_schema()
    return strict_object(props)

def normalize_search_surface(surface):
    if not isinstance(surface,dict):raise ContractError('search surface shape')
    params=surface.get('PARAMETERS')
    if isinstance(params,list):
        converted={}
        for row in params:
            if not isinstance(row,dict) or set(row)!={'NAME','VALUES'}:raise ContractError('provider search-surface encoding')
            name=row['NAME']
            if name in converted:raise ContractError('duplicate search parameter')
            converted[name]=row['VALUES']
        surface={**surface,'PARAMETERS':converted}
    return surface

def normalize_role_output(role,payload):
    if role!='GENERATOR' or not isinstance(payload,dict) or not isinstance(payload.get('CANDIDATES'),list):
        return payload
    cards=[]
    for card in payload['CANDIDATES']:
        if isinstance(card,dict) and 'SEARCH_SURFACE' in card:
            card={**card,'SEARCH_SURFACE':normalize_search_surface(card['SEARCH_SURFACE'])}
        cards.append(card)
    return {**payload,'CANDIDATES':cards}

def validate_instance(instance,schema):
    if 'anyOf' in schema:
        errors=[]
        for option in schema['anyOf']:
            try:validate_instance(instance,option);return
            except ContractError as e:errors.append(str(e))
        raise ContractError('anyOf failed')
    expected=schema.get('type')
    if expected=='object':
        if not isinstance(instance,dict):raise ContractError('expected object')
        additional=schema.get('additionalProperties')
        required=list(schema.get('required',[]))
        props=dict(schema.get('properties',{}))
        if additional is False:
            if set(required)!=set(props):raise ContractError('schema required must list every property')
            extra=set(instance)-set(props);missing=set(props)-set(instance)
            if extra or missing:raise ContractError('object fields differ from schema')
        elif additional is True:
            missing=[k for k in required if k not in instance]
            if missing:raise ContractError('object fields differ from schema')
        else:
            raise ContractError('schema must set additionalProperties')
        for key,sub in props.items():
            if key in instance:validate_instance(instance[key],sub)
        return
    if expected=='array':
        if not isinstance(instance,list):raise ContractError('expected array')
        lo,hi=schema.get('minItems'),schema.get('maxItems')
        if lo is not None and len(instance)<lo:raise ContractError('array too short')
        if hi is not None and len(instance)>hi:raise ContractError('array too long')
        item=schema.get('items')
        if item is None:raise ContractError('array items required')
        for value in instance:validate_instance(value,item)
        return
    if expected=='string':
        if not isinstance(instance,str):raise ContractError('expected string')
        if 'enum' in schema and instance not in schema['enum']:raise ContractError('string enum')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],instance):raise ContractError('string pattern')
        return
    if expected=='boolean':
        if type(instance) is not bool:raise ContractError('expected boolean')
        if 'enum' in schema and instance not in schema['enum']:raise ContractError('boolean enum')
        return
    if expected=='integer':
        if type(instance) is not int:raise ContractError('expected integer')
        if instance<schema.get('minimum',instance) or instance>schema.get('maximum',instance):raise ContractError('integer range')
        return
    if expected=='number':
        if type(instance) not in (int,float) or type(instance) is bool:raise ContractError('expected number')
        if isinstance(instance,float) and not math.isfinite(instance):raise ContractError('nonfinite number')
        return
    raise ContractError('unsupported schema type')
