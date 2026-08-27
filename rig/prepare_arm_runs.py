r"""Build the acute-day per-site reference tapes + the randomized run manifest.

Run AFTER the day's baseline (quiet capture) and plant fit are known. For each
touch site it subprocesses build_touch_reference.py (single source of truth for
the template->reference transform) on that site's template npz, producing
ref_<SITE>.csv with --repeats touch events; then writes run_manifest.json with
a SEEDED random site order per arm. Re-running with the same inputs reproduces
the same tapes and the same orders.

Sham policy: the SHAM tape is built from the real extracted sham template (the
honest "does the controller inject spurious modulation?" test). If the sham
template shows non-trivial modulation (thwacker vibration coupling), rerun with
--sham-scale 0 and the decision is recorded in the manifest.

Usage (surgery day):
  python rig\prepare_arm_runs.py ^
      --templates-dir <NNController>\outputs\BiomimeticInversion\touch\Acute_2026-08-27 ^
      --channel <fitted ch, 1-based> --baseline <volts from quiet capture> ^
      --seed 20260827 --out-dir day_2026-08-27
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

RIG = Path(__file__).resolve().parent
BUILDER = RIG / "build_touch_reference.py"

DEFAULT_SITES = "D1,D2,D3,D4,P1,P2,P3,LP,MP,SHAM"
DEFAULT_ARMS = "choi,mpc,nnol,nncl"


def pick_block_for_site(rows: list[dict], site: str) -> dict:
    """Choose the template row for a site; prefer the most reliable when the
    site was recorded more than once."""
    cand = [r for r in rows if r.get("site") == site]
    if not cand:
        raise SystemExit(f"FAIL: no template with site={site} in touch_targets_summary.json "
                         f"(sites present: {sorted({r.get('site') for r in rows})})")
    if len(cand) > 1:
        cand.sort(key=lambda r: (r.get("split_half_corr") is not None,
                                 r.get("split_half_corr") or -1e9,
                                 r.get("n_used", 0)))
        print(f"WARN: {len(cand)} templates for {site}; using {cand[-1]['block']} "
              f"(highest split-half/n)")
        return cand[-1]
    return cand[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates-dir", required=True,
                    help="Acute_<day> folder holding <block>.npz + touch_targets_summary.json")
    ap.add_argument("--sites", default=DEFAULT_SITES,
                    help=f"comma list, default {DEFAULT_SITES}")
    ap.add_argument("--channel", type=int, required=True,
                    help="the ONE fitted feature channel (1-based) used for every site's tape")
    ap.add_argument("--baseline", type=float, required=True,
                    help="day-of resting feature value in VOLTS (quiet capture)")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--sham-scale", type=float, default=None,
                    help="override --scale for the SHAM tape only (0 = flat-at-baseline)")
    ap.add_argument("--repeats", type=int, default=100)
    ap.add_argument("--gap-secs", type=float, default=2.0)
    ap.add_argument("--lead-secs", type=float, default=2.0)
    ap.add_argument("--signed", action="store_true",
                    help="pass through iff the loop runs --feature-signed")
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--arms", default=DEFAULT_ARMS)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    tdir = Path(args.templates_dir)
    summary_path = tdir / "touch_targets_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"FAIL: {summary_path} not found -- run extract_nthw_templates.py first")
    rows = json.loads(summary_path.read_text(encoding="utf-8"))

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- per-site tapes ----------------------------------------------------
    site_entries = {}
    table = []
    for site in sites:
        row = pick_block_for_site(rows, site)
        npz = tdir / f"{row['block']}.npz"
        if not npz.exists():
            raise SystemExit(f"FAIL: {npz} missing (summary row exists but npz does not)")
        out_csv = out_dir / f"ref_{site}.csv"
        scale = args.sham_scale if (site == "SHAM" and args.sham_scale is not None) else args.scale
        cmd = [sys.executable, str(BUILDER),
               "--npz", str(npz), "--channel", str(args.channel),
               "--baseline", str(args.baseline), "--scale", str(scale),
               "--repeats", str(args.repeats), "--gap-secs", str(args.gap_secs),
               "--lead-secs", str(args.lead_secs), "--out", str(out_csv)]
        if args.signed:
            cmd.append("--signed")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            raise SystemExit(f"FAIL: build_touch_reference failed for {site}")
        meta = json.loads((out_dir / f"ref_{site}_meta.json").read_text(encoding="utf-8"))
        site_entries[site] = {
            "block": row["block"], "npz": str(npz), "ref_csv": str(out_csv),
            "ticks": meta["total_ticks"], "scale": scale,
            "event_peak_delta_volts": meta["event_peak_delta_volts"],
            "split_half_corr": row.get("split_half_corr"),
            "qc_pass": row.get("qc_pass"),
        }
        table.append((site, row["block"], meta["total_ticks"],
                      max(meta["event_peak_delta_volts"]), row.get("split_half_corr")))

    ticks = {e["ticks"] for e in site_entries.values()}
    print("\nsite  block                       ticks   peak dV      shc")
    for site, block, t, pk, shc in table:
        shc_s = f"{shc:.3f}" if isinstance(shc, (int, float)) else "  -- "
        flag = "  <-- ~zero modulation expected" if site == "SHAM" else ""
        print(f"{site:5s} {block:26s} {t:6d}   {pk:.3e}  {shc_s}{flag}")
    if len(ticks) != 1:
        print(f"WARN: tapes differ in length: {sorted(ticks)} (differing template windows?)")

    # ---- sham scoring threshold -------------------------------------------
    # tracking_metrics' default transient threshold is 0.25*max|diff(r)| OF THE
    # SCORED TAPE; on the sham tape (noise template) that would flag bogus
    # "transients". Score the SHAM run with an explicit --transient-thresh
    # derived from the REAL sites' tapes instead.
    real_thr = []
    for site, e in site_entries.items():
        if site == "SHAM":
            continue
        ref = np.loadtxt(e["ref_csv"], delimiter=",", skiprows=1)[:, 1:]
        real_thr.append(0.25 * float(np.max(np.abs(np.diff(ref, axis=0)))))
    sham_thresh = float(np.median(real_thr)) if real_thr else None
    if sham_thresh is not None:
        print(f"\nSHAM scoring: add --transient-thresh {sham_thresh:.6g} "
              f"(median of real sites' default thresholds)")

    # ---- seeded per-arm site orders ---------------------------------------
    manifest = {
        "seed": args.seed, "baseline_volts": args.baseline, "channel": args.channel,
        "scale": args.scale, "sham_scale": args.sham_scale,
        "repeats": args.repeats, "gap_secs": args.gap_secs, "lead_secs": args.lead_secs,
        "signed": bool(args.signed), "templates_dir": str(tdir),
        "sham_transient_thresh": sham_thresh,
        "sites": sites, "arms": {},
    }
    for ai, arm in enumerate(arms):
        rng = np.random.default_rng(args.seed + ai)
        order = [sites[k] for k in rng.permutation(len(sites))]
        manifest["arms"][arm] = [
            {"order": i + 1, "site": s, "ref_csv": site_entries[s]["ref_csv"],
             "run_label": f"{arm}_{s}", "ticks": site_entries[s]["ticks"]}
            for i, s in enumerate(order)
        ]
    manifest["site_templates"] = site_entries
    mpath = out_dir / "run_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nrun_manifest.json -> {mpath}")
    print("\nRUN ORDER (execute top to bottom within each arm):")
    for arm, runs in manifest["arms"].items():
        print(f"  {arm}: " + " -> ".join(r["site"] for r in runs))
    one = next(iter(site_entries.values()))
    print(f"\neach run: {one['ticks']} ticks (~{one['ticks'] * 0.0098304 / 60:.1f} min frame-locked), "
          f"{args.repeats} touch events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
