# Resume here (closed-loop MPC work) — checkpoint 2026-07-23 (evening)

Phase 1 (offline sim harness) **built and validated**. Phase 2 (controller-path benchmark) **done and
decided**. Phase 3 tooling for system ID **built and rehearsed**. Next session is at the TDT rig.

**Read these in order:**
1. `LAB_NOTEBOOK_2026-07-23.md` — what changed today and why. Includes a defect that meant the loop was
   not actually closed. Start here.
2. `RIG_DAY_PROTOCOL.md` — the runbook for the hardware session.
3. `BENCHMARK_NOTES.md` — controller-path numbers and the decision.

## Decisions now closed

- **Controller path: localhost.** Embedded exceeds the 10 ms tick budget and drops ticks (2/500 today);
  localhost holds ~53 µs ticks with 0 drops. Cost is a structural one-tick (10 ms) command lag.
- **System-ID method: ARX least squares**, not `n4sid` — the System Identification Toolbox is not
  installed on this machine (nor is the Control System Toolbox).

## State of the tree (uncommitted)

Modified:
- `matlab_controller_server.m` — blocking read + 1 ms timer resolution (the latency fix), controller
  warm-up, vectorized wire pack/unpack, new `openloop` capture mode, per-packet timing log,
  options-struct config, idle auto-stop.
- `mpc_test.m` — `design_observer_gain` no longer silently returns `L = 0` when the Control System
  Toolbox is missing; computes a steady-state Kalman gain instead. **This changes control behaviour:
  the MPC now actually uses its measurement.**

New:
- `make_excitation.m` — PRBS / multilevel / steps / chirp excitation, no toolbox deps.
- `fit_sysid_from_capture.m` — ARX system ID + validation, no toolbox deps.
- `RIG_DAY_PROTOCOL.md`, `LAB_NOTEBOOK_2026-07-23.md`.
- `capture_test.csv`, `server_lat*.csv`, `sim_*.csv` — rehearsal artifacts, safe to delete.

Binary `MpcPo8eUdpClosedLoop.exe` is current; **no C++ was changed today**, so no rebuild is needed.

## Environment bring-up (every fresh shell)
```powershell
cd "C:\Users\brets\Documents\Repositories\TDTClosedLoop"
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"
```
Required for the `.exe` even on the localhost path — without it, exit code 53 and no output.

**Launch MATLAB in the foreground of its own terminal.** `Start-Process` and `Start-Job` both silently
fail here. Always redirect `2>&1` — `-batch` errors go to stderr.

## Quick verification that nothing rotted
```powershell
.\MpcPo8eUdpClosedLoop.exe 127.0.0.1 . 16 --controller constant --constant-output 5 `
  --sim-input sine --sim-fs 24414 --sim-channels 16 --skip-udp-send `
  --max-control-ticks 300 --validate-log sim_smoke.csv
# expect droppedControlTicks=0
```

## Next actions (at the rig — see RIG_DAY_PROTOCOL.md)
1. Open-loop PRBS capture with a **safe** `uMax` (the default 40 is a controller clamp, not a safety limit).
2. Confirm `|corr| u -> y` is meaningfully above 0.1 — that is the go/no-go for everything after.
3. Fit with `fit_sysid_from_capture`, sanity-check the time constant, save into `AllModels(10).sys`.
4. Set `feature_map` in `mpc_test.m` to the channel actually identified.
5. Closed-loop run; confirm the command tracks the feature (it now can).

## Deferred (need a C++ rebuild — avoided before hardware day)
- Tighten `LOCALHOST_FRESH_OUTPUT_US` (100 ms) / `LOCALHOST_MAX_HOLD_OUTPUT_US` (250 ms) to ~20/50 ms.
- Accept the newest localhost reply rather than only the exact in-flight sequence, to cut the remaining
  ~23/500 timeouts.
- Jitter histograms from the `sim_*.csv` logs; force the solver-fail and stale-reply fail-safes.

Memory: `tdt-closedloop-mpc` (in the project memory dir).
