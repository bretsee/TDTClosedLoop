r"""Build interleaved-event arm runs: p-channel references + Choi tapes + schedules.

    python rig\build_interleaved_run.py --templates-dir <NNC>\outputs\...\touch\Acute_<day> ^
        --sites D1 D2 D3 P2 LP SHAM --channels 8 6 --baseline 1.2e-4 ^
        --model plant_rnd1.lti --runs 3 --events 100 --umax 30 --out-dir day_<day>

Protocol (2026-08-31, user design): every run interleaves N events drawn from a
balanced shuffled deck of sites (SHAM = catch trials), 220-tick period (20-tick
touch template + ~2 s gap). The SAME seeded schedule serves the MPC reference
AND the Choi stimulus tape, so the arms are paired per event.

MIMO (2026-09-01): --channels takes one control channel per model output; the
references carry r1..rp and the Choi synthesis reads p from the model.

Choi lessons baked in as defaults (2026-08-31): gate DISABLED (an operating-
point model embeds the recruitment knee; the gated problem has an all-attenuated
local minimum), mu tiny (volt-scale objectives), offsets read from the .lti,
period synthesis + tiling (a dense 22,200-tick Gram matrix needs ~8 GB).

Outputs per run r: ref_mix_r<r>.csv (tick,r1..rp), design_choi_mix_r<r>.csv
(tick,u1..u8 with only the model's pairs active via --pairs), schedule_mix_
r<r>.json (per-event site + onset_tick; feed to plot_trial_responses --mode arm
and post-hoc scoring).
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("FAIL running %s:\n%s\n%s" % (" ".join(map(str, cmd)), r.stdout[-800:], r.stderr[-800:]))
    return r.stdout


def load_cols(path, prefix):
    rows = list(csv.reader(open(path)))
    hdr = rows[0]
    idx = [i for i, h in enumerate(hdr) if h.strip().lower().startswith(prefix)]
    return np.array([[float(r[i]) for i in idx] for r in rows[1:]])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates-dir", required=True)
    ap.add_argument("--sites", nargs="+", required=True,
                    help="site labels incl. SHAM; template npz matched via touch_targets_summary.json")
    ap.add_argument("--channels", type=int, nargs="+", required=True,
                    help="1-based control channel per model output (order = model output order)")
    ap.add_argument("--baseline", type=float, required=True)
    ap.add_argument("--model", required=True, help=".lti plant (p must equal len(--channels))")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--events", type=int, default=100)
    ap.add_argument("--period-ticks", type=int, default=220)
    ap.add_argument("--lead-ticks", type=int, default=172)
    ap.add_argument("--total-ticks", type=int, default=22200)
    ap.add_argument("--umax", type=float, default=30.0)
    ap.add_argument("--mu", type=float, default=1e-13)
    ap.add_argument("--pairs", type=int, nargs="+", default=None,
                    help="wire slot per model input (default: read m from the model, slots 1..m)")
    ap.add_argument("--seed", type=int, default=None, help="base seed (default from today)")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    tdir = Path(args.templates_dir)
    summary = json.loads((tdir / "touch_targets_summary.json").read_text())
    py = sys.executable

    # model dims + pairs mapping
    toks = (REPO / args.model).read_text().split() if not Path(args.model).is_absolute() \
        else Path(args.model).read_text().split()
    m = int(toks[toks.index("m") + 1]); p = int(toks[toks.index("p") + 1])
    if p != len(args.channels):
        sys.exit("FAIL: model p=%d but %d --channels given" % (p, len(args.channels)))
    pairs = args.pairs or list(range(1, m + 1))
    if len(pairs) != m:
        sys.exit("FAIL: model m=%d but %d --pairs given" % (m, len(pairs)))
    seed0 = args.seed if args.seed is not None else 20260901

    # ---- per-site single-event reference (validated converter, p columns) ----
    site_block = {}
    for entry in (summary if isinstance(summary, list) else summary.get("blocks", summary.get("entries", []))):
        if isinstance(entry, dict) and entry.get("site"):
            site_block[entry["site"]] = entry.get("block")
    period_ref, period_u = {}, {}
    for site in args.sites:
        blk = site_block.get(site)
        if not blk:
            sys.exit("FAIL: site %s not in touch_targets_summary.json (have %s)"
                     % (site, sorted(site_block)))
        npz = tdir / (blk + ".npz")
        one = out / ("_event_%s.csv" % site)
        cmd = [py, str(REPO / "rig" / "build_touch_reference.py"), "--npz", str(npz),
               "--baseline", repr(args.baseline), "--repeats", "1",
               "--gap-secs", "0", "--lead-secs", "0", "--out", str(one)]
        for c in args.channels:
            cmd += ["--channel", str(c)]
        run(cmd)
        ev = load_cols(one, "r")                      # [Tev x p]
        per = np.full((args.period_ticks, p), args.baseline)
        pre = 30
        n = min(len(ev), args.period_ticks - pre)
        per[pre:pre + n] = ev[:n]
        period_ref[site] = per

        # Choi period synthesis on the p-col period reference
        pref = out / ("_period_ref_%s.csv" % site)
        with open(pref, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tick"] + ["r%d" % (i + 1) for i in range(p)])
            for t in range(args.period_ticks):
                w.writerow([t + 1] + [repr(float(v)) for v in per[t]])
        pu = out / ("_period_u_%s.csv" % site)
        run([py, str(REPO / "rig" / "choi_synthesis.py"), "--model", args.model,
             "--reference", str(pref), "--umax", repr(args.umax),
             "--gate-threshold", "0", "--mu", repr(args.mu), "--out", str(pu)])
        U = load_cols(pu, "u")                        # [period x m]
        if U.shape != (args.period_ticks, m):
            sys.exit("FAIL: choi period for %s is %s, expected (%d,%d)"
                     % (site, U.shape, args.period_ticks, m))
        period_u[site] = U
        print("site %s: ref peak %.3g V, choi u in [%.1f %.1f]"
              % (site, per.max(), U.min(), U.max()))

    # ---- runs ---------------------------------------------------------------
    for r in range(1, args.runs + 1):
        rng = np.random.default_rng(seed0 * 10 + r)
        deck = []
        while len(deck) < args.events:
            block = list(args.sites); rng.shuffle(block); deck.extend(block)
        deck = deck[:args.events]

        ref = np.full((args.total_ticks, p), args.baseline)
        tape = np.zeros((args.total_ticks, 8))
        hold = np.mean([period_u[s][-1] for s in args.sites], axis=0)
        for mi, slot in enumerate(pairs):
            tape[:, slot - 1] = hold[mi]
        sched = []
        for k, site in enumerate(deck):
            a = args.lead_ticks + k * args.period_ticks
            b = min(a + args.period_ticks, args.total_ticks)
            ref[a:b] = period_ref[site][:b - a]
            for mi, slot in enumerate(pairs):
                tape[a:b, slot - 1] = period_u[site][:b - a, mi]
            sched.append({"event": k + 1, "site": site, "onset_tick": a + 30 + 1})

        with open(out / ("ref_mix_r%d.csv" % r), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tick"] + ["r%d" % (i + 1) for i in range(p)])
            for t in range(args.total_ticks):
                w.writerow([t + 1] + [repr(float(v)) for v in ref[t]])
        with open(out / ("design_choi_mix_r%d.csv" % r), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tick"] + ["u%d" % (i + 1) for i in range(8)])
            for t in range(args.total_ticks):
                w.writerow([t + 1] + [repr(float(v)) for v in tape[t]])
        counts = {s: deck.count(s) for s in args.sites}
        json.dump({"run": r, "seed": seed0 * 10 + r, "sites": args.sites,
                   "channels": args.channels, "pairs": pairs, "counts": counts,
                   "lead_ticks": args.lead_ticks, "period_ticks": args.period_ticks,
                   "events": sched},
                  open(out / ("schedule_mix_r%d.json" % r), "w"), indent=1)
        print("run r%d: counts %s  tape u range [%.1f %.1f] on pairs %s"
              % (r, counts, tape.min(), tape.max(), pairs))
    print("wrote %d run(s) to %s" % (args.runs, out))


if __name__ == "__main__":
    main()
