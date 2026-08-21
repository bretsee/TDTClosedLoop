# TDTClosedLoop Experiment Manual

Complete instructions for running the closed-loop sensory-prosthesis experiment:
VPL thalamic microstimulation -> S1 cortical recording, with stimulus amplitudes
computed either offline (Choi-2016-style open-loop synthesis) or in real time
(receding-horizon MPC / neural-network policy).

This is the standing reference manual. Dated `RIG_DAY_*.md` files remain the
per-session runbooks; this document is the superset they draw from.
Last verified against the code: **2026-08-20** (all bench/sim acceptance green).

---

## 1. System overview

```
                    THIS PC (10.1.0.1/24, static)                RZ2 (10.1.0.100)
  +--------------------------------------------------+    +------------------------+
  |  MpcPo8eUdpClosedLoop.exe  (the LOOP)            |    |  Synapse circuit       |
  |    PO8e ingest -> ring -> 6-sample feature       |<===|  PZ2 -> Wav1/Wav2      |
  |    -> UDP request to controller server           | PO8e  (5-200 Hz LFP band,  |
  |    <- reply u1..u8 -> clamp -> UDP to RZ2 ------>|===>|   RZ2 DSP filters)     |
  |                                                  | UDP|  UDP1 -> Scle ->       |
  |  Controller server (port 31000/31001), ONE of:   |22022  StimGen (101.7253 Hz |
  |    matlab_controller_server.m  (MPC, tracking)   |    |   carrier, free-run)   |
  |    cpp_controller.exe          (mpc|nn|openloop) |    |  -> IZ2 -> electrodes  |
  +--------------------------------------------------+    +------------------------+

  Word k of the UDP packet drives BIPOLAR PAIR k = electrodes (2k-1, 2k).
  8 words = 8 pairs = 16 electrodes. Verified exact (sal1, 2026-08-17).
```

Key rates: acquisition 610.3516 Hz (base/40); stim carrier 101.7253 Hz
(base/240) = exactly 6 samples/period; control tick 10 ms wall-clock or
9.8304 ms frame-locked (`-TickFrames 6`, PLL onto the RZ2 crystal).

**Feature** = per-channel mean over the newest 6 samples, one value per tick:
rectified `mean(|x|)` by default, or signed `mean(x)` with `--feature-signed`
(Choi-style signed LFP; added 2026-08-20). Windows are contiguous and
non-overlapping in frame-locked mode.

### Golden rules (violating any of these has burned a session before)

1. **Start the Synapse recording LAST** — server ready, loop at its prompt,
   THEN record, then `go`. (Pre-loop streaming overran the card: 3/3 crashes.)
2. **Capture and deploy must share the tick mode** (`-TickFrames 6` both, or
   neither) **and the feature mode** (`-FeatureSigned` both, or neither).
   Models and references are only valid in the space they were fitted in.
3. **Leave `-TickPhaseUs` unset.** The PO8e counter zeroes at recording start,
   so carrier phase re-randomizes per recording; the per-run audit governs.
4. **Archive `exe`+`pdb` before every rebuild** (`MpcPo8eUdpClosedLoop.<tag>.exe`).
5. **Kill stale MATLAB before starting a server** — a bounded server that never
   got a packet blocks forever holding port 31000.
6. **Check stimulator charge** before interpreting any stim-null result
   (`Scle`/`Plse`/`sSig` all-zero has three causes: safety button, battery, routing).
7. Never launch MATLAB via `Start-Process`; always foreground `matlab -batch`
   with `2>&1`.

---

## 2. Hardware bring-up & preflight

