"""art64_common -- artifact-aware raw-LFP redo of the acute-2 (09-10) arms, 64 ch.

Port of day_2026-08-31/analysis/scripts/art_common.py to the 64-channel planar
array and the 09-10 blocks (Wav2 64 ch @ 24414 Hz, Plse, Scle, UDP1).

Pipeline (art64_01 -> art64_02 -> art64_03):
  1. per-channel excision window from the pulse-triggered average (hi-amp tercile)
  2. per run: excise [-0.4 ms, +window] around every Plse edge (linear interp),
     5-200 Hz zero-phase bandpass at 24 kHz, then the loop's own feature --
     rectified mean over the 240 samples (one tick) preceding each UDP1 packet --
     for CLEANED and RAW-bandpassed signals, aligned to the capture rows
  3. tracking r (lag 0 / best lag 0..6), per-event r, paired MPC-vs-Choi dr with
     bootstrap CI, cleaned vs the run-time feature r0 (tracking_*.json)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
DAY = HERE.parents[2]
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk          # noqa: E402
import spat_common as sc      # noqa: E402
import trk_common as tc       # noqa: E402

CACHE = ANA / "cache"
CACHE.mkdir(exist_ok=True)
FS_HI = 24414.0625
TICK = 240                      # samples per loop tick (frame-locked 6 x 40)
BAND = (5.0, 200.0)
PRE_MS = 0.4
CAP_MS = 4.0
FLOOR_MS = 1.0
CH = 64                         # the controlled feature channel (1-based)
LAGS = range(0, 7)
ART_TICKS = (0, 2)              # ticks after event onset excluded from per-event r

RUNS = [r for r in tc.RUNS if r in sc.BLOCK]      # the 10 live arm blocks


def block_path(run: str) -> Path:
    return dk.need(sc.LATER / sc.BLOCK[run])


def read_hi(run: str):
    """Wav2 (64,N) uV float32, Plse 1-D, Scle (8,N), fs, UDP1 (8,M) + ts."""
    import tdt
    blk = tdt.read_block(str(block_path(run)), store=["Wav2", "Plse", "Scle", "UDP1"])
    w2 = np.asarray(blk.streams.Wav2.data, dtype=np.float32)
    if float(np.max(np.abs(w2[:, :FS_HI.__int__()]))) < 0.1:      # volts -> uV
        w2 *= 1e6
    pl = np.asarray(blk.streams.Plse.data).ravel()
    scl = np.asarray(blk.streams.Scle.data)
    fs = float(blk.streams.Wav2.fs)
    U = np.asarray(blk.scalars["UDP1"].data)
    ts = np.asarray(blk.scalars["UDP1"].ts).ravel()
    return w2, pl, scl, fs, U, ts


def pulse_onsets(pl):
    thr = 0.5 * float(np.max(np.abs(pl))) if np.max(np.abs(pl)) > 0 else 0.5
    on = pl > thr
    idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
    if on[0]:
        idx = np.concatenate([[0], idx])
    return idx


def pulse_amps(scl, idx, fs):
    """Commanded amplitude (uA) per carrier pulse: max |Scle| over words within 2 ms."""
    env = np.abs(scl).max(axis=0)
    w = int(round(0.002 * fs))
    n = env.size
    return np.array([env[i:min(i + w, n)].max() for i in idx])


def excise_interp(x, idx, fs, start_ms_per_ch, end_ms_per_ch):
    """Vectorised linear interpolation across [i+start_ch, i+end_ch] for every pulse.

    x: (C, N) float32, modified IN PLACE. start/end in ms relative to the Plse
    edge (start may be negative), (C,) arrays or scalars. Consecutive pulses are
    >= 9.8 ms apart and windows are <= 2.2 ms, so the segments never overlap.
    """
    C, N = x.shape
    st = np.broadcast_to(np.asarray(start_ms_per_ch, float), (C,))
    en = np.broadcast_to(np.asarray(end_ms_per_ch, float), (C,))
    for ch in range(C):
        a_off = -int(round(st[ch] * 1e-3 * fs))
        b_off = int(round(en[ch] * 1e-3 * fs))
        L = a_off + b_off
        if L <= 0:
            continue
        a = idx - a_off
        ok = (a >= 0) & (a + L < N)
        a = a[ok]
        ramp = np.arange(L + 1, dtype=np.float32) / L
        ya = x[ch, a]
        yb = x[ch, a + L]
        seg = ya[:, None] + (yb - ya)[:, None] * ramp[None, :]
        x[ch, a[:, None] + np.arange(L + 1)[None, :]] = seg.astype(np.float32)
    return x


def bandpass_hi(x, fs=FS_HI, chunk=8):
    """5-200 Hz zero-phase bandpass at 24 kHz, channel-chunked (memory)."""
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, BAND, btype="bandpass", fs=fs, output="sos")
    out = np.empty_like(x, dtype=np.float32)
    for c0 in range(0, x.shape[0], chunk):
        out[c0:c0 + chunk] = sosfiltfilt(sos, np.asarray(x[c0:c0 + chunk], np.float64), axis=-1).astype(np.float32)
    return out


def tick_mav(x, ts, fs=FS_HI, tick=TICK):
    """Rectified mean over the `tick` samples preceding each UDP1 packet time.

    x: (C, N); ts: (M,) packet times (s). Returns (M, C) float32; packets whose
    window falls outside the record get NaN.
    """
    C, N = x.shape
    i1 = np.round(ts * fs).astype(np.int64)
    i0 = i1 - tick
    ok = (i0 >= 0) & (i1 <= N)
    out = np.full((ts.size, C), np.nan, np.float32)
    ax = np.abs(x)
    cs = np.concatenate([np.zeros((C, 1), np.float64), np.cumsum(ax, axis=1, dtype=np.float64)], axis=1)
    out[ok] = ((cs[:, i1[ok]] - cs[:, i0[ok]]) / tick).T.astype(np.float32)
    return out


def align_capture(run: str, U, ts):
    """Map capture rows to UDP1 packets: first commanded pulse in both.

    Returns (k0_cap, j0_blk): capture row index and UDP1 packet index of the
    first nonzero command, and the row count checks.
    """
    import pandas as pd
    arm, cap, ref, tj, sch = tc.RUNS[run]
    d = pd.read_csv(dk.need(DAY / cap))
    u = d[[f"u{k}" for k in range(1, 9)]].to_numpy()
    k0 = int(np.flatnonzero(u.max(axis=1) > 1e-9)[0])
    j0 = int(np.flatnonzero(U.max(axis=0) > 1e-9)[0])
    return k0, j0, len(d), U.shape[1]


def pearson(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok] - a[ok].mean(), b[ok] - b[ok].mean()
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / den) if den > 0 else float("nan")


def boot_ci(x, nboot=5000, seed=0):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(nboot, len(x)), replace=True).mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def write_json(name, payload):
    p = ANA / name
    p.write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    print(f"wrote {p}")
    return p
