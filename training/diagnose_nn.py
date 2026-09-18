"""diagnose_nn -- why the NN inverse policy failed on acute #2 (2026-09-10).

Reproducible, all-local, ~10-15 min on the RTX 4090. Writes
    day_2026-09-10/analysis/_nn_diag.json
    day_2026-09-10/analysis/nn_diag_ladder.png   (R2 by arch x history x mode, both acutes)
    day_2026-09-10/analysis/nn_diag_snr.png      (smoothing / record-length / z vs sqrt(N))
    day_2026-09-10/analysis/nn_diag_clone.png    (behaviour cloning of the MPC per site)

Sections (each can be skipped with --skip):
  ladder   task 1+2  inverse & forward R2 ladders on opfit12 (09-10), opfit (08-31),
                     opfit10/11 (09-10, linear only)
  snr      task 3    forward R2 vs y-smoothing and record length; pulse z vs sqrt(N)
                     on the rnd1 probe; MI-implied inverse R2 bound
  alt      task 4    forward-model + optimisation (certainty-equivalent) vs direct
                     inverse; behaviour cloning of the MPC from the arm captures
  figs     task 5

Training reproduces train.py's loop programmatically (same Adam/lr/wd/batch,
contiguous 70/30 split, per-column normalisation, causal u(k)->y(k+1), best-
checkpoint selection on validation R2). ONE deliberate deviation: the GRU is
trained with the same truncated BPTT (hidden state reset every --seq-len ticks,
exactly as train.py resets h=None per chunk) but the independent chunks are
batched through torch.nn.GRU (cuDNN) instead of a per-tick GRUCell loop --
the same model class (one GRU layer + linear head), the same loss, ~100x
faster. Validation is evaluated over the whole held-out tail with carried
state, as train.py does.

    python diagnose_nn.py                # everything
    python diagnose_nn.py --quick        # fewer epochs, for iteration
    python diagnose_nn.py --skip ladder  # reuse a previous ladder from the JSON
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DAY = REPO / "day_2026-09-10"
ANA = DAY / "analysis"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(ANA / "scripts"))

import architectures                      # noqa: E402
import data as datamod                    # noqa: E402
import deckkit as dk                      # noqa: E402

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT_JSON = ANA / "_nn_diag.json"
SKIP = 50                                  # trk_common convention
UMIN, UMAX = 0.0, 30.0

CAPS = {
    "opfit12": REPO / "capture_rig_runopfit12.csv",   # 09-10, pairs 4,6 PRBS 8<->22, ctrl y64
    "opfit11": REPO / "capture_rig_runopfit11.csv",
    "opfit10": REPO / "capture_rig_runopfit10.csv",
    "opfit":   REPO / "capture_rig_runopfit.csv",     # 08-31, pairs 1,4 PRBS 10<->30, ctrl y8
    "rnd1":    REPO / "capture_rig_runrnd1.csv",
}
DAYCFG = {
    "opfit12": dict(day="2026-09-10", pairs=[4, 6], ctrl=64),
    "opfit11": dict(day="2026-09-10", pairs=[1, 4], ctrl=64),            # PRBS 10<->30
    "opfit10": dict(day="2026-09-10", pairs=list(range(1, 9)), ctrl=64),  # all 8 pairs PRBS 10<->30
    "opfit":   dict(day="2026-08-31", pairs=[1, 4], ctrl=8),
}

ARCH_COLOR = {"linear": dk.INK_2, "mlp": dk.CAT[3], "residual_mlp": dk.CAT[6],
              "gru": dk.COLOR["nn"]}
ARCH_LABEL = {"linear": "linear", "mlp": "MLP 64-64", "residual_mlp": "residual MLP",
              "gru": "GRU-32"}


# ---------------------------------------------------------------------------
# training core (train.py's loop, as functions)
# ---------------------------------------------------------------------------
def r2_per_output(pred: np.ndarray, Y: np.ndarray) -> np.ndarray:
    err = pred - Y
    ss_res = (err ** 2).sum(axis=0)
    ss_tot = ((Y - Y.mean(axis=0)) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ss_tot > 1e-12, 1.0 - ss_res / ss_tot, np.nan)


class GruSeq(nn.Module):
    """Same model as architectures.GruPolicy (one GRU layer + linear head),
    evaluated over sequences with cuDNN instead of a per-tick GRUCell loop."""

    def __init__(self, in_dim, out_dim, hidden=32):
        super().__init__()
        self.gru = nn.GRU(in_dim, hidden, batch_first=True)
        self.head = nn.Linear(hidden, out_dim)

    def forward(self, x, h=None):           # x [B, T, F]
        o, h = self.gru(x, h)
        return self.head(o), h


def fit(Xtr, Ytr, Xv, Yv, arch: str, epochs: int, hidden=64, seed=0,
        seq_len=100, chunk_batch=8, batch=256, lr=1e-3, wd=1e-4,
        select_cols=None, verbose=False):
    """Train one model; return dict(r2 per output at the best checkpoint, model).

    Best checkpoint = highest mean validation R2 over `select_cols` (default:
    nanmean over all outputs, as train.py)."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    t0 = time.time()
    in_dim, out_dim = Xtr.shape[1], Ytr.shape[1]
    recurrent = arch == "gru"
    if recurrent:
        model = GruSeq(in_dim, out_dim, hidden=hidden).to(DEVICE)
    else:
        kw = {}
        if arch == "mlp":
            kw["hidden"] = (hidden, hidden)
        elif arch == "residual_mlp":
            kw["hidden"], kw["blocks"] = hidden, 2
        model = architectures.build(arch, in_dim, out_dim, **kw).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    lossf = nn.MSELoss()
    Xtr_t = torch.tensor(Xtr, device=DEVICE)
    Ytr_t = torch.tensor(Ytr, device=DEVICE)
    Xv_t = torch.tensor(Xv, device=DEVICE)
    if recurrent:
        n_chunks = (Xtr_t.shape[0] - 1) // seq_len
        Xc = Xtr_t[:n_chunks * seq_len].reshape(n_chunks, seq_len, in_dim)
        Yc = Ytr_t[:n_chunks * seq_len].reshape(n_chunks, seq_len, out_dim)

    def evaluate():
        model.eval()
        with torch.no_grad():
            if recurrent:
                pred = model(Xv_t[None])[0][0].cpu().numpy()
            else:
                pred = model(Xv_t).cpu().numpy()
        model.train()
        return r2_per_output(pred, Yv), pred

    best_score, best_r2, best_state, best_pred = -1e30, None, None, None
    every = max(1, epochs // 20)
    for epoch in range(1, epochs + 1):
        if recurrent:
            perm = torch.randperm(n_chunks, device=DEVICE)
            for i in range(0, n_chunks, chunk_batch):
                idx = perm[i:i + chunk_batch]
                opt.zero_grad()
                out, _ = model(Xc[idx])
                loss = lossf(out, Yc[idx])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
        else:
            perm = torch.randperm(Xtr_t.shape[0], device=DEVICE)
            for i in range(0, len(perm), batch):
                idx = perm[i:i + batch]
                opt.zero_grad()
                loss = lossf(model(Xtr_t[idx]), Ytr_t[idx])
                loss.backward()
                opt.step()
        if epoch % every == 0 or epoch == epochs:
            r2, pred = evaluate()
            score = float(np.nanmean(r2 if select_cols is None else r2[select_cols]))
            if not np.isfinite(score):
                score = -1e29
            if score > best_score:
                best_score, best_r2, best_pred = score, r2, pred
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            if verbose:
                print(f"    epoch {epoch:4d} val R2 {score:+.4f}")
    model.load_state_dict(best_state)
    model.eval()
    return {"r2": best_r2, "pred": best_pred, "model": model,
            "secs": time.time() - t0, "epochs": epochs}


def prepare(cap_key: str, mode: str, history: int, use_channels=None):
    """(Xtr, Ytr, Xv, Yv, ds) exactly as train.py builds them."""
    cap = datamod.load_capture(CAPS[cap_key])
    ds = datamod.build_dataset([cap], mode=mode, history=history, use_channels=use_channels)
    Xn, Yn = ds.normalised()
    Xtr, Ytr, Xv, Yv = datamod.split_train_val(Xn, Yn, 0.7)
    return Xtr, Ytr, Xv, Yv, ds


# ---------------------------------------------------------------------------
# task 1+2: ladders
# ---------------------------------------------------------------------------
def run_ladder(args) -> dict:
    ep_fast = 30 if args.quick else 120
    ep_gru = 10 if args.quick else args.gru_epochs
    rows, models = [], {}

    def one(cap_key, mode, arch, history, channels_desc, use_channels, report):
        cfg = DAYCFG[cap_key]
        Xtr, Ytr, Xv, Yv, ds = prepare(cap_key, mode, history, use_channels)
        if mode == "inverse":
            cols = [p - 1 for p in cfg["pairs"]]
            names = [f"u{p}" for p in cfg["pairs"]]
        else:
            cols = [cfg["ctrl"] - 1]
            names = [f"y{cfg['ctrl']}"]
        ep = ep_gru if arch == "gru" else ep_fast
        hidden = 32 if arch == "gru" else 64
        res = fit(Xtr, Ytr, Xv, Yv, arch, ep, hidden=hidden, select_cols=cols)
        r2 = res["r2"]
        row = {"capture": cap_key, "day": cfg["day"], "mode": mode, "arch": arch,
               "history": history, "inputs": channels_desc,
               "n_train": int(Xtr.shape[0]), "n_val": int(Xv.shape[0]),
               "epochs": ep, "secs": round(res["secs"], 1),
               "r2": {n: (None if not np.isfinite(r2[c]) else round(float(r2[c]), 4))
                      for n, c in zip(names, cols)}}
        if mode == "forward":
            fin = np.where(np.isfinite(r2), r2, -9)
            row["r2_best_channel"] = {"channel": int(fin.argmax()) + 1,
                                      "r2": round(float(fin.max()), 4)}
        row["r2_report_mean"] = round(float(np.nanmean(r2[cols])), 4)
        if arch == "linear":       # closed-form ridge on the same split: convergence check
            row["r2_ridge_closed_form"] = {
                n: round(ridge_r2(np.concatenate([Xtr, Xv]), np.concatenate([Ytr, Yv])[:, c]), 4)
                for n, c in zip(names, cols)}
        rows.append(row)
        key = (cap_key, mode, arch, history, channels_desc)
        models[key] = (res["model"], ds)
        print(f"  {cap_key:8s} {mode:8s} {arch:13s} h={history:<3d} {channels_desc:9s} "
              f"R2 {row['r2']}  ({res['secs']:.0f}s)")
        return row

    archs_full = ["linear", "mlp", "residual_mlp", "gru"]
    print("[ladder] opfit12 (2026-09-10) inverse, control channel only")
    for arch in archs_full:
        for h in (1, 5, 25):
            one("opfit12", "inverse", arch, h, "y64", [64], ["u4", "u6"])
    print("[ladder] opfit12 inverse, all 64 channels")
    for arch in archs_full:
        for h in (1, 5):
            one("opfit12", "inverse", arch, h, "all64", None, ["u4", "u6"])
    print("[ladder] opfit12 forward (u4,u6 -> y), ceiling check")
    for arch in archs_full:
        for h in (1, 5, 25):
            one("opfit12", "forward", arch, h, "u4,u6", [4, 6], ["y64"])
    print("[ladder] opfit (2026-08-31) inverse (y8) and forward (u1,u4 -> y)")
    for arch in ["linear", "mlp", "gru"]:
        for h in (1, 5, 25):
            one("opfit", "inverse", arch, h, "y8", [8], ["u1", "u4"])
            one("opfit", "forward", arch, h, "u1,u4", [1, 4], ["y8"])
    print("[ladder] opfit10/11 (09-10 operating points), linear only")
    for cap in ("opfit10", "opfit11"):
        pairs = DAYCFG[cap]["pairs"]
        for h in (1, 5, 25):
            one(cap, "inverse", "linear", h, "y64", [64], [f"u{p}" for p in pairs])
            one(cap, "forward", "linear", h, ",".join(f"u{p}" for p in pairs), pairs, ["y64"])
    return {"rows": rows, "_models": models}


# ---------------------------------------------------------------------------
# task 3: SNR / data budget
# ---------------------------------------------------------------------------
def ridge_r2(X, y, lam=1e-3):
    """Closed-form ridge, contiguous 70/30, R2 on the held-out tail."""
    n = X.shape[0]
    cut = int(0.7 * n)
    Xtr, Xv = X[:cut], X[cut:]
    ytr, yv = y[:cut], y[cut:]
    mx, sx = Xtr.mean(0), Xtr.std(0) + 1e-12
    my = ytr.mean()
    A = (Xtr - mx) / sx
    b = ytr - my
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ b)
    pred = ((Xv - mx) / sx) @ w + my
    return float(1 - ((yv - pred) ** 2).sum() / ((yv - yv.mean()) ** 2).sum())


