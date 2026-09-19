# MARKET-03 PUBLIC STRATEGY REPLICATION — source capture + outcome-blind feasibility

- **Status:** `OUTCOME_BLIND_SOURCE_FEASIBILITY`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET-03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY`
- **Date:** 2026-09-18
- **Signalbot inspected HEAD:** `7e39c3c763e239ee09a601d764066e89cb0f9eb7`
- **Signalbot inspected tree:** `4fe44daaa362fd4caa02fe40b0720a960365441e`
- **Outcome inspection:** **NO**
- **Prereg created:** **NO**
- **MARKET-03 ARM:** **NO**
- **MARKET-03 executed:** **NO**
- **RESULT created:** **NO**
- **Protected 2025/2026 OOS opened:** **NO**
- **B2-06 execution authorized:** **NO**

This unit captures one already-selected public strategy family and determines
what can be reproduced faithfully from source. It does **not** preregister,
implement, ARM, execute, backtest, optimize, or inspect Signalbot MARKET-03
outcomes.

Selected family: `EmaCross` vs `EmaCrossFunding` from
`https://github.com/wiktorj137/btc-strategy-lab`.

The source was selected **before** this unit. This unit does not replace it.
If faithful reproduction is impossible, the outcome is `MARKET_03_NOT_FEASIBLE`
or a data-acquisition/source-review verdict — not a new strategy.

Machine-readable twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.json`.

Pinned source inventory:
`docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/`.

JSON twin SHA256:
`471c5318a02b4079a4a3b562f047d54d39f54f09332378a665c3b9144cb0d2f8`.

---

## 1. Selected external source

```text
EXTERNAL_REPO   = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_AUTHOR = wiktorj137
LICENSE         = GPL-3.0 (Freqtrade inheritance); EmaCross logic derived
                  from Paul Csapak EMAPriceCrossoverWithThreshold (MIT)
