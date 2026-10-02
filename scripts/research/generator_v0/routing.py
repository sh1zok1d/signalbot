"""Authoritative multi-provider role routing for Generator V0 (outcome-blind amendment).

Scientific code asks for a ROLE. This registry alone says which provider,
model, parameters, prices, output cap, structured-output mode and transport
implement it. The routing digest covers every field, so changing any of them
changes the campaign identity (and, through the per-role route digest carried
in every request, every call key).

The legacy OpenAI-only map in models.py (ROLE_MODEL_MAP) still drives the
`--provider openai` regression path; it is NOT the authority for routed runs.

Prices are standard (uncached, non-batch, non-priority) USD per 1M tokens.
Official sources were not re-fetched by this offline unit: OpenAI rows mirror
models.MODELS (verified 2026-09-23); Anthropic Opus 5.5 rows are the owner-
supplied standard prices (USD 4 / 20; cache read 0.20; 5m write 5; 1h write 8).
"""
from __future__ import annotations
import copy
from decimal import Decimal
from .context import ContractError,digest
from .models import GENERATOR_MAX_OUTPUT_TOKENS,ROLE_OUTPUT_TOKEN_CAPS

ROUTING_ID='GENERATOR_V0_MULTI_PROVIDER_ROUTING_V1'
ROLES=('GENERATOR','NOVELTY_CRITIC','RED_TEAM','FEASIBILITY_CRITIC','SELECTOR')
PROVIDERS=('ANTHROPIC','OPENAI')
# Owner amendment (execution headroom only): the first live compact round used
# all 32768 output tokens (17,396 thinking) and stopped at max_tokens. The
# legacy OpenAI generator cap (models.GENERATOR_MAX_OUTPUT_TOKENS) is unchanged.
ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS=100000
GENERATOR_OUTPUT_CAPS={'ANTHROPIC':ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS,'OPENAI':GENERATOR_MAX_OUTPUT_TOKENS}

ANTHROPIC_TRANSPORT={'HOST':'api.anthropic.com','METHOD':'POST','PATH':'/v1/messages','API_VERSION':'2023-06-01',
                     'AUTH':'x-api-key from ANTHROPIC_API_KEY (never persisted)','STREAM':False,'BATCH':False,
                     'PROMPT_CACHING':False,'SDK_RETRIES':False,'SYNC':True}
OPENAI_CHAT_TRANSPORT={'HOST':'api.openai.com','METHOD':'POST','PATH':'/v1/chat/completions',
                       'AUTH':'Bearer from OPENAI_API_KEY (never persisted)','STREAM':False,'BATCH':False,
                       'STORE':False,'SERVICE_TIER':'default','SDK_RETRIES':False,'SYNC':True}
# Transport reliability amendments (NOVELTY_CRITIC, then RED_TEAM): one create POST
# (never replayed), then GET polling of the same response_id, so no single HTTP
# connection is held open for a long high-reasoning Sol computation. Same background
# design as the legacy OpenAI generator (openai_provider.create_background / Caller._await_background).
OPENAI_RESPONSES_BACKGROUND_TRANSPORT={'HOST':'api.openai.com','METHOD':'POST','PATH':'/v1/responses',
                                       'POLL':'GET /v1/responses/{response_id}','CLEANUP':'DELETE /v1/responses/{response_id} (best effort, after local persist)',
                                       'AUTH':'Bearer from OPENAI_API_KEY (never persisted)','STREAM':False,'BATCH':False,
                                       'BACKGROUND':True,'STORE':True,'SERVICE_TIER':'default','SDK_RETRIES':False,'SYNC':False,
                                       'CREATE_REPLAY':False}
# ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1 (owner decision 2026-10-02, after r01 lost a
# synchronous Messages call at the 1800 s client timeout with no provider id): the GENERATOR
# request goes into a one-request Message Batch. The create POST is short and returns the batch
# id, which is journaled before any polling; afterwards the call is only polled by that id and
# never POSTed again. A create whose acknowledgement is lost is found again by its custom_id in
# the workspace batch listing. Batch pricing is 50% of standard (official pricing page,
# 2026-10-02: Claude Opus 5.5 batch input USD 2 / output USD 10 per MTok).
ANTHROPIC_BATCH_ENDPOINT='ANTHROPIC_MESSAGE_BATCHES'
BATCH_PRICES={
    'claude-opus-5-5':{'INPUT':Decimal('2.00'),'OUTPUT':Decimal('10.00'),'CACHE_READ':Decimal('0.10'),
                       'CACHE_WRITE_5M':Decimal('2.50'),'CACHE_WRITE_1H':Decimal('4.00')},
}
ANTHROPIC_BATCH_TRANSPORT={'HOST':'api.anthropic.com','METHOD':'POST','PATH':'/v1/messages/batches','API_VERSION':'2023-06-01',
                           'POLL':'GET /v1/messages/batches/{batch_id}','RESULTS':'GET /v1/messages/batches/{batch_id}/results',
                           'RECOVERY':'GET /v1/messages/batches (workspace listing); match the one-request batch by custom_id in its results',
                           'REQUESTS_PER_BATCH':1,'CUSTOM_ID':'gv0- + digest(RUN_ID, CALL_KEY)[:60]',
                           'AUTH':'x-api-key from ANTHROPIC_API_KEY (never persisted)','STREAM':False,'BATCH':True,
                           'PROMPT_CACHING':False,'SDK_RETRIES':False,'SYNC':False,'CREATE_REPLAY':False,
                           'CLEANUP':'none: the batch and its results stay with the provider as audit evidence',
                           'PRICE_BASIS':'BATCH','BATCH_PRICES':{m:{k:str(v) for k,v in row.items()} for m,row in BATCH_PRICES.items()}}
BACKGROUND_ENDPOINTS=('OPENAI_RESPONSES_BACKGROUND',ANTHROPIC_BATCH_ENDPOINT)
_ENDPOINTS={'ANTHROPIC':('ANTHROPIC_MESSAGES',ANTHROPIC_BATCH_ENDPOINT),'OPENAI':('OPENAI_CHAT_COMPLETIONS','OPENAI_RESPONSES_BACKGROUND')}

# Standard USD per 1M tokens. CACHE_* rows are used only to price usage that
# reports cache tokens; no route enables caching and no bound uses a discount.
PRICES={
    'claude-opus-5-5':{'INPUT':Decimal('4.00'),'OUTPUT':Decimal('20.00'),'CACHE_READ':Decimal('0.20'),
                       'CACHE_WRITE_5M':Decimal('5.00'),'CACHE_WRITE_1H':Decimal('8.00'),'CONTEXT_WINDOW_TOKENS':1_000_000,
                       'MAX_OUTPUT_TOKENS':128000},
    'gpt-6-sol':{'INPUT':Decimal('2.00'),'OUTPUT':Decimal('10.00'),'CONTEXT_WINDOW_TOKENS':1_000_000,'MAX_OUTPUT_TOKENS':128000},
    'gpt-6-luna':{'INPUT':Decimal('0.10'),'OUTPUT':Decimal('0.50'),'CONTEXT_WINDOW_TOKENS':1_000_000,'MAX_OUTPUT_TOKENS':128000},
}

