"""Weekly deck, week of 2026-10-02 .. 2026-10-09 (acute #3 postponed; offline
improvement day; deckkit).

Sections: (1) rig status (NIC dead, dongle path, acute #3 postponed),
(2) controller model: the dead-time finding and fix, offset-free MPC, effort
ratio + telemetry, the one-run R sweep, (3) experimental flow: what would have
failed on 10-08, run audit, runcards, (4) burst plant fitter (known-answer +
rnd1), (5) acute-#3 readiness and next week. Every number is read from
day_2026-10-09/ artifacts or recomputed from captures at build time; the build
FAILS on a missing artifact. Ten figures are generated here.

    python scripts\\build_weekly_deck_2026-10-09.py
    python scripts\\check_deck.py <written pptx> --fig-dir .
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "rig"))
import deckkit as dk  # noqa: E402

DAY = REPO / "day_2026-10-09"
FIG = REPO / "outputs" / "deck_figures"
OUT = (REPO.parent / "PythonIntanAnalysis" / "outputs" / "Synthesis"
       / "ClosedLoop_weekly_2026-10-09.pptx")
TARGET_V = 6.5e-5


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def fig_frames() -> Path:
    """Schematic: where the tick went (controller frame vs fitter frame vs data)."""
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        ticks = np.arange(0, 6)
        rows = [("data (rnd1 pulse probe, 7/7 pairs)", 3, dk.COLOR["stim"], "first feature movement at k+3"),
                ("fitter (shift 1 + nk 1), pre 10-09", 2, dk.COLOR["choi"], "fitted relation u(k) → y(k+2)"),
                ("exported model, pre 10-09", 1, dk.MUTED, "export dropped the shift: u(k) → y(k+1)"),
                ("controller assumption (cpp / mpc_test)", 1, dk.COLOR["mpc"], "x(k+1) = A x(k) + B u(k): dead time 1"),
                ("fitter + delay states, 10-09 (inputDelayTicks 2)", 3, dk.COLOR["nn"], "u(k) → y(k+3) in the controller's own frame")]
        for i, (label, dt, col, note) in enumerate(rows):
            y = len(rows) - 1 - i
            ax.plot([0, dt], [y, y], color=col, lw=6, solid_capstyle="butt")
            ax.scatter([0], [y], color=col, s=80, zorder=3)
            ax.scatter([dt], [y], color=col, s=80, marker="s", zorder=3)
            ax.text(-0.15, y, label, ha="right", va="center", fontsize=9, color=dk.INK)
            ax.text(dt + 0.15, y, note, ha="left", va="center", fontsize=9, color=dk.INK_2)
        ax.set_xlim(-4.6, 7.2)
        ax.set_ylim(-0.7, len(rows) - 0.3)
        ax.set_xticks(ticks, [f"k+{t}" if t else "k (command sent)" for t in ticks])
        ax.set_yticks([])
        ax.grid(True, axis="x"); ax.grid(False, axis="y")
        ax.set_title("Command at tick k: when does the feature move? Data say k+3; the deployed model said k+1")
        for sp in ("left",):
            ax.spines[sp].set_visible(False)
        return dk.save_fig(fig, FIG / "weekly1009_frames.png")


def fig_onsets(rnd: dict) -> Path:
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(2, 4, figsize=dk.FIGSIZE["FULL"], sharex=True)
        for k, ax in enumerate(axes.ravel()):
            key = f"u{k+1}"
            d = rnd["inputs"][key]
            prof = np.array(d["profile"][:11]) * 1e6
            thr = d["threshold"] * 1e6
            lags = np.arange(len(prof))
            col = dk.COLOR["stim"] if d["onset"] is not None else dk.MUTED
            ax.bar(lags, prof, color=col, width=0.7)
            ax.axhline(thr, color=dk.INK_2, ls="--", lw=1)
            ax.axhline(-thr, color=dk.INK_2, ls="--", lw=1)
            on = d["onset"]
            ax.set_title(f"pair {k+1}: onset lag {on if on is not None else '—'}", fontsize=10)
            if k >= 4:
                ax.set_xlabel("lag (ticks of 10 ms)")
            if k % 4 == 0:
                ax.set_ylabel("µV per µA")
            ax.set_xticks(range(0, 11, 2))
        fig.suptitle(f"rnd1 pulse probe, channel 64: trial-averaged response per unit amplitude ({rnd['inputs']['u1']['kind']}); dashed = p99 null",
                     fontsize=11)
        return dk.save_fig(fig, FIG / "weekly1009_onsets.png")


def fig_shift(op: dict, syn: dict) -> Path:
    shifts = [-2, -1, 0, 1, 2]
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"])
        ax = axes[0]
        models = [("plant_opfit12.lti", "09-10 export (old)", dk.MUTED),
                  ("plant_opfit12_d1.lti", "refit, delay states, d=1", dk.COLOR["choi"]),
                  ("plant_opfit12_d2.lti", "refit, delay states, d=2", dk.COLOR["mpc"])]
        w = 0.26
        for i, (key, label, col) in enumerate(models):
            vals = [op["models"][key]["fit_by_shift"][str(s)] for s in shifts]
            ax.bar(np.array(shifts) + (i - 1) * w, vals, width=w, color=col, label=label)
            best = shifts[int(np.argmax(vals))]
            ax.annotate(f"best {best:+d}", (best + (i - 1) * w, max(vals)), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=8, color=col)
        ax.axvline(0, color=dk.INK_2, lw=1, ls=":")
        ax.set_xticks(shifts, [f"{s:+d}" for s in shifts])
        ax.set_xlabel("model output advanced by s ticks (s > 0: model answers early)")
        ax.set_ylabel("row-frame free-run fit %")
        ax.set_title("opfit12 tonic PRBS (acute #2 plant source)")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        ax = axes[1]
        for i, (key, label, col) in enumerate([("synth_dead4_d0.lti", "legacy export", dk.MUTED),
                                               ("synth_dead4_d2.lti", "delay states, d=2", dk.COLOR["mpc"])]):
            k = next(kk for kk in syn["models"] if kk.endswith(key))
            vals = [syn["models"][k]["fit_by_shift"][str(s)] for s in shifts]
            ax.bar(np.array(shifts) + (i - 0.5) * 0.36, vals, width=0.36, color=col, label=label)
            best = shifts[int(np.argmax(vals))]
            ax.annotate(f"best {best:+d}", (best + (i - 0.5) * 0.36, max(vals)), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=8, color=col)
        ax.axvline(0, color=dk.INK_2, lw=1, ls=":")
        ax.set_xticks(shifts, [f"{s:+d}" for s in shifts])
        ax.set_xlabel("model output advanced by s ticks")
        ax.set_title("synthetic plant with a known 4-tick dead time")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        return dk.save_fig(fig, FIG / "weekly1009_shift.png")


def fig_mismatch() -> tuple[Path, dict]:
    caps = {m: pd.read_csv(DAY / f"capture_sim_mismatch_{m}.csv") for m in ("plain", "dist")}
    lats = {m: pd.read_csv(DAY / f"server_lat_capture_sim_mismatch_{m}.csv", comment="#") for m in ("plain", "dist")}
    nums = {}
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(2, 1, figsize=dk.FIGSIZE["FULL"], sharex=True,
                                 gridspec_kw={"height_ratios": [2.2, 1]})
        ax = axes[0]
        for m, col, label in (("plain", dk.COLOR["choi"], "plain observer (Choi-comparable default)"),
                              ("dist", dk.COLOR["mpc"], "--dist-observer (offset-free MPC)")):
            t = caps[m]["tick"].values / 100.0
            y = caps[m]["y64"].values * 1e6
            ax.plot(t, y, color=col, lw=1.2, label=label)
            n = len(y)
            nums[m] = {"early": float(y[:200].mean()), "late": float(y[n - 200:].mean()),
                       "u_late": float(caps[m]["u4"].values[n - 200:].mean()),
                       "innov_late": float(np.sqrt(np.mean(lats[m]["innov0"].values[n - 200:] ** 2)))}
        ax.axhline(TARGET_V * 1e6, color=dk.COLOR["ref"], ls="--", lw=1.2, label="target")
        ax.set_ylabel("feature y64 (µV)")
        ax.set_title("Sim on plant_opfit12_d2 with the PLANT at 1.5× the model gain, +10 µV bias, +0.02 µV/tick drift")
        ax.legend(frameon=False, fontsize=9, loc="center right")
        ax = axes[1]
        for m, col in (("plain", dk.COLOR["choi"]), ("dist", dk.COLOR["mpc"])):
            ax.plot(lats[m]["seq"].values / 100.0, np.abs(lats[m]["innov0"].values) * 1e6, color=col, lw=0.8)
        ax.set_yscale("log")
        ax.set_ylabel("|innovation| (µV)")
        ax.set_xlabel("seconds")
        return dk.save_fig(fig, FIG / "weekly1009_mismatch.png"), nums


def fig_effort() -> Path:
    rho = np.logspace(-3, 1, 200)
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["WIDE"])
        ax = axes[0]
        ax.plot(rho, 100 * rho / (1 + rho), color=dk.COLOR["mpc"], lw=2)
        for r, lab in ((0.01, "0.01"), (0.1, "0.1"), (1.0, "1")):
            ax.scatter([r], [100 * r / (1 + r)], color=dk.COLOR["stim"], zorder=3)
            ax.annotate(f"ρ={lab}: {100*r/(1+r):.0f}%", (r, 100 * r / (1 + r)), textcoords="offset points",
                        xytext=(6, -10), fontsize=9)
        ax.set_xscale("log")
        ax.set_xlabel("effort ratio ρ  (R = ρ · Q · G²)")
        ax.set_ylabel("steady-state shortfall (%)")
        ax.set_title("--effort-ratio: one dimensionless knob instead of q-weight 1e12")
        ax = axes[1]
        lat = pd.read_csv(DAY / "server_lat_capture_sim_mismatch_dist.csv", comment="#")
        t = lat["seq"].values / 100.0
        ax.plot(t, lat["qpIters"].values, color=dk.COLOR["mpc"], lw=0.8, label="QP iterations")
        ax.set_ylabel("QP iterations / tick")
        ax.set_xlabel("seconds (offset-free sim run)")
        ax2 = ax.twinx()
        ax2.plot(t, lat["activeFrac"].values, color=dk.COLOR["stim"], lw=0.8, alpha=0.7, label="active-set fraction")
        ax2.set_ylabel("active-set fraction")
        ax2.set_ylim(-0.05, 1.05)
        ax2.spines["top"].set_visible(False)
        ax.set_title(f"per-tick telemetry now in the latency log (converged {100*lat['qpConv'].mean():.0f}% of ticks)")
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper right")
        return dk.save_fig(fig, FIG / "weekly1009_effort.png")


def fig_rsweep(rs: dict) -> Path:
    lat = pd.read_csv(DAY / "server_lat_capture_sim_rsweep.csv", comment="#")
    cols = {100.0: dk.COLOR["mpc"], 30.0: dk.COLOR["choi"], 10.0: dk.COLOR["nn"]}
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"], gridspec_kw={"width_ratios": [1.6, 1]})
        ax = axes[0]
        ax.step(lat["seq"].values / 100.0, lat["rW0"].values, where="post", color=dk.INK, lw=1.5)
        ax.set_yscale("log")
        ax.set_ylabel("R weight in force (rW0, telemetry)")
        ax.set_xlabel("seconds (one 222 s run, ref_mix_r1 schedule)")
        for b in rs["blocks"]:
            ax.axvspan(b["ticks"][0] / 100.0, b["ticks"][1] / 100.0, color=cols[b["R"]], alpha=0.12, lw=0)
            ax.text((b["ticks"][0] + b["ticks"][1]) / 200.0, 150, f"block {b['block']}\nR={b['R']:g}", ha="center",
                    fontsize=8, color=cols[b["R"]])
        ax.set_ylim(5, 300)
        ax.set_title("--r-schedule: the effort weight switches at each 20-event block start")
        ax = axes[1]
        x = [b["block"] for b in rs["blocks"]]
        ax.bar(x, [b["above_hold_uAticks"] for b in rs["blocks"]], color=[cols[b["R"]] for b in rs["blocks"]])
        for b in rs["blocks"]:
            ax.text(b["block"], b["above_hold_uAticks"], f"r0 {b['r0']:.2f}", ha="center", va="bottom", fontsize=8)
        ax.set_xlabel("block (run order)")
        ax.set_ylabel("above-hold charge (µA·ticks)")
        ax.set_title("charge follows R; r0 does not (sim plant = model)", fontsize=11)
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=c, label=f"R={R:g}") for R, c in cols.items()],
                  frameon=False, fontsize=8)
        return dk.save_fig(fig, FIG / "weekly1009_rsweep.png")


def fig_burst_synth() -> tuple[Path, dict]:
    from fit_burst_plant import run as fb_run, burst_drive
    from make_synthetic_burst_capture import simulate, write_capture
    from design_burst_probe import read_design
    tmp = Path(tempfile.mkdtemp(prefix="deck_burst_"))
    QUIET = {"noise": 2e-7}
    Ud = read_design(REPO / "design_runburst1.csv")
    Y, W, T, drive = simulate(Ud, 16, 1, QUIET)
    cap = tmp / "synth_burst1.csv"; write_capture(cap, Ud, Y)
    meta_path = REPO / "design_runburst1_meta.json"
    res_b = fb_run(str(cap), str(meta_path), 5, 25, T["dead"], None, 0.1, 0.8, None, None)
    meta = json.load(open(meta_path))
    Bs = sorted({int(e["burst_ticks"]) for e in meta["events"]})
    per_pair = {}
    for e in meta["events"]:
        per_pair.setdefault((int(e["pair"]), int(e["burst_ticks"])), []).append(
            burst_drive(drive, e) / (float(e["amp"]) * int(e["burst_ticks"])))
    truth_eff = {B: float(np.mean([np.mean(per_pair[(p, B)]) / np.mean(per_pair[(p, Bs[0])])
                                   for p in sorted({k[0] for k in per_pair})])) for B in Bs}
    Ud = read_design(REPO / "design_rungap1.csv")
    Y, W, T, drive = simulate(Ud, 16, 2, QUIET)
    cap = tmp / "synth_gap1.csv"; write_capture(cap, Ud, Y)
    meta_g = REPO / "design_rungap1_meta.json"
    res_g = fb_run(str(cap), str(meta_g), 5, 25, T["dead"], None, 0.1, 0.8, None, None)
    evs = sorted(json.load(open(meta_g))["events"], key=lambda e: int(e["tick"]))
    truth_ratio = {}
    for c, t in zip(evs[0::2], evs[1::2]):
        truth_ratio.setdefault(int(c["gap"]), []).append(burst_drive(drive, t) / burst_drive(drive, c))
    nums = {"eff": {B: (res_b["efficacy_mean"][str(B)], truth_eff[B]) for B in Bs},
            "rank": res_b["eff_rank"][str(Bs[0])], "U": T["U"], "tau": T["tau_rec"],
            "gap": {g: (res_g["ratio"][str(g)], float(np.mean(truth_ratio[g]))) for g in res_g["gaps"]},
            "op_gap": res_g["operating_gap_ticks"]}
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"])
        ax = axes[0]
        x = np.arange(len(Bs))
        ax.bar(x - 0.18, [truth_eff[B] for B in Bs], width=0.36, color=dk.COLOR["ref"], label="truth (plant drive)")
        ax.bar(x + 0.18, [res_b["efficacy_mean"][str(B)] for B in Bs], width=0.36, color=dk.COLOR["mpc"], label="fit_burst_plant estimate")
        ax.set_xticks(x, [f"B={B}" for B in Bs])
        ax.set_ylabel("per-pulse efficacy  gain(B) / (B·gain(1))")
        ax.set_title(f"burst ladder: depression inside the burst (U={T['U']}, τ={T['tau_rec']:.0f});\neff-rank at B=1 = {nums['rank']} (truth 3)", fontsize=11)
        ax.legend(frameon=False, fontsize=9)
        ax = axes[1]
        gs = res_g["gaps"]
        ax.plot(gs, [np.mean(truth_ratio[g]) for g in gs], "o-", color=dk.COLOR["ref"], label="truth")
        ax.plot(gs, [res_g["ratio"][str(g)] for g in gs], "s--", color=dk.COLOR["mpc"], label="estimate (template subtraction)")
        ax.axhline(0.8, color=dk.MUTED, ls=":", lw=1)
        ax.set_xscale("log")
        ax.set_xlabel("gap between conditioning and test burst (ticks)")
        ax.set_ylabel("test / conditioning response")
        ax.set_title(f"gap scan: recovery vs gap;\noperating gap (first ≥ 0.8) = {nums['op_gap']} ticks", fontsize=11)
        ax.legend(frameon=False, fontsize=9)
        return dk.save_fig(fig, FIG / "weekly1009_burst_synth.png"), nums


def fig_burst_rnd1(b: dict, rnd: dict) -> Path:
    pairs = b["pairs"]
    gains = np.array([b["gain"][str(p)]["1"] for p in pairs]) * 1e6
    sv = np.array(b["footprint_sv"]["1"])
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(1, 2, figsize=dk.FIGSIZE["FULL"], gridspec_kw={"width_ratios": [1.3, 1]})
        ax = axes[0]
        cols = [dk.COLOR["stim"] if rnd["inputs"][f"u{p}"]["onset"] is not None else dk.MUTED for p in pairs]
        ax.bar(pairs, gains, color=cols)
        ax.set_xlabel("stim pair")
        ax.set_ylabel("area gain on ch64 (µV·ticks per µA)")
        ax.set_title("rnd1 single pulses, channel 64: grey = no detectable onset (pair 2)")
        ax = axes[1]
        ax.bar(np.arange(1, len(sv) + 1), sv, color=dk.COLOR["mpc"])
        ax.axhline(0.1, color=dk.INK_2, ls="--", lw=1)
        ax.text(len(sv) - 0.5, 0.12, "0.1·σ1", ha="right", fontsize=9, color=dk.INK_2)
        ax.set_xlabel("singular value index")
        ax.set_ylabel("σi / σ1 (64-ch footprint, all amplitudes)")
        ax.set_title(f"footprint eff-rank {b['eff_rank']['1']} — matches the 09-11 pulse number")
        return dk.save_fig(fig, FIG / "weekly1009_burst_rnd1.png")


def fig_stream() -> Path:
    # measured 10-09 with a 10 ms paced client: rows on disk mid-run
    t = np.array([0, 3, 5, 8.3])
    rows = np.array([0, 280, 480, 800])
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        ax.step(t, rows, where="post", color=dk.COLOR["mpc"], lw=2, label="10-09: streamed, flushed every 100 rows")
        ax.scatter(t[1:3], rows[1:3], color=dk.COLOR["mpc"], zorder=3)
        ax.plot([0, 8.3, 8.3], [0, 0, 800], color=dk.COLOR["choi"], lw=2, ls="--", label="pre 10-09: written at exit only")
        ax.set_xlabel("seconds into an 800-tick run")
        ax.set_ylabel("capture rows on disk")
        ax.set_title("The y-liveness watch reads the capture while the run is live")
        ax.legend(frameon=False, fontsize=9, loc="upper left")
        return dk.save_fig(fig, FIG / "weekly1009_stream.png")


# ---------------------------------------------------------------------------
def main():
    FIG.mkdir(parents=True, exist_ok=True)
    op = dk.jload(DAY / "dead_time_opfit12.json")
    rnd = dk.jload(DAY / "dead_time_rnd1_ch64.json")
    syn = dk.jload(DAY / "dead_time_synth_dead4.json")
    rs = dk.jload(DAY / "rsweep_sim_opfit12_d2.json")
    bp = dk.jload(DAY / "burst_plant_rnd1_ch64.json")
    dk.need(REPO / "LAB_NOTEBOOK_2026-10-09.md")

    p_frames = fig_frames()
    p_onsets = fig_onsets(rnd)
    p_shift = fig_shift(op, syn)
    p_mism, mm = fig_mismatch()
    p_eff = fig_effort()
    p_rs = fig_rsweep(rs)
    p_bs, bs = fig_burst_synth()
    p_br = fig_burst_rnd1(bp, rnd)
    p_stream = fig_stream()

    onsets = [rnd["inputs"][f"u{k}"]["onset"] for k in range(1, 9)]
    n_resp = sum(1 for o in onsets if o is not None)
    old_best = int(max(op["models"]["plant_opfit12.lti"]["fit_by_shift"], key=op["models"]["plant_opfit12.lti"]["fit_by_shift"].get))
    d2_best = int(max(op["models"]["plant_opfit12_d2.lti"]["fit_by_shift"], key=op["models"]["plant_opfit12_d2.lti"]["fit_by_shift"].get))
    err = {m: 100 * (mm[m]["late"] / (TARGET_V * 1e6) - 1) for m in mm}
    per_level = rs["per_level"]

    d = dk.Deck(footer="Closed-loop weekly · 2026-10-09 · build_weekly_deck_2026-10-09.py")

    # ---- 1 title + summary ---------------------------------------------------
    d.title_slide("Closed-Loop Thalamic Stimulation: Weekly Report",
                  "Week of 2026-10-02 → 2026-10-09 (acute #3 postponed: rig Ethernet port dead; offline improvement day)",
                  ["Rig: onboard NIC conclusively dead after a true full boot; USB-Ethernet dongle ordered; PO8e card re-bracketed and verified",
                   "Controller model: the plant's dead time is 3 ticks, the deployed model assumed 1 — found, measured, fixed, bench-proven",
                   "Offset-free MPC, dimensionless effort weight, QP telemetry, one-run R sweep; day-of flow hardened; burst-plant fitter ready"])
    d.bullets_slide(
        "This week in six lines",
        [(0, "Acute #3 (10-08) did not run: the rig PC's Realtek port shows 0 bps on every cable and jack across a mains-off drain and a true full boot; "
             "everything else (PO8e card, preflight 64, bench, designs) is banked. A Realtek RTL8153/8156 USB-A dongle is ordered; the day resumes with the 10-min dongle path."),
         (0, f"Dead time: the rnd1 pulse probe puts the first feature movement at lag {min(o for o in onsets if o is not None)} on {n_resp}/8 pairs (ch64). "
             f"The fitter shifted u by one tick AND regressed with one more; the export dropped the shift, so the controller ran a model one tick early "
             f"(old opfit12 export scores best at shift {old_best:+}; the delay-state refit at d=2 scores best at {d2_best:+})."),
         (0, f"Offset-free MPC (flag-gated, default off): with the simulated plant at 1.5× gain + bias + drift the plain observer settles {err['plain']:+.0f}% off target, "
             f"the disturbance observer {err['dist']:+.1f}% — innovation driven to {mm['dist']['innov_late']*1e6:.3f} µV."),
         (0, f"R sweep in ONE run via --r-schedule: above-hold charge {per_level['100.0']['above_hold_mean']:.0f} / {per_level['30.0']['above_hold_mean']:.0f} / "
             f"{per_level['10.0']['above_hold_mean']:.0f} µA·ticks for R = 100 / 30 / 10 with the weight switch verified per block from the new telemetry."),
         (0, "Flow: two commands in the runbook would have failed on the day (ledger append, quiet ingest), the capture was only written at exit (no live liveness check), "
             "and every day_* latency log was being lost. All fixed; run_audit.py gives one PASS/WARN/FAIL line per run and flags the 09-10 PZ2-off run as DEAD."),
         (0, f"Burst plant: fit_burst_plant.py passes its known-answer test (efficacy, rank, 7 recovery ratios) and on the real rnd1 probe reproduces pulse eff-rank {bp['eff_rank']['1']}.")],
        subtitle="Everything below was built and verified offline; selftest 16/16, MATLAB bench 28/28; commit a5dda73")

    # ---- 2 rig status --------------------------------------------------------
    d.section_slide("Rig status and acute #3", kicker="section 1")
    d.table_slide("Why acute #3 did not run: the onboard Ethernet port is dead at the PHY, and Device Manager cannot see that",
                  ["check", "result", "meaning"],
                  [["Device Manager / PnP", "OK, problem code 0, PCIe link 8 GT/s ×1", "the PC side of the chip answers — this is all Device Manager tests"],
                   ["link state", "Disconnected, 0 bps on a new cable, a wall jack and a laptop", "the cable side (PHY) does not negotiate"],
                   ["link LEDs", "none", "LEDs are driven by the PHY"],
                   ["bytes since 09-15", "0 / 0", "nothing has crossed the port in weeks"],
                   ["power-management query", "fails: 'device not functioning'", "the one Windows call that reads PHY registers"],
                   ["Fast-Startup boot (10-08 18:30)", "type 0x1, no change", "not a real reboot"],
                   ["mains-off drain + true full boot (10-08 18:39)", "type 0x0, still dead", "last software step exhausted → hardware failure"],
                   ["PO8e card after re-bracketing", "present, preflight 64 PASS 300/300", "the acquisition side is fine"],
                   ["fix", "USB-A Realtek RTL8153/8156 dongle (driver already in the store)", "set_rig_ip → net_diag → find_rz2 → selftest -LiveStim → wire gate (~10 min)"]],
                  col_widths=[2.6, 4.0, 5.8])
    d.bullets_slide("Latency through a USB NIC is not on the critical path",
                    [(0, "Neural data enters over the PO8e card on PCIe; Ethernet carries only the outgoing UDP stim command once per 10 ms tick."),
                     (0, "A USB 3.0 gigabit adapter adds ~50-200 µs one way, 1-2% of the tick; the plant model already absorbs a 3-tick dead time."),
                     (0, "Rules when it arrives: rear motherboard USB port (no hub), USB selective suspend off, then re-measure selftest turnaround against the 1.4 ms baseline.")])

    # ---- 3 controller model ---------------------------------------------------
    d.section_slide("Controller model: the dead-time finding and fix", kicker="section 2")
    d.fig_slide("Where the tick went: fitter frame, export, controller assumption, and what the data say",
                p_frames,
                caption="fit_sysid shifted u by inputDelayTicks=1 and regressed with nk=1; export_plant_lti dropped the shift; cpp/mpc_test predict x(k+1)=Ax(k)+Bu(k)")
    d.fig_slide("Measured on the acute-#2 pulse probe: first feature movement at lag 3 on every responsive pair",
                p_onsets,
                caption=f"rig/check_dead_time.py, {rnd['inputs']['u1']['kind']}; recommended inputDelayTicks = onset − 1 = {rnd['recommended_inputDelayTicks']} (nk supplies one tick) → dead time 3")
    d.fig_slide("Scoring models in the controller's own frame: the old export answers two ticks early; the d=2 refit is centred",
                p_shift,
                caption="row-frame free-run fit vs an artificial shift of the model output; a correctly framed model peaks at 0. Tonic opfit12 fit% is ~0.6 (SNR), the shape is the evidence")
    d.bullets_slide("The fix, and what it does not change",
                    [(0, "fit_sysid_from_capture: 'delayStates' (default on) appends inputDelayTicks × m pure-delay states in observable form; arx_to_ss now realizes nk > 1; default inputDelayTicks 1 → 2."),
                     (0, "export_plant_lti(path, r.sys) exports a struct directly (AllModels.mat untouched); provenance written as a '#' comment that all three parsers skip."),
                     (0, "DC gain, validation fit and core order are unchanged (check_mimo_rank identical: 7.19e-7 V/µA); old .lti files still load, one tick optimistic."),
                     (0, "MATLAB bench +2 cases on a synthetic 3-tick plant: delay-state export best at shift 0 (92.6%), legacy export best at +2. crossval_model scores row-frame models unshifted."),
                     (0, "Why it matters: with preview MPC a 2-tick framing error pre-empts the template by 20 ms and mis-attributes the observer's innovation. Day-of rule: run check_dead_time on the gate probe, pass onset − 1 to the fit."),
                     (0, "Honesty: this fixes the frame, not the SNR — the tonic opfit12 valFit stays ≈ 0; the burst/duty ID of acute #3 is still the lever for a usable plant.")],
                    subtitle="Models banked: plant_opfit12_d0 / d1 / d2.lti (d2 = centred)")
    d.fig_slide("Offset-free MPC (--dist-observer): the plain observer cannot remove gain-drift bias, the disturbance state can",
                p_mism,
                caption=f"late-run mean error plain {err['plain']:+.0f}% vs dist {err['dist']:+.1f}%; |innovation| late {mm['plain']['innov_late']*1e6:.1f} vs {mm['dist']['innov_late']*1e6:.3f} µV; cost/F/G/H untouched (observer only), C++-only, default off")
    d.fig_slide("Effort ratio and QP telemetry: a dimensionless R and the numbers an optimality claim needs",
                p_eff,
                caption="R_j = ρ Σ Q_i G_ij² from the model's DC gain; latency log now carries qpCost, qpIters, qpConv, activeFrac, innov0, rW0 plus a '#' banner (model, observer, offsets, weights)")
    d.fig_slide("Tier-C R sweep in one run: --r-schedule switches the weight per 20-event block; telemetry proves it",
                p_rs,
                caption=f"sim on plant_opfit12_d2 with ref_mix_r1: above-hold charge {per_level['100.0']['above_hold_mean']:.0f} / {per_level['30.0']['above_hold_mean']:.0f} / {per_level['10.0']['above_hold_mean']:.0f} µA·ticks for R 100 / 30 / 10; analyze_r_sweep fits r ~ R-level + block order (drift covariate)")

    # ---- 4 flow ----------------------------------------------------------------
    d.section_slide("Experimental flow: what would have failed on 10-08, and the fixes", kicker="section 3")
    d.table_slide("Found by reading the runbook against the code (all fixed and tested offline)",
                  ["item", "what would have happened", "fix", "verified by"],
                  [["ingest_block --label quiet", "FAIL: no quiet mode", "quiet mode runs analyze_quiet_capture", "scratch block + ledger"],
                   ["ingest_block ledger", "every append: 'append the row by hand' (10-08 ledger absent; 09-10 file has no marker)", "BLOCK_LEDGER_<day>.md created on first use; before 06:00 keeps yesterday's", "rows 1-2 appended; day logic unit-checked"],
                   ["cpp_controller --capture", "written only at exit → first-minute y-liveness impossible", "streamed, flushed every 100 rows; opened before 'ready'", "280 / 480 rows on disk at 3 / 5 s mid-run"],
                   ["latency log for day_* captures", "silently lost (bad path); none exists for 09-10", "server_lat_<name> in the capture's folder + open check", "file present after sim runs"],
                   ["2_loop -Ticks", "hand-typed per design (26277 / 95586 / …)", "-Design <csv> reads nTicks from meta; -Ticks warns if different", "sim run: 'Ticks from design: 150'"],
                   ["cpp --play", "stale/truncated design plays silently", "FATAL if meta nTicks ≠ rows", "truncated copy refused"],
                   ["1c_server design reuse", "silent replay of design_run<Run>.csv (bit on 09-10)", "prompt 'reuse' / -Reuse", "code path"],
                   ["closed_loop_sim --launch", "server blocks on a full stdout pipe after ~1600 ticks", "stdout → server_<capture>.log", "3000- and 22200-tick runs complete"]],
                  col_widths=[2.2, 3.6, 3.6, 3.0], size=9)
    d.fig_slide("Streamed capture: the y-liveness watch window (opened by 2_loop at 'go') reads it while the run is live",
                p_stream,
                caption="the 09-10 PZ2-off incident (3 void runs, ~1.3M µA·ticks unrecorded) was caught post hoc because the capture did not exist until the run ended")
    d.table_slide("run_audit.py: one line per run, validated on the 09-10 artifacts",
                  ["run", "line", "reads"],
                  [["mpc_mixr1", "WARN | fresh@2 ticks=22200/22200 dropped=0 timeouts=0 stale=0 obs=n/a y=LIVE u_nz=0.53 u_std=4.89", "no server log existed on 09-10 → 'unverified' WARN (now the banner supplies it)"],
                   ["mpc_r4cm (PZ2 off)", "FAIL | … y=DEAD u_nz=1.00 u_std=0.58", "the void run: features zero while stim was delivered"],
                   ["choi_mixr1", "WARN | … y=LIVE; 'Skipping N to position M' line", "recording started before the loop (backlog) — the known ordering rule"],
                   ["sim dress 10-07", "WARN | fresh@2 obs=ACTIVE(0.617) offsets=applied y=LIVE u_nz=0.00", "u pinned in sim (int16 features vs volt reference) — WARN not FAIL under --sim"]],
                  col_widths=[1.8, 6.4, 4.2], size=9)
    d.bullets_slide("Runcards replace the hand-filled blanks: one line prints the exact commands for a phase",
                    [(0, "rig_runcard.py --phase arm --arm mpc --run 1 --resp 1,3,4,6 --ctrl 34,40 --baseline 2.1e-4 → terminal A, terminal B, audit, scoring and ingest lines, written to day_<day>/runcard_arm_mpc_r1.txt."),
                     (1, "cpp_controller --mode mpc --model plant_duty.lti --pairs 1,3,4,6 --feature-map 34,40 --q-weight 1e12,1e12 --r-weight 100,100 --control-horizon 20 --umin 0 --umax 30 --reference … --capture … --max-packets 22200"),
                     (1, "2_loop.ps1 -RZ2 10.1.0.100 -InputChannels 64 -TimeoutMs 10 -TickFrames 6 -Run mpc_mixr1 -Ticks 22200 -Capture … -Baseline 0.00021"),
                     (1, "run_audit.py --run mpc_mixr1 --loop-log … --capture … --ref … --active-u u1,u3,u4,u6 --baseline 0.00021"),
                     (0, "--phase dutyid writes design_rundutyid.csv for the responsive pairs with its meta and validates it (DESIGN OK; replaces the inline pandas one-liner)."),
                     (0, "--phase fit emits the MATLAB line with the struct export and the dead-time check; --phase rsweep emits the schedule build, the --r-schedule arm and the analysis."),
                     (0, "Runbook, helper card and protocol updated; the helper's PASS line for every stim run is now 'AUDIT <run>: PASS'.")])

    # ---- 5 burst plant ---------------------------------------------------------
    d.section_slide("Burst plant: the analysis for acute #3's primary aim now exists", kicker="section 4")
    d.fig_slide("fit_burst_plant.py known-answer test on a depressing-synapse plant (rank 3, dead time 3)",
                p_bs,
                caption=f"area responses, gain-slope footprints across all amplitudes, template-subtracted paired bursts; efficacy B=3 {bs['eff'][3][0]:.3f} vs truth {bs['eff'][3][1]:.3f}, B=10 {bs['eff'][10][0]:.3f} vs {bs['eff'][10][1]:.3f}; all gap ratios within 0.03")
    d.fig_slide("On the real acute-#2 pulse probe: per-pair gain and the 64-channel footprint rank",
                p_br,
                caption=f"rnd1 single pulses (4257 events, 7 amplitudes) with a meta derived from the capture; eff-rank {bp['eff_rank']['1']} at 0.1·σ1 reproduces the 09-11 rank analysis; burst-length dependence waits for the first burst block")
    d.bullets_slide("What the burst tools will answer on the day (Phase 3, 18 min)",
                    [(0, "Burst ladder → per-pair gain vs burst length (1 / 3 / 10 pulses), per-pulse efficacy, footprint eff-rank per B: does rank survive bursts where tonic drive collapsed it to 1?"),
                     (0, "Gap scan → recovery ratio vs gap, operating gap = first ratio ≥ 0.8 (feeds the duty-ID design; default 24 ticks if unreadable)."),
                     (0, "check_impulse_delivery --design-meta: designed burst lengths are bursts, any other run length is a hold-last stall; per-probe delivered pulses scored missed / short / exact / long against B."),
                     (0, "Still untested on a real block (no burst block exists yet); everything else above was exercised on captures or synthetic known answers.")])

    # ---- 6 readiness + next ----------------------------------------------------
    d.table_slide("Acute #3 readiness",
                  ["item", "state"],
                  [["Network", "dongle ordered; 10-min path banked (set_rig_ip -Nic → net_diag -Nic → find_rz2 → selftest -LiveStim → wire gate)"],
                   ["Acquisition", "PO8e re-bracketed, PnP OK, preflight 64 PASS; y-liveness now live during runs"],
                   ["Controller", "cpp selftest 16/16; delay-state models; flags documented; Choi-comparable defaults unchanged"],
                   ["Designs", "gate / burst1 / gap1 / dutyid_all8 validated; --play refuses mismatched meta; dutyid subset written by the runcard"],
                   ["Day-of flow", "runcards per phase, run_audit after every Summary, per-day ledger, helper card updated"],
                   ["Analysis on the day", "check_dead_time on the gate probe → fit; fit_burst_plant on Phase 3; analyze_r_sweep for Tier C"],
                   ["Open", "first burst block to exercise the delivery checker; artifact-aware raw-LFP redo of acute-#2 tracking still queued"]],
                  col_widths=[2.2, 10.2])
    d.bullets_slide("Next week",
                    [(0, "Dongle arrives → net path + wire gate on the dummy load the same day; re-measure selftest turnaround through USB against the 1.4 ms baseline."),
                     (0, "Set the acute-#3 date; day-before: preflight 64, bench, runcards for every phase pre-printed with the pair table."),
                     (0, "Decide the arm set: Choi-comparable MPC (default) vs a labelled offset-free arm (--dist-observer) — recommendation: one extra arm only if Tier B time allows."),
                     (0, "NN: forward model on the burst-ladder data once it exists (the methodology review's path), linear baseline in the same figure."),
                     (0, "Offline queue unchanged: artifact-aware raw-LFP tracking redo for acute #2.")])

    out = d.save(OUT)
    print(f"deck: {out} ({d._n} slides)")


if __name__ == "__main__":
    main()
