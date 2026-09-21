"""Outcome-blind D2 BitMEX replication preregistration freeze.

Verifies sealed-source eligibility (timestamps/gaps/hashes only).
Does not compute MU_RULE, DELTA, candidate/control severity, or classification.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.research.d2_bitmex_pre2020 import (
    AUTHORITY_REL,
    FUTURE_BARS,
    INSTRUMENT,
    PARSER_VERSION,
    PRE2020_END_EXCLUSIVE,
    RV_TRAILING_WINDOW,
    TIMESTAMP_SEMANTICS,
    BitmexSchemaError,
    census_gaps,
    count_legal_decision_rows,
    from_ms,
    refuse_binance_protected_path,
    refuse_d2_outcome_request,
    row_timestamp_complete,
    sha256_bytes,
    utc_ms,
)
from scripts.research.d2_confirmation_feasibility_and_design import (
    D2_CONFIRMATION_POWER_SEED,
    D2_CONFIRMATION_RANDOM_CONTROL_SEED,
    D2_CONFIRMATION_SIZE_PLANNING_SEED,
)
from scripts.research.d2_confirmation_dependence_preserving_power import (
    D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED,
    D2_REFINED_FRESH_N_SEED,
)
from scripts.research.discovery_sprint_01 import common as C

UTC = timezone.utc

UNIT = "D2_BITMEX_REPLICATION_PREREG_FREEZE"
EVIDENCE_CLASS = "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION"
CANDIDATE = "D2 / RULE_1 / RV_ABSTENTION"

# Distinct from discovery 20260921102, confirmation 120-123, refined power 124.
D2_BITMEX_REPLICATION_RANDOM_SEED = 20260921125
N_REPLICATES = 10_000
RV_PCTL = 90.0
AUTHORITATIVE_RELATIVE_EFFECT = 0.20

FROZEN_FIRST_RULE_ELIGIBLE_T = datetime(2017, 1, 24, 0, 5, tzinfo=UTC)
FROZEN_LAST_RULE_ELIGIBLE_T = datetime(2019, 12, 30, 0, 5, tzinfo=UTC)
FROZEN_EXPECTED_ELIGIBLE_N = 1069
FROZEN_COMPLETE_INCLUDING_WARMUP = 1319
FROZEN_MISSING_BUCKET_COUNT = 288
GAP_FIRST_OPEN = datetime(2016, 12, 6, 23, 55, tzinfo=UTC)
GAP_LAST_OPEN = datetime(2016, 12, 7, 23, 50, tzinfo=UTC)

REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815
POWER_AT_REFINED_MIN_N = 0.801
POWER_95CI_AT_REFINED_MIN_N = [0.7751234971811168, 0.824572794210579]
POWER_N820 = 0.794

JSON_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG.json"
MD_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG.md"
BINDING_REL = "docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json"
CANONICAL_REL = "docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz"
FEASIBILITY_JSON_REL = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json"
D2_RESULT_REL = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"

IMPLEMENTATION_FILES = (
    "scripts/research/d2_bitmex_replication_evaluator.py",
    "scripts/research/d2_bitmex_pre2020.py",
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
    "scripts/research/discovery_sprint_01/common.py",
)

FORBIDDEN_SEEDS = {
    C.D2_RANDOM_CONTROL_SEED,
    D2_CONFIRMATION_RANDOM_CONTROL_SEED,
    D2_CONFIRMATION_POWER_SEED,
    D2_CONFIRMATION_SIZE_PLANNING_SEED,
    D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED,
    D2_REFINED_FRESH_N_SEED,
}


class PreregInconsistency(RuntimeError):
    """Sealed BitMEX eligibility did not reproduce the frozen census."""


class ExecutionNotAuthorized(RuntimeError):
    """Scientific replication execution is not authorized by this unit."""


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_sealed_open_times(repo: Path) -> tuple[dict[str, Any], list[int], bytes, bytes]:
    """Load canonical open timestamps after fail-closed hash checks. No outcomes."""
    auth_path = repo / AUTHORITY_REL
    refuse_binance_protected_path(auth_path)
    authority = json.loads(auth_path.read_text(encoding="utf-8"))
    if authority.get("scientific_outcomes", {}).get("D2_OUTCOME_COMPUTED_ON_BITMEX") is not False:
        refuse_d2_outcome_request("AUTHORITY")
    gz_path = repo / str(authority["canonical_relative_path"])
    if not gz_path.is_file():
        gz_path = repo / CANONICAL_REL
    refuse_binance_protected_path(gz_path)
    gz_bytes = gz_path.read_bytes()
    if sha256_bytes(gz_bytes) != authority["canonical_jsonl_gz_sha256"]:
        raise PreregInconsistency("CANONICAL_GZ_HASH_MISMATCH")
    jsonl_bytes = gzip.decompress(gz_bytes)
    if sha256_bytes(jsonl_bytes) != authority["canonical_jsonl_sha256"]:
        raise PreregInconsistency("CANONICAL_JSONL_HASH_MISMATCH")
    opens: list[int] = []
    prev: int | None = None
    for line in jsonl_bytes.splitlines():
        if not line:
            continue
        row = json.loads(line)
        ms = int(row["open_time_ms"])
        if prev is not None and ms <= prev:
            raise BitmexSchemaError(f"NON_MONOTONIC_OR_DUPLICATE:{ms}")
        if ms >= utc_ms(PRE2020_END_EXCLUSIVE):
            raise PreregInconsistency(f"OPEN_AT_OR_AFTER_2020:{ms}")
        opens.append(ms)
        prev = ms
    return authority, opens, gz_bytes, jsonl_bytes


def verify_frozen_eligibility(repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    authority, opens, gz_bytes, jsonl_bytes = load_sealed_open_times(base)
    present = set(opens)
    raw_open = int(opens[0])
    last_open = int(opens[-1])
    legal = count_legal_decision_rows(present, raw_open_ms=raw_open)
    gaps = census_gaps(present, raw_open_ms=raw_open, last_open_ms=last_open)
    first = legal["FIRST_RULE_ELIGIBLE_T"]
    last = legal["LAST_RULE_ELIGIBLE_T"]
    n = int(legal["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"])
    if first != _iso(FROZEN_FIRST_RULE_ELIGIBLE_T):
        raise PreregInconsistency(f"FIRST_T:{first}")
    if last != _iso(FROZEN_LAST_RULE_ELIGIBLE_T):
        raise PreregInconsistency(f"LAST_T:{last}")
    if n != FROZEN_EXPECTED_ELIGIBLE_N:
        raise PreregInconsistency(f"ELIGIBLE_N:{n}")
    if int(legal["COMPLETE_DECISION_ROWS_INCLUDING_WARMUP"]) != FROZEN_COMPLETE_INCLUDING_WARMUP:
        raise PreregInconsistency(f"COMPLETE_N:{legal['COMPLETE_DECISION_ROWS_INCLUDING_WARMUP']}")
    if int(legal["WARMUP_DECISION_ROWS"]) != RV_TRAILING_WINDOW:
        raise PreregInconsistency("WARMUP")
    if int(gaps["missing_bucket_count"]) != FROZEN_MISSING_BUCKET_COUNT:
        raise PreregInconsistency(f"GAP_COUNT:{gaps['missing_bucket_count']}")
    if gaps["missing_open_timestamps_sha256"] != authority["gaps"]["missing_open_timestamps_sha256"]:
        raise PreregInconsistency("GAP_SHA")
    missing_head = datetime.fromisoformat(
        gaps["missing_open_timestamps_head"][0].replace("Z", "+00:00")
    )
    missing_tail = datetime.fromisoformat(
        (gaps["missing_open_timestamps_tail"] or gaps["missing_open_timestamps_head"])[-1].replace(
            "Z", "+00:00"
        )
    )
    if missing_head != GAP_FIRST_OPEN or missing_tail != GAP_LAST_OPEN:
        raise PreregInconsistency("GAP_BOUNDS")
    # Reconstruct eligible timestamps for year census only.
    cursor = datetime(from_ms(raw_open).year, from_ms(raw_open).month, from_ms(raw_open).day, 0, 5, tzinfo=UTC)
    if cursor < from_ms(raw_open):
        cursor = cursor + timedelta(days=1)
    complete: list[datetime] = []
    while cursor < PRE2020_END_EXCLUSIVE:
        if row_timestamp_complete(
            utc_ms(cursor),
            present_open_ms=present,
            raw_open_ms=raw_open,
            assume_complete_grid=False,
        ):
            complete.append(cursor)
        cursor = cursor + timedelta(days=1)
    eligible = complete[RV_TRAILING_WINDOW:]
    if eligible[0] != FROZEN_FIRST_RULE_ELIGIBLE_T or eligible[-1] != FROZEN_LAST_RULE_ELIGIBLE_T:
        raise PreregInconsistency("ELIGIBLE_BOUNDS")
    if len(eligible) != FROZEN_EXPECTED_ELIGIBLE_N:
        raise PreregInconsistency("ELIGIBLE_LEN")
    last_future_end = eligible[-1] + timedelta(minutes=5 * FUTURE_BARS)
    if last_future_end >= PRE2020_END_EXCLUSIVE:
        raise PreregInconsistency("FUTURE_CROSSES_2020")
    years = Counter(int(t.year) for t in eligible)
    if set(years) != {2017, 2018, 2019}:
        raise PreregInconsistency(f"YEARS:{sorted(years)}")
    if any(t >= PRE2020_END_EXCLUSIVE or t.year >= 2020 for t in eligible):
        raise PreregInconsistency("YEAR_2020_IN_SAMPLE")
    # Gap-adjacent calendar decisions are not in the complete list.
    gap_days = {
        datetime(2016, 12, 6, 0, 5, tzinfo=UTC),
        datetime(2016, 12, 7, 0, 5, tzinfo=UTC),
        datetime(2016, 12, 8, 0, 5, tzinfo=UTC),
    }
    complete_set = set(complete)
    if gap_days & complete_set:
        raise PreregInconsistency("GAP_DECISION_NOT_EXCLUDED")
    return {
        "authority": authority,
        "legal": legal,
        "gaps": gaps,
        "year_eligible_n": {str(y): int(years[y]) for y in (2017, 2018, 2019)},
        "canonical_jsonl_sha256": sha256_bytes(jsonl_bytes),
        "canonical_jsonl_gz_sha256": sha256_bytes(gz_bytes),
        "authority_sha256": file_sha256(base / AUTHORITY_REL),
        "n_opens": int(len(opens)),
        "TRAILING_250_VALID_HISTORY_VERIFIED": True,
        "KNOWN_GAP_NEVER_FILLED": True,
        "D2_BITMEX_OUTCOME_COMPUTED": False,
    }


def _hash_implementation_files(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in IMPLEMENTATION_FILES:
        path = repo / rel
        if not path.is_file():
            raise PreregInconsistency(f"MISSING_IMPLEMENTATION:{rel}")
        out[rel] = file_sha256(path)
    return out


def build_prereg(*, repo: Path | None = None) -> dict[str, Any]:
    if D2_BITMEX_REPLICATION_RANDOM_SEED in FORBIDDEN_SEEDS:
        raise PreregInconsistency("SEED_COLLISION")
    base = repo or C.repo_root()
    verified = verify_frozen_eligibility(base)
    impl_hashes = _hash_implementation_files(base)
    feasibility = json.loads((base / FEASIBILITY_JSON_REL).read_text(encoding="utf-8"))
    if int(feasibility["BITMEX_PRE2020_ELIGIBLE_N"]) != FROZEN_EXPECTED_ELIGIBLE_N:
        raise PreregInconsistency("FEASIBILITY_N_DRIFT")
    payload = {
        "unit": UNIT,
        "kind": "OUTCOME_BLIND_REPLICATION_PREREGISTRATION",
        "PREREG_FROZEN": True,
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "NOT_EXACT_BINANCE_CONFIRMATION": True,
        "CANDIDATE": CANDIDATE,
        "INSTRUMENT": INSTRUMENT,
        "CONTRACT_ENVIRONMENT": "FFWCSX_INVERSE_PERPETUAL",
        "SOURCE": {
            "endpoint": "https://www.bitmex.com/api/v1/trade/bucketed",
            "binSize": "5m",
            "timestamp_semantics": TIMESTAMP_SEMANTICS,
            "open_time_mapping": "open_time = bitmex_timestamp - 5 minutes",
            "parser_version": PARSER_VERSION,
            "authority_rel": AUTHORITY_REL,
            "authority_sha256": verified["authority_sha256"],
            "canonical_relative_path": CANONICAL_REL,
            "canonical_jsonl_sha256": verified["canonical_jsonl_sha256"],
            "canonical_jsonl_gz_sha256": verified["canonical_jsonl_gz_sha256"],
            "raw_pages_concat_sha256": verified["authority"]["raw_pages_concat_sha256"],
            "reacquire_forbidden": True,
            "fail_closed_on_authority_byte_change": True,
        },
        "CONFIRMATION_RULE": (
            "ABSTAIN(t)=1 iff RV_BTC_24H(t) > P90 of the previous 250 COMPLETED "
            "valid decision-point RV values with t excluded."
        ),
        "RV_BTC_24H": "sqrt(sum of 288 squared 5m log returns) via frozen rv_btc_24h",
        "RV_TRAILING_WINDOW": RV_TRAILING_WINDOW,
        "RV_PCTL": RV_PCTL,
        "no_threshold_sweep": True,
        "no_p85_p95_companion": True,
        "no_alternate_rv_estimator": True,
        "no_alternate_trailing_window": True,
        "DIRECTION": "BTC_SIDE(t) = sign(BTC_RET_24H(t)) via frozen btc_ret_24h / btc_side_from_ret",
        "zero_return_rows_ineligible": True,
        "use_last_trade_price_path": True,
        "use_mark_price": False,
        "use_index_price": False,
        "use_funding": False,
        "use_inverse_pnl": False,
        "invert_direction_because_inverse_contract": False,
        "ENTRY": "5m bar OPEN at T (MARKET-05/06 opening_at convention)",
        "OUTCOME_PATH": "288 x 5m future bars",
        "ADVERSE_SEVERITY": (
            "arithmetic_mae: long (entry-min(low))/entry; short (max(high)-entry)/entry. "
            "Normalized last-trade price-path metric, not inverse or linear PnL."
        ),
        "DECISION_CLOCK": "00:05:00Z daily",
        "clock_redesigned_for_bitmex": False,
        "DECEMBER_31_FORBIDDEN": True,
        "FIRST_RULE_ELIGIBLE_T": _iso(FROZEN_FIRST_RULE_ELIGIBLE_T),
        "LAST_RULE_ELIGIBLE_T": _iso(FROZEN_LAST_RULE_ELIGIBLE_T),
        "EXPECTED_ELIGIBLE_N": FROZEN_EXPECTED_ELIGIBLE_N,
        "EXPECTED_COMPLETE_INCLUDING_WARMUP": FROZEN_COMPLETE_INCLUDING_WARMUP,
        "EXPECTED_ELIGIBLE_N_BY_YEAR": verified["year_eligible_n"],
        "subsample_to_815_forbidden": True,
        "KNOWN_GAP_HANDLING": "NO_FILL_NO_INTERPOLATION_NO_FORWARD_FILL_NO_SYNTHETIC",
        "KNOWN_GAP": {
            "missing_5m_opens": FROZEN_MISSING_BUCKET_COUNT,
            "first_open": _iso(GAP_FIRST_OPEN),
            "last_open": _iso(GAP_LAST_OPEN),
            "missing_open_timestamps_sha256": verified["gaps"]["missing_open_timestamps_sha256"],
        },
        "TRAILING_250_VALID_HISTORY": (
            "250 previous timestamp-complete decision-point rows on the constructed "
            "sequence (t excluded), not 250 calendar dates and not fabricated bars."
        ),
        "TRAILING_250_VALID_HISTORY_VERIFIED": True,
        "PRE2020_END_EXCLUSIVE": _iso(PRE2020_END_EXCLUSIVE),
        "COMPARATOR": "RATE_MATCHED_RANDOM_ABSTENTION year-matched within 2017/2018/2019",
        "pooled_k_across_years_forbidden": True,
        "year_matched_control": (
            "For each year y compute K_y on eligible rows. Each replicate draws "
            "exactly K_y eligible rows without replacement from year y, concatenates, "
            "and takes the pooled mean."
        ),
        "N_RANDOM_CONTROLS": N_REPLICATES,
        "REPLICATION_RANDOM_SEED": D2_BITMEX_REPLICATION_RANDOM_SEED,
        "RNG": f"numpy.random.Generator(numpy.random.PCG64({D2_BITMEX_REPLICATION_RANDOM_SEED}))",
        "PRIMARY_QUANTITIES": ["MU_RULE", "MU_CONTROL_MEAN", "DELTA", "CONTROL_P95", "MC_P"],
        "MC_P": "(1 + count(control_mean >= MU_RULE)) / (1 + N_REPLICATES); diagnostic only",
        "STATISTICAL_GATE": "MU_RULE > CONTROL_P95",
        "PRACTICAL_GATE": "DELTA >= 0.20 * UNCONDITIONAL_MEAN",
        "UNCONDITIONAL_MEAN": "mean adverse severity across all eligible BitMEX replication rows",
        "discovery_142bp_not_a_threshold": True,
        "relative_bar_not_lowered": True,
        "PRIMARY_PASS_RULE": "STATISTICAL_GATE and PRACTICAL_GATE",
        "NO_YEARLY_RESCUE": True,
        "NO_TWO_OF_THREE_YEAR_REQUIREMENT": True,
        "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
        "CLASSIFICATIONS_FROZEN_UNASSIGNED": [
            "D2_BITMEX_REPLICATION_SUPPORTED",
            "D2_BITMEX_REPLICATION_NOT_SUPPORTED",
            "D2_BITMEX_REPLICATION_INVALID",
        ],
        "CLASSIFICATION_ASSIGNED": None,
        "SAMPLE_IDENTITY_GATE": (
            "Execution must reconstruct timestamp-legal N=1069 with the frozen "
            "first/last T. D2 price-path row ineligibility (BTC_RET_24H==0, "
            "RV_le_0, nonpositive OHLC) applied via frozen functions. If the "
            "constructed eligible sample identity differs from 1069 / frozen "
            "first / frozen last, classify INVALID rather than NOT_SUPPORTED."
        ),
        "POWER_PLANNING_PRESERVED": {
            "REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS": REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS,
            "POWER_AT_REFINED_MIN_N": POWER_AT_REFINED_MIN_N,
            "POWER_95CI_AT_REFINED_MIN_N": POWER_95CI_AT_REFINED_MIN_N,
            "POWER_N820": POWER_N820,
            "further_power_search_forbidden": True,
            "815_is_floor_not_sampling_cap": True,
        },
        "SCIENTIFIC_FUNCTIONS_REUSED": [
            "rv_btc_24h",
            "btc_ret_24h",
            "btc_side_from_ret",
            "arithmetic_mae",
            "rv_abstention_mask",
            "rate_matched_random_abstention",
        ],
        "IMPLEMENTATION_FILES_ALLOWED_TO_EXECUTE": list(IMPLEMENTATION_FILES),
        "IMPLEMENTATION_FILE_SHA256": impl_hashes,
        "EXECUTION_AUTHORIZED": False,
        "D2_BITMEX_OUTCOME_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "MARKET_07_CREATED": False,
        "ARM_CREATED": False,
        "PR_READY_TO_MERGE": True,
        "NEXT_UNIT": "D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW",
        "NOT_CREATED": [
            "MARKET-07",
            "confirmation RESULT",
            "BitMEX replication RESULT",
            "ARM",
            "execution permit",
        ],
        "verified_eligibility": {
            "FIRST_RULE_ELIGIBLE_T": legal_iso(verified),
            "LAST_RULE_ELIGIBLE_T": verified["legal"]["LAST_RULE_ELIGIBLE_T"],
            "EXPECTED_ELIGIBLE_N": verified["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"],
            "year_eligible_n": verified["year_eligible_n"],
            "TRAILING_250_VALID_HISTORY_VERIFIED": True,
            "KNOWN_GAP_NEVER_FILLED": True,
        },
    }
    return payload


def legal_iso(verified: dict[str, Any]) -> str:
    return str(verified["legal"]["FIRST_RULE_ELIGIBLE_T"])


def render_markdown(prereg: dict[str, Any]) -> str:
    years = prereg["EXPECTED_ELIGIBLE_N_BY_YEAR"]
    return f"""# D2 BitMEX replication preregistration

