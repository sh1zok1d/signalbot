"""
Stage 2.1 output-row serialization for the storage writers (storage/db.py).

Narrow, isolated bridge between the four immutable analytics output models and
their existing Stage 2 tables. It is imported **lazily** by the writer methods so
Stage 1 startup never eagerly pulls in the Stage 2 analytics packages.

Responsibilities (and nothing more):
  * frozen column / primary-key tuples per table, derived from the output model
    so a field can never be silently dropped and an invented one can never be
    written;
  * one canonical, deterministic recursive JSON conversion for the consensus
    JSONB columns (MappingProxyType / frozen dataclasses / tuples), failing loud
    on NaN/±Inf, non-string keys, and unsupported objects;
  * whole-batch type validation + parameter-tuple construction, so a malformed
    batch is rejected before any DB connection is acquired.

No DB handle, no clock, no I/O. `computed_at` is never emitted — the table
default fills it on insert and the writer sets `computed_at = now()` on conflict.
"""
from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from typing import Any, Mapping, Sequence

from analytics.data_quality.models import DataHealthSnapshot
from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.percentile_engine.models import PercentileSnapshot


class Stage2SerializationError(TypeError):
    """A Stage 2 output row cannot be safely serialized for storage: wrong row
    type, a mixed batch, or a JSON value that is non-finite, keyed by a non-str,
    or otherwise unsupported. Raised BEFORE any DB call so a batch is never
    partially written. Subclasses TypeError so callers may catch either."""


# ---- canonical JSONB conversion (§7) ---------------------------------------
def to_jsonable(value: Any) -> Any:
    """Recursively convert a deeply-immutable analytics value into plain
    JSON-serializable Python (dict / list / str / int / float / bool / None).

    Supported inputs only: dataclass instances (by declared field name),
    Mapping (str keys), tuple/list, str, int, finite float, bool, None. bool is
    handled before int (bool is an int subclass). Everything else — including a
    non-str mapping key or a non-finite float — raises."""
    # None and bool first (bool must not fall through to the int branch).
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Stage2SerializationError(
                f"non-finite float is not allowed in a JSONB value: {value!r}")
        return value
    if isinstance(value, str):
        return value
    # Frozen/ordinary dataclass INSTANCE -> object by declared field names.
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclass_fields(value)}
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise Stage2SerializationError(
                    f"JSON object keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = to_jsonable(v)
        return out
    if isinstance(value, (tuple, list)):
        return [to_jsonable(v) for v in value]
    raise Stage2SerializationError(
        f"unsupported JSON value of type {type(value).__name__}: {value!r}")


def dumps_canonical_jsonb(value: Any) -> str:
    """Deterministic JSON text for a JSONB column: sorted keys, compact
    separators, NaN/±Inf rejected (belt-and-suspenders alongside `to_jsonable`)."""
    return json.dumps(
        to_jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


# ---- per-table writer specs ------------------------------------------------
def _build_insert_sql(table: str, columns: tuple[str, ...], pk: tuple[str, ...],
                      jsonb_columns: frozenset[str]) -> str:
    """Build the static parameterized upsert. Column/table names come only from
    these trusted constants — never from caller-supplied data. JSONB placeholders
    get an explicit `::jsonb` cast so asyncpg's codec expectation is unambiguous.
    On conflict every non-PK column is refreshed from EXCLUDED and `computed_at`
    is stamped now(); PK columns are never updated."""
    placeholders = []
    for i, col in enumerate(columns, start=1):
        ph = f"${i}::jsonb" if col in jsonb_columns else f"${i}"
        placeholders.append(ph)
    non_pk = [c for c in columns if c not in pk]
    set_clause = ",\n    ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
    set_clause += ",\n    computed_at = now()"
    return (
        f"INSERT INTO {table}\n"
        f"    ({', '.join(columns)})\n"
        f"VALUES ({', '.join(placeholders)})\n"
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET\n    {set_clause}"
    )


@dataclass(frozen=True)
class Stage2WriterSpec:
    model: type
    table: str
    columns: tuple[str, ...]          # output-model field order (excludes computed_at)
    pk: tuple[str, ...]               # == real table PK == ON CONFLICT target
    jsonb_columns: frozenset          # subset of columns serialized to JSONB text
    insert_sql: str

    def serialize_row(self, obj: Any) -> tuple:
        values = []
        for col in self.columns:
            v = getattr(obj, col)
            if col in self.jsonb_columns and v is not None:
                v = dumps_canonical_jsonb(v)
            values.append(v)
        return tuple(values)


def _make_spec(model: type, table: str, pk: tuple[str, ...],
               jsonb_columns: frozenset = frozenset()) -> Stage2WriterSpec:
    columns = tuple(f.name for f in dataclass_fields(model))
    # PK members and JSONB columns must be real model fields (guards typos).
    missing_pk = [c for c in pk if c not in columns]
    if missing_pk:
        raise Stage2SerializationError(f"{table} PK names not in model: {missing_pk}")
    missing_json = [c for c in jsonb_columns if c not in columns]
    if missing_json:
        raise Stage2SerializationError(f"{table} JSONB names not in model: {missing_json}")
    return Stage2WriterSpec(
        model=model, table=table, columns=columns, pk=pk,
        jsonb_columns=jsonb_columns,
        insert_sql=_build_insert_sql(table, columns, pk, jsonb_columns),
    )


EXCHANGE_FEATURE_SPEC = _make_spec(
    ExchangeFeatureVector,
    "exchange_feature_vectors",
    pk=("exchange", "symbol", "market_type", "timeframe", "bucket_ts",
        "calculation_version"),
)

CONSENSUS_FEATURE_SPEC = _make_spec(
    ConsensusFeatureVector,
    "consensus_feature_vectors",
    pk=("symbol", "market_type", "timeframe", "bucket_ts", "calculation_version"),
    jsonb_columns=frozenset({
        "coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric",
        "liquidation_feed_quality_by_exchange", "outlier_exchanges",
    }),
)

PERCENTILE_SNAPSHOT_SPEC = _make_spec(
    PercentileSnapshot,
    "percentile_snapshots",
    pk=("scope", "exchange", "symbol", "market_type", "metric", "timeframe",
        "percentile_window", "bucket_ts", "calculation_version"),
)

DATA_HEALTH_SNAPSHOT_SPEC = _make_spec(
    DataHealthSnapshot,
    "data_health_snapshots",
    pk=("symbol", "exchange", "market_type", "metric", "snapshot_ts",
        "calculation_version"),
)


def serialize_batch(spec: Stage2WriterSpec, rows: Sequence[Any]) -> list[tuple]:
    """Validate the WHOLE batch (exact model type, then JSONB serialization) and
    return one parameter tuple per row. Raises `Stage2SerializationError` before
    the caller touches the database, so a type or serialization fault can never
    yield a partially-written batch."""
    params: list[tuple] = []
    for i, obj in enumerate(rows):
        if type(obj) is not spec.model:
            raise Stage2SerializationError(
                f"row {i} must be exactly {spec.model.__name__}, got {type(obj).__name__}")
        params.append(spec.serialize_row(obj))
    return params
