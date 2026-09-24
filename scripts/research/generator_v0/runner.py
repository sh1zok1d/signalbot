"""A campaign ends at human review; no research execution hooks exist.

Error model (GENERATOR_CONTRACT_V02, pre-live repair):
- A model-content error damages one candidate, never the campaign. A card that
  breaks the contract is recorded HARD_FAIL; a critic answer that breaks its
  contract twice (or a billed unusable answer twice) makes that card
  REVIEW_FAILED. Both stay visible in the ledger and the result metrics.
- Campaign-level stops are limited to: budget authority (STOPPED_BUDGET),
  uncertain provider state awaiting reconciliation (PAUSED_UNCERTAIN_CALL),
  provider throttling or rejection (PAUSED_PROVIDER_*), integrity errors, and
  fewer than MIN_VALID_CANDIDATES admissible cards (STOPPED_INSUFFICIENT_VALID).
- The deterministic ordinal order is authoritative. The selector call is
  advisory: disagreement or unavailability is recorded, never fatal.
"""
from __future__ import annotations
import json
from collections import Counter
from .context import ContractError,canonical,digest
from .schema import parse_json,validate_instance,output_schema,decode_provider_card
from .roles import Roles,SELECTOR_PROMPT,RoleContractError,exact
from .mock import slot_plan
from .ledger import data_gaps,BudgetExceeded,CallUncertain,InfrastructureStop
from .models import GENERATOR_MAX_OUTPUT_TOKENS,ROLE_OUTPUT_TOKEN_CAPS
from .provider import BilledFailure,ProviderThrottled,ProviderRejected,BackgroundPending
from .output_schemas import (generator_round_schema_digest,generator_wire_format,
                             ANTHROPIC_GENERATOR_WIRE_FORMAT,KEYED_GENERATOR_WIRE_FORMAT)
from . import contract,legacy_v01

GENERATOR_PROMPT=contract.generator_prompt()
MIN_VALID_CANDIDATES=25
MAX_CONTENT_ATTEMPTS=2
RESUMABLE_STATUSES=('CREATED','DERIVED_CONTINUATION_AUTHORIZED','PAUSED_UNCERTAIN_CALL','PAUSED_PROVIDER_THROTTLED','PAUSED_PROVIDER_REJECTED','PAUSED_BACKGROUND_PENDING','STOPPED_BUDGET')
TERMINAL_STATUSES=('PENDING_HUMAN_REVIEW','STOPPED_INSUFFICIENT_VALID')
_PAUSE={BudgetExceeded:'STOPPED_BUDGET',CallUncertain:'PAUSED_UNCERTAIN_CALL',ProviderThrottled:'PAUSED_PROVIDER_THROTTLED',
        ProviderRejected:'PAUSED_PROVIDER_REJECTED',BackgroundPending:'PAUSED_BACKGROUND_PENDING'}

def diversity(cards,c):
    """Frozen batch diversity controls. Applied to the attempted slot plan."""
    if not 25<=len(cards)<=50:raise ContractError('batch size outside frozen bounds')
    ids=[x['CANDIDATE_ID'] for x in cards]
    if len(set(ids))!=len(ids):raise ContractError('duplicate candidate IDs')
    counts=Counter(x['MECHANISM_FAMILY'] for x in cards)
    if any(counts[k]>5 for k in c.families):raise ContractError('family cap')
    if counts['NEW_FAMILY_PROPOSAL']<8:raise ContractError('new-family attempts missing')
    if len({x['INFORMATION_SOURCE'] for x in cards})<6:raise ContractError('source diversity')

def generator_identity(c,slots):
    return {'output_contract':contract.CONTRACT_ID,'output_schema_digest':generator_round_schema_digest(c,slots)}

def generator_max_output_tokens(provider=None):
    """The routed provider's GENERATOR route cap; the legacy OpenAI/mock cap otherwise."""
    fn=getattr(provider,'max_output_tokens_for',None)
    return fn('GENERATOR') if fn is not None else GENERATOR_MAX_OUTPUT_TOKENS

