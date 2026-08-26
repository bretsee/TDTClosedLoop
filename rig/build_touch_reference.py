#!/usr/bin/env python
"""build_touch_reference.py -- turn a natural-touch template into a 100 Hz
feature-scale reference trajectory the MPC can track.

    python rig/build_touch_reference.py ^
        --npz <path to BiomimeticInversion touch npz> ^
        --channel 5 --baseline 0.0015 --repeats 10 --out ref_touch.csv

The touch npz (NNController/outputs/BiomimeticInversion/touch/<study>/<block>.npz)
holds `template`: [16 ch x 122 samples] of baseline-corrected, touch-aligned
cortical response in MICROVOLTS at 610.352 Hz (~200 ms).

The controller does NOT see microvolt waveforms -- it sees the C++ feature:
mean|v| over the newest 6 acquisition samples, in VOLTS, once per 10 ms tick.
So the honest biomimetic target is the template pushed through THAT SAME
transformation: |template| -> 6-sample bins -> mean -> volts. That is what this
script emits: `tick,r1[,r2,...]` rows, with a measured baseline added
(features are positive with a noise floor; a reference below the floor is
unreachable and just pins the command at a bound).

TICK-RATE NOTE: each row is 6 acquisition samples = 9.8304 ms of template =
exactly ONE frame-locked control tick (--tick-frames 6). Played frame-locked,
the template timing is EXACT. Played at the wall-clock 100 Hz tick, the
template stretches by 1.7% (harmless, but frame-locked is the more faithful
playback once mpc Ts alignment is in place).

TWO NUMBERS MUST COME FROM THE PREP ON THE DAY (there are no valid defaults):
  --baseline  the resting feature value, in volts, measured with stim OFF
              (read feature0/input0 from a short quiet run, or 3_fit's range line)
  --scale     amplitude multiplier on the template. Start at 1.0. If the fitted
              plant says the target modulation exceeds what uMax can drive,
              scale down rather than letting the MPC saturate.

Output channel count = number of --channel entries, in the order given. That
order must match mpc_test's feature_map / the fitted model outputs.
"""

import argparse
import json
import sys

import numpy as np

CONTROL_RATE_HZ = 100.0
# TEMPLATE samples per control tick: the touch npz is sampled at 610.352 Hz and
# one 9.8304 ms tick spans 6 of ITS samples. This is a property of the stored
# template, NOT the loop's --feature-window-samples: do NOT bump it to 12 for
# the 2x --stream-fs option -- the tick rate is unchanged, so the reference CSV
# is identical at either stream rate (doubling this would play the template 2x
# slow). (Renamed from FEATURE_WINDOW_SAMPLES, 2026-08-25.)
TEMPLATE_SAMPLES_PER_TICK = 6


