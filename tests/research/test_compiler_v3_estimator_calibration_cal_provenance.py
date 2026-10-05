"""CAL provenance deviation record: digests it cites must match the committed artifacts (no simulation)."""

import hashlib
import json
from pathlib import Path

D = Path("docs/research")
N = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_deviation_record_digests_match():
    rec = json.loads((D / (N + "CAL_PROVENANCE_DEVIATION_V1.json")).read_text())
    assert rec["FACTS"]["BINDING_SHA256"] == sha(D / (N + "EXECUTION_BINDING_V1.json"))
    assert rec["FACTS"]["AUTHORIZATION_SHA256"] == sha(D / (N + "CAL_AUTHORIZATION_V1.json"))
    assert rec["CHECKPOINT_RECONSTRUCTION"]["COMMITTED_COPY_SHA256"] == sha(D / (N + "C_TABLE_V1.json")) == rec["CHECKPOINT_RECONSTRUCTION"]["REBUILT_C_TABLE_SHA256"]
    assert rec["DRIVER_AUDIT"]["COMMITTED_DRIVER_SHA256"] == sha("scripts/research/compiler_v3_estimator_calibration/cal_official.py")
    assert rec["CAL_ADMISSIBILITY_STATUS"] == "CAL_ADMISSIBLE_WITH_RECORDED_PROVENANCE_DEVIATION"
    assert rec["PRE_RUN_EVIDENCE"]["DRIVER_PRE_RUN_HASH_EVIDENCE"] == "NO"
    assert rec["EVAL_GOVERNANCE_RULE"]["EVAL_AUTHORIZATION_CREATED_IN_THIS_STEP"] is False
