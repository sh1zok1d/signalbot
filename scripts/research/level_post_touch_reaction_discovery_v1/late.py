"""Late labels on bars j+3 .. j+48. Import this only after the design is frozen.

The touch bar and the two early bars are not in this window. The window ends on
the same bar as the parent 4h horizon. It is not extended by 15 minutes.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import constants as K
from .reactions import _passage


def late_label(high: np.ndarray, low: np.ndarray, j: int, side: int, zone_low: float,
               zone_high: float, x: float) -> Optional[str]:
    """BREAK, REJECT, NEITHER, AMBIGUOUS, or None when the remaining window is unusable."""
    return _passage(
        high, low, j + K.LATE_START_OFFSET, j + K.LATE_STOP_OFFSET,
        side, zone_low, zone_high, x,
    )
