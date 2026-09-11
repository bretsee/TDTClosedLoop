"""trk_nn_negative -- the NN inverse honest negative + mean-drive null (FULL).

Three rows over one 60 s window of nn_r1b: reference; delivered u4/u6 (the
near-mean tape); resulting ch-64 feature. r0 annotated.
"""
import numpy as np

import trk_common as tc
import deckkit as dk

T0, T1 = 3000, 9000   # ticks (30-90 s into the run)


def main():
    u, y, r, _, _ = tc.load("nn_r1b")
    m = tc.recompute("nn_r1b")
    t = np.arange(T0, T1) / 100.0
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(3, 1, figsize=dk.FIGSIZE["FULL"], sharex=True)
        axes[0].plot(t, r[T0:T1] * 1e6, color=dk.COLOR["ref"], lw=1.6)
        axes[0].set_ylabel("reference (µV)")
        axes[0].set_title(
            f"NN inverse policy (GRU, val R² 0.05): tape ≈ tonic mean → "
            f"NOT TRACKING (r0 {m['r0']:.3f})")
        axes[1].plot(t, u[T0:T1, 3], color=dk.COLOR["stim"], lw=1.4,
                     label="u4")
        axes[1].plot(t, u[T0:T1, 5], color=dk.CAT[6], lw=1.4, label="u6")
        axes[1].set_ylabel("command (µA)")
        axes[1].set_ylim(0, 30)
        axes[1].legend(frameon=False, ncols=2, loc="upper right")
        axes[2].plot(t, y[T0:T1] * 1e6, color=dk.COLOR["nn"], lw=1.2)
        axes[2].set_ylabel("ch-64 feature (µV)")
        axes[2].set_xlabel("seconds into run")
        for ax in axes:
            ax.grid(True, axis="y")
            ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_nn.png")
    tc.write_json("_nn.json", {
        "r0": m["r0"], "slope": m["slope"],
        "u4_mean": float(u[:, 3].mean()), "u6_mean": float(u[:, 5].mean()),
        "u4_std": float(u[:, 3].std()), "u6_std": float(u[:, 5].std()),
    })


if __name__ == "__main__":
    main()
