#!/usr/bin/env python
r"""build_decoupled_ref.py -- decoupled-target reference for the MIMO selectivity demo.

Takes an existing p-column reference (tick,r1..rp -- e.g. a ref_mix built by
build_interleaved_run) and produces a reference where only ONE output at a time
is asked to track its template while every other output is held at its own
baseline, switching the active output each segment (round-robin). Tracking this
reference demonstrates output SELECTION -- independent steering -- not just
correlated tracking of a shared touch event; it is the first-in-class MIMO
exhibit identified in RESEARCH_CONTROL_NOVELTY_2026-09-09.md.

    python rig\build_decoupled_ref.py --ref day_X\ref_mix_r1.csv --out day_X\ref_decoupled_r1.csv
    python rig\build_decoupled_ref.py --ref ref_mimo_test.csv --out ref_decoupled_test.csv --segments 4

Baseline per column = its 5th-percentile value (robust resting level).
Scoring: score each segment on the ACTIVE channel's tracking AND the inactive
channels' deviation from baseline (selectivity = active tracks, inactive stays).
A schedule sidecar JSON records segment boundaries and active columns.
"""
import argparse
import json

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="input tick,r1..rp reference CSV")
    ap.add_argument("--out", required=True, help="output decoupled reference CSV")
    ap.add_argument("--segments", type=int, default=0,
                    help="number of equal segments (default 2*p: each output "
                         "active twice, round-robin)")
    args = ap.parse_args()

    d = pd.read_csv(args.ref)
    rcols = [c for c in d.columns if c.startswith("r") and c[1:].isdigit()]
    p = len(rcols)
    if p < 2:
        raise SystemExit(f"FATAL: {args.ref} has {p} r-column(s); decoupling needs p >= 2")
    n = len(d)
    nseg = args.segments if args.segments > 0 else 2 * p
    baselines = {c: float(np.percentile(d[c], 5)) for c in rcols}

    out = d.copy()
    bounds = np.linspace(0, n, nseg + 1).astype(int)
    schedule = []
    for s in range(nseg):
        lo, hi = bounds[s], bounds[s + 1]
        active = rcols[s % p]
        for c in rcols:
            if c != active:
                out.loc[out.index[lo:hi], c] = baselines[c]
        schedule.append({"segment": s, "row_start": int(lo), "row_end": int(hi),
                         "active": active, "inactive_held_at": {c: baselines[c]
                                                                for c in rcols if c != active}})

    out.to_csv(args.out, index=False, float_format="%.10g")
    side = args.out.rsplit(".", 1)[0] + "_schedule.json"
    with open(side, "w") as f:
        json.dump({"source_ref": args.ref, "p": p, "segments": schedule,
                   "baselines": baselines}, f, indent=2)
    print(f"wrote {args.out}: {n} rows x {p} outputs, {nseg} segments "
          f"(each output active {nseg // p}x round-robin)")
    print(f"wrote {side}")
    for s in schedule:
        print(f"  seg {s['segment']}: rows {s['row_start']}..{s['row_end']} "
              f"active={s['active']}")


if __name__ == "__main__":
    main()
