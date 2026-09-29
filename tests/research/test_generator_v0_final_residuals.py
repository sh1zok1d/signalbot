"""Final narrow repair: abbreviated cross-year ranges, imperative trade language,
and the budget gate at the execution layer. Phrasings and year pairs are written
for this file; verifier strings are evidence only, not fixtures."""
import pytest
from scripts.research.generator_v0 import contract
from scripts.research.generator_v0 import textnorm as tn
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.mock import MockResponder
from scripts.research.generator_v0.runner import run_campaign,accept_budget_stop,BudgetGateRefused,campaign_budget_preflight,BUDGET_STOP_EVENT
from scripts.research.generator_v0_gate.corpus import base_ready,SLOT
from scripts.research.generator_v0_gate.noisy import NoisyTransport,provider_for

C=Contexts()

def rules(field,value):
    card=base_ready();card[field]=value
    return {v['RULE'] for v in contract.card_violations(card,C,SLOT)}

# ------------------------------------------------- 1. abbreviated ranges

PROTECTED_ABBREVIATIONS=[
    'the 2023/26 fiscal span',              # plain slash, two-digit continuation
    'coverage 2019-27',                     # hyphen
    'panel 2022–29',                   # en dash
    'panel 2021‒28',                   # figure dash
    'window 2020／31',                  # full-width solidus
    'window 2023∕30',                  # division slash
    'window 2022⁄27',                  # fraction slash
    'series 2021~28',                       # tilde
    'series 2023〜26',                  # wave dash
    'span 2024 / 9',                        # one-digit continuation after a slash
    'the ’22–’29 cycle',     # apostrophe short years
    'fy 23/27 budget',                      # bare short years with a year word
    'the 27/28 season',                     # consecutive season form
    'from 1999/28 onward'.replace(' onward',''),   # century wrap from a 9x start
    'two thousand twenty-two / twenty-eight',      # spelled boundary
    'twenty twenty-three–twenty-seven',       # spelled with en dash
    '２０２１/２８',        # full-width digits
]

@pytest.mark.parametrize('s',PROTECTED_ABBREVIATIONS)
def test_abbreviated_ranges_reaching_a_protected_year_hard_fail(s):
    assert 'NO_PROTECTED_YEARS' in rules('MAIN_CONFOUNDERS','Fee regime in '+s)

@pytest.mark.parametrize('s,end',[('2016/17',2017),('2019-24',2024),('FY2020/21',2021),('’18–’19 season',2019),
                                  ('1997/03',2003),('2012/3',2013),('twenty nineteen / twenty-two',2022)])
def test_reconstruction_is_deterministic_relative_to_the_first_year(s,end):
    assert tn.abbreviated_range_years(tn.normalize_text(s))==[end]

@pytest.mark.parametrize('s',['2024-12','2020-01..2024-12','2023-11-30','2021-06 through 2024-12','2016/17 season','2019-24',
                              '18-22 bars per window','ratio of 3/4'])
def test_non_protected_abbreviations_and_year_months_stay_valid(s):
    assert rules('FUNCTION','Compare '+s+' against the null')==set()

# ---------------------------------------------- 2. imperative trade language

IMPERATIVES=[
    'Fade every spike above the band.',
    'Then sell strength into the close',
    'Short ETH once funding flips',
    'When the gap fills, long the market.',
    'just buy weakness after liquidations',
    'accumulate dips below the band',
    'chase breakouts that clear the range',
    'the plan is to sell rallies',
    'Signal fires; buy it.',
    'Always short the pump',
]

@pytest.mark.parametrize('s',IMPERATIVES)
def test_imperative_and_actionable_trade_language_hard_fails(s):
    assert 'NO_TRADING_CLAIM' in rules('WHAT_POSITIVE_WOULD_TEACH',s)