**Unit:** `{prereg["unit"]}`  
**Kind:** outcome-blind replication preregistration. **Not executed.**

## Evidence class

`{prereg["EVIDENCE_CLASS"]}`

This is **not** `EXACT_BINANCE_CONFIRMATION`. A later positive result would
show portability of `D2 / RULE_1 / RV_ABSTENTION` across an earlier era,
BitMEX, and an inverse perpetual last-trade environment. Protected Binance
2025/2026 remains an unopened same-venue reserve.

## Frozen rule (unchanged)

Candidate: `{prereg["CANDIDATE"]}`

{prereg["CONFIRMATION_RULE"]}

`RV_BTC_24H(t)` is the frozen D2 definition: `sqrt(sum of 288 squared 5m log
returns)` via `rv_btc_24h`. No threshold sweep, no P85/P95 companion, no
alternate RV estimator, no alternate trailing window.

Direction: `{prereg["DIRECTION"]}`. Last-trade XBTUSD path. Do not invert
because the contract is inverse. Do not use mark, index, funding, or inverse
PnL. Exact-zero 24h return remains ineligible.

Entry: 5m open at `T = 00:05:00Z` (MARKET-05/06 convention, not redesigned).  
Outcome: 288 future 5m bars.  
Severity: frozen `arithmetic_mae` price-path metric.

