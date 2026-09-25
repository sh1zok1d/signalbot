"""GENERATOR_CONTRACT_V02 gate: rule table, decoding schemas, legacy isolation,
property and fuzz tests. Offline; no provider is called."""
import copy
import hashlib
import json
import random
import re
import sqlite3
from pathlib import Path
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0 import contract,legacy_v01,legacy_v01_schema
from scripts.research.generator_v0.contract import RULES,RULE_IDS,CHECKS,LEGAL_RANGE_PATTERN,parse_legal_range,card_violations,generator_prompt
from scripts.research.generator_v0.output_schemas import role_schema,strict_subset_violations,assert_strict_subset,generator_schema_digest
from scripts.research.generator_v0.schema import normalize_role_output,normalize_search_surface,validate_card,validate_instance
from scripts.research.generator_v0.mock import fixture,slot_plan
from scripts.research.generator_v0.roles import Roles
from scripts.research.generator_v0.runner import GENERATOR_PROMPT
from scripts.research.generator_v0_gate.corpus import base_ready,SLOT

REPO=Path(__file__).resolve().parents[2]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'
V7_SHA='e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457'

# ---------------------------------------------------------------- rule table

def test_every_rule_has_one_check_and_one_prompt_line():
    assert len(RULE_IDS)==len(set(RULE_IDS))
    assert set(RULE_IDS)==set(CHECKS)
    prompt=generator_prompt()
    for rule in RULES:
        assert rule['ENFORCEMENT'] in ('DECODING','VALIDATOR')
        assert '['+rule['ID']+'] '+rule['TEXT'] in prompt
    assert GENERATOR_PROMPT==prompt

def test_prompt_states_the_rules_that_used_to_be_hidden():
    p=generator_prompt()
    for needle in ('Never refer to any year after 2024, in any form','YYYY-MM..YYYY-MM','per snapshot','at least the product','names at least one exact missing observable',
                   'within three words of signal','wall-clock recency words','explicit end no later than 2024-12','NEAREST_TESTED_MECHANISM is exactly one prior signature ID'):
        assert needle in p,needle

def test_prompt_passes_generator_context_scanner():
    c=Contexts();c.validate('GENERATOR',c.generator(),GENERATOR_PROMPT)

def test_decoding_rules_are_in_the_provider_schema():
    c=Contexts();slots=slot_plan(40)[:10]
    s=role_schema('GENERATOR',c,provider=True,request={'parameters':{'slots':slots}})
    cands=s['properties']['CANDIDATES']
    assert cands['required']==[x['CANDIDATE_ID'] for x in slots] and cands['additionalProperties'] is False
    for slot in slots:
        card=cands['properties'][slot['CANDIDATE_ID']]['properties']
        assert card['CANDIDATE_ID']['enum']==[slot['CANDIDATE_ID']]
        assert card['MECHANISM_FAMILY']['enum']==[slot['MECHANISM_FAMILY']]
        assert card['INFORMATION_SOURCE']['enum']==[slot['INFORMATION_SOURCE']]
        assert card['PROTECTED_DATA_REQUIREMENT']['enum']==[False]
        assert card['DATA_REQUIRED']['items']['properties']['LEGAL_RANGE']['pattern']==LEGAL_RANGE_PATTERN
        assert set(card['DATA_REQUIRED']['items']['properties']['STATUS']['enum'])==set(c.design['DATA_STATUS_TAXONOMY'])
        assert set(card['NEAREST_TESTED_MECHANISM']['enum'])==set(contract.nearest_mechanism_ids(c))

# ---------------------------------------------------------- strict subset

def _all_provider_schemas(c):
    out=[]
    for size in (25,40,50):
        plan=slot_plan(size)
        for i in range(0,size,10):out.append(role_schema('GENERATOR',c,provider=True,request={'parameters':{'slots':plan[i:i+10]}}))
    cards=[fixture(s,c) for s in slot_plan(40)]
    out.append(role_schema('NOVELTY_CRITIC',c,provider=True,request={'context':Roles(c,None).request('NOVELTY_CRITIC',cards[0],cards)}))
    for role in ('FEASIBILITY_CRITIC','RED_TEAM','SELECTOR'):out.append(role_schema(role,c,provider=True))
    return out

def test_every_provider_schema_is_inside_the_strict_subset():
    for schema in _all_provider_schemas(Contexts()):
        assert strict_subset_violations(schema)==[]

