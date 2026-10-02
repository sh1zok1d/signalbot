"""Outcome-blind feasibility compiler, GV0R02_SCHEMA_V2.

Stricter layer over the unchanged V1 compiler. V0 and V1 keep their own
functions and their own results. A proposal is scored here only when it
declares GV0R02_SCHEMA_V2 / GV0R02_POLICY_V2.

V2 adds an outcome-blind primary-mechanism support check before analytic
power is treated as meaningful:

- a binary mechanism variable must vary (both active and inactive counts > 0);
- an all-zero or all-one binary label under PERMUTATION_GROUP_INVARIANCE has
  orbit size 1, so alpha is not attainable;
- discovery power for a binary contrast uses
  n_eff = active * inactive / (active + inactive), never the nominal sample
  size alone;
- a prospective sparse-state design must declare MIN_MECHANISM_ACTIVE_N and
  MIN_MECHANISM_INACTIVE_N. This module does not choose those numbers.

No market target is read. Zero support is an identifiability failure, not a
statement about the mechanism.
"""

from __future__ import annotations

import copy

from scripts.research import gv0r02_feasibility_compiler as v0
from scripts.research import gv0r02_feasibility_compiler_v1 as v1

COMPILER_SCHEMA_VERSION = "GV0R02_SCHEMA_V2"
COMPILER_POLICY_VERSION = "GV0R02_POLICY_V2"
EVALUATION_CONTRACT = v1.EVALUATION_CONTRACT
POWER_PROFILE = v0.POWER_PROFILE
STATUS_PRIORITY = list(v0.STATUS_PRIORITY)

# Fail-closed sparsity screen for a prospective stopping rule that only
# counts episodes. Not a market threshold and not a per-card parameter.
SPARSE_STATE_MINORITY_FRACTION = 0.05
POWER_BLOCKERS = {"MDE_TOO_LARGE", "REPLICATION_MDE_TOO_LARGE"}


def binary_contrast_effective_n(active: int, inactive: int) -> float | None:
    """Two-sample effective N. Undefined when either side has no observations."""
    if active <= 0 or inactive <= 0:
        return None
    return (active * inactive) / (active + inactive)


def _nonneg_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _pos_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _block(code: str, **obj) -> dict:
    return {"BLOCKER_CODE": code, "BLOCKER_OBJECT": obj}


def _sparse(active: int, inactive: int) -> bool:
    total = active + inactive
    if total <= 0:
        return True
    return (min(active, inactive) / total) < SPARSE_STATE_MINORITY_FRACTION


def _support_rows(proposal: dict) -> tuple[list[dict], list[dict]]:
    """One BINARY support row per primary cell. Outcome values are not read."""
    cells = proposal.get("PRIMARY_CELLS")
    cells = cells if isinstance(cells, list) else []
    raw = proposal.get("PRIMARY_MECHANISM_SUPPORT")
    if not cells or not isinstance(raw, list) or len(raw) != len(cells):
        return [], [_block(
            "PRIMARY_MECHANISM_SUPPORT_MISSING",
            PRIMARY_CELLS=len(cells),
            SUPPORT_ROWS=len(raw) if isinstance(raw, list) else None,
        )]
    rows = []
    blockers = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict) or row.get("KIND") != "BINARY":
            blockers.append(_block(
                "PRIMARY_MECHANISM_SUPPORT_MISSING",
                CELL_INDEX=index,
                REASON="KIND must be BINARY",
            ))
            continue
        active, inactive = row.get("MECHANISM_ACTIVE_N"), row.get("MECHANISM_INACTIVE_N")
        if not _nonneg_int(active) or not _nonneg_int(inactive):
            blockers.append(_block(
                "PRIMARY_MECHANISM_SUPPORT_MISSING",
                CELL_INDEX=index,
                REASON="MECHANISM_ACTIVE_N and MECHANISM_INACTIVE_N must be non-negative integers",
            ))
            continue
        variable = row.get("MECHANISM_VARIABLE")
        if variable is not None and not _text(variable):
            blockers.append(_block(
                "PRIMARY_MECHANISM_SUPPORT_MISSING",
                CELL_INDEX=index,
                REASON="MECHANISM_VARIABLE must be a name when present",
            ))
            continue
        if active == 0 and inactive == 0:
            side = "BOTH"
        elif active == 0:
            side = "ACTIVE"
        elif inactive == 0:
            side = "INACTIVE"
        else:
            side = None
        parsed = {
            "CELL_INDEX": index,
            "KIND": "BINARY",
            "MECHANISM_VARIABLE": variable,
            "MECHANISM_ACTIVE_N": active,
            "MECHANISM_INACTIVE_N": inactive,
            "IDENTIFIABLE": side is None,
            "EFFECTIVE_N": binary_contrast_effective_n(active, inactive),
            "SPARSE_STATE": _sparse(active, inactive),
            "ZERO_SIDE": side,
        }
        rows.append(parsed)
        if side is not None:
            blockers.append(_block("PRIMARY_MECHANISM_SUPPORT_ZERO", **parsed))
    return rows, blockers


