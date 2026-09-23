"""Offline protected-data semantics and COMPLETE carry-forward. No real LLM calls."""
import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0.derive import derive_complete_rounds,expected_generator_request,transport_identity,DERIVED_STATUS
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture,slot_plan
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.runner import run_campaign
from scripts.research.generator_v0.schema import validate_card
from scripts.research.generator_v0.__main__ import main

FIXTURE=Path(__file__).resolve().parent/'fixtures'/'generator_v0_c018.json'
CAP=7117536
COST0=1213380
COST1=1352350
IMPORTED_COST=COST0+COST1
REMAINING=CAP-IMPORTED_COST

def c018():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))

def base_card():
    from tests.research.test_generator_v0_schema import card
    return card()

def source_config(contexts,run_id='first-shadow-v5'):
    ident=transport_identity(contexts)
    return {
        'RUN_ID':run_id,'PROVIDER':'OPENAI_MIXED','MODEL':'ROLE_SPECIFIC','SIZE':40,'CAP_MICRO_USD':CAP,
        'CONTEXT_DIGEST':digest(contexts.generator()),'IMPLEMENTATION_DIGEST':'source-test',
        'ROLE_MODEL_MAP':{'GENERATOR':'gpt-6-astra'},'ROLE_REQUEST_PARAMS':{'GENERATOR':{'reasoning_effort':'high'}},
        'PRICE_TABLE':{},'ROUTING_DIGEST':'source-test','REQUEST_TIMEOUT_SECONDS':600,**ident,
    }

def complete_blob(cards,rid):
    raw=canonical({'CANDIDATES':cards})
    return {'raw':raw,'raw_sha256':hashlib.sha256(('wire-'+rid).encode()).hexdigest(),
            'response_id':rid,'provider_status':'completed','provider_envelope':{'id':rid,'status':'completed'}}

def write_source(path,contexts,*,mutate_request=None,state='COMPLETE',include_c018=True,rounds=(0,1),config=None):
    path.mkdir(parents=True)
    cfg=config or source_config(contexts)
    l=Ledger(path/'run.sqlite',cfg)
    plan=slot_plan(40)
    for n in rounds:
        slots=plan[n*10:(n+1)*10]
        req=expected_generator_request(contexts,slots,n)
        if mutate_request:req=mutate_request(req,n)
        cards=[fixture(s,contexts) for s in slots]
        if include_c018 and n==1:
            real=c018()
            idx=next(i for i,s in enumerate(slots) if s['CANDIDATE_ID']=='C018')
            cards[idx]=real
        rid='resp_src_'+str(n)
        blob=complete_blob(cards,rid)
        cost=COST0 if n==0 else COST1
        usage={'input_tokens':4588+n,'output_tokens':23350 if n==0 else 26129,'reasoning_tokens':11897 if n==0 else 13984}
        key=digest(req)
        if state=='COMPLETE':
            l.db.execute('INSERT INTO calls(key,request,state,reserved,response,cost,usage,error) VALUES (?,?,?,?,?,?,?,?)',
                         (key,canonical(req),state,cost+1000,canonical(blob),cost,canonical(usage),None))
        else:
            l.db.execute('INSERT INTO calls(key,request,state,reserved,response,cost,usage,error) VALUES (?,?,?,?,?,?,?,?)',
                         (key,canonical(req),state,cost+1000,canonical({'response_id':rid,'provider_status':'queued'}) if state=='BACKGROUND_SUBMITTED' else None,
                          None if state!='FAILED' else 1,canonical(usage) if state=='FAILED' else None,state))
        l.db.commit()
    l.close()
    return path

def test_c018_fixture_passes_new_protected_data_rule():
    card=c018()
    assert card['CANDIDATE_ID']=='C018'
    assert card['PROTECTED_DATA_REQUIREMENT'] is False
    assert all(row['LEGAL_RANGE']=='2020-01..2024-12' for row in card['DATA_REQUIRED'])
    assert 'No 2025/2026 quotes' in card['NO_LOOKAHEAD_RULE']
    validate_card(card,Contexts())

def test_mention_only_exclusion_in_no_lookahead_passes():
    x=base_card();x['NO_LOOKAHEAD_RULE']='No 2025/2026 data are permitted.'
    validate_card(x,Contexts())

