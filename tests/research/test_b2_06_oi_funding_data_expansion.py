"""Synthetic adversarial tests for the B2-06 OI/funding data-expansion contract.

No test here downloads Binance history, opens CORE partitions, inspects B2-06
predictive outcomes, or authorizes 2025/2026 windows. Fixtures are local.
"""
from __future__ import annotations

import io
import subprocess
import zipfile
from dataclasses import replace
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
    FUNDING_PUBLICATION_PROVEN_STATUS,
    FUNDING_PUBLICATION_SEMANTICS_STATUS,
    MANIFEST_PATH,
    NORMALIZATION_MODULE,
    OI_DUPLICATE_EQUALITY_RULE,
    OI_HEADER,
    OI_PERIOD_MS,
    SNAPSHOT_AUTHORITY_KIND,
    MATERIALIZED_STATUS,
    MATERIALIZED_UNIT_VERDICT,
    ZIP_MATERIALIZER_FAIL_CLOSED,
    OiFundingAuthorizationError,
    OiFundingCorruptError,
    OiFundingIdentityError,
    OiFundingLookaheadError,
    OiFundingMissingError,
    OiFundingSupportError,
    VerifiedOiFundingGitAuthority,
    assert_funding_legally_consumable,
    assert_no_lookahead,
    assert_outcome_access_closed,
    bind_snapshot_to_tracked_authority,
    build_snapshot_identity,
    classify_failure,
    crowding_inputs_ready,
    eligible_decision_keys,
    expected_funding_settlements_ms,
    expected_oi_period_starts,
    funding_legal_available_at_ms,
    funding_object_name,
    funding_publication_contract_is_proven,
    funding_settlement_denominator,
    funding_urls,
    missing_oi_intervals,
    mixed_batch_identity,
    normalize_funding_rows,
    normalize_oi_rows,
    observation_usable_at,
    oi_object_name,
    oi_urls,
    parse_oi_archive_day,
    pair_same_support,
    refuse_reclassify_corrupt_as_missing,
    reject_caller_asserted_funding_publication,
    require_frozen_source,
    require_normalization_identity,
    select_source,
    sha256_hex,
    validate_archive_zip_members,
    verify_oi_funding_git_authority,
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
FUNDING_OBJ_2020_01 = "BTCUSDT-fundingRate-2020-01.zip"
FUNDING_OBJ_2020_09 = "BTCUSDT-fundingRate-2020-09.zip"
FUNDING_OBJ_2021_05 = "BTCUSDT-fundingRate-2021-05.zip"
OI_OBJ_2020_09_01 = "BTCUSDT-metrics-2020-09-01.zip"
OI_OBJ_2021_05_28 = "BTCUSDT-metrics-2021-05-28.zip"
OI_OBJ_2021_05_31 = "BTCUSDT-metrics-2021-05-31.zip"


def _one_oi_day_csv(day_start_ms: int = DAY0, *, skip: set[int] | None = None) -> str:
    skip = skip or set()
    rows = []
    for i in range(288):
        start = day_start_ms + i * OI_PERIOD_MS
        if start in skip:
            continue
        rows.append((_dt(start), "BTCUSDT", f"{39000 + i}.0"))
    return _oi_csv(rows)


def _norm_funding(csv_text: str, archive_object_name: str = FUNDING_OBJ_2020_01, **kwargs):
    return normalize_funding_rows(
        csv_text,
        identity=_identity(),
        archive_object_name=archive_object_name,
        **kwargs,
    )


