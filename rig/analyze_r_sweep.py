#!/usr/bin/env python
"""analyze_r_sweep.py -- per-block tracking and charge for an interleaved
effort-weight (R) sweep run (build_r_schedule.py + cpp_controller --r-schedule).

    python rig/analyze_r_sweep.py --capture day_X/capture_mpc_rsweep.csv \
        --ref day_X/ref_mix_r1.csv --rsched day_X/rsched_r1.json \
        --y-channels 64 --u-channels 4 6 [--hold 15] [--lat day_X/server_lat_...csv] \
        [--json out.json] [--png out.png]

Per block (one R level, B events): Pearson r at lag 0 and at the best lag,
RMSE, total charge sum(u) in uA-ticks, above-hold charge sum(max(u-H, 0)),
and the block's order in the run. Then an ordinary least-squares fit

    r_block ~ 1 + [R-level dummies] + order

so the R effect is read with block order (= drift) as a covariate, which is
the point of interleaving (09-10's one-R-per-run sweep was drift-confounded).
Also checks, when --lat is given, that rW0 actually switched at every block
start (the server's telemetry column), so a schedule that never applied cannot
masquerade as "no R effect".

Charge convention matches trk_charge: sum over ticks of the commanded uA on the
listed --u-channels (1 tick = 10 ms), no pulse-width scaling.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tracking_metrics import load_ref, load_capture, pearson, best_lag   # noqa: E402


def read_lat(path):
    """seq -> rW0 from the server latency CSV (skips the '#' banner)."""
    out = {}
    with open(path) as f:
        hdr = None
        for ln in f:
            if ln.startswith("#") or not ln.strip():
                continue
            cells = ln.strip().split(",")
            if hdr is None:
                hdr = cells
                continue
            if len(cells) == len(hdr):
                try:
                    out[int(float(cells[0]))] = float(cells[hdr.index("rW0")])
                except (ValueError, IndexError):
                    pass
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--rsched", required=True, help="rsched_rN.json from build_r_schedule.py")
    ap.add_argument("--y-channels", type=int, nargs="+", required=True, help="1-based feature columns")
    ap.add_argument("--u-channels", type=int, nargs="+", required=True, help="1-based command columns")
    ap.add_argument("--hold", type=float, default=0.0, help="hold level H (uA) for above-hold charge")
    ap.add_argument("--max-lag", type=int, default=20)
    ap.add_argument("--lat", default=None, help="server latency CSV to verify rW0 switching")
    ap.add_argument("--json", default=None)
    ap.add_argument("--png", default=None)
    args = ap.parse_args()

    with open(args.rsched) as f:
        rs = json.load(f)
    blocks = rs["blocks"]
    U, Y = load_capture(args.capture)
    R = load_ref(args.ref)
    n = min(len(U), len(R))
    U, Y, R = U[:n], Y[:n], R[:n]
    yi = [c - 1 for c in args.y_channels]
    ui = [c - 1 for c in args.u_channels]
    if R.shape[1] < len(yi):
        print("FAIL: reference has %d column(s) but %d --y-channels given" % (R.shape[1], len(yi)))
        return 1

    lat = read_lat(args.lat) if args.lat else None

    rows = []
    for b in blocks:
        a, z = b["start_tick"] - 1, min(b["end_tick"], n)
        if z - a < 50:
            continue
        y = Y[a:z][:, yi]
        r = R[a:z][:, :len(yi)]
        u = U[a:z][:, ui]
        r0 = float(np.mean([pearson(r[:, j], y[:, j]) for j in range(len(yi))]))
        lags = [best_lag(r[:, j], y[:, j], args.max_lag) for j in range(len(yi))]
        rb = float(np.mean([l[1] for l in lags]))
        lagb = int(np.round(np.mean([l[0] for l in lags])))
        rmse = float(np.sqrt(np.mean((y - r) ** 2)))
        charge = float(u.sum())
        above = float(np.maximum(u - args.hold, 0.0).sum())
        row = {"block": b["block"], "R": b["r"], "order": b["block"], "events": b["events"],
               "ticks": [a + 1, z], "r0": r0, "r_best": rb, "lag_best": lagb, "rmse": rmse,
               "charge_uAticks": charge, "above_hold_uAticks": above,
               "mean_u": float(u.mean())}
        if lat is not None:
            seqs = [s for s in range(a + 1, z + 1) if s in lat]
            if seqs:
                vals = np.array([lat[s] for s in seqs])
                row["rW0_median"] = float(np.median(vals))
                row["rW0_applied"] = bool(abs(np.median(vals) - b["r"]) <= 1e-9 * max(1.0, b["r"]))
        rows.append(row)

    if not rows:
        print("FAIL: no block covered by the capture")
        return 1

    levels = sorted(set(r["R"] for r in rows))
    print("block   R        events    r0      rBest(lag)   RMSE       charge   above-hold   rW0")
    for r in rows:
        print("%5d  %-8g %3d-%3d  %+.3f  %+.3f(%+d)  %.3g  %9.0f  %9.0f   %s" % (
            r["block"], r["R"], r["events"][0], r["events"][1], r["r0"], r["r_best"], r["lag_best"],
            r["rmse"], r["charge_uAticks"], r["above_hold_uAticks"],
            ("ok" if r.get("rW0_applied") else "NOT APPLIED") if "rW0_applied" in r else "n/a"))

    # per-level means
    summary = {}
    for L in levels:
        sel = [r for r in rows if r["R"] == L]
        summary[str(L)] = {"n_blocks": len(sel),
                           "r0_mean": float(np.mean([r["r0"] for r in sel])),
                           "charge_mean": float(np.mean([r["charge_uAticks"] for r in sel])),
                           "above_hold_mean": float(np.mean([r["above_hold_uAticks"] for r in sel]))}
    print("\nper R level:")
    for L in levels:
        s = summary[str(L)]
        print("  R=%-8g blocks %d  r0 %.3f  charge %.0f  above-hold %.0f" %
              (L, s["n_blocks"], s["r0_mean"], s["charge_mean"], s["above_hold_mean"]))

    # OLS: r0 ~ 1 + dummies(level 2..) + order  (level 1 = reference)
    ols = None
    if len(rows) >= len(levels) + 2:
        X = np.ones((len(rows), 1 + (len(levels) - 1) + 1))
        for i, r in enumerate(rows):
            for j, L in enumerate(levels[1:]):
                X[i, 1 + j] = 1.0 if r["R"] == L else 0.0
            X[i, -1] = r["order"]
        yv = np.array([r["r0"] for r in rows])
        beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
        resid = yv - X @ beta
        dof = max(1, len(rows) - X.shape[1])
        s2 = float(resid @ resid) / dof
        try:
            cov = s2 * np.linalg.inv(X.T @ X)
            se = np.sqrt(np.diag(cov))
        except np.linalg.LinAlgError:
            se = np.full(len(beta), np.nan)
        ols = {"reference_level": levels[0],
               "intercept": float(beta[0]),
               "level_effects": {str(L): {"beta": float(beta[1 + j]), "se": float(se[1 + j])}
                                 for j, L in enumerate(levels[1:])},
               "order_slope_per_block": float(beta[-1]), "order_se": float(se[-1]),
               "dof": dof}
        print("\nOLS r0 ~ R level + block order (reference R=%g):" % levels[0])
        for L, e in ols["level_effects"].items():
            print("  R=%-8s effect %+.3f (se %.3f)" % (L, e["beta"], e["se"]))
        print("  order slope %+.4f r/block (se %.4f) <- drift covariate" % (beta[-1], se[-1]))
    else:
        print("\n(too few blocks for the OLS; need >= levels + 2)")

    not_applied = [r["block"] for r in rows if r.get("rW0_applied") is False]
    if not_applied:
        print("\nWARNING: rW0 telemetry shows the scheduled R was NOT in force in block(s) %s" % not_applied)

    out = {"capture": args.capture, "ref": args.ref, "rsched": args.rsched, "hold": args.hold,
           "blocks": rows, "per_level": summary, "ols": ols, "not_applied": not_applied}
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)
        print("wrote %s" % args.json)
    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cols = {L: c for L, c in zip(levels, ["#2a78d6", "#eb6834", "#1baf7a", "#8a5cd6", "#777777"])}
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        for r in rows:
            ax[0].scatter(r["order"], r["r0"], color=cols[r["R"]], s=40)
            ax[1].scatter(r["order"], r["above_hold_uAticks"], color=cols[r["R"]], s=40)
        for L in levels:
            ax[0].scatter([], [], color=cols[L], label="R=%g" % L)
        ax[0].set_xlabel("block (run order)"); ax[0].set_ylabel("Pearson r (lag 0)")
        ax[1].set_xlabel("block (run order)"); ax[1].set_ylabel("above-hold charge (uA-ticks)")
        ax[0].legend(frameon=False, fontsize=8)
        ax[0].set_title("tracking by block"); ax[1].set_title("charge by block")
        fig.tight_layout()
        fig.savefig(args.png, dpi=150)
        print("wrote %s" % args.png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
