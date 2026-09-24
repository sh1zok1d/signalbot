"""Budget / run-shape decision support (offline). Reports scenarios; chooses none.

Every number is a worst-case reservation through the live bound() path
(input bound = serialized request bytes + 1024 tokens; output = max tokens;
cost = rate x tokens, rounded up). No POST, no journal is written except a
temporary derived copy of the v7 lineage in a scratch directory.
"""
from __future__ import annotations
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from scripts.research.generator_v0.context import Contexts,canonical
from scripts.research.generator_v0.derive import (campaign_bound,derive_complete_rounds,remaining_campaign_budget_preflight,
    fresh_campaign_budget_preflight,OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,PROXY_CARD_MARGIN,OBSERVED_MAX_CARD_BYTES,OBSERVED_MAX_SIGNATURE_BYTES)
from scripts.research.generator_v0.models import ROLE_OUTPUT_TOKEN_CAPS
from scripts.research.generator_v0.roles import Roles,RELATIONS,BATCH_RELATIONS
from scripts.research.generator_v0.mock import fixture,slot_plan

REPO=Path(__file__).resolve().parents[3]
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'
REPORT=REPO/'docs/research/generator_v0_repair/BUDGET_SCENARIOS.json'
V7_LINEAGE_MICRO_USD=4_946_750
REASONING_ALLOWANCES=(2000,4000,6000)   # unobserved for critics: no paid critic call has ever completed

def usd(micro):return str((Decimal(micro)/Decimal(1_000_000)).quantize(Decimal('0.000001')))

def max_keyed_novelty_response_bytes(contexts,size=40):
    """Largest possible visible novelty answer: every key present with the longest relation."""
    cards=[fixture(s,contexts) for s in slot_plan(size)]
    ctx=Roles(contexts,None).request('NOVELTY_CRITIC',cards[0],cards)
    leaf=sorted(k for k,r in contexts.rows.items() if r['STATE']!='PARTIAL_OR_MIXED')
    longest=max(RELATIONS,key=len);longest_b=max(BATCH_RELATIONS,key=len)
    others=[x['CANDIDATE_ID'] for x in cards[1:]]
    payload={'PRIOR_RELATIONS':{k:longest for k in leaf},'BATCH_RELATIONS':{k:longest_b for k in others},'JUDGMENTS':{'NOVELTY':3,'MECHANISM_DISTANCE':3,'NON_RESCUE':3}}
    # Pretty-printed worst case: the model may emit whitespace; count 4 bytes of indentation per line.
    compact=len(canonical(payload).encode())
    return {'COMPACT_BYTES':compact,'WITH_WHITESPACE_BYTES':compact+4*(len(leaf)+len(others)+8),'PRIOR_KEYS':len(leaf),'BATCH_KEYS':len(others)}

def _row(label,kind,size,b,prior,note):
    single=b['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD'];retry=b['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD']
    remaining=OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD-prior
    return {'SCENARIO':label,'CHANGE_KIND':kind,'SIZE':size,'CAPS':b['CAPS'],'CONTENT_ATTEMPTS':b['CONTENT_ATTEMPTS'],
            'LINEAGE_PRIOR_USD':usd(prior),'WORST_CASE_SINGLE_ATTEMPT_USD':usd(single),'WORST_CASE_WITH_CONTENT_RETRIES_USD':usd(retry),
            'MIN_CEILING_JOURNAL_ONLY_USD':usd(retry if b['CONTENT_ATTEMPTS']>1 else single),
            'MIN_CEILING_CAMPAIGN_CUMULATIVE_USD':usd(prior+(retry if b['CONTENT_ATTEMPTS']>1 else single)),
            'FITS_OWNER_17_10_CUMULATIVE':(retry if b['CONTENT_ATTEMPTS']>1 else single)<=remaining,
            'STAGES':{s['STAGE']:s['BOUND_USD'] for s in b['STAGES']},'NOTE':note}

