"""HISTORICAL_FOLLOW_UP_V0 — "what happened after previous comparable states?"

A pure, descriptive read model. Given already-known comparable TRIGGERED
episodes with their forward outcomes, control candidates and detector episode
windows, it summarises the ABSOLUTE realized range that followed. It never
produces a direction, a return, a probability or a prediction, and it is not
wired into /btc (docs/BETA_HISTORICAL_FOLLOW_UP_V0.md).

* Horizons: 1h and 4h only. Outcome: realized_range_pct only (close return,
  max up/down and their timings stay internal to beta/outcomes.py).
* Fail-closed display sufficiency: DISPLAY_SUFFICIENCY (>= 10 completed events
  across >= 5 distinct UTC dates). Below it, only counts are returned.
* Ordinary same-time baseline: "what was normal around this time of day" — the
  same UTC 5m slot on each of the previous 30 UTC dates, one per date, outside
  +/- 4h of any detector episode. Each event contributes ONE number (the median
  of its controls). It is not an incremental-information test.
* Volatility-matched baseline: Q1-style — LIVE/evaluable candidates, outside
  +/- 4h of any episode, same UTC hour-of-day +/- 1h, same 30d tercile of the
  PREVIOUS 1h realized range (measured strictly before the anchor), up to 5
  nearest-in-time controls, without replacement across events. Matching is
  never relaxed: an event without matches is excluded and counted.
* Provenance (LIVE_OBSERVED vs RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA) is
  carried per observation and preserved in the details.

No database access, no detector replay, no change to any production path.
"""
from __future__ import annotations

import hashlib
import html
import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

from common.versioning import canonical_json

from .comparability import EventComparability
from .config import HORIZON_MINUTES
from .formatter import assert_descriptive
from .models import OUTCOME_COMPLETE
from .outcomes import compute_outcome

FOLLOW_UP_VERSION = "HISTORICAL_FOLLOW_UP_V0"
FOLLOW_UP_HORIZONS = ("1h", "4h")
FOLLOW_UP_OUTCOME = "realized_range_pct"

LIVE_OBSERVED = "LIVE_OBSERVED"
RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA = "RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA"
PROVENANCES = (LIVE_OBSERVED, RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA)


@dataclass(frozen=True)
class DisplaySufficiency:
    """The single configuration point for showing ANY historical number."""
    min_events: int = 10
    min_utc_dates: int = 5


DISPLAY_SUFFICIENCY = DisplaySufficiency()

EPISODE_EXCLUSION = timedelta(hours=4)          # controls never within +/- 4h of any episode
ORDINARY_LOOKBACK_DAYS = 30
ORDINARY_MIN_CONTROLS_PER_EVENT = 10
MATCHED_HOUR_TOLERANCE = 1                      # UTC hour-of-day +/- 1h (circular)
MATCHED_MAX_CONTROLS = 5
MATCHED_MIN_CONTROLS = 1
TERCILE_WINDOW = timedelta(days=30)
TERCILE_MIN_REFERENCE = 7 * 288                 # >= 7 days of 5m anchors before a tercile exists
PRIOR_WINDOW = timedelta(hours=1)

INSUFFICIENT_EVENTS = "INSUFFICIENT_EVENTS"
INSUFFICIENT_UTC_DATES = "INSUFFICIENT_UTC_DATES"
EVENTS_NOT_ELIGIBLE = "EVENT_HISTORY_NOT_ELIGIBLE"


class FollowUpError(ValueError):
    """Malformed follow-up input (fail loudly; never guess)."""


# ---- inputs ---------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    """One forward outcome at one horizon (from beta/outcomes.py semantics)."""
    status: str
    realized_range_pct: Optional[float]
    outcome_version: str


@dataclass(frozen=True)
class EventObservation:
    event_id: str                        # public EV-... id
    comparability_digest: str
    anchor: datetime                     # trigger decision boundary (UTC)
    provenance: str
    outcomes: Mapping[str, Outcome]      # horizon -> Outcome
    prior_1h_tercile: Optional[int] = None


