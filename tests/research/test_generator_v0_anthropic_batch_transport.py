"""ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1: the ladder GENERATOR through Message Batches.

Offline crash/resume fault tests. The production RoutedProvider, AnthropicProvider (batch path),
OpenAIProvider, Caller, Ledger and runner run against fake transports and a fake clock: no
network, no paid call. Every test checks the property the owner asked for: after the provider
accepted a request it is never POSTed again, and a run ends COMPLETE or in a resumable state.
"""
import json
import sqlite3
import subprocess
from collections import Counter

import pytest

from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider
from scripts.research.generator_v0.checkpoint import CheckpointFailed, DirectoryCheckpointer, GitCheckpointer
from scripts.research.generator_v0.context import Contexts, ContractError
from scripts.research.generator_v0.ledger import CallUncertain, Ledger
from scripts.research.generator_v0.provider import BackgroundPending, Caller, ProviderRejected
from scripts.research.generator_v0.routed_provider import offline_routed_provider
from scripts.research.generator_v0.runner import accept_budget_stop, ladder_config, run_campaign
from scripts.research.generator_v0_gate.noisy import Crash, FakeClock, NoisyTransport, ladder_provider_for, routed_provider_for
from tests.research.test_generator_v0_first_30_production_path import GV0CAL_HEAD

CAP_USD12 = 12_000_000
BATCHES = '/v1/messages/batches'
# origin/main before this amendment: V02 routing is unchanged byte for byte.
V02_ROUTING_DIGEST = 'c636f14a9e48dc07f8ebca16666c80dd20343171a6535f3ec8c47d8f71afc596'
V02_ROUTED_IDENTITY_DIRECT = 'e44543e3f071ec2ecba3b91aacc020c032d586bd4e8b90b81e939fd2451da245'
# Batch prices (USD per MTok = micro-USD per token): input 2, output 10.
GEN_COST = 6000 * 2 + 9000 * 10


class Recorder:
    """Checkpointer that records stages and keeps a real directory snapshot."""

    def __init__(self, dest, fail_on=None):
        self.inner = DirectoryCheckpointer(dest)
        self.stages = []
        self.fail_on = fail_on

    @property
    def sequence(self):
        return self.inner.sequence

    def describe(self):
        return self.inner.describe()

    def __call__(self, ledger, stage, detail):
        self.stages.append(stage)
        if self.fail_on == stage:
            self.fail_on = None
            raise CheckpointFailed('synthetic: checkpoint target unavailable')
        return self.inner(ledger, stage, detail)


def start(run_dir, transport=None, faults=None, clock=None, cap=CAP_USD12, checkpointer=None, max_wait=3600):
    c = Contexts(memory_event=GV0CAL_HEAD)
    transport = transport or NoisyTransport(c, faults or {})
    clock = clock or FakeClock()
    ledger = Ledger(run_dir / 'run.sqlite', ladder_config(RUN_ID=run_dir.name, SIZE=40, CAP_MICRO_USD=cap))
    ledger.checkpointer = checkpointer
    caller = Caller(c, ledger, ladder_provider_for(transport, c, clock, max_wait), cap, True)
    return c, ledger, caller, transport, clock


def resume(run_dir, transport, clock, cap=CAP_USD12, checkpointer=None, max_wait=3600):
    c = Contexts(memory_event=GV0CAL_HEAD)
    ledger = Ledger(run_dir / 'run.sqlite')
    ledger.checkpointer = checkpointer
    caller = Caller(c, ledger, ladder_provider_for(transport, c, clock, max_wait), cap, True)
    return c, ledger, caller


def invoke(c, caller):
    accept_budget_stop(c, caller, 40, 'offline-test', 'worst case exceeds the cap; a clean stop is accepted')
    return run_campaign(c, caller)


def batch_posts(transport):
    return [x for x in transport.log if x == ('POST', BATCHES)]


def generator_rows(ledger):
    return [x for x in ledger.export_calls() if x['ROLE'] == 'GENERATOR']


