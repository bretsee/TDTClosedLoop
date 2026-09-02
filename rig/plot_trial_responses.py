#!/usr/bin/env python
"""plot_trial_responses.py -- per-trial response gallery for one TDT block.

    python rig/plot_trial_responses.py --block <dir> --mode thwack [--n-channels 32]
    python rig/plot_trial_responses.py --block <dir> --mode probe [--t-min <s>]
    python rig/plot_trial_responses.py --block <dir> --mode arm --schedule <schedule.json>

The every-block sanity check: epoch Wav1 around the block's trial onsets and
LOOK at them before trusting any downstream number. Modeled on the results
deck's template-gallery slide. Onset source per mode:

  thwack  rising edges of the nThw float32 stream (0/high digital waveform
          @ ~24414 Hz, threshold 0.5); pulses narrower than --min-pulse-ms
          (default 50) are rejected as glitches. One group.
  probe   rising edges per UDP1 scalar word (8 words = stim pairs); the
          amplitude is the word's value at the edge. Groups = pair x amp.
          --t-min drops probes at or before that block time (skip warm-up).
  arm     the schedule JSON's events: onset_tick k -> UDP1.ts[k-1] (UDP1
          carries one scalar sample per loop tick). Groups = schedule site.

Every trial is a [-40, +200 ms] Wav1 epoch, baseline-subtracted on the pre
window. Channel count (32 or 64) comes from the data shape; --n-channels
keeps only the first N rows when the block carries more.

Outputs to galleries/<block_name>/ (repo root; override --out-root):
  <group>_mean.png    mean heatmap (ch x time, RdBu_r centered on 0) +
                      best-channel trace (single trials grey, mean green)
  <group>_stack.png   trial stack for the best channel (trials x time)
  index.png           contact sheet of all group heatmaps (probe: pair rows
                      x amp columns)
  stats.json          per group: n trials, peak uV, latency ms, best channel
                      (1-based), split-half corr

Prints a one-line summary per group. Exit 1 only on load/trigger failures
(missing store, flat nThw, zero onsets); a noisy template is a RESULT.
"""

import argparse
import json
import os
import sys

import numpy as np

PRE_S = 0.04
POST_S = 0.20
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GREEN, GREY, RED, AMBER = "#3F7A4E", "#5B6470", "#B3413A", "#C9A23A"


def fail(msg):
    print("FAIL: %s" % msg)
    return 1


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 10,
        "text.color": "black",
        "axes.labelcolor": "black",
        "axes.edgecolor": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        "axes.titlecolor": "black",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 200,
        "savefig.dpi": 200,
    })
    return plt


def resolve_block_dir(p):
    """TDT blocks sometimes nest one directory level (dir contains one dir with
    the actual .tsq/.tev). Return whichever level holds the .tsq."""
    import glob
    if glob.glob(os.path.join(p, "*.tsq")):
        return p
    kids = [os.path.join(p, k) for k in os.listdir(p)
            if os.path.isdir(os.path.join(p, k))
            and glob.glob(os.path.join(p, k, "*.tsq"))]
    if len(kids) == 1:
        return kids[0]
    return p  # let the tdt reader produce its own error


def read_block(path, stores):
    import tdt
    try:
        blk = tdt.read_block(path, store=list(stores))
        # store-filtered read can silently miss scalars on some tdt versions
        if all(_find_store(blk, s) is not None for s in stores):
            return blk
    except Exception as exc:  # noqa: BLE001
        print("note: filtered read failed (%s); reading full block"
              % type(exc).__name__)
    return tdt.read_block(path)


def _find_store(blk, name):
    """Return the store struct for `name` from streams/scalars/epocs, or None.
    NB: tdt.StructType membership is broken -- always test against .keys()."""
    for grp in ("streams", "scalars", "epocs"):
        g = getattr(blk, grp, None)
        if g is not None and name in list(g.keys()):
            return g[name]
    return None


def wav1_uv(blk):
    """Wav1 as (n_ch, n_samp) float64 in uV, plus fs and stream start time."""
    s = _find_store(blk, "Wav1")
    if s is None:
        raise SystemExit(fail("Wav1 stream not found in block"))
    d = np.asarray(s.data, dtype=np.float64)
    if d.ndim == 1:
        d = d[None, :]
    if not np.any(d):
        raise SystemExit(fail("Wav1 is ALL ZERO -- Wav1 disk saving is OFF in "
                              "Synapse (the 2026-08-18 failure)."))
    max_abs = float(np.max(np.abs(d)))
    branch = "uV (as stored)"
    if max_abs < 0.1:  # early-rig heuristic: volts on disk
        d *= 1e6
        branch = "volts->uV (x1e6)"
    print("Wav1:    %d ch @ %.4f Hz, max|x| %.4g -> %s"
          % (d.shape[0], float(s.fs), max_abs, branch))
    return d, float(s.fs), float(getattr(s, "start_time", 0.0))


