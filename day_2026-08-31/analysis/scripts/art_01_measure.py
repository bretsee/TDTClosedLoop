"""Measure the per-pulse stim artifact at 24 kHz (Wav2) in each arm block.

Pulse-triggered averages per channel, stratified by commanded amplitude tercile.
Chooses a data-driven excision window per channel = time for |PTA| to stay
below 3 SD of the pre-pulse baseline (worst tercile), capped at CAP_MS.
Writes analysis/cache/art_windows.json and art_pta.png.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac

CAP_MS = 4.0        # hard cap (period is 9.83 ms)
PRE_MS = 0.4        # excision starts this far before pulse marker
FLOOR_MS = 1.0      # never excise less than this after the pulse

out_json = os.path.join(ac.CACHE, "art_windows.json")
plt = sc.style()

results = {}
fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharex=True)

for bi, (arm, (blkname, _)) in enumerate(sc.ARM_BLOCKS.items()):
    w2, pl, scl, fs, ts = ac.read_arm_hi(blkname)
    idx = ac.pulse_onsets(pl)
    amps = ac.pulse_amps(scl, idx, fs)
    print(f"{arm}: {idx.size} pulses, amp range {amps.min():.1f}-{amps.max():.1f} uA")

    pre = int(round(0.005 * fs))       # 5 ms pre
    post = int(round(0.0095 * fs))     # 9.5 ms post (~1 period)
    ok = (idx > pre) & (idx < w2.shape[1] - post)
    idx, amps = idx[ok], amps[ok]

    # amplitude terciles
    q = np.quantile(amps, [1 / 3, 2 / 3])
    tlab = np.digitize(amps, q)  # 0,1,2

    t_ms = (np.arange(-pre, post) / fs) * 1000.0
    ptas = np.zeros((3, 32, pre + post), np.float64)
    for t in range(3):
        sel = idx[tlab == t]
        # accumulate PTA without building a giant array
        acc = np.zeros((32, pre + post), np.float64)
        for i in sel:
            acc += w2[:, i - pre:i + post]
        ptas[t] = acc / sel.size
        # remove slow baseline offset (mean of -5..-1 ms)
        bl = ptas[t][:, t_ms < -1.0].mean(axis=1, keepdims=True)
        ptas[t] -= bl

    # recovery time per channel from worst (highest-amp) tercile
    windows = np.zeros(32)
    base_sd = ptas[2][:, t_ms < -1.0].std(axis=1)
    for ch in range(32):
        thr = 3.0 * max(base_sd[ch], 1.0)
        post_mask = t_ms >= 0
        seg = np.abs(ptas[2][ch, post_mask])
        tt = t_ms[post_mask]
        bad = seg > thr
        if not bad.any():
            rec = FLOOR_MS
        else:
            last_bad = tt[bad][-1]
            rec = min(max(last_bad + 0.2, FLOOR_MS), CAP_MS)
        windows[ch] = rec

    results[arm] = {
        "n_pulses": int(idx.size),
        "amp_terciles_uA": [float(amps.min()), float(q[0]), float(q[1]), float(amps.max())],
        "window_post_ms_per_ch": windows.round(3).tolist(),
        "window_pre_ms": PRE_MS,
        "cap_ms": CAP_MS,
        "peak_artifact_uV_per_ch_hi_tercile": np.abs(ptas[2]).max(axis=1).round(1).tolist(),
    }

    # panels: top = PTA overlay (hi tercile), bottom = window per channel
    ax = axes[0, bi]
    for ch in range(32):
        col = sc.RED if ch == 26 else sc.GREY
        ax.plot(t_ms, ptas[2][ch], lw=0.5, color=col, alpha=0.6)
    ax.axvline(0, color=sc.AMBER, lw=1)
    ax.axvspan(-PRE_MS, float(np.median(windows)), color=sc.AMBER, alpha=0.15)
    ax.set_title(f"{arm}: peak {np.abs(ptas[2]).max():.0f} µV", fontsize=10)
    ax.set_xlim(-3, 9.5)
    if bi == 0:
        ax.set_ylabel("PTA, hi-amp tercile (µV)")

    ax2 = axes[1, bi]
    ax2.bar(np.arange(1, 33), windows, color=sc.GREEN)
    ax2.axhline(CAP_MS, color=sc.RED, lw=0.8, ls="--")
    ax2.set_ylim(0, CAP_MS + 0.5)
    ax2.set_xlabel("channel")
    ax2.set_xlim(0, 33)
    if bi == 0:
        ax2.set_ylabel("excision window (ms)")

    # keep hi-tercile PTA for the summary block figure
    np.save(os.path.join(ac.CACHE, f"art_pta_{arm}.npy"), ptas)
    del w2

for ax in axes[0]:
    ax.set_xlabel("")
med_all = np.median([np.median(results[a]["window_post_ms_per_ch"]) for a in results])
fig.suptitle(f"Per-pulse artifact at 24 kHz: sharp ~1 ms transient, recovered by "
             f"~{med_all:.1f} ms (median excision window; amber = excised)", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(ac.ANA_DIR, "art_pta.png"))
print("wrote art_pta.png")

with open(out_json, "w") as f:
    json.dump(results, f, indent=1)
print("wrote", out_json)
for a in results:
    w = np.array(results[a]["window_post_ms_per_ch"])
    print(f"{a}: window median {np.median(w):.2f} ms, max {w.max():.2f} ms, "
          f"n@cap {(w >= CAP_MS).sum()}")
