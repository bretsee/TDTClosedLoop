# Lab notebook — 2026-10-21 (acute #4 preparation; acute #4 is Thu 2026-10-22)

Acute #4 was called for tomorrow this evening. Everything below is built from the 10-14 runbook and the
10-16 post-mortem; no hardware was touched (rig path as last verified 10-14).

## Built tonight
1. **`rig/array_health.py`** (new): `ARRAY HEALTH: OK / SUSPECT / BROKEN / UNINFORMATIVE` from any Wav1
   recording, no trigger needed. Per-contact own-signal RMS (channel minus per-sample median of the live
   channels), median pairwise correlation, PC1 share, dead 16-ch banks, 60 Hz share. Known-answer table:
   | block | context | verdict | own-signal | pair-corr | dead banks |
   |---|---|---|---|---|---|
   | 260910-185534 (acute 2 D1 GO) | tissue | OK | 44/64 | 0.858 | none |
   | 260910-200410 (acute 2 probe) | saline-mode | OK | 64/64 (relative) | 0.887 | none |
   | 261014-204658 (10-14 gate 3) | tissue | BROKEN | 21/64 | 0.977 | 1-16, 49-64 |
   | 261014-221419 (10-14 SHAM) | saline-mode | BROKEN | — | 0.994 | — |
   | 261013-195629 (10-13 bench, air) | tissue | UNINFORMATIVE (60 Hz share 1.00) | — | 0.999 | — |
   Thresholds: BROKEN = own-signal < 32 or corr >= 0.97 or a dead bank; SUSPECT = own-signal < 40 or
   corr >= 0.95 (the suspect limit was first 48 and the healthy acute-2 block read 44, so it was lowered).
   Saline context uses a relative own-signal threshold (0.3 x median) because saline carries no neural signal.
2. **`placement_gate --mode cortical`** now computes the array health, the **common-mode touch wave** (evoked
   mean of the channel median) and a **re-referenced focal map**, and prints a control-channel candidate
   (largest re-referenced peak among contacts with own signal and z in the top half of the map).
   Rules: BROKEN array -> NO-GO; common-mode wave > 20 uV AND > 50 % of the re-referenced focal peak ->
   MARGINAL + "move the REFERENCE"; raw half-max footprint > 32 ch -> MARGINAL.
   - Acute-2 GO block 185534: still **GO** (raw ch34 -219 uV z 34, fp 5; CM +63 uV; re-ref ch39 -357 uV).
     The absolute 20 uV rule alone would have downgraded this real, successful placement, hence the ratio.
   - 10-14 block 204658: **NO-GO** "ARRAY BROKEN" (raw ch47 +79 uV fp 63; CM +53 uV; re-ref ch47 -35 uV z 50 fp 3).
   - Figure is now 4 panels (raw z grid with x on contacts without own signal, re-ref z grid, raw/CM/re-ref
     means, re-ref single trials). Thalamic mode untouched (regression-checked on 211506 and the synthetic block).
3. **`blockutil.block_dirs`**: depth 3 and sorted by the `.tsq` mtime. On 10-14 blocks landed as
   `Acute_101426\<blk>\<blk>` and `--newest` (depth 2, folder mtime) missed every one; `--newest` now returns
   the 10-14 SHAM block as expected.
4. **`rig_runcard.py`**: new phase `cgate` (array_health + cortical gate + ingest), `--short` for the gate
   phase (`design_rungate_short.csv`, 18/25/30 uA, 1.6 min; delivery check amps and meta follow), phase-0
   saline array-check lines. `pull_blocks.ps1` defaults to `Desktop\Data\Acute_102226`.
5. **`RIG_DAY_2026-10-22.md` + `HELPER_CARD_2026-10-22.md`** (lint PASS, PDFs in `day_2026-10-22\`):
   Phase 0 gains array verification before induction (impedance at 100 Hz + 1 kHz to CSV, 60 s saline block ->
   `ARRAY HEALTH: OK`, thalamic wire gate into saline with IZ2 LEDs green); the reference plan (skull screw) is
   a checklist item proven by the gate's common-mode line; the thalamic ladder is a position list (acute-2
   7.8 mm first, then 7.0 / 6.5 / 6.0 per the literature, then AP/ML) on the short design with the full
   design once at the chosen position; the reference plane must be written down (checklist 14).
   Tier A/B/C, solo-mode batching, cut list and 23:00 stop carried over from 10-14.
6. Gate phase sim-rehearsed from the new runcard (`day_2026-10-22\rehearsal_gate_1021.log`).

## Deliberately not done
- No C++ rebuild (no software re-reference in the controller): the controller still reads the raw channel.
  Acute 2 shows a focal raw channel is fine when the reference is clean; the gate now proves that before G'.
- The 10-14 touch templates were not rebuilt re-referenced: tomorrow's battery produces today's templates.
- Both repos remain uncommitted (10-14, 10-16, 10-21 work).

## Open for the surgeon before 08:00
- Which cortical array goes in (the 10-14 one is broken: ch1-16 and 49-64 dead as banks). A different array
  needs its channel map (`--map`) and `-InputChannels`.
- Thalamic reference plane for "7.8 mm" (skull / dura / brain surface) — checklist 14.
- Staffing / start time / hard stop assumed as 10-14 (solo, 23:00).
