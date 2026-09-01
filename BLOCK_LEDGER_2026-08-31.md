# Block ledger — 2026-08-31 acute experiment (32-ch, GO-at-32)

Backup/validation of the hand-written block annotations. One row per Synapse
block, appended live as blocks are handed over. All blocks under
`C:\Users\brets\Desktop\Data\` and nest one directory level.

Day constants: uMax **30** (all arms); baseline (MAV6) **1.2e-4 V**;
blacklist **ch 27** (corr −0.01); watch **ch 14** (corr 0.77, high amplitude);
carrier base/240 = 101.7253 Hz; loop `-InputChannels 32 -TickFrames 6`;
recording started LAST; stim enable ON immediately after `go`.

| # | block | phase / purpose | key results |
|---|---|---|---|
| 1 | `BSClosedLoop32-260831-122406` | **G8** thwack test (SHAM, pre-animal, thwacker in air) | nThw 150/150, ITI ~0.97 s machine-uniform; template (32,122); split-half −0.67 = correct noise-level sham. G8 PASS — migration fully closed. |
| 2 | `BSClosedLoop32-260831-174013` | **Phase 1** quiet capture (implanted, no stim, 62 s) | All 32 ch live, LFP std 75–304 µV; 60 Hz median **7.6%** (vs 74% saline — notch likely unneeded); baseline median 1.2e-4 V; common-signal corr: ch 27 = −0.01 → **BLACKLIST**, ch 14 = 0.77 → watch, rest ≥ 0.90. Extractions to `Acute_2026-08-31-g8/` (row 1) and analyzer JSON alongside the block. |

| 3 | `BSClosedLoop32-260831-175746` | **Phase 2** thwack battery: **SHAM** (in-vivo, thwacker runs, touches nothing) | nThw 150/150, ITI ~0.97 s; split-half −0.08, peak 39.8 µV = correct noise-level sham; "best ch 8" is noise winning (expected). Template → `Acute_2026-08-31/`. |

| 4 | `BSClosedLoop32-260831-180137` | **Phase 2**: site **P3** | nThw 150/150; split-half **0.963**, peak **709.5 µV**, best **ch 8**. Strong real template. |

| 5 | `BSClosedLoop32-260831-180520` | **Phase 2**: site **D4** | nThw 150/150; split-half **0.976**, peak **704.7 µV**, best **ch 8**. |

| 6 | `BSClosedLoop32-260831-180905` | **Phase 2**: site **D1** | nThw 150/150; split-half **0.921**, peak **382.0 µV**, best **ch 8**. |

| 7 | `BSClosedLoop32-260831-181248` | **Phase 2**: site **MP** | nThw 150/150; split-half **0.967**, peak **585.7 µV**, best **ch 8**. |

| 8 | `BSClosedLoop32-260831-181632` | **Phase 2**: site **P1** | nThw 150/150; split-half **0.989**, peak **614.3 µV**, best **ch 8**. |

| 9 | `BSClosedLoop32-260831-182004` | **Phase 2**: site **LP** | nThw 150/150; split-half **0.981**, peak **692.6 µV**, best **ch 6** (first non-8 site — spatial separation on the array). |

| 10 | `BSClosedLoop32-260831-182330` | **Phase 2**: site **D2** | nThw 150/150; split-half **0.924**, peak **496.3 µV**, best **ch 8**. |

| 11 | `BSClosedLoop32-260831-182722` | **Phase 2**: site **D3** | nThw 150/150; split-half **0.946**, peak **419.8 µV**, best **ch 8**. |

| 12 | `BSClosedLoop32-260831-183157` | **Phase 2**: site **P2** (battery complete) | nThw 150/150; split-half **0.976**, peak **501.6 µV**, best **ch 8**. **Battery summary: modal best ch 8 (8/9 sites), LP→ch 6; peaks 382-709 µV; all split-half ≥ 0.92.** |

| 13 | `BSClosedLoop32-260831-183856` | **Phase 3**: randomized probing rnd1 (183k ticks, amps 2-25, 4257 probes) | Wire 4257/4257. Races front-loaded: 26.9%→1.1% doubled at t≈3 min — browser-close CPU stall forced a PLL re-lock from 0.14→1.39 ms margin (agent deep-dive; new rules: apps closed BEFORE runs, per-arm margin check, 30 s burn-in). **Fit: NO-GO — all 8 pairs refuse; sweep best \|corr\| 0.071 < 0.1.** Wav1 healthy all run (no PZ2 brown-out). |
| 14 | `BSClosedLoop32-260831-194938` | **Phase 3b**: high-amp re-probe rndhi (28k ticks, amps 9/18/25/30) | **Perfect delivery 648/648, margin 3.77 ms, 0 races** (hygiene works). **Still null at 30 µA all pairs. Artifact MODERATE in cortex → current flows in tissue → conclusion: stim array POSITION not coupled to recorded S1.** Reposition decision handed to surgeon. |

| 15 | `BSClosedLoop32-260831-201744` | **Phase 4b**: operating-point ID (opfit; PRBS 10↔30 µA pairs 1+4, 2 min, tonic) | **GO: |corr| 0.224-0.228 ch 8/6 (pair 4)**; model SAVED AllModels(10): 2-in/1-out ch 8, order 4, uOff≈[20.0 20.1], yOff 8.8e-5; plant_opfit.lti exported. Threshold nonlinearity (knee 13-18 µA) is why zero-origin fits failed. |
| 16 | `BSClosedLoop32-260831-204547` | **Arm mpc_mixr1 (FAILED — controller inert, rerun as mixr1b)** | Loop flawless (22200/22200, fresh 99.6%). But u1/u4 CONSTANT at offsets: at volt-scale features the QP objective (~1e-7) is below OSQP tolerance → solver returns the offset. **Fix verified in bench: `-QWeight 1e12 -RWeight 100`** (scales objective into numeric range, R/Q ≈ g²). Same scale-mismatch family as Choi's mu (1e-9→1e-13) and the gate local-minimum (disabled; operating-point model embeds the knee). All MPC runs carry the new weights. |

| 17 | `BSClosedLoop32-260831-210818` | **Arm mpc_mixr1b** (MPC closed loop, interleaved schedule r1, QWeight 1e12/RWeight 100) | **TRACKING — first ever on a real plant.** rBest 0.725 @ lag +2 ticks, slope y/r 0.92, trackIdx 5.29, ETA peak ratio 2.04 @ +3; u active pairs 1+4; loop 22200/22200 fresh 99.2%. Capture `capture_mpc_20260831_210645.csv`. |

| 18 | `BSClosedLoop32-260831-211935` | **Arm choi_mixr1** (Choi open-loop tape, schedule r1) | **TRACKING**: rBest 0.716 @ +1, r0 0.573, slope 1.15, RMSE 8.9e-5 (best of day). cpp path perfect (0 timeouts). |
| 19 | `BSClosedLoop32-260831-213101` | **Arm mpc_mixr2** (MPC, schedule r2) | **TRACKING**: rBest 0.712 @ +2, r0 0.380, slope 0.83 — MPC stable across schedules. Capture `capture_mpc_20260831_213029.csv`. |
| 20 | `BSClosedLoop32-260831-214109` | **Arm choi_mixr2** (Choi, schedule r2) | **TRACKING**: rBest 0.704 @ +2, r0 0.452, slope 0.92 — **open-loop lag-0 tracking decayed r1→r2 (0.573→0.452) while MPC held (0.393→0.380): the value-of-feedback signature.** |
| 21 | `BSClosedLoop32-260831-215429` | **Phase 7**: drift re-probe (opfit design replayed) | Pair 4→ch 8 \|corr\| **0.248** vs 0.224 at fit; pair 1 0.127. **Plant HELD (no structural drift)** → Choi's decay is open-loop sensitivity, not prep death. Stim wire zeroed post-run (400 zero packets, 8 words). |

<!-- appended live; do not reorder rows -->
