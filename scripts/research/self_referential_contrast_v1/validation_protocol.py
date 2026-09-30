"""Predeclared validation screen. This module does not execute it.

Worlds are a finite list. A coordinate that sits between two anchors is
not an anchor and is not admitted by interpolation.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.research.self_referential_contrast_v1.constants import (
    AGGREGATE_REJECT_COUNT_MAX,
    D7_ADMISSION_OUTER_WORLD_N,
    GENERIC_OUTER_WORLD_N,
    HIGH_R_DIAGNOSTIC_N,
    HIGH_R_WORLDS_PER_REGION,
    REGION_COUNT,
    REGION_REJECT_COUNT_FAIL_AT,
    SCREEN_FAIL,
    SCREEN_FAILED_CLOSED,
    SCREEN_NOT_OFFICIAL,
    SCREEN_PASS,
    STATUS_BOOTSTRAP_DEGENERATE,
    STATUS_BOOTSTRAP_NUMERICAL,
    STATUS_IMPLEMENTATION_ERROR,
    SUITE_D7_ADMISSION,
    SUITE_GENERIC,
    SUITE_HIGH_R,
    WORLDS_PER_REGION,
)

DESIGN_T = (2048, 16384, 65536)
DESIGN_J = (1, 4)
DESIGN_GAP = ("none", "interior")

FAIL_CLOSED_STATUSES = frozenset(
    {
        STATUS_BOOTSTRAP_DEGENERATE,
        STATUS_BOOTSTRAP_NUMERICAL,
        STATUS_IMPLEMENTATION_ERROR,
    }
)


@dataclass(frozen=True)
class LawSpec:
    family: str
    param: str
    region_id: str

    @property
    def law_id(self) -> str:
        return f"{self.family}|{self.param}"


@dataclass(frozen=True)
class ConfigSpec:
    suite_id: str
    region_id: str
    law: LawSpec
    t_count: int | None
    block_count: int | None
    gap: str | None
    geometry_id: str

    @property
    def configuration_id(self) -> str:
        return f"{self.law.law_id}|{self.geometry_id}"


@dataclass(frozen=True)
class WorldSpec:
    suite_id: str
    configuration_id: str
    world_index: int
    region_id: str
    replicate: int
    t_count: int | None
    block_count: int | None
    gap: str | None
    family: str
    param: str
    geometry_id: str
    purpose: str


def generic_laws() -> tuple[LawSpec, ...]:
    laws: list[LawSpec] = [LawSpec("IID_BERNOULLI", "p=0.25", "R1_IID_BERNOULLI")]
    for rho, region in (
        ("0", "R2_INTERLACED_WEAK"),
        ("0.25", "R2_INTERLACED_WEAK"),
        ("0.50", "R2_INTERLACED_WEAK"),
        ("0.75", "R3_INTERLACED_STRONG"),
        ("0.90", "R3_INTERLACED_STRONG"),
    ):
        laws.append(LawSpec("INTERLACED_LAG2", f"rho={rho}", region))
    for name in ("q=1|theta=0.40", "q=2|theta=0.30,0.20", "q=4|theta=0.20,0.15,0.10,0.05"):
        laws.append(LawSpec("MA_EVEN", name, "R4_MA_EVEN"))
    for coef in ("0.02/0.7", "0.05/0.7", "0.10/0.7"):
        laws.append(LawSpec("CANCELLING_CELLS", f"c={coef}", "R5_CANCELLING_CELLS"))
    laws.append(LawSpec("VARIANCE_REGIMES", "p=0.10,0.50", "R6_VARIANCE_REGIMES"))
    laws.append(LawSpec("VARIANCE_REGIMES", "p=0.05,0.40", "R6_VARIANCE_REGIMES"))
    laws.append(LawSpec("LABEL_MARKOV", "stay=0.50", "R7_LABEL_MARKOV_MODERATE"))
    laws.append(LawSpec("LABEL_MARKOV", "stay=0.80", "R7_LABEL_MARKOV_MODERATE"))
    laws.append(LawSpec("LABEL_MARKOV", "stay=0.95", "R8_LABEL_MARKOV_PERSISTENT"))
    return tuple(laws)


def excluded_sensitivity_laws() -> tuple[LawSpec, ...]:
    return (
        LawSpec("INTERLACED_LAG2", "rho=0.98", "OUT_OF_VALIDATION"),
        LawSpec("LABEL_MARKOV", "stay=0.99", "OUT_OF_VALIDATION"),
    )


def region_ids() -> tuple[str, ...]:
    ordered: list[str] = []
    for law in generic_laws():
        if law.region_id not in ordered:
            ordered.append(law.region_id)
    return tuple(ordered)


def generic_configs() -> tuple[ConfigSpec, ...]:
    configs: list[ConfigSpec] = []
    for law in generic_laws():
        for t_count in DESIGN_T:
            for block_count in DESIGN_J:
                for gap in DESIGN_GAP:
                    geometry = f"T={t_count}|J={block_count}|gap={gap}"
                    configs.append(
                        ConfigSpec(
                            suite_id=SUITE_GENERIC,
                            region_id=law.region_id,
                            law=law,
                            t_count=t_count,
                            block_count=block_count,
                            gap=gap,
                            geometry_id=geometry,
                        )
                    )
    return tuple(configs)


def d7_configs() -> tuple[ConfigSpec, ...]:
    configs: list[ConfigSpec] = []
    for law in generic_laws():
        geometry = "ADAPTER_EXACT_GEOMETRY"
        configs.append(
            ConfigSpec(
                suite_id=SUITE_D7_ADMISSION,
                region_id="D7_EXACT_GEOMETRY",
                law=law,
                t_count=None,
                block_count=None,
                gap=None,
                geometry_id=geometry,
            )
        )
    return tuple(sorted(configs, key=lambda item: item.configuration_id))


def _allocate(configs: tuple[ConfigSpec, ...], n_worlds: int, purpose: str, region_id: str | None = None) -> tuple[WorldSpec, ...]:
    chosen = [item for item in configs if region_id is None or item.region_id == region_id]
    chosen.sort(key=lambda item: item.configuration_id)
    if not chosen:
        raise ValueError("allocation region has no configurations")
    base, remainder = divmod(n_worlds, len(chosen))
    specs: list[WorldSpec] = []
    for index, config in enumerate(chosen):
        count = base + (1 if index < remainder else 0)
        for replicate in range(count):
            specs.append(
                WorldSpec(
                    suite_id=config.suite_id,
                    configuration_id=config.configuration_id,
                    world_index=-1,
                    region_id=config.region_id,
                    replicate=replicate,
                    t_count=config.t_count,
                    block_count=config.block_count,
                    gap=config.gap,
                    family=config.law.family,
                    param=config.law.param,
                    geometry_id=config.geometry_id,
                    purpose=purpose,
                )
            )
    return tuple(specs)


def generic_world_specs() -> tuple[WorldSpec, ...]:
    specs: list[WorldSpec] = []
    configs = generic_configs()
    for region_index, region in enumerate(region_ids()):
        region_specs = _allocate(configs, WORLDS_PER_REGION, SUITE_GENERIC, region)
        start = region_index * WORLDS_PER_REGION
        for offset, spec in enumerate(region_specs):
            specs.append(_with_index(spec, start + offset))
    return tuple(specs)


def d7_world_specs() -> tuple[WorldSpec, ...]:
    allocated = _allocate(d7_configs(), D7_ADMISSION_OUTER_WORLD_N, SUITE_D7_ADMISSION)
    return tuple(_with_index(spec, index) for index, spec in enumerate(allocated))


def high_r_world_specs() -> tuple[WorldSpec, ...]:
    specs: list[WorldSpec] = []
    configs = generic_configs()
    for region_index, region in enumerate(region_ids()):
        region_specs = _allocate(configs, HIGH_R_WORLDS_PER_REGION, SUITE_HIGH_R, region)
        start = region_index * HIGH_R_WORLDS_PER_REGION
        for offset, spec in enumerate(region_specs):
            specs.append(_with_index(spec, start + offset))
    return tuple(specs)


def _with_index(spec: WorldSpec, world_index: int) -> WorldSpec:
    return WorldSpec(
        suite_id=spec.suite_id,
        configuration_id=spec.configuration_id,
        world_index=world_index,
        region_id=spec.region_id,
        replicate=spec.replicate,
        t_count=spec.t_count,
        block_count=spec.block_count,
        gap=spec.gap,
        family=spec.family,
        param=spec.param,
        geometry_id=spec.geometry_id,
        purpose=spec.purpose,
    )


class ProfileValidationDesign:
    """Finite anchor list. Not a filled rectangle."""

    def __init__(self, anchors: tuple[str, ...] | None = None) -> None:
        if anchors is None:
            anchors = tuple(spec.configuration_id for spec in generic_configs())
        self.anchors = tuple(anchors)

    @property
    def is_rectangle(self) -> bool:
        return False

    def admits_coordinate_interpolation(self, _anchor_id: str) -> bool:
        return False

    def contains(self, anchor_id: str) -> bool:
        return anchor_id in self.anchors


class ProfileValidatedDomain:
    """Passed anchors only. Empty until an official screen is recorded."""

    def __init__(self, passed_anchor_ids: frozenset[str] | None = None, *, executed: bool = False) -> None:
        self.passed_anchor_ids = frozenset() if passed_anchor_ids is None else frozenset(passed_anchor_ids)
        self.executed = executed

    def contains(self, anchor_id: str) -> bool:
        return anchor_id in self.passed_anchor_ids


@dataclass(frozen=True)
class HypothesisGeometryAdmission:
    hypothesis_id: str
    executed: bool = False
    status: str = "NOT_EXECUTED"


def official_generic_gate(reject_count: int, *, n_worlds: int, failed_closed: bool) -> str:
    if failed_closed:
        return SCREEN_FAILED_CLOSED
    if n_worlds != GENERIC_OUTER_WORLD_N:
        return SCREEN_NOT_OFFICIAL
    if reject_count <= AGGREGATE_REJECT_COUNT_MAX:
        return SCREEN_PASS
    return SCREEN_FAIL


def official_region_gate(reject_count: int, *, n_worlds: int) -> str:
    if n_worlds != WORLDS_PER_REGION:
        return SCREEN_NOT_OFFICIAL
    if reject_count >= REGION_REJECT_COUNT_FAIL_AT:
        return SCREEN_FAIL
    return SCREEN_PASS


def official_d7_gate(reject_count: int, *, n_worlds: int, failed_closed: bool) -> str:
    if failed_closed:
        return SCREEN_FAILED_CLOSED
    if n_worlds != D7_ADMISSION_OUTER_WORLD_N:
        return SCREEN_NOT_OFFICIAL
    if reject_count <= AGGREGATE_REJECT_COUNT_MAX:
        return SCREEN_PASS
    return SCREEN_FAIL


def screen_status(generic_gate: str, region_gates: tuple[str, ...], d7_gate: str | None = None) -> str:
    if len(region_gates) != REGION_COUNT:
        return SCREEN_NOT_OFFICIAL
    if generic_gate != SCREEN_PASS or any(item != SCREEN_PASS for item in region_gates):
        if SCREEN_FAILED_CLOSED in (generic_gate, *region_gates):
            return SCREEN_FAILED_CLOSED
        if generic_gate == SCREEN_NOT_OFFICIAL or SCREEN_NOT_OFFICIAL in region_gates:
            return SCREEN_NOT_OFFICIAL
        return SCREEN_FAIL
    if d7_gate is None:
        return SCREEN_PASS
    return d7_gate


def assert_allocation_invariants() -> None:
    generic = generic_world_specs()
    if len(generic) != GENERIC_OUTER_WORLD_N:
        raise AssertionError("generic world count drifted")
    if len(region_ids()) != REGION_COUNT:
        raise AssertionError("region count drifted")
    for region in region_ids():
        count = sum(1 for spec in generic if spec.region_id == region)
        if count != WORLDS_PER_REGION:
            raise AssertionError(f"{region} does not have {WORLDS_PER_REGION} worlds")
    if len(d7_world_specs()) != D7_ADMISSION_OUTER_WORLD_N:
        raise AssertionError("D7 world count drifted")
    if len(high_r_world_specs()) != HIGH_R_DIAGNOSTIC_N:
        raise AssertionError("high-R world count drifted")
    excluded = {law.law_id for law in excluded_sensitivity_laws()}
    gating = {spec.family + "|" + spec.param for spec in generic}
    if excluded & gating:
        raise AssertionError("non-gating sensitivity law entered the screen")
