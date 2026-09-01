"""Figure 1: event-triggered averages, sites x (arm,run) grid, achieved vs target."""
import json

import numpy as np
import sci_common as C

plt = C.style()

results = {}
data = {}
for arm, run in C.ARMS:
    data[(arm, run)] = (C.load_y8(arm, run), C.load_ref(run), C.load_schedule(run))

nrow, ncol = len(C.SITES), len(C.ARMS)
fig, axes = plt.subplots(nrow, ncol, figsize=(11.5, 12), sharex=True)
for j, (arm, run) in enumerate(C.ARMS):
    y8, ref, sched = data[(arm, run)]
    for i, site in enumerate(C.SITES):
        ax = axes[i, j]
        out = C.eta(y8, ref, sched, site)
        t, A, T, n, r = out
        ax.plot(t, T * 1e3, color=C.COL["grey"], lw=1.4, label="target")
        col = C.COL["green"] if arm == "MPC" else (C.COL["amber"] if arm == "Hold" else C.COL["green"])
        if arm == "Choi":
            col = C.COL["green"]
        if arm == "Hold":
            col = C.COL["red"]
        ax.plot(t, A * 1e3, color=col, lw=1.0, label="achieved (+2)")
        rtxt = "r=n/a" if np.isnan(r) else f"r={r:.2f}"
        ax.text(0.97, 0.92, f"{rtxt}  n={n}", transform=ax.transAxes, ha="right",
                va="top", fontsize=8)
        results[f"{arm}_{run}_{site}"] = dict(r_eta=None if np.isnan(r) else round(r, 3), n=n,
                                              tgt_peak_mV=round(float(T.max() * 1e3), 4),
                                              ach_peak_mV=round(float(A.max() * 1e3), 4))
        if i == 0:
            ax.set_title(f"{arm} {run}", fontsize=10)
        if j == 0:
            ax.set_ylabel(f"{site}\nΔ feature (mV)", fontsize=9)
        if i == nrow - 1:
            ax.set_xlabel("ticks from onset")
        ax.axvline(0, color=C.COL["grey"], lw=0.5, ls=":", alpha=0.6)
        ax.set_xlim(-30, 190)
        ax.tick_params(labelsize=8)
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False, fontsize=9,
           bbox_to_anchor=(0.99, 1.0))
fig.suptitle("Event-triggered averages: MPC and Choi reproduce touch-shaped targets at every site; "
             "Hold does not (sham targets near-flat)", fontsize=11, x=0.02, ha="left")
fig.tight_layout(rect=[0, 0, 1, 0.965])
fig.savefig(f"{C.OUT}/sci_event_gallery.png")

with open(f"{C.OUT}/scripts/_gallery.json", "w") as f:
    json.dump(results, f, indent=1)
print(json.dumps(results, indent=0))
