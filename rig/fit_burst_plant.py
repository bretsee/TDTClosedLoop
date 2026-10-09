#!/usr/bin/env python
"""fit_burst_plant.py -- the BURST plant from a burst-ladder / gap-scan capture.

    python rig/fit_burst_plant.py --capture capture_rig_runburst1.csv \
        --meta design_runburst1_meta.json [--channels 34 40 47] [--json out.json] [--png out.png]
    python rig/fit_burst_plant.py --capture capture_rig_rungap1.csv --meta design_rungap1_meta.json
    python rig/fit_burst_plant.py --synthetic-check          # known-answer test, no hardware

Acute-3's primary aim (docs/ACUTE3_PLAN_2026-09-18.md C.1) is burst-vs-tonic
rank recovery; until now nothing turned the burst-ladder capture into numbers.
Per event in the design meta (tick, pair, amp, burst_ticks[, role, gap]) this
epochs the feature rows, baseline-subtracts the pre-window and reports:

  burst-ladder
    response(pair, amp, B)   AREA (sum over the response window, feature units
                             x ticks) of the trial-mean epoch on the best
                             channel (or --channels). Area, not peak: for a
                             low-pass cortical response the area is linear in
                             the total evoked drive whatever the pulse timing,
                             the peak is not.
    gain(pair, B)            slope of response vs amp through the origin
    per-pulse efficacy(B)    gain(B) / (B * gain(1)): 1.0 = linear summation,
                             < 1 = depression inside the burst
    footprint(B)             pairs x channels area matrix -> SVD eff-rank at
                             0.1*sigma_1 (placement_gate convention) per B
  gap-scan
    ratio(gap)               test / conditioning burst response per gap, by
                             TEMPLATE SUBTRACTION: the isolated conditioning
                             response (largest-gap trials) is subtracted at
                             the conditioning onset, so the test response is
                             read even when the two overlap (gaps 2-10);
                             operating gap = first gap with ratio >= --ratio-ok

Dead time: epochs start at the event tick; the response lands dead_time ticks
later (3 on the 09-10 prep, rig/check_dead_time.py). --dead sets where the
baseline window ends (default 3: baseline = ticks [tick-pre, tick+dead-1]).
--post (default 25 ticks) must stay below the design's minimum inter-burst gap
(30 in design_runburst1) so areas do not include the next burst.

--synthetic-check: generates captures from design_runburst1.csv and
design_rungap1.csv through rig/make_synthetic_burst_capture.py's depressing
plant (U=0.3, tau_rec=40, rank 3, dead 3), takes the TRUTH from the plant's
own drive trace (total synaptic drive per burst, so incomplete recovery
between ladder bursts is in the truth too), and asserts: eff-rank(B=1) == 3,
per-pulse efficacy per B within 0.1, gap ratios within 0.1. Exit 0 = PASS.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from fit_impulse_model import load_capture   # noqa: E402


def epoch_events(Y, events, pre, post, dead):
    """Per event: baseline-subtracted epoch rows [tick-pre, tick+B+post)."""
    out = []
    for e in events:
        t0 = int(e["tick"]) - 1                  # 0-based capture row of the burst's first tick
        B = int(e.get("burst_ticks", 1))
        a, b = t0 - pre, t0 + B + post
        if a < 0 or b > len(Y):
            continue
        seg = Y[a:b].astype(float)
        base = seg[:pre + max(0, dead - 1)].mean(axis=0, keepdims=True)
        out.append((e, seg - base, pre + max(0, dead - 1)))
    return out


def eff_rank(F, thresh=0.1):
    """placement_gate convention: rows normalized, SVD, count sv >= thresh*sv1."""
    F = np.asarray(F, float)
    if F.size == 0 or F.shape[0] == 0:
        return 0, []
    norms = np.linalg.norm(F, axis=1, keepdims=True) + 1e-12
    sv = np.linalg.svd(F / norms, compute_uv=False)
    sv = sv / (sv[0] + 1e-30)
    return int(np.sum(sv >= thresh)), sv.tolist()


def slope_origin(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = (x * x).sum()
    return float((x * y).sum() / d) if d > 0 else float("nan")


def analyze_ladder(Y, meta, pre, post, dead, channels, rank_thresh):
    evs = [e for e in meta["events"]]
    ep = epoch_events(Y, evs, pre, post, dead)
    pairs = sorted({int(e["pair"]) for e in evs})
    amps = sorted({float(e["amp"]) for e in evs})
    Bs = sorted({int(e.get("burst_ticks", 1)) for e in evs})
    n_ch = Y.shape[1]
    # trial means per (pair, amp, B): peak over the response window per channel
    resp = {}
    for p in pairs:
        for a in amps:
            for B in Bs:
                segs = [s for (e, s, b0) in ep if int(e["pair"]) == p and float(e["amp"]) == a and int(e.get("burst_ticks", 1)) == B]
                if not segs:
                    continue
                M = np.mean(segs, axis=0)                 # [len x ch]
                b0 = ep[0][2]
                resp[(p, a, B)] = M[b0:].sum(axis=0)      # AREA per channel (see header)
    # best channel: largest mean |peak| over the top amplitude, B=1 (or given)
    if channels:
        ch_idx = [c - 1 for c in channels]
    else:
        score = np.zeros(n_ch)
        for p in pairs:
            k = (p, amps[-1], Bs[0])
            if k in resp:
                score += np.abs(resp[k])
        ch_idx = [int(np.argmax(score))]
    best = ch_idx[0]
    out = {"pairs": pairs, "amps": amps, "burst_ticks": Bs, "best_channel": best + 1,
           "channels_used": [c + 1 for c in ch_idx], "gain": {}, "per_pulse_efficacy": {},
           "eff_rank": {}, "footprint_sv": {}, "n_trials": {}}
    for B in Bs:
        F = []
        for p in pairs:
            xs, ys = [], []
            for a in amps:
                k = (p, a, B)
                if k in resp:
                    xs.append(a); ys.append(float(np.mean(resp[k][ch_idx])))
            g = slope_origin(xs, ys) if xs else float("nan")
            out["gain"].setdefault(str(p), {})[str(B)] = g
            # footprint row: per-channel gain slope through the origin across
            # ALL amplitudes (every trial contributes; the top-amplitude peak
            # alone was noise-limited at 20 trials and inflated the rank)
            rows_a = [(a, resp[(p, a, B)]) for a in amps if (p, a, B) in resp]
            if rows_a:
                xa = np.array([a for a, _ in rows_a])
                Ya = np.array([v for _, v in rows_a])            # [amps x ch]
                F.append((xa[:, None] * Ya).sum(axis=0) / (xa * xa).sum())
        r, sv = eff_rank(np.array(F), rank_thresh)
        out["eff_rank"][str(B)] = r
        out["footprint_sv"][str(B)] = sv
    for p in pairs:
        g1 = out["gain"][str(p)].get(str(Bs[0]))
        for B in Bs:
            g = out["gain"][str(p)].get(str(B))
            out["per_pulse_efficacy"].setdefault(str(p), {})[str(B)] = (
                float(g / (B * g1)) if (g1 and np.isfinite(g1) and abs(g1) > 1e-30 and g is not None) else float("nan"))
    out["n_trials"] = {"%d,%g,%d" % k: int(sum(1 for (e, s, b0) in ep
                                                 if int(e["pair"]) == k[0] and float(e["amp"]) == k[1]
                                                 and int(e.get("burst_ticks", 1)) == k[2]))
                       for k in resp}
    # headline: efficacy averaged over pairs
    out["efficacy_mean"] = {str(B): float(np.nanmean([out["per_pulse_efficacy"][str(p)][str(B)] for p in pairs]))
                            for B in Bs}
    return out


def analyze_gap(Y, meta, pre, post, dead, channels, ratio_ok):
    """Paired-burst recovery by template subtraction.

    Each trial = conditioning burst (B pulses) + gap g + test burst (B pulses).
    1. Pair cond/test events by order (the design writes them consecutively).
    2. Baseline for the WHOLE trial = the window before the conditioning onset.
    3. Template T = mean conditioning response of the largest-gap trials
       (isolated: the test starts >= 50 ticks later), length `post` ticks from
       the conditioning onset.
    4. Per trial: subtract T at the conditioning onset; the remainder from the
       test onset over `post` ticks is the test response. ratio = area(test
       remainder) / area(T), averaged per gap.
    """
    evs = sorted(meta["events"], key=lambda e: int(e["tick"]))
    n_ch = Y.shape[1]
    B = int(meta.get("burst_ticks", evs[0].get("burst_ticks", 1)))
    gaps = sorted({int(e["gap"]) for e in evs if "gap" in e})
    pairs = []
    i = 0
    while i + 1 < len(evs):
        c, t = evs[i], evs[i + 1]
        if c.get("role") == "cond" and t.get("role") == "test" and int(c["gap"]) == int(t["gap"]):
            pairs.append((c, t)); i += 2
        else:
            i += 1
    base_len = pre + max(0, dead - 1)
    trials = []
    for c, t in pairs:
        c0 = int(c["tick"]) - 1
        t0 = int(t["tick"]) - 1
        a, b = c0 - pre, t0 + B + post
        if a < 0 or b > len(Y):
            continue
        seg = Y[a:b].astype(float)
        seg = seg - seg[:base_len].mean(axis=0, keepdims=True)
        trials.append((int(c["gap"]), seg, pre, t0 - c0 + pre))   # offsets of cond / test onsets in seg
    if not trials:
        return {"gaps": gaps, "channels_used": [], "ratio": {}, "ratio_ok": ratio_ok,
                "operating_gap_ticks": None, "n_pairs_per_gap": {}}
    g_iso = max(gaps)
    L = post
    T = np.mean([seg[oc:oc + L] for (g, seg, oc, ot) in trials if g == g_iso and seg.shape[0] >= oc + L], axis=0)
    if channels:
        ch_idx = [c - 1 for c in channels]
    else:
        ch_idx = [int(np.argmax(np.abs(T).sum(axis=0)))]
    areaT = float(T[:, ch_idx].mean(axis=1).sum())
    ratio, n_per = {}, {}
    for g in gaps:
        vals = []
        for (gg, seg, oc, ot) in trials:
            if gg != g:
                continue
            rem = seg.copy()
            n_t = min(L, rem.shape[0] - oc)
            rem[oc:oc + n_t] -= T[:n_t]
            n_w = min(L, rem.shape[0] - ot)
            vals.append(float(rem[ot:ot + n_w, ch_idx].mean(axis=1).sum()))
        n_per[str(g)] = len(vals)
        if vals and abs(areaT) > 1e-30:
            ratio[str(g)] = float(np.mean(vals) / areaT)
    op = next((g for g in gaps if str(g) in ratio and ratio[str(g)] >= ratio_ok), None)
    return {"gaps": gaps, "channels_used": [c + 1 for c in ch_idx], "ratio": ratio,
            "ratio_ok": ratio_ok, "operating_gap_ticks": op, "template_gap": g_iso,
            "n_pairs_per_gap": n_per}


def run(capture, meta_path, pre, post, dead, channels, rank_thresh, ratio_ok, json_out, png_out):
    U, Y = load_capture(capture)
    with open(meta_path) as f:
        meta = json.load(f)
    kind = meta.get("kind", "burst-ladder")
    if kind == "gap-scan":
        res = analyze_gap(Y, meta, pre, post, dead, channels, ratio_ok)
        print("GAP SCAN %s: channels %s" % (os.path.basename(capture), res["channels_used"]))
        for g in res["gaps"]:
            print("  gap %3d ticks: test/cond ratio %.3f  (n %d)" % (g, res["ratio"].get(str(g), float("nan")), res["n_pairs_per_gap"][str(g)]))
        print("  OPERATING GAP (first ratio >= %.2f): %s ticks" % (ratio_ok, res["operating_gap_ticks"]))
    else:
        res = analyze_ladder(Y, meta, pre, post, dead, channels, rank_thresh)
        print("BURST LADDER %s: pairs %s, amps %s, B %s, channel(s) %s"
              % (os.path.basename(capture), res["pairs"], res["amps"], res["burst_ticks"], res["channels_used"]))
        print("  gain (feature units per uA) by pair x B:")
        for p in res["pairs"]:
            print("    pair %d: " % p + "  ".join("B=%s %.3g" % (B, res["gain"][str(p)][B]) for B in res["gain"][str(p)]))
        print("  per-pulse efficacy (gain(B) / (B*gain(1))), mean over pairs: " +
              "  ".join("B=%s %.2f" % (B, v) for B, v in res["efficacy_mean"].items()))
        print("  footprint eff-rank per B: " + "  ".join("B=%s rank %d" % (B, r) for B, r in res["eff_rank"].items()))
    res["capture"] = capture; res["meta"] = meta_path; res["kind"] = kind
    if json_out:
        with open(json_out, "w") as f:
            json.dump(res, f, indent=1)
        print("wrote %s" % json_out)
    if png_out:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3.6))
        if kind == "gap-scan":
            gs = res["gaps"]; ax.plot(gs, [res["ratio"].get(str(g), np.nan) for g in gs], "o-", color="#2a78d6")
            ax.axhline(ratio_ok, color="#777", ls="--"); ax.set_xscale("log")
            ax.set_xlabel("gap (ticks)"); ax.set_ylabel("test / cond response"); ax.set_title("recovery vs gap")
        else:
            Bs = res["burst_ticks"]
            for p in res["pairs"]:
                ax.plot(Bs, [res["per_pulse_efficacy"][str(p)][str(B)] for B in Bs], "o-", alpha=0.6, label="pair %d" % p)
            ax.plot(Bs, [res["efficacy_mean"][str(B)] for B in Bs], "k-", lw=2, label="mean")
            ax.set_xlabel("burst length B (pulses)"); ax.set_ylabel("per-pulse efficacy"); ax.set_title("depression inside the burst")
            ax.legend(frameon=False, fontsize=7, ncol=2)
        fig.tight_layout(); fig.savefig(png_out, dpi=150)
        print("wrote %s" % png_out)
    return res


def burst_drive(drive, e):
    """Total synaptic drive of one designed burst in the plant's own drive trace."""
    t0 = int(e["tick"]) - 1
    B = int(e.get("burst_ticks", 1))
    return float(drive[t0:t0 + B, int(e["pair"]) - 1].sum())


