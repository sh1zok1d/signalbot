# SYNTHETIC_BETA_USER_V0 — offline synthetic beta user and delayed outcome auditor

Status: **SYNTHETIC / DESCRIPTIVE_MONITORING / IMPLEMENTED_OFFLINE / NOT_ACTIVATED**.

Code: `tools/beta_user_sim/`. Tests: `tests/beta_user_sim/`.

This is a tool for reading the beta surface the way a trader would. It is not research. It writes no `RESEARCH_LEDGER` entry and promotes nothing. It makes no edge claim and changes no rule. It has no route into detector rules, thresholds, config, push eligibility, wording or code. It takes no part in the beta CONTINUE/STOP decision.

It is not QA evidence, PMF evidence, willingness-to-pay evidence or retention evidence. Do not iterate wording or rules against the same replay tape, and do not treat repeated runs as independent evidence.

## 1. Two roles

| | Role A — synthetic user | Role B — delayed auditor |
|---|---|---|
| Runs at | replay time T | only after `T + 24h + last-bar grace` |
| Sees | sanitized visible chat only | one message, its claim manifest, code-checked facts, matured outcomes, a baseline |
| Context | one persistent conversation | fresh context per item |
| Decides | `NO_ACTION` / `SEND_COMMAND` / `CLICK_BUTTON` | four narrow questions plus a blind A/B preference |

A later market move is never scored as a failure unless the claim manifest says Signalbot made the relevant forward claim. On current main no template does, so the forward slot is `NO_DIRECTIONAL_CLAIM` or `NOT_EVALUABLE`. The code sets `forward_outcome_verdict`, and Role B cannot change it.

## 2. Scope: real surfaces on current main (beta V0.2)

The surfaces come from AST over `runtime/beta_bot.py`.

- Commands: `/start`, `/btc`, `/history`, `/terms`, `/help`, `/feedback <text>`, `/stop`.
- Excluded from the allowlist: `/lang` and `/delete_me` (they would change the state the replay depends on), and the `admin_*` commands (the sandbox has no owner).
- Callbacks: `/btc` Main/Event/1h/24h tabs (`o:`/`e:<view_pk>:…`), push Details, the onboarding `pick:`/`join`/`terms`, and `r:latest`.
- Real pushes.

V0.3 surfaces such as `/catchup`, the morning brief, analogues and P1–P3 are not invented. A future payload kind is a new `timeline` item kind plus a claims adapter.

## 3. Offline replay and causality

- **Input.** A replay bundle (JSON). It comes from one of two sources:
  - `make-synthetic-bundle`, which is fully synthetic, dated 2024, and built with the real `evaluate_bucket`, `step_episode`, push policy, `btc_view`, `format_btc` and `compute_outcome`;
  - `export`, a read-only exporter. It uses one `READ ONLY` transaction plus `default_transaction_read_only=on`, runs `SELECT` statements only, and never reads participant tables.
- **No live access.** There is no live mirror, Telegram, production DB or network.
- **The real handler.** `BetaBotHandler` runs unchanged against `SandboxStore` (in memory) with `owner=None` and no telemetry salt.
- **As-of reads.** Every store read is as-of the replay clock:
  - transitions by `recorded_at`;
  - outcomes by `computed_at`, taking the latest revision then;
  - decisions by `recorded_at`;
  - deliveries by their timestamps.
- **Fail closed.** A set `correction_flag`, or history shorter than requested when the bundle has an `episodes_since` cut, raises `Unreplayable`. The replay never reconstructs from later data.
- **`/btc` at arbitrary T is not reconstructable.** The live path needs current market state, and the handler's live `/btc` and `r:latest` paths raise `Unreplayable`. Instead, `/btc` is served from the first unserved persisted same-language view in `[T, T+10 min]`, and the clock advances to it. Otherwise the action is logged as `UNREPLAYABLE` and Role A gets the notice "Your last action produced no visible reply."
- **Push text is not persisted.** It is rebuilt from the set-once trigger fields with the frozen template. A push arrives at its first `SENT` `finished_at`.
- **Outcomes** use `beta/outcomes.py` with `cfg.outcome_version` (`BETA_OUTCOME_V1`). There is no alternative definition.
  - An episode outcome comes from the bundle's outcome rows.
  - A view outcome is computed by `compute_outcome`, anchored at the view's `data_through`, with the view's own reference price.
  - Horizon h unlocks at `anchor + h + LAST_BAR_GRACE`, and never past `exported_at`; an item that has not matured is deferred.
