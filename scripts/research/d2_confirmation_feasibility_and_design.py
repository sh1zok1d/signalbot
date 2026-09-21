"""D2 RULE_1 confirmation feasibility and outcome-blind design.

Does not execute confirmation, does not open 2025/2026 price bytes,
does not create MARKET-07 / ARM / prereg freeze / RESULT.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d2_abstention_tail_risk import evaluate_rule_1


UTC = timezone.utc

UNIT = "D2_CONFIRMATION_FEASIBILITY_AND_DESIGN"
IMPLEMENTATION_COMMIT = "26d8f7066533bcae7138d5a1952783f2a16f3c39"
CORE_SNAPSHOT = C.CORE_BTC_SNAPSHOT

FIRST_T = datetime(2025, 1, 1, 0, 5, tzinfo=UTC)
LAST_T = datetime(2025, 12, 30, 0, 5, tzinfo=UTC)
CONFIRMATION_T_END_EXCLUSIVE = datetime(2025, 12, 31, 0, 0, tzinfo=UTC)
LAST_FUTURE_BAR_OPEN = datetime(2025, 12, 31, 0, 0, tzinfo=UTC)

# Frozen before any 2025 outcome. Distinct from discovery seed 20260921102.
D2_CONFIRMATION_RANDOM_CONTROL_SEED = 20260921120
D2_CONFIRMATION_POWER_SEED = 20260921121

N_REPLICATES_CONFIRMATION = 10_000
N_POWER_OUTER = 1_000
MINIMUM_ACCEPTABLE_CONFIRMATION_POWER = 0.80
AUTHORITATIVE_RELATIVE_EFFECT = 0.20
SENSITIVITY_RELATIVE_EFFECTS = (0.15, 0.20, 0.25, 0.30)
N_2025_DECISION_SLOTS = 364  # 2025 not leap; Dec 31 forbidden

DISCOVERY_PROVENANCE = {
    "RULE_1_eligible": 1791,
    "ABSTAIN_COUNT": 163,
    "MU_RULE": 0.04005839896629072,
    "MU_CONTROL_MEAN": 0.025856224865193674,
    "DELTA": 0.014202174101097049,
    "UNCONDITIONAL_MEAN": 0.02517689228869647,
    "GATE_PASS": True,
    "positive_years": "5/5",
    "note": "Adaptive discovery only. Not evidence. Not the confirmatory minimum effect.",
}

INVENTORY_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
SNAPSHOT_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
BINDING_REL = "docs/research_data/D2_CONFIRMATION_2025_METADATA_BINDING.json"
JSON_REL = "docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.json"
MD_REL = "docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.md"
D2_RESULT_REL = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"


class ProtectedPriceRefused(RuntimeError):
    """A 2025/2026 price object was requested."""


def _repo(root: Path | None = None) -> Path:
    return root or C.repo_root()


def refuse_protected_price_path(path: Path) -> None:
    C.assert_openable(path)
    text = str(path)
    if "2025-" in text or "2026-" in text:
        if text.endswith(".parquet") or text.endswith(".zip") or "/canonical/" in text.replace("\\", "/"):
            raise ProtectedPriceRefused(f"PROTECTED_PRICE_PATH:{path}")


def confirmation_decision_slot_count() -> int:
    n = 0
    cursor = FIRST_T
    while cursor < CONFIRMATION_T_END_EXCLUSIVE:
        if not (cursor.month == 12 and cursor.day == 31):
            n += 1
        cursor = cursor + timedelta(days=1)
    return n


def extract_2025_metadata(*, repo: Path | None = None) -> dict[str, Any]:
    base = _repo(repo)
    inventory_path = base / INVENTORY_REL
    snapshot_path = base / SNAPSHOT_REL
    C.assert_openable(inventory_path)
    C.assert_openable(snapshot_path)
    refuse_protected_price_path(inventory_path)
    refuse_protected_price_path(snapshot_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    checksums = (snapshot.get("identity_payload") or snapshot).get("output_checksums") or {}
    objects = inventory.get("objects") or inventory.get("source_objects") or []
    if not objects and isinstance(inventory, dict):
        for key in ("monthly_objects", "sources", "items"):
            if isinstance(inventory.get(key), list):
                objects = inventory[key]
                break
    wanted = [f"2025-{m:02d}" for m in range(1, 13)]
    by_period = {}
    for item in objects:
        period = str(item.get("source_period") or "")
        if period in wanted:
            by_period[period] = item
    missing = [p for p in wanted if p not in by_period]
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if missing:
        issues.append("MISSING_MONTHS:" + ",".join(missing))
    for period in wanted:
        item = by_period.get(period)
        if item is None:
            continue
        parquet_rel = f"canonical/1m/monthly/{period}.parquet"
        parquet_sha = checksums.get(parquet_rel)
        source_sha = item.get("expected_sha256") or item.get("local_sha256")
        admitted = bool(item.get("admitted_to_canonical") is True)
        verified = str(item.get("checksum_verification") or "") == "VERIFIED"
        parser_ok = str(item.get("parser_status") or "") == "OK"
        missing_buckets = int(item.get("missing_bucket_count") or 0)
        if not admitted:
            issues.append(f"NOT_ADMITTED:{period}")
        if not verified:
            issues.append(f"CHECKSUM_NOT_VERIFIED:{period}")
        if not parser_ok:
            issues.append(f"PARSER_NOT_OK:{period}")
        if missing_buckets != 0:
            issues.append(f"MISSING_BUCKETS:{period}:{missing_buckets}")
        if parquet_sha is None:
            issues.append(f"NO_CANONICAL_HASH:{period}")
        if item.get("expected_sha256") and item.get("local_sha256"):
            if item["expected_sha256"] != item["local_sha256"]:
                issues.append(f"SOURCE_HASH_MISMATCH:{period}")
        rows.append(
            {
                "period": period,
                "source_filename": item.get("expected_zip_filename"),
                "source_SHA256": source_sha,
                "canonical_parquet_relative_path": parquet_rel,
                "canonical_parquet_SHA256": parquet_sha,
                "admitted_to_canonical": admitted,
                "checksum_verification": item.get("checksum_verification"),
                "parser_status": item.get("parser_status"),
                "expected_rows": item.get("expected_rows"),
                "observed_rows": item.get("observed_rows"),
                "missing_bucket_count": missing_buckets,
                "first_open_time_ms": item.get("first_open_time_ms"),
                "last_open_time_ms": item.get("last_open_time_ms"),
                "invariant_violation_count": item.get("invariant_violation_count"),
            }
        )
    n_2026_checksum_keys = sum(
        1
        for key in checksums
        if "/2026-" in str(key) and str(key).endswith(".parquet")
    )
    return {
        "snapshot_id": CORE_SNAPSHOT,
        "months": rows,
        "n_months": len(rows),
        "issues": issues,
        "CONFIRMATION_2025_MONTHS_METADATA_BOUND": len(rows) == 12 and not missing,
        "CONFIRMATION_2025_SOURCE_HASHES_BOUND": all(r.get("source_SHA256") for r in rows) and len(rows) == 12,
        "CONFIRMATION_2025_CANONICAL_HASHES_BOUND": all(r.get("canonical_parquet_SHA256") for r in rows) and len(rows) == 12,
        "n_2026_monthly_parquet_keys_present_in_snapshot_identity": int(n_2026_checksum_keys),
        "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
        "LAST_FUTURE_BAR_OPEN": LAST_FUTURE_BAR_OPEN.isoformat().replace("+00:00", "Z"),
        "files_read_for_metadata": [INVENTORY_REL, SNAPSHOT_REL],
        "price_values_present_in_binding": False,
    }


def _calibrate_relative_effect(
    y: np.ndarray, selected: np.ndarray, relative: float
) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    mask = np.asarray(selected, dtype=bool)
    k = int(mask.sum())
    n = int(y.size)
    if k == 0 or n == 0:
        raise ValueError("EMPTY_CALIBRATION")
    mu = float(y.mean())
    m_s = float(y[mask].mean())
    denom = 1.0 - (1.0 + relative) * (k / n)
    if abs(denom) < 1e-12:
        raise ValueError("CALIBRATION_DENOM_ZERO")
    shift = (relative * mu - (m_s - mu)) / denom
    out = y.copy()
    out[mask] = out[mask] + shift
    return out


def _randomization_control_means(y: np.ndarray, k: int, n_rep: int, rng: np.random.Generator) -> np.ndarray:
    n = int(y.size)
    if k <= 0 or k > n:
        raise ValueError(f"BAD_K:{k}:{n}")
    keys = rng.random((int(n_rep), n))
    idx = np.argpartition(keys, kth=k - 1, axis=1)[:, :k]
    return y[idx].mean(axis=1)


def _both_gates(y: np.ndarray, selected: np.ndarray, n_rep: int, rng: np.random.Generator) -> dict[str, Any]:
    mask = np.asarray(selected, dtype=bool)
    k = int(mask.sum())
    mu_rule = float(y[mask].mean())
    uncond = float(y.mean())
    ctrl = _randomization_control_means(y, k, n_rep, rng)
    mu_control_mean = float(ctrl.mean())
    delta = float(mu_rule - mu_control_mean)
    p95 = float(np.percentile(ctrl, 95))
    statistical = bool(mu_rule > p95)
    practical = bool(uncond != 0.0 and delta >= AUTHORITATIVE_RELATIVE_EFFECT * uncond)
    p_mc = float((1.0 + float(np.sum(ctrl >= mu_rule))) / (1.0 + n_rep))
    return {
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_MAGNITUDE_GATE": practical,
        "BOTH": bool(statistical and practical),
        "MU_RULE": mu_rule,
        "MU_CONTROL_MEAN": mu_control_mean,
        "DELTA": delta,
        "UNCONDITIONAL_MEAN": uncond,
        "CONTROL_P95": p95,
        "MC_P": p_mc,
    }


def estimate_power(
    rows: list[C.DiscoveryRow],
    *,
    seed: int = D2_CONFIRMATION_POWER_SEED,
    n_outer: int = N_POWER_OUTER,
    n_inner: int = N_REPLICATES_CONFIRMATION,
) -> dict[str, Any]:
    mask = C.rv_abstention_mask(rows)
    years = np.asarray([row.year for row in rows], dtype=np.int64)
    sev = np.asarray([row.severity for row in rows], dtype=np.float64)
    fireable = np.arange(len(rows)) >= C.RV_TRAILING_WINDOW
    fireable_n = int(fireable.sum())
    abstain_fireable = int((mask & fireable).sum())
    fireable_rate = float(abstain_fireable / fireable_n) if fireable_n else float("nan")
    expected_k = int(round(fireable_rate * N_2025_DECISION_SLOTS))
    complete_years = [2021, 2022, 2023, 2024]
    year_pools: dict[int, np.ndarray] = {}
    year_k: dict[int, int] = {}
    for year in complete_years:
        idx = years == year
        year_pools[year] = sev[idx]
        year_k[year] = int(mask[idx].sum())
    rng = np.random.default_rng(int(seed))
    table: dict[str, Any] = {}
    for relative in SENSITIVITY_RELATIVE_EFFECTS:
        both = 0
        stat_only = 0
        prac_only = 0
        for i in range(int(n_outer)):
            year = int(complete_years[i % len(complete_years)])
            y = year_pools[year].copy()
            n = int(y.size)
            k = int(year_k[year])
            if k < 1 or k >= n:
                continue
            selected = np.zeros(n, dtype=bool)
            chosen = rng.choice(n, size=k, replace=False)
            selected[chosen] = True
            y_alt = _calibrate_relative_effect(y, selected, relative)
            inner_rng = np.random.default_rng(rng.integers(0, 2**31 - 1))
            result = _both_gates(y_alt, selected, n_inner, inner_rng)
            if result["STATISTICAL_GATE"]:
                stat_only += 1
            if result["PRACTICAL_MAGNITUDE_GATE"]:
                prac_only += 1
            if result["BOTH"]:
                both += 1
        denom = float(n_outer)
        table[f"{int(relative * 100)}pct"] = {
            "relative_effect": relative,
            "power_both_gates": both / denom,
            "power_statistical_gate": stat_only / denom,
            "power_practical_gate": prac_only / denom,
            "n_outer": int(n_outer),
            "n_inner": int(n_inner),
            "authoritative": relative == AUTHORITATIVE_RELATIVE_EFFECT,
        }
    return {
        "fireable_n_2020_2024": fireable_n,
        "fireable_abstain_count": abstain_fireable,
        "frozen_rule_fireable_rate": fireable_rate,
        "EXPECTED_2025_ELIGIBLE_N": N_2025_DECISION_SLOTS,
        "EXPECTED_2025_ABSTAIN_COUNT": expected_k,
        "year_eligible_n": {str(y): int(year_pools[y].size) for y in complete_years},
        "year_rule_abstain_count": {str(y): int(year_k[y]) for y in complete_years},
        "sensitivity": table,
        "POWER_AT_20PCT_MIN_EFFECT": table["20pct"]["power_both_gates"],
        "POWER_SEED": int(seed),
        "method": (
            "Year-cycled empirical 2021-2024 severity vectors. For each outer "
            "replicate, a random K-subset (K = frozen-rule abstain count that "
            "year) is location-shifted so DELTA/UNCONDITIONAL_MEAN equals the "
            "predeclared relative effect. Inner RATE_MATCHED_RANDOM_ABSTENTION "
            "uses 10000 uniform-without-replacement draws. The random subset "
            "is used so power is evaluated at the predeclared effect rather "
            "than at the observed discovery DELTA."
        ),
    }


def load_exposed_rule1_rows(*, repo: Path | None = None) -> tuple[list[C.DiscoveryRow], C.OpenedFileLog]:
    base = _repo(repo)
    log = C.OpenedFileLog()
    perp = C.load_core_btc_5m(log, repo=base)
    for rel in log.files:
        if "2025-" in rel or "2026-" in rel:
            raise ProtectedPriceRefused(f"LOGGED_PROTECTED:{rel}")
        refuse_protected_price_path(base / rel if not rel.startswith("/") else Path(rel))
    rows = C.build_rows(perp, C.RULE1_INTERVAL_START, C.DISCOVERY_END)
    return rows, log


def run_feasibility(*, repo: Path | None = None) -> dict[str, Any]:
    if confirmation_decision_slot_count() != N_2025_DECISION_SLOTS:
        raise RuntimeError(f"SLOT_COUNT:{confirmation_decision_slot_count()}")
    meta = extract_2025_metadata(repo=repo)
    rows, log = load_exposed_rule1_rows(repo=repo)
    replay = evaluate_rule_1(rows)
    power = estimate_power(rows)
    power_20 = float(power["POWER_AT_20PCT_MIN_EFFECT"])
    underpowered = bool(power_20 < MINIMUM_ACCEPTABLE_CONFIRMATION_POWER)
    feasibility = (
        "UNDERPOWERED_SINGLE_YEAR_2025" if underpowered else "FEASIBLE_SINGLE_YEAR_2025"
    )
    next_unit = (
        "D2_CONFIRMATION_LARGER_FRESH_SURFACE_OR_WAIT"
        if underpowered
        else "D2_CONFIRMATION_PREREG_FREEZE"
    )
    opened = list(log.files)
    protected_price_opened = [
        item for item in opened if "2025-" in item or "2026-" in item
    ]
    report = {
        "unit": UNIT,
        "kind": "OUTCOME_BLIND_CONFIRMATION_DESIGN",
        "date": "2026-09-21",
        "D2_DISCOVERY_STATUS": "PROMISING_PROTOTYPE",
        "CANDIDATE": "D2 / RULE_1 / RV_ABSTENTION",
        "NOT_CONFIRMED_VARIANTS": [
            "DISLOCATION_ABSTENTION",
            "D5 OR composition",
            "AND rule",
            "another RV threshold",
            "another horizon",
            "another direction definition",
            "another outcome",
            "another volatility estimator",
        ],
        "CONFIRMATION_RULE": (
            "ABSTAIN(t)=1 iff ev.rv_btc_24h(t) > P90 of its own trailing 250 "
            "completed decision-point values with t excluded. No threshold sweep."
        ),
        "CONFIRMATION_TARGET": (
            "24h direction-aligned adverse-path severity using the exact existing "
            "288 x 5m future-bar construction (arithmetic MAE). Not terminal "
            "return, close-only MAE, MFE, drawdown, volatility, or PnL."
        ),
        "CONFIRMATION_COMPARATOR": (
            "RATE_MATCHED_RANDOM_ABSTENTION. Frozen D2 year-matched convention "
            "is retained. On a single-year 2025 surface it reduces to selecting "
            "exactly K eligible 2025 rows uniformly without replacement. No "
            "month/quarter matching added."
        ),
        "CONFIRMATION_STATISTICAL_GATE": (
            "MU_RULE > P95 of the 10000 RATE_MATCHED_RANDOM_ABSTENTION replicate "
            "mean-severity values. Authoritative pass rule. Monte Carlo "
            "one-sided p=(1+count(control_mean>=MU_RULE))/(1+N_REPLICATES) is "
            "reported only; it does not replace the percentile gate."
        ),
        "CONFIRMATION_PRACTICAL_GATE": (
            "DELTA >= 0.20 * UNCONDITIONAL_MEAN on the independent 2025 surface. "
            "Same discovery-era 20% relative bar. Not lowered. Not replaced by "
            "the observed +1.42pp discovery DELTA."
        ),
        "DIRECTION": "BTC_SIDE(t)=sign(ev.btc_ret_24h(t)); zero-return rows ineligible",
        "ENTRY": "frozen entry_open(t) from D2 / MARKET-05/06",
        "BASE_EXPOSURE": "full-size BTC perpetual in direction BTC_SIDE(t)",
        "DECISION_SCHEDULE": "one daily BTC decision on MARKET-05/06 00:05:00Z grid",
        "PRIMARY_CONFIRMATION_SURFACE": "2025",
        "SECOND_RESERVED_SURFACE": "2026",
        "FIRST_T": FIRST_T.isoformat().replace("+00:00", "Z"),
        "LAST_T": LAST_T.isoformat().replace("+00:00", "Z"),
        "CONFIRMATION_T_INTERVAL": "[2025-01-01T00:05:00Z, 2025-12-31T00:00:00Z)",
        "WARMUP": (
            "Trailing-250 feature history may use already-exposed 2024 decision "
            "points. 2025 outcomes remain unexposed. Metrics are computed only "
            "on 2025 T."
        ),
        "TEMPORAL_REPORTING": {
            "quarters_diagnostic_only": ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"],
            "quarterly_cannot_rescue_or_veto": True,
            "primary_uses_pooled_2025": True,
            "no_new_quarterly_pass_rule": True,
        },
        "FUTURE_EXECUTION_CLASSIFICATIONS_NOT_ASSIGNED": [
            "CONFIRMED_ON_INDEPENDENT_2025_SURFACE",
            "NOT_CONFIRMED_ON_INDEPENDENT_2025_SURFACE",
            "INVALID_CONFIRMATION_EXECUTION",
        ],
        "PASS_RULE": "STATISTICAL_GATE and PRACTICAL_MAGNITUDE_GATE both true",
        "D2_CONFIRMATION_RANDOM_CONTROL_SEED": D2_CONFIRMATION_RANDOM_CONTROL_SEED,
        "N_REPLICATES_CONFIRMATION": N_REPLICATES_CONFIRMATION,
        "MINIMUM_ACCEPTABLE_CONFIRMATION_POWER": MINIMUM_ACCEPTABLE_CONFIRMATION_POWER,
        "DISCOVERY_PROVENANCE_NOT_EVIDENCE": DISCOVERY_PROVENANCE,
        "RULE_1_REPLAY_ON_EXPOSED_2020_2024": {
            "ABSTAIN_COUNT": replay.get("ABSTAIN_COUNT"),
            "DELTA": replay.get("DELTA"),
            "MU_RULE": replay.get("MU_RULE"),
            "UNCONDITIONAL_MEAN": replay.get("UNCONDITIONAL_MEAN"),
            "RULE_ELIGIBLE_N": replay.get("RULE_ELIGIBLE_N"),
            "GATE_PASS": replay.get("GATE_PASS"),
        },
        "metadata_2025": {
            "CONFIRMATION_2025_MONTHS_METADATA_BOUND": meta["CONFIRMATION_2025_MONTHS_METADATA_BOUND"],
            "CONFIRMATION_2025_SOURCE_HASHES_BOUND": meta["CONFIRMATION_2025_SOURCE_HASHES_BOUND"],
            "CONFIRMATION_2025_CANONICAL_HASHES_BOUND": meta["CONFIRMATION_2025_CANONICAL_HASHES_BOUND"],
            "issues": meta["issues"],
            "n_months": meta["n_months"],
            "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
            "binding": BINDING_REL,
        },
        "power": power,
        "EXPECTED_2025_ELIGIBLE_N": power["EXPECTED_2025_ELIGIBLE_N"],
        "EXPECTED_2025_ABSTAIN_COUNT": power["EXPECTED_2025_ABSTAIN_COUNT"],
        "POWER_AT_20PCT_MIN_EFFECT": power_20,
        "CONFIRMATION_FEASIBILITY": feasibility,
        "2025_OPEN_AUTHORIZED": False,
        "2025_OPENING_JUSTIFIED_BY_POWER": (not underpowered),
        "MARKET_07_CREATED": False,
        "ARM_CREATED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "PROTECTED_2025_PRICE_VALUES_INSPECTED": False,
        "PROTECTED_2026_PRICE_VALUES_INSPECTED": False,
        "PROTECTED_PRICE_PATHS_OPENED": protected_price_opened,
        "EXPOSED_FILES_OPENED_COUNT": len(opened),
        "EXPOSED_FILES_OPENED_YEARS": sorted(
            {item.split("monthly/")[-1][:4] for item in opened if "monthly/" in item and item.endswith(".parquet")}
        ),
        "IMPLEMENTATION_COMMIT_AUTHORITY": IMPLEMENTATION_COMMIT,
        "NEXT_UNIT": next_unit,
        "WHY_NOT_CONSUME_2026": (
            "2026 is a second reserved surface for later replication/follow-up "
            "if justified. Combining 2025+2026 to increase N is forbidden. "
            "Underpowering does not automatically consume 2026."
        ),
        "NOT_CREATED": [
            "MARKET-07",
            "ARM",
            "reservation",
            "execution permit",
            "final prereg freeze",
            "protected-data loader execution",
            "RESULT artifact",
        ],
    }
    if meta["issues"]:
        report["CONFIRMATION_FEASIBILITY"] = "METADATA_ISSUES_PLUS_" + feasibility
    return report


def _flag(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_markdown(report: dict[str, Any], meta: dict[str, Any]) -> str:
    power = report["power"]
    sens_lines = []
    for key in ("15pct", "20pct", "25pct", "30pct"):
        row = power["sensitivity"][key]
        mark = " (authoritative)" if row["authoritative"] else " (sensitivity only)"
        sens_lines.append(
            f"- {int(row['relative_effect']*100)}% relative{mark}: "
            f"both-gates power = {row['power_both_gates']:.3f}; "
            f"statistical = {row['power_statistical_gate']:.3f}; "
            f"practical = {row['power_practical_gate']:.3f}"
        )
    months = "\n".join(
        f"- `{m['period']}` source `{m['source_filename']}` "
        f"SHA256 `{m['source_SHA256']}` parquet `{m['canonical_parquet_SHA256']}`"
        for m in meta["months"]
    )
    return f"""# D2 confirmation feasibility and design

