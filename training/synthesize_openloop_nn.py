#!/usr/bin/env python
"""synthesize_openloop_nn.py -- open-loop stim tape from an inverse NN policy.

    python training/synthesize_openloop_nn.py --nnw models/inv.nnw \
        --ref ../ref_touch.csv --input-channels 11 --umax 25 \
        --out ../design_nntape.csv --parity

The NN analog of choi_synthesis.py: feed the reference trajectory through the
trained inverse policy OFFLINE, tick by tick, exactly as the deployed
controller would see it, and write the resulting command sequence as a design
CSV (tick,u1..uN) for verbatim replay:

    cpp_controller.exe --mode openloop --play design_nntape.csv ...

The rollout replicates cpp_controller's NnController::step to the letter:
per-step normalisation (non-finite -> 0), history window primed with the
first sample (not zeros), residual = input added AFTER activation, PyTorch
GRUCell gate order r,z,n with r multiplying the hidden term after its bias,
de-normalisation, non-finite -> hold previous, clamp to [--umin,--umax] THEN
slew-limit (--max-rate). Clamps come from the CLI exactly as in deployment
(the .nnw's out_min/out_max metadata is NOT consulted at runtime by
cpp_controller -- verified against main.cpp/nn_controller.hpp 2026-08-25).
Give this script the SAME --umin/--umax/--max-rate you will pass to
--mode nn, or the open- and closed-loop arms will not be comparable.

--input-channels maps reference column j to policy input feature c_j
(1-based). Unreferenced input features are held at that feature's training
mean (= 0 after normalisation) by default, or at 0 raw with --fill zero.

--parity launches the real cpp_controller.exe --mode nn, streams the same
feature sequence over the wire, and requires the returned commands to match
the tape to <= 1e-4 (f32 wire quantisation; typically ~1e-6). Run it once per
model before trusting a tape.

Refuses '# mode: forward' models (a forward model as controller would emit
predicted FEATURES as stim amplitudes) -- same rule as rig/check_nnw_mode.py.
"""

import argparse
import csv
import json
import os
import socket
import struct
import subprocess
import sys
import time

import numpy as np


def parse_nnw(path):
    mode = None
    toks = []
    for raw in open(path).read().splitlines():
        s = raw.strip()
        if s.startswith("#"):
            if s.lower().replace(" ", "").startswith("#mode:"):
                mode = s.split(":", 1)[1].strip().lower()
            continue
        toks.extend(s.split())
    it = iter(toks)

    def nxt():
        return next(it)

    def expect(k):
        v = nxt()
        if v != k:
            raise SystemExit("FAIL: %s: expected '%s', got '%s'" % (path, k, v))

    def num():
        return float(nxt())

    def integer():
        return int(nxt())

    def vec(n):
        return np.array([num() for _ in range(n)])

    def mat(r, c):
        return vec(r * c).reshape(r, c)

    expect("NNW")
    if integer() != 1:
        raise SystemExit("FAIL: unsupported NNW version")
    m = {"mode": mode}
    expect("arch"); m["arch"] = nxt()
    expect("input"); m["input"] = integer()
    expect("output"); m["output"] = integer()
    expect("history"); m["history"] = integer()
    expect("in_mean"); m["in_mean"] = vec(m["input"])
    expect("in_std"); m["in_std"] = vec(m["input"])
    expect("out_mean"); m["out_mean"] = vec(m["output"])
    expect("out_std"); m["out_std"] = vec(m["output"])
    expect("out_min"); m["out_min"] = num()
    expect("out_max"); m["out_max"] = num()
    m["in_std"] = np.where(np.abs(m["in_std"]) > 1e-12, m["in_std"], 1.0)
    m["out_std"] = np.where(np.abs(m["out_std"]) > 1e-12, m["out_std"], 1.0)
    expect("layers")
    n_layers = integer()
    layers = []
    for _ in range(n_layers):
        expect("layer")
        kind = nxt()
        if kind in ("linear", "residual"):
            li, lo = integer(), integer()
            act = nxt()
            expect("W"); W = mat(lo, li)
            expect("b"); b = vec(lo)
            layers.append(dict(kind=kind, act=act, W=W, b=b))
        elif kind == "gru":
            li, lo = integer(), integer()
            expect("W_ih"); W_ih = mat(3 * lo, li)
            expect("W_hh"); W_hh = mat(3 * lo, lo)
            expect("b_ih"); b_ih = vec(3 * lo)
            expect("b_hh"); b_hh = vec(3 * lo)
            layers.append(dict(kind="gru", hidden=lo,
                               W_ih=W_ih, W_hh=W_hh, b_ih=b_ih, b_hh=b_hh))
        else:
            raise SystemExit("FAIL: unknown layer kind '%s'" % kind)
    m["layers"] = layers
    return m


