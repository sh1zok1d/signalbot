# E1 VPS Runbook

This runbook executes the pre-registered `E1-RUN-001` without opening future outcomes before the chronological split is frozen.

## Phase A — sync and verify research tooling

Run from the Signalbot repository on the VPS:

```bash
git fetch origin
git switch research/e1-detector-separation
git reset --hard origin/research/e1-detector-separation
git status --short
git rev-parse HEAD

python -m pytest -q tests/research/test_v2_e1_candidate_inventory.py
```

Expected posture:

- worktree clean;
- branch is `research/e1-detector-separation`;
- research tests green;
- do **not** merge PR #67;
- do **not** enable V2.

## Phase B — data inventory only

Do not run any outcome query yet.

The project already loads `.env` from the repository root in `common.config`, so derive the same Postgres DSN the application uses without printing the password into the report:

```bash
mkdir -p artifacts/e1
DSN="$(python -c 'from common.config import _build_postgres_dsn; print(_build_postgres_dsn())')"

psql "$DSN" \
  -v symbol=BTCUSDT \
  -f scripts/research/v2_e1_data_inventory.sql \
  | tee artifacts/e1/data_inventory.txt
```

`v2_e1_data_inventory.sql` starts `BEGIN TRANSACTION READ ONLY` and rolls back. It reads coverage/cadence/version metadata only. It does **not** calculate future returns, MFE, MAE, or detector performance.

After this command, stop. Do not run the candidate harness until these are frozen from `data_inventory.txt`:

1. one `calculation_version` / `feature_schema_version` identity;
2. the honest common historical interval available for the required Stage-3/4/5 inputs;
3. historical/live-equivalence classification;
4. health exchange/metric request set;
5. confirmation that provider cadence (especially OI) does not create pseudo-minute information relevant to the frozen detectors.

## Phase C — Stage-5 candidate counts only

This phase is authorized only after Phase-B inventory has been reviewed. It still reads no future outcome path.

Template:

```bash
python scripts/research/v2_e1_candidate_inventory.py \
  --dsn "$DSN" \
  --symbol BTCUSDT \
  --market-type perp \
  --start '<UTC_START>' \
  --end '<UTC_END_EXCLUSIVE>' \
  --calculation-version '<CALCULATION_VERSION>' \
  --feature-schema-version 1 \
  --health-exchanges <EXCHANGES...> \
  --health-metrics <METRICS...> \
  --output artifacts/e1/candidate_inventory.json
```

The runner:

- opens a coherent H2e read session at each logical `T`;
- executes the frozen Stage 3 -> Stage 4 -> Stage 5 path;
- records only qualifying candidates and context;
- imports no Stage-6 episode/lifecycle code;
- refuses to run if frozen production detector/data-path files differ from `main@8081eb31657f127141efb3a455f86690258164bc`;
- writes `outcomes_included: false`.

After Phase C, freeze the chronological development/holdout boundary using only coverage and qualification counts. Only then may a separate outcome evaluator read future Binance 1m paths.