def journal_text(path):
    db = sqlite3.connect(path)
    try:
        rows = []
        for table in ('calls', 'events', 'meta', 'candidates', 'results', 'cards'):
            rows += [repr(r) for r in db.execute('SELECT * FROM ' + table)]
        return '\n'.join(rows)
    finally:
        db.close()


# --- routing and request identity -----------------------------------------------------

def test_batch_route_is_ladder_only_and_v02_identity_is_unchanged():
    assert routing.routing_digest() == V02_ROUTING_DIGEST
    assert offline_routed_provider(Contexts()).routing_digest == V02_ROUTED_IDENTITY_DIRECT
    assert routing.routes_for_contract('GENERATOR_CONTRACT_V02') is routing.ROUTES
    assert routing.routes_for_contract('GENERATOR_CONTRACT_V03') is routing.LADDER_ROUTES
    ladder, v02 = routing.LADDER_ROUTES, routing.ROUTES
    assert ladder['NOVELTY_CRITIC'] == v02['NOVELTY_CRITIC'] and ladder['RED_TEAM'] == v02['RED_TEAM']
    # OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1: these two roles change transport only.
    for role in ('FEASIBILITY_CRITIC', 'SELECTOR'):
        strip = lambda r: {k: v for k, v in r.items() if k not in ('ENDPOINT', 'TRANSPORT', 'STRUCTURED_OUTPUT')}
        assert strip(ladder[role]) == strip(v02[role])
        assert ladder[role]['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND'
        assert v02[role]['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'
        assert ladder[role]['MODEL'] == v02[role]['MODEL'] and ladder[role]['PARAMS'] == v02[role]['PARAMS']
        assert ladder[role]['MAX_OUTPUT_TOKENS'] == v02[role]['MAX_OUTPUT_TOKENS']
    strip = lambda r: {k: v for k, v in r.items() if k not in ('ENDPOINT', 'TRANSPORT')}
    assert strip(ladder['GENERATOR']) == strip(v02['GENERATOR'])          # same model, effort, cap, output mode
    assert ladder['GENERATOR']['ENDPOINT'] == 'ANTHROPIC_MESSAGE_BATCHES' and v02['GENERATOR']['ENDPOINT'] == 'ANTHROPIC_MESSAGES'
    assert routing.prices_for(ladder['GENERATOR'])['OUTPUT'] * 2 == routing.PRICES['claude-opus-5-5']['OUTPUT']
    bad = {**ladder, 'RED_TEAM': {**ladder['RED_TEAM'], 'PROVIDER': 'ANTHROPIC', 'MODEL': 'claude-opus-5-5', 'PARAMS': {'effort': 'high'},
                                  'ENDPOINT': 'ANTHROPIC_MESSAGE_BATCHES', 'TRANSPORT': routing.ANTHROPIC_BATCH_TRANSPORT}}
    with pytest.raises(ContractError):
        routing.validate_routes(bad)
    tampered = {**ladder, 'GENERATOR': {**ladder['GENERATOR'], 'TRANSPORT': {**routing.ANTHROPIC_BATCH_TRANSPORT, 'BATCH_PRICES': {}}}}
    with pytest.raises(ContractError):
        routing.validate_routes(tampered)


def test_batch_request_is_the_synchronous_request_without_stream_at_half_price(tmp_path):
    d = tmp_path / 'ident'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d)
    try:
        invoke(c, caller)
        req = json.loads(ledger.db.execute("SELECT request FROM calls WHERE request LIKE '%\"generation:0\"%'").fetchone()[0])
        batch = AnthropicProvider(None, routes=routing.LADDER_ROUTES, contexts=c, offline=True)
        sync = AnthropicProvider(None, routes=routing.ROUTES, contexts=c, offline=True)
        params, body = batch.payload(req), sync.payload(req)
        assert 'stream' not in params and body.pop('stream') is False and params == body
        assert params['model'] == 'claude-opus-5-5' and params['max_tokens'] == 100000
        assert params['output_config']['effort'] == 'high' and params['output_config']['format']['type'] == 'json_schema'
        assert abs(2 * batch.bound(req) - sync.bound(req)) <= 200
        done = [json.loads(r[0]) for r in ledger.db.execute("SELECT response FROM calls WHERE json_extract(request,'$.role')='GENERATOR'")]
        cids = [x['provider_envelope']['custom_id'] for x in done]
        assert len(set(cids)) == 4 and all(x.startswith('gv0-') and len(x) == 64 for x in cids)
        assert all(x['response_id'] == x['provider_envelope']['id'] for x in done)
    finally:
        ledger.close()


# --- the happy path --------------------------------------------------------------------

def test_full_ladder_campaign_through_message_batches_with_external_checkpoints(tmp_path):
    d = tmp_path / 'full'
    d.mkdir()
    rec = Recorder(tmp_path / 'durable')
    c, ledger, caller, transport, clock = start(d, checkpointer=rec)
    try:
        result = invoke(c, caller)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and result['CONTRACT'] == 'GENERATOR_CONTRACT_V03'
        assert Counter(x['ROLE'] for x in ledger.export_calls()) == {'GENERATOR': 4, 'NOVELTY_CRITIC': 40, 'FEASIBILITY_CRITIC': 40, 'RED_TEAM': 40, 'SELECTOR': 1}
        assert [s['SEAT'] for s in result['SHORTLIST_RULE']['SEATS']] == ['ATOMIC', 'ATOMIC', 'CONDITIONAL', 'CONDITIONAL', 'COMPLEX']
        assert len(batch_posts(transport)) == 4 and not [x for x in transport.log if x == ('POST', '/v1/messages')]
        gen = generator_rows(ledger)
        assert {x['STATE'] for x in gen} == {'COMPLETE'} and {x['MODEL_PROVIDER'] for x in gen} == {'ANTHROPIC_MESSAGE_BATCHES'}
        assert all(x['RESPONSE_ID'].startswith('msgbatch_') and x['COST_MICRO_USD'] == GEN_COST for x in gen)
        assert all(x['USAGE']['service_tier'] == 'batch' for x in gen)
        # the stages the owner asked for: after provider acceptance and after every round / stage
        assert rec.stages.count('PROVIDER_ACCEPTED') == 4 and rec.stages.count('ROUND_COMPLETE') == 4
        assert rec.stages.count('REVIEW_BLOCK') == 3 and rec.stages[-1] == 'CAMPAIGN_RESULT'
        first = rec.stages.index('PROVIDER_ACCEPTED')
        assert 'ROUND_COMPLETE' not in rec.stages[:first]                  # acceptance is checkpointed before the round ends
        snap = Ledger.open_readonly(tmp_path / 'durable' / 'run.sqlite')
        try:
            assert snap.get('status') == 'PENDING_HUMAN_REVIEW'
        finally:
            snap.close()
        manifest = json.loads((tmp_path / 'durable' / 'CHECKPOINT.json').read_text())
        assert manifest['STAGE'] == 'CAMPAIGN_RESULT' and manifest['OPEN_PROVIDER_CALLS'] == []
        ledger.close()
        text = journal_text(d / 'run.sqlite')
        assert 'SYNTHETIC_HIDDEN_THINKING' not in text and 'synthetic-signature' not in text
        assert 'offline-gate-anthropic' not in text and 'offline-gate-openai' not in text
    finally:
        try:
            ledger.close()
        except Exception:
            pass


def test_acceptance_checkpoint_names_the_batch_id_before_any_polling(tmp_path):
    d = tmp_path / 'accept'
    d.mkdir()
    seen = []

    def spy(ledger, stage, detail):
        if stage == 'PROVIDER_ACCEPTED' and not seen:
            seen.append(ledger.provider_handles())
            raise Crash('VM died right after the acceptance checkpoint')

    c, ledger, caller, transport, clock = start(d, checkpointer=spy)
    with pytest.raises(Crash):
        invoke(c, caller)
    ledger.close()
    (handle,) = seen[0]
    assert handle['STATE'] == 'BACKGROUND_SUBMITTED' and handle['PROVIDER_ID'] == 'msgbatch_noisy_1' and handle['CUSTOM_ID'].startswith('gv0-')
    assert [x for x in transport.log if x[0] == 'GET'] == []                     # checkpointed before the first poll
    c2, ledger2, caller2 = resume(d, transport, clock)
    try:
        assert invoke(c2, caller2)['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert len(batch_posts(transport)) == 4
    finally:
        ledger2.close()


# --- crashes and lost acknowledgements -------------------------------------------------

def test_process_death_after_create_resumes_by_listing_without_a_second_post(tmp_path):
    d = tmp_path / 'crash'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 1, 1): 'crash_after_create'})
    with pytest.raises(Crash):
        invoke(c, caller)
    row = [x for x in generator_rows(ledger) if x['SLOT'] == 'generation:1'][0]
    assert row['STATE'] == 'DISPATCHED' and row['RESPONSE_ID'] is None          # the batch id never reached the journal
    ledger.close()
    c2, ledger2, caller2 = resume(d, transport, clock)
    try:
        result = invoke(c2, caller2)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and result['METRICS']['VALID'] == 40
        assert len(batch_posts(transport)) == 4                                   # found again, not POSTed again
        row = [x for x in generator_rows(ledger2) if x['SLOT'] == 'generation:1'][0]
        assert row['STATE'] == 'COMPLETE' and row['RESPONSE_ID'] == 'msgbatch_noisy_2'
        assert ledger2.db.execute("SELECT count(*) FROM events WHERE kind='PROVIDER_JOB_RECOVERED'").fetchone()[0] == 1
    finally:
        ledger2.close()


