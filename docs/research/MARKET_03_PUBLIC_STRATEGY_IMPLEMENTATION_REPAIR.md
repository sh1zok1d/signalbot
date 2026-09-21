# MARKET-03 PUBLIC STRATEGY IMPLEMENTATION REPAIR

- **Status:** `REPAIR_COMPLETE_NOT_FROZEN`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR`
- **Date:** 2026-09-18
- **Machine-readable twin:** `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR.json`

Outcome-blind repair of red-team verdict `B. REPAIR_REQUIRED`. Does **not**
freeze, ARM, execute MARKET-03, inspect real outcomes, or search
parameters.

```text
PRE_REPAIR_HEAD  = cada1bef4d2852ef07b2b4868cbb3b1ab42769e0
PRE_REPAIR_TREE  = 95a6f7deb2c97a5f0c38026ea93b3456114169dd
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

---

## Frozen authorities (unchanged)

```text
PREREG_MD_SHA256     = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256   = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
EXTERNAL_COMMIT      = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE        = f7717e681c911ea3ccce15492246053cf15883cb
SPOT_SNAPSHOT_ID     = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256     = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4
FUNDING_SNAPSHOT_ID  = d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256  = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
```

---

## Scientific-change map

| Finding | File | Function |
|---|---|---|
| F1 | `scripts/research/market_03_public_strategy_lib.py` | `simulate_strategy` (removed extra force-exit capture) |
| F3 | same | `freqtrade_2026_7_wallet_points`, `_capture`, `realized_closed_profit_abs` |
| F2 | same | `restrict_candles_to_indicator_origin`, `require_frozen_indicator_origin_coverage`, `populate_indicators` |
| F5 | `scripts/research/market_03_public_strategy_authority.py` | `bind_canonical_scientific_identity`, `refuse_unarmed_canonical_execution` |
| F5 | `scripts/research/market_03_public_strategy_lib.py` | `evaluate_canonical_market_03_reproduction` |
| F5 | `scripts/research/market_03_public_strategy_execute.py` | `execute_bound_market_03` |
| F4 | implementation + repair records | `EXACT_DIFFERENTIAL_TESTS = PARTIAL` |

No parameter, metric, or success-criterion changes.

---

## F1 — terminal force-exit double count

**Root cause:** After `force_exit`, the simulator appended a second USDT
row at the **same** last-candle timestamp as the already-captured
open-position wallet. Author/Freqtrade aggregation is
`groupby(date).sum(total_quote)`, so those rows added and approximately
doubled terminal daily equity.

**Pinned semantics:** Freqtrade 2026.7 `handle_left_open` updates live
wallets after force-exit and does **not** append another
`wallet_captures` row. The last capture remains the pre-force-exit
open-position state taken at last-candle open, before that candle's
orders.

**Repair:** Remove the extra `_capture` after force-exit. The trade is
still closed for the trade list (`exit_reason=force_exit`). Wallet
lifecycle is not patched by subtracting terminal equity or blindly
deduplicating timestamps.

**Regression:** `test_f1_force_exit_does_not_double_terminal_equity`
(one USDT row at last ts; filled-spot equity 10000 under F3 composition,
not 19900 and not ~19970). `test_f1_declining_open_position_has_no_fake_final_recovery`
(last day continues the decline).

---

## F2 — frozen warmup / startup boundary

**Root cause:** Bound spot begins `2019-08-01T00:00:00Z`. Frozen
indicator origin / `startup_candle_count=1300` warmup begins
`2019-08-07T20:00:00Z`. EMA was computed on whatever frame was passed,
so 164 extra pre-warmup bars could SMA-seed TA-Lib EMA.

**Repair:** `restrict_candles_to_indicator_origin` drops `date <
WARMUP_START_INCLUSIVE` **before** EMA, funding rolls, and signals.
No compute-then-slice. Canonical identity additionally requires the
frozen warmup string and refuses a different origin.
`require_frozen_indicator_origin_coverage` fails if the first remaining
bar is not exactly warmup start (canonical coverage).

