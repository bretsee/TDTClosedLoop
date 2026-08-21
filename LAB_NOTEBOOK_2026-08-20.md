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

---

# EVENING RIG SESSION (same day) — pre-suite validation runs

User at the rig; goal = bank everything environment-independent before the
suite move. Preflight + UDP selftest all PASS (E1 live RZ2 ACK; E2 correctly
gated).

## Run pre1 — new binary hardware-validated (block LD-260820-181210)

Sequential probe, frame-locked, 28000/28000 ticks, 0 dropped, window 6/6/0
(ring wrap at 65536/65536 is expected on a 275 s run — nothing reads old
samples). Delivery audit: **471/471 probes = exactly one carrier pulse, 0
missed, 0 doubled, wire == design, all 8 pair mappings exact (inversion
EXACT), carrier 101.725 Hz, 6.000 samples/period, margin 4.01 ms, VERDICT
DELIVERY VERIFIED, 0 warnings.** The aug20-signedfeat rebuild reproduces the
bit-perfect record on hardware.

## Ctrl+C emergency zeroing — HARDWARE-VERIFIED (block LD-260820-183738)

The last untested safety item is closed. Stim live at full amplitude
(|Scle| = 25) when Ctrl+C hit the loop mid-run: 7 all-zero packets on the wire
(≥ the 5 the handler sends), **Scle silent 12 ms after the last nonzero
command and exactly zero for the entire 24.27 s recorded tail** (sSig zero
too). Direct disproof of the 2026-08-14 failure mode (41.5 s of held
amplitude).

## BUG FOUND AND FIXED: Ts snap picked the wrong rate on jittery captures

3_fit stamped the frame-locked pre1 capture Ts = 10 ms. Cause: the 08-18 Ts
alignment used `median(diff(t_ms))`; per-tick timestamps carry the PLL's
~±1 ms fire jitter (p5 8.0 / p95 10.6 ms) and the MEDIAN biased to 9.997 ms →
snapped to 10 ms, while the true rate (span/(N−1)) was 9.8306 ms. The two
nominal rates are only 1.7% apart, inside the 2% snap tolerance, so the biased
median crossed the decision boundary. Fixed: rate from total span (jitter
cancels telescopically); refit stamps **101.7253 Hz** correctly. Sim never
caught it because sim timestamps are smooth.

## Saline fit + first MPC-on-hardware (cl1, block LD-260820-185232)

3_fit on pre1: correct saline refusal (|corr| ≤ 0.02, valFit −2.89%) but a
stable order-3 junk model — saved deliberately for the rehearsal. Offsets on
real data for the first time: yOffset = 1.442e-3 V (the saline feature
baseline), uOffset ≈ 0.03.

cl1 (target 0.0016, rWeight 1e-3): 6000/6000, 0 dropped. **out0 constant at
0.030233 = uOffset(1) exactly** — with a ~zero-gain model the optimal command
is the operating point; the E1 "loop NOT closed" verdict is a false alarm in
this configuration (its 1e-6 range threshold assumes usable plant gain).
Documented as a new failure-branch row in the manual.

## Amplitude resolution PROVEN — no integer conversion needed (cl2 block)

User question answered from data: cl2 commanded **5310 distinct fractional
values; Scle reproduced 5309 bit-for-bit** (per-packet 5820/5899 exact to
1e-6; the rest are probe-straddles-edge sampling), finest distinct step 1e-9
preserved. The server-log max (0.0552) exceeding the wire max (0.0103) is the
first 8 observer/QP startup-transient replies being superseded before the next
send (newest-reply-wins) plus one mid-run overwrite — not amplitude loss.
Caveat: IZ2 DAC granularity downstream is unobservable from the PC; folds
into the artifact retest.

## Loop closure PROVEN on hardware (cl2, block LD-260820-190439)

Toy plant staged at AllModels(9) (slot 10 keeps the saline fit);
`-ModelIndex 9`: **out0 varies with the measurement** (range 0.0476 over
logged replies) — first genuine closed-loop-responsive MPC run on hardware.
Together cl1+cl2 show the loop is closed and correctly quiet when the model
says there is nothing to do.

## Moving-target rehearsal (cl3, block LD-260820-191520) — machinery OK,
## control horizon is the binding constraint

Touch-template reference (5 events, baseline 1.442e-3 measured today, 5x
scale). DC tracks exactly (u mean 0.00722 vs predicted 0.00703) but the AC
modulation is statistically absent (slope −0.4 ± 0.5 vs predicted 4.9).
Diagnosis, not a plumbing bug (bench preview test passes): **Nu = 2 hold-last
dilutes a 2-3-tick rectified touch spike by ~3/20 (~2-3% command modulation,
exactly what per-event windows show), and saline feature noise (std 21% of
baseline → ±20% command jitter) buries that in 5 events.** This is the item-C
horizon discussion materialized on hardware — the user's instinct was right.

## QUEUED FOR MORNING (references staged, commands in the manual/chat)

- **cl4**: `ref_steps.csv` (built — 2 s plateaus, +30%) with the same flags →
  unambiguous moving-target validation at Nu = 2.
- **cl5**: `ref_rehearsal.csv` with `-ControlHorizon 20` → quantify how much
  transient fidelity the control horizon buys; sets the Nu standard for touch
  templates in tissue.
- Then the surgical-suite session proper.

## Next session (surgical suite)

1. Quiet capture ~60 s → baseline + noise floor + 60 Hz quantification (notch
   decision rule in VALIDATION_PLAN §1).
2. ~~Ctrl+C mid live run~~ **DONE at the rig 2026-08-20 evening — PASS.**
3. Artifact-amplitude retest (better arrays/contact — pre-deployment gate).
4. Sequential probe run → suite detection floor.
5. Closed-loop dress rehearsal → **engineering pass banked at the rig
   (cl1-cl3); suite session re-banks the environment-referenced numbers** and
   runs the first open-vs-closed A/B on the same reference.
