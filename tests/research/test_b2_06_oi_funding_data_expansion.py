"""Synthetic adversarial tests for the B2-06 OI/funding data-expansion contract.

No test here downloads Binance history, opens CORE partitions, inspects B2-06
predictive outcomes, or authorizes 2025/2026 windows. Fixtures are local.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.research.binance_um_oi_funding_v0_contract_lib import (
    AVAILABILITY_SEMANTICS_VERSION,
    CONTRACT_STATUS,
    DATASET_ID,
    FROZEN_SOURCE,
    FUNDING_HEADER,
    FUNDING_MAX_STALENESS_MS,
    FUNDING_PERIOD_MS,
    OI_HEADER,
    OI_PERIOD_MS,
    SNAPSHOT_AUTHORITY_KIND,
    OiFundingAuthorizationError,
    OiFundingCorruptError,
    OiFundingIdentityError,
    OiFundingLookaheadError,
    OiFundingMissingError,
    OiFundingSupportError,
    assert_no_lookahead,
    assert_outcome_access_closed,
    bind_snapshot_to_tracked_authority,
    build_snapshot_identity,
    classify_failure,
    crowding_inputs_ready,
    eligible_decision_keys,
    funding_object_name,
    funding_urls,
    missing_oi_intervals,
    mixed_batch_identity,
    normalize_funding_rows,
    normalize_oi_rows,
    observation_usable_at,
    oi_object_name,
    pair_same_support,
    refuse_reclassify_corrupt_as_missing,
    require_frozen_source,
    require_normalization_identity,
    select_source,
    sha256_hex,
    verify_source_checksum,
)

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]
LIB_PATH = REPO / "scripts" / "research" / "binance_um_oi_funding_v0_contract_lib.py"
FREEZE_JSON = REPO / "docs" / "research" / "B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json"
MANIFEST = REPO / "docs" / "manifests" / "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml"
INVENTORY = REPO / "docs" / "research" / "V2_FORMULATION_INVENTORY.md"
B2_05_PREREG = REPO / "docs" / "research" / "B2_05_FLOW_ABSORPTION_PREREG.md"


def _identity(**overrides):
    payload = dict(FROZEN_SOURCE)
    payload.update(overrides)
    return payload


def _funding_csv(rows: list[tuple[int, str, str]]) -> str:
    lines = [",".join(FUNDING_HEADER)]
    for calc, hours, rate in rows:
        lines.append(f"{calc},{hours},{rate}")
    return "\n".join(lines) + "\n"


def _oi_csv(rows: list[tuple[str, str, str]]) -> str:
    lines = [",".join(OI_HEADER)]
    for create_time, symbol, oi in rows:
        lines.append(
            ",".join(
                [
                    create_time,
                    symbol,
                    oi,
                    "100.0",
                    "1.0",
                    "1.0",
                    "1.0",
                    "1.0",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _dt(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")


SETTLEMENT_0 = 1577836800000  # 2020-01-01T00:00:00Z
SETTLEMENT_8 = SETTLEMENT_0 + FUNDING_PERIOD_MS
DAY0 = 1598918400000  # 2020-09-01T00:00:00Z


def _one_oi_day_csv(day_start_ms: int = DAY0, *, skip: set[int] | None = None) -> str:
    skip = skip or set()
    rows = []
    for i in range(288):
        start = day_start_ms + i * OI_PERIOD_MS
        if start in skip:
            continue
        rows.append((_dt(start), "BTCUSDT", f"{39000 + i}.0"))
    return _oi_csv(rows)


def test_1_wrong_venue_is_identity_failure():
    with pytest.raises(OiFundingIdentityError, match="venue"):
        require_frozen_source(_identity(venue="Bybit"))


def test_2_wrong_symbol_is_identity_failure():
    with pytest.raises(OiFundingIdentityError, match="symbol"):
        require_frozen_source(_identity(symbol="ETHUSDT"))
    csv_text = _oi_csv([(_dt(DAY0), "ETHUSDT", "1.0")])
    with pytest.raises(OiFundingIdentityError, match="symbol"):
        normalize_oi_rows(csv_text, identity=_identity())


def test_3_wrong_contract_type_is_identity_failure():
    with pytest.raises(OiFundingIdentityError, match="contract"):
        require_frozen_source(_identity(contract_type="QUARTERLY"))


def test_4_wrong_oi_units_or_definition_fail():
    with pytest.raises(OiFundingIdentityError, match="oi_units"):
        require_frozen_source(_identity(oi_units="USDT"))
    with pytest.raises(OiFundingIdentityError, match="oi_definition"):
        require_frozen_source(_identity(oi_definition="SUM_OPEN_INTEREST_VALUE_USDT"))
    csv_text = _one_oi_day_csv()
    with pytest.raises(OiFundingIdentityError, match="OI series"):
        normalize_oi_rows(
            csv_text,
            identity=_identity(),
            oi_series_field="sum_open_interest_value",
        )


def test_5_wrong_funding_definition_fail():
    with pytest.raises(OiFundingIdentityError, match="funding_definition"):
        require_frozen_source(
            _identity(funding_definition="PREDICTED_NEXT_FUNDING_RATE")
        )
    csv_text = _funding_csv([(SETTLEMENT_0, "4", "0.0001")])
    with pytest.raises(OiFundingCorruptError, match="funding interval"):
        normalize_funding_rows(csv_text, identity=_identity())


def test_6_future_available_at_is_lookahead():
    with pytest.raises(OiFundingLookaheadError, match="after decision"):
        assert_no_lookahead(decision_t_ms=100, available_at_ms=101)
    row = {"available_at_ms": SETTLEMENT_8, "published_at_ms": SETTLEMENT_8}
    assert observation_usable_at(record=row, decision_t_ms=SETTLEMENT_8) is True
    assert observation_usable_at(record=row, decision_t_ms=SETTLEMENT_8 - 1) is False


def test_7_missing_availability_metadata_fails_closed():
    with pytest.raises(OiFundingLookaheadError, match="missing availability"):
        observation_usable_at(record={"last_funding_rate": "0.1"}, decision_t_ms=1)


def test_8_conflicting_duplicate_timestamp_is_corrupt():
    funding = _funding_csv(
        [
            (SETTLEMENT_0, "8", "0.0001"),
            (SETTLEMENT_0, "8", "0.0002"),
        ]
    )
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate funding"):
        normalize_funding_rows(funding, identity=_identity())
    oi = _oi_csv(
        [
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0), "BTCUSDT", "11.0"),
        ]
    )
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate OI"):
        normalize_oi_rows(oi, identity=_identity())


def test_identical_oi_duplicates_collapse_and_are_not_missing():
    oi = _oi_csv(
        [
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0 + OI_PERIOD_MS), "BTCUSDT", "11.0"),
        ]
    )
    rows = normalize_oi_rows(oi, identity=_identity())
    assert len(rows) == 2
    assert rows[0].identical_duplicate_collapsed is True
    assert rows[0].sum_open_interest == "10.0"


def test_9_missing_interval_is_missing_not_corrupt():
    csv_text = _one_oi_day_csv(skip={DAY0 + 3 * OI_PERIOD_MS})
    rows = normalize_oi_rows(csv_text, identity=_identity())
    missing = missing_oi_intervals(rows, day_yyyy_mm_dd="2020-09-01")
    assert missing == [DAY0 + 3 * OI_PERIOD_MS]
    assert classify_failure(OiFundingMissingError("gap")) == "MISSING"


def test_10_corrupted_checksum_is_corrupt():
    payload = b"not-the-archive"
    checksum = f"{'0' * 64}  {funding_object_name('2020-01')}\n"
    with pytest.raises(OiFundingCorruptError, match="checksum mismatch"):
        verify_source_checksum(
            zip_bytes=payload,
            checksum_text=checksum,
            expected_zip_filename=funding_object_name("2020-01"),
        )


def test_11_manifest_substitution_is_forbidden():
    tracked = {
        "dataset_id": DATASET_ID,
        "status": CONTRACT_STATUS,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
        "snapshot_id": "NOT_MATERIALIZED",
    }
    fake = dict(tracked)
    fake["dataset_id"] = "SOME_OTHER_DATASET"
    snapshot = {"snapshot_id": "NOT_MATERIALIZED"}
    with pytest.raises(OiFundingAuthorizationError, match="manifest substitution"):
        bind_snapshot_to_tracked_authority(
            snapshot=snapshot,
            tracked_manifest=tracked,
            claimed_manifest=fake,
        )


def test_12_snapshot_substitution_is_forbidden():
    payload = build_snapshot_identity(
        contract_sha256="a" * 64,
        normalization_source_sha256_hex="b" * 64,
        source_objects=[],
        normalized_objects=[],
        requested_intervals={"funding": "8h", "oi": "5m"},
        retrieval_time_utc="2026-09-07T00:00:00Z",
        row_counts={"funding": 0, "oi": 0},
        first_last_timestamps={},
        provenance_git_commit_sha="c" * 40,
    )
    tracked = {
        "dataset_id": DATASET_ID,
        "status": CONTRACT_STATUS,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
        "snapshot_id": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    }
    with pytest.raises(OiFundingAuthorizationError, match="snapshot substitution"):
        bind_snapshot_to_tracked_authority(
            snapshot=payload,
            tracked_manifest=tracked,
            claimed_snapshot_id=payload["snapshot_id"],
        )


def test_13_mixed_provider_fallback_is_forbidden():
    with pytest.raises(OiFundingIdentityError, match="mixed provider"):
        mixed_batch_identity(
            [
                {"provider": "Binance", "venue": "Binance", "oi_native_granularity": "5m"},
                {"provider": "Bybit", "venue": "Binance", "oi_native_granularity": "5m"},
            ]
        )


def test_14_mixed_timeframe_fallback_is_forbidden():
    with pytest.raises(OiFundingIdentityError, match="mixed timeframe"):
        mixed_batch_identity(
            [
                {
                    "provider": "Binance",
                    "venue": "Binance",
                    "market_type": "USD_M_FUTURES",
                    "contract_type": "PERPETUAL",
                    "symbol": "BTCUSDT",
                    "oi_native_granularity": "5m",
                },
                {
                    "provider": "Binance",
                    "venue": "Binance",
                    "market_type": "USD_M_FUTURES",
                    "contract_type": "PERPETUAL",
                    "symbol": "BTCUSDT",
                    "oi_native_granularity": "1m",
                },
            ]
        )


def test_15_malformed_timestamp_is_corrupt():
    with pytest.raises(OiFundingCorruptError, match="malformed timestamp"):
        normalize_funding_rows(
            _funding_csv([("not-a-time", "8", "0.0001")]),
            identity=_identity(),
        )
    with pytest.raises(OiFundingCorruptError, match="malformed timestamp"):
        normalize_oi_rows(
            _oi_csv([("2020/09/01 00:00:00", "BTCUSDT", "1.0")]),
            identity=_identity(),
        )


def test_16_candidate_baseline_support_mismatch_fails():
    keys = ("e1", "e2")
    with pytest.raises(OiFundingSupportError, match="support mismatch"):
        pair_same_support(
            candidate_keys=("e1",),
            baseline_keys=keys,
            eligible_keys=keys,
        )
    funding = normalize_funding_rows(
        _funding_csv([(DAY0, "8", "0.0001")]),
        identity=_identity(),
    )
    oi = normalize_oi_rows(_one_oi_day_csv(), identity=_identity())
    t_ready = DAY0 + OI_PERIOD_MS
    eligible = eligible_decision_keys(
        candidate_keys=("k1",),
        baseline_keys=("k1",),
        oi_rows=oi,
        funding_rows=funding,
        decision_t_by_key={"k1": t_ready},
        price_legally_available_keys=("k1",),
    )
    paired = pair_same_support(
        candidate_keys=eligible,
        baseline_keys=eligible,
        eligible_keys=eligible,
    )
    assert paired == eligible


def test_17_corrupt_is_not_reclassified_as_missing():
    exc = OiFundingCorruptError("checksum mismatch")
    assert refuse_reclassify_corrupt_as_missing(exc) == "CORRUPT"
    assert classify_failure(exc) != "MISSING"


def test_18_later_backfill_not_visible_before_legal_availability():
    funding = normalize_funding_rows(
        _funding_csv([(SETTLEMENT_0, "8", "0.0001")]),
        identity=_identity(),
        published_at_by_event_ms={SETTLEMENT_0: SETTLEMENT_0 + 60_000},
    )
    row = funding[0]
    record = {
        "available_at_ms": row.available_at_ms,
        "published_at_ms": row.published_at_ms,
        "retrieval_time_ms": SETTLEMENT_0 - 1_000,
    }
    assert observation_usable_at(record=record, decision_t_ms=SETTLEMENT_0) is False
    assert observation_usable_at(
        record=record, decision_t_ms=SETTLEMENT_0 + 60_000
    ) is True


def test_19_runtime_caller_cannot_choose_alternate_source():
    with pytest.raises(OiFundingIdentityError, match="kline-only"):
        select_source({"dataset_id": "CORE_BTC_BINANCE_V0"})
    with pytest.raises(OiFundingIdentityError):
        select_source(_identity(provider="Tardis", venue="Binance"))
    with pytest.raises(OiFundingIdentityError, match="alternate_provider"):
        select_source(_identity(alternate_provider="Bybit"))
    selected = select_source(_identity())
    assert selected == dict(FROZEN_SOURCE)


def test_20_normalization_code_identity_mismatch():
    source = LIB_PATH.read_bytes()
    actual = require_normalization_identity(source_bytes=source, claimed_sha256=sha256_hex(source))
    assert actual == sha256_hex(source)
    with pytest.raises(OiFundingCorruptError, match="normalization code identity"):
        require_normalization_identity(source_bytes=source, claimed_sha256="0" * 64)
    with pytest.raises(OiFundingCorruptError, match="missing normalization"):
        require_normalization_identity(source_bytes=source, claimed_sha256=None)


def test_checksum_happy_path_and_filename_identity():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("BTCUSDT-fundingRate-2020-01.csv", _funding_csv([(SETTLEMENT_0, "8", "0.1")]))
    zip_bytes = buf.getvalue()
    name = funding_object_name("2020-01")
    checksum = f"{sha256_hex(zip_bytes)}  {name}\n"
    assert verify_source_checksum(
        zip_bytes=zip_bytes,
        checksum_text=checksum,
        expected_zip_filename=name,
    ) == "VERIFIED"
    with pytest.raises(OiFundingCorruptError, match="filename identity"):
        verify_source_checksum(
            zip_bytes=zip_bytes,
            checksum_text=f"{sha256_hex(zip_bytes)}  other.zip\n",
            expected_zip_filename=name,
        )


def test_snapshot_id_is_computed_not_self_attested():
    source = LIB_PATH.read_bytes()
    first = build_snapshot_identity(
        contract_sha256="a" * 64,
        normalization_source_sha256_hex=sha256_hex(source),
        source_objects=[{"url": funding_urls("2020-01")[0], "local_sha256": "1" * 64}],
        normalized_objects=[{"path": "canonical/funding.parquet", "sha256": "2" * 64}],
        requested_intervals={"funding_months": ["2020-01"], "oi_days": ["2020-09-01"]},
        retrieval_time_utc="2026-09-07T00:00:00Z",
        row_counts={"funding": 1, "oi": 288},
        first_last_timestamps={"funding": {"first": "2020-01-01T00:00:00Z"}},
        provenance_git_commit_sha="d" * 40,
    )
    second = build_snapshot_identity(
        contract_sha256="a" * 64,
        normalization_source_sha256_hex=sha256_hex(source),
        source_objects=[{"url": funding_urls("2020-01")[0], "local_sha256": "1" * 64}],
        normalized_objects=[{"path": "canonical/funding.parquet", "sha256": "2" * 64}],
        requested_intervals={"funding_months": ["2020-01"], "oi_days": ["2020-09-01"]},
        retrieval_time_utc="2026-09-07T00:00:00Z",
        row_counts={"funding": 1, "oi": 288},
        first_last_timestamps={"funding": {"first": "2020-01-01T00:00:00Z"}},
        provenance_git_commit_sha="d" * 40,
    )
    assert first["snapshot_id"] == second["snapshot_id"]
    assert "snapshot_id" not in first["identity_payload"]
    mutated = build_snapshot_identity(
        contract_sha256="e" * 64,
        normalization_source_sha256_hex=sha256_hex(source),
        source_objects=[{"url": funding_urls("2020-01")[0], "local_sha256": "1" * 64}],
        normalized_objects=[{"path": "canonical/funding.parquet", "sha256": "2" * 64}],
        requested_intervals={"funding_months": ["2020-01"], "oi_days": ["2020-09-01"]},
        retrieval_time_utc="2026-09-07T00:00:00Z",
        row_counts={"funding": 1, "oi": 288},
        first_last_timestamps={"funding": {"first": "2020-01-01T00:00:00Z"}},
        provenance_git_commit_sha="d" * 40,
    )
    assert mutated["snapshot_id"] != first["snapshot_id"]
    tracked = {
        "dataset_id": DATASET_ID,
        "status": CONTRACT_STATUS,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
        "snapshot_id": "NOT_MATERIALIZED",
    }
    assert bind_snapshot_to_tracked_authority(
        snapshot=first,
        tracked_manifest=tracked,
        authority_kind=SNAPSHOT_AUTHORITY_KIND,
    ) == "NOT_MATERIALIZED"
    with pytest.raises(OiFundingAuthorizationError, match="caller-selected"):
        bind_snapshot_to_tracked_authority(
            snapshot=first,
            tracked_manifest=tracked,
            authority_kind="CALLER_RUNTIME_METADATA",
        )


def test_same_support_requires_legally_available_oi_and_funding():
    funding = normalize_funding_rows(
        _funding_csv([(DAY0, "8", "0.0001")]),
        identity=_identity(),
    )
    oi = normalize_oi_rows(_one_oi_day_csv(), identity=_identity())
    too_early = DAY0
    ready = DAY0 + OI_PERIOD_MS
    status_early = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=too_early
    )
    assert status_early["ready"] is False
    status_ready = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=ready
    )
    assert status_ready["ready"] is True
    with pytest.raises(OiFundingSupportError, match="declared identically"):
        eligible_decision_keys(
            candidate_keys=("a", "b"),
            baseline_keys=("a",),
            oi_rows=oi,
            funding_rows=funding,
            decision_t_by_key={"a": ready, "b": ready},
            price_legally_available_keys=("a", "b"),
        )


def test_funding_uses_calc_time_not_snapped_label_for_availability():
    calc = SETTLEMENT_8 + 8
    rows = normalize_funding_rows(
        _funding_csv([(calc, "8", "0.0001")]),
        identity=_identity(),
    )
    assert rows[0].canonical_settlement_ms == SETTLEMENT_8
    assert rows[0].available_at_ms == calc
    assert rows[0].period_end_ms == SETTLEMENT_8
    assert observation_usable_at(
        record={"available_at_ms": rows[0].available_at_ms},
        decision_t_ms=SETTLEMENT_8,
    ) is False
    assert observation_usable_at(
        record={"available_at_ms": rows[0].available_at_ms},
        decision_t_ms=calc,
    ) is True


def test_oi_available_at_is_bar_end_exclusive():
    rows = normalize_oi_rows(_one_oi_day_csv(), identity=_identity())
    assert rows[0].period_start_ms == DAY0
    assert rows[0].available_at_ms == DAY0 + OI_PERIOD_MS
    assert rows[0].oi_native_granularity == "5m"


def test_outcome_access_remains_closed():
    manifest = {
        "research_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
    }
    assert_outcome_access_closed(manifest)
    with pytest.raises(OiFundingAuthorizationError):
        assert_outcome_access_closed({**manifest, "research_authorized": True})
    with pytest.raises(OiFundingAuthorizationError):
        assert_outcome_access_closed({**manifest, "b2_06_evaluator_enabled": True})


def test_freeze_docs_and_inventory_untouched():
    import json

    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["dataset_id"] == DATASET_ID
    assert freeze["availability_semantics_version"] == AVAILABILITY_SEMANTICS_VERSION
    assert freeze["decision"] == "DATA_EXPANSION_FEASIBLE_TO_FREEZE"
    assert freeze["year_2025_opened"] is False
    assert freeze["year_2026_opened"] is False
    assert freeze["scientific_evaluator_implemented"] is False
    freeze_text = FREEZE_JSON.read_text(encoding="utf-8")
    assert DATASET_ID in freeze_text
    assert AVAILABILITY_SEMANTICS_VERSION in freeze_text
    assert "DATA_EXPANSION_FEASIBLE_TO_FREEZE" in freeze_text
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert "research_authorized: false" in manifest
    assert "CONTRACT_FROZEN_NOT_MATERIALIZED" in manifest
    inventory = INVENTORY.read_text(encoding="utf-8")
    assert "B2-06_LEVERAGE_CROWDING" in inventory
    b2_05 = B2_05_PREREG.read_text(encoding="utf-8")
    assert "B2-05_FLOW_ABSORPTION" in b2_05


def test_object_url_identity_is_first_party_binance_vision():
    zip_url, checksum_url = funding_urls("2020-09")
    assert zip_url.endswith("/BTCUSDT-fundingRate-2020-09.zip")
    assert checksum_url.endswith(".CHECKSUM")
    assert "data.binance.vision" in zip_url
    assert oi_object_name("2020-09-01") == "BTCUSDT-metrics-2020-09-01.zip"


def test_staleness_bound_does_not_invent_1m_oi():
    funding = normalize_funding_rows(
        _funding_csv([(DAY0, "8", "0.0001")]),
        identity=_identity(),
    )
    oi = normalize_oi_rows(_one_oi_day_csv(), identity=_identity())[:1]
    first_available = DAY0 + OI_PERIOD_MS
    late = first_available + OI_PERIOD_MS + 1
    status = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=late
    )
    assert status["ready"] is False
    assert status["oi_ready"] is False
    assert FUNDING_MAX_STALENESS_MS == 8 * 60 * 60 * 1000
