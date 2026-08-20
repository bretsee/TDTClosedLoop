# Validation Plan — updated 2026-08-19

Supersedes the "remaining pre-deployment saline session" list in `LAB_NOTEBOOK_2026-08-18.md`.
Context for this revision:

1. The saline test rig is MOVING TO THE SURGICAL SUITE for the final pre-deployment test.
   Background noise and the electrical environment (60 Hz line pickup in particular) will change.
2. New evaluation goals raised 2026-08-19: (A) rapid model-type swapping, (B) open-loop
   (offline-optimized) vs closed-loop MPC as a scientific comparison, (C) horizon / settle-time
   assumptions, (D) thresholding of stimulus commands.
3. No rig time was available 2026-08-19; all Phase-0 items below are off-rig code work.

---

## 1. What the move to the surgical suite invalidates — and what it does not

### Carries over unchanged (environment-independent: depends on clocks, wires, and code, not the bath)

- UDP transport bit-exactness (corr 1.000, +1 tick, 2026-08-11).
- Pair mapping: word k -> electrodes (2k-1, 2k), inversion exact (2026-08-17).
- Stim carrier 101.7253 Hz = base/240, 6 samples/period (2026-08-18).
- Frame-locked PLL tick (v2): 476/476 and 923/923 single-carrier-pulse delivery; per-run
  phase audit policy (trim unset).
- Float32 buffer-contract crash fix and the 6/6 clean campaign.
- Backlog fix + "recording starts LAST" operational order.
- Ts alignment (model Ts is source of truth; capture and deploy must share tick mode).
- Stale-reply policy, emergency stim-zeroing code paths (logic verified; the on-rig
  Ctrl+C -> Scle=0 check remains pending and is environment-independent).
- C++ replay path capture==design (0.0 max diff).

### Void or re-measure in the suite (anything referenced to recorded signal amplitude/noise)

| Item | Status | Action |
|---|---|---|
| Saline noise floor (~10 mV RMS Wav1) | void | Re-measure: quiet capture in suite (Phase 1.1) |
| Artifact-amplitude ratios (1.2-1.3x floor, INCONCLUSIVE) | void (was inconclusive anyway) | Retest in suite with better arrays/contact (Phase 1.3) |
| Touch-reference `--baseline` / `--scale` | never banked | Must be measured DAY-OF in the suite (was always the plan) |
| Saline timing number | never banked | Bank during suite dress rehearsal (Phase 2) |
| Detection floors in fit_impulse_model / timing_check | self-adapting | Empirical per-capture (circular shift / pulse-free ticks) — they recompute automatically, but detection POWER will differ; re-establish with a suite probe run (Phase 1.4) |

Net: **nothing already banked is lost.** Every environment-referenced number was either never
banked or already scheduled for retest. The engineering validations all carry.

### 60 Hz line noise — audit result (2026-08-19 code audit; framing CORRECTED 2026-08-20)

**Correction (user, 2026-08-20): the RZ2's onboard DSPs filter the streamed signal BEFORE it
reaches this PC** — roughly the Choi 2016 LFP chain (their published numbers: broadband
0.2-8.5 kHz at 24.4 kHz -> 480 us sample-and-hold blanking -> 5-200 Hz band-pass -> 610 Hz).
So the audit statement below applies to the **PC-side chain only**: from the PO8e onward there
is no filtering — not a notch, not a highpass, not a detrend, in C++ or fitting scripts. The
PC chain is (already-filtered) sample -> |x| (or signed mean, --feature-signed) -> 6-sample
mean -> UDP. Conditioning in the fitters is mean/baseline subtraction only
(`fit_sysid_from_capture.m:149-152`, `fit_impulse_model.py:66`, `timing_check.py:59-60`).
Note 60 Hz sits INSIDE a 5-200 Hz LFP passband, so upstream filtering does not remove line
noise unless the RZ2 circuit also has a notch — the suite quiet capture answers that
empirically either way.

Consequences:
- The 6-sample MAV window (9.83 ms) spans 0.59 of a 60 Hz cycle — line noise does NOT average
  out. The rectified line component (120 Hz) aliases through the ~100 Hz tick grid to a slow
  ~18-20 Hz beat in the feature, inside the band the excitation excites.
- ARX fitting can absorb a coherent line-noise beat as extra fake states (the parsimony guard
  at `fit_sysid_from_capture.m:73` mitigates but does not eliminate this).
- Null floors RISE with line noise (both null constructions preserve autocorrelation) —
  protective against false positives, but masks real responses.
