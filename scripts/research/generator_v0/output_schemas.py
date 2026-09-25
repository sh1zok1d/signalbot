"""Role envelopes for OpenAI Structured Outputs. Application validators stay authoritative.

Decoding-level contracts (GENERATOR_CONTRACT_V02):
- GENERATOR: CANDIDATES is an object keyed by exactly the round's slot IDs, so
  cardinality and candidate IDs are fixed by the schema; each card pins its
  slot identity, LEGAL_RANGE grammar, status enums and NEAREST_TESTED_MECHANISM.
  This exact keyed schema is what intake enforces. The Anthropic wire uses the
  compact array projection below (anthropic_generator_compact_schema).
- NOVELTY_CRITIC: PRIOR_RELATIONS and BATCH_RELATIONS are objects keyed by the
  exact prior signature IDs and other candidate IDs, so coverage is fixed by
  the schema instead of being checked after payment.
Application code still re-validates everything (fakes and drift are not trusted).
"""
import re
from .roles import (RELATIONS,BATCH_RELATIONS,NOVELTY_DIMENSIONS,RED_DIMENSIONS,FEAS_DIMENSIONS)
from .schema import (output_schema,strict_object,validate_instance,normalize_role_output,ContractError)
from .context import digest
from . import contract

ROLE_SCHEMA_NAMES={
    'GENERATOR':'generator_candidates',
    'NOVELTY_CRITIC':'novelty_critic',
    'FEASIBILITY_CRITIC':'feasibility_critic',
    'RED_TEAM':'red_team',
    'SELECTOR':'selector',
}

def _ordinal(keys):
    return strict_object({k:{'type':'integer','minimum':0,'maximum':3} for k in keys})

def _booleans(keys):
    return strict_object({k:{'type':'boolean'} for k in keys})

def _slots(request):
    slots=((request or {}).get('parameters') or {}).get('slots')
    if not isinstance(slots,list) or not slots:raise ContractError('generator request requires slots')
    return slots

def generator_schema(contexts,*,provider=False,request=None):
    if provider:
        slots=_slots(request)
        return strict_object({'CANDIDATES':strict_object({s['CANDIDATE_ID']:output_schema(contexts,provider=True,slot=s) for s in slots})})
    n=len(_slots(request)) if request is not None else None
    arr={'type':'array','minItems':n or 1,'maxItems':n or 50,'items':output_schema(contexts,provider=False)}
    return strict_object({'CANDIDATES':arr})

def _leaf_ids(contexts):
    return sorted(k for k,r in contexts.rows.items() if r['STATE']!='PARTIAL_OR_MIXED')

def _batch_ids(request):
    ctx=(request or {}).get('context') or {}
    own=(ctx.get('CANDIDATE') or {}).get('CANDIDATE_ID')
    return sorted(r['CANDIDATE_ID'] for r in ctx.get('CURRENT_BATCH_SIGNATURES',[]) if r['CANDIDATE_ID']!=own)

def novelty_schema(contexts,*,provider=False,request=None):
    if provider:
        prior=strict_object({k:{'type':'string','enum':sorted(RELATIONS)} for k in _leaf_ids(contexts)})
        batch=strict_object({k:{'type':'string','enum':sorted(BATCH_RELATIONS)} for k in _batch_ids(request)})
        return strict_object({'PRIOR_RELATIONS':prior,'BATCH_RELATIONS':batch,'JUDGMENTS':_ordinal(NOVELTY_DIMENSIONS)})
    prior=strict_object({'SIGNATURE_ID':{'type':'string'},'RELATION':{'type':'string','enum':sorted(RELATIONS)}})
    batch=strict_object({'CANDIDATE_ID':{'type':'string'},'RELATION':{'type':'string','enum':sorted(BATCH_RELATIONS)}})
    return strict_object({
        'PRIOR_RELATIONS':{'type':'array','minItems':1,'items':prior},
        'BATCH_RELATIONS':{'type':'array','items':batch},
        'JUDGMENTS':_ordinal(NOVELTY_DIMENSIONS),
    })

def feasibility_schema(contexts):
    return strict_object({
        'DATA_STATUS':{'type':'string','enum':sorted(contexts.design['DATA_STATUS_TAXONOMY'])},
        'CHECKS':_booleans({'OBSERVABLE_SUPPORTED','LEGAL_RANGE','POINT_IN_TIME','PROVENANCE','BLOCKER_RESOLVED'}),
        'JUDGMENTS':_ordinal(FEAS_DIMENSIONS),
        'FEASIBILITY':{'type':'integer','minimum':0,'maximum':3},
        'CHEAPNESS':{'type':'integer','minimum':0,'maximum':3},
    })

