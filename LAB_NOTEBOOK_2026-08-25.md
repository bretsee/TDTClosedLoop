# Lab notebook — 2026-08-25 (pre-suite prep day)

Context: system moves to the surgical suite tomorrow (Wed 2026-08-26, saline
session there); acute experiment Friday 2026-08-28. Full plan discussed and
approved today; this session implemented and verified the code half. Commit
`3987991` (bench 22/22, selftest 13/13, sim acceptance below).

## What was built (all verified today, no hardware needed)

1. **`schedule='random'` probing** (make_excitation + validator + 1c_server +
   bench). One global train; every probe's (pair, amplitude) drawn without
   replacement from a balanced block-shuffled deck — the channel is genuinely
   randomized per pulse (the old 'interleaved' was an emergent stagger, near
   round-robin; amplitudes cycled deterministically). Friday parameters:
   `-Schedule random -PulseAmps 2,4,6,9,13,18,25 -GapTicks 36 -GapJitterMs 60
   -Ticks 183000` → 56 conditions, **~76 trials/condition in ~30 min**, zero
   epoch contamination by construction (gap 36 > pre 5 + post 30). Generated
   `design_runrndtest.csv` end-to-end: DESIGN VERIFIED 0/0/0; balance 75–76;
   channel/amp transition chi-square uniform; legacy validator output
   byte-identical on `design_runsal2.csv`.
2. **2x-LFP-rate option** (`--stream-fs`, W2). The only hardcode was
   `streamFsNominal` (two sites); now a flag with a stride cross-check
   (warns loudly when `streamFs × offset-step ≠ 24414.0625` — catches both
   forgetting the flag after the circuit change and using it before).
   `2_loop -StreamFs/-SimFs`, `0_preflight` SimFs, `check_impulse_delivery
   --fs-acq`. `build_touch_reference` constant renamed
   `TEMPLATE_SAMPLES_PER_TICK` (do NOT bump to 12 — references are per-tick
   and unchanged). Sim acceptance at 1220.703125 / `--tick-frames 12` /
   window 12: 1000/1000 ticks, 0 dropped, PLL phaseErr 0, ~101.7253 Hz,
   window contents exact vs an independent numpy recomputation.
   **Friday uses 2x ONLY if tomorrow's saline validation passes.** MATLAB
   side needs nothing (Ts measured from data; 12/1220.703125 == 6/610.3515625).
3. **`--feature-trim K`** (W6): drop the K largest-|x| samples per feature
   window — removes the artifact sample at any carrier phase. Default off
   (trim-0 path untouched); sim A/B vs numpy exact; `2_loop -FeatureTrim`;
   archived-build strip list extended (`aug20`, `aug25-pre`).
4. **`rig/assess_artifact.py`** (W3): stim-locked artifact quantification
   from any block. `--events probe` (command onsets) or `pulse` (every
   carrier pulse, amp looked up from Scle — needed for envelope blocks like
   LD-260812). Quiet-segment baseline; feature simulation with trim; **own-
   pair electrodes (2k−1, 2k) excluded from the verdict** (always saturated,
   never controllable).
5. **`rig/tracking_metrics.py`** (W4): the rapid-results workhorse. Joins a
   reference CSV with a capture; RMSE/NRMSE, Pearson at lag 0/best lag,
   slopes y-on-r and u-on-r, tracking index, event-triggered averages,
   TRACKING/MARGINAL/NOT-TRACKING verdict, JSON + PNG. `--self-test` passes
   (identity r=1/slope=1/lag=0 + shuffled control ~0).
6. **`training/synthesize_openloop_nn.py`** (W5): reference → inverse policy
   → open-loop stim tape for `--play`. Exact `NnController::step` replication
   (history priming, residual-after-activation, GRUCell r,z,n, clamp-then-
   slew; CLI clamps win — the .nnw out_min/out_max are NOT consulted at
   runtime, verified in main.cpp). `--parity` vs the live C++ NN server:
   **3.7e-9** on a 1300-tick tape. Refuses `# mode: forward` models.
7. **`scripts/build_experiment_report.py`** (W7): manifest-driven next-day
   deck (Arial, black headings), everything recomputed from artifacts;
   dry-run against today's outputs → 5 slides.

## Findings (advance answers for Friday)

