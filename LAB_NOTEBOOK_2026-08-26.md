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

## Still pending today (rig-side, user)
PHASE B saline gates (quiet capture + **verify Wav1/Wav2 SAVING**, artifact
retest, randomized-probe validation, 2x gate, dress rehearsal on hardware) and
PHASE C: **two nThw test thwack blocks** (block 2 must include no-contact
swings — the sham condition depends on nThw firing without contact). Then
Phase D: prepare_arm_runs smoke on the real test templates, push both repos.
