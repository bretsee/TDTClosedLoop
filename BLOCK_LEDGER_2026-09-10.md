# Block ledger — 2026-09-10 (acute #2, 64-ch MIMO)

All blocks `BSCL20260909BU-260910-<time>` under `Desktop\Data\` (nested one
level), recorded on the rig PC and hand-transferred. Tank experiment name
carries the 09-09 date (created yesterday); blocks are today's.

| Time | Identity | Key result | Files |
|---|---|---|---|
| 183709 | Quiet baseline (in vivo, 64 ch) | Both banks live; baseline ~3.3e-5 V; blacklist 33/36/45/59; ~3-4x lower amplitude than acute #1 (surface array) | — |
| 185201 | SHAM thwack (150 no-contact swings) | Clean null: drift only, no locked component; null mags 17/50 µV | npz in NNC touch/Acute_2026-09-10 |
| 185534 | D1 thwack (150) | −297 µV @ 23 ms ch39; no OFF response | npz; Desktop\D1_thwack_trials.png |
| 191241 | LP thwack (150) | −474 µV @ 21 ms ch47; +ch64; SHARP OFF response at release | npz; Desktop\LP_thwack_trials.png |
| 191958 | D2 thwack (150) | −249 µV @ 26 ms ch39; split-half 0.967 | npz |
| 192302 | P1 thwack (150) | −529 µV @ 33 ms ch39 (day max); +ch64; late peak | npz |
| 192604 | MP thwack (150) | −525 µV @ 25 ms ch47; ch64 strongest (−317) | npz |
| 192914 | D4 thwack (150) | −370 µV @ 25 ms ch39; weak ch64 | npz |
| 193215 | D3 thwack (150) | −321 µV @ 28 ms ch39; no ch64 | npz |
| 193528 | P2 thwack (150) | −471 µV @ 23 ms ch47; no ch64 | npz |
| 193840 | P3 thwack (150) | −438 µV @ 26 ms ch39; +ch64 | npz |
| 200410 | rnd1 all-8-pair probe (STALE 08-31 DESIGN replayed: 7 amps 2-25, 183k ticks, wall-clock — `1c_server` label collision) | DELIVERY VERIFIED 4257/4257, 0 miss/0 double; **ALL 8 PAIRS RESPONSIVE** z 24-121 @ 8-11.5 ms; knees 9-13 µA; stim footprint ch64/56/39 | design_runrnd1.csv (08-31), capture_rig_runrnd1.csv |
| 210727 | opfit10 operating-point PRBS (fresh design: all 8 pairs, 10↔30, decorrelated 0.005, 24k ticks, wall-clock) | MIMO fit input → fit pending | design_runopfit10.csv, capture_rig_runopfit10.csv |

Arm-phase runs (captures local in `day_2026-09-10\`; Synapse blocks on the
rig PC, batch-transfer pending — match by run label/time):

| Run label | Identity | Result |
|---|---|---|
| opfit10 (210727) | 8-pair PRBS 10-30 op-point | gain≈0 — tonic saturation discovered |
| opfit11 (211953) | pairs 1+4 PRBS 10-30 | only pair4→ch64 0.111 |
| opfit12 (213208) | pairs 4+6 PRBS 8-22 | 5 ch >0.1, all via pair 4 → rank-1; MODEL SOURCE |
| mpc/choi_mixr1-r3 | paired arms, refs LP/P1/MP/P3/SHAM on ch64 | MPC 0.330/0.378/0.381 lag0; Choi 0.326/0.300/0.394 (rBest ≤0.469@−1) |
| mpc/choi_mixr1_late | early/late repeat (~2 h) | MPC 0.402 slope→1.000; Choi 0.339 flat |
| mpc_r4_chargematched | **VOID — PZ2 OFF** (dead features; ~642k µA-ticks delivered unrecorded) | retracted claims noted in notebook |
| nn_r1 | **VOID — PZ2 OFF** (~657k µA-ticks unrecorded) | rerun below |
| opfit12_late (first) | **VOID — PZ2 OFF** | rerun below |
| nn_r1b | NN inverse arm rerun (GRU R² 0.049 tape ≈ mean 14.8 µA) | NOT TRACKING r0 0.020 — honest negative + mean-drive null |
| mpc_r4b | charge-matched MPC (R 0.3, late-night) | 0.313@lag0, 303k µA-ticks (drift-confounded vs r1) |
| opfit12late2 | closing drift bracket | u4 gain HELD 0.132→0.137; u6 0.116→0.062 |

**Table 3 -- arm-phase raw Synapse blocks (TRANSFERRED 2026-09-11, dir
`Desktop\Data\Acute_091026-260910_LaterBlocks`).** Matched to run labels by
stim signature (sSig active-pair set `[2,4,5,7]` = pairs 4+6 under the new
map; `all-8` = NN tape) + Wav1 liveness + duration. All flat one level.

| Block (time) | Run label | Wav1 | Note |
|---|---|---|---|
| 215613 | mpc_r1 | LIVE 239 s | raw 64-ch now available for spatial/decoding |
| 220332 | choi_r1 | LIVE 256 s | |
| 221053 | mpc_r2 | LIVE 242 s | |
| 221543 | choi_r2 | LIVE 242 s | |
| 222149 | mpc_r3 | LIVE 243 s | |
| 222643 | choi_r3 | LIVE 264 s | |
| 223341 | mpc_r1_late | LIVE 255 s | |
| 223918 | choi_r1_late | LIVE 270 s | |
| 230004 | mpc_r4cm | DEAD 247 s | PZ2-off void (matches capture audit) |
| 230537 | nn_r1 (orig) | DEAD 241 s | PZ2-off void; all-8 pair tape |
| 231143 | opfit12late (orig) | DEAD 139 s | PZ2-off void; 12k-tick reprobe |
| 231833 | nn_r1b | LIVE 250 s | all-8 pair NN tape |
| 232426 | mpc_r4b | LIVE 238 s | charge-matched rerun |
| 233015 | opfit12late2 | LIVE 137 s | closing drift reprobe |

10 live arm blocks unlock the deck-v2 pending analyses (spatial footprint,
site-decoding, artifact-aware raw-LFP). The 3 DEAD blocks confirm the
capture-side y-liveness audit independently (recording side was genuinely
zero, not just the loop feed).

Yesterday's validation blocks (2026-09-09): 144847 = 64-ch dry quiet;
202840 = MCMap staggered-saw attribution test (PASS all 8 words);
203705 = S4 wire re-bank rndw (DELIVERY VERIFIED).

Conventions: touch battery via nThw, 150 thwacks/site, 254.6 ms contact;
new Microprobes pair table word:(+,−) = 1:(16,12) 2:(15,11) 3:(14,10)
4:(13,9) 5:(4,8) 6:(3,7) 7:(2,6) 8:(1,5); delivery audits require
`--pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"`.
