"""Offline COMPLETE-response carry-forward. Never POSTs. Source archives stay immutable.

Lineage (pre-live repair F10/F13):
- Every charge in the source journal, plus the source's own carried lineage
  spend, stays charged against the owner ceiling. Imported rows move into the
  destination journal; everything else is carried as LINEAGE PRIOR_SPEND.
  A derive can never refund discarded, failed or uncertain spend.
- Every non-imported source call is recorded as a PRIOR_ATTEMPT with its
  charge, response identity and (for generator rounds) per-card intake
  verdicts, so discarded generations stay visible.
Compatibility (option A): legacy v0.1 generator rounds are importable only if
their call key is grandfathered (legacy_v01.py). New rounds use contract V02.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .context import Contexts,ContractError,digest,byte_digest
from .ledger import Ledger,archive_connect
from .models import GENERATOR_MAX_OUTPUT_TOKENS,ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,ROLE_OUTPUT_TOKEN_CAPS,model_for,request_params_for,price_table,routing_digest
from .mock import slot_plan
from .output_schemas import generator_schema_digest
from .runner import GENERATOR_PROMPT,MAX_CONTENT_ATTEMPTS,generator_identity,generator_request_parameters,parse_round,round_cards,slot_violations_v02,contract_of_request
from . import contract,legacy_v01,legacy_v01_schema

DERIVED_STATUS='DERIVED_IMPORTED_REVALIDATED'
CONTINUATION_STATUS='DERIVED_CONTINUATION_AUTHORIZED'
PROMPT_VERSION=contract.PROMPT_VERSION
GENERATOR_PROVIDER='OPENAI_RESPONSES'
ATTEMPT_FIELDS=('content_attempt','transport_attempt')
# Owner-authorized absolute campaign ceiling. Distinct from the technical
# infrastructure maximum of USD 30. Live spend may not exceed this total,
# measured as lineage prior spend plus the current journal.
OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD=17_100_000

def transport_identity(contexts):
    from .openai_provider import (
        GENERATOR_ENDPOINT,BACKGROUND_STORE_POLICY,CRITIC_ENDPOINT,
        CREATE_TIMEOUT_SECONDS,POLL_INTERVAL_SECONDS,POLL_GET_TIMEOUT_SECONDS,BACKGROUND_MAX_WAIT_SECONDS,
    )
    return {
        'GENERATOR_ENDPOINT':GENERATOR_ENDPOINT,'GENERATOR_BACKGROUND':True,
        'GENERATOR_MODEL':ROLE_MODEL_MAP['GENERATOR'],
        'GENERATOR_REASONING_EFFORT':ROLE_REQUEST_PARAMS['GENERATOR']['reasoning_effort'],
        'GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST':generator_schema_digest(contexts),
        'BACKGROUND_STORE_POLICY':BACKGROUND_STORE_POLICY,
        'DELETE_AFTER_LOCAL_PERSIST':True,
        'POLLING_POLICY':{
            'INTERVAL_SECONDS':POLL_INTERVAL_SECONDS,'GET_TIMEOUT_SECONDS':POLL_GET_TIMEOUT_SECONDS,
            'MAX_WAIT_SECONDS':BACKGROUND_MAX_WAIT_SECONDS,'CREATE_TIMEOUT_SECONDS':CREATE_TIMEOUT_SECONDS,
        },
        'CRITIC_ENDPOINT':CRITIC_ENDPOINT,
        'GENERATOR_MAX_OUTPUT_TOKENS':GENERATOR_MAX_OUTPUT_TOKENS,
    }

def expected_generator_request(contexts,slots,round_n):
    """V02 base request (content/transport attempt 0), exactly as Caller.request builds it."""
    return {
        'role':'GENERATOR','context':contexts.generator(),'prompt':GENERATOR_PROMPT,
        'prompt_version':PROMPT_VERSION,'parameters':generator_request_parameters(slots),
        'provider':GENERATOR_PROVIDER,'model':model_for('GENERATOR'),
        'slot':'generation:'+str(round_n),'model_request_params':request_params_for('GENERATOR'),
        **generator_identity(contexts,slots),
    }

def archive_file_digest(path):
    return byte_digest(path)

def _mismatch(field,expected,actual,errors):
    if expected!=actual:errors.append(field)

def compatibility_errors(expected,stored,source_config,current_id):
    errors=[]
    stored={k:v for k,v in stored.items() if k not in ATTEMPT_FIELDS}
    _mismatch('role',expected['role'],stored.get('role'),errors)
    _mismatch('generation_slot',expected['slot'],stored.get('slot'),errors)
    _mismatch('prompt_version',expected['prompt_version'],stored.get('prompt_version'),errors)
    _mismatch('prompt',expected['prompt'],stored.get('prompt'),errors)
    _mismatch('context_digest',digest(expected['context']),digest(stored.get('context')),errors)
    _mismatch('slots',expected['parameters']['slots'],(stored.get('parameters') or {}).get('slots'),errors)
    _mismatch('model',expected['model'],stored.get('model'),errors)
    _mismatch('reasoning_effort',expected['model_request_params'].get('reasoning_effort'),(stored.get('model_request_params') or {}).get('reasoning_effort'),errors)
    _mismatch('endpoint',expected['provider'],stored.get('provider'),errors)
    _mismatch('max_output_tokens',expected['parameters']['max_output_tokens'],(stored.get('parameters') or {}).get('max_output_tokens'),errors)
    _mismatch('model_request_params',expected['model_request_params'],stored.get('model_request_params'),errors)
    _mismatch('parameters',expected['parameters'],stored.get('parameters'),errors)
    _mismatch('output_contract',expected.get('output_contract'),stored.get('output_contract'),errors)
    _mismatch('output_schema_digest',expected.get('output_schema_digest'),stored.get('output_schema_digest'),errors)
    _mismatch('request_fields',sorted(expected),sorted(stored),errors)
    cfg=source_config or {}
    _mismatch('schema_digest',current_id['GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST'],cfg.get('GENERATOR_STRUCTURED_OUTPUT_SCHEMA_DIGEST'),errors)
    _mismatch('GENERATOR_MAX_OUTPUT_TOKENS',current_id['GENERATOR_MAX_OUTPUT_TOKENS'],cfg.get('GENERATOR_MAX_OUTPUT_TOKENS'),errors)
    _mismatch('GENERATOR_ENDPOINT',current_id['GENERATOR_ENDPOINT'],cfg.get('GENERATOR_ENDPOINT'),errors)
    _mismatch('GENERATOR_BACKGROUND',current_id['GENERATOR_BACKGROUND'],cfg.get('GENERATOR_BACKGROUND'),errors)
    _mismatch('BACKGROUND_STORE_POLICY',current_id['BACKGROUND_STORE_POLICY'],cfg.get('BACKGROUND_STORE_POLICY'),errors)
    _mismatch('GENERATOR_MODEL',current_id['GENERATOR_MODEL'],cfg.get('GENERATOR_MODEL'),errors)
    _mismatch('GENERATOR_REASONING_EFFORT',current_id['GENERATOR_REASONING_EFFORT'],cfg.get('GENERATOR_REASONING_EFFORT'),errors)
    return errors

def derived_config(dest_id,source_config,contexts):
    from .openai_provider import OPENAI_REQUEST_TIMEOUT_SECONDS
    ident=transport_identity(contexts)
    impl=digest({x.name:byte_digest(x) for x in sorted(Path(__file__).parent.glob('*.py'))})
    return {
        'RUN_ID':dest_id,'PROVIDER':'OPENAI_MIXED','MODEL':'ROLE_SPECIFIC',
        'SIZE':source_config['SIZE'],'CAP_MICRO_USD':source_config['CAP_MICRO_USD'],
        'CONTEXT_DIGEST':digest(contexts.generator()),'IMPLEMENTATION_DIGEST':impl,
        'ROLE_MODEL_MAP':dict(ROLE_MODEL_MAP),
        'ROLE_REQUEST_PARAMS':{k:dict(v) for k,v in ROLE_REQUEST_PARAMS.items()},
        'PRICE_TABLE':price_table(),
        'ROUTING_DIGEST':digest({'ROUTING':routing_digest(),'TRANSPORT':ident}),
        'REQUEST_TIMEOUT_SECONDS':OPENAI_REQUEST_TIMEOUT_SECONDS,
        **ident,
    }

def charge(row):
    """Python twin of ledger.CHARGE_SQL for one call row."""
    if row['state'] in ('COMPLETE','FAILED_WITH_COST','RECONCILED_BILLED'):return row['cost']
    if row['state'] in ('FAILED_NOT_BILLED','RECONCILED_NOT_BILLED'):return 0
    return row['cost'] if row['cost'] is not None else row['reserved']

def _source_calls(db):
    rows=[]
    for key,request,state,reserved,response,cost,usage,error in db.execute('SELECT * FROM calls ORDER BY rowid'):
        rows.append({
            'key':key,'request':json.loads(request),'state':state,'reserved':reserved,
            'response':json.loads(response) if response else None,'cost':cost,
            'usage':json.loads(usage) if usage else None,'error':error,
        })
    return rows

def _meta(db,key):
    row=db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else None

def _intake_summary(row,contexts):
    """Per-card verdicts of a generator round under the contract it was generated with."""
    raw=(row['response'] or {}).get('raw')
    cards=round_cards(raw,contract_of_request(row['request'])) if raw else None
    if cards is None:return {'ROUND_USABLE':False,'CARDS':[]}
    legacy=row['request'].get('prompt_version')==legacy_v01.PROMPT_VERSION
    out=[]
    for card in cards:
        cid=card.get('CANDIDATE_ID') if isinstance(card,dict) else None
        if legacy:
            try:legacy_v01_schema.validate_card(card,contexts);out.append({'CANDIDATE_ID':cid,'VERDICT':'VALID','CONTRACT':legacy_v01.CONTRACT_ID,'REASONS':[]})
            except ContractError as e:out.append({'CANDIDATE_ID':cid,'VERDICT':'HARD_FAIL','CONTRACT':legacy_v01.CONTRACT_ID,'REASONS':[str(e)[:200]]})
        else:
            v=contract.card_violations(card,contexts)
            out.append({'CANDIDATE_ID':cid,'VERDICT':'HARD_FAIL' if v else 'VALID','CONTRACT':contract.CONTRACT_ID,'REASONS':[x['RULE'] for x in v]})
    return {'ROUND_USABLE':True,'CARDS':out}

def _select_round(rows,slot,contexts,plan,source_config,current_id):
    """The COMPLETE call the runner would use for this round, or None."""
    round_n=int(slot.split(':',1)[1]);slots=plan[round_n*10:round_n*10+10]
    candidates=[r for r in rows if r['request'].get('role')=='GENERATOR' and r['request'].get('slot')==slot and r['state']=='COMPLETE']
    for r in candidates:
        if legacy_v01.is_grandfathered_call(r['key']):
            expected=legacy_v01.expected_request(contexts,slots,round_n,model_for('GENERATOR'),request_params_for('GENERATOR'))
            if digest(expected)!=r['key']:raise ContractError('grandfathered call key does not match legacy identity')
            return r,expected,legacy_v01.CONTRACT_ID
    v02=[r for r in candidates if r['request'].get('prompt_version')==PROMPT_VERSION]
    v02.sort(key=lambda r:(r['request'].get('content_attempt',0),r['request'].get('transport_attempt',0)))
    for r in v02:
        expected=expected_generator_request(contexts,slots,round_n)
        errors=compatibility_errors(expected,r['request'],source_config,current_id)
        if errors:raise ContractError('incompatible COMPLETE call '+slot+': '+','.join(errors))
        if parse_round(r['response'].get('raw')) is not None:return r,r['request'],contract.CONTRACT_ID
    return None

def derive_complete_rounds(source_dir,dest_dir,through_generation=1,contexts=None):
    source_dir=Path(source_dir);dest_dir=Path(dest_dir)
    if through_generation is None or type(through_generation)!=int or through_generation<0:
        raise ContractError('through_generation')
    if dest_dir.exists():raise ContractError('destination run exists')
    source_db=source_dir/'run.sqlite'
    if not source_db.exists():raise ContractError('source run not found')
    before=archive_file_digest(source_db)
    contexts=contexts or Contexts()
    current_id=transport_identity(contexts)
    db=archive_connect(source_db)
    try:
        source_config=_meta(db,'config')
        if not isinstance(source_config,dict):raise ContractError('source config missing')
        size=source_config.get('SIZE')
        if type(size)!=int or not 25<=size<=50:raise ContractError('source batch size')
        plan=slot_plan(size)
        rows=_source_calls(db)
        source_lineage=_meta(db,'lineage') or {}
        source_prior=source_lineage.get('PRIOR_SPEND_MICRO_USD',0)
        if type(source_prior) is not int or source_prior<0:raise ContractError('invalid source lineage')
    finally:
        db.close()
    wanted=['generation:'+str(n) for n in range(through_generation+1)]
    imported=[];missing=[]
    for slot in wanted:
        picked=_select_round(rows,slot,contexts,plan,source_config,current_id)
        if picked is None:missing.append(slot)
        else:imported.append((int(slot.split(':')[1]),)+picked)
    if missing:
        detail=[]
        for slot in missing:
            legacy=[r for r in rows if r['request'].get('slot')==slot and r['request'].get('prompt_version')==legacy_v01.PROMPT_VERSION]
            detail.append(slot+(' (legacy v0.1, not grandfathered)' if legacy else ''))
        raise ContractError('missing COMPLETE source rounds: '+','.join(detail))
    imported_keys={r['key'] for _,r,_,_ in imported}
    source_journal=sum(charge(r) for r in rows)
    imported_charge=sum(charge(r) for _,r,_,_ in imported)
    carried=source_prior+source_journal-imported_charge
    cap=source_config['CAP_MICRO_USD']
    if carried+imported_charge>cap:raise ContractError('lineage spend exceeds campaign cap')
    prior_attempts=list(source_lineage.get('PRIOR_ATTEMPTS',[]))
    for r in rows:
        if r['key'] in imported_keys:continue
        entry={'SOURCE_RUN_ID':source_config['RUN_ID'],'CALL_KEY':r['key'],'ROLE':r['request'].get('role'),'SLOT':r['request'].get('slot'),
               'PROMPT_VERSION':r['request'].get('prompt_version'),'STATE':r['state'],'CHARGED_MICRO_USD':charge(r),
               'RESPONSE_ID':(r['response'] or {}).get('response_id'),'RAW_RESPONSE_SHA256':(r['response'] or {}).get('raw_sha256')}
        if r['request'].get('role')=='GENERATOR' and r['state']=='COMPLETE':entry['INTAKE']=_intake_summary(r,contexts)
        prior_attempts.append(entry)
    sources=list(source_lineage.get('SOURCES',[]))+[{'RUN_ID':source_config['RUN_ID'],'JOURNAL_SHA256':before,
               'JOURNAL_CHARGED_MICRO_USD':source_journal,'LINEAGE_PRIOR_MICRO_USD':source_prior}]
    lineage={'PRIOR_SPEND_MICRO_USD':carried,'PRIOR_ATTEMPTS':prior_attempts,'SOURCES':sources,
             'RULE':'lineage prior spend + journal charges + new reservation <= CAP_MICRO_USD'}
    imported.sort(key=lambda item:item[0])
    intake={};verdicts={}
    for round_n,r,expected,contract_id in imported:
        slots=plan[round_n*10:round_n*10+10];cards=parse_round(r['response']['raw'],contract_id) or []
        by=cards if isinstance(cards,dict) else {c.get('CANDIDATE_ID'):c for c in cards if isinstance(c,dict)}
        valid=0
        for s in slots:
            card=by.get(s['CANDIDATE_ID']);ok=False
            if card is not None and contract_id==legacy_v01.CONTRACT_ID:
                try:legacy_v01.admit_card(card,contexts,r['key']);ok=True
                except ContractError:ok=False
            elif card is not None:ok=not slot_violations_v02(card,contexts,s)[0]
            verdicts[s['CANDIDATE_ID']]='VALID' if ok else 'HARD_FAIL'
            valid+=ok
        intake['generation:'+str(round_n)]={'CONTRACT':contract_id,'VALID':valid,'HARD_FAIL':len(slots)-valid}
    dest_dir.mkdir(parents=True,exist_ok=False)
    dest=Ledger(dest_dir/'run.sqlite',derived_config(dest_dir.name,source_config,contexts))
    try:
        with dest.transaction():dest.set('lineage',lineage)
        for round_n,r,expected,contract_id in imported:
            provenance={
                'SOURCE_RUN_ID':source_config['RUN_ID'],'SOURCE_CALL_KEY':r['key'],
                'SOURCE_RESPONSE_ID':r['response']['response_id'],
                'SOURCE_RAW_RESPONSE_SHA256':r['response']['raw_sha256'],
            }
            dest.import_complete(r['key'],r['request'],r['reserved'],r['response'],r['cost'],r['usage'],provenance)
        total=dest.total_charged_micro_usd()
        if total!=source_prior+source_journal:raise ContractError('lineage spend not preserved')
        cards_ids=[c.get('CANDIDATE_ID') for _,r,_,cid in imported for c in (round_cards(r['response']['raw'],cid) or []) if isinstance(c,dict)]
        report={
            'STATUS':DERIVED_STATUS,'SOURCE_RUN_ID':source_config['RUN_ID'],'DEST_RUN_ID':dest_dir.name,
            'IMPORTED_GENERATION_ROUNDS':['generation:'+str(n) for n,_,_,_ in imported],
            'IMPORTED_CALL_KEYS':[r['key'] for _,r,_,_ in imported],
            'IMPORTED_CONTRACTS':{'generation:'+str(n):c for n,_,_,c in imported},
            'IMPORTED_INTAKE':intake,
            'IMPORTED_COST_MICRO_USD':imported_charge,'LINEAGE_PRIOR_MICRO_USD':carried,
            'LINEAGE_TOTAL_MICRO_USD':total,'CAP_MICRO_USD':cap,'REMAINING_MICRO_USD':cap-total,
            'PRIOR_ATTEMPT_COUNT':len(prior_attempts),'CARD_IDS':cards_ids,
            'IMPORTED_INTAKE_VERDICTS':verdicts,
            'C018_REVALIDATION':{'VALID':'PASS','HARD_FAIL':'HARD_FAIL'}.get(verdicts.get('C018'),'ABSENT'),
            'CARDS_WRITTEN':False,'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,
        }
        with dest.transaction():
            dest.set('imported_rounds',{'generation:'+str(n):{'CALL_KEY':r['key'],'CONTRACT':c} for n,r,_,c in imported})
            dest.set('status',DERIVED_STATUS)
            dest.event('DERIVED_IMPORT',report)
    except Exception:
        dest.close();raise
    dest.close()
    after=archive_file_digest(source_db)
    if before!=after:raise ContractError('source archive mutated during derive')
    return report

def authorize_derived_continuation(run_dir,actor,reason):
    """Explicit offline gate. Never contacts a provider."""
    dbpath=Path(run_dir)/'run.sqlite'
    if not dbpath.exists():raise ContractError('run not found')
    if not isinstance(actor,str) or not actor.strip() or not isinstance(reason,str) or not reason.strip():
        raise ContractError('actor and reason required')
    ledger=Ledger(dbpath)
    try:
        with ledger.transaction():
            if ledger.get('status')!=DERIVED_STATUS:
                raise ContractError('derived continuation requires DERIVED_IMPORTED_REVALIDATED')
            payload={'ACTOR':actor.strip(),'REASON':reason.strip(),'time':datetime.now(timezone.utc).isoformat(),'REAL_LLM_CALLS_MADE':False}
            ledger.event('DERIVED_CONTINUATION_AUTHORIZED',payload)
            ledger.set('status',CONTINUATION_STATUS)
        return {'STATUS':CONTINUATION_STATUS,'ACTOR':actor.strip(),'REASON':reason.strip(),'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False}
    finally:
        ledger.close()

def _cap_micro_usd(value):
    amount=Decimal(str(value))
    if not amount.is_finite() or not 0<amount<=30 or amount*1_000_000!=(amount*1_000_000).to_integral_value():
        raise ContractError('budget must be finite USD 0..30, at microdollar precision')
    return int(amount*1_000_000)

def authorize_budget_extension(run_dir,actor,reason,new_cap_usd):
    """Offline cap increase. Does not rewrite calls, responses, costs, or cards."""
    dbpath=Path(run_dir)/'run.sqlite'
    if not dbpath.exists():raise ContractError('run not found')
    if not isinstance(actor,str) or not actor.strip() or not isinstance(reason,str) or not reason.strip():
        raise ContractError('actor and reason required')
    if new_cap_usd is None or (isinstance(new_cap_usd,str) and not new_cap_usd.strip()):
        raise ContractError('new cap required')
    new=_cap_micro_usd(new_cap_usd)
    ledger=Ledger(dbpath)
    try:
        with ledger.transaction():
            cfg=ledger.get('config')
            if not isinstance(cfg,dict) or type(cfg.get('CAP_MICRO_USD')) is not int:
                raise ContractError('run cap missing')
            old=cfg['CAP_MICRO_USD']
            if new<=old:raise ContractError('new cap must exceed old cap')
            if new>OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD:
                raise ContractError('new cap exceeds owner-authorized campaign total USD 17.100000')
            spent=ledger.total_charged_micro_usd()
            if type(spent) is not int or spent<0:raise ContractError('invalid spent')
            if spent>new:raise ContractError('new cap below spent')
            ledger.set('config',{**cfg,'CAP_MICRO_USD':new})
            payload={
                'OLD_CAP_MICRO_USD':old,'NEW_CAP_MICRO_USD':new,'LINEAGE_TOTAL_SPENT_MICRO_USD':spent,
                'ACTOR':actor.strip(),'REASON':reason.strip(),
                'TIME':datetime.now(timezone.utc).isoformat(),
                'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,
            }
            ledger.event('BUDGET_EXTENSION_AUTHORIZED',payload)
        return {
            'STATUS':'BUDGET_EXTENSION_AUTHORIZED','OLD_CAP_MICRO_USD':old,'NEW_CAP_MICRO_USD':new,
            'SPENT_MICRO_USD':spent,'REMAINING_MICRO_USD':new-spent,
            'ACTOR':actor.strip(),'REASON':reason.strip(),
            'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,
        }
    finally:
        ledger.close()

def reconcile_call(run_dir,call_key,resolution,cost_usd,actor,reason,evidence=''):
    """Offline operator resolution of a possibly-POSTed attempt (see Ledger.reconcile). Never POSTs."""
    dbpath=Path(run_dir)/'run.sqlite'
    if not dbpath.exists():raise ContractError('run not found')
    cost=_cap_micro_usd(cost_usd) if resolution=='BILLED' and cost_usd not in (None,'') else None
    ledger=Ledger(dbpath)
    try:
        payload=ledger.reconcile(call_key,resolution,cost,actor,reason,evidence)
        return {'STATUS':'CALL_RECONCILED',**payload,'LINEAGE_TOTAL_SPENT_MICRO_USD':ledger.total_charged_micro_usd(),'REAL_LLM_CALLS_MADE':False}
    finally:
        ledger.close()

def _offline_bound_provider(contexts,cap):
    from .openai_provider import OpenAIProvider
    def refuse(*_a,**_k):
        raise ContractError('remaining-budget-preflight is offline')
    return OpenAIProvider('remaining-budget-preflight',allow_real=True,budget_micro_usd=max(cap,1),contexts=contexts,transport=refuse)

def _stage(name,bound):
    return {'STAGE':name,'BOUND_MICRO_USD':bound,'BOUND_USD':str(Decimal(bound)/Decimal(1_000_000))}

def _bound_context(c,role,card,cards):
    """Critic context for bounding. Proxy cards need not satisfy the card contract."""
    import copy
    from .roles import CHECKLIST,PROTECTED,current_signatures
    if role=='NOVELTY_CRITIC':
        return copy.deepcopy({'BLIND_MECHANISM_MAP_V0':c.blind,'GOVERNANCE_REGION_AUTHORITY_V0':c.authority,'GENERIC_ANTI_RESCUE_RULES':'Apply only the frozen relation table per signature, never close entire families.','CURRENT_BATCH_SIGNATURES':current_signatures(cards),'CANDIDATE':card})
    if role=='FEASIBILITY_CRITIC':
        rows=[r for r in c.rows.values() if r['STATE']!='PARTIAL_OR_MIXED']
        blockers=[{k:r[k] for k in ('SIGNATURE_ID','BLOCKER_CLASS_IF_ANY','BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY')} for r in rows if r['BLOCKER_CLASS_IF_ANY']]
        return copy.deepcopy({'CANDIDATE':card,'DATA_CATALOG_V0':c.catalog,'DATA_STATUS_TAXONOMY':c.design['DATA_STATUS_TAXONOMY'],'BLOCKER_REQUIREMENTS':blockers,'PROTECTED_DATA_RULES':PROTECTED})
    return copy.deepcopy({'CANDIDATE':card,'METHODOLOGY_CHECKLIST':CHECKLIST,'PROTECTED_DATA_RULES':PROTECTED})

# Proxy for cards not generated yet: the largest serialized card observed in any
# tracked first-shadow journal (v7, 40 cards; recomputed by a test) times a margin.
# Signature fields (copied into every novelty request) are sized separately from
# the observed maximum signature, so one large card is not multiplied 40 times.
OBSERVED_MAX_CARD_BYTES=6008
OBSERVED_MAX_SIGNATURE_BYTES=1043
PROXY_CARD_MARGIN=Decimal('1.5')

def _ceil(x):
    return int(Decimal(x).to_integral_value(rounding='ROUND_CEILING'))

def proxy_card(slot,contexts,target_bytes,signature_bytes):
    """A synthetic card of at least target_bytes serialized bytes whose novelty
    signature is at least signature_bytes. For bounding only."""
    from .mock import fixture
    from .context import canonical
    from .roles import current_signatures
    card=fixture(slot,contexts);card.update(slot)
    pad=signature_bytes-len(canonical(current_signatures([card])[0]).encode())
    if pad>0:card['MECHANISM']=card['MECHANISM']+' '+'x'*(pad-1)
    pad=target_bytes-len(canonical(card).encode())
    if pad>0:card['CAUSAL_OR_STRUCTURAL_STORY']=card['CAUSAL_OR_STRUCTURAL_STORY']+' '+'x'*(pad-1)
    return card

def campaign_bound(contexts,size,known_cards=(),done_rounds=(),caps=None,content_attempts=None,margin=None,bound_provider=None):
    """Worst-case reservation for everything not yet COMPLETE-imported, through the
    live bound() path. Missing cards are proxies of max(largest known card,
    OBSERVED_MAX_CARD_BYTES x margin) bytes. No POST."""
    from .roles import NOVELTY_PROMPT,FEAS_PROMPT,RED_PROMPT,SELECTOR_PROMPT
    from .context import canonical
    caps=dict(ROLE_OUTPUT_TOKEN_CAPS if caps is None else caps)
    attempts=MAX_CONTENT_ATTEMPTS if content_attempts is None else content_attempts
    margin=PROXY_CARD_MARGIN if margin is None else Decimal(margin)
    if type(size)!=int or not 25<=size<=50:raise ContractError('batch size')
    # bound_provider: the provider that will actually be called (execution-layer gate);
    # default: the offline OpenAI bound path (CLI/operator preflight).
    provider=bound_provider if bound_provider is not None else _offline_bound_provider(contexts,30_000_000)
    plan=slot_plan(size)
    cards=[c for c in known_cards if isinstance(c,dict)][:size]
    from .roles import current_signatures
    proxy_bytes=max([_ceil(OBSERVED_MAX_CARD_BYTES*margin)]+[len(canonical(c).encode()) for c in cards])
    sig_bytes=max([_ceil(OBSERVED_MAX_SIGNATURE_BYTES*margin)]+[len(canonical(x).encode()) for x in current_signatures(cards)])
    have={c.get('CANDIDATE_ID') for c in cards}
    cards+=[proxy_card(slot,contexts,proxy_bytes,sig_bytes) for slot in plan if slot['CANDIDATE_ID'] not in have][:size-len(cards)]
    stages=[];total=0
    for round_n in [n for n in range((size+9)//10) if n not in set(done_rounds)]:
        slots=plan[round_n*10:round_n*10+10]
        req={'role':'GENERATOR','context':contexts.generator(),'prompt':GENERATOR_PROMPT,
             'parameters':generator_request_parameters(slots),**generator_identity(contexts,slots)}
        bound=provider.bound(req);total+=bound
        stages.append(_stage('generation:'+str(round_n),bound))
    critic_tot={'NOVELTY_CRITIC':0,'FEASIBILITY_CRITIC':0,'RED_TEAM':0}
    for card in cards:
        for role,prompt in (('NOVELTY_CRITIC',NOVELTY_PROMPT),('FEASIBILITY_CRITIC',FEAS_PROMPT),('RED_TEAM',RED_PROMPT)):
            ctx=_bound_context(contexts,role,card,cards)
            bound=provider.bound({'role':role,'context':ctx,'prompt':prompt,'parameters':{'max_output_tokens':caps[role]}})
            critic_tot[role]+=bound;total+=bound
    for role,bound in critic_tot.items():
        stages.append(_stage(role+' x'+str(size),bound))
    selection={card['CANDIDATE_ID']:{'MECHANISM_DISTANCE':3,'INFORMATION_GAIN':3,'FEASIBILITY':3,'CHEAPNESS':3} for card in cards}
    sanitized=[{'CANDIDATE_ID':card['CANDIDATE_ID'],'DATA_STATUS':card['DATA_STATUS']} for card in cards]
    selector_ctx={'SANITIZED_CRITIC_OUTPUTS':sanitized,'DATA_STATUS':{card['CANDIDATE_ID']:card['DATA_STATUS'] for card in cards},'SELECTION_JUDGMENTS':selection}
    selector_bound=provider.bound({'role':'SELECTOR','context':selector_ctx,'prompt':SELECTOR_PROMPT,'parameters':{'max_output_tokens':caps['SELECTOR']}})
    total+=selector_bound
    stages.append(_stage('SELECTOR',selector_bound))
    # The selector is advisory and never retried; every other call may be retried once per content attempt.
    with_retries=total*attempts-selector_bound*(attempts-1)
    return {'SIZE':size,'CAPS':caps,'CONTENT_ATTEMPTS':attempts,'PROXY_CARD_BYTES':proxy_bytes,'PROXY_SIGNATURE_BYTES':sig_bytes,'PROXY_MARGIN':str(margin),'PROXY_CARDS':size-len([c for c in known_cards if isinstance(c,dict)][:size]),
            'STAGES':stages,'WORST_CASE_SINGLE_ATTEMPT_MICRO_USD':total,'WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD':with_retries}

def fresh_campaign_budget_preflight(size,cap_micro_usd,contexts=None,caps=None,content_attempts=None,margin=None,lineage_prior_micro_usd=0):
    """Preflight for a run that has no journal yet. No POST, no journal written."""
    contexts=contexts or Contexts()
    b=campaign_bound(contexts,size,(),(),caps,content_attempts,margin)
    return _preflight_report(b,cap_micro_usd,lineage_prior_micro_usd,0,[],[])

def _preflight_report(b,cap,prior,journal,done,known_rounds):
    spent=prior+journal;remaining_auth=cap-spent
    total=b['WORST_CASE_SINGLE_ATTEMPT_MICRO_USD'];with_retries=b['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD']
    return {
        'STATUS':'REMAINING_BUDGET_PREFLIGHT',
        'CAP_MICRO_USD':cap,'SPENT_MICRO_USD':spent,'LINEAGE_PRIOR_MICRO_USD':prior,'JOURNAL_SPENT_MICRO_USD':journal,
        'REMAINING_AUTHORIZED_MICRO_USD':remaining_auth,
        'OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD':OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,
        'WORST_CASE_REMAINING_MICRO_USD':total,'WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD':with_retries,
        'MIN_ADDITIONAL_AUTHORIZATION_MICRO_USD':max(0,total-remaining_auth),
        'MIN_TOTAL_CAP_MICRO_USD':spent+total,'MIN_TOTAL_CAP_WITH_CONTENT_RETRIES_MICRO_USD':spent+with_retries,
        'FITS_AUTHORIZED_REMAINING':total<=remaining_auth and cap<=OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,
        'FITS_WITH_CONTENT_RETRIES':with_retries<=remaining_auth and cap<=OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,
        'IMPORTED_GENERATION_ROUNDS':['generation:'+str(n) for n in sorted(done)],
        'REMAINING_GENERATION_ROUNDS':[s['STAGE'] for s in b['STAGES'] if s['STAGE'].startswith('generation:')],
        'PROXY_CARDS':b['PROXY_CARDS'],'PROXY_CARD_BYTES':b['PROXY_CARD_BYTES'],'PROXY_SIGNATURE_BYTES':b['PROXY_SIGNATURE_BYTES'],'PROXY_MARGIN':b['PROXY_MARGIN'],'CAPS':b['CAPS'],'CONTENT_ATTEMPTS':b['CONTENT_ATTEMPTS'],
        'STAGES':b['STAGES'],
        'NOTE':'Conservative: every remaining critic call is bounded even if already COMPLETE in this journal. Budget exhaustion during a live run stops cleanly (STOPPED_BUDGET) before any POST.',
        'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,
    }

def ledger_budget_preflight(ledger,contexts,cap=None,size=None,bound_provider=None,caps=None,content_attempts=None,margin=None):
    """Preflight from an open journal (read only). cap/size default to the journal config."""
    cfg=ledger.get('config') or {}
    cap=cfg.get('CAP_MICRO_USD') if cap is None else cap
    if type(cap) is not int:raise ContractError('run cap missing')
    size=cfg.get('SIZE',40) if size is None else size
    if type(size)!=int or not 25<=size<=50:raise ContractError('source batch size')
    done=[];cards=[]
    for slot,row in sorted((ledger.get('imported_rounds') or {}).items()):
        batch=round_cards(ledger.complete_raw(row['CALL_KEY']),row['CONTRACT'])
        if batch is None:raise ContractError('imported round unusable')
        done.append(int(slot.split(':')[1]));cards+=[c for c in batch if isinstance(c,dict)]
    b=campaign_bound(contexts,size,cards,done,caps,content_attempts,margin,bound_provider)
    return _preflight_report(b,cap,ledger.lineage_prior_micro_usd(),ledger.spent_micro_usd(),done,[])

def remaining_campaign_budget_preflight(run_dir,contexts=None,caps=None,content_attempts=None,margin=None):
    """Worst-case remaining reservation for a fresh, running or derived journal,
    through the same bound() path as live calls. No POST; the journal is read
    through an immutable handle. Spend includes lineage prior spend."""
    dbpath=Path(run_dir)/'run.sqlite'
    if not dbpath.exists():raise ContractError('run not found')
    contexts=contexts or Contexts()
    ledger=Ledger.open_readonly(dbpath)
    try:
        return ledger_budget_preflight(ledger,contexts,caps=caps,content_attempts=content_attempts,margin=margin)
    finally:
        ledger.close()
