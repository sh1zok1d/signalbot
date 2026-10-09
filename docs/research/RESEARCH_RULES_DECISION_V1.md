# Research rules decision V1 — surface classes, exact-formulation closures, exposure counters

**Owner decision, 2026-10-09.** Recorded by the chief architect. The owner partly adopted the proposal `RESEARCH_RULES_REVIEW_V1.md`; this record states what was adopted.
**Applies to:** every research unit designed after this record. It is **not retroactive** (§6).
**Research priority:** `FIND_DIRECTIONAL_EDGE`. No product substitution of this direction.

## 1. Dataset-wide exhaustion is cancelled

- A surface is no longer "consumed" as a whole because it was used for some question.
- What is tracked is the **exact feature → outcome exposure**.
- Using a surface for other questions does not by itself make it unusable for a new question.

## 2. Three surface classes

Every unit names the class of each surface it uses, **per question**.

| Class | Definition | What it may host |
|---|---|---|
| `DISCOVERY_REUSABLE` | Any surface, whatever it was used for before. | Discovery and adaptive search. Every adaptive search on the surface raises its search-exposure counters (§4) and **never yields a confirmation by itself**. |
| `QUESTION_FRESH_REPLICATION` | A surface on which **this exact question** (§3) was never read. It may have been used for other questions. | A one-shot replication of a relation selected elsewhere, labelled "question-fresh, not pristine". |
| `PRISTINE_HOLDOUT` / `PROSPECTIVE` | A reserved holdout never read for anything, or data that accrues after the unit's freeze. | The strongest confirmation class. |

- One surface can be `QUESTION_FRESH_REPLICATION` for one question and only `DISCOVERY_REUSABLE` for another.
- The E1-RUN-001 holdout stays reserved and untouched (§7).

## 3. Exact feature → outcome exposure

**What exposes a question.** A question Q = (feature, outcome family, horizon class) is **exposed on a surface** if any read on that surface computed an outcome statistic of the same outcome family and an overlapping horizon class, conditioned on any of:
- the same feature;
- an equivalent of it: monotone transform, threshold, window or horizon neighbour, relabel, observable substitution, subgroup;
- a feature from which Q was derived.

**Outcome families:** DIRECTION, LEVEL_RESOLUTION, RANGE_VOL, PATH_STRESS, ACTIVITY.

**Design-note duty.** Each design note:
- lists the nearest exposed relations on each surface it uses, from their records;
- states why Q is not one of them.

**What does not expose Q:**
- reads of other features on the same surface;
- unconditional outcome reads, such as the generic hourly race stream or the disclosed unconditional 4h path read on 2025–26.

These still count in the surface and target counters (§4).

## 4. Exposure counters and the search penalty

Three counters, kept in `EXPOSURE_COUNTERS_V1` (initial compilation in progress; lower bounds flagged):
- **surface counter `m_S`:** feature→outcome cells whose outcomes were read on surface S;
- **target counter `m_ST`:** those of them with outcome family T;
- **family counter `m_FT`:** cells of mechanism family F (atlas region) with outcome family T, across all surfaces.

**Rules:**
- Every discovery result reports `m_S`, `m_ST` and `m_FT` as they stand before the unit, plus the unit's own cells.
- Every adaptive search adds its cells to the counters when it is read, whatever the result.
- **Search-exposure penalty (default implementation; the owner may change it).**
  - A discovery relation is promoted to a candidate for question-fresh replication only if it survives a family-wise α = 0.10 Bonferroni bound over `m_ST` plus the unit's own cells. With `m_ST` ≈ 300 that is roughly |t| ≥ 3.6.
  - Below that bar it stays `DISCOVERY_ONLY`, reported with its interval.
  - Promotion is never a confirmation. Confirmation needs a `QUESTION_FRESH_REPLICATION` or `PRISTINE_HOLDOUT/PROSPECTIVE` surface, one shot, no rescue.

## 5. Closures are narrowed to exact formulations

- **What a closed unit closes:** its exact formulation and the equivalents in §3. That covers parameter neighbours, relabels, observable substitutions, subgroups and compositions of its consumed parts.
- **What it does not close:** its mechanism family. Earlier family-wide bans written in unit records or red-team notes no longer close families. Examples: the taker/flow family via H05/B2-05, "family J sessions exhausted" (DH1-X4), D7/D12 child bans, "no second H04-derived child". These units' exact formulations stay closed.
- **Owner-closed research lines stay closed until a new owner override.** Recorded as owner closures:
  - the divergence / selling-exhaustion line, including SEED-0001 and exhaustion units (2026-10-02/03);
  - the DH3 program and its cells, including the X-cells closed before data (2026-10-04);
  - the R03 owner cards (2026-10-03);
  - the formation-width (WIDTH) line and its opening-range object (owner closure recorded on Cursor branch `formation-width-line-closure-v1-08d8`, not yet merged);
  - the TWAP V1 branch, narrow region (2026-10-02);
  - V3 Microscope;
  - the compiler V3 variance line.
- **When an idea's membership in an owner-closed line is unclear,** the architect asks the owner before any design note.

## 6. Causal identification

- Causal identification is **not required** for predictive research.
- A predictive relation needs out-of-sample confirmation (§2), not a causal argument.
- Causal wording remains banned in claims and user texts.

## 7. Not retroactive; P3; E1

- **P3_CONFIRMATION_V1 is not relabelled by these rules.** It stays an **informative result with a governance violation, not a pristine confirmation**. It ran on Binance 2025–26 against the then-binding DH data rule, without a written owner permit.
- **E1-RUN-001:** untouched. No decision now. Its holdout stays reserved under AGENTS.md.

## 8. What does not change

- Design note before outcome.
- Every test logged.
- One-shot confirmation.
- No rescue.
- Discovery is kept apart from confirmation.
- The claim ladder: a historical frequency is never a current probability.
- No trade calls in user texts.
- Sealed records are never rewritten.

## 9. What this record supersedes for new units

- **Atlas §5 `CONFIRMATION_ON_EXPOSED`:** now reads "confirmation on a surface where the exact question (§3) is exposed".
- **Atlas row and surface "consumed" entries:** kept as history and read through §3.
- **`PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §4, research clause** ("a future research claim over those features needs a different untouched window or a prospective test"): replaced by §2–§3 for questions the product never read.
- **`DIRECTIONAL_HYPOTHESES_DECISION_V1` data rule** ("no 2025/2026 object"): it bound DH1–DH3, which are closed. New units follow §2–§3.
- **Generator red-team gates that closed predictive cards for missing causal identification:** removed (§6).

## 10. Effect on the catalog red team

See `MARKET_PHENOMENA_CATALOG_V1_RED_TEAM.md` §13.
