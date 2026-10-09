# Lab notebook — 2026-10-09 (offline day: controller model + experimental flow)

Acute #3 is waiting on a USB-Ethernet dongle (onboard RTL8126 confirmed dead after a true full
boot on 10-08 18:39: boot type 0x0, link 0 bps, 0 bytes, power-management query still failing; PO8e
card fine). No hardware today. Eight improvements, all built and verified offline against the
09-10 captures, the sim harness, synthetic known-answer plants, the cpp selftest and the MATLAB
bench. Everything is flag-gated where it touches the MPC formulation; defaults stay Choi-comparable.

## Headline findings

1. **The deployed plant model was one tick optimistic, and the true dead time is 3 ticks.**
   `fit_sysid_from_capture` shifted u by `inputDelayTicks=1` AND regressed with nk=1 (u(k) → y(k+2)),
   then `export_plant_lti` dropped the shift, while `cpp_controller`/`mpc_test` predict
   `x(k+1) = A x(k) + B u(k)` (dead time 1). An order-1 fit (the 09-10 `plant_opfit12.lti`) has no
   spare coefficient to absorb that. New `rig/check_dead_time.py` measured the data:
   - rnd1 pulse probe (532 trials/pair, ch64): **onset lag 3 on all 7 responsive pairs** (pair 2 did
     not respond on ch64), peak lag 3 → 1 transport tick + ~2 ticks thalamocortical latency.
   - opfit12 tonic PRBS, row-frame free-run scoring: old export **EARLY by 2 ticks** (best shift +2),
     refit with delay states d=1 EARLY by 1, **d=2 centred** (shift profile −1:0.50 / 0:0.59 / +1:0.57).
     Fit% stays ≈0.6 (tonic data; the honest valFit≈0 of 09-10 is unchanged — this fixes framing, not SNR).
   - Fix: `delayStates` (default on) appends d×m pure-delay states in observable form; DC gain unchanged
     (`check_mimo_rank` identical); `arx_to_ss` now realizes nk>1 correctly; `export_plant_lti(path,
     r.sys)` struct overload, provenance as a `#` comment (all three parsers skip it). Fitter default
     `inputDelayTicks` 1 → **2**. `crossval_model` scores row-frame models unshifted. Bench case
     "delay-state realization" on a known 3-tick synthetic: delay-state export best at shift 0 (92.6%),
     legacy export best at shift +2 (93.4% there, 49.7% at 0). Models: `plant_opfit12_d0/d1/d2.lti`.

2. **Offset-free MPC (`--dist-observer`) removes mismatch bias; the plain observer cannot.**
   Sim on `plant_opfit12_d2` with the plant at 1.5× gain, +1e-5 V bias and 2e-9 V/tick drift
   (`closed_loop_sim.py --gain-scale --bias --drift-per-tick --extra-delay`, all new, no-ops by default):

   | observer | y error early | mid | late | innov RMS late |
   |---|---|---|---|---|
   | plain (Choi-comparable) | +24 % | +29 % | +33 % | 2.1e-5 |
   | `--dist-observer --dist-q 1e-2` | +0.7 % | 0.0 % | +0.1 % | 1.4e-8 |

   Selftest case: plant gain 1.5× + bias 0.5 → plain lands at 6.09 for target 5, dist at 5.004.
   Implementation = observer only (augmented [A 0; 0 I], [C I] Kalman gain), cost/F/G/H untouched, so
   the deliberate ρ/(1+ρ) steady-state shortfall of the absolute-u penalty remains. C++-only; MATLAB
   comparison arms run with it off (documented in `mpc_test.m` header and `cpp_controller/README.md`).

3. **Capture was written only at exit** (`cpp_controller --capture` buffered everything), so the
   runbook's "y-liveness in the first minute" could never work on a cpp run — the 09-10 PZ2-off runs
   were only caught post hoc. Now streamed (row per tick, flush every 100; 280 rows at 3 s, 480 at 5 s
   mid-run under a paced client), opened before the socket so a bad path fails before `ready`.

