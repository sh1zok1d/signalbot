# V2 Empirical Validation & Red-Team Plan

> Status: planned research/evidence track. This document does **not** change any frozen V2-v0 setup formula, threshold, lifecycle rule, `rules_version`, or current implementation scope. It defines how the project must distinguish engineering correctness from predictive/economic evidence and how V2 must be challenged before any claim of robust trading edge or user-facing promotion.

## 0. Core principle

Engineering correctness is necessary but not sufficient. A deterministic, no-lookahead, replayable system can still implement a market description that has no predictive or economic edge.

The empirical program therefore has an adversarial objective:

> **Attempt to falsify the trading hypotheses, not optimize the reported metrics.**

A failed hypothesis is an acceptable research outcome. A component, setup family, or even V2-v0 itself must be allowed to be simplified, demoted, or rejected if the evidence does not justify its complexity.

The project must keep these statements separate:

- `implementation is correct`;
- `setup definition is internally coherent`;
- `setup separates interesting future outcomes from comparable controls`;
- `setup has robust out-of-sample predictive value`;
- `setup remains economically useful after delay/costs`;
- `setup survives live shadow`.

Passing an earlier statement never implies a later one.

---

## 1. Evidence ladder

Use explicit evidence levels so GitHub progress cannot be confused with predictive knowledge.

| Level | Meaning | What it does **not** prove |
|---|---|---|
| `E0_CORRECTNESS` | deterministic formulas, no-lookahead, provenance, replay/storage correctness | predictive usefulness |
| `E1_DETECTOR_SEPARATION` | Stage-5 candidates differ from matched controls in a predeclared event study | executable episode edge |
| `E2_EPISODE_HISTORICAL` | full Stage-6/7/8 episodes have favorable historical metrics | OOS robustness or live equivalence |
| `E3_OOS_WALK_FORWARD` | frozen version survives untouched chronological validation / walk-forward | live operational validity |
| `E4_LIVE_SHADOW` | same forward live path survives required shadow evidence | automatic user-facing entitlement |
| `E5_PROMOTION_DECISION` | explicit human promotion decision under correctness contract | calibrated probability or guaranteed future edge |

A 30-day replay is primarily an `E0/E1` engineering/research polygon. It is **not** by itself evidence of durable edge.

---

## 2. Model-risk register — arguments against V2 that must remain explicit

1. **Market description != market prediction / formalized discretionary trading.**
   The setup families may precisely formalize visually plausible states without those states containing incremental information about future executable returns.

2. **The V1 -> V2 causal story is still a hypothesis.**
   `V1 is late/local -> MTF context will fix it` is plausible but unproven. V1 may instead be weak because the public features have little incremental predictive information, because direction itself is poor, or because edge disappears after realistic delay.

3. **Setup-selection bias.**
   `TREND_PULLBACK`, `COMPRESSION_BREAKOUT`, and `CONFIRMED_BREAKOUT` were chosen before empirical validation. The choice itself may encode human hindsight/preferences even with perfect code-level no-lookahead.

4. **Researcher degrees of freedom / human overfit.**
   Repeatedly inspecting failures and adding filters, thresholds, regime exceptions, features, or new setups can turn the researcher into the optimizer.

5. **Parameter brittleness / magic-threshold risk.**
   Apparent edge may exist only at one exact retracement bound, percentile threshold, lookback, confirmation age, buffer, confidence threshold, or other versioned constant.

6. **Small sample / BTC-only concentration.**
   One symbol, one market type, three setup families, and episode-level sampling can yield little effective evidence even over long calendar periods.

7. **Correlated observations / overstated effective N.**
   Multiple decisions inside one episode are repeated measurements. Separate episodes may also cluster inside one latent market move/regime.

8. **Regime dependency / non-stationarity.**
   A family can be excellent in trend/expansion and poor in chop/news/another market era. Aggregate averages can hide this.

9. **MTF latent-information duplication.**
   4h regime, 1h bias, 15m setup, and 5m trigger have distinct semantic roles, but statistically they may still reflect one underlying price impulse. Better structure/UX does not guarantee more information.

10. **Feature redundancy / complexity tax.**
    OI, funding, liquidations, taker flow, HTF context, and other features may add little over price structure while increasing failure and maintenance surface.

11. **Cross-exchange consensus may be robustness, not independent evidence.**
    Binance/Bybit/OKX observe the same BTC market. `3/3 agrees` must not be treated psychologically as three independent experiments without demonstrated incremental information.

