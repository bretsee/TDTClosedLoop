# Lab notebook — 2026-07-23

**Project:** TDTClosedLoop — 100 Hz closed-loop neural stim MPC
**Session type:** Offline (no hardware). Sim harness only, `--sim-input sine`.
**Objective going in:** resolve the open embedded-vs-localhost controller-path
decision, then prepare tooling for the 2026-07-24 TDT rig session.
**Outcome:** decision resolved in favour of the localhost path. Along the way,
found and fixed a defect that meant the closed loop was **not actually closed**.

---

## Summary of the day

Three findings, in ascending order of importance:

1. The localhost controller path was unusable because of the Windows timer
   quantum — in two independent places, only one of which we had suspected.
   Fixed; the path now works and is the better of the two architectures.
2. Neither the System Identification Toolbox nor the Control System Toolbox is
   installed on this machine. Both planned system-ID work and part of the
   existing controller silently depended on them.
3. **`mpc_test` was running fully open-loop.** The observer gain was silently
   zero, so the MPC never used its measurement at all. Fixed and verified.

Finding 3 is the one that matters. Everything measured before today — including
the previous session's benchmarks — was measured on a controller that ignored its
input. The timing results remain valid (they measure transport and solve time,
not control quality), but no statement about *control behaviour* from before
today should be trusted.

---

## Finding 1 — Localhost path latency: two quantum bugs, not one

### What we believed at the start
From `BENCHMARK_NOTES.md` (2026-07-23, earlier session): the localhost path gave
ideal loop timing (46 µs ticks, 0 dropped) but the MATLAB server's `pause(0.001)`
polling loop was Windows-timer-bound at 15–30 ms round trip, so it only ever
delivered with a relaxed ~50 ms timeout. The hypothesis was that replacing
`pause`-polling with a blocking read would fix it.

### What we found
The hypothesis was half right.

**Bug 1 (receive side, as suspected).** `pause(0.001)` is bounded below by the
~15.6 ms system timer quantum, so the server woke roughly every 15.6 ms
regardless of when data arrived. Replaced with a blocking
`read(u, 1, "uint8")`, which parks in the transport layer and wakes on datagram
arrival.

**That alone changed nothing.** After the blocking-read fix the C++ side still
reported `replies=0, timeouts=499, staleDropped=302` — the server was replying,
but always ≥1 tick late, so every reply arrived stale and was discarded.

Server-side instrumentation (added today) localised it:

| quantity | value |
|---|---|
| `compute` (mpc_test itself) | 0.5–1.0 ms |
| `turnaround` (read-return → write-complete) | **15.5 ms** |
| `gap` (wake-to-wake) | 15.6 ms |

The controller was fast; ~14.7 ms was being spent *after* it ran.

**Bug 2 (send side, not suspected).** `udpport`'s `write()` is *also* quantum
bound. Isolated in a standalone microbenchmark:

| condition | avg | median | p95 | min | max |
|---|---|---|---|---|---|
| `write()` baseline | **15.775 ms** | 15.766 | 16.106 | 0.316 | 34.268 |
| `write()` with a 1 ms MATLAB timer running | **1.379 ms** | 1.187 | 2.322 | 0.520 | 4.054 |

The `min` of 0.316 ms is the tell: the call itself is fast, it just gets parked
until the next timer tick. A single `write()` therefore cost more than the entire
10 ms tick budget.

### The fix
Hold the MATLAB process in the 1 ms scheduling quantum for the server's lifetime
by starting a **no-op `timer` object** (`Period` 0.001, `BusyMode` 'drop'). We
never use its callback; the running timer is what changes the process-wide timer
resolution. Confirmed by the side effect that `pause(0.001)` also drops from
~15.6 ms to 1.0 ms once it is running.

This is the standard `timeBeginPeriod(1)` effect, obtained without a MEX file.
Note that since Windows 10 2004 a timer-resolution request only affects the
requesting process, so the C++ side raising it would *not* have helped MATLAB —
it has to be done inside the MATLAB process.

### Third-order effect: cold-start cost
With both fixes in, the residual timeouts were concentrated in the first few
ticks: `seq=1` cost **62.8 ms** of compute (MATLAB JIT + OSQP problem setup).
Added a warm-up that calls `mpc_test` three times and resets persistent state
*before* the server announces `ready`. Timing-only change; control output is
untouched.

### Result

