"""Zero-cost rehearsal of the live ladder-40-card orchestration (AGENT_RUNTIME_PROTOCOL section 9).

The production RoutedProvider on the ladder routes (LADDER_ROUTES), AnthropicProvider (compact wire
through Message Batches) and OpenAIProvider (background Responses and Chat Completions) run against
fake transports and a fake clock: no network, no paid call. Covers call
counts, budget reservations under the USD 12 cap, candidate flow, critic ordering, stop conditions
(budget and provider throttling) and resume without replaying completed calls.
"""
import json
from collections import Counter

import pytest

from scripts.research.generator_v0.context import Contexts
from scripts.research.generator_v0.derive import authorize_budget_extension
from scripts.research.generator_v0.ledger import BudgetExceeded, Ledger
from scripts.research.generator_v0.provider import Caller, ProviderThrottled
from scripts.research.generator_v0.runner import accept_budget_stop, ladder_config, run_campaign
from scripts.research.generator_v0_gate.noisy import FakeClock, NoisyTransport, ladder_provider_for
from scripts.research.generator_v0 import memory_finalizer as fin
from tests.research.test_generator_v0_first_30_production_path import GV0CAL_HEAD
from tests.research.test_generator_v0_memory_finalizer import finalized_root

CAP_USD12 = 12_000_000


def ladder(run_dir, cap, faults=None, transport=None):
    c = Contexts(memory_event=GV0CAL_HEAD)
    transport = transport or NoisyTransport(c, faults or {})
    ledger = Ledger(run_dir / 'run.sqlite', ladder_config(RUN_ID=run_dir.name, SIZE=40, CAP_MICRO_USD=cap))
    caller = Caller(c, ledger, ladder_provider_for(transport, c, FakeClock()), cap, True)
    return c, ledger, caller, transport


def roles(ledger):
    return Counter(r['ROLE'] for r in ledger.export_calls())


def test_full_zero_cost_ladder_campaign_under_the_usd12_cap(tmp_path):
    d = tmp_path / 'full'
    d.mkdir()
    c, ledger, caller, transport = ladder(d, CAP_USD12)
    accept_budget_stop(c, caller, 40, 'rehearsal', 'worst case exceeds the USD 12 cap; clean stop accepted')
    result = run_campaign(c, caller)
    try:
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and result['CONTRACT'] == 'GENERATOR_CONTRACT_V03'
        assert roles(ledger) == {'GENERATOR': 4, 'NOVELTY_CRITIC': 40, 'FEASIBILITY_CRITIC': 40, 'RED_TEAM': 40, 'SELECTOR': 1}
        assert result['METRICS']['VALID'] == 40 and result['METRICS']['REVIEWED'] == 40
        assert Counter(x['COMPLEXITY_CLASS'] for x in result['CANDIDATES']) == {'ATOMIC': 16, 'CONDITIONAL': 14, 'INTERACTION': 7, 'COMPOSITE': 3}
        assert [s['SEAT'] for s in result['SHORTLIST_RULE']['SEATS']] == ['ATOMIC', 'ATOMIC', 'CONDITIONAL', 'CONDITIONAL', 'COMPLEX']
        assert ledger.total_charged_micro_usd() <= CAP_USD12
        gen = [x for x in ledger.export_calls() if x['ROLE'] == 'GENERATOR']
        assert {x['PROMPT_VERSION'] for x in gen} == {'generator-v0.3'}
        # critic ordering: every card is reviewed by novelty, feasibility and red team, after all generation
        calls = [x['ROLE'] for x in ledger.export_calls()]
        assert calls[:4] == ['GENERATOR'] * 4 and calls[-1] == 'SELECTOR'
        root = finalized_root(tmp_path)
        dry = fin.finalize(root, fin.source_from_run_journal(d / 'run.sqlite', 'GVLADREH'))
        assert dry['STATUS'] == 'DRY_RUN' and dry['ATTEMPT_RECORDS'] == 40
    finally:
        ledger.close()


def test_budget_stop_mid_campaign_then_same_run_resume(tmp_path):
    d = tmp_path / 'budget'
    d.mkdir()
    c, ledger, caller, transport = ladder(d, 1_250_000)            # the round-2 generator reservation (batch price) does not fit
    accept_budget_stop(c, caller, 40, 'rehearsal', 'force a mid-campaign stop')
    with pytest.raises(BudgetExceeded):
        run_campaign(c, caller)
    assert ledger.get('status') == 'INCOMPLETE_BUDGET_STOP'
    assert ledger.db.execute("SELECT 1 FROM results WHERE key='campaign'").fetchone() is None
    posts_before = len(transport.posts())
    done_before = {x['CALL_KEY'] for x in ledger.export_calls() if x['STATE'] == 'COMPLETE'}
    assert roles(ledger)['GENERATOR'] == 2 and len(done_before) == 2 and 'NOVELTY_CRITIC' not in roles(ledger)
    ledger.close()
    authorize_budget_extension(d, 'rehearsal', 'extension after the rehearsed stop', '12.00')
    ledger = Ledger(d / 'run.sqlite')
    c2 = Contexts(memory_event=GV0CAL_HEAD)
    caller2 = Caller(c2, ledger, ladder_provider_for(transport, c2, FakeClock()), CAP_USD12, True)
    try:
        accept_budget_stop(c2, caller2, 40, 'rehearsal', 'resume: acceptance is bound to the new snapshot')
        result = run_campaign(c2, caller2)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        new_posts = transport.posts()[posts_before:]
        assert len(new_posts) == 125 - len(done_before)                   # completed calls were not replayed
        assert roles(ledger) == {'GENERATOR': 4, 'NOVELTY_CRITIC': 40, 'FEASIBILITY_CRITIC': 40, 'RED_TEAM': 40, 'SELECTOR': 1}
    finally:
        ledger.close()


def test_provider_throttling_pauses_the_run_for_resume_without_replay(tmp_path):
    d = tmp_path / 'throttle'
    d.mkdir()
    faults = {('NOVELTY_CRITIC', 'C005', k): '429' for k in range(1, 4)}
    c, ledger, caller, transport = ladder(d, CAP_USD12, faults)
    accept_budget_stop(c, caller, 40, 'rehearsal', 'clean stop accepted')
    with pytest.raises(ProviderThrottled):
        run_campaign(c, caller)
    assert ledger.get('status') == 'PAUSED_PROVIDER_THROTTLED'           # infrastructure pause, not a budget stop
    complete = {x['CALL_KEY'] for x in ledger.export_calls() if x['STATE'] == 'COMPLETE'}
    ledger.close()
    ledger = Ledger(d / 'run.sqlite')
    c2 = Contexts(memory_event=GV0CAL_HEAD)
    clean = NoisyTransport(c2, {})
    caller2 = Caller(c2, ledger, ladder_provider_for(clean, c2, FakeClock()), CAP_USD12, True)
    try:
        accept_budget_stop(c2, caller2, 40, 'rehearsal', 'resume: acceptance is bound to the new snapshot')
        result = run_campaign(c2, caller2)                                 # same run, infrastructure fixed
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert len(clean.posts()) == 125 - len(complete)                    # nothing already complete was sent again
    finally:
        ledger.close()
