# MARKET-03 PUBLIC STRATEGY REPLICATION — preregistration design

- **Status:** `PREREG_DESIGN_COMPLETE_NOT_PREREGISTERED`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN`
- **Date:** 2026-09-18
- **Prior units:** source feasibility (`DATA_ACQUISITION_REQUIRED`); data
  acquisition (`READY_FOR_MARKET_03_PREREG_DESIGN`)
- **This unit writes:** design only. It does **not** write the final prereg,
  implement, ARM, or execute.

This unit freezes the scientific identity and success/failure classification
of MARKET-03 **before** any strategy execution.

It is **not** the live preregistration. A later unit may write
`MARKET_03_PUBLIC_STRATEGY_PREREG.md` from this design. That file does not
exist yet.

Machine-readable twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.json`
(SHA256 `91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57`).

```text
MARKET_03_STRATEGY_EXECUTED     = NO
MARKET_03_OUTCOMES_INSPECTED    = NO
MARKET_03_PARAMETER_SEARCH      = NO
MARKET_03_PREREGISTERED         = NO
MARKET_03_ARMED                 = NO
PROTECTED_OOS_TOUCHED           = NO
```

---

## 1. What MARKET-03 is

MARKET-03 is **EXTERNAL HISTORICAL CLAIM REPRODUCTION**.

It is **not**:

- an independent forward replication
- untouched OOS confirmation
- proof of live alpha
- proof of profitability
- proof of a causal funding effect
- validation of the author's full research pipeline

The external strategy was published after substantial exploratory selection.
The author examined 42 public strategies, EMA/exit variants, funding
thresholds, and cross-asset behavior. MARKET-03 preserves the distinction:

| Track | Question | MARKET-03 |
|---|---|---|
| A | Reproduce the final published strategy claim | **YES — this study** |
| B | Validate the strategy-selection process | **NO** |

Parameters `EMA=600`, `exit=2%`, `funding_max_pct=55`, and BTC-only focus
were selected after the author's benchmark, sweeps, and asset comparison.
They were not independently preregistered before that research. MARKET-03
must not later describe them as if they were.

Replication ceiling remains:

```text
LEVEL_2_FAITHFUL_REIMPLEMENTATION
```

Not `LEVEL_1_EXACT_REPRODUCTION` (funding publication latency unproven;
Freqtrade unpinned above `>=2026.7`; Vision spot archive is not the author's
ccxt download). Not `LEVEL_3` perpetual-price substitution.

MARKET-01 `NO_EVIDENCE` and MARKET-02 `NO_EVIDENCE` do not alter these
semantics. MARKET-03 is not a rescue experiment for those studies and is
not confirmation of Signalbot OI hypotheses.

---

## 2. Pinned external source

Selected family and commit are **permanently fixed**. This unit does not
replace them.

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
```

Inventory: `docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/`.

JSON sidecars **must** be loaded. Class defaults are **not** the published
contrast (`EmaCross` class EMA 800 / exit 1.0 vs JSON EMA 600 / exit 2.0;
`EmaCrossFunding` class `funding_max_pct` 90 vs JSON 55).

---

## 3. Target period, warmup, evaluation

### 3.1 Author headline timerange

The source reproduce command is:

```bash
.venv/bin/freqtrade backtesting -c config.json -s EmaCrossFunding \
  --timeframe 1h --timerange 20191001- --fee 0.001
```

Freqtrade `20191001-` is **open-ended**: from `2019-10-01` through the last
candle in the author's local data. It is not a closed interval through
`2024-12-31`.

Implied author terminal from the pinned source/results (not from Signalbot
outcomes):

| Evidence | Terminal implication |
|---|---|
| Bundled `funding.feather` last row | `2026-08-21T16:00:00.001Z` |
| `walk_forward_fast.py` `END` | `2026-08-01` |
| Repository publication | `2026-08-22` |
| Headline CAGR 50.9% on +1,604% | `(1+16.04)^(1/y)-1 = 0.509` ⇒ `y ≈ 6.89` years from 2019-10-01 ≈ **2026-08** |

The author's headline evaluation therefore extends into calendar 2025 and
2026.

### 3.2 Protected-OOS conflict — surfaced, not opened

Signalbot protected 2025 validation / 2026 OOS begins at
`2025-01-01T00:00:00Z`. The author headline **overlaps** that window.

```text
HEADLINE_OVERLAPS_PROTECTED_OOS = YES
RESOLUTION = TRUNCATE_TO_AUTHORIZED_INTERVAL
PROTECTED_OOS_OPENED            = NO
```

This unit does **not** open protected OOS. It does **not** treat the
author's 2025/2026 walk-forward CSV as a Signalbot OOS authorization.

### 3.3 Frozen intervals

```text
WARMUP_INTERVAL      = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL  = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

