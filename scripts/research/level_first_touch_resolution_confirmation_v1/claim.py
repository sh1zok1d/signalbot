"""Evidence label frozen before the BitMEX outcome. Not a PASS/FAIL verdict."""

from __future__ import annotations

from . import constants as K


def supporting_clauses(primary: dict, epochs: list[dict], loeo: list[dict]) -> dict:
    delta = primary.get("estimate")
    lo = primary.get("ci_low")
    eligible = [row for row in epochs if row.get("n", 0) >= K.MIN_EPOCH_PAIRS and row.get("estimate") is not None]
    n_pos = sum(1 for row in eligible if row["estimate"] > 0)
    loeo_ok = (
        len(loeo) == 3
        and all(row.get("estimate") is not None and row["estimate"] > 0 for row in loeo)
    )
    return {
        "positive": bool(delta is not None and delta > 0),
        "interval_excludes_zero": bool(lo is not None and lo > 0),
        "at_least_3pp": bool(delta is not None and delta >= K.PRACTICAL_SCALE),
        "epoch_sign": bool(len(eligible) >= 2 and n_pos >= 2),
        "loeo_sign": bool(loeo_ok),
        "eligible_epochs": len(eligible),
        "positive_epochs": n_pos,
    }


def evidence_label(primary: dict, clauses: dict) -> str:
    keys = ("positive", "interval_excludes_zero", "at_least_3pp", "epoch_sign", "loeo_sign")
    if all(clauses[k] for k in keys):
        return K.LABEL_REPLICATED
    hi = primary.get("ci_high")
    if hi is not None and hi < K.PRACTICAL_SCALE:
        return K.LABEL_NO_MATERIAL
    if clauses["positive"] and clauses["interval_excludes_zero"] and clauses["at_least_3pp"]:
        return K.LABEL_UNSTABLE
    return K.LABEL_LIMITED


def claim_decision(n_analysis: int, label: str) -> dict:
    issued = n_analysis >= K.MIN_PAIRS_CLAIM
    replicated = label == K.LABEL_REPLICATED and issued
    return {
        "claim_level": "L2" if issued else "not_issued",
        "claim_status": "issued" if issued else "not_issued",
        "replicated_historical_mechanism": bool(replicated),
        "current_probability": False,
        "product_integration_candidate": "YES" if replicated else "NO",
    }
