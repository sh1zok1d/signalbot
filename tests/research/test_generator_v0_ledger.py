import pytest
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.context import Contexts,ContractError
from scripts.research.generator_v0.provider import Caller,MockProvider

def ledger(tmp_path):return Ledger(tmp_path/'run.sqlite',{'RUN_ID':'test'})

def test_budget_reserve_uncertain_and_resume(tmp_path):
    l=ledger(tmp_path)
    assert l.reserve('a',{},10,10) is None
    with pytest.raises(ContractError):l.reserve('b',{},1,10)
    with pytest.raises(ContractError):l.reserve('a',{},10,10)
    l.finish('a',{'raw':'ok'},3,{})
    assert l.reserve('a',{},10,10)=={'raw':'ok'}
    assert l.reserve('b',{},7,10) is None
    with pytest.raises(ContractError):l.reserve('c',{},1,10)

def test_rollback_candidate_and_event(tmp_path):
    l=ledger(tmp_path)
    with pytest.raises(RuntimeError):
        with l.transaction():
            l.save_card({'CANDIDATE_ID':'C001'})
            l.event('test',{})
            raise RuntimeError('disk failure simulation')
    assert l.db.execute('SELECT count(*) FROM cards').fetchone()[0]==0
    assert l.db.execute('SELECT count(*) FROM events').fetchone()[0]==0

def test_response_persisted_once(tmp_path):
    l=ledger(tmp_path);c=Contexts();p=MockProvider(lambda r:'{}');caller=Caller(c,l,p)
    assert caller.call('GENERATOR',c.generator(),'Return JSON',{},'first')=='{}'
    assert caller.call('GENERATOR',c.generator(),'Return JSON',{},'first')=='{}'
    assert p.calls==1
    assert l.export_calls()[0]['RAW_RESPONSE_SHA256']

def test_mutation_requires_reason_and_transaction(tmp_path):
    l=ledger(tmp_path)
    with l.transaction():l.save_card({'CANDIDATE_ID':'C001','NAME':'before'})
    with pytest.raises(ContractError):l.mutate('C001','NAME','after','','human',lambda x:x)
    l.mutate('C001','NAME','after','correct spelling','human',lambda x:x)
    assert l.get('status')=='MUTATED_REQUIRES_REVIEW'
    assert l.db.execute('SELECT kind FROM events').fetchone()[0]=='HUMAN_MUTATION'

def test_real_provider_cannot_use_mock_authorization(tmp_path):
    class Real(MockProvider):real=True
    for cap,allow in [(0,True),(30_000_001,True),(1,False)]:
        with pytest.raises(ContractError):Caller(Contexts(),ledger(tmp_path),Real(),cap,allow)
