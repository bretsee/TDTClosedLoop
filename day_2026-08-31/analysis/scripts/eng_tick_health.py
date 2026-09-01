"""eng_tick_health.png - per-run tick-period-error timelines with PLL resyncs."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eng_common import (GREEN, GREY, RED, AMBER, MUTED, RUNS, TICK_MS,
                        parse_log, rig, tick_err_ms, save)
import matplotlib.pyplot as plt

BIN_S = 30.0
FLAG_P95_MS = 3.0  # a 30-s bin whose p95 exceeds this is flagged as a stall

fig, axes = plt.subplots(3, 3, figsize=(11.5, 7.8), sharey=True)
fig.subplots_adjust(hspace=0.62, wspace=0.10, left=0.06, right=0.985,
                    top=0.87, bottom=0.07)

summary = {}
for ax, (lab, _, _, _, kind) in zip(axes.ravel(), RUNS):
    d = rig(lab)
    err, _ = tick_err_ms(d)
    t_s = (d["t_in_us"] - d["t_in_us"][0]) / 1e6
    tmid = 0.5 * (t_s[1:] + t_s[:-1])
    nbins = max(int(np.ceil(t_s[-1] / BIN_S)), 1)
    edges = np.arange(nbins + 1) * BIN_S
    idx = np.clip(np.digitize(tmid, edges) - 1, 0, nbins - 1)
    p95 = np.full(nbins, np.nan)
    bmax = np.full(nbins, np.nan)
    for b in range(nbins):
        m = idx == b
        if m.sum() > 10:
            p95[b] = np.percentile(err[m], 95)
            bmax[b] = err[m].max()
    ctr = (edges[:-1] + edges[1:]) / 2 / 60.0

    ax.plot(ctr, bmax, color=GREY, lw=0.8, alpha=0.55)
    ax.plot(ctr, p95, color=GREEN, lw=1.5)
    bad = p95 > FLAG_P95_MS
    if bad.any():
        ax.plot(ctr[bad], p95[bad], ".", color=RED, ms=6, zorder=4)

    # resyncs from loop log (packet index -> time)
    lg = parse_log(lab)
    n_startup = sum(1 for r in lg["resyncs_pll"] if r["packet"] <= 100)
    mid = [r for r in lg["resyncs_pll"] if r["packet"] > 100]
    for r in mid:
        pk = min(r["packet"], len(t_s)) - 1
        ax.axvline(t_s[pk] / 60.0, color=RED, lw=0.9, ls="--", alpha=0.8)
        ax.plot(t_s[pk] / 60.0, 25, "v", color=RED, ms=5, clip_on=False)
    n_sched = len(lg["resyncs_sched"])
    dropped = lg.get("droppedControlTicks", 0)

    note = f"{n_startup} startup resyncs"
    if mid:
        note += f", {len(mid)} mid-run (red)"
    if dropped:
        note += f"\n{dropped} dropped ticks"
    ax.text(0.985, 0.93, note, transform=ax.transAxes, ha="right", va="top",
            fontsize=7.5, color=(RED if (mid or dropped) else MUTED))

    ax.set_yscale("log")
    ax.set_ylim(0.05, 40)
    ax.axhline(FLAG_P95_MS, color=AMBER, lw=0.7, ls=":")
    ax.set_title(f"{lab}  ({kind})", loc="left", fontsize=9)
    ax.grid(True, axis="y", color="#E5E5E5", lw=0.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("run time (min)", fontsize=7.5)
    summary[lab] = {
        "resyncs_total": lg.get("resyncs_total"),
        "resyncs_startup": n_startup,
        "resyncs_midrun": len(mid),
        "midrun_resync_packets": [r["packet"] for r in mid],
        "scheduler_resync_events_logged": n_sched,
        "dropped_control_ticks": dropped,
        "phase_err_avg_ms": lg.get("phase_err_avg_ms"),
        "phase_err_max_ms": lg.get("phase_err_max_ms"),
        "bins_p95_over_3ms": int(bad.sum()),
        "loop_counters": {k: lg.get(k) for k in
                          ("submitted", "replies", "failures", "timeouts",
                           "staleDropped", "skippedWhileBusy", "freshTicks",
                           "heldTicks", "zeroTicks")},
    }

for ax in axes[:, 0]:
    ax.set_ylabel("|tick err| ms (log)", fontsize=8)

fig.suptitle("Tick health: all four arm runs clean (p95 < 1.9 ms, no mid-run resyncs); "
             "rnd1 had one ~30 ms stall at tick ~16.3k;\n"
             "opfit2 (last run, 21:56) degraded after tick ~9.9k — 73 resyncs, "
             "1016 dropped ticks (post-arm probe only, no arm data affected)",
             fontsize=11.5, fontweight="bold", color="black", x=0.06, ha="left", y=0.975)
fig.text(0.06, 0.895, "green = 30-s bin p95 of |tick period − 9.8304 ms|; grey = bin max; "
         "red dots = bin p95 > 3 ms; red dashes = mid-run Frame-PLL resyncs; "
         "startup resyncs (pre-stream backlog flush) occur at tick 1 in every run",
         fontsize=8.5, color=MUTED)

save(fig, "eng_tick_health.png")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tick.json"), "w") as f:
    json.dump(summary, f, indent=1)
print("tick health stashed")