def _norm_oi(csv_text: str, archive_object_name: str = OI_OBJ_2020_09_01, **kwargs):
    return normalize_oi_rows(
        csv_text,
        identity=_identity(),
        archive_object_name=archive_object_name,
        **kwargs,
    )


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_blob(root: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{path}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _git_commit(root: Path, message: str) -> str:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=B2-06 Repair",
            "-c",
            "user.email=b206@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            message,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return _git(root, "rev-parse", "HEAD")


def _write_rel(root: Path, rel: str, data: bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _init_authority_repo(
    root: Path,
    *,
    include_manifest: bool = True,
    include_norm: bool = True,
    manifest_bytes: bytes | None = None,
    norm_bytes: bytes | None = None,
) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if include_manifest:
        _write_rel(root, MANIFEST_PATH, manifest_bytes or MANIFEST.read_bytes())
    if include_norm:
        _write_rel(root, NORMALIZATION_MODULE, norm_bytes or LIB_PATH.read_bytes())
    _git(root, "add", "-A")
    sha = _git_commit(root, "authority")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    return {"sha": sha, "tree": tree}


def test_1_wrong_venue_is_identity_failure():
    with pytest.raises(OiFundingIdentityError, match="venue"):
        require_frozen_source(_identity(venue="Bybit"))


def test_2_wrong_symbol_is_identity_failure():
    with pytest.raises(OiFundingIdentityError, match="symbol"):
        require_frozen_source(_identity(symbol="ETHUSDT"))
    csv_text = _oi_csv([(_dt(DAY0), "ETHUSDT", "1.0")])
    with pytest.raises(OiFundingIdentityError, match="symbol"):
        _norm_oi(csv_text)


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
            archive_object_name=OI_OBJ_2020_09_01,
            oi_series_field="sum_open_interest_value",
        )


def test_5_wrong_funding_definition_fail():
    with pytest.raises(OiFundingIdentityError, match="funding_definition"):
        require_frozen_source(
            _identity(funding_definition="PREDICTED_NEXT_FUNDING_RATE")
        )
    csv_text = _funding_csv([(SETTLEMENT_0, "4", "0.0001")])
    with pytest.raises(OiFundingCorruptError, match="funding interval"):
        _norm_funding(csv_text)


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
        _norm_funding(funding)
    oi = _oi_csv(
        [
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0), "BTCUSDT", "11.0"),
        ]
    )
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate OI"):
        _norm_oi(oi)


def test_identical_oi_duplicates_collapse_and_are_not_missing():
    oi = _oi_csv(
        [
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0), "BTCUSDT", "10.0"),
            (_dt(DAY0 + OI_PERIOD_MS), "BTCUSDT", "11.0"),
        ]
    )
    rows = _norm_oi(oi)
    assert len(rows) == 2
    assert rows[0].identical_duplicate_collapsed is True
    assert rows[0].sum_open_interest == "10.0"


def test_9_missing_interval_is_missing_not_corrupt():
    csv_text = _one_oi_day_csv(skip={DAY0 + 3 * OI_PERIOD_MS})
    rows = _norm_oi(csv_text)
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


def test_11_fabricated_manifest_mapping_is_not_git_authority():
    tracked = {
        "dataset_id": DATASET_ID,
        "status": CONTRACT_STATUS,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
        "snapshot_id": "NOT_MATERIALIZED",
    }
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        bind_snapshot_to_tracked_authority(
            git_authority=object(),  # type: ignore[arg-type]
            tracked_manifest=tracked,
            claimed_manifest=dict(tracked),
        )


