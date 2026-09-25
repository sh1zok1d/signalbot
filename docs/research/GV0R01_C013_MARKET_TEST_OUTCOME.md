# GV0R01-C013 market test — one-shot outcome

**Classification:** `PROMISING_PROTOTYPE` (discovery tier)
**Date:** 2026-09-25
**Machine-readable twin:** `docs/research/GV0R01_C013_MARKET_TEST_OUTCOME.json`
**Immutable result:** `docs/research/GV0R01_C013_MARKET_TEST_RESULT.json` (SHA256 `036016c403f83e4c63b2e006379551a0f595e8803cb55a0ef8f27a19ce3a1062`)

This is the first scientific market test produced from Generator V0. It is discovery evidence only and requires an independent confirmation. It is **not** a validated edge. No trading, cost or profitability claim is made or tested. Protected 2025/2026 data were not opened.

## Provenance

| Item | Value |
|---|---|
| Hypothesis | GV0R01-C013, "Persistence of intraday wick morphology across the Binance spot USDT cross-section" |
| Test family / search family | `TF-GV0R01-C013-MT1` / `SF-GENERATOR_V0-GV0R01` |
| Prereg | `GV0R01_C013_MARKET_TEST_PREREG.json`, SHA256 `49dff57b3e068d999c9c4467fb5117de9d73ad564425bf737df727a1096f7625` |
| Permit | `GV0R01_C013_MARKET_TEST_EXECUTION_PERMIT.json`, SHA256 `c88ec544…`. Committed and pushed in `386bc10` before any outcome existed. |
| Execution | One run at HEAD `386bc10`, tree `4a63bfca…`, 2026-09-25 05:02:43–05:03:53 UTC. No rerun. |
| Implementation | Digests of the library, the runner and the four Sprint 04 loaders are identical to the prereg (recorded in the result's `IDENTITY` block). |
| Dataset | `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0`. Snapshot `fdd698c6…`, file ledger `fc38ea13…`, exclusions `35779ca5…`. All 18,296 files were verified; no protected file was opened. |
| Execute preflight | 18/18 checks passed, including the permit binding and the local-bytes check against the ledger. No target was computed before execution. |

On the data restore: the sandbox refused `data.binance.vision` (CONNECT 403), so the canonical restore failed before writing anything. The exact frozen ledger keys were then fetched from the same bucket's S3 origin. Each file was kept only if its bytes matched the ledger's SHA256. After that, the canonical `restore_d13_panel` reported `downloaded 0, already_present 18296, verified 18296`.

## Primary (K=5, H=1, N=50; frozen)

| Quantity | Value |
|---|---|
| Pooled weekly-mean Spearman(rank CLV, rank WICK_RESID) | −0.019932 |
| Permutation null, central 95% | [−0.008230, 0.004923] |
| Two-sided permutation p (1000 draws) | 0.001998 (the minimum attainable, 2/1001) |
| Decision days / valid days | 1820 / 1820 |
| Valid weeks | 260 (52 in each year 2020–2024) |
| Missing-target rate | 0.000264 (13 missing bars, 11 delisting-day bars, out of 91,000 name-days) |
| Yearly means | 2020 −0.0691 · 2021 −0.0677 · 2022 −0.0307 · 2023 +0.0315 · 2024 +0.0363 |
| Years sharing the pooled sign | 2020, 2021, 2022 (3 of 5) |
| Controlled (partial on trailing return, range and volume ranks) | −0.053505, p 0.001998 |
| Newey–West t (lag 4) | −2.479 |
| Adjacency (same predictor, target bar t+1) | −0.021409 (260 valid weeks) |

## Gates

| Gate | Result |
|---|---|
| STATISTICAL | pass |
| DIRECTION (negative) | pass |
| TEMPORAL (≥3 of 5 years) | pass, exactly at the threshold |
| CONTROL | pass |
| DEPENDENCE | pass |
| ADJACENCY | pass |

`SUPPORT_PASS = true`, with no support reasons and no failure reasons. Under the frozen rule, this gives `PROMISING_PROTOTYPE`.

## Secondary grid (non-decisional)

`SECONDARY_CAN_CHANGE_CLASSIFICATION = false`. No secondary variant is selected or promoted.

| Variant | Pooled | p | Holm p | Valid weeks |
|---|---|---|---|---|
| K1_H1_N50 | −0.009726 | 0.003996 | 0.013986 | 260 |
| K1_H1_N100 | −0.021810 | 0.001998 | 0.013986 | 239 |
| K1_H5_N50 | −0.021355 | 0.001998 | 0.013986 | 260 |
| K1_H5_N100 | −0.041738 | 0.001998 | 0.013986 | 239 |
| K5_H1_N100 | −0.036437 | 0.001998 | 0.013986 | 239 |
| K5_H5_N50 | −0.053294 | 0.001998 | 0.013986 | 260 |
| K5_H5_N100 | −0.086433 | 0.001998 | 0.013986 | 239 |

As preregistered, the N=100 variants are invalid on the 148 early decision days that have fewer than 100 eligible names. The H=5 variants have overlapping targets and are descriptive only.

## Recorded facts (not a reclassification)

- The temporal gate passed at its threshold. The last two legal years, 2023 and 2024, have positive yearly means, opposite to the pooled sign.
- The primary and controlled p-values sit at the floor of a 1000-draw permutation test.
- The pooled effect is a small cross-sectional rank correlation.

These facts are recorded for the confirmation design. They do not change the frozen classification, and nothing here proposes a new parameter set.

## Accounting and boundary

- `docs/research/SCIENTIFIC_TEST_LEDGER.json`: `TF-GV0R01-C013-MT1` is `EXECUTED`, with its result SHA256 and classification recorded.
- `SF-GENERATOR_V0-GV0R01` now counts 1 executed test out of 30 generated cards. Generated cards are not market tests.
- Market-test executions: 1. Reruns: 0 (not authorized). LLM or provider calls: 0.
- Generator V0 memory is unchanged. This result will enter full memory only through a later deterministic `MARKET_TEST_RESULT` event, and the blind generator map stays outcome-neutral.