@dataclass(frozen=True)
class ControlCandidate:
    anchor: datetime                     # 5m decision boundary (UTC)
    provenance: str
    evaluable: bool                      # LIVE tape row: evaluation_fresh and core families usable
    outcomes: Mapping[str, Outcome]
    prior_1h_tercile: Optional[int] = None


@dataclass(frozen=True)
class EpisodeWindow:
    start: datetime                      # opened bucket
    end: Optional[datetime]              # terminal time; None = still open


def _utc(dt: datetime, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise FollowUpError(f"{name} must be a UTC-aware datetime")
    return dt


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---- pure feature helpers --------------------------------------------------------
def prior_1h_realized_range_pct(*, anchor: datetime, reference_price: Optional[float],
                                exchanges: Sequence[str], klines: Iterable[Mapping[str, Any]]
                                ) -> Optional[float]:
    """Realized range over [anchor - 1h, anchor) with the unchanged composite
    outcome formula. Bars at or after the anchor are never read."""
    _utc(anchor, "anchor")
    before = [k for k in klines if k["ts"] < anchor]
    o = compute_outcome(anchor=anchor - PRIOR_WINDOW, horizon="1h", reference_price=reference_price,
                        exchanges=exchanges, klines=before)
    return o["realized_range_pct"] if o["status"] == OUTCOME_COMPLETE else None


def volatility_tercile(*, anchor: datetime, value: Optional[float],
                       reference: Iterable[tuple]) -> Optional[int]:
    """30d mid-rank tercile (0 low, 1 middle, 2 high) of `value` among prior-1h
    ranges at anchors in [anchor - 30d, anchor). None when unmeasured or when the
    reference sample is too small (fail closed, never a guessed tercile)."""
    _utc(anchor, "anchor")
    if value is None or not math.isfinite(value):
        return None
    lo = anchor - TERCILE_WINDOW
    ref = [float(v) for ts, v in reference if v is not None and lo <= ts < anchor]
    if len(ref) < TERCILE_MIN_REFERENCE:
        return None
    less = sum(1 for v in ref if v < value)
    equal = sum(1 for v in ref if v == value)
    rank = (less + 0.5 * equal) / len(ref)
    return 0 if rank < 1 / 3 else (1 if rank < 2 / 3 else 2)


def in_episode_exclusion(anchor: datetime, windows: Sequence[EpisodeWindow]) -> bool:
    for w in windows:
        if anchor >= w.start - EPISODE_EXCLUSION and (w.end is None or anchor <= w.end + EPISODE_EXCLUSION):
            return True
    return False


def _complete(outcomes: Mapping[str, Outcome], outcome_version: str) -> bool:
    for h in FOLLOW_UP_HORIZONS:
        o = outcomes.get(h)
        if o is None or o.status != OUTCOME_COMPLETE or o.outcome_version != outcome_version \
                or o.realized_range_pct is None or not math.isfinite(o.realized_range_pct):
            return False
    return True


def _matured(anchor: datetime, as_of: datetime) -> bool:
    return anchor + timedelta(minutes=max(HORIZON_MINUTES[h] for h in FOLLOW_UP_HORIZONS)) <= as_of


def _hour_distance(a: datetime, b: datetime) -> int:
    d = abs(a.hour - b.hour) % 24
    return min(d, 24 - d)


# ---- control selection -------------------------------------------------------------
def select_ordinary_controls(event: EventObservation, candidates: Mapping[datetime, ControlCandidate],
                             windows: Sequence[EpisodeWindow], *, outcome_version: str,
                             provenances: Sequence[str]) -> list:
    """Same UTC 5m slot on previous UTC dates (1..30 days back); one per date."""
    out = []
    for d in range(1, ORDINARY_LOOKBACK_DAYS + 1):
        c = candidates.get(event.anchor - timedelta(days=d))
        if c is None or c.provenance not in provenances or in_episode_exclusion(c.anchor, windows):
            continue
        if not _complete(c.outcomes, outcome_version) or not _matured(c.anchor, event.anchor):
            continue
        out.append(c)
    return out


def select_matched_controls(events: Sequence[EventObservation], candidates: Sequence[ControlCandidate],
                            windows: Sequence[EpisodeWindow], *, outcome_version: str,
                            provenances: Sequence[str], as_of: datetime) -> dict:
    """event_id -> controls, deterministic, without replacement across events
    (events processed chronologically; ties broken by the earlier candidate)."""
    pool = sorted((c for c in candidates
                   if c.evaluable and c.provenance in provenances and c.prior_1h_tercile is not None
                   and _matured(c.anchor, as_of) and _complete(c.outcomes, outcome_version)
                   and not in_episode_exclusion(c.anchor, windows)), key=lambda c: c.anchor)
    used: set = set()
    out = {}
    for ev in sorted(events, key=lambda e: (e.anchor, e.event_id)):
        if ev.prior_1h_tercile is None:
            out[ev.event_id] = []
            continue
        ranked = sorted((c for c in pool if c.anchor not in used
                         and c.prior_1h_tercile == ev.prior_1h_tercile
                         and _hour_distance(c.anchor, ev.anchor) <= MATCHED_HOUR_TOLERANCE),
                        key=lambda c: (abs((c.anchor - ev.anchor).total_seconds()), c.anchor))
        chosen = ranked[:MATCHED_MAX_CONTROLS]
        used.update(c.anchor for c in chosen)
        out[ev.event_id] = chosen
    return out


# ---- aggregation --------------------------------------------------------------------
def sufficiency(anchors: Sequence[datetime], rule: DisplaySufficiency = DISPLAY_SUFFICIENCY) -> dict:
    n, dates = len(anchors), len({a.astimezone(timezone.utc).date() for a in anchors})
    reason = INSUFFICIENT_EVENTS if n < rule.min_events else (
        INSUFFICIENT_UTC_DATES if dates < rule.min_utc_dates else None)
    return {"count": n, "distinct_utc_dates": dates, "display_eligible": reason is None,
            "not_eligible_reason": reason}


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def summarize(identity: EventComparability, events: Sequence[EventObservation],
              candidates: Sequence[ControlCandidate], episode_windows: Sequence[EpisodeWindow], *,
              as_of: datetime, provenances: Sequence[str] = PROVENANCES,
              rule: DisplaySufficiency = DISPLAY_SUFFICIENCY) -> dict:
    """Deterministic descriptive summary: {'user_facing': ..., 'details': ...}."""
    _utc(as_of, "as_of")
    provenances = tuple(p for p in PROVENANCES if p in set(provenances))
    if not provenances:
        raise FollowUpError("at least one provenance class must be included")
    seen = set()
    for e in events:
        _utc(e.anchor, "event anchor")
        if e.provenance not in PROVENANCES:
            raise FollowUpError(f"unknown provenance {e.provenance!r}")
        if e.event_id in seen:
            raise FollowUpError(f"duplicate event {e.event_id}")
        seen.add(e.event_id)
    by_anchor: dict = {}
    for c in candidates:
        _utc(c.anchor, "control anchor")
        if c.provenance not in PROVENANCES:
            raise FollowUpError(f"unknown provenance {c.provenance!r}")
        if c.anchor in by_anchor:
            raise FollowUpError(f"duplicate control anchor {_iso(c.anchor)}")
        by_anchor[c.anchor] = c
    ov = identity.outcome_version

    excluded: dict = {}
    included = []
    for e in sorted(events, key=lambda x: (x.anchor, x.event_id)):
        why = ("NOT_COMPARABLE" if e.comparability_digest != identity.digest else
               "PROVENANCE_NOT_INCLUDED" if e.provenance not in provenances else
               "NOT_MATURED" if not _matured(e.anchor, as_of) else
               "OUTCOME_NOT_COMPLETE" if not _complete(e.outcomes, ov) else None)
        if why:
            excluded[why] = excluded.get(why, 0) + 1
        else:
            included.append(e)

    head = sufficiency([e.anchor for e in included], rule)
    user = {"block": FOLLOW_UP_VERSION, "horizons": list(FOLLOW_UP_HORIZONS), "outcome": FOLLOW_UP_OUTCOME,
            "events": head, "event_range_median_pct": None,
            "ordinary_same_time_baseline": None, "volatility_matched": None}
    details = {"comparability_digest": identity.digest, "comparability_payload": dict(identity.payload),
               "as_of": _iso(as_of), "included_provenances": list(provenances),
               "sufficiency_rule": {"min_events": rule.min_events, "min_utc_dates": rule.min_utc_dates},
               "parameters": {"episode_exclusion_h": 4, "ordinary_lookback_days": ORDINARY_LOOKBACK_DAYS,
                              "ordinary_min_controls_per_event": ORDINARY_MIN_CONTROLS_PER_EVENT,
                              "matched_hour_tolerance_h": MATCHED_HOUR_TOLERANCE,
                              "matched_max_controls": MATCHED_MAX_CONTROLS,
                              "matched_min_controls": MATCHED_MIN_CONTROLS,
                              "tercile_window_days": 30, "tercile_min_reference": TERCILE_MIN_REFERENCE},
               "excluded_events": dict(sorted(excluded.items())),
               "event_provenance": _prov_counts(included)}
    if not head["display_eligible"]:
        return _finish(user, details)                  # counts only; no statistic is computed

    user["event_range_median_pct"] = {
        h: _median([e.outcomes[h].realized_range_pct for e in included]) for h in FOLLOW_UP_HORIZONS}

    # Ordinary same-time baseline: one number per event (median of its controls).
    ordinary, ord_counts, ord_ctrls = {}, {}, []
    for e in included:
        ctrls = select_ordinary_controls(e, by_anchor, episode_windows, outcome_version=ov,
                                         provenances=provenances)
        ord_counts[e.event_id] = len(ctrls)
        if len(ctrls) >= ORDINARY_MIN_CONTROLS_PER_EVENT:
            ordinary[e.event_id] = {h: _median([c.outcomes[h].realized_range_pct for c in ctrls])
                                    for h in FOLLOW_UP_HORIZONS}
            ord_ctrls.extend(ctrls)
    ord_events = [e for e in included if e.event_id in ordinary]
    osec = sufficiency([e.anchor for e in ord_events], rule)
    if osec["display_eligible"]:
        osec["range_median_pct"] = {h: _median([ordinary[e.event_id][h] for e in ord_events])
                                    for h in FOLLOW_UP_HORIZONS}
    user["ordinary_same_time_baseline"] = osec
    details["ordinary"] = {"controls_per_event": ord_counts,
                           "control_provenance": _prov_counts({c.anchor: c for c in ord_ctrls}.values())}

    # Volatility-matched baseline (descriptive comparison; no test statistic).
    matched = select_matched_controls(included, candidates, episode_windows, outcome_version=ov,
                                      provenances=provenances, as_of=as_of)
    comp = [e for e in included if len(matched[e.event_id]) >= MATCHED_MIN_CONTROLS]
    msec = sufficiency([e.anchor for e in comp], rule)
    if msec["display_eligible"]:
        by_h = {}
        for h in FOLLOW_UP_HORIZONS:
            diffs = [e.outcomes[h].realized_range_pct
                     - statistics.fmean(c.outcomes[h].realized_range_pct for c in matched[e.event_id])
                     for e in comp]
            by_h[h] = {"comparisons": len(diffs), "median_difference_pct_points": _median(diffs),
                       "event_above_baseline_count": sum(1 for d in diffs if d > 0)}
        msec["by_horizon"] = by_h
    user["volatility_matched"] = msec
    details["matched"] = {
        "controls": {e.event_id: [_iso(c.anchor) for c in matched[e.event_id]] for e in included},
        "events_without_prior_volatility": sum(1 for e in included if e.prior_1h_tercile is None),
        "control_provenance": _prov_counts(c for cs in matched.values() for c in cs)}
    return _finish(user, details)


def _prov_counts(items: Iterable[Any]) -> dict:
    counts = {p: 0 for p in PROVENANCES}
    for x in items:
        counts[x.provenance] += 1
    return counts


def _finish(user: dict, details: dict) -> dict:
    out = {"user_facing": user, "details": details}
    out["summary_digest"] = hashlib.sha256(canonical_json(out).encode("utf-8")).hexdigest()
    return out


def summary_json(summary: Mapping[str, Any]) -> str:
    return canonical_json(summary)


# ---- formatter foundation (NOT wired into /btc) --------------------------------------
# Past-tense, descriptive only. Beyond assert_descriptive, the block rejects
# forward-looking or directional words outright.
_BLOCK_FORBIDDEN = [r"\bnext\b", r"\bexpect", r"\bedge\b", r"\bodds\b", r"\bchance", r"\bwill\b",
                    r"\bbullish\b", r"\bbearish\b", r"(?<!-)\bup\b", r"(?<!-)\bdown\b", r"\blong\b", r"\bshort\b",
                    r"\bprobab", r"\blikel", r"\bforecast", r"\bpredict", r"\bsignal", r"\balpha\b",
                    r"\bconfidence\b", r"\bp-value\b", r"\bsignifican"]


def assert_follow_up_wording(text: str) -> str:
    assert_descriptive(text)
    plain = re.sub(r"<[^>]+>", " ", text)
    for pat in _BLOCK_FORBIDDEN:
        if re.search(pat, plain, flags=re.IGNORECASE):
            raise ValueError(f"forbidden follow-up wording matched {pat!r}")
    return text


def _pct(v: float) -> str:
    return f"{v:.2f}%"


def _n(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def format_historical_follow_up(summary: Mapping[str, Any]) -> str:
    u = summary["user_facing"]
    if u.get("block") != FOLLOW_UP_VERSION or tuple(u.get("horizons") or ()) != FOLLOW_UP_HORIZONS:
        raise FollowUpError("not a HISTORICAL_FOLLOW_UP_V0 summary")
    ev = u["events"]
    lines = ["<b>HISTORICAL FOLLOW-UP</b>"]
    if not ev["display_eligible"]:
        lines += ["Limited comparable history",
                  f"{_n(ev['count'], 'event')} across {_n(ev['distinct_utc_dates'], 'day')}",
                  "More history is being collected"]
        return assert_follow_up_wording("\n".join(lines))
    lines += [f"{_n(ev['count'], 'comparable event')} · {_n(ev['distinct_utc_dates'], 'day')}", "",
              "After previous events:"]
    lines += [f"{h} range · median {_pct(u['event_range_median_pct'][h])}" for h in FOLLOW_UP_HORIZONS]
    o = u["ordinary_same_time_baseline"]
    lines += ["", "Ordinary same-time baseline:"]
    if o["display_eligible"]:
        suffix = "" if o["count"] == ev["count"] else f" ({_n(o['count'], 'event')})"
        lines += [f"{h} · {_pct(o['range_median_pct'][h])}{suffix}" for h in FOLLOW_UP_HORIZONS]
    else:
        lines.append("limited comparable history")
    m = u["volatility_matched"]
    lines += ["", "Matched for prior volatility:"]
    if m["display_eligible"]:
        for h in FOLLOW_UP_HORIZONS:
            b = m["by_horizon"][h]
            lines.append(f"{h} range exceeded matched baseline in "
                         f"{b['event_above_baseline_count']} of {b['comparisons']} events")
    else:
        lines.append("limited comparable history")
    return assert_follow_up_wording("\n".join(html.escape(x, quote=False) if not x.startswith("<b>") else x
                                              for x in lines))