def moving_avg(y, w):
    if w <= 1:
        return y
    c = np.cumsum(np.insert(y, 0, 0.0))
    out = np.empty_like(y)
    out[w - 1:] = (c[w:] - c[:-w]) / w
    for i in range(min(w - 1, len(y))):          # causal ramp-in
        out[i] = y[:i + 1].mean()
    return out


def run_snr(args, ladder_rows) -> dict:
    import rank_common as rc
    out = {}
    # (a) forward R2 vs smoothing and record length, opfit12, linear h25
    cap = datamod.load_capture(CAPS["opfit12"])
    U, Y = cap.U[:, [3, 5]], cap.Y[:, 63]
    H = 25
    Xh = datamod.stack_history(U, H)
    grid = {}
    for frac in (0.25, 0.5, 0.75, 1.0):
        n = int(frac * Xh.shape[0])
        row = {}
        for w in (1, 3, 5, 10, 20):
            ys = moving_avg(Y, w)[H - 1:]
            row[str(w)] = round(ridge_r2(Xh[:n], ys[:n]), 4)
        grid[str(frac)] = row
        print(f"  [snr] record {int(frac*100):3d}%  R2 by smoothing {row}")
    out["forward_r2_grid"] = {"history": H, "rows": "record fraction", "cols": "moving-average ticks",
                              "grid": grid}
    # also the inverse (y64 hist 25 -> u4) under the same smoothing, for the record
    inv = {}
    for w in (1, 3, 5, 10, 20):
        ys = moving_avg(Y, w)
        Xy = datamod.stack_history(ys[:, None], H)
        inv[str(w)] = {"u4": round(ridge_r2(Xy, U[H - 1:, 0]), 4),
                       "u6": round(ridge_r2(Xy, U[H - 1:, 1]), 4)}
    out["inverse_r2_vs_smoothing"] = inv
    print(f"  [snr] inverse (ridge h25) vs smoothing: {inv}")

    # (a') baseline drift: held-out mean shift, and forward R2 after removing a slow
    # (1000-tick) moving baseline from y -- what a high-passed feature would give.
    drift = {}
    for key in ("opfit12", "opfit"):
        cfg = DAYCFG[key]
        c_ = datamod.load_capture(CAPS[key])
        Uk, yk = c_.U[:, [p - 1 for p in cfg["pairs"]]], c_.Y[:, cfg["ctrl"] - 1]
        cut = int(0.7 * len(yk))
        base = np.convolve(yk, np.ones(1001) / 1001, mode="same")
        Xk = datamod.stack_history(Uk, H)
        # per-state means at lag 2 (additivity check)
        states = {}
        L = 2
        for a in np.unique(Uk[:, 0]):
            for b in np.unique(Uk[:, 1]):
                sel = (Uk[:len(yk) - L, 0] == a) & (Uk[:len(yk) - L, 1] == b)
                states[f"({a:g},{b:g})"] = round(float(yk[L:][sel].mean() * 1e6), 2)
        drift[key] = {
            "ctrl_channel": cfg["ctrl"],
            "train_mean_uV": round(float(yk[:cut].mean() * 1e6), 2),
            "val_mean_uV": round(float(yk[cut:].mean() * 1e6), 2),
            "train_sd_uV": round(float(yk[:cut].std() * 1e6), 2),
            "val_sd_uV": round(float(yk[cut:].std() * 1e6), 2),
            "mean_shift_in_val_sd": round(float((yk[:cut].mean() - yk[cut:].mean()) / yk[cut:].std()), 3),
            "forward_r2_h25_raw": round(ridge_r2(Xk, yk[H - 1:]), 4),
            "forward_r2_h25_baseline_removed": round(ridge_r2(Xk, (yk - base)[H - 1:]), 4),
            "state_means_uV_lag2": states,
        }
        print(f"  [snr] drift {key}: mean {drift[key]['train_mean_uV']}->{drift[key]['val_mean_uV']} uV "
              f"({drift[key]['mean_shift_in_val_sd']:+.2f} SD); fwd R2 raw {drift[key]['forward_r2_h25_raw']:+.3f} "
              f"-> baseline-removed {drift[key]['forward_r2_h25_baseline_removed']:+.3f}; states {states}")
    out["drift"] = drift

    # (b) pulse z vs number of trials on rnd1 (channel 64 = control channel)
    Z, A = rc.pulse_response_matrix()
    u, Yr = rc.capture("capture_rig_runrnd1.csv")
    rng = np.random.default_rng(20260918)
    c = 63
    y = Yr[:, c]
    Ns = [10, 20, 50, 100, 200, 300, 500]
    pulse = {}
    for p in range(8):
        col = u[:, p]
        rise = np.flatnonzero((col[1:] > 1e-6) & (col[:-1] <= 1e-6)) + 1
        rise = rise[col[rise] >= 12.9]
        rise = rise[(rise > 10) & (rise < len(u) - 10)]
        post = np.mean([y[rise + k] for k in (1, 2, 3)], axis=0)
        pre = np.mean([y[rise - k] for k in (1, 2, 3)], axis=0)
        d = post - pre                                  # per-trial evoked delta
        # single-trial null: shuffled triggers, same statistic
        fake = rng.integers(10, len(u) - 10, size=4000)
        dn = (np.mean([y[fake + k] for k in (1, 2, 3)], 0)
              - np.mean([y[fake - k] for k in (1, 2, 3)], 0))
        sd1 = float(dn.std())                           # single-event null SD
        zN = {}
        for N in Ns:
            if N > len(rise):
                continue
            vals = []
            for _ in range(40):
                sub = rng.choice(d, size=N, replace=False)
                vals.append(abs(sub.mean()) / (sd1 / np.sqrt(N)))
            zN[N] = float(np.mean(vals))
        # fit z = a sqrt(N)  (least squares through origin)
        ns = np.array(list(zN.keys()), float)
        zs = np.array(list(zN.values()))
        a = float((np.sqrt(ns) * zs).sum() / ns.sum())
        pulse[f"pair{p+1}"] = {
            "n_trials": int(len(rise)),
            "single_event_z": round(abs(d.mean()) / sd1, 3),
            "z_all_trials": round(abs(d.mean()) / (sd1 / np.sqrt(len(rise))), 2),
            "z_rank_common": round(float(Z[p, c]), 2),
            "z_vs_N": {str(int(k)): round(v, 3) for k, v in zN.items()},
            "fit_a": round(a, 4),
            "N_for_z3": int(np.ceil((3.0 / a) ** 2)) if a > 0 else None,
            "delta_uV": round(float(d.mean()) * 1e6, 3),
            "null_sd_single_uV": round(sd1 * 1e6, 3),
        }
        print(f"  [snr] pair {p+1}: {len(rise)} trials, single-event z {pulse[f'pair{p+1}']['single_event_z']:.3f}, "
              f"z(all) {pulse[f'pair{p+1}']['z_all_trials']:.2f}, N for z>=3: {pulse[f'pair{p+1}']['N_for_z3']}")
    out["pulse_z_ch64"] = pulse

    # (c) MI-implied inverse bound from the forward ladder
    def bound(r2f):
        r2f = max(0.0, min(0.999, r2f))
        I = -0.5 * np.log(1 - r2f)                # nats, Gaussian
        return I, 1 - np.exp(-2 * I)
    fwd12 = [r for r in ladder_rows if r["capture"] == "opfit12" and r["mode"] == "forward"]
    best_fwd12 = max((r["r2"]["y64"] or -1) for r in fwd12)
    # all-64-channel forward, h25, best of linear/MLP per channel: sum of per-channel
    # MI (independent-noise bound)
    Xtr, Ytr, Xv, Yv, _ = prepare("opfit12", "forward", 25, [4, 6])
    r2c = np.full(Ytr.shape[1], -1.0)
    for arch in ("linear", "mlp"):
        res = fit(Xtr, Ytr, Xv, Yv, arch, 30 if args.quick else 120)
        r2c = np.maximum(r2c, np.nan_to_num(res["r2"], nan=-1.0))
    r2c = np.clip(r2c, 0, 0.999)
    I_sum = float((-0.5 * np.log(1 - r2c)).sum())
    I1, b1 = bound(best_fwd12)
    out["mi_bound"] = {
        "best_forward_r2_y64": round(best_fwd12, 4),
        "I_y64_nats": round(float(I1), 4),
        "inverse_r2_upper_bound_y64_only": round(float(b1), 4),
        "sum_I_all64_nats_linear_h25": round(I_sum, 4),
        "inverse_r2_upper_bound_all64": round(float(1 - np.exp(-2 * I_sum)), 4),
        "n_channels_r2_gt_0.01": int((r2c > 0.01).sum()),
        "note": "Gaussian identity I = -1/2 ln(1-R2); inverse R2 <= 1 - exp(-2 I). "
                "The all-64 sum assumes independent channel noise, so it is an upper bound on the bound.",
    }
    print(f"  [snr] MI bound: fwd R2(y64) {best_fwd12:.3f} -> inverse R2 <= {b1:.3f}; "
          f"all-64 sum -> <= {out['mi_bound']['inverse_r2_upper_bound_all64']:.3f}")
    return out


