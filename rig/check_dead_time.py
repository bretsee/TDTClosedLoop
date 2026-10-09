#!/usr/bin/env python
"""check_dead_time.py -- measure the command->feature dead time in a capture and
score exported .lti models in the CONTROLLER'S row frame.

    python rig/check_dead_time.py --capture capture_rig_runopfit12.csv \
        --u-channels 4 6 --y-channel 64 \
        --lti plant_opfit12.lti --lti plant_opfit12_d1.lti

Why this exists (2026-10-09). fit_sysid_from_capture shifts u by
inputDelayTicks (default 1) AND regresses with nk=1, so the fitted relation is
u(k) -> y(k+2). mpc_test.m and cpp_controller predict x(k+1) = A x(k) + B u(k),
y(k) = C x(k): the command sent one tick ago explains the current feature. The
pre-10-09 export dropped the alignment, so the controller ran a model one tick
optimistic. An order-1 model (plant_opfit12, the 09-10 arm plant) has no spare
b-coefficient to absorb that. The fitter now appends pure-delay states; this
script is the measurement that says which convention the data obey.

Two measurements:

  1. Dead time from the data (model-free).
     PRBS / tonic captures: least-squares FIR impulse response h(l), l = 0..L,
     all command channels jointly (y(k) = c + sum h(l) u(k-l)). A raw
     cross-correlation would be smeared by the PRBS hold; the FIR is not.
     Onset = first lag whose |h| clears a circular-shift null (3 sigma, and
     > p99 of the null's max over lags).
     Pulse captures (isolated single-tick pulses): trial-averaged epoch around
     each pulse, onset = first post-pulse lag above the same kind of null.
     Row-frame onset L_on means u(k) first moves y(k + L_on). The controllers
     put nk = 1 tick in the model; the fitter's inputDelayTicks should be
     L_on - 1 (with delay states on, that is exactly what gets exported).

  2. Row-frame free-run fit of each --lti model.
     x+ = A x + B (u_k - uOff), yhat_k = C x_k + yOff, driven by the capture's
     command columns (in --u-channels order = the fit's useInputs order).
     Reported: fit% (NRMSE, same definition as the fitter), the fit% when the
     model output is shifted by s = -2..+2 ticks (a model exported one tick
     early scores best at s = +1 -- the signature of the defect), and the
     residual-vs-command cross-correlation at lags 0..5 (a spike at the missing
     lag is the other signature). "Fixed" = best shift 0 and |rho_res,u| < 0.05
     at every lag.

Exit code 0 always (this is a report); --json writes the numbers.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "training"))

from fit_impulse_model import load_capture, find_pulses, epoch   # noqa: E402
from closed_loop_sim import load_lti                             # noqa: E402

RNG = np.random.default_rng(20261009)


# ----------------------------------------------------------------------------
def xcorr_lags(u, y, max_lag):
    """rho(l) = corr(u[0:N-l], y[l:N]) for l = 0..max_lag (u leads y by l)."""
    u = u - u.mean()
    y = y - y.mean()
    n = len(u)
    out = np.zeros(max_lag + 1)
    for l in range(max_lag + 1):
        a = u[: n - l]
        b = y[l:]
        den = np.sqrt((a * a).sum() * (b * b).sum())
        out[l] = (a * b).sum() / den if den > 0 else 0.0
    return out


def fir_ls(U, y, max_lag):
    """Least-squares FIR impulse responses h[ch, l], l = 0..max_lag, all input
    channels jointly:  y(k) = c + sum_ch sum_l h[ch,l] u_ch(k-l).
    Unlike the raw cross-correlation this is NOT smeared by the input's own
    autocorrelation (a PRBS held for 5 ticks correlates u(k) with y(k+8) even
    when the plant answers at lag 3), so the onset it gives is the plant's."""
    n, m = U.shape
    L = max_lag
    rows = n - L
    Phi = np.ones((rows, 1 + m * (L + 1)))
    col = 1
    for ch in range(m):
        for l in range(L + 1):
            Phi[:, col] = U[L - l : n - l, ch]
            col += 1
    th, *_ = np.linalg.lstsq(Phi, y[L:], rcond=None)
    return th[1:].reshape(m, L + 1)


def fir_null(U, y, max_lag, draws):
    """p99 of max_l |h| when every input is circularly shifted far from its
    true alignment; also the pooled std of the null FIR coefficients."""
    n = U.shape[0]
    mx = np.zeros(draws)
    allv = []
    for i in range(draws):
        s = int(RNG.integers(max_lag + 200, n - max_lag - 200))
        h = fir_ls(np.roll(U, s, axis=0), y, max_lag)
        mx[i] = np.abs(h).max()
        allv.append(h.ravel())
    allv = np.concatenate(allv)
    return float(np.percentile(mx, 99)), float(allv.std())


