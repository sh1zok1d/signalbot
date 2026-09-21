"""Adjudicate DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.

Spec-level only. Does not execute the gate, does not compute D1 targets,
and does not invent a daily-return -> ev.rv_btc_24h mapping.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    RV_RETURN_COUNT,
    rv_btc_24h,
)


AUTHORITY_RELATIVE = (
    "docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.json",
    "docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.md",
    "docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.json",
    "docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.md",
)

FORBIDDEN_SUBSTITUTES = (
    "abs(daily_return)",
    "garch sigma",
    "squared daily return",
    "synthetic conditional variance",
    "intraday bridge",
    "brownian bridge",
)

EXPLICIT_MAPPING_PHRASES = (
    "synthetic ev.rv_btc_24h",
    "synthetic rv_btc_24h",
    "map daily return",
    "daily-return-to-rv",
    "construct ev.rv_btc_24h from",
    "proxy ev.rv_btc_24h",
)

TARGET_TOKENS = (
    "MEAN_STATE_RUN_LENGTH",
    "HIGH_VOL_STATE",
    "LOW_VOL_STATE",
)

JSON_REL = "docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.json"
MD_REL = "docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.md"


class D1NullAdequacyRefused(RuntimeError):
    """Adequacy-gate execution is not legal under the frozen spec."""


def _repo(root: Path | None = None) -> Path:
    return root or C.repo_root()


def _load_json(rel: str, *, repo: Path) -> dict[str, Any]:
    path = repo / rel
    C.assert_openable(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _authority_text(repo: Path) -> str:
    chunks: list[str] = []
    for rel in AUTHORITY_RELATIVE:
        path = repo / rel
        C.assert_openable(path)
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def frozen_null_generates_daily_returns(spec: dict[str, Any]) -> str:
    null = spec["cards"]["D1"]["EXACT_SIMPLE_BASELINE_NULL"]
    return str(null["surrogate_generation"])


def frozen_rv20_requires_ev_rv(spec: dict[str, Any]) -> str:
    fix = spec["cards"]["D1"]["red_team_correction_2026_09_21"]["F6_RV_20_formula_fix"]
    return str(fix)


def frozen_mapping_exists(authority_text: str) -> bool:
    """Return True only if authorities already freeze a same-observable map.

    A mention of a forbidden substitute, or of F3's rejected intraday bridge,
    is not a mapping. Require an explicit construction of synthetic
    ev.rv_btc_24h from the GARCH daily-return path.
    """
    lowered = authority_text.lower()
    compact = lowered.replace(" ", "")
    if "dailyreturnpath->" in compact and "ev.rv_btc_24h" in lowered:
        return True
    return any(phrase in lowered for phrase in EXPLICIT_MAPPING_PHRASES)


def f3_rejected_intraday_bridge(red_team: dict[str, Any]) -> str:
    return str(red_team["findings"]["F3"]["fix_applied"]["rejected_option"])


def f3_null_granularity(red_team: dict[str, Any]) -> str:
    return str(red_team["findings"]["F3"]["verification"])


def underspecification_findings(red_team: dict[str, Any]) -> list[str]:
    f5 = red_team["findings"]["F5"]["fix_applied"]
    checks = f5["checks"]
    leverage = next(item for item in checks if "Leverage" in item["statistic"])
    rv20 = next(item for item in checks if item["statistic"].startswith("RV_20"))
    abs_short = next(item for item in checks if "SHORT lags 1-10" in item["statistic"])
    findings: list[str] = []
    if " or " in leverage["statistic"].lower():
        findings.append("LEVERAGE_PROXY_OR_CLAUSE: " + leverage["statistic"])
    if "short-lag" in rv20["statistic"].lower() and "lags 1-" not in rv20["statistic"].lower():
        findings.append("RV_20_SHORT_LAG_ACF_LAG_SET_UNENUMERATED: " + rv20["statistic"])
    if "at each lag" not in rv20["rule"].lower():
        findings.append("RV_20_LAGWISE_PASS_FAIL_UNSPECIFIED: " + rv20["rule"])
    skew = next(item for item in checks if "skewness" in item["statistic"].lower())
    if (
        "skewness and kurtosis" in skew["statistic"].lower()
        and "real-data value" in skew["rule"].lower()
    ):
        findings.append("SKEW_KURTOSIS_JOINT_VS_INDIVIDUAL_UNSPECIFIED: " + skew["rule"])
    abs_stat = abs_short["statistic"].lower()
    if " or " in abs_stat or "(or " in abs_stat or "squared-return" in abs_stat:
        findings.append("ABS_OR_SQUARED_RETURN_ACF_OR_CLAUSE: " + abs_short["statistic"])
    findings.append(
        "NAN_DEGENERATE_TREATMENT_UNSPECIFIED: frozen gate never states NaN/degenerate handling"
    )
    findings.append(
        "GARCH_ESTIMATION_UNSPECIFIED: Student-t MLE is named, but library, "
        "optimizer, parameter constraints, and MLE initialization are not frozen"
    )
    return findings


def observable_granularity_mismatch(
    *,
    mapping: bool,
    null_generation: str,
    rv20_formula: str,
) -> bool:
    if mapping:
        return False
    daily_null = (
        "24h-return path" in null_generation
        or "24h return" in null_generation.lower()
        or "surrogate 24h-return" in null_generation.lower()
    )
    rv_needs_intraday = "ev.rv_btc_24h" in rv20_formula
    return bool(daily_null and rv_needs_intraday)


def refuse_protected_year(period: str) -> None:
    token = str(period)
    path = Path(f"canonical/1m/monthly/{token}.parquet")
    if (
        C.path_is_protected_partition(path)
        or token.startswith("2025")
        or token.startswith("2026")
        or "2025-" in token
        or "2026-" in token
    ):
        raise C.ProtectedYearRefused(f"D1_NULL_ADEQUACY_PROTECTED:{period}")


def adjudicate(*, repo: Path | None = None) -> dict[str, Any]:
    base = _repo(repo)
    spec = _load_json("docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.json", repo=base)
    red_team = _load_json("docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.json", repo=base)
    authority = _authority_text(base)
    null_generation = frozen_null_generates_daily_returns(spec)
    rv20_formula = frozen_rv20_requires_ev_rv(spec)
    mapping = frozen_mapping_exists(authority)
    forbidden_hits = [token for token in FORBIDDEN_SUBSTITUTES if token in authority.lower()]
    under = underspecification_findings(red_team)
    mismatch = observable_granularity_mismatch(
        mapping=mapping,
        null_generation=null_generation,
        rv20_formula=rv20_formula,
    )
    if RV_RETURN_COUNT != 288:
        raise D1NullAdequacyRefused(f"RV_RETURN_COUNT:{RV_RETURN_COUNT}")
    if inspect.getsource(rv_btc_24h).count("log") < 1:
        raise D1NullAdequacyRefused("RV_BTC_24H_SOURCE_UNEXPECTED")

    if mismatch:
        status = "DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH"
    elif under:
        status = "DEFERRED_NULL_ADEQUACY_SPEC_INCOMPLETE"
    else:
        status = "UNDER_REVIEW"

    next_unit = (
        "D2_CONFIRMATION_FEASIBILITY_AND_DESIGN"
        if mismatch or under
        else "DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE_EXECUTION"
    )

    return {
        "unit": "DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE",
        "kind": "PRE_EXECUTION_ADJUDICATION",
        "date": "2026-09-21",
        "D1_NULL_MODEL_OBSERVABLE_MISMATCH": bool(mismatch),
        "D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED": bool(under),
        "D1_NULL_ADEQUACY_GATE_EXECUTED": False,
        "D1_NULL_ADEQUACY_GATE_RESULT": None,
        "D1_TARGET_OUTCOME_COMPUTED": False,
        "D1_STATUS": status,
        "REAL_STATE_OBSERVABLE": (
            "intraday realized volatility (ev.rv_btc_24h from 288 x 5m log "
            "returns; RV_20 L2-aggregates 20 of those daily RV values)"
        ),
        "NULL_GENERATED_OBSERVABLE": (
            "synthetic DAILY 24h-return path from GARCH(1,1)+Student-t "
            "filtered circular block-bootstrap"
        ),
        "FROZEN_NULL_SURROGATE_GENERATION": null_generation,
        "FROZEN_RV_20_FORMULA": rv20_formula,
        "FROZEN_SAME_OBSERVABLE_MAPPING": mapping,
        "FORBIDDEN_SUBSTITUTE_PHRASES_PRESENT_IN_AUTHORITY": forbidden_hits,
        "UNDERSPECIFIED_GATE_QUANTITIES": under,
        "WHY_DEFER_RATHER_THAN_REPAIR": (
            "D2-D5 scientific outcomes are already known. Sprint 01 specs were "
            "intended to be frozen before any card outcome. A new D1 null or "
            "new gate definitions would be a post-sibling-outcome redesign and "
            "must be a future D1-v2 card, not an in-sprint repair."
        ),
        "INTERNAL_DISCOVERY_CARDS_EXECUTED": 4,
        "INTERNAL_PROMISING_PROTOTYPES": 1,
        "D2_STATUS": "PROMISING_PROTOTYPE",
        "D3_STATUS": "NO_USEFUL_STRUCTURE",
        "D4_STATUS": "NO_USEFUL_STRUCTURE",
        "D5_STATUS": "NO_USEFUL_STRUCTURE",
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "NEXT_UNIT": next_unit,
        "RV_RETURN_COUNT": RV_RETURN_COUNT,
        "F3_PRIOR_FINDING": f3_null_granularity(red_team),
        "F3_REJECTED_INTRADAY_BRIDGE": f3_rejected_intraday_bridge(red_team),
        "NOT_DONE": [
            "no synthetic intraday bridge",
            "no 5m GARCH refit",
            "no null replacement",
            "no D1 scientific target",
            "no HIGH_VOL_STATE / LOW_VOL_STATE sequence",
            "no MEAN_STATE_RUN_LENGTH",
            "no 2025/2026 access",
        ],
    }


def execute_adequacy_gate(*, repo: Path | None = None) -> None:
    """Hard refuse. The frozen spec is not executable as a same-observable gate."""
    report = adjudicate(repo=repo)
    if report["D1_NULL_MODEL_OBSERVABLE_MISMATCH"] or report["D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED"]:
        raise D1NullAdequacyRefused(
            "D1_NULL_ADEQUACY_GATE_NOT_EXECUTABLE:"
            f"mismatch={report['D1_NULL_MODEL_OBSERVABLE_MISMATCH']}:"
            f"underspecified={report['D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED']}"
        )
    raise D1NullAdequacyRefused("D1_NULL_ADEQUACY_GATE_NOT_ARMED")


def _flag(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    under = "\n".join(f"- `{item}`" for item in report["UNDERSPECIFIED_GATE_QUANTITIES"])
    forbidden = report["FORBIDDEN_SUBSTITUTE_PHRASES_PRESENT_IN_AUTHORITY"]
    forbidden_txt = ", ".join(f"`{item}`" for item in forbidden) if forbidden else "(none as authorized maps)"
    not_done = "\n".join(f"- {item}" for item in report["NOT_DONE"])
    return f"""# Discovery Sprint 01 — D1 Null Adequacy Gate Adjudication