def test_lost_create_response_is_recovered_in_the_same_invocation(tmp_path):
    d = tmp_path / 'lost'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 2, 1): 'timeout_after_create'})
    try:
        result = invoke(c, caller)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and len(batch_posts(transport)) == 4
        assert {x['STATE'] for x in generator_rows(ledger)} == {'COMPLETE'}
        assert not [x for x in ledger.export_calls() if x['STATE'] == 'UNCERTAIN']
    finally:
        ledger.close()


def test_create_that_made_no_batch_is_proven_absent_closed_not_billed_and_retried(tmp_path):
    d = tmp_path / 'absent'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 0, 1): '500_no_batch'})
    try:
        result = invoke(c, caller)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        gen = generator_rows(ledger)
        first = [x for x in gen if x['SLOT'] == 'generation:0' and x['TRANSPORT_ATTEMPT'] == 0][0]
        assert first['STATE'] == 'FAILED_NOT_BILLED' and first['COST_MICRO_USD'] == 0
        resp = json.loads(ledger.db.execute('SELECT response FROM calls WHERE key=?', (first['CALL_KEY'],)).fetchone()[0])
        assert resp['RECOVERY_EVIDENCE']['ENDED_ONE_REQUEST_BATCHES_CHECKED'] == [] and resp['custom_id'].startswith('gv0-')
        assert len(batch_posts(transport)) == 5 and len(gen) == 5                # one refused create, then a new attempt key
        assert clock.t - 1_790_000_000.0 >= 600 + 120 + 900                       # absence is decided only after the settle window
    finally:
        ledger.close()


