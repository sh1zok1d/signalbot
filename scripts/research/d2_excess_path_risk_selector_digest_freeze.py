"""Pre-outcome freeze of the D2 excess path-risk canonical selector digest.

Reconstructs the frozen RULE_1 / RV_ABSTENTION identity from legal CORE BTC
2020-2024 and writes the tracked selector-identity authority. Does not
compute ADVERSE_SHARE, PATH_SCALE, or any decomposition outcome. Does not
create an execution permit or RESULT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research import d2_excess_path_risk_evaluator as EV
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    JSON_REL as DESIGN_JSON_REL,
    file_sha256,
)
from scripts.research.discovery_sprint_01 import common as C

UNIT = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE"
EXPECTED_REVIEW_RUN_IDENTITY = (
    "bfe92af94df23d7aa6f3adc016dc6f558607d772977a1cc6613394ac9a92625f"
)
EXPECTED_IMPLEMENTATION_COMMIT = "019561384a2b9660a180ff4620c3a9b7f0393727"
EXPECTED_IMPLEMENTATION_TREE = "9b601ab6fcf328220bd1c4c1989239646a0fab1a"
FORBIDDEN_CALLS = (
    "evaluate_decomposition",
    "canonical_orchestration",
    "execute_decomposition",
    "build_target_rows",
    "target_row_from_discovery_row",
)


class SelectorIdentityFreezeInvalid(RuntimeError):
    """Reconstructed selector identity does not match frozen D2 census."""


def _hex64(value: Any) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise SelectorIdentityFreezeInvalid("CANONICAL_SELECTOR_DIGEST_NOT_HEX64")
    return digest


def _assert_no_protected_opens(files: list[str]) -> None:
    for rel in files:
        if C.path_is_protected_partition(Path(rel)):
            raise C.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
        lowered = rel.lower()
        if "/2025-" in lowered or "/2026-" in lowered:
            raise C.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
        if rel.endswith("2025.parquet") or rel.endswith("2026.parquet"):
            raise C.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")


def freeze_selector_identity(*, repo: Path | None = None) -> dict[str, Any]:
    """Reconstruct identity and write the tracked authority. No outcomes."""

    base = repo if isinstance(repo, Path) else C.repo_root()
    blockers = EV.verify_design_authorities(base)
    if blockers:
        raise SelectorIdentityFreezeInvalid(f"DESIGN_AUTHORITY:{','.join(blockers)}")
    facts = EV.verify_frozen_selector_identity_facts(base)

    review_path = base / EV.REVIEW_JSON_REL
    if not review_path.is_file():
        raise SelectorIdentityFreezeInvalid("REVIEW_ARTIFACT_MISSING")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    run_identity = str(review.get("RUN_IDENTITY") or "")
    if run_identity != EXPECTED_REVIEW_RUN_IDENTITY:
        raise SelectorIdentityFreezeInvalid(
            f"RUN_IDENTITY:{run_identity}!={EXPECTED_REVIEW_RUN_IDENTITY}"
        )
    if str(review.get("FINAL_IMPLEMENTATION_COMMIT") or "") != EXPECTED_IMPLEMENTATION_COMMIT:
        raise SelectorIdentityFreezeInvalid("FINAL_IMPLEMENTATION_COMMIT")
    if str(review.get("FINAL_IMPLEMENTATION_TREE") or "") != EXPECTED_IMPLEMENTATION_TREE:
        raise SelectorIdentityFreezeInvalid("FINAL_IMPLEMENTATION_TREE")

    log = C.OpenedFileLog()
    perp = C.load_core_btc_5m(log, repo=base)
    _assert_no_protected_opens(log.files)
    rows = C.build_rows(perp, C.RULE1_INTERVAL_START, C.DISCOVERY_END)
    EV.verify_constructed_rule1_interval(rows)
    mask = EV.SCIENTIFIC_RV_MASK(rows)
    try:
        census = EV.verify_selector_identity(rows, mask)
    except EV.SelectorIdentityError as exc:
        raise SelectorIdentityFreezeInvalid(
            f"D2_SELECTOR_IDENTITY_FREEZE_INVALID:{exc}"
        ) from exc

    constructed_n = int(census["RULE_1_CONSTRUCTED_ROW_COUNT"])
    abstain_n = int(census["SELECTOR_ABSTAIN_COUNT"])
    constructed_years = dict(census["RULE_1_CONSTRUCTED_YEAR_BREAKDOWN"])
    abstain_years = dict(census["SELECTOR_ABSTAIN_YEAR_BREAKDOWN"])
    if constructed_n != 1791 or abstain_n != 163:
        raise SelectorIdentityFreezeInvalid(
            f"D2_SELECTOR_IDENTITY_FREEZE_INVALID:N:{constructed_n}/{abstain_n}"
        )
    if constructed_years != {
        "2020": 334,
        "2021": 364,
        "2022": 364,
        "2023": 364,
        "2024": 365,
    }:
        raise SelectorIdentityFreezeInvalid(
            f"D2_SELECTOR_IDENTITY_FREEZE_INVALID:CONSTRUCTED_YEARS:{constructed_years}"
        )
    if abstain_years != {
        "2020": 10,
        "2021": 48,
        "2022": 32,
        "2023": 23,
        "2024": 50,
    }:
        raise SelectorIdentityFreezeInvalid(
            f"D2_SELECTOR_IDENTITY_FREEZE_INVALID:ABSTAIN_YEARS:{abstain_years}"
        )

    digest = _hex64(census["SELECTOR_DIGEST"])
    payload = EV.selector_identity_authority_payload(
        canonical_selector_digest=digest,
        design_json_sha256=file_sha256(base / DESIGN_JSON_REL),
        implementation_review_json_sha256=file_sha256(review_path),
        run_identity=run_identity,
        core_btc_snapshot_id=C.CORE_BTC_SNAPSHOT,
    )
    if payload.get("CANONICAL_SELECTOR_DIGEST_FROZEN") is not True:
        raise SelectorIdentityFreezeInvalid("AUTHORITY_NOT_MARKED_FROZEN")

    path = base / EV.SELECTOR_IDENTITY_AUTHORITY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    verified = EV.verify_selector_identity_authority(base)
    authority_sha256 = file_sha256(path)
    return {
        "UNIT": UNIT,
        "CANONICAL_SELECTOR_DIGEST": digest,
        "SELECTOR_IDENTITY_AUTHORITY_SHA256": authority_sha256,
        "SELECTOR_IDENTITY_AUTHORITY_REL": EV.SELECTOR_IDENTITY_AUTHORITY_REL,
        "RULE_1_CONSTRUCTED_N": constructed_n,
        "RULE_1_CONSTRUCTED_YEAR_N": constructed_years,
        "SELECTOR_ABSTAIN_N": abstain_n,
        "SELECTOR_ABSTAIN_YEAR_N": abstain_years,
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT,
        "RUN_IDENTITY": run_identity,
        "OPENED_FILES": list(log.files),
        "OPENED_FILE_COUNT": int(len(log.files)),
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED": False,
        "EXECUTION_PERMIT_CREATED": False,
        "RESULT_CREATED": False,
        "CANONICAL_SELECTOR_DIGEST_FROZEN": True,
        "SELECTOR_IDENTITY_AUTHORITY_CREATED": True,
        "MODULE_CANONICAL_SELECTOR_DIGEST_FROZEN": EV.CANONICAL_SELECTOR_DIGEST_FROZEN,
        "AUTHORITY_CANONICAL_SELECTOR_DIGEST_FROZEN": bool(
            verified.get("CANONICAL_SELECTOR_DIGEST_FROZEN") is True
        ),
        "FROZEN_D2_FACTS": facts,
        "NEXT_UNIT": "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION",
    }


if __name__ == "__main__":
    report = freeze_selector_identity()
    print(json.dumps(
        {k: v for k, v in report.items() if k != "OPENED_FILES"},
        indent=2,
        sort_keys=True,
    ))
    print("OPENED_FILE_COUNT", report["OPENED_FILE_COUNT"])
    print("CANONICAL_SELECTOR_DIGEST", report["CANONICAL_SELECTOR_DIGEST"])
    print("SELECTOR_IDENTITY_AUTHORITY_SHA256", report["SELECTOR_IDENTITY_AUTHORITY_SHA256"])
