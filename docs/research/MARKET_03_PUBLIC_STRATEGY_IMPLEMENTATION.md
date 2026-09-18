# MARKET-03 PUBLIC STRATEGY IMPLEMENTATION

- **Status:** `IMPLEMENTATION_COMPLETE_NOT_FROZEN`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION`
- **Date:** 2026-09-18
- **Machine-readable twin:** `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.json`

This unit implements the frozen MARKET-03 LEVEL_2 reproduction semantics.
It does **not** freeze the implementation, ARM, execute MARKET-03, inspect
real outcomes, or search parameters.

```text
IMPLEMENTATION_COMPLETE              = YES
IMPLEMENTATION_FROZEN                = NO
MARKET_03_ARMED                      = NO
CANONICAL_EXECUTIONS_AUTHORIZED      = 0
CANONICAL_EXECUTIONS_CONSUMED        = 0
MARKET_03_STRATEGY_EXECUTED          = NO
MARKET_03_OUTCOMES_INSPECTED         = NO
MARKET_03_PARAMETER_SEARCH           = NO
PROTECTED_OOS_TOUCHED                = NO
PREREG_CHANGED                       = NO
SPOT_SNAPSHOT_CHANGED                = NO
FUNDING_SNAPSHOT_CHANGED             = NO
```

Scientific authority remains the frozen prereg bytes. This file is an
implementation identity record, not a freeze and not a RESULT.

---

## 1. Frozen prereg (unchanged)

```text
PREREG_MD_SHA256   = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
```

---

## 2. Pinned external source

```text
EXTERNAL_REPO     = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_COMMIT   = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE     = f7717e681c911ea3ccce15492246053cf15883cb
FAMILY            = EmaCross vs EmaCrossFunding
REPLICATION_LEVEL = LEVEL_2_FAITHFUL_REIMPLEMENTATION
FREQTRADE_PIN     = 2026.7 documented backtesting / stoploss / IStrategy
INVENTORY         = docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/
```

JSON sidecars are required:

- `ema_period = 600`
- `exit_threshold = 2.0`
- `funding_max_pct = 55`

Class defaults (800 / 1.0 / 90) are **not** the published contrast.

---

## 3. Data authorities (bound, unused in this unit)

```text
SPOT_DATASET_ID    = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT_SNAPSHOT_ID   = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256   = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4

FUNDING_DATASET_ID = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
FUNDING_SNAPSHOT_ID= d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256= e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
FUNDING_ROWS       = 5819
FUNDING_TIME_BOUNDS= 2019-09-10T08:00:00Z .. 2024-12-31T16:00:00Z

