# Private Beta V0 — restart decision (descriptive attention engine)

**Status:** `OWNER_AUTHORIZED / IMPLEMENTED_OFFLINE / NOT_ACTIVATED`
**Date:** 2026-09-25
**Contract:** SIGNALBOT PRIVATE BETA V0.2 implementation contract (owner-authorized design, anchor `0af0ce5`)
**Operating mode:** `RESEARCH_FIRST / DESCRIPTIVE_PRIVATE_BETA_V0_AUTHORIZED / PREDICTIVE_PRODUCT_FROZEN`

## Decision

1. **No edge.** Signalbot still has no validated, durable trading edge. Nothing in this decision claims one.
2. **Predictive product stays frozen.** Legacy predictive product development remains frozen.
3. **V1 and V2 stay frozen.** V1 and V2 forecasting semantics are not rescued, tuned or reused as beta logic.
4. **A narrow beta is authorized.** A descriptive private-beta surface is authorized for two purposes:
   - product-demand discovery with at most 20 invited BTC intraday traders;
   - prospective collection of market-state data.
5. **Beta events are rules, not hypotheses.** They are descriptive operational rules (`BETA_EVENT_RULES_V1`), not validated market hypotheses, and are never presented as trading signals.
6. **Beta outcomes are not confirmation.** Observed beta outcomes do not automatically become independent confirmation of anything.
7. **Promotion needs its own gate.** No research result is promoted into the beta without a separate, future promotion gate.

This decision does not change any frozen experiment, historical research conclusion, the V3 records, E1-RUN-001, the scientific test ledger or Generator V0 memory. Protected 2025/2026 research data stays sealed. None of it was opened for the beta design.

## Scope (V0.2)

- **Market:** BTCUSDT perpetual on Binance, Bybit and OKX. Bitget stays disabled and never counts toward coverage.
- **Channel:** a Telegram private beta capped at 20 users, with an owner allowlist.
- **Rules:** deterministic only. There is no LLM anywhere in the live decision or delivery path.
- **Not included:**
  - web, billing, other assets, order book, spot;
  - user exchange keys or order execution;
  - personalized advice;
  - predictive wording.

## Code boundary

| Path | Role |
|---|---|
| `beta/` | config, models, state tape, rules, detector, outcomes, formatter, delivery, admin, health |
| `runtime/beta_cli.py` | `--beta-bootstrap`, `--beta-once`, `--beta-status` (read-only), `--beta-outcomes-once`, `--beta-notify-once`, `--beta-health` (read-only) |
| `runtime/beta_bot.py` | separate long-polling bot service |
| `storage/beta_v0_schema.sql`, `storage/beta_v0_store.py` | additive beta tables only |
| `config/beta_v0.yaml` | every threshold, duration, TTL, cooldown and cap |
| `deploy/signalbot-beta-*` | prepared systemd units (not enabled) |

**Reused unchanged:**
- the Stage-2 one-bucket materialization, `process_stage2_bucket` (with in-memory writers, and without the V1 forecast that `process_shadow_cycle` adds);
- the Stage-2 consensus core;
- the Percentile core `compute_percentile_snapshot`;
- the Stage-2 schema, revision and instrument bootstrap helpers from `runtime/shadow_cli.py`;
- `notifications.telegram_client.TelegramSender` (subclassed, not modified).

**Not reused:** the legacy `NotificationCandidate`, the LONG/SHORT formatter and the forecast outbox.

## Frozen rule identity

- `rules_version = BETA_EVENT_RULES_V1`
- `state_schema_version = 1` (original identity; schema 2 is active since the temporal-context amendment, see the transition note below)
- `rules_digest = 2e0afa4785675e7a3777627f45647f76268a7cdad3e0639c078ee5ccc7605f44`. This is the sha256 of the canonical JSON of the rule-relevant config fields. It is pinned by `tests/beta/test_beta_config.py`.

### State-tape schema transition (V1 → V2), temporal-context amendment

- `state_schema_version = 2` is now active. V2 additionally records per-venue raw Stage-2 values (snapshot `venue_raw`) and per-venue 5m kline OHLC (`docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md`).
- The `BETA_EVENT_RULES_V1` thresholds are unchanged. The rules digest covers `state_schema_version`, so the identity is now `rules_digest = 9e9d2c631a1abfdb710dc2147835b3a0ccd4620512d3a0d6828140c96de17210` (schema 2). The schema-1 digest above remains the historical identity; a schema-1 configuration still reproduces it.
- A schema change is a version boundary, not a market-data correction. A correction check across it returns `SCHEMA_VERSION_BOUNDARY` and appends and flags nothing. Open detector episodes end with `DETECTOR_VERSION_CHANGED`, as for any rules-digest change.
- `config_digest = de76235b9dea8bad3b251a56ba022f34109e00921e04e6cddfb26550d33eef61`. This is the whole `config/beta_v0.yaml` beta section, including policy.

