"""art64_01: per-channel stim-artifact excision window on the 64-ch array.

Pulse-triggered average (PTA) at 24 kHz on one MPC block, amplitude terciles;
window per channel = last time |PTA| (hi tercile) exceeds 3 SD of the pre-pulse
baseline, +0.2 ms, floored at 1 ms and capped at 4 ms (period 9.83 ms).
Writes analysis/cache/art64_windows.json and analysis/art64_pta.png.

    python day_2026-09-10/analysis/scripts/art64_01_windows.py [--run mpc_r1]
"""
import argparse
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art64_common as ac   # noqa: E402
import deckkit as dk        # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="mpc_r1")
    args = ap.parse_args()
    w2, pl, scl, fs, U, ts = ac.read_hi(args.run)
    idx = ac.pulse_onsets(pl)
    amps = ac.pulse_amps(scl, idx, fs)
    pre = int(round(0.005 * fs))
    post = int(round(0.0095 * fs))
    ok = (idx > pre) & (idx < w2.shape[1] - post) & (amps > 0)
    idx, amps = idx[ok], amps[ok]
    print(f"{args.run}: {idx.size} stim pulses, amp {amps.min():.1f}-{amps.max():.1f} uA, "
          f"record {w2.shape[1] / fs:.1f} s, {w2.shape[0]} ch")
    q = np.quantile(amps, [1 / 3, 2 / 3])
    tlab = np.digitize(amps, q)
    t_ms = (np.arange(-pre, post) / fs) * 1e3
    C = w2.shape[0]
    ptas = np.zeros((3, C, pre + post), np.float64)
    for t in range(3):
        sel = idx[tlab == t]
        acc = np.zeros((C, pre + post), np.float64)
        for i in sel[:4000]:
            acc += w2[:, i - pre:i + post]
        ptas[t] = acc / min(sel.size, 4000)
        ptas[t] -= ptas[t][:, t_ms < -1.0].mean(axis=1, keepdims=True)
    # The carrier latches ~1 ms after the Plse edge, so the artifact (a ~0.5 ms biphasic
    # spike) sits at +0.8..+1.3 ms and the evoked response follows from ~2 ms. A baseline-SD
    # criterion ran out to the 4 ms cap on most channels (first pass): it excised physiology.
    # Window = [first .. last] sample around the artifact PEAK where |PTA| exceeds
    # max(10 % of the peak, 3 SD of the pre-pulse baseline), padded 0.15 ms before / 0.2 ms
    # after, floored at +-0.3 ms about the peak and capped at -0.8 / +0.9 ms.
    windows = np.zeros(C)
    starts = np.zeros(C)
    peaks_ms = np.zeros(C)
    base_sd = ptas[2][:, t_ms < -1.0].std(axis=1)
    for ch in range(C):
        x = np.abs(ptas[2][ch])
        srch = (t_ms >= 0) & (t_ms <= 3.0)
        k = int(np.flatnonzero(srch)[np.argmax(x[srch])])
        tp, amp = float(t_ms[k]), float(x[k])
        thr = max(0.10 * amp, 3.0 * float(base_sd[ch]))
        # the artifact is a fast biphasic spike (< 0.7 ms); the evoked response that follows
        # from ~2 ms is slow and must stay: search only +-0.7 ms about the peak
        after = (t_ms > tp) & (t_ms <= tp + 0.7) & (x > thr)
        before = (t_ms < tp) & (t_ms >= tp - 0.7) & (x > thr)
        t_end = (float(t_ms[after][-1]) if after.any() else tp) + 0.2
        t_start = (float(t_ms[before][0]) if before.any() else tp) - 0.15
        t_end = min(max(t_end, tp + 0.3), tp + 0.9)
        t_start = max(min(t_start, tp - 0.3), tp - 0.8)
        windows[ch], starts[ch], peaks_ms[ch] = t_end, t_start, tp
    out = dict(run=args.run, n_pulses=int(idx.size),
               amp_terciles_uA=[float(amps.min()), float(q[0]), float(q[1]), float(amps.max())],
               window_post_ms_per_ch=windows.round(3).tolist(), window_start_ms_per_ch=starts.round(3).tolist(),
               artifact_peak_ms_per_ch=peaks_ms.round(3).tolist(), window_pre_ms=ac.PRE_MS, cap_ms=ac.CAP_MS,
               peak_artifact_uV_per_ch_hi=np.abs(ptas[2]).max(axis=1).round(1).tolist(),
               blacklist=sorted(ac.sc.BLACKLIST))
    (ac.CACHE / "art64_windows.json").write_text(__import__("json").dumps(out, indent=1), encoding="utf-8")
    print(f"artifact peak at {np.median(peaks_ms):.2f} ms (median); windows [{np.median(starts):.2f}, {np.median(windows):.2f}] ms "
          f"(median; length min {np.min(windows - starts):.2f}, max {np.max(windows - starts):.2f}); "
          f"peak artifact median {np.median(out['peak_artifact_uV_per_ch_hi']):.0f} uV")
    with dk.deck_style() as plt:
        fig, axes = dk.new_fig("FULL", 1, 2, gridspec_kw=dict(width_ratios=[1.5, 1]))
        ax = axes[0]
        for ch in range(C):
            if (ch + 1) in ac.sc.BLACKLIST:
                continue
            ax.plot(t_ms, ptas[2][ch], color=dk.MUTED, lw=0.5, alpha=0.6)
        ax.plot(t_ms, ptas[2][ac.CH - 1], color=dk.COLOR["mpc"], lw=1.6, label=f"ch{ac.CH}")
        ax.axvspan(float(starts[ac.CH - 1]), float(windows[ac.CH - 1]), color=dk.COLOR["stim"], alpha=0.15, label="excised (ch64)")
        ax.set_xlim(-2, 8)
        ax.set_xlabel("time from pulse (ms)")
        ax.set_ylabel("PTA (uV), high-amplitude tercile")
        ax.set_title(f"{args.run}: pulse-triggered average, {C} ch")
        ax.legend()
        ax = axes[1]
        ax.bar(np.arange(1, C + 1), windows - starts, bottom=starts, color=dk.COLOR["stim"], width=0.8)
        ax.set_xlabel("channel")
        ax.set_ylabel("excised interval after the Plse edge (ms)")
        ax.set_title("per-channel window around the artifact peak")
        dk.save_fig(fig, ac.ANA / "art64_pta.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