`WARMUP_INTERVAL` is `startup_candle_count = 1300` hours immediately before
the headline start. Warmup candles may be used only to form indicators
(EMA, funding rolling windows). They **must not** contribute to performance
metrics.

The spot snapshot also contains `[2019-08-01T00:00:00Z, 2019-08-07T20:00:00Z)`
as extra pre-warmup buffer so 1300 **present rows** can be loaded even if
warmup contains gaps. That extra buffer is not an evaluation period.

No fill may use a candle whose `open_time >= 2025-01-01T00:00:00Z`. An open
trade at the authorized end is `force_exit`ed on the last in-interval candle
only (Freqtrade end-of-backtest), without reading 2025/2026 prices. A signal
on `2024-12-31T23:00:00Z` cannot fill at the next open.

### 3.4 Coverage mismatch (explicit)

| Item | External original | Signalbot reproduction |
|---|---|---|
| Price download start | `20180101-` (ccxt/Freqtrade) | Vision spot 1h from `2019-08-01` |
| Headline start | `2019-10-01` | `2019-10-01` (matched) |
| Headline end | open-ended ≈ 2026-08 | truncated `2025-01-01` exclusive |
| Funding end | `2026-08-21` | REST through `2024-12-31T16:00:00Z` |
| Gap set | author's `data_scrub` WARN, unknown exact holes | **43** enumerated native hours missing |
| Degenerate row | unknown in ccxt download | Vision `2020-12-21T14:00:00Z` retained |

Do **not** silently treat Signalbot data through `2024-12-31` as the author's
headline evaluation. Author-reported `49.4%` / `33.8%` were produced on the
**longer** open-ended window. Absolute match to those headlines is
confounded by truncation.

---

## 4. Frozen strategy semantics

`BASELINE = EmaCross` and `FILTERED = EmaCrossFunding` under shipped JSON.

Engine pin for LEVEL_2: **Freqtrade 2026.7 documented defaults**, not an
invented Signalbot fill model and not an unstated later Freqtrade minor.

### 4.1 Market, indicators, signals

| Item | Frozen value |
|---|---|
| Exchange / pair | Binance `BTC/USDT` |
| Market type | **SPOT** |
| Timeframe | `1h` |
| EMA | TA-Lib `EMA(close, 600)` |
| Exit level | `ema * (100 - 2.0) / 100` (2% below EMA) |
| Entry | `crossed_above(close, ema) AND volume > 0` |
| Exit | `crossed_below(close, ema_exit)` |
| Shorts | disabled (`can_short = False`) |
| `crossed_*` | prior present-row not-across AND current-row across; **not** prior calendar hour if that hour is missing |

### 4.2 Risk, sizing, compounding

| Item | Frozen value |
|---|---|
| Stoploss | `-0.15` |
| Trailing | `trailing_stop = True` |
| `trailing_stop_positive` | `None` (unset in strategy; JSON `"trailing": {}`; IStrategy 2026.7 default) |
| `trailing_stop_positive_offset` | `0.0` |
| `trailing_only_offset_is_reached` | `False` |
| Trailing behavior | trail the **−15%** stop from the highest observed price; **no** tighter positive trail |
| ROI | `minimal_roi = {"0": 10}` (1000%; effectively inactive) |
| Max open trades | `1` |
| Pyramiding / position adjust | none |
| Stake | `"unlimited"` |
| `tradable_balance_ratio` | `0.99` |
| Initial capital | `dry_run_wallet = 10000` USDT |
| Compounding | **yes** (unlimited stake, 99% of wallet, one slot) |
| Fee | `0.001` per side, applied on entry and exit |
| Slippage | none if requested price inside candle high/low |
| `--timeframe-detail` | **not used** |
| Protections | **disabled** |

