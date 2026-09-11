"""spat_footprint -- raw 64-ch activity footprint during MPC vs Choi arms.

From the transferred raw Wav1 (not the feature capture): mean |LFP| per
channel over each arm run, laid on the 8x8 array grid. The two arms drive
the same stim pairs, so the footprints match -- the spatial basis of the
selectivity negative, now in raw LFP at 64 ch.
"""
import numpy as np

import spat_common as sp
import deckkit as dk

# 8x8 NeuroNexus grid: channel (1-based) at [row, col]. Row-major by channel.
GRID = np.arange(1, 65).reshape(8, 8)


def to_grid(vec64):
    g = np.full((8, 8), np.nan)
    for r in range(8):
        for c in range(8):
            ch = GRID[r, c]
            g[r, c] = np.nan if ch in sp.BLACKLIST else vec64[ch - 1]
    return g


def main():
    fp_mpc = sp.raw_footprint("mpc_r1")
    fp_choi = sp.raw_footprint("choi_r1")
    # correlation of the two footprints (blacklist removed)
    keep = [c for c in range(64) if (c + 1) not in sp.BLACKLIST]
    r = float(np.corrcoef(fp_mpc[keep], fp_choi[keep])[0, 1])
    vmax = np.nanpercentile(np.concatenate([fp_mpc, fp_choi]), 98)
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["TALL"])
        for ax, (fp, title) in zip(axes, ((fp_mpc, "MPC r1"),
                                          (fp_choi, "Choi r1"))):
            im = ax.imshow(to_grid(fp) * 1e6, cmap="Blues", vmin=0,
                           vmax=vmax * 1e6)
            ax.set_title(title)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
        fig.suptitle(f"Raw 64-ch activity footprint -- MPC vs Choi identical "
                     f"(r = {r:.2f}): one fixed actuator footprint",
                     fontsize=13, fontweight="bold")
        fig.colorbar(im, ax=axes, shrink=0.7, label="mean |LFP| (µV)")
        dk.save_fig(fig, sp.ANA / "spat_footprint.png")
    sp.write_json("_footprint.json", {"mpc_vs_choi_footprint_r": r})


if __name__ == "__main__":
    main()
