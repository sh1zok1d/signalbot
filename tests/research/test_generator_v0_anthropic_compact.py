"""Anthropic compact GENERATOR projection: one shared card schema in an array,
bound to slots only by CANDIDATE_ID and checked against the exact slot schema
and V02 rules at intake. Offline only: fake transports, dummy keys, no network."""
import copy
import json
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError,canonical,digest
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture,slot_plan,SOURCE_CLASSES
from scripts.research.generator_v0.schema import encode_provider_card,output_schema,validate_instance,LEGAL_RANGE_PATTERN
from scripts.research.generator_v0.output_schemas import (role_schema,anthropic_projection,anthropic_output_schema,
    anthropic_generator_compact_schema,anthropic_subset_violations,ANTHROPIC_GENERATOR_WIRE_FORMAT,KEYED_GENERATOR_WIRE_FORMAT,
    ANTHROPIC_COMPACT_RELAXED_CONSTRAINTS)
from scripts.research.generator_v0.provider import Caller
from scripts.research.generator_v0.routed_provider import offline_routed_provider
from scripts.research.generator_v0.runner import (GENERATOR_PROMPT,generator_request_parameters,generator_identity,parse_round,
    round_cards,_intake_round,CompactRound,MIN_VALID_CANDIDATES)
from scripts.research.generator_v0 import contract,routing
from scripts.research.generator_v0_gate.noisy import NoisyTransport,routed_provider_for,run

C=Contexts()
PLAN=slot_plan(40)
SLOTS=PLAN[:10]
FAILED_SMOKE_KEY='767fd9e133e63a6e212277326252679724c3863d9d649e909c0eb1dc2bdf95a0'
CRITICS=('NOVELTY_CRITIC','FEASIBILITY_CRITIC','RED_TEAM')

def cards(slots=SLOTS):
    return [encode_provider_card(fixture(s,C)) for s in slots]

def keyed(slots=SLOTS):
    return {c['CANDIDATE_ID']:c for c in cards(slots)}

def intake(items,slots=SLOTS,round_n=0):
    """(decisions by slot ID, events) for a round through the production intake."""
    l=Ledger(':memory:',{'RUN_ID':'compact'})
    admitted=_intake_round(C,l,round_n,slots,contract.CONTRACT_ID,'key',items,[])
    rows={r['CANDIDATE_ID']:r for r in l.candidates()}
    events=[(k,json.loads(p)) for k,p in l.db.execute('SELECT kind,payload FROM events ORDER BY n')]
    return rows,events,admitted

def compact(items):
    return parse_round(canonical({'CANDIDATES':items}),contract.CONTRACT_ID,ANTHROPIC_GENERATOR_WIRE_FORMAT)

def decisions(rows):
    return {k:(r['STATE'],r['CARD'],r['REASONS']) for k,r in rows.items()}

def gen_request(caller,slots=SLOTS,n=0):
    return caller.request('GENERATOR',C.generator(),GENERATOR_PROMPT,generator_request_parameters(slots),'generation:'+str(n),0,generator_identity(C,slots))

def caller():
    return Caller(C,Ledger(':memory:',{'RUN_ID':'k'}),offline_routed_provider(C),1,True)

def rules(row):return [r['RULE'] for r in row['REASONS']]

# ------------------------------------------------------------- schema shape

def test_compact_schema_is_one_shared_card_with_legal_range_once():
    req=gen_request(caller())
    body=offline_routed_provider(C).adapters['ANTHROPIC'].payload(req)
    s=body['output_config']['format']['schema']
    text=canonical(s)
    assert text.count(json.dumps(LEGAL_RANGE_PATTERN)[1:-1])==1
    items=s['properties']['CANDIDATES']
    assert set(s['properties'])=={'CANDIDATES'} and s['additionalProperties'] is False
    assert items['type']=='array' and items['minItems']==1 and 'maxItems' not in items
    card=items['items']
    assert card['additionalProperties'] is False and sorted(card['required'])==sorted(card['properties'])
    assert sorted(card['properties'])==sorted(output_schema(C,provider=True)['properties'])
    assert card['properties']['CANDIDATE_ID']=={'type':'string','enum':[x['CANDIDATE_ID'] for x in SLOTS]}
    assert card['properties']['MECHANISM_FAMILY']['enum']==sorted(set(C.families)|{'NEW_FAMILY_PROPOSAL'})
    assert card['properties']['INFORMATION_SOURCE']['enum']==sorted(SOURCE_CLASSES)
    assert card['properties']['PROTECTED_DATA_REQUIREMENT']=={'type':'boolean','enum':[False]}
    assert anthropic_subset_violations(s)==[]
    def objects(n):return (n.get('type')=='object')+sum(objects(v) for v in (n.get('properties') or {}).values())+(objects(n['items']) if 'items' in n else 0)
    assert objects(s)==5
    assert text.count('"enum":[false]')==1 and text.count('"enum":[')==7

