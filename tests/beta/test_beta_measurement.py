"""BETA_MEASUREMENT_CONTRACT_V1 instrumentation, pure parts (offline): the U1a withdrawal
schedule is frozen by config before Day 0 and is a pure function of Day 0."""
from datetime import date

import pytest

from beta.config import BetaConfig, BetaConfigError
from beta.delivery import brief_withdrawal_dates

CFG = BetaConfig.load()
FROZEN = dict(CFG.section("briefing")["withdrawal"])


def _rule(**kw):
    return {"withdrawal": {**FROZEN, **kw}}


def test_committed_rule_is_frozen_and_off_until_day0():
    assert FROZEN == {"day0_kyiv": None, "seed": 20261003, "count": 3, "first_cohort_day": 14,
                      "last_cohort_day": 27}
    assert brief_withdrawal_dates(CFG.section("briefing")) == frozenset()
    assert brief_withdrawal_dates({}) == frozenset()                     # an override without the block


@pytest.mark.parametrize("day0", ["2026-10-05", "2026-10-07", "2026-10-10", "2026-11-01"])
def test_three_weekdays_in_weeks_three_and_four_same_for_everyone(day0):
    d0 = date.fromisoformat(day0)
    days = brief_withdrawal_dates(_rule(day0_kyiv=day0))
    assert len(days) == 3
    for d in days:
        assert d.weekday() < 5 and 14 <= (d - d0).days <= 27
    assert days == brief_withdrawal_dates(_rule(day0_kyiv=day0))         # deterministic: no adjustment


def test_the_seed_is_the_only_randomness():
    a = brief_withdrawal_dates(_rule(day0_kyiv="2026-10-05"))
    b = brief_withdrawal_dates(_rule(day0_kyiv="2026-10-05", seed=7))
    shifted = brief_withdrawal_dates(_rule(day0_kyiv="2026-10-12"))
    assert a == brief_withdrawal_dates(_rule(day0_kyiv="2026-10-05"))
    # both Mondays: the same cohort-day layout, one week apart
    assert {d - date(2026, 10, 5) for d in a} == {d - date(2026, 10, 12) for d in shifted}
    assert a != b


@pytest.mark.parametrize("bad", [{"count": 2}, {"count": 4}, {"day0_kyiv": "05.10.2026"}, {"day0_kyiv": 20261005},
                                 {"first_cohort_day": 20, "last_cohort_day": 24}, {"seed": -1}])
def test_the_rule_is_validated(bad):
    b = dict(CFG.section("briefing"))
    b["withdrawal"] = {**FROZEN, **bad}
    with pytest.raises(BetaConfigError):
        CFG.with_overrides(briefing=b)


def test_day0_is_the_only_field_set_after_the_freeze():
    b = dict(CFG.section("briefing"))
    b["withdrawal"] = {**FROZEN, "day0_kyiv": "2026-10-05"}
    cfg = CFG.with_overrides(briefing=b)
    assert {k: v for k, v in cfg.section("briefing")["withdrawal"].items() if k != "day0_kyiv"} == \
        {k: v for k, v in FROZEN.items() if k != "day0_kyiv"}
    assert len(brief_withdrawal_dates(cfg.section("briefing"))) == 3
    assert cfg.rules_digest == CFG.rules_digest                          # never the detector identity
