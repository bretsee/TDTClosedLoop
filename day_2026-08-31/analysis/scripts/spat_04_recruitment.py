"""spat_recruitment.png: recruitment curves (ch 8 signed peak vs amplitude) per stim pair."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

plt = sc.style()

CACHE = os.path.join(sc.ANA_DIR, "cache")
fs = sc.FS_WAV
CH = 7  # ch 8, 0-based


def curves(tag):
    z = np.load(os.path.join(CACHE, f"probe_{tag}.npz"))
    tr, npre = z["trials"].astype(float), int(z["n_pre"])
    pairs, amps = z["pairs"], z["amps"]
    a = npre + int(round(0.005 * fs))
    b = npre + int(round(0.040 * fs))
    out = {}
    for pr in range(1, 9):
        rows = []
        for amp in np.unique(amps):
            m = (pairs == pr) & (amps == amp)
            if m.sum() < 5:
                continue
            mw = tr[m, CH, a:b].mean(axis=0)
            k = np.abs(mw).argmax()
            val = mw[k]
            sem = tr[m, CH, a + k].std(ddof=1) / np.sqrt(m.sum())
            rows.append((int(amp), float(val), float(sem), int(m.sum())))
        out[pr] = rows
    return out

c1 = curves("rnd1")
c2 = curves("rndhi")

fig, axes = plt.subplots(2, 4, figsize=(13.5, 6.8), sharex=True, sharey=True)
knee_lo, knee_hi = 13, 18
summary = {}
for pr in range(1, 9):
    ax = axes[(pr - 1) // 4, (pr - 1) % 4]
    ax.axvspan(knee_lo, knee_hi, color="#EEEEEE", zorder=0)
    for cur, col, mark, lab in ((c1[pr], sc.GREEN, "o", "rnd1"),
                                (c2[pr], sc.AMBER, "s", "rndhi")):
        if not cur:
            continue
        xs = [r[0] for r in cur]; ys = [r[1] for r in cur]; es = [r[2] for r in cur]
        ax.errorbar(xs, ys, yerr=es, color=col, marker=mark, ms=4, lw=1.3,
                    capsize=2, label=lab)
    ax.axhline(0, color="#CCCCCC", lw=0.6, zorder=0)
    y25 = [r[1] for r in c1[pr] if r[0] == 25]
    ax.set_title(f"pair {pr}" + (f"  ({y25[0]:.0f} µV @25)" if y25 else ""), fontsize=10)
    if pr == 1:
        ax.legend(frameon=False, fontsize=8, loc="upper left")
    if (pr - 1) // 4 == 1:
        ax.set_xlabel("amplitude (µA)")
    if (pr - 1) % 4 == 0:
        ax.set_ylabel("ch 8 signed peak, 5–40 ms (µV)")
    summary[f"pair{pr}"] = {"rnd1": c1[pr], "rndhi": c2[pr]}

# knee estimate: lowest amp reaching 50% of |max| within rnd1
knees = {}
for pr in range(1, 9):
    rows = c1[pr]
    if rows:
        ymax = max(abs(r[1]) for r in rows)
        k = [r[0] for r in rows if abs(r[1]) >= 0.5 * ymax]
        knees[f"pair{pr}"] = min(k) if k else None

fig.suptitle(
    "Recruitment (ch 8): only arm pairs 1 & 4 recruit positively (119 / 222 µV @25 µA), turning on above the\n"
    "shaded 13–18 µA knee band and still rising at 30 µA (no saturation); other pairs weak (<100 µV) or\n"
    "negative-going (3, 6); rnd1 vs rndhi disagree on pairs 3/5/7 — state drift between probe blocks",
    fontsize=11, y=0.995)
fig.subplots_adjust(left=0.07, right=0.98, top=0.80, bottom=0.10, hspace=0.35, wspace=0.15)
out = os.path.join(sc.ANA_DIR, "spat_recruitment.png")
fig.savefig(out)
print("wrote", out)
print("half-max amps:", knees)
sc.save_json_part("recruitment", {
    "channel_1based": 8,
    "window_ms": [5, 40],
    "curves_amp_signedpeak_sem_n": summary,
    "half_max_amp": knees,
    "knee_band_marked_uA": [knee_lo, knee_hi],
})
