import json
from decimal import Decimal,ROUND_CEILING
import pytest
from scripts.research.generator_v0.openai_provider import (
    OpenAIProvider,OPENAI_REQUEST_TIMEOUT_SECONDS,bounded_timeout,CREATE_TIMEOUT_SECONDS,
    POLL_GET_TIMEOUT_SECONDS,BACKGROUND_STORE_POLICY,GENERATOR_ENDPOINT,
)
from scripts.research.generator_v0.provider import Caller,BackgroundPending
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.models import ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,rates,spec,request_params_for,model_for
from scripts.research.generator_v0.output_schemas import openai_response_format,responses_text_format,role_schema
from scripts.research.generator_v0.schema import output_schema,validate_card
from scripts.research.generator_v0.mock import MockResponder

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
    assert fmt==responses_text_format('GENERATOR',c)
    assert fmt['type']=='json_schema' and fmt['strict'] is True
    card=fmt['schema']['properties']['CANDIDATES']['items']
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
    log=[]
    def fake(method,path,body,headers,timeout):
        log.append(method+path)
        if kind=='timeout':raise TimeoutError()
        if kind=='http':return 429,b'error'
        return 200,b'not-json'
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});p=provider(fake);caller=Caller(c,l,p,30_000_000,True)
    for _ in range(2):
        with pytest.raises((ContractError,TimeoutError)):caller.call('GENERATOR',c.generator(),'Return JSON',{'max_output_tokens':100},'one')
    assert log==['POST/v1/responses']
    assert l.db.execute('SELECT state,cost FROM calls').fetchone()==('UNCERTAIN',None)

@pytest.mark.parametrize('kind',['timeout','http','malformed'])
def test_create_failure_kinds(tmp_path,kind):
    test_create_failures_are_uncertain_and_never_replayed(tmp_path,kind)

def test_budget_denies_before_http(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'})
    p=OpenAIProvider('key',allow_real=True,budget_micro_usd=1,transport=lambda *a:pytest.fail('HTTP'),sleeper=lambda s:None)
    with pytest.raises(ContractError):Caller(c,l,p,1,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')

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
    ('extra',lambda p:p['CANDIDATES'][0].update(STREAM='EXECUTABLE_NOW')),
    ('missing',lambda p:p['CANDIDATES'][0].pop('FALSIFIER')),
    ('nested',lambda p:p['CANDIDATES'][0]['DATA_REQUIRED'][0].update(EXTRA='nope')),
    ('envelope',lambda p:p.update(STREAM='nope')),
])
def test_schema_violation_persists_completed_envelope_without_new_post(tmp_path,kind,mutate):
    c=Contexts();log=[]
    p=provider(gen_transport(c,log,content=_mutate_generator(c,mutate)));l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'})
    caller=Caller(c,l,p,30_000_000,True)
    with pytest.raises(ContractError):caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert l.export_calls()[0]['STATE']=='COMPLETE'
    assert l.export_calls()[0]['RESPONSE_ID']=='resp_1'
    posts=[x for x in log if x[0]=='POST']
    caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert [x for x in log if x[0]=='POST']==posts

def test_application_validator_still_rejects_semantic_violations(tmp_path):
    c=Contexts();payload=json.loads(generator_json(c));payload['CANDIDATES'][0]['HORIZON']='2025'
    log=[]
    p=provider(gen_transport(c,log,content=json.dumps(payload)));l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'})
    raw=Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'sem')
    parsed=json.loads(raw)
    assert parsed['CANDIDATES'][0]['HORIZON']=='2025'
    with pytest.raises(ContractError,match='protected'):validate_card(parsed['CANDIDATES'][0],c)
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
    result=run_campaign(c,Caller(c,l,p,30_000_000,True))
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert set(seen)==set(ROLE_MODEL_MAP)
    g=seen['GENERATOR']
    assert g['background'] is True and g['store'] is True and g['text']['format']==responses_text_format('GENERATOR',c)
    assert g['reasoning']=={'effort':'high'}
    for role in ('NOVELTY_CRITIC','FEASIBILITY_CRITIC','RED_TEAM','SELECTOR'):
        body=seen[role]
        assert body['model']==ROLE_MODEL_MAP[role]
        assert body['response_format']==openai_response_format(role,c)
        assert body[list(ROLE_REQUEST_PARAMS[role])[0]]==ROLE_REQUEST_PARAMS[role]['reasoning_effort']
        assert 'temperature' not in body
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
        Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert l.db.execute('SELECT state FROM calls').fetchone()[0]=='BACKGROUND_SUBMITTED'
    posts=len([x for x in log if x[0]=='POST'])
    def finish(method,path,body,headers,timeout):
        log.append((method,path))
        if method=='POST':raise AssertionError('new POST')
        if method=='GET':return 200,responses_completed('resp_slow',generator_json(c))
        return 200,b'{}'
    Caller(c,l,provider(finish),30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
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
    Caller(c,Ledger(tmp_path/'r.db',{'RUN_ID':'r'}),provider(fake),30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert [x for x in log if x[0]=='POST']==[('POST','/v1/responses')]
    assert gets['n']==2

def test_polling_does_not_consume_another_reservation(tmp_path):
    c=Contexts();log=[]
    p=provider(gen_transport(c,log));l=Ledger(tmp_path/'r.db',{'RUN_ID':'b'})
    Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
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
    Caller(c,l,provider(fake),30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
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
    with pytest.raises(ContractError,match='background generation'):
        caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert l.export_calls()[0]['STATE']=='FAILED'
    assert l.export_calls()[0]['PROVIDER_STATUS']==status
    with pytest.raises(ContractError,match='never automatic replay'):
        caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
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
    config={'RUN_ID':'resume','GENERATOR_ENDPOINT':'RESPONSES'}
    l=Ledger(tmp_path/'r.db',config)
    Caller(c,l,p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'g0')
    with pytest.raises(ContractError,match='resume configuration differs'):
        Ledger(tmp_path/'r.db',{'RUN_ID':'resume','GENERATOR_ENDPOINT':'CHAT_COMPLETIONS'})

def test_openai_role_schemas_are_strict():
    c=Contexts()
    for role in ROLE_MODEL_MAP:
        schema=role_schema(role,c,provider=True)
        assert schema['additionalProperties'] is False
        assert set(schema['required'])==set(schema['properties'])
    card=output_schema(c,provider=True)
    assert len(card['required'])==27 and 'STREAM' not in card['properties']
    fmt=responses_text_format('GENERATOR',c)
    assert fmt['schema']==role_schema('GENERATOR',c,provider=True)

def test_archived_paid_run_is_not_opened_by_operator(monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('OPENAI_API_KEY','present')
    for run_dir in ('artifacts/generator_v0/first-shadow','artifacts/generator_v0/first-shadow-v2','artifacts/generator_v0/first-shadow-v3'):
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
