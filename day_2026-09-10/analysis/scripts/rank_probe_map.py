"""rank_probe_map -- all 8 thalamic pairs evoke cortex (WIDE, 2 panels)."""
import numpy as np

import rank_common as rc
import deckkit as dk


def main():
    Z, A = rc.pulse_response_matrix()
    best_z = Z.max(axis=1)
    best_ch = Z.argmax(axis=1) + 1
    pairs = np.arange(1, 9)
    with dk.deck_style() as plt:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=dk.FIGSIZE["WIDE"],
                                       width_ratios=[3, 2])
        bars = ax1.bar([str(p) for p in pairs], best_z,
                       color=dk.COLOR["stim"], width=0.62)
        for b, z, c in zip(bars, best_z, best_ch):
            ax1.text(b.get_x() + b.get_width() / 2, z + 1.0, f"ch{c}",
                     ha="center", fontsize=9, color=dk.INK_2)
        ax1.set_xlabel("stim pair (word)")
        ax1.set_ylabel("evoked z (feature-space, amps ≥ 13 µA)")
        ax1.set_title("All 8 pairs drive cortex (acute #1: 2 of 8)")
        ax1.grid(True, axis="y")
        ax1.grid(False, axis="x")
        top = np.argsort(Z.max(axis=0))[::-1][:10]
        im = ax2.imshow(Z[:, top], aspect="auto", cmap="Blues")
        ax2.set_yticks(range(8), [f"p{p}" for p in pairs])
        ax2.set_xticks(range(len(top)), [f"ch{c+1}" for c in top], fontsize=8)
        ax2.set_title("z by pair × top-10 channels")
        fig.colorbar(im, ax=ax2, shrink=0.85, label="z")
        dk.save_fig(fig, rc.ANA / "rank_probe_map.png")
    rc.write_json("_probe_map.json", {
        "pairs": pairs.tolist(),
        "best_z": [round(float(z), 1) for z in best_z],
        "best_channel": best_ch.tolist(),
        "note": "feature-space z at 100 Hz ticks; 8-11.5 ms latencies are "
                "from the raw block (see notebook), transfer pending",
    })


if __name__ == "__main__":
    main()
