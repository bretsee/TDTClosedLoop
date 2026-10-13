#!/usr/bin/env python
"""make_synthetic_block.py -- a fake TDT block (.npz) with KNOWN delivery faults.

    python rig/make_synthetic_block.py --design design_runburst1.csv \
        --meta design_runburst1_meta.json --out day_X/synthetic_block_burst1.npz \
        [--max-ticks 24000] [--miss 0.02 --short 0.01 --long 0.01 --stretch 0.01] [--seed 1]

Nothing in the lab can write a .tsq/.tev, so this writes the stores the rig
readers use, at the real rates, into an .npz that rig/blockutil.load_block
returns with the tdt.read_block attribute shape:

  scalars.UDP1  (8, nTicks) + ts      the commands on the wire, one sample per tick
  streams.Scle  (8, M) int8 @ 24414   stim-enable per word: latches on the NEXT carrier
                                      edge after the command, high for B carrier periods
  streams.Plse  (M,)   int8 @ 24414   stim carrier (240 samples = 101.7253 Hz), 10-sample pulses
  streams.sSig  (16, M) int8 @ 24414  bipolar electrodes: pair (a:b) of --pairs gets +1/-1
  streams.sOut  (16, M) int8          copy of sSig
  streams.Wav1  (64, 6*nTicks) f32 @ 610.35  depressing-plant features (make_synthetic_burst_capture)
  streams.nThw  zeros

Faults injected per event (truth recorded in <out>_truth.json and inside the npz):
  miss     UDP edge present, Scle never latches          -> checker must count 'missed'
  short    Scle high for B-1 periods (B>1 only)           -> 'short'
  long     Scle high for B+1 periods                      -> 'long'
  stretch  UDP run B+1 ticks (hold-last stall) + B+1 periods -> STRETCHED run + 'long'
A companion capture CSV (<out>_capture.csv, tick,seq,t_ms,u1..u8,y1..y64) is written so
check_impulse_delivery --capture accounting can run too.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from design_burst_probe import read_design            # noqa: E402
from make_synthetic_burst_capture import simulate, write_capture   # noqa: E402

FS = 24414.0625
PERIOD = 240                      # samples per carrier period = per tick (frame-locked 6 x 40)
FS_WAV = FS / 40.0
PAIR_TABLE = "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True, help=".npz path")
    ap.add_argument("--max-ticks", type=int, default=24000, help="truncate the design (memory)")
    ap.add_argument("--pairs", default=PAIR_TABLE)
    ap.add_argument("--miss", type=float, default=0.0)
    ap.add_argument("--short", type=float, default=0.0)
    ap.add_argument("--long", type=float, default=0.0)
    ap.add_argument("--stretch", type=float, default=0.0)
    ap.add_argument("--latch-offset", type=int, default=120, help="carrier edge phase (samples) within the tick")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n-channels", type=int, default=64)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    Ud = read_design(args.design)
    with open(args.meta) as f:
        meta = json.load(f)
    n_full = Ud.shape[0]
    n = min(n_full, args.max_ticks)
    events = sorted([e for e in meta.get("events", []) if int(e["tick"]) + int(e.get("burst_ticks", 1)) <= n],
                    key=lambda e: e["tick"])
    Ud = Ud[:n].copy()
    m = Ud.shape[1]
    pairs = [tuple(int(x) - 1 for x in item.split(":")) for item in args.pairs.split(",")]

    # --- fault assignment ---------------------------------------------------
    truth = []
    for e in events:
        B = int(e.get("burst_ticks", 1))
        r = rng.random()
        fault = "exact"
        if r < args.miss:
            fault = "miss"
        elif r < args.miss + args.short and B > 1:
            fault = "short"
        elif r < args.miss + args.short + args.long:
            fault = "long"
        elif r < args.miss + args.short + args.long + args.stretch:
            fault = "stretch"
        truth.append(dict(tick=int(e["tick"]), pair=int(e["pair"]), amp=float(e["amp"]), B=B, fault=fault))

    # --- UDP1: the design, with hold-last stretches --------------------------
    U = Ud.T.astype(np.float32)                       # (8, n)
    for t in truth:
        if t["fault"] == "stretch":
            k = t["tick"] - 1 + t["B"]                # tick index just after the burst (0-based)
            if k < n:
                U[t["pair"] - 1, k] = t["amp"]
    ts = np.arange(n) * PERIOD / FS

    # --- Scle / sSig / Plse at 24414 Hz --------------------------------------
    M = n * PERIOD
    S = np.zeros((8, M), np.int8)
    G = np.zeros((16, M), np.int8)
    P = np.zeros(M, np.int8)
    edges = np.arange(args.latch_offset, M, PERIOD)
    for e0 in edges:
        P[e0:e0 + 10] = 1
    delivered = []
    for t in truth:
        w = t["pair"] - 1
        B = t["B"]
        nper = {"exact": B, "miss": 0, "short": B - 1, "long": B + 1, "stretch": B + 1}[t["fault"]]
        cmd = (t["tick"] - 1) * PERIOD                 # command sample (UDP ts of the first burst tick)
        e0 = edges[np.searchsorted(edges, cmd + 1)] if cmd + 1 <= edges[-1] else None
        if nper > 0 and e0 is not None:
            i1 = min(M, e0 + nper * PERIOD)
            S[w, e0:i1] = 1
            a, b = pairs[w]
            G[a, e0:i1] = 1
            G[b, e0:i1] = -1
        t["delivered"] = int(nper)
        delivered.append(nper)

    # --- Wav1: depressing plant at the tick rate, upsampled x40/6 = 6 frames per tick
    # gain x10 vs the capture generator so the 610 Hz evoked response is ~50 uV
    # (placement_gate thalamic needs z >= 8 against the per-channel noise)
    # dead=2 here: the capture-frame dead time of 3 ticks includes one transport
    # tick; in block time the evoked response follows the UDP edge by ~2 ticks
    # (20 ms), inside placement_gate's 6-30 ms window.
    Y, W, T, _drive = simulate(Ud, args.n_channels, args.seed, truth=dict(gain=2e-5, noise=1.0e-6, dead=2))
    wav = np.repeat(Y.T.astype(np.float32), 6, axis=1)          # (64, 6n) volts
    wav += (0.3 * T["noise"]) * rng.standard_normal(wav.shape).astype(np.float32)

    streams = dict(Scle=FS, Plse=FS, sSig=FS, sOut=FS, Wav1=FS_WAV, nThw=FS)
    meta_json = dict(streams=streams, scalars=["UDP1"], design=os.path.basename(args.design),
                     n_ticks=int(n), n_events=len(truth), fs=FS, period=PERIOD, pairs=args.pairs,
                     faults=dict(miss=args.miss, short=args.short, long=args.long, stretch=args.stretch),
                     latch_offset=args.latch_offset, truth=truth)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.savez_compressed(args.out,
                        meta_json=np.array(json.dumps(meta_json)),
                        stream_Scle=S, stream_Plse=P, stream_sSig=G, stream_sOut=G,
                        stream_Wav1=wav, stream_nThw=np.zeros(M, np.int8),
                        scalar_UDP1=U, scalar_UDP1_ts=ts)
    base = os.path.splitext(args.out)[0]
    with open(base + "_truth.json", "w") as f:
        json.dump(meta_json, f, indent=1)
    # truncated meta for --design-meta (events beyond the window dropped)
    meta_t = dict(meta)
    meta_t["events"] = [e for e in meta.get("events", []) if int(e["tick"]) + int(e.get("burst_ticks", 1)) <= n]
    meta_t["nTicks"] = int(n)
    meta_t["n_events"] = len(meta_t["events"])
    meta_t["truncated_from"] = os.path.basename(args.meta)
    with open(base + "_design_meta.json", "w") as f:
        json.dump(meta_t, f, indent=1)
    write_capture(base + "_capture.csv", Ud, Y)
    counts = {k: sum(1 for t in truth if t["fault"] == k) for k in ("exact", "miss", "short", "long", "stretch")}
    print("wrote %s: %d ticks (%.0f s), %d events, faults %s; Scle/sSig/Plse @ %.4f Hz, Wav1 %dx%d @ %.4f Hz"
          % (args.out, n, n * PERIOD / FS, len(truth), counts, FS, wav.shape[0], wav.shape[1], FS_WAV))
    print("  sidecars: %s_truth.json, %s_design_meta.json, %s_capture.csv" % (base, base, base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
