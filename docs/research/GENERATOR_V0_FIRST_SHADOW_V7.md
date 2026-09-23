# Generator V0 first-shadow-v7 — operational closeout

**Status:** `STOPPED_PROTECTED_RANGE_VALIDATION`
**Expected terminal state:** `PENDING_HUMAN_REVIEW`
**Reached expected state:** no
**Date:** 2026-09-23
**Machine-readable twin:** `docs/research/GENERATOR_V0_FIRST_SHADOW_V7.json`
**Result payload SHA256:** `d3ca214c061aeb10abea0a1389af370af10ff5cdbfa66d1f9259560d3419ebf3`
**Authority journal SHA256:** `e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457`

This is an operational closeout of the live first-shadow-v7 campaign. It is
not scientific evaluation of the generated ideas. Cards were not registered
in the `cards` table. Critics were not run. No shortlist exists. No
hypothesis was executed. No market data were acquired. Protected 2025/2026
data remain unopened. Frozen first-shadow-v6 was not mutated.

The campaign fail-closed on application validation of generation:3. The
LEGAL_RANGE classifier and the C033 exclusion parser were **not** extended
after those outcomes were observed.

## Authorization and preflight

Owner-authorized absolute cumulative ceiling: USD 17.100000, including
already recorded imported spend USD 3.779550. Remaining authorized additional
spend at authorization was USD 13.320450. USD 17.10 is not an additional
allowance. USD 17.117536 remains unauthorized.

Sequence actually executed:

1. Offline `derive` from sealed `first-shadow-v6` through generation:2 into
   `first-shadow-v7` (`DERIVED_IMPORTED_REVALIDATED`; C018 revalidation PASS;
   cards table not written).
2. Offline `authorize-budget-extension` to USD 17.100000.
3. Offline remaining-budget-preflight `FITS_AUTHORIZED_REMAINING=true`
   (recorded worst-case remaining USD 13.286520 < USD 13.320450).
4. Offline `authorize-derived-continuation`.
5. Live `resume` with `--budget-usd 17.100000`. Imported generation:0/1/2
   COMPLETE rows were reused (no replay POST). One new GENERATOR background
   Responses call ran for `generation:3`.
6. Local `validate_card` fail-closed. No critic or selector POST. The
   generation:3 COMPLETE response remains journaled and was not edited.

## Spend and usage

| Item | Value |
|---|---|
| Provider | `OPENAI_MIXED` (GENERATOR background Responses; critics unused) |
| Generator model | `gpt-6-astra` / `reasoning_effort=high` / `max_output_tokens=32768` |
| Authorized absolute ceiling | USD 17.100000 (`17100000` micro-USD) |
| Imported spend (gen0/1/2) | USD 3.779550 (`3779550`) |
| New spend this unit (gen3) | USD 1.167200 (`1167200`) |
| Cumulative spend | USD 4.946750 (`4946750`) |
| Remaining under ceiling | USD 12.153250 (`12153250`) |
| Real LLM calls this unit | 1 |
| Complete calls in journal | 4 (3 imported + 1 live) |
| Uncertain/reserved calls | 0 |
| Candidate count registered | 0 |
| Stream A / B / rejected | 0 / 0 / 0 |
| Shortlist | none |
| Selector | not run |

Per-stage actual spend (micro-USD):

| Stage | Actual | Notes |
|---|---|---|
| generation:0 | 1213380 | imported COMPLETE; not replayed |
| generation:1 | 1352350 | imported COMPLETE; not replayed |
| generation:2 | 1213820 | imported COMPLETE; not replayed |
| generation:3 | 1167200 | live COMPLETE; reservation was 1852570 |
| NOVELTY_CRITIC ×40 | 0 | not started |
| FEASIBILITY_CRITIC ×40 | 0 | not started |
| RED_TEAM ×40 | 0 | not started |
| SELECTOR | 0 | not started |

Live generation:3 usage: input 4635 / output 22417 / reasoning 10358.

