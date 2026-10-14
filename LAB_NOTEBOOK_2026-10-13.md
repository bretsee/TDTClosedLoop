# Lab notebook — 2026-10-13 (rehearsal + surgery preparation; acute #3 is Wed 2026-10-14)

Rig recovered on 10-12 through the USB adapter (`Ethernet 2`, ASIX AX88179; net_diag / find_rz2 /
6_udp_selftest 8/8 / 0_preflight all PASS, commit a575209). Tonight and today: a full simulated
rehearsal of the 10-14 runbook driven from the generated runcards, three offline tool verifications
(synthetic TDT block + burst-aware delivery checker, QP conditioning flags + sweep, artifact-aware
re-analysis of the acute-2 arms), the deck restyle, and the four surgery-prep bundles. The weekly
meeting is after the surgery (Thu/Fri 10-15/16), so the 10-16 deck has a results placeholder.

## Headline findings

1. **The rehearsal's "loop stall" was the rehearsal driver, not the rig.** Every driver-run sim
   phase showed one hole of 3.60-3.62 s at exactly 26.3 s after the first packet (packet 2675),
   366 dropped control ticks per run, and in the first rehearsal the controller server quit on it
   ("Idle 3x") while the loop ran on with zero output.
   - Cause: `rehearse_day.py` started terminal B (`powershell -File 2_loop.ps1`) with stdout on a
     pipe it did not read until the run ended. PowerShell relays the loop exe's prints; when the
     4 KB pipe filled (~26 s of "Latency:" lines) the relay blocked and, behind it, the loop's own
     printf. The pipe drained when the driver's 30 s liveness check finished and `communicate()`
     began — hence a hole of exactly (30 s + check time) − 26.3 s ≈ 3.6 s.
   - Controls (`rig_run*.csv`, `t_in_us` per packet, saved in `day_rehearsal1013/stall_evidence/`):
     three 6000-tick sim runs in their own windows, one of them with python (numpy+pandas import),
     `cmd` and `powershell` launched at 20 / 40 / 55 s: **max packet interval 12 ms, 0 dropped
     ticks** in all three. Rerun of the gate phase with the driver now draining B's stdout in a
     thread: **0 dropped, 0 timeouts**, AUDIT WARN only for the sim's undersampled first window.
   - Kept: `cpp_controller --idle-stop 30` (was a hard-coded 3 idle seconds; now WARN at 3 s,
     stop at 30) and non-timeout `recvfrom` errors are reported and ignored. Runbook rule: never
     pipe or redirect terminal B through another program; the earlier 11,800-timeout gate run was
     the synthetic-block generation (numpy, many threads) running beside the loop — that rule
     stays.
2. **The runcard's fit-phase model check (`--max-packets 1`) waits forever without a loop** (the
   server only counts idle seconds after its first packet). It would have hung terminal A on the
   day. New `--check-model` builds the controller, prints the observer banner and exits 0.
3. **Synthetic TDT block + burst-aware delivery checker: known-answer PASS.**
   `rig/make_synthetic_block.py` writes an `.npz` with the stores `check_impulse_delivery.py` and
   `placement_gate.py` read (Scle/Plse/sSig @ 24414.0625 Hz with the carrier latch at phase 120 of
   240, UDP1 scalars per tick, 64-ch Wav1 @ 610 Hz from the depressing plant, dead time 2 ticks);
   faults injected per event and recorded in `_truth.json`.
   | block | probes | missed | short | exact | long (incl. stretched) | verdict |
   |---|---|---|---|---|---|---|
   | burst1 clean | 605 | 0 | 0 | 605 | 0 | VERIFIED |
   | burst1 faulted (truth 8 / 7 / 578 / 8+4) | 605 | 8 | 7 | 578 | 12 (4 stretched runs) | VERIFIED, 2 warnings |
   | burst1 clean, legacy mode (no `--design-meta`) | 605 | 0 | — | — | — | 385 "multi-pulse" false flags |
   | gate clean | 662 | 0 | 0 | 662 | 0 | VERIFIED |
   The faulted counts equal the injected truth exactly; the legacy single-pulse accounting flags
   every B=3/10 burst as a stall, which is the defect the design-meta mode removes.
   `placement_gate --mode thalamic` on the clean block: 8/8 pairs RESPONSIVE (z 46-63, latency
   20-28 ms, knee 6 µA), footprint eff-rank 3 → GO.
