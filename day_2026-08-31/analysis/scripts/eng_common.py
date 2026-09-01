"""Shared helpers for 2026-08-31 engineering analysis (eng_* figures).

Works only from CSVs/logs in the repo root and day_2026-08-31/ (no TDT blocks).
"""
import json
import os
import re

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop"
DAY = os.path.join(REPO, "day_2026-08-31")
OUT = os.path.join(DAY, "analysis")

# Style contract
GREEN = "#3F7A4E"   # MPC / MATLAB server
GREY = "#5B6470"    # Choi / cpp server
RED = "#B3413A"     # anomalies / stalls
AMBER = "#C9A23A"   # tonic hold / warnings
INK = "#1A1A1A"
MUTED = "#777777"

TICK_MS = 9.8304  # nominal frame-locked tick period

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlecolor": "black",
    "axes.labelsize": 9,
    "axes.edgecolor": "#999999",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "xtick.color": "#444444",
    "ytick.color": "#444444",
    "legend.fontsize": 8,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.dpi": 200,
})

# Chronological run order for the day (label -> files)
RUNS = [
    # label, rig csv, loop log, server-lat csv (None if not written), kind
    ("rnd1",        "rig_runrnd1.csv",        "loop_runrnd1.log",        "server_lat_runrnd1.csv",  "probe"),
    ("rndhi",       "rig_runrndhi.csv",       "loop_runrndhi.log",       "server_lat_runrndhi.csv", "probe"),
    ("opfit",       "rig_runopfit.csv",       "loop_runopfit.log",       None,                      "probe"),
    ("mpc_mixr1",   "rig_runmpc_mixr1.csv",   "loop_runmpc_mixr1.log",   "mpc_lat_20260831_204354.csv", "arm-mpc-inert"),
    ("mpc_mixr1b",  "rig_runmpc_mixr1b.csv",  "loop_runmpc_mixr1b.log",  "mpc_lat_20260831_210645.csv", "arm-mpc"),
    ("choi_mixr1",  "rig_runchoi_mixr1.csv",  "loop_runchoi_mixr1.log",  None,                      "arm-choi"),
    ("mpc_mixr2",   "rig_runmpc_mixr2.csv",   "loop_runmpc_mixr2.log",   "mpc_lat_20260831_213029.csv", "arm-mpc"),
    ("choi_mixr2",  "rig_runchoi_mixr2.csv",  "loop_runchoi_mixr2.log",  None,                      "arm-choi"),
    ("opfit2",      "rig_runopfit2.csv",      "loop_runopfit2.log",      None,                      "probe"),
]

CAPTURES = {
    "mpc_mixr1":  os.path.join(REPO, "capture_mpc_20260831_204354.csv"),
    "mpc_mixr1b": os.path.join(REPO, "capture_mpc_20260831_210645.csv"),
    "mpc_mixr2":  os.path.join(REPO, "capture_mpc_20260831_213029.csv"),
    "choi_mixr1": os.path.join(DAY, "capture_choi_mixr1.csv"),
    "choi_mixr2": os.path.join(DAY, "capture_choi_mixr2.csv"),
    "rnd1":       os.path.join(REPO, "capture_rig_runrnd1.csv"),
    "rndhi":      os.path.join(REPO, "capture_rig_runrndhi.csv"),
    "opfit":      os.path.join(REPO, "capture_rig_runopfit.csv"),
    "opfit2":     os.path.join(REPO, "capture_rig_runopfit2.csv"),
}


def rig(label):
    """Load per-tick loop CSV as structured array."""
    for lab, rigf, _, _, _ in RUNS:
        if lab == label:
            return np.genfromtxt(os.path.join(REPO, rigf), delimiter=",", names=True)
    raise KeyError(label)


def tick_err_ms(d):
    """|tick period error| in ms from t_in_us deltas."""
    dt = np.diff(d["t_in_us"]) / 1000.0
    return np.abs(dt - TICK_MS), dt


def read_log(label):
    for lab, _, logf, _, _ in RUNS:
        if lab == label:
            raw = open(os.path.join(REPO, logf), "rb").read()
            return raw.decode("utf-16", errors="replace").splitlines()
    raise KeyError(label)


def parse_log(label):
    """Extract summary counters and resync events (with approx packet index)."""
    lines = read_log(label)
    out = {"resyncs_pll": [], "resyncs_sched": [], "label": label}
    lastpkt = 0
    for ln in lines:
        m = re.search(r"packet=(\d+)", ln)
        if m:
            lastpkt = int(m.group(1))
        m = re.search(r"Frame-PLL resync: phase error ([\d.]+) ms \(total resyncs (\d+)\)", ln)
        if m:
            out["resyncs_pll"].append({"packet": lastpkt, "phase_err_ms": float(m.group(1)),
                                       "n": int(m.group(2))})
        m = re.search(r"Scheduler resync: dropped=\d+ totalDropped=(\d+) lateUs=(\d+)", ln)
        if m:
            out["resyncs_sched"].append({"packet": lastpkt, "total_dropped": int(m.group(1)),
                                         "late_us": int(m.group(2))})
        if "Summary:" in ln and "packets=" in ln:
            for k in ("packets", "controlTicks", "droppedControlTicks"):
                m = re.search(k + r"=(\d+)", ln)
                if m:
                    out[k] = int(m.group(1))
        if "Scheduler:" in ln and "phaseErr" in ln:
            m = re.search(r"phaseErr avg ([\d.]+) ms max ([\d.]+) ms resyncs (\d+)", ln)
            if m:
                out["phase_err_avg_ms"] = float(m.group(1))
                out["phase_err_max_ms"] = float(m.group(2))
                out["resyncs_total"] = int(m.group(3))
        if "Localhost summary:" in ln:
            for k in ("submitted", "replies", "failures", "timeouts", "staleDropped",
                      "skippedWhileBusy", "freshTicks", "heldTicks", "zeroTicks"):
                m = re.search(k + r"=(\d+)", ln)
                if m:
                    out[k] = int(m.group(1))
    return out


def capture_u(label):
    """Load capture u1..u8 (uA). Returns (tick, U[n,8]) as recorded."""
    d = np.genfromtxt(CAPTURES[label], delimiter=",", names=True)
    U = np.vstack([d["u%d" % i] for i in range(1, 9)]).T
    return d["tick"].astype(int), U


def capture_u_filled(label, nticks):
    """u1..u8 reindexed onto tick 1..nticks, forward-filling gaps.

    MPC captures only log submitted ticks (skipped-while-busy ticks missing);
    the loop holds the previous command there, so ffill = delivered estimate.
    """
    tick, U = capture_u(label)
    full = np.zeros((nticks, 8))
    idx = np.clip(tick - 1, 0, nticks - 1)
    mask = np.zeros(nticks, dtype=bool)
    full[idx] = U
    mask[idx] = True
    # forward fill
    last = np.zeros(8)
    for i in range(nticks):
        if mask[i]:
            last = full[i]
        else:
            full[i] = last
    return full, int(mask.sum())


def pct(x, ps=(50, 95, 99)):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return {("p%g" % p): round(float(np.percentile(x, p)), 4) for p in ps}


def style_ax(ax):
    ax.grid(True, axis="y", color="#DDDDDD", lw=0.6, zorder=0)
    ax.set_axisbelow(True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)
    return p
