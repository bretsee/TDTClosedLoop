# Lab notebook — 2026-10-14, acute #3 (solo surgeon, late start)

**Outcome: no thalamic plant, no closed-loop arms. Banked: cortical placement series (3 D1 blocks)
and a 6-block thwack battery (D1, P1, MP, LP, P3, SHAM) with templates.** Hard stop 23:00 held.

## Timeline
- Induction/surgery ran long; both arrays implanted ~16:20 without auditory confirmation of either.
  17:00 depth-ladder stop lifted (surgeon's call, 16:25). First recording 20:07.
- 20:07 cortical gate cycle 1 (200749): GO z 23, but half-max footprint 63/64 ch. Re-referencing
  (minus per-sample median of 63 live ch) removes 92 -> 3 uV: the touch-evoked wave is COMMON-MODE,
  i.e. the recording reference sits on responsive tissue (Phase-0 item 4 was the unchecked box).
  Residual focal response ch47 -17 uV, consistent with the acute-#2 focus (34/39/40/47).
- 20:35 cycle 2 (203459): reference change attempted, common-mode unchanged (84 uV); ch47 +42 uV.
- 20:47 cycle 3 (204658), array +600 um: ch47 -35 uV @33 ms z 46, 3-ch footprint; common-mode 54 uV.
  Accepted as final. ch20 dead, ch39 weak (80% of common-mode).
- 21:15 thalamic gate depth 1 (211506), acute-#2 coordinates, 7.8 mm: delivery verified 720/720,
  pair mapping confirmed, NO-GO 0/8 pairs (acute #2 at the same coordinates: 8/8).
- Surgeon confirmed hardware: stim-enable ON, IZ2 blips per pair. Repositioned (AP/ML).
- 21:36 re-probe attempt 1 (213610, short design): VOID, Wav1 all zero (PZ2/headstage) — the 09-10
  failure mode again; y-liveness caught it. Fixed at the table.
- 21:46 re-probe attempt 2 (214559): y LIVE, delivery 240/240, NO-GO 0/8 raw and re-referenced.
- 21:53 decision: stop thalamic hunting, run the thwack battery. 21:55-22:14 P1, MP, LP, P3, SHAM.
- 22:29 all 6 battery blocks ingested, templates extracted (NNController outputs/.../touch/Acute_2026-10-14).

## Findings that matter offline
1. **Reference contamination.** Every touch block carries a 54-134 uV common-mode evoked wave on all 63
   live channels. The controller has no software re-reference, so raw y on any channel would have been
   the reference site. Fix for acute #4: reference on a skull screw / quiet site, verified by a 40-thwack
   gate BEFORE the thalamic array goes in; add a common-median option to the gate and to cpp y-extraction.
2. **ch47 carries a thwacker artifact.** SHAM (no touch) shows re-referenced ch47 +21 uV @18 ms z 19
   with no common-mode wave. P1/LP/P3 re-referenced ch47 (+25..27 uV @18 ms) are at that artifact level.
   Genuine focal responses beyond the artifact: MP ch47 -68 uV @23 ms z 62; D1 ch47 -35 uV @33 ms.
   Row 5 (ch33-38) +7-10 uV @16 ms on all palm sites, silent in SHAM = small genuine differential map.
3. **Thalamic array not coupled to this S1 at two positions** with current verified at the command
   monitor. Wav1 (610 Hz) shows no stim artifact even in the acute-#2 GO block, so "artifact = current
   flow" is not a usable test on this stream; it needs the raw stream or a current monitor.
4. **Tooling:** today's blocks nest one level deeper than `--newest` expects (Acute_101426\<blk>\<blk>);
   every check line needed `--block`. Fix `newest_block_dir` to recurse. `2_loop.ps1:176` Join-Path
   error when -Capture has no directory (benign). `design_rungate_short.csv` (18/25/30 uA, 10/cond,
   1.6 min) added for re-probes.

## Templates
`extract_nthw_templates` VERDICT OK for D1/P1/MP/LP/P3, SHAM = noise-level template. These are RAW
(common-mode dominated); re-referenced versions should be regenerated offline before use as targets.