| Step | Command / action | Expect |
|---|---|---|
| Network | (persistent) static 10.1.0.1/24 on Ethernet, no gateway | `rig\net_diag.ps1` verdict OK |
| Find RZ2 | `python rig\find_rz2.py` | exactly one device: 10.1.0.100 |
| UDP path | `.\rig\6_udp_selftest.ps1 -RZ2 10.1.0.100` | all tests PASS |
| Env | `.\rig\0_preflight.ps1` | sets MATLAB PATH (without it the exe exits **code 53 silently**) |
| Off-rig suites | `matlab -batch "cd('<repo>'); bench_test_reference_mpc"` and `.\cpp_controller.exe --selftest` | ALL PASS / SELF-TEST PASSED |
| Synapse | circuit loaded; **stim safety button ON**; PZ2 ON; stimulator charged | `Wav1/Wav2` live |
| Crash net | WER dumps registered (`rig\setup_wer_dumps.ps1`) | dumps land in `crash_dumps\` |

Python = the PythonIntanAnalysis venv:
`C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\.venv\Scripts\python.exe`
(bare `python` on a fresh shell is the MS-Store stub, exit 9009).

---

## 3. Quiet capture (baseline, noise floor, line noise)

First run in any NEW environment (e.g. the surgical suite move).

1. No stim, no loop. Start a Synapse recording, ~60 s, stop.
2. Read the block (note: block dirs NEST one level — the real block is the
   same name repeated inside).
3. Compute per-channel `Wav1` std (noise floor), the feature-space baseline
   (mean of the 6-sample feature over the record — this is the day-of
   `--baseline` for `build_touch_reference.py`), and the 60 Hz + harmonics
   fraction of feature variance.
4. Decision rule: only if line noise dominates feature variance, consider a
   notch (fit-side scripts first; the C++ feature path needs a rebuild).

## 4. Probe capture (system ID data)

Design is by MATLAB offline, validation gates before current flows, delivery
is by the C++ replay server (bit-perfect: 925/925, 476/476, 923/923 across
sal2/seq1/int1 — the MATLAB server stretched probes and lost 5.1%).

```powershell
# Terminal A: design + validate + serve (sequential = per-pair blocks, clean
# baseline; interleaved = default, cross-pair interaction probe)
.\rig\1c_server.ps1 -Run seq2 -Schedule sequential          # ~28000 ticks, 4.6 min
# Terminal B: the loop, frame-locked; recording still NOT started
.\rig\2_loop.ps1 -Run seq2 -RZ2 10.1.0.100 -TimeoutMs 10 -Ticks 28000 -TickFrames 6
#   ... wait at the 'go' prompt; START THE SYNAPSE RECORDING NOW; type 'go'
```

Audit immediately after:

```powershell
python rig\check_impulse_delivery.py --design design_runseq2.csv --block <block path>
# Expect: wire==design, pair mapping exact, ~0 missed / ~0 doubled carrier pulses.
# Margins < ~1.5 ms occasionally give ~0.2% doubles; the fitter auto-excludes them.
```

Notes: `1c_server` REUSES an existing `design_run<label>.csv` (delete to
regenerate). Tissue ID probes ONE pair at a time (`-Channels <p>`); all-pairs
is for saline validation. If the response time constant approaches the 500 ms
gap, raise `-GapTicks` (and `-Ticks` to keep trials/amp).

## 5. Model fitting

### 5a. LTI (the MPC plant)

```powershell
.\rig\3_fit.ps1 -Run seq2 -Channel <k>          # ARX sweep 1..8, parsimony pick
.\rig\3_fit.ps1 -Run seq2 -Channel <k> -Save    # writes AllModels(10).sys
```

What happens on `-Save` (all automatic since 2026-08-20):
- Ts is MEASURED from the capture and stamped (10 / 9.8304 ms) — model Ts is
  the source of truth everywhere downstream.
- The capture means are stored as `sys.uOffset/yOffset`; every controller runs
  the model in centered coordinates and converts at the boundaries. (Before
  2026-08-20 the offsets were computed but never applied — do not compare
  against closed-loop behavior from before that date.)
- Bank the printed **"output N: range [..]"** — targets must come from it.

Model-free cross-checks: `fit_impulse_model.py --input <k>` (kernel, gain,
delay, linearity, null-floor verdict — it REFUSES saline/noise, by design),
`crossval_model.m`, `sweep_channels.m`. Go/no-go: `|corr| u->y > 0.1`; a
`> 0.9` at lag 0 that is global rather than focal is ARTIFACT, not response
(real responses peak 15-28 ms).

For the C++ MPC / synthesis tools: `export_plant_lti('plant_seq2.lti')`
(carries Ts and the offsets; old binaries ignore the extra rows).

### 5b. Neural network (the learned-policy arm)

```powershell
python training\train.py --captures capture_runseq2.csv --mode inverse `
    --arch residual_mlp --history 25 --umax 25 --out models\inv_seq2.nnw
python training\verify_export.py models\inv_seq2.nnw     # PyTorch == C++ to f32
python rig\check_nnw_mode.py models\inv_seq2.nnw         # MUST print OK
.\cpp_controller.exe --mode nn --model models\inv_seq2.nnw --output-count 8 --pairs <k>
```

