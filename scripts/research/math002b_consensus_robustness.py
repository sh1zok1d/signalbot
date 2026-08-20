#!/usr/bin/env python3
"""MATH-002B / issue #52 -- historical 3/3 vs 2/3 Stage 2 consensus
robustness study (deterministic-completion + partial harness; MATH-002B
itself remains open, blocked on real historical database access).

READ-ONLY. This script never INSERTs/UPDATEs/DELETEs, runs no DDL, and
opens every database transaction as `READ ONLY` explicitly (defense in
depth on top of only ever issuing SELECTs). It never touches production
Stage 2 tables' contents -- it only reads `exchange_feature_vectors` and
recomputes controlled consensus variants IN MEMORY via the real, unmodified
`analytics.feature_engine.consensus.compute_consensus_features`.

Usage:
    python -m scripts.research.math002b_consensus_robustness --check-access
    python -m scripts.research.math002b_consensus_robustness --symbol BTCUSDT \\
        --market-type perp --timeframe 4h --family price_structure \\
        --calculation-version <16-hex> --out /tmp/math002b_4h_price_structure.json

`--check-access` only verifies read-only connectivity to the configured
Postgres instance and exits -- it makes no other query and writes nothing.
If the database is unreachable, it prints `DATA_ACCESS_BLOCKED` and exits
non-zero; this is the honest, expected outcome in an environment with no
provisioned historical Postgres instance (this is NOT a failure of the
harness itself).

Implemented (tech-lead review round 1, HEAD cd32ac3 -> this amendment):
* Controlled `FULL3 -> BB/BO/BYO` recomputation for exact-3/3 buckets,
  restricted to the three canonical study venues at the SQL level
  (finding 4) -- `complete_3of3_bucket_count` counts only buckets actually
  analyzed as canonical Binance+Bybit+OKX.
* Per-family exclusion facts for every PRESENT venue are derived via the
  SAME `analytics.feature_engine.bucket_coordinator._derive_family_exclusions()`
  production uses (finding 2) -- a venue valid for the TARGET family can
  legitimately have NULLs in a non-target family (the price SQL only
  guarantees price_structure fields; the OI SQL only guarantees OI), and
  this is now handled honestly rather than fabricated or left to fail
  `compute_consensus_features()`'s own validation.
* Config/calculation-version identity (`config_hash`, `config_version`,
  `feature_schema_version`, `calculation_version`, confidence weights,
  `robust_z_threshold`, `minimum_exchange_coverage`) for the FULL3/BB/BO/BYO
  path all come from the real
  `analytics.feature_engine.consensus_input_adapter.build_consensus_feature_request()`
  against a resolved `Stage2Config` (finding 3) -- never independently
  hardcoded. If a historical row's stored `calculation_version` cannot be
  reproduced by the currently-resolved config, the run FAILS EXPLICITLY
  (`Math002BCalculationVersionUnsupported`) rather than silently mixing a
  historical identity with today's threshold/config semantics.
* `BINANCE_ONLY_RESEARCH_BASELINE` IS computed and reported (previously
  imported/labeled but never actually computed) via a separate,
  clearly-labeled `minimum_exchange_coverage=1` request -- it reuses the
  SAME resolved confidence weights/robust_z_threshold as the production
  path (never arbitrary literals), only the coverage minimum differs, and
  it is never substituted for, or presented as, production `2/3` behavior.
* `_summarize_study()` reports every metric this harness actually computes:
  true absolute (magnitude) AND signed median-delta distributions,
  relative-delta distribution (where stable), agreement-delta distribution,
  confidence-delta distribution, outlier/family-quality-gate flip rates,
  exact analyzed bucket count, and per-pair provenance (contributing/
  omitted venues).

Explicitly NOT implemented (documented, not silently claimed -- see
`docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md` §B.3/§B.8 for why):
natural (non-controlled) 2/3 prevalence study; percentile-variant series
recompute; regime/bias/Stage-5 setup replay; extreme-example table
extraction. Building any of these without real historical data to validate
against would be "fake infrastructure merely to produce a number", which
the MATH-002B task explicitly forbids -- they remain FUTURE work once
DATA_ACCESS is restored.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any, Optional

# `_derive_family_exclusions` is private (no public re-export exists) but is
# imported directly rather than duplicated: the whole point of finding 2 is
# that this research harness must derive EXACTLY the same per-family
# exclusion facts production does, and a local copy would risk silently
# drifting from that logic over time -- the failure mode this fix exists to
# close. No production code is changed to expose it; this is read-only reuse.
from analytics.feature_engine.bucket_coordinator import _derive_family_exclusions
from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_input_adapter import (
    ConsensusInputError,
    build_consensus_feature_request,
)
from analytics.feature_engine.consensus_models import FAMILIES, ConsensusFeatureRequest
from analytics.feature_engine.models import ExchangeFeatureVector
# The GENERIC §6.3a per-family coverage/confidence floor -- NOT
# regime_4h's own REGIME_MIN_COVERAGE/REGIME_MIN_CONFIDENCE (tech-lead
# review round 2: this helper runs across every timeframe/family this
# harness studies, not just the 4h regime consumer; the two threshold
# pairs happen to share the same numeric value today but are owned by
# different consumers and must not be conflated).
from analytics.forecasting_v2.family_quality import FAMILY_MIN_CONFIDENCE, FAMILY_MIN_COVERAGE
from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from scripts.research.math002b_lib import (
    BB,
    BINANCE_ONLY,
    BO,
    BYO,
    FULL3,
    PairComparison,
    family_quality_gate_flip_rate,
    outlier_report_flip_rate,
    sign_flip_rate,
    summarize,
)

EXCHANGES = ("binance", "bybit", "okx")
PAIRS = {BB: ("binance", "bybit"), BO: ("binance", "okx"), BYO: ("bybit", "okx")}
TIMEFRAMES = ("4h", "1h", "15m", "5m")
_STUDY_FAMILIES = ("price_structure", "oi")
_VARIANT_OMISSION_REASON = "MATH002B_HISTORICAL_VARIANT_OMISSION"

_EXCHANGE_LIST_SQL = "('binance', 'bybit', 'okx')"  # kept in one place, interpolated into SQL text below


class Math002BCalculationVersionUnsupported(RuntimeError):
    """Raised when a historical EFV's stored identity/version fields cannot
    be reproduced by the currently-resolved `Stage2Config` -- an explicit,
    reported support limitation (tech-lead review round 1, finding 3), never
    a silent skip or a silent mix of a historical calculation identity with
    today's unrelated threshold/config semantics."""


