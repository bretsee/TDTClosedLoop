#!/usr/bin/env python
"""build_r_schedule.py -- effort-weight schedule for a time-controlled,
interleaved R sweep inside ONE closed-loop run (acute-3 plan item 4, Tier C 6e).

    python rig/build_r_schedule.py --schedule day_X/schedule_mix_r1.json \
        --block-events 20 --r 100 30 10 --out day_X/rsched_r1.csv

Reads the interleaved-run schedule JSON (build_interleaved_run.py: lead_ticks,
period_ticks, events[].onset_tick) and writes

    <out>.csv    tick,r1[,r2..]   consumed by cpp_controller --r-schedule
    <out>.json   per block: index, R, first/last event, start/end tick

Block k covers events [k*B+1, (k+1)*B]; its R is --r cycled in order
(R100, R30, R10, R100, ...). The weight switches at the first tick of the
block's first period (lead_ticks + k*B*period_ticks + 1), i.e. BEFORE the
event onset, so the horizon preview already runs under the new weight.

Why interleave: the 09-10 R sweep was one R per run, so drift between runs
confounded the charge-fidelity frontier. Cycling R every B events inside one
12-minute run puts every R level at every point of the drift curve;
analyze_r_sweep.py then fits r ~ R-level + block order.

--m sets how many weight columns to write (one per controller input; all equal).
--anchor-r is the literal cpp --r-weight scale the levels are multiplied by
(default 1: --r 100 30 10 are the literal weights, as in the runbook).
"""

import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schedule", required=True, help="schedule_mix_rN.json")
    ap.add_argument("--block-events", type=int, default=20)
    ap.add_argument("--r", type=float, nargs="+", required=True,
                    help="R levels in cycling order, e.g. 100 30 10")
    ap.add_argument("--m", type=int, default=1, help="weight columns (controller inputs)")
    ap.add_argument("--anchor-r", type=float, default=1.0)
    ap.add_argument("--out", required=True, help="output CSV path (JSON sidecar alongside)")
    args = ap.parse_args()

    with open(args.schedule) as f:
        sch = json.load(f)
    events = sch["events"]
    lead = int(sch.get("lead_ticks", 172))
    period = int(sch.get("period_ticks", 220))
    n_ev = len(events)
    B = args.block_events
    if B <= 0 or n_ev < B:
        print("FAIL: --block-events %d but the schedule has %d events" % (B, n_ev))
        return 1
    n_blocks = n_ev // B
    if n_ev % B:
        print("WARN: %d trailing event(s) do not fill a block and keep the last R" % (n_ev % B))
    if n_blocks % len(args.r):
        print("WARN: %d blocks is not a multiple of %d R levels -- levels are unbalanced "
              "(use --block-events so that blocks = k * levels)" % (n_blocks, len(args.r)))

    rows, blocks = [], []
    for k in range(n_blocks):
        R = args.r[k % len(args.r)] * args.anchor_r
        first, last = events[k * B], events[min((k + 1) * B, n_ev) - 1]
        start = lead + k * B * period + 1
        end = lead + (k + 1) * B * period
        rows.append((start, R))
        blocks.append({"block": k + 1, "r": R, "events": [int(first["event"]), int(last["event"])],
                       "onset_first": int(first["onset_tick"]), "onset_last": int(last["onset_tick"]),
                       "start_tick": start, "end_tick": end})
    # sanity: the first event of each block must fall inside the block's ticks
    for b in blocks:
        if not (b["start_tick"] <= b["onset_first"] <= b["end_tick"]):
            print("FAIL: block %d event onset %d outside [%d, %d] -- schedule not lead+k*period?"
                  % (b["block"], b["onset_first"], b["start_tick"], b["end_tick"]))
            return 1

    with open(args.out, "w", newline="") as f:
        f.write("tick," + ",".join("r%d" % (i + 1) for i in range(args.m)) + "\n")
        for tick, R in rows:
            f.write("%d," % tick + ",".join("%.9g" % R for _ in range(args.m)) + "\n")
    side = os.path.splitext(args.out)[0] + ".json"
    with open(side, "w") as f:
        json.dump({"schedule": args.schedule, "block_events": B, "levels": args.r,
                   "anchor_r": args.anchor_r, "lead_ticks": lead, "period_ticks": period,
                   "n_events": n_ev, "blocks": blocks}, f, indent=1)
    print("R SCHEDULE OK: %d blocks x %d events, levels %s cycling; %d switches -> %s (+ %s)"
          % (n_blocks, B, args.r, len(rows), args.out, os.path.basename(side)))
    for b in blocks:
        print("  block %2d  R=%-8g events %3d-%3d  ticks %5d-%5d" %
              (b["block"], b["r"], b["events"][0], b["events"][1], b["start_tick"], b["end_tick"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