# ---------------------------------------------------------------------------
# task 4a: forward model + optimisation vs direct inverse
# ---------------------------------------------------------------------------
def load_ref_and_mpc(run: int):
    import pandas as pd
    d = pd.read_csv(DAY / f"capture_mpc_mixr{run}.csv")
    rf = pd.read_csv(DAY / f"ref_mix_r{run}.csv")
    sched = dk.jload(DAY / f"schedule_mix_r{run}.json")
    n = min(len(d), len(rf))
    u = d[[f"u{k}" for k in range(1, 9)]].to_numpy()[SKIP:n]
    y = d["y64"].to_numpy()[SKIP:n]
    r = rf["r1"].to_numpy()[SKIP:n]
    return u, y, r, sched


def corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / den) if den > 0 else 0.0


def run_alt_forward(args, models) -> dict:
    H = 25
    out = {}
    u_mpc, y_mpc, r, _ = load_ref_and_mpc(1)
    tj = dk.jload(DAY / "tracking_mpc_r1.json")["per_channel"][0]
    out["mpc_r1_measured_r0"] = tj["pearson_lag0"]

    def y64_forward(arch):
        Xtr, Ytr, Xv, Yv, ds = prepare("opfit12", "forward", H, [4, 6])
        res = fit(Xtr[:, :], Ytr[:, [63]], Xv, Yv[:, [63]], arch,
                  30 if args.quick else 150)
        resid_sd = float((res["pred"][:, 0] - Yv[:, 0]).std() * ds.out_std[63])   # volts
        return res["model"], ds, float(res["r2"][0]), resid_sd

    rng = np.random.default_rng(20260918)

    def r_noisy(yhat, r, sd, draws=20):
        """Predicted tracking r once the model's own held-out residual noise is added
        back -- the honest 'what would the rig measure' number."""
        ok = np.isfinite(yhat)
        return float(np.mean([corr(yhat[ok] + rng.normal(0, sd, ok.sum()), r[ok])
                              for _ in range(draws)]))

    def predict(model, ds, U_raw):
        """U_raw [T,2] microamps -> predicted y64 (volts), causal, history H."""
        Un = (U_raw - ds.in_mean) / ds.in_std
        X = datamod.stack_history(Un.astype(np.float32), H)
        with torch.no_grad():
            p = model(torch.tensor(X, device=DEVICE)).cpu().numpy()[:, 0]
        yhat = np.full(U_raw.shape[0], np.nan)
        yhat[H - 1:] = p * ds.out_std[63] + ds.out_mean[63]
        return yhat

    def invert(model, ds, r, iters):
        """Certainty-equivalent open-loop inversion: argmin_u ||f(u)-r||^2, u in [0,30]."""
        T = len(r)
        rn = torch.tensor((r - ds.out_mean[63]) / ds.out_std[63], device=DEVICE, dtype=torch.float32)
        theta = torch.zeros(T, 2, device=DEVICE, requires_grad=True)
        in_mean = torch.tensor(ds.in_mean, device=DEVICE, dtype=torch.float32)
        in_std = torch.tensor(ds.in_std, device=DEVICE, dtype=torch.float32)
        opt = torch.optim.Adam([theta], lr=0.1)
        for p_ in model.parameters():
            p_.requires_grad_(False)
        for it in range(iters):
            opt.zero_grad()
            U = UMIN + (UMAX - UMIN) * torch.sigmoid(theta)
            Un = (U - in_mean) / in_std
            X = Un.unfold(0, H, 1).transpose(1, 2).reshape(-1, 2 * H)   # oldest first
            yhat = model(X)[:, 0]
            loss = ((yhat - rn[H - 1:]) ** 2).mean() + 1e-4 * (U ** 2).mean() / 900
            loss.backward()
            opt.step()
        with torch.no_grad():
            U = (UMIN + (UMAX - UMIN) * torch.sigmoid(theta)).cpu().numpy()
        return U

    res = {}
    for arch in ("linear", "mlp"):
        fm, ds, r2v, resid_sd = y64_forward(arch)
        yhat_mpc = predict(fm, ds, u_mpc[:, [3, 5]])
        ok = np.isfinite(yhat_mpc)
        r_mpc_model = corr(yhat_mpc[ok], r[ok])
        U_opt = invert(fm, ds, r, 60 if args.quick else 400)
        yhat_opt = predict(fm, ds, U_opt)
        r_ce = corr(yhat_opt[ok], r[ok])
        # direct inverse policy (linear h5 and gru h5, y64-only) fed the reference as if it were y64
        direct = {}
        for arch_inv, hist in (("linear", 5), ("mlp", 5), ("gru", 5), ("linear", 25)):
            key = ("opfit12", "inverse", arch_inv, hist, "y64")
            if key not in models:
                continue
            pm, pds = models[key]
            rn = ((r[:, None] - pds.in_mean) / pds.in_std).astype(np.float32)
            X = datamod.stack_history(rn, hist)
            with torch.no_grad():
                xt = torch.tensor(X, device=DEVICE)
                if arch_inv == "gru":
                    pn = pm(xt[None])[0][0].cpu().numpy()
                else:
                    pn = pm(xt).cpu().numpy()
            U_inv = np.clip(pn * pds.out_std + pds.out_mean, UMIN, UMAX)[:, [3, 5]]
            U_full = np.zeros((len(r), 2)); U_full[hist - 1:] = U_inv
            U_full[:hist - 1] = U_inv[0]
            yh = predict(fm, ds, U_full)
            direct[f"{arch_inv}_h{hist}"] = {
                "r_under_forward_model": round(corr(yh[ok], r[ok]), 4),
                "r_with_model_noise": round(r_noisy(yh, r, resid_sd), 4),
                "u4_mean": round(float(U_full[:, 0].mean()), 2), "u4_std": round(float(U_full[:, 0].std()), 2),
                "u6_mean": round(float(U_full[:, 1].mean()), 2), "u6_std": round(float(U_full[:, 1].std()), 2)}
        res[arch] = {
            "forward_val_r2_y64": round(r2v, 4),
            "model_residual_sd_uV": round(resid_sd * 1e6, 2),
            "r_mpc_tape_under_model": round(r_mpc_model, 4),
            "r_mpc_tape_with_model_noise": round(r_noisy(yhat_mpc, r, resid_sd), 4),
            "r_certainty_equivalent_inversion": round(r_ce, 4),
            "r_ce_inversion_with_model_noise": round(r_noisy(yhat_opt, r, resid_sd), 4),
            "u_opt_u4_mean": round(float(U_opt[:, 0].mean()), 2), "u_opt_u4_std": round(float(U_opt[:, 0].std()), 2),
            "u_opt_u6_mean": round(float(U_opt[:, 1].mean()), 2), "u_opt_u6_std": round(float(U_opt[:, 1].std()), 2),
            "charge_uA_ticks_opt": round(float(np.abs(U_opt).sum()), 0),
            "charge_uA_ticks_mpc": round(float(np.abs(u_mpc[:, [3, 5]]).sum()), 0),
            "direct_inverse": direct,
        }
        print(f"  [alt-fwd] {arch}: val R2 {r2v:+.3f} resid {resid_sd*1e6:.1f} uV  MPC tape under model r "
              f"{r_mpc_model:+.3f} (noisy {res[arch]['r_mpc_tape_with_model_noise']:+.3f}; measured "
              f"{out['mpc_r1_measured_r0']:+.3f})  CE inversion r {r_ce:+.3f} (noisy "
              f"{res[arch]['r_ce_inversion_with_model_noise']:+.3f})  u_opt u4 {U_opt[:,0].mean():.1f}+-"
              f"{U_opt[:,0].std():.1f}  direct {direct}")
        res[arch]["_traces"] = {"yhat_opt": yhat_opt, "U_opt": U_opt}
    out["forward_inversion"] = res
    return out


