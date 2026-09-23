"""B4: Unicode normalization and structural temporal / trade checks (V02).

Phrasings here were written for this repair; none is copied from the PR #215
verifier corpus. Passing does not prove semantic completeness: the scanners
remove predictable lexical and Unicode bypasses, and critics still review."""
import pytest
from scripts.research.generator_v0 import contract
from scripts.research.generator_v0 import textnorm as tn
from scripts.research.generator_v0.context import Contexts
from scripts.research.generator_v0_gate.corpus import base_ready,SLOT

C=Contexts()

def rules(field,value):
    card=base_ready();card[field]=value
    return {v['RULE'] for v in contract.card_violations(card,C,SLOT)}

def row_rules(field,value):
    card=base_ready();card['DATA_REQUIRED'][0][field]=value
    return {v['RULE'] for v in contract.card_violations(card,C,SLOT)}

# ---------------------------------------------------------- normalization

def test_normalization_is_deterministic_and_idempotent():
    for s in ('Ｆｙ２５ data','x​2‌0‍2⁠5','Ⅿ','A—B','²⁰²⁵'):
        once=tn.normalize_text(s)
        assert tn.normalize_text(once)==once and tn.normalize_text(s)==once

UNICODE_YEARS=[
    '２０２５',                                     # full-width
    '٢٠٢٦',                     # Arabic-Indic
    '२०२५',                     # Devanagari
    '\U0001d7d0\U0001d7ce\U0001d7d0\U0001d7d3',     # mathematical bold digits
    '²⁰²⁵',                     # superscripts
    '₂₀₂₆',                     # subscripts
    '20​26',                                   # zero-width space inside
    '20­25',                                   # soft hyphen inside
    '2 0 2 5',                       # NBSP-spaced digits
    '2.0.2.6',                                      # dotted digits
    '2o26',                                         # letter o inside digits
    'FY２６',                               # fiscal short form, full-width
    'h2’26',                                   # half-year with typographic apostrophe
    'q3 ’25',
    'MMXXVI','mmxxv',                               # Roman numerals
    'Two Thousand and Twenty-Six','twenty‑twenty‑five','two zero two six',
    'year 2031',                                    # any year after 2024 in text
]

@pytest.mark.parametrize('s',UNICODE_YEARS)
def test_unicode_and_spelled_protected_years_hard_fail(s):
    assert 'NO_PROTECTED_YEARS' in rules('MAIN_CONFOUNDERS','Fee schedule shift in '+s+' is excluded')

@pytest.mark.parametrize('s',UNICODE_YEARS[:6])
def test_unicode_years_in_keys_and_dataset_names_hard_fail(s):
    card=base_ready();card['SEARCH_SURFACE']={'PARAMETERS':{'cut_'+s:[1]},'MAX_VARIANTS':1}
    assert 'NO_PROTECTED_YEARS' in {v['RULE'] for v in contract.card_violations(card,C,SLOT)}
    assert 'NO_PROTECTED_YEARS' in row_rules('DATASET','BINANCE_KLINES_'+s)

def test_protected_catalog_entry_matched_after_normalization():
    for name in ('ＰＲＯＴＥＣＴＥＤ_2024','protected holdout','Protected panel'):
        assert 'PROTECTED_SOURCE' in row_rules('DATASET',name)

# ------------------------------------------------------ temporal: beyond 2024

BEYOND_2024=[
    'bars posted subsequent to December 2024',
    'returns in the months following Dec 2024',
    'from 2024-12 on',
    'anything newer than 2024',
    'sample: 2022 and afterwards',
    'coverage 2021-06 onward',
    'coverage ≥ 2023',
    'span 2020 ＋',
    'the quarters succeeding late 2024',
    'data 2019-01 and up',
    'panel 2018–now',
    'panel 2018—current',
]

@pytest.mark.parametrize('s',BEYOND_2024)
def test_scope_extending_past_a_year_hard_fails(s):
    assert 'NO_OPEN_ENDED_WINDOW' in rules('FUNCTION',s)

OPEN_ENDED=[
    'evaluate through whatever is the newest print'.replace('print','month'),
    'accumulate samples until the moment of writing',
    'refresh daily as of today',
    'extend the panel into the indefinite future',
    'panel with no end date',
    'an unbounded end for the sample',
    'Open‐ended collection of funding prints',
    'tracked up to the most recent month',
    'rolled forward thru nowadays',
    'held until real‑time',
]

@pytest.mark.parametrize('s',OPEN_ENDED)
def test_open_ended_scope_hard_fails(s):
    assert 'NO_OPEN_ENDED_WINDOW' in rules('BASELINE_OR_NULL',s)

@pytest.mark.parametrize('s',['live','Real‑Time','the present session','newest','today’s close','this quarter','year to date','up‑to‑date'])
def test_scope_fields_reject_wall_clock_recency(s):
    assert 'SCOPE_NO_RECENCY' in rules('HORIZON','4h ending at '+s)
    assert 'SCOPE_NO_RECENCY' in row_rules('OBSERVABLE','1m bars, '+s)