- **Artifact assessment (the colleague's question): there is NO blanking
  anywhere in the chain and none evident in the recordings** (artifact spans
  ms-scale, vs Choi's 480 µs hardware sample-and-hold). BUT the structural
  mitigations hold in saline: on the stim pair's OWN electrodes the artifact
  is huge and focal (LD-260812 sOut: 63x/43x baseline std — reproduces the
  banked 40.2x/27.0x measurement); on the OFF-pair (controllable) channels it
  is only **0.8–2.7x the noise floor** at amps 18–25. Verdict ARTIFACT
  MODERATE on both assessed blocks. The in-band, in-vivo answer comes from
  running `assess_artifact.py` on Friday's first probe block (bigger evoked
  signals AND bigger artifacts); `--feature-trim` is built and validated as
  the fallback if it comes back DOMINANT.
- **`Wav1`/`Wav2` STORES ARE ZERO in the 08-18 saline blocks** (sal2 checked;
  only sOut/IZn1/Scle/sSig/Plse live). The PO8e STREAM was live (features
  were real), so this is a disk-saving configuration issue, not acquisition —
  but artifact/evoked analysis needs the stored Wav1. **Tomorrow: enable
  Wav1/Wav2 saving in the Synapse recording setup and confirm on the quiet
  capture.**
- **Bench false-fails against the STAGED AllModels.mat**: with the rehearsal
  file (toy@9, saline junk fit@10) three reference-tracking bench tests
  legitimately null out (zero-gain model at slot 10 → u pinned at uOffset).
  Run the bench against the committed AllModels.mat (`git stash`-style swap)
  or expect exactly those 3 failures. All 22 pass on the committed file.
- **NN training wall-clock on a 28k-tick capture (RTX 4090, 200 epochs,
  history 25): linear 14 s, mlp 15 s, residual_mlp 17 s** (GRU pending —
  slower with TBPTT; see models/bench_*.nnw). Training 3–4 models between
  arms on Friday costs ~1–2 min plus the GRU. Never train during a live loop.

## Evening rig session — cl4/cl5 BANKED (the last pre-suite validations)

Both runs: frame-locked (`-TickFrames 6`), toy plant at `AllModels(9)`,
`-RWeight 1e-3 -Pairs 1 -FeatureChannel 1`, 1300 ticks, recording-last order.
Engineering clean on both: 1300/1300 ticks, `droppedControlTicks=0`, window
6/6/0, server turnaround ~2 ms avg.

**cl4 — moving-target tracking PROVEN** (`ref_steps.csv`, Nu=2;
`capture_mpc_20260825_212708.csv`, scored by `tracking_metrics.py` →
`tracking_cl4.{json,png}`):

- u1 plateaus **0.00935 → 0.01355** locked to the reference steps
  (r 0.001442 → 0.001875), std ~0.0011, corr(u1, r) = 0.886,
  step gain Δu/Δr = **9.7**.
- "Looked like all zeros" at the rig was pure scale: the reference is
  feature-space volts (~0.0014), so optimal commands are ~0.01 amplitude
  units — invisible on displays calibrated for 5–25.
- Slope 9.7 vs the certainty-equivalence 4.9: the observer pushes harder
  because the saline "plant" never responds to u (measured y ~0.0009
  regardless), so the state estimate keeps correcting downward. Correct
  closed-loop behavior against a dead plant, not a defect; with a real
  fitted plant the loop settles at the certainty-equivalence point.
- y-channel verdict NOT TRACKING = the expected saline null. For these two
  runs the readout is u-on-r, not y-on-r.

**cl5 — Nu QUESTION SETTLED** (`ref_rehearsal.csv` touch-template rehearsal,
**`-ControlHorizon 20`**; `capture_mpc_20260825_213442.csv` →
`tracking_cl5.{json,png}`):

- slope u1-on-r = 7.8; 5 template events detected at their exact 220-tick
  spacing.
- **Transient fidelity du/(slope·dr) ≈ 1.0–1.3** — the u event swing
  (0.00258 on a 0.000257 reference event) is FULL amplitude, vs **cl3's
  ~2–3% at Nu=2** (2026-08-20). A ~40x recovery from one flag.
- **STANDARD SET: every touch-template MPC arm on Friday runs
  `-ControlHorizon 20`.** This also makes open-vs-closed fair: Choi's
  offline synthesis optimizes every tick independently, and Nu=20 gives
  the closed-loop arm the same freedom.

First real-data outing for `tracking_metrics.py`: verdicts, slopes and ETAs
all behaved; the JSON/PNG pairs are ready for the Friday report manifest.

## Still pending before Friday

- Suite saline session (tomorrow): quiet capture + 60 Hz quantification;
  **enable Wav1/Wav2 SAVING in Synapse** (stores were zero in the 08-18
  blocks); artifact retest at higher amplitude (then final trim decision);
  randomized-probe delivery validation; **2x-rate saline gate** (positive +
  negative stream-fs tests); frame-locked closed-loop dress rehearsal.
- `git push` (repo ahead of origin; user will push after tomorrow's
  successful suite test).
