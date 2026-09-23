import copy
import json
import shutil
import pytest
from scripts.research.generator_v0.context import Contexts, ContractError, ROOT, DESIGN, MEMORY, ROTATION, MAP, AUTHORITY, PINS

def test_canonical_context_and_explicit_rule_provenance():
    c=Contexts();g=c.generator();c.validate('GENERATOR',g)
    assert g['GENERIC_METHODOLOGY']['GENERATOR_SIDE_RULE']==c.design['BLIND_GENERATOR_CONTEXT']['GENERATOR_SIDE_RULE']
    assert len(c.provenance())==11
    assert all(r['REGION_STATE']=='PRIOR_WORK_SIGNATURE' for r in c.blind.values())
    for card in ('D1','D2','D4','D6'):
        assert not any(word in json.dumps(c.blind[card]).lower() for word in ('reclassified','replicat','deferred','unpinned'))

@pytest.mark.parametrize('artifact', ['MECHANISM_MEMORY_V0_RAW','RESULT_ARTIFACTS','GOVERNANCE_REGION_AUTHORITY_V0','STATUS_EVIDENCE_CLASS'])
def test_generator_rejects_extra_sources(artifact):
    c=Contexts();g=c.generator();g[artifact]={}
    with pytest.raises(ContractError):c.validate('GENERATOR',g)

def test_nested_leak_and_prompt_scanner():
    c=Contexts();g=copy.deepcopy(c.generator());g['GENERIC_METHODOLOGY']['METHODOLOGY'].append('promising')
    with pytest.raises(ContractError):c.validate('GENERATOR',g)
    with pytest.raises(ContractError):c.validate('GENERATOR',Contexts().generator(),'previous experiment was executed')

@pytest.mark.parametrize('path',[MEMORY,MAP,AUTHORITY,DESIGN,ROTATION])
def test_source_drift_fails_closed(tmp_path,path):
    for p in (DESIGN,MEMORY,ROTATION,MAP,AUTHORITY,PINS):
        target=tmp_path/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
    c=Contexts(tmp_path)
    with (tmp_path/path).open('a') as f:f.write(' ')
    with pytest.raises(ContractError):c.generator()

def test_d4_states_and_selector_boundary():
    c=Contexts()
    assert c.rows['D4.ROLLING_CORRELATION_90D']['STATE']=='CONSUMED'
    assert c.rows['D4.LEAD_LAG_1DAY']['STATE']=='DEFERRED_OR_BLOCKED'
    for key in ('BLIND_MECHANISM_MAP_V0','GOVERNANCE_REGION_AUTHORITY_V0','RESULT_ARTIFACTS'):
        with pytest.raises(ContractError):c.validate('SELECTOR',{key:{}})
