"""Exact frozen D2 BitMEX replication evaluator.

Scientific formulas are reused, not forked. Real BitMEX outcome evaluation
is gated behind an immutable execution permit that does not exist in this
unit. Synthetic / constructed-row evaluation is allowed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.d2_bitmex_pre2020 import (
    AUTHORITY_REL,
    FUTURE_BARS,
    PRE2020_END_EXCLUSIVE,
    RV_TRAILING_WINDOW,
    refuse_binance_protected_path,
    refuse_d2_outcome_request,
    row_timestamp_complete,
    sha256_bytes,
    utc_ms,
)
from scripts.research.d2_bitmex_replication_prereg import (
    AUTHORITATIVE_RELATIVE_EFFECT,
    BINDING_REL,
    CANONICAL_REL,
    D2_BITMEX_REPLICATION_RANDOM_SEED,
    FROZEN_EXPECTED_ELIGIBLE_N,
    FROZEN_FIRST_RULE_ELIGIBLE_T,
    FROZEN_LAST_RULE_ELIGIBLE_T,
    IMPLEMENTATION_FILES,
    JSON_REL,
    N_REPLICATES as PREREG_N_REPLICATES,
    file_sha256,
    load_sealed_open_times,
    verify_frozen_eligibility,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    arithmetic_mae,
    btc_ret_24h,
    btc_side_from_ret,
    rv_btc_24h,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar

UTC = timezone.utc

EXECUTION_AUTHORIZED = False
EXECUTION_PERMIT_REL = "docs/research/D2_BITMEX_REPLICATION_EXECUTION_PERMIT.json"
N_REPLICATES = int(PREREG_N_REPLICATES)
REPLICATION_RANDOM_SEED = int(D2_BITMEX_REPLICATION_RANDOM_SEED)
RV_PCTL = 90.0
RELATIVE_PRACTICAL_BAR = float(AUTHORITATIVE_RELATIVE_EFFECT)

SCIENTIFIC_RV = rv_btc_24h
SCIENTIFIC_RET = btc_ret_24h
SCIENTIFIC_SIDE = btc_side_from_ret
SCIENTIFIC_MAE = arithmetic_mae
SCIENTIFIC_RV_MASK = C.rv_abstention_mask
SCIENTIFIC_CONSTRUCT_ROW = C.construct_discovery_row

CLASS_SUPPORTED = "D2_BITMEX_REPLICATION_SUPPORTED"
CLASS_NOT_SUPPORTED = "D2_BITMEX_REPLICATION_NOT_SUPPORTED"
CLASS_INVALID = "D2_BITMEX_REPLICATION_INVALID"

FROZEN_CANONICAL_JSONL_SHA256 = "b145013cbcda34294104a0234c89fa9e27965bded66e3bc18b23753dde03fd0f"
FROZEN_CANONICAL_GZ_SHA256 = "8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa"


class ExecutionNotAuthorized(RuntimeError):
    """BitMEX D2 scientific execution is not authorized."""


class SampleIdentityError(RuntimeError):
    """Constructed eligible sample is not the frozen 1069 / first / last T."""


@dataclass(frozen=True)
class ExecutionPermit:
    """Future immutable permit. None exists in this unit."""

    prereg_sha256: str
    execution_binding_sha256: str
    implementation_sha256: str
    canonical_jsonl_sha256: str
    run_identity: str


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _pcg64(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def verify_eligibility(*, repo: Path | None = None) -> dict[str, Any]:
    """Timestamp/gap/hash census only. No D2 outcomes."""
    return verify_frozen_eligibility(repo)


def last_future_bar_end(decision: datetime) -> datetime:
    return decision + timedelta(minutes=5 * FUTURE_BARS)


def assert_pre2020_future(decision: datetime) -> None:
    if last_future_bar_end(decision) >= PRE2020_END_EXCLUSIVE:
        raise ValueError("FUTURE_CROSSES_2020")
    if decision.year >= 2020:
        raise ValueError("DECISION_IN_2020")


def timestamp_complete_decisions(
    present_open_ms: set[int],
    *,
    raw_open_ms: int,
) -> list[datetime]:
    """00:05 UTC decisions whose feature, entry, and 24h future bars exist."""
    first = datetime.fromtimestamp(int(raw_open_ms) / 1000.0, tz=UTC)
    cursor = datetime(first.year, first.month, first.day, 0, 5, tzinfo=UTC)
    if cursor < first:
        cursor = cursor + timedelta(days=1)
    complete: list[datetime] = []
    while cursor < PRE2020_END_EXCLUSIVE:
        if row_timestamp_complete(
            utc_ms(cursor),
            present_open_ms=present_open_ms,
            raw_open_ms=raw_open_ms,
            assume_complete_grid=False,
        ):
            complete.append(cursor)
        cursor = cursor + timedelta(days=1)
    return complete


def construct_rows_for_decisions(
    decisions: Sequence[datetime],
    perp: Mapping[int, PerpBar],
) -> list[C.DiscoveryRow]:
    """Reuse frozen construct_discovery_row. Skip price-path ineligible T."""
    rows: list[C.DiscoveryRow] = []
    for moment in decisions:
        row = SCIENTIFIC_CONSTRUCT_ROW(utc_ms(moment), perp)
        if row is not None:
            rows.append(row)
    return rows


def split_warmup_eligible(
    rows: Sequence[C.DiscoveryRow],
) -> tuple[list[C.DiscoveryRow], list[C.DiscoveryRow]]:
    if len(rows) < RV_TRAILING_WINDOW:
        raise SampleIdentityError("INSUFFICIENT_VALID_RV_HISTORY")
    warmup = list(rows[:RV_TRAILING_WINDOW])
    eligible = list(rows[RV_TRAILING_WINDOW:])
    return warmup, eligible


def assert_frozen_sample_identity(eligible: Sequence[C.DiscoveryRow]) -> None:
    if len(eligible) != FROZEN_EXPECTED_ELIGIBLE_N:
        raise SampleIdentityError(f"ELIGIBLE_N:{len(eligible)}")
    first = C.utc_from_ms(eligible[0].t_ms)
    last = C.utc_from_ms(eligible[-1].t_ms)
    if first != FROZEN_FIRST_RULE_ELIGIBLE_T:
        raise SampleIdentityError(f"FIRST_T:{_iso(first)}")
    if last != FROZEN_LAST_RULE_ELIGIBLE_T:
        raise SampleIdentityError(f"LAST_T:{_iso(last)}")


def rv_abstention_mask(rows: Sequence[C.DiscoveryRow]) -> np.ndarray:
    """Exact frozen D2 mask: P90 of prior 250 valid RVs, t excluded, strict >."""
    return SCIENTIFIC_RV_MASK(rows)


def pooled_k_is_forbidden(years: Sequence[int], abstain: np.ndarray) -> None:
    years_arr = np.asarray(list(years), dtype=np.int64)
    mask = np.asarray(abstain, dtype=bool)
    unique = sorted(set(int(y) for y in years_arr.tolist()))
    k_y = [int(mask[years_arr == y].sum()) for y in unique]
    if int(sum(k_y)) != int(mask.sum()):
        raise ValueError("K_YEAR_SUM")
    if len(unique) >= 2 and int(mask.sum()) > 0 and all(k == 0 for k in k_y):
        raise ValueError("POOLED_K_EMPTY_YEARS")


def year_matched_control_masks(
    years: Sequence[int],
    abstain: np.ndarray,
    *,
    seed: int,
    n_replicates: int,
) -> list[np.ndarray]:
    """Year-matched RATE_MATCHED_RANDOM_ABSTENTION using frozen PCG64 seed."""
    years_arr = np.asarray(list(years), dtype=np.int64)
    mask = np.asarray(abstain, dtype=bool)
    if years_arr.shape != mask.shape:
        raise ValueError("YEAR_ABSTAIN_SHAPE")
    pooled_k_is_forbidden(years_arr, mask)
    rng = _pcg64(int(seed))
    unique_years = sorted(set(int(y) for y in years_arr.tolist()))
    year_indices = {year: np.flatnonzero(years_arr == year) for year in unique_years}
    year_counts = {year: int(mask[idx].sum()) for year, idx in year_indices.items()}
    replicates: list[np.ndarray] = []
    n = int(mask.size)
    for _ in range(int(n_replicates)):
        drawn = np.zeros(n, dtype=bool)
        for year, idx in year_indices.items():
            count = year_counts[year]
            if count == 0:
                continue
            if count > int(idx.size):
                raise ValueError(f"ABSTAIN_COUNT_EXCEEDS_YEAR:{year}")
            chosen = rng.choice(idx, size=count, replace=False)
            drawn[chosen] = True
        if int(drawn.sum()) != int(mask.sum()):
            raise ValueError("RATE_MATCH_COUNT_MISMATCH")
        replicates.append(drawn)
    return replicates


def year_matched_control_replicate_means(
    years: Sequence[int],
    severity: Sequence[float],
    abstain: np.ndarray,
    *,
    seed: int,
    n_replicates: int = N_REPLICATES,
) -> np.ndarray:
    """Year-matched control means. No pooled K."""
    sev = np.asarray(list(severity), dtype=np.float64)
    masks = year_matched_control_masks(
        years, abstain, seed=int(seed), n_replicates=int(n_replicates)
    )
    return np.asarray([float(np.mean(sev[rep])) for rep in masks], dtype=np.float64)


def compute_mu_rule(severity: Sequence[float], abstain: np.ndarray) -> float:
    sev = np.asarray(list(severity), dtype=np.float64)
    mask = np.asarray(abstain, dtype=bool)
    if sev.shape != mask.shape:
        raise ValueError("MU_RULE_SHAPE")
    if not mask.any():
        raise ValueError("MU_RULE_EMPTY_ABSTAIN")
    return float(np.mean(sev[mask]))


def compute_delta(mu_rule: float, mu_control_mean: float) -> float:
    return float(mu_rule) - float(mu_control_mean)


def compute_mc_p(control_means: Sequence[float], mu_rule: float) -> float:
    ctrl = np.asarray(list(control_means), dtype=np.float64)
    return float((1.0 + float(np.sum(ctrl >= float(mu_rule)))) / (1.0 + float(ctrl.size)))


def statistical_gate(mu_rule: float, control_p95: float) -> bool:
    return bool(float(mu_rule) > float(control_p95))


def practical_gate(delta: float, unconditional_mean: float) -> bool:
    uncond = float(unconditional_mean)
    if uncond == 0.0:
        return False
    return bool(float(delta) >= RELATIVE_PRACTICAL_BAR * uncond)


def classify_replication(
    *,
    integrity_invalid: bool,
    statistical: bool,
    practical: bool,
    yearly_positive: Sequence[bool] | None = None,
) -> str:
    """Pooled gates only. Yearly diagnostics cannot rescue or veto."""
    del yearly_positive  # F12: explicitly unused
    if integrity_invalid:
        return CLASS_INVALID
    if statistical and practical:
        return CLASS_SUPPORTED
    return CLASS_NOT_SUPPORTED


def yearly_diagnostics(
    years: Sequence[int],
    severity: Sequence[float],
    abstain: np.ndarray,
    control_masks: Sequence[np.ndarray],
) -> dict[str, Any]:
    """Diagnostic only. Must not enter classification."""
    years_arr = np.asarray(list(years), dtype=np.int64)
    sev = np.asarray(list(severity), dtype=np.float64)
    mask = np.asarray(abstain, dtype=bool)
    out: dict[str, Any] = {}
    for year in (2017, 2018, 2019):
        year_sel = years_arr == year
        n = int(year_sel.sum())
        k = int((mask & year_sel).sum())
        payload: dict[str, Any] = {
            "eligible_n": n,
            "candidate_k": k,
            "MU_RULE": None,
            "MU_CONTROL_MEAN": None,
            "DELTA": None,
        }
        if n > 0 and k > 0:
            mu_y = float(np.mean(sev[mask & year_sel]))
            ctrl_y = []
            for rep in control_masks:
                sel = np.asarray(rep, dtype=bool) & year_sel
                if np.any(sel):
                    ctrl_y.append(float(np.mean(sev[sel])))
            if ctrl_y:
                mu_c = float(np.mean(ctrl_y))
                payload["MU_RULE"] = mu_y
                payload["MU_CONTROL_MEAN"] = mu_c
                payload["DELTA"] = float(mu_y - mu_c)
        out[str(year)] = payload
    return out


def evaluate_constructed_rows(
    rows: Sequence[C.DiscoveryRow],
    *,
    seed: int = REPLICATION_RANDOM_SEED,
    n_replicates: int = N_REPLICATES,
    enforce_sample_identity: bool = False,
) -> dict[str, Any]:
    """Scientific evaluation on an already-constructed row sequence.

    ``rows`` must include the 250 valid warmup observations followed by
    eligible observations. Does not load BitMEX.
    """
    warmup, eligible = split_warmup_eligible(rows)
    integrity_invalid = False
    identity_error = None
    if enforce_sample_identity:
        try:
            assert_frozen_sample_identity(eligible)
        except SampleIdentityError as exc:
            integrity_invalid = True
            identity_error = str(exc)
    mask_full = rv_abstention_mask(rows)
    if int(mask_full[:RV_TRAILING_WINDOW].sum()) != 0:
        raise ValueError("WARMUP_ABSTAINED")
    mask = mask_full[RV_TRAILING_WINDOW:]
    years = [row.year for row in eligible]
    severity = [row.severity for row in eligible]
    sev = np.asarray(severity, dtype=np.float64)
    uncond = float(np.mean(sev)) if sev.size else float("nan")
    if not mask.any():
        result = {
            "integrity_invalid": integrity_invalid,
            "identity_error": identity_error,
            "WARMUP_N": int(len(warmup)),
            "ELIGIBLE_N": int(len(eligible)),
            "ABSTAIN_COUNT": 0,
            "MU_RULE": None,
            "MU_CONTROL_MEAN": None,
            "DELTA": None,
            "CONTROL_P95": None,
            "UNCONDITIONAL_MEAN": uncond,
            "MC_P": None,
            "STATISTICAL_GATE": False,
            "PRACTICAL_GATE": False,
            "PRIMARY_PASS": False,
            "YEARLY_DIAGNOSTICS": yearly_diagnostics(years, severity, mask, []),
            "CLASSIFICATION": classify_replication(
                integrity_invalid=integrity_invalid,
                statistical=False,
                practical=False,
            ),
            "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
            "NO_YEARLY_RESCUE": True,
            "D2_BITMEX_OUTCOME_COMPUTED": False,
        }
        return result
    mu_rule = compute_mu_rule(severity, mask)
    control_masks = year_matched_control_masks(
        years, mask, seed=int(seed), n_replicates=int(n_replicates)
    )
    control_means = np.asarray(
        [float(np.mean(sev[rep])) for rep in control_masks], dtype=np.float64
    )
    mu_control = float(np.mean(control_means))
    delta = compute_delta(mu_rule, mu_control)
    control_p95 = float(np.percentile(control_means, 95))
    mc_p = compute_mc_p(control_means, mu_rule)
    statistical = statistical_gate(mu_rule, control_p95)
    practical = practical_gate(delta, uncond)
    classification = classify_replication(
        integrity_invalid=integrity_invalid,
        statistical=statistical,
        practical=practical,
    )
    return {
        "integrity_invalid": integrity_invalid,
        "identity_error": identity_error,
        "WARMUP_N": int(len(warmup)),
        "ELIGIBLE_N": int(len(eligible)),
        "ABSTAIN_COUNT": int(mask.sum()),
        "MU_RULE": mu_rule,
        "MU_CONTROL_MEAN": mu_control,
        "DELTA": delta,
        "CONTROL_P95": control_p95,
        "UNCONDITIONAL_MEAN": uncond,
        "MC_P": mc_p,
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_GATE": practical,
        "PRIMARY_PASS": bool(statistical and practical and not integrity_invalid),
        "YEARLY_DIAGNOSTICS": yearly_diagnostics(years, severity, mask, control_masks),
        "CLASSIFICATION": classification,
        "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
        "NO_YEARLY_RESCUE": True,
        "N_RANDOM_CONTROLS": int(n_replicates),
        "REPLICATION_RANDOM_SEED": int(seed),
        "D2_BITMEX_OUTCOME_COMPUTED": False,
    }


def current_implementation_file_sha256(repo: Path) -> dict[str, str]:
    return {rel: file_sha256(repo / rel) for rel in IMPLEMENTATION_FILES}


def current_artifact_sha256(repo: Path) -> dict[str, str]:
    return {
        "PREREG_ARTIFACT_SHA256": file_sha256(repo / JSON_REL),
        "EXECUTION_BINDING_SHA256": file_sha256(repo / BINDING_REL),
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "SOURCE_AUTHORITY_SHA256": file_sha256(repo / AUTHORITY_REL),
        "IMPLEMENTATION_FILE_SHA256": current_implementation_file_sha256(repo),
    }


def compute_run_identity(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def bars_from_canonical_jsonl(jsonl_bytes: bytes) -> dict[int, PerpBar]:
    """Parse official 5m bins keyed by open_time_ms. No fill. No network."""
    bars: dict[int, PerpBar] = {}
    prev: int | None = None
    for line in jsonl_bytes.splitlines():
        if not line:
            continue
        row = json.loads(line)
        open_ms = int(row["open_time_ms"])
        if prev is not None and open_ms <= prev:
            raise ValueError(f"NON_MONOTONIC_OR_DUPLICATE:{open_ms}")
        if open_ms >= utc_ms(PRE2020_END_EXCLUSIVE):
            raise ValueError(f"OPEN_AT_OR_AFTER_2020:{open_ms}")
        bars[open_ms] = PerpBar(
            open_time_ms=open_ms,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        )
        prev = open_ms
    return bars


def load_sealed_canonical_bytes(repo: Path) -> bytes:
    """Fail-closed hash check. Returns JSONL bytes. Does not build outcomes."""
    _authority, _opens, gz_bytes, jsonl_bytes = load_sealed_open_times(repo)
    if sha256_bytes(gz_bytes) != FROZEN_CANONICAL_GZ_SHA256:
        raise ExecutionNotAuthorized("CANONICAL_GZ_HASH_MISMATCH")
    if sha256_bytes(jsonl_bytes) != FROZEN_CANONICAL_JSONL_SHA256:
        raise ExecutionNotAuthorized("CANONICAL_JSONL_HASH_MISMATCH")
    return jsonl_bytes


def _require_execution_permit(
    execution_authority: Mapping[str, Any] | ExecutionPermit | None,
    *,
    repo: Path,
) -> None:
    permit_path = repo / EXECUTION_PERMIT_REL
    if not permit_path.is_file():
        raise ExecutionNotAuthorized("NO_EXECUTION_PERMIT")
    if execution_authority is None:
        raise ExecutionNotAuthorized("EXECUTION_AUTHORITY_REQUIRED")
    if EXECUTION_AUTHORIZED is not True:
        raise ExecutionNotAuthorized("EXECUTION_AUTHORIZED_FALSE")
    if isinstance(execution_authority, ExecutionPermit):
        authority = {
            "prereg_sha256": execution_authority.prereg_sha256,
            "execution_binding_sha256": execution_authority.execution_binding_sha256,
            "implementation_sha256": execution_authority.implementation_sha256,
            "canonical_jsonl_sha256": execution_authority.canonical_jsonl_sha256,
            "run_identity": execution_authority.run_identity,
        }
    else:
        authority = dict(execution_authority)
    hashes = current_artifact_sha256(repo)
    expected = {
        "prereg_sha256": hashes["PREREG_ARTIFACT_SHA256"],
        "execution_binding_sha256": hashes["EXECUTION_BINDING_SHA256"],
        "implementation_sha256": hashes["IMPLEMENTATION_FILE_SHA256"][
            "scripts/research/d2_bitmex_replication_evaluator.py"
        ],
        "canonical_jsonl_sha256": FROZEN_CANONICAL_JSONL_SHA256,
    }
    for key, value in expected.items():
        if str(authority.get(key)) != value:
            raise ExecutionNotAuthorized(f"PERMIT_MISMATCH:{key}")
    if str(authority.get("run_identity") or "") != str(
        json.loads(permit_path.read_text(encoding="utf-8")).get("run_identity") or ""
    ):
        raise ExecutionNotAuthorized("PERMIT_RUN_IDENTITY_MISMATCH")
    refuse_d2_outcome_request("PERMIT_PRESENT_BUT_UNIT_REFUSES")


def load_sealed_bitmex_bars(
    repo: Path,
    *,
    execution_authority: Mapping[str, Any] | ExecutionPermit | None,
) -> dict[int, PerpBar]:
    """Load sealed OHLC. Hard-gated: no permit, no bars."""
    _require_execution_permit(execution_authority, repo=repo)
    jsonl_bytes = load_sealed_canonical_bytes(repo)
    return bars_from_canonical_jsonl(jsonl_bytes)


def execute_replication(
    **kwargs: Any,
) -> dict[str, Any]:
    """Real BitMEX scientific replication. Refused until a future permit exists."""
    repo = kwargs.get("repo")
    base = repo if isinstance(repo, Path) else C.repo_root()
    refuse_binance_protected_path(base / CANONICAL_REL)
    _require_execution_permit(kwargs.get("execution_authority"), repo=base)
    census = verify_eligibility(repo=base)
    jsonl_bytes = load_sealed_canonical_bytes(base)
    perp = bars_from_canonical_jsonl(jsonl_bytes)
    raw_open = utc_ms(
        datetime.fromisoformat(
            str(census["legal"]["RAW_DATA_START"]).replace("Z", "+00:00")
        )
    )
    decisions = timestamp_complete_decisions(set(perp), raw_open_ms=raw_open)
    rows = construct_rows_for_decisions(decisions, perp)
    evaluated = evaluate_constructed_rows(
        rows,
        seed=REPLICATION_RANDOM_SEED,
        n_replicates=N_REPLICATES,
        enforce_sample_identity=True,
    )
    evaluated["D2_BITMEX_OUTCOME_COMPUTED"] = True
    return evaluated
