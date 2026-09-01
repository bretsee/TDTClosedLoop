# Lab notebook — 2026-08-31 (Monday, SURGERY DAY): first closed-loop biomimetic tracking

**Headline: closed-loop MPC reproduced touch-shaped cortical activity from
thalamic microstimulation in vivo — TRACKING verdicts on all four arm runs
(2× MPC, 2× Choi open-loop, paired randomized interleaved schedules), with a
drift-controlled value-of-feedback signature.** Full per-block record:
`BLOCK_LEDGER_2026-08-31.md` (21 blocks). 32-ch recording ran flawlessly all
day (every run 22,200/22,200 or better, dropped=0, `channelMode=exact(in=32
card=32)`).

## Morning

Phase 0 all green (card OK, preflight 32, net, UDP A–E2 with the live packet
pre-animal). G8 closed: thwack test block → (32,122) template, 150/150. uMax
set 30. Longer-than-expected surgery; array localization by audio through the
PZ2 (thalamic contacts 2,3,6,7,13 touch-responsive — this mattered later).

## Implant + battery

- Phase 1 quiet: superb prep — 60 Hz down to 7.6% (was 74% saline; no notch
  needed), LFP 75–300 µV; **blacklist ch 27** (corr −0.01), watch ch 14.
- Phase 2: full 10-block thwack battery, every real site split-half ≥ 0.92,
  peaks 382–709 µV, **modal best channel 8** (8/9 sites; LP → ch 6).

## The NO-GO and its reversal (the day's scientific pivot)

Phase-3 probing (4,257 probes, amps 2–25) + a 30 µA re-probe both REFUSED in
the standard fitter; sweep best |corr| 0.071. Systematic isolation: recording
side proven (touch templates), delivery proven (wire 100%, artifact MODERATE
in cortex = current flows). The user challenged the reposition call, citing
the thalamic audio. A raw-LFP signed-average deep dive then found **real
evoked responses the MAV fitter missed**: pair 4 → +241 µV @ 13 ms (z=23.5),
pair 1 → +121 µV (z=9.7), spatial footprint r = 0.97–0.99 vs the touch
templates, **recruitment threshold ~13–18 µA** — the through-origin linear
fit had averaged sub-threshold amps into oblivion. The 2026-08-06
control-coverage prescription (tonic operating point) applied verbatim:
PRBS 10↔30 µA on pairs 1+4 (never below the knee) → **|corr| 0.224–0.228,
GO**; model saved (2-in/1-out ch 8, order 4, uOff≈[20.0 20.1]).
Races time-course note: rnd1's doubles were front-loaded (26.9%→1.1% at
t≈3 min) — a browser-close CPU stall forced a PLL re-lock onto a luckier
carrier phase; rules adopted (apps closed before runs, per-run margin check,
30 s burn-in).

## Three scale-mismatch bugs, one family (volt-unit features)

1. **Choi mu**: default 1e-9 ≫ available tracking gain → u≈0 tapes. Fixed
   mu=1e-13; gate disabled (the operating-point model embeds the knee; the
   gated problem's all-attenuated local minimum is the known disconnected-set
   failure).
2. **Choi horizon**: dense G at T=22,200 needs 7.9 GB → synthesized one
   220-tick event period and tiled 100×.
3. **MPC weights**: first arm run's u sat at exactly uOffset — at volt scale
   the QP objective (~1e-7) is below OSQP tolerance. Fixed
   **`-QWeight 1e12 -RWeight 100`** (objective rescaled; R/Q ≈ g²);
   bench-verified before re-running.

## Design changes (user-driven, better science)

- **Interleaved randomized event schedules** replaced blocked per-site runs
  (thalamocortical adaptation control): 100 events/run, balanced deck over
  D1/D2/D3/P2/LP + SHAM catch trials, 2 s gaps; **identical seeded schedule
  shared by both arms** → paired per-event comparison.
  Artifacts: `day_2026-08-31/ref_mix_r{1,2,3}.csv`,
  `design_choi_mix_r{1,2,3}.csv`, `schedule_mix_r{1,2,3}.json`.
- Site subset chosen by achievability (stim authority ≈ 240–320 µV at
  uMax 30 ≈ 35–45% of the largest touch templates).
- **Tonic carrier between events** (hold ≈ 20 µA, modulate during events) —
  required by the knee; the analytic contrast is modulate-vs-hold. Interpretive
  caveat recorded: continuous drive, more charge, possible slow tonic adaptation.