def generator_request_parameters(slots,max_output_tokens=GENERATOR_MAX_OUTPUT_TOKENS):
    return {'max_output_tokens':max_output_tokens,'slots':list(slots)}

class CompactRound(list):
    """Anthropic compact wire output: provider-encoded items in returned order.
    Nothing in it is trusted; intake binds each item to a slot by its own
    CANDIDATE_ID and applies that slot's exact provider schema and V02 rules."""

def parse_round(raw,contract_id=contract.CONTRACT_ID,wire=KEYED_GENERATOR_WIRE_FORMAT):
    """Generator output -> cards, or None if unusable as a round.

    V02 keyed wire: the provider-keyed object {'CANDIDATES': {slot_id: card}}
    exactly as decoded (a list is unusable). V02 Anthropic compact wire:
    {'CANDIDATES': [card, ...]} as a CompactRound (an object is unusable).
    Cards stay in provider encoding; intake checks each against its slot's
    strict provider schema before the V02 rules.
    Legacy v0.1 (grandfathered imports only): the stored list form."""
    try:payload=parse_json(raw)
    except ContractError:return None
    if not isinstance(payload,dict) or set(payload)!={'CANDIDATES'}:return None
    cards=payload['CANDIDATES']
    if contract_id==legacy_v01.CONTRACT_ID:return cards if isinstance(cards,list) else None
    if wire==ANTHROPIC_GENERATOR_WIRE_FORMAT:return CompactRound(cards) if isinstance(cards,list) else None
    if wire!=KEYED_GENERATOR_WIRE_FORMAT:raise ContractError('unknown generator wire format')
    return cards if isinstance(cards,dict) else None

def slot_violations_v02(card,c,slot):
    """V02 per-slot check of a provider-keyed card: its slot's strict provider
    schema first, then the contract rules. Returns (violations, application card)."""
    try:
        validate_instance(card,output_schema(c,provider=True,slot=slot))
        card=decode_provider_card(card)
    except ContractError as e:return [{'RULE':'PROVIDER_SCHEMA','DETAIL':str(e)}],card
    return contract.card_violations(card,c,slot),card

def round_cards(raw,contract_id=contract.CONTRACT_ID,wire=KEYED_GENERATOR_WIRE_FORMAT):
    """Parsed round as a list of application cards (summaries, preflight); None if unusable."""
    cards=parse_round(raw,contract_id,wire)
    if cards is None:return None
    if isinstance(cards,CompactRound):
        out=[]
        for v in cards:
            try:out.append(decode_provider_card(v))
            except ContractError:out.append(v)
        return out
    if isinstance(cards,list):return cards
    out=[]
    for k,v in cards.items():
        try:out.append(decode_provider_card(v))
        except ContractError:out.append(v if isinstance(v,dict) else {'CANDIDATE_ID':k})
    return out

def call_wire_format(ledger,key):
    """Generator wire format recorded in the journaled request of call key."""
    row=ledger.db.execute('SELECT request FROM calls WHERE key=?',(key,)).fetchone() if key else None
    return generator_wire_format(json.loads(row[0]) if row else None)

def contract_of_request(request):
    return legacy_v01.CONTRACT_ID if request.get('prompt_version')==legacy_v01.PROMPT_VERSION else contract.CONTRACT_ID

