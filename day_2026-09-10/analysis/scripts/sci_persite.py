"""sci_persite -- battery magnitudes bar chart (WIDE) + site table JSON."""
import numpy as np

import sci_common as sc
import deckkit as dk


def main():
    metas = sc.registry()
    sites = [m["site"] for m in metas]
    peaks = [float(m["peak_uv"]) for m in metas]
    lats = [sc.latency_ms(m) for m in metas]
    with dk.deck_style() as plt:
        fig, ax = dk.new_fig("WIDE")
        colors = [dk.COLOR["null"] if s == "SHAM" else dk.COLOR["touch"]
                  for s in sites]
        bars = ax.bar(sites, peaks, color=colors, width=0.62)
        for b, v in zip(bars, peaks):
            ax.text(b.get_x() + b.get_width() / 2, v + 8, f"{v:.0f}",
                    ha="center", fontsize=9, color=dk.INK_2)
        ax.set_ylabel("|peak| evoked LFP (uV)")
        ax.set_title("Touch battery -- evoked magnitude by site "
                     "(SHAM = no-contact null)")
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
        dk.save_fig(fig, sc.ANA / "sci_persite.png")
    rows = [{
        "site": m["site"],
        "block": m["block"],
        "peak_uv": round(float(m["peak_uv"]), 1),
        "best_channel": int(m["best_channel_1based"]),
        "latency_ms": round(l, 1),
        "split_half": round(float(m["split_half_corr"]), 3),
        "n_trials": int(m["n_used"]),
    } for m, l in zip(metas, lats)]
    sc.write_json("_sites.json", {"rows": rows})


if __name__ == "__main__":
    main()
