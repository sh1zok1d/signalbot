"""A campaign ends at human review; no research execution hooks exist."""
from __future__ import annotations
import json
from collections import Counter
from .context import ContractError,canonical,digest
from .schema import parse_json,validate_card
from .roles import Roles,SELECTOR_PROMPT,exact
from .mock import slot_plan
from .ledger import data_gaps
from .models import GENERATOR_MAX_OUTPUT_TOKENS

GENERATOR_PROMPT='''Return JSON with exactly CANDIDATES: an array containing one card for each supplied slot. Match slot CANDIDATE_ID, MECHANISM_FAMILY and INFORMATION_SOURCE exactly. Each card has exactly the 27 required schema fields. DATA_REQUIRED is a nonempty list of objects with DATASET, OBSERVABLE, STATUS, LEGAL_RANGE strings. DATA_STATUS is an aggregate enum present among those requirements. MISSING_OBSERVABLES is a string list. SEARCH_SURFACE is {PARAMETERS: {parameter_name: [explicit_values]}, MAX_VARIANTS: integer}, the product of list lengths must fit MAX_VARIANTS (1..100). PROTECTED_DATA_REQUIREMENT is false. Other fields are nonempty strings. NEAREST_TESTED_MECHANISM is a prior signature ID or NONE. DATA_GAP_CLASS is NONE for ready cards or a named missing-data class. Propose bounded mechanistic questions, falsifiers and null models. Data-blocked ideas are wanted. No self-grading or success estimates. Use public-time semantics and legal ranges in the catalog. Slot assignments are neutral batch-diversity instructions, not historical research evidence. No tools, market execution or acquisition.'''

def diversity(cards,c):
    if not 25<=len(cards)<=50:raise ContractError('batch size outside frozen bounds')
    ids=[x['CANDIDATE_ID'] for x in cards]
    if len(set(ids))!=len(ids):raise ContractError('duplicate candidate IDs')
    counts=Counter(x['MECHANISM_FAMILY'] for x in cards)
    if any(counts[k]>5 for k in c.families):raise ContractError('family cap')
    if counts['NEW_FAMILY_PROPOSAL']<8:raise ContractError('new-family attempts missing')
    if len({x['INFORMATION_SOURCE'] for x in cards})<6:raise ContractError('source diversity')

def run_campaign(c,caller,size=40):
    ledger=caller.ledger
    if ledger.get('status')=='MUTATED_REQUIRES_REVIEW':raise ContractError('human mutation invalidated prior decisions; review explicitly')
    existing=ledger.db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone()
    if existing:return json.loads(existing[0])
    if type(size)!=int or not 25<=size<=50:raise ContractError('invalid batch size')
    cards=[]
    plan=slot_plan(size)
    for round_n,start in enumerate(range(0,size,10)):
        slots=plan[start:start+10]
        raw=caller.call('GENERATOR',c.generator(),GENERATOR_PROMPT,{'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':slots},'generation:'+str(round_n))
        parsed=parse_json(raw);exact(parsed,{'CANDIDATES'})
        batch=parsed['CANDIDATES']
        if not isinstance(batch,list) or len(batch)!=len(slots):raise ContractError('wrong generation round size')
        for card,slot in zip(batch,slots):
            validate_card(card,c)
            if any(card[k]!=v for k,v in slot.items()):raise ContractError('slot assignment mismatch')
        cards.extend(batch)
    diversity(cards,c)
    roles=Roles(c,caller);reviews=[];sanitized=[];selection={};streams=[]
    for card in cards:
        n=roles.novelty(card,cards);f=roles.feasibility(card);r=roles.red_team(card)
        route=roles.route(n,f,r)
        judgments=n['JUDGMENTS']|f['JUDGMENTS']|r['JUDGMENTS']
        exact(judgments,c.design['GENERATOR_EVALUATION_CRITERIA']['PER_CANDIDATE_DIMENSIONS'])
        review={'CANDIDATE_ID':card['CANDIDATE_ID'],'NOVELTY':n,'FEASIBILITY':f,'RED_TEAM':r,'ORDINAL_JUDGMENTS':judgments,'STREAM':route}
        reviews.append(review)
    # A near-duplicate relation reported in either direction excludes the later ID.
    # Do this only after all critics have answered, so order cannot hide asymmetry.
    duplicate_later=set()
    for review in reviews:
        cid=review['CANDIDATE_ID']
        for relation in review['NOVELTY']['BATCH_RELATIONS']:
            if relation['RELATION']!='ORTHOGONAL_MECHANISM':
                duplicate_later.add(max(cid,relation['CANDIDATE_ID']))
    for card,review in zip(cards,reviews):
        n,f,r=review['NOVELTY'],review['FEASIBILITY'],review['RED_TEAM']
        if card['CANDIDATE_ID'] in duplicate_later:
            n['VERDICT']='REJECT'
            review['STREAM']='NOT_A_STREAM'
        route=review['STREAM'];judgments=review['ORDINAL_JUDGMENTS']
        if route!='NOT_A_STREAM':
            sanitized.append(roles.sanitize(card,n,f,r));streams.append((card,route))
            selection[card['CANDIDATE_ID']]={'MECHANISM_DISTANCE':judgments['MECHANISM_DISTANCE'],'INFORMATION_GAIN':judgments['NULL_INFORMATION_GAIN'],'FEASIBILITY':f['FEASIBILITY'],'CHEAPNESS':f['CHEAPNESS']}
    ctx={'SANITIZED_CRITIC_OUTPUTS':sanitized,'DATA_STATUS':{x['CANDIDATE_ID']:x['DATA_STATUS'] for x in sanitized},'SELECTION_JUDGMENTS':selection}
    # Deterministic ordinal ordering is authoritative; provider selection is checked.
    order=sorted(selection,key=lambda k:tuple(-selection[k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))
    if order:
        proposal=parse_json(caller.call('SELECTOR',ctx,SELECTOR_PROMPT,{'max_output_tokens':2000},'selection'))
        exact(proposal,{'ORDERED_CANDIDATE_IDS'})
        if proposal['ORDERED_CANDIDATE_IDS']!=order:raise ContractError('selector violates deterministic ordinal order')
    gaps=data_gaps([card for card,stream in streams if stream=='HIGH_VALUE_DATA_BLOCKED'])
    result={'STATUS':'PENDING_HUMAN_REVIEW','EVIDENCE_KIND':'INFRASTRUCTURE_ONLY' if not caller.provider.real else 'UNEXECUTED_SHADOW_IDEATION','CANDIDATES':cards,'REVIEWS':reviews,'STREAM_A':[card['CANDIDATE_ID'] for card,stream in streams if stream=='EXECUTABLE_NOW'],'STREAM_B':[card['CANDIDATE_ID'] for card,stream in streams if stream=='HIGH_VALUE_DATA_BLOCKED'],'SHORTLIST':order[:5],'DATA_GAP_LEDGER_V0':gaps,'SELECTION_JUDGMENTS':selection}
    result['SEMANTIC_RESULT_DIGEST']=digest(result)
    with ledger.transaction():
        for card,review in zip(cards,reviews):ledger.save_card(card,review)
        ledger.db.execute('INSERT INTO results VALUES (?,?)',('campaign',canonical(result)))
        ledger.set('status','PENDING_HUMAN_REVIEW')
    return result
