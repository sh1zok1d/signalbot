# MARKET-03 PUBLIC STRATEGY REPLICATION — Preregistration

- **Status:** `PREREGISTERED_OUTCOME_BLIND`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_PREREG`
- **Date:** 2026-09-18
- **Machine-readable twin:** `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json`
  (SHA256 `3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89`;
  15587 bytes)
- **Parent design (sole design authority):**
  `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.md`
  (commit `9454af65398df1d3f5e0cb3af5e48c0986049d2d` /
  tree `27531689a1185dda7946f6742d725a87477911e2`;
  JSON SHA256 `91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57`)

This document is the complete outcome-blind MARKET-03 preregistration.
It copies the approved design. It does **not** redesign MARKET-03, implement
the strategy, ARM, execute, inspect outcomes, or search parameters.

A separate freeze record binds these exact bytes. This file's internal
status string remains `PREREGISTERED_OUTCOME_BLIND`. Freeze authority is
the freeze document, not a silent edit of these bytes.

```text
MARKET_03_STRATEGY_EXECUTED        = NO
MARKET_03_OUTCOMES_INSPECTED       = NO
MARKET_03_PARAMETER_SEARCH         = NO
MARKET_03_ARMED                    = NO
CANONICAL_EXECUTIONS_AUTHORIZED    = 0
CANONICAL_EXECUTIONS_CONSUMED      = 0
PROTECTED_OOS_TOUCHED              = NO
execution_authorized               = NO
```

---

## 0. What this is and is not

MARKET-03 is **EXTERNAL HISTORICAL CLAIM REPRODUCTION**
(`EXTERNAL_HISTORICAL_CLAIM_REPRODUCTION`) at

```text
LEVEL_2_FAITHFUL_REIMPLEMENTATION
```

It addresses track **A** only: reproduce the final published strategy
claim. It does **not** address track **B**: validate the author's
42-strategy / EMA / funding-threshold / cross-asset selection pipeline.

It is **not**:

- independent forward replication
- untouched OOS confirmation
- live alpha validation
- causal funding evidence
- LEVEL_1 exact reproduction
- LEVEL_3 perpetual-price substitution
- a rescue of MARKET-01 / MARKET-02 (`NO_EVIDENCE`)
- confirmation of Signalbot OI hypotheses

JSON sidecars **must** be loaded. Class defaults are not the published
contrast.

---

## 1. Pinned external source

```text
EXTERNAL_REPO     = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_COMMIT   = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE     = f7717e681c911ea3ccce15492246053cf15883cb
FAMILY            = EmaCross vs EmaCrossFunding
PUBLICATION       = 2026-08-22
LICENSE           = GPL-3.0
FREQTRADE_PIN     = freqtrade>=2026.7   (NO UPPER BOUND)
ENGINE_DOCS_PIN   = Freqtrade 2026.7 documented backtesting / stoploss /
                    IStrategy defaults
BASELINE          = EmaCross
FILTERED          = EmaCrossFunding
```

Inventory: `docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/`.

---

## 2. Frozen temporal identity

Author headline timerange `20191001-` is **open-ended** and extends into
Signalbot protected 2025/2026 OOS (implied author terminal ≈ 2026-08).
MARKET-03 **deliberately truncates** reproduction at `2025-01-01` to
preserve protected OOS. Do **not** inspect 2025/2026 data. Do **not**
treat Signalbot data through `2024-12-31` as the author's full headline.

```text
WARMUP_INTERVAL      = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL  = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
HEADLINE_OVERLAPS_PROTECTED_OOS = YES
PROTECTED_OOS_TOUCHED           = NO
```

Warmup candles may form indicators only. They **must not** contribute to
performance metrics.

No fill may use a candle whose `open_time >= 2025-01-01T00:00:00Z`. An
open trade at the authorized end is `force_exit`ed on the last in-interval
candle only, without reading 2025/2026 prices.

---

## 3. Data authorities

### 3.1 Spot (frozen identity; required)

```text
DATASET_ID       = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SNAPSHOT_ID      = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256 = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4
exchange         = Binance
market_type      = SPOT
symbol           = BTCUSDT
interval         = 1h
```

CORE USD-M perpetual prices must **not** be substituted.

### 3.2 Funding (PRE-ARM REQUIRED ARTIFACT)

B2-06 is **not** MARKET-03 funding authority.

```text
PROPOSED_DATASET_ID = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
SOURCE              = REST GET /fapi/v1/fundingRate
FIELD               = fundingRate
TIMESTAMP           = fundingTime
ACQUIRED_JSONL_SHA256
  = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