def test_compact_is_a_projection_of_the_exact_schema_and_every_relaxation_is_listed():
    """Relaxed vs the exact keyed slot schema: exactly the listed constraints."""
    comp=anthropic_generator_compact_schema(C,{'parameters':{'slots':SLOTS}})
    _,removed=anthropic_projection(comp)
    assert sorted({k for _,k,_ in removed})==['maxItems','maximum','minimum']
    assert sorted(p for p,_,_ in removed)==sorted(['#/CANDIDATES/items/DATA_REQUIRED','#/CANDIDATES/items/SEARCH_SURFACE/MAX_VARIANTS','#/CANDIDATES/items/SEARCH_SURFACE/MAX_VARIANTS'])
    exact_card=output_schema(C,provider=True,slot=SLOTS[0])
    diff={k for k in exact_card['properties'] if exact_card['properties'][k]!=comp['properties']['CANDIDATES']['items']['properties'][k]}
    assert diff=={'CANDIDATE_ID','MECHANISM_FAMILY','INFORMATION_SOURCE'}
    assert len(ANTHROPIC_COMPACT_RELAXED_CONSTRAINTS)==6
    listed=' '.join(r['CONSTRAINT'] for r in ANTHROPIC_COMPACT_RELAXED_CONSTRAINTS)
    for word in ('CANDIDATES keyed','CANDIDATE_ID','MECHANISM_FAMILY','INFORMATION_SOURCE','MAX_VARIANTS','maxItems'):assert word in listed

@pytest.mark.parametrize('label,mutate,rule_detail',[
    ('MAX_VARIANTS above 100',lambda c:c['SEARCH_SURFACE'].update(MAX_VARIANTS=101),'integer range'),
    ('MAX_VARIANTS below 1',lambda c:c['SEARCH_SURFACE'].update(MAX_VARIANTS=0),'integer range'),
    ('DATA_REQUIRED over maxItems',lambda c:c.update(DATA_REQUIRED=c['DATA_REQUIRED']*(contract.MAX_DATA_ROWS+1)),'array too long'),
    ('family of another slot',lambda c:c.update(MECHANISM_FAMILY='B'),'string enum'),
    ('source of another slot',lambda c:c.update(INFORMATION_SOURCE='OPTIONS'),'string enum'),
])
def test_relaxed_constraints_decode_under_compact_but_intake_rejects(label,mutate,rule_detail):
    items=cards();mutate(items[0])
    validate_instance({'CANDIDATES':items},anthropic_output_schema('GENERATOR',C,{'parameters':{'slots':SLOTS}}))
    rows,_,admitted=intake(compact(items))
    assert rows['C001']['STATE']=='HARD_FAIL' and rows['C001']['REASONS']==[{'RULE':'PROVIDER_SCHEMA','DETAIL':rule_detail}]
    assert 'C001' not in [a['CANDIDATE_ID'] for a in admitted]
    assert all(rows[s['CANDIDATE_ID']]['STATE']=='VALID' for s in SLOTS[1:])

# ------------------------------------------------------------- identity

def test_wire_format_and_schema_digest_are_in_the_call_key():
    cal=caller();req=gen_request(cal)
    assert req['provider_wire_format']==ANTHROPIC_GENERATOR_WIRE_FORMAT
    assert req['provider_schema_digest']==digest(anthropic_output_schema('GENERATOR',C,req))
    assert digest(req)!=FAILED_SMOKE_KEY
    for n in range(4):assert digest(gen_request(cal,PLAN[n*10:n*10+10],n))!=FAILED_SMOKE_KEY
    assert routing.ROUTES['GENERATOR']['STRUCTURED_OUTPUT']=='ANTHROPIC_OUTPUT_CONFIG_JSON_SCHEMA_COMPACT_CANDIDATE_ARRAY_V1'
    keyed_req={k:v for k,v in req.items() if k not in ('provider_wire_format','provider_schema_digest')}
    assert digest(keyed_req)!=digest(req)

