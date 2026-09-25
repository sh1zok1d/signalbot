"""Fresh synthetic corpus gate (>=200 cards) for GENERATOR_CONTRACT_V02.

Required: unsafe cards admitted = 0; every invalid card quarantined individually;
false-negative rate measured; legacy compatibility isolated from new output."""
import json
import sqlite3
from collections import Counter
from pathlib import Path
from scripts.research.generator_v0.context import Contexts
from scripts.research.generator_v0 import contract,legacy_v01
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import fixture,slot_plan
from scripts.research.generator_v0.runner import _intake_round
from scripts.research.generator_v0_gate.corpus import build_corpus,round_cases

REPO=Path(__file__).resolve().parents[2]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'

def evaluate(items,c):
    rows=[]
    for it in items:
        v=contract.card_violations(it['CARD'],c,it['SLOT'])
        rows.append({**it,'GOT':'HARD_FAIL' if v else 'VALID','RULES':sorted({x['RULE'] for x in v})})
    return rows

def corpus_metrics(rows):
    safe_compliant=[r for r in rows if r['SAFETY'] in ('SAFE','SEMANTIC_ERROR') and r['CONTRACT']=='COMPLIANT']
    safe_violating=[r for r in rows if r['SAFETY']=='SAFE' and r['CONTRACT']=='VIOLATING']
    unsafe=[r for r in rows if r['SAFETY']=='UNSAFE']
    return {
        'CORPUS_SIZE':len(rows),'CATEGORIES':dict(sorted(Counter(r['CATEGORY'] for r in rows).items())),
        'UNSAFE':len(unsafe),'UNSAFE_ADMITTED':sum(r['GOT']=='VALID' for r in unsafe),
        'SAFE_COMPLIANT':len(safe_compliant),'FALSE_NEGATIVES_SAFE_COMPLIANT':sum(r['GOT']=='HARD_FAIL' for r in safe_compliant),
        'SAFE_BUT_CONTRACT_VIOLATING':len(safe_violating),'SAFE_BUT_CONTRACT_VIOLATING_QUARANTINED':sum(r['GOT']=='HARD_FAIL' for r in safe_violating),
        'SEMANTIC_ERROR_ADMITTED_FOR_RED_TEAM':sum(r['GOT']=='VALID' for r in rows if r['SAFETY']=='SEMANTIC_ERROR'),
        'EXPECTATION_MISMATCHES':[r['ID'] for r in rows if r['GOT']!=r['EXPECT']],
        'RULE_HITS':dict(sorted(Counter(x for r in rows for x in r['RULES']).items())),
    }

def test_corpus_is_large_fresh_and_labelled():
    items=build_corpus()
    assert len(items)>=200
    assert len({i['ID'] for i in items})==len(items)
    for it in items:
        assert it['SAFETY'] in ('SAFE','UNSAFE','SEMANTIC_ERROR') and it['CONTRACT'] in ('COMPLIANT','VIOLATING') and it['EXPECT'] in ('VALID','HARD_FAIL')

def test_corpus_reuses_no_production_string():
    db=sqlite3.connect('file:{}?mode=ro&immutable=1'.format(V7.as_posix()),uri=True)
    prod=set()
    def walk(v):
        if isinstance(v,dict):[walk(x) for x in v.values()]
        elif isinstance(v,list):[walk(x) for x in v]
        elif isinstance(v,str) and len(v)>=16:prod.add(v)
    try:
        for (resp,) in db.execute('SELECT response FROM calls'):walk(json.loads(json.loads(resp)['raw']))
    finally:db.close()
    assert len(prod)>100
    ours=set()
    def walk2(v):
        if isinstance(v,dict):[walk2(x) for x in v.values()]
        elif isinstance(v,list):[walk2(x) for x in v]
        elif isinstance(v,str):ours.add(v)
    for it in build_corpus():walk2(it['CARD'])
    # Controlled vocabulary (catalog keys, status enums, family names, canonical
    # range tokens) is shared by design; free-text production prose must not be.
    c=Contexts();import re
    vocab=set(c.catalog)|set(c.design['DATA_STATUS_TAXONOMY'])|set(c.families)|set(c.families.values())|{'NEW_FAMILY_PROPOSAL'}
    shared={x for x in ours&prod if x not in vocab and not re.fullmatch(contract.LEGAL_RANGE_PATTERN,x)}
    assert shared==set()