ROWS                = 5819
NAMED_SNAPSHOT      = NOT YET MATERIALIZED
FUNDING_SNAPSHOT_READY = NO
REQUIRED_BEFORE_ARM = YES
```

Author bundled `funding.feather` is **not** authority (it extends into
protected 2025/2026). Constructing the named snapshot must not create
scientific outcomes.

---

## 4. Exact strategy semantics

Copied from the approved design. No field below is implementation-defined.

| Item | Frozen value |
|---|---|
| Market | Binance SPOT BTC/USDT |
| Timeframe | `1h` |
| EMA | TA-Lib `EMA(close, 600)` |
| Exit level | `ema * (100 - 2.0) / 100` |
| Entry | `qtpylib.crossed_above(close, ema) AND volume > 0` |
| Entry tag (baseline) | `ema_cross_up` |
| Entry tag (filtered) | `ema_cross_funding_ok` |
| Exit | `qtpylib.crossed_below(close, ema_exit)` |
| Exit tag | `ema_cross_down` |
| Shorts | disabled (`can_short = False`) |
| `crossed_*` | prior **present** dataframe row, not prior calendar hour if missing |
| Stoploss | `-0.15` |
| Trailing | `trailing_stop = True` |
| `trailing_stop_positive` | `None` |
| `trailing_stop_positive_offset` | `0.0` |
| `trailing_only_offset_is_reached` | `False` |
| Trailing behavior | trail the **−15%** stop from the highest observed price; no tighter positive trail |
| ROI | `minimal_roi = {"0": 10}` (effectively inactive) |
| Max open trades | `1` |
| Pyramiding / position adjust | none |
| Stake | `"unlimited"` |
| `tradable_balance_ratio` | `0.99` |
| Initial capital | `10000` USDT |
| Compounding | **yes** |
| Fee | `0.001` per side, applied twice |
| Slippage | none if requested price inside candle high/low |
| `--timeframe-detail` | **not used** |
| Protections | **disabled** |
| `startup_candle_count` | `1300` |
| `process_only_new_candles` | `True` |
| Interface | v3 |
| `use_exit_signal` | `True` |
| `exit_profit_only` | `False` |
| `exit_profit_offset` | `0.0` |
| `ignore_roi_if_entry_signal` | `False` |
| Order types | entry/exit/stoploss `limit`; `stoploss_on_exchange = False` |
| TIF | `GTC` |
| Live order book | **ignored in backtest** |
| Entry / exit signal timing | candle **close** |
| Entry fill | **open of the next candle** |
| Exit-signal fill | **open of the next candle** |
| Stoploss fill | exactly at stoploss price even if `low` was lower; loss is `2 * fees` higher than stoploss price |
| Same-candle order | **exit-signal → stoploss → ROI → trailing stoploss** |
| Exit-signal vs stop | exit-signal favored |
| Intra-candle trailing | high first adjusts stop; low uses adjusted stop; trail only if new stop remains below candle low |
| Custom exit / custom stoploss | **not defined** |
| JSON sidecars | **required** |

Under JSON, the **only** trading-rule difference is the funding entry
conjunct.

---

## 5. Exact funding-filter semantics

```text
endpoint           = /fapi/v1/fundingRate
symbol             = BTCUSDT USD-M perpetual
field              = fundingRate
timestamp          = fundingTime
join               = reindex onto 1h candle date (open), method=ffill
                     last fundingTime <= candle date
