# NN methodology review: why the inverse policy failed on acute #2, and what to do instead

Date: 2026-09-18. Source of every number: `day_2026-09-10/analysis/_nn_diag.json`,
produced by `training/diagnose_nn.py` (one command, ~4.6 min on the RTX 4090, seeds fixed;
log in `day_2026-09-10/analysis/_nn_diag_log.txt`). Figures: `nn_diag_ladder.png`,
`nn_diag_snr.png`, `nn_diag_clone.png` in the same folder (deckkit style, WIDE preset).

**One-paragraph verdict.** The NN arm did not fail because of the network. It failed because
(1) the per-tick signal-to-noise of the PRBS identification capture is ~0.1 SD, which caps
*any* model of the plant at held-out R² ≈ 0.10 and, by the mutual-information identity,
caps the inverse at the same R² ≈ 0.10; and (2) the *inverse framing itself* turns that low
SNR into a policy that emits the mean command: a least-squares inverse shrinks its output
gain by the R², so R² 0.05 predicts a tape of 14.8 µA ± ~1 µA — exactly what was deployed
(`_nn.json`: u4 14.74 ± 0.28, u6 14.85 ± 0.88). The MPC tracked with the same information
(r0 0.33-0.40) because feedback plus 100-event averaging integrates over the noise; the
inverse policy has no such integrator. The architecture ladder (linear / MLP / residual /
GRU × history 1 / 5 / 25 × control-channel / all-64) moves the inverse R² by at most 0.06,
and the acute-#1 capture, which had a 2× stronger plant, gives the same inverse verdict.
Two reformulations tested on the *same* data do work: a forward model used as the plant in
an optimisation reproduces the MPC's measured tracking level, and behaviour cloning of the
MPC from the reference preview alone reaches held-out R² 0.99 on a different run.

## (i) What was done

### Framing and data

| item | value |
|---|---|
| capture (09-10) | `capture_rig_runopfit12.csv`: 24 000 ticks at 100 Hz, pairs 4 and 6 PRBS 8↔22 µA, 64 features, control channel y64 |
| capture (08-31) | `capture_rig_runopfit.csv`: 12 000 ticks, pairs 1 and 4 PRBS 10↔30 µA, 32 features, control channel y8 |
| other 09-10 operating points | `opfit10` (all 8 pairs PRBS 10↔30), `opfit11` (pairs 1, 4 PRBS 10↔30), linear only |
| probe capture | `capture_rig_runrnd1.csv`: 183 k ticks, all 8 pairs, single-tick pulses, 228 trials per pair at ≥ 13 µA |
| MPC arm captures | `capture_mpc_mixr{1,2,3}.csv` + `schedule_mix_r{1,2,3}.json` + `ref_mix_r1.csv` (100 events per run, 5 sites, period 220 ticks) |
| training loop | `train.py` replicated in-process: Adam 1e-3, wd 1e-4, batch 256, 120 epochs, contiguous 70/30 split, per-column normalisation, causal u(k)→y(k+1), best checkpoint by validation R² over the reported outputs |
| GRU | hidden 32, 40 epochs, the same truncated BPTT (state reset every 100 ticks) with chunks batched through cuDNN; validated over the whole held-out tail with carried state |
| convergence check | every linear row also carries a closed-form ridge R² on the same split; they agree to ±0.01 |

### Results table (held-out R², contiguous last 30 %)

**Task 1 — acute #2 (`opfit12`), inverse y64 → (u4, u6) and forward (u4, u6) → y64.**

| arch | history | inverse u4 | inverse u6 | inverse all-64 ch (u4 / u6) | forward y64 |
|---|---|---|---|---|---|
| linear | 1 | 0.000 | −0.000 | 0.007 / 0.001 | −0.004 |
| linear | 5 | 0.001 | 0.002 | −0.003 / −0.006 | −0.029 |
| linear | 25 | 0.004 | −0.007 | — | 0.025 |
| MLP 64-64 | 1 | 0.002 | 0.006 | 0.004 / 0.011 | −0.042 |
| MLP 64-64 | 5 | 0.011 | 0.024 | −0.003 / 0.018 | −0.007 |
| MLP 64-64 | 25 | 0.008 | 0.054 | — | **0.102** |
| residual MLP | 1 | 0.002 | 0.005 | 0.002 / 0.012 | −0.039 |
| residual MLP | 5 | 0.012 | 0.022 | −0.001 / 0.004 | −0.006 |
| residual MLP | 25 | 0.007 | 0.050 | — | **0.104** |
| GRU-32 | 1 | 0.008 | 0.040 | −0.000 / **0.068** | 0.051 |
| GRU-32 | 5 | 0.009 | 0.053 | −0.023 / 0.040 | 0.084 |
| GRU-32 | 25 | 0.007 | **0.058** | — | 0.088 |