B2-06 is not MARKET-03 funding authority.
```

Production execution against these snapshots is fail-closed in this unit
(`MARKET_03_BOUND_EXECUTION_AUTHORIZED = False`).

---

## 4. Temporal identity

```text
WARMUP_INTERVAL     = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
PROTECTED_OOS       = [2025-01-01T00:00:00Z, inf)  untouched
```

Warmup candles may form indicators only. No fill may use a candle whose
`open_time >= 2025-01-01T00:00:00Z`. An open trade at the authorized end
is `force_exit`ed on the last in-interval candle open, without reading
2025/2026 prices.

---

## 5. Implementation files

| File | Role | SHA256 |
|---|---|---|
| `scripts/research/market_03_public_strategy_lib.py` | Scientific core (indicators, funding, signals, sim, MDD, classification) | `46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5` |
| `scripts/research/market_03_public_strategy_authority.py` | Frozen identity + fail-closed bound-data guard | `97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4` |
| `scripts/research/market_03_public_strategy_execute.py` | Bound-execution stub (always refuses) | `90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf` |
| `tests/research/test_market_03_public_strategy_implementation.py` | Synthetic / fixture / handcrafted tests | recorded in JSON after the hash-lock test |

Scientific functions are separable from ARM, reservation, result
persistence, CLI execution, and bound dataset loading.

---

## 6. Fidelity method

`LEVEL_2_FAITHFUL_REIMPLEMENTATION`. Exact pinned source was the
implementation reference, not README prose.

### EXACT_DIFFERENTIAL_TESTS = PARTIAL

Executed against identical synthetic/fixture inputs:

1. **Genuine external differential:** qtpylib `crossed_above` vs the published Freqtrade test vector `[56,97,19,76,65,25,87,91,79,79]` vs `60`.
2. **Genuine external differential:** Funding alignment / ffill / 3-day mean / 180-day percentile vs an independently inlined copy of the pinned `EmaCrossFunding.py` pandas body.
3. **Genuine external differential:** `risk_report` MDD / return / CAGR / Sharpe / Sortino vs pinned `research/metrics.py` imported from the captured source tree.
4. **Tautological/shared-formula:** `crossed_below` vs the same qtpylib formula rewritten in the test.

Do **not** claim global exact differential fidelity. EMA and the trade engine remain semantic fixtures.

### SEMANTIC_FIXTURE_TESTS = YES

Encoded from pinned code + Freqtrade 2026.7 source/docs, not from a
live `talib`/`freqtrade` process (those packages are not installed):

1. TA-Lib EMA SMA-seed then `k=2/(n+1)` (C library not executed).
2. Trade engine: signal-on-close / fill-next-open, stoploss exact price,
   trailing high-first then low uses adjusted stop, same-candle order
   `exit_signal → stoploss → ROI → trailing`, max_open_trades=1, fee
   0.001/side twice, unlimited stake × 0.99, force_exit last open,
   no shorts.
3. Adversarial synthetic edges listed in the test file.

Do **not** claim exact differential fidelity where only the semantic
fixture was tested.

---

## 7. Known LEVEL_2 deviations

1. TA-Lib C `EMA` is reimplemented from the published SMA-seed algorithm;
   `talib` is not imported.
2. Freqtrade is not executed. The engine is a LEVEL_2 reimplementation of
   Freqtrade 2026.7 `backtesting.py` / `interface.py` / `trade_model.py`
   documented+source semantics.
3. Exchange `price_to_precision` / amount precision (`ROUND_UP` on long
   stops) is not applied (no Binance tick-size table in this unit).
4. Wallet captures follow Freqtrade 2026.7 spot `Wallets._update_dry` +
   `_capture_wallet`: USDT.total = start + closed `profit_abs` − open
   `stake_amount` (filled-spot `used_stake` is unfilled entry orders
   only, so tied-up stake is **not** inside USDT.total) plus BTC amount
   × candle open while a position is open. Capture is at candle open
   before that candle's orders. Force-exit does **not** append a second
   same-timestamp row. Tick-level `wallet.feather` identity vs a live
   Freqtrade process is not claimed because `freqtrade` is not executed.
5. Indicator input is restricted to `WARMUP_START_INCLUSIVE =
   2019-08-07T20:00:00Z` before EMA/funding/signals. Pre-warmup bound
   bars (spot starts 2019-08-01) are dropped, not used as SMA-seed.
6. `STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN`. Reproduction
   treats a funding observation as available at raw `fundingTime`
   (LEVEL_2 assumption only; not `legal_available_at`; does not resolve
   B2-06).

`fundingTime` milliseconds are preserved. They are not rounded.

---

## 8. Funding filter (pinned)

```text
join            = reindex onto 1h candle date (open), method=ffill
                  last fundingTime <= candle date (ms matter)
funding_3d      = rolling(72, min_periods=24).mean()
funding_pct     = rolling(24*180, min_periods=24*30).rank(pct=True)*100
current-in-window = YES
threshold       = 55
skip entry iff  = funding_pct >= 55
missing pct     = ALLOWS entry
filter scope    = entries only; exits unchanged
```

---

## 9. Primary classification (frozen)

Authoritative MDD is the signed `metrics.py` ratio
`float(dd.min())` on daily wallet equity.

```text
REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline)
                         and (MDD_filtered > MDD_baseline)
```

`abs(MDD)`, return, Sharpe, trade count, and magnitude fidelity cannot
override. Scientific errors are `EXECUTION_INVALID` or
`EXECUTION_INCOMPLETE`, never silently `NOT_REPRODUCED_DIRECTION`.

No bootstrap, p-values, optimization, or parameter sweep.

---

## 10. Fail-closed real-data access

`scripts/research/market_03_public_strategy_execute.py` always refuses.

`evaluate_market_03_reproduction` is the **synthetic/fixture** scientific
entry. `evaluate_canonical_market_03_reproduction` is the **canonical**
identity path: it requires exact prereg/source/snapshot/SHA/interval/gap
fields and then refuses execution while unarmed. It never loads bound
series.

Tests may use `synthetic` / `pinned_external_fixture` / `handcrafted`
only. They do not load the bound full spot or funding scientific
snapshots into strategy logic.

Repair record:
`docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR.md`.

---

## 11. Tests

```bash
python3 -m compileall -q .
python3 -m pytest -q tests/research/test_market_03_public_strategy_implementation.py
git diff --check
```

Focused MARKET-03 implementation tests: recorded in the twin JSON
after `python3 -m pytest -q tests/research/test_market_03_public_strategy_implementation.py`.

Full `python -m pytest -q` is **not** claimed as completed by this unit
if not run to finish.

---

## 12. Next (not this unit)

Implementation freeze, then ARM, then at most one canonical execution.
This unit authorizes none of those.
