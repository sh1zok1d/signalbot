# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1 — draft (Unit B; NOT frozen, NOT to be run)

**Date:** 2026-10-09.
**Status:** `DRAFT_PENDING_DESIGN_REVIEW`. Prepared outcome-blind. Nothing is read.
**Runs only:**
1. after the result of `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1` (Unit A);
2. after a separate design review;
3. after a separate owner go.

**Intent:** the same object, target, primary nuisance set, method, bootstrap and route table as Unit A, on Binance USD-M BTCUSDT 5m from 2025-01-01. It is its own one-shot unit with its own route. It is not combined with Unit A into any joint gate. A later synthesis reads recorded results only.

**Open for the design review (not decided here):**
- **The exact end date** of the surface.
- **How the E1-RUN-001 holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is handled.**
  - Object-level refusal before any request, as in `beta/history_data.py`.
  - The treatment of anchors whose window or target is near it.
  - Other special windows.
- **Exposure accounting:** P3_CONFIRMATION_V1, the level-race held-out read, product statistics, the divergence validation and the architect's disclosed unconditional read. None of them conditioned on `RP4H`, but the review records them.
- **The data source and verification:** Vision objects, checksums, and the µs → ms open-time change in 2025 archives.

No code for Unit B is written until the review.
