# Helper card — engineer lane, acute #3 (2026-10-08)

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
Synapse recording, then run the check lines.

**Since 2026-10-09 every row's exact lines come from the runcard:**
`& $py rig\rig_runcard.py --phase <gate|quiet|thwack|burst|gap|dutyid|fit|refs|arm|rsweep|drift> --day <day> [--resp 1,3,4,6 --ctrl 34,40 --baseline <V>]`
prints terminal-A / terminal-B / check lines with every blank filled in (and writes them to
`day_<day>\runcard_<phase>.txt`). B lines take `-Design <csv>` (tick count comes from the design) and
`-Capture <csv> -Baseline <V>` (opens the y-liveness watch window when you type `go`). After every
`Summary:` the first check line is `run_audit.py` → **one line starting `AUDIT <run>: PASS`** (read
`WARN`/`FAIL` lines aloud).

| # | When the surgeon says | Run | PASS line to look for |
|---|---|---|---|
| 1 | "cortical gate" (after 40 thwacks, recording stopped) | `& $py rig\placement_gate.py --mode cortical --newest` | `CORTICAL GATE: GO` (else read the `ADJUST:` line aloud) |
| 2 | "thalamic gate" | `rig_runcard.py --phase gate --depth <d>` → A: `.\cpp_controller.exe --mode openloop --play design_rungate.csv --output-count 8 --capture capture_rig_rungate<d>.csv`  B: `.\rig\2_loop.ps1 -RZ2 10.1.0.100 -InputChannels 64 -TimeoutMs 10 -TickFrames 6 -Run gate<d> -Design design_rungate.csv -Capture capture_rig_rungate<d>.csv` → after Summary: `run_audit`, then `& $py rig\placement_gate.py --mode thalamic --newest --min-amp 13` | `AUDIT gate<d>: PASS`; `THALAMIC GATE: GO` + the per-pair table (read "responsive N, eff rank R") |
| 3 | "quiet" (60 s recording done) | `& $py rig\ingest_block.py --label quiet` (runs analyze_quiet_capture itself; prints the JSON path) | blacklist list + baseline volts — write both on the whiteboard |
| 4 | "thwack <SITE>" (each battery block) | `& $py rig\ingest_block.py --label "<SITE> thwack" --mode thwack` and `& $py C:\Users\brets\Documents\Repositories\NNController\scripts\touch\extract_nthw_templates.py --block <blk> --site <SITE> --day 2026-10-08 --min-pulse-ms 50 --n-channels 64` | gallery line with peak µV / best ch / split-half ≥ 0.8 |
| 5 | "burst probe" | `rig_runcard.py --phase burst` → A: `--play design_runburst1.csv --capture capture_rig_runburst1.csv`  B: `-Run burst1 -Design design_runburst1.csv -Capture capture_rig_runburst1.csv` (rest as row 2) → `run_audit`, `& $py rig\check_impulse_delivery.py --block <blk> --capture capture_rig_runburst1.csv --amps 6 9 13 18 25 --pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5" --design-meta design_runburst1_meta.json`, `& $py rig\fit_burst_plant.py --capture capture_rig_runburst1.csv --meta design_runburst1_meta.json --json day_2026-10-08\burst_plant.json --png day_2026-10-08\burst_plant.png`, then `placement_gate --mode thalamic --newest --min-amp 13 --blacklist <list>` | `AUDIT burst1: PASS`; `DELIVERY VERIFIED`; efficacy line `B=1 1.00 B=3 … B=10 …` + eff-rank per B; gate table with knees |
| 6 | "gap scan" | `rig_runcard.py --phase gap` → A: `--play design_rungap1.csv --capture capture_rig_rungap1.csv`  B: `-Run gap1 -Design design_rungap1.csv -Capture capture_rig_rungap1.csv` → `run_audit`, `& $py rig\fit_burst_plant.py --capture capture_rig_rungap1.csv --meta design_rungap1_meta.json` | `AUDIT gap1: PASS`; `OPERATING GAP (first ratio >= 0.80): N ticks` — write N on the whiteboard |
| 7 | "duty ID, pairs X,Y,Z" | `& $py rig\rig_runcard.py --phase dutyid --day 2026-10-08 --resp X,Y,Z --baseline <V>` (writes + validates `design_rundutyid.csv`) → its A/B lines → `run_audit` → `& $py rig\rig_runcard.py --phase fit --day 2026-10-08 --resp X,Y,Z --ctrl <c1>,<c2>` → its `matlab -batch` line, `check_dead_time`, `check_mimo_rank`, the cpp observer line | `DESIGN OK`; `AUDIT dutyid: PASS`; `VERDICT: OK: centred`; `check_mimo_rank` PASS; `Observer: ACTIVE` |
| 8 | "build refs" | `rig_runcard.py --phase refs --resp … --ctrl … --baseline <V>` → its `build_interleaved_run.py` line, then its `closed_loop_sim.py` line | `wrote 3 run(s)`; `Command varies` |
| 9 | "arm MPC rN" / "arm Choi rN" | `rig_runcard.py --phase arm --arm mpc|choi --run N --resp … --ctrl … --baseline <V>` → A line, B line (the y-liveness window opens itself at `go`), then `run_audit`, `tracking_metrics`, `ingest_block` | liveness window says `LIVE`; `AUDIT <arm>_mixrN: PASS`; `tracking_metrics` prints a verdict + r0 |
| 10 | "R sweep" (Tier C) | `rig_runcard.py --phase rsweep --run N --resp … --ctrl …` → `build_r_schedule.py` line, A line (has `--r-schedule`), B line, `run_audit`, `analyze_r_sweep.py` | `R SCHEDULE OK`; `AUDIT mpc_rsweep_rN: PASS`; per-block table with `rW0 ok` in every row |
| 11 | "stim zero" (end of day) | `& $py rig\send_envelope.py --rz2 10.1.0.100 --shape const --umax 0 --secs 2 --count 8 --yes` | `26 packets ACKed` style line |

Red flags — say them immediately:
- the liveness window says `DEAD` (or `run_audit` says `y=DEAD`) → amplifier/PZ2 is off. Stop the run.
- `AUDIT …: FAIL` → read every `FAIL:` line aloud; the run is suspect until the surgeon says otherwise.
- B never prints `policy=fresh` by tick ~100 → Ctrl+C in B, restart B, `go` again.
- `Skipping ... to position` in B → Synapse recording was started too early; stop, restart B, start
  recording LAST.
- Any `FAIL` from `check_impulse_delivery` → read the `missed` count and time window aloud (a late
  stim-enable looks like missed probes at the start; that is operator timing, not a fault).
