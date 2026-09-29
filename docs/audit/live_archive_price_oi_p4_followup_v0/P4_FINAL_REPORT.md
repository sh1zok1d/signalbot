# P4 PRICE_OI historical follow-up — final owner-run record

**Status:** `FROZEN_EVIDENCE / OWNER_RUN_DESCRIPTIVE_FOLLOW_UP`  
**Recorded:** 2026-09-29  
**Scope:** `PRICE_OI_CONTRACTION_DOWN` and `PRICE_OI_CONTRACTION_UP` only.

This file durably records the completed owner-run P4 follow-up that had previously
existed only in the owner output and the current-state summary.

It is a **descriptive historical follow-up**, not a predictive result, not a causal
claim, not a directional signal, and not evidence of a trading edge.

## Identity and provenance

- Replay class: `CURRENT_RULE_SEMANTIC_RECONSTRUCTION`.
- Follow-up contract: `HISTORICAL_FOLLOW_UP_V0`.
- Frozen follow-up source SHA: `9e1ba03638b5e53fedea5b91cb60d41e23288f5e`.
- Stage-2 feature-code identity used by the owner runner:
  `43b1e1dd1d3acaaba3d9b917f5319d31b2afb0b5`.
- Authorized replay buckets: `12434`.
- Owner-run `as_of`: `2026-09-29T15:03:00Z`.
- Replay provenance at the runner boundary:
  `RECONSTRUCTED_FROM_SIGNALBOT_LIVE_ARCHIVE` mapped to the frozen follow-up
  provenance `RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA`.
- `LIVE_OBSERVED` was not written by this reconstruction.

The replay is a reconstruction under the current frozen PRICE+OI rules from
Signalbot observations collected live. It does **not** prove historical runtime
`evaluation_fresh`, raw-revision coherence, materialization state, or alert
delivery.

The row-level P4 output was produced in the owner's ephemeral output directory
`/tmp/live_archive_price_oi_p4_followup_v0`. Those raw output files are not
committed here, and their final file hashes were not captured into the repository.
This record therefore freezes the owner-reported summary, not a byte-for-byte
archive of the row-level output.

## Result

| Metric | DOWN | UP |
|---|---:|---:|
| Reconstructed episodes | 277 | 223 |
| Triggered episodes | 25 | 19 |
| Follow-up eligible events | 22 | 17 |
| Follow-up eligible UTC dates | 17 | 12 |
| Event median realized range — 1h | 0.9280488526070928% | 1.3288664266566295% |
| Event median realized range — 4h | 1.5765374076858096% | 2.09441932438176% |
| Ordinary comparison events | 18 | 11 |
| Ordinary comparison UTC dates | 13 | 7 |
| Ordinary median realized range — 1h | 0.31225251980032437% | 0.3374713940875821% |
| Ordinary median realized range — 4h | 0.6508845191856447% | 0.6888552939953104% |
| Triggered but outcome-incomplete | 3 | 2 |
| Ordinary events with too few controls | 4 | 6 |
| Reference unavailable | 0 | 0 |
| Not comparable | 0 | 0 |
| Not matured | 0 | 0 |

Both families passed the frozen **display sufficiency** threshold. That threshold
means only that enough observations existed to display the frozen descriptive
statistic.

## Correct interpretation

In this archive, triggered PRICE_OI_CONTRACTION states were followed by larger
realized ranges than the ordinary same-time baseline.

That statement is deliberately narrow.

The event medians and ordinary-baseline medians are **not a paired effect
estimator over identical event sets**:

- DOWN event medians use 22 eligible events; the ordinary comparison uses 18.
- UP event medians use 17 eligible events; the ordinary comparison uses 11.
- The ordinary baseline is the median of per-event same-time historical
  baselines, not random-market anchors.

Do not turn the side-by-side values into an effect ratio or a significance claim.

The endpoint is `realized_range_pct`, which has no direction. This result does
not establish direction prediction, profitability, a trading edge, or incremental
information beyond the volatility already present at the event.

## Matched baseline

The frozen matched baseline was **not available** for this historical archive.

Status: `UNAVAILABLE_FAIL_CLOSED`.

Reason: the frozen candidate predicate depends on LIVE tape
`evaluation_fresh` and raw-revision/coherence state. Those historical states are
not present in the archive and cannot honestly be reconstructed from PRICE+OI
alone.

No matched controls were fabricated.

A later adversarial review also identified design defects in the frozen matched
baseline, including a forward-looking ±4h exclusion and insufficient control for
the event-defining recent price move. No matched-baseline number from that frozen
design should be treated as evidence.

## Research consequence

P4 is complete as a descriptive archive check.

Any claim that PRICE_OI_CONTRACTION contains information beyond volatility needs
a new protocol frozen before its outcomes are inspected. The key next scientific
control is a price-move ablation: compare the same extreme/persistent price move
with OI contraction versus the same price condition without OI contraction.

This P4 record does not authorize that experiment and does not open protected
2025/2026 research data.
