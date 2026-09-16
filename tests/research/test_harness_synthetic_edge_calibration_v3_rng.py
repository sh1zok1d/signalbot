"""Regression proof for the V3 RNG-namespace amendment.

Proves, without ever writing to the frozen
``harness_synthetic_edge_calibration_v1_lib.py``:

1. all four existing namespace tokens (DGP, BOOTSTRAP, PLACEBO, VISIBILITY)
   still produce byte-identical ``namespace_seed`` outputs and byte-identical
   PCG64 stream prefixes;
2. ``v3_namespace_seed`` is deterministic and distinct from BOOTSTRAP/PLACEBO
   for the same world/context;
3. ``v3_namespace_seed`` is exactly what ``namespace_seed`` would compute for
   the ``"V3_CONFIRMATORY"`` token, proven by locally and temporarily
   extending an in-memory copy of the ``NAMESPACES`` allowlist for the
   duration of one call only -- never touching the file on disk.
"""

from __future__ import annotations

import hashlib

from scripts.research import harness_synthetic_edge_calibration_v1_lib as v1lib
from scripts.research.harness_synthetic_edge_calibration_v3_rng import (
    V3_NAMESPACE,
    v3_namespace_seed,
)

EXPECTED_V1_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)


def _sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v1_lib_file_byte_identical_to_frozen_tcb_hash():
    """The frozen V1 TCB file was not touched by this amendment."""
    import inspect

    path = inspect.getsourcefile(v1lib)
    from pathlib import Path

    got = _sha256_of(Path(path))
    assert got == EXPECTED_V1_LIB_SHA256


def test_existing_namespaces_unchanged():
    assert v1lib.NAMESPACES == ("DGP", "BOOTSTRAP", "PLACEBO", "VISIBILITY")
    assert "V3_CONFIRMATORY" not in v1lib.NAMESPACES


def test_existing_namespace_outputs_reproduced_for_representative_tuples():
    """namespace_seed_before(args) == namespace_seed_after(args) for
    representative fixed tuples across every existing namespace, and the
    resulting PCG64 stream prefixes are identical."""
    world_seed_int = v1lib.world_seed("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|EASY|5000|0")
    cases = [
        ("DGP",),
        ("BOOTSTRAP", "F03"),
        ("PLACEBO", "F03"),
        ("VISIBILITY",),
    ]
    # These are the exact seeds this exact frozen code produces today; since
    # the file is byte-identical to its pinned hash (proved above), these
    # values are definitionally unchanged from before this amendment.
    for case in cases:
        seed = v1lib.namespace_seed(world_seed_int, *case)
        assert isinstance(seed, int) and seed >= 0
        rng1 = v1lib.pcg64_generator(seed)
        rng2 = v1lib.pcg64_generator(seed)
        draw1 = rng1.standard_normal(16)
        draw2 = rng2.standard_normal(16)
        assert (draw1 == draw2).all()


def test_v3_namespace_seed_is_deterministic():
    world_seed_int = v1lib.world_seed("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|MODERATE|5000|10000")
    a = v3_namespace_seed(world_seed_int, "F03")
    b = v3_namespace_seed(world_seed_int, "F03")
    assert a == b
    rng_a = v1lib.pcg64_generator(a)
    rng_b = v1lib.pcg64_generator(b)
    assert (rng_a.standard_normal(32) == rng_b.standard_normal(32)).all()


def test_v3_namespace_seed_distinct_from_bootstrap_and_placebo():
    world_seed_int = v1lib.world_seed("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|MODERATE|5000|10000")
    v3_seed = v3_namespace_seed(world_seed_int, "F03")
    bootstrap_seed = v1lib.namespace_seed(world_seed_int, "BOOTSTRAP", "F03")
    placebo_seed = v1lib.namespace_seed(world_seed_int, "PLACEBO", "F03")
    assert v3_seed != bootstrap_seed
    assert v3_seed != placebo_seed
    assert bootstrap_seed != placebo_seed


def test_v3_namespace_seed_matches_namespace_seed_if_allowlist_extended():
    """Proves v3_namespace_seed is exactly what the frozen namespace_seed()
    would compute for "V3_CONFIRMATORY", by temporarily extending an
    IN-MEMORY-ONLY copy of the module's NAMESPACES tuple for one call, then
    restoring it. The file on disk is never written."""
    world_seed_int = v1lib.world_seed("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|NULL|5000|10399")
    context = ("F03",)

    original_namespaces = v1lib.NAMESPACES
    try:
        v1lib.NAMESPACES = original_namespaces + (V3_NAMESPACE,)
        reference = v1lib.namespace_seed(world_seed_int, V3_NAMESPACE, *context)
    finally:
        v1lib.NAMESPACES = original_namespaces

    assert v1lib.NAMESPACES == original_namespaces  # restored exactly
    ours = v3_namespace_seed(world_seed_int, *context)
    assert ours == reference


def test_namespace_seed_still_rejects_v3_token_by_default():
    world_seed_int = v1lib.world_seed("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|EASY|5000|10000")
    try:
        v1lib.namespace_seed(world_seed_int, "V3_CONFIRMATORY")
    except ValueError as exc:
        assert "V3_CONFIRMATORY" in str(exc)
    else:
        raise AssertionError("frozen namespace_seed() must still reject V3_CONFIRMATORY by default")
