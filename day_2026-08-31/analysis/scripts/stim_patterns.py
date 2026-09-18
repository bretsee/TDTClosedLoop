"""stim_patterns -- what stimulus does each controller emit per touch site?
(acute #1, 2026-08-31; MPC vs Choi; pairs u1+u4; control channel y8)

Logic is shared with acute #2 via
day_2026-09-10/analysis/scripts/stim_patterns_common.py (imported by path).
Loading convention matches sci_common.py: no skip, tick 1 = row 0, onset
index = onset_tick - 1, capture truncated to min(len capture, len ref) -- the
MPC captures are 21601 / 21348 rows so their trailing events drop.

Outputs (analysis/): _stim_patterns.json, stim_overview.png, stim_table.png,
stim_charge.png, stim_site_<SITE>.png
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "day_2026-09-10" / "analysis" / "scripts"))
import stim_patterns_common as sp  # noqa: E402

DAY = "0831"


def main():
    res = sp.analyse_day(DAY)
    sp.fig_overview(res, ANA / "stim_overview.png")
    sp.fig_table(res, ANA / "stim_table.png")
    sp.fig_charge(res, ANA / "stim_charge.png")
    for s in res["sites"]:
        sp.fig_site(res, s, ANA / f"stim_site_{s}.png")
    sp.write_json(res, ANA / "_stim_patterns.json")
    print("\n" + sp.markdown_table(res))
    sim = res["similarity"]
    for arm, d in sim["between_site"].items():
        print(f"{arm}: between-site cmd corr (real sites) mean {d['offdiag_mean_real_sites']:.3f} "
              f"min {d['offdiag_min_real_sites']:.3f}; decode acc {sim['decoding'][arm]['accuracy']:.2f} "
              f"(chance {sim['decoding'][arm]['chance']:.2f}, null p95 {sim['decoding'][arm]['null_p95']:.2f}); "
              f"real-only {sim['decoding'][arm]['real_sites_only']['accuracy']:.2f}; "
              f"shape-only {sim['decoding'][arm]['shape_only_real_sites']['accuracy']:.2f}")
    print(f"ref between-site corr (real) {sim['reference_between_site']['offdiag_mean_real_sites']:.3f}")
    for k, r in res["runs"].items():
        print(f"{k}: {r['n_events']} events used of 100 ({r['n_ticks']} ticks)")
    print("stim_patterns (08-31): green")


if __name__ == "__main__":
    main()