def _round_output(c,ledger,caller,round_n,slots):
    """(contract, call_key, cards or None, failure reasons)."""
    slot_id='generation:'+str(round_n)
    imported=(ledger.get('imported_rounds') or {}).get(slot_id)
    if imported:
        return imported['CONTRACT'],imported['CALL_KEY'],parse_round(ledger.complete_raw(imported['CALL_KEY']),imported['CONTRACT'],call_wire_format(ledger,imported['CALL_KEY'])),['imported output is not a usable round']
    reasons=[];key=None
    for attempt in range(MAX_CONTENT_ATTEMPTS):
        try:
            raw=caller.call('GENERATOR',c.generator(),GENERATOR_PROMPT,generator_request_parameters(slots,generator_max_output_tokens(caller.provider)),slot_id,content_attempt=attempt,identity=generator_identity(c,slots))
        except BilledFailure as e:
            reasons.append('attempt '+str(attempt)+': '+str(e));key=caller.last_key;continue
        key=caller.last_key
        cards=parse_round(raw,contract.CONTRACT_ID,call_wire_format(ledger,key))
        if cards is not None:return contract.CONTRACT_ID,key,cards,reasons
        reasons.append('attempt '+str(attempt)+': unusable generation output')
    return contract.CONTRACT_ID,key,None,reasons

def _intake_round(c,ledger,round_n,slots,contract_id,key,cards,failure):
    """Per-slot VALID/HARD_FAIL. Returns admitted cards in slot order.

    cards is either the V02 provider-keyed object (slot ID -> provider-encoded
    card; duplicate IDs cannot exist) or a list of application cards (legacy
    imports and synthetic tests), or a CompactRound (Anthropic compact wire:
    provider-encoded items bound to a slot only by their own CANDIDATE_ID and
    then checked against that slot's exact provider schema, like keyed cards)."""
    slot_id='generation:'+str(round_n)
    by_id={};dupes=set();extras=[];malformed=[];compact=isinstance(cards,CompactRound)
    keyed=isinstance(cards,dict) or compact
    wanted={s['CANDIDATE_ID'] for s in slots}
    if compact:
        pairs=[]
        for i,item in enumerate(cards):
            k=item.get('CANDIDATE_ID') if isinstance(item,dict) else None
            if not isinstance(k,str):malformed.append(i);continue
            pairs.append((k,item))
    else:
        pairs=cards.items() if keyed else ((c.get('CANDIDATE_ID') if isinstance(c,dict) else None,c) for c in cards or [])
    for k,card in pairs:
        if k not in wanted:extras.append(k);continue
        if k in by_id:dupes.add(k)
        by_id[k]=card
    admitted=[]
    for slot in slots:
        cid=slot['CANDIDATE_ID'];card=by_id.get(cid)
        if cards is None:state,reasons,card='HARD_FAIL',[{'RULE':'GENERATION_OUTPUT','DETAIL':'; '.join(failure) or 'no usable output'}],None
        elif cid in dupes:state,reasons,card='HARD_FAIL',[{'RULE':'SLOT_IDENTITY','DETAIL':'duplicate card for slot'}],None
        elif card is None:state,reasons='HARD_FAIL',[{'RULE':'SLOT_IDENTITY','DETAIL':'missing card for slot'}]
        elif contract_id==legacy_v01.CONTRACT_ID:
            try:legacy_v01.admit_card(card,c,key);state,reasons='VALID',[]
            except ContractError as e:state,reasons='HARD_FAIL',[{'RULE':'LEGACY_V01','DETAIL':str(e)}]
        else:
            if keyed:reasons,card=slot_violations_v02(card,c,slot)
            else:reasons=contract.card_violations(card,c,slot)
            state='HARD_FAIL' if reasons else 'VALID'
        ledger.record_candidate(cid,slot_id,key,contract_id,state,card,reasons)
        if state=='VALID':admitted.append(card)
    if extras:
        with ledger.transaction():ledger.event('EXTRA_GENERATED_CARDS_IGNORED',{'ROUND':slot_id,'CALL_KEY':key,'CANDIDATE_IDS':sorted(map(str,extras))})
    if malformed:
        with ledger.transaction():ledger.event('MALFORMED_GENERATED_ITEMS_IGNORED',{'ROUND':slot_id,'CALL_KEY':key,'ITEM_INDEXES':malformed})
    return admitted

