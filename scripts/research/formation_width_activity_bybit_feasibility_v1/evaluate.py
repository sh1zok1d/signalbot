"""Outcome gate. This feasibility unit never scores the next-hour endpoint."""

from __future__ import annotations

from . import constants as K


def main() -> None:
    raise SystemExit(K.REFUSAL_BEFORE_GO)


if __name__ == "__main__":
    main()
