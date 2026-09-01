"""Figure 5: SHAM catch trials — modulation on sham vs real events, false-touch rate vs threshold."""
import csv
import json

import numpy as np
import sci_common as C

plt = C.style()

rows = list(csv.DictReader(open(f"{C.OUT}/scripts/_per_event_metrics.csv")))
for r in rows:
    for k in ("ach_absmod", "ach_max_raw", "tgt_peak", "ach_peak"):
        r[k] = float(r[k])

arms = ["MPC", "Choi", "Hold"]


def grab(arm, sham, key):
    want = "SHAM" if sham else "real"
    return np.array([r[key] for r in rows if r["arm"] == arm and
                     ((r["site"] == "SHAM") == sham)])


out = {}
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3), gridspec_kw=dict(width_ratios=[1.2, 1]))

# Panel A: peak modulation distributions, sham vs real, per arm
ax = axes[0]
rng = np.random.default_rng(5)
xt, xl = [], []
for i, arm in enumerate(arms):
    for k, sham in enumerate([False, True]):
        v = grab(arm, sham, "ach_absmod") * 1e3
        x0 = i * 2.4 + k
        col = (C.COL["grey"] if sham else C.COL["green"]) if arm != "Hold" else C.COL["red"]
        ax.boxplot(v, positions=[x0], widths=0.7, showfliers=False,
                   medianprops=dict(color="black"), boxprops=dict(color=col),
                   whiskerprops=dict(color=col), capprops=dict(color=col))
        ax.scatter(x0 + rng.uniform(-0.2, 0.2, len(v)), v, s=6, color=col, alpha=0.5,
                   edgecolors="none", zorder=3)
        xt.append(x0)
        xl.append(f"{arm}\n{'sham' if sham else 'real'}")
        out[f"{arm}_{'sham' if sham else 'real'}_absmod_mV"] = dict(
            n=len(v), median=round(float(np.median(v)), 4),
            mean=round(float(v.mean()), 4), p90=round(float(np.percentile(v, 90)), 4))
ax.set_yscale("log")
ax.set_xticks(xt)
ax.set_xticklabels(xl, fontsize=8)
ax.set_ylabel("peak |Δ feature| in event window (mV, log)")
sep_mpc = out["MPC_real_absmod_mV"]["median"] / out["MPC_sham_absmod_mV"]["median"]
sep_choi = out["Choi_real_absmod_mV"]["median"] / out["Choi_sham_absmod_mV"]["median"]
ax.set_title(f"Real/sham modulation separation: MPC {sep_mpc:.0f}x, Choi {sep_choi:.0f}x", fontsize=10)

# Panel B: detection statistic = mean raw y8 over the 21-tick pulse window (lag-corrected).
# With the given SHAM threshold this separates real from sham cleanly; raw single-tick peaks do not
# (spontaneous transients cross it ~100% of the time even under tonic Hold).
def pulse_means(arm):
    sham_v, real_v = [], []
    for run in ["r1", "r2"]:
        if (arm, run) not in C.CAPTURES:
            continue
        y8 = C.load_y8(arm, run)
        sched = C.load_schedule(run)
        for ev in sched["events"]:
            i = ev["onset_tick"] - 1 + C.LAG
            if i + 190 > len(y8):
                continue
            (sham_v if ev["site"] == "SHAM" else real_v).append(float(y8[i:i + 21].mean()))
    return np.array(sham_v), np.array(real_v)


ax = axes[1]
bars = []
for arm in arms:
    sham_pm, real_pm = pulse_means(arm)
    fa = float((sham_pm > C.SHAM_THRESHOLD).mean())
    hit = float((real_pm > C.SHAM_THRESHOLD).mean())
    out[f"{arm}_false_touch_rate"] = dict(rate=round(fa, 3), n=len(sham_pm),
                                          k=int((sham_pm > C.SHAM_THRESHOLD).sum()),
                                          statistic="mean raw y8 over 21-tick pulse window, lag +2")
    out[f"{arm}_real_hit_rate"] = dict(rate=round(hit, 3), n=len(real_pm))
    pooled_sd = np.sqrt((sham_pm.var(ddof=1) + real_pm.var(ddof=1)) / 2)
    out[f"{arm}_dprime"] = round(float((real_pm.mean() - sham_pm.mean()) / pooled_sd), 2)
    bars.append((arm, hit, fa))
x = np.arange(len(arms))
ax.bar(x - 0.19, [b[1] for b in bars], width=0.38, color=C.COL["green"], label="real events > threshold (hit)")
ax.bar(x + 0.19, [b[2] for b in bars], width=0.38, color=C.COL["red"], label="sham events > threshold (false touch)")
for i, (arm, hit, fa) in enumerate(bars):
    ax.text(i - 0.19, hit + 0.02, f"{hit * 100:.0f}%", ha="center", fontsize=8)
    ax.text(i + 0.19, fa + 0.02, f"{fa * 100:.0f}%", ha="center", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels(arms)
ax.set_ylim(0, 1.12)
ax.set_ylabel(f"fraction of events over threshold\n(pulse-window mean > {C.SHAM_THRESHOLD:.3e} V)")
ax.legend(frameon=False, fontsize=8, loc="center right")
ax.set_title("Detection readout: pulse-window mean vs SHAM threshold", fontsize=10)

mfa = out["MPC_false_touch_rate"]["rate"] * 100
cfa = out["Choi_false_touch_rate"]["rate"] * 100
mh = out["MPC_real_hit_rate"]["rate"] * 100
ch = out["Choi_real_hit_rate"]["rate"] * 100
fig.suptitle(f"SHAM catch trials: false-touch rate MPC {mfa:.0f}%, Choi {cfa:.0f}% "
             f"(Hold base rate {out['Hold_false_touch_rate']['rate'] * 100:.0f}%); "
             f"real-event hits MPC {mh:.0f}%, Choi {ch:.0f}%", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(f"{C.OUT}/sci_sham.png")

# note: sham targets are not perfectly flat (small bump); quantify how big
tgt_sham = np.array([r["tgt_peak"] for r in rows if r["site"] == "SHAM" and r["arm"] == "MPC"]) * 1e3
tgt_real = np.array([r["tgt_peak"] for r in rows if r["site"] != "SHAM" and r["arm"] == "MPC"]) * 1e3
out["sham_target_peak_mV"] = dict(median=round(float(np.median(tgt_sham)), 4))
out["real_target_peak_mV"] = dict(median=round(float(np.median(tgt_real)), 4))
with open(f"{C.OUT}/scripts/_sham.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
