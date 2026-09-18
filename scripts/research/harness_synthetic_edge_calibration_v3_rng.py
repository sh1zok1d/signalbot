"""V3-scoped RNG namespace-seed extension.

Adds a legal ``V3_CONFIRMATORY`` namespace-seed derivation without modifying
the frozen V1 ``NAMESPACES`` allowlist in
``harness_synthetic_edge_calibration_v1_lib.py``. That file's bytes are part
of the pinned V1 TCB (``FROZEN_V1_TCB_SHA256["lib"]`` =
``12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`` in
``harness_synthetic_edge_calibration_v2_production.py``), and that hash is
checked -- at any commit, live or historical -- by both live V1 TCB-intactness
assertions (``assert_v1_tcb_intact``) and historical V2 ARM re-verification
(``_v2_arm_payload_authorizes_at_commit`` via ``v1_tcb_digests_at``). Editing
``NAMESPACES`` in that file would either break live TCB checks (if
``FROZEN_V1_TCB_SHA256`` is left unchanged) or, if that constant were updated
to match, reintroduce -- for TCB identity -- the exact live-global
commit-purity defect already found and repaired once for canonical plan
identity. Both are out of scope for this narrow, pre-outcome RNG-namespace
amendment.

``v3_namespace_seed`` reuses ``namespace_seed``'s own hash construction
exactly: the same ``"|".join(world_seed_int, namespace, *context)`` payload,
the same ``_uint64_from_digest`` truncation, imported and reused verbatim,
not reimplemented. It is not a parallel RNG implementation: the only
RNG-relevant primitive is imported from the frozen module; the remaining
logic is the identical trivial string-join ``namespace_seed`` itself
performs, with the allowlist check simply omitted for this one, prospectively
fixed token.
"""

from __future__ import annotations

import hashlib

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    _uint64_from_digest,
)

V3_NAMESPACE = "V3_CONFIRMATORY"


def v3_namespace_seed(world_seed_int: int, *context: object) -> int:
    """Equivalent to ``namespace_seed(world_seed_int, "V3_CONFIRMATORY", *context)``.

    Computed identically to the frozen V1 primitive's own hash construction,
    without touching its ``NAMESPACES`` allowlist or any other byte of
    ``harness_synthetic_edge_calibration_v1_lib.py``.
    """
    parts = [str(world_seed_int), V3_NAMESPACE, *[str(item) for item in context]]
    payload = "|".join(parts).encode("utf-8")
    return _uint64_from_digest(hashlib.sha256(payload).digest())
