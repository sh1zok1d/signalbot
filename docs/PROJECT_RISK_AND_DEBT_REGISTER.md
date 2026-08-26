# Signalbot — Current Risk & Debt Register

**Status:** ACTIVE  
**Scope:** only risks that matter under the current research-first posture.

The previous long register, including closed V2 implementation items and detailed PR histories, remains in git history at commit `a9c383355690c5ab9bcc577454da3ebec75d8d89`. Closed implementation archaeology does not belong in the active risk surface.

Status: `OPEN`, `VERIFY`, `BLOCKED`, `DEFERRED`, `CLOSED`.

Severity: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

## A. Research-validity risks

| ID | Sev | Status | Risk | Closure evidence |
|---|---|---|---|---|
| R-001 | CRITICAL | OPEN | Engineering correctness may be mistaken for trading edge | Every report separates correctness, exploratory evidence, validation and OOS |
| R-002 | CRITICAL | OPEN | Current rich history is roughly one month and cannot establish durability across regimes | Multi-year CORE dataset + chronological validation under `HISTORICAL_DATA_STRATEGY.md` |
| R-003 | CRITICAL | OPEN | Repeated threshold/hypothesis search can produce research overfit | Search-surface ledger + development-only tuning + untouched validation/OOS |
| R-004 | HIGH | OPEN | Correlated 5m candidates inflate apparent sample size | Episode/time clustering, block concentration and effective-N reporting |
| R-005 | HIGH | OPEN | Regime-specific failure may be explained post-hoc | Prospectively defined regime gates reproduced on independent data |
| R-006 | HIGH | OPEN | Magic thresholds/lookbacks may be local artifacts | Parameter-neighborhood/plateau analysis before candidate promotion |
| R-007 | HIGH | OPEN | Simple price structure may match or beat richer logic | Mandatory simple/matched controls and ablations |
| R-008 | HIGH | OPEN | Multiple hypothesis families/variants create selection bias | Material variant count and selection criteria recorded in research ledger |
| R-009 | HIGH | OPEN | Delay/cost can erase apparent detector edge | Resolution-supported delay and friction stress before tradability claims |
| R-010 | HIGH | OPEN | Missing/incomplete rows may be non-random | Full denominator/missingness reports; no survivor-only headline result |
| R-011 | HIGH | OPEN | One favorable asset/period may be mistaken for market-general mechanism | Cross-time/regime validation; cross-asset validation only where claim is general |

## B. Data risks

| ID | Sev | Status | Risk | Closure evidence |
|---|---|---|---|---|
| D-001 | CRITICAL | OPEN | Historical feeds are not automatically live-equivalent | Versioned source-period evidence tiers in dataset manifest |
| D-002 | HIGH | VERIFY | Coarse OI/history may acquire fake fine-grained timing after forward-fill | Provider-granularity audit/tests; preserve actual observation resolution |
| D-003 | HIGH | OPEN | Liquidation semantics/completeness differ by venue/period | Capability/semantics matrix; only comparable windows used for claims |
| D-004 | HIGH | OPEN | Taker/OI/funding/liquidation coverage differs by venue | Per-source date/granularity matrix in every material dataset |
| D-005 | HIGH | OPEN | Mutable database/revisions can make reports irreproducible | Dataset/revision/checksum identity stored with research artifacts |
| D-006 | HIGH | OPEN | Outages/gaps may correlate with volatility | Missingness-by-regime/outage diagnostics |
| D-007 | MEDIUM | OPEN | Expensive rich-data acquisition may happen before core mechanism is validated | Enforce CORE-first acquisition priority |

## C. Current experiment risks

| ID | Sev | Status | Risk | Closure evidence |
|---|---|---|---|---|
| E1-001 | CRITICAL | OPEN | `E1-RUN-001` holdout could be contaminated by post-hoc changes | Run only frozen one-shot evaluator; no rule changes before result |
| E1-002 | HIGH | OPEN | Final +6h time-shift control requires timestamp coverage beyond primary +4h outcomes | Timestamp-only preflight must pass frozen coverage rule before opening outcomes |
| E1-003 | HIGH | OPEN | One historical 1m gap exists at `2026-08-24T12:29Z` | Keep affected paths incomplete; do not repair specifically for E1 |
| E1-004 | HIGH | OPEN | Development results may bias interpretation of final holdout | Apply frozen verdict vocabulary/controls; no family rescue inside RUN-001 |

## D. Frozen implementation debt

These items are retained but **not active development work** while research-first freeze is in force.

| ID | Sev | Status | Risk | Re-entry condition |
|---|---|---|---|---|
| V2-001 | HIGH | BLOCKED | PR #67 Stage-6 history evaluation can use later `history.as_of` geometry for earlier T | Only revisit if validated edge actually requires this lifecycle path; fix temporal semantics before merge |
| V2-002 | HIGH | BLOCKED | PR #67 same-T second event may collide deterministic event identity | Same re-entry condition; lifecycle semantics must define unique same-boundary identity |
| V2-003 | MEDIUM | DEFERRED | Large V2 formal contracts/modules increase maintenance burden | Reassess after edge validation; do not refactor frozen code for aesthetics now |
| CFG-001 | MEDIUM | DEFERRED | Legacy config names/thresholds can look active even when not used | Clean when research requires touching config/runtime or before product restart |

## E. Repository/documentation debt

| ID | Sev | Status | Risk | Closure evidence |
|---|---|---|---|---|
| DOC-001 | MEDIUM | CLOSED | README described Stage 1 / obsolete V2 progression | Research-first README + `PROJECT_STATUS.md` |
| DOC-002 | MEDIUM | CLOSED | Multiple roadmaps/contracts appeared simultaneously authoritative | `DOCUMENTATION_INDEX.md` + superseded stubs |
| DOC-003 | MEDIUM | OPEN | Historical Stage1/Stage2/audit/runbook files still share `docs/` root and can feel noisy | Keep explicit status index; physically archive/move only when tooling can preserve exact content cheaply |
| DOC-004 | LOW | OPEN | Some operational runbooks may contain stale names/commands | Verify before next actual deploy; do not spend research time polishing unused deploy docs |
| DOC-005 | MEDIUM | OPEN | One-off research scripts can accumulate without ownership/status | Add/maintain `scripts/research/README.md`; later separate reusable tooling from frozen run artifacts |

## F. Security / operational risks

| ID | Sev | Status | Risk | Closure evidence |
|---|---|---|---|---|
| OPS-001 | HIGH | OPEN | Research/data state depends on VPS availability and mutable local DB | Durable backups/snapshots and reproducible historical materialization before critical future OOS runs |
| OPS-002 | MEDIUM | OPEN | Old deployment docs can be mistaken for current authorization | Operational docs classified as reference only; deploy requires explicit decision |
| SEC-001 | HIGH | VERIFY | Historical credential exposure cannot be assumed harmless | Confirm secrets are absent from current tree/history where feasible and rotate any known exposed credentials |

## G. Priority order

Under the current project posture:

1. preserve/finish frozen E1;
2. build multi-year reproducible CORE data;
3. control researcher/search overfit;
4. validate simple mechanisms;
5. test rich-feature incremental value;
6. only after an edge survives, reopen architecture/product debt.

Do not close research risks by adding product code.