## Response IDs

Imported (unchanged from first-shadow-v6):

- generation:0 `resp_08273b80118314ac006ab39d9b92dc87d2ba9539e343da810e`
- generation:1 `resp_0a0404f934baedd9006ab3a068c70887d2af71eda734b5aa3c`
- generation:2 `resp_0804f042cef56925006ab3cdfb548887d2b43773b1e57a8094`

Live this unit:

- generation:3 `resp_071edfe3d5c0aaa9006ab3de92a5ac87d28b9f8efaec6c7db7`
- call key `efff72aad0b133316e5908a0378ff3aa4aaa57b8fba1a22eb9ac875fb9b6025d`
- raw SHA256 `69fc7a97217e5d3deba1887ec5746115c0c64d62466f92a74e461f9f61fbcf33`

## Card counts

| Stage | Count | Registered |
|---|---|---|
| generation:0 (imported, revalidated) | 10 (C001–C010) | no |
| generation:1 (imported, revalidated) | 10 (C011–C020) | no |
| generation:2 (imported, revalidated) | 10 (C021–C030) | no |
| generation:3 parsed | 10 (C031–C040) | no |
| generation:3 valid | 1 (`C037`) | no |
| generation:3 invalid | 9 | no |
| `cards` table | 0 | — |
| critics | 0 | — |
| selector shortlist | none | — |

Invalid generation:3 IDs: C031, C032, C033, C034, C035, C036, C038, C039,
C040. Eight failed `ambiguous protected range`. C033 failed
`protected data requirement` because `NO_LOOKAHEAD_RULE` contains
"use 2025/2026 bars" without the frozen unambiguous exclusion form
(`No 2025[/2026] <non-numeric subject> are/is permitted|allowed`).

Observed generation:3 LEGAL_RANGE wrappers are recorded in
`docs/research/generator_v0_first_shadow_v7/GEN3_VALIDATION_DIAGNOSTIC.json`
only. They were **not** added to `classify_legal_range`. Source cards
C001–C030 were not edited.

## Stop

Resume exit 1. Stderr: `ambiguous protected range`. Ledger `status`
remains `DERIVED_CONTINUATION_AUTHORIZED`. Campaign JSON views
(`shadow_registry.json`, `human_review_queue.json`, `data_gap_ledger.json`,
`run_ledger.json`) were not written because the runner never reached a
registry commit.

The operator now treats `artifacts/generator_v0/first-shadow-v7` as an
archived paid run and refuses run/resume/review/inspect/derive-dest/
authorize/preflight against it. Resume would otherwise reuse the journaled
COMPLETE generation:3 answer and fail the same validator without a new POST.
That path is sealed rather than retried.

first-shadow-v6 sqlite SHA256 remains
`ed318020ff5d6c765394c15ba4ff5bd7dc0f89ffe83f7692f678e3f7e124b22d`.

## Artifacts

Runtime run directory (gitignored): `artifacts/generator_v0/first-shadow-v7`

Tracked sealed copy:

- `docs/research/generator_v0_first_shadow_v7/run.sqlite` (authority journal; SHA256 `e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457`)
- `docs/research/generator_v0_first_shadow_v7/call_metadata.json`
- `docs/research/generator_v0_first_shadow_v7/events.json`
- `docs/research/generator_v0_first_shadow_v7/derived_import.json`
- `docs/research/generator_v0_first_shadow_v7/GEN3_VALIDATION_DIAGNOSTIC.json`
- `docs/research/generator_v0_first_shadow_v7/resume.stderr.txt`
- `docs/research/generator_v0_first_shadow_v7/resume.exit.txt`

## What this does not authorize

No scientific interpretation. No LEGAL_RANGE grammar extension from
generation:3. No C033 exclusion-parser expansion. No automatic replay. No
second paid campaign. No Sprint 05, D14, MARKET-07, acquisition, or
protected-data open. No product unfreeze.
