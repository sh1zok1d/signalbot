# Generator V0 — background RED_TEAM transport amendment

Date: 2026-09-24. Base: PR #218 head `caa71a24b0526029f33b2cd5663b279121e80be8`
(tree `6ceaf4291b03de6140faaf92bdd1e3edce405a62`). Owner-authorized, transport only.
No live API call, no protected data, no scientific change. Machine-readable record:
`GENERATOR_V0_BACKGROUND_RED_TEAM_TRANSPORT_AMENDMENT.json`.

## Why

The critic-only continuation of the five-card cost calibration stopped on C001
`RED_TEAM` (`gpt-6-sol`, `reasoning_effort=high`, synchronous Chat Completions):
HTTP 502, `UNCERTAIN`, call key `8e94c966…6c39`, reservation 98,806 micro-USD.
It is the same failure class that ended two synchronous high-effort Sol
`NOVELTY_CRITIC` calls before PR #218. Background `NOVELTY_CRITIC` has since
completed live. This is treated as transport evidence only.

## Change

`RED_TEAM` moves from synchronous Chat Completions to background Responses, with
the same machinery `NOVELTY_CRITIC` already uses: one `POST /v1/responses`
(`background=true`, `store=true`, `stream=false`), never replayed; then
`GET /v1/responses/{response_id}` until terminal; best-effort `DELETE` after local
persist.

The code change is the `RED_TEAM` entry in `routing.py`: `ENDPOINT`, `TRANSPORT`
and `STRUCTURED_OUTPUT`. The OpenAI adapter, `Caller` and `Ledger` background state
machine are role-generic and unchanged.

Unchanged for `RED_TEAM`: provider, model, effort, prompt, strict schema,
application validation, the 8,000-token cap, protected-data rules and downstream
governance. `NOVELTY_CRITIC` (background), `FEASIBILITY_CRITIC` and `SELECTOR`
(synchronous) and `GENERATOR` (Anthropic) keep their routes.

## Identity

| | Before | After |
|---|---|---|
| RED_TEAM route digest | `b51a1a31…f9b9` | `f6fadb7b…a2f2` |
| Routing digest | `9c99dc12…df66` | `c636f14a…c596` |
| Reference RED_TEAM call key | `ef4bebf2…c8eb6` | `14f85a61…d701` |

The GENERATOR, NOVELTY_CRITIC, FEASIBILITY_CRITIC and SELECTOR route digests and
the reference feasibility call key are unchanged. An old synchronous red-team
request is refused by the new route, and a completed synchronous red-team row is
never served to the background route.

## Budget

The bound formula is unchanged. The Responses payload is slightly smaller: the
40-card red-team worst case moves from USD 4.194940 to 4.191020, and the fresh
40-card single-attempt bound to USD 26.736625. `BUDGET_SCENARIOS.json` and
`OFFLINE_GATE_REPORT.json` were regenerated with the repository generators. The
mixed fake E2E still makes 91 POSTs; the red-team POSTs moved to `/v1/responses`,
and its application decisions equal those of an all-synchronous transport.

## Calibration state at this amendment

Scratch continuation journal only (not committed); the recovered generator
journal is unchanged.

- GENERATOR: COMPLETE, USD 0.892012.
- C001 NOVELTY: COMPLETE, USD 0.029376. C001 FEASIBILITY: COMPLETE, USD 0.000415.
- C001 synchronous RED_TEAM: `RECONCILED_UNKNOWN` at its full reservation, USD 0.098806
  (no `response_id` or usage existed). This closes the logical call
  `RED_TEAM|RED_TEAM:C001` in that journal.
- Ledger total charged: USD 1.020609. Calibration incomplete; no cost classification.

## Validation

- New `tests/research/test_generator_v0_background_red_team.py` covers routing,
  request shape, strict schema, completion, reasoning redaction, raw/wire hashes,
  create timeout and ambiguous create as `UNCERTAIN` without replay,
  `response_id` persistence before polling, resumable GET-only polling, resume with
  zero POSTs, best-effort DELETE, unchanged application validation on both
  transports, identity changes, unchanged sibling routes and cost accounting.
- The PR #218 novelty tests and the multi-provider route table now record the
  new RED_TEAM route.

`READY_FOR_BACKGROUND_RED_TEAM_SMOKE`
