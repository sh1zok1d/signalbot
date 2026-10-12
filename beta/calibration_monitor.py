"""Calibration monitor V2 for touch and «ни один» probabilities.

This module scores an immutable claim journal. It does not read coefficients, refit a model,
or change the live V1 wording (`beta.claims.touch_wording`, health key `touch_live_cal`).

The estimand is the procedure that issued the probabilities (claim class, evaluation rule,
horizon), not a coefficient snapshot. Snapshot ids are recorded and never reset the evidence.
A nightly refit therefore cannot erase a divergence that the journal still supports.

Time index is the UTC day. Inside a day, claims that share a horizon-length slot are one
market path: the slot is averaged first, then slots are averaged with equal weight. The
sequential test is a mixture e-process on that daily statistic, so overlapping claims do not
multiply the evidence.

Channels, per procedure × family × horizon:

- LEVEL: mean residual y − p. Catches a shift of the whole horizon.
- TAIL_HIGH / TAIL_LOW: the same residual on p ≥ 0.70 and p < 0.30. A horizon whose average
  residual is near zero can still be wrong in the tails.
- SHAPE: residual on p ≥ 0.5 minus residual on p < 0.5, inside slots that have both halves.
  This is the slope failure the average residual misses.

Thresholds below were fixed before any replay of October 2026 and are not fit to it.
The 5 pp practical gate is the product tolerance already in
`docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md`. The day floors and the e-process bounds are
round predeclared information floors, longer than V1's 5-day bootstrap.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence

MONITOR_VERSION = "CALIBRATION_MONITOR_V2"
PROCEDURE_TOUCH_CHANCE = "TOUCH_CHANCE_PROCEDURE_V1"
# V1 health component stays `touch_live_cal`. Shadow output uses another name so a later
# recorder cannot overwrite the live sticky flags.
SHADOW_COMPONENT = "touch_cal_monitor_v2"

FAMILIES = ("touch", "neither")
HORIZONS = ("1h", "4h", "24h")
HORIZON_SECONDS = {"1h": 3600, "4h": 14400, "24h": 86400}
CHANNELS = ("LEVEL", "TAIL_HIGH", "TAIL_LOW", "SHAPE")

TAIL_HIGH_P = 0.70
TAIL_LOW_P = 0.30
SHAPE_SPLIT_P = 0.50
# Symmetric bets. |λ| ≤ 0.5 keeps 1 + λx > 0 for every daily statistic in [-1, 1].
LAMBDAS = (-0.5, -0.25, 0.25, 0.5)
MONITOR_SEED = 20261005

MIN_DAYS_SUSPECT = 10
MIN_DAYS_CONFIRM = 20
RECOVERY_DAYS = 20
CHECKPOINT_DAY = 28
E_SUSPECT = 2.0
E_CONFIRM = 20.0
# One predeclared look. α = 0.025, so a bootstrap percentile interval uses 1.25% / 98.75%.
CHECKPOINT_ALPHA = 0.025
PRACTICAL_ABS = 0.05
INCOMPLETE_FRACTION = 0.20
INCOMPLETE_MIN_ROWS = 10
BOOTSTRAP_REPS = 2000

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


def _mix_e(log_wealth: list) -> float:
    if not log_wealth:
        return 1.0
    peak = max(log_wealth)
    acc = sum(math.exp(item - peak) for item in log_wealth)
    return math.exp(peak + math.log(acc / len(log_wealth)))


def _update(log_wealth: list, statistic: float) -> None:
    bounded = min(1.0, max(-1.0, statistic))
    for index, lam in enumerate(LAMBDAS):
        log_wealth[index] += math.log1p(lam * bounded)


def _direction(log_wealth: list) -> int:
    best = max(range(len(LAMBDAS)), key=lambda index: log_wealth[index])
    return 1 if LAMBDAS[best] > 0 else -1


def _bootstrap_interval(values: Sequence[float], *, seed: int) -> Optional[list]:
    """Percentile interval of the day-mean. Returns None when there is nothing to resample."""
    import numpy as np

    sample = np.asarray(list(values), dtype=float)
    if sample.size == 0:
        return None
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, sample.size, size=(BOOTSTRAP_REPS, sample.size))
    means = sample[draws].mean(axis=1)
    tail = CHECKPOINT_ALPHA / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return [float(low), float(high)]


def _book_seed(procedure_id: str, family: str, horizon: str) -> int:
    text = f"{MONITOR_SEED}|{procedure_id}|{family}|{horizon}"
    acc = MONITOR_SEED
    for char in text:
        acc = (acc * 131 + ord(char)) % 2_147_483_647
    return acc


class _Channel:
    def __init__(self) -> None:
        self.days: list = []          # (ordinal, iso, estimate, e-process input)
        self.episodes: list = []
        self.operating_start = 0
        self.log_wealth = [0.0 for _ in LAMBDAS]
        self.open_episode = None
        self.checkpoint_used = False

    def add(self, ordinal: int, iso: str, estimate: float, e_input: float) -> None:
        self.days.append((ordinal, iso, float(estimate), float(e_input)))
        self._advance()

    def _operating(self) -> list:
        return self.days[self.operating_start:]

    def _advance(self) -> None:
        _ordinal, iso, estimate, e_input = self.days[-1]
        if self.open_episode is None:
            _update(self.log_wealth, e_input)
            operating = self._operating()
            count = len(operating)
            mean = sum(item[2] for item in operating) / count
            evidence = _mix_e(self.log_wealth)
            agrees = _direction(self.log_wealth) == (1 if mean > 0 else -1 if mean < 0 else 0)
            if (not self.checkpoint_used and count == CHECKPOINT_DAY and agrees
                    and abs(mean) > PRACTICAL_ABS):
                self.checkpoint_used = True
                interval = _bootstrap_interval([item[2] for item in operating], seed=self.checkpoint_seed)
                excludes = bool(interval and (interval[0] > 0.0 or interval[1] < 0.0))
                if excludes:
                    self._confirm(iso, mean, evidence, "CHECKPOINT_DAY_28", interval)
                    return
            if (count >= MIN_DAYS_CONFIRM and evidence >= E_CONFIRM and agrees
                    and abs(mean) > PRACTICAL_ABS):
                self._confirm(iso, mean, evidence, "E_PROCESS", None)
            return
        # A trailing window, not an e-value that starts at confirmation. An e-value inflated
        # by the failing stretch does not drift back to 1, so it cannot be the recovery test.
        # The archived e-value stays on the episode. Only days after confirmation are eligible,
        # and only the latest RECOVERY_DAYS of them are scored.
        after = self.days[self.open_episode["confirm_index"] + 1:]
        if len(after) < RECOVERY_DAYS:
            return
        window = after[-RECOVERY_DAYS:]
        log_wealth = [0.0 for _ in LAMBDAS]
        for item in window:
            _update(log_wealth, item[3])
        recovery_mean = sum(item[2] for item in window) / RECOVERY_DAYS
        recovery_e = _mix_e(log_wealth)
        if recovery_e < E_SUSPECT and abs(recovery_mean) <= PRACTICAL_ABS:
            self.open_episode["recovered_on"] = iso
            self.open_episode["recovery_e"] = recovery_e
            self.open_episode["recovery_estimate"] = recovery_mean
            self.episodes.append(self.open_episode)
            self.open_episode = None
            self.operating_start = len(self.days) - RECOVERY_DAYS
            self.log_wealth = log_wealth
            self.checkpoint_used = False

    def _confirm(self, iso: str, mean: float, evidence: float, via: str, interval) -> None:
        self.open_episode = {
            "confirmed_on": iso, "confirmed_by": via, "estimate_at_confirm": mean,
            "e_at_confirm": evidence, "interval_at_confirm": interval,
            "confirm_index": len(self.days) - 1,
            "recovered_on": None, "archived_e": evidence,
        }

    def snapshot(self) -> dict:
        operating = self._operating()
        if not self.days:
            return {"state": "ABSENT", "n_days": 0}
        count = len(operating)
        mean = sum(item[2] for item in operating) / count if count else 0.0
        evidence = _mix_e(self.log_wealth) if count else 1.0
        if self.open_episode is not None:
            state = STATE_CONFIRMED
        elif count < MIN_DAYS_SUSPECT:
            state = STATE_INSUFFICIENT
        elif abs(mean) > PRACTICAL_ABS and evidence >= E_SUSPECT and count >= MIN_DAYS_SUSPECT:
            sign = 1 if mean > 0 else -1
            state = STATE_SUSPECTED if _direction(self.log_wealth) == sign else STATE_NOISE
        elif self.episodes and self.episodes[-1].get("recovered_on"):
            state = STATE_RECOVERED
        else:
            state = STATE_NOISE
        closed = []
        for item in self.episodes:
            episode = dict(item)
            episode.pop("confirm_index", None)
            closed.append(episode)
        if self.open_episode is not None:
            episode = dict(self.open_episode)
            after = self.days[episode["confirm_index"] + 1:]
            episode["recovery_days"] = len(after)
            if len(after) >= RECOVERY_DAYS:
                window = after[-RECOVERY_DAYS:]
                episode["recovery_estimate"] = sum(item[2] for item in window) / RECOVERY_DAYS
            episode.pop("confirm_index", None)
            closed.append(episode)
        return {
            "state": state,
            "n_days": count,
            "estimate": mean if count else None,
            "e_value": evidence if count else None,
            "episodes": closed,
        }


def _prepare(rows: Sequence[Mapping]) -> tuple:
    """Split rows into complete observations and book-level faults.

    A book is one procedure, one family, one horizon. Mixed evaluation rules or an illegal
    probability are a technical fault. Too many unfinished outcomes are incomplete data.
    """
    faults: dict = {}
    incomplete: dict = {}
    grouped: dict = {}
    counts: dict = {}

    def bucket(key):
        faults.setdefault(key, [])
        counts.setdefault(key, {"rows": 0, "unfinished": 0})
        grouped.setdefault(key, [])

    for raw in rows:
        procedure = str(raw.get("procedure_id") or PROCEDURE_TOUCH_CHANCE)
        family = raw.get("family")
        horizon = raw.get("horizon")
        if family not in FAMILIES or horizon not in HORIZONS:
            key = (procedure, str(family), str(horizon))
            bucket(key)
            faults[key].append("FAMILY_OR_HORIZON")
            continue
        key = (procedure, family, horizon)
        bucket(key)
        counts[key]["rows"] += 1
        status = str(raw.get("status") or ("COMPLETE" if raw.get("outcome") is not None else "MISSING"))
        moment = _as_utc(raw.get("as_of"))
        if moment is None:
            faults[key].append("AS_OF_NOT_UTC")
            continue
        rule = raw.get("eval_rule_id")
        if not rule:
            faults[key].append("EVAL_RULE_MISSING")
            continue
        if status != "COMPLETE":
            counts[key]["unfinished"] += 1
            continue
        probability = _finite_probability(raw.get("probability"))
        outcome = _outcome_bit(raw.get("outcome"))
        if probability is None or outcome is None:
            faults[key].append("PROBABILITY_OR_OUTCOME")
            continue
        grouped[key].append({
            "as_of": moment,
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
            incomplete[key] = {"rows": total, "unfinished": unfinished}
        if not faults[key] and key not in incomplete:
            ready[key] = items
    return ready, faults, incomplete


def _channel_days(items: Sequence[Mapping]) -> dict:
    """Equal-slot daily statistics. A day with no claim in a channel is omitted there."""
    by_day: dict = {}
    for item in items:
        by_day.setdefault(item["day"], {"iso": item["iso"], "slots": {}})
        slot = by_day[item["day"]]["slots"].setdefault(item["slot"], [])
        slot.append(item)
    out = {name: [] for name in CHANNELS}
    for ordinal in sorted(by_day):
        block = by_day[ordinal]
        level, high, low, shape = [], [], [], []
        for claims in block["slots"].values():
            level.append(sum(item["y"] - item["p"] for item in claims) / len(claims))
            highs = [item for item in claims if item["p"] >= TAIL_HIGH_P]
            lows = [item for item in claims if item["p"] < TAIL_LOW_P]
            upper = [item for item in claims if item["p"] >= SHAPE_SPLIT_P]
            lower = [item for item in claims if item["p"] < SHAPE_SPLIT_P]
            if highs:
                high.append(sum(item["y"] - item["p"] for item in highs) / len(highs))
            if lows:
                low.append(sum(item["y"] - item["p"] for item in lows) / len(lows))
            if upper and lower:
                up = sum(item["y"] - item["p"] for item in upper) / len(upper)
                down = sum(item["y"] - item["p"] for item in lower) / len(lower)
                shape.append(up - down)
        iso = block["iso"]
        if level:
            out["LEVEL"].append((ordinal, iso, sum(level) / len(level), sum(level) / len(level)))
        if high:
            value = sum(high) / len(high)
            out["TAIL_HIGH"].append((ordinal, iso, value, value))
        if low:
            value = sum(low) / len(low)
            out["TAIL_LOW"].append((ordinal, iso, value, value))
        if shape:
            value = sum(shape) / len(shape)
            out["SHAPE"].append((ordinal, iso, value, value / 2.0))
    return out


def _score_channels(items: Sequence[Mapping], *, seed: int) -> dict:
    daily = _channel_days(items)
    scored = {}
    for name in CHANNELS:
        channel = _Channel()
        channel.checkpoint_seed = seed + CHANNELS.index(name) * 1009
        for ordinal, iso, estimate, e_input in daily[name]:
            channel.add(ordinal, iso, estimate, e_input)
        snap = channel.snapshot()
        snap["channel"] = name
        scored[name] = snap
    return scored


def _rollup(channels: Mapping[str, Mapping]) -> str:
    present = [item for item in channels.values() if item["state"] != "ABSENT"]
    if not present:
        return STATE_INSUFFICIENT
    states = {item["state"] for item in present}
    if STATE_CONFIRMED in states:
        return STATE_CONFIRMED
    if STATE_SUSPECTED in states:
        return STATE_SUSPECTED
    if STATE_RECOVERED in states and states <= {STATE_RECOVERED, STATE_NOISE, STATE_INSUFFICIENT}:
        return STATE_RECOVERED
    if STATE_NOISE in states or STATE_RECOVERED in states:
        return STATE_NOISE if STATE_RECOVERED not in states else STATE_RECOVERED
    return STATE_INSUFFICIENT


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


def evaluate(observations: Sequence[Mapping]) -> dict:
    """Replay the journal. The same observations always produce the same books."""
    ready, faults, incomplete = _prepare(list(observations))
    books = []
    keys = sorted(set(ready) | set(faults) | set(incomplete), key=lambda item: tuple(str(part) for part in item))
    for key in keys:
        procedure, family, horizon = key
        if faults.get(key):
            state = STATE_FAULT
            channels = {}
            reason = sorted(set(faults[key]))
        elif key in incomplete:
            state = STATE_INCOMPLETE
            channels = {}
            reason = [incomplete[key]]
        else:
            channels = _score_channels(ready[key], seed=_book_seed(procedure, family, horizon))
            state = _rollup(channels)
            reason = []
        items = ready.get(key) or []
        books.append({
            "monitor_version": MONITOR_VERSION,
            "procedure_id": procedure,
            "family": family,
            "horizon": horizon,
            "state": state,
            "user_action": user_action(state),
            "reason": reason,
            "channels": channels,
            "n_claims": len(items),
            "n_slots": len({item["slot"] for item in items}),
            "n_days": len({item["day"] for item in items}),
            "eval_rule_ids": sorted({item["rule"] for item in items}),
            "snapshot_ids": sorted({item["snapshot"] for item in items if item["snapshot"]}),
            "snapshot_policy": "RECORDED_NOT_RESET",
        })
    return {"monitor_version": MONITOR_VERSION, "shadow_component": SHADOW_COMPONENT, "books": books}
