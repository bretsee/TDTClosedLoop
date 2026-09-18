#!/usr/bin/env python
r"""placement_gate.py -- ONE-SCREEN GO / MARGINAL / NO-GO for array placement.

    python rig\placement_gate.py --mode cortical --newest            # last thwack block
    python rig\placement_gate.py --mode cortical --block <thwack block dir>
    python rig\placement_gate.py --mode thalamic --newest            # last probe block
    python rig\placement_gate.py --mode thalamic --block <probe block dir> --min-amp 13
    python rig\placement_gate.py --mode both --cortical <thwack blk> --thalamic <probe blk>

The surgery-day question is "is the array where it needs to be, and if not,
which way do I move it?" -- answered quantitatively from ONE short block, so
nobody listens for spikes or squints at a scrolling trace.

cortical  (planar/laminar S1 array, thwack block, nThw trigger)
    Per channel: touch-evoked signed peak in 5-60 ms vs a SHUFFLED-TRIGGER
    null (same trial count, random onsets) -> z. Split-half reliability of
    the 64-ch map, latency, footprint size, focus position on the grid.
    GO       best z >= 8, split-half >= 0.80, latency 8-45 ms, n >= 30
    MARGINAL best z >= 4 or split-half >= 0.60
    NO-GO    otherwise (= the SHAM / off-target signature)
    ADJUST hint: if the focus sits within one row/col of the grid edge the
    array should be shifted toward that edge (grid = row-major by channel,
    ch1-8 = row 1 -- the convention used by spat_footprint; pass --map to
    override with a 64-entry JSON list of channel numbers in grid order).
    A 40-thwack block (~45 s) is enough for the verdict; 150 is for templates.

thalamic  (VPL stim array, single-pulse probe block, UDP1 words = pairs)
    Per pair (amp >= --min-amp): signed-average raw LFP, per-channel peak in
    6-30 ms vs shuffled-trigger null -> z (a peak ON the window's first sample
    is the stim-artifact tail and is re-searched past it -- the 2026-08-31
    32-ch block otherwise reads every pair as a 3 ms "response"); knee = smallest amp with z >= 3 on
    the best channel; footprint = per-channel signed peak vector; pairwise
    footprint correlation + effective rank (SVD, >= 0.1*s1).
    per pair  RESPONSIVE z >= 5 | WEAK 3-5 | SILENT < 3
    GO       >= 2 responsive pairs AND footprint eff. rank >= 2
    MARGINAL 1 responsive pair, or >= 2 but rank 1 (same footprint)
    NO-GO    0 responsive pairs
    ADJUST hint: silent pairs reported by ladder position (short-tip end vs
    long-tip end of the Microprobes 2x8) -> depth/AP direction to move.
    This is the 2026-08-31 lesson made automatic: a FITTER null is never a
    placement verdict; the signed raw-LFP average is.

Outputs: galleries/<block>/gate_<mode>.png + gate_<mode>.json, and the
verdict line on stdout. Exit 0 = GO, 2 = MARGINAL, 3 = NO-GO, 1 = could not
evaluate (missing store, flat trigger, too few trials).
"""

import argparse
import glob
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "rig"))
DEFAULT_DATA_ROOT = r"C:\Users\brets\Desktop\Data"

# thresholds (one place; quoted in the JSON so a deck can print them)
CORT = dict(z_go=8.0, z_marg=4.0, shc_go=0.80, shc_marg=0.60,
            lat_lo_ms=8.0, lat_hi_ms=45.0, n_min=30, win_ms=(5.0, 60.0),
            pre_ms=40.0, post_ms=200.0, foot_z=4.0)
THAL = dict(z_resp=5.0, z_weak=3.0, lat_lo_ms=6.0, lat_hi_ms=30.0,
            n_min=20, win_ms=(6.0, 30.0), pre_ms=20.0, post_ms=60.0, edge_skip=2,
            rank_thresh=0.1, knee_z=3.0)
N_SHUFFLE = 200