# ---------------------------------------------------------------------------
# task 4b: behaviour cloning of the MPC per site
# ---------------------------------------------------------------------------
W0, W1 = -10, 40         # window relative to event onset (ticks)
PRE, POST = 5, 15        # reference preview fed to the policy (k-5 .. k+15)
FB = 5                   # ticks of measured y64 feedback in variant B


def clone_dataset(run: int):
    u, y, r, sched = load_ref_and_mpc(run)
    period = int(sched["period_ticks"])
    XA, XB, Y, meta = [], [], [], []
    for ev in sched["events"]:
        i0 = int(ev["onset_tick"]) - SKIP
        if i0 + W0 - PRE - FB < 0 or i0 + W1 + POST >= len(y):
            continue
        for k in range(W0, W1):
            t = i0 + k
            prev = r[t - PRE:t + POST] / 1e-4                # reference preview
            tt = np.array([(k - W0) / (W1 - W0)])
            fb = y[t - FB:t] / 1e-4                           # measured feature history
            XA.append(np.concatenate([prev, tt]))
            XB.append(np.concatenate([prev, tt, fb]))
            Y.append(u[t, [3, 5]])
            meta.append((run, ev["event"], ev["site"], k))
    return (np.array(XA, np.float32), np.array(XB, np.float32),
            np.array(Y, np.float32), meta)


