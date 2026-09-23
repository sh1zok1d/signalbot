"""Verified models, prices, and role routing. Fail closed.

GENERATOR transport is background Responses (`openai_provider.py`).
Critic/selector transport remains Chat Completions at ENDPOINT.
Role map and reasoning_effort are unchanged."""
from decimal import Decimal
from .context import ContractError,digest

# Official pages checked 2026-09-23 without an API call:
# https://developers.openai.com/api/docs/guides/structured-outputs
# https://developers.openai.com/api/docs/guides/background
# https://developers.openai.com/api/reference/resources/responses
# https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
# https://developers.openai.com/api/docs/guides/latest-model
# https://developers.openai.com/api/docs/models/gpt-6-astra
# https://developers.openai.com/api/docs/models/gpt-6-sol
# https://developers.openai.com/api/docs/models/gpt-6-luna
# https://developers.openai.com/api/docs/pricing
VERIFIED='2026-09-23'
ENDPOINT='https://api.openai.com/v1/chat/completions'

# Standard uncached short-context USD / million tokens.
# Cached-input discount is ignored. Long-context (>272K) multipliers are
# not used: campaign bounds fail closed above 1M total tokens and expected
# requests stay well under the 272K threshold.
MODELS={
    'gpt-6-astra':{
        'INPUT_RATE':Decimal('10.00'),'OUTPUT_RATE':Decimal('50.00'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REASONING_EFFORTS':('low','medium','high','xhigh','max'),
        'NOTES':'Flagship GPT-6; Chat Completions + Structured Outputs. No dated snapshot. Does not support reasoning_effort=none. Do not send temperature.',
    },
    'gpt-6-sol':{
        'INPUT_RATE':Decimal('2.00'),'OUTPUT_RATE':Decimal('10.00'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REASONING_EFFORTS':('none','low','medium','high','xhigh','max'),
        'NOTES':'Strong GPT-6 reasoning; Chat Completions + Structured Outputs. No dated snapshot. Do not send temperature when reasoning_effort is not none.',
    },
    'gpt-6-luna':{
        'INPUT_RATE':Decimal('0.10'),'OUTPUT_RATE':Decimal('0.50'),
        'STRUCTURED_OUTPUTS':True,'MAX_OUTPUT_TOKENS':128000,
        'REASONING_EFFORTS':('none','low','medium','high','xhigh','max'),
        'NOTES':'Efficient GPT-6; Chat Completions + Structured Outputs. No dated snapshot. Supports reasoning_effort=none.',
    },
}

# Chat Completions architecture is unchanged. Official catalog exposes only
# these stable IDs (no dated snapshots to pin).
ROLE_MODEL_MAP={
    'GENERATOR':'gpt-6-astra',
    'NOVELTY_CRITIC':'gpt-6-sol',
    'RED_TEAM':'gpt-6-sol',
    'FEASIBILITY_CRITIC':'gpt-6-luna',
    'SELECTOR':'gpt-6-luna',
}

ROLE_REQUEST_PARAMS={
    'GENERATOR':{'reasoning_effort':'high'},
    'NOVELTY_CRITIC':{'reasoning_effort':'medium'},
    'RED_TEAM':{'reasoning_effort':'medium'},
    'FEASIBILITY_CRITIC':{'reasoning_effort':'low'},
    'SELECTOR':{'reasoning_effort':'none'},
}

ROLES=frozenset(ROLE_MODEL_MAP)
FORBIDDEN_SHARED={'temperature','top_p','top_logprobs','logprobs','tools','functions'}

# Campaign request bound for GENERATOR only. first-shadow-v4 hit the previous
# 16000 cap (incomplete / max_output_tokens). Included in run identity.
GENERATOR_MAX_OUTPUT_TOKENS=32768
# Critic/selector completion caps. For reasoning models the cap includes
# reasoning tokens; the novelty answer alone is ~1.4k visible tokens over a
# ~38 KB context at medium effort, so 6000 risked a billed length stop.
ROLE_OUTPUT_TOKEN_CAPS={'NOVELTY_CRITIC':12000,'RED_TEAM':8000,'FEASIBILITY_CRITIC':6000,'SELECTOR':2000}

def spec(model):
    if model not in MODELS:raise ContractError('unknown model or missing verified pricing: '+str(model))
    row=MODELS[model]
    if row['STRUCTURED_OUTPUTS'] is not True:raise ContractError('model lacks verified structured outputs')
    if not row['REASONING_EFFORTS']:raise ContractError('model lacks verified reasoning_effort set')
    return row

def model_for(role):
    if role not in ROLE_MODEL_MAP:raise ContractError('unknown role for model routing')
    model=ROLE_MODEL_MAP[role];spec(model);return model

def request_params_for(role):
    if role not in ROLE_REQUEST_PARAMS:raise ContractError('unknown role for model routing')
    row=spec(model_for(role));params=dict(ROLE_REQUEST_PARAMS[role])
    if set(params)-{'reasoning_effort'}:raise ContractError('unsupported sampling parameter')
    if set(params)&FORBIDDEN_SHARED:raise ContractError('unsupported sampling parameter')
    effort=params.get('reasoning_effort')
    if effort not in row['REASONING_EFFORTS']:raise ContractError('unsupported reasoning_effort for model')
    return params

def rates(role):
    row=spec(model_for(role));return row['INPUT_RATE'],row['OUTPUT_RATE']

def price_table():
    return {name:{'INPUT_RATE':str(row['INPUT_RATE']),'OUTPUT_RATE':str(row['OUTPUT_RATE'])} for name,row in MODELS.items()}

def routing_digest():
    models={k:{n:str(v) if n.endswith('RATE') else list(v) if n=='REASONING_EFFORTS' else v for n,v in row.items()} for k,row in MODELS.items()}
    return digest({'ROLE_MODEL_MAP':ROLE_MODEL_MAP,'ROLE_REQUEST_PARAMS':ROLE_REQUEST_PARAMS,'MODELS':models,'VERIFIED':VERIFIED})