# Microprobes 2x8 (MEA #20786) ladder, word -> tip length mm (09-09 verified)
PAIR_LENGTH_MM = {1: 7.4, 2: 7.6, 3: 7.8, 4: 8.0, 5: 8.0, 6: 8.0, 7: 8.0, 8: 8.0}

EXIT = {"GO": 0, "MARGINAL": 2, "NO-GO": 3}


def fail(msg):
    print("GATE: COULD NOT EVALUATE -- %s" % msg)
    return 1


# --------------------------------------------------------------------------
# block helpers (same conventions as plot_trial_responses.py)
# --------------------------------------------------------------------------
def resolve_block_dir(p):
    if glob.glob(os.path.join(p, "*.tsq")):
        return p
    kids = [os.path.join(p, k) for k in os.listdir(p)
            if os.path.isdir(os.path.join(p, k))
            and glob.glob(os.path.join(p, k, "*.tsq"))]
    return kids[0] if len(kids) == 1 else p


def newest_block_dir(data_root):
    dirs = [os.path.join(data_root, d) for d in os.listdir(data_root)
            if os.path.isdir(os.path.join(data_root, d))]
    return max(dirs, key=os.path.getmtime) if dirs else None


def _find_store(blk, name):
    for grp in ("streams", "scalars", "epocs"):
        g = getattr(blk, grp, None)
        if g is not None and name in list(g.keys()):
            return g[name]
    return None


def read_block(path, stores):
    import tdt
    try:
        blk = tdt.read_block(path, store=list(stores))
        if all(_find_store(blk, s) is not None for s in stores):
            return blk
    except Exception as exc:  # noqa: BLE001
        print("note: filtered read failed (%s); reading full block" % type(exc).__name__)
    return tdt.read_block(path)


def wav1_uv(blk, n_channels):
    s = _find_store(blk, "Wav1")
    if s is None:
        raise RuntimeError("Wav1 stream not found")
    d = np.asarray(s.data, dtype=np.float64)
    if d.ndim == 1:
        d = d[None, :]
    if not np.any(d):
        raise RuntimeError("Wav1 is ALL ZERO (disk saving off / PZ2 off)")
    if float(np.max(np.abs(d))) < 0.1:
        d *= 1e6
    if n_channels and d.shape[0] > n_channels:
        d = d[:n_channels]
    return d, float(s.fs), float(getattr(s, "start_time", 0.0))


def thwack_onsets(blk, min_pulse_ms=50.0):
    s = _find_store(blk, "nThw")
    if s is None:
        raise RuntimeError("nThw not found (thwacker line not enabled?)")
    if hasattr(s, "onset"):
        return np.asarray(s.onset, dtype=np.float64)
    d = np.asarray(s.data, dtype=np.float64).ravel()
    fs = float(s.fs)
    t0 = float(getattr(s, "start_time", 0.0))
    if float(d.max()) <= float(d.min()):
        raise RuntimeError("nThw is FLAT -- thwacker never pulsed")
    b = d > 0.5
    rise = np.flatnonzero(~b[:-1] & b[1:]) + 1
    fall = np.flatnonzero(b[:-1] & ~b[1:]) + 1
    if len(fall) and len(rise) and fall[0] < rise[0]:
        fall = fall[1:]
    n = min(len(rise), len(fall))
    keep = (fall[:n] - rise[:n]) / fs * 1000.0 >= min_pulse_ms
    return t0 + rise[:n][keep] / fs


def probe_events(blk, t_min=None):
    u = _find_store(blk, "UDP1")
    if u is None:
        raise RuntimeError("UDP1 scalar store not found (loop server not running?)")
    ts = np.asarray(u.ts).ravel()
    dd = np.asarray(u.data)
    if dd.ndim == 1:
        dd = dd[None, :]
    pairs, amps, times = [], [], []
    for r in range(dd.shape[0]):
        v = dd[r]
        on = v > 0.5
        idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
        for i in idx:
            if t_min is not None and ts[i] <= t_min:
                continue
            pairs.append(r + 1)
            amps.append(float(np.max(v[i:i + 4])))
            times.append(ts[i])
    if not times:
        raise RuntimeError("zero UDP1 rising edges -- no probes in block")
    pairs, amps, times = map(np.asarray, (pairs, amps, times))
    o = np.argsort(times)
    return times[o], pairs[o], np.round(amps[o]).astype(int)