def run_clone(args) -> dict:
    sets = {r: clone_dataset(r) for r in (1, 2, 3)}
    out = {"window": [W0, W1], "preview": [PRE, POST], "feedback_ticks": FB, "results": {}}
    ep = 40 if args.quick else 200
    traces = {}
    for variant, xi in (("A_reference_only", 0), ("B_reference_plus_y64", 1)):
        # cross-run: train r1+r2, test r3
        Xtr = np.concatenate([sets[1][xi], sets[2][xi]]); Ytr = np.concatenate([sets[1][2], sets[2][2]])
        Xv, Yv, meta_v = sets[3][xi], sets[3][2], sets[3][3]
        mx, sx = Xtr.mean(0), Xtr.std(0); sx[sx < 1e-9] = 1
        my, sy = Ytr.mean(0), Ytr.std(0); sy[sy < 1e-9] = 1
        Xtr_n, Xv_n = (Xtr - mx) / sx, (Xv - mx) / sx
        Ytr_n, Yv_n = (Ytr - my) / sy, (Yv - my) / sy
        vres = {}
        for arch in ("linear", "mlp"):
            res = fit(Xtr_n, Ytr_n, Xv_n, Yv_n, arch, ep, hidden=64)
            pred = res["pred"] * sy + my
            r2 = res["r2"]
            per_site = {}
            sites = np.array([m[2] for m in meta_v])
            for s in ("LP", "P1", "MP", "P3", "SHAM"):
                sel = sites == s
                per_site[s] = {"u4": round(float(r2_per_output(pred[sel], Yv[sel])[0]), 3),
                               "u6": round(float(r2_per_output(pred[sel], Yv[sel])[1]), 3)}
            # within-run contiguous 70/30 (r3 events) as a second view
            n = Xv.shape[0]; cut = int(0.7 * n)
            res_in = fit(Xv_n[:cut], Yv_n[:cut], Xv_n[cut:], Yv_n[cut:], arch, ep, hidden=64)
            vres[arch] = {"cross_run_r2": {"u4": round(float(r2[0]), 4), "u6": round(float(r2[1]), 4)},
                          "within_r3_r2": {"u4": round(float(res_in["r2"][0]), 4),
                                           "u6": round(float(res_in["r2"][1]), 4)},
                          "per_site_cross_run_r2": per_site,
                          "n_train": int(Xtr.shape[0]), "n_val": int(Xv.shape[0])}
            print(f"  [clone] {variant} {arch}: cross-run R2 u4 {r2[0]:+.3f} u6 {r2[1]:+.3f}  "
                  f"within-r3 u4 {res_in['r2'][0]:+.3f} u6 {res_in['r2'][1]:+.3f}")
            traces[(variant, arch)] = (pred, Yv, meta_v)
        out["results"][variant] = vres
    out["_traces"] = traces
    return out