def test_anthropic_payload_refuses_a_request_without_the_matching_projection_identity():
    a=offline_routed_provider(C).adapters['ANTHROPIC'];req=gen_request(caller())
    for bad in ({'provider_wire_format':KEYED_GENERATOR_WIRE_FORMAT},{'provider_schema_digest':'0'*64}):
        with pytest.raises(ContractError):a.payload(dict(req,**bad))
    with pytest.raises(ContractError):a.payload({k:v for k,v in req.items() if k!='provider_wire_format'})

def test_openai_requests_carry_no_anthropic_wire_identity():
    cal=caller()
    f=cal.request('FEASIBILITY_CRITIC',{'CANDIDATE':fixture(SLOTS[0],C)},'p',{'max_output_tokens':1},'x')
    assert 'provider_wire_format' not in f and 'provider_schema_digest' not in f

# ------------------------------------------------------------- equivalence

def test_parse_is_wire_specific():
    raw_keyed=canonical({'CANDIDATES':keyed()});raw_compact=canonical({'CANDIDATES':cards()})
    assert parse_round(raw_keyed,contract.CONTRACT_ID,ANTHROPIC_GENERATOR_WIRE_FORMAT) is None
    assert parse_round(raw_compact) is None and parse_round(raw_compact,contract.CONTRACT_ID,KEYED_GENERATOR_WIRE_FORMAT) is None
    assert isinstance(parse_round(raw_compact,contract.CONTRACT_ID,ANTHROPIC_GENERATOR_WIRE_FORMAT),CompactRound)
    with pytest.raises(ContractError):parse_round(raw_compact,contract.CONTRACT_ID,'SOMETHING_ELSE')
    assert round_cards(raw_keyed)==round_cards(raw_compact,contract.CONTRACT_ID,ANTHROPIC_GENERATOR_WIRE_FORMAT)

@pytest.mark.parametrize('n',range(4))
def test_valid_rounds_decide_identically_under_keyed_and_compact(n):
    slots=PLAN[n*10:n*10+10]
    old=intake(parse_round(canonical({'CANDIDATES':keyed(slots)})),slots,n)
    new=intake(compact(cards(slots)),slots,n)
    rev=intake(compact(list(reversed(cards(slots)))),slots,n)
    assert decisions(old[0])==decisions(new[0])==decisions(rev[0])
    assert old[2]==new[2]==rev[2] and len(new[2])==10 and new[1]==[]