| stage | server turnaround (avg / median / p95) | C++ usable replies (of 500) | timeouts |
|---|---|---|---|
| original (`pause` poll) | — (15.7 ms round trip) | 0 at 5 ms timeout | 500 |
| + blocking read | 15.774 / 15.513 / 15.838 ms | **0** | 499 |
| + 1 ms timer resolution | 2.478 / 1.893 / 3.462 ms | 451 | 48 |
| + controller warm-up | **2.122 / 1.886 / 3.186 ms** | **476** | 23 |

---

## Finding 2 — Missing toolboxes

`ver` reports only: MATLAB, Signal Processing, DSP System, Communications,
Instrument Control.

**Absent:** System Identification Toolbox (`n4sid`, `iddata`, `compare`) and
Control System Toolbox (`ss`, `c2d`, `place`, `dcgain`, `lsim`, `dlyap`).

Consequences:
- The planned `n4sid` system-ID route is unavailable. Rewrote the fitting
  pipeline to be dependency-free (details below).
- `AllModels(10).sys` is stored as a plain struct rather than an `ss` object —
  which is *why* `mpc_test` has a struct branch in `unpack_model`, and why it has
  been working at all.
- It also caused Finding 3.

---

## Finding 3 — The loop was not closed *(most important)*

### Symptom
In the benchmark server logs, the command output was constant while the input
varied:

```
Reply #200 feature0=242.310211 out0=1.236830
Reply #300 feature0=245.588470 out0=1.236830
Reply #400 feature0=198.655731 out0=1.236830
Reply #500 feature0=224.881638 out0=1.236830
```

### Root cause
`mpc_test.m`, `design_observer_gain`:

```matlab
try
    obsPoles = linspace(0.35, 0.75, n);
    L = place(A.', C.', obsPoles).';
catch
    L = zeros(n, p);        % <-- silently taken, every time
end
```

`place` is Control System Toolbox — not installed (Finding 2). So `L = 0` on
every run, and the state update

```matlab
P.xhat = x_pred + P.L * (yk - y_pred);
```

reduces to `P.xhat = x_pred`. The measurement `yk` was computed, sanitised,
logged — and then multiplied by zero. The MPC was propagating its internal model
open-loop and converging to a fixed command.

Verified directly: `exist('place','file')` → `0`; `place(...)` → `MATLAB:UndefinedFunction`;
resulting `L` → `0`; observer active → `false`.

### Fix
Replaced the silent fallback with a dependency-free **steady-state Kalman gain**
computed by iterating the discrete Riccati recursion to convergence, then formed
the filtering gain `L = Pp*C'*(C*Pp*C' + R)^-1`. `place` is still preferred when
available. The estimator is now checked for stability before being returned, and
a zero gain is only ever produced *loudly*, via `warning`, with explicit text
saying the controller will run open-loop.

### Verification (toy model, A=0.9512, B=0.00975, C=1)

| | before | after |
|---|---|---|
| observer gain `L` | 0 | **0.062008** |
| observer error pole `|(I-LC)A|` | 0.9512 (uncorrected) | 0.892246 (stable) |
| command range over a sinusoidal feature sweep | **0.000000** | **8.309425** |

With a reachable target (`MPC_TARGET = 250`) and the feature swept 130→370, the
command now moves 21.4→29.7 with sensible phase lag. The loop responds to its
measurement.

> **Caveat:** this is verified on the toy first-order model only. Watch closed-loop
> behaviour carefully on first hardware use.

### End-to-end regression through the real C++ loop
Re-ran the full localhost path after the observer fix (`MPC_TARGET = 300`, 500 ticks):

```
Reply #100 feature0=242.820084 out0=7.539483
Reply #200 feature0=227.065567 out0=7.774791
Reply #300 feature0=205.744858 out0=7.420239
Reply #400 feature0=262.549194 out0=7.466720
Reply #500 feature0=236.877548 out0=7.688327
```

The command now tracks the measurement instead of sitting at a constant. This is
the same test that produced the flat `out0=1.236830` above, so it is a direct
before/after on the identical path.

`droppedControlTicks=0`, `totalTick` avg 55.1 µs, server turnaround avg 2.615 ms.