- **Manifest.** The ordered replay input IDs and the skipped inputs (with reasons) are recorded in the run manifest.
- **Protected data.** `export` refuses any window whose 24h horizon reaches 2025-01-01 or later, unless `--beta-live-window` is given. That flag records an owner decision that the export reads only live beta tables, never a sealed research dataset. No protected research dataset is read by any path.

## 4. Role A input, persona and actions

Role A receives only `UserTurn` JSON:
- `now`;
- new messages, with visible text, arrival time, arrival attention state, and opaque button ids `mN.bK` with their labels;
- notices and popups.

Callback data, view/episode ids, digests, payloads, outcomes and research fields never reach the prompt. `assert_role_a_safe` checks every turn.

The prompt is `ROLE_A_USER_PROMPT_V0` (`prompts.py`). It sets up an experienced BTC perp intraday trader who dislikes noise and overconfident wording, and it contains verbatim:

> You are a user, not a QA engineer. Do not try to exercise every feature. If a message does not deserve your attention, ignore it.

It also says "Do not flatter the product. Do not guess what the developers intended."

Output must be one JSON object:
- `SEND_COMMAND` accepts only allowlisted real commands;
- `CLICK_BUTTON` accepts only a button visible on a shown message;
- anything else is rejected with a reason and not executed.

Accepted actions go through the real handler path inside the sandbox.

Journal notes are restricted to the listed topics. PMF, WTP, retention and replace-tool talk is tagged `UNSUPPORTED_SYNTHETIC_OPINION` and excluded. The journal is never fed back into Signalbot or Role B.

## 5. Attention

`AttentionSchedule` is deterministic for a seed (default 7):
- 30-minute slots in three states: AVAILABLE, BUSY (`p_busy=0.45`) and SLEEPING (00:30–07:30 Kyiv);
- messages that arrive while BUSY or SLEEPING form a backlog;
- the backlog is shown at the next AVAILABLE start, in arrival order, with original times;
- each available slot also gets one idle turn, so Role A may open `/btc` unprompted.

## 6. Claim manifest and deterministic audit

`claims.py` builds claims in code, from frozen template behavior (legacy adapter). Production rendering is untouched.

Each claim has `claim_id`, `claim_type`, `source_fields`, `rendered_text_fragment`, `evaluation_class` (`AT_T_FACT` / `FORWARD_OUTCOME` / `WORDING_JUDGMENT`), `evaluation_rule`, `directional_claim` and `horizon`.

Statuses are `CONSISTENT`, `CONTRADICTED`, `NOT_EVALUABLE` and `NO_DIRECTIONAL_CLAIM`.

- **At-T facts.** Price, horizon lines, incomplete-horizon lines, the event line, history rows and the like are re-rendered from payload fields with the frozen formatter helpers and compared.
- **Forward slot.** It is `NO_DIRECTIONAL_CLAIM` only when the text is reproduced by the frozen catalog: a `TEMPLATE_MATCH` view, a template-rebuilt push or a handler reply.
  - A non-template view with unparsed fragments gets `NOT_EVALUABLE`, because the forbidden-wording guard is a blocklist and cannot prove absence.
  - Forbidden wording also gives `NOT_EVALUABLE`.
- **Unclear lines** are `NOT_EVALUABLE`, never guessed.

## 7. Role B

The auditor prompt is `ROLE_B_AUDITOR_PROMPT_V0`. Its request keys are exactly `time_T`, `kind`, `original_message`, `claims`, `what_followed` and `baseline_message`. It asks:
- wording stronger than evidence;
- explanatory value over the baseline;
- understandable without hidden knowledge;
- retrospective usefulness.

It does not recompute numbers. Answers outside the enum become `INVALID_RESPONSE`.

