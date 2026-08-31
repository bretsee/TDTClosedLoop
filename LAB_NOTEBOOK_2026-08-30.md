# Lab notebook — 2026-08-30 (Sunday, suite): 32-ch gates G3–G9 → GO-at-32

Fast-path session (~1 h of rig time). All remaining Saturday gates banked
except G8, which moves to first thing Monday (thwacker not in the suite
tonight; low risk — nThw was hardware-validated 08-26 and is width-independent,
the 32-wide extractor is regression-tested). **DECISION: GO-at-32.** The
Monday deltas are applied to `RIG_DAY_2026-08-31.md`; the circuit is frozen
until surgery.

## Prep (before user arrived)

Card OK on PCI; preflight PASS at 32; probe design `design_runrnd30.csv`
pre-generated with 1c_server's exact defaults and validated (32 cond,
~15 trials/amp/pair, DESIGN VERIFIED) so the server started instantly.

## G3 — bath quiet capture (block `BSClosedLoop32-260830-211918`) — PASS

**TEMPORARY TEST ARRAY** (user's deliberate choice to protect the real array
during bring-up) — **this blacklist does NOT carry to Monday.**
- All 32 channels live. Floors mostly 30–37 µV (≈3× the 08-26 16-ch
  headstage's 8–11 µV — plausibly this array's impedance; evoked responses are
  100s of µV so SNR is workable). Baseline (MAV6) ≈ 2.75e-5 V.
- Common-bath cross-corr (median-common): **blacklist ch 19 (−0.42), 26
  (0.38), 30 (0.27)** — same floors are the noise outliers (99/87/125 µV);
  marginal 0.70–0.85: ch 8, 15, 16, 21, 22, 25, 28. 29/32 usable → gate met.
- 60 Hz fraction 74% → fit-side notch plan unchanged.

## G5 (+ the deleted G4's evidence) — delivery re-bank (block
`BSClosedLoop32-260830-213455`, run rnd30, 28k ticks @ -InputChannels 32) — PASS

- Loop: 28000/28000, dropped=0, window 6/6/0, `channelMode=exact(in=32
  card=32)`. Watch: 2 PLL resyncs early with seconds-scale phase errors
  (likely start-order/backlog interplay; phaseErr avg 0.61 ms otherwise).
- **Wire == design 473/473, 0 lost.** Pair map word k → (2k−1, 2k) EXACT 8/8,
  inversion exact. Carrier 101.725 Hz = base/240, 6.000 samples/period.
- The user hit stim-enable ~40 s late (deliberately noted as a bonus safety
  retest). check_impulse_delivery printed FAIL "9.5% carrier races" — **that
  attribution is WRONG for this run**: all 45 missed probes lie in
  12.8–37.7 s = the enable hole exactly (45 expected from the timing).
  **Post-enable delivery = 428/428 single-pulse, 0 missed, 0 doubled** despite
  a 2.05 ms phase margin. Enable-gate-blocks-Scle re-confirmed on the 32-ch
  circuit. (Tool gap noted: the auditor doesn't model an enable hole and
  mis-bins those probes as phase races — same story as 08-27's "12 missed".)

## G6 — artifact at 32 (`--own-pair none`) — PASS
ARTIFACT MODERATE, 0 fail / 0 warn → `--feature-trim` stays OFF. Re-assess on
the first in-vivo probe block (standing rule).

## G7 — 13 s MPC at 32, warm-width fix live (block
`BSClosedLoop32-260830-215130`, capture_mpc_20260830_215035) — PASS
- 1300/1300, dropped=0, `exact(in=32 card=32)`, `policy=fresh` by tick 18.
- **`-FeatureCount 32 -FeatureChannel 20` ran clean — no BadFeatureChannel**
  (the pre-fix code threw on the first packet; bench check 13 shows the throw).
- freshTicks 97.6% / timeouts 11.7% — inside the 08-27 watch band.
- slope u1-on-r **9.87** (cl4 9.7, 08-27 mpccheck 9.06 — signature matches);
  y NOT TRACKING = correct saline null.

## G9 — fit-path timing on real 32-ch data — PASS
- `fit_impulse_model` per-input: all 8 inputs correctly REFUSE in saline
  (clean negative control, mirrors 08-18's 24/24); all-8 wall time 5.6 s.
- **Full 32-channel `sweep_channels` on the 28k-tick capture: 12.4 s.** The
  2× runtime concern is dead; Phase-4's 40-min budget is safe by two orders.

## Deferred / carried

- **G8 → Monday first thing** (first Phase-2 block doubles as the gate):
  one thwack block → `extract_nthw_templates --n-channels 32` → (32,122) npz,
  onset count ≈ programmed count. Runbook updated to say so.
- Monday Phase 1 derives the REAL array's blacklist; neither today's
  (19/26/30, test array) nor ch-13 (16-ch headstage) carries.
- Watch items: PLL resync pair at rnd30 start; noise-floor regime is
  array-dependent (don't judge Monday's floors against 8-11 µV absolutes).

## Decision

**GO-at-32.** `RIG_DAY_2026-08-31.md` now carries the 32-ch deltas everywhere
(`-InputChannels 32`, `-FeatureCount 32`, `--n-channels 32`, `--own-pair
none`, `--expect-input 32`, banner gate = 32, blacklist prose = Phase-1-of-day).
Do not touch the Synapse circuit before Monday; never run Detect.
