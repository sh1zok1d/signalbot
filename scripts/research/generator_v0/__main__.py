"""Canonical shadow-only operator entry point."""
import argparse
import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from .context import Contexts,ContractError,canonical,digest,byte_digest
from .ledger import Ledger,SEALED_REGISTRY,sealed_reason
from .provider import Caller,MockProvider
from .mock import MockResponder
from .runner import run_campaign,GENERATOR_PROMPT,generator_max_output_tokens
from .derive import derive_complete_rounds,authorize_derived_continuation,authorize_budget_extension,remaining_campaign_budget_preflight,fresh_campaign_budget_preflight,reconcile_call,OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD
from .ledger import InfrastructureStop

ARCHIVED_PAID_RUNS={
    ('generator_v0','first-shadow'),
    ('generator_v0','first-shadow-v2'),
    ('generator_v0','first-shadow-v3'),
    ('generator_v0','first-shadow-v4'),
    ('generator_v0','first-shadow-v5'),
    ('generator_v0','first-shadow-v6'),
    ('generator_v0','first-shadow-v7'),
}


def archived_paid_run(path):
    return len(path.parts)>=2 and tuple(path.parts[-2:]) in ARCHIVED_PAID_RUNS

def sealed_journal(run_dir):
    """True if run_dir/run.sqlite is sealed (registry content hash or meta SEALED).
    The same check runs inside Ledger itself; this CLI check also stops report writes."""
    return sealed_reason(Path(run_dir)/'run.sqlite') is not None

def _journal_bound_provider(run_dir):
    """Offline bound path matching the journal's own routing (routed journals record ROUTING_ID;
    V03 ladder journals use the ladder routes)."""
    dbpath=Path(run_dir)/'run.sqlite'
    if not dbpath.exists():return None
    l=Ledger.open_readonly(dbpath)
    try:
        config=l.get('config') or {}
        routed=config.get('ROUTING_ID') is not None
    finally:l.close()
    if not routed:return None
    from .routed_provider import offline_routed_provider
    from .routing import routes_for_contract
    return offline_routed_provider(Contexts(),routes_for_contract(config.get('GENERATOR_CONTRACT')))

def checkpointer_from_args(a,run_dir):
    """External journal checkpoint target. Required for live V03 ladder runs and resumes."""
    from .checkpoint import DirectoryCheckpointer,GitCheckpointer
    if a.checkpoint_dir and a.checkpoint_git_branch:raise ContractError('choose one checkpoint target: --checkpoint-dir or --checkpoint-git-branch')
    if a.checkpoint_dir:
        dest=Path(a.checkpoint_dir).resolve()
        if dest==Path(run_dir).resolve():raise ContractError('the checkpoint directory must differ from the run directory')
        return DirectoryCheckpointer(dest)
    if a.checkpoint_git_branch:
        import subprocess
        top=subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,text=True)
        if top.returncode!=0:raise ContractError('--checkpoint-git-branch must run inside a git checkout')
        repo=Path(top.stdout.strip()).resolve()
        try:rel=(Path(run_dir).resolve()/'checkpoint').relative_to(repo)
        except ValueError:raise ContractError('--checkpoint-git-branch needs the run directory inside the checkout')
        return GitCheckpointer(repo,rel,a.checkpoint_git_branch)
    return None

def refuse_sealed_or_archived(run_dir):
    if archived_paid_run(run_dir):raise ContractError('archived paid run is read-only and must not be opened by this operator')
    if sealed_journal(run_dir):raise ContractError('sealed journal is read-only and must not be opened by this operator')