The baseline is `BASELINE_SIMPLE_V0`: deterministic, frozen and versioned. It covers price, the 1h and 24h change, the 1h range against its usual size, volume against usual, and the 24h high/low. It has no OI, taker, liquidation, funding or multi-venue interpretation. A push has no baseline, so it is `NOT_EVALUABLE` for A/B.

The blind judge prompt is `ROLE_B_BLIND_JUDGE_PROMPT_V0`.
- **Sides** are assigned by `random.Random(f"{judge_seed}:{item_id}:{pair_kind}")`.
- **Identity is hidden.** The judge sees only `option_a`, `option_b` and `what_followed`. The disclaimer is stripped, and `assert_blind` rejects identity words.
- **Instructions.** The prompt tells the judge not to reward length, formatting, confidence or metric count.
- **Controls.** Every item also gets baseline-vs-baseline and Signalbot-vs-Signalbot pairs, and side preference is reported.
- **No composite score.**
- **Known limit.** The format of a Signalbot message can still reveal its source.

## 8. Isolation

- **No imports into the harness.** No production module imports `tools.beta_user_sim` (AST test).
- **Restricted imports from the harness.** The harness imports no storage, network, Telegram or research code. Only the CLI `export` path can open a database connection.
- **Synthetic participant.** It is `telegram_user_id = -7_311_000_001`. The production schema `CHECK (telegram_user_id > 0)` rejects it in `beta_allowlist` and `beta_users`, which is proven by a PostgreSQL test. Synthetic activity exists only in the sandbox.
- **Beta metrics stay real-only.** `beta/usage.py` reports, the participant cap, rollout and real pushes are unaffected. `beta/usage.py` itself is unchanged.
- **Real models.** `OpenAIChatModel` needs `--allow-network`, `SIGNALBOT_SIM_ALLOW_NETWORK=1` and `OPENAI_API_KEY`. Tests use fake models only, with sockets blocked.
- **No capabilities.** There is no trading, no exchange credentials, no config writes, no push or detector state, and no research state.

## 9. Reports

`run.json` is the full result. `report.json` and `report.md` hold:
- the manifest: models, prompt versions, replay, attention and judge seeds, input IDs, inference settings, run time and code commit;
- the Role A usage summary;
- the deterministic audit;
- the Role B summary, including both controls and side bias;
- daily and ISO-week grouping.

`transcript.md` holds the transcript. The renderer refuses "edge", "predictive", PMF, p-value and overall-score wording. Fake-model runs are deterministic; real models are not claimed to be bit-identical.

## 10. Commands

```bash
python -m tools.beta_user_sim make-synthetic-bundle --out /tmp/sim/bundle.json
python -m tools.beta_user_sim replay --bundle /tmp/sim/bundle.json --out /tmp/sim/run --model fake
# read-only export (owner decision needed for any 2025+ window):
BETA_SIM_EXPORT_DSN=... python -m tools.beta_user_sim export --dsn-env BETA_SIM_EXPORT_DSN \
  --start 2026-09-25T00:00:00+00:00 --end 2026-09-26T00:00:00+00:00 --out /tmp/sim/export.json --beta-live-window
# real-model smoke — NOT authorized, never executed:
SIGNALBOT_SIM_ALLOW_NETWORK=1 OPENAI_API_KEY=... python -m tools.beta_user_sim replay \
  --bundle /tmp/sim/bundle.json --out /tmp/sim/real --model openai --model-id <id> --allow-network
```

## 11. Known blockers and NOT_EVALUABLE places

- `/btc` at an arbitrary T and `r:latest` are unreplayable. Only persisted views are served.
- Push text is rebuilt rather than persisted. `PUSH_RULE_DESCRIPTION` is `NOT_EVALUABLE` because the bundle has no tape.
- Pushes have no baseline, so they are `NOT_EVALUABLE` for A/B.
- View lines without a V0 rule (for example per-venue OI lines) are `NOT_EVALUABLE`.
- View outcome venue membership is not persisted, so the bundle venues are used.
- A real export of the live 2026 beta window needs an explicit owner decision (`--beta-live-window`).
- `/lang` and `/delete_me` are not exercised.
