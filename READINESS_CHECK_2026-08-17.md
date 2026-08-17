# Off-Rig Readiness Check — 2026-08-17 (day before in-vivo week)

Re-verification of everything in `DEPLOYMENT_PLAN_INVIVO.md` that can be proven without
the rig. Tree at `a1aa856` + the two changes committed with this report.

## Results — everything off-rig PASSES

| # | Check | Result |
|---|-------|--------|
| 1 | Git/tree state | PASS — clean tree at `a1aa856`; current exe sha256-identical to archived `aug15-final.exe`; PDB present |
| 2 | `rig\0_preflight.ps1` | PASS — MATLAB PATH, 6 files, AllModels backup, 300-tick sim smoke `droppedControlTicks=0`, window 6/6/0 **at the corrected 610.3516 Hz** (see fix below) |
| 3 | `bench_test_reference_mpc` | PASS — 8/8, `ALL BENCH TESTS PASS`; OSQP resolves in `-batch` (exist=2) |
| 4 | `rig\6_udp_selftest.ps1` | PASS — A/B1/B2/B3/C/D vs fake RZ2 (checkRZ ACK, one-shot, words, envelope 506 pkts @100.4 Hz, silent-failure demo) |
| 5 | WER LocalDumps | PASS — DumpFolder=`crash_dumps\`, DumpType=2 (full), DumpCount=16, DontShowUI=1, WER enabled. Keys on canonical exe name only |
| 6 | PageHeap | PASS — IFEO key absent (OFF; correct for timing runs) |
| 7 | `build_touch_reference.py` | PASS — dry run on `Acute_121223\ExperimentBL-231212-210716.npz` (split-half 0.977, peak 400 µV, ch 11): 4600 ticks, 20 events, **peak Δ 5.13e-05 V** (51% of a 1e-4 baseline — clears the 10% floor). Bank that Δ for the day-of scale sanity: Δ/gain must sit well inside uMax |
| 8 | `fit_impulse_model.py` refusal path | PASS — correctly rejects PRBS `capture_rig_runc04.csv` ("0 isolated pulses"), exit 1 |
| 9 | `fit_impulse_model.py` positive path | PASS — new fixture `capture_synth_impulse.csv` (see below): ch 7 RESPONDING at 4.2× floor, gain 0.4961 vs true 0.5, delay 2 ticks vs true 2, linearity R² 1.000; all 15 other channels below floor |
| 10 | Closed-loop dress rehearsal (runbook step 4, sim) | PASS (mechanics) — `4_mpc_server -Reference -RWeight 1e-3 -Pairs 1` + `2_loop -Sim -TimeoutMs 10 -Ticks 4600`: reference loaded (range 600–702.7), MPC_OPTS override applied, pair-1 mapping active, 4428 packets serviced, server turnaround avg 2.37 ms / p95 3.07 ms, loop 4600/4600 `droppedControlTicks=0`, window 6/6/0, zeroTicks=19 (startup only), clean bounded stop, `capture_mpc_*.csv` written, out0-varied check green |
| 11 | Emergency stim-zero (bench half of preflight step 5) | **PASS — first time exercised.** Genuine console-control event (CTRL_BREAK to process group) mid-run with UDP live to fake RZ2: "EMERGENCY STIM ZERO (console control event)" printed, exit 0xC000013A, and the fake RZ2's packet log ends with exactly **5 all-zero DATA packets** (all 8 words), ~50 µs apart, immediately after the last commanded packet. Only the Synapse-side `Scle`-drops-to-zero confirmation remains for the rig |
| 12 | `7_campaign.ps1 -Run rdy01 -Sim` | PASS — CLEAN verdict, exit 0x0, 6000/6000, venv python resolved, ledger row appended |
| 13 | Stale-state sweep | PASS — no MATLAB processes left, port 31000 free |

## Caveats on the rehearsal (item 10)

- out0 sat at ~40 the whole run: the 600-unit reference is unreachable for the toy
  AllModels plant (DC gain ~0.2). That is the runbook's **branch E2 saturation**
  signature appearing exactly as documented — expected, since the sim feature (sine MAV
  ~636) is decoupled from the command. Mechanics verified; tracking quality is only
  testable on a real identified plant.
- Loop timeouts 307/4600 (6.7%) **even at `-TimeoutMs 10`** with freshTicks 98.4%.
  Not blocking (hold-last covers the gaps) but the plan's "10 ms absorbs the timeouts"
  expectation was optimistic; watch this number on the day.

## Changes committed with this report

1. **`rig\0_preflight.ps1`**: smoke-test `--sim-fs 24414` → `610.3516`. The old value
   ran sim 40× faster than hardware — the same rate that hid the arrival-window defect
   pre-08-13. Preflight now smokes at the real frame rate (and still passes).
2. **`rig\make_synthetic_impulse_capture.m` + `capture_synth_impulse.csv`**: committed
   positive-control fixture for `fit_impulse_model.py` (the 08-15 validation synthetic
   was never checked in). NOTE it uses tissue-speed poles 0.50/0.20, not
   make_synthetic_capture's 0.90/0.70: the fitter's null floor draws from ticks 31–48
   after each pulse and its +30-tick windows reach the next pulse's response, so a
   plant with a ~100 ms time constant leaks signal into the null and caps SNR at ~1.4×
   no matter the noise. That is a designed-in assumption (response dead inside the
   500 ms gap) which real tissue (23 ms settle) satisfies. Corollary for the rig: if a
   prep somehow responds with a time constant approaching the gap, the probe's null
   floor is invalid — lengthen `gapTicks`.

## Rig-only checklist (cannot be verified off-rig)

1. Synapse **recording ON for every run** (08-15 campaign has no delivery record);
   stimulator **charged** (08-14 lesson); **safety button ON** (08-12 lesson).
2. **Stim rate divisor**: still base/100 = 244.14 Hz as of run 5. If base/240 =
   101.7253 Hz can't be set, use `-FeatureWindow 30` or accept artifact wobble.
3. 30 s quiet capture → real per-channel `--baseline` in volts (~1e-4 expected);
   watch for the 16–23 mV saline-style transients in the quiet record.
4. **Emergency stim-zero, Synapse half**: saline run, Ctrl+C, confirm `Scle` → 0.
   (Wire half proven today.) Hard kill still bypasses handlers → ask the TDT circuit
   owner for an RZ2-side zero-on-UDP-silence watchdog.
5. Impulse probes per pair: RESPONDING = ≥3× null floor; nothing clears → debug stim
   delivery (sSig/battery/safety), do NOT fit.
6. ARX fit + second-seed validation; cross-check ARX DC-gain/time-constant vs the
   impulse report; **set `feature_map` in mpc_test.m** (the known trap).
7. Template hemisphere match: `site_provisional` is null in all 29 summary entries —
   day-of judgment call.
8. Deploy: recording started **LAST**; `-RWeight 1e-3`; `-TimeoutMs 10`; `-Pairs` =
   the identified pair; watch out0 motion vs events and 0/40 saturation.
9. Saline timing number — still unbanked (needs a recorded saline run).

## Run artifacts left in the tree (gitignored)

`rig_runrehearsal1.csv`, `loop_runrehearsal1.log`, `rig_runrdy01.csv`,
`loop_runrdy01.log`, `matlab_mpc_20260817_174503.log`,
`capture_mpc_20260817_174503.csv`, `mpc_lat_20260817_174503.csv`,
`sim_smoke.csv` (refreshed). Dry-run references live in the session scratchpad only.