12. **Potential alpha may live in venue differences rather than agreement.**
    Lead/lag, OI/flow/funding divergence may contain more incremental information than common direction. This is a future hypothesis only; it must **not** be added before current V2 earns evidence.

13. **Liquidation feeds are not semantically identical instruments.**
    Venue feeds differ in completeness/aggregation semantics and liquidation history is not equivalent to live availability. Absolute cross-venue comparisons require explicit feed-semantics handling.

14. **Historical feature availability may not be live-equivalent.**
    OHLCV, taker flow, OI, funding, and liquidation coverage differ by venue and period. A detector being computable historically does not mean it saw the same information environment it would see live.

15. **Coarse-source upsampling can create pseudo-information.**
    Forward-filling 5m OI to 1m must never allow downstream features to infer minute-level timing/slope/acceleration that the provider did not publish.

16. **Simple-baseline risk.**
    V2 may fail to outperform a simple price-structure, lower-timeframe, V1, or time-matched randomized baseline under identical delay/cost semantics.

17. **Multiple-comparison / subgroup cherry-picking risk.**
    Direction/family/regime/volatility/session/confidence breakdowns create many opportunities for chance findings.

18. **Replay-to-live gap.**
    Replay can pass while live shadow fails because of publication timing, missing data, latency, outage behavior, revisions, or different feature availability.

19. **Cost/delay sensitivity.**
    Positive expectancy may depend on optimistic user-action delay, fees, spread/slippage, or exact entry assumptions.

20. **Missing-data survivorship bias.**
    Data gaps may correlate with volatility. Dropping incomplete episodes can selectively remove the hardest periods from the denominator.

21. **Model confidence may not order outcome quality.**
    `model_confidence` is an evidence-strength score, not a calibrated probability. Its empirical monotonic relation to actionability/MFE/MAE/utility remains an open hypothesis.

22. **Setup-family overlap may make three families less distinct than assumed.**
    If families repeatedly identify the same latent market event, aggregate episode counts and apparent diversification may be overstated.

23. **Architecture can outrun evidence.**
    New feeds, ML, order book, CoinGlass, more symbols/setups, adaptive thresholds, and automatic tuning increase overfit surface before the current hypothesis has earned its complexity.

---

## 3. Work that starts **before** Stage 8

The empirical track begins now. Stage 8 remains the canonical full episode evaluator, but cheap falsification work must not wait for it.

### 3.1 Formal V1 diagnosis — start now

Produce a reproducible report from persisted V1 predictions/outcomes. At minimum:

- exact date range and model/version identities;
- total predictions and clustered/episode-like market-event count;
- LONG/SHORT split;
- 15m/1h/4h directional results;
- MFE/MAE distributions;
- post-notification/post-delay MFE and MAE where timestamps permit;
- late-signal fraction / fraction of move already consumed;
- performance by confidence bins/deciles;
- performance by component/reason where reproducible;
- volatility/regime/time-of-day diagnostics, clearly labeled exploratory unless predeclared;
- consecutive-signal clustering;
- missing/data-quality statistics;
- V1 vs simple momentum/price-structure baseline;
- V1 vs simple breakout baseline;
- V1 vs time-matched randomized control with similar frequency/direction/time-of-day distribution.

The report must explicitly classify which explanation is best supported:

- V1 direction is weak;
- V1 direction is useful but signal is late;
- V1 complexity does not beat simple price structure;
- one/few components appear useful while others add little;
- evidence is insufficient.

This report is diagnostic evidence, not a reason to silently retune frozen V1.

### 3.2 Research ledger — start now

Every model/research change must record:

- hypothesis ID and date;
- hypothesis stated **before** result inspection or marked exploratory/post-hoc;
- proposed model/config change;
- causal/economic reason;
- primary metric and expected direction;
- data windows touched;
- whether any validation/OOS window has been viewed;
- result (`+`, `0`, `-`, inconclusive);
- keep/reject/defer decision;
- model/rules version affected.

Every viewed holdout consumes research budget. A viewed OOS period cannot remain an untouched OOS period for a modified model.

### 3.3 Historical data-semantics / live-equivalence audit — start now

Before headline historical V2 evaluation, every episode/sample must be classifiable by data environment. Introduce/define an evaluation concept equivalent to:

- `LIVE_EQUIVALENT` — required feature families and feed semantics match the live decision path for that version;
- `PARTIAL_HISTORICAL` — decision is computable but one or more live feature families are absent/degraded historically;
- `NON_COMPARABLE_FEED_SEMANTICS` — nominal feature exists but feed meaning/completeness is not comparable enough for the intended analysis;
- `NOT_EVALUABLE` — required correctness/data path is unavailable.

The exact persisted representation belongs to a later implementation/contract decision; the **requirement to separate these evidence classes is mandatory for the research plan**.

Headline performance must never silently mix tiers as if they were the same model information environment.

### 3.4 Provider-granularity invariant audit — start now

Audit OI and every other coarsely sampled source that is upsampled/forward-filled.

Required invariant:

> **No downstream model/feature may extract event timing, slope, acceleration, compression, or independent sample count from temporal granularity the provider did not supply.**

Specifically determine whether 5m OI ffilled to 1m can produce artificial four-minute flatness followed by a one-minute jump in any percentile/change/slope/acceleration feature. If yes, treat as a correctness/research blocker and redesign source-time semantics before relying on those historical features.

### 3.5 Pre-register baselines and negative controls — start before event study

Baseline definitions must be fixed before seeing the candidate-study result. Minimum baselines:

- frozen V1 where comparable;
- simple 4h trend + 5m breakout;
- simple 15m breakout/pullback price structure;
- time-matched random control preserving approximate frequency, direction prevalence, and time-of-day distribution;
- trivial/null control needed to expose BTC drift/regime exposure.

Negative controls:

- **time-shift control:** shift candidate times by predeclared random offsets within comparable chronological blocks/day;
- **direction inversion:** LONG <-> SHORT;
- **feature permutation:** permute OI/taker/liquidation evidence within valid chronological blocks without introducing lookahead;
- **venue permutation:** permute venue identities for selected feature families where semantics allow.

If a negative control performs similarly to the real signal, treat that as evidence against incremental information.

### 3.6 Stage-5 detector event study — immediately after coherent replay foundation (H2e)

This is **not** a full V2 backtest and does not require pretending Stage-6 episode semantics already exist.

For every Stage-5 candidate/qualification point, collect:

- `T`, family, direction, model/rules/calculation identities;
- market/reference price at `T`;
- +15m/+30m/+1h/+2h/+4h returns;
- MFE/MAE and time-to-MFE over predeclared horizons;
- available input/data-quality/provenance tier;
- matched baseline/control outcomes.

Primary question:

> **Do Stage-5 detectors separate future market behavior from comparable random/simple moments at all?**

If there is no meaningful separation, the state machine must not be expected to create predictive information magically. Continue correctness work as needed, but trigger an explicit hypothesis review before adding signal intelligence.

---

## 4. Unit of analysis and denominator discipline

### 4.1 Episode is the primary sample unit

After Stage 6, the primary research sample is `episode_id`, not every 5m decision/state update.

State updates inside one episode are repeated measurements. Reports may describe them operationally but must not count them as independent predictive successes.

### 4.2 Clustered episodes

Report temporal clustering and, when material, estimate effective evidence below raw episode count. Do not quote `N episodes` as if all N were independent when many belong to one volatility/news/regime block.

### 4.3 Missing/incomplete denominator

Never do:

`data-gap episode -> drop -> recompute performance on survivors`.

Always report a denominator tree such as:

- all detected/candidate episodes;
- confirmed;
- actionable;
- late / invalidated-before-entry;
- path-complete;
- incomplete due to data gap;
- non-comparable due to feed semantics;
- terminal outcomes.

The existing correctness-contract population rules remain authoritative; this research view adds transparency, not a competing promotion denominator.

---

## 5. Full post-Stage-8 empirical red-team program

### 5.1 Freeze before evaluation

Before opening the designated validation/OOS result, record:

- `rules_version`;
- calculation/code/decision identities;
- dependency/execution-environment identity or lock artifact used for the run;
- exact historical data revision/snapshot boundaries;
- data-equivalence tier rules;
- cost and delay assumptions;
- populations and primary metrics;
- baselines and negative controls;
- planned subgroup/regime analyses;
- parameter-neighborhood tests.

No silent tuning under the same identity.

### 5.2 Chronological validation only

Random train/test splits are not accepted for primary evidence because overlapping timeframes and clustered episodes violate the independence intuition behind random shuffling.