def test_12_caller_snapshot_id_substitution_is_forbidden_without_git_authority():
    with pytest.raises(OiFundingAuthorizationError, match="verify_oi_funding_git_authority proof"):
        bind_snapshot_to_tracked_authority(
            git_authority=object(),  # type: ignore[arg-type]
            claimed_snapshot_id="a" * 64,
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
        _norm_funding(_funding_csv([("not-a-time", "8", "0.0001")]))
    with pytest.raises(OiFundingCorruptError, match="malformed timestamp"):
        _norm_oi(_oi_csv([("2020/09/01 00:00:00", "BTCUSDT", "1.0")]))


def test_16_candidate_baseline_support_mismatch_fails():
    keys = ("e1", "e2")
    with pytest.raises(OiFundingSupportError, match="support mismatch"):
        pair_same_support(
            candidate_keys=("e1",),
            baseline_keys=keys,
            eligible_keys=keys,
        )
    funding = _norm_funding(
        _funding_csv([(DAY0, "8", "0.0001")]),
        archive_object_name=FUNDING_OBJ_2020_09,
    )
    oi = _norm_oi(_one_oi_day_csv())
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
    assert eligible == ()


def test_17_corrupt_is_not_reclassified_as_missing():
    exc = OiFundingCorruptError("checksum mismatch")
    assert refuse_reclassify_corrupt_as_missing(exc) == "CORRUPT"
    assert classify_failure(exc) != "MISSING"


def test_18_calc_time_and_caller_published_at_cannot_authorize_funding():
    with pytest.raises(OiFundingAuthorizationError, match="published_at"):
        _norm_funding(
            _funding_csv([(SETTLEMENT_0, "8", "0.0001")]),
            published_at_by_event_ms={SETTLEMENT_0: SETTLEMENT_0 + 60_000},
        )
    rows = _norm_funding(_funding_csv([(SETTLEMENT_0, "8", "0.0001")]))
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        assert_funding_legally_consumable(rows[0], SETTLEMENT_0)
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        funding_legal_available_at_ms(SETTLEMENT_0)
    with pytest.raises(OiFundingLookaheadError, match="calc_time"):
        observation_usable_at(
            record={
                "available_at_ms": SETTLEMENT_0,
                "publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
                "funding_definition": "SETTLED_LAST_FUNDING_RATE",
            },
            decision_t_ms=SETTLEMENT_0,
        )


def test_19_runtime_caller_cannot_choose_alternate_source():
    with pytest.raises(OiFundingIdentityError, match="kline-only"):
        select_source({"dataset_id": "CORE_BTC_BINANCE_V0"})
    with pytest.raises(OiFundingIdentityError):
        select_source(_identity(provider="Tardis", venue="Binance"))
    with pytest.raises(OiFundingIdentityError, match="alternate_provider"):
        select_source(_identity(alternate_provider="Bybit"))
    selected = select_source(_identity())
    assert selected == dict(FROZEN_SOURCE)


def test_20_caller_normalization_bytes_are_not_authority():
    source = LIB_PATH.read_bytes()
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        require_normalization_identity(
            git_authority=object(),  # type: ignore[arg-type]
            source_bytes=source,
            claimed_sha256=sha256_hex(source),
        )


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
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        bind_snapshot_to_tracked_authority(
            git_authority=object(),  # type: ignore[arg-type]
            snapshot=first,
            tracked_manifest={"dataset_id": DATASET_ID, "snapshot_id": "NOT_MATERIALIZED"},
            authority_kind=SNAPSHOT_AUTHORITY_KIND,
        )
    with pytest.raises(OiFundingAuthorizationError, match="caller-selected"):
        bind_snapshot_to_tracked_authority(
            git_authority=object(),  # type: ignore[arg-type]
            authority_kind="CALLER_RUNTIME_METADATA",
        )


def test_same_support_requires_legally_available_oi_and_funding():
    funding = _norm_funding(
        _funding_csv([(DAY0, "8", "0.0001")]),
        archive_object_name=FUNDING_OBJ_2020_09,
    )
    oi = _norm_oi(_one_oi_day_csv())
    too_early = DAY0
    ready = DAY0 + OI_PERIOD_MS
    status_early = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=too_early
    )
    assert status_early["ready"] is False
    assert status_early["funding_ready"] is False
    status_oi_ok = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=ready
    )
    assert status_oi_ok["oi_ready"] is True
    assert status_oi_ok["funding_ready"] is False
    assert status_oi_ok["ready"] is False
    assert status_oi_ok["reason"] == FUNDING_PUBLICATION_SEMANTICS_STATUS
    assert status_oi_ok["funding_block"] == FUNDING_PUBLICATION_SEMANTICS_STATUS
    with pytest.raises(OiFundingSupportError, match="declared identically"):
        eligible_decision_keys(
            candidate_keys=("a", "b"),
            baseline_keys=("a",),
            oi_rows=oi,
            funding_rows=funding,
            decision_t_by_key={"a": ready, "b": ready},
            price_legally_available_keys=("a", "b"),
        )


def test_funding_calc_time_is_source_event_time_not_legal_available_at():
    calc = SETTLEMENT_8 + 8
    rows = _norm_funding(_funding_csv([(calc, "8", "0.0001")]))
    assert rows[0].canonical_settlement_ms == SETTLEMENT_8
    assert rows[0].source_event_time_ms == calc
    assert rows[0].period_end_ms == SETTLEMENT_8
    assert rows[0].legal_available_at_ms is None
    assert rows[0].publication_semantics_status == FUNDING_PUBLICATION_SEMANTICS_STATUS
    assert not hasattr(rows[0], "available_at_ms")
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        assert_funding_legally_consumable(rows[0], calc)
    with pytest.raises(OiFundingLookaheadError, match="calc_time"):
        observation_usable_at(
            record={
                "available_at_ms": calc,
                "publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
                "funding_definition": "SETTLED_LAST_FUNDING_RATE",
            },
            decision_t_ms=calc,
        )


def test_future_oi_rejected_and_future_funding_unusable():
    oi = _norm_oi(_one_oi_day_csv())[:1]
    too_early = oi[0].period_start_ms
    assert observation_usable_at(
        record={"available_at_ms": oi[0].available_at_ms},
        decision_t_ms=too_early,
    ) is False
    with pytest.raises(OiFundingLookaheadError, match="after decision"):
        assert_no_lookahead(
            decision_t_ms=too_early,
            available_at_ms=oi[0].available_at_ms,
        )
    funding = _norm_funding(_funding_csv([(SETTLEMENT_0, "8", "0.0001")]))
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        assert_funding_legally_consumable(funding[0], SETTLEMENT_0 - 1)
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        assert_funding_legally_consumable(funding[0], SETTLEMENT_0)


