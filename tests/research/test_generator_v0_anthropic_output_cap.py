"""Routed Anthropic GENERATOR output cap (owner amendment 32768 -> 100000) and
failure-path hash provenance. Offline only: fake transports, dummy keys, no network."""
import hashlib
import json
import pytest
from decimal import Decimal
from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider,usage_cost
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.routed_provider import RoutedProvider,offline_routed_provider,routed_run_identity
from scripts.research.generator_v0.provider import Caller,BilledFailure,ProviderRejected
from scripts.research.generator_v0.ledger import Ledger,CallUncertain
from scripts.research.generator_v0.runner import (GENERATOR_PROMPT,generator_request_parameters,generator_identity,
    generator_max_output_tokens,_round_output)
from scripts.research.generator_v0.roles import Roles,FEAS_PROMPT,NOVELTY_PROMPT
from scripts.research.generator_v0.models import GENERATOR_MAX_OUTPUT_TOKENS,ROLE_OUTPUT_TOKEN_CAPS
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.derive import expected_generator_request,campaign_bound
from scripts.research.generator_v0.provider import MockProvider

C=Contexts()
PLAN=slot_plan(40)
SLOTS=PLAN[:10]
AKEY='sk-ant-test-DO-NOT-PERSIST-0123456789'
OKEY='sk-openai-test-DO-NOT-PERSIST-9876543210'
CAP=3_100_000
# Billed failed first live compact round (32768-token cap) and the earlier keyed grammar rejection.
FAILED_32768_COMPACT_KEY='f8207e1f0fa229f24eec50b0c894d704dd32ad1fece59672e2d2440b47ea930e'
FAILED_KEYED_GRAMMAR_KEY='767fd9e133e63a6e212277326252679724c3863d9d649e909c0eb1dc2bdf95a0'
PRIOR_ROUTING_DIGEST='ef21451e433da324430c15cbfda41e514ab114d8f9fd2fa0921d9cc266d32716'
HISTORICAL_SMOKE_MICRO_USD=713_332
SMOKE_CEILING_MICRO_USD=3_100_000

class Fake:
    def __init__(self,*answers):self.answers=list(answers);self.bodies=[]
    def __call__(self,method,path,body,headers,timeout):
        self.bodies.append(json.loads(body))
        a=self.answers.pop(0)
        if isinstance(a,BaseException):raise a
        return a

def router(atransport,otransport=None):
    return RoutedProvider({'ANTHROPIC':AnthropicProvider(AKEY,allow_real=True,budget_micro_usd=CAP,transport=atransport,contexts=C),
                           'OPENAI':OpenAIProvider(OKEY,allow_real=True,budget_micro_usd=CAP,transport=otransport or Fake(),contexts=C,routes=routing.ROUTES,sleeper=lambda s:None)},
                          routing.ROUTES,sleeper=lambda s:None)

def env(text,stop='end_turn',out=9000):
    content=[{'type':'thinking','thinking':'','signature':'opaque'}]+([{'type':'text','text':text}] if text is not None else [])
    return json.dumps({'id':'msg_cap_1','type':'message','role':'assistant','model':'claude-opus-5-5','content':content,
                       'stop_reason':stop,'stop_sequence':None,'usage':{'input_tokens':6000,'output_tokens':out}}).encode()

def gen_json():
    keyed=json.loads(MockResponder(C)({'role':'GENERATOR','context':C.generator(),'parameters':{'slots':SLOTS}}))
    return canonical({'CANDIDATES':list(keyed['CANDIDATES'].values())})

