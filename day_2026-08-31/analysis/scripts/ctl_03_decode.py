"""Q3: intent decoding from the y8 feature epoch alone. Per arm (runs pooled):
LOO nearest-centroid 5-way site decoder on ticks 3..40 post-onset (artifact
ticks 0-2 excluded), permutation p (1000 label shuffles). Hold control = null."""
import json

import numpy as np
import sci_common as C
import ctl_common as X

plt = C.style()

FEAT_LO, FEAT_HI = 3, 40          # relative ticks kept (0-2 excluded as artifact)
fsel = (X.TREL >= FEAT_LO) & (X.TREL <= FEAT_HI)
SITES = C.REAL_SITES


def features(arm, runs):
    F, lab = [], []
    for run in runs:
        for r in X.event_epochs(arm, run):
            F.append(r["dy"][fsel])
            lab.append(SITES.index(r["site"]))
    return np.array(F), np.array(lab)


def loo_nc_acc(F, lab):
    """Leave-one-out nearest-centroid accuracy (Euclidean), vectorized."""
    n, k = len(F), len(SITES)
    sums = np.stack([F[lab == c].sum(0) for c in range(k)])
    cnts = np.array([(lab == c).sum() for c in range(k)])
    pred = np.empty(n, int)
    for i in range(n):
        cent = sums / cnts[:, None]
        c = lab[i]
        cent[c] = (sums[c] - F[i]) / max(cnts[c] - 1, 1)
        pred[i] = np.argmin(((cent - F[i]) ** 2).sum(1))
    return float((pred == lab).mean()), pred


ARMS = {"MPC": ["r1", "r2"], "Choi": ["r1", "r2"], "Hold": ["r1"]}
rng = np.random.default_rng(30)
res, conf, accs = {}, {}, {}
for arm, runs in ARMS.items():
    F, lab = features(arm, runs)
    acc, pred = loo_nc_acc(F, lab)
    null = np.empty(1000)
    for i in range(1000):
        null[i] = loo_nc_acc(F, rng.permutation(lab))[0]
    p = float((null >= acc).mean())
    cm = np.zeros((len(SITES), len(SITES)))
    for t, q in zip(lab, pred):
        cm[t, q] += 1
    cm = cm / cm.sum(1, keepdims=True)
    chance = float(max(np.bincount(lab)) / len(lab))
    res[arm] = dict(n=len(lab), accuracy=round(acc, 3), chance_majority=round(chance, 3),
                    null_mean=round(float(null.mean()), 3),
                    null95=round(float(np.percentile(null, 95)), 3), p_perm=p)
    conf[arm], accs[arm] = cm, (acc, p)

fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.3))
for ax, arm in zip(axes, ARMS):
    cm = conf[arm]
    im = ax.imshow(cm, cmap="Greens", vmin=0, vmax=1)
    for i in range(len(SITES)):
        for j in range(len(SITES)):
            ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if cm[i, j] > 0.55 else "black")
    ax.set_xticks(range(len(SITES)))
    ax.set_xticklabels(SITES, fontsize=8)
    ax.set_yticks(range(len(SITES)))
    ax.set_yticklabels(SITES, fontsize=8)
    ax.set_xlabel("decoded site")
    if arm == "MPC":
        ax.set_ylabel("true (attempted) site")
    a, p = accs[arm]
    ptxt = f"p<0.001" if p < 0.001 else f"p={p:.3f}"
    ax.set_title(f"{arm}: LOO acc {a * 100:.0f}% vs null "
                 f"{res[arm]['null_mean'] * 100:.0f}% ({ptxt}, n={res[arm]['n']})", fontsize=9.5)
cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
cb.set_label("row fraction")

both_sig = accs["MPC"][1] < 0.05 and accs["Choi"][1] < 0.05
verdict = ("y8 amplitude/time-course carries site identity even though 32-ch space does not"
           if both_sig else "site identity is NOT reliably decodable from the y8 time course")
fig.suptitle(f"Intent decoding from y8 time course alone (ticks 3-40): "
             f"MPC {accs['MPC'][0] * 100:.0f}%, Choi {accs['Choi'][0] * 100:.0f}%, "
             f"Hold {accs['Hold'][0] * 100:.0f}% (chance ~20%) — {verdict}", fontsize=11)
fig.savefig(f"{C.OUT}/ctl_intent_decoding.png", bbox_inches="tight")

# robustness: correlation-distance variant (row-normalized features -> shape only)
shape = {}
for arm, runs in ARMS.items():
    F, lab = features(arm, runs)
    Fz = (F - F.mean(1, keepdims=True)) / (F.std(1, keepdims=True) + 1e-15)
    acc, _ = loo_nc_acc(Fz, lab)
    null = np.array([loo_nc_acc(Fz, rng.permutation(lab))[0] for _ in range(1000)])
    shape[arm] = dict(accuracy=round(acc, 3), p_perm=float((null >= acc).mean()))

out = dict(decoder="nearest centroid, Euclidean, LOO; features = baseline-subtracted "
                   "lag-corrected y8 at ticks 3..40 post-onset (38 dims); runs pooled per arm",
           per_arm=res, shape_only_variant=shape, verdict=verdict)
with open(f"{X.SCR}/_ctl_q3.json", "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
