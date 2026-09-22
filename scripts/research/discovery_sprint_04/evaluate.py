"""Guarded scientific execution entry. Real D12/D13 outcomes are forbidden here."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d12 as D12
from scripts.research.discovery_sprint_04 import d13 as D13


def _assert_authorized() -> None:
    if not C.EXECUTION_AUTHORIZED:
        C.refuse_real_scientific_execution()


def evaluate_d12_real(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    _assert_authorized()
    raise C.RealScientificOutcomeForbidden("D12_EXECUTED_GUARD")


def evaluate_d13_real(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    _assert_authorized()
    raise C.RealScientificOutcomeForbidden("D13_EXECUTED_GUARD")


def evaluate_supplied_arrays(
    card: str,
    *,
    support: Mapping[str, Any],
    authorized: bool | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if not (C.EXECUTION_AUTHORIZED if authorized is None else authorized):
        C.refuse_real_scientific_execution()
    if card == "D12":
        return D12.evaluate_d12_scientific(
            kwargs["us_a"],
            kwargs["us_delta"],
            kwargs["us_years"],
            kwargs["plus_pool"],
            kwargs["minus_pool"],
            support=support,
        )
    if card == "D13":
        return D13.evaluate_d13_scientific(
            kwargs["weekly_ic"],
            kwargs["weekly_years"],
            kwargs["weekly_raw_spreads"],
            support=support,
            n=kwargs["n"],
            no_post_t_close_selected_n=kwargs["no_post_t_close_selected_n"],
            pinned_taker_fee=kwargs["pinned_taker_fee"],
        )
    raise C.Sprint04IntegrityError(f"UNKNOWN_CARD:{card}")


def main() -> None:
    C.refuse_real_scientific_execution()


if __name__ == "__main__":
    main()