### 4.3 Timing, orders, fills (Freqtrade 2026.7 backtesting)

| Item | Frozen value |
|---|---|
| `startup_candle_count` | `1300` |
| `process_only_new_candles` | `True` |
| Interface | v3 |
| `use_exit_signal` | `True` (2026.7 default; omitted in source/config) |
| `exit_profit_only` | `False` |
| `ignore_roi_if_entry_signal` | `False` |
| Order types | entry/exit/stoploss `limit`; `stoploss_on_exchange = False` |
| TIF | `GTC` |
| Live `use_order_book` | **ignored in backtest** |
| Entry signal | candle **close** |
| Exit signal | candle **close** |
| Entry fill | **open of the next candle** |
| Exit-signal fill | **open of the next candle** |
| Stoploss fill | exactly at stoploss price even if `low` was lower; loss is `2 * fees` higher than the stoploss price |
| Same-candle order | **exit-signal → stoploss → ROI → trailing stoploss** |
| Exit-signal vs stop | exit-signal is favored (assumed to trigger on candle open) |
| Intra-candle trailing | high first (adjust stop); low uses adjusted stop; trail only if the new stop remains below the candle low |
| Custom exit / custom stoploss | **not defined** |

These are documented Freqtrade 2026.7 assumptions, not approximations of
undocumented internals. Remaining LEVEL_2 mismatches (current vs historic
exchange precision/limits; Freqtrade minor above 2026.7) are recorded in
§18 and are not unpinned strategy rules.

---

## 5. Frozen funding filter

`EmaCrossFunding` only. Under JSON, this is the **only** trading-rule
difference versus `EmaCross`.

```text
funding source     = REST GET /fapi/v1/fundingRate
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
current-in-window  = YES; current funding_3d enters its own percentile
funding payments   = not in spot PnL
```

Entry (filtered):

```text
crossed_above(close, ema)
AND volume > 0
AND (funding_pct < 55 OR funding_pct is NA)
```

### Reproduction assumption (named, not proven)

```text
REPRODUCTION_ASSUMPTION:
For purposes of reproducing the pinned external implementation,
a funding observation is treated as available at fundingTime.

STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

This assumption does **not** establish actual historical zero-latency
availability, does not set `legal_available_at`, and does not solve the
B2-06 publication-timing blocker.

---

## 6. Primary external claim

The primary claim to reproduce is **drawdown reduction**, not return
improvement.

Author-reported headline values (README after commit `45b6559`, pinned
HEAD):

```text
EmaCross          MDD ≈ 49.4%     (signed −49.4%)
EmaCrossFunding   MDD ≈ 33.8%     (signed −33.8%)
```

Verified arithmetic on those reported figures:

```text
49.4 − 33.8 = 15.6 percentage points
15.6 / 49.4 = 0.3157894736842105 ≈ 31.6% relative reduction
```

Do not silently redefine the primary claim as return improvement
(`+1,353%` → `+1,604%`). The author prose is that the funding rule "buys
drawdown, not return."

Those headlines were produced on the author's **open-ended** `20191001-`
window. They are the external reference for fidelity reporting. They are
**not** a binary magnitude gate on the truncated authorized interval.

---

## 7. Drawdown metric

Prefer the pinned Freqtrade-adjacent author metric, not a new
Signalbot-specific MDD.

Freqtrade summary "Absolute drawdown (x%)" is a **different** quantity
(largest currency drawdown's contemporaneous percent). The author states
Freqtrade prints `−23.6%` where `metrics.py` gives `−33.8%`. MARKET-03
reproduces **`research/metrics.py` `Max drawdown`**.

Frozen definition:

```text
wallet equity at each Freqtrade wallet timestamp
  = sum(total_quote) across currencies
  = USDT cash + mark-to-market quote value of the open BTC position
