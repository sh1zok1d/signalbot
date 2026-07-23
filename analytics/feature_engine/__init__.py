"""Stage 2.1 feature engine: per-exchange (Level A) and consensus (Level B)
feature computation. Pure/deterministic cores — no DB, network, or clock.

The input adapter (`input_adapter`) bridges Stage 1 raw rows to a valid
`ExchangeFeatureRequest`; its pure helpers do no I/O, and its async loader only
calls a supplied raw reader (it never writes, loops, or reads a clock)."""
from .pipeline import ExchangeFeatureWriter, process_exchange_feature_bucket
from .consensus_input_adapter import ConsensusInputError, build_consensus_feature_request
from .consensus_pipeline import ConsensusFeatureWriter, process_consensus_feature_bucket
from .input_adapter import (
    AssemblyContext, FeatureInputError, RawBundleReader,
    assemble_exchange_feature_request, build_assembly_context,
    load_exchange_feature_request,
)

__all__ = [
    "AssemblyContext", "FeatureInputError", "RawBundleReader",
    "assemble_exchange_feature_request", "build_assembly_context",
    "load_exchange_feature_request",
    "ExchangeFeatureWriter", "process_exchange_feature_bucket",
    "ConsensusInputError", "build_consensus_feature_request",
    "ConsensusFeatureWriter", "process_consensus_feature_bucket",
]
