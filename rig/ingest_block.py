#!/usr/bin/env python
"""ingest_block.py -- one-command per-block pipeline for rig days.

    python rig/ingest_block.py --label "P2 thwack" [--mode thwack|probe|arm|quiet]
        [--schedule day_.../schedule_mix_r1.json]
        [--data-root C:/Users/brets/Desktop/Data]
        [--ledger BLOCK_LEDGER_2026-10-08.md] [--day 2026-10-08]

Run this right after Synapse closes a block. It:

  1. finds the NEWEST block directory (by mtime) under --data-root and
     prints its name -- record LAST, ingest FIRST, so newest == the block
     you just handed over;
  2. runs rig/plot_trial_responses.py on it with the given mode. If --mode
     is absent the mode is inferred from --label keywords: thwack/thw ->
     thwack, probe/rnd -> probe, arm/mpc/choi -> arm, quiet/baseline ->
     quiet (no keyword = FAIL). Quiet mode has no trial gallery: it runs
     rig/analyze_quiet_capture.py instead and records the JSON path;
  3. APPENDS a row skeleton to TODAY'S ledger, BLOCK_LEDGER_<day>.md in the
     repo root (| # | block | label | PENDING: <gallery path> |), just above
     the '<!-- appended live' marker, so the key-results cell gets filled in
     by hand once the gallery has been looked at. Never overwrites existing
     rows. The ledger is created from a template on first use. <day> is
     today, except before 06:00 when yesterday's ledger exists (acute days
     run past midnight); --day or --ledger override. It never falls back to
     an OLDER day's ledger (the 09-10 file carries no marker, so every append
     on 10-08 would have failed with "append the row by hand").

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # rig/blockutil

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
                      (("arm", "mpc", "choi"), "arm"),
                      (("quiet", "baseline"), "quiet")):
        if any(k in low for k in kws):
            return mode
    return None


def newest_block_dir(data_root):
    """Newest directory under data_root that actually holds a block (.tsq at
    depth <= 2). An empty tank folder (e.g. Desktop\\Data\\Acute3 created before
    the first recording) can no longer be picked -- 2026-10-13, rig/blockutil."""
    from blockutil import newest_block_dir as _newest
    return _newest(data_root)


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


def ledger_day(now=None):
    """The acute day a block belongs to: today, or yesterday before 06:00
    when yesterday's ledger exists (the 09-10 acute wrapped at ~01:00)."""
    now = now or datetime.datetime.now()
    today = now.date()
    if now.hour < 6:
        yday = today - datetime.timedelta(days=1)
        if os.path.isfile(os.path.join(REPO, "BLOCK_LEDGER_%s.md" % yday.isoformat())):
            return yday.isoformat()
    return today.isoformat()


def ensure_ledger(path, day, data_root):
    """Create the ledger from LEDGER_HEADER if it does not exist yet."""
    if os.path.isfile(path):
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(LEDGER_HEADER.format(day=day, data_root=data_root))
    return True


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
    ap.add_argument("--mode", choices=["thwack", "probe", "arm", "quiet"], default=None,
                    help="gallery mode (default: inferred from --label keywords)")
    ap.add_argument("--schedule", default=None,
                    help="schedule JSON, passed through for arm mode")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--block", default=None,
                    help="explicit block (directory, or a synthetic .npz for the sim rehearsal) "
                         "instead of the newest under --data-root")
    ap.add_argument("--t-min", type=float, default=None,
                    help="passed through to probe mode")
    ap.add_argument("--ledger", default=None,
                    help="ledger file to append to (default BLOCK_LEDGER_<day>.md, created if absent)")
    ap.add_argument("--day", default=None,
                    help="acute day YYYY-MM-DD for the default ledger name (default: today, "
                         "or yesterday before 06:00 if its ledger exists)")
    args = ap.parse_args()

    mode = args.mode or infer_mode(args.label)
    if mode is None:
        return fail("cannot infer mode from label %r -- say thwack/probe/arm "
                    "in the label or pass --mode" % args.label)
    if mode == "arm" and not args.schedule:
        return fail("arm mode needs --schedule <schedule.json>")
    if not os.path.isdir(args.data_root):
        return fail("data root not found: %s" % args.data_root)

    if args.block:
        top = args.block
        if not (os.path.isdir(top) or top.lower().endswith(".npz")):
            return fail("--block not found: %s" % top)
    else:
        top = newest_block_dir(args.data_root)
        if top is None:
            return fail("no block directories under %s" % args.data_root)
    is_npz = top.lower().endswith(".npz")
    block_dir = top if is_npz else resolve_block_dir(top)
    block_name = os.path.basename(os.path.normpath(block_dir))
    if is_npz:
        block_name = block_name[:-4]
    elif not glob.glob(os.path.join(block_dir, "*.tsq")):
        print("WARN: newest directory %s holds no .tsq at either level -- "
              "is Synapse still writing it?" % top)
    print("newest block: %s" % block_name)
    print("       under: %s" % top)

    gallery = os.path.join("galleries", block_name)
    if mode == "quiet":
        # No trials to plot: the quiet capture yields the blacklist and the
        # baseline feature level (analyze_quiet_capture), which is what the
        # ledger cell and the y-liveness watch need.
        os.makedirs(os.path.join(REPO, gallery), exist_ok=True)
        pending = os.path.join(gallery, "quiet.json")
        cmd = [sys.executable, os.path.join(RIG_DIR, "analyze_quiet_capture.py"),
               "--block", top, "--json", os.path.join(REPO, pending)]
        tool = "analyze_quiet_capture"
        look_at = pending
    else:
        pending = gallery + os.sep
        cmd = [sys.executable, os.path.join(RIG_DIR, "plot_trial_responses.py"),
               "--block", top, "--mode", mode]
        if args.schedule:
            cmd += ["--schedule", args.schedule]
        if args.t_min is not None:
            cmd += ["--t-min", str(args.t_min)]
        tool = "plot_trial_responses"
        look_at = os.path.join(gallery, "index.png")
    print("running: %s\n" % " ".join(cmd))
    sys.stdout.flush()  # keep parent/child output in order
    rc = subprocess.call(cmd)
    if rc != 0:
        print("\nWARN: %s exited %d -- output incomplete; "
              "ledger row appended anyway (fix and rerun by hand)" % (tool, rc))

    day = args.day or ledger_day()
    ledger = args.ledger or os.path.join(REPO, "BLOCK_LEDGER_%s.md" % day)
    if ensure_ledger(ledger, day, args.data_root):
        print("created ledger %s" % ledger)
    n, row = append_ledger_row(ledger, block_name, args.label, pending)
    if n is None:
        return fail(row)
    print("\nledger:  %s" % ledger)
    print("appended row %d: %s" % (n, row))
    print("next: look at %s, then replace the PENDING cell with key results" % look_at)
    return 0


if __name__ == "__main__":
    sys.exit(main())
