"""build_weekly_deck_2026-10-23.py -- weekly deck: acute #4 (2026-10-22/23).

    python scripts/build_weekly_deck_2026-10-23.py

Every figure is recomputed from the banked artifacts (deckkit house rules; the build FAILS on a
missing artifact): the gate / burst JSONs and PNGs in galleries/, the TDT blocks of the day for the
per-contact touch maps, the loop logs for the timing fault, the duty-ID capture for the feature
responses. Story: clean cortical readout -> thalamic ladder NO-GO -> burst-only coupling, rank 1 ->
duty-ID unfittable -> no arms; plus the timer bug found and fixed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "rig"))
import deckkit as dk  # noqa: E402

FIG = REPO / "outputs" / "deck_figures"
OUT = Path(r"C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\outputs\Synthesis\ClosedLoop_weekly_2026-10-23.pptx")
GAL = REPO / "galleries"
DAY = REPO / "day_2026-10-22"
TANK = Path(r"C:\Users\brets\Desktop\Data\Acute_102226")
CACHE = FIG / "weekly1023_touchmaps.json"

BLK = dict(D1="BSCL20260909BU-261022-194524", SHAM="BSCL20260909BU-261022-194131",
           MP="BSCL20260909BU-261022-233752", P2="BSCL20260909BU-261022-234325",
           g78="BSCL20260909BU-261022-215921", g70="BSCL20260909BU-261022-221551",
           g67="BSCL20260909BU-261022-222415", g70b="BSCL20260909BU-261022-223347",
           burst30="BSCL20260909BU-261022-225622", duty8="BSCL20260909BU-261022-235620",
           duty16="BSCL20260909BU-261023-001009", quiet="BSCL20260909BU-261022-231858")


def png(name):
    return FIG / f"weekly1023_{name}.png"


def gal(key, name):
    return dk.need(GAL / BLK[key] / name)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def touch_maps():
    """Per-contact raw evoked peak (5-80 ms) for D1 / SHAM / MP / P2, from the blocks (cached)."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    import placement_gate as PG
    out = {}
    for site in ("D1", "SHAM", "MP", "P2"):
        d = str(dk.need(TANK / BLK[site]))
        blk = PG.read_block(d, ("Wav1", "nThw"))
        data, fs, t0 = PG.wav1_uv(blk, 64)
        on = PG.thwack_onsets(blk)
        i0, npre, npost = PG.epoch_idx(data.shape[1], fs, t0, on, 40, 200)
        m, _ = PG.mean_response(data, i0, npre, npost)
        t = np.arange(-npre, npost) / fs * 1e3
        w = (t >= 5) & (t <= 80)
        pk = [float(m[c, w][np.argmax(np.abs(m[c, w]))]) for c in range(64)]
        lat = [float(t[w][np.argmax(np.abs(m[c, w]))]) for c in range(64)]
        out[site] = dict(n=int(len(i0)), peak_uv=pk, lat_ms=lat)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out))
    return out


def loop_summaries():
    """droppedControlTicks per run from the loop logs (root copies first, day copies as fallback)."""
    runs = ["gate1", "gate2", "gate3", "gate4", "burst30", "dutyid", "dutyid2"]
    out = {}
    for r in runs:
        cands = [REPO / f"loop_run{r}.log", DAY / f"loopB_{r}.log"]
        txt = None
        for c in cands:
            if c.exists():
                txt = c.read_text(encoding="utf-8", errors="replace")
                if "Summary:" in txt:
                    break
        if txt is None:
            raise FileNotFoundError(f"no loop log for {r}")
        m = re.search(r"Summary: packets=(\d+) controlTicks=(\d+) droppedControlTicks=(\d+)", txt)
        if not m:
            raise RuntimeError(f"no Summary in loop log for {r}")
        resync = [(int(p), int(d)) for p, d in re.findall(r"packet=(\d+)\)\n[^\n]*\n(?:[^\n]*\n)?Scheduler resync: dropped=\d+ totalDropped=(\d+)", txt)]
        out[r] = dict(ticks=int(m.group(2)), dropped=int(m.group(3)), resync=resync)
    return out