def red_team_schema():
    return strict_object({
        'CHECKS':_booleans({'NO_LOOKAHEAD','CAUSALITY','FALSIFIABLE','BOUNDED_SEARCH','CONFOUNDING_ADDRESSED','NO_TRADING_CLAIM'}),
        'JUDGMENTS':_ordinal(RED_DIMENSIONS),
    })

def selector_schema():
    return strict_object({'ORDERED_CANDIDATE_IDS':{'type':'array','items':{'type':'string'}}})

def role_schema(role,contexts,*,provider=False,request=None):
    if role=='GENERATOR':return generator_schema(contexts,provider=provider,request=request)
    if role=='NOVELTY_CRITIC':return novelty_schema(contexts,provider=provider,request=request)
    if role=='FEASIBILITY_CRITIC':return feasibility_schema(contexts)
    if role=='RED_TEAM':return red_team_schema()
    if role=='SELECTOR':return selector_schema()
    raise ContractError('unknown role schema')

def openai_response_format(role,contexts,request=None):
    if role not in ROLE_SCHEMA_NAMES:raise ContractError('unknown role schema')
    schema=role_schema(role,contexts,provider=True,request=request)
    assert_strict_subset(schema)
    return {'type':'json_schema','json_schema':{'name':ROLE_SCHEMA_NAMES[role],'strict':True,'schema':schema}}

def responses_text_format(role,contexts,request=None):
    """Responses API Structured Outputs: text.format.{type,name,strict,schema}."""
    if role not in ROLE_SCHEMA_NAMES:raise ContractError('unknown role schema')
    schema=role_schema(role,contexts,provider=True,request=request)
    assert_strict_subset(schema)
    return {'type':'json_schema','name':ROLE_SCHEMA_NAMES[role],'strict':True,'schema':schema}

def request_schema_digest(role,contexts,request):
    return digest(role_schema(role,contexts,provider=True,request=request))

def generator_round_schema_digest(contexts,slots):
    return request_schema_digest('GENERATOR',contexts,{'parameters':{'slots':list(slots)}})

def generator_schema_digest(contexts):
    """Run-level V02 generator contract identity: rule table plus the 40-slot plan's round schemas."""
    from .mock import slot_plan
    plan=slot_plan(40)
    return digest({'CONTRACT':contract.CONTRACT_ID,'RULES':contract.RULES,'ROUNDS':[generator_round_schema_digest(contexts,plan[i:i+10]) for i in range(0,40,10)]})

def assert_structured_payload(role,contexts,payload,request=None):
    """Provider payload -> application form, checked against the exact provider schema first."""
    validate_instance(payload,role_schema(role,contexts,provider=True,request=request))
    return normalize_role_output(role,payload)

# Offline conformance to the Structured Outputs strict subset (official docs,
# structured-outputs guide, checked 2026-09-23). This proves our schemas use only
# the documented subset and limits; it is not a provider acceptance test.
STRICT_ALLOWED_KEYWORDS={
    'object':{'type','properties','required','additionalProperties'},
    'array':{'type','items','minItems','maxItems'},
    'string':{'type','enum','pattern'},
    'integer':{'type','minimum','maximum'},
    'number':{'type','minimum','maximum'},
    'boolean':{'type','enum'},
}
STRICT_LIMITS={'MAX_DEPTH':10,'MAX_PROPERTIES':5000,'MAX_ENUM_VALUES':1000}
_PROPERTY_NAME=re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
_FORBIDDEN_REGEX=re.compile(r'\(\?|\\[1-9]|\\[bBdDwWsS]')

def strict_subset_violations(schema):
    out=[];counts={'properties':0,'enums':0}
    def walk(node,depth,path):
        if depth>STRICT_LIMITS['MAX_DEPTH']:out.append(path+': nesting depth');return
        if 'anyOf' in node:
            if set(node)!={'anyOf'} or not node['anyOf']:out.append(path+': anyOf must stand alone')
            for i,opt in enumerate(node.get('anyOf',[])):walk(opt,depth+1,path+'/anyOf'+str(i))
            return
        t=node.get('type')
        if t not in STRICT_ALLOWED_KEYWORDS:out.append(path+': unsupported type '+str(t));return
        extra=set(node)-STRICT_ALLOWED_KEYWORDS[t]
        if extra:out.append(path+': unsupported keywords '+','.join(sorted(extra)))
        if t=='object':
            props=node.get('properties',{})
            if node.get('additionalProperties') is not False:out.append(path+': additionalProperties must be false')
            if sorted(node.get('required',[]))!=sorted(props):out.append(path+': every property must be required')
            counts['properties']+=len(props)
            for k,v in props.items():
                if not _PROPERTY_NAME.fullmatch(k):out.append(path+': property name '+k)
                walk(v,depth+1,path+'/'+k)
        elif t=='array':
            if 'items' not in node:out.append(path+': array items required')
            else:walk(node['items'],depth+1,path+'/items')
        if 'enum' in node:
            counts['enums']+=len(node['enum'])
            if not node['enum']:out.append(path+': empty enum')
        if 'pattern' in node:
            p=node['pattern']
            if _FORBIDDEN_REGEX.search(p):out.append(path+': pattern uses lookaround, backreference or shorthand class')
            try:re.compile(p)
            except re.error:out.append(path+': invalid pattern')
    walk(schema,1,'#')
    if counts['properties']>STRICT_LIMITS['MAX_PROPERTIES']:out.append('#: too many properties')
    if counts['enums']>STRICT_LIMITS['MAX_ENUM_VALUES']:out.append('#: too many enum values')
    return out

