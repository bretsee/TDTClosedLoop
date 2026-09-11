"""rank_pulse_vs_tonic -- THE claim-2 exhibit (FULL).

Normalized singular-value spectra: the pulse-evoked response matrix
(8 pairs x 64 ch, from the rnd1 probe) vs the tonic gain matrix (opfit10,
same 8 pairs driven simultaneously). Pulse spectrum rich; tonic collapses.
"""
import numpy as np

import rank_common as rc
import deckkit as dk


def main():
    _, A = rc.pulse_response_matrix()          # signed evoked deltas
    G = rc.tonic_gain_matrix("capture_rig_runopfit10.csv", list(range(1, 9)))
    rank_p, sv_p = rc.eff_rank(A)
    rank_t, sv_t = rc.eff_rank(G)
    k = np.arange(1, 9)
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        ax.semilogy(k, sv_p, "o-", color=dk.COLOR["stim"], ms=10, lw=2.4,
                    label=f"pulse-evoked (single pulses) - eff. rank {rank_p}")
        ax.semilogy(k, sv_t, "o-", color=dk.COLOR["mpc"], ms=10, lw=2.4,
                    label=f"tonic drive (continuous 100 Hz) - eff. rank {rank_t}")
        ax.axhline(0.1, color=dk.AXIS, lw=1.0, ls="--")
        ax.annotate("rank threshold (0.1 x s1)", (5.6, 0.11), fontsize=9,
                    color=dk.INK_2)
        ax.set_xlabel("singular value index k")
        ax.set_ylabel("sk / s1")
        ax.set_title(
            f"Pulse drive is rich (s2/s1 = {sv_p[1]:.2f}, eff. rank "
            f"{rank_p}); tonic drive collapses (s2/s1 = {sv_t[1]:.2f}, "
            f"eff. rank {rank_t}, one direction above the |corr| 0.1 "
            "usability bar)")
        ax.legend(frameon=False)
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, rc.ANA / "rank_pulse_vs_tonic.png")
    rc.write_json("_rank.json", {
        "pulse_eff_rank": rank_p, "tonic_eff_rank": rank_t,
        "pulse_sv": [round(float(v), 4) for v in sv_p],
        "tonic_sv": [round(float(v), 4) for v in sv_t],
    })


if __name__ == "__main__":
    main()