daily equity     = resample("D").last().ffill()
returns r        = daily_equity.pct_change()
risk_report      = dropna(r)
cum              = (1 + r).cumprod()
drawdown         = cum / cum.cummax() - 1
Max drawdown     = float(dd.min())     # signed negative ratio
```

| Piece | Frozen handling |
|---|---|
| Initial capital | `10000` USDT (compounding from this wallet) |
| Open trades | included via `total_quote` |
| Fees | inside the wallet path (`--fee 0.001`) |
| Funding payments | not present (spot) |
| Peak / trough | running peak of `cum`; trough is the minimum of `cum/cummax - 1` |
| Denominator | the running peak of `cum` |
| Warmup | excluded (metrics start at `EVALUATION_INTERVAL`) |
| End-of-window force-exit | included in the wallet path |
| Precision | full float comparison for classification; author headlines are 1 decimal percent |

LEVEL_2 equivalent reconstruction (if Freqtrade is not executed as the
engine) must produce the same wallet→daily→`risk_report` object, not a
different peak-trough on intra-day marks or on closed-trade-only equity.

This identity is reconstructed from pinned `results.py` + `metrics.py`.
It is sufficient to preregister. It is **not** an observed Signalbot MDD.

---

## 8. Primary classification (frozen before execution)

Do **not** treat `filtered_MDD < baseline_MDD` as reproduction of the
author's **magnitude**. A microscopic reduction is directional only.

No defensible binary magnitude tolerance exists:

1. author values are rounded to 0.1 percentage point;
2. the authorized interval is truncated versus the author's ~2019-10→2026-08
   headline (material missing path, including 2025–2026);
3. LEVEL_2 data/engine differences remain (Vision vs ccxt, 43 gaps,
   degenerate row, unpinned Freqtrade minor);
4. inventing ±X percentage points would be a fake gate.

Therefore the **primary** classification is directional. Magnitude
fidelity is a **frozen descriptive measure**, not a pass/fail threshold.

Let `MDD_*` be the signed `metrics.py` ratio on `EVALUATION_INTERVAL`.

```text
if MDD_filtered or MDD_baseline is not finite:
    PRIMARY = EXECUTION_INCOMPLETE     # fail closed; not a claim
elif MDD_filtered > MDD_baseline:      # strict; less negative
    PRIMARY = REPRODUCED_DIRECTION
else:                                  # equal or worse
    PRIMARY = NOT_REPRODUCED_DIRECTION
```

Equality is `NOT_REPRODUCED_DIRECTION` because the published claim is
**reduction**, not "no worse."

`REPRODUCED_DIRECTION` is the only successful primary label.
`NOT_REPRODUCED_DIRECTION` is failure of the primary external claim.
Secondary metrics cannot override that.

### Magnitude fidelity (descriptive)

Report, do not gate:

```text
OBS_ABS_REDUCTION_PP = 100 * (MDD_filtered - MDD_baseline)
OBS_REL_REDUCTION    = (MDD_filtered - MDD_baseline) / abs(MDD_baseline)
                       if MDD_baseline != 0