def test_absence_is_not_concluded_while_a_candidate_batch_is_still_processing(tmp_path):
    d = tmp_path / 'undecided'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 0, 1): 'timeout_after_create'}, max_wait=600)
    transport.processing_seconds = 5000
    try:
        with pytest.raises(BackgroundPending):
            invoke(c, caller)
        assert ledger.get('status') == 'PAUSED_BACKGROUND_PENDING'
        (row,) = generator_rows(ledger)
        assert row['STATE'] == 'DISPATCHED' and len(batch_posts(transport)) == 1
    finally:
        ledger.close()
    c2, ledger2, caller2 = resume(d, transport, clock, max_wait=7200)
    try:
        assert invoke(c2, caller2)['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert len(batch_posts(transport)) == 4
    finally:
        ledger2.close()


# --- polling: PENDING, never UNCERTAIN ---------------------------------------------------

def test_poll_timeouts_keep_polling_the_same_batch(tmp_path):
    d = tmp_path / 'polltimeout'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d)
    transport.poll_timeouts = 5
    try:
        assert invoke(c, caller)['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert len(batch_posts(transport)) == 4 and transport.poll_timeouts == 0
    finally:
        ledger.close()


def test_long_batch_pauses_pending_with_its_id_and_resume_polls_without_a_post(tmp_path):
    d = tmp_path / 'pending'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, max_wait=300)
    transport.processing_seconds = 4000
    with pytest.raises(BackgroundPending):
        invoke(c, caller)
    assert ledger.get('status') == 'PAUSED_BACKGROUND_PENDING'
    (row,) = generator_rows(ledger)
    assert row['STATE'] == 'BACKGROUND_SUBMITTED' and row['RESPONSE_ID'] == 'msgbatch_noisy_1'
    assert ledger.provider_handles()[0]['PROVIDER_ID'] == 'msgbatch_noisy_1'
    ledger.close()
    c2, ledger2, caller2 = resume(d, transport, clock, max_wait=7200)
    try:
        assert invoke(c2, caller2)['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert len(batch_posts(transport)) == 4
    finally:
        ledger2.close()


@pytest.mark.parametrize('status', [401, 403, 404])
def test_poll_credential_error_pauses_pending_and_resume_polls_the_same_batch(tmp_path, status):
    d = tmp_path / ('auth' + str(status))
    d.mkdir()
    c, ledger, caller, transport, clock = start(d)
    transport.poll_status_queue = [status]
    with pytest.raises(BackgroundPending):
        invoke(c, caller)
    assert ledger.get('status') == 'PAUSED_BACKGROUND_PENDING'
    assert generator_rows(ledger)[0]['STATE'] == 'BACKGROUND_SUBMITTED'
    ledger.close()
    c2, ledger2, caller2 = resume(d, transport, clock)
    try:
        assert invoke(c2, caller2)['STATUS'] == 'PENDING_HUMAN_REVIEW' and len(batch_posts(transport)) == 4
    finally:
        ledger2.close()


# --- provider outcomes ------------------------------------------------------------------

@pytest.mark.parametrize('fault', ['errored_overloaded', 'expired'])
def test_retryable_not_billed_batch_outcome_is_retried_under_a_new_key(tmp_path, fault):
    d = tmp_path / fault
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 1, 1): fault})
    try:
        assert invoke(c, caller)['STATUS'] == 'PENDING_HUMAN_REVIEW'
        rows = [x for x in generator_rows(ledger) if x['SLOT'] == 'generation:1']
        assert [(x['TRANSPORT_ATTEMPT'], x['STATE'], x['COST_MICRO_USD']) for x in rows] == [(0, 'FAILED_NOT_BILLED', 0), (1, 'COMPLETE', GEN_COST)]
        assert len(batch_posts(transport)) == 5
    finally:
        ledger.close()


