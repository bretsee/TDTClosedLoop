"""Shared loaders + per-event metrics for the 2026-08-31 science-core analysis.

Signals
-------
capture y8 : achieved control-channel feature (volts, ~101.7 Hz ticks)
ref_mix_rN : target trajectory r1 (volts), baseline 1.2e-4 V
Both tick columns start at 1 and are aligned 1:1.

Epoch convention: -30..+190 ticks relative to onset (220 ticks).
Lag-corrected comparison at +L: achieved y8[t+L] vs target ref[t].
"""
import json
import os

import numpy as np

DAY = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ROOT = os.path.normpath(os.path.join(DAY, ".."))
OUT = os.path.join(DAY, "analysis")

BASELINE_REF = 1.2e-4
SHAM_THRESHOLD = 0.000110803
PRE, POST = 30, 190          # epoch: onset-PRE .. onset+POST-1  (220 ticks)
LAG = 2                      # global best lag (achieved trails target)
SITES = ["D1", "D2", "D3", "P2", "LP", "SHAM"]
REAL_SITES = ["D1", "D2", "D3", "P2", "LP"]

CAPTURES = {
    ("MPC", "r1"):  os.path.join(ROOT, "capture_mpc_20260831_210645.csv"),
    ("MPC", "r2"):  os.path.join(ROOT, "capture_mpc_20260831_213029.csv"),
    ("Choi", "r1"): os.path.join(DAY, "capture_choi_mixr1.csv"),
    ("Choi", "r2"): os.path.join(DAY, "capture_choi_mixr2.csv"),
    ("Hold", "r1"): os.path.join(ROOT, "capture_mpc_20260831_204354.csv"),
}
ARMS = list(CAPTURES.keys())

COL = dict(green="#3F7A4E", grey="#5B6470", red="#B3413A", amber="#C9A23A")


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "Arial", "font.size": 10,
        "text.color": "black", "axes.labelcolor": "black",
        "axes.titlecolor": "black", "xtick.color": "black", "ytick.color": "black",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.dpi": 200, "savefig.dpi": 200,
    })
    return plt


def load_schedule(run):
    with open(os.path.join(DAY, f"schedule_mix_{run}.json")) as f:
        return json.load(f)


def load_ref(run):
    a = np.loadtxt(os.path.join(DAY, f"ref_mix_{run}.csv"), delimiter=",", skiprows=1)
    assert a[0, 0] == 1
    return a[:, 1]


def load_y8(arm, run):
    # header: tick,seq,t_ms,u1..u8,y1..y32 -> y8 at column 18
    a = np.loadtxt(CAPTURES[(arm, run)], delimiter=",", skiprows=1, usecols=(0, 18))
    assert a[0, 0] == 1
    ticks = a[:, 0].astype(int)
    assert np.all(np.diff(ticks) == 1), "non-contiguous ticks"
    return a[:, 1]


def epoch_indices(onset, n, lag=0):
    """0-based slice for ticks onset-PRE .. onset+POST-1 shifted by lag; None if out of range."""
    i0 = onset - PRE - 1 + lag
    i1 = onset + POST - 1 + lag
    if i0 < 0 or i1 > n:
        return None
    return i0, i1


def per_event_table(arm, run, sched=None, ref=None, y8=None):
    """List of dicts, one per usable event, with metrics at lag 0 and +LAG."""
    sched = sched or load_schedule(run)
    ref = load_ref(run) if ref is None else ref
    y8 = load_y8(arm, run) if y8 is None else y8
    n = len(y8)
    rows = []
    for ev in sched["events"]:
        onset = ev["onset_tick"]
        ri = epoch_indices(onset, len(ref), 0)
        yi0 = epoch_indices(onset, n, 0)
        yiL = epoch_indices(onset, n, LAG)
        if ri is None or yi0 is None or yiL is None:
            continue
        tgt = ref[ri[0]:ri[1]]
        ach0 = y8[yi0[0]:yi0[1]]
        achL = y8[yiL[0]:yiL[1]]
        # per-event baselines from the pre-onset margin (first 25 of the 30 pre ticks)
        tb = tgt[:25].mean()
        yb = achL[:25].mean()
        dt = tgt - tb
        dyL = achL - yb
        dy0 = ach0 - ach0[:25].mean()

        def safe_r(a, b):
            if a.std() < 1e-12 or b.std() < 1e-12:
                return np.nan
            return float(np.corrcoef(a, b)[0, 1])

        tgt_peak = float(dt[PRE:].max())
        ach_peak = float(dyL[PRE:].max())
        rows.append(dict(
            event=ev["event"], site=ev["site"], onset=onset,
            r0=safe_r(dt, dy0), rlag=safe_r(dt, dyL),
            tgt_peak=tgt_peak, ach_peak=ach_peak,
            peak_ratio=(ach_peak / tgt_peak) if tgt_peak > 1e-6 else np.nan,
            ach_absmod=float(np.abs(dyL[PRE:]).max()),
            ach_max_raw=float(achL[PRE:].max()),
            rmse=float(np.sqrt(np.mean((dyL - dt) ** 2))),
        ))
    return rows


def eta(arm_run_y8, ref, sched, site, lag=LAG):
    """Event-triggered average (baseline-subtracted) for one site. Returns (t_rel, mean_ach, mean_tgt, n, r_of_means)."""
    y8 = arm_run_y8
    achs, tgts = [], []
    for ev in sched["events"]:
        if ev["site"] != site:
            continue
        yi = epoch_indices(ev["onset_tick"], len(y8), lag)
        ri = epoch_indices(ev["onset_tick"], len(ref), 0)
        if yi is None or ri is None:
            continue
        a = y8[yi[0]:yi[1]]
        t = ref[ri[0]:ri[1]]
        achs.append(a - a[:25].mean())
        tgts.append(t - t[:25].mean())
    if not achs:
        return None
    A = np.mean(achs, axis=0)
    T = np.mean(tgts, axis=0)
    t_rel = np.arange(-PRE, POST)
    if T.std() > 1e-12 and A.std() > 1e-12:
        r = float(np.corrcoef(A, T)[0, 1])
    else:
        r = np.nan
    return t_rel, A, T, len(achs), r


def boot_ci(x, nboot=5000, seed=0):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(nboot, len(x)), replace=True).mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))