Synthetic short frames that start after warmup are unchanged (nothing
to drop). Missing post-slice rows raise `MARKET_03_INDICATOR_ORIGIN_EMPTY`.

**Regression:** `test_f2_pre_warmup_history_cannot_change_canonical_ema_or_signals`.

---

## F3 — wallet composition vs Freqtrade 2026.7

**Root cause:** Captures used leftover free USDT after `stake + entry
fee`, plus BTC mark-to-market. Author `results.py` consumes Freqtrade
`wallet.feather` rows produced by `_capture_wallet(currency, price,
get_total(currency))`.

**Pinned identity (independently re-checked against Freqtrade 2026.7
`Wallets._update_dry` + `Backtesting._capture_wallet` +
`handle_left_open`; MARKET-03 config is `trading_mode=spot`):**

```text
tot_profit    = closed profit_abs (+ open realized_profit; 0 without partials)
tot_in_trades = open trade.stake_amount
used_stake    = unfilled *entry* order stakes   (0 once filled on spot)
USDT.total    = start_cap + tot_profit - tot_in_trades + used_stake
              = start_cap + tot_profit - open stake_amount
BTC.total     = trade.amount          (omitted if no position / total==0)
BTC.price     = candle open
equity_at_ts  = USDT.total + BTC.total * BTC.price
```

The futures branch assigns `used_stake = tot_in_trades`, which would
put tied-up stake back into `USDT.total`. That is **not** MARKET-03.

USDT.total is **not** leftover cash after the entry fee (fees enter
`tot_profit` only when the trade closes). It is also **not**
`start + profit` with stake still inside the USDT total.

Capture happens at candle open **before** that candle's orders. Same-
candle exits therefore still show the pre-exit open-position
composition at that timestamp. The next candle shows updated
USDT.total and no BTC.

**Repair:** `freqtrade_2026_7_wallet_points` is the sole capture
constructor. `_capture` appends that object once per timestamp.

**Regression:** `test_f3_wallet_composition_no_position_after_entry_profit_loss_close_force_exit`
and `test_f3_simulate_matches_independent_freqtrade_wallet_formula_on_open_and_close`.

---

## F5 — canonical authority fail-closed

Synthetic `evaluate_market_03_reproduction` remains for fixtures.

Canonical `evaluate_canonical_market_03_reproduction` requires exact:

- prereg MD/JSON bytes
- external commit/tree
- spot dataset/snapshot/data SHA
- funding dataset/snapshot/data SHA
- warmup start
- evaluation start/end
- spot gap count 43
- degenerate row `2020-12-21T14:00:00Z`

then refuses execution while unarmed. Missing fields, B2-06, wrong
interval, wrong SHA, and injected series all fail closed. Row count
and `origin="synthetic"` are not scientific authority on this path.

---

## F4 — differential label

`EXACT_DIFFERENTIAL_TESTS = PARTIAL`

Genuine: Freqtrade `crossed_above` vector; independent funding pandas
copy; imported `metrics.py`.

Tautological: `crossed_below` shared formula.

Semantic fixture: EMA C library and live Freqtrade engine.

---

## F6 — input policy

Unchanged. Canonical identity binds snapshot `2ce1f504…`, which is the
frozen object containing 43 omitted native hours and retained
`2020-12-21T14:00:00Z`. Scientific preprocessing does not interpolate
or drop that row.

---

## Remaining LEVEL_2 deviations

- TA-Lib C `EMA` not executed; SMA-seed reimplemented
- `freqtrade` package not executed
- exchange tick/amount precision not applied
- `STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN`

The withdrawn deviation “extra terminal wallet capture after
force-exit” is no longer claimed.

---

## Blindness

Bound MARKET-03 OHLCV/funding were not loaded into `simulate_strategy`
or `evaluate_market_03_reproduction`. No real trades, return, MDD,
baseline/filtered comparison, or parameter search.
