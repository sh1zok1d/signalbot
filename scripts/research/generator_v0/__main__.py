"""Canonical shadow-only operator entry point."""
import argparse
import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from .context import Contexts,ContractError,canonical,digest,byte_digest
from .ledger import Ledger
from .provider import Caller,MockProvider
from .mock import MockResponder
from .runner import run_campaign,GENERATOR_PROMPT

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
    p.add_argument('command',choices=['preflight','run','resume','review','mutate','inspect'])
    p.add_argument('--provider',choices=['mock','openai'],default='mock')
    p.add_argument('--run-dir',type=Path,default=Path('artifacts/generator_v0/first-shadow'))
    p.add_argument('--size',type=int,default=40)
    p.add_argument('--allow-real-llm',action='store_true')
    p.add_argument('--budget-usd',default='0')
    p.add_argument('--model',default=os.environ.get('GENERATOR_V0_MODEL','gpt-4.1-mini-2025-04-14'))
    p.add_argument('--candidate-id')
    p.add_argument('--decision',choices=['ACCEPT_FOR_FUTURE_DESIGN','REJECT','DEFER'])
    p.add_argument('--reason')
    p.add_argument('--actor')
    p.add_argument('--active-minutes',type=float,default=0)
    p.add_argument('--field')
    p.add_argument('--value-json')
    a=p.parse_args(argv)
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
    if a.provider=='openai':
        from .openai_provider import OpenAIProvider
        provider=OpenAIProvider(os.environ.get('OPENAI_API_KEY',''),allow_real=a.allow_real_llm,budget_micro_usd=cap,model=a.model)
    else:
        if cap or a.allow_real_llm:raise ContractError('mock requires zero budget and no real authorization')
        provider=MockProvider(MockResponder(c))
    if a.command=='preflight':
        print(canonical({'STATUS':'PREFLIGHT_PASS','PROVIDER':provider.provider_id,'REAL_LLM_CALLS_MADE':False,'BATCH_SIZE':a.size}));return
    dbpath=a.run_dir/'run.sqlite'
    if a.command=='run' and dbpath.exists():raise ContractError('run exists; use resume')
    if a.command=='resume' and not dbpath.exists():raise ContractError('run not found')
    a.run_dir.mkdir(parents=True,exist_ok=True)
    config={'RUN_ID':a.run_dir.name,'PROVIDER':provider.provider_id,'MODEL':provider.model_id,'SIZE':a.size,'CAP_MICRO_USD':cap,'CONTEXT_DIGEST':digest(c.generator()),'IMPLEMENTATION_DIGEST':digest({x.name:byte_digest(x) for x in sorted(Path(__file__).parent.glob('*.py'))})}
    l=Ledger(dbpath,config)
    try:
        result=run_campaign(c,Caller(c,l,provider,cap,a.allow_real_llm),a.size)
        atomic_json(a.run_dir/'shadow_registry.json',result)
        atomic_json(a.run_dir/'data_gap_ledger.json',result['DATA_GAP_LEDGER_V0'])
        atomic_json(a.run_dir/'human_review_queue.json',{'STATUS':result['STATUS'],'SHORTLIST':result['SHORTLIST']})
        atomic_json(a.run_dir/'run_ledger.json',{'RUN_ID':config['RUN_ID'],'CALLS':l.export_calls(),'PARSED_CARD':result['CANDIDATES'],'CRITIC_OUTPUTS':result['REVIEWS'],'FINAL_DECISION':result['STATUS'],'HUMAN_MUTATIONS':[json.loads(x[0]) for x in l.db.execute("SELECT payload FROM events WHERE kind='HUMAN_MUTATION' ORDER BY n")]})
        print(canonical({'RUN_ID':config['RUN_ID'],'STATUS':result['STATUS'],'SEMANTIC_RESULT_DIGEST':result['SEMANTIC_RESULT_DIGEST'],'CANDIDATES':len(result['CANDIDATES']),'STREAM_A_N':len(result['STREAM_A']),'STREAM_B_N':len(result['STREAM_B']),'SHORTLIST_N':len(result['SHORTLIST'])}))
    finally:l.close()

if __name__=='__main__':
    try:main()
    except (ContractError,OSError,ValueError) as e:raise SystemExit(str(e))