# --------------------------------------------------------------------------
# core estimator: evoked peak z against a shuffled-trigger null
# --------------------------------------------------------------------------
def epoch_idx(n_samp, fs, t0, onsets, pre_ms, post_ms):
    n_pre = int(round(pre_ms * 1e-3 * fs))
    n_post = int(round(post_ms * 1e-3 * fs))
    i0 = np.round((onsets - t0) * fs).astype(int)
    ok = (i0 - n_pre >= 0) & (i0 + n_post <= n_samp)
    return i0[ok], n_pre, n_post


def mean_response(data, i0, n_pre, n_post):
    """Baseline-subtracted trial mean [ch, n_pre+n_post] via fancy indexing."""
    off = np.arange(-n_pre, n_post)
    idx = i0[:, None] + off[None, :]                    # [n_tr, T]
    tr = data[:, idx]                                    # [ch, n_tr, T]
    tr = tr - tr[:, :, :n_pre].mean(axis=2, keepdims=True)
    return tr.mean(axis=1), tr


def peak_in_window(m, n_pre, fs, win_ms, edge_skip=0):
    """Signed peak per channel in the window. With edge_skip>0 a peak that
    lands on the window's FIRST sample is treated as artifact spill-over and
    the search is repeated from edge_skip samples later (returns edge flag)."""
    a = n_pre + int(round(win_ms[0] * 1e-3 * fs))
    b = n_pre + int(round(win_ms[1] * 1e-3 * fs))
    seg = m[:, a:b]
    k = np.argmax(np.abs(seg), axis=1)
    edge = k == 0
    if edge_skip and np.any(edge):
        k2 = np.argmax(np.abs(seg[:, edge_skip:]), axis=1) + edge_skip
        k = np.where(edge, k2, k)
    peak = seg[np.arange(m.shape[0]), k]
    lat_ms = (a + k - n_pre) / fs * 1e3
    if edge_skip:
        return peak, lat_ms, edge
    return peak, lat_ms


def shuffled_null(data, n_tr, n_pre, n_post, fs, win_ms, rng, n_shuffle=N_SHUFFLE):
    """Per-channel (mean, sd) of |peak| under random triggers, same n_tr."""
    n_samp = data.shape[1]
    peaks = np.empty((n_shuffle, data.shape[0]))
    for s in range(n_shuffle):
        fake = rng.integers(n_pre, n_samp - n_post, size=n_tr)
        m, _ = mean_response(data, fake, n_pre, n_post)
        pk, _ = peak_in_window(m, n_pre, fs, win_ms)
        peaks[s] = np.abs(pk)
    return peaks.mean(axis=0), peaks.std(axis=0) + 1e-12


def split_half(tr, rng):
    """corr of two half-means over the whole [ch x T] map; tr [ch, n_tr, T]."""
    n = tr.shape[1]
    if n < 4:
        return float("nan")
    idx = rng.permutation(n)
    h = n // 2
    a = tr[:, idx[:h]].mean(axis=1).ravel()
    b = tr[:, idx[h:2 * h]].mean(axis=1).ravel()
    return float(np.corrcoef(a, b)[0, 1])


def grid_of(vec, chmap):
    g = np.full((8, 8), np.nan)
    for r in range(8):
        for c in range(8):
            ch = chmap[r * 8 + c]
            if 1 <= ch <= len(vec):
                g[r, c] = vec[ch - 1]
    return g


