"""sci_gallery -- 10-site best-channel template grid (TALL preset)."""
import numpy as np

import sci_common as sc
import deckkit as dk


def main():
    metas = sc.registry()
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(2, 5, figsize=dk.FIGSIZE["TALL"],
                                 sharex=True, sharey=True)
        for ax, m in zip(axes.ravel(), metas):
            T, fs = sc.template(m)
            c = int(m["best_channel_1based"]) - 1
            t_ms = np.arange(T.shape[1]) / fs * 1e3
            color = dk.COLOR["null"] if m["site"] == "SHAM" else dk.COLOR["touch"]
            ax.plot(t_ms, T[c], color=color, lw=1.8)
            ax.axhline(0, color=dk.AXIS, lw=0.6)
            ax.set_title(f"{m['site']}  ch{m['best_channel_1based']}", fontsize=11)
            ax.grid(True, axis="y")
            ax.grid(False, axis="x")
        for ax in axes[-1]:
            ax.set_xlabel("ms")
        for ax in axes[:, 0]:
            ax.set_ylabel("uV")
        fig.suptitle("Touch templates -- best channel per site (150-trial mean)",
                     fontsize=13, fontweight="bold")
        dk.save_fig(fig, sc.ANA / "sci_gallery.png")
    sc.write_json("_gallery.json", {
        "sites": [m["site"] for m in metas],
        "best_channels": [m["best_channel_1based"] for m in metas],
    })


if __name__ == "__main__":
    main()
