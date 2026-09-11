"""spat_summary -- findings for the spatial/decoding family (deck v2)."""
import json

import spat_common as sp


def main():
    dec = json.loads((sp.ANA / "_decode.json").read_text())
    fp = json.loads((sp.ANA / "_footprint.json").read_text())
    numbers = {
        "decode_mpc_all5": dec["MPC"]["accuracy"],
        "decode_mpc_active4": dec["MPC"]["accuracy_active"],
        "decode_choi_all5": dec["Choi"]["accuracy"],
        "decode_choi_active4": dec["Choi"]["accuracy_active"],
        "chance_5way": dec["chance"], "chance_4way": 0.25,
        "footprint_r": fp["mpc_vs_choi_footprint_r"],
    }
    findings = [
        f"Target-vs-no-target IS separable (SHAM decodes ~60%); but among "
        f"the four biomimetic sites the 64-ch pattern is near chance "
        f"(MPC {dec['MPC']['accuracy_active']*100:.0f}%, Choi "
        f"{dec['Choi']['accuracy_active']*100:.0f}% vs 25%): one fixed stim "
        "footprint tracks a target's TIME COURSE but cannot SELECT its "
        "spatial identity -- the selectivity negative holds at 64 ch.",
        f"Raw-LFP footprints of the two arms are near-identical "
        f"(r = {fp['mpc_vs_choi_footprint_r']:.3f}): both drive the same "
        "cortical territory, as expected for a rank-1 actuator.",
        "Quantitative basis for the acute-#3 redesign: recover actuator "
        "rank (burst/duty-cycle drive) before spatial selection is "
        "achievable. Feature-space result; raw-LFP artifact-aware redo next.",
    ]
    sp.write_json("spat_summary.json", {"findings": findings,
                                        "numbers": numbers})


if __name__ == "__main__":
    main()
