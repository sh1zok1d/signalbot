"""FORWARD_MARKET_OBSERVABILITY_V1 collection-authorization lifecycle.

Repairs the same defect class found and fixed for MARKET-05: the frozen
collector could never itself transition into authoritative collection,
because ``cli.py``'s ``collect`` refused unconditionally and
``default_config()`` hardcoded ``authoritative_collection_authorized =
False`` as dead config, never read by anything.

This module makes the SAME frozen collector bytes transition from
UNAUTHORIZED to AUTHORIZED through an external, authenticated collection
ARM artifact, with no post-ARM source modification:

    UNAUTHORIZED
      -> add an authenticated FORWARD_MARKET_OBSERVABILITY_V1_COLLECTION_ARM
      -> the SAME frozen collector bytes become authorized
      -> "collect" starts a new authoritative session

This module computes/checks nothing scientific. It does not read market
payloads, does not classify observation validity, and does not decide
source readiness -- those remain in ``schemas.py``/``collector.py`` and the
``readiness`` CLI command.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PROGRAM_ID = "FORWARD_MARKET_OBSERVABILITY_V1"

# The frozen COLLECTOR SOURCE commit -- distinct from the later
# COLLECTION_AUTHORITY commit that adds only the ARM. This module cannot
# hardcode it as a constant: that would require this very file to contain
# a literal equal to the hash of the commit that contains this file,
# which is circular. It is read LIVE from the refreeze artifact via the
# authority root instead (see collector_source_provenance() below).

REFREEZE_JSON_REL = (
    "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_REFREEZE.json"
)
ARM_JSON_REL = "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTION_ARM.json"
ARM_MD_REL = "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTION_ARM.md"

COLLECTION_AUTHORITY_REL = (
    "scripts/research/forward_market_observability_v1/collection_authority.py"
)
AUTHORITY_ROOT_REL = (
    "scripts/research/forward_market_observability_v1/authority_root.py"
)

RAW_ENVELOPE_SCHEMA = "forward_market_observability_v1_raw_envelope/1.0.0"
CHUNK_SCHEMA = "forward_market_observability_v1_chunk/1.0.0"
MANIFEST_SCHEMA = "forward_market_observability_v1_manifest/1.0.0"
CONFIG_SCHEMA = "forward_market_observability_v1_config/1.1.0"

INSTRUMENT = "BTCUSDT"
MARKET_TYPE = "BINANCE_USD_M_FUTURES"
VENUE = "binance"
LEGAL_AVAILABLE_AT_RULE = "local_received_at_utc"

# Every collector source file EXCEPT this module and the authority root
# (self-reference is impossible: a file cannot contain a literal constant
# equal to its own hash). Those two are anchored by git blob identity in
# ``authority_root.py`` instead. Filled by the refreeze.
COLLECTOR_IMPLEMENTATION_HASHES: dict[str, str] = {
    "scripts/research/forward_market_observability_v1/__init__.py": "5fcf8fd96f28d54e7817ef75c236fb6a233c4cd2b5c64e0e0c6eff2928c513b5",
    "scripts/research/forward_market_observability_v1/__main__.py": "072107e51ab58b3d6d0c17495b55d8d791959ca451797fd64fbf946396ce9f37",
    "scripts/research/forward_market_observability_v1/cli.py": "b628902d8ba03bbcd952ecd3c0bb764eb697c1692f1b6848ba95ca9dba32eca8",
    "scripts/research/forward_market_observability_v1/clock.py": "a800a90c1037303c387ef261283c319c9013329a745947a805da626284522184",
    "scripts/research/forward_market_observability_v1/collector.py": "63fafc2e5e4f106b1ffeb846a57c54b60c459dfeb81de86cc6ab7a67319ed717",
    "scripts/research/forward_market_observability_v1/envelope.py": "47e9f38c5ad394bb54a5b4ce6954adf7aeebcb0c175623e0ac1ac9d22d02f59d",
    "scripts/research/forward_market_observability_v1/health.py": "ad20f4a2f750070f82d60dea48adf512b2605612e60c49645b4233c75bf15429",
    "scripts/research/forward_market_observability_v1/identity.py": "dd8f2677dc5319d0dd6530565981de37b0565db785ba8ab233042da4a6b009dc",
    "scripts/research/forward_market_observability_v1/parse.py": "b13896c23d97cc08e2acf3e7f9cc171c2b57487739067ff55be04485b0a77a41",
    "scripts/research/forward_market_observability_v1/schemas.py": "6898dc58456771dafff2ec67307f25a88b454e8ff459c9106dbd75dd114b9e07",
    "scripts/research/forward_market_observability_v1/session.py": "8e8d3fa469ab434ced7ad2ebbb5c735b793024e7daad2d5b0a13ffe859ff05da",
    "scripts/research/forward_market_observability_v1/sources.py": "2d2d8c965cc193206d4334ab18ececcc3e00a61ec070347eba5bdbea19d00723",
    "scripts/research/forward_market_observability_v1/storage.py": "e6bf6f60fb9b35db222699db42c35a3d18919efd1fee2bc2874010fb52bdb6f5",
    "scripts/research/forward_market_observability_v1/transport.py": "2d86bb46a089ca081f25dc01bc11cbaca8eb8d313a45468e0157bb11230f54f2",
}

FROZEN_SOURCES = (
    "BINANCE_UM_BTCUSDT_MARK_PRICE_WS",
    "BINANCE_UM_BTCUSDT_PREMIUM_INDEX_REST",
    "BINANCE_UM_BTCUSDT_OPEN_INTEREST_REST",
)

# Any of these appearing in the ARM means it is carrying scientific/outcome
# content, which a collection authorization must never grant.
ARM_FORBIDDEN_FIELDS = (
    "future_return",
    "mae",
    "beta",
    "prediction",
    "classification",
    "threshold_selected_from_data",
    "market_06",
    "m04_fwd",
)


class CollectionAuthorityError(RuntimeError):
    """Collection-ARM authority or identity failure."""


class CollectionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "COLLECTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path(rel: str) -> Path:
    return _repo_root() / rel


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Deterministic canonical serialization. No clock, no uuid."""
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_regular_file(rel: str) -> Path:
    path = _path(rel)
    if path.is_symlink():
        raise CollectionAuthorityError(f"FORWARD_OBS_SYMLINK_REFUSED:{rel}")
    if not path.is_file():
        raise CollectionNotAuthorized(f"FORWARD_OBS_FILE_MISSING:{rel}")
    return path