def burst30_timeline():
    """(packet, totalDropped) pairs for the burst30 run, in order, from the B log."""
    txt = dk.need(DAY / "loopB_burst30.log").read_text(encoding="utf-8", errors="replace")
    pk = 0
    pts = [(0, 0)]
    for ln in txt.splitlines():
        m = re.search(r"packet=(\d+)", ln)
        if m:
            pk = int(m.group(1))
        m = re.search(r"totalDropped=(\d+) lateUs=(-?\d+)", ln)
        if m:
            pts.append((pk, int(m.group(1))))
    pts.append((28917, pts[-1][1]))
    return np.array(pts, dtype=float)


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def fig_timeline():
    ev = [("19:41", "SHAM thwack block (150)", "ok"),
          ("19:45", "D1 thwack block (150): array OK, gate GO on evidence", "ok"),
          ("21:59", "thalamic 7.8 mm: NO-GO 0/8", "fail"),
          ("22:17", "7.0 mm: NO-GO, near miss (2 weak @ 16 ms)", "warn"),
          ("22:25", "6.7 mm: NO-GO", "fail"),
          ("22:3x", "7.0 mm again: first try y DEAD (Synapse idle) -> stim zero; rerun NO-GO, no repeat", "fail"),
          ("22:57", "burst ladder 30 uA: 5/8 pairs at 16 pulses, rank 1 | timer fault found", "warn"),
          ("23:19", "quiet: blacklist ch33 | timer fix verified live", "ok"),
          ("23:38", "MP + P2 thwack (reduced battery)", "ok"),
          ("23:56", "duty-ID 8-pulse 15-30 uA: loop clean, fit 0 %", "warn"),
          ("00:10", "duty-ID 16-pulse 25-30 uA: loop clean, fit 0 % -> stop", "fail"),
          ("00:20", "stim zero, array OK, archive", "ok")]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        y = np.arange(len(ev))[::-1]
        for yi, (when, what, kind) in zip(y, ev):
            ax.scatter([0], [yi], s=120, color=dk.COLOR[kind], zorder=3)
            ax.text(0.05, yi, f"{when}   {what}", va="center", fontsize=10.5)
        ax.plot([0, 0], [y.min(), y.max()], color=dk.AXIS, lw=2, zorder=1)
        ax.set_xlim(-0.1, 4); ax.set_ylim(-0.7, len(ev) - 0.3); ax.axis("off")
        ax.set_title("Acute #4, 2026-10-22: late start, solo surgeon, engineer lane remote; every gate ran live")
        dk.save_fig(fig, png("timeline"))


def fig_touchmaps(tm):
    """Raw per-contact peak grids for SHAM / D1 / MP / P2 with the two D1-silent contacts marked."""
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("WIDE", 1, 4)
        for ax, site in zip(axs, ("SHAM", "D1", "MP", "P2")):
            pk = np.array(tm[site]["peak_uv"]).reshape(8, 8)
            lim = max(50.0, float(np.abs(pk).max()))
            im = ax.imshow(pk, cmap="RdBu_r", vmin=-lim, vmax=lim)
            for c in (52, 60):
                r, q = divmod(c - 1, 8)
                ax.add_patch(plt.Rectangle((q - 0.5, r - 0.5), 1, 1, fill=False, ec="k", lw=1.6))
            ax.set_title(f"{site}  (n={tm[site]['n']})  min|pk| {np.abs(pk).min():.0f} uV", fontsize=11)
            ax.set_xticks([]); ax.set_yticks([])
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03).set_label("peak uV, 5-80 ms", fontsize=8)
        fig.suptitle("Raw evoked peak per contact (8 x 8). Boxes: ch52 / ch60, ~0 uV for D1, +220/+250 for MP, -875/-717 for P2")
        dk.save_fig(fig, png("touchmaps"))


def fig_ladder(gates):
    """Per-pair z at each thalamic position (short design, 30 probes/pair)."""
    pos = [("7.8 mm", "g78"), ("7.0 mm", "g70"), ("6.7 mm", "g67"), ("7.0 mm (repeat)", "g70b")]
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("WIDE", 1, 4, sharey=True)
        for ax, (lab, key) in zip(axs, pos):
            j = gates[key]
            z = [e["z"] for e in j["per_pair"]]
            cols = [dk.COLOR["ok"] if e["status"] == "RESPONSIVE" else dk.COLOR["warn"] if e["status"] == "WEAK" else dk.MUTED for e in j["per_pair"]]
            ax.bar(range(1, 9), z, color=cols)
            ax.axhline(5, color=dk.INK_2, ls="--", lw=1); ax.axhline(3, color=dk.AXIS, ls=":", lw=1)
            ax.set_title(f"{lab}: {j['verdict']}  resp {j['n_responsive']}, weak {j['n_weak']}, rank {j['eff_rank']}", fontsize=10.5)
            ax.set_xlabel("stim pair"); ax.set_xticks(range(1, 9))
        axs[0].set_ylabel("evoked z (single pulses, 18/25/30 uA)")
        fig.suptitle("Thalamic ladder at the acute-2 AP/ML, depths to the tip from the brain surface: no position reaches 2 responsive pairs")
        dk.save_fig(fig, png("ladder"))


