import copy
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.schema import validate_card,parse_json

def card():
    c=Contexts();x={k:'specified' for k in c.design['CANDIDATE_SCHEMA']['REQUIRED_FIELDS']}
    x.update(CANDIDATE_ID='C001',MECHANISM_FAMILY='A',NEAREST_TESTED_MECHANISM='NONE',PROTECTED_DATA_REQUIREMENT=False,DATA_STATUS='DATA_READY',MISSING_OBSERVABLES=[],DATA_GAP_CLASS='NONE',DATA_REQUIRED=[{'DATASET':'CORE_BTC_BINANCE_V0','OBSERVABLE':'quote volume','STATUS':'DATA_READY','LEGAL_RANGE':'2020-01..2024-12'}],SEARCH_SURFACE={'PARAMETERS':{'horizon':['6h']},'MAX_VARIANTS':1})
    return x

def test_valid_and_off_catalog_blocked():
    c=Contexts();x=card();validate_card(x,c)
    x.update(DATA_STATUS='FEASIBILITY_REQUIRED',MISSING_OBSERVABLES=['specific archive identity'],DATA_GAP_CLASS='PROVENANCE')
    x['DATA_REQUIRED'][0].update(DATASET='unknown',STATUS='FEASIBILITY_REQUIRED')
    validate_card(x,c)

@pytest.mark.parametrize('mutation',[
 lambda x:x.pop('FALSIFIER'),lambda x:x.update(EXPECTED_PROBABILITY_OF_SUCCESS=.9),
 lambda x:x.update(FALSIFIER=''),lambda x:x.update(PROTECTED_DATA_REQUIREMENT=True),
 lambda x:x.update(HORIZON='2025'),lambda x:x.update(DATA_STATUS='magic'),
 lambda x:x.update(SEARCH_SURFACE={'PARAMETERS':{},'MAX_VARIANTS':1000000}),
 lambda x:x['DATA_REQUIRED'][0].update(DATASET='unknown'),
 lambda x:x.update(BASELINE_OR_NULL=''),lambda x:x.update(NAME='validated trading edge')])
def test_invalid_cards(mutation):
    x=card();mutation(x)
    with pytest.raises(ContractError):validate_card(x,Contexts())

@pytest.mark.parametrize('s',['oops','{"x":1,"x":2}','{"x":NaN}'])
def test_malformed_json(s):
    with pytest.raises(ContractError):parse_json(s)


@pytest.mark.parametrize('key',['EXPECTED_PROBABILITY_OF_SUCCESS','expected-alpha','P_SUCCESS'])
def test_success_fields_cannot_hide_in_dynamic_search_parameters(key):
    x=card();x['SEARCH_SURFACE']['PARAMETERS'][key]=[0.8]
    with pytest.raises(ContractError):validate_card(x,Contexts())


def test_protected_horizon_year_is_a_requirement():
    x=card();x['HORIZON']='2025'
    with pytest.raises(ContractError,match='NO_PROTECTED_YEARS'):validate_card(x,Contexts())
