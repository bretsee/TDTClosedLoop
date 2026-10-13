"""art64_02: artifact-cleaned per-tick features for every live arm block.

Per run: Wav2 64 ch @ 24 kHz -> excise [start_ch, end_ch] ms around every Plse
edge (the artifact peak sits ~1 ms after the edge; linear interp) -> 5-200 Hz zero-phase bandpass -> rectified mean over the
240 samples preceding each UDP1 packet (the loop's own feature definition) for
CLEANED and RAW-bandpassed signals -> cache/art64_<run>.npz with the capture
alignment (first commanded pulse in capture rows <-> first UDP1 edge).

    python day_2026-09-10/analysis/scripts/art64_02_clean.py [--runs mpc_r1,choi_r1] [--example]
--example also saves a 24 kHz raw-vs-cleaned excerpt (ch64) for the deck.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art64_common as ac   # noqa: E402


def process(run, windows, example=False):
    t0 = time.time()
    w2, pl, scl, fs, U, ts = ac.read_hi(run)
    idx = ac.pulse_onsets(pl)
    amps = ac.pulse_amps(scl, idx, fs)
    idx = idx[amps > 0]
    k0, j0, n_cap, n_udp = ac.align_capture(run, U, ts)
    print(f"{run}: {w2.shape[0]} ch x {w2.shape[1] / fs:.1f} s, {idx.size} stim pulses, "
          f"capture rows {n_cap}, UDP1 packets {n_udp}, first pulse row {k0} <-> packet {j0}")
    raw_bp = ac.bandpass_hi(w2)
    mav_raw = ac.tick_mav(raw_bp, ts, fs)
    ex = None
    if example:
        ch = ac.CH - 1
        i = idx[min(2000, idx.size - 1)]
        a, b = i - int(0.01 * fs), i + int(0.05 * fs)
        ex = dict(t_ms=((np.arange(a, b) - i) / fs * 1e3).astype(np.float32),
                  raw=w2[ch, a:b].copy(), raw_bp=raw_bp[ch, a:b].copy())
    del raw_bp
    ac.excise_interp(w2, idx, fs, np.asarray(windows["start"]), np.asarray(windows["end"]))
    clean_bp = ac.bandpass_hi(w2)
    if example:
        ex["clean"] = w2[ac.CH - 1, a:b].copy()
        ex["clean_bp"] = clean_bp[ac.CH - 1, a:b].copy()
        ex["pulses_ms"] = ((idx[(idx >= a) & (idx < b)] - i) / fs * 1e3).astype(np.float32)
    del w2
    mav_clean = ac.tick_mav(clean_bp, ts, fs)
    del clean_bp
    out = ac.CACHE / f"art64_{run}.npz"
    np.savez_compressed(out, mav_clean=mav_clean, mav_raw=mav_raw, ts=ts.astype(np.float64),
                        k0=k0, j0=j0, n_cap=n_cap, n_udp=n_udp, n_pulses=idx.size,
                        **({f"ex_{k}": v for k, v in ex.items()} if ex else {}))
    print(f"  wrote {out.name} ({time.time() - t0:.0f} s): mav_clean {mav_clean.shape}, "
          f"ch64 mean clean {np.nanmean(mav_clean[:, ac.CH - 1]):.1f} uV vs raw {np.nanmean(mav_raw[:, ac.CH - 1]):.1f} uV")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=",".join(ac.RUNS))
    ap.add_argument("--example", action="store_true", help="store a 24 kHz excerpt on the first run")
    args = ap.parse_args()
    wj = json.loads((ac.CACHE / "art64_windows.json").read_text())
    windows = dict(start=wj["window_start_ms_per_ch"], end=wj["window_post_ms_per_ch"])
    for i, run in enumerate([r.strip() for r in args.runs.split(",") if r.strip()]):
        process(run, windows, example=(args.example and i == 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
