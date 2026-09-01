"""Synthesize Choi tape for one 220-tick period, tile to the full 22200-tick
reference (100 identical events), expand to 8-wide (model inputs 1,2 -> stim
words 1,4), write day_2026-08-31/design_choi_<SITE>.csv."""
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\brets\Documents\Repositories\TDTClosedLoop")
PY = sys.executable
DAY = REPO / "day_2026-08-31"
SCRATCH = Path(__file__).parent
PERIOD = 220
FIRST_ONSET = 202
PRE = 30                      # ticks of pre-event margin inside the period window
N_TICKS = 22200
WORD_MAP = {0: 0, 1: 3}       # model input index -> design column (u1, u4)

def load_ref(p):
    rows = list(csv.reader(open(p)))[1:]
    return np.array([float(r[1]) for r in rows])

for site in sys.argv[1:]:
    ref = load_ref(DAY / f"ref_{site}.csv")
    start = FIRST_ONSET - PRE
    period_ref = ref[start:start + PERIOD]
    pr = SCRATCH / f"period_ref_{site}.csv"
    with open(pr, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "r1"])
        for i, v in enumerate(period_ref):
            w.writerow([i + 1, repr(float(v))])
    pu = SCRATCH / f"period_u_{site}.csv"
    r = subprocess.run([PY, str(REPO / "rig" / "choi_synthesis.py"),
                        "--model", str(REPO / "plant_opfit.lti"),
                        "--reference", str(pr), "--umax", "30",
                        "--gate-threshold", "0", "--mu", "1e-13",
                        "--u-offset", "19.98", "20.11",
                        "--y-offset", "8.803e-05",
                        "--out", str(pu)], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or ["?"])[-1]
    if r.returncode != 0:
        print(f"{site}: CHOI FAIL: {tail} {r.stderr.strip().splitlines()[-1:] }")
        continue
    rows = list(csv.reader(open(pu)))
    hdr = rows[0]
    ui = [i for i, h in enumerate(hdr) if h.strip().lower().startswith("u")]
    U = np.array([[float(row[i]) for i in ui] for row in rows[1:]])  # [220 x 2]
    assert U.shape == (PERIOD, 2), U.shape
    tape = np.zeros((N_TICKS, 8))
    hold = U[-1]                                # steady-state value for lead-in
    for m, col in WORD_MAP.items():
        tape[:start, col] = hold[m]
        for k in range(1000):
            a = start + k * PERIOD
            if a >= N_TICKS:
                break
            b = min(a + PERIOD, N_TICKS)
            tape[a:b, col] = U[:b - a, m]
    out = DAY / f"design_choi_{site}.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick"] + [f"u{i+1}" for i in range(8)])
        for t in range(N_TICKS):
            w.writerow([t + 1] + [repr(float(v)) for v in tape[t]])
    print(f"{site}: choi OK ({tail}); tape u1 range [{tape[:,0].min():.2f} {tape[:,0].max():.2f}] "
          f"u4 range [{tape[:,3].min():.2f} {tape[:,3].max():.2f}] others max {tape[:,[1,2,4,5,6,7]].max():.0f} -> {out.name}")
