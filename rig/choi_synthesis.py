"""Offline open-loop stimulus optimization, replicating Choi et al. 2016 (eq. 5).

Choi, Brockmeier, McNiel, von Kraus, Principe & Francis 2016, "Eliciting
naturalistic cortical responses with a sensory prosthesis via optimized
microstimulation," J Neural Eng 13(5):056007. Their controller precomputed an
optimal multichannel stimulus amplitude envelope OFFLINE for each touch
condition:

    minimize    sum_t ||y_d(t) - y(t)||^2  +  mu*||u(t)||^2  +  lam*v(t)^2
    subject to  x(t+1) = A x(t) + B gate(u(t)),   0 <= u(t) <= I_max
    where       gate(u_i) = u_i if u_i >= threshold else atten*u_i
                v(t+1) = (1-a) v(t) + a * sum_i u_i(t),  a = Ts/(tau_lp + Ts)

The gate models the microstimulation threshold ("to prevent the optimization
from relying on ineffectual subthreshold amplitudes" -- their words); it is
handled by sequential linearization B_hat = B*diag(g(u)) with the damped update
z <- beta*z_new + (1-beta)*z, beta = max(0.3, 0.97^k) (their exact schedule).
The lam term penalizes high-amplitude slowly-varying input (tau_lp = 100 ms).

This tool solves the same problem on OUR fitted model (.lti from
export_plant_lti.m, offsets included) and emits a design CSV that
cpp_controller --mode openloop --play delivers verbatim -- the open-loop arm
of the open-vs-closed-loop comparison.

Frames: the optimization runs in RAW command units (mu/lam price actual
injected current; the gate thresholds actual amplitude). The model's centered
coordinates are handled by folding offsets into the constant target term.

Usage:
    python rig\\choi_synthesis.py --model plant.lti --reference ref_touch.csv \
        --umax 25 --mu 1e-9 --gate-threshold 8 --gate-atten 0.1 \
        --out design_choi.csv --report

Numpy-only by design (same dependency policy as the rest of rig/).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

MAX_DENSE_BYTES = 500 * 1024 * 1024


# ---------------------------------------------------------------------------
# Model / reference loading
# ---------------------------------------------------------------------------

class Model:
    def __init__(self, A, B, C, D, Ts, uOff, yOff):
        self.A, self.B, self.C, self.D = A, B, C, D
        self.Ts = Ts
        self.uOff, self.yOff = uOff, yOff
        self.n, self.m, self.p = A.shape[0], B.shape[1], C.shape[0]


def load_lti(path: Path) -> Model:
    """Strictly-ordered .lti parser + optional trailing uOffset/yOffset rows."""
    toks = []
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
    uOff, yOff = np.zeros(m), np.zeros(p)
    while i < len(toks):
        key = nxt()
        if key == "uOffset":
            uOff = np.array([float(nxt()) for _ in range(m)])
        elif key == "yOffset":
            yOff = np.array([float(nxt()) for _ in range(p)])
        else:
            break

    for name, M in (("A", A), ("B", B), ("C", C), ("D", D),
                    ("uOffset", uOff), ("yOffset", yOff)):
        if not np.all(np.isfinite(M)):
            raise SystemExit(f"FAIL: non-finite entries in {name} of {path}")
    sr = np.max(np.abs(np.linalg.eigvals(A)))
    if sr >= 1.0:
        raise SystemExit(f"FAIL: model A is unstable (spectral radius {sr:.6f} >= 1); "
                         f"A^k in the prediction matrix diverges. Refit the model.")
    return Model(A, B, C, D, Ts, uOff, yOff)


def load_reference(path: Path, p: int) -> np.ndarray:
    """Reference CSV (tick,r1..rK rows; build_touch_reference.py convention).

    Returns [T x p] raw feature units. More columns than p: first p are used
    (with a warning). Fewer: error.
    """
    rows = Path(path).read_text().strip().splitlines()
    hdr = rows[0].split(",")
    ncols = len(hdr) - 1
    if ncols < p:
        raise SystemExit(f"FAIL: reference has {ncols} columns but the model has p={p} outputs.")
    if ncols > p:
        print(f"WARNING: reference has {ncols} columns; using the first {p} "
              f"(model output order).")
    R = np.array([[float(v) for v in r.split(",")[1:p + 1]] for r in rows[1:]])
    if not np.all(np.isfinite(R)):
        raise SystemExit("FAIL: non-finite values in the reference.")
    return R


# ---------------------------------------------------------------------------
# Stacked prediction / penalty operators
# ---------------------------------------------------------------------------

def markov_G(mod: Model, T: int) -> np.ndarray:
    """Block-lower-triangular [pT x mT]: y(t) = sum_{j<=t} H[t-j] u(j).

    H[0] = D (direct term; 0 for our strictly-proper fits), H[k] = C A^{k-1} B.
    """
    n, m, p = mod.n, mod.m, mod.p
    need = p * T * m * T * 8
    if need > MAX_DENSE_BYTES:
        raise SystemExit(f"FAIL: dense G would need {need/1e6:.0f} MB (> "
                         f"{MAX_DENSE_BYTES/1e6:.0f} MB). Shorten T or reduce channels.")
    H = np.empty((T, p, m))
    H[0] = mod.D
    AkB = mod.B.copy()
    for k in range(1, T):
        H[k] = mod.C @ AkB
        AkB = mod.A @ AkB
    G = np.zeros((p * T, m * T))
    for t in range(T):
        for j in range(t + 1):
            G[t * p:(t + 1) * p, j * m:(j + 1) * m] = H[t - j]
    return G


def free_F(mod: Model, T: int) -> np.ndarray:
    """[pT x n]: free response rows C A^t (t = 0..T-1, matching markov_G's clock)."""
    F = np.empty((mod.p * T, mod.n))
    Ak = np.eye(mod.n)
    for t in range(T):
        F[t * mod.p:(t + 1) * mod.p] = mod.C @ Ak
        Ak = mod.A @ Ak
    return F


def lowpass_L(T: int, m: int, a: float) -> np.ndarray:
    """[T x mT] map U -> v, v(t) = sum_{j<=t} a (1-a)^(t-j) * sum_i u_i(j)."""
    ks = np.arange(T)
    col = a * (1.0 - a) ** ks                       # a(1-a)^k, k = row - col >= 0
    Lsc = np.zeros((T, T))
    for t in range(T):
        Lsc[t, :t + 1] = col[:t + 1][::-1]
    return np.kron(Lsc, np.ones((1, m)))


def rest_state(mod: Model) -> np.ndarray:
    """Centered state at raw u = 0 (stim off): x = (I - A)^-1 B (-uOff)."""
    return np.linalg.solve(np.eye(mod.n) - mod.A, mod.B @ (-mod.uOff))


# ---------------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------------

def power_iteration(H: np.ndarray, iters: int = 200) -> float:
    """Largest eigenvalue estimate; over-estimating is the safe direction
    (same convention as cpp_controller/qp_solver.hpp)."""
    v = np.ones(H.shape[0])
    v /= np.linalg.norm(v)
    lam = 1.0
    for _ in range(iters):
        w = H @ v
        nw = np.linalg.norm(w)
        if nw <= 0:
            return 1.0
        lam = nw
        v = w / nw
    return lam * 1.01


def solve_box_fista(H, q, ub, U0, Lip, max_iters=3000, tol=1e-9):
    """min 0.5 U'H U + q'U  s.t. 0 <= U <= ub. Every iterate feasible, so early
    termination is always safe (the qp_solver.hpp property)."""
    U = np.clip(U0, 0.0, ub)
    y = U.copy()
    t = 1.0
    for _ in range(max_iters):
        grad = H @ y + q
        U_new = np.clip(y - grad / Lip, 0.0, ub)
        step = np.max(np.abs(U_new - U))
        t_new = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
        y = U_new + ((t - 1.0) / t_new) * (U_new - U)
        U, t = U_new, t_new
        if step < tol:
            break
    return U


def synthesize(mod: Model, R: np.ndarray, umax: float, mu: float, lam: float,
               tau_lp: float, gate_thr: float, gate_atten: float,
               gate_iters: int, x0_mode: str, gate_tol: float = 1e-6):
    """Returns (U [T x m], info dict). See module docstring for the problem."""
    T = R.shape[0]
    m, p = mod.m, mod.p
    mT = m * T

    G = markov_G(mod, T)
    F = free_F(mod, T)
    x0 = rest_state(mod) if x0_mode == "rest" else np.zeros(mod.n)

    # Constant target in centered-output space, raw-U decision variable:
    # y_raw = yOff + F x0 + G_g U - G Uoff  =>  d = R - yOff - F x0 + G Uoff
    Uoff = np.tile(mod.uOff, T)
    d = R.ravel() - np.tile(mod.yOff, T) - F @ x0 + G @ Uoff

    K0 = G.T @ G                     # one gemm, ever
    c0 = G.T @ d                     # one gemv, ever
    a = mod.Ts / (tau_lp + mod.Ts)
    LtL = None
    lam_LtL = 0.0
    if lam > 0:
        L = lowpass_L(T, m, a)
        LtL = L.T @ L
        lam_LtL = power_iteration(LtL)

    lam_K0 = power_iteration(K0)
    ub = np.full(mT, umax)

    def build(gvec):
        # G_g = G diag(g): H = 2(gg' * K0 + mu I + lam L'L), q = -2 (g * c0).
        # Elementwise scaling of precomputed blocks -- no gemm per iteration.
        # The Lipschitz bound scales with max(g)^2 (lmax(Dg K0 Dg) <=
        # max(g)^2 lmax(K0)); using the ungated bound for a fully-attenuated
        # subproblem would slow FISTA by 1/atten^2.
        Hm = 2.0 * (np.outer(gvec, gvec) * K0)
        Hm[np.diag_indices_from(Hm)] += 2.0 * mu
        if LtL is not None:
            Hm += 2.0 * lam * LtL
        Lip_g = 2.0 * (float(np.max(gvec)) ** 2 * lam_K0 + mu + lam * lam_LtL)
        return Hm, -2.0 * (gvec * c0), Lip_g

    g = np.ones(mT)
    Hm, q, Lip = build(g)
    U = solve_box_fista(Hm, q, ub, np.zeros(mT), Lip)

    def true_objective(Uv):
        # The ACTUAL nonconvex objective, gate applied elementwise -- used only
        # to tie-break boundary 2-cycles, never inside the convex solves.
        gated = np.where(Uv >= gate_thr, Uv, gate_atten * Uv)
        err_t = d - G @ gated
        J = err_t @ err_t + mu * (Uv @ Uv)
        if LtL is not None:
            J += lam * ((LtL @ Uv) @ Uv)
        return J

    gate_converged = True
    boundary_entries = 0
    outer_used = 0
    if gate_thr > 0:
        gate_converged = False
        g_prev = None
        U_prev = None
        boundary_cap = max(2 * m, int(np.ceil(0.05 * mT)))
        for k in range(gate_iters):
            outer_used = k + 1
            g_new = np.where(U >= gate_thr, 1.0, gate_atten)

            # 2-cycle detection: entries whose two branch optima straddle the
            # threshold flip forever (the gate is discontinuous there; Choi's
            # damping cannot settle them). A SMALL such set is a boundary
            # phenomenon: tie-break those entries on the TRUE objective and
            # accept. A large set means the linearization has no fixed point
            # for this problem -- keep iterating and report non-convergence.
            if g_prev is not None and np.array_equal(g_new, g_prev) \
                    and not np.array_equal(g_new, g):
                n_flip = int(np.sum(g_new != g))
                if n_flip <= boundary_cap:
                    if true_objective(U_prev) < true_objective(U):
                        U = U_prev
                    boundary_entries = n_flip
                    gate_converged = True
                    break

            Hm, q, Lip = build(g_new)
            U_new = solve_box_fista(Hm, q, ub, U.copy(), Lip)
            beta = max(0.3, 0.97 ** k)               # Choi's damping schedule
            U_damped = np.clip(beta * U_new + (1.0 - beta) * U, 0.0, umax)
            # Relative step tolerance: commands are uA-scale; 1e-6 relative is
            # far beyond stimulator resolution.
            tol_eff = gate_tol * max(1.0, float(np.max(np.abs(U))))
            done = (np.max(np.abs(U_damped - U)) < tol_eff
                    and np.array_equal(g_new, g))
            U_prev, g_prev = U, g
            U, g = U_damped, g_new
            if done:
                gate_converged = True
                break

    gated_final = np.where(U >= gate_thr, U, gate_atten * U) if gate_thr > 0 else U
    y_pred = np.tile(mod.yOff, T) + F @ x0 + G @ gated_final - G @ Uoff
    err = R.ravel() - y_pred
    info = {
        "T": T, "m": m, "p": p, "alpha": a,
        "track_cost": float(err @ err),
        "mu_cost": float(mu * (U @ U)),
        "lam_cost": float(lam * ((LtL @ U) @ U)) if LtL is not None else 0.0,
        "track_rms": float(np.sqrt(np.mean(err ** 2))),
        "n_active": int(np.sum(U >= max(gate_thr, 1e-12))),
        "n_subthr": int(np.sum((U > 1e-9) & (U < gate_thr))) if gate_thr > 0 else 0,
        "gate_converged": gate_converged,
        "gate_outer_iters": outer_used,
        "boundary_entries": boundary_entries,
        "u_max": float(U.max()) if mT else 0.0,
    }
    return U.reshape(T, m), info


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_design_csv(path: Path, U: np.ndarray) -> None:
    """tick,u1..uM, 1-based, %.9g -- byte-format of write_excitation_csv.m, so
    cpp_controller --play and validate_impulse_design.py accept it unchanged."""
    m = U.shape[1]
    with open(path, "w", newline="") as f:
        f.write("tick," + ",".join(f"u{i+1}" for i in range(m)) + "\n")
        for t, row in enumerate(U, start=1):
            f.write(str(t) + "," + ",".join(f"{v:.9g}" for v in row) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help=".lti plant (export_plant_lti.m)")
    ref = ap.add_mutually_exclusive_group(required=True)
    ref.add_argument("--reference", help="per-tick reference CSV (tick,r1..)")
    ref.add_argument("--target", type=float, help="constant raw-unit reference")
    ap.add_argument("--ticks", type=int, default=0,
                    help="horizon T (default: reference length; required with --target)")
    ap.add_argument("--umax", type=float, default=40.0, help="I_max (Choi: max probing amp)")
    ap.add_argument("--mu", type=float, default=1e-9,
                    help="quadratic input penalty (Choi's mu; tiny default for conditioning)")
    ap.add_argument("--lam", type=float, default=0.0,
                    help="low-passed total-current penalty (Choi's lambda)")
    ap.add_argument("--tau-lp", type=float, default=0.1,
                    help="low-pass time constant, s (Choi: 100 ms)")
    ap.add_argument("--gate-threshold", type=float, default=0.0,
                    help="stim threshold in command units; 0 disables the gate")
    ap.add_argument("--gate-atten", type=float, default=0.1,
                    help="subthreshold attenuation a in (0,1] (Choi: 0.1 or 0.2)")
    ap.add_argument("--gate-iters", type=int, default=60)
    ap.add_argument("--x0", choices=["rest", "mean"], default="rest",
                    help="initial state: raw-rest (replay starts stim-off) or capture mean")
    ap.add_argument("--u-offset", type=float, nargs="+", default=None,
                    help="override model uOffset (older .lti files carry none)")
    ap.add_argument("--y-offset", type=float, nargs="+", default=None,
                    help="override model yOffset")
    ap.add_argument("--out", required=True, help="design CSV to write")
    ap.add_argument("--report", action="store_true", help="print objective breakdown")
    args = ap.parse_args()

    mod = load_lti(Path(args.model))
    if args.u_offset is not None:
        if len(args.u_offset) != mod.m:
            raise SystemExit(f"FAIL: --u-offset needs {mod.m} values")
        mod.uOff = np.array(args.u_offset, dtype=float)
    if args.y_offset is not None:
        if len(args.y_offset) != mod.p:
            raise SystemExit(f"FAIL: --y-offset needs {mod.p} values")
        mod.yOff = np.array(args.y_offset, dtype=float)

    if args.reference:
        R = load_reference(Path(args.reference), mod.p)
        if args.ticks > 0:
            if args.ticks <= R.shape[0]:
                R = R[:args.ticks]
            else:   # hold last row, same convention as build_reference_stack
                R = np.vstack([R, np.tile(R[-1], (args.ticks - R.shape[0], 1))])
    else:
        if args.ticks <= 0:
            raise SystemExit("FAIL: --target needs --ticks")
        R = np.full((args.ticks, mod.p), args.target, dtype=float)

    # The rectified-feature signature: large positive DC in the reference but a
    # zero-offset model means the .lti predates the 2026-08-20 offset export
    # and the optimizer would massively overdrive trying to reach the DC level.
    if np.all(mod.yOff == 0) and R.size and abs(R.mean()) > 10 * (R.std() + 1e-30):
        print("WARNING: reference has a large DC component but the model carries "
              "yOffset = 0. If this model was fitted on mean-removed data "
              "(fit_sysid_from_capture), re-export the .lti with offsets "
              "(export_plant_lti) or pass --y-offset / --u-offset explicitly.")

    print(f"Model: n={mod.n} m={mod.m} p={mod.p} Ts={mod.Ts:.6g} "
          f"uOff={np.array2string(mod.uOff, precision=4)} "
          f"yOff={np.array2string(mod.yOff, precision=4)}")
    print(f"Horizon T={R.shape[0]} ticks ({R.shape[0]*mod.Ts*1e3:.0f} ms), umax={args.umax}, "
          f"mu={args.mu:g}, lam={args.lam:g} (tau_lp={args.tau_lp:g} s), "
          f"gate thr={args.gate_threshold:g} atten={args.gate_atten:g}, x0={args.x0}")

    U, info = synthesize(mod, R, args.umax, args.mu, args.lam, args.tau_lp,
                         args.gate_threshold, args.gate_atten, args.gate_iters,
                         args.x0)

    write_design_csv(Path(args.out), U)
    print(f"Wrote {args.out}: {U.shape[0]} ticks x {U.shape[1]} channels, "
          f"u in [0, {info['u_max']:.4g}], {info['n_active']} active entries")
    if args.gate_threshold > 0:
        state = "CONVERGED" if info["gate_converged"] else \
                "DID NOT CONVERGE (gate pattern still changing at iteration cap)"
        print(f"Gate: {state} after {info['gate_outer_iters']} outer iterations; "
              f"{info['n_subthr']} entries below threshold"
              + (f"; {info['boundary_entries']} boundary entries tie-broken on "
                 f"the true objective" if info["boundary_entries"] else "") + ".")
        if not info["gate_converged"]:
            print("*** Treat this design as suspect: re-run with more --gate-iters "
                  "or adjust the threshold. ***")

    if args.report:
        tc, mc, lc = info["track_cost"], info["mu_cost"], info["lam_cost"]
        print("\nObjective breakdown at the solution:")
        print(f"  tracking : {tc:.6g}   (rms {info['track_rms']:.6g} per sample)")
        print(f"  mu term  : {mc:.6g}")
        print(f"  lam term : {lc:.6g}")
        if tc > 0 and (mc + lc) > 10 * tc:
            print("WARNING: input penalties exceed the tracking term by >10x -- "
                  "the same scale trap as rWeight (features are volts ~1e-3, "
                  "commands are ~10). The design is probably over-suppressed; "
                  "lower --mu / --lam.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