def assert_strict_subset(schema):
    bad=strict_subset_violations(schema)
    if bad:raise ContractError('schema outside strict subset: '+'; '.join(bad[:5]))
    return schema

# ------------------------------------------------ Anthropic structured outputs
# Claude structured outputs (output_config.format json_schema) support a
# different subset than OpenAI strict mode: no numerical constraints
# (minimum/maximum/multipleOf), no string length constraints, no complex array
# constraints (maxItems, minItems above 1). The Anthropic request therefore
# carries a projection with only those keywords removed (for GENERATOR, of the
# compact schema below), and every removed constraint is still enforced after
# decoding: intake validates each card against the exact provider schema
# (slot_violations_v02) and the V02 rules. This is an offline conformance check
# against the documented subset, not a provider acceptance test.
ANTHROPIC_ALLOWED_KEYWORDS={
    'object':{'type','properties','required','additionalProperties'},
    'array':{'type','items','minItems'},
    'string':{'type','enum','pattern','const','format'},
    'integer':{'type','enum','const'},
    'number':{'type','enum','const'},
    'boolean':{'type','enum','const'},
    'null':{'type'},
}
ANTHROPIC_DROPPED_KEYWORDS=('minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf','minLength','maxLength','maxItems','uniqueItems')
ANTHROPIC_STRING_FORMATS={'date-time','time','date','duration','email','hostname','uri','ipv4','ipv6','uuid'}

def anthropic_projection(schema):
    """(projected schema, removed [(path, keyword, value)]). Only unsupported constraint keywords are removed."""
    removed=[]
    def walk(node,path):
        if isinstance(node,dict):
            out={}
            for k,v in node.items():
                if k in ANTHROPIC_DROPPED_KEYWORDS or (k=='minItems' and not (type(v) is int and v in (0,1))):
                    removed.append((path,k,v));continue
                if k=='properties':out[k]={name:walk(sub,path+'/'+name) for name,sub in v.items()}
                elif k=='items':out[k]=walk(v,path+'/items')
                elif k=='anyOf':out[k]=[walk(x,path+'/anyOf'+str(i)) for i,x in enumerate(v)]
                else:out[k]=v
            return out
        return node
    return walk(schema,'#'),removed

def anthropic_subset_violations(schema):
    out=[]
    def walk(node,depth,path):
        if depth>32:out.append(path+': nesting depth');return
        if 'anyOf' in node:
            if set(node)!={'anyOf'} or not node['anyOf']:out.append(path+': anyOf must stand alone')
            for i,opt in enumerate(node.get('anyOf',[])):walk(opt,depth+1,path+'/anyOf'+str(i))
            return
        t=node.get('type')
        if t not in ANTHROPIC_ALLOWED_KEYWORDS:out.append(path+': unsupported type '+str(t));return
        extra=set(node)-ANTHROPIC_ALLOWED_KEYWORDS[t]
        if extra:out.append(path+': unsupported keywords '+','.join(sorted(extra)))
        if t=='object':
            if node.get('additionalProperties') is not False:out.append(path+': additionalProperties must be false')
            props=node.get('properties',{})
            if sorted(node.get('required',[]))!=sorted(props):out.append(path+': every property must be required')
            for k,v in props.items():
                if not _PROPERTY_NAME.fullmatch(k):out.append(path+': property name '+k)
                walk(v,depth+1,path+'/'+k)
        elif t=='array':
            if 'items' not in node:out.append(path+': array items required')
            else:walk(node['items'],depth+1,path+'/items')
            if 'minItems' in node and node['minItems'] not in (0,1):out.append(path+': minItems above 1')
        if 'enum' in node and not node['enum']:out.append(path+': empty enum')
        if 'format' in node and node['format'] not in ANTHROPIC_STRING_FORMATS:out.append(path+': unsupported format')
        if 'pattern' in node:
            p=node['pattern']
            if _FORBIDDEN_REGEX.search(p):out.append(path+': pattern uses lookaround, backreference or shorthand class')
            try:re.compile(p)
            except re.error:out.append(path+': invalid pattern')
    walk(schema,1,'#')
    return out

