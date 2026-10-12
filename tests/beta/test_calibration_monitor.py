"""Calibration monitor V2. The live V1 wording and sticky health key are not invoked."""
from datetime import datetime, timedelta, timezone

import numpy as np

from beta import claims as claims
from beta.calibration_monitor import (
    ACTION_NO_OVERRIDE, ACTION_WITHHOLD_FIGURE, ACTION_WITHHOLD_PROBABILITY,
    E_CONFIRM, MIN_DAYS_SUSPECT, MONITOR_VERSION, PRACTICAL_ABS, PROCEDURE_TOUCH_CHANCE,
    STATE_CONFIRMED, STATE_FAULT, STATE_INCOMPLETE, STATE_INSUFFICIENT, STATE_NOISE,
    STATE_RECOVERED, STATE_SUSPECTED, digest_due, evaluate, user_action,
)

UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)


def _rows(days, *, family="touch", horizon="4h", probabilities=(0.40,), outcome=0.0,
          every_hours=1, snapshot="snap-a", rule="TOUCH_V1", procedure=PROCEDURE_TOUCH_CHANCE,
          status="COMPLETE", probability_override=None):
    out = []
    step = timedelta(hours=every_hours)
    moment = START
    end = START + timedelta(days=days)
    index = 0
    while moment < end:
        for probability in probabilities:
            out.append({
                "procedure_id": procedure,
                "family": family,
                "horizon": horizon,
                "as_of": moment,
                "probability": probability if probability_override is None else probability_override(index, probability),
                "outcome": outcome if not callable(outcome) else outcome(index, probability),
                "status": status,
                "eval_rule_id": rule,
                "snapshot_id": snapshot,
            })
            index += 1
        moment += step
    return out


def _book(report, family="touch", horizon="4h"):
    found = [item for item in report["books"]
             if item["family"] == family and item["horizon"] == horizon]
    assert len(found) == 1
    return found[0]


def test_seven_dense_days_stay_insufficient_even_when_the_gap_is_large():
    """V1's slot count is already past 30; V2 still has fewer than the day floor."""
    report = evaluate(_rows(7, outcome=0.0, probabilities=(0.40,)))
    book = _book(report)
    assert book["state"] == STATE_INSUFFICIENT
    assert book["n_days"] == 7
    assert book["n_slots"] >= 30
    assert book["user_action"]["action"] == ACTION_NO_OVERRIDE
    assert book["monitor_version"] == MONITOR_VERSION


def test_v1_diverges_on_the_same_seven_days_the_v2_refuses():
    rows = _rows(7, outcome=0.0, probabilities=(0.40,))
    cells = {}
    for row in rows:
        day = int(row["as_of"].timestamp()) // 86400
        slot = int(row["as_of"].timestamp()) // 14400
        bin_index = 3  # [0.30, 0.50)
        key = (day, slot, bin_index)
        cell = cells.setdefault(key, {"n": 0, "hits": 0, "psum": 0.0, "day": day, "slot": slot,
                                      "bin": bin_index, "claim_class": "L3_DISTANCE_TOUCH_4H"})
        cell["n"] += 1
        cell["hits"] += int(row["outcome"])
        cell["psum"] += row["probability"]
    bins = claims.live_touch_bins(list(cells.values()), "4h")
    assert claims.diverged_bins(bins) == [[0.3, 0.5]]
    assert _book(evaluate(rows))["state"] == STATE_INSUFFICIENT


def test_a_sustained_level_shift_confirms_and_keeps_both_snapshots():
    rows = _rows(40, outcome=0.0, probabilities=(0.40,), snapshot="snap-a")
    rows += _rows(40, outcome=0.0, probabilities=(0.40,), snapshot="snap-b")
    # second half continues the clock instead of repeating January
    for index, row in enumerate(rows):
        row["as_of"] = START + timedelta(hours=index)
    book = _book(evaluate(rows))
    assert book["state"] == STATE_CONFIRMED
    assert book["snapshot_ids"] == ["snap-a", "snap-b"]
    assert book["snapshot_policy"] == "RECORDED_NOT_RESET"
    level = book["channels"]["LEVEL"]
    assert level["estimate"] < -PRACTICAL_ABS
    assert level["e_value"] >= E_CONFIRM
    assert book["user_action"]["show_model_probability"] is False
    assert book["user_action"]["blend_model_toward_outcome"] is False
    assert book["user_action"]["action"] == ACTION_WITHHOLD_PROBABILITY


def test_tails_confirm_when_the_horizon_average_residual_is_zero():
    def outcome(_index, probability):
        if probability >= 0.70:
            return 0.0
        if probability < 0.30:
            return 1.0
        return 1.0 if probability == 0.50 else 0.0

    rows = _rows(25, probabilities=(0.10, 0.50, 0.90), outcome=outcome)
    # two claims at 0.50 so their residuals cancel: rewrite half of the 0.50 outcomes
    seen = 0
    for row in rows:
        if row["probability"] != 0.50:
            continue
        row["outcome"] = 1.0 if seen % 2 == 0 else 0.0
        seen += 1
    book = _book(evaluate(rows))
    assert abs(book["channels"]["LEVEL"]["estimate"]) < 0.02
    assert book["channels"]["TAIL_HIGH"]["state"] == STATE_CONFIRMED
    assert book["channels"]["TAIL_LOW"]["state"] == STATE_CONFIRMED
    assert book["state"] == STATE_CONFIRMED


