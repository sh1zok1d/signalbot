"""AUTOGEN_G01 candidate inventory: generation, red team and dedupe.

Written before any market value of this program is read. It is the single
source for docs/research/AUTOGEN_G01_CANDIDATES.{json,md}. Survivors go to the
outcome-blind feasibility pass in support.py; the rest are closed here with the
reason. No closed candidate is repaired or re-scored.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT_JSON = REPO / "docs/research/AUTOGEN_G01_CANDIDATES.json"
OUT_MD = REPO / "docs/research/AUTOGEN_G01_CANDIDATES.md"

SURVIVES = "SURVIVES_TO_FEASIBILITY"
RED_TEAM = "CLOSED_AT_RED_TEAM"
DEDUPE = "CLOSED_AT_DEDUPE"

CANDIDATES = [
    {
        "ID": "G01-A1", "NAME": "TOM_PARTICIPATION", "STAGE": SURVIVES, "FAMILY": "J-adjacent / CALENDAR_CASH_FLOW_CLOCK (new subfamily)",
        "MECHANISM": "Recurring fiat-rail cash flows (salary-linked purchases, monthly DCA plans, fund subscriptions and month-end marks) concentrate around the turn of the month, so participation rises on the first days of a month.",
        "EXACT_CLAIM": "Mean over calendar months of [mean z(log daily trade count) over turn-of-month days minus mean z over days 8-21 of the same month] is positive and at least 0.5 comparator-SD, Holm-adjusted two-sided sign-flip p <= 0.05 within TF-G01-A.",
        "INFERENCE_CLASS": "CONTEXT_DESCRIPTIVE / UNCONDITIONAL / ATOMIC; sign-flip over month units",
        "UNIT": "calendar month",
        "EXPOSURE": "turn-of-month days: the last UTC calendar day of the previous month and days 1-3; minus the last-Friday expiry day and the fixed holiday windows Dec 24-Jan 2 and Oct 1-7",
        "OUTCOME": "log of the UTC-day trade count (Binance 1m `count`; BitMEX 5m `trades`), standardized per year and weekday class (Mon-Fri / Sat-Sun), label-blind",
        "COMPARATOR": "days 8-21 of the same month outside the holiday windows",
        "DATA": ["CORE_BTC_BINANCE_V0 (1m, 2020-01..2024-12)", "D2_BITMEX_PRE2020_XBTUSD (5m, 2017-01..2019-12, replication)"],
        "EXPECTED_NOMINAL_N": "about 60 discovery months, 36 replication months; about 3-4 state and 14 comparator days per month",
        "DEPENDENCE": "months are time-separated; slow participation regimes cancel inside a month; residual serial dependence across months is checked with a moving-block SE",
        "CONFOUNDERS": ["weekday composition of state days (removed by weekday-class standardization)", "monthly expiry on the last Friday (that day is excluded)", "year-end and CN Golden Week holidays (fixed-date exclusions)", "floating holidays (CN New Year, US Labor Day) remain as noise"],
        "PRACTICAL_BAR": "0.5 comparator-SD (the same product-relevance bar as R03: a shift that roughly doubles the rate of extreme-day flags)",
        "PRODUCT_RELEVANCE": "activity ranks and baselines in the briefing; a turn-of-month shift would mis-calibrate a 30-day activity baseline",
        "PRIOR_OVERLAP": ["R03-A2 last-Friday expiry hour (different clock; that day excluded)", "R03-C weekday/session clock (weekday handled by standardization)", "GV0V03L40-C028 tax-year-end panel turnover (December only, panel, losers)"],
        "WHY_NOT_DUPLICATE": "No prior card tests the day-of-month cash-flow clock; turn-of-month appears in no ledger, memory or generator record.",
        "RED_TEAM": "Lookahead: none (calendar). Hidden conditioning: none. Overlap: state day -1 belongs to the next month's unit only. Pseudo-replication: month units. Multiplicity: Holm within card. Epoch: calendar years, gate per contract. Venue artifact: trade count changes with fragmentation, absorbed by per-year standardization. Exposed-outcome leakage: no day-of-month statistic was ever reported. Survives.",
    },
    {
        "ID": "G01-A2", "NAME": "TOM_RANGE", "STAGE": SURVIVES, "FAMILY": "J-adjacent / CALENDAR_CASH_FLOW_CLOCK",
        "MECHANISM": "If turn-of-month flows are directional and lumpy, they move price more on those days than mid-month, widening the daily range.",
        "EXACT_CLAIM": "As G01-A1 with target z(log daily range ln(max high / min low)).",
        "INFERENCE_CLASS": "CONTEXT_DESCRIPTIVE / UNCONDITIONAL / ATOMIC; sign-flip over month units",
        "UNIT": "calendar month", "EXPOSURE": "as G01-A1",
        "OUTCOME": "log daily range over the UTC day, standardized per year and weekday class",
        "COMPARATOR": "as G01-A1", "DATA": ["CORE_BTC_BINANCE_V0", "D2_BITMEX_PRE2020_XBTUSD (replication)"],
        "EXPECTED_NOMINAL_N": "as G01-A1", "DEPENDENCE": "as G01-A1",
        "CONFOUNDERS": ["as G01-A1", "volatility regime (nuisance diagnostic: prior 24h RV, lagged target)"],
        "PRACTICAL_BAR": "0.5 comparator-SD", "PRODUCT_RELEVANCE": "range ranks behind the unusual-hour and daily context",
        "PRIOR_OVERLAP": ["as G01-A1"], "WHY_NOT_DUPLICATE": "as G01-A1",
        "RED_TEAM": "As G01-A1. The range target is the product-facing one; the participation target is the direct mechanism observable. Both are kept as separate cells (Holm m <= 3). Survives.",
    },
    {
        "ID": "G01-A3", "NAME": "MONTH_END_MARK_HOUR", "STAGE": SURVIVES, "FAMILY": "J-adjacent / CALENDAR_CASH_FLOW_CLOCK",
        "MECHANISM": "Crypto funds and treasuries mark month-end NAV at 00:00 UTC; rebalancing and marking trades concentrate in the last UTC hour of the month.",
        "EXACT_CLAIM": "Mean over months of [z(log range of 23:00-24:00 UTC on the last day of the month) minus mean z of the same hour on days 8-21] is positive and at least 0.5 SD, Holm within TF-G01-A.",
        "INFERENCE_CLASS": "CONTEXT_DESCRIPTIVE / UNCONDITIONAL / ATOMIC; sign-flip over month units",
        "UNIT": "calendar month", "EXPOSURE": "23:00-24:00 UTC on the last day of the month (December excluded by the year-end window)",
        "OUTCOME": "log range of the hour, standardized per year and weekday class over all days' 23:00 hours",
        "COMPARATOR": "23:00-24:00 UTC on days 8-21 of the same month",
        "DATA": ["CORE_BTC_BINANCE_V0", "D2_BITMEX_PRE2020_XBTUSD (replication)"],
        "EXPECTED_NOMINAL_N": "about 55 months with one state hour each",
        "DEPENDENCE": "time-separated months",
        "CONFOUNDERS": ["one state hour per unit: rare-event power is the expected failure", "daily 00:00 UTC funding and candle close affect state and comparator alike"],
        "PRACTICAL_BAR": "0.5 comparator-SD", "PRODUCT_RELEVANCE": "the unusual-hour flag at the month boundary",
        "PRIOR_OVERLAP": ["R03-A2/A3 (monthly single-hour cells closed INFORMATIONALLY_WEAK at feasibility)"],
        "WHY_NOT_DUPLICATE": "Different clock (month-end mark, not expiry). Kept so that the compiler, not the author, decides its power.",
        "RED_TEAM": "Rare-event N is the expected failure; it is sent to the compiler rather than closed by the author, because the R03 precedent is a compiler decision. Survives to feasibility.",
    },
    {
        "ID": "G01-B1", "NAME": "ETF_FIXING_HOUR_PARTICIPATION", "STAGE": SURVIVES, "FAMILY": "G-adjacent / SCHEDULED_REFERENCE_FIXING (ETF era; not FOMC/CPI/NFP; not CME monthly settlement)",
        "MECHANISM": "US spot bitcoin ETFs (trading from 2024-01-11) strike NAV on reference rates computed over 15:00-16:00 New York. Authorized-participant and market-maker execution and the associated CME basis activity concentrate in that window on NYSE trading days, raising its participation relative to the adjacent afternoon hours.",
        "EXACT_CLAIM": "Difference-in-differences over ISO weeks: mean over post-launch weeks of d_week minus mean over pre-launch weeks of d_week is positive and at least 0.5 comparator-SD, two-sided block-permutation p <= 0.05; d_week = mean over NYSE full trading days of [z(log quote volume 15:00-16:00 NY) - mean z(log quote volume 13:00-14:00, 14:00-15:00 NY)].",
        "INFERENCE_CLASS": "CONTEXT_DESCRIPTIVE / UNCONDITIONAL / ATOMIC; block permutation of era labels over 4-week blocks",
        "UNIT": "ISO week (pre: 2020-01-01..2024-01-07; post: 2024-01-15..2024-12-31; launch week 2024-W02 dropped)",
        "EXPOSURE": "post-launch NYSE full trading days",
        "OUTCOME": "log quote volume of the fixing hour relative to the two preceding hours, standardized per year on a common scale across the three hours",
        "COMPARATOR": "the same relative quantity in pre-launch weeks",
        "DATA": ["CORE_BTC_BINANCE_V0", "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"],
        "EXPECTED_NOMINAL_N": "about 209 pre and 50 post weeks; about 4.8 trading days per week",
        "DEPENDENCE": "serial dependence across weeks (4-week blocks); the within-day difference removes day-level volatility",
        "CONFOUNDERS": ["US equity close and CME daily settlement also sit at 16:00 NY (present in both eras; DiD)", "hour-specific trends unrelated to ETFs (not removable; stated as a blocking assumption)", "single post year: epochs are 2024 quarters"],
        "PRACTICAL_BAR": "0.5 comparator-SD", "PRODUCT_RELEVANCE": "same-hour baselines that mix NYSE days, weekends and holidays mis-calibrate the 15:00-16:00 NY hour if it changed with ETFs",
        "PRIOR_OVERLAP": ["R03-C4 Friday 15:00-16:00 NY vs Tue-Thu (different comparator and question; null)", "GV0CAL-C004 CME monthly settlement fixing (blocked on confounding)", "D12 US-clock anchoring (profile shift at DST; different identification)"],
        "WHY_NOT_DUPLICATE": "No prior card uses the ETF launch as a natural experiment; ETF NAV fixing appears in no ledger, memory or generator record.",
        "RED_TEAM": "Lookahead: none (calendar and launch date are public before T). Confounding: the hour also hosts the equity close and CME daily settle, handled by DiD against pre-launch weeks; ETF-unrelated hour-specific trends cannot be removed and are stated. Replication: no historical ETF era exists; prospective only, against the frozen pre-launch mean. Range target not added, to keep a single primary cell. Survives.",
    },
    {
        "ID": "G01-X1", "NAME": "HK_ETF_FIXING_0800UTC", "STAGE": RED_TEAM, "FAMILY": "G-adjacent",
        "MECHANISM": "Hong Kong spot bitcoin ETFs (from 2024-04-30) strike NAV at 16:00 HKT (08:00 UTC).",
        "EXACT_CLAIM": "Range or participation of 08:00-09:00 UTC after 2024-04-30 vs before, relative to adjacent hours.",
        "CLOSE_REASON": "Not identifiable: 08:00 UTC is also the Binance funding settlement and the Deribit expiry hour (the GV0CAL-C003 causal-identification blocker class). HK ETF flows are also very small.",
    },
    {
        "ID": "G01-X2", "NAME": "WEEKEND_BTC_SHARE_PANEL", "STAGE": RED_TEAM, "FAMILY": "H/J",
        "MECHANISM": "Weekend participants are retail-heavy and rotate into altcoins, lowering BTC's share of spot USDT volume on weekends.",
        "EXACT_CLAIM": "BTC share of the top-100 spot USDT panel quote volume is lower on Saturday-Sunday than Tuesday-Thursday of the same week.",
        "CLOSE_REASON": "Exchange-specific artifact. Binance zero-fee BTC spot trading (2022-07 to 2023-03) and the 2023 migration of BTC spot liquidity to FDUSD pairs make the BTC share of USDT pairs a measure of fee promotions rather than participant composition. Product relevance is low (the briefing is BTC perp). Acquiring the 18k-object panel is not justified for this card.",
    },
    {
        "ID": "G01-X3", "NAME": "SESSION_TAKER_SIGN_PROFILE", "STAGE": RED_TEAM, "FAMILY": "J",
        "MECHANISM": "Regional participant populations differ in aggressiveness, so net taker share differs by session.",
        "EXACT_CLAIM": "Mean net taker share in US-session hours minus Asia-session hours differs from zero.",
        "CLOSE_REASON": "A directional flow claim is INCREMENTAL, not context. A UTC-hour profile does not identify an institutional clock; the only identification (DST shifts) is the D12 template, whose neighbors are forbidden. Funding hours (00/08/16 UTC) confound the session blocks.",
    },
    {
        "ID": "G01-X4", "NAME": "TAKER_SIGN_PERSISTENCE", "STAGE": RED_TEAM, "FAMILY": "B/E",
        "MECHANISM": "Order splitting makes the sign of hourly net taker flow persistent.",
        "EXACT_CLAIM": "P(sign of next-hour net taker share equals this hour's) exceeds 0.5 by a bar.",
        "CLOSE_REASON": "The outcome is not in doubt (long memory of order signs is a known stylized fact), so a test is not informative. H05 and B2-05 governance also deprioritize taker/flow children presented as fresh formulas.",
    },
    {
        "ID": "G01-X5", "NAME": "SIGNED_SHOCK_RANGE_ASYMMETRY", "STAGE": DEDUPE, "FAMILY": "A/F",
        "MECHANISM": "Long-liquidation convexity makes ranges after down-shocks wider than after equal-magnitude up-shocks.",
        "EXACT_CLAIM": "Next-4h range after a down-shock hour exceeds that after an up-shock hour of matched magnitude.",
        "CLOSE_REASON": "Hidden repeat of GV0V03L40-C027 and C003 (inverse-margin and liquidation convexity, down- vs up-shock paths; blocked for confounding control and lookahead), which it does not resolve. Volatility-conditioning neighbor of D2 and D8 (forbidden RV-threshold children; D8 not to be weakened).",
    },
    {
        "ID": "G01-X6", "NAME": "UNUSUAL_HOUR_PERSISTENCE", "STAGE": DEDUPE, "FAMILY": "A",
        "MECHANISM": "An hour with an extreme same-hour range rank is followed by elevated ranges.",
        "EXACT_CLAIM": "Next-hour standardized range after a rank >= 0.95 hour exceeds that after ordinary hours.",
        "CLOSE_REASON": "Volatility clustering. The outcome is not in doubt, and the card is an RV-threshold child of D2 (forbidden).",
    },
    {
        "ID": "G01-X7", "NAME": "EQUITY_OPEX_HOUR", "STAGE": RED_TEAM, "FAMILY": "G",
        "MECHANISM": "US equity monthly options expiry (third Friday) dealer hedging spills into BTC through cross-asset books.",
        "EXACT_CLAIM": "15:00-16:00 NY range on the third Friday exceeds the same hour on other Fridays of the month.",
        "CLOSE_REASON": "Rare-event N: one state hour per monthly unit. Under the frozen stress SD the paired MDE is about 0.84 SD, far above the bar, as for R03-A2/A3. The mechanism is also weak a priori.",
    },
    {
        "ID": "G01-X8", "NAME": "ASIA_LUNCH_PARTICIPATION", "STAGE": RED_TEAM, "FAMILY": "J",
        "MECHANISM": "Asian retail lunch breaks lower participation at fixed UTC hours.",
        "EXACT_CLAIM": "02:30-05:00 UTC participation is below adjacent hours.",
        "CLOSE_REASON": "Not identifiable: Asian clocks have no DST, so the claim cannot be separated from a generic UTC hour-of-day profile. Holiday-based identification is the GV0R01-C020 neighbor (data/feasibility blocked).",
    },
    {
        "ID": "G01-X9", "NAME": "ETF_WEEKEND_GAP_GROWTH", "STAGE": RED_TEAM, "FAMILY": "J",
        "MECHANISM": "ETF-era weekday participation widens the weekday/weekend gap.",
        "EXACT_CLAIM": "The weekend-minus-weekday range gap widened after 2024-01-11.",
        "CLOSE_REASON": "Leakage from previously exposed outcomes: the idea follows from R03-C1's observed epoch trend (-0.19 in 2020 to -0.65 in 2024) on the same surface. That is post-hoc and a rescue of a closed card.",
    },
    {
        "ID": "G01-X10", "NAME": "BANK_HOLIDAY_FIAT_RAIL", "STAGE": RED_TEAM, "FAMILY": "J/G",
        "MECHANISM": "US bank holidays with NYSE open (Columbus Day, Veterans Day) close fiat rails and lower US participation.",
        "EXACT_CLAIM": "Participation on those days is below matched weekdays.",
        "CLOSE_REASON": "Rare-event N (about 10 days in 2020-2024). Close neighbor of the holiday participant-removal card GV0R01-C020.",
    },
]


def _md() -> str:
    lines = [
        "# AUTOGEN_G01 — candidate inventory, red team and dedupe", "",
        "**Status:** `INVENTORY_FROZEN_BEFORE_DATA`. No market value of this program was read when it was written.",
        "**Decision record:** `AUTOGEN_G01_DECISION.md`. **Machine record:** `AUTOGEN_G01_CANDIDATES.json` (generated by `scripts/research/autogen_g01/candidates.py`).", "",
        "## Summary", "",
        "| ID | Name | Family | Stage |", "|---|---|---|---|",
    ]
    for c in CANDIDATES:
        lines.append(f"| {c['ID']} | `{c['NAME']}` | {c['FAMILY']} | `{c['STAGE']}` |")
    counts = {s: sum(c["STAGE"] == s for c in CANDIDATES) for s in (SURVIVES, RED_TEAM, DEDUPE)}
    lines += ["", f"Generated {len(CANDIDATES)}; closed at red team {counts[RED_TEAM]}; closed at dedupe {counts[DEDUPE]}; to feasibility {counts[SURVIVES]}.", "",
              "## Survivors (full card fields)", ""]
    for c in CANDIDATES:
        if c["STAGE"] != SURVIVES:
            continue
        lines.append(f"### {c['ID']} `{c['NAME']}`")
        lines.append("")
        for key in ("MECHANISM", "EXACT_CLAIM", "INFERENCE_CLASS", "UNIT", "EXPOSURE", "OUTCOME", "COMPARATOR",
                    "EXPECTED_NOMINAL_N", "DEPENDENCE", "PRACTICAL_BAR", "PRODUCT_RELEVANCE", "WHY_NOT_DUPLICATE", "RED_TEAM"):
            lines.append(f"- **{key.replace('_', ' ').capitalize()}:** {c[key]}")
        lines.append(f"- **Data:** {'; '.join(c['DATA'])}")
        lines.append(f"- **Confounders:** {'; '.join(c['CONFOUNDERS'])}")
        lines.append(f"- **Prior overlap:** {'; '.join(c['PRIOR_OVERLAP'])}")
        lines.append("")
    lines += ["## Closed before feasibility (no outcome, no repair)", ""]
    for c in CANDIDATES:
        if c["STAGE"] == SURVIVES:
            continue
        lines += [f"### {c['ID']} `{c['NAME']}` — `{c['STAGE']}`", "",
                  f"- **Mechanism:** {c['MECHANISM']}", f"- **Claim:** {c['EXACT_CLAIM']}", f"- **Why closed:** {c['CLOSE_REASON']}", ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    body = {"PROGRAM_ID": "AUTOGEN_G01", "MARKET_VALUES_READ": False, "CANDIDATES": CANDIDATES,
            "COUNTS": {s: sum(c["STAGE"] == s for c in CANDIDATES) for s in (SURVIVES, RED_TEAM, DEDUPE)}}
    OUT_JSON.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    OUT_MD.write_text(_md())
    print(json.dumps(body["COUNTS"]))


if __name__ == "__main__":
    main()