def act_apply(name, v):
    if name == "relu":
        return np.maximum(v, 0.0)
    if name == "tanh":
        return np.tanh(v)
    return v


def sigmoid(v):
    return 1.0 / (1.0 + np.exp(-v))


class Rollout:
    """Mirror of cpp_controller NnController::step (nn_controller.hpp)."""

    def __init__(self, m, umin, umax, max_rate):
        self.m = m
        self.umin, self.umax, self.max_rate = umin, umax, max_rate
        self.hist = np.zeros(m["input"] * m["history"])
        self.u_last = np.zeros(m["output"])
        self.h = [np.zeros(L["hidden"]) if L["kind"] == "gru" else None
                  for L in m["layers"]]
        self.primed = False

    def step(self, features):
        m = self.m
        raw = np.zeros(m["input"])
        raw[:min(len(features), m["input"])] = features[:m["input"]]
        x = (raw - m["in_mean"]) / m["in_std"]
        x[~np.isfinite(x)] = 0.0
        if m["history"] > 1:
            if not self.primed:
                self.hist = np.tile(x, m["history"])
                self.primed = True
            else:
                self.hist = np.concatenate([self.hist[m["input"]:], x])
        else:
            self.hist = x.copy()
        cur = self.hist
        for li, L in enumerate(m["layers"]):
            if L["kind"] in ("linear", "residual"):
                s = L["W"] @ cur + L["b"]
                s = act_apply(L["act"], s)
                if L["kind"] == "residual":
                    s = s + cur[:len(s)]
                cur = s
            else:
                H = L["hidden"]
                gi = L["W_ih"] @ cur + L["b_ih"]
                gh = L["W_hh"] @ self.h[li] + L["b_hh"]
                r = sigmoid(gi[:H] + gh[:H])
                z = sigmoid(gi[H:2 * H] + gh[H:2 * H])
                n = np.tanh(gi[2 * H:] + r * gh[2 * H:])
                self.h[li] = (1.0 - z) * n + z * self.h[li]
                cur = self.h[li]
        u = cur[:m["output"]] * m["out_std"] + m["out_mean"]
        if not np.all(np.isfinite(u)):
            u = self.u_last.copy()
        u = np.clip(u, self.umin, self.umax)
        if self.max_rate > 0:
            d = np.clip(u - self.u_last, -self.max_rate, self.max_rate)
            u = self.u_last + d
        self.u_last = u.copy()
        return u


