"""spat_mahalanobis.png: site-identity analysis.

Touch battery -> per-site 31-dim response distributions (10-40 ms mean, ch 27 dropped,
Ledoit-Wolf-regularized pooled covariance). Arm events -> Mahalanobis distance to each
touch site + nearest-template classification. Touch LOO self-classification = ceiling.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

plt = sc.style()
from matplotlib.gridspec import GridSpec

CACHE = os.path.join(sc.ANA_DIR, "cache")
fs = sc.FS_WAV
good = np.array([c for c in range(32) if c not in sc.BLACKLIST_CH])  # 31 ch
ARM_SITES = ["D1", "D2", "D3", "P2", "LP"]

def vecs(trials, n_pre):
    a = n_pre + int(round(0.010 * fs))
    b = n_pre + int(round(0.040 * fs))
    return trials[:, good, a:b].mean(axis=2)  # n_tr x 31

# ---- touch distributions ----
touch_V = {}
for site in sc.SITE_ORDER:
    z = np.load(os.path.join(CACHE, f"touch_{site}.npz"))
    touch_V[site] = vecs(z["trials"].astype(float), int(z["n_pre"]))
mus = {s: v.mean(axis=0) for s, v in touch_V.items()}

# pooled within-site scatter + Ledoit-Wolf shrinkage to scaled identity
X = np.concatenate([touch_V[s] - mus[s] for s in sc.SITE_ORDER])  # 1500 x 31
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
print(f"LW shrinkage {shrink:.4f}, cond(S) {np.linalg.cond(S):.1f} -> cond(Sigma) {np.linalg.cond(Sigma):.1f}")

def mdist(V, site):
    D = V - mus[site]
    return np.sqrt(np.einsum("ij,jk,ik->i", D, Sinv, D))

# ---- touch LOO self-classification (ceiling) ----
loo_conf = np.zeros((10, 10), int)
for i, site in enumerate(sc.SITE_ORDER):
    V = touch_V[site]
    ns = V.shape[0]
    dists = np.zeros((ns, 10))
    for j, s2 in enumerate(sc.SITE_ORDER):
        if s2 == site:
            mu_loo = (ns * mus[s2] - V) / (ns - 1)   # per-trial LOO mean
            D = V - mu_loo
        else:
            D = V - mus[s2]
        dists[:, j] = np.sqrt(np.einsum("ij,jk,ik->i", D, Sinv, D))
    pred = dists.argmin(axis=1)
    for pr in pred:
        loo_conf[i, pr] += 1
loo_acc = np.trace(loo_conf) / loo_conf.sum()
print(f"touch LOO 10-way accuracy {loo_acc:.3f} (chance 0.10)")

# ---- arm event vectors ----
arm_V = {}   # (armtype, site) -> vectors
for arm_type, keys in (("MPC", ["MPC_r1b", "MPC_r2"]), ("Choi", ["Choi_r1", "Choi_r2"])):
    trs, sl = [], []
    for k in keys:
        z = np.load(os.path.join(CACHE, f"arm_{k}.npz"))
        trs.append(z["trials"].astype(float)); sl.append(z["sites"])
        npre = int(z["n_pre"])
    trs = np.concatenate(trs); sl = np.concatenate(sl)
    V = vecs(trs, npre)
    for site in ARM_SITES + ["SHAM"]:
        arm_V[(arm_type, site)] = V[sl == site]

# median-distance matrix: 12 rows x 10 touch sites
rows = [(a, s) for a in ("MPC", "Choi") for s in ARM_SITES + ["SHAM"]]
Dmed = np.zeros((len(rows), 10))
for r, (a, s) in enumerate(rows):
    for c, ts_ in enumerate(sc.SITE_ORDER):
        Dmed[r, c] = np.median(mdist(arm_V[(a, s)], ts_))

# touch-touch reference distances (median trial distance to own vs other sites)
self_d = np.median([np.median(mdist(touch_V[s], s)) for s in sc.SITE_ORDER])

# ---- classification of arm events among 5 real sites ----
conf = {}
acc = {}
match_rate_rows = {}
for a in ("MPC", "Choi"):
    C5 = np.zeros((5, 5), int)
    for i, s in enumerate(ARM_SITES):
        V = arm_V[(a, s)]
        d5 = np.stack([mdist(V, ts_) for ts_ in ARM_SITES], axis=1)
        pred = d5.argmin(axis=1)
        for pr in pred:
            C5[i, pr] += 1
    conf[a] = C5
    acc[a] = np.trace(C5) / C5.sum()
    print(f"{a} 5-way nearest-touch-template accuracy {acc[a]:.3f} (chance 0.20)")

# binomial p-value vs chance (normal approx)
from scipy import stats
pvals = {}
for a in ("MPC", "Choi"):
    ntot = conf[a].sum(); k = np.trace(conf[a])
    pvals[a] = float(stats.binomtest(int(k), int(ntot), 0.2, alternative="greater").pvalue)

# ---------------- figure ----------------
fig = plt.figure(figsize=(13.5, 10.5))
gs = GridSpec(2, 3, figure=fig, height_ratios=[1.0, 1.0], width_ratios=[1, 1, 1.25],
              hspace=0.45, wspace=0.45)

# Panel A: median distance matrix
axA = fig.add_subplot(gs[0, :])
imA = axA.imshow(Dmed, cmap="Greys", aspect="auto", interpolation="nearest")
axA.set_xticks(range(10)); axA.set_xticklabels(sc.SITE_ORDER)
axA.set_yticks(range(len(rows)))
axA.set_yticklabels([f"{a} {s}" for a, s in rows], fontsize=9)
for r in range(len(rows)):
    for c in range(10):
        v = Dmed[r, c]
        axA.text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=7.5,
                 color="white" if v > np.percentile(Dmed, 75) else "black")
    # mark nearest touch site per row
    cmin = int(Dmed[r].argmin())
    axA.add_patch(plt.Rectangle((cmin - 0.5, r - 0.5), 1, 1, fill=False,
                                edgecolor=sc.GREEN, lw=2.0))
axA.axhline(5.5, color="black", lw=1.0)
axA.spines["top"].set_visible(True); axA.spines["right"].set_visible(True)
axA.set_title(f"Median Mahalanobis distance, arm events vs touch-site distributions "
              f"(31-ch, 10–40 ms; green box = nearest). Touch within-site median = {self_d:.1f}",
              fontsize=11)
cbA = fig.colorbar(imA, ax=axA, fraction=0.02, pad=0.06)
cbA.set_label("median Mahalanobis d")

# Panels B/C: arm confusion matrices
for k, a in enumerate(("MPC", "Choi")):
    ax = fig.add_subplot(gs[1, k])
    C5 = conf[a]
    Cn = C5 / C5.sum(axis=1, keepdims=True)
    im = ax.imshow(Cn, cmap="Greens", vmin=0, vmax=1, interpolation="nearest")
    ax.set_xticks(range(5)); ax.set_xticklabels(ARM_SITES, fontsize=9)
    ax.set_yticks(range(5)); ax.set_yticklabels(ARM_SITES, fontsize=9)
    ax.set_xlabel("nearest touch site"); ax.set_ylabel("stim-for site")
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{C5[i, j]}", ha="center", va="center", fontsize=9,
                    color="white" if Cn[i, j] > 0.5 else "black")
    ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
    ax.set_title(f"{a}: {acc[a]*100:.0f}% (chance 20%, p={pvals[a]:.3f})", fontsize=11)

# Panel D: touch LOO ceiling
axD = fig.add_subplot(gs[1, 2])
Cn = loo_conf / loo_conf.sum(axis=1, keepdims=True)
imD = axD.imshow(Cn, cmap="Greens", vmin=0, vmax=1, interpolation="nearest")
axD.set_xticks(range(10)); axD.set_xticklabels(sc.SITE_ORDER, fontsize=7.5, rotation=45)
axD.set_yticks(range(10)); axD.set_yticklabels(sc.SITE_ORDER, fontsize=7.5)
axD.set_xlabel("predicted site"); axD.set_ylabel("true touch site")
for i in range(10):
    for j in range(10):
        if loo_conf[i, j] > 0:
            axD.text(j, i, f"{loo_conf[i, j]}", ha="center", va="center", fontsize=6,
                     color="white" if Cn[i, j] > 0.5 else "black")
axD.spines["top"].set_visible(True); axD.spines["right"].set_visible(True)
axD.set_title(f"Ceiling: touch LOO 10-way {loo_acc*100:.0f}% (chance 10%)", fontsize=11)

fig.suptitle(
    f"Site identity: touch responses are decodable ({loo_acc*100:.0f}% 10-way LOO vs 10% chance), "
    f"but arm stim does NOT reproduce it - {acc['MPC']*100:.0f}% (MPC) / {acc['Choi']*100:.0f}% (Choi) "
    f"vs 20% chance, and arm events sit 2-5x the touch within-site distance",
    fontsize=12, y=0.99)
fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=0.08)
out = os.path.join(sc.ANA_DIR, "spat_mahalanobis.png")
fig.savefig(out)
print("wrote", out)

sc.save_json_part("mahalanobis", {
    "window_ms": [10, 40],
    "n_dims": int(p),
    "lw_shrinkage": float(shrink),
    "touch_within_site_median_dist": float(self_d),
    "touch_loo_10way_accuracy": float(loo_acc),
    "touch_loo_confusion_rows_true": {s: loo_conf[i].tolist() for i, s in enumerate(sc.SITE_ORDER)},
    "arm_rows": [f"{a} {s}" for a, s in rows],
    "touch_cols": sc.SITE_ORDER,
    "median_distance_matrix": Dmed.tolist(),
    "confusion_5way": {a: conf[a].tolist() for a in conf},
    "accuracy_5way": {a: float(acc[a]) for a in acc},
    "pvalue_vs_chance": pvals,
    "chance": 0.2,
})
