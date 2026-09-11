"""trk_summary -- aggregate findings + numbers for the arms family."""
import json

import trk_common as tc


def main():
    per_run = json.loads((tc.ANA / "_per_run.json").read_text())
    el = json.loads((tc.ANA / "_early_late.json").read_text())
    null = json.loads((tc.ANA / "_null.json").read_text())
    charge = json.loads((tc.ANA / "_charge.json").read_text())
    nn = json.loads((tc.ANA / "_nn.json").read_text())
    mpc_r0 = [m["r0"] for m in per_run["mpc"]]
    choi_r0 = [c["r0"] for c in per_run["choi"]]
    d_mpc = el["pairs"]["MPC"]["late"]["r0"] - el["pairs"]["MPC"]["early"]["r0"]
    d_choi = el["pairs"]["Choi"]["late"]["r0"] - el["pairs"]["Choi"]["early"]["r0"]
    numbers = {
        "mpc_r0_range": [min(mpc_r0), max(mpc_r0)],
        "choi_r0_range": [min(choi_r0), max(choi_r0)],
        "mpc_all_lag0": all(m["best_lag"] == 0 for m in per_run["mpc"]),
        "early_late_delta": {"MPC": d_mpc, "Choi": d_choi},
        "mpc_late_slope": el["pairs"]["MPC"]["late"]["slope"],
        "null_p_bound": null["p_value_bound"],
        "charge_r1": {"mpc": charge["mpc"]["mpc_r1"],
                      "choi": charge["choi"]["choi_r1"]},
        "r4b": {"r0": tc.recompute("mpc_r4b")["r0"],
                "charge": charge["mpc"]["mpc_r4b"]},
        "nn_r0": nn["r0"],
    }
    findings = [
        f"MPC tracked at lag 0 in every run (r0 "
        f"{numbers['mpc_r0_range'][0]:.2f}-{numbers['mpc_r0_range'][1]:.2f}); "
        f"Choi r0 {numbers['choi_r0_range'][0]:.2f}-"
        f"{numbers['choi_r0_range'][1]:.2f} at a wandering best lag.",
        f"Feedback adapts, replay cannot: identical tape ~2 h apart, MPC "
        f"{d_mpc:+.3f} with amplitude slope re-converging to "
        f"{numbers['mpc_late_slope']:.3f}; Choi {d_choi:+.3f}, flat.",
        f"Tracking is genuine reference-following: circular-shift null "
        f"p < {numbers['null_p_bound']:.3f}; mean-drive NN tape r0 "
        f"{numbers['nn_r0']:.2f}.",
        f"Charge reversal vs acute #1: MPC {charge['mpc']['mpc_r1']/1e3:.0f}k "
        f"vs Choi {charge['choi']['choi_r1']/1e3:.0f}k µA-ticks in r1; "
        f"fidelity robust to a 3× input penalty (r4b), frontier "
        f"drift-confounded -> acute #3 time-controlled sweep.",
    ]
    tc.write_json("trk_summary.json", {"findings": findings, "numbers": numbers})


if __name__ == "__main__":
    main()
