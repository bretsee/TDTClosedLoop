"""eng_u_strategy.png - MPC vs Choi command strategy on the same schedule (mix r1)."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eng_common import (GREEN, GREY, RED, AMBER, MUTED, INK, DAY, TICK_MS,
                        capture_u_filled, save)
import matplotlib.pyplot as plt

NT = 22200
PRE, POST = 30, 190  # ticks around event onset (period is 220)

sched = json.load(open(os.path.join(DAY, "schedule_mix_r1.json")))
events = sched["events"]
sites = sched["sites"]  # ['D1','D2','D3','P2','LP','SHAM']

Ump, _ = capture_u_filled("mpc_mixr1b", NT)
Uch, _ = capture_u_filled("choi_mixr1", NT)


def eta(U, uidx, onsets):
    """event-triggered matrix (nev, PRE+POST) for channel uidx (0-based)."""
    out = []
    for o in onsets:
        i0, i1 = o - 1 - PRE, o - 1 + POST
        if i0 >= 0 and i1 <= NT:
            out.append(U[i0:i1, uidx])
    return np.array(out)


fig = plt.figure(figsize=(12.5, 8.0))
gs = fig.add_gridspec(3, 6, hspace=0.55, wspace=0.14,
                      left=0.06, right=0.985, top=0.855, bottom=0.07,
                      height_ratios=[1, 1, 1.25])

tt = (np.arange(-PRE, POST) * TICK_MS) / 1000.0
for row, uidx, uname in ((0, 0, "u1"), (1, 3, "u4")):
    for col, site in enumerate(sites):
        ax = fig.add_subplot(gs[row, col])
        ons = [e["onset_tick"] for e in events if e["site"] == site]
        m = eta(Ump, uidx, ons)
        c = eta(Uch, uidx, ons)
        ax.axvline(0, color="#CCCCCC", lw=0.8)
        ax.axhline(20, color=AMBER, lw=0.8, ls=":")
        ax.plot(tt, c.mean(0), color=GREY, lw=1.4)
        ax.plot(tt, m.mean(0), color=GREEN, lw=1.4)
        ax.set_ylim(-1, 31)
        ax.set_xlim(tt[0], tt[-1])
        if row == 0:
            ax.set_title(f"{site}  (n={len(ons)})", loc="left", fontsize=9)
        if col == 0:
            ax.set_ylabel(f"{uname} (µA)", fontsize=9)
        else:
            ax.set_yticklabels([])
        if row == 1:
            ax.set_xlabel("s from event onset", fontsize=8)
        else:
            ax.set_xticklabels([])
        ax.tick_params(labelsize=7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(True, axis="y", color="#EEEEEE", lw=0.5)
        ax.set_axisbelow(True)
        if row == 0 and col == 0:
            ax.text(0.03, 0.95, "MPC", color=GREEN, transform=ax.transAxes,
                    fontsize=8.5, fontweight="bold", va="top")
            ax.text(0.03, 0.82, "Choi", color=GREY, transform=ax.transAxes,
                    fontsize=8.5, fontweight="bold", va="top")
            ax.text(0.6, 0.72, "hold 20 µA", color=AMBER, transform=ax.transAxes,
                    fontsize=7)

# --- bottom left: amplitude distributions ---
axH = fig.add_subplot(gs[2, 0:3])
bins = np.linspace(0, 30, 61)
pool_m = np.concatenate([Ump[:, 0], Ump[:, 3]])
pool_c = np.concatenate([Uch[:, 0], Uch[:, 3]])
axH.hist(pool_c, bins=bins, color=GREY, alpha=0.85, label="Choi", zorder=2)
axH.hist(pool_m, bins=bins, color=GREEN, alpha=0.85, label="MPC", zorder=3)
axH.set_yscale("log")
axH.set_xlabel("commanded amplitude (µA), u1+u4 pooled over run")
axH.set_ylabel("ticks (log)")
axH.legend(loc="upper center")
axH.set_title("Amplitude use: MPC lives in a ±5 µA band around hold;\n"
              "Choi is near-bang-bang between 0 and the 30 µA cap", loc="left")
axH.spines[["top", "right"]].set_visible(False)
axH.grid(True, axis="y", color="#EEEEEE", lw=0.5)
axH.set_axisbelow(True)

# --- bottom right: duty / activity stats ---
axD = fig.add_subplot(gs[2, 3:6])
def stats(p):
    dm = np.abs(np.diff(p))
    return [float(np.mean(p >= 29.9) * 100), float(np.mean(p < 0.05) * 100),
            float(np.mean(np.abs(p - 20) < 0.5) * 100), float(dm.mean())]
sm, sc = stats(pool_m), stats(pool_c)
cats = ["at 30 µA cap\n(% ticks)", "at 0 µA\n(% ticks)", "within ±0.5 µA\nof hold (%)",
        "mean |Δu| per tick\n(µA ×10)"]
smp = [sm[0], sm[1], sm[2], sm[3] * 10]
scp = [sc[0], sc[1], sc[2], sc[3] * 10]
xx = np.arange(len(cats))
axD.bar(xx - 0.19, smp, 0.34, color=GREEN, label="MPC", zorder=3)
axD.bar(xx + 0.19, scp, 0.34, color=GREY, label="Choi", zorder=3)
for xi, (a, b) in enumerate(zip(smp, scp)):
    axD.text(xi - 0.19, a + 1.2, f"{a:.1f}", ha="center", fontsize=7.5)
    axD.text(xi + 0.19, b + 1.2, f"{b:.1f}", ha="center", fontsize=7.5)
axD.set_xticks(xx)
axD.set_xticklabels(cats, fontsize=7.5)
axD.legend(loc="upper left")
axD.set_title("Duty: Choi saturates the cap 48% of ticks and slews ~5× harder;\n"
              "MPC spends 49% of ticks within ±0.5 µA of hold", loc="left")
axD.spines[["top", "right"]].set_visible(False)
axD.grid(True, axis="y", color="#EEEEEE", lw=0.5)
axD.set_axisbelow(True)

fig.suptitle("Command strategy on the SAME schedule (mix r1): MPC is reactive and parsimonious "
             "(±5 µA excursions around the 20 µA hold, back to hold between events);\n"
             "Choi's precomputed drive rides near the 30 µA cap with brief full shut-offs "
             "at event onsets — on SHAM too — explaining its +30% charge at matched scores",
             fontsize=11, fontweight="bold", color="black", x=0.06, ha="left", y=0.975)
fig.text(0.06, 0.885, "Top rows: event-triggered mean of u1 / u4 per site "
         "(mpc_mixr1b vs choi_mixr1, n = events per site); amber dotted = tonic hold.",
         fontsize=8.5, color=MUTED)

save(fig, "eng_u_strategy.png")
out = {"mpc": {"pct_at_cap": sm[0], "pct_at_zero": sm[1], "pct_near_hold": sm[2],
               "mean_abs_du_uA": sm[3]},
       "choi": {"pct_at_cap": sc[0], "pct_at_zero": sc[1], "pct_near_hold": sc[2],
                "mean_abs_du_uA": sc[3]},
       "slew_ratio_choi_over_mpc": round(sc[3] / sm[3], 2)}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ustrat.json"), "w") as f:
    json.dump(out, f, indent=1)
print(out)