# ---------------------------------------------------------------------------
# task 5: figures
# ---------------------------------------------------------------------------
def fig_ladder(rows):
    panels = [("opfit12", "inverse", "09-10 inverse: y64 -> u4,u6"),
              ("opfit12", "forward", "09-10 forward: u4,u6 -> y64"),
              ("opfit", "inverse", "08-31 inverse: y8 -> u1,u4"),
              ("opfit", "forward", "08-31 forward: u1,u4 -> y8")]
    archs = ["linear", "mlp", "residual_mlp", "gru"]
    hists = [1, 5, 25]
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 4, figsize=dk.FIGSIZE["WIDE"], sharey=True)
        for ax, (cap, mode, title) in zip(axes, panels):
            sub = [r for r in rows if r["capture"] == cap and r["mode"] == mode
                   and r["inputs"] in ("y64", "u4,u6", "y8", "u1,u4")]
            present = [a for a in archs if any(r["arch"] == a for r in sub)]
            wdt = 0.8 / len(present)
            for j, a in enumerate(present):
                vals = []
                for h in hists:
                    m = [r for r in sub if r["arch"] == a and r["history"] == h]
                    vals.append(m[0]["r2_report_mean"] if m else np.nan)
                x = np.arange(len(hists)) + (j - (len(present) - 1) / 2) * wdt
                ax.bar(x, np.clip(vals, -0.14, 1), width=wdt * 0.92, color=ARCH_COLOR[a],
                       label=ARCH_LABEL[a], edgecolor="white", linewidth=1)
                for xi, v in zip(x, vals):
                    if np.isfinite(v):
                        ax.text(xi, max(v, 0) + 0.01, f"{v:.2f}", ha="center", va="bottom",
                                fontsize=7, color=dk.INK_2, rotation=90)
            if cap == "opfit12" and mode == "inverse":
                all64 = [r for r in rows if r["capture"] == cap and r["mode"] == mode
                         and r["inputs"] == "all64"]
                if all64:
                    best = max(all64, key=lambda r: r["r2_report_mean"])
                    ax.axhline(best["r2_report_mean"], color=dk.MUTED, ls=":", lw=1.2)
                    ax.text(-0.45, best["r2_report_mean"] + 0.045,
                            f"dotted: best with all 64 ch = {best['r2_report_mean']:.2f}", fontsize=7,
                            ha="left", color=dk.MUTED)
            ax.axhline(0, color=dk.AXIS, lw=0.8)
            ax.set_xticks(range(len(hists)))
            ax.set_xticklabels([f"h={h}" for h in hists])
            ax.set_title(title, fontsize=10)
            ax.grid(False, axis="x")
        axes[0].set_ylabel("held-out R² (mean over reported outputs)")
        axes[0].set_ylim(-0.15, 0.36)
        axes[0].legend(frameon=False, fontsize=8, loc="upper left")
        fig.suptitle("NN inverse ladder: the inverse is at the noise floor on 09-10; "
                     "the forward ceiling is the SNR, not the architecture", fontsize=12)
        return dk.save_fig(fig, ANA / "nn_diag_ladder.png")


