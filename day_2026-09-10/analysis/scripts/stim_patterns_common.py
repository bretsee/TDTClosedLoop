"""stim_patterns_common -- shared logic for the stim-pattern comparison
(event-triggered command patterns per site, per controller) across acutes.

Question: what stimulus does each controller actually emit for each touch
site?  MPC (closed loop), Choi (open-loop QP tape), NN (learned inverse tape,
acute #2 only).

Window convention: onset-PRE .. onset+POST-1  (PRE=20, POST=200 -> 220 ticks =
one schedule period, so consecutive windows tile without overlap).
  acute #2 (09-10): arrays come from trk_common.load() (SKIP=50 rows applied);
                    onset index = onset_tick - 50 (identical to trk_ scripts).
  acute #1 (08-31): sci_common convention -- no skip, tick 1 = row 0,
                    onset index = onset_tick - 1; capture truncated to
                    min(len(capture), len(ref)); events that do not fit drop.
Under both conventions the reference template departs baseline 1-2 ticks
before window t=0; every lag reported here is command-vs-reference cut from
the SAME window, so that offset cancels.

Lag sign: negative = command leads the reference.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE.parent))
import deckkit as dk  # noqa: E402

PRE, POST = 20, 200
WIN = PRE + POST
TREL = np.arange(-PRE, POST)
BASE = 15            # y / r baseline = mean of the first 15 pre-onset ticks
CAP, FLOOR = 29.5, 0.5
MAXLAG = 30
XMAX = 80            # plotting cut (nothing but the hold happens after ~+25)


def hold_of(x: np.ndarray) -> float:
    """Command hold level = MEDIAN of the 20 pre-onset ticks.  (A mean would be
    contaminated by the 3-4 tick preview lead of MPC and the Choi tape.)"""
    return float(np.median(x[:PRE], axis=0)) if x.ndim == 1 else np.median(x[:PRE], axis=0)


def base_of(x: np.ndarray) -> float:
    return float(x[:BASE].mean())
ARM_LABEL = {"mpc": "MPC", "choi": "Choi", "nn": "NN"}
ARM_ORDER = ["mpc", "choi", "nn"]

# ---------------------------------------------------------------------------
# Day registries
# ---------------------------------------------------------------------------
DAYS = {
    "0910": {
        "label": "acute #2 (2026-09-10)",
        "dir": REPO / "day_2026-09-10",
        "sites": ["LP", "P1", "MP", "P3", "SHAM"],
        "pairs": [4, 6],            # 1-based u columns
        "ctrl": "y64",
        "offset": 50,               # onset index = onset_tick - offset
        "pool": {"mpc": ["mpc_r1", "mpc_r2", "mpc_r3"],
                 "choi": ["choi_r1", "choi_r2", "choi_r3"],
                 "nn": ["nn_r1b"]},
        "extra": ["mpc_r1_late", "choi_r1_late", "mpc_r4b"],
    },
    "0831": {
        "label": "acute #1 (2026-08-31)",
        "dir": REPO / "day_2026-08-31",
        "sites": ["D1", "D2", "D3", "P2", "LP", "SHAM"],
        "pairs": [1, 4],
        "ctrl": "y8",
        "offset": 1,
        "pool": {"mpc": ["mpc_r1", "mpc_r2"], "choi": ["choi_r1", "choi_r2"]},
        "extra": [],
        "runs": {  # key: (arm, capture path, ref, schedule)
            "mpc_r1": ("mpc", REPO / "capture_mpc_20260831_210645.csv",
                       "ref_mix_r1.csv", "schedule_mix_r1.json"),
            "mpc_r2": ("mpc", REPO / "capture_mpc_20260831_213029.csv",
                       "ref_mix_r2.csv", "schedule_mix_r2.json"),
            "choi_r1": ("choi", REPO / "day_2026-08-31" / "capture_choi_mixr1.csv",
                        "ref_mix_r1.csv", "schedule_mix_r1.json"),
            "choi_r2": ("choi", REPO / "day_2026-08-31" / "capture_choi_mixr2.csv",
                        "ref_mix_r2.csv", "schedule_mix_r2.json"),
        },
    },
}

_run_cache: dict = {}


def load_run(day: str, key: str) -> dict:
    """{key, arm, u[N,8], y[N], r[N], sched, offset} for one arm run."""
    ck = (day, key)
    if ck in _run_cache:
        return _run_cache[ck]
    cfg = DAYS[day]
    if day == "0910":
        import trk_common as tc
        u, y, r, _, sched = tc.load(key)
        arm = tc.RUNS[key][0]
        assert cfg["offset"] == tc.SKIP
    else:
        import pandas as pd
        arm, cap, ref, sch = cfg["runs"][key]
        d = pd.read_csv(dk.need(cap))
        rf = pd.read_csv(dk.need(cfg["dir"] / ref))
        ticks = d["tick"].to_numpy().astype(int)
        assert ticks[0] == 1 and np.all(np.diff(ticks) == 1), f"{key}: non-contiguous ticks"
        n = min(len(d), len(rf))
        u = d[[f"u{k}" for k in range(1, 9)]].to_numpy()[:n]
        y = d[cfg["ctrl"]].to_numpy()[:n]
        r = rf["r1"].to_numpy()[:n]
        sched = dk.jload(cfg["dir"] / sch)
    run = {"key": key, "arm": arm, "u": u, "y": y, "r": r, "sched": sched,
           "offset": cfg["offset"], "day": day}
    _run_cache[ck] = run
    return run


# ---------------------------------------------------------------------------
# Event cutting + per-event metrics
# ---------------------------------------------------------------------------
def cut_events(run: dict, pairs: list[int]) -> list[dict]:
    """Per event: u[220, npairs] (active pairs), usum[220], y[220], r[220]."""
    u, y, r = run["u"], run["y"], run["r"]
    cols = [p - 1 for p in pairs]
    out = []
    for ev in run["sched"]["events"]:
        i0 = int(ev["onset_tick"]) - run["offset"] - PRE
        i1 = i0 + WIN
        if i0 < 0 or i1 > len(u):
            continue
        up = u[i0:i1][:, cols]
        out.append({"run": run["key"], "arm": run["arm"], "event": int(ev["event"]),
                    "site": ev["site"], "u": up, "usum": up.sum(1),
                    "y": y[i0:i1], "r": r[i0:i1]})
    return out


def xcorr_lag(a: np.ndarray, b: np.ndarray, maxlag: int = MAXLAG):
    """(lag, corr): lag maximising corr(a[t+lag], b[t]).  Negative = a leads b."""
    best = (0, np.nan)
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return best
    bc = -np.inf
    for L in range(-maxlag, maxlag + 1):
        if L >= 0:
            aa, bb = a[L:], b[:len(b) - L]
        else:
            aa, bb = a[:len(a) + L], b[-L:]
        if np.std(aa) < 1e-12 or np.std(bb) < 1e-12:
            continue
        c = float(np.corrcoef(aa, bb)[0, 1])
        if c > bc:
            bc, best = c, (L, c)
    return best


def safe_corr(a, b):
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _trace_metrics(x: np.ndarray, cap_frac, floor_frac) -> dict:
    hold = hold_of(x)
    post = x[PRE:]
    ipk = int(np.argmax(x))
    return {"hold": hold, "peak": float(x.max()), "t_peak": int(TREL[ipk]),
            "depth": float(x.max() - hold),
            "charge_above_hold": float(np.maximum(x - hold, 0).sum()),
            "charge_total": float(x.sum()),
            "cap_frac": float(cap_frac), "floor_frac": float(floor_frac),
            "post_mean": float(post.mean())}


def event_metrics(ev: dict, pairs: list[int]) -> dict:
    """Scalar metrics per active pair and for the summed command."""
    m = {"run": ev["run"], "arm": ev["arm"], "event": ev["event"], "site": ev["site"]}
    u = ev["u"]
    for j, p in enumerate(pairs):
        x = u[:, j]
        m[f"u{p}"] = _trace_metrics(x, (x >= CAP).mean(), (x <= FLOOR).mean())
    s = ev["usum"]
    ms = _trace_metrics(s, (u >= CAP).any(1).mean(), (u <= FLOOR).all(1).mean())
    ms["cap_frac_pairmean"] = float((u >= CAP).mean())
    rb = ev["r"] - base_of(ev["r"])
    lag, c = xcorr_lag(s - ms["hold"], rb)
    ms["lag_vs_ref"] = int(lag)
    ms["corr_vs_ref_bestlag"] = c
    ms["corr_vs_ref_lag0"] = safe_corr(s - ms["hold"], rb)
    m["sum"] = ms
    yb = ev["y"] - base_of(ev["y"])
    m["y_peak"] = float(yb[PRE:].max())
    m["r_peak"] = float(rb.max())
    return m


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def site_stats(events: list[dict], sites: list[str], pairs: list[int]) -> dict:
    """Per site: mean/SD traces (u per pair, usum, y baseline-subtracted, r)."""
    out = {}
    for s in sites:
        evs = [e for e in events if e["site"] == s]
        if not evs:
            continue
        U = np.stack([e["u"] for e in evs])              # [n, 220, npairs]
        S = np.stack([e["usum"] for e in evs])
        Y = np.stack([e["y"] - base_of(e["y"]) for e in evs])
        R = np.stack([e["r"] - base_of(e["r"]) for e in evs])
        d = {"n": len(evs), "mean_usum": S.mean(0), "sd_usum": S.std(0),
             "mean_y": Y.mean(0), "sd_y": Y.std(0), "mean_r": R.mean(0),
             "mean_u": {}, "sd_u": {}}
        for j, p in enumerate(pairs):
            d["mean_u"][p] = U[:, :, j].mean(0)
            d["sd_u"][p] = U[:, :, j].std(0)
        out[s] = d
    return out


def metric_summary(mets: list[dict], sites: list[str], pairs: list[int]) -> dict:
    """mean/SD of each scalar over events, per site, for 'sum' and each pair."""
    keys = list(_trace_metrics(np.zeros(WIN), 0, 0).keys())
    out = {}
    for s in sites:
        rows = [m for m in mets if m["site"] == s]
        if not rows:
            continue
        d = {"n": len(rows)}
        for grp in ["sum"] + [f"u{p}" for p in pairs]:
            gk = keys + (["cap_frac_pairmean", "lag_vs_ref", "corr_vs_ref_bestlag",
                          "corr_vs_ref_lag0"] if grp == "sum" else [])
            d[grp] = {}
            for k in gk:
                v = np.array([r[grp][k] for r in rows], float)
                v = v[~np.isnan(v)]
                d[grp][k] = {"mean": float(v.mean()) if len(v) else float("nan"),
                             "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                             "n": int(len(v))}
        for k in ("y_peak", "r_peak"):
            v = np.array([r[k] for r in rows], float)
            d[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0}
        out[s] = d
    return out


def between_site_matrix(stats: dict, sites: list[str]) -> np.ndarray:
    """Corr of hold-subtracted mean summed-command patterns between sites."""
    present = [s for s in sites if s in stats]
    M = np.full((len(present), len(present)), np.nan)
    for i, a in enumerate(present):
        for j, b in enumerate(present):
            xa = stats[a]["mean_usum"] - hold_of(stats[a]["mean_usum"])
            xb = stats[b]["mean_usum"] - hold_of(stats[b]["mean_usum"])
            M[i, j] = safe_corr(xa, xb)
    return M


def loo_nearest_centroid(events: list[dict], sites: list[str], seed=0, nperm=200,
                         shape_only=False) -> dict:
    """Leave-one-out nearest-centroid site decoding from per-event command
    patterns (hold-subtracted active-pair traces, concatenated).
    shape_only: each pattern divided by its peak |amplitude| so only the
    time-course (not the amplitude) can carry site identity."""
    evs = [e for e in events if e["site"] in sites]
    feats = []
    for e in evs:
        f = (e["u"] - hold_of(e["u"])).T.ravel()
        if shape_only:
            a = np.abs(f).max()
            f = f / a if a > 1e-6 else f
        feats.append(f)
    X = np.stack(feats)
    lab = np.array([sites.index(e["site"]) for e in evs])
    k = len(sites)

    def loo_acc(lab):
        sums = np.stack([X[lab == c].sum(0) for c in range(k)])
        cnt = np.array([(lab == c).sum() for c in range(k)])
        pred = np.empty(len(X), int)
        for i in range(len(X)):
            s = sums.copy()
            n = cnt.astype(float).copy()
            s[lab[i]] -= X[i]
            n[lab[i]] -= 1
            with np.errstate(invalid="ignore", divide="ignore"):
                cent = s / n[:, None]
            dists = np.linalg.norm(cent - X[i], axis=1)
            dists[n <= 0] = np.inf
            pred[i] = int(np.argmin(dists))
        return pred

    pred = loo_acc(lab)
    acc = float((pred == lab).mean())
    conf = np.zeros((k, k), int)
    for t, p in zip(lab, pred):
        conf[t, p] += 1
    rng = np.random.default_rng(seed)

    def perm_acc():
        pl = rng.permutation(lab)
        return float((loo_acc(pl) == pl).mean())

    null = np.array([perm_acc() for _ in range(nperm)]) if nperm else np.array([])
    return {"n": int(len(X)), "n_sites": k, "chance": 1.0 / k, "accuracy": acc,
            "per_site_recall": {s: float(conf[i, i] / max(conf[i].sum(), 1))
                                for i, s in enumerate(sites)},
            "confusion": conf.tolist(),
            "null_mean": float(null.mean()) if len(null) else None,
            "null_p95": float(np.percentile(null, 95)) if len(null) else None,
            "p_perm": float((null >= acc).mean()) if len(null) else None}


# ---------------------------------------------------------------------------
# Whole-day analysis driver
# ---------------------------------------------------------------------------
def analyse_day(day: str) -> dict:
    cfg = DAYS[day]
    sites, pairs = cfg["sites"], cfg["pairs"]
    res = {"day": day, "label": cfg["label"], "sites": sites, "pairs": pairs,
           "ctrl": cfg["ctrl"], "window": {"pre": PRE, "post": POST, "ticks": WIN},
           "conventions": {
               "onset_index": f"onset_tick - {cfg['offset']}",
               "note": ("trk_common SKIP=50 rows" if day == "0910" else
                        "sci_common: no skip, tick1=row0, truncated to min(len cap, len ref)"),
               "lag_sign": "negative = command leads reference",
               "cap_uA": CAP, "floor_uA": FLOOR,
               "hold": "MEDIAN of the 20 pre-onset ticks (mean is contaminated by the "
                       "3-4 tick preview lead); y/r baseline = mean of first 15 pre ticks",
               "cap_frac": "fraction of (tick, active pair) samples >= 29.5 uA over the window",
               "charge_units": "uA*ticks over the 220-tick window"},
           "runs": {}, "pooled": {}, "events": []}
    pooled_events = {}
    pooled_mets = {}
    for arm, runs in cfg["pool"].items():
        pooled_events[arm] = []
        pooled_mets[arm] = []
        for key in runs:
            run = load_run(day, key)
            evs = cut_events(run, pairs)
            mets = [event_metrics(e, pairs) for e in evs]
            st = site_stats(evs, sites, pairs)
            res["runs"][key] = {
                "arm": arm, "n_events": len(evs),
                "n_ticks": int(len(run["u"])),
                "per_site": {s: {"n": st[s]["n"],
                                 "mean_usum": st[s]["mean_usum"].round(3).tolist(),
                                 "mean_u": {p: st[s]["mean_u"][p].round(3).tolist() for p in pairs}}
                             for s in st},
                "metrics": metric_summary(mets, sites, pairs)}
            pooled_events[arm] += evs
            pooled_mets[arm] += mets
            res["events"] += mets
        st = site_stats(pooled_events[arm], sites, pairs)
        res["pooled"][arm] = {
            "runs": runs, "n_events": len(pooled_events[arm]),
            "stats": {s: {"n": st[s]["n"],
                          "mean_usum": st[s]["mean_usum"].round(3).tolist(),
                          "sd_usum": st[s]["sd_usum"].round(3).tolist(),
                          "mean_u": {p: st[s]["mean_u"][p].round(3).tolist() for p in pairs},
                          "sd_u": {p: st[s]["sd_u"][p].round(3).tolist() for p in pairs},
                          "mean_y": st[s]["mean_y"].tolist(),
                          "sd_y": st[s]["sd_y"].tolist(),
                          "mean_r": st[s]["mean_r"].tolist()} for s in st},
            "metrics": metric_summary(pooled_mets[arm], sites, pairs)}
    res["_events"] = pooled_events            # in-memory only (stripped on write)
    res["_stats"] = {arm: site_stats(pooled_events[arm], sites, pairs) for arm in pooled_events}

    # -- similarity ---------------------------------------------------------
    sim = {"mpc_vs_choi_per_site": {}, "between_site": {}, "decoding": {}}
    for s in sites:
        a, b = res["_stats"]["mpc"].get(s), res["_stats"]["choi"].get(s)
        if a is None or b is None:
            continue
        xa = a["mean_usum"] - hold_of(a["mean_usum"])
        xb = b["mean_usum"] - hold_of(b["mean_usum"])
        lag, cl = xcorr_lag(xa, xb)
        d = {"corr_lag0": safe_corr(xa, xb), "corr_bestlag": cl, "best_lag": int(lag),
             "per_pair_corr": {p: safe_corr(a["mean_u"][p] - hold_of(a["mean_u"][p]),
                                            b["mean_u"][p] - hold_of(b["mean_u"][p]))
                               for p in pairs}}
        if "nn" in res["_stats"] and s in res["_stats"]["nn"]:
            c = res["_stats"]["nn"][s]
            xc = c["mean_usum"] - hold_of(c["mean_usum"])
            d["mpc_vs_nn_corr_lag0"] = safe_corr(xa, xc)
            d["choi_vs_nn_corr_lag0"] = safe_corr(xb, xc)
            d["mpc_vs_nn_bestlag"] = list(xcorr_lag(xa, xc))
        sim["mpc_vs_choi_per_site"][s] = d
    # paired per-event corr (shared schedule -> pair by (run suffix, event))
    pe = []
    for m in pooled_mets["mpc"]:
        sfx = m["run"].split("_", 1)[1]
        partner = [c for c in pooled_mets["choi"] if c["run"].endswith(sfx) and c["event"] == m["event"]]
        if partner:
            pe.append((m["site"], m["sum"]["peak"], partner[0]["sum"]["peak"],
                       m["sum"]["depth"], partner[0]["sum"]["depth"]))
    if pe:
        pk_m = np.array([x[1] for x in pe]); pk_c = np.array([x[2] for x in pe])
        sim["paired_peak_mpc_vs_choi"] = {
            "n": len(pe), "corr_peak": safe_corr(pk_m, pk_c),
            "corr_depth": safe_corr(np.array([x[3] for x in pe]), np.array([x[4] for x in pe])),
            "mean_peak_mpc": float(pk_m.mean()), "mean_peak_choi": float(pk_c.mean())}
    for arm, st in res["_stats"].items():
        present = [s for s in sites if s in st]
        M = between_site_matrix(st, sites)
        off = M[~np.eye(len(present), dtype=bool)]
        real = [s for s in present if s != "SHAM"]
        Mr = between_site_matrix(st, real)
        offr = Mr[~np.eye(len(real), dtype=bool)]
        sim["between_site"][arm] = {"sites": present, "matrix": np.round(M, 4).tolist(),
                                    "offdiag_mean": float(np.nanmean(off)),
                                    "offdiag_min": float(np.nanmin(off)),
                                    "offdiag_mean_real_sites": float(np.nanmean(offr)),
                                    "offdiag_min_real_sites": float(np.nanmin(offr))}
        sim["decoding"][arm] = loo_nearest_centroid(pooled_events[arm], sites)
        sim["decoding"][arm]["real_sites_only"] = loo_nearest_centroid(pooled_events[arm], real)
        sim["decoding"][arm]["shape_only_real_sites"] = loo_nearest_centroid(
            pooled_events[arm], real, shape_only=True)
        sim["decoding"][arm]["note"] = (
            "1.00 is expected for deterministic tapes and a deterministic controller "
            "driven by a fixed per-site template: decodability is inherited from the "
            "reference, it is not evidence of a site-specific stimulation strategy. "
            "Use between_site correlations for that question.")
    # reference-template similarity (what the controllers are asked to do)
    rs = {}
    ref_st = res["_stats"]["mpc"]
    present = [s for s in sites if s in ref_st]
    R = np.full((len(present), len(present)), np.nan)
    for i, a in enumerate(present):
        for j, b in enumerate(present):
            R[i, j] = safe_corr(ref_st[a]["mean_r"], ref_st[b]["mean_r"])
    rs["sites"] = present
    rs["matrix"] = np.round(R, 4).tolist()
    nr = len([s for s in present if s != "SHAM"])       # real sites listed first
    Rr = R[:nr, :nr]
    rs["offdiag_mean_real_sites"] = float(np.nanmean(Rr[~np.eye(nr, dtype=bool)]))
    rs["offdiag_min_real_sites"] = float(np.nanmin(Rr[~np.eye(nr, dtype=bool)]))
    rs["peak_uV"] = {s: float(ref_st[s]["mean_r"].max() * 1e6) for s in present}
    rs["t_peak_ticks"] = {s: int(TREL[int(np.argmax(ref_st[s]["mean_r"]))]) for s in present}
    sim["reference_between_site"] = rs
    res["similarity"] = sim

    # -- big-picture table -------------------------------------------------
    table = {}
    for s in sites:
        row = {}
        for arm in res["pooled"]:
            ms = res["pooled"][arm]["metrics"].get(s)
            if ms is None:
                continue
            row[arm] = {"peak_uA": ms["sum"]["peak"]["mean"],
                        "t_peak_ticks": ms["sum"]["t_peak"]["mean"],
                        "hold_uA": ms["sum"]["hold"]["mean"],
                        "charge_per_event": ms["sum"]["charge_total"]["mean"],
                        "charge_above_hold": ms["sum"]["charge_above_hold"]["mean"],
                        "cap_frac": ms["sum"]["cap_frac_pairmean"]["mean"],
                        "floor_frac": ms["sum"]["floor_frac"]["mean"],
                        "lag_vs_ref": ms["sum"]["lag_vs_ref"]["mean"],
                        "cmd_ref_corr": ms["sum"]["corr_vs_ref_bestlag"]["mean"],
                        "n": ms["n"]}
        if s in sim["mpc_vs_choi_per_site"]:
            row["mpc_vs_choi_corr"] = sim["mpc_vs_choi_per_site"][s]["corr_lag0"]
            row["mpc_vs_choi_corr_bestlag"] = sim["mpc_vs_choi_per_site"][s]["corr_bestlag"]
        table[s] = row
    res["table"] = table
    return res


def strip_private(res: dict) -> dict:
    return {k: v for k, v in res.items() if not k.startswith("_")}


def write_json(res: dict, path: Path):
    path.write_text(json.dumps(strip_private(res), indent=1, default=_jsonable), encoding="utf-8")
    print(f"wrote {path}")


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(str(type(o)))


TABLE_COLS = [("peak_uA", "peak µA", "{:.1f}"), ("hold_uA", "hold µA", "{:.1f}"),
              ("t_peak_ticks", "t-peak", "{:.0f}"),
              ("charge_per_event", "charge/ev", "{:.0f}"), ("cap_frac", "cap frac", "{:.2f}"),
              ("cmd_ref_corr", "cmd-ref r", "{:.2f}")]


def markdown_table(res: dict) -> str:
    arms = [a for a in ARM_ORDER if a in res["pooled"]]
    hdr = ["site"] + [f"{ARM_LABEL[a]} {lbl}" for a in arms for _, lbl, _ in TABLE_COLS] + ["MPC-vs-Choi r"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for s in res["sites"]:
        row = res["table"][s]
        cells = [s]
        for a in arms:
            for k, _, fmt in TABLE_COLS:
                cells.append(fmt.format(row[a][k]) if a in row else "-")
        cells.append(f"{row.get('mpc_vs_choi_corr', float('nan')):.2f}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Figures (matplotlib, deck style)
# ---------------------------------------------------------------------------
def _band(ax, x, m, sd, color, label, lw=2.0, ls="-"):
    ax.plot(x, m, color=color, lw=lw, ls=ls, label=label)
    ax.fill_between(x, m - sd, m + sd, color=color, alpha=0.18, lw=0)


def _ref_guide(ax, r, scale_to, label="ref (scaled)"):
    rb = r - base_of(r)
    if rb.max() > 1e-12:
        ax.plot(TREL, rb / rb.max() * scale_to, color=dk.COLOR["ref"], ls="--",
                lw=1.4, label=label)


def fig_overview(res: dict, out: Path):
    sites, pairs = res["sites"], res["pairs"]
    arms = [a for a in ARM_ORDER if a in res["_stats"]]
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("FULL", nrows=len(sites), ncols=len(pairs), sharex=True, sharey=True)
        axs = np.atleast_2d(axs)
        for i, s in enumerate(sites):
            for j, p in enumerate(pairs):
                ax = axs[i, j]
                top = 0
                for arm in arms:
                    st = res["_stats"][arm].get(s)
                    if st is None:
                        continue
                    _band(ax, TREL, st["mean_u"][p], st["sd_u"][p], dk.COLOR[arm],
                          ARM_LABEL[arm] if (i == 0 and j == 0) else None, lw=1.6)
                    top = max(top, st["mean_u"][p].max())
                _ref_guide(ax, res["_stats"][arms[0]][s]["mean_r"], max(top, 1.0),
                           label="ref (scaled)" if (i == 0 and j == 0) else None)
                ax.axvline(0, color=dk.AXIS, lw=0.8)
                ax.set_xlim(-PRE, XMAX)
                ax.set_ylim(-1, 32)
                ax.set_yticks([0, 15, 30])
                ax.tick_params(labelsize=8)
                if j == 0:
                    ax.set_ylabel(s, fontsize=10, fontweight="bold")
                if i == 0:
                    ax.set_title(f"pair u{p} (µA)", fontsize=11)
                if i == len(sites) - 1:
                    ax.set_xlabel("ticks from template onset (10 ms)")
        axs[0, 0].legend(frameon=False, fontsize=8, ncol=len(arms) + 1, loc="upper right")
        fig.suptitle(f"{res['label']}: event-triggered command per site and pair "
                     f"(mean ± SD, runs pooled; x-axis cut at +{XMAX})", fontsize=13, fontweight="bold")
        dk.save_fig(fig, out)


def fig_table(res: dict, out: Path):
    from matplotlib.colors import LinearSegmentedColormap
    sites = res["sites"]
    arms = [a for a in ARM_ORDER if a in res["pooled"]]
    cols = [(a, k, lbl, fmt) for a in arms for k, lbl, fmt in TABLE_COLS] + [(None, "mpc_vs_choi_corr", "MPC-vs-Choi r", "{:.2f}")]
    V = np.full((len(sites), len(cols)), np.nan)
    for i, s in enumerate(sites):
        for j, (a, k, _, _) in enumerate(cols):
            row = res["table"][s]
            if a is None:
                V[i, j] = row.get(k, np.nan)
            elif a in row:
                V[i, j] = row[a][k]
    # column-normalised shading (one hue, light -> dark)
    N = np.full_like(V, np.nan)
    for j in range(V.shape[1]):
        c = V[:, j]
        lo, hi = np.nanmin(c), np.nanmax(c)
        N[:, j] = (c - lo) / (hi - lo) if hi > lo else 0.5
    cmap = LinearSegmentedColormap.from_list("seq", ["#f3f7fc", dk.COLOR["mpc"]])
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        ax.imshow(N, cmap=cmap, vmin=0, vmax=1, aspect="auto")
        ax.grid(False)
        for i in range(V.shape[0]):
            for j in range(V.shape[1]):
                if np.isnan(V[i, j]):
                    txt = "-"
                else:
                    txt = cols[j][3].format(V[i, j])
                ax.text(j, i, txt, ha="center", va="center", fontsize=9,
                        color="white" if N[i, j] > 0.65 else dk.INK)
        ax.set_yticks(range(len(sites)), sites, fontsize=10)
        ax.set_xticks(range(len(cols)), [c[2] for c in cols], fontsize=8, rotation=35, ha="right")
        # arm group headers
        for gi, a in enumerate(arms):
            x0 = gi * len(TABLE_COLS)
            ax.text(x0 + (len(TABLE_COLS) - 1) / 2, -0.85, ARM_LABEL[a], ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color=dk.COLOR[a])
            if gi:
                ax.axvline(x0 - 0.5, color="white", lw=3)
        ax.axvline(len(cols) - 1.5, color="white", lw=3)
        ax.set_ylim(len(sites) - 0.5, -1.3)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(f"{res['label']}: summed active-pair command per event, by site  "
                     f"(shade = column-normalised; charge = µA·ticks per 220-tick period)",
                     fontsize=11, pad=22)
        dk.save_fig(fig, out)


def fig_charge(res: dict, out: Path):
    sites = res["sites"]
    arms = [a for a in ARM_ORDER if a in res["pooled"]]
    x = np.arange(len(sites))
    w = 0.8 / len(arms)
    with dk.deck_style() as plt:
        fig, (a1, a2) = dk.new_fig("WIDE", ncols=2)
        for k, arm in enumerate(arms):
            off = (k - (len(arms) - 1) / 2) * w
            ms = res["pooled"][arm]["metrics"]
            ch = [ms[s]["sum"]["charge_total"]["mean"] if s in ms else np.nan for s in sites]
            che = [ms[s]["sum"]["charge_total"]["sd"] if s in ms else 0 for s in sites]
            cp = [ms[s]["sum"]["cap_frac_pairmean"]["mean"] if s in ms else np.nan for s in sites]
            cpe = [ms[s]["sum"]["cap_frac_pairmean"]["sd"] if s in ms else 0 for s in sites]
            a1.bar(x + off, ch, w, yerr=che, color=dk.COLOR[arm], label=ARM_LABEL[arm],
                   capsize=2, error_kw={"ecolor": dk.INK_2, "elinewidth": 1})
            a2.bar(x + off, cp, w, yerr=cpe, color=dk.COLOR[arm], label=ARM_LABEL[arm],
                   capsize=2, error_kw={"ecolor": dk.INK_2, "elinewidth": 1})
        for ax, yl, t in ((a1, "charge per event (µA·ticks, both pairs, 220 ticks)", "Charge per event"),
                          (a2, "fraction of pair-ticks at cap (≥29.5 µA)", "Time at the 30 µA cap")):
            ax.set_xticks(x, sites)
            ax.set_ylabel(yl)
            ax.set_title(t)
            ax.grid(False, axis="x")
        a2.set_ylim(0, max(0.05, a2.get_ylim()[1]))
        a1.legend(frameon=False)
        fig.suptitle(f"{res['label']}: mean ± SD over events, runs pooled", fontsize=12, fontweight="bold")
        dk.save_fig(fig, out)


def fig_site(res: dict, site: str, out: Path):
    pairs = res["pairs"]
    arms = [a for a in ARM_ORDER if a in res["_stats"] and site in res["_stats"][a]]
    with dk.deck_style() as plt:
        fig = plt.figure(figsize=dk.FIGSIZE["FULL"])
        gs = fig.add_gridspec(2, 3, width_ratios=[1.3, 1.1, 0.8])
        axl = [fig.add_subplot(gs[j, 0]) for j in range(len(pairs))]
        axm = fig.add_subplot(gs[:, 1])
        axr = fig.add_subplot(gs[0, 2])
        axr2 = fig.add_subplot(gs[1, 2])
        ref = res["_stats"][arms[0]][site]["mean_r"]
        for j, p in enumerate(pairs):
            ax = axl[j]
            top = 1.0
            for arm in arms:
                st = res["_stats"][arm][site]
                _band(ax, TREL, st["mean_u"][p], st["sd_u"][p], dk.COLOR[arm], ARM_LABEL[arm])
                top = max(top, st["mean_u"][p].max())
            _ref_guide(ax, ref, top)
            ax.axvline(0, color=dk.AXIS, lw=0.8)
            ax.set_xlim(-PRE, XMAX)
            ax.set_ylim(-1, 32)
            ax.set_ylabel(f"u{p} (µA)")
            if j == 0:
                ax.set_title("Command per pair (mean ± SD)")
                ax.legend(frameon=False, ncol=2, fontsize=9, loc="upper right")
            if j == len(pairs) - 1:
                ax.set_xlabel("ticks from template onset")
            else:
                ax.tick_params(labelbottom=False)
        # middle: achieved y vs ref
        for arm in arms:
            st = res["_stats"][arm][site]
            _band(axm, TREL, st["mean_y"] * 1e6, st["sd_y"] * 1e6, dk.COLOR[arm], ARM_LABEL[arm])
        axm.plot(TREL, ref * 1e6, color=dk.COLOR["ref"], ls="--", lw=1.6, label="reference")
        axm.axvline(0, color=dk.AXIS, lw=0.8)
        axm.set_xlim(-PRE, XMAX)
        axm.set_xlabel("ticks from template onset")
        axm.set_ylabel(f"{res['ctrl']} feature, baseline-subtracted (µV)")
        axm.set_title("Achieved control channel vs reference")
        axm.legend(frameon=False, fontsize=9)
        # right: per-event strips -- summed peak (top), charge above hold (bottom)
        rng = np.random.default_rng(1)
        for ax, key, yl, t in ((axr, "peak", "peak of summed command (µA)", "Peak per event"),
                               (axr2, "charge_above_hold", "charge above hold (µA·ticks)",
                                "Charge above hold per event")):
            vmax = 0
            for k, arm in enumerate(arms):
                v = np.array([m["sum"][key] for m in res["events"]
                              if m["arm"] == arm and m["site"] == site])
                xj = k + rng.uniform(-0.18, 0.18, len(v))
                ax.scatter(xj, v, s=14, color=dk.COLOR[arm], alpha=0.6, lw=0)
                ax.hlines(v.mean(), k - 0.3, k + 0.3, color=dk.INK, lw=2)
                vmax = max(vmax, v.max())
                ax.annotate(f"{v.mean():.0f}", (k, v.mean()), xytext=(0, 6),
                            textcoords="offset points", ha="center", fontsize=8, color=dk.INK_2)
            ax.set_xticks(range(len(arms)), [ARM_LABEL[a] for a in arms])
            ax.set_ylim(0, vmax * 1.15 + 1)
            ax.set_ylabel(yl, fontsize=9)
            ax.set_title(t, fontsize=11)
            ax.grid(False, axis="x")
        n = {a: res["_stats"][a][site]["n"] for a in arms}
        fig.suptitle(f"{res['label']} -- site {site}: " +
                     ", ".join(f"{ARM_LABEL[a]} n={n[a]}" for a in arms),
                     fontsize=13, fontweight="bold")
        dk.save_fig(fig, out)


def fig_pattern_pairs(pairs_of_stats: list, title: str, out: Path, preset="WIDE",
                      style_by="arm"):
    """Generic per-site panel row: each entry = (site, [(label, arm, ls, usum_mean, ref)])."""
    n = len(pairs_of_stats)
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig(preset, ncols=n, sharey=True)
        axs = np.atleast_1d(axs)
        for ax, (site, sub, note) in zip(axs, pairs_of_stats):
            top = 1.0
            for label, arm, ls, m in sub:
                ax.plot(TREL, m, color=dk.COLOR[arm], ls=ls, lw=1.8, label=label)
                top = max(top, m.max())
            ax.axvline(0, color=dk.AXIS, lw=0.8)
            ax.set_xlim(-PRE, XMAX)
            ax.set_title(f"{site}\n{note}", fontsize=10)
            ax.set_xlabel("ticks from onset")
        axs[0].set_ylabel("summed command (µA)")
        axs[0].legend(frameon=False, fontsize=9)
        fig.suptitle(title, fontsize=12, fontweight="bold")
        dk.save_fig(fig, out)