def test_safe_explicit_range_on_unknown_blocked_source_passes():
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['quotes'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':'PROSPECTIVE_UNKNOWN_QUOTES','OBSERVABLE':'quotes','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':'2020-01..2024-12'}]
    validate_card(x,Contexts())

def test_safe_frozen_catalog_per_snapshot_passes():
    x=base_card()
    x['DATA_REQUIRED']=[{'DATASET':'MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0','OBSERVABLE':'spot 1h','STATUS':'DATA_READY','LEGAL_RANGE':'per snapshot'}]
    validate_card(x,Contexts())

@pytest.mark.parametrize('dataset,rng,match',[
    ('PROTECTED_2025_2026','2020-01..2024-12','protected source'),
    ('CORE_BTC_BINANCE_V0','2020-01..2025-06','protected legal range'),
    ('CORE_BTC_BINANCE_V0','2024-01..2026-01','protected legal range'),
    ('unknown','2024-01..2025-01','protected legal range'),
    ('unknown','latest available','ambiguous protected range'),
    ('unknown','through present','ambiguous protected range'),
    ('unknown','current','ambiguous protected range'),
    ('unknown','per snapshot','ambiguous protected range'),
])
def test_protected_and_ambiguous_legal_ranges_fail(dataset,rng,match):
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['x'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':dataset,'OBSERVABLE':'x','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':rng}]
    with pytest.raises(ContractError,match=match):validate_card(x,Contexts())

def test_protected_data_requirement_true_fails():
    x=base_card();x['PROTECTED_DATA_REQUIREMENT']=True
    with pytest.raises(ContractError,match='protected data requirement'):validate_card(x,Contexts())

def test_exact_compatible_complete_import(tmp_path):
    c=Contexts();src=write_source(tmp_path/'src',c)
    before=src.joinpath('run.sqlite').read_bytes()
    dest=tmp_path/'dst'
    report=derive_complete_rounds(src,dest,1,c)
    assert src.joinpath('run.sqlite').read_bytes()==before
    assert report['STATUS']==DERIVED_STATUS
    assert report['IMPORTED_GENERATION_ROUNDS']==['generation:0','generation:1']
    assert report['IMPORTED_COST_MICRO_USD']==IMPORTED_COST
    assert report['REMAINING_MICRO_USD']==REMAINING==4551806
    assert report['C018_REVALIDATION']=='PASS'
    assert report['REAL_LLM_CALLS_MADE'] is False
    l=Ledger(dest/'run.sqlite')
    calls=l.export_calls()
    assert [x['STATE'] for x in calls]==['COMPLETE','COMPLETE']
    assert [x['COST_MICRO_USD'] for x in calls]==[COST0,COST1]
    assert all(x['SOURCE_RUN_ID']=='first-shadow-v5' for x in calls)
    assert all(x['SOURCE_CALL_KEY']==x['CALL_KEY'] for x in calls)
    assert all(x['SOURCE_RESPONSE_ID']==x['RESPONSE_ID'] for x in calls)
    assert all(x['SOURCE_RAW_RESPONSE_SHA256']==x['RAW_RESPONSE_SHA256'] for x in calls)
    env=json.loads(l.db.execute('SELECT response FROM calls LIMIT 1').fetchone()[0])
    assert env['provider_envelope']['status']=='completed'
    assert l.spent_micro_usd()==IMPORTED_COST
    l.close()

def test_imported_call_does_not_trigger_http(tmp_path,monkeypatch):
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch.setattr(HTTPS,'__call__',lambda *a,**k:pytest.fail('HTTP reached'))
    c=Contexts();src=write_source(tmp_path/'src',c)
    derive_complete_rounds(src,tmp_path/'dst',1,c)

def test_source_archive_byte_for_byte_with_cli(tmp_path,monkeypatch):
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch.setattr(HTTPS,'__call__',lambda *a,**k:pytest.fail('HTTP reached'))
    c=Contexts();src=write_source(tmp_path/'src',c)
    before=src.joinpath('run.sqlite').read_bytes()
    main(['derive','--source-run-dir',str(src),'--run-dir',str(tmp_path/'dst'),'--through-generation','1'])
    assert src.joinpath('run.sqlite').read_bytes()==before
    assert (tmp_path/'dst'/'derived_import.json').exists()

@pytest.mark.parametrize('field,mut',[
    ('prompt',lambda r,n:{**r,'prompt':'tampered prompt Return JSON'}),
    ('context',lambda r,n:{**r,'context':{**r['context'],'CANDIDATE_SCHEMA':{'tampered':True}}}),
    ('model',lambda r,n:{**r,'model':'gpt-6-sol'}),
    ('effort',lambda r,n:{**r,'model_request_params':{'reasoning_effort':'medium'}}),
    ('output_bound',lambda r,n:{**r,'parameters':{**r['parameters'],'max_output_tokens':16000}}),
    ('slot_assignments',lambda r,n:{**r,'parameters':{**r['parameters'],'slots':[{**s,'INFORMATION_SOURCE':'TAMPERED'} for s in r['parameters']['slots']]}}),
])
def test_incompatible_request_identity_refuses(tmp_path,field,mut):
    c=Contexts();src=write_source(tmp_path/'src',c,mutate_request=mut)
    with pytest.raises(ContractError,match='incompatible COMPLETE call'):
        derive_complete_rounds(src,tmp_path/'dst',1,c)
    assert not (tmp_path/'dst').exists()

def test_incompatible_schema_digest_refuses(tmp_path):
    c=Contexts();cfg=source_config(c);cfg['GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST']='0'*64
    src=write_source(tmp_path/'src',c,config=cfg)
    with pytest.raises(ContractError,match='schema_digest'):
        derive_complete_rounds(src,tmp_path/'dst',1,c)

@pytest.mark.parametrize('state',['FAILED','UNCERTAIN','BACKGROUND_SUBMITTED'])
def test_non_complete_source_cannot_import(tmp_path,state):
    c=Contexts();src=write_source(tmp_path/'src',c,state=state)
    with pytest.raises(ContractError,match='cannot be imported'):
        derive_complete_rounds(src,tmp_path/'dst',1,c)

def test_imported_cost_counts_against_cap_exactly_once(tmp_path):
    c=Contexts();src=write_source(tmp_path/'src',c)
    dest=tmp_path/'dst'
    derive_complete_rounds(src,dest,1,c)
    l=Ledger(dest/'run.sqlite')
    assert l.spent_micro_usd()==IMPORTED_COST
    assert l.reserve('extra',{'n':1},REMAINING,CAP) is None
    with pytest.raises(ContractError,match='budget exceeded'):l.reserve('over',{'n':2},1,CAP)
    l.close()
    with pytest.raises(ContractError,match='destination run exists'):
        derive_complete_rounds(src,dest,1,c)

def test_revalidation_uses_new_validator_and_stops_without_generation_2(tmp_path,monkeypatch):
    from scripts.research.generator_v0.openai_provider import HTTPS
    posts=[]
    def fake(*a,**k):
        posts.append(a);pytest.fail('HTTP reached')
    monkeypatch.setattr(HTTPS,'__call__',fake)
    c=Contexts();src=write_source(tmp_path/'src',c)
    dest=tmp_path/'dst'
    report=derive_complete_rounds(src,dest,1,c)
    assert 'C018' in report['CARD_IDS']
    l=Ledger(dest/'run.sqlite')
    assert l.get('status')==DERIVED_STATUS
    p=MockProvider(lambda r:pytest.fail('provider complete reached'))
    with pytest.raises(ContractError,match='derived import stopped after revalidation'):
        run_campaign(c,Caller(c,l,p,CAP,False))
    assert p.calls==0
    l.close()
    monkeypatch.setenv('OPENAI_API_KEY','present')
    with pytest.raises(ContractError,match='archived paid run|derived import|resume configuration|destination'):
        main(['resume','--provider','openai','--allow-real-llm','--budget-usd','7.117536','--run-dir',str(dest)])
    assert posts==[]

def test_derive_refuses_real_provider_flags(tmp_path):
    with pytest.raises(ContractError,match='derive is offline'):
        main(['derive','--provider','openai','--allow-real-llm','--budget-usd','1','--source-run-dir',str(tmp_path/'src'),'--run-dir',str(tmp_path/'dst')])

def test_imported_complete_caller_reuse_does_not_post(tmp_path):
    from scripts.research.generator_v0.openai_provider import OpenAIProvider
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT
    from scripts.research.generator_v0.models import GENERATOR_MAX_OUTPUT_TOKENS
    c=Contexts();src=write_source(tmp_path/'src',c)
    dest=tmp_path/'dst'
    derive_complete_rounds(src,dest,1,c)
    l=Ledger(dest/'run.sqlite')
    p=OpenAIProvider('key',allow_real=True,budget_micro_usd=CAP,transport=lambda *a,**k:pytest.fail('HTTP reached'),sleeper=lambda s:None)
    raw=Caller(c,l,p,CAP,True).call('GENERATOR',c.generator(),GENERATOR_PROMPT,{'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':slot_plan(40)[:10]},'generation:0')
    assert json.loads(raw)['CANDIDATES'][0]['CANDIDATE_ID']=='C001'
    raw2=Caller(c,l,p,CAP,True).call('GENERATOR',c.generator(),GENERATOR_PROMPT,{'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':slot_plan(40)[10:20]},'generation:1')
    assert any(card['CANDIDATE_ID']=='C018' for card in json.loads(raw2)['CANDIDATES'])
    l.close()

def test_validation_error_stops_without_silent_repair(tmp_path):
    c=Contexts()
    src=write_source(tmp_path/'src',c,include_c018=False)
    l=Ledger.open_readonly(src/'run.sqlite')
    key,request,response=l.db.execute('SELECT key,request,response FROM calls WHERE request LIKE ?',('%generation:1%',)).fetchone()
    l.close()
    blob=json.loads(response)
    cards=json.loads(blob['raw'])['CANDIDATES']
    cards[0]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01..2025-06'
    blob['raw']=canonical({'CANDIDATES':cards})
    w=sqlite3.connect(src/'run.sqlite')
    w.execute('UPDATE calls SET response=? WHERE key=?',(canonical(blob),key));w.commit();w.close()
    with pytest.raises(ContractError,match='protected legal range'):
        derive_complete_rounds(src,tmp_path/'dst',1,c)
    assert not (tmp_path/'dst').exists()