def fig_snr(snr):
    grid = snr["forward_r2_grid"]["grid"]
    pulse = snr["pulse_z_ch64"]
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 3, figsize=dk.FIGSIZE["WIDE"])
        ax = axes[0]
        ws = [1, 3, 5, 10, 20]
        fracs = ["0.25", "0.5", "0.75", "1.0"]
        shades = ["#b9d3f1", "#7fade4", "#4a8ddc", dk.COLOR["mpc"]]
        for f, c in zip(fracs, shades):
            ax.plot(ws, [grid[f][str(w)] for w in ws], marker="o", ms=5, color=c,
                    label=f"first {int(float(f)*100)}% of record")
        ax.axhline(0, color=dk.AXIS, lw=0.8)
        ax.set_xscale("log"); ax.set_xticks(ws); ax.set_xticklabels([str(w) for w in ws])
        ax.set_xlabel("moving average on y64 (ticks)")
        ax.set_ylabel("linear forward R² (h=25, held-out)")
        ax.set_title("Averaging does not create signal", fontsize=10)
        ax.legend(frameon=False, fontsize=8)
        ax.grid(False, axis="x")

        ax = axes[1]
        for p in (4, 6):
            d = pulse[f"pair{p}"]
            Ns = np.array([int(k) for k in d["z_vs_N"]]); zs = np.array(list(d["z_vs_N"].values()))
            col = dk.COLOR["stim"] if p == 4 else dk.CAT[6]
            ax.plot(np.sqrt(Ns), zs, "o", ms=6, color=col, label=f"pair {p} (a={d['fit_a']:.3f})")
            xx = np.linspace(0, np.sqrt(max(d["N_for_z3"] or 1, 600)), 50)
            ax.plot(xx, d["fit_a"] * xx, color=col, lw=1.2, ls="--")
            if d["N_for_z3"]:
                ax.annotate(f"z=3 at N≈{d['N_for_z3']}", (np.sqrt(d["N_for_z3"]), 3.0),
                            xytext=(0, 8 if p == 4 else -14), textcoords="offset points",
                            fontsize=8, color=col, ha="center")
        ax.axhline(3, color=dk.MUTED, ls=":", lw=1.2)
        ax.set_xlabel("√N averaged trials (13-25 µA single pulses)")
        ax.set_ylabel("evoked z on y64 (ticks +1..+3)")
        ax.set_title("Single-pulse SNR scales as √N", fontsize=10)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        ax.grid(False, axis="x")

        ax = axes[2]
        for p in range(1, 9):
            d = pulse[f"pair{p}"]
            col = dk.COLOR["stim"] if p == 4 else (dk.CAT[6] if p == 6 else dk.MUTED)
            ax.bar(p, d["single_event_z"], color=col, edgecolor="white")
        ax.axhline(3, color=dk.MUTED, ls=":", lw=1.2)
        ax.text(8.4, 3.05, "z=3 (usable single event)", ha="right", fontsize=8, color=dk.MUTED)
        ax.set_xticks(range(1, 9)); ax.set_xlabel("stim pair")
        ax.set_ylabel("single-event z on y64")
        ax.set_ylim(0, 3.4)
        ax.set_title("One pulse is ~0.1-0.25 SD of the feature noise", fontsize=10)
        ax.grid(False, axis="x")
        mb = snr["mi_bound"]
        fig.suptitle(f"SNR budget: forward R²(y64) {mb['best_forward_r2_y64']:.3f} → inverse R² ≤ "
                     f"{mb['inverse_r2_upper_bound_y64_only']:.3f} (all-64 bound ≤ "
                     f"{mb['inverse_r2_upper_bound_all64']:.2f}); a single event is z ≈ 0.1-0.25",
                     fontsize=12)
        return dk.save_fig(fig, ANA / "nn_diag_snr.png")