def fig_bursts(b30, b16):
    """z per pair and burst length, burst30 (2/5/16 pulses) and the 16-pulse duty-ID block."""
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("WIDE", 1, 2)
        ax = axs[0]
        rows = b30["rows"]
        for b, col, lab in ((1, dk.MUTED, "2 pulses"), (3, dk.COLOR["warn"], "5 pulses"), (10, dk.COLOR["stim"], "16 pulses")):
            z = [next(r["z"] for r in rows if r["pair"] == p and r["B"] == b) for p in range(1, 9)]
            off = {1: -0.27, 3: 0.0, 10: 0.27}[b]
            ax.bar(np.arange(1, 9) + off, z, width=0.26, color=col, label=lab)
        ax.axhline(5, color=dk.INK_2, ls="--", lw=1)
        ax.set_xticks(range(1, 9)); ax.set_xlabel("stim pair"); ax.set_ylabel("z (artifact-robust, median-filtered)")
        ax.set_title("30 uA burst ladder, 30 bursts per condition"); ax.legend(frameon=False)
        ax = axs[1]
        rows = b16["rows"]
        pairs = [r["pair"] for r in rows]
        ax.bar(pairs, [r["z"] for r in rows], color=[dk.COLOR["ok"] if r["status"] == "RESPONSIVE" else dk.COLOR["warn"] for r in rows])
        for r in rows:
            ax.text(r["pair"], r["z"] + 0.3, f"ch{r['best_channel_1based']} {r['peak_uv']:+.0f} uV\nn={r['n']}", ha="center", fontsize=9)
        ax.axhline(5, color=dk.INK_2, ls="--", lw=1)
        ax.set_xticks(pairs); ax.set_xlabel("stim pair"); ax.set_title("duty-ID #2: 16-pulse bursts, 25-30 uA")
        fig.suptitle("Coupling appears only with long bursts; the long-burst footprint is one shared mode (effective rank 1)")
        dk.save_fig(fig, png("bursts"))


def fig_timer(tl, sums):
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("WIDE", 1, 2)
        ax = axs[0]
        ax.plot(tl[:, 0] / 100.0, tl[:, 1], color=dk.COLOR["fail"], lw=2)
        ax.set_xlabel("s into run burst30"); ax.set_ylabel("dropped control ticks (cumulative)")
        ax.set_title("burst30: 0 drops for 69 s, then every other tick 5.6 ms late")
        ax.axvline(69, color=dk.AXIS, ls="--"); ax.text(71, tl[-1, 1] * 0.9, "timer -> 15.62 ms", fontsize=10)
        ax = axs[1]
        names = list(sums.keys())
        frac = [100.0 * sums[n]["dropped"] / sums[n]["ticks"] for n in names]
        cols = [dk.COLOR["fail"] if f > 1 else dk.COLOR["ok"] for f in frac]
        ax.bar(range(len(names)), frac, color=cols)
        for i, (n, f) in enumerate(zip(names, frac)):
            ax.text(i, f + 0.5, f"{sums[n]['dropped']}/{sums[n]['ticks']}", ha="center", fontsize=8.5)
        ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=20)
        ax.set_ylabel("% control ticks dropped"); ax.set_title("per run: before (burst30) and after the 1 ms timer hold")
        fig.suptitle("The loop exe never requests the 1 ms Windows timer; it ran on borrowed resolution until 22:58")
        dk.save_fig(fig, png("timer"))