## Sealed BitMEX authority

Parser `{prereg["SOURCE"]["parser_version"]}`. Timestamp = bucket end;
`open_time = timestamp - 5m`. Reacquisition of a different dataset is
forbidden. Execution must fail closed if authority or canonical hashes change.

- authority SHA256: `{prereg["SOURCE"]["authority_sha256"]}`
- canonical JSONL SHA256: `{prereg["SOURCE"]["canonical_jsonl_sha256"]}`
- canonical gzip SHA256: `{prereg["SOURCE"]["canonical_jsonl_gz_sha256"]}`

## Interval and missing data

```
FIRST_RULE_ELIGIBLE_T = {prereg["FIRST_RULE_ELIGIBLE_T"]}
LAST_RULE_ELIGIBLE_T  = {prereg["LAST_RULE_ELIGIBLE_T"]}
EXPECTED_ELIGIBLE_N   = {prereg["EXPECTED_ELIGIBLE_N"]}
2017 / 2018 / 2019    = {years["2017"]} / {years["2018"]} / {years["2019"]}
```

All 24h future paths complete strictly before `2020-01-01T00:00:00Z`.
Do not subsample to 815. 815 is a power floor only.

Known gap: 288 missing 5m opens
`{prereg["KNOWN_GAP"]["first_open"]}` through `{prereg["KNOWN_GAP"]["last_open"]}`.
Handling: `{prereg["KNOWN_GAP_HANDLING"]}`. Decisions whose RV window, trailing
valid history, entry, or future path need those bars are ineligible. Gap-day
decisions 2016-12-06/07/08 are excluded. Trailing-250 uses previous completed
valid decision-point rows, not fabricated calendar dates.
`TRAILING_250_VALID_HISTORY_VERIFIED = true`.