- **Standing goal recorded: multichannel control at maximum achievable rank**
  (today single-channel ch 8 by toolchain; with 2 pairs the controllable rank
  is ≤2 and the stim footprint ≈ touch footprint, so ch-8 control ≈ the
  rank-1 optimum; full 32-ch match is an offline analysis on the recorded data).

## Results (tracking ch 8, `tracking_*_{mixr*}.json/png` in day_2026-08-31/)

| run | arm | rBest @lag | r0 | slope y/r | RMSE | verdict |
|---|---|---|---|---|---|---|
| mixr1b | MPC | 0.725 @ +2 | 0.393 | 0.92 | 1.06e-4 | TRACKING |
| mixr1 | Choi | 0.716 @ +1 | 0.573 | 1.15 | 0.89e-4 | TRACKING |
| mixr2 | MPC | 0.712 @ +2 | 0.380 | 0.83 | 0.98e-4 | TRACKING |
| mixr2 | Choi | 0.704 @ +2 | 0.452 | 0.92 | 0.94e-4 | TRACKING |

- Fresh off ID, open-loop Choi edges MPC on RMSE/lag-0 (its tape rides the
  0-timeout cpp path). Across ~25 min, **Choi's lag-0 r decayed 0.573→0.452
  while MPC held 0.393→0.380** — value-of-feedback signature — and the drift
  re-probe shows the plant itself HELD (|corr| 0.224→0.248), so the decay is
  open-loop sensitivity, not prep death. (Two-run trend; the per-event paired
  analysis on the shared schedules is the proper test, offline.)
- ~20 ms tracking latency = physiological thalamocortical delay.

## End of session

Stim wire zeroed (400 zero packets; note `send_envelope` flag is `--shape
const`, not `--kind` — runbook line stale).

---

## OVERNIGHT ANALYSIS (run while the user slept; three parallel deep dives)

Everything in `day_2026-08-31/analysis/` (13 figures, 3 summary JSONs,
reproducible scripts; per-trial caches local-only, not committed). Deck:
`PythonIntanAnalysis/outputs/Synthesis/AcuteClosedLoop_2026-08-31_results.pptx`
(17 slides), builder `scripts/build_results_deck_2026-08-31.py`.

**Refinements to the live conclusions (the honest version):**
1. **MPC-vs-Choi is a TIE on shape fidelity at each arm's own best lag**
   (Δr −0.007 [−0.034,+0.019], p=0.63, n=161 paired events) — the live "MPC
   wins at lag 0" was Choi's run-1 latency sitting at +1 tick. MPC's real,
   defensible advantages: **latency stability** (~2.1 ticks both runs vs Choi
   1.3→1.8) and **within-run stability** (Choi decays −0.13 r/100 events at
   best lag, both runs; MPC never degrades) → MPC wins outright beyond ~100
   events. Plus **29.5% less charge** for the tied fidelity (Choi rides the
   30 µA cap 48% of ticks; MPC hugs hold, never full-off).
2. **SHAM catch trials clean**: false-touch 0/32 (MPC), 1/33 (Choi); d′ 4.2 /
   3.6; Hold control flat (r 0.004±0.125) — tracking is controller action.
3. **HEADLINE NEGATIVE — no site-selectivity**: Mahalanobis nearest-template
   classification of arm-evoked 32-ch patterns = 19–22% vs 20% chance. One
   control channel + one fixed stim footprint cannot choose WHICH site it
   reproduces (the acute rank/selectivity ceiling, live). Touch itself IS
   decodable (48% ten-way) — the ceiling is on the stim side.
4. **Artifact confound in biological-space validation**: raw-Wav1 arm-event
   averages are contaminated by overlapping continuous-stim artifact (Choi
   worst); TRACKING verdicts are FEATURE-space. Single-pulse probes (artifact
   separable) do show real touch-footprint responses (r 0.96–0.99), so drive
   is real — but artifact-aware analysis (pulse-resolved 24 kHz, signed
   features, trim) is the top queue item before claiming biological
   reproduction during the arms.
5. Peak overshoot ~2× on single-tick peaks (onset jitter, not gain);
   sub-spontaneous-floor targets unreachable; final drift re-probe (opfit2)
   had degraded PC timing (8.5% dropped ticks, 73 resyncs) — treat its fit as
   indicative; cpp server didn't write latency CSVs for choi arm runs (add to
   preflight checklist).
6. Engineering: MATLAB server p50 1.69 ms vs cpp 17 µs (~100×); all four arm
   runs p95 tick error < 1.9 ms, zero dropped ticks, no mid-run resyncs.
