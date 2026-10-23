"""drive_live_run.py -- run one LIVE terminal-A / terminal-B pair from a runcard, with the
'go' prompt answered from a signal file instead of a keyboard (engineer lane run remotely).

    python rig/drive_live_run.py --card day_2026-10-22/runcard_gate_d1_short.txt --day 2026-10-22

  1. starts terminal A (cpp_controller) in the background -> day_<day>/server_<run>.log, waits for 'ready'
  2. starts terminal B (2_loop.ps1 ... -NoWatch) with stdin piped -> day_<day>/loopB_<run>.log
  3. when B prints its "Type 'go'" prompt, writes day_<day>/driver_<run>.status = WAITING_FOR_GO
     and polls for day_<day>/GO_<run>  (create it to answer 'go'; write 'abort' into it to abort)
  4. answers the prompt, runs check_y_liveness.py once ~30 s in, waits for Summary:, records everything
     in day_<day>/driver_<run>.json and prints the Summary / liveness lines.
A previous-run AUDIT FAIL ('override' prompt) is NOT overridden here: the run aborts and says so.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rehearse_day as RD  # noqa: E402
import rig_runcard as RC   # noqa: E402


def status(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("[driver] " + text, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    ap.add_argument("--day", required=True)
    ap.add_argument("--go-timeout", type=float, default=1800.0, help="s to wait for the GO file")
    ap.add_argument("--override", action="store_true",
                    help="answer a previous-run AUDIT FAIL prompt with 'override' (surgeon's call; say so in the ledger)")
    args = ap.parse_args()

    lines = [ln.strip() for ln in open(args.card, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    a_cmd = next(ln for ln in lines if ln.startswith(".\\cpp_controller.exe"))
    b_cmd = next(ln for ln in lines if ln.startswith(".\\rig\\2_loop.ps1"))
    run = RD.re.search(r"-Run (\S+)", b_cmd).group(1)
    day_dir = os.path.join(REPO, "day_%s" % args.day)
    os.makedirs(day_dir, exist_ok=True)
    slog = os.path.join(day_dir, "server_%s.log" % run)
    blog = os.path.join(day_dir, "loopB_%s.log" % run)
    st = os.path.join(day_dir, "driver_%s.status" % run)
    gofile = os.path.join(day_dir, "GO_%s" % run)
    out_json = os.path.join(day_dir, "driver_%s.json" % run)
    if os.path.exists(gofile):
        os.remove(gofile)
    a_argv = RD.argv_for(a_cmd)
    cap = a_argv[a_argv.index("--capture") + 1] if "--capture" in a_argv else None
    rec = dict(run=run, a_cmd=a_cmd, b_cmd=b_cmd, t_start=time.strftime("%H:%M:%S"))
    t0 = time.time()

    # hold the system timer at 1 ms for the whole run (23:05 burst30: 15.62 ms timer -> 30 % dropped ticks)
    import atexit
    tlog = open(os.path.join(day_dir, "timer_hold_%s.log" % run), "w", encoding="utf-8")
    TH = subprocess.Popen([RC.PY, os.path.join(HERE, "timer_hold.py")], cwd=REPO, stdout=tlog, stderr=subprocess.STDOUT)
    atexit.register(lambda: (TH.poll() is None) and TH.kill())
    time.sleep(1.0)
    HIGH = getattr(subprocess, "HIGH_PRIORITY_CLASS", 0x80)
    sf = open(slog, "w", encoding="utf-8")
    A = subprocess.Popen(a_argv, cwd=REPO, stdout=sf, stderr=subprocess.STDOUT, creationflags=HIGH)
    status(st, "A started (pid %d), waiting for ready" % A.pid)
    if not RD.wait_for(slog, "ready", 30):
        if A.poll() is not None:
            status(st, "FAILED: controller exited before ready rc=%s" % A.returncode)
            print("\n".join(RD.tail(open(slog, encoding="utf-8", errors="replace").read(), 10)))
            sys.exit(1)
        status(st, "WARN: no 'ready' in server log after 30 s, continuing")

    b_argv = RD.argv_for(b_cmd) + ["-NoWatch"]
    B = subprocess.Popen(b_argv, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                         creationflags=HIGH)   # the loop exe inherits the HIGH priority class
    b_lines = []
    bf = open(blog, "w", encoding="utf-8")

    def _drain():
        for ln in B.stdout:
            b_lines.append(ln)
            bf.write(ln)
            bf.flush()
    th = threading.Thread(target=_drain, daemon=True)
    th.start()

    # wait for the prompt (Read-Host does not echo its prompt text with a newline, so look in the joined text)
    t1 = time.time()
    prompt = None
    while time.time() - t1 < 180 and B.poll() is None:
        txt = "".join(b_lines)
        if "Type 'override'" in txt:
            prompt = "override"
            break
        # Read-Host prints its prompt WITHOUT a newline, so it never reaches the line drain;
        # the '=== LIVE RUN' banner is the last full line before the prompt.
        if "Type 'go'" in txt or "=== LIVE RUN" in txt:
            prompt = "go"
            time.sleep(1.0)
            break
        time.sleep(0.5)
    if prompt == "override" and args.override:
        status(st, "previous run audited FAIL -> 'override' sent (--override given)")
        B.stdin.write("override\n"); B.stdin.flush()
        prompt = None
        t1 = time.time()
        while time.time() - t1 < 60 and B.poll() is None:
            if "=== LIVE RUN" in "".join(b_lines):
                prompt = "go"; time.sleep(1.0); break
            time.sleep(0.5)
    if prompt == "override":
        status(st, "ABORTED: previous run audited FAIL (override prompt); rerun with --override if that is the surgeon's call")
        B.stdin.write("\n"); B.stdin.flush()
        B.wait(timeout=30); A.kill()
        sys.exit(2)
    if prompt is None:
        status(st, "FAILED: B never reached the go prompt (rc=%s)" % B.poll())
        print("".join(b_lines[-15:]))
        try:
            B.kill()
        except Exception:
            pass
        A.kill()
        sys.exit(1)

    status(st, "WAITING_FOR_GO  (create %s ; write 'abort' in it to abort)" % gofile)
    t2 = time.time()
    answer = None
    while time.time() - t2 < args.go_timeout:
        if os.path.exists(gofile):
            try:
                answer = open(gofile, encoding="utf-8").read().strip() or "go"
            except OSError:
                answer = "go"
            break
        time.sleep(0.25)
    if answer is None:
        status(st, "ABORTED: no GO within %.0f s" % args.go_timeout)
        B.stdin.write("\n"); B.stdin.flush()
        B.wait(timeout=30); A.kill()
        sys.exit(2)
    rec["t_go"] = time.strftime("%H:%M:%S")
    if answer.lower() != "go":
        status(st, "ABORTED by GO file content '%s' (nothing sent)" % answer)
        B.stdin.write("\n"); B.stdin.flush()
        B.wait(timeout=30); A.kill()
        sys.exit(2)
    B.stdin.write("go\n"); B.stdin.flush()
    status(st, "RUNNING since %s (go sent)" % rec["t_go"])

    live = None
    if cap:
        time.sleep(30)
        if B.poll() is None:
            live = RD.run_check("& $py rig\\check_y_liveness.py --capture %s" % cap, REPO, timeout=60)
            status(st, "RUNNING; liveness@30s: " + (" | ".join(live["tail"][-2:]) if live["tail"] else "n/a"))
    B.wait()
    th.join(timeout=10)
    bf.close()
    try:
        A.wait(timeout=30)
        a_note = "controller exit rc=%d" % A.returncode
    except subprocess.TimeoutExpired:
        A.kill()
        a_note = "controller still running 30 s after the loop ended -> killed"
    sf.close()
    b_out = "".join(b_lines)
    summ = [ln.rstrip() for ln in b_out.splitlines() if ln.startswith(("Summary:", "Localhost summary:", "Exit reason:"))]
    stext = open(slog, encoding="utf-8", errors="replace").read()
    rec.update(secs=round(time.time() - t0, 1), b_rc=B.returncode, controller=a_note, loop_summary=summ,
               fatal=[ln for ln in stext.splitlines() if "FATAL" in ln],
               liveness=(live["tail"] if live else None), t_end=time.strftime("%H:%M:%S"))
    json.dump(rec, open(out_json, "w", encoding="utf-8"), indent=1)
    ok = bool(summ) and not rec["fatal"] and "droppedControlTicks=0" in " ".join(summ)
    status(st, ("DONE OK" if ok else "DONE CHECK") + " rc=%s %s" % (B.returncode, a_note))
    for ln in summ:
        print(ln)
    if rec["fatal"]:
        print("\n".join(rec["fatal"]))
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