The deployed GRU's 0.049 is reproduced (0.040-0.058 depending on history). The best inverse
number on the table, 0.068, is below the forward ceiling 0.104 and within the MI bound
(below). Nothing in the ladder beats the linear baseline by more than 0.06 R².

**Task 2 — acute #1 (`opfit`), inverse y8 → (u1, u4) and forward (u1, u4) → y8; and the
other 09-10 operating points (linear only).**

| capture | arch | history | inverse (per output) | forward ctrl ch |
|---|---|---|---|---|
| opfit 08-31 | linear | 1 / 5 / 25 | u1 0.002 / 0.004 / 0.006; u4 0.013 / 0.014 / 0.017 | −0.053 / −0.120 / −0.063 |
| opfit 08-31 | MLP | 1 / 5 / 25 | u1 0.003 / 0.004 / 0.012; u4 0.022 / 0.026 / 0.018 | −0.069 / −0.052 / **0.204** |
| opfit 08-31 | GRU-32 | 1 / 5 / 25 | u1 0.003 / 0.005 / 0.016; u4 0.016 / 0.016 / 0.013 | 0.062 / 0.077 / 0.152 |
| opfit11 09-10 (pairs 1, 4) | linear | 1 / 5 / 25 | u1 ≤ 0.001; u4 0.002 / 0.002 / 0.003 | −0.003 / −0.002 / 0.081 |
| opfit10 09-10 (all 8 pairs) | linear | 1 / 5 / 25 | all eight ≤ 0.001 | −0.005 / −0.005 / −0.025 |

Acute #1's plant was measurably better (forward MLP 0.20 vs 0.10) and *strongly
super-additive*: lag-2 y8 means by (u1, u4) state are 59 / 96 / 56 / 141 µV for
(10,10) / (10,30) / (30,10) / (30,30), i.e. both pairs together give 141 µV where additivity
predicts 92. That is why only the nonlinear models find it, and why the linear forward is
negative there. On opfit12 the same table is 49.8 / 48.9 / 54.6 / 58.9 µV: a 5 µV main
effect from pair 4, ~0 from pair 6, on a feature whose SD is 39-47 µV. The inverse is at the
noise floor on both days regardless. `opfit10` (all eight pairs on at once) is the
tonic-saturation case from the acute-#2 notebook: no channel carries a forward signal.

**Task 3 — SNR and data budget (`opfit12`, linear forward h = 25, ridge).**

R² versus a causal moving average on y64 and versus record length (first fraction used,
then 70/30 inside it):

| record | MA 1 | MA 3 | MA 5 | MA 10 | MA 20 |
|---|---|---|---|---|---|
| first 25 % | 0.061 | 0.074 | 0.091 | **0.109** | 0.062 |
| first 50 % | 0.034 | 0.047 | 0.054 | 0.079 | 0.025 |
| first 75 % | 0.051 | 0.057 | 0.057 | 0.050 | −0.028 |
| 100 % | 0.022 | 0.014 | 0.003 | −0.032 | −0.146 |

Inverse (y64 history 25 → u4 / u6) under the same smoothing: 0.004 / −0.012 at every
window. Smoothing raises the forward R² by at most 0.05 and does nothing for the inverse.
Longer record *lowers* R²: the plant drifts (held-out baseline shift −0.22 SD on 09-10, +0.30
SD on 08-31). Removing a 10 s moving baseline from y64 triples the linear forward R² on
opfit12 (0.022 → 0.067) and removes the negative R² on acute #1 (−0.097 → −0.009).

