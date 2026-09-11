"""rank_common -- loaders/estimators for the plant-physiology (rank_) family.

Sources (all LOCAL): root capture_rig_runopfit10/11/12.csv (+_late2),
capture_rig_runrnd1.csv (183k-tick all-8-pair probe), plant_opfit12.lti.

Tonic gains: best-lag |corr| between a pair's command and each channel's
feature over lags 0..8 ticks (the surgery-night estimator, verbatim).
Pulse-evoked: feature-space signed response z per (pair, channel) from the
rnd1 probe -- onset-triggered feature deltas vs a shuffled-trigger floor.
NOTE the ms-resolution latencies (8-11.5 ms) came from the raw 610 Hz block
(not yet transferred); feature-space latency here is tick-resolution.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk  # noqa: E402

CACHE = ANA / "cache"
BLACKLIST = {33, 36, 45, 59}
MAX_LAG = 8

_caps: dict = {}


def capture(name: str):
    """(u [N,8], Y [N,64]) for a root rig capture."""
    if name in _caps:
        return _caps[name]
    import pandas as pd
    d = pd.read_csv(dk.need(REPO / name))
    u = d[[f"u{k}" for k in range(1, 9)]].to_numpy()
    Y = d[[f"y{k}" for k in range(1, 65)]].to_numpy()
    _caps[name] = (u, Y)
    return u, Y


def best_lag_corr(u_col: np.ndarray, y_col: np.ndarray) -> float:
    best = 0.0
    for L in range(MAX_LAG + 1):
        a = u_col[:len(u_col) - L] if L else u_col
        b = y_col[L:] if L else y_col
        c = np.corrcoef(a, b)[0, 1]
        if np.isfinite(c) and abs(c) > abs(best):
            best = float(abs(c))
    return best


def tonic_gain_matrix(name: str, pairs: list[int]) -> np.ndarray:
    """|corr| matrix len(pairs) x 64 for the named capture."""
    u, Y = capture(name)
    G = np.zeros((len(pairs), 64))
    for i, p in enumerate(pairs):
        for c in range(64):
            if (c + 1) in BLACKLIST:
                continue
            G[i, c] = best_lag_corr(u[:, p - 1], Y[:, c])
    return G


def pulse_response_matrix(min_amp: float = 12.9):
    """(Z [8,64] onset z, A [8,64] signed peak) from the rnd1 probe capture,
    feature-space (100 Hz ticks), cached (the capture is 183k rows)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "probe_rnd1_feature.npz"
    if f.exists():
        z = np.load(f)
        return z["Z"], z["A"]
    u, Y = capture("capture_rig_runrnd1.csv")
    rng = np.random.default_rng(20260910)
    Z = np.zeros((8, 64))
    A = np.zeros((8, 64))
    for p in range(8):
        col = u[:, p]
        rise = np.flatnonzero((col[1:] > 1e-6) & (col[:-1] <= 1e-6)) + 1
        rise = rise[col[rise] >= min_amp]
        rise = rise[(rise > 10) & (rise < len(u) - 10)]
        # signed evoked delta: mean over ticks +1..+3 minus ticks -3..-1
        for c in range(64):
            if (c + 1) in BLACKLIST:
                continue
            y = Y[:, c]
            post = np.mean([y[rise + k] for k in (1, 2, 3)], axis=0)
            pre = np.mean([y[rise - k] for k in (1, 2, 3)], axis=0)
            d = post - pre
            obs = float(d.mean())
            # shuffled-trigger floor
            nulls = []
            for _ in range(60):
                fake = rng.integers(10, len(u) - 10, size=len(rise))
                pf = np.mean([y[fake + k] for k in (1, 2, 3)], axis=0)
                bf = np.mean([y[fake - k] for k in (1, 2, 3)], axis=0)
                nulls.append(float((pf - bf).mean()))
            sd = np.std(nulls) + 1e-15
            Z[p, c] = abs(obs) / sd
            A[p, c] = obs
    np.savez_compressed(f, Z=Z, A=A)
    print(f"cached {f.name}")
    return Z, A


def eff_rank(M: np.ndarray, thresh: float = 0.1):
    sv = np.linalg.svd(M, compute_uv=False)
    sv = sv / (sv[0] + 1e-30)
    return int((sv >= thresh).sum()), sv


def write_json(name: str, payload: dict):
    out = ANA / name
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")