def fig_clone(clone):
    sites = ["LP", "P1", "MP", "P3", "SHAM"]
    resA = clone["results"]["A_reference_only"]["mlp"]
    resB = clone["results"]["B_reference_plus_y64"]["mlp"]
    pred, Yv, meta = clone["_traces"][("A_reference_only", "mlp")]
    ks = np.array([m[3] for m in meta]); ss = np.array([m[2] for m in meta])
    t = np.arange(W0, W1)
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 5, figsize=dk.FIGSIZE["WIDE"], sharey=True)
        for ax, s in zip(axes, sites):
            sel = ss == s
            for j, (name, col, ls) in enumerate((("u4", dk.COLOR["stim"], "-"), ("u6", dk.CAT[6], "-"))):
                dm = np.array([Yv[sel & (ks == k), j].mean() for k in t])
                pm = np.array([pred[sel & (ks == k), j].mean() for k in t])
                ax.plot(t / 100, dm, color=col, lw=2.2, alpha=0.35, label=f"MPC delivered {name}")
                ax.plot(t / 100, pm, color=col, lw=1.4, ls="--", label=f"cloned {name}")
            ps = resA["per_site_cross_run_r2"][s]
            ax.set_title(f"{s}  R² u4 {ps['u4']:.2f} / u6 {ps['u6']:.2f}", fontsize=10)
            ax.axvline(0, color=dk.AXIS, lw=0.8)
            ax.set_xlabel("s from touch onset")
            ax.grid(False, axis="x")
        axes[0].set_ylabel("command (µA), event-averaged")
        axes[0].legend(frameon=False, fontsize=7, loc="upper right")
        cr = resA["cross_run_r2"]; cb = resB["cross_run_r2"]
        fig.suptitle(f"Behaviour cloning of the MPC (train r1+r2 → held-out r3): reference-only policy "
                     f"R² u4 {cr['u4']:.2f} / u6 {cr['u6']:.2f}; with y64 feedback {cb['u4']:.2f} / {cb['u6']:.2f}",
                     fontsize=12)
        return dk.save_fig(fig, ANA / "nn_diag_clone.png")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--gru-epochs", type=int, default=40)
    ap.add_argument("--skip", nargs="*", default=[], choices=["ladder", "snr", "alt", "figs"])
    args = ap.parse_args()
    ANA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    prev = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "device": DEVICE,
           "torch": torch.__version__,
           "settings": {"quick": args.quick, "gru_epochs": args.gru_epochs,
                        "gru_hidden": 32, "seq_len": 100, "chunk_batch": 8,
                        "fast_epochs": 30 if args.quick else 120,
                        "note": "train.py loop replicated; GRU batched over truncated-BPTT chunks (see docstring)"}}
    models = {}
    if "ladder" not in args.skip:
        lad = run_ladder(args)
        models = lad.pop("_models")
        out["ladder"] = lad["rows"]
    else:
        out["ladder"] = prev.get("ladder", [])
        # models for the direct-inverse comparison need retraining (cheap)
        for arch_inv, hist in (("linear", 5), ("mlp", 5), ("linear", 25)):
            Xtr, Ytr, Xv, Yv, ds = prepare("opfit12", "inverse", hist, [64])
            res = fit(Xtr, Ytr, Xv, Yv, arch_inv, 30 if args.quick else 120, select_cols=[3, 5])
            models[("opfit12", "inverse", arch_inv, hist, "y64")] = (res["model"], ds)
    print(f"[t+{time.time()-t0:.0f}s] ladder done")
    if "snr" not in args.skip:
        out["snr"] = run_snr(args, out["ladder"])
    else:
        out["snr"] = prev.get("snr")
    print(f"[t+{time.time()-t0:.0f}s] snr done")
    if "alt" not in args.skip:
        fwd = run_alt_forward(args, models)
        for a in fwd["forward_inversion"].values():
            a.pop("_traces", None)
        out["alt_forward_inversion"] = fwd
        clone = run_clone(args)
        traces = clone.pop("_traces")
        out["alt_behaviour_cloning"] = clone
        clone["_traces"] = traces
    else:
        out["alt_forward_inversion"] = prev.get("alt_forward_inversion")
        clone = prev.get("alt_behaviour_cloning")
        if clone is not None and "figs" not in args.skip:
            clone["_traces"] = run_clone(args).pop("_traces")
    print(f"[t+{time.time()-t0:.0f}s] alt done")
    if "figs" not in args.skip:
        out["figures"] = [str(fig_ladder(out["ladder"])), str(fig_snr(out["snr"])),
                          str(fig_clone(clone))]
    out["alt_behaviour_cloning"] = {k: v for k, v in (clone or {}).items() if k != "_traces"}
    out["runtime_s"] = round(time.time() - t0, 1)
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {OUT_JSON}  ({out['runtime_s']} s)")


if __name__ == "__main__":
    main()
