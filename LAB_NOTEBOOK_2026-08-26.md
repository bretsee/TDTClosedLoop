# Lab notebook — 2026-08-26 (suite move day; SURGERY MOVED UP TO THU 08-27)

Schedule change: the acute experiment is **tomorrow, Thu 2026-08-27** (was Fri
08-28). Today = suite validation + the new `nThw` pipeline + tomorrow's runbook.
Session docs written today: `RIG_DAY_2026-08-26.md` (today), `RIG_DAY_2026-08-27.md`
(surgery runbook, THE document for tomorrow).

## Protocol decisions (user, 2026-08-26)
- Per arm: **100 elicited touch responses × 10 sites (9 + SHAM) = 1000/arm**;
  one 22,200-tick run per (arm, site) = template ×100 with 2 s gaps; **site
  order randomized per arm** (seeded, manifest-recorded). Arms modular; cut
  order nncl → nnol.
- SHAM = thwacker runs with the same `nThw` output, touches nothing; its REAL
  extracted (noise) template is the sham tape; templates are archival artifacts
  (npz + meta committed).

## Preflight after the move — ALL GREEN (details in RIG_DAY_2026-08-26 PHASE A)
Static 10.1.0.1/24 persisted; RZ2 ACKs at 10.1.0.100; 0_preflight PASS;
UDP selftest A-E1 PASS (E2 → tomorrow pre-animal); cpp 13/13; choi 7/7;
PageHeap off; WER full dumps armed; 396 GB free; link still 10 Mbps (known
cable). Bench **19/22** — the 3 fails are the reference tests against the
zero-gain saline junk fit at AllModels(10), the documented false-fail; expect
22/22 after tomorrow's real `-Save`. Pushed `0a082e6..77bdd9b`.

## Built today (all verified off-rig)
- **`<NNC>/scripts/touch/extract_nthw_templates.py`** — per-block template
  extraction triggered by the new `nThw` epoc (rising=onset, falling=offset),
  explicit `--site` whitelist (order-based inference retired), QC always
  (durations, ITIs, mPos/thwk agreement, gap-filled-offset warning, Wav1
  all-zero hard gate), same npz schema as the legacy extractor.
  **Regression: `--trigger mpos` on `Acute_121223\ExperimentBL-231212-210716`
  reproduces the legacy npz BYTE-IDENTICALLY** (shc 0.977, peak 400 µV);
  `--trigger thwk` agrees 150/150 with the mPos detector (median |dt| 2.9 ms)
  and confirms legacy thwk offsets are gap-filled (nThw's falling edge is new
  information). **Gotcha: `tdt.StructType.__contains__` is broken** — `'Wav1'
  in blk.streams` returns False even when present; always test against
  `.keys()`.