def load_ref(path):
    with open(path, newline="") as f:
        rows = []
        header = None
        for raw in csv.reader(f):
            if not raw or raw[0].lstrip().startswith("#"):
                continue
            if header is None:
                header = raw
                continue
            rows.append([float(v) for v in raw])
    M = np.array(rows)
    cols = [i for i, c in enumerate(header) if c.startswith("r")]
    if not cols:
        cols = list(range(1, M.shape[1]))
    return M[:, cols]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nnw", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--input-channels", type=int, nargs="+", required=True,
                    help="policy input feature (1-based) driven by each ref column")
    ap.add_argument("--fill", choices=["mean", "zero"], default="mean",
                    help="unreferenced input features: training mean (default) or 0")
    ap.add_argument("--output-count", type=int, default=8)
    ap.add_argument("--umin", type=float, default=0.0)
    ap.add_argument("--umax", type=float, default=25.0)
    ap.add_argument("--max-rate", type=float, default=0.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--parity", action="store_true",
                    help="verify the tape against a live cpp_controller --mode nn")
    ap.add_argument("--cpp", default=os.path.join(os.path.dirname(__file__),
                                                  "..", "cpp_controller.exe"))
    args = ap.parse_args()

    m = parse_nnw(args.nnw)
    if m["mode"] == "forward":
        print("FAIL: %s is stamped '# mode: forward' -- a PLANT model. Feeding a "
              "reference through it emits predicted features as stim amplitudes. "
              "Train/export with --mode inverse." % args.nnw)
        return 1
    if m["mode"] != "inverse":
        print("warn: %s has no '# mode:' stamp; proceeding, but confirm it is an "
              "inverse policy (rig/check_nnw_mode.py)" % args.nnw)

    R = load_ref(args.ref)
    if R.shape[1] != len(args.input_channels):
        print("FAIL: reference has %d column(s) but %d --input-channels given"
              % (R.shape[1], len(args.input_channels)))
        return 1
    bad = [c for c in args.input_channels if not (1 <= c <= m["input"])]
    if bad:
        print("FAIL: --input-channels %s outside the policy's %d inputs"
              % (bad, m["input"]))
        return 1

    # Feature stream in f32, exactly what the wire would carry.
    T = len(R)
    F = np.tile((m["in_mean"] if args.fill == "mean"
                 else np.zeros(m["input"])).astype(np.float32), (T, 1))
    for j, c in enumerate(args.input_channels):
        F[:, c - 1] = R[:, j].astype(np.float32)

    ro = Rollout(m, args.umin, args.umax, args.max_rate)
    U = np.array([ro.step(F[t].astype(np.float64)) for t in range(T)])
    Uw = np.zeros((T, args.output_count))
    n_copy = min(args.output_count, m["output"])
    Uw[:, :n_copy] = U[:, :n_copy]

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick"] + ["u%d" % (i + 1) for i in range(args.output_count)])
        for t in range(T):
            w.writerow([t + 1] + ["%.9g" % v for v in Uw[t]])
    print("Wrote %s: %d ticks x %d outputs, u in [%.4g, %.4g], mean %.4g"
          % (args.out, T, args.output_count, Uw.min(), Uw.max(), Uw.mean()))
    if not np.all(np.isfinite(Uw)):
        print("FAIL: tape contains non-finite values")
        return 1

    meta = dict(nnw=os.path.abspath(args.nnw),
                nnw_mtime=os.path.getmtime(args.nnw), ref=os.path.abspath(args.ref),
                input_channels=args.input_channels, fill=args.fill,
                umin=args.umin, umax=args.umax, max_rate=args.max_rate,
                output_count=args.output_count, arch=m["arch"],
                history=m["history"], parity=None)

    if args.parity:
        exe = os.path.abspath(args.cpp)
        cmd = [exe, "--mode", "nn", "--model", os.path.abspath(args.nnw),
               "--output-count", str(args.output_count),
               "--umin", str(args.umin), "--umax", str(args.umax),
               "--max-packets", str(T)]
        if args.max_rate > 0:
            cmd += ["--max-rate", str(args.max_rate)]
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(exe),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        time.sleep(1.0)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.bind(("127.0.0.1", 31001))
        worst = 0.0
        try:
            for t in range(T):
                payload = struct.pack(">II", t + 1, m["input"]) + \
                    b"".join(struct.pack(">f", v) for v in F[t])
                sock.sendto(payload, ("127.0.0.1", 31000))
                data, _ = sock.recvfrom(65536)
                seq, cnt = struct.unpack(">II", data[:8])
                vals = struct.unpack(">%df" % cnt, data[8:8 + 4 * cnt])
                n = min(cnt, args.output_count)
                worst = max(worst, float(np.max(np.abs(
                    np.array(vals[:n]) - Uw[t, :n]))))
        finally:
            sock.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        ok = worst <= 1e-4
        meta["parity"] = dict(worst_abs_diff=worst, passed=bool(ok))
        print("PARITY %s: max |tape - live cpp_controller| = %.3g over %d ticks "
              "(limit 1e-4)" % ("PASS" if ok else "FAIL", worst, T))
        if not ok:
            return 1

    with open(args.out.rsplit(".", 1)[0] + "_meta.json", "w") as f:
        json.dump(meta, f, indent=1)
    print("Deliver with: cpp_controller.exe --mode openloop --play %s "
          "--output-count %d --max-packets %d" % (args.out, args.output_count, T))
    return 0


if __name__ == "__main__":
    sys.exit(main())
