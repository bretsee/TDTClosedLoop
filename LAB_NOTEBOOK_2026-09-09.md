# Lab notebook — 2026-09-09 (WEDNESDAY): 64-ch + MIMO validation day

**STATUS: FINAL (end of day 2026-09-09). ALL GATES GREEN — GO for acute #2
on 2026-09-10 at 64-ch / MIMO / cpp-primary / new Microprobes map.**

Goal: validate the full 64-ch recording + MIMO cpp-primary control stack in the
surgical suite so acute #2 (2026-09-10, `RIG_DAY_2026-09-10.md`) runs with zero
unknowns. Rig re-assembled by the user earlier this week; PO8e bracket from TDT
en route (not yet installed).

## Context set this morning

- Research agent report: `RESEARCH_CONTROL_NOVELTY_2026-09-09.md`. Choi 2016
  identified and full-text verified (Choi, Brockmeier, McNiel, von Kraus,
  Príncipe, Francis, *J Neural Eng* 13:056007) — their QP was computed offline
  per condition and delivered OPEN-loop; our receding-horizon feedback closure
  is the direct answer to their stated limitation. No prior real-time feedback
  MPC tracking of biomimetic cortical templates via thalamic stim found; no
  MIMO version anywhere. Closest prior art ranked in the report (watch:
  REACH-Ctrl, bioRxiv 2026-03 — precomputed minimum-energy steering, macaque).
  Their r=0.78 vs our 0.71: lead with drift immunity / latency stability /
  29.5% charge, not raw fidelity.
- Experiment (.synexpz) sent to Mark @ TDT last night; his DSP-spread 64-ch
  rework may return files. DECISION RULE: today validates OUR manually widened
  circuit; Mark's version is imported only if it arrives with time to re-bank
  S2–S4, else acute #3.

## Gate ledger (RIG_DAY_2026-09-09.md)

### S0 — PC + toolchain: PASS
- PO8e present on PCI bus (VEN_4550, Status OK) — before bracket install.
- `0_preflight -InputChannels 64`: first run WARN droppedControlTicks=1
  (boot-time load), immediate re-run clean PASS (300/300, exact 64/64).
- `cpp_controller --selftest` 13/13; `bench_test_reference_mpc` ALL PASS
  (28 checks incl. MIMO featureChannel map + arity).

### S1 — Synapse 64-ch config (user, rig PC): DONE
- New experiment saved from the 32-ch one; PZ2 Channels 64 initially went
  **RED** — same failure shape as 08-26: rig-side PZ2 device width < gizmo
  width. Resolved by the user via manual rig edit (no Detect). DSP compile
  (squares-greening window) completed at 64 ch — our circuit fits the RZ2's
  DSPs without Mark's rework.
- .synrig export: done after the 64-ch compile; **the MCMap changed later,
  so a RE-EXPORT tonight is on the user's leave-checklist** (acknowledged).
  Pre-teardown export was never made; Synapse Backups live on the rig PC
  only — 8/30 backup zip preserved to the lab NAS 09-08.

### S2 — 64-ch acquisition (dry): PASS
- Probe banner: `Streaming. numChannels=64 sampleBytes=4 (float32)`,
  `channelMode=exact(in=64 card=64)`, 300/300, dropped=0, window 6/6/0,
  RZ2 ACK, totalTick avg 11.8 µs. One startup `Skipping` (pre-attach Preview
  history flush), none mid-run.
- Quiet block `BSCL20260909BU-260909-144847` (61.7 s, dry, headstages in
  air): Wav1 (64, T) @610.35 Hz and Wav2 (64, T) @24414 Hz both fully live —
  **all 64 channels nonzero, both banks** (zeros-above-32 trap did not
  recur). Line noise dominates (median 60 Hz+harmonics fraction 0.997) as
  expected dry; fit-side notch remains the plan.
- WATCH: bank asymmetry dry — ch 1–32 noise 3–9 mV vs ch 33–64 0.6–1 mV
  (~5–10×). Probably antenna geometry of dangling headstages; tomorrow's
  Phase-1 common-bath correlation is the arbiter. Not a gate item today.

### S3 — 64-ch loop soak (live stream, zeros on wire): PASS
- Ops note: loop sat at `Waiting for stream...` because Synapse dropped to
  Idle after the S2 recording (+ one unrelated Synapse crash, user recovered);
  latched instantly once Preview restarted.
- `Summary: packets=6000 controlTicks=6000 droppedControlTicks=0
  nominalWindowSamples=6 minWindowSamples=6 undersampledWindows=0
  channelMode=exact(in=64 card=64)`.
- Frame-locked PLL: phaseErr avg 0.62 ms max 3.86 ms, **resyncs 0**.
- cpp server: **timeouts 0, staleDropped 0, freshTicks 5999/6000** (single
  zeroTick = tick 1; policy=fresh from tick 2). Compare MATLAB-server era:
  5–13% timeouts on every prior rig day. cpp-primary vindicated on hardware.
