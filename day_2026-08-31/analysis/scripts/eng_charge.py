"""eng_charge.png - commanded-amplitude (charge-proportional) ledger per run."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eng_common import (GREEN, GREY, RED, AMBER, MUTED, INK, RUNS,
                        capture_u_filled, parse_log, save)
import matplotlib.pyplot as plt

HOLD_UA = 20.0
TICK_S = 0.0098304

NTICKS = {"rnd1": 183000, "rndhi": 28000, "opfit": 12000, "opfit2": 12000,
          "mpc_mixr1": 22200, "mpc_mixr1b": 22200, "mpc_mixr2": 22200,
          "choi_mixr1": 22200, "choi_mixr2": 22200}

order = ["rnd1", "rndhi", "opfit", "mpc_mixr1", "mpc_mixr1b", "choi_mixr1",
         "mpc_mixr2", "choi_mixr2", "opfit2"]

ledger = {}
for lab in order:
    U, nlogged = capture_u_filled(lab, NTICKS[lab])
    held = np.median(U, axis=0) > 10.0            # tonically-held channels
    tonic = HOLD_UA * NTICKS[lab] * held.sum()    # baseline component
    mod = float(np.abs(U[:, held] - HOLD_UA).sum() + U[:, ~held].sum())
    delivered = float(U.sum())
    ledger[lab] = {
        "nticks": NTICKS[lab],
        "capture_rows": nlogged,
        "held_channels": [f"u{i+1}" for i in range(8) if held[i]],
        "tonic_hold_uA_ticks": round(tonic, 0),
        "modulation_uA_ticks": round(mod, 0),
        "delivered_total_uA_ticks": round(delivered, 0),
        "delivered_total_uA_s": round(delivered * TICK_S, 0),
        "mean_delivered_uA_per_tick_per_held_pair": (
            round(delivered / NTICKS[lab] / max(held.sum(), 1), 2) if held.any() else None),
    }

modcolor = {"rnd1": GREY, "rndhi": GREY, "opfit": GREY, "opfit2": GREY,
            "mpc_mixr1": GREEN, "mpc_mixr1b": GREEN, "mpc_mixr2": GREEN,
            "choi_mixr1": "#8A93A0", "choi_mixr2": "#8A93A0"}

fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.6),
                               gridspec_kw={"width_ratios": [2.1, 1.0], "wspace": 0.28})
fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.17)

x = np.arange(len(order))
tonics = np.array([ledger[l]["tonic_hold_uA_ticks"] for l in order]) / 1e6
mods = np.array([ledger[l]["modulation_uA_ticks"] for l in order]) / 1e6
deliv = np.array([ledger[l]["delivered_total_uA_ticks"] for l in order]) / 1e6

axL.bar(x, tonics, 0.62, color=AMBER, label="tonic hold (20 µA × held pairs)",
        zorder=3)
axL.bar(x, mods, 0.62, bottom=tonics, zorder=3,
        color=[modcolor[l] for l in order], label="modulation Σ|u − hold|")
axL.scatter(x, deliv, marker="D", s=26, color=INK, zorder=4,
            label="delivered Σu (actual)")
for xi, l in zip(x, order):
    axL.text(xi, tonics[xi] + mods[xi] + 0.035, f"{deliv[xi]:.2f}",
             ha="center", fontsize=7.5, color=INK)
axL.set_xticks(x)
axL.set_xticklabels(order, rotation=35, ha="right", fontsize=8)
axL.set_ylabel("10⁶ µA·ticks  (1 tick = 9.83 ms, 1 carrier pulse)")
axL.set_title("Per-run ledger: Choi delivered ~30% more charge than MPC on the same\n"
              "schedule (1.19 vs 0.92 ×10⁶ µA·ticks); labels = delivered Σu",
              loc="left")
axL.legend(loc="upper left", fontsize=7.5)
axL.grid(True, axis="y", color="#DDDDDD", lw=0.6)
axL.set_axisbelow(True)
axL.spines[["top", "right"]].set_visible(False)

cum = np.cumsum(deliv)
axR.step(x, cum, where="mid", color=GREEN, lw=2)
axR.scatter(x, cum, s=18, color=GREEN, zorder=3)
axR.set_xticks(x)
axR.set_xticklabels(order, rotation=35, ha="right", fontsize=8)
axR.set_ylabel("cumulative 10⁶ µA·ticks")
day_total = cum[-1]
axR.set_title(f"Day total {day_total:.2f} ×10⁶ µA·ticks\n"
              "(one carrier pulse per 9.83 ms tick)",
              loc="left")
axR.grid(True, axis="y", color="#DDDDDD", lw=0.6)
axR.set_axisbelow(True)
axR.spines[["top", "right"]].set_visible(False)
axR.text(x[-1], cum[-1], f"  {day_total:.2f}", fontsize=8, va="center", color=INK)

fig.suptitle("Charge ledger (commanded amplitude, proportional to charge): tonic hold dominates arm runs; "
             "Choi's precomputed bursts ride the 30 µA cap while MPC modulates around hold",
             fontsize=11.5, fontweight="bold", color="black", x=0.08, ha="left", y=0.97)

save(fig, "eng_charge.png")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_charge.json"), "w") as f:
    json.dump({"per_run": ledger,
               "day_total_delivered_uA_ticks": round(float(deliv.sum() * 1e6), 0),
               "day_total_delivered_uA_s": round(float(deliv.sum() * 1e6 * TICK_S), 0),
               "hold_uA": HOLD_UA,
               "note": ("MPC captures log only submitted ticks; skipped ticks forward-filled "
                        "(loop holds last command). Stacked bar = tonic+|u-hold| per the ledger "
                        "definition; diamond = actual delivered sum(u), which for Choi off-ticks "
                        "is below tonic+modulation.")},
              f, indent=1)
print("charge stashed")
for l in order:
    print(l, ledger[l]["delivered_total_uA_ticks"], ledger[l]["held_channels"])
