"""Artifact-cleaned reprocessing of the four arm blocks.

Pipeline per block (Wav2, 24414 Hz):
  1. pulse onsets from Plse rising edges
  2. excise [-0.4 ms, +per-channel window] around every pulse, linear interp
  3. 5-200 Hz bandpass (zero-phase) + decimate x40 -> 610.3516 Hz
  4. epoch at schedule event times (UDP1.ts[onset_tick-1]), baseline subtract
     -> cache/arm_{k}_clean.npz  (and _rawbp.npz: same pipeline, no excision)
  5. hold-only segments (tonic stim, no event) -> Welch PSD cleaned vs raw
Also: touch battery Wav1 re-epoched through the same 5-200 Hz bandpass
(-> cache/touch_{site}_bp.npz) and quiet-capture PSD from the SHAM block Wav2.

Run with --verify to process one epoch of Choi_r1 and write art_verify_epoch.png.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc
import art_common as ac
from scipy.signal import butter, sosfiltfilt, welch

VERIFY = "--verify" in sys.argv
PRE_S = 0.05
POST = sc.POST_SAMPLES

with open(os.path.join(ac.CACHE, "art_windows.json")) as f:
    WINDOWS = json.load(f)

sos_hi = butter(4, ac.BAND, btype="bandpass", fs=ac.FS_HI, output="sos")
sos_lo = butter(4, ac.BAND, btype="bandpass", fs=ac.FS_LO, output="sos")


def band_decim_chunked(x, sos):
    out = []
    for c0 in range(0, x.shape[0], 8):
        y = sosfiltfilt(sos, np.asarray(x[c0:c0 + 8], np.float64), axis=-1)
        out.append(y[:, ::ac.DECIM].astype(np.float32))
    return np.concatenate(out, axis=0)


def event_times(ts, schname):
    sch = json.load(open(os.path.join(sc.DAY_DIR, schname)))
    sites, times = [], []
    for e in sch["events"]:
        k = e["onset_tick"] - 1
        if 0 <= k < ts.size:
            sites.append(e["site"]); times.append(ts[k])
    return np.array(sites), np.array(times)


def hold_psd(x610, ev_t, fs=ac.FS_LO):
    """Welch PSD over hold-only segments: [t+1.2, min(t+2.2, next-0.3)] s."""
    segs = []
    for i, t in enumerate(ev_t):
        a = t + 1.2
        b = t + 2.2
        if i + 1 < len(ev_t):
            b = min(b, ev_t[i + 1] - 0.3)
        if b - a < 0.5:
            continue
        ia, ib = int(a * fs), int(b * fs)
        if ib <= x610.shape[1]:
            segs.append(x610[:, ia:ib])
    psds = []
    for s in segs:
        f, p = welch(s, fs=fs, nperseg=256, axis=-1)
        psds.append(p)
    return f, np.mean(psds, axis=0), len(segs)  # f, (32, nf), nseg


def process(arm, blkname, schname):
    w2, pl, scl, fs, ts = ac.read_arm_hi(blkname)
    idx = ac.pulse_onsets(pl)
    win = np.array(WINDOWS[arm]["window_post_ms_per_ch"])
    pre_ms = float(WINDOWS[arm]["window_pre_ms"])
    sites, ev_t = event_times(ts, schname)
    print(f"{arm}: {idx.size} pulses, {len(ev_t)} events, dur {w2.shape[1]/fs:.1f} s")

    clean_hi = ac.excise_interp(w2, idx, fs, pre_ms, win)
    x_clean = band_decim_chunked(clean_hi, sos_hi)
    del clean_hi
    x_raw = band_decim_chunked(w2, sos_hi)

    if VERIFY:
        return w2, x_clean, x_raw, idx, fs, sites, ev_t
    del w2

    for tag, x in (("clean", x_clean), ("rawbp", x_raw)):
        tr, n_pre, kept = sc.epoch(x, ac.FS_LO, 0.0, ev_t, pre_s=PRE_S, post_samples=POST)
        trb = sc.baseline_subtract(tr, n_pre)
        np.savez_compressed(os.path.join(ac.CACHE, f"arm_{arm}_{tag}.npz"),
                            trials=trb.astype(np.float32), n_pre=n_pre, fs=ac.FS_LO,
                            sites=np.array(sites)[kept])
        print(f"  {tag}: trials {trb.shape}")

    f, p_clean, nseg = hold_psd(x_clean, ev_t)
    _, p_raw, _ = hold_psd(x_raw, ev_t)
    np.savez_compressed(os.path.join(ac.CACHE, f"art_holdpsd_{arm}.npz"),
                        f=f, psd_clean=p_clean, psd_raw=p_raw, n_seg=nseg)
    print(f"  hold PSD from {nseg} segments")


if VERIFY:
    arm = "Choi_r1"
    blkname, schname = sc.ARM_BLOCKS[arm]
    w2, x_clean, x_raw, idx, fs, sites, ev_t = process(arm, blkname, schname)
    plt = sc.style()
    # pick the first non-SHAM event
    k = next(i for i, s in enumerate(sites) if s != "SHAM")
    t0 = ev_t[k]
    ch = 7  # ch 8 (1-based), touch best channel
    fig, axes = plt.subplots(3, 1, figsize=(12, 9))
    # 24 kHz zoom: 60 ms around onset
    i0, i1 = int((t0 - 0.02) * fs), int((t0 + 0.06) * fs)
    tt = (np.arange(i0, i1) / fs - t0) * 1000
    axes[0].plot(tt, w2[ch, i0:i1], color=sc.GREY, lw=0.6, label="raw Wav2")
    cl_hi = ac.excise_interp(w2[ch:ch + 1], idx, fs, 0.4,
                             WINDOWS[arm]["window_post_ms_per_ch"][ch])
    axes[0].plot(tt, cl_hi[0, i0:i1], color=sc.GREEN, lw=0.8, label="excised+interp")
    axes[0].set_title(f"Choi_r1 event {k+1} (site {sites[k]}), ch 8 at 24 kHz: "
                      "pulse transients removed, LFP between pulses kept")
    axes[0].legend(); axes[0].set_xlabel("ms from event onset")
    # 610 Hz: full epoch
    j0, j1 = int((t0 - PRE_S) * ac.FS_LO), int(t0 * ac.FS_LO) + POST
    tt6 = (np.arange(j0, j1) / ac.FS_LO - t0) * 1000
    axes[1].plot(tt6, x_raw[ch, j0:j1], color=sc.GREY, lw=0.9, label="bandpassed, no excision")
    axes[1].plot(tt6, x_clean[ch, j0:j1], color=sc.GREEN, lw=1.1, label="cleaned")
    axes[1].axvline(0, color=sc.AMBER, lw=1)
    axes[1].set_title("Same epoch at 610 Hz, 5-200 Hz band: artifact energy gone from the event window")
    axes[1].legend(); axes[1].set_xlabel("ms from event onset")
    # all channels cleaned, epoch image
    seg = x_clean[:, j0:j1] - x_clean[:, j0:j0 + int(PRE_S * ac.FS_LO)].mean(1, keepdims=True)
    im = axes[2].imshow(seg, aspect="auto", cmap="RdBu_r",
                        vmin=-150, vmax=150,
                        extent=[tt6[0], tt6[-1], 32.5, 0.5])
    axes[2].set_title("Cleaned epoch, all 32 channels (µV)")
    axes[2].set_xlabel("ms from event onset"); axes[2].set_ylabel("channel")
    fig.colorbar(im, ax=axes[2], fraction=0.02)
    fig.tight_layout()
    out = os.path.join(ac.ANA_DIR, "art_verify_epoch.png")
    fig.savefig(out)
    print("wrote", out)
    sys.exit(0)

# ---------- mass production ----------
for arm, (blkname, schname) in sc.ARM_BLOCKS.items():
    if os.path.exists(os.path.join(ac.CACHE, f"art_holdpsd_{arm}.npz")):
        print("skip", arm); continue
    process(arm, blkname, schname)

# ---------- touch battery through the same 5-200 Hz band ----------
for site in sc.SITE_ORDER:
    out = os.path.join(ac.CACHE, f"touch_{site}_bp.npz")
    if os.path.exists(out):
        print("skip", out); continue
    blk = sc.read_block(sc.TOUCH_BLOCKS[site])
    d, fs, t0s = sc.wav1_uv(blk)
    dbp = sosfiltfilt(sos_lo, d, axis=-1)
    on = sc.rising_edges_stream(blk.streams.nThw)
    tr, n_pre, kept = sc.epoch(dbp, fs, t0s, on, pre_s=PRE_S, post_samples=POST)
    trb = sc.baseline_subtract(tr, n_pre)
    np.savez_compressed(out, trials=trb.astype(np.float32), n_pre=n_pre, fs=fs)
    print(f"touch {site} bp: {trb.shape}")

# ---------- quiet-capture PSD (SHAM block Wav2 through same pipeline) ----------
qout = os.path.join(ac.CACHE, "art_quietpsd.npz")
if not os.path.exists(qout):
    import tdt
    blk = tdt.read_block(sc.block_path(ac.QUIET_BLOCK), store=["Wav2"])
    w2 = np.asarray(blk.streams.Wav2.data, dtype=np.float32)
    xq = band_decim_chunked(w2, sos_hi)
    f, p = welch(xq, fs=ac.FS_LO, nperseg=256, axis=-1)
    np.savez_compressed(qout, f=f, psd=p, dur_s=xq.shape[1] / ac.FS_LO)
    print("quiet PSD from", ac.QUIET_BLOCK)

print("done")