def test_oi_available_at_is_bar_end_exclusive():
    rows = _norm_oi(_one_oi_day_csv())
    assert rows[0].period_start_ms == DAY0
    assert rows[0].available_at_ms == DAY0 + OI_PERIOD_MS
    assert rows[0].oi_native_granularity == "5m"


def test_caller_cannot_mark_funding_publication_proven():
    rows = _norm_funding(_funding_csv([(SETTLEMENT_0, "8", "0.0001")]))
    spoofed = replace(
        rows[0],
        publication_semantics_status=FUNDING_PUBLICATION_PROVEN_STATUS,
        legal_available_at_ms=SETTLEMENT_0,
    )
    with pytest.raises(OiFundingAuthorizationError, match="cannot mark funding"):
        crowding_inputs_ready(
            oi_rows=_norm_oi(_one_oi_day_csv())[:1],
            funding_rows=[spoofed],
            decision_t_ms=DAY0 + OI_PERIOD_MS,
        )


def test_forged_normalized_funding_row_cannot_self_attest_publication():
    assert funding_publication_contract_is_proven() is False
    honest = _norm_funding(_funding_csv([(SETTLEMENT_0, "8", "0.0001")]))[0]
    oi = _norm_oi(_one_oi_day_csv())
    ready_t = DAY0 + OI_PERIOD_MS

    proven = replace(
        honest,
        publication_semantics_status=FUNDING_PUBLICATION_PROVEN_STATUS,
        legal_available_at_ms=SETTLEMENT_0,
    )
    with pytest.raises(OiFundingAuthorizationError, match="cannot mark funding"):
        assert_funding_legally_consumable(proven, SETTLEMENT_0)
    with pytest.raises(OiFundingAuthorizationError, match="cannot mark funding"):
        reject_caller_asserted_funding_publication(proven)

    legal_only = replace(honest, legal_available_at_ms=SETTLEMENT_0)
    with pytest.raises(OiFundingAuthorizationError, match="cannot supply funding legal_available_at"):
        assert_funding_legally_consumable(legal_only, SETTLEMENT_0)
    with pytest.raises(OiFundingAuthorizationError, match="cannot supply funding legal_available_at"):
        crowding_inputs_ready(
            oi_rows=oi[:1], funding_rows=[legal_only], decision_t_ms=ready_t
        )

    published = type(
        "ForgedFunding",
        (),
        {
            "publication_semantics_status": FUNDING_PUBLICATION_SEMANTICS_STATUS,
            "legal_available_at_ms": None,
            "published_at_ms": SETTLEMENT_0,
            "funding_definition": honest.funding_definition,
        },
    )()
    with pytest.raises(OiFundingAuthorizationError, match="cannot supply funding published_at"):
        assert_funding_legally_consumable(published, SETTLEMENT_0)

    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        assert_funding_legally_consumable(honest, SETTLEMENT_0)
    with pytest.raises(OiFundingLookaheadError, match="FUNDING_PUBLICATION_LATENCY_UNPROVEN"):
        funding_legal_available_at_ms(honest.source_event_time_ms)
    with pytest.raises(OiFundingLookaheadError, match="calc_time"):
        observation_usable_at(
            record={
                "available_at_ms": SETTLEMENT_0,
                "publication_semantics_status": FUNDING_PUBLICATION_PROVEN_STATUS,
                "funding_definition": "SETTLED_LAST_FUNDING_RATE",
                "legal_available_at_ms": SETTLEMENT_0,
                "published_at_ms": SETTLEMENT_0,
            },
            decision_t_ms=SETTLEMENT_0,
        )

    status = crowding_inputs_ready(
        oi_rows=oi, funding_rows=[honest], decision_t_ms=ready_t
    )
    assert status["ready"] is False
    assert status["oi_ready"] is True
    assert status["funding_ready"] is False
    assert status["reason"] == FUNDING_PUBLICATION_SEMANTICS_STATUS
    assert status["funding_block"] == FUNDING_PUBLICATION_SEMANTICS_STATUS

    freeze = {
        "research_authorized": False,
        "outcome_access_authorized": False,
        "b2_06_evaluator_enabled": False,
        "snapshot_id": "NOT_MATERIALIZED",
    }
    assert_outcome_access_closed(freeze)
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert "research_authorized: false" in manifest
    assert "b2_06_evaluator_enabled: false" in manifest
    assert "FUNDING_PUBLICATION_LATENCY_UNPROVEN" in manifest
    assert "research_authorized: true" not in manifest


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
    assert freeze["unit_verdict"] == MATERIALIZED_UNIT_VERDICT
    assert freeze["status"] == MATERIALIZED_STATUS
    assert freeze["funding_publication_semantics_status"] == FUNDING_PUBLICATION_SEMANTICS_STATUS
    assert freeze["funding_calc_time_is_legal_available_at"] is False
    assert freeze["funding"]["caller_constructed_row_cannot_self_attest_publication"] is True
    assert freeze["snapshot_id"] == "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
    assert freeze["snapshot_manifest_sha256"] == "bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e"
    assert freeze["object_ledger_sha256"] == "521d42a471cc5fec74d808e8a4a3ea0078c87342b801df5dbf3836b4b69b4296"
    assert freeze["quality_report_sha256"] == "a6b46df8350871bd737f02197b201b58d6069b19896d1767bda4c286bdc6c7b3"
    assert freeze["checksum_sidecar_status"] == (
        "TRANSIENT_CORROBORATING_EVIDENCE_NOT_GIT_RETAINED"
    )
    assert freeze["durability_status"] == (
        "IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED"
    )
    assert freeze["raw_zip_bytes_git_retained"] is False
    assert freeze["normalized_jsonl_bytes_git_retained"] is False
    assert freeze["current_local_recoverability_claimed"] is False
    assert freeze["snapshot_materialized"] is True
    assert freeze["research_authorized"] is False
    assert freeze["year_2025_opened"] is False
    assert freeze["year_2026_opened"] is False
    assert freeze["scientific_evaluator_implemented"] is False
    freeze_text = FREEZE_JSON.read_text(encoding="utf-8")
    assert "available_at\": \"calc_time" not in freeze_text
    assert "zero-latency" not in freeze_text.lower()
    assert DATASET_ID in freeze_text
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert "research_authorized: false" in manifest
    assert MATERIALIZED_STATUS in manifest
    assert "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33" in manifest
    assert "521d42a471cc5fec74d808e8a4a3ea0078c87342b801df5dbf3836b4b69b4296" in manifest
    assert "a6b46df8350871bd737f02197b201b58d6069b19896d1767bda4c286bdc6c7b3" in manifest
    assert "object_ledger_sha256:" in manifest
    assert "quality_report_sha256:" in manifest
    assert "EXACT_GIT_COMMIT_TREE_OBJECT_AUTHORITY" in manifest
    assert "FUNDING_PUBLICATION_LATENCY_UNPROVEN" in manifest
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


