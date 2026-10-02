# Beta — Historical Follow-up V0 (foundation only)

**Question it answers:** "What happened after previous comparable states?"

It is descriptive historical evidence. It is **not** a predictive signal, a direction call, a probability, trading advice or a causal claim.

**Status:** `FOUNDATION_ONLY / NOT_WIRED_INTO_BTC / NO_HISTORICAL_REPLAY`.
**2026-10-02:** `BETA_HISTORICAL_ANALOGUE_GATE_V1.md` builds on this foundation and permits direction medians under its rules (baseline, N, spread, mandatory verdict, separate cohorts). This document's range-only output and directional-word guard remain the V0 behavior.
- Code: `beta/comparability.py` and `beta/followup.py`. Both are pure and do no I/O.
- Tests: `tests/beta/test_beta_followup.py`.
- `/btc`, the detector, rules, `rules_digest`, episodization, the state tape, percentiles, Stage-2 features, push and the `beta/outcomes.py` formulas are all unchanged.
- The original prospective Q1/Q2 is superseded before any inspection. See the 2026-09-28 amendment in `research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md`.

## 1. `EVENT_COMPARABILITY_V0`

This is a narrow semantic identity: would two episode observations have the same market-state definition **and** the same outcome semantics? It is the canonical JSON of the payload below, hashed with SHA-256. `comparability_payload` returns the human-readable payload.

| Field | Why it changes comparability |
|---|---|
| `comparability_version` | Version of this identity itself. |
| `symbol`, `market_type`, `timeframe` | Different market or bucket grid. |
| `event_type` | Different event types never compare. |
| `rules_version` (`BETA_EVENT_RULES_V1`) | Authoritative version of the rule predicates and lifecycle code (`beta/rules.py`, `beta/detector.py`). |
| `rule` — only the keys this event type reads | Thresholds decide which buckets qualify. Streaks decide when an episode arms or triggers. `max_duration_min` decides when a build-up episode expires and a new one can start. `enabled` gates existence. Keys of sibling events are excluded: a TAKER SELL threshold never changes TAKER BUY identity. |
| `gates.active_exchanges` (sorted) | Venues entering consensus, liquidation voting and the reference price. |
| `gates.min_venue_coverage` | Family usability, and whether a reference price (the outcome denominator) exists. |
| `gates.percentile_window` | Every rule compares 30d percentile ranks. |
| `gates.max_state_age_s` | Gates `evaluation_fresh`, hence NOT_EVALUABLE, hence which episodes exist. |
| `features.stage2_calculation_version` | Hash of Stage-2 `feature_schema_version`, the Stage-2 config hash (including the percentile maturity tiers that gate every rule) and the path-scoped feature-computation code version. Percentile history is already partitioned by it. |
| `features.detector_feature_semantics` | Semantics class of the episode's state-tape schema. Schema 1 and 2 map to the same class, because V2 only added keys and the tape treats V1 and V2 rows as the same percentile history (`PERCENTILE_HISTORY_SCHEMA_VERSIONS`). A future schema that changes detector features must map to a new class; an unknown schema fails closed. |
| `outcome_version` | Definition of the measured forward outcome. |

Percentile thresholds are normalized to real numbers, so `1` and `1.0` are the same threshold.

**Deliberately excluded:**
- `rules_digest`: it covers `state_schema_version`, so the V1→V2 serialization change reset it.
- `config_digest`, and raw `state_schema_version`.
- `episodization` and `context`: presentation projection, LAST EVENT retention and 1h labels.
- Push, cooldown, TTL, daily cap, `bucket_close_grace_s` and `forward_horizons`: the horizon is carried per statistic instead.
- `feature_schema_version` and the Stage-2 config hash as separate fields: both are inside `calculation_version`.

**Limitation.** An episode row stores its `rules_digest`, not the rule values. A stored episode is keyed with `episode_comparability(cfg, …)`, which fails closed unless `cfg` reproduces that `rules_digest`. A new Stage-2 `calculation_version`, for example after a feature-code change, conservatively starts a new comparable history.

## 2. What is shown

