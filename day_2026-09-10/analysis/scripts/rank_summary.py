"""rank_summary -- aggregate findings for the plant-physiology family."""
import json

import rank_common as rc


def main():
    probe = json.loads((rc.ANA / "_probe_map.json").read_text())
    rank = json.loads((rc.ANA / "_rank.json").read_text())
    tonic = json.loads((rc.ANA / "_tonic.json").read_text())
    drift = json.loads((rc.ANA / "_drift.json").read_text())
    numbers = {
        "pairs_pulse_responsive": sum(1 for z in probe["best_z"] if z >= 5),
        "probe_z_range": [min(probe["best_z"]), max(probe["best_z"])],
        "pulse_eff_rank": rank["pulse_eff_rank"],
        "tonic_eff_rank": rank["tonic_eff_rank"],
        "tonic_max_gain": max(v["max_gain"] for v in tonic.values()),
        "drift_u4": drift["u4"], "drift_u6": drift["u6"],
    }
    findings = [
        f"All {numbers['pairs_pulse_responsive']}/8 thalamic pairs evoke "
        f"cortex under single pulses (feature-space z "
        f"{numbers['probe_z_range'][0]:.0f}-{numbers['probe_z_range'][1]:.0f}; "
        "acute #1 had 2/8).",
        f"Tonic drive collapses the actuator space: pulse spectrum is rich "
        f"(eff. rank {numbers['pulse_eff_rank']} at 0.1·σ1) while tonic "
        f"collapses after σ1 (σ2/σ1 = {rank['tonic_sv'][1]:.2f}; eff. rank "
        f"{numbers['tonic_eff_rank']}, only ONE direction above the "
        "|corr| 0.1 usability bar -- the day ran rank-1). MIMO/decoupled "
        "control needs a burst/duty-cycle redesign -- the acute-#3 lever.",
        f"The rank-1 channel that survives (pair 4 -> ch 64, gain "
        f"{numbers['tonic_max_gain']:.2f}) was stationary all night "
        f"(u4 {drift['u4']['early']:.3f} -> {drift['u4']['late']:.3f}); the "
        f"secondary faded (u6 {drift['u6']['early']:.3f} -> "
        f"{drift['u6']['late']:.3f}) -- drift lives in the periphery of the "
        "footprint, and feedback absorbs it.",
    ]
    rc.write_json("rank_summary.json", {"findings": findings,
                                        "numbers": numbers})


if __name__ == "__main__":
    main()
