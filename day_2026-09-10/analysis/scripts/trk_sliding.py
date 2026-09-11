"""trk_sliding -- sliding-window fidelity within runs (WIDE).

r in 2200-tick (~22 s, 10-event) windows stepped by 550 ticks, for the
early/late pair of each arm: within-run stability + across-hours context.
"""
import numpy as np

import trk_common as tc
import deckkit as dk

WIN, STEP = 2200, 550
SHOW = [("mpc_r1", "MPC early", dk.COLOR["mpc"], "-"),
        ("mpc_r1_late", "MPC late", dk.COLOR["mpc"], "--"),
        ("choi_r1", "Choi early", dk.COLOR["choi"], "-"),
        ("choi_r1_late", "Choi late", dk.COLOR["choi"], "--")]


def slide_r(run):
    u, y, r, _, _ = tc.load(run)
    out_t, out_r = [], []
    for i0 in range(0, len(y) - WIN, STEP):
        rr, yy = r[i0:i0 + WIN], y[i0:i0 + WIN]
        rz, yz = rr - rr.mean(), yy - yy.mean()
        den = np.linalg.norm(rz) * np.linalg.norm(yz)
        out_t.append((i0 + WIN / 2) / 100.0 / 60.0)   # minutes into run
        out_r.append(float(np.dot(rz, yz) / den) if den > 0 else 0.0)
    return np.array(out_t), np.array(out_r)


def main():
    payload = {}
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("HALF")
        for run, label, color, ls in SHOW:
            t, r = slide_r(run)
            ax.plot(t, r, ls, color=color, lw=2.0, label=label)
            payload[run] = {"t_min": t.tolist(), "r": [round(v, 4) for v in r]}
        ax.set_xlabel("minutes into run")
        ax.set_ylabel("sliding-window r (22 s windows)")
        ax.set_title("Within-run stability -- identical tape early vs ~2 h later")
        ax.legend(frameon=False, ncols=2, loc="lower center", fontsize=9)
        ax.set_ylim(-0.1, 0.7)
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_sliding.png")
    tc.write_json("_sliding.json", payload)


if __name__ == "__main__":
    main()
