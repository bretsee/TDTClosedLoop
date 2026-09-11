"""trk_common -- run registry + raw recompute gate for the arms (trk_) family.

Anti-drift contract: headline r0 / slope / charge are RECOMPUTED here from the
raw capture + reference CSVs and asserted against the run-time tracking_*.json
(tolerance 2e-3 -- the run-time tool's exact lag/skip conventions are its own).
Best-lag values are quoted from the run-time JSONs (they are artifacts of
record, regression-pinned by the r0 assertion).

VOID runs (PZ2-off: mpc_r4cm original, nn_r1 original, first late re-probe)
are deliberately absent from RUNS; they appear only on the incident slide.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ANA = HERE.parents[1]
DAY = HERE.parents[2]                    # day_2026-09-10
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk  # noqa: E402

SKIP = 50

RUNS = {
    # key: (arm, capture, ref, tracking_json, schedule_json or None)
    "mpc_r1":      ("mpc",  "capture_mpc_mixr1.csv",       "ref_mix_r1.csv", "tracking_mpc_r1.json",      "schedule_mix_r1.json"),
    "mpc_r2":      ("mpc",  "capture_mpc_mixr2.csv",       "ref_mix_r2.csv", "tracking_mpc_r2.json",      "schedule_mix_r2.json"),
    "mpc_r3":      ("mpc",  "capture_mpc_mixr3.csv",       "ref_mix_r3.csv", "tracking_mpc_r3.json",      "schedule_mix_r3.json"),
    "mpc_r1_late": ("mpc",  "capture_mpc_mixr1_late.csv",  "ref_mix_r1.csv", "tracking_mpc_r1_late.json", "schedule_mix_r1.json"),
    "mpc_r4b":     ("mpc",  "capture_mpc_r4b_cm.csv",      "ref_mix_r1.csv", "tracking_mpc_r4b.json",     "schedule_mix_r1.json"),
    "choi_r1":     ("choi", "capture_choi_mixr1.csv",      "ref_mix_r1.csv", "tracking_choi_r1.json",     "schedule_mix_r1.json"),
    "choi_r2":     ("choi", "capture_choi_mixr2.csv",      "ref_mix_r2.csv", "tracking_choi_r2.json",     "schedule_mix_r2.json"),
    "choi_r3":     ("choi", "capture_choi_mixr3.csv",      "ref_mix_r3.csv", "tracking_choi_r3.json",     "schedule_mix_r3.json"),
    "choi_r1_late": ("choi", "capture_choi_mixr1_late.csv", "ref_mix_r1.csv", "tracking_choi_r1_late.json", "schedule_mix_r1.json"),
    "nn_r1b":      ("nn",   "capture_nn_r1b.csv",          "ref_mix_r1.csv", "tracking_nn_r1b.json",      "schedule_mix_r1.json"),
}

_cache: dict = {}


def load(run: str):
    """(u [N,8], y64 [N], r [N], tjson dict, schedule dict|None), skip applied."""
    if run in _cache:
        return _cache[run]
    import pandas as pd
    arm, cap, ref, tj, sch = RUNS[run]
    d = pd.read_csv(dk.need(DAY / cap))
    rf = pd.read_csv(dk.need(DAY / ref))
    n = min(len(d), len(rf))
    u = d[[f"u{k}" for k in range(1, 9)]].to_numpy()[SKIP:n]
    y = d["y64"].to_numpy()[SKIP:n]
    r = rf["r1"].to_numpy()[SKIP:n]
    tjson = dk.jload(DAY / tj)
    sched = dk.jload(DAY / sch) if sch else None
    _cache[run] = (u, y, r, tjson, sched)
    return _cache[run]


def shipped(run: str) -> dict:
    """The run-time tracking numbers (per_channel[0]) for quoting."""
    return load(run)[3]["per_channel"][0]


def recompute(run: str) -> dict:
    """r0/slope/charge from raw; ASSERT r0 matches the run-time JSON."""
    u, y, r, tjson, _ = load(run)
    pc = tjson["per_channel"][0]
    rz = r - r.mean()
    yz = y - y.mean()
    denom = np.linalg.norm(rz) * np.linalg.norm(yz)
    r0 = float(np.dot(rz, yz) / denom) if denom > 0 else 0.0
    slope = float(np.dot(rz, yz) / np.dot(rz, rz))
    charge = float(np.abs(u).sum())
    d0 = abs(r0 - pc["pearson_lag0"])
    if d0 > 2e-3:
        raise SystemExit(
            f"trk_common: ANTI-DRIFT FAIL on {run}: recomputed r0 {r0:.4f} vs "
            f"shipped {pc['pearson_lag0']:.4f} (|d|={d0:.4f})")
    return {"run": run, "arm": RUNS[run][0], "r0": r0, "slope": slope,
            "charge_uAticks": charge,
            "r_best": pc["pearson_best"], "best_lag": pc["best_lag_ticks"],
            "slope_shipped": pc["slope_y_on_r"], "verdict": pc["verdict"]}


def per_event_r(run: str) -> list[dict]:
    """Per-event tracking r within each schedule event window (220 ticks)."""
    u, y, r, _, sched = load(run)
    period = int(sched["period_ticks"])
    out = []
    for ev in sched["events"]:
        i0 = int(ev["onset_tick"]) - SKIP
        i1 = i0 + period
        if i0 < 0 or i1 > len(y):
            continue
        rr, yy = r[i0:i1], y[i0:i1]
        rz, yz = rr - rr.mean(), yy - yy.mean()
        den = np.linalg.norm(rz) * np.linalg.norm(yz)
        out.append({"site": ev["site"], "event": ev["event"],
                    "r": float(np.dot(rz, yz) / den) if den > 0 else 0.0})
    return out


def write_json(name: str, payload: dict):
    out = ANA / name
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    # Gate check: recompute every run, assert against shipped numbers.
    for k in RUNS:
        m = recompute(k)
        print(f"{k:14s} r0 {m['r0']:+.3f} (shipped ok) slope {m['slope']:+.3f} "
              f"charge {m['charge_uAticks']:.0f}")
    print("trk_common: ALL RUNS PASS the anti-drift recompute gate")
