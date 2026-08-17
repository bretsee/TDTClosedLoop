#!/usr/bin/env python3
"""timing_check.py -- measure command->feature latency from a capture CSV.

This is the saline TIMING CONFIRMATION analysis. It answers one question:

    when the controller commands a change, how many ticks later does that
    change appear in the feature it reads back?

Saline has no dynamics -- it is an instantaneous, essentially rank-1 medium --
so any lag measured through it is PURE INSTRUMENTATION LATENCY. That is what
makes it a clean timing measurement and not a physiology one. The same script
run on tissue would conflate the two.

Input is the wide capture CSV written by the controller server
(matlab_controller_server.m or cpp_controller.exe):

    tick,seq,t_ms,u1..uN,y1..yM

Expect a structural +1 tick from the localhost controller path (the command
logged at tick k is not transmitted until k+1), plus whatever acquisition
latency the PO8e adds.

Usage:
    python rig/timing_check.py --capture capture_saline.csv
    python rig/timing_check.py --capture capture_saline.csv --max-lag 30 --top 15

Reading the output:
  * lag is in TICKS; at 100 Hz one tick is 10 ms.
  * Positive lag means the feature FOLLOWS the command (causal, expected).
  * A negative lag is not physically possible for a real effect. If the best
    lag is negative, you are looking at noise or at a periodic command whose
    period aliases -- check |corr| against the reported noise floor first.
  * |corr| below the noise floor means NOTHING WAS DETECTED. It does not mean
    a small effect. The floor is computed from this record's own geometry, so
    it already accounts for record length and the number of comparisons made.
  * In saline every channel responds, because the coupling is conduction, not
    biology. A focal response would be the surprising result there.
"""

import argparse
import csv
import sys

import numpy as np

TICK_MS = 10.0