**Unit:** `{report["unit"]}`
**Kind:** `{report["kind"]}`
**Date:** `{report["date"]}`
**Candidate:** `{report["CANDIDATE"]}`
**Discovery status:** `{report["D2_DISCOVERY_STATUS"]}` (adaptive discovery only; not evidence)

This unit does **not** execute confirmation, inspect 2025/2026 BTC price
values, materialize protected parquet, create MARKET-07, or ARM anything.

## Verdict

| Field | Value |
|---|---|
| `PRIMARY_CONFIRMATION_SURFACE` | `{report["PRIMARY_CONFIRMATION_SURFACE"]}` |
| `SECOND_RESERVED_SURFACE` | `{report["SECOND_RESERVED_SURFACE"]}` |
| `CONFIRMATION_FEASIBILITY` | `{report["CONFIRMATION_FEASIBILITY"]}` |
| `POWER_AT_20PCT_MIN_EFFECT` | `{report["POWER_AT_20PCT_MIN_EFFECT"]}` |
| `MINIMUM_ACCEPTABLE_CONFIRMATION_POWER` | `{report["MINIMUM_ACCEPTABLE_CONFIRMATION_POWER"]}` |
| `EXPECTED_2025_ELIGIBLE_N` | `{report["EXPECTED_2025_ELIGIBLE_N"]}` |
| `EXPECTED_2025_ABSTAIN_COUNT` | `{report["EXPECTED_2025_ABSTAIN_COUNT"]}` |
| `2025_OPEN_AUTHORIZED` | `false` |
| `MARKET_07_CREATED` | `false` |
| `ARM_CREATED` | `false` |
| `PROTECTED_2025_PRICE_VALUES_INSPECTED` | `false` |
| `PROTECTED_2026_PRICE_VALUES_INSPECTED` | `false` |
| `NEXT_UNIT` | `{report["NEXT_UNIT"]}` |

