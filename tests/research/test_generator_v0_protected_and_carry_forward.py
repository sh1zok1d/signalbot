"""Offline protected-data semantics and COMPLETE carry-forward. No real LLM calls."""
import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0.derive import derive_complete_rounds,expected_generator_request,transport_identity,DERIVED_STATUS,CONTINUATION_STATUS,authorize_derived_continuation,authorize_budget_extension,remaining_campaign_budget_preflight,OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture,slot_plan
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.runner import run_campaign
from scripts.research.generator_v0.schema import validate_card,classify_legal_range
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
        cost=COST0 if n==0 else COST1 if n==1 else 1213820
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

def test_c018_exclusion_statement_is_not_a_requirement():
    x=base_card()
    x['NO_LOOKAHEAD_RULE']=('Use only quotes disseminated by the minute mark and no older than two seconds. '
        'Never use nearest future quotes. Establish common legal support before computing either the observed statistic or its null. '
        'No 2025/2026 quotes, execution assumptions, or post hoc best-venue selection are permitted.')
    validate_card(x,Contexts())

def test_safe_exclusion_allowed_wording_passes():
    x=base_card()
    x['NO_LOOKAHEAD_RULE']=('Use only quotes disseminated by the minute mark. '
        'No 2025/2026 quotes, execution assumptions, or post hoc best-venue selection are allowed.')
    validate_card(x,Contexts())

def test_ordinary_no_lookahead_without_protected_year_passes():
    x=base_card()
    x['NO_LOOKAHEAD_RULE']='Every predictor must have an observable public timestamp at or before decision T.'
    validate_card(x,Contexts())

def test_methodology_current_batch_and_candidate_are_not_protected_windows():
    x=base_card()
    x['WHY_NOT_A_RESCUE']='This current candidate is scored against the current batch, not market quotes.'
    validate_card(x,Contexts())

@pytest.mark.parametrize('field,text',[
    ('NO_LOOKAHEAD_RULE','Use the latest closed 1m bar at or before T.'),
    ('NO_LOOKAHEAD_RULE','Features use only the current and prior closed bars.'),
    ('NO_LOOKAHEAD_RULE','Estimate the residualization fit before the current observation.'),
    ('CAUSAL_OR_STRUCTURAL_STORY','Dealers hedge against the current regime state.'),
    ('INFORMATION_SOURCE','Timestamp of the latest scheduled FOMC statement before T'),
    ('OBSERVABLE','current funding rate as-of T'),
    ('MAIN_CONFOUNDERS','Current volatility level'),
])
def test_point_in_time_latest_and_current_wording_passes(field,text):
    x=base_card();x[field]=text
    validate_card(x,Contexts())

@pytest.mark.parametrize('rule',[
    'No 2025/2026 quotes. The target is the 2025 return and is permitted.',
    'No 2026 data; outcomes measured in calendar 2025 are permitted.',
    'No 2025 restrictions apply: 2025 outcomes are permitted.',
    'No 2025/2026 quotes are not permitted.',
    'No 2025 data are forbidden.',
])
def test_exclusion_parser_does_not_swallow_requirements(rule):
    x=base_card();x['NO_LOOKAHEAD_RULE']=rule
    with pytest.raises(ContractError,match='protected data requirement'):validate_card(x,Contexts())

def test_non_exclusion_in_no_lookahead_fails():
    x=base_card();x['NO_LOOKAHEAD_RULE']='outcomes measured in 2025'
    with pytest.raises(ContractError,match='protected data requirement'):validate_card(x,Contexts())

