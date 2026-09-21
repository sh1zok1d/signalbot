"""Global canonical-reconstruction invariants (red-team F-06).

Synthetic objects only. No retained bytes, no real OHLC, no outcomes.

The frozen production constants are asserted separately; the structural
tests shrink the window so a complete synthetic grid is cheap to build.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

import pytest

from scripts.research import market_06_canonical_reconstruction as recon
from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import BAR_MS

WINDOW_START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
SYNTHETIC_BARS = 24
WINDOW_END = WINDOW_START + SYNTHETIC_BARS * BAR_MS


def _permit() -> lifecycle.ExecutionPermit:
    return lifecycle.ExecutionPermit(
        run_identity="synthetic-run-identity",
        arm_commit="0" * 39 + "1",
        implementation_freeze_head="0" * 39 + "2",
        implementation_freeze_tree="0" * 39 + "3",
        dataset_id=lifecycle.DATASET_ID,
        snapshot_id=lifecycle.SNAPSHOT_ID,
        durable_evidence_root_sha256=lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        authorization_kind=lifecycle.AUTHORIZATION_KIND,
        _token=lifecycle._PERMIT_TOKEN,
    )


def _binance_zip(timestamps: list[int], *, price: float = 100.0) -> bytes:
    rows = ["open_time,open,high,low,close"]
    for ts in timestamps:
        rows.append(f"{ts},{price},{price + 1},{price - 1},{price}")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("BTCUSDT-5m.csv", "\n".join(rows))
    return buf.getvalue()


def _okx_body(timestamps: list[int], *, price: float = 100.0) -> bytes:
    data = [
        [str(ts), str(price), str(price + 1), str(price - 1), str(price), "1", "1", "1", "1"]
        for ts in timestamps
    ]
    return json.dumps({"code": "0", "data": data}).encode("utf-8")


def _install(monkeypatch, binance_chunks, okx_chunks, *, blobs=None, manifest_patch=None):
    """Serve synthetic objects through the Git authority layer."""

    monkeypatch.setattr(recon, "WINDOW_START_MS", WINDOW_START)
    monkeypatch.setattr(recon, "WINDOW_END_EXCLUSIVE_MS", WINDOW_END)
    monkeypatch.setattr(recon, "EXPECTED_5M_TIMESTAMPS", SYNTHETIC_BARS)
    monkeypatch.setattr(recon, "EXPECTED_FIRST_MS", WINDOW_START)
    monkeypatch.setattr(recon, "EXPECTED_LAST_MS", WINDOW_END - BAR_MS)
    monkeypatch.setattr(recon, "BINANCE_OBJECT_COUNT", len(binance_chunks))
    monkeypatch.setattr(recon, "OKX_OBJECT_COUNT", len(okx_chunks))

    store: dict[str, bytes] = {}
    binance_rows = []
    for i, chunk in enumerate(binance_chunks, start=1):
        payload = _binance_zip(chunk)
        path = f"durable_raw/binance/BTCUSDT-5m-obj{i}.zip"
        store[f"{recon.DATASET_DIR_REL}/{path}"] = payload
        binance_rows.append(
            {
                "logical_id": f"BINANCE_OBJ_{i}",
                "durable_path": path,
                "original_filename": f"BTCUSDT-5m-obj{i}.zip",
                "sha256": recon._sha256(payload),
                "byte_length": len(payload),
            }
        )
    okx_rows = []
    for i, chunk in enumerate(okx_chunks, start=1):
        payload = _okx_body(chunk)
        path = f"durable_raw/okx/page-{i:06d}.json"
        store[f"{recon.DATASET_DIR_REL}/{path}"] = payload
        okx_rows.append(
            {
                "logical_id": f"OKX_PAGE_{i}",
                "durable_path": path,
                "original_filename": f"page-{i:06d}.json",
                "sha256": recon._sha256(payload),
                "byte_length": len(payload),
            }
        )

    manifest = {
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "binance_objects": binance_rows,
        "okx_objects": okx_rows,
    }
    if manifest_patch:
        manifest_patch(manifest)
    store[recon.DURABLE_MANIFEST_REL] = json.dumps(manifest).encode("utf-8")
    if blobs:
        store.update(blobs)

    monkeypatch.setattr(recon.gitauth, "require_commit", lambda c, **k: "a" * 40)

    def fake_cat_blob(commit, relpath):
        if relpath not in store:
            raise recon.gitauth.Market06GitAuthorityError(f"missing:{relpath}")
        return store[relpath]

    monkeypatch.setattr(recon.gitauth, "cat_blob", fake_cat_blob)
    return manifest


def _full_grid() -> list[int]:
    return [WINDOW_START + i * BAR_MS for i in range(SYNTHETIC_BARS)]


def _halves():
    grid = _full_grid()
    return grid[: SYNTHETIC_BARS // 2], grid[SYNTHETIC_BARS // 2 :]


def test_frozen_production_constants_unchanged():
    assert recon.BINANCE_OBJECT_COUNT == 36
    assert recon.OKX_OBJECT_COUNT == 1053
    assert recon.EXPECTED_5M_TIMESTAMPS == 315648
    assert recon.EXPECTED_FIRST_MS == int(
        datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
    )
    assert recon.EXPECTED_LAST_MS == int(
        datetime(2024, 12, 31, 23, 55, tzinfo=timezone.utc).timestamp() * 1000
    )


def test_permit_is_required():
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        recon.reconstruct_canonical_dataset(None)
    with pytest.raises(lifecycle.Market06ExecutionNotAuthorized):
        recon.reconstruct_canonical_dataset(object())


def test_complete_synthetic_grid_reconstructs(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, b], [a, b])
    perp, spot, audit = recon.reconstruct_canonical_dataset(_permit())
    assert len(perp) == len(spot) == SYNTHETIC_BARS
    assert set(perp) == set(spot)
    assert audit["leg_timestamp_sets_equal"] is True
    assert audit["interpolation"] is False
    assert audit["deduplication"] is False
    assert audit["ohlc_values_reported"] is False


def test_duplicate_timestamp_across_two_binance_objects_fails(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, [a[-1]] + b], [a, b])
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "GLOBAL_DUPLICATE_TIMESTAMP:binance" in exc.value.reason


def test_duplicate_timestamp_across_two_okx_pages_fails(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, b], [a, [a[-1]] + b])
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "GLOBAL_DUPLICATE_TIMESTAMP:okx" in exc.value.reason


def test_identical_values_do_not_excuse_a_cross_object_duplicate(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, [a[-1]] + b], [a, b])
    with pytest.raises(Market06IncompleteExecution):
        recon.reconstruct_canonical_dataset(_permit())


def test_missing_global_timestamp_fails(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, b[1:]], [a, b])
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "TIMESTAMP_COUNT:binance" in exc.value.reason


def test_extra_in_window_timestamp_fails(monkeypatch):
    a, b = _halves()
    extra = WINDOW_START + (SYNTHETIC_BARS + 5) * BAR_MS
    monkeypatch.setattr(recon, "WINDOW_END_EXCLUSIVE_MS", WINDOW_END + 10 * BAR_MS)
    _install(monkeypatch, [a, b + [extra]], [a, b])
    monkeypatch.setattr(recon, "WINDOW_END_EXCLUSIVE_MS", WINDOW_END + 10 * BAR_MS)
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "TIMESTAMP_COUNT:binance" in exc.value.reason or "LAST_TIMESTAMP" in exc.value.reason


def test_mismatched_leg_timestamp_sets_fail(monkeypatch):
    a, b = _halves()
    shifted = [ts for ts in b[:-1]] + [WINDOW_START - BAR_MS]
    _install(monkeypatch, [a, b], [a, shifted])
    with pytest.raises(Market06IncompleteExecution):
        recon.reconstruct_canonical_dataset(_permit())


def test_wrong_object_count_fails(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, b], [a, b])
    monkeypatch.setattr(recon, "BINANCE_OBJECT_COUNT", 3)
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert exc.value.reason == "MANIFEST_BINANCE_COUNT"


def test_same_filename_different_bytes_fails_authority(monkeypatch):
    a, b = _halves()
    manifest = _install(monkeypatch, [a, b], [a, b])
    tampered = _binance_zip(a, price=555.0)
    rel = f"{recon.DATASET_DIR_REL}/{manifest['binance_objects'][0]['durable_path']}"

    original = recon.gitauth.cat_blob

    def tampering_cat_blob(commit, relpath):
        if relpath == rel:
            return tampered
        return original(commit, relpath)

    monkeypatch.setattr(recon.gitauth, "cat_blob", tampering_cat_blob)
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "RETAINED_OBJECT_SHA256" in exc.value.reason


def test_inventory_reorder_cannot_alter_authority(monkeypatch):
    a, b = _halves()
    _install(monkeypatch, [a, b], [a, b])
    forward = recon.reconstruct_canonical_dataset(_permit())[2]

    def reverse(manifest):
        manifest["binance_objects"].reverse()
        manifest["okx_objects"].reverse()

    _install(monkeypatch, [a, b], [a, b], manifest_patch=reverse)
    reversed_audit = recon.reconstruct_canonical_dataset(_permit())[2]
    assert forward["binance_timestamps"] == reversed_audit["binance_timestamps"]
    assert forward["okx_timestamps"] == reversed_audit["okx_timestamps"]


def test_duplicate_logical_id_in_inventory_fails(monkeypatch):
    a, b = _halves()

    def dup(manifest):
        manifest["binance_objects"][1]["logical_id"] = manifest["binance_objects"][0][
            "logical_id"
        ]

    _install(monkeypatch, [a, b], [a, b], manifest_patch=dup)
    with pytest.raises(Market06IncompleteExecution) as exc:
        recon.reconstruct_canonical_dataset(_permit())
    assert "INVENTORY_DUPLICATE_LOGICAL_ID" in exc.value.reason


def test_working_tree_mutation_cannot_substitute_git_bound_bytes(monkeypatch, tmp_path):
    """Reconstruction reads Git objects only; on-disk files are irrelevant."""

    a, b = _halves()
    _install(monkeypatch, [a, b], [a, b])
    stray = tmp_path / "durable_raw"
    stray.mkdir(parents=True)
    (stray / "BTCUSDT-5m-obj1.zip").write_bytes(_binance_zip(a, price=999.0))
    perp, spot, audit = recon.reconstruct_canonical_dataset(_permit())
    assert audit["binance_timestamps"] == SYNTHETIC_BARS
    assert set(perp) == set(spot)


def test_out_of_window_rows_are_trimmed_not_treated_as_corruption(monkeypatch):
    """OKX pages are fixed-size and legitimately straddle the boundary."""

    a, b = _halves()
    before = [WINDOW_START - 2 * BAR_MS, WINDOW_START - BAR_MS]
    _install(monkeypatch, [a, b], [before + a, b])
    _perp, _spot, audit = recon.reconstruct_canonical_dataset(_permit())
    assert audit["okx_out_of_window_trimmed"] == 2
    assert audit["okx_timestamps"] == SYNTHETIC_BARS
