# Product direction V0 — decision record

**Status:** `OWNER_DIRECTION_RECORDED / NO_SCOPE_AUTHORITY / PARTLY_SUPERSEDED_2026-10-02`
**2026-10-02:** `PRODUCT_FIRST_DECISION_V1.md` is the canonical product decision. Superseded here: the claim ledger as a product feature, the evidence corpus as the main product bet, the stricter monetization checkpoint of §6 (payment is tested directly in the 30-day user test, U3) and the diagnosis that only research-backed claims can give a reason to pay. Kept as recorded owner thinking: §2 (what is not a moat), §3.5 (personal decision history, now on the DO-NOT-BUILD-YET list) and §7 positioning.
**Date:** 2026-10-01
**Review at:** the beta checkpoint, 4 weeks after the first external user (`PRIVATE_BETA_V0_RESTART_DECISION.md`, success and exit criteria)

**Scope of this record.** It records what the owner and the agents concluded about where Signalbot has to go to become defensible.
- **It authorizes no scope change.** The beta stays frozen as it is. Every item marked "decision needed" below needs its own owner decision.
- **It changes no research rule.** `HYPOTHESIS_EVALUATION_CONTRACT_V1` governs all evidence.
- **Inputs:** `PRODUCT_DIRECTION_AFTER_BETA_PROPOSAL.md`, which remains the comparison list for the checkpoint, and `research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`.

## 1. Diagnosis (2026-10-01)

**The product today is a descriptive summary.** It shows what is happening and what changed. Competitors give the same information cheaply or for free. There is no moat.

**Users need a finished state, not raw information:**

**situation → evidence → implications → decision context**

Signalbot never says BUY or SELL. An illustrative message (not a result):

> TWAP selling continues.
> In comparable confirmed episodes, extra downward drift persisted 1–6h.
> Current conditions match X of Y features.
> So chasing a long right now carries higher risk.

**No charging now.** There is nothing yet that gives a reason to pay.

## 2. What is not a moat

- **Formats and features:** summary screens, alerts, risk and position calculators, pre-trade checks, TWAP or flow detectors, multi-asset scanners, hour-of-day maps. All of them already exist and are copied in weeks.
- **Storing raw exchange data:** "we keep Binance/Bybit/OKX" is not a moat.

## 3. What can become a moat

Moats here are assets that accumulate over time and cannot be rebuilt retroactively.

**1. An accumulated evidence base on market states (the main bet).**
- **What it is:** a corpus of tens to hundreds of claims. Each is formulated in advance, registered, tested against a comparator, replicated on a time-disjoint surface, and kept with its history of failures.
- **Why one result is not enough:** a single result, such as the TWAP study, can be repeated by a competitor. The corpus is the moat.
- **First test:** the TWAP study is the first test of whether such claims can be produced at all.

**2. An immutable claim ledger.** For every claim, the ledger records:
- what Signalbot said, when, and on what data;
- what happened next;
- how well it matched the stated claim.

It is a ledger of claims and states, not of "predictions". A new competitor can copy the interface and the detectors. It cannot copy a past year of honest, timestamped claims.

**3. A record of what Signalbot could know at the time.** The value is not the raw tape. It is what cannot be reconstructed:
- live classifications and detector states at each moment;
- episode boundaries;
- provenance and what-was-known-then snapshots;
- our own derived microstructure features.

The beta state tape has been collected since 2026-09-25 and is the start of this.

**4. The research pipeline.** Mechanism-first generation, the V1 contract, the feasibility compiler and the null ledger are harder to copy than any one result.

**5. A personal decision history.** This is the strongest switching cost later, and out of scope now. A read-only account link would allow statements like: "in the last 4 months you entered after this state 17 times; your average result here is worse than your baseline". No product can reproduce that history on the day a user signs up. An unknown bot will not be trusted with keys, so this waits for an established product (decision needed).

## 4. Moat levels over time

| Horizon | Moat |
|---|---|
| Today | research process + first proprietary live records |
| Months | evidence corpus + claim ledger |
| A year and more | an accumulated calibration reputation + users' personal decision histories |

## 5. Bets and how we will judge them

| Bet | Working if | Not working if |
|---|---|---|
| Evidence corpus (§3.1) | The first V1 cards produce `SUPPORTED` claims that pass the usefulness test in §6 | After about 10 V1 mechanism cards (or about 3 months), not one claim passes §6. The unique-content thesis is then false for now: pivot (for example to multi-asset attention) or stop, and do not add features. |
| TWAP as the first content test | The L1 mechanism gate passes and L2 holds on discovery and replication | Too few episodes for the feasibility gate, an L1 failure, or an L2 failure. That closes this mechanism only, not the corpus bet. |
| Claim ledger (§3.2) | Claims are frequent enough to accumulate, and users look at the record | Under a handful of claims a month, or the record goes unread in beta telemetry and interviews |
| Live records (§3.3) | At least one V1 card or product claim uses data only Signalbot recorded live, within 6 months | Nothing uses it. It is then storage, not an asset. |
| Retention of the current bot | The beta CONTINUE criteria are met | The beta CHANGE PRODUCT or STOP criteria are met |

## 6. Monetization checkpoint (stricter)

Charging is considered only when there is at least one proven claim that:
1. passed V1 (supported and replicated) and its promotion gate; **and**
2. a user does not get in an obvious way from an ordinary chart; **and**
3. changes the user's decision or risk assessment.

A scientifically real but obvious claim is not enough. "Volatility rises after X" is an example.

## 7. Positioning

**A risk co-pilot that does not lie.** Signalbot does not win on the number of indicators. It owns a history: we observed state X, claimed Y in advance, tested it on Z, and here is our accuracy and when we were wrong.

## 8. Decisions needed before the matching work

These are not authorized here:
- **Publishing a claim ledger, and live evaluation on 2026 data.** Both fall under the protected-data rules.
- **A trade-stream collector for live TWAP detection.** The beta is frozen.
- **A read-only account link for the personal layer.** This is a scope, security and privacy decision.
- **Multi-asset scope.**

## 9. Checkpoint review

At the beta checkpoint, open this record and write down, for each assumption in §§1, 3 and 5, whether it held, changed or was dropped against user evidence. Two questions are asked explicitly in the interviews:
- would users give a read-only key in exchange for an analysis of their own trades;
- would a public claim record change their trust.
