#!/usr/bin/env python
"""run_audit.py -- one PASS / WARN / FAIL line per closed-loop run, from the
loop log, the controller's latency log (or terminal log) and the capture.

    python rig/run_audit.py --run mpc_r1 [--loop-log loop_runmpc_r1.log]
        [--capture day_2026-10-08/capture_mpc_r1.csv]
        [--lat day_2026-10-08/server_lat_capture_mpc_r1.csv | --server-log server.log]
        [--expect-ticks 22200 | --design design_X.csv | --ref ref_mix_r1.csv]
        [--baseline 2.1e-4] [--sim] [--json out.json]

Replaces the by-eye banner checks in the runbook (policy=fresh by ~tick 100,
offsets=applied, observer pole < 1, out varies) and the post-hoc y-liveness
scan that caught the 09-10 PZ2-off incident three runs late.

Checks (FAIL / WARN):
  loop log   first policy=fresh controlTick <= 100            FAIL
             droppedControlTicks == 0                         FAIL
             controlTicks == expected                         WARN
             mid-run "Skipping N to position M" (backlog)     WARN
             timeouts > 50 / zeroTicks > 25 (after startup)   WARN
             staleDropped > 1% of ticks                       FAIL
             Exit reason: reached max control ticks           WARN otherwise
  latency    '#' banner: observer ACTIVE and pole < 1         FAIL
  log /      offsets=applied (model carries offsets)          FAIL
  server log FEATURE-MAP-FAULT                                FAIL
             qpConv < 95%                                     WARN
             dist_observer / r_schedule / effort_ratio        reported
  capture    y-liveness (check_y_liveness.verdict)            DEAD FAIL / SUSPECT WARN
             seq monotonic, no gaps                           FAIL
             active command channels move (nonzero fraction,  FAIL (WARN with --sim:
             std > 0)                                         sim features pin u)

Exit code: 0 PASS, 1 WARN, 2 FAIL. The one-line summary is the ledger cell.
"""

import argparse
import csv
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_y_liveness import read_tail, verdict as y_verdict   # noqa: E402


