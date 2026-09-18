"""stim_patterns -- what stimulus does each controller emit per touch site?
(acute #2, 2026-09-10; MPC vs Choi vs NN; pairs u4+u6; control channel y64)

Outputs (analysis/):
  _stim_patterns.json        every number (per-run + pooled traces, per-event
                             metrics, similarity, decoding, table, extras)
  stim_overview.png          rows = sites, cols = pairs, arms overlaid (FULL)
  stim_table.png             heat-table of the big-picture metrics (WIDE)
  stim_charge.png            charge/event + cap fraction by site x arm (WIDE)
  stim_site_<SITE>.png       3-panel per-site comparison (FULL)
  stim_cross_acute_LP.png    LP on both acutes (different plants!) (WIDE)
  stim_early_late.png        MPC r1 vs r1_late (~2 h apart) per site (WIDE)
  stim_rweight.png           MPC r1 (R=100) vs r4b (R=0.3) per site (WIDE)
Shared logic lives in stim_patterns_common.py (also used by the 08-31 script).
"""
from pathlib import Path

import numpy as np

import stim_patterns_common as sp
import deckkit as dk

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
DAY = "0910"


def compare_runs(key_a, key_b, label_a, label_b, sites, pairs):
    """Per-site pattern corr + charge/hold/depth ratios between two runs."""
    ra, rb = sp.load_run(DAY, key_a), sp.load_run(DAY, key_b)
    ea, eb = sp.cut_events(ra, pairs), sp.cut_events(rb, pairs)
    sa, sb = sp.site_stats(ea, sites, pairs), sp.site_stats(eb, sites, pairs)
    ma = sp.metric_summary([sp.event_metrics(e, pairs) for e in ea], sites, pairs)
    mb = sp.metric_summary([sp.event_metrics(e, pairs) for e in eb], sites, pairs)
    out = {"a": key_a, "b": key_b, "per_site": {}}
    for s in sites:
        xa = sa[s]["mean_usum"] - sp.hold_of(sa[s]["mean_usum"])
        xb = sb[s]["mean_usum"] - sp.hold_of(sb[s]["mean_usum"])
        lag, cl = sp.xcorr_lag(xa, xb)
        out["per_site"][s] = {
            "pattern_corr_lag0": sp.safe_corr(xa, xb),
            "pattern_corr_bestlag": cl, "best_lag": int(lag),
            "pattern_corr_raw": sp.safe_corr(sa[s]["mean_usum"], sb[s]["mean_usum"]),
            "charge_ratio_b_over_a": mb[s]["sum"]["charge_total"]["mean"] / ma[s]["sum"]["charge_total"]["mean"],
            "hold_a": ma[s]["sum"]["hold"]["mean"], "hold_b": mb[s]["sum"]["hold"]["mean"],
            "depth_a": ma[s]["sum"]["depth"]["mean"], "depth_b": mb[s]["sum"]["depth"]["mean"],
            "peak_a": ma[s]["sum"]["peak"]["mean"], "peak_b": mb[s]["sum"]["peak"]["mean"],
            "cap_a": ma[s]["sum"]["cap_frac_pairmean"]["mean"],
            "cap_b": mb[s]["sum"]["cap_frac_pairmean"]["mean"],
            "y_peak_a": ma[s]["y_peak"]["mean"], "y_peak_b": mb[s]["y_peak"]["mean"]}
    v = out["per_site"]
    real = [s for s in sites if s != "SHAM"]
    out["summary"] = {
        "mean_pattern_corr_lag0_real_sites": float(np.mean([v[s]["pattern_corr_lag0"] for s in real])),
        "mean_charge_ratio": float(np.mean([v[s]["charge_ratio_b_over_a"] for s in sites])),
        "mean_depth_ratio": float(np.mean([v[s]["depth_b"] / v[s]["depth_a"] for s in real])),
        "mean_hold_a": float(np.mean([v[s]["hold_a"] for s in sites])),
        "mean_hold_b": float(np.mean([v[s]["hold_b"] for s in sites]))}
    panels = []
    for s in sites:
        d = v[s]
        panels.append((s, [(label_a, ra["arm"], "-", sa[s]["mean_usum"]),
                           (label_b, rb["arm"], "--", sb[s]["mean_usum"])],
                       f"r={d['pattern_corr_lag0']:.2f}, charge x{d['charge_ratio_b_over_a']:.2f}"))
    return out, panels


