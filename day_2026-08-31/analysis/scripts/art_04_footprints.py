"""Cleaned-data spatial footprint correlations vs touch templates + deltas vs
spat_summary.json. Writes art_footprints.png and merges into art_summary.json.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac

plt = sc.style()
CACHE = ac.CACHE
fs = ac.FS_LO
good = np.array([c for c in range(32) if c not in sc.BLACKLIST_CH])
ARM_SITES = ["D1", "D2", "D3", "P2", "LP", "SHAM"]


def peak_profile(mean_wave, n_pre, w0=0.005, w1=0.040):
    a = n_pre + int(round(w0 * fs))
    b = n_pre + int(round(w1 * fs))
    seg = mean_wave[:, a:b]
    k = np.abs(seg[good]).max(axis=0).argmax()
    return seg[:, k].copy(), (a + k - n_pre) / fs * 1000.0


# touch templates (bandpassed, matched pipeline)
tpl_profiles, tpl_sites = [], []
for site in sc.SITE_ORDER:
    z = np.load(os.path.join(CACHE, f"touch_{site}_bp.npz"))
    m = z["trials"].astype(float).mean(axis=0)
    p, tms = peak_profile(m, int(z["n_pre"]), 0.005, 0.060)
    tpl_profiles.append(p); tpl_sites.append(site)
tpl_profiles = np.array(tpl_profiles)

# sanity: bp templates vs raw templates
raw_tpl_corr = {}
for i, site in enumerate(sc.SITE_ORDER):
    T = np.asarray(sc.load_template(site)["template"], float)
    p_raw, _ = peak_profile(T, 0, 0.005, 0.060)
    raw_tpl_corr[site] = float(np.corrcoef(p_raw[good], tpl_profiles[i][good])[0, 1])
print("bp vs raw touch template profile corr:", {k: round(v, 3) for k, v in raw_tpl_corr.items()})


def arm_profiles(tag):
    out = {}
    for arm_type, keys in (("MPC", ["MPC_r1b", "MPC_r2"]), ("Choi", ["Choi_r1", "Choi_r2"])):
        trs, sl = [], []
        for k in keys:
            z = np.load(os.path.join(CACHE, f"arm_{k}_{tag}.npz"))
            trs.append(z["trials"].astype(float)); sl.append(z["sites"])
            npre = int(z["n_pre"])
        trs = np.concatenate(trs); sl = np.concatenate(sl)
        for site in ARM_SITES:
            m = trs[sl == site].mean(axis=0)
            p, tms = peak_profile(m, npre)
            out[f"{arm_type} {site}"] = (p, tms, float(np.abs(p[good]).max()))
    return out


prof_clean = arm_profiles("clean")
prof_raw = arm_profiles("rawbp")

labels = list(prof_clean.keys())


def corr_matrix(profs):
    C = np.zeros((10, len(labels)))
    for i in range(10):
        for j, lab in enumerate(labels):
            C[i, j] = np.corrcoef(tpl_profiles[i][good], profs[lab][0][good])[0, 1]
    return C


C_clean = corr_matrix(prof_clean)
C_raw = corr_matrix(prof_raw)

# old values from spat_summary for the same 12 columns
with open(os.path.join(ac.ANA_DIR, "spat_summary.json")) as f:
    spat = json.load(f)
old_cols = spat["footprints"]["corr_cols_conditions"]
old_C = np.array(spat["footprints"]["corr_matrix"])
old_map = {lab: old_C[:, old_cols.index(lab)] for lab in labels if lab in old_cols}
C_old = np.stack([old_map[lab] for lab in labels], axis=1)

# matched-site correlation (touch site X vs arm "stim-for X"), excluding SHAM rows
match_old, match_clean = [], []
for j, lab in enumerate(labels):
    site = lab.split()[1]
    if site == "SHAM":
        continue
    i = sc.SITE_ORDER.index(site)
    match_old.append(C_old[i, j]); match_clean.append(C_clean[i, j])

# ---------------- figure ----------------
fig, axes = plt.subplots(1, 3, figsize=(17, 6.5), sharey=True)
for ax, M, ttl in ((axes[0], C_old, "OLD (Wav1 raw, artifact-contaminated)"),
                   (axes[1], C_clean, "CLEANED (Wav2 per-pulse excised, 5-200 Hz)"),
                   (axes[2], C_clean - C_old, "DELTA (cleaned - old)")):
    v = 1 if M is not C_clean - C_old else 1
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(10)); ax.set_yticklabels(sc.SITE_ORDER, fontsize=8)
    for i in range(10):
        for j in range(len(labels)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6,
                    color="white" if abs(M[i, j]) > 0.6 else "black")
    ax.set_title(ttl, fontsize=10)
    ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
fig.colorbar(im, ax=axes, fraction=0.015, pad=0.02).set_label("Pearson r")
med_old = float(np.median(C_old[1:, :]))
med_clean = float(np.median(C_clean[1:, :]))
fig.suptitle(f"Touch-footprint correlation of arm responses: median r {med_old:.2f} (old) -> "
             f"{med_clean:.2f} (cleaned); matched-site r {np.median(match_old):.2f} -> "
             f"{np.median(match_clean):.2f}", fontsize=12.5)
fig.savefig(os.path.join(ac.ANA_DIR, "art_footprints.png"), bbox_inches="tight")
print("wrote art_footprints.png")

ac.save_json_part("footprints_cleaned", {
    "labels": labels,
    "touch_rows": sc.SITE_ORDER,
    "corr_matrix_old": C_old.tolist(),
    "corr_matrix_rawbp_pipeline": C_raw.tolist(),
    "corr_matrix_clean": C_clean.tolist(),
    "median_r_old": med_old,
    "median_r_clean": med_clean,
    "median_r_rawbp": float(np.median(C_raw[1:, :])),
    "matched_site_r_old": [float(x) for x in match_old],
    "matched_site_r_clean": [float(x) for x in match_clean],
    "peak_uv_clean": {lab: prof_clean[lab][2] for lab in labels},
    "peak_ms_clean": {lab: prof_clean[lab][1] for lab in labels},
    "peak_uv_rawbp": {lab: prof_raw[lab][2] for lab in labels},
    "touch_template_bp_vs_raw_corr": raw_tpl_corr,
})
print(f"median r old {med_old:.3f} -> clean {med_clean:.3f}")
print("matched-site old:", np.round(match_old, 2))
print("matched-site clean:", np.round(match_clean, 2))
print("peaks clean:", {k: round(v[2]) for k, v in prof_clean.items()})