@pytest.mark.parametrize('fault', ['errored_invalid', 'canceled'])
def test_non_retryable_not_billed_batch_outcome_pauses_for_the_operator(tmp_path, fault):
    d = tmp_path / fault
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 0, 1): fault})
    try:
        with pytest.raises(ProviderRejected):
            invoke(c, caller)
        assert ledger.get('status') == 'PAUSED_PROVIDER_REJECTED'
        (row,) = generator_rows(ledger)
        assert row['STATE'] == 'FAILED_NOT_BILLED' and row['COST_MICRO_USD'] == 0 and ledger.total_charged_micro_usd() == 0
        assert len(batch_posts(transport)) == 1
    finally:
        ledger.close()


def test_succeeded_but_truncated_batch_message_is_billed_at_batch_price_and_not_retried(tmp_path):
    d = tmp_path / 'maxtok'
    d.mkdir()
    c, ledger, caller, transport, clock = start(d, faults={('GENERATOR', 3, 1): 'max_tokens'})
    try:
        result = invoke(c, caller)
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW' and result['METRICS']['VALID'] == 30
        row = [x for x in generator_rows(ledger) if x['SLOT'] == 'generation:3'][0]
        assert row['STATE'] == 'FAILED_WITH_COST' and row['COST_MICRO_USD'] == 6000 * 2 + 100000 * 10
        assert len(batch_posts(transport)) == 4
    finally:
        ledger.close()


# --- external checkpoints ----------------------------------------------------------------