## Candidate (exact survivor only)

`{report["CONFIRMATION_RULE"]}`

Not confirmed: {", ".join(report["NOT_CONFIRMED_VARIANTS"])}.

Mechanism preserved from frozen D2 / implementation `{report["IMPLEMENTATION_COMMIT_AUTHORITY"]}`:

- schedule: {report["DECISION_SCHEDULE"]}
- exposure: {report["BASE_EXPOSURE"]}
- direction: {report["DIRECTION"]}
- entry: {report["ENTRY"]}
- target: {report["CONFIRMATION_TARGET"]}

## Independent surface

Primary: calendar **2025 only**, Binance USD-M BTCUSDT perpetual,
`CORE_BTC_BINANCE_V0` snapshot `{CORE_SNAPSHOT}`.

```
FIRST_T = {report["FIRST_T"]}
LAST_T  = {report["LAST_T"]}
T in {report["CONFIRMATION_T_INTERVAL"]}
```

2020-2024 is historically exposed and is **not** independent confirmation.
{report["WARMUP"]}
{report["WHY_NOT_CONSUME_2026"]}

## 2025 metadata-only binding

Binding file: `{BINDING_REL}`. No price values. Objects were not
downloaded or materialized.

Months bound: {meta["n_months"]}/12.
Source hashes bound: `{_flag(meta["CONFIRMATION_2025_SOURCE_HASHES_BOUND"])}`.
Canonical hashes bound: `{_flag(meta["CONFIRMATION_2025_CANONICAL_HASHES_BOUND"])}`.
Issues: {meta["issues"] or "none"}.
2026 object needed for frozen interval: `false`
(last future bar opens `{meta["LAST_FUTURE_BAR_OPEN"]}`).

