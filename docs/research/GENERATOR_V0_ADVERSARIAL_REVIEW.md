# Generator V0 adversarial self-review

Status: PASS for the implementation tests below. This is a self-review, not an
independent review and not evidence about real LLM ideation quality. PR remains
draft for independent review. No scientific outcomes or paid calls.

| Required failure class | Evidence / result |
|---|---|
| 1 RESULT reaches Generator | Context and adversarial nested-source tests reject before calls |
| 2 raw memory reaches Generator | Explicit artifact and nested-source rejection |
| 3 governance state reaches Generator | Noncanonical projection rejected; prompt scanner backstop |
| 4 authority reaches Selector | Role allowlist rejects artifact |
| 5 old prototype/null identity through critic | Extra critic fields rejected; selector nested fields and free text rejected |
| 6 memory drift | Exact-byte pins verified on every request; five-source drift tests |
| 7 unknown source DATA_READY | Schema rejects before critic/provider reuse |
| 8 protected periods | Schema refuses protected requirement and calendar-year references |
| 9 lookahead | Separate red-team check false prevents routing; mock adversarial card exercises path |
| 10 exact duplicate | Frozen prior relation table, exact mechanism/function guard and batch signature guard |
| 11 cosmetic rescue | Frozen parameter-neighbor and functional-relabel relations reject consumed signatures |
| 12 blocked distinct mechanism suppressed | Five blocked regions tested for orthogonal and blocker-resolution routes |
| 13 D4 mixed state | Both leaf states tested; parent cannot replace leaf coverage |
| 14 malformed JSON | Duplicate keys, nonfinite values and malformed model output fail closed; paid raw answer retained |
| 15 unexpected fields | Exact 27-field equality, strict role schemas |
| 16 missing fields | Required falsifier/schema tests |
| 17 timeout | Fake HTTP timeout retains full reservation, no retry |
| 18 duplicate provider candidates | Duplicate IDs/slot violation rejected; semantic duplicate test routes later card out |
| 19 retry over budget | No automatic retries; reservations survive errors and consume cap |
| 20 campaign over USD 30 | Constructor, CLI, ledger and pre-call budget checks |
| 21 ambient API credential | Default mock and offline preflight never contact HTTP; missing explicit flags fail |
| 22 resume repeats paid response | Fake real adapter response reused; full fake HTTP E2E; 125 responses retained after registry failure |
| 23 unsanitized critic state | Selector accepts only typed enum/ordinal survivor fields, never free-text rationales |
| 24 unaudited human mutation | Reason/actor mandatory; mutation/event transaction; stale decisions invalidated |
| 25 partial registry/ledger writes | SQLite transaction rollback injected mid-registry; resume reuses all provider results |

## Defects found and fixed

1. A claimed blocker resolution with blocked data could survive even when the
   feasibility critic did not confirm resolution. ALLOW_TO_FEASIBILITY now
   requires BLOCKER_RESOLVED for Stream B. Orthogonal candidates do not inherit
   that constraint.
2. Asymmetric batch novelty answers could double-count data demand. A relation
   in either direction excludes the later candidate ID after all critics run.
3. Mock CLI accepted the frozen upper bound 50 but had only 40 fixture names.
   Fixture construction now supports both 25 and 50; boundary campaigns tested.
4. Human edits could leave misleading old JSON views. Mutation now invalidates
   the registry/data-gap views and writes the current human audit view.
5. Flat CI source mapping missed future nested-package-only edits. Generator
   source or authority changes now select the complete focused suite.

## Validation scope

113 focused Generator V0 tests; 501 tests in the combined integration subset.
Subset includes Sprint03/Sprint04 metadata contracts, PR-gate routing, general
research-harness tests, data-quality and exchange-feature unit tests. These
use synthetic fixtures; no market experiment is executed. Compilation and
`git diff --check` pass. Two clean canonical mock CLI runs agree exactly.
A full fake HTTP campaign exercises the concrete real adapter. No actual API
request is used to establish this result.

Semantic judgments remain fallible. Tests prove response contracts and routing,
not that a model recognizes every paraphrased duplicate or hidden lookahead.
Human adjudication is still required. Source checkout excludes market dataset
payloads; no data-dependent full-regression claim is made.