def _review(roles,card,batch,stats):
    """Run the three critics with bounded content retries. Returns (review, failure)."""
    out={}
    for name,fn in (('NOVELTY',lambda a:roles.novelty(card,batch,a)),('FEASIBILITY',lambda a:roles.feasibility(card,a)),('RED_TEAM',lambda a:roles.red_team(card,a))):
        errors=[]
        for attempt in range(MAX_CONTENT_ATTEMPTS):
            try:
                out[name]=fn(attempt);stats['COMPLETED'][name]+=1
                if attempt:stats['CONTENT_RETRIES'][name]+=1
                break
            except (RoleContractError,BilledFailure) as e:
                errors.append({'ROLE':name,'ATTEMPT':attempt,'DETAIL':type(e).__name__+': '+str(e)[:300]})
        else:
            stats['REVIEW_FAILED'][name]+=1
            return None,errors
    return out,[]

def _selector_advisory(c,caller,ctx,order):
    """Deterministic order is authoritative. Record agreement; never abort."""
    if not order:return {'STATUS':'NOT_CALLED','REASON':'no survivors'}
    try:
        raw=caller.call('SELECTOR',ctx,SELECTOR_PROMPT,{'max_output_tokens':ROLE_OUTPUT_TOKEN_CAPS['SELECTOR']},'selection')
    except (BudgetExceeded,CallUncertain,ProviderThrottled,ProviderRejected,BilledFailure) as e:
        # Advisory, so never fatal; but an attempt left open keeps its reserved charge
        # and is named here so the spend is explained (it is also listed in SPEND).
        key=caller.last_key;state=caller.ledger.call_state(key) if key else None
        out={'STATUS':'UNAVAILABLE','REASON':type(e).__name__+': '+str(e)[:300],'CALL_KEY':key,'CALL_STATE':state}
        if state is not None:
            out['CHARGED_MICRO_USD']=caller.ledger.db.execute("SELECT CASE WHEN state IN ('COMPLETE','FAILED_WITH_COST','RECONCILED_BILLED') THEN cost WHEN state IN ('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED') THEN 0 ELSE COALESCE(cost,reserved) END FROM calls WHERE key=?",(key,)).fetchone()[0]
            if state in ('RESERVED','DISPATCHED','UNCERTAIN','BACKGROUND_SUBMITTED'):out['RESOLUTION']='reconcile '+key+' offline; its reserved bound stays charged until then'
        return out
    try:
        proposal=parse_json(raw);exact(proposal,{'ORDERED_CANDIDATE_IDS'})
        proposed=proposal['ORDERED_CANDIDATE_IDS']
    except ContractError as e:
        return {'STATUS':'MALFORMED','REASON':str(e)[:300]}
    if proposed==order:return {'STATUS':'AGREES'}
    return {'STATUS':'DISAGREES','PROPOSED':proposed if isinstance(proposed,list) else None}

def run_campaign(c,caller,size=40):
    ledger=caller.ledger
    status=ledger.get('status')
    if status=='MUTATED_REQUIRES_REVIEW':raise ContractError('human mutation invalidated prior decisions; review explicitly')
    if status=='DERIVED_IMPORTED_REVALIDATED':
        raise ContractError('derived import stopped after revalidation; generation continuation is not authorized')
    existing=ledger.db.execute("SELECT payload FROM results WHERE key='campaign'").fetchone()
    if existing:return json.loads(existing[0])
    if status not in RESUMABLE_STATUSES:
        raise ContractError('campaign status does not permit generation')
    _require_causal_event(ledger,status)
    if type(size)!=int or not 25<=size<=50:raise ContractError('invalid batch size')
    enforce_campaign_budget(c,caller,size)
    try:
        return _run(c,caller,ledger,size,status)
    except InfrastructureStop as e:
        new=next((v for k,v in _PAUSE.items() if isinstance(e,k)),'PAUSED_UNCERTAIN_CALL')
        with ledger.transaction():
            ledger.set('status',new)
            ledger.event('CAMPAIGN_'+new,{'REASON':type(e).__name__+': '+str(e)[:500],'RESOLUTION':_resolution(new)})
        raise

