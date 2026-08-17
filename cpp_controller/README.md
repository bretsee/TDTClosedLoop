# Native controller server — the backup control path

A drop-in replacement for `matlab_controller_server.m`. Same UDP ports, same
big-endian wire protocol, same capture CSV format, so `MpcPo8eUdpClosedLoop.exe`
runs against it **unchanged and unrebuilt** with `--controller localhost`.

```powershell
build_cpp_controller.bat
cpp_controller.exe --selftest          # 12 offline checks, no hardware
```

## Why it exists

The primary path depends on MATLAB, which on this machine has no Control System
Toolbox and no System Identification Toolbox, needs a licence, takes ~30 s to
start, and requires a Windows timer-quantum workaround (a running no-op `timer`
object) to hit its latency target. Every one of those is a way to lose a rig day.

This binary has none of them. It depends only on the C++ toolchain already
required to build the acquisition loop — **no CMake, no Eigen, no OSQP, no
LibTorch**. It also happens to be much faster:

| | MATLAB server | native server |
|---|---|---|
| controller round-trip | ~1.4 ms mean, 15.8 ms without the timer fix | **0.019 ms mean** |
| startup | ~30 s | immediate |
| external dependencies | MATLAB + OSQP | none |

The point is not the speed. It is that the backup path removes the structural
one-tick (10 ms) command lag as a *future* option: because it is native, it can
eventually be linked into the acquisition loop directly instead of going over a
socket. Today it deliberately stays a separate process so the benchmarked binary
does not change.

## Modes

```powershell
# transport check -- constant output
cpp_controller.exe --mode constant --constant-output 5

# open-loop capture for system ID (replaces rig\1_server.ps1's MATLAB server)
cpp_controller.exe --mode openloop --max-packets 3000 --umax 30 ^
                   --exc-kind prbs --exc-channels 3 --capture capture_cpp_run1.csv

# model-based control on an identified plant
cpp_controller.exe --mode mpc --model plant.lti --target 250 --feature-map 7

# neural policy
cpp_controller.exe --mode nn --model models\policy.nnw --max-rate 2
```

`export_plant_lti.m` writes `plant.lti` from the same `AllModels(10).sys` that
`mpc_test.m` uses, so both controllers run the identical plant and any behavioural
difference is attributable to the controller.

## Architectures

**`mpc`** — condensed-QP linear MPC, a faithful port of `mpc_test.m`: same
prediction matrices, same hold-last input parameterisation, same steady-state
Kalman observer, same box constraints. Verified against MATLAB on the toy plant —
observer pole **0.892232** here versus **0.892246** in MATLAB.

The QP is solved by accelerated projected gradient rather than OSQP. That is not
a compromise: the constraint set is *only* bounds, so projection is a clamp, and
the method needs no factorisation, no ADMM parameters, and has a hard iteration
cap. **Every iterate is feasible**, so even an early-terminated solve returns a
command that respects the amplitude limits — which is what makes the bounded
worst case safe on hardware.

**`nn`** — feed-forward evaluation of a policy trained in PyTorch (see
`../training/`). Supports `linear`, `mlp`, `residual_mlp`, `gru`, each optionally
with a stacked history window for temporal context. Weights load from a plain-text
`.nnw` file.

LibTorch is deliberately not used. It is a ~2 GB dependency whose allocator and
dispatcher add latency variance that is hard to bound inside a 10 ms tick, and it
would defeat a backup path that must build from nothing. These networks are small
— a 16-64-64-16 MLP is ~5k parameters, microseconds as a plain matmul.

Three guards run after every forward pass: clamp to the amplitude bounds, an
optional slew limit (`--max-rate`), and a non-finite check that falls back to the
previous command. **Use `--max-rate`.** An untrained or mis-normalised network
will otherwise step the stimulation across its full range in a single tick.

## Known behaviour that looks like a bug and is not

**The MPC settles short of its setpoint.** `R` penalises the absolute input, not
its increment, and there is no integral action, so the controller stops at the
cost-optimal trade-off:

```
u* = r_sp · g / (g² + R/Q)        y* = g · u*        g = plant DC gain
```

On a plant with `g = 0.1997` and `Q = R = 1`, a setpoint of 5 gives `y* ≈ 0.19`.
The input penalty dominates because the plant gain is small. **This is inherited
from `mpc_test.m` and applies to the MATLAB controller too.** It matters at the
rig: a default-weighted MPC on a low-gain plant looks like it is barely
responding when it is in fact exactly at its optimum. Lower `--r-weight` (or
raise `--q-weight`) to close the gap — at `--r-weight 1e-4` the same code tracks
a setpoint of 5 to within 0.14%.

## Self-test

`--selftest` runs 12 offline checks covering the wire codec, the QP against
closed-form optima, the Cholesky solve, the observer (including that it *refuses*
an unstable-unobservable model rather than silently returning zero gain), the
closed-loop trade-off above, and the excitation channel mask. Run it after any
change and before any rig day.

For the neural path, `../training/verify_export.py` is the equivalent: it pushes
identical input through PyTorch and this binary over a real socket and compares.
All 7 architecture × history combinations currently match to float32 precision.

`../training/closed_loop_sim.py` closes the loop against a simulated plant and
works against *either* server, which makes it the A/B harness.

## Files

| file | role |
|---|---|
| `main.cpp` | UDP server, argument parsing, self-test |
| `controller.hpp` | the interface every architecture implements |
| `mpc_controller.hpp` | condensed-QP MPC + Kalman observer |
| `nn_controller.hpp` | neural network forward pass |
| `qp_solver.hpp` | box-constrained QP |
| `linalg.hpp` | small dense matrix ops, Cholesky, spectral radius |
| `model_io.hpp` | `.lti` and `.nnw` loaders |
| `excitation.hpp` | open-loop system-ID sequences |
| `wire.hpp` | the UDP protocol |
