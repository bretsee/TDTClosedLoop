#!/usr/bin/env python
"""assess_artifact.py -- quantify stimulus artifact in a recorded block.

    python rig/assess_artifact.py --block <tdt_inner_block_dir> [--store Wav1]
        [--events probe|pulse]

The control loop has NO artifact blanking or rejection anywhere: the feature is
a plain mean(|x|) (or signed mean) over the newest window samples. The only
structural mitigations are (a) window = whole stim-carrier periods, which turns
a phase-locked artifact into a constant offset, and (b) DC/mean removal in the
fitters. This script measures whether that is enough.

Event sources:
  probe   command onsets (Scle rising edges, UDP1 fallback) -- for single-pulse
          probe blocks (long gaps, one carrier pulse per command tick)
  pulse   every physical carrier pulse (Plse rising edges), amplitude looked up
          from Scle at the pulse time -- for envelope/continuous-carrier blocks
          (e.g. the 2026-08-12 saw block where Scle never returns to zero
          between pulses). Default epoch shrinks to one carrier period.

Per (stim word, recorded channel):
  waveform    trial-averaged stim-locked epoch; artifact peak vs noise, std
              ratio (post-event window vs QUIET-SEGMENT baseline -- samples
              with all Scle words at zero, +/-20 ms margin -- falling back to
              the pre-event window when the record has no quiet span), width in
              samples/ms (3-sigma crossings), decay tau, high-frequency (>150
              Hz) power fraction
  feature     the epoch rebinned into loop ticks aligned at the event: the
              feature the controller would see at ticks 0..3, with and without
              trimming the K largest-|x| samples per window (the exact rule of
              the optional --feature-trim K loop flag), and the fraction of the
              tick-0 feature deflection attributable to the trimmed samples
  blanking    width <= 1 sample at ~610 Hz is consistent with upstream
              (circuit) blanking a la Choi 2016's 480 us sample-and-hold;
              >= 2 samples means no hardware blanking is evident

Verdicts: ARTIFACT DOMINANT (std ratio > 10 AND trim removes > 50% of the
tick-0 deflection somewhere) / MODERATE / NEGLIGIBLE.

Caveat for in-vivo blocks: tick 0 (0..~10 ms post-pulse) contains BOTH the
artifact and the earliest neural response; the trim-K delta is an ESTIMATE of
the artifact share. Real evoked responses peak 15-28 ms = ticks 1-3.

Needs the PythonIntanAnalysis venv (tdt, numpy, matplotlib). TDT blocks nest
one level: pass the INNER directory.
"""

import argparse
import json
import sys

import numpy as np

HARD, WARN, INFO = "FAIL", "warn", "info"
FS_ACQ_NOMINAL = 610.3515625
QUIET_MARGIN_S = 0.020


def scle_matrix(d):
    st = getattr(getattr(d, "streams", None), "Scle", None)
    if st is None or np.max(np.abs(st.data)) <= 1e-9:
        return None, None
    return np.atleast_2d(st.data), float(st.fs)


def probe_events(d, min_amp):
    """Command onsets: Scle rising edges per word; UDP1 scalar fallback."""
    events = []
    S, fs = scle_matrix(d)
    if S is not None:
        for w in range(S.shape[0]):
            x = S[w]
            on = np.flatnonzero((x[1:] > 1e-9) & (x[:-1] <= 1e-9)) + 1
            events += [(i / fs, w, float(x[i])) for i in on if x[i] >= min_amp]
        if events:
            return sorted(events), "Scle onsets"
    sc = getattr(getattr(d, "scalars", None), "UDP1", None)
    if sc is not None:
        U, ts = sc.data, sc.ts
        for w in range(U.shape[0]):
            x = U[w]
            on = np.flatnonzero((x[1:] > 1e-9) & (x[:-1] <= 1e-9)) + 1
            if x[0] > 1e-9:
                on = np.r_[0, on]
            events += [(float(ts[i]), w, float(x[i])) for i in on if x[i] >= min_amp]
        if events:
            return sorted(events), "UDP1 onsets"
    return [], None


