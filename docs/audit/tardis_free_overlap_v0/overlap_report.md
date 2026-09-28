# Tardis free overlap validation V0

This run compared the free Tardis files for 2026-08-01 and 2026-09-01 with the read-only Signalbot live export. Tolerances were not refit. The current instrument table was not used as point-in-time metadata.

Overall decision: **REJECT_TARDIS_FOR_CURRENT_REPLAY**

## Export and vendor identity

Signalbot gold is `source=live` only. Empty open-interest cells stay missing.

| File | Data rows | SHA-256 |
| --- | --- | --- |
| `exchange_instrument_history.csv` | 0 | `a19bce69c435363847eb667f07afaf07f2aa5d02bccb0c8d3f4b364a7996ad0c` |
| `exchange_instruments_current_not_used_as_pit.csv` | 3 | `21fffc12b954398630fed664b1361f1caac78a6b4a538442318391fa5704b1be` |
| `klines_1m.csv` | 8639 | `071e141abecfb3cf226bc3f1e910b75a360230259aea6b3bcc26864a12f740ec` |
| `klines_1m_source_counts.csv` | 3 | `49a3f12f63b0b6b088d615894d4ca67c62f87071d359ec72e99034d2c96eeece` |
| `open_interest.csv` | 33450 | `1be99608fb721868f756eff3435531ea575fa9c51bcb3d4c16048583e6a32f59` |
| `open_interest_source_counts.csv` | 4 | `35c022647d799f1caed34452399a58838f1508523e4e2520d4c6ca5c2a0fc875` |

Source-count rows shipped with the export:

- `klines_1m_source_counts.csv`: [{'exchange': 'binance', 'n': '2880', 'source': 'live', 'table_name': 'klines_1m'}, {'exchange': 'bybit', 'n': '2880', 'source': 'live', 'table_name': 'klines_1m'}, {'exchange': 'okx', 'n': '2879', 'source': 'live', 'table_name': 'klines_1m'}]
- `open_interest_source_counts.csv`: [{'exchange': 'binance', 'n': '288', 'source': 'backfill', 'table_name': 'open_interest'}, {'exchange': 'binance', 'n': '11137', 'source': 'live', 'table_name': 'open_interest'}, {'exchange': 'bybit', 'n': '11361', 'source': 'live', 'table_name': 'open_interest'}, {'exchange': 'okx', 'n': '10952', 'source': 'live', 'table_name': 'open_interest'}]

Tardis files are the same public free bytes as the earlier inventory (SHA-256 matched before this comparison):

| File | HTTP | Bytes | Rows | SHA-256 | Status |
| --- | --- | --- | --- | --- | --- |
| `binance-futures_derivative_ticker_20260801_BTCUSDT.csv.gz` | 200 | 1422904 | 96681 | `a9887d7699f05df661f061f28e05e145957e71218c7a0162e4092c9264874422` | OK |
| `binance-futures_trades_20260801_BTCUSDT.csv.gz` | 200 | 8954358 | 1073872 | `27622702d5e33e6d374ec3d6f9040e8d7550ca9229641bccb6289d64256e4afe` | OK |
| `bybit_derivative_ticker_20260801_BTCUSDT.csv.gz` | 200 | 1675529 | 142285 | `f25ab55ce5c40a22e16aad40c880c66e2e35ee80302ed91b79647eba85612971` | OK |
| `bybit_trades_20260801_BTCUSDT.csv.gz` | 200 | 14480418 | 530577 | `b85d6c0a9f378b249c673215a1afdb383035059e4f0cf9b60b3f47e1ca75c6db` | OK |
| `okex-swap_derivative_ticker_20260801_BTC-USDT-SWAP.csv.gz` | 200 | 2538526 | 195778 | `bf1efd934fbf0aaa31240ebb077dadac4b34c4691aa95ee935007cad85673325` | OK |
| `okex-swap_trades_20260801_BTC-USDT-SWAP.csv.gz` | 200 | 5931280 | 691214 | `ae04dea89f04e4b20ad5046f4da651f5090fc29d6cbb2250fc2156f0c262d2eb` | OK |
| `binance-futures_derivative_ticker_20260901_BTCUSDT.csv.gz` | 200 | 1800753 | 112367 | `636144962f3857d81f36d77a125163664efdbad10ac1d9feb5bf15bc4e4acdfb` | OK |
| `binance-futures_trades_20260901_BTCUSDT.csv.gz` | 200 | 27906263 | 3602361 | `2686d38f10b30df1dd0d3058fe0efda5fc89e6f427b57d1e3c231ceda3ee4430` | OK |
| `bybit_derivative_ticker_20260901_BTCUSDT.csv.gz` | 200 | 3048767 | 244575 | `851dd3d1ed78fbdc0cf35cbbf4c7c28cad63783531b8408829873d1c2b3b01d0` | OK |
| `bybit_trades_20260901_BTCUSDT.csv.gz` | 200 | 54305683 | 2017317 | `25ff55e4433f2cc9efcc81e91dbac39a29f0c7eeb1cc3e210a0ea5853fc215ea` | OK |
| `okex-swap_derivative_ticker_20260901_BTC-USDT-SWAP.csv.gz` | 200 | 5473923 | 430097 | `760551b30c56a3052d687e9d765d73593172f891c930973513f3385d6291f0bb` | OK |
| `okex-swap_trades_20260901_BTC-USDT-SWAP.csv.gz` | 200 | 21078171 | 2654495 | `bb061fbc75096a68113898e1b858d6dd5804ca98a673ea2a32174c79ada273fd` | OK |

