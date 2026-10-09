"""Frozen Unit B bounds. The scientific constants are Unit A's (imported there and asserted equal in tests)."""

from __future__ import annotations

UNIT = "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1"
EVIDENCE_CLASS = "TEMPORAL_HISTORICAL_REPLICATION / ONE_SHOT"
CLAIM_CEILING = "HISTORICAL_ONLY"
DESIGN_SHA256 = "PENDING_DESIGN_HASH"
DESIGN_COMMIT = "PENDING"
SIBLING_UNIT = "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1"
PARENT_UNIT = "RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1"

MANIFEST = "docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json"
OBJECT_LIST_SHA256 = "5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621"
VISION = "https://data.binance.vision/"

BAR_MS = 300_000
SURFACE_START_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z
SURFACE_END_MS = 1_791_504_000_000    # 2026-10-09T00:00:00Z (exclusive)
PHASE_ORIGIN_MS = 1_577_836_800_000   # parent clock origin 2020-01-01T00:00:00Z

# Unit-specific exclusion, fixed before freeze by the exposure audit (in addition to the product's E1 guard):
# the E1-RUN-001 development slice read an exact-class equivalent of RP4H -> R_1H on this surface.
EXCLUDED_PERIODS = (
    ("E1-RUN-001 development exposure slice", 1_785_628_800_000, 1_786_838_400_000),  # [2026-08-02, 2026-08-16)
)

# Preflight census, pinned after the outcome-blind preflight and before the run (timestamps only).
CENSUS_PINNED = False
EXPECTED_ROWS = None
EXPECTED_HOLES = None
EXPECTED_HOLES_SHA256 = None
EXPECTED_ANCHORS = None
