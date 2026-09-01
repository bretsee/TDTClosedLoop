"""Build interleaved-event reference tapes + Choi tapes + schedules.
Events drawn from a balanced shuffled deck of sites; SAME schedule serves the
MPC reference and the Choi stimulus tape so the arms are paired per event."""
import csv
import json
from pathlib import Path

import numpy as np

DAY = Path(r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\day_2026-08-31")
SCRATCH = Path(__file__).parent
SITES = ["D1", "D2", "D3", "P2", "LP", "SHAM"]
RUNS = 3
EVENTS = 100
LEAD = 172
PERIOD = 220
N_TICKS = 22200
BASE = 1.2e-4
WORD_MAP = {0: 0, 1: 3}  # model input -> design column (u1, u4)

def load_col(p, prefix):
    rows = list(csv.reader(open(p)))
    hdr = rows[0]
    idx = [i for i, h in enumerate(hdr) if h.strip().lower().startswith(prefix)]
    return np.array([[float(r[i]) for i in idx] for r in rows[1:]])

refs = {s: load_col(SCRATCH / f"period_ref_{s}.csv", "r")[:, 0] for s in SITES}
us = {s: load_col(SCRATCH / f"period_u_{s}.csv", "u") for s in SITES}
for s in SITES:
    assert len(refs[s]) == PERIOD and us[s].shape == (PERIOD, 2), s

for r in range(1, RUNS + 1):
    rng = np.random.default_rng(20260831 * 10 + r)
    deck = []
    while len(deck) < EVENTS:
        block = list(SITES)
        rng.shuffle(block)
        deck.extend(block)
    deck = deck[:EVENTS]

    ref = np.full(N_TICKS, BASE)
    tape = np.zeros((N_TICKS, 8))
    for m, col in WORD_MAP.items():
        tape[:, col] = np.mean([us[s][-1, m] for s in SITES])  # steady hold
    sched = []
    for k, site in enumerate(deck):
        a = LEAD + k * PERIOD
        b = a + PERIOD
        ref[a:b] = refs[site]
        for m, col in WORD_MAP.items():
            tape[a:b, col] = us[site][:, m]
        sched.append({"event": k + 1, "site": site, "onset_tick": a + 30 + 1})

    with open(DAY / f"ref_mix_r{r}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "r1"])
        for t in range(N_TICKS):
            w.writerow([t + 1, repr(float(ref[t]))])
    with open(DAY / f"design_choi_mix_r{r}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick"] + [f"u{i+1}" for i in range(8)])
        for t in range(N_TICKS):
            w.writerow([t + 1] + [repr(float(v)) for v in tape[t]])
    counts = {s: deck.count(s) for s in SITES}
    with open(DAY / f"schedule_mix_r{r}.json", "w") as f:
        json.dump({"run": r, "seed": 20260831 * 10 + r, "sites": SITES,
                   "counts": counts, "lead_ticks": LEAD, "period_ticks": PERIOD,
                   "events": sched}, f, indent=1)
    print(f"r{r}: counts {counts}  ref range [{ref.min():.3g} {ref.max():.3g}]  "
          f"u1 [{tape[:,0].min():.1f} {tape[:,0].max():.1f}] u4 [{tape[:,3].min():.1f} {tape[:,3].max():.1f}]")
print("wrote ref_mix_r*.csv, design_choi_mix_r*.csv, schedule_mix_r*.json ->", DAY)