ABS_PP_ERROR         = OBS_ABS_REDUCTION_PP - 15.6
REL_ERROR            = OBS_REL_REDUCTION - 0.3157894736842105
```

Reference author reduction: **15.6 percentage points**, **≈31.6%** relative.

---

## 9. Internal contrast vs external fidelity

Two comparisons are mandatory and must not be collapsed.

**A. INTERNAL CONTRAST** (primary)

`MDD(EmaCrossFunding)` vs `MDD(EmaCross)` on the frozen reimplementation
and authorized interval. This is `REPRODUCED_DIRECTION` /
`NOT_REPRODUCED_DIRECTION`.

**B. EXTERNAL FIDELITY** (always reported)

Signalbot-reimplemented metrics vs author-reported headlines
(`EmaCross` MDD −49.4%, `EmaCrossFunding` MDD −33.8%, and the secondary
headline table). Truncation **confounds** this comparison. A mismatch
must be reported as such. It must not be hidden behind a successful
internal direction.

Frozen reporting template:

> If direction reproduces while absolute MDDs differ materially from
> −49.4% / −33.8%, report `REPRODUCED_DIRECTION` on the truncated
> authorized interval **and** report the external-fidelity errors.
> Do not claim that Signalbot matched the author's headline magnitudes.

---

## 10. Secondary metrics (descriptive only)

Faithfully available from `metrics.py` plus the trade list:

| Metric | Source |
|---|---|
| Total return | `cum.iloc[-1] - 1` |
| CAGR | `cum.iloc[-1] ** (365 / n) - 1` |
| Sharpe | `r.mean() / r.std() * sqrt(365)` |
| Sortino | `r.mean() / downside.std() * sqrt(365)` |
| Trade count | length of the trade list (including force-exits) |
| Baseline MDD / filtered MDD | §7 |
| Absolute / relative MDD reduction | §8 |

`PPY = 365` as in pinned `metrics.py`.

These **must not** become alternate success criteria after execution.
High return plus failed MDD direction remains failure of the primary
external claim.

---

## 11. Gap and degenerate-row policy

Frozen **now**, without strategy outcomes. Priority: faithful native-data
reproduction of the Vision spot archive, matching Freqtrade's native
dataframe (missing hours are absent rows; they are not synthesized).

Author `data_scrub.py` **WARNs** on gaps and stale `volume=0` / `open==close`
candles and still marks data "ready for backtest". It does not drop those
rows. MARKET-03 does not repair after seeing results.

```text
43 enumerated missing native hours:
  do NOT synthesize
  Freqtrade dataframe simply omits them
  crossed_* / EMA / funding join use present rows only
  this creates a discontinuity in calendar time, not a filled bar

degenerate Vision row 2020-12-21T14:00:00Z
  close_time < open_time, volume = 0
  RETAIN unrepaired
  volume > 0 blocks entry
  close MAY still enter the EMA and MAY trigger an exit cross
  (exit has no volume check)
```

No post-hoc drop, fill, or OHLC repair is authorized.

---

## 12. Funding dataset authority (ARM bind)

B2-06 remains unauthorized. Historical REST/Vision overlap equivalence
does **not** make B2-06 MARKET-03 authority.

**Spot (already materialized; bind at ARM):**

```text
DATASET_ID  = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SNAPSHOT_ID = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
```

Currently `research_authorized = false` /
`market_03_scientifically_bound = false`. ARM would bind it. This design
does not bind it.

**Funding (required dedicated snapshot, not yet named as an identity):**

ARM must bind a dedicated MARKET-03 REST funding snapshot, **not** B2-06
and **not** the author's bundled `funding.feather` (that file extends into
protected 2025/2026).

```text
PROPOSED_DATASET_ID = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
SOURCE              = REST GET /fapi/v1/fundingRate
FIELD               = fundingRate at fundingTime
ACQUIRED_JSONL_SHA256
  = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
