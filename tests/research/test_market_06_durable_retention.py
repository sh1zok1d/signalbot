"""Durable Git retention of MARKET_06_OKX_BINANCE_FEASIBILITY_V0 raw bytes."""

from __future__ import annotations

import json
import shutil
import socket
import urllib.request
from pathlib import Path

import pytest

from scripts.research import market_06_durable_retention as retention

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
FORBIDDEN = {
    "MARKET_06.md",
    "MARKET_06_PREREG.md",
    "MARKET_06_PREREG.json",
    "MARKET_06_ARM.md",
    "MARKET_06_ARM.json",
    "MARKET_06_RESULT.md",
    "MARKET_06_RESULT.json",
    "M04_FWD.md",
    "MARKET_04_FWD_PREREG.md",
}


def test_object_counts_and_snapshot_id():
    assert retention.BINANCE_OBJECT_COUNT == 36
    assert retention.OKX_PAGE_COUNT == 1053
    assert retention.recompute_snapshot_id(DOCS) == retention.SNAPSHOT_ID
    assert (
        retention.SNAPSHOT_ID
        == "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
    )
    zips = list((DOCS / "durable_raw/binance").glob("BTCUSDT-5m-*.zip"))
    pages = list((DOCS / "durable_raw/okx").glob("page-*.json"))
    assert len(zips) == 36
    assert len(pages) == 1053


def test_durable_files_are_git_tracked():
    import subprocess

    proc = subprocess.run(
        [
            "git",
            "ls-files",
            "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw",
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [line for line in proc.stdout.splitlines() if line]
    assert len([p for p in tracked if p.endswith(".zip")]) == 36
    assert len([p for p in tracked if "/okx/page-" in p and p.endswith(".json")]) == 1053
    assert len([p for p in tracked if p.endswith(".CHECKSUM")]) == 36


def test_byte_for_byte_match_to_original_manifests():
    result = retention.verify_durable_offline()
    assert result["all_preexisting_sha256_match"] is True
    assert result["byte_for_byte_recovery_proven"] is True
    assert result["snapshot_id"] == retention.SNAPSHOT_ID


def test_offline_verification_with_network_disabled(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("NETWORK_USED")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    result = retention.verify_durable_offline()
    assert result["offline_recovery_proven"] is True
    assert result["snapshot_id"] == retention.SNAPSHOT_ID


def _clone_identity(tmp_path: Path) -> Path:
    dest = tmp_path / "identity"
    shutil.copytree(DOCS, dest, ignore=shutil.ignore_patterns("probes"))
    return dest


def test_one_byte_mutation_fails(tmp_path):
    dest = _clone_identity(tmp_path)
    target = dest / "durable_raw/binance/BTCUSDT-5m-2022-01.zip"
    data = bytearray(target.read_bytes())
    data[0] ^= 0x01
    target.write_bytes(bytes(data))
    with pytest.raises(retention.DurableRetentionMismatch):
        retention.verify_durable_offline(identity_dir=dest)


def test_missing_object_fails(tmp_path):
    dest = _clone_identity(tmp_path)
    (dest / "durable_raw/okx/page-000001.json").unlink()
    with pytest.raises(retention.DurableRetentionMissing):
        retention.verify_durable_offline(identity_dir=dest)


def test_substituted_object_fails(tmp_path):
    dest = _clone_identity(tmp_path)
    src = dest / "durable_raw/binance/BTCUSDT-5m-2022-01.zip"
    other = dest / "durable_raw/binance/BTCUSDT-5m-2022-02.zip"
    other.write_bytes(src.read_bytes())
    with pytest.raises(retention.DurableRetentionMismatch):
        retention.verify_durable_offline(identity_dir=dest)


def test_object_order_does_not_change_authority():
    manifest = json.loads((DOCS / "DURABLE_RETENTION_MANIFEST.json").read_text())
    inspected = {
        "binance_objects": list(manifest["binance_objects"]),
        "okx_objects": list(manifest["okx_objects"]),
    }
    reversed_inspected = {
        "binance_objects": list(reversed(manifest["binance_objects"])),
        "okx_objects": list(reversed(manifest["okx_objects"])),
    }
    assert (
        retention.durable_evidence_root_sha256(inspected)
        == manifest["durable_evidence_root_sha256"]
    )
    assert (
        retention.durable_evidence_root_sha256(reversed_inspected)
        == manifest["durable_evidence_root_sha256"]
    )


def test_no_scientific_artifacts_created():
    research = REPO / "docs/research"
    for name in FORBIDDEN:
        assert not (research / name).exists()
    review = json.loads(
        (REPO / "docs/research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.json").read_text()
    )
    assert review["verdict"] == "MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED"
    bybit = json.loads(
        (REPO / "docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.json").read_text()
    )
    assert bybit["verdict"] == "MARKET_06_HISTORICAL_FEASIBILITY_REQUIRES_DESIGN_REVIEW"
    manifest = json.loads((DOCS / "DURABLE_RETENTION_MANIFEST.json").read_text())
    assert manifest["scientific_outcomes_inspected"] is False
    assert manifest["new_snapshot_minted"] is False
    assert manifest["snapshot_id"] == retention.SNAPSHOT_ID
    assert manifest["raw_bytes_git_retained"] is True
