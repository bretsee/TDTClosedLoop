"""trk_per_run -- headline tracking per run per arm (FULL)."""
import trk_common as tc
import deckkit as dk

ORDER = ["r1", "r2", "r3", "r1_late"]
LABELS = ["r1", "r2", "r3", "r1 late\n(same tape as r1)"]


def main():
    mpc = [tc.recompute(f"mpc_{k}") for k in ORDER]
    choi = [tc.recompute(f"choi_{k}") for k in ORDER]
    nn = tc.recompute("nn_r1b")
    x = range(len(ORDER))
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        ax.plot(x, [m["r0"] for m in mpc], "o-", color=dk.COLOR["mpc"],
                ms=9, label="MPC (lag 0 in every run)")
        ax.plot(x, [c["r0"] for c in choi], "o-", color=dk.COLOR["choi"],
                ms=9, label="Choi r0")
        ax.plot(x, [c["r_best"] for c in choi], "o--", color=dk.COLOR["choi"],
                ms=9, mfc="white", label="Choi at its best lag (-1)")
        ax.axhline(nn["r0"], color=dk.COLOR["nn"], lw=2.0, ls=":",
                   label=f"NN / mean-drive tape (r0 {nn['r0']:.2f})")
        ax.set_xticks(list(x), LABELS)
        ax.set_ylabel("tracking fidelity r (ref vs ch-64 feature)")
        ax.set_ylim(-0.05, 0.55)
        ax.set_title("Closed-loop arms: fidelity per run "
                     "(recomputed from raw captures)")
        ax.legend(frameon=False, loc="lower right")
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_per_run.png")
    tc.write_json("_per_run.json", {
        "mpc": mpc, "choi": choi, "nn": nn,
    })


if __name__ == "__main__":
    main()
