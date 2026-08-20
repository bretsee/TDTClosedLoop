"""Write a trained PyTorch model to the .nnw text format cpp_controller reads.

The format is plain text on purpose: greppable at the rig, diffable in git, and
parseable with no serialisation library on the C++ side. A 16-64-64-16 network is
about 5k numbers, so the file is small and load time is negligible.

WEIGHT LAYOUT -- the part that is easy to get silently wrong:
  nn.Linear stores weight as [out, in] and computes x @ W.T + b, so writing the
  tensor row-major gives exactly the [out x in] matrix the C++ side expects.
  nn.GRUCell stores weight_ih as [3H, in] with the gates stacked in the order
  r, z, n, and keeps SEPARATE input and hidden biases (b_ih, b_hh) which must
  both be preserved -- collapsing them into one bias changes the result, because
  the reset gate multiplies the hidden term after its bias is added.

Always run verify_export.py after changing anything here. It pushes identical
input through PyTorch and the built cpp_controller and compares.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from architectures import GruPolicy


def _fmt(values: np.ndarray) -> str:
    """Full round-trip precision. repr-style floats keep the C++ result bit-close."""
    return " ".join(f"{v:.9g}" for v in np.asarray(values, dtype=np.float64).ravel())


def export_nnw(model: torch.nn.Module, dataset, out_path: str | Path,
               out_min: float = 0.0, out_max: float = 40.0,
               mode: str = "inverse") -> Path:
    out_path = Path(out_path)
    model = model.eval().cpu()

    layers = model.export_layers()
    lines: list[str] = []
    lines.append("NNW 1")
    # Comment form so every existing parser (model_io.hpp strips '#' tokens)
    # stays compatible. Only an 'inverse' model (features -> stim) is a
    # controller; deploying a 'forward' model in cpp_controller --mode nn
    # would send predicted FEATURES as stim commands. rig/check_nnw_mode.py
    # enforces this before deployment; a C++-side refusal is queued for the
    # next cpp_controller rebuild.
    lines.append(f"# mode: {mode}")
    lines.append(f"arch {model.arch_name}")
    lines.append(f"input {dataset.per_step_input_dim}")
    lines.append(f"output {dataset.Y.shape[1]}")
    lines.append(f"history {dataset.history}")
    lines.append(f"in_mean {_fmt(dataset.in_mean)}")
    lines.append(f"in_std {_fmt(dataset.in_std)}")
    lines.append(f"out_mean {_fmt(dataset.out_mean)}")
    lines.append(f"out_std {_fmt(dataset.out_std)}")
    lines.append(f"out_min {out_min:.9g}")
    lines.append(f"out_max {out_max:.9g}")
    lines.append(f"layers {len(layers)}")

    for kind, module, act in layers:
        if kind in ("linear", "residual"):
            W = module.weight.detach().numpy()          # [out, in]
            b = module.bias.detach().numpy()            # [out]
            lines.append(f"layer {kind} {W.shape[1]} {W.shape[0]} {act}")
            lines.append(f"W {_fmt(W)}")
            lines.append(f"b {_fmt(b)}")
        elif kind == "gru":
            cell = module
            in_dim = cell.weight_ih.shape[1]
            hidden = cell.weight_hh.shape[1]
            lines.append(f"layer gru {in_dim} {hidden}")
            lines.append(f"W_ih {_fmt(cell.weight_ih.detach().numpy())}")
            lines.append(f"W_hh {_fmt(cell.weight_hh.detach().numpy())}")
            lines.append(f"b_ih {_fmt(cell.bias_ih.detach().numpy())}")
            lines.append(f"b_hh {_fmt(cell.bias_hh.detach().numpy())}")
        else:
            raise SystemExit(f"export_nnw: unsupported layer kind '{kind}'")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def torch_reference_forward(model: torch.nn.Module, dataset,
                            raw_features: np.ndarray) -> np.ndarray:
    """Run the PyTorch model exactly as cpp_controller would, for comparison.

    Takes RAW (un-normalised) per-timestep features shaped [history, per_step],
    applies the same normalisation, forward pass and de-normalisation, and
    returns the clamped command. This is the reference verify_export.py checks
    the C++ against.
    """
    model = model.eval().cpu()
    x = (raw_features - dataset.in_mean) / dataset.in_std
    flat = torch.tensor(x.reshape(1, -1), dtype=torch.float32)
    with torch.no_grad():
        if isinstance(model, GruPolicy):
            out, _ = model(flat, None)
        else:
            out = model(flat)
    y = out.numpy().ravel() * dataset.out_std + dataset.out_mean
    return y
