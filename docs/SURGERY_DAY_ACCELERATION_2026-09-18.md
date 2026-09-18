# Surgery-day acceleration: recordings by 15:30

Goal (user, 2026-09-18): anesthesia induction 09:00-10:00 and recording by
15:00-16:00, instead of after 20:00. Two acutes give the baseline.

## 1. Where the hours went (block timestamps; `scripts/surgery_timeline.py`)

| | acute #1 (08-31) | acute #2 (09-10) |
|---|---|---|
| induction (user) | ~09:30 | ~09:30 |
| first recording block | 17:40 | 18:37 |
| **surgery + implant + localisation** | **8.2 h** | **9.1 h** |
| first block -> first arm (battery, probe, fits) | 3.1 h | 3.3 h |
| arms span | 1.1 h | 1.6 h |
| last block | 21:55 | 23:30 |
| gap to a 15:30 first recording | 2.2 h | 3.1 h |

Two separate budgets have to shrink: the pre-recording block (8-9 h -> 6 h)
and the pre-arm protocol (3.2 h -> 1.5 h). Together that moves the first arm
from ~21:30 to ~17:00 and the wrap from midnight to ~20:00.

## 2. Positioning validation: the go/no-go gate (built and validated today)

`rig/placement_gate.py` answers "is the array where it needs to be, and if
not which way do I move it" from ONE short block, in ~3 s (cortical) or ~8 s
(thalamic), with a one-line verdict, a compact table, and a single PNG.

### Cortical gate (planar/laminar S1 array, thwack block)
```
python rig\placement_gate.py --mode cortical --newest --blacklist <today's list>
```
* Per channel: touch-evoked signed peak in 5-60 ms vs a shuffled-trigger null
  (same trial count, random onsets) -> z. Split-half reliability of the whole
  64-ch map, latency, half-max footprint size, focus position on the 8x8 grid.
* GO = best z >= 8, split-half >= 0.80, latency 8-45 ms, n >= 30 thwacks.
  MARGINAL = z >= 4 or split-half >= 0.60. NO-GO otherwise.
* ADJUST hint: focus within one row/col of the grid edge -> shift toward it.
* Validated: acute-#2 D1 block -> GO (ch34 -219 uV @ 23 ms, z 34, split-half
  0.95, 5-ch half-max footprint); acute-#2 SHAM block -> NO-GO (z 1.1).
* **A 40-thwack block (~45 s) is enough for the verdict.** 150 thwacks are for
  templates, not placement.

### Thalamic gate (VPL stim array, single-pulse probe block)
```
python rig\placement_gate.py --mode thalamic --newest --blacklist <list> --min-amp 13
```
* Per pair: signed-average raw LFP (amps >= 13 uA), per-channel peak in 6-30 ms
  vs shuffled null -> z; recruitment knee (smallest amp with z >= 3); footprint
  vector; pairwise footprint correlation; effective rank.
* RESPONSIVE z >= 5 | WEAK 3-5 | SILENT < 3. GO = >= 2 responsive pairs AND
  eff. rank >= 2. MARGINAL = 1 responsive, or several with one footprint.
