"""Shared helpers for spat_* overnight analysis (day 2026-08-31, part 2)."""
import json
import os

import numpy as np

DATA_ROOT = r"C:\Users\brets\Desktop\Data"
DAY_DIR = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\day_2026-08-31"
ANA_DIR = os.path.join(DAY_DIR, "analysis")
TPL_DIR = (r"C:\Users\brets\Documents\Repositories\NNController\outputs"
           r"\BiomimeticInversion\touch\Acute_2026-08-31")

FS_WAV = 610.3516
POST_SAMPLES = 122
BLACKLIST_CH = [26]  # 0-based (ch 27 1-based)
WATCH_CH = 13        # 0-based (ch 14 1-based)

TOUCH_BLOCKS = {  # site -> block name
    "SHAM": "BSClosedLoop32-260831-175746",
    "P3": "BSClosedLoop32-260831-180137",
    "D4": "BSClosedLoop32-260831-180520",
    "D1": "BSClosedLoop32-260831-180905",
    "MP": "BSClosedLoop32-260831-181248",
    "P1": "BSClosedLoop32-260831-181632",
    "LP": "BSClosedLoop32-260831-182004",
    "D2": "BSClosedLoop32-260831-182330",
    "D3": "BSClosedLoop32-260831-182722",
    "P2": "BSClosedLoop32-260831-183157",
}
SITE_ORDER = ["SHAM", "P3", "D4", "D1", "MP", "P1", "LP", "D2", "D3", "P2"]

ARM_BLOCKS = {
    "MPC_r1b": ("BSClosedLoop32-260831-210818", "schedule_mix_r1.json"),
    "Choi_r1": ("BSClosedLoop32-260831-211935", "schedule_mix_r1.json"),
    "MPC_r2": ("BSClosedLoop32-260831-213101", "schedule_mix_r2.json"),
    "Choi_r2": ("BSClosedLoop32-260831-214109", "schedule_mix_r2.json"),
}
RND1_BLOCK = "BSClosedLoop32-260831-183856"
RNDHI_BLOCK = "BSClosedLoop32-260831-194938"


def block_path(name):
    return os.path.join(DATA_ROOT, name, name)


def read_block(name, **kw):
    import tdt
    return tdt.read_block(block_path(name), **kw)


def wav1_uv(blk):
    """Wav1 data as (n_ch, n_samp) float64 in uV, plus fs and start time."""
    s = blk.streams.Wav1
    d = np.asarray(s.data, dtype=np.float64)
    return d, float(s.fs), float(getattr(s, "start_time", 0.0))


def rising_edges_stream(stream, thresh=0.5):
    """Onset times (s) of a 0/1 float stream (block time base)."""
    d = np.asarray(stream.data).ravel()
    fs = float(stream.fs)
    t0 = float(getattr(stream, "start_time", 0.0))
    on = d > thresh
    idx = np.flatnonzero(~on[:-1] & on[1:]) + 1
    if on[0]:
        idx = np.concatenate([[0], idx])
    return t0 + idx / fs


def epoch(data, fs, t_start_stream, onset_times, pre_s=0.05, post_samples=POST_SAMPLES):
    """Epoch (n_ch, n_samp) data around onsets.

    Returns (trials [n_tr, n_ch, n_pre+post], n_pre, kept_mask).
    Baseline NOT subtracted here.
    """
    n_pre = int(round(pre_s * fs))
    n_ch, n_samp = data.shape
    trials, kept = [], []
    for t in onset_times:
        i0 = int(round((t - t_start_stream) * fs))
        a, b = i0 - n_pre, i0 + post_samples
        if a < 0 or b > n_samp:
            kept.append(False)
            continue
        trials.append(data[:, a:b])
        kept.append(True)
    return np.array(trials), n_pre, np.array(kept, bool)


def baseline_subtract(trials, n_pre):
    """Subtract per-trial per-channel mean of the pre window."""
    base = trials[:, :, :n_pre].mean(axis=2, keepdims=True)
    return trials - base


def load_template(site):
    d = np.load(os.path.join(TPL_DIR, TOUCH_BLOCKS[site] + ".npz"))
    return d


def response_vectors(trials_bs, n_pre, fs=FS_WAV, w0=0.010, w1=0.040):
    """Mean LFP per channel in [w0, w1] s post-onset -> (n_tr, n_ch)."""
    a = n_pre + int(round(w0 * fs))
    b = n_pre + int(round(w1 * fs))
    return trials_bs[:, :, a:b].mean(axis=2)


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 10,
        "text.color": "black",
        "axes.labelcolor": "black",
        "axes.edgecolor": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        "axes.titlecolor": "black",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 200,
        "savefig.dpi": 200,
    })
    return plt


GREEN, GREY, RED, AMBER = "#3F7A4E", "#5B6470", "#B3413A", "#C9A23A"


def save_json_part(key, obj):
    """Merge a section into spat_summary.json."""
    p = os.path.join(ANA_DIR, "spat_summary.json")
    cur = {}
    if os.path.exists(p):
        with open(p) as f:
            cur = json.load(f)
    cur[key] = obj
    with open(p, "w") as f:
        json.dump(cur, f, indent=1, default=float)
