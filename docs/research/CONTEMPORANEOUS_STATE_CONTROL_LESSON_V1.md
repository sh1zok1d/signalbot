# Contemporaneous-state control — lesson V1

**Status:** `RESEARCH_NOTE (2026-10-09)`. Not a new claim ladder and not a product change.

A control for an object built from the current market must not delete the contemporaneous state and then assign the resulting gap to a special geometry or boundary.

`FROZEN_HOUR_RANGE` compared a real frozen hour with a weekday half-rotation pseudo. That pseudo kept a shape and moved another era's width onto today. The published UTC_00 gap was +9.48 pp. The same-surface equal-width diagnosis then forced the pseudo to today's width and the common-support gap went from +9.55 pp to −0.58 pp. The pseudo resolution rate moved from 82.31% to 92.43%, next to the real rate 91.85%. The 2023 and 2024 gaps did not survive. An equal-width read on Binance spot 2017–2019 also found no resolution difference.

The rotated control had removed today's width, which was part of today's volatility regime. The gap measured that removal. It did not identify a special hour boundary.

Later units that ask whether a current-market feature is a state have to keep that state in the object. A baseline may use information from before the decision. It does not residualize the feature on the same hour's own range or volatility and then call the leftover a boundary.