# --------------------------------------------------------------------------
# cortical gate
# --------------------------------------------------------------------------
def gate_cortical(block_dir, n_channels, chmap, blacklist, out_dir, plt):
    P = CORT
    blk = read_block(block_dir, ("Wav1", "nThw"))
    data, fs, t0 = wav1_uv(blk, n_channels)
    n_ch = data.shape[0]
    for ch in blacklist:
        if 1 <= ch <= n_ch:
            data[ch - 1] = 0.0
    onsets = thwack_onsets(blk)
    i0, n_pre, n_post = epoch_idx(data.shape[1], fs, t0, onsets, P["pre_ms"], P["post_ms"])
    n_tr = len(i0)
    if n_tr < 4:
        raise RuntimeError("only %d usable thwacks" % n_tr)
    rng = np.random.default_rng(0)
    m, tr = mean_response(data, i0, n_pre, n_post)
    peak, lat = peak_in_window(m, n_pre, fs, P["win_ms"])
    nmean, nsd = shuffled_null(data, n_tr, n_pre, n_post, fs, P["win_ms"], rng)
    z = (np.abs(peak) - nmean) / nsd
    shc = split_half(tr, rng)
    best = int(np.argmax(z))
    z_best = float(z[best])
    half = (z >= P["foot_z"]) & (np.abs(peak) >= 0.5 * abs(peak[best]))
    footprint = int(np.sum(half))
    # focus position on the grid (|peak|-weighted centroid of the half-max footprint)
    gz = grid_of(z, chmap)
    gp = grid_of(np.abs(peak) * half, chmap)
    w = np.nan_to_num(gp)
    if w.sum() > 0:
        rr, cc = np.indices(w.shape)
        cy, cx = float((rr * w).sum() / w.sum()), float((cc * w).sum() / w.sum())
    else:
        cy, cx = float("nan"), float("nan")
    edge = []
    if np.isfinite(cy):
        if cy < 1.0:
            edge.append("row-1 edge (ch1-8 side)")
        if cy > 6.0:
            edge.append("row-8 edge (ch57-64 side)")
        if cx < 1.0:
            edge.append("col-1 edge")
        if cx > 6.0:
            edge.append("col-8 edge")

    lat_ok = P["lat_lo_ms"] <= lat[best] <= P["lat_hi_ms"]
    if (z_best >= P["z_go"] and shc >= P["shc_go"] and lat_ok and n_tr >= P["n_min"]):
        verdict = "GO"
    elif z_best >= P["z_marg"] or shc >= P["shc_marg"]:
        verdict = "MARGINAL"
    else:
        verdict = "NO-GO"
    reasons = []
    if z_best < P["z_go"]:
        reasons.append("best z %.1f < %.0f" % (z_best, P["z_go"]))
    if shc < P["shc_go"]:
        reasons.append("split-half %.2f < %.2f" % (shc, P["shc_go"]))
    if not lat_ok:
        reasons.append("latency %.0f ms outside %g-%g" % (lat[best], P["lat_lo_ms"], P["lat_hi_ms"]))
    if n_tr < P["n_min"]:
        reasons.append("only %d trials (< %d)" % (n_tr, P["n_min"]))
    hint = ""
    if verdict != "GO":
        hint = ("no evoked focus -> array is off the responding S1 patch (or the "
                "touch site is wrong / thwacker missed): move array, re-thwack 40x"
                if z_best < P["z_marg"] else
                "weak focus -> nudge toward the strongest channels and repeat")
    if edge:
        hint = (hint + "; " if hint else "") + "focus on the %s -> shift array toward it" % " & ".join(edge)

    top = np.argsort(z)[::-1][:5]
    res = dict(mode="cortical", block=os.path.basename(block_dir), verdict=verdict,
               n_trials=int(n_tr), n_channels=int(n_ch), fs=fs,
               best_channel_1based=best + 1, best_z=z_best,
               best_peak_uv=float(peak[best]), best_latency_ms=float(lat[best]),
               split_half=shc, footprint_channels=footprint,
               focus_grid_rc=[cy, cx], edge=edge, reasons=reasons, hint=hint,
               top5=[dict(ch=int(c + 1), z=float(z[c]), peak_uv=float(peak[c]),
                          lat_ms=float(lat[c])) for c in top],
               z_per_channel=[float(v) for v in z], thresholds=P,
               grid_convention="row-major by channel (ch1-8 = row 1)" if chmap is None
               else "custom --map")

    # ---- figure ---------------------------------------------------------
    t_ms = (np.arange(-n_pre, n_post)) / fs * 1e3
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2), width_ratios=[1.0, 1.4, 1.2])
    ax = axes[0]
    im = ax.imshow(gz, cmap="Blues", vmin=0, vmax=max(P["z_go"], np.nanmax(gz)))
    ax.set_title("evoked z, 8x8 grid (half-max ch labelled)")
    for r in range(8):
        for c in range(8):
            v = gz[r, c]
            if np.isfinite(v) and half[chmap[r * 8 + c] - 1]:
                ax.text(c, r, "%d" % chmap[r * 8 + c], ha="center", va="center", fontsize=7,
                        color="white" if v > 0.6 * np.nanmax(gz) else "black")
    if np.isfinite(cy):
        ax.plot(cx, cy, "+", color="#e34948", ms=14, mew=2)
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.8, label="z")
    ax = axes[1]
    for c in top:
        ax.plot(t_ms, m[c], lw=1.4, label="ch%d z%.0f" % (c + 1, z[c]))
    ax.axvspan(P["win_ms"][0], P["win_ms"][1], color="#e1e0d9", alpha=0.5, lw=0)
    ax.axvline(0, color="#52514e", lw=0.8, ls="--")
    ax.set_xlabel("ms from touch onset"); ax.set_ylabel("uV")
    ax.set_title("top-5 channel means (n=%d)" % n_tr)
    ax.legend(frameon=False, fontsize=8)
    ax = axes[2]
    stack = tr[best]
    v = np.percentile(np.abs(stack), 98) + 1e-9
    ax.imshow(stack, aspect="auto", cmap="RdBu_r", vmin=-v, vmax=v,
              extent=[t_ms[0], t_ms[-1], n_tr, 0], interpolation="nearest")
    ax.axvline(0, color="#52514e", lw=0.8, ls="--")
    ax.set_xlabel("ms"); ax.set_ylabel("trial")
    ax.set_title("ch%d single trials, split-half %.2f" % (best + 1, shc))
    fig.suptitle("CORTICAL GATE: %s  --  %s | best ch%d %+.0f uV @ %.0f ms, z %.1f, footprint %d ch%s"
                 % (verdict, res["block"], best + 1, peak[best], lat[best], z_best, footprint,
                    (" | " + hint) if hint else ""),
                 fontsize=11, color={"GO": "#1b7a3a", "MARGINAL": "#b8860b", "NO-GO": "#b3413a"}[verdict])
    fig.tight_layout()
    return res, fig


