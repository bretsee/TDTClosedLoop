"""Merge all partial results into sci_summary.json with a findings list."""
import json

import numpy as np
import sci_common as C

parts = {}
for name in ["gallery", "persite", "paired", "timecourse", "sham"]:
    with open(f"{C.OUT}/scripts/_{name}.json") as f:
        parts[name] = json.load(f)

# latency analysis: per-event best lag (0..4) on real events, first/last 20 events
def latency(arm, run):
    y8 = C.load_y8(arm, run)
    ref = C.load_ref(run)
    sched = C.load_schedule(run)
    best_lags, best_rs = [], []
    for ev in sched["events"]:
        if ev["site"] == "SHAM":
            continue
        o = ev["onset_tick"]
        ri = C.epoch_indices(o, len(ref), 0)
        if ri is None:
            continue
        t = ref[ri[0]:ri[1]]
        dt = t - t[:25].mean()
        rs = {}
        ok = True
        for L in range(5):
            yi = C.epoch_indices(o, len(y8), L)
            if yi is None:
                ok = False
                break
            a = y8[yi[0]:yi[1]]
            da = a - a[:25].mean()
            rs[L] = float(np.corrcoef(dt, da)[0, 1])
        if not ok:
            continue
        L = max(rs, key=rs.get)
        best_lags.append(L)
        best_rs.append(rs[L])
    bl, br = np.array(best_lags), np.array(best_rs)
    return dict(mean_best_lag=round(float(bl.mean()), 2),
                best_lag_first20=round(float(bl[:20].mean()), 2),
                best_lag_last20=round(float(bl[-20:].mean()), 2),
                bestlag_r_first20=round(float(br[:20].mean()), 3),
                bestlag_r_last20=round(float(br[-20:].mean()), 3))


latencies = {f"{a}_{r}": latency(a, r) for a, r in C.ARMS if a != "Hold"}

# global lag scan (replication of reported scores)
lagscan = {}
for arm, run in C.ARMS:
    y8 = C.load_y8(arm, run)
    ref = C.load_ref(run)
    dref = ref - C.BASELINE_REF
    n = min(len(ref), len(y8))
    row = {}
    for lag in [0, 1, 2, 3]:
        a = y8[lag:n]
        b = dref[:n - lag]
        m = min(len(a), len(b))
        row[f"lag{lag}"] = round(float(np.corrcoef(a[:m] - a[:m].mean(), b[:m])[0, 1]), 3)
    lagscan[f"{arm}_{run}"] = row

summary = dict(
    meta=dict(
        date="2026-08-31",
        analysis="science core (part 1/3)",
        feature="6-sample mean-abs of Wav1 ch8, ~101.7 Hz ticks, volts",
        epoch_ticks=[-C.PRE, C.POST],
        lag_correction=C.LAG,
        baseline_ref_V=C.BASELINE_REF,
        sham_threshold_V=C.SHAM_THRESHOLD,
        sham_threshold_statistic="mean raw y8 over 21-tick pulse window (lag +2); "
                                 "raw single-tick peaks cross this threshold ~100% of the time "
                                 "even under tonic Hold and are NOT usable for detection",
        captures={f"{a}_{r}": p for (a, r), p in C.CAPTURES.items()},
        events_per_run=100,
        usable_events=dict(MPC_r1=97, MPC_r2=96, Choi_r1=100, Choi_r2=100, Hold_r1=97),
        dropped="events whose -30..+190 epoch (+2 lag) runs past capture end "
                "(MPC captures 21348-21601 ticks vs 22200-tick schedule/refs)",
        per_event_table=f"{C.OUT}/scripts/_per_event_metrics.csv",
    ),
    global_lag_scan_r=lagscan,
    latency=latencies,
    event_gallery=parts["gallery"],
    per_site=parts["persite"],
    paired_test=parts["paired"],
    timecourse=parts["timecourse"],
    sham=parts["sham"],
    findings=[
        "GOOD: Both controllers reproduce touch-shaped cortical responses at all 5 real sites. "
        "Event-triggered-average r vs target: MPC 0.88-0.95 across sites/runs; Choi 0.66-0.90. "
        "Tonic Hold control shows no event-locked response (per-event r mean 0.004 +/- 0.125 SD), "
        "so tracking is controller action, not stim artifact or spontaneous coincidence.",
        "HEADLINE CORRECTION: Paired schedule-matched test at a common lag of +2 says MPC beats Choi "
        "(delta-r +0.068 [0.040, 0.096], p<1e-4, n=161), but that gap comes entirely from r1, where "
        "Choi's response latency was +1 tick (not +2). Scoring each arm at its own best lag, the arms "
        "TIE on shape fidelity: delta-r -0.007 [-0.034, +0.019], p=0.63, MPC wins 53% of events. "
        "MPC's real advantages are stability, not instantaneous shape fidelity (see below).",
        "LATENCY: MPC latency is stable at ~2.1 ticks in both runs; Choi's drifts (~1.3 ticks in r1, "
        "~1.6-1.8 in r2, rising within r2). Choi is 1 tick FASTER in r1 (no per-tick optimization), "
        "but its timing is nonstationary, which is what collapsed its lag-0 global score r1->r2 "
        "(0.573 -> 0.452).",
        "GOOD: SHAM catch trials are clean. Using the pulse-window-mean detector at the given threshold: "
        "false-touch rate MPC 0/32 (0%), Choi 1/33 (3%), vs Hold base rate 1/16 (6%); real-event hit "
        "rates MPC 95%, Choi 86%; d' MPC 4.2, Choi 3.6. Controller modulation on sham events "
        "(median 0.14-0.18 mV) is at or below the spontaneous-activity floor seen under Hold "
        "(0.20-0.25 mV) -> controllers do not fabricate touches.",
        "GOOD: No within-run degradation for MPC: r1 slope +0.07 r/100 events (ns), r2 +0.14 "
        "(significant IMPROVEMENT, mostly a ~10-event warm-up transient at run start).",
        "BAD (for Choi): Choi degrades within-run and it is genuine shape/amplitude loss, not lag "
        "drift: even scored at each event's own best lag, Choi falls first-20 -> last-20 events "
        "0.814 -> 0.702 (r1) and 0.807 -> 0.673 (r2); fixed-lag slope r2 = -0.13 r/100 events "
        "[-0.20, -0.07]. MPC moves the other way (best-lag 0.748 -> 0.804 r1, 0.659 -> 0.771 r2). "
        "Consistent with open-loop tapes drifting off a nonstationary plant while MPC re-anchors "
        "every tick; over runs longer than ~100 events MPC should win outright.",
        "BAD: Both arms overshoot single-tick peaks ~2x (median per-event peak ratio MPC 2.26, "
        "Choi 1.97) with tick-to-tick jitter; event-averaged waveform peaks match the target closely, "
        "so this is transient spikiness at pulse onset, not a gain error. Part of the per-event max "
        "statistic is noise-inflated: Hold's spontaneous activity alone yields peak ratio ~0.5.",
        "NUANCE: SHAM targets are not perfectly flat (small 0.038 mV bump, ~11% of real target 0.36 mV); "
        "neither controller tracks that small shape (per-event r ~ 0), i.e. targets below the "
        "spontaneous-activity floor are currently unreachable.",
        "CHECK: global lag-scan reproduces reported scores (MPC r1 0.721 @ +2 here vs 0.725 reported; "
        "differences are demeaning conventions).",
    ],
)

with open(f"{C.OUT}/sci_summary.json", "w") as f:
    json.dump(summary, f, indent=1)
print("lagscan:", json.dumps(lagscan, indent=0))
print("wrote sci_summary.json")