DESCRIPTIVE=[
    'Participants who sell rallies leave a footprint in close location.',
    'Holders tend to buy dips after liquidation cascades.',
    'Retail buys dips; whales sell strength.',
    'Taker buy volume and sell volume imbalance over 1h.',
    'Short-horizon returns after a long gap in prints.',
    'Long memory in absolute returns; short interest proxies.',
    'Acquire historical book snapshots from a vendor archive.',
    'Purchase of a licensed archive is a data cost, not a result.',
    'Dip buying by funds is the mechanism under test.',
]

@pytest.mark.parametrize('s',DESCRIPTIVE)
def test_descriptive_market_language_stays_valid(s):
    assert rules('CAUSAL_OR_STRUCTURAL_STORY',s)==set()

def test_prompt_states_the_imperative_rule():
    p=contract.generator_prompt()
    assert 'Describe behaviour, never instruct it' in p
    for w in tn.IMPERATIVE_VERBS+tn.IMPERATIVE_LEADS+tn.DESCRIPTIVE_SUBJECTS:assert w in p

# --------------------------------- 3. budget gate at the execution layer

OWNER=17_100_000

def live_like(tmp_path,name='r'):
    t=NoisyTransport(C,{});l=Ledger(tmp_path/(name+'.sqlite'),{'RUN_ID':name,'CAP_MICRO_USD':OWNER})
    return t,l,Caller(C,l,provider_for(t,C),OWNER,True)

def test_direct_library_run_cannot_bypass_the_budget_gate(tmp_path):
    t,l,caller=live_like(tmp_path)
    assert caller.provider.real
    pre=campaign_budget_preflight(C,caller,40)
    assert pre['FITS_AUTHORIZED_REMAINING'] is False
    with pytest.raises(BudgetGateRefused):run_campaign(C,caller)
    assert t.log==[] and l.export_calls()==[] and l.get('status')=='CREATED'

def test_acceptance_has_the_same_recorded_semantics_and_is_bound_to_the_snapshot(tmp_path):
    t,l,caller=live_like(tmp_path)
    with pytest.raises(ContractError,match='actor and reason'):accept_budget_stop(C,caller,40,'','')
    rec=accept_budget_stop(C,caller,40,'op','accept a clean STOPPED_BUDGET')
    assert rec['ACTOR']=='op' and rec['FITS_AUTHORIZED_REMAINING'] is False
    # Spend changes after acceptance (e.g. a partial run): the old acceptance no longer applies.
    l.reserve('other',{'role':'X','slot':'y'},10,OWNER);l.mark_dispatched('other');l.finish('other',{'raw':'{}'},7,{})
    with pytest.raises(BudgetGateRefused):run_campaign(C,caller)
    assert t.log==[]
    accept_budget_stop(C,caller,40,'op','re-accepted after spend changed')
    assert run_campaign(C,caller)['STATUS']=='PENDING_HUMAN_REVIEW'
    assert len(l.db.execute('SELECT 1 FROM events WHERE kind=?',(BUDGET_STOP_EVENT,)).fetchall())==2

def test_real_cap_above_owner_ceiling_is_refused_even_with_acceptance(tmp_path):
    t=NoisyTransport(C,{});l=Ledger(tmp_path/'x.sqlite',{'RUN_ID':'x','CAP_MICRO_USD':OWNER+1})
    caller=Caller(C,l,provider_for(t,C),OWNER+1,True)
    accept_budget_stop(C,caller,40,'op','try')
    with pytest.raises(BudgetGateRefused,match='owner'):run_campaign(C,caller)
    assert t.log==[]

def test_gate_uses_the_callers_own_provider_bound(tmp_path):
    """A provider whose bound fits needs no acceptance (the zero-cost mock)."""
    l=Ledger(tmp_path/'m.sqlite',{'RUN_ID':'m'});caller=Caller(C,l,MockProvider(MockResponder(C)))
    assert campaign_budget_preflight(C,caller,40)['FITS_AUTHORIZED_REMAINING']
    assert run_campaign(C,caller)['STATUS']=='PENDING_HUMAN_REVIEW'
