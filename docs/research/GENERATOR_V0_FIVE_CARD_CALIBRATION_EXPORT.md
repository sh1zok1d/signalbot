# Generator V0 — five-card calibration sample export

```
NO_SCIENTIFIC_STATUS   = true
MARKET_OUTCOMES_TESTED = false
PROTECTED_DATA_OPENED  = false
PURPOSE                = COST_AND_PIPELINE_CALIBRATION
```

Date: 2026-09-24. Source code: `df0fccf13c1babadb7ccc4da46c6d9d524101c4e`
(tree `78c20b03da337f641a8fa93c8e232d40778e236d`). Machine-readable export,
including full card fields, critic judgments, usage and call provenance:
`GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json`.

These are calibration fixtures: cards written by a model and judged by model
critics, used only to measure cost and exercise the pipeline. They are not
evidence, have not been tested against market data, and are not promoted. The
selector order below checks that the deterministic ordinal rule runs; it is not
a ranking of research merit.

## Provenance

- Generator: Anthropic `claude-opus-5-5`, effort high, one round of 10 cards, call
  `e9ea20c2…1a75`, 10/10 admitted, USD 0.892012. The sample is the five lowest
  candidate IDs, fixed before any critic call.
- Critics: `gpt-6-sol` (novelty and red team, background Responses, effort high),
  `gpt-6-luna` (feasibility, synchronous, effort low). Every novelty call used the
  full five-card batch, so each carries batch relations for exactly the other four
  cards.
- Critic results were re-derived offline from the stored model text with the
  production schema, normalization and application validators at the source
  commit. Every call key re-hashes from its stored request and every raw hash
  matches. The three source journals were read-only and are byte-identical after
  the export.
- Excluded: hidden reasoning (never stored), raw provider envelopes, credentials,
  and the per-signature novelty relation values.

## Cards and final critic verdicts

| ID | Name | Source class | Data status | Novelty | Feasibility | Red team | Stream |
|---|---|---|---|---|---|---|---|
| C001 | Average trade size as participant-composition state and subsequent sub-hour variance ratio | KLINES | DATA_READY | ALLOW | PASS | PASS | EXECUTABLE_NOW |
| C002 | Intraday rotation of perpetual-versus-spot price-discovery locus and its displacement at US DST shifts | CROSS_VENUE | DATA_READY | ALLOW | PASS | PASS | EXECUTABLE_NOW |
| C003 | Funding-settlement clock microstructure identified by offset settlement schedules across BitMEX and Binance | PRE2020_SURFACE | FEASIBILITY_REQUIRED | ALLOW | PASS | REJECT | NOT_A_STREAM |
| C004 | Reference-rate fixing window footprint on Binance perpetual activity at CME bitcoin futures settlement | OFFICIAL_CALENDAR | FEASIBILITY_REQUIRED | ALLOW | PASS | REJECT | NOT_A_STREAM |
| C005 | Listing-age lifecycle drift in the Binance spot USDT cross-section | CROSS_SECTIONAL_PANEL | DATA_READY | ALLOW | PASS | PASS | EXECUTABLE_NOW |

All five cards are `NEW_FAMILY_PROPOSAL`. The red team failed C003 on
`CONFOUNDING_ADDRESSED` and `CAUSALITY`, and C004 on `CONFOUNDING_ADDRESSED`. For
C003 and C004 the feasibility critic confirmed `FEASIBILITY_REQUIRED` and marked
the availability checks false; under the frozen rules that is expected for a
data-blocked card and is not itself a rejection.

## Deterministic selector

Rule: descending `MECHANISM_DISTANCE`, `INFORMATION_GAIN`, `FEASIBILITY`,
`CHEAPNESS`, then ascending candidate ID. No LLM selector call. No near-duplicate
exclusions.

| Order | ID | Mechanism distance | Information gain | Feasibility | Cheapness |
|---|---|---|---|---|---|
| 1 | C005 | 2 | 2 | 3 | 3 |
| 2 | C002 | 2 | 2 | 2 | 2 |
| 3 | C001 | 2 | 1 | 3 | 3 |

C003 and C004 are not selector inputs because they are not in any stream.

## Successful critic cost per card (USD)

| ID | Novelty | Feasibility | Red team | Chain |
|---|---|---|---|---|
| C001 | 0.029376 | 0.000415 | 0.016884 | 0.046675 |
| C002 | 0.036238 | 0.000503 | 0.016296 | 0.053037 |
| C003 | 0.034482 | 0.000561 | 0.011660 | 0.046703 |
| C004 | 0.030496 | 0.000628 | 0.014724 | 0.045848 |
| C005 | 0.029182 | 0.000429 | 0.014320 | 0.043931 |
| Total | 0.159774 | 0.002536 | 0.073884 | 0.236194 |

Successful final calls only. Excluded: the C001 direct-path 403 (not billed),
the C001 synchronous red-team call reconciled UNKNOWN (USD 0.098806), and the
synthetic red-team transport smoke (USD 0.006570).
