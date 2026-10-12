"""Calibration monitor V2 for touch and «ни один» probabilities.

This module scores an immutable claim journal. It does not read coefficients, refit a model,
or change the live V1 wording (`beta.claims.touch_wording`, health key `touch_live_cal`).

The estimand is the procedure that issued the probabilities (claim class, evaluation rule,
horizon), not a coefficient snapshot. Snapshot ids are recorded and never reset the evidence.
A nightly refit therefore cannot erase a divergence that the journal still supports.

Filtration. A claim issued at t with horizon H is settled by prices on (t, t+H]. The next bet
is valid only when every claim already inside the e-process has resolved before this claim is
issued. Candidate claims are those issued in the first hour of a horizon slot. One slot is one
averaged step. The greedy chain keeps a slot only when its issue time is at or after the
previous included slot's resolution, so 4h and 24h overlap cannot multiply evidence. Claims
outside that chain are counted and then ignored by the decision statistic.

Channels, per procedure × family × horizon, are averaged into one mixture e-process per book.
Six books are predeclared (touch and neither, each at 1h, 4h and 24h). Ville's inequality plus
a union bound gives the false-confirm guarantee below. Thresholds were fixed before any replay
of October 2026 and are not fit to it. `variants_tried_for_thresholds = 0`.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

MONITOR_VERSION = "CALIBRATION_MONITOR_V2"
PROCEDURE_TOUCH_CHANCE = "TOUCH_CHANCE_PROCEDURE_V1"
# Rows written before a procedure carried a specification stay in one book. A named
# spec_id, such as a Rangecast V2 specification, is a separate book. The e-value
# thresholds are not recomputed when another procedure is added: each specification
# is its own family of six books.
JOURNAL_SPEC_ID = "JOURNAL_UNSPECIFIED"
# V1 health component stays `touch_live_cal`. Shadow output uses another name so a later
# recorder cannot overwrite the live sticky flags.
SHADOW_COMPONENT = "touch_cal_monitor_v2"

FAMILIES = ("touch", "neither")
HORIZONS = ("1h", "4h", "24h")
HORIZON_SECONDS = {"1h": 3600, "4h": 14400, "24h": 86400}
CHANNELS = ("LEVEL", "TAIL_HIGH", "TAIL_LOW", "SHAPE")
# First hour of a horizon slot. Production claims are issued one minute after the bar, so
# they fall in this window. A claim later in the slot overlaps the next slot's prices.
ANCHOR_WIDTH_S = 3600
HORIZON_TOLERANCE_S = 2.0
# Same full-window fraction as beta.claims.COVERAGE_MIN. A partial window is unfinished for
# both outcomes: production marks an early touch COMPLETE and a quiet partial window NO_DATA,
# and scoring only the touch would push the touch rate up.
COVERAGE_MIN = 0.9

TAIL_HIGH_P = 0.70
TAIL_LOW_P = 0.30
SHAPE_SPLIT_P = 0.50
# Symmetric bets. |λ| ≤ 0.5 keeps 1 + λx > 0 for every statistic in [-1, 1].
LAMBDAS = (-0.5, -0.25, 0.25, 0.5)
MONITOR_SEED = 20261005

# Six books, one mixture e-process each. Confirming when E >= 6 / 0.10 means that the
# probability of any book ever confirming, under a calibrated procedure, is at most 10%,
# at any time, whether or not the books share a price path. Suspicion uses the same process
# at 6 / 0.30. The two thresholds are nested, so the confirm guarantee is not added on top
# of the suspect guarantee.
N_PREDECLARED_BOOKS = 6
CONFIRM_ALPHA_UNION = 0.10
SUSPECT_ALPHA_UNION = 0.30
MIN_DAYS_SUSPECT = 10
MIN_DAYS_CONFIRM = 20
RECOVERY_DAYS = 20
E_SUSPECT = N_PREDECLARED_BOOKS / SUSPECT_ALPHA_UNION
E_CONFIRM = N_PREDECLARED_BOOKS / CONFIRM_ALPHA_UNION
RECOVERY_E_MAX = 2.0
PRACTICAL_ABS = 0.05
INCOMPLETE_FRACTION = 0.20
INCOMPLETE_MIN_ROWS = 10
# A forecast whose horizon has not elapsed is PENDING. It is outside the unfinished
# fraction and outside the scored set. A missing outcome after the horizon is a hole.
PENDING_STATUS = "PENDING"
VARIANTS_TRIED_FOR_THRESHOLDS = 0

STATE_INSUFFICIENT = "INSUFFICIENT_DATA"
STATE_NOISE = "WITHIN_NOISE"
STATE_SUSPECTED = "SUSPECTED_DEGRADATION"
STATE_CONFIRMED = "CONFIRMED_DIVERGENCE"
STATE_RECOVERED = "RECOVERED"
STATE_FAULT = "TECHNICAL_FAULT"
STATE_INCOMPLETE = "INCOMPLETE_DATA"

ACTION_NO_OVERRIDE = "NO_V2_OVERRIDE"
ACTION_WITHHOLD_PROBABILITY = "WITHHOLD_MODEL_PROBABILITY"
ACTION_WITHHOLD_FIGURE = "WITHHOLD_FIGURE"

_DIGEST_STATES = (STATE_SUSPECTED, STATE_CONFIRMED, STATE_FAULT, STATE_INCOMPLETE)
_NOTABLE_STATES = _DIGEST_STATES + (STATE_RECOVERED,)
_CLASS_RE = re.compile(r"^L3_(LEVEL_TOUCH|DISTANCE_TOUCH|NEITHER)_(1H|4H|24H)$")
_FAMILY_OF = {"LEVEL_TOUCH": "touch", "DISTANCE_TOUCH": "touch", "NEITHER": "neither"}
_HORIZON_OF = {"1H": "1h", "4H": "4h", "24H": "24h"}
_RULE_OF = {"touch": "TOUCH_V1", "neither": "NEITHER_V1"}


def _as_utc(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finite_probability(value) -> Optional[float]:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(p) or p < 0.0 or p > 1.0:
        return None
    return p


def _outcome_bit(value) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in (0, 1, 0.0, 1.0):
        return float(value)
    return None


def _day_ordinal(moment: datetime) -> int:
    return int(moment.timestamp()) // 86400


def _slot_id(moment: datetime, horizon: str) -> int:
    return int(moment.timestamp()) // HORIZON_SECONDS[horizon]


def _mix_e(log_wealth: Sequence[float]) -> float:
    if not log_wealth:
        return 1.0
    peak = max(log_wealth)
    acc = sum(math.exp(item - peak) for item in log_wealth)
    return math.exp(peak + math.log(acc / len(log_wealth)))


def _update(log_wealth: list, statistic: float) -> None:
    bounded = min(1.0, max(-1.0, statistic))
    for index, lam in enumerate(LAMBDAS):
        log_wealth[index] += math.log1p(lam * bounded)


def _direction(log_wealth: Sequence[float]) -> int:
    best = max(range(len(LAMBDAS)), key=lambda index: log_wealth[index])
    return 1 if LAMBDAS[best] > 0 else -1


def mixture_peak(statistics: Sequence[float]) -> float:
    """Supremum of the λ-mixture along one sequence. Used by the overlap check."""
    logs = [0.0 for _ in LAMBDAS]
    peak = 1.0
    for statistic in statistics:
        _update(logs, float(statistic))
        peak = max(peak, _mix_e(logs))
    return peak


def _coverage_value(raw: Mapping) -> Optional[float]:
    if raw.get("coverage") is not None:
        source = raw.get("coverage")
    else:
        realized = raw.get("realized")
        if isinstance(realized, str):
            try:
                realized = json.loads(realized)
            except json.JSONDecodeError:
                return None
        if not isinstance(realized, Mapping) or realized.get("coverage") is None:
            return None
        source = realized.get("coverage")
    try:
        value = float(source)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _slot_channel_stats(claims: Sequence[Mapping]) -> dict:
    """One step per channel. Shape is halved so the e-process input stays in [-1, 1]."""
    level = [item["y"] - item["p"] for item in claims]
    highs = [item["y"] - item["p"] for item in claims if item["p"] >= TAIL_HIGH_P]
    lows = [item["y"] - item["p"] for item in claims if item["p"] < TAIL_LOW_P]
    upper = [item["y"] - item["p"] for item in claims if item["p"] >= SHAPE_SPLIT_P]
    lower = [item["y"] - item["p"] for item in claims if item["p"] < SHAPE_SPLIT_P]
    stats = {}
    if level:
        value = sum(level) / len(level)
        stats["LEVEL"] = (value, value)
    if highs:
        value = sum(highs) / len(highs)
        stats["TAIL_HIGH"] = (value, value)
    if lows:
        value = sum(lows) / len(lows)
        stats["TAIL_LOW"] = (value, value)
    if upper and lower:
        value = sum(upper) / len(upper) - sum(lower) / len(lower)
        stats["SHAPE"] = (value, value / 2.0)
    return stats


def _anchor_candidates(items: Sequence[Mapping], horizon: str) -> list:
    width = HORIZON_SECONDS[horizon]
    grouped: dict = {}
    for item in items:
        offset = int(item["as_of"].timestamp()) % width
        if offset >= ANCHOR_WIDTH_S:
            continue
        grouped.setdefault(item["slot"], []).append(item)
    candidates = []
    for slot, claims in grouped.items():
        issue = min(item["as_of"] for item in claims)
        resolution = max(item["horizon_end"] for item in claims)
        candidates.append({
            "slot": slot,
            "issue": issue,
            "resolution": resolution,
            "ordinal": _day_ordinal(issue),
            "iso": issue.date().isoformat(),
            "stats": _slot_channel_stats(claims),
        })
    candidates.sort(key=lambda item: (item["issue"], item["slot"]))
    return candidates


def _select_chain(candidates: Sequence[Mapping]) -> tuple:
    """Keep a slot only after the previous kept slot has resolved."""
    included = []
    skipped = 0
    last = None
    for candidate in candidates:
        if last is not None and candidate["issue"] < last:
            skipped += 1
            continue
        included.append(candidate)
        last = candidate["resolution"]
    return included, skipped


def _fresh_logs() -> dict:
    return {name: [0.0 for _ in LAMBDAS] for name in CHANNELS}


def _apply_slot(slot: Mapping, logs: dict, steps: dict, *, update_wealth: bool) -> None:
    for name, (estimate, e_input) in slot["stats"].items():
        if update_wealth:
            _update(logs[name], e_input)
        steps[name].append((slot["ordinal"], slot["iso"], estimate, e_input))


def _view_channel(steps: Sequence[tuple], log_wealth: Sequence[float]) -> dict:
    if not steps:
        return {"present": False, "e": 1.0, "estimate": None, "days": 0, "direction": 0}
    mean = sum(item[2] for item in steps) / len(steps)
    return {
        "present": True,
        "e": _mix_e(log_wealth),
        "estimate": mean,
        "days": len({item[0] for item in steps}),
        "direction": _direction(log_wealth),
    }


def _views(logs: Mapping, steps: Mapping) -> dict:
    return {name: _view_channel(steps[name], logs[name]) for name in CHANNELS}


def _book_e(view: Mapping) -> float:
    return sum(view[name]["e"] for name in CHANNELS) / len(CHANNELS)


def _qualifiers(view: Mapping, *, min_days: int) -> list:
    named = []
    for name in CHANNELS:
        item = view[name]
        estimate = item["estimate"]
        if not item["present"] or estimate is None:
            continue
        if item["days"] < min_days or item["e"] < E_SUSPECT or abs(estimate) <= PRACTICAL_ABS:
            continue
        sign = 1 if estimate > 0 else -1
        if item["direction"] == sign:
            named.append(name)
    return named


def _distinct_days(slots: Sequence[Mapping]) -> list:
    seen = []
    for slot in slots:
        if not seen or seen[-1] != slot["ordinal"]:
            if slot["ordinal"] not in seen:
                seen.append(slot["ordinal"])
    return seen


def _rebuild(slots: Sequence[Mapping]) -> tuple:
    logs = _fresh_logs()
    steps = {name: [] for name in CHANNELS}
    for slot in slots:
        _apply_slot(slot, logs, steps, update_wealth=True)
    return logs, steps


def _public_episode(episode: Mapping) -> dict:
    published = {
        "confirmed_on": episode["confirmed_on"],
        "confirmed_by": episode["confirmed_by"],
        "e_at_confirm": episode["e_at_confirm"],
        "archived_e": episode["archived_e"],
        "named_channels": list(episode["named_channels"]),
        "recovered_on": episode.get("recovered_on"),
        "recovery_e": episode.get("recovery_e"),
    }
    return published


def _score_book(items: Sequence[Mapping], horizon: str) -> dict:
    candidates = _anchor_candidates(items, horizon)
    included, skipped = _select_chain(candidates)
    logs = _fresh_logs()
    steps = {name: [] for name in CHANNELS}
    episodes = []
    open_episode = None
    for index, slot in enumerate(included):
        if open_episode is None:
            _apply_slot(slot, logs, steps, update_wealth=True)
            view = _views(logs, steps)
            evidence = _book_e(view)
            day_count = len({item[0] for name in CHANNELS for item in steps[name]})
            if (day_count >= MIN_DAYS_CONFIRM and evidence >= E_CONFIRM
                    and _qualifiers(view, min_days=MIN_DAYS_CONFIRM)):
                named = _qualifiers(view, min_days=MIN_DAYS_CONFIRM)
                open_episode = {
                    "confirmed_on": slot["iso"],
                    "confirmed_by": "BOOK_E_PROCESS",
                    "e_at_confirm": evidence,
                    "archived_e": evidence,
                    "named_channels": named,
                    "confirm_index": index,
                    "confirm_ordinal": slot["ordinal"],
                    "recovered_on": None,
                }
            continue
        # Wealth keeps moving after confirmation so a channel that was still quiet at the
        # crossing can be named once its own evidence arrives. The archived e-value stays
        # the value at the crossing. Recovery does not use this wealth: an e-value that
        # has already grown does not drift back down.
        _apply_slot(slot, logs, steps, update_wealth=True)
        view = _views(logs, steps)
        for name in _qualifiers(view, min_days=MIN_DAYS_CONFIRM):
            if name not in open_episode["named_channels"]:
                open_episode["named_channels"].append(name)
        after = [item for item in included[open_episode["confirm_index"] + 1:]
                 if item["ordinal"] > open_episode["confirm_ordinal"]]
        days = _distinct_days(after)
        if len(days) < RECOVERY_DAYS:
            continue
        keep = set(days[-RECOVERY_DAYS:])
        window = [item for item in after if item["ordinal"] in keep]
        fresh_logs, fresh_steps = _rebuild(window)
        fresh = _views(fresh_logs, fresh_steps)
        present = [fresh[name] for name in CHANNELS if fresh[name]["present"]]
        if not present:
            continue
        if _book_e(fresh) < RECOVERY_E_MAX and all(abs(item["estimate"]) <= PRACTICAL_ABS for item in present):
            open_episode["recovered_on"] = slot["iso"]
            open_episode["recovery_e"] = _book_e(fresh)
            episodes.append(open_episode)
            open_episode = None
            logs, steps = fresh_logs, fresh_steps
    view = _views(logs, steps)
    evidence = _book_e(view) if any(item["present"] for item in view.values()) else 1.0
    day_count = len({item[0] for name in CHANNELS for item in steps[name]})
    if open_episode is not None:
        state = STATE_CONFIRMED
        named_now = list(open_episode["named_channels"])
    elif day_count < MIN_DAYS_SUSPECT:
        state = STATE_INSUFFICIENT
        named_now = []
    else:
        suspected = _qualifiers(view, min_days=MIN_DAYS_SUSPECT)
        if evidence >= E_SUSPECT and suspected:
            state = STATE_SUSPECTED
            named_now = suspected
        elif episodes and episodes[-1].get("recovered_on"):
            state = STATE_RECOVERED
            named_now = []
        else:
            state = STATE_NOISE
            named_now = []
    closed = [_public_episode(item) for item in episodes]
    if open_episode is not None:
        closed.append(_public_episode(open_episode))
    channels = {}
    for name in CHANNELS:
        item = view[name]
        if not item["present"]:
            channel_state = "ABSENT"
        elif open_episode is not None and name in open_episode["named_channels"]:
            channel_state = STATE_CONFIRMED
        elif state == STATE_SUSPECTED and name in named_now:
            channel_state = STATE_SUSPECTED
        elif state == STATE_RECOVERED and any(name in episode["named_channels"] for episode in episodes):
            channel_state = STATE_RECOVERED
        elif item["days"] < MIN_DAYS_SUSPECT:
            channel_state = STATE_INSUFFICIENT
        else:
            channel_state = STATE_NOISE
        channel_episodes = [episode for episode in closed if name in episode["named_channels"]]
        channels[name] = {
            "channel": name,
            "state": channel_state,
            "n_days": item["days"],
            "estimate": item["estimate"],
            "e_value": item["e"] if item["present"] else None,
            "episodes": channel_episodes,
        }
    return {
        "state": state,
        "e_value": evidence,
        "n_days": day_count,
        "n_included_slots": len(included),
        "n_candidate_slots": len(candidates),
        "n_skipped_overlapping": skipped,
        "channels": channels,
        "episodes": closed,
        "filtration": "NON_OVERLAPPING_ANCHOR",
    }


def _prepare(rows: Sequence[Mapping]) -> tuple:
    """Split rows into scored observations and book-level faults.

    A book is one procedure, one specification, one family, one horizon. Two forecast
    procedures never share a book. Mixed evaluation rules, an illegal probability, or a
    horizon window that is not the claimed horizon are technical faults.
    A partial price window is unfinished for a hit and for a miss alike.
    A PENDING row is not yet due. It does not enter the row count or the unfinished
    fraction, so an open 24h horizon cannot by itself make the book INCOMPLETE_DATA.
    """
    faults: dict = {}
    incomplete: dict = {}
    grouped: dict = {}
    counts: dict = {}

    def bucket(key):
        faults.setdefault(key, [])
        counts.setdefault(key, {"rows": 0, "unfinished": 0, "low_coverage": 0, "pending": 0})
        grouped.setdefault(key, [])

    for raw in rows:
        procedure = str(raw.get("procedure_id") or PROCEDURE_TOUCH_CHANCE)
        spec = str(raw.get("spec_id") or JOURNAL_SPEC_ID)
        family = raw.get("family")
        horizon = raw.get("horizon")
        if family not in FAMILIES or horizon not in HORIZONS:
            key = (procedure, spec, str(family), str(horizon))
            bucket(key)
            faults[key].append("FAMILY_OR_HORIZON")
            continue
        key = (procedure, spec, family, horizon)
        bucket(key)
        if raw.get("fault_reason"):
            counts[key]["rows"] += 1
            faults[key].append(str(raw["fault_reason"]))
            continue
        moment = _as_utc(raw.get("as_of"))
        if moment is None:
            counts[key]["rows"] += 1
            faults[key].append("AS_OF_NOT_UTC")
            continue
        rule = raw.get("eval_rule_id")
        if not rule:
            counts[key]["rows"] += 1
            faults[key].append("EVAL_RULE_MISSING")
            continue
        end = None
        if raw.get("horizon_end") is not None:
            end = _as_utc(raw.get("horizon_end"))
            if end is None:
                counts[key]["rows"] += 1
                faults[key].append("HORIZON_END_NOT_UTC")
                continue
            if abs((end - moment).total_seconds() - HORIZON_SECONDS[horizon]) > HORIZON_TOLERANCE_S:
                counts[key]["rows"] += 1
                faults[key].append("HORIZON_WINDOW")
                continue
        status = str(raw.get("status") or ("COMPLETE" if raw.get("outcome") is not None else "MISSING"))
        if status == PENDING_STATUS:
            counts[key]["pending"] += 1
            continue
        counts[key]["rows"] += 1
        coverage = _coverage_value(raw)
        if raw.get("coverage") is not None and coverage is None:
            faults[key].append("COVERAGE_NOT_FINITE")
            continue
        if status != "COMPLETE" or (coverage is not None and coverage < COVERAGE_MIN):
            counts[key]["unfinished"] += 1
            if coverage is not None and coverage < COVERAGE_MIN:
                counts[key]["low_coverage"] += 1
            continue
        probability = _finite_probability(raw.get("probability"))
        outcome = _outcome_bit(raw.get("outcome"))
        if probability is None or outcome is None:
            faults[key].append("PROBABILITY_OR_OUTCOME")
            continue
        if end is None:
            end = moment + timedelta(seconds=HORIZON_SECONDS[horizon])
        grouped[key].append({
            "as_of": moment,
            "horizon_end": end,
            "day": _day_ordinal(moment),
            "iso": moment.date().isoformat(),
            "slot": _slot_id(moment, horizon),
            "p": probability,
            "y": outcome,
            "rule": str(rule),
            "snapshot": None if raw.get("snapshot_id") is None else str(raw.get("snapshot_id")),
        })
    ready = {}
    for key, items in grouped.items():
        rules = {item["rule"] for item in items}
        if len(rules) > 1:
            faults[key].append("MIXED_EVAL_RULES")
        total = counts[key]["rows"]
        unfinished = counts[key]["unfinished"]
        if total >= INCOMPLETE_MIN_ROWS and unfinished / total > INCOMPLETE_FRACTION:
            incomplete[key] = {"rows": total, "unfinished": unfinished,
                               "low_coverage": counts[key]["low_coverage"]}
        if not faults[key] and key not in incomplete:
            ready[key] = items
    return ready, faults, incomplete, counts


def _blank_channels() -> dict:
    return {name: {"channel": name, "state": "ABSENT", "n_days": 0, "estimate": None,
                   "e_value": None, "episodes": []} for name in CHANNELS}


def user_action(state: str) -> dict:
    """What a surface may do with the model probability. V2 does not apply this itself.

    A confirmed gap withholds the model number. Keeping the same number under a softer
    sentence would still show the probability the check rejected. A supplied historical
    baseline is a different procedure and is not blended into the model number.
    """
    if state == STATE_CONFIRMED:
        return {
            "action": ACTION_WITHHOLD_PROBABILITY,
            "show_model_probability": False,
            "blend_model_toward_outcome": False,
            "allow_separate_baseline": True,
        }
    if state in (STATE_FAULT, STATE_INCOMPLETE):
        return {
            "action": ACTION_WITHHOLD_FIGURE,
            "show_model_probability": False,
            "blend_model_toward_outcome": False,
            "allow_separate_baseline": False,
        }
    return {
        "action": ACTION_NO_OVERRIDE,
        "show_model_probability": True,
        "blend_model_toward_outcome": False,
        "allow_separate_baseline": True,
    }


def digest_due(state: str, *, utc_day: str, last_digest_day: Optional[str],
               previous_state: Optional[str] = None) -> bool:
    """At most one owner digest per UTC day. V1's 30-minute repeat is untouched."""
    transition = state == STATE_RECOVERED and previous_state == STATE_CONFIRMED
    if state not in _DIGEST_STATES and not transition:
        return False
    return last_digest_day != utc_day