@pytest.mark.parametrize('bad,needle',[
    ({'type':'string','pattern':'^(?=x).*$'},'lookaround'),
    ({'type':'string','pattern':'^\\d+$'},'shorthand'),
    ({'type':'object','properties':{'a':{'type':'string'}},'required':[],'additionalProperties':False},'every property must be required'),
    ({'type':'object','properties':{},'required':[],'additionalProperties':True},'additionalProperties must be false'),
    ({'type':'string','format':'date'},'unsupported keywords'),
    ({'type':'array'},'array items required'),
    ({'type':'string','enum':[]},'empty enum'),
])
def test_strict_subset_checker_rejects_unsupported_constructs(bad,needle):
    assert any(needle in v for v in strict_subset_violations(bad))
    with pytest.raises(ContractError):assert_strict_subset(bad)

# ------------------------------------------------- LEGAL_RANGE properties

def _random_range(rng):
    y=lambda:str(rng.choice([rng.randint(1890,2031),2024,2025,2026,1900,1899,2019,2020]))
    m=lambda:rng.choice(['00','01','06','09','10','12','13','1','001'])
    forms=[lambda:y()+'-'+m()+'..'+y()+'-'+m(),lambda:'pre-'+y(),lambda:'per snapshot',lambda:y()+'..'+y(),lambda:y()+'-'+m()+' to '+y()+'-'+m(),
           lambda:' '+y()+'-'+m()+'..'+y()+'-'+m(),lambda:y()+'-'+m()+'..'+y()+'-'+m()+';',lambda:'PER SNAPSHOT',lambda:'pre '+y()]
    return rng.choice(forms)()

def test_property_pattern_and_parser_agree_and_never_reach_protected():
    rng=random.Random(7);pattern=re.compile(LEGAL_RANGE_PATTERN);seen=0
    for _ in range(20000):
        s=_random_range(rng);parsed=parse_legal_range(s);matched=pattern.fullmatch(s) is not None
        if parsed is not None:
            seen+=1;assert matched
            if parsed['KIND']=='BOUNDED':
                assert parsed['END']<=(2024,12)
                assert parsed['START'] is None or parsed['START']<=parsed['END']
        elif matched:
            a,b=s.split('..');assert (int(a[:4]),int(a[5:]))>(int(b[:4]),int(b[5:]))  # only reversed ranges match but do not parse
    assert seen>1000

def test_property_no_expressible_range_reaches_the_protected_period():
    for y1 in range(1900,2027):
        for y2 in range(y1,2027):
            for m2 in ('01','12'):
                s='%d-01..%d-%s'%(y1,y2,m2);p=parse_legal_range(s)
                assert (p is not None)==(y2<=2024),s
    for y in range(1900,2030):
        assert (parse_legal_range('pre-%d'%y) is not None)==(y<=2024)

# ------------------------------------------------------------- fuzzing

PROTECTED_INSERTS=('2025','2026','FY25',"'26",'twenty twenty-five','2025-2026','in 2026')
OPEN_INSERTS=('through today','until present','post-2024','after 2024','2024 onwards','2024+','open-ended','2024-present','year after 2024')

def _fields(card):
    return [k for k,v in card.items() if isinstance(v,str) and k not in ('CANDIDATE_ID','MECHANISM_FAMILY','INFORMATION_SOURCE','NEAREST_TESTED_MECHANISM','DATA_STATUS','DATA_GAP_CLASS')]

def test_fuzz_protected_or_open_ended_text_is_never_admitted():
    c=Contexts();rng=random.Random(11);base=base_ready();checked=0
    for _ in range(1500):
        x=copy.deepcopy(base);field=rng.choice(_fields(x)+['DATA_REQUIRED.OBSERVABLE','SEARCH_KEY'])
        insert=rng.choice(PROTECTED_INSERTS+OPEN_INSERTS)
        if field=='DATA_REQUIRED.OBSERVABLE':x['DATA_REQUIRED'][0]['OBSERVABLE']+=' '+insert
        elif field=='SEARCH_KEY':x['SEARCH_SURFACE']['PARAMETERS']['w '+insert]=[1];x['SEARCH_SURFACE']['MAX_VARIANTS']=2
        else:
            text=x[field];pos=rng.randint(0,len(text));x[field]=text[:pos]+' '+insert+' '+text[pos:]
        v=card_violations(x,c,SLOT)
        assert v,('admitted',field,insert)
        assert {r['RULE'] for r in v}&contract.SAFETY_RULES
        checked+=1
    assert checked==1500

