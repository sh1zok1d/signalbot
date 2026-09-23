import hashlib
import json
import pytest
from scripts.research.generator_v0.openai_provider import OpenAIProvider,ProviderFailure,MODEL
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger

def envelope(content='{}',finish='stop'):
    return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':20}}).encode()

def test_adapter_request_auth_and_durable_response(tmp_path):
    calls=[]
    def fake(body,headers,timeout):calls.append((json.loads(body),headers,timeout));return 200,envelope()
    p=OpenAIProvider('test-credential',allow_real=True,budget_micro_usd=30_000_000,transport=fake)
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});caller=Caller(c,l,p,30_000_000,True)
    assert caller.call('GENERATOR',c.generator(),'Return JSON',{'max_output_tokens':100},'test')=='{}'
    assert caller.call('GENERATOR',c.generator(),'Return JSON',{'max_output_tokens':100},'test')=='{}'
    assert len(calls)==1
    body,headers,timeout=calls[0]
    assert body['model']==MODEL and body['response_format']=={'type':'json_object'}
    assert body['max_completion_tokens']==100 and not body['stream'] and not body['store']
    assert headers['Authorization']=='Bearer test-credential' and timeout==60
    assert 'tools' not in body
    call=l.export_calls()[0];assert call['COST_MICRO_USD']==72
    assert call['RAW_RESPONSE_SHA256']==hashlib.sha256(envelope()).hexdigest()
    assert 'test-credential' not in json.dumps(l.export_calls())

@pytest.mark.parametrize('key,allow,budget',[('',True,1),('key',False,1),('key',True,0),('key',True,30_000_001)])
def test_spend_gates(key,allow,budget):
    with pytest.raises(ContractError):OpenAIProvider(key,allow_real=allow,budget_micro_usd=budget,transport=lambda *a:pytest.fail('network reached'))

@pytest.mark.parametrize('kind',['timeout','http','malformed','truncated','usage'])
def test_failure_retains_reservation_and_never_retries(tmp_path,kind):
    calls=[]
    def fake(*args):
        calls.append(1)
        if kind=='timeout':raise TimeoutError()
        if kind=='http':return 429,b'error'
        if kind=='malformed':return 200,b'not-json'
        if kind=='usage':return 200,b'{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}],"usage":{}}'
        return 200,envelope(finish='length')
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});p=OpenAIProvider('key',allow_real=True,budget_micro_usd=100000,transport=fake);caller=Caller(c,l,p,100000,True)
    for _ in range(2):
        with pytest.raises((ContractError,TimeoutError)):caller.call('GENERATOR',c.generator(),'Return JSON',{'max_output_tokens':100},'one')
    assert len(calls)==1
    assert l.db.execute('SELECT state,cost FROM calls').fetchone()==('UNCERTAIN',None)

def test_budget_denies_before_http(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'})
    p=OpenAIProvider('key',allow_real=True,budget_micro_usd=1,transport=lambda *a:pytest.fail('HTTP'))
    with pytest.raises(ContractError):Caller(c,l,p,1,True).call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')

def test_malformed_model_json_is_persisted_without_repeat(tmp_path):
    calls=[]
    def fake(*args):calls.append(1);return 200,envelope('bad-json')
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'});p=OpenAIProvider('key',allow_real=True,budget_micro_usd=100000,transport=fake);caller=Caller(c,l,p,100000,True)
    for _ in range(2):assert caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')=='bad-json'
    assert len(calls)==1 and l.export_calls()[0]['STATE']=='COMPLETE'

def test_full_real_adapter_pipeline_fake_http_only(tmp_path):
    from scripts.research.generator_v0.runner import run_campaign,GENERATOR_PROMPT
    from scripts.research.generator_v0.roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT
    from scripts.research.generator_v0.mock import MockResponder
    prompts={GENERATOR_PROMPT:'GENERATOR',NOVELTY_PROMPT:'NOVELTY_CRITIC',FEAS_PROMPT:'FEASIBILITY_CRITIC',RED_PROMPT:'RED_TEAM',SELECTOR_PROMPT:'SELECTOR'}
    c=Contexts();respond=MockResponder(c);calls=[]
    def fake(body,headers,timeout):
        b=json.loads(body);user=json.loads(b['messages'][1]['content']);calls.append(1)
        result=respond({'role':prompts[b['messages'][0]['content']],'context':user['context'],'parameters':{'slots':user.get('slots',[])}})
        return 200,envelope(result)
    p=OpenAIProvider('test-key',allow_real=True,budget_micro_usd=30_000_000,transport=fake)
    l=Ledger(tmp_path/'real-stub.db',{'RUN_ID':'fake-http-e2e'})
    result=run_campaign(c,Caller(c,l,p,30_000_000,True))
    assert len(calls)==125 and result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert l.db.execute('SELECT sum(cost) FROM calls').fetchone()[0]==125*72

def test_ambient_key_never_enables_http(monkeypatch,tmp_path):
    from scripts.research.generator_v0.__main__ import main
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch.setenv('OPENAI_API_KEY','present-but-not-authorized')
    monkeypatch.setattr(HTTPS,'__call__',lambda *args:pytest.fail('HTTP reached'))
    main(['preflight'])
    with pytest.raises(ContractError):main(['preflight','--provider','openai'])
    main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','30'])
