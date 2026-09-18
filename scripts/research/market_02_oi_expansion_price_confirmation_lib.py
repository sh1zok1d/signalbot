"""MARKET-02 frozen-prereg implementation.

Synthetic/in-memory scientific implementation only. This module does not ARM
or authorize bound CORE/OI execution. Episode construction deliberately
reuses the semantics-preserving MARKET-01 fast path; MARKET-02 changes only
the frozen population/group/outcome mapping and confirmatory identity.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import namespace_seed, pcg64_generator
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import optimal_stationary_block_length
from scripts.research.market_01_episode_construction_fast import construct_episodes_fast
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    ALPHA, BOOTSTRAP_B, ERA_BOUNDS_MS, OiView, PriceView, SYNTHETIC_SNAPSHOT,
)

RESEARCH_ID = "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION"
CONFIRMATION_THRESHOLD = 0.25
TOTAL_MIN, CAND_MIN, BASE_MIN, USABLE_STRATA_MIN, STRATUM_GROUP_MIN = 100, 30, 30, 3, 5
SEED_MATERIAL = RESEARCH_ID + "|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999"
SEED_MATERIAL_SHA256 = "19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f"
MARKET_02_BOOTSTRAP_SEED = 1852983754304692007

CLASS_NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
CLASS_NO_EVIDENCE = "NO_EVIDENCE"
CLASS_ROBUST = "EVIDENCE_WITH_PROSPECTIVE_ROBUSTNESS"
CLASS_FRAGILE = "EVIDENCE_FRAGILE_NONSTATIONARITY"

PRICE_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"


class Market02ExecutionNotAuthorized(RuntimeError):
    pass


def _refuse_bound(price: PriceView, oi: OiView) -> None:
    if price.snapshot_id == PRICE_SNAPSHOT_ID or oi.snapshot_id == OI_SNAPSHOT_ID:
        raise Market02ExecutionNotAuthorized("bound MARKET-02 execution is not armed")


def confirmatory_rows(price: PriceView, oi: OiView) -> list[dict[str, Any]]:
    _refuse_bound(price, oi)
    episodes = construct_episodes_fast(price, oi)
    rows: list[dict[str, Any]] = []
    for rec in episodes:
        if not rec.confirmatory_eligible or not rec.qualifying_impulse:
            continue
        # Frozen MARKET-02 population is conditional on OI expansion.
        if not rec.oi_expansion:
            continue
        if rec.continuation_ratio is None or not math.isfinite(float(rec.continuation_ratio)):
            continue
        if rec.reversal_return is None or rec.stratum_id is None or rec.D is None:
            continue
        # MARKET-01 stored reversal_return = -D*outcome. MARKET-02 continuation
        # is exactly its negative under the shared temporal geometry.
        continuation_return = -float(rec.reversal_return)
        rows.append({
            "impulse_end_t_ms": int(rec.impulse_end_t_ms),
            "impulse_start_ms": int(rec.impulse_start_ms),
            "decision_T_ms": int(rec.decision_T_ms),
            "continuation_return": continuation_return,
            "candidate_indicator": 1 if float(rec.continuation_ratio) > CONFIRMATION_THRESHOLD else 0,
            "stratum_id": str(rec.stratum_id),
        })
    rows.sort(key=lambda r: (r["decision_T_ms"], r["impulse_start_ms"]))
    return rows


def usable_strata(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    out = []
    for sid in sorted({str(r["stratum_id"]) for r in rows}):
        c = sum(str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 1 for r in rows)
        b = sum(str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 0 for r in rows)
        if c >= STRATUM_GROUP_MIN and b >= STRATUM_GROUP_MIN:
            out.append(sid)
    return out


def support_gate(rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    s = set(usable)
    primary = [dict(r) for r in rows if str(r["stratum_id"]) in s]
    nc = sum(int(r["candidate_indicator"]) == 1 for r in primary)
    nb = len(primary) - nc
    ok = len(primary) >= TOTAL_MIN and nc >= CAND_MIN and nb >= BASE_MIN and len(usable) >= USABLE_STRATA_MIN
    return {"ok": ok, "TOTAL_ELIGIBLE_EPISODES": len(primary), "CANDIDATE_EPISODES": nc,
            "BASELINE_EPISODES": nb, "USABLE_STRATA": len(usable),
            "usable_stratum_ids": list(usable), "primary_rows": primary}


def design_matrix(rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    idx = {sid: i for i, sid in enumerate(usable)}
    x = np.zeros((len(rows), len(usable) + 1), dtype=np.float64)
    y = np.empty(len(rows), dtype=np.float64)
    for i, r in enumerate(rows):
        x[i, idx[str(r["stratum_id"])]] = 1.0
        x[i, -1] = float(r["candidate_indicator"])
        y[i] = float(r["continuation_return"])
    return x, y


def fit(rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    if not rows or not usable:
        return {"ok": False, "reason": "empty_design"}
    x, y = design_matrix(rows, usable)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        return {"ok": False, "reason": "nonfinite_design"}
    xtx = x.T @ x
    if int(np.linalg.matrix_rank(xtx)) != int(x.shape[1]):
        return {"ok": False, "reason": "rank_deficient"}
    try:
        beta = np.linalg.solve(xtx, x.T @ y)
    except np.linalg.LinAlgError:
        return {"ok": False, "reason": "linalg_error"}
    if not np.all(np.isfinite(beta)):
        return {"ok": False, "reason": "nonfinite_beta"}
    return {"ok": True, "beta_confirmation": float(beta[-1])}


def _within_stratum(values: np.ndarray, sids: Sequence[str]) -> np.ndarray:
    out = values.astype(np.float64, copy=True)
    for sid in sorted(set(sids)):
        mask = np.asarray([x == sid for x in sids], dtype=bool)
        out[mask] -= float(np.mean(out[mask]))
    return out


def _stationary_indices(n: int, p: float, rng: np.random.Generator) -> np.ndarray:
    idx = np.empty(n, dtype=np.int64)
    idx[0] = int(rng.integers(0, n))
    for i in range(1, n):
        idx[i] = int(rng.integers(0, n)) if float(rng.random()) < p else (idx[i-1] + 1) % n
    return idx


def bootstrap(rows: Sequence[Mapping[str, Any]], usable: Sequence[str], beta_hat: float) -> dict[str, Any]:
    x = np.asarray([float(r["candidate_indicator"]) for r in rows])
    y = np.asarray([float(r["continuation_return"]) for r in rows])
    sids = [str(r["stratum_id"]) for r in rows]
    xt, yt = _within_stratum(x, sids), _within_stratum(y, sids)
    z = xt * (yt - xt * float(beta_hat))
    b_hat = float(optimal_stationary_block_length(z))
    if not math.isfinite(b_hat) or b_hat <= 0:
        return {"ok": False, "reason": "invalid_block_length"}
    block = int(round(min(max(b_hat, 1.0), float(len(rows)))))
    p = 1.0 / block
    rng = pcg64_generator(namespace_seed(MARKET_02_BOOTSTRAP_SEED, "BOOTSTRAP", "PRIMARY_BETA_CONFIRMATION"))
    vals = np.empty(BOOTSTRAP_B, dtype=np.float64)
    base = [dict(r) for r in rows]
    for j in range(BOOTSTRAP_B):
        ii = _stationary_indices(len(base), p, rng)
        sample = [base[int(i)] for i in ii]
        f = fit(sample, usable)
        if not f["ok"]:
            return {"ok": False, "reason": "bootstrap_refit_failed"}
        vals[j] = f["beta_confirmation"]
    se = float(np.std(vals, ddof=1))
    if not math.isfinite(se) or se <= 0:
        return {"ok": False, "reason": "invalid_se"}
    t_obs = float(beta_hat) / se
    t_star = (vals - float(beta_hat)) / se
    p_one = (1.0 + float(np.count_nonzero(t_star >= t_obs))) / (BOOTSTRAP_B + 1.0)
    return {"ok": True, "b_hat": b_hat, "p_geom": p, "se_hat": se, "p_one_sided": p_one}


def _era(t: int) -> str | None:
    for name, lo, hi in ERA_BOUNDS_MS:
        if lo <= int(t) < hi:
            return name
    return None


def robustness(rows: Sequence[Mapping[str, Any]], usable: Sequence[str]) -> dict[str, Any]:
    all_ok = True
    loeo = {}
    for era, _, _ in ERA_BOUNDS_MS:
        rem = [r for r in rows if _era(int(r["decision_T_ms"])) != era]
        gate = support_gate(rem, usable)
        per_sid_ok = all(
            sum(str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 1 for r in rem) >= 5
            and sum(str(r["stratum_id"]) == sid and int(r["candidate_indicator"]) == 0 for r in rem) >= 5
            for sid in usable
        )
        f = fit(rem, usable) if gate["ok"] and per_sid_ok else {"ok": False}
        ok = bool(f.get("ok") and float(f["beta_confirmation"]) > 0.0)
        loeo[era] = {"ok": ok, "beta_confirmation": f.get("beta_confirmation")}
        all_ok &= ok
    nc = sum(int(r["candidate_indicator"]) == 1 for r in rows)
    shares = {}
    for era, _, _ in ERA_BOUNDS_MS:
        c = sum(int(r["candidate_indicator"]) == 1 and _era(int(r["decision_T_ms"])) == era for r in rows)
        shares[era] = c / nc if nc else float("nan")
    max_share = max(shares.values()) if shares else float("nan")
    conc_ok = math.isfinite(max_share) and max_share <= 0.50
    return {"ROBUSTNESS_SIGN_STABLE": all_ok, "ROBUSTNESS_CONCENTRATION_OK": conc_ok,
            "candidate_era_shares": shares, "max_candidate_share": max_share, "LOEO": loeo}


def evaluate_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = sorted((dict(r) for r in rows), key=lambda r: (int(r["decision_T_ms"]), int(r.get("impulse_start_ms", 0))))
    usable = usable_strata(rows)
    gate = support_gate(rows, usable)
    base = {"research_id": RESEARCH_ID, "MARKET_02_TEST_CALIBRATED": False,
            "MARKET_02_ARMED": False, "MARKET_02_EXECUTION_AUTHORIZED": False,
            "PROTECTED_OOS_TOUCHED": False, "support": {k:v for k,v in gate.items() if k != "primary_rows"}}
    if not gate["ok"]:
        return {**base, "detected": False, "robustness": None, "final_classification": CLASS_NOT_IDENTIFIABLE}
    primary = gate["primary_rows"]
    f = fit(primary, usable)
    if not f["ok"]:
        return {**base, "detected": False, "robustness": None, "final_classification": CLASS_NOT_IDENTIFIABLE}
    boot = bootstrap(primary, usable, f["beta_confirmation"])
    if not boot["ok"]:
        return {**base, "detected": False, "robustness": None, "final_classification": CLASS_NOT_IDENTIFIABLE}
    detected = f["beta_confirmation"] > 0.0 and boot["p_one_sided"] <= ALPHA
    if not detected:
        return {**base, **f, "bootstrap": boot, "detected": False, "robustness": None, "final_classification": CLASS_NO_EVIDENCE}
    rob = robustness(primary, usable)
    robust = rob["ROBUSTNESS_SIGN_STABLE"] and rob["ROBUSTNESS_CONCENTRATION_OK"]
    return {**base, **f, "bootstrap": boot, "detected": True, "robustness": rob,
            "final_classification": CLASS_ROBUST if robust else CLASS_FRAGILE}


def evaluate_market_02(price: PriceView, oi: OiView) -> dict[str, Any]:
    _refuse_bound(price, oi)
    return evaluate_rows(confirmatory_rows(price, oi))
