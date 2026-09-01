"""eng_latency.png - server turnaround (MATLAB vs cpp), loop timing, tick jitter."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eng_common import (GREEN, GREY, RED, AMBER, MUTED, INK, REPO, RUNS, TICK_MS,
                        pct, rig, tick_err_ms, style_ax, save)
import matplotlib.pyplot as plt


def load_matlab(fname):
    d = np.genfromtxt(os.path.join(REPO, fname), delimiter=",", names=True)
    return d["turnaround_ms"][np.isfinite(d["turnaround_ms"])], \
        d["compute_ms"][np.isfinite(d["compute_ms"])]


def load_cpp(fname):
    d = np.genfromtxt(os.path.join(REPO, fname), delimiter=",", names=True)
    return d["turnaroundMs"][np.isfinite(d["turnaroundMs"])], \
        d["computeMs"][np.isfinite(d["computeMs"])]


ml1, mlc1 = load_matlab("mpc_lat_20260831_210645.csv")   # mpc_mixr1b
ml2, mlc2 = load_matlab("mpc_lat_20260831_213029.csv")   # mpc_mixr2
ml = np.concatenate([ml1, ml2])
cp1, cpc1 = load_cpp("server_lat_runrnd1.csv")
cp2, cpc2 = load_cpp("server_lat_runrndhi.csv")
cp = np.concatenate([cp1, cp2])

ml_p = pct(ml)
cp_p = pct(cp)
ratio = ml_p["p50"] / cp_p["p50"]

fig = plt.figure(figsize=(10.5, 7.2))
gs = fig.add_gridspec(2, 2, hspace=0.52, wspace=0.30,
                      left=0.09, right=0.97, top=0.86, bottom=0.08)

bins = np.logspace(np.log10(0.005), np.log10(60), 90)

# --- A: MATLAB server turnaround ---
axA = fig.add_subplot(gs[0, 0])
axA.hist(np.clip(ml, bins[0], bins[-1]), bins=bins, color=GREEN, edgecolor="none")
axA.set_xscale("log")
axA.set_xlim(0.005, 60)
axA.axvline(TICK_MS, color=RED, lw=1.0, ls="--")
axA.text(TICK_MS * 1.15, axA.get_ylim()[1] * 0.02, "tick 9.83 ms", color=RED,
         fontsize=8, rotation=90, va="bottom")
axA.set_title("MATLAB MPC server (arm runs mixr1b+mixr2)\n"
              f"p50 {ml_p['p50']:.2f} / p95 {ml_p['p95']:.2f} / p99 {ml_p['p99']:.1f} ms",
              loc="left")
axA.set_xlabel("turnaround (ms, log)")
axA.set_ylabel("ticks")
style_ax(axA)
frac_over = float(np.mean(ml > TICK_MS))
axA.text(0.02, 0.95, f"{frac_over*100:.1f}% of replies\nmiss the 9.83 ms tick",
         transform=axA.transAxes, va="top", fontsize=8.5, color=RED)

# --- B: cpp server turnaround ---
axB = fig.add_subplot(gs[0, 1])
axB.hist(np.clip(cp, bins[0], bins[-1]), bins=bins, color=GREY, edgecolor="none")
axB.set_xscale("log")
axB.set_xlim(0.005, 60)
axB.axvline(TICK_MS, color=RED, lw=1.0, ls="--")
axB.set_title("cpp Choi server (probe runs rnd1+rndhi)\n"
              f"p50 {cp_p['p50']*1000:.0f} / p95 {cp_p['p95']*1000:.0f} / "
              f"p99 {cp_p['p99']*1000:.0f} µs",
              loc="left")
axB.set_xlabel("turnaround (ms, log)")
axB.set_ylabel("ticks")
style_ax(axB)
axB.text(0.98, 0.95, f"max {cp.max():.2f} ms\n(never misses a tick)\n"
         "choi-run server CSVs not saved;\nsame binary as probe runs",
         transform=axB.transAxes, va="top", ha="right", fontsize=8.5, color=MUTED)

# --- C: loop-side timing percentiles per run ---
axC = fig.add_subplot(gs[1, 0])
labels, m50, m95, m99, u50, u95, u99 = [], [], [], [], [], [], []
tick_stats = []
for lab, _, _, _, kind in RUNS:
    d = rig(lab)
    labels.append(lab)
    mp = pct(d["mpc_ms"]); up = pct(d["in_to_udp_ms"])
    m50.append(mp["p50"]); m95.append(mp["p95"]); m99.append(mp["p99"])
    u50.append(up["p50"]); u95.append(up["p95"]); u99.append(up["p99"])
    err, _ = tick_err_ms(d)
    tick_stats.append((pct(err), float(err.max())))
y = np.arange(len(labels))[::-1]
axC.hlines(y + 0.17, m50, m99, color=GREY, lw=2, alpha=0.55)
axC.scatter(m50, y + 0.17, s=22, color=GREY, zorder=3, label="mpc_ms (apply reply)")
axC.hlines(y - 0.17, u50, u99, color=GREEN, lw=2, alpha=0.55)
axC.scatter(u50, y - 0.17, s=22, color=GREEN, zorder=3, label="in_to_udp_ms (full tick)")
axC.set_yticks(y)
axC.set_yticklabels(labels, fontsize=8)
axC.set_xlabel("ms  (dot = p50, bar to p99)")
axC.set_title("Loop-side work is negligible: p99 in→udp ≤ 0.13 ms on every run",
              loc="left")
axC.legend(loc="lower right")
style_ax(axC)
axC.grid(True, axis="x", color="#DDDDDD", lw=0.6)
axC.grid(False, axis="y")

# --- D: tick-period |error| per run ---
axD = fig.add_subplot(gs[1, 1])
e50 = [t[0]["p50"] for t in tick_stats]
e95 = [t[0]["p95"] for t in tick_stats]
e99 = [t[0]["p99"] for t in tick_stats]
emax = [t[1] for t in tick_stats]
colors = [RED if lab in ("opfit2",) else (AMBER if lab == "rnd1" else GREEN)
          for lab in labels]
axD.hlines(y, e50, e99, color=colors, lw=2, alpha=0.6)
axD.scatter(e50, y, s=22, c=colors, zorder=3)
axD.scatter(emax, y, marker="x", s=26, c=colors, zorder=3)
axD.set_yticks(y)
axD.set_yticklabels(labels, fontsize=8)
axD.set_xlabel("|tick period − 9.8304 ms|  (dot p50, bar to p99, x = max)")
axD.set_title("Tick jitter p99 < 1.9 ms except opfit2 (p99 6.3 ms)\n"
              "and one rnd1 stall (max 11.1 ms)", loc="left")
style_ax(axD)
axD.grid(True, axis="x", color="#DDDDDD", lw=0.6)
axD.grid(False, axis="y")

fig.suptitle("Latency: MATLAB MPC server is ~100× slower than the cpp Choi server "
             f"(p50 {ml_p['p50']:.2f} ms vs {cp_p['p50']*1000:.0f} µs); "
             "loop overhead stays under 0.13 ms",
             fontsize=12, fontweight="bold", color="black", x=0.09, ha="left", y=0.965)

save(fig, "eng_latency.png")

# stash numbers for eng_summary
import json
out = {
    "matlab_turnaround_ms": {**pct(ml), "max": round(float(ml.max()), 2),
                             "n": int(len(ml)),
                             "frac_over_tick": round(frac_over, 4)},
    "matlab_compute_ms": pct(np.concatenate([mlc1, mlc2])),
    "cpp_turnaround_ms": {**pct(cp), "max": round(float(cp.max()), 4), "n": int(len(cp)),
                          "note": "choi-run server CSVs not written; cpp stats from rnd1/rndhi probe runs (same binary)"},
    "cpp_compute_ms": pct(np.concatenate([cpc1, cpc2])),
    "p50_ratio_matlab_over_cpp": round(ratio, 1),
    "per_run_loop": {lab: {"mpc_ms": {"p50": m50[i], "p95": m95[i], "p99": m99[i]},
                           "in_to_udp_ms": {"p50": u50[i], "p95": u95[i], "p99": u99[i]},
                           "tick_err_ms": {**tick_stats[i][0], "max": round(tick_stats[i][1], 3)}}
                     for i, lab in enumerate(labels)},
}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lat.json"), "w") as f:
    json.dump(out, f, indent=1)
print("latency numbers stashed")
