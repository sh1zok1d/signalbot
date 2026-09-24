"""Write docs/research/generator_v0_repair/OFFLINE_GATE_REPORT.json. Offline only.

    python -m scripts.research.generator_v0_gate
"""
from __future__ import annotations
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from scripts.research.generator_v0.context import Contexts
from scripts.research.generator_v0.derive import derive_complete_rounds,remaining_campaign_budget_preflight,fresh_campaign_budget_preflight
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0 import contract
from .noisy import run_noisy_campaign,run_mixed_noisy_campaign,derive_after_partial_work

REPO=Path(__file__).resolve().parents[3]
REPORT=REPO/'docs/research/generator_v0_repair/OFFLINE_GATE_REPORT.json'
V7=REPO/'docs/research/generator_v0_first_shadow_v7/run.sqlite'

def build():
    import sys
    sys.path.insert(0,str(REPO))
    from tests.research.test_generator_v0_corpus import evaluate,corpus_metrics
    from .corpus import build_corpus
    c=Contexts()
    corpus=corpus_metrics(evaluate(build_corpus(),c))
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        noisy,l,_=run_noisy_campaign(tmp/'noisy',contexts=c);l.close()
        mixed,l,_=run_mixed_noisy_campaign(tmp/'mixed',contexts=c);l.close()
        partial=derive_after_partial_work(tmp/'partial',contexts=c)
        src=tmp/'v7';src.mkdir();shutil.copy(V7,src/'run.sqlite')
        # first-shadow-v7 ran under the pre-GV0CAL memory (memory-chain event LEGACY_BOOTSTRAP).
        v7c=Contexts(memory_event='LEGACY_BOOTSTRAP')
        v7=derive_complete_rounds(src,tmp/'v8',2,v7c)
        led=Ledger(tmp/'v8'/'run.sqlite');prior=led.get('lineage')['PRIOR_ATTEMPTS'];led.close()
        pre=remaining_campaign_budget_preflight(tmp/'v8',v7c)
        fresh=fresh_campaign_budget_preflight(40,17_100_000,c)
        v7_sha_after=hashlib.sha256((src/'run.sqlite').read_bytes()).hexdigest()
    noisy.pop('SELECTOR_ADVISORY',None)
    return {
        'UNIT':'GENERATOR_V0_LIMITED_REPAIR_OFFLINE_GATE','CONTRACT':contract.CONTRACT_ID,
        'CORPUS':corpus,
        'NOISY_E2E':noisy,
        'MIXED_PROVIDER_NOISY_E2E':{k:v for k,v in mixed.items() if k!='SELECTOR_ADVISORY'},
        'DERIVE_AFTER_PARTIAL_WORK':partial,
        'V7_DERIVE_PROOF':{
            'SOURCE_JOURNAL_SHA256_BEFORE_AND_AFTER':v7_sha_after,
            'IMPORTED_GENERATION_ROUNDS':v7['IMPORTED_GENERATION_ROUNDS'],'IMPORTED_CONTRACTS':v7['IMPORTED_CONTRACTS'],
            'IMPORTED_COST_MICRO_USD':v7['IMPORTED_COST_MICRO_USD'],'LINEAGE_PRIOR_MICRO_USD':v7['LINEAGE_PRIOR_MICRO_USD'],
            'LINEAGE_TOTAL_MICRO_USD':v7['LINEAGE_TOTAL_MICRO_USD'],'REMAINING_MICRO_USD':v7['REMAINING_MICRO_USD'],
            'PRIOR_ATTEMPT':{'SLOT':prior[0]['SLOT'],'CHARGED_MICRO_USD':prior[0]['CHARGED_MICRO_USD'],
                             'INTAKE_VERDICTS':{x['CANDIDATE_ID']:x['VERDICT'] for x in prior[0]['INTAKE']['CARDS']}},
        },
        'FRESH_BUDGET_PREFLIGHT':{k:fresh[k] for k in ('SPENT_MICRO_USD','REMAINING_AUTHORIZED_MICRO_USD','WORST_CASE_REMAINING_MICRO_USD','WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD','FITS_AUTHORIZED_REMAINING','FITS_WITH_CONTENT_RETRIES','PROXY_CARDS','PROXY_CARD_BYTES','PROXY_SIGNATURE_BYTES','PROXY_MARGIN','STAGES')},
        'V8_REMAINING_BUDGET_PREFLIGHT':{k:pre[k] for k in ('SPENT_MICRO_USD','REMAINING_AUTHORIZED_MICRO_USD','WORST_CASE_REMAINING_MICRO_USD','WORST_CASE_WITH_CONTENT_RETRIES_MICRO_USD','FITS_AUTHORIZED_REMAINING','FITS_WITH_CONTENT_RETRIES','PROXY_CARDS','PROXY_CARD_BYTES','PROXY_SIGNATURE_BYTES','PROXY_MARGIN','STAGES')},
        'REAL_LLM_CALLS_MADE':False,'SCIENTIFIC_OUTCOMES_COMPUTED':False,'PROTECTED_2025_2026_OPENED':False,
        'CORPUS_AUTHOR_NOTE':'The corpus was written by the implementer of the repair. The PR #215 verifier corpus was run as external regression evidence only (not copied): see EXTERNAL_REGRESSION in the repair record.',
    }

def main():
    report=build()
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'CORPUS':report['CORPUS']['CORPUS_SIZE'],'UNSAFE_ADMITTED':report['CORPUS']['UNSAFE_ADMITTED'],'NOISY_STATUS':report['NOISY_E2E']['STATUS'],'V7_LINEAGE_TOTAL':report['V7_DERIVE_PROOF']['LINEAGE_TOTAL_MICRO_USD']}))

if __name__=='__main__':
    main()