def test_corpus_gate_unsafe_admitted_zero_and_false_negatives_measured():
    c=Contexts();m=corpus_metrics(evaluate(build_corpus(),c))
    assert m['UNSAFE']>=80 and m['UNSAFE_ADMITTED']==0
    assert m['SAFE_COMPLIANT']>=60 and m['FALSE_NEGATIVES_SAFE_COMPLIANT']==0
    assert m['SAFE_BUT_CONTRACT_VIOLATING_QUARANTINED']==m['SAFE_BUT_CONTRACT_VIOLATING']>0
    assert m['SEMANTIC_ERROR_ADMITTED_FOR_RED_TEAM']==4
    assert m['EXPECTATION_MISMATCHES']==[]

def test_corpus_gate_report_is_current():
    """The committed gate report must equal a fresh recomputation (no stale evidence)."""
    report=json.loads((REPO/'docs/research/generator_v0_repair/OFFLINE_GATE_REPORT.json').read_text(encoding='utf-8'))
    assert report['CORPUS']==corpus_metrics(evaluate(build_corpus(),Contexts()))

def test_each_corpus_card_is_quarantined_individually_inside_a_round(tmp_path):
    """Put invalid corpus cards into real rounds: only their own slot fails."""
    c=Contexts();plan=slot_plan(40);bad=[r for r in evaluate(build_corpus(),c) if r['EXPECT']=='HARD_FAIL']
    for i in range(0,40,10):
        slots=plan[i:i+10];l=Ledger(tmp_path/('r%d.sqlite'%i),{'RUN_ID':'q'})
        cards=[fixture(s,c) for s in slots]
        victim=bad[i//10];card=dict(victim['CARD']);card.update(slots[3]) if victim['CATEGORY']!='SLOT' else None
        if victim['CATEGORY']=='SLOT':card=dict(victim['CARD'],CANDIDATE_ID=slots[3]['CANDIDATE_ID']) if victim['NOTE']!='wrong id for slot' else card
        cards[3]=card
        admitted=_intake_round(c,l,i//10,slots,contract.CONTRACT_ID,'k'+str(i),cards,[])
        states={x['CANDIDATE_ID']:x['STATE'] for x in l.candidates()}
        assert states[slots[3]['CANDIDATE_ID']]=='HARD_FAIL'
        assert sum(s=='VALID' for s in states.values())==9 and len(admitted)==9
        l.close()

def test_round_level_faults_quarantine_slots(tmp_path):
    c=Contexts();slots=slot_plan(40)[:10]
    for n,(label,fn,expected) in enumerate(round_cases()):
        l=Ledger(tmp_path/('round%d.sqlite'%n),{'RUN_ID':'r'})
        cards=fn([fixture(s,c) for s in slots])
        _intake_round(c,l,0,slots,contract.CONTRACT_ID,'key',cards,['synthetic'])
        states=[{x['CANDIDATE_ID']:x['STATE'] for x in l.candidates()}[s['CANDIDATE_ID']] for s in slots]
        assert states==expected,label
        l.close()
    l=Ledger(tmp_path/'none.sqlite',{'RUN_ID':'r'})
    _intake_round(c,l,0,slots,contract.CONTRACT_ID,'key',None,['unusable'])
    assert {x['STATE'] for x in l.candidates()}=={'HARD_FAIL'}

def test_historical_cards_are_not_admitted_under_new_keys(tmp_path):
    """Legacy acceptance is bound to call key: the same 30 cards in a new V02 round are judged by V02."""
    c=Contexts()
    db=sqlite3.connect('file:{}?mode=ro&immutable=1'.format(V7.as_posix()),uri=True)
    try:rows={json.loads(r)['slot']:(k,json.loads(json.loads(resp)['raw'])['CANDIDATES']) for k,r,resp in db.execute('SELECT key,request,response FROM calls')}
    finally:db.close()
    key,cards=rows['generation:1'];slots=slot_plan(40)[10:20]
    l=Ledger(tmp_path/'legacy.sqlite',{'RUN_ID':'l'})
    admitted=_intake_round(c,l,1,slots,legacy_v01.CONTRACT_ID,key,cards,[])
    assert len(admitted)==10
    l2=Ledger(tmp_path/'v02.sqlite',{'RUN_ID':'v'})
    admitted_v02=_intake_round(c,l2,1,slots,contract.CONTRACT_ID,'new-key',cards,[])
    assert len(admitted_v02)<10
    l.close();l2.close()
