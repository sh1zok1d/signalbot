"""MARKET-06 frozen-authority authentication and execution refuse-gate.

Does not evaluate MARKET outcomes. Does not parse OHLC for science.
Caller kwargs, env vars, and CLI flags cannot substitute scientific
authority or authorize canonical execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping


IMPLEMENTATION_ID = "MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION"
RESEARCH_ID = "MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK"

PREREG_FREEZE_HEAD = "e2d543eadb5425473b6d4b8d24c177c1d7ae7930"
PREREG_FREEZE_TREE = "a1706c775154fc65ad1d5eaaa5818f87b834a2b7"
PREREG_CONTENT_HEAD = "6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59"
PREREG_CONTENT_TREE = "11658516cab22774501daa8e2e966c9a8861c9a3"
PREREG_MD_SHA256 = "70dd8d09e07e1209e77ea6d1c741e412534ef5cccbfc36609bc46924e13cc4c6"
PREREG_JSON_SHA256 = "f60bf0bdbeb5982933c648b1c9b56017f25a5dabb29ad39eac58d53b5f590a24"
PREREG_MD_SIZE = 21434
PREREG_JSON_SIZE = 14159

PREREG_MD_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
PREREG_FREEZE_JSON_REL = (
    "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json"
)
DURABLE_MANIFEST_REL = (
    "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/"
    "DURABLE_RETENTION_MANIFEST.json"
)
IDENTITY_DIR_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0"

DATASET_ID = "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
DURABLE_EVIDENCE_ROOT_SHA256 = (
    "f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f"
)
BINANCE_OBJECT_COUNT = 36
OKX_PAGE_COUNT = 1053
IDENTITY_FILES = (
    "binance_object_ledger.json",
    "okx_page_manifest.json",
    "timestamp_census.json",
    "snapshot.json",
)

LIVE_AMENDMENT_ID = "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002"
HISTORICAL_AMENDMENT_001 = "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001"

CLASS_PROMOTED = "MARKET_06_PROMOTED_HISTORICAL_CANDIDATE"
CLASS_NO_EVIDENCE = "MARKET_06_NO_EVIDENCE"
CLASS_INCOMPLETE = "MARKET_06_INCOMPLETE_EXECUTION"
FORBIDDEN_PROMOTION_STATES = ("NEAR_PASS", "MIXED", "PROMISING", "PARTIAL_PASS")

ARM_RELATIVES = (
    "docs/research/MARKET_06_ARM.md",
    "docs/research/MARKET_06_ARM.json",
    "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_ARM.md",
    "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_ARM.json",
)
RESULT_RELATIVES = (
    "docs/research/MARKET_06_RESULT.md",
    "docs/research/MARKET_06_RESULT.json",
    "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.md",
    "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.json",
)

BYPASS_ENV_KEYS = (
    "MARKET_06_EXECUTE",
    "MARKET_06_AUTHORIZATION",
    "MARKET_06_FORCE",
    "SIGNALBOT_MARKET_06_EXECUTE",
)


class Market06AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market06IncompleteExecution(RuntimeError):
    classification = CLASS_INCOMPLETE

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"{CLASS_INCOMPLETE}:{reason}")


class Market06ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_06_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
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


def _git(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise Market06IncompleteExecution(
            f"GIT_OBJECT_MISSING:{' '.join(args)}:{proc.stderr.decode('utf-8', 'replace')[:200]}"
        )
    return proc.stdout


def git_rev_parse(ref: str) -> str:
    return _git("rev-parse", ref).decode("ascii").strip()


def git_cat_file(commit: str, relpath: str) -> bytes:
    return _git("cat-file", "-p", f"{commit}:{relpath}")


def _reject_caller_authority_override(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args:
        raise Market06ExecutionNotAuthorized(
            "positional arguments cannot redefine MARKET-06 authority"
        )
    forbidden = {
        "authorize",
        "authorized",
        "force",
        "execute",
        "allow_real",
        "bypass",
        "execution_authorized",
        "arm",
        "expected_sha256",
        "prereg_head",
        "snapshot_id",
    }
    hit = forbidden.intersection(kwargs)
    if hit:
        raise Market06ExecutionNotAuthorized(
            f"caller kwargs cannot redefine MARKET-06 authority:{sorted(hit)}"
        )


def _env_bypass_attempted() -> bool:
    return any(os.environ.get(key) for key in BYPASS_ENV_KEYS)


def execution_authorization_artifact_exists() -> bool:
    """Only a future Git-tracked authenticated ARM can authorize execution.

    No such artifact exists now. Env/kwargs/CLI cannot create one.
    """

    root = _repo_root()
    for rel in ARM_RELATIVES:
        if (root / rel).exists():
            return False
    return False


def require_execution_authorization(*args: Any, **kwargs: Any) -> None:
    _reject_caller_authority_override(args, kwargs)
    if _env_bypass_attempted():
        raise Market06ExecutionNotAuthorized(
            "environment variables cannot authorize MARKET-06 execution"
        )
    if execution_authorization_artifact_exists():
        raise Market06ExecutionNotAuthorized(
            "unauthenticated ARM artifact cannot authorize MARKET-06 execution"
        )
    raise Market06ExecutionNotAuthorized("MARKET_06_EXECUTION_NOT_AUTHORIZED")


def refuse_canonical_execution(*args: Any, **kwargs: Any) -> None:
    require_execution_authorization(*args, **kwargs)


def assert_no_arm_or_result() -> None:
    root = _repo_root()
    for rel in ARM_RELATIVES + RESULT_RELATIVES:
        if (root / rel).exists():
            raise Market06AuthorityError(f"MARKET_06_ARM_OR_RESULT_EXISTS:{rel}")


def verify_live_prereg_freeze_objects() -> dict[str, Any]:
    head = git_rev_parse(PREREG_FREEZE_HEAD)
    if head != PREREG_FREEZE_HEAD:
        raise Market06AuthorityError(f"PREREG_FREEZE_HEAD_MISSING:{head}")
    tree = git_rev_parse(f"{PREREG_FREEZE_HEAD}^{{tree}}")
    if tree != PREREG_FREEZE_TREE:
        raise Market06AuthorityError(f"PREREG_FREEZE_TREE_MISMATCH:{tree}")
    current = git_rev_parse("HEAD")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREREG_FREEZE_HEAD, "HEAD"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise Market06AuthorityError(
            f"HEAD_DOES_NOT_DESCEND_FROM_PREREG_FREEZE:{current}"
        )
    payload_tree = git_rev_parse(f"{PREREG_CONTENT_HEAD}^{{tree}}")
    if payload_tree != PREREG_CONTENT_TREE:
        raise Market06AuthorityError(f"PREREG_CONTENT_TREE_MISMATCH:{payload_tree}")
    return {
        "prereg_freeze_head": head,
        "prereg_freeze_tree": tree,
        "current_head": current,
        "prereg_content_head": PREREG_CONTENT_HEAD,
        "prereg_content_tree": payload_tree,
    }


def load_frozen_prereg_json() -> dict[str, Any]:
    data = git_cat_file(PREREG_CONTENT_HEAD, PREREG_JSON_REL)
    digest = sha256_bytes(data)
    if digest != PREREG_JSON_SHA256 or len(data) != PREREG_JSON_SIZE:
        raise Market06AuthorityError(
            f"PREREG_JSON_BYTE_IDENTITY_MISMATCH:{digest}:{len(data)}"
        )
    md = git_cat_file(PREREG_CONTENT_HEAD, PREREG_MD_REL)
    md_digest = sha256_bytes(md)
    if md_digest != PREREG_MD_SHA256 or len(md) != PREREG_MD_SIZE:
        raise Market06AuthorityError(
            f"PREREG_MD_BYTE_IDENTITY_MISMATCH:{md_digest}:{len(md)}"
        )
    payload = json.loads(data.decode("utf-8"))
    amendment = payload.get("amendment_of") or {}
    if amendment.get("amendment_id") != LIVE_AMENDMENT_ID:
        raise Market06AuthorityError("LIVE_AMENDMENT_002_MISSING")
    if amendment.get("previous_amendment_id") != HISTORICAL_AMENDMENT_001:
        raise Market06AuthorityError("AMENDMENT_001_HISTORY_MISSING")
    dislocation = payload["dislocation"]
    if dislocation.get("ROBUST_SCALE_T") != "1.4826 * MAD_T":
        raise Market06AuthorityError("F1_MISSING")
    if "ABS_BTC_RET_24H" not in payload["baseline_model"]:
        raise Market06AuthorityError("F2_MISSING")
    if payload["primary_outcome"].get("logarithmic_adverse_excursion") is not False:
        raise Market06AuthorityError("F3_MISSING")
    if payload.get("gate_2_exact_predicate") != "BETA_ABS_DISLOCATION_Z_CI95_LOW > 0":
        raise Market06AuthorityError("F4_MISSING")
    boot = payload["bootstrap"]
    if boot.get("PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR") is not True:
        raise Market06AuthorityError("AMENDMENT_002_STRATIFICATION_MISSING")
    if boot.get("CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED") is not False:
        raise Market06AuthorityError("AMENDMENT_002_CROSS_YEAR_MISSING")
    if payload["data"]["snapshot_id"] != SNAPSHOT_ID:
        raise Market06AuthorityError("SNAPSHOT_ID_MISMATCH")
    if payload["data"]["durable_evidence_root_sha256"] != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06AuthorityError("DURABLE_ROOT_MISMATCH")
    if payload["data"]["dataset_id"] != DATASET_ID:
        raise Market06AuthorityError("DATASET_ID_MISMATCH")
    return payload


def verify_prereg_authority(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_authority_override(args, kwargs)
    heads = verify_live_prereg_freeze_objects()
    payload = load_frozen_prereg_json()
    assert_no_arm_or_result()
    freeze = json.loads(
        git_cat_file(PREREG_FREEZE_HEAD, PREREG_FREEZE_JSON_REL).decode("utf-8")
    )
    bound = freeze["accepted_prereg_content"]
    if bound["head"] != PREREG_CONTENT_HEAD or bound["tree"] != PREREG_CONTENT_TREE:
        raise Market06AuthorityError("FREEZE_PAYLOAD_BINDING_MISMATCH")
    return {
        **heads,
        "prereg_md_sha256": PREREG_MD_SHA256,
        "prereg_json_sha256": PREREG_JSON_SHA256,
        "amendment_id": payload["amendment_of"]["amendment_id"],
        "snapshot_id": payload["data"]["snapshot_id"],
        "durable_evidence_root_sha256": payload["data"]["durable_evidence_root_sha256"],
        "scientific_outcomes_inspected": False,
    }


def _recompute_snapshot_id_from_bytes(files: Mapping[str, bytes]) -> str:
    hashes = {name: sha256_bytes(files[name]) for name in IDENTITY_FILES}
    preimage = (json.dumps(hashes, sort_keys=True) + "\n").encode("utf-8")
    return sha256_bytes(preimage)


def load_git_bound_durable_manifest() -> dict[str, Any]:
    data = git_cat_file(PREREG_FREEZE_HEAD, DURABLE_MANIFEST_REL)
    manifest = json.loads(data.decode("utf-8"))
    if manifest.get("snapshot_id") != SNAPSHOT_ID:
        raise Market06IncompleteExecution("MANIFEST_SNAPSHOT_ID")
    if manifest.get("dataset_id") != DATASET_ID:
        raise Market06IncompleteExecution("MANIFEST_DATASET_ID")
    if manifest.get("durable_evidence_root_sha256") != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06IncompleteExecution("MANIFEST_DURABLE_ROOT")
    if len(manifest.get("binance_objects") or []) != BINANCE_OBJECT_COUNT:
        raise Market06IncompleteExecution("MANIFEST_BINANCE_COUNT")
    if len(manifest.get("okx_objects") or []) != OKX_PAGE_COUNT:
        raise Market06IncompleteExecution("MANIFEST_OKX_COUNT")
    return manifest


def retained_payload_sha256s() -> frozenset[str]:
    manifest = load_git_bound_durable_manifest()
    hashes = {str(row["sha256"]) for row in manifest["binance_objects"]}
    hashes |= {str(row["sha256"]) for row in manifest["okx_objects"]}
    return frozenset(hashes)


def refuse_real_retained_bytes(data: bytes, *, where: str) -> None:
    digest = sha256_bytes(data)
    if digest in retained_payload_sha256s():
        raise Market06ExecutionNotAuthorized(
            f"real retained MARKET-06 bytes cannot be parsed for science:{where}:{digest}"
        )


def verify_git_bound_data_authority(*, hash_raw_objects: bool = True) -> dict[str, Any]:
    """Identity verification of Git-bound retained bytes. No OHLC science."""

    files = {
        name: git_cat_file(PREREG_FREEZE_HEAD, f"{IDENTITY_DIR_REL}/{name}")
        for name in IDENTITY_FILES
    }
    snapshot = _recompute_snapshot_id_from_bytes(files)
    if snapshot != SNAPSHOT_ID:
        raise Market06IncompleteExecution(f"SNAPSHOT_ID_MISMATCH:{snapshot}")
    hashes_doc = json.loads(
        git_cat_file(PREREG_FREEZE_HEAD, f"{IDENTITY_DIR_REL}/HASHES.json").decode("utf-8")
    )
    if hashes_doc.get("snapshot_id") != SNAPSHOT_ID:
        raise Market06IncompleteExecution("HASHES_SNAPSHOT_ID")
    manifest = load_git_bound_durable_manifest()
    if hash_raw_objects:
        for row in manifest["binance_objects"]:
            blob = git_cat_file(PREREG_FREEZE_HEAD, f"{IDENTITY_DIR_REL}/{row['durable_path']}")
            digest = sha256_bytes(blob)
            if digest != row["sha256"] or len(blob) != int(row["byte_length"]):
                raise Market06IncompleteExecution(f"BINANCE_OBJECT:{row['logical_id']}")
        for row in manifest["okx_objects"]:
            blob = git_cat_file(PREREG_FREEZE_HEAD, f"{IDENTITY_DIR_REL}/{row['durable_path']}")
            digest = sha256_bytes(blob)
            if digest != row["sha256"] or len(blob) != int(row["byte_length"]):
                raise Market06IncompleteExecution(f"OKX_OBJECT:{row['logical_id']}")
    return {
        "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT_ID,
        "durable_evidence_root_sha256": DURABLE_EVIDENCE_ROOT_SHA256,
        "binance_object_count": BINANCE_OBJECT_COUNT,
        "okx_page_count": OKX_PAGE_COUNT,
        "raw_objects_hashed": bool(hash_raw_objects),
        "scientific_parse": False,
    }