def _omitted(pair_name: str) -> str:
    contributing = set(PAIRS[pair_name])
    (omitted,) = (ex for ex in EXCHANGES if ex not in contributing)
    return omitted


# ---- exact-3/3 bucket discovery (read-only SQL) ----------------------------
# Finding 4: restricted explicitly to the three canonical study venues --
# `HAVING COUNT(DISTINCT exchange) = 3` alone could admit any three exchange
# names (e.g. a future-added venue), which would silently redefine what
# "FULL3" means for this study.
_EXACT_3OF3_PRICE_SQL = f"""
    SELECT bucket_ts
    FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4
      AND exchange IN {_EXCHANGE_LIST_SQL}
      AND price_move_pct IS NOT NULL
      AND range_width_pct IS NOT NULL
      AND close_price IS NOT NULL
      AND is_usable = TRUE
    GROUP BY bucket_ts
    HAVING COUNT(DISTINCT exchange) = 3
    ORDER BY bucket_ts
"""

_EXACT_3OF3_OI_SQL = f"""
    SELECT bucket_ts
    FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4
      AND exchange IN {_EXCHANGE_LIST_SQL}
      AND oi_change_pct IS NOT NULL
    GROUP BY bucket_ts
    HAVING COUNT(DISTINCT exchange) = 3
    ORDER BY bucket_ts
"""

_ROWS_FOR_BUCKET_SQL = f"""
    SELECT * FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4 AND bucket_ts = $5
      AND exchange IN {_EXCHANGE_LIST_SQL}
"""


def _row_to_efv(row: Any) -> ExchangeFeatureVector:
    """Build a real `ExchangeFeatureVector` from one `exchange_feature_vectors`
    row -- field-for-field, no coercion, no defaulting of a NULL to a
    synthetic value."""
    d = dict(row)
    return ExchangeFeatureVector(**{
        f: d[f] for f in (
            "exchange", "symbol", "market_type", "timeframe", "bucket_ts",
            "feature_schema_version", "calculation_version", "price_move_pct",
            "range_width_pct", "close_price", "volume_raw", "volume_raw_unit",
            "volume_notional_usd", "taker_buy_notional_usd",
            "taker_sell_notional_usd", "taker_delta_notional_usd",
            "cvd_delta_notional_usd", "oi_change_pct", "oi_unit",
            "funding_rate", "long_liquidation_notional",
            "short_liquidation_notional", "liquidation_event_count",
            "liquidation_feed_quality", "is_snapshot_feed", "bars_expected",
            "bars_present", "has_gap", "is_usable", "config_hash",
            "config_version", "code_version",
        )
    })


