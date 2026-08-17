"""Closed-loop simulation against a controller server, over the real socket.

Simulates a plant in Python and drives it with whatever controller is listening
on the localhost control ports. Because it speaks the same wire protocol as
MpcPo8eUdpClosedLoop.exe, it can drive EITHER server:

    # native controller (launched automatically)
    python closed_loop_sim.py --plant ../plant_toy.lti --target 5 --launch

    # MATLAB controller (start matlab_controller_server in mpc mode first)
    python closed_loop_sim.py --plant ../plant_toy.lti --target 5

That makes it the A/B harness for the two control paths: same plant, same
protocol, same setpoint, and the only difference is which server is answering.
It is also the way to exercise a controller end to end with no hardware and no
animal -- which is when you want to discover that a policy oscillates.

WHAT TO LOOK AT
  command range    if it is ~0 the loop is open. That is the exact signature of
                   the observer defect that left the MATLAB MPC ignoring its
                   measurement for months.
  final output     against the setpoint. Note that with R = I and no integral
                   action the MPC settles SHORT of the setpoint by design; see
                   the offset formula in cpp_controller/main.cpp's self-test.
  saturation       a command pinned at a bound means the target is unreachable.
"""
from __future__ import annotations

import argparse
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def load_lti(path: Path):
    """Parse the .lti text format written by export_plant_lti.m."""
    toks, skip = [], False
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0]
        toks.extend(line.split())
    i = 0

    def nxt():
        nonlocal i
        v = toks[i]
        i += 1
        return v

    assert nxt() == "LTI" and nxt() == "1", "not an LTI 1 file"
    assert nxt() == "Ts"; Ts = float(nxt())
    assert nxt() == "n";  n = int(nxt())
    assert nxt() == "m";  m = int(nxt())
    assert nxt() == "p";  p = int(nxt())

    def block(name, r, c):
        assert nxt() == name, f"expected block {name}"
        return np.array([float(nxt()) for _ in range(r * c)]).reshape(r, c)

    A = block("A", n, n); B = block("B", n, m)
    C = block("C", p, n); D = block("D", p, m)
    return A, B, C, D, Ts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plant", required=True, help=".lti plant to simulate")
    ap.add_argument("--ticks", type=int, default=2000)
    ap.add_argument("--target", type=float, default=5.0)
    ap.add_argument("--request-port", type=int, default=31000)
    ap.add_argument("--reply-port", type=int, default=31001)
    ap.add_argument("--output-count", type=int, default=16)
    ap.add_argument("--noise", type=float, default=0.0, help="measurement noise std")
    ap.add_argument("--launch", action="store_true",
                    help="start cpp_controller in mpc mode automatically")
    ap.add_argument("--launch-args", nargs=argparse.REMAINDER, default=[],
                    help="extra args passed through to cpp_controller")
    args = ap.parse_args()

    A, B, C, D, Ts = load_lti(Path(args.plant))
    n, m, p = A.shape[0], B.shape[1], C.shape[0]
    print(f"Plant {args.plant}: n={n} m={m} p={p} Ts={Ts}")

    proc = None
    if args.launch:
        cmd = [str(REPO / "cpp_controller.exe"), "--mode", "mpc",
               "--model", str(args.plant), "--target", str(args.target),
               "--output-count", str(args.output_count),
               "--max-packets", str(args.ticks),
               "--request-port", str(args.request_port),
               "--reply-port", str(args.reply_port)] + list(args.launch_args)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(0.6)

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", args.reply_port))
    rx.settimeout(2.0)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    x = np.zeros(n)
    u = np.zeros(m)
    rng = np.random.default_rng(0)
    ys, us, rtts, timeouts = [], [], [], 0

    try:
        for k in range(args.ticks):
            y = (C @ x + D @ u).ravel()
            if args.noise > 0:
                y = y + rng.normal(0, args.noise, y.shape)

            # The feature vector the C++ loop sends is output_count wide; the
            # controller's feature_map picks out the modelled channels.
            feat = np.zeros(args.output_count)
            feat[:min(p, args.output_count)] = y[:min(p, args.output_count)]

            pkt = struct.pack(">II", k + 1, len(feat))
            pkt += b"".join(struct.pack(">f", float(v)) for v in feat)
            t0 = time.perf_counter()
            tx.sendto(pkt, ("127.0.0.1", args.request_port))
            try:
                dat, _ = rx.recvfrom(65536)
            except socket.timeout:
                timeouts += 1
                if timeouts > 20:
                    print("controller stopped responding")
                    break
                continue
            rtts.append((time.perf_counter() - t0) * 1000.0)

            seq, cnt = struct.unpack(">II", dat[:8])
            vals = np.array(struct.unpack(f">{cnt}f", dat[8:8 + 4 * cnt]))
            u = vals[:m]

            # One-tick command lag, matching the real localhost path: the command
            # computed from y(k) is not applied until k+1. Omitting this would
            # make the simulation optimistic relative to the rig.
            x = (A @ x + B @ u).ravel()
            ys.append(float(y[0]))
            us.append(float(u[0]))
    finally:
        rx.close(); tx.close()
        if proc:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    if not ys:
        print("no data collected")
        return 1

    ys_a, us_a = np.array(ys), np.array(us)
    tail = slice(max(0, len(ys_a) - 200), None)
    print(f"\nTicks completed      : {len(ys_a)}  (timeouts {timeouts})")
    print(f"Round-trip           : mean {np.mean(rtts):.3f} ms, p95 {np.percentile(rtts,95):.3f} ms")
    print(f"Output y  final/mean : {ys_a[-1]:.4f} / {ys_a[tail].mean():.4f}   target {args.target}")
    print(f"Command u final/mean : {us_a[-1]:.4f} / {us_a[tail].mean():.4f}")
    print(f"Command range        : {us_a.max() - us_a.min():.6f}")

    if us_a.max() - us_a.min() < 1e-6:
        print("\n*** COMMAND IS CONSTANT -- the loop is NOT closed. ***")
        return 1
    print("\nCommand varies: the controller is responding to its measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
