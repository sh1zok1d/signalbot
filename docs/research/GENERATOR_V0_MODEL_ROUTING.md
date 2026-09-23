# Generator V0 role-specific model routing

Verified 2026-09-23 from official OpenAI API documentation, without an
API call. This is an implementation routing table, not a scientific
design change. Frozen Generator V0 design already allowed
`ROLE_SPECIFIC_CONFIG`.

```
GENERATOR           = gpt-5.4-2026-03-05
NOVELTY_CRITIC      = gpt-5-2025-08-07
RED_TEAM            = gpt-5-2025-08-07
FEASIBILITY_CRITIC  = gpt-5-mini-2025-08-07
SELECTOR            = gpt-5-mini-2025-08-07
```

Authority: `scripts/research/generator_v0/models.py`. Prices and
request parameters are fail-closed. A single `--model` /
`GENERATOR_V0_MODEL` override is rejected. The map is stored in the run
config and hashed into the implementation/config digest, so resume
refuses routing drift.

GPT-5.4 / GPT-5 / GPT-5 Mini do not share gpt-4.1-mini sampling
parameters. Reasoning roles send `reasoning_effort` and never
`temperature`. Budget accounting uses the model actually selected for
that call.