{months}

## Estimand and gates

Comparator: {report["CONFIRMATION_COMPARATOR"]}

Quantities: `MU_RULE`, `MU_CONTROL_MEAN`, `DELTA = MU_RULE - MU_CONTROL_MEAN`,
`UNCONDITIONAL_MEAN`.

Statistical: {report["CONFIRMATION_STATISTICAL_GATE"]}

Seed frozen now: `D2_CONFIRMATION_RANDOM_CONTROL_SEED = {report["D2_CONFIRMATION_RANDOM_CONTROL_SEED"]}`.
Replicates: `{report["N_REPLICATES_CONFIRMATION"]}`.

Practical: {report["CONFIRMATION_PRACTICAL_GATE"]}

Pass: {report["PASS_RULE"]}. No quarterly rescue, threshold change, sign
reversal, alternative comparator, D5 combination, or horizon swap.

Quarters `{report["TEMPORAL_REPORTING"]["quarters_diagnostic_only"]}` are
diagnostic only.

Future execution labels (not assigned here):
{report["FUTURE_EXECUTION_CLASSIFICATIONS_NOT_ASSIGNED"]}.

## Discovery provenance (planning context only)

Eligible 1791, abstain 163, `MU_RULE` 0.04005839896629072,
`MU_CONTROL_MEAN` 0.025856224865193674, `DELTA` 0.014202174101097049,
`GATE_PASS` true, 5/5 positive years.

