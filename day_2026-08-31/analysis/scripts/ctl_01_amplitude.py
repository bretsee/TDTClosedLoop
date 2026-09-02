"""Q1: amplitude transfer. Regress per-event achieved peak (y8, baseline-sub,
artifact-excluded, lag-corrected) on the site's target peak, per arm/run."""
import json

import numpy as np
import sci_common as C
import ctl_common as X

plt = C.style()

ARMRUNS = [("MPC", "r1"), ("MPC", "r2"), ("Choi", "r1"), ("Choi", "r2"), ("Hold", "r1")]
res = {}
data = {}
RESP = (X.TREL >= 3) & (X.TREL <= 40)     # early-response window, artifact-free
for k, (arm, run) in enumerate(ARMRUNS):
    rows = X.event_epochs(arm, run)
    tx = np.array([r["tgt_peak"] for r in rows]) * 1e3   # mV
    ay = np.array([r["ach_peak"] for r in rows]) * 1e3
    mr = np.array([r["dy"][RESP].mean() for r in rows]) * 1e3
    sl, ic = X.ols(tx, ay)
    lo, hi, _ = X.boot_slope(tx, ay, seed=100 + k)
    pear = float(np.corrcoef(tx, ay)[0, 1])
    res[f"{arm}_{run}"] = dict(n=len(rows), slope=round(sl, 3), slope_ci=[round(lo, 3), round(hi, 3)],
                               intercept_mV=round(ic, 5), pearson_r=round(pear, 3))
    data[(arm, run)] = (tx, ay, mr)

# pooled per arm (runs combined) + MPC-vs-Choi slope difference by bootstrap
pooled = {}
boots = {}
for arm in ["MPC", "Choi"]:
    tx = np.concatenate([data[(arm, r)][0] for r in ["r1", "r2"]])
    ay = np.concatenate([data[(arm, r)][1] for r in ["r1", "r2"]])
    sl, ic = X.ols(tx, ay)
    lo, hi, sb = X.boot_slope(tx, ay, seed=77 if arm == "MPC" else 78)
    pooled[arm] = dict(n=len(tx), slope=round(sl, 3), slope_ci=[round(lo, 3), round(hi, 3)],
                       pearson_r=round(float(np.corrcoef(tx, ay)[0, 1]), 3))
    boots[arm] = sb
nb = min(len(boots["MPC"]), len(boots["Choi"]))
dsl = boots["MPC"][:nb] - boots["Choi"][:nb]
pooled["slope_diff_MPC_minus_Choi"] = dict(
    mean=round(float(np.mean(dsl)), 3),
    ci=[round(float(np.percentile(dsl, 2.5)), 3), round(float(np.percentile(dsl, 97.5)), 3)])

# supplementary: mean early response (ticks 3-40) vs target peak — less dominated
# than the epoch-max statistic by the noise floor that Hold reveals
meanresp = {}
for arm in ["MPC", "Choi", "Hold"]:
    runs = ["r1", "r2"] if arm != "Hold" else ["r1"]
    tx = np.concatenate([data[(arm, r)][0] for r in runs])
    mr = np.concatenate([data[(arm, r)][2] for r in runs])
    sl, ic = X.ols(tx, mr)
    lo, hi, _ = X.boot_slope(tx, mr, seed=200 + len(arm))
    meanresp[arm] = dict(slope=round(sl, 3), slope_ci=[round(lo, 3), round(hi, 3)],
                         pearson_r=round(float(np.corrcoef(tx, mr)[0, 1]), 3))
hold_floor = dict(mean_peak_mV=round(float(data[("Hold", "r1")][1].mean()), 4),
                  sd_mV=round(float(data[("Hold", "r1")][1].std()), 4))
tgt_range_mV = dict()
for run in ["r1", "r2"]:
    rows = X.event_epochs("MPC", run)
    per_site = {s: round(float(np.mean([r["tgt_peak"] for r in rows if r["site"] == s]) * 1e3), 4)
                for s in C.REAL_SITES}
    tgt_range_mV[run] = per_site

fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2), sharex=True, sharey=True)
panel = {"MPC": axes[0], "Choi": axes[1], "Hold": axes[2]}
colors = {"MPC": C.COL["green"], "Choi": C.COL["amber"], "Hold": C.COL["grey"]}
mk = {"r1": "o", "r2": "^"}
rng = np.random.default_rng(5)
xg = np.linspace(0, 0.45, 10)
for arm, run in ARMRUNS:
    ax = panel[arm]
    tx, ay, _mr = data[(arm, run)]
    jx = tx + rng.uniform(-0.006, 0.006, len(tx))
    ax.scatter(jx, ay, s=12, marker=mk[run], color=colors[arm], alpha=0.55,
               edgecolors="none", label=f"{run} (n={len(tx)})")
    sl = res[f"{arm}_{run}"]["slope"]
    ic = res[f"{arm}_{run}"]["intercept_mV"]
    ax.plot(xg, sl * xg + ic, color=colors[arm], lw=1.4,
            ls="-" if run == "r1" else "--")
for arm, ax in panel.items():
    ax.plot(xg, xg, color=C.COL["grey"], lw=1, ls=":", label="identity (gain 1)")
    ax.axhline(data[("Hold", "r1")][1].mean(), color=C.COL["red"], lw=1, ls="--",
               label="Hold noise floor" if arm == "MPC" else None)
    ax.set_xlabel("target peak (mV)")
    if arm == "MPC":
        ax.set_ylabel("achieved y8 peak (mV)")
    if arm == "Hold":
        s = res["Hold_r1"]
        ax.set_title(f"Hold control: slope {s['slope']:.2f} "
                     f"[{s['slope_ci'][0]:.2f}, {s['slope_ci'][1]:.2f}] — flat, as it must be",
                     fontsize=9.5)
    else:
        p = pooled[arm]
        ax.set_title(f"{arm}: pooled slope {p['slope']:.2f} "
                     f"[{p['slope_ci'][0]:.2f}, {p['slope_ci'][1]:.2f}], r={p['pearson_r']:.2f}",
                     fontsize=9.5)
    ax.legend(fontsize=8, frameon=False, loc="upper left")

d = pooled["slope_diff_MPC_minus_Choi"]


def slope_verdict(p):
    lo_, hi_ = p["slope_ci"]
    if lo_ > 0 and hi_ < 1:
        return "partial"
    if lo_ <= 0:
        return "absent"
    return "present"


fig.suptitle(
    f"Amplitude transfer is {slope_verdict(pooled['MPC'])} for MPC "
    f"(slope {pooled['MPC']['slope']:.2f} {pooled['MPC']['slope_ci']}) and "
    f"{slope_verdict(pooled['Choi'])} for Choi ({pooled['Choi']['slope']:.2f} "
    f"{pooled['Choi']['slope_ci']}) — cleaned peaks sit near the Hold noise floor "
    f"({hold_floor['mean_peak_mV']:.2f} mV)", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(f"{C.OUT}/ctl_amplitude_transfer.png")

# Spearman (rank) transfer per arm as honesty check on monotonicity
from scipy.stats import spearmanr  # noqa: E402
for arm in ["MPC", "Choi", "Hold"]:
    runs = ["r1", "r2"] if arm != "Hold" else ["r1"]
    tx = np.concatenate([data[(arm, r)][0] for r in runs])
    ay = np.concatenate([data[(arm, r)][1] for r in runs])
    rho, p = spearmanr(tx, ay)
    (pooled if arm != "Hold" else res).setdefault(arm if arm != "Hold" else "Hold_r1", {})
    tgtd = pooled.get(arm) if arm != "Hold" else res["Hold_r1"]
    tgtd["spearman_rho"] = round(float(rho), 3)
    tgtd["spearman_p"] = float(p)

out = dict(per_arm_run=res, pooled=pooled,
           meanresp_slope_ticks3to40=meanresp, hold_peak_noise_floor=hold_floor,
           site_target_peaks_mV=tgt_range_mV,
           note="peaks in mV, artifact ticks 0-2 excluded, per-arm best lag; "
                "slope CI = 5000x bootstrap over events; epoch-max peak is partly a "
                "noise-max statistic (see Hold floor), mean-response slope supplements it")
with open(f"{X.SCR}/_ctl_q1.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
