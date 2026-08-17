"""End-to-end check that cpp_controller computes what PyTorch computes.

For each architecture it builds a randomly-initialised model, exports it to .nnw,
launches the real cpp_controller.exe, sends a real UDP request, and compares the
reply against PyTorch's output for the same input.

This is the test that matters for the neural path. The forward passes in
nn_controller.hpp are hand-written -- the GRU gate ordering and its split
input/hidden biases are especially easy to get subtly wrong, and a subtly wrong
policy does not crash, it just quietly commands the wrong stimulation. Nothing
else in the pipeline would catch that.

    python verify_export.py

Run it after ANY change to nn_controller.hpp or export_nnw.py.
"""
from __future__ import annotations

import socket
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architectures
from export_nnw import export_nnw, torch_reference_forward

REPO = Path(__file__).resolve().parents[1]
EXE = REPO / "cpp_controller.exe"

REQ_PORT = 31500
REP_PORT = 31501


@dataclass
class FakeDataset:
    """Minimal stand-in for data.Dataset -- only what export_nnw touches."""
    in_mean: np.ndarray
    in_std: np.ndarray
    out_mean: np.ndarray
    out_std: np.ndarray
    per_step_input_dim: int
    history: int
    Y: np.ndarray


def make_dataset(per_step: int, history: int, out_dim: int, rng) -> FakeDataset:
    # Non-trivial normalisation stats on purpose: mean 0 / std 1 would let a
    # normalisation bug pass unnoticed.
    return FakeDataset(
        in_mean=rng.uniform(-5, 5, per_step),
        in_std=rng.uniform(0.5, 3.0, per_step),
        out_mean=rng.uniform(-2, 2, out_dim),
        out_std=rng.uniform(0.5, 2.0, out_dim),
        per_step_input_dim=per_step,
        history=history,
        Y=np.zeros((1, out_dim)),
    )


def query_cpp(model_path: Path, features: np.ndarray, out_count: int,
              timeout_s: float = 20.0) -> np.ndarray | None:
    """Launch cpp_controller for a single packet and return its reply."""
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", REP_PORT))
    rx.settimeout(0.5)

    proc = subprocess.Popen(
        [str(EXE), "--mode", "nn", "--model", str(model_path),
         "--output-count", str(out_count), "--max-packets", "1",
         "--request-port", str(REQ_PORT), "--reply-port", str(REP_PORT),
         "--umin", "-1e9", "--umax", "1e9"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        payload = struct.pack(">II", 7, len(features))
        payload += b"".join(struct.pack(">f", float(v)) for v in features)

        deadline = time.time() + timeout_s
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while time.time() < deadline:
            tx.sendto(payload, ("127.0.0.1", REQ_PORT))
            try:
                data, _ = rx.recvfrom(65536)
            except socket.timeout:
                if proc.poll() is not None:
                    print(proc.stdout.read())
                    return None
                continue
            seq, count = struct.unpack(">II", data[:8])
            return np.array(struct.unpack(f">{count}f", data[8:8 + 4 * count]))
        print("  timed out waiting for a reply")
        return None
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        rx.close()


def main() -> int:
    if not EXE.exists():
        print(f"cpp_controller.exe not found at {EXE}\nBuild it: build_cpp_controller.bat")
        return 1

    rng = np.random.default_rng(20260730)
    torch.manual_seed(0)

    cases = [
        ("linear", 1, {}),
        ("mlp", 1, {"hidden": (32, 24)}),
        ("mlp", 4, {"hidden": (32,), "activation": "tanh"}),
        ("residual_mlp", 1, {"hidden": 32, "blocks": 2}),
        ("residual_mlp", 3, {"hidden": 16, "blocks": 3}),
        ("gru", 1, {"hidden": 24}),
        ("gru", 2, {"hidden": 16}),
    ]

    per_step, out_dim = 8, 5
    failures = 0
    tmpdir = Path(tempfile.mkdtemp(prefix="nnw_verify_"))
    print(f"Comparing PyTorch against cpp_controller.exe over UDP\n"
          f"per-timestep features = {per_step}, outputs = {out_dim}\n")

    for arch, history, kw in cases:
        ds = make_dataset(per_step, history, out_dim, rng)
        model = architectures.build(arch, per_step * history, out_dim, **kw)
        # Random init leaves some weights near zero; scale up so a wrong gate
        # ordering produces a visibly different answer rather than a near-miss.
        with torch.no_grad():
            for p in model.parameters():
                p.mul_(1.5).add_(torch.randn_like(p) * 0.25)

        path = tmpdir / f"{arch}_h{history}.nnw"
        export_nnw(model, ds, path, out_min=-1e9, out_max=1e9)

        # One tick: NnController primes its whole history window with the first
        # sample, so the reference input is that sample tiled `history` times.
        x = rng.uniform(-4, 8, per_step)
        expected = torch_reference_forward(model, ds, np.tile(x, (history, 1)))
        got = query_cpp(path, x, out_dim)

        label = f"{arch:14s} history={history}"
        if got is None:
            print(f"  {label}  FAIL (no reply)")
            failures += 1
            continue

        err = float(np.max(np.abs(got - expected)))
        # float32 on the wire, double internally -- 1e-4 is a generous bound that
        # still catches any structural error (a wrong gate order is O(1)).
        ok = err < 1e-4
        print(f"  {label}  {'PASS' if ok else 'FAIL'}  max|Δ| = {err:.3e}")
        if not ok:
            failures += 1
            print(f"      torch: {np.array2string(expected, precision=6)}")
            print(f"      cpp  : {np.array2string(got, precision=6)}")

    print(f"\n{'ALL MATCH' if failures == 0 else 'MISMATCH'} "
          f"({failures} failure{'' if failures == 1 else 's'})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
