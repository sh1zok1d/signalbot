# Generator V0 — Cursor DIRECT transport amendment

**Status:** `IMPLEMENTED`, infrastructure only  
**Date:** 2026-10-02  
**LLM calls:** 0

```
CURSOR_DIRECT_TRANSPORT = implementation/infrastructure amendment only
SCIENTIFIC_DESIGN_CHANGED = false
LIVE_LLM_CALLS = 0
```

## Purpose

The V03 `ladder-40-card` entry point previously overwrote `--openai-network-mode` with `CLOUD_PROXY`. That is correct for the managed Cloud Agent environment, but blocks Cursor/local sessions that have direct provider credentials and no sandbox `HTTPS_PROXY`.

This amendment allows an explicit:

```bash
--openai-network-mode DIRECT
```

for `ladder-40-card`. With no flag, the command still defaults to `CLOUD_PROXY`. `first-30-card` continues to force `CLOUD_PROXY`.

## Invariants

- No change to `GENERATOR_CONTRACT_V03`.
- No change to models, prompts, schemas, role routing, complexity slots, critic rules, shortlist quota, pricing, budget-stop semantics, or market-data policy.
- `HTTPS_PROXY` never selects a mode automatically.
- DIRECT requires `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.
- CLOUD_PROXY keeps the existing sandbox-auth path for OpenAI and the Anthropic credential requirement.
- OpenAI network mode is explicit in transport identity, so DIRECT and CLOUD_PROXY produce distinct run identities; resume across modes fails closed.

## Cursor run shape

After merge and separate live authorization:

```bash
python -m scripts.research.generator_v0 ladder-40-card \
  --allow-real-llm --budget-usd 12 \
  --accept-budget-stop --actor owner --reason "<reason>" \
  --openai-network-mode DIRECT \
  --run-dir <dir>
```

This record authorizes no live call by itself.