If constructed sample identity at execution differs from 1069 / frozen first /
frozen last, classify `D2_BITMEX_REPLICATION_INVALID`.

## Comparator and randomization

`RATE_MATCHED_RANDOM_ABSTENTION` with **year-matched** `K_y` inside 2017, 2018,
and 2019. Pooled-K across years is forbidden.

```
N_RANDOM_CONTROLS = {prereg["N_RANDOM_CONTROLS"]}
REPLICATION_RANDOM_SEED = {prereg["REPLICATION_RANDOM_SEED"]}
RNG = {prereg["RNG"]}
```

`MC_P` is diagnostic. The percentile gate is authoritative.

## Gates (unassigned)

```
STATISTICAL_GATE = {prereg["STATISTICAL_GATE"]}
PRACTICAL_GATE   = {prereg["PRACTICAL_GATE"]}
PRIMARY_PASS_RULE = {prereg["PRIMARY_PASS_RULE"]}
```

Yearly 2017/2018/2019 breakdowns are diagnostic only. They cannot rescue or
replace the pooled primary decision. No 2/3-year requirement.

Classifications frozen, **not assigned**:
`D2_BITMEX_REPLICATION_SUPPORTED` /
`D2_BITMEX_REPLICATION_NOT_SUPPORTED` /
`D2_BITMEX_REPLICATION_INVALID`.