DEFAULT_BRANCH  = main
TAGS            = none
```

This is an EXTERNAL PUBLIC STRATEGY REPLICATION / VALIDATION study object.
It is not a Signalbot-invented setup family.

---

## 2. Exact external commit

Resolved by cloning the public repository and reading `origin/main` HEAD.
Authority is this commit object, not moving HEAD.

```text
EXTERNAL_COMMIT_SHA            = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_COMMIT_TREE           = f7717e681c911ea3ccce15492246053cf15883cb
EXTERNAL_COMMIT_SUBJECT        = Publish three more negative results: order flow, crowd positioning, EMA ensemble
EXTERNAL_COMMITTER_DATE        = 2026-08-22T05:18:19+02:00
CAPTURE_TIMESTAMP_UTC          = 2026-09-18T16:46:53Z
N_COMMITS_ON_MAIN              = 19
FIRST_COMMIT_SHA               = 0a3f134a09c468be0525bfaca57e71c6e683faf5
FIRST_COMMIT_DATE              = 2026-08-22T00:09:34+02:00
```

All published commits on `main` are timestamped 2026-08-22. The repository
did not exist as a public git history before that calendar day.

`EmaCross.py` and `EmaCrossFunding.py` at HEAD are byte-identical to the
first commit. `EmaCross.json` was pretty-printed/restored later; parameter
values `ema_period=600`, `exit_threshold=2.0` were already present at the
first commit.

---

## 3. External source file hashes

Complete inventory: `docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/SOURCE_INVENTORY.json`.

Scientifically material files at the pinned commit:

| path | SHA256 | size |
|---|---|---|
| `user_data/strategies/EmaCross.py` | `387cf39f58d266bb63d06865a0784bc2e08676edf54f4610c7d7709bb2a95f24` | 2183 |
| `user_data/strategies/EmaCross.json` | `9209a90e5092216af166fd10b9e7415690ab16af0fb3010c7e94e162c027e3ee` | 168 |
| `user_data/strategies/EmaCrossFunding.py` | `0f0d3d4677647da2e11d4dc8195adbb95fce201ce400300df0a78741cf9a9564` | 3366 |
| `user_data/strategies/EmaCrossFunding.json` | `1641ce3122ccc0c216aaae1af77bedb15dd77670643201d1c7453066eca38f0b` | 198 |
| `config.json` | `a20cfbf8c9efa36b06f336ef772e8be905e9c236b6f7bed38a4a0a810879ecda` | 1236 |
| `README.md` | `92dd726a7c9a1e2859da423612a82c4d91524a2c4722dc7c904026c324e39e72` | 17041 |
| `requirements.txt` | `7a3901b84957ea3182f14ade79b9045cde1464c0fcdf29bc527fbb85b5f53639` | 88 |
| `research/fetch_onchain.py` | `2312dc978cc62b8b3acd1f75226bd1f51292704d2758fb01eb4d9ead06d876bf` | 2289 |
| `research/webdata/funding.feather` | `e1bcef5fe2a058f85fdf80662b8ed11a69fefbc09bc3e7db6af2ef112d25b2f3` | 89426 |
| `research/metrics.py` | `982b76ff2ab8bcac0b1512015dbad9125edf5cbfde8f8af9bff0183251bc44e8` | 4785 |
| `research/results.py` | `e83e92c4c8b8e4163cdabab0beebec99dc781a6044f39a867e5181394e44e1c3` | 2114 |
| `research/sweep_emacross.py` | `0e90f1e7c95d8d9fd7a5c2b91cc4d474b4155ec903a775c8d9a79c124b275ba2` | 3321 |
| `research/sweep_funding.py` | `1227276e1ea11a46c9036e7cc2feece956ca3c5706e4cf1c3c9da95adae49bc3` | 3426 |
| `research/walk_forward_fast.py` | `6df4b05e8aa1dd27e2f96bfd6bcfa6da1fbb3b762b21651b7ae9aa66a53e5f5c` | 4939 |
| `research/out/benchmark.csv` | `c47aeefcb5243605359f8b4760ead11744354b0f54fcf9cd8714a8f6f58231b5` | 7174 |
| `research/out/walk_forward.csv` | `17f0422573da19b2a4665f1194cebde3a2a95c00461f4644564769b9aee4146b` | 726 |
| `scripts/download_data.sh` | `ca2ff70e9b1a3aa12526c919598a7c15ad85df50381e8f1a04fda97cadce3557` | 294 |
| `scripts/setup.sh` | `d7f88c6d3c07c88e48c1772fcaa029c238db15e9ec334916dee6d2130d51ca52` | 306 |

`funding.feather` is hashed, not copied into Signalbot. Schema inspection of
that bundled file (source capture, not a Signalbot outcome): columns
`date`, `funding`; 7613 rows; `2019-09-10T08:00:00Z` … `2026-08-21T16:00:00.001Z`;
8h spacing; 3288 rows have non-zero milliseconds on `fundingTime`.

---

## 4. EmaCross executable semantics

Recovered from `EmaCross.py` + `EmaCross.json` + `config.json` + README
reproduce command. Class-default hyperparameters are **not** the shipped
contrast unless the JSON sidecar is loaded.

### 4.1 Market / data

| Item | Recovered fact | Source |
|---|---|---|
| Exchange | Binance | `config.json` `exchange.name` |
| Pair | `BTC/USDT` | `config.json` `pair_whitelist` |
| Market type | **spot** | `config.json` `trading_mode: "spot"` |
| Candle timeframe | `1h` | strategy `timeframe` and config |
| OHLCV source | Freqtrade `download-data` Binance spot, feather | `scripts/download_data.sh` |
| Download timerange | `20180101-` | `download_data.sh` |
| Headline backtest timerange | `20191001-` | README reproduce command |
| Data format | feather | `config.json` `dataformat_ohlcv` |

### 4.2 Signal rules (shipped JSON params)

Freqtrade loads `user_data/strategies/EmaCross.json` beside the class.
Shipped values:

```text
ema_period      = 600          # class default 800; JSON overrides
exit_threshold  = 2.0          # class default 1.0; JSON overrides
```

Indicators (TA-Lib EMA on the 1h dataframe):

- `ema = EMA(close, 600)`
- `ema_exit = ema * (100 - 2.0) / 100`  → 2% below EMA

Entry (`populate_entry_trend`):

```text
qtpylib.crossed_above(close, ema) AND volume > 0
enter_tag = "ema_cross_up"
```

`qtpylib.crossed_above(a, b)` is the standard prior-bar-not-above AND
current-bar-above test. It uses the **current candle close** and the
**previous candle close** relative to the EMA on those same candles.

Exit (`populate_exit_trend`):

```text
qtpylib.crossed_below(close, ema_exit)
exit_tag = "ema_cross_down"
```

No shorting (`can_short = False`). Funding is not used.

### 4.3 Risk / sizing / engine flags

| Item | Recovered fact |
|---|---|
| Stoploss | `-0.15` |
| Trailing stop | `trailing_stop = True`; `trailing_stop_positive` **unset** in strategy |
| ROI | `minimal_roi = {"0": 10}` (1000%; effectively inactive as a take-profit) |
| Leverage | none (spot) |
| Position sizing | `stake_amount: "unlimited"`; `tradable_balance_ratio: 0.99` |
| Initial wallet | `dry_run_wallet: 10000` USDT |
| Max open trades | `1` |
| Pyramiding | none (`max_open_trades: 1`; no position-adjustment callbacks) |
| Startup candles | `1300` |
| `process_only_new_candles` | `True` |
| Interface | Freqtrade `INTERFACE_VERSION = 3` |
| Fee used in headline reproduce | `--fee 0.001` (0.1% per side) |
| Slippage | not modelled in strategy; Freqtrade backtest fills at requested price if inside candle range |
| Funding payments | not applicable (spot position does not pay/receive perpetual funding) |

### 4.4 Signal vs fill timing (Freqtrade engine, not invented here)

Freqtrade 2026.x strategy docs: signals are evaluated on **candle close**;
regular backtest entries/exit-signals fill at the **open of the next candle**.
Config `entry_pricing.use_order_book: true` applies to live/dry-run order-book
pricing. Official backtesting docs state historical order books are not used
and regular entries happen at open-price.

This unit did not run Freqtrade. Fill identity is therefore:

```text
AUTHOR_ENGINE_CLAIM = Freqtrade backtesting defaults for >=2026.7
SIGNALBOT_HAS_NOT_REPLAYED_THE_ENGINE = true
```

---

## 5. EmaCrossFunding executable semantics

Same engine/config/spot market/timeframe/stoploss/ROI/trailing/sizing as
EmaCross **if** `EmaCrossFunding.json` is loaded.

Shipped JSON:

```text
ema_period       = 600
exit_threshold   = 2.0
funding_max_pct  = 55     # class default 90; JSON overrides
```

Class defaults without JSON would **not** match EmaCross (`EmaCross` class
default EMA 800 / exit 1.0 vs funding class default EMA 600 / exit 2.0 /
funding 90). The author's comparison table is only a controlled contrast
under the JSON sidecars.

### 5.1 Funding construction

`research/fetch_onchain.py`:

- HTTP `GET https://fapi.binance.com/fapi/v1/fundingRate`
- `symbol = BTCUSDT` (USD-M perpetual)
- paginated from `2019-09-01`
- `date = pd.to_datetime(fundingTime, unit="ms", utc=True)`
- `funding = float(fundingRate)`
- written to `research/webdata/funding.feather`

