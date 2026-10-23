# Lab notebook — 2026-10-16 (acute #3 post-mortem: the cortical array was broken; weekly deck draft 1)

**User finding (10-15): the 64-ch cortical array is physically broken.** Re-examined every block with
that in hand (`day_2026-10-14/analysis/array_health.py`, `array_health_maps.py`, `battery_sites.py`;
JSON artifacts next to them; figures in `outputs/deck_figures/weekly1016_*.png`).

## Findings
1. **Signature present from the first 10-14 recording; no abrupt change inside the day.** Median
   pairwise channel correlation 0.977-0.994 on every 10-14 block (10 s windows: flat), vs 0.867-0.899
   on the same array across acute #2 (09-10 18:55 through the last block at 22:10). Channel-own
   (differential) RMS 6-8 uV vs 12.6-13.7 uV. PC1 share 0.94-0.97 vs 0.78-0.80.
2. **Which contacts survived.** Channels with > 10 uV of their own signal: acute #2 46-55/64 (all
   blocks incl. the last); acute #3 first block 27/64, battery 21/64. Rows 1-2 (ch1-16) and most of
   rows 7-8 are dead as a bank -> connector / lead-bundle damage. The break happened between the end
   of acute #2 and the first 10-14 recording (storage, cleaning, handling or the implant itself);
   the data cannot narrow it further. The 10-13 bench block was in air (pure mains, corr 0.999) and
   is uninformative; a saline impedance check would have caught it.
3. **Reinterpretation of 10-14.** The "reference on responsive tissue" reading was the right
   description of the signal (every channel = reference) with the wrong cause: open contacts float to
   the reference. The thalamic NO-GO (0/8 at two positions, delivery verified) is therefore not a
   placement result: the readout had ~21 live contacts, one of them (ch47) on the forepaw focus.
   Target position remains unknown.
4. **Battery stands, with caveats.** Genuine focal responses: MP ch47 -68 uV @23 ms (z 62), D1 ch47
   -35 uV @33 ms; row 5 (ch33-38) +7-10 uV on all palm sites, silent in SHAM. ch47 +21-27 uV @18 ms
   on P1/LP/P3 equals the SHAM level = thwacker coupling into one contact. Templates must be rebuilt
   re-referenced before use.
5. **Literature survey for acute #4** -> `docs/ACUTE4_LOCALIZATION_METHODS.md` (13 methods with
   sources; top-5 protocol). Notable: forepaw VPL is reported at 5-7 mm depth (Choi 2016: 6-7 mm,
   2.8 L / 2.4 P) while our tips are 7.4-8.0 mm; the reference plane must be written on the runbook.
   Impedance: 1 kHz alone can miss broken leads (Caldwell 2018); add a < 100 Hz point. Barrese 2013:
   48 % of array failures acute mechanical, 83 % of those connector-related.

## Deck
`scripts/build_weekly_deck_2026-10-16.py` -> `PythonIntanAnalysis/outputs/Synthesis/ClosedLoop_weekly_2026-10-16.pptx`,
draft 1: 31 slides, 17 figures, 5 tables, check_deck PASS 0 warnings. Framing: "Acute #3: an
instrumentation day" (the tooling worked, the array did not) + "Acute #4: verify first, then localize".
More drafts expected (audience framing).

## To do
- placement_gate: footprint + pairwise-corr + common-mode rules -> broken array = NO-GO.
- cpp y-extraction: common-median re-reference option.
- Rebuild 10-14 touch templates re-referenced (MP, D1 usable).
- Phase 0 for every acute: saline impedance at 100 Hz + 1 kHz, CSV in the block, logged.
- Commit + push both repos (10-14 and 10-16 work uncommitted).
