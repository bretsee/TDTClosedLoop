# Offline controller-path benchmark

Reproducible offline comparison of the two controller integration paths, run through the **real** C++
loop with the hardware-free `--sim-input` source (no PO8e card). Both paths run the identical `mpc_test`
MPC. Workload: sine sim input, fs=24414 Hz, 16 channels, `--skip-udp-send`, 500 control ticks @ 100 Hz.

> **Updated 2026-07-23 (second session).** The localhost server's latency defects were found and fixed;
> the numbers below supersede the earlier run. Full analysis in `LAB_NOTEBOOK_2026-07-23.md`.
>
> Note also that these are **timing** results. They were gathered on a controller whose observer gain was
> silently zero (see the notebook, Finding 3), so they say nothing about control quality — only about
> transport and solve time, which the defect did not affect.

Environment bring-up first (required, or the `.exe` exits with code 53 and prints nothing):
```powershell
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"
```

Reproduce:
```
# Embedded MATLAB Engine
MpcPo8eUdpClosedLoop.exe 127.0.0.1 <repo> 16 --controller mpc_test \
  --sim-input sine --sim-fs 24414 --sim-channels 16 --skip-udp-send \
  --max-control-ticks 500 --validate-log sim_mpc.csv

# Localhost server. Start MATLAB first, in the FOREGROUND of its own terminal
# (Start-Process / Start-Job both silently fail here):
#   matlab -batch "cd('<repo>'); matlab_controller_server('mpc',31000,31001,16,0,600,'server_lat.csv')"
MpcPo8eUdpClosedLoop.exe 127.0.0.1 <repo> 16 --controller localhost --localhost-timeout-ms 5 \
  --sim-input sine --sim-fs 24414 --sim-channels 16 --skip-udp-send \
  --max-control-ticks 500 --validate-log sim_localhost.csv
```

## Results (500 ticks each, same session)

| Path | Controller latency avg / max | Loop totalTick avg / max | Dropped ticks | Usable replies |
|------|------------------------------|--------------------------|---------------|----------------|
| **Embedded Engine** | 1.586 ms / **11.266 ms** | 1.612 ms / **11.341 ms** | **2 / 500** | n/a (synchronous) |
| **Localhost (fixed)** | 9.999 ms / 11.968 ms | **0.053 ms / 0.660 ms** | **0 / 500** | 476 / 500 |

Server-side turnaround for the localhost path: avg 2.122 ms, median 1.886 ms, p95 3.186 ms.

A later regression run (after the observer fix, `MPC_TARGET = 300`) gave 0 dropped ticks and 55.1 µs
average ticks, but `timeouts=74` rather than 23 — `freshTicks=462`, `heldTicks=14`, `zeroTicks=24`.
Per-packet `compute` was unchanged at ~0.55 ms, so this is tail variance rather than added cost, but the
23–74 spread across runs is wide. **Treat the timeout count as a distribution, not a fixed figure**, and
collect repeat runs at the rig.

### How the localhost path got there

| stage | server turnaround (avg / median / p95) | usable replies | timeouts |
|---|---|---|---|
| original (`pause(0.001)` poll) | ~15.7 ms round trip | 0 at 5 ms timeout | 500 |
| + blocking `read()` | 15.774 / 15.513 / 15.838 ms | 0 | 499 |
| + 1 ms timer resolution | 2.478 / 1.893 / 3.462 ms | 451 | 48 |
| + controller warm-up | 2.122 / 1.886 / 3.186 ms | 476 | 23 |

Two independent Windows-timer-quantum problems, not one: `pause()` on the receive side (as suspected)
**and** `udpport`'s `write()` on the send side (not suspected — measured at 15.775 ms avg, 0.316 ms min).
Both are resolved by holding the MATLAB process at 1 ms timer resolution via a no-op `timer` object.

## Decision: deploy the localhost path

- **Embedded** runs the MATLAB solve *inside* the tick, so its worst case becomes the tick's worst case.
  It exceeded the 10 ms budget in both sessions (9.57 ms / 1 drop, then 11.27 ms / 2 drops) — over budget,
  and the margin is not reproducible run to run.
- **Localhost** fully decouples the loop: ~53 µs ticks, 0 drops, and a late controller degrades to a
  defined fail-safe rather than a missed tick.
- **Cost:** a structural one-tick (10 ms) command lag. The loop polls for the in-flight reply at the start
  of the tick *after* it sent the request (`MpcPo8eUdpClosedLoop.cpp:1332-1381`), so 10 ms is the floor,
  not a slow server. The measured 9999 µs average is exactly that floor. This lag must be modelled —
  `fit_sysid_from_capture.m` defaults to `inputDelayTicks = 1` for this reason.
- **Startup transient:** ~15–25 ticks command zero output while MATLAB warms. Safe (zero = no stim), but
  do not begin analysis at tick 1.

## Still open

- Freshness thresholds `LOCALHOST_FRESH_OUTPUT_US = 100 ms` / `LOCALHOST_MAX_HOLD_OUTPUT_US = 250 ms`
  (`MpcPo8eUdpClosedLoop.cpp:1147-1148`) are far too loose for a 10 ms loop; ~20 ms / ~50 ms would be
  appropriate. Needs a C++ rebuild.
- The C++ side discards any reply whose sequence is not the exact in-flight one. Accepting the *newest*
  reply instead would recover most of the remaining 23 timeouts. Needs a C++ rebuild.
- Rerun on `--sim-input file:<recorded>` once a block is exported; real features may change the QP solve
  time distribution.

Per-tick data for jitter histograms is in the `sim_*.csv` validate logs
(`packet,offset,input0,u0,amp0,t_in_us,t_mpc_done_us,t_udp_send_us,mpc_ms,in_to_udp_ms`).
Per-packet server timing is in `server_lat*.csv` (`seq,gap_ms,compute_ms,turnaround_ms`).
