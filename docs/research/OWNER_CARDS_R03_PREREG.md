# Owner cards R03 — twin preregistration

**Status:** `FROZEN_BEFORE_OUTCOMES`
**Date:** 2026-10-03
**Contract:** `HYPOTHESIS_EVALUATION_CONTRACT_V1`; planning under `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1`
**Machine twin:** `OWNER_CARDS_R03_PREREG.json` is authoritative for every constant; its SHA256 is bound in `SCIENTIFIC_TEST_LEDGER.json` and in the execution permit.
**Design text:** `OWNER_CARDS_R03_CARDS.md`; feasibility: `OWNER_CARDS_R03_FEASIBILITY.md`

```
SEARCH_FAMILY_ID = SF-OWNER-CARDS-R03
TF-R03-A-EXPIRY-CLOCK : executed = ['R03-A1', 'R03-A4'] (Holm m = 2)
TF-R03-B-PANEL-STATES : executed = ['R03-B2'] (Holm m = 1)
TF-R03-C-SESSION-CLOCK : executed = ['R03-C1', 'R03-C2', 'R03-C4'] (Holm m = 3)
CLOSED_AT_FEASIBILITY = {'R03-A2': 'INFORMATIONALLY_WEAK', 'R03-A3': 'INFORMATIONALLY_WEAK', 'R03-B1': 'INFORMATIONALLY_WEAK_AT_UNIT_LEVEL', 'R03-B3': 'INFORMATIONALLY_WEAK_AT_UNIT_LEVEL', 'R03-B4': 'INFORMATIONALLY_WEAK_AT_UNIT_LEVEL', 'R03-C3': 'INFORMATIONALLY_WEAK'}
MARKET_OUTCOMES_COMPUTED = false
PROTECTED_2025_2026_OPENED = false
```

## Executed hypotheses

### R03-A1 `WEEKLY_EXPIRY_HOUR` (R03-A)

- **State:** Friday 08:00-09:00 UTC, the Deribit weekly, monthly and quarterly expiry hour
- **Comparator:** 08:00-09:00 UTC on Monday-Thursday of the same ISO week
- **Unit:** ISO_WEEK; frozen units 260, digest `c21fb0f451224fb6…` (`owner_cards_r03/UNITS_R03-A1.json`)
- **Expected sign:** POSITIVE
- **Mechanism (descriptive motivation, not a claim):** Deribit settles every listed option and future at 08:00 UTC on Fridays. Dealers and basis traders unwind hedges and roll positions into and out of that hour, so the hour carries more price discovery than the same hour on other weekdays.
- **Replication:** Deribit expiries ran at 08:00 UTC through 2017-2019; BitMEX XBTUSD 5m bars.

### R03-A4 `PRE_EXPIRY_PINNING` (R03-A)

- **State:** Friday 04:00-08:00 UTC, the four hours before the Deribit expiry
- **Comparator:** 04:00-08:00 UTC on Monday-Thursday of the same ISO week
- **Unit:** ISO_WEEK; frozen units 260, digest `1d87cae9f481462f…` (`owner_cards_r03/UNITS_R03-A4.json`)
- **Expected sign:** NEGATIVE
- **Mechanism (descriptive motivation, not a claim):** Into a large options expiry, dealer gamma hedging near popular strikes pins the spot price, so the pre-expiry window should show a narrower range than the same window on other weekdays.
- **Replication:** Same rule on BitMEX 2017-2019.

### R03-B2 `BREADTH_SYNCHRONY` (R03-B)

- **State:** UTC day whose |fraction of eligible symbols with a positive daily return - 0.5| is at or above its trailing-180-day 0.80 quantile
- **Comparator:** Other eligible UTC days of the same calendar month
- **Unit:** CALENDAR_MONTH; frozen units 53, digest `74fedd39d084cbe9…` (`owner_cards_r03/UNITS_R03-B2.json`)
- **Expected sign:** POSITIVE
- **Mechanism (descriptive motivation, not a claim):** When nearly every symbol moves the same way, the move is a common-factor shock. Common shocks cluster, so the next BTC day should carry a wider range.
- **Replication:** prospective panel surface (card B)