ROUTES={
    'GENERATOR':{'PROVIDER':'ANTHROPIC','MODEL':'claude-opus-5-5','PARAMS':{'effort':'high'},
                 'MAX_OUTPUT_TOKENS':ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS,'STRUCTURED_OUTPUT':'ANTHROPIC_OUTPUT_CONFIG_JSON_SCHEMA_COMPACT_CANDIDATE_ARRAY_V1',
                 'ENDPOINT':'ANTHROPIC_MESSAGES','TRANSPORT':ANTHROPIC_TRANSPORT},
    'NOVELTY_CRITIC':{'PROVIDER':'OPENAI','MODEL':'gpt-6-sol','PARAMS':{'reasoning_effort':'high'},
                      'MAX_OUTPUT_TOKENS':ROLE_OUTPUT_TOKEN_CAPS['NOVELTY_CRITIC'],'STRUCTURED_OUTPUT':'OPENAI_RESPONSES_TEXT_FORMAT_JSON_SCHEMA_STRICT',
                      'ENDPOINT':'OPENAI_RESPONSES_BACKGROUND','TRANSPORT':OPENAI_RESPONSES_BACKGROUND_TRANSPORT},
    'RED_TEAM':{'PROVIDER':'OPENAI','MODEL':'gpt-6-sol','PARAMS':{'reasoning_effort':'high'},
                'MAX_OUTPUT_TOKENS':ROLE_OUTPUT_TOKEN_CAPS['RED_TEAM'],'STRUCTURED_OUTPUT':'OPENAI_RESPONSES_TEXT_FORMAT_JSON_SCHEMA_STRICT',
                'ENDPOINT':'OPENAI_RESPONSES_BACKGROUND','TRANSPORT':OPENAI_RESPONSES_BACKGROUND_TRANSPORT},
    'FEASIBILITY_CRITIC':{'PROVIDER':'OPENAI','MODEL':'gpt-6-luna','PARAMS':{'reasoning_effort':'low'},
                          'MAX_OUTPUT_TOKENS':ROLE_OUTPUT_TOKEN_CAPS['FEASIBILITY_CRITIC'],'STRUCTURED_OUTPUT':'OPENAI_CHAT_RESPONSE_FORMAT_JSON_SCHEMA_STRICT',
                          'ENDPOINT':'OPENAI_CHAT_COMPLETIONS','TRANSPORT':OPENAI_CHAT_TRANSPORT},
    # Advisory only: the deterministic ordinal order is authoritative (runner._selector_advisory).
    'SELECTOR':{'PROVIDER':'OPENAI','MODEL':'gpt-6-luna','PARAMS':{'reasoning_effort':'none'},
                'MAX_OUTPUT_TOKENS':ROLE_OUTPUT_TOKEN_CAPS['SELECTOR'],'STRUCTURED_OUTPUT':'OPENAI_CHAT_RESPONSE_FORMAT_JSON_SCHEMA_STRICT',
                'ENDPOINT':'OPENAI_CHAT_COMPLETIONS','TRANSPORT':OPENAI_CHAT_TRANSPORT,'ADVISORY_ONLY':True},
}

# OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1 (owner decision 2026-10-02, after r02 lost a
# synchronous FEASIBILITY_CRITIC Chat Completions call at the client timeout with no response id).
# Ladder campaigns only. GENERATOR stays on Message Batches. NOVELTY_CRITIC and RED_TEAM stay on
# background Responses. FEASIBILITY_CRITIC and SELECTOR move from synchronous Chat Completions to
# the same background Responses transport. Model, reasoning effort, output cap, prompt and schema
# are unchanged; only the endpoint, transport and structured-output wire wrapper change.
# ROUTES (V02, first-30-card) is unchanged.
OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1='OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1'

def _background_responses_route(route):
    """Same scientific route, served by resumable background Responses."""
    return {**copy.deepcopy(route),'STRUCTURED_OUTPUT':'OPENAI_RESPONSES_TEXT_FORMAT_JSON_SCHEMA_STRICT',
            'ENDPOINT':'OPENAI_RESPONSES_BACKGROUND','TRANSPORT':OPENAI_RESPONSES_BACKGROUND_TRANSPORT}

LADDER_ROUTES={**copy.deepcopy(ROUTES),
               'GENERATOR':{**copy.deepcopy(ROUTES['GENERATOR']),'ENDPOINT':ANTHROPIC_BATCH_ENDPOINT,'TRANSPORT':ANTHROPIC_BATCH_TRANSPORT},
               'FEASIBILITY_CRITIC':_background_responses_route(ROUTES['FEASIBILITY_CRITIC']),
               'SELECTOR':_background_responses_route(ROUTES['SELECTOR'])}

def routes_for_contract(contract_id):
    """V03 ladder runs use the batch generator; every other run keeps ROUTES."""
    return LADDER_ROUTES if contract_id=='GENERATOR_CONTRACT_V03' else ROUTES

def prices_for(r):
    """USD per 1M tokens actually charged on this route (batch routes: the batch table)."""
    return BATCH_PRICES[r['MODEL']] if r['ENDPOINT']==ANTHROPIC_BATCH_ENDPOINT else PRICES[r['MODEL']]

