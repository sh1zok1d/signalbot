"""Tardis incidentReports applied only when they cover the datasets we read.

A documented gap is tagged VENDOR_DOCUMENTED_GAP. Missing rows inside that
window stay missing. They are not written as zero.

The OKX incident that runs from 2023-06-09 through 2026-08-04 names generated
statistics channels (long-short-account-ratio, taker-volume, loan-ratio) and
says other OKX channels were unaffected. trades and derivative_ticker are
therefore not tagged for that incident.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .constants import VENDOR_GAP_TAG

_STATS_ONLY_MARK = "other okx channels were unaffected"


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def incident_applies_to_requested_datasets(incident: dict) -> bool:
    details = str(incident.get("details") or "")
    if _STATS_ONLY_MARK in details.lower():
        return False
    return True


def overlapping_incidents(incidents: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Incidents whose [from, to] overlaps the half-open bucket [start, end)."""
    hit = []
    for incident in incidents:
        if not incident_applies_to_requested_datasets(incident):
            continue
        inc_from = parse_utc(incident["from"])
        inc_to = parse_utc(incident["to"])
        if inc_from < end and inc_to > start:
            hit.append(incident)
    return hit


def bucket_tags(incidents: list[dict], start: datetime, end: datetime) -> list[str]:
    if overlapping_incidents(incidents, start, end):
        return [VENDOR_GAP_TAG]
    return []