### R03-C1 `WEEKEND_HOURS` (R03-C)

- **State:** Every UTC hour of Saturday and Sunday
- **Comparator:** The same UTC hour of Tuesday, Wednesday and Thursday of the same ISO week
- **Unit:** ISO_WEEK; frozen units 260, digest `950aefc338362ffe…` (`owner_cards_r03/UNITS_R03-C1.json`)
- **Expected sign:** NEGATIVE
- **Mechanism (descriptive motivation, not a claim):** Traditional-finance participants and their funding rails are closed at the weekend, so the hourly range should be narrower hour for hour.
- **Replication:** Same rule on BitMEX 2017-2019.

### R03-C2 `MONDAY_US_OPEN` (R03-C)

- **State:** Monday 09:30-10:30 America/New_York, excluding Mondays that are NYSE full-day closures
- **Comparator:** 09:30-10:30 America/New_York on Tuesday-Thursday of the same ISO week
- **Unit:** ISO_WEEK; frozen units 232, digest `a8bf182fafaca086…` (`owner_cards_r03/UNITS_R03-C2.json`)
- **Expected sign:** POSITIVE
- **Mechanism (descriptive motivation, not a claim):** Information that accumulates over the weekend is priced by US-session participants when they return; the first US-open hour of the week should carry a wider range than the same hour later in the week.
- **Replication:** BitMEX 2017-2019; NYSE closures are not pinned for those years, so Monday closures are not excluded there.

### R03-C4 `FRIDAY_US_CLOSE` (R03-C)

- **State:** Friday 15:00-16:00 America/New_York, excluding Fridays that are NYSE closures or early-close days
- **Comparator:** 15:00-16:00 America/New_York on Tuesday-Thursday of the same ISO week
- **Unit:** ISO_WEEK; frozen units 246, digest `b57b2f0e5147c18f…` (`owner_cards_r03/UNITS_R03-C4.json`)
- **Expected sign:** POSITIVE
- **Mechanism (descriptive motivation, not a claim):** Before the weekend, participants who cannot manage risk over two closed days square positions in the last regular US hour of the week.
- **Replication:** BitMEX 2017-2019; NYSE early closes are not pinned there, so no exclusion is applied.

## Frozen inference

- Target: log range of the window; standardized per year and window definition, label-blind.
- Estimand: mean over units of d = mean z(state) − mean z(comparator).
- Test: sign-flip over units, 20000 draws, seed 20261003 + index, two-sided; Holm within the card at alpha 0.05.
- Practical bar: |estimate| ≥ 0.5 SD with the declared sign.
- Epochs: calendar years; Q test against a block permutation (4-unit blocks, 2000 draws) and the opposite-sign test; the compiler recorded every cell `NOT_ASSESSABLE`, so the epoch record is descriptive and cannot fail a card.
- Nuisance diagnostic: prior 24h realized variance and the lagged target, fitted label-blind; it decides wording only.
- Replication (cards A and C): BitMEX XBTUSD 5m 2017-01..2019-12, same rule, Holm over the replicated prototypes of the card; card B: prospective from 2027-01-01 with the fixed stopping rule in the planning objects.

## Classification

Discovery: `PROMISING_PROTOTYPE` iff statistical and practical pass; `NO_INCREMENTAL_STRUCTURE` otherwise. Final: `SUPPORTED_UNCONDITIONAL` iff the replication also passes; `PROMISING_PROTOTYPE_NOT_REPLICATED` if it fails; `PROMISING_PROTOTYPE` when no replication surface exists in this unit.

## Forbidden after outcomes

- any change to a window, state, comparator, unit, standardization or seed
- any added hypothesis, regime, horizon or sign
- any rescue of a closed hypothesis
- any rerun
- any 2025/2026 object

## Interpretation

Allowed: A non-directional description of the range of a scheduled or calendar-defined hour or day relative to a named ordinary-conditions comparator, with the nuisance diagnostic deciding whether the state is more than the general volatility regime.

Forbidden: No direction, no trade, no target, no probability of direction, no causal claim about dealers, hedgers or any participant group, no generalization beyond the venue and years tested.