PAUSE_STATUSES=tuple(_PAUSE.values())
BUDGET_STOP_EVENT='BUDGET_STOP_ACCEPTED'
_BUDGET_SNAPSHOT=('CAP_MICRO_USD','SPENT_MICRO_USD','WORST_CASE_REMAINING_MICRO_USD')

class BudgetGateRefused(ContractError):
    """The worst-case remaining reservation does not fit and no matching budget-stop acceptance is recorded."""

def campaign_budget_preflight(c,caller,size):
    """Execution-layer preflight: the Caller's own provider bound() and cap, the
    journal's lineage + journal spend. Read only; no POST."""
    from .derive import ledger_budget_preflight
    return ledger_budget_preflight(caller.ledger,c,cap=caller.cap,size=size,bound_provider=caller.provider)

def accept_budget_stop(c,caller,size,actor,reason):
    """Record an explicit acceptance that this campaign may stop at STOPPED_BUDGET.
    Bound to the current cap, spend and worst case: any change needs a new acceptance."""
    if not isinstance(actor,str) or not actor.strip() or not isinstance(reason,str) or not reason.strip():
        raise ContractError('budget-stop acceptance requires actor and reason')
    pre=campaign_budget_preflight(c,caller,size)
    payload={**{k:pre[k] for k in _BUDGET_SNAPSHOT+('REMAINING_AUTHORIZED_MICRO_USD','FITS_AUTHORIZED_REMAINING')},'ACTOR':actor.strip(),'REASON':reason.strip()}
    with caller.ledger.transaction():caller.ledger.event(BUDGET_STOP_EVENT,payload)
    return payload

def enforce_campaign_budget(c,caller,size):
    """Fail closed before any provider call: the worst-case remaining reservation
    must fit the authorized remainder (and a real campaign cap must not exceed the
    owner ceiling), unless the latest recorded BUDGET_STOP_ACCEPTED matches the
    current cap, spend and worst case. This is the authoritative gate; the CLI
    only adds an earlier refusal before a run directory is created."""
    from .derive import OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD
    if caller.provider.real and caller.cap>OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD:
        raise BudgetGateRefused('campaign cap exceeds the owner-authorized total')
    pre=campaign_budget_preflight(c,caller,size)
    if pre['FITS_AUTHORIZED_REMAINING']:return pre
    row=caller.ledger.db.execute('SELECT payload FROM events WHERE kind=? ORDER BY n DESC LIMIT 1',(BUDGET_STOP_EVENT,)).fetchone()
    accepted=json.loads(row[0]) if row else None
    if accepted and all(accepted.get(k)==pre[k] for k in _BUDGET_SNAPSHOT):return pre
    raise BudgetGateRefused('worst-case remaining reservation does not fit the authorized remainder: '+canonical({k:pre[k] for k in _BUDGET_SNAPSHOT+('REMAINING_AUTHORIZED_MICRO_USD',)})+'; record accept_budget_stop (actor, reason) for these exact values to accept a clean STOPPED_BUDGET')

def _require_causal_event(ledger,status):
    """A pause/stop status is valid only with the journal row that caused it: the
    latest CAMPAIGN_* event must be CAMPAIGN_<status>. A status written alone
    (hand edit, partial write) is refused."""
    if status not in PAUSE_STATUSES:return
    row=ledger.db.execute("SELECT kind FROM events WHERE kind LIKE 'CAMPAIGN_%' ORDER BY n DESC LIMIT 1").fetchone()
    if row is None or row[0]!='CAMPAIGN_'+status:
        raise ContractError('status '+status+' has no causal CAMPAIGN_'+status+' journal event; refuse to resume')

def _resolution(status):
    return {
        'STOPPED_BUDGET':'authorize-budget-extension (within the owner ceiling), then resume',
        'PAUSED_UNCERTAIN_CALL':'reconcile the possibly-POSTed call key: BILLED with cost and evidence, NOT_BILLED only with provider evidence for its response_id, or UNKNOWN (charges the bound and closes that logical call); then resume',
        'PAUSED_PROVIDER_THROTTLED':'resume later; not-billed attempts cost nothing',
        'PAUSED_PROVIDER_REJECTED':'fix the rejected request contract or credentials, then resume',
        'PAUSED_BACKGROUND_PENDING':'resume to continue polling the same response_id',
    }[status]