# ----------------------------------------------------------------------------
def read_text_any(path):
    """Decode a log by BOM: Tee-Object writes UTF-16LE, the C++ server UTF-8."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    # Heuristic: many NULs = UTF-16 without BOM
    if raw[:4000].count(b"\x00") > len(raw[:4000]) // 4:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("utf-8", errors="replace")


def kv_ints(line):
    return {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)\b", line)}


class Audit:
    def __init__(self):
        self.fails, self.warns, self.facts = [], [], {}

    def fail(self, msg): self.fails.append(msg)
    def warn(self, msg): self.warns.append(msg)

    @property
    def level(self):
        return "FAIL" if self.fails else ("WARN" if self.warns else "PASS")


# ----------------------------------------------------------------------------
def audit_loop_log(path, a, expect_ticks):
    txt = read_text_any(path)
    lines = txt.splitlines()
    first_fresh = None
    skips = 0
    for ln in lines:
        if first_fresh is None and "policy=fresh" in ln:
            m = re.search(r"controlTick=(\d+)", ln)
            first_fresh = int(m.group(1)) if m else -1
        if ln.startswith("Skipping ") and " to position " in ln:
            skips += 1
    a.facts["fresh_at"] = first_fresh
    if first_fresh is None:
        a.fail("loop never reached policy=fresh (controller replies never used)")
    elif first_fresh > 100:
        a.fail("policy=fresh only at controlTick %d (> 100)" % first_fresh)

    summ = next((ln for ln in lines if ln.startswith("Summary:")), None)
    if summ is None:
        a.fail("no 'Summary:' line -- the loop did not finish cleanly")
    else:
        kv = kv_ints(summ)
        a.facts["controlTicks"] = kv.get("controlTicks")
        a.facts["dropped"] = kv.get("droppedControlTicks")
        if kv.get("droppedControlTicks", 0) != 0:
            a.fail("droppedControlTicks=%d" % kv["droppedControlTicks"])
        if expect_ticks and kv.get("controlTicks") != expect_ticks:
            a.warn("controlTicks %s != expected %d" % (kv.get("controlTicks"), expect_ticks))
        m = re.search(r"undersampledWindows=(\d+)", summ)
        if m and int(m.group(1)) > 0:
            a.warn("undersampledWindows=%s" % m.group(1))

    loc = next((ln for ln in lines if ln.startswith("Localhost summary:")), None)
    if loc is not None:
        kv = kv_ints(loc)
        a.facts["timeouts"] = kv.get("timeouts")
        a.facts["stale"] = kv.get("staleDropped")
        a.facts["zeroTicks"] = kv.get("zeroTicks")
        n = max(1, kv.get("submitted", 1))
        if kv.get("timeouts", 0) > 50:
            a.warn("localhost timeouts=%d" % kv["timeouts"])
        if kv.get("staleDropped", 0) > 0.01 * n:
            a.fail("staleDropped=%d (> 1%% of %d)" % (kv["staleDropped"], n))
        if kv.get("zeroTicks", 0) > 25:
            a.warn("zeroTicks=%d (> 25: controller output was zero beyond startup)" % kv["zeroTicks"])
    else:
        a.warn("no 'Localhost summary:' line")

    ex = next((ln for ln in lines if ln.startswith("Exit reason:")), None)
    if ex is None or "reached max control ticks" not in ex:
        a.warn("exit reason: %s" % (ex.replace("Exit reason: ", "") if ex else "none recorded"))
    if skips:
        a.warn("%d 'Skipping N to position M' line(s): acquisition backlog -- recording started before the loop?" % skips)
    for ln in lines:
        if "FATAL" in ln:
            a.fail("loop log FATAL: %s" % ln.strip()[:120])
            break
    a.facts["backlog"] = next((kv_ints(ln).get("backlogFramesDropped")
                               for ln in lines if "backlogFramesDropped=" in ln), None)


def audit_latency_log(path, a):
    txt = read_text_any(path)
    lines = txt.splitlines()
    if not lines:
        a.warn("latency log empty")
        return
    banner = lines[0] if lines[0].startswith("#") else None
    if banner:
        kv = dict(re.findall(r"(\w+)=(\S+)", banner))
        a.facts["observer"] = kv.get("observer")
        a.facts["pole"] = float(kv["pole"]) if "pole" in kv else None
        a.facts["offsets"] = kv.get("offsets")
        a.facts["dist"] = kv.get("dist_observer")
        a.facts["r_sched"] = kv.get("r_schedule")
        a.facts["effort_ratio"] = kv.get("effort_ratio")
        if kv.get("mode") == "mpc":
            if kv.get("observer") == "OFF":
                a.fail("observer OFF (requested but not accepted): controller ran open loop")
            elif kv.get("observer") == "DELIBERATE_OFF":
                a.warn("observer deliberately off (--no-observer feedforward arm)")
            if a.facts["pole"] is not None and not (a.facts["pole"] < 1.0):
                a.fail("observer pole %.3f >= 1" % a.facts["pole"])
            if kv.get("offsets") != "applied":
                a.fail("model offsets NOT applied (centered controller on a raw plant)")
    else:
        a.warn("latency log has no '#' banner (pre-10-09 server?)")
    body = [ln for ln in lines if ln and not ln.startswith("#")]
    if len(body) > 1:
        hdr = body[0].split(",")
        if "qpConv" in hdr:
            ci = hdr.index("qpConv"); ai = hdr.index("activeFrac")
            conv, act = [], []
            for ln in body[1:]:
                c = ln.split(",")
                if len(c) > max(ci, ai):
                    try:
                        conv.append(float(c[ci])); act.append(float(c[ai]))
                    except ValueError:
                        pass
            if conv:
                a.facts["qpConv"] = float(np.mean(conv))
                a.facts["activeFrac"] = float(np.mean(act))
                if a.facts["qpConv"] < 0.95:
                    a.warn("QP converged on only %.0f%% of ticks" % (100 * a.facts["qpConv"]))
        a.facts["lat_rows"] = len(body) - 1


def audit_server_log(path, a):
    """Terminal log of cpp_controller (no banner): read the Reply# status."""
    txt = read_text_any(path)
    for ln in txt.splitlines():
        if "Observer:" in ln and "observer" not in a.facts:
            a.facts["observer"] = "ACTIVE" if "ACTIVE" in ln else ("DELIBERATE_OFF" if "DELIBERATE" in ln else "OFF")
            m = re.search(r"\|pole\| = ([0-9.eE+-]+)", ln)
            a.facts["pole"] = float(m.group(1)) if m else None
        if ln.startswith("Reply #"):
            if "offsets=applied" in ln: a.facts["offsets"] = "applied"
            elif "offsets=none" in ln: a.facts["offsets"] = "none"
            if "FEATURE-MAP-FAULT" in ln:
                a.fail("FEATURE-MAP-FAULT in server log (feature map past the frame width; hold-last)")
                break
            m = re.search(r"qpFail=(\d+)", ln)
            if m: a.facts["qpFail"] = int(m.group(1))
    if a.facts.get("observer") == "OFF":
        a.fail("observer INACTIVE: controller ran open loop")
    if a.facts.get("pole") is not None and not (a.facts["pole"] < 1.0):
        a.fail("observer pole %.3f >= 1" % a.facts["pole"])
    if a.facts.get("offsets") == "none":
        a.warn("server reports offsets=none (fine for an offset-free model; FAIL if the plant was fitted with offsets)")
    if a.facts.get("qpFail", 0) > 0:
        a.warn("qpFail=%d" % a.facts["qpFail"])