This is **Binance USD-M perpetual settled funding history via REST**, not
spot data, and not the Signalbot Vision archive contract.

### 5.2 Funding features inside the strategy

```text
fr = funding.feather indexed by date, column "funding"
idx = dataframe["date"] as UTC datetime          # Freqtrade candle open
f = fr.reindex(idx, method="ffill")              # last fundingTime <= candle date
funding_3d = f.rolling(72, min_periods=24).mean()
funding_pct = Series(funding_3d).rolling(24*180, min_periods=24*30).rank(pct=True) * 100
```

Recovered meanings:

| Item | Executable meaning |
|---|---|
| Funding variable | REST `fundingRate` stored as `funding` |
| Lookback for level | 72 × 1h = 3 calendar days, `min_periods=24` (1 day) |
| Threshold | trailing percentile of `funding_3d` |
| Percentile window | 24*180 = 4320 hours ≈ 180 days; `min_periods=24*30` ≈ 30 days |
| Rank convention | pandas `rolling.rank(pct=True)` **includes the current observation** in its own window |
| Current-in-threshold | **YES** — current `funding_3d` enters the percentile that gates it |
| Alignment | `reindex(..., method="ffill")` uses last `fundingTime <= candle date` |
| Sub-ms fundingTime | 3288/7613 bundled rows have `fundingTime` after the exact hour; those rows are **not** eligible for the exact-hour candle |
| Missing funding | `funding_pct.isna()` **allows entry** |
| Entry suppression | additional conjunct: `funding_pct < 55 OR isna` |
| Exit change | **none** — `populate_exit_trend` is the same EMA-exit cross |
| Funding payments on PnL | **none** — spot account; funding is a filter only |

