"""trk_early_late -- claim 1: feedback adapts, replay cannot (FULL, 2 panels).

Left: paired r0, identical tape run early vs ~2 h later, per arm (slopegraph).
Right: amplitude calibration (slope y-on-r) early vs late per arm -- MPC
returns to exactly 1.000.  Plus per-event paired stats via schedule windows.
"""
import numpy as np

import trk_common as tc
import deckkit as dk


def main():
    pairs = {
        "MPC": (tc.recompute("mpc_r1"), tc.recompute("mpc_r1_late")),
        "Choi": (tc.recompute("choi_r1"), tc.recompute("choi_r1_late")),
    }
    # per-event paired deltas (same events, same tape)
    ev = {}
    for arm, (e_run, l_run) in (("MPC", ("mpc_r1", "mpc_r1_late")),
                                ("Choi", ("choi_r1", "choi_r1_late"))):
        early = {d["event"]: d["r"] for d in tc.per_event_r(e_run)}
        late = {d["event"]: d["r"] for d in tc.per_event_r(l_run)}
        common = sorted(set(early) & set(late))
        deltas = np.array([late[k] - early[k] for k in common])
        ev[arm] = {"n": len(common), "delta_mean": float(deltas.mean()),
                   "delta_sem": float(deltas.std(ddof=1) / np.sqrt(len(deltas)))}
    colors = {"MPC": dk.COLOR["mpc"], "Choi": dk.COLOR["choi"]}
    with dk.deck_style() as plt:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"])
        for arm, (e, l) in pairs.items():
            ax1.plot([0, 1], [e["r0"], l["r0"]], "o-", color=colors[arm],
                     ms=10, lw=2.4, label=arm)
            ax1.annotate(f"{l['r0']-e['r0']:+.3f}", (1.03, l["r0"]),
                         color=colors[arm], fontsize=11, va="center")
            ax2.plot([0, 1], [e["slope"], l["slope"]], "o-", color=colors[arm],
                     ms=10, lw=2.4, label=arm)
        ax2.axhline(1.0, color=dk.AXIS, lw=1.0, ls="--")
        ax2.annotate("perfect calibration", (0.02, 1.005), fontsize=9,
                     color=dk.INK_2)
        for ax, ylab, title in ((ax1, "r0 (identical tape/ref)",
                                 "Fidelity: early vs ~2 h later"),
                                (ax2, "amplitude slope (y on ref)",
                                 "Calibration: MPC re-converges to 1.000")):
            ax.set_xticks([0, 1], ["early (r1)", "late (r1 repeat)"])
            ax.set_xlim(-0.25, 1.35)
            ax.set_ylabel(ylab)
            ax.set_title(title)
            ax.legend(frameon=False, loc="lower left")
            ax.grid(True, axis="y")
            ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_early_late.png")
    tc.write_json("_early_late.json", {
        "pairs": {a: {"early": e, "late": l} for a, (e, l) in pairs.items()},
        "per_event_paired": ev,
    })


if __name__ == "__main__":
    main()
