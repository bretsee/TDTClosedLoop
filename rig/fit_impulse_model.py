#!/usr/bin/env python
"""fit_impulse_model.py -- impulse-response report from a single-pulse capture.

    python rig/fit_impulse_model.py --capture capture_rig_runN.csv

Companion to `make_excitation` kind='impulse' (single-tick pulses, long gaps).
Reads the server capture (tick,seq,t_ms,u1..uN,y1..yM), finds every isolated
pulse on the active input, epochs each output feature around the pulses, and
reports, per output channel:

    kernel        trial-averaged, baseline-subtracted response (feature units
                  per tick of lag), normalized per unit command amplitude
    gain          peak of the unit kernel (feature units per amplitude unit)
    delay_ticks   lag of that peak. Structural floor is +2: the command logged
                  at tick k is transmitted at k+1 (localhost path) and read
                  back at k+2 at the earliest. Tissue peak (13-15 ms) adds ~1.
    snr           |peak| / p99 of a null built from pulse-free ticks -- if this
                  is ~1 the channel did not respond, whatever the kernel looks
                  like
    linearity_r2  R^2 of peak-vs-amplitude through the origin across the
                  amplitude levels (the acute arrays gave ~0.92)

This is the MODEL-FREE view. The model the MPC uses still comes from
fit_sysid_from_capture (3_fit.ps1) -- ARX fits impulse captures fine. Use this
report to pick the channel, sanity-check gain/delay/linearity, and catch a
non-responding prep BEFORE trusting any fit.
"""

import argparse
import csv
import json
import sys

import numpy as np

RNG = np.random.default_rng(12345)


def load_capture(path):
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        rows = np.array([[float(v) for v in row] for row in r])
    u_cols = [i for i, h in enumerate(header) if h.startswith("u")]
    y_cols = [i for i, h in enumerate(header) if h.startswith("y")]
    return rows[:, u_cols], rows[:, y_cols]


def find_pulses(u, baseline):
    """Ticks t where u[t] > baseline and both neighbours are at baseline."""
    hi = u > baseline + 1e-9
    pulses = []
    for t in range(1, len(u) - 1):
        if hi[t] and not hi[t - 1] and not hi[t + 1]:
            pulses.append(t)
    return pulses