def atomic_json(path,value):
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def main(argv=None):
    p=argparse.ArgumentParser(description='Generator V0 shadow only; stops at human review')
    p.add_argument('command',choices=['preflight','run','resume','review','mutate','inspect','derive','authorize-derived-continuation','authorize-budget-extension','remaining-budget-preflight','reconcile','first-30-card','ladder-40-card'])
    p.add_argument('--source-run-dir',type=Path)
    p.add_argument('--through-generation',type=int,default=1)
    p.add_argument('--provider',choices=['mock','openai','routed'],default='mock',help='routed = multi-provider routing (Opus generator, Sol/Luna critics); openai = legacy OpenAI-only path')
    p.add_argument('--run-dir',type=Path,default=Path('artifacts/generator_v0/shadow'))
    p.add_argument('--size',type=int,default=40)
    p.add_argument('--allow-real-llm',action='store_true')
    p.add_argument('--budget-usd',default='0')
    p.add_argument('--model',default=None)
    p.add_argument('--candidate-id')
    p.add_argument('--decision',choices=['ACCEPT_FOR_FUTURE_DESIGN','REJECT','DEFER'])
    p.add_argument('--reason')
    p.add_argument('--actor')
    p.add_argument('--new-cap-usd')
    p.add_argument('--call-key')
    p.add_argument('--resolution',choices=['NOT_BILLED','BILLED','UNKNOWN'])
    p.add_argument('--cost-usd')
    p.add_argument('--evidence',default='')
    p.add_argument('--active-minutes',type=float,default=0)
    p.add_argument('--accept-budget-stop',action='store_true',help='live run/resume even though the worst case exceeds the authorized remainder (requires --actor and --reason; recorded)')
    p.add_argument('--openai-network-mode',choices=['DIRECT','CLOUD_PROXY'],default=None,help='explicit OpenAI transport for routed runs; ladder-40-card defaults to CLOUD_PROXY, while DIRECT is supported for Cursor/local environments; never inferred from HTTPS_PROXY')
    p.add_argument('--contract',choices=['V02','V03'],default='V02',help='V03 = complexity-ladder card contract (40 slots)')
    p.add_argument('--checkpoint-dir',type=Path,help='external journal checkpoint: a directory on durable storage')
    p.add_argument('--checkpoint-git-branch',help='external journal checkpoint: commit <run-dir>/checkpoint/ and push this (current) branch')
    p.add_argument('--field')
    p.add_argument('--value-json')
    a=p.parse_args(argv)
    if a.command=='first-30-card':
        a.size=30;a.provider='routed';a.openai_network_mode='CLOUD_PROXY'
        if a.contract!='V02':raise ContractError('first-30-card is the frozen V02 campaign')
        if not a.allow_real_llm:raise ContractError('first-30-card requires --allow-real-llm and a nonzero budget')
    if a.command=='ladder-40-card':
        a.size=40;a.provider='routed';a.contract='V03'
        if a.openai_network_mode is None:a.openai_network_mode='CLOUD_PROXY'
        if not a.allow_real_llm:raise ContractError('ladder-40-card requires --allow-real-llm and a nonzero budget')
    if a.openai_network_mode is None:a.openai_network_mode='DIRECT'
    from .runner import campaign_plan
    contract_id={'V02':'GENERATOR_CONTRACT_V02','V03':'GENERATOR_CONTRACT_V03'}[a.contract]
    if a.contract=='V03' and a.size!=40:raise ContractError('the V03 ladder plan is frozen for 40 slots')
    if a.provider!='routed' and a.openai_network_mode!='DIRECT':raise ContractError('CLOUD_PROXY applies only to the routed provider')
    if a.command=='derive':
        refuse_sealed_or_archived(a.run_dir)
        if a.allow_real_llm or a.provider in ('openai','routed') or Decimal(a.budget_usd)!=0:
            raise ContractError('derive is offline; do not authorize a provider or budget')
        if a.source_run_dir is None:raise ContractError('source run required')
        c=Contexts();c.validate('GENERATOR',c.generator(),GENERATOR_PROMPT)
        report=derive_complete_rounds(a.source_run_dir,a.run_dir,a.through_generation,c)
        atomic_json(a.run_dir/'derived_import.json',report)
        print(canonical(report));return
    if a.command=='authorize-derived-continuation':
        refuse_sealed_or_archived(a.run_dir)
        if a.allow_real_llm or a.provider in ('openai','routed') or Decimal(a.budget_usd)!=0:
            raise ContractError('authorize-derived-continuation is offline; do not authorize a provider or budget')
        report=authorize_derived_continuation(a.run_dir,a.actor,a.reason)
        print(canonical(report));return
    if a.command=='authorize-budget-extension':
        refuse_sealed_or_archived(a.run_dir)
        if a.allow_real_llm or a.provider in ('openai','routed') or Decimal(a.budget_usd)!=0:
            raise ContractError('authorize-budget-extension is offline; do not authorize a provider or budget')
        report=authorize_budget_extension(a.run_dir,a.actor,a.reason,a.new_cap_usd)
        print(canonical(report));return
    if a.command=='remaining-budget-preflight':
        refuse_sealed_or_archived(a.run_dir)
        if a.allow_real_llm or a.provider in ('openai','routed') or Decimal(a.budget_usd)!=0:
            raise ContractError('remaining-budget-preflight is offline; do not authorize a provider or budget')
        report=remaining_campaign_budget_preflight(a.run_dir,bound_provider=_journal_bound_provider(a.run_dir))
        print(canonical(report));return
    if a.command=='reconcile':
        refuse_sealed_or_archived(a.run_dir)
        if a.allow_real_llm or a.provider in ('openai','routed') or Decimal(a.budget_usd)!=0:
            raise ContractError('reconcile is offline; do not authorize a provider or budget')
        if not a.call_key or not a.resolution:raise ContractError('call key and resolution required')
        report=reconcile_call(a.run_dir,a.call_key,a.resolution,a.cost_usd,a.actor,a.reason,a.evidence)
        print(canonical(report));return
    refuse_sealed_or_archived(a.run_dir)
    c=Contexts();c.validate('GENERATOR',c.generator(),GENERATOR_PROMPT)
    if not 25<=a.size<=50:raise ContractError('batch size')
    if a.command in ('review','mutate','inspect'):
        from .operator import adjudicate,registry
        from .schema import validate_card,parse_json
        dbpath=a.run_dir/'run.sqlite'
        if not dbpath.exists():raise ContractError('run not found')
        l=Ledger(dbpath)
        try:
            if a.command=='review':adjudicate(l,a.candidate_id,a.decision,a.reason,a.actor,a.active_minutes)
            if a.command=='mutate':
                if not all((a.candidate_id,a.field,a.value_json,a.reason,a.actor)):raise ContractError('mutation fields required')
                l.mutate(a.candidate_id,a.field,parse_json(a.value_json),a.reason,a.actor,lambda x:validate_card(x,c))
            view=registry(l)
            atomic_json(a.run_dir/'human_review_queue.json',view)
            if a.command=='mutate':
                atomic_json(a.run_dir/'shadow_registry.json',view)
                atomic_json(a.run_dir/'data_gap_ledger.json',{'STATUS':'MUTATED_REQUIRES_REVIEW'})
            atomic_json(a.run_dir/'human_events.json',view['HUMAN_EVENTS'])
            print(canonical(view))
        finally:l.close()
        return
    amount=Decimal(a.budget_usd)
    if not amount.is_finite() or not 0<=amount<=30 or amount*1_000_000 != (amount*1_000_000).to_integral_value():raise ContractError('budget must be finite USD 0..30, at microdollar precision')
    cap=int(amount*1_000_000)
    if a.command in ('run','resume','first-30-card','ladder-40-card') and a.provider in ('openai','routed') and cap>OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD:
        raise ContractError('live campaign cap exceeds owner-authorized total USD 17.100000')
    if a.provider=='routed':
        from .routed_provider import live_routed_provider,offline_routed_provider,routed_run_identity
        if a.model or os.environ.get('GENERATOR_V0_MODEL'):raise ContractError('the routing registry is authoritative; do not pass --model or GENERATOR_V0_MODEL')
        from .routing import routes_for_contract
        routes=routes_for_contract(contract_id)
        if a.allow_real_llm:provider=live_routed_provider(c,cap,os.environ,openai_network_mode=a.openai_network_mode,routes=routes)
        elif a.command in ('run','resume','first-30-card','ladder-40-card'):raise ContractError('routed run/resume requires --allow-real-llm and a nonzero budget')
        else:provider=offline_routed_provider(c,routes)
    elif a.provider=='openai':
        from .openai_provider import OpenAIProvider
        from .models import ROLE_MODEL_MAP,ROLE_REQUEST_PARAMS,price_table
        if a.model or os.environ.get('GENERATOR_V0_MODEL'):raise ContractError('role-specific model map is authoritative; do not pass --model or GENERATOR_V0_MODEL')
        provider=OpenAIProvider(os.environ.get('OPENAI_API_KEY',''),allow_real=a.allow_real_llm,budget_micro_usd=cap)
    else:
        if cap or a.allow_real_llm:raise ContractError('mock requires zero budget and no real authorization')
        if a.model:raise ContractError('mock does not take a real model id')
        provider=MockProvider(MockResponder(c))
    if a.command=='preflight':
        info={'STATUS':'PREFLIGHT_PASS','PROVIDER':provider.provider_id,'REAL_LLM_CALLS_MADE':False,'BATCH_SIZE':a.size,'STRUCTURED_OUTPUTS_ENABLED':a.provider=='openai','GENERATOR_MAX_OUTPUT_TOKENS':generator_max_output_tokens(provider)}
        if a.contract=='V03':info['GENERATOR_CONTRACT']=contract_id;campaign_plan(contract_id,a.size)
        if a.provider=='routed':
            pre=fresh_campaign_budget_preflight(a.size,cap or OWNER_AUTHORIZED_CAMPAIGN_CAP_MICRO_USD,c,bound_provider=offline_routed_provider(c,routes),contract_id=contract_id)
            info.update(STRUCTURED_OUTPUTS_ENABLED=True,**routed_run_identity(provider,c),
                        FRESH_WORST_CASE_SINGLE_ATTEMPT_MICRO_USD=pre['WORST_CASE_REMAINING_MICRO_USD'],
                        FRESH_WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD=pre['WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD'],
                        FRESH_BOUND_STAGES={x['STAGE']:x['BOUND_MICRO_USD'] for x in pre['STAGES']})
        if a.provider=='openai':
            ident=provider.transport_identity()
            info.update(ROLE_MODEL_MAP=dict(ROLE_MODEL_MAP),ROLE_REQUEST_PARAMS=dict(ROLE_REQUEST_PARAMS),ROUTING_DIGEST=provider.routing_digest,REQUEST_TIMEOUT_SECONDS=provider.request_timeout_seconds,**ident)
        print(canonical(info));return
    dbpath=a.run_dir/'run.sqlite'
    if a.command in ('run','first-30-card','ladder-40-card') and dbpath.exists():raise ContractError('run exists; use resume')
    if a.command=='resume' and not dbpath.exists():raise ContractError('run not found')
    def live_budget_gate(pre):
        """Worst case must fit the authorized remainder, or the operator explicitly
        accepts a clean STOPPED_BUDGET (recorded with actor and reason). Offline."""
        gate={k:pre[k] for k in ('CAP_MICRO_USD','SPENT_MICRO_USD','REMAINING_AUTHORIZED_MICRO_USD','WORST_CASE_REMAINING_MICRO_USD','WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD','FITS_AUTHORIZED_REMAINING','FITS_WITH_CONTENT_RETRIES')}
        if not pre['FITS_AUTHORIZED_REMAINING']:
            if not a.accept_budget_stop:
                raise ContractError('worst-case remaining reservation does not fit the authorized remainder: '+canonical(gate)+'; pass --accept-budget-stop with --actor and --reason to accept a clean STOPPED_BUDGET')
            if not a.actor or not a.reason:raise ContractError('--accept-budget-stop requires --actor and --reason')
        return gate
    budget_gate=None
    if a.provider=='openai' and a.command=='run':budget_gate=live_budget_gate(fresh_campaign_budget_preflight(a.size,cap,c,contract_id=contract_id))
    if a.provider=='routed' and a.command in ('run','first-30-card','ladder-40-card'):budget_gate=live_budget_gate(fresh_campaign_budget_preflight(a.size,cap,c,bound_provider=offline_routed_provider(c,routes),contract_id=contract_id))
    checkpointer=None
    if a.command in ('run','resume','ladder-40-card') and a.contract=='V03' and a.allow_real_llm:
        # ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1: paid provider state leaves the machine.
        checkpointer=checkpointer_from_args(a,a.run_dir)
        if checkpointer is None:raise ContractError('a live V03 ladder run needs an external journal checkpoint: --checkpoint-git-branch <current branch> or --checkpoint-dir <durable dir>')
    elif a.checkpoint_dir or a.checkpoint_git_branch:
        checkpointer=checkpointer_from_args(a,a.run_dir)
    a.run_dir.mkdir(parents=True,exist_ok=True)
    config={'RUN_ID':a.run_dir.name,'PROVIDER':provider.provider_id,'MODEL':provider.model_id,'SIZE':a.size,'CAP_MICRO_USD':cap,'CONTEXT_DIGEST':digest(c.generator()),'IMPLEMENTATION_DIGEST':digest({x.name:byte_digest(x) for x in sorted(Path(__file__).parent.glob('*.py'))}),'GENERATOR_MAX_OUTPUT_TOKENS':generator_max_output_tokens(provider)}
    if a.contract=='V03':
        from .runner import ladder_config
        config=ladder_config(**config)
    if a.provider=='routed':
        config.update(**routed_run_identity(provider,c))
    if a.provider=='openai':
        ident=provider.transport_identity()
        config.update(ROLE_MODEL_MAP=dict(ROLE_MODEL_MAP),ROLE_REQUEST_PARAMS={k:dict(v) for k,v in ROLE_REQUEST_PARAMS.items()},PRICE_TABLE=price_table(),ROUTING_DIGEST=provider.routing_digest,REQUEST_TIMEOUT_SECONDS=provider.request_timeout_seconds,**ident)
    l=Ledger(dbpath,config)
    l.checkpointer=checkpointer
    try:
        caller=Caller(c,l,provider,cap,a.allow_real_llm)
        if a.provider in ('openai','routed') and a.command=='resume':
            from .runner import RESUMABLE_STATUSES
            if l.get('status') in RESUMABLE_STATUSES:budget_gate=live_budget_gate(remaining_campaign_budget_preflight(a.run_dir,c,bound_provider=_journal_bound_provider(a.run_dir)))
        if a.accept_budget_stop:
            # Same library semantics as any programmatic caller; run_campaign enforces it.
            from .runner import accept_budget_stop
            accept_budget_stop(c,caller,a.size,a.actor,a.reason)
        try:
            result=run_campaign(c,caller,a.size)
        except InfrastructureStop as e:
            if l.get('status')=='INCOMPLETE_BUDGET_STOP':
                from .runner import incomplete_progress
                atomic_json(a.run_dir/'incomplete_budget_stop.json',{'RUN_ID':config['RUN_ID'],'STATUS':'INCOMPLETE_BUDGET_STOP',**incomplete_progress(l),
                                                                    'SPEND_MICRO_USD':l.total_charged_micro_usd()})
            stop={'RUN_ID':config['RUN_ID'],'STATUS':l.get('status'),'STOP':type(e).__name__,'DETAIL':str(e)[:500],'SPEND_MICRO_USD':l.total_charged_micro_usd(),
                  'OPEN_PROVIDER_CALLS':l.provider_handles()}
            if checkpointer is not None:stop['CHECKPOINT']=dict(checkpointer.describe(),LAST_SEQUENCE=checkpointer.sequence,ERROR=getattr(e,'checkpoint_error',None))
            print(canonical(stop))
            raise
        atomic_json(a.run_dir/'shadow_registry.json',result)
        atomic_json(a.run_dir/'data_gap_ledger.json',result.get('DATA_GAP_LEDGER_V0',[]))
        atomic_json(a.run_dir/'human_review_queue.json',{'STATUS':result['STATUS'],'SHORTLIST':result.get('SHORTLIST',[])})
        atomic_json(a.run_dir/'run_ledger.json',{'RUN_ID':config['RUN_ID'],'CALLS':l.export_calls(),'CANDIDATE_INTAKE':l.candidates(),'PARSED_CARD':result.get('CANDIDATES',[]),'CRITIC_OUTPUTS':result.get('REVIEWS',[]),'FINAL_DECISION':result['STATUS'],'HUMAN_MUTATIONS':[json.loads(x[0]) for x in l.db.execute("SELECT payload FROM events WHERE kind='HUMAN_MUTATION' ORDER BY n")]})
        print(canonical({'RUN_ID':config['RUN_ID'],'STATUS':result['STATUS'],'SEMANTIC_RESULT_DIGEST':result['SEMANTIC_RESULT_DIGEST'],'CANDIDATES':len(result.get('CANDIDATES',[])),'METRICS':result.get('METRICS'),'SPEND':result.get('SPEND'),'STREAM_A_N':len(result.get('STREAM_A',[])),'STREAM_B_N':len(result.get('STREAM_B',[])),'SHORTLIST_N':len(result.get('SHORTLIST',[]))}))
    finally:l.close()

if __name__=='__main__':
    try:main()
    except (ContractError,OSError,ValueError) as e:raise SystemExit(str(e))