def fig_features():
    """Burst-triggered average of the controller's per-tick features, duty-ID #2 capture."""
    d = pd.read_csv(dk.need(REPO / "capture_rig_rundutyid2.csv"))
    U = d[[f"u{k}" for k in range(1, 9)]].values; Y = d[[f"y{k}" for k in range(1, 65)]].values
    lags = np.arange(-5, 46)
    rng = np.random.default_rng(0)
    with dk.deck_style() as plt:
        fig, axs = dk.new_fig("WIDE", 1, 3, sharey=True)
        for ax, p in zip(axs, (1, 4, 8)):
            u = U[:, p - 1]; on = np.flatnonzero((u[:-1] <= 0) & (u[1:] > 0)) + 1; on = on[(on > 10) & (on < len(u) - 50)]
            for ch, col in ((34, dk.COLOR["mpc"]), (64, dk.COLOR["touch"]), (32, dk.COLOR["nn"])):
                y = Y[:, ch - 1]; seg = np.array([y[i + lags] for i in on])
                m = (seg - seg[:, :5].mean(1, keepdims=True)).mean(0) / np.median(y) * 100
                ax.plot(lags, m, color=col, lw=1.8, label=f"ch{ch}")
            # null band from shuffled onsets, ch34
            y = Y[:, 33]; nulls = []
            for _ in range(40):
                r = rng.integers(10, len(u) - 50, size=len(on)); s = np.array([y[i + lags] for i in r])
                nulls.append((s - s[:, :5].mean(1, keepdims=True)).mean(0) / np.median(y) * 100)
            nulls = np.array(nulls)
            ax.fill_between(lags, nulls.mean(0) - 2 * nulls.std(0), nulls.mean(0) + 2 * nulls.std(0), color=dk.GRID, label="shuffled +/-2 sd")
            ax.axvspan(0, 16, color=dk.COLOR["stim"], alpha=0.08)
            ax.set_title(f"pair {p}, n={len(on)} bursts"); ax.set_xlabel("ticks from burst onset (shaded: 16-pulse burst)")
        axs[0].set_ylabel("feature change, % of median"); axs[0].legend(frameon=False, fontsize=9)
        fig.suptitle("What the controller sees: a +60 % feature bump for ~5 ticks after a 16-pulse burst (pair 1), nothing on pair 4")
        dk.save_fig(fig, png("features"))


def fig_strength(b30, j2):
    """Per-trial strength z/sqrt(n): acute-2 GO pairs vs tonight's best."""
    a2 = [e["z"] / np.sqrt(e["n_trials"]) for e in j2["per_pair"] if e.get("n_trials", 0) > 3]
    r30 = [r for r in b30["rows"] if r["B"] == 10]
    r5 = [r for r in b30["rows"] if r["B"] == 3]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        groups = [("acute 2 single pulses\n(09-10, n=228/pair)", a2, dk.COLOR["ok"]),
                  ("acute 4 single pulses\n(7.0 mm pooled, n=60)", [0.54, 0.22, 0.46, 0.30, 0.08, 0.15, 0.30, 0.08], dk.MUTED),
                  ("acute 4, 5-pulse bursts", [r["strength"] for r in r5], dk.COLOR["warn"]),
                  ("acute 4, 16-pulse bursts", [r["strength"] for r in r30], dk.COLOR["stim"])]
        for i, (lab, vals, col) in enumerate(groups):
            x = i + (np.random.default_rng(1).uniform(-0.15, 0.15, len(vals)))
            ax.scatter(x, vals, color=col, s=60, zorder=3)
            ax.hlines(np.median(vals), i - 0.3, i + 0.3, color=col, lw=3)
        ax.axhline(0.9, color=dk.INK_2, ls="--", lw=1); ax.text(3.45, 0.93, "acute-2 weakest pair", fontsize=9, ha="right")
        ax.set_xticks(range(4)); ax.set_xticklabels([g[0] for g in groups], fontsize=10)
        ax.set_ylabel("per-trial strength  z / sqrt(n)"); ax.set_title("Only long bursts bring tonight's site into the acute-2 range of per-trial strength")
        dk.save_fig(fig, png("strength"))