def thwack_onsets(blk, min_pulse_ms):
    """Onset times (s) from the nThw digital stream: 0.5-threshold rising
    edges, pulses narrower than min_pulse_ms rejected."""
    s = _find_store(blk, "nThw")
    if s is None:
        raise SystemExit(fail("nThw not found in block -- is the thwacker "
                              "digital line wired and enabled in Synapse?"))
    if hasattr(s, "onset"):  # epoc form, if the circuit ever saves it that way
        on = np.asarray(s.onset, dtype=np.float64)
        print("nThw:    epoc store, %d onsets" % len(on))
        return on
    d = np.asarray(s.data, dtype=np.float64).ravel()
    fs = float(s.fs)
    t0 = float(getattr(s, "start_time", 0.0))
    if float(d.max()) <= float(d.min()):
        raise SystemExit(fail("nThw stream is FLAT at %g -- the thwacker never "
                              "pulsed (not running, or line not reaching the "
                              "RZ2)." % float(d.min())))
    b = d > 0.5
    rise = np.flatnonzero(~b[:-1] & b[1:]) + 1
    fall = np.flatnonzero(b[:-1] & ~b[1:]) + 1
    if len(fall) and len(rise) and fall[0] < rise[0]:
        fall = fall[1:]  # started high mid-pulse
    n = min(len(rise), len(fall))
    width_ms = (fall[:n] - rise[:n]) / fs * 1000.0
    keep = width_ms >= min_pulse_ms
    n_glitch = int(np.count_nonzero(~keep))
    if n_glitch:
        print("WARN:    %d pulse(s) narrower than %g ms rejected as glitches"
              % (n_glitch, min_pulse_ms))
    on = t0 + rise[:n][keep] / fs
    print("nThw:    stream @ %.1f Hz, %d pulses kept" % (fs, len(on)))
    return on


def probe_events(blk, t_min):
    """(times, pairs, amps) from UDP1 scalar rising edges, one word per pair."""
    u = _find_store(blk, "UDP1")
    if u is None:
        raise SystemExit(fail("UDP1 scalar store not found -- was the loop "
                              "server running during this block?"))
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
            t = ts[i]
            if t_min is not None and t <= t_min:
                continue
            pairs.append(r + 1)
            amps.append(float(np.max(v[i:i + 4])))
            times.append(t)
    if not times:
        raise SystemExit(fail("zero UDP1 rising edges%s -- no probes in this "
                              "block?" % (" after --t-min %g s" % t_min
                                          if t_min is not None else "")))
    pairs, amps, times = map(np.asarray, (pairs, amps, times))
    order = np.argsort(times)
    print("UDP1:    %d words x %d ticks, %d probe edges" %
          (dd.shape[0], dd.shape[1], len(times)))
    return times[order], pairs[order], np.round(amps[order]).astype(int)


def arm_events(blk, schedule_path):
    """(times, sites, site_order) from schedule onset_ticks via UDP1.ts."""
    u = _find_store(blk, "UDP1")
    if u is None:
        raise SystemExit(fail("UDP1 scalar store not found -- arm mode needs "
                              "the loop's tick timestamps"))
    ts = np.asarray(u.ts).ravel()
    with open(schedule_path) as f:
        sch = json.load(f)
    times, sites = [], []
    n_out = 0
    for e in sch["events"]:
        k = int(e["onset_tick"]) - 1
        if k < 0 or k >= ts.size:
            n_out += 1
            continue
        times.append(ts[k])
        sites.append(e["site"])
    if n_out:
        print("WARN:    %d schedule event(s) outside the block's %d UDP1 ticks"
              % (n_out, ts.size))
    if not times:
        raise SystemExit(fail("no schedule event landed inside the block's "
                              "%d UDP1 ticks -- wrong schedule for this "
                              "block?" % ts.size))
    site_order = [s for s in sch.get("sites", []) if s in sites]
    site_order += [s for s in dict.fromkeys(sites) if s not in site_order]
    print("sched:   %s -> %d events on %d ticks, sites %s"
          % (os.path.basename(schedule_path), len(times), ts.size, site_order))
    return np.asarray(times), np.asarray(sites), site_order


def epoch(data, fs, t0_stream, onset_times):
    """(trials [n_tr, n_ch, n_pre+n_post], n_pre, kept mask); baseline (pre
    window mean) subtracted per trial per channel."""
    n_pre = int(round(PRE_S * fs))
    n_post = int(round(POST_S * fs))
    n_ch, n_samp = data.shape
    trials, kept = [], []
    for t in onset_times:
        i0 = int(round((t - t0_stream) * fs))
        a, b = i0 - n_pre, i0 + n_post
        if a < 0 or b > n_samp:
            kept.append(False)
            continue
        trials.append(data[:, a:b])
        kept.append(True)
    kept = np.asarray(kept, bool)
    if not trials:
        return np.zeros((0, n_ch, n_pre + n_post)), n_pre, kept
    trials = np.array(trials)
    trials -= trials[:, :, :n_pre].mean(axis=2, keepdims=True)
    return trials, n_pre, kept