**One number moved the wrong way:** this run showed `timeouts=74` versus 23 in the
pre-fix warm-up run (`freshTicks=462`, `heldTicks=14`, `zeroTicks=24`). Dropped
ticks stayed at 0 and per-packet `compute` stayed ~0.55 ms, so this is run-to-run
variance in the tail rather than the observer costing time — but it has only been
seen across a handful of runs and the spread (23–74 of 500) is wider than is
comfortable. Worth collecting a few repeat runs at the rig rather than treating
either figure as *the* number. Deferred item 5 below (accepting the newest reply
rather than only the exact in-flight sequence) would largely remove this
sensitivity.

---

## Controller-path decision: **localhost**

Both paths re-benchmarked in the same session, identical workload (sine sim,
fs 24414, 16 ch, 500 ticks, `--skip-udp-send`).

| | Embedded MATLAB Engine | Localhost (fixed) |
|---|---|---|
| controller latency avg / max | 1.586 ms / **11.266 ms** | 9.999 ms / 11.968 ms |
| loop `totalTick` avg / max | 1.612 ms / **11.341 ms** | **0.053 ms / 0.660 ms** |
| **dropped control ticks** | **2 / 500** | **0 / 500** |
| ticks commanding zero (fail-safe) | 0 | 24 (startup transient) |
| command lag | none | **1 tick (10 ms), structural** |

**Decision: deploy the localhost path.** The embedded path puts the MATLAB solve
*inside* the tick, so its worst case (11.3 ms today, 9.6 ms in the previous
session) directly becomes the tick's worst case and exceeds the 10 ms budget —
it dropped 2 ticks today versus 1 last time, i.e. it is over budget and the
margin is not reproducible run to run. The localhost path fully decouples the
loop: ticks stay at ~53 µs with zero drops even when the controller occasionally
takes tens of ms, and a late controller degrades to a defined fail-safe instead
of a missed tick.

The cost is a structural one-tick (10 ms) command lag: the C++ loop polls for the
in-flight reply at the *start* of the tick after it sent the request
(`MpcPo8eUdpClosedLoop.cpp:1332-1381`), so 10 ms is the floor, not a symptom of a
slow server. Measured average controller latency of 9999 µs is exactly that floor.
This lag is real and must be modelled — it is why the system-ID fitter defaults to
`inputDelayTicks = 1`.

---

## Rig-day tooling built (all rehearsed against the sim harness)

### `make_excitation.m` (new)
Open-loop excitation design: `prbs` (LFSR m-sequence), `multilevel`, `steps`,
`chirp`. Deliberately **zero toolbox dependencies** — this runs during
acquisition, where a missing-toolbox error costs a session.

Verified: balanced m-sequence (mean 20.04 over a 0–40 range), channel
decorrelation |r| = 0.071 across 2 channels, all four kinds produce the requested
range.

### `matlab_controller_server.m` — new `openloop` mode
Ignores the measurement, emits the designed excitation, and logs one row per tick
of `[tick, seq, t_ms, u1..uN, y1..yM]`. Because it sits at the control tick, the
capture is automatically aligned to the 100 Hz rate and already in the MAV
feature space the MPC uses. Sequence is generated up front so no allocation or
RNG work happens inside a tick.

Also switched configuration to an options struct (positional calls still work).

Rehearsed end-to-end: 400 ticks, 0 dropped, 386/400 replies, capture written with
16 u-columns and 16 y-columns, server turnaround avg 1.301 ms.

### `fit_sysid_from_capture.m` (new)
Because `n4sid` is unavailable, identification is **ARX by linear least squares**,
realised in observable canonical form, validated by direct free-run simulation and
NRMSE. No toolboxes.

Four things it does deliberately, each guarding a way to get a wrong answer:
1. **Causal alignment** — undoes the one-tick command lag. Off-by-one here
   invents a feedthrough term and flatters the fit.
2. **Detrending** — MAV features are large and positive; un-centred data makes the
   model spend its range on the mean.
3. **Held-out validation** — order chosen on unseen data, not training fit.
4. **Excitation quality check** — reports input movement and peak |cross-corr|,
   and warns when the stim did not measurably move the output.

**Validated against synthetic ground truth** (known 2-state plant, poles 0.9/0.7,
PRBS input, measurement noise, one-tick lag applied):

| | true | recovered |
|---|---|---|
| dominant poles | 0.9000, 0.7000 | 0.9123, 0.6928 |
| DC gain | 1.246667 | 1.274999 (2.27 % error) |
| validation fit | — | 93.75 % |

**Negative control** — run on the sim capture where `u` has no causal effect on
`y`: peak |corr| 0.013, the warning fired, and validation fit was **-0.01 %**
(i.e. no better than predicting the mean). It does not manufacture a model from
noise.

