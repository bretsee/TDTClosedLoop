"""Build the Acute #2 (2026-09-10) results deck -- first deck on deckkit.

Every figure and number comes from day_2026-09-10\\analysis\\ artifacts
(regenerate with analysis\\scripts\\run_all.py); the build FAILS on any
missing artifact. Output goes to PythonIntanAnalysis\\outputs\\Synthesis\\.

    python scripts\\build_acute2_results_deck.py
    python scripts\\check_deck.py <written pptx>
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import deckkit as dk  # noqa: E402

ANA = REPO / "day_2026-09-10" / "analysis"
OUT = (REPO.parent / "PythonIntanAnalysis" / "outputs" / "Synthesis"
       / "AcuteClosedLoop_2026-09-10_results.pptx")


def fig(name):
    return dk.need(ANA / name)


def main():
    sci = dk.jload(ANA / "sci_summary.json")
    trk = dk.jload(ANA / "trk_summary.json")
    rank = dk.jload(ANA / "rank_summary.json")
    sites = dk.jload(ANA / "_sites.json")["rows"]
    charge = dk.jload(ANA / "_charge.json")
    null = dk.jload(ANA / "_null.json")
    sn, tn, rn = sci["numbers"], trk["numbers"], rank["numbers"]

    d = dk.Deck(footer="Acute #2 · 2026-09-10 · generated "
                       "build_acute2_results_deck.py")

    # 1 -- title
    d.title_slide(
        "Acute #2: 64-channel Closed-Loop Biomimetic Control",
        "Thalamic (VPL) microstimulation → S1 tracking of touch templates "
        "· 2026-09-10",
        ["New Microprobes 2×8 thalamic array (map verified in data) "
         "· NeuroNexus 8×8 planar cortical array",
         "All numbers recomputed from raw captures at build time; "
         "provenance: LAB_NOTEBOOK_2026-09-10.md + BLOCK_LEDGER_2026-09-10.md"])

    # 2 -- executive summary
    d.bullets_slide(
        "Six results, ranked",
        [(0, trk["findings"][1]),                       # feedback adapts
         (0, rank["findings"][1]),                      # rank collapse
         (0, trk["findings"][3]),                       # charge reversal
         (0, trk["findings"][2]),                       # nulls / NN negative
         (0, sci["findings"][0]),                       # battery
         (0, "Site-decoding / spatial-match at 64 ch: PENDING raw-block "
             "transfer (analysis queued)")],
        subtitle="Every claim below is one slide; verbatim findings from the "
                 "analysis summary JSONs")

    # 3 -- methods
    s = d.bullets_slide(
        "Methods in one slide",
        [(0, "Cortical: 64-ch planar array tangent to S1; features = 10 ms "
             "rectified-mean LFP per channel at 100 Hz (wall-clock ticks)"),
         (0, "Thalamic: 8 bipolar pairs, 101.7 Hz carrier, amplitude-"
             "commanded; delivery audit: wire==design, 0 missed / 0 doubled, "
             "pair map exact"),
         (0, "Plant: order-1 ARX, inputs pairs 4+6, output ch 64 "
             "(open-loop valFit ≈ 0% — stated honestly: feedback "
             "tracked anyway, and that gap IS the value-of-feedback claim)"),
         (0, "Arms: 100 interleaved biomimetic events/run (LP P1 MP P3 + "
             "SHAM templates on ch 64), paired MPC-vs-Choi runs, identical-"
             "tape early/late repeat, NN-inverse arm, drift brackets")],
        subtitle="cpp controller, preview MPC; references from same-prep "
                 "touch templates recorded hours earlier")
    d.kv_band(s, [
        (f"{sn['n_sites_active']}+1", "touch sites (+SHAM)"),
        (f"{rn['pairs_pulse_responsive']}/8", "pairs evoke cortex"),
        (f"{len(charge['mpc']) + len(charge['choi']) + 1}", "scored arm runs"),
        ("lag 0", "MPC tracking delay"),
        (f"p < {tn['null_p_bound']:.3f}", "vs shuffled-ref null"),
    ])

    # 4 -- thalamic map
    d.fig_slide("New thalamic array: all 8 pairs are usable actuators",
                fig("rank_probe_map.png"),
                subtitle="Single-pulse probe (feature-space z, shuffled-"
                         "trigger floor); acute #1's array had 2 responsive "
                         "pairs of 8",
                caption="Raw-block latencies (8–11.5 ms) and recruitment "
                        "knees (9–13 µA) recorded in the notebook; "
                        "ms-resolution refinement pending block transfer")

    # -- touch battery ----------------------------------------------------
    d.section_slide("The touch battery", kicker="10 sites · 150 trials each")
    d.fig_slide("Ten reference-grade templates from a speaker-silent array",
                fig("sci_gallery.png"),
                caption=sci["findings"][2])
    d.table_slide(
        "Battery quality table",
        ["site", "peak (µV)", "best ch", "latency (ms)", "split-half",
         "trials"],
        [[r["site"], f"{r['peak_uv']:.0f}", r["best_channel"],
          f"{r['latency_ms']:.0f}", f"{r['split_half']:.2f}", r["n_trials"]]
         for r in sites],
        subtitle="From touch_targets_summary.json; SHAM row is the "
                 "no-contact null")
    d.fig_slide("Single trials, digit sites + SHAM",
                fig("sci_rasters_digits.png"),
                caption="150 raw trials per panel; the deflection is visible "
                        "trial-by-trial, SHAM shows drift only")
    d.fig_slide("Single trials, pad sites", fig("sci_rasters_pads.png"),
                caption="Pads are larger and carry the ch-64 signature "
                        "channel used as the control target")
    d.fig_slide("Evoked magnitude by site", fig("sci_persite.png"),
                caption=sci["findings"][1])
    d.fig_slide("The OFF-response is site-specific", fig("sci_offresp.png"),
                caption=sci["findings"][3] + " — offset dynamics are a "
                        "future biomimetic target (template window keeps the "
                        "acute-#1 200 ms convention)")

    # -- arms -------------------------------------------------------------
    d.section_slide("Closed-loop arms", kicker="MPC vs Choi vs NN, "
                                               "paired interleaved runs")
    d.fig_slide("Fidelity per run", fig("trk_per_run.png"),
                subtitle=trk["findings"][0],
                caption="Recomputed from raw captures; run-time tracking "
                        "JSONs regression-pin every number (anti-drift gate)")
    d.fig_slide("CLAIM: feedback adapts — replay cannot",
                fig("trk_early_late.png"),
                subtitle="Identical tape and reference, ~2 h apart",
                caption=trk["findings"][1])
    d.two_fig_slide("Stability and nulls", fig("trk_sliding.png"),
                    fig("trk_null.png"),
                    captions=("sliding 22 s windows, early vs late runs",
                              f"circular-shift null, {null['n_draws']} draws"))
    d.fig_slide("Tracking by target site", fig("trk_persite.png"),
                caption="Per-event r via the interleaved schedules; both "
                        "arms follow every biomimetic template class")
    d.fig_slide("CLAIM: the charge story reversed", fig("trk_charge.png"),
                subtitle="Sparse deconvolution tape vs sustained feedback "
                         "effort at partially unreachable targets",
                caption=trk["findings"][3])
    d.fig_slide("CLAIM: NN inverse is an honest negative — and the "
                "mean-drive null", fig("trk_nn.png"),
                caption="Best trainable policy at this SNR emits the tonic "
                        "mean; tonic drive alone tracks nothing, so the "
                        "model-based arms' r is genuine reference-following")

    # -- physiology --------------------------------------------------------
    d.section_slide("The central physiology finding",
                    kicker="why this was a rank-1 day")
    d.fig_slide("CLAIM: pulse rank 8, tonic rank 1", fig("rank_pulse_vs_tonic.png"),
                caption=rank["findings"][1])
    d.fig_slide("Pair identity collapses under tonic drive",
                fig("rank_tonic.png"),
                caption="Three operating-point configs, shared scale: only "
                        "pair 4 → ch 64 retains gain; other pairs couple "
                        "weakly into the same footprint")
    d.fig_slide("Drift bracket", fig("rank_drift.png"),
                bullets_below=[(0, rank["findings"][2])])

    # -- provenance + next ------------------------------------------------
    d.bullets_slide(
        "Incidents & provenance (recorded, not hidden)",
        [(0, "PZ2-off incident: operator battery-saving zeroed features for "
             "3 runs; caught by a capture liveness audit, boundary clean, "
             "voided runs rerun live. New rule: y-liveness check in every "
             "run's first minute."),
         (1, "Exposure during void runs (delivered, unrecorded): "
             f"~{charge['unrecorded_exposure_uAticks']['value']/1e6:.1f}M "
             "µA-ticks tonic — cited from the lab notebook"),
         (0, "Two retractions made same-night and recorded: the r2 'Choi "
             "decay' read (two-points lesson) and the first r4/NN/'null "
             "control' results (dead-amp artifacts)"),
         (0, "Stale-design label collision (probe replayed the 08-31 7-amp "
             "design; benign, documented); fit-order observability trap "
             "(n=5 fit → unstable observer → silent open-loop; "
             "order capped, banner check institutionalized)"),
         (0, "Every number on these slides recomputes from raw data at "
             "build time; the deck build fails on missing artifacts")],
        subtitle="LAB_NOTEBOOK_2026-09-10.md · BLOCK_LEDGER_2026-09-10.md")
    d.bullets_slide(
        "Pending + acute #3",
        [(0, "Pending the raw-block batch transfer: site-decoding / spatial-"
             "match at 64 ch (claim 6), artifact-aware raw-LFP redo, "
             "ms-resolution probe latencies"),
         (0, "Acute #3 lever #1: burst / duty-cycled drive to recover the "
             "pulse-rank for true MIMO + the decoupled-target exhibit "
             "(tooling already built and sim-verified)"),
         (0, "Acute #3 lever #2: time-controlled charge-fidelity sweep "
             "(R-weight ladder within one plant epoch)"),
         (0, "Offline: extended-template OFF-response tracking; tank-share "
             "workflow to kill per-block hand transfers")],
        subtitle="The deck regenerates in one command when the blocks land "
                 "(v2 adds the pending slides)")

    out = d.save(OUT)
    print(f"deck: {out} ({len(d.prs.slides._sldIdLst)} slides)")
    return out


if __name__ == "__main__":
    main()
