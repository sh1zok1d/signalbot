"""Canonical Discovery Sprint 03 scientific execution runner.

Ordinary import does not load market data and cannot emit results.
Real execution requires an explicit CLI authorization flag and matching
EXECUTION_ROOT implementation hashes. EXECUTION_AUTHORIZED in common.py
stays false.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from scripts.research.discovery_sprint_03 import common as C
from scripts.research.discovery_sprint_03 import d9 as D9
from scripts.research.discovery_sprint_03 import d10 as D10
from scripts.research.discovery_sprint_03 import d11 as D11


UNIT = "DISCOVERY_SPRINT_03_CANONICAL_SCIENTIFIC_EXECUTION"
EXECUTION_ROOT = "e2852f57ee946ec8380f09fa4cf834579c40f872"
EXPECTED_TREE = "8805ee7d39b29c267589e7f9400384ebdb1f66ca"
AUTHORIZE_FLAG = "--authorize-canonical-sprint03-execution"

IMPLEMENTATION_HASHES_AT_ROOT = {
    "docs/research/DISCOVERY_SPRINT_03.json": (
        "58699f5613193fb02dda5255dcae55d4624d5afcdc8591a4a95605de30d56000"
    ),
    "docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.json": (
        "53b3b87adfa3d87d936c3940d603edaab65bf9436e9d49975c7347a3aa6ed036"
    ),
    "scripts/research/discovery_sprint_03/common.py": (
        "f26c1b84cdfa2c2343b3b2816acff00360929143add189bff34c2e1674523e8d"
    ),
    "scripts/research/discovery_sprint_03/d9.py": (
        "479e1d4c58289433d57b5e1a0f4f9976a9e1cb5a10203b15c4f74fcf863a00f6"
    ),
    "scripts/research/discovery_sprint_03/d10.py": (
        "4364be6c75a6655f212c2b2d5bd4bec13c2dd3c327cf0de25ebc4817e303bf78"
    ),
    "scripts/research/discovery_sprint_03/d11.py": (
        "df09c1280c7d869990bfdbbf515a2349f74affa210c7b4e9d91aaf4108fe7797"
    ),
}

EXPECTED_D9_STRUCTURE = {
    "RAW_EXTREME_BAR_N": 35157,
    "RETAINED_EVENT_N": 8349,
    "REFRACTORY_DROPPED_EXTREME_N": 26808,
    "CLOSING_EVENT_N": 7184,
    "RAW_ELIGIBLE_CLOSING_CONTROL_N": 130238,
    "MATCHED_CONTROL_N": 7184,
    "ALL_MATCHED_CELLS_BALANCED": True,
}
EXPECTED_D10_STRUCTURE = {
    "EVENT_N": 4442,
    "RAW_ELIGIBLE_CONTROL_N": 21368,
    "MATCHED_CONTROL_N": 4442,
    "ALL_MATCHED_CELLS_BALANCED": True,
}
EXPECTED_D11_STRUCTURE = {
    "EVENT_N": 39,
    "CONTROL_N": 551,
}

RESULT_REL = {
    "D9": (
        "docs/research/discovery_results/D9_DISCOVERY_RESULT.json",
        "docs/research/discovery_results/D9_DISCOVERY_RESULT.md",
    ),
    "D10": (
        "docs/research/discovery_results/D10_DISCOVERY_RESULT.json",
        "docs/research/discovery_results/D10_DISCOVERY_RESULT.md",
    ),
    "D11": (
        "docs/research/discovery_results/D11_DISCOVERY_RESULT.json",
        "docs/research/discovery_results/D11_DISCOVERY_RESULT.md",
    ),
    "BATCH": (
        "docs/research/DISCOVERY_SPRINT_03_RESULT.json",
        "docs/research/DISCOVERY_SPRINT_03_RESULT.md",
    ),
}


class ExecutionAbortedPreResult(RuntimeError):
    """Scientific classification must not be persisted."""


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(C.jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def payload_sha256(payload: Mapping[str, Any]) -> str:
    hashed = {k: v for k, v in payload.items() if k != "RESULT_PAYLOAD_SHA256"}
    return C.sha256_bytes(canonical_json(hashed).encode("utf-8"))


def current_implementation_hashes(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in IMPLEMENTATION_HASHES_AT_ROOT:
        path = repo / rel
        if not path.is_file():
            raise ExecutionAbortedPreResult(f"MISSING_IMPLEMENTATION_FILE:{rel}")
        C.assert_openable(path)
        out[rel] = C.sha256_file(path)
    return out


def verify_implementation_identity(repo: Path) -> dict[str, str]:
    observed = current_implementation_hashes(repo)
    for rel, expected in IMPLEMENTATION_HASHES_AT_ROOT.items():
        if observed[rel] != expected:
            raise ExecutionAbortedPreResult(
                f"IMPLEMENTATION_HASH_MISMATCH:{rel}:expected={expected}:observed={observed[rel]}"
            )
    return observed


def git_sha(repo: Path, rev: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", rev],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def verify_execution_root(repo: Path) -> None:
    root = git_sha(repo, EXECUTION_ROOT)
    if root != EXECUTION_ROOT:
        raise ExecutionAbortedPreResult(f"EXECUTION_ROOT_UNRESOLVED:{root}")
    tree = git_sha(repo, f"{EXECUTION_ROOT}^{{tree}}")
    if tree != EXPECTED_TREE:
        raise ExecutionAbortedPreResult(f"EXECUTION_TREE_MISMATCH:{tree}")
    for rel in IMPLEMENTATION_HASHES_AT_ROOT:
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"{EXECUTION_ROOT}:{rel}"],
            check=True,
            capture_output=True,
        )
        digest = C.sha256_bytes(proc.stdout)
        if digest != IMPLEMENTATION_HASHES_AT_ROOT[rel]:
            raise ExecutionAbortedPreResult(f"EXECUTION_ROOT_FILE_MISMATCH:{rel}")


def _year_of_ms(open_ms: int) -> str:
    return str(datetime.fromtimestamp(int(open_ms) / 1000.0, tz=C.UTC).year)


def _assert_structure(card: str, census: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    for key, want in expected.items():
        got = census.get(key)
        if got != want:
            raise ExecutionAbortedPreResult(
                f"{card}_STRUCTURE_MISMATCH:{key}:expected={want}:observed={got}"
            )


def assemble_d9(repo: Path) -> dict[str, Any]:
    perp, spot, identity = D9.load_d9_inputs(repo=repo)
    if not identity.get("IDENTITY_OK"):
        raise ExecutionAbortedPreResult("D9_IDENTITY_NOT_OK")
    census = D9.d9_feasibility_census(perp, spot, include_indices=True)
    _assert_structure("D9", census, EXPECTED_D9_STRUCTURE)
    if census.get("SHARE_VALUES_EMITTED"):
        raise ExecutionAbortedPreResult("D9_CENSUS_EMITTED_SHARE")
    open_ms, perp_close, spot_close = D9._aligned_m06_series(perp, spot)
    d_values = np.log(perp_close / spot_close)
    horizon = C.D9_H_BARS
    extreme = set(census["IS_EXTREME_IDX"])

    def share_at(i: int) -> float:
        j = i + horizon
        if j >= int(open_ms.size) or int(open_ms[j]) != int(open_ms[i]) + horizon * C.BAR_5M_MS:
            raise ExecutionAbortedPreResult(f"D9_HORIZON_BROKEN:{i}")
        if int(open_ms[i]) + horizon * C.BAR_5M_MS >= C.PROTECTED_START_MS:
            raise ExecutionAbortedPreResult(f"D9_PROTECTED_HORIZON:{i}")
        rp = math.log(float(perp_close[j]) / float(perp_close[i]))
        rs = math.log(float(spot_close[j]) / float(spot_close[i]))
        row = D9.d9_relative_resolution(float(d_values[i]), rp, rs)
        if not row.eligible or row.perp_resolution_share is None:
            raise ExecutionAbortedPreResult(f"D9_INELIGIBLE_SELECTED_BAR:{i}:{row.reason}")
        return float(row.perp_resolution_share)

    event_ids_by_cell = census["CLOSING_EVENT_IDS_BY_CELL"]
    control_ids_by_cell = census["MATCHED_CONTROL_IDS_BY_CELL"]
    event_shares: list[float] = []
    yearly_event: dict[str, list[float]] = {}
    event_by_cell: dict[str, list[float]] = {}
    for cell in sorted(event_ids_by_cell):
        cell_shares: list[float] = []
        for i in event_ids_by_cell[cell]:
            if int(i) not in extreme:
                raise ExecutionAbortedPreResult(f"D9_CLOSING_EVENT_NOT_EXTREME:{i}")
            share = share_at(int(i))
            cell_shares.append(share)
            event_shares.append(share)
            year = _year_of_ms(int(open_ms[int(i)]))
            yearly_event.setdefault(year, []).append(share)
        event_by_cell[cell] = cell_shares
    control_shares: list[float] = []
    control_by_cell: dict[str, list[float]] = {}
    for cell in sorted(control_ids_by_cell):
        cell_shares = []
        for i in control_ids_by_cell[cell]:
            if int(i) in extreme:
                raise ExecutionAbortedPreResult(f"D9_CONTROL_IS_EXTREME:{i}")
            share = share_at(int(i))
            cell_shares.append(share)
            control_shares.append(share)
        control_by_cell[cell] = cell_shares
    if len(event_shares) != EXPECTED_D9_STRUCTURE["CLOSING_EVENT_N"]:
        raise ExecutionAbortedPreResult(f"D9_EVENT_SHARE_N:{len(event_shares)}")
    if len(control_shares) != EXPECTED_D9_STRUCTURE["MATCHED_CONTROL_N"]:
        raise ExecutionAbortedPreResult(f"D9_CONTROL_SHARE_N:{len(control_shares)}")
    support = {
        "SUPPORT_PASS": bool(census["SUPPORT_PASS"]),
        "IDENTITY_OK": True,
    }
    summary = D9.evaluate_d9_scientific(
        event_shares,
        control_shares,
        yearly_event,
        support=support,
        event_by_cell=event_by_cell,
        control_by_cell=control_by_cell,
    )
    event_med = float(summary["MEDIAN_SHARE"])
    control_med = float(summary["CONTROL_MEDIAN_SHARE"])
    return {
        "CENSUS": {k: v for k, v in census.items() if not str(k).endswith("_IDX") and "IDS_BY_CELL" not in str(k)},
        "IDENTITY": {k: v for k, v in identity.items() if k != "FILES_OPENED"},
        "FILES_OPENED_N": len(identity.get("FILES_OPENED") or []),
        "EVALUATION": summary,
        "MEDIAN_EVENT_SHARE": event_med,
        "MEDIAN_MATCHED_CONTROL_SHARE": control_med,
        "DELTA_VS_HALF": event_med - C.D9_NULL_SHARE,
        "DELTA_VS_CONTROL": event_med - control_med,
    }


def assemble_d10(repo: Path) -> dict[str, Any]:
    btc, eth, identity = D10.load_d10_inputs(repo=repo)
    if not identity.get("IDENTITY_OK"):
        raise ExecutionAbortedPreResult("D10_IDENTITY_NOT_OK")
    if identity.get("OPENED_1H_BARS_PARQUET"):
        raise ExecutionAbortedPreResult("D10_OPENED_PROTECTED_1H_BARS")
    census = D10.d10_feasibility_census(btc, eth, include_indices=True)
    _assert_structure("D10", census, EXPECTED_D10_STRUCTURE)
    if census.get("PERSISTENCE_VALUES_EMITTED"):
        raise ExecutionAbortedPreResult("D10_CENSUS_EMITTED_PERSISTENCE")
    hours, r_btc, r_eth, _adj = D10.aligned_return_arrays(btc, eth)
    event_ids_by_cell = census["EVENT_IDS_BY_CELL"]
    control_ids_by_cell = census["MATCHED_CONTROL_IDS_BY_CELL"]

    def target_at(t: int) -> float:
        row = D10.d10_fixed_beta_row(r_btc, r_eth, int(t), window=C.D10_WINDOW)
        return float(row["primary_target"])

    event_targets: list[float] = []
    yearly_event: dict[str, list[float]] = {}
    yearly_control: dict[str, list[float]] = {}
    event_by_cell: dict[str, list[float]] = {}
    control_by_cell: dict[str, list[float]] = {}
    control_targets: list[float] = []
    used: set[int] = set()
    for cell in sorted(event_ids_by_cell):
        cell_vals: list[float] = []
        for t in event_ids_by_cell[cell]:
            val = target_at(int(t))
            cell_vals.append(val)
            event_targets.append(val)
            year = _year_of_ms(int(hours[int(t)]))
            yearly_event.setdefault(year, []).append(val)
        event_by_cell[cell] = cell_vals
        ctrl_vals: list[float] = []
        for t in control_ids_by_cell.get(cell, []):
            if int(t) in used:
                raise ExecutionAbortedPreResult(f"D10_CONTROL_REUSED:{t}")
            used.add(int(t))
            val = target_at(int(t))
            ctrl_vals.append(val)
            control_targets.append(val)
            year = _year_of_ms(int(hours[int(t)]))
            yearly_control.setdefault(year, []).append(val)
        control_by_cell[cell] = ctrl_vals
        if len(ctrl_vals) != len(cell_vals):
            raise ExecutionAbortedPreResult(f"D10_CELL_UNBALANCED:{cell}")
    if len(event_targets) != EXPECTED_D10_STRUCTURE["EVENT_N"]:
        raise ExecutionAbortedPreResult(f"D10_EVENT_TARGET_N:{len(event_targets)}")
    if len(control_targets) != EXPECTED_D10_STRUCTURE["MATCHED_CONTROL_N"]:
        raise ExecutionAbortedPreResult(f"D10_CONTROL_TARGET_N:{len(control_targets)}")
    support = {"SUPPORT_PASS": bool(census["SUPPORT_PASS"]), "IDENTITY_OK": True}
    summary = D10.evaluate_d10_scientific(
        event_targets,
        control_targets,
        yearly_event,
        yearly_control,
        support=support,
        event_by_cell=event_by_cell,
        control_by_cell=control_by_cell,
    )
    delta = float(summary["DELTA"])
    return {
        "CENSUS": {k: v for k, v in census.items() if not str(k).endswith("_IDX") and "IDS_BY_CELL" not in str(k)},
        "IDENTITY": {k: v for k, v in identity.items() if k != "FILES_OPENED"},
        "FILES_OPENED_N": len(identity.get("FILES_OPENED") or []),
        "EVALUATION": summary,
        "MEAN_EVENT": float(summary["MEAN_EVENT"]),
        "MEAN_MATCHED_CONTROL": float(summary["MEAN_CONTROL"]),
        "DELTA": delta,
        "DELTA_BPS": delta * 10_000.0,
    }


def assemble_d11(repo: Path) -> dict[str, Any]:
    events, hour_returns, identity = D11.load_d11_inputs(repo=repo)
    if not identity.get("IDENTITY_OK"):
        raise ExecutionAbortedPreResult("D11_IDENTITY_NOT_OK")
    census = D11.d11_feasibility_census(events, hour_returns)
    _assert_structure("D11", census, EXPECTED_D11_STRUCTURE)
    if census.get("RV_VALUES_EMITTED"):
        raise ExecutionAbortedPreResult("D11_CENSUS_EMITTED_RV")
    if int(census.get("MIN_CONTROLS_AMONG_EVENTS") or 0) < 44:
        raise ExecutionAbortedPreResult("D11_MIN_CONTROLS_BELOW_FREEZE")

    event_starts: list[int] = []
    event_rv: list[float] = []
    yearly_event: dict[str, list[float]] = {}
    yearly_control: dict[str, list[float]] = {}
    fomc_hours: set[int] = set()
    event_cells: set[str] = set()
    for event in events:
        if event.get("EVENT_FAMILY") != "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS":
            continue
        announ = int(event["ANNOUNCEMENT_UTC_MS"])
        if announ >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"D11_PROTECTED_EVENT:{event.get('EVENT_ID')}")
        start = D11.first_hour_open_ms(announ)
        if not D11._hour_complete_for_rv(hour_returns, start):
            continue
        rv = D11.post_event_rv_6h(hour_returns, announ)
        event_starts.append(start)
        event_rv.append(float(rv))
        dt = datetime.fromtimestamp(start / 1000.0, tz=C.UTC)
        yearly_event.setdefault(str(dt.year), []).append(float(rv))
        event_cells.add(f"{dt.year}:{dt.weekday()}:{dt.hour}")
        for k in range(C.D11_HORIZON_HOURS):
            fomc_hours.add(start + k * C.HOUR_MS)
    event_start_set = set(event_starts)
    control_rv: list[float] = []
    for start_ms in sorted(hour_returns):
        if start_ms in event_start_set:
            continue
        if D11.window_overlaps_fomc(start_ms, fomc_hours):
            continue
        ret = hour_returns.get(start_ms)
        if ret is None or not math.isfinite(ret):
            continue
        if not D11._hour_complete_for_rv(hour_returns, start_ms):
            continue
        dt = datetime.fromtimestamp(start_ms / 1000.0, tz=C.UTC)
        cell = f"{dt.year}:{dt.weekday()}:{dt.hour}"
        if cell not in event_cells:
            continue
        rv = D11.post_event_rv_6h(hour_returns, start_ms)
        control_rv.append(float(rv))
        yearly_control.setdefault(str(dt.year), []).append(float(rv))
    if len(event_rv) != EXPECTED_D11_STRUCTURE["EVENT_N"]:
        raise ExecutionAbortedPreResult(f"D11_EVENT_RV_N:{len(event_rv)}")
    if len(control_rv) != EXPECTED_D11_STRUCTURE["CONTROL_N"]:
        raise ExecutionAbortedPreResult(f"D11_CONTROL_RV_N:{len(control_rv)}")
    support = {"SUPPORT_PASS": bool(census["SUPPORT_PASS"]), "IDENTITY_OK": True}
    summary = D11.evaluate_d11_scientific(
        event_rv,
        control_rv,
        yearly_event,
        yearly_control,
        support=support,
    )
    return {
        "CENSUS": census,
        "IDENTITY": {k: v for k, v in identity.items() if k != "FILES_OPENED"},
        "FILES_OPENED_N": len(identity.get("FILES_OPENED") or []),
        "EVALUATION": summary,
        "MEAN_EVENT_RV_6H": float(summary["MEAN_EVENT_RV"]),
        "MEAN_CONTROL_RV_6H": float(summary["MEAN_CONTROL_RV"]),
        "RELATIVE": float(summary["RELATIVE"]),
    }


def _common_result_fields(*, hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "UNIT": UNIT,
        "KIND": "CANONICAL_SCIENTIFIC_EXECUTION",
        "EXECUTION_ROOT": EXECUTION_ROOT,
        "EXPECTED_TREE": EXPECTED_TREE,
        "IMPLEMENTATION_HASHES": dict(hashes),
        "EVIDENCE_LABEL": "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA",
        "NOT_PROVEN_ALPHA": True,
        "NOT_VALIDATED_TRADING_EDGE": True,
        "NOT_PRODUCTION_SIGNAL": True,
        "NOT_CONFIRMED_MECHANISM": True,
        "NOT_CAUSAL_PROOF": True,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "D7_RERUN_PERFORMED": False,
        "D8_EXECUTED": False,
        "MARKET_07_CREATED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
    }


def build_d9_result(assembled: Mapping[str, Any], hashes: Mapping[str, str]) -> dict[str, Any]:
    ev = assembled["EVALUATION"]
    payload = {
        **_common_result_fields(hashes=hashes),
        "DISCOVERY_ID": "D9",
        "NAME": "VENUE_DISLOCATION_RESOLUTION_STRUCTURE",
        "D9_EXECUTED": True,
        "CLASSIFICATION": ev["CLASSIFICATION"],
        "DATA_IDENTITY": assembled["IDENTITY"],
        "M06_SNAPSHOT_ID": C.M06_SNAPSHOT_ID,
        "STRUCTURAL": {
            key: assembled["CENSUS"].get(key)
            for key in EXPECTED_D9_STRUCTURE
        },
        "SEEDS": {
            "P_HALF": C.D9_SEED,
            "P_CONTROL": C.D9_CONTROL_PERM_SEED,
            "CONTROL_SAMPLE": C.D9_CONTROL_SAMPLE_SEED,
            "N_RANDOMIZATIONS": C.D9_N_RANDOMIZATIONS,
        },
        "MEDIAN_EVENT_SHARE": assembled["MEDIAN_EVENT_SHARE"],
        "MEDIAN_MATCHED_CONTROL_SHARE": assembled["MEDIAN_MATCHED_CONTROL_SHARE"],
        "DELTA_VS_HALF": assembled["DELTA_VS_HALF"],
        "DELTA_VS_CONTROL": assembled["DELTA_VS_CONTROL"],
        "P_HALF": ev["P_HALF"],
        "P_CONTROL": ev["P_CONTROL"],
        "STATISTICAL_GATE": ev["STATISTICAL_GATE"],
        "PRACTICAL_GATE": ev["PRACTICAL_GATE"],
        "TEMPORAL_GATE": ev["TEMPORAL_GATE"],
        "YEARLY_MEDIAN_SHARE": ev["YEARLY_MEDIAN_SHARE"],
        "PRIMARY_LOCATION_STATISTIC": C.D9_PRIMARY_LOCATION_STATISTIC,
        "SCIENTIFIC_CLAIM_MAY_ESTABLISH": "CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION",
        "SCIENTIFIC_CLAIM_MUST_NOT_ESTABLISH": [
            "PRICE_DISCOVERY_LEADERSHIP",
            "CAUSAL_LEADERSHIP",
            "WHICH_VENUE_MOVED_FIRST",
            "TRADING_ALPHA",
        ],
        "LIMITATIONS": [
            "SHARE is conditional on TOTAL_CLOSURE>0 (collider/selection).",
            "Adaptive discovery on historically exposed 2022-2024 MARKET-06 overlap.",
            "Not price-discovery leadership, causal leadership, or trading alpha.",
        ],
    }
    payload["RESULT_PAYLOAD_SHA256"] = payload_sha256(payload)
    return payload


def build_d10_result(assembled: Mapping[str, Any], hashes: Mapping[str, str]) -> dict[str, Any]:
    ev = assembled["EVALUATION"]
    payload = {
        **_common_result_fields(hashes=hashes),
        "DISCOVERY_ID": "D10",
        "NAME": "BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE",
        "D10_EXECUTED": True,
        "CLASSIFICATION": ev["CLASSIFICATION"],
        "DATA_IDENTITY": assembled["IDENTITY"],
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "CORE_ETH_SNAPSHOT_ID": C.CORE_ETH_SNAPSHOT_ID,
        "REGRESSION_SPECIFICATION": C.D10_REGRESSION_SPECIFICATION,
        "STRUCTURAL": {
            key: assembled["CENSUS"].get(key)
            for key in EXPECTED_D10_STRUCTURE
        },
        "SEEDS": {
            "PERMUTATION": C.D10_SEED,
            "CONTROL_SAMPLE": C.D10_CONTROL_SAMPLE_SEED,
            "N_RANDOMIZATIONS": C.D10_N_RANDOMIZATIONS,
        },
        "MEAN_EVENT": assembled["MEAN_EVENT"],
        "MEAN_MATCHED_CONTROL": assembled["MEAN_MATCHED_CONTROL"],
        "DELTA": assembled["DELTA"],
        "DELTA_BPS": assembled["DELTA_BPS"],
        "MC_P": ev["MC_P"],
        "STATISTICAL_GATE": ev["STATISTICAL_GATE"],
        "PRACTICAL_GATE": ev["PRACTICAL_GATE"],
        "TEMPORAL_GATE": ev["TEMPORAL_GATE"],
        "YEARLY_DELTA": ev["YEARLY_DELTA"],
        "PERMUTATION_RULE": ev.get("PERMUTATION_RULE"),
        "TEMPORAL_DEPENDENCE_LIMITATION": C.D10_TEMPORAL_DEPENDENCE_LIMITATION,
        "LIMITATIONS": [
            C.D10_TEMPORAL_DEPENDENCE_LIMITATION,
            "Does not validate MARKET-05.",
            "Does not imply generic ETH lead-lag or trading alpha.",
        ],
    }
    payload["RESULT_PAYLOAD_SHA256"] = payload_sha256(payload)
    return payload


def build_d11_result(assembled: Mapping[str, Any], hashes: Mapping[str, str]) -> dict[str, Any]:
    ev = assembled["EVALUATION"]
    payload = {
        **_common_result_fields(hashes=hashes),
        "DISCOVERY_ID": "D11",
        "NAME": "SCHEDULED_FOMC_EVENT_VOL_RESPONSE",
        "D11_EXECUTED": True,
        "CLASSIFICATION": ev["CLASSIFICATION"],
        "DATA_IDENTITY": assembled["IDENTITY"],
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "EVENT_FAMILY": "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS",
        "STRUCTURAL": {
            key: assembled["CENSUS"].get(key)
            for key in EXPECTED_D11_STRUCTURE
        },
        "MIN_CONTROLS_AMONG_EVENTS": assembled["CENSUS"].get("MIN_CONTROLS_AMONG_EVENTS"),
        "SEEDS": {
            "PERMUTATION": C.D11_SEED,
            "N_RANDOMIZATIONS": C.D11_N_RANDOMIZATIONS,
        },
        "MEAN_EVENT_RV_6H": assembled["MEAN_EVENT_RV_6H"],
        "MEAN_CONTROL_RV_6H": assembled["MEAN_CONTROL_RV_6H"],
        "RELATIVE": assembled["RELATIVE"],
        "MC_P": ev["MC_P"],
        "STATISTICAL_GATE": ev["STATISTICAL_GATE"],
        "PRACTICAL_GATE": ev["PRACTICAL_GATE"],
        "TEMPORAL_GATE": ev["TEMPORAL_GATE"],
        "YEARLY_RELATIVE": ev["YEARLY_RELATIVE"],
        "DIRECTIONAL_SIGN_USED": False,
        "LIMITATIONS": [
            "N=39 scheduled FOMC events only.",
            "Unsigned volatility response, not a directional or trading claim.",
            "Does not validate D8 recovery or generic macro-event alpha.",
        ],
    }
    payload["RESULT_PAYLOAD_SHA256"] = payload_sha256(payload)
    return payload


def render_card_md(result: Mapping[str, Any]) -> str:
    disc = result["DISCOVERY_ID"]
    lines = [
        f"# Discovery Sprint 03 {disc} RESULT",
        "",
        f"**Classification:** `{result['CLASSIFICATION']}`",
        f"**Execution root:** `{result['EXECUTION_ROOT']}`",
        f"**RESULT_PAYLOAD_SHA256:** `{result['RESULT_PAYLOAD_SHA256']}`",
        "",
        "Adaptive discovery on historically exposed data. Not proven alpha, "
        "not a trading edge, not a confirmed mechanism, not causal proof.",
        "",
        "```",
        f"CLASSIFICATION = {result['CLASSIFICATION']}",
        f"STATISTICAL_GATE = {result['STATISTICAL_GATE']}",
        f"PRACTICAL_GATE = {result['PRACTICAL_GATE']}",
        f"TEMPORAL_GATE = {result['TEMPORAL_GATE']}",
        f"PROTECTED_2025_OPENED = {result['PROTECTED_2025_OPENED']}",
        f"PROTECTED_2026_OPENED = {result['PROTECTED_2026_OPENED']}",
        "```",
        "",
    ]
    if disc == "D9":
        lines.extend(
            [
                f"MEDIAN_EVENT_SHARE = {result['MEDIAN_EVENT_SHARE']}",
                f"MEDIAN_MATCHED_CONTROL_SHARE = {result['MEDIAN_MATCHED_CONTROL_SHARE']}",
                f"DELTA_VS_HALF = {result['DELTA_VS_HALF']}",
                f"DELTA_VS_CONTROL = {result['DELTA_VS_CONTROL']}",
                f"P_HALF = {result['P_HALF']}",
                f"P_CONTROL = {result['P_CONTROL']}",
                "",
                "A positive may establish only CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION.",
                "It does not establish price-discovery leadership, causal leadership, "
                "which venue moved first, or trading alpha.",
                "",
            ]
        )
    elif disc == "D10":
        lines.extend(
            [
                f"MEAN_EVENT = {result['MEAN_EVENT']}",
                f"MEAN_MATCHED_CONTROL = {result['MEAN_MATCHED_CONTROL']}",
                f"DELTA = {result['DELTA']}",
                f"DELTA_BPS = {result['DELTA_BPS']}",
                f"MC_P = {result['MC_P']}",
                "",
                "Does not validate MARKET-05. Does not imply generic ETH lead-lag or trading alpha.",
                "",
                result["TEMPORAL_DEPENDENCE_LIMITATION"],
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"MEAN_EVENT_RV_6H = {result['MEAN_EVENT_RV_6H']}",
                f"MEAN_CONTROL_RV_6H = {result['MEAN_CONTROL_RV_6H']}",
                f"RELATIVE = {result['RELATIVE']}",
                f"MC_P = {result['MC_P']}",
                "",
                "Unsigned scheduled-FOMC BTC vol response only. Not a FOMC trading strategy, "
                "not directional prediction, not D8 recovery validation.",
                "",
            ]
        )
    return "\n".join(lines)


def information_gain(d9: Mapping[str, Any], d10: Mapping[str, Any], d11: Mapping[str, Any]) -> dict[str, Any]:
    def note(card: str, classification: str) -> dict[str, str]:
        if classification == "PROMISING_PROTOTYPE":
            supports = {
                "D9": "A discovery-stage conditional venue-resolution SHARE location shift under the frozen D9 design.",
                "D10": "A discovery-stage next-hour ETH residual persistence difference vs matched small-residual controls.",
                "D11": "A discovery-stage unsigned BTC 6h RV elevation after scheduled FOMC announcements.",
            }[card]
            deprior = {
                "D9": "Does not reopen MARKET-06 24h MAE prediction. Does not authorize leadership/causal claims.",
                "D10": "Does not reopen MARKET-05. Does not authorize generic ETH lead-lag neighbors.",
                "D11": "Does not rescue D8. Does not authorize CPI/NFP/ECB substitution.",
            }[card]
            open_ = {
                "D9": "Independent confirmation on a fresh surface. Not a trading rule.",
                "D10": "Independent confirmation; residual calendar clustering remains a discovery-stage limitation.",
                "D11": "Independent confirmation; N=39 is the frozen scheduled-FOMC family size.",
            }[card]
        elif classification == "NO_USEFUL_STRUCTURE":
            supports = f"{card} frozen discovery formulation did not pass the discovery gate."
            deprior = {
                "D9": "This SHARE-on-closing-extremes formulation. Do not rescue with clipping or leadership relabel.",
                "D10": "This residual-persistence formulation. Do not add post-hoc refractory or block bootstrap.",
                "D11": "This scheduled-FOMC unsigned RV formulation. Do not expand the event family.",
            }[card]
            open_ = "Orthogonal families remain as already recorded. Do not convert this null into neighbor rescue."
        elif classification == "INCONCLUSIVE_DISCOVERY":
            supports = f"{card} support/integrity did not permit scientific resolution."
            deprior = "Nothing scientifically. Not negative evidence."
            open_ = f"{card} remains unresolved under the frozen design."
        elif classification == "INVALID_DISCOVERY":
            supports = f"{card} identity/integrity failed."
            deprior = "Nothing scientifically. Not negative evidence."
            open_ = f"{card} cannot be interpreted until identity is restored by a later unit."
        else:
            supports = f"{card} classified {classification}."
            deprior = "Do not reinterpret."
            open_ = "See frozen predicate."
        return {
            "CLASSIFICATION": classification,
            "WHAT_THIS_RESULT_SUPPORTS": supports,
            "WHAT_THIS_RESULT_DEPRIORITIZES": deprior,
            "WHAT_REMAINS_OPEN": open_,
        }

    cards = {
        "D9": note("D9", d9["CLASSIFICATION"]),
        "D10": note("D10", d10["CLASSIFICATION"]),
        "D11": note("D11", d11["CLASSIFICATION"]),
    }
    executed = sum(
        1
        for row in cards.values()
        if row["CLASSIFICATION"] in {"PROMISING_PROTOTYPE", "NO_USEFUL_STRUCTURE"}
    )
    promising = sum(1 for row in cards.values() if row["CLASSIFICATION"] == "PROMISING_PROTOTYPE")
    return {
        "D9": cards["D9"],
        "D10": cards["D10"],
        "D11": cards["D11"],
        "SPRINT03_TERMINAL_SCIENTIFIC_CARDS": executed,
        "SPRINT03_PROMISING_PROTOTYPES": promising,
        "INTERNAL_DISCOVERY_CARDS_EXECUTED_BEFORE": 5,
        "INTERNAL_PROMISING_PROTOTYPES_BEFORE": 2,
        "INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER": 5 + executed,
        "INTERNAL_PROMISING_PROTOTYPES_AFTER": 2 + promising,
        "DO_NOT_ALTER_HYPOTHESIS_GENERATION_PHILOSOPHY": True,
        "DO_NOT_CREATE_NEIGHBOR_RESCUE_HYPOTHESES": True,
        "DO_NOT_SELECT_SPRINT04_IN_THIS_UNIT": True,
    }


def write_result(repo: Path, rel_json: str, rel_md: str, payload: Mapping[str, Any]) -> None:
    json_path = repo / rel_json
    md_path = repo / rel_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in payload.items() if k != "_MARKDOWN"}
    json_path.write_text(canonical_json(body), encoding="utf-8")
    if "DISCOVERY_ID" in body:
        md_path.write_text(render_card_md(body), encoding="utf-8")
    else:
        md_path.write_text(str(payload.get("_MARKDOWN") or ""), encoding="utf-8")


def execute(*, repo: Path, authorize: bool, write: bool) -> dict[str, Any]:
    if not authorize:
        raise C.RealScientificOutcomeForbidden("SPRINT03_EXECUTION_NOT_AUTHORIZED")
    if C.EXECUTION_AUTHORIZED:
        raise ExecutionAbortedPreResult("GLOBAL_EXECUTION_AUTHORIZED_MUST_REMAIN_FALSE")
    verify_execution_root(repo)
    hashes = verify_implementation_identity(repo)
    d9_a = assemble_d9(repo)
    d10_a = assemble_d10(repo)
    d11_a = assemble_d11(repo)
    d9_r = build_d9_result(d9_a, hashes)
    d10_r = build_d10_result(d10_a, hashes)
    d11_r = build_d11_result(d11_a, hashes)
    gain = information_gain(d9_r, d10_r, d11_r)
    batch = {
        **_common_result_fields(hashes=hashes),
        "D9_EXECUTED": True,
        "D10_EXECUTED": True,
        "D11_EXECUTED": True,
        "D9_CLASSIFICATION": d9_r["CLASSIFICATION"],
        "D10_CLASSIFICATION": d10_r["CLASSIFICATION"],
        "D11_CLASSIFICATION": d11_r["CLASSIFICATION"],
        "D9_RESULT_PAYLOAD_SHA256": d9_r["RESULT_PAYLOAD_SHA256"],
        "D10_RESULT_PAYLOAD_SHA256": d10_r["RESULT_PAYLOAD_SHA256"],
        "D11_RESULT_PAYLOAD_SHA256": d11_r["RESULT_PAYLOAD_SHA256"],
        "SPRINT03_INFORMATION_GAIN": gain,
        "INTERNAL_DISCOVERY_CARDS_EXECUTED": gain["INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER"],
        "INTERNAL_PROMISING_PROTOTYPES": gain["INTERNAL_PROMISING_PROTOTYPES_AFTER"],
        "NEXT_UNIT": "DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION",
        "SPRINT04_HYPOTHESES_SELECTED": False,
    }
    batch["RESULT_PAYLOAD_SHA256"] = payload_sha256(batch)
    batch["_MARKDOWN"] = "\n".join(
        [
            "# Discovery Sprint 03 canonical RESULT",
            "",
            f"EXECUTION_ROOT = `{EXECUTION_ROOT}`",
            f"D9_CLASSIFICATION = `{d9_r['CLASSIFICATION']}`",
            f"D10_CLASSIFICATION = `{d10_r['CLASSIFICATION']}`",
            f"D11_CLASSIFICATION = `{d11_r['CLASSIFICATION']}`",
            f"INTERNAL_DISCOVERY_CARDS_EXECUTED = {gain['INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER']}",
            f"INTERNAL_PROMISING_PROTOTYPES = {gain['INTERNAL_PROMISING_PROTOTYPES_AFTER']}",
            f"BATCH_RESULT_PAYLOAD_SHA256 = `{batch['RESULT_PAYLOAD_SHA256']}`",
            "",
            "Adaptive discovery only. Not proven alpha. Sprint 04 not selected here.",
            "",
        ]
    )
    if write:
        write_result(repo, *RESULT_REL["D9"], d9_r)
        write_result(repo, *RESULT_REL["D10"], d10_r)
        write_result(repo, *RESULT_REL["D11"], d11_r)
        md = batch.pop("_MARKDOWN")
        write_result(repo, *RESULT_REL["BATCH"], {**batch, "_MARKDOWN": md})
        batch["_MARKDOWN"] = md
    return {"D9": d9_r, "D10": d10_r, "D11": d11_r, "BATCH": batch, "GAIN": gain}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument(AUTHORIZE_FLAG, dest="authorize", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--identity-only", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo or C.repo_root()
    try:
        if args.identity_only:
            verify_execution_root(repo)
            hashes = verify_implementation_identity(repo)
            print(json.dumps({"IMPLEMENTATION_IDENTITY_VERIFIED": True, "HASHES": hashes}, indent=2))
            return 0
        out = execute(repo=repo, authorize=args.authorize, write=args.write)
        summary = {
            "D9_CLASSIFICATION": out["D9"]["CLASSIFICATION"],
            "D10_CLASSIFICATION": out["D10"]["CLASSIFICATION"],
            "D11_CLASSIFICATION": out["D11"]["CLASSIFICATION"],
            "D9_RESULT_PAYLOAD_SHA256": out["D9"]["RESULT_PAYLOAD_SHA256"],
            "D10_RESULT_PAYLOAD_SHA256": out["D10"]["RESULT_PAYLOAD_SHA256"],
            "D11_RESULT_PAYLOAD_SHA256": out["D11"]["RESULT_PAYLOAD_SHA256"],
            "BATCH_RESULT_PAYLOAD_SHA256": out["BATCH"]["RESULT_PAYLOAD_SHA256"],
        }
        print(canonical_json(summary))
        return 0
    except ExecutionAbortedPreResult as exc:
        print("EXECUTION_ABORTED_PRE_RESULT")
        print(f"REASON = {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