**Unit:** `{report["unit"]}`
**Kind:** `{report["kind"]}`
**Date:** `{report["date"]}`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.json`

This is **not** D1 scientific execution. The adequacy gate was **not**
run. D1 target statistics were **not** computed. D2–D5 results are
unchanged. Protected 2025/2026 was not opened. MARKET-07 was not created.

## Verdict

| Field | Value |
|---|---|
| `D1_NULL_MODEL_OBSERVABLE_MISMATCH` | `{_flag(report["D1_NULL_MODEL_OBSERVABLE_MISMATCH"])}` |
| `D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED` | `{_flag(report["D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED"])}` |
| `D1_NULL_ADEQUACY_GATE_EXECUTED` | `{_flag(report["D1_NULL_ADEQUACY_GATE_EXECUTED"])}` |
| `D1_NULL_ADEQUACY_GATE_RESULT` | `{_flag(report["D1_NULL_ADEQUACY_GATE_RESULT"])}` |
| `D1_TARGET_OUTCOME_COMPUTED` | `{_flag(report["D1_TARGET_OUTCOME_COMPUTED"])}` |
| `D1_STATUS` | `{report["D1_STATUS"]}` |
| `NEXT_UNIT` | `{report["NEXT_UNIT"]}` |
| `INTERNAL_DISCOVERY_CARDS_EXECUTED` | `{report["INTERNAL_DISCOVERY_CARDS_EXECUTED"]}` |
| `INTERNAL_PROMISING_PROTOTYPES` | `{report["INTERNAL_PROMISING_PROTOTYPES"]}` |
| `D2_STATUS` | `{report["D2_STATUS"]}` |
| `MARKET_07_CREATED` | `{_flag(report["MARKET_07_CREATED"])}` |
| `PROTECTED_2025_OPENED` | `{_flag(report["PROTECTED_2025_OPENED"])}` |
| `PROTECTED_2026_OPENED` | `{_flag(report["PROTECTED_2026_OPENED"])}` |

Primary classification is **C** (`DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`).
The independent second check is also true (D), but does not replace the
fatal first finding.

## Check A — same-observable mapping

Frozen D1 state variable:

```
daily RV input = ev.rv_btc_24h(t)
RV_BTC_24H    = sqrt(sum_{{i=1..288}} r_i^2)   # 288 x 5m intra-day log returns
RV_20(t)      = sqrt(sum_{{i=0..19}} [ev.rv_btc_24h(t-i)]^2)
```

`ev.rv_btc_24h` is the MARKET-06 evaluator function
(`RV_RETURN_COUNT = {report["RV_RETURN_COUNT"]}`).

Frozen D1 null (`EXACT_SIMPLE_BASELINE_NULL.surrogate_generation`):

> {report["FROZEN_NULL_SURROGATE_GENERATION"]}

Corrected RV_20 (F6):

> {report["FROZEN_RV_20_FORMULA"]}

| Object | Frozen identity |
|---|---|
| `REAL_STATE_OBSERVABLE` | {report["REAL_STATE_OBSERVABLE"]} |
| `NULL_GENERATED_OBSERVABLE` | {report["NULL_GENERATED_OBSERVABLE"]} |
| `FROZEN_SAME_OBSERVABLE_MAPPING` | `{_flag(report["FROZEN_SAME_OBSERVABLE_MAPPING"])}` |

No exact already-frozen mapping

`synthetic DAILY return path -> synthetic ev.rv_btc_24h -> synthetic RV_20`

exists in the authority documents. The following substitutes are **not**
used, and are not authorized as mappings: `abs(daily_return)`, GARCH
sigma, squared daily return, synthetic conditional variance. Forbidden
substitute phrases that appear in authority text (as **rejected**
options, not as maps): {forbidden_txt}.

F3 already recorded that D1's null generates exactly one scalar
surrogate 24h return per decision point and cannot produce a 288×5m
path. An arbitrary intraday bridge was explicitly rejected:

> {report["F3_REJECTED_INTRADAY_BRIDGE"]}

F5's adequacy gate still requires surrogate `RV_20`, which is defined
only via `ev.rv_btc_24h`. That is a requirement, not a mapping.

Therefore:

```
D1_NULL_MODEL_OBSERVABLE_MISMATCH = true
```

The gate is not executed. No synthetic intraday bridge is created. No
5m GARCH is refit after sibling-card outcomes. The null is not replaced.

## Check B — adequacy-gate executability

Even if a same-observable mapping existed, the frozen gate is not
mathematically executable without new researcher degrees of freedom.
Underspecified quantities:

{under}

```
D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED = true
```

No researcher-defined substitute is executed.

## Why defer rather than repair

{report["WHY_DEFER_RATHER_THAN_REPAIR"]}

A future D1-v2 may be designed as a **new** discovery card/unit,
explicitly acknowledging that Sprint 01 sibling outcomes were already
observed.

## Program state

Deferred D1 is **not** counted as executed. D2 remains
`PROMISING_PROTOTYPE`. No confirmatory claim is created.

## Not done

{not_done}
"""


def write_artifacts(*, repo: Path | None = None) -> dict[str, Any]:
    base = _repo(repo)
    report = adjudicate(repo=base)
    json_path = base / JSON_REL
    md_path = base / MD_REL
    C.assert_openable(json_path)
    C.assert_openable(md_path)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    written = write_artifacts()
    print(json.dumps({k: written[k] for k in (
        "D1_STATUS",
        "D1_NULL_MODEL_OBSERVABLE_MISMATCH",
        "D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED",
        "D1_NULL_ADEQUACY_GATE_EXECUTED",
        "NEXT_UNIT",
    )}, indent=2))
