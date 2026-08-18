# Lab Notebook — 2026-08-18 (Tuesday)

**Session goal:** validate the redesigned impulse probe (new amps, jittered gaps,
C++ replay) on the rig, verify the stim-rate fix, and resolve the carrier-sync
problem before more seeds. **Outcome: probe delivery is bit-perfect end to end,
both probe protocols are hardware-validated, and the last engineering blocker
(Ts alignment) is closed. One regression was introduced, diagnosed from rig data,
and fixed same-day.**

## Timeline

| Run / block | What happened |
|---|---|
| sal2 (`LD-260818-143352`) | First C++-replay rig run. **Stim rate fix VERIFIED: carrier 101.7253 Hz = base/240 exactly, 6.000 acquisition samples/period** → `-FeatureWindow 6` default now correct. Wire perfect: 925/925 designed pulses, 0 lost, 0 stretched (vs MATLAB sal1's 12 stretched + 5.1% lost). Pair mapping re-confirmed. NEW issue quantified: **carrier-latch beat** — command clock 99.244 Hz free-runs vs the 101.7253 Hz carrier (beat ~0.4 s) → per single-tick probe: 1 pulse 93.8%, 2 pulses 4.2%, 0 pulses 1.9% (silent physical miss). "Pulses closer than design" explained: cross-pair interleaving (median 59 ms pooled), same-word spacing held (min 518 ms). |
| decisions | Circuit stays as-is (user); sync fixed loop-side. Two probe protocols: **sequential** (contiguous per-pair blocks, fully independent channels — clean baseline; default 28000 ticks ≈ 4.6 min, ~15 trials/amp/pair) and **interleaved** (retained; configurable `-CrossGuardMs`; seq-vs-int kernel contrast = interim cross-pair interaction probe). Formal additivity protocol deferred until kernels exist. |
| seq1 v1 (`LD-260818-160640`) | **Frame-lock v1 REGRESSED.** v1 fired ticks on ingested-frame count; sim was clean, but hardware frames arrive in irregular chunks → tick jitter ±2.5 ms (4–8 frames/tick) → **21.6% missed / 21.0% doubled**. Rate was perfectly locked (9.8304 ms mean); timing was not. **Lesson: rate lock ≠ phase lock, and sim cannot exhibit arrival burstiness.** |
| v2 fix | **Software PLL**: ticks fire on the smooth PC clock, period+phase steered onto the frame-counter grid (phase gain 0.05/slew 250 µs, freq gain 0.0015); grid origin **quantized to absolute counter multiples**; new `--tick-phase-us` trim; `check_impulse_delivery.py` measures command→latch delay + boundary margin per run. |
| seq1 v2 (`LD-260818-173226`) | **PERFECT: 476/476 probes = exactly one carrier pulse (0 missed, 0 doubled)**, phaseErr avg 0.65 ms, 0 resyncs. First clean sequential dataset. |
| int1 (`LD-260818-175148`) | Interleaved validated: 923 probes, 0 missed, 2 doubled (0.2%) — phase landed 1.97 ms from a latch (racing regime edge). |
| int2 (`LD-260818-180721`) | **Decisive phase test** with `-TickPhaseUs -2949`: preserved phase would have read 4.92 ms, read **7.91 ms** → **the PO8e counter zeroes at recording start, so grid-vs-carrier phase re-rolls every recording.** Trim is a per-run diagnostic, NOT a set-once calibration. Run itself flawless: 923/923 at only 1.93 ms margin. Empirics (3 PLL runs: margins 3.7/1.97/1.93 ms → races 0/2/0): only margins < ~1.5 ms race → ~70% of runs perfect, rest ~0.2% doubles (auto-excluded by the fitter). **Policy: leave trim unset; per-run audit governs.** |

## Offline analyses (no rig)

- **Per-pair kernel fits, 24/24 correct refusals** (seq1/int1/int2 × inputs 1–8):
  best SNRs 0.5–2.0×, no repeatable input→channel structure — clean negative
  control on real multi-pair hardware data, both schedules. With the synthetic
  positive fixture, the go/no-go gate is now proven in both directions.
- **Seq-vs-interleaved contrast: null** (as predicted in saline) — tissue baseline
  established; divergence in tissue = cross-pair interaction signal.
- **Artifact cancellation: INCONCLUSIVE** — stim artifact only 1.2–1.3× the
  saline Wav1 noise floor (~10 mV RMS, ~100× the expected in-vivo floor; likely
  the bath arrays). Simulated MAV6 (1.12×) vs MAV5 (1.08×) indistinguishable.
  **Action: artifact-amplitude saline retest before deployment** (runbook).

## Ts alignment (closes the last engineering blocker)

Model Ts is now the source of truth: `fit_sysid_from_capture` **measures** the
tick period from the capture's `t_ms` (snaps to 10 / 9.8304 ms) and stamps the
model; `mpc_test` follows the model's Ts (no resampling — a tick is a tick;
warns >5% off nominal); `export_plant_lti` carries Ts into the `.lti`.
Reference CSVs were already frame-native (row = 6 samples = one frame-locked
tick; wall-clock playback stretches 1.7%). Bench suite **13/13**.
**Frame-locked closed loop UNLOCKED — capture and deploy must share the tick
mode (`-TickFrames 6` both, or neither).**

## Artifacts

- Commits (all UNPUSHED, `bb1c369`..`7d5a28e` today on top of yesterday's):
  sal2 analysis; protocols+frame-lock v1 (`d9d1fcf`); PLL v2 (`689f9c9`);
  carrier-sync closure (`be84f10`); phase-stability correction (`a637b66`);
  decisive-test verdict (`f552582`); Ts alignment (`7d5a28e`). **Push before
  the next rig day.**
- Binaries archived: `MpcPo8eUdpClosedLoop.aug18-tickframes.{exe,pdb}` (v1),
  `aug18-pll.{exe,pdb}` (v2 = current exe).
- Captures: `capture_rig_run{sal2,seq1,int1,int2}.csv` + designs + blocks above.

## Tomorrow (pre-deployment saline session, ~30 min + retest)

1. 30 s quiet capture → per-channel `--baseline` + noise-floor characterization.
2. Emergency stim-zero, Synapse half: Ctrl+C mid live run → `Scle` → 0 in block.
3. Closed-loop dress rehearsal on hardware, frame-locked end to end
   (probe capture `-TickFrames 6` → `3_fit` → `4_mpc_server -Reference` +
   `2_loop -TickFrames 6`) → banks MPC-on-hardware + the saline timing number.
4. Artifact-amplitude retest (different array/contact or higher amplitude).
5. `git push`.
