"""MARKET-05 canonical production bootstrap.

Import order is the root of trust:

    stdlib + authority_root
    -> verify authority root
    -> refuse if scientific modules are already in sys.modules
    -> verify source bytes + execution environment
    -> authenticate ARM/reservation (pre-claim)
    -> structural data preflight (no Y)
    -> atomic execution claim  (THIS consumes the one-shot)
    -> only then import evaluator/data modules
    -> verify imported files resolve to the repository copies
    -> execute science and write RESULT

This module imports only the standard library at load time.
"""

from __future__ import annotations

import sys
from typing import Any

FORBIDDEN_PRELOADED_MODULES = (
    "scripts.research.market05_cross_asset_lib",
    "scripts.research.market05_cross_asset_canonical_execution",
    "scripts.research.market05_cross_asset_data",
    "scripts.research.market05_eth_execution_binding",
    "scripts.research.market05_cross_asset_data_preflight",
)


class Market05BootstrapError(RuntimeError):
    """Canonical bootstrap refused before or during verification."""


def _refuse_preloaded_scientific_modules() -> None:
    loaded = [name for name in FORBIDDEN_PRELOADED_MODULES if name in sys.modules]
    if loaded:
        raise Market05BootstrapError(
            "MARKET_05_SCIENTIFIC_MODULE_PRELOADED:" + ",".join(sorted(loaded))
        )


def run_canonical_market_05_bootstrap(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """The only production entry that may open scientific data."""
    if args or kwargs:
        raise Market05BootstrapError(
            "caller arguments cannot redefine MARKET-05 canonical bootstrap"
        )
    _refuse_preloaded_scientific_modules()

    from scripts.research.market05_cross_asset_authority_root import (
        Market05AuthorityRootError,
        verify_authority_root,
    )

    try:
        verify_authority_root()
    except Market05AuthorityRootError as exc:
        raise Market05BootstrapError(str(exc)) from exc

    _refuse_preloaded_scientific_modules()

    from scripts.research.market05_cross_asset_arm_authority import (
        authenticate_frozen_scientific_bytes,
        authenticate_market_05_pre_claim,
        derive_market_05_run_identity,
        verify_execution_environment,
    )

    authenticate_frozen_scientific_bytes()
    verify_execution_environment()
    bound = authenticate_market_05_pre_claim()
    run_identity = bound["run_identity"]
    if run_identity != derive_market_05_run_identity():
        raise Market05BootstrapError("MARKET_05_RUN_IDENTITY_DRIFT")

    from scripts.research.market05_cross_asset_data_preflight import (
        run_structural_preflight,
    )

    run_structural_preflight()

    from scripts.research.market05_cross_asset_execution_claim import (
        create_execution_claim_atomically,
    )

    create_execution_claim_atomically(bound["claim_payload"])

    from scripts.research import market05_cross_asset_canonical_execution as execution
    from scripts.research import market05_cross_asset_lib as lib

    execution.verify_imported_module_paths()
    lib_file = getattr(lib, "__file__", "")
    execution.verify_imported_lib_path(lib_file)
    return execution.execute_science_after_claim()


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        run_canonical_market_05_bootstrap()
    except Exception as exc:  # noqa: BLE001 — fail closed to stderr
        sys.stderr.write(f"{exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