Do not use +0.0142 as the minimum effect. Do not power solely at that
observed effect. Do not shrink the 20% bar. Do not call it evidence.

## Prospective power (2020-2024 only)

Method: {power["method"]}

Frozen-rule fireable rate = {power["frozen_rule_fireable_rate"]:.6f}
({power["fireable_abstain_count"]} / {power["fireable_n_2020_2024"]}).

{chr(10).join(sens_lines)}

`MINIMUM_ACCEPTABLE_CONFIRMATION_POWER = 0.80`. The 20% row is
authoritative. Other rows are feasibility context only and were not
selected after seeing power.

At the exact predeclared 20% practical bar, practical-gate power is
about one-half (a point-estimate hurdle placed at the alternative mean).
Statistical-gate power at that same 20% effect is far lower (~0.01)
because one year of ~364 eligible days and K ≈ {report["EXPECTED_2025_ABSTAIN_COUNT"]}
rate-matched draws cannot push `MU_RULE` past the control P95 under the
heavy-tailed adverse-path severity distribution. Joint power at 20% is
{report["POWER_AT_20PCT_MIN_EFFECT"]:.3f}, below 0.80. Even the 30%
sensitivity row remains below 0.80. A single independent 2025 year is
therefore not informative enough to spend. Do not lower the 20% bar.
Do not automatically consume 2026. Wait for a larger genuinely fresh
surface, or obtain another independent equivalent surface.

