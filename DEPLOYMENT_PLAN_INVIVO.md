# In Vivo Deployment Plan — Biomimetic Closed-Loop (week of 2026-08-17)

Goal: stimulate VPL thalamus to reproduce, in S1 cortex, the feature-level response a
natural paw touch evokes. This document is the runbook; every tool it names exists and
was verified in sim on 2026-08-15 (`bench_test_reference_mpc.m` + end-to-end sim run).

## What the acute-array analysis fixes about this design

(From the 28-block control/coverage analysis, `Acute_array_control_and_coverage.pptx`.)

- **The plant is fast and near-static** (onset 7 ms, peak 13–15 ms, settle 23 ms,
  −3 dB at 12 Hz) — the 100 Hz loop is much faster than the tissue. Dead time 1–3 ticks.
- **Effective rank ~3 of 15 pairs** → identify and control 1–3 pairs, not all 8.
- **Observability is the constraint, not authority** (single-trial σ ≈ 87 µV vs
  ~2.1 µV/amp gain; stim out-drives touch ~5×). Judge tracking on averages over
  repeated events, not single trials.
- **Non-negativity is the binding constraint** (cosine 0.30 box-positive vs 0.76
  signed). If the target dips below the stim-free baseline, consider a **tonic bias**
  operating point (e.g. hold a0 = 20 via `--umin`-style floor... see "Bias option").
- **Gain drifts ~7% per 30 min** → re-identify at the start of every block; keep
  identification captures short (60 s) so this is cheap.

## Pre-rig (bench, no animal) — DONE 2026-08-15

- Float32 acquisition fix verified on hardware (campaign c04–c09, 6 clean runs).
- `make_excitation` kind **'impulse'**; MPC reference tracking with preview
  (`mpc_test(y, Rprev)`); `MPC_OPTS` tuning (rWeight!); server `referenceFile`;
  `4_mpc_server.ps1 -Reference/-RWeight`; `build_touch_reference.py`;
  `fit_impulse_model.py` (validated on a planted synthetic: gain/delay/linearity
  recovered exactly; underpowered plants correctly refused).

## Rig-day sequence