`--mode inverse` (features->stim) is the controller; `forward` is a plant
model and `check_nnw_mode.py` refuses to deploy it (predicted features on the
stim wire). Models from the acute NNController work do NOT port — different
input framing and layer types; retrain on rig captures (the acute result that
transfers is the architecture ranking, and that the map is ~linear — compare
against ridge/ARX before crediting the NN).

## 6. Gate-threshold calibration (per pair; Choi's method)

Run a separate LOW-amplitude probing sequence (amps below and around expected
threshold, e.g. 2-12 uA) per pair; fit evoked amplitude vs current; the knee
is that pair's threshold. Choi 2016 found 4-10 uA in rat VPL and set the gate
attenuation a = 0.1-0.2 BY HAND (a -> 0 is harmful to the optimization).
Thresholds are per-pair and drift — re-calibrate each session. These numbers
feed `choi_synthesis.py --gate-threshold/--gate-atten`.

## 7. Reference construction (touch templates)

```powershell
python rig\build_touch_reference.py --npz <touch npz> --channel <k> `
    --baseline <day-of volts> --repeats 10 --out ref_touch.csv          # rectified
python rig\build_touch_reference.py --npz <touch npz> --channel <k> `
    --baseline 0 --signed --out ref_touch_signed.csv                    # signed mode
```

Templates live in `NNController\outputs\BiomimeticInversion\touch\` ([16 ch x
122 samples] uV @ 610.352 Hz ~= 200 ms, Choi's T = hold + 50 ms convention).
`--baseline` is a DAY-OF measurement (quiet capture), not a stored constant.
`--signed` iff the loop runs `--feature-signed`.

## 8. Open-loop arm (Choi replication)

Two ways to make the open-loop trajectory:

**8a. Choi synthesis (primary — his exact formulation, eq. 5 + gate):**

```powershell
python rig\choi_synthesis.py --model plant_seq2.lti --reference ref_touch.csv `
    --umax 25 --mu 1e-9 --lam 0 --gate-threshold <cal> --gate-atten 0.1 `
    --out design_choi1.csv --report
```

- Optimizes raw amplitudes 0..umax against the model; gate handled by
  sequential linearization with Choi's damping (beta = max(0.3, 0.97^k)).
- READ THE REPORT: if it says the gate DID NOT CONVERGE, the design is
  suspect. If input penalties dominate tracking >10x, lower mu/lam (volts vs
  uA differ ~1e8 — the rWeight lesson).
- Acceptance suite: `python rig\test_choi_synthesis.py` (7 checks, no hardware).

**8b. Certainty-equivalent dump (for exact open-vs-closed parity):** run the
closed-loop MPC against the MODEL plant in sim and replay its command tape:

```powershell
python training\closed_loop_sim.py --plant plant_seq2.lti --launch `
    --ticks 2000 --target <t> --dump-u design_ce1.csv
```

**Deliver either on hardware** (same replay path as probes — verbatim, zeros
after the last row):

```powershell
.\cpp_controller.exe --mode openloop --play design_choi1.csv --output-count 8 `
    --capture capture_choi1.csv --max-packets <rows>
.\rig\2_loop.ps1 -Run choi1 -RZ2 10.1.0.100 -TimeoutMs 10 -Ticks <rows> -TickFrames 6
# recording LAST, then 'go'
```

## 9. Closed-loop arm (real-time MPC)

```powershell
# Terminal A (server; kill stale MATLAB first):
.\rig\4_mpc_server.ps1 -Reference ref_touch.csv -RWeight 1e-3 -Pairs <k> `
    -FeatureChannel <k> [-Horizon 40] [-ControlHorizon 4] [-QWeight 1] [-UMax 25] `
    [-ModelIndex 10]
