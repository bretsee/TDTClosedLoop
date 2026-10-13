#!/usr/bin/env python
"""qp_sweep.py -- QP conditioning sweep: iteration cap x tolerance x effort ratio, in sim.

    python rig/qp_sweep.py --out day_X/qp_sweep.json [--ticks 3000] [--plant plant_opfit12_d2.lti]

For each (effort_ratio, qp_iters, qp_tol) runs training/closed_loop_sim.py --launch
(plant = model, reference day_2026-09-10/ref_mix_r1.csv, pairs 4,6 -> feature 64) and
collects from the server latency log: converged %, mean/p99 computeMs, mean qpIters, and
tracking r0 (capture y64 vs reference, SKIP 50). Serial, one sim at a time.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable


def run_one(plant, rho, iters, tol, ticks, out_dir, tag):
    cap = os.path.join(out_dir, "capture_qp_%s.csv" % tag)
    cmd = [PY, os.path.join(REPO, "training", "closed_loop_sim.py"), "--plant", plant, "--ticks", str(ticks),
           "--pairs", "4,6", "--feature-map", "64", "--output-count", "8",
           "--launch", "--launch-args", "--pairs", "4,6", "--feature-map", "64", "--q-weight", "1e12",
           "--effort-ratio", "%g" % rho, "--qp-iters", str(iters), "--qp-tol", "%g" % tol,
           "--control-horizon", "20", "--umax", "30", "--capture", cap,
           "--reference", os.path.join(REPO, "day_2026-09-10", "ref_mix_r1.csv")]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
    secs = time.time() - t0
    lat = os.path.join(out_dir, "server_lat_capture_qp_%s.csv" % tag)
    rec = dict(tag=tag, rho=rho, qp_iters=iters, qp_tol=tol, rc=p.returncode, secs=round(secs, 1))
    if os.path.isfile(lat):
        import pandas as pd
        d = pd.read_csv(lat, comment="#")
        rec.update(ticks=int(len(d)), conv_pct=float(100.0 * d["qpConv"].mean()),
                   iters_mean=float(d["qpIters"].mean()), iters_p99=float(np.percentile(d["qpIters"], 99)),
                   compute_mean_ms=float(d["computeMs"].mean()), compute_p99_ms=float(np.percentile(d["computeMs"], 99)),
                   compute_max_ms=float(d["computeMs"].max()))
    if os.path.isfile(cap):
        import pandas as pd
        c = pd.read_csv(cap)
        r = pd.read_csv(os.path.join(REPO, "day_2026-09-10", "ref_mix_r1.csv"))
        n = min(len(c), len(r))
        y = c["y64"].to_numpy()[50:n] if "y64" in c else c[[k for k in c.columns if k.startswith("y")][0]].to_numpy()[50:n]
        rr = r["r1"].to_numpy()[50:n]
        rz, yz = rr - rr.mean(), y - y.mean()
        den = np.linalg.norm(rz) * np.linalg.norm(yz)
        rec["r0"] = float(np.dot(rz, yz) / den) if den > 0 else float("nan")
        rec["charge"] = float(c[[k for k in c.columns if k.startswith("u")]].to_numpy()[50:n].sum())
    tail = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()][-2:]
    rec["tail"] = tail
    print("%-22s rc=%d %5.0f s  conv %5.1f%%  iters %6.1f (p99 %6.0f)  compute %.3f ms (p99 %.3f, max %.3f)  r0 %s"
          % (tag, rec["rc"], secs, rec.get("conv_pct", float("nan")), rec.get("iters_mean", float("nan")),
             rec.get("iters_p99", float("nan")), rec.get("compute_mean_ms", float("nan")),
             rec.get("compute_p99_ms", float("nan")), rec.get("compute_max_ms", float("nan")),
             ("%.3f" % rec["r0"]) if "r0" in rec else "n/a"), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plant", default="plant_opfit12_d2.lti")
    ap.add_argument("--ticks", type=int, default=3000)
    ap.add_argument("--rhos", default="0.1,0.01")
    ap.add_argument("--iters", default="200,1000,5000")
    ap.add_argument("--tols", default="1e-7,1e-6")
    args = ap.parse_args()
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    res = []
    for rho in [float(x) for x in args.rhos.split(",")]:
        for it in [int(x) for x in args.iters.split(",")]:
            for tol in [float(x) for x in args.tols.split(",")]:
                tag = "rho%g_it%d_tol%g" % (rho, it, tol)
                res.append(run_one(args.plant, rho, it, tol, args.ticks, out_dir, tag))
                with open(args.out, "w") as f:
                    json.dump(dict(plant=args.plant, ticks=args.ticks, runs=res), f, indent=1)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
