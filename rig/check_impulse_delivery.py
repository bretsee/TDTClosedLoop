#!/usr/bin/env python
"""check_impulse_delivery.py -- audit what the RZ2 actually received/delivered.

    python rig/check_impulse_delivery.py --block <tdt_block_dir> \
        [--capture capture_rig_run<label>.csv]

Companion to validate_impulse_design.py (which audits the DESIGNED sequence in
the server capture). This one reads the TDT block and answers, per UDP word:

  UDP1   pulse events on the wire, amplitudes, multi-tick extensions (the
         loop's hold-last stale policy repeats the last command during server
         stalls, stretching a 10 ms probe), and -- with --capture -- how many
         designed pulses were LOST in delivery (stale-dropped/overwritten
         replies never sent)
  Scle   onset match and word->channel transport delay
  sSig   bipolar mapping: word k must drive electrodes (2k-1, 2k) with exact
         inversion (the 2026-08-12 finding); verified two ways (pair inversion
         + per-word focality)
  Plse   actual stim carrier rate vs base/100 = 244.141 Hz and the intended
         base/240 = 101.725 Hz, and acquisition samples per stim period
         (integer = artifact cancels inside the feature window)

Needs the PythonIntanAnalysis venv (tdt, numpy). Remember TDT blocks nest one
level: pass the INNER directory.
"""

import argparse
import csv
import sys

import numpy as np

FS_ACQ = 610.3515625