- No feature-window length can cancel both the stim carrier (multiples of 6 samples) and 60 Hz
  (10.17 samples/cycle, non-integer). A window fix is not available; a filter would be needed.

**Decision rule:** quantify the 60 Hz + harmonics component in the suite quiet capture FIRST
(Phase 1.1). Only if it dominates the feature variance do we add a filter. Options, cheapest
first: (a) fit-side notch in the Python/MATLAB fitters (no C++ rebuild; closed-loop feature
stays raw); (b) a small IIR notch or 60 Hz-synchronous comb in the C++ feature path (rebuild,
archive binary first). Do not build either until the suite measurement says it is needed.

---

## 2. (A) Model modularity — audit result and gap list

### What is already easy (supports "multiple model types in rapid succession")

- **LTI models:** `fit_sysid_from_capture` (ARX 1..8, parsimony pick, stability gate) writes
  `AllModels(10).sys`; `export_plant_lti.m` writes `.lti` for the C++ MPC. Swap time: seconds
  (C++, `--model x.lti`, restart process) or ~30 s (MATLAB server restart). No rebuild.
- **NN models:** `training/train.py` (archs linear | mlp | residual_mlp | gru, `--history K`,
  inverse or forward) -> plain-text `.nnw` -> `cpp_controller --mode nn --model x.nnw`.
  C++ inference supports linear/residual layers (none|relu|tanh) and GRUCell. Swap: seconds.
- Controller/model choice is runtime config end to end; the loop is model-agnostic
  (`--controller localhost`). Nothing in a normal model swap requires a rebuild.

### The acute-dataset models do NOT port directly (audit finding)

The NNController acute models answer a different question: (pair one-hot x amplitude) ->
flattened evoked waveform, at acute-recording time base. The rig contract is per-tick
features -> stim at ~100 Hz. Also: NNController uses `nn.GRU` (not GRUCell), has archs the C++
cannot run (tcn/transformer/film/...), and no `.nnw` exporter exists for its checkpoints.
**Conclusion: retrain on rig capture CSVs with `TDTClosedLoop/training` (same arch family as
the acute search winners — residual_mlp is available). What ports from the acute work is the
ARCHITECTURE RANKING and the touch templates (via `build_touch_reference.py`), not weights.**
This also matches the acute finding that the map is ~linear: the rapid-succession comparison
should lead with ridge/ARX-order sweeps and use NNs as the "does nonlinearity buy anything"
arm, mirroring the acute conclusion.

### Friction items to fix (Phase 0)

- A1. `mpc_test.m:431` hard-codes model slot 10 and ignores the `MPC_TARGET` variable already
  stored in AllModels.mat. Make it read `MPC_TARGET` (default 10). Removes an edit-the-source
  step from every multi-model session.
- A2. `feature_map` is a hand-edited function in `mpc_test.m` (`3_fit.ps1:87-91` instructs the
  operator to edit source at the rig). Promote to `MPC_OPTS.featureChannel` / server cfg.
- A3. `4_mpc_server.ps1` exposes only `-RWeight`. Add `-Horizon -ControlHorizon -QWeight -UMax`
  (pass-through to MPC_OPTS). Needed for (C).
- A4. **Latent defect:** `fit_sysid_from_capture` fits on mean-removed data and stores
  `uOffset/yOffset` in SYSID_INFO, but `mpc_test`, `export_plant_lti`, and cpp_controller all
  run the model on RAW features — an operating-point mismatch invisible on the toy plant.
  Fix before any closed-loop run on a fitted model: apply offsets in the controller
  (y_meas - yOffset in, u + uOffset out) or refit with affine augmentation.
- A5. **Safety gap:** nothing stops deploying a `forward` model as a controller — `.nnw` has no
  mode field (`training/README.md` documents the convention in prose only). Add `mode` to the
  .nnw header + exporter, and make `--mode nn` refuse a forward model without an override flag.

---

## 3. (B) Open-loop vs closed-loop — what exists, what to build

Exists today:
- Open-loop REPLAY is first-class and hardware-proven: `cpp_controller --play design.csv`
  (verbatim, zeros after last row, no clamps in the play path) via `1c_server.ps1`.
- Closed-loop MPC: `4_mpc_server.ps1` (MATLAB, 20-tick reference preview) or
  `cpp_controller --mode mpc` (constant target only, NO preview — MATLAB stays primary for tracking).

Does NOT exist: any offline computation of an OPTIMAL open-loop u trajectory. Two build routes
(both small, both use committed pieces):

