#!/usr/bin/env python
"""ingest_block.py -- one-command per-block pipeline for rig days.

    python rig/ingest_block.py --label "P2 thwack" [--mode thwack|probe|arm]
        [--schedule day_.../schedule_mix_r1.json]
        [--data-root C:/Users/brets/Desktop/Data]

Run this right after Synapse closes a block. It:

  1. finds the NEWEST block directory (by mtime) under --data-root and
     prints its name -- record LAST, ingest FIRST, so newest == the block
     you just handed over;
  2. runs rig/plot_trial_responses.py on it with the given mode. If --mode
     is absent the mode is inferred from --label keywords: thwack/thw ->
     thwack, probe/rnd -> probe, arm/mpc/choi -> arm (no keyword = FAIL);
  3. APPENDS a row skeleton to the newest BLOCK_LEDGER_*.md in the repo
     root (| # | block | label | PENDING: <gallery path> |), just above the
     '<!-- appended live' marker, so the key-results cell gets filled in by
     hand once the gallery has been looked at. Never overwrites existing
     rows. If no ledger exists one is created as BLOCK_LEDGER_<today>.md.

A gallery failure (e.g. flat nThw) still appends the ledger row -- the
block happened and must be accounted for; the PENDING cell records the
debt. Exit is 1 only when no block/ledger can be found or written.
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import sys

RIG_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(RIG_DIR)
DEFAULT_DATA_ROOT = r"C:\Users\brets\Desktop\Data"

LEDGER_HEADER = """# Block ledger — {day} acute experiment

Backup/validation of the hand-written block annotations. One row per Synapse
block, appended live as blocks are handed over. All blocks under
`{data_root}\\` and nest one directory level.

| # | block | phase / purpose | key results |
|---|---|---|---|

<!-- appended live; do not reorder rows -->
"""


def fail(msg):
    print("FAIL: %s" % msg)
    return 1


def infer_mode(label):
    low = label.lower()
    for kws, mode in ((("thwack", "thw"), "thwack"),
                      (("probe", "rnd"), "probe"),
                      (("arm", "mpc", "choi"), "arm")):
        if any(k in low for k in kws):
            return mode
    return None


def newest_block_dir(data_root):
    """Newest directory (by mtime) under data_root."""
    dirs = [os.path.join(data_root, d) for d in os.listdir(data_root)
            if os.path.isdir(os.path.join(data_root, d))]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)


def resolve_block_dir(p):
    """Same one-level-nesting resolution as plot_trial_responses."""
    if glob.glob(os.path.join(p, "*.tsq")):
        return p
    kids = [os.path.join(p, k) for k in os.listdir(p)
            if os.path.isdir(os.path.join(p, k))
            and glob.glob(os.path.join(p, k, "*.tsq"))]
    if len(kids) == 1:
        return kids[0]
    return p


def newest_ledger():
    """Newest BLOCK_LEDGER_*.md in the repo root (by the date in the name)."""
    paths = glob.glob(os.path.join(REPO, "BLOCK_LEDGER_*.md"))
    return max(paths) if paths else None  # ISO dates sort lexicographically


def append_ledger_row(ledger, block_name, label, gallery):
    with open(ledger, encoding="utf-8") as f:
        text = f.read()
    marker = "<!-- appended live"
    pos = text.find(marker)
    if pos < 0:
        return None, ("ledger %s has no '%s' marker -- append the row by hand"
                      % (ledger, marker))
    nums = [int(m) for m in re.findall(r"^\|\s*(\d+)\s*\|", text, re.M)]
    n = (max(nums) + 1) if nums else 1
    row = "| %d | `%s` | %s | PENDING: `%s` |\n" % (n, block_name, label, gallery)
    with open(ledger, "w", encoding="utf-8") as f:
        f.write(text[:pos] + row + text[pos:])
    return n, row.rstrip("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True,
                    help='ledger label, e.g. "P2 thwack" (also used to infer mode)')
    ap.add_argument("--mode", choices=["thwack", "probe", "arm"], default=None,
                    help="gallery mode (default: inferred from --label keywords)")
    ap.add_argument("--schedule", default=None,
                    help="schedule JSON, passed through for arm mode")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--t-min", type=float, default=None,
                    help="passed through to probe mode")
    args = ap.parse_args()

    mode = args.mode or infer_mode(args.label)
    if mode is None:
        return fail("cannot infer mode from label %r -- say thwack/probe/arm "
                    "in the label or pass --mode" % args.label)
    if mode == "arm" and not args.schedule:
        return fail("arm mode needs --schedule <schedule.json>")
    if not os.path.isdir(args.data_root):
        return fail("data root not found: %s" % args.data_root)

    top = newest_block_dir(args.data_root)
    if top is None:
        return fail("no block directories under %s" % args.data_root)
    block_dir = resolve_block_dir(top)
    block_name = os.path.basename(os.path.normpath(block_dir))
    if not glob.glob(os.path.join(block_dir, "*.tsq")):
        print("WARN: newest directory %s holds no .tsq at either level -- "
              "is Synapse still writing it?" % top)
    print("newest block: %s" % block_name)
    print("       under: %s" % top)

    cmd = [sys.executable, os.path.join(RIG_DIR, "plot_trial_responses.py"),
           "--block", top, "--mode", mode]
    if args.schedule:
        cmd += ["--schedule", args.schedule]
    if args.t_min is not None:
        cmd += ["--t-min", str(args.t_min)]
    print("running: %s\n" % " ".join(cmd))
    sys.stdout.flush()  # keep parent/child output in order
    rc = subprocess.call(cmd)
    gallery = os.path.join("galleries", block_name)
    if rc != 0:
        print("\nWARN: plot_trial_responses exited %d -- gallery incomplete; "
              "ledger row appended anyway (fix and rerun the plot by hand)" % rc)

    ledger = newest_ledger()
    if ledger is None:
        day = datetime.date.today().isoformat()
        ledger = os.path.join(REPO, "BLOCK_LEDGER_%s.md" % day)
        with open(ledger, "w", encoding="utf-8") as f:
            f.write(LEDGER_HEADER.format(day=day, data_root=args.data_root))
        print("no ledger found -- created %s" % ledger)
    n, row = append_ledger_row(ledger, block_name, args.label, gallery + os.sep)
    if n is None:
        return fail(row)
    print("\nledger:  %s" % ledger)
    print("appended row %d: %s" % (n, row))
    print("next: look at %s, then replace the PENDING cell with key results"
          % os.path.join(gallery, "index.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
