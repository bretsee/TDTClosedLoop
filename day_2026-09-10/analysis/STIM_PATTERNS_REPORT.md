# Stimulus patterns by controller and touch site (acute #1 and #2)

Question: what stimulus does each controller actually emit for each touch site, and do the controllers differ?
Arms: MPC (closed loop), Choi (open-loop QP tape), NN (learned inverse tape, acute #2 only).
Every number below is read from `_stim_patterns.json` (one per day), produced by
`day_2026-09-10/analysis/scripts/stim_patterns.py` and `day_2026-08-31/analysis/scripts/stim_patterns.py`
(shared logic in `day_2026-09-10/analysis/scripts/stim_patterns_common.py`).

Conventions. Window = onset-20 .. onset+199 ticks (220 = one schedule period, 10 ms ticks). Acute #2 arrays come from
`trk_common.load()` (SKIP=50 rows, onset index = onset_tick-50, identical to the trk_ scripts); acute #1 follows
`sci_common.py` (no skip, tick 1 = row 0, onset index = onset_tick-1, capture truncated to min(len capture, len ref);
the 08-31 MPC captures are 21601 / 21348 rows so 3 / 4 trailing events drop: 97 + 96 MPC events vs 100 + 100 Choi).
"Summed command" = sum of the two active pairs (u4+u6 on 09-10, u1+u4 on 08-31; cap 30 uA per pair, so 60 = both at cap).
Hold = median of the 20 pre-onset ticks (a mean is contaminated by the controllers' 3-4-tick preview lead).
Charge = uA*ticks over the 220-tick window. Cap fraction = fraction of (tick, pair) samples >= 29.5 uA.
Lag = cross-correlation lag of the hold-subtracted summed command vs the reference template; negative = command leads.
Runs pooled: MPC r1-r3 and Choi r1-r3 (09-10, 60 events per site), MPC r1-r2 and Choi r1-r2 (08-31, 32-34 per site), NN r1b (20 per site).

## Big-picture table

### Acute #2 (2026-09-10), pairs u4+u6, control channel y64

| site | MPC peak uA | MPC hold uA | MPC t-peak | MPC charge/ev | MPC cap frac | MPC cmd-ref r | Choi peak uA | Choi hold uA | Choi t-peak | Choi charge/ev | Choi cap frac | Choi cmd-ref r | NN peak uA | NN hold uA | NN t-peak | NN charge/ev | NN cap frac | NN cmd-ref r | MPC-vs-Choi r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LP | 60.0 | 6.1 | -2 | 1729 | 0.02 | 0.67 | 60.0 | 0.0 | -2 | 501 | 0.02 | 0.70 | 34.5 | 29.6 | 11 | 6508 | 0.00 | 0.52 | 0.90 |
| P1 | 60.0 | 6.1 | -2 | 1966 | 0.03 | 0.69 | 60.0 | 0.0 | -3 | 753 | 0.04 | 0.72 | 34.2 | 29.6 | 11 | 6512 | 0.00 | 0.54 | 0.91 |
| MP | 60.0 | 6.2 | -2 | 1762 | 0.03 | 0.68 | 60.0 | 0.0 | -3 | 548 | 0.03 | 0.70 | 34.4 | 29.6 | 11 | 6506 | 0.00 | 0.53 | 0.91 |
| P3 | 60.0 | 6.0 | -2 | 1813 | 0.03 | 0.70 | 60.0 | 0.0 | -2 | 585 | 0.03 | 0.75 | 33.8 | 29.6 | 11 | 6508 | 0.00 | 0.52 | 0.91 |
| SHAM | 14.6 | 5.8 | 7 | 1320 | 0.00 | 0.82 | 3.7 | 0.0 | 6 | 8 | 0.00 | 0.67 | 30.0 | 29.6 | 8 | 6517 | 0.00 | 0.97 | 0.63 |

### Acute #1 (2026-08-31), pairs u1+u4, control channel y8

| site | MPC peak uA | MPC hold uA | MPC t-peak | MPC charge/ev | MPC cap frac | MPC cmd-ref r | Choi peak uA | Choi hold uA | Choi t-peak | Choi charge/ev | Choi cap frac | Choi cmd-ref r | MPC-vs-Choi r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 54.0 | 40.8 | -1 | 9069 | 0.00 | 0.79 | 60.0 | 27.3 | -3 | 11894 | 0.49 | 0.10 | 0.24 |
| D2 | 53.4 | 40.7 | -1 | 9070 | 0.00 | 0.81 | 60.0 | 25.9 | -3 | 11839 | 0.49 | 0.09 | 0.26 |
| D3 | 53.1 | 40.6 | -1 | 9081 | 0.00 | 0.81 | 60.0 | 25.7 | -3 | 11771 | 0.48 | 0.09 | 0.27 |
| P2 | 53.4 | 40.6 | -1 | 9079 | 0.00 | 0.80 | 60.0 | 25.2 | -3 | 11793 | 0.48 | 0.09 | 0.28 |
| LP | 55.0 | 40.5 | -2 | 9082 | 0.01 | 0.77 | 60.0 | 22.6 | -3 | 11736 | 0.48 | 0.09 | 0.31 |
| SHAM | 43.3 | 41.1 | 15 | 9060 | 0.00 | 0.84 | 60.0 | 38.5 | 4 | 12109 | 0.52 | 0.15 | 0.18 |

t-peak = ticks after window t=0 of the summed-command maximum (negative = before the template departs baseline).
cmd-ref r = command-vs-reference correlation at the best lag (per event, then averaged).
MPC-vs-Choi r = correlation of the two arms' hold-subtracted mean summed-command patterns at lag 0.

## Key findings

1. **On acute #2 both MPC and Choi drive both pairs to the 30 uA cap at every real-site event** (summed peak 60.0 uA on 300/300 events each) and do it *before* the template: t-peak -2 (MPC) / -2 to -3 (Choi); per-event cross-correlation lag MPC -1.9 +/- 0.2 ticks, Choi -3.0 +/- 0.0 (negative = command leads the reference). The cap is touched briefly -- 3.0 % of pair-ticks for both arms (about 6.6 pair-ticks per 220-tick period). The NN tape never reaches cap (summed peak 34 uA, 17 / 20 uA per pair) and *lags* the reference by +9.3 ticks.

2. **MPC re-derives the Choi tape on-line.** Mean-pattern correlation MPC-vs-Choi per site is 0.90-0.91 at lag 0 and 0.99 at the best lag (+1 tick: Choi's tape leads MPC by one tick), on every real site. Both arms put a 60 uA edge at onset followed by a smaller second lobe whose timing is the only site-dependent feature (LP one lobe at +7, P1 two lobes at +10 / +16, MP two small lobes, P3 one lobe at +12). Per-event paired peak is uninformative (both saturate; r = 0.9998).

3. **Charge: MPC 1817 vs Choi 597 uA*ticks per event (3.0x) on acute #2, but the whole difference is MPC's tonic hold.** MPC holds u6 at 6.1 uA (u4 at 0); 6.1 x 220 = 1342 of its charge is hold (the SHAM row, 1320, is essentially hold only). Charge *above hold* is MPC 624 vs Choi 597 (+4.5 %). Choi sits at the floor (<= 0.5 uA) 92 % of ticks. NN is the opposite regime: tonic 14.7 / 14.9 uA on both pairs (6508 uA*ticks per event, 3.6x MPC) with only 18 uA*ticks of modulation above hold (depth 4.6 uA).

4. **Neither controller emits a site-specific command; between-site command similarity simply mirrors between-site reference similarity.** Acute #2, real sites: mean between-site correlation of the summed command pattern is 0.82 (min 0.67) for MPC, 0.83 (0.71) for Choi, 0.98 (0.96) for NN, versus 0.915 (min 0.82) for the reference templates themselves. Where references are near-identical (P1 / MP / P3: r 0.97-0.99) commands are near-identical (0.85-0.93); the one template that differs (LP, ref r 0.82-0.88 vs the others) gives the one command that differs (0.67-0.80). Same two pairs, same 60 uA edge -- site identity is carried only by the timing / amplitude of the secondary lobe on one channel. Acute #1 is starker: Choi between-site 0.99 (min 0.99), MPC 0.94 (0.90), references 0.95.

5. **Leave-one-out nearest-centroid site decoding from the command is 1.00 for every arm** (chance 0.20 on 09-10 / 0.17 on 08-31; permutation-null 95th percentile 0.27 / 0.23; 1.00 also with peak-normalised, shape-only patterns). This is expected, not a selectivity result: the tapes are deterministic and MPC is a deterministic function of a fixed per-site template, so any consistent difference in the references is decodable. The known ~chance decoding of the achieved y is the informative side (not redone here).

6. **Acute #1 was a different regime on both arms: tonic bias.** MPC held 40.6 uA summed (u1 20.0 + u4 20.6) and pulsed to 53-55 (u4 to cap, u1 to ~24): cmd-ref r 0.79, lag -1.7, cap fraction 0.4 %, charge above hold 165 uA*ticks. Choi's 08-31 tape rode u4 at the cap 87 % of ticks (any pair at cap 88 %) and produced the touch transient by a *withdrawal-then-step*: u1 dropped to 0 for ~16 ticks before onset, u4 dipped to ~0 at -5..-3, then both stepped to cap at -3. That pattern barely resembles the template (cmd-ref r 0.09) and is near-identical across sites (0.99); charge above hold 6359 uA*ticks (39x MPC), total 11 807 vs MPC 9076. MPC-vs-Choi pattern correlation on 08-31 is only 0.24-0.31 (vs 0.90 on 09-10).

7. **Cross-acute LP (only shared site; different plants -- 08-31 32-ch, pairs 1+4 -> y8; 09-10 64-ch planar, pairs 4+6 -> y64):** MPC's LP command pattern correlates 0.59 (0.65 at best lag) across the two plants -- the same lead-edge-plus-lobe strategy on a different hold (40.5 vs 5.8 uA). Choi's correlates 0.02: the QP found a saturated withdrawal-step solution on acute #1 and a clean pulse on acute #2. Achieved LP y patterns correlate 0.62 (MPC) / 0.60 (Choi) across acutes; the 08-31 reference peak was 552 uV vs 199 uV on 09-10.

8. **MPC's command is stationary over ~2 h (r1 vs r1_late, same tape):** pattern correlation 0.999-1.000 on every real site, charge ratio 1.00 (0.999-1.008), hold 6.1 -> 6.0 uA, cap fraction unchanged (0.023-0.035). The feedback path did not move the command even though the plant drifted (per-event y peak LP 277 -> 243 uV, P1 273 -> 309 uV). The Choi tape is identical by construction (1.000).

9. **The MPC input penalty changes the operating point, not the shape (r4b, R = 0.3 vs r1, R = 100):** pattern correlation 0.99 on every real site (0.98 SHAM); charge x1.71 (1.63-1.75 per site; x2.00 on SHAM), which is entirely the hold doubling (6.1 -> 12.1 uA summed) -- modulation depth actually fell 53.9 -> 47.9 uA (0.89x) and cap fraction 0.030 -> 0.025. Lowering R buys tonic current, not a different pulse.

10. **SHAM rows are the controllers' baseline behaviour.** MPC still emits a 14.6 uA summed bump (+8.8 over hold) at +7 for the ~7 uV sham template on 09-10 (cmd-ref r 0.82 -- it faithfully tracks a tiny template); Choi's tape has a 3.7 uA blip; NN is all hold (30.0 uA, charge 6517). On 08-31 Choi's SHAM tape still steps to the 60 uA cap (peak 60, cap fraction 0.52).

Caveat: per-event y peaks quoted in 7-8 are maxima of a noisy trace (biased upward); the achieved-y comparison per site is in the middle panel of each `stim_site_<SITE>.png` (mean +/- SD vs reference).

## Files

Scripts (added to `run_all.py` ORDER after `trk_nn_negative.py`):
- `day_2026-09-10/analysis/scripts/stim_patterns_common.py` -- loaders (both days), windowing, metrics, similarity, decoding, figures
- `day_2026-09-10/analysis/scripts/stim_patterns.py` -- acute #2 driver (+ early/late, R-weight, cross-acute LP)
- `day_2026-08-31/analysis/scripts/stim_patterns.py` -- acute #1 driver (imports the common module by path)

Acute #2 outputs (`day_2026-09-10/analysis/`):
- `_stim_patterns.json` -- all numbers (per-run and pooled traces, per-event metrics, similarity matrices, decoding, table, extras)
- `stim_overview.png` (FULL: rows = sites, cols = pairs u4 / u6, MPC / Choi / NN mean +/- SD, scaled reference guide)
- `stim_table.png` (WIDE heat-table), `stim_charge.png` (WIDE: charge/event and cap fraction by site x arm)
- `stim_site_LP.png`, `stim_site_P1.png`, `stim_site_MP.png`, `stim_site_P3.png`, `stim_site_SHAM.png` (FULL, 3 panels: command per pair, achieved y64 vs reference, per-event peak / charge-above-hold strips)
- `stim_cross_acute_LP.png`, `stim_early_late.png`, `stim_rweight.png` (WIDE)

Acute #1 outputs (`day_2026-08-31/analysis/`):
- `_stim_patterns.json`, `stim_overview.png`, `stim_table.png`, `stim_charge.png`
- `stim_site_D1.png`, `stim_site_D2.png`, `stim_site_D3.png`, `stim_site_P2.png`, `stim_site_LP.png`, `stim_site_SHAM.png`
