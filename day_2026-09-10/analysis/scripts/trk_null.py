"""trk_null -- shuffled-template null vs observed r (HALF).

Circular-shift null (500 draws, shifts >= 1000 ticks) on the mpc_r1 pairing:
the reference is rotated against the recorded y, r recomputed per draw.
Observed r0 vs the null distribution = the REACH-Ctrl-style control.
"""
import numpy as np

import trk_common as tc
import deckkit as dk

N_DRAWS, MIN_SHIFT = 500, 1000


def main():
    u, y, r, _, _ = tc.load("mpc_r1")
    rng = np.random.default_rng(20260911)
    yz = y - y.mean()
    ny = np.linalg.norm(yz)
    nulls = []
    for _ in range(N_DRAWS):
        s = int(rng.integers(MIN_SHIFT, len(r) - MIN_SHIFT))
        rs = np.roll(r, s)
        rz = rs - rs.mean()
        nulls.append(float(np.dot(rz, yz) / (np.linalg.norm(rz) * ny)))
    nulls = np.array(nulls)
    obs = tc.recompute("mpc_r1")["r0"]
    p = float((np.abs(nulls) >= abs(obs)).mean())
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("HALF")
        ax.hist(nulls, bins=40, color=dk.COLOR["null"], edgecolor="white")
        ax.axvline(obs, color=dk.COLOR["mpc"], lw=2.5)
        ax.annotate(f"observed r0 = {obs:.3f}\np < {max(p, 1/N_DRAWS):.3f}",
                    (obs, ax.get_ylim()[1] * 0.82), fontsize=11,
                    color=dk.COLOR["mpc"], ha="right", xytext=(-8, 0),
                    textcoords="offset points")
        ax.set_xlabel("r under circular-shift null")
        ax.set_ylabel("draws")
        ax.set_title(f"Shuffled-reference null ({N_DRAWS} draws), MPC r1")
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_null.png")
    tc.write_json("_null.json", {
        "n_draws": N_DRAWS, "observed_r0": obs,
        "null_abs_p99": float(np.percentile(np.abs(nulls), 99)),
        "p_value_bound": max(p, 1 / N_DRAWS),
    })


if __name__ == "__main__":
    main()