# --------------------------------------------------------------------------
# thalamic gate
# --------------------------------------------------------------------------
def gate_thalamic(block_dir, n_channels, min_amp, blacklist, t_min, out_dir, plt):
    P = THAL
    blk = read_block(block_dir, ("Wav1", "UDP1"))
    data, fs, t0 = wav1_uv(blk, n_channels)
    n_ch = data.shape[0]
    for ch in blacklist:
        if 1 <= ch <= n_ch:
            data[ch - 1] = 0.0
    times, pairs, amps = probe_events(blk, t_min)
    rng = np.random.default_rng(0)
    t_ms = None
    per_pair, footprints, traces = [], [], []
    n_pre = n_post = None
    for p in sorted(set(pairs.tolist())):
        sel = pairs == p
        # per-amp z on the pooled-best channel -> knee
        i_all, n_pre, n_post = epoch_idx(data.shape[1], fs, t0, times[sel & (amps >= min_amp)],
                                         P["pre_ms"], P["post_ms"])
        n_tr = len(i_all)
        entry = dict(pair=int(p), n_trials=int(n_tr), tip_mm=PAIR_LENGTH_MM.get(int(p)))
        if n_tr < 4:
            entry.update(status="NO DATA", z=0.0)
            per_pair.append(entry); footprints.append(np.zeros(n_ch)); traces.append(None)
            continue
        m, tr = mean_response(data, i_all, n_pre, n_post)
        peak, lat, edge = peak_in_window(m, n_pre, fs, P["win_ms"], P["edge_skip"])
        nmean, nsd = shuffled_null(data, n_tr, n_pre, n_post, fs, P["win_ms"], rng, n_shuffle=100)
        z = (np.abs(peak) - nmean) / nsd
        best = int(np.argmax(z))
        z_best = float(z[best])
        lat_ok = P["lat_lo_ms"] <= lat[best] <= P["lat_hi_ms"]
        status = ("RESPONSIVE" if (z_best >= P["z_resp"] and lat_ok)
                  else "WEAK" if z_best >= P["z_weak"] else "SILENT")
        # knee: smallest amp with z>=knee_z on the best channel
        knee = None
        amp_z = []
        for a in sorted(set(amps[sel].tolist())):
            ia, _, _ = epoch_idx(data.shape[1], fs, t0, times[sel & (amps == a)], P["pre_ms"], P["post_ms"])
            if len(ia) < 4:
                continue
            ma, _ = mean_response(data[best:best + 1], ia, n_pre, n_post)
            pa, _, _ = peak_in_window(ma, n_pre, fs, P["win_ms"], P["edge_skip"])
            nm, ns = shuffled_null(data[best:best + 1], len(ia), n_pre, n_post, fs, P["win_ms"], rng, n_shuffle=60)
            za = float((abs(pa[0]) - nm[0]) / ns[0])
            amp_z.append(dict(amp=int(a), n=int(len(ia)), z=za))
            if knee is None and za >= P["knee_z"]:
                knee = int(a)
        entry.update(status=status, z=z_best, best_channel_1based=best + 1,
                     peak_uv=float(peak[best]), latency_ms=float(lat[best]),
                     artifact_edge_channels=int(edge.sum()),
                     footprint_channels=int(np.sum((z >= P["z_weak"]) & (np.abs(peak) >= 0.5 * abs(peak[best])))),
                     knee_uA=knee, amp_z=amp_z)
        per_pair.append(entry)
        footprints.append(peak * (z >= P["z_weak"]))   # signed peaks, noise-gated
        traces.append(m[best])
        if t_ms is None:
            t_ms = np.arange(-n_pre, n_post) / fs * 1e3

    F = np.array(footprints)                              # [pairs, ch]
    resp = [e for e in per_pair if e.get("status") == "RESPONSIVE"]
    live = [i for i, e in enumerate(per_pair) if e.get("status") in ("RESPONSIVE", "WEAK")]
    if len(live) >= 1:
        Fl = F[live]
        norms = np.linalg.norm(Fl, axis=1, keepdims=True) + 1e-12
        C = (Fl / norms) @ (Fl / norms).T
        sv = np.linalg.svd(Fl / norms, compute_uv=False)
        sv = sv / (sv[0] + 1e-30)
        eff_rank = int(np.sum(sv >= P["rank_thresh"]))
    else:
        C = np.zeros((0, 0)); sv = np.array([]); eff_rank = 0
    n_resp = len(resp)
    if n_resp >= 2 and eff_rank >= 2:
        verdict = "GO"
    elif n_resp >= 1:
        verdict = "MARGINAL"
    else:
        verdict = "NO-GO"
    silent = [e["pair"] for e in per_pair if e.get("status") in ("SILENT", "NO DATA")]
    hint = ""
    if verdict == "NO-GO":
        hint = ("no pair evokes cortex at >= %g uA -> stim array not coupled to the recorded S1 "
                "(check current flow via artifact; if present, reposition: AP/ML, not depth alone)" % min_amp)
    elif verdict == "MARGINAL" and n_resp >= 2:
        hint = "responsive pairs share ONE footprint (eff rank 1) -> control will be rank-1; consider re-seating for spread"
    elif verdict == "MARGINAL":
        hint = "one responsive pair only -> usable for rank-1 control; reposition for more if time allows"
    if silent:
        short = [p for p in silent if PAIR_LENGTH_MM.get(p, 8) < 8.0]
        long_ = [p for p in silent if PAIR_LENGTH_MM.get(p, 8) >= 8.0]
        parts = []
        if short:
            parts.append("short-tip pairs %s silent" % short)
        if long_:
            parts.append("8 mm pairs %s silent" % long_)
        hint = (hint + "; " if hint else "") + ", ".join(parts)

    res = dict(mode="thalamic", block=os.path.basename(block_dir), verdict=verdict,
               min_amp=min_amp, n_probes=int(len(times)), n_channels=int(n_ch),
               n_responsive=n_resp, n_weak=len(live) - n_resp, silent_pairs=silent,
               eff_rank=eff_rank, sv=[float(v) for v in sv],
               footprint_corr=C.tolist(), live_pairs=[per_pair[i]["pair"] for i in live],
               per_pair=per_pair, hint=hint, thresholds=P)

    # ---- figure ---------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2), width_ratios=[1.2, 1.0, 1.4])
    ax = axes[0]
    zs = [e.get("z", 0.0) for e in per_pair]
    cols = [{"RESPONSIVE": "#2a78d6", "WEAK": "#eda100"}.get(e.get("status"), "#c3c2b7") for e in per_pair]
    bars = ax.bar([str(e["pair"]) for e in per_pair], zs, color=cols, width=0.65)
    for b, e in zip(bars, per_pair):
        lab = "ch%s" % e.get("best_channel_1based", "-")
        if e.get("knee_uA"):
            lab += "\nknee %d" % e["knee_uA"]
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.3, lab, ha="center", fontsize=7)
    ax.axhline(P["z_resp"], color="#52514e", lw=0.8, ls="--")
    ax.axhline(P["z_weak"], color="#898781", lw=0.8, ls=":")
    ax.set_xlabel("stim pair (word)"); ax.set_ylabel("evoked z (amp >= %g uA)" % min_amp)
    ax.set_title("per-pair response")
    ax = axes[1]
    if C.size:
        im = ax.imshow(C, cmap="RdBu_r", vmin=-1, vmax=1)
        labs = [str(per_pair[i]["pair"]) for i in live]
        ax.set_xticks(range(len(live)), labs); ax.set_yticks(range(len(live)), labs)
        fig.colorbar(im, ax=ax, shrink=0.8, label="footprint corr")
    ax.set_title("footprint similarity, eff rank %d" % eff_rank)
    ax = axes[2]
    if t_ms is not None:
        for e, trc in zip(per_pair, traces):
            if trc is None:
                continue
            ax.plot(t_ms, trc, lw=1.2, label="p%d ch%d" % (e["pair"], e["best_channel_1based"]),
                    alpha=1.0 if e["status"] == "RESPONSIVE" else 0.5)
        ax.axvspan(P["win_ms"][0], P["win_ms"][1], color="#e1e0d9", alpha=0.5, lw=0)
        ax.axvline(0, color="#52514e", lw=0.8, ls="--")
        ax.legend(frameon=False, fontsize=7, ncols=2)
    ax.set_xlabel("ms from pulse"); ax.set_ylabel("uV")
    ax.set_title("best-channel signed averages")
    fig.suptitle("THALAMIC GATE: %s  --  %s | %d responsive / %d weak / %d silent, eff rank %d%s"
                 % (verdict, res["block"], n_resp, len(live) - n_resp, len(silent), eff_rank,
                    (" | " + hint) if hint else ""),
                 fontsize=10, color={"GO": "#1b7a3a", "MARGINAL": "#b8860b", "NO-GO": "#b3413a"}[verdict])
    fig.tight_layout()
    return res, fig