# ---- production-semantics-reusing request construction ---------------------
def _resolve_authoritative_identity(
    stage2_config: Stage2Config, efv: ExchangeFeatureVector,
) -> tuple[str, str, int, str]:
    """Re-derive `(config_hash, config_version, feature_schema_version,
    calculation_version)` from the CURRENTLY resolved `Stage2Config` for
    `efv`'s symbol -- exactly the same derivation
    `consensus_input_adapter.build_consensus_feature_request()` performs
    internally. Exposed separately so the `BINANCE_ONLY_RESEARCH_BASELINE`
    path (which cannot use `build_consensus_feature_request()` because it
    needs `minimum_exchange_coverage=1`, not the production `2`) still gets
    the identical identity-reproducibility check."""
    resolved = stage2_config.resolve(efv.symbol)
    config_hash = resolved.config_hash()
    config_version = stage2_config.config_version
    feature_schema_version = stage2_config.feature_schema_version
    calculation_version = compute_calculation_version(
        feature_schema_version, config_hash, efv.code_version)
    return config_hash, config_version, feature_schema_version, calculation_version


def _require_reproducible_identity(stage2_config: Stage2Config, efv: ExchangeFeatureVector) -> None:
    config_hash, config_version, feature_schema_version, calculation_version = (
        _resolve_authoritative_identity(stage2_config, efv))
    actual = (efv.config_hash, efv.config_version, efv.feature_schema_version, efv.calculation_version)
    expected = (config_hash, config_version, feature_schema_version, calculation_version)
    if actual != expected:
        raise Math002BCalculationVersionUnsupported(
            f"historical EFV for exchange={efv.exchange!r} at bucket_ts={efv.bucket_ts!r} has "
            f"identity {actual!r}, but the currently-resolved Stage2Config derives {expected!r} "
            "for the same code_version -- this historical calculation_version cannot be "
            "reproduced by the available config. Restrict the study to a reproducible "
            "calculation_version rather than silently mixing identities."
        )


def _build_family_exclusions(
    efv_by_exchange: dict[str, ExchangeFeatureVector], *, present_exchanges: tuple[str, ...],
    omit: Optional[str],
) -> dict[str, dict[str, str]]:
    """Honest per-family exclusion facts: the deliberately omitted variant
    venue (research-only), overlaid on top of REAL per-family exclusion
    reasons for every other present venue, derived via the same
    `_derive_family_exclusions()` production uses. A present EFV valid for
    the TARGET family can still legitimately be excluded from a
    NON-target family here (e.g. a price_structure-guaranteed row with
    NULL funding) -- never fabricated, never silently defaulted."""
    exclusions: dict[str, dict[str, str]] = {family: {} for family in FAMILIES}
    if omit is not None:
        for family in FAMILIES:
            exclusions[family][omit] = _VARIANT_OMISSION_REASON
    for ex in present_exchanges:
        efv = efv_by_exchange[ex]
        for family, reason in _derive_family_exclusions(efv).items():
            exclusions[family][ex] = reason
    return exclusions


def _build_variant_request(
    stage2_config: Stage2Config, efv_by_exchange: dict[str, ExchangeFeatureVector], *,
    omit: Optional[str],
) -> ConsensusFeatureRequest:
    """Build one real `ConsensusFeatureRequest` for either FULL3
    (`omit=None`) or a controlled 2-venue variant (`omit=<venue>`), reusing
    PRODUCTION identity/config/exclusion semantics exactly via
    `build_consensus_feature_request()` -- never a hand-built request with
    independently hardcoded weights/threshold (finding 3), and never a
    fabricated exclusion reason for a present venue (finding 2)."""
    present_exchanges = tuple(ex for ex in EXCHANGES if ex != omit)
    exclusions = _build_family_exclusions(efv_by_exchange, present_exchanges=present_exchanges, omit=omit)
    present_efvs = [efv_by_exchange[ex] for ex in present_exchanges]
    try:
        return build_consensus_feature_request(
            stage2_config, exchange_features=present_efvs,
            expected_exchanges_by_family={family: EXCHANGES for family in FAMILIES},
            exclusion_reasons_by_family=exclusions,
        )
    except ConsensusInputError as exc:
        raise Math002BCalculationVersionUnsupported(
            f"bucket_ts={present_efvs[0].bucket_ts!r}: historical EFV identity/version does not "
            f"match the currently resolved Stage2Config: {exc}"
        ) from exc