Author comment in source: "ffill = ostatnia OPUBLIKOWANA wartosc, nigdy przyszla".
That is the author's identification of `fundingTime` with publication time.
It is not a first-party Binance publication-clock proof.

### 5.3 Entry condition (exact)

```text
crossed_above(close, ema)
AND volume > 0
AND (funding_pct < 55 OR funding_pct is NA)
enter_tag = "ema_cross_funding_ok"
```

This is **not** "funding high → don't buy" as a slogan. It is: skip a
long EMA-cross entry when the 3-day mean funding's trailing-180d percentile
is ≥ 55, after 30d of percentile warmup; if the percentile is not yet
defined, do not skip.

README wording "top 45% of its trailing 180-day range" equals
`funding_max_pct = 55` (100-55=45). That wording is consistent with the
JSON, not with the class default 90.

---

## 6. Exact differences between strategies

Under shipped JSON files, the **only trading-rule difference** is the extra
entry conjunct on `funding_pct`.

Also different, and material if JSON is ignored:

| Field | EmaCross class default | EmaCrossFunding class default | Shipped JSON both |
|---|---|---|---|
| `ema_period` | 800 | 600 | 600 |
| `exit_threshold` | 1.0 | 2.0 | 2.0 |
| `funding_max_pct` | n/a | 90 | 55 |

Sweep timeranges also differ in the author's harness:

- `sweep_emacross.py` uses `--timerange 20180101-`
- `sweep_funding.py` and README reproduce use `--timerange 20191001-`

A later prereg must freeze one common window. This unit does not freeze it.

---

## 7. External reported results

**AUTHOR_REPORTED_FACT** from README at the pinned commit (headline table is
`EmaCrossFunding`, "This strategy"):

All numbers stated as: BTC/USDT **spot**, 1h, 0.1% fee per side, no leverage,
single position.

| Metric | EmaCrossFunding (headline) | BTC buy & hold | S&P 500 |
|---|---|---|---|
| Total return | **+1,604%** | +781% | +189% |
| CAGR | **50.9%** | 37.1% | 16.7% |
| Max drawdown | **−33.8%** | −76.6% | −33.7% |
| Sharpe | **1.31** | 0.83 | 0.88 |
| Sortino | **1.42** | 1.13 | 0.89 |
| Calmar | **1.51** | 0.48 | 0.49 |
| Time in market | 61% | 100% | — |
| Trades | 96 | — | — |

Controlled contrast table (same README, after commit `45b6559`):

| | Return | Max drawdown |
|---|---|---|
| Rules 1–3 only (`EmaCross`) | +1,353% | −49.4% |
| Rules 1–4 (`EmaCrossFunding`) | **+1,604%** | **−33.8%** |

Reproduce command timerange: `20191001-`.

Walk-forward table is **EmaCross**, not EmaCrossFunding (`walk_forward_fast.py`
copies `EmaCross.py` only): 13 windows, 8 profitable, compound OOS +1,125%
stated in README. CSV windows include `2025-01`, `2025-07`, `2026-01`.
Those author-published numbers are recorded here as **author artifacts**.
This unit did **not** recompute them and did **not** open Signalbot 2025/2026.

Benchmark.csv first row (author artifact):
`EMAPriceCrossoverWithThreshold,1h,1312.24...,210 trades,...`

---

## 8. External claim wording

### AUTHOR_REPORTED_FACT (verbatim intent, not strengthened)

The author states that the funding rule "buys drawdown, not return", that
the filter is 55 not the best-performing 60, and that "50, 55 and 60 all
work". The author states verification "across both halves of the data and
three EMA lengths — 6 out of 6 independent checks showed reduced drawdown".

The author **does** claim:

- funding filter reduces drawdown vs the EMA-cross baseline;
- headline return is higher with the filter in the full-sample table
  (+1,353% → +1,604%), while the prose still says the rule buys drawdown
  not return;
- robustness of the *drawdown reduction* across two halves and three EMA
  lengths (author-reported; supporting sweep matrix is **not** committed
  as `sweep_funding.feather`).

The author **explicitly does not** claim:

- robustness across assets (table shows BTC unique; several alts lose to
  hold or lose money);
- that Deflated Sharpe clears after counting the 42-strategy benchmark and
  the added fourth rule ("The shipped strategy does not clear this gate.");
- live trading / slippage-complete fills ("Not live-tested").

### SIGNALBOT_INTERPRETATION (not a scientific claim)

