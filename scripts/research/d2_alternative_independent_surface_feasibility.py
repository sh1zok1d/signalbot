"""Assemble D2 alternative independent surface feasibility artifacts.

Feasibility only. Does not execute confirmation, open 2025/2026, create
MARKET-07/ARM, or compute D2 outcomes on BitMEX.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.d2_bitmex_pre2020 import (
    AUTHORITY_REL,
    BITMEX_BUCKETED,
    BITMEX_BUCKETED_DOCS,
    BITMEX_LAUNCH_POST,
    BITMEX_PUBLIC_ARCHIVE,
    INSTRUMENT,
    LISTING_UTC,
    PARSER_VERSION,
    PRE2020_END_EXCLUSIVE,
    TIMESTAMP_SEMANTICS,
    refuse_binance_protected_path,
    refuse_d2_outcome_request,
)
from scripts.research.d2_confirmation_dependence_preserving_power import (
    AUTHORITATIVE_POWER_METHOD,
    D2_REFINED_FRESH_N_SEED,
    RETAINED_PREVIOUS_POWER,
)
from scripts.research.d2_confirmation_feasibility_and_design import (
    refuse_protected_price_path,
)
from scripts.research.discovery_sprint_01 import common as C

POWER_RESULT_REL = "docs/research_data/D2_REFINED_FRESH_N_POWER.json"
POWER_RESULT_FALLBACK_REL = "artifacts/research_data/D2_REFINED_FRESH_N_POWER.json"

UTC = C.UTC
UNIT = "D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY"
JSON_REL = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json"
MD_REL = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.md"
D2_RESULT_REL = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"

FROZEN_MECHANISM = {
    "CANDIDATE": "D2 / RULE_1 / RV_ABSTENTION",
    "CONFIRMATION_RULE": (
        "ABSTAIN(t)=1 iff ev.rv_btc_24h(t) > P90 of its own trailing 250 "
        "completed decision-point values with t excluded."
    ),
    "CONFIRMATION_TARGET": (
        "24h direction-aligned adverse-path severity using the exact existing "
        "288 x 5m future-bar construction (arithmetic MAE)."
    ),
    "DIRECTION": "BTC_SIDE(t) = sign(BTC_RET_24H(t))",
    "PRACTICAL_BAR": "DELTA >= 0.20 * UNCONDITIONAL_MEAN",
    "STATISTICAL_CONCEPT": (
        "candidate-abstained rows must have unusually high severity versus "
        "rate-matched random abstention"
    ),
    "RULE_CHANGED": False,
    "TARGET_CHANGED": False,
    "GATES_CHANGED": False,
    "CLOCK_CHANGED": False,
}

SEMANTIC_AUDIT = {
    "PRICE_OBSERVABLE": {
        "binance": "USD-M BTCUSDT last-trade 5m OHLC (CORE_BTC_BINANCE_V0)",
        "bitmex": "XBTUSD last-trade 5m OHLC from GET /trade/bucketed",
        "differences": [
            "BTC/USDT vs BTC/USD quote",
            "venue microstructure / last-price formation",
            "index/mark conventions differ; this surface uses last-trade buckets not mark",
        ],
    },
    "VOLATILITY_OBSERVABLE": {
        "definition": "rv_btc_24h = sqrt(sum of 288 squared 5m log closes)",
        "depends_on_inverse_pnl": False,
        "portable_as_price_path": True,
    },
    "DIRECTION_OBSERVABLE": {
        "definition": "sign of 24h close-to-close log return at feature cutoff",
        "depends_on_inverse_pnl": False,
        "portable_as_price_path": True,
    },
    "ENTRY_SEMANTICS": {
        "definition": "open of the 5m bar opening at T (00:05 UTC)",
        "depends_on_inverse_pnl": False,
    },
    "FUTURE_PATH": {
        "definition": "288 subsequent 5m last-trade bars",
        "depends_on_inverse_pnl": False,
    },
    "ADVERSE_SEVERITY_METRIC": {
        "function": "arithmetic_mae(side, entry_open, future_bars)",
        "formula_long": "max(0, (entry - min(lows)) / entry)",
        "formula_short": "max(0, (max(highs) - entry) / entry)",
        "uses_contract_multiplier": False,
        "uses_inverse_pnl": False,
        "uses_funding": False,
        "normalized_price_path_observable": True,
        "why_xbtusd_ohlc_preserves_target": (
            "The frozen target is relative adverse excursion of the quoted "
            "BTC price path, not USD-M linear PnL and not inverse XBT PnL "
            "(1/entry - 1/exit). Applying the same arithmetic to XBTUSD "
            "last-trade OHLC does not convert inverse payoff into linear PnL."
        ),
    },
    "DECISION_CLOCK": {
        "frozen_clock": "00:05:00Z",
        "authority": (
            "MARKET-05/06 is_forbidden_decision NOT_DAILY_0005; D2 confirmation "
            "DECISION_SCHEDULE cites that grid. Feature cutoff is T-5m so UTC "
            "midnight features + first 5m bar entry."
        ),
        "scientifically_essential_vs_grid_convention": (
            "Inherited 5m UTC grid convention from MARKET-05/06. Not redesigned "
            "here. Exact frozen clock is preserved."
        ),
        "clock_changed_in_this_unit": False,
        "preserve_0005": True,
    },
    "CONTRACT_STRUCTURE": {
        "binance": "linear USD-M perpetual, quote USDT, PnL in USDT",
        "bitmex_xbtusd": (
            "inverse perpetual FFWCSX, quote USD, multiplier -1e8, "
            "settlCurrency XBt, isInverse true"
        ),
        "xbtusd_now_settled": (
            "Instrument API state=Settled, expiry/settle 2026-09-16T12:00:00Z. "
            "Pre-2020 history used the live XBTUSD perpetual; 2026 settlement "
            "does not split the 2016-2019 symbol."
        ),
        "documented_contract_changes_not_in_target": [
            "2016-05-13 listing; funding initially Bitfinex lending",
            "2017-03-31 tick 0.01->0.10 and .BXBT index",
            "2017-04-21 funding interest component fixed 0.03%/day",
            "funding interval may compress 8h->2h; not part of arithmetic_mae",
        ],
    },
    "BITMEX_CONTRACT_COMPATIBILITY": "SCIENTIFICALLY_COMPARABLE_CROSS_VENUE",
    "exact_binance_confirmation": False,
    "future_evidence_label_if_executed": "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION",
    "why_not_exact_observable_portable": (
        "Quote (USD vs USDT), venue last-price, and inverse vs linear contract "
        "environment differ. The mathematical price-path objects are the same."
    ),
    "why_not_nonportable_contract_semantics": (
        "Existing arithmetic_mae does not use linear USD-M PnL, inverse 1/x "
        "PnL, funding, or mark/index. It is a normalized OHLC path metric."
    ),
}


def classify_feasibility(
    *,
    bitmex_n: int | None,
    min_required: int | None,
    compatible: str,
    five_m_available: bool,
) -> dict[str, str]:
    if compatible == "NONPORTABLE_CONTRACT_SEMANTICS":
        return {
            "CONFIRMATION_FEASIBILITY": "BITMEX_NOT_SCIENTIFICALLY_PORTABLE",
            "NEXT_UNIT": "D2_ALTERNATIVE_INDEPENDENT_SURFACE_SEARCH",
        }
    if compatible not in {
        "EXACT_OBSERVABLE_PORTABLE",
        "SCIENTIFICALLY_COMPARABLE_CROSS_VENUE",
    }:
        return {
            "CONFIRMATION_FEASIBILITY": "BITMEX_NOT_SCIENTIFICALLY_PORTABLE",
            "NEXT_UNIT": "D2_ALTERNATIVE_INDEPENDENT_SURFACE_SEARCH",
        }
    if not five_m_available or bitmex_n is None or min_required is None:
        return {
            "CONFIRMATION_FEASIBILITY": "NO_IMMEDIATE_INDEPENDENT_HISTORICAL_SURFACE",
            "NEXT_UNIT": "D2_REMAINS_QUEUED_FOR_FUTURE_CONFIRMATION",
        }
    if int(bitmex_n) >= int(min_required):
        return {
            "CONFIRMATION_FEASIBILITY": (
                "FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION"
            ),
            "NEXT_UNIT": "D2_BITMEX_REPLICATION_PREREG_FREEZE",
        }
    return {
        "CONFIRMATION_FEASIBILITY": "BITMEX_PRE2020_VALID_BUT_UNDERPOWERED",
        "NEXT_UNIT": "D2_ALTERNATIVE_INDEPENDENT_SURFACE_SEARCH",
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    power_path = base / POWER_RESULT_REL
    if not power_path.is_file():
        power_path = base / POWER_RESULT_FALLBACK_REL
    auth_path = base / AUTHORITY_REL
    if not power_path.is_file():
        raise FileNotFoundError(f"MISSING_POWER:{power_path}")
    if not auth_path.is_file():
        raise FileNotFoundError(f"MISSING_BITMEX_AUTHORITY:{auth_path}")
    refuse_protected_price_path(power_path)
    refuse_binance_protected_path(auth_path)
    power = _load_json(power_path)
    authority = _load_json(auth_path)
    if power.get("POWER_USES_BINANCE_2025_2026") is not False:
        raise RuntimeError("POWER_USED_PROTECTED")
    if power.get("POWER_USES_BITMEX_OUTCOMES") is not False:
        raise RuntimeError("POWER_USED_BITMEX_OUTCOMES")
    if authority.get("scientific_outcomes", {}).get("D2_OUTCOME_COMPUTED_ON_BITMEX") is not False:
        refuse_d2_outcome_request("AUTHORITY_FLAG")
    observed = authority["calendar_observed_timestamp_presence"]
    theoretical = authority["calendar_theoretical_complete_grid"]
    bitmex_n = int(observed["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"])
    min_required = int(power["MIN_REQUIRED_FRESH_DECISION_ROWS"])
    five_m = int(authority["coverage"]["observed_5m_bars"]) > 0
    decision = classify_feasibility(
        bitmex_n=bitmex_n,
        min_required=min_required,
        compatible=str(SEMANTIC_AUDIT["BITMEX_CONTRACT_COMPATIBILITY"]),
        five_m_available=bool(five_m),
    )
    backup: dict[str, Any]
    if decision["CONFIRMATION_FEASIBILITY"] == (
        "FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION"
    ):
        backup = {
            "opened": False,
            "reason": "BitMEX primary candidate is feasible before any D2 outcome; no backup venue search.",
            "candidates": [],
        }
    else:
        backup = {
            "opened": True,
            "reason": "BitMEX failed feasibility or power before any D2 outcome.",
            "note": (
                "Metadata/schema only. No D2 outcomes. Contemporaneous venue rows "
                "are not independent daily observations and must not be added."
            ),
            "candidates": _backup_surface_metadata(),
        }
    report = {
        "unit": UNIT,
        "kind": "OUTCOME_BLIND_ALTERNATIVE_SURFACE_FEASIBILITY",
        **FROZEN_MECHANISM,
        "AUTHORITATIVE_POWER_METHOD": AUTHORITATIVE_POWER_METHOD,
        "REFINED_FRESH_N_SEED": D2_REFINED_FRESH_N_SEED,
        "RETAINED_PREVIOUS_POWER": RETAINED_PREVIOUS_POWER,
        "refined_power": {
            k: power[k]
            for k in (
                "COARSE_REFINED_N_GRID",
                "FIVE_ROW_REFINEMENT_GRID",
                "N_BELOW",
                "N_ABOVE",
                "MIN_REQUIRED_FRESH_DECISION_ROWS",
                "POWER_AT_REFINED_MIN_N",
                "POWER_95CI_AT_REFINED_MIN_N",
                "POWER_BY_N",
                "POWER_95CI_BY_N",
                "surfaces",
                "COMPLETE_EXPOSED_YEARS",
                "n_outer",
                "n_inner",
                "POWER_USES_BINANCE_2025_2026",
                "POWER_USES_BITMEX_OUTCOMES",
                "EXPOSED_FILES_OPENED_YEARS",
                "additional_adaptive_search",
            )
            if k in power
        },
        "REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS": min_required,
        "POWER_AT_REFINED_MIN_N": power["POWER_AT_REFINED_MIN_N"],
        "POWER_95CI_AT_REFINED_MIN_N": power["POWER_95CI_AT_REFINED_MIN_N"],
        "PRIMARY_ALTERNATIVE_SURFACE": "BITMEX_XBTUSD_PERPETUAL",
        "BITMEX_INSTRUMENT": INSTRUMENT,
        "BITMEX_INSTRUMENT_TYP": "FFWCSX_INVERSE_PERPETUAL",
        "BITMEX_LISTING": LISTING_UTC.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "BITMEX_RAW_DATA_START": observed["RAW_DATA_START"],
        "BITMEX_FIRST_RV_AVAILABLE_T": observed["FIRST_RV_AVAILABLE_T"],
        "BITMEX_FIRST_RULE_ELIGIBLE_T": observed["FIRST_RULE_ELIGIBLE_T"],
        "BITMEX_LAST_RULE_ELIGIBLE_T": observed["LAST_RULE_ELIGIBLE_T"],
        "BITMEX_PRE2020_ELIGIBLE_N": bitmex_n,
        "BITMEX_THEORETICAL_COMPLETE_GRID_N": theoretical["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"],
        "BITMEX_5M_PATH_AVAILABLE": True,
        "BITMEX_SOURCE_AUTHORITY": {
            "endpoint": BITMEX_BUCKETED,
            "docs": BITMEX_BUCKETED_DOCS,
            "launch_post": BITMEX_LAUNCH_POST,
            "public_archive": BITMEX_PUBLIC_ARCHIVE,
            "timestamp_semantics": TIMESTAMP_SEMANTICS,
            "parser_version": PARSER_VERSION,
            "third_party_kaggle_used": False,
            "authority_rel": AUTHORITY_REL,
            "canonical_jsonl_sha256": authority["canonical_jsonl_sha256"],
            "canonical_jsonl_gz_sha256": authority["canonical_jsonl_gz_sha256"],
            "raw_pages_concat_sha256": authority["raw_pages_concat_sha256"],
        },
        "BITMEX_DATA_GAPS": authority["gaps"],
        "BITMEX_CONTRACT_COMPATIBILITY": SEMANTIC_AUDIT["BITMEX_CONTRACT_COMPATIBILITY"],
        "BITMEX_TEMPORAL_INDEPENDENCE_CLASS": "PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION",
        "TEMPORAL_INDEPENDENCE_CLASSES": {
            "A": "PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION",
            "B": "2020_2024_CROSS_VENUE_ONLY_REPLICATION",
            "C": "FUTURE_PROTECTED_BINANCE",
        },
        "semantic_audit": SEMANTIC_AUDIT,
        "FUTURE_EVIDENCE_LABEL_IF_EXECUTED": (
            "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION"
        ),
        "NOT_EXACT_BINANCE_CONFIRMATION": True,
        "PROTECTED_BINANCE_2025_2026_REMAINS_SEALED_AS_SAME_VENUE_OOS_RESERVE": True,
        **decision,
        "D2_OUTCOME_COMPUTED_ON_BITMEX": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "PROTECTED_2025_PRICE_VALUES_INSPECTED": False,
        "PROTECTED_2026_PRICE_VALUES_INSPECTED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "MARKET_07_CREATED": False,
        "ARM_CREATED": False,
        "PR_READY_TO_MERGE": False,
        "CROSS_VENUE_ROW_COUNT_MULTIPLICATION": False,
        "CONTEMPORANEOUS_VENUES_NOT_POOLED": True,
        "POWER_CRITERION": "POINT_ESTIMATE_STATISTICAL_POWER_GE_0.80",
        "N820_POINT_ESTIMATE_BELOW_080_AFTER_N815": (
            float(power["POWER_BY_N"].get("820", 1.0)) < 0.80
            and float(power["POWER_BY_N"].get("815", 0.0)) >= 0.80
        ),
        "backup_surface_search": backup,
        "pre2020_end_exclusive": PRE2020_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "NOT_CREATED": [
            "MARKET-07",
            "confirmation RESULT",
            "ARM",
            "execution permit",
            "candidate outcome",
            "one-shot run",
        ],
    }
    if report["CROSS_VENUE_ROW_COUNT_MULTIPLICATION"] is True:
        raise RuntimeError("CROSS_VENUE_N_MULTIPLIED")
    return report


def _backup_surface_metadata() -> list[dict[str, Any]]:
    """Metadata/schema only. Invoked only after BitMEX feasibility failure."""
    return [
        {
            "venue": "Deribit",
            "instrument": "BTC-PERPETUAL",
            "EARLIEST_USABLE_DATE": "2018-08-27T00:00:00Z_UNVERIFIED_NEEDS_OFFICIAL_CENSUS",
            "PRE2020_ELIGIBLE_N": None,
            "5M_PATH_AVAILABLE": "INSUFFICIENT_INFORMATION",
            "CONTRACT_TYPE": "inverse_perpetual",
            "DATA_AUTHORITY": "https://www.deribit.com/api/v2/public/get_tradingview_chart_data",
            "TEMPORAL_INDEPENDENCE_CLASS": "PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION",
            "SEMANTIC_COMPATIBILITY": "INSUFFICIENT_INFORMATION",
            "note": "Shorter pre-2020 window than XBTUSD; not selected while BitMEX is primary.",
        },
        {
            "venue": "Bybit",
            "instrument": "BTCUSD",
            "EARLIEST_USABLE_DATE": "2018-11-01T00:00:00Z_UNVERIFIED_NEEDS_OFFICIAL_CENSUS",
            "PRE2020_ELIGIBLE_N": None,
            "5M_PATH_AVAILABLE": "INSUFFICIENT_INFORMATION",
            "CONTRACT_TYPE": "inverse_perpetual",
            "DATA_AUTHORITY": "https://bybit-exchange.github.io/docs/v5/market/kline",
            "TEMPORAL_INDEPENDENCE_CLASS": "PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION",
            "SEMANTIC_COMPATIBILITY": "INSUFFICIENT_INFORMATION",
        },
        {
            "venue": "OKX",
            "instrument": "BTC-USD-SWAP",
            "EARLIEST_USABLE_DATE": "INSUFFICIENT_INFORMATION",
            "PRE2020_ELIGIBLE_N": None,
            "5M_PATH_AVAILABLE": "INSUFFICIENT_INFORMATION",
            "CONTRACT_TYPE": "inverse_perpetual",
            "DATA_AUTHORITY": "https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks-history",
            "TEMPORAL_INDEPENDENCE_CLASS": "PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION",
            "SEMANTIC_COMPATIBILITY": "INSUFFICIENT_INFORMATION",
        },
    ]


def render_markdown(report: dict[str, Any]) -> str:
    power = report["refined_power"]
    surfaces = []
    for row in power.get("surfaces") or []:
        ci = row.get("STATISTICAL_POWER_AT_20PCT_95CI") or [None, None]
        surfaces.append(
            f"- N={row['N']} stage={row.get('grid_stage')} "
            f"power={row['STATISTICAL_POWER_AT_20PCT']} "
            f"95CI=[{ci[0]}, {ci[1]}]"
        )
    gaps = report["BITMEX_DATA_GAPS"]
    backup = report["backup_surface_search"]
    return f"""# D2 alternative independent surface feasibility