Use chronological development/validation/OOS blocks and, when sample size permits, multiple walk-forward folds.

If OOS causes a model change, the modified model is a new version and requires new untouched evidence. The consumed OOS becomes development evidence for that new version.

### 5.3 Parameter-sensitivity / neighborhood stability

For every economically material versioned parameter, test a small **predeclared** neighborhood around the frozen value.

Goal: detect brittle magic points, **not** search the grid for a better parameter.

Red flag: exceptional performance at one exact value with collapse at nearby values.

Positive evidence: broadly similar economic behavior across a reasonable local region; the frozen value need not be the numerical optimum.

### 5.4 Ablation — each component must earn the right to stay

At minimum compare full V2 against controlled removals where semantics permit:

- no OI;
- no funding;
- no liquidations;
- no taker flow;
- no cross-exchange predictive confirmation;
- no 4h regime conditioning;
- no 1h bias conditioning;
- price-structure-only / lower-TF structure baseline.

If removal does not degrade OOS/generalization, the removed component has not demonstrated incremental predictive value. Simplification is a valid success outcome.

### 5.5 Cross-exchange contribution test

Compare, where technically comparable:

- Binance-only/reference venue;
- reduced venue set;
- canonical Binance+Bybit+OKX consensus;
- simple median/robust aggregation baseline.

Interpret exchange agreement first as **cross-venue robustness**. Do not grant extra model certainty merely because multiple highly correlated venues agree unless empirical contribution justifies it.

### 5.6 Setup-family distinctness / overlap

Report overlap/correlation among setup families:

- same/nearby detection windows;
- same direction;
- same latent market-move cluster;
- outcome correlation.

If multiple families repeatedly identify the same event, do not present them as independent diversification or inflate effective sample size.

### 5.7 Model-confidence ordering test

Without treating confidence as calibrated probability, test whether higher `model_confidence` bins consistently order useful outcomes such as:

- entry feasibility;
- post-delay MFE;
- MAE;
- cost-adjusted utility.

No monotonic/meaningful ordering means confidence remains an explainability score only and must not receive stronger empirical interpretation.

### 5.8 Regime stability and concentration

Use a small predeclared regime taxonomy with adequate samples. Report:

- family x regime metrics;
- direction concentration;
- calendar-period concentration;
- contribution of top few episodes/blocks;
- whether almost all apparent edge is one volatility/news episode.

Tiny cells are `NOT ENOUGH EVIDENCE`, never selectively highlighted as proof.

### 5.9 Statistical uncertainty / effective evidence

Report sample counts and calendar spans with every headline metric.

Freeze an uncertainty method suitable for serially correlated episode data before confirmatory evaluation (e.g. block/bootstrap or another justified time-series method). If many model/parameter configurations are ever explored, add an explicit backtest-overfitting/multiple-testing analysis rather than relying on a single conventional holdout statistic.

Current minimum sample thresholds remain engineering promotion minima, not proof of statistical significance.

### 5.10 Cost and delay stress — use a curve, not one point

Canonical contract assumptions remain canonical for promotion, but research sensitivity must test realistic adverse alternatives.

At minimum evaluate a predeclared delay grid such as:

`0s, 15s, 30s, 60s, 120s`

or, preferably once measurable, an empirical notification/action-delay distribution.

For each delay ask:

- entry zone still feasible?;
- invalidation already occurred?;
- MFE remaining after the user could act?;
- MAE after feasible entry?;
- resulting RR/utility?;

Also stress conservative round-trip cost/slippage assumptions. An effect that disappears under a small realistic worsening is fragile.

### 5.11 Baseline challenge

Full V2 must be compared under the **same** calendar periods, delay/cost assumptions, and denominator semantics against the pre-registered baselines.

Positive raw returns alone are insufficient evidence for V2 complexity.

### 5.12 Negative controls

Run the pre-registered time-shift, direction-inversion, feature-permutation, and venue-permutation controls where valid.

A real model should meaningfully outperform controls that deliberately destroy the purported causal/informational structure while preserving broad market exposure.

### 5.13 Multiple-testing ledger

Every parameter/model/filter/subgroup inspected is recorded. Exploratory findings can motivate a **future version** but cannot be retroactively presented as confirmatory evidence for the version that generated them.

---

## 6. Per-component falsification matrix

Every complex component must have an explicit condition under which its predictive role is removed or demoted.

