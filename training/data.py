"""Datasets built from the (u, y) capture CSVs the control loop writes.

A capture row is one 100 Hz control tick: the commanded stimulation amplitudes
u1..uM and the measured features y1..yN. Both controller servers -- MATLAB and
native -- write this same format, so anything captured at the rig trains here.

TWO FRAMINGS, and picking the right one matters more than picking the architecture:

  inverse  (default)   input = recent feature history      -> output = stim command
                       This IS a controller. It learns which stimulation produced
                       an observed cortical response, so at run time you feed it
                       the response you WANT and it emits the stimulation to get
                       there. It is the learned counterpart of the box-constrained
                       inversion in the biomimetic analysis.

  forward              input = recent stim history         -> output = features
                       This is a plant model, not a controller. Use it to compare
                       against the ARX fit, to simulate, or to supply a nonlinear
                       model for a future MPC. It cannot be dropped into
                       cpp_controller --mode nn and asked to control anything.

CAUSAL ALIGNMENT is applied exactly as fit_sysid_from_capture.m does it: the
command logged at tick k is not transmitted until k+1, so u(k) acts on y(k+1).
Getting this off by one invents a feedthrough term and flatters every metric.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Capture:
    U: np.ndarray          # [T, M] commanded amplitudes
    Y: np.ndarray          # [T, N] measured features
    path: str

    @property
    def n_ticks(self) -> int:
        return self.U.shape[0]


def load_capture(path: str | Path, input_delay_ticks: int = 1,
                 skip_ticks: int = 50) -> Capture:
    path = Path(path)
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        raise SystemExit(f"{path}: no data rows")
    header = rows[0]
    data = np.array(rows[1:], dtype=np.float64)

    u_idx = [i for i, h in enumerate(header) if h.startswith("u")]
    y_idx = [i for i, h in enumerate(header) if h.startswith("y")]
    if not u_idx or not y_idx:
        raise SystemExit(f"{path}: expected u*/y* columns, found {header[:8]}")

    U, Y = data[:, u_idx], data[:, y_idx]
    if input_delay_ticks > 0:
        U, Y = U[:-input_delay_ticks], Y[input_delay_ticks:]
    if skip_ticks > 0:
        U, Y = U[skip_ticks:], Y[skip_ticks:]
    return Capture(U=U, Y=Y, path=str(path))


def stack_history(X: np.ndarray, history: int) -> np.ndarray:
    """[T, F] -> [T-history+1, F*history], oldest first within each row.

    Row t contains [x(t-history+1) ... x(t)] flattened, matching the ordering
    NnController maintains in its ring buffer. If this ordering is changed, the
    C++ side must change with it or the deployed network sees reversed time.
    """
    if history <= 1:
        return X
    T, F = X.shape
    if T < history:
        raise SystemExit(f"record too short ({T} ticks) for history={history}")
    out = np.empty((T - history + 1, F * history), dtype=X.dtype)
    for k in range(history):
        out[:, k * F:(k + 1) * F] = X[k:T - history + 1 + k]
    return out


@dataclass
class Dataset:
    X: np.ndarray
    Y: np.ndarray
    in_mean: np.ndarray     # per-timestep feature stats, NOT per stacked column
    in_std: np.ndarray
    out_mean: np.ndarray
    out_std: np.ndarray
    per_step_input_dim: int
    history: int
    mode: str

    def normalised(self):
        tiled_mean = np.tile(self.in_mean, self.history)
        tiled_std = np.tile(self.in_std, self.history)
        Xn = (self.X - tiled_mean) / tiled_std
        Yn = (self.Y - self.out_mean) / self.out_std
        return Xn.astype(np.float32), Yn.astype(np.float32)


def build_dataset(captures: list[Capture], mode: str = "inverse",
                  history: int = 1, use_channels: list[int] | None = None) -> Dataset:
    """Assemble a supervised dataset from one or more captures.

    Records are normalised with statistics pooled across ALL captures, then
    concatenated. Pooling matters: per-record normalisation would hide exactly
    the between-record baseline drift that crossval_model.m exists to detect.
    """
    src_list, tgt_list = [], []
    for cap in captures:
        if mode == "inverse":
            src, tgt = cap.Y, cap.U
        elif mode == "forward":
            src, tgt = cap.U, cap.Y
        else:
            raise SystemExit(f"unknown mode '{mode}' (use inverse or forward)")

        if use_channels:
            idx = [c - 1 for c in use_channels]
            src = src[:, idx]

        src_h = stack_history(src, history)
        tgt_h = tgt[history - 1:] if history > 1 else tgt
        src_list.append(src_h)
        tgt_list.append(tgt_h)

    X = np.concatenate(src_list, axis=0)
    Y = np.concatenate(tgt_list, axis=0)

    per_step = X.shape[1] // history
    X_steps = X.reshape(-1, history, per_step).reshape(-1, per_step)
    in_mean = X_steps.mean(axis=0)
    in_std = X_steps.std(axis=0)
    in_std[in_std < 1e-9] = 1.0

    out_mean = Y.mean(axis=0)
    out_std = Y.std(axis=0)
    # A stim channel held constant (the activeChannels mask) has zero variance.
    # Leave its std at 1 so normalisation is a pure offset and the network can
    # still learn to emit that constant, rather than dividing by ~0.
    out_std[out_std < 1e-9] = 1.0

    return Dataset(X=X, Y=Y, in_mean=in_mean, in_std=in_std,
                   out_mean=out_mean, out_std=out_std,
                   per_step_input_dim=per_step, history=history, mode=mode)


def split_train_val(X: np.ndarray, Y: np.ndarray, train_fraction: float = 0.7):
    """Contiguous split, never random.

    A random split leaks: adjacent ticks are highly correlated at 100 Hz, so a
    shuffled validation set is effectively the training set and every metric
    looks excellent. The last (1 - train_fraction) of the record is held out,
    matching fit_sysid_from_capture.m.
    """
    n = X.shape[0]
    cut = int(n * train_fraction)
    return X[:cut], Y[:cut], X[cut:], Y[cut:]
