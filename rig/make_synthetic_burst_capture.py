#!/usr/bin/env python
"""make_synthetic_burst_capture.py -- capture with a KNOWN depressing burst plant.

    python rig/make_synthetic_burst_capture.py --design design_runburst1.csv \
        --out capture_synth_burst1.csv [--n-channels 16] [--seed 1]

Plays a burst-probe design (design_burst_probe.py CSV: tick,u1..u8) through a
synthetic thalamocortical plant with short-term synaptic DEPRESSION, so
fit_burst_plant.py has ground truth to check against:

  per pair j, resource R_j(k) in [0, 1]:
      R_j <- R_j + (1 - R_j) / tau_rec            every tick (recovery)
      R_j <- R_j - U * R_j                        on a pulse tick (depletion)
      drive_j(k) = amp_j(k) * U * R_j(k)          effective synaptic drive
  feature channels: y(k+1) = a * y(k) + sum_j drive_j(k - dead + 1) * w_j + noise
  with footprint vectors w_j (pairs x channels) of KNOWN rank 3, dead time 3
  ticks in the row frame (matches rig/check_dead_time on the 09-10 probe).

Known answers (returned in the sidecar <out>_truth.json):
  * per-pulse efficacy of a B-pulse burst = mean R over its pulses
    (R starts at 1: 1, 1-U, (1-U)^2 ... so a 10-pulse burst at U=0.3 delivers
    ~0.32 x the charge-normalized single-pulse response per pulse)
  * recovery ratio after gap g (test/cond, gap-scan design) = 1 - U e^{-g/tau_rec}
  * eff. rank of the single-pulse footprint matrix = 3

fit_burst_plant.py --synthetic-check generates these captures itself, fits,
and asserts the recovered numbers within tolerance.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from design_burst_probe import read_design   # noqa: E402

TRUTH = dict(U=0.3, tau_rec=40.0, a=0.63, dead=3, rank=3, gain=2e-6, noise=1.5e-6, offset=5e-5)


def simulate(Ud, n_channels=16, seed=1, truth=None):
    T = dict(TRUTH); T.update(truth or {})
    rng = np.random.default_rng(seed)
    n, m = Ud.shape
    # rank-3 footprints: 3 latent spatial modes, each pair a positive mix
    modes = np.abs(rng.normal(size=(T["rank"], n_channels)))
    modes /= np.linalg.norm(modes, axis=1, keepdims=True)
    mix = np.abs(rng.normal(size=(m, T["rank"])))
    mix /= mix.sum(axis=1, keepdims=True)
    W = mix @ modes                                   # [pairs x channels], rank 3
    R = np.ones(m)
    drive = np.zeros((n, m))
    for k in range(n):
        R += (1.0 - R) / T["tau_rec"]
        on = Ud[k] > 1e-9
        drive[k] = Ud[k] * T["U"] * R
        R[on] -= T["U"] * R[on]
    y = np.zeros((n, n_channels))
    state = np.zeros(n_channels)
    d = T["dead"]
    for k in range(n):
        y[k] = T["offset"] + state + T["noise"] * rng.normal(size=n_channels)
        src = drive[k - d + 1] if k - d + 1 >= 0 else np.zeros(m)
        state = T["a"] * state + T["gain"] * (src @ W)
    return y, W, T, drive


def write_capture(path, Ud, Y):
    n, m = Ud.shape
    with open(path, "w", newline="") as f:
        f.write("tick,seq,t_ms," + ",".join("u%d" % (i + 1) for i in range(m)) +
                "," + ",".join("y%d" % (i + 1) for i in range(Y.shape[1])) + "\n")
        for k in range(n):
            f.write("%d,%d,%.1f," % (k + 1, k + 1, 10.0 * k) +
                    ",".join("%.9g" % v for v in Ud[k]) + "," +
                    ",".join("%.9g" % v for v in Y[k]) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-channels", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    Ud = read_design(args.design)
    Y, W, T, _drive = simulate(Ud, args.n_channels, args.seed)
    write_capture(args.out, Ud, Y)
    sv = np.linalg.svd(W / np.linalg.norm(W, axis=1, keepdims=True), compute_uv=False)
    truth = dict(T, footprint_sv=(sv / sv[0]).tolist(), design=args.design, n_channels=args.n_channels)
    with open(os.path.splitext(args.out)[0] + "_truth.json", "w") as f:
        json.dump(truth, f, indent=1)
    print("wrote %s (%d ticks x %d ch) + truth sidecar; U=%g tau_rec=%g dead=%d rank=%d"
          % (args.out, Ud.shape[0], args.n_channels, T["U"], T["tau_rec"], T["dead"], T["rank"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
