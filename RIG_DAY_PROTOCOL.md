# Rig day protocol — open-loop capture and system ID

Written 2026-07-23 for the TDT session on 2026-07-24. Companion to
`LAB_NOTEBOOK_2026-07-23.md` (what changed and why) — this file is the runbook.

Everything below has been rehearsed end-to-end against the sim harness. What has
**not** been exercised is real PO8e acquisition and real stim delivery.

---

## 0. Pre-flight (every fresh shell)

```powershell
cd "C:\Users\brets\Documents\Repositories\TDTClosedLoop"
$mr = "C:\Program Files\MATLAB\R2025b"
$env:PATH = "$mr\runtime\win64;$mr\bin\win64;$mr\extern\bin\win64;$mr\sys\os\win64;$env:PATH"
```

The `$env:PATH` line is **not optional** for the `.exe` — without it the loader
fails with exit code 53 and prints nothing at all.

Two gotchas found on 2026-07-23:

- **Do not launch MATLAB with `Start-Process`.** `bin\matlab.exe` is a launcher
  that spawns the real process and exits immediately, so redirection captures
  nothing and the server appears to die silently. Call `matlab.exe` directly and
  background the whole command instead (see Step 2). `bin\win64\MATLAB.exe`
  produces no output at all — do not use it.
- MATLAB `-batch` sends errors to **stderr**. Always redirect `2>&1`, or a
  failing server looks like an empty log file.

---

## 1. Sanity: is the loop still healthy? (no hardware, ~1 min)

```powershell
.\MpcPo8eUdpClosedLoop.exe 127.0.0.1 . 16 --controller constant --constant-output 5 `
  --sim-input sine --sim-fs 24414 --sim-channels 16 --skip-udp-send `
  --max-control-ticks 300 --validate-log sim_smoke.csv
```
Expect `droppedControlTicks=0`.

---

## 2. Open-loop capture for system ID (the main event)

This is what the whole day is for: drive a designed stim sequence, record the
response, and fit a real plant model to replace the toy first-order stand-in.

### 2a. Choose the excitation — read this before running

`make_excitation` writes commands in the same engineering units the MPC uses,
clamped to `[uMin, uMax]`. `mpc_test` clamps to `[0, 40]`, so 40 is the value the
controller believes is its ceiling.

> **Start well below the ceiling.** Set `uMax` to a stim amplitude already known
> to be safe for this preparation, and do a short run before a long one. Nothing
> in this code knows anything about tissue safety or compliance limits.

| kind | when to use | notes |
|---|---|---|
| `prbs` | **default first run** | two-level m-sequence, flat spectrum, best SNR per unit time |
| `multilevel` | if you suspect amplitude nonlinearity | visits interior amplitudes |
| `steps` | to eyeball DC gain and settling by hand | poor spectral coverage alone |
| `chirp` | to see bandwidth directly | |

`clockTicks` sets how many 10 ms ticks each value is held. **5 is the default and
a good starting point** (energy roughly 0.04–10 Hz). Do not use `clockTicks = 1`:
that puts nearly all the energy above the plant bandwidth and identifies noise.

Record length: 60 s (`maxPackets = 6000`) is a reasonable first capture. Longer
is better for SNR; the fit uses the first 70 % to train and the last 30 % to
validate.

### 2b. Start the capture server

**Open a second PowerShell terminal for the server and leave it in the
foreground.** Neither `Start-Process` nor `Start-Job` reliably backgrounds MATLAB
here (both were tried on 2026-07-23 and both silently produced nothing) — and at
the rig you want the server's output visible anyway.

In terminal 2:
```powershell
cd "C:\Users\brets\Documents\Repositories\TDTClosedLoop"
& "C:\Program Files\MATLAB\R2025b\bin\matlab.exe" -batch @'
cd('C:/Users/brets/Documents/Repositories/TDTClosedLoop');
cfg = struct('mode','openloop','requestPort',31000,'replyPort',31001, ...
             'outputCount',16,'maxPackets',6000, ...
             'captureFile','capture_rig_run1.csv','logFile','server_lat_run1.csv');
cfg.excitation = struct('kind','prbs','clockTicks',5,'uMin',0,'uMax',10);
matlab_controller_server(cfg)
'@
```
Wait until it prints `ready` before continuing. It prints the excitation summary
(kind, ticks, actual u range) first — **check that the printed u range is what you
intended before any stim is delivered.**

MATLAB takes ~30 s to start. It then stops on its own 1 s after the loop ends.

### 2c. Run the loop against real hardware

Drop `--sim-input` (that flag is what bypasses the PO8e card) and drop
`--skip-udp-send` so stim actually goes to the RZ2:

