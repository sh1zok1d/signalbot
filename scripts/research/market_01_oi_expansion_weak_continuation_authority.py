"""MARKET-01 freeze/prereg authentication and execution refusal.

Does not evaluate MARKET outcomes. Canonical bound-dataset execution is
unauthorized in this unit.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_MD = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
PREREG_JSON = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
FREEZE_MD = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md"
FREEZE_JSON = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json"

RESEARCH_ID = "MARKET-01_OI_EXPANSION_WEAK_CONTINUATION"
FROZEN_PREREG_MD_SHA256 = "d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866"
FROZEN_PREREG_JSON_SHA256 = "6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4"
FROZEN_FREEZE_MD_SHA256 = "e0e0da9e22ebed9a9663e3c5f973237e3231e991f13227378288779e6ea07fe4"
FROZEN_FREEZE_JSON_SHA256 = "902863878acd2897c9dacdee6fae068ee17f87f6e10893d3c756b1f49b488176"
ARCH_SOURCE_SHA256 = "104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21"
ARCH_PACKAGE_VERSION = "8.0.0"

PRICE_DATASET_ID = "CORE_BTC_BINANCE_V0"
PRICE_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"

MARKET_01_EXECUTION_AUTHORIZED = False
MARKET_01_ARMED = False
MARKET_01_TEST_CALIBRATED = False
B2_06_EXECUTION_AUTHORIZED = False
DEFAULT_V4 = False
PROTECTED_OOS_AUTHORIZED = False


class Market01AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market01ExecutionNotAuthorized(RuntimeError):
    def __init__(self) -> None:
        super().__init__("MARKET_01_EXECUTION_NOT_AUTHORIZED")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authenticate_frozen_prereg_bytes() -> None:
    md = sha256_file(PREREG_MD)
    js = sha256_file(PREREG_JSON)
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market01AuthorityError("MARKET_01_PREREG_BYTE_IDENTITY_MISMATCH")
    freeze_md = sha256_file(FREEZE_MD)
    freeze_js = sha256_file(FREEZE_JSON)
    if freeze_md != FROZEN_FREEZE_MD_SHA256 or freeze_js != FROZEN_FREEZE_JSON_SHA256:
        raise Market01AuthorityError("MARKET_01_FREEZE_BYTE_IDENTITY_MISMATCH")


def authenticate_arch_selector() -> dict:
    try:
        import arch
        import arch.bootstrap.base as base
    except ImportError as exc:
        raise Market01AuthorityError("MARKET_01_ARCH_SELECTOR_UNAVAILABLE") from exc
    version = str(getattr(arch, "__version__", ""))
    if version != ARCH_PACKAGE_VERSION:
        raise Market01AuthorityError(
            f"MARKET_01_ARCH_VERSION_MISMATCH:{version!r}"
        )
    path = Path(base.__file__)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ARCH_SOURCE_SHA256:
        raise Market01AuthorityError("MARKET_01_ARCH_SOURCE_SHA256_MISMATCH")
    return {
        "package": "arch",
        "package_version": version,
        "source_file": "arch/bootstrap/base.py",
        "source_file_sha256": digest,
        "branch": "stationary-bootstrap only (c=2, b_sb)",
    }


def refuse_bound_execution() -> None:
    raise Market01ExecutionNotAuthorized()


def snapshot_is_bound(snapshot_id: str | None) -> bool:
    if snapshot_id is None:
        return False
    return snapshot_id in {PRICE_SNAPSHOT_ID, OI_SNAPSHOT_ID}
