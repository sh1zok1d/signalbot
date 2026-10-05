"""Build the immutable execution binding V2 (audit-trail repair, owner 2026-10-04).

V1 stays byte-identical to its committed state in e5dd620. V2 supersedes it and
records the current generator-module digests. Neither binding authorizes a run:
that needs the separate RUN_AUTHORIZATION artifact, which does not exist.
"""

from __future__ import annotations

import hashlib
import json

from . import freeze


def build() -> dict:
    record = freeze.verify_freeze()
    amendment = freeze.verify_amendment()
    effective = json.loads(freeze.EFFECTIVE_MANIFEST.read_text())
    v1_rel = str(freeze.EXECUTION_BINDING_V1.relative_to(freeze.REPO))
    binding = {
        "BINDING": "COMPILER_V3_VARIANCE_FLOOR_EXECUTION_BINDING_V2", "CREATED": "2026-10-04",
        "SUPERSEDES": {"PATH": v1_rel, "SHA256": freeze.sha256_path(v1_rel), "COMMITTED_IN": "e5dd620",
                       "NOTE": "V1 is immutable as committed; its generator digests predate the freeze amendment"},
        "ORIGINAL_FREEZE": {"COMMIT": freeze.ORIGINAL_FREEZE_COMMIT, "ARTIFACTS": record["ARTIFACTS"]},
        "AMENDMENT": {"PATH": str(freeze.AMENDMENT.relative_to(freeze.REPO)),
                      "SHA256": freeze.sha256_path(str(freeze.AMENDMENT.relative_to(freeze.REPO)))},
        "EFFECTIVE_MANIFEST_SHA256": amendment["EFFECTIVE_MANIFEST_SHA256"],
        "ACTIVE_COUNTS": effective["ACTIVE_COUNTS"],
        "GENERATOR_DIGESTS": freeze.generator_digests(),
        "GENERATOR_DIGESTS_NOTE": "authoritative for the official run; the amendment's GENERATOR_DIGESTS field lists the pre-repair modules and is superseded by this record",
        "OFFICIAL_RUN_AUTHORIZED": False,
        "RUN_AUTHORIZATION_RULE": "a run is authorized only by the separate immutable artifact docs/research/COMPILER_V3_VARIANCE_FLOOR_RUN_AUTHORIZATION_V1.json carrying this binding's sha256, the commit, a run identity and the exact execution identity; editing a binding never authorizes anything",
    }
    freeze.EXECUTION_BINDING.write_text(json.dumps(binding, indent=2) + "\n")
    return binding


if __name__ == "__main__":
    b = build()
    print(json.dumps({"V1": b["SUPERSEDES"]["SHA256"], "V2": hashlib.sha256(freeze.EXECUTION_BINDING.read_bytes()).hexdigest(),
                      "GENERATOR_DIGESTS": b["GENERATOR_DIGESTS"]}, indent=1))
