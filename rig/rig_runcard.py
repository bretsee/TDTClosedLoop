#!/usr/bin/env python
"""rig_runcard.py -- print the exact rig-day commands for one phase with every
hand-substituted field filled in, and write them to day_<day>/runcard_<phase>.txt.

    python rig/rig_runcard.py --phase gate --day 2026-10-14 [--depth 1]
    python rig/rig_runcard.py --phase dutyid --day 2026-10-14 --resp 1,3,4,6
    python rig/rig_runcard.py --phase fit --day 2026-10-14 --ctrl 34,40
    python rig/rig_runcard.py --phase arm --day 2026-10-14 --arm mpc --run 1 \
        --resp 1,3,4,6 --ctrl 34,40 --baseline 2.1e-4
    python rig/rig_runcard.py --phase rsweep --day 2026-10-14 --resp 1,3,4,6 --ctrl 34,40
    python rig/rig_runcard.py --phase all --day 2026-10-14 --sim      # rehearsal card

Phases: phase0 gate quiet thwack burst gap dutyid fit refs arm rsweep drift
(--phase all prints every phase in order with placeholders where a value is
still unknown).

--sim (2026-10-13): every terminal-B line gets -Sim (no RZ2, no stim), every
run_audit gets --sim, hardware-only lines (net_diag, find_rz2, selftest, card
probe, send_envelope) are printed as '# skipped in sim', and -Baseline is
omitted (sim features are int16-scale). rig/rehearse_day.py executes the
resulting card end to end.

What it removes from the runbook: the hand-typed -Ticks per design (now
-Design), the inline pandas one-liner that wrote design_rundutyid.csv with no
meta/validation (now written here with its meta and validated: must print
DESIGN OK), the 8 hand-filled fields of build_interleaved_run, the per-arm
--pairs/--feature-map retyping, and the "watch the banner" steps (now
run_audit.py). Every command below is emitted with the current flag set
(-Design/-Capture/-Baseline, run_audit, r-schedule).

Library use: build_card(args) returns [(role, text)] with role in
{comment, A, B, check, matlab, skip}; rehearse_day.py consumes that.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PY = r"C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\.venv\Scripts\python.exe"
PAIR_TABLE = "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"
NNC_TEMPLATES = r"C:\Users\brets\Documents\Repositories\NNController\outputs\BiomimeticInversion\touch\Acute_%s"
LOOP_LIVE = r".\rig\2_loop.ps1 -RZ2 %s -InputChannels %d -TimeoutMs 10 -TickFrames 6"
LOOP_SIM = r".\rig\2_loop.ps1 -Sim -InputChannels %d -TimeoutMs 10 -TickFrames 6"
PHASES = ["phase0", "gate", "quiet", "thwack", "burst", "gap", "dutyid", "fit", "refs",
          "arm", "rsweep", "drift"]


def design_ticks(csv_path):
    meta = os.path.splitext(csv_path)[0] + "_meta.json"
    if os.path.isfile(meta):
        with open(meta) as f:
            return int(json.load(f).get("nTicks", 0))
    if os.path.isfile(csv_path):
        with open(csv_path) as f:
            return sum(1 for _ in f) - 1
    return 0


def ph(name):
    return "\n# ---------------- %s ----------------" % name


def add_args(ap):
    ap.add_argument("--phase", required=True, choices=PHASES + ["all"])
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (or any label: day_<label>/ is used)")
    ap.add_argument("--rz2", default="10.1.0.100")
    ap.add_argument("--sim", action="store_true", help="rehearsal card: -Sim loop, --sim audits, hardware lines skipped")
    ap.add_argument("--input-channels", type=int, default=64)
    ap.add_argument("--depth", type=int, default=1, help="gate: depth index for the run label")
    ap.add_argument("--site", default="<SITE>", help="thwack: site label")
    ap.add_argument("--resp", default=None, help="responsive pairs, e.g. 1,3,4,6")
    ap.add_argument("--ctrl", default=None, help="control channels, e.g. 34,40")
    ap.add_argument("--baseline", type=float, default=None, help="quiet-capture MAV baseline (V)")
    ap.add_argument("--blacklist", default=None, help="channel blacklist for placement_gate, e.g. 33,36")
    ap.add_argument("--block", default=None, help="TDT block dir (or synthetic .npz) when known; fills <blk>")
    ap.add_argument("--best-ch", type=int, default=None, help="best responding channel from the gate table; fills <best ch>")
    ap.add_argument("--model", default="plant_duty.lti")
    ap.add_argument("--templates-day", default=None,
                    help="touch-template day for build_interleaved_run (default: --day; 2026-09-10 for rehearsals)")
    ap.add_argument("--arm", choices=["mpc", "choi"], default="mpc")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--suffix", default="", help="run-label suffix, e.g. _late, _umin")
    ap.add_argument("--r-weight", default="100,100")
    ap.add_argument("--umin", type=float, default=0.0)
    ap.add_argument("--umax", type=float, default=30.0)
    ap.add_argument("--delay-ticks", type=int, default=None,
                    help="fit: inputDelayTicks (default: from check_dead_time on the gate probe, else fitter default 2)")
    ap.add_argument("--sites", default="LP,P1,MP,P3,D1,SHAM")
    ap.add_argument("--events", type=int, default=100)
    ap.add_argument("--total-ticks", type=int, default=22200)
    ap.add_argument("--r-levels", default="100,30,10")
    ap.add_argument("--block-events", type=int, default=20)
    ap.add_argument("--gap-ticks", type=int, default=None,
                    help="dutyid: REGENERATE design_rundutyid.csv for --resp with this measured operating gap "
                         "(from the gap scan) instead of subsetting the pre-built gap-24 design")
    ap.add_argument("--gap-pair", type=int, default=None,
                    help="gap: regenerate design_rungap1.csv on this pair (the gate's best responsive pair) ...")
    ap.add_argument("--gap-amp", type=float, default=25.0, help="... at this amplitude (uA)")
    ap.add_argument("--no-write", action="store_true")
    return ap


def regenerate_design(kind, out_csv, P, extra):
    """Run design_burst_probe.py --kind <kind> --out <csv> <extra>; must validate (DESIGN OK)."""
    import subprocess
    cmd = [PY, os.path.join(HERE, "design_burst_probe.py"), "--kind", kind, "--out", out_csv] + [str(x) for x in extra]
    P("# regenerating %s: %s" % (out_csv, " ".join(cmd[1:])))
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()][-3:]
    for ln in tail:
        P("#   " + ln)
    ok = r.returncode == 0 and any("DESIGN OK" in ln for ln in (r.stdout + r.stderr).splitlines())
    P("# validate -> %s" % ("DESIGN OK" if ok else "FAIL -- do not play"))
    return 0 if ok else 1


def build_card(args):
    """Return [(role, text)] for the requested phase(s)."""
    day = args.day
    D = "day_%s" % day
    resp = args.resp or "<resp>"
    ctrl = args.ctrl or "<c1>,<c2>"
    ctrl_sp = ctrl.replace(",", " ")
    blk = args.block or "<blk>"
    best_ch = ("%d" % args.best_ch) if args.best_ch is not None else (ctrl.split(",")[0] if args.ctrl else "<best ch>")
    base = ("%g" % args.baseline) if args.baseline is not None else "<V>"
    base_flag = (" -Baseline %g" % args.baseline) if (args.baseline is not None and not args.sim) else ""
    audit_sim = " --sim" if args.sim else ""
    bl_flag = (" --blacklist %s" % args.blacklist.replace(",", " ")) if args.blacklist else ""
    loop = (LOOP_SIM % args.input_channels) if args.sim else (LOOP_LIVE % (args.rz2, args.input_channels))
    tdir = NNC_TEMPLATES % (args.templates_day or day)
    model = args.model
    out = []

    def P(text, role="comment"):
        out.append((role, text))

    def HW(text):
        # hardware-only line: kept verbatim live, flagged in sim
        P(text, "skip" if args.sim else "check")

    phases = PHASES if args.phase == "all" else [args.phase]

    P("# RUNCARD %s  phase=%s%s  (generated by rig/rig_runcard.py; $py = %s)"
      % (day, args.phase, "  SIM" if args.sim else "", PY))
    P("# Every PowerShell: Set-ExecutionPolicy -Scope Process Bypass; $py = '%s'" % PY)
    P("# Terminal A = cpp_controller, terminal B = 2_loop (recording LAST, stim enable ON at 'go').")
    if not os.path.isfile(os.path.join(REPO, model)) and args.phase not in ("phase0", "gate", "quiet", "thwack", "burst", "gap", "dutyid"):
        P("# WARN: model %s does not exist yet (the fit phase writes it); lines below reference it." % model)

    for phase in phases:
        if phase == "phase0":
            P(ph("PHASE 0 -- bring-up, before induction"))
            HW("Get-PnpDevice | Where-Object { $_.InstanceId -match 'VEN_4550' } | Format-List FriendlyName, Status, Problem")
            P(".\\rig\\0_preflight.ps1 -InputChannels %d" % args.input_channels, "check")
            HW(".\\rig\\net_diag.ps1                                  # auto-detects the rig NIC (USB dongle 'Ethernet 2' since 10-12); PASS: the path is correctly configured")
            HW("& $py rig\\find_rz2.py                              # exactly one device: %s" % args.rz2)
            HW(".\\rig\\6_udp_selftest.ps1 -RZ2 %s -LiveStim          # before the animal is on the table; 8/8 PASS" % args.rz2)
            HW(".\\MpcPo8eUdpClosedLoop.exe %s . %d --controller constant --constant-output 0 --skip-udp-send --max-control-ticks 300"
               % (args.rz2, args.input_channels))
            P("# PASS = Streaming. numChannels=%d, 300/300, window 6" % args.input_channels)

        elif phase == "gate":
            d = args.depth
            cap = "capture_rig_rungate%d.csv" % d
            P(ph("PHASE G' -- thalamic placement gate, depth %d (%d ticks = %.1f min)" % (d, design_ticks("design_rungate.csv"), design_ticks("design_rungate.csv") / 6000.0)))
            P("# A:")
            P(".\\cpp_controller.exe --mode openloop --play design_rungate.csv --output-count 8 --capture %s" % cap, "A")
            P("# B:")
            P("%s -Run gate%d -Design design_rungate.csv -Capture %s%s" % (loop, d, cap, base_flag), "B")
            P("# after Summary: (recording stopped)")
            P("& $py rig\\run_audit.py --run gate%d --loop-log loop_rungate%d.log --capture %s --design design_rungate.csv%s" % (d, d, cap, audit_sim), "check")
            P("& $py rig\\placement_gate.py --mode thalamic %s --min-amp 13%s" % (("--block %s" % blk) if args.block else "--newest", bl_flag), "check")
            P("& $py rig\\check_impulse_delivery.py --block %s --capture %s --amps 13 18 25 --pairs \"%s\" --design-meta design_rungate_meta.json   # wire gate re-bank" % (blk, cap, PAIR_TABLE), "check")
            P("& $py rig\\check_dead_time.py --capture %s --y-channel %s --json %s\\dead_time_gate%d.json   # -> inputDelayTicks for the fit" % (cap, best_ch, D, d), "check")
            P("& $py rig\\ingest_block.py --label \"gate depth %d probe\" --day %s" % (d, day), "check")
            P("# GO = >= 2 RESPONSIVE pairs AND eff rank >= 2")

        elif phase == "quiet":
            P(ph("PHASE 1 -- quiet capture (60 s), blacklist + baseline"))
            P("& $py rig\\ingest_block.py --label quiet --day %s      # runs analyze_quiet_capture -> galleries/<blk>/quiet.json" % day, "check")
            P("# record baseline V -> pass as --baseline to every later runcard")

        elif phase == "thwack":
            P(ph("PHASE 2 -- thwack battery, site %s" % args.site))
            P("& $py rig\\ingest_block.py --label \"%s thwack\" --mode thwack --day %s" % (args.site, day), "check")
            P("& $py C:\\Users\\brets\\Documents\\Repositories\\NNController\\scripts\\touch\\extract_nthw_templates.py --block %s --site %s --day %s --min-pulse-ms 50 --n-channels %d"
              % (blk, args.site, day, args.input_channels), "check")

        elif phase == "burst":
            cap = "capture_rig_runburst1.csv"
            P(ph("PHASE 3a -- burst ladder (%d ticks = %.1f min)" % (design_ticks("design_runburst1.csv"), design_ticks("design_runburst1.csv") / 6000.0)))
            P("# A:")
            P(".\\cpp_controller.exe --mode openloop --play design_runburst1.csv --output-count 8 --capture %s" % cap, "A")
            P("# B:")
            P("%s -Run burst1 -Design design_runburst1.csv -Capture %s%s" % (loop, cap, base_flag), "B")
            P("& $py rig\\run_audit.py --run burst1 --loop-log loop_runburst1.log --capture %s --design design_runburst1.csv%s" % (cap, audit_sim), "check")
            P("& $py rig\\check_impulse_delivery.py --block %s --capture %s --amps 6 9 13 18 25 --pairs \"%s\" --design-meta design_runburst1_meta.json" % (blk, cap, PAIR_TABLE), "check")
            P("& $py rig\\fit_burst_plant.py --capture %s --meta design_runburst1_meta.json --json %s\\burst_plant.json --png %s\\burst_plant.png   # gain vs burst length, eff-rank per B" % (cap, D, D), "check")
            P("& $py rig\\placement_gate.py --mode thalamic %s --min-amp 13%s      # knees per pair" % (("--block %s" % blk) if args.block else "--newest", bl_flag), "check")
            P("& $py rig\\ingest_block.py --label \"burst ladder probe\" --day %s" % day, "check")

        elif phase == "gap":
            cap = "capture_rig_rungap1.csv"
            P(ph("PHASE 3b -- gap scan (%d ticks = %.1f min)" % (design_ticks("design_rungap1.csv"), design_ticks("design_rungap1.csv") / 6000.0)))
            if args.gap_pair is not None:
                # the pre-built design probes pair 4; put the scan on the gate's best pair instead
                rc = regenerate_design("gap-scan", "design_rungap1.csv", P,
                                       ["--pairs", args.gap_pair, "--amps", "%g" % args.gap_amp])
                if rc != 0:
                    P("# FAIL: gap-scan design did not validate; card stops here")
                    return out
            else:
                P("# (pass --gap-pair <best pair> [--gap-amp 25] to regenerate the scan on the gate's best pair; default design probes pair 4)")
            P("# A:")
            P(".\\cpp_controller.exe --mode openloop --play design_rungap1.csv --output-count 8 --capture %s" % cap, "A")
            P("# B:")
            P("%s -Run gap1 -Design design_rungap1.csv -Capture %s%s" % (loop, cap, base_flag), "B")
            P("& $py rig\\run_audit.py --run gap1 --loop-log loop_rungap1.log --capture %s --design design_rungap1.csv%s" % (cap, audit_sim), "check")
            P("& $py rig\\fit_burst_plant.py --capture %s --meta design_rungap1_meta.json --json %s\\gap_scan.json --png %s\\gap_scan.png   # operating gap = first ratio >= 0.8" % (cap, D, D), "check")
            P("& $py rig\\ingest_block.py --label \"gap scan probe\" --day %s" % day, "check")

        elif phase == "dutyid":
            cap = "capture_rig_rundutyid.csv"
            P(ph("PHASE 4a -- duty-cycled operating-point ID on the responsive pairs"))
            if args.resp and args.gap_ticks is not None:
                # measured operating gap from the gap scan -> fresh duty-PRBS design on the responsive pairs
                rc = regenerate_design("duty-prbs", "design_rundutyid.csv", P,
                                       ["--pairs"] + args.resp.split(",") + ["--gap-ticks", args.gap_ticks, "--n-slots", 1100])
                if rc != 0:
                    P("# FAIL: dutyid design did not validate; card stops here")
                    return out
            elif args.resp:
                rc = write_dutyid_design(args.resp, P)
                if rc != 0:
                    P("# FAIL: dutyid design did not validate; card stops here")
                    return out
                P("# (gap 24 from the pre-built design; pass --gap-ticks <operating gap> to regenerate with the measured gap)")
            else:
                P("# (pass --resp 1,3,4,6 [--gap-ticks N] to write design_rundutyid.csv + meta here; validated)")
            P("# A:")
            P(".\\cpp_controller.exe --mode openloop --play design_rundutyid.csv --output-count 8 --capture %s" % cap, "A")
            P("# B:")
            P("%s -Run dutyid -Design design_rundutyid.csv -Capture %s%s" % (loop, cap, base_flag), "B")
            P("& $py rig\\run_audit.py --run dutyid --loop-log loop_rundutyid.log --capture %s --design design_rundutyid.csv --active-u %s%s"
              % (cap, ",".join("u%s" % p for p in resp.split(",")), audit_sim), "check")
            P("& $py rig\\ingest_block.py --label \"duty-ID probe\" --day %s" % day, "check")

        elif phase == "fit":
            cap = "capture_rig_rundutyid.csv"
            dflag = (",'inputDelayTicks',%d" % args.delay_ticks) if args.delay_ticks is not None else ""
            P(ph("PHASE 4b -- MIMO fit -> %s -> rank gate" % model))
            P("# inputDelayTicks: take check_dead_time's 'recommended' value from the gate probe (pulse onset - 1); fitter default is 2.")
            P("matlab -batch \"cd('%s'); r = fit_sysid_from_capture('%s', struct('useInputs',[%s],'useOutputs',[%s],'orders',1:3%s)); export_plant_lti('%s', r.sys)\""
              % (REPO, cap, resp.replace(",", " "), ctrl_sp, dflag, model), "matlab")
            P("& $py rig\\check_dead_time.py --capture %s --u-channels %s --y-channel %s --lti %s   # VERDICT must be OK/centred"
              % (cap, resp.replace(",", " "), ctrl.split(",")[0], model), "check")
            P("& $py rig\\check_mimo_rank.py --model %s" % model, "check")
            P(".\\cpp_controller.exe --mode mpc --model %s --target 0 --check-model   # Observer: ACTIVE, pole < 1, DC gain printed; exits by itself" % model, "check")
            P("# GO: per-output |corr| > 0.1 on >= 2 channels AND rank PASS -> control channels on DIFFERENT pair footprints")

        elif phase == "refs":
            P(ph("PHASE 5 -- references + tapes + manifest"))
            P("& $py rig\\build_interleaved_run.py --templates-dir %s --sites %s --channels %s --baseline %s --model %s --runs 3 --events %d --total-ticks %d --umax %g --pairs %s --out-dir %s"
              % (tdir, args.sites.replace(",", " "), ctrl_sp, base, model, args.events, args.total_ticks, args.umax, resp.replace(",", " "), D), "check")
            P("# sim-verify u pushes (plant = model, so this is the certainty-equivalent check):")
            P("& $py training\\closed_loop_sim.py --plant %s --ticks 2000 --pairs %s --feature-map %s --output-count 8 --launch --launch-args --pairs %s --feature-map %s --q-weight 1e12,1e12 --r-weight %s --control-horizon 20 --umax %g --reference %s\\ref_mix_r1.csv --capture %s\\capture_sim_refcheck.csv"
              % (model, resp, ctrl, resp, ctrl, args.r_weight, args.umax, D, D), "check")
            P("# want: 'Command varies' and per-output means moving toward the reference")

        elif phase == "arm":
            r = args.run
            lab = "%s_mixr%d%s" % (args.arm, r, args.suffix)
            cap = "%s\\capture_%s.csv" % (D, lab)
            ref = "%s\\ref_mix_r%d.csv" % (D, r)
            n_ref = design_ticks(os.path.join(REPO, D, "ref_mix_r%d.csv" % r))
            ticks = ("-Ticks %d" % n_ref) if n_ref else "-Ticks %d" % args.total_ticks
            P(ph("PHASE 6 -- arm %s (run r%d%s)" % (args.arm.upper(), r, args.suffix)))
            if args.arm == "mpc":
                P("# A:")
                P(".\\cpp_controller.exe --mode mpc --model %s --output-count 8 --pairs %s --feature-map %s --q-weight 1e12,1e12 --r-weight %s --control-horizon 20 --umin %g --umax %g --reference %s --capture %s --max-packets %d"
                  % (model, resp, ctrl, args.r_weight, args.umin, args.umax, ref, cap, n_ref or args.total_ticks), "A")
                P("#   (alternative, dimensionless: replace --q-weight/--r-weight with --q-weight 1e12,1e12 --effort-ratio 0.1; add --dist-observer for the offset-free arm -- NOT Choi-comparable, label it)")
            else:
                P("# A:")
                P(".\\cpp_controller.exe --mode openloop --play %s\\design_choi_mix_r%d.csv --output-count 8 --capture %s" % (D, r, cap), "A")
            P("# B:")
            P("%s -Run %s %s -Capture %s%s" % (loop, lab, ticks, cap, base_flag), "B")
            P("# after Summary:")
            P("& $py rig\\run_audit.py --run %s --loop-log loop_run%s.log --capture %s --ref %s --active-u %s%s%s"
              % (lab, lab, cap, ref, ",".join("u%s" % p for p in resp.split(",")),
                 (" --baseline %g" % args.baseline) if (args.baseline is not None and not args.sim) else "", audit_sim), "check")
            P("& $py rig\\tracking_metrics.py --capture %s --ref %s --y-channels %s --label %s_r%d%s --json %s\\tracking_%s_r%d%s.json --png %s\\tracking_%s_r%d%s.png"
              % (cap, ref, ctrl_sp, args.arm, r, args.suffix, D, args.arm, r, args.suffix, D, args.arm, r, args.suffix), "check")
            P("& $py rig\\ingest_block.py --label \"%s r%d%s arm\" --mode arm --schedule %s\\schedule_mix_r%d.json --day %s" % (args.arm, r, args.suffix, D, r, day), "check")

        elif phase == "rsweep":
            r = args.run
            lab = "mpc_rsweep_r%d" % r
            cap = "%s\\capture_%s.csv" % (D, lab)
            ref = "%s\\ref_mix_r%d.csv" % (D, r)
            n_ref = design_ticks(os.path.join(REPO, D, "ref_mix_r%d.csv" % r))
            levels = args.r_levels.replace(",", " ")
            m = len(resp.split(",")) if args.resp else 2
            P(ph("TIER C 6e -- interleaved R sweep in ONE run: R in {%s}, %d-event blocks" % (levels, args.block_events)))
            P("# build the per-block schedule (needs a ref with blocks = k * levels, e.g. --events 120 for 3 levels x 20):")
            P("& $py rig\\build_r_schedule.py --schedule %s\\schedule_mix_r%d.json --block-events %d --r %s --m %d --out %s\\rsched_r%d.csv"
              % (D, r, args.block_events, levels, m, D, r), "check")
            P("# A:")
            P(".\\cpp_controller.exe --mode mpc --model %s --output-count 8 --pairs %s --feature-map %s --q-weight 1e12,1e12 --r-weight %s --r-schedule %s\\rsched_r%d.csv --control-horizon 20 --umin %g --umax %g --reference %s --capture %s --max-packets %d"
              % (model, resp, ctrl, args.r_weight, D, r, args.umin, args.umax, ref, cap, n_ref or args.total_ticks), "A")
            P("# B:")
            P("%s -Run %s %s -Capture %s%s" % (loop, lab, ("-Ticks %d" % n_ref) if n_ref else "-Ticks %d" % args.total_ticks, cap, base_flag), "B")
            P("& $py rig\\run_audit.py --run %s --loop-log loop_run%s.log --capture %s --ref %s%s" % (lab, lab, cap, ref, audit_sim), "check")
            P("& $py rig\\analyze_r_sweep.py --capture %s --ref %s --rsched %s\\rsched_r%d.json --y-channels %s --u-channels %s --hold %g --lat %s\\server_lat_capture_%s.csv --json %s\\rsweep_r%d.json --png %s\\rsweep_r%d.png"
              % (cap, ref, D, r, ctrl_sp, resp.replace(",", " "), args.umin, D, lab, D, r, D, r), "check")
            P("& $py rig\\ingest_block.py --label \"mpc R-sweep r%d arm\" --mode arm --schedule %s\\schedule_mix_r%d.json --day %s" % (r, D, r, day), "check")

        elif phase == "drift":
            cap = "capture_rig_rundutyid_late.csv"
            P(ph("PHASE 7 -- drift re-probe (duty-ID replay, 2 min) then stim zero"))
            P("# A:")
            P(".\\cpp_controller.exe --mode openloop --play design_rundutyid.csv --output-count 8 --capture %s --max-packets 12000" % cap, "A")
            P("# B:")
            P("%s -Run dutyid_late -Ticks 12000 -Capture %s%s" % (loop, cap, base_flag), "B")
            P("& $py rig\\run_audit.py --run dutyid_late --loop-log loop_rundutyid_late.log --capture %s --expect-ticks 12000%s" % (cap, audit_sim), "check")
            P("& $py rig\\check_dead_time.py --capture %s --u-channels %s --y-channel %s --lti %s   # gain/lag drift vs the fit" % (cap, resp.replace(",", " "), ctrl.split(",")[0], model), "check")
            HW("& $py rig\\send_envelope.py --rz2 %s --shape const --umax 0 --secs 2 --count 8 --yes      # stim zero" % args.rz2)
    return out


def render(card):
    lines = []
    for role, text in card:
        if role == "skip":
            lines.append("# skipped in sim: " + text.lstrip())
        else:
            lines.append(text)
    return "\n".join(lines) + "\n"


def main():
    ap = add_args(argparse.ArgumentParser(description=__doc__,
                                          formatter_class=argparse.RawDescriptionHelpFormatter))
    args = ap.parse_args()
    card = build_card(args)
    text = render(card)
    print(text)
    if not args.no_write:
        D = "day_%s" % args.day
        os.makedirs(os.path.join(REPO, D), exist_ok=True)
        name = "runcard_%s%s%s.txt" % (args.phase,
                                       ("_%s_r%d%s" % (args.arm, args.run, args.suffix)) if args.phase in ("arm", "rsweep") else "",
                                       "_sim" if args.sim else "")
        path = os.path.join(REPO, D, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("# written: %s" % path)
    return 1 if any(t.startswith("# FAIL") for _, t in card) else 0


def write_dutyid_design(resp, P):
    """Zero the non-responsive columns of design_rundutyid_all8.csv, write the
    subset with a meta sidecar, validate (must print DESIGN OK)."""
    import numpy as np  # noqa: F401
    from design_burst_probe import read_design, write_design, validate
    keep = sorted({int(x) for x in resp.split(",")})
    src = os.path.join(REPO, "design_rundutyid_all8.csv")
    meta_src = os.path.join(REPO, "design_rundutyid_all8_meta.json")
    if not os.path.isfile(src):
        P("# FAIL: %s not found" % src)
        return 1
    U = read_design(src)
    for k in range(U.shape[1]):
        if (k + 1) not in keep:
            U[:, k] = 0.0
    dst = os.path.join(REPO, "design_rundutyid.csv")
    write_design(dst, U)
    meta = {}
    if os.path.isfile(meta_src):
        with open(meta_src) as f:
            meta = json.load(f)
    meta["pairs"] = keep
    meta["events"] = [e for e in meta.get("events", []) if int(e.get("pair", 0)) in keep]
    meta["nTicks"] = int(U.shape[0])
    meta["total_charge_uAticks"] = float(U.sum())
    meta["derived_from"] = os.path.basename(src)
    with open(os.path.join(REPO, "design_rundutyid_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    P("# design_rundutyid.csv written from design_rundutyid_all8.csv keeping pairs %s; duty per pair: %s"
      % (keep, {("u%d" % (k + 1)): round(float((U[:, k] > 0).mean()), 3) for k in range(U.shape[1]) if (k + 1) in keep}))
    rc = validate(dst, U, meta)
    P("# validate -> %s" % ("DESIGN OK" if rc == 0 else "HARD FAIL -- do not play"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
