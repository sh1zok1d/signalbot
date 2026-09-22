"""Guarded scientific execution entry. Real outcomes are forbidden in this unit."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.research.discovery_sprint_03 import common as C
from scripts.research.discovery_sprint_03 import d9 as D9
from scripts.research.discovery_sprint_03 import d10 as D10
from scripts.research.discovery_sprint_03 import d11 as D11


def _assert_authorized() -> None:
    if not C.EXECUTION_AUTHORIZED:
        C.refuse_real_scientific_execution()


def evaluate_d9_real(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    _assert_authorized()
    raise C.RealScientificOutcomeForbidden("D9_EXECUTED_GUARD")


def evaluate_d10_real(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    _assert_authorized()
    raise C.RealScientificOutcomeForbidden("D10_EXECUTED_GUARD")


def evaluate_d11_real(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    _assert_authorized()
    raise C.RealScientificOutcomeForbidden("D11_EXECUTED_GUARD")


def evaluate_supplied_arrays(
    card: str,
    *,
    event_values: Sequence[float],
    control_values: Sequence[float],
    yearly_event: Mapping[str, Sequence[float]],
    yearly_control: Mapping[str, Sequence[float]] | None = None,
    support: Mapping[str, Any],
    authorized: bool | None = None,
) -> dict[str, Any]:
    """Pure array evaluator. Still refused unless explicitly authorized.

    A later execution unit must pass authorized=True AND set a documented
    execution permit. Importing this module never reads market data.
    """

    if not (C.EXECUTION_AUTHORIZED if authorized is None else authorized):
        C.refuse_real_scientific_execution()
    if card == "D9":
        return D9.evaluate_d9_scientific(event_values, control_values, yearly_event, support=support)
    if card == "D10":
        return D10.evaluate_d10_scientific(
            event_values,
            control_values,
            yearly_event,
            yearly_control or {},
            support=support,
        )
    if card == "D11":
        return D11.evaluate_d11_scientific(
            event_values,
            control_values,
            yearly_event,
            yearly_control or {},
            support=support,
        )
    raise C.Sprint03IntegrityError(f"UNKNOWN_CARD:{card}")


def main() -> None:
    C.refuse_real_scientific_execution()


if __name__ == "__main__":
    main()