# --------------------------------------------------------------------------
def print_summary(res):
    print("=" * 78)
    if res["mode"] == "cortical":
        print("CORTICAL GATE: %s   block %s   (%d thwacks, %d ch)"
              % (res["verdict"], res["block"], res["n_trials"], res["n_channels"]))
        print("  best ch%-3d  %+7.0f uV @ %4.0f ms   z %5.1f   split-half %.2f   half-max footprint %d ch"
              % (res["best_channel_1based"], res["best_peak_uv"], res["best_latency_ms"],
                 res["best_z"], res["split_half"], res["footprint_channels"]))
        print("  top-5: " + "  ".join("ch%d z%.0f %+.0fuV@%.0fms" % (t["ch"], t["z"], t["peak_uv"], t["lat_ms"])
                                     for t in res["top5"]))
        if res["reasons"]:
            print("  short of GO because: " + "; ".join(res["reasons"]))
    else:
        print("THALAMIC GATE: %s   block %s   (%d probes >= any amp, %d ch, min-amp %g)"
              % (res["verdict"], res["block"], res["n_probes"], res["n_channels"], res["min_amp"]))
        print("  pair  tip   status      z    best  peak(uV) lat(ms) knee(uA)  n")
        for e in res["per_pair"]:
            print("  %4d  %3.1f  %-10s %5.1f  ch%-3s %+8.0f %7.1f %8s %4d"
                  % (e["pair"], e.get("tip_mm") or 0, e["status"], e.get("z", 0),
                     e.get("best_channel_1based", "-"), e.get("peak_uv", 0), e.get("latency_ms", 0),
                     e.get("knee_uA") if e.get("knee_uA") else "-", e["n_trials"]))
        print("  responsive %d, weak %d, silent %s, footprint eff rank %d (sv %s)"
              % (res["n_responsive"], res["n_weak"], res["silent_pairs"], res["eff_rank"],
                 ", ".join("%.2f" % v for v in res["sv"][:4])))
    if res["hint"]:
        print("  ADJUST: " + res["hint"])
    print("=" * 78)