## Power planning (not a sampling cap)

`REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (power `0.801`, Wilson 95% CI
`[0.7751234971811168, 0.824572794210579]`). `N=820` point-estimate `0.794`.
No further power search. Use all 1069 legal rows.

## Implementation binding

Reuse frozen `rv_btc_24h`, `btc_ret_24h`, `arithmetic_mae`. Adapt BitMEX
timestamp plumbing only. Execution is **not** authorized in this unit.

## Not created / not opened

- BitMEX D2 outcome: false
- Protected 2025/2026: false / false
- MARKET-07 / ARM: false

`NEXT_UNIT = {prereg["NEXT_UNIT"]}`  
`PR_READY_TO_MERGE = {prereg["PR_READY_TO_MERGE"]}`
"""


def write_artifacts(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    prereg = build_prereg(repo=base)
    binding = {
        "schema": "signalbot_d2_bitmex_replication_execution_binding",
        "PREREG_FROZEN": True,
        "EXECUTION_AUTHORIZED": False,
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "authority_rel": AUTHORITY_REL,
        "authority_sha256": prereg["SOURCE"]["authority_sha256"],
        "canonical_jsonl_sha256": prereg["SOURCE"]["canonical_jsonl_sha256"],
        "canonical_jsonl_gz_sha256": prereg["SOURCE"]["canonical_jsonl_gz_sha256"],
        "parser_version": PARSER_VERSION,
        "REPLICATION_RANDOM_SEED": D2_BITMEX_REPLICATION_RANDOM_SEED,
        "N_RANDOM_CONTROLS": N_REPLICATES,
        "FIRST_RULE_ELIGIBLE_T": prereg["FIRST_RULE_ELIGIBLE_T"],
        "LAST_RULE_ELIGIBLE_T": prereg["LAST_RULE_ELIGIBLE_T"],
        "EXPECTED_ELIGIBLE_N": FROZEN_EXPECTED_ELIGIBLE_N,
        "STATISTICAL_GATE": prereg["STATISTICAL_GATE"],
        "PRACTICAL_GATE": prereg["PRACTICAL_GATE"],
        "PRIMARY_PASS_RULE": prereg["PRIMARY_PASS_RULE"],
        "IMPLEMENTATION_FILES_ALLOWED_TO_EXECUTE": prereg["IMPLEMENTATION_FILES_ALLOWED_TO_EXECUTE"],
        "IMPLEMENTATION_FILE_SHA256": prereg["IMPLEMENTATION_FILE_SHA256"],
        "D2_BITMEX_OUTCOME_COMPUTED": False,
        "CLASSIFICATION_ASSIGNED": None,
    }
    (base / JSON_REL).write_text(json.dumps(prereg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (base / MD_REL).write_text(render_markdown(prereg), encoding="utf-8")
    (base / BINDING_REL).write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return prereg


if __name__ == "__main__":
    written = write_artifacts()
    keys = (
        "PREREG_FROZEN",
        "EVIDENCE_CLASS",
        "FIRST_RULE_ELIGIBLE_T",
        "LAST_RULE_ELIGIBLE_T",
        "EXPECTED_ELIGIBLE_N",
        "REPLICATION_RANDOM_SEED",
        "N_RANDOM_CONTROLS",
        "STATISTICAL_GATE",
        "PRACTICAL_GATE",
        "PRIMARY_PASS_RULE",
        "D2_BITMEX_OUTCOME_COMPUTED",
        "PR_READY_TO_MERGE",
        "NEXT_UNIT",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
    print("canonical", written["SOURCE"]["canonical_jsonl_sha256"])