def gen_request(caller,slots=SLOTS,n=0,cap=None):
    cap=generator_max_output_tokens(caller.provider) if cap is None else cap
    return caller.request('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(slots,cap),'generation:'+str(n),0,generator_identity(C,slots))

def offline_caller():
    return Caller(C,Ledger(':memory:',{'RUN_ID':'cap'}),offline_routed_provider(C),1,True)

def response_blob(ledger,key):
    return json.loads(ledger.db.execute('SELECT response FROM calls WHERE key=?',(key,)).fetchone()[0])

# ------------------------------------------------------------- cap

def test_routed_anthropic_generator_cap_is_100000_and_legacy_openai_cap_is_unchanged():
    assert routing.ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS==100000
    assert routing.ROUTES['GENERATOR']['MAX_OUTPUT_TOKENS']==100000
    assert routing.ROUTES['GENERATOR']['MAX_OUTPUT_TOKENS']<=routing.PRICES['claude-opus-5-5']['MAX_OUTPUT_TOKENS']==128000
    assert GENERATOR_MAX_OUTPUT_TOKENS==32768
    assert generator_max_output_tokens(offline_routed_provider(C))==100000
    assert generator_max_output_tokens(MockProvider())==32768
    legacy=OpenAIProvider(OKEY,allow_real=True,budget_micro_usd=CAP,transport=Fake(),contexts=C)
    assert generator_max_output_tokens(legacy)==32768
    assert expected_generator_request(C,SLOTS,0)['parameters']['max_output_tokens']==32768

def test_the_rest_of_the_generator_route_is_unchanged():
    r=routing.ROUTES['GENERATOR']
    assert (r['PROVIDER'],r['MODEL'],r['PARAMS'])==('ANTHROPIC','claude-opus-5-5',{'effort':'high'})
    assert r['STRUCTURED_OUTPUT']=='ANTHROPIC_OUTPUT_CONFIG_JSON_SCHEMA_COMPACT_CANDIDATE_ARRAY_V1'
    assert all(len(PLAN[i:i+10])==10 for i in range(0,40,10)) and len(PLAN)==40
    for role in ('NOVELTY_CRITIC','RED_TEAM','FEASIBILITY_CRITIC','SELECTOR'):
        assert routing.ROUTES[role]['MAX_OUTPUT_TOKENS']==ROLE_OUTPUT_TOKEN_CAPS[role]

@pytest.mark.parametrize('cap',[32768,99999,100001,128001])
def test_routing_refuses_any_other_anthropic_generator_cap(cap):
    routes=json.loads(json.dumps(routing.ROUTES));routes['GENERATOR']['MAX_OUTPUT_TOKENS']=cap
    with pytest.raises(ContractError):routing.validate_routes(routes)

def test_anthropic_request_carries_max_tokens_100000_and_refuses_the_old_cap():
    a=offline_routed_provider(C).adapters['ANTHROPIC'];cal=offline_caller()
    assert a.payload(gen_request(cal))['max_tokens']==100000
    with pytest.raises(ContractError,match='output token cap differs'):a.payload(gen_request(cal,cap=32768))

def test_runner_round_sends_max_tokens_100000(tmp_path):
    t=Fake((200,env(gen_json())))
    cal=Caller(C,Ledger(tmp_path/'r.sqlite',{'RUN_ID':'r','CAP_MICRO_USD':CAP}),router(t),CAP,True)
    contract_id,key,cards,reasons=_round_output(C,cal.ledger,cal,0,SLOTS)
    assert cards is not None and reasons==[] and len(t.bodies)==1
    assert t.bodies[0]['max_tokens']==100000 and t.bodies[0]['output_config']['effort']=='high'
    assert json.loads(cal.ledger.db.execute('SELECT request FROM calls WHERE key=?',(key,)).fetchone()[0])['parameters']['max_output_tokens']==100000

# ------------------------------------------------------------- identity

def test_cap_is_in_the_call_key_and_no_round_reuses_a_failed_key():
    cal=offline_caller()
    keys=[digest(gen_request(cal,PLAN[n*10:n*10+10],n)) for n in range(4)]
    assert keys[0]=='b1ed0d8333ae4b823e72e4175ef7680e0896cfc02915aa476d3278fa56d5cc93'
    assert len(set(keys))==4 and not set(keys)&{FAILED_32768_COMPACT_KEY,FAILED_KEYED_GRAMMAR_KEY}
    old=gen_request(cal,cap=32768)
    assert old['parameters']['max_output_tokens']==32768 and digest(old)!=keys[0]

def test_cap_is_in_the_routing_and_route_identity():
    assert routing.routing_digest()!=PRIOR_ROUTING_DIGEST
    routes=json.loads(json.dumps(routing.ROUTES))
    before=routing.role_route_digest('GENERATOR')
    routes['GENERATOR']['MAX_OUTPUT_TOKENS']=32768
    assert digest({'ROUTING_ID':routing.ROUTING_ID,'ROLE':'GENERATOR','ROUTE':routes['GENERATOR'],'PRICES':routing.price_row('claude-opus-5-5')})!=before
    ident=routed_run_identity(offline_routed_provider(C),C)
    assert ident['TRANSPORT_IDENTITY']['ADAPTERS']['ANTHROPIC']['ROLES']['GENERATOR']['MAX_OUTPUT_TOKENS']==100000

def test_failed_32768_row_is_never_reused_for_the_100000_call(tmp_path):
    """A journal holding the billed failed 32768-token call: the new call is a new key and a new POST."""
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'r','CAP_MICRO_USD':CAP})
    t=Fake((200,env(gen_json())))
    cal=Caller(C,l,router(t),CAP,True)
    old=gen_request(cal,cap=32768)
    l.db.execute('INSERT INTO calls(key,request,state,reserved,cost) VALUES (?,?,?,?,?)',(digest(old),canonical(old),'FAILED_WITH_COST',782028,713332));l.db.commit()
    raw=cal.call('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(SLOTS,100000),'generation:0',identity=generator_identity(C,SLOTS))
    assert raw and cal.last_key!=digest(old) and len(t.bodies)==1
    assert l.call_state(digest(old))=='FAILED_WITH_COST'

# ------------------------------------------------------------- bounds

def test_generator_bound_prices_100000_output_tokens():
    cal=offline_caller();a=offline_routed_provider(C).adapters['ANTHROPIC'];req=gen_request(cal)
    inp,out=a.bounds(req)
    assert out==100000
    assert a.bound(req)==int((Decimal(4)*inp+Decimal(20)*out).to_integral_value(rounding='ROUND_CEILING'))==2126672

def test_usage_up_to_the_new_cap_is_accepted_and_above_it_is_not():
    recorded,cost=usage_cost({'input_tokens':14493,'output_tokens':100000},'claude-opus-5-5',31668,100000)
    assert cost==14493*4+100000*20
    with pytest.raises(ValueError):usage_cost({'input_tokens':14493,'output_tokens':100001},'claude-opus-5-5',31668,100000)

def test_campaign_bound_uses_the_route_cap():
    b=campaign_bound(C,40,(),(),None,1,None,offline_routed_provider(C))
    gens=[s['BOUND_MICRO_USD'] for s in b['STAGES'] if s['STAGE'].startswith('generation:')]
    assert gens==[2126672,2126732,2126716,2127392]

def _smoke_bounds(routes=None):
    p=offline_routed_provider(C,routes);cal=Caller(C,Ledger(':memory:',{'RUN_ID':'cap'}),p,1,True)
    card=fixture(SLOTS[0],C);roles=Roles(C,cal)
    gen=p.bound(gen_request(cal))
    feas=p.bound(cal.request('FEASIBILITY_CRITIC',roles.request('FEASIBILITY_CRITIC',card),FEAS_PROMPT,{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS['FEASIBILITY_CRITIC']},'FEASIBILITY_CRITIC:C001'))
    nov=p.bound(cal.request('NOVELTY_CRITIC',roles.request('NOVELTY_CRITIC',card,[card]),NOVELTY_PROMPT,{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS['NOVELTY_CRITIC']},'NOVELTY_CRITIC:C001'))
    return gen,feas,nov

def test_smoke_reservations_fit_the_absolute_smoke_ceiling_including_history():
    # The executed re-smoke reserved novelty on synchronous Chat Completions (historical record).
    import copy
    chat=copy.deepcopy(routing.ROUTES)
    chat['NOVELTY_CRITIC'].update(STRUCTURED_OUTPUT='OPENAI_CHAT_RESPONSE_FORMAT_JSON_SCHEMA_STRICT',ENDPOINT='OPENAI_CHAT_COMPLETIONS',TRANSPORT=routing.OPENAI_CHAT_TRANSPORT)
    assert _smoke_bounds(chat)==(2126672,3950,194770)
    assert HISTORICAL_SMOKE_MICRO_USD+2126672+3950+194770==3038724<=SMOKE_CEILING_MICRO_USD
    # Background Responses novelty: same bound formula over a slightly smaller payload.
    gen,feas,nov=_smoke_bounds()
    assert (gen,feas,nov)==(2126672,3950,194672)
    assert HISTORICAL_SMOKE_MICRO_USD+gen+feas+nov<=SMOKE_CEILING_MICRO_USD

# ------------------------------------------------------------- hash provenance

def _call(tmp_path,answer):
    l=Ledger(tmp_path/'p.sqlite',{'RUN_ID':'p','CAP_MICRO_USD':CAP})
    cal=Caller(C,l,router(Fake(answer)),CAP,True)
    err=None
    try:cal.call('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(SLOTS,100000),'generation:0',identity=generator_identity(C,SLOTS))
    except BaseException as e:err=e
    return l,cal.last_key,err

def test_complete_call_raw_hash_is_model_text_and_wire_hash_is_envelope(tmp_path):
    text=gen_json();wire=env(text)
    l,key,err=_call(tmp_path,(200,wire))
    assert err is None
    blob=response_blob(l,key)
    assert blob['raw_sha256']==hashlib.sha256(text.encode()).hexdigest()
    assert blob['wire_sha256']==hashlib.sha256(wire).hexdigest()!=blob['raw_sha256']

def test_billed_max_tokens_failure_has_no_raw_hash_only_the_envelope_hash(tmp_path):
    wire=env('{"CANDIDATES":[{"CAND',stop='max_tokens',out=100000)
    l,key,err=_call(tmp_path,(200,wire))
    assert isinstance(err,BilledFailure)
    blob=response_blob(l,key)
    assert 'raw_sha256' not in blob and blob['wire_sha256']==hashlib.sha256(wire).hexdigest()
    assert blob['stop_reason']=='max_tokens' and blob['message_id']=='msg_cap_1'
    row=[r for r in l.export_calls() if r['CALL_KEY']==key][0]
    assert row['RAW_RESPONSE_SHA256'] is None and row['WIRE_SHA256']==hashlib.sha256(wire).hexdigest()
    assert row['STATE']=='FAILED_WITH_COST' and row['COST_MICRO_USD']==6000*4+100000*20

@pytest.mark.parametrize('answer,exc,state',[
    ((400,b'{"type":"error","error":{"type":"invalid_request_error","message":"x"}}'),ProviderRejected,'FAILED_NOT_BILLED'),
    ((529,b'{"type":"error","error":{"type":"overloaded_error","message":"x"}}'),CallUncertain,'UNCERTAIN'),
])
def test_http_failures_record_only_the_envelope_hash(tmp_path,answer,exc,state):
    l,key,err=_call(tmp_path,answer)
    assert isinstance(err,exc) and l.call_state(key)==state
    blob=response_blob(l,key)
    assert 'raw_sha256' not in blob and blob['wire_sha256']==hashlib.sha256(answer[1]).hexdigest()

def test_failure_without_any_wire_records_neither_hash(tmp_path):
    l,key,err=_call(tmp_path,TimeoutError('read timeout'))
    assert isinstance(err,CallUncertain)
    row=l.db.execute('SELECT response FROM calls WHERE key=?',(key,)).fetchone()[0]
    blob=json.loads(row) if row else {}
    assert 'raw_sha256' not in blob and 'wire_sha256' not in blob

def test_failed_never_accepts_a_raw_hash_from_an_envelope(tmp_path):
    l=Ledger(tmp_path/'f.sqlite',{'RUN_ID':'f','CAP_MICRO_USD':CAP})
    l.db.execute('INSERT INTO calls(key,request,state,reserved) VALUES (?,?,?,?)',('k','{}','DISPATCHED',10));l.db.commit()
    l.failed('k','x','w'*64,state='FAILED_WITH_COST',envelope={'raw_sha256':'r'*64,'stop_reason':'max_tokens'})
    blob=response_blob(l,'k')
    assert 'raw_sha256' not in blob and blob['wire_sha256']=='w'*64
