"""Implementation-correctness tests. These are not profile validation."""

from __future__ import annotations

import inspect
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.self_referential_contrast_v1.bartlett import (
    bartlett_variance,
    contiguous_segments,
    direct_quadratic_form,
    variance_tolerance,
)
from scripts.research.self_referential_contrast_v1.constants import (
    AGGREGATE_REJECT_COUNT_MAX,
    ALPHA,
    D7_ADMISSION_OUTER_WORLD_N,
    GENERIC_OUTER_WORLD_N,
    HIGH_R_DIAGNOSTIC_N,
    PRIMARY_METHOD,
    R_CONFIRMATORY,
    R_VALIDATION,
    REGION_COUNT,
    REGION_REJECT_COUNT_FAIL_AT,
    STATUS_BOOTSTRAP_DEGENERATE,
    STATUS_BOOTSTRAP_NUMERICAL,
    STATUS_ESTIMAND_UNDEFINED,
    STATUS_IMPLEMENTATION_ERROR,
    STATUS_PRIMARY_COMPLETED,
    STATUS_VARIANCE_DEGENERATE,
    WORLDS_PER_REGION,
)
from scripts.research.self_referential_contrast_v1.contrast import (
    ContrastInput,
    analytic_partials,
    bandwidths,
    block_center,
    canonical_result_json,
    classify_bootstrap_variance,
    classify_observed_variance,
    counts_as_exceedance,
    finite_r_tail,
    gradient_influence,
    indexed_epsilon_sampler,
    primitive_moments,
    product_identity_influence,
    run_primary,
    sensitivity_rejects,
)
from scripts.research.self_referential_contrast_v1.multipliers import (
    bartlett_covariance,
    moving_average_multipliers,
    multiplier_design_matrix,
)
from scripts.research.self_referential_contrast_v1.runner import run_worlds, sort_results
from scripts.research.self_referential_contrast_v1.seeds import (
    confirmatory_hmac_digest,
    master_validation_seed,
    world_entropy,
)
from scripts.research.self_referential_contrast_v1.validation_protocol import (
    HypothesisGeometryAdmission,
    ProfileValidatedDomain,
    ProfileValidationDesign,
    d7_world_specs,
    excluded_sensitivity_laws,
    generic_world_specs,
    high_r_world_specs,
    official_d7_gate,
    official_generic_gate,
    official_region_gate,
    region_ids,
    screen_status,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "scripts/research/self_referential_contrast_v1"


def _input(x, y, cell, block, segment, declared, h=0):
    return ContrastInput(
        x=np.asarray(x, dtype=np.float64),
        y=np.asarray(y, dtype=np.float64),
        cell=np.asarray(cell),
        block=np.asarray(block),
        segment_id=np.asarray(segment),
        declared_cells=tuple(declared),
        h_mechanical=h,
    )


def _sampler(entropy: bytes):
    return indexed_epsilon_sampler(entropy)


def test_primitive_moments_and_functional():
    data = _input([1, 0, 1, 0], [1, 0, 0, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 0, 0], [0, 1])
    moments = primitive_moments(data)
    assert moments["status"] == "DEFINED"
    by_cell = {item.cell: item for item in moments["cells"]}
    assert by_cell[0].m0 == pytest.approx(0.5)
    assert by_cell[0].d == pytest.approx(0.125)
    assert by_cell[1].d == pytest.approx(-0.125)
    assert moments["theta_hat"] == pytest.approx(0.0)
    assert moments["M_hat"] == pytest.approx(0.5)


def test_empty_declared_cell_is_not_dropped():
    data = _input([1, 0, 1], [0, 1, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 1])
    moments = primitive_moments(data)
    assert moments["status"] == STATUS_ESTIMAND_UNDEFINED
    assert moments["empty_cells"] == (1,)
    result = run_primary(data, replicates=4, epsilon_sampler=_sampler(b"1" * 32), compute_sensitivity=False)
    assert result["inference_status"] == STATUS_ESTIMAND_UNDEFINED
    assert result["primary_reject"] is False
    assert result["method_switched"] is False
    assert result["p_value"] is None


def test_zero_candidate_mass_is_undefined():
    data = _input([0, 0, 0], [1, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0])
    assert primitive_moments(data)["status"] == STATUS_ESTIMAND_UNDEFINED


def test_analytic_gradient_matches_closed_form_partials():
    data = _input([1, 0, 1, 0, 1], [1, 1, 0, 0, 1], [0, 0, 1, 1, 0], [0, 0, 0, 1, 1], [0, 0, 0, 0, 0], [0, 1])
    moments = primitive_moments(data)
    partials = analytic_partials(moments)
    mass = moments["M_hat"]
    theta = moments["theta_hat"]
    for item in moments["cells"]:
        pi = item.m_x / item.m0
        mu = item.m_y / item.m0
        assert partials[item.cell]["m_xy"] == pytest.approx(1.0 / mass)
        assert partials[item.cell]["m_y"] == pytest.approx(-pi / mass)
        assert partials[item.cell]["m_x"] == pytest.approx(-(mu) / mass - theta / mass)
        assert partials[item.cell]["m0"] == pytest.approx((pi * mu) / mass)


def test_gradient_influence_matches_product_identity():
    data = _input(
        [1, 0, 1, 1, 0, 0],
        [1, 0, 0, 1, 1, 0],
        [0, 0, 1, 1, 0, 1],
        [0, 0, 0, 1, 1, 1],
        [0, 0, 0, 0, 0, 0],
        [0, 1],
    )
    left = gradient_influence(data)
    right = product_identity_influence(data)
    assert left == pytest.approx(right, abs=1e-12)
    assert left.mean() == pytest.approx(0.0, abs=1e-12)
    moments = primitive_moments(data)
    mass = moments["M_hat"]
    theta = moments["theta_hat"]
    if abs(theta) < 1e-12:
        pi = {item.cell: item.m_x / item.m0 for item in moments["cells"]}
        mu = {item.cell: item.m_y / item.m0 for item in moments["cells"]}
        product = np.array(
            [(data.x[i] - pi[data.cell[i]]) * (data.y[i] - mu[data.cell[i]]) / mass for i in range(len(data.x))]
        )
        assert left == pytest.approx(product, abs=1e-12)


def test_boundary_product_score_identity():
    data = _input([1, 0, 1, 0], [1, 0, 0, 1], [0, 0, 1, 1], ["y", "y", "y", "y"], [0, 0, 0, 0], [0, 1])
    moments = primitive_moments(data)
    assert moments["theta_hat"] == pytest.approx(0.0)
    phi = gradient_influence(data, moments)
    mass = moments["M_hat"]
    pi = {item.cell: item.m_x / item.m0 for item in moments["cells"]}
    mu = {item.cell: item.m_y / item.m0 for item in moments["cells"]}
    product = np.array([(data.x[i] - pi[data.cell[i]]) * (data.y[i] - mu[data.cell[i]]) / mass for i in range(4)])
    assert phi == pytest.approx(product, abs=1e-12)


def test_block_centering_does_not_change_theta():
    data = _input([1, 0, 1, 0, 1, 1], [1, 1, 0, 0, 1, 0], [0, 0, 1, 1, 0, 1], [0, 1, 0, 1, 0, 1], [0, 0, 0, 0, 0, 0], [0, 1])
    moments = primitive_moments(data)
    phi = gradient_influence(data, moments)
    centered = block_center(phi, data.block)
    assert centered.sum() == pytest.approx(0.0, abs=1e-12)
    assert primitive_moments(data)["theta_hat"] == moments["theta_hat"]
    # Cell labels are not centering keys: two block means, not one per cell.
    assert set(np.unique(data.block).tolist()) == {0, 1}


def test_bartlett_matches_dense_quadratic_form_across_a_gap():
    series = np.array([0.4, -0.2, 0.8, -0.1, 0.3, -0.7, 0.2], dtype=np.float64)
    segments = [(0, 3), (3, 7)]
    bandwidth = 3
    rolling, gamma0 = bartlett_variance(series, segments, bandwidth)
    dense = direct_quadratic_form(series, segments, bandwidth)
    assert rolling[0] * series.shape[0] == pytest.approx(dense, abs=variance_tolerance(series.shape[0], bandwidth, float(gamma0[0])))
    crossed = direct_quadratic_form(series, [(0, 7)], bandwidth)
    assert crossed != pytest.approx(dense)


def test_variance_failure_statuses_are_not_tail_events():
    tolerance_scale = variance_tolerance(10, 2, 1.0)
    assert classify_observed_variance(0.2, 1.0, 2, 10) == "POSITIVE"
    assert classify_observed_variance(0.0, 0.0, 2, 10) == STATUS_VARIANCE_DEGENERATE
    assert classify_observed_variance(-0.1 * tolerance_scale, 1.0, 2, 10) == STATUS_VARIANCE_DEGENERATE
    assert classify_observed_variance(-10.0 * tolerance_scale, 1.0, 2, 10) == STATUS_IMPLEMENTATION_ERROR
    assert classify_bootstrap_variance(0.0, 1.0, 2, 10) == STATUS_BOOTSTRAP_DEGENERATE
    assert classify_bootstrap_variance(-0.1 * tolerance_scale, 1.0, 2, 10) == STATUS_BOOTSTRAP_NUMERICAL
    assert classify_bootstrap_variance(-10.0 * tolerance_scale, 1.0, 2, 10) == STATUS_IMPLEMENTATION_ERROR
    zero = _input([1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0])
    result = run_primary(zero, replicates=5, epsilon_sampler=_sampler(b"2" * 32), compute_sensitivity=False)
    assert result["inference_status"] == STATUS_VARIANCE_DEGENERATE
    assert result["p_value"] is None
    assert result["primary_reject"] is False
    assert result["T_obs"] is None


def test_bandwidth_floor_binding_is_not_data_dependent():
    free = bandwidths(64, 1)
    assert free["B_T"] == free["L_T"] == math.ceil(64 ** (1 / 3))
    assert free["MECHANICAL_FLOOR_BINDS"] is False
    bound = bandwidths(64, 9)
    assert bound["B_T"] == bound["L_T"] == 9
    assert bound["MECHANICAL_FLOOR_BINDS"] is True
    assert bandwidths(8, 0)["B_T"] == 2


def test_multiplier_matches_bartlett_covariance_and_is_segment_local():
    length = 5
    bandwidth = 3
    design = multiplier_design_matrix(length, bandwidth)
    gram = (design @ design.T) / bandwidth
    assert gram == pytest.approx(bartlett_covariance(length, bandwidth), abs=1e-12)
    epsilon = np.array([0.2, -0.4, 0.6, 0.1, -0.3, 0.8, 0.0], dtype=np.float64)
    eta = moving_average_multipliers(epsilon, bandwidth)
    assert eta == pytest.approx(design @ epsilon / math.sqrt(bandwidth))
    other = epsilon.copy()
    other[-1] = 5.0
    # The last shock is inside this one segment; a second segment's shocks are a separate buffer.
    separate = np.array([9.0, 8.0, 7.0, 6.0], dtype=np.float64)
    eta_separate = moving_average_multipliers(separate, bandwidth)
    assert eta_separate.shape == (2,)
    assert not np.allclose(eta_separate, eta[:2])


def test_bootstrap_studentizer_is_recomputed_without_second_block_centering():
    data = _input(
        [1, 0, 1, 0, 1, 0, 1, 0],
        [1, 1, 0, 0, 1, 0, 0, 1],
        [0, 0, 0, 0, 1, 1, 1, 1],
        [0, 0, 1, 1, 0, 0, 1, 1],
        [0, 0, 0, 1, 1, 1, 1, 1],
        [0, 1],
        h=1,
    )
    entropy = world_entropy(
        suite_id="IMPLEMENTATION_TEST",
        configuration_id="studentizer",
        world_index=3,
        purpose="IMPLEMENTATION_TEST",
    )
    result = run_primary(data, replicates=6, epsilon_sampler=_sampler(entropy), compute_sensitivity=True)
    assert result["inference_status"] == STATUS_PRIMARY_COMPLETED
    assert result["primary_method"] == PRIMARY_METHOD
    assert result["R"] == 6
    assert result["L_T"] == result["B_T"]
    again = run_primary(data, replicates=6, epsilon_sampler=_sampler(entropy), compute_sensitivity=True)
    assert canonical_result_json(result) == canonical_result_json(again)


def test_finite_r_pvalue_ties_and_lattice():
    assert counts_as_exceedance(1.0, 1.0) is True
    assert counts_as_exceedance(0.999, 1.0) is False
    validation_edge = finite_r_tail(49, R_VALIDATION)
    assert validation_edge["reject"] is True
    assert validation_edge["p_value"] == pytest.approx(0.05)
    assert finite_r_tail(50, R_VALIDATION)["reject"] is False
    confirmatory_edge = finite_r_tail(499, R_CONFIRMATORY)
    assert confirmatory_edge["reject"] is True
    assert finite_r_tail(500, R_CONFIRMATORY)["reject"] is False
    assert confirmatory_edge["R"] == 9999
    assert validation_edge["monte_carlo_se"] > 0.0


def test_sensitivity_disagreement_does_not_switch_primary():
    assert sensitivity_rejects(2.0, True) is True
    assert sensitivity_rejects(1.0, True) is False
    assert sensitivity_rejects(3.0, False) is False
    data = _input([1, 1, 0, 1, 0, 0, 1, 0], [1, 0, 0, 1, 1, 0, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 1, 1, 0, 0, 1, 1], [0, 0, 0, 0, 0, 0, 0, 0], [0])
    entropy = world_entropy(suite_id="IMPLEMENTATION_TEST", configuration_id="sensitivity", world_index=1, purpose="IMPLEMENTATION_TEST")
    result = run_primary(data, replicates=30, epsilon_sampler=_sampler(entropy), compute_sensitivity=True)
    assert result["primary_method"] == PRIMARY_METHOD
    assert result["sensitivity_role"] == "SENSITIVITY_ONLY"
    assert result["INFERENCE_SENSITIVE"] == (result["primary_reject"] != result["sensitivity_reject"])
    assert result["method_switched"] is False


def test_seed_domain_separation_and_world_713_stability():
    first = world_entropy(suite_id="GENERIC_STRESS_SCREEN", configuration_id="cfg", world_index=713, purpose="GENERIC_STRESS_SCREEN")
    second = world_entropy(suite_id="GENERIC_STRESS_SCREEN", configuration_id="cfg", world_index=713, purpose="GENERIC_STRESS_SCREEN")
    other = world_entropy(suite_id="GENERIC_STRESS_SCREEN", configuration_id="cfg", world_index=713, purpose="DEVELOPMENT_BENCHMARK")
    assert first == second
    assert first != other
    assert "worker" not in inspect.signature(world_entropy).parameters
    beacon_a = confirmatory_hmac_digest(tree="abc", adapter_digest="def", beacon_time="1", beacon_value="ff")
    beacon_b = confirmatory_hmac_digest(
        tree="abc",
        adapter_digest="def",
        beacon_time="1",
        beacon_value="ff",
        purpose="D7_EXACT_GEOMETRY_ADMISSION",
    )
    assert beacon_a != beacon_b
    assert master_validation_seed() == master_validation_seed()


def test_allocation_is_finite_and_not_a_rectangle():
    worlds = generic_world_specs()
    assert len(worlds) == GENERIC_OUTER_WORLD_N
    assert len(region_ids()) == REGION_COUNT
    for region in region_ids():
        assert sum(item.region_id == region for item in worlds) == WORLDS_PER_REGION
    assert len(d7_world_specs()) == D7_ADMISSION_OUTER_WORLD_N
    assert len(high_r_world_specs()) == HIGH_R_DIAGNOSTIC_N
    excluded = {law.law_id for law in excluded_sensitivity_laws()}
    assert not any(f"{item.family}|{item.param}" in excluded for item in worlds)
    design = ProfileValidationDesign()
    assert design.is_rectangle is False
    assert design.admits_coordinate_interpolation("T=4096|J=2|gap=none") is False
    domain = ProfileValidatedDomain(frozenset({design.anchors[0], design.anchors[-1]}))
    assert domain.executed is False
    assert domain.contains("T=4096") is False
    admission = HypothesisGeometryAdmission(hypothesis_id="example")
    assert admission.executed is False
    assert admission.status == "NOT_EXECUTED"
    assert official_generic_gate(AGGREGATE_REJECT_COUNT_MAX, n_worlds=1600, failed_closed=False) == "SCREEN_PASS"
    assert official_generic_gate(AGGREGATE_REJECT_COUNT_MAX + 1, n_worlds=1600, failed_closed=False) == "SCREEN_FAIL"
    assert official_generic_gate(0, n_worlds=1599, failed_closed=False) == "NOT_AN_OFFICIAL_SCREEN"
    assert official_region_gate(REGION_REJECT_COUNT_FAIL_AT - 1, n_worlds=WORLDS_PER_REGION) == "SCREEN_PASS"
    assert official_region_gate(REGION_REJECT_COUNT_FAIL_AT, n_worlds=WORLDS_PER_REGION) == "SCREEN_FAIL"
    assert official_d7_gate(95, n_worlds=1600, failed_closed=False) == "SCREEN_PASS"
    gates = tuple(["SCREEN_PASS"] * REGION_COUNT)
    assert screen_status("SCREEN_PASS", gates) == "SCREEN_PASS"
    assert screen_status("SCREEN_PASS", gates[:-1] + ("SCREEN_FAIL",)) == "SCREEN_FAIL"


def test_worker_count_and_chunk_size_do_not_change_results():
    from scripts.research.self_referential_contrast_v1.validation_protocol import WorldSpec

    specs = []
    for index, spec in enumerate(generic_world_specs()):
        if spec.family == "IID_BERNOULLI" and spec.gap == "none" and spec.block_count == 1:
            specs.append(
                WorldSpec(
                    suite_id="IMPLEMENTATION_TEST",
                    configuration_id=f"tiny-{index}",
                    world_index=index,
                    region_id=spec.region_id,
                    replicate=0,
                    t_count=36,
                    block_count=1,
                    gap="none",
                    family="IID_BERNOULLI",
                    param="p=0.25",
                    geometry_id="tiny",
                    purpose="IMPLEMENTATION_TEST",
                )
            )
        if len(specs) == 4:
            break
    specs[0] = WorldSpec(**{**specs[0].__dict__, "world_index": 713})
    one = run_worlds(specs, workers=1, chunk_size=1, replicates=5, purpose="IMPLEMENTATION_TEST")
    chunked = run_worlds(specs, workers=1, chunk_size=3, replicates=5, purpose="IMPLEMENTATION_TEST")
    parallel = run_worlds(specs, workers=2, chunk_size=2, replicates=5, purpose="IMPLEMENTATION_TEST")
    assert [item.seed_digest for item in one] == [item.seed_digest for item in chunked]
    assert [item.seed_digest for item in one] == [item.seed_digest for item in parallel]
    assert [item.p_value for item in one] == [item.p_value for item in parallel]
    assert [item.reject for item in one] == [item.reject for item in parallel]
    shuffled = sort_results(list(reversed(one)))
    assert [item.world_index for item in shuffled] == [item.world_index for item in one]
    assert list(shuffled) == sorted(one, key=lambda item: (item.suite_id, item.configuration_id, item.world_index))


def test_generic_builder_respects_eligible_length_and_gap():
    from dataclasses import replace

    from scripts.research.self_referential_contrast_v1.dgp import build_generic_world

    spec = next(
        item
        for item in generic_world_specs()
        if item.family == "CANCELLING_CELLS" and item.gap == "interior" and item.t_count == 2048
    )
    data = build_generic_world(
        replace(spec, suite_id="IMPLEMENTATION_TEST", world_index=7),
        purpose="IMPLEMENTATION_TEST",
    )
    assert data.x.shape == data.y.shape == (2048,)
    assert len(set(data.segment_id.tolist())) == 2
    assert set(data.declared_cells) == {"c0", "c1"}
    again = build_generic_world(
        replace(spec, suite_id="IMPLEMENTATION_TEST", world_index=7),
        purpose="IMPLEMENTATION_TEST",
    )
    assert np.array_equal(data.x, again.x)


def test_generic_inference_sources_omit_adapter_constants():
    forbidden = ("30354", "721", "BitMEX", "bitmex", "XBTUSD", "year × RV")
    for path in PACKAGE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name} contains {token}"


def test_amendment_constants_match_the_document():
    document = json.loads(
        (ROOT / "docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_VALIDATION_PROTOCOL_AMENDMENT_V1.json").read_text(
            encoding="utf-8"
        )
    )
    assert document["VALIDATION_PROTOCOL_AMENDED"] is True
    assert document["official_validation_previously_executed"] is False
    assert document["GENERIC_OUTER_WORLD_N"] == GENERIC_OUTER_WORLD_N
    assert document["D7_ADMISSION_OUTER_WORLD_N"] == D7_ADMISSION_OUTER_WORLD_N
    assert document["R_VALIDATION"] == R_VALIDATION
    assert document["R_CONFIRMATORY"] == R_CONFIRMATORY
    assert document["AGGREGATE_REJECT_COUNT_MAX"] == AGGREGATE_REJECT_COUNT_MAX
    assert document["REGION_REJECT_COUNT_FAIL_AT"] == REGION_REJECT_COUNT_FAIL_AT
    assert document["PRIMARY_METHOD"] == PRIMARY_METHOD
    assert document["ALPHA"] == ALPHA
    assert contiguous_segments(np.array([0, 0, 1, 1])) == [(0, 2), (2, 4)]
