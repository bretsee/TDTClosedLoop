r"""Refuse to deploy a forward model as a controller.

    python rig\check_nnw_mode.py model.nnw    ->  exit 0 only if safe to deploy

Only an 'inverse' .nnw (features -> stim) is a controller. A 'forward' model
(stim -> features) deployed in cpp_controller --mode nn would emit predicted
FEATURES as stim commands -- volts-scale garbage on the amplitude wire. The
.nnw carries the mode as a '# mode: <m>' comment (export_nnw.py, 2026-08-20);
files exported before then have no marker and get a warning, not a pass.
Run this before every 'cpp_controller --mode nn' deployment (the manual and
runbooks reference it). A C++-side refusal is queued for the next
cpp_controller rebuild.
"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print(__doc__)
    sys.exit(2)

path = Path(sys.argv[1])
if not path.is_file():
    print(f"FAIL: {path} not found")
    sys.exit(2)

head = path.read_text().splitlines()[:20]
mode = None
for line in head:
    mm = re.match(r"\s*#\s*mode:\s*(\w+)", line)
    if mm:
        mode = mm.group(1).lower()
        break

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
