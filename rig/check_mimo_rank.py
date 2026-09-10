#!/usr/bin/env python
r"""check_mimo_rank.py -- DC-gain rank/conditioning check for a fitted MIMO plant.

Run this on the .lti exported by the Phase-4 MIMO fit BEFORE committing to a
control channel set. If the effective rank of the DC gain is below p (the
number of controlled outputs), the MPC is being asked to steer directions the
actuators cannot reach independently -- swap output channels (or drop to a
smaller p) rather than discovering it in the tracking scores.

    python rig\check_mimo_rank.py --model plant_rnd1.lti
    python rig\check_mimo_rank.py --model plant_rnd1.lti --sv-thresh 0.1

Reads the plain-text LTI export (A,B,C,D,Ts,uOffset,yOffset).
DC gain G = C (I-A)^-1 B + D  (valid: our fitted plants are stable).
Effective rank = # singular values >= sv_thresh * sigma_max (default 0.1).

Verdict lines:
  PASS  effective rank >= p and condition number < 20
  WARN  effective rank >= p but conditioning poor (>= 20): tracking will be
        charge-hungry in the weak direction; consider per-output qWeight or a
        different channel pair
  FAIL  effective rank < p: outputs are not independently steerable with
        these inputs -- change the output set
"""
import argparse
import sys

import numpy as np


def read_lti(path):
    with open(path) as f:
        tokens = []
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                tokens.extend(line.split())
    it = iter(tokens)
    if next(it) != "LTI":
        raise ValueError(f"{path}: not an LTI export (missing 'LTI' magic)")
    next(it)  # version
    mats = {}
    scalars = {}
    key = None
    # scalar keys carry one value; matrix keys are followed by n*cols numbers
    scalar_keys = {"Ts": float, "n": int, "m": int, "p": int}
    vals = []
    for tok in it:
        if tok in scalar_keys:
            scalars[tok] = scalar_keys[tok](next(it))
        elif tok in ("A", "B", "C", "D", "uOffset", "yOffset"):
            if key is not None:
                mats[key] = vals
            key, vals = tok, []
        else:
            vals.append(float(tok))
    if key is not None:
        mats[key] = vals
    n, m, p = scalars["n"], scalars["m"], scalars["p"]
    A = np.array(mats["A"]).reshape(n, n)
    B = np.array(mats["B"]).reshape(n, m)
    C = np.array(mats["C"]).reshape(p, n)
    D = np.array(mats["D"]).reshape(p, m)
    return A, B, C, D, scalars, mats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help=".lti export from export_plant_lti")
    ap.add_argument("--sv-thresh", type=float, default=0.1,
                    help="singular value >= thresh*sigma_max counts toward rank (default 0.1)")
    ap.add_argument("--cond-warn", type=float, default=20.0,
                    help="condition number above this draws a WARN (default 20)")
    args = ap.parse_args()

    A, B, C, D, sc, mats = read_lti(args.model)
    n, m, p = sc["n"], sc["m"], sc["p"]
    poles = np.linalg.eigvals(A)
    rho = float(np.max(np.abs(poles)))
    print(f"model: {args.model}")
    print(f"  n={n} states, m={m} inputs (stim pairs), p={p} outputs (control channels), "
          f"Ts={sc['Ts']*1e3:.4f} ms")
    print(f"  spectral radius {rho:.4f} " + ("(stable)" if rho < 1 else "(UNSTABLE -- DC gain meaningless)"))
    if rho >= 1:
        print("VERDICT: FAIL (unstable fit; refit before any rank claim)")
        sys.exit(1)

    G = C @ np.linalg.solve(np.eye(n) - A, B) + D
    print("  DC gain G (p x m), volts per uA:")
    for i in range(p):
        print("    " + "  ".join(f"{G[i, j]: .3e}" for j in range(m)))

    U, S, Vt = np.linalg.svd(G)
    smax = S[0] if S[0] > 0 else 1.0
    eff_rank = int(np.sum(S >= args.sv_thresh * smax))
    cond = float(S[0] / S[-1]) if S[-1] > 0 else np.inf
    print(f"  singular values: " + "  ".join(f"{s:.3e}" for s in S)
          + f"   (ratios to max: " + "  ".join(f"{s/smax:.3f}" for s in S) + ")")
    print(f"  effective rank {eff_rank} of p={p} at thresh {args.sv_thresh}; condition {cond:.1f}")
    for k in range(min(p, len(S))):
        outdir = "  ".join(f"{U[i, k]:+.2f}" for i in range(p))
        indir = "  ".join(f"{Vt[k, j]:+.2f}" for j in range(m))
        print(f"    mode {k+1}: output dir [{outdir}]  <- input dir [{indir}]  gain {S[k]:.3e}")

    if eff_rank < p:
        print(f"VERDICT: FAIL -- only {eff_rank} independently steerable output direction(s); "
              f"swap control channels or reduce p")
        sys.exit(1)
    if cond >= args.cond_warn:
        print(f"VERDICT: WARN -- rank OK but condition {cond:.1f} >= {args.cond_warn}: weak "
              f"direction will be charge-hungry; consider different channels or per-output weights")
        sys.exit(0)
    print("VERDICT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