def test_impossible_oi_calendar_dates_are_corrupt_not_valueerror():
    leap = expected_oi_period_starts("2024-02-29")
    assert len(leap) == 288
    assert leap[0] == int(datetime(2024, 2, 29, tzinfo=UTC).timestamp() * 1000)
    assert oi_object_name("2024-02-29") == "BTCUSDT-metrics-2024-02-29.zip"
    assert parse_oi_archive_day("BTCUSDT-metrics-2024-02-29.zip") == "2024-02-29"
    zip_url, checksum_url = oi_urls("2024-02-29")
    assert zip_url.endswith("/BTCUSDT-metrics-2024-02-29.zip")
    assert checksum_url.endswith(".CHECKSUM")

    invalid_days = (
        "0000-01-01",
        "2023-02-29",
        "2024-02-30",
        "2024-04-31",
        "2024-13-01",
        "2024-00-10",
        "2024-01-00",
        "2024-01-32",
    )
    for day in invalid_days:
        for helper in (expected_oi_period_starts, oi_object_name, oi_urls):
            with pytest.raises(OiFundingCorruptError) as caught:
                helper(day)
            assert type(caught.value) is OiFundingCorruptError
            assert classify_failure(caught.value) == "CORRUPT"
        with pytest.raises(OiFundingCorruptError) as named:
            parse_oi_archive_day(f"BTCUSDT-metrics-{day}.zip")
        assert type(named.value) is OiFundingCorruptError
        assert classify_failure(named.value) == "CORRUPT"


def test_git_commit_fixture_isolates_signing_and_hooks():
    import inspect

    source = inspect.getsource(_git_commit)
    assert "commit.gpgsign=false" in source
    assert "core.hooksPath=/dev/null" in source


def test_staleness_bound_does_not_invent_1m_oi():
    funding = _norm_funding(
        _funding_csv([(DAY0, "8", "0.0001")]),
        archive_object_name=FUNDING_OBJ_2020_09,
    )
    oi = _norm_oi(_one_oi_day_csv())[:1]
    first_available = DAY0 + OI_PERIOD_MS
    late = first_available + OI_PERIOD_MS + 1
    status = crowding_inputs_ready(
        oi_rows=oi, funding_rows=funding, decision_t_ms=late
    )
    assert status["ready"] is False
    assert status["oi_ready"] is False
    assert FUNDING_MAX_STALENESS_MS == 8 * 60 * 60 * 1000


