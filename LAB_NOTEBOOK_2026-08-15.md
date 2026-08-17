# Lab Notebook — 2026-08-15 (Saturday)

**Session goal:** 10 bounded runs to determine the cause, or at least the rate, of the
intermittent closed-loop crash (2/3 of runs on 08-14, dying at tick 2–36 with no summary
and a 0-byte capture). **Outcome: root cause found, fixed, and verified — and it was
bigger than the crash.**

## Timeline

| When | What |
|---|---|
| prep | Windows Application event log already had the answer-shape: all five 08-14 crashes were `0xc0000374` heap corruption in ntdll, same fault offset, on BOTH the Jul-23 and Aug-14 builds → not a code regression. Instrumented before running: WER LocalDumps (full dumps), rebuild with PDB, per-tick flush of the capture CSV, `rig\7_campaign.ps1` wrapper (exit code, crash detect, auto-zero stim, ledger row per run). Dump pipeline validated end-to-end with a deliberate crash-test exe before any rig run. |
| c01, c02 | Both crashed `0xC0000374` within ~5 packets. Full dumps captured. Both show the identical corruption: **16 consecutive float32 values written across two adjacent 32-byte heap blocks**, destroying the second block's header. Detected later at an unrelated per-tick allocation (`clamp_amplitudes_f32`) — the detector was never the culprit. |
| c03 | One diagnostic run under **full PageHeap**. Caught the corrupter mid-write: `0xC0000005` inside **PO8eStreaming.dll**, called from `readBlock`, guard page hit exactly 32 bytes past our buffer. |
| fix | `PO8e.h` requires read buffers of `numChannels() × dataSampleSize()` bytes. The code hard-coded 2 bytes/sample (int16) and never called `dataSampleSize()`. **The stream is float32 (4 bytes/sample)** — 16 ch × 4 B = 64 B written into a 32 B buffer on every read. Fixed: query the sample size, size the buffer per the contract, decode int16 or float32 into the (now float) ring, hard-fail on anything else. Sim-verified byte-identical on the int16 path, then rebuilt. |
| c04–c09 | **Six consecutive clean 6000/6000 runs** on hardware (`droppedControlTicks=0`, feature window 6/6/0, no offset jumps every run). Under the old ~2/3 crash rate, six clean in a row is P≈0.001 — combined with the PageHeap capture, the case is closed. Banner confirms `sampleBytes=4 (float32)` live. |
| c10 | Operator error, and an informative one: the Terminal-A server never came up (port held by a stale MATLAB), the loop correctly ran its zero-command policy for 1408 ticks and exited cleanly when the stream stopped. The failure ledger row is accurate. |

## The bigger finding: every feature was garbage

Since the Synapse stream became float32 (likely with the circuit changes around 08-12/14),
the controller has been reading **reinterpreted float bytes as int16 samples**. Example:
float `0.00118` (a real ~1.2 mV feature) has high half-word `0x3A9B` = 14,987 as int16 —
exactly the "healthy" feature magnitudes we celebrated on 08-14. Consequences:

- The crash was the *benign* symptom; the silent one was a controller with meaningless
  measurements. **All feature-based data from float32-era captures (pre-fix) is invalid.**
- Post-fix features are volts-scale (~1.5 mV mean in saline) and physically sensible.
- The corruption's intermittency was allocation-order luck (whether the 32-byte spill hit
  a heap block anyone checked).

## Secondary findings and fixes today

- **Stim-left-live hazard closed for crashes**: SEH faults bypass the C++ cleanup, so the
  RZ2 held the last commanded amplitude after every crash. The campaign wrapper now
  auto-zeros (verified against the fake RZ2); c01/c02 crashes were zeroed within seconds.
- **Timing analysis of c04–c09**: no stim→feature coupling above the noise floor — but no
  Synapse recordings were made today (diagnosis runs), so stim delivery is unverified and
  no conclusion is drawn. The saline timing number remains unbanked; the +1-tick transport
  delay stands proven from `UDP1` (08-11).