def _build_binance_only_request(
    stage2_config: Stage2Config, efv_by_exchange: dict[str, ExchangeFeatureVector],
) -> ConsensusFeatureRequest:
    """`BINANCE_ONLY_RESEARCH_BASELINE` -- a SEPARATE, clearly-labeled
    diagnostic request. `minimum_exchange_coverage=1` is a deliberate
    RESEARCH-ONLY override (never production's own value, which is always
    2); confidence weights and `robust_z_threshold` are still the REAL
    resolved-config values, never arbitrary literals. Never substituted
    for, or presented as, current production `2/3` behavior."""
    binance_efv = efv_by_exchange["binance"]
    _require_reproducible_identity(stage2_config, binance_efv)
    resolved = stage2_config.resolve(binance_efv.symbol)
    exclusions = _build_family_exclusions(
        efv_by_exchange, present_exchanges=("binance",), omit=None)
    for family in FAMILIES:
        for ex in ("bybit", "okx"):
            exclusions[family][ex] = _VARIANT_OMISSION_REASON
    data_confidence = resolved["data_confidence"]
    return ConsensusFeatureRequest(
        symbol=binance_efv.symbol, market_type=binance_efv.market_type,
        timeframe=binance_efv.timeframe, bucket_ts=binance_efv.bucket_ts,
        feature_schema_version=binance_efv.feature_schema_version,
        calculation_version=binance_efv.calculation_version,
        config_hash=binance_efv.config_hash, config_version=binance_efv.config_version,
        code_version=binance_efv.code_version,
        exchange_features=[binance_efv],
        expected_exchanges_by_family={family: EXCHANGES for family in FAMILIES},
        exclusion_reasons_by_family=exclusions,
        minimum_exchange_coverage=1,  # RESEARCH-ONLY override -- see docstring
        confidence_weights=data_confidence["weights"],
        robust_z_threshold=resolved["outliers"]["robust_z_threshold"],
    )


def _outlier_metric_for_family(family: str) -> Optional[str]:
    return {"price_structure": "price_move_pct", "oi": "oi_change_pct"}.get(family)


_MEDIAN_FIELD = {"price_structure": "price_move_pct_median", "oi": "oi_change_pct_median"}
_AGREEMENT_FIELD = {"price_structure": "price_direction_agreement", "oi": "oi_direction_agreement"}
_MAD_FIELD = {"price_structure": "price_move_pct_mad", "oi": "oi_change_pct_mad"}


def _family_quality_gate_pass(consensus, family: str) -> bool:
    """The GENERIC §6.3a per-family coverage/confidence gate
    (`family_quality.FAMILY_MIN_COVERAGE`/`FAMILY_MIN_CONFIDENCE`) -- used
    identically across every timeframe/family this harness studies, never
    the 4h-regime-specific `REGIME_MIN_COVERAGE`/`REGIME_MIN_CONFIDENCE`.
    Reads `coverage_by_metric[family].ratio`/`data_confidence_by_metric[family]`
    directly off the already-computed `ConsensusFeatureVector` (the same
    facts `family_quality.family_quality()` reads, just from the vector's
    own attributes rather than a JSON-decoded row -- both scoped to exactly
    ONE metric family, never the global rollup)."""
    return (
        consensus.coverage_by_metric[family].ratio >= FAMILY_MIN_COVERAGE
        and consensus.data_confidence_by_metric[family] >= FAMILY_MIN_CONFIDENCE
    )