def pulse_events(x, thresh=1e-9):
    """(n_events, n_single, run_lengths>1, first_multi_indices) of a sample train."""
    nz = np.flatnonzero(x > thresh)
    if not len(nz):
        return 0, 0, [], []
    brk = np.flatnonzero(np.diff(nz) > 1)
    starts = np.r_[nz[0], nz[brk + 1]]
    ends = np.r_[nz[brk], nz[-1]]
    lens = ends - starts + 1
    multi = lens[lens > 1].tolist()
    return len(starts), int((lens == 1).sum()), multi, starts[lens > 1].tolist()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", required=True)
    ap.add_argument("--capture", default=None,
                    help="server capture CSV for designed-vs-delivered accounting")
    ap.add_argument("--amps", type=float, nargs="+", default=[5, 10, 18, 25])
    args = ap.parse_args()

    import tdt
    d = tdt.read_block(args.block, evtype=["streams", "scalars"])
    issues = []

    def note(sev, msg):
        issues.append((sev, msg))
        print("  %s: %s" % (sev, msg))

    U, ts = d.scalars.UDP1.data, d.scalars.UDP1.ts
    n_words = U.shape[0]
    print("UDP1: %d words x %d samples, span %.1f..%.1f s, interval median %.4f ms"
          % (n_words, U.shape[1], ts[0], ts[-1], 1e3 * np.median(np.diff(ts))))

    designed = None
    if args.capture:
        rows = list(csv.reader(open(args.capture)))
        h = rows[0]
        cap = np.array([[float(v) for v in r] for r in rows[1:]])
        Ud = cap[:, [i for i, c in enumerate(h) if c.startswith("u")]]
        designed = [int(np.sum((Ud[1:, w] > 0) & (Ud[:-1, w] <= 0)) + (Ud[0, w] > 0))
                    for w in range(min(n_words, Ud.shape[1]))]

    print("\nper-word wire audit:")
    expected = set(np.round(args.amps, 6))
    tot_d = tot_w = tot_multi = 0
    for w in range(n_words):
        n_ev, n_single, multi, _ = pulse_events(U[w])
        vals = set(np.round(U[w][U[w] > 1e-9], 6))
        stray = sorted(vals - expected)
        if stray:
            note("FAIL", "word %d carries unexpected amplitude(s) %s" % (w + 1, stray))
        loss = ""
        if designed and w < len(designed):
            tot_d += designed[w]
            loss = "  designed %3d -> lost %d" % (designed[w], designed[w] - n_ev)
        tot_w += n_ev
        tot_multi += len(multi)
        print("  word %d: %3d events (%3d single, %d multi %s)%s"
              % (w + 1, n_ev, n_single, len(multi), multi, loss))
    if tot_multi:
        note("warn", "%d multi-tick pulse(s) on the wire -- hold-last stretched a "
             "probe during a server stall; excluded automatically by "
             "fit_impulse_model's isolation filter, but the extra charge WAS "
             "delivered" % tot_multi)
    if designed and tot_d > tot_w:
        pct = 100.0 * (tot_d - tot_w) / max(1, tot_d)
        sev = "warn" if pct < 8 else "FAIL"
        note(sev, "%d/%d designed pulses (%.1f%%) never reached the wire "
             "(stale-dropped/overwritten replies)" % (tot_d - tot_w, tot_d, pct))
    elif designed:
        print("  wire == design: every designed pulse reached the RZ2")

    # ---- Scle + carrier: pulses actually DELIVERED per commanded probe ------
    # The scale value latches on the free-running stim carrier, and the command
    # clock (~99.2 Hz effective) is NOT synchronous with it, so the two phases
    # slide through each other (beat ~0.4 s at 101.7 Hz carrier). A single-tick
    # probe window therefore gates 1 carrier pulse usually, 2 when the phases
    # align, and 0 when the window falls between latches -- a silent physical
    # miss even though UDP1 and Scle software delivery are perfect. Count it.
    S, fsS = d.streams.Scle.data, d.streams.Scle.fs
    P, fsP = d.streams.Plse.data, d.streams.Plse.fs
    pk = np.max(np.abs(P))
    carrier = (np.flatnonzero((P[1:] > 0.5 * pk) & (P[:-1] <= 0.5 * pk)) + 1) / fsP \
        if pk > 0 else np.array([])
    print("\nper-probe delivered-pulse audit (carrier ticks inside each probe's Scle-high span):")
    n_miss = n_single = n_double = n_probe = 0
    for w in range(min(n_words, S.shape[0])):
        onU = np.flatnonzero((U[w][1:] > 1e-9) & (U[w][:-1] <= 1e-9)) + 1
        hi = S[w] > 1e-9
        counts = []
        for t in ts[onU]:
            i0 = int(max(0.0, t - 0.001) * fsS)
            i1 = min(len(hi), int((t + 0.022) * fsS))
            seg = hi[i0:i1]
            if not seg.any():
                counts.append(0)
                continue
            t0 = (i0 + np.argmax(seg)) / fsS
            t1 = (i0 + len(seg) - np.argmax(seg[::-1])) / fsS
            counts.append(int(np.sum((carrier >= t0) & (carrier < t1))))
        c = np.bincount(np.array(counts) if counts else np.zeros(0, int), minlength=3)
        n_probe += len(counts)
        n_miss += int(c[0]); n_single += int(c[1]); n_double += int(c[2:].sum())
        print("  word %d: %3d probes -> missed %2d, single %3d, double+ %2d"
              % (w + 1, len(counts), c[0], c[1], c[2:].sum()))
    if n_probe:
        pm, pd = 100.0 * n_miss / n_probe, 100.0 * n_double / n_probe
        print("  TOTAL %d probes: missed %d (%.1f%%), single %d (%.1f%%), double+ %d (%.1f%%)"
              % (n_probe, n_miss, pm, n_single, 100.0 * n_single / n_probe, n_double, pd))
        if n_miss or n_double:
            note("FAIL" if pm > 5 else "warn",
                 "carrier-latch beat: %.1f%% probes delivered 0 pulses, %.1f%% "
                 "delivered 2 -- expected while the command clock free-runs "
                 "against the stim carrier; excluded trials are measurable, "
                 "kernel amplitudes carry ~this much spread" % (pm, pd))

    # ---- sSig bipolar mapping ----------------------------------------------
    G, fsG = d.streams.sSig.data, d.streams.sSig.fs
    print("\nsSig bipolar pairs (inversion + word attribution):")
    ok_map = True
    absG = np.abs(G)
    for w in range(min(n_words, G.shape[0] // 2)):
        a, b = G[2 * w], G[2 * w + 1]
        inv_ok = a.std() > 1e-12 and np.max(np.abs(a + b)) < 1e-6 * max(1.0, np.max(np.abs(a)))
        onU = np.flatnonzero((U[w][1:] > 1e-9) & (U[w][:-1] <= 1e-9)) + 1
        mask = np.zeros(G.shape[1], bool)
        for t in ts[onU]:
            i0 = int(t * fsG)
            mask[i0:i0 + int(0.012 * fsG)] = True
        ratio = absG[:, mask].mean(axis=1) / (absG[:, ~mask].mean(axis=1) + 1e-12)
        top2 = set(np.argsort(ratio)[::-1][:2].tolist())
        attr_ok = top2 == {2 * w, 2 * w + 1}
        ok_map = ok_map and inv_ok and attr_ok
        print("  word %d -> pair %d (ch%d,ch%d): inversion %s, attribution %s "
              "(focality %.0fx)"
              % (w + 1, w + 1, 2 * w + 1, 2 * w + 2,
                 "EXACT" if inv_ok else "BROKEN",
                 "OK" if attr_ok else "WRONG CHANNELS %s" % sorted(c + 1 for c in top2),
                 min(ratio[2 * w], ratio[2 * w + 1])))
    if not ok_map:
        note("FAIL", "bipolar mapping word k -> electrodes (2k-1, 2k) does NOT hold")
    else:
        print("  PAIR MAPPING CONFIRMED: word k -> electrodes (2k-1, 2k), exact inversion")

    # ---- Plse carrier rate --------------------------------------------------
    P, fsP = d.streams.Plse.data, d.streams.Plse.fs
    thr = 0.5 * np.max(np.abs(P)) if np.max(np.abs(P)) > 0 else 0
    rise = np.flatnonzero((P[1:] > thr) & (P[:-1] <= thr)) + 1
    iv = np.diff(rise) / fsP
    iv = iv[(iv > 1e-4) & (iv < 0.1)]
    if len(iv):
        rate = 1.0 / np.median(iv)
        spp = FS_ACQ * np.median(iv)
        print("\nPlse carrier: %.3f Hz (%d pulses; base/100 = 244.141, base/240 = 101.725)"
              % (rate, len(rise)))
        print("  acquisition samples per stim period: %.3f" % spp)
        if abs(spp - round(spp)) > 0.05:
            note("warn", "samples-per-stim-period %.2f is NOT an integer -- stim "
                 "artifact does not cancel in a 6-sample feature window; use "
                 "-FeatureWindow 30 (= %.1f periods) or change the circuit divisor"
                 % (spp, 30 / spp))
    else:
        note("warn", "no Plse pulses found -- stimulator off or safety button?")

    hard = sum(1 for s, _ in issues if s == "FAIL")
    print("\nVERDICT: %s (%d hard failure(s), %d warning(s))"
          % ("DELIVERY BROKEN" if hard else "DELIVERY VERIFIED",
             hard, len(issues) - hard))
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