def test_invalid_cards_decide_identically_under_keyed_and_compact():
    """A per-card V02 violation gets the same decision whatever the wire."""
    k=keyed();items=cards()
    for c in (k['C002'],items[1]):c['NO_LOOKAHEAD_RULE']='No 2025/2026 bars are permitted.'
    for c in (k['C005'],items[4]):c['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01 to 2024-12'
    old=intake(parse_round(canonical({'CANDIDATES':k})));new=intake(compact(items))
    assert decisions(old[0])==decisions(new[0]) and old[2]==new[2]
    assert rules(new[0]['C002'])==['NO_PROTECTED_YEARS'] and rules(new[0]['C005'])==['PROVIDER_SCHEMA']

# ------------------------------------------------------------- adversarial

def _set(i,**kw):
    def f(items):items[i].update(kw);return items
    return f

def _row(i,**kw):
    def f(items):items[i]['DATA_REQUIRED'][0].update(kw);return items
    return f

ADVERSARIAL=[
    # label, mutate(items)->items, expected HARD_FAIL {slot: rule/detail}, expected events
    ('nine_cards',lambda x:x[:9],{'C010':'missing card for slot'},{}),
    ('eleven_cards',lambda x:x+[encode_provider_card(fixture(PLAN[10],C))],{},{'EXTRA_GENERATED_CARDS_IGNORED':['C011']}),
    ('duplicate_id',lambda x:x+[dict(copy.deepcopy(x[3]))],{'C004':'duplicate card for slot'},{}),
    ('duplicate_cannot_replace_another_slot',lambda x:[x[0],dict(copy.deepcopy(x[0]))]+x[2:],{'C001':'duplicate card for slot','C002':'missing card for slot'},{}),
    ('unknown_id',_set(4,CANDIDATE_ID='C999'),{'C005':'missing card for slot'},{'EXTRA_GENERATED_CARDS_IGNORED':['C999']}),
    ('card_assigned_to_another_slot',lambda x:[dict(x[1],CANDIDATE_ID='C003') if i==2 else c for i,c in enumerate(x) if i!=1],{'C002':'missing card for slot','C003':'PROVIDER_SCHEMA'},{}),
    ('wrong_family',_set(0,MECHANISM_FAMILY='B'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('wrong_source',_set(0,INFORMATION_SOURCE='OPTIONS'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('protected_true',_set(0,PROTECTED_DATA_REQUIREMENT=True),{'C001':'PROVIDER_SCHEMA'},{}),
    ('malformed_legal_range',_row(0,LEGAL_RANGE='2020-01 to 2024-12'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('protected_year_range',_row(0,LEGAL_RANGE='2020-01..2025-06'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('protected_year_text',_set(0,NO_LOOKAHEAD_RULE='No 2025/2026 bars are permitted.'),{'C001':'NO_PROTECTED_YEARS'},{}),
    ('open_ended_range',_row(0,LEGAL_RANGE='2020-01..'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('open_ended_present',_row(0,LEGAL_RANGE='2020-01..present'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('malformed_candidate_not_object',lambda x:['not a card']+x[1:],{'C001':'missing card for slot'},{'MALFORMED_GENERATED_ITEMS_IGNORED':[0]}),
    ('malformed_candidate_bad_id',lambda x:[dict(x[0],CANDIDATE_ID=['C001'])]+x[1:],{'C001':'missing card for slot'},{'MALFORMED_GENERATED_ITEMS_IGNORED':[0]}),
    ('malformed_candidate_missing_field',lambda x:[{k:v for k,v in x[0].items() if k!='FALSIFIER'}]+x[1:],{'C001':'PROVIDER_SCHEMA'},{}),
    ('unknown_property',_set(0,CONFIDENCE='high'),{'C001':'PROVIDER_SCHEMA'},{}),
    ('reordered',lambda x:x[::-1],{},{}),
]

@pytest.mark.parametrize('label,mutate,expected,events',ADVERSARIAL,ids=[a[0] for a in ADVERSARIAL])
def test_adversarial_compact_rounds(label,mutate,expected,events):
    rows,got_events,admitted=intake(compact(mutate(cards())))
    assert sorted(rows)==[s['CANDIDATE_ID'] for s in SLOTS]                     # one decision per slot, never an unknown ID
    for cid,row in rows.items():
        if cid in expected:
            assert row['STATE']=='HARD_FAIL',cid
            assert expected[cid] in (row['REASONS'][0]['RULE'],row['REASONS'][0]['DETAIL']),row['REASONS']
        else:
            assert (row['STATE'],row['REASONS'])==('VALID',[]),(cid,row['REASONS'])
            assert row['CARD']==fixture(SLOTS[int(cid[1:])-1],C)                  # the slot's own card, never a moved one
    assert [a['CANDIDATE_ID'] for a in admitted]==[s['CANDIDATE_ID'] for s in SLOTS if s['CANDIDATE_ID'] not in expected]
    got={k:(p.get('CANDIDATE_IDS') or p.get('ITEM_INDEXES')) for k,p in got_events}
    assert got==events

def test_a_whole_round_that_is_not_an_array_is_unusable():
    assert compact_raw({'CANDIDATES':keyed()}) is None
    assert compact_raw({'CANDIDATES':cards(),'EXTRA':1}) is None
    assert compact_raw([]) is None

def compact_raw(obj):
    return parse_round(canonical(obj),contract.CONTRACT_ID,ANTHROPIC_GENERATOR_WIRE_FORMAT)

# ------------------------------------------------------------- end to end

def _e2e_mutator(rnd,items):
    ids=[c['CANDIDATE_ID'] for c in items]
    x=[copy.deepcopy(c) for c in items]
    at=lambda cid:ids.index(cid)
    if rnd==0:
        x[at('C001')]['CANDIDATE_ID']='C002'                       # duplicate C002, C001 missing
        x[at('C003')]['CANDIDATE_ID']='C999'                       # unknown ID, C003 missing
        x[at('C004')]['MECHANISM_FAMILY']='E'                      # wrong family
        x.append(encode_provider_card(dict(fixture(PLAN[10],C),NAME='round-0 impostor for C011')))   # next round's ID
    if rnd==1:
        x[at('C012')]['INFORMATION_SOURCE']='ONCHAIN'              # wrong source
        x[at('C013')]['PROTECTED_DATA_REQUIREMENT']=True
        x[at('C014')]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01 to 2024-12'
        x[at('C015')]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2021-01..2026-03'
    if rnd==2:
        x[at('C021')]['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01..'
        x[at('C022')]['CONFIDENCE']='high'                         # unknown property
        x[at('C023')].pop('FALSIFIER')                              # malformed candidate
        x.pop(at('C024'))                                           # 9 cards for 10 slots
        x=['not a card',{'NAME':'no id'}]+x[::-1]                   # malformed items, reordered
    if rnd==3:
        moved=dict(x[at('C031')],CANDIDATE_ID='C032')               # C031's card offered for C032
        x=[moved if c['CANDIDATE_ID']=='C032' else c for c in x if c['CANDIDATE_ID']!='C031']
    return x

E2E_INVALID={'C001','C002','C003','C004','C012','C013','C014','C015','C021','C022','C023','C024','C031','C032'}

@pytest.fixture(scope='module')
def e2e(tmp_path_factory):
    d=tmp_path_factory.mktemp('compact_e2e');l=Ledger(d/'run.sqlite',{'RUN_ID':'compact-e2e','CAP_MICRO_USD':17_100_000})
    t=NoisyTransport(C,{},compact_mutator=_e2e_mutator)
    result=run(C,l,t,routed_provider_for)
    yield result,l,t
    l.close()

def test_e2e_mixed_compact_campaign_reaches_human_review(e2e):
    result,l,t=e2e
    assert 40-len(E2E_INVALID)>=MIN_VALID_CANDIDATES
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert {h['CANDIDATE_ID'] for h in result['HARD_FAILS']}==E2E_INVALID
    assert t.counts[('GENERATOR',0)]==t.counts[('GENERATOR',1)]==t.counts[('GENERATOR',2)]==t.counts[('GENERATOR',3)]==1

def test_e2e_no_invalid_projected_candidate_reaches_a_critic(e2e):
    result,l,t=e2e
    reviewed={k[1] for k in t.counts if k[0] in CRITICS}
    assert reviewed and not reviewed&E2E_INVALID
    assert reviewed=={f'C{i:03}' for i in range(1,41)}-E2E_INVALID
    for (req,) in l.db.execute('SELECT request FROM calls'):
        r=json.loads(req)
        if r['role'] in CRITICS:
            cand=r['context']['CANDIDATE']
            assert cand['CANDIDATE_ID'] not in E2E_INVALID
            assert cand==fixture(PLAN[int(cand['CANDIDATE_ID'][1:])-1],C)      # the slot's own exact card

def test_e2e_impostor_for_a_later_slot_is_ignored(e2e):
    result,l,t=e2e
    rows={r['CANDIDATE_ID']:r for r in l.candidates()}
    gen={json.loads(q)['slot']:k for k,q in l.db.execute("SELECT key,request FROM calls WHERE request LIKE '%\"role\":\"GENERATOR\"%'")}
    assert rows['C011']['ROUND']=='generation:1' and rows['C011']['CALL_KEY']==gen['generation:1']
    assert 'impostor' not in canonical(rows['C011']['CARD'])
    ev=[json.loads(p) for k,p in l.db.execute("SELECT kind,payload FROM events WHERE kind='EXTRA_GENERATED_CARDS_IGNORED'")]
    assert sorted(tuple(e['CANDIDATE_IDS']) for e in ev)==[('C011','C999')]
    mal=[json.loads(p) for k,p in l.db.execute("SELECT kind,payload FROM events WHERE kind='MALFORMED_GENERATED_ITEMS_IGNORED'")]
    assert [(m['ROUND'],m['ITEM_INDEXES']) for m in mal]==[('generation:2',[0,1])]

def test_e2e_generator_calls_carry_the_compact_identity(e2e):
    result,l,t=e2e
    for k,q in l.db.execute('SELECT key,request FROM calls'):
        r=json.loads(q)
        if r['role']=='GENERATOR':
            assert r['provider_wire_format']==ANTHROPIC_GENERATOR_WIRE_FORMAT and k!=FAILED_SMOKE_KEY
            assert r['provider_schema_digest']==digest(anthropic_output_schema('GENERATOR',C,r))
