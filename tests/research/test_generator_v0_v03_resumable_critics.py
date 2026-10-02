"""OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1 and the r02 derived continuation.

Offline only. Feasibility and selector on the V03 ladder use background Responses.
The vendored r02 checkpoint is read, never mutated. No provider POST leaves the process.
"""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.research.generator_v0 import routing
from scripts.research.generator_v0.checkpoint import CheckpointFailed
from scripts.research.generator_v0.context import Contexts, ContractError
from scripts.research.generator_v0.derive import (
    authorize_derived_continuation, continuation_bound_view, derive_complete_rounds,
    remaining_campaign_budget_preflight,
)
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import MockResponder, fixture
from scripts.research.generator_v0.openai_provider import OpenAIProvider
from scripts.research.generator_v0.provider import BackgroundPending, Caller
from scripts.research.generator_v0.roles import FEAS_PROMPT, ROLE_OUTPUT_TOKEN_CAPS, Roles, SELECTOR_PROMPT
from scripts.research.generator_v0.routed_provider import RoutedProvider, offline_routed_provider
from scripts.research.generator_v0.runner import accept_budget_stop, run_campaign
from scripts.research.generator_v0.anthropic_provider import AnthropicProvider
from scripts.research.generator_v0_gate.noisy import NoisyTransport, ladder_provider_for
from scripts.research.generator_v0 import contract_v03
from tests.research.test_generator_v0_anthropic_batch_transport import V02_ROUTING_DIGEST

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'docs/research/generator_v0_ladder40_v03_r02/run.sqlite'
SOURCE_SHA = 'ffa179220d12986520c214f7a1ad1cfecd084848f9de0158fcd43476d9447a37'
R02_CHARGED = 3_659_239
C024_KEY = '76ddea9fac6cbafa398ad5c821b1fed99e40f25be8af903ef0634811b0450604'
C024_RESERVED = 5302
CAP = 9_789_228
C = Contexts()
CARD = fixture(contract_v03.slot_plan()[0], C)


class Script:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.log = []

    def __call__(self, method, path, body, headers, timeout):
        self.log.append((method, path, json.loads(body) if body else None))
        a = self.answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a

    def posts(self):
        return [(p, b) for m, p, b in self.log if m == 'POST']


class Crash(BaseException):
    pass


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


def _router(transport, clock=None, wait=3600):
    clock = clock or Clock()

    def sleep(seconds):
        clock.t += seconds

    def refuse(*_a, **_k):
        raise AssertionError('generator must not be called')
    return RoutedProvider({
        'ANTHROPIC': AnthropicProvider('offline-anthropic', allow_real=True, budget_micro_usd=17_100_000,
                                       routes=routing.LADDER_ROUTES, contexts=C, transport=refuse),
        'OPENAI': OpenAIProvider('offline-openai', allow_real=True, budget_micro_usd=17_100_000, contexts=C,
                                 routes=routing.LADDER_ROUTES, transport=transport, sleeper=sleep, clock=clock,
                                 background_max_wait_seconds=wait),
    }, routing.LADDER_ROUTES)


def _caller(transport, path, clock=None, wait=3600):
    ledger = Ledger(path, {'RUN_ID': Path(path).parent.name if path != ':memory:' else 'mem', 'CAP_MICRO_USD': CAP})
    return Caller(C, ledger, _router(transport, clock, wait), CAP, True)


def _created(rid='resp_feas_1'):
    return 200, json.dumps({'id': rid, 'object': 'response', 'status': 'queued'}).encode()


def _completed(text, rid='resp_feas_1'):
    body = {'id': rid, 'object': 'response', 'status': 'completed', 'output_text': text,
            'usage': {'input_tokens': 800, 'output_tokens': 120, 'output_tokens_details': {'reasoning_tokens': 10}}}
    return 200, json.dumps(body).encode()


def _feas_text():
    return MockResponder(C)({'role': 'FEASIBILITY_CRITIC', 'context': Roles(C, None).request('FEASIBILITY_CRITIC', CARD), 'parameters': {}})


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_source(dest):
    dest.mkdir()
    shutil.copy(SOURCE, dest / 'run.sqlite')
    return dest