_REQUIRED=('PROVIDER','MODEL','PARAMS','MAX_OUTPUT_TOKENS','STRUCTURED_OUTPUT','ENDPOINT','TRANSPORT')
_EFFORTS={'ANTHROPIC':('effort',('low','medium','high','xhigh','max')),
          'OPENAI':('reasoning_effort',('none','low','medium','high','xhigh','max'))}

def validate_routes(routes=None):
    """Fail closed on any incomplete or inconsistent route table."""
    routes=ROUTES if routes is None else routes
    if set(routes)!=set(ROLES):raise ContractError('routing must cover exactly the Generator V0 roles')
    for role,r in routes.items():
        if any(k not in r for k in _REQUIRED):raise ContractError('incomplete route for '+role)
        if r['PROVIDER'] not in PROVIDERS:raise ContractError('unknown provider for '+role)
        if r['MODEL'] not in PRICES:raise ContractError('no verified price for '+role+' model')
        if r['ENDPOINT'] not in _ENDPOINTS[r['PROVIDER']]:raise ContractError('unsupported endpoint for '+role)
        if role=='GENERATOR' and r['ENDPOINT']=='OPENAI_RESPONSES_BACKGROUND':raise ContractError('routed GENERATOR is not a background Responses route')
        if r['ENDPOINT']==ANTHROPIC_BATCH_ENDPOINT:
            if role!='GENERATOR':raise ContractError('Message Batches serve the GENERATOR only')
            if r['TRANSPORT']!=ANTHROPIC_BATCH_TRANSPORT or r['MODEL'] not in BATCH_PRICES:raise ContractError('batch route without the frozen batch transport and price')
        key,allowed=_EFFORTS[r['PROVIDER']]
        if set(r['PARAMS'])!={key} or r['PARAMS'][key] not in allowed:raise ContractError('unsupported effort parameters for '+role)
        cap=r['MAX_OUTPUT_TOKENS']
        if type(cap)!=int or not 1<=cap<=PRICES[r['MODEL']]['MAX_OUTPUT_TOKENS']:raise ContractError('output cap for '+role)
        # The routing layer never changes the scientific run shape.
        expected=GENERATOR_OUTPUT_CAPS[r['PROVIDER']] if role=='GENERATOR' else ROLE_OUTPUT_TOKEN_CAPS[role]
        if cap!=expected:raise ContractError('route output cap differs from the frozen run shape for '+role)
    return routes

def route(role,routes=None):
    routes=validate_routes(routes)
    if role not in routes:raise ContractError('unknown role for routing: '+str(role))
    return copy.deepcopy(routes[role])

def role_route_digest(role,routes=None):
    """Identity of one role's route (carried in every request, hence the call key)."""
    r=route(role,routes)
    return digest({'ROUTING_ID':ROUTING_ID,'ROLE':role,'ROUTE':r,'PRICES':price_row(r['MODEL'])})

def price_row(model):
    if model not in PRICES:raise ContractError('no verified price for model '+str(model))
    return {k:(str(v) if isinstance(v,Decimal) else v) for k,v in PRICES[model].items()}

def price_table(routes=None):
    routes=validate_routes(routes)
    return {m:price_row(m) for m in sorted({r['MODEL'] for r in routes.values()})}

def role_provider_map(routes=None):
    return {role:r['PROVIDER'] for role,r in validate_routes(routes).items()}

def role_model_map(routes=None):
    return {role:r['MODEL'] for role,r in validate_routes(routes).items()}

def role_params(routes=None):
    return {role:dict(r['PARAMS']) for role,r in validate_routes(routes).items()}

def routing_digest(routes=None):
    """Covers provider, model, effort, prices, output caps, structured-output mode and transport."""
    routes=validate_routes(routes)
    return digest({'ROUTING_ID':ROUTING_ID,'ROUTES':routes,'PRICES':price_table(routes)})

def routing_table(routes=None):
    """Human-readable preflight rows."""
    return {role:'{} / {} / {}'.format(r['PROVIDER'],r['MODEL'],'/'.join('{}={}'.format(k,v) for k,v in r['PARAMS'].items()))
            for role,r in validate_routes(routes).items()}
