r"""Refuse to deploy a forward model as a controller.

    python rig\check_nnw_mode.py model.nnw                    ->  exit 0 only if safe
    python rig\check_nnw_mode.py model.nnw --expect-input 32  ->  also check width

Only an 'inverse' .nnw (features -> stim) is a controller. A 'forward' model
(stim -> features) deployed in cpp_controller --mode nn would emit predicted
FEATURES as stim commands -- volts-scale garbage on the amplitude wire. The
.nnw carries the mode as a '# mode: <m>' comment (export_nnw.py, 2026-08-20);
files exported before then have no marker and get a warning, not a pass.

--expect-input N (2026-08-29): additionally require the network's input width
to equal N (the loop's -InputChannels). cpp_controller's NnController silently
zero-pads or truncates the live feature vector to the .nnw's input dim
(nn_controller.hpp), so a 16-input net on a 32-ch loop would silently ignore
channels 17-32 -- pass --expect-input 32 on the 32-ch circuit to refuse that.

Run this before every 'cpp_controller --mode nn' deployment (the manual and
runbooks reference it). A C++-side refusal is queued for the next
cpp_controller rebuild.
"""
import argparse
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser(description="Gate a .nnw before controller deployment")
ap.add_argument("nnw", help="path to the .nnw export")
ap.add_argument("--expect-input", type=int, default=0,
                help="require the network input width to equal this (the loop's "
                     "-InputChannels); 0 = report the width but do not enforce")
args = ap.parse_args()

path = Path(args.nnw)
if not path.is_file():
    print(f"FAIL: {path} not found")
    sys.exit(2)

head = path.read_text().splitlines()[:40]
mode = None
in_width = None
for line in head:
    mm = re.match(r"\s*#\s*mode:\s*(\w+)", line)
    if mm and mode is None:
        mode = mm.group(1).lower()
    mw = re.match(r"\s*input\s+(\d+)\s*$", line)
    if mw and in_width is None:
        in_width = int(mw.group(1))

if in_width is not None:
    print(f"input width: {in_width}")
else:
    print("WARNING: no 'input N' line found in the header -- cannot report width.")

if args.expect_input > 0:
    if in_width is None:
        print(f"REFUSE: --expect-input {args.expect_input} given but the file "
              f"declares no input width.")
        sys.exit(1)
    if in_width != args.expect_input:
        print(f"REFUSE: {path.name} takes {in_width} inputs but the loop will send "
              f"{args.expect_input} features. cpp_controller would silently "
              f"pad/truncate (nn_controller.hpp) -- retrain on a "
              f"{args.expect_input}-channel capture.")
        sys.exit(1)

if mode == "inverse":
    print(f"OK: {path.name} is an inverse model -- safe to deploy as a controller.")
    sys.exit(0)
if mode == "forward":
    print(f"REFUSE: {path.name} is a FORWARD model (stim -> features). Deploying it "
          f"as a controller would send predicted features as stim commands. "
          f"Train with --mode inverse for a controller.")
    sys.exit(1)
print(f"WARNING: {path.name} carries no mode marker (exported before 2026-08-20). "
      f"Verify by provenance that it was trained with --mode inverse, or re-export.")
sys.exit(1)
