# Lab notebook — 2026-09-10 (THURSDAY): ACUTE #2 — 64-ch, new thalamic array, closed-loop arms

**STATUS: FINAL. Experiment COMPLETED after a morning localization scare; all
planned claims banked in modified (rank-1) form + several new findings.
Companion: `BLOCK_LEDGER_2026-09-10.md` (all block identities + files).**

## The morning scare and its resolution (biggest lesson of the day)

No audible neural response to touch during array localization → experiment
nearly declared defunct. Resolution: the audible-touch criterion was
calibrated on penetrating arrays; the new NeuroNexus 8×8 planar array laid
TANGENT to S1 is superficial/LFP-dominant and near-silent to the ear by
geometry. Quantitative screen replaced the speaker:
- Quiet block: both banks live, baseline ~3.3e-5 V (~3-4× below acute #1 —
  surface geometry), blacklist 33/36/45/59 (line-dominated).
- SHAM thwack: clean null (drift only, no locked component, no evoked
  morphology). Established null magnitudes 17/50 µV.
- D1 thwack: **−297 µV @ 23 ms focal response, visible in single trials**,
  return-current ring around a ch 39/47 focus. Speaker silence fully
  explained (focus on bank 2; superficial LFP).
**RULE (institutionalize): for surface/planar arrays the placement gate is
the thwack z-score table, never the speaker.**

## Full 10-site thwack battery (150 thwacks each, all reference-grade)

D1 −297@23 ch39 | D2 −249@26 ch39 | D3 −321@28 ch39 | D4 −370@25 ch39 |
P1 −529@33 ch39 | P2 −471@23 ch47 | P3 −438@26 ch39 | MP −525@25 ch47 |
LP −474@21 ch47 (+sharp OFF response at release — site-specific; D1 has
none) | SHAM null. Split-halves 0.82-0.98. ch64 active on pad-ish sites
(P1/P3/MP/LP), absent digits — a decoding dimension. OFF responses sit
beyond the 200 ms template window (offline follow-up; convention kept for
cross-acute comparability).

## Thalamic probing (all-8-pair, single-pulse)

- NOTE: run rnd1 silently replayed the STALE 08-31 design (7 amps ≤25;
  1c_server label-collision gotcha). Scientifically fine; label hygiene rule
  reaffirmed — fresh labels or delete design_run*.csv.
- **DELIVERY: first 0-fail/0-warn audit ever** (4257/4257 single, pair map
  exact via --pairs table, base/240).
