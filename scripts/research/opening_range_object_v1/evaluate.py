"""Outcome evaluator guard. No historical resolution label is computed."""

from __future__ import annotations

REFUSAL = "REFUSING_OUTCOME_BEFORE_OWNER_GO"


def main() -> int:
    raise SystemExit(REFUSAL)


if __name__ == "__main__":
    raise SystemExit(main())
