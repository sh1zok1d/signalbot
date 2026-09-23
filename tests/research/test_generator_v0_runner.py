import pytest
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.provider import Caller,MockProvider
from scripts.research.generator_v0.mock import MockResponder,fixture,slot_plan
from scripts.research.generator_v0.runner import run_campaign,diversity

def execute(path):
    c=Contexts();l=Ledger(path,{'RUN_ID':path.name});p=MockProvider(MockResponder(c));return run_campaign(c,Caller(c,l,p)),l,p

def test_full_pipeline_and_resume(tmp_path):
    result,l,p=execute(tmp_path/'one.sqlite')
    assert len(result['CANDIDATES'])==40
    assert len(result['STREAM_A'])>0 and len(result['STREAM_B'])>0
    assert len(result['SHORTLIST'])==5
    assert len(result['STREAM_A'])+len(result['STREAM_B'])==35
    assert p.calls==125
    before=p.calls
    assert run_campaign(Contexts(),Caller(Contexts(),l,p))==result
    assert p.calls==before
    assert len(l.export_calls())==125
    assert result['STATUS']=='PENDING_HUMAN_REVIEW'
    assert all(set(r['ORDINAL_JUDGMENTS'])==set(Contexts().design['GENERATOR_EVALUATION_CRITERIA']['PER_CANDIDATE_DIMENSIONS']) for r in result['REVIEWS'])

def test_mock_semantic_reproducibility(tmp_path):
    a,_,_=execute(tmp_path/'a.sqlite');b,_,_=execute(tmp_path/'b.sqlite')
    assert a['SEMANTIC_RESULT_DIGEST']==b['SEMANTIC_RESULT_DIGEST']

def test_diversity_duplicate_id(tmp_path):
    c=Contexts();cards=[fixture(s,c) for s in slot_plan()];cards[1]['CANDIDATE_ID']=cards[0]['CANDIDATE_ID']
    with pytest.raises(ContractError):diversity(cards,c)
