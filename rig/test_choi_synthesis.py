"""No-hardware acceptance tests for rig/choi_synthesis.py.

Run:  python rig\\test_choi_synthesis.py        (from the repo root, any python
with numpy; the venv interpreter works)

Checks, all against the toy plant (A=0.95122942, B=0.00975412, C=1, D=0,
g = B/(1-A) = 0.2000):
  1. Analytic steady state, gate off: interior u* = r*g/(g^2 + mu), mu in {0, 0.01}.
  2. Gate pass-through: threshold below the solution -> identical to ungated.
  3. Gate compensation (the Choi undershoot fix): with everything below a high
     threshold attenuated by a, the optimizer must command u = r/(a*g) -- it
     boosts to punch through the modeled attenuation instead of undershooting.
  4. Gate honesty: a threshold placed exactly in the oscillatory band must be
     REPORTED as non-converged, never silently emitted as clean.
  5. Offset frame: with uOffset/yOffset the interior settles at
     u* = uOff + (r - yOff)/g (mu -> 0), in RAW units.
  6. CSV round-trip: emitted design re-reads exactly (%.9g), header matches the
     write_excitation_csv.m convention, all values in [0, umax].
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from choi_synthesis import Model, synthesize, write_design_csv  # noqa: E402

A_, B_ = 0.95122942450071402, 0.0097541150998571979
G_DC = B_ / (1.0 - A_)          # 0.20000 DC gain

fails = 0

def report(name: str, ok: bool, detail: str) -> int:
    print(f"{'PASS' if ok else 'FAIL'}  {name:34s} {detail}")
    return 0 if ok else 1

def toy(uOff=0.0, yOff=0.0) -> Model:
    return Model(np.array([[A_]]), np.array([[B_]]), np.array([[1.0]]),
                 np.array([[0.0]]), 0.01, np.array([uOff]), np.array([yOff]))

def interior(U: np.ndarray) -> np.ndarray:
    T = U.shape[0]
    return U[T // 3: 2 * T // 3, 0]

T = 600
r = 0.5
R = np.full((T, 1), r)

# ---- 1. analytic steady state, gate off ----------------------------------
for mu in (0.0, 0.01):
    U, info = synthesize(toy(), R, umax=40.0, mu=mu, lam=0.0, tau_lp=0.1,
                         gate_thr=0.0, gate_atten=0.1, gate_iters=0, x0_mode="rest")
    u_star = r * G_DC / (G_DC ** 2 + mu)
    got = interior(U).mean()
    rel = abs(got - u_star) / u_star
    fails += report(f"steady state mu={mu:g}", rel < 1e-3,
                    f"interior u = {got:.5f}, analytic u* = {u_star:.5f} (rel {rel:.2e})")

# ---- 2. gate pass-through (threshold below the solution) ------------------
U0, _ = synthesize(toy(), R, 40.0, 0.0, 0.0, 0.1, 0.0, 0.1, 0, "rest")
U2, info2 = synthesize(toy(), R, 40.0, 0.0, 0.0, 0.1, gate_thr=1.0,
                       gate_atten=0.1, gate_iters=60, x0_mode="rest")
fails += report("gate pass-through", info2["gate_converged"]
                and np.max(np.abs(interior(U2) - interior(U0))) < 1e-4,
                f"converged={info2['gate_converged']}, "
                f"max interior diff vs ungated {np.max(np.abs(interior(U2)-interior(U0))):.2e}")

# ---- 3. gate compensation (the undershoot fix) ----------------------------
# Threshold 30 with atten 0.1: everything the optimizer can afford is modeled
# as attenuated, so honest tracking requires u = r/(a*g) = 25 -- 10x the naive
# ungated command. Without the gate this problem "solves" at 2.5 and the rig
# would undershoot by 90%. That boost IS Choi's reason for the gate.
U3, info3 = synthesize(toy(), R, 40.0, 0.0, 0.0, 0.1, gate_thr=30.0,
                       gate_atten=0.1, gate_iters=60, x0_mode="rest")
u_comp = r / (0.1 * G_DC)
got3 = interior(U3).mean()
fails += report("gate compensation", info3["gate_converged"]
                and abs(got3 - u_comp) / u_comp < 1e-3,
                f"interior u = {got3:.4f}, expected r/(a*g) = {u_comp:.4f} "
                f"(ungated would be {r/G_DC:.2f})")

# ---- 4. gate honesty: oscillatory threshold must be flagged ---------------
# thr = 3 sits between the supra-threshold optimum (2.5) and the attenuated
# one (25): the linearization has no fixed point and the gate pattern flips
# forever. The tool must SAY so.
U4, info4 = synthesize(toy(), R, 40.0, 0.0, 0.0, 0.1, gate_thr=3.0,
                       gate_atten=0.1, gate_iters=60, x0_mode="rest")
fails += report("gate honesty", not info4["gate_converged"],
                f"non-convergence correctly reported "
                f"(outer iters {info4['gate_outer_iters']}, "
                f"interior u ended at {interior(U4).mean():.3f})")

# ---- 5. offset frame ------------------------------------------------------
mod5 = toy(uOff=5.0, yOff=0.5)
R5 = np.full((T, 1), 1.0)
U5, _ = synthesize(mod5, R5, 40.0, 0.0, 0.0, 0.1, 0.0, 0.1, 0, "rest")
u_star5 = 5.0 + (1.0 - 0.5) / G_DC
got5 = interior(U5).mean()
fails += report("offset steady state", abs(got5 - u_star5) / u_star5 < 1e-3,
                f"interior u = {got5:.4f} raw, analytic uOff + (r-yOff)/g = {u_star5:.4f}")

# ---- 6. CSV round-trip ----------------------------------------------------
tmp = Path(__file__).parent.parent / "design_choi_selftest_tmp.csv"
write_design_csv(tmp, U3)
rows = tmp.read_text().strip().splitlines()
hdr_ok = rows[0] == "tick,u1"
back = np.array([[float(v) for v in rw.split(",")[1:]] for rw in rows[1:]])
tick_ok = all(int(rw.split(",")[0]) == i + 1 for i, rw in enumerate(rows[1:]))
vals_ok = (back.shape == U3.shape
           and np.max(np.abs(back - np.array([[float(f"{v:.9g}") for v in rr]
                                              for rr in U3]))) == 0.0
           and back.min() >= 0.0 and back.max() <= 40.0)
tmp.unlink()
fails += report("CSV round-trip", hdr_ok and tick_ok and vals_ok,
                f"header '{rows[0]}', {len(rows)-1} rows, values in "
                f"[{back.min():.3g}, {back.max():.3g}]")

print(f"\n{'ALL CHOI-SYNTHESIS TESTS PASS' if fails == 0 else f'{fails} TEST(S) FAILED'}")
sys.exit(1 if fails else 0)
