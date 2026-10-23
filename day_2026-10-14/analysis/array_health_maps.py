"""array_health_maps.py -- per-channel 'alive' maps + acute-2 end-of-day blocks + within-block timeline."""
import json, os, sys, numpy as np
sys.path.insert(0, r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\rig"); sys.path.insert(0, r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\scripts")
import placement_gate as pg
import deckkit as dk
OUT = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\day_2026-10-14\analysis"
FIG = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\outputs\deck_figures"; os.makedirs(FIG, exist_ok=True)
D = r"C:\Users\brets\Desktop\Data"
def load(p):
    blk = pg.read_block(p, ("Wav1",)); x, fs, t0 = pg.wav1_uv(blk, 0); return x, fs
def per_ch(x):
    med = np.median(x, axis=0); r = x - med[None, :]
    return np.sqrt(np.mean(r**2, axis=1)), np.array([np.corrcoef(c, med)[0,1] for c in x]), np.sqrt(np.mean(x**2, axis=1))
blocks = {
 "acute2 09-10 18:55 (D1 thwack)": D + r"\BSCL20260909BU-260910-185534",
 "acute2 09-10 22:10 (last block)": D + r"\Acute_091026-260910_LaterBlocks\BSCL20260909BU-260910-221053",
 "acute3 10-14 20:07 (first block)": D + r"\Acute_101426\BSCL20260909BU-261014-200749\BSCL20260909BU-261014-200749",
 "acute3 10-14 22:00 (MP)": D + r"\Acute_101426\BSCL20260909BU-261014-220050\BSCL20260909BU-261014-220050",
}
summary = {}
maps = {}
for lab, p in blocks.items():
    try:
        x, fs = load(p)
    except Exception as e:
        print(lab, "SKIP", e); continue
    rr, cm, rms = per_ch(x)
    alive = rr > 10.0   # >10 uV differential RMS = channel carries its own signal
    maps[lab] = dict(resid=rr, cm=cm, rms=rms)
    summary[lab] = dict(n_alive=int(alive.sum()), alive=[int(i)+1 for i in np.flatnonzero(alive)], resid_median=float(np.median(rr)), cm_median=float(np.median(cm)))
    print("%-34s alive(>10uV diff) %2d/64  resid median %5.1f  corr-with-median median %.3f  alive ch: %s" % (lab, alive.sum(), np.median(rr), np.median(cm), summary[lab]["alive"][:20]))
# acute-2 later blocks metrics (did the array degrade at the end of acute 2?)
late = ["BSCL20260909BU-260910-215613", "BSCL20260909BU-260910-220332", "BSCL20260909BU-260910-221053"]
for b in late:
    try:
        x, fs = load(D + r"\Acute_091026-260910_LaterBlocks\%s" % b)
        rr, cm, rms = per_ch(x); C = np.corrcoef(x); iu = np.triu_indices(64, 1)
        print("acute2 late %s: pair-corr %.3f  resid median %5.1f  alive %d" % (b[-6:], np.median(C[iu]), np.median(rr), (rr > 10).sum()))
        summary["acute2 late " + b[-6:]] = dict(pair_corr=float(np.median(C[iu])), resid_median=float(np.median(rr)), n_alive=int((rr > 10).sum()))
    except Exception as e:
        print("late", b, "SKIP", e)
json.dump(summary, open(os.path.join(OUT, "array_alive_summary.json"), "w"), indent=1)
# figure 1: 2x2 alive maps (differential RMS per channel, 8x8)
with dk.deck_style() as plt:
    fig, axs = dk.new_fig("WIDE", nrows=1, ncols=len(maps))
    axs = np.atleast_1d(axs)
    vmax = 40
    for ax, (lab, m) in zip(axs, maps.items()):
        g = m["resid"].reshape(8, 8)
        im = ax.imshow(g, cmap="Blues", vmin=0, vmax=vmax)
        for i in range(8):
            for j in range(8):
                ch = i*8+j+1; ax.text(j, i, str(ch), ha="center", va="center", fontsize=6, color="white" if g[i,j] > vmax*0.55 else dk.INK)
        n = int((m["resid"] > 10).sum())
        ax.set_title("%s\n%d/64 ch with own signal" % (lab, n), fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=axs.tolist(), fraction=0.02, pad=0.02, label="differential RMS (uV, channel minus array median)")
    fig.suptitle("Same 64-ch array: acute #2 vs acute #3. Differential signal per channel", fontsize=13)
    dk.save_fig(fig, os.path.join(FIG, "weekly1016_alive_maps.png"))
# figure 2: metrics over blocks (from array_health.json) + within-block timeline
H = json.load(open(os.path.join(OUT, "array_health.json")))
H = [h for h in H if "error" not in h]
with dk.deck_style() as plt:
    fig, (a1, a2) = dk.new_fig("WIDE", nrows=1, ncols=2)
    labs = [h["label"].replace(" (", "\n(") for h in H]
    xs = np.arange(len(H))
    col = [dk.COLOR["ok"] if h["label"].startswith("acute2") else (dk.COLOR["warn"] if "bench" in h["label"] else dk.COLOR["fail"]) for h in H]
    a1.bar(xs, [h["med_pair_corr"] for h in H], color=col)
    a1.set_ylim(0.8, 1.0); a1.set_ylabel("median pairwise channel correlation"); a1.set_xticks(xs); a1.set_xticklabels([l.split("\n")[0].replace("acute2 ", "A2 ").replace("10-14 ", "") for l in labs], rotation=60, ha="right", fontsize=8)
    a1.axhline(0.9, color=dk.AXIS, ls="--", lw=1); a1.set_title("Every acute-3 block is >0.98 correlated across channels\n(acute 2: 0.87-0.90, same array)")
    a2.bar(xs, [h["resid_rms_median"] for h in H], color=col)
    a2.set_ylabel("median differential RMS (uV)"); a2.set_xticks(xs); a2.set_xticklabels([l.split("\n")[0].replace("acute2 ", "A2 ").replace("10-14 ", "") for l in labs], rotation=60, ha="right", fontsize=8)
    a2.set_ylim(0, 20); a2.set_title("Signal that is the channel's own: halved (13 -> 7 uV)\n(bench block in air off-scale: 891 uV mains)")
    dk.save_fig(fig, os.path.join(FIG, "weekly1016_array_metrics.png"))
# figure 3: within-block 10-s timeline for the 3 cortical-gate blocks + thal gate + MP
with dk.deck_style() as plt:
    fig, ax = dk.new_fig("WIDE")
    t_off = 0
    for h in H:
        if not h["label"].startswith("10-14"): continue
        w = [v for v in h["windows"] if v["med_pair_corr"] is not None]
        if not w: continue
        t = np.array([v["t"] for v in w]) / 60.0
        ax.plot(t_off + t, [v["med_pair_corr"] for v in w], lw=1.5, label=h["label"].replace("10-14 ", ""))
        t_off += t.max() + 1.0
    ax.set_ylim(0.9, 1.0); ax.set_xlabel("minutes of recording (blocks concatenated, 1 min gaps)"); ax.set_ylabel("pairwise channel corr, 10 s windows")
    ax.legend(fontsize=7, ncol=3, loc="lower right"); ax.set_title("No step change inside any block or between blocks: the array was in this state at the first recording")
    dk.save_fig(fig, os.path.join(FIG, "weekly1016_array_timeline.png"))
print("figures written")
