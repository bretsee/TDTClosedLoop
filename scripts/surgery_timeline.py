"""surgery_timeline -- where the surgery-day hours went (acutes #1 and #2) vs target.

Block start times are read from the block directory names under Desktop\\Data
(HHMMSS after the date), so the timeline cannot drift from the record. Phase
labels come from the two BLOCK_LEDGER files (hand-checked mapping below).
Induction times are the user's statement (09:00-10:00); the first block of
each day is the first hard timestamp we have.

Outputs: outputs/deck_figures/surgery_timeline.png (WIDE) + _surgery_timeline.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import deckkit as dk  # noqa: E402

DATA = Path(r"C:\Users\brets\Desktop\Data")
OUT = REPO / "outputs" / "deck_figures"

DAYS = {
    "acute #1  2026-08-31 (32 ch)": ("BSClosedLoop32-260831-", {
        "122406": ("pre-animal G8 test", "prep"),
        "174013": ("quiet capture", "quiet"),
        "175746": ("thwack battery", "battery"), "180137": ("thwack battery", "battery"),
        "180520": ("thwack battery", "battery"), "180905": ("thwack battery", "battery"),
        "181248": ("thwack battery", "battery"), "181632": ("thwack battery", "battery"),
        "182004": ("thwack battery", "battery"), "182330": ("thwack battery", "battery"),
        "182722": ("thwack battery", "battery"), "183157": ("thwack battery", "battery"),
        "183856": ("probe rnd1 (30 min) -> fitter NO-GO", "probe"),
        "194938": ("re-probe 30 uA -> raw-LFP rescue", "probe"),
        "201744": ("operating-point fit", "fit"),
        "204547": ("arm (inert, rerun)", "arms"), "210818": ("arms", "arms"),
        "211935": ("arms", "arms"), "213101": ("arms", "arms"), "214109": ("arms", "arms"),
        "215429": ("drift re-probe", "wrap"),
    }),
    "acute #2  2026-09-10 (64 ch)": ("BSCL20260909BU-260910-", {
        "183709": ("quiet capture", "quiet"),
        "185201": ("thwack battery", "battery"), "185534": ("thwack battery", "battery"),
        "191241": ("thwack battery", "battery"), "191958": ("thwack battery", "battery"),
        "192302": ("thwack battery", "battery"), "192604": ("thwack battery", "battery"),
        "192914": ("thwack battery", "battery"), "193215": ("thwack battery", "battery"),
        "193528": ("thwack battery", "battery"), "193840": ("thwack battery", "battery"),
        "200410": ("probe rnd1 (30 min)", "probe"),
        "210727": ("op-point fits (3 ladders)", "fit"), "211953": ("op-point fits", "fit"),
        "213208": ("op-point fits", "fit"),
        "215613": ("arms", "arms"), "220332": ("arms", "arms"), "221053": ("arms", "arms"),
        "221543": ("arms", "arms"), "222149": ("arms", "arms"), "222643": ("arms", "arms"),
        "223341": ("arms", "arms"), "223918": ("arms", "arms"), "230004": ("arms (PZ2-off void)", "arms"),
        "230537": ("arms (PZ2-off void)", "arms"), "231143": ("re-probe (void)", "arms"),
        "231833": ("arms", "arms"), "232426": ("arms", "arms"), "233015": ("drift re-probe", "wrap"),
    }),
}
PHASE_COLOR = {"prep": dk.MUTED, "quiet": dk.CAT[3], "battery": dk.COLOR["touch"],
               "probe": dk.COLOR["stim"], "fit": dk.CAT[5], "arms": dk.COLOR["mpc"], "wrap": dk.MUTED}
INDUCTION_H = 9.5      # user: 09:00-10:00
TARGET_REC_H = 15.5    # user: recordings by 15:00-16:00


def hhmmss_to_h(s):
    return int(s[:2]) + int(s[2:4]) / 60 + int(s[4:6]) / 3600


def block_hours(prefix):
    out = {}
    roots = [DATA] + [d for d in DATA.iterdir() if d.is_dir() and "LaterBlocks" in d.name]
    for root in roots:
        for d in root.iterdir():
            m = re.match(re.escape(prefix) + r"(\d{6})$", d.name)
            if m and d.is_dir():
                out[m.group(1)] = hhmmss_to_h(m.group(1))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    with dk.deck_style() as plt:
        fig, axes = plt.subplots(len(DAYS), 1, figsize=dk.FIGSIZE["WIDE"], sharex=True)
        for ax, (day, (prefix, labels)) in zip(axes, DAYS.items()):
            hours = block_hours(prefix)
            missing = [k for k in labels if k not in hours]
            if missing:
                raise SystemExit(f"{day}: blocks missing on disk: {missing}")
            keys = sorted(labels)
            first = hours[keys[0]] if "prep" not in labels[keys[0]][1] else hours[keys[1]]
            first_arm = min(hours[k] for k in keys if labels[k][1] == "arms")
            last = max(hours.values())
            end = last + 0.4 if last < 23.9 else 24.0
            # phase spans: from each block start to the next block start
            for i, k in enumerate(keys):
                t0 = hours[k]
                t1 = hours[keys[i + 1]] if i + 1 < len(keys) else last + 0.3
                if t1 < t0:
                    t1 = 24.0
                ax.barh(0, t1 - t0, left=t0, color=PHASE_COLOR[labels[k][1]], height=0.6, lw=0)
            ax.axvspan(INDUCTION_H, first, color=dk.GRID, alpha=0.7, lw=0)
            ax.text((INDUCTION_H + first) / 2, 0.55, f"surgery + implant + localisation\n{first - INDUCTION_H:.1f} h",
                    ha="center", va="bottom", fontsize=9, color=dk.INK_2)
            ax.axvline(TARGET_REC_H, color=dk.COLOR["stim"], ls="--", lw=1.2)
            ax.text(TARGET_REC_H + 0.05, -0.5, "target: first recording 15:30", color=dk.COLOR["stim"], fontsize=8)
            ax.axvline(first_arm, color=dk.COLOR["mpc"], ls=":", lw=1.2)
            ax.text(first_arm + 0.05, -0.5, f"first arm {first_arm:.1f} h", color=dk.COLOR["mpc"], fontsize=8)
            ax.set_yticks([]); ax.set_ylim(-0.7, 1.0)
            ax.set_title(day, loc="left")
            ax.grid(True, axis="x"); ax.grid(False, axis="y")
            summary[day] = dict(induction_h=INDUCTION_H, first_block_h=round(first, 2),
                                first_arm_h=round(first_arm, 2), last_block_h=round(last, 2),
                                surgery_to_first_block_h=round(first - INDUCTION_H, 2),
                                first_block_to_first_arm_h=round(first_arm - first, 2),
                                arms_span_h=round(last - first_arm, 2),
                                gap_vs_target_h=round(first - TARGET_REC_H, 2))
        axes[-1].set_xlabel("clock hour")
        axes[-1].set_xlim(9, 24.2)
        axes[-1].set_xticks(range(9, 25))
        from matplotlib.patches import Patch
        handles = [Patch(color=c, label=k) for k, c in PHASE_COLOR.items() if k != "prep"]
        axes[0].legend(handles=handles, frameon=False, ncols=6, fontsize=8, loc="upper right",
                       bbox_to_anchor=(1.0, 1.35))
        dk.save_fig(fig, OUT / "surgery_timeline.png")
    (OUT / "_surgery_timeline.json").write_text(json.dumps(summary, indent=2))
    for d, s in summary.items():
        print(d, s)


if __name__ == "__main__":
    main()