def pulse_events(d, min_amp):
    """Every physical carrier pulse (Plse), amplitude from Scle at pulse time."""
    st = getattr(getattr(d, "streams", None), "Plse", None)
    S, fsS = scle_matrix(d)
    if st is None or S is None:
        return [], None
    P, fsP = st.data, float(st.fs)
    pk = float(np.max(np.abs(P)))
    if pk <= 0:
        return [], None
    rise = np.flatnonzero((P[1:] > 0.5 * pk) & (P[:-1] <= 0.5 * pk)) + 1
    events = []
    for i in rise:
        t = i / fsP
        j = min(S.shape[1] - 1, int(t * fsS))
        w = int(np.argmax(np.abs(S[:, j])))
        a = float(S[w, j])
        if a >= min_amp and a > 1e-9:
            events.append((t, w, a))
    return events, "Plse pulses (amp from Scle)"


def quiet_std(x, fs, S, fsS, n_edge):
    """Per-channel std over samples where every Scle word is zero (+margin)."""
    if S is None:
        return None
    active = np.max(np.abs(S), axis=0) > 1e-9
    k = int(round(QUIET_MARGIN_S * fsS))
    if k > 0:
        kernel = np.ones(2 * k + 1)
        active = np.convolve(active.astype(float), kernel, mode="same") > 0
    t_idx = np.minimum((np.arange(len(x)) / fs * fsS).astype(int), len(active) - 1)
    quiet = ~active[t_idx]
    quiet[:n_edge] = quiet[len(x) - n_edge:] = False
    if quiet.sum() < 100:
        return None
    return float(x[quiet].std()), int(quiet.sum())


def epoch(x, fs, t_events, pre_s, post_s):
    pre = int(round(pre_s * fs))
    post = int(round(post_s * fs))
    out = []
    for t in t_events:
        i = int(round(t * fs))
        if i - pre < 0 or i + post >= len(x):
            continue
        out.append(x[i - pre:i + post + 1])
    return (np.array(out) if out else np.zeros((0, pre + post + 1))), pre, post