* Validated in BOTH directions: acute-#2 probe -> GO, 8/8 responsive, knees
  6-13 uA, latencies 10-12 ms. **Acute-#1 probe -> GO with pairs 1, 4, 6
  responsive at 11-18 ms** -- the block where the fitter said NO-GO and the
  reposition was nearly called. The gate finds in 6 s what took a manual
  raw-LFP deep dive that evening. A stim-artifact guard (a peak on the
  window's first sample is re-searched) was needed for the 32-ch block.
* ADJUST hint: silent pairs reported by ladder position (short-tip 7.4-7.8 mm
  end vs 8 mm end) -> depth / AP direction.
* Quick probe design for the gate (4 min, not 30):
  `1c_server -Run gate1 -Schedule random -PulseAmps 13,18,25 -GapTicks 30 -GapJitterMs 40 -Ticks 24000`
  = 8 pairs x 3 amps x ~30 trials. At n = 228 the acute-#2 pairs read z 15-42,
  so n = 30 still gives z 5-15: above the RESPONSIVE bar for every pair that
  was real. The 30-min 7-amp probe stays for the recruitment curves AFTER the
  position is accepted.

### Rules the gate encodes (from the two acutes)
1. Surface/planar arrays are speaker-silent by geometry; the z table is the
   only placement criterion (09-10 morning scare).
2. A fitter null is NEVER a placement verdict; the signed raw-LFP average is
   (08-31 near-miss).
3. `rig/check_y_liveness.py --capture <csv>` in the first minute of every run
   (09-10 PZ2-off incident: three runs and ~1.3M uA-ticks recorded against
   zeros; validated today: mpc_r1 LIVE, r4_chargematched DEAD, exit 3).

## 3. Proposed day plan (clock times, 2-person)

| clock | surgeon | engineer (parallel) |
|---|---|---|
| 09:00-09:30 | induction, shave, stereotax | Phase 0: PnP check, preflight 64, UDP selftest, stimulator charged, designs staged (`design_burst_probe.py`), G8 pre-animal thwack test |
| 09:30-11:30 | scalp, craniotomies (cortical AND thalamic windows in one sitting) | rig PC: tank share mounted, Synapse in Preview, `ingest_block` watcher ready |
| 11:30-12:15 | cortical array placement at pre-measured coordinates (acute-#2 focus: ch34/39/47 region) | **cortical gate**: 40-thwack block on D1 or P1 -> GO/adjust; repeat until GO (each cycle ~3 min) |
| 12:15-13:30 | thalamic penetration to 7.8 mm on acute-#2 coordinates | **thalamic gate**: 4-min quick probe at each of up to 3 depths (7.6 / 7.8 / 8.0 mm), pick the depth with most responsive pairs + highest eff. rank |
| 13:30-14:00 | seal, let the prep settle | quiet capture (60 s) -> blacklist + baseline; y-liveness |
| 14:00-14:40 | thwack battery: 100/site, 6 sites chosen by achievability + SHAM | templates extracted per block as they land |
| 14:40-15:00 | 12-min recruitment probe (3 amps x 8 pairs x 40) | gate (full) + knees per pair |
| 15:00-15:30 | | **duty-cycled operating-point ID** (ONE 5-min duty-PRBS on the responsive pairs, replaces the 3 tonic ladders) -> MIMO fit + rank gate |
| 15:30-16:00 | | references + tapes + manifest (`build_interleaved_run.py`) |
| 16:00-19:00 | | ARMS (paired MPC/Choi schedules, decoupled-target run, time-controlled R sweep, early/late repeat) |
| 19:00-19:30 | | drift re-probe, stim zero, commit |

Pre-recording block: 6.0 h (was 8.2-9.1). Pre-arm protocol: 2.5 h including
the 30 min of settling (was 3.1-3.3). First arm 16:00 (was 20:45-21:55).

## 4. Where the surgical hours themselves can go (recommendations beyond the gate)

1. **Do both craniotomies before either implant.** Today the thalamic window is
   opened after the cortical array is seated; opening both in one drilling
   sitting removes a tool change and a re-draping.
2. **Pre-measured coordinates from acute #2.** The thalamic array was well
   placed (8/8 pairs recruit at <= 13 uA). Record AP/ML/DV and the array
   rotation from the 09-10 sheet as the default insertion target, and write
   them on the runbook. The cortical focus (ch34/39/47 = rows 5-6, cols 2-7 of
   the 8x8 grid, `spat_footprint` convention) fixes the array's centre.
3. **Depth ladder instead of hunting.** Insert to the shallowest plausible
   depth, run the 4-min gate, advance 200 um, repeat; stop at the best gate.
   Three gates = 15 min including advancing. Never go by audio.
4. **New-electrode familiarity.** A 30-min dry run the day before in agar (or
   the previous brain if kept) with the actual holder, the ZIF clips and the
   Microprobes cable: every acute so far has spent its first hour on handling.
5. **Sequence the engineer's work off the critical path.** Everything in the
   engineer column above runs while the surgeon is cutting; nothing in Phase
   0-1 needs the animal. Templates and gates run per block as blocks land
   (`ingest_block --newest` + `placement_gate --newest`).
6. **Battery: 100 thwacks x 6 sites** (split-half was >= 0.92 at 150; at 100 it
   stays > 0.9) and only the sites the arms will use. Saves ~40 min.
7. **Probe: 12 min, not 30.** Knees and z are stable at 40 trials/condition.
8. **Op-point ID: one duty-cycled run.** The three tonic ladders on 09-10 took
   an hour and found saturation; a single duty-PRBS (`design_burst_probe.py
   --kind duty-prbs`) fits all responsive pairs at once at a duty that
   avoids saturation.
9. **Cut list for a late day**: decoupled run -> R sweep -> r3 -> LP site;
   never cut the early/late repeat (cheapest drift number we have).

## 5. Files
* `rig/placement_gate.py` (new), `rig/check_y_liveness.py` (new),
  `rig/design_burst_probe.py` (new), `scripts/surgery_timeline.py` (new)
* Galleries: `galleries/<block>/gate_cortical.png|json`, `gate_thalamic.png|json`
* Runbook: `RIG_DAY_ACUTE3_TEMPLATE.md`
