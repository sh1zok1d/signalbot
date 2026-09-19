"""MARKET-05 authorization barrier and protected-OOS fence.

Ordinary import, --help, and pytest must not execute scientific MARKET-05
or surface protected 2025/2026 values.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.research import market05_cross_asset as cli
from scripts.research.core_eth_binance_v0_acceptor_lib import (
    DATASET_ID,
    INVENTORY_SHA256,
    INSTRUMENT,
    expected_csv_member,
    load_bound_inventory,
    snapshot_id_from_payload,
    zip_url_from_checksum_url,
)
from scripts.research.market05_cross_asset_authority import (
    ETH_INVENTORY_SHA256,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    MARKET_05_ARMED,
    MARKET_05_EXECUTION_AUTHORIZED,
    Market05ExecutionNotAuthorized,
    authenticate_frozen_prereg_bytes,
    inspect_market_05_authorization_state,
    refuse_scientific_result_instantiation,
    refuse_unarmed_canonical_execution,
    require_execution_authorized_before_outcome_load,
)
from scripts.research.market05_cross_asset_data import (
    filter_development_open_times,
    load_feature_window,
    load_outcome_window,
    load_real_development_scientific_rows,
    reject_protected_scientific_bars,
)
from scripts.research.market05_cross_asset_lib import (
    Bar,
    FIRST_USABLE_MS,
    PROTECTED_OOS_START_MS,
    Market05ProtectedOOSError,
    feature_open_times,
    outcome_open_times,
    prefix_open_time,
)

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]


def test_prereg_authentication_and_unarmed_flags():
    bound = authenticate_frozen_prereg_bytes()
    assert bound["prereg_md_sha256"] == FROZEN_PREREG_MD_SHA256
    assert bound["prereg_json_sha256"] == FROZEN_PREREG_JSON_SHA256
    assert MARKET_05_ARMED is False
    assert MARKET_05_EXECUTION_AUTHORIZED is False
    state = inspect_market_05_authorization_state()
    assert state["MARKET_05_ARMED"] is False
    assert state["MARKET_05_EXECUTION_AUTHORIZED"] is False
    assert state["arm_artifact_exists"] is False
    assert state["result_artifact_exists"] is False
    assert not (REPO / "docs/research/MARKET_05_ARM.json").exists()
    assert not (REPO / "docs/research/MARKET_05_RESULT.json").exists()


def test_cli_help_does_not_execute():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_cli_and_direct_execution_refuse_before_outcomes():
    outcome_loaded = []

    def _should_not_run() -> None:
        outcome_loaded.append(True)

    with pytest.raises(Market05ExecutionNotAuthorized):
        require_execution_authorized_before_outcome_load()
        _should_not_run()
    assert outcome_loaded == []

    with pytest.raises(Market05ExecutionNotAuthorized):
        refuse_unarmed_canonical_execution()
    with pytest.raises(Market05ExecutionNotAuthorized):
        refuse_scientific_result_instantiation()
    with pytest.raises(Market05ExecutionNotAuthorized):
        load_real_development_scientific_rows()
    assert cli.main([]) == 2
    assert cli.main(["--write-result"]) == 2


def test_protected_oos_rows_never_surface():
    with pytest.raises(Market05ProtectedOOSError):
        filter_development_open_times([PROTECTED_OOS_START_MS])
    mixed = [FIRST_USABLE_MS, PROTECTED_OOS_START_MS]
    with pytest.raises(Market05ProtectedOOSError):
        filter_development_open_times(mixed)
    protected_bar = Bar(PROTECTED_OOS_START_MS, 1.0, 1.0, 1.0)
    with pytest.raises(Market05ProtectedOOSError):
        reject_protected_scientific_bars([protected_bar])


def test_feature_loader_never_selects_bar_at_or_after_t():
    t = FIRST_USABLE_MS + 10 * 86_400_000
    prefix = Bar(prefix_open_time(t), 1.0, 1.0, 1.0)
    feat = [Bar(ot, 1.0, 1.0, 1.0) for ot in feature_open_times(t)]
    at_t = Bar(t, 9.0, 9.0, 9.0)
    after = Bar(t + 60_000, 8.0, 8.0, 8.0)
    selected = load_feature_window(t, [prefix, *feat, at_t, after])
    opens = {b.open_time_ms for b in selected}
    assert t not in opens
    assert t + 60_000 not in opens
    assert prefix_open_time(t) in opens
    assert max(opens) == t - 60_000


def test_outcome_loader_uses_bar_at_t_and_rejects_protected():
    t = int(datetime(2024, 12, 31, tzinfo=UTC).timestamp() * 1000)
    out = [Bar(ot, 1.0, 1.0, 1.0) for ot in outcome_open_times(t)]
    selected = load_outcome_window(t, out)
    assert selected[0].open_time_ms == t
    assert selected[-1].open_time_ms == t + 86_400_000 - 60_000
    with pytest.raises(Market05ProtectedOOSError):
        load_outcome_window(t, out + [Bar(PROTECTED_OOS_START_MS, 1.0, 1.0, 1.0)])


def test_eth_inventory_identity_is_bound_and_eth_not_btc():
    inv = load_bound_inventory()
    assert inv["dataset_id"] == DATASET_ID
    assert inv["instrument"] == INSTRUMENT
    assert INSTRUMENT == "ETHUSDT"
    assert INVENTORY_SHA256 == ETH_INVENTORY_SHA256
    rec = inv["checksum_records"][0]
    assert rec["expected_zip_filename"].startswith("ETHUSDT-")
    assert "BTCUSDT" not in rec["expected_zip_filename"]
    url = zip_url_from_checksum_url(rec["checksum_url"])
    assert url.endswith("ETHUSDT-1m-2020-01.zip")
    assert expected_csv_member("monthly", "2020-01") == "ETHUSDT-1m-2020-01.csv"
    payload = {"dataset_id": DATASET_ID, "objects": []}
    a = snapshot_id_from_payload(payload)
    b = snapshot_id_from_payload(payload)
    assert a == b
    assert len(a) == 64


def test_eth_csv_member_reader_fixture_roundtrip(tmp_path: Path):
    from scripts.research.core_btc_binance_v0_probe_lib import read_kline_csv_member_named
    from scripts.research.core_eth_binance_v0_acceptor_lib import audit_object_timestamps

    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rows = []
    for i in range(1440):
        ot = start + i * 60_000
        close_t = ot + 59_999
        rows.append(
            ",".join(
                [
                    str(ot),
                    "100.0",
                    "101.0",
                    "99.0",
                    "100.5",
                    "1.0",
                    str(close_t),
                    "100.0",
                    "10",
                    "0.4",
                    "40.0",
                    "0",
                ]
            )
        )
    member = "ETHUSDT-1m-2020-01-01.csv"
    zip_path = tmp_path / "ETHUSDT-1m-2020-01-01.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(member, "\n".join(rows) + "\n")
    text, names, status = read_kline_csv_member_named(zip_path, member)
    assert status == "OK"
    assert member in names
    assert text is not None
    record = {
        "archive_class": "daily",
        "source_period": "2020-01-01",
        "expected_zip_filename": "ETHUSDT-1m-2020-01-01.zip",
    }
    audit = audit_object_timestamps(zip_path, record)
    assert audit["observed_rows"] == 1440
    assert audit["missing_bucket_count"] == 0
    assert audit["duplicate_count"] == 0
    assert "open_times_ms" in audit
    assert "close" not in audit
    assert "high" not in audit
    assert "low" not in audit