4. **QP conditioning: the cap is binding at small effort ratios, lifting it is free.**
   `--qp-iters/--qp-tol` added to cpp_controller (defaults 200 / 1e-7 unchanged; printed in the
   latency-log banner; selftest case "qp cap reported and lifted" → 17/17). `rig/qp_sweep.py` on
   `plant_opfit12_d2` with `ref_mix_r1`, 3000 sim ticks, pairs 4,6 → ch64:
   | ρ | cap | converged | mean / p99 iters | mean / p99 / max solve (ms) | r0 |
   |---|---|---|---|---|---|
   | 0.1 | 200 | 95.5 % | 21 / 200 | 0.012 / 0.09 / 0.11 | 0.670 |
   | 0.1 | 1000 | 98.6 % | 35 / 1000 | 0.018 / 0.45 / 0.49 | 0.670 |
   | 0.1 | 5000 | 99.1-99.9 % | 69-88 / 2772-4793 | 0.04 / 1.3-2.2 / 2.3 | 0.670 |
   | 0.01 | 200 | 91.2 % | 22 / 200 | 0.012 / 0.09 / 0.15 | 0.668 |
   | 0.01 | 1000 | 99.6 % | 42 / 545 | 0.021 / 0.25 / 0.48 | 0.668 |
   | 0.01 | 5000 | 99.7-100 % | 47-57 / 503-545 | 0.025 / 0.24 / 2.3 | 0.668 |
   (tol 1e-7 vs 1e-6 changes converged % by < 1 point.) Tracking does not move with the cap: the
   unconverged ticks are late iterations on an already-good step. Worst solve 2.3 ms against the
   10 ms tick → `--qp-iters 5000` is live-safe; the runbook now says to add it for any ρ ≤ 0.01
   arm. Not implemented (noted for later): a scale-aware tolerance (∞-norm step relative to umax)
   so the convergence flag means the same thing at every R.
5. **Artifact-aware re-analysis of acute #2: the 09-10 tracking result is artifact-robust, and on
   the cleaned LFP MPC is ahead of Choi.** `day_2026-09-10/analysis/scripts/art64_*` (port of the
   08-31 `art_*` pipeline to the 64-ch planar array, Wav2 @ 24414 Hz, 10 live arm blocks read
   read-only, one block at a time, 64 × 240 k samples each; 19-22 s per block).
   - The carrier latches ~0.94 ms after the Plse edge, so the artifact is a ~0.5 ms biphasic
     spike at +0.8..+1.3 ms (peak median 31 µV in the high-amplitude tercile, 22,510 pulses on
     mpc_r1); the evoked response starts ~2 ms later. A baseline-SD window rule (first pass) ran
     to the 4 ms cap on most channels and excised physiology; the rule now brackets the spike
     (|PTA| > max(10 % of peak, 3 SD) within ±0.7 ms of the peak, padded): windows
     [0.64, 1.26] ms median, max length 1.2 ms (`cache/art64_windows.json`, `art64_pta.png`).
   - Per run, Pearson r of ch64 against the run's reference at lag 0 (feature r0 recomputed from
     the captures by `trk_common.recompute` first; identical to `tracking_*.json`):
     | arm | run-time feature | raw 5-200 Hz | artifact-excised 5-200 Hz | best lag |
     |---|---|---|---|---|
     | mpc r1 / r2 / r3 / r1_late / r4b | .330 / .378 / .381 / .402 / .313 | .202 / .213 / .201 / .216 / .193 | .202 / .214 / .201 / .216 / .192 | 4 / 4 / 4 / 4 / 0 |
     | choi r1 / r2 / r3 / r1_late | .326 / .300 / .394 / .339 | .156 / .159 / .189 / .128 | .156 / .159 / .189 / .128 | 1 / 4 / 3 / 0 |
     | nn r1b | .020 | .037 | .037 | 3 |
     Cleaned and uncleaned are equal to three decimals on every arm (ch64 mean rectified feature
     56.3 vs 56.4 µV): at ≤ 30 µA on this array the pulse artifact carries no energy into the
     5-200 Hz band, so **no 09-10 tracking number was artifact-inflated**. The lower absolute r on
     the LFP than on the run-time feature is the signal, not the cleaning (different band and
     rectification scale than the feature-space reference was built in).
   - Paired per-event MPC-vs-Choi on the cleaned LFP (best lag per event, artifact ticks 0-2
     excluded, SHAM dropped, shared events of r1/r2/r3/r1_late): **n = 317, Δr = +0.074
     [+0.055, +0.092] (5000-resample bootstrap), sign-permutation p < 0.001 → MPC ahead**;
     mean event r MPC 0.40 vs Choi 0.33. Same as 08-31 (+0.079 [0.046, 0.112]) on a different
     array and preparation. `analysis/art64_tracking.json`, `art64_paired.png`, `art64_example.png`.