- B1 (**preferred, ~5 lines**): `training/closed_loop_sim.py` already runs the controller
  against the model plant over the wire protocol and holds the full `us` history — dump it to
  a `tick,u1..uM` CSV (same format as `write_excitation_csv.m`). Because the sim plant IS the
  model, the resulting trajectory is the certainty-equivalent open-loop optimum. Replay on
  hardware with `--play`.
- B2 (optional, exact single-shot): `mpc_test` already assembles the full condensed QP; with
  Nu=N and one call carrying the full reference, the whole `z = [u_0..u_{N-1}]` is the
  open-loop optimum — currently truncated to `z(1:m)` at `mpc_test.m:110`. Expose full-z
  behind an option.
- B3 (for a pure-feedforward arm): `P.useObserver` is hard-coded true at `mpc_test.m:204`.
  Expose as an MPC_OPTS field (with a loud banner — running open-loop silently was the
  historical defect, so this must never be a silent default).

**Planned three-arm scientific comparison (Phase 3):** identical reference, identical session:
(1) open-loop optimal replay (B1) — optimization with zero feedback;
(2) closed-loop MPC (observer on) — real-time re-optimization;
(3) NN inverse policy (`--mode nn`) — learned feedback, no optimization.
Primary outcome: tracking error vs reference; secondary: total charge (sum of u), robustness to
operating-point drift (arm 1 should degrade first — that degradation IS the scientific result
quantifying the value of feedback).

---

## 4. (C) Horizon and settle-time numbers — current state and expansion knobs

Current MPC (verified in source 2026-08-19):

| Quantity | Value | Where |
|---|---|---|
| Prediction horizon N | 20 ticks = 200 ms (196.6 ms frame-locked) | `mpc_test.m:222`, `mpc_controller.hpp:40` |
| Control horizon Nu | 2 moves, then hold-last | same |
| Reference preview | 20 ticks (cropped/padded to N) | `matlab_controller_server.m:96` |
| Measurement history | RECURSIVE — 1 new measurement/tick into a Kalman observer; state dim = ARX order (sweep 1..8, parsimony-picked) | `mpc_test.m:71-81`, `fit_sysid_from_capture.m:62,73` |

So the MPC "takes into account": one fresh sample per tick (the observer state summarizes the
past — order na, i.e. effectively the last ~na ticks of dynamics), and looks ahead 200 ms.
The only true multi-sample history window in the system is the NN path's `--history K`.

Baked-in settle-time assumptions (the ones the "conservative" concern applies to):

| Assumption | Value | Where |
|---|---|---|
| "tissue settles in ~23 ms" | comment + gapTicks=50 (500 ms) default | `make_excitation.m:24-26,97` |
| Impulse epoch window | post-ticks 30 = 300 ms | `fit_impulse_model.py:78` |
| Null-floor draw region | pulse-free ticks 31..48 post-pulse | `make_synthetic_impulse_capture.m:21-27` |
| Evoked-response peak | 15-28 ms | `MpcPo8eUdpClosedLoop.cpp:573` (feature-window rationale) |
| Settle convention | 4*tau from fitted dominant pole | `fit_sysid_from_capture.m:420-421` |

**If observed responses settle slower than ~300 ms, the epoch window and the null region
collide with the next pulse's tail and the fitter's SNR is capped (documented at
`make_synthetic_impulse_capture.m` — a slow plant caps SNR ~1.4x regardless of noise).**

Expansion knobs — all flag-level except N:
- `fit_impulse_model.py --post-ticks` (raise 30 -> 50+), `--pre-ticks`.
- `1c_server.ps1 -GapTicks` (raise 50 -> 80-100 if response tau approaches the gap); keep
  `-Ticks` scaled up to preserve trials/amp.
- MPC N via MPC_OPTS (A3 adds `-Horizon`). Raise N so N*Ts comfortably covers the observed
  settle (e.g., 500 ms settle -> N >= 50). Cost: QP size is m*Nu (unchanged), only the
  condensed matrices grow — negligible at this scale.
- Rule of thumb to apply from the FIRST suite kernel fit: read tau from the fitted dominant
  pole, set post-ticks >= ceil(5*tau/Ts), gapTicks >= 2x that, N >= 4*tau/Ts.

---

## 5. (D) Stimulus thresholding — literature verdict and design

Full annotated bibliography in the 2026-08-19 session notes; key conclusions:

**Verdict: an amplitude-aware objective term is worth adding and is nearly free, but it is
provably NOT sufficient for a minimum-effective-amplitude guarantee.**