def test_checkpoint_failure_pauses_and_resume_polls_the_accepted_batch(tmp_path):
    d = tmp_path / 'ckfail'
    d.mkdir()
    rec = Recorder(tmp_path / 'durable', fail_on='PROVIDER_ACCEPTED')
    c, ledger, caller, transport, clock = start(d, checkpointer=rec)
    with pytest.raises(CheckpointFailed):
        invoke(c, caller)
    assert ledger.get('status') == 'PAUSED_CHECKPOINT_FAILED'
    assert generator_rows(ledger)[0]['STATE'] == 'BACKGROUND_SUBMITTED'
    ledger.close()
    c2, ledger2, caller2 = resume(d, transport, clock, checkpointer=Recorder(tmp_path / 'durable'))
    try:
        assert invoke(c2, caller2)['STATUS'] == 'PENDING_HUMAN_REVIEW' and len(batch_posts(transport)) == 4
    finally:
        ledger2.close()


def _git(*args, cwd):
    return subprocess.run(['git'] + list(args), cwd=cwd, check=True, capture_output=True, text=True)


def test_git_checkpointer_commits_only_its_files_and_pushes_the_current_branch(tmp_path):
    remote, repo = tmp_path / 'remote.git', tmp_path / 'repo'
    _git('init', '-q', '--bare', str(remote), cwd=tmp_path)
    _git('init', '-q', '-b', 'ckpt', str(repo), cwd=tmp_path)
    for k, v in (('user.email', 'offline@test'), ('user.name', 'offline'), ('commit.gpgsign', 'false')):
        _git('config', k, v, cwd=repo)
    (repo / 'README').write_text('x\n')
    (repo / 'unrelated.txt').write_text('must stay uncommitted\n')
    _git('add', 'README', cwd=repo)
    _git('commit', '-q', '-m', 'init', cwd=repo)
    _git('remote', 'add', 'origin', str(remote), cwd=repo)
    run_dir = repo / 'runs' / 'r02'
    run_dir.mkdir(parents=True)
    ledger = Ledger(run_dir / 'run.sqlite', ladder_config(RUN_ID='r02', SIZE=40, CAP_MICRO_USD=CAP_USD12))
    try:
        ck = GitCheckpointer(repo, 'runs/r02/checkpoint', 'ckpt', sleeper=lambda s: None)
        ledger.checkpointer = ck
        ledger.checkpoint('PROVIDER_ACCEPTED', {'PROVIDER_ID': 'msgbatch_x'})
        ledger.checkpoint('ROUND_COMPLETE', {'ROUND': 'generation:0'})
        log = _git('--git-dir', str(remote), 'log', '--format=%s', 'ckpt', cwd=tmp_path).stdout.split('\n')
        assert log[0] == 'checkpoint(generator): r02 #2 ROUND_COMPLETE' and log[1] == 'checkpoint(generator): r02 #1 PROVIDER_ACCEPTED'
        files = _git('--git-dir', str(remote), 'ls-tree', '-r', '--name-only', 'ckpt', cwd=tmp_path).stdout.split()
        assert sorted(files) == ['README', 'runs/r02/checkpoint/CHECKPOINT.json', 'runs/r02/checkpoint/run.sqlite']
        assert 'unrelated.txt' in _git('status', '--porcelain', cwd=repo).stdout
        _git('remote', 'set-url', 'origin', str(tmp_path / 'missing.git'), cwd=repo)
        with pytest.raises(CheckpointFailed):
            ledger.checkpoint('ROUND_COMPLETE', {'ROUND': 'generation:1'})
        with pytest.raises(ContractError):
            GitCheckpointer(repo, 'runs/r02/checkpoint', 'other-branch')
    finally:
        ledger.close()


# --- guards -------------------------------------------------------------------------------

def test_live_v03_refuses_the_synchronous_generator_route(tmp_path):
    d = tmp_path / 'sync'
    d.mkdir()
    c = Contexts(memory_event=GV0CAL_HEAD)
    transport = NoisyTransport(c, {})
    ledger = Ledger(d / 'run.sqlite', ladder_config(RUN_ID='sync', SIZE=40, CAP_MICRO_USD=CAP_USD12))
    try:
        caller = Caller(c, ledger, routed_provider_for(transport, c), CAP_USD12, True)
        with pytest.raises(ContractError, match='Message Batches'):
            invoke(c, caller)
        assert transport.log == []
    finally:
        ledger.close()


