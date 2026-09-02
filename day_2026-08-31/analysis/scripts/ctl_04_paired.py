"""Q4: cleaned paired MPC-vs-Choi comparison. Same schedule events, artifact
ticks 0-2 excluded, each event scored at its own best lag (0..6). Does the
overnight "tie at best lag" conclusion survive window cleaning?"""
import json

import numpy as np
import sci_common as C
import ctl_common as X

plt = C.style()
LAGS = range(0, 7)


def best_lag_r(arm, run):
    """event -> (best r over lags, best lag), masked windows, real sites only."""
    sched = C.load_schedule(run)
    ref = C.load_ref(run)
    sig = X.y8(arm, run)
    out = {}
    for ev in sched["events"]:
        if ev["site"] not in C.REAL_SITES:
            continue
        o = ev["onset_tick"]
        ri = C.epoch_indices(o, len(ref), 0)
        if ri is None:
            continue
        t = ref[ri[0]:ri[1]]
        dt = t - t[:25].mean()
        best = (-np.inf, None)
        for lag in LAGS:
            yi = C.epoch_indices(o, len(sig), lag)
            if yi is None:
                continue
            a = sig[yi[0]:yi[1]]
            r = X.masked_r(dt, a - a[:25].mean())
            if np.isfinite(r) and r > best[0]:
                best = (r, lag)
        if best[1] is not None:
            out[ev["event"]] = best
    return out


pairs, lags_used = [], {"MPC": [], "Choi": []}
for run in ["r1", "r2"]:
    m = best_lag_r("MPC", run)
    c = best_lag_r("Choi", run)
    for e in sorted(set(m) & set(c)):
        pairs.append(dict(run=run, event=e, mpc=m[e][0], choi=c[e][0], dr=m[e][0] - c[e][0]))
        lags_used["MPC"].append(m[e][1])
        lags_used["Choi"].append(c[e][1])

d = np.array([p["dr"] for p in pairs])
mean, lo, hi = C.boot_ci(d, seed=40)
rng = np.random.default_rng(41)
perm = np.abs((d[None, :] * rng.choice([-1, 1], size=(20000, len(d)))).mean(axis=1))
pval = float((perm >= abs(d.mean())).mean())
win = float((d > 0).mean())

per_run = {}
for run in ["r1", "r2"]:
    dr = np.array([p["dr"] for p in pairs if p["run"] == run])
    mr, lor, hir = C.boot_ci(dr, seed=42)
    per_run[run] = dict(n=len(dr), mean_dr=round(mr, 4), ci=[round(lor, 4), round(hir, 4)],
                        winrate=round(float((dr > 0).mean()), 3))

# decomposition control: masked r at FIXED per-arm overnight lags (MPC +2,
# Choi r1 +1, Choi r2 +2) -> separates window-cleaning from lag freedom
fixed_ctrl = {}
for run, (lm, lc) in {"r1": (2, 1), "r2": (2, 2)}.items():
    rm = {r["event"]: r["r"] for r in X.event_epochs("MPC", run, lag=lm)}
    rc = {r["event"]: r["r"] for r in X.event_epochs("Choi", run, lag=lc)}
    dd = np.array([rm[e] - rc[e] for e in sorted(set(rm) & set(rc))])
    mf, lof, hif = C.boot_ci(dd, seed=50)
    fixed_ctrl[run] = dict(n=len(dd), mean_dr=round(mf, 4), ci=[round(lof, 4), round(hif, 4)])

# Hold-control noise floor: best-lag masked r for Hold events vs the r1 targets
hold = best_lag_r("Hold", "r1")
hold_r = np.array([v[0] for v in hold.values()])
hm, hlo, hhi = C.boot_ci(hold_r, seed=43)

mpc_r = np.array([p["mpc"] for p in pairs])
choi_r = np.array([p["choi"] for p in pairs])

# ---------- figure ----------
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3), gridspec_kw=dict(width_ratios=[1.1, 1]))
ax = axes[0]
ax.hist(d, bins=30, color=C.COL["green"], alpha=0.85, edgecolor="white")
ax.axvline(0, color=C.COL["grey"], lw=1)
ax.axvline(d.mean(), color="black", lw=1.4)
ax.axvspan(lo, hi, color=C.COL["green"], alpha=0.18)
ax.set_xlabel("Δr per event (MPC − Choi), artifact-excluded, per-event best lag")
ax.set_ylabel("events")
ax.text(0.02, 0.95,
        f"n={len(d)} paired events\nmean Δr = {mean:+.3f}\n95% CI [{lo:.3f}, {hi:.3f}]\n"
        f"p(perm) = {pval:.3f}\nMPC wins {win * 100:.0f}%\n"
        f"r1: {per_run['r1']['mean_dr']:+.3f} {per_run['r1']['ci']}\n"
        f"r2: {per_run['r2']['mean_dr']:+.3f} {per_run['r2']['ci']}",
        transform=ax.transAxes, va="top", fontsize=9)

ax = axes[1]
cols = {"r1": C.COL["green"], "r2": C.COL["amber"]}
for run in ["r1", "r2"]:
    sel = [i for i, p in enumerate(pairs) if p["run"] == run]
    ax.scatter(choi_r[sel], mpc_r[sel], s=10, color=cols[run], alpha=0.55,
               edgecolors="none", label=f"{run} (n={len(sel)})")
ax.plot([-0.2, 1], [-0.2, 1], color=C.COL["grey"], lw=1, ls=":")
ax.axvline(hm, color=C.COL["red"], lw=1, ls="--")
ax.axhline(hm, color=C.COL["red"], lw=1, ls="--")
ax.text(hm + 0.01, -0.15, f"Hold noise floor\nbest-lag r = {hm:.2f} [{hlo:.2f}, {hhi:.2f}]",
        fontsize=8, color=C.COL["red"])
ax.set_xlabel("Choi per-event best-lag r (masked)")
ax.set_ylabel("MPC per-event best-lag r (masked)")
ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.spines["left"].set_visible(True)

tie = lo <= 0 <= hi
verdict = "TIE survives cleaning" if tie else ("MPC ahead after cleaning" if lo > 0
                                               else "Choi ahead after cleaning")
ptxt = "p<0.0001" if pval < 1e-4 else f"p={pval:.3f}"
fig.suptitle(f"Cleaned paired test (artifact ticks excluded, per-event best lag):\n"
             f"Δr = {mean:+.3f} [{lo:.3f}, {hi:.3f}], {ptxt} — {verdict} "
             f"(overnight best-lag Δr was −0.001/−0.012)", fontsize=10.5)
fig.tight_layout(rect=[0, 0, 1, 0.90])
fig.savefig(f"{C.OUT}/ctl_paired_clean.png")

out = dict(n_pairs=len(d), mean_dr=round(mean, 4), ci=[round(lo, 4), round(hi, 4)],
           p_perm=pval, mpc_winrate=round(win, 3), per_run=per_run,
           median_best_lag=dict(MPC=float(np.median(lags_used["MPC"])),
                                Choi=float(np.median(lags_used["Choi"]))),
           mean_r=dict(MPC=round(float(mpc_r.mean()), 3), Choi=round(float(choi_r.mean()), 3)),
           hold_noise_floor=dict(n=len(hold_r), mean_bestlag_r=round(hm, 3),
                                 ci=[round(hlo, 3), round(hhi, 3)]),
           fixed_lag_masked_control=fixed_ctrl,
           verdict=verdict,
           note="masked r excludes ticks 0-2 post-onset; per-event best lag searched 0..6 "
                "independently per arm; Hold floor shows the optimism from best-lag selection")
with open(f"{X.SCR}/_ctl_q4.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
