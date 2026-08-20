# Lab Notebook — 2026-08-20

No rig time (soldering day for the user; saline final test relocating to the
surgical suite). Full off-rig session: the Phase-0 code work from
`VALIDATION_PLAN_2026-08-19.md`, plus three deliverables (this entry, the
weekly deck, and `EXPERIMENT_MANUAL.md`). All validation suites green at
session end.

## Context set by the user today

- **The user is Choi's successor in the lab.** Standing directive: match
  **Choi et al. 2016** (J Neural Eng 13:056007 — full methods extracted, open
  access) as closely as possible for the MPC experiments; NN arm may diverge.
  The control-rate divergence (9.83 ms ticks vs Choi's 1.63 ms bins) is a
  prior user decision.
- **Filtering framing corrected:** the RZ2's onboard DSPs already deliver a
  ~Choi-2016 LFP band (5-200 Hz @ 610 Hz) to this PC. The 2026-08-19 "no
  filtering anywhere" audit statement applies to the PC-side chain only
  (VALIDATION_PLAN section 1 amended). 60 Hz sits inside that passband; the
  suite quiet capture still decides the notch question.
- Decisions taken (offered as options): Choi threshold gate in **offline
  synthesis only** (real-time gate queued); **signed-mean feature flag built
  today** (C++ rebuild authorized); experiment manual as repo Markdown.

## Defect fixed: operating-point (offset) mismatch — REQUIRED before closed loop

`fit_sysid_from_capture` fits on mean-removed data and stored
`uOffset/yOffset` in `SYSID_INFO`, but **nothing applied them at control
time** — every controller ran the centered model on raw features. Invisible on
the zero-mean toy plant; would have biased the first real closed-loop run.

Fix (design reviewed, one correction adopted — `P.u_last` stays RAW so
resets/fail-safes keep meaning "stim off"):
- Offsets now travel **with the model**: attached to `sys` after the parsimony
  block (attach-before would be discarded by `best = c`), carried into the
  `.lti` as trailing rows (old binaries ignore trailing tokens — verified in
  both existing parsers).
- `mpc_test` runs observer/QP in centered coordinates; converts at the two
  boundaries (measurement in, command out); QP box shifts by −uOff so the
  un-centered command maps exactly onto [umin, umax]; reference centered
  per-tick (all three reference sources arrive raw).
- `closed_loop_sim.py` simulates the plant in the raw frame.
- **Bench proof:** synthetic offset model (uOff 5, yOff 0.5) tracks
  y = 1.0007 vs target 1.00, u = 7.506 vs analytic 7.496. Offsets absent →
  bit-identical legacy behavior (subtraction of +0).
- HAZARD logged: `cpp_controller --mode mpc` does not yet apply offsets —
  MATLAB↔C++ A/B on offset models is meaningless until ported (queued).

## Solver hygiene (D0)

MATLAB OSQP ran at defaults (eps 1e-3, no polish) → ~1e-3 ADMM residue posing
as sub-threshold stim commands. Now: polish on, eps 1e-6 (handles the
`polish`→`polishing` rename across OSQP versions), post-solve dust clamp.
Bench: zero target → u EXACTLY 0.

## Model modularity (A1/A2/A3)

- `MPC_MODEL_INDEX` selects the AllModels slot (default 10; `MPC_TARGET` is a
  reference value and stays un-overloaded).
- `MPC_OPTS.featureChannel` replaces hand-editing `feature_map` at the rig
  (3_fit's instruction text updated).
- `4_mpc_server.ps1` gains `-Horizon -ControlHorizon -QWeight -UMax
  -FeatureChannel -ModelIndex`; all accumulate into one `cfg.mpcOpts`.
  Smoke: N=40/qWeight=2/featureChannel=3 confirmed in mpc_test's banner.

## Open-loop arm (B1 + Choi synthesis)

- `closed_loop_sim.py --dump-u` writes the commanded trajectory in design-CSV
  format; `cpp_controller --play` replays it. **Acceptance: replay == dump
  exactly (float32, shift 0).** This is the certainty-equivalent open-loop
  optimum (sim plant == model).
- **`rig/choi_synthesis.py`** replicates Choi eq. 5 offline on our fitted
  model: raw-unit amplitudes in [0, I_max], quadratic µ‖u‖², low-passed
  total-current λv² (α = Ts/(τ+Ts), τ = 100 ms), and the **in-model threshold
  gate** via sequential linearization with Choi's exact damping
  (β = max(0.3, 0.97^k)). Numpy-only; gate handled by two-sided diagonal
  scaling of precomputed G'G (no per-iteration gemm); per-subproblem Lipschitz
  (max(g)² scaling — the shared bound slowed attenuated solves 100×).
- Gate boundary physics found during testing: entries whose two branch optima
  straddle the threshold flip in a 2-cycle forever (the gate is discontinuous
  there). Resolution: detect the 2-cycle; a SMALL flipping set is tie-broken
  on the TRUE nonconvex objective and reported; a large set is honest
  non-convergence.
- **`rig/test_choi_synthesis.py`: 7/7 PASS** — analytic steady states (µ=0,
  0.01), gate pass-through, gate compensation (thr 30/atten 0.1 → u rises
  2.5 → 25 = r/(a·g), the undershoot fix demonstrated), gate honesty
  (oscillatory thr flagged), offset frame (u* = uOff + (r−yOff)/g), CSV
  round-trip.
- `MPC_OPTS.useObserver = 0` gives a loud pure-feedforward mode (third arm /
  ablation). The earlier L1-term idea is DROPPED (diverges from Choi; his µ
  is our rWeight).

## Signed-LFP feature mode (C++ rebuild)

Choi controlled the signed LFP; our feature was rectified. Added
`--feature-signed` / `2_loop -FeatureSigned` (plain mean instead of mean|x|;
default unchanged), `build_touch_reference.py --signed` (templates in the same
space — the signed template preserves the negative S1 deflection that
rectification folded upward).

Rebuild protocol followed: current exe verified hash-identical to the
`aug18-pll` archive before edits; rebuilt; archived `aug20-signedfeat.{exe,pdb}`.
**Sim acceptance:** both modes 1500/1500, 0 dropped, window 6 nominal;
rectified feature mean **635.3 = the historical sim value (~636)** →
pre-rebuild behavior preserved; signed mean 1.7 on a zero-mean sine (range
±966) → new path correct. `cpp_controller --selftest` untouched, 13/13.

## Safety guard (A5)

`.nnw` files now stamped `# mode: inverse|forward` (comment form — every
parser strips `#`); `rig/check_nnw_mode.py` refuses forward models (exit 1)
and warns on unstamped legacy files. C++-side refusal queued for the next
cpp_controller rebuild.

## Deliverables

- **`EXPERIMENT_MANUAL.md`** — standing step-by-step manual: system diagram,
  golden rules, bring-up → quiet capture → probe → fit (LTI + NN) → gate
  calibration → reference → open-loop arm → closed-loop arm → safety →
  analysis; Choi-2016 correspondence table; failure-branch lookup.
- **Weekly deck** `scripts/build_weekly_deck_2026-08-20.py` →
  `PythonIntanAnalysis/outputs/Synthesis/ClosedLoop_weekly_2026-08-20.pptx`
  (11 slides, 11pt Arial/black per standing preference; campaign stats
  recomputed from the ledger at build time; suite tallies parsed from test
  sources; hardware numbers quoted with block provenance).
- This entry.

## Validation summary (all off-rig, session end)

| Suite | Result |
|---|---|
| `bench_test_reference_mpc` (13 legacy + 5 new) | **18/18 PASS** |
| `cpp_controller --selftest` | **13/13 PASS** (not rebuilt) |
| `rig/test_choi_synthesis.py` | **7/7 PASS** |
| Loop sim post-rebuild, rectified | 1500/1500, 0 dropped, mean 635.3 (=history) |
| Loop sim post-rebuild, signed | 1500/1500, 0 dropped, zero-mean as expected |
| B1 dump→replay | exact (float32 max diff 0.0, shift 0) |
| Offset chain fit→AllModels→.lti→python parsers | round-trips exactly |
| 4_mpc_server opts propagation | banner confirms N/qWeight/featureChannel |

## Next session (surgical suite)

1. Quiet capture ~60 s → baseline + noise floor + 60 Hz quantification (notch
   decision rule in VALIDATION_PLAN §1).
2. Ctrl+C mid live run → `Scle` → 0 in the block (last untested safety item).
3. Artifact-amplitude retest (better arrays/contact — pre-deployment gate).
4. Sequential probe run → suite detection floor.
5. Closed-loop dress rehearsal, frame-locked end to end → banks
   MPC-on-hardware + timing number. Then the first open-vs-closed A/B on the
   same reference.
