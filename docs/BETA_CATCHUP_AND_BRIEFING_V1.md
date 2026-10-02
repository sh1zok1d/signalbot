# Beta — `/catchup`, morning briefing and 1h/4h labels (build-to-test steps 1–2)

**Status:** `IMPLEMENTED_ON_BRANCH / NOT_DEPLOYED / UX_THRESHOLDS_PROVISIONAL`
**Authority:** `PRODUCT_FIRST_DECISION_V1.md` §3 rows 1–6 and §3.1. This file records how those rows are built. It adds no scope.

## 1. What exists

| Piece | Where | Notes |
|---|---|---|
| 1h / 4h context with taker-delta and OI-change ranks | `beta/context.py` (`BETA_CONTEXT_1H_V2`) | See `BETA_BTC_TEMPORAL_CONTEXT_V0.md`. Carries V1's episode memory, so there is no reset on deploy. |
| Interpretation of one 1h or 4h window | `beta/interpretation.py` (`BETA_INTERPRETATION_V1`, status `PROVISIONAL_PENDING_DRY_RUN`) | Pure function; §2 below. |
| 4h horizon with a time-of-day baseline | `beta/horizons.py` (`BETA_HORIZON_TOD_V2`) | Same rule as the 1h baseline over 48 buckets. 24h is unchanged. |
| Shared view builder | `beta/market_view.py` | One path for `/btc`, `/catchup` and the briefing. `/btc` keeps its exact payload keys and rendering. Views are stored in `beta_btc_views` with `kind` = `btc` / `catchup` / `brief`. |
| `/catchup`, `/catchup N` (1–24 h, default 8) | `runtime/beta_bot.py`, `beta/formatter.py::format_catchup` | Window line, detector events in the window, 1h and 4h labels, 24h line, data time. Activity `cmd_catchup`. |
| Morning briefing | `beta/delivery.py::run_due_briefs` inside the existing `run_notify_once` | Same view and render as `/catchup`, window 8 h, at `briefing.time_kyiv` (08:00). §3 below. |
| `/brief`, `/brief on`, `/brief off` | `runtime/beta_bot.py` | `beta_users.brief_enabled`. Activity `cmd_brief`. Does not touch pushes. |
| Recorded-tape dry run | `beta/dry_run.py`, `--beta-context-dry-run` | Read-only. §4 below. |

Unchanged: `BETA_EVENT_RULES_V1`, the rules digest, tape schema V2, `STRICT_QUALIFICATION_V1`, the detector, push decisions and push policy, the push loop of the notifier, and `/btc` text.

## 2. Interpretation wording

- **Inferred labels** (price + OI + taker all agree):
  - «похоже на выход шортов»
  - «похоже на рост с новыми лонгами»
  - «похоже на снижение с новыми шортами»
  - «похоже на выход лонгов»
  - «похоже на вынос шортов» / «похоже на вынос лонгов», only with an overlapping `LIQUIDATION_STRESS_*` episode of the matching side. A liquidation interpretation is never stated as a fact.
- **Factual fallbacks** (no causal label):
  - «рост при снижении OI», «рост с ростом OI», «снижение с ростом OI», «снижение при снижении OI» — taker missing, neutral or opposite;
  - «рост при стабильном OI» / «снижение при стабильном OI» — OI mature and available but neutral;
  - «рост, OI н/д» / «снижение, OI н/д» — OI missing, immature or from fewer than 2 venues.
- **Other states:**
  - «сжатие», «сжатие, OI н/д»;
  - «обычное состояние»;
  - «мало истории» (immature ranks);
  - «н/д».
- **«биржи расходятся»** is checked only after an unusual aggregate move. The gate is the price rank's up/down band. Mixed signs of tiny calm-market moves are not labelled. The gate threshold is **not frozen** until the dry run is reviewed.
- **24h** has no label.

## 3. Briefing delivery

- **Committed off** (`briefing.enabled: false`). Sending also needs the global push switches (`BETA_PUSH_ENABLED`, no `/admin_pause_push`).
- **Once per Kyiv day** after the slot, within `max_delay_min` (120), the notifier:
  - builds one view of kind `brief` and persists it;
  - materializes one `PENDING` outbox row per ACTIVE participant with the briefing on. The rows have `kind='brief'`, no decision or episode, and `view_pk` and `brief_date` set. A partial unique index on `(brief_date, user_pk)` makes this idempotent.
- **Each row follows the outbox rules:** at most one send attempt, expired rather than late, suppressed while pushes are off. Activity is recorded as `brief_delivered`.
- **Push isolation.** The push loop reads only `kind='push'` rows, and `delivery_state_counts` counts only push rows. Push decisions are never read or written by the briefing.

## 4. Dry run (owner step before freezing UX thresholds)

```bash
python main.py --beta-context-dry-run --dry-run-days 7 --dry-run-stride 12 --beta-json > /tmp/beta_context_dry_run.json
python main.py --beta-context-dry-run --dry-run-days 7 --dry-run-stride 12 --dry-run-provisional --beta-json > /tmp/beta_context_dry_run_provisional.json
```

- **Reports:**
  - label frequencies per horizon;
  - every «биржи расходятся» case, with its venue moves;
  - how many calm samples had mixed venue signs and were not labelled (the gate's effect);
  - up to 3 examples per label;
  - six rendered `/catchup` texts.
- **Two modes.**
  - Without `--dry-run-provisional`, the production maturity rules apply.
  - With it, ranks count as mature after 3 days of history (the minimum the percentile core accepts). Those numbers are `PROVISIONAL`. V2 tape rows exist only since 2026-10-01, so production ranks mature around 2026-10-21 to 31.
- **Cost:** about 2 s per sample; a week at hourly stride takes about 6 minutes.

## 5. Known limits

- **Stage-1 OI has no record time.** A late backfill can change the as-of history. This is documented, non-blocking debt for beta UX. This context layer is never research evidence without a separate provenance / record-time solution.
- **Band frequencies are structural.** With 20% bands, «сжатие» and the directional rows are each expected roughly one window in five, before the other conditions are applied. The dry run measures the real shares.