def run_one(mode, block, args, plt):
    block_dir = resolve_block_dir(block)
    name = os.path.basename(os.path.normpath(block_dir))
    out_dir = os.path.join(args.out_root, name)
    os.makedirs(out_dir, exist_ok=True)
    chmap = list(range(1, 65))
    if args.map:
        chmap = json.load(open(args.map))
    try:
        if mode == "cortical":
            res, fig = gate_cortical(block_dir, args.n_channels, chmap, args.blacklist, out_dir, plt)
        else:
            res, fig = gate_thalamic(block_dir, args.n_channels, args.min_amp, args.blacklist,
                                     args.t_min, out_dir, plt)
    except RuntimeError as exc:
        return fail(str(exc)), None
    png = os.path.join(out_dir, "gate_%s.png" % mode)
    fig.savefig(png, dpi=150)
    plt.close(fig)
    res["png"] = png
    with open(os.path.join(out_dir, "gate_%s.json" % mode), "w") as f:
        json.dump(res, f, indent=1)
    print_summary(res)
    print("  figure: %s" % png)
    return EXIT[res["verdict"]], res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=["cortical", "thalamic", "both"])
    ap.add_argument("--block", help="block dir (cortical or thalamic single mode)")
    ap.add_argument("--newest", action="store_true", help="use the newest block under --data-root")
    ap.add_argument("--cortical", help="thwack block dir (mode both)")
    ap.add_argument("--thalamic", help="probe block dir (mode both)")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--n-channels", type=int, default=0, help="keep first N Wav1 channels")
    ap.add_argument("--blacklist", type=int, nargs="*", default=[], help="1-based channels to zero")
    ap.add_argument("--map", default=None, help="JSON list of 64 channel numbers in grid order")
    ap.add_argument("--min-amp", type=float, default=13.0, help="thalamic: pooled amps >= this (uA)")
    ap.add_argument("--t-min", type=float, default=None, help="thalamic: ignore probes before t (s)")
    ap.add_argument("--out-root", default=os.path.join(REPO, "galleries"))
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titleweight": "bold"})

    if args.mode == "both":
        if not (args.cortical and args.thalamic):
            return fail("--mode both needs --cortical and --thalamic block dirs")
        rc1, _ = run_one("cortical", args.cortical, args, plt)
        rc2, _ = run_one("thalamic", args.thalamic, args, plt)
        return max(rc1, rc2)
    block = args.block
    if args.newest:
        block = newest_block_dir(args.data_root)
        print("newest block: %s" % block)
    if not block or not os.path.isdir(block):
        return fail("block directory not found: %s" % block)
    rc, _ = run_one(args.mode, block, args, plt)
    return rc


if __name__ == "__main__":
    sys.exit(main())
