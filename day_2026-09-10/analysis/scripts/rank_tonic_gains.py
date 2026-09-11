"""rank_tonic_gains -- tonic gain collapse across operating configs (TALL)."""
import numpy as np

import rank_common as rc
import deckkit as dk

CONFIGS = [
    ("capture_rig_runopfit10.csv", list(range(1, 9)), "8 pairs @ 10-30 µA"),
    ("capture_rig_runopfit11.csv", [1, 4], "pairs 1+4 @ 10-30 µA"),
    ("capture_rig_runopfit12.csv", [4, 6], "pairs 4+6 @ 8-22 µA"),
]
SHOW_CH = [64, 47, 42, 40, 39, 34, 29, 56]


def main():
    mats = []
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 3, figsize=dk.FIGSIZE["TALL"],
                                 width_ratios=[8, 2, 2])
        vmax = 0.15
        for ax, (name, pairs, title) in zip(axes, CONFIGS):
            G = rc.tonic_gain_matrix(name, pairs)
            mats.append((name, pairs, G))
            sub = G[:, [c - 1 for c in SHOW_CH]]
            im = ax.imshow(sub.T, aspect="auto", cmap="Blues", vmin=0,
                           vmax=vmax)
            ax.set_xticks(range(len(pairs)), [f"p{p}" for p in pairs])
            if ax is axes[0]:
                ax.set_yticks(range(len(SHOW_CH)),
                              [f"ch{c}" for c in SHOW_CH])
            else:
                ax.set_yticks([])
            ax.set_title(title, fontsize=10)
            ax.grid(False)
        fig.colorbar(im, ax=axes, shrink=0.8, label="|corr| (u -> feature)")
        fig.suptitle("Tonic drive collapses pair identity: gain survives "
                     "only via pair 4", fontsize=13, fontweight="bold")
        dk.save_fig(fig, rc.ANA / "rank_tonic.png")
    rc.write_json("_tonic.json", {
        name: {"pairs": pairs,
               "max_gain": round(float(G.max()), 3),
               "gain_ch64": [round(float(G[i, 63]), 3)
                             for i in range(len(pairs))]}
        for name, pairs, G in mats
    })


if __name__ == "__main__":
    main()
