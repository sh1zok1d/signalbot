"""Outcome-blind design and power for GV0R01-C004. No price values."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.discovery_sprint_03.common import sample_matched_ids_per_cell

REPO = Path(__file__).resolve().parents[2]
FOMC_PIN = REPO / "docs/research_data/D11_FOMC_OFFICIAL_V0/PIN.json"
CPI_EVENTS = REPO / "docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/EVENTS.json"
CPI_MANIFEST = REPO / "docs/research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/MANIFEST.json"
OUT_JSON = REPO / "docs/research/GV0R01_C004_OUTCOME_BLIND_DESIGN.json"

MATCH_SEED = 10004
PERMUTATION_SEED = 10004
PERMUTATION_DRAWS = 2000
POWER_REPS = 300
POWER_SEED = 10004004
ALPHA = 0.05
POST_MINUTES = 60
BETA_DAYS = 90
TARGET_POWER = 0.80
# Frozen before any simulated MDE. Not the C012 0.50 single-window-SD bar.
EXECUTION_MDE_THRESHOLD = 0.10
EXECUTION_MDE_UNITS = "RESID_SHARE_POINTS"

CLAIM = (
    "A scheduled FOMC statement is a common-factor shock, so the idiosyncratic "
    "share of ETHUSDT perpetual variance relative to BTCUSDT, after a beta frozen "
    "before the statement, is lower in the 60 minutes after the statement than in "
    "the same year, weekday and UTC hour on weeks with no FOMC or CPI release."
)


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _overlap(a0: dt.datetime, a1: dt.datetime, b0: dt.datetime, b1: dt.datetime) -> bool:
    return a0 < b1 and b0 < a1


def _minutes(a0: dt.datetime, a1: dt.datetime, b0: dt.datetime, b1: dt.datetime) -> int:
    left, right = max(a0, b0), min(a1, b1)
    if right <= left:
        return 0
    return int((right - left).total_seconds() // 60)


def load_events() -> tuple[list[dict], set[str]]:
    pin = json.loads(FOMC_PIN.read_text())
    if pin["DATASET_ID"] != "D11_FOMC_OFFICIAL_V0":
        raise RuntimeError("FOMC_DATASET")
    events = []
    for e in pin["EVENTS"]:
        if e["EVENT_FAMILY"] != "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS":
            raise RuntimeError("FOMC_FAMILY")
        t = _parse(e["ANNOUNCEMENT_UTC"])
        events.append({
            "EVENT_ID": e["EVENT_ID"],
            "T": t,
            "YEAR": e["YEAR"],
            "WEEKDAY": e["WEEKDAY"],
            "UTC_HOUR": e["UTC_HOUR"],
            "CELL": f"{e['YEAR']}:{e['WEEKDAY']}:{e['UTC_HOUR']}",
        })
    cpi = json.loads(CPI_EVENTS.read_text())
    if cpi["DATASET_ID"] != "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0":
        raise RuntimeError("CPI_DATASET")
    days = {e["SCHEDULED_RELEASE_DATE"] for e in cpi["EVENTS"]}
    days.update(e["T"].date().isoformat() for e in events)
    return events, days


def _windows(t: dt.datetime) -> dict:
    return {
        "OUT0": t,
        "OUT1": t + dt.timedelta(minutes=POST_MINUTES),
        "BETA0": t - dt.timedelta(days=BETA_DAYS),
        "BETA1": t - dt.timedelta(hours=1),
    }


def covered(t: dt.datetime) -> bool:
    w = _windows(t)
    start = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    return w["BETA0"] >= start and w["OUT1"] < end


def assign(events: list[dict], blocked_days: set[str]) -> list[dict]:
    usable = [e for e in events if covered(e["T"])]
    by_cell: dict[str, list[int]] = {}
    for e in usable:
        by_cell.setdefault(e["CELL"], []).append(int(e["T"].timestamp()))
    candidates: dict[str, list[int]] = {}
    for cell, group in by_cell.items():
        year, weekday, hour = (int(x) for x in cell.split(":"))
        # Clock minute is part of the FOMC timestamp, not a searched parameter.
        minutes = {dt.datetime.fromtimestamp(x, dt.timezone.utc).minute for x in group}
        seconds = {dt.datetime.fromtimestamp(x, dt.timezone.utc).second for x in group}
        if len(minutes) != 1 or len(seconds) != 1:
            raise RuntimeError(f"CELL_CLOCK:{cell}")
        minute, second = minutes.pop(), seconds.pop()
        ids = []
        day = dt.date(year, 1, 1)
        while day.year == year:
            if day.weekday() == weekday and day.isoformat() not in blocked_days:
                t = dt.datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=dt.timezone.utc)
                if covered(t):
                    ids.append(int(t.timestamp()))
            day += dt.timedelta(days=1)
        candidates[cell] = sorted(set(ids))
    matched, balanced = sample_matched_ids_per_cell(by_cell, candidates, seed=MATCH_SEED)
    if not balanced:
        raise RuntimeError("UNBALANCED")
    pairs = []
    for cell in sorted(by_cell):
        ev = sorted((e for e in usable if e["CELL"] == cell), key=lambda e: e["EVENT_ID"])
        chosen = matched[cell]
        if len(ev) != len(chosen):
            raise RuntimeError("PAIR")
        for e, cid in zip(ev, chosen):
            ct = dt.datetime.fromtimestamp(cid, dt.timezone.utc)
            pairs.append({"EVENT": e, "CONTROL_T": ct, "CELL": cell})
    return pairs


def observations(pairs: list[dict]) -> list[dict]:
    rows = []
    for p in pairs:
        for role, t in (("EVENT", p["EVENT"]["T"]), ("CONTROL", p["CONTROL_T"])):
            w = _windows(t)
            rows.append({
                "ID": f"{role[0]}:{p['EVENT']['EVENT_ID']}",
                "ROLE": role,
                "CELL": p["CELL"],
                "T": t,
                **w,
            })
    return rows


def graph_from(rows: list[dict], kind: str) -> dict[str, list[str]]:
    nb = {r["ID"]: [] for r in rows}
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if kind == "OUTCOME":
                hit = _overlap(a["OUT0"], a["OUT1"], b["OUT0"], b["OUT1"])
            else:
                hit = _overlap(a["BETA0"], a["BETA1"], b["BETA0"], b["BETA1"])
            if hit:
                nb[a["ID"]].append(b["ID"])
                nb[b["ID"]].append(a["ID"])
    for k in nb:
        nb[k] = sorted(nb[k])
    return nb


def union_graph(a: dict[str, list[str]], b: dict[str, list[str]]) -> dict[str, list[str]]:
    out = {}
    for k in a:
        out[k] = sorted(set(a[k]) | set(b[k]))
    return out


def components(nb: dict[str, list[str]]) -> list[list[str]]:
    seen = set()
    comps = []
    for node in sorted(nb):
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        comp = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in nb[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        comps.append(sorted(comp))
    return comps


def edge_count(nb: dict[str, list[str]]) -> int:
    return sum(len(v) for v in nb.values()) // 2


def differing_swaps(rows: list[dict], nb: dict[str, list[str]]) -> int:
    by = {}
    for r in rows:
        by.setdefault(r["CELL"], []).append(r["ID"])
    cell = {r["ID"]: r["CELL"] for r in rows}
    n = 0
    for ids in by.values():
        hood = {}
        for i in ids:
            hood[i] = tuple(sorted(x for x in nb[i] if cell[x] != cell[i]))
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if hood[a] != hood[b]:
                    n += 1
    return n


def admissible_transposition(nb: dict[str, list[str]], cell: dict[str, str], a: str, b: str) -> bool:
    if cell[a] != cell[b]:
        return False
    na = set(nb[a]) - {b}
    nb_ = set(nb[b]) - {a}
    return na == nb_


def class_indices(rows: list[dict], nb: dict[str, list[str]]) -> list[np.ndarray]:
    """Nodes that may be exchanged: same stratum and identical external neighbors.

    A transposition of any two is an automorphism. The class may be larger than
    a single pair; permuting inside the class preserves adjacency because every
    member has the same neighbors outside the class and no edges inside it
    unless those edges are universal. We split off any intra-class edge.
    """
    cell = {r["ID"]: r["CELL"] for r in rows}
    index = {r["ID"]: i for i, r in enumerate(rows)}
    by = {}
    for r in rows:
        ext = tuple(sorted(x for x in nb[r["ID"]] if cell[x] != r["CELL"]))
        by.setdefault((r["CELL"], ext), []).append(r["ID"])
    classes = []
    for ids in by.values():
        # Drop pairs that are adjacent inside the class; those cannot be freely swapped
        # unless the class is a clique, which we do not assume. Keep only an
        # independent set of mutually non-adjacent nodes with equal hoods.
        free = []
        blocked = set()
        for i in ids:
            if any(j in nb[i] for j in ids if j != i):
                blocked.add(i)
            else:
                free.append(i)
        if len(free) > 1:
            classes.append(np.array([index[i] for i in free], dtype=np.int64))
        # Adjacent same-hood pairs are fixed unless the transposition test passes
        # for a matching. Handle mutual pairs separately below.
        adj = [i for i in ids if i in blocked]
        used = set()
        for i in adj:
            if i in used:
                continue
            mates = [j for j in adj if j not in used and j != i and j in nb[i] and admissible_transposition(nb, cell, i, j)]
            if len(mates) == 1 and admissible_transposition(nb, cell, i, mates[0]):
                # Single flippable edge: swapping endpoints preserves the edge.
                classes.append(np.array([index[i], index[mates[0]]], dtype=np.int64))
                used.add(i)
                used.add(mates[0])
    return classes


def sample_labels(n: int, base: np.ndarray, classes: list[np.ndarray], rng: np.random.Generator, draws: int) -> np.ndarray:
    labels = np.tile(base, (draws, 1))
    for idx in classes:
        k = idx.size
        n_e = int(base[idx].sum())
        if n_e == 0 or n_e == k:
            continue
        noise = rng.random((draws, k))
        chosen = np.argpartition(noise, n_e - 1, axis=1)[:, :n_e]
        block = np.zeros((draws, k), dtype=np.int8)
        block[np.arange(draws)[:, None], chosen] = 1
        labels[:, idx] = block
    return labels


def monte_carlo_p_less(observed: np.ndarray, null_stats: np.ndarray) -> np.ndarray:
    exceed = np.sum(null_stats <= observed[None, :], axis=0)
    return (1.0 + exceed) / (1.0 + null_stats.shape[0])


def _share_batch(rng: np.random.Generator, n: int, idio_sd: float) -> np.ndarray:
    btc = rng.normal(0.0, 1.0, size=(n, 12))
    eth = btc + rng.normal(0.0, idio_sd, size=(n, 12))
    # beta frozen at 1, the planning common-factor loading. Not estimated from BTC.
    resid = eth - btc
    den = np.sum(eth * eth, axis=1)
    den = np.where(den == 0.0, 1.0, den)
    share = np.sum(resid * resid, axis=1) / den
    share = np.where(np.sum(eth * eth, axis=1) == 0.0, 1.0, share)
    return share


def power_curve(rows: list[dict], classes: list[np.ndarray], beta_minutes: dict[tuple[str, str], int]) -> dict:
    n = len(rows)
    base = np.array([1 if r["ROLE"] == "EVENT" else 0 for r in rows], dtype=np.float64)
    order = [r["ID"] for r in rows]
    index = {i: k for k, i in enumerate(order)}
    length = BETA_DAYS * 24 * 60
    corr = np.eye(n)
    for (a, b), mins in beta_minutes.items():
        i, j = index[a], index[b]
        corr[i, j] = corr[j, i] = min(1.0, mins / length)
    scenarios = {
        "A_INDEPENDENT_WINDOWS": None,
        "B_BETA_WINDOW_CORRELATION": corr,
        "C_IDIO_SD_SQRT2": None,
    }
    deltas = (0.0, -0.02, -0.05, -0.08, -0.10, -0.15, -0.20)
    out = {}
    for name in scenarios:
        rows_out = []
        idio = math.sqrt(2.0) if name.startswith("C_") else 1.0
        for delta in deltas:
            rng = np.random.default_rng(POWER_SEED + int(abs(delta) * 1000) + (0 if name.startswith("A") else 17 if name.startswith("B") else 29))
            if name.startswith("B"):
                # Gaussian copula through the 12-bar marginal is unnecessary for the
                # mean-difference scale: shift a correlated gaussian with the
                # marginal SD of the 12-bar share, then the endpoint unit stays
                # a RESID_SHARE point.
                pilot = _share_batch(np.random.default_rng(7), 4000, 1.0)
                sd = float(pilot.std(ddof=1))
                mean = float(pilot.mean())
                z = rng.multivariate_normal(np.zeros(n), corr, size=POWER_REPS)
                shares = mean + sd * z
            else:
                shares = np.vstack([_share_batch(rng, n, idio) for _ in range(POWER_REPS)])
            values = shares + delta * base[None, :]
            observed = values[:, base == 1].mean(axis=1) - values[:, base == 0].mean(axis=1)
            lab_rng = np.random.default_rng(int(rng.integers(1, 2**31 - 1)))
            labels = sample_labels(n, base, classes, lab_rng, PERMUTATION_DRAWS)
            ev = labels @ values.T
            n_e = float(base.sum())
            stat = ev / n_e - (values.sum(axis=1)[None, :] - ev) / (n - n_e)
            # n_event is fixed by the class design. Guard it.
            if np.any(labels.sum(axis=1) != int(base.sum())):
                raise RuntimeError("LABELS")
            p = monte_carlo_p_less(observed, stat)
            if np.any(p <= 0):
                raise RuntimeError("P_ZERO")
            reject = p <= ALPHA
            phat = float(reject.mean())
            se = math.sqrt(phat * (1 - phat) / POWER_REPS)
            rows_out.append({
                "DELTA_RESID_SHARE": delta,
                "POWER": phat,
                "MC_SE": se,
                "POWER_CI95": [max(0.0, phat - 1.96 * se), min(1.0, phat + 1.96 * se)],
            })
        out[name] = rows_out
    return out


def _mde(curve: list[dict]) -> float | None:
    # Power should rise as delta becomes more negative. Interpolate to 0.80.
    ordered = sorted(curve, key=lambda r: r["DELTA_RESID_SHARE"], reverse=True)
    below = None
    for row in ordered:
        if row["POWER"] >= TARGET_POWER:
            if below is None:
                return row["DELTA_RESID_SHARE"]
            span = row["POWER"] - below["POWER"]
            if span <= 0:
                return row["DELTA_RESID_SHARE"]
            w = (TARGET_POWER - below["POWER"]) / span
            return below["DELTA_RESID_SHARE"] + w * (row["DELTA_RESID_SHARE"] - below["DELTA_RESID_SHARE"])
        below = row
    return None


def build(run_power: bool = True) -> dict:
    events, blocked = load_events()
    if len(events) != 39:
        raise RuntimeError("FOMC_N")
    pairs = assign(events, blocked)
    rows = observations(pairs)
    out_nb = graph_from(rows, "OUTCOME")
    beta_nb = graph_from(rows, "BETA")
    dep = union_graph(out_nb, beta_nb)
    comps = components(dep)
    sizes = [len(c) for c in comps]
    beta_mins = {}
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            m = _minutes(a["BETA0"], a["BETA1"], b["BETA0"], b["BETA1"])
            if m:
                beta_mins[(a["ID"], b["ID"])] = m
    classes = class_indices(rows, dep)
    base = np.array([1 if r["ROLE"] == "EVENT" else 0 for r in rows], dtype=np.float64)
    # Orbit size: product of multinomials. Exact integer.
    orbit = 1
    mobile = 0
    for idx in classes:
        labels = base[idx]
        n_e = int(labels.sum())
        n_c = int(idx.size - n_e)
        piece = math.comb(idx.size, n_e)
        orbit *= piece
        if piece > 1:
            mobile += idx.size
    curves = power_curve(rows, classes, beta_mins) if run_power else None
    mdes = {k: _mde(v) for k, v in curves.items()} if curves else {}
    stress = mdes.get("C_IDIO_SD_SQRT2")
    if stress is None:
        gate = "EXECUTION_INFORMATIONALLY_WEAK"
    elif abs(stress) <= EXECUTION_MDE_THRESHOLD + 1e-12:
        gate = "EXECUTION_JUSTIFIED"
    else:
        gate = "EXECUTION_INFORMATIONALLY_WEAK"
    manifest = json.loads(CPI_MANIFEST.read_text())
    digest = manifest["CANONICAL_DATASET_DIGEST"]
    if digest != "760ed2c5d18b03b7a41c25e6bab157ebde476977fdc3e5f7a3462aa376f4154f":
        raise RuntimeError("CPI_DIGEST")
    doc = {
        "UNIT": "GV0R01_C004_OUTCOME_BLIND_DESIGN_AND_POWER",
        "C004_DEFINITION_STATUS": "UNAMBIGUOUS",
        "DEFINITION_AUTHORITY": "GV0R01-C004 card in the Stream-B triage and the GV0R01 attempt record. GV0CAL-C004 is a different candidate.",
        "C004_CANONICAL_CLAIM": CLAIM,
        "EVENT_FAMILIES": ["SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS"],
        "EVENT_COUNT_PLANNED": 39,
        "EVENT_COUNT_COVERED": len(pairs),
        "UNCOVERED_EVENT_IDS": [e["EVENT_ID"] for e in events if not covered(e["T"])],
        "EVENT_IDS": [p["EVENT"]["EVENT_ID"] for p in pairs],
        "INCLUSION_RULE": "Scheduled FOMC statements in D11_FOMC_OFFICIAL_V0 whose 90-day beta window and 60-minute post window lie inside [2020-01-01, 2025-01-01).",
        "EXCLUSION_RULE": "CPI releases are not primary events. FOMC_PLUS_CPI is not the primary universe. The one FOMC statement whose beta window starts before 2020-01-01 is uncovered.",
        "EVENT_UNIVERSE_RATIONALE": "The card primary target, function and name are FOMC windows. The CPI arm is described as an extension that triples N. Pooling it would be an N choice, not the mechanism.",
        "CPI_POOLED_IN_PRIMARY": False,
        "NON_DECISIVE_CARD_VARIANTS": ["FOMC_PLUS_CPI", "post_window_minutes=120", "beta_lookback_days=30"],
        "CALENDAR_AUTHORITIES": {
            "FOMC": "D11_FOMC_OFFICIAL_V0",
            "CPI_CONTROL_EXCLUSION_ONLY": "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0",
            "CPI_DIGEST": digest,
        },
        "POINT_IN_TIME_EVENT_STATUS": "FOMC release times are the pinned official schedule. No realized FOMC or CPI value enters. Beta uses only (T-90d, T-1h].",
        "MARKET_INSTRUMENT": "ETHUSDT and BTCUSDT USD-M perpetuals",
        "SOURCE_DATASETS": ["CORE_ETH_BINANCE_V0", "CORE_BTC_BINANCE_V0"],
        "PRIMARY_WINDOW": "(T, T+60m] after the scheduled statement. Twelve 5m bars whose close times fall in that interval. The bar that closes at T is excluded.",
        "PRIMARY_RETURN_DEFINITION": "5m log return from 1m closes. e_t = r_ETH,t - beta_pre * r_BTC,t. beta_pre is the OLS slope with intercept of r_ETH on r_BTC over 5m bars whose close times lie in (T-90d, T-1h]. RESID_SHARE = sum(e^2)/sum(r_ETH^2), or 1 if the denominator is 0.",
        "COUNTERFACTUAL_DESIGN": "1:1 match inside YEAR x WEEKDAY x UTC_HOUR. Control clock equals the event timestamp's minute. The control day is not an FOMC or CPI release date. Seed 10004 via sample_matched_ids_per_cell.",
        "CONTROL_COUNT": len(pairs),
        "CONTROL_REUSE_POLICY": "Without replacement. A pair with a missing bar is dropped and not redrawn.",
        "OVERLAP_GRAPH_NODES": len(rows),
        "OUTCOME_EDGES": edge_count(out_nb),
        "BETA_EDGES": edge_count(beta_nb),
        "OVERLAP_GRAPH_EDGES": edge_count(dep),
        "OVERLAP_GRAPH_COMPONENTS": len(comps),
        "MAX_OVERLAP_COMPONENT_SIZE": max(sizes) if sizes else 0,
        "WITHIN_STRATUM_SWAPS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS": differing_swaps(rows, dep),
        "INFERENCE_METHOD": "ONE_SIDED_LABEL_PERMUTATION_ON_THE_STRATUM_AND_DEPENDENCE_AUTOMORPHISM_SUBGROUP",
        "GLOBAL_INFERENCE_VALIDITY_STATUS": "PASS_FOR_THE_GENERATED_SUBGROUP",
        "RESIDUAL_INFERENCE_ASSUMPTIONS": "RESID_SHARE values are exchangeable under the null among windows that the dependence graph treats as equivalent. Graph preservation does not prove that ETH and BTC returns are unconditionally exchangeable. The subgroup is the set of within-stratum swaps the graph allows; it is not the full within-stratum symmetric group.",
        "PRIMARY_ENDPOINT": "DELTA_SHARE = mean(RESID_SHARE event) - mean(RESID_SHARE matched control)",
        "NULL_HYPOTHESIS": "The mean post-statement RESID_SHARE equals the mean matched-control RESID_SHARE.",
        "ALTERNATIVE_HYPOTHESIS": "The event mean is lower. The mechanism states a collapse, so the primary test is one-sided. A positive difference is a beta-shift falsification, not support.",
        "ALPHA": ALPHA,
        "TEST_SIDEDNESS": "ONE_SIDED_LESS",
        "TIE_RULE": "T_perm <= T_obs counts as extreme. p = (1 + count) / (1 + draws).",
        "PERMUTATION_DRAWS": PERMUTATION_DRAWS,
        "PERMUTATION_SEED": PERMUTATION_SEED,
        "PRIMARY_LABEL_ORBIT_SIZE": str(orbit),
        "MIN_ATTAINABLE_EXACT_P": {"NUMERATOR": 1, "DENOMINATOR": str(orbit)},
        "ALPHA_ATTAINABLE": orbit > int(1 / ALPHA),
        "OBSERVATIONS_THAT_CAN_CHANGE_LABEL": mobile,
        "FALSIFIERS": [
            {
                "ID": "F1",
                "RULE": "One-sided permutation p > 0.05.",
                "VETO": True,
                "POWER": "Included in POWER_PRIMARY_TEST.",
            },
            {
                "ID": "F2",
                "RULE": "Event RESID_SHARE is lower than that same event's (T-60m, T] share in fewer than half of covered events.",
                "VETO": True,
                "POWER": "Not separately calibrated. POWER_FULL_DECISION_RULE is not claimed.",
            },
            {
                "ID": "F3",
                "RULE": "The same contrast on (T-60m, T] versus controls shifted back 60m is significant in the same direction.",
                "VETO": True,
                "POWER": "Not separately calibrated.",
            },
        ],
        "MISSING_DATA_POLICY": "Any missing 5m close in the outcome window or the beta window drops the pair. No imputation. No redraw. If the dropped covered-event rate exceeds 0.05, the result is INCONCLUSIVE.",
        "OUTLIER_POLICY": "No winsorization and no outcome-based deletion. A zero ETH-variance window is assigned RESID_SHARE 1, as the card states.",
        "BAD_BAR_POLICY": "A non-finite or non-positive close is missing.",
        "DUPLICATE_TIMESTAMP_POLICY": "A duplicate 1m open time with disagreeing closes is a hard failure.",
        "MULTIPLE_TESTING_POLICY": "One primary endpoint and one alpha. The other seven card variants are non-decisive and are not estimated in this unit.",
        "TARGET_POWER": TARGET_POWER,
        "EXECUTION_MDE_THRESHOLD": EXECUTION_MDE_THRESHOLD,
        "EXECUTION_MDE_UNITS": EXECUTION_MDE_UNITS,
        "GATE_AUTHORITY": "C004 card language that the idiosyncratic share collapses. No repository-wide 0.50-SD bar governs every candidate. The C012 threshold is not reused.",
        "GATE_RATIONALE": "A mean decline of 0.10 residual-share points is the smallest shift still described as a collapse rather than a negligible reallocation. Frozen before the power simulation.",
        "STANDARDIZED_UNIT": "One RESID_SHARE point is an absolute difference in the variance ratio. MDE_PRIMARY_UNITS is that difference. There is no second SD-unit gate.",
        "POWER_SIMULATION_ASSUMPTIONS": "Synthetic 5m Gaussian BTC and ETH with unit factor loading. Idiosyncratic SD is 1 in A and B and sqrt(2) in C. No CORE_BTC or CORE_ETH value is read. B correlates window shares by beta-window overlap fraction.",
        "D10_D11_NOTE": "D11 measured post-event BTC realized variance on this FOMC set. D10 used a frozen-beta ETH residual in a different design and was NO_USEFUL_STRUCTURE. C004's endpoint is the post-statement residual share, not those results. Their outcomes are not inputs.",
        "MARKET_DATA_OPENED_FOR_C004": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "C004_PRIMARY_TEST_EXECUTED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING": 0,
        "MATCH_SEED": MATCH_SEED,
    }
    if curves is not None:
        doc["POWER_CURVES"] = curves
        doc["MDE_PRIMARY_UNITS"] = stress
        doc["MDE_BY_SCENARIO_RESID_SHARE"] = mdes
        doc["MDE_PLANNING_PERCENT_ILLUSTRATION"] = "NOT_APPLICABLE. The endpoint is a variance share, not a percent return."
        doc["OUTCOME_BLIND_GATE"] = "TARGET_POWER_0.80_BY_0.10_RESID_SHARE_UNDER_IDIO_SD_SQRT2"
        doc["OUTCOME_BLIND_GATE_RESULT"] = gate
        doc["NEXT_UNIT"] = (
            "GV0R01_C004_ONE_SHOT_EXECUTION_PREP"
            if gate == "EXECUTION_JUSTIFIED"
            else "NO_C004_EXECUTION_AUTHORIZED"
        )
    return doc
