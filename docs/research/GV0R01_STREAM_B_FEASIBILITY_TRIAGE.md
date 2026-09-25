# GV0R01 Stream-B feasibility triage and post-C013 program decision

**Unit:** `GV0R01_STREAM_B_FEASIBILITY_TRIAGE`
**Kind:** outcome-blind data feasibility and program routing
**Date:** 2026-09-25
**Machine-readable twin:** `docs/research/GV0R01_STREAM_B_FEASIBILITY_TRIAGE.json` (includes the exact card fields from the sealed GV0R01 journal)

This unit executed no hypothesis and computed no target, outcome, correlation or statistic. No protected 2025/2026 value was opened. No GV0 batch was generated, and no provider was called. C013, the scientific test ledger and Generator V0 memory are unchanged.

## Program decision

- **C013.** `PROMISING_PROTOTYPE` + `CONFIRMATION_DEFERRED_LOW_POWER`. It is parked pending a scientifically adequate independent surface. There is no underpowered 2025/2026 confirmation, no rescue of any kind, and 2025/2026 stay sealed.
- **Active program.** Triage the six Stream-B candidates (C004, C006, C012, C014, C016, C020) before paying for another Generator V0 campaign.

## Matrix

| ID | Feasibility | Missing source | Point-in-time | Data cost | Effort | Confirmation surface | Ready to design | Remaining blocker |
|---|---|---|---|---|---|---|---|---|
| C004 | `READY_AFTER_FREE_PUBLIC_ACQUISITION` | BLS CPI schedule archive (CPI arm only) | FOMC arm yes; CPI pending | $0 | LOW / MEDIUM | fresh available but limited | **true** | CPI pinning; D10/D11 overlap accounting |
| C006 | `BLOCKED_POINT_IN_TIME_SEMANTICS` | DVOL with non-revision evidence; option marks | no | $0 values; about $700/mo vendor capture | HIGH | fresh available but limited | false | DVOL point-in-time evidence; paid marks |
| C012 | `READY_AFTER_FREE_PUBLIC_ACQUISITION` | BLS CPI schedule archive (CPI arm only) | FOMC arm yes; CPI pending | $0 | LOW / MEDIUM | fresh available but limited, plus a pre-2020 BTC candidate | **true** | CPI pinning |
| C014 | `BLOCKED_POINT_IN_TIME_SEMANTICS` | BTC+ETH DVOL with non-revision evidence; option quotes | no | $0 values; about $700/mo vendor | HIGH | fresh available but limited | false | DVOL point-in-time evidence; paid quotes |
| C016 | `BLOCKED_EXPENSIVE_DATA` | spread / top-of-book history for the card falsifier | partial | $0 depth; about $700/mo spread/L2 | HIGH | fresh available but limited | false | paid spread/L2; depth schema/gap audit |
| C020 | `READY_AFTER_FREE_PUBLIC_ACQUISITION` | NYSE, China State Council and OPM holiday calendars with publication dates | pending | $0 | MEDIUM | fresh available but limited | **true** | three-calendar pinning; D12 overlap accounting |

About the cost figures: the $700/month paid figures come from the repository's first-party pricing check of 2026-09-22 (Tardis Solo Options or Perpetuals). This sandbox cannot re-verify them, because its network policy refuses the documentation hosts.

## Candidate notes

- **C004. ETH vs BTC common-factor dominance in FOMC windows.**
  - The FOMC core is ready: the pinned official Fed statements (`D11_FOMC_OFFICIAL_V0`, 39 events, per-statement release time), CORE BTC and CORE ETH.
  - The CPI extension needs the BLS schedule archive with advance-publication evidence.
  - Prior exposure: C004 reuses D11's event set and D10's frozen-beta ETH residual (`NO_USEFUL_STRUCTURE`).
  - Fresh surface: about 14 scheduled FOMC statements in 2025–2026, against 39 in discovery. A pre-2020 surface would need spot ETH/BTC, which is an instrument change.
- **C006. Option-implied volatility gap before RV-regime transitions.**
  - Deribit's free DVOL API history starts in 2021-03. It cannot, by itself, evidence that values were never recomputed, and the card makes that a hard requirement ("blocked rather than used"). An independent contemporaneous capture is paid.
  - The TERM_SLOPE arm needs paid option marks.
  - Binance BVOLIndex (first-party, only from 2023-06-20) is a different observable. Adopting it would change the hypothesis.
- **C012. Pre-announcement BTC drift before FOMC and CPI.**
  - The FOMC arm is ready and point-in-time resolved.
  - The CPI arm needs the BLS schedule archive. Rescheduled releases must follow the schedule as published before each window, never the realized release time.
  - Because the test is BTC-only, a pre-2020 alternative surface exists: BitMEX XBTUSD 5m (DATA_READY) and Binance spot 1m for scheduled events 2017–2019. It needs a D2-style equivalence adjudication.
- **C014. ETH-BTC implied relative variance spread.** It has the same DVOL point-in-time blocker as C006, for both assets, and its quote-based arm is paid.
- **C016. Order-book depth thinning before RV-regime transitions.**
  - First-party metadata (key names and sizes only):
    - Binance USD-M BTCUSDT `bookDepth` daily files run from 2023-01-01. The legal 2023–2024 window has 728 files (2 days missing, 341 MB), and 631 fresh days follow.
    - `bookTicker` exists only from 2023-05-16 to 2024-03-30, then was discontinued.
  - The card's falsifier (3) requires a trailing-spread control, and its TOP_OF_BOOK arm needs top-of-book history. Neither is covered by first-party data for the range.
  - A kline-based spread proxy would change the falsifier, so the candidate is blocked on paid spread/L2 history.
  - bookDepth is aggregated band depth, not a tick-level L2 reconstruction.
- **C020. Official-holiday participant removal and intraday volume shares.**
  - Market data and DST calendars are ready.
  - Three free official calendars need pinning with publication dates. Edge cases are frozen by a publication-date rule; for example, the 2021 Juneteenth federal holiday was enacted one day before it was first observed.
  - Prior exposure: C020 overlaps D12 (family J, the same volume profiles).

## Selection (feasibility only)

`NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C012`

Three candidates can reach DATA_READY without changing the hypothesis, at zero data cost: C004, C012 and C020. C012 has five advantages:
- its core FOMC arm is already point-in-time resolved;
- it needs one new free source;
- it declares the smallest search surface (6 variants);
- it has the lowest effort;
- it is the only one with a credible independent route beyond the limited fresh 2025–2026 events: a pre-2020 BTC surface.

C004 needs ETH and overlaps D10/D11. C020 needs three calendars and overlaps D12. This is not a tie. Expected market performance was not considered.

`RUN_GV0R02_NEXT = false`: an actionable Stream-B candidate exists.

**Confirmation-first rule (from C013).** The C012 design unit must plan its confirmation surface and outcome-free power before any discovery execution.

**Next unit:** `GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN`.

**Environment note.** This sandbox refuses `bls.gov`, `federalreserve.gov`, `web.archive.org` and the other documentation hosts (CONNECT refused). Pinning the BLS CPI archive needs `bls.gov` and `web.archive.org` added to the environment's allowed domains, or another environment.

## Access log

Only the Binance S3 origin was used: 13 ListBucket requests (key names and sizes only) and 0 payload GETs. All 12 external documentation hosts were attempted and none was reachable.
