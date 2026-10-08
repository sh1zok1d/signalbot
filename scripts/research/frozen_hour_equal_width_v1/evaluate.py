"""Outcome entry point for FROZEN_HOUR_EQUAL_WIDTH_V1.

Refuses until a separate owner go. This module does not load a market file
and does not score a barrier.
"""

from __future__ import annotations

from . import constants as K


def main() -> int:
    raise SystemExit(K.REFUSAL_OUTCOME)


if __name__ == "__main__":
    raise SystemExit(main())