Single-pulse SNR on the control channel from the rnd1 probe (13-25 µA pulses, delta over
ticks +1..+3 vs shuffled-trigger null; the all-trial z reproduces `rank_common`'s to ±0.5):

| pair | Δ (µV) | single-event z | z at 228 trials | fit a in z = a·√N | N for z ≥ 3 |
|---|---|---|---|---|---|
| 4 (control pair) | 13.2 | **0.37** | 5.6 | 0.373 | **65** |
| 6 (control pair) | 7.9 | **0.23** | 3.4 | 0.230 | **171** |
| 3 / 7 / 8 / 5 | 10.5 / 10.1 / 8.9 / 8.4 | 0.30 / 0.28 / 0.26 / 0.24 | 4.5 / 4.2 / 3.9 / 3.6 | — | 99 / 117 / 138 / 166 |
| 1 / 2 | 5.9 / 2.7 | 0.17 / 0.08 | 2.6 / 1.1 | — | 326 / 1048 |

The √N law fits the subsampled points to the last digit (`z_vs_N` in the JSON). The null SD
of a single-event delta is 35 µV on every pair; the evoked delta is 3-13 µV.

MI bound: best forward R²(y64) = 0.104 → I(u; y64) = 0.055 nat → inverse R² ≤ 0.104. Summing
per-channel MI over all 64 channels (best of linear / MLP per channel; only 2 channels have
R² > 0.01) gives ≤ 0.113. Every inverse result in the ladder sits under this bound; the GRU is
at half of it.

**Task 4a — forward model + optimisation instead of a direct inverse (`opfit12` model,
reference `ref_mix_r1`, u ∈ [0, 30] µA, certainty-equivalent open loop).**

| quantity | linear h25 | MLP h25 |
|---|---|---|
| forward held-out R² (y64) / residual SD | 0.024 / 44 µV | 0.115 / 47 µV |
| MPC's real r1 tape pushed through the model: r (noiseless / with model noise) | 0.14 / 0.03 | **0.54 / 0.20** (measured r0 0.33) |
| CE inversion, r under the model (noiseless / with model noise) | 0.92 / 0.22 | **1.00 / 0.35** |
| direct inverse policy fed the reference, r under the model (noiseless / with noise) | 0.03-0.13 / 0.00 | −0.07-0.35 / **0.00** |
| direct inverse policy output modulation (SD of u4, u6) | 0.15-0.35 µA / 0.08-0.97 µA | same |
| charge, CE tape vs MPC tape (µA·ticks) | 844 k vs 173 k | 645 k vs 173 k |

The MLP forward model is *calibrated in the right regime*: given the MPC's actual command
tape it predicts r ≈ 0.20 once its own residual noise is added back, against 0.33 measured
(the gap is the MPC's feedback adaptation, which an open-loop push-through cannot show).
Under that same model, an optimiser reaches r 0.35 with noise — the MPC's league — while the
direct-inverse policies, which get the *shape* right (0.35 noiseless), modulate the command
by 0.1-1 µA and are erased by the noise (r 0.00). The CE tape spends 3.7-4.9× the MPC's
charge because the optimiser rails to the box with only a token amplitude penalty; the
number to read is the r, not the charge.

**Task 4b — behaviour cloning of the MPC per site (train r1 + r2, held out r3; input = 20-tick
reference preview [k−5, k+15) + normalised time-in-event; window −10..+40 ticks around
each onset; 10 000 train / 5 000 held-out samples).**

| policy input | arch | cross-run R² u4 / u6 | within-r3 R² u4 / u6 | per-site u4 (LP / P1 / MP / P3 / SHAM) |
|---|---|---|---|---|
| reference only | linear | 0.770 / 0.851 | 0.770 / 0.855 | 0.69 / 0.70 / 0.88 / 0.76 / — |
| reference only | MLP 64-64 | **0.996 / 0.989** | 0.997 / 0.991 | 0.99 / 0.99 / 1.00 / 1.00 / 0.70 |
| reference + last 5 ticks of y64 | linear | 0.772 / 0.855 | 0.773 / 0.856 | 0.70 / 0.71 / 0.88 / 0.76 / — |
| reference + last 5 ticks of y64 | MLP 64-64 | **0.998 / 0.997** | 0.998 / 0.997 | 1.00 / 1.00 / 1.00 / 1.00 / 0.89 |

The MPC's command is a near-deterministic function of the upcoming reference (the
event-to-event SD of u4 at the peak tick is < 2.3 µA); adding feedback moves R² by 0.002. A
64-64 MLP clones it on an unseen run to R² 0.99 on the four real sites. SHAM is lower only
because its reference is nearly flat and its commands are small.

## (ii) Diagnosis, in plain language

**It is data/SNR first, formulation second, architecture not at all.**

1. *SNR.* On acute #2 a PRBS step of 14 µA moves the control feature by ~5 µV against a
   39-47 µV feature SD (per-tick r ≈ 0.12, R² ≈ 0.015 per tick). Integrating 25 ticks of
   history gets a model to R² 0.10 and no further. A single stimulation event is z 0.23-0.37
   on the feature; z 3 needs 65 (pair 4) to 171 (pair 6) averaged trials. That is the whole
   story of why "one tick in, one command out" cannot work: no model of any class can read
   a single tick.
2. *Formulation.* An inverse policy trained by least squares emits E[u | y]. When R² is
   0.05 its output SD is √0.05 ≈ 0.22 of the command SD (7 µA) ≈ 1.5 µA at best — the
   14.8 ± 1 µA tape is the *correct* answer to the question that was asked. The forward
   model + optimiser test shows the same information used the other way round reaches the
   MPC's tracking level, because the optimiser is allowed to drive the command to the box
   and let the plant integrate; the inverse regresses to the mean and is never allowed to.
   The MPC also has an integrator the inverse lacks: feedback over 100 events.
3. *Drift.* The held-out tail differs from the training head by 0.2-0.3 SD in baseline on
   both acutes; longer records made the forward fit *worse* (0.11 → 0.02). A model trained
   on 4 min of PRBS is stale by the time it is deployed 25 min later. Baseline removal alone
   triples the linear forward R².
4. *Architecture.* Across 4 architectures × 3 histories × 2 input sets the inverse R² spans
   0.000-0.068; the GRU is the best of a bad set by 0.03-0.05. The only place a nonlinear
   model wins something real is the acute-#1 *forward* model (0.20 vs −0.06 linear), because
   the pair-1 × pair-4 response is super-additive (141 µV vs 92 additive) — a plant
   nonlinearity, not a policy one.
5. *Was the policy class the problem?* No: the MPC's own policy — the thing we actually want
   in the tick — is learnable from the reference alone at R² 0.99 with a 64-64 MLP on an
   unseen run. What was not learnable was the *plant* from tick-level PRBS data; the direct
   inverse is the plant learned backwards.

## (iii) Recommended path forward (ranked)

1. **Forward model as the plant, optimisation as the controller (nonlinear MPC).** Train
   the forward model on event/burst-probe data (pulse-triggered, averaged targets: see (iv)),
   with a slow-baseline term or high-passed feature, and run the existing MPC cost against
   it (sampling or gradient over the horizon; the CE inversion above is the one-step
   prototype). This is where an NN earns its place: on acute #1 the MLP forward beats linear
   by 0.26 R² because of the inter-pair super-additivity a linear ARX cannot represent. Gate:
   deploy the NN plant only if its held-out forward R² on the control channel clears the
   linear ARX by ≥ 0.05 *and* the tonic-saturation rank test still passes.
2. **Behaviour cloning of the MPC as the NN arm's positive control, then residual
   learning.** A 64-64 MLP on the reference preview reproduces the MPC tape at R² 0.99
   and costs nothing in the tick; deploying it in `--mode nn` is an honest end-to-end test
   of the NN pipeline (verify_export → check_nnw_mode → max-rate) that is *expected* to
   track at the MPC's r0 ≈ 0.33-0.40. Residual learning on top (predict the MPC's per-event
   error from the event-averaged response) is only worth it once the plant model is good
   enough that the residual is not noise — it needs the event-level data of (iv).