def audit_capture(path, a, baseline, sim, active_u=None):
    Y, n_rows = read_tail(path, max_rows=100000)
    if Y is None or Y.size == 0:
        a.fail("capture has no rows")
        return
    a.facts["cap_rows"] = n_rows
    v, zf, med_abs, banks = y_verdict(Y, baseline)
    a.facts["y"] = v
    if v == "DEAD":
        a.fail("y-liveness DEAD: features are zero -- amp/PZ2 off or stream dead (run is VOID)")
    elif v == "SUSPECT":
        a.warn("y-liveness SUSPECT: level off-scale vs baseline or a bank is dead")
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        hdr = next(r)
        ui = [i for i, h in enumerate(hdr) if h.startswith("u")]
        si = hdr.index("seq") if "seq" in hdr else None
        U, seq = [], []
        for row in r:
            if len(row) != len(hdr):
                continue
            U.append([float(row[i]) for i in ui])
            if si is not None:
                seq.append(int(float(row[si])))
    U = np.array(U)
    if si is not None and len(seq) > 1:
        d = np.diff(seq)
        if (d <= 0).any():
            a.fail("capture seq not monotonic")
        gaps = int((d > 1).sum())
        a.facts["seq_gaps"] = gaps
        if gaps:
            a.warn("capture seq has %d gap(s) (requests dropped between loop and server)" % gaps)
    if U.size:
        moved = [j for j in range(U.shape[1]) if U[:, j].std() > 1e-9]
        if active_u:
            moved_named = ["u%d" % (j + 1) for j in moved]
            missing = [c for c in active_u if c not in moved_named]
            if missing:
                (a.warn if sim else a.fail)("commanded channel(s) %s never moved" % " ".join(missing))
        if not moved:
            (a.warn if sim else a.fail)("NO command channel moved -- the controller output was constant")
            a.facts["u_nz"] = 0.0; a.facts["u_std"] = 0.0
        else:
            act = U[:, moved]
            a.facts["u_nz"] = float((np.abs(act) > 1e-9).mean())
            a.facts["u_std"] = float(act.std(axis=0).mean())
            a.facts["u_active"] = ["u%d" % (j + 1) for j in moved]


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=None, help="run label (defaults file names)")
    ap.add_argument("--loop-log", default=None)
    ap.add_argument("--capture", default=None)
    ap.add_argument("--lat", default=None, help="server latency CSV (with '#' banner)")
    ap.add_argument("--server-log", default=None, help="cpp_controller terminal log (fallback)")
    ap.add_argument("--expect-ticks", type=int, default=None)
    ap.add_argument("--design", default=None, help="design CSV: expected ticks from its _meta.json / rows")
    ap.add_argument("--ref", default=None, help="reference CSV: expected ticks = its row count")
    ap.add_argument("--baseline", type=float, default=None, help="quiet-capture MAV baseline (V)")
    ap.add_argument("--active-u", default=None, help="comma list of commanded channels, e.g. u4,u6")
    ap.add_argument("--sim", action="store_true", help="sim-dress run: pinned u is a WARN not a FAIL")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    run = args.run or "run"
    loop_log = args.loop_log or ("loop_run%s.log" % run)
    capture = args.capture or ("capture_rig_run%s.csv" % run)
    lat = args.lat
    if lat is None and args.capture:
        d, b = os.path.split(args.capture)
        cand = os.path.join(d, "server_lat_" + b)
        if os.path.isfile(cand):
            lat = cand
    if lat is None and os.path.isfile("server_lat_run%s.csv" % run):
        lat = "server_lat_run%s.csv" % run

    expect = args.expect_ticks
    if expect is None and args.design:
        meta = os.path.splitext(args.design)[0] + "_meta.json"
        if os.path.isfile(meta):
            with open(meta) as f:
                expect = int(json.load(f).get("nTicks", 0)) or None
        if expect is None:
            with open(args.design) as f:
                expect = sum(1 for _ in f) - 1
    if expect is None and args.ref:
        with open(args.ref) as f:
            expect = sum(1 for _ in f) - 1

    a = Audit()
    if os.path.isfile(loop_log):
        audit_loop_log(loop_log, a, expect)
    else:
        a.warn("loop log %s not found" % loop_log)
    if lat and os.path.isfile(lat):
        audit_latency_log(lat, a)
    elif args.server_log and os.path.isfile(args.server_log):
        audit_server_log(args.server_log, a)
    else:
        a.warn("no server latency log / server log: observer, offsets, QP state unverified")
    if os.path.isfile(capture):
        active = args.active_u.split(",") if args.active_u else None
        audit_capture(capture, a, args.baseline, args.sim, active)
    else:
        a.fail("capture %s not found" % capture)

    f = a.facts
    def fmt(k, spec="%s"):
        return (spec % f[k]) if f.get(k) is not None else "n/a"
    summary = ("AUDIT %s: %s | fresh@%s ticks=%s/%s dropped=%s timeouts=%s stale=%s zero=%s "
               "obs=%s(%s) offsets=%s y=%s u_nz=%s u_std=%s qpConv=%s"
               % (run, a.level, fmt("fresh_at"), fmt("controlTicks"), expect or "?",
                  fmt("dropped"), fmt("timeouts"), fmt("stale"), fmt("zeroTicks"),
                  fmt("observer"), fmt("pole", "%.3f"), fmt("offsets"), fmt("y"),
                  fmt("u_nz", "%.2f"), fmt("u_std", "%.3g"),
                  ("%.0f%%" % (100 * f["qpConv"])) if f.get("qpConv") is not None else "n/a"))
    print(summary)
    for m in a.fails:
        print("  FAIL: " + m)
    for m in a.warns:
        print("  WARN: " + m)
    extras = {k: f[k] for k in ("dist", "r_sched", "effort_ratio", "activeFrac", "backlog", "u_active")
              if f.get(k) is not None}
    if extras:
        print("  info: " + " ".join("%s=%s" % kv for kv in extras.items()))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"run": run, "level": a.level, "summary": summary, "fails": a.fails,
                       "warns": a.warns, "facts": f}, fh, indent=1)
    return {"PASS": 0, "WARN": 1, "FAIL": 2}[a.level]


if __name__ == "__main__":
    sys.exit(main())