The intended later confirmatory object, if a prereg is ever written, would
have to specify a single estimand. The user-supplied approximate interest
("funding filter reduces maximum percentage drawdown") is **consistent with
the author's prose**, but is **not yet** a frozen Signalbot claim.

Do not upgrade:

- "6 of 6 independent checks" into a Signalbot robustness RESULT;
- full-sample +1,604% into validated alpha;
- same-history sequential search into independent discovery.

Drawdown improvement as arithmetic on the author's **percentage** table:

```text
AUTHOR_MAX_DD_EMACROSS          = -49.4%
AUTHOR_MAX_DD_EMACROSSFUNDING   = -33.8%
AUTHOR_DD_REDUCTION_PP          = 15.6 percentage points
```

A prior README table (first commit, later corrected) reported EmaCross
1,350% / −33.8% vs filtered 1,468% / −23.6%. Commit `45b6559` replaced
those with the percentage-drawdown figures above and attributed −23.6%
to Freqtrade's absolute-currency drawdown printout.

---

## 9. Selection-history reconstruction

Short timeline from the pinned git history and README (author-reported):

1. **Author's own `BtcHybrid`** was backtested, returned about +268%, then
   failed PBO = 1.00 and was discarded. File kept.
2. **42 public Freqtrade strategies** were benchmarked on identical spot
   data/fees (`scripts/fetch_benchmark_strategies.sh` +
   `research/benchmark_strategies.py`). 33 lost money; 3 beat BTC hold.
3. **`EMAPriceCrossoverWithThreshold` (Paul Csapak)** won the 1h benchmark
   (+1,312% in `benchmark.csv`).
4. That logic was **parameterized** as `EmaCross` (EMA length, exit %,
   stoploss as parameters).
5. **EMA/exit sweep after seeing results:** `sweep_emacross.py` grid
   `ema_period ∈ {400,600,800,1000,1200}` × `exit_threshold ∈ {0.5,1.0,1.5,2.0,2.5}`
   = 25 variants on `20180101-`. README: returns vary smoothly
   `600 > 800 > 400 > 1000 > 1200`. Shipped `600` / `2.0`.
6. **Funding added after** a separate on-chain test (`test_onchain_edge.py`)
   found a 3-day funding effect and a **2023 sign flip**. Filter is
   one-sided "don't buy into froth" because a directional rule would have
   stopped working.
7. **Funding threshold selected after seeing a sweep:**
   `sweep_funding.py` grid `ema_period ∈ {500,600,700}` ×
   `funding_max_pct ∈ {40,50,60,70,80,90,100}` on `20191001-`.
   Author: peak 60, shipped 55 because 50/55/60 "all work".
8. **BTC vs other assets after comparison:** same rules on ETH/DOGE/AVAX/BNB/LINK/SOL/XRP
   "does not generalise"; BTC is the outlier. BTC was therefore **not** an
   independently preregistered asset before cross-asset inspection.
9. **Walk-forward** (24m train / 6m test, Calmar selection) is on
   **`EmaCross` only**, grid EMA {400…1200} × exit {1,2,3}. Chosen EMA
   drifts 500–1200. CSV includes 2025 and 2026 windows.
10. **DSR / multiple-testing:** PBO 0.21 and DSR p=0.994 are computed on
    the 25 EmaCross variants. Author states the 42-strategy selection and
    the fourth rule are **not** in the trial count, and that the shipped
    strategy does not clear a more honest DSR gate.
11. Drawdown **reporting convention was corrected after publication of the
    first README table**.

```text
EMA=600, funding_max_pct=55, lookback=180d, BTC
were selected after benchmark + sweeps + asset comparison.
They were not independently preregistered before the author's research.
```

MARKET-03 must not later describe them as if they were.

Neighboring parameters examined (author grids, not Signalbot search):

- EMA lengths 400–1200
- exit thresholds 0.5–2.5 (EmaCross sweep) and 1/2/3 (walk-forward)
- funding percentiles 40–100
- crowd-positioning filters tested and **not shipped**
- EMA ensemble tested and **not shipped**

Train/test: walk-forward on EmaCross; no committed frozen confirmatory
split for EmaCrossFunding. No DSR correction for the full pipeline.

---

## 10. Original data / execution environment

### PRICE

