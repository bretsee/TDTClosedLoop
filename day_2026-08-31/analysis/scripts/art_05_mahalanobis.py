"""Mahalanobis site-identity analysis on artifact-cleaned arm data.

Identical spec to spat_03: 10-40 ms window, ch 27 dropped (31 dims), LW-regularized
pooled covariance from touch trials (here: bandpass-matched touch_bp caches).
Writes art_mahalanobis.png and merges deltas into art_summary.json.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac
from scipy import stats

plt = sc.style()
CACHE = ac.CACHE
fs = ac.FS_LO
good = np.array([c for c in range(32) if c not in sc.BLACKLIST_CH])
ARM_SITES = ["D1", "D2", "D3", "P2", "LP"]


def vecs(trials, n_pre):
    a = n_pre + int(round(0.010 * fs))
    b = n_pre + int(round(0.040 * fs))
    return trials[:, good, a:b].mean(axis=2)


touch_V = {}
for site in sc.SITE_ORDER:
    z = np.load(os.path.join(CACHE, f"touch_{site}_bp.npz"))
    touch_V[site] = vecs(z["trials"].astype(float), int(z["n_pre"]))
mus = {s: v.mean(axis=0) for s, v in touch_V.items()}

X = np.concatenate([touch_V[s] - mus[s] for s in sc.SITE_ORDER])
n, p = X.shape
S = X.T @ X / n
m = np.trace(S) / p
d2 = np.linalg.norm(S - m * np.eye(p), "fro") ** 2
b2 = 0.0
for k in range(n):
    xk = X[k][:, None]
    b2 += np.linalg.norm(xk @ xk.T - S, "fro") ** 2
b2 = min(b2 / n ** 2, d2)
shrink = b2 / d2 if d2 > 0 else 1.0
Sigma = shrink * m * np.eye(p) + (1 - shrink) * S
Sinv = np.linalg.inv(Sigma)
print(f"LW shrinkage {shrink:.4f}")


def mdist(V, site):
    D = V - mus[site]
    return np.sqrt(np.einsum("ij,jk,ik->i", D, Sinv, D))


# touch LOO ceiling (bp pipeline)
loo_conf = np.zeros((10, 10), int)
for i, site in enumerate(sc.SITE_ORDER):
    V = touch_V[site]; ns = V.shape[0]
    dists = np.zeros((ns, 10))
    for j, s2 in enumerate(sc.SITE_ORDER):
        if s2 == site:
            mu_loo = (ns * mus[s2] - V) / (ns - 1)
            D = V - mu_loo
        else:
            D = V - mus[s2]
        dists[:, j] = np.sqrt(np.einsum("ij,jk,ik->i", D, Sinv, D))
    for pr in dists.argmin(axis=1):
        loo_conf[i, pr] += 1
loo_acc = loo_conf.trace() / loo_conf.sum()
self_d = np.median([np.median(mdist(touch_V[s], s)) for s in sc.SITE_ORDER])
print(f"touch LOO 10-way (bp): {loo_acc:.3f}; within-site median d {self_d:.2f}")


def arm_vectors(tag):
    out = {}
    for arm_type, keys in (("MPC", ["MPC_r1b", "MPC_r2"]), ("Choi", ["Choi_r1", "Choi_r2"])):
        trs, sl = [], []
        for k in keys:
            z = np.load(os.path.join(CACHE, f"arm_{k}_{tag}.npz"))
            trs.append(z["trials"].astype(float)); sl.append(z["sites"])
            npre = int(z["n_pre"])
        trs = np.concatenate(trs); sl = np.concatenate(sl)
        V = vecs(trs, npre)
        for site in ARM_SITES + ["SHAM"]:
            out[(arm_type, site)] = V[sl == site]
    return out


def run(tag):
    arm_V = arm_vectors(tag)
    rows = [(a, s) for a in ("MPC", "Choi") for s in ARM_SITES + ["SHAM"]]
    Dmed = np.zeros((len(rows), 10))
    for r, (a, s) in enumerate(rows):
        for c, ts_ in enumerate(sc.SITE_ORDER):
            Dmed[r, c] = np.median(mdist(arm_V[(a, s)], ts_))
    conf, acc, pv = {}, {}, {}
    for a in ("MPC", "Choi"):
        C5 = np.zeros((5, 5), int)
        for i, s in enumerate(ARM_SITES):
            V = arm_V[(a, s)]
            d5 = np.stack([mdist(V, t_) for t_ in ARM_SITES], axis=1)
            for pr in d5.argmin(axis=1):
                C5[i, pr] += 1
        conf[a] = C5
        acc[a] = C5.trace() / C5.sum()
        pv[a] = float(stats.binomtest(int(C5.trace()), int(C5.sum()), 0.2,
                                      alternative="greater").pvalue)
    return rows, Dmed, conf, acc, pv


rows, Dmed_c, conf_c, acc_c, pv_c = run("clean")
_, Dmed_r, conf_r, acc_r, pv_r = run("rawbp")
print("cleaned acc:", {a: round(v, 3) for a, v in acc_c.items()}, "p:", pv_c)
print("rawbp   acc:", {a: round(v, 3) for a, v in acc_r.items()}, "p:", pv_r)

with open(os.path.join(ac.ANA_DIR, "spat_summary.json")) as f:
    spat = json.load(f)
old = spat["mahalanobis"]
Dmed_old = np.array(old["median_distance_matrix"])
# reorder old rows to match ours (old rows: MPC D1..SHAM then Choi D1..SHAM, same order)
assert old["arm_rows"] == [f"{a} {s}" for a, s in rows]

# ---------------- figure ----------------
from matplotlib.gridspec import GridSpec
fig = plt.figure(figsize=(14, 11))
gs = GridSpec(2, 3, figure=fig, height_ratios=[1.0, 1.0], hspace=0.4, wspace=0.4)

axA = fig.add_subplot(gs[0, :])
imA = axA.imshow(Dmed_c, cmap="Greys", aspect="auto", interpolation="nearest")
axA.set_xticks(range(10)); axA.set_xticklabels(sc.SITE_ORDER)
axA.set_yticks(range(len(rows)))
axA.set_yticklabels([f"{a} {s}" for a, s in rows], fontsize=9)
for r in range(len(rows)):
    for c in range(10):
        axA.text(c, r, f"{Dmed_c[r, c]:.1f}", ha="center", va="center", fontsize=7.5,
                 color="white" if Dmed_c[r, c] > np.percentile(Dmed_c, 75) else "black")
    cmin = int(Dmed_c[r].argmin())
    axA.add_patch(plt.Rectangle((cmin - 0.5, r - 0.5), 1, 1, fill=False,
                                edgecolor=sc.GREEN, lw=2.0))
axA.axhline(5.5, color="black", lw=1.0)
axA.spines["top"].set_visible(True); axA.spines["right"].set_visible(True)
axA.set_title(f"CLEANED median Mahalanobis distance, arm events vs touch sites "
              f"(touch within-site median {self_d:.1f}; old arm medians: MPC 8-14, Choi 15-20)",
              fontsize=11)
fig.colorbar(imA, ax=axA, fraction=0.02, pad=0.05).set_label("median d")

for k, a in enumerate(("MPC", "Choi")):
    ax = fig.add_subplot(gs[1, k])
    C5 = conf_c[a]; Cn = C5 / C5.sum(axis=1, keepdims=True)
    ax.imshow(Cn, cmap="Greens", vmin=0, vmax=1, interpolation="nearest")
    ax.set_xticks(range(5)); ax.set_xticklabels(ARM_SITES, fontsize=9)
    ax.set_yticks(range(5)); ax.set_yticklabels(ARM_SITES, fontsize=9)
    ax.set_xlabel("nearest touch site"); ax.set_ylabel("stim-for site")
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{C5[i, j]}", ha="center", va="center", fontsize=9,
                    color="white" if Cn[i, j] > 0.5 else "black")
    ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
    old_acc = old["accuracy_5way"][a]
    ax.set_title(f"{a} cleaned: {acc_c[a]*100:.0f}% (was {old_acc*100:.0f}%; "
                 f"chance 20%, p={pv_c[a]:.3f})", fontsize=10.5)

axD = fig.add_subplot(gs[1, 2])
Cn = loo_conf / loo_conf.sum(axis=1, keepdims=True)
axD.imshow(Cn, cmap="Greens", vmin=0, vmax=1, interpolation="nearest")
axD.set_xticks(range(10)); axD.set_xticklabels(sc.SITE_ORDER, fontsize=7.5, rotation=45)
axD.set_yticks(range(10)); axD.set_yticklabels(sc.SITE_ORDER, fontsize=7.5)
for i in range(10):
    for j in range(10):
        if loo_conf[i, j] > 0:
            axD.text(j, i, f"{loo_conf[i, j]}", ha="center", va="center", fontsize=6,
                     color="white" if Cn[i, j] > 0.5 else "black")
axD.spines["top"].set_visible(True); axD.spines["right"].set_visible(True)
axD.set_title(f"Ceiling (bp pipeline): touch LOO {loo_acc*100:.0f}%", fontsize=10.5)

fig.suptitle(f"Site identity after artifact cleaning: MPC {acc_c['MPC']*100:.0f}% / "
             f"Choi {acc_c['Choi']*100:.0f}% 5-way vs 20% chance "
             f"(was 19% / 22% on artifact-contaminated data)", fontsize=12.5, y=0.99)
fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=0.08)
fig.savefig(os.path.join(ac.ANA_DIR, "art_mahalanobis.png"))
print("wrote art_mahalanobis.png")

ac.save_json_part("mahalanobis_cleaned", {
    "window_ms": [10, 40], "n_dims": int(p), "lw_shrinkage": float(shrink),
    "touch_bp_within_site_median_dist": float(self_d),
    "touch_bp_loo_10way_accuracy": float(loo_acc),
    "arm_rows": [f"{a} {s}" for a, s in rows],
    "touch_cols": sc.SITE_ORDER,
    "median_distance_matrix_clean": Dmed_c.tolist(),
    "median_distance_matrix_rawbp": Dmed_r.tolist(),
    "median_distance_matrix_old": Dmed_old.tolist(),
    "confusion_5way_clean": {a: conf_c[a].tolist() for a in conf_c},
    "accuracy_5way_clean": {a: float(acc_c[a]) for a in acc_c},
    "accuracy_5way_rawbp": {a: float(acc_r[a]) for a in acc_r},
    "accuracy_5way_old": old["accuracy_5way"],
    "pvalue_vs_chance_clean": pv_c,
    "pvalue_vs_chance_rawbp": pv_r,
    "chance": 0.2,
})