def _constant_label(rows: list[dict]) -> dict | None:
    """All-zero or all-one binary assignment. Orbit size is 1; targets are not used."""
    if not rows:
        return None
    if any(row["MECHANISM_ACTIVE_N"] == 0 or row["MECHANISM_INACTIVE_N"] == 0 for row in rows):
        return {
            "PRIMARY_LABEL_ORBIT_SIZE": 1,
            "MIN_ATTAINABLE_P": 1.0,
            "ALPHA_ATTAINABLE": False,
        }
    return None


def _prospective_guarantee(proposal: dict, rows: list[dict], support_missing: bool) -> dict | None:
    replication = proposal.get("REPLICATION_SURFACE")
    if not isinstance(replication, dict) or replication.get("KIND") != "PROSPECTIVE":
        return None
    sparse = support_missing or any(row["SPARSE_STATE"] for row in rows)
    if not sparse:
        return {"APPLIES": False, "GUARANTEED": None}
    rule = replication.get("STOPPING_RULE")
    rule = rule if isinstance(rule, dict) else {}
    active_min = rule.get("MIN_MECHANISM_ACTIVE_N")
    inactive_min = rule.get("MIN_MECHANISM_INACTIVE_N")
    guaranteed = _pos_int(active_min) and _pos_int(inactive_min)
    return {
        "APPLIES": True,
        "GUARANTEED": guaranteed,
        "MIN_MECHANISM_ACTIVE_N": active_min if guaranteed else None,
        "MIN_MECHANISM_INACTIVE_N": inactive_min if guaranteed else None,
    }


def _screen(n_eff: float | None, effect, z_alpha: float, *, replication: bool) -> dict:
    stress_sd = POWER_PROFILE["BASE_SD"] * POWER_PROFILE["STRESS_SD_MULTIPLIER"]
    if n_eff is None:
        body = {
            "MDE_BASE": None,
            "MDE_STRESS": None,
            "POWER_BASE": None,
            "POWER_STRESS": None,
            "EFFECTIVE_N": None,
            "NON_IDENTIFIABLE": True,
        }
        if replication:
            return {"MDE_STRESS": None, "POWER_STRESS": None, "EFFECTIVE_N": None, "NON_IDENTIFIABLE": True}
        return body
    full = {
        "MDE_BASE": v1._mde(POWER_PROFILE["BASE_SD"], n_eff, z_alpha),
        "MDE_STRESS": v1._mde(stress_sd, n_eff, z_alpha),
        "POWER_BASE": v1._power(effect, POWER_PROFILE["BASE_SD"], n_eff, z_alpha),
        "POWER_STRESS": v1._power(effect, stress_sd, n_eff, z_alpha),
        "EFFECTIVE_N": n_eff,
        "NON_IDENTIFIABLE": False,
    }
    if replication:
        return {
            "MDE_STRESS": full["MDE_STRESS"],
            "POWER_STRESS": full["POWER_STRESS"],
            "EFFECTIVE_N": n_eff,
            "NON_IDENTIFIABLE": False,
        }
    return full


def _weak(numbers: dict, effect, inference) -> bool:
    power_stress, mde_stress = numbers.get("POWER_STRESS"), numbers.get("MDE_STRESS")
    if numbers.get("NON_IDENTIFIABLE") is True:
        return False
    if power_stress is not None and power_stress < POWER_PROFILE["TARGET_POWER"]:
        return True
    return (
        mde_stress is not None
        and effect is not None
        and abs(mde_stress) > abs(effect)
        and inference != "PLACEBO_REFERENCE_DISTRIBUTION"
    )


def _discovery_n(rows: list[dict], support_missing: bool) -> float | None:
    if support_missing or not rows or any(row["EFFECTIVE_N"] is None for row in rows):
        return None
    return min(row["EFFECTIVE_N"] for row in rows)


def _replication_n(proposal: dict, rows: list[dict], support_missing: bool, prospective: dict | None):
    """Return (n_eff or None, null_the_screen)."""
    if support_missing:
        return None, True
    if prospective is not None and prospective["APPLIES"]:
        if not prospective["GUARANTEED"]:
            return None, True
        return binary_contrast_effective_n(
            prospective["MIN_MECHANISM_ACTIVE_N"],
            prospective["MIN_MECHANISM_INACTIVE_N"],
        ), False
    if rows and any(row["EFFECTIVE_N"] is None for row in rows):
        return None, True
    return None, False


