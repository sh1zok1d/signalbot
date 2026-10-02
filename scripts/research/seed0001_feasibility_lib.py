"""SEED-0001 outcome-blind feasibility statistics.

Pure functions over the frozen episode layout (arm, decision date, epoch,
weekly cluster, pre-decision covariates). No outcome is read or computed:
power comes from synthetic Bernoulli draws on the real layout under a frozen
planning profile (`docs/research/SEED0001_REGULAR_DIVERGENCE_PREREG.json`,
section FEASIBILITY_RULE).

Frozen primary procedure that the power simulation mirrors (prereg S9):
linear probability model Y ~ 1 + A + B + C (D reference) with CR1
cluster-robust variance over weekly UTC clusters and a t reference on G - 1
degrees of freedom; contrasts P1 = beta_A - beta_B and P2 = beta_A - beta_C;
Holm over {P1, P2} at family alpha 0.05; the conclusion needs both contrasts
rejected with a positive sign. The real analysis adds the frozen covariates;
the simulation leaves them out because their outcome effect is unknown.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

from scripts.research import seed0001_regular_divergence_lib as L

POWER_PROFILE_ID = "SEED0001_BINARY_POWER_PROFILE_V1"
COMPARATOR_RATE = 0.50
LATENT_ICC = {"BASE": 0.10, "STRESS": 0.25}
# BASE: one probit shock per week shared by every arm (it partly cancels in a
# contrast). STRESS: an independent shock per (week, arm), which does not cancel.
SHOCK_LEVEL = {"BASE": "WEEK", "STRESS": "WEEK_X_ARM"}
ALPHA_FAMILY = 0.05
TARGET_POWER = 0.80
POWER_REPS = 2000
POWER_SEED = 20261002
EFFECT_GRID = [round(0.025 * k, 3) for k in range(1, 17)]
MIN_MEANINGFUL_EFFECT = 0.10
PLANNING_FRACTIONS = [0.5, 0.75, 1.0]
MIN_ARM_A_EPISODES = 40
MIN_ARM_A_DISTINCT_DAYS = 30
SMD_LIMIT = 1.0
ALPHA_HET = 0.05
HET_ASSESSABLE_POWER = 0.50
PROSPECTIVE_STOP_A = 30
PROSPECTIVE_MIN_A = 20
COVARIATES = ("RV24_LOG", "TOD_SIN", "TOD_COS", "DECLINE_ATR", "NETFLOW24", "RISK_ATR")

VERDICT_BELOW_FLOOR = "INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR"
VERDICT_SUPPORT = "INCONCLUSIVE_SAMPLE / NUISANCE_SUPPORT_INSUFFICIENT"
VERDICT_WEAK = "INCONCLUSIVE_SAMPLE / INFORMATIONALLY_WEAK"
VERDICT_FEASIBLE = "FEASIBLE_FOR_OUTCOME_OPENING_REQUEST"


def covariate_matrix(episodes) -> dict[str, np.ndarray]:
    """The frozen adjustment covariates as model columns (prereg S7)."""
    hour = np.array([e["TOD_HOUR_UTC"] for e in episodes], dtype=float)
    return {
        "RV24_LOG": np.log(np.array([e["RV24"] for e in episodes], dtype=float)),
        "TOD_SIN": np.sin(2 * np.pi * hour / 24.0),
        "TOD_COS": np.cos(2 * np.pi * hour / 24.0),
        "DECLINE_ATR": np.array([e["DECLINE_ATR"] for e in episodes], dtype=float),
        "NETFLOW24": np.array([e["NETFLOW24"] for e in episodes], dtype=float),
        "RISK_ATR": np.array([e["RISK_ATR"] for e in episodes], dtype=float),
    }


def smd(a, b) -> float | None:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size < 2 or b.size < 2:
        return None
    pooled = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    return None if pooled == 0 else float((a.mean() - b.mean()) / pooled)


def covariate_support(episodes) -> dict:
    """Outcome-blind support diagnostic: per-arm summaries and A-vs-B / A-vs-C SMDs."""
    arms = np.array([e["ARM"] for e in episodes])
    cov = covariate_matrix(episodes)
    out = {"SMD": {}, "BY_ARM": {}}
    for name, x in cov.items():
        out["BY_ARM"][name] = {
            arm: ({"MEAN": float(x[arms == arm].mean()), "SD": float(x[arms == arm].std(ddof=1)),
                   "Q25": float(np.quantile(x[arms == arm], 0.25)), "Q50": float(np.quantile(x[arms == arm], 0.5)),
                   "Q75": float(np.quantile(x[arms == arm], 0.75))} if (arms == arm).sum() >= 2 else None)
            for arm in ("A", "B", "C", "D")
        }
        out["SMD"][name] = {"A_VS_B": smd(x[arms == "A"], x[arms == "B"]),
                            "A_VS_C": smd(x[arms == "A"], x[arms == "C"])}
    values = [abs(v) for row in out["SMD"].values() for v in row.values() if v is not None]
    out["MAX_ABS_SMD"] = max(values) if values else None
    out["SMD_LIMIT"] = SMD_LIMIT
    return out


# ------------------------------------------------------------------ layout stats

def layout_stats(episodes, chains) -> dict:
    arms = [e["ARM"] for e in episodes]
    by_arm = {}
    for arm in ("A", "B", "C", "D"):
        idx = [k for k, a in enumerate(arms) if a == arm]
        weeks = Counter(episodes[k]["WEEK_BLOCK"] for k in idx)
        arm_chains = Counter(int(chains[k]) for k in idx)
        by_arm[arm] = {
            "EPISODES": len(idx),
            "DISTINCT_DECISION_DATES": len({episodes[k]["DECISION_DATE_UTC"] for k in idx}),
            "BY_EPOCH": dict(sorted(Counter(episodes[k]["EPOCH"] for k in idx).items())),
            "WEEK_CLUSTERS": len(weeks),
            "MAX_EPISODES_PER_WEEK": max(weeks.values()) if weeks else 0,
            "OVERLAP_CHAINS_48H": len(arm_chains),
        }
    weeks_all = Counter(e["WEEK_BLOCK"] for e in episodes)
    chain_sizes = Counter(int(c) for c in chains)
    straddle = sum(1 for e in episodes
                   if L.week_block(e["DECISION_TIME_MS"] + L.PRIMARY_CAP_HOURS * L.BAR_MS - 1) != e["WEEK_BLOCK"])
    a_idx = [k for k, a in enumerate(arms) if a == "A"]
    shared = sum(1 for k in a_idx if chain_sizes[int(chains[k])] > 1)
    return {
        "BY_ARM": by_arm,
        "TOTAL_ELIGIBLE": len(episodes),
        "WEEK_CLUSTERS": {"COUNT": len(weeks_all),
                          "MEAN_EPISODES": (len(episodes) / len(weeks_all)) if weeks_all else None,
                          "MAX_EPISODES": max(weeks_all.values()) if weeks_all else 0},
        "OVERLAP_CHAINS_48H": {"COUNT": len(chain_sizes),
                               "MEAN_SIZE": (len(episodes) / len(chain_sizes)) if chain_sizes else None,
                               "MAX_SIZE": max(chain_sizes.values()) if chain_sizes else 0,
                               "SINGLETON_SHARE": (sum(1 for v in chain_sizes.values() if v == 1) / len(chain_sizes))
                               if chain_sizes else None},
        "A_EPISODES_SHARING_A_48H_CHAIN": shared,
        "EPISODES_WHOSE_48H_WINDOW_CROSSES_A_WEEK_BOUNDARY": straddle,
    }


# ------------------------------------------------------------------- power

def _design(arms) -> np.ndarray:
    arms = np.asarray(arms)
    return np.column_stack([np.ones(arms.size), arms == "A", arms == "B", arms == "C"]).astype(float)


def _cluster_index(clusters) -> tuple[np.ndarray, int]:
    _, inv = np.unique(np.asarray(clusters), return_inverse=True)
    return inv, int(inv.max()) + 1


def _holm_conjunction(t1, t2, df, one_sided: bool) -> np.ndarray:
    if one_sided:
        p1, p2 = stats.t.sf(t1, df), stats.t.sf(t2, df)
    else:
        p1, p2 = 2 * stats.t.sf(np.abs(t1), df), 2 * stats.t.sf(np.abs(t2), df)
    lo, hi = np.minimum(p1, p2), np.maximum(p1, p2)
    both = (lo <= ALPHA_FAMILY / 2) & (hi <= ALPHA_FAMILY)
    return both & (t1 > 0) & (t2 > 0)


def conjunction_power(arms, clusters, delta: float, latent_icc: float, *, shock: str = "WEEK",
                      reps: int = POWER_REPS, seed: int = POWER_SEED, one_sided: bool = False) -> dict:
    """Power that Holm rejects both P1 and P2 with positive signs.

    Synthetic outcomes only: Y ~ Bernoulli(p_arm) with a probit-scale shock
    whose latent ICC is `latent_icc`, drawn per week (`WEEK`) or per
    (week, arm) (`WEEK_X_ARM`). The marginal rate is exactly COMPARATOR_RATE
    for B, C, D and COMPARATOR_RATE + delta for A. Analysis clusters are weeks.
    """
    arms = np.asarray(arms)
    counts = Counter(arms.tolist())
    if any(counts.get(a, 0) < 2 for a in ("A", "B", "C", "D")):
        return {"POWER": 0.0, "REASON": "AN_ARM_HAS_FEWER_THAN_2_EPISODES"}
    X = _design(arms)
    g, n_g = _cluster_index(clusters)
    if shock == "WEEK":
        shock_g, n_shock = g, n_g
    elif shock == "WEEK_X_ARM":
        shock_g, n_shock = _cluster_index([f"{c}|{a}" for c, a in zip(np.asarray(clusters).tolist(), arms.tolist())])
    else:
        raise ValueError(f"unknown shock level {shock}")
    if n_g < 3:
        return {"POWER": 0.0, "REASON": "FEWER_THAN_3_CLUSTERS"}
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    proj = xtx_inv @ X.T
    w1 = xtx_inv @ np.array([0.0, 1.0, -1.0, 0.0])
    w2 = xtx_inv @ np.array([0.0, 1.0, 0.0, -1.0])
    scale = n_g / (n_g - 1) * (n - 1) / (n - k)
    tau = math.sqrt(latent_icc / (1.0 - latent_icc))
    p_arm = np.where(arms == "A", COMPARATOR_RATE + delta, COMPARATOR_RATE)
    loc = stats.norm.ppf(p_arm) * math.sqrt(1.0 + tau * tau)
    rng = np.random.default_rng(seed)
    hits = np.zeros(0, dtype=bool)
    batch = 250
    done = 0
    while done < reps:
        m = min(batch, reps - done)
        z = rng.standard_normal((n_shock, m))[shock_g]
        y = (rng.standard_normal((n, m)) < loc[:, None] + tau * z).astype(float)
        beta = proj @ y
        resid = y - X @ beta
        s = np.zeros((n_g, k, m))
        for col in range(k):
            np.add.at(s[:, col, :], g, X[:, col:col + 1] * resid)
        v1 = scale * np.einsum("gkm,k->gm", s, w1) ** 2
        v2 = scale * np.einsum("gkm,k->gm", s, w2) ** 2
        se1, se2 = np.sqrt(v1.sum(axis=0)), np.sqrt(v2.sum(axis=0))
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = np.where(se1 > 0, (beta[1] - beta[2]) / se1, 0.0)
            t2 = np.where(se2 > 0, (beta[1] - beta[3]) / se2, 0.0)
        hits = np.r_[hits, _holm_conjunction(t1, t2, n_g - 1, one_sided)]
        done += m
    power = float(hits.mean())
    return {"POWER": power, "MC_SE": math.sqrt(power * (1 - power) / reps), "REPS": reps, "CLUSTERS": n_g}


def power_table(arms, clusters, *, one_sided: bool = False, reps: int = POWER_REPS) -> dict:
    out = {}
    for p_index, (profile, icc) in enumerate(sorted(LATENT_ICC.items())):
        grid = {}
        for d_index, delta in enumerate(EFFECT_GRID):
            res = conjunction_power(arms, clusters, delta, icc, shock=SHOCK_LEVEL[profile], reps=reps,
                                    seed=POWER_SEED + 1000 * p_index + d_index, one_sided=one_sided)
            grid[f"{delta:.3f}"] = res["POWER"]
        mde = next((d for d in EFFECT_GRID if grid[f"{d:.3f}"] >= TARGET_POWER), None)
        out[profile] = {
            "LATENT_ICC": icc,
            "SHOCK_LEVEL": SHOCK_LEVEL[profile],
            "POWER_BY_EFFECT": grid,
            "MDE_AT_TARGET_POWER": mde,
            "POWER_AT_PLANNING_FRACTIONS": {f"{f:.2f}": grid[f"{f * MIN_MEANINGFUL_EFFECT:.3f}"]
                                            for f in PLANNING_FRACTIONS},
        }
    return out


# ---------------------------------------------------- heterogeneity (V1 §4)

def heterogeneity_assessability(episodes) -> dict:
    """V1 §4 low-power rule: power to detect a 2x epoch difference of the planning effect.

    Analytic, without a design effect (optimistic): the two epochs with the
    fewest A episodes, difference MIN_MEANINGFUL_EFFECT, alpha_het 0.05.
    """
    counts = defaultdict(Counter)
    for e in episodes:
        counts[e["EPOCH"]][e["ARM"]] += 1
    epochs = sorted(counts, key=lambda ep: (counts[ep]["A"], ep))
    if len([ep for ep in epochs if counts[ep]["A"] > 0]) < 3:
        return {"STATUS": "NOT_ASSESSABLE", "REASON": "FEWER_THAN_3_EPOCHS_WITH_A", "NOT_EVIDENCE_OF_STABILITY": True}
    e1, e2 = epochs[0], epochs[1]
    z = stats.norm.ppf(1 - ALPHA_HET / 2)
    powers = {}
    for comp in ("B", "C"):
        var = 0.0
        ok = True
        for ep in (e1, e2):
            na, nc = counts[ep]["A"], counts[ep][comp]
            if na == 0 or nc == 0:
                ok = False
                break
            var += 0.25 / na + 0.25 / nc
        powers[f"A_VS_{comp}"] = float(stats.norm.cdf(MIN_MEANINGFUL_EFFECT / math.sqrt(var) - z)) if ok else 0.0
    status = "ASSESSABLE" if min(powers.values()) >= HET_ASSESSABLE_POWER else "NOT_ASSESSABLE"
    return {"STATUS": status, "SMALLEST_EPOCHS": [e1, e2], "POWER": powers,
            "THRESHOLD": HET_ASSESSABLE_POWER, "NOT_EVIDENCE_OF_STABILITY": True}


# ----------------------------------------------------- prospective planning

def prospective_layout(episodes, stop_a: int) -> tuple[list[str], list[int]] | None:
    """Chronological prefix of the retrospective layout until `stop_a` A episodes.

    A structural stand-in for a prospective window with the same episode
    density; only arms and weekly clusters are used.
    """
    ordered = sorted(episodes, key=lambda e: e["DECISION_TIME_MS"])
    arms, clusters, a = [], [], 0
    for e in ordered:
        arms.append(e["ARM"])
        clusters.append(e["WEEK_BLOCK"])
        a += e["ARM"] == "A"
        if a == stop_a:
            return arms, clusters
    return None


# --------------------------------------------------------------- verdict

def verdict(n_a: int, dates_a: int, max_abs_smd: float | None, stress_power_at_mme: float) -> str:
    """Frozen retrospective feasibility rule (prereg FEASIBILITY_RULE), first match wins."""
    if n_a < MIN_ARM_A_EPISODES or dates_a < MIN_ARM_A_DISTINCT_DAYS:
        return VERDICT_BELOW_FLOOR
    if max_abs_smd is None or max_abs_smd > SMD_LIMIT:
        return VERDICT_SUPPORT
    if stress_power_at_mme < TARGET_POWER:
        return VERDICT_WEAK
    return VERDICT_FEASIBLE