def synthetic_check(tmpdir):
    from make_synthetic_burst_capture import simulate, write_capture
    from design_burst_probe import read_design
    ok = True
    POST = 25
    # Low noise: this is a known-answer test of the ESTIMATOR (area, template
    # subtraction, rank), not of its SNR limit. At the default noise the gap
    # ratios scatter by ~0.15 at 25 trials/gap -- the rig's problem, reported
    # honestly by n_pairs_per_gap, not an estimator defect.
    QUIET = {"noise": 2e-7}
    # ---- burst ladder ------------------------------------------------------
    dsn = os.path.join(REPO, "design_runburst1.csv")
    Ud = read_design(dsn)
    Y, W, T, drive = simulate(Ud, 16, 1, QUIET)
    cap = os.path.join(tmpdir, "synth_burst1.csv"); write_capture(cap, Ud, Y)
    meta_path = os.path.join(REPO, "design_runburst1_meta.json")
    res = run(cap, meta_path, 5, POST, T["dead"], None, 0.1, 0.8, None, None)
    with open(meta_path) as f:
        meta = json.load(f)
    # truth from the drive trace: per-pulse efficacy(B) = mean over bursts of
    # [drive per pulse per uA at B] / [drive per pulse per uA at B=1], per pair,
    # then averaged over pairs -- the same quantity the fitter estimates from
    # the response areas, including incomplete recovery between ladder bursts.
    Bs = sorted({int(e["burst_ticks"]) for e in meta["events"]})
    per_pair = {}
    for e in meta["events"]:
        key = (int(e["pair"]), int(e["burst_ticks"]))
        per_pair.setdefault(key, []).append(burst_drive(drive, e) / (float(e["amp"]) * int(e["burst_ticks"])))
    truth_eff = {}
    for B in Bs:
        vals = []
        for p in sorted({k[0] for k in per_pair}):
            if (p, B) in per_pair and (p, Bs[0]) in per_pair:
                vals.append(np.mean(per_pair[(p, B)]) / np.mean(per_pair[(p, Bs[0])]))
        truth_eff[str(B)] = float(np.mean(vals))
    for B in Bs:
        got, want = res["efficacy_mean"][str(B)], truth_eff[str(B)]
        good = abs(got - want) < 0.1
        ok &= good
        print("  check efficacy B=%s: got %.3f want %.3f %s" % (B, got, want, "PASS" if good else "FAIL"))
    r1 = res["eff_rank"][str(Bs[0])]
    good = r1 == T["rank"]
    ok &= good
    print("  check eff-rank at B=1: got %d want %d %s (sv %s)" % (r1, T["rank"], "PASS" if good else "FAIL",
          ["%.2f" % v for v in res["footprint_sv"][str(Bs[0])][:5]]))
    # ---- gap scan ----------------------------------------------------------
    dsn = os.path.join(REPO, "design_rungap1.csv")
    Ud = read_design(dsn)
    Y, W, T, drive = simulate(Ud, 16, 2, QUIET)
    cap = os.path.join(tmpdir, "synth_gap1.csv"); write_capture(cap, Ud, Y)
    meta_path = os.path.join(REPO, "design_rungap1_meta.json")
    res = run(cap, meta_path, 5, POST, T["dead"], None, 0.1, 0.8, None, None)
    with open(meta_path) as f:
        meta = json.load(f)
    evs = sorted(meta["events"], key=lambda e: int(e["tick"]))
    truth_ratio = {}
    for c, t in zip(evs[0::2], evs[1::2]):
        if c.get("role") == "cond" and t.get("role") == "test":
            truth_ratio.setdefault(str(int(c["gap"])), []).append(burst_drive(drive, t) / burst_drive(drive, c))
    for g in res["gaps"]:
        want = float(np.mean(truth_ratio[str(g)]))
        got = res["ratio"].get(str(g), float("nan"))
        good = abs(got - want) < 0.1
        ok &= good
        print("  check gap %3d: ratio got %.3f want %.3f %s" % (g, got, want, "PASS" if good else "FAIL"))
    print("SYNTHETIC CHECK %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture")
    ap.add_argument("--meta")
    ap.add_argument("--channels", type=int, nargs="*", default=None, help="1-based feature channels to average")
    ap.add_argument("--pre", type=int, default=5)
    ap.add_argument("--post", type=int, default=25,
                    help="response window after the burst (ticks); keep < the design's min inter-burst gap")
    ap.add_argument("--dead", type=int, default=3, help="row-frame dead time (check_dead_time.py)")
    ap.add_argument("--rank-thresh", type=float, default=0.1)
    ap.add_argument("--ratio-ok", type=float, default=0.8)
    ap.add_argument("--json", default=None)
    ap.add_argument("--png", default=None)
    ap.add_argument("--synthetic-check", action="store_true")
    args = ap.parse_args()
    if args.synthetic_check:
        import tempfile
        return synthetic_check(tempfile.mkdtemp(prefix="burst_synth_"))
    if not (args.capture and args.meta):
        ap.error("--capture and --meta are required (or --synthetic-check)")
    run(args.capture, args.meta, args.pre, args.post, args.dead, args.channels,
        args.rank_thresh, args.ratio_ok, args.json, args.png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
