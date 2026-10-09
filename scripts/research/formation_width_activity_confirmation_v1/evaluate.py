"""Outcome evaluator gate for FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1.

Until a separate owner go, the only legal result is a refusal. This module
does not load a market panel and does not compute the next-hour endpoint.
"""

from __future__ import annotations

from . import constants as K


def main() -> None:
    raise SystemExit(K.REFUSAL_BEFORE_GO)


if __name__ == "__main__":
    main()
