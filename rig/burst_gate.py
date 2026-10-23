"""burst_gate.py -- per-pair, per-burst-length thalamic gate from a burst-ladder BLOCK (RZ2 clock).

    python rig/burst_gate.py --block <dir> [--n-channels 64] [--out-root galleries]

Reads Wav1 + UDP1 from the block, finds every stim event per word (rising edge of the UDP1 word),
measures the burst length actually delivered from the word's hold time (carrier 101.725 Hz), then per
pair x burst class grades the touch-style evoked response with an ARTIFACT-ROBUST estimator:
the trial-mean trace is median-filtered over 5 samples (~8 ms at 610 Hz) so one-sample stim-pulse
spikes at multiples of 9.83 ms vanish while a cortical LFP wave (>= 5 ms wide) survives. z is that
filtered peak against a shuffled-onset null with the same estimator and n. Also reports the per-trial
strength z/sqrt(n) (acute-2 GO pairs: 0.96-2.8 at n=228) and the split-half correlation of the two
half-means over the window. Written 2026-10-22 23:20 for run burst30 (B = 1, 3, 10 at 30 uA).
"""
import argparse
import json
import os
import sys

import numpy as np
from scipy.ndimage import median_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import placement_gate as PG  # noqa: E402

CARRIER_HZ = 101.725
PRE_MS, POST_MS = 40.0, 260.0
N_SHUFFLE = 100
Z_RESP, Z_WEAK, STRENGTH_OK, SPLIT_OK = 5.0, 3.0, 0.9, 0.6


def events_with_length(blk):
    u = PG._find_store(blk, "UDP1")
    ts = np.asarray(u.ts).ravel()
    dd = np.asarray(u.data)
    if dd.ndim == 1:
        dd = dd[None, :]
    dt = float(np.median(np.diff(ts)))
    ev = []
    for r in range(dd.shape[0]):
        on = dd[r] > 0.5
        idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
        for i in idx:
            j = i
            while j < len(on) and on[j]:
                j += 1
            hold_s = (j - i) * dt
            ev.append((ts[i], r + 1, float(np.max(dd[r][i:j])), hold_s, int(round(hold_s * CARRIER_HZ))))
    ev.sort()
    t = np.array([e[0] for e in ev]); p = np.array([e[1] for e in ev]); a = np.array([e[2] for e in ev])
    hold = np.array([e[3] for e in ev]); npulse = np.array([e[4] for e in ev])
    return t, p, a, hold, npulse


def burst_class(npulse):
    # nominal B = 1 / 3 / 10 ticks; PC tick drops stretch holds, so classify by nearest nominal
    nom = np.array([1, 3, 10])
    return nom[np.argmin(np.abs(npulse[:, None] - nom[None, :]), axis=1)]


def filt(m):
    return median_filter(m, size=(1, 5), mode="nearest")