def shadow_notifications(previous: Optional[Mapping], current: Mapping, *, utc_day: str,
                         last_summary_day: Optional[str] = None) -> dict:
    """State-change notices plus one daily summary.

    A book that stays confirmed does not produce another notice. Transitions that stay
    inside insufficient/noise are not paged. This does not read or write V1 sticky flags
    and it does not change `health.owner_alert_repeat_s`.
    """
    previous_books = () if not previous else previous.get("books") or ()
    previous_state = {_notice_key(item): item["state"] for item in previous_books}
    changes = []
    for book in current.get("books") or ():
        key = _notice_key(book)
        old = previous_state.get(key)
        new = book["state"]
        if old == new:
            continue
        if old not in _NOTABLE_STATES and new not in _NOTABLE_STATES:
            continue
        changes.append({
            "kind": "STATE_CHANGED",
            "procedure_id": key[0],
            "spec_id": key[1],
            "family": key[2],
            "horizon": key[3],
            "from_state": old,
            "to_state": new,
        })
    notable = [book for book in (current.get("books") or ()) if book["state"] in _NOTABLE_STATES]
    summary = None
    stored_day = last_summary_day
    if notable and last_summary_day != utc_day:
        summary = {
            "kind": "DAILY_SUMMARY",
            "utc_day": utc_day,
            "books": [
                {"procedure_id": book["procedure_id"], "spec_id": book.get("spec_id") or JOURNAL_SPEC_ID,
                 "family": book["family"], "horizon": book["horizon"], "state": book["state"]}
                for book in notable
            ],
        }
        stored_day = utc_day
    return {
        "component": SHADOW_COMPONENT,
        "v1_component_untouched": "touch_live_cal",
        "v1_repeat_untouched": True,
        "changes": changes,
        "daily_summary": summary,
        "last_summary_day": stored_day,
    }