def test_oi_row_outside_requested_object_day_is_corrupt():
    inside = _dt(int(datetime(2021, 5, 28, tzinfo=UTC).timestamp() * 1000))
    previous = _dt(int(datetime(2021, 5, 27, tzinfo=UTC).timestamp() * 1000))
    next_day = _dt(int(datetime(2021, 5, 29, tzinfo=UTC).timestamp() * 1000))
    ok = _norm_oi(
        _oi_csv([(inside, "BTCUSDT", "1.0")]),
        archive_object_name=OI_OBJ_2021_05_28,
    )
    assert ok[0].archive_object_name == OI_OBJ_2021_05_28
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _norm_oi(
            _oi_csv([(previous, "BTCUSDT", "1.0")]),
            archive_object_name=OI_OBJ_2021_05_28,
        )
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _norm_oi(
            _oi_csv([(next_day, "BTCUSDT", "1.0")]),
            archive_object_name=OI_OBJ_2021_05_28,
        )


def test_oi_midnight_month_end_belongs_to_next_object():
    may31_last = _dt(int(datetime(2021, 5, 31, 23, 55, tzinfo=UTC).timestamp() * 1000))
    june1 = _dt(int(datetime(2021, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000))
    rows = _norm_oi(
        _oi_csv([(may31_last, "BTCUSDT", "1.0")]),
        archive_object_name=OI_OBJ_2021_05_31,
    )
    assert rows[0].period_start_ms == int(
        datetime(2021, 5, 31, 23, 55, tzinfo=UTC).timestamp() * 1000
    )
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _norm_oi(
            _oi_csv([(june1, "BTCUSDT", "1.0")]),
            archive_object_name=OI_OBJ_2021_05_31,
        )


def test_funding_row_outside_requested_object_month_is_corrupt():
    may_last = int(datetime(2021, 5, 31, 16, 0, tzinfo=UTC).timestamp() * 1000)
    june_first = int(datetime(2021, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    april_last = int(datetime(2021, 4, 30, 16, 0, tzinfo=UTC).timestamp() * 1000)
    rows = _norm_funding(
        _funding_csv([(may_last, "8", "0.0001")]),
        archive_object_name=FUNDING_OBJ_2021_05,
    )
    assert rows[0].canonical_settlement_ms == may_last
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _norm_funding(
            _funding_csv([(june_first, "8", "0.0001")]),
            archive_object_name=FUNDING_OBJ_2021_05,
        )
    with pytest.raises(OiFundingCorruptError, match="outside requested"):
        _norm_funding(
            _funding_csv([(april_last, "8", "0.0001")]),
            archive_object_name=FUNDING_OBJ_2021_05,
        )


def test_funding_missing_settlement_is_enumerated_not_filled():
    expected = expected_funding_settlements_ms("2020-01")
    assert expected[0] == SETTLEMENT_0
    assert expected[-1] == int(datetime(2020, 1, 31, 16, 0, tzinfo=UTC).timestamp() * 1000)
    assert len(expected) == 31 * 3
    present_ts = expected[:2]
    rows = _norm_funding(
        _funding_csv([(ts, "8", "0.0001") for ts in present_ts])
    )
    denom = funding_settlement_denominator(rows, year_month="2020-01")
    assert denom["present_valid_settlements"] == present_ts
    assert denom["missing_settlements"][0] == expected[2]
    assert denom["gap_count"] == len(expected) - 2
    assert denom["gap_ranges"][0][0] == expected[2]
    assert classify_failure(OiFundingMissingError("missing settlement")) == "MISSING"


def test_funding_conflicting_duplicate_remains_corrupt_in_denominator_path():
    csv_text = _funding_csv(
        [
            (SETTLEMENT_0, "8", "0.0001"),
            (SETTLEMENT_0, "8", "0.0002"),
        ]
    )
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate funding"):
        _norm_funding(csv_text)


def test_oi_duplicate_equality_is_entire_frozen_raw_row():
    assert OI_DUPLICATE_EQUALITY_RULE == "ENTIRE_FROZEN_RAW_ROW"
    create = _dt(DAY0)
    identical = ",".join(OI_HEADER) + "\n"
    identical += ",".join([create, "BTCUSDT", "10.0", "100.0", "1.0", "1.0", "1.0", "1.0"]) + "\n"
    identical += ",".join([create, "BTCUSDT", "10.0", "100.0", "1.0", "1.0", "1.0", "1.0"]) + "\n"
    collapsed = _norm_oi(identical)
    assert len(collapsed) == 1
    assert collapsed[0].identical_duplicate_collapsed is True
    assert collapsed[0].duplicate_equality_rule == OI_DUPLICATE_EQUALITY_RULE
    mixed = ",".join(OI_HEADER) + "\n"
    mixed += ",".join([create, "BTCUSDT", "10.0", "100.0", "1.0", "1.0", "1.0", "1.0"]) + "\n"
    mixed += ",".join([create, "BTCUSDT", "10.0", "999.0", "1.0", "1.0", "1.0", "1.0"]) + "\n"
    with pytest.raises(OiFundingCorruptError, match="conflicting duplicate OI"):
        _norm_oi(mixed)


def test_zip_member_integrity_fail_closed():
    assert "path traversal" in ZIP_MATERIALIZER_FAIL_CLOSED
    csv_name = "BTCUSDT-fundingRate-2020-01.csv"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(csv_name, _funding_csv([(SETTLEMENT_0, "8", "0.1")]))
    assert validate_archive_zip_members(buf.getvalue(), expected_member_name=csv_name)
    extra = io.BytesIO()
    with zipfile.ZipFile(extra, "w") as zf:
        zf.writestr(csv_name, "a,b,c\n")
        zf.writestr("hidden.csv", "nope\n")
    with pytest.raises(OiFundingCorruptError, match="exactly one CSV"):
        validate_archive_zip_members(extra.getvalue(), expected_member_name=csv_name)
    traversal = io.BytesIO()
    with zipfile.ZipFile(traversal, "w") as zf:
        zf.writestr("../" + csv_name, "a,b,c\n")
    with pytest.raises(OiFundingCorruptError, match="traversal"):
        validate_archive_zip_members(traversal.getvalue(), expected_member_name=csv_name)
    unexpected = io.BytesIO()
    with zipfile.ZipFile(unexpected, "w") as zf:
        zf.writestr("other.csv", "a,b,c\n")
    with pytest.raises(OiFundingCorruptError, match="unexpected ZIP member"):
        validate_archive_zip_members(unexpected.getvalue(), expected_member_name=csv_name)


def test_verified_git_authority_cannot_be_fabricated():
    with pytest.raises(OiFundingAuthorizationError, match="must be created by"):
        VerifiedOiFundingGitAuthority(
            repo_root=REPO,
            authority_commit_sha="a" * 40,
            authority_tree_sha="b" * 40,
            manifest_git_path=MANIFEST_PATH,
            normalization_git_path=NORMALIZATION_MODULE,
            manifest={},
            normalization_source_sha256="c" * 64,
            code_freeze=object(),  # type: ignore[arg-type]
        )


def test_exact_git_commit_manifest_and_normalization_accepted(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    authority = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
        manifest_git_path=MANIFEST_PATH,
        normalization_git_path=NORMALIZATION_MODULE,
    )
    git_norm = sha256_hex(_git_blob(repo, ids["sha"], NORMALIZATION_MODULE))
    assert authority.normalization_source_sha256 == git_norm
    bound = bind_snapshot_to_tracked_authority(git_authority=authority)
    assert bound == authority.manifest.get("snapshot_id")
    assert require_normalization_identity(
        git_authority=authority,
        claimed_sha256=git_norm,
    ) == git_norm


def test_manifest_never_committed_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo, include_manifest=False)
    with pytest.raises(OiFundingAuthorizationError, match="absent from commit tree"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
        )


def test_manifest_committed_in_another_commit_only_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo, include_manifest=False)
    first_sha, first_tree = ids["sha"], ids["tree"]
    _write_rel(repo, MANIFEST_PATH, MANIFEST.read_bytes())
    _git(repo, "add", MANIFEST_PATH)
    later_sha = _git_commit(repo, "add manifest")
    _git(repo, "checkout", first_sha)
    assert later_sha != first_sha
    with pytest.raises(OiFundingAuthorizationError, match="absent from commit tree"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=first_sha,
            authority_tree_sha=first_tree,
        )


def test_wrong_commit_sha_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    other = "0" * 40
    with pytest.raises(OiFundingAuthorizationError, match="HEAD mismatch"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=other,
            authority_tree_sha=ids["tree"],
        )


def test_wrong_tree_sha_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    with pytest.raises(OiFundingAuthorizationError, match="authority tree mismatch"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha="0" * 40,
        )


def test_dirty_working_tree_same_path_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    (repo / MANIFEST_PATH).write_text(
        (repo / MANIFEST_PATH).read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    with pytest.raises(OiFundingAuthorizationError, match="not clean"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
        )


def test_skip_worktree_modified_bytes_are_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    _git(repo, "update-index", "--skip-worktree", MANIFEST_PATH)
    (repo / MANIFEST_PATH).write_text(
        (repo / MANIFEST_PATH).read_text(encoding="utf-8").replace(
            "research_authorized: false", "research_authorized: true"
        ),
        encoding="utf-8",
    )
    assert _git(repo, "status", "--porcelain") == ""
    with pytest.raises(OiFundingAuthorizationError, match="skip-worktree"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
        )


def test_assume_unchanged_modified_bytes_are_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    _git(repo, "update-index", "--assume-unchanged", MANIFEST_PATH)
    (repo / MANIFEST_PATH).write_text(
        (repo / MANIFEST_PATH).read_text(encoding="utf-8").replace(
            "research_authorized: false", "research_authorized: true"
        ),
        encoding="utf-8",
    )
    assert _git(repo, "status", "--porcelain") == ""
    with pytest.raises(OiFundingAuthorizationError, match="assume-unchanged"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
        )


def test_caller_fabricated_manifest_mapping_rejected_even_with_git_proof(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    authority = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
    )
    fake = dict(authority.manifest)
    fake["research_authorized"] = True
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        bind_snapshot_to_tracked_authority(
            git_authority=authority,
            tracked_manifest=fake,
            claimed_manifest=fake,
        )


def test_caller_fabricated_normalization_bytes_rejected_with_git_proof(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    authority = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
    )
    fake = b"print('not the frozen module')\n"
    with pytest.raises(OiFundingAuthorizationError, match="not Git authority"):
        require_normalization_identity(
            git_authority=authority,
            source_bytes=fake,
            claimed_sha256=sha256_hex(fake),
        )


def test_normalization_blob_from_wrong_commit_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    original = LIB_PATH.read_bytes()
    ids = _init_authority_repo(repo, norm_bytes=original)
    first_sha, first_tree = ids["sha"], ids["tree"]
    first_norm_sha = sha256_hex(original)
    _write_rel(repo, NORMALIZATION_MODULE, original + b"\n# other commit\n")
    _git(repo, "add", NORMALIZATION_MODULE)
    later_sha = _git_commit(repo, "change normalization")
    later_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    later = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=later_sha,
        authority_tree_sha=later_tree,
    )
    with pytest.raises(OiFundingCorruptError, match="normalization code identity mismatch"):
        require_normalization_identity(
            git_authority=later,
            claimed_sha256=first_norm_sha,
        )
    _git(repo, "checkout", first_sha)
    with pytest.raises(OiFundingAuthorizationError, match="HEAD mismatch"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=later_sha,
            authority_tree_sha=later_tree,
        )
    first = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=first_sha,
        authority_tree_sha=first_tree,
    )
    assert first.normalization_source_sha256 == first_norm_sha


