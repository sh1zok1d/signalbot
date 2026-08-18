# Local QA command surface. Every target below acts ONLY on the local test
# resources (isolated .venv + the signalbot-qa Docker project). Nothing here
# touches production infra, the server, secrets, or live exchange APIs.

PY          := .venv/bin/python
ENV_FILE    := .env.test
COMPOSE     := docker compose -p signalbot-qa --env-file $(ENV_FILE) -f docker-compose.test.yml

.DEFAULT_GOAL := help
.PHONY: help qa-bootstrap qa-status qa-fast qa-full qa-infra-smoke qa-check \
        qa-last-failure qa-logs qa-reset qa-down

help: ## Show available QA commands
	@echo "Signalbot QA commands:"
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  %-18s %s\n", $$1, $$2}'

# Order-only: create .env.test from the example if it does not exist yet. Never
# overwrites an existing file (make only runs this rule when the target is absent).
$(ENV_FILE):
	cp .env.test.example $(ENV_FILE)

qa-bootstrap: ## First-time setup: venv, deps, test stack, smoke, fast tests
	./scripts/qa-bootstrap.sh

qa-status: ## Show env + service status (no secrets)
	./scripts/qa-status.sh

qa-fast: ## Fast unit suite — no Docker, no network
	$(PY) -m pytest -q -m "not slow and not manual"

qa-full: ## Full pytest suite (still no live internet; excludes manual tests)
	$(PY) -m pytest -q -m "not manual"

qa-infra-smoke: $(ENV_FILE) ## Bring up the test stack and run the infra smoke test
	$(COMPOSE) up -d --wait
	SIGNALBOT_ENV_FILE=$(ENV_FILE) $(PY) scripts/qa-smoke.py

qa-check: ## Same base as CI: compileall + pytest
	$(PY) -m compileall -q -x '(\.venv|\.git|__pycache__)' .
	$(PY) -m pytest -q -m "not manual"

qa-last-failure: ## Re-run only the tests that failed last time
	$(PY) -m pytest -q --last-failed

qa-logs: $(ENV_FILE) ## Follow the test-stack logs
	$(COMPOSE) logs --tail=200 -f

qa-reset: ## DESTROY only the test containers + volumes (guarded)
	./scripts/qa-reset.sh

qa-down: $(ENV_FILE) ## Stop the test stack (keeps volumes)
	$(COMPOSE) down