def _authority_root():
    from scripts.research.forward_market_observability_v1 import authority_root as root

    return root


def collector_source_provenance() -> dict[str, str]:
    """The frozen COLLECTOR SOURCE commit/tree, read live from the refreeze
    artifact via the authority root -- never a hardcoded constant here."""
    return _authority_root().load_frozen_provenance()


def verify_authority_root(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Delegate to the independent git-anchored root of trust."""
    if args or kwargs:
        raise CollectionNotAuthorized(
            "caller arguments cannot redefine FORWARD_MARKET_OBSERVABILITY_V1 authority"
        )
    return _authority_root().verify_authority_root()


def authenticate_frozen_collector_bytes(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Every collector file (except this module + the root) must match frozen bytes."""
    if args or kwargs:
        raise CollectionNotAuthorized(
            "caller arguments cannot redefine FORWARD_MARKET_OBSERVABILITY_V1 authority"
        )
    seen: dict[str, str] = {}
    for rel, expected in sorted(COLLECTOR_IMPLEMENTATION_HASHES.items()):
        digest = sha256_file(_require_regular_file(rel))
        if digest != expected:
            raise CollectionAuthorityError(
                f"FORWARD_OBS_IMPLEMENTATION_BYTE_MISMATCH:{rel}"
            )
        seen[rel] = digest
    return seen


def source_definitions() -> list[dict[str, Any]]:
    from scripts.research.forward_market_observability_v1.sources import DEFAULT_SOURCES

    return [dict(item) for item in DEFAULT_SOURCES]


def collection_run_identity_payload() -> dict[str, Any]:
    """Canonical, deterministic preimage. No clock, no uuid, no fs ordering.

    Deliberately excludes the collector source commit/tree SHAs: those are
    commit identities, not content, and are checked directly against the
    live-read refreeze provenance in authenticate_collection_arm() instead.
    RUN_IDENTITY is fully determined by file CONTENT hashes (this module's
    own hardcoded hash map plus the authority root's blob-id map), so it
    never depends on git history shape.
    """
    return {
        "schema": "forward_market_observability_v1_collection_run_identity",
        "schema_version": "1.0.0",
        "program_id": PROGRAM_ID,
        "collector_implementation_hashes": dict(
            sorted(COLLECTOR_IMPLEMENTATION_HASHES.items())
        ),
        "collection_authority_file": COLLECTION_AUTHORITY_REL,
        "authority_root_file": AUTHORITY_ROOT_REL,
        "authority_root_blob_ids": dict(sorted(_authority_root().FROZEN_BLOB_IDS.items())),
        "instrument": INSTRUMENT,
        "market_type": MARKET_TYPE,
        "venue": VENUE,
        "sources": source_definitions(),
        "raw_envelope_schema": RAW_ENVELOPE_SCHEMA,
        "chunk_schema": CHUNK_SCHEMA,
        "manifest_schema": MANIFEST_SCHEMA,
        "config_schema": CONFIG_SCHEMA,
        "legal_available_at_rule": LEGAL_AVAILABLE_AT_RULE,
        "scientific_outcomes_forbidden": True,
        "market_06_created": False,
        "m04_fwd_created": False,
    }


def derive_collection_run_identity(*args: Any, **kwargs: Any) -> str:
    if args or kwargs:
        raise CollectionNotAuthorized(
            "caller arguments cannot redefine FORWARD_MARKET_OBSERVABILITY_V1 authority"
        )
    return hashlib.sha256(
        canonical_json_bytes(collection_run_identity_payload())
    ).hexdigest()


def require_git_tracked_authority(rel: str) -> None:
    _require_regular_file(rel)
    proc = _authority_root().git_ls_files(rel)
    if proc.returncode != 0:
        raise CollectionAuthorityError(f"FORWARD_OBS_AUTHORITY_FILE_UNTRACKED:{rel}")


def _require_field(payload: Mapping[str, Any], key: str, expected: Any, code: str) -> None:
    if payload.get(key) != expected:
        raise CollectionNotAuthorized(f"{code}:{key}")


def authenticate_collection_arm(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Authenticate the collection ARM by bound content.

    Verification order matters: the independent root of trust runs FIRST,
    then frozen collector bytes, before any ARM field is trusted.
    """
    if args or kwargs:
        raise CollectionNotAuthorized(
            "caller arguments cannot redefine FORWARD_MARKET_OBSERVABILITY_V1 authority"
        )
    verify_authority_root()
    authenticate_frozen_collector_bytes()

    require_git_tracked_authority(ARM_JSON_REL)
    require_git_tracked_authority(ARM_MD_REL)
    path = _require_regular_file(ARM_JSON_REL)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectionAuthorityError("FORWARD_OBS_ARM_MALFORMED_JSON") from exc

    for field in ARM_FORBIDDEN_FIELDS:
        if field in payload:
            raise CollectionAuthorityError("FORWARD_OBS_ARM_CONTAINS_SCIENTIFIC_FIELD")

    _require_field(payload, "program_id", PROGRAM_ID, "FORWARD_OBS_ARM_PROGRAM_ID_MISMATCH")
    provenance = collector_source_provenance()
    _require_field(
        payload,
        "collector_source_head",
        provenance["head"],
        "FORWARD_OBS_ARM_SOURCE_HEAD_MISMATCH",
    )
    _require_field(
        payload,
        "collector_source_tree",
        provenance["tree"],
        "FORWARD_OBS_ARM_SOURCE_TREE_MISMATCH",
    )
    arm_hashes = payload.get("collector_implementation_sha_set")
    if arm_hashes != COLLECTOR_IMPLEMENTATION_HASHES:
        raise CollectionAuthorityError("FORWARD_OBS_ARM_IMPLEMENTATION_MISMATCH")
    _require_field(
        payload, "raw_envelope_schema", RAW_ENVELOPE_SCHEMA, "FORWARD_OBS_ARM_SCHEMA_MISMATCH"
    )
    _require_field(payload, "chunk_schema", CHUNK_SCHEMA, "FORWARD_OBS_ARM_SCHEMA_MISMATCH")
    _require_field(
        payload, "manifest_schema", MANIFEST_SCHEMA, "FORWARD_OBS_ARM_SCHEMA_MISMATCH"
    )
    _require_field(payload, "config_schema", CONFIG_SCHEMA, "FORWARD_OBS_ARM_SCHEMA_MISMATCH")
    _require_field(payload, "instrument", INSTRUMENT, "FORWARD_OBS_ARM_INSTRUMENT_MISMATCH")
    _require_field(
        payload, "market_type", MARKET_TYPE, "FORWARD_OBS_ARM_MARKET_TYPE_MISMATCH"
    )
    _require_field(payload, "venue", VENUE, "FORWARD_OBS_ARM_VENUE_MISMATCH")
    if payload.get("sources") != source_definitions():
        raise CollectionAuthorityError("FORWARD_OBS_ARM_SOURCE_DEFINITIONS_MISMATCH")
    _require_field(
        payload,
        "legal_available_at_rule",
        LEGAL_AVAILABLE_AT_RULE,
        "FORWARD_OBS_ARM_LEGAL_RULE_MISMATCH",
    )
    if payload.get("scientific_outcomes_forbidden") is not True:
        raise CollectionAuthorityError("FORWARD_OBS_ARM_MUST_FORBID_SCIENTIFIC_OUTCOMES")
    if payload.get("market_06_created") is not False:
        raise CollectionAuthorityError("FORWARD_OBS_ARM_MARKET_06_MUST_BE_FALSE")
    if payload.get("m04_fwd_created") is not False:
        raise CollectionAuthorityError("FORWARD_OBS_ARM_M04_FWD_MUST_BE_FALSE")

    derived = derive_collection_run_identity()
    if payload.get("collection_run_identity") != derived:
        raise CollectionNotAuthorized("FORWARD_OBS_ARM_RUN_IDENTITY_MISMATCH")
    if payload.get("authoritative_collection_authorized") is not True:
        raise CollectionNotAuthorized("FORWARD_OBS_ARM_NOT_AUTHORIZED")

    return {
        "payload": payload,
        "sha256": sha256_file(_path(ARM_JSON_REL)),
        "collection_run_identity": derived,
    }


def collection_is_authorized() -> bool:
    """Non-raising predicate. Fails closed on any error."""
    try:
        authenticate_collection_arm()
    except Exception:  # noqa: BLE001 — any failure means unauthorized
        return False
    return True


def inspect_collection_authorization_state() -> dict[str, Any]:
    try:
        out = authenticate_collection_arm()
        return {
            "AUTHORITATIVE_COLLECTION_AUTHORIZED": True,
            "collection_run_identity": out["collection_run_identity"],
            "arm_sha256": out["sha256"],
        }
    except Exception:  # noqa: BLE001
        return {
            "AUTHORITATIVE_COLLECTION_AUTHORIZED": False,
            "collection_run_identity": None,
            "arm_sha256": None,
        }
