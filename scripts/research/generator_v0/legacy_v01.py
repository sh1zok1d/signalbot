"""Isolated compatibility layer for generator contract v0.1 (option A: grandfather).

Only the historical generation:0/1/2 calls listed in
docs/research/GENERATOR_V0_LEGACY_V01_GRANDFATHER.json may be admitted under
the frozen v0.1 validator (legacy_v01_schema.py), and only with the exact card
digests recorded there. Every other model output, including any new generation
and the discarded first-shadow-v7 generation:3, is judged by
GENERATOR_CONTRACT_V02 (contract.py). This module never widens what new output
may contain.
"""
from __future__ import annotations
import json
from functools import lru_cache
from .context import ROOT,ContractError,digest,read
from . import legacy_v01_schema

MANIFEST='docs/research/GENERATOR_V0_LEGACY_V01_GRANDFATHER.json'
CONTRACT_ID='GENERATOR_CONTRACT_V01_LEGACY'
PROMPT_VERSION='generator-v0.1'
MAX_OUTPUT_TOKENS=32768
PROVIDER='OPENAI_RESPONSES'
# Verbatim pre-repair GENERATOR_PROMPT (first-shadow v5-v7).
PROMPT='''Return JSON with exactly CANDIDATES: an array containing one card for each supplied slot. Match slot CANDIDATE_ID, MECHANISM_FAMILY and INFORMATION_SOURCE exactly. Each card has exactly the 27 required schema fields. DATA_REQUIRED is a nonempty list of objects with DATASET, OBSERVABLE, STATUS, LEGAL_RANGE strings. DATA_STATUS is an aggregate enum present among those requirements. MISSING_OBSERVABLES is a string list. SEARCH_SURFACE is {PARAMETERS: {parameter_name: [explicit_values]}, MAX_VARIANTS: integer}, the product of list lengths must fit MAX_VARIANTS (1..100). PROTECTED_DATA_REQUIREMENT is false. Other fields are nonempty strings. NEAREST_TESTED_MECHANISM is a prior signature ID or NONE. DATA_GAP_CLASS is NONE for ready cards or a named missing-data class. Propose bounded mechanistic questions, falsifiers and null models. Data-blocked ideas are wanted. No self-grading or success estimates. Use public-time semantics and legal ranges in the catalog. Slot assignments are neutral batch-diversity instructions, not historical research evidence. No tools, market execution or acquisition.'''

GRANDFATHERED_SLOTS=('generation:0','generation:1','generation:2')
SOURCE_JOURNAL='docs/research/generator_v0_first_shadow_v7/run.sqlite'

def build_manifest(journal,contexts):
    """Recompute the grandfather manifest from the sealed v7 journal, read-only."""
    import hashlib,sqlite3
    from pathlib import Path
    path=Path(journal).resolve()
    db=sqlite3.connect('file:{}?mode=ro'.format(path.as_posix()),uri=True)
    try:
        config=json.loads(db.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
        calls=[];excluded=[]
        for key,request,state,response,cost in db.execute('SELECT key,request,state,response,cost FROM calls ORDER BY rowid'):
            req=json.loads(request);resp=json.loads(response) if response else {}
            if req.get('role')!='GENERATOR':continue
            if req['slot'] not in GRANDFATHERED_SLOTS:
                excluded.append({'SLOT':req['slot'],'CALL_KEY':key,'STATE':state,'REASON':'not grandfathered; judged only under GENERATOR_CONTRACT_V02'})
                continue
            if state!='COMPLETE' or req['prompt']!=PROMPT or req['prompt_version']!=PROMPT_VERSION:raise ContractError('journal row is not a v0.1 COMPLETE generator call')
            cards=json.loads(resp['raw'])['CANDIDATES']
            calls.append({'SLOT':req['slot'],'CALL_KEY':key,'RESPONSE_ID':resp['response_id'],'RAW_RESPONSE_SHA256':resp['raw_sha256'],
                          'COST_MICRO_USD':cost,'CARD_DIGESTS':{c['CANDIDATE_ID']:digest(c) for c in cards}})
    finally:
        db.close()
    if config['GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST']!=schema_digest(contexts):raise ContractError('legacy schema digest drift')
    return {
        'CONTRACT':CONTRACT_ID,'DECISION':'A_GRANDFATHER_ONLY_LISTED_CALL_KEYS',
        'PROMPT_VERSION':PROMPT_VERSION,'PROMPT_SHA256':hashlib.sha256(PROMPT.encode()).hexdigest(),
        'STRUCTURED_OUTPUT_SCHEMA_DIGEST':schema_digest(contexts),
        'SOURCE_JOURNAL':SOURCE_JOURNAL,'SOURCE_JOURNAL_SHA256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'CALLS':calls,'EXCLUDED_CALLS':excluded,
        'RULE':'Legacy v0.1 validation applies only to these call keys and exact card digests. New model output never uses it.',
    }

def schema_digest(contexts):
    """Digest of the frozen v0.1 strict provider schema (recorded in v5-v7 configs)."""
    s=legacy_v01_schema
    return digest(s.strict_object({'CANDIDATES':{'type':'array','minItems':1,'maxItems':50,'items':s.output_schema(contexts,provider=True)}}))

def expected_request(contexts,slots,round_n,model,model_request_params):
    return {
        'role':'GENERATOR','context':contexts.generator(),'prompt':PROMPT,'prompt_version':PROMPT_VERSION,
        'parameters':{'max_output_tokens':MAX_OUTPUT_TOKENS,'slots':list(slots)},
        'provider':PROVIDER,'model':model,'slot':'generation:'+str(round_n),'model_request_params':model_request_params,
    }

@lru_cache(maxsize=4)
def _manifest(root=str(ROOT)):
    from pathlib import Path
    m=read(Path(root)/MANIFEST)
    if m.get('CONTRACT')!=CONTRACT_ID or m.get('DECISION')!='A_GRANDFATHER_ONLY_LISTED_CALL_KEYS':raise ContractError('grandfather manifest identity')
    return m

def manifest():
    return json.loads(json.dumps(_manifest()))

def grandfathered_calls():
    return {row['CALL_KEY']:row for row in _manifest()['CALLS']}

def grandfathered_card_digests():
    return {d for row in _manifest()['CALLS'] for d in row['CARD_DIGESTS'].values()}

def is_grandfathered_call(key):
    return key in grandfathered_calls()

def admit_card(card,contexts,call_key):
    """Admit one historical card: call key listed, card digest exact, v0.1 validator passes."""
    row=grandfathered_calls().get(call_key)
    if row is None:raise ContractError('call key is not grandfathered')
    cid=card.get('CANDIDATE_ID') if isinstance(card,dict) else None
    if row['CARD_DIGESTS'].get(cid)!=digest(card):raise ContractError('card differs from grandfathered digest')
    legacy_v01_schema.validate_card(card,contexts)
    return card

def admitted_by_digest(card,contexts):
    """Downstream re-check for a card already admitted at intake."""
    if not isinstance(card,dict) or digest(card) not in grandfathered_card_digests():return False
    legacy_v01_schema.validate_card(card,contexts)
    return True
