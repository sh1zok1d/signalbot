# Owner cards R03 — the three cards and twelve hypotheses

**Status:** `DESIGN_FROZEN / EXECUTED_ONCE` (result: `OWNER_CARDS_R03_RESULT.md`) (constants in `scripts/research/owner_cards_r03/constants.py`)
**Decision record:** `OWNER_CARDS_R03_DECISION.md`
**Planning objects:** `OWNER_CARDS_R03_PLANNING.json` (one `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1` object per hypothesis)

## Common design

- **Target.** Log range `ln(max high / min low)` of a window. Standardized per calendar year and per window definition over all days' windows of that definition (label-blind), so an estimate is in comparator-SD units.
- **Unit and estimand.** Each hypothesis names a unit (ISO week, calendar month, closure day). Inside a unit, `d = mean z(state windows) − mean z(comparator windows)`. The estimate is the mean of `d` over units.
- **Inference.** Sign-flip randomization over units, 20 000 draws, seed 20261003 + hypothesis index, two-sided p. Holm within the card over the executed hypotheses at family alpha 0.05. A moving-block SE over units is reported as a dependence diagnostic.
- **Practical bar.** |estimate| ≥ 0.5 SD with the declared sign (any sign for a two-sided claim).
- **Epochs.** Calendar years; block-permutation heterogeneity test and opposite-sign test are recorded. The compiler's outcome-blind assessability decides whether the gate can fail the card.
- **Nuisance diagnostic.** Prior 24h realized variance and the lagged target (same window, previous day), fitted label-blind per year and definition. If the adjusted estimate keeps less than half of the raw estimate or changes sign, the wording is "reflects the general volatility regime".
- **Claim type.** `CONTEXT_DESCRIPTIVE`, `UNCONDITIONAL`, `ATOMIC`. No direction, no trade, no cause.

## R03-A — Scheduled derivatives-expiry clock (family G)

| ID | State | Comparator | Unit | Expected |
|---|---|---|---|---|
| A1 `WEEKLY_EXPIRY_HOUR` | Friday 08:00–09:00 UTC (Deribit expiry hour) | 08:00–09:00 UTC Mon–Thu, same ISO week | week | wider |
| A2 `LARGE_EXPIRY_INCREMENT` | 08:00–09:00 UTC on the last Friday of the month | 08:00–09:00 UTC on the other Fridays of the month | month | wider |
| A3 `CME_EXPIRY_HOUR` | hour from 16:00 London on the last Friday of the month (CME BRR settlement) | same London hour on the other Fridays of the month | month | wider |
| A4 `PRE_EXPIRY_PINNING` | Friday 04:00–08:00 UTC | 04:00–08:00 UTC Mon–Thu, same week | week | narrower |

Replication: BitMEX XBTUSD 5m, 2017-01..2019-12 (A3 from 2018-01, CME listing).
Nearest prior work: D11 (FOMC, forbidden to copy), D8 (deferred). Neither touched settlement clocks.

## R03-B — Panel breadth and dispersion states (family H)

Universe at UTC day d: USDT-quoted spot symbols not in `EXCLUSION_LISTS.json`, with 30 prior days present, top 100 by trailing-30-day median quote volume; at least 20 symbols; BTC included. States are past-only trailing-180-day quantiles of the day-d metric; the decision boundary is T = d+1 00:00 UTC; the target is the BTC day [T, T+24h).

| ID | Day-d metric | State | Unit | Expected |
|---|---|---|---|---|
| B1 `RETURN_DISPERSION_HIGH` | cross-sectional SD of daily log returns | ≥ trailing P80 | month | wider |
| B2 `BREADTH_SYNCHRONY` | \|fraction up − 0.5\| | ≥ trailing P80 | month | wider |
| B3 `VOLUME_SHOCK_FRACTION` | fraction of symbols with quote volume ≥ 2× own 30-day median | ≥ trailing P80 | month | wider |
| B4 `BTC_SHARE_LOW` | BTC share of universe quote volume | ≤ trailing P20 | month | two-sided |

Comparator: the other eligible days of the same calendar month. Replication: prospective, Binance spot panel from 2027-01-01, stop at 730 days or 2028-12-31, minimum 365 days with at least 60 state and 240 comparator days; counts-only monitoring.
Nearest prior work: D13 (weekly relative-return rank IC, null), D9 (two-venue share, null), S4-C03 (pool, not selected).

## R03-C — Session and participant-clock structure (family J)

| ID | State | Comparator | Unit | Expected |
|---|---|---|---|---|
| C1 `WEEKEND_HOURS` | every UTC hour of Saturday and Sunday | same UTC hour Tue–Thu, same week | week | narrower |
| C2 `MONDAY_US_OPEN` | Monday 09:30–10:30 New York (not a NYSE closure) | same local hour Tue–Thu, same week | week | wider |
| C3 `NYSE_CLOSURE_US_OPEN` | 09:30–10:30 New York on a weekday NYSE full-day closure | same local hour on the other non-closure weekdays of the week | closure day | narrower |
| C4 `FRIDAY_US_CLOSE` | Friday 15:00–16:00 New York (not a closure or early close) | same local hour Tue–Thu, same week | week | wider |

Local hours are resolved with the IANA tz database, so DST is exact. Replication: BitMEX 2017-2019 for C1, C2 and C4 (no pinned NYSE calendar for those years, so no exclusions there); C3 has no replication surface.
Nearest prior work: D12 (US-DST profile shift, prototype; not re-scored), D3 (time of day as a nuisance stratum), S4-C10 (pool, not selected).

## Feasibility

The outcome-blind count pass and compile are in `OWNER_CARDS_R03_FEASIBILITY.md/.json`. Hypotheses that fail there are closed and never executed; the Holm count of each card is the number that pass.