DATES_COMPARED = ['2026-08-01', '2026-09-01']

VENUES_COMPARED = ['binance', 'bybit', 'okx']

## Coverage by venue and date

A bucket is present when it contains at least one 1-minute bar or one open-interest observation inside `[B, B+5m)`. Comparable feature pairs below are the frozen diagnostics on buckets that were not gap-excluded. OKX notional stays null when no PIT multiplier exists; those nulls are not zeros and are not treated as agreement of a USD magnitude.

| Date | Venue | Gold buckets | Vendor buckets | Both present | Missing gold | Missing vendor | Gap-excluded |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-08-01 | binance | 288 | 288 | 288 | 0 | 0 | 0 |
| 2026-08-01 | bybit | 288 | 288 | 288 | 0 | 0 | 0 |
| 2026-08-01 | okx | 288 | 288 | 288 | 0 | 0 | 0 |
| 2026-09-01 | binance | 288 | 288 | 288 | 0 | 0 | 0 |
| 2026-09-01 | bybit | 288 | 288 | 288 | 0 | 0 | 0 |
| 2026-09-01 | okx | 288 | 288 | 288 | 0 | 0 | 0 |

Expected buckets per venue-date: 288.

## Feature agreement by venue and date

### 2026-08-01 binance

- `price_move_pct`: comparable=288 sign=1 spearman=0.999999 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=288 sign=1 spearman=0.999961 median_abs=9.31323e-09 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=288 sign=1 spearman=0.999999 median_abs=6.51926e-09 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=0 gold_only=288 tardis_only=0
- evaluability disagreements: count=0 fraction=0 buckets_entering_equivalence=288

### 2026-08-01 bybit

- `price_move_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=0.999989 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=288 sign=1 spearman=0.998973 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=288 sign=1 spearman=0.999946 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=288 sign=0.9375 spearman=0.948212 median_abs=0.000772719 median_ratio=0.999223 both_null=0 gold_only=0 tardis_only=0
- evaluability disagreements: count=0 fraction=0 buckets_entering_equivalence=288

### 2026-08-01 okx

- `price_move_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=288 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=288 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=270 sign=0.933333 spearman=0.941916 median_abs=0.000920912 median_ratio=1 both_null=0 gold_only=18 tardis_only=0
- evaluability disagreements: count=0 fraction=0 buckets_entering_equivalence=288

### 2026-09-01 binance

- `price_move_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=0.999999 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=288 sign=1 spearman=0.999978 median_abs=4.76837e-07 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=288 sign=1 spearman=0.999884 median_abs=1.52737e-07 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=0 gold_only=288 tardis_only=0
- evaluability disagreements: count=0 fraction=0 buckets_entering_equivalence=288

### 2026-09-01 bybit

- `price_move_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=1 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=288 sign=1 spearman=0.999456 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=288 sign=0.996528 spearman=0.99715 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=288 sign=0.982639 spearman=0.986153 median_abs=0.00286555 median_ratio=0.99807 both_null=0 gold_only=0 tardis_only=0
- evaluability disagreements: count=0 fraction=0 buckets_entering_equivalence=288

### 2026-09-01 okx

- `price_move_pct`: comparable=288 sign=0.996528 spearman=0.99922 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=288 sign=1 spearman=0.998286 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=288 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=0 sign=null spearman=null median_abs=null median_ratio=null both_null=288 gold_only=0 tardis_only=0
- `oi_change_pct`: comparable=252 sign=0.984127 spearman=0.993363 median_abs=0.00273877 median_ratio=1 both_null=0 gold_only=36 tardis_only=0
- evaluability disagreements: count=1 fraction=0.00347222 buckets_entering_equivalence=288

## Aggregate verdicts