ROWS                = 5819
BOUNDS              = [2019-09-01 request, 2025-01-01)
OBSERVED            = 2019-09-10T08:00:00Z .. 2024-12-31T16:00:00Z
NAMED_SNAPSHOT      = NOT YET MATERIALIZED
REQUIRED_BEFORE_ARM = YES
```

Bytes already exist from the acquisition unit. What ARM needs is an
immutable named snapshot identity wrapping those bytes. Creating that
identity is **not** this unit and is **not** a reason to execute the
strategy.

---

## 13. No statistical p-value theater

MARKET-03 is historical reproduction of a **deterministic** published
strategy claim on one frozen path.

It does **not** import MARKET-01/02 bootstrap machinery. It does not
create a p-value because previous MARKET studies had one.

Statistical inference is **not** scientifically warranted here: there is
no sampling model, no two-group estimand, and no confirmatory OOS trial.
Classification is the deterministic rule in §8.

---

## 14. Claim boundaries

### If `REPRODUCED_DIRECTION`

Allowed claim, and no stronger:

> Under the frozen LEVEL_2 faithful reimplementation of the pinned
> external strategy and its explicit fundingTime availability assumption,
> adding the published funding filter reduced historical maximum
> drawdown relative to the corresponding baseline over the frozen
> reproduction interval.

It must **not** imply: live profitability; current alpha; causal funding
effect; independent replication; OOS confirmation; validation of the
author's parameter selection; calibrated statistical evidence; proven
funding publication timing; independent confirmation of Signalbot OI
hypotheses; or rescue of MARKET-01/02.

### If `NOT_REPRODUCED_DIRECTION`

Allowed claim:

> Signalbot's frozen faithful reimplementation did not reproduce the
> direction of the published drawdown-reduction claim.

It must **not** be generalized to "funding filters do not work."

---

## 15. Protected OOS policy

```text
PROTECTED_2025_2026_OOS = UNTOUCHED
MARKET_03_MUST_NOT_CONSUME_IT
```

The external headline **does** extend into that period. The conflict is
surfaced in §3.2. The frozen scientific window **stops** at
`2025-01-01T00:00:00Z`. Do not "complete" the author's headline by
opening OOS.

---

## 16. Required design contents (index)

| Required item | Where |
|---|---|
| Pinned external source identity | §2 |
| Source selection history | §1 |
| Replication level | §1 |
| Exact strategy semantics | §4 |
| Exact funding semantics | §5 |
| fundingTime assumption | §5 |
| Evaluation / warmup intervals | §3 |
| Execution semantics | §4.3 |
| Gap / degenerate-row policy | §11 |
| Funding dataset authority | §12 |
| Exact MDD definition | §7 |
| Primary external claim | §6 |
| Primary classification rule | §8 |
| Magnitude-fidelity reporting | §8 |
| External-fidelity reporting | §9 |
| Secondary metrics | §10 |
| Claim boundaries | §14 |
| Protected-OOS policy | §3.2, §15 |
| Unresolved blockers | §18 |

---

## 17. Design verdict

Exactly one label:

**A. READY_FOR_MARKET_03_PREREG**

```text
DESIGN_VERDICT = READY_FOR_MARKET_03_PREREG
```

Strategy semantics, funding filter, MDD identity, directional
classification, truncated authorized interval, gap policy, and ARM-time
funding-snapshot requirement are specified without executing the
strategy.

Not B: trailing defaults, next-open fills, same-candle order, and the
author `metrics.py` MDD are reconstructed from the pinned source plus
Freqtrade 2026.7 documentation. They are no longer unpinned strategy
rules.

Not C: spot snapshot `2ce1f504…` exists; REST funding bytes
`e7885cd5…` exist. The remaining funding **identity** wrap is a pre-ARM
requirement, not a missing acquisition.

Not D: the object of study remains this public family on LEVEL_2.

This unit does **not** write the final preregistration.

---

## 18. Unresolved blockers (later units; not this verdict)

1. Dedicated REST funding snapshot identity
   `MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0` is **required before
   ARM**. JSONL sha256 already acquired.
2. Spot snapshot is not yet scientifically bound; ARM binds
   `MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0` / `2ce1f504…`.
3. `freqtrade>=2026.7` has no upper bound. LEVEL_2 freezes 2026.7
   documented semantics.
4. `STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN` remains.
5. Authorized evaluation is truncated versus the author headline. Frozen
   mismatch, not a reason to open OOS.
6. Author ccxt gap set versus Vision's 43 gaps and the degenerate
   `2020-12-21T14:00:00Z` row may differ.

---

## 19. Outcome-blindness statement

This unit did **not** compute any Signalbot MARKET-03 scientific outcome.

| Quantity | Computed? |
|---|---|
| EmaCross execution | **NO** |
| EmaCrossFunding execution | **NO** |
| Strategy trades | **NO** |
| Strategy returns | **NO** |
| Drawdown | **NO** |
| Sharpe / Sortino | **NO** |
| Parameter sensitivity | **NO** |
| Protected 2025/2026 OOS inspection | **NO** |

Author-reported numbers were read from the pinned README only.
Arithmetic in §6 is on those reported figures.

```text
MARKET_03_STRATEGY_EXECUTED     = NO
MARKET_03_OUTCOMES_INSPECTED    = NO
MARKET_03_PARAMETER_SEARCH      = NO
MARKET_03_PREREGISTERED         = NO
MARKET_03_ARMED                 = NO
PROTECTED_OOS_TOUCHED           = NO
```

STOP after prereg **design**. Do not implement. Do not ARM. Do not execute.