- Because u >= 0 already, an L1 penalty is a pure LINEAR cost `lambda*sum(u)` — implemented by
  adding `lambda*(S'*1)` to the QP's linear term. No variable splitting, no new constraints,
  OSQP setup unchanged, lambda has units of "price per uA-tick of charge." It DOES produce
  exact zeros (screening: a channel stays off unless its marginal tracking benefit exceeds
  lambda).
- But no convex penalty can produce a minimum-nonzero-amplitude GAP: `{0} U [u_min, u_max]` is
  disconnected, and convex solutions vary continuously with the reference — small nonzero
  commands are generic. (Chatterjee/Nagahara et al. 2016: in singular problems the L1
  relaxation is non-sparse. Our plant is exactly that regime: acute analysis found rank ~3
  from 8+ pairs with non-negativity binding.)
- **Direct precedent in this exact preparation: Choi, Brockmeier, Francis et al. 2016
  (J. Neural Eng. 13:056007)** — VPL thalamic microstimulation -> rat S1, linear state-space
  model, QP-optimized stimulus amplitudes to reproduce touch-evoked responses. They hit this
  same failure mode and put a THRESHOLD GATE IN THE PLANT MODEL (threshold 4-10 uA,
  attenuation 0.1-0.2) "to prevent the optimization from relying on ineffectual subthreshold
  amplitudes." Cite this; follow its forward citations.
- Thresholds are per-channel, per-subject, drift over time (Greenspon 2025: median detection
  14.5-61.5 uA across humans), and depend on co-active neighbors (Kunigk 2022: synchronous
  pairs at <600 um halve per-site threshold). So u_min must come from a per-pair calibration
  (amplitude staircase -> evoked amplitude), not from literature constants.
- Precedent that gated stim can BEAT always-on: Little et al. 2013 adaptive DBS.

**Implementation ladder (in order; stop when behavior is acceptable):**

- D0. Solver hygiene first — the MATLAB OSQP setup (`mpc_test.m:196`) runs at DEFAULT
  eps_abs=eps_rel=1e-3 with polishing OFF; at umax 40 that is real numerical junk on every
  channel. Set polish=true, eps ~1e-6, clamp |u|<1e-8 to 0. Some of the small-nonzero symptom
  may not be real. (C++ box-QP already at tol 1e-7; add the same tiny-value clamp.)
- D1. Move effort penalty from quadratic R to linear lambda: quadratic R on a redundant
  low-rank plant actively SPREADS drive across channels (ridge behavior) — R alone explains
  "many small amplitudes" in the 8-pair case. Keep a tiny R for conditioning. Side benefit:
  removes most of the known settle-short bias (u* = r*g/(g^2+R/Q)) since the linear term
  shifts rather than scales the optimum.
- D2. Solve -> threshold at u_min -> RE-SOLVE restricted box QP (surviving channels bounded
  [u_min, u_max], others fixed 0), warm-started; add hysteresis (u_on > u_off) and a minimum
  dwell (N_dwell ticks) to prevent 100 Hz chatter. Two small QP solves fits the 10 ms budget
  trivially. The re-solve step reallocates discarded drive and debiases L1 shrinkage — this
  is the difference between this and naive clipping.