These labels are the frozen `_verdicts` output. A `MATERIAL_REORDER` finding is attached to price, range, and open interest together because the frozen function matches on finding code, not on which feature moved. Consensus is `FAIL` only when `CONSENSUS_QUORUM_DISAGREEMENT` is present; otherwise the frozen function returns `NOT_EVALUABLE`.

PRICE_VERDICT = PASS_ON_PREDECLARED_PRINCIPLES

RANGE_VERDICT = PASS_ON_PREDECLARED_PRINCIPLES

VOLUME_VERDICT = PASS_ON_PREDECLARED_PRINCIPLES

OI_VERDICT = PASS_ON_PREDECLARED_PRINCIPLES

TAKER_VERDICT = PASS_ON_PREDECLARED_PRINCIPLES

CONSENSUS_VERDICT = FAIL

Aggregate feature diagnostics:

- `oi_change_pct`: comparable=1098 sign=0.959016 spearman=0.977153 median_abs=0.00156667 median_ratio=1 both_null=0 gold_only=630 tardis_only=0
- `price_move_pct`: comparable=1728 sign=0.999421 spearman=0.999877 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct`: comparable=1728 sign=1 spearman=0.999859 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd`: comparable=1152 sign=0.999132 spearman=0.99892 median_abs=1.16415e-10 median_ratio=1 both_null=576 gold_only=0 tardis_only=0
- `volume_notional_usd`: comparable=1152 sign=1 spearman=0.999909 median_abs=0 median_ratio=1 both_null=576 gold_only=0 tardis_only=0

Consensus diagnostics:

- `oi_change_pct_median`: comparable=522 sign=0.787356 spearman=0.731221 median_abs=0.0180076 median_ratio=1.2741 both_null=0 gold_only=54 tardis_only=0
- `price_move_pct_median`: comparable=576 sign=1 spearman=0.999999 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `range_width_pct_median`: comparable=576 sign=1 spearman=0.999992 median_abs=0 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `taker_delta_notional_usd_sum`: comparable=576 sign=1 spearman=0.999513 median_abs=2.98023e-08 median_ratio=1 both_null=0 gold_only=0 tardis_only=0
- `volume_notional_usd_sum`: comparable=576 sign=1 spearman=0.999969 median_abs=5.96046e-08 median_ratio=1 both_null=0 gold_only=0 tardis_only=0

Quorum member disagreements: count=576 fraction=1 buckets=576

## OI sign agreement by magnitude

```json
{
  "edges": {
    "p10_abs_gold": 0.004548105171693217,
    "p50_abs_gold": 0.0313558589914449,
    "p90_abs_gold": 0.18833478859160954
  },
  "label": "SAMPLE-DAY magnitude strata of the Signalbot reference. Not a 30-day percentile.",
  "strata": {
    "10_to_50pct": {
      "count": 439,
      "sign_agreement_fraction": 0.9567198177676538,
      "sign_disagreement_count": 19
    },
    "50_to_90pct": {
      "count": 440,
      "sign_agreement_fraction": 0.9977272727272727,
      "sign_disagreement_count": 1
    },
    "lowest_10pct": {
      "count": 110,
      "sign_agreement_fraction": 0.7727272727272727,
      "sign_disagreement_count": 25
    },
    "top_10pct": {
      "count": 109,
      "sign_agreement_fraction": 1.0,
      "sign_disagreement_count": 0
    }
  }
}
```

## Tail agreement

Label: SAMPLE-DAY TAIL AGREEMENT. This is not a production 30-day percentile.

```json
{
  "features": {
    "oi_change_pct": {
      "top_bottom_10pct": {
        "bottom_overlap": 0.963302752293578,
        "fraction": 0.1,
        "k": 109,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1098,
        "top_overlap": 0.9357798165137615
      },
      "top_bottom_5pct": {
        "bottom_overlap": 0.9444444444444444,
        "fraction": 0.05,
        "k": 54,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1098,
        "top_overlap": 0.8888888888888888
      }
    },
    "price_move_pct": {
      "top_bottom_10pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.1,
        "k": 172,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1728,
        "top_overlap": 1.0
      },
      "top_bottom_5pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.05,
        "k": 86,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1728,
        "top_overlap": 1.0
      }
    },
    "range_width_pct": {
      "top_bottom_10pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.1,
        "k": 172,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1728,
        "top_overlap": 0.9941860465116279
      },
      "top_bottom_5pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.05,
        "k": 86,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1728,
        "top_overlap": 1.0
      }
    },
    "taker_delta_notional_usd": {
      "top_bottom_10pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.1,
        "k": 115,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1152,
        "top_overlap": 1.0
      },
      "top_bottom_5pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.05,
        "k": 57,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1152,
        "top_overlap": 1.0
      }
    },
    "volume_notional_usd": {
      "top_bottom_10pct": {
        "bottom_overlap": 0.991304347826087,
        "fraction": 0.1,
        "k": 115,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1152,
        "top_overlap": 1.0
      },
      "top_bottom_5pct": {
        "bottom_overlap": 1.0,
        "fraction": 0.05,
        "k": 57,
        "label": "SAMPLE-DAY TAIL AGREEMENT",
        "n": 1152,
        "top_overlap": 1.0
      }
    }
  },
  "label": "SAMPLE-DAY TAIL AGREEMENT"
}
```

