"""spat_common -- spatial/decoding analysis unlocked by the arm-block transfer.

Two data paths:
  - per-event 64-ch feature vectors from the ARM CAPTURES (day_2026-09-10),
    windowed by the interleaved schedules -> site decoding. Feature-space
    (rectified-mean LFP), artifact-contaminated during tonic stim; the
    decoding is reported with that caveat (raw-LFP artifact-aware redo is
    the next refinement).
  - a raw 64-ch stim-triggered footprint from one live arm BLOCK (Wav1),
    aligned to its capture by first-stim onset -> spatial footprint map.

Live arm blocks (matched 2026-09-11 by stim signature + Wav1 liveness):
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
DAY = HERE.parents[2]
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk        # noqa: E402
import trk_common as tc     # noqa: E402

LATER = Path(r"C:\Users\brets\Desktop\Data\Acute_091026-260910_LaterBlocks")
BLOCK = {  # run label -> block dir (live arms only)
    "mpc_r1": "BSCL20260909BU-260910-215613",
    "choi_r1": "BSCL20260909BU-260910-220332",
    "mpc_r2": "BSCL20260909BU-260910-221053",
    "choi_r2": "BSCL20260909BU-260910-221543",
    "mpc_r3": "BSCL20260909BU-260910-222149",
    "choi_r3": "BSCL20260909BU-260910-222643",
    "mpc_r1_late": "BSCL20260909BU-260910-223341",
    "choi_r1_late": "BSCL20260909BU-260910-223918",
    "nn_r1b": "BSCL20260909BU-260910-231833",
    "mpc_r4b": "BSCL20260909BU-260910-232426",
}
BLACKLIST = {33, 36, 45, 59}
SITES = ["LP", "P1", "MP", "P3", "SHAM"]
EVOKED_TICKS = (2, 18)   # 20-180 ms post event-onset feature window


def event_vectors(run: str) -> tuple[np.ndarray, list[str]]:
    """Per-event 64-ch feature vector (mean over evoked window), from capture."""
    import pandas as pd
    arm, cap, ref, tj, sch = tc.RUNS[run]
    d = pd.read_csv(dk.need(DAY / cap))
    Y = d[[f"y{k}" for k in range(1, 65)]].to_numpy()
    sched = dk.jload(DAY / sch)
    X, labels = [], []
    a, b = EVOKED_TICKS
    for ev in sched["events"]:
        i0 = int(ev["onset_tick"])
        if i0 + b > len(Y):
            continue
        base = Y[i0 - 5:i0].mean(axis=0) if i0 >= 5 else Y[i0]
        v = Y[i0 + a:i0 + b].mean(axis=0) - base
        X.append(v)
        labels.append(ev["site"])
    X = np.array(X)
    keep = [c for c in range(64) if (c + 1) not in BLACKLIST]
    return X[:, keep], labels


def raw_footprint(run: str) -> np.ndarray:
    """Mean |Wav1| across the run per channel (64,), from the raw block."""
    import tdt
    blk = dk.need(LATER / BLOCK[run])
    d = tdt.read_block(str(blk), store=["Wav1"])
    w = np.asarray(d.streams.Wav1.data)
    return np.abs(w).mean(axis=1)


def write_json(name, payload):
    (ANA / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {ANA / name}")