def test_neither_can_confirm_while_touch_stays_inside_noise():
    touch = _rows(30, family="touch", probabilities=(0.40,), outcome=lambda index, _p: 1.0 if index % 5 < 2 else 0.0,
                  rule="TOUCH_V1")
    neither = _rows(30, family="neither", probabilities=(0.80,), outcome=1.0, rule="NEITHER_V1")
    report = evaluate(touch + neither)
    assert _book(report, "touch")["state"] in (STATE_NOISE, STATE_INSUFFICIENT, STATE_SUSPECTED)
    assert _book(report, "neither")["state"] == STATE_CONFIRMED
    assert _book(report, "touch")["state"] != STATE_CONFIRMED


def test_clean_days_after_a_confirmed_gap_recover_without_erasing_the_episode():
    biased = _rows(30, probabilities=(0.55,), outcome=0.0)
    clean = []
    moment = START + timedelta(days=30)
    rng = np.random.default_rng(20261005)
    while moment < START + timedelta(days=70):
        draw = float(rng.random())
        clean.append({
            "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
            "as_of": moment, "probability": 0.55, "outcome": 1.0 if draw < 0.55 else 0.0,
            "status": "COMPLETE", "eval_rule_id": "TOUCH_V1", "snapshot_id": "snap-refit",
        })
        moment += timedelta(hours=1)
    full = evaluate(biased + clean)
    book = _book(full)
    level = book["channels"]["LEVEL"]
    assert level["episodes"], "the biased stretch has to leave an episode"
    assert level["episodes"][0]["recovered_on"] is not None
    assert level["episodes"][0]["archived_e"] >= E_CONFIRM or level["episodes"][0]["confirmed_by"] == "CHECKPOINT_DAY_28"
    assert book["state"] in (STATE_RECOVERED, STATE_NOISE)
    prefix = _book(evaluate(biased))
    assert prefix["state"] == STATE_CONFIRMED
    assert prefix["channels"]["LEVEL"]["episodes"][0]["recovered_on"] is None


def test_illegal_probability_and_mixed_rules_are_faults_not_divergences():
    broken = _rows(12, probabilities=(0.40,))
    broken[0]["probability"] = 1.4
    fault = _book(evaluate(broken))
    assert fault["state"] == STATE_FAULT
    assert fault["user_action"]["action"] == ACTION_WITHHOLD_FIGURE
    mixed = _rows(4, probabilities=(0.40,))
    mixed[0]["eval_rule_id"] = "OTHER_RULE"
    assert _book(evaluate(mixed))["state"] == STATE_FAULT


def test_too_many_unscored_outcomes_are_incomplete_rather_than_a_model_verdict():
    rows = _rows(15, probabilities=(0.40,), outcome=0.0)
    for row in rows[: len(rows) // 3]:
        row["status"] = "NO_DATA"
        row["outcome"] = None
    book = _book(evaluate(rows))
    assert book["state"] == STATE_INCOMPLETE
    assert book["user_action"]["show_model_probability"] is False
    assert book["user_action"]["allow_separate_baseline"] is False


def test_naive_timestamps_are_a_fault():
    rows = _rows(2, probabilities=(0.40,))
    rows[0]["as_of"] = datetime(2024, 1, 1, 0, 0)
    assert _book(evaluate(rows))["state"] == STATE_FAULT


def test_owner_digest_is_once_per_utc_day_and_silence_is_not_paged():
    assert digest_due(STATE_NOISE, utc_day="2026-10-12", last_digest_day=None) is False
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-12", last_digest_day=None) is True
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-12", last_digest_day="2026-10-12") is False
    assert digest_due(STATE_CONFIRMED, utc_day="2026-10-13", last_digest_day="2026-10-12") is True
    assert digest_due(STATE_RECOVERED, utc_day="2026-10-14", last_digest_day=None,
                      previous_state=STATE_CONFIRMED) is True
    assert digest_due(STATE_RECOVERED, utc_day="2026-10-14", last_digest_day=None,
                      previous_state=STATE_NOISE) is False
    assert user_action(STATE_SUSPECTED)["action"] == ACTION_NO_OVERRIDE
    assert user_action(STATE_INSUFFICIENT)["show_model_probability"] is True


def test_replay_is_deterministic_and_does_not_mutate_inputs():
    rows = _rows(12, probabilities=(0.22, 0.78), outcome=lambda index, probability: 1.0 if index % 3 == 0 else 0.0)
    first = evaluate(rows)
    second = evaluate(rows)
    assert first == second
    assert rows[0]["probability"] == 0.22


def test_e_process_null_bound_is_not_exceeded_on_daily_noise():
    rng = np.random.default_rng(20261005)
    crossings = 0
    paths = 80
    for _ in range(paths):
        rows = []
        for day in range(120):
            bit = 1.0 if rng.random() < 0.5 else 0.0
            rows.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "1h",
                "as_of": START + timedelta(days=int(day), hours=1),
                "probability": 0.50, "outcome": bit,
                "status": "COMPLETE", "eval_rule_id": "TOUCH_V1", "snapshot_id": "noise",
            })
        book = _book(evaluate(rows), horizon="1h")
        if book["state"] == STATE_CONFIRMED:
            crossings += 1
    # Anytime bound per book is 5% at E=20, plus one 2.5% checkpoint. 80 paths: allow slack.
    assert crossings <= 12


def test_day_floor_is_the_predeclared_constant_not_a_slot_count():
    assert MIN_DAYS_SUSPECT > 5
    short = _rows(MIN_DAYS_SUSPECT - 1, probabilities=(0.90,), outcome=0.0)
    assert _book(evaluate(short))["state"] == STATE_INSUFFICIENT
