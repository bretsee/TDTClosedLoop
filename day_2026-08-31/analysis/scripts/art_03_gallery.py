"""art_cleaned_gallery.png: raw vs artifact-cleaned event averages (ch 8) per arm/site,
with the touch template overlaid; art_hold_validation.png: hold-only PSD vs quiet capture.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac

plt = sc.style()
CACHE = ac.CACHE
CH = 7  # ch 8 1-based
SITES = ["D1", "D2", "D3", "P2", "LP", "SHAM"]


def load_arm(arm_type, tag):
    keys = {"MPC": ["MPC_r1b", "MPC_r2"], "Choi": ["Choi_r1", "Choi_r2"]}[arm_type]
    trs, sl = [], []
    for k in keys:
        z = np.load(os.path.join(CACHE, f"arm_{k}_{tag}.npz"))
        trs.append(z["trials"].astype(float)); sl.append(z["sites"])
        npre = int(z["n_pre"])
    return np.concatenate(trs), np.concatenate(sl), npre


touch_tpl = {}
for s in SITES:
    z = np.load(os.path.join(CACHE, f"touch_{s}_bp.npz"))
    touch_tpl[s] = (z["trials"].astype(float).mean(axis=0), int(z["n_pre"]))

fig, axes = plt.subplots(2, 6, figsize=(19, 7), sharex=True)
stats = {}
for r, arm_type in enumerate(["Choi", "MPC"]):
    Tr, Sr, npre_r = load_arm(arm_type, "rawbp")
    Tc, Sc_, npre_c = load_arm(arm_type, "clean")
    t = (np.arange(Tr.shape[2]) - npre_r) / ac.FS_LO * 1000
    for c, site in enumerate(SITES):
        ax = axes[r, c]
        mr = Tr[Sr == site].mean(axis=0)[CH]
        mc = Tc[Sc_ == site].mean(axis=0)[CH]
        tpl, tnp = touch_tpl[site]
        tt = (np.arange(tpl.shape[1]) - tnp) / ac.FS_LO * 1000
        ax.plot(t, mr, color=sc.GREY, lw=1.0, label="stim raw (bp)")
        ax.plot(t, mc, color=sc.GREEN, lw=1.2, label="stim cleaned")
        ax.plot(tt, tpl[CH], color=sc.AMBER, lw=1.0, label="touch template")
        ax.axvspan(10, 40, color=sc.GREY, alpha=0.08)
        ax.axvline(0, color="black", lw=0.5)
        pk_r = np.abs(mr[npre_r + 6:npre_r + 25]).max()   # 10-40 ms
        pk_c = np.abs(mc[npre_c + 6:npre_c + 25]).max()
        stats[f"{arm_type} {site}"] = (float(pk_r), float(pk_c))
        ax.set_title(f"{arm_type} {site}: 10-40 ms peak {pk_r:.0f}->{pk_c:.0f} µV",
                     fontsize=9)
        if c == 0:
            ax.set_ylabel(f"{arm_type} ch 8 mean (µV)")
        if r == 1:
            ax.set_xlabel("ms from event onset")
        if r == 0 and c == 0:
            ax.legend(fontsize=7, loc="lower right")
        ax.set_xlim(-50, 200)

red = np.mean([1 - v[1] / v[0] for v in stats.values() if v[0] > 0])
fig.suptitle("Event-triggered averages, raw vs per-pulse-artifact-cleaned (ch 8): pulse artifact removal "
             "changes the averages little - the large 0-25 ms deflection is an event-locked "
             "amplitude-step transient, not a per-pulse artifact", fontsize=12.5)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(os.path.join(ac.ANA_DIR, "art_cleaned_gallery.png"))
print("wrote art_cleaned_gallery.png; mean 10-40 ms peak reduction", f"{red*100:.1f}%")
ac.save_json_part("gallery_peaks_10_40ms_uv_raw_clean", stats)

# ---------------- hold-only PSD validation ----------------
q = np.load(os.path.join(CACHE, "art_quietpsd.npz"))
fq, pq = q["f"], np.median(q["psd"], axis=0)

fig2, axes2 = plt.subplots(1, 4, figsize=(16, 4), sharey=True)
val = {}
for i, arm in enumerate(sc.ARM_BLOCKS):
    z = np.load(os.path.join(CACHE, f"art_holdpsd_{arm}.npz"))
    f = z["f"]
    pr = np.median(z["psd_raw"], axis=0)
    pc = np.median(z["psd_clean"], axis=0)
    ax = axes2[i]
    ax.semilogy(f, pr, color=sc.GREY, lw=1.1, label="hold, raw (bp)")
    ax.semilogy(f, pc, color=sc.GREEN, lw=1.2, label="hold, cleaned")
    ax.semilogy(fq, pq, color=sc.AMBER, lw=1.1, label="quiet capture (no stim)")
    ax.axvline(101.7253, color=sc.RED, lw=0.6, ls="--")
    ax.set_xlim(0, 305); ax.set_xlabel("Hz")
    band = (f >= 5) & (f <= 200)
    # dB excess vs quiet in LFP band
    exc_r = 10 * np.mean(np.log10(pr[band] / np.interp(f[band], fq, pq)))
    exc_c = 10 * np.mean(np.log10(pc[band] / np.interp(f[band], fq, pq)))
    val[arm] = {"excess_dB_raw": float(exc_r), "excess_dB_clean": float(exc_c),
                "n_seg": int(z["n_seg"])}
    ax.set_title(f"{arm}: 5-200 Hz excess vs quiet {exc_r:.1f}->{exc_c:.1f} dB", fontsize=9.5)
    if i == 0:
        ax.set_ylabel("PSD (µV²/Hz, ch-median)"); ax.legend(fontsize=8)
fig2.suptitle("Cleaning validation on hold-only epochs (tonic stim, no events): cleaned baseline "
              "spectra approach the quiet capture; 101.7 Hz carrier line removed", fontsize=12)
fig2.tight_layout(rect=[0, 0, 1, 0.92])
fig2.savefig(os.path.join(ac.ANA_DIR, "art_hold_validation.png"))
print("wrote art_hold_validation.png")
ac.save_json_part("hold_validation", val)
for a, v in val.items():
    print(a, v)
