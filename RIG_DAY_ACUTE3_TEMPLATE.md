# Rig day template — ACUTE #3 (date: ______): burst-recovered rank, MIMO, timed to arms by 16:00

Deltas vs acute #2 (all built 2026-09-18, see `docs/SURGERY_DAY_ACCELERATION_2026-09-18.md`
and `docs/ACUTE3_PLAN_2026-09-18.md`): placement GATES replace listening/hunting; duty-cycled
(burst) drive replaces tonic PRBS for ID and for the arms' carrier; y-liveness after every
`go`; one 5-min ID run replaces three ladders; time-controlled R sweep inside one plant epoch.

Conventions carried: 64 ch (`-InputChannels 64`), new Microprobes pair table
`--pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"`, recording started LAST, stim enable ON
at `go`, apps closed, cpp-primary, uMax 30, blacklist from TODAY's Phase 1 only.

## 09:00 Phase 0 — bring-up (engineer, no animal needed)
`Get-PnpDevice` VEN_4550 present → `0_preflight.ps1 -InputChannels 64` → `net_diag` →
`6_udp_selftest -RZ2 10.1.0.100 -LiveStim` (E2 before the animal) → bench 28/28 →
stimulator V ______ → designs staged:
```powershell
python rig\design_burst_probe.py --kind burst-ladder --amps 13 18 25 --burst-ticks 1 --n-per-cond 30 --gap-ticks 30 --out design_rungate.csv     # 4-min placement probe
python rig\design_burst_probe.py --kind burst-ladder --amps 6 9 13 18 25 --burst-ticks 1 3 10 --n-per-cond 20 --out design_runburst1.csv          # recruitment + burst-length ladder (~13 min)
python rig\design_burst_probe.py --kind gap-scan --pairs 4 --burst-ticks 3 --n-per-cond 25 --out design_rungap1.csv                              # recovery-gap scan (2 min)
python rig\design_burst_probe.py --kind duty-prbs --pairs <resp> --burst-ticks 3 --gap-ticks 20 --duty 0.3 --n-slots 1300 --out design_rundutyid.csv  # ID run (5 min); pairs filled after the gate
```
G8 pre-animal thwack test (nThw 150/150, air).

## 11:30 Phase G — cortical placement gate (repeat until GO)
Surgeon seats the 8×8 planar array at the acute-#2 focus (rows 5-6, cols 2-7 of the grid).
```powershell
# 40 thwacks on D1 (or P1), ~45 s, then:
python rig\placement_gate.py --mode cortical --newest
```
GO → continue. MARGINAL/NO-GO → read the ADJUST line (edge → shift toward it; no focus →
move), re-thwack 40×, re-run. Log each cycle: verdict ______ z ______ focus ______.

