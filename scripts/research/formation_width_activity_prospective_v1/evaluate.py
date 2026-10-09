"""Evaluator gate for FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1.

Until a separate owner go for the first formal checkpoint, the only legal
result is a refusal. This module does not load a market panel, does not import
a data loader, and does not compute a forward association.
"""

from __future__ import annotations

from . import constants as K


def main() -> None:
    raise SystemExit(K.REFUSAL_BEFORE_GO)


if __name__ == "__main__":
    main()
