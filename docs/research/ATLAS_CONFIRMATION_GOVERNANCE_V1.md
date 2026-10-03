# Atlas confirmation governance V1 — reserve and budget

**Status:** 2026-10-03.
- **Reserve:** `IMPLEMENTED (schema + validation)`. One reservation is registered: the E1-RUN-001 final holdout, which was already protected by its own records. No new dataset is reserved.
- **Budget:** `DESIGN_ONLY`. Nothing is enforced.

This document belongs to `SIGNALBOT_RESEARCH_ATLAS_V1`. Its sources are `docs/research/atlas/ATLAS_SURFACES_V1.yaml` (`reservations:`) and the per-dataset exposure ledger.

## 1. Why

Under `HYPOTHESIS_EVALUATION_CONTRACT_V1`, a replication must be **time-disjoint or prospective**; the same period on another venue is robustness only. Confirmation therefore needs time slices that discovery has not read, and Signalbot has few of them for BTC. Without a rule, autonomous research could spend them one card at a time without anyone deciding to.

## 2. Reserved confirmation surfaces (implemented)

A reservation is an entry in `reservations:` with these fields:
- `id`
- `status`: `RESERVED`, `RELEASED` or `CONSUMED`
- `datasets`
- `period` (start and exclusive end), or none for a whole dataset
- `scope`: regions and cells
- `intended_use`
- `holder_units`
- `permit_required`
- `permit`
- `authority` records

The builder enforces:
1. **Invisible to exploratory generation.**
   - A dataset held whole is left out of the generator view.
   - A held period appears there only as `unavailable_periods`, with no reason text, under the rule that such periods may not be read, used or proposed.
   - A wholly reserved dataset does not count toward a cell's data readiness.
2. **Consumption needs an explicit permit.**
   - A `RESERVED` entry must have `permit_required: true`.
   - A `CONSUMED` entry must name the permit that consumed it.
3. **Scope and use are recorded.** Every entry names its region/cells, its intended confirmation use, and the units entitled to it.
4. **Failed feasibility does not release it.** A reservation stays `RESERVED` when a feasibility check fails before outcomes are opened. Only an owner decision moves it to `RELEASED`, and only a permit moves it to `CONSUMED`.
5. **Conflicts are explicit.** A unit whose frozen data window overlaps a reservation is `BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP` and must name the reservation. Today that unit is `PRICE-OI-PILOT-V0`.

**Registry now:**

| id | status | pristine status | period | holder | authority |
|---|---|---|---|---|---|
| `E1_RUN_001_FINAL_HOLDOUT` | RESERVED | `INVALIDATED_FOR_P4_OVERLAP` | `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` on every atlas dataset covering it | E1-RUN-001 | AGENTS.md; `docs/e1/E1_RUN_001_FINAL_HOLDOUT_EVALUATOR_FREEZE.md`; `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md` |

**Pristine status.** A reservation may record a `pristine_status` other than `PRISTINE`; it must then list its contamination (who opened it, the period, the decision and the record), and the builder fails otherwise. Contamination does not release a reservation. The E1 holdout's outcome surface was opened by the P4 owner-run follow-up over the whole interval (owner decision 2026-10-03, erratum Amendment 1). Its evaluator and sealed artifacts were not touched.

History, not registered: D2's reservation on 2025 and pre-E1 2026 was released by the divergence owner decisions (`CURRENT_RESEARCH_STATE.md`). Adding a reservation needs an owner decision; the atlas never creates one on its own.

## 3. Confirmation budget per region (design only)

**Unit of account.** A budget unit is an **independent outcome slice**: instrument × time span. Datasets are not the unit. Many datasets cover the same span, and the contract does not count a second venue over the same span as confirmation. A slice is spent for a region when a confirmatory or exploratory outcome analysis of any unit in that region read it. The exposure ledger already records this per dataset and row.

**BTC slices on today's map** (from the exposure ledger and the unit records):

| Slice | State for confirmation |
|---|---|
| Binance 2020–2024 | Discovery surface for almost every unit (`CORE_BTC_BINANCE_V0` is exposed for all rows). Not a confirmation surface for any region. |
| BitMEX 2016–2019 | **The only time-disjoint historical slice left.** Spent for VOLATILITY_STATE.tail_risk (D2 replication) and VOLATILITY_STATE.execution_impact (D7 confirmation). Declared but never opened as the replication surface of R03 (expiries, sessions, weekday) and G01 (month boundary). Unspent for the other regions. |
| Binance 2025-01 .. 2026-08-15 | Opened for the divergence/support program (divergence, exhaustion, levels, book support). Consumed for product-feature research (range/volatility, levels, price/OI/taker states, event days). Not declared spent for unrelated families. |
| E1 holdout | Reserved (§2), no longer pristine: its outcome surface was opened by P4. |
| Live archive 2026-07-17T19:30Z .. 2026-09-29T04:00Z | Exposed for all rows by the P4 owner-run follow-up (it contains the E1 holdout). |
| Live archive after 2026-09-29T04:00Z | Short and growing; unread by any recorded analysis. |
| Prospective, after a dated freeze | The only renewable source. It accrues with time. |

**Proposed rules (owner decision):**
1. **One confirmatory family per region and slice.** A confirmatory test consumes its (region, slice) pair permanently. It is recorded as `CONSUMED` exposure and as an atlas event.
2. **Budget is derived from the map, never set by hand.** A region's budget is the number of unspent independent slices it has on the map. Today that is BitMEX 2016–2019 for most regions, plus prospective time.
3. **Autonomous research never spends a region's last unspent historical slice.** For most regions that slice is BitMEX 2016–2019. Spending it would leave only prospective confirmation, so it needs an explicit owner permit naming the card.

   This is the only number in the design, and the map justifies it: the slice is unique.
4. **Prospective slices are allocated at freeze time.** A prospective confirmation names its start date and stopping rule when frozen. Two cards in one region may not share a prospective slice unless their windows are disjoint.
5. **Feasibility before allocation.** A slice is allocated only after feasibility has passed. A card closed at feasibility returns nothing, because it took nothing.

**To implement (not done):**
- a derived `CONFIRMATION_BUDGET` table in the full view (region × slice: unspent / declared / spent / reserved);
- a validation that blocks a confirmatory permit on a spent or last slice without an owner permit.
