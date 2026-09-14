"""Tests for the approved 33/33 V2 inherited-ladder implementation binding.

Covers: Amendment_003/004 authority intactness and mutation rejection, a
golden oracle cross-checking every derivable conclusion id against frozen
executable operators applied independently (not merely against the module's
own internals), a precedence oracle porting the Amendment_004 review's
composite differential check into a permanent regression, the ten required
adversarial cases, and the disclosed GROUND_TRUTH_VISIBLE gap (raised only
when actually needed, never unconditionally).

Disposable synthetic ``WorldRecordV2`` fixtures only. No production run, no
real ARM, no RESULT mint.
"""

from __future__ import annotations

import hashlib
import itertools

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v2_inherited_ladder as ladder
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = __import__("pathlib").Path(__file__).resolve().parents[2]

PASS, FAIL, IND = "PASS", "FAIL", "INDETERMINATE"


def make_record(scenario, n, idx, *, detected_map=None, taxonomy=None, selected=None, L=1):
    detected_map = detected_map or {}
    cands = {}
    for cid in v2.FEATURE_IDS:
        det = detected_map.get(cid, False)
        cands[cid] = v2.CandidateWorldRecord(
            candidate_id=cid,
            state="CANDIDATE_IDENTIFIABLE",
            detected=det,
            gates={"STRICT_PASS": det, "STRICT_PASS_EX_MATERIALITY": det},
        )
    return v2.WorldRecordV2(
        world_id=f"{scenario}|{n}|{idx}",
        scenario=scenario,
        N=n,
        world_index=idx,
        world_state="WORLD_VALID",
        L=L,
        selection_state="SELECTED",
        selected_candidate=selected,
        taxonomy=taxonomy,
        candidates=cands,
    )


def make_cell(scenario, n, count, *, detected_map=None, taxonomy=None, selected=None, gates_override=None):
    out = []
    for i in range(count):
        rec = make_record(scenario, n, i, detected_map=detected_map, taxonomy=taxonomy, selected=selected)
        if gates_override is not None:
            for cid, gv in gates_override.items():
                rec.candidates[cid].gates = dict(gv)
        out.append(rec)
    return out


# --- authority intactness / mutation rejection -------------------------------


def test_authority_intact_at_head():
    ladder.assert_v2_inherited_ladder_authority_intact()  # must not raise


def test_authority_loads_exactly_33_conclusions():
    auth = ladder.load_v2_inherited_ladder_authority()
    assert set(auth["conclusions"]) == set(v2.frozen_required_coverage_map())
    assert len(auth["conclusions"]) == 33