- Horizons: **1h and 4h** only.
- Outcome: **`realized_range_pct`** only, meaning absolute range, with no direction.
- `close_return_pct`, `max_up_pct`, `max_down_pct` and the time-to-max fields stay internal to `beta/outcomes.py`. They are never aggregated or shown.
- **Event set.**
  - Included: comparable TRIGGERED episodes whose 1h **and** 4h outcomes are `COMPLETE` under the same `outcome_version`, and whose 4h window ended by `as_of`.
  - Excluded, and counted by reason: not comparable, provenance not included, not matured, or outcome not complete.
  - One event set is used for every statistic.
- **Display sufficiency** (`DISPLAY_SUFFICIENCY`, the single configuration point):
  - The rule is ≥ 10 events **and** ≥ 5 distinct UTC dates.
  - Below it, only counts are returned ("Limited comparable history · N events across D days"). No median, rate or baseline is computed.
  - The same rule applies separately to each baseline's own event subset.
- **Event statistic:** per horizon, `event_range_median` = median of `realized_range_pct`. It is displayed with two decimals.

## 3. Ordinary same-time baseline

What was normal around this time of day? This is **not** an incremental-information test.

- **Candidates:** the same UTC 5m slot as the event anchor on each of the 30 previous UTC dates. That gives at most one candidate per date, with none on the same day or later.
- **Eligibility:** a candidate must have `COMPLETE` 1h and 4h outcomes computed by the unchanged `compute_outcome`. Its 4h window must end by the event anchor. It must lie outside ±4h of **any** detector episode.
- **Per event:** the event needs ≥ 10 such controls (`ORDINARY_MIN_CONTROLS_PER_EVENT`). Its baseline is the median of its controls' ranges. So each event contributes one number, and overlapping 5m anchors cannot inflate the sample.
- **Reported:** `ordinary_range_median` is the median across events of those per-event baselines.

## 4. Volatility-matched baseline (Q1 spirit)

Does the state add information beyond the volatility regime that already existed before it?

- **Candidates:** LIVE/evaluable tape anchors (`evaluation_fresh` and core families usable), outside ±4h of any detector episode, with `COMPLETE` 1h and 4h outcomes, matured by `as_of`.
- **Match:** same UTC hour-of-day ±1h (circular), and the same tercile of the **previous 1h realized range**.
  - The prior range is computed by the unchanged composite formula over `[anchor − 1h, anchor)`, using only bars before the anchor.
  - Its tercile is a mid-rank against prior-1h ranges at anchors in `[anchor − 30d, anchor)`, requiring ≥ 7 days (2016 anchors) of reference values. Otherwise there is no tercile.
- **Selection:** up to 5 nearest-in-calendar-time controls, with the earlier candidate winning a tie. Controls are drawn without replacement across events, processed chronologically.
- **No relaxation:** an event with no match, or with no prior-volatility tercile, is excluded and counted.
- **Per event:** event range − mean of its controls' ranges.
- **Reported:** number of comparisons, number of distinct event dates, median difference in percentage points, and the descriptive count "range exceeded matched baseline in X of N events".
- **Never reported:** p-values, confidence intervals, probabilities, or likely/unlikely, alpha or edge wording.

## 5. Provenance

Every observation carries `LIVE_OBSERVED` or `RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA`. The summary `details` keep provenance counts for events and for both control sets. `summarize(…, provenances=…)` can restrict to one class; excluded observations are counted. Reconstructed history is never labelled live. `/btc` does not need to show provenance in V0.

## 6. Formatter foundation

`format_historical_follow_up` renders only the `user_facing` structure. It uses past-tense, descriptive wording and must pass `assert_descriptive`. On top of that, it rejects forward-looking or directional words (next, expected, will, edge, odds, up/down, long/short, p-value, significant and similar). It is **not wired** into `/btc`.

## 7. Deferred to historical replay (not in this PR)

- Reading comparable episodes, outcomes, episode windows and LIVE tape rows from PostgreSQL.
- Computing control candidates: forward outcomes and prior-1h ranges from 1m bars, and the 30d reference series for terciles.
- Detector replay over live-collected raw data, and writing reconstructed episodes, which must never go into the production episode tables.
- Any schema, index or storage change.
- Wiring the block into `/btc` or Details, and freezing the ordinary and matched parameters before any confirmatory use.
