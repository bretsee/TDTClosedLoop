#!/usr/bin/env python3
"""check_envelope.py -- did the RZ2 actually deliver the envelope we sent?

Takes the CSV written by send_envelope.py and a recorded TDT block, extracts the
DELIVERED pulse amplitude per 10 ms bin from the `sSig` store, aligns the two by
cross-correlation, and reports per-channel correlation and slope.

What the numbers mean:
  corr   how faithfully delivered amplitude follows the commanded envelope.
         A slow sawtooth on a working path gives > 0.95. This is the pass/fail.
  slope  delivered units per commanded unit. Do NOT expect 1.0 -- sSig is in the
         stimulator's own units (typically uA) while the command is in the
         0-40 engineering scale. What matters is that slope is CONSTANT across
         channels and runs; that constant IS your units conversion.
  lag    delivered minus commanded, in ms. Expect a small positive lag (one
         control tick of transport plus the RZ2's own pipeline). A lag of
         hundreds of ms means something is buffering that should not be.

A high corr on the commanded channel and ~0 on every other channel is also the
channel-ROUTING check: it proves word k of the packet drives the pair you think
it does. Run send_envelope.py with --stagger to make that unambiguous. Note the
uncommanded-channel test uses the same peak-per-bin statistic, so it catches
GROSS mis-mapping (a whole channel driven by the wrong word) but not small
leakage: crosstalk a few percent of full scale stays under the noise floor of a
bin peak and reads as "quiet".

USAGE
    python rig/check_envelope.py --sent envelope_sent_saw.csv --block D:\\Data\\Block-1
    python rig/check_envelope.py --sent envelope_sent_saw.csv --block ... --plot out.png

Needs numpy and the `tdt` package -- use the analysis interpreter:
    ..\\PythonIntanAnalysis\\.venv\\Scripts\\python.exe rig\\check_envelope.py ...
"""

from __future__ import annotations

import argparse
import csv
import sys

import numpy as np