```text
exchange          = Binance
instrument        = BTC/USDT
spot/perpetual    = SPOT
timeframe         = 1h (also downloads 5m,15m,4h,12h,1d; strategy uses 1h)
OHLCV semantics   = Freqtrade/ccxt Binance spot klines, feather store
download start    = 2018-01-01
```

### FUNDING

```text
exchange          = Binance
instrument        = BTCUSDT USD-M perpetual
raw source        = REST GET /fapi/v1/fundingRate
variable          = fundingRate
timestamp         = fundingTime (ms) stored as date
publication clock = AUTHOR ASSUMES fundingTime == publicly available
                    Signalbot first-party authority: UNPROVEN
bundled span      = 2019-09-10T08:00:00Z … 2026-08-21T16:00:00.001Z
```

### EXECUTION

```text
engine            = Freqtrade
requirement pin   = freqtrade>=2026.7   (NO UPPER BOUND)
python            = README badge 3.11+
other pkgs        = pandas, numpy, scipy, plotly, kaleido, streamlit,
                    yfinance, requests, pyarrow  (unpinned)
fee               = 0.001 per side on the reproduce command
order type        = config uses order-book "other" side for live;
                    backtest docs: open of next candle
fill assumptions  = no slippage if price in candle range
candle execution  = signal on close; fill next open (Freqtrade docs)
```

Material reproduction changers: Freqtrade minor version, whether JSON
sidecars load, spot vs perpetual klines, `fundingTime` vs `legal_available_at`,
percentage vs Freqtrade absolute drawdown, timerange start 2018 vs 2019-10.

---

## 11. Signalbot data compatibility matrix

Inspected **identity/manifest documents only**. No strategy run. No parquet
row outcomes. Protected 2025/2026 contents were not opened.

| Requirement | External | Signalbot available | Compatible? |
|---|---|---|---|
| Exchange | Binance | CORE and B2-06: Binance | YES (venue) |
| Market | **SPOT** BTC/USDT | CORE: **USD-M perpetual** BTCUSDT; spot explicitly excluded | **NO** |
| Price source | Freqtrade spot klines | CORE Vision USD-M 1m klines | **NO** (wrong market) |
| Timeframe | 1h | CORE native 1m; derived 1h exists as UTC-epoch aggregation of **perp** | **NO** as substitute |
| Funding source | REST `/fapi/v1/fundingRate` | B2-06 Vision `monthly/fundingRate` `last_funding_rate` | **NOT THE SAME OBJECT** |
| Funding definition | REST `fundingRate` at `fundingTime` | settled `last_funding_rate` at `calc_time` | same *economic series class*, different archive identity |
| Timestamp | `fundingTime` ffilled onto spot 1h candle **open** | `calc_time` event time; `legal_available_at` unset | **NO proven as-of join** |
| Publication/availability | author treats `fundingTime` as published | `FUNDING_PUBLICATION_LATENCY_UNPROVEN` | **NO** |
| Historical coverage | spot from 2018; funding from 2019-09; headline from 2019-10 | CORE klines `[2020-01-01, 2026-08-26)`; B2-06 joint `[2020-09-01, 2025-01-01)` | overlap exists **only if wrong market were accepted** |
| Missingness | funding NA **allows** entry | B2-06 missing ≠ corrupt; funding not legally consumable | different rule |
| Research authorization | public backtest | CORE discovery-authorized; B2-06 `research_authorized=false` | funding path blocked as B2-06 science; this unit does not unblock it |

```text
CORE_BTC_BINANCE_V0                 = USD_M_FUTURES BTCUSDT 1m; excludes spot
B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0
                                    = OI + settled funding; research unauthorized
BINANCE_SPOT_BTCUSDT_DATASET        = DOES NOT EXIST IN SIGNALBOT
```

---

## 12. Funding timing / lookahead assessment

Question: at the moment `EmaCrossFunding` decides whether an entry is
allowed, could a historical trader actually have known the funding value
the external implementation used?

Separate clocks:

| Clock | What the external code uses |
|---|---|
| Event timestamp | REST `fundingTime` |
| Strategy join timestamp | Freqtrade 1h candle `date` (candle open) via `ffill` |
| Decision timestamp | Freqtrade: signal on that candle's **close** (1h later than `date`) |
| Fill timestamp | Freqtrade docs: **next candle open** (2h after candle `date`) |
| Public availability | **not a field in the source** |

If a later unit adopted the author's assumption `fundingTime = published_at`,
then a closed-candle signal at `date+1h` would usually be ≥1h after
`fundingTime` for exact-hour settlements, and longer when `fundingTime` is
1 ms after the hour (those rows attach to a later candle).