def peak_in(mf, t_ms, lo, hi):
    w = (t_ms >= lo) & (t_ms <= hi)
    seg = mf[:, w]
    k = np.argmax(np.abs(seg), axis=1)
    pk = seg[np.arange(seg.shape[0]), k]
    lat = t_ms[w][k]
    return pk, lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", required=True)
    ap.add_argument("--n-channels", type=int, default=64)
    ap.add_argument("--out-root", default=os.path.join(os.path.dirname(HERE), "galleries"))
    args = ap.parse_args()
    bdir = PG.resolve_block_dir(args.block)
    blk = PG.read_block(bdir, ("Wav1", "UDP1"))
    data, fs, t0 = PG.wav1_uv(blk, args.n_channels)
    n_ch = data.shape[0]
    t, pairs, amps, hold, npulse = events_with_length(blk)
    B = burst_class(npulse)
    name = os.path.basename(bdir.rstrip("\\/"))
    out_dir = os.path.join(args.out_root, name)
    os.makedirs(out_dir, exist_ok=True)
    print("block %s: %d events, pulses delivered per nominal B: %s" % (
        name, len(t), {int(b): "median %d (min %d max %d)" % (np.median(npulse[B == b]), npulse[B == b].min(), npulse[B == b].max())
                       for b in (1, 3, 10) if np.any(B == b)}))
    rng = np.random.default_rng(0)
    n_pre = int(round(PRE_MS * 1e-3 * fs)); n_post = int(round(POST_MS * 1e-3 * fs))
    t_ms = np.arange(-n_pre, n_post) / fs * 1e3
    rows = []
    traces = {}
    hdr = "pair  B  n  pulses   z_filt  z_raw  best   peak(uV) lat(ms)  split  z/sqrt(n)  status"
    print(hdr)
    for p in range(1, 9):
        for b in (1, 3, 10):
            sel = (pairs == p) & (B == b)
            i0, _, _ = PG.epoch_idx(data.shape[1], fs, t0, t[sel], PRE_MS, POST_MS)
            n = len(i0)
            if n < 6:
                continue
            m, tr = PG.mean_response(data, i0, n_pre, n_post)
            npl = int(np.median(npulse[sel]))
            lo, hi = 6.0, (npl - 1) * (1000.0 / CARRIER_HZ) + 40.0
            mf = filt(m)
            pk, lat = peak_in(mf, t_ms, lo, hi)
            pk_raw, _ = peak_in(m, t_ms, lo, hi)
            # null with the same estimator
            nullpk = np.zeros((N_SHUFFLE, n_ch)); nullraw = np.zeros((N_SHUFFLE, n_ch))
            off = np.arange(-n_pre, n_post)
            for k in range(N_SHUFFLE):
                on = rng.integers(n_pre, data.shape[1] - n_post, size=n)
                seg = data[:, on[:, None] + off[None, :]]
                seg = seg - seg[:, :, :n_pre].mean(axis=2, keepdims=True)
                ms = seg.mean(axis=1)
                nullpk[k] = np.abs(peak_in(filt(ms), t_ms, lo, hi)[0])
                nullraw[k] = np.abs(peak_in(ms, t_ms, lo, hi)[0])
            z = (np.abs(pk) - nullpk.mean(0)) / (nullpk.std(0) + 1e-9)
            z_raw = (np.abs(pk_raw) - nullraw.mean(0)) / (nullraw.std(0) + 1e-9)
            best = int(np.argmax(z))
            w = (t_ms >= lo) & (t_ms <= hi)
            h1 = filt(tr[best:best + 1, 0::2].mean(axis=1))[0, w]
            h2 = filt(tr[best:best + 1, 1::2].mean(axis=1))[0, w]
            split = float(np.corrcoef(h1, h2)[0, 1])
            strength = float(z[best] / np.sqrt(n))
            status = ("RESPONSIVE" if z[best] >= Z_RESP and strength >= STRENGTH_OK and split >= SPLIT_OK
                      else "MARGINAL" if z[best] >= Z_RESP else "WEAK" if z[best] >= Z_WEAK else "SILENT")
            rows.append(dict(pair=p, B=b, n=n, pulses=npl, z=float(z[best]), z_raw=float(z_raw[best]), best_channel_1based=best + 1,
                             peak_uv=float(pk[best]), latency_ms=float(lat[best]), split_half=split, strength=strength,
                             status=status, window_ms=[lo, hi], z_per_channel=np.round(z, 2).tolist()))
            traces[(p, b)] = (m[best], mf[best], best)
            print("%4d %2d %3d  %4d    %6.1f %6.1f  ch%-3d  %+8.0f  %6.1f   %5.2f   %5.2f    %s" % (
                p, b, n, npl, z[best], z_raw[best], best + 1, pk[best], lat[best], split, strength, status))
    # verdict per B
    for b in (1, 3, 10):
        rr = [r for r in rows if r["B"] == b]
        if not rr:
            continue
        resp = [r for r in rr if r["status"] == "RESPONSIVE"]
        # footprint rank over responsive+marginal pairs from the per-channel z maps
        live = [r for r in rr if r["status"] in ("RESPONSIVE", "MARGINAL")]
        rank = 0
        if live:
            F = np.array([np.array(r["z_per_channel"]) * (np.array(r["z_per_channel"]) >= Z_WEAK) for r in live])
            F = F / (np.linalg.norm(F, axis=1, keepdims=True) + 1e-12)
            sv = np.linalg.svd(F, compute_uv=False); sv = sv / (sv[0] + 1e-30)
            rank = int(np.sum(sv >= 0.3))
        print("B=%2d: responsive %d %s, marginal %d, eff rank %d -> %s" % (
            b, len(resp), [r["pair"] for r in resp], len(live) - len(resp), rank,
            "BURST GATE GO" if len(resp) >= 2 and rank >= 2 else "no"))
    json.dump(dict(block=name, rows=rows), open(os.path.join(out_dir, "burst_gate.json"), "w"), indent=1)
    # figure: 8 pairs x (raw mean B=1/3/10 at each class's best channel)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 4, figsize=(18, 7), sharex=True)
    for p in range(1, 9):
        ax = axs[(p - 1) // 4, (p - 1) % 4]
        for b, c in zip((1, 3, 10), ("tab:blue", "tab:orange", "tab:red")):
            if (p, b) in traces:
                m, mf, best = traces[(p, b)]
                ax.plot(t_ms, m, color=c, lw=0.7, alpha=0.5)
                ax.plot(t_ms, mf, color=c, lw=1.6, label="B=%d ch%d" % (b, best + 1))
        ax.axvline(0, color="k", ls="--", lw=0.7)
        ax.set_title("pair %d" % p); ax.legend(fontsize=7); ax.set_xlim(-30, 200)
        if p > 4:
            ax.set_xlabel("ms from burst onset")
        if p in (1, 5):
            ax.set_ylabel("uV (thin raw, thick median-filtered)")
    fig.suptitle("%s  burst30: per-pair means at the best channel per burst length" % name)
    fig.tight_layout()
    png = os.path.join(out_dir, "burst_gate.png")
    fig.savefig(png, dpi=110)
    print("figure:", png)


if __name__ == "__main__":
    main()
