"""sci_common -- shared loaders for the acute #2 touch-battery (sci_) family.

Data sources (all LOCAL, verified 2026-09-11):
  - NNController touch npz + touch_targets_summary.json (templates, QC)
  - the 10 raw thwack blocks under Desktop\\Data (transferred on the day),
    paths recorded in each _meta.json's block_path -- used for per-trial
    epochs and the >200 ms OFF-response window the npz templates cut off.

Per-site best-channel epochs are extracted once into ..\\cache\\epochs_<site>.npz
(matrix trials x samples, baseline-subtracted uV, -30..+400 ms @ 610.35 Hz);
figures read the cache.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]                    # day_2026-09-10\analysis
REPO = HERE.parents[3]                   # TDTClosedLoop
CACHE = ANA / "cache"
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk  # noqa: E402

NNC_TOUCH = (REPO.parent / "NNController" / "outputs" / "BiomimeticInversion"
             / "touch" / "Acute_2026-09-10")
SITE_ORDER = ["D1", "D2", "D3", "D4", "P1", "P2", "P3", "MP", "LP", "SHAM"]

PRE_MS, POST_MS = 30.0, 400.0
CONTACT_MS = 254.6                       # machine-uniform thwacker hold
MIN_PULSE_MS = 50.0                      # nThw runt filter (day-of rule)


def registry() -> list[dict]:
    """Per-site meta dicts in SITE_ORDER, from touch_targets_summary.json."""
    metas = json.loads(dk.need(NNC_TOUCH / "touch_targets_summary.json")
                       .read_text())
    by_site = {m["site"]: m for m in metas}
    missing = [s for s in SITE_ORDER if s not in by_site]
    if missing:
        raise SystemExit(f"sci_common: summary missing sites {missing}")
    return [by_site[s] for s in SITE_ORDER]


def template(meta) -> tuple[np.ndarray, float]:
    """(template 64 x 122 uV, fs) for one site's npz."""
    z = np.load(dk.need(NNC_TOUCH / f"{meta['block']}.npz"))
    return np.asarray(z["template"]), float(z["fs"])


def latency_ms(meta) -> float:
    T, fs = template(meta)
    c = int(meta["best_channel_1based"]) - 1
    return float(np.abs(T[c]).argmax() / fs * 1e3)


def _extract_epochs(meta) -> tuple[np.ndarray, float]:
    import tdt
    blk = dk.need(meta["block_path"])
    d = tdt.read_block(str(blk), store=["Wav1", "nThw"])
    w = d.streams.Wav1
    fs = float(w.fs)
    x = np.asarray(w.data)[int(meta["best_channel_1based"]) - 1]
    nt = d.streams.nThw
    fs_n = float(nt.fs)
    v = np.asarray(nt.data).ravel()
    on = np.flatnonzero((v[1:] > 0.5) & (v[:-1] <= 0.5)) + 1
    off = np.flatnonzero((v[1:] <= 0.5) & (v[:-1] > 0.5)) + 1
    keep = []
    for o in on:
        nxt = off[off > o]
        if len(nxt) and (nxt[0] - o) / fs_n * 1e3 >= MIN_PULSE_MS:
            keep.append(o / fs_n)
    pre = int(PRE_MS * 1e-3 * fs)
    post = int(POST_MS * 1e-3 * fs)
    rows = []
    for t0 in keep:
        i = int(round(t0 * fs))
        if i - pre < 0 or i + post > len(x):
            continue
        seg = x[i - pre:i + post].astype(np.float32)
        rows.append(seg - seg[:pre].mean())
    return np.array(rows), fs


def epochs(meta) -> tuple[np.ndarray, np.ndarray]:
    """(trials x T uV, t_ms) for the site's best channel; cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"epochs_{meta['site']}.npz"
    if f.exists():
        z = np.load(f)
        E, fs = z["E"], float(z["fs"])
    else:
        E, fs = _extract_epochs(meta)
        np.savez_compressed(f, E=E, fs=fs)
        print(f"cached {f.name}: {E.shape}")
    pre = int(PRE_MS * 1e-3 * fs)
    t_ms = (np.arange(E.shape[1]) - pre) / fs * 1e3
    return E, t_ms


def write_json(name: str, payload: dict):
    out = ANA / name
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")
