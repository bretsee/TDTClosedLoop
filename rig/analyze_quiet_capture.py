r"""Quiet-capture analysis: baseline volts, noise floor, line-noise fraction.

Run on the ~60 s no-stim Synapse block at the start of every rig session
(EXPERIMENT_MANUAL section 3). Produces the three numbers everything downstream
needs, plus the Wav-saving and stim-silence gates:

  1. GATE  Wav1 (and Wav2 if present) saved and NONZERO (the 2026-08-18 trap:
           streams live, disk saving off).
  2. GATE  sSig silent (this was supposed to be a QUIET capture).
  3. BANK  per-channel feature baseline in VOLTS = mean of the 6-sample
           mean-|x| feature, exactly what build_touch_reference --baseline and
           MPC targets need. (--signed reports the signed-mean baseline too.)
  4. BANK  per-channel noise floor (uV std).
  5. BANK  60 Hz + harmonics fraction of 5-200 Hz power (Welch) -> notch
           decision (fit-side first; no C++ change on animal day).

Usage:
  python rig\analyze_quiet_capture.py --block <block dir> [--channel k]
      [--feature-window 6] [--json quiet_report.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

NNC = Path(r"C:\Users\brets\Documents\Repositories\NNController")
sys.path.insert(0, str(NNC))
sys.path.insert(0, str(NNC / "src"))

from nncontroller.io.tdt import load_tdt_block  # noqa: E402


def resolve_block_dir(p: Path) -> Path:
    if list(p.glob("*.tsq")):
        return p
    kids = [k for k in p.iterdir() if k.is_dir() and list(k.glob("*.tsq"))]
    return kids[0] if len(kids) == 1 else p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--block", required=True)
    ap.add_argument("--channel", type=int, default=None,
                    help="1-based channel to highlight (the intended feature channel)")
    ap.add_argument("--feature-window", type=int, default=6)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    block = resolve_block_dir(Path(args.block))
    print(f"block: {block}")
    report: dict = {"block": str(block), "feature_window": args.feature_window}
    gates_ok = True

    blk = load_tdt_block(str(block), full_block=True)
    streams = list(blk.streams.keys()) if hasattr(blk, "streams") else []
    print(f"streams: {streams}")

    # ---- gate 1: Wav saving ------------------------------------------------
    for store in ("Wav1", "Wav2"):
        if store not in streams:
            msg = "MISSING" if store == "Wav1" else "absent (ok if not configured)"
            print(f"{store}: {msg}")
            if store == "Wav1":
                gates_ok = False
            report[f"{store.lower()}_saved"] = False
            continue
        d = np.asarray(blk.streams[store].data, dtype=np.float64)
        nz = bool(np.any(d))
        report[f"{store.lower()}_saved"] = nz
        if not nz:
            print(f"GATE FAIL: {store} is ALL ZERO -- disk saving is OFF in Synapse "
                  "(the 2026-08-18 trap). Enable saving and re-record.")
            gates_ok = False
        else:
            print(f"{store}: saved, nonzero ({d.shape})")

    # ---- gate 2: actually quiet -------------------------------------------
    if "sSig" in streams:
        s = np.asarray(blk.streams["sSig"].data, dtype=np.float64)
        n_nz = int(np.count_nonzero(s))
        report["ssig_nonzero_samples"] = n_nz
        if n_nz > 0:
            print(f"GATE FAIL: sSig has {n_nz} nonzero samples -- stim ran during "
                  "the 'quiet' capture. Re-record.")
            gates_ok = False
        else:
            print("sSig: silent (quiet confirmed)")

    if not report.get("wav1_saved"):
        print("VERDICT: GATE FAIL")
        return 1

    wav = np.asarray(blk.streams["Wav1"].data, dtype=np.float64)
    if wav.ndim == 1:
        wav = wav[None, :]
    fs = float(blk.streams["Wav1"].fs)
    n_ch, T = wav.shape
    dur = T / fs

    # units: same heuristic as the extractors -- volts if max|x| < 0.1
    max_abs = float(np.max(np.abs(wav)))
    if max_abs < 0.1:
        wav_v = wav                      # stored volts
        units = "volts (as stored)"
    else:
        wav_v = wav * 1e-6               # stored uV -> volts
        units = "uV -> volts (x1e-6)"
    print(f"Wav1: {n_ch} ch @ {fs:.4f} Hz, {dur:.1f} s, max|x| {max_abs:.4g} -> {units}")
    report.update({"n_channels": n_ch, "fs": fs, "duration_s": round(dur, 2),
                   "units_branch": units})

    # ---- baseline: mean 6-sample MAV feature, volts (matches the C++ loop) --
    w = args.feature_window
    nwin = T // w
    binned = wav_v[:, : nwin * w].reshape(n_ch, nwin, w)
    mav = np.mean(np.abs(binned), axis=2)              # (n_ch, nwin) rectified
    signed = np.mean(binned, axis=2)                   # signed-mean variant
    base_mav = mav.mean(axis=1)
    base_signed = signed.mean(axis=1)
    noise_uv = wav_v.std(axis=1) * 1e6

    # ---- line noise: Welch, 60 Hz + harmonics fraction of 5-200 Hz ---------
    from scipy.signal import welch
    f, pxx = welch(wav_v, fs=fs, nperseg=int(fs * 4), axis=1)
    band = (f >= 5) & (f <= 200)
    line = np.zeros(n_ch)
    for h in (60.0, 120.0, 180.0):
        m = np.abs(f - h) <= 1.0
        line += pxx[:, m].sum(axis=1)
    total = pxx[:, band].sum(axis=1)
    frac = np.where(total > 0, line / total, 0.0)

    print(f"\n ch | baseline V (MAV{w}) | signed V    | noise uV | 60Hz+harm frac")
    rows = []
    for c in range(n_ch):
        mark = "  <-- --channel" if args.channel == c + 1 else ""
        print(f" {c + 1:2d} | {base_mav[c]:.6e}     | {base_signed[c]:+.3e} | "
              f"{noise_uv[c]:8.2f} | {frac[c]:.3f}{mark}")
        rows.append({"ch": c + 1, "baseline_mav_v": float(base_mav[c]),
                     "baseline_signed_v": float(base_signed[c]),
                     "noise_uv": float(noise_uv[c]), "line_frac": float(frac[c])})
    report["channels"] = rows
    report["median_line_frac"] = float(np.median(frac))

    print(f"\nmedian 60Hz+harmonics fraction of 5-200 Hz power: {np.median(frac):.3f}")
    if np.median(frac) > 0.5:
        print("NOTE: line noise DOMINATES -- plan a fit-side notch (no C++ change).")
    if args.channel:
        c = args.channel - 1
        print(f"\nBANK for --baseline (ch {args.channel}): {base_mav[c]:.6e} V"
              f"   (signed mode: {base_signed[c]:.3e} V)")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    print(f"VERDICT: {'OK' if gates_ok else 'GATE FAIL'}")
    return 0 if gates_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