- totalTick avg 37.2 µs at 64-wide features. Capture `y1..y64` × 6000 rows.
- finalBuffered 36001/65536 after 60 s — known ring-growth watch item
  (benign at 22.2k-tick run length per 08-31, ring holds only newest-6 use).

### S5 (sim half) — MIMO closed-loop dress: PASS
- `closed_loop_sim --plant plant_mimo_test.lti` + cpp mpc (pairs 1,4;
  q 1e12; r 100): 1300/1300, timeouts 0, round-trip mean 0.027 ms p95
  0.034 ms, command range 12.26 around uOffset — controller demonstrably
  feedback-responsive. Matches 09-01 banked sim. (y prints 0.0000 = 4-dp
  display rounding of volt-scale features; cosmetic.)

### NEW TOOL: `rig/check_mimo_rank.py`
- DC-gain SVD gate for fitted MIMO plants (from the novelty/optimality
  research actionables). Reads .lti, reports G(1), singular values, effective
  rank vs p, condition, steerable mode directions; PASS/WARN/FAIL verdicts.
- First run on `plant_mimo_test.lti` (09-01 fit, outputs ch8+ch6 from 08-31
  pairs 1+4 data): **FAIL — effective rank 1 of p=2** (SVs 5.41e-6 /
  1.73e-7, ratio 0.032, cond 31; both modes' input directions nearly
  parallel). This is the 08-31 selectivity negative made quantitative: ch6
  and ch8 ride the same stim footprint. TOMORROW: run this on `plant_rnd1.lti`
  right after the Phase-4 fit and choose control channels that PASS before
  committing arm runs.

### Thalamic stim mapping (new Microprobes 2×8 VPL array) — IN PROGRESS
- Current MCMap (RPvdsEx), unchanged from old Acute + Acute #1:
  1-1, 2-9, 3-2, 4-10, 5-3, 6-11, 7-4, 8-12, 9-5, 10-13, 11-6, 12-14,
  13-7, 14-15, 15-8, 16-16 — i.e. (2k−1)↔k and (2k)↔(8+k): the
  interleave/de-interleave between GROUPED logical order (1–8 = anode legs,
  9–16 = negated cathode legs of words 1–8) and PHYSICAL connector order
  (adjacent electrodes (2k−1, 2k) = bipolar pair k). Direction of the pair
  list (in→out vs out←in) not independently confirmed, but both readings
  encode the same pairing structure; physically verified in data three times
  (sal1 08-17: inversion corr −1.000000 all 8 pairs; gates 08-27, 08-30).
- Plan for the new array: keep word→±bank logic untouched; only the
  permutation changes, built from the Microprobes site→pin wiring table so
  logical k / 8+k land on the chosen anatomical pair. Verification = S4
  pair attribution.
- **New array documented: Microprobes MEA #20786** (part
  MEA-PI-A3-00-16-X-8-3-0.25-0.5-1-1SS-1, A79038-001 Omnetics, inspection
  2023-03-29; PDF on Desktop). Pin 1 = REF (10 kΩ, 8 mm), pin 10 = GND
  (5 cm wire); stim sites 0.1 MΩ. **Rows column-aligned (NOT mirrored):
  pins 11–18 sit under pins 2–9 with per-column length match — lengths
  7.4, 7.6, 7.8, 8, 8, 8, 8, 8 mm (VPL curvature profile, identical both
  rows).** Chosen cross-row bipolar pairs in PIN numbers: pair j = pins
  (j+1, j+10), j=1..8.
- **Adapter layer RESOLVED (user anchor: "channel 1 drives the tip" on the
  old A1x16 ⇒ cable unscrambles to NN site order, channel = site).** NN
  CM16 mapping doc (photos): bottom pin row l→r = G,16,15,14,13,4,3,2,1,R;
  top row = 12,11,10,9,8,7,6,5; A1x16 depth order tip→top =
  1,16,2,15,3,14,4,13,5,12,6,11,7,10,8,9. Ref/gnd hazard CLEARED: both
  vendors use pins 1+10 for ref/gnd (roles swapped) → all 16 stim lines
  land 1:1.
- Pin→channel: pins 2–9 → ch 16,15,14,13,4,3,2,1; pins 11–18 → ch
  12,11,10,9,8,7,6,5. Cross-row pairs (word: +ch,−ch): 1:(16,12) 7.4mm,
  2:(15,11) 7.6, 3:(14,10) 7.8, 4:(13,9) 8, 5:(4,8) 8, 6:(3,7) 8,
  7:(2,6) 8, 8:(1,5) 8. Row 1 = anode leg.