def compare_bucket(
    stage2_config: Stage2Config, efv_by_exchange: dict[str, ExchangeFeatureVector], *,
    family: str, timeframe: str,
) -> list[PairComparison]:
    """Recompute FULL3 and every BB/BO/BYO variant for ONE exact-3/3 bucket
    and return the three `PairComparison`s, using real production request
    construction throughout (see module docstring). Pure with respect to
    I/O -- the caller already fetched `efv_by_exchange` read-only."""
    full3_request = _build_variant_request(stage2_config, efv_by_exchange, omit=None)
    full3 = compute_consensus_features(full3_request)

    metric = _outlier_metric_for_family(family)
    full3_has_outlier = metric is not None and metric in full3.outlier_exchanges
    full3_family_quality_pass = _family_quality_gate_pass(full3, family)

    comparisons: list[PairComparison] = []
    for pair_name in PAIRS:
        omitted = _omitted(pair_name)
        pair_request = _build_variant_request(stage2_config, efv_by_exchange, omit=omitted)
        pair = compute_consensus_features(pair_request)
        pair_has_outlier = metric is not None and metric in pair.outlier_exchanges
        pair_family_quality_pass = _family_quality_gate_pass(pair, family)
        comparisons.append(PairComparison(
            bucket_ts=full3_request.bucket_ts, timeframe=timeframe, family=family,
            pair_name=pair_name, omitted_venue=omitted,
            full3_median=getattr(full3, _MEDIAN_FIELD[family]),
            pair_median=getattr(pair, _MEDIAN_FIELD[family]),
            full3_mad=getattr(full3, _MAD_FIELD[family]), pair_mad=getattr(pair, _MAD_FIELD[family]),
            full3_agreement=getattr(full3, _AGREEMENT_FIELD[family]),
            pair_agreement=getattr(pair, _AGREEMENT_FIELD[family]),
            full3_confidence=full3.data_confidence_by_metric[family],
            pair_confidence=pair.data_confidence_by_metric[family],
            full3_has_outlier=full3_has_outlier, pair_has_outlier=pair_has_outlier,
            full3_family_quality_gate_pass=full3_family_quality_pass,
            pair_family_quality_gate_pass=pair_family_quality_pass,
        ))
    return comparisons


def compute_binance_only_diagnostic(
    stage2_config: Stage2Config, efv_by_exchange: dict[str, ExchangeFeatureVector], *, family: str,
) -> dict:
    """Actually compute (not merely label) the `BINANCE_ONLY_RESEARCH_BASELINE`
    diagnostic for one bucket. Returned dict is explicitly tagged
    `variant=BINANCE_ONLY_RESEARCH_BASELINE` and a `note` reiterating it is
    not production `2/3` behavior."""
    request = _build_binance_only_request(stage2_config, efv_by_exchange)
    result = compute_consensus_features(request)
    return {
        "variant": BINANCE_ONLY,
        "note": "RESEARCH ONLY -- NOT current production 2/3 behavior (minimum_exchange_coverage=1 override)",
        "bucket_ts": str(request.bucket_ts),
        "median": getattr(result, _MEDIAN_FIELD[family]),
        "coverage_ratio": result.coverage_by_metric[family].ratio,
        "data_confidence": result.data_confidence_by_metric[family],
    }