def _notice_key(book: Mapping) -> tuple:
    return (
        book["procedure_id"],
        book.get("spec_id") or JOURNAL_SPEC_ID,
        book["family"],
        book["horizon"],
    )


def _mapping(value):
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, Mapping) else None
    return None


def observation_from_journal_row(row: Mapping) -> Optional[dict]:
    """Map one claim plus its latest outcome into a monitor observation.

    Returns None for classes this monitor does not score. Subject, price and user fields
    are not copied. The evaluation identity is the rule digest when the journal has one,
    so two rule versions do not pool. `stats_digest` is the model snapshot; a missing
    digest falls back to `stats_pk`.
    """
    matched = _CLASS_RE.match(str(row.get("claim_class") or ""))
    if not matched:
        return None
    family = _FAMILY_OF[matched.group(1)]
    horizon = _HORIZON_OF[matched.group(2)]
    numbers = _mapping(row.get("numbers")) or {}
    probability = row.get("probability")
    if probability is None:
        probability = numbers.get("probability")
    realized = _mapping(row.get("realized")) or {}
    if row.get("outcome") is not None:
        outcome = row.get("outcome")
    elif family == "touch":
        outcome = realized.get("touched")
    else:
        outcome = realized.get("neither")
    rule_name = row.get("eval_rule_id")
    nested_rule = _mapping(row.get("eval_rule"))
    if not rule_name and isinstance(nested_rule, Mapping):
        rule_name = nested_rule.get("id")
    digest = row.get("eval_rule_digest")
    snapshot = row.get("stats_digest")
    if snapshot is None and row.get("snapshot_id") is not None:
        snapshot = row.get("snapshot_id")
    if snapshot is None and row.get("stats_pk") is not None:
        snapshot = str(row.get("stats_pk"))
    coverage = realized.get("coverage") if realized.get("coverage") is not None else row.get("coverage")
    observation = {
        "procedure_id": str(row.get("procedure_id") or PROCEDURE_TOUCH_CHANCE),
        "spec_id": str(row.get("spec_id") or JOURNAL_SPEC_ID),
        "family": family,
        "horizon": horizon,
        "as_of": row.get("as_of"),
        "horizon_end": row.get("horizon_end"),
        "probability": probability,
        "outcome": outcome,
        "status": row.get("status") or "MISSING",
        "eval_rule_id": str(digest) if digest else (str(rule_name) if rule_name else ""),
        "snapshot_id": None if snapshot is None else str(snapshot),
        "coverage": coverage,
        "rule_version": None if row.get("rule_version") is None else str(row.get("rule_version")),
    }
    if rule_name and str(rule_name) != _RULE_OF[family]:
        observation["fault_reason"] = "EVAL_RULE_FAMILY"
    return observation