- D3 (only if D2's suboptimality proves to matter): exact semi-continuous MIQP on the FIRST
  MOVE only (8 binaries; miOSQP-style warm-started branch-and-bound, or exhaustive 256-support
  enumeration for a deterministic worst case). Affordable at this size; not first choice.
- D4 (scientifically strongest formulation, for the paper): Choi-style soft gate in the plant
  model (attenuate below threshold) so the OPTIMIZER'S MODEL matches the biology. Nonconvex;
  pairs naturally with D3 machinery. Defer until real kernels exist.

**Insertion points (from the code audit):**
- Primary: `mpc_test.m` immediately after the clamp at line 114 (BEFORE `P.u_last = u`, so the
  observer predicts from the u the plant actually saw). C++ twin: `mpc_controller.hpp:154-156`.
- Wire-path hard floor (defense in depth, all controllers, needs rebuild): inside
  `clamp_amplitudes_f32` (`MpcPo8eUdpClosedLoop.cpp:400-413`) + its cached twin.
- Interaction to handle: hold-last stale policy re-sends a >u_min command for up to 250 ms —
  dwell logic must count re-sends, and the threshold must be applied controller-side so
  held values are already thresholded.

---

## 6. Work queue

### Phase 0 — off-rig code (before next suite session)
1. D0 solver hygiene (mpc_test OSQP settings + tiny-value clamps both paths). [small]
2. A4 offset fix (operating point) — REQUIRED before closed-loop on a fitted model. [small]
3. A3 4_mpc_server flags (-Horizon -ControlHorizon -QWeight -UMax). [small]
4. A1 MPC_TARGET honored; A2 featureChannel via opts. [small]
5. B1 dump-us-to-CSV in closed_loop_sim.py -> --play pipeline + sim A/B test. [small]
6. D1 lambda term (MPC_OPTS.uL1Weight; add lambda*(S'*1) to q) + bench test. [medium]
7. D2 threshold/re-solve/hysteresis/dwell behind MPC_OPTS (uMinEffective, uOn/uOff, dwell)
   + bench tests incl. chatter test. [medium]
8. A5 .nnw mode guard. B3 useObserver opt (loud banner). [small]
9. Archive binary before ANY rebuild (standing rule).

### Phase 1 — first surgical-suite session (saline)
1. **Quiet capture ~60 s** (no stim, no loop): baseline for touch reference, noise floor,
   AND 60 Hz/harmonics quantification -> decide on notch per Section 1 decision rule.
2. **Ctrl+C safety test** mid live run -> verify Scle -> 0 in the block (last untested safety item).
3. **Artifact-amplitude retest** with improved arrays/contact (or higher amp — saline has no
   tissue-safety limit): need artifact >> floor to settle the MAV6-vs-MAV5 cancellation question.
4. **Sequential probe run** (1c_server, frame-locked) -> suite detection floor + confirm
   24/24 refuse-in-saline still holds in the new environment.

### Phase 2 — suite closed-loop dress rehearsal (frame-locked end to end)
Probe capture `-TickFrames 6` -> `3_fit` (check printed rate ~101.7 Hz) -> `4_mpc_server
-Reference -RWeight 1e-3 -Pairs` + `2_loop -TickFrames 6` -> banks MPC-on-hardware + saline
timing number. Then a B1 open-loop replay of the SAME reference for the first open-vs-closed A/B.

### Phase 3 — scientific protocol (tissue)
1. Per-pair threshold calibration (amplitude staircase -> u_min per pair; repeat periodically).
2. Three-arm comparison (Section 3), threshold ladder sweep (D0/D1/D2 on-off), model-type
   rapid comparison (ARX order sweep + ridge vs residual_mlp vs gru via .nnw), all against
   identical touch references.

### Standing operational rules (unchanged)
Recording starts LAST; capture and deploy share tick mode; -TickPhaseUs stays unset (per-run
audit governs); archive exe+pdb before rebuilds; kill stale MATLAB before starting servers.

---

## 7. Key references for (D)

- Choi, Brockmeier, McNiel, von Kraus, Principe, Francis (2016). Eliciting naturalistic
  cortical responses with a sensory prosthesis via optimized microstimulation. J Neural Eng
  13(5):056007. https://iopscience.iop.org/article/10.1088/1741-2560/13/5/056007  [closest prior art]
- Nagahara, Quevedo, Nesic (2016). Maximum Hands-Off Control. IEEE TAC 61(3):735-747.
  https://arxiv.org/abs/1408.3025  [L1<->L0 equivalence + bang-off-bang]
- Chatterjee, Nagahara, Quevedo, Rao (2016). Characterization of maximum hands-off control.
  Syst Control Lett 94:31-36. https://arxiv.org/abs/1602.08834  [L1 fails in singular problems]
- Gallieri & Maciejowski (2012). lasso MPC. ACC.  [L1-regularized MPC for over-actuation]
- Candes, Wakin, Boyd (2008). Reweighted L1. J Fourier Anal Appl 14:877-905.
- Stellato, Naik, Bemporad, Goulart, Boyd (2018). Embedded MIQP with OSQP (miOSQP). ECC.
- Little et al. (2013). Adaptive DBS in advanced Parkinson disease. Ann Neurol 74:449-457.
  [thresholded stim can beat always-on]
- Greenspon et al. (2025). ICMS in humans: a decade of safety and efficacy. Sci Transl Med.
  [thresholds are per-channel/subject and drift]
- Kunigk et al. (2022). Reducing detection thresholds via synchronous spatially-dependent
  ICMS. Front Neurosci 16:876142.  [threshold depends on co-active neighbors]
- OSQP defaults (eps 1e-3, polish off): https://osqp.org/docs/interfaces/solver_settings.html
