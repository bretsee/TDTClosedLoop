#!/usr/bin/env python
"""validate_impulse_design.py -- audit an impulse-probe capture before analysis.

    python rig/validate_impulse_design.py --capture capture_rig_run<label>.csv

Reads a server capture (tick,seq,t_ms,u1..uN[,y1..yM]) and verifies the
commanded impulse design actually made it into the record, per input channel:

  design      amplitudes exactly the expected ladder, cycled evenly; every
              pulse single-tick (neighbours at baseline); nothing clamped
  intervals   base gap respected; jitter strictly positive; mean jitter near
              the requested value; geometric-shape sanity (std, lag-1
              autocorrelation ~ 0 = memoryless = no rhythm); quasi-periodicity
              warning if any one interval dominates
  cross-chan  no two pulses on any channels within the guard window (each
              pulse attributable to exactly one bipolar pair, +1-tick
              transport delay included)
  analysis    per-input compatibility with rig/fit_impulse_model.py: trial
              count, tail losses (pulses too close to the record end), null-
              floor candidate count, and epoch contamination by other
              channels' pulses (expected and quantified in a multi-pair
              record; drives the "analyze per input" instruction)

Exit code 0 = design verified (warnings allowed), 1 = hard failure. Run it on
the sim rehearsal capture BEFORE the saline session and on the rig capture
right after each run -- a difference between the two is a translation problem.
"""

import argparse
import csv
import sys

import numpy as np

HARD, WARN, INFO = "FAIL", "warn", "info"