def observations_from_claim_rows(rows: Sequence[Mapping], *, now: Optional[datetime] = None) -> list:
    """Drop classes this monitor does not score. Malformed touch rows are kept so they fault.

    When ``now`` is set, a row with no outcome whose horizon is still open is PENDING.
    After the horizon, a missing outcome stays a hole. The replay uses the process clock.
    """
    clock = _as_utc(now) if now is not None else None
    out = []
    for row in rows:
        observation = observation_from_journal_row(row)
        if observation is None:
            continue
        if clock is not None and _not_yet_due(observation, clock):
            observation["status"] = PENDING_STATUS
        out.append(observation)
    return out


def _not_yet_due(observation: Mapping, now: datetime) -> bool:
    status = str(observation.get("status") or "MISSING")
    if status == PENDING_STATUS:
        return True
    if status != "MISSING" or observation.get("outcome") is not None:
        return False
    end = _as_utc(observation.get("horizon_end"))
    return end is not None and end > now


def _thresholds() -> dict:
    return {
        "min_days_suspect": MIN_DAYS_SUSPECT,
        "min_days_confirm": MIN_DAYS_CONFIRM,
        "recovery_days": RECOVERY_DAYS,
        "e_suspect": E_SUSPECT,
        "e_confirm": E_CONFIRM,
        "recovery_e_max": RECOVERY_E_MAX,
        "practical_abs": PRACTICAL_ABS,
        "predeclared_books": N_PREDECLARED_BOOKS,
        "confirm_alpha_union": CONFIRM_ALPHA_UNION,
        "suspect_alpha_union": SUSPECT_ALPHA_UNION,
        "variants_tried_for_thresholds": VARIANTS_TRIED_FOR_THRESHOLDS,
        "filtration": "NON_OVERLAPPING_ANCHOR",
        "anchor_width_s": ANCHOR_WIDTH_S,
        "coverage_min": COVERAGE_MIN,
        "bound": "VILLE_UNION_OVER_PREDECLARED_BOOKS",
    }