def epoch(y, ticks, pre, post):
    """[n_trials x (pre+post+1) x n_ch], baseline = mean of the pre window."""
    out = []
    for t in ticks:
        if t - pre < 0 or t + post >= len(y):
            continue
        seg = y[t - pre : t + post + 1, :].copy()
        seg -= seg[:pre, :].mean(axis=0, keepdims=True)
        out.append(seg)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--input", type=int, default=0,
                    help="1-based input channel; 0 = auto (the one that moved)")
    ap.add_argument("--pre-ticks", type=int, default=5)
    ap.add_argument("--post-ticks", type=int, default=30)
    ap.add_argument("--skip-ticks", type=int, default=50,
                    help="warm-up ticks discarded from the head (default 50)")
    ap.add_argument("--null-draws", type=int, default=500,
                    help="null epochs for the significance floor (default 500)")
    ap.add_argument("--out-prefix", default="",
                    help="write <prefix>_kernels.csv + <prefix>_report.json")
    args = ap.parse_args()

    U, Y = load_capture(args.capture)
    U, Y = U[args.skip_ticks:], Y[args.skip_ticks:]
    n_ch = Y.shape[1]

    moved = [j for j in range(U.shape[1]) if np.ptp(U[:, j]) > 1e-9]
    if args.input > 0:
        j_in = args.input - 1
    elif len(moved) == 1:
        j_in = moved[0]
    else:
        raise SystemExit("FAIL: %d inputs moved (%s); pick one with --input"
                         % (len(moved), [m + 1 for m in moved]))

    u = U[:, j_in]
    baseline_u = np.min(u)
    pulses = find_pulses(u, baseline_u)
    if len(pulses) < 5:
        raise SystemExit("FAIL: only %d isolated pulses found on input %d -- is "
                         "this an impulse capture?" % (len(pulses), j_in + 1))
    amps = np.array([u[t] for t in pulses])
    levels = sorted(set(np.round(amps, 6)))
    print("Input %d: %d pulses, amplitudes %s (n = %s)"
          % (j_in + 1, len(pulses), ["%g" % l for l in levels],
             [int(np.sum(np.isclose(amps, l))) for l in levels]))

    pre, post = args.pre_ticks, args.post_ticks
    trials = epoch(Y, pulses, pre, post)                     # trials x lag x ch
    kept = trials.shape[0]
    trial_amps = np.array([u[t] for t in pulses
                           if pre <= t < len(u) - post])[:kept]

    # Unit kernel: response normalized per amplitude unit, averaged over trials.
    unit = (trials / trial_amps[:, None, None]).mean(axis=0)  # lag x ch
    lags = np.arange(-pre, post + 1)

    # Null: same epoching at random pulse-free ticks, same per-trial count.
    forbidden = set()
    for t in pulses:
        forbidden.update(range(t - 2, t + post + 1))
    candidates = [t for t in range(pre, len(u) - post) if t not in forbidden]
    null_peaks = np.zeros((args.null_draws, n_ch))
    mean_amp = trial_amps.mean()
    for d in range(args.null_draws):
        picks = RNG.choice(candidates, size=kept, replace=True)
        nt = epoch(Y, picks, pre, post)
        null_peaks[d] = np.abs(nt.mean(axis=0)[pre:, :]).max(axis=0) / mean_amp
    floor = np.percentile(null_peaks, 99, axis=0)             # per channel

    # Per-amplitude peaks for the linearity check (at each channel's best lag).
    report = []
    for ch in range(n_ch):
        k = unit[pre:, ch]                                    # causal lags only
        peak_lag = int(np.argmax(np.abs(k)))
        peak = float(k[peak_lag])
        snr = abs(peak) / max(floor[ch], 1e-15)

        lvl_peaks, lvl_amps = [], []
        for l in levels:
            sel = np.isclose(trial_amps, l)
            if sel.sum() < 3:
                continue
            m = trials[sel, :, ch].mean(axis=0)
            lvl_peaks.append(m[pre + peak_lag])
            lvl_amps.append(l)
        if len(lvl_amps) >= 2:
            a, p_ = np.array(lvl_amps), np.array(lvl_peaks)
            g = (a @ p_) / (a @ a)                            # through-origin slope
            ss_res = np.sum((p_ - g * a) ** 2)
            ss_tot = np.sum(p_ ** 2)
            lin_r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        else:
            lin_r2 = float("nan")

        report.append({"channel": ch + 1, "gain": peak,
                       "delay_ticks": peak_lag, "delay_ms": peak_lag * 10.0,
                       "snr_vs_p99floor": round(snr, 2),
                       "linearity_r2": None if np.isnan(lin_r2) else round(lin_r2, 3)})

    report.sort(key=lambda r: -r["snr_vs_p99floor"])
    print("\n ch   gain(feat/amp)  delay     snr    linR2   verdict")
    for r in report:
        verdict = ("RESPONDING" if r["snr_vs_p99floor"] >= 3 else
                   "marginal" if r["snr_vs_p99floor"] >= 1.5 else "-")
        print(" %2d   %+12.4g   %2d tk  %6.1fx   %s   %s"
              % (r["channel"], r["gain"], r["delay_ticks"], r["snr_vs_p99floor"],
                 ("%.3f" % r["linearity_r2"]) if r["linearity_r2"] is not None else "  -  ",
                 verdict))

    best = report[0]
    if best["snr_vs_p99floor"] < 3:
        print("\nVERDICT: NO channel clears 3x the null floor. Do not fit a model")
        print("         from this capture; check stim delivery first (sSig/battery/safety).")
    else:
        print("\nVERDICT: best channel %d, gain %.4g feature-units/amp, delay %d ticks."
              % (best["channel"], best["gain"], best["delay_ticks"]))
        print("Next: .\\rig\\3_fit.ps1 -Run <label> -Channel %d   (then -Validate on a second capture)"
              % best["channel"])

    if args.out_prefix:
        with open(args.out_prefix + "_kernels.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["lag_ticks"] + ["ch%d" % (c + 1) for c in range(n_ch)])
            for i, lag in enumerate(lags):
                w.writerow([int(lag)] + ["%.9g" % v for v in unit[i]])
        with open(args.out_prefix + "_report.json", "w") as f:
            json.dump({"capture": args.capture, "input_1based": j_in + 1,
                       "n_pulses": len(pulses), "trials_used": int(kept),
                       "levels": [float(l) for l in levels],
                       "channels": report}, f, indent=2)
        print("Wrote %s_kernels.csv and %s_report.json" % (args.out_prefix, args.out_prefix))
    return 0


if __name__ == "__main__":
    sys.exit(main())