def test_safe_explicit_range_on_unknown_blocked_source_passes():
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['quotes'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':'PROSPECTIVE_UNKNOWN_QUOTES','OBSERVABLE':'quotes','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':'2020-01..2024-12'}]
    validate_card(x,Contexts())

def test_safe_frozen_catalog_per_snapshot_passes():
    x=base_card()
    x['DATA_REQUIRED']=[{'DATASET':'MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0','OBSERVABLE':'spot 1h','STATUS':'DATA_READY','LEGAL_RANGE':'per snapshot'}]
    validate_card(x,Contexts())

@pytest.mark.parametrize('rng',[
    'Required historical window: 2020-01..2024-12; coverage unverified and not catalogued',
    'Required historical window: 2020-01..2024-12; no known public coverage',
    'Required historical window: 2022-01..2024-12; coverage unverified and not catalogued',
])
def test_real_v5_annotated_legal_range_passes(rng):
    inner=rng.split(':',1)[1].split(';',1)[0].strip()
    assert classify_legal_range(rng)==classify_legal_range(inner)
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['quotes'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':'PROSPECTIVE_UNKNOWN_QUOTES','OBSERVABLE':'quotes','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':rng}]
    validate_card(x,Contexts())

@pytest.mark.parametrize('rng,inner',[
    ('Proposed archive limited to 2020-01..2024-12; no catalog-authorized options coverage is claimed.','2020-01..2024-12'),
    ('Proposed event reconstruction within 2020-01..2024-12; pre-2020 ancestry only to establish output ages. No catalog-authorized chain archive is claimed.','2020-01..2024-12'),
    ('Required public-receipt records for 2020-01..2024-12 only; historical authority is unproven.','2020-01..2024-12'),
    ('Proposed historical coverage limited to 2020-01..2024-12; no catalog-authorized order-book archive is claimed.','2020-01..2024-12'),
    ('Proposed official notices and interruptions strictly pre-2020; no catalog-authorized notice archive is claimed.','pre-2020'),
    ('Public benchmark published before 2020; panel evaluation limited to legal 2019-12..2024-12 bars.','2019-12..2024-12'),
    ('Required chain observations limited to 2020-01..2024-12; original pre-expiry publication authority is unproven.','2020-01..2024-12'),
    ('Proposed rule versions effective within 2020..2024; no catalog-authorized rule archive is claimed.','2020..2024'),
    ('Proposed index coverage limited to 2020-01..2024-12; no catalog-authorized index archive is claimed.','2020-01..2024-12'),
])
def test_generation2_wrapped_legal_range_passes(rng,inner):
    assert classify_legal_range(rng)==classify_legal_range(inner)
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['quotes'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':'PROSPECTIVE_UNKNOWN_QUOTES','OBSERVABLE':'quotes','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':rng}]
    validate_card(x,Contexts())

@pytest.mark.parametrize('rng,match',[
    ('Required historical window: 2020-01..2025-01; coverage unverified and not catalogued','protected legal range'),
    ('Required historical window: 2020-01..2024-12; use 2025 if available','ambiguous protected range'),
    ('Required historical window: 2020-01..2024-12; through present','ambiguous protected range'),
    ('Required historical window: 2020-01..2024-12; latest available','ambiguous protected range'),
    ('Required historical window: 2020-01..2024-12; then evaluate next year','ambiguous protected range'),
    ('Historical window maybe 2020-01..2024-12','ambiguous protected range'),
    ('2020-01..2024-12; coverage unverified and not catalogued; extra text','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2025-01; no coverage is claimed.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12; use 2025 if available.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12; extend through present.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12; latest available data may be used.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12; then evaluate the next year.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12 and 2025-01..2025-06; no coverage is claimed.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2025-01; no catalog-authorized options coverage is claimed.','protected legal range'),
    ('Proposed archive limited to 2020-01..2024-12; no catalog-authorized options 2024 coverage is claimed.','ambiguous protected range'),
    ('Proposed archive limited to 2020-01..2024-12; no catalog-authorized latest available coverage is claimed.','ambiguous protected range'),
    ('Proposed event reconstruction within 2020-01..2024-12; pre-2025 ancestry only to establish output ages. No catalog-authorized chain archive is claimed.','ambiguous protected range'),
    ('Proposed event reconstruction within 2020-01..2024-12; no catalog-authorized chain archive is claimed.','ambiguous protected range'),
    ('The proposed archive limited to 2020-01..2024-12; no catalog-authorized options coverage is claimed.','ambiguous protected range'),
])
def test_unsafe_annotated_legal_range_fails(rng,match):
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['x'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':'unknown','OBSERVABLE':'x','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':rng}]
    with pytest.raises(ContractError,match=match):validate_card(x,Contexts())

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

@pytest.mark.parametrize('mutation',[
    lambda x:x.update(HORIZON='calendar year 2025'),
    lambda x:x.update(PRIMARY_TARGET='BTC return during 2025'),
    lambda x:x.update(OBSERVABLE='2025 realized volatility'),
    lambda x:x.update(FUNCTION='compare 2024 state to 2025 outcome'),
    lambda x:x.update(BASELINE_OR_NULL='evaluate on the 2025-2026 holdout'),
    lambda x:x.update(FALSIFIER='evaluate on 2025 observations'),
    lambda x:x.update(CAUSAL_OR_STRUCTURAL_STORY='The mechanism must be evaluated on calendar 2025.'),
    lambda x:x.update(SEARCH_SURFACE={'PARAMETERS':{'END_YEAR':[2024,2025]},'MAX_VARIANTS':2}),
    lambda x:x.update(INFORMATION_SOURCE='latest/current bars through today'),
    lambda x:x.update(PRIMARY_TARGET='BTC return through today'),
    lambda x:x.update(HORIZON='until present'),
    lambda x:x.update(OBSERVABLE='latest available closes'),
    lambda x:x['DATA_REQUIRED'][0].update(OBSERVABLE='latest closes through today'),
    lambda x:x.update(HORIZON='post-2024'),
    lambda x:x.update(HORIZON='after 2024'),
    lambda x:x.update(HORIZON='since 2024'),
    lambda x:x.update(HORIZON='2024+'),
    lambda x:x.update(HORIZON='2024 onward'),
    lambda x:x.update(HORIZON='2024 onwards'),
    lambda x:x.update(HORIZON='2024 and later'),
    lambda x:x.update(HORIZON='2024-present'),
    lambda x:x.update(HORIZON='the year after 2024'),
    lambda x:x.update(PRIMARY_TARGET='returns from 2024-07 onward'),
    lambda x:x.update(SEARCH_SURFACE={'PARAMETERS':{'WINDOW':['open-ended']},'MAX_VARIANTS':1}),
    lambda x:x.update(OBSERVABLE='latest available'),
    lambda x:x.update(OBSERVABLE='latest data'),
    lambda x:x.update(OBSERVABLE='latest quotes'),
    lambda x:x.update(OBSERVABLE='latest prices'),
    lambda x:x.update(OBSERVABLE='latest observations'),
    lambda x:x.update(OBSERVABLE='current bars'),
    lambda x:x.update(OBSERVABLE='current quotes'),
    lambda x:x.update(OBSERVABLE='current closes'),
    lambda x:x.update(OBSERVABLE='current prices'),
    lambda x:x.update(OBSERVABLE='current data'),
    lambda x:x.update(HORIZON='current available window'),
    lambda x:x.update(HORIZON='current observation window'),
    lambda x:x.update(HORIZON='through present'),
    lambda x:x.update(HORIZON='up to now'),
])
def test_operational_protected_year_and_open_window_fail(mutation):
    x=base_card();mutation(x)
    with pytest.raises(ContractError,match='protected data requirement'):validate_card(x,Contexts())

@pytest.mark.parametrize('dataset,observable',[
    ('BTCUSDT_TRADES_2025','closes'),
    ('protected_2025_2026','closes'),
    ('PROTECTED-2025-2026','closes'),
    ('unknown','2025-2026 closes'),
])
def test_data_required_protected_aliases_fail(dataset,observable):
    x=base_card()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['x'],DATA_GAP_CLASS='COST')
    x['DATA_REQUIRED']=[{'DATASET':dataset,'OBSERVABLE':observable,'STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':'2020-01..2024-12'}]
    with pytest.raises(ContractError,match='protected'):validate_card(x,Contexts())

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
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0
    assert report.get('CARDS_WRITTEN') is False
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

def test_authorize_derived_continuation_requires_actor_reason_and_status(tmp_path):
    c=Contexts();src=write_source(tmp_path/'src',c);dest=tmp_path/'dst'
    derive_complete_rounds(src,dest,1,c)
    with pytest.raises(ContractError,match='actor and reason required'):
        authorize_derived_continuation(dest,'','continue')
    with pytest.raises(ContractError,match='actor and reason required'):
        authorize_derived_continuation(dest,'owner','')
    with pytest.raises(ContractError,match='offline'):
        main(['authorize-derived-continuation','--provider','openai','--allow-real-llm','--budget-usd','1','--run-dir',str(dest),'--actor','owner','--reason','go'])
    report=authorize_derived_continuation(dest,'owner','revalidation passed; continue remaining rounds')
    assert report['STATUS']==CONTINUATION_STATUS
    assert report['REAL_LLM_CALLS_MADE'] is False
    l=Ledger(dest/'run.sqlite')
    assert l.get('status')==CONTINUATION_STATUS
    kinds=[k for k, in l.db.execute("SELECT kind FROM events ORDER BY n")]
    assert 'DERIVED_CONTINUATION_AUTHORIZED' in kinds
    l.close()
    with pytest.raises(ContractError,match='DERIVED_IMPORTED_REVALIDATED'):
        authorize_derived_continuation(dest,'owner','again')

def test_offline_derive_authorize_continue_to_pending_human_review(tmp_path,monkeypatch):
    from scripts.research.generator_v0.openai_provider import HTTPS
    from scripts.research.generator_v0.runner import GENERATOR_PROMPT
    from scripts.research.generator_v0.roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT
    from scripts.research.generator_v0.mock import MockResponder
    from tests.research.test_generator_v0_openai import chat_envelope,responses_create,responses_completed,provider
    monkeypatch.setattr(HTTPS,'__call__',lambda *a,**k:pytest.fail('real HTTPS reached'))
    c=Contexts();src=write_source(tmp_path/'src',c);dest=tmp_path/'dst'
    report=derive_complete_rounds(src,dest,1,c)
    assert report['STATUS']==DERIVED_STATUS
    assert report['CARDS_WRITTEN'] is False
    l=Ledger(dest/'run.sqlite')
    assert l.get('status')==DERIVED_STATUS
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0
    p_block=MockProvider(lambda r:pytest.fail('provider complete reached'))
    with pytest.raises(ContractError,match='generation continuation is not authorized'):
        run_campaign(c,Caller(c,l,p_block,CAP,False))
    l.close()
    with pytest.raises(ContractError,match='derived import|resume configuration'):
        main(['resume','--run-dir',str(dest)])
    auth=main(['authorize-derived-continuation','--run-dir',str(dest),'--actor','owner','--reason','continue after protected-data revalidation'])
    l=Ledger(dest/'run.sqlite')
    assert l.get('status')==CONTINUATION_STATUS
    respond=MockResponder(c)
    prompts={GENERATOR_PROMPT:'GENERATOR',NOVELTY_PROMPT:'NOVELTY_CRITIC',FEAS_PROMPT:'FEASIBILITY_CRITIC',RED_PROMPT:'RED_TEAM',SELECTOR_PROMPT:'SELECTOR'}
    log=[];created={'n':0};payloads={}
    def fake(method,path,body,headers,timeout):
        log.append((method,path,json.loads(body) if body else None))
        if method=='POST' and path=='/v1/responses':
            b=json.loads(body);user=json.loads(b['input']);slots=user.get('slots') or []
            ids=[s['CANDIDATE_ID'] for s in slots]
            assert ids[0] not in ('C001','C011')
            created['n']+=1;rid='resp_new_'+str(created['n'])
            payloads[rid]=respond({'role':'GENERATOR','context':user['context'],'parameters':{'slots':slots}})
            return 200,responses_create(rid)
        if method=='GET' and path.startswith('/v1/responses/'):
            rid=path.rsplit('/',1)[1]
            return 200,responses_completed(rid,payloads[rid])
        if method=='DELETE':return 200,b'{}'
        assert path=='/v1/chat/completions'
        b=json.loads(body);role=prompts[b['messages'][0]['content']]
        user=json.loads(b['messages'][1]['content'])
        result=respond({'role':role,'context':user['context'],'parameters':{'slots':user.get('slots',[])}})
        return 200,chat_envelope(result)
    p=provider(fake,budget=CAP)
    result=run_campaign(c,Caller(c,l,p,CAP,True))
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert len(result['CANDIDATES'])==40
    gen_posts=[row for row in log if row[0]=='POST' and row[1]=='/v1/responses']
    assert len(gen_posts)==2
    first_ids=[]
    for row in gen_posts:
        slots=json.loads(row[2]['input'])['slots']
        first_ids.append(slots[0]['CANDIDATE_ID'])
    assert first_ids==['C021','C031']
    calls=l.export_calls()
    slots={json.loads(req)['slot']:state for req,state in l.db.execute('SELECT request,state FROM calls') if (json.loads(req).get('slot') or '').startswith('generation:')}
    assert slots['generation:0']=='COMPLETE' and slots['generation:1']=='COMPLETE'
    assert slots['generation:2']=='COMPLETE' and slots['generation:3']=='COMPLETE'
    imported=[x for x in calls if x['SOURCE_RUN_ID']=='first-shadow-v5']
    assert len(imported)==2
    assert sum(x['COST_MICRO_USD'] for x in imported)==IMPORTED_COST
    assert l.db.execute("SELECT count(*) FROM cards").fetchone()[0]==40
    assert l.get('config')['CAP_MICRO_USD']==CAP==7117536
    assert l.spent_micro_usd()>IMPORTED_COST
    assert l.get('status')=='PENDING_HUMAN_REVIEW'
    assert created['n']==2
    l.close()

def test_through_generation_2_imports_three_complete_rounds(tmp_path):
    c=Contexts();src=write_source(tmp_path/'src',c,rounds=(0,1,2))
    before=src.joinpath('run.sqlite').read_bytes()
    dest=tmp_path/'dst'
    report=derive_complete_rounds(src,dest,2,c)
    assert src.joinpath('run.sqlite').read_bytes()==before
    assert report['STATUS']==DERIVED_STATUS
    assert report['IMPORTED_GENERATION_ROUNDS']==['generation:0','generation:1','generation:2']
    assert report['IMPORTED_COST_MICRO_USD']==3779550
    assert report['CARDS_WRITTEN'] is False
    assert report['REAL_LLM_CALLS_MADE'] is False
    l=Ledger(dest/'run.sqlite')
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0
    assert l.spent_micro_usd()==3779550
    l.close()

def test_authorize_budget_extension_increases_cap_without_rewriting_calls(tmp_path):
    c=Contexts();src=write_source(tmp_path/'src',c,rounds=(0,1,2))
    dest=tmp_path/'dst'
    derive_complete_rounds(src,dest,2,c)
    l=Ledger(dest/'run.sqlite')
    before_calls=l.export_calls()
    before_status=l.get('status')
    before_cards=l.db.execute('SELECT count(*) FROM cards').fetchone()[0]
    l.close()
    with pytest.raises(ContractError,match='offline'):
        main(['authorize-budget-extension','--provider','openai','--allow-real-llm','--budget-usd','1','--run-dir',str(dest),'--actor','owner','--reason','go','--new-cap-usd','17.100000'])
    with pytest.raises(ContractError,match='actor and reason required'):
        authorize_budget_extension(dest,'','more budget','17.100000')
    with pytest.raises(ContractError,match='new cap must exceed old cap'):
        authorize_budget_extension(dest,'owner','same','7.117536')
    with pytest.raises(ContractError,match='new cap must exceed old cap'):
        authorize_budget_extension(dest,'owner','down','6.000000')
    with pytest.raises(ContractError,match='owner-authorized campaign total'):
        authorize_budget_extension(dest,'owner','above authorized absolute ceiling','17.117536')
    with pytest.raises(ContractError,match='budget must be finite'):
        authorize_budget_extension(dest,'owner','too high','31')
    with pytest.raises(ContractError,match='new cap required'):
        authorize_budget_extension(dest,'owner','missing',None)
    report=authorize_budget_extension(dest,'owner','set absolute authorized campaign total to USD 17.10','17.100000')
    assert report['STATUS']=='BUDGET_EXTENSION_AUTHORIZED'
    assert report['OLD_CAP_MICRO_USD']==7117536
    assert report['NEW_CAP_MICRO_USD']==OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD==17_100_000
    assert report['SPENT_MICRO_USD']==3779550
    assert report['REMAINING_MICRO_USD']==13320450
    assert report['REAL_LLM_CALLS_MADE'] is False
    l=Ledger(dest/'run.sqlite')
    assert l.get('config')['CAP_MICRO_USD']==17_100_000
    assert l.get('status')==before_status==DERIVED_STATUS
    assert l.export_calls()==before_calls
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==before_cards==0
    assert l.spent_micro_usd()==3779550
    kinds=[k for k, in l.db.execute("SELECT kind FROM events ORDER BY n")]
    assert 'BUDGET_EXTENSION_AUTHORIZED' in kinds
    payload=json.loads(l.db.execute("SELECT payload FROM events WHERE kind='BUDGET_EXTENSION_AUTHORIZED'").fetchone()[0])
    assert payload['OLD_CAP_MICRO_USD']==7117536
    assert payload['NEW_CAP_MICRO_USD']==17_100_000
    assert payload['ACTOR']=='owner'
    assert payload['REASON']=='set absolute authorized campaign total to USD 17.10'
    assert payload['TIME']
    l.close()
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch=pytest.MonkeyPatch()
    monkeypatch.setattr(HTTPS,'__call__',lambda *a,**k:pytest.fail('HTTP reached'))
    try:
        with pytest.raises(ContractError,match='offline'):
            main(['remaining-budget-preflight','--provider','openai','--allow-real-llm','--budget-usd','17.100000','--run-dir',str(dest)])
        pre=remaining_campaign_budget_preflight(dest)
    finally:
        monkeypatch.undo()
    assert pre['STATUS']=='REMAINING_BUDGET_PREFLIGHT'
    assert pre['CAP_MICRO_USD']==17_100_000
    assert pre['SPENT_MICRO_USD']==3779550
    assert pre['REMAINING_AUTHORIZED_MICRO_USD']==13320450
    assert pre['WORST_CASE_REMAINING_MICRO_USD']<=13320450
    assert pre['FITS_AUTHORIZED_REMAINING'] is True
    assert pre['REAL_LLM_CALLS_MADE'] is False
    assert pre['IMPORTED_GENERATION_ROUNDS']==['generation:0','generation:1','generation:2']
    assert pre['REMAINING_GENERATION_ROUNDS']==['generation:3']
    names=[row['STAGE'] for row in pre['STAGES']]
    assert names[0]=='generation:3'
    assert any(s.startswith('NOVELTY_CRITIC') for s in names)
    assert any(s.startswith('RED_TEAM') for s in names)
    with pytest.raises(ContractError,match='archived paid run'):
        main(['authorize-budget-extension','--run-dir','artifacts/generator_v0/first-shadow-v6','--actor','owner','--reason','no','--new-cap-usd','17.100000'])
    with pytest.raises(ContractError,match='archived paid run'):
        main(['remaining-budget-preflight','--run-dir','artifacts/generator_v0/first-shadow-v6'])

def test_live_openai_run_refuses_cap_above_owner_authorized_total(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','present')
    from scripts.research.generator_v0.openai_provider import HTTPS
    monkeypatch.setattr(HTTPS,'__call__',lambda *a,**k:pytest.fail('HTTP reached'))
    with pytest.raises(ContractError,match='owner-authorized total'):
        main(['run','--provider','openai','--allow-real-llm','--budget-usd','17.117536','--run-dir',str(tmp_path/'x')])
    with pytest.raises(ContractError,match='owner-authorized total'):
        main(['resume','--provider','openai','--allow-real-llm','--budget-usd','30','--run-dir',str(tmp_path/'y')])
    with pytest.raises(ContractError,match='run not found'):
        main(['resume','--provider','openai','--allow-real-llm','--budget-usd','17.100000','--run-dir',str(tmp_path/'missing')])
    main(['preflight','--provider','openai','--allow-real-llm','--budget-usd','30'])
