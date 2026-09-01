"""Extract per-trial epochs for touch battery, arm blocks, and probe blocks.

Caches to analysis/cache/*.npz so figure scripts are fast to iterate.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

CACHE = os.path.join(sc.ANA_DIR, "cache")
os.makedirs(CACHE, exist_ok=True)

PRE_S = 0.05

# ---------- 1) Touch battery ----------
for site in sc.SITE_ORDER:
    out = os.path.join(CACHE, f"touch_{site}.npz")
    if os.path.exists(out):
        print("skip", out); continue
    blk = sc.read_block(sc.TOUCH_BLOCKS[site])
    d, fs, t0s = sc.wav1_uv(blk)
    on = sc.rising_edges_stream(blk.streams.nThw)
    tr, n_pre, kept = sc.epoch(d, fs, t0s, on, pre_s=PRE_S)
    trb = sc.baseline_subtract(tr, n_pre)
    np.savez_compressed(out, trials=trb.astype(np.float32), n_pre=n_pre,
                        fs=fs, site=site, n_onsets=len(on))
    print(f"touch {site}: {trb.shape} n_pre {n_pre}")

# ---------- 2) Arm blocks ----------
for arm, (blkname, schname) in sc.ARM_BLOCKS.items():
    out = os.path.join(CACHE, f"arm_{arm}.npz")
    if os.path.exists(out):
        print("skip", out); continue
    blk = sc.read_block(blkname)
    d, fs, t0s = sc.wav1_uv(blk)
    u = blk.scalars["UDP1"]
    ts = np.asarray(u.ts).ravel()
    sch = json.load(open(os.path.join(sc.DAY_DIR, schname)))
    ev_sites, ev_times = [], []
    n_ticks = ts.size
    for e in sch["events"]:
        k = e["onset_tick"] - 1
        if k < 0 or k >= n_ticks:
            print(f"  WARN {arm} event {e['event']} tick {e['onset_tick']} outside UDP1 ({n_ticks})")
            continue
        ev_sites.append(e["site"]); ev_times.append(ts[k])
    ev_times = np.array(ev_times)
    tr, n_pre, kept = sc.epoch(d, fs, t0s, ev_times, pre_s=PRE_S)
    ev_sites = np.array(ev_sites)[kept]
    trb = sc.baseline_subtract(tr, n_pre)
    np.savez_compressed(out, trials=trb.astype(np.float32), n_pre=n_pre, fs=fs,
                        sites=ev_sites, n_udp_ticks=n_ticks)
    print(f"arm {arm}: {trb.shape} sites {dict(zip(*np.unique(ev_sites, return_counts=True)))}")

# ---------- 3) Probe blocks (rnd1, rndhi) ----------
def extract_probes(blkname, tag, t_min=None):
    out = os.path.join(CACHE, f"probe_{tag}.npz")
    if os.path.exists(out):
        print("skip", out); return
    blk = sc.read_block(blkname)
    d, fs, t0s = sc.wav1_uv(blk)
    u = blk.scalars["UDP1"]
    ts = np.asarray(u.ts).ravel()
    dd = np.asarray(u.data)  # 8 x n_ticks
    pairs, amps, times = [], [], []
    for r in range(dd.shape[0]):
        v = dd[r]
        on = v > 0.5
        idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
        for i in idx:
            a = float(np.max(v[i:i + 4]))
            t = ts[i]
            if t_min is not None and t <= t_min:
                continue
            pairs.append(r + 1); amps.append(a); times.append(t)
    pairs, amps, times = map(np.array, (pairs, amps, times))
    order = np.argsort(times)
    pairs, amps, times = pairs[order], amps[order], times[order]
    tr, n_pre, kept = sc.epoch(d, fs, t0s, times, pre_s=PRE_S)
    pairs, amps, times = pairs[kept], amps[kept], times[kept]
    trb = sc.baseline_subtract(tr, n_pre)
    np.savez_compressed(out, trials=trb.astype(np.float32), n_pre=n_pre, fs=fs,
                        pairs=pairs, amps=np.round(amps).astype(int), times=times)
    uamps = np.unique(np.round(amps).astype(int))
    print(f"probe {tag}: {trb.shape} pairs {np.unique(pairs)} amps {uamps} "
          f"counts/pair {np.bincount(pairs)[1:]}")

extract_probes(sc.RND1_BLOCK, "rnd1", t_min=185.0)
try:
    extract_probes(sc.RNDHI_BLOCK, "rndhi")
except Exception as ex:
    print("rndhi failed:", ex)

print("extraction done")
