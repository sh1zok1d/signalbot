"""Aggregation of the frozen three-way barrier label. This is not a new classifier."""

from __future__ import annotations

from typing import Optional


def resolved(label: Optional[str]) -> Optional[int]:
    """1 if BREAK or REJECT, 0 if NEITHER, None if the touch is not in the analysis set."""
    if label is None or label == "AMBIGUOUS":
        return None
    if label in ("BREAK", "REJECT"):
        return 1
    if label == "NEITHER":
        return 0
    raise ValueError(f"unknown barrier label {label}")


def indicator(label: Optional[str], name: str) -> Optional[int]:
    """1 if the frozen label equals `name`, 0 for the other two analysis labels."""
    if resolved(label) is None:
        return None
    if name not in ("BREAK", "REJECT", "NEITHER"):
        raise ValueError(name)
    return 1 if label == name else 0
