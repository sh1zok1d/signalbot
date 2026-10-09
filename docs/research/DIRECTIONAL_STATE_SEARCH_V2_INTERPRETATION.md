# DIRECTIONAL_STATE_SEARCH_V2 — interpretation, claim decision and replication proposals (after the one cycle)

**Date:** 2026-10-09. **Author:** chief architect.
**Reads only:** the frozen evaluator output `DIRECTIONAL_STATE_SEARCH_V2_RESULT.json` (SHA256 `25e67a16…3389`) / `.md` (`e47fb3fd…e75d`).
**Design:** `99205a3a`, SHA256 `a361ff35…2c52`. **Pre-outcome ledger:** `5ae1a804…98e6`.
**Status:** every number is `DISCOVERY_ONLY` on an exposed surface (`ADAPTIVE_HISTORICAL_DISCOVERY`). Nothing here is a confirmation, a current probability or a product line.

## 1. What the cycle found

**One object carries information beyond the baseline and clears the search bar: F2a `OCC_MEAN_4H`.**
- **Incremental partial Spearman** (B0 = RP4H, RET_4H, RV_4H): +0.0202 [+0.0130, +0.0277], z 5.31, N 175,292, 262 weeks.
- **Raw:** +0.0256 [+0.0185, +0.0329].
- **Per year:** 2020 +0.022, 2021 −0.001, 2022 +0.024, 2023 +0.042, 2024 +0.019 (4/5 same sign; 2021 flat).
- **Declared variant OCC_THIRDS_4H:** +0.0212 [+0.0140, +0.0287], consistent.
- **Residual quintiles** (state net of B0): P(UP) 0.491 / 0.499 / 0.506 / 0.517 / 0.530; median R_1H −0.65 … +2.43 bp; mean not monotone (+0.81, −0.16, +0.16, +0.86, +1.27 bp).
- **Stage 2:** the interaction with RP4H is −0.0045 [−0.0111, +0.0023]. The RP4H partial is −0.037 / −0.025 / −0.039 across OCC terciles, so OCC does not modify the RP4H effect. It adds a separate term.
- **Reading:** at the same current position in the 4h range, the next hour was more often up when price had spent more of the 4h above where it is now. This is a time-weighted reference: the close relative to where the 4h path lived.

**Rules §4 search bar:** |z| ≥ 3.848 (m = 813 + 27 cells). Only F2a clears it.

## 2. Competing reading of F2a (not tested here; must be in the replication design)

OCC_MEAN_4H − RP4H = (TWAP_4H − C_T)/(H − L): the close's distance below its 4h time-weighted mean, in range units.
- That makes F2a a member of the short-horizon reversal family measured against a third reference: start price → RET_4H, range extremes → RP4H, time-weighted mean → OCC.
- **Outcome-blind collinearity check after the run** (no R_1H read; feature–feature only):
  - Spearman(OCC, RET_1H) −0.26;
  - partial(OCC, RET_1H | B0) −0.42;
  - partial(OCC, RET_30M | B0) −0.27;
  - partial(OCC, RET_15M | B0) −0.16.
- **Prior evidence on the local path:** a short local reversal exists beyond B0 on this surface. The F6a placebo (30-min return / RV at every other anchor) is −0.029 [−0.034, −0.024]. RP4H's own partial fell when RET_1H and RET_15M were added in Units A and B.
- **Consequence:** part, possibly most, of F2a's +0.020 may be the last-hour reversal rather than "where price lived".
- This cycle did not pre-declare a local-path control for F2a. Adding one now would be an analysis chosen after the result, so it is not done.
- The replication design must declare it before its outcome (§6).

## 3. Nulls and objects explained away