def build(contexts=None,v7_contexts=None):
    # Scenarios A-E are decision support for the first-shadow-v7 lineage, which ran under the
    # pre-GV0CAL memory (memory-chain event LEGACY_BOOTSTRAP). The routed section is a fresh run
    # and uses the current memory head.
    current=contexts or Contexts()
    c=v7_contexts or Contexts(memory_event='LEGACY_BOOTSTRAP')
    caps=dict(ROLE_OUTPUT_TOKEN_CAPS)
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);(tmp/'v7').mkdir();shutil.copy(V7,tmp/'v7'/'run.sqlite')
        report=derive_complete_rounds(tmp/'v7',tmp/'v8',2,c)
        from scripts.research.generator_v0.ledger import Ledger
        from scripts.research.generator_v0.runner import round_cards
        l=Ledger.open_readonly(tmp/'v8'/'run.sqlite')
        try:
            known=[];done=[]
            for slot,row in sorted((l.get('imported_rounds') or {}).items()):
                known+=round_cards(l.complete_raw(row['CALL_KEY']),row['CONTRACT']);done.append(int(slot.split(':')[1]))
        finally:l.close()
        derived_pre=remaining_campaign_budget_preflight(tmp/'v8',c)
    lineage=report['LINEAGE_TOTAL_MICRO_USD']
    assert lineage==V7_LINEAGE_MICRO_USD
    def fresh(size=40,caps_=caps,attempts=None):return campaign_bound(c,size,(),(),caps_,attempts)
    def derived(caps_=caps,attempts=None):return campaign_bound(c,40,known,done,caps_,attempts)
    rows=[]
    note_fresh='Fresh 40-slot run, every card a documented proxy. Campaign-cumulative adds the v7 lineage only if the owner counts a fresh run against the same USD 17.10 campaign authority.'
    note_derived='v7-derived continuation (generation:0-2 imported, generation:3 and all critics remaining).'
    rows.append(_row('A_CURRENT_FRESH','NONE',40,fresh(),0,note_fresh))
    rows.append(_row('A_CURRENT_FRESH_COUNTED_IN_V7_CAMPAIGN','NONE',40,fresh(),lineage,note_fresh))
    rows.append(_row('A_CURRENT_V7_DERIVED','NONE',40,derived(),lineage,note_derived))
    rows.append(_row('B_NO_CONTENT_RETRIES_FRESH','OPERATIONAL (MAX_CONTENT_ATTEMPTS=1; more REVIEW_FAILED/HARD_FAIL risk, no scientific change)',40,fresh(attempts=1),0,note_fresh))
    rows.append(_row('B_NO_CONTENT_RETRIES_V7_DERIVED','OPERATIONAL (MAX_CONTENT_ATTEMPTS=1; more REVIEW_FAILED/HARD_FAIL risk, no scientific change)',40,derived(attempts=1),lineage,note_derived))
    nov=max_keyed_novelty_response_bytes(c)
    visible=nov['WITH_WHITESPACE_BYTES']    # tokens <= bytes for this ASCII JSON
    for allowance in REASONING_ALLOWANCES:
        cap_n=((visible+allowance+499)//500)*500
        if cap_n>=caps['NOVELTY_CRITIC']:continue
        cc=dict(caps,NOVELTY_CRITIC=cap_n)
        kind='OPERATIONAL (novelty cap {} = visible bound {} + reasoning allowance {}, rounded up to 500; critic reasoning usage is unobserved, a length stop is a billed failure and may end REVIEW_FAILED)'.format(cap_n,visible,allowance)
        for attempts in (None,1):
            tag='C_NOVELTY_CAP_{}{}'.format(cap_n,'_NO_RETRIES' if attempts==1 else '')
            rows.append(_row(tag+'_FRESH',kind,40,fresh(caps_=cc,attempts=attempts),0,note_fresh))
            rows.append(_row(tag+'_V7_DERIVED',kind,40,derived(caps_=cc,attempts=attempts),lineage,note_derived))
    for size in (25,30):
        kind='DESIGN_CHANGE (batch size {}; requires an outcome-blind design amendment before use; not applicable to the v7-derived run, whose imported slots follow the 40-slot plan and would leave no NEW_FAMILY_PROPOSAL slots)'.format(size)
        rows.append(_row('D_BATCH_{}_FRESH'.format(size),kind,size,fresh(size=size),0,note_fresh))
        rows.append(_row('D_BATCH_{}_FRESH_NO_RETRIES'.format(size),kind,size,fresh(size=size,attempts=1),0,note_fresh))
    return {
        'UNIT':'GENERATOR_V0_LIMITED_REPAIR_BUDGET_SCENARIOS','DECISION':'NONE_TAKEN (owner decision)',
        'OWNER_AUTHORIZED_CAMPAIGN_CAP_USD':usd(OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD),
        'V7_LINEAGE':{'IMPORTED_MICRO_USD':report['IMPORTED_COST_MICRO_USD'],'PRIOR_MICRO_USD':report['LINEAGE_PRIOR_MICRO_USD'],'TOTAL_MICRO_USD':lineage,
                      'REMAINING_UNDER_17_10_MICRO_USD':OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD-lineage},
        'PROXY_RULE':{'OBSERVED_MAX_CARD_BYTES':OBSERVED_MAX_CARD_BYTES,'OBSERVED_MAX_SIGNATURE_BYTES':OBSERVED_MAX_SIGNATURE_BYTES,'MARGIN':str(PROXY_CARD_MARGIN),
                      'SOURCE':'largest serialized card / novelty signature among the 40 tracked first-shadow-v7 cards (recomputed by a test)'},
        'NOVELTY_VISIBLE_RESPONSE_BOUND':nov,
        'DERIVED_PREFLIGHT_CROSSCHECK_MICRO_USD':derived_pre['WORST_CASE_REMAINING_MICRO_USD'],
        'SCENARIOS':rows,
        'E_MINIMUM_ABSOLUTE_CEILING':{r['SCENARIO']:{'JOURNAL_ONLY_USD':r['MIN_CEILING_JOURNAL_ONLY_USD'],'CAMPAIGN_CUMULATIVE_USD':r['MIN_CEILING_CAMPAIGN_CUMULATIVE_USD']} for r in rows},
        'NOTES':['Worst cases bound every call at its maximum output; realized v7 generator spend was about 65 percent of its bound.',
                 'No paid critic call has ever completed, so critic reasoning usage is unobserved; scenario C caps are not validated against real outputs.',
                 'NOT_BILLED transport retries charge 0 and are excluded.'],
        'ROUTED_MULTI_PROVIDER':build_routed(current),
        'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,'PROTECTED_2025_2026_OPENED':False,
    }

ROLE_STAGE={'GENERATOR':'generation:','NOVELTY_CRITIC':'NOVELTY_CRITIC','FEASIBILITY_CRITIC':'FEASIBILITY_CRITIC','RED_TEAM':'RED_TEAM','SELECTOR':'SELECTOR'}

def build_routed(contexts=None):
    """Worst-case bounds for the multi-provider routing (fresh 40-card run). Decision support only."""
    from scripts.research.generator_v0.routed_provider import offline_routed_provider
    from scripts.research.generator_v0 import routing
    c=contexts or Contexts()
    provider=offline_routed_provider(c)
    single=campaign_bound(c,40,(),(),None,1,None,provider)
    retries=campaign_bound(c,40,(),(),None,None,None,provider)
    by_role={}
    for role,prefix in ROLE_STAGE.items():
        r=routing.ROUTES[role]
        micro=sum(s['BOUND_MICRO_USD'] for s in single['STAGES'] if s['STAGE'].startswith(prefix))
        by_role[role]={'ROUTE':'{} / {} / {}'.format(r['PROVIDER'],r['MODEL'],'/'.join('{}={}'.format(k,v) for k,v in r['PARAMS'].items())),
                       'WORST_CASE_SINGLE_ATTEMPT_USD':usd(micro),'CALLS':4 if role=='GENERATOR' else (1 if role=='SELECTOR' else 40)}
    total=single['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD'];with_retries=retries['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD']
    return {
        'ROUTING_ID':routing.ROUTING_ID,'ROUTING_DIGEST':routing.routing_digest(),'ROUTING_TABLE':routing.routing_table(),
        'PRICE_TABLE':routing.price_table(),
        'FRESH_40_CARD_SINGLE_ATTEMPT_USD':usd(total),'FRESH_40_CARD_WITH_CONTENT_RETRIES_USD':usd(with_retries),
        'BY_ROLE_SINGLE_ATTEMPT':by_role,'STAGES':{s['STAGE']:s['BOUND_USD'] for s in single['STAGES']},
        'FITS_OWNER_17_10_FRESH_SINGLE_ATTEMPT':total<=OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,
        'FITS_OWNER_17_10_FRESH_WITH_RETRIES':with_retries<=OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,
        'CAMPAIGN_CUMULATIVE_IF_COUNTED_IN_V7_AUTHORITY_USD':usd(V7_LINEAGE_MICRO_USD+total),
        'V7_DERIVED_ROUTED_RUN':'NOT_APPLICABLE: v7 generation:0-2 were produced by gpt-6-astra under the grandfathered v0.1 contract; continuing them with an Opus generator would mix generator models inside one batch, and derive of routed journals is not implemented.',
        'CALIBRATION_TARGET':{'TARGET_EXPECTED_FULL_40_CARD_RUN_USD':'10','TARGET_4_RUN_MONTH_USD':'40',
                              'NOTE':'Product/cost targets for later empirical 5-card calibration; not authorization to weaken gates or change the design.'},
        'NOTES':['Worst-case reservation bounds (max output on every call, input bound = request bytes + margin), not expected cost.',
                 'Anthropic input bound adds a fixed 4096-token provider-scaffolding margin; no cache or batch discount is used anywhere.',
                 'Deferred: Anthropic/OpenAI Batch, prompt caching, Opus second opinion, adaptive critic routing, batch-size change.'],
        'REAL_LLM_CALLS_MADE':False,
    }

def main():
    r=build();REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(r,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    for row in r['SCENARIOS']:print(row['SCENARIO'],row['WORST_CASE_SINGLE_ATTEMPT_USD'],row['WORST_CASE_WITH_CONTENT_RETRIES_USD'],row['MIN_CEILING_CAMPAIGN_CUMULATIVE_USD'],row['FITS_OWNER_17_10_CUMULATIVE'])

if __name__=='__main__':
    main()