def xcorr_lag(x, y, max_lag):
    """Return (lag, signed_r) maximising |Pearson r| over -max_lag..+max_lag.

    Positive lag means y follows x by that many samples. Mirrors the definition
    in sweep_channels.m / build_status_deck.py's max_abs_xcorr, extended to
    report WHICH lag won and to scan negative lags so an a-causal result is
    visible rather than silently folded into the positive side.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = x - x.mean()
    y = y - y.mean()
    n = x.size
    best_lag, best_r = 0, 0.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            xa, ya = x[: n - lag], y[lag:]
        else:
            xa, ya = x[-lag:], y[: n + lag]
        if xa.size < 10:
            continue
        dx, dy = np.linalg.norm(xa), np.linalg.norm(ya)
        if dx > 1e-12 and dy > 1e-12:
            r = float(xa @ ya) / (dx * dy)
            if abs(r) > abs(best_r):
                best_lag, best_r = lag, r
    return best_lag, best_r


def noise_floor(U, Y, moved, max_lag, n_shift=10, seed=12345):
    """Empirical |corr| floor from circularly shifted y.

    A circular shift destroys the true temporal relationship while preserving
    each signal's autocorrelation and the record length, so the resulting
    distribution is what "no relationship" actually looks like for THIS record
    searched over THIS many lags and channels. Comparing against a textbook
    significance threshold instead would understate the floor badly, which is
    how the rig-day-1 |corr| 0.059 could have been mistaken for a weak signal
    (the real floor was 0.027-0.064).
    """
    rng = np.random.default_rng(seed)
    n = Y.shape[0]
    if n < 40:
        return float("nan"), float("nan")
    vals = []
    for _ in range(n_shift):
        s = int(rng.integers(n // 4, max(n // 4 + 1, 3 * n // 4)))
        Ys = np.roll(Y, s, axis=0)
        for ch in range(Ys.shape[1]):
            for m in moved:
                vals.append(abs(xcorr_lag(U[:, m], Ys[:, ch], max_lag)[1]))
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 95)), float(np.percentile(vals, 99))


def load_capture(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 3:
        raise SystemExit(f"FAIL: {path} has too few rows to analyse.")
    header = rows[0]
    data = np.array(rows[1:], dtype=float)
    u_idx = [i for i, h in enumerate(header) if h.strip().startswith("u")]
    y_idx = [i for i, h in enumerate(header) if h.strip().startswith("y")]
    if not u_idx or not y_idx:
        raise SystemExit(
            f"FAIL: {path} has no u*/y* columns. Header was: {header[:8]}..."
        )
    t_idx = header.index("t_ms") if "t_ms" in header else None
    return data[:, u_idx], data[:, y_idx], data[:, t_idx] if t_idx is not None else None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--capture", required=True, help="wide capture CSV")
    ap.add_argument("--max-lag", type=int, default=20, help="ticks to scan (default 20)")
    ap.add_argument("--skip-ticks", type=int, default=50,
                    help="warm-up ticks to discard (default 50)")
    ap.add_argument("--top", type=int, default=10, help="pairs to list (default 10)")
    ap.add_argument("--shifts", type=int, default=10,
                    help="circular shifts for the noise floor (default 10)")
    args = ap.parse_args(argv)

    U, Y, t_ms = load_capture(args.capture)

    if args.skip_ticks > 0:
        if U.shape[0] <= args.skip_ticks + 40:
            raise SystemExit(
                f"FAIL: only {U.shape[0]} rows; cannot discard {args.skip_ticks} "
                "and still analyse. Lower --skip-ticks or record longer."
            )
        U, Y = U[args.skip_ticks:], Y[args.skip_ticks:]
        if t_ms is not None:
            t_ms = t_ms[args.skip_ticks:]

    print(f"=== TIMING CHECK: {args.capture} ===")
    print(f"  rows analysed : {U.shape[0]}  ({U.shape[1]} u, {Y.shape[1]} y)")
    if t_ms is not None and t_ms.size > 2:
        dt = np.diff(t_ms)
        print(f"  tick spacing  : median {np.median(dt):.4f} ms  "
              f"std {dt.std():.4f}  min {dt.min():.3f}  max {dt.max():.3f}")

    moved = [i for i in range(U.shape[1]) if U[:, i].std() > 1e-12]
    if not moved:
        print("\n  FAIL: no u column varies. Nothing was commanded -- "
              "check the excitation actually ran.")
        return 2
    print(f"  u channels that moved: {[m + 1 for m in moved]}")

    p95, p99 = noise_floor(U, Y, moved, args.max_lag, n_shift=args.shifts)
    print(f"  noise floor   : |corr| p95 {p95:.4f}   p99 {p99:.4f}  "
          f"(circular-shift, same lags/channels)")

    results = []
    for m in moved:
        for ch in range(Y.shape[1]):
            lag, r = xcorr_lag(U[:, m], Y[:, ch], args.max_lag)
            results.append((abs(r), lag, r, m + 1, ch + 1))
    results.sort(reverse=True)

    print(f"\n  top {min(args.top, len(results))} pairs by |corr|:")
    print(f"    {'u':>3} {'y':>4} {'lag':>5} {'lag_ms':>8} {'corr':>9}   verdict")
    for absr, lag, r, uu, yy in results[: args.top]:
        if np.isnan(p95):
            verdict = "?"
        elif absr > p99:
            verdict = "SIGNIFICANT"
        elif absr > p95:
            verdict = "marginal"
        else:
            verdict = "at noise floor"
        print(f"    {uu:>3} {yy:>4} {lag:>+5d} {lag * TICK_MS:>+8.1f} "
              f"{r:>+9.4f}   {verdict}")

    sig = [(lag, absr) for absr, lag, r, uu, yy in results
           if not np.isnan(p99) and absr > p99]
    print()
    if not sig:
        print("  VERDICT: no pair exceeds the noise floor -- NO TIMING MEASURED.")
        print("           Nothing arrived, or the commanded amplitude was too small.")
        print("           This is the same signature as rig day 1; check stim was")
        print("           actually delivered before interpreting it as latency.")
        return 1

    lags = np.array([l for l, _ in sig])
    med = float(np.median(lags))
    n_pairs = len(results)
    expected_fp = 0.01 * n_pairs  # p99 admits ~1% of pairs by construction
    best_abs = max(a for a, _, _, _, _ in results)
    ratio = best_abs / p99 if p99 > 1e-12 else float("inf")
    print(f"  VERDICT: {len(sig)} pair(s) above the p99 floor "
          f"(~{expected_fp:.1f} expected by chance from {n_pairs} pairs).")
    print(f"           best |corr| {best_abs:.4f} = {ratio:.1f}x the p99 floor.")

    # Two independent ways a result can be real: many channels agreeing, or one
    # channel far above the floor. Judge on both -- counting alone cries wolf on
    # a strong single-channel effect, and magnitude alone misses a diffuse one.
    weak_count = len(sig) <= max(1.0, 2.0 * expected_fp)
    if ratio >= 3.0:
        print("           Magnitude alone puts this well clear of chance.")
    elif weak_count:
        print("           CAUTION: consistent with CHANCE ALONE -- a p99 threshold")
        print("                    admits ~1% of pairs no matter what, and nothing")
        print("                    here stands far above the floor. Real conduction")
        print("                    in saline should light up MANY channels at the")
        print("                    SAME lag, or one channel far above the floor.")
        print("                    Do not report a latency from this.")
    print(f"           median lag = {med:+.1f} ticks = {med * TICK_MS:+.1f} ms")
    print(f"           lag spread = {lags.min():+d} .. {lags.max():+d} ticks")
    if lags.std() > 2.0:
        print("           WARNING: lag is not consistent across channels "
              "(std > 2 ticks).")
        print("                    A real transport delay should be nearly the same")
        print("                    everywhere. Check for aliasing or a periodic")
        print("                    command whose period is near the scan range.")
    if med < 0:
        print("           WARNING: negative median lag is not physically possible.")
        print("                    Treat this as a detection failure, not a result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