def compile_proposal_v2(proposal: dict, *, registry: dict | None = None) -> dict:
    registry = registry or v0.derive_feature_registry()
    schema_ok = proposal.get("COMPILER_SCHEMA_VERSION") == COMPILER_SCHEMA_VERSION
    policy_ok = proposal.get("COMPILER_POLICY_VERSION") == COMPILER_POLICY_VERSION

    v1_input = copy.deepcopy(proposal)
    v1_input["COMPILER_SCHEMA_VERSION"] = v1.COMPILER_SCHEMA_VERSION
    v1_input["COMPILER_POLICY_VERSION"] = v1.COMPILER_POLICY_VERSION
    base = v1.compile_proposal_v1(v1_input, registry=registry)

    blockers = [b for b in base["BLOCKERS"] if b["BLOCKER_CODE"] not in POWER_BLOCKERS]
    flags = {status: False for status in STATUS_PRIORITY}
    power_only = (
        base["FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
        and bool(base["BLOCKERS"])
        and all(b["BLOCKER_CODE"] in POWER_BLOCKERS for b in base["BLOCKERS"])
    )
    if base["FEASIBILITY_STATUS"] != "FEASIBLE_FOR_PREREGISTRATION" and not power_only:
        flags[base["FEASIBILITY_STATUS"]] = True
    reasons = [
        reason for reason in base["STATUS_REASONS"]
        if "stress screen" not in reason and reason != "no harder status matched"
    ]

    if not schema_ok or not policy_ok:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("schema or policy version is not GV0R02 V2")
        blockers.append(_block(
            "DEFINITION_INCOMPLETE",
            FIELDS=["COMPILER_SCHEMA_VERSION", "COMPILER_POLICY_VERSION"],
            REQUIRED_SCHEMA=COMPILER_SCHEMA_VERSION,
            REQUIRED_POLICY=COMPILER_POLICY_VERSION,
        ))

    rows, support_blockers = _support_rows(proposal)
    support_missing = any(b["BLOCKER_CODE"] == "PRIMARY_MECHANISM_SUPPORT_MISSING" for b in support_blockers)
    zero_support = any(b["BLOCKER_CODE"] == "PRIMARY_MECHANISM_SUPPORT_ZERO" for b in support_blockers)
    if support_missing:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("primary mechanism support was not declared for every primary cell")
    if zero_support:
        flags["INFERENCE_SUPPORT_INSUFFICIENT"] = True
        reasons.append("primary mechanism variable has no variation")
    blockers += support_blockers

    passes = base["V0_PASSES"]
    orbit = passes["PRIMARY_SUPPORT_SIZE"]
    min_p = passes["MIN_ATTAINABLE_P"]
    alpha_attainable = passes["ALPHA_ATTAINABLE"]
    if proposal.get("NAMED_INFERENCE_CLASS") == "PERMUTATION_GROUP_INVARIANCE":
        derived = _constant_label(rows)
        if derived is not None:
            orbit = derived["PRIMARY_LABEL_ORBIT_SIZE"]
            min_p = derived["MIN_ATTAINABLE_P"]
            alpha_attainable = derived["ALPHA_ATTAINABLE"]
            if "ALPHA_UNATTAINABLE" not in {b["BLOCKER_CODE"] for b in blockers}:
                flags["INFERENCE_SUPPORT_INSUFFICIENT"] = True
                reasons.append("all-zero or all-one permutation label has orbit size 1")
                blockers.append(_block(
                    "ALPHA_UNATTAINABLE",
                    MIN_ATTAINABLE_P=min_p,
                    ALPHA=POWER_PROFILE["ALPHA"],
                    PRIMARY_LABEL_ORBIT_SIZE=orbit,
                ))

    prospective = _prospective_guarantee(proposal, rows, support_missing)
    if prospective is not None and prospective["APPLIES"] and not prospective["GUARANTEED"]:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("prospective sparse-state design does not guarantee mechanism support")
        blockers.append(_block(
            "PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED",
            REQUIRED=["MIN_MECHANISM_ACTIVE_N", "MIN_MECHANISM_INACTIVE_N"],
            SPARSE_STATE_MINORITY_FRACTION=SPARSE_STATE_MINORITY_FRACTION,
        ))

    cells = proposal.get("PRIMARY_CELLS") if isinstance(proposal.get("PRIMARY_CELLS"), list) else []
    k = max(1, min(len(cells), v1.MAX_PRIMARY_CELLS)) if cells else 1
    alpha_cell = POWER_PROFILE["ALPHA"] / k
    z_cell = v1.z_two_sided(alpha_cell)
    effect = proposal.get("MIN_MEANINGFUL_EFFECT")
    inference = proposal.get("NAMED_INFERENCE_CLASS")

    discovery = _screen(_discovery_n(rows, support_missing), effect, z_cell, replication=False)
    if _weak(discovery, effect, inference):
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("discovery stress screen misses the target at the mechanism effective N")
        blockers.append(_block(
            "MDE_TOO_LARGE",
            SURFACE="DISCOVERY",
            MIN_MEANINGFUL_EFFECT=effect,
            MDE_STRESS=discovery["MDE_STRESS"],
            POWER_STRESS=discovery["POWER_STRESS"],
            EFFECTIVE_N=discovery["EFFECTIVE_N"],
            ALPHA_PER_CELL=alpha_cell,
        ))

    rep_n, null_replication = _replication_n(proposal, rows, support_missing, prospective)
    if null_replication:
        replication = _screen(None, effect, z_cell, replication=True)
    elif rep_n is not None:
        replication = _screen(rep_n, effect, z_cell, replication=True)
    else:
        replication = dict(base["REPLICATION_SCREEN"])
        replication["NON_IDENTIFIABLE"] = False
        replication["EFFECTIVE_N"] = None
    if not flags["DEFINITION_INCOMPLETE"] and _weak(replication, effect, inference):
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("replication stress screen misses the target at the mechanism effective N")
        blockers.append(_block(
            "REPLICATION_MDE_TOO_LARGE",
            SURFACE="REPLICATION",
            N=rep_n,
            **replication,
        ))

    if not any(flags[status] for status in STATUS_PRIORITY if status != "FEASIBLE_FOR_PREREGISTRATION"):
        flags["FEASIBLE_FOR_PREREGISTRATION"] = True
        reasons.append("no harder status matched")
    status = next(name for name in STATUS_PRIORITY if flags[name])

    digest_fields = (
        v0.REQUIRED_FIELDS
        + v1.V1_REQUIRED_FIELDS
        + ["NUISANCE_EXCLUSIONS", "NUISANCE_DIAGNOSTIC_PLANNED", "PRIMARY_MECHANISM_SUPPORT"]
    )
    proposal_digest = v0.sha256_hex(v0.canonical_json({
        field: proposal[field] for field in digest_fields if field in proposal
    }))
    identity = {
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "EVALUATION_CONTRACT": EVALUATION_CONTRACT,
        "POWER_ASSUMPTION_PROFILE_VERSION": v0.POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
    }
    return {
        "RESULT_ID": v0.sha256_hex(v0.canonical_json(identity)),
        "PROPOSAL_ID": proposal.get("PROPOSAL_ID"),
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "EVALUATION_CONTRACT": EVALUATION_CONTRACT,
        "POWER_ASSUMPTION_PROFILE_VERSION": v0.POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
        "V1_LAYER": {
            "FEASIBILITY_STATUS": base["FEASIBILITY_STATUS"],
            "BLOCKERS": base["BLOCKERS"],
            "DISCOVERY_SCREEN": base["DISCOVERY_SCREEN"],
            "REPLICATION_SCREEN": base["REPLICATION_SCREEN"],
            "ALPHA_ATTAINABLE": passes["ALPHA_ATTAINABLE"],
            "MIN_ATTAINABLE_P": passes["MIN_ATTAINABLE_P"],
            "COMPILER_SCHEMA_VERSION": base["COMPILER_SCHEMA_VERSION"],
            "COMPILER_POLICY_VERSION": base["COMPILER_POLICY_VERSION"],
        },
        "CLAIM_TYPE": proposal.get("CLAIM_TYPE"),
        "TARGET_CLASS": proposal.get("TARGET_CLASS"),
        "PRIMARY_CELL_COUNT": len(cells),
        "PRIMARY_MECHANISM_SUPPORT": rows,
        "ALPHA_PER_CELL_HOLM_FIRST_STEP": alpha_cell,
        "PRIMARY_LABEL_ORBIT_SIZE": orbit,
        "MIN_ATTAINABLE_P": min_p,
        "ALPHA_ATTAINABLE": alpha_attainable,
        "DISCOVERY_SCREEN": discovery,
        "REPLICATION_KIND": (proposal.get("REPLICATION_SURFACE") or {}).get("KIND")
        if isinstance(proposal.get("REPLICATION_SURFACE"), dict) else None,
        "REPLICATION_SCREEN": replication,
        "PROSPECTIVE_MECHANISM_SUPPORT": prospective,
        "HETEROGENEITY_ASSESSABILITY": base["HETEROGENEITY_ASSESSABILITY"],
        "PROTECTED_OVERLAP": base["PROTECTED_OVERLAP"],
        "MIN_MEANINGFUL_EFFECT": effect,
        "TARGET_POWER": POWER_PROFILE["TARGET_POWER"],
        "SPARSE_STATE_MINORITY_FRACTION": SPARSE_STATE_MINORITY_FRACTION,
        "BLOCKERS": blockers,
        "FEASIBILITY_STATUS": status,
        "STATUS_REASONS": reasons,
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
    }
