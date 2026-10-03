"""Pinned inputs for the AUTOGEN_G01 outcome-blind feasibility pass. No 2025/2026 object
is selected and no market value is read.

- `bitmex_timestamps` reads BitMEX XBTUSD 5m bar open times only (D2_BITMEX_PRE2020_XBTUSD
  canonical gz, digest checked against the D2 source authority) for replication availability.
- `dataset_identity` binds the pinned BTC inventory, the BitMEX file and the NYSE calendar
  through the frozen R03 helpers, imported unchanged.

No market-value loader exists here: no hypothesis passed feasibility, so nothing is executed.
"""

from __future__ import annotations

import gzip
import json

import numpy as np

from scripts.research.owner_cards_r03 import data as RD

from . import constants as K


def _bitmex_verified():
    authority = json.loads(RD.BITMEX_AUTHORITY.read_text())
    if RD.sha256_file(RD.BITMEX_GZ) != authority["canonical_jsonl_gz_sha256"]:
        raise RuntimeError("BitMEX canonical gz digest drifted")
    return RD.BITMEX_GZ


def bitmex_timestamps() -> np.ndarray:
    """5m bar open times only (no price, no trade count), 2017-01-01..2019-12-31."""
    out = []
    with gzip.open(_bitmex_verified(), "rt") as handle:
        for line in handle:
            out.append(json.loads(line)["open_time_ms"])
    t = np.array(sorted(out), dtype=np.int64)
    return t[(t >= K.BITMEX_START_MS) & (t < K.BITMEX_END_MS)]


def dataset_identity() -> dict:
    return {
        "BTC": {"DATASET_ID": K.DATASET_BTC, "ZIP_LIST_SHA256": RD.btc_dataset_digest(), "MONTHS": "2020-01..2024-12",
                "VALUES_READ": False},
        "BITMEX": {"DATASET_ID": K.DATASET_BITMEX, "GZ_SHA256": RD.sha256_file(RD.BITMEX_GZ),
                   "YEARS": "2017-2019", "READ": "bar open times only"},
        "NYSE": {"DATASET_ID": K.DATASET_NYSE, "EVENTS_SHA256": RD.sha256_file(RD.NYSE_EVENTS)},
        "PROTECTED_2025_2026_SELECTED": False,
    }
