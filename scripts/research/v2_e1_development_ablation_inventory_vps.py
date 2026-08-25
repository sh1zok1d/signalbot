#!/usr/bin/env python3
"""Legacy-VPS launcher for the frozen E1 development ablation census.

The VPS research adapter can expose nested JSON-like values as immutable
``mappingproxy`` objects.  The frozen census implementation only needs to
modify the current 5m trigger row for CB ablations, but its original helper
used ``copy.deepcopy`` on the whole detached row; Python cannot deepcopy a
``mappingproxy`` and aborts before any ablation evidence is produced.

This launcher changes NO detector/variant semantics.  It imports the frozen
census module, replaces only that row-copy helper with a deterministic
Mapping->dict thaw, then calls the original ``main()``.  Holdout/read guards,
variant definitions, production detector calls, output schema, and CLI remain
owned by the original module unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import scripts.research.v2_e1_development_ablation_inventory as impl


def _thaw_jsonlike(value: Any) -> Any:
    """Detach immutable JSON-like containers without pickle/deepcopy.

    Production/research rows may contain ``mappingproxy`` or other Mapping
    implementations.  Only container identity changes; scalar values are
    preserved exactly.  The source object is never mutated.
    """
    if isinstance(value, Mapping):
        return {key: _thaw_jsonlike(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_thaw_jsonlike(item) for item in value)
    if isinstance(value, list):
        return [_thaw_jsonlike(item) for item in value]
    return value


def _neutralize_taker_and_optional_agreement(
    inputs: impl.V2CompressionBreakoutInputs,
    *,
    sign: int,
    force_agreement: bool,
    neutralize_context: bool,
) -> impl.V2CompressionBreakoutInputs:
    if sign not in (-1, 1):
        raise ValueError(sign)

    changed_rows: list[Mapping] = []
    for source in inputs.consensus_5m_rows:
        row = _thaw_jsonlike(source)
        if not isinstance(row, dict):
            raise TypeError(f"thawed consensus row must be dict, got {type(row).__name__}")

        coverage = row["coverage_by_metric"]
        if not isinstance(coverage, dict):
            raise TypeError("thawed coverage_by_metric must be dict")
        taker_cov = coverage["taker_flow"]
        if not isinstance(taker_cov, dict):
            raise TypeError("thawed taker_flow coverage must be dict")
        taker_cov["ratio"] = 1.0

        confidence = row["data_confidence_by_metric"]
        if not isinstance(confidence, dict):
            raise TypeError("thawed data_confidence_by_metric must be dict")
        confidence["taker_flow"] = 100.0

        row["taker_delta_notional_usd_sum"] = float(sign)
        if force_agreement:
            row["price_direction_agreement"] = 1.0
        changed_rows.append(row)

    context = impl._neutral_context(inputs.context) if neutralize_context else inputs.context
    return replace(
        inputs,
        context=context,
        consensus_5m_rows=tuple(changed_rows),
    )


# Narrow monkeypatch: only the copy helper that failed on mappingproxy.
impl._neutralize_taker_and_optional_agreement = _neutralize_taker_and_optional_agreement


if __name__ == "__main__":
    raise SystemExit(impl.main())
