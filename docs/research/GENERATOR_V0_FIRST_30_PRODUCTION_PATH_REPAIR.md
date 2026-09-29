# Generator V0 — first 30-card production-path repair

**Status:** `OFFLINE / READY_FOR_REVERIFY`  
**Date:** 2026-09-24

Enforcement of the already-frozen first 30-card rules. Prompts, schemas, models, reasoning effort, critic retry, memory, and budget reservation are unchanged. No live call was made.

- `GENERATOR_CONTENT_ATTEMPTS = 1` (`GENERATOR_CONTENT_RETRIES = 0`). Size 30 allows `MAX_GENERATOR_POSTS = 3`.
- `SELECTOR_LLM_CALLS = 0` on that path. `SELECTOR_AUTHORITY = DETERMINISTIC_ORDINAL_ORDER`. Advisory status is `NOT_CALLED`.
- Cloud Agent OpenAI uses `OPENAI_NETWORK_MODE = CLOUD_PROXY` and `CloudProxyOpenAITransport`. The mode is explicit. `OPENAI_API_KEY` is not required. Anthropic still requires `SIGNALBOT_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY`.
- `MEMORY_FINALIZER_V1` is unchanged.
- Entry point: `python -m scripts.research.generator_v0 first-30-card`.

Machine-readable record: `GENERATOR_V0_FIRST_30_PRODUCTION_PATH_REPAIR.json`.
