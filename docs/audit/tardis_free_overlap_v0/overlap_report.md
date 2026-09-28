# Tardis free overlap validation V0

This run inventoried the free first-of-month Tardis files and did not compare them to Signalbot.

Overall decision: **INCOMPLETE_NO_SIGNALBOT_EXPORT**

Status: **WAITING_FOR_SIGNALBOT_EXPORT**

No Signalbot database credentials, SSH key, or live raw export were available in this environment. Local fixture databases were not used as gold. No feature verdict below is a measurement.

## What was obtained at USD 0

Plain GET, no API key, no Range header, no account:

| File | HTTP | Bytes | Rows | SHA-256 | First timestamp | Last timestamp | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `binance-futures_derivative_ticker_20260801_BTCUSDT.csv.gz` | 200 | 1422904 | 96681 | `a9887d7699f05df661f061f28e05e145957e71218c7a0162e4092c9264874422` | 2026-08-01T00:00:00+00:00 | 2026-08-01T23:59:59.212000+00:00 | OK |
| `binance-futures_trades_20260801_BTCUSDT.csv.gz` | 200 | 8954358 | 1073872 | `27622702d5e33e6d374ec3d6f9040e8d7550ca9229641bccb6289d64256e4afe` | 2026-08-01T00:00:00.022000+00:00 | 2026-08-01T23:59:59.912000+00:00 | OK |
| `bybit_derivative_ticker_20260801_BTCUSDT.csv.gz` | 200 | 1675529 | 142285 | `f25ab55ce5c40a22e16aad40c880c66e2e35ee80302ed91b79647eba85612971` | 2026-07-31T23:59:59.983000+00:00 | 2026-08-01T23:59:59.083000+00:00 | OK |
| `bybit_trades_20260801_BTCUSDT.csv.gz` | 200 | 14480418 | 530577 | `b85d6c0a9f378b249c673215a1afdb383035059e4f0cf9b60b3f47e1ca75c6db` | 2026-08-01T00:00:00.044000+00:00 | 2026-08-01T23:59:59.039000+00:00 | OK |
| `okex-swap_derivative_ticker_20260801_BTC-USDT-SWAP.csv.gz` | 200 | 2538526 | 195778 | `bf1efd934fbf0aaa31240ebb077dadac4b34c4691aa95ee935007cad85673325` | 2026-07-31T23:59:59.962000+00:00 | 2026-08-01T23:59:58.466000+00:00 | OK |
| `okex-swap_trades_20260801_BTC-USDT-SWAP.csv.gz` | 200 | 5931280 | 691214 | `ae04dea89f04e4b20ad5046f4da651f5090fc29d6cbb2250fc2156f0c262d2eb` | 2026-08-01T00:00:00.303000+00:00 | 2026-08-01T23:59:59.962000+00:00 | OK |
| `binance-futures_derivative_ticker_20260901_BTCUSDT.csv.gz` | 200 | 1800753 | 112367 | `636144962f3857d81f36d77a125163664efdbad10ac1d9feb5bf15bc4e4acdfb` | 2026-09-01T00:00:00.035000+00:00 | 2026-09-01T23:59:59.001000+00:00 | OK |
| `binance-futures_trades_20260901_BTCUSDT.csv.gz` | 200 | 27906263 | 3602361 | `2686d38f10b30df1dd0d3058fe0efda5fc89e6f427b57d1e3c231ceda3ee4430` | 2026-09-01T00:00:00.003000+00:00 | 2026-09-01T23:59:59.987000+00:00 | OK |
| `bybit_derivative_ticker_20260901_BTCUSDT.csv.gz` | 200 | 3048767 | 244575 | `851dd3d1ed78fbdc0cf35cbbf4c7c28cad63783531b8408829873d1c2b3b01d0` | 2026-08-31T23:59:59.984000+00:00 | 2026-09-01T23:59:59.683000+00:00 | OK |
| `bybit_trades_20260901_BTCUSDT.csv.gz` | 200 | 54305683 | 2017317 | `25ff55e4433f2cc9efcc81e91dbac39a29f0c7eeb1cc3e210a0ea5853fc215ea` | 2026-09-01T00:00:00.116000+00:00 | 2026-09-01T23:59:59.755000+00:00 | OK |
| `okex-swap_derivative_ticker_20260901_BTC-USDT-SWAP.csv.gz` | 200 | 5473923 | 430097 | `760551b30c56a3052d687e9d765d73593172f891c930973513f3385d6291f0bb` | 2026-08-31T23:59:59.970000+00:00 | 2026-09-01T23:59:59.939000+00:00 | OK |
| `okex-swap_trades_20260901_BTC-USDT-SWAP.csv.gz` | 200 | 21078171 | 2654495 | `bb061fbc75096a68113898e1b858d6dd5804ca98a673ea2a32174c79ada273fd` | 2026-09-01T00:00:00.007000+00:00 | 2026-09-01T23:59:59.914000+00:00 | OK |

URL pattern: `https://datasets.tardis.dev/v1/{exchange}/{dataType}/{YYYY}/{MM}/{DD}/{symbol}.csv.gz`