def test_a_dispatched_row_without_a_recovery_intent_still_needs_reconciliation(tmp_path):
    ledger = Ledger(tmp_path / 'run.sqlite', {'RUN_ID': 'legacy', 'CAP_MICRO_USD': CAP_USD12})
    try:
        ledger.reserve('k', {'role': 'GENERATOR', 'slot': 'generation:0'}, 1000, CAP_USD12)
        ledger.mark_dispatched('k')
        with pytest.raises(CallUncertain):
            ledger.reserve('k', {'role': 'GENERATOR', 'slot': 'generation:0'}, 1000, CAP_USD12)
        with pytest.raises(ContractError):
            ledger.reserve('k2', {'role': 'GENERATOR'}, 1, CAP_USD12) or ledger.mark_dispatched('k2', {'RECOVERY': 'GUESS'})
    finally:
        ledger.close()


def test_cli_live_ladder_run_requires_an_external_checkpoint(tmp_path, monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('SIGNALBOT_ANTHROPIC_API_KEY', 'offline-test-key')
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:9')
    run_dir = tmp_path / 'r02'
    with pytest.raises(ContractError, match='external journal checkpoint'):
        main(['ladder-40-card', '--allow-real-llm', '--budget-usd', '12', '--accept-budget-stop', '--actor', 'offline',
              '--reason', 'offline test', '--run-dir', str(run_dir)])
    assert not run_dir.exists()


def test_cli_checkpoint_targets_fail_closed_before_a_run_exists(tmp_path, monkeypatch):
    from scripts.research.generator_v0.__main__ import main
    monkeypatch.setenv('SIGNALBOT_ANTHROPIC_API_KEY', 'offline-test-key')
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:9')
    base = ['ladder-40-card', '--allow-real-llm', '--budget-usd', '12', '--accept-budget-stop', '--actor', 'offline', '--reason', 'offline test']
    run_dir = tmp_path / 'r02'
    with pytest.raises(ContractError, match='checkpoint directory must differ'):
        main(base + ['--checkpoint-dir', str(run_dir), '--run-dir', str(run_dir)])
    with pytest.raises(ContractError, match='choose one checkpoint target'):
        main(base + ['--checkpoint-dir', str(tmp_path / 'ck'), '--checkpoint-git-branch', 'x', '--run-dir', str(run_dir)])
    with pytest.raises(ContractError):
        main(base + ['--checkpoint-git-branch', 'not-the-current-branch-zz', '--run-dir', str(run_dir)])
    assert not run_dir.exists()


def test_frozen_r01_journal_cannot_be_resumed_by_the_batch_transport(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    from scripts.research.generator_v0.__main__ import main
    src = Path('docs/research/generator_v0_ladder40_v03_r01/run.sqlite')
    run_dir = tmp_path / 'ladder-40-card-v03-r01'
    run_dir.mkdir()
    shutil.copy(src, run_dir / 'run.sqlite')
    monkeypatch.setenv('SIGNALBOT_ANTHROPIC_API_KEY', 'offline-test-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test-key')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'offline-test-key')
    with pytest.raises(ContractError, match='resume configuration differs'):
        main(['resume', '--provider', 'routed', '--contract', 'V03', '--openai-network-mode', 'DIRECT', '--allow-real-llm',
              '--budget-usd', '12', '--checkpoint-dir', str(tmp_path / 'ck'), '--run-dir', str(run_dir)])
    l = Ledger.open_readonly(run_dir / 'run.sqlite')
    try:
        (row,) = l.export_calls()
        assert row['STATE'] == 'UNCERTAIN' and row['RESERVED_MICRO_USD'] == 2210772 and l.get('status') == 'PAUSED_UNCERTAIN_CALL'
        assert l.get('config')['ROUTING_DIGEST'] == V02_ROUTED_IDENTITY_DIRECT     # the synchronous route
    finally:
        l.close()
