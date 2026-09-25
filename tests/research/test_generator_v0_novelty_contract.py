"""B1: the novelty (and generator) producer/consumer contract is one keyed shape.

The prompt, the strict provider schema sent with the request, the parser and
the offline fixtures all use objects keyed by exact IDs. A list form is a
contract error; omissions fail the schema; duplicate keys cannot be decoded."""
import copy
import json
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical
from scripts.research.generator_v0.roles import Roles,NOVELTY_PROMPT,RoleContractError,RELATIONS,BATCH_RELATIONS
from scripts.research.generator_v0.output_schemas import role_schema,openai_response_format
from scripts.research.generator_v0.schema import parse_json,validate_instance,normalize_role_output
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture,slot_plan,MockResponder
from scripts.research.generator_v0.runner import parse_round,_intake_round
from scripts.research.generator_v0 import contract

C=Contexts()
CARDS=[fixture(s,C) for s in slot_plan(40)]
CARD=CARDS[7]
LEAF=sorted(k for k,r in C.rows.items() if r['STATE']!='PARTIAL_OR_MIXED')
OTHERS=sorted(x['CANDIDATE_ID'] for x in CARDS if x is not CARD)

def ctx():return Roles(C,None).request('NOVELTY_CRITIC',CARD,CARDS)
def schema():return role_schema('NOVELTY_CRITIC',C,provider=True,request={'context':ctx()})
def keyed():
    return {'PRIOR_RELATIONS':{k:'ORTHOGONAL_MECHANISM' for k in LEAF},'BATCH_RELATIONS':{k:'ORTHOGONAL_MECHANISM' for k in OTHERS},
            'JUDGMENTS':{'NOVELTY':1,'MECHANISM_DISTANCE':2,'NON_RESCUE':3}}

def novelty_with(tmp_path,text):
    tmp_path.mkdir(parents=True,exist_ok=True)
    l=Ledger(tmp_path/'n.sqlite',{'RUN_ID':'n'})
    return Roles(C,Caller(C,l,MockProvider(lambda r:text))).novelty(CARD,CARDS)

def test_prompt_requires_keyed_objects_not_lists():
    p=NOVELTY_PROMPT
    assert 'PRIOR_RELATIONS is an object, not a list' in p and 'BATCH_RELATIONS is an object, not a list' in p
    assert 'is a list' not in p and '{SIGNATURE_ID, RELATION}' not in p and '{CANDIDATE_ID, RELATION}' not in p
    for r in RELATIONS:assert r in p
    assert 'copy them exactly' in p

def test_schema_keys_are_exactly_the_required_ids():
    s=schema()['properties']
    assert sorted(s['PRIOR_RELATIONS']['properties'])==sorted(s['PRIOR_RELATIONS']['required'])==LEAF
    assert sorted(s['BATCH_RELATIONS']['properties'])==sorted(s['BATCH_RELATIONS']['required'])==OTHERS
    assert CARD['CANDIDATE_ID'] not in s['BATCH_RELATIONS']['properties']
    assert s['PRIOR_RELATIONS']['additionalProperties'] is False and s['BATCH_RELATIONS']['additionalProperties'] is False
    assert all(v['enum']==sorted(RELATIONS) for v in s['PRIOR_RELATIONS']['properties'].values())
    assert all(v['enum']==sorted(BATCH_RELATIONS) for v in s['BATCH_RELATIONS']['properties'].values())
    # The exact schema is what goes on the wire.
    assert openai_response_format('NOVELTY_CRITIC',C,{'context':ctx()})['json_schema']['schema']==schema()

def test_prompt_key_description_matches_the_schema():
    """The prompt's rule for which keys exist yields exactly the schema's keys."""
    c=ctx()
    rows=c['GOVERNANCE_REGION_AUTHORITY_V0']['ROWS']
    from_prompt_prior=sorted([r['SIGNATURE_ID'] for r in rows if r['STATE']!='PARTIAL_OR_MIXED']+[s['SIGNATURE_ID'] for r in rows if r['STATE']=='PARTIAL_OR_MIXED' for s in r['SUB_SIGNATURES']])
    from_prompt_batch=sorted(r['CANDIDATE_ID'] for r in c['CURRENT_BATCH_SIGNATURES'] if r['CANDIDATE_ID']!=c['CANDIDATE']['CANDIDATE_ID'])
    s=schema()['properties']
    assert from_prompt_prior==sorted(s['PRIOR_RELATIONS']['required'])
    assert from_prompt_batch==sorted(s['BATCH_RELATIONS']['required'])

