"""art64_03: tracking on the artifact-cleaned feature vs the run-time feature.

Per run: Pearson r of the CLEANED rectified-mean ch64 feature against the
reference at lag 0 and best lag 0..6, same for the RAW-bandpassed feature, and
the run-time feature r0 (tracking_*.json, re-asserted by trk_common.recompute).
Per event (220-tick windows, ticks 0-2 after onset excluded): r at the event's
best lag; paired MPC-vs-Choi dr over the shared events of r1/r2/r3 (+ r1_late)
with a 5000-resample bootstrap CI and a sign-permutation p.

Writes analysis/art64_tracking.json, art64_paired.png, art64_example.png.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art64_common as ac   # noqa: E402
import deckkit as dk        # noqa: E402
import trk_common as tc     # noqa: E402

SKIP = tc.SKIP
PRE, POST = 0, 220


def load_run(run):
    z = np.load(ac.CACHE / f"art64_{run}.npz")
    u, y, r, tjson, sched = tc.load(run)              # skip applied, length n-SKIP
    k0, j0, n_cap = int(z["k0"]), int(z["j0"]), int(z["n_cap"])
    shift = j0 - k0                                   # packet index = row index + shift
    mav_c, mav_r = z["mav_clean"], z["mav_raw"]
    n = len(y) + SKIP
    rows = np.arange(SKIP, n)
    pk = rows + shift
    ok = (pk >= 0) & (pk < mav_c.shape[0])
    yc = np.full(len(rows), np.nan, np.float32); yr = yc.copy()
    yc[ok] = mav_c[pk[ok], ac.CH - 1]
    yr[ok] = mav_r[pk[ok], ac.CH - 1]
    return dict(u=u, y_feat=y, r=r, y_clean=yc, y_raw=yr, tjson=tjson, sched=sched, shift=shift, z=z)


def lagged_r(y, r, lag):
    if lag == 0:
        return ac.pearson(y, r)
    return ac.pearson(y[lag:], r[:-lag])


def best_lag(y, r):
    vals = [(lagged_r(y, r, L), L) for L in ac.LAGS]
    return max(vals, key=lambda t: (t[0] if np.isfinite(t[0]) else -9))


def per_event(d, key):
    """event -> (best masked r over lags, lag) for signal `key`."""
    y, r, sched = d[key], d["r"], d["sched"]
    period = int(sched["period_ticks"])
    keep = np.ones(period, bool); keep[ac.ART_TICKS[0]:ac.ART_TICKS[1] + 1] = False
    out = {}
    for ev in sched["events"]:
        o = int(ev["onset_tick"]) - SKIP
        if o < 0 or o + period > len(r):
            continue
        rr = r[o:o + period]
        rr = rr - rr[:25].mean()
        best = (-np.inf, None)
        for L in ac.LAGS:
            if o + L + period > len(y):
                continue
            yy = y[o + L:o + L + period]
            yy = yy - np.nanmean(yy[:25])
            v = ac.pearson(rr[keep], yy[keep])
            if np.isfinite(v) and v > best[0]:
                best = (v, L)
        if best[1] is not None:
            out[int(ev["event"])] = (best[0], best[1], ev["site"])
    return out


def main():
    res = dict(runs={}, paired={})
    data = {}
    for run in ac.RUNS:
        if not (ac.CACHE / f"art64_{run}.npz").exists():
            print(f"skip {run}: no cache")
            continue
        d = load_run(run)
        data[run] = d
        rec = tc.recompute(run)                       # anti-drift gate on the feature r0
        entry = dict(arm=d["tjson"].get("label", run).split("_")[0] if False else tc.RUNS[run][0],
                     feature_r0=rec["r0"], feature_best=rec["r_best"], feature_best_lag=rec["best_lag"],
                     shift_packets=d["shift"], n_pulses=int(d["z"]["n_pulses"]))
        for key, tag in (("y_clean", "clean"), ("y_raw", "rawbp")):
            r0 = lagged_r(d[key], d["r"], 0)
            rb, L = best_lag(d[key], d["r"])
            entry[f"{tag}_r0"] = r0; entry[f"{tag}_best"] = rb; entry[f"{tag}_best_lag"] = L
            ev = per_event(d, key)
            entry[f"{tag}_event_r_mean"] = float(np.mean([v[0] for v in ev.values()])) if ev else float("nan")
            entry[f"{tag}_n_events"] = len(ev)
        res["runs"][run] = entry
        print(f"{run:13s} feature r0 {entry['feature_r0']:+.3f}  rawbp r0 {entry['rawbp_r0']:+.3f} "
              f"(best {entry['rawbp_best']:+.3f}@{entry['rawbp_best_lag']})  clean r0 {entry['clean_r0']:+.3f} "
              f"(best {entry['clean_best']:+.3f}@{entry['clean_best_lag']})  events {entry['clean_n_events']}")

    # paired MPC vs Choi per event (cleaned, best lag per event)
    pairs = []
    for r in ("r1", "r2", "r3", "r1_late"):
        m, c = f"mpc_{r}", f"choi_{r}"
        if m not in data or c not in data:
            continue
        em, ec = per_event(data[m], "y_clean"), per_event(data[c], "y_clean")
        fm, fc = per_event(data[m], "y_raw"), per_event(data[c], "y_raw")
        for e in sorted(set(em) & set(ec)):
            if em[e][2] == "SHAM":
                continue
            pairs.append(dict(run=r, event=e, site=em[e][2], mpc=em[e][0], choi=ec[e][0], dr=em[e][0] - ec[e][0],
                              dr_raw=(fm[e][0] - fc[e][0]) if (e in fm and e in fc) else float("nan")))
    if pairs:
        d_ = np.array([p["dr"] for p in pairs]); draw = np.array([p["dr_raw"] for p in pairs])
        mean, lo, hi = ac.boot_ci(d_, seed=40)
        mr, lor, hir = ac.boot_ci(draw, seed=41)
        rng = np.random.default_rng(42)
        perm = np.abs((d_[None, :] * rng.choice([-1, 1], size=(20000, len(d_)))).mean(axis=1))
        pval = float((perm >= abs(d_.mean())).mean())
        per_run = {}
        for r in sorted(set(p["run"] for p in pairs)):
            dr = np.array([p["dr"] for p in pairs if p["run"] == r])
            m_, l_, h_ = ac.boot_ci(dr, seed=43)
            per_run[r] = dict(n=len(dr), mean_dr=m_, ci=[l_, h_], winrate=float((dr > 0).mean()))
        verdict = ("TIE" if lo <= 0 <= hi else ("MPC ahead" if lo > 0 else "Choi ahead"))
        res["paired"] = dict(n=len(d_), clean=dict(mean_dr=mean, ci=[lo, hi], p_perm=pval, winrate=float((d_ > 0).mean())),
                             rawbp=dict(mean_dr=mr, ci=[lor, hir]), per_run=per_run, verdict=verdict,
                             mean_r=dict(mpc=float(np.mean([p["mpc"] for p in pairs])), choi=float(np.mean([p["choi"] for p in pairs]))))
        print(f"PAIRED cleaned: n={len(d_)} dr={mean:+.3f} [{lo:+.3f},{hi:+.3f}] p={pval:.3f} -> {verdict}; "
              f"raw-bp dr={mr:+.3f} [{lor:+.3f},{hir:+.3f}]")
    ac.write_json("art64_tracking.json", res)

    # ---- figures ----
    with dk.deck_style() as plt:
        runs = [r for r in ac.RUNS if r in res["runs"]]
        fig, axes = dk.new_fig("FULL", 1, 2, gridspec_kw=dict(width_ratios=[1.3, 1]))
        ax = axes[0]
        x = np.arange(len(runs))
        w = 0.27
        for k, (tag, lab, col) in enumerate((("feature", "run-time feature (rectified Wav1)", dk.MUTED),
                                             ("rawbp", "raw 5-200 Hz, not cleaned", dk.INK_2),
                                             ("clean", "artifact-excised 5-200 Hz", dk.COLOR["mpc"]))):
            vals = [res["runs"][r][f"{tag}_r0"] for r in runs]
            ax.bar(x + (k - 1) * w, vals, w, color=col, label=lab)
        ax.set_xticks(x); ax.set_xticklabels(runs, rotation=35, ha="right")
        ax.set_ylabel("Pearson r at lag 0 (ch64 vs reference)")
        ax.set_title("tracking r per arm: feature vs cleaned raw LFP")
        ax.axhline(0, color=dk.AXIS, lw=0.8)
        ax.legend(loc="upper right")
        ax = axes[1]
        if pairs:
            for r, mk in (("r1", "o"), ("r2", "s"), ("r3", "^"), ("r1_late", "D")):
                sel = [p for p in pairs if p["run"] == r]
                if sel:
                    ax.scatter([p["choi"] for p in sel], [p["mpc"] for p in sel], s=14, marker=mk, alpha=0.6,
                               color=dk.COLOR["mpc"], edgecolors="none", label=f"{r} (n={len(sel)})")
            lim = (-0.5, 1.0)
            ax.plot(lim, lim, color=dk.AXIS, lw=1, ls=":")
            ax.set_xlim(lim); ax.set_ylim(lim)
            ax.set_xlabel("Choi per-event best-lag r (cleaned)")
            ax.set_ylabel("MPC per-event best-lag r (cleaned)")
            p_ = res["paired"]
            ax.set_title(f"paired dr = {p_['clean']['mean_dr']:+.3f} [{p_['clean']['ci'][0]:+.3f}, {p_['clean']['ci'][1]:+.3f}], "
                         f"p={p_['clean']['p_perm']:.3f}: {p_['verdict']}")
            ax.legend(loc="upper left")
        dk.save_fig(fig, ac.ANA / "art64_paired.png")

        ex_run = next((r for r in runs if "ex_raw" in data[r]["z"].files), None)
        if ex_run:
            z = data[ex_run]["z"]
            fig, axes = dk.new_fig("WIDE", 1, 2)
            t = z["ex_t_ms"]
            ax = axes[0]
            ax.plot(t, z["ex_raw"], color=dk.MUTED, lw=0.7, label="raw Wav2")
            ax.plot(t, z["ex_clean"], color=dk.COLOR["mpc"], lw=0.9, label="excised + interpolated")
            for pm in z["ex_pulses_ms"]:
                ax.axvline(pm, color=dk.COLOR["stim"], lw=0.6, alpha=0.5)
            ax.set_xlabel("time from a stim pulse (ms)"); ax.set_ylabel("ch64 (uV), 24 kHz")
            ax.set_title(f"{ex_run}: pulse artifacts excised (red = Plse edges)")
            ax.legend(loc="upper right")
            ax = axes[1]
            ax.plot(t, z["ex_raw_bp"], color=dk.MUTED, lw=0.9, label="raw, 5-200 Hz")
            ax.plot(t, z["ex_clean_bp"], color=dk.COLOR["mpc"], lw=1.1, label="cleaned, 5-200 Hz")
            ax.set_xlabel("time from a stim pulse (ms)"); ax.set_ylabel("ch64 (uV)")
            ax.set_title("after the LFP bandpass")
            ax.legend(loc="upper right")
            dk.save_fig(fig, ac.ANA / "art64_example.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
