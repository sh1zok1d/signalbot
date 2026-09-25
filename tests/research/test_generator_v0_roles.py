import json
import pytest
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.roles import Roles
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.ledger import Ledger
from test_generator_v0_schema import card

def roles(tmp_path,answer):
    c=Contexts();l=Ledger(tmp_path/'r.db',{'RUN_ID':'t'})
    return Roles(c,Caller(c,l,MockProvider(lambda r:json.dumps(answer))))

def novelty_answer(c,near,relation):
    # Live provider encoding: objects keyed by exact signature / candidate IDs.
    return {'PRIOR_RELATIONS':{k:relation if k==near else 'ORTHOGONAL_MECHANISM' for k,v in c.rows.items() if v['STATE']!='PARTIAL_OR_MIXED'},'BATCH_RELATIONS':{},'JUDGMENTS':{'NOVELTY':2,'MECHANISM_DISTANCE':2,'NON_RESCUE':2}}

@pytest.mark.parametrize('near',['B2-06','MARKET-04','D6','D8','D4.LEAD_LAG_1DAY'])
@pytest.mark.parametrize('relation,expected',[('EXACT_DUPLICATE','DEFER_BLOCKER_UNRESOLVED'),('RESOLVES_BLOCKER','ALLOW_TO_FEASIBILITY'),('ORTHOGONAL_MECHANISM','ALLOW'),('PARAMETER_NEIGHBOR','REJECT')])
def test_blocked_regions_preserve_new_mechanisms(tmp_path,near,relation,expected):
    r=roles(tmp_path,novelty_answer(Contexts(),near,relation));x=card()
    n=r.novelty(x,[x]);assert n['VERDICT']==expected
    if expected in ('ALLOW','ALLOW_TO_FEASIBILITY'):
        assert r.route(n,{'VERDICT':'PASS','DATA_STATUS':'FEASIBILITY_REQUIRED','CHECKS':{'BLOCKER_RESOLVED':True}},{'VERDICT':'PASS'})=='HIGH_VALUE_DATA_BLOCKED'

@pytest.mark.parametrize('relation',['EXACT_DUPLICATE','PARAMETER_NEIGHBOR','FUNCTIONAL_RELABEL'])
def test_consumed_d4_rejects(tmp_path,relation):
    r=roles(tmp_path,novelty_answer(Contexts(),'D4.ROLLING_CORRELATION_90D',relation));x=card()
    assert r.novelty(x,[x])['VERDICT']=='REJECT'

def test_extra_critic_state_rejected(tmp_path):
    a=novelty_answer(Contexts(),'D6','ORTHOGONAL_MECHANISM');a['STATE']='PROMISING_PROTOTYPE';r=roles(tmp_path,a);x=card()
    with pytest.raises(ContractError):r.novelty(x,[x])

def test_role_requests_are_separate(tmp_path):
    r=roles(tmp_path,{})
    for role in ('NOVELTY_CRITIC','FEASIBILITY_CRITIC','RED_TEAM'):
        ctx=r.request(role,card(),[card()]);r.c.validate(role,ctx)
        assert 'MECHANISM_MEMORY_V0_RAW' not in ctx
        if role!='NOVELTY_CRITIC':assert 'BLIND_MECHANISM_MAP_V0' not in ctx

def test_red_team_lookahead_rejects(tmp_path):
    a={'CHECKS':{'NO_LOOKAHEAD':False,'CAUSALITY':True,'FALSIFIABLE':True,'BOUNDED_SEARCH':True,'CONFOUNDING_ADDRESSED':True,'NO_TRADING_CLAIM':True},'JUDGMENTS':{k:1 for k in ('FALSIFIABILITY','NO_LOOKAHEAD_QUALITY','CONFOUNDING_AWARENESS','SEARCH_SURFACE_DISCIPLINE','NULL_INFORMATION_GAIN')}}
    assert roles(tmp_path,a).red_team(card())['VERDICT']=='REJECT'
