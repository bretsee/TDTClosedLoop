#!/usr/bin/env python
"""tracking_metrics.py -- score a closed/open-loop run: reference vs achieved.

    python rig/tracking_metrics.py --ref ref_steps.csv \
        --capture capture_rig_runcl4.csv --y-channels 1 \
        [--lti models/plant.lti] [--label cl4] [--json ...] [--png ...]

Joins a reference CSV (tick,r1..rp -- the file given to 4_mpc_server
-Reference or used to synthesize an open-loop tape) with a loop capture CSV
(tick,seq,t_ms,u1..uN,y1..yM) and reports, per reference column:

  error       RMSE and normalized RMSE (by ptp(r) and std(r))
  agreement   Pearson r at lag 0 and at the best lag (+-max-lag xcorr);
              regression slope y-on-r (achieved gain; 1.0 = perfect scale)
              and u-on-r per active input (control effort per unit reference)
  dynamics    event-triggered averages of y and u around reference transients
              (onsets where |diff(r)| exceeds --transient-thresh), peak delay
              and peak amplitude ratio vs the reference transient
  segmentation baseline-vs-active tracking index (std of y while the reference
              moves / std while it sits at its low plateau)

--y-channels is REQUIRED: capture y column (1-based) per reference column, in
the reference's column order -- the run's -FeatureChannel. A wrong mapping
silently scores the wrong electrode; there is no guessable default.

Verdict per channel: TRACKING (best-lag r >= 0.5 AND slope in [0.3, 1.5] AND
|lag| <= 10 ticks) / MARGINAL (r >= 0.3) / NOT TRACKING. A NOT TRACKING run
still exits 0 -- tracking failure is a RESULT; only load errors exit 1.

--self-test: score the capture's own y column against itself as the reference
(must give r = 1, slope = 1, lag = 0, RMSE = 0) plus a shuffled-reference
negative control. Run it once on any capture before trusting new numbers.
"""

import argparse
import csv
import json
import sys

import numpy as np

HARD, WARN, INFO = "FAIL", "warn", "info"


def read_csv_matrix(path):
    with open(path, newline="") as f:
        rows = []
        header = None
        for raw in csv.reader(f):
            if not raw:
                continue
            if raw[0].lstrip().startswith("#"):
                continue
            if header is None:
                header = raw
                continue
            rows.append([float(v) for v in raw])
    return header, np.array(rows)


def load_ref(path):
    h, M = read_csv_matrix(path)
    cols = [i for i, c in enumerate(h) if c.startswith("r")]
    if not cols:  # tolerate refs with no header conventions beyond tick,r*
        cols = list(range(1, M.shape[1]))
    return M[:, cols]


def load_capture(path):
    h, M = read_csv_matrix(path)
    u_cols = [i for i, c in enumerate(h) if c.startswith("u")]
    y_cols = [i for i, c in enumerate(h) if c.startswith("y")]
    return M[:, u_cols], M[:, y_cols]


def load_lti_offsets(path):
    """uOffset/yOffset from an .lti (same tokenizer as closed_loop_sim.load_lti)."""
    toks = []
    for raw in open(path).read().splitlines():
        toks.extend(raw.split("#", 1)[0].split())
    i = [0]

    def nxt():
        v = toks[i[0]]
        i[0] += 1
        return v

    assert nxt() == "LTI" and nxt() == "1", "not an LTI 1 file"
    assert nxt() == "Ts"; float(nxt())
    assert nxt() == "n"; n = int(nxt())
    assert nxt() == "m"; m = int(nxt())
    assert nxt() == "p"; p = int(nxt())
    for name, r, c in (("A", n, n), ("B", n, m), ("C", p, n), ("D", p, m)):
        assert nxt() == name
        for _ in range(r * c):
            nxt()
    uOff, yOff = np.zeros(m), np.zeros(p)
    while i[0] < len(toks):
        key = nxt()
        if key == "uOffset":
            uOff = np.array([float(nxt()) for _ in range(m)])
        elif key == "yOffset":
            yOff = np.array([float(nxt()) for _ in range(p)])
    return uOff, yOff


