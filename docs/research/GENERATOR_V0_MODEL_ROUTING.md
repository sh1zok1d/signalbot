# Generator V0 role-specific model routing

Verified 2026-09-23 from official OpenAI API documentation, without an
API call. This is an implementation routing table, not a scientific
design change. Frozen Generator V0 design already allowed
`ROLE_SPECIFIC_CONFIG`.

Official catalog pages expose only stable IDs (no dated snapshots):

```
GENERATOR           = gpt-6-astra     reasoning_effort=high
NOVELTY_CRITIC      = gpt-6-sol       reasoning_effort=medium
RED_TEAM            = gpt-6-sol       reasoning_effort=medium
FEASIBILITY_CRITIC  = gpt-6-luna      reasoning_effort=low
SELECTOR            = gpt-6-luna      reasoning_effort=none
```

Authority: `scripts/research/generator_v0/models.py`. Prices and
request parameters are fail-closed. A single `--model` /
`GENERATOR_V0_MODEL` override is rejected. The map and per-role
`reasoning_effort` are stored in the run config and hashed into the
implementation/config digest, so resume refuses routing drift.

GPT-6 Astra, Sol, and Luna all support Chat Completions and Structured
Outputs. They do not share gpt-4.1-mini sampling parameters. Every role
sends `reasoning_effort` and never `temperature`. Astra does not support
`none`; Selector uses Luna with `none` because deterministic ordinal
authority remains application-side. Budget accounting uses the model
actually selected for that call.
