# Mechanism memory V0

**Unit:** `MECHANISM_MEMORY_V0`
**Kind:** compact accumulated-research map
**Date:** 2026-09-24
**Status:** `EXTENDED_THROUGH_GENERATOR_V0_CALIBRATION_C005`
**Machine-readable record:** `docs/research/MECHANISM_MEMORY_V0.json`

This is **not** a new research framework, pipeline, or MARKET unit. It is a
compact map of already-consumed mechanism space. Historical RESULT/prereg
artifacts remain authoritative for their own semantics. Sprint 03 scientific
outcomes were recorded after that canonical one-shot and are not rewritten
here. Sprint 04 D12/D13 outcomes are appended after the canonical Sprint 04
one-shot; they are not recomputed from this file.

## Coverage

35 entries: H01–H05, B2-01–B2-06, MARKET-01–06, D1–D13, plus five durable Generator V0 calibration signatures `GV0CAL-C001`–`GV0CAL-C005`.

```
BATCH01_PROMOTED = 0 / 5
B2-01..B2-04 = CLOSED_NO_PROMOTION
B2-05 = DEVELOPMENT_CONSUMED / B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED
      (not cryptographic byte-proof; do not invent a RESULT)
B2-06 = BLOCKED_MISSING_OBSERVABLE (not negative evidence)
MARKET-01/02/05/06 = NO_EVIDENCE (consumed)
MARKET-03 = EXTERNAL reproduction (not internal discovery)
MARKET-04/04H = BLOCKED_OBSERVABLE / NOT_TESTED
D1 = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
D2 = PROMISING_PROTOTYPE + independent pre-2020 BitMEX replication
D3/D4-rolling/D5 = NO_USEFUL_STRUCTURE
D4 lead-lag = deferred
D6 = deferred (source not pinned; family I diagnostic)
D7 = PROMISING_PROTOTYPE (adaptive discovery only; not independently replicated)
D8 = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT (not NO_USEFUL_STRUCTURE)
D9 = NO_USEFUL_STRUCTURE (SHARE-on-closing-extremes; do not rescue)
D10 = NO_USEFUL_STRUCTURE (residual persistence; do not add post-hoc refractory)
D11 = PROMISING_PROTOTYPE (unsigned scheduled-FOMC 6h RV; N=39; not D8 rescue)
D12 = PROMISING_PROTOTYPE (US-clock quote-volume anchoring; EU diagnostic does not classify)
D13 = NO_USEFUL_STRUCTURE (1-week panel IC; observed reversal; practical gate failed)
INTERNAL_DISCOVERY_CARDS_EXECUTED = 10
INTERNAL_PROMISING_PROTOTYPES = 4
SPRINT04_HYPOTHESES_SELECTED = true
```

Protected 2025/2026 remain sealed in every listed unit.

Use this map to require nearest H/B2/MARKET/D priors on new discovery
candidates. Do not reopen closed Batch01/02, MARKET, D2, D7, D9, D10, or
D13 neighbor space from this file. Do not redesign D12 from the EU
diagnostic or from W-window/hour-slice neighbors. Do not pick the larger
of D13 momentum vs reversal.


## Generator V0 calibration-memory extension — 2026-09-24

Five model-generated cost/pipeline calibration cards are retained as prior-work
mechanism signatures. They have **no scientific status** and no market outcomes
were tested.

- `GV0CAL-C001`: participant-composition proxy from average trade size → sub-hour variance-ratio structure; pipeline survivor.
- `GV0CAL-C002`: perp-vs-spot price-discovery locus with US-DST displacement; pipeline survivor.
- `GV0CAL-C003`: venue funding-settlement clock microstructure; red-team blocked on causal identification and confounding.
- `GV0CAL-C004`: CME fixing-window spillover into Binance perpetual activity; red-team blocked on confounding.
- `GV0CAL-C005`: listing-age lifecycle drift in Binance spot USDT cross-section; pipeline survivor.

The generator does **not** receive survivor/reject labels or critic reasons. Its
blind map contains only neutral prior-work signatures. The novelty critic gets
the outcome-neutral governance state: C001/C002/C005 are `CONSUMED` prior
signatures; C003/C004 are `DEFERRED_OR_BLOCKED` with named methodological
blockers so a materially redesigned card may advance only by explicitly
resolving the blocker. Exact duplicates, cosmetic relabels and parameter/window/
horizon neighbors remain disallowed.

Full calibration details remain in
`GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.{json,md}`.

## Memory-chain authority (2026-09-24)

`MECHANISM_MEMORY_V0.json` is now a derived byte copy of the memory-chain head
snapshot (`docs/research/generator_v0_memory/`). Do not edit it by hand; ingest
campaigns with `scripts/research/generator_v0/finalize_memory.py`. The 30 pre-GV0CAL
entries are carried verbatim by the `LEGACY_BOOTSTRAP` event; the five `GV0CAL-*`
entries come from the deterministic `GV0CAL` finalization event. See
`GENERATOR_V0_MEMORY_FINALIZER.md`.
