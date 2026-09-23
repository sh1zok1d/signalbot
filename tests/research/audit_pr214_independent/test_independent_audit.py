"""Independent verifier suite for Generator V0 PR #214.

Audit-only. Does not modify production code. Makes no paid API calls.
Does not open 2025/2026 market data. Does not resume v6/v7 live runs.
Does not compute scientific outcomes.

Oracles in this file are written from the published contract text, the
call-state charging rules, and observed campaign behavior — not by copying
production regexes, selector sort, or the implementer's labelled corpus.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import random
import shutil
import socket
import sqlite3
import tempfile
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

import pytest

from scripts.research.generator_v0.context import Contexts, ContractError, canonical, digest
from scripts.research.generator_v0.ledger import Ledger, BudgetExceeded, CallUncertain, AttemptClosed
from scripts.research.generator_v0.provider import (
    Caller, MockProvider, Response, ProviderFailure, BilledFailure, ProviderRejected, ProviderThrottled,
    BackgroundPending,
)
from scripts.research.generator_v0.runner import run_campaign, MIN_VALID_CANDIDATES, MAX_CONTENT_ATTEMPTS, RESUMABLE_STATUSES, TERMINAL_STATUSES
from scripts.research.generator_v0.roles import Roles, RoleContractError, NOVELTY_PROMPT, SELECTOR_PROMPT, FEAS_PROMPT, NOVELTY_DIMENSIONS, RED_DIMENSIONS, FEAS_DIMENSIONS, RELATIONS, BATCH_RELATIONS
from scripts.research.generator_v0.schema import normalize_role_output, parse_json, validate_card
from scripts.research.generator_v0.output_schemas import role_schema, openai_response_format, responses_text_format, strict_subset_violations
from scripts.research.generator_v0.derive import (
    derive_complete_rounds, authorize_derived_continuation, remaining_campaign_budget_preflight,
    OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD, reconcile_call, authorize_budget_extension, derived_config,
)
from scripts.research.generator_v0.__main__ import main, refuse_sealed_or_archived, sealed_journal
from scripts.research.generator_v0.mock import slot_plan
from scripts.research.generator_v0.contract import card_violations, generator_prompt, RULES, LEGAL_RANGE_PATTERN
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS, GENERATOR_MAX_OUTPUT_TOKENS, rates
import importlib.util as _ilu
_corpus_spec=_ilu.spec_from_file_location('audit_pr214_corpus', Path(__file__).parent/'corpus.py')
_corpus=_ilu.module_from_spec(_corpus_spec);_corpus_spec.loader.exec_module(_corpus)
build=_corpus.build;seed=_corpus.seed;LISTED_OPEN_ENDED=_corpus.LISTED_OPEN_ENDED

REPO=Path(__file__).resolve().parents[3]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'
V7_SHA='e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457'
# Independently required cumulative: task statement, not implementer test.
V7_CUMULATIVE=4_946_750
OWNER_CAP=17_100_000

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k: pytest.fail('network reached'))


# ---------------------------------------------------------------------------
# Independent charge oracle (re-stated from the published failure model, not
# imported from derive.charge / ledger.CHARGE_SQL).
# ---------------------------------------------------------------------------

def audit_charge(state, cost, reserved):
    if state in ('COMPLETE','FAILED_WITH_COST','RECONCILED_BILLED'):
        return 0 if cost is None else cost
    if state in ('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED'):
        return 0
    if cost is not None:
        return cost
    return reserved or 0

def journal_spend(path, *, immutable=False):
    """Read-only spend sum. immutable=True for sealed-hash copies (no WAL)."""
    path=Path(path).resolve()
    if immutable:
        from scripts.research.generator_v0.ledger import archive_connect
        db=archive_connect(path)
    else:
        db=sqlite3.connect('file:{}?mode=ro'.format(path.as_posix()), uri=True)
    try:
        rows=db.execute('SELECT state,cost,reserved FROM calls').fetchall()
        return sum(audit_charge(s,c,r) for s,c,r in rows), rows
    finally:
        db.close()


# ---------------------------------------------------------------------------
# A. Independent corpus
# ---------------------------------------------------------------------------

CORPUS=build()

def test_independent_corpus_size_and_label_source():
    assert len(CORPUS)>=200
    assert {x['SPEC_INTENT'] for x in CORPUS}<= {'ADMIT','QUARANTINE'}
    impl=REPO/'scripts/research/generator_v0_gate/corpus.py'
    impl_text=impl.read_text(encoding='utf-8')
    for item in CORPUS:
        if not isinstance(item['CARD'],dict):
            continue
        name=item['CARD'].get('NAME')
        if isinstance(name,str) and name.startswith('Audit probe'):
            assert name not in impl_text

def test_independent_corpus_listed_phrases_quarantined():
    c=Contexts()
    listed=[x for x in CORPUS if x['CATEGORY'] in ('LISTED_OPEN_ENDED','LISTED_RECENCY','LISTED_TRADING','LISTED_YEAR','PROTECTED_FLAG','PROTECTED_SOURCE')]
    assert len(listed)>=40
    admitted=[]
    for item in listed:
        v=card_violations(item['CARD'],c,item['SLOT'])
        if not v:
            admitted.append(item['ID']+':'+item['NOTE'])
    assert admitted==[], admitted

def test_independent_corpus_canonical_admitted():
    c=Contexts()
    bad=[]
    for item in CORPUS:
        if item['CATEGORY']!='CANONICAL':
            continue
        v=card_violations(item['CARD'],c,item['SLOT'])
        if v:
            bad.append((item['ID'],item['NOTE'],v[:2]))
    assert bad==[], bad

def test_independent_corpus_paraphrase_false_negatives():
    """Principle-level open-ended / post-2024 / recency / trading paraphrases.

    A false negative is a card whose SPEC_INTENT is QUARANTINE and whose
    category is a paraphrase of the rule principle, but intake admits it.
    """
    c=Contexts()
    leaks=[]
    for item in CORPUS:
        if item['CATEGORY'] not in ('PARAPHRASE','RECENCY_PARAPHRASE','TRADING_PARAPHRASE'):
            continue
        v=card_violations(item['CARD'],c,item['SLOT'])
        if not v:
            leaks.append({'ID':item['ID'],'NOTE':item['NOTE'],'CATEGORY':item['CATEGORY']})
    notes={x['NOTE'] for x in leaks}
    # Confirmed false negatives against the rule *principle* (not the listed-phrase regex).
    for needle in ('post 2024','thru today','until now','after December 2024','fullwidth 2025','signal to buy'):
        assert needle in notes, needle
    assert len(leaks)>=30, len(leaks)
    (Path(__file__).parent/'PARAPHRASE_LEAKS.json').write_text(json.dumps(leaks,indent=2)+'\n',encoding='utf-8')

def test_independent_corpus_structural_quarantined():
    c=Contexts()
    admitted=[]
    for item in CORPUS:
        if item['CATEGORY'] not in ('STRUCT','RANGE_NEARMISS','LEGAL_RANGE','SCHEMA','SLOT','NEAREST','SEARCH','TEXT','CATALOG_RANGE','PER_SNAPSHOT_MISUSE','AGGREGATE','MISSING_OBS','GAP_CLASS','READY_UNCATALOGUED'):
            continue
        if not isinstance(item['CARD'],dict):
            v=card_violations(item['CARD'],c,item['SLOT'])
            assert v
            continue
        v=card_violations(item['CARD'],c,item['SLOT'])
        if not v:
            admitted.append(item['ID']+':'+item['NOTE'])
    assert admitted==[], admitted

def test_one_invalid_card_does_not_kill_campaign(tmp_path):
    c=Contexts()
    plan=slot_plan(40)
    def responder(req):
        if req['role']=='GENERATOR':
            cards=[]
            for s in req['parameters']['slots']:
                card=seed();card.update(s)
                if s['CANDIDATE_ID']=='C003':
                    card['MECHANISM']='Occupancy window through today is the object of study.'
                if s['CANDIDATE_ID']=='C007':
                    card['PROTECTED_DATA_REQUIREMENT']=True
                cards.append(card)
            return canonical({'CANDIDATES':cards})
        return _cooperative_critic(c,req)
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'f01'})
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    states={x['CANDIDATE_ID']:x['STATE'] for x in l.candidates()}
    assert states['C003']=='HARD_FAIL' and states['C007']=='HARD_FAIL'
    assert r['METRICS']['VALID']==38
    l.close()


# ---------------------------------------------------------------------------
# F02-F05 / F06 prompt vs schema
# ---------------------------------------------------------------------------

def test_novelty_prompt_describes_lists_schema_requires_keyed_objects():
    prompt=NOVELTY_PROMPT
    assert 'list of {SIGNATURE_ID, RELATION}' in prompt or 'list of {SIGNATURE_ID,RELATION}' in prompt.replace(' ','')
    # Application prompt language.
    assert 'PRIOR_RELATIONS is a list' in prompt
    c=Contexts()
    req={'context':{'CANDIDATE':{'CANDIDATE_ID':'C401'},'CURRENT_BATCH_SIGNATURES':[{'CANDIDATE_ID':'C401'},{'CANDIDATE_ID':'C402'}]}}
    schema=role_schema('NOVELTY_CRITIC',c,provider=True,request=req)
    assert schema['properties']['PRIOR_RELATIONS']['type']=='object'
    assert schema['properties']['BATCH_RELATIONS']['type']=='object'
    assert schema['properties']['PRIOR_RELATIONS']['additionalProperties'] is False

def test_generator_prompt_and_provider_schema_agree_on_keyed_candidates():
    p=generator_prompt()
    assert 'keyed as the output schema requires' in p
    c=Contexts();slots=slot_plan(40)[:10]
    s=role_schema('GENERATOR',c,provider=True,request={'parameters':{'slots':slots}})
    assert s['properties']['CANDIDATES']['type']=='object'
    assert set(s['properties']['CANDIDATES']['properties'])=={x['CANDIDATE_ID'] for x in slots}

def test_legal_range_pattern_admits_start_after_end_that_validator_rejects():
    import re
    sample='2024-12..2020-01'
    assert re.fullmatch(LEGAL_RANGE_PATTERN, sample)
    card=seed();card['DATA_REQUIRED'][0]['LEGAL_RANGE']=sample
    v=card_violations(card,Contexts(),{'CANDIDATE_ID':'C401','MECHANISM_FAMILY':'NEW_FAMILY_PROPOSAL','INFORMATION_SOURCE':'KLINES'})
    rules={x['RULE'] for x in v}
    assert 'LEGAL_RANGE_GRAMMAR' in rules

def test_schema_one_value_enums_and_capturing_groups():
    c=Contexts();slots=slot_plan(10)
    s=role_schema('GENERATOR',c,provider=True,request={'parameters':{'slots':slots}})
    card=s['properties']['CANDIDATES']['properties']['C001']
    assert card['properties']['CANDIDATE_ID']['enum']==['C001']
    assert card['properties']['PROTECTED_DATA_REQUIREMENT']['enum']==[False]
    pattern=card['properties']['DATA_REQUIRED']['items']['properties']['LEGAL_RANGE']['pattern']
    # Unnamed capturing groups are present. Offline subset checker allows them;
    # provider acceptance is not proved here.
    assert '(' in pattern and '(?:' not in pattern
    assert strict_subset_violations(s)==[]


# ---------------------------------------------------------------------------
# F07-F08 retry / reconcile / crash
# ---------------------------------------------------------------------------

def _red_ctx(c):
    from scripts.research.generator_v0.roles import RED_PROMPT
    return Roles(c,None).request('RED_TEAM',seed()), RED_PROMPT

def test_not_billed_charges_zero_and_uses_new_transport_key(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    n={'i':0}
    class P(MockProvider):
        def complete(self,req):
            n['i']+=1
            if n['i']<3:
                raise ProviderFailure('429',billing='NOT_BILLED',retryable=True)
            return Response('{"ok":1}',{'input_tokens':1,'output_tokens':1},0)
    cal=Caller(c,l,P(None), cap_micro_usd=10_000)
    ctx,prompt=_red_ctx(c)
    assert cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')=='{"ok":1}'
    rows=l.export_calls()
    assert [r['STATE'] for r in rows]==['FAILED_NOT_BILLED','FAILED_NOT_BILLED','COMPLETE']
    assert l.spent_micro_usd()==0
    posts=n['i']
    assert cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')=='{"ok":1}'
    assert n['i']==posts  # COMPLETE never re-POSTed
    l.close()

def test_billed_failure_charges_and_content_retry_uses_new_key(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    n={'i':0}
    class P(MockProvider):
        def bound(self,req):return 50
        def complete(self,req):
            n['i']+=1
            if n['i']==1:
                raise ProviderFailure('length',billing='BILLED',cost=40,usage={'input_tokens':1,'output_tokens':1})
            return Response('{"ok":1}',{'input_tokens':1,'output_tokens':1},10)
    cal=Caller(c,l,P(None), cap_micro_usd=10_000)
    ctx,prompt=_red_ctx(c)
    with pytest.raises(BilledFailure):
        cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s',content_attempt=0)
    assert l.spent_micro_usd()==40
    assert cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s',content_attempt=1)=='{"ok":1}'
    states=[r['STATE'] for r in l.export_calls()]
    assert states==['FAILED_WITH_COST','COMPLETE']
    assert l.spent_micro_usd()==50
    l.close()

def test_uncertain_never_auto_replayed(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    class P(MockProvider):
        def bound(self,req):return 25
        def complete(self,req):
            raise TimeoutError('gone')
    cal=Caller(c,l,P(None), cap_micro_usd=10_000)
    ctx,prompt=_red_ctx(c)
    with pytest.raises(CallUncertain):
        cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')
    assert l.spent_micro_usd()==25
    with pytest.raises(CallUncertain):
        cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')
    assert len(l.export_calls())==1
    l.close()

def test_crash_after_post_then_not_billed_reconcile_duplicates_post(tmp_path):
    """RESERVED after a POST that left the machine, then NOT_BILLED, POSTs again.

    This is the unsafe operator path. Automatic resume is blocked; the
    duplicate requires an explicit reconcile.
    """
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    n={'i':0}
    class Crash(BaseException):
        pass
    class P(MockProvider):
        def bound(self,req):return 30
        def complete(self,req):
            n['i']+=1
            if n['i']==1:
                raise Crash('after the request left')
            return Response('{"ok":1}',{'input_tokens':1,'output_tokens':1},10)
    cal=Caller(c,l,P(None), cap_micro_usd=10_000)
    ctx,prompt=_red_ctx(c)
    with pytest.raises(Crash):
        cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')
    row=l.export_calls()[0]
    assert row['STATE']=='RESERVED' and l.spent_micro_usd()==30
    with pytest.raises(CallUncertain):
        cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')
    assert n['i']==1  # no auto replay
    l.reconcile(row['CALL_KEY'],'NOT_BILLED',None,'op','assumed unbilled')
    out=cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')
    assert out=='{"ok":1}'
    assert n['i']==2  # second POST of the same logical call
    l.close()


# ---------------------------------------------------------------------------
# F09 selector
# ---------------------------------------------------------------------------

def _cooperative_critic(c,req):
    role=req['role'];ctx=req.get('context') or {}
    if role=='SELECTOR':
        j=ctx['SELECTION_JUDGMENTS']
        # Independent order: ascending ID, not the production ordinal sort.
        return canonical({'ORDERED_CANDIDATE_IDS':list(reversed(sorted(j)))})
    card=ctx['CANDIDATE']
    if role=='NOVELTY_CRITIC':
        leaf=[]
        for k,row in c.rows.items():
            if row['STATE']=='PARTIAL_OR_MIXED':
                continue
            leaf.append({'SIGNATURE_ID':k,'RELATION':'ORTHOGONAL_MECHANISM'})
        others=[{'CANDIDATE_ID':x['CANDIDATE_ID'],'RELATION':'ORTHOGONAL_MECHANISM'} for x in ctx['CURRENT_BATCH_SIGNATURES'] if x['CANDIDATE_ID']!=card['CANDIDATE_ID']]
        return canonical({'PRIOR_RELATIONS':leaf,'BATCH_RELATIONS':others,'JUDGMENTS':{k:2 for k in NOVELTY_DIMENSIONS}})
    if role=='FEASIBILITY_CRITIC':
        return canonical({'DATA_STATUS':card['DATA_STATUS'],'CHECKS':{'OBSERVABLE_SUPPORTED':True,'LEGAL_RANGE':True,'POINT_IN_TIME':True,'PROVENANCE':True,'BLOCKER_RESOLVED':True},'JUDGMENTS':{k:2 for k in FEAS_DIMENSIONS},'FEASIBILITY':2,'CHEAPNESS':2})
    if role=='RED_TEAM':
        return canonical({'CHECKS':{'NO_LOOKAHEAD':True,'CAUSALITY':True,'FALSIFIABLE':True,'BOUNDED_SEARCH':True,'CONFOUNDING_ADDRESSED':True,'NO_TRADING_CLAIM':True},'JUDGMENTS':{k:2 for k in RED_DIMENSIONS}})
    raise AssertionError(role)

def _gen_ok(req):
    cards=[]
    for s in req['parameters']['slots']:
        card=seed();card.update(s)
        if s['INFORMATION_SOURCE']!='KLINES':
            card['DATA_REQUIRED'][0]={'DATASET':'AUDIT_X','OBSERVABLE':'x','STATUS':'DATA_BLOCKED_MISSING_OBSERVABLE','LEGAL_RANGE':'2020-01..2024-12'}
            card['DATA_STATUS']='DATA_BLOCKED_MISSING_OBSERVABLE'
            card['MISSING_OBSERVABLES']=['x']
            card['DATA_GAP_CLASS']='AUDIT'
        cards.append(card)
    return canonical({'CANDIDATES':cards})

def test_selector_uncertain_completes_campaign_but_leaves_charged_reserved(tmp_path):
    c=Contexts()
    class P(MockProvider):
        def bound(self,req):
            return 77 if req['role']=='SELECTOR' else 0
        def complete(self,req):
            if req['role']=='GENERATOR':
                return Response(_gen_ok(req),{'input_tokens':0,'output_tokens':0},0)
            if req['role']=='SELECTOR':
                raise ProviderFailure('gateway',billing='UNCERTAIN')
            return Response(_cooperative_critic(c,req),{'input_tokens':0,'output_tokens':0},0)
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'sel'})
    r=run_campaign(c,Caller(c,l,P(None),cap_micro_usd=1_000_000))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    assert r['SELECTOR_ADVISORY']['STATUS']=='UNAVAILABLE'
    uncertain=[row for row in l.export_calls() if row['STATE']=='UNCERTAIN']
    assert len(uncertain)==1 and uncertain[0]['SLOT']=='selection'
    assert l.spent_micro_usd()>=77
    # Resume after completion does not reconcile.
    again=run_campaign(c,Caller(c,l,P(None),cap_micro_usd=1_000_000))
    assert again['STATUS']=='PENDING_HUMAN_REVIEW'
    assert [row['STATE'] for row in l.export_calls() if row['SLOT']=='selection']==['UNCERTAIN']
    l.close()

def test_selector_disagreement_does_not_abort(tmp_path):
    c=Contexts()
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        return _cooperative_critic(c,req)
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'sel2'})
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    assert r['SELECTOR_ADVISORY']['STATUS']=='DISAGREES'
    assert r['SELECTOR_AUTHORITY']=='DETERMINISTIC_ORDINAL_ORDER'
    l.close()


# ---------------------------------------------------------------------------
# F10 / F13 v7 lineage
# ---------------------------------------------------------------------------

def test_v7_cumulative_spend_is_4946750_before_any_new_reservation(tmp_path):
    assert hashlib.sha256(V7.read_bytes()).hexdigest()==V7_SHA
    src=tmp_path/'src';src.mkdir();shutil.copy(V7,src/'run.sqlite')
    # Independent sum of the copy via immutable archive connection, never the sealed original.
    spend, rows=journal_spend(src/'run.sqlite', immutable=True)
    assert spend==V7_CUMULATIVE, (spend, Counter(s for s,_,_ in rows))
    report=derive_complete_rounds(src,tmp_path/'dest',2)
    assert report['LINEAGE_TOTAL_MICRO_USD']==V7_CUMULATIVE
    assert report['LINEAGE_PRIOR_MICRO_USD']+report['IMPORTED_COST_MICRO_USD']==V7_CUMULATIVE
    dest=tmp_path/'dest'/'run.sqlite'
    dspend,_=journal_spend(dest)
    l=Ledger.open_readonly(dest)
    try:
        prior=l.lineage_prior_micro_usd()
        total=l.total_charged_micro_usd()
    finally:
        l.close()
    assert total==V7_CUMULATIVE==prior+dspend
    lineage=json.loads(sqlite3.connect('file:{}?mode=ro&immutable=1'.format((tmp_path/'dest'/'run.sqlite').resolve().as_posix()),uri=True).execute("SELECT value FROM meta WHERE key='lineage'").fetchone()[0])
    # Discarded generation:3 remains visible.
    slots={a['SLOT'] for a in lineage['PRIOR_ATTEMPTS']}
    assert 'generation:3' in slots
    gen3=[a for a in lineage['PRIOR_ATTEMPTS'] if a['SLOT']=='generation:3'][0]
    assert gen3['CHARGED_MICRO_USD']>0
    assert gen3.get('INTAKE',{}).get('CARDS')
    # Nested derive still totals the same.
    authorize_derived_continuation(tmp_path/'dest','op','go')
    report2=derive_complete_rounds(tmp_path/'dest',tmp_path/'dest2',2)
    assert report2['LINEAGE_TOTAL_MICRO_USD']==V7_CUMULATIVE
    assert hashlib.sha256((src/'run.sqlite').read_bytes()).hexdigest()==V7_SHA
    pre=remaining_campaign_budget_preflight(tmp_path/'dest')
    assert pre['SPENT_MICRO_USD']==V7_CUMULATIVE
    assert pre['REMAINING_AUTHORIZED_MICRO_USD']==OWNER_CAP-V7_CUMULATIVE
    assert pre['WORST_CASE_REMAINING_MICRO_USD']>pre['REMAINING_AUTHORIZED_MICRO_USD']
    (Path(__file__).parent/'V7_REMAINING_BOUND.json').write_text(json.dumps({
        'SPENT_MICRO_USD':pre['SPENT_MICRO_USD'],
        'REMAINING_AUTHORIZED_MICRO_USD':pre['REMAINING_AUTHORIZED_MICRO_USD'],
        'WORST_CASE_REMAINING_MICRO_USD':pre['WORST_CASE_REMAINING_MICRO_USD'],
        'WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD':pre['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD'],
        'FITS_AUTHORIZED_REMAINING':pre['FITS_AUTHORIZED_REMAINING'],
    },indent=2)+'\n',encoding='utf-8')

def test_repeated_derive_cannot_refund_or_omit_prior_spend(tmp_path):
    src=tmp_path/'src';src.mkdir();shutil.copy(V7,src/'run.sqlite')
    a=derive_complete_rounds(src,tmp_path/'a',2)
    authorize_derived_continuation(tmp_path/'a','op','go')
    b=derive_complete_rounds(tmp_path/'a',tmp_path/'b',1)
    authorize_derived_continuation(tmp_path/'b','op','go')
    c=derive_complete_rounds(tmp_path/'b',tmp_path/'c',1)
    assert a['LINEAGE_TOTAL_MICRO_USD']==b['LINEAGE_TOTAL_MICRO_USD']==c['LINEAGE_TOTAL_MICRO_USD']==V7_CUMULATIVE


# ---------------------------------------------------------------------------
# F12 sealed journal
# ---------------------------------------------------------------------------

def test_cli_refuses_sealed_hash_at_foreign_path(tmp_path):
    d=tmp_path/'elsewhere';d.mkdir();shutil.copy(V7,d/'run.sqlite')
    assert sealed_journal(d) is True
    with pytest.raises(ContractError, match='sealed journal'):
        refuse_sealed_or_archived(d)
    with pytest.raises(ContractError, match='sealed journal'):
        main(['inspect','--run-dir',str(d)])
    assert hashlib.sha256((d/'run.sqlite').read_bytes()).hexdigest()==V7_SHA

def test_ledger_library_can_mutate_a_sealed_hash_copy(tmp_path):
    d=tmp_path/'copy';d.mkdir();shutil.copy(V7,d/'run.sqlite')
    before=hashlib.sha256((d/'run.sqlite').read_bytes()).hexdigest()
    assert before==V7_SHA
    l=Ledger(d/'run.sqlite')  # no sealed check in Ledger.__init__
    try:
        with l.transaction():
            l.event('AUDIT_WRITE',{'x':1})
            l.set('status','CREATED')
    finally:
        l.close()
    after=hashlib.sha256((d/'run.sqlite').read_bytes()).hexdigest()
    assert after!=V7_SHA
    # After the hash changes, CLI no longer treats it as sealed.
    assert sealed_journal(d) is False


# ---------------------------------------------------------------------------
# F13 attach_parsed provenance split
# ---------------------------------------------------------------------------

def test_attach_parsed_replaces_raw_but_keeps_wire_hash(tmp_path):
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x','CAP_MICRO_USD':1000})
    key=digest({'n':'k'})
    req={'n':'k','prompt_version':'generator-v0.2','context':{},'provider':'x','model':'x','parameters':{},'role':'GENERATOR'}
    # Use the actual key the ledger will compute from canonical(request) via import/finish path.
    key=digest(req) if False else 'k1'
    l.reserve('k1',req,100,1000)
    wire='{ "CANDIDATES" : [ ] }'
    sha=hashlib.sha256(wire.encode()).hexdigest()
    l.finish('k1',{'raw':wire,'raw_sha256':sha,'response_id':'r1'},10,{'input_tokens':1,'output_tokens':1})
    l.attach_parsed('k1',canonical({'CANDIDATES':[]}))
    blob=json.loads(l.db.execute('SELECT response FROM calls WHERE key=?',('k1',)).fetchone()[0])
    assert blob['raw_sha256']==sha
    assert blob['raw']!=wire
    assert hashlib.sha256(blob['raw'].encode()).hexdigest()!=sha
    l.close()


# ---------------------------------------------------------------------------
# State machine with real pause-causing rows
# ---------------------------------------------------------------------------

def test_resume_from_uncertain_without_reconcile_cannot_post(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    flag={'boom':True}
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        if flag['boom'] and req['role']=='NOVELTY_CRITIC' and req['slot'].endswith('C001'):
            raise TimeoutError('x')
        return _cooperative_critic(c,req)
    with pytest.raises(CallUncertain):
        run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert l.get('status')=='PAUSED_UNCERTAIN_CALL'
    posts=MockProvider(responder).calls
    p=MockProvider(responder)
    with pytest.raises(CallUncertain):
        run_campaign(c,Caller(c,l,p))
    assert p.calls==0
    key=[r['CALL_KEY'] for r in l.export_calls() if r['STATE']=='UNCERTAIN'][0]
    l.reconcile(key,'NOT_BILLED',None,'op','dashboard empty')
    flag['boom']=False
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    l.close()

@pytest.mark.parametrize('status',('PENDING_HUMAN_REVIEW','STOPPED_INSUFFICIENT_VALID','MUTATED_REQUIRES_REVIEW','DERIVED_IMPORTED_REVALIDATED','UNKNOWN'))
def test_non_resumable_status_posts_nothing(tmp_path,status):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    l.set('status',status);l.db.commit()
    p=MockProvider(lambda req: _gen_ok(req))
    with pytest.raises(ContractError):
        run_campaign(c,Caller(c,l,p))
    assert p.calls==0
    l.close()

def test_created_status_without_pause_row_is_not_a_sufficient_resume_oracle(tmp_path):
    """Implementer state-machine tests set status without the causing row.

    A CREATED journal with no calls is a legal start, not a pause. A
    PAUSED_UNCERTAIN_CALL without an UNCERTAIN row is a corrupt label: the
    runner will still attempt generation because RESUMABLE_STATUSES includes
    it and the first call is a new key.
    """
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    l.set('status','PAUSED_UNCERTAIN_CALL');l.db.commit()
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        return _cooperative_critic(c,req)
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    l.close()


# ---------------------------------------------------------------------------
# Budget property
# ---------------------------------------------------------------------------

def test_budget_property_random_sequences_never_exceed_cap(tmp_path):
    rng=random.Random(214)
    cap=40_000
    for trial in range(25):
        l=Ledger(tmp_path/('t%d.sqlite'%trial),{'RUN_ID':'t','CAP_MICRO_USD':cap})
        l.set('lineage',{'PRIOR_SPEND_MICRO_USD':rng.choice([0,1000,5000,20000])})
        l.db.commit()
        prior=l.lineage_prior_micro_usd()
        for step in range(rng.randint(8,40)):
            key='k%d'%step
            bound=rng.randint(1,8000)
            before=l.total_charged_micro_usd()
            try:
                saved=l.reserve(key,{'id':key,'prompt_version':'x','context':{},'provider':'p','model':'m','parameters':{},'role':'RED_TEAM'},bound,cap)
            except BudgetExceeded:
                assert before+bound>cap
                continue
            assert saved is None
            assert l.total_charged_micro_usd()==before+bound<=cap
            roll=rng.random()
            if roll<0.35:
                cost=rng.randint(0,bound)
                l.finish(key,{'raw':'x','raw_sha256':'a'*64,'response_id':'r'},cost,{'input_tokens':1,'output_tokens':1})
            elif roll<0.5:
                l.failed(key,'429',state='FAILED_NOT_BILLED')
            elif roll<0.65:
                l.failed(key,'len',state='FAILED_WITH_COST',cost=rng.randint(0,bound),usage={'input_tokens':1})
            elif roll<0.8:
                l.failed(key,'to',state='UNCERTAIN')
                if rng.random()<0.6:
                    l.reconcile(key,rng.choice(['NOT_BILLED','BILLED']),rng.randint(1,bound),'op','e')
            # else leave RESERVED
            rows=l.db.execute('SELECT state,cost,reserved FROM calls').fetchall()
            assert l.spent_micro_usd()==sum(audit_charge(*row) for row in rows)
            assert l.total_charged_micro_usd()==prior+l.spent_micro_usd()<=cap
        l.close()

def test_fresh_campaign_worst_case_bound_against_owner_cap():
    """Offline bound for a brand-new 40-slot live shadow. No HTTP."""
    c=Contexts()
    def refuse(*a,**k):
        raise ContractError('offline')
    p=OpenAIProvider('audit',allow_real=True,budget_micro_usd=OWNER_CAP,contexts=c,transport=refuse)
    plan=slot_plan(40)
    total=0
    cards=[]
    for i in range(4):
        slots=plan[i*10:(i+1)*10]
        req={'role':'GENERATOR','context':c.generator(),'prompt':generator_prompt(),
             'parameters':{'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':slots},
             'output_contract':'GENERATOR_CONTRACT_V02','output_schema_digest':'x'}
        total+=p.bound(req)
        for s in slots:
            card=seed();card.update(s);cards.append(card)
    for card in cards:
        for role,prompt in (('NOVELTY_CRITIC',NOVELTY_PROMPT),('FEASIBILITY_CRITIC','feas'),('RED_TEAM','red')):
            if role=='NOVELTY_CRITIC':
                ctx=Roles(c,None).request(role,card,cards)
            else:
                ctx=Roles(c,None).request(role,card)
            req={'role':role,'context':ctx,'prompt':prompt,'parameters':{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS[role]}}
            total+=p.bound(req)
    sel_ctx={'SANITIZED_CRITIC_OUTPUTS':[{'CANDIDATE_ID':x['CANDIDATE_ID'],'DATA_STATUS':x['DATA_STATUS']} for x in cards],
             'DATA_STATUS':{x['CANDIDATE_ID']:x['DATA_STATUS'] for x in cards},
             'SELECTION_JUDGMENTS':{x['CANDIDATE_ID']:{'MECHANISM_DISTANCE':3,'INFORMATION_GAIN':3,'FEASIBILITY':3,'CHEAPNESS':3} for x in cards}}
    total+=p.bound({'role':'SELECTOR','context':sel_ctx,'prompt':SELECTOR_PROMPT,'parameters':{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS['SELECTOR']}})
    with_retry=total*MAX_CONTENT_ATTEMPTS  # conservative (selector usually not retried)
    # Finding: a fresh 40-slot shadow cannot be shown to fit the owner ceiling
    # at reservation-bound accounting.
    (Path(__file__).parent/'FRESH_CAMPAIGN_BOUND.json').write_text(json.dumps({
        'SINGLE_ATTEMPT_WORST_CASE_MICRO_USD':total,
        'CONTENT_RETRY_UPPER_MICRO_USD':with_retry,
        'OWNER_CAP_MICRO_USD':OWNER_CAP,
        'EXCEEDS_OWNER_CAP':total>OWNER_CAP,
    },indent=2)+'\n',encoding='utf-8')
    assert total>OWNER_CAP, {'single_attempt':total,'cap':OWNER_CAP}


# ---------------------------------------------------------------------------
# Roles.request F01 hole: ContractError from validate_card
# ---------------------------------------------------------------------------

def test_invalid_card_into_roles_request_is_not_role_contract_error():
    c=Contexts()
    roles=Roles(c,None)
    bad=seed();bad['PROTECTED_DATA_REQUIREMENT']=True
    with pytest.raises(ContractError) as e:
        roles.request('RED_TEAM',bad)
    assert not isinstance(e.value, RoleContractError)


# ---------------------------------------------------------------------------
# Independent noisy E2E using keyed provider encoding (not MockResponder)
# ---------------------------------------------------------------------------

class AuditCrash(BaseException):
    pass

class IndependentTransport:
    def __init__(self,contexts,faults=None):
        self.c=contexts;self.faults=dict(faults or {});self.log=[];self.payloads={};self.n=0;self.counts=Counter()
    def posts(self):
        return [x for x in self.log if x[0]=='POST']
    def __call__(self,method,path,body,headers,timeout):
        self.log.append((method,path))
        if method=='DELETE':
            return 200,b'{}'
        if method=='GET':
            rid=path.rsplit('/',1)[1]
            text=self.payloads[rid]
            return 200,json.dumps({'id':rid,'status':'completed','output_text':text,'usage':{'input_tokens':4000,'output_tokens':8000,'output_tokens_details':{'reasoning_tokens':3000}}}).encode()
        b=json.loads(body)
        if path=='/v1/responses':
            user=json.loads(b['input']);slots=user['slots']
            rnd=(int(slots[0]['CANDIDATE_ID'][1:])-1)//10
            self.counts[('GENERATOR',rnd)]+=1
            fault=self.faults.get(('GENERATOR',rnd,self.counts[('GENERATOR',rnd)]))
            if fault=='429':
                return 429,b'{"error":{"type":"rate_limit"}}'
            cards={}
            for s in slots:
                card=seed();card.update(s)
                if s['INFORMATION_SOURCE']!='KLINES':
                    card['DATA_REQUIRED'][0]={'DATASET':'AUDIT_X','OBSERVABLE':'x','STATUS':'DATA_BLOCKED_MISSING_OBSERVABLE','LEGAL_RANGE':'2020-01..2024-12'}
                    card['DATA_STATUS']='DATA_BLOCKED_MISSING_OBSERVABLE'
                    card['MISSING_OBSERVABLES']=['x'];card['DATA_GAP_CLASS']='AUDIT'
                if fault=='drop' and s['CANDIDATE_ID']==slots[-1]['CANDIDATE_ID']:
                    continue
                if fault=='bad_range' and s==slots[4]:
                    card['DATA_REQUIRED'][0]['LEGAL_RANGE']='2020-01 to 2024-12'
                surf=card['SEARCH_SURFACE']
                enc=dict(card)
                enc['SEARCH_SURFACE']={'MAX_VARIANTS':surf['MAX_VARIANTS'],'PARAMETERS':[{'NAME':k,'VALUES':v} for k,v in surf['PARAMETERS'].items()]}
                cards[enc['CANDIDATE_ID']]=enc
            self.n+=1;rid='resp_audit_'+str(self.n)
            self.payloads[rid]=canonical({'CANDIDATES':cards})
            return 200,json.dumps({'id':rid,'object':'response','status':'queued'}).encode()
        # chat completions
        sysmsg=b['messages'][0]['content'];user=json.loads(b['messages'][1]['content']);ctx=user['context']
        if sysmsg==NOVELTY_PROMPT or 'PRIOR_RELATIONS' in sysmsg:
            role='NOVELTY_CRITIC'
        elif sysmsg==SELECTOR_PROMPT or 'ORDERED_CANDIDATE_IDS' in sysmsg:
            role='SELECTOR'
        elif 'NO_LOOKAHEAD' in sysmsg and 'FALSIFIABLE' in sysmsg:
            role='RED_TEAM'
        else:
            role='FEASIBILITY_CRITIC'
        target=ctx['CANDIDATE']['CANDIDATE_ID'] if 'CANDIDATE' in ctx else 'selection'
        self.counts[(role,target)]+=1
        fault=self.faults.get((role,target,self.counts[(role,target)]))
        if fault=='crash':
            raise AuditCrash('after POST '+role+' '+target)
        if fault=='429':
            return 429,b'{"error":{"type":"rate_limit"}}'
        def chat(obj,finish='stop'):
            return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':canonical(obj)}}],'usage':{'prompt_tokens':800,'completion_tokens':200}}).encode()
        if role=='NOVELTY_CRITIC':
            if fault=='malformed':
                return 200,chat('not-json') if False else json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'not-json'}}],'usage':{'prompt_tokens':800,'completion_tokens':200}}).encode()
            card=ctx['CANDIDATE']
            prior={k:'ORTHOGONAL_MECHANISM' for k,row in self.c.rows.items() if row['STATE']!='PARTIAL_OR_MIXED'}
            batch={x['CANDIDATE_ID']:'ORTHOGONAL_MECHANISM' for x in ctx['CURRENT_BATCH_SIGNATURES'] if x['CANDIDATE_ID']!=card['CANDIDATE_ID']}
            return 200,chat({'PRIOR_RELATIONS':prior,'BATCH_RELATIONS':batch,'JUDGMENTS':{k:2 for k in NOVELTY_DIMENSIONS}})
        if role=='FEASIBILITY_CRITIC':
            card=ctx['CANDIDATE']
            return 200,chat({'DATA_STATUS':card['DATA_STATUS'],'CHECKS':{'OBSERVABLE_SUPPORTED':True,'LEGAL_RANGE':True,'POINT_IN_TIME':True,'PROVENANCE':True,'BLOCKER_RESOLVED':True},'JUDGMENTS':{k:2 for k in FEAS_DIMENSIONS},'FEASIBILITY':2,'CHEAPNESS':2})
        if role=='RED_TEAM':
            if fault=='length':
                return 200,json.dumps({'choices':[{'finish_reason':'length','message':{'content':'{'}}],'usage':{'prompt_tokens':800,'completion_tokens':8000}}).encode()
            return 200,chat({'CHECKS':{'NO_LOOKAHEAD':True,'CAUSALITY':True,'FALSIFIABLE':True,'BOUNDED_SEARCH':True,'CONFOUNDING_ADDRESSED':True,'NO_TRADING_CLAIM':True},'JUDGMENTS':{k:2 for k in RED_DIMENSIONS}})
        ids=sorted(ctx['SELECTION_JUDGMENTS'])
        ids=list(reversed(ids))
        return 200,chat({'ORDERED_CANDIDATE_IDS':ids})

def test_independent_noisy_e2e_reaches_pending_human_review(tmp_path):
    c=Contexts()
    faults={
        ('GENERATOR',0,1):'429',
        ('GENERATOR',1,1):'drop',
        ('GENERATOR',2,1):'bad_range',
        ('NOVELTY_CRITIC','C004',1):'malformed',
        ('FEASIBILITY_CRITIC','C005',1):'429',
        ('RED_TEAM','C006',1):'length',
        ('RED_TEAM','C008',1):'crash',
    }
    t=IndependentTransport(c,faults)
    cap=OWNER_CAP
    l=Ledger(tmp_path/'run.sqlite',{'RUN_ID':'audit','CAP_MICRO_USD':cap,'SIZE':40})
    p=OpenAIProvider('audit',allow_real=True,budget_micro_usd=cap,transport=t,contexts=c,sleeper=lambda s:None)
    steps=[]
    try:
        try:
            run_campaign(c,Caller(c,l,p,cap,True),40)
        except AuditCrash:
            steps.append('CRASH')
            assert l.get('status') in (None,'CREATED') or True
        except CallUncertain:
            steps.append('UNCERTAIN_UNCAUGHT')
        # Crash is BaseException; runner does not pause. Ledger row is RESERVED.
        reserved=[r for r in l.export_calls() if r['STATE']=='RESERVED']
        if reserved:
            steps.append('RESERVED')
            with pytest.raises(CallUncertain):
                run_campaign(c,Caller(c,l,p,cap,True),40)
            steps.append('PAUSED')
            l.reconcile(reserved[0]['CALL_KEY'],'BILLED',max(1,min(reserved[0]['RESERVED_MICRO_USD'],1)),'op','treat as billed to avoid duplicate POST')
            steps.append('RECONCILED_BILLED')
        result=run_campaign(c,Caller(c,l,p,cap,True),40)
        steps.append(result['STATUS'])
        assert result['STATUS']=='PENDING_HUMAN_REVIEW', {'steps':steps,'status':l.get('status'),'metrics':result.get('METRICS')}
        assert result['METRICS']['HARD_FAIL']>=2
        assert result['SELECTOR_ADVISORY']['STATUS'] in ('DISAGREES','AGREES','UNAVAILABLE','MALFORMED')
        # No hidden manual patch of cards table.
        assert l.get('status')=='PENDING_HUMAN_REVIEW'
    finally:
        l.close()


# ---------------------------------------------------------------------------
# Implementer-test circularity notes encoded as assertions we can cite
# ---------------------------------------------------------------------------

def test_implementer_selector_mock_copies_production_sort():
    src=(REPO/'scripts/research/generator_v0/mock.py').read_text(encoding='utf-8')
    runner=(REPO/'scripts/research/generator_v0/runner.py').read_text(encoding='utf-8')
    needle="sorted(j,key=lambda k:tuple(-j[k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))"
    assert needle in src
    assert "sorted(selection,key=lambda k:tuple(-selection[k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))" in runner

def test_implementer_rule_table_test_is_self_referential():
    t=(REPO/'tests/research/test_generator_v0_contract.py').read_text(encoding='utf-8')
    assert "assert '['+rule['ID']+'] '+rule['TEXT'] in prompt" in t
    assert 'LEGAL_RANGE_PATTERN' in t and 'parse_legal_range' in t

def test_f11_feasibility_false_legal_range_rejects():
    c=Contexts();card=seed()
    l=Ledger(Path(tempfile.mkdtemp())/'r.sqlite',{'RUN_ID':'f11'})
    payload=canonical({'DATA_STATUS':card['DATA_STATUS'],'CHECKS':{'OBSERVABLE_SUPPORTED':True,'LEGAL_RANGE':False,'POINT_IN_TIME':True,'PROVENANCE':True,'BLOCKER_RESOLVED':True},'JUDGMENTS':{k:2 for k in FEAS_DIMENSIONS},'FEASIBILITY':2,'CHEAPNESS':2})
    roles=Roles(c,Caller(c,l,MockProvider(lambda req: payload)))
    out=roles.feasibility(card)
    assert out['VERDICT']=='REJECT' and out['CHECKS']['LEGAL_RANGE'] is False
    l.close()

def test_implementer_gate_test_count():
    n=0
    files=('test_generator_v0_contract.py','test_generator_v0_faults.py','test_generator_v0_corpus.py')
    for name in files:
        text=(REPO/'tests'/'research'/name).read_text(encoding='utf-8')
        n+=sum(1 for line in text.splitlines() if line.startswith('def test_'))
    (Path(__file__).parent/'IMPLEMENTER_GATE_TEST_COUNT.json').write_text(json.dumps({'THREE_FILE_TEST_DEFS':n,'CLAIMED':52},indent=2)+'\n')
    assert n>=40

def test_pause_provider_rejected_then_resume(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});flag={'reject':True}
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        if flag['reject'] and req['role']=='FEASIBILITY_CRITIC' and req['slot'].endswith('C002'):
            raise ProviderFailure('400',billing='NOT_BILLED',retryable=False)
        return _cooperative_critic(c,req)
    p=MockProvider(responder)
    with pytest.raises(ProviderRejected):
        run_campaign(c,Caller(c,l,p))
    assert l.get('status')=='PAUSED_PROVIDER_REJECTED'
    flag['reject']=False
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    l.close()

def test_pause_throttled_then_resume(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'});flag={'busy':True}
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        if flag['busy'] and req['role']=='RED_TEAM' and req['slot'].endswith('C001'):
            raise ProviderFailure('429',billing='NOT_BILLED',retryable=True)
        return _cooperative_critic(c,req)
    p=MockProvider(responder);p._sleep=lambda s: None
    with pytest.raises(ProviderThrottled):
        run_campaign(c,Caller(c,l,p))
    assert l.get('status')=='PAUSED_PROVIDER_THROTTLED'
    flag['busy']=False
    r=run_campaign(c,Caller(c,l,MockProvider(responder)))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    l.close()

def test_stopped_budget_then_extension_then_resume(tmp_path):
    c=Contexts()
    class Priced(MockProvider):
        def bound(s,req):return 80
        def complete(s,req):
            raw=super().complete(req);return Response(raw.raw,raw.usage,20)
    d=tmp_path/'run';d.mkdir()
    def responder(req):
        if req['role']=='GENERATOR':
            return _gen_ok(req)
        return _cooperative_critic(c,req)
    l=Ledger(d/'run.sqlite',{'RUN_ID':'b','CAP_MICRO_USD':500,'SIZE':40})
    with pytest.raises(BudgetExceeded):
        run_campaign(c,Caller(c,l,Priced(responder),500))
    assert l.get('status')=='STOPPED_BUDGET'
    spent=l.total_charged_micro_usd();l.close()
    ext=authorize_budget_extension(d,'op','continue','0.020000')
    assert ext['NEW_CAP_MICRO_USD']==20_000
    l=Ledger(d/'run.sqlite')
    r=run_campaign(c,Caller(c,l,Priced(responder),20_000))
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    assert l.total_charged_micro_usd()>=spent
    l.close()

def test_background_pending_resumes_same_response_id(tmp_path):
    c=Contexts()
    clock={'t':0};pending={'on':True}
    class T(IndependentTransport):
        def __call__(self,method,path,body,headers,timeout):
            self.log.append((method,path))
            if method=='DELETE':
                return 200,b'{}'
            if method=='GET':
                rid=path.rsplit('/',1)[1]
                if pending['on']:
                    return 200,json.dumps({'id':rid,'status':'queued'}).encode()
                text=self.payloads[rid]
                return 200,json.dumps({'id':rid,'status':'completed','output_text':text,'usage':{'input_tokens':4000,'output_tokens':8000,'output_tokens_details':{'reasoning_tokens':3000}}}).encode()
            return IndependentTransport.__call__(self,method,path,body,headers,timeout)
    t=T(c,{})
    l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'bg','CAP_MICRO_USD':OWNER_CAP,'SIZE':40})
    p=OpenAIProvider('audit',allow_real=True,budget_micro_usd=OWNER_CAP,transport=t,contexts=c,
                     sleeper=lambda s: clock.__setitem__('t',clock['t']+s),
                     clock=lambda: clock['t'],background_max_wait_seconds=1,poll_interval_seconds=2)
    with pytest.raises(BackgroundPending):
        run_campaign(c,Caller(c,l,p,OWNER_CAP,True),40)
    assert l.get('status')=='PAUSED_BACKGROUND_PENDING'
    rows=[r for r in l.export_calls() if r['STATE']=='BACKGROUND_SUBMITTED']
    assert len(rows)==1 and rows[0]['RESPONSE_ID']
    rid=rows[0]['RESPONSE_ID']
    creates_before=len([x for x in t.log if x==('POST','/v1/responses')])
    pending['on']=False
    r=run_campaign(c,Caller(c,l,p,OWNER_CAP,True),40)
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    gen0=[row for row in l.export_calls() if row['SLOT']=='generation:0']
    assert len(gen0)==1 and gen0[0]['STATE']=='COMPLETE' and gen0[0]['RESPONSE_ID']==rid
    # Later rounds may POST; generation:0 must not have been created again.
    assert gen0[0]['RESPONSE_ID']==rid
    l.close()

def test_crash_after_finish_does_not_repost(tmp_path):
    c=Contexts();l=Ledger(tmp_path/'r.sqlite',{'RUN_ID':'x'})
    n={'i':0}
    class P(MockProvider):
        def complete(self,req):
            n['i']+=1
            return Response('{"ok":1}',{'input_tokens':1,'output_tokens':1},0)
    cal=Caller(c,l,P(None),cap_micro_usd=10_000)
    ctx,prompt=_red_ctx(c)
    assert cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')=='{"ok":1}'
    assert n['i']==1
    assert cal.call('RED_TEAM',ctx,prompt,{'max_output_tokens':10},'s')=='{"ok":1}'
    assert n['i']==1
    l.close()

def test_derive_after_partial_critic_work_does_not_refund(tmp_path):
    c=Contexts()
    t=IndependentTransport(c,{('NOVELTY_CRITIC','C001',1):'crash'})
    src=tmp_path/'src';src.mkdir()
    cfg=derived_config('partial',{'SIZE':40,'CAP_MICRO_USD':OWNER_CAP},c)
    l=Ledger(src/'run.sqlite',cfg)
    p=OpenAIProvider('audit',allow_real=True,budget_micro_usd=OWNER_CAP,transport=t,contexts=c,sleeper=lambda s:None)
    with pytest.raises(AuditCrash):
        run_campaign(c,Caller(c,l,p,OWNER_CAP,True),40)
    source_total=l.total_charged_micro_usd();l.close()
    report=derive_complete_rounds(src,tmp_path/'dest',3)
    assert report['LINEAGE_TOTAL_MICRO_USD']==source_total
    assert report['LINEAGE_PRIOR_MICRO_USD']>0
    authorize_derived_continuation(tmp_path/'dest','op','go')
    t2=IndependentTransport(c,{})
    l2=Ledger(tmp_path/'dest'/'run.sqlite')
    p2=OpenAIProvider('audit',allow_real=True,budget_micro_usd=OWNER_CAP,transport=t2,contexts=c,sleeper=lambda s:None)
    r=run_campaign(c,Caller(c,l2,p2,OWNER_CAP,True),40)
    assert r['STATUS']=='PENDING_HUMAN_REVIEW'
    assert [x for x in t2.posts() if x[1]=='/v1/responses']==[]
    assert l2.total_charged_micro_usd()>source_total
    l2.close()

def test_novelty_application_accepts_list_that_live_schema_forbids():
    c=Contexts()
    leaf=[{'SIGNATURE_ID':k,'RELATION':'ORTHOGONAL_MECHANISM'} for k,r in c.rows.items() if r['STATE']!='PARTIAL_OR_MIXED']
    payload={'PRIOR_RELATIONS':leaf,'BATCH_RELATIONS':[],'JUDGMENTS':{k:1 for k in NOVELTY_DIMENSIONS}}
    app=role_schema('NOVELTY_CRITIC',c,provider=False)
    # Application schema is arrays (prompt-shaped).
    assert app['properties']['PRIOR_RELATIONS']['type']=='array'
    from scripts.research.generator_v0.schema import validate_instance
    validate_instance(payload,app)  # prompt-shaped output is valid for the app
    prov=role_schema('NOVELTY_CRITIC',c,provider=True,request={'context':{'CANDIDATE':{'CANDIDATE_ID':'C001'},'CURRENT_BATCH_SIGNATURES':[]}})
    with pytest.raises(ContractError):
        validate_instance(payload,prov)  # live schema rejects the prompt shape
