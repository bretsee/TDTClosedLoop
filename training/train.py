"""Train a control policy from rig captures and export it for cpp_controller.

    python train.py --captures capture_rig_run1.csv --arch residual_mlp --history 5
    python train.py --captures a.csv b.csv --arch gru --hidden 64 --epochs 300
    python train.py --captures a.csv --arch linear            # the baseline to beat

Produces a .nnw file that drops straight into:

    cpp_controller.exe --mode nn --model models\policy.nnw --max-rate 2

READ THE BASELINE NUMBER BEFORE BELIEVING A NETWORK. The acute architecture
search found the winning networks beat a ridge/linear baseline by only ~0.7%
median RMSE. --arch linear trains in seconds and prints the same metrics; if a
deeper model is not clearly better than it on HELD-OUT data, deploy the linear
one. It is faster, bounded, and far easier to reason about on a stim system.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architectures
import data as datamod
from export_nnw import export_nnw


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--captures", nargs="+", required=True,
                   help="one or more capture CSVs written by either controller server")
    p.add_argument("--arch", default="residual_mlp", choices=sorted(architectures.REGISTRY))
    p.add_argument("--mode", default="inverse", choices=["inverse", "forward"],
                   help="inverse = features->stim (a controller); forward = stim->features (a plant model)")
    p.add_argument("--history", type=int, default=1,
                   help="timesteps of context stacked into the input")
    p.add_argument("--use-channels", type=int, nargs="*", default=None,
                   help="1-based feature channels to use (default all)")

    p.add_argument("--hidden", type=int, nargs="+", default=[64, 64],
                   help="mlp: layer widths; residual_mlp/gru: first value is width")
    p.add_argument("--blocks", type=int, default=2, help="residual_mlp block count")
    p.add_argument("--activation", default="relu", choices=["relu", "tanh"])

    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--batch", type=int, default=256)
    p.add_argument("--seq-len", type=int, default=100, help="gru: truncated BPTT length")
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--train-fraction", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")

    p.add_argument("--out", default=None, help="output .nnw path")
    p.add_argument("--umin", type=float, default=0.0)
    p.add_argument("--umax", type=float, default=40.0)
    return p.parse_args()


def evaluate(model, Xv, Yv, recurrent: bool, device) -> dict:
    """R^2 and RMSE per output, in NORMALISED units, on held-out data."""
    model.eval()
    with torch.no_grad():
        xb = torch.tensor(Xv, device=device)
        if recurrent:
            h = None
            preds = []
            for t in range(xb.shape[0]):
                out, h = model(xb[t:t + 1], h)
                preds.append(out)
            pred = torch.cat(preds, dim=0).cpu().numpy()
        else:
            pred = model(xb).cpu().numpy()

    err = pred - Yv
    rmse = float(np.sqrt((err ** 2).mean()))
    ss_res = (err ** 2).sum(axis=0)
    ss_tot = ((Yv - Yv.mean(axis=0)) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = np.where(ss_tot > 1e-12, 1.0 - ss_res / ss_tot, np.nan)
    return {"rmse": rmse, "r2_mean": float(np.nanmean(r2)), "r2_per_output": r2.tolist()}


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    captures = [datamod.load_capture(c) for c in args.captures]
    for c in captures:
        print(f"Loaded {c.path}: {c.n_ticks} ticks, {c.U.shape[1]} stim ch, {c.Y.shape[1]} features")

    ds = datamod.build_dataset(captures, mode=args.mode, history=args.history,
                               use_channels=args.use_channels)
    Xn, Yn = ds.normalised()
    Xtr, Ytr, Xv, Yv = datamod.split_train_val(Xn, Yn, args.train_fraction)
    print(f"\nDataset: mode={args.mode} history={args.history} "
          f"input={Xn.shape[1]} output={Yn.shape[1]}")
    print(f"Split: {Xtr.shape[0]} train / {Xv.shape[0]} validation (contiguous, not shuffled)")

    if Xv.shape[0] < 10:
        raise SystemExit("validation split is too small; use a longer capture")

    kw = dict(activation=args.activation)
    if args.arch == "mlp":
        kw["hidden"] = tuple(args.hidden)
    elif args.arch == "residual_mlp":
        kw["hidden"] = args.hidden[0]
        kw["blocks"] = args.blocks
    elif args.arch == "gru":
        kw["hidden"] = args.hidden[0]

    model = architectures.build(args.arch, Xn.shape[1], Yn.shape[1], **kw).to(args.device)
    recurrent = architectures.is_recurrent(model)
    nparams = sum(p.numel() for p in model.parameters())
    print(f"Model: {args.arch} ({nparams:,} parameters) on {args.device}\n")

    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    lossf = nn.MSELoss()
    Xtr_t = torch.tensor(Xtr, device=args.device)
    Ytr_t = torch.tensor(Ytr, device=args.device)

    best = {"r2_mean": -1e30}
    best_state = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        if recurrent:
            # Contiguous chunks with carried hidden state (truncated BPTT). Order
            # must be preserved for a recurrent model, so no shuffling here.
            total, nb = 0.0, 0
            for start in range(0, Xtr_t.shape[0] - args.seq_len, args.seq_len):
                h = None
                opt.zero_grad()
                loss = 0.0
                for t in range(start, start + args.seq_len):
                    out, h = model(Xtr_t[t:t + 1], h)
                    loss = loss + lossf(out, Ytr_t[t:t + 1])
                loss = loss / args.seq_len
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                h = None
                total += float(loss); nb += 1
            train_loss = total / max(1, nb)
        else:
            perm = torch.randperm(Xtr_t.shape[0], device=args.device)
            total, nb = 0.0, 0
            for i in range(0, len(perm), args.batch):
                idx = perm[i:i + args.batch]
                opt.zero_grad()
                loss = lossf(model(Xtr_t[idx]), Ytr_t[idx])
                loss.backward()
                opt.step()
                total += float(loss); nb += 1
            train_loss = total / max(1, nb)

        if epoch % max(1, args.epochs // 20) == 0 or epoch == args.epochs:
            m = evaluate(model, Xv, Yv, recurrent, args.device)
            print(f"  epoch {epoch:4d}  train {train_loss:.5f}  "
                  f"val RMSE {m['rmse']:.5f}  val R2 {m['r2_mean']:+.4f}")
            if m["r2_mean"] > best["r2_mean"]:
                best = m
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    # Report the BEST per-output R2 alongside the mean, and judge on the best.
    #
    # The mean is badly misleading on this data. A capture has 16 output channels
    # and typically only one carries a response, so a model that nails that
    # channel at R2 = 0.90 still shows a mean near 0.06 -- and a naive threshold
    # on the mean would discard it as having learned nothing. This is the same
    # dilution that made the acute architecture search's median R2 look trivial.
    r2 = np.array(best["r2_per_output"], dtype=float)
    finite = r2[np.isfinite(r2)]
    best_idx = int(np.nanargmax(r2)) if finite.size else -1
    best_r2 = float(np.nanmax(r2)) if finite.size else float("nan")

    print(f"\nBest held-out: RMSE {best['rmse']:.5f}  mean R2 {best['r2_mean']:+.4f}")
    if best_idx >= 0:
        print(f"Strongest output: index {best_idx + 1} at R2 {best_r2:+.4f}")
        ranked = np.argsort(-np.nan_to_num(r2, nan=-1e9))[:5]
        print("Top outputs: " + "  ".join(f"[{i + 1}] {r2[i]:+.3f}" for i in ranked))

    if not finite.size or best_r2 < 0.05:
        print("\nWARNING: no output is predicted better than its own mean on held-out\n"
              "         data. This model has learned nothing useful -- do not deploy it.\n"
              "         Check the capture contains a stim->response relationship first\n"
              "         (rig\\3_fit.ps1 -Sweep).")
    elif best["r2_mean"] < 0.05:
        print("\nNote: mean R2 is low only because most channels carry no response.\n"
              "      Judge this model on the strongest output above, and set\n"
              "      --use-channels to train on just the channels that respond.")

    out = Path(args.out) if args.out else Path("models") / f"{args.arch}_{args.mode}_h{args.history}.nnw"
    export_nnw(model, ds, out, out_min=args.umin, out_max=args.umax, mode=args.mode)
    print(f"\nExported {out}")

    meta = {
        "arch": args.arch, "mode": args.mode, "history": args.history,
        "captures": args.captures, "params": nparams,
        "val_rmse": best["rmse"], "val_r2_mean": best["r2_mean"],
        "val_r2_per_output": best["r2_per_output"],
    }
    Path(str(out) + ".json").write_text(json.dumps(meta, indent=2))
    print(f"Wrote {out}.json")
    print(f"\nVerify the export matches PyTorch before using it:\n"
          f"  python verify_export.py --model {out}")


if __name__ == "__main__":
    main()