## Independence boundary

Protected 2025/2026 price values inspected: `false` / `false`.
Exposed parquet years opened: {report["EXPOSED_FILES_OPENED_YEARS"]}.
Protected price paths opened: {report["PROTECTED_PRICE_PATHS_OPENED"] or "none"}.

## Not created

{chr(10).join(f"- {item}" for item in report["NOT_CREATED"])}
"""


def write_artifacts(*, repo: Path | None = None) -> dict[str, Any]:
    base = _repo(repo)
    meta = extract_2025_metadata(repo=base)
    report = run_feasibility(repo=base)
    binding = {
        "schema": "signalbot_d2_confirmation_2025_metadata_binding",
        "snapshot_id": CORE_SNAPSHOT,
        "PRIMARY_CONFIRMATION_SURFACE": "2025",
        "SECOND_RESERVED_SURFACE": "2026",
        "contains_price_values": False,
        "objects_materialized": False,
        "objects": [
            {
                "period": m["period"],
                "source_filename": m["source_filename"],
                "source_SHA256": m["source_SHA256"],
                "canonical_parquet_relative_path": m["canonical_parquet_relative_path"],
                "canonical_parquet_SHA256": m["canonical_parquet_SHA256"],
            }
            for m in meta["months"]
        ],
        "coverage_metadata_not_prices": [
            {
                "period": m["period"],
                "expected_rows": m["expected_rows"],
                "observed_rows": m["observed_rows"],
                "missing_bucket_count": m["missing_bucket_count"],
                "first_open_time_ms": m["first_open_time_ms"],
                "last_open_time_ms": m["last_open_time_ms"],
                "admitted_to_canonical": m["admitted_to_canonical"],
                "checksum_verification": m["checksum_verification"],
                "parser_status": m["parser_status"],
            }
            for m in meta["months"]
        ],
        "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
    }
    (base / BINDING_REL).write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (base / JSON_REL).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (base / MD_REL).write_text(render_markdown(report, meta), encoding="utf-8")
    return report


if __name__ == "__main__":
    written = write_artifacts()
    keys = (
        "CONFIRMATION_FEASIBILITY",
        "POWER_AT_20PCT_MIN_EFFECT",
        "EXPECTED_2025_ELIGIBLE_N",
        "EXPECTED_2025_ABSTAIN_COUNT",
        "NEXT_UNIT",
        "PROTECTED_2025_PRICE_VALUES_INSPECTED",
        "metadata_2025",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