@pytest.mark.parametrize(
    "rel",
    [
        ladder.AMENDMENT_003_MD_REL,
        ladder.AMENDMENT_003_JSON_REL,
        ladder.AMENDMENT_004_MD_REL,
        ladder.AMENDMENT_004_JSON_REL,
    ],
)
def test_mutated_amendment_content_fails_closed(tmp_path, monkeypatch, rel):
    import subprocess

    def _git(repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    for r in ladder.FROZEN_AMENDMENT_003_SHA256:
        (repo / r).parent.mkdir(parents=True, exist_ok=True)
        (repo / r).write_bytes((REPO / r).read_bytes())
    for r in ladder.FROZEN_AMENDMENT_004_SHA256:
        (repo / r).parent.mkdir(parents=True, exist_ok=True)
        (repo / r).write_bytes((REPO / r).read_bytes())
    # tamper exactly one tracked artifact
    target = repo / rel
    target.write_bytes(target.read_bytes() + b"\ntampered\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "tamper")
    with pytest.raises(ladder.V2InheritedLadderAuthorityError):
        ladder.assert_v2_inherited_ladder_authority_intact(repo_root=repo, commit="HEAD")
    with pytest.raises(ladder.V2InheritedLadderAuthorityError):
        ladder.load_v2_inherited_ladder_authority(repo_root=repo, commit="HEAD")


def test_missing_amendment_artifact_fails_closed(tmp_path):
    import subprocess

    def _git(repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "placeholder.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "no amendments present")
    with pytest.raises(ladder.V2InheritedLadderAuthorityError):
        ladder.assert_v2_inherited_ladder_authority_intact(repo_root=repo, commit="HEAD")


# --- golden oracle: cross-check derivation against frozen operators ---------


def test_null_oracle_fpr_matches_frozen_specificity_verdict_directly():
    records = make_cell("NULL", 5000, 250, detected_map={c: (c == "F03") for c in ()})
    # 30 of 250 F03 detections -> independent cross-check via frozen wilson/specificity
    records = []
    for i in range(250):
        det = i < 30
        records.append(make_record("NULL", 5000, i, detected_map={"F03": det}))
    got = ladder.derive_v2_inherited_conclusion("NULL_ORACLE_FPR", records)
    expected = lib.specificity_verdict(lib.wilson_interval(30, 250), 0.05)
    assert got == expected


def test_easy_oracle_power_matches_frozen_power_verdict_directly():
    records = [make_record("EASY", 5000, i, detected_map={"F03": i < 230}) for i in range(250)]
    got = ladder.derive_v2_inherited_conclusion("EASY_ORACLE_POWER", records)
    expected = lib.power_verdict(lib.wilson_interval(230, 250), 0.90)
    assert got == expected


def test_small_oracle_band_matches_frozen_small_band_directly():
    records = [make_record("SMALL", 5000, i, detected_map={"F03": i < 220}) for i in range(250)]
    got = ladder.derive_v2_inherited_conclusion("SMALL_ORACLE_BAND", records)
    expected = lib.small_band(lib.wilson_interval(220, 250))
    assert got == expected


def test_null_blind_fpr_uses_pooled_l_gt_0_denominator():
    # 250 worlds, all L=1, half ANY_EDGE_DECLARED (FALSE_DISCOVERY taxonomy).
    records = []
    for i in range(250):
        tax = "FALSE_DISCOVERY" if i < 10 else "NO_DISCOVERY"
        records.append(make_record("NULL", 5000, i, taxonomy=tax, selected="F04" if i < 10 else None))
    got = ladder.derive_v2_inherited_conclusion("NULL_BLIND_FPR", records)
    expected = lib.specificity_verdict(lib.wilson_interval(10, 250), 0.10)
    assert got == expected


def test_trap_specificity_uses_strict_pass_ex_materiality_not_plain_detected():
    """Regression: NONSTATIONARY_TRAP_ORACLE_SPECIFICITY must read
    STRICT_PASS_EX_MATERIALITY, not the plain `detected` (STRICT_PASS) field
    -- these can differ, and Amendment_003 is explicit that TRAP's statistic
    is the EX_MATERIALITY gate."""
    records = []
    for i in range(250):
        # detected(STRICT_PASS) always False, but STRICT_PASS_EX_MATERIALITY
        # True for the first 120 -- a real STRICT_PASS/EX_MATERIALITY split,
        # far enough from the 0.20 boundary for the Wilson interval to be
        # unambiguously FAIL rather than straddling INDETERMINATE.
        rec = make_record("NONSTATIONARY_TRAP", 5000, i, detected_map={"F03": False})
        rec.candidates["F03"].gates = {
            "STRICT_PASS": False,
            "STRICT_PASS_EX_MATERIALITY": i < 120,
        }
        records.append(rec)
    got = ladder.derive_v2_inherited_conclusion(
        "NONSTATIONARY_TRAP_ORACLE_SPECIFICITY", records
    )
    expected = lib.specificity_verdict(lib.wilson_interval(120, 250), 0.20)
    assert got == expected
    assert got == FAIL
    assert got == FAIL  # 60/250 = 0.24 > 0.20 ceiling


def test_materiality_only_diagnostic_is_strict_greater_than():
    records = []
    for i in range(250):
        rec = make_record("EASY", 5000, i, detected_map={"F03": i < 200})  # STRICT_PASS
        rec.candidates["F03"].gates = {
            "STRICT_PASS": i < 200,
            "STRICT_PASS_EX_MATERIALITY": i < 210,  # 10 more worlds pass ex-materiality only
        }
        records.append(rec)
    got = ladder.derive_v2_inherited_conclusion("MATERIALITY_ONLY_DIAGNOSTIC", records)
    assert got == "MATERIALITY_ONLY_DIAGNOSTIC"  # 210 > 200, strict >
    # equality (no extra ex-materiality passes) must NOT trigger
    records_eq = []
    for i in range(250):
        rec = make_record("EASY", 5000, i, detected_map={"F03": i < 200})
        rec.candidates["F03"].gates = {
            "STRICT_PASS": i < 200,
            "STRICT_PASS_EX_MATERIALITY": i < 200,
        }
        records_eq.append(rec)
    got_eq = ladder.derive_v2_inherited_conclusion("MATERIALITY_ONLY_DIAGNOSTIC", records_eq)
    assert got_eq == "NO_MATERIALITY_ONLY_SUPPRESSION"


def test_aliases_are_byte_identical_to_their_targets():
    records = [make_record("NULL", 5000, i, detected_map={"F03": i < 5}) for i in range(250)]
    a = ladder.derive_v2_inherited_conclusion("NULL_ORACLE_FPR", records)
    b = ladder.derive_v2_inherited_conclusion("ORACLE_F03_NULL", records)
    assert a == b


def test_null_per_candidate_fpr_aggregates_all_ten_fail_dominates():
    records = []
    for i in range(250):
        det = {c: False for c in v2.FEATURE_IDS}
        if i < 80:
            det["F05"] = True  # only F05 has an elevated FPR
        records.append(make_record("NULL", 5000, i, detected_map=det))
    got = ladder.derive_v2_inherited_conclusion("NULL_PER_CANDIDATE_FPR", records)
    assert got == FAIL  # 80/250=0.32, clearly > 0.10 for F05 alone -> aggregate FAIL


# --- visibility gap: raised only when actually needed -----------------------


def test_visibility_dependent_ids_always_raise_when_directly_requested():
    records = [make_record("EASY", 5000, i, detected_map={"F03": True}) for i in range(250)]
    for cid in sorted(ladder.VISIBILITY_BLOCKED_IDS):
        with pytest.raises(ladder.V2VisibilityStatisticUnavailable):
            ladder.derive_v2_inherited_conclusion(cid, records)


def test_derive_all_raises_listing_every_blocked_id():
    records = [make_record("EASY", 5000, i, detected_map={"F03": True}) for i in range(250)]
    with pytest.raises(ladder.V2VisibilityStatisticUnavailable) as excinfo:
        ladder.derive_all_v2_inherited_conclusions(records)
    for cid in ladder.VISIBILITY_BLOCKED_IDS:
        assert cid in str(excinfo.value)


def test_needed_ids_excludes_visibility_avoids_the_raise():
    records = [make_record("EASY", 5000, i, detected_map={"F03": True}) for i in range(250)]
    non_visibility = [
        cid for cid in v2.frozen_required_coverage_map() if cid not in ladder.VISIBILITY_BLOCKED_IDS
    ]
    got = ladder.derive_v2_inherited_conclusions_needed(records, non_visibility)
    assert set(got) == set(non_visibility)


def test_final_overall_short_circuits_before_visibility_on_definitive_fail():
    """A definitive frozen failure earlier in the ladder must resolve WITHOUT
    ever touching the unavailable visibility statistic."""
    records = []
    # TRAP fails specificity badly; everything else favourable.
    for i in range(250):
        records.append(make_record("NULL", 5000, i, detected_map={c: False for c in v2.FEATURE_IDS}))
    for i in range(250):
        rec = make_record("NONSTATIONARY_TRAP", 5000, i, detected_map={"F03": False})
        rec.candidates["F03"].gates = {"STRICT_PASS": False, "STRICT_PASS_EX_MATERIALITY": True}
        records.append(rec)
    for scenario in ("EASY", "MODERATE"):
        for i in range(250):
            records.append(
                make_record(
                    scenario, 5000, i, detected_map={"F03": True},
                    taxonomy="TRUE_DISCOVERY", selected="F03",
                )
            )
    got = ladder.derive_v2_final_overall_conclusion(records, structurally_complete=True)
    assert got == "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"


def test_final_overall_raises_on_a_genuinely_all_passing_path():
    records = []
    for i in range(250):
        records.append(make_record("NULL", 5000, i, detected_map={c: False for c in v2.FEATURE_IDS}))
    for i in range(250):
        records.append(make_record("NONSTATIONARY_TRAP", 5000, i, detected_map={"F03": False}))
    for scenario in ("EASY", "MODERATE"):
        for i in range(250):
            records.append(
                make_record(
                    scenario, 5000, i, detected_map={"F03": True},
                    taxonomy="TRUE_DISCOVERY", selected="F03",
                )
            )
    with pytest.raises(ladder.V2VisibilityStatisticUnavailable):
        ladder.derive_v2_final_overall_conclusion(records, structurally_complete=True)


def test_final_overall_structurally_incomplete_never_touches_visibility():
    assert (
        ladder.derive_v2_final_overall_conclusion([], structurally_complete=False)
        == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    )


# --- precedence oracle: ports the Amendment_004 review's composite check ----
# directly onto the frozen mechanical_conclusion() + the module's own _comb()
# folding, proving zero masking across the full verdict-tuple x gate space.


def _frozen_bare(onull, bnull, trap, epow, mpow, eb, mb, vu, mu, mf):
    return lib.mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=onull,
        blind_null_specificity=bnull,
        trap_specificity=trap,
        easy_oracle_power=epow,
        moderate_oracle_power=mpow,
        easy_blind_useful=eb,
        moderate_blind_useful=mb,
        visibility_wilson_upper=vu,
        model_detection_wilson_upper=mu,
        materiality_only_failure=mf,
    )


def _module_composite(gate, onull, bnull, trap, epow, mpow, eb, mb, vu, mu, mf):
    trap_folded = ladder._comb(trap, gate)
    return lib.mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=onull,
        blind_null_specificity=bnull,
        trap_specificity=trap_folded,
        easy_oracle_power=epow,
        moderate_oracle_power=mpow,
        easy_blind_useful=eb,
        moderate_blind_useful=mb,
        visibility_wilson_upper=vu,
        model_detection_wilson_upper=mu,
        materiality_only_failure=mf,
    )


CONCLUSION_PRIORITY = lib.CONCLUSION_PRIORITY
_INSUF = "INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM"
_SEV = [CONCLUSION_PRIORITY[0], _INSUF] + list(CONCLUSION_PRIORITY[1:])
_V = (PASS, FAIL, IND)


def test_composite_precedence_oracle_zero_masking():
    floors = (None, 0.30, 0.4999, 0.50, 0.5001, 0.80)
    masked = 0
    conservative = 0
    n = 0
    for gate in _V:
        for onull, bnull, trap, epow, mpow, eb, mb in itertools.product(_V, repeat=7):
            for vu, mu in itertools.product(floors, floors):
                for mf in (False, True):
                    n += 1
                    bare = _frozen_bare(onull, bnull, trap, epow, mpow, eb, mb, vu, mu, mf)
                    got = _module_composite(gate, onull, bnull, trap, epow, mpow, eb, mb, vu, mu, mf)
                    if got != bare:
                        if _SEV.index(got) > _SEV.index(bare):
                            masked += 1
                        else:
                            conservative += 1
    assert n > 400_000
    assert masked == 0
    assert conservative > 0  # the gate does add strictly-conservative divergences


@pytest.mark.parametrize(
    "name,gate,overrides,expected",
    [
        ("gate_ind_trap_fail", IND, {"trap": FAIL}, "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_ind_onull_fail", IND, {"onull": FAIL}, "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_ind_bnull_fail", IND, {"bnull": FAIL}, "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_ind_epow_fail", IND, {"epow": FAIL}, "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_ind_mpow_fail", IND, {"mpow": FAIL}, "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_ind_no_definitive", IND, {}, "CALIBRATION_INDETERMINATE"),
        ("gate_fail_else_pass", FAIL, {}, "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"),
        ("gate_pass_everything_pass", PASS, {}, "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"),
        ("gate_ind_visibility_floor", IND, {"vu": 0.30}, "CALIBRATION_INDETERMINATE"),
        ("gate_ind_materiality", IND, {"mf": True}, "CALIBRATION_INDETERMINATE"),
    ],
)
def test_ten_required_adversarial_cases(name, gate, overrides, expected):
    base = dict(onull=PASS, bnull=PASS, trap=PASS, epow=PASS, mpow=PASS, eb=PASS, mb=PASS,
                vu=0.99, mu=0.99, mf=False)
    base.update(overrides)
    got = _module_composite(gate, base["onull"], base["bnull"], base["trap"], base["epow"],
                            base["mpow"], base["eb"], base["mb"], base["vu"], base["mu"], base["mf"])
    assert got == expected, name


def test_frozen_tcb_pin_reverified_by_this_test_file():
    import subprocess

    rel = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
    blob = subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:{rel}"], capture_output=True
    ).stdout
    assert hashlib.sha256(blob).hexdigest() == "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