def group_stats(trials, n_pre, fs):
    """(mean [ch x t], best_ch0, peak_uv, latency_ms, split_half)."""
    m = trials.mean(axis=0)
    post = np.abs(m[:, n_pre:])
    best = int(np.argmax(post.max(axis=1)))
    pk_i = int(np.argmax(post[best]))
    peak = float(m[best, n_pre + pk_i])
    lat_ms = pk_i / fs * 1000.0
    shc = float("nan")
    if len(trials) >= 4:
        idx = np.random.default_rng(0).permutation(len(trials))
        h = len(idx) // 2
        a = trials[idx[:h]].mean(0).ravel()
        b = trials[idx[h:2 * h]].mean(0).ravel()
        shc = float(np.corrcoef(a, b)[0, 1])
    return m, best, peak, lat_ms, shc


def heatmap(ax, m, t_ms, vmax):
    im = ax.imshow(m, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   extent=[t_ms[0], t_ms[-1], m.shape[0] + 0.5, 0.5],
                   interpolation="nearest")
    ax.axvline(0, color=GREY, lw=0.6, ls="--")
    ax.spines["top"].set_visible(True)   # imshow panels keep a closed frame
    ax.spines["right"].set_visible(True)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", required=True,
                    help="TDT block directory (one-level nesting handled)")
    ap.add_argument("--mode", required=True, choices=["thwack", "probe", "arm"])
    ap.add_argument("--schedule", default=None,
                    help="schedule JSON (required for --mode arm)")
    ap.add_argument("--n-channels", type=int, default=0,
                    help="keep only the first N Wav1 channels (default: all)")
    ap.add_argument("--t-min", type=float, default=None,
                    help="probe mode: drop probes at or before this block time (s)")
    ap.add_argument("--min-pulse-ms", type=float, default=50.0,
                    help="thwack mode: reject nThw pulses narrower than this "
                         "(default %(default)s)")
    ap.add_argument("--out-root", default=os.path.join(REPO, "galleries"),
                    help="gallery root (default <repo>/galleries)")
    args = ap.parse_args()

    if args.mode == "arm" and not args.schedule:
        return fail("--mode arm requires --schedule <schedule.json>")
    if args.schedule and not os.path.isfile(args.schedule):
        return fail("schedule not found: %s" % args.schedule)
    if not os.path.isdir(args.block):
        return fail("block directory not found: %s" % args.block)

    block_dir = resolve_block_dir(args.block)
    block_name = os.path.basename(os.path.normpath(block_dir))
    print("block:   %s   mode: %s" % (block_dir, args.mode))

    stores = {"thwack": ("Wav1", "nThw"),
              "probe": ("Wav1", "UDP1"),
              "arm": ("Wav1", "UDP1")}[args.mode]
    blk = read_block(block_dir, stores)
    wav, fs, t0 = wav1_uv(blk)
    if args.n_channels and wav.shape[0] > args.n_channels:
        print("NOTE:    keeping the first %d of %d Wav1 channels"
              % (args.n_channels, wav.shape[0]))
        wav = wav[:args.n_channels]

    # ---- onsets + grouping -------------------------------------------------
    if args.mode == "thwack":
        times = thwack_onsets(blk, args.min_pulse_ms)
        labels = np.array(["thwack"] * len(times))
        order = ["thwack"]
    elif args.mode == "probe":
        times, pairs, amps = probe_events(blk, args.t_min)
        labels = np.array(["pair%d_amp%02d" % (p, a)
                           for p, a in zip(pairs, amps)])
        order = sorted(set(labels.tolist()))
    else:
        times, sites, order = arm_events(blk, args.schedule)
        labels = sites

    trials, n_pre, kept = epoch(wav, fs, t0, times)
    if trials.shape[0] == 0:
        return fail("no onset had a full [-40, +200 ms] window inside Wav1")
    labels = labels[kept]
    n_drop = int(np.count_nonzero(~kept))
    if n_drop:
        print("WARN:    %d trial(s) dropped (window ran off the recording)" % n_drop)
    t_ms = (np.arange(trials.shape[2]) - n_pre) / fs * 1000.0

    out_dir = os.path.join(args.out_root, block_name)
    os.makedirs(out_dir, exist_ok=True)
    plt = style()

    # ---- per-group figures + stats ----------------------------------------
    stats = {"block": block_name, "block_path": block_dir, "mode": args.mode,
             "fs": round(fs, 4), "n_channels": int(wav.shape[0]),
             "n_trials_total": int(trials.shape[0]), "groups": {}}
    means = {}
    for g in order:
        tr = trials[labels == g]
        if tr.shape[0] == 0:
            print("%-14s  no trials -- skipped" % g)
            continue
        m, best, peak, lat_ms, shc = group_stats(tr, n_pre, fs)
        means[g] = (m, best)
        stats["groups"][g] = {
            "n_trials": int(tr.shape[0]),
            "peak_uv": round(peak, 1),
            "latency_ms": round(lat_ms, 1),
            "best_channel_1based": best + 1,
            "split_half_corr": round(shc, 3) if shc == shc else None,
        }
        print("%-14s  n %3d   peak %+8.1f uV @ %5.1f ms   best ch %2d   "
              "split-half %s" % (g, tr.shape[0], peak, lat_ms, best + 1,
                                 "%.3f" % shc if shc == shc else "-"))

        vmax = max(float(np.percentile(np.abs(m), 99.5)), 1e-9)
        fig, (axh, axt) = plt.subplots(1, 2, figsize=(9, 3.4),
                                       gridspec_kw={"width_ratios": [1.2, 1]})
        im = heatmap(axh, m, t_ms, vmax)
        fig.colorbar(im, ax=axh, label="uV", fraction=0.046, pad=0.03)
        axh.set(xlabel="time from onset (ms)", ylabel="channel",
                title="%s  n=%d  mean" % (g, tr.shape[0]))
        for row in tr[:, best, :]:
            axt.plot(t_ms, row, color=GREY, lw=0.3, alpha=0.25)
        axt.plot(t_ms, m[best], color=GREEN, lw=1.4)
        axt.axvline(0, color=GREY, lw=0.6, ls="--")
        axt.set(xlabel="time from onset (ms)", ylabel="uV",
                title="ch %d  peak %+.0f uV @ %.0f ms" % (best + 1, peak, lat_ms))
        fig.suptitle("%s  [%s]" % (block_name, args.mode), y=1.02, fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "%s_mean.png" % g),
                    bbox_inches="tight")
        plt.close(fig)

        stack = tr[:, best, :]
        vs = max(float(np.percentile(np.abs(stack), 99)), 1e-9)
        fig, ax = plt.subplots(figsize=(6, 3.4))
        im = ax.imshow(stack, aspect="auto", cmap="RdBu_r", vmin=-vs, vmax=vs,
                       extent=[t_ms[0], t_ms[-1], stack.shape[0] + 0.5, 0.5],
                       interpolation="nearest")
        ax.axvline(0, color=GREY, lw=0.6, ls="--")
        ax.spines["top"].set_visible(True)
        ax.spines["right"].set_visible(True)
        fig.colorbar(im, ax=ax, label="uV", fraction=0.046, pad=0.03)
        ax.set(xlabel="time from onset (ms)", ylabel="trial",
               title="%s  ch %d  trial stack (n=%d)" % (g, best + 1, len(stack)))
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "%s_stack.png" % g),
                    bbox_inches="tight")
        plt.close(fig)

    if not means:
        return fail("no group had any trials")

    # ---- index contact sheet ----------------------------------------------
    keys = [g for g in order if g in means]
    if args.mode == "probe":
        prs = sorted({k.split("_")[0] for k in keys})
        ams = sorted({k.split("_")[1] for k in keys})
        n_r, n_c = len(prs), len(ams)
        pos = {k: (prs.index(k.split("_")[0]), ams.index(k.split("_")[1]))
               for k in keys}
    else:
        n_c = min(5, len(keys))
        n_r = (len(keys) + n_c - 1) // n_c
        pos = {k: (i // n_c, i % n_c) for i, k in enumerate(keys)}
    vall = max(max(float(np.percentile(np.abs(m), 99.5))
                   for m, _ in means.values()), 1e-9)
    fig, axes = plt.subplots(n_r, n_c, figsize=(2.1 * n_c + 0.6, 1.7 * n_r + 0.7),
                             squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for k in keys:
        r, c = pos[k]
        ax = axes[r][c]
        ax.axis("on")
        heatmap(ax, means[k][0], t_ms, vall)
        s = stats["groups"][k]
        ax.set_title("%s  n=%d  %+.0fuV ch%d" %
                     (k, s["n_trials"], s["peak_uv"], s["best_channel_1based"]),
                     fontsize=7)
        ax.set_xticks([]), ax.set_yticks([])
    fig.suptitle("%s  [%s]  mean responses, shared scale +-%.0f uV"
                 % (block_name, args.mode, vall), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(out_dir, "index.png"), bbox_inches="tight")
    plt.close(fig)

    with open(os.path.join(out_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("\nwrote:   %s  (%d group PNG pairs + index.png + stats.json)"
          % (out_dir, len(keys)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