**Unit:** `{report["unit"]}`  
**Kind:** outcome-blind feasibility only. Not confirmation execution.

## Frozen mechanism (unchanged)

Candidate: `{report["CANDIDATE"]}`

- rule: {report["CONFIRMATION_RULE"]}
- target: {report["CONFIRMATION_TARGET"]}
- direction: {report["DIRECTION"]}
- practical bar: {report["PRACTICAL_BAR"]}
- statistical concept: {report["STATISTICAL_CONCEPT"]}
- `RULE_CHANGED` / `TARGET_CHANGED` / `GATES_CHANGED` / `CLOCK_CHANGED` = false

00:05 UTC is preserved as the frozen MARKET-05/06 5m grid convention. It was
not redesigned for BitMEX convenience.

## Refined fresh-N power (Binance 2020-2024 only)

Method: `{report["AUTHORITATIVE_POWER_METHOD"]}`  
Seed: `{report["REFINED_FRESH_N_SEED"]}` (previous 728/1092 retained from seed 20260921123 as `{report["RETAINED_PREVIOUS_POWER"]}`)

```
N_BELOW = {power.get("N_BELOW")}
N_ABOVE = {power.get("N_ABOVE")}
FIVE_ROW_REFINEMENT_GRID = {power.get("FIVE_ROW_REFINEMENT_GRID")}
REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = {report["REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS"]}
POWER_AT_REFINED_MIN_N = {report["POWER_AT_REFINED_MIN_N"]}
POWER_95CI_AT_REFINED_MIN_N = {report["POWER_95CI_AT_REFINED_MIN_N"]}
POWER_USES_BINANCE_2025_2026 = false
POWER_USES_BITMEX_OUTCOMES = false
```