funding_3d         = rolling(72, min_periods=24).mean()
funding_pct        = rolling(24*180, min_periods=24*30).rank(pct=True) * 100
threshold          = 55
skip entry iff     = funding_pct >= 55
missing percentile = ALLOWS entry
filter scope       = entries only; exits unchanged
current-in-window  = YES
funding payments   = not in spot PnL
```

Filtered entry:

```text
crossed_above(close, ema)
AND volume > 0
AND (funding_pct < 55 OR funding_pct is NA)
```

```text
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

**Reproduction assumption (LEVEL_2 only):** a funding observation is
treated as historically available at its Binance `fundingTime`, matching
the pinned external implementation.

This is **not** evidence of actual zero publication latency. It does
**not** set `legal_available_at`. It does **not** resolve the B2-06
publication-timing blocker.

---

## 6. Gap and degenerate-row policy

```text
43 enumerated missing native hours:
  do NOT synthesize
  Freqtrade dataframe omits them
  crossed_* / EMA / funding join use present rows only

degenerate Vision row 2020-12-21T14:00:00Z
  close_time < open_time, volume = 0
  RETAIN unrepaired
  volume > 0 blocks entry
  close MAY enter the EMA and MAY trigger an exit cross
```

Do not repair, drop, interpolate, or reinterpret these after seeing
strategy behavior.

---

## 7. Primary metric and sign convention

MARKET-03 reproduces author `research/metrics.py` `Max drawdown`, **not**
Freqtrade "Absolute drawdown %".

```text
daily_equity = wallet groupby date sum(total_quote); resample("D").last().ffill()
r            = daily_equity.pct_change().dropna()
cum          = (1 + r).cumprod()
dd           = cum / cum.cummax() - 1
MDD          = float(dd.min())
```

```text
UNITS            = signed ratio
SIGN CONVENTION  = negative or zero
```

`MDD = -0.338` means a 33.8% peak-to-trough decline. Less negative is
smaller drawdown magnitude. Example for interpretation only:

```text
-0.338 > -0.494
```

means the filtered strategy has smaller drawdown magnitude.

Comparison uses these **signed** values. It is **not** rewritten as a
comparison of absolute values.

Warmup is excluded. Open trades, fees, compounding, and end-of-window
force-exits are included. Funding payments are not (spot).

---

## 8. Primary claim and classification

Primary claim:

> Under the frozen LEVEL_2 faithful reimplementation, does adding the
> published funding entry filter reduce historical maximum wallet
> drawdown relative to the corresponding EmaCross baseline over the
> frozen evaluation interval?

Author-reported headlines (descriptive reference only; produced on the
longer open-ended `20191001-` window):

```text
baseline MDD ≈ -49.4%     (ratio -0.494)
filtered MDD ≈ -33.8%     (ratio -0.338)
Δ = 15.6 percentage points
relative reduction ≈ 31.6%   (15.6 / 49.4)
```

Let `MDD_*` be the signed `metrics.py` ratio on `EVALUATION_INTERVAL`.

```text
REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline) and (MDD_filtered > MDD_baseline)
```

```text
if a fail-closed protocol condition in §11 fires:
    PRIMARY = EXECUTION_INVALID          # not a scientific claim
elif MDD_filtered or MDD_baseline is not finite:
    PRIMARY = EXECUTION_INCOMPLETE       # not a scientific claim
elif MDD_filtered > MDD_baseline:        # strict; signed; less negative
    PRIMARY = REPRODUCED_DIRECTION
else:                                    # equal or worse
    PRIMARY = NOT_REPRODUCED_DIRECTION
```

`REPRODUCED_DIRECTION` is the only successful primary label.
Equality is `NOT_REPRODUCED_DIRECTION`.

---

