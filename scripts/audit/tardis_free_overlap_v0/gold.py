"""Load a Signalbot live-raw export. Rows with any other source are rejected."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from analytics.feature_engine.models import KlineBar, OpenInterestObservation

from .constants import VENUE_BY_SIGNALBOT, VenueMap
from .features import structural_metadata
from common.instrument_metadata import InstrumentMetadata

REQUIRED_FILES = (
    "klines_1m.csv",
    "open_interest.csv",
    "exchange_instrument_history.csv",
)


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    ts = datetime.fromisoformat(text)
    if ts.tzinfo is None:
        raise ValueError(f"timestamp {value!r} is not timezone-aware")
    return ts.astimezone(timezone.utc)


def _float_or_none(value: str):
    if value is None or value == "":
        return None
    return float(value)


@dataclass(frozen=True)
class HistoryRow:
    exchange: str
    quantity_unit: str | None
    contract_multiplier: float | None
    effective_from: datetime
    effective_until: datetime | None
    exchange_instrument_id: str


@dataclass
class GoldArchive:
    bars: dict[tuple[str, datetime], KlineBar]
    oi: dict[str, list[OpenInterestObservation]]
    history: list[HistoryRow]

    def metadata_asof(self, exchange: str, bucket_ts: datetime) -> InstrumentMetadata | None:
        venue: VenueMap = VENUE_BY_SIGNALBOT[exchange]
        matches = [
            row for row in self.history
            if row.exchange == exchange
            and row.effective_from <= bucket_ts
            and (row.effective_until is None or bucket_ts < row.effective_until)
        ]
        if len(matches) > 1:
            raise ValueError(
                f"overlapping instrument history for {exchange} at {bucket_ts.isoformat()}"
            )
        if len(matches) == 1:
            row = matches[0]
            multiplier = row.contract_multiplier
            unit = row.quantity_unit or venue.quantity_unit
            if unit == "contracts" and not (multiplier is not None and multiplier > 0):
                multiplier = None
            return structural_metadata(
                venue,
                contract_multiplier=multiplier if unit == "contracts" else None,
                metadata_source="manual",
                note="PIT exchange_instrument_history as-of bucket start",
            ) if unit == venue.quantity_unit else structural_metadata(
                VenueMap(
                    signalbot_exchange=venue.signalbot_exchange,
                    canonical_symbol=venue.canonical_symbol,
                    tardis_exchange=venue.tardis_exchange,
                    tardis_symbol=venue.tardis_symbol,
                    quantity_unit=unit,
                    oi_unit=venue.oi_unit,
                    contract_multiplier=None,
                ),
                contract_multiplier=multiplier if unit == "contracts" else None,
                metadata_source="manual",
                note="PIT history unit",
            )
        if venue.quantity_unit == "contracts":
            return structural_metadata(
                venue,
                contract_multiplier=None,
                metadata_source="manual",
                note="no PIT multiplier; notional fail-closed",
            )
        return structural_metadata(
            venue,
            contract_multiplier=None,
            metadata_source="manual",
            note="structural base unit; no history row",
        )


def _require_live(source: str, *, table: str) -> None:
    if source != "live":
        raise ValueError(
            f"{table} row source={source!r}; only source=live may enter the gold set"
        )


def load_gold_dir(path: str | Path) -> GoldArchive:
    root = Path(path)
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            raise FileNotFoundError(f"missing {name} in {root}")
    bars: dict[tuple[str, datetime], KlineBar] = {}
    with (root / "klines_1m.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            _require_live(row["source"], table="klines_1m")
            if row["symbol"] != "BTCUSDT":
                raise ValueError(f"unexpected symbol {row['symbol']!r}")
            if row["exchange"] not in VENUE_BY_SIGNALBOT:
                raise ValueError(f"unexpected exchange {row['exchange']!r}")
            ts = _parse_ts(row["ts"])
            buy = _float_or_none(row["taker_buy_volume"])
            sell = _float_or_none(row["taker_sell_volume"])
            bars[(row["exchange"], ts)] = KlineBar(
                ts=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                taker_buy_volume=buy,
                taker_sell_volume=sell,
            )
    oi: dict[str, list[OpenInterestObservation]] = {ex: [] for ex in VENUE_BY_SIGNALBOT}
    with (root / "open_interest.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            _require_live(row["source"], table="open_interest")
            if row["symbol"] != "BTCUSDT":
                raise ValueError(f"unexpected symbol {row['symbol']!r}")
            if row["exchange"] not in VENUE_BY_SIGNALBOT:
                raise ValueError(f"unexpected exchange {row['exchange']!r}")
            if row["oi_raw"] == "" or row["oi_unit"] == "":
                continue
            oi[row["exchange"]].append(OpenInterestObservation(
                ts=_parse_ts(row["ts"]),
                oi_raw=float(row["oi_raw"]),
                oi_unit=row["oi_unit"],
            ))
    history: list[HistoryRow] = []
    with (root / "exchange_instrument_history.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames == ["note"]:
            history = []
        else:
            for row in reader:
                if not row.get("exchange"):
                    continue
                until = row.get("effective_until") or ""
                history.append(HistoryRow(
                    exchange=row["exchange"],
                    quantity_unit=row.get("quantity_unit") or None,
                    contract_multiplier=_float_or_none(row.get("contract_multiplier") or ""),
                    effective_from=_parse_ts(row["effective_from"]),
                    effective_until=_parse_ts(until) if until else None,
                    exchange_instrument_id=row.get("exchange_instrument_id") or "",
                ))
    return GoldArchive(bars=bars, oi=oi, history=history)