- **New MCMap entries (out←in convention, same as old file):
  1-8, 2-7, 3-6, 4-5, 5-16, 6-15, 7-14, 8-13, 9-12, 10-11, 11-10, 12-9,
  13-4, 14-3, 15-2, 16-1.** Verification signatures: word 1 → ch 16&12
  inverted; word 8 → ch 1&5. If vendor-diagram mirroring slipped in, word
  1 shows on (1,5) instead — fix = reverse along both rows. NOTE:
  check_impulse_delivery's pair attribution predates non-(2k−1,2k) maps —
  read its detected pairs against the table; patch to accept a pair table
  if it hard-fails on stale expectation.
- **MAP VERIFIED IN DATA — PASS, all 8 words** (block
  `BSCL20260909BU-260909-202840`, send_envelope 1-8 staggered saw uMax 10;
  one-off analysis: scratchpad check_map_attribution.py, 16×8 rectified-
  envelope attribution matrix). Every word → exactly the mapped channel
  pair at |corr| 0.96-0.97 (background 0.45 = staggered-saw envelope
  cross-corr, not bleed); pair raw inversion −1.0000 exact on all 8.
  User re-entered map in RPvdsEx, recompiled, reopened Synapse (stale-
  apply avoided). The thalamic mapping GATE IS CLOSED.

### S4 — wire-level stim re-bank: PASS (banked under the NEW map + 64-ch circuit)
- Deferred until the MCMap edit was final so the banked gate matches
  tomorrow's config. Run rndw (1c_server random, 28k ticks, uMax 30),
  block `BSCL20260909BU-260909-203705`.
- **DELIVERY VERIFIED**: wire == design 473/473 designed pulses, 0 lost;
  per-probe 0 missed / 471 single / 2 double (0.4%) — this run's carrier
  phase margin was 1.60 ms (racing regime; phase re-rolls per recording,
  known physics, not a fault). Carrier base/240 = 101.725 Hz at exactly
  6.000 samples/period.
- **Pair attribution: all 8 words on the new-map pairs, inversion EXACT**
  — first run "FAILED" purely on the tool's hard-coded legacy (2k−1,2k)
  expectation while its own detected channels were exactly the new map
  (predicted false-alarm). `check_impulse_delivery.py` patched with
  `--pairs a:b,...` (default legacy); re-run VERIFIED, 0 hard failures.
  **Tomorrow's Phase-3 command must carry
  `--pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"`.**

### S5 (live-wire half) — 13 s MPC dress at 64: PASS
- 1300/1300, dropped=0, window 6/6/0, exact(64/64); localhost timeouts 0,
  fresh 1299/1300 (single startup zeroTick); server turnaround avg
  0.023 ms p95 0.031 ms max 0.064 ms; latency CSV written (defaults on).
- Feature map 40,33 (both above ch 32) accepted — 64-wide plumbing proven;
  u1 varied 22.6–24.5 around the applied uOffset, u4 at cap, inactive
  pairs exactly 0; capture y1..y64 × 1300; clean stim-zero shutdown.

### S6 — decision: **GO AT 64-ch / MIMO / cpp-primary / NEW MAP.**
- All gates green under the exact Thursday config. 32-ch fallback not
  needed. Planning session + wrap follow below.
- Experiment plan review + improvements session: PENDING (planned after
  validation).

## Planning wrap (end of day)

- **Design upgrades adopted for tomorrow (user-approved):** (1) EARLY/LATE
  REPEAT — both arms of run r1 re-run with identical tapes at day end
  (Phase 7), giving a measured within-day drift number per arm; (2)
  DECOUPLED-TARGET RUN — new `rig/build_decoupled_ref.py` (tested;
  sim-verified end-to-end through cpp MPC, 1300/1300) builds a
  round-robin one-active-output reference from any ref_mix; one such run
  in Phase 6 = the first-in-class MIMO selectivity exhibit. Both are in
  RIG_DAY_2026-09-10.md.
- Scoring upgrades (post-hoc, no rig dependency): shuffled-template
  nulls, identical charge accounting across arms, latency distributions,
  sliding-window r. To be applied in the results analysis.
- Mark @ TDT's reworked files did not arrive today → per standing rule
  they wait for acute #3; tomorrow runs our validated circuit.
- Leave-checklist (user acknowledged): stimulator on charge overnight;
  re-export dated .synrig (post-MCMap state); PO8e bracket NOT installed
  until after acute #2.
- Workflow: tank-dir network share deferred to tomorrow morning
  (share read-only on rig PC → UNC/mapped access from the analysis PC;
  point ingest at the share).

## Ops notes for the record
- Synapse falls to Idle after a recording stops — restart Preview before any
  loop attach (cost one stall today; also one unrelated Synapse crash).
- Analysis blocks live on the rig PC now; manual transfer per block. Workflow
  item (network share of the tank dir) parked for the post-validation
  planning discussion — matters for tomorrow's per-phase ingest cadence.
- PZ2 charged for testing (user, morning).