{chr(10).join(surfaces)}

1092 is only the smallest previously tested size meeting power, not an
assumed true minimum.

## Primary candidate: BitMEX XBTUSD

Instrument: `{report["BITMEX_INSTRUMENT"]}` inverse perpetual (`{report["BITMEX_INSTRUMENT_TYP"]}`), listing `{report["BITMEX_LISTING"]}`.

Official source: `{report["BITMEX_SOURCE_AUTHORITY"]["endpoint"]}`  
Docs: `{report["BITMEX_SOURCE_AUTHORITY"]["docs"]}`  
Launch: `{report["BITMEX_SOURCE_AUTHORITY"]["launch_post"]}`  
Timestamp semantics: `{report["BITMEX_SOURCE_AUTHORITY"]["timestamp_semantics"]}` (open_time = timestamp − 5m).  
Kaggle / third-party cleaned datasets: not used.

```
BITMEX_RAW_DATA_START = {report["BITMEX_RAW_DATA_START"]}
BITMEX_FIRST_RV_AVAILABLE_T = {report["BITMEX_FIRST_RV_AVAILABLE_T"]}
BITMEX_FIRST_RULE_ELIGIBLE_T = {report["BITMEX_FIRST_RULE_ELIGIBLE_T"]}
BITMEX_LAST_RULE_ELIGIBLE_T = {report["BITMEX_LAST_RULE_ELIGIBLE_T"]}
BITMEX_PRE2020_ELIGIBLE_N = {report["BITMEX_PRE2020_ELIGIBLE_N"]}
BITMEX_THEORETICAL_COMPLETE_GRID_N = {report["BITMEX_THEORETICAL_COMPLETE_GRID_N"]}
BITMEX_5M_PATH_AVAILABLE = {report["BITMEX_5M_PATH_AVAILABLE"]}
missing_bucket_count = {gaps["missing_bucket_count"]}
```

