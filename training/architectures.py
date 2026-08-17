"""Network architectures for the neural control path.

Every architecture here is EXPORTABLE to the .nnw format that cpp_controller
reads, which constrains what may be used: affine layers, ReLU/tanh, residual
skips, and GRU cells. That constraint is deliberate. A model that trains
beautifully in PyTorch but cannot be evaluated inside a 10 ms tick without
LibTorch is not a control policy, it is a research artefact.

Temporal context is provided by `history`, which stacks the last K feature
vectors into the network input. This is how the temporally-aware models are
deployed without needing convolution support in the C++ inference path.

    linear        one affine map. The ridge/least-squares baseline, and the one
                  to beat -- the acute architecture search found networks beat a
                  linear baseline by only ~0.7% median RMSE, so if a fancier
                  model is not clearly better here, prefer this one.
    mlp           stacked affine + activation
    residual_mlp  as mlp with skip connections. Won most per-block comparisons
                  in the acute search, which is why it is the default.
    gru           recurrent. The architecture to reach for given that the
                  biomimetic result identifies the shortfall as TEMPORAL.

NOT SUPPORTED ON PURPOSE: convolutional (TCN) models. They would need a conv
layer in cpp_controller/nn_controller.hpp. A window_size>1 MLP covers most of
the same ground; add the C++ layer first if a real TCN is wanted.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class LinearPolicy(nn.Module):
    """Affine map. Equivalent to ridge regression when trained with weight decay."""

    arch_name = "linear"

    def __init__(self, in_dim: int, out_dim: int, **_: object) -> None:
        super().__init__()
        self.fc = nn.Linear(in_dim, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)

    def export_layers(self):
        return [("linear", self.fc, "none")]


class MlpPolicy(nn.Module):
    arch_name = "mlp"

    def __init__(self, in_dim: int, out_dim: int, hidden=(64, 64),
                 activation: str = "relu", **_: object) -> None:
        super().__init__()
        self.activation = activation
        act = {"relu": nn.ReLU, "tanh": nn.Tanh}[activation]
        self.layers = nn.ModuleList()
        self.acts = []
        prev = in_dim
        for h in hidden:
            self.layers.append(nn.Linear(prev, h))
            self.acts.append(activation)
            prev = h
        self.layers.append(nn.Linear(prev, out_dim))
        self.acts.append("none")
        self._act = act()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for i, layer in enumerate(self.layers):
            x = layer(x)
            if self.acts[i] != "none":
                x = self._act(x)
        return x

    def export_layers(self):
        return [("linear", l, a) for l, a in zip(self.layers, self.acts)]


class ResidualMlpPolicy(nn.Module):
    """MLP with skip connections on the equal-width hidden layers.

    The residual blocks require in == out, so an input projection and an output
    head bracket a stack of constant-width residual layers. Matches the
    'residual_mlp' that won the per-block architecture search on the acute data.
    """

    arch_name = "residual_mlp"

    def __init__(self, in_dim: int, out_dim: int, hidden: int = 64, blocks: int = 2,
                 activation: str = "relu", **_: object) -> None:
        super().__init__()
        self.activation = activation
        self.proj = nn.Linear(in_dim, hidden)
        self.blocks = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(blocks)])
        self.head = nn.Linear(hidden, out_dim)
        self._act = {"relu": nn.ReLU, "tanh": nn.Tanh}[activation]()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self._act(self.proj(x))
        for b in self.blocks:
            x = self._act(b(x)) + x          # matches LayerKind::Residual in C++
        return self.head(x)

    def export_layers(self):
        out = [("linear", self.proj, self.activation)]
        out += [("residual", b, self.activation) for b in self.blocks]
        out += [("linear", self.head, "none")]
        return out


class GruPolicy(nn.Module):
    """Single GRU cell followed by a linear head.

    Kept to one cell because cpp_controller evaluates GRUCell semantics directly;
    stacking is possible but each extra cell is another exported layer and another
    hidden state to keep in sync. Verify any change with verify_export.py.
    """

    arch_name = "gru"

    def __init__(self, in_dim: int, out_dim: int, hidden: int = 64, **_: object) -> None:
        super().__init__()
        self.cell = nn.GRUCell(in_dim, hidden)
        self.head = nn.Linear(hidden, out_dim)
        self.hidden_size = hidden

    def forward(self, x: torch.Tensor, h: torch.Tensor | None = None) -> torch.Tensor:
        # x: [batch, in_dim] -- one timestep. Sequence training feeds ticks in
        # order and carries h; see train.py's --seq-len.
        if h is None:
            h = torch.zeros(x.shape[0], self.hidden_size, device=x.device, dtype=x.dtype)
        h = self.cell(x, h)
        return self.head(h), h

    def export_layers(self):
        return [("gru", self.cell, "none"), ("linear", self.head, "none")]


REGISTRY = {
    "linear": LinearPolicy,
    "mlp": MlpPolicy,
    "residual_mlp": ResidualMlpPolicy,
    "gru": GruPolicy,
}


def build(arch: str, in_dim: int, out_dim: int, **kwargs) -> nn.Module:
    if arch not in REGISTRY:
        raise SystemExit(f"unknown architecture '{arch}'. Options: {', '.join(REGISTRY)}")
    return REGISTRY[arch](in_dim=in_dim, out_dim=out_dim, **kwargs)


def is_recurrent(model: nn.Module) -> bool:
    return isinstance(model, GruPolicy)
