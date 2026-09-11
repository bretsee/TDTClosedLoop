"""spat_decode -- claim 6: can the 64-ch arm-evoked pattern SELECT the site?

Pools per-event 64-ch feature vectors across MPC r1-r3 (and Choi r1-r3),
leave-one-out nearest-centroid classification of the 5 target sites, vs the
20% chance line. Acute #1's headline negative was ~19-22% at one control
channel; this tests it at 64-ch recording.
"""
import numpy as np

import spat_common as sp
import deckkit as dk

POOL = {"MPC": ["mpc_r1", "mpc_r2", "mpc_r3"],
        "Choi": ["choi_r1", "choi_r2", "choi_r3"]}


def loo_confusion(X, y, sites):
    idx = {s: i for i, s in enumerate(sites)}
    yi = np.array([idx[s] for s in y])
    C = np.zeros((len(sites), len(sites)))
    correct = 0
    for i in range(len(X)):
        mask = np.ones(len(X), bool)
        mask[i] = False
        cents = np.array([X[mask][yi[mask] == k].mean(axis=0)
                          for k in range(len(sites))])
        pred = int(np.argmin(np.linalg.norm(cents - X[i], axis=1)))
        C[yi[i], pred] += 1
        correct += (pred == yi[i])
    return C, correct / len(X)


def main():
    result = {}
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"])
        for ax, (arm, runs) in zip(axes, POOL.items()):
            X = np.vstack([sp.event_vectors(r)[0] for r in runs])
            y = [s for r in runs for s in sp.event_vectors(r)[1]]
            # z-score channels
            X = (X - X.mean(0)) / (X.std(0) + 1e-12)
            C, acc = loo_confusion(X, y, sp.SITES)
            # active-only accuracy (drop SHAM = the trivial target/no-target split)
            act = [i for i, s in enumerate(sp.SITES) if s != "SHAM"]
            act_correct = sum(C[i, i] for i in act)
            act_total = sum(C[i].sum() for i in act)
            acc_active = act_correct / act_total
            Cn = C / C.sum(1, keepdims=True)
            im = ax.imshow(Cn, cmap="Blues", vmin=0, vmax=1)
            ax.set_xticks(range(5), sp.SITES)
            ax.set_yticks(range(5), sp.SITES)
            ax.set_xlabel("predicted site")
            if ax is axes[0]:
                ax.set_ylabel("true site")
            ax.set_title(f"{arm}: all-5 {acc*100:.0f}% (chance 20%)  ·  "
                         f"4 active sites {acc_active*100:.0f}% (chance 25%)")
            for i in range(5):
                for j in range(5):
                    ax.text(j, i, f"{Cn[i,j]*100:.0f}", ha="center",
                            va="center", fontsize=8,
                            color="white" if Cn[i, j] > 0.5 else dk.INK_2)
            ax.grid(False)
            result[arm] = {"accuracy": acc, "accuracy_active": acc_active,
                           "n_events": len(X)}
        fig.suptitle("Site-decoding from arm-evoked 64-ch patterns "
                     "(leave-one-out) -- one fixed stim footprint cannot "
                     "SELECT the target site", fontsize=13, fontweight="bold")
        fig.colorbar(im, ax=axes, shrink=0.7, label="fraction")
        dk.save_fig(fig, sp.ANA / "spat_decode.png")
    sp.write_json("_decode.json", {**result, "chance": 0.20,
                                   "note": "feature-space (rectified LFP), "
                                           "artifact-contaminated; raw-LFP "
                                           "artifact-aware redo is the "
                                           "refinement"})


if __name__ == "__main__":
    main()