def trimmed_feature(vals, k, signed):
    v = np.asarray(vals, dtype=float)
    if k > 0 and k < len(v):
        v = v[np.argsort(np.abs(v))[:len(v) - k]]
    return float(np.mean(v) if signed else np.mean(np.abs(v)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", required=True)
    ap.add_argument("--store", default="Wav1",
                    help="recording stream to assess (default Wav1; use sOut on "
                         "blocks where Wav1 was dead, e.g. LD-260812)")
    ap.add_argument("--events", choices=["probe", "pulse"], default="probe")
    ap.add_argument("--channels", type=int, nargs="+", default=None)
    ap.add_argument("--pre-ms", type=float, default=None,
                    help="epoch pre window (default: 25 probe / 2 pulse)")
    ap.add_argument("--post-ms", type=float, default=None,
                    help="epoch post window (default: 60 probe / 7 pulse)")
    ap.add_argument("--feature-window", type=int, default=6,
                    help="loop feature window in samples of the store's rate")
    ap.add_argument("--signed", action="store_true")
    ap.add_argument("--trim-k", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--min-amp", type=float, default=0.0)
    ap.add_argument("--max-events", type=int, default=3000,
                    help="cap on epoched events (evenly subsampled)")
    ap.add_argument("--out-prefix", default=None)
    args = ap.parse_args()

    import tdt
    d = tdt.read_block(args.block, evtype=["streams", "scalars"])
    issues = []

    def note(sev, msg):
        issues.append((sev, msg))
        print("  %s: %s" % (sev, msg))

    st = getattr(d.streams, args.store, None)
    if st is None:
        print("FAIL: store %s not in block (has: %s)"
              % (args.store, sorted(k for k in vars(d.streams) if not k.startswith("_"))))
        return 1
    X, fs = np.atleast_2d(st.data), float(st.fs)
    n_ch = X.shape[0]
    chans = args.channels or list(range(1, n_ch + 1))
    if np.max(np.abs(X)) <= 1e-15:
        print("FAIL: store %s is entirely zero -- nothing to assess (PZ2 off? "
              "try --store sOut)" % args.store)
        return 1

    pre_s = (args.pre_ms if args.pre_ms is not None
             else (25.0 if args.events == "probe" else 2.0)) / 1e3
    post_s = (args.post_ms if args.post_ms is not None
              else (60.0 if args.events == "probe" else 7.0)) / 1e3

    events, src = (probe_events if args.events == "probe" else pulse_events)(d, args.min_amp)
    if not events and args.events == "probe":
        events, src = pulse_events(d, args.min_amp)
        if events:
            note(INFO, "no command onsets found; fell back to --events pulse")
    if not events:
        print("FAIL: no stim events found -- was stim delivered? "
              "(safety button / battery / routing)")
        return 1
    if len(events) > args.max_events:
        events = events[::int(np.ceil(len(events) / args.max_events))]
    words = sorted(set(w for _, w, _ in events))
    amps = np.array([a for _, _, a in events])
    print("Block: %s" % args.block)
    print("Store: %s  (%d ch @ %.4f Hz)   events: %d from %s on word(s) %s, "
          "amp %g..%g" % (args.store, n_ch, fs, len(events), src,
                          [w + 1 for w in words], amps.min(), amps.max()))
    if abs(fs - FS_ACQ_NOMINAL) > 1.0:
        note(INFO, "store fs %.1f Hz != acquisition 610.35 Hz -- waveform metrics "
                   "fine; the feature simulation bins %d samples of THIS rate, "
                   "an approximation of the loop feature" % (fs, args.feature_window))

    S, fsS = scle_matrix(d)
    w_feat = args.feature_window
    per_word = {}
    worst = {"std_ratio": 0.0, "word": None, "ch": None}
    for w in words:
        t_ev = [t for t, ww, _ in events if ww == w]
        rows = []
        for ch in chans:
            x = X[ch - 1].astype(float)
            ep, ipre, ipost = epoch(x, fs, t_ev, pre_s, post_s)
            if ep.shape[0] < 3:
                continue
            base = ep[:, :ipre]
            ep_c = ep - base.mean(axis=1, keepdims=True)
            m = ep_c.mean(axis=0)
            q = quiet_std(x, fs, S, fsS, n_edge=ipre + ipost)
            noise = q[0] if q else float(base.std())
            noise_src = "quiet" if q else "pre-window"
            sigma_mean = max(noise / np.sqrt(ep.shape[0]), 1e-15)
            post_seg = m[ipre:]
            peak = float(np.max(np.abs(post_seg)))
            # std ratio: pooled post-event samples (0..min(12 ms, post)) vs noise
            i12 = min(len(post_seg), int(round(0.012 * fs)) + 1)
            std_ratio = float(ep_c[:, ipre:ipre + i12].std()) / max(noise, 1e-15)
            # width threshold: 3-sigma of the MEAN, but never below 10% of the
            # artifact peak -- with many trials sigma_mean is microscopic and a
            # pure 3-sigma width degenerates to "the whole window"
            thr = max(3.0 * sigma_mean, 0.1 * peak) if peak > 0 else 3.0 * sigma_mean
            over = np.flatnonzero(np.abs(post_seg) > thr)
            width_samp = int(over[-1] - over[0] + 1) if len(over) else 0
            width_ms = 1e3 * width_samp / fs
            tau_ms = float("nan")
            if len(over):
                ipk = int(np.argmax(np.abs(post_seg)))
                below = np.flatnonzero(np.abs(post_seg[ipk:]) < thr)
                iend = ipk + (int(below[0]) if len(below) else len(post_seg) - ipk)
                seg = np.abs(post_seg[ipk:iend])
                if len(seg) >= 3 and np.all(seg > 0):
                    sl = np.polyfit(np.arange(len(seg)) / fs, np.log(seg), 1)[0]
                    if sl < -1e-9:
                        tau_ms = -1e3 / sl
            F = np.fft.rfft(m)
            fr = np.fft.rfftfreq(len(m), 1.0 / fs)
            pw = np.abs(F) ** 2
            hf_frac = float(pw[fr > 150.0].sum() / max(pw[1:].sum(), 1e-30))
            n_ticks_sim = min(4, (ipost + 1) // w_feat) if w_feat <= ipost + 1 else 0
            feats = {"full": [], "base": None}
            for k in args.trim_k:
                feats["trim%d" % k] = []
            if ipre >= w_feat:
                fb = [trimmed_feature(ep[i, ipre - w_feat:ipre], 0, args.signed)
                      for i in range(ep.shape[0])]
                feats["base"] = float(np.mean(fb))
            for tk in range(n_ticks_sim):
                sl0, sl1 = ipre + tk * w_feat, ipre + (tk + 1) * w_feat
                feats["full"].append(float(np.mean(
                    [trimmed_feature(ep[i, sl0:sl1], 0, args.signed)
                     for i in range(ep.shape[0])])))
                for k in args.trim_k:
                    feats["trim%d" % k].append(float(np.mean(
                        [trimmed_feature(ep[i, sl0:sl1], k, args.signed)
                         for i in range(ep.shape[0])])))
            frac = {}
            defl = ((feats["full"][0] - feats["base"])
                    if (n_ticks_sim and feats["base"] is not None) else 0.0)
            for k in args.trim_k:
                if n_ticks_sim and feats["base"] is not None and abs(defl) > 1e-15:
                    frac[k] = float(np.clip(
                        (feats["full"][0] - feats["trim%d" % k][0]) / defl, -1, 2))
                else:
                    frac[k] = float("nan")
            rows.append(dict(channel=ch, n_trials=int(ep.shape[0]),
                             own_pair=(ch in (2 * w + 1, 2 * w + 2)),
                             peak=peak, peak_over_noise=peak / max(sigma_mean, 1e-15),
                             std_ratio=std_ratio, noise_source=noise_src,
                             width_samples=width_samp, width_ms=width_ms,
                             decay_tau_ms=tau_ms, hf_power_frac=hf_frac,
                             features=feats, artifact_fraction=frac,
                             mean_epoch=m.tolist()))
            if std_ratio > worst["std_ratio"]:
                worst = {"std_ratio": std_ratio, "word": w, "ch": ch}
        per_word[w] = rows

    # ---- report ------------------------------------------------------------
    k0 = args.trim_k[0]
    print("\nper stim word, top channels by artifact std ratio "
          "(post-event window vs %s baseline).\n"
          "  Channels marked * are the stim pair's OWN electrodes (2k-1, 2k):\n"
          "  always artifact-saturated, never usable for control, and EXCLUDED\n"
          "  from the verdict -- the verdict scores the controllable channels."
          % ("quiet-segment" if S is not None else "pre-event"))
    print("  word  ch    trials  stdRatio  peak/noise  width(samp/ms)  tau_ms  "
          "hf>150Hz  tick0 full/trim%d/base  artifactFrac(k=%d)" % (k0, k0))
    dominant = moderate = False
    for w in words:
        rows = sorted(per_word[w], key=lambda r: -r["std_ratio"])
        off = [r for r in rows if not r["own_pair"]]
        own = [r for r in rows if r["own_pair"]]
        show = own[:1] + off[:3]
        for r in show:
            f = r["features"]
            t0f = f["full"][0] if f["full"] else float("nan")
            t0t = f["trim%d" % k0][0] if f["full"] else float("nan")
            fb = f["base"] if f["base"] is not None else float("nan")
            fr0 = r["artifact_fraction"][k0]
            print("  %4d  %2d%s  %6d  %8.1f  %10.1f  %6d/%5.1f  %6.1f  %8.2f  "
                  "%.3g/%.3g/%.3g  %s"
                  % (w + 1, r["channel"], "*" if r["own_pair"] else " ",
                     r["n_trials"], r["std_ratio"],
                     r["peak_over_noise"], r["width_samples"], r["width_ms"],
                     r["decay_tau_ms"], r["hf_power_frac"], t0f, t0t, fb,
                     ("%.2f" % fr0) if fr0 == fr0 else "-"))
        for r in off:
            fr0 = r["artifact_fraction"][k0]
            if r["std_ratio"] > 10 and fr0 == fr0 and fr0 > 0.5:
                dominant = True
            elif r["std_ratio"] > 3 or (fr0 == fr0 and 0.2 < fr0 <= 2):
                moderate = True
        best = off[0] if off else (rows[0] if rows else None)
        if best and best["std_ratio"] > 3:
            eq_samples = best["width_ms"] * FS_ACQ_NOMINAL / 1e3
            if eq_samples <= 1.0:
                note(INFO, "word %d: artifact width %.2f ms (<= 1 sample at 610 Hz) "
                           "at the top channel -- consistent with upstream/hardware "
                           "blanking" % (w + 1, best["width_ms"]))
            else:
                note(INFO, "word %d: artifact spans %.1f ms (~%.1f samples at "
                           "610 Hz) -- hardware blanking NOT evident (Choi 2016 "
                           "used 480 us sample-and-hold before filtering)"
                           % (w + 1, best["width_ms"], eq_samples))

    if dominant:
        verdict = "ARTIFACT DOMINANT"
        note(WARN, "artifact dominates the tick-0 feature deflection somewhere -- "
                   "recommend the loop's --feature-trim option AND verifying "
                   "whether the Synapse circuit has blanking; fit-side: treat "
                   "lag-0 'responses' as artifact (real peaks 15-28 ms)")
    elif moderate:
        verdict = "ARTIFACT MODERATE"
        note(INFO, "artifact measurable but not dominant -- whole-period window + "
                   "DC removal likely adequate; re-run this assessment on the "
                   "first in-vivo probe block before trusting lag-0 content")
    else:
        verdict = "ARTIFACT NEGLIGIBLE"

    if args.out_prefix:
        rep = dict(block=args.block, store=args.store, fs=fs, event_source=src,
                   n_events=len(events), words=[w + 1 for w in words],
                   config=dict(pre_ms=1e3 * pre_s, post_ms=1e3 * post_s,
                               feature_window=w_feat, signed=args.signed,
                               trim_k=args.trim_k, min_amp=args.min_amp,
                               events=args.events),
                   verdict=verdict,
                   worst=dict(std_ratio=worst["std_ratio"],
                              word=(worst["word"] + 1) if worst["word"] is not None else None,
                              channel=worst["ch"]),
                   worst_off_pair=max(
                       (dict(std_ratio=r["std_ratio"], word=w + 1,
                             channel=r["channel"])
                        for w in words for r in per_word[w] if not r["own_pair"]),
                       key=lambda x: x["std_ratio"], default=None),
                   per_word={str(w + 1): [{k: v for k, v in r.items()
                                           if k != "mean_epoch"}
                                          for r in per_word[w]] for w in words})
        with open(args.out_prefix + "_report.json", "w") as f:
            json.dump(rep, f, indent=1)
        print("  wrote %s_report.json" % args.out_prefix)

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ww = worst["word"] if worst["word"] is not None else words[0]
        rows = sorted(per_word[ww], key=lambda r: -r["std_ratio"])[:4]
        fig, axes = plt.subplots(2, 1, figsize=(9, 7))
        tms = (np.arange(len(rows[0]["mean_epoch"])) / fs - pre_s) * 1e3
        for r in rows:
            axes[0].plot(tms, np.array(r["mean_epoch"]) * 1e3,
                         label="ch %d (x%.0f)" % (r["channel"], r["std_ratio"]))
        axes[0].axvline(0, color="k", lw=0.7, ls="--")
        axes[0].set(xlabel="ms from stim", ylabel="mV (trial mean)",
                    title="word %d stim-locked mean epochs, %s" % (ww + 1, args.store))
        axes[0].legend(fontsize=8)
        r0 = rows[0]
        f = r0["features"]
        if f["full"]:
            keys = ["base", "full"] + ["trim%d" % k for k in args.trim_k]
            vals = [f["base"] if f["base"] is not None else np.nan,
                    f["full"][0]] + [f["trim%d" % k][0] for k in args.trim_k]
            axes[1].bar(range(len(keys)), vals,
                        color=["#777", "#c33"] + ["#39c"] * len(args.trim_k))
            axes[1].set_xticks(range(len(keys)))
            axes[1].set_xticklabels(keys)
            axes[1].set(ylabel="feature value",
                        title="tick-0 feature, worst channel %d (window=%d, %s)"
                              % (r0["channel"], w_feat,
                                 "signed" if args.signed else "mean|x|"))
        fig.tight_layout()
        fig.savefig(args.out_prefix + ".png", dpi=120)
        print("  wrote %s.png" % args.out_prefix)

    hard = sum(1 for s, _ in issues if s == HARD)
    warns = sum(1 for s, _ in issues if s == WARN)
    print("\nVERDICT: %s  (%d hard failure(s), %d warning(s), %d info)"
          % (verdict, hard, warns, len(issues) - hard - warns))
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