3. **Event-level, not tick-level, targets.** Train on pulse/burst-triggered averages
   (≥ 65-171 trials per condition on the control channel, per the √N fit), or on the
   MPC-arm event windows (20 events per site per run). Tick-level PRBS supervision at z ≈ 0.3
   per tick cannot be rescued by smoothing (max +0.05 R²) or by length (drift wins).
4. **Drift-aware training.** Baseline-track the feature (10 s moving baseline, or a
   high-pass) before fitting; weight recent data or refit online (RLS on the linear part,
   fine-tune the NN head between runs); re-probe gain every ~10 min as the sliding analysis
   already does for the MPC.
5. **Pretraining across acutes** is low value for now: only 2 of 64 channels carry any
   forward signal on 09-10, the channel maps differ, and the plants differ in kind
   (super-additive on 08-31, near-additive on 09-10). A shared forward-model *family* with a
   per-animal calibration head could pay off after 3-4 acutes, not before.
6. **When an NN is worth it versus linear.** Only for the *forward* model, and only when the
   plant is measurably nonlinear (an inter-pair interaction or a burst-length knee) and the
   forward R² clears ~0.1. For the policy, the linear/ridge baseline within 0.06 R² of every
   network on both acutes says: ship the linear one unless the gate in (1) is met. Never a
   direct inverse on PRBS data again.