def test_fuzz_structural_mutations_never_crash_and_are_quarantined():
    """Oracle independent of contract.py: the application JSON schema. Anything it
    rejects must be quarantined; nothing may raise."""
    from scripts.research.generator_v0.schema import output_schema
    c=Contexts();rng=random.Random(13);base=base_ready();app=output_schema(c,provider=False);rejected=0
    values=[None,0,-1,1.5,'',' ',[],{},True,'x'*13000,{'a':1},['a'],2025]
    for _ in range(3000):
        x=copy.deepcopy(base);op=rng.randrange(5);key=rng.choice(sorted(x))
        if op==0:x.pop(key)
        elif op==1:x[key]=rng.choice(values)
        elif op==2:x['EXTRA_'+str(rng.randrange(9))]='value'
        elif op==3:x['DATA_REQUIRED']=[rng.choice(values)]
        else:x['SEARCH_SURFACE']={'PARAMETERS':{rng.choice(['a','','b']):[rng.choice(values)]},'MAX_VARIANTS':rng.choice(values)}
        v=card_violations(x,c,SLOT)
        assert isinstance(v,list)
        try:validate_instance(x,app);schema_ok=True
        except ContractError:schema_ok=False
        if not schema_ok:
            rejected+=1;assert v,(op,key,x.get(key))
    assert rejected>1000

def test_card_violations_never_raises_on_arbitrary_json():
    c=Contexts();rng=random.Random(17)
    atoms=[None,0,'',[],{},'2025',{'DATA_REQUIRED':'x'},[{'LEGAL_RANGE':1}]]
    for _ in range(500):
        x={k:rng.choice(atoms) for k in rng.sample(sorted(base_ready()),rng.randint(0,27))}
        assert card_violations(x,c,SLOT)
    assert card_violations('not a card',c,SLOT)[0]['RULE']=='SCHEMA_FIELDS'

# ------------------------------------------------------ round-trip tests

def test_generator_provider_encoding_round_trips_and_is_schema_valid():
    c=Contexts();slots=slot_plan(40)[10:20];cards=[fixture(s,c) for s in slots]
    enc={'CANDIDATES':{x['CANDIDATE_ID']:{**x,'SEARCH_SURFACE':{'MAX_VARIANTS':x['SEARCH_SURFACE']['MAX_VARIANTS'],'PARAMETERS':[{'NAME':k,'VALUES':v} for k,v in x['SEARCH_SURFACE']['PARAMETERS'].items()]}} for x in cards}}
    validate_instance(enc,role_schema('GENERATOR',c,provider=True,request={'parameters':{'slots':slots}}))
    back=normalize_role_output('GENERATOR',json.loads(canonical(enc)))
    assert back=={'CANDIDATES':{x['CANDIDATE_ID']:x for x in cards}}
    with pytest.raises(ContractError):normalize_role_output('GENERATOR',{'CANDIDATES':cards})

def test_novelty_keyed_encoding_round_trips():
    c=Contexts();cards=[fixture(s,c) for s in slot_plan(40)]
    ctx=Roles(c,None).request('NOVELTY_CRITIC',cards[3],cards)
    leaf=sorted(k for k,r in c.rows.items() if r['STATE']!='PARTIAL_OR_MIXED')
    enc={'PRIOR_RELATIONS':{k:'ORTHOGONAL_MECHANISM' for k in leaf},'BATCH_RELATIONS':{x['CANDIDATE_ID']:'ORTHOGONAL_MECHANISM' for x in cards if x is not cards[3]},'JUDGMENTS':{'NOVELTY':1,'MECHANISM_DISTANCE':2,'NON_RESCUE':3}}
    validate_instance(enc,role_schema('NOVELTY_CRITIC',c,provider=True,request={'context':ctx}))
    missing=copy.deepcopy(enc);missing['BATCH_RELATIONS'].pop(cards[0]['CANDIDATE_ID'])
    with pytest.raises(ContractError):validate_instance(missing,role_schema('NOVELTY_CRITIC',c,provider=True,request={'context':ctx}))
    back=normalize_role_output('NOVELTY_CRITIC',enc)
    assert [r['SIGNATURE_ID'] for r in back['PRIOR_RELATIONS']]==leaf
    assert {r['CANDIDATE_ID'] for r in back['BATCH_RELATIONS']}=={x['CANDIDATE_ID'] for x in cards}-{cards[3]['CANDIDATE_ID']}

def test_search_surface_encoding_rejects_duplicates():
    with pytest.raises(ContractError):normalize_search_surface({'MAX_VARIANTS':1,'PARAMETERS':[{'NAME':'a','VALUES':[1]},{'NAME':'a','VALUES':[2]}]})

# ------------------------------------------------ legacy isolation (option A)

