"""Outcome-blind structural feasibility CLI for Discovery Sprint 04.

D12: complete-day / window constructibility only. Never A, D(L), or profiles.
D13: enumeration, checksums, N, exclusions, universe identity, terminal-mark
presence counts. Never formation/holding returns or IC.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d12 as D12
from scripts.research.discovery_sprint_04 import d13 as D13
from scripts.research.discovery_sprint_04 import d13_panel as P

FREEZE_JSON_REL = "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.json"
FREEZE_MD_REL = "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.md"
UNIVERSE_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/UNIVERSE_IDENTITY.json"
)
FEE_PIN_REL = C.D13_FEE_AUTHORITY_REL


def _blocked(card: str, status: str, detail: str) -> dict[str, Any]:
    return {
        "CARD": card,
        "STATUS": status,
        "DETAIL": detail,
        "IDENTITY_OK": False,
        "SUPPORT_PASS": False,
        "SCIENTIFIC_OUTCOME_COMPUTED": False,
    }


def run_d12(*, repo: Path) -> dict[str, Any]:
    try:
        census = D12.feasibility_census(repo=repo)
    except C.MissingLocalData as exc:
        return _blocked("D12", "D12_DATA_MATERIAL_BLOCKED", str(exc))
    census["CARD"] = "D12"
    census["STATUS"] = (
        "OUTCOME_BLIND_IMPLEMENTATION_READY"
        if census.get("IDENTITY_OK") and census.get("SUPPORT_PASS")
        else "OUTCOME_BLIND_IMPLEMENTATION_BLOCKED"
    )
    census["SCIENTIFIC_OUTCOME_COMPUTED"] = False
    census["D12_EXECUTED"] = False
    return census


def run_d13(*, repo: Path) -> dict[str, Any]:
    docs = repo / C.D13_DOCS_REL
    prefixes_path = docs / "symbol_prefixes.json"
    index_path = docs / "object_key_index.json"
    ledger_path = docs / "object_ledger.json"
    pin_path = repo / FEE_PIN_REL
    if not prefixes_path.is_file() or not index_path.is_file():
        return _blocked("D13", "D13_ENUMERATION_NOT_PINNED", "missing listing authority")
    prefixes = json.loads(prefixes_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not ledger_path.is_file():
        return _blocked("D13", "D13_LEDGER_MISSING", "object ledger not written")
    if not pin_path.is_file():
        return _blocked("D13", "DEFERRED_PRACTICAL_FLOOR_NOT_PINNED", "fee PIN.json missing")
    try:
        P.verify_index_ledger_keyset(repo=repo)
        byte_id = P.verify_local_bytes_against_ledger(repo=repo)
    except C.MissingLocalData as exc:
        return _blocked("D13", "D13_RAW_BYTES_NOT_RESTORABLE", str(exc))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    enumeration_digest = prefixes["listing_digest"]
    ledger_digest = P.file_ledger_digest(ledger)
    snap = P.snapshot_id(enumeration_digest=enumeration_digest, ledger_digest=ledger_digest)
    panel = P.load_presence_panel(repo=repo)
    census = P.feasibility_universe_census(panel, prefixes["symbols"])
    census.update(
        {
            "CARD": "D13",
            "IDENTITY_OK": bool(byte_id["IDENTITY_OK"]),
            "DATASET_ID": C.D13_DATASET_ID,
            "SNAPSHOT_ID": snap,
            "SYMBOL_ENUMERATION_AUTHORITY": enumeration_digest,
            "FILE_LEDGER_DIGEST": ledger_digest,
            "SYMBOLS_ENUMERATED": len(prefixes["symbols"]),
            "FILES_DOWNLOADED": ledger["n_files"],
            "LEDGER_ERRORS": ledger.get("n_errors", 0),
            "PINNED_TAKER_FEE": pin["PINNED_TAKER_FEE"],
            "FRICTION_FLOOR": pin["FRICTION_FLOOR"],
            "RANDOM_SEED": C.D13_RANDOM_SEED,
            "CANONICALIZATION_VERSION": C.D13_CANONICALIZATION_VERSION,
            "PROTECTED_2025_OPENED": False,
            "PROTECTED_2026_OPENED": False,
            "PROTECTED_KEYS_LISTED_NOT_FETCHED": index.get("protected_keys_listed_not_fetched", 0),
            "RETURNS_COMPUTED": False,
            "IC_COMPUTED": False,
            "SCIENTIFIC_OUTCOME_COMPUTED": False,
            "D13_EXECUTED": False,
            "TEMPORAL_DEPENDENCE_LIMITATION": C.D13_TEMPORAL_DEPENDENCE_LIMITATION,
        }
    )
    if census["NO_POST_T_CLOSE_SELECTED_N"] > 0:
        census["STATUS"] = "DEFERRED_TERMINAL_MARK_UNRESOLVED"
        census["SUPPORT_PASS"] = False
    elif census["N"] < C.D13_N_MIN:
        census["STATUS"] = "DEFERRED_INSUFFICIENT_PANEL_SUPPORT"
        census["SUPPORT_PASS"] = False
    elif not census["IDENTITY_OK"]:
        census["STATUS"] = "INVALID_DISCOVERY_IDENTITY"
    else:
        census["STATUS"] = "OUTCOME_BLIND_IMPLEMENTATION_READY"
    return census


def persist_universe_identity(census: Mapping[str, Any], *, repo: Path) -> None:
    dest = repo / UNIVERSE_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "DATASET_ID": census.get("DATASET_ID"),
        "SNAPSHOT_ID": census.get("SNAPSHOT_ID"),
        "N": census.get("N"),
        "FIRST_DECISION_MONDAY": census.get("FIRST_DECISION_MONDAY"),
        "LAST_DECISION_MONDAY": census.get("LAST_DECISION_MONDAY"),
        "UNIVERSE_IDENTITY_DIGEST": census.get("UNIVERSE_IDENTITY_DIGEST"),
        "NO_POST_T_CLOSE_SELECTED_N": census.get("NO_POST_T_CLOSE_SELECTED_N"),
        "ELIGIBLE_COUNT_BY_MONDAY": census.get("ELIGIBLE_COUNT_BY_MONDAY"),
        "SELECTED_BY_MONDAY": census.get("SELECTED_BY_MONDAY"),
        "EXCLUSION_LIST_DIGEST": (census.get("EXCLUSIONS") or {}).get("EXCLUSION_LIST_DIGEST"),
        "RETURNS_COMPUTED": False,
        "HOLDING_RETURNS_PERSISTED": False,
    }
    dest.write_text(C.canonical_json(payload), encoding="utf-8")


def assemble(d12: dict[str, Any], d13: dict[str, Any], *, repo: Path) -> dict[str, Any]:
    return {
        "UNIT": C.UNIT,
        "KIND": "OUTCOME_BLIND_BATCH_FEASIBILITY_AND_IMPLEMENTATION",
        "BASE_MAIN_SHA": "bc30eeb3b6a3e8fe880490d205101f4f63c9456e",
        "BASE_MAIN_TREE": "009ea5230ed11fd96aab1188cfbc389c26861ebf",
        "EXECUTION_AUTHORIZED": C.EXECUTION_AUTHORIZED,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "D12_EXECUTED": False,
        "D13_EXECUTED": False,
        "D7_RERUN_PERFORMED": False,
        "D8_EXECUTED": False,
        "D7_CONFIRMATION_EXECUTED": False,
        "D11_CONFIRMATION_EXECUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "D12": d12,
        "D13": d13,
        "D12_STATUS": d12.get("STATUS"),
        "D13_STATUS": d13.get("STATUS"),
        "D12_IMPLEMENTATION_READY": d12.get("STATUS") == "OUTCOME_BLIND_IMPLEMENTATION_READY",
        "D13_IMPLEMENTATION_READY": d13.get("STATUS") == "OUTCOME_BLIND_IMPLEMENTATION_READY",
        "IMPLEMENTATION_HASHES": C.implementation_hashes(repo),
        "NEXT_UNIT": "DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION_DECISION",
        "CLASSIFICATION_PREDICATE": (
            "INVALID_DISCOVERY if IDENTITY_OK is false; "
            "INCONCLUSIVE_DISCOVERY if SUPPORT_PASS is false; "
            "PROMISING_PROTOTYPE iff SUPPORT and STATISTICAL and PRACTICAL and TEMPORAL; "
            "else NO_USEFUL_STRUCTURE"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=C.repo_root())
    parser.add_argument("--d12-only", action="store_true")
    parser.add_argument("--d13-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo
    d12 = {"STATUS": "SKIPPED"} if args.d13_only else run_d12(repo=repo)
    d13 = {"STATUS": "SKIPPED"} if args.d12_only else run_d13(repo=repo)
    if d13.get("SELECTED_BY_MONDAY"):
        persist_universe_identity(d13, repo=repo)
    assembled = assemble(d12, d13, repo=repo)
    print(json.dumps({k: assembled[k] for k in assembled if k not in {"D12", "D13"}}, indent=2))
    slim_d13 = {k: v for k, v in d13.items() if k not in {"SELECTED_BY_MONDAY", "EXCLUSIONS"}}
    print("D12_STATUS", d12.get("STATUS"))
    print("D13_STATUS", d13.get("STATUS"))
    print("D13_N", d13.get("N"))
    print("D13_NO_POST_T_CLOSE_SELECTED_N", d13.get("NO_POST_T_CLOSE_SELECTED_N"))
    _ = slim_d13


if __name__ == "__main__":
    main()