- **`rig/prepare_arm_runs.py`** — builds all 10 per-site 100-repeat tapes (via
  build_touch_reference subprocess), seeded per-arm site permutations →
  `run_manifest.json`, prints run-order checklist + the SHAM scoring
  `--transient-thresh` (median of real sites' defaults — a flat/noise sham ref
  makes tracking_metrics' default threshold degenerate). Smoke: 10×22,200-tick
  tapes, manifests byte-identical across reruns, `4_mpc_server -Reference`
  auto-Ticks picks up 22,200.
- `NNController/.gitignore`: unignore ladder for
  `outputs/BiomimeticInversion/touch/Acute_2026-08-2{6,7}/` (outputs/ was
  ignored wholesale — day templates would have silently not committed).

## 22,200-tick dress rehearsal (sim, toy@9, rWeight 1e-3, Nu 20) — PASS with a lesson
- Attempt 1: loop-side TOTAL failure from tick 1 (replies=0, `recv failed`,
  zeroTicks=22200) while the SERVER serviced 17,548 packets at median 1.8 ms —
  a startup race, NOT a length effect.
- Attempt 2 (1,300 ticks): clean (freshTicks 96.9%). Attempt 3 (full 22,200):
  **clean — 22,200/22,200, dropped=0, window 6/6/0, PLL resyncs 0, freshTicks
  98.8% (21,936), heldTicks 249, zeroTicks 15, timeouts 11%.**
- **Runbook guard: `policy=fresh` must appear by tick ~100 or abort+relaunch.**
- tracking_metrics at 100 repeats: exactly 100 transients found, ETA clean,
  self-consistent slope/corr; sham scored with the explicit threshold behaves.

## EVENING SUITE SESSION (20:00-23:00) — EXPERIMENT POSTPONED at day's end

### Banked
- **B1 quiet capture** (block `ClosedLoopTest_LD-260826-220719`, nests one
  level; report `quiet_2026-08-26.json` via NEW `rig/analyze_quiet_capture.py`):
  **Wav1/Wav2 DISK SAVING VERIFIED ON** (08-18 trap closed). sSig silent.
  Noise floor **8-11 µV** std (suite bath is REAL — the old downstairs bath's
  ~10 mV floor / 1.44e-3 V baseline was the anomaly, user concurs "possibly
  erroneous"). Feature baseline (MAV6) ~7-9e-6 V/channel. 60 Hz+harmonics =
  **73% of 5-200 Hz power** (relative dominance, absolute ~7 µV) → fit-side
  notch stays planned, re-judge on tissue.
- **Headstage validated by the common-bath test** (channels sharing a bath must
  correlate): 14/16 channels at ~0.90 mean cross-corr, 60 Hz phase-locked 1.00
  → genuinely coupled, not open-input amp noise. **Ch 13 BAD** (corr 0.18,
  38 µV private broadband — bad contact/pin; blacklisted for the experiment).
  Ch 16 marginal (0.81), usable.
- **PHASE C — nThw FULLY VALIDATED** (blocks `LD-260826-221416`, `-221752`,
  150 programmed thwacks each, both effectively sham in saline):
  **nThw is a float32 STREAM @ 24,414 Hz** (0/1), NOT an epoc — extractor
  gained stream-edge detection (rising/falling, ~41 µs resolution,
  `--min-pulse-ms` glitch guard; negative-tested on the flat quiet block).
  **150/150 pulses detected in both blocks**; contact width machine-uniform
  254.6 ms (real falling edges — NOT gap-filled; one 2.7 ms runt in block 1 →
  use `--min-pulse-ms 50` on the day). ITI ~0.97 s. **mPos/mCtl are FLAT** —
  this thwacker bypasses the manipulandum stores; nThw is the only touch
  record; QC = count vs programmed count. Templates noise-level as expected
  (split-half −0.03/−0.33, peak ~7 µV, "best ch 13" = the bad channel winning
  on noise — consistent). Uniform machine-driven width ⇒ nThw fires on the
  device program regardless of contact ⇒ the SHAM condition works.
- **prepare_arm_runs on the REAL suite templates**: 2×22,200-tick tapes,
  manifest, per-arm orders, sham threshold — end-to-end chain
  (record → extract → npz → tapes → manifest) proven on real data.
- Decisions logged: **2x rate SKIPPED (no circuit change) — locked to the
  validated 610 path**; sham scoring threshold mechanism in the manifest.

### THE BLOCKER — PO8e receives ZERO frames from the RZ2 (unresolved)
First live `2_loop` threw **`Block index mismatch: 0 != 1`** (string lives in
PO8eStreaming.dll, not our code). Isolation with a card-only probe
(`--controller constant --constant-output 0 --skip-udp-send`, no stim
possible): Device Manager shows the card **Status OK**; probe connects
(`Source is collecting (PO8e)`) then **`Waiting for stream...` forever**.
No effect from: Synapse Preview, Idle→Preview re-arm, a **fiber swap**, fresh
card connects. So: PC card/driver/connect healthy; **the RZ2 is not sending**.
Leading hypothesis (UNTESTED): the PO8e interface **dropped out of the rig
file during the PZ2 16→32 hardware re-detection** earlier today (recording to
disk kept working — it doesn't touch the tap), or the streamer gizmo is
orphaned/disabled in the experiment tree; also untested: wrong optical port
(PO8e vs amp port), original fiber back, RZ2 power-cycle, PC reboot.
**Full morning debug ladder: `RIG_DAY_2026-08-27.md` PHASE −1** (probe command
included; PASS = the `Streaming. numChannels=16 sampleBytes=4` banner).

### Also noted
- PZ2 in the suite has banks for ~96+ channels; user deliberately stayed at
  **16 cortical channels** with the proper 16-ch headstage (validated above) —
  32-ch iteration deferred until after this experiment.
- Per-shell gotchas bit again in fresh suite terminals (wrong cwd, execution
  policy, exit-53 PATH) — all three are first lines of PHASE −1 step 0 now.

**STATE AT CLOSE: experiment postponed until the PO8e stream is restored;
everything else on the critical path is banked and green. Deferred to the
morning: PHASE −1 ladder, then merged B2+B3 run, then the 13 s MPC check —
both green ⇒ RIG_DAY_2026-08-27 is a GO from PHASE 0.**