Temporal class: `{report["BITMEX_TEMPORAL_INDEPENDENCE_CLASS"]}` (class A).  
A 2020-2024 other-venue window is class B and is not counted as independent
temporal confirmation. Protected Binance 2025/2026 remains class C, sealed.

## Semantic compatibility

Classification: `{report["BITMEX_CONTRACT_COMPATIBILITY"]}`

The frozen adverse-severity metric is a **normalized price-path** observable
(`(entry − min(low))/entry` or `(max(high) − entry)/entry`). It does not use
inverse 1/x PnL, linear USD-M PnL, funding, or mark/index. XBTUSD last-trade
OHLC can carry that target without converting inverse payoff into linear PnL.

It is **not** `EXACT_OBSERVABLE_PORTABLE` (USD vs USDT, venue last-price,
inverse vs linear environment). A later BitMEX result, if executed, is

`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`

not `EXACT_BINANCE_CONFIRMATION`. Future protected Binance 2025/2026 remains
the stronger same-venue OOS reserve.

## Decision

```
CONFIRMATION_FEASIBILITY = {report["CONFIRMATION_FEASIBILITY"]}
NEXT_UNIT = {report["NEXT_UNIT"]}
D2_OUTCOME_COMPUTED_ON_BITMEX = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
ARM_CREATED = false
CROSS_VENUE_ROW_COUNT_MULTIPLICATION = false
```

