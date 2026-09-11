"""trk_persite -- per-event fidelity split by scheduled site (FULL).

Mean +/- SEM of per-event r by site, pooled over r1-r3, per arm. SHAM events
(flat reference) are the built-in low bar.
"""
import numpy as np

import trk_common as tc
import deckkit as dk

SITES = ["LP", "P1", "MP", "P3", "SHAM"]
POOL = {"mpc": ["mpc_r1", "mpc_r2", "mpc_r3"],
        "choi": ["choi_r1", "choi_r2", "choi_r3"]}


def main():
    stats = {}
    for arm, runs in POOL.items():
        rows = [d for run in runs for d in tc.per_event_r(run)]
        stats[arm] = {}
        for site in SITES:
            vals = np.array([d["r"] for d in rows if d["site"] == site])
            stats[arm][site] = {"n": len(vals), "mean": float(vals.mean()),
                                "sem": float(vals.std(ddof=1) / np.sqrt(len(vals)))}
    x = np.arange(len(SITES))
    w = 0.36
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        for k, (arm, color, off) in enumerate(
                (("mpc", dk.COLOR["mpc"], -w / 2),
                 ("choi", dk.COLOR["choi"], +w / 2))):
            m = [stats[arm][s]["mean"] for s in SITES]
            e = [stats[arm][s]["sem"] for s in SITES]
            ax.bar(x + off, m, width=w, color=color, label=arm.upper()
                   if arm == "mpc" else "Choi", yerr=e, capsize=3,
                   error_kw={"ecolor": dk.INK_2, "elinewidth": 1.2})
        ax.set_xticks(x, SITES)
        ax.set_ylabel("per-event r (mean ± SEM, r1-r3 pooled)")
        ax.set_title("Tracking by target site -- both arms follow every "
                     "biomimetic template; SHAM (flat ref) is the floor")
        ax.axhline(0, color=dk.AXIS, lw=0.8)
        ax.legend(frameon=False)
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, tc.ANA / "trk_persite.png")
    tc.write_json("_persite.json", stats)


if __name__ == "__main__":
    main()