# A-F. Transport amendment -----------------------------------------------------------------

def test_a_feasibility_background_create_journals_the_response_id(tmp_path):
    t = Script(_created(), _completed(_feas_text()), (200, b'{}'))
    cal = _caller(t, tmp_path / 'a.sqlite')
    Roles(C, cal).feasibility(CARD)
    (path, body), = t.posts()
    row = [r for r in cal.ledger.export_calls() if r['ROLE'] == 'FEASIBILITY_CRITIC'][-1]
    assert path == '/v1/responses' and body['background'] is True and body['store'] is True
    assert body['model'] == 'gpt-6-luna' and body['reasoning'] == {'effort': 'low'}
    assert body['max_output_tokens'] == ROLE_OUTPUT_TOKEN_CAPS['FEASIBILITY_CRITIC'] == 6000
    assert body['instructions'] == FEAS_PROMPT
    assert row['RESPONSE_ID'] == 'resp_feas_1' and row['STATE'] == 'COMPLETE'
    assert row['MODEL_PROVIDER'] == 'OPENAI_RESPONSES_BACKGROUND'


def test_b_process_death_after_acceptance_polls_the_same_response_id(tmp_path):
    path = tmp_path / 'b.sqlite'
    clock = Clock()
    first = Script(_created('resp_same'), Crash('died after the id was journaled'))
    cal = _caller(first, path, clock)
    with pytest.raises(Crash):
        Roles(C, cal).feasibility(CARD)
    assert len(first.posts()) == 1
    assert cal.ledger.call_state(cal.last_key) == 'BACKGROUND_SUBMITTED'
    cal.ledger.close()
    second = Script(_completed(_feas_text(), 'resp_same'), (200, b'{}'))
    cal2 = _caller(second, path, clock)
    Roles(C, cal2).feasibility(CARD)
    assert second.posts() == [] and second.log[0][1] == '/v1/responses/resp_same'
    row = [r for r in cal2.ledger.export_calls() if r['ROLE'] == 'FEASIBILITY_CRITIC'][-1]
    assert row['STATE'] == 'COMPLETE' and row['RESPONSE_ID'] == 'resp_same'


def test_c_poll_5xx_stays_pending_and_is_not_created_again(tmp_path):
    path = tmp_path / 'c.sqlite'
    clock = Clock()
    t = Script(_created('resp_poll'), (500, b'{"error":{"type":"server_error"}}'), (500, b'{"error":{"type":"server_error"}}'))
    cal = _caller(t, path, clock, wait=1)
    with pytest.raises(BackgroundPending):
        Roles(C, cal).feasibility(CARD)
    assert len(t.posts()) == 1 and cal.ledger.call_state(cal.last_key) == 'BACKGROUND_SUBMITTED'
    cal.ledger.close()
    resume = Script(_completed(_feas_text(), 'resp_poll'), (200, b'{}'))
    cal2 = _caller(resume, path, Clock())
    Roles(C, cal2).feasibility(CARD)
    assert resume.posts() == [] and [r['STATE'] for r in cal2.ledger.export_calls()] == ['COMPLETE']


