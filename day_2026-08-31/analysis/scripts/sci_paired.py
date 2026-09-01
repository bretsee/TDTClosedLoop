"""Figure 3: paired per-event test. Same schedule, same event index -> MPC r minus Choi r."""
import csv
import json

import numpy as np
import sci_common as C

plt = C.style()

rows = list(csv.DictReader(open(f"{C.OUT}/scripts/_per_event_metrics.csv")))
tab = {}
for r in rows:
    tab[(r["arm"], r["run"], int(r["event"]))] = r

pairs = []  # (run, event, site, dr)
for run in ["r1", "r2"]:
    for ev in range(1, 101):
        a = tab.get(("MPC", run, ev))
        b = tab.get(("Choi", run, ev))
        if a is None or b is None or a["site"] == "SHAM":
            continue
        dr = float(a["rlag"]) - float(b["rlag"])
        pairs.append(dict(run=run, event=ev, site=a["site"], dr=dr,
                          mpc=float(a["rlag"]), choi=float(b["rlag"])))

d = np.array([p["dr"] for p in pairs])
m, lo, hi = C.boot_ci(d, seed=2)
# sign-flip permutation p-value
rng = np.random.default_rng(3)
perm = np.abs((d[None, :] * rng.choice([-1, 1], size=(20000, len(d)))).mean(axis=1))
pval = float((perm >= abs(d.mean())).mean())
cohen_d = float(d.mean() / d.std(ddof=1))
winrate = float((d > 0).mean())

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2),
                         gridspec_kw=dict(width_ratios=[1.15, 1]))
ax = axes[0]
ax.hist(d, bins=30, color=C.COL["green"], alpha=0.85, edgecolor="white")
ax.axvline(0, color=C.COL["grey"], lw=1)
ax.axvline(d.mean(), color="black", lw=1.4)
ax.axvspan(lo, hi, color=C.COL["green"], alpha=0.18)
ax.set_xlabel("Δr per event  (MPC − Choi, lag +2)")
ax.set_ylabel("events")
ax.text(0.02, 0.95, f"n={len(d)} paired events\nmean Δr = {d.mean():.3f}\n"
        f"95% CI [{lo:.3f}, {hi:.3f}]\np(perm) = {pval:.4f}\nCohen d = {cohen_d:.2f}\n"
        f"MPC wins {winrate * 100:.0f}% of events", transform=ax.transAxes, va="top", fontsize=9)

ax = axes[1]
per_site = {}
for si, site in enumerate(C.REAL_SITES):
    ds = np.array([p["dr"] for p in pairs if p["site"] == site])
    ms, los, his = C.boot_ci(ds, seed=4 + si)
    per_site[site] = dict(n=len(ds), mean_dr=round(ms, 3), ci=[round(los, 3), round(his, 3)])
    col = C.COL["green"] if los > 0 else (C.COL["amber"] if ms > 0 else C.COL["red"])
    ax.errorbar(ms, si, xerr=[[ms - los], [his - ms]], fmt="o", color=col, capsize=3, ms=5)
    ax.scatter(ds, si + rng.uniform(-0.16, 0.16, len(ds)), s=6, color=C.COL["grey"],
               alpha=0.4, edgecolors="none")
ax.axvline(0, color=C.COL["grey"], lw=1)
ax.set_yticks(range(len(C.REAL_SITES)))
ax.set_yticklabels(C.REAL_SITES)
ax.set_xlabel("Δr per event (MPC − Choi), mean ± 95% CI by site")
ax.spines["left"].set_visible(True)

# --- control: per-arm best lag (Choi r1 responds at +1, not +2; forcing +2 penalizes it) ---
def per_event_r_lag(arm, run, lag):
    y8 = C.load_y8(arm, run)
    ref = C.load_ref(run)
    sched = C.load_schedule(run)
    res = {}
    for ev in sched["events"]:
        if ev["site"] == "SHAM":
            continue
        o = ev["onset_tick"]
        ri = C.epoch_indices(o, len(ref), 0)
        yi = C.epoch_indices(o, len(y8), lag)
        if ri is None or yi is None:
            continue
        t = ref[ri[0]:ri[1]]
        a = y8[yi[0]:yi[1]]
        dt, da = t - t[:25].mean(), a - a[:25].mean()
        if dt.std() > 1e-12 and da.std() > 1e-12:
            res[ev["event"]] = float(np.corrcoef(dt, da)[0, 1])
    return res


dbl = []
for run, choi_lag in [("r1", 1), ("r2", 2)]:
    m = per_event_r_lag("MPC", run, 2)
    c = per_event_r_lag("Choi", run, choi_lag)
    dbl += [m[e] - c[e] for e in m if e in c]
dbl = np.array(dbl)
mb, lob, hib = C.boot_ci(dbl, seed=11)
permb = np.abs((dbl[None, :] * rng.choice([-1, 1], size=(20000, len(dbl)))).mean(axis=1))
pvalb = float((permb >= abs(dbl.mean())).mean())
axes[0].text(0.02, 0.42, "control: each arm at its own\nbest lag (Choi r1 = +1):\n"
             f"Δr = {mb:+.3f} [{lob:.3f}, {hib:.3f}]\np = {pvalb:.2f}  →  TIE",
             transform=axes[0].transAxes, va="top", fontsize=9, color=C.COL["red"])

d1 = np.array([p["dr"] for p in pairs if p["run"] == "r1"])
d2 = np.array([p["dr"] for p in pairs if p["run"] == "r2"])
verdict = ("MPC beats Choi" if lo > 0 else ("Choi beats MPC" if hi < 0 else "no significant difference"))
fig.suptitle(f"Paired test at common lag +2: MPC ahead (Δr {d.mean():+.3f}, n={len(d)}) — but the r1 gap "
             f"is Choi's shorter latency (+1); at per-arm best lag the arms TIE (Δr {mb:+.3f}, p={pvalb:.2f})",
             fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(f"{C.OUT}/sci_paired.png")

# per-run split for JSON honesty
per_run = {}
for run in ["r1", "r2"]:
    dr = np.array([p["dr"] for p in pairs if p["run"] == run])
    mr, lor, hir = C.boot_ci(dr, seed=10)
    per_run[run] = dict(n=len(dr), mean_dr=round(mr, 3), ci=[round(lor, 3), round(hir, 3)],
                        winrate=round(float((dr > 0).mean()), 3))

out = dict(n_pairs=len(d), mean_dr=round(float(d.mean()), 4), ci=[round(lo, 4), round(hi, 4)],
           p_perm=pval, cohen_d=round(cohen_d, 3), mpc_winrate=round(winrate, 3),
           per_site=per_site, per_run=per_run, verdict_common_lag2=verdict,
           best_lag_control=dict(
               note="Choi r1 scored at its best lag +1, Choi r2 and MPC at +2",
               n=len(dbl), mean_dr=round(float(dbl.mean()), 4),
               ci=[round(lob, 4), round(hib, 4)], p_perm=pvalb,
               mpc_winrate=round(float((dbl > 0).mean()), 3),
               verdict="tie" if (lob <= 0 <= hib) else ("MPC" if lob > 0 else "Choi")),
           verdict="At matched latency the arms tie on shape fidelity; the common-lag(+2) MPC "
                   "advantage in r1 reflects Choi's shorter (+1) latency there.")
with open(f"{C.OUT}/scripts/_paired.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