- **Stale-server gotcha** (bit us twice, including c10): a bounded MATLAB server that
  never receives a packet blocks forever holding port 31000. Kill stale MATLAB before
  starting a server.
- Watch items: 4–8% localhost timeouts at `-TimeoutMs 5` (use 10); occasional 16–23 mV
  feature transients in c05–c09 uncorrelated with commands (saline motion suspected).

## Also built today (evening): in-vivo deployment tooling

Impulse-probe excitation (`make_excitation` kind 'impulse'), model-free impulse-response
report (`rig/fit_impulse_model.py`, validated on a planted synthetic), touch-template →
feature-scale reference builder (`rig/build_touch_reference.py`), MPC trajectory tracking
with horizon preview and tunable weights (`mpc_test`, `matlab_controller_server`,
`4_mpc_server.ps1 -Reference/-RWeight`), all bench-tested (`bench_test_reference_mpc.m`,
5/5 pass) and exercised end-to-end in sim. Runbook: `DEPLOYMENT_PLAN_INVIVO.md`.

## Late-evening addendum: full code review + fixes (all re-verified)

A 10-finding adversarial review of the uncommitted tree surfaced two safety-grade
defects, both fixed and re-tested same night:

1. **Stim zeroing never ran on Ctrl+C or crashes** (no console/SEH handlers existed,
   despite the function comment claiming that coverage). Added `SetConsoleCtrlHandler`
   + best-effort `SetUnhandledExceptionFilter` (allocation-free zeroing; WER dumps
   still captured). Untested on hardware — a 30 s Ctrl+C check in saline is now step 5
   of the deployment preflight. A hard kill still bypasses any in-process handler; an
   RZ2-side zero-on-UDP-silence watchdog is the durable fix (raised in the plan).
2. **Scalar controller replies were broadcast to all 8 stim pairs** — the standard
   single-pair workflow (1-pair capture → m=1 model → scalar mpc output) would have
   stimulated 7 unintended sites in vivo. C++ now refuses to broadcast (slot 0 + loud
   warning); the proper mapping is server-side: `4_mpc_server -Pairs <n>` routes the
   command to the pair the model was identified on.

Also fixed from the review: single-output reference previews were silently truncated
to the current tick (preview was a no-op in exactly the production configuration —
now bench-tested to anticipate); MPC warm-up was nullified by its own cleanup (init
cost re-paid on the first real tick — now soft-resets state only); a bounded server
died on any single 1 s stall (now requires 3 consecutive idle reads); sim
flush-discard was a no-op making overrun-fix validation vacuous (sim now mirrors the
PO8e peek/flush contract exactly); MPC_OPTS-in-AllModels.mat was documented but never
loaded; stale base-workspace MPC_OPTS leaked across sessions (server now clears);
unbounded-run capture buffers capped at 1 row (now 20k + loud warning); unbounded
turnaround-array growth in the reply path (now bounded with exact running stats).

Bench suite `bench_test_reference_mpc.m` extended to 8 checks (all pass), C++
rebuilt (`aug15-final.{exe,pdb}` archived), post-fix sim smoke clean 600/600.

## Artifacts

- `campaign_ledger.csv` (13 rows: c00–c10 + rehearsals), `loop_runc*.log`,
  `rig_runc*.csv`, `capture_rig_runc*.csv`
- `crash_dumps\`: c01/c02 heap-corruption dumps, c03 PageHeap dump, analysis logs
- Binaries: `MpcPo8eUdpClosedLoop.preCampaign-aug15.exe` (pre-instrumentation),
  `aug15-campaign.{exe,pdb}` (instrumented, pre-fix), `aug15-fix.{exe,pdb}` (current)
- `CAMPAIGN_2026-08-15.md` (protocol + evidence), `UDP_FAULT_ANALYSIS_2026-08-09.md`
  (prior fault, for the chain of custody on the transport path)
