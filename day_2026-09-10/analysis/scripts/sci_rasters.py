"""sci_rasters -- per-trial spaghetti for all 10 sites, from the raw blocks.

Two FULL figures: digit sites + SHAM, pad sites. Every panel: 150 single
trials (light) + mean (entity color), contact + release markers.
"""
import numpy as np

import sci_common as sc
import deckkit as dk

GROUPS = {
    "sci_rasters_digits.png": ["D1", "D2", "D3", "D4", "SHAM"],
    "sci_rasters_pads.png": ["P1", "P2", "P3", "MP", "LP"],
}


def main():
    metas = {m["site"]: m for m in sc.registry()}
    with dk.deck_style() as plt:
        for fname, group in GROUPS.items():
            fig, axes = plt.subplots(1, 5, figsize=dk.FIGSIZE["FULL"],
                                     sharey=True)
            for ax, site in zip(axes, group):
                m = metas[site]
                E, t_ms = sc.epochs(m)
                for tr in E:
                    ax.plot(t_ms, tr, color=dk.COLOR["touch"], lw=0.25,
                            alpha=0.10)
                mean_c = dk.COLOR["null"] if site == "SHAM" else dk.COLOR["stim"]
                ax.plot(t_ms, E.mean(axis=0), color=mean_c, lw=2.2)
                ax.axvline(0, color=dk.INK, lw=0.8, ls="--")
                ax.axvline(sc.CONTACT_MS, color=dk.CAT[5], lw=0.8, ls="--")
                ax.set_ylim(-500, 500)
                ax.set_title(f"{site}  ch{m['best_channel_1based']} "
                             f"(n={len(E)})", fontsize=11)
                ax.set_xlabel("ms")
                ax.grid(True, axis="y")
                ax.grid(False, axis="x")
            axes[0].set_ylabel("LFP (uV)")
            dk.save_fig(fig, sc.ANA / fname)
    sc.write_json("_rasters.json", {"figures": list(GROUPS)})


if __name__ == "__main__":
    main()
