"""Assemble art_summary.json findings for the artifact-aware redo (B1)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac

p = os.path.join(ac.ANA_DIR, "art_summary.json")
with open(p) as f:
    A = json.load(f)
with open(os.path.join(ac.CACHE, "art_windows.json")) as f:
    W = json.load(f)

# 5-45 Hz hold excess (analysis-relevant band; 10-40 ms window mean ~ <50 Hz)
q = np.load(os.path.join(ac.CACHE, "art_quietpsd.npz"))
fq, pq = q["f"], np.median(q["psd"], axis=0)
hold545 = {}
for arm in sc.ARM_BLOCKS:
    z = np.load(os.path.join(ac.CACHE, f"art_holdpsd_{arm}.npz"))
    f = z["f"]
    band = (f >= 5) & (f <= 45)
    qi = np.interp(f[band], fq, pq)
    hold545[arm] = {
        "excess_dB_raw": float(10 * np.mean(np.log10(np.median(z["psd_raw"], 0)[band] / qi))),
        "excess_dB_clean": float(10 * np.mean(np.log10(np.median(z["psd_clean"], 0)[band] / qi))),
    }
A["hold_validation_5_45Hz"] = hold545

fp = A["footprints_cleaned"]
mh = A["mahalanobis_cleaned"]
labels = fp["labels"]
C_old = np.array(fp["corr_matrix_old"])
C_clean = np.array(fp["corr_matrix_clean"])

choi_cols = [j for j, l in enumerate(labels) if l.startswith("Choi") and "SHAM" not in l]
mpc_cols = [j for j, l in enumerate(labels) if l.startswith("MPC") and "SHAM" not in l]

med = lambda M, cols: float(np.median(M[1:, cols]))  # exclude touch-SHAM row

Dc = np.array(mh["median_distance_matrix_clean"])
Do = np.array(mh["median_distance_matrix_old"])
rows = mh["arm_rows"]
mpc_rows = [i for i, r in enumerate(rows) if r.startswith("MPC") and "SHAM" not in r]
choi_rows = [i for i, r in enumerate(rows) if r.startswith("Choi") and "SHAM" not in r]

A["excision_spec"] = {
    "pre_ms": 0.4,
    "post_ms_median_per_block": {a: float(np.median(W[a]["window_post_ms_per_ch"])) for a in W},
    "cap_ms": 4.0,
    "fraction_of_record_excised_median": float(np.median(
        [(0.4 + np.median(W[a]["window_post_ms_per_ch"])) / 9.8304 for a in W])),
    "peak_artifact_uV_hi_tercile": {a: float(np.max(W[a]["peak_artifact_uV_per_ch_hi_tercile"])) for a in W},
}

A["findings"] = [
    ("PIPELINE: Wav2 24 kHz per-pulse excision (-0.4 to ~3.5-4.0 ms per channel, data-driven; "
     f"~{A['excision_spec']['fraction_of_record_excised_median']*100:.0f}% of record) + linear interp, "
     "5-200 Hz zero-phase bandpass, x40 decimate to 610 Hz; touch battery re-epoched through the same "
     "5-200 Hz band (bp templates r 0.996-1.000 vs raw, so touch side unchanged)."),
    ("CLEANING WORKS ON THE PER-PULSE ARTIFACT: 700-915 uV pulse transients removed; hold-only "
     "(tonic stim) spectra lose the 203 Hz harmonic and pulse broadband; a residual 101.7 Hz "
     "fundamental line remains (smooth <10 uV pulse-locked tail beyond 4 ms, not excisable at 100% "
     "duty). In the analysis-relevant 5-45 Hz band, hold excess vs quiet capture is "
     + ", ".join(f"{a} {hold545[a]['excess_dB_raw']:.1f}->{hold545[a]['excess_dB_clean']:.1f} dB"
                 for a in hold545)
     + " - i.e. baseline elevation is state/tonic-stim, not pulse artifact."),
    ("KEY NEW RESULT: the huge Choi event-locked deflection is NOT per-pulse artifact. Cleaning "
     "leaves Choi event averages nearly unchanged (10-40 ms ch-8 peaks 512-766 -> 511-748 uV, "
     "1-3% reduction). It is a slow event-locked transient time-locked to the amplitude step "
     "(single-trial ~2000 uV, starts ~1 pulse before nominal onset, trough 5-15 ms, recovered by "
     "~40 ms), absent in Choi SHAM (23 uV) where amplitude never steps. Whether electrode/amp "
     "settling or genuine strong-onset evoked LFP, it scales with the commanded step, not with site."),
    ("FOOTPRINT CORRELATION AFTER CLEANING: overall median r vs touch "
     f"{med(C_old, list(range(len(labels)))):.2f} -> {med(C_clean, list(range(len(labels)))):.2f}. "
     f"Choi matched-site r {np.median([fp['matched_site_r_old'][i] for i in range(5,10)]):.2f} -> "
     f"{np.median([fp['matched_site_r_clean'][i] for i in range(5,10)]):.2f} (anticorrelation STANDS). "
     f"MPC matched-site r {np.median([fp['matched_site_r_old'][i] for i in range(5)]):.2f} -> "
     f"{np.median([fp['matched_site_r_clean'][i] for i in range(5)]):.2f} (softens to ~0; MPC D1 "
     f"alone reaches r={fp['matched_site_r_clean'][0]:.2f}, but MPC responses are only 62-144 uV "
     "and ~0-correlated for the other four sites - no systematic touch-footprint recovery)."),
    ("MAHALANOBIS SITE IDENTITY - THE SELECTIVITY NEGATIVE STANDS: 5-way nearest-template accuracy "
     f"MPC {mh['accuracy_5way_old']['MPC']*100:.0f}% -> {mh['accuracy_5way_clean']['MPC']*100:.0f}% "
     f"(p={mh['pvalue_vs_chance_clean']['MPC']:.2f}), Choi {mh['accuracy_5way_old']['Choi']*100:.0f}% -> "
     f"{mh['accuracy_5way_clean']['Choi']*100:.0f}% (p={mh['pvalue_vs_chance_clean']['Choi']:.2f}) vs "
     "20% chance; ceiling touch LOO 51%. Median distances barely move: MPC "
     f"{np.median(Do[mpc_rows]):.1f} -> {np.median(Dc[mpc_rows]):.1f}, Choi "
     f"{np.median(Do[choi_rows]):.1f} -> {np.median(Dc[choi_rows]):.1f} (touch within-site 3.9). "
     "Choi confusions still collapse onto one column (D1); MPC onto D3/P2."),
    ("INTERPRETATION: artifact removal does NOT rescue the arms. Choi remains dominated by an "
     "amplitude-step transient anticorrelated with touch; MPC, once pulse-cleaned, produces small "
     "(~60-140 uV vs touch 300-700 uV) responses with no site-selective spatial structure - "
     "consistent with the rank~3 / non-selective coverage picture. Both negatives are now "
     "artifact-robust results, not artifacts."),
]

with open(p, "w") as f:
    json.dump(A, f, indent=1, default=float)
print("wrote", p)
for k in A["findings"]:
    print("-", k[:120])