def load_capture(path):
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        rows = np.array([[float(v) for v in row] for row in r])
    u_cols = [i for i, h in enumerate(header) if h.startswith("u")]
    return rows[:, u_cols]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--amps", type=float, nargs="+", default=[5, 10, 18, 25],
                    help="expected amplitude ladder (default 5 10 18 25)")
    ap.add_argument("--gap-ticks", type=int, default=50,
                    help="designed deterministic gap (default 50)")
    ap.add_argument("--jitter-mean-ticks", type=int, default=8,
                    help="designed mean of the geometric jitter, ticks (default 8 = 80 ms); 0 = periodic design")
    ap.add_argument("--umax", type=float, default=25)
    ap.add_argument("--pre-ticks", type=int, default=5,
                    help="fit_impulse_model epoch pre-window (default 5)")
    ap.add_argument("--post-ticks", type=int, default=30,
                    help="fit_impulse_model epoch post-window (default 30)")
    ap.add_argument("--guard-ticks", type=int, default=2,
                    help="cross-channel exclusion window the design promises (default 2)")
    args = ap.parse_args()

    U = load_capture(args.capture)
    n_ticks, n_in = U.shape
    base = np.min(U)
    period = args.gap_ticks + 1
    expected = sorted(args.amps)
    issues = []

    def note(sev, msg):
        issues.append((sev, msg))
        print("  %s: %s" % (sev, msg))

    moved = [j for j in range(n_in) if np.ptp(U[:, j]) > 1e-9]
    print("Capture: %s  (%d ticks = %.1f s, %d inputs, %d moved: %s, baseline %g)"
          % (args.capture, n_ticks, n_ticks / 100.0, n_in, len(moved),
             [j + 1 for j in moved], base))
    if not moved:
        print("FAIL: no input moved at all.")
        return 1
    if np.max(U) > args.umax + 1e-9:
        note(HARD, "command exceeds uMax %g (max seen %g)" % (args.umax, np.max(U)))

    all_pulse_ticks = []
    print("\n ch  pulses  per-amp %-20s  interval ticks        jitter ticks   lag1"
          % str([("%g" % a) for a in expected]))
    for j in moved:
        u = U[:, j]
        hi = u > base + 1e-9
        ticks = np.flatnonzero(hi)
        # single-tick isolation: no two consecutive hi ticks on this channel
        runs = np.flatnonzero(np.diff(ticks) == 1)
        if len(runs):
            note(HARD, "input %d has %d multi-tick pulse(s) (first at tick %d) "
                       "-- not an isolated-impulse record" % (j + 1, len(runs), ticks[runs[0]]))
        amps = u[ticks]
        stray = sorted(set(np.round(amps, 6)) - set(np.round(expected, 6)))
        if stray:
            note(HARD, "input %d carries unexpected amplitude(s) %s -- clamping or "
                       "scaling changed the design in translation" % (j + 1, stray))
        counts = [int(np.sum(np.isclose(amps, a))) for a in expected]
        if max(counts) - min(counts) > 1:
            note(WARN, "input %d amplitude ladder uneven %s (cycling should keep "
                       "counts within 1)" % (j + 1, counts))

        iv = np.diff(ticks)
        jit = iv - period
        lag1 = float("nan")
        if len(iv) >= 3:
            if np.any(jit < (1 if args.jitter_mean_ticks > 0 else 0)):
                note(HARD, "input %d has interval(s) at/below the base period "
                           "(min %d ticks vs designed >= %d) -- jitter not strictly "
                           "positive" % (j + 1, iv.min(), period + (1 if args.jitter_mean_ticks else 0)))
            if args.jitter_mean_ticks > 0:
                mj, sj = jit.mean(), jit.std()
                if abs(mj - args.jitter_mean_ticks) > max(2.0, 3 * sj / np.sqrt(len(jit))):
                    note(WARN, "input %d mean jitter %.1f ticks vs designed %d"
                               % (j + 1, mj, args.jitter_mean_ticks))
                if len(jit) >= 10 and sj > 1e-9:
                    a0 = jit[:-1] - jit[:-1].mean()
                    a1 = jit[1:] - jit[1:].mean()
                    denom = np.sqrt((a0 ** 2).sum() * (a1 ** 2).sum())
                    lag1 = float((a0 * a1).sum() / denom) if denom > 0 else 0.0
                    if abs(lag1) > 4.0 / np.sqrt(len(jit)):
                        note(WARN, "input %d jitter lag-1 autocorr %.2f -- intervals "
                                   "are not independent" % (j + 1, lag1))
            modal_frac = np.max(np.bincount(iv)) / len(iv)
            if modal_frac > 0.5 and args.jitter_mean_ticks > 0:
                note(WARN, "input %d: %d%% of intervals share one value -- "
                           "quasi-periodic, rhythm risk" % (j + 1, round(100 * modal_frac)))

        tail_lost = int(np.sum(ticks + args.post_ticks >= n_ticks))
        if tail_lost:
            note(INFO, "input %d: %d pulse(s) within %d ticks of the record end are "
                       "dropped by the fitter's epoching" % (j + 1, tail_lost, args.post_ticks))

        all_pulse_ticks.append(ticks)
        print(" %2d  %6d  %-28s  min/mean/max %3d/%5.1f/%3d  mean %5.1f  %s"
              % (j + 1, len(ticks), counts, iv.min() if len(iv) else 0,
                 iv.mean() if len(iv) else 0, iv.max() if len(iv) else 0,
                 jit.mean() if len(iv) else 0,
                 ("%+.2f" % lag1) if lag1 == lag1 else "  -  "))

    # ---- cross-channel attribution -------------------------------------
    print()
    if len(moved) > 1:
        merged = np.zeros(n_ticks, dtype=int)
        for ticks in all_pulse_ticks:
            merged[ticks] += 1
        if np.any(merged > 1):
            note(HARD, "%d tick(s) carry pulses on more than one channel -- pulses "
                       "not attributable per pair" % int(np.sum(merged > 1)))
        spacing = np.diff(np.flatnonzero(merged > 0))
        if len(spacing) and spacing.min() <= args.guard_ticks:
            note(HARD, "cross-channel pulse spacing %d ticks <= guard %d -- "
                       "attribution window violated" % (spacing.min(), args.guard_ticks))
        elif len(spacing):
            print("  cross-channel: no collisions; min spacing %d ticks (guard %d); "
                  "total %d pulses across %d channels"
                  % (spacing.min(), args.guard_ticks, int(merged.sum()), len(moved)))

    # ---- fit_impulse_model compatibility -------------------------------
    for j, ticks in zip(moved, all_pulse_ticks):
        forbidden = np.zeros(n_ticks, dtype=bool)
        for t in ticks:
            forbidden[max(0, t - 2):min(n_ticks, t + args.post_ticks + 1)] = True
        cand = int(np.sum(~forbidden[args.pre_ticks:n_ticks - args.post_ticks]))
        contaminated = 0
        others = [t for jj, t in zip(moved, all_pulse_ticks) if jj != j]
        if others:
            other_ticks = np.concatenate(others)
            for t in ticks:
                if np.any((other_ticks > t - args.pre_ticks) &
                          (other_ticks <= t + args.post_ticks)):
                    contaminated += 1
        if cand < 200:
            note(WARN, "input %d: only %d null-floor candidate ticks -- the fitter's "
                       "significance floor will be shaky" % (j + 1, cand))
        if contaminated:
            pct = 100.0 * contaminated / max(1, len(ticks))
            sev = WARN if pct > 60 else INFO
            note(sev, "input %d: %d/%d epochs (%.0f%%) contain another channel's "
                       "pulse inside the %d-tick window -- expected in a multi-pair "
                       "record; responses average out across trials, but analyze "
                       "per input" % (j + 1, contaminated, len(ticks), pct,
                                      args.pre_ticks + args.post_ticks + 1))
    if len(moved) > 1:
        print("\n  fit_impulse_model.py auto-detect needs ONE moved input; with %d "
              "moved, run per input:" % len(moved))
        for j in moved:
            print("    python rig\\fit_impulse_model.py --capture %s --input %d "
                  "--out-prefix probe_in%d" % (args.capture, j + 1, j + 1))

    hard = sum(1 for s, _ in issues if s == HARD)
    warns = sum(1 for s, _ in issues if s == WARN)
    print("\nVERDICT: %s  (%d hard failure(s), %d warning(s), %d info)"
          % ("DESIGN BROKEN -- fix before the rig" if hard else "DESIGN VERIFIED",
             hard, warns, len(issues) - hard - warns))
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
