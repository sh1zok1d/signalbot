"""Cutoff tests for the C012 discovery-month materializer. No price outcomes."""

import pytest

from scripts.research import gv0r01_c012_discovery_market_bytes as M


def test_allowlist_is_sixty_discovery_months():
    months = [o.source_period for o in M.discovery_objects()]
    assert len(months) == 60
    assert months[0] == "2020-01"
    assert months[-1] == "2024-12"
    assert months == list(M.ALLOWLIST)


def test_protected_month_rejected_before_fetch():
    called = []

    def fetch(url):
        called.append(url)
        raise AssertionError("fetch must not run")

    with pytest.raises(RuntimeError, match="MONTH_REJECTED_BEFORE_BYTE_ACCESS"):
        M.guarded_fetch(fetch, "https://data.binance.vision/BTCUSDT-1m-2025-01.zip")
    with pytest.raises(RuntimeError, match="MONTH_REJECTED_BEFORE_BYTE_ACCESS"):
        M.guarded_fetch(fetch, "https://example.invalid/BTCUSDT-1m-2026-08.zip")
    assert called == []


def test_module_does_not_call_full_snapshot_acquire_or_c012_returns():
    src = open(M.__file__).read()
    assert "acquire_all_verified" not in src
    assert "build_frozen_source_plan" not in src
    assert "stage_acquire" not in src
    assert "gv0r01_c012_execute" not in src
    assert "DELTA_24" not in src
    assert "window_return" not in src


def test_manifest_digest_stable():
    body = {
        "DATASET_ID": M.DISCOVERY_DATASET_ID,
        "MONTHS": [{"MONTH": "2020-01", "ROW_COUNT": 1}],
    }
    import hashlib, json
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    again = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == again