4. **Sim harness deadlock found and fixed:** `closed_loop_sim.py --launch` piped the server's stdout
   and never read it; the server blocked on printf after ~1600 ticks ("controller stopped
   responding"). Stdout now goes to `server_<capture>.log`. The 10-07 sim dress (1300 ticks) sat just
   under the limit.

## Controller changes (`cpp_controller`, selftest 13 → 16/16; MATLAB bench 26 → 28 PASS)
- `--effort-ratio RHO`: R_j = ρ Σ_i Q_i G_ij², G = DC gain by Neumann series (printed at startup).
  ρ=0.1 on opfit12_d2 with Q=1e12 → R=[0.0534, 8.0e-5]. SISO settles at r/(1+ρ).
- Telemetry per tick in the latency log: `qpCost,qpIters,qpConv,activeFrac,innov0,rW0`, plus a `#`
  banner line (model, n, observer ACTIVE/OFF + pole, offsets, N/Nu, q/r, umin/umax, effort_ratio,
  r_schedule, preview, dist_observer). Latency log now defaults to `server_lat_<name>` **in the
  capture's directory** (was silently lost for every `day_*/` capture, including all of 09-10).
- `--r-schedule tick,r1[,r2..]`: `set_r_weights` rebuilds the Hessian (warm start kept). Sim with
  ref_mix_r1 + 5 blocks R100/30/10/100/30: every switch applied (rW0 verified per block), above-hold
  charge 175 / 243 / 485 µA-ticks for R=100/30/10, r0 flat at 0.79 (sim plant = model).
- `--play` refuses a design whose `_meta.json` nTicks ≠ row count. Help text for `--reference`
  corrected (preview exists).

## Flow changes
- `rig/ingest_block.py`: `quiet` mode (runs `analyze_quiet_capture`), ledger = `BLOCK_LEDGER_<day>.md`
  created on first use (before 06:00 continues yesterday's), `--ledger/--day`; never falls back to an
  older ledger (the 09-10 file has no marker: every 10-08 append would have failed). Template table
  no longer has a blank line before the first row.
- `rig/2_loop.ps1 -Design <csv>` (ticks from meta; explicit `-Ticks` wins with a warning),
  `-Capture/-Baseline` spawn `check_y_liveness --watch` at `go`; final hint = `run_audit` line.
- `rig/1c_server.ps1`: existing `design_run<Run>.csv` requires typing `reuse` (or `-Reuse`).
- **`rig/run_audit.py`** (one PASS/WARN/FAIL line; UTF-16 loop logs decoded by BOM). On 09-10 artifacts:
  mpc_mixr1 WARN (no server log existed), mpc_r4cm **FAIL y=DEAD** (the PZ2-off run), choi_mixr1 WARN
  (backlog skip line), sim dress WARN (u pinned, `--sim`).
- **`rig/rig_runcard.py --phase …`**: exact A/B/check lines per phase, writes
  `day_<day>/runcard_<phase>.txt`; `dutyid` phase writes `design_rundutyid.csv` + meta and validates
  (`DESIGN OK` on pairs 1,3,4,6: 30100 ticks, 0 overlaps). `fit` phase emits the struct export and
  the dead-time check.
- **R sweep tooling**: `rig/build_r_schedule.py` (blocks from `schedule_mix_rN.json`),
  `rig/analyze_r_sweep.py` (per-block r0/best-lag/RMSE/charge/above-hold, OLS r ~ R-level + order,
  rW0 verification, PNG). Runbook 6e is now one run.
- **`rig/fit_burst_plant.py`** (+ `rig/make_synthetic_burst_capture.py`): burst-ladder gain vs B,
  per-pulse efficacy, footprint eff-rank per B (gain-slope footprint across all amplitudes), gap-scan
  recovery by template subtraction. Known-answer check on a depressing-synapse plant (U=0.3, τ=40,
  rank 3, dead 3): efficacy B=3 0.742 vs 0.738, B=10 0.366 vs 0.364, eff-rank 3, all 7 gap ratios
  within 0.03 → PASS. On the real rnd1 probe (single pulses, ch64): eff-rank **5** at B=1 (matches the
  09-11 "pulse eff-rank 5" number), pair 2 weakest, pair 8 strongest.
- `rig/check_impulse_delivery.py --design-meta`: burst-aware run-length audit (designed lengths are
  bursts, others are stalls) and per-probe window = B·10+12 ms scored missed/short/exact/long.
  Compile-checked; not run on a block (no burst block exists yet).
- `RIG_DAY_2026-10-08.md` (10-09 banner + Phase 4/5/6a/6e rewritten), `HELPER_CARD` (runcard rows,
  AUDIT lines), `RIG_DAY_PROTOCOL.md` dead-time note, `cpp_controller/README.md`, `mpc_test.m` header.

## Numbers banked in `day_2026-10-09/`
`dead_time_opfit12.json`, `dead_time_rnd1_ch64.json`, `capture_sim_mismatch_{plain,dist}.csv` +
latency logs, `rsweep_sim_opfit12_d2.{json,png}`, `rsched_sim_r1.{csv,json}`,
`burst_plant_rnd1_ch64.json`, `design_runrnd1_meta_derived.json`. Models `plant_opfit12_d{0,1,2}.lti`
in the repo root.

## For the weekly deck (figures to build with deckkit, not built today)
dead-time shift profile old vs d2 (from `dead_time_opfit12.json`), rnd1 onset profiles (8 pairs),
mismatch sim y(t) plain vs dist with innov0 (captures above), R-sweep block table/PNG, synthetic
burst-plant efficacy + recovery curves, run_audit lines for the four 09-10 artifacts.

## Open / next
- Acute #3 day-of: run `check_dead_time` on the gate probe and pass onset−1 to the Phase-4 fit
  (default 2). Any `--dist-observer` arm is a separate, labelled arm (not Choi-comparable).
- `check_impulse_delivery --design-meta` needs its first real burst block to be exercised.
- `sweep_channels.m` still aligns with d=1 for its correlation scan (harmless; it does not export).
- The QP hits its 200-iteration cap for 1-2 ticks after an R switch (warm start far from the new
  optimum); converged on every other tick. Fine for 20-event blocks.
