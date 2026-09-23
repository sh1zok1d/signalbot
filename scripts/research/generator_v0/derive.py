"""Offline COMPLETE-response carry-forward. Never POSTs. Source archives stay immutable."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .context import Contexts,ContractError,digest,byte_digest
from .ledger import Ledger
from .models import GENERATOR_MAX_OUTPUT_TOKENS,ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,model_for,request_params_for,price_table,routing_digest
from .mock import slot_plan
from .output_schemas import generator_schema_digest
from .runner import GENERATOR_PROMPT
from .schema import parse_json,validate_card
from .roles import exact

DERIVED_STATUS='DERIVED_IMPORTED_REVALIDATED'
CONTINUATION_STATUS='DERIVED_CONTINUATION_AUTHORIZED'
PROMPT_VERSION='generator-v0.1'
GENERATOR_PROVIDER='OPENAI_RESPONSES'

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
    return {
        'role':'GENERATOR','context':contexts.generator(),'prompt':GENERATOR_PROMPT,
        'prompt_version':PROMPT_VERSION,
        'parameters':{'max_output_tokens':GENERATOR_MAX_OUTPUT_TOKENS,'slots':list(slots)},
        'provider':GENERATOR_PROVIDER,'model':model_for('GENERATOR'),
        'slot':'generation:'+str(round_n),'model_request_params':request_params_for('GENERATOR'),
    }

def archive_file_digest(path):
    return byte_digest(path)

def _mismatch(field,expected,actual,errors):
    if expected!=actual:errors.append(field)

def compatibility_errors(expected,stored,source_config,current_id):
    errors=[]
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

def _source_calls(source):
    rows=[]
    for key,request,state,reserved,response,cost,usage,error in source.db.execute('SELECT * FROM calls ORDER BY rowid'):
        rows.append({
            'key':key,'request':json.loads(request),'state':state,'reserved':reserved,
            'response':json.loads(response) if response else None,'cost':cost,
            'usage':json.loads(usage) if usage else None,'error':error,
        })
    return rows

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
    source=Ledger.open_readonly(source_db)
    try:
        source_config=source.get('config')
        if not isinstance(source_config,dict):raise ContractError('source config missing')
        size=source_config.get('SIZE')
        if type(size)!=int or not 25<=size<=50:raise ContractError('source batch size')
        plan=slot_plan(size)
        wanted={'generation:'+str(n) for n in range(through_generation+1)}
        imported=[]
        for row in _source_calls(source):
            slot=row['request'].get('slot')
            if slot not in wanted:continue
            if row['state']!='COMPLETE':
                raise ContractError('source call '+str(slot)+' is '+str(row['state'])+' and cannot be imported')
            round_n=int(slot.split(':',1)[1])
            start=round_n*10
            expected=expected_generator_request(contexts,plan[start:start+10],round_n)
            errors=compatibility_errors(expected,row['request'],source_config,current_id)
            if errors:raise ContractError('incompatible COMPLETE call '+slot+': '+','.join(errors))
            if digest(expected)!=row['key']:raise ContractError('source call key does not match reconstructed identity')
            imported.append((round_n,row,expected))
        found={item[1]['request']['slot'] for item in imported}
        missing=sorted(wanted-found)
        if missing:raise ContractError('missing COMPLETE source rounds: '+','.join(missing))
        imported.sort(key=lambda item:item[0])
        cards=[]
        for round_n,row,expected in imported:
            raw=(row['response'] or {}).get('raw')
            parsed=parse_json(raw);exact(parsed,{'CANDIDATES'})
            batch=parsed['CANDIDATES']
            slots=expected['parameters']['slots']
            if not isinstance(batch,list) or len(batch)!=len(slots):raise ContractError('wrong generation round size')
            for card,slot in zip(batch,slots):
                validate_card(card,contexts)
                if any(card[k]!=v for k,v in slot.items()):raise ContractError('slot assignment mismatch')
                cards.append(card)
        dest_dir.mkdir(parents=True,exist_ok=False)
        dest=Ledger(dest_dir/'run.sqlite',derived_config(dest_dir.name,source_config,contexts))
        try:
            for round_n,row,expected in imported:
                provenance={
                    'SOURCE_RUN_ID':source_config['RUN_ID'],'SOURCE_CALL_KEY':row['key'],
                    'SOURCE_RESPONSE_ID':row['response']['response_id'],
                    'SOURCE_RAW_RESPONSE_SHA256':row['response']['raw_sha256'],
                }
                dest.import_complete(row['key'],expected,row['reserved'],row['response'],row['cost'],row['usage'],provenance)
            spent=sum(row['cost'] for _,row,_ in imported)
            cap=source_config['CAP_MICRO_USD']
            c018=next((card for card in cards if card['CANDIDATE_ID']=='C018'),None)
            report={
                'STATUS':DERIVED_STATUS,'SOURCE_RUN_ID':source_config['RUN_ID'],'DEST_RUN_ID':dest_dir.name,
                'IMPORTED_GENERATION_ROUNDS':[item[1]['request']['slot'] for item in imported],
                'IMPORTED_CALL_KEYS':[item[1]['key'] for item in imported],
                'IMPORTED_COST_MICRO_USD':spent,'CAP_MICRO_USD':cap,
                'REMAINING_MICRO_USD':cap-spent,'CARD_IDS':[card['CANDIDATE_ID'] for card in cards],
                'C018_REVALIDATION':'PASS' if c018 is not None else 'ABSENT',
                'CARDS_WRITTEN':False,'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,
            }
            with dest.transaction():
                dest.set('status',DERIVED_STATUS)
                dest.event('DERIVED_IMPORT',report)
        except Exception:
            dest.close();raise
        dest.close()
    finally:
        source.close()
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
            spent=ledger.spent_micro_usd()
            if type(spent) is not int or spent<0:raise ContractError('invalid spent')
            if spent>new:raise ContractError('new cap below spent')
            ledger.set('config',{**cfg,'CAP_MICRO_USD':new})
            payload={
                'OLD_CAP_MICRO_USD':old,'NEW_CAP_MICRO_USD':new,
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
