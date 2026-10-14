# Helper card — engineer lane, acute #3 (2026-10-14)

You are running the computer side so the surgeon can stay sterile. Every step is: run the lines,
look for ONE pass line, say "PASS" or read the FAIL line aloud. Terminal = PowerShell in
`C:\Users\brets\Documents\Repositories\TDTClosedLoop`. First thing in every new terminal:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
$py = "C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\.venv\Scripts\python.exe"
.\rig\0_preflight.ps1 -InputChannels 64        # prints PASS: droppedControlTicks=0
```
Two terminals are used for every stim run: **A** = controller server, **B** = loop. Order is always:
start A, start B and wait for the `go` prompt, **then** start the Synapse recording, **then** type `go`
and turn the Synapse stim-enable ON right away. When B prints `Summary:` the run is over: stop the
Synapse recording, do the flash-drive round-trip (copy the new block folder from the Synapse tank onto
the drive, carry it over, copy it into `C:\Users\brets\Desktop\Data\Acute_101426\`; 2-3 min), then run
the check lines; they find the newest block by themselves and print its name on the first line — check
it is the recording you just stopped. **The surgeon is mostly solo: only the gate blocks (rows 1-2) and
the quiet block (row 3) are carried over right away; every other block is batched to the WRAP, and
the lines marked `batched` in the runbook run then.**
**Nothing else runs on this PC while a run is going** (no analysis, no browser).

**Every row's exact lines come from the runcard:**
`& $py rig\rig_runcard.py --phase <gate|quiet|thwack|burst|gap|dutyid|fit|refs|arm|rsweep|drift> --day 2026-10-14 [--resp 1,3,4,6 --ctrl 34,40 --baseline <V> --blacklist 33,36 --block <dir>]`
prints terminal-A / terminal-B / check lines with every blank filled in (and writes them to
`day_2026-10-14\runcard_<phase>.txt`). After every `Summary:` the first check line is `run_audit.py` →
**one line starting `AUDIT <run>: PASS`** (read `WARN`/`FAIL` lines aloud).

| # | When the surgeon says | Run | PASS line to look for |
|---|---|---|---|
| 0 | "set up" (before induction) | one window: `.\rig\physio_timer.ps1 -Day 2026-10-14 -EveryMin 15` (every beep: read heart rate + body temperature off the PhysioSuite, type e.g. `HR 310 T 37.2`); the Phase-0 lines of `rig_runcard --phase phase0`; flash drive empty and at the Synapse PC (runbook 0c) | `net_diag` PASS; `find_rz2` one device; selftest `8/8`; preflight PASS |
| 1 | "cortical gate" (after 40 thwacks, recording stopped) | `& $py rig\placement_gate.py --mode cortical --newest` | `CORTICAL GATE: GO` (else read the `ADJUST:` line aloud) |
| 2 | "thalamic gate" | `rig_runcard --phase gate --depth <d>` → A, B (`-Run gate<d> -Design design_rungate.csv -Capture capture_rig_rungate<d>.csv`) → after Summary: `run_audit`, `placement_gate --mode thalamic --newest --min-amp 13`, `check_impulse_delivery … --design-meta design_rungate_meta.json`, `check_dead_time … --y-channel <best ch>` | `AUDIT gate<d>: PASS`; `THALAMIC GATE: GO` + the per-pair table (read "responsive N, eff rank R, best pair P, best ch C"); `DELIVERY VERIFIED`; dead-time `recommended inputDelayTicks = N` |
| 3 | "quiet" (60 s recording done) | `& $py rig\ingest_block.py --label quiet --day 2026-10-14` | blacklist list + baseline volts — write both on the whiteboard |
| 4 | "thwack <SITE>" (each battery block) | `rig_runcard --phase thwack --site <SITE> --block <blk>` → its two lines | gallery line with peak µV / best ch / split-half ≥ 0.8 |
| 5 | "burst probe" | `rig_runcard --phase burst --blacklist <list> --baseline <V>` → A, B → `run_audit`, `check_impulse_delivery … --design-meta design_runburst1_meta.json`, `fit_burst_plant`, `placement_gate` | `AUDIT burst1: PASS`; `DELIVERY VERIFIED`; efficacy line `B=1 1.00 B=3 … B=10 …` + eff-rank per B; gate table with knees |
| 6 | "gap scan, pair P" | `rig_runcard --phase gap --gap-pair P --baseline <V>` (prints `DESIGN OK` first) → A, B → `run_audit`, `fit_burst_plant` | `DESIGN OK`; `AUDIT gap1: PASS`; `OPERATING GAP (first ratio >= 0.80): N ticks` — write N on the whiteboard |
| 7 | "duty ID, pairs X,Y,Z, gap N" | `rig_runcard --phase dutyid --resp X,Y,Z --gap-ticks N --baseline <V>` (writes + validates the design) → A, B → `run_audit` → `rig_runcard --phase fit --resp X,Y,Z --ctrl <c1>,<c2> --delay-ticks <onset-1>` → its `matlab -batch` line, `check_dead_time`, `check_mimo_rank`, the cpp observer line | `DESIGN OK`; `AUDIT dutyid: PASS`; `VERDICT: OK: centred`; `check_mimo_rank` PASS; `Observer: ACTIVE` |
| 8 | "build refs" | `rig_runcard --phase refs --resp … --ctrl … --baseline <V>` → its `build_interleaved_run.py` line, then its `closed_loop_sim.py` line | `wrote 3 run(s)`; `Command varies` |
| 9 | "arm MPC rN" / "arm Choi rN" (add `--suffix _late` for 6g, `--suffix _umin --umin <knee>` for 6c) | `rig_runcard --phase arm --arm mpc|choi --run N …` → A line, B line (the y-liveness window opens itself at `go` and BEEPS on DEAD), then `run_audit`, `tracking_metrics`, `ingest_block` | liveness window says `LIVE`; `AUDIT <arm>_mixrN: PASS`; `tracking_metrics` prints a verdict + r0 |
| 10 | "R sweep" (Tier C) | the `build_interleaved_run … --runs 1 --events 120 --total-ticks 26600 --run-offset 3` line from the runbook, then `rig_runcard --phase rsweep --run 4 …` → `build_r_schedule`, A (has `--r-schedule`), B, `run_audit`, `analyze_r_sweep` | `R SCHEDULE OK`; `AUDIT mpc_rsweep_r4: PASS`; per-block table with `rW0 ok` in every row |
| 11 | "stim zero" (end of day, or after ANY crash) | `.\rig\stim_zero.ps1` | `stim zero sent (8 words, 2 s of zeros)` |
| 12 | "archive" | `.\rig\archive_day.ps1 -Day 2026-10-14` | `DONE: …zip (N MB)` — then copy zip + blocks to the external drive |

Red flags — say them immediately:

- the liveness window BEEPS or says `DEAD` (or `run_audit` says `y=DEAD`) → amplifier/PZ2 is off. Stop the run.
- `AUDIT …: FAIL` → read every `FAIL:` line aloud; B will refuse the next run until someone types `override`.
- any crash/abort of a stim run → `.\rig\stim_zero.ps1` BEFORE anything else.
- B never prints `policy=fresh` by tick ~100 → Ctrl+C in B, restart B, `go` again.
- `Skipping ... to position` in B → Synapse recording was started too early; stop, restart B, start recording LAST.
- A gate/ingest line prints `newest block:` with a time that is NOT the recording you just stopped →
  the copy has not landed (recording still open? copied too early?); say so, it graded a STALE block.
- Any `FAIL` from `check_impulse_delivery` → read the `missed` count and time window aloud (a late
  stim-enable looks like missed probes at the start; that is operator timing, not a fault).
- The physio timer beeped (every 15 min) → read heart rate + body temperature off the PhysioSuite to the
  surgeon, type them (e.g. `HR 310 T 37.2`, or `-`) so the log keeps time.