async def _check_access(dsn: str) -> bool:
    try:
        import asyncpg
    except ImportError:
        print("DATA_ACCESS_BLOCKED: asyncpg not installed", file=sys.stderr)
        return False
    try:
        conn = await asyncpg.connect(dsn, timeout=5)
    except Exception as exc:  # noqa: BLE001 -- any connection failure is DATA_ACCESS_BLOCKED
        print(f"DATA_ACCESS_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    try:
        async with conn.transaction(readonly=True):
            await conn.fetchval("SELECT 1")
    finally:
        await conn.close()
    return True


async def run_study(
    dsn: str, *, symbol: str, market_type: str, timeframe: str, family: str,
    calculation_version: str, stage2_config: Optional[Stage2Config] = None,
) -> dict:
    import asyncpg  # local import: never required unless actually running the DB study

    if family not in _STUDY_FAMILIES:
        raise ValueError(f"family must be one of {_STUDY_FAMILIES}, got {family!r}")
    if stage2_config is None:
        stage2_config = Stage2Config.load()

    sql = _EXACT_3OF3_PRICE_SQL if family == "price_structure" else _EXACT_3OF3_OI_SQL

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        async with conn.transaction(readonly=True):
            bucket_rows = await conn.fetch(sql, symbol, market_type, timeframe, calculation_version)
            all_comparisons: list[PairComparison] = []
            binance_only_diagnostics: list[dict] = []
            analyzed_bucket_count = 0
            for brow in bucket_rows:
                rows = await conn.fetch(
                    _ROWS_FOR_BUCKET_SQL, symbol, market_type, timeframe,
                    calculation_version, brow["bucket_ts"])
                efv_by_exchange = {r["exchange"]: _row_to_efv(r) for r in rows}
                if set(efv_by_exchange) != set(EXCHANGES):
                    continue  # defensive -- SQL already restricts to the 3 canonical venues
                all_comparisons.extend(
                    compare_bucket(stage2_config, efv_by_exchange, family=family, timeframe=timeframe))
                binance_only_diagnostics.append(
                    compute_binance_only_diagnostic(stage2_config, efv_by_exchange, family=family))
                analyzed_bucket_count += 1
    finally:
        await conn.close()

    return _summarize_study(
        symbol=symbol, market_type=market_type, timeframe=timeframe, family=family,
        complete_3of3_bucket_count=analyzed_bucket_count, comparisons=all_comparisons,
        binance_only_diagnostics=binance_only_diagnostics,
    )


def _summarize_study(
    *, symbol: str, market_type: str, timeframe: str, family: str,
    complete_3of3_bucket_count: int, comparisons: list[PairComparison],
    binance_only_diagnostics: Optional[list[dict]] = None,
) -> dict:
    """Report every predeclared metric this harness actually computes (tech-
    lead review round 1, finding 5): true absolute AND signed median-delta
    distributions, relative-delta distribution (where stable), agreement-
    delta distribution, confidence-delta distribution, outlier/family-
    quality-gate flip rates, exact analyzed bucket count, and per-pair
    provenance."""
    by_pair: dict[str, list[PairComparison]] = {p: [] for p in PAIRS}
    for c in comparisons:
        by_pair[c.pair_name].append(c)

    out: dict[str, Any] = {
        "symbol": symbol, "market_type": market_type, "timeframe": timeframe,
        "family": family, "complete_3of3_bucket_count": complete_3of3_bucket_count,
        "pairs": {},
        "binance_only_research_baseline": {
            "implemented": True,
            "note": "RESEARCH ONLY -- NOT current production 2/3 behavior",
            "n": len(binance_only_diagnostics or []),
            "median": asdict(summarize([
                d["median"] for d in (binance_only_diagnostics or []) if d["median"] is not None])),
        },
        "not_implemented_this_pr": [
            "natural_2of3_prevalence_study", "percentile_variant_series",
            "regime_flip_study", "bias_flip_study", "setup_eligibility_flip_study",
            "extreme_example_table",
        ],
    }
    for pair_name, pair_comparisons in by_pair.items():
        abs_deltas = [c.absolute_median_delta for c in pair_comparisons
                      if c.absolute_median_delta is not None]
        signed_deltas = [c.signed_median_delta for c in pair_comparisons
                         if c.signed_median_delta is not None]
        rel_deltas = [c.relative_median_delta for c in pair_comparisons
                     if c.relative_median_delta is not None]
        agreement_deltas = [c.agreement_delta for c in pair_comparisons
                           if c.agreement_delta is not None]
        confidence_deltas = [c.confidence_delta for c in pair_comparisons
                            if c.confidence_delta is not None]
        out["pairs"][pair_name] = {
            "contributing_venues": sorted(PAIRS[pair_name]),
            "omitted_venue": _omitted(pair_name),
            "n": len(pair_comparisons),
            "absolute_median_delta": asdict(summarize(abs_deltas)),
            "signed_median_delta": asdict(summarize(signed_deltas)),
            "relative_median_delta": asdict(summarize(rel_deltas)),
            "agreement_delta": asdict(summarize(agreement_deltas)),
            "confidence_delta": asdict(summarize(confidence_deltas)),
            "sign_flip_rate": sign_flip_rate(pair_comparisons),
            "outlier_report_flip_rate": outlier_report_flip_rate(pair_comparisons),
            "family_quality_gate_flip_rate": family_quality_gate_flip_rate(pair_comparisons),
        }
    return out


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-access", action="store_true",
                        help="only verify read-only DB connectivity, then exit")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--market-type", default="perp")
    parser.add_argument("--timeframe", choices=TIMEFRAMES, default="4h")
    parser.add_argument("--family", choices=_STUDY_FAMILIES, default="price_structure")
    parser.add_argument("--calculation-version", required=False,
                        help="exact Stage2 calculation_version to study (required unless --check-access)")
    parser.add_argument("--out", default=None, help="write JSON summary here (default: stdout only)")
    args = parser.parse_args()

    from common.config import Config, load_secrets
    cfg = Config.load()
    secrets = load_secrets(cfg)
    dsn = secrets.postgres_dsn

    if args.check_access:
        ok = asyncio.run(_check_access(dsn))
        if not ok:
            return 1
        print("DB read-only connectivity OK.")
        return 0

    if not args.calculation_version:
        parser.error("--calculation-version is required unless --check-access is passed")

    try:
        result = asyncio.run(run_study(
            dsn, symbol=args.symbol, market_type=args.market_type, timeframe=args.timeframe,
            family=args.family, calculation_version=args.calculation_version))
    except Math002BCalculationVersionUnsupported as exc:
        print(f"UNSUPPORTED_CALCULATION_VERSION: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
