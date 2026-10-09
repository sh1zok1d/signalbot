"""Owner go is required before any market fit.

The support census is a different entry point. This one does not load prices.
"""

from __future__ import annotations

from . import constants as K


def main() -> None:
    if not K.OWNER_GO:
        raise SystemExit("AWAITING_OWNER_GO")
    raise SystemExit("FORECAST_IMPLEMENTATION_INVALID")


if __name__ == "__main__":
    main()
