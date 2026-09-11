"""run_all -- regenerate every acute #2 analysis figure/JSON, in order.

Stops on first failure. Rerun any single script directly to iterate on it.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = [
    "sci_gallery.py", "sci_persite.py", "sci_rasters.py", "sci_offresp.py",
    "sci_summary.py",
    "trk_per_run.py", "trk_early_late.py", "trk_sliding.py", "trk_null.py",
    "trk_persite.py", "trk_charge.py", "trk_nn_negative.py", "trk_summary.py",
    "rank_probe_map.py", "rank_tonic_gains.py", "rank_pulse_vs_tonic.py",
    "rank_drift.py", "rank_summary.py",
]


def main():
    for s in ORDER:
        print(f"== {s} ==")
        rc = subprocess.call([sys.executable, str(HERE / s)], cwd=str(HERE))
        if rc != 0:
            raise SystemExit(f"run_all: {s} failed (rc={rc})")
    print(f"run_all: all {len(ORDER)} analysis scripts green")


if __name__ == "__main__":
    main()
