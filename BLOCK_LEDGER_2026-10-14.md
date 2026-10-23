# Block ledger — 2026-10-14 acute experiment

Backup/validation of the hand-written block annotations. One row per Synapse
block, appended live as blocks are handed over. All blocks under
`C:\Users\brets\Desktop\Data\` and nest one directory level.

| # | block | phase / purpose | key results |
|---|---|---|---|
| 1 | `BSCL20260909BU-261014-204658` | D1 thwack | GATE GO (final cortical position, +600 um). raw ch47 +79 uV @20 ms z 25, footprint 63 ch (common-mode); re-ref ch47 -35 uV @33 ms z 46, 3 ch. templates OK |
| 2 | `BSCL20260909BU-261014-215545` | P1 thwack | GATE GO. raw ch47 +127 uV @18 ms z 21 (common-mode 101 uV); re-ref ch47 +25 uV @18 ms (= SHAM artifact level), row-5 ch33-38 +7 uV @16 ms z 15-17. templates OK |
| 3 | `BSCL20260909BU-261014-220050` | MP thwack | GATE GO. raw ch47 +155 uV @16 ms z 29 (common-mode 122 uV); re-ref ch47 -68 uV @23 ms z 62 = strongest genuine focal response of the day; row 5 +9 uV. templates OK |
| 4 | `BSCL20260909BU-261014-220623` | LP thwack | GATE GO. raw ch47 +156 uV @18 ms z 36 (common-mode 134 uV); re-ref ch47 +27 uV @18 ms (artifact level), row 5 +10 uV z 27. templates OK |
| 5 | `BSCL20260909BU-261014-221014` | P3 thwack | GATE GO. raw ch47 +131 uV @18 ms z 27 (common-mode 106 uV); re-ref ch47 +25 uV @18 ms (artifact level), row 5 +7 uV z 15. templates OK |
| 6 | `BSCL20260909BU-261014-221419` | SHAM thwack | GATE NO-GO as expected (no common-mode wave, raw 7 uV). BUT re-ref ch47 +21 uV @18 ms z 19 with NO touch -> thwacker artifact on ch47; row 5 silent. noise-level template |
| 7 | `BSCL20260909BU-261014-200749` | D1 thwack, cortical gate cycle 1 | GO z 23 but 63-ch footprint = reference pickup; re-ref ch47 -17 uV. not used for templates |
| 8 | `BSCL20260909BU-261014-203459` | D1 thwack, cortical gate cycle 2 | GO z 25; re-ref ch47 +42 uV (artifact-dominated). not used |
| 9 | `BSCL20260909BU-261014-211506` | thalamic gate depth 1 (design_rungate, 13/18/25 uA, 720 probes) | AUDIT WARN (backlog only), DELIVERY VERIFIED 720/720, mapping confirmed; THALAMIC GATE NO-GO 0/8 pairs, best z 1.7 |
| 10 | `BSCL20260909BU-261014-213610` | thalamic gate after reposition, attempt 1 (short design) | VOID: Wav1 all zero for 197 s (PZ2/headstage), y=DEAD; delivery 32 missed/36 double from early recording start |
| 11 | `BSCL20260909BU-261014-214559` | thalamic gate after reposition, attempt 2 (short design, 18/25/30 uA, 240 probes) | y LIVE, DELIVERY VERIFIED 240/240; THALAMIC GATE NO-GO 0/8 raw and re-referenced. No thalamic plant today |
<!-- appended live; do not reorder rows -->
