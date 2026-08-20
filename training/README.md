# Training neural control policies

Trains in PyTorch on the GPU, exports plain-text weights, and the native
controller evaluates them inside the 10 ms tick. Nothing here is needed at run
time — the rig machine only needs `cpp_controller.exe` and a `.nnw` file.

Interpreter: `PythonIntanAnalysis/.venv/Scripts/python.exe` (torch 2.6 + cu124).

```powershell
$py = "C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\.venv\Scripts\python.exe"
cd C:\Users\brets\Documents\Repositories\TDTClosedLoop\training

& $py train.py --captures ..\capture_rig_run1.csv --arch residual_mlp --history 5
& $py verify_export.py
& $py closed_loop_sim.py --plant ..\plant.lti --target 250 --launch
```

## Pick the framing before the architecture

It matters more than any hyperparameter.

| `--mode` | learns | is it a controller? |
|---|---|---|
| `inverse` *(default)* | features → stim command | **yes** — feed it the response you want, it emits the stimulation |
| `forward` | stim → features | no — a plant model, for simulation or a future nonlinear MPC |

`inverse` is the learned counterpart of the box-constrained inversion in the
biomimetic analysis. `forward` produces something comparable to the ARX fit.

Only an `inverse` model can be dropped into `cpp_controller --mode nn`. Since
2026-08-20 the exporter stamps `# mode: inverse|forward` into the `.nnw`, and
`python rig\check_nnw_mode.py model.nnw` refuses a forward model (exit 1) —
run it before every nn deployment. Files exported earlier carry no stamp and
are warned about rather than passed.

## Architectures

| `--arch` | when |
|---|---|
| `linear` | **the baseline, and run it first** |
| `mlp` | standard feed-forward |
| `residual_mlp` | default — won most per-block comparisons in the acute search |
| `gru` | recurrent; the one to try given the shortfall is temporal |

All support `--history K`, which stacks the last K feature vectors into the
input. That is how temporal context is provided without needing convolutions in
the C++ inference path.

**Train `--arch linear` first and take its number seriously.** The acute
architecture search found the winning networks beat a ridge/linear baseline by
only ~0.7% median RMSE. If a deeper model is not clearly better on held-out data,
deploy the linear one — it is faster, bounded, and far easier to reason about on
a stimulation system.

Convolutional (TCN) models are deliberately unsupported: they would need a conv
layer in `nn_controller.hpp`. A `--history K` MLP covers most of the same ground.

## Reading the output

Metrics are reported per output channel, not only as a mean. **The mean is
misleading on this data**: a capture has 16 channels and typically one carries a
response, so a model that nails that channel at R² = 0.90 still shows a mean near
0.06. Judge on the strongest output, then narrow with `--use-channels`.

Two guards distinguish the cases:

- *no output beats its own mean* → the model learned nothing. Check the capture
  contains a stim→response relationship at all (`rig\3_fit.ps1 -Sweep`).
- *mean is low but one channel is strong* → normal, and reported as such.

Validation is a **contiguous** tail split, never random. At 100 Hz adjacent ticks
are highly correlated, so a shuffled split leaks the training set into validation
and every metric looks excellent. Same convention as `fit_sysid_from_capture.m`.

Causal alignment (`u(k)` acts on `y(k+1)`) is applied on load, matching the
fitter. Off by one here invents a feedthrough term and flatters everything.

## Before deploying anything

```powershell
& $py verify_export.py
```

Builds a random model of every architecture, exports it, launches the real
`cpp_controller.exe`, sends a real UDP request, and compares the reply against
PyTorch. The hand-written forward passes — especially the GRU's gate ordering and
its split input/hidden biases — are easy to get subtly wrong, and a subtly wrong
policy does not crash. It quietly commands the wrong stimulation. Nothing else in
the pipeline catches that.

Then close the loop against a simulated plant before any hardware:

```powershell
& $py closed_loop_sim.py --plant ..\plant.lti --target 250 --launch
```

Watch the **command range**. If it is ~0 the loop is open — the exact signature of
the observer defect that left the MATLAB MPC ignoring its measurement.

## Safety

A network can emit anything. `cpp_controller --mode nn` clamps to `[--umin,
--umax]` and, if given `--max-rate`, limits the per-tick change. **Set
`--max-rate`.** Without it an untrained or mis-normalised network steps the
stimulation amplitude across its full range in one 10 ms tick.

## Files

| file | role |
|---|---|
| `architectures.py` | the four exportable model families |
| `data.py` | capture CSV → supervised dataset, alignment, history stacking, splits |
| `train.py` | CLI trainer and exporter |
| `export_nnw.py` | PyTorch → `.nnw` writer, and the PyTorch reference forward |
| `verify_export.py` | PyTorch vs C++ equivalence over UDP |
| `closed_loop_sim.py` | closed-loop simulation / MATLAB-vs-native A/B harness |