def _run(c,caller,ledger,size,prior_status):
    plan=slot_plan(size)
    diversity(plan,c)
    cards=[]
    for round_n,start in enumerate(range(0,size,10)):
        slots=plan[start:start+10]
        contract_id,key,round_cards,failure=_round_output(c,ledger,caller,round_n,slots)
        cards+=_intake_round(c,ledger,round_n,slots,contract_id,key,round_cards,failure)
    intake=ledger.candidates()
    hard=[{'CANDIDATE_ID':x['CANDIDATE_ID'],'ROUND':x['ROUND'],'CONTRACT':x['CONTRACT'],'REASONS':x['REASONS']} for x in intake if x['STATE']=='HARD_FAIL']
    base_metrics={'SLOTS':size,'VALID':len(cards),'HARD_FAIL':len(hard),'HARD_FAIL_RATE':'{}/{}'.format(len(hard),size),
                  'HARD_FAIL_BY_RULE':dict(sorted(Counter(r['RULE'] for h in hard for r in h['REASONS']).items()))}
    if len(cards)<MIN_VALID_CANDIDATES:
        result={'STATUS':'STOPPED_INSUFFICIENT_VALID','MIN_VALID_CANDIDATES':MIN_VALID_CANDIDATES,'HARD_FAILS':hard,'METRICS':base_metrics,'SPEND':_spend(ledger)}
        result['SEMANTIC_RESULT_DIGEST']=digest(result)
        with ledger.transaction():
            ledger.db.execute('INSERT INTO results VALUES (?,?)',('campaign',canonical(result)))
            ledger.set('status','STOPPED_INSUFFICIENT_VALID')
        return result
    roles=Roles(c,caller);reviews=[];review_failed=[];sanitized=[];selection={};streams=[]
    stats={'COMPLETED':Counter(),'CONTENT_RETRIES':Counter(),'REVIEW_FAILED':Counter()}
    for card in cards:
        out,errors=_review(roles,card,cards,stats)
        if out is None:
            review_failed.append({'CANDIDATE_ID':card['CANDIDATE_ID'],'REASONS':errors})
            reviews.append({'CANDIDATE_ID':card['CANDIDATE_ID'],'STATE':'REVIEW_FAILED','REASONS':errors,'STREAM':'NOT_A_STREAM'})
            continue
        n,f,r=out['NOVELTY'],out['FEASIBILITY'],out['RED_TEAM']
        route=roles.route(n,f,r)
        judgments=n['JUDGMENTS']|f['JUDGMENTS']|r['JUDGMENTS']
        exact(judgments,c.design['GENERATOR_EVALUATION_CRITERIA']['PER_CANDIDATE_DIMENSIONS'])
        reviews.append({'CANDIDATE_ID':card['CANDIDATE_ID'],'STATE':'REVIEWED','NOVELTY':n,'FEASIBILITY':f,'RED_TEAM':r,'ORDINAL_JUDGMENTS':judgments,'STREAM':route})
    # A near-duplicate relation reported in either direction excludes the later ID.
    # Do this only after all critics have answered, so order cannot hide asymmetry.
    duplicate_later=set()
    for review in reviews:
        if review['STATE']!='REVIEWED':continue
        cid=review['CANDIDATE_ID']
        for relation in review['NOVELTY']['BATCH_RELATIONS']:
            if relation['RELATION']!='ORTHOGONAL_MECHANISM':
                duplicate_later.add(max(cid,relation['CANDIDATE_ID']))
    for card,review in zip(cards,reviews):
        if review['STATE']!='REVIEWED':continue
        n,f,r=review['NOVELTY'],review['FEASIBILITY'],review['RED_TEAM']
        if card['CANDIDATE_ID'] in duplicate_later:
            n['VERDICT']='REJECT'
            review['STREAM']='NOT_A_STREAM'
        route=review['STREAM'];judgments=review['ORDINAL_JUDGMENTS']
        if route!='NOT_A_STREAM':
            sanitized.append(roles.sanitize(card,n,f,r));streams.append((card,route))
            selection[card['CANDIDATE_ID']]={'MECHANISM_DISTANCE':judgments['MECHANISM_DISTANCE'],'INFORMATION_GAIN':judgments['NULL_INFORMATION_GAIN'],'FEASIBILITY':f['FEASIBILITY'],'CHEAPNESS':f['CHEAPNESS']}
    ctx={'SANITIZED_CRITIC_OUTPUTS':sanitized,'DATA_STATUS':{x['CANDIDATE_ID']:x['DATA_STATUS'] for x in sanitized},'SELECTION_JUDGMENTS':selection}
    # Deterministic ordinal ordering is authoritative; the provider selector is advisory.
    order=sorted(selection,key=lambda k:tuple(-selection[k][f] for f in ('MECHANISM_DISTANCE','INFORMATION_GAIN','FEASIBILITY','CHEAPNESS'))+(k,))
    advisory=_selector_advisory(c,caller,ctx,order)
    gaps=data_gaps([card for card,stream in streams if stream=='HIGH_VALUE_DATA_BLOCKED'])
    metrics=dict(base_metrics,REVIEWED=len(cards)-len(review_failed),REVIEW_FAILED=len(review_failed),
                 CRITIC_COMPLETIONS=dict(sorted(stats['COMPLETED'].items())),CONTENT_RETRIES=dict(sorted(stats['CONTENT_RETRIES'].items())),
                 REVIEW_FAILED_BY_ROLE=dict(sorted(stats['REVIEW_FAILED'].items())),SELECTOR_ADVISORY=advisory['STATUS'])
    result={'STATUS':'PENDING_HUMAN_REVIEW','CONTRACT':contract.CONTRACT_ID,'EVIDENCE_KIND':'INFRASTRUCTURE_ONLY' if not caller.provider.real else 'UNEXECUTED_SHADOW_IDEATION',
            'CANDIDATES':cards,'REVIEWS':reviews,'HARD_FAILS':hard,'REVIEW_FAILED':review_failed,
            'STREAM_A':[card['CANDIDATE_ID'] for card,stream in streams if stream=='EXECUTABLE_NOW'],'STREAM_B':[card['CANDIDATE_ID'] for card,stream in streams if stream=='HIGH_VALUE_DATA_BLOCKED'],
            'SHORTLIST':order[:5],'SELECTOR_AUTHORITY':'DETERMINISTIC_ORDINAL_ORDER','SELECTOR_ADVISORY':advisory,
            'DATA_GAP_LEDGER_V0':gaps,'SELECTION_JUDGMENTS':selection,'METRICS':metrics,'SPEND':_spend(ledger)}
    result['SEMANTIC_RESULT_DIGEST']=digest(result)
    with ledger.transaction():
        for card,review in zip(cards,reviews):
            ledger.save_card(card,review)
            ledger.db.execute('UPDATE candidates SET state=?,reasons=? WHERE id=? AND state=?',(review['STATE'],canonical(review.get('REASONS',[])),card['CANDIDATE_ID'],'VALID'))
        ledger.db.execute('INSERT INTO results VALUES (?,?)',('campaign',canonical(result)))
        ledger.set('status','PENDING_HUMAN_REVIEW')
    return result

def _spend(ledger):
    return {'LINEAGE_PRIOR_MICRO_USD':ledger.lineage_prior_micro_usd(),'JOURNAL_MICRO_USD':ledger.spent_micro_usd(),'TOTAL_MICRO_USD':ledger.total_charged_micro_usd(),
            'UNRESOLVED_CALLS':ledger.unresolved_calls()}
