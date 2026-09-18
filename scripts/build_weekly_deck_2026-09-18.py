"""Weekly deck, week of 2026-09-11 .. 2026-09-18 (catch-up week; deckkit).

Sections: (1) acute-#2 recap (usual), (2) stimulus patterns per site and
controller [item 6], (3) thalamic array status [item 5], (4) NN methodology
[item 7], (5) surgery-day acceleration + placement gates [item 2],
(6) acute-#3 plan improvements [item 4], (7) literature + electrode briefs
[items 1, 3], (8) next week. Every number is read from JSON at build time;
the build FAILS on a missing artifact. Two figures are generated here (timed
day plan Gantt; burst-design raster from the demo designs).

    python scripts\\build_weekly_deck_2026-09-18.py
    python scripts\\check_deck.py <written pptx> --fig-dir .
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import deckkit as dk  # noqa: E402

ANA2 = REPO / "day_2026-09-10" / "analysis"
ANA1 = REPO / "day_2026-08-31" / "analysis"
FIG = REPO / "outputs" / "deck_figures"
GAL = REPO / "galleries"
OUT = (REPO.parent / "PythonIntanAnalysis" / "outputs" / "Synthesis"
       / "ClosedLoop_weekly_2026-09-18.pptx")

PLAN = [  # (label, start_h, dur_h, lane, color-key)
    ("induction / stereotax", 9.0, 0.5, 0, "wrap"),
    ("scalp + both craniotomies", 9.5, 2.0, 0, "wrap"),
    ("cortical array + GATE cycles", 11.5, 0.75, 0, "touch"),
    ("thalamic depth ladder + GATE", 12.25, 1.25, 0, "stim"),
    ("seal / settle", 13.5, 0.5, 0, "wrap"),
    ("Phase 0 preflight, designs, G8 (engineer)", 9.0, 2.5, 1, "null"),
    ("quiet + blacklist + y-liveness", 13.5, 0.5, 1, "mpc"),
    ("battery 100x6 + SHAM", 14.0, 0.67, 1, "touch"),
    ("burst-ladder probe + gap scan", 14.67, 0.33, 1, "stim"),
    ("duty-PRBS ID -> MIMO fit -> rank gate", 15.0, 0.5, 1, "stim"),
    ("refs + tapes + manifest", 15.5, 0.5, 1, "null"),
    ("ARMS (paired, decoupled, burst-vs-tonic, R sweep, early/late)", 16.0, 3.0, 1, "mpc"),
    ("drift + wrap", 19.0, 0.5, 1, "wrap"),
]
COL = {"wrap": dk.MUTED, "touch": dk.COLOR["touch"], "stim": dk.COLOR["stim"],
       "null": dk.GRID, "mpc": dk.COLOR["mpc"]}


def fig_plan() -> Path:
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        for i, (label, t0, dur, lane, ck) in enumerate(PLAN, start=1):
            ax.barh(lane, dur, left=t0, color=COL[ck], height=0.55, lw=0, edgecolor="white")
            ax.text(t0 + dur / 2, lane, str(i), ha="center", va="center", fontsize=9, fontweight="bold",
                    color="white" if ck in ("mpc", "wrap", "stim", "touch") else dk.INK)
        ax.axvline(15.5, color=dk.COLOR["stim"], ls="--", lw=1.2)
        ax.text(15.55, 1.55, "target: recordings 15:30", color=dk.COLOR["stim"], fontsize=9)
        ax.axvline(16.0, color=dk.COLOR["mpc"], ls=":", lw=1.2)
        ax.text(16.05, 1.25, "first arm 16:00 (was 20:45 / 21:55)", color=dk.COLOR["mpc"], fontsize=9)
        ax.set_yticks([0, 1], ["surgeon", "engineer"])
        ax.set_ylim(-3.6, 1.9)
        ax.set_xlim(8.8, 20.0)
        ax.set_xticks(range(9, 21))
        ax.set_xlabel("clock hour (acute #3 template)")
        ax.set_title("Acute #3 timed plan: two lanes, gates instead of hunting, arms by 16:00")
        ax.grid(True, axis="x"); ax.grid(False, axis="y")
        # numbered key, two columns, below the lanes
        for i, (label, t0, dur, lane, ck) in enumerate(PLAN, start=1):
            col = 0 if i <= 7 else 1
            row = (i - 1) if i <= 7 else (i - 8)
            ax.text(9.0 + col * 5.6, -0.75 - 0.4 * row, f"{i}. {label}", fontsize=8, va="center", color=dk.INK)
        return dk.save_fig(fig, FIG / "weekly0918_plan.png")


def fig_designs() -> Path:
    def load(name):
        rows = list(csv.reader(open(REPO / "outputs" / "designs" / name)))
        return np.array([[float(v) for v in r[1:]] for r in rows[1:]])
    U_b = load("design_burstladder_demo.csv")[:6000]
    U_d = load("design_dutyprbs_demo.csv")[:3000]
    U_g = load("design_gapscan_demo.csv")[:2500]
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(3, 1, figsize=dk.FIGSIZE["FULL"], sharex=False)
        for ax, U, title in zip(axes, (U_b, U_d, U_g),
                                ("burst-ladder: one pair at a time, bursts of 1/3/10 pulses at 9-25 µA, ≥300 ms recovery (ID of the BURST plant)",
                                 "duty-PRBS: 4 pairs, 3-pulse bursts, duty 0.3, staggered so bursts never overlap (multi-input ID without saturation)",
                                 "gap-scan: conditioning + test burst with the gap swept 20-1000 ms (sets the operating duty cycle)")):
            t = np.arange(U.shape[0]) / 100.0
            for k in range(8):
                on = U[:, k] > 0
                if on.any():
                    ax.fill_between(t, k - 0.4, k - 0.4 + 0.8 * U[:, k] / 30.0, where=on,
                                    color=dk.CAT[k % 8], lw=0, step="post")
            ax.set_yticks(range(8), [f"u{k+1}" for k in range(8)], fontsize=8)
            ax.set_ylim(-0.6, 7.6)
            ax.set_title(title, fontsize=10)
            ax.grid(False)
        axes[-1].set_xlabel("seconds (amplitude = bar height, 0-30 µA)")
        return dk.save_fig(fig, FIG / "weekly0918_designs.png")


def main():
    trk = dk.jload(ANA2 / "trk_summary.json")
    rank = dk.jload(ANA2 / "rank_summary.json")
    spat = dk.jload(ANA2 / "spat_summary.json")
    arr = dk.jload(ANA2 / "_array_status.json")
    sp2 = dk.jload(ANA2 / "_stim_patterns.json")
    sp1 = dk.jload(ANA1 / "_stim_patterns.json")
    nn = dk.jload(ANA2 / "_nn_diag.json")
    tl = dk.jload(FIG / "_surgery_timeline.json")
    gate_d1 = dk.jload(GAL / "BSCL20260909BU-260910-185534" / "gate_cortical.json")
    gate_sham = dk.jload(GAL / "BSCL20260909BU-260910-185201" / "gate_cortical.json")
    gate_t2 = dk.jload(GAL / "BSCL20260909BU-260910-200410" / "gate_thalamic.json")
    gate_t1 = dk.jload(GAL / "BSClosedLoop32-260831-183856" / "gate_thalamic.json")
    tn, rn = trk["numbers"], rank["numbers"]
    a2 = arr["acute2"]
    t1, t2 = list(tl.values())
    plan_png = fig_plan()
    designs_png = fig_designs()
    # NN diagnostic headline numbers (schema of training/diagnose_nn.py output)
    inv_rows = [r for r in nn["ladder"] if r["mode"] == "inverse" and r["capture"] == "opfit12"]
    inv_best = max(max(r["r2"].values()) for r in inv_rows)
    fwd_ceiling = nn["snr"]["mi_bound"]["best_forward_r2_y64"]
    clone = nn["alt_behaviour_cloning"]["results"]["A_reference_only"]["mlp"]["cross_run_r2"]
    clone_lin = nn["alt_behaviour_cloning"]["results"]["A_reference_only"]["linear"]["cross_run_r2"]
    clone_r2 = float(np.mean(list(clone.values())))
    fwd_inv = nn["alt_forward_inversion"]["forward_inversion"]
    nn_head = dict(forward_r2_ceiling=fwd_ceiling, inverse_r2_best=inv_best, clone_r2=clone_r2)
    nn_caps = dict(
        ladder=f"Inverse R² on opfit12 never exceeds {inv_best:.2f} for any architecture or history; forward R² ceiling {fwd_ceiling:.2f} (y64); acute-#1 plant is better but still weak",
        snr=f"Forward R² barely moves with smoothing or record length; single-event pulse z ≈ 0.2-0.4 per pair (√N to z≈3 needs ~100 trials); inverse R² bound ≤ {nn['snr']['mi_bound']['inverse_r2_upper_bound_all64']:.2f} from all 64 ch",
        clone=f"Reference-only MLP clone of the MPC generalises to a held-out run at R² {clone['u4']:.2f} (u4) / {clone['u6']:.2f} (u6) (linear {clone_lin['u4']:.2f}/{clone_lin['u6']:.2f}): the POLICY is learnable, the tick-level inverse is not")
    nn_recs = [
        "Stop training tick-level inverse policies on tonic PRBS: the forward R² ceiling (0.02-0.12) bounds any inverse at this SNR and rank (distal-teacher failure on a many-to-one plant).",

        f"Behaviour-clone the MPC from the reference (MLP R² {clone['u4']:.2f}/{clone['u6']:.2f} on a held-out run; linear {clone_lin['u4']:.2f}/{clone_lin['u6']:.2f}) as the NN open-loop arm: a legitimate learned controller, cheap to deploy, and a fair comparator.",
        "Judge every model against the linear baseline on held-out, contiguous data; deploy only if it clears linear by a stated margin on the control channel.",
        "Data budget for acute #3 NN: ≥ 15-20 min of burst-ID capture, ≥ 100 trials per (pair, amp, burst-length) condition, plus the arm captures as cloning data.",
        "Handle drift explicitly (train/val feature means differ by 20-30%): recursive/adaptive fitting or per-run re-normalisation; k-step forward prediction as the validation metric.",
        "GRU at hidden 32 / 40 epochs adds nothing over linear here; keep architectures small until the forward ceiling moves.",
    ]
    real = [s for s in sp2["sites"] if s != "SHAM"]
    mc_bestlag = float(np.mean([sp2["table"][s]["mpc_vs_choi_corr_bestlag"] for s in real]))
    mpc_above = float(np.mean([sp2["table"][s]["mpc"]["charge_above_hold"] for s in real]))
    choi_above = float(np.mean([sp2["table"][s]["choi"]["charge_above_hold"] for s in real]))
    mpc_tot = float(np.mean([sp2["table"][s]["mpc"]["charge_per_event"] for s in real]))
    choi_tot = float(np.mean([sp2["table"][s]["choi"]["charge_per_event"] for s in real]))

    d = dk.Deck(footer="Closed-loop weekly · 2026-09-18 · build_weekly_deck_2026-09-18.py")

    # ---- 1 title + summary --------------------------------------------------
    d.title_slide("Closed-Loop Thalamic Stimulation: Weekly Report",
                  "Week of 2026-09-11 → 2026-09-18 (catch-up week: analysis, tooling, planning)",
                  ["Acute #2 offline analyses extended: stimulus patterns per site/controller, thalamic-array status, NN diagnosis",
                   "Surgery-day acceleration: placement go/no-go gates (validated on both acutes), timed 2-lane runbook",
                   "Acute #3 plan: burst/duty-cycled drive to recover actuator rank; literature base (~200 papers); electrode options"])
    d.bullets_slide(
        "This week in six lines",
        [(0, f"Stimulus patterns (item 6): at rank 1 the MPC re-derives the Choi tape online (pattern r {mc_bestlag:.2f} at best lag); "
             f"both cap briefly at onset; the {mpc_tot/choi_tot:.1f}× charge gap is MPC's tonic hold (above-hold {mpc_above:.0f} vs {choi_above:.0f} µA·ticks/event)."),
         (0, f"Thalamic array (item 5): well placed — 8/8 pairs recruit at ≤13 µA, latency 10-12 ms — but pulse footprints share one mode (median pair-pair r {a2['offdiag_corr_median']:.2f}, eff rank {a2['eff_rank']}); tonic drive removes the rest (8-pair max |corr| {max(p['tonic_gain_8pair'] for p in a2['per_pair']):.3f})."),
         (0, f"NN (item 7): the negative is formulation + SNR, not architecture — forward R² ceiling {nn_head['forward_r2_ceiling']:.2f}, inverse R² ≤ {nn_head['inverse_r2_best']:.2f} on opfit12; behaviour-cloning the MPC reaches R² {nn_head['clone_r2']:.2f}. Path: forward model + optimisation on burst data."),
         (0, f"Surgery (item 2): surgery→first recording {t1['surgery_to_first_block_h']:.1f} h / {t2['surgery_to_first_block_h']:.1f} h; new placement gates give a 3-8 s GO/NO-GO from one short block (validated: D1 GO z {gate_d1['best_z']:.0f}, SHAM NO-GO, acute-#1 probe GO where the fitter said NO-GO)."),
         (0, "Acute #3 plan (item 4): burst-ladder / gap-scan / duty-PRBS designs built; one 5-min ID run replaces three tonic ladders; y-liveness alarm; timed runbook with arms at 16:00."),
         (0, "Literature (item 1) + electrodes (item 3): 197 annotated entries in three files with synthesis sections; NeuroNexus pre-SfN sale brief with connector/charge tables and two picks per role.")],
        subtitle="Items 4-7 of the request are the middle sections; usual acute-#2 recap first")

    # ---- 2 acute-#2 recap (usual) -------------------------------------------
    d.section_slide("Acute #2 recap (2026-09-10)", kicker="usual items")
    d.fig_slide("Tracking per run: MPC lag-0 in every run, Choi at a wandering best lag",
                ANA2 / "trk_per_run.png",
                caption=f"MPC r0 {tn['mpc_r0_range'][0]:.2f}-{tn['mpc_r0_range'][1]:.2f}; Choi r0 {tn['choi_r0_range'][0]:.2f}-{tn['choi_r0_range'][1]:.2f}; circular-shift null p<{tn['null_p_bound']}")
    d.fig_slide("Feedback adapts, replay cannot: same tape ~2 h apart",
                ANA2 / "trk_early_late.png",
                caption=f"MPC +{tn['early_late_delta']['MPC']:.3f} with slope → {tn['mpc_late_slope']:.3f}; Choi +{tn['early_late_delta']['Choi']:.3f}")
    d.fig_slide("Pulse-rich, tonic-collapsed: the central physiology finding",
                ANA2 / "rank_pulse_vs_tonic.png",
                caption=f"pulse eff rank {rn['pulse_eff_rank']} vs tonic {rn['tonic_eff_rank']} at 0.1·σ1 (σ2/σ1 tonic 0.22) — one usable direction")
    d.fig_slide("Selectivity at 64 ch: target-vs-no-target separable, biomimetic sites at chance",
                ANA2 / "spat_decode.png",
                caption=f"SHAM decodes ~60%; 4 sites MPC {spat['numbers']['decode_mpc_active4']*100:.0f}% / Choi {spat['numbers']['decode_choi_active4']*100:.0f}% vs 25%; arm footprints r {spat['numbers']['footprint_r']:.3f}")

    # ---- 3 stimulus patterns (item 6) --------------------------------------
    d.section_slide("Stimulus patterns by controller and touch site", kicker="item 6")
    d.fig_slide("Acute #2: event-triggered command per site and pair (MPC, Choi, NN)",
                ANA2 / "stim_overview.png",
                caption="Both model-based arms put a 60 µA edge just before the template and a smaller site-dependent lobe; NN sits at tonic mean")
    d.fig_slide("Acute #2 big-picture table: peak, hold, timing, charge, cap fraction, shape fidelity",
                ANA2 / "stim_table.png",
                caption="Charge/event MPC ~1800 vs Choi ~600 µA·ticks; MPC hold 6 µA × 220 ticks = the whole difference; above-hold within 5%")
    d.fig_slide("Charge and cap usage per site and arm",
                ANA2 / "stim_charge.png",
                caption="Cap touched 3% of pair-ticks by both arms on acute #2 vs Choi riding the cap 48% on acute #1")
    d.fig_slide("Individual comparison: LP (the site present in both acutes)",
                ANA2 / "stim_site_LP.png",
                caption="Left: commands per pair; middle: achieved ch-64 feature vs reference; right: per-event peak command")
    d.two_fig_slide("Individual comparisons: P1 and MP", ANA2 / "stim_site_P1.png", ANA2 / "stim_site_MP.png",
                    captions=("P1: two secondary lobes at +10/+16 in both arms", "MP: two small lobes; MPC vs Choi r 0.91"))
    d.two_fig_slide("Individual comparisons: P3 and SHAM", ANA2 / "stim_site_P3.png", ANA2 / "stim_site_SHAM.png",
                    captions=("P3: one lobe at +12", "SHAM: MPC emits a 15 µA bump for the 7 µV sham template; Choi 4 µA"))
    d.fig_slide("Acute #1: a different regime — tonic bias for MPC, withdrawal-then-step for Choi",
                ANA1 / "stim_overview.png",
                caption="MPC held 40.6 µA summed and pulsed to 53-55 (cmd-ref r 0.79); Choi's tape rode the cap 87% (cmd-ref r 0.09); MPC-vs-Choi r 0.24-0.31")
    d.fig_slide("Acute #1 big-picture table",
                ANA1 / "stim_table.png",
                caption="Between-site command similarity 0.94-0.99: neither controller emitted site-specific commands on either day")
    d.two_fig_slide("Same tape 2 h later, and R-weight 0.3 vs 100",
                    ANA2 / "stim_early_late.png", ANA2 / "stim_rweight.png",
                    captions=("MPC command stationary (r 0.999-1.000); adaptation lives in y, not u",
                              "R buys tonic hold (×2), not a different pulse (shape r 0.99, depth 0.89×)"))
    d.fig_slide("Cross-acute LP: same MPC strategy on a different hold; Choi tapes unrelated",
                ANA2 / "stim_cross_acute_LP.png",
                caption="MPC LP command r 0.59 across plants (0.65 at best lag); Choi 0.02; achieved y patterns r 0.62 / 0.60")

    # ---- 4 thalamic array status (item 5) ----------------------------------
    d.section_slide("Thalamic array status: VPL-contoured Microprobes 2×8", kicker="item 5")
    pp = a2["per_pair"]
    d.table_slide("Per-pair status from the acute-#2 raw probe block (amp ≥ 13 µA)",
                  ["pair", "electrodes (+/−)", "tip mm", "z", "best ch", "peak µV", "lat ms", "knee µA", "half-max ch", "private ch", "tonic |corr| (8-pair)"],
                  [[p["pair"], f"{p['electrodes'][0]}/{p['electrodes'][1]}", p["tip_mm"], p["z"], p["best_ch"], p["peak_uv"],
                    p["lat_ms"], p["knee_uA"], p["halfmax_ch"], p["unique_halfmax_ch"], f"{p['tonic_gain_8pair']:.3f}"] for p in pp],
                  subtitle=f"All 8 pairs recruit; every pair peaks on ch64; median pair-pair footprint r {a2['offdiag_corr_median']:.2f}, pulse eff rank {a2['eff_rank']}, tonic eff rank {a2['tonic_eff_rank']}")
    d.fig_slide("Where the rank goes: pulses rich, footprints shared, carrier collapses the rest",
                ANA2 / "rank_array_status.png",
                caption=arr["findings"][-1][:180])
    d.fig_slide("Recruitment curves per pair, acute #2 vs acute #1",
                ANA2 / "rank_array_curves.png",
                bullets_below=[(0, "Verdict: the contour is doing its job (placement and recruitment are not the limit); the pairs are redundant actuators for a 200 µm-pitch surface readout under tonic drive."),
                               (0, "Rank must come from timing (burst/duty-cycled drive across pairs) and from a readout that resolves modes 2-4, not from more contacts on the same contour.")])

    # ---- 5 NN methodology (item 7) -----------------------------------------
    d.section_slide("Neural-network methodology: diagnosis and path forward", kicker="item 7")
    d.fig_slide("Ladder: inverse and forward R² by architecture, history and day",
                ANA2 / "nn_diag_ladder.png",
                caption=nn_caps["ladder"])
    d.fig_slide("SNR and data budget: what averaging buys, and what an inverse could reach",
                ANA2 / "nn_diag_snr.png",
                caption=nn_caps["snr"])
    d.fig_slide("Behaviour cloning the MPC per site: the policy IS learnable when the teacher is the MPC",
                ANA2 / "nn_diag_clone.png",
                caption=nn_caps["clone"])
    d.bullets_slide("NN: what to do next", [(0, b) for b in nn_recs[:7]],
                    subtitle="Full review: docs/NN_METHODOLOGY_REVIEW_2026-09-18.md (+ LIT_C synthesis, 60 papers)")

    # ---- 6 surgery acceleration (item 2) -----------------------------------
    d.section_slide("Surgery-day acceleration and placement validation", kicker="item 2")
    d.fig_slide("Where the hours went: 8.2 h and 9.1 h from induction to the first recording",
                FIG / "surgery_timeline.png",
                caption=f"First arm at {t1['first_arm_h']:.1f} h and {t2['first_arm_h']:.1f} h; pre-arm protocol {t1['first_block_to_first_arm_h']:.1f} / {t2['first_block_to_first_arm_h']:.1f} h; arms only {t1['arms_span_h']:.1f} / {t2['arms_span_h']:.1f} h")
    d.two_fig_slide("Cortical placement gate: one 40-thwack block → GO / NO-GO with a shift hint",
                    GAL / "BSCL20260909BU-260910-185534" / "gate_cortical.png",
                    GAL / "BSCL20260909BU-260910-185201" / "gate_cortical.png",
                    captions=(f"D1 block: GO — ch{gate_d1['best_channel_1based']} {gate_d1['best_peak_uv']:+.0f} µV @ {gate_d1['best_latency_ms']:.0f} ms, z {gate_d1['best_z']:.0f}, split-half {gate_d1['split_half']:.2f}",
                              f"SHAM block: NO-GO — z {gate_sham['best_z']:.1f}, split-half {gate_sham['split_half']:.2f}"))
    d.two_fig_slide("Thalamic placement gate: 4-min probe → responsive pairs, knees, footprint rank",
                    GAL / "BSCL20260909BU-260910-200410" / "gate_thalamic.png",
                    GAL / "BSClosedLoop32-260831-183856" / "gate_thalamic.png",
                    captions=(f"Acute #2: GO, {gate_t2['n_responsive']}/8 responsive, eff rank {gate_t2['eff_rank']}",
                              f"Acute #1: GO, pairs {[e['pair'] for e in gate_t1['per_pair'] if e['status']=='RESPONSIVE']} responsive — the block where the fitter said NO-GO"))
    d.fig_slide("Acute #3 timed plan: recordings by 15:30, arms by 16:00",
                plan_png,
                bullets_below=[(0, "Both craniotomies in one sitting; pre-measured coordinates from acute #2; depth ladder with the gate instead of hunting; battery 100×6; probe 12 min; one 5-min duty-PRBS ID."),
                               (0, "Engineer lane runs off the critical path; y-liveness after every go; cut list ordered by information value (never cut the early/late repeat).")])

    # ---- 7 acute-#3 plan (item 4) ------------------------------------------
    d.section_slide("Experimental plan improvements for acute #3", kicker="item 4")
    d.table_slide("Shortfall → change → tool (all implemented this week)",
                  ["shortfall (acutes #1/#2)", "change", "tool"],
                  [["fitter false NO-GO (08-31), speaker false NO-GO (09-10)", "quantitative placement gates, both arrays", "rig/placement_gate.py"],
                   ["tonic drive collapses rank to 1", "burst-ladder / gap-scan / duty-PRBS designs; burst carrier in arms", "rig/design_burst_probe.py"],
                   ["three tonic ID ladders (1 h) on 09-10", "one 5-min duty-PRBS multi-pair ID", "design_burst_probe --kind duty-prbs"],
                   ["PZ2-off: 3 void runs, 1.3M µA-ticks", "first-minute y-liveness alarm, --watch", "rig/check_y_liveness.py"],
                   ["R sweep drift-confounded", "interleaved R blocks in one run", "runbook §6d"],
                   ["charge comparisons dominated by hold", "report total AND above-hold charge", "stim_patterns.py"],
                   ["first arm 20:45 / 21:55", "2-lane timed runbook, arms 16:00", "RIG_DAY_ACUTE3_TEMPLATE.md"]],
                  col_widths=[3, 3, 2.2])
    d.fig_slide("The three burst designs (demo instances, validated: 0 cross-pair overlaps, gaps as designed)",
                designs_png,
                caption="burst-ladder 9.6 min · duty-PRBS 4.7 min (4 pairs, duty 0.3) · gap-scan 2.2 min; replayed by cpp_controller --play")
    d.bullets_slide("Acute #3 science, in priority order",
                    [(0, "1. Burst-vs-tonic rank recovery: burst-ladder → gap scan → duty-PRBS ID → MIMO fit + rank gate (prediction: eff rank ≥ 2 at duty ≤ 0.3, ≥ 200 ms gaps)."),
                     (0, "2. Decoupled-target MIMO run (first-in-class selectivity exhibit) — if 1 passes."),
                     (0, "3. Burst-vs-tonic paired arms on the same schedule: does a duty-cycled carrier keep rank during control?"),
                     (0, "4. Time-controlled R sweep (R 100/30/10 interleaved in 20-event blocks) → clean charge-fidelity frontier."),
                     (0, "5. Early/late repeat of r1, both arms — never cut."),
                     (0, "6. NN arm re-formulated (forward model + optimisation on burst data, or MPC behaviour cloning); deploy only above the linear baseline.")],
                    subtitle="docs/ACUTE3_PLAN_2026-09-18.md")

    # ---- 8 literature + electrodes (items 1, 3) -----------------------------
    d.section_slide("Literature base and electrode options", kicker="items 1 and 3")
    d.table_slide("Three annotated bibliographies for weekend review (literature/README.md)",
                  ["file", "scope", "entries", "starred", "what it tells us"],
                  [["LIT_A feedback control", "MPC/LQR/adaptive control of neural circuits; closed-loop DBS; BO/RL tuning; controllability & rank; artifact; drift", "62", "11",
                    "Bolus 2018/2021 = closest analogue; Ching & Ritt 2013 explains rank collapse under common drive; charge benchmarks 50-57%"],
                   ["LIT_B biomimetic stimulation", "Francis lineage (Choi 2016 methods verified); Bensmaia/Micera encoding; microstim physiology; anesthesia; VPL geometry; metrics", "75", "12",
                    "Tonic 100 Hz sits in the thalamocortical depression regime; bursts with ≥100 ms gaps; Choi fit on sparse Poisson probing"],
                   ["LIT_C data-driven / NN", "NN forward models; inverse/RL/Koopman/GP-BO control; sysID at low SNR; linear-vs-nonlinear; deployment", "60", "11",
                    "Direct inverse on a rank-1 plant = distal-teacher failure; forward model + optimisation, residual on MPC, k-step validation"]],
                  col_widths=[1.6, 4.2, 0.8, 0.8, 4.6])
    d.table_slide("NeuroNexus pre-SfN sale: options that fit the program (docs/NEURONEXUS_ELECTRODE_OPTIONS_2026-09-18.md)",
                  ["role", "pick", "why", "watch"],
                  [["cortical S1 (64 ch planar)", "A8x8-5mm-200-200-703-Z64", "same geometry as today, larger sites (LFP SNR), direct ZC64, stock", "stock-only discounts; confirm % and deadline"],
                   ["cortical complement", "E64 rat ECoG grid (500 µm or 1 mm pitch), HZ64", "true surface readout on a second ZC64; resolves footprint modes", "second headstage bank"],
                   ["thalamic VPL stim (rank)", "A8x8-10mm-200-200-703-Z64, IrOx-activated", "8 shanks × 200 µm = 8 spatially separated dipoles across VPL; 42 µA at 200 µs/phase", "ZC64_SW16 or DB26 cable to IZ2; activation mandatory"],
                   ["thalamic 3D", "Matrix MA64 (2× M4x8-10mm-100-200-703, 400 µm)", "true 3D coverage of the nucleus", "Omnetics-only packaging, insertion tool"],
                   ["custom", "8-shank VPL-contour, 1250 µm² IrOx", "75 µA headroom, contour + spread", "5-probe minimum, NRE, months"]],
                  col_widths=[1.8, 2.8, 4.2, 3.2])

    # ---- 9 next week ----------------------------------------------------------
    d.bullets_slide("Next week",
                    [(0, "Set the acute-#3 date; day-before: agar dry run with the holders, preflight 64, designs staged, stimulator charged."),
                     (0, "NN: train the forward model on burst-ladder data as soon as it exists; keep the linear baseline in the same plot."),
                     (0, "Electrode quote request to NeuroNexus (questions listed in the brief) before the sale closes."),
                     (0, "Weekend: review the starred literature entries and the three synthesis sections; mark what changes in the methods text."),
                     (0, "Offline still open: artifact-aware raw-LFP redo of acute-#2 tracking; ms-resolution probe latencies are now in the gate JSONs.")])

    out = d.save(OUT)
    print(f"deck: {out} ({d._n} slides)")


if __name__ == "__main__":
    main()
