"""Outcome-blind multi-provider routing (Opus generator, Sol/Luna critics). Offline only:
fake transports, dummy keys, no network, no real API call."""
import copy
import hashlib
import json
import random
import pytest
from pathlib import Path
from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider,usage_cost,classify_anthropic_http,FORBIDDEN_BODY_KEYS,INPUT_OVERHEAD_TOKENS
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.routed_provider import RoutedProvider,offline_routed_provider,routed_run_identity
from scripts.research.generator_v0.output_schemas import (role_schema,anthropic_projection,anthropic_subset_violations,anthropic_output_schema,
    strict_subset_violations,anthropic_generator_compact_schema,ANTHROPIC_GENERATOR_WIRE_FORMAT)
from scripts.research.generator_v0.provider import Caller,ProviderFailure,ProviderRejected,BilledFailure,Response
from scripts.research.generator_v0.ledger import Ledger,CallUncertain,BudgetExceeded
from scripts.research.generator_v0.runner import GENERATOR_PROMPT,generator_request_parameters,generator_identity,run_campaign,accept_budget_stop
from scripts.research.generator_v0.roles import Roles,NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS,GENERATOR_MAX_OUTPUT_TOKENS
GEN_CAP=routing.ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS
from scripts.research.generator_v0_gate.noisy import NoisyTransport,routed_provider_for,run_mixed_noisy_campaign,Crash,CAP

C=Contexts()
REPO=Path(__file__).resolve().parents[2]
SLOTS=slot_plan(40)[:10]
AKEY='sk-ant-test-DO-NOT-PERSIST-0123456789'
OKEY='sk-openai-test-DO-NOT-PERSIST-9876543210'

def env(text,stop='end_turn',model='claude-opus-5-5',mid='msg_test_1',usage=None,blocks=None):
    content=blocks if blocks is not None else [{'type':'thinking','thinking':'','signature':'opaque'},{'type':'text','text':text}]
    body={'id':mid,'type':'message','role':'assistant','model':model,'content':content,'stop_reason':stop,'stop_sequence':None}
    if usage is not False:body['usage']=usage if usage is not None else {'input_tokens':6000,'output_tokens':9000}
    return json.dumps(body).encode()

def gen_json():
    keyed=json.loads(MockResponder(C)({'role':'GENERATOR','context':C.generator(),'parameters':{'slots':SLOTS}}))
    return canonical({'CANDIDATES':list(keyed['CANDIDATES'].values())})   # Anthropic compact wire

class Fake:
    """Scripted transport: a list of (status, wire) or exceptions, consumed in order."""
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def __call__(self,method,path,body,headers,timeout):
        self.calls.append((method,path,json.loads(body) if body else None,dict(headers)))
        a=self.answers.pop(0)
        if isinstance(a,BaseException):raise a
        return a

def anthropic(transport,cap=CAP):
    return AnthropicProvider(AKEY,allow_real=True,budget_micro_usd=cap,transport=transport,contexts=C)

def openai(transport,cap=CAP):
    return OpenAIProvider(OKEY,allow_real=True,budget_micro_usd=cap,transport=transport,contexts=C,routes=routing.ROUTES,sleeper=lambda s:None)

def router(atransport,otransport,cap=CAP):
    return RoutedProvider({'ANTHROPIC':anthropic(atransport,cap),'OPENAI':openai(otransport,cap)},routing.ROUTES,sleeper=lambda s:None)