Note it selected order 5 for a true order-2 plant: ARX is an equation-error
method and buys apparent fit with extra states. Added a `parsimonyTolerance`
option (default 1.0 pp) that takes the smallest order within tolerance of the
best. **Do not read the chosen order as the physical state count.**

### `RIG_DAY_PROTOCOL.md` (new)
Step-by-step runbook for tomorrow.

---

## Environment gotchas discovered (cost real time today)

- **Do not launch MATLAB with `Start-Process` or `Start-Job`.** Both silently
  produce nothing. `bin\matlab.exe` is a launcher that spawns the real process and
  exits immediately, so redirected handles capture nothing;
  `bin\win64\MATLAB.exe` produces no output at all. Run `matlab.exe -batch` in the
  foreground of its own terminal.
- **MATLAB `-batch` writes errors to stderr.** Without `2>&1` a failing server is
  indistinguishable from a silent one — this cost the first three attempts.
- **The `.exe` needs the MATLAB runtime on `PATH`** even for the localhost path.
  Without it: exit code 53, no output.
- The udpport read-timeout warning ID is
  `instrument:interface:udpport:ReadWarning` (not the `transportlib:` name I
  first guessed).

---

## Files changed

| file | status | change |
|---|---|---|
| `matlab_controller_server.m` | modified | blocking read; 1 ms timer resolution; controller warm-up; vectorized big-endian pack/unpack; `openloop` mode + (u,y) capture logging; per-packet timing log; options-struct config; idle auto-stop for bounded runs |
| `mpc_test.m` | modified | `design_observer_gain`: toolbox-free steady-state Kalman gain; stability check; loud failure instead of silent `L = 0` |
| `make_excitation.m` | **new** | excitation design, dependency-free |
| `fit_sysid_from_capture.m` | **new** | ARX least-squares system ID + validation, dependency-free |
| `RIG_DAY_PROTOCOL.md` | **new** | rig runbook |
| `LAB_NOTEBOOK_2026-07-23.md` | **new** | this file |
| `BENCHMARK_NOTES.md` | updated | new numbers + decision |
| `NEXT_STEPS.md` | updated | current state |

Wire-format change was verified byte-identical to the original per-element loop
implementation before use (`pack`, `unpack`, and round-trip, across several
sequence numbers and vector lengths).

---

## Open questions for the rig

1. **Does stim actually move the MAV feature?** Everything downstream depends on
   it. The `|corr| u -> y` line in the fitter is the go/no-go.
2. **Which feature channel to control.** `feature_map` in `mpc_test.m` currently
   takes the first `p` entries of the feature vector. If the identified channel
   is not channel 1, this must be changed or the MPC will control a channel it
   has no model of.
3. **Does the observer behave on a real model?** Verified only on the toy
   first-order plant. The `qScale = 1e-2` process/measurement noise ratio is a
   guess and is the knob for observer aggressiveness.
4. **Freshness thresholds are too loose.** `LOCALHOST_FRESH_OUTPUT_US = 100 ms`
   and `LOCALHOST_MAX_HOLD_OUTPUT_US = 250 ms`
   (`MpcPo8eUdpClosedLoop.cpp:1147-1148`) treat a command up to 10 ticks stale as
   "fresh". Should be ~20 ms / ~50 ms. Deliberately **not** changed today to avoid
   a C++ rebuild immediately before hardware day.
5. **Reduce the structural one-tick lag?** The C++ side discards any reply whose
   sequence is not the exact in-flight one (`staleDropped`). Accepting the
   *newest* reply instead would recover most of the timeouts and cut dropout.
   C++ change, needs a rebuild.
6. **`umax = 40` is a physical stim limit, not an arbitrary clamp.** *(Corrected
   2026-07-24.)* The MPC command is the **pulse-amplitude envelope** — one stim
   pulse amplitude per 100 Hz control point, exactly the signal recorded in the
   acute datasets' stimblock CSVs (16 channels × time, values ±{7,12,20,30,40}).
   So `[0, 40]` (or signed ±40) enforces the real charge/compliance ceiling of
   the stimulator, and clamping to it is physically meaningful, not a placeholder.
   This makes the excitation `uMax` genuinely safety-relevant: set it from
   known-safe limits for the preparation, and note it is the *amplitude* of each
   pulse in the envelope, not a continuous current.
