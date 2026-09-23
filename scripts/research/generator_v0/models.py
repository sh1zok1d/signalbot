"""Verified Chat Completions models, prices, and role routing. Fail closed."""
from decimal import Decimal
from .context import ContractError,digest

# Official pages checked 2026-09-23 without an API call:
# https://developers.openai.com/api/docs/guides/structured-outputs
# https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
# https://developers.openai.com/api/docs/guides/latest-model
# https://developers.openai.com/api/docs/models/gpt-5.4
# https://developers.openai.com/api/docs/models/gpt-5
# https://developers.openai.com/api/docs/models/gpt-5-mini
# https://developers.openai.com/api/docs/models/gpt-4.1-mini
# https://developers.openai.com/api/docs/pricing
VERIFIED='2026-09-23'
ENDPOINT='https://api.openai.com/v1/chat/completions'

# Standard uncached USD / million tokens. Cached-input discount is ignored.
MODELS={
    'gpt-5.4-2026-03-05':{
        'INPUT_RATE':Decimal('2.50'),'OUTPUT_RATE':Decimal('15.00'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REQUEST_PARAMS':{'reasoning_effort':'medium'},
        'NOTES':'Flagship Chat Completions reasoning model; temperature unsupported when reasoning. effort: none|low|medium|high|xhigh; default none.',
    },
    'gpt-5-2025-08-07':{
        'INPUT_RATE':Decimal('1.25'),'OUTPUT_RATE':Decimal('10.00'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REQUEST_PARAMS':{'reasoning_effort':'medium'},
        'NOTES':'Strong reasoning; effort: minimal|low|medium|high. Do not send temperature.',
    },
    'gpt-5-mini-2025-08-07':{
        'INPUT_RATE':Decimal('0.25'),'OUTPUT_RATE':Decimal('2.00'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REQUEST_PARAMS':{'reasoning_effort':'low'},
        'NOTES':'Lower-cost capable GPT-5 family; reasoning tokens supported. Do not send temperature.',
    },
    'gpt-4.1-mini-2025-04-14':{
        'INPUT_RATE':Decimal('0.40'),'OUTPUT_RATE':Decimal('1.60'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':32768,
        'REQUEST_PARAMS':{'temperature':0},
        'NOTES':'Non-reasoning; temperature supported; no reasoning_effort. Kept in the price table only.',
    },
}

# GPT-6 Astra is stronger on the current model card but is Responses-first,
# forbids temperature while reasoning, and at USD 10/50 per million tokens is
# not appropriate under the frozen USD 30 campaign cap with conservative
# reservations. Routing stays on verified Chat Completions snapshots.
ROLE_MODEL_MAP={
    'GENERATOR':'gpt-5.4-2026-03-05',
    'NOVELTY_CRITIC':'gpt-5-2025-08-07',
    'RED_TEAM':'gpt-5-2025-08-07',
    'FEASIBILITY_CRITIC':'gpt-5-mini-2025-08-07',
    'SELECTOR':'gpt-5-mini-2025-08-07',
}

ROLES=frozenset(ROLE_MODEL_MAP)
FORBIDDEN_SHARED={'temperature','top_p','top_logprobs','logprobs','tools','functions'}

def spec(model):
    if model not in MODELS:raise ContractError('unknown model or missing verified pricing: '+str(model))
    row=MODELS[model]
    if row['STRUCTURED_OUTPUTS'] is not True:raise ContractError('model lacks verified structured outputs')
    return row

def model_for(role):
    if role not in ROLE_MODEL_MAP:raise ContractError('unknown role for model routing')
    model=ROLE_MODEL_MAP[role];spec(model);return model

def request_params_for(role):
    row=spec(model_for(role));params=dict(row['REQUEST_PARAMS'])
    if set(params)&FORBIDDEN_SHARED and 'temperature' not in row['REQUEST_PARAMS']:
        raise ContractError('unsupported sampling parameter')
    if 'temperature' in params and 'reasoning_effort' in params:
        raise ContractError('temperature and reasoning_effort cannot share a request')
    return params

def rates(role):
    row=spec(model_for(role));return row['INPUT_RATE'],row['OUTPUT_RATE']

def price_table():
    return {name:{'INPUT_RATE':str(row['INPUT_RATE']),'OUTPUT_RATE':str(row['OUTPUT_RATE'])} for name,row in MODELS.items()}

def routing_digest():
    return digest({'ROLE_MODEL_MAP':ROLE_MODEL_MAP,'MODELS':{k:{n:str(v) if n.endswith('RATE') else v for n,v in row.items()} for k,row in MODELS.items()},'VERIFIED':VERIFIED})
