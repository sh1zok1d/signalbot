"""TWAP chain detector (DECISION_LAYER_RESEARCH_PROGRAM_V0 §8, frozen grid).

Prints are one-sided taker prints of at least $1,000. Each print belongs to two
keys: its exact quantity (1e-8 units) and its quote notional rounded to $10.
A chain is a run of prints of one key whose consecutive gaps stay within an
absolute tolerance of the running period (2–300 s), with at most one missed
slice in a row. A chain is seeded by a triplet z < y < x with |(x-y)-(y-z)| <= tau.
The chain ends (TWAP_END) once no matching slice arrived for 3 x period after
its last slice; the end time is that declaration time.

Chain growth depends only on the tolerance. The minimum slice count K and the
minimum duration only decide when a chain qualifies, so one build per tolerance
serves every (K, duration) cell of the grid exactly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

P_MIN_MS, P_MAX_MS = 2_000, 300_000
MIN_K_IN_GRID = 20
MIN_DUR_IN_GRID_MS = 15 * 60_000


@dataclass
class Chain:
    side: int
    key_type: str
    key: int
    slices: list = field(default_factory=list)
    period: float = 0.0
    units: int = 0
    miss_in_row: int = 0
    version: int = 0

    @property
    def start(self) -> int:
        return self.slices[0]

    @property
    def last(self) -> int:
        return self.slices[-1]

    @property
    def end(self) -> float:
        return self.last + 3.0 * self.period

    def qualified_at(self, k: int, min_dur_ms: int):
        s = self.slices
        if len(s) < k:
            return None
        lo = k - 1
        target = s[0] + min_dur_ms
        idx = int(np.searchsorted(np.asarray(s), target, side="left"))
        i = max(lo, idx)
        return s[i] if i < len(s) else None


def build_chains_for_key(arr: np.ndarray, tau: int, side: int, key_type: str, key: int) -> list[Chain]:
    """Greedy chain building on sorted unique ms timestamps of one key.

    Returns only chains that reach the loosest grid cell (>= 20 slices and
    >= 15 min); no other chain can qualify for any candidate.
    """
    n_arr = len(arr)
    if n_arr < MIN_K_IN_GRID:
        return []
    chains: list = []
    buckets: dict[int, list] = {}
    kept: list[tuple[int, Chain]] = []

    def register(cid: int):
        ch = chains[cid]
        top = 2 if ch.miss_in_row == 0 else 1
        for k in range(1, top + 1):
            pred = ch.last + k * ch.period
            buckets.setdefault(int(pred // tau), []).append((cid, ch.version, k, k == top))

    def finalize(cid: int):
        # a chain whose furthest prediction bucket is gone can never be extended again
        ch = chains[cid]
        if len(ch.slices) >= MIN_K_IN_GRID and ch.last - ch.start >= MIN_DUR_IN_GRID_MS:
            kept.append((cid, ch))
        chains[cid] = None

    last_clean = 0
    for i in range(n_arr):
        x = int(arr[i])
        bx = x // tau
        best = None
        for b in (bx - 1, bx, bx + 1):
            for cid, ver, k, _ in buckets.get(b, ()):
                ch = chains[cid]
                if ch is None or ch.version != ver:
                    continue
                d = abs(x - (ch.last + k * ch.period))
                if d <= tau:
                    cand = (len(ch.slices), -d, cid, k)
                    if best is None or cand > best:
                        best = cand
        if best is not None:
            _, _, cid, k = best
            ch = chains[cid]
            ch.period = (ch.period * ch.units + (x - ch.last)) / (ch.units + k)
            ch.units += k
            ch.miss_in_row = 1 if k == 2 else 0
            ch.slices.append(x)
            ch.version += 1
            register(cid)
        else:
            lo = int(np.searchsorted(arr, x - P_MAX_MS, side="left"))
            hi = int(np.searchsorted(arr, x - P_MIN_MS, side="right"))
            hi = min(hi, i)
            if hi > lo:
                ys = arr[lo:hi]
                targets = 2 * ys - x
                idx = np.searchsorted(arr, targets - tau, side="left")
                valid = idx < n_arr
                idx_c = np.minimum(idx, n_arr - 1)
                zs = arr[idx_c]
                ok = valid & (zs <= targets + tau) & (zs < ys) & ((ys - zs) >= P_MIN_MS) & ((ys - zs) <= P_MAX_MS)
                for y, z in zip(ys[ok].tolist(), zs[ok].tolist()):
                    ch = Chain(side=side, key_type=key_type, key=key, slices=[z, y, x],
                               period=(x - z) / 2.0, units=2)
                    chains.append(ch)
                    register(len(chains) - 1)
        if i - last_clean >= 2000:
            last_clean = i
            cutoff = (x - tau) // tau - 1
            for b in sorted(b for b in buckets if b < cutoff):
                for cid, ver, _, top in buckets.pop(b):
                    ch = chains[cid]
                    if top and ch is not None and ch.version == ver:
                        finalize(cid)
    for cid, ch in enumerate(chains):
        if ch is not None:
            finalize(cid)
    kept.sort(key=lambda c: c[0])
    return [ch for _, ch in kept]


def key_groups(prints: dict, min_count: int = MIN_K_IN_GRID):
    """Yield (side, key_type, key, times) for keys with at least min_count prints."""
    t, side, q, nkey = prints["time"], prints["side"], prints["q"], prints["nkey"]
    for key_type, kv in (("Q", q), ("N", nkey)):
        for s in (1, -1):
            m = side == s
            tt, kk = t[m], kv[m]
            order = np.lexsort((tt, kk))
            tt, kk = tt[order], kk[order]
            starts = np.flatnonzero(np.r_[True, kk[1:] != kk[:-1]])
            ends = np.r_[starts[1:], len(kk)]
            big = (ends - starts) >= min_count
            for a, b in zip(starts[big], ends[big]):
                yield s, key_type, int(kk[a]), tt[a:b]


def build_all(prints: dict, tau: int, workers: int = 4) -> list[Chain]:
    groups = list(key_groups(prints))
    if workers <= 1 or len(groups) < 50:
        out = []
        for s, kt, k, arr in groups:
            out.extend(build_chains_for_key(arr, tau, s, kt, k))
        return out
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    # interleave by size so work is balanced
    groups.sort(key=lambda g: -len(g[3]))
    chunks = [groups[i::workers] for i in range(workers)]
    with ctx.Pool(workers) as pool:
        parts = pool.starmap(_build_chunk, [(c, tau) for c in chunks])
    return [ch for part in parts for ch in part]


def _build_chunk(groups, tau):
    out = []
    for s, kt, k, arr in groups:
        out.extend(build_chains_for_key(arr, tau, s, kt, k))
    return out


def qualified(chains: list[Chain], k: int, min_dur_ms: int) -> list[dict]:
    rows = []
    for ch in chains:
        qa = ch.qualified_at(k, min_dur_ms)
        if qa is None:
            continue
        rows.append({"side": ch.side, "key_type": ch.key_type, "key": ch.key, "start": ch.start,
                     "qualified_at": int(qa), "last": ch.last, "end": float(ch.end),
                     "period_ms": ch.period, "slices": len(ch.slices)})
    return rows


def merge_episodes(rows: list[dict]) -> list[dict]:
    """Overlapping same-side qualified chains merge into one episode."""
    eps = []
    for s in (1, -1):
        rs = sorted((r for r in rows if r["side"] == s), key=lambda r: r["start"])
        cur = None
        for r in rs:
            if cur is not None and r["start"] <= cur["end"]:
                cur["end"] = max(cur["end"], r["end"])
                cur["T"] = min(cur["T"], r["qualified_at"])
                cur["chains"] += 1
                cur["slices"] += r["slices"]
                cur["key_types"].add(r["key_type"])
            else:
                if cur is not None:
                    eps.append(cur)
                cur = {"side": s, "start": r["start"], "T": r["qualified_at"], "end": r["end"],
                       "chains": 1, "slices": r["slices"], "period_ms": r["period_ms"],
                       "key_types": {r["key_type"]}}
        if cur is not None:
            eps.append(cur)
    for e in eps:
        e["key_types"] = "".join(sorted(e["key_types"]))
    return sorted(eps, key=lambda e: e["T"])


def apply_refractory(eps: list[dict], refractory_ms: int = 6 * 3_600_000) -> tuple[list[dict], list[dict]]:
    kept, dropped = [], []
    last = {1: -math.inf, -1: -math.inf}
    for e in sorted(eps, key=lambda e: e["T"]):
        if e["T"] >= last[e["side"]] + refractory_ms:
            kept.append(e)
            last[e["side"]] = e["T"]
        else:
            dropped.append({**e, "exclusion": "REFRACTORY"})
    return kept, dropped


def shuffle_within_hour(prints: dict, seed: int) -> dict:
    """Hour-preserving null: each print keeps its hour, its time is redrawn uniformly within it."""
    rng = np.random.default_rng(seed)
    t = prints["time"]
    hour = t // 3_600_000
    nt = hour * 3_600_000 + rng.integers(0, 3_600_000, size=len(t))
    out = {k: v for k, v in prints.items()}
    order = np.argsort(nt, kind="stable")
    out = {k: v[order] for k, v in out.items()}
    out["time"] = nt[order]
    # a key never has two prints in the same millisecond after grouping; break rare ties
    return _dedupe_same_ms(out)


def _dedupe_same_ms(p: dict) -> dict:
    key = p["time"] * 2 + (p["side"] > 0)
    keep = np.r_[True, key[1:] != key[:-1]]
    return {k: v[keep] for k, v in p.items()}


def make_injections(n: int, seed: int, t_start: int, t_end: int, price_at) -> list[dict]:
    """Synthetic TWAPs: period 3–60 s, slice $2k–$50k (log-uniform), duration 20–120 min,
    quantity or notional slicing, either side, jitter U(-100, +100) ms per slice."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        period = float(rng.uniform(3_000, 60_000))
        dur = float(rng.uniform(20, 120)) * 60_000
        start = int(rng.integers(t_start, t_end - int(dur) - 3_600_000))
        usd = float(np.exp(rng.uniform(np.log(2_000), np.log(50_000))))
        mode = "Q" if rng.random() < 0.5 else "N"
        if mode == "N":
            usd = float(round(usd / 100.0) * 100.0)   # quote-sized orders use round notionals
        side = 1 if rng.random() < 0.5 else -1
        n_sl = int(dur // period) + 1
        times = start + (np.arange(n_sl) * period).astype(np.int64) + rng.integers(-100, 101, size=n_sl)
        p0 = price_at(start)
        q_fixed = int(round(usd / p0 * 1e5)) * 1000            # lot 1e-5 BTC in 1e-8 units
        qs, us = [], []
        for tt in times:
            px = price_at(int(tt))
            if mode == "Q":
                q = q_fixed
            else:
                q = int(math.floor(usd / px * 1e5)) * 1000
            qs.append(q)
            us.append(q / 1e8 * px)
        out.append({"id": i, "side": side, "mode": mode, "period_ms": period, "start": int(times[0]),
                    "stop": int(times[-1]), "times": times.astype(np.int64), "q": np.array(qs, dtype=np.int64),
                    "usd": np.array(us),
                    "key": (q_fixed if mode == "Q" else int(np.bincount(np.rint(np.array(us) / 10.0).astype(np.int64)).argmax()))})
    return out


def inject(prints: dict, injections: list[dict]) -> dict:
    """Add synthetic prints; a collision with a real print of the same side and ms merges them."""
    t = [prints["time"]]; s = [prints["side"]]; q = [prints["q"]]; u = [prints["usd"]]
    for inj in injections:
        t.append(inj["times"]); s.append(np.full(len(inj["times"]), inj["side"], dtype=np.int8))
        q.append(inj["q"]); u.append(inj["usd"])
    t = np.concatenate(t); s = np.concatenate(s); q = np.concatenate(q); u = np.concatenate(u)
    key = t * 2 + (s > 0)
    order = np.argsort(key, kind="stable")
    key, q, u = key[order], q[order], u[order]
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    k = key[st]
    tt = k // 2
    ss = np.where(k % 2 == 1, 1, -1).astype(np.int8)
    qq = np.add.reduceat(q, st)
    uu = np.add.reduceat(u, st)
    o = np.argsort(tt, kind="stable")
    return {"time": tt[o], "side": ss[o], "q": qq[o], "nkey": np.rint(uu[o] / 10.0).astype(np.int64), "usd": uu[o]}


def injection_detected(inj: dict, qualified_rows: list[dict]) -> bool:
    span = inj["stop"] - inj["start"]
    for r in qualified_rows:
        if r["side"] != inj["side"] or r["key_type"] != inj["mode"] or r["key"] != inj["key"]:
            continue
        ov = min(r["last"], inj["stop"]) - max(r["start"], inj["start"])
        if ov >= 0.5 * span:
            return True
    return False
