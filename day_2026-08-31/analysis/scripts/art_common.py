"""Shared helpers for art_* (artifact-aware redo, workstream B1)."""
import json
import os

import numpy as np

import spat_common as sc  # reuse paths, block lists, style

ANA_DIR = sc.ANA_DIR
CACHE = os.path.join(ANA_DIR, "cache")

FS_HI = 24414.0625
FS_LO = 610.3515625
DECIM = 40  # FS_HI / FS_LO exactly

BAND = (5.0, 200.0)  # LFP band, Hz

QUIET_BLOCK = sc.TOUCH_BLOCKS["SHAM"]  # no stim: quiet-capture reference


def read_arm_hi(blkname):
    """Read Wav2 + Plse + Scle + UDP1 of an arm block (full length)."""
    import tdt
    blk = tdt.read_block(sc.block_path(blkname), store=["Wav2", "Plse", "Scle", "UDP1"])
    w2 = np.asarray(blk.streams.Wav2.data, dtype=np.float32)  # uV
    pl = np.asarray(blk.streams.Plse.data).ravel()
    scl = np.asarray(blk.streams.Scle.data)
    fs = float(blk.streams.Wav2.fs)
    ts = np.asarray(blk.scalars["UDP1"].ts).ravel()
    return w2, pl, scl, fs, ts


def pulse_onsets(pl):
    """Sample indices of Plse rising edges (+1 phase onset)."""
    on = pl > 0.5
    idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
    if on[0]:
        idx = np.concatenate([[0], idx])
    return idx


def pulse_amps(scl, idx, fs):
    """Per-pulse commanded amplitude (uA): max |Scle| over active rows within 2 ms."""
    act = np.abs(scl)
    env = act.max(axis=0)
    w = int(round(0.002 * fs))
    n = env.size
    return np.array([env[i:min(i + w, n)].max() for i in idx])


def excise_interp(w2, idx, fs, pre_ms, post_ms):
    """Linear-interpolate each channel across [i-pre, i+post] around every pulse.

    post_ms may be a scalar or a per-channel (32,) array. In-place on w2 copy.
    """
    x = w2.copy()
    n = x.shape[1]
    a_off = int(round(pre_ms * 1e-3 * fs))
    post = np.broadcast_to(np.atleast_1d(post_ms), (x.shape[0],))
    b_offs = np.round(np.asarray(post) * 1e-3 * fs).astype(int)
    for ch in range(x.shape[0]):
        b_off = b_offs[ch]
        row = x[ch]
        for i in idx:
            a = max(i - a_off, 0)
            b = min(i + b_off, n - 1)
            if b <= a:
                continue
            row[a:b + 1] = np.linspace(row[a], row[b], b - a + 1)
    return x


def band_decimate(x, fs):
    """5-200 Hz bandpass (zero-phase) then take every DECIM-th sample -> 610 Hz."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, BAND, btype="bandpass", fs=fs, output="sos")
    y = sosfiltfilt(sos, x, axis=-1)
    return y[..., ::DECIM].astype(np.float32)


def band610(x, fs=FS_LO):
    """Same 5-200 Hz bandpass applied to already-610 Hz data (touch Wav1)."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, BAND, btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=-1).astype(np.float32)


def save_json_part(key, obj):
    p = os.path.join(ANA_DIR, "art_summary.json")
    cur = {}
    if os.path.exists(p):
        with open(p) as f:
            cur = json.load(f)
    cur[key] = obj
    with open(p, "w") as f:
        json.dump(cur, f, indent=1, default=float)