Decompressed headers match the documented trades and derivative_ticker schemas. No source was stopped for a schema change. HTTP `Content-Type` is `text/csv`; the body is gzip (`1f 8b`).

Empty `open_interest` cells are counted in the manifest and are not zeros. Rows timestamped before 00:00 UTC are outside the sample day and are not placed in the first bucket.

## Inventory notes (not a comparison)

Rows before the sample date, excluded from that date's buckets:

- `bybit_derivative_ticker_20260801_BTCUSDT.csv.gz`: 3 row(s) before 00:00 UTC
- `okex-swap_derivative_ticker_20260801_BTC-USDT-SWAP.csv.gz`: 1 row(s) before 00:00 UTC
- `bybit_derivative_ticker_20260901_BTCUSDT.csv.gz`: 3 row(s) before 00:00 UTC
- `okex-swap_derivative_ticker_20260901_BTC-USDT-SWAP.csv.gz`: 1 row(s) before 00:00 UTC

Files whose exchange timestamps are not non-decreasing. Open-interest endpoints are chosen by timestamp, not by file order:

- `bybit_derivative_ticker_20260801_BTCUSDT.csv.gz`
- `okex-swap_derivative_ticker_20260801_BTC-USDT-SWAP.csv.gz`
- `bybit_derivative_ticker_20260901_BTCUSDT.csv.gz`
- `okex-swap_derivative_ticker_20260901_BTC-USDT-SWAP.csv.gz`

Trade `side` values observed, after the buy/sell/unknown mapping was fixed from the Tardis docs: `buy`=5375048, `sell`=5194788. No other side token appeared, so nothing was remapped after the count.

## Documented vendor gaps

Incident windows that overlap a sample date:

- `okex-swap` 2026-08-01 2023-06-09T15:30:00.000Z → 2026-08-04T11:16:00.000Z: **REVIEWED_NOT_APPLICABLE_TO_REQUESTED_DATASETS**. Some generated OKX statistics channels were collected less frequently than the documented 1-minute interval. The affected channels were long-short-account-ratio and taker-volume for OKX Futures and Swap, and taker-volume and loan-ratio for OKX Spot. Recent OKX Swap long-short-account-ratio data was typically recorded every 35-40 minutes. Other OKX channels were unaffected. The missing observations were not recorded and cannot be backfilled. Normal 1-minute collection resumed on 2026-08-04.

Applicable trades or derivative_ticker gap tags on these two dates: **0**.

The OKX statistics-channel incident that ends 2026-08-04 overlaps 2026-08-01 and states that other OKX channels were unaffected. It is not applied to `trades` or `derivative_ticker`.

## Verdicts

PRICE_VERDICT = NOT_RUN

RANGE_VERDICT = NOT_RUN

VOLUME_VERDICT = NOT_RUN

OI_VERDICT = NOT_RUN

TAKER_VERDICT = NOT_RUN

CONSENSUS_VERDICT = NOT_RUN

OI_SIGN_AGREEMENT_BY_MAGNITUDE = not computed

TAIL_AGREEMENT_SUMMARY = not computed (would have been labeled SAMPLE-DAY TAIL AGREEMENT, not a production percentile)

NULL_EVALUABILITY_DISAGREEMENTS = not computed

TOP_MISMATCH_CAUSES = none; no pairs exist

No detector episodes, historical outcomes, 30-day percentile ranks, or alpha were computed.

## Owner commands

On the host that can read the live Signalbot database, with `SIGNALBOT_DSN` set in the environment and not written to disk:

```bash
python -m scripts.audit.tardis_free_overlap_v0.extract_signalbot_readonly \
  --out-dir ./signalbot_gold_20260801_20260901
```

The script starts a read-only session, exports `source = 'live'` BTCUSDT rows for Binance, Bybit, and OKX on 2026-08-01 and 2026-09-01, plus the PIT instrument rows needed for notional conversion, and prints SHA-256 hashes. It does not export Telegram or user data.

After those files exist, from this repository:

```bash
python -m scripts.audit.tardis_free_overlap_v0 compare \
  --vendor-dir /path/to/tardis-cache \
  --gold-dir ./signalbot_gold_20260801_20260901 \
  --out-dir docs/audit/tardis_free_overlap_v0
```

Do not point `--gold-dir` at a synthetic fixture.

## Decision

D. INCOMPLETE_NO_SIGNALBOT_EXPORT

The free files are readable and the production feature functions are wired for a later comparison. That is not evidence that Tardis reproduces Signalbot's 5-minute state.

NEXT_EXPERIMENT: finish this free comparison after the owner export. Do not purchase a Tardis plan on the basis of this run.

COST_INCURRED_USD = 0

PRODUCTION_CODE_CHANGED = false
PRODUCTION_DB_WRITTEN = false
DETECTOR_CHANGED = false
RULES_CHANGED = false
PERCENTILES_COMPUTED_AS_PRODUCTION_30D = false
EPISODES_REPLAYED = false
OUTCOMES_COMPUTED = false
PUSH_CHANGED = false
PROTECTED_RESEARCH_OPENED = false
PAID_SUBSCRIPTION_STARTED = false
DATA_PURCHASED = false
DEPLOYED = false
