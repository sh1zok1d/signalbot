# P3 confirmation V1 — preregistration (frozen before any 2025/2026 outcome is read)

**Date:** 2026-10-09. **Author:** chief architect, on the owner's FORECAST FIRST directive of 2026-10-09: "one hypothesis that decides it".
**Mode:** `CONFIRMATION` (`DISCOVERY_FIRST_RESEARCH_DECISION_V1`). One shot. No variant is tried after an outcome is seen.

## Why this hypothesis
DH3-P3 is the strongest directional result this project has (`docs/research/DH3_RESULT.md`).
- **Discovery** (BTC, Binance, 2020-10..2024-12): crowd long vs crowd short → up first in 4h, −5.92 pp (47.7 % vs 53.5 %), 95 % CI −8.32 … −3.52, Holm p 0.0015, N 14218. Negative in every year.
- **Status:** `PROMISING_PROTOTYPE`, never tested on new data. 2025/2026 objects were not used by DH3.

If it holds on new data and survives trading costs, it is the first candidate signal. If it does not, the best directional lead is closed.

## Surface C (confirmation)
- **Venue and symbol:** Binance USD-M BTCUSDT perpetual.
- **Decision hours T:** from **2025-01-01T00:00Z**, with T + 4h ≤ **2026-08-15T00:00Z**.
- **Objects requested:**
  - 5m klines: monthly 2024-11 … 2026-07, daily 2026-08-01 … 2026-08-14;
  - metrics (`count_long_short_ratio`): daily 2024-11-01 … 2026-08-14.
- **Never requested:** any object dated 2026-08-15 or later. The E1-RUN-001 holdout `[2026-08-16, 2026-08-25 17:20)` and its guard day stay untouched.
- **Epochs** (for heterogeneity and the clustered bootstrap): `2025` = [2025-01-01, 2026-01-01), `2026A` = [2026-01-01, 2026-08-15).

## State and endpoint (DH3-P3, unchanged)
- **Crowd metric:** `count_long_short_ratio`, the snapshot labelled with bar j's open time used at bar j's close, sampled at hourly decision bars.
- **z:** against the trailing 30 days of hourly values (at least 600 present), as `scripts/research/dh3/features.card_p`.
- **State:** `S = 1` crowd long (z ≥ q80), `S = 0` crowd short (z ≤ q20); other hours are not used.
- **Frozen thresholds q20 / q80:** the 20 % and 80 % quantiles of z over the **discovery** decision hours (DH3-P surface, 2020-10-01 … 2025-01-01). They are computed by this pipeline from discovery data only and written to the result before any confirmation outcome is computed.
- **Endpoint:** `UP_FIRST_4H`: 1 if close·(1+X) is reached before close·(1−X) within 48 bars, 0 if the reverse, 0.5 if neither or both in the same bar. X = DH1's barrier (half of the 80 % 4h corridor half-width from the 24h realized scale).
- **Nuisance:** DH3-P3's: hour block, RV tercile, lag tercile, prior-24h-return tercile (terciles within the sample, as DH3 does on every surface).

## Pipeline parity check (gate before the confirmation)
This pipeline reads 5m archives, not DH3's 1m-derived core dataset. It is first run on the **discovery** surface.
- **Pass:** the adjusted shift is within ±1.0 pp of −5.92 pp and N within ±3 % of 14218.
- **Fail:** stop. The confirmation is not run; the mismatch is reported.

## Primary result (statistical)
Estimator: `scripts/research/dh3/evaluate.evaluate_cell` (week-clustered bootstrap, 2000 draws, seed 20261009), the frozen discovery `MODEL` for the skill. Classes, frozen:

| Class | Rule |
|---|---|
| `CONFIRMED` | adjusted shift ≤ −3 pp and CI95 upper < 0 |
| `PRESENT_BELOW_BAR` | CI95 upper < 0 and shift > −3 pp |
| `NOT_CONFIRMED` | CI95 contains 0 |
| `OPPOSITE` | CI95 lower > 0 |

The minimum detectable effect is reported with the result.

## Secondary result (trading translation, frozen)
- **Signal:** at a decision hour in a state, crowd short → **long**, crowd long → **short**.
- **One position at a time:** a signal while a position is open is skipped.
- **Entry:** close[j]. **Exit:** the first of +X / −X on bars j+1 … j+48 (both in one bar → the stop); otherwise close[j+48].
- **Costs:** 0.12 % per round trip (taker 0.05 % × 2, slippage 0.01 % × 2). Funding is not modelled (stated as a limitation).
- **Report:** trades, win rate, mean net return per trade (% and in units of X), sum, max drawdown of the cumulative sum, by epoch and by side; the mean net with a week-clustered bootstrap 95 % CI (2000 draws, seed 20261009).
- **Classes:** `TRADING_PASS` if the mean net > 0 and the CI lower bound > 0; `TRADING_FAIL` otherwise.
- **Sensitivity** (reported, never a class): costs 0.04 % (maker) and 0 %.
- The same translation on the discovery surface is reported as **discovery reference**, not evidence.

## What each outcome means
- `CONFIRMED` + `TRADING_PASS`: the first candidate signal. Next: live paper-trading shadow before any user sees it.
- `CONFIRMED` + `TRADING_FAIL`: the effect is real but too small to trade after costs on this rule.
- `NOT_CONFIRMED` / `OPPOSITE`: the best directional lead does not hold on new data. Closed; never rescued on this surface.

No other cell, threshold, horizon, barrier or cost is tried on surface C.
