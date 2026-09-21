#!/usr/bin/env bash
# One-shot setup: virtualenv + dependencies.
set -euo pipefail

python3 -m venv .venv
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -r requirements.txt
else
  .venv/bin/pip install -r requirements.txt
fi
echo "Done. Next: ./scripts/download_data.sh"
