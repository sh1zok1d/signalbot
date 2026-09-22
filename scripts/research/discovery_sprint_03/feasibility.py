"""Outcome-blind structural feasibility CLI for Discovery Sprint 03.

Runs D9/D10/D11 independently. One blocked card does not stop the others.
Never computes SHARE summaries, residual-persistence effects, or RV deltas.
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

from scripts.research.discovery_sprint_03 import common as C
from scripts.research.discovery_sprint_03 import d9 as D9
from scripts.research.discovery_sprint_03 import d10 as D10
from scripts.research.discovery_sprint_03 import d11 as D11


FREEZE_JSON_REL = "docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.json"
FREEZE_MD_REL = "docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.md"


def _classification_contracts() -> dict[str, Any]:
    return {
        "D9": {
            "PRIMARY_STATISTIC": C.D9_PRIMARY_LOCATION_STATISTIC,
            "PRIMARY_BASELINE_NULL": "0.5 and matched closing-control median",
            "PRACTICAL_GATE": (
                f"|median_event-0.5|>= {C.D9_PRACTICAL_ABS_VS_HALF} AND "
                f"|median_event-median_control|>= {C.D9_PRACTICAL_ABS_VS_CONTROL}"
            ),
            "TEMPORAL_GATE": (
                f">={C.D9_TEMPORAL_YEARS_REQUIRED} years with "
                f">={C.D9_TEMPORAL_MIN_CLOSING_PER_YEAR} closing events, same sign vs 0.5, "
                f"|median-0.5|>= {C.D9_TEMPORAL_YEAR_ABS_VS_HALF}"
            ),
            "UNCERTAINTY_RULE": (
                f"P_HALF: two-sided sign-flip MC around 0.5, N={C.D9_N_RANDOMIZATIONS}, "
                f"seed={C.D9_SEED}. P_CONTROL: two-sided stratified label permutation of "
                f"median_event-median_matched_control inside YEAR x SIGN_D x RV_BUCKET, "
                f"N={C.D9_N_RANDOMIZATIONS}, seed={C.D9_CONTROL_PERM_SEED}. "
                f"STATISTICAL_GATE_D9 = P_HALF < {C.D9_MC_ALPHA} AND P_CONTROL < {C.D9_MC_ALPHA}."
            ),
            "MINIMUM_SUPPORT": {
                "MIN_NONOVERLAPPING_EVENTS": C.D9_MIN_NONOVERLAPPING_EVENTS,
                "MIN_CLOSING_EVENTS": C.D9_MIN_CLOSING_EVENTS,
                "MIN_YEARS_WITH_CLOSING_EVENTS": C.D9_MIN_YEARS_WITH_CLOSING_EVENTS,
                "MIN_MATCHED_CLOSING_CONTROLS": C.D9_MIN_MATCHED_CLOSING_CONTROLS,
                "MIN_YEARS_WITH_EVENT_AND_CONTROL": C.D9_MIN_YEARS_WITH_EVENT_AND_CONTROL,
            },
            "CLASSIFICATION_PREDICATE": (
                "INVALID_DISCOVERY if IDENTITY_OK is false; "
                "INCONCLUSIVE_DISCOVERY if SUPPORT_PASS is false; "
                "PROMISING_PROTOTYPE iff SUPPORT and STATISTICAL and PRACTICAL and TEMPORAL; "
                "else NO_USEFUL_STRUCTURE"
            ),
            "RANDOM_SEED": C.D9_SEED,
            "CONTROL_SAMPLE_SEED": C.D9_CONTROL_SAMPLE_SEED,
            "CONTROL_PERM_SEED": C.D9_CONTROL_PERM_SEED,
            "MATCH_RULE": (
                "IS_EXTREME_BAR from trailing P90 independent of refractory; "
                "PRIMARY EVENT = keep-first 12-bar among extremes; "
                "controls require IS_EXTREME_BAR==false; 1:1 YEAR x SIGN_D x "
                "RV_BUCKET closing non-extreme sample without replacement"
            ),
            "STATISTICAL_GATE_RULE": "P_HALF < 0.05 AND P_CONTROL < 0.05",
            "SCIENTIFIC_CLAIM_MAY_ESTABLISH": "CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION",
            "SCIENTIFIC_CLAIM_MUST_NOT_ESTABLISH": [
                "PRICE_DISCOVERY_LEADERSHIP",
                "CAUSAL_LEADERSHIP",
                "WHICH_VENUE_MOVED_FIRST",
            ],
            "ROBUST_LOCATION_REASON": (
                "PERP_RESOLUTION_SHARE is a ratio whose denominator TOTAL_CLOSURE can be "
                "arbitrarily close to zero while remaining positive. MEAN SHARE is not a "
                "location functional of the typical closing event; MEDIAN is. No "
                "outcome-derived TOTAL_CLOSURE cutoff is introduced."
            ),
        },
        "D10": {
            "PRIMARY_STATISTIC": "MEAN_EVENT_SIGNED_PERSISTENCE_MINUS_MEAN_CONTROL",
            "PRIMARY_BASELINE_NULL": "delta=0 vs YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET small-|e| controls",
            "PRACTICAL_GATE": f"delta >= {C.D10_PRACTICAL_DELTA}",
            "TEMPORAL_GATE": (
                f">={C.D10_TEMPORAL_YEARS_REQUIRED} years with positive yearly delta "
                "when pooled delta is positive"
            ),
            "UNCERTAINTY_RULE": (
                f"one-sided STRATIFIED event/control label permutation inside "
                f"YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET, N={C.D10_N_RANDOMIZATIONS}, "
                f"seed={C.D10_SEED}, alpha={C.D10_MC_ALPHA}. 1:1 matched sample. "
                "Does not globally shuffle across strata."
            ),
            "MINIMUM_SUPPORT": {
                "MIN_EVENTS": C.D10_MIN_EVENTS,
                "MIN_YEARS_WITH_EVENTS": C.D10_MIN_YEARS_WITH_EVENTS,
                "MIN_MATCHED_CONTROLS": C.D10_MIN_MATCHED_CONTROLS,
                "MIN_YEARS_WITH_EVENT_AND_CONTROL": C.D10_MIN_YEARS_WITH_EVENT_AND_CONTROL,
            },
            "CLASSIFICATION_PREDICATE": (
                "INVALID_DISCOVERY if IDENTITY_OK is false; "
                "INCONCLUSIVE_DISCOVERY if SUPPORT_PASS is false; "
                "PROMISING_PROTOTYPE iff SUPPORT and STATISTICAL and PRACTICAL and TEMPORAL; "
                "else NO_USEFUL_STRUCTURE"
            ),
            "RANDOM_SEED": C.D10_SEED,
            "CONTROL_SAMPLE_SEED": C.D10_CONTROL_SAMPLE_SEED,
            "PERMUTATION_RULE": (
                "STRATIFIED_LABEL_PERMUTATION inside YEAR x SIGN_E_T x "
                "ABS_BTC_RETURN_BUCKET; preserve event/control counts per stratum"
            ),
            "MATCH_RULE": (
                "1:1 YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET without replacement "
                "from |e_t|<=trailing P50 non-events"
            ),
            "TEMPORAL_DEPENDENCE_LIMITATION": C.D10_TEMPORAL_DEPENDENCE_LIMITATION,
            "REGRESSION_SPECIFICATION": C.D10_REGRESSION_SPECIFICATION,
            "REGRESSION_SPEC_REASON": (
                "OPTION A no-intercept OLS. The frozen residual is e=r_eth-beta*r_btc with "
                "no intercept term. Combining a centered slope with an intercept-dropped "
                "residual would be incoherent. Coefficients fitted on the previous 720 "
                "hours strictly before t are reused unchanged at t+1."
            ),
        },
        "D11": {
            "PRIMARY_STATISTIC": "RELATIVE_MEAN_POST_EVENT_RV_6H_VS_MATCHED_CONTROL",
            "PRIMARY_BASELINE_NULL": "relative=0 vs YEAR x WEEKDAY x UTC_HOUR non-FOMC windows",
            "PRACTICAL_GATE": f"mean_event_rv/mean_control_rv - 1 >= {C.D11_PRACTICAL_RELATIVE}",
            "TEMPORAL_GATE": (
                f">={C.D11_TEMPORAL_YEARS_REQUIRED} years with positive yearly relative "
                "when pooled relative is positive"
            ),
            "UNCERTAINTY_RULE": (
                f"one-sided event/control label permutation MC, N={C.D11_N_RANDOMIZATIONS}, "
                f"seed={C.D11_SEED}, alpha={C.D11_MC_ALPHA}"
            ),
            "MINIMUM_SUPPORT": {
                "MIN_EVENTS": C.D11_MIN_EVENTS,
                "MIN_YEARS": C.D11_MIN_YEARS,
                "MIN_CONTROLS_PER_EVENT": C.D11_MIN_CONTROLS_PER_EVENT,
                "MIN_TOTAL_CONTROLS": C.D11_MIN_TOTAL_CONTROLS,
            },
            "CLASSIFICATION_PREDICATE": (
                "INVALID_DISCOVERY if IDENTITY_OK is false; "
                "INCONCLUSIVE_DISCOVERY if SUPPORT_PASS is false; "
                "PROMISING_PROTOTYPE iff SUPPORT and STATISTICAL and PRACTICAL and TEMPORAL; "
                "else NO_USEFUL_STRUCTURE"
            ),
            "RANDOM_SEED": C.D11_SEED,
            "EVENT_FAMILY": "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS",
        },
    }


def _blocked(card: str, status: str, detail: str) -> dict[str, Any]:
    return {
        "STATUS": status,
        "DETAIL": detail,
        "SUPPORT_PASS": False,
        "IDENTITY_OK": False,
        "SHARE_VALUES_EMITTED": False,
        "PERSISTENCE_VALUES_EMITTED": False,
        "RV_VALUES_EMITTED": False,
        "CARD": card,
    }


def run_d9(*, repo: Path) -> dict[str, Any]:
    perp, spot, identity = D9.load_d9_inputs(repo=repo)
    census = D9.d9_feasibility_census(perp, spot)
    census["IDENTITY_OK"] = bool(identity.get("IDENTITY_OK"))
    census["DATA_IDENTITY_VERIFIED"] = bool(identity.get("IDENTITY_OK"))
    census["SNAPSHOT_ID"] = identity.get("SNAPSHOT_ID")
    census["CARD"] = "D9"
    return census


def run_d10(*, repo: Path) -> dict[str, Any]:
    try:
        btc, eth, identity = D10.load_d10_inputs(repo=repo)
    except C.MissingLocalData as exc:
        return _blocked("D10", "D10_DATA_MATERIAL_BLOCKED", str(exc))
    census = D10.d10_feasibility_census(btc, eth)
    census["IDENTITY_OK"] = bool(identity.get("IDENTITY_OK"))
    census["DATA_IDENTITY_VERIFIED"] = bool(identity.get("IDENTITY_OK"))
    census["CORE_BTC_SNAPSHOT_ID"] = identity.get("CORE_BTC_SNAPSHOT_ID")
    census["CORE_ETH_SNAPSHOT_ID"] = identity.get("CORE_ETH_SNAPSHOT_ID")
    census["BTC_HOURS"] = identity.get("BTC_HOURS")
    census["ETH_HOURS"] = identity.get("ETH_HOURS")
    census["CARD"] = "D10"
    return census


def run_d11(*, repo: Path, pin: bool) -> dict[str, Any]:
    try:
        if pin or not (repo / C.D11_SOURCE_REL / "PIN.json").is_file():
            D11.pin_official_fomc_sources(repo=repo, retrieve=True)
        events, hour_returns, identity = D11.load_d11_inputs(repo=repo)
    except D11.D11SourceNotPinned as exc:
        return _blocked("D11", "D11_SOURCE_NOT_PINNED", str(exc))
    except C.MissingLocalData as exc:
        return _blocked("D11", "D11_DATA_MATERIAL_BLOCKED", str(exc))
    census = D11.d11_feasibility_census(events, hour_returns)
    census["IDENTITY_OK"] = bool(identity.get("IDENTITY_OK"))
    census["OFFICIAL_SOURCE_PINNED"] = bool(identity.get("OFFICIAL_SOURCE_PINNED"))
    census["YEAR_COVERAGE"] = identity.get("YEAR_COVERAGE")
    census["PINNED_EVENT_N"] = identity.get("EVENT_N_PINNED")
    census["CARD"] = "D11"
    return census


def assemble(d9: dict[str, Any], d10: dict[str, Any], d11: dict[str, Any]) -> dict[str, Any]:
    contracts = _classification_contracts()
    return {
        "UNIT": C.UNIT,
        "KIND": "OUTCOME_BLIND_BATCH_FEASIBILITY_AND_IMPLEMENTATION",
        "EXECUTION_AUTHORIZED": C.EXECUTION_AUTHORIZED,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "REAL_SCIENTIFIC_TARGET_VALUES_INSPECTED": False,
        "D9_EXECUTED": False,
        "D10_EXECUTED": False,
        "D11_EXECUTED": False,
        "D7_RERUN_PERFORMED": False,
        "D8_EXECUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "CLASSIFICATION_ASSIGNED": False,
        "D9": {**contracts["D9"], **d9},
        "D10": {**contracts["D10"], **d10},
        "D11": {**contracts["D11"], **d11},
        "D9_STATUS": d9.get("STATUS"),
        "D10_STATUS": d10.get("STATUS"),
        "D11_STATUS": d11.get("STATUS"),
        "D9_IMPLEMENTATION_READY": d9.get("STATUS") == "OUTCOME_BLIND_IMPLEMENTATION_READY",
        "D10_IMPLEMENTATION_READY": d10.get("STATUS") == "OUTCOME_BLIND_IMPLEMENTATION_READY",
        "D11_IMPLEMENTATION_READY": d11.get("STATUS") == "OUTCOME_BLIND_IMPLEMENTATION_READY",
        "CLASSIFICATION_IDENTITY_PRECEDENCE": (
            "INVALID_DISCOVERY if IDENTITY_OK is false; else INCONCLUSIVE_DISCOVERY "
            "if SUPPORT_PASS is false; else PROMISING_PROTOTYPE iff STATISTICAL and "
            "PRACTICAL and TEMPORAL; else NO_USEFUL_STRUCTURE"
        ),
        "REPAIR_UNIT": "TARGETED_RED_TEAM_REPAIR_F1_F5",
        "NEXT_UNIT": "DISCOVERY_SPRINT_03_IMPLEMENTATION_RED_TEAM_AND_EXECUTION_DECISION",
    }


def _md(payload: dict[str, Any]) -> str:
    d9, d10, d11 = payload["D9"], payload["D10"], payload["D11"]
    return "\n".join(
        [
            "# Discovery Sprint 03 — Implementation Freeze",
            "",
            f"**Unit:** `{payload['UNIT']}`",
            "**Kind:** outcome-blind feasibility and implementation. No scientific outcomes.",
            "",
            "```",
            f"EXECUTION_AUTHORIZED = {payload['EXECUTION_AUTHORIZED']}",
            f"SCIENTIFIC_OUTCOMES_COMPUTED = {payload['SCIENTIFIC_OUTCOMES_COMPUTED']}",
            f"D9_STATUS = {payload['D9_STATUS']}",
            f"D10_STATUS = {payload['D10_STATUS']}",
            f"D11_STATUS = {payload['D11_STATUS']}",
            f"D9_PRIMARY_LOCATION_STATISTIC = {d9.get('PRIMARY_LOCATION_STATISTIC') or d9.get('PRIMARY_STATISTIC')}",
            f"D10_REGRESSION_SPECIFICATION = {d10.get('REGRESSION_SPECIFICATION')}",
            f"D11_OFFICIAL_SOURCE_PINNED = {d11.get('OFFICIAL_SOURCE_PINNED')}",
            f"PROTECTED_2025_OPENED = {payload['PROTECTED_2025_OPENED']}",
            f"PROTECTED_2026_OPENED = {payload['PROTECTED_2026_OPENED']}",
            f"MARKET_07_CREATED = {payload['MARKET_07_CREATED']}",
            f"NEXT_UNIT = {payload['NEXT_UNIT']}",
            "```",
            "",
            "Classification contracts are frozen. No card is classified in this unit.",
            "Real scientific target values were not inspected.",
            "",
            "Classification precedence (all cards): IDENTITY_OK false → "
            "INVALID_DISCOVERY, then SUPPORT_PASS false → INCONCLUSIVE_DISCOVERY, "
            "then PROMISING_PROTOTYPE iff STATISTICAL and PRACTICAL and TEMPORAL, "
            "else NO_USEFUL_STRUCTURE.",
            "",
            "D9 repair freeze:",
            "",
            "- Extreme bars (`IS_EXTREME_BAR`, trailing P90 on 8640 valid |D|) are "
            "classified independently of the 12-bar refractory rule.",
            "- Primary events are keep-first retained extremes. Refractory-dropped "
            "extremes are neither primary events nor controls.",
            "- Controls require `IS_EXTREME_BAR == false`, genuine closure, and "
            "1:1 YEAR × SIGN_D × RV_BUCKET matching of closing retained events, "
            "without replacement, seed "
            f"`{C.D9_CONTROL_SAMPLE_SEED}`.",
            "- Report `RAW_EXTREME_BAR_N`, `RETAINED_EVENT_N`, "
            "`REFRACTORY_DROPPED_EXTREME_N`, `RAW_ELIGIBLE_CLOSING_CONTROL_N`, "
            "`MATCHED_CLOSING_CONTROL_N`. No SHARE summaries.",
            "- `P_HALF`: sign-flip vs 0.5, seed "
            f"`{C.D9_SEED}`. `P_CONTROL`: two-sided stratified label permutation "
            "of median_event − median_matched_control inside YEAR × SIGN_D × "
            f"RV_BUCKET, seed `{C.D9_CONTROL_PERM_SEED}`.",
            "- `STATISTICAL_GATE_D9 = P_HALF < 0.05 AND P_CONTROL < 0.05`.",
            f"- Structural: events {d9.get('EVENT_N')}; closing {d9.get('CLOSING_EVENT_N')}; "
            f"raw extreme {d9.get('RAW_EXTREME_BAR_N')}; refractory-dropped "
            f"{d9.get('REFRACTORY_DROPPED_EXTREME_N')}; raw eligible closing controls "
            f"{d9.get('RAW_ELIGIBLE_CLOSING_CONTROL_N')}; matched closing controls "
            f"{d9.get('MATCHED_CLOSING_CONTROL_N')}; cells balanced "
            f"{d9.get('ALL_MATCHED_CELLS_BALANCED')}.",
            "",
            "D10 repair freeze:",
            "",
            "- 1:1 YEAR × SIGN_E_T × ABS_BTC_RETURN_BUCKET matching from "
            f"|e_t| ≤ trailing P50 non-events, seed `{C.D10_CONTROL_SAMPLE_SEED}`.",
            "- Report `RAW_ELIGIBLE_CONTROL_N` vs `MATCHED_CONTROL_N`.",
            "- Permutation is stratified inside those frozen cells; event/control "
            f"counts preserved per stratum; seed `{C.D10_SEED}`. No global shuffle.",
            "- Residual discovery-stage limitation: events may cluster in calendar "
            "time. This repair does not add a post-hoc refractory or block bootstrap.",
            f"- Structural: events {d10.get('EVENT_N')}; raw eligible controls "
            f"{d10.get('RAW_ELIGIBLE_CONTROL_N')}; matched controls "
            f"{d10.get('MATCHED_CONTROL_N')}; cells balanced "
            f"{d10.get('ALL_MATCHED_CELLS_BALANCED')}.",
            "",
            "D11: official scheduled FOMC only. Control windows exclude any of the "
            "6 constituent hours that overlap FOMC event/aftermath. No scientific "
            "redesign.",
            f"- Structural: events {d11.get('EVENT_N')}; controls {d11.get('CONTROL_N')}; "
            f"min controls among events {d11.get('MIN_CONTROLS_AMONG_EVENTS')}.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--pin-d11", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo or C.repo_root()
    results: dict[str, dict[str, Any]] = {}
    for name, fn in (
        ("D9", lambda: run_d9(repo=repo)),
        ("D10", lambda: run_d10(repo=repo)),
        ("D11", lambda: run_d11(repo=repo, pin=args.pin_d11)),
    ):
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001 — per-card isolation
            results[name] = _blocked(name, f"{name}_BLOCKED", f"{type(exc).__name__}:{exc}")
            results[name]["TRACE"] = traceback.format_exc(limit=8)
    payload = assemble(results["D9"], results["D10"], results["D11"])
    text = json.dumps(C.jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.write:
        json_path = repo / FREEZE_JSON_REL
        md_path = repo / FREEZE_MD_REL
        json_path.write_text(text, encoding="utf-8")
        md_path.write_text(_md(payload), encoding="utf-8")
        print(json_path)
        print(md_path)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