## Rehearsal record (`day_rehearsal1013/`)

Three passes: the first run (undrained driver pipe), targeted reruns while fixing, and a full
second run of all 12 phases (02:30-03:14, 44 min; `rehearsal_rehearsal1013.json`,
`_first.json` and `_fullrun.json` keep the earlier passes).

| phase | first run | full rerun after the fixes |
|---|---|---|
| phase0 | preflight PASS (3 s) | PASS |
| gate | 268 s; AUDIT FAIL dropped=366; checks ran on the burst block (wrong design) | 270 s; **AUDIT PASS dropped=0 timeouts=0**; gate block GO 8/8, delivery VERIFIED, dead-time json, ingest + gallery on the npz |
| burst | 953 s; dropped=365 | 957 s; WARN (undersampled first window only); delivery VERIFIED; burst-plant fit written |
| gap | 134 s; dropped=367 | 139 s; PASS; gap-scan fit written |
| dutyid | 301 s; dropped=366 | 306 s; WARN (first window); design regenerated with the measured gap |
| fit | MATLAB fit 6 s; dead time centred (max residual ρ 0.014); rank PASS; model check hung 1800 s | 7 s, all four checks PASS (`--check-model` exits by itself) |
| refs | FAIL (`--capture` before `--launch-args`), then skipped on `<V>` | 3 runs written; sim refcheck "Command varies" (fallback model needs the volt-scale baseline 3.3e-5 V, not the int16 sim level — driver fills each) |
| arm mpc / choi | FAIL: no refs | 222 / 222 s, dropped=0; WARN only (sim plant is a sine that does not respond to stim: MPC output constant / Choi undersampled window) |
| rsweep | FAIL: no refs | 222 s, dropped=0; R-schedule built, sweep analysed; WARN as above |
| drift | 124 s; dropped=344 | 120 s; **PASS** |

Every run of the full rerun: `timeouts=0 stale=0 dropped=0 qpConv=100%`. The sim's limitation is
honest and documented: the loop exe's sim source is a sine independent of u, so a plant fitted on
the sim dutyid capture is unobservable (observer pole 1.103 → AUDIT FAIL on the arms in the
second pass) and the closed-loop phases therefore run on the 09-10 fallback model with its own
baseline; they exercise every command, file and check, not tracking.

What the rehearsal changed in the tools (all committed): `rig_runcard.py --sim/--block/--best-ch/
--gap-ticks/--gap-pair/--gap-amp`, space-separated `--blacklist`, `net_diag` without `-Nic`,
`--capture` after `--launch-args`; `rig/rehearse_day.py` (A in background, B blocking with its
stdout drained, liveness at 30 s, per-phase JSON record, `<V>` filled from the dutyid capture in
sim, `--gate-block`); `rig/blockutil.py` (newest block = newest dir holding a `.tsq` at depth ≤ 2,
so the empty `Desktop\Data\Acute3` can no longer be picked; `.npz` reader); `ingest_block --block`,
`plot_trial_responses` and `placement_gate` accept the `.npz`; `check_impulse_delivery --json`.

## Surgery-prep bundles (all tested today)