Backup search opened: `{backup["opened"]}`. {backup["reason"]}

## Not created

{chr(10).join(f"- {item}" for item in report["NOT_CREATED"])}
"""


def write_artifacts(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    report = build_report(repo=base)
    (base / JSON_REL).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (base / MD_REL).write_text(render_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    written = write_artifacts()
    keys = (
        "REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS",
        "POWER_AT_REFINED_MIN_N",
        "POWER_95CI_AT_REFINED_MIN_N",
        "PRIMARY_ALTERNATIVE_SURFACE",
        "BITMEX_INSTRUMENT",
        "BITMEX_RAW_DATA_START",
        "BITMEX_FIRST_RULE_ELIGIBLE_T",
        "BITMEX_LAST_RULE_ELIGIBLE_T",
        "BITMEX_PRE2020_ELIGIBLE_N",
        "BITMEX_5M_PATH_AVAILABLE",
        "BITMEX_CONTRACT_COMPATIBILITY",
        "BITMEX_TEMPORAL_INDEPENDENCE_CLASS",
        "CONFIRMATION_FEASIBILITY",
        "D2_OUTCOME_COMPUTED_ON_BITMEX",
        "PROTECTED_2025_OPENED",
        "PROTECTED_2026_OPENED",
        "MARKET_07_CREATED",
        "ARM_CREATED",
        "PR_READY_TO_MERGE",
        "NEXT_UNIT",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
