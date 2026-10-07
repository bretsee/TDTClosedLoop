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

| # | When the surgeon says | Run | PASS line to look for |
|---|---|---|---|
| 1 | "cortical gate" (after 40 thwacks, recording stopped) | `& $py rig\placement_gate.py --mode cortical --newest` | `CORTICAL GATE: GO` (else read the `ADJUST:` line aloud) |
| 2 | "thalamic gate" | A: `.\cpp_controller.exe --mode openloop --play design_rungate.csv --output-count 8 --capture capture_rig_rungate1.csv`  B: `.\rig\2_loop.ps1 -Run gate1 -RZ2 10.1.0.100 -InputChannels 64 -TimeoutMs 10 -Ticks 26277 -TickFrames 6` → after Summary: `& $py rig\placement_gate.py --mode thalamic --newest --min-amp 13` | `THALAMIC GATE: GO` + the per-pair table (read "responsive N, eff rank R") |
| 3 | "quiet" (60 s recording done) | `& $py rig\ingest_block.py --label quiet` then `& $py rig\analyze_quiet_capture.py --block <printed block>` | blacklist list + baseline volts — write both on the whiteboard |
| 4 | "thwack <SITE>" (each battery block) | `& $py rig\ingest_block.py --label "<SITE> thwack" --mode thwack` and `& $py C:\Users\brets\Documents\Repositories\NNController\scripts\touch\extract_nthw_templates.py --block <blk> --site <SITE> --day 2026-10-08 --min-pulse-ms 50 --n-channels 64` | gallery line with peak µV / best ch / split-half ≥ 0.8 |
| 5 | "burst probe" | A: `--play design_runburst1.csv --capture capture_rig_runburst1.csv`  B: `-Run burst1 -Ticks 95586` (rest as row 2) → `& $py rig\check_impulse_delivery.py --block <blk> --capture capture_rig_runburst1.csv --amps 6 9 13 18 25 --pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"` then `& $py rig\placement_gate.py --mode thalamic --newest --min-amp 13 --blacklist <list>` | `DELIVERY VERIFIED`; gate table with knees |
| 6 | "gap scan" | A: `--play design_rungap1.csv --capture capture_rig_rungap1.csv`  B: `-Run gap1 -Ticks 13098` | `Summary:` with `droppedControlTicks=0` |
| 7 | "duty ID, pairs X,Y,Z" | the one-line pandas command in RIG_DAY Phase 4 with `keep={X,Y,Z}` → A: `--play design_rundutyid.csv --capture capture_rig_rundutyid.csv`  B: `-Run dutyid -Ticks 30100` → `& $py rig\check_y_liveness.py --capture capture_rig_rundutyid.csv --baseline <V>` → the `matlab -batch` fit line → `& $py rig\check_mimo_rank.py --model plant_duty.lti` | `y-liveness: LIVE`; fit prints per-output corr; `check_mimo_rank` PASS |
| 8 | "build refs" | `build_interleaved_run.py` line from RIG_DAY Phase 5 | `wrote 3 run(s)` |
| 9 | "arm MPC rN" / "arm Choi rN" | RIG_DAY Phase 6a lines with rN; **within the first minute** run `& $py rig\check_y_liveness.py --capture day_2026-10-08\capture_<arm>_mixrN.csv --baseline <V>` | B prints `policy=fresh` by tick ~100; `y-liveness: LIVE`; after Summary: `tracking_metrics` prints a verdict + r0 |
| 10 | "stim zero" (end of day) | `& $py rig\send_envelope.py --rz2 10.1.0.100 --shape const --umax 0 --secs 2 --count 8 --yes` | `26 packets ACKed` style line |

Red flags — say them immediately:
- `y-liveness: DEAD` → amplifier/PZ2 is off. Stop the run.
- B never prints `policy=fresh` by tick ~100 → Ctrl+C in B, restart B, `go` again.
- `Skipping ... to position` in B → Synapse recording was started too early; stop, restart B, start
  recording LAST.
- Any `FAIL` from `check_impulse_delivery` → read the `missed` count and time window aloud (a late
  stim-enable looks like missed probes at the start; that is operator timing, not a fault).