## Null and evaluability disagreements

```json
{
  "count": 1,
  "definition": "Disagreement of (is_usable and price_move_pct is not None) on buckets that were not gap-excluded.",
  "fraction": 0.0005787037037037037
}
```

## Documented vendor gaps

Applicable trades or derivative_ticker incidents: **0**.

Vendor-gap buckets excluded: **0**.

- `okex-swap` 2026-08-01 2023-06-09T15:30:00.000Z → 2026-08-04T11:16:00.000Z: **REVIEWED_NOT_APPLICABLE_TO_REQUESTED_DATASETS**. Some generated OKX statistics channels were collected less frequently than the documented 1-minute interval. The affected channels were long-short-account-ratio and taker-volume for OKX Futures and Swap, and taker-volume and loan-ratio for OKX Spot. Recent OKX Swap long-short-account-ratio data was typically recorded every 35-40 minutes. Other OKX channels were unaffected. The missing observations were not recorded and cannot be backfilled. Normal 1-minute collection resumed on 2026-08-04.

## Top mismatch causes

- `CONSENSUS_QUORUM_DISAGREEMENT` (reject): 1.0

## Mechanism notes

These notes explain the computed diagnostics. They do not add a tolerance and they do not change the decision.
The only rejection finding is CONSENSUS_QUORUM_DISAGREEMENT, fraction 1.0 on 576/576 consensus buckets. Price, range, volume, taker, and the OI percentage did not fire their own rejection rules.
Binance oi_change_pct is gold-only on 288/288 buckets on both dates. A read of the Binance derivative_ticker files found at least one same-timestamp open_interest disagreement in every 5-minute bucket. 2026-08-01: 9574 conflicting timestamps, maximum absolute difference 496.893. 2026-09-01: 11262 conflicting timestamps, maximum absolute difference 879.360. One small example is 2026-08-01T00:00:24Z with 109546.512 and 109546.513. The frozen production rule nulls the whole bucket when any timestamp conflicts, so Binance OI percentage was not compared.
Gold Binance OI stayed evaluable, so the OI contributing set differs on every consensus bucket. That membership gap is the quorum failure. It is not a price failure.
Bybit and OKX oi_change_pct were compared. OKX uses native contracts on both sides. No ctVal was applied. exchange_instrument_history has 0 rows. The current instrument file was not used. OKX volume and taker notional are both null on 288/288 buckets each date.
Signalbot is missing one OKX 1-minute bar, 2026-09-01T15:54:00Z. That lines up with the single price-evaluability disagreement, 1/1728.
On comparable Binance and Bybit volume and taker pairs the median scale ratio is 1 and rank correlation stays above 0.90. The largest absolute gaps are still large. The top sample is Binance 2026-09-01T18:25:00Z volume, absolute difference about 7.964e7 USD. Median agreement is not bit-identical replay.
The export's open-interest source counts include 288 Binance rows with source=backfill. Those rows were not loaded. They are not zeros and they are not comparison evidence.

Gap buckets excluded from equivalence: 0.

Unit mismatches: 0.

OKX_OI_PIT_STATUS = PIT_BLOCKED_NO_HISTORICAL_CTVAL

OKX open-interest percentage uses native contract units on both sides and does not apply ctVal. OKX volume and taker notional stay fail-closed without a historical contract multiplier. The current instrument file was not read as that multiplier.

## Decision

REJECT_TARDIS_FOR_CURRENT_REPLAY

No detector episodes, historical outcomes, or production 30-day percentile ranks were computed.

COST_INCURRED_USD = 0

DATA_PURCHASED = false
DEPLOYED = false
DETECTOR_CHANGED = false
EPISODES_REPLAYED = false
OUTCOMES_COMPUTED = false
PAID_SUBSCRIPTION_STARTED = false
PERCENTILES_COMPUTED_AS_PRODUCTION_30D = false
PRODUCTION_CODE_CHANGED = false
PRODUCTION_DB_WRITTEN = false
PROTECTED_RESEARCH_OPENED = false
PUSH_CHANGED = false
RULES_CHANGED = false