| id | state | raw | incremental | reading |
|---|---|---|---|---|
| F1a | SPA_24H | −0.022 [−0.031, −0.014] | +0.002 [−0.007, +0.011] | **explained away** by RET_24H / RET_4H / RP4H / RV (SPA ~ RET_24H, ρ 0.79) |
| F1b | UPFRAC_24H | −0.016 [−0.024, −0.007] | +0.006 [−0.002, +0.015] | **explained away** (same) |
| F4a | CMD_UP_24H | −0.019 [−0.026, −0.011] | +0.001 [−0.008, +0.009] | **explained away** (ρ with RET_4H 0.41, RP4H 0.31) |
| F3a | REJ_DECAY_24H | +0.001 [−0.020, +0.022] | +0.003 [−0.018, +0.023] | **null** (N 25,439) |
| F7a | FLOW_RESPONSE_CHANGE_4H | −0.005 [−0.012, +0.002] | −0.003 [−0.010, +0.005] | **null**; sensitivity with the λ level −0.002 [−0.010, +0.005] |
| F7b | SIDE_ASYM_CHANGE_4H | +0.004 [−0.004, +0.012] | +0.002 [−0.006, +0.011] | **null** |
| F6a | US_OPEN_DRIVE | −0.043 [−0.103, +0.016] | −0.030 [−0.089, +0.029] | **no clock effect:** clock − placebo −0.000 [−0.061, +0.060]; the drive behaves like any 30-min return |
| F6b | SESSION_HANDOFF | −0.054 [−0.110, +0.002] | −0.056 [−0.110, −0.002] | **below the bar** (z −1.95; Holm p 0.10); 5/5 years negative; clock − placebo −0.044 [−0.099, +0.009] includes zero; the placebo itself is −0.012 [−0.020, −0.004] |

**Important nulls:**
- The **E1 change-in-response objects** (F7a, F7b) carry no directional information beyond flow and B0 on CORE. This was the owner-admitted form of E1.
- **Path asymmetry** (S1's observable) and **countermove decay** are momentum/position in other clothes at 1h: their raw signal disappears after RET_24H/RET_4H/RP4H.
- **Rejection decay** on a 24h box carries nothing.
- **US open drive** is not a clock effect.

## 4. Claim decision (EVIDENCE_AND_CLAIMS ladder)

- **F2a:** L1 discovery evidence on an exposed surface: a partial rank association of +0.020 with an interval above zero, beyond B0. Not L2: no replication. Not a probability. No bot line, no product line.
- **All other objects:** no claim.
- **F6b:** recorded as a below-bar discovery observation with no clock separation. No successor is proposed from it.

## 5. Ranking (the frozen rule) and TOP 3

- **Eligible:** F2a only (interval excludes zero, 4/5 years, z 5.31 ≥ 3.848, replication surfaces exist).
- **Not eligible:** F6b (z −1.95 < bar; also fails the placebo separation), and every other object (interval includes zero).
- **TOP 3 = {F2a}.** Fewer than three qualify. No object is added to fill the list.

## 6. Proposed replication unit (not executed; needs its own design note and owner GO)

**OCC_MEAN_4H_TEMPORAL_REPLICATION_V1.**
- **Object:** F2a exactly (the 47 prior closes in the RP4H box at T; current close excluded), R_1H, 15-minute RP4H anchors.
- **Primary:** partial Spearman(OCC_MEAN_4H, R_1H | RP4H, RET_4H, RV_4H), as discovered.
- **Declared before the outcome, decisive for "not a renamed reversal":** partial given B0 + RET_1H + RET_15M (the Unit A/B local-path set).
  - A replication that holds only without the local path is reported as `REVERSAL_RELABEL_NOT_EXCLUDED`.
- **Fresh surfaces** (none ever read OCC against a direction outcome):
  1. **BitMEX XBTUSD 5m 2016-05 … 2019-12** (D2 canonical; time-disjoint, longest; RP4H was read there by Unit A, OCC was not). The first choice.
  2. **Binance spot BTCUSDT 5m 2017-08 … 2019-12** (another market type and epoch).
  3. **Binance USD-M BTCUSDT 2025-01 … 2026-10, E1 window and E1-development slice excluded.** Only after its own per-question exposure audit. The E1 CB breakout is adjacent (box extremes); Unit B read RP4H there.
- **Prospective:** live 5m after a freeze.

## 7. Exposure written

- **CORE × DIRECTION:** 27 cells read in this cycle: 9 objects × (raw, incremental), 1 variant × 2, 1 sensitivity, 2 placebo, 2 placebo differences, 2 stage-2 interactions. The counter moves from ≈813\* to ≈840\*.
- **Not read:** no 2025/2026 object, no OI, no spot, no BitMEX, no successor.
- **Blocked before outcome:** FAILED_PROGRESS (owner-closed divergence/selling-exhaustion line) and OI_RESPONSE (owner-closed DH3 line / MARKET-01; OI permit). Each needs an owner ruling to reopen.