## 9. Magnitude and external fidelity (descriptive)

Magnitude fidelity is **DESCRIPTIVE ONLY**.

- No minimum magnitude threshold.
- No post-result promotion from magnitude.
- `"direction failed but return improved"` is **not** reproduction.

Report, do not gate:

```text
OBS_ABS_REDUCTION_PP = 100 * (MDD_filtered - MDD_baseline)
OBS_REL_REDUCTION    = (MDD_filtered - MDD_baseline) / abs(MDD_baseline)
                       if MDD_baseline != 0
```

External-fidelity diagnostics (cannot override primary classification):

- Signalbot baseline MDD vs author baseline MDD −0.494
- Signalbot filtered MDD vs author filtered MDD −0.338
- those differences in percentage points

Truncation confounds external fidelity. A directional success with
material headline mismatch must report both.

---

## 10. Secondary metrics (descriptive only)

From `metrics.py` (`PPY = 365`) plus the trade list:

- total return
- CAGR
- Sharpe
- Sortino
- trade count
- baseline MDD
- filtered MDD
- absolute MDD reduction
- relative MDD reduction
- external-author fidelity deltas

Secondary metrics **cannot** change primary classification. High return
plus failed MDD direction remains failure of the primary claim.

---

## 11. Fail-closed states

These **must not** silently become `NOT_REPRODUCED_DIRECTION`.

`EXECUTION_INVALID` if any of:

- wrong external source identity
- wrong spot snapshot
- missing or wrong funding snapshot
- funding outside frozen semantics
- protected OOS access
- strategy semantic mismatch
- unresolved Freqtrade semantic
- execution outside frozen interval
- unauthorized second canonical execution

`EXECUTION_INCOMPLETE` if:

- invalid or missing primary metric
- non-finite `MDD_baseline` or `MDD_filtered`

Neither is a scientific directional claim.

---

## 12. No p-value

MARKET-03 is a deterministic historical reproduction.

**Forbidden** as a promotion gate: bootstrap, permutation test,
confidence interval, p-value, MARKET-01/02 statistical machinery.

---

## 13. Claim boundaries

### If `REPRODUCED_DIRECTION`

Allowed, and no stronger:

> Under the frozen LEVEL_2 faithful reimplementation of the pinned
> external strategy, and under the explicit fundingTime availability
> assumption, the published funding filter reduced historical maximum
> wallet drawdown relative to the corresponding baseline over the
> Signalbot frozen reproduction interval.

**Forbidden:** current alpha; live profitability; causal funding effect;
independent replication; OOS confirmation; validation of the author's
strategy-selection pipeline; validation of the 42-strategy search;
calibrated statistical evidence; proven funding publication timing.

### If `NOT_REPRODUCED_DIRECTION`

Allowed:

> Signalbot's frozen LEVEL_2 faithful reimplementation did not
> reproduce the direction of the published drawdown-reduction claim
> over the frozen reproduction interval.

**Forbidden:** generalizing to "funding does not work."

---

## 14. Lifecycle (this unit)

```text
MARKET_03_PREREGISTERED             = YES
MARKET_03_ARMED                     = NO
MARKET_03_IMPLEMENTED               = NO
MARKET_03_STRATEGY_EXECUTED         = NO
MARKET_03_OUTCOMES_INSPECTED        = NO
MARKET_03_PARAMETER_SEARCH          = NO
CANONICAL_EXECUTIONS_AUTHORIZED     = 0
CANONICAL_EXECUTIONS_CONSUMED       = 0
PROTECTED_OOS_TOUCHED               = NO
FUNDING_SNAPSHOT_READY              = NO
B2_06_EXECUTION_AUTHORIZED          = NO
execution_authorized                = NO
```

This preregistration does **not** authorize execution or ARM.
Canonical executions authorized remains **zero**.

Next: freeze these bytes, then (later, not this unit) implementation of
the frozen contract. Implementation is not execution.
