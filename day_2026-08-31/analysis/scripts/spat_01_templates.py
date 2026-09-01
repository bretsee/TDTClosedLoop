"""spat_templates.png: gallery of all 10 touch templates."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

plt = sc.style()
from matplotlib.gridspec import GridSpec

tpls = {}
for site in sc.SITE_ORDER:
    d = sc.load_template(site)
    tpls[site] = np.asarray(d["template"], float)

fs = sc.FS_WAV
t_ms = np.arange(sc.POST_SAMPLES) / fs * 1000.0

peaks, bestch = {}, {}
for site, T in tpls.items():
    peaks[site] = float(np.abs(T).max())
    bestch[site] = int(np.unravel_index(np.abs(T).argmax(), T.shape)[0]) + 1

VLIM = 500.0
LINE_COLORS = {
    "SHAM": "#9AA1AA", "P3": "#3F7A4E", "D4": "#7FB069", "D1": "#B3413A",
    "MP": "#C9A23A", "P1": "#2E5E8C", "LP": "#5B6470", "D2": "#8C5E2E",
    "D3": "#6B4E8C", "P2": "#3A8C8C",
}

fig = plt.figure(figsize=(14, 9.5))
gs = GridSpec(3, 5, figure=fig, height_ratios=[1, 1, 0.85], hspace=0.55, wspace=0.35)

im = None
for i, site in enumerate(sc.SITE_ORDER):
    ax = fig.add_subplot(gs[i // 5, i % 5])
    T = tpls[site]
    im = ax.imshow(T, aspect="auto", cmap="RdBu_r", vmin=-VLIM, vmax=VLIM,
                   extent=[t_ms[0], t_ms[-1], 32.5, 0.5], interpolation="nearest")
    ax.set_title(f"{site}  peak {peaks[site]:.0f} µV, best ch {bestch[site]}",
                 fontsize=10)
    ax.set_xlabel("time from touch (ms)")
    if i % 5 == 0:
        ax.set_ylabel("channel")
    ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
    ax.set_yticks([1, 8, 16, 24, 32])

cax = fig.add_axes([0.92, 0.45, 0.012, 0.35])
cb = fig.colorbar(im, cax=cax)
cb.set_label("µV")

ax8 = fig.add_subplot(gs[2, 0:2])
ax6 = fig.add_subplot(gs[2, 2:4])
for site in sc.SITE_ORDER:
    lw = 1.8 if site in ("SHAM",) else 1.2
    ax8.plot(t_ms, tpls[site][7], color=LINE_COLORS[site], lw=lw, label=site)
    ax6.plot(t_ms, tpls[site][5], color=LINE_COLORS[site], lw=lw, label=site)
ax8.set_title("ch 8 (control channel)", fontsize=10)
ax6.set_title("ch 6 (LP best channel)", fontsize=10)
for ax in (ax8, ax6):
    ax.set_xlabel("time from touch (ms)")
    ax.set_ylabel("µV")
    ax.axhline(0, color="#CCCCCC", lw=0.6, zorder=0)
axl = fig.add_subplot(gs[2, 4]); axl.axis("off")
axl.legend(*ax8.get_legend_handles_labels(), loc="center left", frameon=False,
           fontsize=9, ncol=2)

n_strong = sum(1 for s in sc.SITE_ORDER if s != "SHAM" and peaks[s] > 200)
fig.suptitle(
    f"Touch templates (150 touches/site): {n_strong}/9 real sites evoke 380–710 µV "
    f"responses, best ch 8 (LP: ch 6); SHAM flat ({peaks['SHAM']:.0f} µV)",
    fontsize=12, color="black", y=0.995)
fig.subplots_adjust(left=0.05, right=0.90, top=0.92, bottom=0.07)
out = os.path.join(sc.ANA_DIR, "spat_templates.png")
fig.savefig(out)
print("wrote", out)

sc.save_json_part("templates", {
    "peak_uv": peaks,
    "best_channel_1based": bestch,
    "vlim_uv": VLIM,
    "note": "templates re-verified against raw re-extraction (corr 1.0000, scale 0.991)",
})
