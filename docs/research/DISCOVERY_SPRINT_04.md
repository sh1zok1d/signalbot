# Discovery Sprint 04 — Outcome-Blind Selection

**Unit:** `DISCOVERY_SPRINT_04_OUTCOME_BLIND_SELECTION`
**Date:** 2026-09-22
**Base:** `origin/main` `d74255545f709d002733b2cb5d0aa447d7b30198`
**Policy:** `HETEROGENEOUS_FAMILY_ROTATION_V3`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_04.json` (authoritative for exact definitions)

Adaptive discovery on historically exposed data. No outcome computed. No
card executed. D7/D11 not confirmed. Protected 2025/2026 sealed. No
MARKET-07.

## How the selection was made

The mechanism space was reconstructed from the repository first:

- All three survivors (D2, D7, D11) are volatility/activity-level
  structures; every direction/return card is null.
- All eight executed cards used BTC, plus at most ETH or a second venue.
  No card used a true cross-section, forward expectations, or an
  identification (quasi-experimental) design.
- Derivatives-state observables (funding, premium) remain blocked on
  unproven publication latency.

Twelve candidates spanning eight mechanism/source combinations were
generated before any selection, scored on mechanism distance, information
gain, data feasibility and execution cost — never on probability of
success. Two were selected. A third was not forced.

## Candidate pool (12)

| ID | Candidate | Family | Source | Data status | Selected | Reason if not |
|---|---|---|---|---|---|---|
| S4-C01 | Participation clock anchoring (DST natural experiment) | J (new) | DST calendars + CORE BTC 1m volume | ready | **D12** | — |
| S4-C02 | Cross-sectional weekly relative return | H true panel | Binance Vision spot USDT panel | feasibility required | **D13** | — |
| S4-C03 | Cross-sectional synchronization as BTC risk state | H panel as BTC state | same panel | feasibility required | no | vol target; BTC-conditional scalar pattern; BTC common-factor confound; one panel card per sprint |
| S4-C04 | Options implied vs realized variance | forward expectations | Deribit DVOL | feasibility required | no | second new dataset; vol target; positive largely literature-predicted. Named as the only B-eligible region for post-Sprint 04 |
| S4-C05 | Derivatives expiry settlement vol | G | settlement rule + CORE BTC | feasibility required | no | structural copy of the D11 template right after D11 was positive |
| S4-C06 | Perp crowding (funding/premium) | B2-06/MARKET-04 region | Binance USD-M | blocked | no | observable availability unproven (no-lookahead) |
| S4-C07 | TradFi-stress-conditioned BTC–equity coupling | D-like cross-market | FRED VIX/SP500 | feasibility required | no | second dataset; common-vol confound; D12 probes TradFi linkage more cleanly |
| S4-C08 | Stablecoin peg stress reversion | new region candidate | Binance USDCUSDT | feasibility required | no | near-mechanical tick-scale reversion; one episode dominates; low relevance |
| S4-C09 | On-chain stablecoin issuance → participation | new region candidate | on-chain supply series | feasibility required | no | no point-in-time provenance; external-scalar → BTC pattern |
| S4-C10 | Weekend TradFi-closure regime | J-adjacent | calendar + CORE BTC | ready | no | cannot separate TradFi closure from crypto weekly cycle; D12 answers it with identification |
| S4-C11 | BTC–ETH common-factor lead-lag | D | CORE BTC + ETH | ready | no | raw lead-lag rescue forbidden after D10; BTC-ETH subfamily deprioritized |
| S4-C12 | OKX L2 spread/depth state | E (cooldown) | OKX L2 | feasibility required | no | family E cooldown; "better D7" justification; heavy engineering |

Full records (mechanism, observable, function, target, horizon, null,
falsifier, nearest work, confounders, positive/null information) are in
the JSON.

## D12 — `PARTICIPATION_CLOCK_ANCHORING_DST_NATURAL_EXPERIMENT` (family J, new)

**Question.** Is BTC intraday participation anchored to the US wall clock
rather than to UTC?

**Design.** US and EU change daylight-saving time on different dates. In
2020–2024 the US fall-back always comes exactly 7 days after the EU
fall-back, and the US spring-forward comes 14–21 days before the EU one.
Every transition is a Sunday. For each of the 10 US transitions, the
Monday–Saturday **before** and the Monday–Saturday **after** the transition
Sunday form a 6+6-day comparison in which **only the US clock changes**:
both windows contain exactly the same weekdays, neither contains any US or
EU transition day, and the EU clock is constant across both. (Amended
pre-outcome from 7+7: the EU fall transition is the Sunday just before the
US fall transition, so a 7-day window lost a Sunday and broke weekday
balance.) If participation follows
the US clock, the UTC hourly volume-share profile must move one hour
earlier after spring-forward and one hour later after fall-back.

- Observable: per-day 24-bin hourly quote-volume share from CORE BTC 1m
  (complete hours/days only), averaged equally over window days.
- Index: `A = (D(0) − D(δ)) / D(0)`, where `D(L)` is the squared distance
  between the after-profile and the before-profile shifted by `L` hours,
  and `δ` is the clock-predicted shift (+1 spring, −1 fall).
- Null: pseudo-transition Sundays (any Sunday that is not a US/EU
  transition) with the identical Monday–Saturday 6+6 windows; one-sided
  Monte Carlo (N=10000) matched on the δ mix.
- Practical: `A > 0` in ≥7 of 10 US transitions. Temporal: yearly mean
  `A > 0` in ≥3 of 5 years. Support: a window is eligible with ≥5 of its
  6 days included; ≥8 eligible US transitions; ≥100 eligible pseudo
  Sundays.
- EU transitions: same statistic, **diagnostic only**, cannot change the
  classification.
- Not predictive; no decision clock. Search surface: one observable, one
  calendar-derived window, one index.

**Novelty.** No card has asked which clock organizes participation. Not an
event outcome, not a volatility level, not an impact proxy, not a FOMC
child — the design would be identical had D11 been null.

**Positive teaches:** US/TradFi clock linkage is a live region; UTC-hour
matching mixes NY-clock positions. **Null eliminates:** US-clock anchoring
of BTC participation; deprioritizes TradFi-session-timing hypotheses.

**Forbidden claims:** specific participants (ETFs, institutions), equity
session specifically, any direction/return/trading or volatility-level
claim, any re-scoring of D11.

## D13 — `CROSS_SECTIONAL_WEEKLY_RELATIVE_RETURN_STRUCTURE` (family H, true panel)

**Question.** Do relative returns in a liquid, survivorship-controlled
crypto cross-section show 1-week momentum or reversal?

**Design.**

- Source: Binance public data archive, spot monthly 1d klines for all
  USDT-quoted symbols, **including delisted symbols**; months 2019-12 to
  2024-12 only; pinned bucket listings; CHECKSUM-verified object ledger.
  (This unit only listed object keys: SRMUSDT, BUSDUSDT and BTTUSDT keep
  files until their delisting month — encouraging, not proof.)
- Clock: Monday 00:00 UTC. Formation return = last week; holding return =
  next week; non-overlapping.
- Universe at `T`: name-only exclusion of stablecoin/fiat and leveraged
  tokens; ≥35 days listed; closes present at `T−7d` and `T`; top `N` by
  trailing 28-day quote volume strictly before `T`. `N` fixed from counts
  only: `min(100, min over weeks of eligible count)`; `N < 20` → deferred.
- Statistic: mean weekly Spearman rank IC; two-sided sign-flip Monte Carlo
  (N=10000). Momentum and reversal are both pre-declared as structure.
- Practical: signed Q5−Q1 holding-week spread ≥ 4 × a first-party-pinned
  Binance spot taker fee; if the fee can't be pinned, deferred (no
  substitute). Temporal: yearly mean IC same sign in ≥3 of 5 years.
  Support: ≥200 weeks.
- Terminal mark (amended pre-outcome): membership at `T` uses only data
  through `T` and never depends on survival to `T+7d`. Full week → close at
  `T+7d`. Disappears mid-week → final observed close inside the holding
  week. **No close at all after `T` → never dropped, never given a zero
  return, never marked with later relisting data**: counted in
  `NO_POST_T_CLOSE_SELECTED_N`, and execution fails closed as
  `DEFERRED_TERMINAL_MARK_UNRESOLVED` unless the feasibility unit freezes
  a point-in-time terminal-mark authority before outcomes. Reference rule:
  `scripts/research/discovery_sprint_04/d13_terminal_mark.py`.

**Novelty.** First card with more than two assets and first
market-neutral target. Not BTC-conditional prediction, not 24h MAE, not an
ETH substitute, not a flow child.

**Positive teaches:** a cross-sectional structure invisible to BTC-only
work exists; opens the panel region. **Null eliminates:** simple 1-week
cross-sectional momentum/reversal on this panel, and tells us whether the
panel investment deserves more cards.

**Forbidden claims:** tradable strategy or net profitability, BTC
direction, factor/risk-premium interpretation, other horizons or venues.

## Values frozen in the next unit (before any outcome)

- D12: random seed.
- D13: `N`, exclusion lists, pinned taker fee, random seed, first/last
  decision Monday, and a terminal-mark authority if
  `NO_POST_T_CLOSE_SELECTED_N > 0`.

## Pre-outcome amendment 1 (on `fe6f252`)

No outcome inspected; candidate pool and selection unchanged.

- **F1** D12 windows 7+7 → weekday-matched Monday–Saturday 6+6 (real and
  pseudo). Observable, clock-shift algebra, δ sign, statistic, family and
  claim unchanged.
- **F2** Mechanism-memory reference corrected: `MECHANISM_MEMORY_V0` is
  current through D11.
- **F3** D13 no longer silently excludes a selected symbol with no post-`T`
  close; it fails closed instead.

## Next unit

`DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION`

It may acquire the D13 panel (bounded, pinned, 2019-12..2024-12 only), run
count-only feasibility censuses, freeze the values above, and implement
outcome-blind evaluators with synthetic tests. It must not compute D12/D13
outcomes early, widen D12 windows, change D13 horizons, download
2025/2026 files, rerun D7, execute D8, confirm D7/D11, or build generic
generator infrastructure.

```
SPRINT04_SELECTED_CARDS = [D12, D13]
SPRINT04_SELECTED_COUNT = 2
D14 = NOT_SELECTED
EXPECTED_INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER_SPRINT04 = 10
POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED = true
AUTOMATIC_SPRINT05 = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
```
