# Adaptive occupancy program — closure (owner decision 2026-10-11, Track B)

**Status:** `INFORMATIONALLY_WEAK_ON_AVAILABLE_SURFACES / OUTCOME_NOT_READ`.
**Decision:** MULTISCALE_ADAPTIVE_OCCUPANCY_V2 is **not** run on real market outcomes. The adaptive occupancy program is closed.

## What this means

At the observed scale of the occupancy association (partial ρ ≈ 0.011 given B1) and with the available historical data, the current past-only adaptive procedures lack the information to tell a weak adaptive edge from no edge.

## What this does NOT mean

- OCC = 0;
- adaptation is impossible;
- a market edge is refuted.

## Preserved in full

- **V1:** `ADAPTIVE_OCCUPANCY_TIMESCALE_V1`, `DESIGN_INFORMATIONALLY_INSUFFICIENT / OUTCOME_NOT_READ`.
  - Design SHA `d33f32b7…`, commits `bb5c35ef` / `7df10edc`.
  - Preflight, synthetic power and closure (`ADAPTIVE_OCCUPANCY_TIMESCALE_V1_CLOSURE.md`). Atlas `CLOSED_BEFORE_START`.
- **V2:** `MULTISCALE_ADAPTIVE_OCCUPANCY_V2`, `DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`.
  - Protocol frozen at `6e1bc6a4` before the Monte Carlo summary.
  - Design and synthetic adequacy report `MULTISCALE_ADAPTIVE_OCCUPANCY_V2_DESIGN.md`.
  - Full Monte Carlo record `MULTISCALE_ADAPTIVE_OCCUPANCY_V2_SYNTHETIC_ADEQUACY.json`, with the MDE tables.
  - Atlas `INFORMATIONALLY_WEAK`.
- **No real outer market outcome was read** by V1 or V2.

**Key synthetic facts:**
- MDE80 of the selected V2 is 2.6× the observed order in CONSTANT and > 3× in SWITCHING.
- At the observed order, P(SUPPORT) ≤ 0.18 for every architecture.
- Trailing-memory adaptation costs ≈ 2e-5 Brier against the same model on an expanding window in every world.

## Exposure

**Market exposure counters are not incremented for V1 or V2.** No surface was consumed.

## Not opened now

- a static multiscale OCC model;
- the Clark–West variant;
- new OCC lookbacks;
- spot OCC;
- an occupancy V3.

## Reopening

Reopening occupancy needs a new owner decision and a new reason, for example:
- substantially more data;
- a new independent observable;
- a materially stronger signal family.

The static OCC_4H status `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE` is unchanged.
