"""Outcome-blind end-to-end readiness for the GV0V03L40 shortlist.

C033 is read from its sealed V2 result and is not recompiled. C005, C024,
C031 and C037 stop at the data or point-in-time stage. No market target is
computed and no planning object is frozen.
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs/research/ladder-40-card-v03-r02-derived-critics-v2/run_ledger.json"
C033_RESULT = REPO / "docs/research/GV0V03L40_C033_V2_FEASIBILITY.json"
REPORT_JSON = REPO / "docs/research/GV0V03L40_SHORTLIST_FINAL_READINESS.json"
REPORT_MD = REPO / "docs/research/GV0V03L40_SHORTLIST_FINAL_READINESS.md"

SHORTLIST = ("C037", "C031", "C005", "C024", "C033")
OPEN_CARDS = ("C005", "C024", "C031", "C037")
FINAL_STATUSES = {
    "READY_FOR_PREREGISTRATION_DESIGN",
    "READY_FOR_TEST_IMPLEMENTATION_AFTER_OWNER_FREEZE",
    "DATA_BLOCKED",
    "PIT_BLOCKED",
    "INFERENCE_SUPPORT_INSUFFICIENT",
    "INFORMATIONALLY_WEAK",
    "DEFINITION_INCOMPLETE",
    "TERMINAL_NOT_PREREGISTRABLE",
}


def _cards() -> dict[str, dict]:
    ledger = json.loads(LEDGER.read_text())
    return {row["CANDIDATE_ID"]: row for row in ledger["PARSED_CARD"]}


def _variants(card: dict) -> list[dict]:
    params = card["SEARCH_SURFACE"]["PARAMETERS"]
    names = list(params)
    rows = []
    for values in product(*(params[name] for name in names)):
        rows.append({name: value for name, value in zip(names, values)})
    max_variants = card["SEARCH_SURFACE"]["MAX_VARIANTS"]
    if len(rows) > max_variants:
        raise RuntimeError(f"{card['CANDIDATE_ID']} search surface exceeds MAX_VARIANTS")
    return rows


def _blank_support() -> dict:
    return {
        "NOMINAL_N": None,
        "MECHANISM_ACTIVE_N": None,
        "MECHANISM_INACTIVE_N": None,
        "ALPHA_ATTAINABLE": None,
        "MIN_ATTAINABLE_P": None,
        "PRIMARY_LABEL_ORBIT_SIZE": None,
        "GV0R02_V2_STATUS": "NOT_COMPILED",
        "OWNER_DECISION_REQUIRED": None,
        "COMPILED": False,
        "MARKET_OUTCOMES_OPENED": False,
    }


def _matrix(card: dict, *, rejection: str, pit_status: str, zero_cost: bool, paid: bool) -> list[dict]:
    legal = {row["DATASET"]: row["LEGAL_RANGE"] for row in card["DATA_REQUIRED"]}
    rows = []
    for index, variant in enumerate(_variants(card)):
        rows.append({
            "INDEX": index,
            "VARIANT": variant,
            "DATA_REQUIREMENTS": [row["DATASET"] for row in card["DATA_REQUIRED"]],
            "LEGAL_RANGE": legal,
            "PIT_STATUS": pit_status,
            "ZERO_COST_AVAILABLE": zero_cost,
            "PAID_DATA_REQUIRED": paid,
            "NOMINAL_SUPPORT_COUNT": None,
            "MECHANISM_ACTIVE_N": None,
            "MECHANISM_INACTIVE_N": None,
            "INFERENCE_SUPPORT": "NOT_ASSESSED",
            "IMPLEMENTATION_COST": card["EXPECTED_IMPLEMENTATION_COST"],
            "ELIGIBLE": False,
            "REJECTION_REASON": rejection,
        })
    return rows


def _stopped(card: dict, *, final: str, data_status: str, pit_status: str, blockers: list[str],
             next_unit: str, rejection: str, zero_cost: bool, paid: bool, evidence: dict) -> dict:
    if final not in FINAL_STATUSES:
        raise RuntimeError("status outside the readiness set")
    return {
        "CARD": card["CANDIDATE_ID"],
        "CLASS": card["COMPLEXITY_CLASS"],
        "NAME": card["NAME"],
        "DATA_STATUS": data_status,
        "PIT_STATUS": pit_status,
        "PRIMARY_VARIANT": None,
        "BLOCKERS": blockers,
        "FINAL_READINESS": final,
        "NEXT_UNIT": next_unit,
        "STAGE_STOPPED": "B",
        "PAID_DATA_REQUIRED": paid,
        "PAID_DATA_SPEND_USD": 0,
        "VARIANT_MATRIX": _matrix(card, rejection=rejection, pit_status=pit_status, zero_cost=zero_cost, paid=paid),
        "EVIDENCE": evidence,
        **_blank_support(),
    }


def c024_record(card: dict) -> dict:
    evidence = {
        "SOURCE": "BINANCE_VISION_S3_LIST_AND_HEAD",
        "OBSERVED_ON": "2026-10-02",
        "PREFIX_2022_BTCUSDT_KEYS": 0,
        "PREFIX_2022_ETHUSDT_KEYS": 0,
        "EARLIEST_BTCUSDT_KEY": "data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip",
        "EARLIEST_ETHUSDT_KEY": "data/futures/um/daily/bookDepth/ETHUSDT/ETHUSDT-bookDepth-2023-01-01.zip",
        "HEAD_2022_01_01": 404,
        "HEAD_2023_01_01": 200,
        "MONTHLY_BOOKDEPTH_2023_01": 404,
        "SPOT_BOOKDEPTH_2023_01_01": 404,
        "REQUIRED_LEGAL_RANGE": "2022-01..2024-12",
        "WINDOW_CHANGED": False,
        "TARDIS_PURCHASED": False,
        "PAYLOADS_OPENED": False,
    }
    return _stopped(
        card,
        final="DATA_BLOCKED",
        data_status="DATA_BLOCKED",
        pit_status="NOT_ASSESSED_COVERAGE_ABSENT",
        blockers=["ORDER_BOOK_DEPTH_HISTORY"],
        next_unit="STOP. Do not shorten discovery to 2023-01 and do not buy Tardis L2.",
        rejection="Public USD-M bookDepth for BTCUSDT and ETHUSDT begins 2023-01-01. The frozen legal range starts 2022-01.",
        zero_cost=False,
        paid=True,
        evidence=evidence,
    )


def c005_record(card: dict) -> dict:
    evidence = {
        "SOURCE": "BINANCE_CMS_CATALOG_AND_VISION_HEAD",
        "OBSERVED_ON": "2026-10-02",
        "LISTING_CATALOG_ID": 48,
        "LISTING_CATALOG_TOTAL": 2276,
        "LISTING_OLDEST_PUBLISH_UTC": "2017-07-21T00:06:19Z",
        "LISTING_OLDEST_IS_USD_M_REGISTRY": False,
        "DELIST_CATALOG_ID": 161,
        "DELIST_CATALOG_TOTAL": 439,
        "DELIST_OLDEST_TITLE": "Notice of Removal of Trading Pairs - 2022-02-24",
        "DELIST_OLDEST_PUBLISH_UTC": "2022-02-17T03:47:56Z",
        "DELIST_COVERS_2019_09": False,
        "EXCHANGEINFO_ARCHIVE_URL": "https://data.binance.vision/data/futures/um/daily/exchangeInfo/",
        "EXCHANGEINFO_ARCHIVE_STATUS": 404,
        "LIVE_EXCHANGEINFO_USED": False,
        "LIVE_FAPI_EXCHANGEINFO_STATUS": 451,
        "ARTICLE_BODIES_TREATED_AS_IMMUTABLE": False,
    }
    return _stopped(
        card,
        final="PIT_BLOCKED",
        data_status="PUBLIC_CMS_NOT_A_PIT_REGISTRY",
        pit_status="PIT_BLOCKED",
        blockers=["PERP_LISTING_HISTORY_UNVERIFIED"],
        next_unit="STOP. A later unit needs a pinned PIT launch and delisting archive for 2019-09..2024-12, including delisted USD-M contracts, and historical onboardDate snapshots. Do not use a live exchangeInfo snapshot.",
        rejection="The public delist catalog does not reach 2019-09, and no historical onboardDate snapshot archive exists.",
        zero_cost=False,
        paid=False,
        evidence=evidence,
    )


def c031_record(card: dict) -> dict:
    evidence = {
        "SOURCE": "REPOSITORY_AND_PUBLIC_CATALOG_PROBE",
        "OBSERVED_ON": "2026-10-02",
        "AS_OF_BINANCE_DEPOSIT_LABEL_ARCHIVE_IN_REPO": False,
        "COINMETRICS_COMMUNITY_BTC_EXCHANGE_METRICS": [
            "FlowInExNtv",
            "FlowInExUSD",
            "FlowOutExNtv",
            "FlowOutExUSD",
        ],
        "COINMETRICS_COMMUNITY_HAS_ADDRESS_LABELS": False,
        "CONFIRMATION_POLICY_DATED_ARCHIVE_FOUND": False,
        "BINANCE_FAQ_CONFIRMATION_URL_BODY_BYTES": 0,
        "TODAYS_LABELS_USED": False,
        "TODAYS_CONFIRMATION_COUNT_USED": False,
        "COMMERCIAL_LABEL_FEED_PURCHASED": False,
    }
    return _stopped(
        card,
        final="PIT_BLOCKED",
        data_status="LABEL_AND_POLICY_ARCHIVE_ABSENT",
        pit_status="PIT_BLOCKED",
        blockers=["ADDRESS_LABEL_PROVENANCE_AND_EXCHANGE_POLICY_POINT_IN_TIME"],
        next_unit="STOP. A later unit needs as-of-dated Binance BTC deposit-address labels and a dated confirmation-count policy. Do not use today's labels or today's confirmation count.",
        rejection="Neither as-of address attribution nor a dated confirmation-count policy is established.",
        zero_cost=False,
        paid=True,
        evidence=evidence,
    )


def c037_record(card: dict) -> dict:
    evidence = {
        "SOURCE": "FROZEN_CARD_TEXT_AND_REPOSITORY_MANIFESTS",
        "OBSERVED_ON": "2026-10-02",
        "CIRCULATING_SUPPLY_PIT_SERIES_PINNED": False,
        "REVISED_SUPPLY_SERIES_ACCEPTED": False,
        "VOLUME_SHARE_PROXY_NAMED_IN_SEARCH_SURFACE": True,
        "VOLUME_SHARE_PROXY_ARITHMETIC_IN_FROZEN_CARD": False,
        "VOLUME_SHARE_PROXY_SELECTED": False,
        "SPRINT04_PANEL_STATUS_ON_CARD": "DATA_READY",
        "VENDOR_SUPPLY_VINTAGE_PURCHASED": False,
    }
    record = _stopped(
        card,
        final="PIT_BLOCKED",
        data_status="PIT_SUPPLY_HISTORY_ABSENT",
        pit_status="PIT_BLOCKED",
        blockers=["POINT_IN_TIME_SUPPLY_HISTORY"],
        next_unit="STOP. A later unit needs daily circulating supply as known on each date, including unlock revisions. The volume-share proxy was not selected because the frozen card does not define its arithmetic.",
        rejection="Point-in-time circulating supply is not pinned. The volume-share proxy has no frozen formula, so it is not exactly computable.",
        zero_cost=False,
        paid=True,
        evidence=evidence,
    )
    for row in record["VARIANT_MATRIX"]:
        if row["VARIANT"]["TURNOVER_SOURCE"] == "volume_share_proxy":
            row["PAID_DATA_REQUIRED"] = False
            row["REJECTION_REASON"] = (
                "The frozen card names volume_share_proxy and does not define the estimator. "
                "It was not selected."
            )
    return record


def c033_record() -> dict:
    result = json.loads(C033_RESULT.read_text())
    codes = [row["BLOCKER_CODE"] for row in result["BLOCKERS"]]
    return {
        "CARD": "C033",
        "CLASS": "COMPOSITE",
        "NAME": "Forced-flow joint state",
        "DATA_STATUS": "OUTCOME_BLIND_COUNT_RECORDED",
        "PIT_STATUS": "NOT_THE_BINDING_CONSTRAINT",
        "PRIMARY_VARIANT": {
            "SHOCK_SIGMA": 3,
            "TAKER_BAND": "p1_p99",
            "POST_WINDOW_H": 6,
        },
        "NOMINAL_N": result["MECHANISM_INACTIVE_N"],
        "MECHANISM_ACTIVE_N": result["MECHANISM_ACTIVE_N"],
        "MECHANISM_INACTIVE_N": result["MECHANISM_INACTIVE_N"],
        "ALPHA_ATTAINABLE": result["ALPHA_ATTAINABLE"],
        "MIN_ATTAINABLE_P": result["MIN_ATTAINABLE_P"],
        "PRIMARY_LABEL_ORBIT_SIZE": result["PRIMARY_LABEL_ORBIT_SIZE"],
        "GV0R02_V2_STATUS": result["FEASIBILITY_STATUS"],
        "BLOCKERS": codes,
        "OWNER_DECISION_REQUIRED": None,
        "FINAL_READINESS": "TERMINAL_NOT_PREREGISTRABLE",
        "NEXT_UNIT": result["C033_NEXT"],
        "STAGE_STOPPED": "CANONICAL_V2_RESULT",
        "PAID_DATA_REQUIRED": False,
        "PAID_DATA_SPEND_USD": 0,
        "COMPILED": False,
        "RECOMPILED_IN_THIS_UNIT": False,
        "SOURCE_RESULT": "docs/research/GV0V03L40_C033_V2_FEASIBILITY.json",
        "COMPILER_SCHEMA_VERSION": result["COMPILER_SCHEMA_VERSION"],
        "COMPILER_POLICY_VERSION": result["COMPILER_POLICY_VERSION"],
        "MARKET_OUTCOMES_OPENED": False,
        "VARIANT_MATRIX": [],
        "EVIDENCE": {"READ_ONLY": True},
    }


def build_report() -> dict:
    cards = _cards()
    built = {
        "C005": c005_record(cards["C005"]),
        "C024": c024_record(cards["C024"]),
        "C031": c031_record(cards["C031"]),
        "C037": c037_record(cards["C037"]),
        "C033": c033_record(),
    }
    for card_id in OPEN_CARDS:
        if built[card_id]["PRIMARY_VARIANT"] is not None:
            raise RuntimeError("a blocked card must not carry a primary variant")
        if built[card_id]["COMPILED"]:
            raise RuntimeError("a blocked card must not be compiled")
    order = ["C005", "C024", "C031", "C033", "C037"]
    ready = [cid for cid in order if built[cid]["FINAL_READINESS"] == "READY_FOR_PREREGISTRATION_DESIGN"]
    return {
        "UNIT": "GV0V03L40_SHORTLIST_E2E_READINESS",
        "OBSERVED_ON": "2026-10-02",
        "SOURCE_MAIN": "cdf4f9fa3821a6c3255ad497a962e7eb02e08d6e",
        "MEMORY_CAMPAIGN_ID": "GV0V03L40",
        "CARDS": {cid: built[cid] for cid in order},
        "READY_CARDS": ready,
        "OWNER_DECISION_CARDS": [],
        "BLOCKED_CARDS": [cid for cid in order if built[cid]["FINAL_READINESS"] in {"DATA_BLOCKED", "PIT_BLOCKED"}],
        "TERMINAL_CARDS": ["C033"],
        "TEST_QUEUE": ready,
        "PREREG_DRAFTS_CREATED": [],
        "TEST_IMPLEMENTATION_SPECS_CREATED": [],
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_2026_OPENED": False,
        "PAID_DATA_SPEND_USD": 0,
        "LLM_CALLS": 0,
        "SCIENTIFIC_DESIGN_CHANGED": False,
    }


def _cell(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "(none)"
    return str(value)


def render_markdown(report: dict) -> str:
    lines = [
        "# GV0V03L40 shortlist final readiness",
        "",
        "**Status:** `COMPLETE`",
        "**Date:** 2026-10-02",
        "",
        "Outcome-blind readiness only. No market target was computed. No card was repriced after a compiler result. C033 was read from its sealed V2 artifact and was not recompiled.",
        "",
        "| Card | Class | Final | Blockers |",
        "|---|---|---|---|",
    ]
    for card_id, row in report["CARDS"].items():
        lines.append(f"| {card_id} | {row['CLASS']} | `{row['FINAL_READINESS']}` | {_cell(row['BLOCKERS'])} |")
    lines.extend([
        "",
        "TEST_QUEUE = [" + ", ".join(report["TEST_QUEUE"]) + "]",
        "PREREG_DRAFTS_CREATED = []",
        "TEST_IMPLEMENTATION_SPECS_CREATED = []",
        "MARKET_OUTCOMES_OPENED = false",
        "PROTECTED_2025_2026_OPENED = false",
        "PAID_DATA_SPEND_USD = 0",
        "LLM_CALLS = 0",
        "",
    ])
    notes = {
        "C005": "The public delisting catalog's oldest notice is 2022-02-24. USD-M history required by the card starts in 2019-09. data.binance.vision has no exchangeInfo snapshot archive. A live exchangeInfo snapshot was not used.",
        "C024": "USD-M daily bookDepth for BTCUSDT and ETHUSDT has no 2022 objects. The first listed key is 2023-01-01 for both symbols. The frozen window was not shortened. Tardis was not bought.",
        "C031": "No as-of Binance BTC deposit-address label archive and no dated confirmation-count policy were found. Aggregated exchange-flow metrics are not address attribution. Today's labels and today's confirmation count were not used.",
        "C033": "Canonical V2 result. Active support is 0 on 1383 inactive kept shocks. Orbit size is 1 and alpha is not attainable. No ALL3 or threshold change was attempted.",
        "C037": "No pinned point-in-time circulating supply. The named volume_share_proxy variant has no frozen arithmetic, so it was not selected and no turnover estimator was invented.",
    }
    for card_id, row in report["CARDS"].items():
        lines.extend([
            f"## {card_id}",
            "",
            notes[card_id],
            "",
            "```",
            f"CLASS = {row['CLASS']}",
            f"DATA_STATUS = {row['DATA_STATUS']}",
            f"PIT_STATUS = {row['PIT_STATUS']}",
            f"PRIMARY_VARIANT = {_cell(row['PRIMARY_VARIANT'])}",
            f"NOMINAL_N = {_cell(row['NOMINAL_N'])}",
            f"MECHANISM_ACTIVE_N = {_cell(row['MECHANISM_ACTIVE_N'])}",
            f"MECHANISM_INACTIVE_N = {_cell(row['MECHANISM_INACTIVE_N'])}",
            f"ALPHA_ATTAINABLE = {_cell(row['ALPHA_ATTAINABLE'])}",
            f"MIN_ATTAINABLE_P = {_cell(row['MIN_ATTAINABLE_P'])}",
            f"GV0R02_V2_STATUS = {row['GV0R02_V2_STATUS']}",
            f"BLOCKERS = {_cell(row['BLOCKERS'])}",
            f"OWNER_DECISION_REQUIRED = {_cell(row['OWNER_DECISION_REQUIRED'])}",
            f"FINAL_READINESS = {row['FINAL_READINESS']}",
            f"NEXT_UNIT = {row['NEXT_UNIT']}",
            f"VARIANTS = {len(row['VARIANT_MATRIX'])}",
            "```",
            "",
        ])
    return "\n".join(lines)


def write_report() -> dict:
    report = build_report()
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REPORT_MD.write_text(render_markdown(report))
    return report


def main() -> None:
    report = write_report()
    print(json.dumps({
        cid: row["FINAL_READINESS"] for cid, row in report["CARDS"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