def template_to_feature_ticks(template_uv, window=TEMPLATE_SAMPLES_PER_TICK,
                              signed=False):
    """uV -> consecutive `window`-sample bins -> mean -> volts. [n_ticks]

    signed=False: rectify first (matches the loop's default mean(|x|) feature).
    signed=True:  plain mean (matches --feature-signed, the Choi-style signed
    LFP feature). The reference MUST live in the same space as the deployed
    feature -- pass --signed if and only if the loop runs --feature-signed.
    """
    v = template_uv.astype(float) * 1e-6
    if not signed:
        v = np.abs(v)
    n_bins = len(v) // window
    if n_bins == 0:
        raise SystemExit("FAIL: template shorter than one feature window")
    return v[: n_bins * window].reshape(n_bins, window).mean(axis=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", required=True, help="touch template npz")
    ap.add_argument("--channel", type=int, action="append", required=True,
                    help="cortical channel (1-based) to build a reference for; "
                         "repeat for multiple outputs, order = model output order")
    ap.add_argument("--baseline", type=float, required=True,
                    help="resting feature value in VOLTS measured on the day (e.g. 0.0015)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="template amplitude multiplier (default 1.0)")
    ap.add_argument("--repeats", type=int, default=10,
                    help="how many touch events to string together (default 10)")
    ap.add_argument("--gap-secs", type=float, default=2.0,
                    help="baseline seconds between events (default 2)")
    ap.add_argument("--lead-secs", type=float, default=2.0,
                    help="baseline seconds before the first event (default 2)")
    ap.add_argument("--signed", action="store_true",
                    help="build the reference in SIGNED feature space (loop "
                         "running --feature-signed). Default is rectified.")
    ap.add_argument("--out", default="ref_touch.csv", help="output reference CSV")
    args = ap.parse_args()

    if not args.signed and args.baseline < 0:
        raise SystemExit("FAIL: --baseline must be >= 0 (it is a mean-abs feature)")

    d = np.load(args.npz, allow_pickle=True)
    template = d["template"]          # [n_ch x n_samples], microvolts
    n_ch = template.shape[0]
    for ch in args.channel:
        if not (1 <= ch <= n_ch):
            raise SystemExit("FAIL: --channel %d outside 1..%d" % (ch, n_ch))

    # Per-requested-channel event trace in feature units (volts).
    events = []
    for ch in args.channel:
        events.append(args.scale * template_to_feature_ticks(template[ch - 1],
                                                             signed=args.signed))
    events = np.stack(events, axis=1)          # [event_ticks x p]
    event_ticks = events.shape[0]

    lead = int(round(args.lead_secs * CONTROL_RATE_HZ))
    gap = int(round(args.gap_secs * CONTROL_RATE_HZ))
    p = events.shape[1]

    rows = [np.full((lead, p), 0.0)]
    for _ in range(max(1, args.repeats)):
        rows.append(events)
        rows.append(np.full((gap, p), 0.0))
    traj = np.vstack(rows) + args.baseline     # baseline-referenced, positive

    with open(args.out, "w", newline="") as f:
        f.write("tick," + ",".join("r%d" % (i + 1) for i in range(p)) + "\n")
        for i, row in enumerate(traj, start=1):
            f.write("%d," % i + ",".join("%.9g" % v for v in row) + "\n")

    meta = {
        "source_npz": args.npz,
        "channels_1based": args.channel,
        "baseline_volts": args.baseline,
        "scale": args.scale,
        "repeats": args.repeats,
        "gap_secs": args.gap_secs,
        "lead_secs": args.lead_secs,
        "event_ticks": int(event_ticks),
        "total_ticks": int(traj.shape[0]),
        "total_secs": traj.shape[0] / CONTROL_RATE_HZ,
        "event_peak_delta_volts": [float(np.max(events[:, j])) for j in range(p)],
        # legacy key name kept for downstream compat; the value is TEMPLATE
        # samples per tick (a property of the 610 Hz npz), not the loop flag
        "feature_window_samples": TEMPLATE_SAMPLES_PER_TICK,
        "template_samples_per_tick": TEMPLATE_SAMPLES_PER_TICK,
        # each row = one 101.7253 Hz frame-locked tick (= 6 template samples),
        # whatever --tick-frames/--stream-fs the loop runs;
        # at the 100 Hz wall-clock tick the template plays 1.7% slow
        "tick_native_hz": 101.7253,
    }
    meta_path = args.out.rsplit(".", 1)[0] + "_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print("Reference: %d ticks (%.1f s), %d output(s), %d events of %d ticks (%.0f ms each)"
          % (traj.shape[0], meta["total_secs"], p, args.repeats, event_ticks,
             event_ticks * 10.0))
    print("Baseline %.6g V; event peak delta %s V (%.1fx..%.1fx of baseline)"
          % (args.baseline,
             ["%.3g" % v for v in meta["event_peak_delta_volts"]],
             min(meta["event_peak_delta_volts"]) / max(args.baseline, 1e-12),
             max(meta["event_peak_delta_volts"]) / max(args.baseline, 1e-12)))
    if args.baseline > 0 and max(meta["event_peak_delta_volts"]) < 0.1 * args.baseline:
        print("WARNING: event modulation is <10%% of baseline -- likely inside the")
        print("         feature noise floor. Consider --scale > 1, or accept that")
        print("         tracking will be judged on averages over repeats.")
    print("Wrote %s and %s" % (args.out, meta_path))
    print("Deploy: .\\rig\\4_mpc_server.ps1 -Reference %s -Ticks %d"
          % (args.out, traj.shape[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