Signalbot already investigated first-party Binance funding publication
(`docs/research/B2_06_FUNDING_PUBLICATION_AUTHORITY.md`):

```text
funding_publication_semantics_status = FUNDING_PUBLICATION_LATENCY_UNPROVEN
funding_calc_time_is_legal_available_at = false
legal_available_at = null
```

This unit does **not** invent publication latency from `fundingTime`,
archive `calc_time`, 8h cadence, or REST-now-returns-the-row.

Classification:

```text
FUNDING_LOOKAHEAD_STATUS =
  REPRODUCTION_REQUIRES_EXPLICIT_ASSUMPTION
```

The author's **implementation** is reconstructable. The author's
**publication-clock identification is unproven**. Exact point-in-time
legal reproduction is therefore

```text
EXACT_REPRODUCTION_BLOCKED_BY_FUNDING_TIMING
```

unless a later unit pins a first-party publication rule **or** a prereg
explicitly adopts `fundingTime`-as-available as a named assumption (that
would be a weaker, non-legal-as-of study — not LEVEL_1).

Pandas rolling rank including the current `funding_3d` is **not** a future
candle leak. It is a contemporaneous-threshold definition and must be
copied exactly if the filter is reproduced.

---

## 13. Spot vs perpetual compatibility

External strategy **trades** Binance **spot** `BTC/USDT`.
It **reads** perpetual funding only as an auxiliary filter.

Signalbot MARKET-01/02 used Binance USD-M **perpetual** price
(`CORE_BTC_BINANCE_V0`). CORE **excludes** `spot_market`.

```text
A. Faithful reproduction with current snapshots = IMPOSSIBLE
   (no Binance spot BTC/USDT identity/snapshot exists)

B. Approximate conceptual replication on perpetual klines = possible
   only as LEVEL_3, and is NOT a faithful reproduction.
```

Do not silently substitute perpetual close for spot close.

---

## 14. Original period vs Signalbot period

External headline timerange: `20191001-` through the author's data end
(funding file ends 2026-08-21; README walk-forward `END = 2026-08-01`).

External repository **published 2026-08-22**. Therefore:

| Kind | Status |
|---|---|
| Historical reproduction of the author's published claim | possible **in principle** on a later-acquired spot+funding archive covering 2019-10 → ≤ publication |
| Genuinely forward untouched confirmation | **not** the 2019–2026 window the author already fitted/reported |
| Signalbot already-authorized research data | CORE 2020-01→2026-08-26 **perp**; B2-06 2020-09→2025-01 **OI/funding unauthorized** |
| Protected Signalbot 2025/2026 OOS | **not opened**; author's WF CSV contains 2025/2026 as *author* numbers only |

Reproduction **cannot** currently be performed inside already-authorized
Signalbot snapshots because those snapshots are the wrong market and
funding is not legally consumable.

A later confirmatory design, if any, would have to distinguish
pre-publication reconstruction from post-`2026-08-22` confirmation.
This unit does not freeze that split.

---

## 15. Drawdown metric identity

Author's **percentage** max drawdown used in the README after `45b6559`:

`research/metrics.py` `risk_report`:

```text
equity_curve     = (1 + daily_returns).cumprod()
                   daily_returns from Freqtrade wallet total_quote
                   resampled D.last().ffill()  (`research/results.py`)
drawdown         = equity / equity.cummax() - 1
Max drawdown     = min(drawdown)          # most negative percentage
```

This is mark-to-market on the resampled daily wallet (open position
included via `total_quote` sum across currencies). Fees are inside the
Freqtrade wallet series (CLI `--fee 0.001`). Funding payments are not in
spot PnL. Compounding: yes (`stake_amount: unlimited`). Initial capital:
config `10000`. Peak/trough: running peak of that daily equity.