```powershell
.\MpcPo8eUdpClosedLoop.exe <RZ2_IP> "C:/Users/brets/Documents/Repositories/TDTClosedLoop" 16 `
  --controller localhost --localhost-timeout-ms 5 `
  --max-control-ticks 6000 --validate-log rig_run1.csv
```

The server stops on its own 1 s after the loop finishes and writes
`capture_rig_run1.csv`.

### 2d. Check the capture before tearing anything down

```powershell
Get-Content .\matlab_server_run1.log -Tail 5
```
Want to see: `Server turnaround ... avg ~2 ms`, and `Wrote 6000 capture rows`.
From the `.exe`: `droppedControlTicks=0` and `timeouts` in the low tens at most.

**Do a second capture with a different `seed` or `kind` before moving on.** A
model fitted on one record and validated on an independent record is worth far
more than one fitted on 70 % of a single record.

---

## 3. Fit the model

```powershell
& "$mr\bin\matlab.exe" -batch "cd('C:/Users/brets/Documents/Repositories/TDTClosedLoop'); r = fit_sysid_from_capture('capture_rig_run1.csv', struct('useOutputs',1)); disp(r)"
```

Read the output in this order:

1. **Excitation check.** `|corr| u -> y` is the go/no-go number. Below ~0.1 and
   the stim did not measurably move the feature — fix the preparation, the
   channel selection, or the amplitude before fitting anything. A model fitted
   here will look confident and mean nothing.
2. **Order sweep table.** `valFit%` is on held-out data. If it does not rise
   meaningfully above ~0 there is no identifiable linear dynamic.
3. **Chosen order.** ARX is an equation-error method and buys apparent fit with
   extra states; `parsimonyTolerance` (default 1.0 pp) takes the smallest order
   that is nearly as good. On a synthetic order-2 plant this picks order 4–5, so
   do not read the chosen order as "the plant has N states".
4. **Model summary.** Sanity-check the time constant against what you know of
   the evoked response. A 5 ms or 5 s time constant means something is wrong.

`useOutputs` selects **one** feature channel at a time — run it once per channel
of interest. Then commit the one you want:

```matlab
r = fit_sysid_from_capture('capture_rig_run1.csv', struct('useOutputs',1,'save',true));
```
This backs up `AllModels.mat` first and writes the model as a plain struct into
`AllModels(10).sys`.

**Then set `feature_map` in `mpc_test.m`.** It currently takes the first `p`
entries of the feature vector as the measurement. If the channel you identified
is not channel 1, this is where you say so — otherwise the MPC controls a
different channel than the one you modelled.

---

## 4. Closed-loop test with the new model

```powershell
mpc_test([])   # in MATLAB: force a reload of AllModels
```

Then run the loop with `--controller localhost` and a server in `mpc` mode. Again
in terminal 2, foreground (`maxPackets = 0` means it runs until you Ctrl+C):

```powershell
& "C:\Program Files\MATLAB\R2025b\bin\matlab.exe" -batch "cd('C:/Users/brets/Documents/Repositories/TDTClosedLoop'); matlab_controller_server('mpc',31000,31001,16,0,0,'')"
```

Set the target before or during the run:
```matlab
MPC_TARGET = <desired feature value>;   % base workspace; get_reference reads it
```

### Watch for
- `out0` **changing with** `feature0` in the server log. If the command converges
  to a constant while the feature moves, the loop is open somewhere.
- `zeroTicks` in the `.exe` summary — every one is a tick that commanded zero
  stim because no fresh reply arrived.
- Saturation at 0 or 40. If `MPC_TARGET` is unreachable the command pins at a
  bound and the loop tells you nothing.

---

## 5. Known limitations to keep in mind

- **One-tick (10 ms) command lag is structural on the localhost path.** The C++
  loop polls for the in-flight reply at the start of the tick *after* it sent the
  request, so the command applied at tick k was computed from the features of
  tick k-1. This is why the capture fitter uses `inputDelayTicks = 1`. The
  embedded path has no such lag but drops ticks (see the notebook).
- **The freshness thresholds are loose.** `LOCALHOST_FRESH_OUTPUT_US = 100 ms`
  and `LOCALHOST_MAX_HOLD_OUTPUT_US = 250 ms`
  (`MpcPo8eUdpClosedLoop.cpp:1147-1148`) mean a 100 ms-old command still counts
  as "fresh" in a 10 ms loop — up to 10 ticks stale. Worth tightening to ~20 ms /
  ~50 ms, but that needs a C++ rebuild, so it was left alone before hardware day.
- **Startup transient.** Expect ~15–25 ticks of zero output at the start of a
  localhost run while MATLAB warms. Harmless (zero output = no stim), but do not
  start analysis at tick 1 — the fitter discards 50 ticks by default.
- **The observer gain fix is new and has only been tested on the toy model.**
  See the notebook. Watch closed-loop behaviour carefully the first time.
