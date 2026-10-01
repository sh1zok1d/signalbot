# Product direction after the private beta — proposal

**Status:** `PROPOSED / DEFERRED_UNTIL_BETA_RESULTS / NO_AUTHORITY`
**Date:** 2026-10-01
**Origin:** owner conversation on 2026-10-01. The owner endorsed this direction as the plan to compare against beta evidence. It is not an authorization.

**Scope of this document:**
- It changes nothing in `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`: scope, soak gate, rollout, and exit criteria stay as they are.
- It changes no research rule and does not override `docs/SIGNALBOT_MANDATE_V1.md`.
- Each item that widens the product scope needs its own owner decision.
- Research items go through the post-D7 methodology review (`docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1_PROPOSAL.md`).

## Premise

The descriptive `/btc` screen alone largely duplicates free dashboards (Coinglass, Velo, TradingView). It will not retain traders by itself.

Value has to come from what a trader will not do alone:
- being told **when** to look;
- getting an **honest answer to "so what?"**;
- having **more than one market scanned at once**.

## Sequence

1. **Observe first (weeks 1–3 after the first external user).** Build nothing new.
   - The primary metric is whether users open the bot **without a reminder**.
   - Talk to each trader for about 15 minutes every week: when they opened it, why, and what was missing.
   - Track which horizon tabs they actually open (`beta_details_opens`).
2. **Push alerts (the main lever).** A bot a user has to remember to query is forgotten within a week. The product is the bot tapping the trader on the shoulder when BTC does something unusual.
   - Alert quality is the product: few messages a day, per-type mute, and quiet hours. Noisy alerts get muted, and a muted bot is dead.
   - Push follows the existing rollout of the restart decision: owner-only push first, then the soak and Useful/Noise votes.
3. **An honest answer to "so what?"** For example: "after comparable events the next 4h range was typically 2× normal, on N cases".
   - No direction and no long/short.
   - Foundation: `beta/followup.py`, which is not wired yet.
   - D7 is the first research-backed context of this kind.
4. **Research serves the product.**
   - Next hypotheses are framed as product questions, for example: does an alert mark materially different next hours than matched ordinary periods?
   - Each hypothesis is time-boxed, for example about one week.
   - Process weight matches the claim: a lighter path for context claims, full confirmation for anything framed as trading-relevant. This is an input to the post-D7 methodology review. D7 took about three days to support one line of context.
5. **Multi-asset scan.** "What is unusual right now across the top ~20 liquid perpetuals." No human can watch 20 markets at once. This may become the main feature, which is also what the scalper interview asked for.
   - It comes only after BTC shows retention.
   - It needs a scope decision, because other assets are currently excluded.
6. **Willingness to pay.** Once 4–5 users use the bot weekly without reminders and say they would miss it, ask a few of them for about $10–20 a month. Payment is the honest test of value.

## Not doing

- **Entry calls, direction, long/short.** One false call and the bot is deleted, as the scalper interview said explicitly.
- **Order book, liquidity walls, heatmaps.** That is a costly race with specialised tools, outside our strength.
- **More features when users do not return.** If, a month after push is live, users do not come back on their own, pivot (for example to the multi-asset scan) instead of extending the current screen.

## Positioning

**"The bot that does not lie."**
- Every statement is backed by tested evidence.
- Where there is none, the bot says it does not know.
- It never fakes a prediction.

That is rare among crypto Telegram "signal" bots and is the basis for trust.

## Review trigger

Revisit at the beta CONTINUE / CHANGE PRODUCT / STOP checkpoint, four weeks after the first external user, against the observed metrics and interviews. Record which items were confirmed, changed, or dropped.
