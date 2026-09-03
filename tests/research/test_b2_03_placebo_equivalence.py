"""Exact-equivalence tests for the B2-03 placebo hot path.

Synthetic fixtures only. These tests must not open CORE parquet, create a
production evidence reservation, or invoke run_development.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

from scripts.research import b2_03_impulse_morphology_lib as lib


FUZZ_SEED = 20260911
FUZZ_CASES = 400
PERM_SEEDS_PER_CELL = 80
PERM_NS = (1, 2, 3, 4, 5, 10, 40, 80, 81, 120, 500, 2160)
PERM_KINDS = (
    "all_same",
    "LOW_HIGH",
    "LOW_MID_HIGH",
    "imbalanced",
    "ties_boundary",
)


def _labels_from_states(states: np.ndarray) -> np.ndarray:
    return np.asarray([lib.STATE_LABELS[int(code)] for code in states])


def _make_label_list(kind: str, n: int) -> list[str]:
    if kind == "all_same":
        return ["MID"] * n
    if kind == "LOW_HIGH":
        return ["LOW" if i % 2 == 0 else "HIGH" for i in range(n)]
    if kind == "LOW_MID_HIGH":
        return [lib.STATE_LABELS[i % 3] for i in range(n)]
    if kind == "imbalanced":
        if n < 3:
            return ["LOW"] * n
        return ["LOW"] * (n - 3) + ["MID", "HIGH", "HIGH"]
    if kind == "ties_boundary":
        n_high = n // 5
        n_low = n // 2
        n_mid = n - n_low - n_high
        return ["LOW"] * n_low + ["MID"] * n_mid + ["HIGH"] * n_high
    raise ValueError(kind)


def _stamp_targets(events, frame, H, scale_cache=None):
    del frame, scale_cache
    out = []
    for event in events:
        record = dict(event)
        record["H"] = int(H)
        out.append(record)
    return out


def _ready_event(
    t: int,
    *,
    W: int = 15,
    direction: str = "UP",
    morph: int = lib.STATE_HIGH,
    mag: int = lib.STATE_MID,
    vol: int = lib.STATE_MID,
    y: float = 0.01,
) -> dict[str, object]:
    d = 1 if direction == "UP" else -1
    return {
        "T": int(t),
        "W": int(W),
        "d": int(d),
        "direction": direction,
        "D_W": 0.01 * d,
        "abs_disp": 0.01,
        "pre_vol": 0.1,
        "mag_state": int(mag),
        "vol_state": int(vol),
        "morphology_state": int(morph),
        "warmup_only": False,
        "Y": float(y),
        "target_available": True,
    }


def test_placebo_seed_matches_frozen_part_order():
    stratum = lib.baseline_stratum_id(
        W=30, direction="DOWN", displacement_mag_state="HIGH", vol_state="LOW"
    )
    t = lib.DEV_START_MS + 12 * lib.HOUR_MS
    seed = lib._placebo_seed(7, 30, 120, t, stratum)
    assert seed == lib.seed_int((20260904, 7, 30, 120, t, stratum))
    assert seed == lib.seed_int((lib.SEED_PLACEBO, 7, 30, 120, t, stratum))
    assert lib.SEED_PLACEBO == 20260904
    assert lib.N_PLACEBO == 100


def test_placebo_seed_changes_with_t_w_h_stratum_and_rep():
    stratum_a = lib.baseline_stratum_id(
        W=15, direction="UP", displacement_mag_state="MID", vol_state="MID"
    )
    stratum_b = lib.baseline_stratum_id(
        W=15, direction="UP", displacement_mag_state="LOW", vol_state="MID"
    )
    t0 = lib.DEV_START_MS + 100 * lib.HOUR_MS
    t1 = t0 + lib.HOUR_MS
    base = lib._placebo_seed(0, 15, 60, t0, stratum_a)
    assert lib._placebo_seed(0, 15, 60, t1, stratum_a) != base
    assert lib._placebo_seed(0, 30, 60, t0, stratum_a) != base
    assert lib._placebo_seed(0, 15, 120, t0, stratum_a) != base
    assert lib._placebo_seed(0, 15, 60, t0, stratum_b) != base
    assert lib._placebo_seed(1, 15, 60, t0, stratum_a) != base


def test_index_permutation_matches_label_permutation_mapping():
    mismatches = 0
    checked = 0
    rng_meta = np.random.default_rng(FUZZ_SEED)
    for n in PERM_NS:
        for kind in PERM_KINDS:
            values = _make_label_list(kind, n)
            labels_u = np.asarray(values)
            labels_o = np.asarray(values, dtype=object)
            seeds = [int(x) for x in rng_meta.integers(0, 2**63, size=PERM_SEEDS_PER_CELL)]
            seeds.extend([lib.SEED_PLACEBO + i for i in range(20)])
            for labels in (labels_u, labels_o):
                for seed in seeds:
                    ref = lib._placebo_permuted_labels_reference(labels, seed)
                    idx = lib._placebo_permutation_indices(n, seed)
                    got = np.asarray(labels)[idx]
                    checked += 1
                    if not np.array_equal(ref, got):
                        mismatches += 1
    assert mismatches == 0
    assert checked == (
        len(PERM_NS) * len(PERM_KINDS) * 2 * (PERM_SEEDS_PER_CELL + 20)
    )


def test_exact_median_matches_np_median_on_required_shapes():
    rng = np.random.default_rng(FUZZ_SEED + 1)
    cases = []
    for n in list(range(1, 33)) + [40, 80, 81, 100, 121, 200, 500]:
        for _ in range(25):
            values = rng.normal(scale=2.5, size=n)
            values[::5] = values[0]
            cases.append(values)
        cases.append(np.linspace(-3.0, 3.0, n))
        cases.append(np.full(n, 0.25))
        cases.append(np.concatenate([np.full(max(n - 1, 1), -1.5), np.array([2.5])])[:n])
    extremes = [
        np.array([1e-308, -1e-308, 1e-308], dtype=np.float64),
        np.array([1e308, -1e308, 0.0, 1e308], dtype=np.float64),
        np.array([-1e308, 1e308], dtype=np.float64),
        np.array([np.nextafter(0.0, 1.0), np.nextafter(0.0, -1.0)], dtype=np.float64),
        np.array([-0.0, 0.0, -0.0], dtype=np.float64),
    ]
    cases.extend(extremes)
    mismatches = 0
    for values in cases:
        ref = float(np.median(values))
        got = lib._exact_finite_median_inplace(values.copy())
        if np.float64(got) != np.float64(ref) and not (
            math.isnan(got) and math.isnan(ref)
        ):
            mismatches += 1
    assert mismatches == 0
    assert len(cases) >= 800


def _one_event_compare(
    sorted_y: np.ndarray,
    sorted_states: np.ndarray,
    eval_state: int,
    seed: int,
    base_ae: float,
    y: float,
) -> dict[str, object]:
    labels = _labels_from_states(sorted_states)
    eval_label = lib.STATE_LABELS[int(eval_state)]
    ref_perm = lib._placebo_permuted_labels_reference(labels, seed)
    opt_idx = lib._placebo_permutation_indices(int(sorted_y.size), seed)
    opt_perm = labels[opt_idx]
    ref_chosen = sorted_y[ref_perm == eval_label]
    opt_chosen = sorted_y[sorted_states[opt_idx] == int(eval_state)]
    ref_pred = lib._placebo_prediction_reference(sorted_y, labels, eval_label, seed)
    opt_pred = lib._placebo_prediction(sorted_y, sorted_states, eval_state, seed)
    if math.isfinite(ref_pred):
        ref_impr = base_ae - abs(y - ref_pred)
    else:
        ref_impr = float("nan")
    if math.isfinite(opt_pred):
        opt_impr = base_ae - abs(y - opt_pred)
    else:
        opt_impr = float("nan")
    return {
        "perm_equal": np.array_equal(ref_perm, opt_perm),
        "chosen_equal": np.array_equal(ref_chosen, opt_chosen),
        "pred_equal": (
            np.float64(ref_pred) == np.float64(opt_pred)
            if math.isfinite(ref_pred) or math.isfinite(opt_pred)
            else math.isnan(ref_pred) and math.isnan(opt_pred)
        ),
        "impr_equal": (
            np.float64(ref_impr) == np.float64(opt_impr)
            if math.isfinite(ref_impr) or math.isfinite(opt_impr)
            else math.isnan(ref_impr) and math.isnan(opt_impr)
        ),
        "ref_pred": ref_pred,
        "opt_pred": opt_pred,
        "ref_impr": ref_impr,
        "opt_impr": opt_impr,
    }


def test_reference_vs_optimized_per_replicate_contract():
    rng = np.random.default_rng(FUZZ_SEED + 2)
    n = 81
    states = np.asarray([i % 3 for i in range(n)], dtype=np.int8)
    y_hist = rng.normal(size=n)
    eval_state = lib.STATE_HIGH
    t = lib.DEV_START_MS + 333 * lib.HOUR_MS
    stratum = lib.baseline_stratum_id(
        W=15, direction="UP", displacement_mag_state="MID", vol_state="HIGH"
    )
    y_eval = 0.4
    base_ae = 0.25
    ref_impr = np.empty(lib.N_PLACEBO, dtype=np.float64)
    opt_impr = np.empty(lib.N_PLACEBO, dtype=np.float64)
    for rep in range(lib.N_PLACEBO):
        seed = lib._placebo_seed(rep, 15, 60, t, stratum)
        out = _one_event_compare(y_hist, states, eval_state, seed, base_ae, y_eval)
        assert out["perm_equal"]
        assert out["chosen_equal"]
        assert out["pred_equal"]
        assert out["impr_equal"]
        ref_impr[rep] = out["ref_impr"]
        opt_impr[rep] = out["opt_impr"]
    assert np.array_equal(ref_impr, opt_impr)
    ref_q = float(np.quantile(ref_impr, lib.PLACEBO_Q))
    opt_q = float(np.quantile(opt_impr, lib.PLACEBO_Q))
    assert np.float64(ref_q) == np.float64(opt_q)


def test_row_order_invariance_after_canonical_sort():
    rng = np.random.default_rng(FUZZ_SEED + 3)
    n = 40
    t0 = lib.DEV_START_MS + 10 * lib.HOUR_MS
    times = t0 + np.arange(n) * lib.HOUR_MS
    states = np.asarray([i % 3 for i in range(n)], dtype=np.int8)
    y_hist = rng.normal(size=n)
    ids = [
        lib.canonical_event_id(W=15, direction="UP", T_ms=int(t), H=60)
        for t in times
    ]
    order = np.argsort(np.asarray(ids))
    sorted_y = y_hist[order]
    sorted_states = states[order]
    shuffled = rng.permutation(n)
    shuffled_times = times[shuffled]
    shuffled_states = states[shuffled]
    shuffled_y = y_hist[shuffled]
    shuffled_ids = [
        lib.canonical_event_id(W=15, direction="UP", T_ms=int(t), H=60)
        for t in shuffled_times
    ]
    reorder = np.argsort(np.asarray(shuffled_ids))
    resorted_y = shuffled_y[reorder]
    resorted_states = shuffled_states[reorder]
    assert np.array_equal(sorted_y, resorted_y)
    assert np.array_equal(sorted_states, resorted_states)
    seed = lib._placebo_seed(
        4,
        15,
        60,
        int(t0 + n * lib.HOUR_MS),
        lib.baseline_stratum_id(
            W=15, direction="UP", displacement_mag_state="LOW", vol_state="HIGH"
        ),
    )
    a = lib._placebo_prediction(sorted_y, sorted_states, lib.STATE_MID, seed)
    b = lib._placebo_prediction(resorted_y, resorted_states, lib.STATE_MID, seed)
    assert np.float64(a) == np.float64(b)
    labels = _labels_from_states(sorted_states)
    ref = lib._placebo_prediction_reference(sorted_y, labels, "MID", seed)
    assert np.float64(a) == np.float64(ref)


def test_differential_fuzz_reference_vs_optimized():
    rng = np.random.default_rng(FUZZ_SEED)
    mismatches = 0
    replicate_comparisons = 0
    q95_comparisons = 0
    for case in range(FUZZ_CASES):
        n = int(rng.integers(80, 121))
        composition = int(rng.integers(0, 4))
        if composition == 0:
            states = np.full(n, int(rng.integers(0, 3)), dtype=np.int8)
        elif composition == 1:
            states = np.asarray(rng.integers(0, 2, size=n), dtype=np.int8)
        elif composition == 2:
            states = np.asarray(rng.integers(0, 3, size=n), dtype=np.int8)
        else:
            states = np.full(n, 0, dtype=np.int8)
            n_high = max(1, n // 10)
            states[-n_high:] = 2
            states[-(2 * n_high) : -n_high] = 1
        y_hist = rng.normal(scale=float(rng.uniform(0.1, 3.0)), size=n)
        eval_state = int(rng.integers(0, 3))
        if int(np.sum(states == eval_state)) == 0:
            eval_state = int(states[0])
        W = int(rng.choice(lib.W_VALUES))
        H = int(rng.choice(lib.H_VALUES))
        direction = str(rng.choice(["UP", "DOWN"]))
        mag = lib.STATE_LABELS[int(rng.integers(0, 3))]
        vol = lib.STATE_LABELS[int(rng.integers(0, 3))]
        t = int(lib.DEV_START_MS + int(rng.integers(100, 8000)) * lib.HOUR_MS)
        stratum = lib.baseline_stratum_id(
            W=W, direction=direction, displacement_mag_state=mag, vol_state=vol
        )
        y_eval = float(rng.normal())
        base_pred = float(np.median(y_hist))
        base_ae = abs(y_eval - base_pred)
        ref_impr = np.empty(lib.N_PLACEBO, dtype=np.float64)
        opt_impr = np.empty(lib.N_PLACEBO, dtype=np.float64)
        for rep in range(lib.N_PLACEBO):
            seed = lib._placebo_seed(rep, W, H, t, stratum)
            out = _one_event_compare(
                y_hist, states, eval_state, seed, base_ae, y_eval
            )
            replicate_comparisons += 1
            if not (
                out["perm_equal"]
                and out["chosen_equal"]
                and out["pred_equal"]
                and out["impr_equal"]
            ):
                mismatches += 1
            ref_impr[rep] = out["ref_impr"]
            opt_impr[rep] = out["opt_impr"]
        if not np.array_equal(ref_impr, opt_impr):
            mismatches += 1
        ref_q = float(np.quantile(ref_impr[np.isfinite(ref_impr)], lib.PLACEBO_Q))
        opt_q = float(np.quantile(opt_impr[np.isfinite(opt_impr)], lib.PLACEBO_Q))
        q95_comparisons += 1
        if np.float64(ref_q) != np.float64(opt_q):
            mismatches += 1
    assert mismatches == 0
    assert replicate_comparisons == FUZZ_CASES * lib.N_PLACEBO
    assert q95_comparisons == FUZZ_CASES


def test_evaluate_cell_q95_matches_reference_on_single_scored_event(monkeypatch):
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    t0 = lib.DEV_START_MS + 200 * lib.HOUR_MS
    events = []
    for i in range(81):
        events.append(
            _ready_event(
                t0 + i * lib.HOUR_MS,
                morph=lib.STATE_HIGH,
                y=float(i % 17) * 0.01,
            )
        )
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["N"] == 1
    assert cell["placebo_replicate_count_nominal"] == 100
    assert cell["placebo_replicate_count_finite"] == 100
    scored = cell["scored"][0]
    hist = events[:-1]
    ids = [
        lib.canonical_event_id(W=15, direction="UP", T_ms=int(e["T"]), H=60)
        for e in hist
    ]
    order = np.argsort(np.asarray(ids))
    sorted_y = np.asarray([float(hist[i]["Y"]) for i in order], dtype=np.float64)
    sorted_states = np.asarray(
        [int(hist[i]["morphology_state"]) for i in order],
        dtype=np.int8,
    )
    labels = _labels_from_states(sorted_states)
    eval_t = int(events[-1]["T"])
    stratum = lib.baseline_stratum_id(
        W=15, direction="UP", displacement_mag_state="MID", vol_state="MID"
    )
    y_eval = float(events[-1]["Y"])
    base_ae = float(scored["base_ae"])
    ref_impr = np.empty(lib.N_PLACEBO, dtype=np.float64)
    for rep in range(lib.N_PLACEBO):
        seed = lib._placebo_seed(rep, 15, 60, eval_t, stratum)
        pred = lib._placebo_prediction_reference(
            sorted_y, labels, "HIGH", seed
        )
        ref_impr[rep] = base_ae - abs(y_eval - pred)
    ref_q = float(np.quantile(ref_impr, lib.PLACEBO_Q))
    assert np.float64(cell["placebo_q95"]) == np.float64(ref_q)


def test_evaluate_cell_q95_matches_reference_walk_forward(monkeypatch):
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    t0 = lib.DEV_START_MS + 400 * lib.HOUR_MS
    events = []
    for i in range(130):
        events.append(
            _ready_event(
                t0 + i * lib.HOUR_MS,
                morph=i % 3,
                y=float((i % 23) - 11) * 0.02,
            )
        )
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 15)
    assert cell["N"] > 1
    assert cell["placebo_replicate_count_nominal"] == 100
    assert cell["placebo_replicate_count_finite"] == 100

    ready = []
    for event in events:
        record = dict(event)
        record["H"] = 15
        if lib._decision_ready(record) and math.isfinite(float(record["Y"])):
            ready.append(record)
    ready.sort(key=lambda item: (int(item["T"]), str(item["direction"])))
    baseline_queues: dict[tuple[object, ...], deque] = defaultdict(deque)
    candidate_queues: dict[tuple[object, ...], deque] = defaultdict(deque)
    mature = 0
    h_ms = 15 * lib.BAR_MS
    placebo_sums = np.zeros(lib.N_PLACEBO, dtype=np.float64)
    n_scored = 0
    for event in ready:
        current_t = int(event["T"])
        while mature < len(ready) and int(ready[mature]["T"]) + h_ms <= current_t:
            previous = ready[mature]
            item = (
                int(previous["T"]),
                float(previous["Y"]),
                int(previous["morphology_state"]),
                str(previous["direction"]),
                int(previous["W"]),
                lib.canonical_event_id(
                    W=int(previous["W"]),
                    direction=str(previous["direction"]),
                    T_ms=int(previous["T"]),
                    H=15,
                ),
            )
            base_key = (
                int(previous["W"]),
                str(previous["direction"]),
                lib.state_label(int(previous["mag_state"])),
                lib.state_label(int(previous["vol_state"])),
            )
            candidate_key = (
                *base_key,
                lib.state_label(int(previous["morphology_state"])),
            )
            baseline_queues[base_key].append(item)
            candidate_queues[candidate_key].append(item)
            mature += 1
        if not lib.scoring_eligible(current_t, 15):
            continue
        base_key = (
            int(event["W"]),
            str(event["direction"]),
            lib.state_label(int(event["mag_state"])),
            lib.state_label(int(event["vol_state"])),
        )
        candidate_key = (
            *base_key,
            lib.state_label(int(event["morphology_state"])),
        )
        base_queue = baseline_queues[base_key]
        candidate_queue = candidate_queues[candidate_key]
        cutoff = current_t - lib.TRAIN_MS
        lib._purge(base_queue, cutoff)
        lib._purge(candidate_queue, cutoff)
        if (
            len(base_queue) < lib.BASELINE_MIN_COUNT
            or len(candidate_queue) < lib.CANDIDATE_MIN_COUNT
        ):
            continue
        base_y = np.asarray([float(item[1]) for item in base_queue], dtype=np.float64)
        cand_y = np.asarray(
            [float(item[1]) for item in candidate_queue], dtype=np.float64
        )
        base_pred = float(np.median(base_y))
        cand_pred = float(np.median(cand_y))
        y = float(event["Y"])
        if not (
            math.isfinite(base_pred) and math.isfinite(cand_pred) and math.isfinite(y)
        ):
            continue
        n_scored += 1
        base_ae = abs(y - base_pred)
        sorted_items = sorted(base_queue, key=lambda item: str(item[5]))
        sorted_y = np.asarray(
            [float(item[1]) for item in sorted_items], dtype=np.float64
        )
        labels = np.asarray(
            [lib.STATE_LABELS[int(item[2])] for item in sorted_items]
        )
        eval_label = lib.state_label(int(event["morphology_state"]))
        stratum = lib.baseline_stratum_id(
            W=15,
            direction=str(event["direction"]),
            displacement_mag_state=lib.state_label(int(event["mag_state"])),
            vol_state=lib.state_label(int(event["vol_state"])),
        )
        for rep in range(lib.N_PLACEBO):
            seed = lib._placebo_seed(rep, 15, 15, current_t, stratum)
            pred = lib._placebo_prediction_reference(
                sorted_y, labels, eval_label, seed
            )
            if not math.isfinite(pred):
                placebo_sums[rep] = float("nan")
                continue
            placebo_sums[rep] += base_ae - abs(y - pred)
    assert n_scored == cell["N"]
    placebo_means = placebo_sums / n_scored
    ref_q = float(np.quantile(placebo_means[np.isfinite(placebo_means)], lib.PLACEBO_Q))
    assert np.float64(cell["placebo_q95"]) == np.float64(ref_q)


def test_evaluate_cell_does_not_call_reference_hot_path():
    source = Path(lib.__file__).read_text(encoding="utf-8")
    start = source.index("def evaluate_cell")
    end = source.index("\ndef _cell_five_pass")
    body = source[start:end]
    assert "_placebo_prediction_reference" not in body
    assert "rng.permutation(sorted_base_labels)" not in body
    assert "_placebo_prediction(" in body
    assert "_placebo_seed(" in body
    assert "_placebo_prediction" in lib.evaluate_cell.__code__.co_names


def test_production_placebo_constants_unchanged():
    assert lib.N_PLACEBO == 100
    assert lib.SEED_PLACEBO == 20260904
    assert lib.PLACEBO_Q == 0.95
    source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "np.random.default_rng" in source
    assert "SeedSequence" not in source
    assert "hash(" not in source.replace("hashlib", "")
