import json
from decimal import Decimal,ROUND_CEILING
import pytest
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.models import ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,rates,spec,request_params_for,model_for
from scripts.research.generator_v0.output_schemas import openai_response_format,role_schema
from scripts.research.generator_v0.schema import output_schema,validate_card
from scripts.research.generator_v0.mock import MockResponder

def envelope(content='{}',finish='stop'):
    return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':20}}).encode()

def provider(transport,budget=30_000_000):
    return OpenAIProvider('test-credential',allow_real=True,budget_micro_usd=budget,transport=transport)

def cost_of(role,inp=100,out=20):
    i,o=rates(role)
    return int((i*inp+o*out).to_integral_value(rounding=ROUND_CEILING))

def generator_json(contexts):
    return MockResponder(contexts)({'role':'GENERATOR','context':contexts.generator(),'parameters':{'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}})

def test_adapter_request_uses_strict_json_schema_and_role_model(tmp_path):
    calls=[]
    def fake(body,headers,timeout):calls.append((json.loads(body),headers,timeout));return 200,envelope(generator_json(Contexts()))
    c=Contexts();p=provider(fake);l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});caller=Caller(c,l,p,30_000_000,True)
    slots={'max_output_tokens':100,'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}
    raw=caller.call('GENERATOR',c.generator(),'Return JSON',slots,'test')
    assert caller.call('GENERATOR',c.generator(),'Return JSON',slots,'test')==raw
    assert len(calls)==1
    body,headers,timeout=calls[0]
    assert body['model']==ROLE_MODEL_MAP['GENERATOR']
    assert body['response_format']['type']=='json_schema'
    assert body['response_format']['json_schema']['strict'] is True
    card=body['response_format']['json_schema']['schema']['properties']['CANDIDATES']['items']
    assert card['additionalProperties'] is False
    assert 'STREAM' not in card['properties']
    assert set(card['required'])==set(c.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS'])
    assert len(card['required'])==27
    assert card['properties']['SEARCH_SURFACE']['properties']['PARAMETERS']['type']=='array'
    assert 'temperature' not in body and body['reasoning_effort']=='high'
    assert body['max_completion_tokens']==100 and not body['stream'] and not body['store']
    assert headers['Authorization']=='Bearer test-credential' and timeout==60
    assert 'tools' not in body
    call=l.export_calls()[0]
    assert call['MODEL_ID']==ROLE_MODEL_MAP['GENERATOR']
    assert call['MODEL_REQUEST_PARAMS']=={'reasoning_effort':'high'}
    assert call['COST_MICRO_USD']==cost_of('GENERATOR')
    assert 'test-credential' not in json.dumps(l.export_calls())

@pytest.mark.parametrize('key,allow,budget',[('',True,1),('key',False,1),('key',True,0),('key',True,30_000_001)])
def test_spend_gates(key,allow,budget):
    with pytest.raises(ContractError):OpenAIProvider(key,allow_real=allow,budget_micro_usd=budget,transport=lambda *a:pytest.fail('network reached'))

def test_single_model_override_is_rejected():
    with pytest.raises(ContractError,match='role-specific'):OpenAIProvider('key',allow_real=True,budget_micro_usd=1,model='gpt-4.1-mini-2025-04-14',transport=lambda *a:pytest.fail('network reached'))

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
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'});p=provider(fake);caller=Caller(c,l,p,30_000_000,True)
    for _ in range(2):
        with pytest.raises((ContractError,TimeoutError)):caller.call('GENERATOR',c.generator(),'Return JSON',{'max_output_tokens':100},'one')
    assert len(calls)==1
    assert l.db.execute('SELECT state,cost FROM calls').fetchone()==('UNCERTAIN',None)

def test_budget_denies_before_http(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'test'})
    p=OpenAIProvider('key',allow_real=True,budget_micro_usd=1,transport=lambda *a:pytest.fail('HTTP'))
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
    assert ROLE_REQUEST_PARAMS['NOVELTY_CRITIC']==ROLE_REQUEST_PARAMS['RED_TEAM']=={'reasoning_effort':'medium'}
    assert ROLE_REQUEST_PARAMS['FEASIBILITY_CRITIC']=={'reasoning_effort':'low'}
    assert ROLE_REQUEST_PARAMS['SELECTOR']=={'reasoning_effort':'none'}
    assert model_for('GENERATOR')=='gpt-6-astra'
    assert rates('GENERATOR')==(Decimal('10.00'),Decimal('50.00'))
    assert rates('NOVELTY_CRITIC')==rates('RED_TEAM')==(Decimal('2.00'),Decimal('10.00'))
    assert rates('FEASIBILITY_CRITIC')==rates('SELECTOR')==(Decimal('0.10'),Decimal('0.50'))
    assert spec('gpt-6-astra')['STRUCTURED_OUTPUTS'] is True
    assert spec('gpt-6-sol')['STRUCTURED_OUTPUTS'] is True
    assert spec('gpt-6-luna')['STRUCTURED_OUTPUTS'] is True
    assert 'none' not in spec('gpt-6-astra')['REASONING_EFFORTS']
    assert 'none' in spec('gpt-6-luna')['REASONING_EFFORTS']
    for role in ROLE_MODEL_MAP:
        params=request_params_for(role)
        assert params==ROLE_REQUEST_PARAMS[role]
        assert params['reasoning_effort'] in spec(model_for(role))['REASONING_EFFORTS']
        assert 'temperature' not in params

def _mutate_generator(contexts,mutate):
    payload=json.loads(generator_json(contexts));mutate(payload);return json.dumps(payload)

@pytest.mark.parametrize('kind,mutate',[
    ('extra',lambda p:p['CANDIDATES'][0].update(STREAM='EXECUTABLE_NOW')),
    ('missing',lambda p:p['CANDIDATES'][0].pop('FALSIFIER')),
    ('nested',lambda p:p['CANDIDATES'][0]['DATA_REQUIRED'][0].update(EXTRA='nope')),
    ('envelope',lambda p:p.update(STREAM='nope')),
])
def test_structured_response_rejects_schema_violations_without_retry(tmp_path,kind,mutate):
    calls=[];c=Contexts()
    def fake(*args):calls.append(1);return 200,envelope(_mutate_generator(c,mutate))
    l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'});p=provider(fake);caller=Caller(c,l,p,30_000_000,True)
    for _ in range(2):
        with pytest.raises(ContractError):caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'one')
    assert len(calls)==1 and l.export_calls()[0]['STATE']=='UNCERTAIN'

def test_application_validator_still_rejects_semantic_violations(tmp_path):
    c=Contexts();payload=json.loads(generator_json(c));payload['CANDIDATES'][0]['HORIZON']='2025'
    calls=[]
    def fake(*args):calls.append(1);return 200,envelope(json.dumps(payload))
    p=provider(fake);l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'});caller=Caller(c,l,p,30_000_000,True)
    raw=caller.call('GENERATOR',c.generator(),'JSON',{'max_output_tokens':100},'sem')
    parsed=json.loads(raw)
    assert parsed['CANDIDATES'][0]['HORIZON']=='2025'
    with pytest.raises(ContractError,match='protected'):validate_card(parsed['CANDIDATES'][0],c)
    assert calls==[1] and l.export_calls()[0]['STATE']=='COMPLETE'

def test_each_role_schema_and_model_parameters(tmp_path):
    c=Contexts();respond=MockResponder(c);seen={}
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT,run_campaign
    from scripts.research.generator_v0.roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT
    prompts={GENERATOR_PROMPT:'GENERATOR',NOVELTY_PROMPT:'NOVELTY_CRITIC',FEAS_PROMPT:'FEASIBILITY_CRITIC',RED_PROMPT:'RED_TEAM',SELECTOR_PROMPT:'SELECTOR'}
    def fake(body,headers,timeout):
        b=json.loads(body);role=prompts[b['messages'][0]['content']];seen.setdefault(role,b)
        user=json.loads(b['messages'][1]['content'])
        result=respond({'role':role,'context':user['context'],'parameters':{'slots':user.get('slots',[])}})
        return 200,envelope(result)
    p=provider(fake);l=Ledger(tmp_path/'r.db',{'RUN_ID':'roles'})
    result=run_campaign(c,Caller(c,l,p,30_000_000,True))
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert set(seen)==set(ROLE_MODEL_MAP)
    for role,body in seen.items():
        assert body['model']==ROLE_MODEL_MAP[role]
        fmt=body['response_format']
        assert fmt==openai_response_format(role,c)
        assert fmt['json_schema']['strict'] is True
        assert fmt['json_schema']['schema']['additionalProperties'] is False
        params=request_params_for(role)
        assert params==ROLE_REQUEST_PARAMS[role]
        for key,value in params.items():assert body[key]==value
        assert 'temperature' not in body
        assert params['reasoning_effort'] in spec(body['model'])['REASONING_EFFORTS']
    assert {row['MODEL_ID'] for row in l.export_calls()}==set(ROLE_MODEL_MAP.values())
    expected=4*cost_of('GENERATOR')+40*cost_of('NOVELTY_CRITIC')+40*cost_of('FEASIBILITY_CRITIC')+40*cost_of('RED_TEAM')+cost_of('SELECTOR')
    assert l.db.execute('SELECT sum(cost) FROM calls').fetchone()[0]==expected
    assert l.db.execute('SELECT count(*) FROM calls').fetchone()[0]==125

def test_resume_identity_includes_role_model_map(tmp_path):
    c=Contexts();calls=[]
    def fake(body,headers,timeout):
        calls.append(json.loads(body)['model'])
        return 200,envelope(generator_json(c))
    p=provider(fake);config={'RUN_ID':'resume','ROLE_MODEL_MAP':dict(ROLE_MODEL_MAP),'ROLE_REQUEST_PARAMS':{k:dict(v) for k,v in ROLE_REQUEST_PARAMS.items()}}
    l=Ledger(tmp_path/'r.db',config)
    caller=Caller(c,l,p,30_000_000,True)
    slots={'max_output_tokens':100,'slots':[{'CANDIDATE_ID':'C001','MECHANISM_FAMILY':'A','INFORMATION_SOURCE':'KLINES'}]}
    caller.call('GENERATOR',c.generator(),'JSON',slots,'g0')
    caller.call('GENERATOR',c.generator(),'JSON',slots,'g0')
    assert calls==[ROLE_MODEL_MAP['GENERATOR']]
    Caller(c,Ledger(tmp_path/'r.db',config),p,30_000_000,True).call('GENERATOR',c.generator(),'JSON',slots,'g0')
    assert calls==[ROLE_MODEL_MAP['GENERATOR']]
    with pytest.raises(ContractError,match='resume configuration differs'):
        Ledger(tmp_path/'r.db',{'RUN_ID':'resume','ROLE_MODEL_MAP':{'GENERATOR':'changed'}})
    with pytest.raises(ContractError,match='resume configuration differs'):
        drifted={k:dict(v) for k,v in ROLE_REQUEST_PARAMS.items()};drifted['GENERATOR']={'reasoning_effort':'low'}
        Ledger(tmp_path/'r.db',{'RUN_ID':'resume','ROLE_MODEL_MAP':dict(ROLE_MODEL_MAP),'ROLE_REQUEST_PARAMS':drifted})

def test_openai_role_schemas_are_strict():
    c=Contexts()
    for role in ROLE_MODEL_MAP:
        schema=role_schema(role,c,provider=True)
        assert schema['additionalProperties'] is False
        assert set(schema['required'])==set(schema['properties'])
    card=output_schema(c,provider=True)
    assert len(card['required'])==27 and 'STREAM' not in card['properties']

def test_archived_paid_run_is_not_opened_by_operator(monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('OPENAI_API_KEY','present')
    with pytest.raises(ContractError,match='archived paid run'):
        main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','10','--run-dir','artifacts/generator_v0/first-shadow'])

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