### 0. Preflight (10 min)
1. `.\rig\0_preflight.ps1` (PATH, exec policy). **Kill any stale MATLAB first** —
   a server that never received a packet blocks forever and holds port 31000
   (this caused run c10's failure): `Get-Process matlab,MATLAB | Stop-Process -Force`.
2. Synapse: recording ON for every run (the 08-15 campaign has no delivery record
   because no recording ran); stimulator charged (08-14 lesson); safety button ON.
3. **Check the stim rate divisor**: still base/100 = 244.14 Hz as of run 5. Intended
   base/240 = 101.7253 Hz gives exactly 6 acquisition samples per stim period so the
   artifact cancels in the feature window. If it cannot be changed, set
   `-FeatureWindow 30` (= 12.3 stim periods at 244 Hz, still integer-ish) or accept
   artifact wobble.
4. First 30 s quiet capture (no stim): note the resting feature value per channel —
   this is `--baseline` for the reference builder, in volts (~1e-4 expected in vivo).
5. **Verify the emergency stim-zero once, in saline/bench:** start a short live run,
   Ctrl+C mid-run, confirm "EMERGENCY STIM ZERO (console control event)" prints and
   `Scle` drops to 0 in Synapse. The handlers (Ctrl+C + crash-path) were added
   2026-08-15 and are code-reviewed but not yet exercised on hardware. A hard
   process kill still bypasses them — the durable fix is an RZ2-side watchdog
   (zero on UDP silence), worth asking the TDT circuit owner for.

### 1. Single-pulse impulse probe (5 min per pair)
```powershell
# Terminal A (per pair p = the pair under test):
.\rig\1_server.ps1 -Run probe1 -UMax 40 -Ticks 6000 -Channels <p> -Kind impulse
# Terminal B:
.\rig\2_loop.ps1 -Run probe1 -RZ2 10.1.0.100 -TimeoutMs 10
```
(1_server passes `-Kind` through to make_excitation; impulse = single-tick pulses
cycling [10 20 30 40], 500 ms apart → ~29 trials/amplitude in 60 s.)

Then, immediately:
```powershell
python rig\fit_impulse_model.py --capture capture_rig_runprobe1.csv --out-prefix probe1
```
Read the table: channels marked RESPONDING (≥3× null floor), their gain, delay,
linearity R² (acute arrays gave ~0.92). **If nothing clears 3×, stop and debug stim
delivery (sSig, battery, safety button) — do not proceed to a fit.**
Repeat for 2–3 candidate pairs; keep the 1–2 with the strongest, most distinct
responding channels (rank ~3 says more buys nothing).

### 2. Model training (10 min)
```powershell
# PRBS capture for the ARX fit (better spectral coverage than impulses alone):
.\rig\1_server.ps1 -Run fit1 -UMax 40 -Ticks 6000 -Channels <p> ; .\rig\2_loop.ps1 -Run fit1 ...
.\rig\3_fit.ps1 -Run fit1 -Sweep                  # confirm the same channel responds
.\rig\3_fit.ps1 -Run fit1 -Channel <c>            # fit; check valFit, time constant
# Second capture, different seed, for honest validation:
.\rig\1_server.ps1 -Run fit2 -Seed 777 ... ; loop ...
.\rig\3_fit.ps1 -Run fit1 -Channel <c> -Validate fit2
.\rig\3_fit.ps1 -Run fit1 -Channel <c> -Save      # -> AllModels(10).sys
```
Cross-check the ARX model's DC gain and dominant time constant against the
impulse report's gain and delay — they measured the same plant two ways; if they
disagree grossly, trust neither and re-probe.
**Then set `feature_map` in mpc_test.m to channel <c>** (the runbook's known trap).

### 3. Build the touch reference (2 min)
```powershell
python rig\build_touch_reference.py `
  --npz <BiomimeticInversion touch npz for this prep's site/hemisphere> `
  --channel <c> --baseline <measured resting feature, volts> `
  --scale 1.0 --repeats 20 --gap-secs 2 --out ref_touch.csv
```
- Template choice: prefer a block with high `split_half_corr` in
  `touch_targets_summary.json`, matched to hemisphere where known.
- The builder warns if the event modulation is under 10% of baseline. Options,
  in order of honesty: accept and evaluate on trial averages (20 repeats are built
  in for exactly this); raise `--scale` (a louder-than-life touch is still
  biomimetic in SHAPE); pick the template channel with the largest peak.
- Scale sanity: required Δfeature / plant gain (feature-units per amp) must be
  well inside uMax. The builder prints the peak delta; divide by the impulse
  report's gain.

### 4. Deploy (per attempt, ~1 min each)
```powershell
# Terminal A: -Pairs = the stim pair the model was identified on (word k on the
# wire drives bipolar pair k; a 1-output model with no -Pairs drives pair 1).
.\rig\4_mpc_server.ps1 -Reference ref_touch.csv -RWeight 1e-3 -Pairs <p>
# Terminal B (recording started LAST, then go):
.\rig\2_loop.ps1 -Run deploy1 -RZ2 10.1.0.100 -TimeoutMs 10
```
- `-RWeight 1e-3` is required: at the default 1 the controller *deliberately*
  settles short (absolute-u penalty, no integral action).
- `-TimeoutMs 10`: MPC compute is 0.5–3 ms and server turnaround p95 ~5 ms; the
  historical 5 ms timeout wastes ~5–20% of replies.
- Watch: `out0` must move when the reference events arrive (every ~2.2 s).
  Saturation at 0 or 40 through entire events = unreachable target → rescale.

### 5. Evaluate (same session, minutes)
- The server writes `capture_mpc_<stamp>.csv` (u and y per tick). Trial-average y
  around the known event start ticks (from `ref_touch_meta.json` timing) and
  overlay against the reference event: that is the primary tracking figure.
- Offline (PythonIntanAnalysis): trial-average the RAW `Wav1` around event starts
  and compare to the touch template waveform itself — the biomimetic claim is made
  at the waveform level, the tracking claim at the feature level. Keep them separate.
- Success ladder for the week: (a) commands move with the reference and evoke a
  measurable feature response; (b) trial-averaged feature tracks the event shape;
  (c) trial-averaged Wav1 resembles the touch template better than a
  constant-amplitude control does.
- Control condition worth one run: same total charge, constant amplitude, same
  event timing (`build_touch_reference.py` on a flat template or --scale 0 plus
  MPC_TARGET) — distinguishes "shaped stim matters" from "any stim there responds".

### Bias option (if targets prove unreachable from u=0)
The acute analysis says a tonic operating point (a0=20, modulate ±20) recovers most
of the signed-authority loss. Cheap version this week: set `MPC_OPTS.umin = 10`
(base workspace, before the server starts) so the loop rides a floor and can
modulate DOWN as well as up; re-fit the model AROUND that operating point (run the
PRBS capture with `-UMin 10`). Tissue-safety sign-off on continuous tonic stim is
the PI's call, not this document's.

## Saline validation 2026-08-17 (run sal1, block `ClosedLoopTest_LD-260817-195626`)

All-8-pairs jittered impulse probe, amps [5 10 18 25]. Audited with
`rig/validate_impulse_design.py` (design) + `rig/check_impulse_delivery.py` (block):

- **Bipolar mapping CONFIRMED with data: word k → electrodes (2k−1, 2k)**, all 8
  pairs, exact inversion (corr −1.000000, max|w1+w2| = 0), focality 300–3000×.
  UDP1→Scle onset match 855/855, delay ~2 ms.
- **Stim rate is STILL base/100 = 244.141 Hz** (Plse, 19,681 pulses) = 2.5
  acquisition samples per stim period, non-integer → for closed-loop runs use
  `-FeatureWindow 30` (= 12.0 periods) unless the circuit is changed to base/240.
- ~~OPEN: hold-last stretches probes / 5.1% pulse loss~~ **RESOLVED same night:
  probe runs now go through the C++ replay server** (`rig\1c_server.ps1` →
  `cpp_controller.exe --play`), which serves the MATLAB-designed, validator-audited
  CSV verbatim with no MATLAB in the real-time path. Sim-verified: capture ==
  design EXACTLY (max diff 0.0 over 7000×8), 0 lost, 0 stretched, 0 timeouts,
  turnaround avg 0.011 ms / max 0.101 ms (vs MATLAB's ~300 timeouts + 100 ms stalls).

### Saline sal2, 2026-08-18 (first C++-replay run on the rig)

- **Stim rate FIXED and verified: 101.7253 Hz = base/240 exactly** (8,805 Plse
  pulses), **6.000 acquisition samples per period** → the default
  `-FeatureWindow 6` is now correct; the `-FeatureWindow 30` fallback is obsolete.
- **C++ replay path perfect on the wire on real hardware**: 925/925 designed
  pulses in UDP1, 0 lost, 0 stretched. Pair mapping re-confirmed.
- **Carrier-latch beat (the remaining, now-quantified physicality):** the
  command clock (~99.24 Hz effective, 10.076 ms) free-runs against the 101.73 Hz
  carrier (9.830 ms), phases sliding through each other every ~0.4 s. Each
  single-tick probe therefore gates **1 pulse 93.8%** of the time, **2 pulses
  4.2%** (phase-aligned), **0 pulses 1.9%** (window falls between latches —
  silent physical miss despite perfect UDP/Scle delivery).
  `check_impulse_delivery.py` now measures this per run. Analysis handling:
  missed probes = no-stim trials (dilute the trial average ~2%), doubles = 2×
  charge 9.8 ms apart (within the 23 ms settle). Acceptable and quantified for
  probing; the DURABLE fix is circuit-side — one-shot/triggered StimGen instead
  of a free-running carrier — or pacing the loop tick off the PO8e frame clock
  (6 frames = exactly one carrier period, RZ2-crystal-locked). Ask the circuit
  owner alongside the watchdog request.
- Same-word spacing held the design (min 518 ms ≈ the 52-tick floor; median
  581 ms). Pulses that "look closer" are DIFFERENT pairs interleaving — pooled
  across 8 pairs the median spacing is 59 ms with a designed 30 ms guard;
  that is intentional, per-pair analysis is unaffected.

### MATLAB-free probe path (preferred for probes from 2026-08-18 on)

```powershell
# Terminal A (design once offline in MATLAB, validate, then C++ serves):
.\rig\1c_server.ps1 -Run sal2 -Seed 777          # amps 5,10,18,25 + 80ms jitter defaults
# Terminal B, unchanged:
.\rig\2_loop.ps1 -Run sal2 -RZ2 10.1.0.100 -TimeoutMs 10 -Ticks 7000
# post-run, unchanged: validate_impulse_design.py + check_impulse_delivery.py
```
For tissue probing pass `-Channels <p>` (one pair) and the day's `-UMax`.

### Full C++ backup for the CLOSED loop (if MATLAB must go entirely)

`cpp_controller.exe --mode mpc --model <plant.lti> --reference ref_touch.csv
--pairs <p> --r-weight 1e-3 --output-count 8 --capture <csv> --log <csv>`
(plant via `export_plant_lti('<name>.lti', 10)` after `-Save`). Sim-verified:
observer pole 0.892246 = MATLAB's exact value, per-tick reference + pair
mapping work, turnaround 0.014 ms. **Known gap: NO horizon preview** — the C++
MPC tracks the reference reactively (~1-tick lag on event onsets), so the
MATLAB server (`4_mpc_server.ps1`) stays the PRIMARY tracking path; this is
the fallback if MATLAB misbehaves on the day.

## Known watch items going in
- 5–8% localhost timeouts at `-TimeoutMs 5` (fix: 10 ms, above).
- Occasional 16–23 mV feature transients in saline runs c05–c09, uncorrelated with
  commands (motion/bubbles suspected). If they appear in vivo they will dominate a
  mean-abs feature tick — worth watching in the quiet capture.
- Saline timing number was never banked (no recordings on 08-15); the +1-tick
  transport delay IS empirically proven from `UDP1` (2026-08-11), so this does not
  block deployment.
- All feature-based data from before 2026-08-15 is invalid (int16/float32 misread).
```