# Terminal B (loop):
.\rig\2_loop.ps1 -Run cl1 -RZ2 10.1.0.100 -TimeoutMs 10 -Ticks <rows> -TickFrames 6
# recording LAST, then 'go'
```

- `-RWeight 1e-3` (or lower) is REQUIRED for honest tracking: the cost
  penalizes absolute u with no integral action, so the default R=1 settles at
  u* = r*g/(g^2 + R/Q), far short of the target. Expected, not a fault.
- `-FeatureChannel` replaces the old hand-edit of `feature_map` (2026-08-20).
- `-Pairs <k>` maps a 1-output model to the pair it was identified on —
  without it the command lands on pair 1.
- Defaults: N=20 (~200 ms), Nu=2, preview 20 ticks. The horizon should cover
  the observed settle: from the fitted dominant pole, N >= 4*tau/Ts.
- **Control horizon vs reference speed (measured on hardware, cl3
  2026-08-20): Nu=2 holds one value for N-1 of the N horizon ticks, so a
  reference transient w ticks wide is diluted to ~w/N of its amplitude — a
  2-3-tick rectified touch spike came through at ~2-3% instead of 18%.**
  For touch-template tracking set `-ControlHorizon` >= the event width in
  ticks (Nu=N=20 is fine; the QP is still tiny). Slow plateau references
  (>= ~1 s) track fully at Nu=2. Choi's offline synthesis optimizes every
  tick's amplitude independently — the closed-loop arm should be given the
  same freedom via Nu when comparing.
- Fractional amplitudes are delivered exactly: 5310 distinct float commands
  reproduced bit-for-bit at Scle (cl2, 2026-08-20). Do NOT round commands to
  integers; any IZ2-internal DAC quantization is invisible to the command
  path and assessed only via artifact amplitude.
- Watch the server: **out0 must vary with feature0** (constant out0 = the
  historical open-loop defect); saturation at a bound = unreachable target.
- MATLAB is the primary tracking server (the C++ mpc has no preview).
  Frame-locked closed loop is allowed since Ts alignment (2026-08-18).

The scientific comparison (same session, same reference, same pair): 8a
open-loop vs 9 closed-loop vs 5b NN policy. Metrics per Choi: correlation of
trial-averaged evoked vs natural responses (his: 0.78 all / 0.90 first
100 ms), spatial map correlation, charge delivered, and robustness to drift
(open-loop should degrade first — that gap IS the value-of-feedback result).

## 10. Safety systems & emergency procedures

- **The RZ2 HOLDS the last commanded amplitude and StimGen free-runs.**
  Anything that exits without zeroing leaves stim ON (measured: 41.5 s at
  full amplitude, 2026-08-14).
- The loop zeroes all 8 outputs (5 packets) on: normal exit, caught errors,
  **Ctrl+C / console close / unhandled SEH** (`emergency_zero_now`).
  **HARDWARE-VERIFIED 2026-08-20 (block LD-260820-183738): Ctrl+C during live
  full-amplitude stim -> Scle silent within 12 ms and zero for the entire
  24 s recorded tail.** A hard kill (`Stop-Process`) BYPASSES all of it.
- After ANY crash: `python rig\send_envelope.py --kind const --umax 0` zeroes
  the wire (this is also what `7_campaign.ps1` does automatically).
- Ultimate fallback: Synapse stim safety button / stimulator power.
- Crashes leave WER dumps in `crash_dumps\`; `rig\analyze_dump.ps1` wraps
  WinDbg (set `_NT_SYMBOL_PATH`; never `.sympath` inline).

## 11. Post-run analysis

| Question | Command |
|---|---|
| Did commands reach the RZ2? | read `UDP1` from the block (the wire record; `sSig` is downstream) |
| Probe delivery quality | `python rig\check_impulse_delivery.py` |
| u->y timing/coupling | `python rig\timing_check.py` (empirical floor; refuses chance) |
| Which channel responds | `sweep_channels.m` |
| Model transfer | `crossval_model.m` |
| Kernels per pair | `python rig\fit_impulse_model.py --input <k>` |

## 12. Choi 2016 correspondence

| Item | Choi 2016 | This rig | Status |
|---|---|---|---|
| Prep | rat VPL stim -> S1 LFP | same lineage | match |
| Stim config | 8 bipolar adjacent pairs (16-ch cohort) | 8 bipolar pairs, word k -> (2k-1,2k) | match |
| Pulse | symmetric biphasic 200 us/phase, single polarity | ~205 us/phase biphasic, u >= 0 | match |
| Input parameterization | amplitude envelope on a constant-rate carrier | same (101.7 Hz carrier) | match (rate differs) |
| Carrier / bin | 610 Hz, 1.63 ms bins | 101.7253 Hz, 9.83 ms ticks | DIVERGENCE (user decision) |
| Controlled signal | signed 5-200 Hz LFP @610 Hz (or 12-15 PCs) | 6-sample mean; rectified default, signed via `--feature-signed` | match available (signed mode) |
| Blanking | 480 us sample-and-hold pre-filter | RZ2 DSP chain (verify on circuit) | assumed match — confirm |
| System ID | N4SID subspace, n=50 | ARX LS 1..8 + parsimony | DIVERGENCE (deliberate, toolbox-free) |
| Optimization | offline QP, T = hold+50 ms, box 0..I_max | `choi_synthesis.py`, same form | match |
| Effort penalties | mu*\|\|u\|\|^2 + lam*v^2 (tau_lp 100 ms), hand-tuned | same terms, same alpha formula | match |
| Threshold gate | in-model, 4-10 uA, atten 0.1-0.2, seq. linearization + damping | same, same schedule | match |
| Reference | trial-averaged touch-locked LFP, 25 trials | touch npz templates, trial-averaged | match |
| Closed loop | none (named as future work) | receding-horizon MPC + observer | our NOVEL extension |
| I_max convention | max probing amplitude | same rule | match |

Because gate thresholds and mu/lam were derived on Choi's 1.63 ms grid, the
published numbers do NOT transfer to 9.83 ms bins — recalibrate (Section 6)
and re-tune mu/lam per animal (Choi hand-tuned per animal too).

## 13. Failure branches (fast lookup)

| Symptom | Cause | Fix |
|---|---|---|
| exe exits code 53, no output | MATLAB runtime not on PATH | run `0_preflight.ps1` in THIS shell |
| server "Unable to bind" 31000 | stale MATLAB holding the port | kill matlab/MATLAB pair |
| `Skipping N to position M` then death | card backlog (recording started too early) | recording-LAST order |
| out0 constant while feature0 moves | controller ignoring measurement | check observer warnings; branch E1 |
| out0 constant AT the model's uOffset | model has ~zero gain (e.g. saline junk fit) — "do nothing" IS optimal; E1's 1e-6 threshold false-alarms | prove closure with a known-gain model (toy at another slot, -ModelIndex) |
| reference DC tracks but transients don't | Nu too small: hold-last dilutes a w-tick event by ~w/N | raise -ControlHorizon to >= event width (Section 9) |
| server-log out0 max exceeds wire max | startup-transient replies superseded before the next send (newest-reply-wins) | normal; the wire (UDP1) is the ground truth |
| u pinned at 0 or uMax | unreachable target | pick target from the capture's printed range |
| 3_fit stamps 10 ms on a frame-locked capture | pre-2026-08-20 median(diff) Ts estimator biased by PLL fire jitter | fixed (span/(N-1)); update the repo if you see it |
| `Scle`/`Plse`/`sSig` all zero | safety button OR battery OR routing | check in that order |
| ~0.2-2% doubled carrier pulses | unlucky per-recording carrier phase | rerun (re-rolls phase); fitter auto-excludes |
| timeouts ~5% at `-TimeoutMs 5` | MATLAB server turnaround spikes | `-TimeoutMs 10`; freshTicks >= 99% is fine |
| fake_rz2 CSV missing the tail | buffered writes | read only after the process exits |

---

*Formats: design CSV = `tick,u1..u8` (1-based, %.9g); capture CSV =
`tick,seq,t_ms,u1..,y1..`; `.lti` = text A/B/C/D/Ts + optional offsets;
`.nnw` = text net + `# mode:` stamp. All parsers strip `#` comments.*
