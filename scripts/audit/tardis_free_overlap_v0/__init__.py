"""Tardis free-sample overlap validation V0.

Outcome-blind market-feature tooling. It does not import or modify the beta
detector, rules, percentile engine, or production writers.
"""

SOURCE_TARDIS = "TARDIS_FREE_SAMPLE"
SOURCE_SIGNALBOT_GOLD = "RECONSTRUCTED_FROM_SIGNALBOT_LIVE_RAW"
CANDIDATE_PROVENANCE_CLASS = "HISTORICAL_MULTI_VENUE_CLOSE_REPLAY"
DECISION_INCOMPLETE = "INCOMPLETE_NO_SIGNALBOT_EXPORT"
WAITING_FOR_EXPORT = "WAITING_FOR_SIGNALBOT_EXPORT"