def test_grandfather_manifest_is_recomputable_from_the_sealed_v7_journal(tmp_path):
    import shutil
    assert hashlib.sha256(V7.read_bytes()).hexdigest()==V7_SHA
    copy_=tmp_path/'run.sqlite';shutil.copy(V7,copy_)
    rebuilt=legacy_v01.build_manifest(copy_,Contexts())
    committed=json.loads((REPO/legacy_v01.MANIFEST).read_text(encoding='utf-8'))
    assert rebuilt['CALLS']==committed['CALLS'] and rebuilt['EXCLUDED_CALLS']==committed['EXCLUDED_CALLS']
    assert committed['SOURCE_JOURNAL_SHA256']==V7_SHA
    assert [r['SLOT'] for r in committed['CALLS']]==['generation:0','generation:1','generation:2']
    assert [r['SLOT'] for r in committed['EXCLUDED_CALLS']]==['generation:3']
    assert sum(len(r['CARD_DIGESTS']) for r in committed['CALLS'])==30
    assert hashlib.sha256(V7.read_bytes()).hexdigest()==V7_SHA

def _v7_cards():
    db=sqlite3.connect('file:{}?mode=ro&immutable=1'.format(V7.as_posix()),uri=True)
    try:
        return {json.loads(r)['slot']:(k,json.loads(json.loads(resp)['raw'])['CANDIDATES']) for k,r,resp in db.execute('SELECT key,request,response FROM calls')}
    finally:db.close()

def test_legacy_admission_requires_listed_key_and_exact_digest():
    c=Contexts();rows=_v7_cards()
    key0,cards0=rows['generation:0'];key3,cards3=rows['generation:3']
    for card in cards0:legacy_v01.admit_card(card,c,key0)
    with pytest.raises(ContractError,match='not grandfathered'):legacy_v01.admit_card(cards0[0],c,key3)
    tampered=copy.deepcopy(cards0[0]);tampered['NAME']+=' '
    with pytest.raises(ContractError,match='grandfathered digest'):legacy_v01.admit_card(tampered,c,key0)
    with pytest.raises(ContractError,match='grandfathered digest'):legacy_v01.admit_card(cards0[1],c,key0) if cards0[1]['CANDIDATE_ID']==cards0[0]['CANDIDATE_ID'] else legacy_v01.admit_card(dict(cards0[1],CANDIDATE_ID=cards0[0]['CANDIDATE_ID']),c,key0)

def test_discarded_v7_generation3_is_judged_only_by_v02():
    c=Contexts();key3,cards3=_v7_cards()['generation:3']
    assert not legacy_v01.is_grandfathered_call(key3)
    verdicts={x['CANDIDATE_ID']:bool(card_violations(x,c)) for x in cards3}
    assert sum(verdicts.values())>=9  # the contract was not widened to admit the observed output

def test_legacy_grammar_is_unreachable_for_new_cards():
    """Inspected-output wrappers from the legacy grammar are not V02 LEGAL_RANGE forms."""
    c=Contexts();x=base_ready()
    x.update(DATA_STATUS='DATA_BLOCKED_COST',MISSING_OBSERVABLES=['x'],DATA_GAP_CLASS='COST')
    for wrapper in ('Required historical window: 2020-01..2024-12; coverage unverified and not catalogued',
                    'Proposed archive limited to 2020-01..2024-12; no catalog-authorized options coverage is claimed.'):
        assert legacy_v01_schema.classify_legal_range(wrapper)['KIND']=='BOUNDED'
        x['DATA_REQUIRED']=[{'DATASET':'GATE_UNKNOWN','OBSERVABLE':'x','STATUS':'DATA_BLOCKED_COST','LEGAL_RANGE':wrapper}]
        assert 'LEGAL_RANGE_GRAMMAR' in {v['RULE'] for v in card_violations(x,c,SLOT)}
        with pytest.raises(ContractError):validate_card(x,c)

def test_legacy_schema_digest_matches_the_v5_v7_configs():
    committed=json.loads((REPO/legacy_v01.MANIFEST).read_text(encoding='utf-8'))
    assert legacy_v01.schema_digest(Contexts())==committed['STRUCTURED_OUTPUT_SCHEMA_DIGEST']=='0765ca969dde317b247e677633886f2c685b07ee516a6d42d092862e9d28b18e'
    assert hashlib.sha256(legacy_v01.PROMPT.encode()).hexdigest()==committed['PROMPT_SHA256']
    assert generator_schema_digest(Contexts())!=committed['STRUCTURED_OUTPUT_SCHEMA_DIGEST']
