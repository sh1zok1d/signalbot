"""Pre-outcome amendment A2. Routing specificity only.

A null endpoint does not veto another endpoint. No statistic, threshold,
sample, or outcome definition changes. This module does not load a market panel.
"""

from __future__ import annotations

from .amendment_a1 import (
    ENDPOINTS,
    INCREMENTAL_COVARIATE,
    ROUTE_INFORMATION_LIMITED,
    ROUTE_NO_DETECTABLE,
    ROUTE_NOT_SPECIFIC,
    ROUTE_PRESENT,
    ROUTE_REDUNDANT,
    ROUTE_UNSTABLE,
    RV_PREV_ROLE,
)

_REQUIRED = (
    "foundation_clears",
    "year_unstable",
    "incremental_formation_clears",
    "foundation_abs",
    "lag_placebo_abs",
)


def current_state_specific(row: dict) -> bool:
    """True when this endpoint's own lag placebo is strictly smaller than its own foundation."""
    return float(row["lag_placebo_abs"]) < float(row["foundation_abs"])


def _endpoint_row(name: str, row: dict) -> dict:
    specific = current_state_specific(row)
    return {
        "endpoint": name,
        "foundation_rho": row.get("foundation_rho"),
        "foundation_clears": bool(row["foundation_clears"]),
        "year_unstable": bool(row["year_unstable"]),
        "year_stable": not bool(row["year_unstable"]),
        "incremental_rho": row.get("incremental_rho"),
        "incremental_clears": bool(row["incremental_formation_clears"]),
        "lag_placebo_rho": row.get("lag_placebo_rho"),
        "current_state_specific": specific,
    }


def assign_route(endpoints: dict[str, dict], *, information_limited: bool) -> dict:
    """Existential route. Endpoint order is the frozen name order, not effect size."""
    if set(endpoints) != set(ENDPOINTS):
        raise RuntimeError("inferential endpoints must be ACTIVITY and DISPLACEMENT")
    for payload in endpoints.values():
        if "rv_prev_clears" in payload or "incremental_prev_clears" in payload:
            raise RuntimeError("RV_PREV is not an inferential input")
    if information_limited:
        return _decision(ROUTE_INFORMATION_LIMITED, interpretable=None, rows=[], supporting=[], held=[])
    rows = []
    for name in ENDPOINTS:
        row = endpoints[name]
        for key in _REQUIRED:
            if key not in row:
                raise RuntimeError(f"{name} is missing {key}")
        rows.append(_endpoint_row(name, row))
    clearing = [row for row in rows if row["foundation_clears"]]
    if not clearing:
        return _decision(ROUTE_NO_DETECTABLE, interpretable=None, rows=rows, supporting=[], held=[])
    if all(row["year_unstable"] for row in clearing):
        return _decision(ROUTE_UNSTABLE, interpretable=None, rows=rows, supporting=[], held=[])
    stable = [row for row in clearing if row["year_stable"]]
    if all(not row["incremental_clears"] for row in stable):
        return _decision(ROUTE_REDUNDANT, interpretable=None, rows=rows, supporting=[], held=[])
    supporting = [
        row["endpoint"]
        for row in rows
        if row["foundation_clears"] and row["year_stable"] and row["incremental_clears"] and row["current_state_specific"]
    ]
    held = [
        row["endpoint"]
        for row in rows
        if row["foundation_clears"] and row["year_stable"] and row["incremental_clears"] and not row["current_state_specific"]
    ]
    if supporting:
        return _decision(ROUTE_PRESENT, interpretable=True, rows=rows, supporting=supporting, held=held)
    return _decision(ROUTE_NOT_SPECIFIC, interpretable=False, rows=rows, supporting=[], held=held)


def _decision(name: str, *, interpretable: bool | None, rows: list, supporting: list, held: list) -> dict:
    return {
        "route": name,
        "interpretable_as_current_state": interpretable,
        "incremental_covariate": INCREMENTAL_COVARIATE,
        "rv_prev_role": RV_PREV_ROLE,
        "endpoints": rows,
        "route_supporting_endpoints": list(supporting),
        "incremental_qualified_but_not_specific_endpoints": list(held),
    }