def gen_request(caller):
    return caller.request('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(SLOTS,GEN_CAP),'generation:0',0,generator_identity(C,SLOTS))

def critic_request(caller,role,prompt):
    cards=[fixture(s,C) for s in slot_plan(40)]
    ctx=Roles(C,caller).request(role,cards[2],cards if role=='NOVELTY_CRITIC' else None)
    return caller.request(role,ctx,prompt,{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS[role]},role+':C003')

def gen_call(caller):
    return caller.call('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(SLOTS,GEN_CAP),'generation:0',identity=generator_identity(C,SLOTS))

# ------------------------------------------------------------ A. routing

EXPECTED={'GENERATOR':('ANTHROPIC','claude-opus-5-5',{'effort':'high'}),
          'NOVELTY_CRITIC':('OPENAI','gpt-6-sol',{'reasoning_effort':'high'}),
          'RED_TEAM':('OPENAI','gpt-6-sol',{'reasoning_effort':'high'}),
          'FEASIBILITY_CRITIC':('OPENAI','gpt-6-luna',{'reasoning_effort':'low'}),
          'SELECTOR':('OPENAI','gpt-6-luna',{'reasoning_effort':'none'})}

def test_each_role_resolves_to_the_expected_provider_model_and_effort():
    p=offline_routed_provider(C)
    for role,(prov,model,params) in EXPECTED.items():
        assert (p.provider_for(role),p.model_for(role),p.request_params_for(role))==(prov,model,params)
        assert routing.route(role)['MAX_OUTPUT_TOKENS']==(GEN_CAP if role=='GENERATOR' else ROLE_OUTPUT_TOKEN_CAPS[role])
    assert routing.ROUTES['SELECTOR'].get('ADVISORY_ONLY') is True

def test_unknown_role_fails_closed():
    p=offline_routed_provider(C)
    for fn in (routing.route,p.model_for,p.request_params_for,p.endpoint_for,p.provider_for):
        with pytest.raises(ContractError):fn('SECOND_OPINION')
    with pytest.raises(ContractError):p.bound({'role':'SECOND_OPINION','parameters':{'max_output_tokens':10},'context':{},'prompt':''})

@pytest.mark.parametrize('mutate',[
    lambda r:r['GENERATOR'].update(PROVIDER='OPENAI'),
    lambda r:r['GENERATOR'].update(MODEL='gpt-6-sol'),
    lambda r:r['GENERATOR'].update(PARAMS={'effort':'xhigh'}),
    lambda r:r['NOVELTY_CRITIC'].update(PARAMS={'reasoning_effort':'medium'}),
    lambda r:r['RED_TEAM'].update(MODEL='gpt-6-luna'),
    lambda r:r['FEASIBILITY_CRITIC'].update(STRUCTURED_OUTPUT='JSON_MODE'),
    lambda r:r['GENERATOR'].update(TRANSPORT=dict(r['GENERATOR']['TRANSPORT'],BATCH=True)),
    lambda r:r['SELECTOR'].update(ENDPOINT='OPENAI_RESPONSES'),
],ids=['provider','model','effort','critic-effort','critic-model','structured-mode','transport','endpoint'])
def test_changing_any_route_field_changes_the_routing_digest(mutate):
    r=copy.deepcopy(routing.ROUTES);mutate(r)
    try:d=routing.routing_digest(r)
    except ContractError:return          # an unpriced/invalid route is refused outright
    assert d!=routing.routing_digest()

def test_price_and_cap_changes_change_digest_or_fail_closed(monkeypatch):
    base=routing.routing_digest()
    prices=copy.deepcopy(routing.PRICES);prices['claude-opus-5-5']['OUTPUT']=routing.Decimal('25.00')
    monkeypatch.setattr(routing,'PRICES',prices)
    assert routing.routing_digest()!=base
    monkeypatch.undo()
    r=copy.deepcopy(routing.ROUTES);r['GENERATOR']['MAX_OUTPUT_TOKENS']=16000
    with pytest.raises(ContractError,match='frozen run shape'):routing.routing_digest(r)

@pytest.mark.parametrize('mutate',[lambda r:r.pop('SELECTOR'),lambda r:r['GENERATOR'].update(PROVIDER='GOOGLE'),
                                   lambda r:r['GENERATOR'].update(PARAMS={'reasoning_effort':'high'}),lambda r:r['RED_TEAM'].update(MODEL='gpt-6-astra')])
def test_incomplete_or_inconsistent_routes_fail_closed(mutate):
    r=copy.deepcopy(routing.ROUTES);mutate(r)
    with pytest.raises(ContractError):routing.validate_routes(r)

# ------------------------------------------------------- B. RoutedProvider

def test_router_dispatches_each_role_to_its_provider_only():
    at=Fake((200,env(gen_json())));ot=NoisyTransport(C,{})
    p=router(at,ot);l=Ledger(':memory:',{'RUN_ID':'r'});cal=Caller(C,l,p,CAP,True)
    raw=gen_call(cal)
    assert [x[1] for x in at.calls]==['/v1/messages'] and ot.log==[]
    Roles(C,cal).feasibility(fixture(SLOTS[0],C))
    assert [x[1] for x in ot.log]==['/v1/chat/completions'] and len(at.calls)==1
    assert [x['CANDIDATE_ID'] for x in json.loads(raw)['CANDIDATES']]==[s['CANDIDATE_ID'] for s in SLOTS]

def test_bound_uses_the_routed_provider():
    p=offline_routed_provider(C);cal=Caller(C,Ledger(':memory:',{'RUN_ID':'b'}),p,1,True)
    g=gen_request(cal);f=critic_request(cal,'FEASIBILITY_CRITIC',FEAS_PROMPT)
    assert p.bound(g)==p.adapters['ANTHROPIC'].bound(g)
    assert p.bound(f)==p.adapters['OPENAI'].bound(f)
    with pytest.raises(ContractError,match='not routed to OpenAI'):p.adapters['OPENAI'].bound(g)
    with pytest.raises(ContractError,match='not routed to Anthropic'):p.adapters['ANTHROPIC'].bound(f)

def test_provider_model_and_route_identity_are_in_the_call_key():
    p=offline_routed_provider(C);cal=Caller(C,Ledger(':memory:',{'RUN_ID':'k'}),p,1,True)
    g=gen_request(cal)
    assert (g['provider'],g['model'],g['route_provider'],g['model_request_params'])==('ANTHROPIC_MESSAGES','claude-opus-5-5','ANTHROPIC',{'effort':'high'})
    assert g['route_digest']==routing.role_route_digest('GENERATOR')
    moved=dict(g,provider='OPENAI_CHAT_COMPLETIONS',model='gpt-6-sol',route_provider='OPENAI',model_request_params={'reasoning_effort':'high'},route_digest=routing.role_route_digest('NOVELTY_CRITIC'))
    assert digest(moved)!=digest(g)
    with pytest.raises(ContractError,match='does not match the route'):p.bound(moved)
    for field,value in (('model','gpt-6-sol'),('route_provider','OPENAI'),('provider','OPENAI_CHAT_COMPLETIONS'),('route_digest','x')):
        with pytest.raises(ContractError):p.complete(dict(g,**{field:value}))

def test_router_refuses_missing_or_extra_adapters():
    with pytest.raises(ContractError):RoutedProvider({'ANTHROPIC':offline_routed_provider(C).adapters['ANTHROPIC']})
    with pytest.raises(ContractError):RoutedProvider({'OPENAI':OpenAIProvider(OKEY,allow_real=True,budget_micro_usd=CAP,contexts=C)})

# --------------------------------------------------- C. Anthropic payload

def test_opus_generator_request_shape():
    cal=Caller(C,Ledger(':memory:',{'RUN_ID':'c'}),offline_routed_provider(C),1,True)
    req=gen_request(cal);body=offline_routed_provider(C).adapters['ANTHROPIC'].payload(req)
    assert set(body)=={'model','max_tokens','system','messages','stream','output_config'}
    assert body['model']=='claude-opus-5-5' and body['max_tokens']==GEN_CAP and body['stream'] is False
    assert body['system']==GENERATOR_PROMPT
    assert body['messages']==[{'role':'user','content':canonical({'context':C.generator(),'slots':SLOTS})}]
    assert body['output_config']['effort']=='high' and body['output_config']['format']['type']=='json_schema'
    assert not any(k in body for k in FORBIDDEN_BODY_KEYS)
    assert 'thinking' not in canonical(body).split('"messages"')[0]+canonical(body['output_config'])
    compact=anthropic_generator_compact_schema(C,req)
    assert body['output_config']['format']['schema']==anthropic_projection(compact)[0]==anthropic_output_schema('GENERATOR',C,req)
    assert req['provider_wire_format']==ANTHROPIC_GENERATOR_WIRE_FORMAT
    assert req['provider_schema_digest']==digest(body['output_config']['format']['schema'])

def test_anthropic_projection_removes_only_unsupported_constraints_which_intake_still_enforces():
    exact=role_schema('GENERATOR',C,provider=True,request={'parameters':{'slots':SLOTS}})
    proj,removed=anthropic_projection(exact)
    assert sorted({k for _,k,_ in removed})==['maxItems','maximum','minimum'] and len(removed)==30
    def restore(node,path):
        for p,k,v in removed:
            if p==path:node[k]=v
        for key,sub in (node.get('properties') or {}).items():restore(sub,path+'/'+key)
        if 'items' in node:restore(node['items'],path+'/items')
        return node
    assert restore(copy.deepcopy(proj),'#')==exact
    assert anthropic_subset_violations(proj)==[] and anthropic_subset_violations(exact)!=[]

def test_payload_rejects_a_different_output_cap():
    cal=Caller(C,Ledger(':memory:',{'RUN_ID':'c2'}),offline_routed_provider(C),1,True)
    req=gen_request(cal);req['parameters']=dict(req['parameters'],max_output_tokens=16000)
    with pytest.raises(ContractError,match='differs from the route'):offline_routed_provider(C).adapters['ANTHROPIC'].payload(req)

# ---------------------------------------------------- D. Anthropic envelopes

def complete_with(wire,status=200):
    a=anthropic(Fake((status,wire)));cal=Caller(C,Ledger(':memory:',{'RUN_ID':'d'}),offline_routed_provider(C),1,True)
    return a.complete(gen_request(cal))

def test_end_turn_text_is_returned_verbatim_and_thinking_is_dropped():
    text=gen_json();wire=env(text)
    r=complete_with(wire)
    assert r.raw==text and r.wire_sha256==hashlib.sha256(wire).hexdigest() and 'opaque' not in r.raw
    assert r.cost_micro_usd==4*6000+20*9000

def test_text_only_end_turn_is_usable():
    r=complete_with(env(gen_json(),blocks=[{'type':'text','text':gen_json()}]))
    assert r.raw==gen_json()

@pytest.mark.parametrize('label,wire,billed_cost',[
    ('max_tokens',env('{"CAND',stop='max_tokens',usage={'input_tokens':6000,'output_tokens':GEN_CAP}),True),
    ('refusal',env('',stop='refusal',blocks=[]),True),
    ('context',env('x',stop='model_context_window_exceeded'),True),
    ('tool_use',env('x',stop='tool_use',blocks=[{'type':'tool_use','id':'t','name':'x','input':{}}]),True),
    ('tool_block_end_turn',env('x',blocks=[{'type':'tool_use','id':'t','name':'x','input':{}},{'type':'text','text':'{}'}]),True),
    ('two_text_blocks',env('x',blocks=[{'type':'text','text':'{}'},{'type':'text','text':'{}'}]),True),
    ('empty_text',env('',blocks=[{'type':'text','text':''}]),True),
    ('wrong_model',env(gen_json(),model='claude-opus-5'),True),
    ('wrong_id',env(gen_json(),mid='resp_123'),True),
    ('missing_usage',env(gen_json(),usage=False),False),
    ('malformed_usage',env(gen_json(),usage={'input_tokens':'many','output_tokens':1}),False),
    ('negative_usage',env(gen_json(),usage={'input_tokens':-1,'output_tokens':1}),False),
    ('usage_over_bound',env(gen_json(),usage={'input_tokens':6000,'output_tokens':GEN_CAP+1}),False),
    ('not_json',b'<html>ok</html>',False),
])
def test_unusable_200_responses_are_billed_failures(label,wire,billed_cost):
    with pytest.raises(ProviderFailure) as e:complete_with(wire)
    assert e.value.billing=='BILLED'
    assert (e.value.cost is not None)==billed_cost,label
    if e.value.envelope:assert set(e.value.envelope)<={'message_id','stop_reason'}

def test_oversized_response_is_uncertain():
    with pytest.raises(ProviderFailure) as e:complete_with(b'{'+b' '*4_000_001+b'}')
    assert e.value.billing=='UNCERTAIN'

# ------------------------------------------------------- E. usage / cost

def test_usage_cost_accounting():
    big=10**7
    rec,cost=usage_cost({'input_tokens':1000,'output_tokens':2000},'claude-opus-5-5',big,big)
    assert cost==4*1000+20*2000 and rec['input_tokens']==1000
    rec,cost=usage_cost({'input_tokens':10,'output_tokens':10,'thinking_tokens':7},'claude-opus-5-5',big,big)
    assert rec['thinking_tokens']==7 and cost==240                    # output is authoritative, no thinking surcharge
    assert usage_cost({'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':1000},'claude-opus-5-5',big,big)[1]==200
    assert usage_cost({'input_tokens':0,'output_tokens':0,'cache_creation_input_tokens':1000,'cache_creation':{'ephemeral_5m_input_tokens':1000}},'claude-opus-5-5',big,big)[1]==5000
    assert usage_cost({'input_tokens':0,'output_tokens':0,'cache_creation_input_tokens':1000,'cache_creation':{'ephemeral_1h_input_tokens':1000}},'claude-opus-5-5',big,big)[1]==8000
    assert usage_cost({'input_tokens':0,'output_tokens':0,'cache_creation_input_tokens':1000},'claude-opus-5-5',big,big)[1]==8000   # unsplit: higher 1h rate
    assert usage_cost({'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':1},'claude-opus-5-5',big,big)[1]==1             # ROUND_CEILING
    with pytest.raises(ValueError):usage_cost({'input_tokens':0,'output_tokens':0,'cache_creation_input_tokens':1,'cache_creation':{'ephemeral_5m_input_tokens':2}},'claude-opus-5-5',big,big)
    with pytest.raises(ValueError):usage_cost({'input_tokens':5,'output_tokens':0},'claude-opus-5-5',4,big)

def test_recorded_cost_never_exceeds_the_reserved_bound():
    rng=random.Random(55)
    cal=Caller(C,Ledger(':memory:',{'RUN_ID':'e'}),offline_routed_provider(C),1,True);req=gen_request(cal)
    bound=offline_routed_provider(C).adapters['ANTHROPIC'].bound(req)
    maxin,maxout=offline_routed_provider(C).adapters['ANTHROPIC'].bounds(req)
    for _ in range(200):
        u={'input_tokens':rng.randint(0,maxin),'output_tokens':rng.randint(0,maxout)}
        if rng.random()<0.5:
            left=maxin-u['input_tokens'];cw=rng.randint(0,left);u['cache_creation_input_tokens']=cw
            u['cache_creation']={'ephemeral_1h_input_tokens':rng.randint(0,cw)};u['cache_read_input_tokens']=rng.randint(0,left-cw)
        try:r=anthropic(Fake((200,env(gen_json(),usage=u)))).complete(req);cost=r.cost_micro_usd
        except ProviderFailure as e:cost=e.cost
        assert cost is None or cost<=bound

# ------------------------------------------------ F. failure injection

def caller_with(at,cap=CAP):
    l=Ledger(':memory:',{'RUN_ID':'f'});return Caller(C,l,router(at,NoisyTransport(C,{}),cap),cap,True),l

def states(l):return [r['STATE'] for r in l.export_calls()]

@pytest.mark.parametrize('status',[400,401,403,404,413,402])
def test_deterministic_rejections_are_not_billed_and_pause(status):
    cal,l=caller_with(Fake((status,b'{"type":"error","error":{"type":"invalid_request_error","message":"no"}}')))
    with pytest.raises(ProviderRejected):gen_call(cal)
    assert states(l)==['FAILED_NOT_BILLED'] and l.spent_micro_usd()==0

DOCUMENTED=[(429,'rate_limit_error'),(529,'overloaded_error')]

def documented(status,etype):
    return json.dumps({'type':'error','error':{'type':etype,'message':'x'}}).encode()

@pytest.mark.parametrize('status,etype',DOCUMENTED)
def test_documented_rate_limit_and_overload_are_uncertain_not_replayable(status,etype):
    """Anthropic error semantics do not establish that no model work occurred."""
    assert classify_anthropic_http(status,documented(status,etype))==('UNCERTAIN',False)

@pytest.mark.parametrize('status,etype',DOCUMENTED)
def test_documented_rate_limit_and_overload_post_once_and_pause(status,etype):
    at=Fake((status,documented(status,etype)),(200,env(gen_json())));cal,l=caller_with(at)
    with pytest.raises(CallUncertain):gen_call(cal)                      # existing uncertain-call mechanism
    assert len(at.calls)==1 and states(l)==['UNCERTAIN']
    with pytest.raises(CallUncertain):gen_call(cal)                      # resume never replays it
    assert len(at.calls)==1 and states(l)==['UNCERTAIN']
    row=l.export_calls()[0]
    # Conservative accounting: the reservation stays charged in the shared pool.
    assert l.spent_micro_usd()==l.total_charged_micro_usd()==row['RESERVED_MICRO_USD']>0
    assert l.unresolved_calls()==[{'CALL_KEY':row['CALL_KEY'],'STATE':'UNCERTAIN','RESERVED_MICRO_USD':row['RESERVED_MICRO_USD']}]
    with pytest.raises(ContractError,match='provider-side evidence'):l.reconcile(row['CALL_KEY'],'NOT_BILLED',None,'op','it was only a 429')
    out=l.reconcile(row['CALL_KEY'],'UNKNOWN',None,'op','no provider-side evidence')
    assert out['COST_MICRO_USD']==row['RESERVED_MICRO_USD'] and l.spent_micro_usd()==row['RESERVED_MICRO_USD']
    from scripts.research.generator_v0.provider import CallClosed
    for attempt in (0,1):
        with pytest.raises(CallClosed):
            cal.call('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(SLOTS,GEN_CAP),'generation:0',content_attempt=attempt,identity=generator_identity(C,SLOTS))
    assert len(at.calls)==1

def test_uncertain_429_reservation_counts_against_the_shared_cross_provider_ceiling():
    probe=offline_routed_provider(C);pc=Caller(C,Ledger(':memory:',{'RUN_ID':'p2'}),probe,1,True)
    gbound=probe.bound(gen_request(pc));fbound=probe.bound(critic_request(pc,'FEASIBILITY_CRITIC',FEAS_PROMPT))
    cap=gbound+fbound-1;ot=NoisyTransport(C,{})
    l=Ledger(':memory:',{'RUN_ID':'h2'});cal=Caller(C,l,router(Fake((429,documented(429,'rate_limit_error'))),ot,cap),cap,True)
    with pytest.raises(CallUncertain):gen_call(cal)
    assert l.total_charged_micro_usd()==gbound
    with pytest.raises(BudgetExceeded):Roles(C,cal).feasibility(fixture(SLOTS[0],C))
    assert ot.log==[] and l.total_charged_micro_usd()==gbound

def test_not_billed_outcomes_still_cost_zero():
    cal,l=caller_with(Fake((400,documented(400,'invalid_request_error'))))
    with pytest.raises(ProviderRejected):gen_call(cal)
    assert states(l)==['FAILED_NOT_BILLED'] and l.spent_micro_usd()==0 and l.export_calls()[0]['COST_MICRO_USD']==0

@pytest.mark.parametrize('status,wire',[(429,b'proxy says slow down'),(500,b'{"type":"error","error":{"type":"api_error"}}'),(502,b'bad gateway'),
                                        (504,b'gateway'),(529,b'not the documented envelope'),(408,b''),(503,b''),
                                        (429,b'{"type":"error","error":{"type":"overloaded_error"}}'),(529,b'{"type":"error","error":{"type":"rate_limit_error"}}')])
def test_ambiguous_http_failures_are_uncertain_and_never_resent(status,wire):
    at=Fake((status,wire));cal,l=caller_with(at)
    with pytest.raises(CallUncertain):gen_call(cal)
    assert states(l)==['UNCERTAIN']
    with pytest.raises(CallUncertain):gen_call(cal)
    assert len(at.calls)==1

@pytest.mark.parametrize('exc',[ConnectionResetError('reset'),TimeoutError('read timeout'),OSError('network down')])
def test_connection_failure_and_timeout_after_dispatch_are_uncertain(exc):
    at=Fake(exc);cal,l=caller_with(at)
    with pytest.raises(CallUncertain):gen_call(cal)
    with pytest.raises(CallUncertain):gen_call(cal)
    assert states(l)==['UNCERTAIN'] and len(at.calls)==1

def test_malformed_200_is_billed_at_the_reservation():
    cal,l=caller_with(Fake((200,b'not json')))
    with pytest.raises(BilledFailure):gen_call(cal)
    row=l.export_calls()[0]
    assert row['STATE']=='FAILED_WITH_COST' and row['COST_BASIS']=='RESERVED_BOUND' and row['COST_MICRO_USD']==row['RESERVED_MICRO_USD']

def test_crash_after_dispatch_is_never_reposted_on_resume():
    at=Fake(Crash('died after POST'),(200,env(gen_json())));cal,l=caller_with(at)
    with pytest.raises(Crash):gen_call(cal)
    assert states(l)==['DISPATCHED']
    with pytest.raises(CallUncertain):gen_call(cal)
    assert len(at.calls)==1
    with pytest.raises(ContractError,match='provider-side evidence'):l.reconcile(l.export_calls()[0]['CALL_KEY'],'NOT_BILLED',None,'op','assert')

# -------------------------------------------- G / I. mixed campaign + provenance

@pytest.fixture(scope='module')
def mixed(tmp_path_factory):
    report,l,t=run_mixed_noisy_campaign(tmp_path_factory.mktemp('mixed')/'m')
    yield report,l,t
    l.close()

def test_mixed_campaign_reaches_human_review_with_each_role_on_its_route(mixed):
    report,l,t=mixed
    assert report['STATUS']=='PENDING_HUMAN_REVIEW' and report['STEPS'][-1]=='FINAL: PENDING_HUMAN_REVIEW'
    assert report['ROLE_ROUTES']=={'FEASIBILITY_CRITIC':['OPENAI / OPENAI_CHAT_COMPLETIONS / gpt-6-luna'],
                                   'GENERATOR':['ANTHROPIC / ANTHROPIC_MESSAGES / claude-opus-5-5'],
                                   'NOVELTY_CRITIC':['OPENAI / OPENAI_RESPONSES_BACKGROUND / gpt-6-sol'],
                                   'RED_TEAM':['OPENAI / OPENAI_CHAT_COMPLETIONS / gpt-6-sol'],
                                   'SELECTOR':['OPENAI / OPENAI_CHAT_COMPLETIONS / gpt-6-luna']}
    assert report['POSTS']==report['JOURNAL_ROWS']
    gen_posts=report['POSTS_BY_PATH']['/v1/messages']
    assert gen_posts==sum(1 for r in l.export_calls() if r['ROLE']=='GENERATOR')
    assert 'NOT_BILLED_WITHOUT_EVIDENCE_REFUSED' in report['STEPS'] and report['SPEND']['UNRESOLVED_CALLS']==[]

def test_mixed_campaign_anthropic_429_is_uncertain_and_never_replayed(mixed):
    report,l,t=mixed
    assert report['STEPS'][:2]==['PAUSED: PAUSED_UNCERTAIN_CALL','RECONCILED_UNKNOWN: generation:0']
    gen0=[r for r in l.export_calls() if r['SLOT']=='generation:0']
    assert [r['STATE'] for r in gen0]==['RECONCILED_UNKNOWN'] and t.counts[('GENERATOR',0)]==1       # exactly one POST
    assert gen0[0]['COST_MICRO_USD']==gen0[0]['RESERVED_MICRO_USD']                                   # charged conservatively
    slots=['C%03d'%i for i in range(1,11)]
    hard={h for h in report['HARD_FAIL_IDS']};assert set(slots)<=hard
    assert not [k for k in t.counts if k[0]!='GENERATOR' and k[1] in slots]                            # no critic call for them
    assert all(r['COST_MICRO_USD']==0 for r in l.export_calls() if r['STATE']=='FAILED_NOT_BILLED')   # OpenAI 429 retry: free
    assert l.total_charged_micro_usd()==report['SPEND']['TOTAL_MICRO_USD']<=CAP

def test_every_complete_call_records_full_provenance(mixed):
    report,l,t=mixed
    rows={k:(json.loads(req),json.loads(resp)) for k,req,resp in l.db.execute("SELECT key,request,response FROM calls WHERE state='COMPLETE'")}
    exported={r['CALL_KEY']:r for r in l.export_calls()}
    assert len(rows)==report['CALL_STATES']['COMPLETE']
    for key,(req,resp) in rows.items():
        e=exported[key]
        assert digest(req)==key
        assert e['ROUTE_PROVIDER']==routing.ROUTES[req['role']]['PROVIDER'] and e['MODEL_PROVIDER']==routing.ROUTES[req['role']]['ENDPOINT']
        assert e['MODEL_ID']==routing.ROUTES[req['role']]['MODEL'] and e['ROUTE_DIGEST']==routing.role_route_digest(req['role'])
        assert resp['raw_sha256']==hashlib.sha256(resp['raw'].encode()).hexdigest() and len(resp['wire_sha256'])==64
        assert isinstance(e['USAGE'],dict) and 0<=e['COST_MICRO_USD']<=e['RESERVED_MICRO_USD']

def test_no_provider_identity_leaks_into_critic_prompts(mixed):
    report,l,t=mixed
    ot=NoisyTransport(C,{});p=router(Fake(),ot);cal=Caller(C,Ledger(':memory:',{'RUN_ID':'leak'}),p,CAP,True)
    for role,prompt in (('NOVELTY_CRITIC',NOVELTY_PROMPT),('FEASIBILITY_CRITIC',FEAS_PROMPT),('RED_TEAM',RED_PROMPT)):
        body=canonical(p.adapters['OPENAI'].chat_payload(critic_request(cal,role,prompt))).casefold()
        for word in ('anthropic','claude','opus','route_provider','route_digest','generated by'):assert word not in body,(role,word)
    # The same holds for the critic calls that actually ran in the mixed campaign.
    for (req,) in l.db.execute("SELECT request FROM calls"):
        r=json.loads(req)
        if r['role']!='GENERATOR':assert not any(w in canonical({'context':r['context'],'prompt':r['prompt']}).casefold() for w in ('anthropic','claude','opus'))

# --------------------------------------------------------------- H. budget

def test_one_campaign_ceiling_spans_both_providers():
    """After an Anthropic call is charged, an OpenAI reservation that would cross the cap is refused before any POST."""
    probe=offline_routed_provider(C);pc=Caller(C,Ledger(':memory:',{'RUN_ID':'p'}),probe,1,True)
    gbound=probe.bound(gen_request(pc));fbound=probe.bound(critic_request(pc,'FEASIBILITY_CRITIC',FEAS_PROMPT))
    maxin,maxout=probe.adapters['ANTHROPIC'].bounds(gen_request(pc))
    cap=gbound+fbound-1
    ot=NoisyTransport(C,{})
    full={'input_tokens':maxin,'output_tokens':maxout}          # the Opus call charges exactly its bound
    l=Ledger(':memory:',{'RUN_ID':'h'});cal=Caller(C,l,router(Fake((200,env(gen_json(),usage=full))),ot,cap),cap,True)
    gen_call(cal)
    spent=l.spent_micro_usd();assert spent>cap-fbound
    with pytest.raises(BudgetExceeded):Roles(C,cal).feasibility(fixture(SLOTS[0],C))
    assert ot.log==[] and l.spent_micro_usd()==spent

def test_property_lineage_plus_both_providers_plus_next_reservation_within_cap():
    rng=random.Random(2027);probe=offline_routed_provider(C);pc=Caller(C,Ledger(':memory:',{'RUN_ID':'q'}),probe,1,True)
    requests=[gen_request(pc)]+[critic_request(pc,role,prompt) for role,prompt in (('NOVELTY_CRITIC',NOVELTY_PROMPT),('FEASIBILITY_CRITIC',FEAS_PROMPT),('RED_TEAM',RED_PROMPT))]
    bounds=[(r,probe.bound(r)) for r in requests]
    for trial in range(30):
        cap=rng.randint(5_000_000,17_100_000);prior=rng.randint(0,cap//3)
        l=Ledger(':memory:',{'RUN_ID':'t','CAP_MICRO_USD':cap});l.set('lineage',{'PRIOR_SPEND_MICRO_USD':prior});l.db.commit()
        by={'ANTHROPIC':0,'OPENAI':0}
        for n in range(rng.randint(5,40)):
            req,b=rng.choice(bounds);key='%d-%d'%(trial,n);before=l.total_charged_micro_usd()
            try:l.reserve(key,dict(req,n=n),b,cap)
            except BudgetExceeded:
                assert before+b>cap;continue
            l.mark_dispatched(key);cost=rng.randint(0,b)
            l.finish(key,{'raw':'{}'},cost,{});by[req['route_provider']]+=cost
            assert prior+by['ANTHROPIC']+by['OPENAI']==l.total_charged_micro_usd()<=cap
        l.close()

# ---------------------------------------------- schemas, secrets, CLI

def test_offline_schema_results():
    req={'parameters':{'slots':SLOTS}}
    for i in range(0,40,10):
        assert anthropic_subset_violations(anthropic_output_schema('GENERATOR',C,{'parameters':{'slots':slot_plan(40)[i:i+10]}}))==[]
    cards=[fixture(s,C) for s in slot_plan(40)]
    nov=Roles(C,None).request('NOVELTY_CRITIC',cards[0],cards)
    assert strict_subset_violations(role_schema('NOVELTY_CRITIC',C,provider=True,request={'context':nov}))==[]
    for role in ('FEASIBILITY_CRITIC','RED_TEAM','SELECTOR'):assert strict_subset_violations(role_schema(role,C,provider=True))==[]

def test_keys_are_never_persisted_or_exposed(mixed,tmp_path):
    report,l,t=mixed
    p=router(Fake(),NoisyTransport(C,{}))
    blob=canonical(routed_run_identity(p,C))+canonical(p.transport_identity())+canonical(report)
    for key in (AKEY,OKEY,'offline-gate-anthropic','offline-gate-openai'):assert key not in blob
    dump='\n'.join(l.db.iterdump())
    for key in ('offline-gate-anthropic','offline-gate-openai'):assert key not in dump
    at=Fake((200,env(gen_json())));cal,l2=caller_with(at);gen_call(cal)
    assert at.calls[0][3]['x-api-key']==AKEY and at.calls[0][3]['anthropic-version']=='2023-06-01'
    assert AKEY not in '\n'.join(l2.db.iterdump())

def test_cli_routed_preflight_needs_no_secrets_and_live_mode_needs_both(tmp_path,monkeypatch,capsys):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    main(['preflight','--provider','routed'])
    out=json.loads(capsys.readouterr().out)
    assert out['ROUTING_TABLE']=={'GENERATOR':'ANTHROPIC / claude-opus-5-5 / effort=high','NOVELTY_CRITIC':'OPENAI / gpt-6-sol / reasoning_effort=high',
                                  'RED_TEAM':'OPENAI / gpt-6-sol / reasoning_effort=high','FEASIBILITY_CRITIC':'OPENAI / gpt-6-luna / reasoning_effort=low',
                                  'SELECTOR':'OPENAI / gpt-6-luna / reasoning_effort=none'}
    assert out['REAL_LLM_CALLS_MADE'] is False and out['ROUTING_DIGEST']==offline_routed_provider(C).routing_digest
    with pytest.raises(ContractError,match='requires --allow-real-llm'):main(['run','--provider','routed','--run-dir',str(tmp_path/'r')])
    monkeypatch.setenv('OPENAI_API_KEY','only-one')
    with pytest.raises(ContractError,match='both OPENAI_API_KEY and ANTHROPIC_API_KEY'):
        main(['run','--provider','routed','--allow-real-llm','--budget-usd','17.1','--run-dir',str(tmp_path/'r')])
    assert not (tmp_path/'r').exists()
