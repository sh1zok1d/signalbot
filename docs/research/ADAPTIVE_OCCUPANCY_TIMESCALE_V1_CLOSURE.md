# ADAPTIVE_OCCUPANCY_TIMESCALE_V1 — closure (owner decision 2026-10-10)

**Status:** `DESIGN_INFORMATIONALLY_INSUFFICIENT / OUTCOME_NOT_READ`. Atlas state `CLOSED_BEFORE_START`.
**Decision:** DO NOT RUN. No real market outcome of this design may be read.

## Why

The frozen hard-selection design failed its outcome-free synthetic power check (design §10–§11, `ADAPTIVE_OCCUPANCY_TIMESCALE_V1_PREFLIGHT.json`):
- ADAPTIVE was worse than B1 in NULL, CONSTANT_OCC_4H and **SWITCHING_OCC_2H_8H**, the world built to reward adaptation, at β = 0.03.
- β = 0.06 did not rescue the switching scenario: NONE.
- An expanding-memory option did not rescue it either.

A real NULL/WORSE would therefore not discriminate between:
- **A.** no adaptive occupancy information in the market;
- **B.** an incapable selector.

**This is a design failure, not a market result.**

## Preserved (unchanged)

- Design `docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1_DESIGN.md`: SHA256 `d33f32b7ec4eaa9b970f444600b9c512dc7b608523008215f710b3ef0703ee0d`, freeze commit `bb5c35ef`, pins `7df10edc`.
- Design JSON, fold and selector manifests, exposure record.
- Preflight record with the synthetic power results and the two outcome-free owner options.
- Code `scripts/research/adaptive_occupancy_v1/`. The only change after the pins: `run --go` refuses with `OWNER_CLOSED` (`constants.OWNER_STATUS`).

## Facts

- **No real outer metric was computed or read.** No result file and no attempt journal (`docs/research/adaptive_occupancy_timescale_v1_execution/`) exist.
- **No surface consumed:** DIRECTION exposure counters are **not** incremented for the unexecuted outer evaluation. The 78 cells listed in the exposure record were conditional on a run that will not happen.
- **Unchanged:** the static OCC_4H status `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE`.

## Successor

`MULTISCALE_ADAPTIVE_OCCUPANCY_V2` is a new algorithmic object: one regularized logistic model on B1 plus all seven OCC_L, with no discrete lookback selection. It needs its own outcome-free synthetic adequacy gate before any preflight or owner go. V1 cannot become its primary model.
