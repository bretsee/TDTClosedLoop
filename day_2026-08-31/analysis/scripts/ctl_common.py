"""Shared helpers for the ctl_* (workstream B4) extended control analyses.

Artifact-aware convention: exclude relative ticks 0..2 post-onset (the art_*
pass showed stim-artifact contamination there) from all masked metrics.
Per-arm best lags from the overnight pass: MPC +2, Choi r1 +1, Choi r2 +2.
"""
import os

import numpy as np
import sci_common as C

SCR = os.path.join(C.OUT, "scripts")
ART_LO, ART_HI = 0, 2                      # relative ticks excluded (inclusive)
BEST_LAG = {("MPC", "r1"): 2, ("MPC", "r2"): 2,
            ("Choi", "r1"): 1, ("Choi", "r2"): 2, ("Hold", "r1"): 2}
TREL = np.arange(-C.PRE, C.POST)
KEEP = ~((TREL >= ART_LO) & (TREL <= ART_HI))      # artifact-excluded samples
POST_KEEP = KEEP & (TREL >= 0)                     # post-onset, artifact-excluded

_y8_cache = {}


def y8(arm, run):
    key = f"{arm}_{run}"
    if key not in _y8_cache:
        p = os.path.join(SCR, f"_ctl_y8_{key}.npy")
        if os.path.exists(p):
            _y8_cache[key] = np.load(p)
        else:
            v = C.load_y8(arm, run)
            np.save(p, v)
            _y8_cache[key] = v
    return _y8_cache[key]


def masked_r(dt, dy):
    a, b = dt[KEEP], dy[KEEP]
    if a.std() < 1e-12 or b.std() < 1e-12:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def event_epochs(arm, run, lag=None, real_only=True):
    """Per-event dicts with baseline-subtracted target (dt) and lag-corrected,
    baseline-subtracted achieved (dy) epochs (trel -30..189). Baselines use the
    first 25 pre-onset ticks (artifact-free by construction)."""
    if lag is None:
        lag = BEST_LAG[(arm, run)]
    sched = C.load_schedule(run)
    ref = C.load_ref(run)
    sig = y8(arm, run)
    rows = []
    for ev in sched["events"]:
        if real_only and ev["site"] not in C.REAL_SITES:
            continue
        o = ev["onset_tick"]
        ri = C.epoch_indices(o, len(ref), 0)
        yi = C.epoch_indices(o, len(sig), lag)
        if ri is None or yi is None:
            continue
        t = ref[ri[0]:ri[1]]
        a = sig[yi[0]:yi[1]]
        dt = t - t[:25].mean()
        dy = a - a[:25].mean()
        rows.append(dict(event=ev["event"], site=ev["site"], onset=o,
                         dt=dt, dy=dy,
                         # target has no artifact -> full post-onset peak;
                         # achieved is masked (ticks 0-2 excluded)
                         tgt_peak=float(dt[TREL >= 0].max()),
                         ach_peak=float(dy[POST_KEEP].max()),
                         r=masked_r(dt, dy)))
    return rows


def ols(x, y):
    """slope, intercept of y = a*x + b."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    a, b = np.polyfit(x, y, 1)
    return float(a), float(b)


def boot_slope(x, y, nboot=5000, seed=0):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rng = np.random.default_rng(seed)
    n = len(x)
    sl = np.empty(nboot)
    for i in range(nboot):
        idx = rng.integers(0, n, n)
        if np.std(x[idx]) < 1e-15:
            sl[i] = np.nan
            continue
        sl[i] = np.polyfit(x[idx], y[idx], 1)[0]
    sl = sl[~np.isnan(sl)]
    return float(np.percentile(sl, 2.5)), float(np.percentile(sl, 97.5)), sl
