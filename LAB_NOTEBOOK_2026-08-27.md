# Lab notebook — 2026-08-27 (suite): PO8e blocker resolved, gates banked, GO for 08-31

**Bottom line: the 08-26 "RZ2 not sending" blocker was the PO8e CARD UNSEATED
in its PCIe slot (transport damage from the suite move), not the rig file.
Reseat fixed it. Both deferred saline gates banked green. The acute experiment
is a GO for Monday 2026-08-31 (`RIG_DAY_2026-08-31.md`).**

---

## 1. Morning diagnosis — the blocker reframed

State at start (PC powered on 15:18 in the suite):

| check | result |
|---|---|
| RZ2 on 10.1.0.100 | **PASS** — GET_VERSION VALID ACK, protocol_version=1 |
| `0_preflight.ps1` | **PASS** — 300/300 sim ticks, dropped=0, window 6/6/0 |
| Card probe (`--skip-udp-send`, constant 0) | **"Found 0 card(s) in the system"** |
| `Get-PnpDevice` (VEN_4550) | **`CM_PROB_PHANTOM`** — registry ghost, card ABSENT from the PCI bus |
| System event log since boot | no WHEA/PCIe errors — the card simply never enumerated |

This is NEW relative to 08-26 evening, when the card enumerated (Status OK) and
connected but passed zero frames. **One fault explains both days: marginal PCIe
seating after the physical move** — day 1 the card enumerated but the data path
was dead; on the next cold boot it dropped off the bus entirely. The 08-26
leading hypothesis (PO8e interface lost from the rig file in the PZ2 re-detect)
is **falsified** — the rig file was never touched and never broken; PHASE −1
ladder steps 1–6 were never needed.

**Fix:** full shutdown, power killed at the source ~15 s, PO8e card reseated
(fiber checked at the card end), boot 16:08 → card **Status OK, CM_PROB_NONE**.

**Probe after reseat (Synapse Preview running): PASS** —
`Streaming. numChannels=16 sampleBytes=4 (float32)`, 300/300 ticks,
droppedControlTicks=0, feature window 6, clean stim-zero cleanup trace.

**Lesson (now in RIG_DAY_2026-08-31 PHASE 0 and the failure branches):**
"card connects but zero frames" and "Found 0 card(s)" are both PCIe-seating
signatures. Check `Get-PnpDevice | ? InstanceId -match 'VEN_4550'` BEFORE any
Synapse/fiber/rig-file debugging. Exit code 53 gotcha re-confirmed: the exe
needs all four MATLAB dirs (`runtime\win64;bin\win64;extern\bin\win64;sys\os\win64`)
+ `TDT_MATLAB_ROOT`, i.e. run `0_preflight.ps1` in the same shell.

## 2. Gate 1 — merged B2+B3, randomized-probe delivery + artifact retest

Run `rndval` (design reused from 08-26: 7 amps [2 4 6 9 13 18 25], random
schedule, GapTicks 36, jitter 60 ms, 28,000 ticks). Block
`ClosedLoopTest_LD-260827-182650` (nests one level). Loop clean, 28,000/28,000.

**`check_impulse_delivery` — VERDICT: DELIVERY VERIFIED (0 fail / 1 warn):**

- **Wire == design: 652/652 designed pulses reached the RZ2** — 0 lost,
  0 stretched, 0 multi (C++ server; the MATLAB-server sal1 pathology stays gone).
- **Pair mapping exact on all 8 words** (word k → electrodes (2k−1, 2k),
  inversion EXACT, focality ~7e10x).
- **Carrier 101.725 Hz = base/240 confirmed in the SUITE circuit**, exactly
  6.000 acquisition samples/period → `-FeatureWindow 6` stands.
- Command→latch phase this run: 5.86 ms of 9.830 (margin 3.97 ms — safe roll).

**The audit's "12 missed probes (1.8%)" warning is NOT latch races — it is the
stim enable gate, and it re-confirms the safety chain.** Operator note: the
stim control was switched on shortly after `go`. Measured from the block:
first UDP command t=16.8 s, first carrier pulse (`Plse`) t=22.071 s, first
`Scle` span t=22.111 s. The 12 "missed" probes are exactly the probes designed
into that 5.3 s pre-enable hole. **Post-enable: 640/640 probes delivered
exactly ONE carrier pulse — 0 missed, 0 doubled, zero true latch races.**
New circuit fact: **the enable gate blocks `Scle` as well as the carrier**
(no scale spans before enable; on 08-12 we only established the carrier half).
Runbook sequence updated: recording → `go` → enable ON immediately.

**`assess_artifact` — VERDICT: ARTIFACT MODERATE (0 fail / 0 warn, 1 info):**
640 events on all 8 words, amps 2–25. Controllable (off-pair) channels:
stdRatio 1.0–1.1, peak/noise 1.3–3.2 — measurable, not dominant.
**Decision: `--feature-trim` stays OFF for 08-31** (whole-period window + DC
removal adequate). Per the tool: re-assess on the first in-vivo probe block
before trusting lag-0 content. Ch 13's ~30x tick0 values are the blacklisted
channel's private noise, not artifact.

## 3. Gate 2 — 13-second MPC closed-loop check

`4_mpc_server -Reference ref_steps.csv -RWeight 1e-3 -ControlHorizon 20
-Pairs 1 -FeatureChannel 1 -ModelIndex 9` (toy plant) + 1,300-tick frame-locked
loop. Block `ClosedLoopTest_LD-260827-184414`. Capture
`capture_mpc_20260827_184338.csv`.

- 1,300/1,300 ticks; **`policy=fresh` at tick 19** (startup race avoided);
  clean stim-zero shutdown.
- **`tracking_metrics` (tracking_mpccheck_20260827.{json,png}): u1-on-r slope
  9.06** — the controller steps with the reference, matching the banked cl4
  signature (9.7). y verdict NOT TRACKING with 5 transients detected = the
  CORRECT saline null (toy model, no plant in the bath).
- Watch item: timeouts 169/1300 (13%), freshTicks 1261/1300 (**97.0%**) —
  above the 5–11% baseline. Known MATLAB stall behavior (localhostOutputAge
  max 168 ms); cpp arms immune. Baseline row updated in the 08-31 runbook;
  escalate only if freshTicks collapses.

## 4. Decisions & state

- **GO for Monday 2026-08-31.** `RIG_DAY_2026-08-31.md` = re-dated runbook
  (PHASE −1 replaced by the resolution + gate summary; day paths
  `day_2026-08-31`, templates `Acute_2026-08-31`, seed 20260827 unchanged).
- `--feature-trim` OFF. 2x rate locked out (610 Hz path). `-FeatureWindow 6`.
- Runbook Phase-3 delivery-audit command corrected: the script takes
  `--capture capture_rig_run<label>.csv --amps ...` (the old `--design` form
  was never its interface).
- Artifacts today: `card_probe.csv`, `capture_rig_runrndval.csv` +
  `rig_runrndval.csv` + `loop_runrndval.log`, `capture_mpc_20260827_184338.csv`,
  `rig_runmpccheck.csv` + `loop_runmpccheck.log`,
  `tracking_mpccheck_20260827.{json,png}`; blocks `LD-260827-182650`,
  `LD-260827-184414`.
- Weekly deck (2026-08-28): built from these artifacts —
  `scripts/build_weekly_deck_2026-08-27.py`.
