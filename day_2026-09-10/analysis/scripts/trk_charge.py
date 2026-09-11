"""trk_charge -- delivered charge per run per arm + the reversal (FULL).

Sum|u| in uA-ticks recomputed from every capture. The single sanctioned
hardcode: ~1.3M uA-ticks delivered UNRECORDED during the two PZ2-off void
runs -- a notebook-cited exposure constant, flagged in the JSON.
"""
import numpy as np

import trk_common as tc
import deckkit as dk

ORDER = ["r1", "r2", "r3", "r1_late"]
UNRECORDED_EXPOSURE_UATICKS = 1.30e6   # cited: LAB_NOTEBOOK_2026-09-10.md (PZ2 incident)


def main():
    mpc = [tc.recompute(f"mpc_{k}") for k in ORDER]
    choi = [tc.recompute(f"choi_{k}") for k in ORDER]
    r4b = tc.recompute("mpc_r4b")
    nn = tc.recompute("nn_r1b")
    x = np.arange(len(ORDER))
    w = 0.36
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        ax.bar(x - w / 2, [m["charge_uAticks"] / 1e3 for m in mpc], width=w,
               color=dk.COLOR["mpc"], label="MPC")
        ax.bar(x + w / 2, [c["charge_uAticks"] / 1e3 for c in choi], width=w,
               color=dk.COLOR["choi"], label="Choi")
        ax.bar([len(ORDER)], [r4b["charge_uAticks"] / 1e3], width=w,
               color=dk.COLOR["mpc"], alpha=0.55,
               label="MPC, 3× input penalty (late)")
        ax.bar([len(ORDER) + 0.8], [nn["charge_uAticks"] / 1e3], width=w,
               color=dk.COLOR["nn"], label="NN / mean tape")
        for xi, m, c in zip(x, mpc, choi):
            ax.text(xi - w / 2, m["charge_uAticks"] / 1e3 + 6,
                    f"r {m['r0']:.2f}", ha="center", fontsize=9, color=dk.INK_2)
            ax.text(xi + w / 2, c["charge_uAticks"] / 1e3 + 6,
                    f"r {c['r0']:.2f}", ha="center", fontsize=9, color=dk.INK_2)
        ax.text(len(ORDER), r4b["charge_uAticks"] / 1e3 + 6,
                f"r {r4b['r0']:.2f}", ha="center", fontsize=9, color=dk.INK_2)
        ax.text(len(ORDER) + 0.8, nn["charge_uAticks"] / 1e3 + 6,
                f"r {nn['r0']:.2f}", ha="center", fontsize=9, color=dk.INK_2)
        ax.set_xticks(list(x) + [len(ORDER), len(ORDER) + 0.8],
                      ORDER + ["r4b", "NN"])
        ax.set_ylabel("delivered charge proxy (10³ µA-ticks)")
        ax.set_title("Charge per run: acute #1's MPC charge win REVERSED here "
                     "-- sparse tape vs sustained feedback effort")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_charge.png")
    tc.write_json("_charge.json", {
        "mpc": {m["run"]: m["charge_uAticks"] for m in mpc + [r4b]},
        "choi": {c["run"]: c["charge_uAticks"] for c in choi},
        "nn_r1b": nn["charge_uAticks"],
        "unrecorded_exposure_uAticks": {
            "value": UNRECORDED_EXPOSURE_UATICKS,
            "SANCTIONED_HARDCODE": True,
            "source": "LAB_NOTEBOOK_2026-09-10.md -- PZ2-off incident section",
        },
    })


if __name__ == "__main__":
    main()