Freqtrade summary "Absolute drawdown (x%)" is a **different** quantity
(largest currency drawdown's contemporaneous percent). Author: Freqtrade
prints −23.6% where `metrics.py` gives −33.8%.

Exact identity with a future Signalbot equity definition is **not yet
proven**; it is recoverable **if** Signalbot uses the same wallet→daily
`cumprod` percentage min. Until that is frozen, "reproduce lower
drawdown" is not a well-posed confirmatory claim.

---

## 16. Replication-level classification

Do not choose the flattering category.

| Level | Current evidence |
|---|---|
| `LEVEL_1_EXACT_REPRODUCTION` | **NO.** Missing spot dataset; funding publication unproven; Freqtrade unpinned; JSON-vs-class defaults must be frozen; drawdown identity not yet bound to a Signalbot equity object. |
| `LEVEL_2_FAITHFUL_REIMPLEMENTATION` | **NOT WITH CURRENT SNAPSHOTS.** Strategy *rules* are recoverable. Engine/data plumbing could be documented (Freqtrade next-open fills, JSON params, `fundingTime` ffill, pandas rank). Blocked today by missing spot history and unproven funding availability. |
| `LEVEL_3_CONCEPTUAL_REPLICATION` | Perp-price + unauthorized funding would test only a broad idea. **Not faithful.** Not authorized by this unit. |
| `NOT_FEASIBLE` **with current snapshots** | **YES** for faithful reproduction. |

Overall unit classification of *what MARKET-03 could become after missing
data/provenance are addressed*: ceiling is **LEVEL_2**, and only with an
explicit funding-availability assumption or a later publication-clock
proof. LEVEL_1 remains blocked by publication timing even after spot
acquisition unless that proof appears.

---

## 17. Unresolved blockers

1. **No Binance spot BTC/USDT dataset** in Signalbot.
2. **Funding publication latency unproven**; do not invent `legal_available_at`.
3. REST funding vs Vision `last_funding_rate` are not the same frozen object.
4. `freqtrade>=2026.7` has no upper bound.
5. Trailing-stop positive offset not set; depends on Freqtrade defaults.
6. Author full-sample window is post-selected and pre-publication; 2025/2026
   author WF numbers are not a Signalbot OOS authorization.
7. Selection path (42 strategies → EMA sweep → funding sweep → BTC-only)
   is not a preregistered confirmatory identity.
8. `sweep_funding.feather` / `sweep_emacross.feather` are **not** in the
   git tree; "6 of 6" cannot be independently replayed from the commit
   without re-running the author's Freqtrade harness on *their* data.

---

## 18. Feasibility verdict

```text
VERDICT = DATA_ACQUISITION_REQUIRED
```

Exactly one of the allowed labels:

**B. DATA_ACQUISITION_REQUIRED**

The selected public strategy family's **rules are recoverable**. Faithful
reproduction is blocked by missing Binance **spot** history and by missing
proven funding **publication** provenance — not by an unreadable strategy
file. This is not permission to substitute perpetual CORE prices, not
permission to consume B2-06 funding, not a prereg, and not a RESULT.

Not A: not enough authorized data/provenance to design a confirmatory
prereg that could actually be executed faithfully.

Not C as the primary label: remaining Freqtrade-default ambiguities are
real but secondary; they do not prevent stating what data must be
acquired. A later source-review can still freeze JSON-on, trailing
defaults, and fill-at-next-open.

Not D: the object of study remains this public family. Faithful
reproduction is not *materially impossible in principle*; required
inputs are missing.

```text
MARKET_03_PREREG                 = NO
MARKET_03_IMPLEMENTED            = NO
MARKET_03_ARMED                  = NO
MARKET_03_EXECUTED               = NO
MARKET_03_TEST_CALIBRATED        = NO
DEFAULT_V4                       = NO
B2_06_EXECUTION_AUTHORIZED       = NO
PROTECTED_OOS_TOUCHED            = NO
```

Next authorized step if any: **spot-dataset / funding-provenance acquisition
design**, or an explicit later decision that LEVEL_2 with a named
`fundingTime`-as-available assumption is acceptable. Do not preregister
in this unit.

---

## 19. Outcome-blindness statement

This unit did **not** compute any Signalbot MARKET-03 scientific outcome.

| Quantity on Signalbot data | Computed? |
|---|---|
| strategy trades | **NO** |
| strategy return | **NO** |
| drawdown | **NO** |
| Sharpe | **NO** |
| candidate comparison | **NO** |
| EmaCross performance | **NO** |
| EmaCrossFunding performance | **NO** |
| parameter sensitivity | **NO** |

Author-reported numbers were read from the pinned README/CSV only.
`funding.feather` was inspected for **schema, span, and timestamp
exactness**, not joined to Signalbot prices and not used to produce
trades or metrics.

No EmaCross or EmaCrossFunding run was invoked. No Freqtrade backtest
was run. Protected 2025/2026 Signalbot OOS was not opened.
