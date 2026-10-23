#!/usr/bin/env python
r"""array_health.py -- ARRAY HEALTH: OK / SUSPECT / BROKEN from ANY Wav1 recording.

    python rig\array_health.py --newest --context tissue            # first in-tissue block
    python rig\array_health.py --newest --context saline            # Phase-0 bench block (both arrays in saline)
    python rig\array_health.py --block <dir> [--n-channels 64] [--label "cortical saline"]

Why (2026-10-16 post-mortem of acute #3): the 64-ch cortical array was electrically
broken BEFORE the first 10-14 recording and nothing on the rig said so. The gate graded
a 63-channel common-mode touch wave as GO (z 23) and the thalamic depth ladder then
read 0/8 on a readout with ~21 live contacts. The signature was visible in the raw
stream of every block: open contacts float to the reference, so they all carry the
same trace. Numbers (same array, same rig):

                         acute #2 (good)      10-14 (broken)     10-13 bench in AIR
  own-signal ch (>10 uV)   44-55 / 64          21-27 / 64         64 (mains, meaningless)
  median pairwise corr     0.858-0.899         0.977-0.994        0.999
  PC1 share                0.78-0.80           0.94-0.97          1.00
  median residual RMS      12.4-13.7 uV        6-8 uV             891 uV
  dead 16-ch banks         none                ch1-16, 49-64      --
  (validated 2026-10-21 on blocks 260910-185534 / 200410, 261014-204658 / 221419, 261013-195629)

No trigger is needed, so this runs on the saline bench block before induction, on the
first in-tissue recording, and inside placement_gate --mode cortical (which turns
BROKEN into NO-GO).

Metrics (Wav1, 610 Hz, first --n-channels channels, blacklist zeroed):
  own-signal RMS  = RMS of (channel - per-sample median of live channels)  [uV]
  n_own           = channels whose own-signal RMS > OWN_UV (tissue) or
                    > OWN_REL x the median own-signal RMS (saline, relative:
                    saline has no neural signal, only each contact's own noise)
  med_pair_corr   = median of all pairwise channel correlations
  pc1_share       = variance fraction of PC1 on z-scored channels (common-mode share)
  banks           = 16-ch connector banks with >= BANK_DEAD of 16 channels lacking own signal
  p60_share       = 58-62 Hz share of the median trace (>= 0.5 => mains-dominated; in AIR?)

Verdict (either context):
  BROKEN   n_own < 32  OR  med_pair_corr >= 0.97  OR  any dead bank
  SUSPECT  n_own < 48  OR  med_pair_corr >= 0.95  OR  (tissue) median own RMS < 10 uV
  OK       otherwise
  A mains-dominated record (p60_share >= 0.5) is reported as UNINFORMATIVE: re-record
  with the contacts and the reference wire submerged (saline) or grounded (tissue).
  The authoritative bench test is still the Synapse impedance sweep at 100 Hz AND
  1 kHz saved to CSV (Caldwell 2018: 1 kHz alone misses broken leads).

Outputs: galleries/<block>/array_health.png + array_health.json, one verdict line.
Exit 0 = OK, 2 = SUSPECT, 3 = BROKEN, 4 = UNINFORMATIVE, 1 = could not evaluate.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DEFAULT_DATA_ROOT = r"C:\Users\brets\Desktop\Data"

# thresholds (one place; copied into the JSON)
TH = dict(own_uv=10.0,          # tissue: a contact with its own signal has > 10 uV residual RMS
          own_rel=0.30,         # saline: a contact with < 0.30 x median residual RMS is floating
          n_own_broken=32, n_own_suspect=40,   # acute #2 blocks read 44-55 own-signal contacts with this metric
          corr_broken=0.97, corr_suspect=0.95,
          resid_suspect_uv=10.0,
          bank_dead=14,         # of 16
          p60_uninformative=0.50,
          max_seconds=120.0)    # analyse at most the first 2 min (enough; keeps a 16-min block fast)

EXIT = {"OK": 0, "SUSPECT": 2, "BROKEN": 3, "UNINFORMATIVE": 4}


def wav1_uv(blk, n_channels):
    from blockutil import find_store
    s = find_store(blk, "Wav1")
    if s is None:
        raise RuntimeError("Wav1 stream not found")
    d = np.asarray(s.data, dtype=np.float64)
    if d.ndim == 1:
        d = d[None, :]
    if not np.any(d):
        raise RuntimeError("Wav1 is ALL ZERO (disk saving off / PZ2 off)")
    if float(np.max(np.abs(d))) < 0.1:
        d *= 1e6
    if n_channels and d.shape[0] > n_channels:
        d = d[:n_channels]
    return d, float(s.fs)


def metrics(x, fs, context="tissue", blacklist=()):
    """x: [ch, t] in uV. Returns a dict with the verdict; no I/O."""
    x = np.array(x, dtype=np.float64, copy=True)
    n_ch = x.shape[0]
    for ch in blacklist:
        if 1 <= ch <= n_ch:
            x[ch - 1] = 0.0
    n_max = int(TH["max_seconds"] * fs)
    if x.shape[1] > n_max:
        x = x[:, :n_max]
    x = x - x.mean(axis=1, keepdims=True)
    live = np.std(x, axis=1) > 1e-6
    n_live = int(live.sum())
    if n_live < 2:
        raise RuntimeError("fewer than 2 non-flat channels")
    xl = x[live]
    med = np.median(xl, axis=0)
    resid = x - med[None, :]
    own_rms = np.sqrt(np.mean(resid ** 2, axis=1))
    own_rms[~live] = 0.0
    own_med = float(np.median(own_rms[live]))
    if context == "saline":
        own_thr = TH["own_rel"] * own_med
    else:
        own_thr = TH["own_uv"]
    has_own = live & (own_rms > own_thr)
    n_own = int(has_own.sum())

    C = np.corrcoef(xl)
    iu = np.triu_indices(n_live, 1)
    med_corr = float(np.median(C[iu]))
    z = xl / (xl.std(axis=1, keepdims=True) + 1e-12)
    s = np.linalg.svd(z, compute_uv=False)
    pc1 = float(s[0] ** 2 / np.sum(s ** 2))

    n = min(len(med), int(fs * 60))
    seg = med[:n] - med[:n].mean()
    f = np.fft.rfftfreq(n, 1.0 / fs)
    P = np.abs(np.fft.rfft(seg)) ** 2
    p60 = float(P[(f > 58) & (f < 62)].sum() / max(P[f > 1].sum(), 1e-12))

    banks = []
    for b in range(0, n_ch, 16):
        idx = np.arange(b, min(b + 16, n_ch))
        n_dead = int(np.sum(~has_own[idx]))
        banks.append(dict(bank=b // 16 + 1, channels="%d-%d" % (idx[0] + 1, idx[-1] + 1),
                          n_without_own_signal=n_dead, dead=bool(len(idx) == 16 and n_dead >= TH["bank_dead"])))
    dead_banks = [bk["channels"] for bk in banks if bk["dead"]]

    reasons = []
    if n_own < TH["n_own_broken"]:
        reasons.append("only %d/%d contacts carry their own signal (< %d)" % (n_own, n_ch, TH["n_own_broken"]))
    if med_corr >= TH["corr_broken"]:
        reasons.append("median pairwise corr %.3f >= %.2f (every channel = the reference)" % (med_corr, TH["corr_broken"]))
    if dead_banks:
        reasons.append("dead 16-ch bank(s): %s (connector / lead bundle)" % ", ".join(dead_banks))
    if reasons:
        verdict = "BROKEN"
    else:
        if n_own < TH["n_own_suspect"]:
            reasons.append("%d/%d contacts with own signal (< %d)" % (n_own, n_ch, TH["n_own_suspect"]))
        if med_corr >= TH["corr_suspect"]:
            reasons.append("median pairwise corr %.3f >= %.2f" % (med_corr, TH["corr_suspect"]))
        if context == "tissue" and own_med < TH["resid_suspect_uv"]:
            reasons.append("median own-signal RMS %.1f uV < %.0f" % (own_med, TH["resid_suspect_uv"]))
        verdict = "SUSPECT" if reasons else "OK"
    note = ""
    if p60 >= TH["p60_uninformative"]:
        note = ("mains-dominated record (60 Hz share %.2f): contacts/reference in AIR or ungrounded; "
                "re-record submerged/grounded before trusting this verdict" % p60)
        verdict = "UNINFORMATIVE"
    hint = {"BROKEN": "do NOT proceed on this array: reseat the connector/headstage, re-run; if unchanged, swap the array",
            "SUSPECT": "reseat the connector and re-run once; proceed only if the cortical gate shows a focal (< 16 ch) response",
            "OK": "", "UNINFORMATIVE": note}[verdict]
    return dict(verdict=verdict, context=context, n_channels=int(n_ch), n_live=n_live, n_own=n_own,
                own_threshold_uv=float(own_thr), own_rms_median_uv=own_med,
                own_rms_uv=[float(v) for v in own_rms], has_own_signal=[bool(v) for v in has_own],
                channels_without_own_signal=[int(i) + 1 for i in np.flatnonzero(~has_own)],
                flat_channels=[int(i) + 1 for i in np.flatnonzero(~live)],
                med_pair_corr=med_corr, pc1_share=pc1, p60_share=p60, banks=banks, dead_banks=dead_banks,
                reasons=reasons, hint=hint, note=note, seconds_analysed=float(x.shape[1] / fs), thresholds=TH)


def one_line(m, label=""):
    return ("ARRAY HEALTH: %s%s | own-signal %d/%d ch | pair-corr %.3f | PC1 %.2f | own RMS med %.1f uV | "
            "dead banks: %s%s" % (m["verdict"], (" (%s)" % label) if label else "", m["n_own"], m["n_channels"],
                                  m["med_pair_corr"], m["pc1_share"], m["own_rms_median_uv"],
                                  ", ".join(m["dead_banks"]) if m["dead_banks"] else "none",
                                  (" | " + "; ".join(m["reasons"])) if m["reasons"] else ""))


def figure(m, plt, title):
    n = m["n_channels"]
    rows = int(np.ceil(n / 8.0))
    g = np.full(rows * 8, np.nan)
    g[:n] = m["own_rms_uv"]
    g = g.reshape(rows, 8)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), width_ratios=[1.0, 1.3])
    ax = axes[0]
    im = ax.imshow(g, cmap="viridis", vmin=0, vmax=max(1.0, np.nanpercentile(g, 95)))
    for r in range(rows):
        for c in range(8):
            k = r * 8 + c
            if k < n:
                ax.text(c, r, "%d" % (k + 1), ha="center", va="center", fontsize=6.5,
                        color="white" if m["has_own_signal"][k] else "#e34948",
                        fontweight="normal" if m["has_own_signal"][k] else "bold")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("own-signal RMS per contact (red = none)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="uV")
    ax = axes[1]
    v = np.asarray(m["own_rms_uv"])
    cols = ["#3b6fb6" if h else "#e34948" for h in m["has_own_signal"]]
    ax.bar(np.arange(1, n + 1), v, color=cols, width=0.8)
    ax.axhline(m["own_threshold_uv"], color="#52514e", lw=0.8, ls="--")
    for b in range(16, n, 16):
        ax.axvline(b + 0.5, color="#b0afa8", lw=0.6)
    ax.set_xlabel("channel (16-ch banks separated)"); ax.set_ylabel("own-signal RMS (uV)")
    ax.set_title("threshold %.1f uV; pair-corr %.3f; PC1 %.2f" % (m["own_threshold_uv"], m["med_pair_corr"], m["pc1_share"]))
    fig.suptitle(title, fontsize=11,
                 color={"OK": "#1b7a3a", "SUSPECT": "#b8860b", "BROKEN": "#b3413a", "UNINFORMATIVE": "#52514e"}[m["verdict"]])
    fig.tight_layout()
    return fig


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", help="block dir")
    ap.add_argument("--newest", action="store_true", help="newest block under --data-root")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--context", choices=["tissue", "saline"], default="tissue")
    ap.add_argument("--n-channels", type=int, default=64, help="keep first N Wav1 channels (0 = all)")
    ap.add_argument("--blacklist", type=int, nargs="*", default=[])
    ap.add_argument("--label", default="")
    ap.add_argument("--out-root", default=os.path.join(REPO, "galleries"))
    ap.add_argument("--json", default=None, help="extra copy of the JSON")
    args = ap.parse_args()

    from blockutil import newest_block_dir, resolve_block_dir, load_block
    block = args.block
    if args.newest:
        block = newest_block_dir(args.data_root)
        print("newest block: %s" % block)
    if not block or not os.path.isdir(block):
        print("ARRAY HEALTH: COULD NOT EVALUATE -- block directory not found: %s" % block)
        return 1
    block = resolve_block_dir(block)
    try:
        blk = load_block(block, ("Wav1",))
        x, fs = wav1_uv(blk, args.n_channels)
        m = metrics(x, fs, args.context, args.blacklist)
    except Exception as exc:  # noqa: BLE001
        print("ARRAY HEALTH: COULD NOT EVALUATE -- %s" % exc)
        return 1
    m["block"] = os.path.basename(block)
    m["label"] = args.label
    print(one_line(m, args.label))
    if m["hint"]:
        print("  -> %s" % m["hint"])
    if m["channels_without_own_signal"]:
        print("  contacts without own signal: %s" % " ".join(str(c) for c in m["channels_without_own_signal"]))

    out_dir = os.path.join(args.out_root, m["block"])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "array_health.json"), "w") as f:
        json.dump(m, f, indent=1)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(m, f, indent=1)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.spines.top": False,
                             "axes.spines.right": False, "axes.titleweight": "bold"})
        fig = figure(m, plt, "ARRAY HEALTH: %s -- %s (%s, %s)" % (m["verdict"], m["block"], args.context,
                                                                 args.label or "unlabelled"))
        fig.savefig(os.path.join(out_dir, "array_health.png"), dpi=130)
        print("  wrote %s" % os.path.join(out_dir, "array_health.png"))
    except Exception as exc:  # noqa: BLE001
        print("  (figure skipped: %s)" % exc)
    return EXIT[m["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
