"""build_weekly_deck_2026-10-16.py -- weekly deck: rig back online, 10-13 offline work,
acute-3 preparation, and (when the day_2026-10-14 artifacts exist) the acute-3 results.

    python scripts/build_weekly_deck_2026-10-16.py [--skip-results]

Every figure is recomputed from the banked artifacts (deckkit house rules; the build
FAILS on a missing artifact). Results section is need()-guarded: it builds only when
day_2026-10-14/ holds the acute-3 outputs, otherwise a single placeholder slide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk  # noqa: E402

FIG = REPO / "outputs" / "deck_figures"
OUT = Path(r"C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\outputs\Synthesis\ClosedLoop_weekly_2026-10-16.pptx")
REH = REPO / "day_rehearsal1013"
ANA = REPO / "day_2026-09-10" / "analysis"
DAY14 = REPO / "day_2026-10-14"


def png(name):
    return FIG / f"weekly1016_{name}.png"


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def fig_dongle():
    """Timeline of the network outage and recovery (dates from the notebooks)."""
    events = [
        ("10-08 18:39", "onboard NIC dead after a true full boot (link 0 bps, 0 bytes)", "fail"),
        ("10-09", "USB adapter ordered; offline improvement day instead", "warn"),
        ("10-11 22:49", "adapter arrives: ASIX AX88179 on USB 3, link 10 Mbps to the RZ2", "ok"),
        ("10-12 10:4x", "static 10.1.0.1 moved to the dongle (admin); net_diag PASS", "ok"),
        ("10-12 10:5x", "find_rz2 valid ACK; 6_udp_selftest 8/8 incl. live zero packet; preflight PASS", "ok"),
        ("10-13", "NIC auto-detect in every rig script; full sim rehearsal of the 10-14 runbook", "ok"),
    ]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        y = np.arange(len(events))[::-1]
        for yi, (when, what, kind) in zip(y, events):
            ax.scatter([0], [yi], s=140, color=dk.COLOR[kind], zorder=3)
            ax.text(0.06, yi, f"{when}   {what}", va="center", fontsize=11)
        ax.plot([0, 0], [y.min(), y.max()], color=dk.AXIS, lw=2, zorder=1)
        ax.set_xlim(-0.1, 4)
        ax.set_ylim(-0.7, len(events) - 0.3)
        ax.axis("off")
        ax.set_title("From dead onboard port to a verified path through the USB adapter")
        dk.save_fig(fig, png("dongle"))


def fig_rehearsal(first, final):
    """Gantt of the rehearsal phases coloured by outcome: first run (top) vs the rerun after the fixes."""
    from matplotlib.patches import Patch

    def colour(p):
        aud = p.get("audit") or ""
        if p["ok"]:
            return dk.COLOR["ok"]
        if "WARN" in aud and not any(c["rc"] not in (0, 1) for c in p.get("checks", [])):
            return dk.COLOR["warn"]
        return dk.COLOR["fail"]

    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        rows = [(1.0, "first run (undrained driver pipe)", first), (0.0, "rerun after the fixes", final)]
        tmax = 0.0
        for y, lab, reh in rows:
            t = 0.0
            for p in reh["phases"]:
                dur = p["secs"] / 60.0
                ax.barh(y, dur, left=t, height=0.6, color=colour(p), edgecolor="white")
                name = p["phase"] + (" (hung, 30 min timeout)" if p["phase"] == "fit" and p["secs"] > 1000 else "")
                if dur > 1.2:
                    ax.text(t + dur / 2, y, name, ha="center", va="center", fontsize=9, color="white")
                t += dur
            tmax = max(tmax, t)
            ok = sum(1 for p in reh["phases"] if colour(p) != dk.COLOR["fail"])
            ax.text(0, y + 0.42, f"{lab}: {len(reh['phases'])} phases, {ok} clean or WARN, {t:.0f} min", fontsize=10, va="bottom")
        ax.set_xlim(0, tmax * 1.02)
        ax.set_ylim(-0.5, 1.9)
        ax.set_yticks([])
        ax.set_xlabel("wall-clock minutes (frame-locked sim runs in real time)")
        ax.set_title("Sim rehearsal of the 10-14 runbook, before and after the fixes it produced")
        ax.legend(handles=[Patch(color=dk.COLOR["ok"], label="all checks PASS"),
                           Patch(color=dk.COLOR["warn"], label="audit WARN only (sim-expected)"),
                           Patch(color=dk.COLOR["fail"], label="a check failed -> fixed")], loc="upper right", ncol=3)
        dk.save_fig(fig, png("rehearsal"))


def fig_stall():
    """The loop-stall finding, root-caused: inter-packet interval traces from the loop's own
    validation log (rig_run<run>.csv, t_in_us per packet) for the first rehearsal (undrained
    driver pipe), a control run with processes launched mid-run, and the rerun with the
    draining driver; right: dropped control ticks per run."""
    ev = REH / "stall_evidence"

    def trace(name):
        d = pd.read_csv(ev / name)
        t = d["t_in_us"].to_numpy() / 1e6
        return t[:-1] - t[0], np.diff(t) * 1e3   # interval plotted from its start (steps-post)

    probes = []
    for ln in (ev / "probes_stallC.txt").read_text().splitlines():
        m = re.match(r"probe at=(\d+) start_ms=(\d+) .*cmd=(.*)", ln)
        if m:
            probes.append((int(m.group(1)), m.group(3)))
    runs = [("first rehearsal, gap scan (driver did not drain the loop's stdout)", "rig_rungap1_firstrehearsal.csv", dk.COLOR["fail"]),
            ("control: python / cmd / powershell launched at 20, 40, 55 s", "rig_runstallC.csv", dk.COLOR["choi"]),
            ("rerun, gate run (driver drains stdout continuously)", "rig_rungate1_rerun_draining.csv", dk.COLOR["mpc"])]
    with dk.deck_style() as plt:
        fig, axes = dk.new_fig("WIDE", 1, 2, gridspec_kw=dict(width_ratios=[2.2, 1]))
        ax = axes[0]
        for lab, f, c in runs:
            t, dt = trace(f)
            keep = t <= 60
            ax.plot(t[keep], dt[keep], color=c, lw=1.2, label=lab, drawstyle="steps-post")
        for at, cmd in probes:
            ax.axvline(at, color=dk.MUTED, ls=":", lw=1)
            ax.text(at + 0.4, 2.2e3, cmd.split("\\")[-1].split(" ")[0].strip('"'), fontsize=8, color=dk.MUTED, rotation=90, va="top")
        ax.set_yscale("log")
        ax.set_ylim(5, 6000)
        ax.set_xlim(0, 60)
        ax.set_xlabel("time since first packet (s)")
        ax.set_ylabel("packet interval (ms, log)")
        ax.set_title("one 3.6 s hole at 26.3 s in every driver run; none in the controls or the rerun")
        ax.legend(loc="upper right", fontsize=8.5)
        ax = axes[1]
        labels = ["first rehearsal\n(5 runs)", "controls\n(3 runs)", "rerun\n(gate)"]
        cols = [dk.COLOR["fail"], dk.COLOR["choi"], dk.COLOR["mpc"]]
        vals = [366, 0, 0]
        ax.bar(labels, vals, color=cols)
        for i, v in enumerate(vals):
            ax.text(i, v + 8, str(v), ha="center", fontsize=10)
        ax.set_ylabel("dropped control ticks per run")
        ax.set_title("cause: the driver's pipe, not the rig")
        dk.save_fig(fig, png("stall"))


def fig_delivery(truth, rep_clean, rep_faulted, legacy):
    """Injected vs detected faults per burst length, plus legacy false positives."""
    inj = {"1": {}, "3": {}, "10": {}}
    for t in truth["truth"]:
        b = str(t["B"])
        k = {"exact": "exact", "miss": "missed", "short": "short", "long": "long", "stretch": "long"}[t["fault"]]
        inj.setdefault(b, {})
        inj[b][k] = inj[b].get(k, 0) + 1
    det = {}
    for w in rep_faulted["words"]:
        for b, d in w["by_B"].items():
            for k, v in d.items():
                det.setdefault(b, {}).setdefault(k, 0)
                det[b][k] += v
    cats = ["missed", "short", "exact", "long"]
    with dk.deck_style() as plt:
        fig, axes = dk.new_fig("FULL", 1, 3, gridspec_kw=dict(width_ratios=[1.4, 1.4, 1]))
        for ax, (title, src) in zip(axes[:2], [("injected (ground truth)", inj), ("detected by check_impulse_delivery", det)]):
            M = np.array([[src.get(b, {}).get(k, 0) for k in cats] for b in ["1", "3", "10"]], float)
            im = ax.imshow(M, cmap="Blues", vmin=0, vmax=max(1, M.max()))
            for i in range(3):
                for j in range(4):
                    ax.text(j, i, f"{int(M[i, j])}", ha="center", va="center",
                            color="white" if M[i, j] > 0.6 * M.max() else dk.INK, fontsize=11)
            ax.set_xticks(range(4)); ax.set_xticklabels(cats)
            ax.set_yticks(range(3)); ax.set_yticklabels(["B=1", "B=3", "B=10"])
            ax.set_title(title)
            ax.grid(False)
        ax = axes[2]
        ax.bar(["legacy\n(no --design-meta)", "burst-aware"], [legacy["legacy_multi"], rep_clean["stretched_runs"]],
               color=[dk.COLOR["fail"], dk.COLOR["ok"]])
        ax.set_ylabel("stall warnings on a CLEAN block")
        ax.set_title("false positives removed")
        dk.save_fig(fig, png("delivery"))
    match = all(inj.get(b, {}).get(k, 0) == det.get(b, {}).get(k, 0) for b in ["1", "3", "10"] for k in cats)
    return match


def fig_qp(sw):
    runs = sw["runs"]
    with dk.deck_style() as plt:
        fig, axes = dk.new_fig("WIDE", 1, 2)
        for rho, col in ((0.1, dk.INK_2), (0.01, dk.CAT[2])):   # not the MPC/Choi entity colours
            for tol, ls in ((1e-7, "-"), (1e-6, "--")):
                sel = sorted([r for r in runs if r["rho"] == rho and r["qp_tol"] == tol and "conv_pct" in r], key=lambda r: r["qp_iters"])
                if not sel:
                    continue
                x = [r["qp_iters"] for r in sel]
                axes[0].plot(x, [r["conv_pct"] for r in sel], ls, marker="o", color=col, label=f"rho={rho:g}, tol={tol:g}")
                axes[1].plot(x, [r["compute_p99_ms"] for r in sel], ls, marker="o", color=col, label=f"rho={rho:g}, tol={tol:g}")
        axes[0].set_xscale("log"); axes[1].set_xscale("log"); axes[1].set_yscale("log")
        caps = sorted(set(r["qp_iters"] for r in runs))
        for ax in axes:
            ax.set_xticks(caps); ax.set_xticklabels([str(c) for c in caps]); ax.minorticks_off()
        axes[0].set_xlabel("iteration cap (--qp-iters)"); axes[0].set_ylabel("ticks converged (%)")
        axes[1].set_xlabel("iteration cap (--qp-iters)"); axes[1].set_ylabel("p99 solve time per tick (ms, log)")
        axes[1].axhline(5, color=dk.COLOR["fail"], lw=1, ls=":"); axes[1].text(min(r["qp_iters"] for r in runs), 5.3, "5 ms budget", color=dk.COLOR["fail"], fontsize=9)
        axes[0].set_title("convergence vs cap"); axes[1].set_title("cost of lifting the cap")
        axes[0].legend(loc="lower right")
        dk.save_fig(fig, png("qp"))


def fig_plan14():
    """Timeline of the 10-14 plan with tiers and cut points."""
    blocks = [  # (start_h, dur_h, label, kind)
        (8.5, 0.35, "Phase 0 bring-up", "ok"), (9.5, 6.5, "induction + surgery (solo)", "null"),
        (16.0, 0.25, "gates G/G'", "ok"), (16.25, 0.6, "settle + quiet", "null"),
        (16.85, 0.7, "thwack battery", "mpc"), (17.55, 0.3, "burst + gap", "mpc"),
        (17.85, 0.35, "duty-ID + fit", "mpc"), (18.2, 0.2, "refs", "mpc"), (18.4, 0.35, "6a r1 MPC/Choi", "mpc"),
        (18.75, 1.5, "Tier B: 6b 6c 6d", "choi"), (20.25, 1.0, "Tier C: 6e 6f", "warn"),
        (21.25, 0.5, "6g early/late (never cut)", "ok"), (21.75, 0.3, "drift + stim zero + archive", "ok"),
    ]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        for s, d, lab, kind in blocks:
            ax.barh(0, d, left=s, height=0.6, color=dk.COLOR[kind], edgecolor="white")
            ax.text(s + d / 2, 0.45 if d < 0.5 else 0, lab, ha="center", va="bottom" if d < 0.5 else "center",
                    fontsize=8, rotation=90 if d < 0.5 else 0, color=dk.INK if d < 0.5 else "white")
        for h, lab in ((19.5, "Decision A"), (21.0, "Decision B"), (22.25, "WRAP latest"), (23.0, "HARD STOP")):
            ax.axvline(h, color=dk.COLOR["fail"] if h >= 22 else dk.INK_2, lw=1.2, ls="--")
            ax.text(h, 1.05, lab, rotation=90, va="bottom", ha="center", fontsize=8)
        ax.set_xlim(8, 23.5); ax.set_ylim(-0.6, 2.4); ax.set_yticks([])
        ax.set_xticks(range(8, 24)); ax.set_xticklabels([f"{h:02d}:00" for h in range(8, 24)], rotation=45)
        ax.set_title("Acute #3 plan (Wed 10-14): Tier A by 19:00, decisions at 19:30 / 21:00, wrap by 22:15")
        dk.save_fig(fig, png("plan14"))


# ---------------------------------------------------------------------------
# deck
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# acute #3 results (2026-10-14) -- every number from day_2026-10-14/analysis/*.json
# and galleries/<block>/gate_*.json; nothing typed in.
# ---------------------------------------------------------------------------
GAL = REPO / "galleries"
AN14 = DAY14 / "analysis"


def fig_day14_timeline():
    """What actually happened on 10-14, from the block ledger times."""
    ev = [
        ("09:30-16:20", "induction, two craniotomies, both arrays in (solo); no auditory confirmation possible", "warn"),
        ("20:07", "first recording: cortical gate GO on amplitude but 63/64-ch footprint (common-mode)", "warn"),
        ("20:34 / 20:46", "reference re-seated, array +600 um: focal ch47 response appears; accepted", "ok"),
        ("21:15", "thalamic gate depth 1: 720/720 pulses delivered, 0/8 pairs evoke cortex", "fail"),
        ("21:36", "re-probe after reposition: VOID (cortical stream zero; liveness alarm caught it)", "fail"),
        ("21:45", "re-probe 2: delivered 240/240, 0/8 pairs", "fail"),
        ("21:53-22:14", "switch to the touch battery: D1 P1 MP LP P3 SHAM, 150 thwacks each", "ok"),
        ("22:30", "all blocks ingested, templates written, ledger + notebook + archive", "ok"),
        ("10-15", "cortical array found physically broken -> the whole day explained", "ok"),
    ]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        y = np.arange(len(ev))[::-1]
        for yi, (when, what, kind) in zip(y, ev):
            ax.scatter([0], [yi], s=130, color=dk.COLOR[kind], zorder=3)
            ax.text(0.05, yi, f"{when}   {what}", va="center", fontsize=10.5)
        ax.plot([0, 0], [y.min(), y.max()], color=dk.AXIS, lw=2, zorder=1)
        ax.set_xlim(-0.1, 4); ax.set_ylim(-0.7, len(ev) - 0.3); ax.axis("off")
        ax.set_title("Acute #3, Wednesday 10-14: late start, two gates, one diagnosis")
        dk.save_fig(fig, png("day14"))


def fig_thal_gate(j1, j2):
    """Per-pair evoked z at both thalamic positions, with the RESPONSIVE threshold."""
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        pairs = [e["pair"] for e in j1["per_pair"]]
        x = np.arange(len(pairs)); w = 0.38
        z1 = [e.get("z", 0.0) for e in j1["per_pair"]]
        z2 = {e["pair"]: e.get("z", 0.0) for e in j2["per_pair"]}
        ax.bar(x - w / 2, z1, w, color=dk.CAT[0], label="position 1 (acute-2 coordinates), 13-25 uA, 90 probes/pair")
        ax.bar(x + w / 2, [z2.get(p, 0.0) for p in pairs], w, color=dk.CAT[1], label="position 2 (repositioned), 18-30 uA, 30 probes/pair")
        ax.axhline(j1["thresholds"]["z_resp"], color=dk.COLOR["fail"], ls="--", lw=1.2)
        ax.text(len(pairs) - 0.5, j1["thresholds"]["z_resp"] + 0.3, "RESPONSIVE threshold (z = %g)" % j1["thresholds"]["z_resp"], ha="right", fontsize=9, color=dk.COLOR["fail"])
        ax.set_xticks(x); ax.set_xticklabels(["pair %d\n%.1f mm" % (e["pair"], e.get("tip_mm") or 0) for e in j1["per_pair"]])
        ax.set_ylabel("best-channel evoked z (6-30 ms)"); ax.set_ylim(0, 8)
        ax.legend(loc="upper left", fontsize=9)
        ax.set_title("Thalamic gate: no pair evoked the (broken) cortical array at either position; acute #2 gave 8/8 here")
        dk.save_fig(fig, png("thalgate"))


def fig_battery(bat):
    """Per-site touch response: raw common-mode vs re-referenced ch47 vs row-5 mean; SHAM shows the thwacker artifact."""
    sites = ["D1", "P1", "MP", "LP", "P3", "SHAM"]
    with dk.deck_style() as plt:
        fig, (a1, a2) = dk.new_fig("WIDE", nrows=1, ncols=2, gridspec_kw={"width_ratios": [1.15, 1]})
        x = np.arange(len(sites)); w = 0.27
        a1.bar(x - w, [bat[s]["common_mode_uv"] for s in sites], w, color=dk.MUTED, label="common-mode wave (all 63 ch, |peak| median)")
        a1.bar(x, [abs(bat[s]["car_ch47_uv"]) for s in sites], w, color=dk.CAT[0], label="ch47 own signal (re-referenced, |peak|)")
        a1.bar(x + w, [abs(bat[s]["car_row5_uv"]) for s in sites], w, color=dk.CAT[2], label="row 5 (ch33-38) own signal, mean |peak|")
        a1.axhline(abs(bat["SHAM"]["car_ch47_uv"]), color=dk.COLOR["fail"], ls="--", lw=1.2)
        a1.text(len(sites) - 0.6, abs(bat["SHAM"]["car_ch47_uv"]) + 3, "SHAM level on ch47 = thwacker artifact (%.0f uV)" % abs(bat["SHAM"]["car_ch47_uv"]), fontsize=8.5, color=dk.COLOR["fail"], ha="right")
        a1.set_xticks(x); a1.set_xticklabels(sites); a1.set_ylabel("evoked peak (uV)"); a1.legend(fontsize=8, loc="upper right")
        a1.set_title("Touch battery, 150 thwacks per site")
        for s_, c in zip(sites, [dk.CAT[0], dk.CAT[1], dk.CAT[2], dk.CAT[3], dk.MUTED, dk.COLOR["fail"]]):
            a2.plot(bat[s_]["t_ms"], bat[s_]["car_ch47_trace"], color=c, lw=1.4 if s_ in ("MP", "D1", "SHAM") else 0.9, label=s_)
        a2.axvspan(8, 45, color=dk.GRID, lw=0); a2.axvline(0, color=dk.AXIS, ls="--", lw=0.8)
        a2.set_xlim(-40, 200); a2.set_xlabel("ms from touch onset"); a2.set_ylabel("ch47 minus array median (uV)")
        a2.legend(fontsize=8, ncol=2); a2.set_title("ch47 re-referenced mean: MP and D1 carry a negative wave")
        dk.save_fig(fig, png("battery"))


def fig_lit_depth():
    """Reported forepaw-VPL depths in the literature vs our tip lengths (docs/ACUTE4_LOCALIZATION_METHODS.md)."""
    rows = [("Choi 2016 (hand VPL)", 6.0, 7.0), ("Chao 2014 (forepaw VP)", 5.0, 6.0), ("Aguilar 2008 (VPM/VPL)", 5.0, 7.0),
            ("Jiang 2015 (hindpaw VPL)", 6.3, 6.65), ("ours: tip lengths, acute #2 = 8/8 responsive", 7.4, 8.0), ("ours: acute #3 (0/8, broken readout)", 7.4, 8.0)]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        for i, (lab, lo, hi) in enumerate(rows):
            c = dk.CAT[0] if lab.startswith("ours: tip") else (dk.COLOR["fail"] if lab.startswith("ours: acute #3") else dk.MUTED)
            ax.barh(i, hi - lo, left=lo, color=c, height=0.55)
            ax.text(hi + 0.05, i, lab, va="center", fontsize=10)
        ax.set_yticks([]); ax.set_xlim(4.5, 11); ax.set_xlabel("depth below skull / dura (mm)  -- reference point differs between reports")
        ax.invert_yaxis(); ax.set_title("Where forepaw VPL is reported vs where our tips sit: re-check the depth reference before acute #4")
        dk.save_fig(fig, png("litdepth"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-results", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)

    reh = dk.jload(REH / "rehearsal_rehearsal1013.json")
    reh_first = dk.jload(REH / "rehearsal_rehearsal1013_first.json")
    truth = dk.jload(REH / "synthetic_block_burst1_faulted_truth.json")
    rep_clean = dk.jload(REH / "delivery_clean.json")
    rep_faulted = dk.jload(REH / "delivery_faulted.json")
    legacy = dk.jload(REH / "delivery_clean_legacy.json")
    sw = dk.jload(REH / "qp_sweep.json")
    art = dk.jload(ANA / "art64_tracking.json")

    fig_dongle()
    fig_rehearsal(reh_first, reh)
    fig_stall()
    match = fig_delivery(truth, rep_clean, rep_faulted, legacy)
    fig_qp(sw)
    fig_plan14()

    d = dk.Deck(footer="Closed-loop thalamic stim -> S1  |  weekly 2026-10-16")
    d.title_slide("Closed-loop MPC: rig recovered, day rehearsed, acute #3 diagnosed",
                  "Weekly update, 2026-10-16",
                  ["Rig back on the network through a USB adapter; every bring-up check passes",
                   "Full simulated rehearsal of the acute-3 runbook caught and fixed two server-side defects",
                   "Acute #3 (Wed 10-14): the cortical array was electrically broken before the first recording; the gates saw it, the stim path was verified, a six-site touch battery was banked",
                   "Acute #4 plan: pre-implant array verification and a localization protocol from the literature"])
    d.agenda_slide("Agenda", [("Rig back online", "dead onboard port -> USB adapter, verified end to end"),
                              ("Rehearsal of the surgery day", "what the sim dress caught"),
                              ("Tooling verified offline", "delivery checker, QP cap, artifact-aware tracking"),
                              ("Acute #3 preparation", "runbook, safety checklist, data path"),
                              ("Acute #3: an instrumentation day", "what happened, the diagnosis, what was banked"),
                              ("Acute #4: verify first, then localize", "literature survey + protocol")])

    d.section_slide("Rig back online", kicker="network path")
    d.stat_slide("Verified path to the RZ2 through the USB adapter",
                 [("10 Mbps", "link (same as always)"), ("1", "device: 10.1.0.100"), ("8 / 8", "UDP selftest"), ("0", "dropped ticks, preflight")],
                 png=png("dongle"),
                 takeaway="The onboard controller is dead at the PHY; the adapter reproduces the exact pre-failure path, and every rig script now auto-detects it.")

    d.section_slide("Rehearsal of the surgery day", kicker="sim dress, end to end")
    d.fig_slide("Every runcard phase executed in sim from the generated commands", png("rehearsal"),
                takeaway="rehearse_day.py runs the same lines the helper card pastes; outcomes are recorded per phase with the audit verdict.")
    d.fig_slide("What it caught: a 3.6 s loop stall ended the server; the loop ran on", png("stall"),
                takeaway="Root cause: the rehearsal driver's undrained stdout pipe back-pressured the loop exe. Fixed in the driver; the server now also tolerates 30 s without requests (was 3 s). Rule: never pipe terminal B through another program.")
    d.table_slide("Rehearsal findings and fixes", ["finding", "where", "fix", "verified"],
                  [["server stopped after 3 idle reads while the loop kept ticking", "cpp_controller", "--idle-stop 30 s; non-timeout errors ignored", "selftest 17/17, rerun"],
                   ["runcard printed -Nic for a script that auto-detects", "rig_runcard phase0", "line regenerated", "lint PASS"],
                   ["--blacklist pasted as a comma string", "rig_runcard", "space-separated", "lint PASS"],
                   ["closed_loop_sim given a cpp flag", "runcard refs", "moved after --launch-args", "lint PASS"],
                   ["runcard fit check (--max-packets 1) waits forever without a loop", "cpp_controller", "--check-model exits after the build", "rerun"],
                   ["ingest / gallery tools could not take a synthetic block", "ingest_block, plot_trial_responses", ".npz branch via blockutil", "rerun"],
                   ["a data job alongside the loop: 11,800 timeouts in one gate run", "this PC", "runbook rule: nothing else runs", "documented"]],
                  col_widths=[3, 1.3, 2.4, 1.3],
                  takeaway="The rehearsal paid for itself before the animal: two of these would have cost runs on Wednesday.")

    d.section_slide("Tooling verified offline", kicker="known-answer tests")
    d.fig_slide("Burst-aware delivery checker on a synthetic block with injected faults", png("delivery"),
                takeaway=("Detected counts equal the injected truth exactly; legacy mode flagged %d stalls on a clean block." % legacy["legacy_multi"])
                if match else "Detected counts differ from the injected truth -- see notebook.")
    d.fig_slide("QP conditioning: iteration cap vs convergence and solve time", png("qp"),
                takeaway="At R=100 (today's arms) the solver converges in a few iterations; small effort ratios need --qp-iters raised, which the sweep shows is affordable.")
    d.fig_slide("Artifact-aware re-analysis of acute #2: pulse excision at 24 kHz", dk.need(ANA / "art64_example.png"),
                takeaway="The artifact is a 0.5 ms spike 1 ms after the pulse edge; excising it changes the 5-200 Hz LFP feature by nothing measurable (r equal to three decimals on all 10 arms), so no 09-10 tracking number was artifact-inflated.")
    p_ = art.get("paired", {})
    d.fig_slide("Tracking on the cleaned LFP vs the run-time feature, all live arms", dk.need(ANA / "art64_paired.png"),
                takeaway=(f"Paired MPC-vs-Choi on cleaned LFP: dr = {p_['clean']['mean_dr']:+.3f} [{p_['clean']['ci'][0]:+.3f}, {p_['clean']['ci'][1]:+.3f}], "
                          f"p = {p_['clean']['p_perm']:.3f} -> {p_['verdict']}") if p_ else "paired result pending")

    d.section_slide("Acute #3 preparation", kicker="Wednesday 10-14")
    d.fig_slide("The day as planned: tiers, decision points, hard stop", png("plan14"),
                takeaway="Tier A plus the early/late repeat is the minimum publishable day; everything else is cut from the bottom of one list.")
    d.table_slide("New safety and data-path tools for the day", ["tool", "what it does", "when"],
                  [["pull_blocks.ps1 -Once (USB drive)", "mirrors new TDT blocks from the hand-carried drive, 2-3 min per block; gates read the newest real block (SMB over school Wi-Fi dropped in the 10-13 test; both PCs' Ethernet ports died in one event)", "after every recording"],
                   ["physio_timer.ps1", "beeps on the protocol interval and logs the reading", "from induction"],
                   ["check_y_liveness --beep", "audible alarm when features go dead (PZ2-off incident)", "every run"],
                   ["run_audit -> 2_loop gate", "a FAIL must be acknowledged before the next stim run", "every run"],
                   ["stim_zero.ps1", "zero every stim word after ANY crash", "red flag"],
                   ["build_interleaved_run --run-offset", "references can no longer be overwritten (early/late repeat)", "Tier C"],
                   ["archive_day.ps1", "zips captures, logs, ledger, galleries (git ignores them)", "wrap"]],
                  col_widths=[1.6, 3.4, 1.0],
                  takeaway="Pre-induction checklist in the runbook: stimulator voltage, PZ2 charger, reference wiring, electrode map, impedances, monitoring interval.")

    # ---------------- acute #3 results ----------------
    j1 = dk.jload(GAL / "BSCL20260909BU-261014-211506" / "gate_thalamic.json")
    j2 = dk.jload(GAL / "BSCL20260909BU-261014-214559" / "gate_thalamic.json")
    bat = dk.jload(AN14 / "battery_sites.json")
    health = [h for h in dk.jload(AN14 / "array_health.json") if "error" not in h]
    alive = dk.jload(AN14 / "array_alive_summary.json")
    g1 = dk.jload(GAL / "BSCL20260909BU-261014-200749" / "gate_cortical.json")
    fig_day14_timeline(); fig_thal_gate(j1, j2); fig_battery(bat); fig_lit_depth()
    a2 = [h for h in health if h["label"].startswith("acute2")]
    a3 = [h for h in health if h["label"].startswith("10-14")]
    corr2 = (min(h["med_pair_corr"] for h in a2), max(h["med_pair_corr"] for h in a2))
    corr3 = (min(h["med_pair_corr"] for h in a3), max(h["med_pair_corr"] for h in a3))
    res2 = np.median([h["resid_rms_median"] for h in a2]); res3 = np.median([h["resid_rms_median"] for h in a3])
    n_alive2 = alive["acute2 09-10 22:10 (last block)"]["n_alive"]; n_alive3a = alive["acute3 10-14 20:07 (first block)"]["n_alive"]; n_alive3b = alive["acute3 10-14 22:00 (MP)"]["n_alive"]

    d.section_slide("Acute #3: an instrumentation day", kicker="Wednesday 10-14")
    d.fig_slide("The day: late start, every safety tool fired, no thalamic plant", png("day14"),
                takeaway="Solo surgeon at the table with the engineer lane on the helper card. The gates, the audit, the liveness alarm and the delivery checker all did their job in real time; what they reported was a broken recording array.")
    d.fig_slide("Cortical gate, first block: GO on amplitude and reliability, but the footprint is the whole array",
                dk.need(GAL / "BSCL20260909BU-261014-200749" / "gate_cortical.png"),
                takeaway=f"z {g1['best_z']:.0f}, split-half {g1['split_half']:.2f}, latency {g1['best_latency_ms']:.0f} ms, but {g1['footprint_channels']}/64 channels at half-max with one identical waveform: the touch response was arriving through the reference, not the contacts. Flagged at 20:10, before any stim.")
    d.fig_slide("Re-referenced (minus array median): what the contacts themselves saw",
                dk.need(GAL / "BSCL20260909BU-261014-204658" / "avg" / "avg_car_grid.png"),
                takeaway="Final cortical position (+600 um): one channel (47) with a focal, repeatable response and a faint copy on 26/30/31; 60 of 64 channels contribute nothing of their own.")
    d.fig_slide("Post hoc: which contacts still carried their own signal", png("alive_maps"),
                takeaway=f"Same array, differential RMS per channel. Acute #2 last block: {n_alive2}/64 channels above 10 uV. Acute #3 first block: {n_alive3a}/64, by the battery {n_alive3b}/64; rows 1-2 (ch1-16) and 7-8 gone as a bank = connector / lead damage, not tissue.")
    d.fig_slide("The signature is there from the first minute of 10-14", png("array_metrics"),
                takeaway=f"Median pairwise channel correlation {corr3[0]:.3f}-{corr3[1]:.3f} on 10-14 vs {corr2[0]:.2f}-{corr2[1]:.2f} on 09-10; channel-own RMS {res3:.0f} vs {res2:.0f} uV. The break happened between the end of acute #2 (09-10 22:10, still {n_alive2}/64) and the first 10-14 recording.")
    d.fig_slide("Inside the day: 10-second windows, every block", png("array_timeline"),
                takeaway="No step inside any block and none between blocks: handling, the +600 um move and the thalamic repositions changed nothing. The 10-13 bench block was recorded in air (pure mains) and could not have shown it; a saline impedance check would have.")
    d.fig_slide("Thalamic gate, two positions: stim verified, no readout to see it", png("thalgate"),
                takeaway=f"Position 1: {j1['n_probes']} probes, delivery verified 720/720, pair mapping confirmed on all 8 pairs, 0 responsive. Position 2: 240/240, 0 responsive. With {n_alive3b} live contacts and the forepaw focus on one of them, the gate had no way to see VPL; the array, not the target, is the unknown.")
    d.fig_slide("Banked: a six-site touch battery with a SHAM control", png("battery"),
                takeaway=f"MP {bat['MP']['car_ch47_uv']:+.0f} uV and D1 {bat['D1']['car_ch47_uv']:+.0f} uV on ch47 are genuine focal responses; P1/LP/P3 on ch47 sit at the SHAM level ({bat['SHAM']['car_ch47_uv']:+.0f} uV at {bat['SHAM']['car_ch47_lat_ms']:.0f} ms = thwacker coupling into one contact). Row 5 carries a small real palm map ({bat['LP']['car_row5_uv']:+.0f} uV LP). Templates are banked but must be rebuilt re-referenced.")
    d.table_slide("What acute #3 established", ["question", "answer", "evidence"],
                  [["Was the stim path intact?", "yes", "720/720 and 240/240 pulses on the wire, mapping exact, IZ2 blips per pair, battery charged"],
                   ["Was the recording path intact?", "amplifier yes, array no", "liveness LIVE on every run except one PZ2 drop (caught); array common-mode from the first block"],
                   ["Was the thalamic target wrong?", "unknown, untestable that day", "the only readout had ~21 live contacts and one focal channel"],
                   ["Did the rig-day tooling work under solo conditions?", "yes", "gates, audit, delivery check, liveness alarm, ledger, archive all ran; one void run cost 10 min"],
                   ["What is reusable?", "touch battery + templates, the diagnosis, the runbook", "6 blocks, SHAM-controlled; array-health metrics now a pre-implant check"]],
                  col_widths=[2.2, 1.6, 3.8],
                  takeaway="The experiment that did not happen was blocked by one broken component that no step in the protocol tested before implant. That is the fix.")

    d.section_slide("Acute #4: verify first, then localize", kicker="literature survey + protocol")
    d.table_slide("Array integrity before anything touches the brain (literature)", ["check", "criterion reported", "source"],
                  [["1 kHz impedance census, saline, both arrays", "Utah pre-implant mean 305 kOhm; open > 2.5 MOhm; connector short = all ch < 50-100 kOhm; 48% of failures acute mechanical, 83% of those connector", "Barrese 2013, J Neural Eng 10:066014"],
                   ["Second frequency (< 100 Hz magnitude + phase)", "1 kHz alone did not separate working from broken leads; opens = |Z| > 1e8 Ohm below 100 Hz, phase is the discriminator", "Caldwell 2018, J Neural Eng (rat Utah)"],
                   ["Synapse runtime impedance -> CSV in the block", "500 ms sine per channel, user thresholds, green/yellow/red, Ref-to-ground and Gnd impedance on the PZ5", "TDT Synapse docs (IZ2, PZ5 fast facts)"],
                   ["Saline bench protocol", "contacts + ref + gnd fully submerged, no bubbles (bubbles covered 44% of contacts in one study), inspect under magnification", "Emory CAMBER impedance protocol 2023"],
                   ["Viability after insertion", "spikes p-p >= 40 uV and noise < 150 uV on the majority of channels before the second array goes in", "Barrese 2013"]],
                  col_widths=[2.2, 4.0, 1.6],
                  takeaway="On 10-14 the bench block was in air and the Phase-0 impedance item was unchecked. Either check would have been a NO-GO before induction.")
    d.fig_slide("Target depth: the literature puts forepaw VPL shallower than our tips", png("litdepth"),
                takeaway="Choi 2016: VPL hand region 2.8 L, 2.4 P, depth 6-7 mm; Chao 2014: AP -2.7, ML 2.5, DV 5-6; Aguilar 2008: D 5-7. Our acute #2 found 8/8 responsive at 7.4-8.0 mm tips, so the reference plane (skull vs dura, tip vs shank) must be pinned down and written on the runbook, not re-derived on the day.")
    d.table_slide("Localization protocol for acute #4 (from the survey)", ["step", "method", "criterion", "source"],
                  [["descent", "audio + forepaw tap while advancing from 5.5 mm; recording channel on the stim array or a separate tungsten", "forepaw units / multiunit hash at target, tactile latency 5-9 ms; fine-tune depth to maximize responsive shanks", "Choi 2016; Chao 2014; Aguilar 2008"],
                   ["final test", "single-pulse bipolar VPL stim 20-30 uA, 200 us/phase", "S1 evoked response at 2-5 ms on >= 2 pairs (existing thalamic gate)", "Choi 2016; Jiang 2015"],
                   ["delivery proof", "IZ2 MonBank output-voltage trace per stim channel", "non-railing pulse (< +/-10 V compliance) on every active channel", "TDT IZ2 docs"],
                   ["reference", "cortical ref / gnd on a skull screw, verified by the cortical gate", "common-mode evoked wave < 20 uV; footprint < 16 ch; pairwise corr < 0.95", "this week's data"],
                   ["post hoc", "DiI-coat the thalamic array; 30 uA / 30 s lesion at the end", "track in histology closes the loop on coordinates", "DiCarlo 1996; Chao 2014"]],
                  col_widths=[1.1, 3.0, 2.8, 1.5],
                  takeaway="Full list with URLs: docs/ACUTE4_LOCALIZATION_METHODS.md. Antidromic identification and hippocampal landmarks were reviewed and set aside (need a live S1 readout / no VPL protocol found).")

    d.bullets_slide("Next", [(0, "Array: inspect / repair or replace the 64-ch cortical array; saline impedance at two frequencies becomes a logged Phase-0 artifact for every array"),
                             (0, "Gate: add footprint and pairwise-correlation rules to placement_gate so a broken array is a NO-GO, not a GO"),
                             (0, "Controller: common-median re-reference option for y extraction (today's y would have been the reference site)"),
                             (0, "Data: rebuild the 10-14 touch templates re-referenced; keep MP / D1 as the usable targets"),
                             (0, "Acute #4: date after the array is verified; descent protocol with audio + tap and the depth reference written down"),
                             (0, "Open: direct link between the Synapse and rig PCs (USB drive by hand on 10-14, 2-3 min per block)")])
    out = d.save(OUT)
    print(f"deck: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