def test_d_selector_background_create_and_no_chat_fallback(tmp_path):
    row = {'CANDIDATE_ID': 'C006', 'NOVELTY_VERDICT': 'ALLOW', 'MECHANISM_DISTANCE_JUDGMENT': 2,
           'FEASIBILITY_VERDICT': 'PASS', 'DATA_STATUS': 'DATA_READY', 'DATA_GAP_CLASS': 'NONE',
           'RED_TEAM_VERDICT': 'PASS', 'HARD_FAILS': [], 'INFORMATION_GAIN_JUDGMENT': 2, 'COST_JUDGMENT': 2}
    ctx = {'SANITIZED_CRITIC_OUTPUTS': [row], 'DATA_STATUS': {'C006': 'DATA_READY'},
           'SELECTION_JUDGMENTS': {'C006': {'MECHANISM_DISTANCE': 2, 'INFORMATION_GAIN': 2, 'FEASIBILITY': 2, 'CHEAPNESS': 2}}}
    text = json.dumps({'ORDERED_CANDIDATE_IDS': ['C006']})
    t = Script(_created('resp_sel'), _completed(text, 'resp_sel'), (200, b'{}'))
    cal = _caller(t, tmp_path / 'd.sqlite')
    raw = cal.call('SELECTOR', ctx, SELECTOR_PROMPT, {'max_output_tokens': ROLE_OUTPUT_TOKEN_CAPS['SELECTOR']}, 'selection')
    (path, body), = t.posts()
    assert path == '/v1/responses' and body['background'] is True and body['model'] == 'gpt-6-luna'
    assert body['reasoning'] == {'effort': 'none'} and body['max_output_tokens'] == 2000
    assert json.loads(raw)['ORDERED_CANDIDATE_IDS'] == ['C006']
    req = cal.request('SELECTOR', ctx, SELECTOR_PROMPT, {'max_output_tokens': 2000}, 'selection')
    with pytest.raises(ContractError, match='background'):
        cal.provider.complete(req)
    assert routing.LADDER_ROUTES['SELECTOR']['ADVISORY_ONLY'] is True
    assert routing.ROUTES['SELECTOR']['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'


def test_e_every_paid_v03_role_is_resumable_and_f_v02_is_unchanged():
    ladder = routing.validate_routes(routing.LADDER_ROUTES)
    assert routing.OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1
    for role, route in ladder.items():
        assert route['ENDPOINT'] in routing.BACKGROUND_ENDPOINTS
        assert route['TRANSPORT']['SYNC'] is False
    assert ladder['GENERATOR']['ENDPOINT'] == 'ANTHROPIC_MESSAGE_BATCHES'
    for role in ('NOVELTY_CRITIC', 'FEASIBILITY_CRITIC', 'RED_TEAM', 'SELECTOR'):
        assert ladder[role]['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND'
    assert ladder['FEASIBILITY_CRITIC']['MODEL'] == 'gpt-6-luna' and ladder['FEASIBILITY_CRITIC']['PARAMS'] == {'reasoning_effort': 'low'}
    assert ladder['SELECTOR']['PARAMS'] == {'reasoning_effort': 'none'}
    v02 = routing.validate_routes()
    assert routing.routing_digest() == V02_ROUTING_DIGEST
    assert offline_routed_provider(C).routing_digest != offline_routed_provider(C, routing.LADDER_ROUTES).routing_digest
    assert v02['FEASIBILITY_CRITIC']['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'
    assert v02['SELECTOR']['ENDPOINT'] == 'OPENAI_CHAT_COMPLETIONS'
    assert v02['NOVELTY_CRITIC']['ENDPOINT'] == 'OPENAI_RESPONSES_BACKGROUND'
    p = offline_routed_provider(C)
    assert p.uses_background('FEASIBILITY_CRITIC') is False and p.uses_background('SELECTOR') is False
    ladder_p = offline_routed_provider(C, routing.LADDER_ROUTES)
    assert all(ladder_p.uses_background(role) for role in routing.ROLES)


# G-O. Derived continuation of the real r02 checkpoint ------------------------------------

def _derive(tmp_path):
    src = _copy_source(tmp_path / 'src')
    before = _sha(src / 'run.sqlite')
    report = derive_complete_rounds(src, tmp_path / 'dst', 3, C)
    after = _sha(src / 'run.sqlite')
    return src, report, before, after


def test_g_through_l_derive_preserves_r02_and_replays_no_official_critic(tmp_path):
    src, report, before, after = _derive(tmp_path)
    assert before == after == SOURCE_SHA
    assert report['IMPORTED_GENERATION_ROUNDS'] == ['generation:0', 'generation:1', 'generation:2', 'generation:3']
    assert report['NEW_GENERATOR_CALLS_REQUIRED'] == 0
    assert report['IMPORTED_VALID'] == 30 and report['IMPORTED_HARD_FAIL'] == 10
    assert len(report['IMPORTED_INTAKE_VERDICTS']) == 40 and report['CANDIDATE_CORPUS_MATCH'] is True
    assert report['OFFICIAL_CRITIC_OUTPUTS_IMPORTED'] is False
    assert report['LINEAGE_TOTAL_MICRO_USD'] == R02_CHARGED
    assert report['CAP_MICRO_USD'] == CAP and report['REMAINING_MICRO_USD'] == CAP - R02_CHARGED
    assert report['REAL_LLM_CALLS_MADE'] is False
    ledger = Ledger.open_readonly(tmp_path / 'dst' / 'run.sqlite')
    try:
        roles = {r['ROLE'] for r in ledger.export_calls()}
        assert roles == {'GENERATOR'}
        lineage = ledger.get('lineage')
        assert ledger.total_charged_micro_usd() == R02_CHARGED
        priors = lineage['PRIOR_ATTEMPTS']
        assert priors and all(p['ROLE'] != 'GENERATOR' or p['STATE'] != 'COMPLETE' for p in priors)
        critic_priors = [p for p in priors if p['ROLE'] in ('NOVELTY_CRITIC', 'FEASIBILITY_CRITIC', 'RED_TEAM')]
        assert len(critic_priors) == 41
        assert {p['CALL_KEY'] for p in critic_priors}.isdisjoint({r['CALL_KEY'] for r in ledger.export_calls()})
        c024 = [p for p in priors if p['CALL_KEY'] == C024_KEY]
        assert len(c024) == 1
        assert c024[0]['STATE'] == 'UNCERTAIN' and c024[0]['RESPONSE_ID'] is None
        assert c024[0]['CHARGED_MICRO_USD'] == C024_RESERVED
        assert c024[0]['SLOT'] == 'FEASIBILITY_CRITIC:C024'
        assert ledger.call_state(C024_KEY) is None
        official = [r for r in ledger.export_calls() if r['ROLE'] != 'GENERATOR']
        assert official == []
    finally:
        ledger.close()
    # source call is still UNCERTAIN and was not reconciled
    source = Ledger.open_readonly(src / 'run.sqlite')
    try:
        row = [r for r in source.export_calls() if r['CALL_KEY'] == C024_KEY][0]
        assert row['STATE'] == 'UNCERTAIN' and row['RESPONSE_ID'] is None and row['RESERVED_MICRO_USD'] == C024_RESERVED
        assert source.get('status') == 'PAUSED_UNCERTAIN_CALL'
    finally:
        source.close()


def test_preflight_bounds_thirty_valid_critics_and_no_generator(tmp_path):
    _derive(tmp_path)
    pre = remaining_campaign_budget_preflight(
        tmp_path / 'dst', C, bound_provider=offline_routed_provider(C, routing.LADDER_ROUTES))
    view = continuation_bound_view(pre)
    assert pre['REMAINING_GENERATION_ROUNDS'] == [] and pre['PROXY_CARDS'] == 0
    assert pre['SPENT_MICRO_USD'] == R02_CHARGED
    assert pre['REMAINING_AUTHORIZED_MICRO_USD'] == CAP - R02_CHARGED == 6_129_989
    stages = {s['STAGE']: s['BOUND_MICRO_USD'] for s in pre['STAGES']}
    assert not any(name.startswith('generation:') for name in stages)
    assert pre['REVIEW_CARDS'] == 30
    assert stages['NOVELTY_CRITIC x30'] > 0 and stages['FEASIBILITY_CRITIC x30'] > 0 and stages['RED_TEAM x30'] > 0
    assert view['AVAILABLE_USD'] == '6.129989'
    assert view['FITS_BASE'] is pre['FITS_AUTHORIZED_REMAINING']
    assert view['FITS_STRESS'] is pre['FITS_WITH_CONTENT_RETRIES']
    assert pre['REAL_LLM_CALLS_MADE'] is False
    # Persist the figures for the record written by the test run's caller via the return.
    (tmp_path / 'view.json').write_text(json.dumps(view), encoding='utf-8')


def test_m_n_fake_continuation_posts_no_generator_and_finishes_the_shortlist(tmp_path):
    _derive(tmp_path)
    dest = tmp_path / 'dst'
    authorize_derived_continuation(dest, 'offline-test', 'clean critic pass under background responses')
    c = Contexts()
    transport = NoisyTransport(c)
    ledger = Ledger(dest / 'run.sqlite')
    ledger.checkpointer = _Ok()
    caller = Caller(c, ledger, ladder_provider_for(transport, c), CAP, True)
    try:
        accept_budget_stop(c, caller, 40, 'offline-test', 'worst case may exceed the remaining r02 authorization')
        result = run_campaign(c, caller, 40)
        posts = transport.posts()
        assert not [p for p in posts if p[1].startswith('/v1/messages')]
        gen_posts = [p for p in posts if p == ('POST', '/v1/messages/batches')]
        assert gen_posts == []
        roles = {}
        for row in ledger.export_calls():
            roles[row['ROLE']] = roles.get(row['ROLE'], 0) + 1
        assert roles['GENERATOR'] == 4
        assert roles['NOVELTY_CRITIC'] == 30 and roles['FEASIBILITY_CRITIC'] == 30 and roles['RED_TEAM'] == 30
        assert roles['SELECTOR'] == 1
        feas = [r for r in ledger.export_calls() if r['ROLE'] in ('FEASIBILITY_CRITIC', 'SELECTOR')]
        assert feas and {r['MODEL_PROVIDER'] for r in feas} == {'OPENAI_RESPONSES_BACKGROUND'}
        assert result['STATUS'] == 'PENDING_HUMAN_REVIEW'
        assert [s['SEAT'] for s in result['SHORTLIST_RULE']['SEATS']] == ['ATOMIC', 'ATOMIC', 'CONDITIONAL', 'CONDITIONAL', 'COMPLEX']
        assert ledger.call_state(C024_KEY) is None
    finally:
        ledger.close()


class _Fail:
    def __init__(self):
        self.stages = []

    def __call__(self, ledger, stage, detail):
        self.stages.append(stage)
        if stage == 'REVIEW_BLOCK':
            raise CheckpointFailed('synthetic checkpoint target unavailable')


class _Ok:
    def __init__(self):
        self.stages = []

    def __call__(self, ledger, stage, detail):
        self.stages.append(stage)


def test_o_checkpoint_failure_pauses_without_a_second_generator_post(tmp_path):
    _derive(tmp_path)
    dest = tmp_path / 'dst'
    authorize_derived_continuation(dest, 'offline-test', 'checkpoint fault')
    c = Contexts()
    transport = NoisyTransport(c)
    ledger = Ledger(dest / 'run.sqlite')
    ledger.checkpointer = _Fail()
    caller = Caller(c, ledger, ladder_provider_for(transport, c), CAP, True)
    try:
        accept_budget_stop(c, caller, 40, 'offline-test', 'worst case may exceed the remaining r02 authorization')
        with pytest.raises(CheckpointFailed):
            run_campaign(c, caller, 40)
        assert ledger.get('status') == 'PAUSED_CHECKPOINT_FAILED'
        assert not [p for p in transport.posts() if p == ('POST', '/v1/messages/batches')]
        assert ledger.call_state(C024_KEY) is None
    finally:
        ledger.close()


def test_p_secret_scan_of_the_vendored_journal_is_clean():
    import re
    blob = SOURCE.read_bytes()
    assert re.search(br'sk-(?:proj|ant|live|test)-[A-Za-z0-9_\-]{8,}', blob) is None
    assert re.search(br'(?:OPENAI|ANTHROPIC)_API_KEY\s*=\s*\S+', blob) is None
    for needle in (b'BEGIN PRIVATE', b'BEGIN OPENSSH', b'AKIA'):
        assert needle not in blob
