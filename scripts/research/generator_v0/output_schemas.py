"""Role envelopes for OpenAI Structured Outputs. Application validators stay authoritative."""
from .roles import (RELATIONS,BATCH_RELATIONS,NOVELTY_DIMENSIONS,RED_DIMENSIONS,FEAS_DIMENSIONS)
from .schema import (output_schema,strict_object,validate_instance,normalize_role_output,ContractError)
from .context import digest

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

def generator_schema(contexts,*,provider=False):
    return strict_object({'CANDIDATES':{'type':'array','minItems':1,'maxItems':50,'items':output_schema(contexts,provider=provider)}})

def novelty_schema():
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

def role_schema(role,contexts,*,provider=False):
    if role=='GENERATOR':return generator_schema(contexts,provider=provider)
    if role=='NOVELTY_CRITIC':return novelty_schema()
    if role=='FEASIBILITY_CRITIC':return feasibility_schema(contexts)
    if role=='RED_TEAM':return red_team_schema()
    if role=='SELECTOR':return selector_schema()
    raise ContractError('unknown role schema')

def openai_response_format(role,contexts):
    if role not in ROLE_SCHEMA_NAMES:raise ContractError('unknown role schema')
    schema=role_schema(role,contexts,provider=True)
    return {'type':'json_schema','json_schema':{'name':ROLE_SCHEMA_NAMES[role],'strict':True,'schema':schema}}

def responses_text_format(role,contexts):
    """Responses API Structured Outputs: text.format.{type,name,strict,schema}."""
    if role not in ROLE_SCHEMA_NAMES:raise ContractError('unknown role schema')
    schema=role_schema(role,contexts,provider=True)
    return {'type':'json_schema','name':ROLE_SCHEMA_NAMES[role],'strict':True,'schema':schema}

def generator_schema_digest(contexts):
    return digest(role_schema('GENERATOR',contexts,provider=True))

def assert_structured_payload(role,contexts,payload):
    normalized=normalize_role_output(role,payload)
    validate_instance(normalized,role_schema(role,contexts,provider=False))
    return normalized
