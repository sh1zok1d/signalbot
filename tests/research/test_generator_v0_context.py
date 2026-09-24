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


def test_calibration_memory_is_blind_and_governed():
    c=Contexts();g=c.generator();c.validate('GENERATOR',g)
    ids=['GV0CAL-C001','GV0CAL-C002','GV0CAL-C003','GV0CAL-C004','GV0CAL-C005']
    assert all(i in c.blind for i in ids)
    assert all(c.blind[i]['REGION_STATE']=='PRIOR_WORK_SIGNATURE' for i in ids)
    # Generator projection must not reveal calibration critic dispositions.
    blob=json.dumps({i:c.blind[i] for i in ids},sort_keys=True).lower()
    for forbidden in ('pipeline_survivor','red_team','reject','causality=false','confounding_addressed=false'):
        assert forbidden not in blob
    assert c.rows['GV0CAL-C001']['STATE']=='CONSUMED'
    assert c.rows['GV0CAL-C002']['STATE']=='CONSUMED'
    assert c.rows['GV0CAL-C005']['STATE']=='CONSUMED'
    assert c.rows['GV0CAL-C003']['STATE']=='DEFERRED_OR_BLOCKED'
    assert c.rows['GV0CAL-C003']['BLOCKER_CLASS_IF_ANY']=='METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING'
    assert c.rows['GV0CAL-C004']['STATE']=='DEFERRED_OR_BLOCKED'
    assert c.rows['GV0CAL-C004']['BLOCKER_CLASS_IF_ANY']=='METHOD_CONFOUNDING_CONTROL_INADEQUATE'


def test_calibration_memory_is_available_to_novelty_authority():
    c=Contexts()
    signature_ids={row['SIGNATURE_ID'] for row in c.authority['ROWS']}
    assert {'GV0CAL-C001','GV0CAL-C002','GV0CAL-C003','GV0CAL-C004','GV0CAL-C005'} <= signature_ids
    assert len(c.blind)==len(c.authority['ROWS'])