# Compact GENERATOR wire format. The keyed exact schema repeats the full
# slot-pinned card schema once per slot; Claude rejected its compiled grammar as
# too large (10 slots: 42 objects, 40 one-value enums, LEGAL_RANGE x10). The
# compact projection sends ONE shared card schema inside an array. It is a
# decoding aid only: intake maps each returned card to its slot by
# CANDIDATE_ID and validates it against that slot's EXACT provider schema and
# the V02 rules (runner._intake_round / slot_violations_v02) before any card is
# VALID or reaches a critic. Relaxed only at the provider level:
ANTHROPIC_GENERATOR_WIRE_FORMAT='ANTHROPIC_COMPACT_CANDIDATE_ARRAY_V1'
KEYED_GENERATOR_WIRE_FORMAT='KEYED_SLOT_OBJECT'
ANTHROPIC_COMPACT_RELAXED_CONSTRAINTS=(
    {'CONSTRAINT':'CANDIDATES keyed by exactly the round slot IDs (one card per slot, no extras, no duplicates)',
     'PROVIDER':'array of cards, minItems 1','INTAKE':'missing slot / duplicate ID -> HARD_FAIL for that slot; unknown ID -> ignored and recorded'},
    {'CONSTRAINT':'CANDIDATE_ID one-value enum per slot','PROVIDER':'enum of the round slot IDs','INTAKE':'card bound to the slot named by its own CANDIDATE_ID; exact slot schema'},
    {'CONSTRAINT':'MECHANISM_FAMILY one-value enum per slot','PROVIDER':'enum of all frozen families','INTAKE':'exact slot schema one-value enum'},
    {'CONSTRAINT':'INFORMATION_SOURCE one-value enum per slot','PROVIDER':'enum of all slot source classes','INTAKE':'exact slot schema one-value enum'},
    {'CONSTRAINT':'SEARCH_SURFACE.MAX_VARIANTS minimum 1 / maximum 100','PROVIDER':'integer','INTAKE':'exact slot schema integer range'},
    {'CONSTRAINT':'DATA_REQUIRED maxItems 20','PROVIDER':'array, minItems 1','INTAKE':'exact slot schema array length'},
)

def generator_wire_format(request):
    """Wire format of a stored/issued GENERATOR request (absent = keyed exact schema)."""
    return (request or {}).get('provider_wire_format') or KEYED_GENERATOR_WIRE_FORMAT

def anthropic_generator_compact_schema(contexts,request):
    """{'CANDIDATES': [card]} with one shared card schema for the whole round."""
    from .mock import SOURCE_CLASSES
    slots=_slots(request)
    card=output_schema(contexts,provider=True,slot=None)
    card['properties']['CANDIDATE_ID']={'type':'string','enum':[s['CANDIDATE_ID'] for s in slots]}
    card['properties']['INFORMATION_SOURCE']={'type':'string','enum':sorted(set(SOURCE_CLASSES)|{s['INFORMATION_SOURCE'] for s in slots})}
    return strict_object({'CANDIDATES':{'type':'array','minItems':1,'items':card}})

def anthropic_output_schema(role,contexts,request):
    """Per-request Anthropic schema: the compact GENERATOR projection, or the exact
    provider schema for other roles; projected to the Anthropic subset and checked."""
    exact=anthropic_generator_compact_schema(contexts,request) if role=='GENERATOR' else role_schema(role,contexts,provider=True,request=request)
    projected,_=anthropic_projection(exact)
    bad=anthropic_subset_violations(projected)
    if bad:raise ContractError('schema outside Anthropic structured-output subset: '+'; '.join(bad[:5]))
    return projected

def anthropic_generator_schema_digest(contexts):
    """Run-level identity of the Anthropic generator schemas over the 40-slot plan."""
    from .mock import slot_plan
    plan=slot_plan(40)
    return digest({'CONTRACT':contract.CONTRACT_ID,'WIRE_FORMAT':ANTHROPIC_GENERATOR_WIRE_FORMAT,
                   'ROUNDS':[digest(anthropic_output_schema('GENERATOR',contexts,{'parameters':{'slots':plan[i:i+10]}})) for i in range(0,40,10)]})