- **ALL 8 PAIRS EVOKE CORTEX** (z 24-121 @ 8-11.5 ms; acute #1 had 2/8).
  Knees 9-13 µA. Stim footprint (ch64/56/39) ≠ touch footprint (ch39/47).

## THE CENTRAL PHYSIOLOGY FINDING: tonic-drive saturation → rank-1

Operating-point PRBS fits:
- 8 pairs simultaneously @10-30: feature gain ≈ 0 everywhere (ch39 pinned
  3.8× baseline, no modulation). Aggregate ~800 pulses/s saturates cortex.
- 2 pairs @10-30: only pair4→ch64 crosses GO (0.111).
- 2 pairs @8-22 (lower op point): five channels >0.1 — but ALL via pair 4;
  pair identity collapses under tonic drive (pairs 1 and 6 couple weakly
  into pair 4's shared footprint).
**Pulse-evoked rank (8) ≫ tonic-drive rank (~1). MIMO/decoupled exhibits
deferred to a prep/protocol with higher tonic rank (duty-cycle or burst
redesign is the acute-#3 lever). Decision made per pre-stated tree; rank-1
day executed in full.**

## Plant + controller

- Model: order-1 (orders 1:3; n=5 default fit had UNOBSERVABLE duplicated
  modes → observer pole 1.04 → cpp forces open-loop. Rule: check the
  banner's observer line; cap orders for p=1 fits). m=2 (pairs 4,6),
  p=1 (ch 64), Ts 10 ms wall-clock, gains ~5e-7 V/µA. valFit ≈ 0% — noted
  honestly; feedback tracked anyway (below), the acute-#1 pattern.
- **Three sim-harness bugs found+fixed in closed_loop_sim.py during
  verification** (it predated the pairs/feature-map era): (1) plant read
  reply slots 1..m, ignoring --pairs (S5's 09-09 sim pass was partially
  vacuous); (2) feature frame 8-wide with y at slot 1 → cpp
  FEATURE-MAP-FAULT(hold-last)=zeros for maps >8 (fault itself worked as
  designed); (3) reported only slot-1 command. Now: --pairs/--feature-map
  mirrored, per-slot ranges reported.
- Tick base: WALL-CLOCK all day (—TickFrames dropped operationally at the
  probe; kept consistently thereafter: fit Ts = arm ticking. Delivery was
  0-miss/0-double anyway).

## ARMS (references: LP/P1/MP/P3/SHAM templates on ch 64; 100 interleaved
events/run; Choi tapes mu 1e-13 kept for acute-#1 comparability — spiky
step profile documented, --lam not plumbed, offline cleaning per art_*)

| run | MPC r0 (lag) | Choi r0 (rBest@lag) |
|---|---|---|
| r1 | 0.330 (0) | 0.326 (0.369@−1) |
| r2 | 0.378 (0) | 0.300 (0.344@−1) |
| r3 | 0.381 (0) | 0.394 (0.469@−1) |
| r1-LATE (~2 h, same tape) | **0.402 (0), slope 0.83→1.000** | 0.339 (0.378@−1), slope flat |

- Fidelity ≈ half of acute #1 (0.33-0.47 vs 0.71): weaker gain, surface
  signals, refs ~4× above reachable band (clip; convention kept).
- **MPC: lag 0 every run** (preview horizon; acute #1 was +2), slope up to
  1.000 at late. **Early/late: MPC +0.072 and re-calibrated to slope
  exactly 1.000; Choi flat (+0.013).** Claim: feedback ADAPTS to the
  drifted plant; replay cannot. (NOT claimed: Choi decay — r3 was Choi's
  best run; the r2 "decay" read was retracted, two-points lesson.)
- Charge r1: MPC 173k vs Choi 48k µA-ticks — **acute #1's charge win
  REVERSED** under weak-gain/unreachable targets (sparse tape vs sustained
  feedback effort). r4b (R 0.3, late): still tracks 0.313@lag0 at 303k —
  fidelity robust to 3× input penalty; charge-fidelity frontier CONFOUNDED
  by time-of-night drift → needs a time-controlled sweep (acute #3).
- **NN arm (honest negative)**: inverse policy untrainable at this SNR
  (linear R²=0.000, GRU 0.049); tape ≈ tonic mean 14.8 µA + σ<1 wiggle →
  **NOT TRACKING (r0 0.020)**. Doubles as the mean-drive null: tonic drive
  produces no tracking → model-based arms' r is genuine reference-following.

## PZ2-off incident (operator battery-saving; caught by capture audit)

Runs r4-chargematched(orig), nn_r1(orig), late-reprobe(orig) had ALL-ZERO
features (amp off). Detected by y-zerofrac scan; boundary clean, ALL
headline runs live. Voided runs rerun with amp verified live. Retractions
recorded: the "tonic null via r4cm" and "R=10 knife-edge measured" claims
were void (dead-amp artifacts). ~1.3M µA-ticks tonic stim delivered
unrecorded (exposure ledger). **Rule: check y-liveness (zerofrac) in the
FIRST minute of every run's capture; the amp state is invisible on the
loop side otherwise.**

## Drift bracket (opfit12 replay early 21:32 vs final ~01:00)

u4→ch64 gain **0.132 → 0.137 (HELD all night)**; u6 0.116 → 0.062 (faded);
y-level stable. The primary actuator was stationary; drift lived in the
secondary — context for MPC's late improvement.

## For the results deck / paper queue

1. Feedback-adapts-vs-replay (early/late, slope→1.000) — cleanest claim.
2. Tonic-saturation/rank-collapse (pulse rank 8 vs tonic rank 1) — the
   scientific finding that redesigns acute #3 (burst/duty-cycle probing).
3. Charge-reversal + robustness to R — honest complication of acute #1.
4. NN-inverse negative + mean-drive null.
5. 10-site battery on a planar 64-ch surface array + LP OFF-response.
6. Site-decoding + spatial-match offline (48%-analog) from arm blocks.
Offline queue: raw-LFP artifact-aware redo on arm blocks (batch-transfer),
shuffled-template nulls, sliding-window r, per-site tracking split,
early/late paired-event stats, exposure accounting.