def best_lag(r, y, max_lag):
    """Lag in ticks maximizing |corr|; positive = y follows r."""
    rc, yc = r - r.mean(), y - y.mean()
    denom = np.sqrt((rc ** 2).sum() * (yc ** 2).sum())
    if denom <= 0:
        return 0, 0.0
    best = (0, 0.0)
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a, b = rc[:len(rc) - lag or None], yc[lag:]
        else:
            a, b = rc[-lag:], yc[:lag]
        if len(a) < 10:
            continue
        c = float(np.dot(a - a.mean(), b - b.mean()) /
                  max(np.sqrt(((a - a.mean()) ** 2).sum() * ((b - b.mean()) ** 2).sum()), 1e-30))
        if abs(c) > abs(best[1]):
            best = (lag, c)
    return best


def pearson(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def slope(x_ref, y_out):
    xc = x_ref - x_ref.mean()
    d = (xc ** 2).sum()
    return float((xc * (y_out - y_out.mean())).sum() / d) if d > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", help="reference CSV (tick,r1..rp)")
    ap.add_argument("--capture", required=True)
    ap.add_argument("--y-channels", type=int, nargs="+", required=True,
                    help="capture y column (1-based) per reference column")
    ap.add_argument("--u-channels", type=int, nargs="+", default=None,
                    help="1-based u columns to report (default: all that moved)")
    ap.add_argument("--lti", default=None,
                    help=".lti supplying uOffset/yOffset (informational centering)")
    ap.add_argument("--max-lag", type=int, default=50)
    ap.add_argument("--skip-ticks", type=int, default=50)
    ap.add_argument("--transient-thresh", type=float, default=None,
                    help="|diff(r)| onset threshold (default 0.25*max|diff(r)|)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--png", default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="use the capture's own y as the reference; assert exact "
                         "tracking and a failing shuffled control")
    args = ap.parse_args()

    issues = []

    def note(sev, msg):
        issues.append((sev, msg))
        print("  %s: %s" % (sev, msg))

    U, Y = load_capture(args.capture)
    if args.self_test:
        R = Y[:, [c - 1 for c in args.y_channels]].copy()
        print("SELF-TEST: reference = the capture's own y column(s) %s"
              % args.y_channels)
    else:
        if not args.ref:
            print("FAIL: --ref is required (or use --self-test)")
            return 1
        R = load_ref(args.ref)
    if R.shape[1] != len(args.y_channels):
        print("FAIL: reference has %d column(s) but %d --y-channels given"
              % (R.shape[1], len(args.y_channels)))
        return 1
    bad = [c for c in args.y_channels if not (1 <= c <= Y.shape[1])]
    if bad:
        print("FAIL: --y-channels %s outside capture's %d y columns" % (bad, Y.shape[1]))
        return 1

    uOff = yOff = None
    if args.lti:
        uOff, yOff = load_lti_offsets(args.lti)
        print("Model offsets from %s: uOffset %s, yOffset %s"
              % (args.lti, np.round(uOff, 6).tolist(), np.round(yOff, 6).tolist()))

    n_total = len(Y)
    if len(R) < n_total:  # reference shorter than capture: server holds last row
        R = np.vstack([R, np.repeat(R[-1:], n_total - len(R), axis=0)])
    n = n_total - args.skip_ticks
    if n < 100:
        print("FAIL: only %d overlapping ticks after --skip-ticks %d"
              % (n, args.skip_ticks))
        return 1
    sl = slice(args.skip_ticks, args.skip_ticks + n)
    R, Yc, Uc = R[sl], Y[sl], U[sl]

    moved = args.u_channels or [j + 1 for j in range(Uc.shape[1])
                                if np.ptp(Uc[:, j]) > 1e-12]
    label = args.label or args.capture
    print("Run %s: %d ticks scored (skip %d), ref %d col(s), u active: %s"
          % (label, n, args.skip_ticks, R.shape[1], moved))

    per = []
    verdicts = []
    for j in range(R.shape[1]):
        r = R[:, j].astype(float)
        y = Yc[:, args.y_channels[j] - 1].astype(float)
        if np.ptp(r) <= 1e-15:
            note(WARN, "ref col %d is constant -- lag/slope/ETA meaningless; "
                       "reporting DC error only" % (j + 1))
        rmse = float(np.sqrt(np.mean((y - r) ** 2)))
        nrmse_ptp = rmse / max(np.ptp(r), 1e-30)
        nrmse_std = rmse / max(r.std(), 1e-30)
        p0 = pearson(r, y)
        lag, pbest = best_lag(r, y, args.max_lag)
        s_yr = slope(r, y)
        s_ur = {u: slope(r, Uc[:, u - 1].astype(float)) for u in moved}
        # baseline / active segmentation
        r_lo = np.percentile(r, 20)
        base_mask = np.abs(r - r_lo) < 0.05 * max(np.ptp(r), 1e-30)
        t_idx = None
        eta = None
        if base_mask.sum() >= 20 and (~base_mask).sum() >= 20:
            tracking_index = float(y[~base_mask].std() / max(y[base_mask].std(), 1e-30))
        else:
            tracking_index = float("nan")
        # event-triggered averages
        dr = np.abs(np.diff(r))
        thr = args.transient_thresh or 0.25 * max(dr.max(), 1e-30)
        onsets = np.flatnonzero(dr > thr) + 1
        keep = []
        for t in onsets:
            if (not keep or t - keep[-1] >= 50) and t - 20 >= 0 and t + 80 < n:
                keep.append(int(t))
        eta_stats = None
        if len(keep) >= 2 and np.ptp(r) > 1e-15:
            E_y = np.array([y[t - 20:t + 80] for t in keep])
            E_r = np.array([r[t - 20:t + 80] for t in keep])
            E_u = np.array([Uc[t - 20:t + 80, moved[0] - 1] for t in keep]) \
                if moved else None
            my = E_y.mean(axis=0) - E_y[:, :20].mean()
            mr = E_r.mean(axis=0) - E_r[:, :20].mean()
            pk_r = int(np.argmax(np.abs(mr[20:]))) if np.ptp(mr) > 0 else 0
            pk_y = int(np.argmax(np.abs(my[20:]))) if np.ptp(my) > 0 else 0
            ratio = float(my[20 + pk_y] / mr[20 + pk_r]) if abs(mr[20 + pk_r]) > 1e-30 else float("nan")
            eta_stats = dict(n_transients=len(keep), peak_delay_ticks=pk_y - pk_r,
                             peak_ratio=ratio)
            eta = dict(t=np.arange(-20, 80).tolist(), y=my.tolist(), r=mr.tolist(),
                       y_sem=(E_y.std(axis=0) / np.sqrt(len(keep))).tolist(),
                       u=(E_u.mean(axis=0).tolist() if E_u is not None else None))
        if pbest >= 0.5 and 0.3 <= s_yr <= 1.5 and abs(lag) <= 10:
            v = "TRACKING"
        elif pbest >= 0.3:
            v = "MARGINAL"
        else:
            v = "NOT TRACKING"
        verdicts.append(v)
        per.append(dict(ref_col=j + 1, y_channel=args.y_channels[j], rmse=rmse,
                        nrmse_ptp=nrmse_ptp, nrmse_std=nrmse_std,
                        pearson_lag0=p0, pearson_best=pbest, best_lag_ticks=lag,
                        slope_y_on_r=s_yr,
                        slope_u_on_r={("u%d" % u): s for u, s in s_ur.items()},
                        tracking_index=tracking_index, eta=eta_stats,
                        verdict=v))
        print("  ref %d -> y%-2d  RMSE %.4g (%.1f%% of ptp)  r0 %.3f  "
              "rBest %.3f @ lag %+d  slope y/r %.3f  trackIdx %s  %s"
              % (j + 1, args.y_channels[j], rmse, 100 * nrmse_ptp, p0, pbest,
                 lag, s_yr,
                 ("%.2f" % tracking_index) if tracking_index == tracking_index else "-",
                 v))
        for u, s in s_ur.items():
            print("      slope u%d-on-r: %.4g" % (u, s))
        if eta_stats:
            print("      transients: %d, ETA peak delay %+d ticks, peak ratio %.3f"
                  % (eta_stats["n_transients"], eta_stats["peak_delay_ticks"],
                     eta_stats["peak_ratio"]))

        if args.png and j == 0:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 2, figsize=(11, 7))
            t = np.arange(n)
            ax[0, 0].plot(t, r, "k", lw=0.8, label="reference")
            ax[0, 0].plot(t, y, "C0", lw=0.8, alpha=0.8,
                          label="y%d" % args.y_channels[j])
            ax[0, 0].legend(fontsize=8)
            ax[0, 0].set(title="%s: reference vs achieved" % label, xlabel="tick")
            for u in moved:
                ax[0, 1].plot(t, Uc[:, u - 1], lw=0.7, label="u%d" % u)
            ax[0, 1].legend(fontsize=8)
            ax[0, 1].set(title="commands", xlabel="tick")
            if eta:
                tt = np.array(eta["t"])
                my, sem = np.array(eta["y"]), np.array(eta["y_sem"])
                ax[1, 0].plot(tt, np.array(eta["r"]), "k", label="ref")
                ax[1, 0].plot(tt, my, "C0", label="y")
                ax[1, 0].fill_between(tt, my - sem, my + sem, color="C0", alpha=0.3)
                ax[1, 0].legend(fontsize=8)
                ax[1, 0].set(title="event-triggered average", xlabel="ticks from onset")
            ax[1, 1].plot(r, y, ".", ms=2, alpha=0.4)
            xx = np.array([r.min(), r.max()])
            ax[1, 1].plot(xx, y.mean() + s_yr * (xx - r.mean()), "r",
                          label="slope %.2f" % s_yr)
            ax[1, 1].legend(fontsize=8)
            ax[1, 1].set(title="y vs r (rBest %.2f)" % pbest, xlabel="r", ylabel="y")
            fig.tight_layout()
            fig.savefig(args.png, dpi=120)
            print("  wrote %s" % args.png)

    if args.self_test:
        p = per[0]
        rng = np.random.default_rng(0)
        r_sh = R[:, 0].copy()
        rng.shuffle(r_sh)
        p_sh = pearson(r_sh, Yc[:, args.y_channels[0] - 1])
        ok = (p["rmse"] < 1e-12 and abs(p["pearson_best"] - 1) < 1e-9 and
              abs(p["slope_y_on_r"] - 1) < 1e-9 and p["best_lag_ticks"] == 0 and
              abs(p_sh) < 0.2)
        print("\nSELF-TEST %s  (identity: rmse %.2g, r %.6f, slope %.6f, lag %d; "
              "shuffled control r %.3f)"
              % ("PASS" if ok else "FAIL", p["rmse"], p["pearson_best"],
                 p["slope_y_on_r"], p["best_lag_ticks"], p_sh))
        return 0 if ok else 1

    overall = ("TRACKING" if all(v == "TRACKING" for v in verdicts)
               else ("NOT TRACKING" if all(v == "NOT TRACKING" for v in verdicts)
                     else "MIXED/MARGINAL"))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(dict(label=label, ref=args.ref, capture=args.capture,
                           lti=args.lti, n_ticks=n, skip_ticks=args.skip_ticks,
                           y_channels=args.y_channels, u_channels=moved,
                           per_channel=per, overall=overall), f, indent=1)
        print("  wrote %s" % args.json)
    warns = sum(1 for s, _ in issues if s == WARN)
    print("\nVERDICT: %s  (%d warning(s))" % (overall, warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
