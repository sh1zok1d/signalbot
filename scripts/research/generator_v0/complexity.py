"""Complexity ladder for generated hypotheses (owner decision 2026-10-02).

Generation goes from simple to complex, and simple mechanisms stay in the
shortlist so that the library of tested base effects keeps growing.

  ATOMIC       one mechanism -> one observable -> one outcome, unconditional
  CONDITIONAL  one simple mechanism inside a regime declared in advance
  INTERACTION  two independent layers; the claim is the joint term's incremental effect
               over the components' main effects
  COMPOSITE    a market state built from 3-5 independent components; the claim is the joint
               state's incremental effect over the components' main effects

For INTERACTION and COMPOSITE the requirement is control, not prior support:
every component's main effect is in the baseline, the joint term is the
mechanism variable, and the primary claim is the joint term's increment over
those main effects. The components need not have supported effects of their
own: A ~ 0, B ~ 0 and A x B != 0 is a valid interaction.

Simplicity is not banality: an ATOMIC card still needs a market mechanism (who
acts, under which constraint, why the effect should exist). An indicator
threshold mapped to a return is a weak ATOMIC card, not a good one. That is
judged by the novelty critic, not mechanically here.

This module holds the ladder, its structural rules for a V1 planning object,
and the deterministic shortlist quota. It reads no market data.
"""
from __future__ import annotations

from .context import ContractError

ATOMIC, CONDITIONAL, INTERACTION, COMPOSITE = "ATOMIC", "CONDITIONAL", "INTERACTION", "COMPOSITE"
COMPLEXITY_CLASSES = (ATOMIC, CONDITIONAL, INTERACTION, COMPOSITE)
COMPONENT_COUNT = {ATOMIC: (0, 0), CONDITIONAL: (0, 0), INTERACTION: (2, 2), COMPOSITE: (3, 5)}

# Shortlist seats. INTERACTION and COMPOSITE share the COMPLEX seat.
SEAT_OF = {ATOMIC: ATOMIC, CONDITIONAL: CONDITIONAL, INTERACTION: "COMPLEX", COMPOSITE: "COMPLEX"}
SHORTLIST_QUOTA = (("ATOMIC", 2), ("CONDITIONAL", 2), ("COMPLEX", 1))
# An unfilled seat passes down the ladder, never up: a complex card never takes a simple seat.
CASCADE = {"COMPLEX": "CONDITIONAL", "CONDITIONAL": "ATOMIC", "ATOMIC": None}


def _reject(field: str, reason: str) -> None:
    raise ContractError(f"{field}: {reason}")


def check_planning_ladder(proposal: dict) -> None:
    """Structural ladder rules on a V1 planning object. Shape only; no outcome is read."""
    cls = proposal.get("COMPLEXITY_CLASS")
    if cls not in COMPLEXITY_CLASSES:
        _reject("COMPLEXITY_CLASS", "one of " + ", ".join(COMPLEXITY_CLASSES))
    components = proposal.get("COMPONENTS")
    if not isinstance(components, list) or not all(isinstance(c, str) and c.strip() for c in components):
        _reject("COMPONENTS", "a list of component names")
    lo, hi = COMPONENT_COUNT[cls]
    if not lo <= len(components) <= hi or len(set(components)) != len(components):
        _reject("COMPONENTS", f"{cls} needs {lo}-{hi} distinct components")
    roles = proposal["VARIABLE_ROLES"]
    mechanism, nuisance = roles["MECHANISM_VARIABLES"], roles["NUISANCE_BASELINE_VARIABLES"]
    if cls in (ATOMIC, CONDITIONAL):
        if len(mechanism) != 1:
            _reject("COMPLEXITY_CLASS", f"{cls} has exactly one mechanism variable")
        wanted = "UNCONDITIONAL" if cls == ATOMIC else "CONDITIONAL"
        if proposal["TARGET_CLASS"] != wanted:
            _reject("COMPLEXITY_CLASS", f"{cls} requires TARGET_CLASS {wanted}")
    else:
        if proposal["CLAIM_TYPE"] != "INCREMENTAL":
            _reject("COMPLEXITY_CLASS", f"{cls} is a claim beyond its components: CLAIM_TYPE INCREMENTAL")
        # Main effects are controlled, not required to be supported (A ~ 0, B ~ 0, A x B != 0 is valid).
        missing = [c for c in components if c not in nuisance]
        if missing:
            _reject("COMPONENTS", "each component's main effect must be in NUISANCE_BASELINE_VARIABLES: " + ", ".join(missing))
        if not mechanism or set(mechanism) & set(components):
            _reject("COMPLEXITY_CLASS", f"{cls} mechanism variable is the joint term, not a component")


def complexity_shortlist(order: list[str], classes: dict[str, str]) -> list[dict]:
    """Shortlist of at most 5 from the deterministic ordinal order, by complexity quota.

    Seats: 2 ATOMIC, 2 CONDITIONAL, 1 COMPLEX (INTERACTION or COMPOSITE). Each seat takes
    the best-ordered unused survivor of its class. An unfilled seat passes down the ladder
    (COMPLEX -> CONDITIONAL -> ATOMIC), never up; a seat with no eligible survivor stays empty.
    """
    for cid in order:
        if classes.get(cid) not in COMPLEXITY_CLASSES:
            _reject("COMPLEXITY_CLASS", f"{cid} has no complexity class")
    used: set[str] = set()
    picks = []
    for seat, n in SHORTLIST_QUOTA:
        for _ in range(n):
            target = seat
            while target is not None:
                cid = next((c for c in order if c not in used and SEAT_OF[classes[c]] == target), None)
                if cid is not None:
                    used.add(cid)
                    picks.append({"CANDIDATE_ID": cid, "SEAT": seat, "COMPLEXITY_CLASS": classes[cid]})
                    break
                target = CASCADE[target]
    return picks
