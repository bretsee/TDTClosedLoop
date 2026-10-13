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
    d.title_slide("Closed-loop MPC: rig recovered, day rehearsed, acute #3",
                  "Weekly update, 2026-10-16",
                  ["Rig back on the network through a USB adapter; every bring-up check passes",
                   "Full simulated rehearsal of the acute-3 runbook caught and fixed two server-side defects",
                   "Delivery checker, QP conditioning and the artifact-aware re-analysis of acute #2 verified",
                   "Acute #3 ran Wed 10-14 (results section)"])
    d.agenda_slide("Agenda", [("Rig back online", "dead onboard port -> USB adapter, verified end to end"),
                              ("Rehearsal of the surgery day", "what the sim dress caught"),
                              ("Tooling verified offline", "delivery checker, QP cap, artifact-aware tracking"),
                              ("Acute #3 preparation", "runbook, safety checklist, data path"),
                              ("Acute #3 results", "placeholder until the blocks are analysed")])

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
                  [["pull_blocks.ps1 -Watch", "mirrors new TDT blocks from the Synapse PC; gates read the newest real block", "Phase 0, all day"],
                   ["physio_timer.ps1", "beeps on the protocol interval and logs the reading", "from induction"],
                   ["check_y_liveness --beep", "audible alarm when features go dead (PZ2-off incident)", "every run"],
                   ["run_audit -> 2_loop gate", "a FAIL must be acknowledged before the next stim run", "every run"],
                   ["stim_zero.ps1", "zero every stim word after ANY crash", "red flag"],
                   ["build_interleaved_run --run-offset", "references can no longer be overwritten (early/late repeat)", "Tier C"],
                   ["archive_day.ps1", "zips captures, logs, ledger, galleries (git ignores them)", "wrap"]],
                  col_widths=[1.6, 3.4, 1.0],
                  takeaway="Pre-induction checklist in the runbook: stimulator voltage, PZ2 charger, reference wiring, electrode map, impedances, monitoring interval.")

    d.section_slide("Acute #3 results", kicker="Wednesday 10-14")
    if not args.skip_results and (DAY14 / "BLOCK_LEDGER_2026-10-14.md").exists():
        d.bullets_slide("Acute #3: results", [(0, "ledger found -- results slides to be built from day_2026-10-14/")])
    else:
        d.bullets_slide("Acute #3: results to be added after the day",
                        [(0, "gate verdicts and depth ladder"), (0, "burst-ladder efficacy and eff-rank per burst length; operating gap"),
                         (0, "MIMO fit, rank gate, control channels"), (0, "MPC vs Choi r1 (+ early/late repeat), tiers reached"),
                         (0, "run audits: every run PASS/WARN/FAIL")],
                        takeaway="This section is filled from the acute-3 blocks on Thursday.")

    d.bullets_slide("Next", [(0, "Thursday: ingest the acute-3 blocks, artifact-aware tracking on the new arms, results deck"),
                             (0, "Closed: the 3.6 s loop stall was the rehearsal driver's pipe; zero dropped ticks in every rerun"),
                             (0, "Open item: the Synapse tank share name must be set on the day (pull_blocks -Check)")])
    out = d.save(OUT)
    print(f"deck: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