def load_sent(path: str):
    """Return (t_rel[n], U[n, count]) from a send_envelope.py log."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    ch_cols = [i for i, name in enumerate(header) if name.startswith("ch")]
    t_col = header.index("t_rel_s")
    t = np.array([float(r[t_col]) for r in rows[1:]], dtype=float)
    u = np.array([[float(r[i]) for i in ch_cols] for r in rows[1:]], dtype=float)
    return t, u


def load_delivered(block_path: str, store: str, bin_s: float):
    """Return (t[n], A[n, ch]) -- peak |sSig| per bin, i.e. delivered pulse
    amplitude on the same grid as the command.

    Peak-per-bin, not mean: sSig holds sparse biphasic pulses, so a mean over a
    10 ms bin mostly measures the silence between pulses and would scale with
    pulse RATE rather than pulse AMPLITUDE. The envelope is an amplitude.
    """
    if block_path.lower().endswith(".npz"):
        # Escape hatch: a saved [ch x n] extract plus fs. Lets the check run on
        # a machine without the tdt package, and makes this path testable.
        z = np.load(block_path)
        x = np.atleast_2d(np.asarray(z["data"], dtype=float))
        fs = float(z["fs"])
        start_time = float(z["start_time"]) if "start_time" in z else 0.0
        step = max(1, int(round(bin_s * fs)))
        n_bins = x.shape[1] // step
        if n_bins == 0:
            raise SystemExit("FAIL: extract is shorter than one %g s bin." % bin_s)
        trimmed = np.abs(x[:, : n_bins * step]).reshape(x.shape[0], n_bins, step)
        return np.arange(n_bins) * bin_s + start_time, trimmed.max(axis=2).T, fs

    import tdt
    blk = tdt.read_block(block_path, store=store)
    data = getattr(blk.streams, store)
    x = np.atleast_2d(np.asarray(data.data, dtype=float))
    fs = float(data.fs)
    step = max(1, int(round(bin_s * fs)))
    n_bins = x.shape[1] // step
    if n_bins == 0:
        raise SystemExit("FAIL: %s is shorter than one %g s bin." % (store, bin_s))
    trimmed = np.abs(x[:, : n_bins * step]).reshape(x.shape[0], n_bins, step)
    amp = trimmed.max(axis=2).T                      # [n_bins, ch]
    t = np.arange(n_bins) * bin_s + float(getattr(data, "start_time", 0.0))
    return t, amp, fs


def best_lag(cmd: np.ndarray, dev: np.ndarray, max_lag_bins: int):
    """Integer bin lag maximising correlation of dev(t+lag) with cmd(t)."""
    c = cmd - cmd.mean()
    best = (0, -2.0)
    for lag in range(-max_lag_bins, max_lag_bins + 1):
        d = np.roll(dev, -lag)
        lo = max(0, lag)
        hi = len(cmd) - max(0, -lag)
        if hi - lo < 10:
            continue
        a, b = c[lo:hi], d[lo:hi] - d[lo:hi].mean()
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom <= 0:
            continue
        r = float(np.dot(a, b) / denom)
        if r > best[1]:
            best = (lag, r)
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sent", required=True, help="CSV from send_envelope.py")
    ap.add_argument("--block", required=True,
                    help="TDT block directory, or a .npz holding data[ch,n] + fs")
    ap.add_argument("--store", default="sSig", help="delivered-stim store (default sSig)")
    ap.add_argument("--bin-ms", type=float, default=10.0, help="bin width (default 10 = one tick)")
    ap.add_argument("--channels", default=None,
                    help="channels to report (default: all that were commanded, plus 3 controls)")
    ap.add_argument("--max-lag-ms", type=float, default=500.0)
    ap.add_argument("--plot", default=None, help="write an overlay PNG here")
    args = ap.parse_args(argv)

    bin_s = args.bin_ms / 1000.0
    t_cmd, u_cmd = load_sent(args.sent)
    t_dev, a_dev, fs = load_delivered(args.block, args.store, bin_s)
    print("Commanded: %d ticks x %d ch from %s" % (u_cmd.shape[0], u_cmd.shape[1], args.sent))
    print("Delivered: %d bins x %d ch from %s/%s (fs=%.1f Hz)"
          % (a_dev.shape[0], a_dev.shape[1], args.block, args.store, fs))

    commanded = [i for i in range(u_cmd.shape[1]) if np.ptp(u_cmd[:, i]) > 0]
    if not commanded:
        raise SystemExit("FAIL: the sent log contains no channel that ever moved.")

    # The recording starts before and ends after the envelope, so compare over
    # the commanded length and let the lag search place it.
    n = min(len(t_cmd), a_dev.shape[0])
    max_lag_bins = int(round(args.max_lag_ms / args.bin_ms))

    def score(ch, cmd):
        """Lag-aligned correlation and slope of delivered ch against command."""
        dev = a_dev[:n, ch]
        lag, r = best_lag(cmd, dev, max_lag_bins)
        aligned = np.roll(dev, -lag)
        lo, hi = max(0, lag), n - max(0, -lag)
        slope = float(np.polyfit(cmd[lo:hi], aligned[lo:hi], 1)[0]) if hi - lo > 10 else float("nan")
        return r, slope, lag, aligned

    present = min(a_dev.shape[1], u_cmd.shape[1])
    primary = u_cmd[:n, commanded[0]]

    if args.channels:
        report = [int(c) - 1 for c in args.channels.replace(" ", "").split(",")]
        controls = [c for c in report if c not in commanded]
    else:
        # Score every uncommanded channel against the primary envelope and show
        # the three most suspicious. Noise scores ~0; a channel that tracks the
        # command but was never commanded means the word -> pair mapping is off,
        # which is exactly the failure this run exists to catch.
        others = [i for i in range(present) if i not in commanded]
        controls = sorted(others, key=lambda c: -abs(score(c, primary)[0]))[:3]
        report = commanded + controls

    print("")
    print("  ch  commanded   peak_dev      corr     slope    lag_ms   verdict")
    print("  --  ---------   --------   -------   -------   -------   -------")
    results = []
    for ch in report:
        if ch >= a_dev.shape[1]:
            print("  %2d  %-9s  %s" % (ch + 1, "yes" if ch in commanded else "-",
                                       "(not present in %s)" % args.store))
            continue
        driven_ch = ch in commanded
        cmd = u_cmd[:n, ch] if driven_ch else primary
        r, slope, lag, aligned = score(ch, cmd)
        if driven_ch:
            verdict = "PASS" if r >= 0.9 else ("weak" if r >= 0.5 else "FAIL")
        else:
            # Correlation against an envelope this channel was never given.
            # Noise gives |r| ~ 0.1; sustained tracking means leakage or a
            # mis-mapped word.
            verdict = "quiet" if abs(r) < 0.3 else "CROSSTALK/MISMAP?"
        print("  %2d  %-9s  %8.3f   %7.3f   %7.4g   %7.1f   %s"
              % (ch + 1, "yes" if driven_ch else "no", a_dev[:n, ch].max(),
                 r, slope, lag * args.bin_ms, verdict))
        results.append((ch, r if driven_ch else None, slope, lag, aligned))

    driven = [x for x in results if x[1] is not None]
    if driven:
        best = max(driven, key=lambda x: x[1])
        print("")
        if best[1] >= 0.9:
            print("PASS: delivered amplitude tracks the commanded envelope on ch %d (corr %.3f)."
                  % (best[0] + 1, best[1]))
            print("      Units conversion: 1 command unit = %.4g %s units." % (best[2], args.store))
        elif best[1] >= 0.5:
            print("WEAK (best corr %.3f on ch %d). Envelope is getting through but distorted -- "
                  "check for saturation at umax, a rate limit, or a mis-set gain in the RZ2 circuit."
                  % (best[1], best[0] + 1))
        else:
            print("FAIL (best corr %.3f). Delivered stim does not follow the command." % best[1])
            print("      Work backwards: (1) did %s contain ANY nonzero data? peak above is the "
                  "answer; (2) is the RZ2 circuit reading the UDP word into the stim amplitude "
                  "parameter; (3) did SET_REMOTE_IP succeed (send_envelope.py prints it)."
                  % args.store)

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        show = [x for x in results if x[1] is not None][:4]
        fig, axes = plt.subplots(len(show), 1, figsize=(10, 2.2 * max(1, len(show))),
                                 sharex=True, squeeze=False)
        t = np.arange(n) * bin_s
        for ax, (ch, r, slope, lag, aligned) in zip(axes[:, 0], show):
            ax.plot(t, u_cmd[:n, ch], color="0.35", lw=1.2, label="commanded")
            ax2 = ax.twinx()
            ax2.plot(t, aligned[:n], color="tab:red", lw=1.0, alpha=0.8, label="delivered")
            ax.set_ylabel("ch %d cmd" % (ch + 1), fontsize=9)
            ax2.set_ylabel("delivered", fontsize=9, color="tab:red")
            ax.set_title("ch %d: corr %.3f, slope %.4g, lag %.0f ms"
                         % (ch + 1, r, slope, lag * args.bin_ms), fontsize=10)
        axes[-1, 0].set_xlabel("time (s)")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=130)
        print("Wrote %s" % args.plot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