def test_claimed_snapshot_id_substitution_rejected_with_git_proof(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    authority = verify_oi_funding_git_authority(
        repo_root=repo,
        authority_commit_sha=ids["sha"],
        authority_tree_sha=ids["tree"],
    )
    with pytest.raises(
        OiFundingAuthorizationError,
        match="caller-chosen snapshot_id|snapshot-id tampering",
    ):
        bind_snapshot_to_tracked_authority(
            git_authority=authority,
            claimed_snapshot_id="a" * 64,
        )
    computed = build_snapshot_identity(
        contract_sha256="a" * 64,
        normalization_source_sha256_hex=authority.normalization_source_sha256,
        source_objects=[{"url": funding_urls("2020-01")[0], "local_sha256": "1" * 64}],
        normalized_objects=[{"path": "canonical/funding.parquet", "sha256": "2" * 64}],
        requested_intervals={"funding_months": ["2020-01"], "oi_days": ["2020-09-01"]},
        retrieval_time_utc="2026-09-07T00:00:00Z",
        row_counts={"funding": 1, "oi": 288},
        first_last_timestamps={"funding": {"first": "2020-01-01T00:00:00Z"}},
        provenance_git_commit_sha=ids["sha"],
    )
    with pytest.raises(
        OiFundingAuthorizationError,
        match="caller-chosen snapshot_id|snapshot-id tampering",
    ):
        bind_snapshot_to_tracked_authority(
            git_authority=authority,
            snapshot=computed,
        )
    bound = bind_snapshot_to_tracked_authority(git_authority=authority)
    assert bound == authority.manifest.get("snapshot_id")


def test_alternate_authority_path_is_rejected(tmp_path: Path):
    repo = tmp_path / "auth"
    ids = _init_authority_repo(repo)
    with pytest.raises(OiFundingAuthorizationError, match="absent from commit tree"):
        verify_oi_funding_git_authority(
            repo_root=repo,
            authority_commit_sha=ids["sha"],
            authority_tree_sha=ids["tree"],
            manifest_git_path="docs/manifests/NOT_THE_FROZEN_MANIFEST.yaml",
        )
