"""Compute per-event metrics for every (arm, run) and cache as CSV for the figure scripts."""
import csv

import sci_common as C

rows_all = []
for arm, run in C.ARMS:
    rows = C.per_event_table(arm, run)
    for r in rows:
        r["arm"], r["run"] = arm, run
    rows_all += rows
    n_sham = sum(1 for r in rows if r["site"] == "SHAM")
    print(f"{arm} {run}: {len(rows)} usable events ({n_sham} sham), "
          f"mean rlag(real)={sum(r['rlag'] for r in rows if r['site'] != 'SHAM') / max(1, len(rows) - n_sham):.3f}")

fields = ["arm", "run", "event", "site", "onset", "r0", "rlag", "tgt_peak", "ach_peak",
          "peak_ratio", "ach_absmod", "ach_max_raw", "rmse"]
with open(f"{C.OUT}/scripts/_per_event_metrics.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows_all)
print("wrote", len(rows_all), "rows")
