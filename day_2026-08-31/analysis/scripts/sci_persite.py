"""Figure 2: per-site distributions of per-event r (lag +2) and peak ratio, MPC vs Choi."""
import csv
import json

import numpy as np
import sci_common as C

plt = C.style()

rows = list(csv.DictReader(open(f"{C.OUT}/scripts/_per_event_metrics.csv")))
for r in rows:
    for k in ("r0", "rlag", "peak_ratio", "tgt_peak", "ach_peak", "ach_absmod", "ach_max_raw", "rmse"):
        r[k] = float(r[k]) if r[k] not in ("", "nan") else np.nan


def sel(arm, site, key, run=None):
    return np.array([r[key] for r in rows
                     if r["arm"] == arm and r["site"] == site and (run is None or r["run"] == run)])


summary = {}
for arm in ["MPC", "Choi", "Hold"]:
    for run in ["r1", "r2"]:
        if (arm, run) not in C.CAPTURES:
            continue
        for site in C.SITES:
            rl = sel(arm, site, "rlag", run)
            pr = sel(arm, site, "peak_ratio", run)
            if len(rl) == 0:
                continue
            m, lo, hi = C.boot_ci(rl)
            mp, lop, hip = C.boot_ci(pr)
            summary[f"{arm}_{run}_{site}"] = dict(
                n=len(rl), rlag_mean=round(m, 3), rlag_ci=[round(lo, 3), round(hi, 3)],
                peak_ratio_mean=None if np.isnan(mp) else round(mp, 3),
                peak_ratio_ci=None if np.isnan(mp) else [round(lop, 3), round(hip, 3)])

fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.5), sharex=True)
rng = np.random.default_rng(1)
site_order = C.REAL_SITES + ["SHAM"]
for ax, key, ylab in [(axes[0], "rlag", "per-event r (lag +2)"),
                      (axes[1], "peak_ratio", "per-event peak ratio (achieved/target)")]:
    for si, site in enumerate(site_order):
        if key == "peak_ratio" and site == "SHAM":
            continue
        for k, (arm, col) in enumerate([("MPC", C.COL["green"]), ("Choi", C.COL["grey"])]):
            x0 = si + (-0.19 + 0.38 * k)
            v = sel(arm, site, key)
            v = v[~np.isnan(v)]
            bp = ax.boxplot(v, positions=[x0], widths=0.28, showfliers=False,
                            medianprops=dict(color="black", lw=1.2),
                            boxprops=dict(color=col), whiskerprops=dict(color=col),
                            capprops=dict(color=col))
            ax.scatter(x0 + rng.uniform(-0.08, 0.08, len(v)), v, s=6, color=col, alpha=0.45,
                       edgecolors="none", zorder=3)
    ax.set_ylabel(ylab)
    ax.set_xticks(range(len(site_order)))
    ax.set_xticklabels(site_order)
# reference lines
hold_r = np.array([r["rlag"] for r in rows if r["arm"] == "Hold" and r["site"] != "SHAM"])
axes[0].axhline(np.nanmean(hold_r), color=C.COL["red"], lw=1, ls="--")
axes[0].text(len(site_order) - 0.55, np.nanmean(hold_r) + 0.03, "Hold (tonic) floor",
             color=C.COL["red"], fontsize=8, ha="right")
axes[1].axhline(1.0, color=C.COL["amber"], lw=1, ls="--")
axes[1].text(len(site_order) - 1.55, 1.05, "perfect peak match", color=C.COL["amber"], fontsize=8)
import matplotlib.patches as mpatches
axes[0].legend(handles=[mpatches.Patch(color=C.COL["green"], label="MPC (runs pooled)"),
                        mpatches.Patch(color=C.COL["grey"], label="Choi (runs pooled)")],
               frameon=False, loc="lower left")

mpc_all = np.array([r["rlag"] for r in rows if r["arm"] == "MPC" and r["site"] != "SHAM"])
choi_all = np.array([r["rlag"] for r in rows if r["arm"] == "Choi" and r["site"] != "SHAM"])
fig.suptitle(f"Per-event tracking by site: MPC median r={np.nanmedian(mpc_all):.2f} vs "
             f"Choi {np.nanmedian(choi_all):.2f}; single-tick peaks overshoot ~2x (MPC 2.3, Choi 2.0); "
             "SHAM r ~0 for both (tiny sham targets not tracked)", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(f"{C.OUT}/sci_persite_scores.png")

# pooled arm-level numbers
for arm in ["MPC", "Choi", "Hold"]:
    v = np.array([r["rlag"] for r in rows if r["arm"] == arm and r["site"] != "SHAM"])
    p = np.array([r["peak_ratio"] for r in rows if r["arm"] == arm and r["site"] != "SHAM"])
    m, lo, hi = C.boot_ci(v)
    mp, lop, hip = C.boot_ci(p)
    summary[f"{arm}_pooled_real"] = dict(n=len(v), rlag_mean=round(m, 3), rlag_ci=[round(lo, 3), round(hi, 3)],
                                         rlag_median=round(float(np.nanmedian(v)), 3),
                                         peak_ratio_mean=round(mp, 3), peak_ratio_ci=[round(lop, 3), round(hip, 3)],
                                         peak_ratio_median=round(float(np.nanmedian(p)), 3))

with open(f"{C.OUT}/scripts/_persite.json", "w") as f:
    json.dump(summary, f, indent=1)
print(json.dumps({k: v for k, v in summary.items() if "pooled" in k}, indent=1))
