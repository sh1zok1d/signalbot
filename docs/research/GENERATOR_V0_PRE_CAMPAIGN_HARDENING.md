# Generator V0 — pre-campaign hardening (V03)

**Status:** `IMPLEMENTED`, offline only
**Date:** 2026-10-02
**Record:** `GENERATOR_V0_PRE_CAMPAIGN_HARDENING.json`
**Tests:** `tests/research/test_generator_v0_v03_hardening.py`

```
LLM_CALLS              = 0
MARKET_OUTCOMES_OPENED = false
NEXT_UNIT              = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (paid; waits for owner live authorization and provider keys)
```

## 1. Memory finalizer accepts V03 campaigns

`memory_finalizer` accepts the V03 red-team check `RUNG_CONSISTENT` and the V03 card fields `COMPLEXITY_CLASS` and `COMPONENTS`.

**It validates and copies; it never decides.**
- **Validation.** It checks the shape of the ladder fields against the frozen ladder, and that the red-team check set is exactly the V03 set.
- **Copying.** It copies the ladder fields and every critic output verbatim onto the attempt record.
- **Blocker mapping.** It appends one blocker rule after all V02 rules: a failed `RUNG_CONSISTENT` gives `METHOD_RUNG_INCONSISTENT`.
- **Provenance.** V03 deltas record `GENERATOR_CONTRACT`, and V03 events add `FINALIZER_RULES_V03` to their rules digest.

**Refused:**
- mixing ladder fields into a non-V03 campaign;
- a V03 card with a bad class or component count;
- a run without a completed result.

**V02 unchanged.**
- The V02 rules digest still equals the published chain head's `RULES_DIGEST`.
- For a V02 mock campaign, `main` and this branch produce byte-identical deltas (`674bd61a…`): the same rules digest, source digest, resulting memory digests and counts.
- Only event hashes differ, because every event records the finalizer's code digest.

## 2. Budget-stop semantics (frozen for V03 campaigns)

A budget stop before all 40 slots and all mandatory reviews are complete sets the status `INCOMPLETE_BUDGET_STOP`.
- **No official shortlist.** No campaign result is written.
- **Partial work is kept, not counted.** Partial cards and the full journal are kept, and the event records the progress. They are not a completed shadow campaign and cannot be finalized into memory.
- **Resume only of the same run.**
  - Config, `GENERATOR_CONTRACT`, `LADDER_IDENTITY` (slot plan, rules, prompts, quota), routing identity and code must be identical.
  - Calls already obtained are replayed from the journal and never sent again.
  - The cap may change only through `authorize-budget-extension`, which is recorded and bounded by the owner ceiling.
- **After a full resume,** the 2/2/1 shortlist is built once, by the normal rule.
- **V02** keeps `STOPPED_BUDGET`, unchanged.

## 3. Campaign plan (unchanged)

- **Slots:** 40, split 16 / 14 / 7 / 3. **Shortlist:** 2 / 2 / 1.
- **Budget:** a hard cap of USD 12 with `--accept-budget-stop`.
- **No design changes after the first live call.**
- **Entry point:**

```
python -m scripts.research.generator_v0 ladder-40-card --allow-real-llm --budget-usd 12 \
  --accept-budget-stop --actor owner --reason "<reason>" --run-dir <dir>
```

| Role | Model / provider | Params | Max output tokens | Logical calls | Max attempts |
|---|---|---|---|---|---|
| GENERATOR | claude-opus-5-5 / Anthropic | effort high | 100,000 | 4 | 4 (no content retry) |
| NOVELTY_CRITIC | gpt-6-sol / OpenAI | reasoning high | 12,000 | 40 | 80 |
| RED_TEAM | gpt-6-sol / OpenAI | reasoning high | 8,000 | 40 | 80 |
| FEASIBILITY_CRITIC | gpt-6-luna / OpenAI | reasoning low | 6,000 | 40 | 80 |
| SELECTOR (advisory) | gpt-6-luna / OpenAI | reasoning none | 2,000 | 1 | 1 |
| **Total** | | | | **125** | **≤ 245** |

Routing digest: `f44b5418…`.

**Offline worst case** (conservative: maximum-size proxy cards and full output caps; no calls made):

| | USD |
|---|---|
| Single attempt | 30.749115 |
| With critic content retries | 61.496292 |
| Generation, 4 rounds | 8.84 |
| Novelty critic ×40 | 17.43 |
| Red team ×40 | 4.25 |
| Feasibility critic ×40 | 0.22 |
| Selector | 0.002 |

**Expected spend is about USD 7–8.** This is scaled from GV0R01, which actually spent USD 5.09 on 30 cards and 93 calls against a USD 19.52 bound.

The cap of USD 12 is below the worst case, so the run uses `--accept-budget-stop`. A stop at the cap ends as `INCOMPLETE_BUDGET_STOP` with no shortlist.

**Prerequisites for the live run:**
1. The owner's live authorization, naming the budget, roles and call limits.
2. `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in the environment; both are absent in the preparing session.
3. A verified `main` checkout.