def test_parser_accepts_exactly_what_the_schema_accepts(tmp_path):
    good=keyed();validate_instance(good,schema())
    n=novelty_with(tmp_path,canonical(good))
    assert [r['SIGNATURE_ID'] for r in n['PRIOR_RELATIONS']]==LEAF and sorted(r['CANDIDATE_ID'] for r in n['BATCH_RELATIONS'])==OTHERS
    bad=[]
    omit_prior=keyed();omit_prior['PRIOR_RELATIONS'].pop(LEAF[0]);bad.append(omit_prior)
    omit_batch=keyed();omit_batch['BATCH_RELATIONS'].pop(OTHERS[-1]);bad.append(omit_batch)
    extra=keyed();extra['BATCH_RELATIONS'][CARD['CANDIDATE_ID']]='ORTHOGONAL_MECHANISM';bad.append(extra)
    wrong=keyed();wrong['BATCH_RELATIONS'][OTHERS[0]]='RESOLVES_BLOCKER';bad.append(wrong)
    as_list=keyed();as_list['PRIOR_RELATIONS']=[{'SIGNATURE_ID':k,'RELATION':'ORTHOGONAL_MECHANISM'} for k in LEAF];bad.append(as_list)
    as_list2=keyed();as_list2['BATCH_RELATIONS']=[{'CANDIDATE_ID':k,'RELATION':'ORTHOGONAL_MECHANISM'} for k in OTHERS];bad.append(as_list2)
    for i,payload in enumerate(bad):
        with pytest.raises(ContractError):validate_instance(payload,schema())
        with pytest.raises(RoleContractError):novelty_with(tmp_path/str(i),canonical(payload))

def test_duplicate_ids_cannot_be_decoded(tmp_path):
    text=canonical(keyed()).replace('"PRIOR_RELATIONS":{','"PRIOR_RELATIONS":{"'+LEAF[0]+'":"EXACT_DUPLICATE",',1)
    with pytest.raises(ContractError,match='duplicate'):parse_json(text)
    with pytest.raises(RoleContractError):novelty_with(tmp_path,text)

def test_normalizer_refuses_list_forms():
    with pytest.raises(ContractError):normalize_role_output('NOVELTY_CRITIC',{**keyed(),'PRIOR_RELATIONS':[]})
    with pytest.raises(ContractError):normalize_role_output('GENERATOR',{'CANDIDATES':[CARD]})

def test_mock_fixtures_emit_the_live_keyed_encoding():
    r=MockResponder(C)
    nov=json.loads(r({'role':'NOVELTY_CRITIC','context':ctx(),'parameters':{}}))
    validate_instance(nov,schema())
    slots=slot_plan(40)[:10]
    gen=json.loads(r({'role':'GENERATOR','context':C.generator(),'parameters':{'slots':slots}}))
    validate_instance(gen,role_schema('GENERATOR',C,provider=True,request={'parameters':{'slots':slots}}))

def test_generator_round_is_consumed_keyed_and_checked_per_slot(tmp_path):
    slots=slot_plan(40)[:10]
    raw=MockResponder(C)({'role':'GENERATOR','context':C.generator(),'parameters':{'slots':slots}})
    assert parse_round(canonical({'CANDIDATES':list(json.loads(raw)['CANDIDATES'].values())})) is None
    keyedcards=parse_round(raw);assert set(keyedcards)=={s['CANDIDATE_ID'] for s in slots}
    bad=copy.deepcopy(keyedcards)
    bad['C003']['SEARCH_SURFACE']['PARAMETERS']={'horizon_hours':[6]}         # application form: not the provider encoding
    bad['C004']=copy.deepcopy(bad['C005'])                                     # wrong card under a slot key
    del bad['C006']                                                            # omission
    l=Ledger(tmp_path/'g.sqlite',{'RUN_ID':'g'})
    _intake_round(C,l,0,slots,contract.CONTRACT_ID,'k',bad,[])
    st={x['CANDIDATE_ID']:(x['STATE'],[r['RULE'] for r in x['REASONS']]) for x in l.candidates()}
    assert st['C003']==('HARD_FAIL',['PROVIDER_SCHEMA']) and st['C004']==('HARD_FAIL',['PROVIDER_SCHEMA'])
    assert st['C006']==('HARD_FAIL',['SLOT_IDENTITY'])
    assert sum(v[0]=='VALID' for v in st.values())==7
    l.close()

def test_start_after_end_legal_range_fails_at_intake(tmp_path):
    """The strict-schema regex cannot express month ordering (no lookaround or
    backreferences in the subset), so ordering is enforced at the first
    deterministic layer after decoding: per-slot intake, before any critic call."""
    slots=slot_plan(40)[:10]
    raw=json.loads(MockResponder(C)({'role':'GENERATOR','context':C.generator(),'parameters':{'slots':slots}}))
    raw['CANDIDATES']['C001']['DATA_REQUIRED'][0]['LEGAL_RANGE']='2023-06..2021-01'
    validate_instance(raw['CANDIDATES']['C001'],__import__('scripts.research.generator_v0.schema',fromlist=['output_schema']).output_schema(C,provider=True,slot=slots[0]))
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'r'})
    _intake_round(C,l,0,slots,contract.CONTRACT_ID,'k',parse_round(canonical(raw)),[])
    st={x['CANDIDATE_ID']:(x['STATE'],[r['RULE'] for r in x['REASONS']]) for x in l.candidates()}
    assert st['C001']==('HARD_FAIL',['LEGAL_RANGE_GRAMMAR'])
    l.close()
