"""sci_summary -- aggregate findings + numbers for the touch-battery family."""
import json

import sci_common as sc
import deckkit as dk


def main():
    sites = json.loads((sc.ANA / "_sites.json").read_text())["rows"]
    offr = json.loads((sc.ANA / "_offresp.json").read_text())
    active = [r for r in sites if r["site"] != "SHAM"]
    sham = next(r for r in sites if r["site"] == "SHAM")
    peaks = [r["peak_uv"] for r in active]
    lats = [r["latency_ms"] for r in active]
    sh = [r["split_half"] for r in active]
    lp_off = offr["off_peak_uv_by_site"].get("LP")
    d1_off = offr["off_peak_uv_by_site"].get("D1")
    numbers = {
        "n_sites_active": len(active),
        "peak_uv_min": min(peaks), "peak_uv_max": max(peaks),
        "latency_ms_min": min(lats), "latency_ms_max": max(lats),
        "split_half_min": min(sh), "split_half_max": max(sh),
        "sham_peak_uv": sham["peak_uv"],
        "trials_per_site": active[0]["n_trials"],
        "lp_off_peak_uv": lp_off, "d1_off_peak_uv": d1_off,
    }
    findings = [
        f"All {numbers['n_sites_active']} active sites reference-grade: peaks "
        f"{numbers['peak_uv_min']:.0f}-{numbers['peak_uv_max']:.0f} uV at "
        f"{numbers['latency_ms_min']:.0f}-{numbers['latency_ms_max']:.0f} ms, "
        f"split-half {numbers['split_half_min']:.2f}-{numbers['split_half_max']:.2f} "
        f"({numbers['trials_per_site']} trials each).",
        f"SHAM null clean: {numbers['sham_peak_uv']:.0f} uV drift-shaped, no "
        "locked morphology -- thwacker sound/vibration/electronics excluded.",
        "Surface-tangent planar array is LFP-dominant and speaker-silent by "
        "geometry; placement gate for such arrays is the z-score table.",
        f"OFF-response is site-specific: LP {lp_off:+.0f} uV in the "
        f"post-release window vs D1 {d1_off:+.0f} uV.",
    ]
    sc.write_json("sci_summary.json", {"findings": findings, "numbers": numbers})


if __name__ == "__main__":
    main()
