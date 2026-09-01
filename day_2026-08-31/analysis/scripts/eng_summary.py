"""Merge stashed numbers into eng_summary.json with findings list."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "eng_summary.json")

lat = json.load(open(os.path.join(HERE, "_lat.json")))
tick = json.load(open(os.path.join(HERE, "_tick.json")))
charge = json.load(open(os.path.join(HERE, "_charge.json")))
ustrat = json.load(open(os.path.join(HERE, "_ustrat.json")))

runs = {
    "rnd1":       {"kind": "probe (random excitation, cpp server)", "ticks": 183000, "server_lat": "server_lat_runrnd1.csv"},
    "rndhi":      {"kind": "probe (random hi-amp, cpp server)", "ticks": 28000, "server_lat": "server_lat_runrndhi.csv"},
    "opfit":      {"kind": "probe (operating-point fit, design-driven)", "ticks": 12000, "server_lat": None},
    "mpc_mixr1":  {"kind": "arm MPC r1 - INERT first attempt (u frozen at hold; excluded)", "ticks": 22200, "server_lat": "mpc_lat_20260831_204354.csv"},
    "mpc_mixr1b": {"kind": "arm MPC r1 (valid)", "ticks": 22200, "server_lat": "mpc_lat_20260831_210645.csv"},
    "choi_mixr1": {"kind": "arm Choi r1", "ticks": 22200, "server_lat": None},
    "mpc_mixr2":  {"kind": "arm MPC r2", "ticks": 22200, "server_lat": "mpc_lat_20260831_213029.csv"},
    "choi_mixr2": {"kind": "arm Choi r2", "ticks": 22200, "server_lat": None},
    "opfit2":     {"kind": "probe (post-arm operating-point re-fit)", "ticks": 12000, "server_lat": None},
}
for lab in runs:
    runs[lab]["loop"] = lat["per_run_loop"][lab]
    runs[lab]["tick_health"] = tick[lab]
    runs[lab]["charge"] = charge["per_run"][lab]

findings = [
    "MATLAB-vs-cpp server contrast (for the paper): MATLAB MPC server turnaround p50 1.69 ms / p95 2.96 ms / p99 29.3 ms / max 47.7 ms (pooled arm runs mixr1b+mixr2, n=42,949); cpp Choi-class server p50 17 us / p95 29 us / p99 35 us / max 0.35 ms (rnd1+rndhi, n=211,000). ~100x at the median.",
    "1.4% of MATLAB replies exceed the 9.83 ms tick outright; the loop's tighter wait budget turned that tail into ~5-6.5% timeouts per MPC arm run (timeouts=staleDropped: 1043 mixr1b, 1401 mixr2), all absorbed by hold-last-command: freshTicks >= 22027/22200 (99.2%), heldTicks <= 145, zeroTicks <= 28, failures 0. cpp choi runs: 0 timeouts, freshTicks 22199/22200 (single zeroTick is the first tick before any reply).",
    "ANOMALY (process, resolved): first MPC r1 attempt (mpc_mixr1, 20:43-20:49) was inert - u1/u4 frozen at exactly the hold values (19.98/20.11 uA, zero variance for all 21,557 logged ticks) while the MATLAB server ran with normal latency. Rerun as mpc_mixr1b was healthy. Keep excluding mixr1 from science.",
    "Tick health: all four arm runs clean - |tick err| p95 < 1.9 ms, 0 dropped control ticks, no mid-run PLL resyncs (the 2-4 multi-second 'resyncs' in every log are the pre-stream backlog flush at tick 1).",
    "ANOMALY: rnd1 had one mid-run stall at tick ~16.3k (~2.7 min): 5 scheduler resyncs + 2 PLL resyncs (~30 ms phase error), 88/183,000 ticks dropped (0.05%). Isolated; rest of the 30-min run nominal.",
    "ANOMALY (worst of the day, but post-arm): opfit2 (last run, 21:56) degraded from tick ~9.9k to end of run - 1016/12,000 control ticks dropped (8.5%), 73 PLL resyncs, sustained ~5-6 ms lateness, tick-err p99 6.3 ms. Pattern (a drop roughly every other tick from ~10k on, ~5 ms late each time) looks like a sustained competing load on the rig PC, not PO8e trouble. No arm run affected, but opfit2's operating-point fit should be treated as suspect or re-derived from opfit (which was clean).",
    "MISSING FILES: the cpp server did not write server_lat_runchoi_mixr1/2.csv for the choi arm runs; cpp turnaround is quantified from the rnd probe runs (same binary) and corroborated loop-side (choi mpc_ms p50 0.029 ms). Check the cpp server's -latcsv flag before the next rig day.",
    "Loop-side overhead is negligible everywhere: in_to_udp_ms p99 <= 0.111 ms, mpc_ms p99 <= 0.093 ms across all 9 runs; the control budget is entirely the server turnaround.",
    "Charge ledger: Choi delivered 1.186M uA-ticks per arm run vs MPC 0.916M (+29.5%) on identical schedules; day total across 9 runs 6.12M uA-ticks. Tonic hold (20 uA x 2 pairs) is 97% of the MPC total - MPC modulation is only ~3% on top of baseline.",
    "Command strategy on the same schedule (r1): MPC is reactive and parsimonious - 48.9% of ticks within +/-0.5 uA of hold, never at 0, 0.3% at cap, mean |du| 0.11 uA/tick. Choi's precomputed drive rides near the 30 uA cap (48.2% of ticks at cap, median u4 = 30) with brief full shut-offs (6.4% at 0) around event onsets, including SHAM events; it slews 4.9x harder. Same tracking scores, very different actuation - and MPC's is the gentler, charge-cheaper policy.",
]

summary = {
    "generated": "2026-08-31 overnight analysis, part 3/3 (engineering)",
    "sources": "loop CSVs/logs + server latency CSVs + command captures only (no TDT blocks)",
    "nominal_tick_ms": 9.8304,
    "server_latency": {k: lat[k] for k in ("matlab_turnaround_ms", "matlab_compute_ms",
                                            "cpp_turnaround_ms", "cpp_compute_ms",
                                            "p50_ratio_matlab_over_cpp")},
    "u_strategy_r1": ustrat,
    "charge_day_total_uA_ticks": charge["day_total_delivered_uA_ticks"],
    "charge_note": charge["note"],
    "runs": runs,
    "findings": findings,
}
with open(OUT, "w") as f:
    json.dump(summary, f, indent=1)
print("wrote", os.path.abspath(OUT))
