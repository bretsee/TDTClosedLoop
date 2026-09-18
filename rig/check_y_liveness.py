#!/usr/bin/env python
r"""check_y_liveness.py -- is the amplifier actually feeding the loop? (60 s rule)

    python rig\check_y_liveness.py --capture day_<day>\capture_mpc_mixr1.csv
    python rig\check_y_liveness.py --capture <csv> --watch      # re-check every 5 s while a run grows
    python rig\check_y_liveness.py --capture <csv> --baseline 3.3e-5

The 2026-09-10 PZ2-off incident: an operator battery-saving step powered the
amplifier down between runs and THREE runs (~1.3M uA-ticks of stimulation)
were recorded against all-zero features. Nothing on the loop side complains:
the PO8e keeps streaming zeros, the controller keeps solving, the capture
keeps growing. This script is the missing alarm. Run it in the FIRST minute
of every run (or leave --watch running in a spare terminal).

Checks on the y1..yN feature columns of the capture (rows so far):
  DEAD      zero-fraction >= 0.5 on the median channel, or every channel
            constant  -> amp off / stream dead.  Exit 3.  STOP THE RUN.
  SUSPECT   median |y| < 0.2 x --baseline (if given) or > 20 x -> exit 2
            (bank off, wrong gain, or saturated).
  LIVE      otherwise -> exit 0.  Prints per-bank medians so a dead bank
            (e.g. ch 33-64 on a two-headstage prep) is visible.
"""
import argparse
import csv
import os
import sys
import time

import numpy as np


def read_tail(path, max_rows=6000):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        return None, None
    hdr = rows[0]
    yi = [i for i, h in enumerate(hdr) if h.startswith("y")]
    body = rows[1:][-max_rows:]
    Y = np.array([[float(r[i]) for i in yi] for r in body if len(r) == len(hdr)])
    return Y, len(rows) - 1


def verdict(Y, baseline):
    n_rows, n_ch = Y.shape
    zf = (np.abs(Y) < 1e-12).mean(axis=0)               # per-channel zero fraction
    const = (Y.std(axis=0) < 1e-15)
    med_abs = np.median(np.abs(Y), axis=0)
    banks = {}
    for b0 in range(0, n_ch, 32):
        banks["ch%d-%d" % (b0 + 1, min(b0 + 32, n_ch))] = float(np.median(med_abs[b0:b0 + 32]))
    if float(np.median(zf)) >= 0.5 or bool(const.all()):
        return "DEAD", zf, med_abs, banks
    if baseline:
        m = float(np.median(med_abs))
        if m < 0.2 * baseline or m > 20 * baseline:
            return "SUSPECT", zf, med_abs, banks
    dead_banks = [k for k, v in banks.items() if v < 1e-12]
    if dead_banks:
        return "SUSPECT", zf, med_abs, banks
    return "LIVE", zf, med_abs, banks


def report(path, baseline):
    Y, n_total = read_tail(path)
    if Y is None or Y.size == 0:
        print("y-liveness: %s has no rows yet" % os.path.basename(path))
        return 1
    v, zf, med_abs, banks = verdict(Y, baseline)
    n_dead = int((zf >= 0.5).sum())
    print("y-liveness: %-8s %s  rows %d  dead ch %d/%d  median|y| %.3g  banks %s"
          % (v, os.path.basename(path), n_total, n_dead, Y.shape[1],
             float(np.median(med_abs)),
             " ".join("%s=%.2g" % (k, b) for k, b in banks.items())))
    if v == "DEAD":
        print("  >>> FEATURES ARE ZERO. Amp/PZ2 off or stream dead. STOP THE RUN, fix, rerun. <<<")
        return 3
    if v == "SUSPECT":
        print("  >>> feature level off-scale vs baseline or a bank is dead -- check PZ2 banks/gain. <<<")
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--baseline", type=float, default=None, help="today's quiet-capture MAV baseline (V)")
    ap.add_argument("--watch", action="store_true", help="re-check every --every seconds until Ctrl+C")
    ap.add_argument("--every", type=float, default=5.0)
    a = ap.parse_args()
    if not a.watch:
        return report(a.capture, a.baseline)
    last = -1
    try:
        while True:
            if os.path.isfile(a.capture):
                rc = report(a.capture, a.baseline)
                if rc == 3:
                    return 3
            time.sleep(a.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
