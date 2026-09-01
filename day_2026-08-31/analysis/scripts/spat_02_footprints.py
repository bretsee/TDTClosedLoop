"""spat_footprints.png: spatial profiles at peak for touch / stim / arm conditions
plus touch-site x condition correlation matrix."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

plt = sc.style()
from matplotlib.gridspec import GridSpec

CACHE = os.path.join(sc.ANA_DIR, "cache")
fs = sc.FS_WAV
BL = sc.BLACKLIST_CH  # [26]
good = np.array([c for c in range(32) if c not in BL])


def peak_profile(mean_wave, n_pre, w0=0.005, w1=0.040):
    """32-vector at the time of max |mean| (blacklist excluded for peak pick)."""
    a = n_pre + int(round(w0 * fs))
    b = n_pre + int(round(w1 * fs))
    seg = mean_wave[:, a:b]
    k = np.abs(seg[good]).max(axis=0).argmax()
    return seg[:, k].copy(), (a + k - n_pre) / fs * 1000.0


profiles, labels, peak_uv, peak_ms, groups = [], [], [], [], []

# --- touch templates (peak over full template, window 5-60 ms to catch ~28 ms peak) ---
for site in sc.SITE_ORDER:
    T = np.asarray(sc.load_template(site)["template"], float)  # 32 x 122, t0=onset
    p, tms = peak_profile(T, 0, 0.005, 0.060)
    profiles.append(p); labels.append(f"touch {site}")
    peak_uv.append(np.abs(p[good]).max()); peak_ms.append(tms); groups.append("touch")

# --- stim probes: pairs 1 & 4 at amp 25 from rnd1 ---
pr = np.load(os.path.join(CACHE, "probe_rnd1.npz"))
ptr, pn_pre = pr["trials"].astype(float), int(pr["n_pre"])
for pair in (1, 4):
    m = ptr[(pr["pairs"] == pair) & (pr["amps"] == 25)].mean(axis=0)
    p, tms = peak_profile(m, pn_pre)
    profiles.append(p); labels.append(f"stim p{pair}@25")
    peak_uv.append(np.abs(p[good]).max()); peak_ms.append(tms); groups.append("stim")

# --- arm-evoked per site, pooled across the two runs of each arm ---
ARM_SITES = ["D1", "D2", "D3", "P2", "LP", "SHAM"]
arm_data = {}
for arm_type, keys in (("MPC", ["MPC_r1b", "MPC_r2"]), ("Choi", ["Choi_r1", "Choi_r2"])):
    trs, sites_l = [], []
    for k in keys:
        z = np.load(os.path.join(CACHE, f"arm_{k}.npz"))
        trs.append(z["trials"].astype(float)); sites_l.append(z["sites"])
        an_pre = int(z["n_pre"])
    trs = np.concatenate(trs); sites_l = np.concatenate(sites_l)
    arm_data[arm_type] = (trs, sites_l, an_pre)
    for site in ARM_SITES:
        m = trs[sites_l == site].mean(axis=0)
        p, tms = peak_profile(m, an_pre)
        profiles.append(p); labels.append(f"{arm_type} {site}")
        peak_uv.append(np.abs(p[good]).max()); peak_ms.append(tms); groups.append(arm_type)

profiles = np.array(profiles)          # n_cond x 32
n_touch = 10
cond_idx = np.arange(n_touch, len(labels))  # stim + arm conditions

# --- correlation matrix: touch sites x conditions, blacklist dropped ---
C = np.zeros((n_touch, len(cond_idx)))
for i in range(n_touch):
    for j, cj in enumerate(cond_idx):
        C[i, j] = np.corrcoef(profiles[i, good], profiles[cj, good])[0, 1]

# ---------------- figure ----------------
fig = plt.figure(figsize=(14, 10))
gs = GridSpec(2, 2, figure=fig, height_ratios=[1.05, 1.0], width_ratios=[1, 1],
              hspace=0.45, wspace=0.25)

# Panel A: profile matrix, each row normalized to its own peak
ax = fig.add_subplot(gs[0, :])
N = profiles / np.abs(profiles[:, good]).max(axis=1, keepdims=True)
im = ax.imshow(N, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1,
               interpolation="nearest")
ax.set_xticks([0, 7, 15, 23, 26, 31])
ax.set_xticklabels(["1", "8", "16", "24", "27*", "32"])
ax.set_xlabel("channel (27* blacklisted)")
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=8)
for r, (u, tm) in enumerate(zip(peak_uv, peak_ms)):
    ax.text(32.2, r, f"{u:.0f} µV @ {tm:.0f} ms", va="center", fontsize=7.5,
            color="black")
ax.axhline(n_touch - 0.5, color="black", lw=1.0)
ax.axhline(n_touch + 1.5, color="black", lw=1.0)
ax.axhline(n_touch + 7.5, color="black", lw=1.0)
ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
ax.set_title("Spatial profiles at response peak (each row / its own peak; sign kept). "
             "Touch and single-pulse stim probes share the ch 5–8 + 17–25 motif; "
             "arm event-locked averages are dominated by stim artifact (Choi peak at 5–13 ms; MPC by ch 23)",
             fontsize=10.5)
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.09)
cb.set_label("norm. amplitude")

# Panel B: correlation matrix with printed values
axc = fig.add_subplot(gs[1, :])
imc = axc.imshow(C, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto",
                 interpolation="nearest")
axc.set_xticks(range(len(cond_idx)))
axc.set_xticklabels([labels[c] for c in cond_idx], rotation=45, ha="right", fontsize=8)
axc.set_yticks(range(n_touch))
axc.set_yticklabels([labels[i] for i in range(n_touch)], fontsize=8)
for i in range(n_touch):
    for j in range(len(cond_idx)):
        v = C[i, j]
        axc.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                 color="white" if abs(v) > 0.6 else "black")
axc.spines["top"].set_visible(True); axc.spines["right"].set_visible(True)
med_real = np.median(C[1:, :])  # exclude touch SHAM row
med_probe = np.median(C[1:, :2])
axc.set_title(f"Pearson r, touch-site profile vs stim/arm profile (ch 27 dropped): "
              f"probes match touch (median r = {med_probe:.2f}); "
              f"arm averages do not (artifact-contaminated)", fontsize=11)
cbc = fig.colorbar(imc, ax=axc, fraction=0.025, pad=0.09)
cbc.set_label("r")

fig.suptitle("Spatial footprints: single-pulse thalamic stim reproduces the touch footprint "
             "(r 0.96–0.99); continuous-stim arm averages are artifact-dominated in 5–40 ms",
             fontsize=12, y=0.99)
fig.subplots_adjust(left=0.10, right=0.97, top=0.93, bottom=0.10)
out = os.path.join(sc.ANA_DIR, "spat_footprints.png")
fig.savefig(out)
print("wrote", out)

sc.save_json_part("footprints", {
    "labels": labels,
    "peak_uv": dict(zip(labels, map(float, peak_uv))),
    "peak_ms": dict(zip(labels, map(float, peak_ms))),
    "corr_rows_touch_sites": [labels[i] for i in range(n_touch)],
    "corr_cols_conditions": [labels[c] for c in cond_idx],
    "corr_matrix": C.tolist(),
    "median_r_real_touch_rows": float(med_real),
    "median_r_probes_vs_real_touch": float(med_probe),
    "alignment_note": ("arm events epoched at UDP1.ts[onset_tick-1]; alignment verified "
                       "(large event-locked deflections at offset 0; offset sweep rejected "
                       "alternatives). Arm averages contain overlapping stim artifact."),
})
print("median r (real touch rows):", med_real)
print("top-left of C:", np.round(C[:3, :4], 2))
