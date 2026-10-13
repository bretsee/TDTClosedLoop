#!/usr/bin/env python
"""rehearse_day.py -- execute a full rig day in sim from the runcards (dress rehearsal).

    python rig/rehearse_day.py --day rehearsal1013 --resp 1,3,4,6 --ctrl 34,40 \
        [--block day_rehearsal1013/synthetic_block_burst1.npz] [--phases gate,burst,...]

For every phase in day order it builds the runcard with rig_runcard.build_card(--sim),
writes it to day_<day>/runcard_<phase>_sim.txt, and then RUNS it:
  * role A  (cpp_controller)  -> background process, stdout to day_<day>/server_<run>.log,
                                 waits for 'ready'
  * role B  (2_loop -Sim)     -> powershell -File rig/2_loop.ps1 ... -NoWatch (blocks until Summary:)
                                 ~30 s in, check_y_liveness.py runs once on the streamed capture
  * role check / matlab       -> run, exit code + last lines recorded
  * role skip                 -> hardware-only line, recorded as skipped
ingest_block lines get --data-root <scratch> --ledger <scratch>/BLOCK_LEDGER_<day>.md so the
real ledger and galleries are untouched; lines that still contain <blk> are skipped unless
--block is given.

Output: day_<day>/rehearsal_<day>.json (per phase: wall-clock s, ticks, AUDIT line, every
check's exit code) and a one-line verdict per phase on stdout. Nothing reaches the RZ2.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rig_runcard as RC  # noqa: E402

DEFAULT_PHASES = ["phase0", "gate", "quiet", "burst", "gap", "dutyid", "fit", "refs",
                  "arm:mpc", "arm:choi", "rsweep", "drift"]


def tokens(cmd):
    """Split a runcard line into argv (Windows quoting: keep backslashes, strip quotes)."""
    cmd = cmd.split("   #")[0].strip()
    toks = shlex.split(cmd, posix=False)
    out = []
    for t in toks:
        if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        out.append(t)
    return out


def argv_for(cmd):
    """Map a runcard line to a subprocess argv."""
    toks = tokens(cmd)
    if toks[:2] == ["&", "$py"]:
        return [RC.PY] + toks[2:]
    if toks[0].lower().endswith(".ps1"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + toks
    if toks[0] == "matlab":
        return ["matlab", "-wait"] + toks[1:]
    return toks


def tail(text, n=6):
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return lines[-n:]


def run_check(cmd, cwd, timeout=1800, extra=None):
    argv = argv_for(cmd) + (extra or [])
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        rc, out = -9, "TIMEOUT after %d s" % timeout
    except FileNotFoundError as exc:
        rc, out = -2, "NOT FOUND: %s" % exc
    return dict(cmd=cmd, rc=rc, secs=round(time.time() - t0, 1), tail=tail(out), out=out)


def wait_for(path, needle, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                if needle in f.read():
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def run_pair(a_cmd, b_cmd, day_dir, cwd, liveness_py=None):
    """Terminal A in the background, terminal B blocking, liveness check mid-run."""
    m = re.search(r"-Run (\S+)", b_cmd)
    run = m.group(1) if m else "run"
    slog = os.path.join(day_dir, "server_%s.log" % run)
    a_argv = argv_for(a_cmd)
    cap = None
    if "--capture" in a_argv:
        cap = a_argv[a_argv.index("--capture") + 1]
    t0 = time.time()
    with open(slog, "w", encoding="utf-8") as sf:
        A = subprocess.Popen(a_argv, cwd=cwd, stdout=sf, stderr=subprocess.STDOUT)
        ready = wait_for(slog, "ready", 20)
        if not ready and A.poll() is not None:
            return dict(run=run, ok=False, reason="controller exited before ready (rc=%s)" % A.returncode,
                        server_log=slog, secs=round(time.time() - t0, 1),
                        server_tail=tail(open(slog, encoding="utf-8", errors="replace").read()))
        b_argv = argv_for(b_cmd) + ["-NoWatch"]
        B = subprocess.Popen(b_argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        # Drain B's stdout continuously: a full 4 KB pipe would stall PowerShell's
        # Tee-Object and, behind it, the loop exe itself (10-13: stalls at the
        # same packet count in every driver run).
        import threading
        b_lines = []

        def _drain():
            for ln in B.stdout:
                b_lines.append(ln)
        th = threading.Thread(target=_drain, daemon=True)
        th.start()
        live = None
        if cap and liveness_py:
            time.sleep(30)
            if B.poll() is None:
                live = run_check("& $py rig\\check_y_liveness.py --capture %s" % cap, cwd, timeout=60)
        B.wait()
        th.join(timeout=10)
        b_out = "".join(b_lines)
        try:
            A.wait(timeout=30)
        except subprocess.TimeoutExpired:
            A.kill()
            a_note = "controller still running 30 s after the loop ended -> killed"
        else:
            a_note = "controller exit rc=%d" % A.returncode
    secs = round(time.time() - t0, 1)
    summ = [ln for ln in b_out.splitlines() if ln.startswith(("Summary:", "Localhost summary:", "Exit reason:"))]
    stext = open(slog, encoding="utf-8", errors="replace").read()
    ok = bool(summ) and "FATAL" not in stext and "droppedControlTicks=0" in " ".join(summ)
    return dict(run=run, ok=ok, secs=secs, loop_summary=summ, controller=a_note, server_log=slog,
                fatal=[ln for ln in stext.splitlines() if "FATAL" in ln],
                liveness=(live["tail"] if live else None), b_rc=B.returncode)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", required=True, help="label; artifacts go to day_<label>/")
    ap.add_argument("--resp", default="1,3,4,6")
    ap.add_argument("--ctrl", default="34,40")
    ap.add_argument("--model", default=None, help="default day_<day>/plant_duty.lti (written by the fit phase)")
    ap.add_argument("--fallback-model", default="plant_opfit12_d2.lti",
                    help="used for refs/arm/rsweep if the fit phase did not produce --model")
    ap.add_argument("--fallback-resp", default="4,6")
    ap.add_argument("--fallback-ctrl", default="64")
    ap.add_argument("--fallback-baseline", type=float, default=3.3e-5,
                    help="<V> for phases run on the fallback model (volt-scale, 09-10 quiet baseline 3.3e-5 V); "
                         "the sim-derived baseline is int16-scale and makes the volt-scale model saturate")
    ap.add_argument("--templates-day", default="2026-09-10")
    ap.add_argument("--block", default=None, help="synthetic .npz block for the block-dependent checks")
    ap.add_argument("--baseline", type=float, default=None,
                    help="value for the <V> placeholder (quiet-capture MAV baseline); default in sim: mean of the "
                         "first --ctrl channel over the first 200 ticks of capture_rig_rundutyid.csv")
    ap.add_argument("--gate-block", default=None,
                    help="synthetic .npz built from design_rungate.csv, used for the gate phase instead of --block")
    ap.add_argument("--phases", default=",".join(DEFAULT_PHASES))
    ap.add_argument("--use-fit-model", action="store_true",
                    help="run refs/arm/rsweep on the model the fit phase produced. Default: the fallback model, "
                         "because a sim capture (sine input, no response to u) fits to an unobservable plant "
                         "(10-13: observer pole 1.103 -> AUDIT FAIL on the arms). The fit phase still runs.")
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--skip-matlab", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    day = args.day
    day_dir = os.path.join(REPO, "day_%s" % day)
    os.makedirs(day_dir, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="rehearsal_")
    fake_block = os.path.join(scratch, "BSCL_fake-%s-000000" % day.replace("-", ""))
    os.makedirs(fake_block, exist_ok=True)
    ledger = os.path.join(scratch, "BLOCK_LEDGER_%s.md" % day)
    model = args.model or ("day_%s\\plant_duty.lti" % day)
    report = dict(day=day, started=time.strftime("%Y-%m-%d %H:%M:%S"), scratch=scratch, phases=[])
    resp, ctrl = args.resp, args.ctrl
    baseline = args.baseline
    if baseline is None:
        capd = os.path.join(REPO, "capture_rig_rundutyid.csv")
        if os.path.isfile(capd):
            try:
                import pandas as pd
                col = "y%d" % int(ctrl.split(",")[0])
                baseline = float(pd.read_csv(capd, nrows=200)[col].mean())
                print("sim baseline <V> = %.6g (mean %s of the first 200 dutyid ticks)" % (baseline, col), flush=True)
            except Exception as exc:  # noqa: BLE001
                print("WARN: could not derive a sim baseline from %s: %s" % (capd, exc), flush=True)

    for spec in [s.strip() for s in args.phases.split(",") if s.strip()]:
        phase, _, arm = spec.partition(":")
        use_model, p_resp, p_ctrl = model, resp, ctrl
        if phase in ("refs", "arm", "rsweep") and (
                not args.use_fit_model or not os.path.isfile(os.path.join(REPO, model))):
            use_model, p_resp, p_ctrl = args.fallback_model, args.fallback_resp, args.fallback_ctrl
        p_baseline = args.fallback_baseline if use_model == args.fallback_model else baseline
        argv = ["--phase", phase, "--day", day, "--sim", "--resp", p_resp, "--ctrl", p_ctrl,
                "--model", use_model, "--templates-day", args.templates_day, "--depth", str(args.depth)]
        if arm:
            argv += ["--arm", arm]
        blk = args.gate_block if (phase == "gate" and args.gate_block) else args.block
        if blk:
            argv += ["--block", blk]
        cargs = RC.add_args(argparse.ArgumentParser()).parse_args(argv)
        card = RC.build_card(cargs)
        text = RC.render(card)
        with open(os.path.join(day_dir, "runcard_%s%s_sim.txt" % (phase, ("_" + arm) if arm else "")), "w", encoding="utf-8") as f:
            f.write(text)
        rec = dict(phase=spec, model=use_model, runs=[], checks=[], skipped=[], t0=time.time())
        print("\n=== %s ===" % spec, flush=True)
        pending_a = None
        for role, line in card:
            if role == "comment":
                if line.startswith("# FAIL"):
                    rec["checks"].append(dict(cmd=line, rc=1, tail=[line]))
                continue
            if role == "skip":
                rec["skipped"].append(line.strip())
                continue
            if role == "A":
                pending_a = line
                continue
            if role == "B":
                if pending_a is None:
                    rec["checks"].append(dict(cmd=line, rc=-1, tail=["B line without an A line"]))
                    continue
                print("  A: %s\n  B: %s" % (pending_a, line), flush=True)
                r = run_pair(pending_a, line, day_dir, REPO, liveness_py=RC.PY)
                rec["runs"].append(dict(A=pending_a, B=line, **r))
                print("  -> %s %.0f s  %s" % ("OK " if r["ok"] else "BAD", r["secs"], " | ".join(r.get("loop_summary", [])[:1]) or r.get("reason", "")), flush=True)
                pending_a = None
                continue
            # check / matlab lines
            if role == "matlab" and args.skip_matlab:
                rec["skipped"].append(line)
                continue
            extra = []
            if "ingest_block.py" in line:
                extra = ["--data-root", scratch, "--ledger", ledger]
                if blk:
                    extra += ["--block", blk]
            if "check_impulse_delivery.py" in line and blk:
                # the synthetic block was not produced by this sim run: compare it
                # with its own sidecar capture (the sim capture belongs to no block)
                side = blk[:-4] + "_capture.csv"
                if os.path.isfile(os.path.join(REPO, side)):
                    line = re.sub(r"--capture \S+", "--capture " + side.replace("\\", "\\\\"), line)
            if "<V>" in line and p_baseline is not None:
                line = line.replace("<V>", "%.6g" % p_baseline)
            if "<blk>" in line or "<best ch>" in line or "<V>" in line:
                rec["skipped"].append(line.strip() + "   (placeholder)")
                continue
            print("  $ %s" % line.split("   #")[0].strip(), flush=True)
            r = run_check(line, REPO, extra=extra)
            r.pop("out", None)
            if "run_audit.py" in line:
                aud = [ln for ln in r["tail"] if ln.startswith("AUDIT")]
                r["audit"] = aud[-1] if aud else None
                rec["audit"] = r["audit"]
            rec["checks"].append(r)
            print("    rc=%s %.0f s  %s" % (r["rc"], r["secs"], (r.get("audit") or (r["tail"][-1] if r["tail"] else ""))[:150]), flush=True)
        rec["secs"] = round(time.time() - rec.pop("t0"), 1)
        # run_audit exits 1 on WARN; in sim a WARN is expected (u pinned / undersampled first
        # window / no server log) and is not a rehearsal failure. FAIL (rc 2) still is.
        def _check_ok(c):
            return c["rc"] == 0 or (c.get("audit") or "").startswith("AUDIT") and " WARN " in (c.get("audit") or "")
        rec["ok"] = all(x["ok"] for x in rec["runs"]) and all(_check_ok(c) for c in rec["checks"])
        report["phases"].append(rec)
        out = args.json or os.path.join(day_dir, "rehearsal_%s.json" % day)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)

    print("\n=== REHEARSAL %s ===" % day)
    for rec in report["phases"]:
        bad = [c for c in rec["checks"] if c["rc"] != 0]
        print("  %-10s %-4s %6.0f s  runs %d  checks %d (bad %d)  %s"
              % (rec["phase"], "OK" if rec["ok"] else "FAIL", rec["secs"], len(rec["runs"]), len(rec["checks"]), len(bad),
                 rec.get("audit") or ""))
        for c in bad:
            print("      rc=%s  %s" % (c["rc"], c["cmd"].split("   #")[0].strip()[:110]))
            for ln in c["tail"][-2:]:
                print("         %s" % ln[:140])
    print("json: %s" % (args.json or os.path.join(day_dir, "rehearsal_%s.json" % day)))
    return 0 if all(r["ok"] for r in report["phases"]) else 1


if __name__ == "__main__":
    sys.exit(main())