def cross_acute_lp(res10, out_png):
    res31 = sp.analyse_day("0831")
    d = {"note": "different animals/plants: 08-31 pairs u1+u4 -> y8 (32-ch); "
                 "09-10 pairs u4+u6 -> y64 (64-ch planar). Only LP is on both schedules.",
         "per_arm": {}}
    for arm in ("mpc", "choi"):
        a, b = res31["_stats"][arm]["LP"], res10["_stats"][arm]["LP"]
        xa = a["mean_usum"] - sp.hold_of(a["mean_usum"])
        xb = b["mean_usum"] - sp.hold_of(b["mean_usum"])
        lag, cl = sp.xcorr_lag(xa, xb)
        d["per_arm"][arm] = {
            "cmd_pattern_corr_lag0": sp.safe_corr(xa, xb), "cmd_pattern_corr_bestlag": cl,
            "best_lag_0910_vs_0831": int(lag),
            "y_pattern_corr_lag0": sp.safe_corr(a["mean_y"], b["mean_y"]),
            "hold_0831": sp.hold_of(a["mean_usum"]),
            "hold_0910": sp.hold_of(b["mean_usum"]),
            "peak_0831": float(a["mean_usum"].max()), "peak_0910": float(b["mean_usum"].max()),
            "n_0831": a["n"], "n_0910": b["n"]}
    d["table_0831"] = res31["table"]["LP"]
    d["table_0910"] = res10["table"]["LP"]
    with dk.deck_style() as plt:
        fig, (a1, a2) = dk.new_fig("WIDE", ncols=2)
        for arm in ("mpc", "choi"):
            for res, ls, tag in ((res31, "--", "08-31 u1+u4"), (res10, "-", "09-10 u4+u6")):
                st = res["_stats"][arm]["LP"]
                a1.plot(sp.TREL, st["mean_usum"], color=dk.COLOR[arm], ls=ls, lw=1.8,
                        label=f"{sp.ARM_LABEL[arm]} {tag}")
                a2.plot(sp.TREL, st["mean_y"] * 1e6, color=dk.COLOR[arm], ls=ls, lw=1.8,
                        label=f"{sp.ARM_LABEL[arm]} {res['ctrl']} {tag[:5]}")
        for res, ls, tag in ((res31, "--", "08-31"), (res10, "-", "09-10")):
            a2.plot(sp.TREL, res["_stats"]["mpc"]["LP"]["mean_r"] * 1e6, color=dk.COLOR["ref"],
                    ls=ls, lw=1.2, label=f"ref {tag}")
        for ax in (a1, a2):
            ax.axvline(0, color=dk.AXIS, lw=0.8)
            ax.set_xlim(-sp.PRE, sp.XMAX)
            ax.set_xlabel("ticks from template onset")
            ax.legend(frameon=False, fontsize=8)
        a1.set_ylabel("summed active-pair command (µA)")
        a1.set_title("LP command pattern, both acutes")
        a2.set_ylabel("achieved control feature, baseline-subtracted (µV)")
        a2.set_title("LP achieved response vs reference")
        fig.suptitle("Cross-acute LP: different plants (08-31: 32-ch, pairs 1+4 -> y8; "
                     "09-10: 64-ch planar, pairs 4+6 -> y64)", fontsize=12, fontweight="bold")
        dk.save_fig(fig, out_png)
    return d


def main():
    res = sp.analyse_day(DAY)
    sites, pairs = res["sites"], res["pairs"]
    sp.fig_overview(res, ANA / "stim_overview.png")
    sp.fig_table(res, ANA / "stim_table.png")
    sp.fig_charge(res, ANA / "stim_charge.png")
    for s in sites:
        sp.fig_site(res, s, ANA / f"stim_site_{s}.png")

    extras = {}
    el, panels = compare_runs("mpc_r1", "mpc_r1_late", "MPC r1", "MPC r1_late", sites, pairs)
    el_choi, _ = compare_runs("choi_r1", "choi_r1_late", "Choi r1", "Choi r1_late", sites, pairs)
    extras["early_late_mpc"] = el
    extras["early_late_choi"] = el_choi
    sp.fig_pattern_pairs(panels, "MPC r1 (solid) vs r1_late (dashed), same tape ~2 h apart: "
                         "summed command per site (mean over 20 events)",
                         ANA / "stim_early_late.png")
    rw, panels = compare_runs("mpc_r1", "mpc_r4b", "MPC r1 (R=100)", "MPC r4b (R=0.3)", sites, pairs)
    extras["rweight_r1_vs_r4b"] = rw
    sp.fig_pattern_pairs(panels, "MPC input penalty R=100 (r1, solid) vs R=0.3 (r4b, dashed): "
                         "summed command per site", ANA / "stim_rweight.png")
    extras["cross_acute_LP"] = cross_acute_lp(res, ANA / "stim_cross_acute_LP.png")
    res["extras"] = extras
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
    print("early/late MPC:", el["summary"])
    print("rweight:", rw["summary"])
    print("cross LP:", {a: {k: round(v, 3) if isinstance(v, float) else v for k, v in d.items()}
                        for a, d in extras["cross_acute_LP"]["per_arm"].items()})
    print("stim_patterns (09-10): green")


if __name__ == "__main__":
    main()