## (iv) Acute-#3 data-collection asks for the NN arm

Costed against the plan in `docs/ACUTE3_PLAN_2026-09-18.md` (burst-ladder 13 min, gap scan
2 min, duty-PRBS 5 min); the NN asks reuse those captures and add ~20 min.

1. **Burst-probe forward-model set (the primary NN dataset).** For the two control pairs:
   bursts of 1 / 3 / 10 pulses at 4 amplitudes (≈ 8, 13, 18, 25 µA), randomised order,
   400-500 ms gap, **≥ 200 trials per (pair, burst, amplitude)** — at z ≈ 0.37·√N per
   single pulse this gives z ≈ 5 per cell and z ≥ 3 at every amplitude; bursts should raise
   the per-event z well above that. 2 pairs × 3 bursts × 4 amps × 200 × 0.45 s ≈ 36 min if
   run alone; interleaving with the burst-ladder probe covers most of it. Add the **joint
   condition** (both pairs together, 3 amplitude combinations, 200 trials each, ~5 min) —
   the 08-31 super-additivity is the one nonlinearity worth modelling.
2. **A higher-contrast, longer-dwell ID capture** instead of 8↔22 PRBS: duty-PRBS with
   0↔25-30 µA and dwell ≥ 5 ticks (the plant integrates over ~4 ticks; best lag 3-4), 5 min,
   recorded **twice**, 20 min apart, for a drift-aware split. Per-tick SNR scales with
   contrast; 8↔22 was the weakest contrast of the three operating points.
3. **Feature ask:** log the raw 610 Hz block alongside the 100 Hz feature so an
   evoked-window feature (8-12 ms post-pulse, where the ms-latency work found the response)
   can be computed offline; the rectified tick-mean dilutes a ~10 ms response over 10 ms +
   noise. If the evoked feature doubles single-event z, every trial count above halves.
4. **MPC arm captures for cloning/residual learning:** the three mixed-site runs as on
   09-10 (100 events each) plus one **repeat of the same schedule late in the day** (already
   in the plan as the drift re-probe). Keep `schedule_*.json`, `ref_*.csv` and the capture
   aligned exactly as on 09-10 (SKIP 50, period 220): the cloning pipeline runs unchanged.
5. **NN-arm deployment order:** (a) cloned-MPC policy as positive control (expect r0 ≈ MPC);
   (b) NN forward model inside the MPC only if the gate in (iii-1) is met on the day's
   burst-probe set; (c) no direct inverse. Budget 2 × 4 min arms.

## Literature (merged 2026-09-18 from literature/LIT_C_datadriven_NN_control.md, 60 entries)

The field's verdict matches the diagnosis above. Direct supervised inverse learning on a
many-to-one plant is the distal-teacher failure mode (Jordan & Rumelhart 1992,
10.1207/s15516709cog1603_1). Working recipes for learned control of stimulation-evoked
activity are forward model + optimisation (Moure et al. 2026 Neuron,
10.1016/j.neuron.2026.07.006; Bryan et al. 2025 J Neural Eng, 10.1088/1741-2552/ae036a;
Steffen & Cannon 2025, arXiv 2504.00618 -- ICNN multi-step predictor inside an MPC), linear
state-space plants where the macroscale data are effectively linear (Yang et al. 2021 Nat
Biomed Eng, 10.1038/s41551-020-00666-w; Nozari et al. 2024 Nat Biomed Eng,
10.1038/s41551-023-01117-y), adaptive/recursive fitting for drift (Yang, Ahmadipour &
Shanechi 2021, 10.1088/1741-2552/abcefd; DFINE, Abbaspourazad et al. 2024,
10.1038/s41551-023-01106-1), excitation design for identification under charge limits
(Bolus et al. 2018, 10.1088/1741-2552/aaa506; Yang, Connolly & Shanechi 2018 stochastic
binary-modulated pulse trains, 10.1088/1741-2552/aad1a8), and Gaussian-process Bayesian
optimisation for the outer pair/amplitude problem (Bonizzato et al. 2023 Cell Rep Med,
10.1016/j.xcrm.2023.101008). Deep RL in this exact preparation exists as a protocol
(Coventry & Bartlett 2024, TD3 thalamus-to-cortex in rat, 10.1016/j.xpro.2024.103496) but
its sample cost is far above one acute. Validation standard across these papers: k-step
forward prediction on held-out contiguous data plus an interleaved closed-loop A/B against
the linear controller -- the same gate written into (iii)-1 above.
