import json
from scripts.research.generator_v0.schema import decode_provider_card
from decimal import Decimal,ROUND_CEILING
import pytest
from scripts.research.generator_v0.openai_provider import (
    OpenAIProvider,OPENAI_REQUEST_TIMEOUT_SECONDS,bounded_timeout,CREATE_TIMEOUT_SECONDS,
    POLL_GET_TIMEOUT_SECONDS,BACKGROUND_STORE_POLICY,GENERATOR_ENDPOINT,
)
from scripts.research.generator_v0.provider import Caller,BackgroundPending
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.models import ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,rates,spec,request_params_for,model_for,GENERATOR_MAX_OUTPUT_TOKENS
from scripts.research.generator_v0.output_schemas import openai_response_format,responses_text_format,role_schema
from scripts.research.generator_v0.schema import output_schema,validate_card
from scripts.research.generator_v0.mock import MockResponder
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS
from scripts.research.generator_v0.ledger import CallUncertain
from scripts.research.generator_v0.provider import ProviderThrottled,BilledFailure

SLOT={'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}
GEN_PARAMS={'max_output_tokens':100,'slots':[SLOT]}
GEN_FULL={'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':[SLOT]}

def chat_envelope(content='{}',finish='stop'):
    return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':20}}).encode()

def responses_create(rid,status='queued'):
    return json.dumps({'id':rid,'object':'response','status':status}).encode()

def responses_completed(rid,content,inp=100,out=20,reasoning=7):
    return json.dumps({
        'id':rid,'object':'response','status':'completed',
        'output_text':content,
        'output':[{'type':'message','content':[{'type':'output_text','text':content}]}],
        'usage':{'input_tokens':inp,'output_tokens':out,'output_tokens_details':{'reasoning_tokens':reasoning}},
    }).encode()

def responses_incomplete(rid,content='',inp=4588,out=16000,reasoning=9322,reason='max_output_tokens'):
    body={'id':rid,'object':'response','status':'incomplete','incomplete_details':{'reason':reason},
          'usage':{'input_tokens':inp,'output_tokens':out,'output_tokens_details':{'reasoning_tokens':reasoning}}}
    if content:
        body['output_text']=content
        body['output']=[{'type':'message','content':[{'type':'output_text','text':content}]}]
    return json.dumps(body).encode()

def provider(transport,budget=30_000_000,**kw):
    return OpenAIProvider('test-credential',allow_real=True,budget_micro_usd=budget,transport=transport,
                          sleeper=kw.get('sleeper',lambda s:None),clock=kw.get('clock'),
                          background_max_wait_seconds=kw.get('background_max_wait_seconds',3600))

def cost_of(role,inp=100,out=20):
    i,o=rates(role)
    return int((i*inp+o*out).to_integral_value(rounding=ROUND_CEILING))

def generator_json(contexts):
    return MockResponder(contexts)({'role':'GENERATOR','context':contexts.generator(),'parameters':{'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}})

def gen_transport(contexts,log,content=None,status_seq=None):
    states=list(status_seq or ['queued','in_progress','completed'])
    created={'n':0}
    def fake(method,path,body,headers,timeout):
        log.append((method,path,json.loads(body) if body else None,timeout,headers))
        if method=='POST' and path=='/v1/responses':
            created['n']+=1;rid='resp_'+str(created['n'])
            return 200,responses_create(rid,states[0] if states else 'queued')
        if method=='GET' and path.startswith('/v1/responses/'):
            rid=path.rsplit('/',1)[1]
            st=states.pop(0) if states else 'completed'
            if st=='completed':
                return 200,responses_completed(rid,content if content is not None else generator_json(contexts))
            return 200,json.dumps({'id':rid,'status':st}).encode()
        if method=='DELETE':return 200,b'{}'
        raise AssertionError('unexpected '+method+' '+path)
    return fake

def test_generator_uses_background_responses_strict_schema(tmp_path):
    c=Contexts();log=[]
    p=provider(gen_transport(c,log));l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});caller=Caller(c,l,p,30_000_000,True)
    slots={'max_output_tokens':100,'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}
    raw=caller.call('GENERATOR',c.generator(),'Return JSON',slots,'test')
    assert caller.call('GENERATOR',c.generator(),'Return JSON',slots,'test')==raw
    posts=[x for x in log if x[0]=='POST']
    gets=[x for x in log if x[0]=='GET']
    assert len(posts)==1 and posts[0][1]=='/v1/responses'
    body=posts[0][2]
    assert body['model']=='gpt-6-astra' and body['background'] is True and body['store'] is True
    assert body['reasoning']=={'effort':'high'} and 'reasoning_effort' not in body and 'temperature' not in body
    fmt=body['text']['format']
    assert fmt==responses_text_format('GENERATOR',c,{'parameters':slots})
    assert fmt['type']=='json_schema' and fmt['strict'] is True
    # Decoding-level contract: CANDIDATES is keyed by exactly the round's slot IDs.
    assert fmt['schema']['properties']['CANDIDATES']['required']==['C001']
    card=fmt['schema']['properties']['CANDIDATES']['properties']['C001']
    assert card['properties']['CANDIDATE_ID']['enum']==['C001'] and card['properties']['MECHANISM_FAMILY']['enum']==['A']
    assert card['properties']['DATA_REQUIRED']['items']['properties']['LEGAL_RANGE']['pattern']
    assert card['additionalProperties'] is False and 'STREAM' not in card['properties']
    assert len(card['required'])==27
    assert gets and all(x[1].startswith('/v1/responses/resp_') for x in gets)
    assert posts[0][3]==CREATE_TIMEOUT_SECONDS
    assert any(x[3]==POLL_GET_TIMEOUT_SECONDS for x in gets)
    call=l.export_calls()[0]
    assert call['STATE']=='COMPLETE' and call['RESPONSE_ID']=='resp_1'
    assert call['MODEL_ID']=='gpt-6-astra' and call['COST_MICRO_USD']==cost_of('GENERATOR')
    assert call['USAGE']['reasoning_tokens']==7
    assert 'test-credential' not in json.dumps(l.export_calls())
    assert any(x[0]=='DELETE' for x in log)

@pytest.mark.parametrize('key,allow,budget',[('',True,1),('key',False,1),('key',True,0),('key',True,30_000_001)])
def test_spend_gates(key,allow,budget):
    with pytest.raises(ContractError):OpenAIProvider(key,allow_real=allow,budget_micro_usd=budget,transport=lambda *a:pytest.fail('network reached'))

def test_single_model_override_is_rejected():
    with pytest.raises(ContractError,match='role-specific'):OpenAIProvider('key',allow_real=True,budget_micro_usd=1,model='gpt-4.1-mini-2025-04-14',transport=lambda *a:pytest.fail('network reached'))

def test_create_failures_are_uncertain_and_never_replayed(tmp_path,kind='timeout'):
    """Timeout or an unusable 200 acknowledgement: outcome unknown -> UNCERTAIN, never replayed."""
    log=[]
    def fake(method,path,body,headers,timeout):
        log.append(method+path)
        if kind=='timeout':raise TimeoutError()
        return 200,b'not-json'
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});p=provider(fake);caller=Caller(c,l,p,30_000_000,True)
    for _ in range(2):
        with pytest.raises(CallUncertain):caller.call('GENERATOR',c.generator(),'Return JSON',GEN_PARAMS,'one')
    assert log==['POST/v1/responses']
    assert l.db.execute('SELECT state,cost FROM calls').fetchone()==('UNCERTAIN',None)
    assert l.spent_micro_usd()==l.db.execute('SELECT reserved FROM calls').fetchone()[0]

@pytest.mark.parametrize('kind',['timeout','malformed'])
def test_create_failure_kinds(tmp_path,kind):
    test_create_failures_are_uncertain_and_never_replayed(tmp_path,kind)

def test_create_429_is_not_billed_retried_with_backoff_and_never_strands(tmp_path):
    log=[];sleeps=[]
    def fake(method,path,body,headers,timeout):
        log.append(method+path);return 429,b'{"error":"rate_limited"}'
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'throttle'})
    p=provider(fake,sleeper=sleeps.append);caller=Caller(c,l,p,30_000_000,True)
    with pytest.raises(ProviderThrottled):caller.call('GENERATOR',c.generator(),'Return JSON',GEN_PARAMS,'one')
    assert log==['POST/v1/responses']*3 and sleeps==[2,8,30]
    assert {r['STATE'] for r in l.export_calls()}=={'FAILED_NOT_BILLED'}
    assert l.spent_micro_usd()==0
    # A later invocation continues with fresh attempt keys; it is not stranded.
    inner=gen_transport(c,[])
    def ok(method,path,body,headers,timeout):
        log.append(method+path)
        return inner(method,path,body,headers,timeout)
    raw=Caller(c,l,provider(ok),30_000_000,True).call('GENERATOR',c.generator(),'Return JSON',GEN_PARAMS,'one')
    assert json.loads(raw)['CANDIDATES']['C001']['CANDIDATE_ID']=='C001'
    assert [r['STATE'] for r in l.export_calls()]==['FAILED_NOT_BILLED']*3+['COMPLETE']
    assert [r['TRANSPORT_ATTEMPT'] for r in l.export_calls()]==[0,1,2,3]