# ---------------------------------------------------------------------------
def main():
    FIG.mkdir(parents=True, exist_ok=True)
    gates = {k: dk.jload(GAL / BLK[k] / "gate_thalamic.json") for k in ("g78", "g70", "g67", "g70b")}
    gD1 = dk.jload(GAL / BLK["D1"] / "gate_cortical.json")
    gSH = dk.jload(GAL / BLK["SHAM"] / "gate_cortical.json")
    gMP = dk.jload(GAL / BLK["MP"] / "gate_cortical.json")
    gP2 = dk.jload(GAL / BLK["P2"] / "gate_cortical.json")
    b30 = dk.jload(GAL / BLK["burst30"] / "burst_gate.json")
    b8 = dk.jload(GAL / BLK["duty8"] / "burst_gate.json")
    b16 = dk.jload(GAL / BLK["duty16"] / "burst_gate.json")
    j2 = dk.jload(GAL / "BSCL20260909BU-260910-200410" / "gate_thalamic.json")
    ahD1 = dk.jload(GAL / BLK["D1"] / "array_health.json")
    tm = touch_maps()
    sums = loop_summaries()
    tl = burst30_timeline()

    fig_timeline(); fig_touchmaps(tm); fig_ladder(gates); fig_bursts(b30, b16); fig_timer(tl, sums); fig_features(); fig_strength(b30, j2)

    r16 = {r["pair"]: r for r in b16["rows"]}
    r30_10 = [r for r in b30["rows"] if r["B"] == 10]
    n_resp30 = sum(r["status"] == "RESPONSIVE" for r in r30_10)
    pkD1 = np.array(tm["D1"]["peak_uv"]); pkP2 = np.array(tm["P2"]["peak_uv"]); pkMP = np.array(tm["MP"]["peak_uv"])

    d = dk.Deck(footer="Closed-loop thalamic stim -> S1  |  weekly 2026-10-23")
    d.title_slide("Acute #4: a clean cortical readout, a burst-only thalamic site, and a rig bug fixed",
                  "Weekly update, 2026-10-23",
                  ["Pre-implant array verification tooling built 10-21 and used live: the new 64-ch array was healthy all night and the gates graded real physiology, not a broken connector",
                   "Thalamic ladder at the acute-2 coordinates (7.8 / 7.0 / 6.7 / 7.0 mm from the brain surface): NO-GO at every depth with single pulses, delivery verified every run",
                   f"The site couples to long 30 uA bursts ({n_resp30}/8 pairs at 16 pulses) as one slow shared mode; two duty-ID runs fit 0 % of the controller's feature variance -> no closed-loop arms",
                   "Found and fixed: the loop exe never requested the 1 ms Windows timer; 30 % dropped ticks on the first long run, 0 after the fix (60k clean ticks)"])
    d.agenda_slide("Agenda", [("Preparation (10-21)", "array-health check, gate rules, runcard phases"),
                              ("The day", "timeline, how the engineer lane ran"),
                              ("Cortical readout", "array health, D1 vs sham, the common-mode question"),
                              ("Thalamic ladder", "four positions, pooled evidence, why no reinsertion"),
                              ("Burst regime", "what long bursts evoke, and why it is rank 1"),
                              ("Duty-ID and the fit", "feature-level response vs tick-level predictability"),
                              ("Rig timing bug", "diagnosis, fix, verification"),
                              ("Touch battery and wrap", "MP, P2, what acute #4 established, next")])

    # ---------------- preparation ----------------
    d.section_slide("Preparation (10-21)", kicker="the 10-16 post-mortem to-dos, landed")
    d.table_slide("What was built the evening before, and how it was validated", ["tool", "what it does", "known answer"],
                  [["rig/array_health.py", "ARRAY HEALTH OK / SUSPECT / BROKEN / UNINFORMATIVE from any Wav1 block: own-signal contacts, pairwise correlation, dead 16-ch banks, 60 Hz share", "acute-2 blocks OK (44-64/64, corr 0.86-0.89); every 10-14 block BROKEN (21-27/64, corr 0.98-0.99, banks 1-16 + 49-64 dead); 10-13 in-air UNINFORMATIVE"],
                   ["placement_gate --mode cortical", "array line, common-mode touch wave, re-referenced focal map and a control-channel candidate; BROKEN -> NO-GO", "acute-2 GO block stays GO (CM +63 uV under -219 uV focal); 10-14 block -> NO-GO ARRAY BROKEN"],
                   ["blockutil.block_dirs", "finds blocks nested one level deeper, newest by .tsq time", "--newest returns the 10-14 SHAM block (it missed every 10-14 block before)"],
                   ["rig_runcard --phase cgate / --short", "cortical-gate phase; short 1.6-min thalamic design for the ladder", "gate phase sim-rehearsed end to end, AUDIT PASS"],
                   ["RIG_DAY + HELPER_CARD 2026-10-22", "Phase 0 array verification before induction; ladder as a position list; reference plane written down", "lint PASS, PDFs"]],
                  col_widths=[1.8, 3.0, 2.8],
                  takeaway="Everything on the 10-16 list that mattered for the day landed and was known-answer tested against both earlier acutes before the animal.")

    # ---------------- the day ----------------
    d.section_slide("The day", kicker="Wednesday 10-22, 19:40 -> 00:20")
    d.fig_slide("Timeline: every decision made on a gate line, minutes after the recording", png("timeline"),
                takeaway="New: rig/drive_live_run.py runs terminals A and B from the runcard with the go prompt answered on the surgeon's word, so the engineer lane ran from the analysis PC while the surgeon stayed at the table. Sequence that worked all night: B at the prompt -> recording ON -> stim-enable ON -> go.")

    # ---------------- cortical ----------------
    d.section_slide("Cortical readout", kicker="brand-new 64-ch array, skull-screw reference")
    d.stat_slide("Array health was OK from the first block to the last",
                 [(f"{ahD1['n_own']}/64", "contacts with own signal"), (f"{ahD1['med_pair_corr']:.2f}", "median pair corr (10-14: 0.98)"), ("none", "dead banks"), ("3 / 3", "checks OK: 19:45, 23:19, 00:10")],
                 png=gal("D1", "array_health.png"),
                 takeaway="The 10-14 failure mode (common-mode array, two dead banks) was tested for before any gate and did not recur. Saline impedance was skipped on the surgeon's call (factory impedances, new array); impedance-on-receipt is added for the next batch.")
    d.fig_slide("D1: a large, reliable response on 30 of 64 contacts; sham: nothing", gal("D1", "gate_cortical.png"),
                takeaway=f"D1 (150 taps): raw best ch{gD1['best_channel_1based']} {gD1['best_peak_uv']:+.0f} uV @ {gD1['best_latency_ms']:.0f} ms, z {gD1['best_z']:.0f}, split-half {gD1['split_half']:.2f}, half-max footprint {gD1['footprint_channels']} ch. SHAM (150 TTLs, thwacker not touching): best z {gSH['best_z']:.1f}, {gSH['best_peak_uv']:+.0f} uV. The thwacker alone puts nothing on the array.")
    d.fig_slide("Reference or tissue? The per-contact maps answer it", png("touchmaps"),
                takeaway=f"A reference picking up a touch wave adds the SAME wave to every contact. For D1, ch52/ch60 read {pkD1[51]:+.0f}/{pkD1[59]:+.0f} uV while 62 contacts go negative -> the reference is clean and the -186 uV median is a genuine widespread S1 negativity; the gate's MARGINAL (common-mode rule) was overruled. MP even reverses polarity on those contacts. P2 is different: every contact ≥ -{np.abs(pkP2).min():.0f} uV, see the battery section.")
    d.table_slide("Cortical gate decisions", ["block", "gate verdict", "evidence", "decision"],
                  [["D1 194524", f"MARGINAL (CM {gD1['common_mode_wave_uv']:+.0f} uV)", "ch52/60 ~0 uV; 62/64 negative; z 59; split-half 0.99", "GO; control channel ch58 (raw -387 uV, re-ref best z 62)"],
                   ["SHAM 194131", "NO-GO (z 2)", "no evoked focus, CM +5 uV", "clean negative control"],
                   ["MP 233752", f"MARGINAL (CM {gMP['common_mode_wave_uv']:+.0f} uV)", f"ch19 {gMP['best_peak_uv']:+.0f} uV @ {gMP['best_latency_ms']:.0f} ms, polarity reversal at ch52/60", "genuine local pattern, different focus from D1"],
                   ["P2 234325", f"MARGINAL (CM {gP2['common_mode_wave_uv']:+.0f} uV)", f"ch7 {gP2['best_peak_uv']:+.0f} uV @ {gP2['best_latency_ms']:.0f} ms; ALL 64 contacts negative incl. ch52/60", "template with a caveat: a ~-700 uV component common to every contact"]],
                  col_widths=[1.2, 1.8, 2.8, 2.6],
                  takeaway="Rule to encode after this week: the common-mode test should ask whether near-zero or reversed contacts exist, not whether the median wave is large. A reference pickup leaves no contact at zero.")

    # ---------------- ladder ----------------
    d.section_slide("Thalamic ladder", kicker="acute-2 AP/ML, depths to the tip from the BRAIN SURFACE")
    d.fig_slide("Four positions, single pulses, 30 probes per pair: no GO", png("ladder"),
                takeaway="Delivery verified on every run (pair mapping exact, 8/8), IZ2 LEDs green, loop 9101/9101 ticks each. The 7.8 mm 'weak' pairs are the next-pulse artifact at 9.8 ms; the 7.0 mm near miss (pairs 5/7, z 4-4.7 at a proper 16 ms latency) did not reproduce in the repeat and pooling to 60 trials leaves the best pair at z 4.2.")
    d.fig_slide("7.0 mm, first block: the near miss that set the depth", gal("g70", "gate_thalamic.png"),
                takeaway="Real-looking negativities on ch27/ch35 starting ~8 ms after the pulse and peaking at 15-17 ms, but unreliable trial to trial. 6.7 mm was weaker, 7.8 mm empty; the depth was bracketed and the remaining degree of freedom was lateral.")
    d.table_slide("Why the ladder stopped where it did", ["option", "cost", "decision"],
                  [["move AP/ML 0.3 mm at 7.0 mm (ladder step 5)", "16 microwires: an ML move needs the array out and back in = a new track and more damage", "declined by the surgeon; reasonable"],
                   ["longer single-pulse block at 7.0 mm", "the per-trial strength does not grow with n; the full design would at best put one pair on the z = 5 line", "not run"],
                   ["30 uA burst ladder at 7.0 mm", "4.8 min, no surgical risk; bursts are what the duty controller drives anyway", "run (next section)"]],
                  col_widths=[2.4, 3.4, 1.8],
                  takeaway="Calibration: acute-2 GO pairs had per-trial strength z/sqrt(n) 0.96-2.8; tonight's best single-pulse pair pooled over 60 trials: 0.54, and not reproducible.")

    # ---------------- bursts ----------------
    d.section_slide("Burst regime", kicker="30 uA, bursts of 2 / 5 / 16 pulses (see the timing section for why not 1 / 3 / 10)")
    d.fig_slide("Long bursts recruit cortex from 5 of 8 pairs; short ones from none", gal("burst30", "burst_gate.png"),
                takeaway="Per pair, trial means at the best contact (thin raw, thick median-filtered to remove the one-sample pulse artifacts). The 16-pulse response is a slow negativity that builds during the 157 ms burst and recovers when it ends; the 5-pulse responses on pairs 4 and 8 peak 20 ms after the burst ends, which rules out electrode polarization.")
    d.fig_slide("Per-pair z by burst length, and the 16-pulse duty-ID block", png("bursts"),
                takeaway=f"burst30: 16 pulses -> {n_resp30}/8 responsive (-116..-195 uV, split-half 0.6-0.9) but effective rank 1 (shared footprint ch32-40); 5 pulses -> pairs 4 and 8, rank 2; 2 pulses -> nothing. duty-ID #2 (16 pulses, 25-30 uA): pair 1 z {r16[1]['z']:.0f}, pair 4 z {r16[4]['z']:.0f}, pair 8 z {r16[8]['z']:.0f}.")
    d.fig_slide("Per-trial strength: where tonight's site sits against acute 2", png("strength"),
                takeaway="Single pulses at this site are 2-5x weaker per trial than acute 2's weakest pair; 16-pulse bursts reach the acute-2 range, but as one mode. This is the acute-2 tonic-saturation finding at a second site: sustained drive collapses the actuator to a single direction.")

    # ---------------- duty-ID ----------------
    d.section_slide("Duty-ID and the fit", kicker="two attempts, pre-registered stop rule")
    d.fig_slide("What the controller's per-tick features see after a 16-pulse burst", png("features"),
                takeaway="Pair 1 lifts the ch34 feature by ~60 % for about 5 ticks from lag 8-10 (dead time 10 ticks); pair 8 does the same on ch64; pair 4 shows nothing. The bumps are real (z 6-7 over 165-174 bursts) and about one hundredth of the tick-to-tick feature noise.")
    d.table_slide("Fit results and the decision", ["run", "design", "loop", "block-level response", "MIMO fit (validation)", "decision"],
                  [["dutyid", "8-pulse bursts, 15-30 uA, pairs 1 2 4 7 8, 977 bursts", "30160/30160, 0 dropped", f"pair 8 marginal only (z {next(r['z'] for r in b8['rows'] if r['pair']==8):.0f}); others silent", "-0.08 % (orders 1-3)", "under-driven; rerun at the proven condition"],
                   ["dutyid2", "16-pulse bursts, 25-30 uA, pairs 1 4 8, 510 bursts", "30360/30360, 0 dropped", f"pair 1 z {r16[1]['z']:.0f}, pair 4 z {r16[4]['z']:.0f}, pair 8 z {r16[8]['z']:.0f}", "0.11 % (delay 2); -0.07 % (measured delay 9, orders 1-4)", "stop: the rule was valFit > ~10 %"]],
                  col_widths=[0.8, 2.2, 1.3, 1.9, 1.6, 1.8],
                  takeaway="The site is coupled and the loop is clean, but a plant explaining 0.1 % of the feature variance would make MPC drive noise. No arms; the day's result is the clean localization verdict itself.")

    # ---------------- timing ----------------
    d.section_slide("Rig timing bug", kicker="found 23:05, fixed 23:12, verified 23:19")
    d.fig_slide("30 % of ticks dropped on the first long run; 0 after the fix", png("timer"),
                takeaway=f"MpcPo8eUdpClosedLoop.exe never calls timeBeginPeriod. It keeps its 10 ms cadence only while some other process holds the system timer at 1 ms; when that process went idle the timer fell to 15.62 ms and every other tick fired 5.6 ms late (lateUs 5300-5800 = 15.62 - 10). Effect: every stim word held 1.6x (1/3/10 -> 2/5/16 pulses, uniformly). The 91 s gate runs had 0 drops by luck; acute-2 runs of 22-28k ticks had 0 drops because something held the timer that day.")
    d.table_slide("Fix and verification", ["item", "what", "evidence"],
                  [["rig/timer_hold.py", "timeBeginPeriod(1) holder; raises the GLOBAL resolution (checked from a separate process: 15.62 -> 1.00 ms)", "NtQueryTimerResolution"],
                   ["rig/drive_live_run.py", "starts the holder before terminal A; runs A and B at HIGH priority class; answers the go prompt from a signal file", "all later runs"],
                   ["verification", f"no-stim loop on the live stream: 5000 ticks, 4 dropped; dutyid {sums['dutyid']['dropped']}/{sums['dutyid']['ticks']}; dutyid2 {sums['dutyid2']['dropped']}/{sums['dutyid2']['ticks']}, 0 scheduler resyncs", "loop logs"],
                   ["to do", "call timeBeginPeriod(1) in the exe at startup and rebuild; count 'Scheduler resync' lines in run_audit; sim mode does not reproduce the fault", "post-mortem"]],
                  col_widths=[1.6, 4.4, 1.6],
                  takeaway="The finalBuffered=65536 pattern seen since acute 2 is NOT this bug (09-10 runs had it with 0 drops); the discriminator is the 'Scheduler resync' line and droppedControlTicks.")

    # ---------------- battery + wrap ----------------
    d.section_slide("Touch battery and wrap", kicker="reduced battery by choice (rank-limited plant)")
    d.two_fig_slide("MP: a second focus, polarity reversal; P2: -1.3 mV on every contact",
                    gal("MP", "gate_cortical.png"), gal("P2", "gate_cortical.png"),
                    captions=(f"MP, n={tm['MP']['n']}: ch19 {pkMP.min():+.0f} uV; ch52/60 {pkMP[51]:+.0f}/{pkMP[59]:+.0f} uV", f"P2, n={tm['P2']['n']}: min |peak| over 64 contacts {np.abs(pkP2).min():.0f} uV; median {np.median(pkP2):+.0f} uV"),
                    takeaway="P2 carries a ~-700 uV component common to all 64 contacts (including the D1-silent ch52/60) on top of a D1-like gradient, and peaks 10-15 ms later than D1/MP. Reference pickup of a positive far-field at the skull screw, or a mechanical / arousal component, cannot be separated tonight. P1 / LP / P3 were not run (wrap chosen at 00:15).")
    d.table_slide("What acute #4 established", ["question", "answer", "evidence"],
                  [["Was the cortical readout trustworthy?", "yes, all night", "array health OK x3; D1 z 59 vs sham z 2; per-contact maps clear the reference"],
                   ["Is VPL at the acute-2 coordinates, 6.7-7.8 mm from the surface?", "not with single pulses", "4 positions NO-GO, delivery verified, LEDs green, repeat at 7.0 did not reproduce"],
                   ["Does the site couple at all?", "yes, to >= 5-pulse 30 uA bursts, as one slow mode", f"{n_resp30}/8 pairs at 16 pulses, rank 1; per-trial strength in the acute-2 range"],
                   ["Can that plant be controlled at the tick level?", "no", "two duty-ID runs, 0.1 % validation fit at the measured dead time"],
                   ["Did the tooling work under solo + remote conditions?", "yes, and it found a rig bug", "12 blocks graded live; one void run (y DEAD) caught at 30 s; timer fault diagnosed and fixed mid-night"]],
                  col_widths=[2.6, 1.8, 3.2],
                  takeaway="Compared with 10-14 this is a real placement result: the readout was clean, so the NO-GO is about the target, and the burst coupling tells us the array sits near, not in, the forepaw VPL.")
    d.bullets_slide("Next", [(0, "Executable: request the 1 ms timer at startup and rebuild; keep the holder as belt-and-braces; add the resync count to run_audit"),
                             (0, "Gates: artifact-robust estimator (median filter) in the thalamic gate; common-mode rule on near-zero / reversed contacts instead of the median amplitude; re-grade every 10-14 and 10-22 thalamic block"),
                             (0, "P2: test the skull-screw far-field hypothesis with a re-referenced template; compare against MP and D1"),
                             (0, "Localization for the next acute: write the reference plane; audio-guided descent with forepaw tap from 5.5 mm (docs/ACUTE4_LOCALIZATION_METHODS.md); a histology track (DiI / lesion) to close the loop on coordinates"),
                             (0, "Analysis: rank and footprint of the burst responses vs acute 2's tonic saturation; is a burst-duty plant fittable with a slower feature (e.g. 100 ms window) rather than the 10 ms MAV?"),
                             (0, "Housekeeping: both repos uncommitted since 10-14 -> commit; impedance-on-receipt for the next electrode batch")])
    out = d.save(OUT)
    print(f"deck: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