| Hypothesis | Required challenge | Falsification / downgrade signal |
|---|---|---|
| V1 is mainly weak because of lateness | formal V1 post-delay MFE/MAE + direction diagnosis | direction remains weak even when residual move exists; lateness is not dominant explanation |
| MTF improves quality | full V2 vs lower-TF/simple price baselines | no stable OOS improvement |
| 4h regime adds selectivity | ablation without 4h conditioning | no degradation / better generalization without it |
| 1h bias adds information | ablation without 1h conditioning | no degradation / better generalization without it |
| OI adds position-information | OI ablation on comparable data | no-OI is indistinguishable or better OOS |
| Taker flow adds information | taker-flow ablation | no-flow is indistinguishable or better OOS |
| Liquidations add information | liquidation ablation on live-equivalent evidence | no-liquidations is indistinguishable or better |
| Funding adds intraday information | funding ablation | no incremental value |
| Three-venue consensus adds information | single/reduced/median vs full consensus | full consensus adds negligible predictive benefit; retain at most reliability role |
| Three setup families are distinct | event overlap/outcome-correlation analysis | mostly same latent events / no meaningful differentiation |
| Confidence orders quality | outcome curves by confidence bins | no stable monotonic relationship |
| V2 beats V1 | same-period comparable evaluation | no meaningful improvement |
| V2 beats simple TA | pre-registered simple baseline | no meaningful improvement |
| Edge survives execution | delay/cost stress | advantage disappears at realistic delay/cost |
| Edge is not one-regime artifact | chronological/regime/concentration analysis | result dominated by one narrow regime/block |

---

## 7. GO / KILL / SIMPLIFY gate after Stage 8

Stage 8 completion does **not** automatically authorize Stage 9 product work.

Before Telegram V2/user-facing promotion, hold an explicit empirical gate:

### `GO`
Continue toward shadow/product only if the frozen model shows meaningful evidence beyond simple controls, survives required correctness/acceptance metrics, and has no unresolved critical research-validity blocker.

### `SIMPLIFY`
Remove/demote components or setup families whose incremental value is unsupported. A simpler model with equal generalization is preferable to unexplained complexity.

### `KILL / RETHINK`
Treat V2-v0 as not having demonstrated its hypothesis if, for example:

- no positive cost-adjusted OOS utility;
- no meaningful separation from simple/time-matched controls;
- effect disappears under small parameter perturbations;
- result depends on one/few episodes or one narrow regime;
- full V2 does not materially beat simpler price structure;
- repeated retuning is needed after each validation window;
- replay and live shadow disagree systematically;
- required evidence cannot be accumulated for a family in a reasonable period.

`KILL` is a valid research result, not a project failure. The ingestion/replay/evaluation platform remains useful for a new hypothesis.

---

## 8. Expansion freeze

Until the current V2 families survive the evidence program, do **not** use weak performance as justification to add:

- new setup families;
- order book;
- spot/CVD;
- CoinGlass/vendor feeds;
- macro/news features;
- ML;
- adaptive thresholds;
- automatic tuning;
- new scoring dimensions;
- multi-symbol expansion for the purpose of rescuing the current hypothesis.

Any future source/feature requires a separately stated hypothesis and later ablation/baseline evidence of incremental value.

---

## 9. Required artifact before claiming robust V2 edge

Produce a version-pinned validation report containing at minimum:

- exact model/rules/calculation/decision identities;
- dependency/execution-environment identity;
- exact data windows and data-equivalence tiers;
- sample sizes, calendar spans, and clustering/effective-evidence notes;
- canonical acceptance metrics and denominator tree;
- V1 diagnosis summary;
- Stage-5 event-study result;
- chronological OOS/walk-forward results;
- parameter-sensitivity results;
- ablation results;
- baseline and cross-exchange comparisons;
- negative-control results;
- setup-overlap/distinctness analysis;
- confidence-ordering analysis;
- regime/concentration analysis;
- execution delay/cost stress;
- data-completeness/feed-semantics analysis;
- all failed as well as passed tests;
- research-change/multiple-testing ledger;
- explicit conclusion such as `NO ROBUST EDGE SHOWN`, `RESEARCH_ONLY`, `SIMPLIFY`, `SHADOW_ELIGIBLE`, or the contract-defined promotion state supported by the evidence.

No one backtest, one 30-day replay, one good regime, one Sharpe number, one win rate, or one passing correctness suite constitutes proof of edge.