def test_budget_denies_before_http(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'})
    p=OpenAIProvider('key',allow_real=True,budget_micro_usd=1,transport=lambda *a:pytest.fail('HTTP'),sleeper=lambda s:None)
    with pytest.raises(ContractError):Caller(c,l,p,1,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')

def test_unknown_model_fails_closed():
    with pytest.raises(ContractError,match='unknown model'):spec('gpt-not-a-model')
    with pytest.raises(ContractError,match='unknown model'):spec('gpt-5.4-2026-03-05')

def test_gpt6_role_map_prices_and_effort():
    assert ROLE_MODEL_MAP=={
        'GENERATOR':'gpt-6-astra','NOVELTY_CRITIC':'gpt-6-sol','RED_TEAM':'gpt-6-sol',
        'FEASIBILITY_CRITIC':'gpt-6-luna','SELECTOR':'gpt-6-luna',
    }
    assert ROLE_REQUEST_PARAMS['GENERATOR']=={'reasoning_effort':'high'}
    assert ROLE_REQUEST_PARAMS['SELECTOR']=={'reasoning_effort':'none'}
    assert rates('GENERATOR')==(Decimal('10.00'),Decimal('50.00'))

def _mutate_generator(contexts,mutate):
    payload=json.loads(generator_json(contexts));mutate(payload);return json.dumps(payload)

@pytest.mark.parametrize('kind,mutate',[
    ('extra',lambda p:p['CANDIDATES']['C001'].update(STREAM='EXECUTABLE_NOW')),
    ('missing',lambda p:p['CANDIDATES']['C001'].pop('FALSIFIER')),
    ('nested',lambda p:p['CANDIDATES']['C001']['DATA_REQUIRED'][0].update(EXTRA='nope')),
    ('envelope',lambda p:p.update(STREAM='nope')),
])
def test_schema_violation_persists_completed_envelope_without_new_post(tmp_path,kind,mutate):
    """Content errors never raise in transport: the billed COMPLETE answer is kept and judged by intake."""
    c=Contexts();log=[]
    p=provider(gen_transport(c,log,content=_mutate_generator(c,mutate)));l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'})
    caller=Caller(c,l,p,30_000_000,True)
    raw=caller.call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert l.export_calls()[0]['STATE']=='COMPLETE'
    assert l.export_calls()[0]['RESPONSE_ID']=='resp_1'
    posts=[x for x in log if x[0]=='POST']
    assert caller.call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')==raw
    assert [x for x in log if x[0]=='POST']==posts

def test_application_validator_still_rejects_semantic_violations(tmp_path):
    c=Contexts();payload=json.loads(generator_json(c));payload['CANDIDATES']['C001']['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01..2025-06'
    log=[]
    p=provider(gen_transport(c,log,content=json.dumps(payload)));l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'})
    raw=Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'sem')
    parsed=json.loads(raw)
    assert parsed['CANDIDATES']['C001']['DATA_REQUIRED'][0]['LEGAL_RANGE']=='2020-01..2025-06'
    with pytest.raises(ContractError,match='protected'):validate_card(decode_provider_card(parsed['CANDIDATES']['C001']),c)
    assert [x[0] for x in log].count('POST')==1 and l.export_calls()[0]['STATE']=='COMPLETE'
    env=json.loads(l.db.execute('SELECT response FROM calls').fetchone()[0])
    assert 'provider_envelope' in env

def test_each_role_mixed_transport_and_budget(tmp_path):
    c=Contexts();respond=MockResponder(c);seen={};log=[]
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT,run_campaign
    from scripts.research.generator_v0.roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT
    prompts={GENERATOR_PROMPT:'GENERATOR',NOVELTY_PROMPT:'NOVELTY_CRITIC',FEAS_PROMPT:'FEASIBILITY_CRITIC',RED_PROMPT:'RED_TEAM',SELECTOR_PROMPT:'SELECTOR'}
    created={'n':0}
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST' and path=='/v1/responses':
            b=json.loads(body);seen.setdefault('GENERATOR',b)
            created['n']+=1;rid='resp_g'+str(created['n'])
            user=json.loads(b['input']);result=respond({'role':'GENERATOR','context':user['context'],'parameters':{'slots':user.get('slots',[])}})
            fake.payloads[rid]=result
            return 200,responses_create(rid)
        if method=='GET' and path.startswith('/v1/responses/'):
            rid=path.rsplit('/',1)[1]
            return 200,responses_completed(rid,fake.payloads[rid])
        if method=='DELETE':return 200,b'{}'
        assert path=='/v1/chat/completions' and timeout==OPENAI_REQUEST_TIMEOUT_SECONDS
        b=json.loads(body);role=prompts[b['messages'][0]['content']];seen.setdefault(role,b)
        user=json.loads(b['messages'][1]['content'])
        result=respond({'role':role,'context':user['context'],'parameters':{'slots':user.get('slots',[])}})
        return 200,chat_envelope(result)
    fake.payloads={}
    p=provider(fake);l=Ledger(tmp_path/'r.db',{'RUN_ID':'roles'})
    result=_accepted(c,Caller(c,l,p,17_100_000,True))
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert set(seen)==set(ROLE_MODEL_MAP)
    g=seen['GENERATOR']
    assert g['background'] is True and g['store'] is True and g['text']['format']['strict'] is True
    assert set(g['text']['format']['schema']['properties']['CANDIDATES']['properties'])=={'C001','C002','C003','C004','C005','C006','C007','C008','C009','C010'}
    assert g['reasoning']=={'effort':'high'}
    assert g['max_output_tokens']==GENERATOR_MAX_OUTPUT_TOKENS==32768
    for role in ('NOVELTY_CRITIC','FEASIBILITY_CRITIC','RED_TEAM','SELECTOR'):
        body=seen[role]
        assert body['model']==ROLE_MODEL_MAP[role]
        assert body['response_format']['type']=='json_schema' and body['response_format']['json_schema']['strict'] is True
        if role!='NOVELTY_CRITIC':assert body['response_format']==openai_response_format(role,c)
        assert body[list(ROLE_REQUEST_PARAMS[role])[0]]==ROLE_REQUEST_PARAMS[role]['reasoning_effort']
        assert 'temperature' not in body
    for role,cap in ROLE_OUTPUT_TOKEN_CAPS.items():assert seen[role]['max_completion_tokens']==cap
    assert [x for x in log if x==('POST','/v1/responses')].__len__()==4
    assert [x for x in log if x[0]=='POST' and x[1]=='/v1/chat/completions'].__len__()==121
    expected=4*cost_of('GENERATOR')+40*cost_of('NOVELTY_CRITIC')+40*cost_of('FEASIBILITY_CRITIC')+40*cost_of('RED_TEAM')+cost_of('SELECTOR')
    assert l.db.execute('SELECT sum(cost) FROM calls').fetchone()[0]==expected
    assert l.db.execute('SELECT count(*) FROM calls').fetchone()[0]==125

def test_crash_after_submit_resumes_same_response_id(tmp_path):
    c=Contexts();log=[];t={'n':0}
    def clock():return t['n']
    def sleep(s):t['n']+=100
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':return 200,responses_create('resp_keep')
        if method=='GET':raise TimeoutError()
        return 200,b'{}'
    p=provider(fake,clock=clock,sleeper=sleep,background_max_wait_seconds=5)
    l=Ledger(tmp_path/'r2.db',{'RUN_ID':'x'})
    slots={'max_output_tokens':100,'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}
    with pytest.raises(BackgroundPending):
        Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',slots,'g0')
    assert l.db.execute('SELECT state FROM calls').fetchone()[0]=='BACKGROUND_SUBMITTED'
    log.clear()
    def resume_fake(method,path,body,headers,timeout):
        log.append((method,path))
        assert method!='POST'
        if method=='GET':return 200,responses_completed('resp_keep',generator_json(c))
        return 200,b'{}'
    Caller(c,l,provider(resume_fake),30_000_000,True).call('GENERATOR',c.generator(),'JSON',slots,'g0')
    assert ('POST','/v1/responses') not in log
    assert l.export_calls()[0]['RESPONSE_ID']=='resp_keep'
    assert l.export_calls()[0]['STATE']=='COMPLETE'

def test_polling_timeout_stays_resumable(tmp_path):
    c=Contexts();log=[];t={'n':0}
    def clock():return t['n']
    def sleep(s):t['n']+=s
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':return 200,responses_create('resp_slow')
        if method=='GET':return 200,json.dumps({'id':'resp_slow','status':'in_progress'}).encode()
        return 200,b'{}'
    p=provider(fake,clock=clock,sleeper=sleep,background_max_wait_seconds=5)
    l=Ledger(tmp_path/'r.db',{'RUN_ID':'pend'})
    with pytest.raises(BackgroundPending):
        Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert l.db.execute('SELECT state FROM calls').fetchone()[0]=='BACKGROUND_SUBMITTED'
    posts=len([x for x in log if x[0]=='POST'])
    def finish(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':raise AssertionError('new POST')
        if method=='GET':return 200,responses_completed('resp_slow',generator_json(c))
        return 200,b'{}'
    Caller(c,l,provider(finish),30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert len([x for x in log if x[0]=='POST'])==posts
    assert l.export_calls()[0]['STATE']=='COMPLETE'

def test_get_retry_does_not_post_again(tmp_path):
    c=Contexts();log=[];gets={'n':0}
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':return 200,responses_create('resp_r')
        if method=='GET':
            gets['n']+=1
            if gets['n']==1:raise TimeoutError()
            return 200,responses_completed('resp_r',generator_json(c))
        return 200,b'{}'
    Caller(c,Ledger(tmp_path/'r.db',{'RUN_ID':'r'}),provider(fake),30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert [x for x in log if x[0]=='POST']==[('POST','/v1/responses')]
    assert gets['n']==2

def test_polling_does_not_consume_another_reservation(tmp_path):
    c=Contexts();log=[]
    p=provider(gen_transport(c,log));l=Ledger(tmp_path/'r.db',{'RUN_ID':'b'})
    Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    count,reserved,cost=l.db.execute('SELECT count(*),sum(reserved),sum(cost) FROM calls').fetchone()
    assert count==1 and reserved>=cost==cost_of('GENERATOR')

def test_response_id_is_persisted_before_first_get(tmp_path):
    c=Contexts();events=[];l=Ledger(tmp_path/'r.db',{'RUN_ID':'order'})
    orig=l.submit_background
    def wrapped(key,tracker):
        events.append(('persist',tracker['response_id']));orig(key,tracker)
    l.submit_background=wrapped
    def fake(method,path,body,headers,timeout):
        if method=='POST':
            events.append(('post',path));return 200,responses_create('resp_first')
        if method=='GET':
            events.append(('get',path))
            assert ('persist','resp_first') in events
            return 200,responses_completed('resp_first',generator_json(c))
        events.append(('delete',path));return 200,b'{}'
    Caller(c,l,provider(fake),30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert events[0]==('post','/v1/responses')
    assert events[1]==('persist','resp_first')
    assert events[2]==('get','/v1/responses/resp_first')
    assert l.export_calls()[0]['STATE']=='COMPLETE'

@pytest.mark.parametrize('status',['failed','cancelled','incomplete'])
def test_terminal_noncompleted_background_fails_closed(tmp_path,status):
    log=[]
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':return 200,responses_create('resp_term')
        if method=='GET':return 200,json.dumps({'id':'resp_term','status':status}).encode()
        return 200,b'{}'
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'term'})
    caller=Caller(c,l,provider(fake),30_000_000,True)
    with pytest.raises(BilledFailure,match='background generation'):
        caller.call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert l.export_calls()[0]['STATE']=='FAILED_WITH_COST'
    assert l.export_calls()[0]['PROVIDER_STATUS']==status
    with pytest.raises(BilledFailure,match='billed attempt without usable content'):
        caller.call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'one')
    assert [x for x in log if x[0]=='POST']==[('POST','/v1/responses')]

def test_generator_synchronous_complete_is_refused():
    p=provider(lambda *a:pytest.fail('network reached'))
    with pytest.raises(ContractError,match='background Responses'):
        p.complete({'role':'GENERATOR','context':{},'prompt':'JSON','parameters':{'max_output_tokens':100}})

def test_resume_identity_includes_transport(tmp_path):
    c=Contexts();log=[]
    p=provider(gen_transport(c,log));ident=p.transport_identity()
    assert ident['GENERATOR_ENDPOINT']==GENERATOR_ENDPOINT=='RESPONSES'
    assert ident['GENERATOR_BACKGROUND'] is True
    assert ident['BACKGROUND_STORE_POLICY']==BACKGROUND_STORE_POLICY
    assert ident['GENERATOR_MAX_OUTPUT_TOKENS']==GENERATOR_MAX_OUTPUT_TOKENS==32768
    config={'RUN_ID':'resume','GENERATOR_ENDPOINT':'RESPONSES','GENERATOR_MAX_OUTPUT_TOKENS':32768}
    l=Ledger(tmp_path/'r.db',config)
    Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',GEN_PARAMS,'g0')
    with pytest.raises(ContractError,match='resume configuration differs'):
        Ledger(tmp_path/'r.db',{'RUN_ID':'resume','GENERATOR_ENDPOINT':'CHAT_COMPLETIONS','GENERATOR_MAX_OUTPUT_TOKENS':32768})
    with pytest.raises(ContractError,match='resume configuration differs'):
        Ledger(tmp_path/'r.db',{'RUN_ID':'resume','GENERATOR_ENDPOINT':'RESPONSES','GENERATOR_MAX_OUTPUT_TOKENS':16000})

def test_openai_role_schemas_are_strict():
    c=Contexts()
    from scripts.research.generator_v0.roles import Roles
    from scripts.research.generator_v0.mock import fixture,slot_plan
    cards=[fixture(x,c) for x in slot_plan(40)]
    requests={'GENERATOR':{'parameters':GEN_PARAMS},'NOVELTY_CRITIC':{'context':Roles(c,None).request('NOVELTY_CRITIC',cards[0],cards)}}
    for role in ROLE_MODEL_MAP:
        schema=role_schema(role,c,provider=True,request=requests.get(role))
        assert schema['additionalProperties'] is False
        assert set(schema['required'])==set(schema['properties'])
    card=output_schema(c,provider=True)
    assert len(card['required'])==27 and 'STREAM' not in card['properties']
    fmt=responses_text_format('GENERATOR',c,requests['GENERATOR'])
    assert fmt['schema']==role_schema('GENERATOR',c,provider=True,request=requests['GENERATOR'])
    nov=role_schema('NOVELTY_CRITIC',c,provider=True,request=requests['NOVELTY_CRITIC'])
    assert set(nov['properties']['BATCH_RELATIONS']['required'])=={x['CANDIDATE_ID'] for x in cards[1:]}
    assert set(nov['properties']['PRIOR_RELATIONS']['required'])=={k for k,r in c.rows.items() if r['STATE']!='PARTIAL_OR_MIXED'}

def test_archived_paid_run_is_not_opened_by_operator(monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('OPENAI_API_KEY','present')
    from scripts.research.generator_v0.__main__ import ARCHIVED_PAID_RUNS
    assert ('generator_v0','first-shadow-v5') in ARCHIVED_PAID_RUNS
    assert ('generator_v0','first-shadow-v6') in ARCHIVED_PAID_RUNS
    assert ('generator_v0','first-shadow-v7') in ARCHIVED_PAID_RUNS
    for run_dir in ('artifacts/generator_v0/first-shadow','artifacts/generator_v0/first-shadow-v2','artifacts/generator_v0/first-shadow-v3','artifacts/generator_v0/first-shadow-v4','artifacts/generator_v0/first-shadow-v5','artifacts/generator_v0/first-shadow-v6','artifacts/generator_v0/first-shadow-v7'):
        with pytest.raises(ContractError,match='archived paid run'):
            main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','10','--run-dir',run_dir])

def test_ambient_key_never_enables_http(monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch.setenv('OPENAI_API_KEY','present-but-not-authorized')
    monkeypatch.delenv('GENERATOR_V0_MODEL',raising=False)
    monkeypatch.setattr(HTTPS,'__call__',lambda *args:pytest.fail('HTTP reached'))
    main(['preflight'])
    with pytest.raises(ContractError):main(['preflight','--provider','openai'])
    main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','30'])
    with pytest.raises(ContractError,match='role-specific'):
        main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','30','--model','gpt-4.1-mini-2025-04-14'])

def test_critic_timeout_still_600():
    seen=[]
    def fake(method,path,body,headers,timeout):
        seen.append((path,timeout))
        payload={'CHECKS':{'NO_LOOKAHEAD':True,'CAUSALITY':True,'FALSIFIABLE':True,'BOUNDED_SEARCH':True,'CONFOUNDING_ADDRESSED':True,'NO_TRADING_CLAIM':True},
                 'JUDGMENTS':{'FALSIFIABILITY':3,'NO_LOOKAHEAD_QUALITY':3,'CONFOUNDING_AWARENESS':3,'SEARCH_SURFACE_DISCIPLINE':3,'NULL_INFORMATION_GAIN':3}}
        return 200,chat_envelope(json.dumps(payload))
    p=provider(fake)
    assert p.request_timeout_seconds==OPENAI_REQUEST_TIMEOUT_SECONDS==600
    p.complete({'role':'RED_TEAM','context':{},'prompt':'JSON','parameters':{'max_output_tokens':100}})
    assert seen==[('/v1/chat/completions',600)]

@pytest.mark.parametrize('value',[0,-1,1801,60.0,'600',True,False])
def test_invalid_timeout_fails_closed(value):
    with pytest.raises(ContractError,match='invalid request timeout'):bounded_timeout(value)
    with pytest.raises(ContractError,match='invalid request timeout'):
        OpenAIProvider('key',allow_real=True,budget_micro_usd=1,timeout_seconds=value,transport=lambda *a:pytest.fail('network reached'))

def test_incomplete_max_output_tokens_accounts_actual_cost(tmp_path):
    log=[];c=Contexts()
    partial=json.dumps({'CANDIDATES':[{'NAME':'partial-must-not-parse'}]})
    def fake(method,path,body,headers,timeout):
        log.append((method,path,json.loads(body) if body else None))
        if method=='POST':
            assert json.loads(body)['max_output_tokens']==GENERATOR_MAX_OUTPUT_TOKENS
            return 200,responses_create('resp_v4')
        if method=='GET':return 200,responses_incomplete('resp_v4',content=partial)
        return 200,b'{}'
    l=Ledger(tmp_path/'r.db',{'RUN_ID':'v4acc'})
    caller=Caller(c,l,provider(fake),30_000_000,True)
    with pytest.raises(BilledFailure,match='background generation incomplete'):
        caller.call('GENERATOR',c.generator(),'JSON',GEN_FULL,'generation:0')
    row=l.export_calls()[0]
    assert row['STATE']=='FAILED_WITH_COST' and row['PROVIDER_STATUS']=='incomplete' and row['COST_BASIS']=='USAGE'
    assert row['RESPONSE_ID']=='resp_v4'
    assert row['USAGE']=={'input_tokens':4588,'output_tokens':16000,'reasoning_tokens':9322}
    assert row['COST_MICRO_USD']==cost_of('GENERATOR',4588,16000)==845880
    assert row['COST_MICRO_USD']<row['RESERVED_MICRO_USD']
    env=json.loads(l.db.execute('SELECT response FROM calls').fetchone()[0])
    assert env['provider_envelope']['incomplete_details']=={'reason':'max_output_tokens'}
    assert 'CANDIDATES' not in env
    spent=l.db.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM calls').fetchone()[0]
    assert spent==845880
    with pytest.raises(BilledFailure,match='billed attempt without usable content'):
        caller.call('GENERATOR',c.generator(),'JSON',GEN_FULL,'generation:0')
    assert [x[0] for x in log if x[0]=='POST']==['POST']
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0

def test_incomplete_malformed_usage_stays_reservation_backed(tmp_path):
    log=[]
    def fake(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':return 200,responses_create('resp_bad')
        if method=='GET':
            return 200,json.dumps({'id':'resp_bad','status':'incomplete','incomplete_details':{'reason':'max_output_tokens'},'usage':{'input_tokens':'nope','output_tokens':16000}}).encode()
        return 200,b'{}'
    l=Ledger(tmp_path/'r.db',{'RUN_ID':'badu'})
    with pytest.raises(BilledFailure,match='background generation incomplete'):
        Caller(Contexts(),l,provider(fake),30_000_000,True).call('GENERATOR',Contexts().generator(),'JSON',GEN_FULL,'one')
    row=l.export_calls()[0]
    # Billed with unknown usage: charged the full reservation, recorded as such.
    assert row['STATE']=='FAILED_WITH_COST' and row['COST_MICRO_USD']==row['RESERVED_MICRO_USD'] and row['USAGE'] is None
    assert row['COST_BASIS']=='RESERVED_BOUND'
    spent=l.db.execute('SELECT COALESCE(SUM(COALESCE(cost,reserved)),0) FROM calls').fetchone()[0]
    assert spent==row['RESERVED_MICRO_USD']
    assert [x for x in log if x[0]=='POST']==[('POST','/v1/responses')]

def test_terminal_cost_above_reservation_fails_closed(tmp_path):
    def fake(method,path,body,headers,timeout):
        if method=='POST':return 200,responses_create('resp_over')
        if method=='GET':return 200,responses_incomplete('resp_over')
        return 200,b'{}'
    l=Ledger(tmp_path/'r.db',{'RUN_ID':'over'});p=provider(fake)
    p.terminal_usage_cost=lambda req,payload:({'input_tokens':1,'output_tokens':1,'reasoning_tokens':0},10**12)
    with pytest.raises(ContractError,match='exceeds reserved bound'):
        Caller(Contexts(),l,p,30_000_000,True).call('GENERATOR',Contexts().generator(),'JSON',GEN_FULL,'one')
    row=l.export_calls()[0]
    assert row['STATE']=='FAILED_WITH_COST' and row['COST_MICRO_USD']==row['RESERVED_MICRO_USD'] and row['USAGE'] is None
    assert row['PROVIDER_STATUS']=='incomplete' and row['COST_BASIS']=='RESERVED_BOUND'

def _accepted(c,caller,size=40):
    """Record the budget-stop acceptance the execution gate requires, then run (library path)."""
    from scripts.research.generator_v0.runner import accept_budget_stop,run_campaign as _rc
    accept_budget_stop(c,caller,size,'test-operator','this test exercises a campaign whose worst case exceeds its cap')
    return _rc(c,caller,size)
