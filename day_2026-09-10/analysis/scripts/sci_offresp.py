"""sci_offresp -- the LP OFF-response, from raw blocks (not template-limited).

FULL figure: mean traces to 400 ms for LP (sharp OFF at release) vs D1
(no OFF) vs SHAM, shared axes; release marker at 254.6 ms. Quantifies the
post-release deflection in a 255-320 ms window for every site.
"""
import numpy as np

import sci_common as sc
import deckkit as dk

SHOW = ["LP", "D1", "SHAM"]
COLORS = {"LP": dk.COLOR["stim"], "D1": dk.COLOR["mpc"], "SHAM": dk.COLOR["null"]}
OFF_WIN_MS = (258.0, 330.0)


def off_peak(E, t_ms) -> float:
    m = E.mean(axis=0)
    sel = (t_ms >= OFF_WIN_MS[0]) & (t_ms <= OFF_WIN_MS[1])
    seg = m[sel]
    return float(seg[np.abs(seg).argmax()])


def main():
    metas = {m["site"]: m for m in sc.registry()}
    table = {}
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("FULL")
        for site in SHOW:
            E, t_ms = sc.epochs(metas[site])
            ax.plot(t_ms, E.mean(axis=0), color=COLORS[site], lw=2.2,
                    label=f"{site} (ch{metas[site]['best_channel_1based']})")
        ax.axvline(0, color=dk.INK, lw=0.8, ls="--")
        ax.axvline(sc.CONTACT_MS, color=dk.CAT[5], lw=1.0, ls="--")
        ax.text(sc.CONTACT_MS + 4, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1]
                else 50, "release", fontsize=9, color=dk.INK_2)
        ax.set_xlabel("ms from contact")
        ax.set_ylabel("mean LFP (uV)")
        ax.set_title("OFF-response is site-specific: sharp at LP, absent at D1")
        ax.legend(frameon=False)
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, sc.ANA / "sci_offresp.png")
    for site, m in metas.items():
        E, t_ms = sc.epochs(m)
        table[site] = round(off_peak(E, t_ms), 1)
    sc.write_json("_offresp.json", {
        "off_window_ms": OFF_WIN_MS,
        "off_peak_uv_by_site": table,
        "status": "computed_from_raw_blocks",
    })


if __name__ == "__main__":
    main()
