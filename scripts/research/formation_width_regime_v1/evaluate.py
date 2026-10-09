"""Outcome entry point for FORMATION_WIDTH_REGIME_V1.

Refuses before a separate owner go. This module does not load a market panel.
A later go uses amendment_a2.assign_route.
"""

from __future__ import annotations

REFUSAL_OUTCOME = "REFUSING_OUTCOME_BEFORE_OWNER_GO"


def main() -> int:
    raise SystemExit(REFUSAL_OUTCOME)


if __name__ == "__main__":
    raise SystemExit(main())
