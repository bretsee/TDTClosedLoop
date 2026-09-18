#!/usr/bin/env python
r"""design_burst_probe.py -- burst / duty-cycled stimulation designs (acute #3 lever).

    python rig\design_burst_probe.py --kind burst-ladder --out design_runburst1.csv
    python rig\design_burst_probe.py --kind duty-prbs   --duty 0.3 --burst-ticks 3 --out design_runduty1.csv
    python rig\design_burst_probe.py --kind gap-scan    --out design_rungap1.csv
    python rig\design_burst_probe.py --validate design_runburst1.csv

WHY (acute #2, 2026-09-10): single pulses recruit cortex from all 8 pairs with
distinct-enough footprints (pulse eff. rank 4-5), but continuous 100 Hz
amplitude-modulated drive collapses the actuator to ONE direction (tonic eff.
rank 1 usable). Thalamocortical synapses depress within tens of ms of sustained
drive and every pair then shares the same saturated mode. The literature fix
(Swadlow & Gusev 2001; Hughes/Flesher/Gaunt 2022; Millard 2013) is
INTERMITTENT drive: short bursts with >= 100 ms recovery, and a plant fitted on
sparse-burst data. These designs are replayed by cpp_controller --mode openloop
--play <csv> (tick,u1..u8 in uA; one row per 100 Hz tick, so a "burst of K
ticks" = K carrier pulses at 101.7 Hz).

kinds
  burst-ladder  per pair, bursts of B ticks at each of --amps, --n-per-cond
                repeats, one pair at a time, random order, gap >= --gap-ticks
                (default 30 = 300 ms recovery) plus jitter. -> per-pair burst
                response + burst-length dependence (B in --burst-ticks list).
                This is the ID data set for a BURST plant (response per burst).
  duty-prbs     all --pairs simultaneously, each pair an independent PRBS of
                bursts: within its own slots a pair fires a B-tick burst at a
                random amplitude in [--umin, --umax] with probability --duty,
                else stays at 0; slots are B + gap ticks long and pairs are
                phase-staggered so bursts of different pairs never overlap.
                -> multi-input ID at a chosen duty (charge = duty x tonic).
  gap-scan      one pair (--pairs first), bursts of B ticks at --umax with the
                recovery gap swept over --gap-list (ticks), random order,
                --n-per-cond each. -> where the depression recovers (the number
                that sets acute-#3's operating duty cycle).

--validate <csv> audits any design: per-pair burst count, burst-length
histogram, min inter-burst gap per pair, cross-pair overlaps (must be 0 for
burst-ladder/gap-scan), duty cycle, total charge (uA-ticks), duration.
Writes <out>_meta.json next to the CSV. Exit 1 on hard failures.
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np


def write_design(path, U):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick"] + ["u%d" % k for k in range(1, U.shape[1] + 1)])
        for i, row in enumerate(U, start=1):
            w.writerow([i] + ["%g" % v for v in row])


def read_design(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    hdr = rows[0]
    ui = [i for i, h in enumerate(hdr) if h.startswith("u")]
    return np.array([[float(r[i]) for i in ui] for r in rows[1:]])


def burst_ladder(a):
    rng = np.random.default_rng(a.seed)
    conds = [(p, amp, B) for p in a.pairs for amp in a.amps for B in a.burst_ticks]
    deck = conds * a.n_per_cond
    rng.shuffle(deck)
    rows = []
    t = a.lead_ticks
    events = []
    for (p, amp, B) in deck:
        gap = a.gap_ticks + int(rng.geometric(1.0 / max(1, a.jitter_mean_ticks))) - 1
        t_end = t + B + gap
        rows.append((t, p, amp, B))
        events.append(dict(tick=int(t + 1), pair=int(p), amp=float(amp), burst_ticks=int(B)))
        t = t_end
    n = t + a.lead_ticks
    U = np.zeros((n, 8))
    for (t0, p, amp, B) in rows:
        U[t0:t0 + B, p - 1] = amp
    meta = dict(kind="burst-ladder", pairs=a.pairs, amps=a.amps, burst_ticks=a.burst_ticks,
                n_per_cond=a.n_per_cond, gap_ticks=a.gap_ticks, jitter_mean_ticks=a.jitter_mean_ticks,
                n_conditions=len(conds), n_events=len(deck), events=events)
    return U, meta


def duty_prbs(a):
    rng = np.random.default_rng(a.seed)
    B = a.burst_ticks[0]
    m = len(a.pairs)
    slot = B + a.gap_ticks                       # one pair's private slot length
    frame = slot                                 # pairs staggered by B ticks inside the slot
    if m * B > slot:
        raise SystemExit("duty-prbs: %d pairs x %d burst ticks exceed slot %d; raise --gap-ticks" % (m, B, slot))
    n = a.lead_ticks + a.n_slots * frame + a.lead_ticks
    U = np.zeros((n, 8))
    events = []
    for s in range(a.n_slots):
        base = a.lead_ticks + s * frame
        for j, p in enumerate(a.pairs):
            if rng.random() < a.duty:
                amp = float(rng.uniform(a.umin, a.umax)) if a.umin < a.umax else a.umax
                t0 = base + j * B
                U[t0:t0 + B, p - 1] = amp
                events.append(dict(tick=int(t0 + 1), pair=int(p), amp=round(amp, 2), burst_ticks=B))
    meta = dict(kind="duty-prbs", pairs=a.pairs, burst_ticks=B, gap_ticks=a.gap_ticks, duty=a.duty,
                umin=a.umin, umax=a.umax, n_slots=a.n_slots, n_events=len(events), events=events)
    return U, meta


def gap_scan(a):
    rng = np.random.default_rng(a.seed)
    p = a.pairs[0]
    B = a.burst_ticks[0]
    deck = list(a.gap_list) * a.n_per_cond
    rng.shuffle(deck)
    rows, events = [], []
    t = a.lead_ticks
    for g in deck:
        # a PAIR of bursts: conditioning burst, gap g, test burst; then long recovery
        rows.append((t, p, a.umax, B)); events.append(dict(tick=int(t + 1), pair=p, amp=a.umax, burst_ticks=B, role="cond", gap=int(g)))
        t2 = t + B + g
        rows.append((t2, p, a.umax, B)); events.append(dict(tick=int(t2 + 1), pair=p, amp=a.umax, burst_ticks=B, role="test", gap=int(g)))
        t = t2 + B + a.gap_ticks + int(rng.geometric(1.0 / max(1, a.jitter_mean_ticks))) - 1
    n = t + a.lead_ticks
    U = np.zeros((n, 8))
    for (t0, pp, amp, BB) in rows:
        U[t0:t0 + BB, pp - 1] = amp
    meta = dict(kind="gap-scan", pair=p, burst_ticks=B, amp=a.umax, gap_list=list(a.gap_list),
                n_per_cond=a.n_per_cond, recovery_gap_ticks=a.gap_ticks, n_events=len(events), events=events)
    return U, meta


def validate(path, U=None, meta=None):
    if U is None:
        U = read_design(path)
    n, m = U.shape
    on = U > 1e-9
    print("design %s: %d ticks (%.1f s @100 Hz), %d columns, total charge %.0f uA-ticks, "
          "duty (any pair on) %.3f" % (os.path.basename(path), n, n / 100.0, m, U.sum(), on.any(axis=1).mean()))
    hard = []
    overl = int((on.sum(axis=1) > 1).sum())
    print("  ticks with >1 pair active: %d" % overl)
    for k in range(m):
        col = on[:, k]
        if not col.any():
            continue
        rise = np.flatnonzero(~col[:-1] & col[1:]) + 1
        fall = np.flatnonzero(col[:-1] & ~col[1:]) + 1
        if col[0]:
            rise = np.r_[0, rise]
        if col[-1]:
            fall = np.r_[fall, n]
        lens = fall - rise
        gaps = rise[1:] - fall[:-1]
        amps = sorted(set(np.round(U[rise, k], 2).tolist()))
        print("  u%d: %4d bursts, len ticks %s, min gap %s ticks, amps %s, charge %.0f"
              % (k + 1, len(rise), dict(zip(*np.unique(lens, return_counts=True))) if len(lens) else {},
                 int(gaps.min()) if len(gaps) else "-", amps[:8] if len(amps) <= 8 else "%d distinct" % len(amps),
                 U[:, k].sum()))
        if len(gaps) and gaps.min() < 1:
            hard.append("u%d bursts touch" % (k + 1))
    if meta and meta.get("kind") in ("burst-ladder", "gap-scan") and overl:
        hard.append("cross-pair overlap in a single-pair design")
    if hard:
        print("  HARD FAIL: " + "; ".join(hard))
        return 1
    print("  DESIGN OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["burst-ladder", "duty-prbs", "gap-scan"])
    ap.add_argument("--validate", default=None, help="audit an existing design CSV and exit")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pairs", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6, 7, 8])
    ap.add_argument("--amps", type=float, nargs="+", default=[9, 13, 18, 25])
    ap.add_argument("--burst-ticks", type=int, nargs="+", default=[1, 3, 10],
                    help="burst lengths in ticks (=carrier pulses); duty-prbs/gap-scan use the first")
    ap.add_argument("--n-per-cond", type=int, default=20)
    ap.add_argument("--gap-ticks", type=int, default=30, help="minimum recovery gap after a burst (ticks)")
    ap.add_argument("--jitter-mean-ticks", type=int, default=6)
    ap.add_argument("--lead-ticks", type=int, default=200)
    ap.add_argument("--duty", type=float, default=0.3)
    ap.add_argument("--umin", type=float, default=10.0)
    ap.add_argument("--umax", type=float, default=25.0)
    ap.add_argument("--n-slots", type=int, default=1200, help="duty-prbs: number of slots (frames)")
    ap.add_argument("--gap-list", type=int, nargs="+", default=[2, 5, 10, 20, 30, 50, 100])
    ap.add_argument("--seed", type=int, default=20260918)
    a = ap.parse_args()

    if a.validate:
        meta_p = os.path.splitext(a.validate)[0] + "_meta.json"
        meta = json.load(open(meta_p)) if os.path.isfile(meta_p) else None
        return validate(a.validate, meta=meta)
    if not a.kind or not a.out:
        ap.error("--kind and --out are required unless --validate is used")
    U, meta = {"burst-ladder": burst_ladder, "duty-prbs": duty_prbs, "gap-scan": gap_scan}[a.kind](a)
    U = np.clip(U, 0, a.umax if a.kind != "burst-ladder" else max(a.amps))
    write_design(a.out, U)
    meta.update(generated=time.strftime("%Y-%m-%d %H:%M:%S"), generator="design_burst_probe.py",
                nTicks=int(U.shape[0]), seed=a.seed, total_charge_uAticks=float(U.sum()))
    events = meta.pop("events")
    meta_p = os.path.splitext(a.out)[0] + "_meta.json"
    with open(meta_p, "w") as f:
        json.dump(dict(meta, events=events), f)
    print("wrote %s (%d ticks = %.1f min) + %s" % (a.out, U.shape[0], U.shape[0] / 6000.0, os.path.basename(meta_p)))
    return validate(a.out, U, meta)


if __name__ == "__main__":
    sys.exit(main())