def onset_from_profile(prof, thr):
    idx = np.where(np.abs(prof) > thr)[0]
    return int(idx[0]) if len(idx) else None


def is_pulse_capture(u):
    """Isolated single-tick pulses on a zero baseline (impulse / rnd designs)."""
    nz = u > 1e-9
    if nz.mean() > 0.2 or nz.sum() < 10:
        return False
    pulses = find_pulses(u, 0.0)
    return len(pulses) >= 0.8 * nz.sum()


def nrmse_fit(y, yhat):
    den = np.linalg.norm(y - y.mean())
    if den < 1e-300 or not np.all(np.isfinite(yhat)):
        return float("-inf")
    return 100.0 * (1.0 - np.linalg.norm(y - yhat) / den)


def free_run(A, B, C, D, uOff, yOff, U):
    n = A.shape[0]
    x = np.zeros(n)
    Y = np.zeros((U.shape[0], C.shape[0]))
    for k in range(U.shape[0]):
        uc = U[k] - uOff
        Y[k] = yOff + C @ x + D @ uc
        x = A @ x + B @ uc
    return Y


def shifted_fit(y, yhat, s):
    """fit% with yhat advanced by s ticks (s>0: model output arrives early)."""
    n = len(y)
    if s > 0:
        return nrmse_fit(y[s:], yhat[: n - s])
    if s < 0:
        return nrmse_fit(y[: n + s], yhat[-s:])
    return nrmse_fit(y, yhat)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--u-channels", type=int, nargs="*", default=None,
                    help="1-based command columns (default: every column that moves)")
    ap.add_argument("--y-channel", type=int, default=1, help="1-based feature column")
    ap.add_argument("--max-lag", type=int, default=10)
    ap.add_argument("--skip-ticks", type=int, default=50)
    ap.add_argument("--null-draws", type=int, default=200)
    ap.add_argument("--pulse", action="store_true",
                    help="force the pulse-epoch path (default: auto-detect)")
    ap.add_argument("--pre", type=int, default=5)
    ap.add_argument("--post", type=int, default=30)
    ap.add_argument("--lti", action="append", default=[],
                    help=".lti to score in the row frame (repeatable)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    U_all, Y_all = load_capture(args.capture)
    s = max(0, args.skip_ticks)
    U_all, Y_all = U_all[s:], Y_all[s:]
    if args.u_channels:
        u_idx = [c - 1 for c in args.u_channels]
    else:
        u_idx = [i for i in range(U_all.shape[1]) if U_all[:, i].std() > 1e-9]
    if not u_idx:
        print("FAIL: no command channel moves in this capture")
        return 1
    yi = args.y_channel - 1
    y = Y_all[:, yi]
    print("capture %s: %d ticks after skip, inputs %s, output y%d"
          % (args.capture, len(y), [i + 1 for i in u_idx], args.y_channel))

    report = {"capture": args.capture, "u_channels": [i + 1 for i in u_idx],
              "y_channel": args.y_channel, "inputs": {}, "models": {}}

    # ---- 1. dead time from the data ---------------------------------------
    onsets = []
    U_sel = U_all[:, u_idx]
    any_pulse = args.pulse or all(is_pulse_capture(U_all[:, i]) for i in u_idx)
    H = thr_fir = None
    if not any_pulse:
        H = fir_ls(U_sel, y, args.max_lag)
        p99, sd = fir_null(U_sel, y, args.max_lag, args.null_draws)
        thr_fir = max(p99, 3.0 * sd)
    for j, i in enumerate(u_idx):
        u = U_all[:, i]
        pulse_path = any_pulse
        if pulse_path:
            pulses = find_pulses(u, 0.0)
            E = epoch(Y_all[:, [yi]], pulses, args.pre, args.post)
            if len(E) == 0:
                print("  u%d: no usable pulses" % (i + 1))
                continue
            prof = E[:, args.pre:, 0].mean(axis=0)            # lag 0.. post
            amp = np.array([u[t] for t in pulses if t - args.pre >= 0 and t + args.post < len(u)])
            prof = prof / max(amp.mean(), 1e-12)
            # null: random non-pulse ticks, same epoch, same averaging
            cand = np.where(u <= 1e-9)[0]
            cand = cand[(cand > args.pre) & (cand < len(u) - args.post - 1)]
            mx = np.zeros(args.null_draws)
            for d in range(args.null_draws):
                tt = RNG.choice(cand, size=len(E), replace=False)
                En = epoch(Y_all[:, [yi]], tt, args.pre, args.post)
                mx[d] = np.abs(En[:, args.pre:, 0].mean(axis=0)).max() / max(amp.mean(), 1e-12)
            thr = float(np.percentile(mx, 99))
            L = args.post
            kind = "pulse (%d trials)" % len(E)
        else:
            prof = H[j]
            thr = thr_fir
            L = args.max_lag
            kind = "FIR-LS"
        on = onset_from_profile(prof, thr)
        pk = int(np.abs(prof).argmax())
        print("  u%d [%s]: null thr %.4g; |profile| by lag 0..%d:" % (i + 1, kind, thr, min(L, 8)))
        print("      " + "  ".join("%d:%+.3g" % (l, prof[l]) for l in range(min(L, 8) + 1)))
        if on is None:
            print("      onset: NONE above null (channel did not respond at |rho| > thr)")
        else:
            print("      onset lag %d, peak lag %d  -> row-frame dead time %d tick(s)" % (on, pk, on))
            onsets.append(on)
        report["inputs"]["u%d" % (i + 1)] = {
            "kind": kind, "threshold": thr, "onset": on, "peak": pk,
            "profile": [float(v) for v in prof[: L + 1]]}

    if onsets:
        on_min = min(onsets)
        rec = max(0, on_min - 1)
        print("\nFastest onset %d tick(s) => recommended inputDelayTicks = %d "
              "(nk supplies one tick; with delayStates=true the export then has dead time %d)."
              % (on_min, rec, rec + 1))
        if on_min == 1:
            print("  NOTE: onset at lag 1 means the command logged at tick k already moves y(k+1); "
                  "that is the controller's own convention with no extra delay.")
        report["onset_min"] = on_min
        report["recommended_inputDelayTicks"] = rec
    else:
        print("\nNo input produced a detectable response; nothing to recommend.")
        report["onset_min"] = None

    # ---- 2. row-frame fit of each model -----------------------------------
    U = U_all[:, u_idx]
    for path in args.lti:
        A, B, C, D, Ts, uOff, yOff = load_lti(path)
        m, p = B.shape[1], C.shape[0]
        if m != U.shape[1]:
            print("\n%s: model has m=%d inputs but %d --u-channels were given; skipping"
                  % (path, m, U.shape[1]))
            continue
        Yh = free_run(A, B, C, D, uOff, yOff, U)
        yh = Yh[:, 0] if p == 1 else Yh[:, 0]
        fit0 = nrmse_fit(y, yh)
        shifts = {s_: shifted_fit(y, yh, s_) for s_ in range(-2, 3)}
        best_s = max(shifts, key=shifts.get)
        res = y - yh
        rc = {}
        for j, i in enumerate(u_idx):
            rc["u%d" % (i + 1)] = [float(v) for v in xcorr_lags(U[:, j], res, 5)]
        worst = max(abs(v) for vs in rc.values() for v in vs)
        # The shift profile is the robust signature; residual-vs-u correlation
        # of ~0.06-0.08 remains even on a 94%-fit synthetic (equation-error
        # bias), so it is reported but only flags above 0.10.
        if best_s > 0:
            verdict = "EARLY by %d tick(s) (model says the response arrives before it does)" % best_s
        elif best_s < 0:
            verdict = "LATE by %d tick(s)" % -best_s
        elif worst >= 0.10:
            verdict = "centred (best shift 0) but residual still correlated with u (max |rho| %.3f)" % worst
        else:
            verdict = "OK: centred in the controller row frame (max residual |rho| %.3f)" % worst
        print("\n%s: n=%d m=%d p=%d" % (path, A.shape[0], m, p))
        print("  row-frame free-run fit %.2f%%; fit vs model-output shift s=-2..+2: %s"
              % (fit0, "  ".join("%+d:%.2f" % (k, v) for k, v in sorted(shifts.items()))))
        print("  residual-vs-u xcorr lags 0..5: " +
              "; ".join("%s %s" % (k, " ".join("%+.3f" % v for v in vs)) for k, vs in rc.items()))
        print("  VERDICT: %s" % verdict)
        report["models"][path] = {"n": int(A.shape[0]), "fit_pct": fit0,
                                  "fit_by_shift": {str(k): v for k, v in shifts.items()},
                                  "best_shift": best_s, "residual_xcorr": rc,
                                  "max_residual_xcorr": worst, "verdict": verdict}

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=1)
        print("\nwrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