def evaluate(observations: Sequence[Mapping]) -> dict:
    """Replay the journal. The same observations always produce the same books."""
    ready, faults, incomplete, counts = _prepare(list(observations))
    books = []
    keys = sorted(set(ready) | set(faults) | set(incomplete), key=lambda item: tuple(str(part) for part in item))
    for key in keys:
        procedure, spec, family, horizon = key
        items = ready.get(key) or []
        if faults.get(key):
            state = STATE_FAULT
            scored = {"channels": _blank_channels(), "episodes": [], "e_value": None,
                      "n_days": 0, "n_included_slots": 0, "n_candidate_slots": 0,
                      "n_skipped_overlapping": 0}
            reason = sorted(set(faults[key]))
        elif key in incomplete:
            state = STATE_INCOMPLETE
            scored = {"channels": _blank_channels(), "episodes": [], "e_value": None,
                      "n_days": 0, "n_included_slots": 0, "n_candidate_slots": 0,
                      "n_skipped_overlapping": 0}
            reason = [incomplete[key]]
        else:
            scored = _score_book(items, horizon)
            state = scored["state"]
            reason = []
        books.append({
            "monitor_version": MONITOR_VERSION,
            "procedure_id": procedure,
            "spec_id": spec,
            "family": family,
            "horizon": horizon,
            "state": state,
            "user_action": user_action(state),
            "reason": reason,
            "channels": scored["channels"],
            "episodes": scored["episodes"],
            "e_value": scored["e_value"],
            "n_claims": len(items),
            "n_rows": counts.get(key, {}).get("rows", 0),
            "n_pending": counts.get(key, {}).get("pending", 0),
            "n_unfinished": counts.get(key, {}).get("unfinished", 0),
            "n_low_coverage": counts.get(key, {}).get("low_coverage", 0),
            "n_slots": len({item["slot"] for item in items}),
            "n_days": scored["n_days"] if items else len({item["day"] for item in items}),
            "n_included_slots": scored["n_included_slots"],
            "n_candidate_slots": scored["n_candidate_slots"],
            "n_skipped_overlapping": scored["n_skipped_overlapping"],
            "filtration": "NON_OVERLAPPING_ANCHOR",
            "eval_rule_ids": sorted({item["rule"] for item in items}),
            "snapshot_ids": sorted({item["snapshot"] for item in items if item["snapshot"]}),
            "snapshot_policy": "RECORDED_NOT_RESET",
            "coverage_policy": "FULL_WINDOW_ONLY",
        })
    return {
        "monitor_version": MONITOR_VERSION,
        "shadow_component": SHADOW_COMPONENT,
        "thresholds": _thresholds(),
        "books": books,
    }
