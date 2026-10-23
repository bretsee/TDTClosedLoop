# Lab notebook — 2026-10-22 / 23 (acute #4)

Started late (external), surgeon solo, engineer lane run remotely from this PC through the new
`rig/drive_live_run.py` (terminal A/B from a runcard, the loop's `go` prompt answered from a signal file
on the surgeon's word). 23:00 stop lifted; last stim run 00:10, wrap 00:20. Block ledger:
`BLOCK_LEDGER_2026-10-22.md` (12 rows, all filled). Day folder: `day_2026-10-22\`.

## Headline
1. **Cortical readout was clean for the first time since acute #2.** Brand-new 64-ch array (factory impedances,
   saline check skipped by the surgeon's decision; impedance-on-receipt added to the next electrode batch).
   `ARRAY HEALTH: OK` 64/64 at 19:45, 23:19 and 00:10 (pair-corr 0.78-0.81, no dead banks).
   D1 thwack (150): ch62 −374 µV @ 23 ms, z 59, split-half 0.99; sham (150): nothing (z 2). The gate's
   common-mode rule flagged D1 (CM −186 µV) and was overruled on evidence: 62/64 contacts negative while
   ch52/ch60 read ~0 µV, which a reference pickup cannot produce. **Control channel ch58.**
2. **Thalamic ladder at the acute-2 AP/ML, depths to the TIP from the BRAIN SURFACE: NO-GO at 7.8, 7.0, 6.7 and
   7.0 again** (short design, 18/25/30 µA, 30 probes/pair). 7.0 gave a non-reproducible near miss (pairs 5/7,
   z 4-4.7 @ 16 ms in one block, z < 3 in the repeat; pooled 60 trials max z 4.2). Delivery verified on every
   run, IZ2 LEDs green throughout. Surgeon declined a reinsertion (16 microwires, damage) — reasonable.
3. **The site IS coupled, but only to long bursts, and one-dimensionally.** 30 µA burst ladder (B = 1/3/10
   ticks, delivered as 2/5/16 pulses, see item 5): 16-pulse bursts → 5/8 pairs responsive (−116…−195 µV,
   slow negativity building over the 157 ms burst, split-half 0.6-0.9, per-trial strength 1.0-1.5 = acute-2
   range) with effective rank 1; 5 pulses → pairs 4 and 8, rank 2; 2 pulses → nothing. This is the acute-2
   tonic-saturation mode at a second site. New tool `rig/burst_gate.py` (block-based, median-filter
   artifact-robust). The standard `placement_gate --mode thalamic` on that block says "GO 7/8 rank 6" and is
   WRONG: its 8 ms peaks are the second pulse's artifact. Do not quote it.
4. **No closed-loop arms.** Two duty-PRBS ID runs: 8-pulse bursts at 15-30 µA (under-driven: block shows pair 8
   marginal only) and 16-pulse bursts at 25-30 µA on pairs 1/4/8 (block: pair 1 z 16, pair 4 z 11, pair 8 z 6;
   capture features: +60 % MAV for ~5 ticks from lag 8-10, dead time 10 ticks). The MIMO fit explains
   0.1 % of the tick-level feature variance either way (delay 2 or the measured 9, orders 1-4). Pre-registered
   rule (valFit > ~10 %) → stop. The response exists but is not controllable in the controller's feature space.
5. **RIG BUG FOUND AND FIXED: `MpcPo8eUdpClosedLoop.exe` never calls `timeBeginPeriod`.** It keeps its 10 ms
   cadence only while some other process holds the Windows timer at 1 ms. At 69 s into the burst run that
   process went idle, the timer fell to 15.62 ms, every other tick fired ~5.6 ms late (lateUs 5.3-5.8 ms =
   15.62 − 10) and 8811/28917 control ticks were dropped; every stim word was held 1.6× (hence 2/5/16 pulses,
   uniformly, all 720 events). The three 91 s gate runs earlier had 0 drops by luck. Fix: `rig/timer_hold.py`
   (timeBeginPeriod(1); raises the global resolution — verified from another process) started by
   `drive_live_run.py`, which also runs A and B at HIGH priority. Verified: 5000-tick no-stim loop 4 dropped;
   both duty-ID runs 30k ticks, 0 dropped, 0 resyncs. **TODO: call timeBeginPeriod(1) in the exe at startup and
   rebuild; add a "Scheduler resync" count to run_audit.** The finalBuffered=65536 pattern is NOT this bug
   (09-10 runs had it with 0 drops).
6. Reduced thwack battery (surgeon's call, rank-limited plant): MP (163; ch19 −571 µV @ 28 ms, polarity reversal
   at ch52/60 → genuine local pattern) and **P2 (149; −1.3 mV on ch7 @ 38 ms, every one of 64 contacts ≥ −120 µV,
   most ≈ −900 µV, including the D1-silent ch52/60)**. P2 carries a ~−700 µV component common to every contact
   on top of a D1-like gradient: reference pickup (positive far-field at the skull screw) or a mechanical /
   arousal component — unresolved; template usable only with that caveat. P1/LP/P3 not done (wrap chosen).
7. Quiet block: blacklist ch33 (line-dominated), baselines ch34 1.38e-4 V, ch58 2.07e-4 V, array median 1.77e-4 V.

## Known-answer / validation notes
- Sham thwack block = clean null for the cortical gate (thwacker TTL alone evokes nothing).
- The artifact rule: a stim-pulse artifact is a one-sample spike at k × 9.83 ms; the `burst_gate` median
  filter (5 samples) removes it; a cortical wave survives. Applies to `placement_gate` thalamic too — fix it.
- The CM rule misfires on broad responses: a reference pickup adds the SAME wave to EVERY contact, so the
  presence of near-zero contacts (D1: ch52/60) or a polarity reversal (MP) clears the reference. Make this the
  rule in `placement_gate --mode cortical` instead of the amplitude ratio.
- One aborted attempt (gate4 #1, 23:3x): y DEAD at 30 s because Synapse was not streaming; loop killed,
  stim_zero sent, files in `day_2026-10-22\dead_gate4_attempt1`. The sequence that worked all night:
  B at the `go` prompt → recording ON → stim-enable ON → `go`.

## Files
`rig/drive_live_run.py`, `rig/timer_hold.py`, `rig/burst_gate.py` (new); `design_runburst30.csv`,
`design_rundutyid_burst8.csv`, `design_rundutyid_burst16.csv` (+meta); `day_2026-10-22\runcard_*.txt`,
`driver_*.json`, `loopB_*.log`, `server_*.log`, `dead_time_*.json`, `fit_dutyid*_matlab.log`,
`plant_duty_burst8_valfit0.lti`, `last_audit_burst30_FAIL.txt`; `galleries\<blk>\{gate_cortical,gate_thalamic,
burst_gate,array_health}.png`. Archive: `Desktop\Data\Archive\TDTClosedLoop_2026-10-22.zip`.

## Open for the post-mortem
- Rebuild the exe with timeBeginPeriod(1) (and keep the holder as belt-and-braces).
- Re-grade all 10-14 and 10-22 thalamic blocks with the artifact-robust estimator; fix the CM rule.
- P2's global wave: compare against the skull-screw reference hypothesis with a re-referenced template.
- Acute-2 vs acute-4 thalamic position: the acute-2 reference plane was never written down; 7.0-from-surface
  did not reproduce 8/8. Next acute: write the plane, consider audio-guided descent (docs/ACUTE4_LOCALIZATION_METHODS.md).
- Both repos remain uncommitted (10-14, 10-16, 10-21, 10-22).
