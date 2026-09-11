"""rank_drift -- the closing drift bracket (HALF)."""
import rank_common as rc
import deckkit as dk

N = 12000  # compare equal lengths (the late replay is 12k ticks)


def gain(name, pair, n):
    u, Y = rc.capture(name)
    return rc.best_lag_corr(u[:n, pair - 1], Y[:n, 63])


def main():
    vals = {
        "u4": (gain("capture_rig_runopfit12.csv", 4, N),
               gain("capture_rig_runopfit12_late2.csv", 4, N)),
        "u6": (gain("capture_rig_runopfit12.csv", 6, N),
               gain("capture_rig_runopfit12_late2.csv", 6, N)),
    }
    colors = {"u4": dk.COLOR["stim"], "u6": dk.CAT[6]}
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("HALF")
        for name, (e, l) in vals.items():
            ax.plot([0, 1], [e, l], "o-", color=colors[name], ms=10, lw=2.4,
                    label=f"pair {name[1]} → ch64")
            ax.annotate(f"{l:.3f}", (1.04, l), color=colors[name], fontsize=10,
                        va="center")
        ax.set_xticks([0, 1], ["21:32", "~01:00"])
        ax.set_xlim(-0.2, 1.35)
        ax.set_ylabel("tonic gain |corr| (u → ch-64 feature)")
        ax.set_title("Drift bracket: the primary actuator held all night")
        ax.legend(frameon=False, loc="lower left")
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, rc.ANA / "rank_drift.png")
    rc.write_json("_drift.json", {k: {"early": round(e, 3), "late": round(l, 3)}
                                  for k, (e, l) in vals.items()})


if __name__ == "__main__":
    main()