## 12:15 Phase G' — thalamic placement gate (depth ladder, ≤3 depths)
At each depth (7.6 / 7.8 / 8.0 mm; start with acute-#2 coordinates):
```powershell
.\cpp_controller.exe --mode openloop --play design_rungate.csv --output-count 8 --capture capture_rig_rungate<d>.csv
.\rig\2_loop.ps1 -Run gate<d> -RZ2 10.1.0.100 -InputChannels 64 -TimeoutMs 10 -Ticks 24000 -TickFrames 6
python rig\placement_gate.py --mode thalamic --newest --min-amp 13 --blacklist <ph1 list or none yet>
```
Pick the depth with the most RESPONSIVE pairs and highest eff. rank; a tie → the one whose
footprint-corr matrix has the lowest median. Depth chosen ______, responsive pairs ______,
eff rank ______.

## 13:30 Phase 1 — quiet capture (60 s) + blacklist + baseline
`ingest_block --label quiet` + `analyze_quiet_capture` → blacklist ______ baseline ______ V.
`python rig\check_y_liveness.py --capture <any capture> --baseline <V>` must print LIVE.

## 14:00 Phase 2 — thwack battery, 100/site, 6 sites + SHAM (40 min)
Sites by achievability from the gate focus (acute #2: P1/MP/LP/P3 strongest on ch64/47/39).
Per block: `ingest_block --label "<SITE> thwack" --mode thwack` + `extract_nthw_templates
--site <SITE> --day <date> --min-pulse-ms 50 --n-channels 64`.

## 14:40 Phase 3 — burst-ladder probe (13 min) + gap scan (2 min)
```powershell
.\cpp_controller.exe --mode openloop --play design_runburst1.csv --output-count 8 --capture capture_rig_runburst1.csv
.\rig\2_loop.ps1 -Run burst1 ... -Ticks <nTicks from meta>
python rig\design_burst_probe.py --validate design_runburst1.csv
python rig\check_impulse_delivery.py --block <blk> --capture capture_rig_runburst1.csv --amps 6 9 13 18 25 --pairs "16:12,15:11,14:10,13:9,4:8,3:7,2:6,1:5"
python rig\placement_gate.py --mode thalamic --newest --min-amp 13 --blacklist <list>   # knees per pair
```
Then gap scan (pair 4 or the strongest pair): the response ratio test/cond vs gap sets the
**operating gap** for the day (first gap where ratio ≥ 0.8): ______ ticks.
Offline in parallel: per-pair burst-length dependence (1/3/10 ticks) = the burst plant.

## 15:00 Phase 4 — duty-cycled operating-point ID (5 min) → MIMO fit → rank gate
Fill `--pairs` with the responsive set; `--gap-ticks` = operating gap; `--duty 0.3`.
```powershell
.\cpp_controller.exe --mode openloop --play design_rundutyid.csv --output-count 8 --capture capture_rig_rundutyid.csv
.\rig\2_loop.ps1 -Run dutyid ... 
python rig\check_y_liveness.py --capture capture_rig_rundutyid.csv --baseline <V>
matlab -batch "cd('<repo>'); r = fit_sysid_from_capture('capture_rig_rundutyid.csv', struct('useOutputs',[<c1> <c2> <c3>],'orders',1:3,'save',true)); export_plant_lti('plant_duty.lti',10)"
python rig\check_mimo_rank.py --model plant_duty.lti
```
GO: per-output |corr| > 0.1 on ≥ 2 channels AND rank gate PASS. Control channels ______
(choose channels riding DIFFERENT pair footprints: the gate's footprint maps show them).
Fallback (rank gate FAIL): p = 1 on the best channel, pairs = top-2 by knee; the day still
yields the burst-vs-tonic comparison (Phase 6c).

## 15:30 Phase 5 — references + tapes + manifest (30 min)
`build_interleaved_run.py --templates-dir ... --sites <6> --channels <c...> --baseline <V>
--model plant_duty.lti --runs 3 --events 100 --umax 30 --pairs <resp> --out-dir day_<date>`.
Choi tapes: `--lam` smoothness if they slam the cap (step-transient artifact, 08-31 finding).
MPC weights: `--q-weight 1e12 --r-weight 100` per output; sim-verify u pushes
(`closed_loop_sim.py --pairs ... --feature-map ...`) BEFORE the first arm.

## 16:00 Phase 6 — ARMS (3 h)
Order (cut from the bottom): 
6a r1 MPC → r1 Choi → **y-liveness after each `go`** → score (`tracking_metrics`, `ingest_block --mode arm`).
6b **decoupled-target run** (`build_decoupled_ref.py` on ref_mix_r1) — the MIMO selectivity exhibit.
6c **burst-vs-tonic paired run**: same schedule r1, MPC with the carrier held at duty 0.3 vs
   continuous (two 3.7-min runs back to back) → does the burst carrier keep the plant's rank
   during control? (charge and r reported for both).
6d **time-controlled R sweep**: R ∈ {100, 30, 10} as three 60-event runs INTERLEAVED
   (R100, R30, R10, R100, R30, R10 …, 20 events each block) inside one 12-min run so drift
   cannot confound the charge–fidelity frontier.
6e r2 MPC/Choi; NN arm (forward-model-based tape, see NN review) if trained by then.
6f early/late repeat of r1 (both arms) — never cut.

## 19:00 Phase 7 — drift + wrap (30 min)
Re-probe (duty-ID replay 2 min) → per-output |corr| drift ______; stim zero
(`send_envelope.py --rz2 10.1.0.100 --shape const --umax 0 --secs 2 --count 8 --yes`);
commit + push both repos; ledger rows auto-appended.

**Cut order if late:** 6e NN → 6d R sweep → 6c → 6b → r2. Keep 6a + 6f.
