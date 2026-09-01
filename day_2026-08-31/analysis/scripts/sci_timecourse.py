"""Figure 4: per-event tracking vs event number — within-run adaptation / decay, Hold noise band.

Also decomposes the 'Choi r1->r2 decay' claim: global r0 fell r1->r2 while lag+2 per-event r rose,
so we plot both r0 and rlag trends for Choi.
"""
import csv
import json

import numpy as np
import sci_common as C

plt = C.style()

rows = list(csv.DictReader(open(f"{C.OUT}/scripts/_per_event_metrics.csv")))
for r in rows:
    r["event"] = int(r["event"])
    r["rlag"] = float(r["rlag"])
    r["r0"] = float(r["r0"])


def series(arm, run, key="rlag", real_only=True):
    s = [(r["event"], r[key]) for r in rows
         if r["arm"] == arm and r["run"] == run and (not real_only or r["site"] != "SHAM")]
    s.sort()
    return np.array([e for e, _ in s]), np.array([v for _, v in s])


def runmed(x, y, w=9):
    out = np.array([np.nanmedian(y[max(0, i - w // 2):i + w // 2 + 1]) for i in range(len(y))])
    return out


hold_e, hold_v = series("Hold", "r1")
h_mean, h_lo, h_hi = C.boot_ci(hold_v)
h_sd = float(np.nanstd(hold_v))

fig, axes = plt.subplots(2, 2, figsize=(11.5, 7), sharey="row")
panels = [("MPC", "r1", axes[0, 0]), ("MPC", "r2", axes[0, 1]),
          ("Choi", "r1", axes[1, 0]), ("Choi", "r2", axes[1, 1])]
slopes = {}
for arm, run, ax in panels:
    e, v = series(arm, run)
    e0, v0 = series(arm, run, "r0")
    ax.axhspan(h_mean - 2 * h_sd, h_mean + 2 * h_sd, color=C.COL["red"], alpha=0.10, lw=0)
    ax.axhline(h_mean, color=C.COL["red"], lw=0.8, ls="--")
    ax.scatter(e, v, s=8, color=C.COL["green"], alpha=0.5, edgecolors="none", label="per-event r (lag +2)")
    ax.plot(e, runmed(e, v), color=C.COL["green"], lw=1.6)
    ax.scatter(e0, v0, s=8, color=C.COL["grey"], alpha=0.35, edgecolors="none", label="per-event r (lag 0)")
    ax.plot(e0, runmed(e0, v0), color=C.COL["grey"], lw=1.2)
    # linear trend on lag+2
    A = np.polyfit(e, v, 1)
    slope_per_100 = A[0] * 100
    # bootstrap CI on slope
    rng = np.random.default_rng(7)
    bs = []
    for _ in range(3000):
        idx = rng.integers(0, len(e), len(e))
        bs.append(np.polyfit(e[idx], v[idx], 1)[0] * 100)
    lo_s, hi_s = np.percentile(bs, [2.5, 97.5])
    slopes[f"{arm}_{run}"] = dict(
        slope_r_per_100events=round(float(slope_per_100), 3),
        slope_ci=[round(float(lo_s), 3), round(float(hi_s), 3)],
        mean_rlag_first20=round(float(np.nanmean(v[:20])), 3),
        mean_rlag_last20=round(float(np.nanmean(v[-20:])), 3),
        mean_r0_first20=round(float(np.nanmean(v0[:20])), 3),
        mean_r0_last20=round(float(np.nanmean(v0[-20:])), 3))
    sig = "" if lo_s <= 0 <= hi_s else " *"
    ax.set_title(f"{arm} {run}: slope {slope_per_100:+.2f} r/100 events "
                 f"[{lo_s:+.2f},{hi_s:+.2f}]{sig}", fontsize=10)
    ax.set_xlabel("event number")
    if ax in (axes[0, 0], axes[1, 0]):
        ax.set_ylabel("per-event r (real sites)")
    ax.set_ylim(-0.4, 1.0)
axes[0, 0].legend(frameon=False, fontsize=8, loc="lower left")
axes[0, 1].text(0.98, 0.05, "red band: Hold (tonic) noise floor ±2SD", color=C.COL["red"],
                fontsize=8, ha="right", transform=axes[0, 1].transAxes)
fig.suptitle("Within-run timecourse: MPC holds or improves (r2 +0.14*/100 ev, warm-up); Choi decays "
             "(r2 -0.13*); Choi r2 also lags more (lag-0 vs lag+2 gap)", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(f"{C.OUT}/sci_timecourse.png")

out = dict(hold_floor=dict(mean=round(h_mean, 4), sd=round(h_sd, 4), n=len(hold_v)), slopes=slopes)
with open(f"{C.OUT}/scripts/_timecourse.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