# --------------------------------------------------------------- trading

TRADE=[
    'we then acquire spot BTC at the open',
    'You should sell into the spike',
    'recommend buying after the cross',
    'fires a purchase alert on the cross',
    'a clean sell setup appears',
    'enter a short once funding flips',
    'take long exposure when the cross prints',
    'flip short on confirmation',
    'captures persistent alpha',
    'earns a reliable P&L',
    'risk-free arbitrage across venues',
    'projected profitability after fees',
    'a tradeable edge',
    'Guaranteed profit',
    'sells‑signal cascade',
]

@pytest.mark.parametrize('s',TRADE)
def test_trade_and_success_paraphrases_hard_fail(s):
    assert 'NO_TRADING_CLAIM' in rules('WHAT_POSITIVE_WOULD_TEACH',s)

# --------------------------------------------------- compliant controls

COMPLIANT={
    'FUNCTION':['Compare 2020-01 to 2024-12 against 2019 as a placebo year',
                'Map each bar to the latest bar closed at or before decision T',
                'Rank taker buy volume ratio against sell-side imbalance',
                'Short interest proxies and long-short spreads, never joined to future quotes',
                'Window of 1440 bars, then 2880 minutes',
                'EWMA alpha 0.1 decay; edge cases at session boundaries',
                'Fit from 2020 to 2024 inclusive'],
    'EXPECTED_INFORMATION_GAIN':['Expected information gain is high because the null is sharp'],
    'HORIZON':['next 24h after T','4h after decision T'],
    'MAIN_CONFOUNDERS':['After the 2020-03 crash, liquidity regimes changed; data from 2020 to 2024 present a challenge'.replace('After the 2020-03 crash','Around the 2020-03 crash')],
}

def test_compliant_controls_stay_valid():
    for field,values in COMPLIANT.items():
        for s in values:
            assert rules(field,s)==set(),(field,s,rules(field,s))

def test_numeric_search_values_are_only_forbidden_for_2025_2026():
    card=base_ready();card['SEARCH_SURFACE']={'PARAMETERS':{'bars':[2048,2100]},'MAX_VARIANTS':2}
    assert contract.card_violations(card,C,SLOT)==[]
    card['SEARCH_SURFACE']={'PARAMETERS':{'bars':[2026]},'MAX_VARIANTS':1}
    assert 'NO_PROTECTED_YEARS' in {v['RULE'] for v in contract.card_violations(card,C,SLOT)}

def test_rule_texts_state_every_structural_list():
    p=contract.generator_prompt()
    for group in (tn.BEFORE_RELATIONS,tn.AFTER_RELATIONS,tn.OPEN_ENDPOINTS,tn.UNANCHORED_ENDPOINTS,tn.ACTION_WORDS,tn.INSTRUCTION_WORDS,tn.POSITION_VERBS,tn.CLAIM_NOUNS,tn.CLAIM_MODIFIERS):
        for w in group:assert w in p,w

# ------------- structural classes added after the external regression run
# (own phrasings; the external corpus is evidence, not a string list)

@pytest.mark.parametrize('field,s,rule',[
    ('MECHANISM','Timing crosses Dec 2024 into the next season','NO_OPEN_ENDED_WINDOW'),
    ('MECHANISM','Series runs well past two thousand twenty-four','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Anchor the panel at December 2024 as its beginning','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Begin sampling at 2024-11','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Keep the window open at its upper edge','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Allow an unlimited sample horizon','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Add incoming bars as they arrive','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Sample anything beyond the catalogued coverage','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Contemporary data only','NO_OPEN_ENDED_WINDOW'),
    ('FUNCTION','Log prints through this afternoon','NO_OPEN_ENDED_WINDOW'),
    ('HORIZON','4h in the next fiscal quarter','SCOPE_NO_RECENCY'),
    ('HORIZON','freshest 4h','SCOPE_NO_RECENCY'),
    ('NAME','Card about yr 26 flows','NO_PROTECTED_YEARS'),
    ('WHAT_POSITIVE_WOULD_TEACH','Raises the odds of a winning bet','NO_TRADING_CLAIM'),
    ('WHAT_POSITIVE_WOULD_TEACH','An alpha source that later gets validated out of sample','NO_TRADING_CLAIM'),
])
def test_structural_classes(field,s,rule):
    assert rule in rules(field,s)

@pytest.mark.parametrize('field,s',[
    ('FUNCTION','Begin sampling at 2024-01 and stop at 2024-12'),
    ('FUNCTION','From 2021 through 2024-06'),
    ('MECHANISM','Funding flips whenever basis crosses zero'),
    ('MECHANISM','Live order books are not used; completed bars only'.replace('Live order books','Order books')),
    ('FALSIFIER','Win rate of the null equals the observed rank correlation'.replace('Win rate of the null','Null rank correlation')),
])
def test_structural_class_controls(field,s):
    assert rules(field,s)==set(),rules(field,s)
