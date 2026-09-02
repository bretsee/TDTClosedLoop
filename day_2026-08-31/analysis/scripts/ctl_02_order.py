"""Q2: order effects / adaptation. (A) does a real-site event after a SAME-site
event differ from one after a DIFFERENT-site event? (B) lag-1 autocorrelation
of per-event residuals (site means removed) + 1000x order-shuffle permutation.
Hold control included as null everywhere."""
import json

import numpy as np
import sci_common as C
import ctl_common as X

plt = C.style()
rng = np.random.default_rng(20)

ARMRUNS = [("MPC", "r1"), ("MPC", "r2"), ("Choi", "r1"), ("Choi", "r2"), ("Hold", "r1")]


def sequences(arm, run):
    """All events in schedule order (real + SHAM) with masked metrics and prev-site tag."""
    rows = X.event_epochs(arm, run, real_only=False)
    rows.sort(key=lambda r: r["event"])
    for i, r in enumerate(rows):
        r["prev_site"] = rows[i - 1]["site"] if i > 0 else None
    return rows


def residuals(rows, key):
    """Residual of metric `key` after removing the (scheduled) site mean, in event order."""
    vals = np.array([r[key] for r in rows], float)
    sites = np.array([r["site"] for r in rows])
    res = np.full(len(vals), np.nan)
    for s in np.unique(sites):
        m = sites == s
        res[m] = vals[m] - np.nanmean(vals[m])
    return res


summary = {}
ab_data = {}
for arm, run in ARMRUNS:
    rows = sequences(arm, run)
    real = [r for r in rows if r["site"] in C.REAL_SITES and r["prev_site"] is not None]
    # A: same-site vs different-site predecessor, on site-mean residuals (peak and r)
    res_pk = residuals(rows, "ach_peak")
    res_r = residuals(rows, "r")
    idx = {r["event"]: i for i, r in enumerate(rows)}
    same_pk, diff_pk, same_r, diff_r = [], [], [], []
    for r in real:
        i = idx[r["event"]]
        (same_pk if r["prev_site"] == r["site"] else diff_pk).append(res_pk[i])
        (same_r if r["prev_site"] == r["site"] else diff_r).append(res_r[i])
    same_pk, diff_pk = np.array(same_pk), np.array(diff_pk)
    same_r, diff_r = np.array(same_r), np.array(diff_r)

    def perm_diff(a, b, nperm=10000, seed=1):
        obs = np.nanmean(a) - np.nanmean(b)
        pool = np.concatenate([a, b])
        pool = pool[~np.isnan(pool)]
        g = np.random.default_rng(seed)
        cnt = 0
        for _ in range(nperm):
            g.shuffle(pool)
            if abs(pool[:len(a)].mean() - pool[len(a):].mean()) >= abs(obs):
                cnt += 1
        return float(obs), float(cnt / nperm)

    d_pk, p_pk = perm_diff(same_pk, diff_pk, seed=2)
    d_r, p_r = perm_diff(same_r, diff_r, seed=3)

    # B: lag-1 autocorrelation of residual sequence (real-site events, event order)
    ridx = [idx[r["event"]] for r in rows if r["site"] in C.REAL_SITES]
    seq = res_pk[ridx]
    seq = seq[~np.isnan(seq)]

    def lag1(x):
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    ac = lag1(seq)
    null = np.array([lag1(rng.permutation(seq)) for _ in range(1000)])
    p_ac = float((np.abs(null) >= abs(ac)).mean())

    summary[f"{arm}_{run}"] = dict(
        n_same=int(len(same_pk)), n_diff=int(len(diff_pk)),
        same_minus_diff_peak_mV=round(d_pk * 1e3, 5), p_perm_peak=p_pk,
        same_minus_diff_r=round(d_r, 4), p_perm_r=p_r,
        lag1_autocorr_peak_resid=round(ac, 3), p_perm_autocorr=p_ac,
        null95=[round(float(np.percentile(null, 2.5)), 3),
                round(float(np.percentile(null, 97.5)), 3)])
    ab_data[(arm, run)] = (same_pk * 1e3, diff_pk * 1e3, ac, null)

# ---------- figure ----------
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), gridspec_kw=dict(width_ratios=[1.2, 1]))
ax = axes[0]
cols = {"MPC": C.COL["green"], "Choi": C.COL["amber"], "Hold": C.COL["grey"]}
for i, (arm, run) in enumerate(ARMRUNS):
    s, d, _, _ = ab_data[(arm, run)]
    for off, grp, filled in [(-0.16, s, True), (0.16, d, False)]:
        m = np.nanmean(grp)
        se = np.nanstd(grp) / np.sqrt(max(len(grp), 1))
        ax.errorbar(i + off, m, yerr=1.96 * se, fmt="o", ms=6, capsize=3,
                    color=cols[arm], markerfacecolor=cols[arm] if filled else "white")
        ax.scatter(np.full(len(grp), i + off) + rng.uniform(-0.05, 0.05, len(grp)),
                   grp, s=6, color=cols[arm], alpha=0.3, edgecolors="none")
ax.axhline(0, color=C.COL["grey"], lw=0.8)
for i, (arm, run) in enumerate(ARMRUNS):
    st = summary[f"{arm}_{run}"]
    ax.text(i, 0.98, f"p={st['p_perm_peak']:.2f}", ha="center", va="top",
            fontsize=8, transform=ax.get_xaxis_transform())
ax.set_xticks(range(len(ARMRUNS)))
ax.set_xticklabels([f"{a} {r}" for a, r in ARMRUNS])
ax.set_ylabel("peak residual after site-mean removal (mV)")
ax.set_title("A  filled = after SAME-site event, open = after DIFFERENT-site event\n"
             "(peak residuals; permutation p at top; n_same only 2-3 per run — underpowered)",
             fontsize=9.5, loc="left")

ax = axes[1]
for i, (arm, run) in enumerate(ARMRUNS):
    _, _, ac, null = ab_data[(arm, run)]
    lo, hi = np.percentile(null, [2.5, 97.5])
    ax.vlines(i, lo, hi, color=C.COL["grey"], lw=6, alpha=0.35)
    st = summary[f"{arm}_{run}"]
    sig = st["p_perm_autocorr"] < 0.05
    ax.plot(i, ac, "o", ms=7, color=C.COL["red"] if sig else cols[arm])
    ax.text(i, hi + 0.02, f"p={st['p_perm_autocorr']:.2f}", ha="center", fontsize=8)
ax.axhline(0, color=C.COL["grey"], lw=0.8)
ax.set_xticks(range(len(ARMRUNS)))
ax.set_xticklabels([f"{a} {r}" for a, r in ARMRUNS])
ax.set_ylabel("lag-1 autocorrelation of peak residuals")
ax.set_title("B  lag-1 autocorrelation vs 1000x order-shuffle null (grey band = null 95%)",
             fontsize=9.5, loc="left")

n_sig_a = sum(1 for k, v in summary.items() if v["p_perm_peak"] < 0.05)
n_sig_b = sum(1 for k, v in summary.items() if v["p_perm_autocorr"] < 0.05)
fig.suptitle(f"Order effects: {n_sig_a}/5 arm-runs show a same-site predecessor effect, "
             f"{n_sig_b}/5 show significant lag-1 residual autocorrelation", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(f"{C.OUT}/ctl_order_effects.png")

with open(f"{X.SCR}/_ctl_q2.json", "w") as f:
    json.dump(summary, f, indent=1)
print(json.dumps(summary, indent=1))