**Core events:**
- `PRICE_OI_CONTRACTION_DOWN`
- `PRICE_OI_CONTRACTION_UP`
- `POSITION_BUILDUP_COMPRESSION`

**Gated optional events** (`NOT_EVALUABLE` until the gate is met):
- `TAKER_FLOW_EXTREME_BUY` / `_SELL`: requires 30d-mature consensus taker flow on at least 2 venues.
- `LIQUIDATION_STRESS_LONG` / `_SHORT`: requires per-venue 30d percentiles, and at least 2 eligible venues. A venue is eligible only when:
  - its feed is declared available;
  - its heartbeat is healthy, meaning all five 1m bars came from the live websocket and no logged outage overlaps the bucket;
  - its percentile is mature;
  - its value was measured. A measured zero counts; an absent value never becomes zero.

`LEVEL_SWEEP` is not implemented. The four legacy names are not live detectors, and the beta does not wrap them.

A threshold change is a new rules version plus a full audit. It must never be tuned against beta price outcomes. Only product-frequency and operational tuning is allowed.

## Soak gate (before any external user)

Run a 7-day shadow soak with push disabled (`beta.push_enabled: false`, `BETA_PUSH_ENABLED` unset). Every one of the following must hold:
- zero stale `NO ACTIVE EVENTS` responses;
- zero TRIGGERED decisions built from stale or unusable required families;
- zero duplicate open episodes;
- zero duplicate episodes or push identities after a restart or redeploy;
- zero stale push attempts after a Telegram outage longer than the TTL;
- liquidation-feed loss leads to `NOT_EVALUABLE`;
- a one-venue bad print never produces a 2-venue event;
- 100% of successful evaluations are on the tape;
- 100% of TRIGGERED episodes are persisted;
- every matured outcome either completes or is explicitly marked `INCOMPLETE_DATA`;
- no predictive wording;
- no secret or raw Telegram id in logs;
- the kill switches have been tested.

The metrics below come from `--beta-status`:
- evaluations per day;
- EARLY, ARMED and TRIGGERED counts by type;
- ARMED→TRIGGERED conversion;
- cap-activation days (target about zero);
- data-degraded fraction;
- optional-event maturity.

If fewer than about one useful TRIGGERED event occurs every 2–3 days, stop before inviting users and review the product packaging.

## Rollout (after the soak gate)

1. Owner-only live push.
2. 2–3 real intraday traders.
3. 5–10 traders.
4. At most 20.

There is no public bot.

## Beta success and exit criteria (frozen before inviting external users)

- **Duration:** 4 weeks from the first external user.
- **Target:** 10–20 invited users.
- **CONTINUE** requires both:
  - at least 5 users still active (not stopped) and using `/btc`, `/history` or Details at least once a week in weeks 3–4;
  - qualitative interviews showing that at least 3 users would miss the product.
- **CHANGE PRODUCT** if either:
  - Noise votes outnumber Useful votes by 2:1 or more across all feedback;
  - users report the events as unactionable or confusing.
- **STOP BETA** if either:
  - 50% or more of users /stop within 2 weeks;
  - the soak or health invariants fail in production.
- With 20 users or fewer, qualitative feedback is primary. Percentages are not over-interpreted.

## Boundary flags (implementation unit)

| Flag | Value |
|---|---|
| REAL_TELEGRAM_MESSAGES_SENT | false |
| REAL_BETA_USERS_ENROLLED | false |
| LIVE_BETA_PUSH_ENABLED | false |
| EXCHANGE_ORDER_EXECUTION | false |
| USER_EXCHANGE_KEYS_USED | false |
| PROTECTED_RESEARCH_2025_2026_OPENED_FOR_BETA_DESIGN | false |
| NEW_MARKET_OUTCOME_CLAIM_CREATED | false |
| LLM_LIVE_DECISION_PATH_ENABLED | false |

Prospective research sidecar: `docs/research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md`. Deploy and privacy runbook: `docs/PRIVATE_BETA_V0_DEPLOY.md`.