- **A. Block transfer + data safety.** `pull_blocks.ps1 -Check` (reachability, free space, newest
  block) and `-Once`/`-Watch` (robocopy /E /XO loop, prints NEW BLOCK lines) tested against a
  local fake tank: PASS, copied, exit 0. `archive_day.ps1` rewritten to per-file zipping: a file
  still open for writing is skipped and listed instead of aborting the whole zip (Compress-Archive
  did abort on the running loop's log); 10-09 test: 416 files, 200 MB, 2 skipped. `build_interleaved_run
  --run-offset/--force` protects the r1 references; `0_preflight` prints the sleep setting and free
  space; `2_loop` refuses to run after an AUDIT FAIL unless `override` is typed (tested: aborted
  before the LIVE RUN prompt).
- **B. Date-safe runbook + helper card** for 10-14, every line generated from the runcard;
  `rig/lint_runbook.py`: 0 mismatches for both files. One reconciled cut list; old lists marked
  superseded.
- **C. Safety + animal checklist.** Pre-induction table in Phase 0 (stimulator voltage, PZ2 charger,
  stim safety, reference/ground, electrode map, impedances, physiology monitoring per the lab
  protocol — interval and parameters left blank on purpose). `physio_timer.ps1` 1-minute test:
  beeps, logs the typed reading to `day_<day>/physio_log.csv`, quits on `q`. `check_y_liveness
  --beep` on a dead capture: DEAD, exit 3, alarm. `stim_zero.ps1` for "after any crash".
- **D. Science flow.** dutyid design regenerated with the measured operating gap; gap scan on the
  best responsive pair; `--lam` documented as not implemented.

## Deck

`scripts/deckkit.py` refined house style (Arial, black titles kept; accent rule, kicker, real
bullets, takeaway box, no-style grid tables, section bands, agenda/stat/two-figure slides, speaker
notes) and `check_deck.py` rules (table style, body ≤ 12.5 pt on title-band slides, title > 70
chars WARN, text-only count). Regression: the 10-09 deck rebuilt unchanged → PASS (7 long-title
warnings, pre-existing). `scripts/build_weekly_deck_2026-10-16.py` → `PythonIntanAnalysis/outputs/Synthesis/ClosedLoop_weekly_2026-10-16.pptx`:
19 slides, 8 recomputed figures (dongle timeline, rehearsal before/after Gantt, stall root cause,
delivery matrix, QP sweep, 10-14 plan, artifact example, paired tracking), check_deck PASS with 0
warnings; the results section is a placeholder until the acute-3 blocks are analysed.

## Open items

- **Block transfer over the school network is not viable; USB flash drive by hand on 10-14, 2-3 min
  per block.** The user's usual route (Synapse PC → lab NAS → rig PC) is also out: the Synapse PC's
  Ethernet died in the same event as this PC's onboard port and it now sits on Wi-Fi, too slow for the
  NAS hop. The 10-13 test block (`BSCL20260909BU-261013-195629`, 77 s, 570 MB, all stores) came over
  on the drive and was found by `placement_gate --newest` and `ingest_block`. Prep-day share test
  (evening): `Test-NetConnection DESKTOP-G2170R2 -Port 445` succeeded, `\\DESKTOP-G2170R2\SynapseTanks`
  listed (read-only share to the TDT account, credential stored with `cmdkey`), `pull_blocks -Check`
  PASS; a timed robocopy of one 437 MB block then moved 0.6 MB in 10 min and failed, and port 445 was
  closed afterwards with nothing changed on either PC (the Synapse PC was awake and does not sleep).
  Both machines sit on the school Wi-Fi, so client-to-client SMB is at the mercy of AP roaming /
  client isolation. **Hardware needed:** a direct link between the two PCs (second NIC or a small
  switch on the RZ2's private subnet, or a USB-C/Thunderbolt cable) before the share is used on a
  surgery day. `pull_blocks.ps1` gained `-Tank <prefix>` (share root + newest tank by prefix,
  waits before the first Record), UNC-safe free space, and a sort that does not touch the share twice;
  it works unchanged against the flash drive (`-Source <drive>:\<tank> -Once`). **Hardware for the
  lab:** two dead Ethernet ports in one event → check the lab switch/port for a fault before plugging
  anything else in; a USB-3 SSD (~30 s per block) and, properly, a direct link between the two PCs.
- Push: done 10-13 evening (a5dda73 → 465c384, 10 commits); the 10-13 evening edits are a new commit.
- Defender exclusion for the repo is optional hygiene (not implicated in the stall).
- `run_audit`: an isolated dropped tick (≤ max(3, 0.05 %) per run) is now WARN, not FAIL — the
  full rerun's R-sweep had exactly one (a 27 ms gap at 9.2 s, 6 ms late) in 44 min of runs;
  repeated slips (08-31: 8.5 %, 73 resyncs) still FAIL.
- Not implemented: scale-aware QP tolerance; `--lam`.
